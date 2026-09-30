"""Texas sales-tax FILING RECORD (Kerry 2026-09-30, #1047: "I approve the
sales_tax_filings table"; he asked to "track Sales Tax payments completely
for the year"). The table is created by migrations/0001_sales_tax_filings.sql.

A month is FILED only from a row here: never from the calendar. Status is
FILED when a row exists; otherwise LATE once past its due date, else OPEN.
Evidence is either the WebFile confirmation ('confirmation') or Kerry's
stated word ('kerry_word', 9/30: "I've made payment on all but August").

Writes are dry runs unless apply=True, and every applied write is logged in
agent_action_log.
"""
from __future__ import annotations

from datetime import date

FIELDS = ("period", "due_date", "filed_at", "total_tx_sales", "taxable_sales", "tax",
          "discount", "penalty", "interest", "amount_paid", "webfile_ref", "payment_ref",
          "confirmation_path", "evidence", "note", "entered_by")
MONEY = ("total_tx_sales", "taxable_sales", "tax", "discount", "penalty", "interest", "amount_paid")
FILING_DAY = 20


def due_date_for(period: str) -> str:
    y, m = int(period[:4]), int(period[5:7])
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{ny:04d}-{nm:02d}-{FILING_DAY:02d}"


def status_for(period: str, filed: dict | None, today: str | None = None) -> str:
    if filed:
        return "FILED"
    today = today or date.today().isoformat()
    return "LATE" if due_date_for(period) < today else "OPEN"


def filings(conn) -> dict:
    try:
        return {r["period"]: dict(r) for r in conn.execute("SELECT * FROM sales_tax_filings")}
    except Exception:
        return {}


def _validate(row: dict) -> list:
    p = str(row.get("period") or "")
    errs = []
    if len(p) != 7 or p[4] != "-" or not (p[:4] + p[5:]).isdigit():
        errs.append("period must be YYYY-MM")
    if row.get("evidence") not in ("confirmation", "kerry_word"):
        errs.append("evidence must be 'confirmation' or 'kerry_word'")
    if row.get("evidence") == "confirmation" and not (row.get("webfile_ref") or row.get("confirmation_path")):
        errs.append("a 'confirmation' row needs webfile_ref or confirmation_path")
    if not row.get("entered_by"):
        errs.append("entered_by is required")
    for k in MONEY:
        v = row.get(k)
        if v not in (None, ""):
            try:
                float(v)
            except (TypeError, ValueError):
                errs.append(f"{k} must be a number")
    return errs


def record_filing(row: dict, apply: bool = False, db_path=None) -> dict:
    from email_parser import database as db
    row = {k: row.get(k) for k in FIELDS}
    if row.get("period") and not row.get("due_date"):
        row["due_date"] = due_date_for(row["period"])
    for k in MONEY:
        if row.get(k) in ("",):
            row[k] = None
        elif row.get(k) is not None:
            row[k] = round(float(row[k]), 2)
    errs = _validate(row)
    if errs:
        return {"error": "; ".join(errs), "row": row}
    with db._connect(db_path) as conn:
        prior = filings(conn).get(row["period"])
        if not apply:
            return {"dry_run": True, "row": row, "replaces": prior}
        cols = [k for k in FIELDS]
        conn.execute(
            f"INSERT INTO sales_tax_filings ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
            f"ON CONFLICT(period) DO UPDATE SET "
            + ", ".join(f"{k} = excluded.{k}" for k in cols if k != "period")
            + ", updated_at = datetime('now')", [row[k] for k in cols])
        conn.commit()
    db.log_agent_action(row["entered_by"], "sales_tax_filing",
                        f"{row['period']} {row['evidence']} paid={row.get('amount_paid')} "
                        f"ref={row.get('webfile_ref')}" + (" (replaced prior row)" if prior else ""))
    return {"applied": True, "row": row, "replaced": prior}


# The register as verified 9/30 (docs/claude/sales-tax-register.md): six
# months with WebFile confirmations, and the months Kerry says are paid
# whose confirmations sit in iCloud (amounts to be added when copied).
_REG_CONF = "OneDrive: 3_Events/2025/0 Financial/Sales Tax/ or TGF Financial/TGF Transaction Logs/Bookkeeping/Sales Tax/<YYYY>/ (per sales-tax-register.md)"
BACKFILL = [
    ("2025-01", "2025-02-20", 2433, 1250, 103.13, -0.52, 102.61, "5125311547"),
    ("2025-02", "2025-03-20", 2675, 1343, 110.80, -0.55, 110.25, "7925264448"),
    ("2025-03", "2025-04-21", 6271, 1752, 144.54, -0.73, 143.81, "11125470461"),
    ("2025-07", "2025-08-18", 25440, 3400, 280.50, -1.40, 279.10, "23025237478"),
    ("2026-02", "2026-03-20", 7810, 1699, 140.17, -0.70, 139.47, "7926255547"),
    ("2026-03", "2026-04-04", 22057, 3515, 289.99, -1.45, 288.54, "9426022559"),
]
KERRY_WORD = ["2025-04", "2025-05", "2025-06", "2025-08", "2025-09", "2025-10", "2025-11",
              "2025-12", "2026-01", "2026-04", "2026-05", "2026-06", "2026-07"]


def backfill(apply: bool = False, db_path=None) -> dict:
    rows = []
    for period, filed, tx, taxable, tax, disc, paid, ref in BACKFILL:
        rows.append({"period": period, "filed_at": filed, "total_tx_sales": tx,
                     "taxable_sales": taxable, "tax": tax, "discount": disc, "amount_paid": paid,
                     "webfile_ref": ref, "confirmation_path": _REG_CONF, "evidence": "confirmation",
                     "entered_by": "tracker-claude (Tracker Build) from the CFO register 2026-09-30"})
    for period in KERRY_WORD:
        rows.append({"period": period, "evidence": "kerry_word",
                     "note": "Kerry 2026-09-30: \"I've made payment on all but August.\" Confirmation "
                             "in iCloud, not yet in OneDrive; amounts to be added when copied.",
                     "entered_by": "tracker-claude (Tracker Build) from the CFO register 2026-09-30"})
    out = [record_filing(r, apply=apply, db_path=db_path) for r in rows]
    return {"apply": apply, "rows": len(out),
            "errors": [o for o in out if o.get("error")],
            "periods": [o["row"]["period"] for o in out if not o.get("error")]}
