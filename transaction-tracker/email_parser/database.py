"""
SQLite storage layer for parsed transactions.

Each row represents a single line item.  One email with 3 items becomes 3 rows.
Dedicated columns for Golf Fellowship fields (city, handicap, side_games, etc.)
so they can be filtered and sorted directly from the dashboard.
"""

import json
import os
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Allow overriding via env var so Railway can point to a persistent volume.
_default_db = Path(__file__).resolve().parent.parent / "transactions.db"
DB_PATH = Path(os.environ.get("DATABASE_PATH", str(_default_db)))

# All item-level columns (order matches the CREATE TABLE below)
ITEM_COLUMNS = [
    "email_uid", "item_index", "merchant", "customer",
    "customer_email", "customer_phone",
    "order_id", "order_date", "total_amount",
    "item_name", "event_date", "item_price", "quantity",
    "city", "course", "handicap", "side_games", "tee_choice",
    "member_status", "golf_or_compete", "post_game", "returning_or_new",
    "shirt_size", "guest_name", "date_of_birth",
    "net_points_race", "gross_points_race", "city_match_play",
    "subject", "from_addr",
]


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = str(db_path or DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    """Create the items table if it doesn't exist."""
    conn = get_connection(db_path)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            email_uid        TEXT NOT NULL,
            item_index       INTEGER NOT NULL DEFAULT 0,
            merchant         TEXT NOT NULL,
            customer         TEXT,
            customer_email   TEXT,
            customer_phone   TEXT,
            order_id         TEXT,
            order_date       TEXT NOT NULL,
            total_amount     TEXT,
            item_name        TEXT NOT NULL,
            event_date       TEXT,
            item_price       TEXT,
            quantity         INTEGER DEFAULT 1,
            city             TEXT,
            course           TEXT,
            handicap         TEXT,
            side_games       TEXT,
            tee_choice       TEXT,
            member_status    TEXT,
            golf_or_compete  TEXT,
            post_game        TEXT,
            returning_or_new TEXT,
            shirt_size       TEXT,
            guest_name       TEXT,
            date_of_birth    TEXT,
            net_points_race  TEXT,
            gross_points_race TEXT,
            city_match_play  TEXT,
            subject          TEXT,
            from_addr        TEXT,
            created_at       TEXT DEFAULT (datetime('now')),
            UNIQUE(email_uid, item_index)
        )
        """
    )

    # Migrate: add columns that may not exist in older databases
    for col, col_type in [
        ("customer_email", "TEXT"),
        ("customer_phone", "TEXT"),
        ("event_date", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE items ADD COLUMN {col} {col_type}")
            logger.info("Added new column: %s", col)
        except sqlite3.OperationalError:
            pass  # column already exists

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_order_date ON items(order_date DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_item_name ON items(item_name)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_customer ON items(customer)"
    )

    conn.commit()
    conn.close()
    logger.info("Database initialized at %s", db_path or DB_PATH)


def save_items(rows: list[dict], db_path: str | Path | None = None) -> int:
    """
    Insert item rows into the database, skipping duplicates
    (by email_uid + item_index).  Returns the number of newly inserted rows.
    """
    conn = get_connection(db_path)
    placeholders = ", ".join(["?"] * len(ITEM_COLUMNS))
    col_names = ", ".join(ITEM_COLUMNS)
    sql = f"INSERT OR IGNORE INTO items ({col_names}) VALUES ({placeholders})"

    inserted = 0
    for row in rows:
        values = tuple(row.get(col) for col in ITEM_COLUMNS)
        try:
            cursor = conn.execute(sql, values)
            if cursor.rowcount > 0:
                inserted += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    logger.info("Saved %d new item rows (%d total provided)", inserted, len(rows))
    return inserted


def get_all_items(db_path: str | Path | None = None) -> list[dict]:
    """Return all item rows ordered by order_date descending."""
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM items ORDER BY order_date DESC, id ASC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_item_stats(db_path: str | Path | None = None) -> dict:
    """Return summary statistics about stored items."""
    conn = get_connection(db_path)

    row = conn.execute(
        """
        SELECT
            COUNT(*)                 AS total_items,
            COUNT(DISTINCT order_id) AS total_orders,
            MIN(order_date)          AS earliest,
            MAX(order_date)          AS latest
        FROM items
        """
    ).fetchone()

    # Sum item prices (strip $ and commas)
    price_rows = conn.execute("SELECT item_price FROM items").fetchall()
    conn.close()

    total_spent = 0.0
    for r in price_rows:
        try:
            val = (r["item_price"] or "").replace("$", "").replace(",", "")
            total_spent += float(val)
        except (ValueError, AttributeError):
            pass

    return {
        "total_items": row["total_items"],
        "total_orders": row["total_orders"],
        "total_spent": f"${total_spent:,.2f}",
        "earliest_date": row["earliest"] or "N/A",
        "latest_date": row["latest"] or "N/A",
    }


def get_audit_report(db_path: str | Path | None = None) -> dict:
    """
    Analyse extraction quality across all stored items.

    Returns field fill-rates, rows with critical missing data,
    and per-field value distributions for key columns.
    """
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM items ORDER BY order_date DESC, id ASC").fetchall()
    conn.close()

    if not rows:
        return {"total_items": 0, "message": "No items in database."}

    items = [dict(r) for r in rows]
    total = len(items)

    # --- Field fill rates ---------------------------------------------------
    critical_fields = [
        "customer", "customer_email", "order_id", "order_date",
        "item_name", "item_price", "event_date", "city", "course",
    ]
    golf_fields = [
        "handicap", "side_games", "tee_choice", "member_status",
        "golf_or_compete", "post_game", "returning_or_new",
        "shirt_size", "guest_name",
    ]
    all_tracked = critical_fields + golf_fields

    fill_rates = {}
    for field in all_tracked:
        filled = sum(1 for it in items if it.get(field))
        fill_rates[field] = {
            "filled": filled,
            "empty": total - filled,
            "pct": round(filled / total * 100, 1),
        }

    # --- Rows missing critical fields ----------------------------------------
    problems = []
    for it in items:
        missing = [f for f in critical_fields if not it.get(f)]
        if missing:
            problems.append({
                "id": it["id"],
                "email_uid": it.get("email_uid"),
                "customer": it.get("customer") or "(empty)",
                "item_name": it.get("item_name") or "(empty)",
                "missing_fields": missing,
            })

    # --- Value distributions for key columns ---------------------------------
    distributions = {}
    for field in ["city", "course", "member_status", "golf_or_compete", "tee_choice"]:
        counts: dict[str, int] = {}
        for it in items:
            val = it.get(field) or "(empty)"
            counts[val] = counts.get(val, 0) + 1
        distributions[field] = dict(sorted(counts.items(), key=lambda x: -x[1]))

    return {
        "total_items": total,
        "fill_rates": fill_rates,
        "problems": problems,
        "problem_count": len(problems),
        "distributions": distributions,
    }


def get_data_snapshot(limit: int = 50, db_path: str | Path | None = None) -> dict:
    """
    Quick snapshot of the database: stats + the most recent items (default 50).

    Designed for fast inspection — returns enough context to spot issues
    without dumping the entire table.
    """
    conn = get_connection(db_path)

    # Stats
    row = conn.execute(
        """
        SELECT
            COUNT(*)                 AS total_items,
            COUNT(DISTINCT order_id) AS total_orders,
            COUNT(DISTINCT customer) AS unique_customers,
            MIN(order_date)          AS earliest,
            MAX(order_date)          AS latest
        FROM items
        """
    ).fetchone()

    # Most recent items
    recent = conn.execute(
        "SELECT * FROM items ORDER BY created_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()

    return {
        "stats": dict(row),
        "recent_items": [dict(r) for r in recent],
        "showing": min(limit, len(recent)),
    }


def delete_item(item_id: int, db_path: str | Path | None = None) -> bool:
    """Delete an item row by ID.  Returns True if a row was deleted."""
    conn = get_connection(db_path)
    cursor = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0
