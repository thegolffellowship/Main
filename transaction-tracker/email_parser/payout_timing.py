"""PAID-AT TIMES + HOW LONG PAYING TOOK (Kerry 2026-10-28, Event Ops #2460-D).

Kerry, verbatim: "Can you also timestamp each payment ... there could be a
big gap between a batch and one other or multiple other batches. Looking for
total time taken as a value to track over time".

`tgf_payouts.paid_at` keeps the DATE (every reader slices or compares it as
a date). The TIME of each payment is kept beside it, in Central time, in one
app setting per Payouts-page event: `payout_paid_times:<tgf_event_id>` =
{payout_id: {"at": "YYYY-MM-DD HH:MM", "src": "receipt" | "pressed"}}.
  - receipt: the matcher (`auto_match_venmo_payouts_to_tgf`) stamps the time
    the Venmo / PayPal / Cash App / Zelle receipt email arrived (stored on the
    expense row's raw_extract as `email_received_at`), else the time the row
    was ingested;
  - pressed: Mark Paid (`/api/tgf/mark-paid`) stamps the moment it was pressed
    when the payment is dated today.
The first time recorded for a row is kept.

`payout_timing(event_id)` (events.id) reads it back: first paid, last paid,
the batches (a gap over 30 minutes starts a new one), and the minutes
actually spent paying (sum of batch spans). Read-only bridge
`scoring-payout-timing:<event_id>`. Guard test_payout_timing.py.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

KEY = "payout_paid_times:{tgf_event_id}"
BATCH_GAP_MINUTES = 30
FMT = "%Y-%m-%d %H:%M"


def _fmt(dt: datetime | None) -> str | None:
    return dt.strftime(FMT) if dt else None


def receipt_time(exp: dict) -> str:
    """Central "YYYY-MM-DD HH:MM" for a payment receipt (expense row)."""
    from email_parser.timezone_utils import now_central, to_central
    raw = exp.get("raw_extract")
    try:
        raw = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except (ValueError, TypeError):
        raw = {}
    for v in ((raw or {}).get("email_received_at"), exp.get("created_at")):
        dt = to_central(v) if v else None
        if dt:
            return _fmt(dt)
    return _fmt(now_central())


def pressed_time() -> str:
    from email_parser.timezone_utils import now_central
    return _fmt(now_central())


def _read(conn, tgf_event_id) -> dict:
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?",
                       (KEY.format(tgf_event_id=int(tgf_event_id)),)).fetchone()
    try:
        return json.loads(row[0]) if row and row[0] else {}
    except (ValueError, TypeError):
        return {}


def stamp_conn(conn, tgf_event_id, payout_ids, at: str, src: str) -> int:
    """Record `at` for each payout row not yet stamped, on the caller's
    connection (the matcher holds the write lock; a second connection would
    wait on it). Never raises."""
    try:
        m = _read(conn, tgf_event_id)
        n = 0
        for pid in payout_ids or []:
            if pid is None or str(int(pid)) in m:
                continue
            m[str(int(pid))] = {"at": at, "src": src}
            n += 1
        if n:
            conn.execute(
                "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
                (KEY.format(tgf_event_id=int(tgf_event_id)), json.dumps(m, sort_keys=True)))
        return n
    except Exception:
        logger.exception("payout paid-time stamp failed for tgf_event %s", tgf_event_id)
        return 0


def paid_times(tgf_event_id, db_path=None) -> dict:
    from email_parser import database as db
    with db._connect(db_path) as conn:
        return _read(conn, tgf_event_id)


def batches(times: list[str], gap_minutes: int = BATCH_GAP_MINUTES) -> list[dict]:
    """Group sorted "YYYY-MM-DD HH:MM" times; a gap over `gap_minutes`
    starts a new batch. Each: {start, end, payments, minutes}."""
    ts = sorted(datetime.strptime(t, FMT) for t in times if t)
    out: list[dict] = []
    for t in ts:
        if out and (t - out[-1]["_end"]).total_seconds() <= gap_minutes * 60:
            out[-1]["_end"] = t
            out[-1]["payments"] += 1
        else:
            out.append({"_start": t, "_end": t, "payments": 1})
    return [{"start": _fmt(b["_start"]), "end": _fmt(b["_end"]), "payments": b["payments"],
             "minutes": int((b["_end"] - b["_start"]).total_seconds() // 60)} for b in out]


def payout_timing(event_id: int, db_path=None) -> dict:
    """How long paying one event took (events.id)."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        ev = conn.execute("SELECT id, item_name FROM events WHERE id = ?",
                          (int(event_id),)).fetchone()
        if not ev:
            return {"error": f"no event {event_id}"}
        tids = [r[0] for r in conn.execute(
            "SELECT id FROM tgf_events WHERE events_id = ?", (int(event_id),)).fetchall()]
        rows, times = [], {}
        for tid in tids:
            times.update(_read(conn, tid))
            rows += [dict(r) for r in conn.execute(
                "SELECT p.id, p.customer_id, p.amount, p.paid_at, t.source "
                "FROM tgf_payouts p LEFT JOIN acct_transactions t ON t.id = p.acct_transaction_id "
                "WHERE p.event_id = ?", (tid,)).fetchall()]
    paid = [r for r in rows if r["paid_at"] and (r["source"] or "pending") != "pending"]
    # One payment = one person paid at one moment (a group of rows).
    pay_moments = {}
    untimed = 0
    for r in paid:
        t = (times.get(str(r["id"])) or {}).get("at")
        if not t:
            untimed += 1
            continue
        pay_moments[(r["customer_id"], t)] = t
    bs = batches(list(pay_moments.values()))
    out = {"event_id": int(event_id), "event": ev["item_name"],
           "payout_rows": len(rows), "paid_rows": len(paid), "untimed_paid_rows": untimed,
           "payments": len(pay_moments),
           "first_paid": bs[0]["start"] if bs else None,
           "last_paid": bs[-1]["end"] if bs else None,
           "batch_count": len(bs), "batches": bs,
           "minutes_spent": sum(b["minutes"] for b in bs),
           "batch_gap_minutes": BATCH_GAP_MINUTES, "timezone": "America/Chicago"}
    if bs:
        span = datetime.strptime(bs[-1]["end"], FMT) - datetime.strptime(bs[0]["start"], FMT)
        out["elapsed_minutes"] = int(span.total_seconds() // 60)
    return out
