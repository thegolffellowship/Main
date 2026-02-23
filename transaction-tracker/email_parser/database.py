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

    # Events table — canonical event list, auto-populated from items
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name   TEXT NOT NULL UNIQUE,
            event_date  TEXT,
            course      TEXT,
            city        TEXT,
            event_type  TEXT DEFAULT 'event',
            created_at  TEXT DEFAULT (datetime('now'))
        )
        """
    )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_order_date ON items(order_date DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_item_name ON items(item_name)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_customer ON items(customer)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_event_date ON events(event_date DESC)"
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


def get_known_email_uids(db_path: str | Path | None = None) -> set[str]:
    """Return the set of email_uid values already stored in the database."""
    conn = get_connection(db_path)
    rows = conn.execute("SELECT DISTINCT email_uid FROM items").fetchall()
    conn.close()
    return {r["email_uid"] for r in rows}


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


def autofix_side_games(db_path: str | Path | None = None) -> dict:
    """
    Scan all rows and fix side_games / golf_or_compete misplacement.

    Returns a summary: { "scanned": N, "fixed": N, "details": [...] }
    """
    from email_parser.parser import _fixup_side_games_field

    conn = get_connection(db_path)
    rows = conn.execute("SELECT id, golf_or_compete, side_games FROM items").fetchall()

    fixed = 0
    details = []
    for row in rows:
        item = dict(row)
        original_goc = item.get("golf_or_compete") or ""
        original_sg = item.get("side_games") or ""

        result = _fixup_side_games_field({
            "golf_or_compete": original_goc,
            "side_games": original_sg,
        })

        new_goc = result.get("golf_or_compete") or ""
        new_sg = result.get("side_games") or ""

        if new_goc != original_goc or new_sg != original_sg:
            conn.execute(
                "UPDATE items SET golf_or_compete = ?, side_games = ? WHERE id = ?",
                (new_goc, new_sg, item["id"]),
            )
            fixed += 1
            details.append({
                "id": item["id"],
                "old_golf_or_compete": original_goc,
                "new_golf_or_compete": new_goc,
                "old_side_games": original_sg,
                "new_side_games": new_sg,
            })

    conn.commit()
    conn.close()
    logger.info("Autofix: scanned %d rows, fixed %d", len(rows), fixed)
    return {"scanned": len(rows), "fixed": fixed, "details": details}


def autofix_all(db_path: str | Path | None = None) -> dict:
    """
    Run all autofix passes on existing data:
      1. side_games / golf_or_compete misplacement
      2. customer name → Title Case
      3. course name → canonical spelling
      4. item_name normalisation (e.g. membership variants)

    Returns a combined summary.
    """
    from email_parser.parser import (
        _fixup_side_games_field,
        _normalize_customer_name,
        _normalize_course_name,
        _normalize_item_name,
    )

    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT id, item_name, customer, course, golf_or_compete, side_games FROM items"
    ).fetchall()

    fixes = {"side_games": 0, "customer_name": 0, "course_name": 0, "item_name": 0}
    details = []

    for row in rows:
        item = dict(row)
        row_id = item["id"]
        updates = {}

        # --- Side games fix ---
        original_goc = item.get("golf_or_compete") or ""
        original_sg = item.get("side_games") or ""
        result = _fixup_side_games_field({
            "golf_or_compete": original_goc,
            "side_games": original_sg,
        })
        new_goc = result.get("golf_or_compete") or ""
        new_sg = result.get("side_games") or ""
        if new_goc != original_goc or new_sg != original_sg:
            updates["golf_or_compete"] = new_goc
            updates["side_games"] = new_sg
            fixes["side_games"] += 1

        # --- Customer name fix ---
        original_name = item.get("customer") or ""
        new_name = _normalize_customer_name(original_name) or ""
        if new_name and new_name != original_name:
            updates["customer"] = new_name
            fixes["customer_name"] += 1

        # --- Course name fix ---
        original_course = item.get("course") or ""
        new_course = _normalize_course_name(original_course) or ""
        if new_course and new_course != original_course:
            updates["course"] = new_course
            fixes["course_name"] += 1

        # --- Item name fix (memberships etc.) ---
        original_item = item.get("item_name") or ""
        new_item = _normalize_item_name(original_item) or ""
        if new_item and new_item != original_item:
            updates["item_name"] = new_item
            fixes["item_name"] += 1

        # Apply all updates for this row in one statement
        if updates:
            set_clause = ", ".join(f"{col} = ?" for col in updates)
            values = list(updates.values()) + [row_id]
            conn.execute(f"UPDATE items SET {set_clause} WHERE id = ?", values)
            details.append({"id": row_id, "changes": updates})

    conn.commit()
    conn.close()

    total_fixed = len(details)
    logger.info(
        "Autofix all: scanned %d rows, %d rows changed "
        "(side_games=%d, customer_name=%d, course_name=%d, item_name=%d)",
        len(rows), total_fixed,
        fixes["side_games"], fixes["customer_name"], fixes["course_name"],
        fixes["item_name"],
    )
    return {
        "scanned": len(rows),
        "fixed": total_fixed,
        "breakdown": fixes,
        "details": details,
    }


# ---------------------------------------------------------------------------
# Events table
# ---------------------------------------------------------------------------

# Keywords that indicate an item is NOT an event (membership, merch, etc.)
_NON_EVENT_KEYWORDS = [
    "member", "membership", "shirt", "merch", "hat", "polo",
    "donation", "gift card", "season pass",
]


def _is_event_item(item_name: str) -> bool:
    """Heuristic: an item is an event if it has a date-like pattern or course name."""
    if not item_name:
        return False
    lower = item_name.lower()
    # Exclude memberships, merch, etc.
    for kw in _NON_EVENT_KEYWORDS:
        if kw in lower:
            return False
    # Contains a month name or date pattern → likely an event
    import re
    month_pattern = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b"
    if re.search(month_pattern, lower):
        return True
    # Contains a known course name keyword → likely an event
    course_keywords = [
        "cantera", "morris", "cedar", "cowboys", "wolfdancer", "falconhead",
        "moody", "quarry", "tpc", "kissing", "plum", "landa", "vaaler",
        "hancock", "craig ranch",
    ]
    for ck in course_keywords:
        if ck in lower:
            return True
    return False


def sync_events_from_items(db_path: str | Path | None = None) -> dict:
    """
    Scan items table and insert any new events into the events table.

    An 'event' is determined heuristically: items with date-like names or
    course references are events; memberships and merchandise are not.
    """
    conn = get_connection(db_path)
    items = conn.execute(
        "SELECT DISTINCT item_name, event_date, course, city FROM items"
    ).fetchall()

    inserted = 0
    skipped_non_event = 0
    for item in items:
        name = item["item_name"] or ""
        if not _is_event_item(name):
            skipped_non_event += 1
            continue
        try:
            conn.execute(
                """INSERT OR IGNORE INTO events (item_name, event_date, course, city, event_type)
                   VALUES (?, ?, ?, ?, 'event')""",
                (name, item["event_date"], item["course"], item["city"]),
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    logger.info("Events sync: %d new events, %d non-event items skipped", inserted, skipped_non_event)
    return {"inserted": inserted, "skipped_non_event": skipped_non_event, "total_items_scanned": len(items)}


def get_all_events(db_path: str | Path | None = None) -> list[dict]:
    """Return all events with registration counts."""
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT e.*, COUNT(i.id) as registrations
        FROM events e
        LEFT JOIN items i ON i.item_name = e.item_name
        GROUP BY e.id
        ORDER BY e.event_date DESC, e.id DESC
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_event(event_id: int, fields: dict, db_path: str | Path | None = None) -> bool:
    """Update specific fields on an event row."""
    allowed = {"item_name", "event_date", "course", "city", "event_type"}
    safe = {k: v for k, v in fields.items() if k in allowed}
    if not safe:
        return False
    set_clause = ", ".join(f"{col} = ?" for col in safe)
    values = list(safe.values()) + [event_id]
    conn = get_connection(db_path)
    cursor = conn.execute(f"UPDATE events SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def delete_event(event_id: int, db_path: str | Path | None = None) -> bool:
    """Delete an event by ID."""
    conn = get_connection(db_path)
    cursor = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def update_item(item_id: int, fields: dict, db_path: str | Path | None = None) -> bool:
    """
    Update specific fields on an item row.

    Only columns in ITEM_COLUMNS are allowed (prevents SQL injection via column names).
    Returns True if a row was updated.
    """
    # Whitelist: only allow known columns
    safe_fields = {k: v for k, v in fields.items() if k in ITEM_COLUMNS}
    if not safe_fields:
        return False

    set_clause = ", ".join(f"{col} = ?" for col in safe_fields)
    values = list(safe_fields.values()) + [item_id]

    conn = get_connection(db_path)
    cursor = conn.execute(f"UPDATE items SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def delete_item(item_id: int, db_path: str | Path | None = None) -> bool:
    """Delete an item row by ID.  Returns True if a row was deleted."""
    conn = get_connection(db_path)
    cursor = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0
