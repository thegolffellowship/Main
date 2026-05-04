"""One-shot reconciliation fixes for April 2026 drift.

Run once on Railway:
    cd transaction-tracker && python scripts/fix_recon_drift_2026_04.py

Idempotent: every UPDATE has a precondition predicate so re-running is a no-op.
create_entry_from_deposit() short-circuits on existing source_ref.
run_deposit_auto_match() uses INSERT OR IGNORE on reconciliation_matches.

Steps:
  1. Void duplicate Municipal Golf row 2740 (re-point expense_transactions 279).
  2. Restore null fields on Canyon Springs row 2742.
  3. (Already applied via code change in same commit) — see promote_expense_to_ledger.
  4. Backfill entry_type/amount on every existing exp-promoted-* row that's still null.
  5. Run auto-match for TGF Checking, identify which Canyon Springs deposit
     was claimed by 2742, and create_entry_from_deposit() for the other one.
  6. Final auto-match pass.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from email_parser.database import (  # noqa: E402
    create_entry_from_deposit,
    run_deposit_auto_match,
)

DB_PATH = os.environ.get("DATABASE_PATH", str(REPO_ROOT / "transactions.db"))
TGF_CHECKING_ACCOUNT_ID = 3


def banner(label: str) -> None:
    print()
    print("=" * 72)
    print(label)
    print("=" * 72)


def dump_row(conn: sqlite3.Connection, table: str, row_id: int,
             cols: list[str]) -> None:
    placeholders = ", ".join(cols)
    row = conn.execute(
        f"SELECT {placeholders} FROM {table} WHERE id = ?", (row_id,)
    ).fetchone()
    if row is None:
        print(f"  {table}.id={row_id}: (not found)")
        return
    parts = [f"{c}={row[c]!r}" for c in cols]
    print(f"  {table}.id={row_id}: " + " | ".join(parts))


def main() -> int:
    print(f"DB: {DB_PATH}")
    if not Path(DB_PATH).exists():
        print(f"ERROR: database not found at {DB_PATH}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # ----------------------------------------------------------------- #
    # Before snapshot
    # ----------------------------------------------------------------- #
    banner("BEFORE — target rows")
    for tid in (2740, 2742, 3037):
        dump_row(conn, "acct_transactions", tid,
                 ["id", "status", "entry_type", "type", "amount", "total_amount",
                  "date", "description", "source", "source_ref"])
    for eid in (279, 289, 317):
        dump_row(conn, "expense_transactions", eid,
                 ["id", "merchant", "amount", "review_status",
                  "acct_transaction_id"])
    for did in (760, 761, 855):
        dump_row(conn, "bank_deposits", did,
                 ["id", "deposit_date", "amount", "status", "description"])

    # ----------------------------------------------------------------- #
    # Fix 1 — void duplicate Municipal Golf row 2740
    # ----------------------------------------------------------------- #
    banner("FIX 1 — void duplicate acct_transaction 2740 + re-point expense 279")
    sql_1a = (
        "UPDATE acct_transactions SET status = 'merged' "
        "WHERE id = 2740 AND status = 'active'"
    )
    print(f"  SQL: {sql_1a}")
    cur = conn.execute(sql_1a)
    print(f"  rowcount: {cur.rowcount}")

    sql_1b = (
        "UPDATE expense_transactions SET acct_transaction_id = 3037 "
        "WHERE id = 279 AND acct_transaction_id = 2740"
    )
    print(f"  SQL: {sql_1b}")
    cur = conn.execute(sql_1b)
    print(f"  rowcount: {cur.rowcount}")
    conn.commit()

    # ----------------------------------------------------------------- #
    # Fix 2 — restore null fields on Canyon Springs row 2742
    # ----------------------------------------------------------------- #
    banner("FIX 2 — restore null fields on acct_transaction 2742")
    sql_2 = (
        "UPDATE acct_transactions "
        "SET entry_type = 'expense', amount = 600.00, source = 'receipt' "
        "WHERE id = 2742 AND entry_type IS NULL AND amount IS NULL"
    )
    print(f"  SQL: {sql_2}")
    cur = conn.execute(sql_2)
    print(f"  rowcount: {cur.rowcount}")
    conn.commit()

    # ----------------------------------------------------------------- #
    # Fix 7 — backfill entry_type/amount on every promoted row
    # (Step 6 — the upstream code fix in promote_expense_to_ledger —
    # was applied to email_parser/database.py in this same commit.)
    # ----------------------------------------------------------------- #
    banner("FIX 7 — backfill entry_type/amount on existing exp-promoted-* rows")
    # Diagnostic: how do their `type` values break down? If any row's
    # `type` is not 'expense', the literal user spec would mis-classify it,
    # so we copy from `type` instead of hardcoding 'expense'.
    diag = conn.execute(
        "SELECT type, COUNT(*) AS n FROM acct_transactions "
        "WHERE source_ref LIKE 'exp-promoted-%' "
        "  AND entry_type IS NULL "
        "  AND total_amount IS NOT NULL "
        "  AND COALESCE(status, 'active') != 'merged' "
        "GROUP BY type"
    ).fetchall()
    print("  Candidate breakdown by `type`:")
    for r in diag:
        print(f"    type={r['type']!r}: {r['n']}")

    sql_7 = (
        "UPDATE acct_transactions "
        "SET entry_type = type, amount = total_amount "
        "WHERE source_ref LIKE 'exp-promoted-%' "
        "  AND entry_type IS NULL "
        "  AND total_amount IS NOT NULL "
        "  AND COALESCE(status, 'active') != 'merged'"
    )
    print(f"  SQL: {sql_7}")
    cur = conn.execute(sql_7)
    print(f"  rowcount: {cur.rowcount}")
    conn.commit()

    # ----------------------------------------------------------------- #
    # After snapshot — confirm targeted rows
    # ----------------------------------------------------------------- #
    banner("AFTER fixes 1, 2, 7 — target rows")
    for tid in (2740, 2742, 3037):
        dump_row(conn, "acct_transactions", tid,
                 ["id", "status", "entry_type", "type", "amount", "total_amount",
                  "date", "description", "source", "source_ref"])

    conn.close()  # release before invoking module functions that re-open

    # ----------------------------------------------------------------- #
    # First auto-match — should claim one of the Canyon Springs deposits
    # for acct_transaction 2742, and clean up any other newly-visible rows.
    # ----------------------------------------------------------------- #
    banner("AUTO-MATCH #1 — TGF Checking (after status/null fixes)")
    result_1 = run_deposit_auto_match(account_id=TGF_CHECKING_ACCOUNT_ID)
    print(f"  auto_matched: {result_1.get('auto_matched')}")
    print(f"  partial:      {result_1.get('partial')}")
    print(f"  unmatched:    {result_1.get('unmatched')}")
    # Find which Canyon Springs deposit got matched to 2742
    matched_to_2742: int | None = None
    for d in result_1.get("details", []):
        if d.get("deposit_id") in (760, 761) and "2742" in (d.get("detail") or ""):
            matched_to_2742 = d["deposit_id"]
            print(f"  acct_transaction 2742 matched to bank_deposit {matched_to_2742}")
            print(f"    detail: {d.get('detail')}")
    if matched_to_2742 is None:
        # Fall back: query reconciliation_matches directly.
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT bank_deposit_id FROM reconciliation_matches "
            "WHERE acct_transaction_id = 2742 LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            matched_to_2742 = row["bank_deposit_id"]
            print(f"  (via reconciliation_matches) 2742 → bank_deposit "
                  f"{matched_to_2742}")

    # ----------------------------------------------------------------- #
    # Fix 4 — create ledger entry for the Canyon Springs deposit that
    # was NOT claimed by 2742.
    # ----------------------------------------------------------------- #
    banner("FIX 4 — create ledger entry for the orphan Canyon Springs deposit")
    candidates = {760, 761}
    if matched_to_2742 in candidates:
        orphan_id = (candidates - {matched_to_2742}).pop()
    else:
        # 2742 didn't claim either — pick the lower id deterministically and
        # let the next auto-match round handle 2742 separately.
        orphan_id = min(candidates)
        print(f"  WARNING: 2742 did not match either 760/761; falling back "
              f"to {orphan_id} as orphan candidate")
    print(f"  orphan deposit_id: {orphan_id}")
    print(f"  idempotency: create_entry_from_deposit checks for existing "
          f"acct_transactions.source_ref = 'bank-deposit-{orphan_id}'")

    create_result = create_entry_from_deposit(
        deposit_id=orphan_id,
        txn_type="expense",
        entry_type="expense",
        category_name="Course Fees",
        description="Canyon Springs course fee — April 2026",
        event_name="s9.7 CANYON SPRINGS",
    )
    print(f"  create_entry_from_deposit result: {create_result}")

    # ----------------------------------------------------------------- #
    # Final auto-match — wide remediation has populated entry_type
    # everywhere, so previously invisible expense rows should now match
    # their bank deposits.
    # ----------------------------------------------------------------- #
    banner("AUTO-MATCH #2 — final pass after backfill (TGF Checking)")
    result_2 = run_deposit_auto_match(account_id=TGF_CHECKING_ACCOUNT_ID)
    print(f"  auto_matched: {result_2.get('auto_matched')}")
    print(f"  partial:      {result_2.get('partial')}")
    print(f"  unmatched:    {result_2.get('unmatched')}")

    banner("DONE")
    print("Re-running this script is safe; every step is idempotent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
