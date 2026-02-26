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
    "order_id", "order_date", "total_amount", "transaction_fees",
    "item_name", "event_date", "item_price", "quantity",
    "city", "chapter", "course", "handicap", "has_handicap",
    "side_games", "tee_choice",
    "member_status", "post_game", "returning_or_new",
    "shirt_size", "guest_name", "date_of_birth",
    "net_points_race", "gross_points_race", "city_match_play",
    "subject", "from_addr",
    "transaction_status", "credit_note", "transferred_from_id", "transferred_to_id",
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
            transaction_status TEXT DEFAULT 'active',
            credit_note      TEXT,
            transferred_from_id INTEGER,
            transferred_to_id   INTEGER,
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
        ("transaction_status", "TEXT DEFAULT 'active'"),
        ("credit_note", "TEXT"),
        ("transferred_from_id", "INTEGER"),
        ("transferred_to_id", "INTEGER"),
        ("chapter", "TEXT"),
        ("has_handicap", "TEXT"),
        ("transaction_fees", "TEXT"),
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

    # RSVPs table — Golf Genius round signup confirmations
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rsvps (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            email_uid        TEXT NOT NULL UNIQUE,
            player_name      TEXT,
            player_email     TEXT,
            gg_event_name    TEXT,
            event_identifier TEXT,
            event_date       TEXT,
            response         TEXT NOT NULL,
            received_at      TEXT,
            matched_event    TEXT,
            matched_item_id  INTEGER,
            created_at       TEXT DEFAULT (datetime('now'))
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rsvps_matched_event ON rsvps(matched_event)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rsvps_player_email ON rsvps(player_email)"
    )

    # Manual RSVP overrides — tap-to-change circle on event detail
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rsvp_overrides (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id    INTEGER NOT NULL,
            event_name TEXT NOT NULL,
            status     TEXT NOT NULL DEFAULT 'none',
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(item_id, event_name)
        )
        """
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
        "total_spent": f"${total_spent:,.0f}",
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
        "post_game", "returning_or_new",
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
    for field in ["city", "course", "member_status", "tee_choice"]:
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
    Scan all rows and fix side_games misplacement.

    Returns a summary: { "scanned": N, "fixed": N, "details": [...] }
    """
    from email_parser.parser import _fixup_side_games_field

    conn = get_connection(db_path)
    rows = conn.execute("SELECT id, side_games FROM items").fetchall()

    fixed = 0
    details = []
    for row in rows:
        item = dict(row)
        original_sg = item.get("side_games") or ""

        result = _fixup_side_games_field({
            "golf_or_compete": "",
            "side_games": original_sg,
        })

        new_sg = result.get("side_games") or ""

        if new_sg != original_sg:
            conn.execute(
                "UPDATE items SET side_games = ? WHERE id = ?",
                (new_sg, item["id"]),
            )
            fixed += 1
            details.append({
                "id": item["id"],
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
      1. side_games misplacement
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
        _normalize_chapter,
    )

    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT id, item_name, customer, course, chapter, side_games FROM items"
    ).fetchall()

    fixes = {"side_games": 0, "customer_name": 0, "course_name": 0, "item_name": 0, "chapter": 0}
    details = []

    for row in rows:
        item = dict(row)
        row_id = item["id"]
        updates = {}

        # --- Side games fix ---
        original_sg = item.get("side_games") or ""
        result = _fixup_side_games_field({
            "golf_or_compete": "",
            "side_games": original_sg,
        })
        new_sg = result.get("side_games") or ""
        if new_sg != original_sg:
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

        # --- Chapter fix ---
        original_chapter = item.get("chapter") or ""
        new_chapter = _normalize_chapter(original_chapter) or ""
        if new_chapter and new_chapter != original_chapter:
            updates["chapter"] = new_chapter
            fixes["chapter"] += 1

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
        "(side_games=%d, customer_name=%d, course_name=%d, item_name=%d, chapter=%d)",
        len(rows), total_fixed,
        fixes["side_games"], fixes["customer_name"], fixes["course_name"],
        fixes["item_name"], fixes["chapter"],
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
    """Return all events with registration counts (active items only)."""
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT e.*, COUNT(i.id) as registrations
        FROM events e
        LEFT JOIN items i ON i.item_name = e.item_name
            AND COALESCE(i.transaction_status, 'active') = 'active'
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


