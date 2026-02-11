"""SQLite storage layer for parsed transactions."""

import json
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "transactions.db"


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = str(db_path or DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    """Create the transactions table if it doesn't exist."""
    conn = get_connection(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email_uid   TEXT UNIQUE,
            merchant    TEXT NOT NULL,
            amount      TEXT NOT NULL,
            date        TEXT NOT NULL,
            subject     TEXT,
            from_addr   TEXT,
            items       TEXT,
            order_id    TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_transactions_date
        ON transactions(date DESC)
        """
    )
    conn.commit()
    conn.close()
    logger.info("Database initialized at %s", db_path or DB_PATH)


def save_transactions(transactions: list[dict], db_path: str | Path | None = None) -> int:
    """
    Insert transactions into the database, skipping duplicates (by email_uid).
    Returns the number of newly inserted rows.
    """
    conn = get_connection(db_path)
    inserted = 0
    for txn in transactions:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO transactions
                    (email_uid, merchant, amount, date, subject, from_addr, items, order_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    txn.get("email_uid", ""),
                    txn["merchant"],
                    txn["amount"],
                    txn["date"],
                    txn.get("subject", ""),
                    txn.get("from", ""),
                    json.dumps(txn.get("items", [])),
                    txn.get("order_id"),
                ),
            )
            if conn.total_changes:
                inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    logger.info("Saved %d new transactions (%d total provided)", inserted, len(transactions))
    return inserted


def get_all_transactions(db_path: str | Path | None = None) -> list[dict]:
    """Return all transactions ordered by date descending."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY date DESC"
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        d = dict(row)
        try:
            d["items"] = json.loads(d.get("items") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["items"] = []
        results.append(d)
    return results


def get_transaction_stats(db_path: str | Path | None = None) -> dict:
    """Return summary statistics about stored transactions."""
    conn = get_connection(db_path)
    row = conn.execute(
        """
        SELECT
            COUNT(*) as total_count,
            MIN(date) as earliest,
            MAX(date) as latest
        FROM transactions
        """
    ).fetchone()

    # Sum amounts (strip $ and commas)
    amount_rows = conn.execute("SELECT amount FROM transactions").fetchall()
    conn.close()

    total_spent = 0.0
    for r in amount_rows:
        try:
            val = r["amount"].replace("$", "").replace(",", "")
            total_spent += float(val)
        except (ValueError, AttributeError):
            pass

    return {
        "total_count": row["total_count"],
        "total_spent": f"${total_spent:,.2f}",
        "earliest_date": row["earliest"] or "N/A",
        "latest_date": row["latest"] or "N/A",
    }


def delete_transaction(txn_id: int, db_path: str | Path | None = None) -> bool:
    """Delete a transaction by ID. Returns True if a row was deleted."""
    conn = get_connection(db_path)
    cursor = conn.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0
