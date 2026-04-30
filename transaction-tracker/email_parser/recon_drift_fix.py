"""One-shot reconciliation drift fix for April 2026.

Same logic as scripts/fix_recon_drift_2026_04.py, but returns a structured
dict instead of printing to stdout — so it can be invoked from a Flask
route and rendered as JSON.

All UPDATEs are idempotent (predicate-guarded). create_entry_from_deposit
short-circuits on existing source_ref. run_deposit_auto_match uses
INSERT OR IGNORE on reconciliation_matches.
"""
from __future__ import annotations

from .database import (
    _connect,
    create_entry_from_deposit,
    run_deposit_auto_match,
)

TGF_CHECKING_ACCOUNT_ID = 3
ACCT_TXN_COLS = [
    "id", "status", "entry_type", "type", "amount", "total_amount",
    "date", "description", "source", "source_ref",
]
EXP_TXN_COLS = [
    "id", "merchant", "amount", "review_status", "acct_transaction_id",
]
BANK_DEP_COLS = [
    "id", "deposit_date", "amount", "status", "description",
]


def _row(conn, table: str, row_id: int, cols: list[str]) -> dict | None:
    select_clause = ", ".join(cols)
    row = conn.execute(
        f"SELECT {select_clause} FROM {table} WHERE id = ?", (row_id,),
    ).fetchone()
    return dict(row) if row else None


def _snapshot(conn) -> dict:
    return {
        "acct_transactions": {
            tid: _row(conn, "acct_transactions", tid, ACCT_TXN_COLS)
            for tid in (2740, 2742, 3037)
        },
        "expense_transactions": {
            eid: _row(conn, "expense_transactions", eid, EXP_TXN_COLS)
            for eid in (279, 289, 317)
        },
        "bank_deposits": {
            did: _row(conn, "bank_deposits", did, BANK_DEP_COLS)
            for did in (760, 761, 855)
        },
    }


def apply_recon_drift_fix() -> dict:
    """Run the entire April-2026 drift remediation.

    Returns a JSON-ready dict with before/after snapshots, every SQL
    statement and rowcount, both auto-match results, and the
    create_entry_from_deposit return value.
    """
    result: dict = {
        "before": None,
        "fixes": [],
        "backfill_diagnostic": [],
        "after": None,
        "auto_match_1": None,
        "matched_to_2742": None,
        "orphan_canyon_springs_deposit_id": None,
        "create_entry": None,
        "auto_match_2": None,
    }

    with _connect() as conn:
        result["before"] = _snapshot(conn)

        # Fix 1a — void duplicate Municipal Golf row 2740
        sql_1a = (
            "UPDATE acct_transactions SET status = 'merged' "
            "WHERE id = 2740 AND status = 'active'"
        )
        rc_1a = conn.execute(sql_1a).rowcount
        result["fixes"].append({"step": "1a", "sql": sql_1a, "rowcount": rc_1a})

        # Fix 1b — re-point expense_transactions FK
        sql_1b = (
            "UPDATE expense_transactions SET acct_transaction_id = 3037 "
            "WHERE id = 279 AND acct_transaction_id = 2740"
        )
        rc_1b = conn.execute(sql_1b).rowcount
        result["fixes"].append({"step": "1b", "sql": sql_1b, "rowcount": rc_1b})

        # Fix 2 — restore null fields on Canyon Springs row 2742
        sql_2 = (
            "UPDATE acct_transactions "
            "SET entry_type = 'expense', amount = 600.00, source = 'receipt' "
            "WHERE id = 2742 AND entry_type IS NULL AND amount IS NULL"
        )
        rc_2 = conn.execute(sql_2).rowcount
        result["fixes"].append({"step": "2", "sql": sql_2, "rowcount": rc_2})

        # Fix 7 — wide backfill of entry_type/amount on every promoted row.
        # Diagnostic: how do their `type` values break down?
        diag_rows = conn.execute(
            "SELECT type, COUNT(*) AS n FROM acct_transactions "
            "WHERE source_ref LIKE 'exp-promoted-%' "
            "  AND entry_type IS NULL "
            "  AND total_amount IS NOT NULL "
            "  AND COALESCE(status, 'active') != 'merged' "
            "GROUP BY type"
        ).fetchall()
        result["backfill_diagnostic"] = [
            {"type": r["type"], "count": r["n"]} for r in diag_rows
        ]

        sql_7 = (
            "UPDATE acct_transactions "
            "SET entry_type = type, amount = total_amount "
            "WHERE source_ref LIKE 'exp-promoted-%' "
            "  AND entry_type IS NULL "
            "  AND total_amount IS NOT NULL "
            "  AND COALESCE(status, 'active') != 'merged'"
        )
        rc_7 = conn.execute(sql_7).rowcount
        result["fixes"].append({"step": "7", "sql": sql_7, "rowcount": rc_7})

        conn.commit()
        result["after"] = _snapshot(conn)

    # First auto-match — claims one Canyon Springs deposit for 2742, plus
    # whatever else the backfill made visible.
    am1 = run_deposit_auto_match(account_id=TGF_CHECKING_ACCOUNT_ID)
    result["auto_match_1"] = {
        "auto_matched": am1.get("auto_matched"),
        "partial": am1.get("partial"),
        "unmatched": am1.get("unmatched"),
        "details": am1.get("details", []),
    }

    # Identify which of bank_deposits 760/761 was claimed by acct_transaction 2742.
    matched_to_2742: int | None = None
    with _connect() as conn:
        row = conn.execute(
            "SELECT bank_deposit_id FROM reconciliation_matches "
            "WHERE acct_transaction_id = 2742 LIMIT 1"
        ).fetchone()
    if row:
        matched_to_2742 = row["bank_deposit_id"]
    result["matched_to_2742"] = matched_to_2742

    # The orphan Canyon Springs deposit — the one 2742 did not claim.
    candidates = {760, 761}
    if matched_to_2742 in candidates:
        orphan_id = (candidates - {matched_to_2742}).pop()
    else:
        orphan_id = min(candidates)
    result["orphan_canyon_springs_deposit_id"] = orphan_id

    # Fix 4 — create ledger entry for the orphan deposit (idempotent on
    # source_ref = "bank-deposit-{id}").
    create_result = create_entry_from_deposit(
        deposit_id=orphan_id,
        txn_type="expense",
        entry_type="expense",
        category_name="Course Fees",
        description="Canyon Springs course fee — April 2026",
        event_name="s9.7 CANYON SPRINGS",
    )
    result["create_entry"] = create_result

    # Final auto-match — should reconcile the new entry plus anything
    # else now visible after the backfill.
    am2 = run_deposit_auto_match(account_id=TGF_CHECKING_ACCOUNT_ID)
    result["auto_match_2"] = {
        "auto_matched": am2.get("auto_matched"),
        "partial": am2.get("partial"),
        "unmatched": am2.get("unmatched"),
        "details": am2.get("details", []),
    }

    return result