def get_item(item_id: int, db_path: str | Path | None = None) -> dict | None:
    """Return a single item by ID, or None if not found."""
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def credit_item(item_id: int, note: str = "", db_path: str | Path | None = None) -> bool:
    """Mark an item as credited (money held for future use)."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "UPDATE items SET transaction_status = 'credited', credit_note = ? WHERE id = ? AND COALESCE(transaction_status, 'active') = 'active'",
        (note or "Credit on account", item_id),
    )
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def transfer_item(item_id: int, target_event_name: str, note: str = "", db_path: str | Path | None = None) -> dict | None:
    """
    Transfer an item to a different event.

    Marks the original as 'transferred' and creates a new item
    at the target event with $0 price (credit applied).
    Returns the new item dict or None on failure.
    """
    conn = get_connection(db_path)

    # Fetch the original item
    orig = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not orig:
        conn.close()
        return None
    orig = dict(orig)

    if orig.get("transaction_status") not in (None, "active"):
        conn.close()
        return None  # already credited/transferred

    # Fetch the target event for date/course/city
    target_event = conn.execute(
        "SELECT * FROM events WHERE item_name = ?", (target_event_name,)
    ).fetchone()
    target_event = dict(target_event) if target_event else {}

    # Mark original as transferred
    transfer_note = note or f"Transferred to {target_event_name}"
    conn.execute(
        "UPDATE items SET transaction_status = 'transferred', credit_note = ? WHERE id = ?",
        (transfer_note, item_id),
    )

    # Create new item at target event
    new_values = {col: orig.get(col) for col in ITEM_COLUMNS}
    new_values["item_name"] = target_event_name
    new_values["event_date"] = target_event.get("event_date") or orig.get("event_date")
    new_values["course"] = target_event.get("course") or orig.get("course")
    new_values["city"] = target_event.get("city") or orig.get("city")
    new_values["item_price"] = "$0.00 (credit)"
    new_values["email_uid"] = f"transfer-{item_id}"
    new_values["item_index"] = 0
    new_values["order_date"] = orig.get("order_date") or ""
    new_values["transaction_status"] = "active"
    new_values["credit_note"] = f"Transferred from {orig.get('item_name', '')} (#{item_id})"
    new_values["transferred_from_id"] = str(item_id)
    new_values["transferred_to_id"] = None

    cols = ", ".join(ITEM_COLUMNS)
    placeholders = ", ".join(["?"] * len(ITEM_COLUMNS))
    cursor = conn.execute(
        f"INSERT INTO items ({cols}) VALUES ({placeholders})",
        tuple(new_values.get(c) for c in ITEM_COLUMNS),
    )
    new_id = cursor.lastrowid

    # Link original to the new row
    conn.execute(
        "UPDATE items SET transferred_to_id = ? WHERE id = ?",
        (new_id, item_id),
    )

    conn.commit()
    conn.close()

    new_values["id"] = new_id
    return new_values


def reverse_credit(item_id: int, db_path: str | Path | None = None) -> bool:
    """
    Reverse a credit or transfer.

    For credits: simply resets to active.
    For transfers: resets original to active and deletes the transferred-to item.
    """
    conn = get_connection(db_path)
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        conn.close()
        return False
    item = dict(item)

    status = item.get("transaction_status")
    if status not in ("credited", "transferred"):
        conn.close()
        return False

    if status == "transferred" and item.get("transferred_to_id"):
        # Delete the destination item
        conn.execute("DELETE FROM items WHERE id = ?", (item["transferred_to_id"],))

    # Reset original
    conn.execute(
        "UPDATE items SET transaction_status = 'active', credit_note = NULL, transferred_to_id = NULL WHERE id = ?",
        (item_id,),
    )
    conn.commit()
    conn.close()
    return True


def create_event(item_name: str, event_date: str = None, course: str = None,
                 city: str = None, db_path: str | Path | None = None) -> dict | None:
    """Manually create a new event. Returns the event dict or None if duplicate."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO events (item_name, event_date, course, city, event_type) VALUES (?, ?, ?, ?, 'event')",
            (item_name, event_date, course, city),
        )
        conn.commit()
        new_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM events WHERE id = ?", (new_id,)).fetchone()
        conn.close()
        return dict(row) if row else None
    except sqlite3.IntegrityError:
        conn.close()
        return None


