"""One-shot reconciliation drift fix for April 2026.

Same logic as scripts/fix_recon_drift_2026_04.py, but returns a structured
dict instead of printing to stdout — so it can be invoked from a Flask
route and rendered as JSON.

Each step (each UPDATE, each lookup, each module call) runs in its own
try/except. A failure in one step is recorded in result["step_errors"]
and execution continues with the next step. Each fix opens its own DB
connection and commits independently — earlier fixes are not rolled
back if a later fix raises.

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
TGF_ENTITY_NAME = "TGF"  # short_name on the seeded "The Golf Fellowship" entity
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


def _run_update(result: dict, step: str, sql: str) -> None:
    """Execute one UPDATE in its own connection/transaction.

    Records the SQL and rowcount on success, or the exception message on
    failure, in result["fixes"] / result["step_errors"]. Never raises.
    """
    try:
        with _connect() as conn:
            rc = conn.execute(sql).rowcount
            conn.commit()
        result["fixes"].append({"step": step, "sql": sql, "rowcount": rc})
    except Exception as e:  # noqa: BLE001
        result["fixes"].append(
            {"step": step, "sql": sql, "rowcount": None, "error": str(e)}
        )
        result["step_errors"].append({"step": step, "error": str(e)})


def apply_recon_drift_fix() -> dict:
    """Run the entire April-2026 drift remediation.

    Returns a JSON-ready dict with before/after snapshots, every SQL
    statement and rowcount, both auto-match results, and the
    create_entry_from_deposit return value. Per-step errors do not abort
    the run — they are captured in result["step_errors"].
    """
    result: dict = {
        "before": None,
        "fixes": [],
        "step_errors": [],
        "backfill_diagnostic": [],
        "after": None,
        "auto_match_1": None,
        "matched_to_2742": None,
        "orphan_canyon_springs_deposit_id": None,
        "create_entry": None,
        "auto_match_2": None,
    }

    # Snapshot BEFORE
    try:
        with _connect() as conn:
            result["before"] = _snapshot(conn)
    except Exception as e:  # noqa: BLE001
        result["step_errors"].append({"step": "snapshot_before", "error": str(e)})

    # Fix 1a — void duplicate Municipal Golf row 2740
    _run_update(
        result, "1a",
        "UPDATE acct_transactions SET status = 'merged' "
        "WHERE id = 2740 AND status = 'active'",
    )

    # Fix 1b — re-point expense_transactions FK
    _run_update(
        result, "1b",
        "UPDATE expense_transactions SET acct_transaction_id = 3037 "
        "WHERE id = 279 AND acct_transaction_id = 2740",
    )

    # Fix 2 — restore null fields on Canyon Springs row 2742
    _run_update(
        result, "2",
        "UPDATE acct_transactions "
        "SET entry_type = 'expense', amount = 600.00, source = 'receipt' "
        "WHERE id = 2742 AND entry_type IS NULL AND amount IS NULL",
    )

    # Backfill diagnostic — how do candidate rows' `type` values break down?
    try:
        with _connect() as conn:
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
    except Exception as e:  # noqa: BLE001
        result["step_errors"].append(
            {"step": "backfill_diagnostic", "error": str(e)}
        )

    # Fix 7 — wide backfill
    _run_update(
        result, "7",
        "UPDATE acct_transactions "
        "SET entry_type = type, amount = total_amount "
        "WHERE source_ref LIKE 'exp-promoted-%' "
        "  AND entry_type IS NULL "
        "  AND total_amount IS NOT NULL "
        "  AND COALESCE(status, 'active') != 'merged'",
    )

    # Snapshot AFTER fixes 1, 2, 7
    try:
        with _connect() as conn:
            result["after"] = _snapshot(conn)
    except Exception as e:  # noqa: BLE001
        result["step_errors"].append({"step": "snapshot_after", "error": str(e)})

    # First auto-match — claims one Canyon Springs deposit for 2742, plus
    # whatever else the backfill made visible.
    try:
        am1 = run_deposit_auto_match(account_id=TGF_CHECKING_ACCOUNT_ID)
        result["auto_match_1"] = {
            "auto_matched": am1.get("auto_matched"),
            "partial": am1.get("partial"),
            "unmatched": am1.get("unmatched"),
            "details": am1.get("details", []),
        }
    except Exception as e:  # noqa: BLE001
        result["step_errors"].append({"step": "auto_match_1", "error": str(e)})

    # Identify which of bank_deposits 760/761 was claimed by acct_transaction 2742.
    matched_to_2742: int | None = None
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT bank_deposit_id FROM reconciliation_matches "
                "WHERE acct_transaction_id = 2742 LIMIT 1"
            ).fetchone()
        if row:
            matched_to_2742 = row["bank_deposit_id"]
    except Exception as e:  # noqa: BLE001
        result["step_errors"].append(
            {"step": "lookup_matched_to_2742", "error": str(e)}
        )
    result["matched_to_2742"] = matched_to_2742

    # The orphan Canyon Springs deposit — the one 2742 did not claim.
    candidates = {760, 761}
    if matched_to_2742 in candidates:
        orphan_id = (candidates - {matched_to_2742}).pop()
    else:
        orphan_id = min(candidates)
    result["orphan_canyon_springs_deposit_id"] = orphan_id

    # Fix 4 — create ledger entry for the orphan deposit. entity_name="TGF"
    # resolves via short_name lookup on the seeded "The Golf Fellowship"
    # entity. create_entry_from_deposit also has a default-entity fallback
    # since acct_splits.entity_id is NOT NULL.
    try:
        result["create_entry"] = create_entry_from_deposit(
            deposit_id=orphan_id,
            txn_type="expense",
            entry_type="expense",
            entity_name=TGF_ENTITY_NAME,
            category_name="Course Fees",
            description="Canyon Springs course fee — April 2026",
            event_name="s9.7 CANYON SPRINGS",
        )
    except Exception as e:  # noqa: BLE001
        result["create_entry"] = {"error": str(e)}
        result["step_errors"].append({"step": "create_entry", "error": str(e)})

    # Final auto-match — should reconcile the new entry plus anything
    # else now visible after the backfill.
    try:
        am2 = run_deposit_auto_match(account_id=TGF_CHECKING_ACCOUNT_ID)
        result["auto_match_2"] = {
            "auto_matched": am2.get("auto_matched"),
            "partial": am2.get("partial"),
            "unmatched": am2.get("unmatched"),
            "details": am2.get("details", []),
        }
    except Exception as e:  # noqa: BLE001
        result["step_errors"].append({"step": "auto_match_2", "error": str(e)})

    return result