def seed_events(events: list[dict], db_path: str | Path | None = None) -> dict:
    """
    Batch-insert events. Each dict should have: item_name, event_date, course, city.
    Skips duplicates. Returns {"inserted": N, "skipped": N}.
    """
    conn = get_connection(db_path)
    inserted = 0
    skipped = 0
    for ev in events:
        try:
            conn.execute(
                "INSERT INTO events (item_name, event_date, course, city, event_type) VALUES (?, ?, ?, ?, 'event')",
                (ev["item_name"], ev.get("event_date"), ev.get("course"), ev.get("city")),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1
    conn.commit()
    conn.close()
    return {"inserted": inserted, "skipped": skipped}


def add_player_to_event(event_name: str, customer: str, mode: str = "comp",
                        side_games: str = "", tee_choice: str = "",
                        handicap: str = "", member_status: str = "",
                        payment_amount: str = "", payment_source: str = "",
                        customer_email: str = "", customer_phone: str = "",
                        db_path: str | Path | None = None) -> dict | None:
    """
    Add a player to an event.

    Modes:
      - 'comp': Manager comp ($0.00 price, full golf details)
      - 'rsvp': RSVP-only placeholder (name only, no price, no games)
      - 'paid_separately': Paid via Venmo/Zelle/Cash (custom price, full details)

    Returns the new item dict or None on failure.
    """
    import time

    conn = get_connection(db_path)

    # Look up the event for date/course/city
    event = conn.execute(
        "SELECT * FROM events WHERE item_name = ?", (event_name,)
    ).fetchone()
    event = dict(event) if event else {}

    uid = f"manual-{mode}-{int(time.time() * 1000)}"

    new_values = {col: None for col in ITEM_COLUMNS}
    new_values["email_uid"] = uid
    new_values["item_index"] = 0
    new_values["customer"] = customer
    new_values["customer_email"] = customer_email or None
    new_values["customer_phone"] = customer_phone or None
    new_values["item_name"] = event_name
    new_values["order_date"] = __import__("datetime").date.today().isoformat()
    new_values["event_date"] = event.get("event_date") or ""
    new_values["course"] = event.get("course") or ""
    new_values["city"] = event.get("city") or ""
    new_values["transaction_status"] = "active"

    if mode == "comp":
        new_values["merchant"] = "Manual Entry"
        new_values["item_price"] = "$0.00 (comp)"
        new_values["side_games"] = side_games or None
        new_values["tee_choice"] = tee_choice or None
        new_values["handicap"] = handicap or None
        new_values["member_status"] = member_status or None
    elif mode == "rsvp":
        new_values["merchant"] = "RSVP Only"
        new_values["item_price"] = None
        new_values["transaction_status"] = "rsvp_only"
    elif mode == "paid_separately":
        source_label = payment_source or "External"
        new_values["merchant"] = f"Paid Separately ({source_label})"
        new_values["item_price"] = payment_amount or "$0.00"
        new_values["side_games"] = side_games or None
        new_values["tee_choice"] = tee_choice or None
        new_values["handicap"] = handicap or None
        new_values["member_status"] = member_status or None
    else:
        new_values["merchant"] = "Manual Entry"
        new_values["item_price"] = "$0.00"

    cols = ", ".join(ITEM_COLUMNS)
    placeholders = ", ".join(["?"] * len(ITEM_COLUMNS))
    cursor = conn.execute(
        f"INSERT INTO items ({cols}) VALUES ({placeholders})",
        tuple(new_values.get(c) for c in ITEM_COLUMNS),
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    new_values["id"] = new_id
    logger.info("Added player %s to event %s (mode=%s, id=%d)",
                customer, event_name, mode, new_id)
    return new_values


def upgrade_rsvp_to_paid(item_id: int, payment_amount: str = "",
                         payment_source: str = "", side_games: str = "",
                         tee_choice: str = "", handicap: str = "",
                         member_status: str = "",
                         db_path: str | Path | None = None) -> dict | None:
    """
    Upgrade an RSVP-only placeholder to a full paid registration.

    Updates the existing item row with payment and golf details.
    Returns the updated item dict or None on failure.
    """
    conn = get_connection(db_path)

    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        conn.close()
        return None
    item = dict(item)

    if item.get("transaction_status") != "rsvp_only":
        conn.close()
        logger.warning("Item %d is not rsvp_only (status=%s)", item_id,
                       item.get("transaction_status"))
        return None

    source_label = payment_source or "External"
    conn.execute(
        """UPDATE items SET
            merchant = ?,
            item_price = ?,
            side_games = ?,
            tee_choice = ?,
            handicap = ?,
            member_status = ?,
            transaction_status = 'active'
        WHERE id = ?""",
        (
            f"Paid Separately ({source_label})",
            payment_amount or "$0.00",
            side_games or None,
            tee_choice or None,
            handicap or None,
            member_status or None,
            item_id,
        ),
    )
    conn.commit()

    # Re-read the updated row
    updated = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    conn.close()

    if updated:
        updated = dict(updated)
        logger.info("Upgraded RSVP item %d to paid registration", item_id)
        return updated
    return None


def delete_item(item_id: int, db_path: str | Path | None = None) -> bool:
    """Delete an item row by ID.  Returns True if a row was deleted."""
    conn = get_connection(db_path)
    cursor = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def delete_manual_player(item_id: int, db_path: str | Path | None = None) -> bool:
    """Delete a manually added player (email_uid starts with 'manual-').

    Returns True if the row was deleted, False if not found or not manual.
    """
    conn = get_connection(db_path)
    item = conn.execute("SELECT email_uid FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        conn.close()
        return False
    uid = dict(item).get("email_uid") or ""
    if not uid.startswith("manual-"):
        conn.close()
        logger.warning("Refused to delete non-manual item %d (uid=%s)", item_id, uid)
        return False
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    logger.info("Deleted manual player item %d (uid=%s)", item_id, uid)
    return True


# ---------------------------------------------------------------------------
# RSVPs — Golf Genius round signup confirmations
# ---------------------------------------------------------------------------

def get_known_rsvp_uids(db_path: str | Path | None = None) -> set[str]:
    """Return the set of email_uid values already stored in rsvps."""
    conn = get_connection(db_path)
    rows = conn.execute("SELECT DISTINCT email_uid FROM rsvps").fetchall()
    conn.close()
    return {r["email_uid"] for r in rows}


def match_rsvp_to_event(event_identifier: str, event_date: str | None,
                         db_path: str | Path | None = None) -> str | None:
    """Try to match an RSVP event identifier to an events.item_name.

    Strategies:
      1. item_name contains the event_identifier substring
      2. Match by event_date alone (if only one event on that date)
      3. Normalize the identifier as a course name and match course + date
    """
    conn = get_connection(db_path)

    # Strategy 1: Direct substring match
    rows = conn.execute(
        "SELECT item_name FROM events WHERE item_name LIKE ?",
        (f"%{event_identifier}%",),
    ).fetchall()
    if len(rows) == 1:
        conn.close()
        return rows[0]["item_name"]

    # Strategy 2: Match by event_date (if one event on that date)
    if event_date:
        rows = conn.execute(
            "SELECT item_name FROM events WHERE event_date = ?",
            (event_date,),
        ).fetchall()
        if len(rows) == 1:
            conn.close()
            return rows[0]["item_name"]

    # Strategy 3: Normalize as course name and match course + date
    from email_parser.parser import _normalize_course_name
    normalized = _normalize_course_name(event_identifier)
    if normalized and event_date:
        rows = conn.execute(
            "SELECT item_name FROM events WHERE course LIKE ? AND event_date = ?",
            (f"%{normalized}%", event_date),
        ).fetchall()
        if len(rows) == 1:
            conn.close()
            return rows[0]["item_name"]
    elif normalized:
        rows = conn.execute(
            "SELECT item_name FROM events WHERE course LIKE ?",
            (f"%{normalized}%",),
        ).fetchall()
        if len(rows) == 1:
            conn.close()
            return rows[0]["item_name"]

    conn.close()
    return None


def match_rsvp_to_item(player_email: str | None, player_name: str | None,
                        event_name: str, db_path: str | Path | None = None) -> int | None:
    """Try to match an RSVP player to an items row (transaction).

    Strategies:
      1. Match by player email + event name
      2. Match by player first name + event name (only if single match)
    """
    conn = get_connection(db_path)

    # Strategy 1: Email match
    if player_email:
        row = conn.execute(
            """SELECT id FROM items
               WHERE LOWER(customer_email) = LOWER(?)
                 AND item_name = ?
                 AND COALESCE(transaction_status, 'active') = 'active'""",
            (player_email, event_name),
        ).fetchone()
        if row:
            conn.close()
            return row["id"]

    # Strategy 2: First name match (loose — only if one match)
    if player_name:
        rows = conn.execute(
            """SELECT id FROM items
               WHERE customer LIKE ?
                 AND item_name = ?
                 AND COALESCE(transaction_status, 'active') = 'active'""",
            (f"{player_name}%", event_name),
        ).fetchall()
        if len(rows) == 1:
            conn.close()
            return rows[0]["id"]

    conn.close()
    return None


def save_rsvp(rsvp: dict, db_path: str | Path | None = None) -> int | None:
    """
    Save a parsed RSVP to the database.

    Performs event and item matching before insert.
    Returns the rsvp id, or None if it was a duplicate.
    """
    conn = get_connection(db_path)

    # Match event
    matched_event = match_rsvp_to_event(
        rsvp["event_identifier"], rsvp.get("event_date"), db_path,
    )

    # Match transaction
    matched_item_id = None
    if matched_event:
        matched_item_id = match_rsvp_to_item(
            rsvp.get("player_email"), rsvp.get("player_name"),
            matched_event, db_path,
        )

    try:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO rsvps
               (email_uid, player_name, player_email, gg_event_name,
                event_identifier, event_date, response, received_at,
                matched_event, matched_item_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rsvp["email_uid"],
                rsvp.get("player_name"),
                rsvp.get("player_email"),
                rsvp.get("gg_event_name"),
                rsvp.get("event_identifier"),
                rsvp.get("event_date"),
                rsvp["response"],
                rsvp.get("received_at"),
                matched_event,
                matched_item_id,
            ),
        )
        conn.commit()
        if cursor.rowcount > 0:
            rsvp_id = cursor.lastrowid
            conn.close()
            logger.info(
                "Saved RSVP: %s %s for %s (matched_event=%s, matched_item=%s)",
                rsvp.get("player_name"), rsvp["response"],
                rsvp.get("event_identifier"), matched_event, matched_item_id,
            )
            return rsvp_id
    except sqlite3.IntegrityError:
        pass

    conn.close()
    return None


def save_rsvps(rsvps: list[dict], db_path: str | Path | None = None) -> int:
    """Save a batch of parsed RSVPs. Returns count of newly inserted."""
    inserted = 0
    for rsvp in rsvps:
        result = save_rsvp(rsvp, db_path)
        if result is not None:
            inserted += 1
    logger.info("Saved %d new RSVPs (%d total provided)", inserted, len(rsvps))
    return inserted


def get_rsvps_for_event(event_name: str, db_path: str | Path | None = None) -> list[dict]:
    """
    Return the latest RSVP for each player for the given event.

    Groups by player_email and returns only the most recent response.
    """
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT r1.*
           FROM rsvps r1
           INNER JOIN (
               SELECT player_email, MAX(received_at) AS max_date
               FROM rsvps
               WHERE matched_event = ?
                 AND player_email IS NOT NULL AND player_email != ''
               GROUP BY player_email
           ) r2 ON r1.player_email = r2.player_email AND r1.received_at = r2.max_date
           WHERE r1.matched_event = ?
           ORDER BY r1.player_name ASC""",
        (event_name, event_name),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_rsvps(event_name: str = "", response: str = "",
                   db_path: str | Path | None = None) -> list[dict]:
    """Return RSVPs with optional filtering by event and/or response."""
    conn = get_connection(db_path)
    clauses = []
    params = []

    if event_name:
        clauses.append("matched_event LIKE ?")
        params.append(f"%{event_name}%")
    if response:
        clauses.append("response = ?")
        params.append(response.upper())

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM rsvps{where} ORDER BY received_at DESC",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_rsvp_stats(db_path: str | Path | None = None) -> dict:
    """Return summary RSVP statistics."""
    conn = get_connection(db_path)
    total = conn.execute("SELECT COUNT(*) as c FROM rsvps").fetchone()["c"]
    playing = conn.execute(
        "SELECT COUNT(*) as c FROM rsvps WHERE response = 'PLAYING'"
    ).fetchone()["c"]
    not_playing = conn.execute(
        "SELECT COUNT(*) as c FROM rsvps WHERE response = 'NOT PLAYING'"
    ).fetchone()["c"]
    matched = conn.execute(
        "SELECT COUNT(*) as c FROM rsvps WHERE matched_item_id IS NOT NULL"
    ).fetchone()["c"]
    unmatched = conn.execute(
        "SELECT COUNT(*) as c FROM rsvps WHERE matched_event IS NOT NULL AND matched_item_id IS NULL AND response = 'PLAYING'"
    ).fetchone()["c"]
    conn.close()
    return {
        "total_rsvps": total,
        "playing": playing,
        "not_playing": not_playing,
        "matched_to_transaction": matched,
        "playing_no_transaction": unmatched,
    }


def rematch_rsvps(db_path: str | Path | None = None) -> dict:
    """
    Re-run matching logic on all RSVPs that are missing matches.

    Useful after new events or transactions are added.
    Returns {"rematched_events": N, "rematched_items": N}.
    """
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM rsvps WHERE matched_event IS NULL OR matched_item_id IS NULL"
    ).fetchall()

    rematched_events = 0
    rematched_items = 0

    for row in rows:
        rsvp = dict(row)
        updates = {}

        # Re-match event
        if not rsvp.get("matched_event"):
            matched_event = match_rsvp_to_event(
                rsvp["event_identifier"], rsvp.get("event_date"), db_path,
            )
            if matched_event:
                updates["matched_event"] = matched_event
                rematched_events += 1

        event_name = updates.get("matched_event") or rsvp.get("matched_event")

        # Re-match item
        if event_name and not rsvp.get("matched_item_id"):
            matched_item = match_rsvp_to_item(
                rsvp.get("player_email"), rsvp.get("player_name"),
                event_name, db_path,
            )
            if matched_item:
                updates["matched_item_id"] = matched_item
                rematched_items += 1

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [rsvp["id"]]
            conn.execute(f"UPDATE rsvps SET {set_clause} WHERE id = ?", values)

    conn.commit()
    conn.close()
    logger.info("Rematch: %d events, %d items rematched", rematched_events, rematched_items)
    return {"rematched_events": rematched_events, "rematched_items": rematched_items}


def normalize_tee_choices(db_path: str | Path | None = None) -> int:
    """
    One-time migration: standardise all tee_choice values in the DB.
    Standards: <50, 50-64, 65+, Forward.
    Returns the number of rows updated.
    """
    import re

    _TEE_MAP = [
        (re.compile(r"\bforward\b|\bfront\b", re.IGNORECASE), "Forward"),
        (re.compile(r"\b65\s*\+", re.IGNORECASE), "65+"),
        (re.compile(r"\b50\s*[-–]\s*64\b", re.IGNORECASE), "50-64"),
        (re.compile(r"(?:^|(?<=\s))<\s*50\b|\bunder\s*50\b", re.IGNORECASE), "<50"),
    ]
    canonical = {"<50", "50-64", "65+", "Forward"}

    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT id, tee_choice FROM items WHERE tee_choice IS NOT NULL AND tee_choice != ''"
    ).fetchall()

    updated = 0
    for row_id, val in rows:
        cleaned = val.strip()
        if cleaned in canonical:
            continue
        new_val = cleaned
        for pattern, label in _TEE_MAP:
            if pattern.search(cleaned):
                new_val = label
                break
        if new_val != val:
            conn.execute("UPDATE items SET tee_choice = ? WHERE id = ?", (new_val, row_id))
            updated += 1

    conn.commit()
    conn.close()
    return updated


# ---------------------------------------------------------------------------
# Manual RSVP Overrides
# ---------------------------------------------------------------------------

def get_rsvp_overrides(event_name: str, db_path=None) -> dict:
    """Return {item_id: status} for all manual overrides on an event."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT item_id, status FROM rsvp_overrides WHERE event_name = ?",
        (event_name,),
    ).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def set_rsvp_override(item_id: int, event_name: str, status: str, db_path=None):
    """Upsert a manual RSVP override. status is 'none', 'playing', or 'not_playing'."""
    conn = get_connection(db_path)
    if status == "none":
        conn.execute(
            "DELETE FROM rsvp_overrides WHERE item_id = ? AND event_name = ?",
            (item_id, event_name),
        )
    else:
        conn.execute(
            """INSERT INTO rsvp_overrides (item_id, event_name, status)
               VALUES (?, ?, ?)
               ON CONFLICT(item_id, event_name)
               DO UPDATE SET status = excluded.status, updated_at = datetime('now')""",
            (item_id, event_name, status),
        )
    conn.commit()
    conn.close()
