"""
SQLite storage layer for parsed transactions.

Each row represents a single line item.  One email with 3 items becomes 3 rows.
Dedicated columns for Golf Fellowship fields (city, handicap, side_games, etc.)
so they can be filtered and sorted directly from the dashboard.
"""

import json
import os
import re
import sqlite3
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

_SAFE_COL_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _validate_column_names(columns: list[str]) -> None:
    """Raise ValueError if any column name contains unexpected characters."""
    for col in columns:
        if not _SAFE_COL_RE.match(col):
            raise ValueError(f"Invalid column name: {col!r}")


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
    "partner_request", "fellowship_after", "notes",
    "shirt_size", "guest_name", "date_of_birth",
    "net_points_race", "gross_points_race", "city_match_play",
    "subject", "from_addr",
    "transaction_status", "credit_note", "transferred_from_id", "transferred_to_id",
]


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = str(db_path or DB_PATH)
    # Ensure parent directory exists (Railway persistent volume may need creation)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def _connect(db_path: str | Path | None = None):
    """Context manager that guarantees conn.close() even if an exception occurs."""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str | Path | None = None) -> None:
    """Create the items table if it doesn't exist."""
    with _connect(db_path) as conn:

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
                partner_request  TEXT,
                fellowship_after TEXT,
                notes            TEXT,
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
            ("partner_request", "TEXT"),
            ("fellowship_after", "TEXT"),
            ("notes", "TEXT"),
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
            "CREATE INDEX IF NOT EXISTS idx_items_transaction_status ON items(transaction_status)"
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

        # Email-based RSVP overrides — for GG RSVP players without a real item row
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rsvp_email_overrides (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                player_email TEXT NOT NULL,
                event_name   TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'none',
                updated_at   TEXT DEFAULT (datetime('now')),
                UNIQUE(player_email, event_name)
            )
            """
        )

        # Event aliases — maps variant/old item names to the canonical event name.
        # When events are merged or renamed, the old name becomes an alias so
        # transactions keep their original item_name but still link to the event.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_aliases (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                alias_name           TEXT NOT NULL UNIQUE,
                canonical_event_name TEXT NOT NULL,
                created_at           TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_event_aliases_canonical ON event_aliases(canonical_event_name)"
        )

        # Support feedback — bug reports and feature requests from the chat widget
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                type       TEXT NOT NULL CHECK(type IN ('bug', 'feature')),
                message    TEXT NOT NULL,
                page       TEXT,
                role       TEXT,
                status     TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'resolved', 'dismissed')),
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )

        conn.commit()

        # Soft constraint check: warn about NULL values in critical columns
        for col in ("customer", "item_name"):
            row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM items WHERE {col} IS NULL OR {col} = ''"
            ).fetchone()
            if row["cnt"] > 0:
                logger.warning("Data quality: %d items have NULL/empty %s", row["cnt"], col)

        logger.info("Database initialized at %s", db_path or DB_PATH)


def save_items(rows: list[dict], db_path: str | Path | None = None) -> int:
    """
    Insert item rows into the database, skipping duplicates
    (by email_uid + item_index).  Returns the number of newly inserted rows.
    """
    with _connect(db_path) as conn:
        placeholders = ", ".join(["?"] * len(ITEM_COLUMNS))
        col_names = ", ".join(ITEM_COLUMNS)
        sql = f"INSERT OR IGNORE INTO items ({col_names}) VALUES ({placeholders})"

        inserted = 0
        skipped = 0
        for row in rows:
            values = tuple(row.get(col) for col in ITEM_COLUMNS)
            try:
                cursor = conn.execute(sql, values)
                if cursor.rowcount > 0:
                    inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1
                logger.debug("Duplicate item skipped: email_uid=%s item_index=%s",
                             row.get("email_uid"), row.get("item_index"))

        conn.commit()
        logger.info("Saved %d new item rows, %d duplicates skipped (%d total provided)",
                    inserted, skipped, len(rows))
        return inserted


def get_known_email_uids(db_path: str | Path | None = None) -> set[str]:
    """Return the set of email_uid values already stored in the database."""
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT DISTINCT email_uid FROM items").fetchall()
        return {r["email_uid"] for r in rows}


def get_all_items(db_path: str | Path | None = None) -> list[dict]:
    """Return all item rows ordered by order_date descending."""
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM items ORDER BY order_date DESC, id ASC").fetchall()
        return [dict(row) for row in rows]


def get_item_stats(db_path: str | Path | None = None) -> dict:
    """Return summary statistics about stored items."""
    with _connect(db_path) as conn:

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
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM items ORDER BY order_date DESC, id ASC").fetchall()

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
    with _connect(db_path) as conn:

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

    with _connect(db_path) as conn:
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
        logger.info("Autofix: scanned %d rows, fixed %d", len(rows), fixed)
        return {"scanned": len(rows), "fixed": fixed, "details": details}


def autofix_all(db_path: str | Path | None = None) -> dict:
    """
    Run all autofix passes on existing data:
      1. side_games misplacement
      2. customer name → Title Case
      3. course name → canonical spelling
      4. item_name normalisation (e.g. membership variants)
      5. backfill missing customer_email/phone from most recent transaction
      6. RSVP player_name → full name & backfill player_email from items

    Returns a combined summary.
    """
    from email_parser.parser import (
        _fixup_side_games_field,
        _normalize_customer_name,
        _normalize_course_name,
        _normalize_item_name,
        _normalize_chapter,
    )

    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, item_name, customer, customer_email, customer_phone, course, chapter, side_games FROM items"
        ).fetchall()

        fixes = {"side_games": 0, "customer_name": 0, "course_name": 0, "item_name": 0, "chapter": 0, "email_backfill": 0}
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
                old_values = {col: item.get(col, "") for col in updates}
                _validate_column_names(list(updates))
                set_clause = ", ".join(f"{col} = ?" for col in updates)
                values = list(updates.values()) + [row_id]
                conn.execute(f"UPDATE items SET {set_clause} WHERE id = ?", values)
                details.append({"id": row_id, "changes": updates, "old": old_values})

        # --- Email/phone backfill pass ---
        # Build lookup: customer name → best email/phone (from most recent transaction)
        contact_rows = conn.execute(
            """SELECT customer, customer_email, customer_phone, order_date
               FROM items
               WHERE customer IS NOT NULL AND customer != ''
               ORDER BY order_date DESC"""
        ).fetchall()
        best_contact: dict[str, dict] = {}
        for cr in contact_rows:
            name = cr["customer"]
            if name not in best_contact:
                best_contact[name] = {"email": "", "phone": ""}
            if not best_contact[name]["email"] and cr["customer_email"]:
                best_contact[name]["email"] = cr["customer_email"]
            if not best_contact[name]["phone"] and cr["customer_phone"]:
                best_contact[name]["phone"] = cr["customer_phone"]

        # Re-fetch rows that are missing email or phone
        missing_contact = conn.execute(
            """SELECT id, customer, customer_email, customer_phone FROM items
               WHERE customer IS NOT NULL AND customer != ''
                 AND ((customer_email IS NULL OR customer_email = '')
                   OR (customer_phone IS NULL OR customer_phone = ''))"""
        ).fetchall()
        for mc in missing_contact:
            contact = best_contact.get(mc["customer"])
            if not contact:
                continue
            updates = {}
            old_values = {}
            if not mc["customer_email"] and contact["email"]:
                updates["customer_email"] = contact["email"]
                old_values["customer_email"] = mc["customer_email"] or ""
            if not mc["customer_phone"] and contact["phone"]:
                updates["customer_phone"] = contact["phone"]
                old_values["customer_phone"] = mc["customer_phone"] or ""
            if updates:
                set_clause = ", ".join(f"{col} = ?" for col in updates)
                values = list(updates.values()) + [mc["id"]]
                conn.execute(f"UPDATE items SET {set_clause} WHERE id = ?", values)
                details.append({"id": mc["id"], "changes": updates, "old": old_values})
                fixes["email_backfill"] += 1

        # --- RSVP name/email backfill pass ---
        # Build email → full customer name lookup from items (most recent wins)
        fixes["rsvp_updated"] = 0
        email_to_name: dict[str, str] = {}
        for cr in contact_rows:
            em = (cr["customer_email"] or "").strip().lower()
            if em and em not in email_to_name and cr["customer"]:
                email_to_name[em] = cr["customer"]

        # Also build first-name → (full_name, email) for RSVPs with no email.
        # Only store if first name maps to exactly one customer to avoid ambiguity.
        first_to_full: dict[str, list[tuple[str, str]]] = {}
        for em, full_name in email_to_name.items():
            first = full_name.split()[0].lower() if full_name else ""
            if first:
                first_to_full.setdefault(first, []).append((full_name, em))

        rsvp_rows = conn.execute(
            "SELECT id, player_name, player_email FROM rsvps"
        ).fetchall()

        for rr in rsvp_rows:
            rsvp = dict(rr)
            rsvp_id = rsvp["id"]
            rsvp_updates: dict[str, str] = {}
            rsvp_old: dict[str, str] = {}
            email = (rsvp.get("player_email") or "").strip().lower()
            cur_name = rsvp.get("player_name") or ""

            if email and email in email_to_name:
                full_name = email_to_name[email]
                # Upgrade first-name-only to full name
                if full_name and full_name != cur_name:
                    rsvp_updates["player_name"] = full_name
                    rsvp_old["player_name"] = cur_name
            elif not email and cur_name:
                # Try to backfill email by matching first name
                first = cur_name.split()[0].lower()
                candidates = first_to_full.get(first, [])
                if len(candidates) == 1:
                    full_name, matched_email = candidates[0]
                    rsvp_updates["player_email"] = matched_email
                    rsvp_old["player_email"] = ""
                    if full_name and full_name != cur_name:
                        rsvp_updates["player_name"] = full_name
                        rsvp_old["player_name"] = cur_name

            if rsvp_updates:
                set_clause = ", ".join(f"{col} = ?" for col in rsvp_updates)
                values = list(rsvp_updates.values()) + [rsvp_id]
                conn.execute(f"UPDATE rsvps SET {set_clause} WHERE id = ?", values)
                details.append({
                    "id": rsvp_id,
                    "table": "rsvps",
                    "changes": rsvp_updates,
                    "old": rsvp_old,
                })
                fixes["rsvp_updated"] += 1

        conn.commit()

        total_fixed = len(details)
        logger.info(
            "Autofix all: scanned %d rows, %d rows changed "
            "(side_games=%d, customer_name=%d, course_name=%d, item_name=%d, "
            "chapter=%d, email_backfill=%d, rsvp_updated=%d)",
            len(rows), total_fixed,
            fixes["side_games"], fixes["customer_name"], fixes["course_name"],
            fixes["item_name"], fixes["chapter"], fixes["email_backfill"],
            fixes["rsvp_updated"],
        )
        return {
            "scanned": len(rows),
            "fixed": total_fixed,
            "breakdown": fixes,
            "details": details,
        }


def undo_autofix(details: list[dict], db_path: str | Path | None = None) -> dict:
    """Revert autofix changes using the old values saved in details."""
    with _connect(db_path) as conn:
        reverted = 0
        for entry in details:
            row_id = entry.get("id")
            old_values = entry.get("old")
            if not row_id or not old_values:
                continue
            table = entry.get("table", "items")
            set_clause = ", ".join(f"{col} = ?" for col in old_values)
            values = list(old_values.values()) + [row_id]
            conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
            reverted += 1
        conn.commit()
        logger.info("Undo autofix: reverted %d rows", reverted)
        return {"reverted": reverted}


# ---------------------------------------------------------------------------
# Events table
# ---------------------------------------------------------------------------

# Keywords that indicate an item is NOT an event (membership, merch, etc.)
_NON_EVENT_KEYWORDS = [
    "member", "membership", "shirt", "merch", "hat", "polo",
    "donation", "gift card", "season pass",
]


def _is_event_item(item_name: str, *, course: str = "", city: str = "") -> bool:
    """Heuristic: an item is an event if it has a date-like pattern, course name,
    event-type keyword, series identifier, or course/city metadata."""
    if not item_name:
        return False
    lower = item_name.lower()
    # Exclude memberships, merch, etc.
    for kw in _NON_EVENT_KEYWORDS:
        if kw in lower:
            return False
    # If the item row has course or city metadata → it's an event
    if (course and course.strip()) or (city and city.strip()):
        return True
    # Contains a month name or date pattern → likely an event
    import re
    month_pattern = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b"
    if re.search(month_pattern, lower):
        return True
    # Event-type keywords → definitely an event
    event_keywords = [
        "kickoff", "tournament", "scramble", "classic", "invitational",
        "championship", "cup", "open ", "shootout", "challenge",
    ]
    for ek in event_keywords:
        if ek in lower:
            return True
    # Series identifier pattern (e.g., s18.1, a18.2) → season event
    if re.match(r"^[a-z]\d+\.\d+\s", lower):
        return True
    # Contains a known course name keyword → likely an event
    course_keywords = [
        "cantera", "morris", "cedar", "cowboys", "wolfdancer", "falconhead",
        "moody", "quarry", "tpc", "kissing", "plum", "landa", "vaaler",
        "hancock", "craig ranch", "northern hills", "shadowglen",
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

    Items whose item_name is already an alias of another event are skipped
    (they're already linked via the alias table).
    """
    with _connect(db_path) as conn:
        items = conn.execute(
            "SELECT DISTINCT item_name, event_date, course, city FROM items"
        ).fetchall()

        # Load existing aliases so we can skip aliased names
        alias_set = set(
            r["alias_name"]
            for r in conn.execute("SELECT alias_name FROM event_aliases").fetchall()
        )

        inserted = 0
        skipped_non_event = 0
        skipped_aliased = 0
        for item in items:
            name = item["item_name"] or ""
            if not _is_event_item(name, course=item["course"] or "", city=item["city"] or ""):
                skipped_non_event += 1
                continue
            # Skip names that are aliases of another event
            if name in alias_set:
                skipped_aliased += 1
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
                logger.debug("Duplicate event skipped during sync: %s", name)

        conn.commit()
        logger.info("Events sync: %d new, %d non-event skipped, %d aliased skipped",
                    inserted, skipped_non_event, skipped_aliased)
        return {"inserted": inserted, "skipped_non_event": skipped_non_event,
                "skipped_aliased": skipped_aliased, "total_items_scanned": len(items)}


def get_all_events(db_path: str | Path | None = None) -> list[dict]:
    """Return all events with registration counts (active items only).

    Counts items whose item_name matches the event's canonical name
    OR any alias that points to it.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT e.*,
                   COUNT(DISTINCT i.id) as registrations,
                   GROUP_CONCAT(DISTINCT ea.alias_name) as aliases
            FROM events e
            LEFT JOIN event_aliases ea ON ea.canonical_event_name = e.item_name
            LEFT JOIN items i
                ON (i.item_name = e.item_name OR i.item_name = ea.alias_name)
                AND COALESCE(i.transaction_status, 'active') = 'active'
            GROUP BY e.id
            ORDER BY e.event_date DESC, e.id DESC
            """
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            # Convert aliases CSV to list
            d["aliases"] = [a for a in (d.get("aliases") or "").split(",") if a]
            results.append(d)
        return results


def update_event(event_id: int, fields: dict, db_path: str | Path | None = None) -> bool:
    """Update specific fields on an event row.

    When item_name changes the old name is stored as an alias so transactions
    keep their original item_name but still link to this event.
    RSVPs and overrides are updated to the new canonical name.
    Items are NEVER rewritten — they are linked via the alias table.
    """
    allowed = {"item_name", "event_date", "course", "city", "event_type"}
    safe = {k: v for k, v in fields.items() if k in allowed}
    if not safe:
        return False

    with _connect(db_path) as conn:

        # If renaming the event, store old name as alias (don't rewrite items)
        old_name = None
        new_name = safe.get("item_name")
        if new_name:
            row = conn.execute("SELECT item_name FROM events WHERE id = ?", (event_id,)).fetchone()
            if row:
                old_name = row["item_name"]
                if old_name and old_name != new_name:
                    # Store old name as alias of the new canonical name
                    conn.execute(
                        "INSERT OR IGNORE INTO event_aliases (alias_name, canonical_event_name) VALUES (?, ?)",
                        (old_name, new_name),
                    )
                    # Update any existing aliases that pointed to old name
                    conn.execute(
                        "UPDATE event_aliases SET canonical_event_name = ? WHERE canonical_event_name = ?",
                        (new_name, old_name),
                    )
                    # Update RSVPs and overrides to new canonical name
                    conn.execute("UPDATE rsvps SET matched_event = ? WHERE matched_event = ?",
                                 (new_name, old_name))
                    conn.execute("UPDATE rsvp_overrides SET event_name = ? WHERE event_name = ?",
                                 (new_name, old_name))
                    conn.execute("UPDATE rsvp_email_overrides SET event_name = ? WHERE event_name = ?",
                                 (new_name, old_name))
                    logger.info("Renamed event '%s' → '%s': old name stored as alias, RSVPs/overrides updated",
                                old_name, new_name)

        _validate_column_names(list(safe))
        set_clause = ", ".join(f"{col} = ?" for col in safe)
        values = list(safe.values()) + [event_id]
        cursor = conn.execute(f"UPDATE events SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return cursor.rowcount > 0


def delete_event(event_id: int, db_path: str | Path | None = None) -> bool:
    """Delete an event by ID and clean up its aliases."""
    with _connect(db_path) as conn:
        # Get the event name so we can clean up aliases
        row = conn.execute("SELECT item_name FROM events WHERE id = ?", (event_id,)).fetchone()
        if row:
            conn.execute("DELETE FROM event_aliases WHERE canonical_event_name = ?",
                         (row["item_name"],))
        cursor = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()
        return cursor.rowcount > 0


def merge_events(source_id: int, target_id: int, db_path: str | Path | None = None) -> dict | None:
    """
    Merge source event into target event.

    The source event's item_name is stored as an alias of the target so that
    transactions keep their original item_name.  RSVPs and overrides are
    moved to the target canonical name.  The source event row is deleted.

    Returns summary dict or None on failure.
    """
    with _connect(db_path) as conn:

        source = conn.execute("SELECT * FROM events WHERE id = ?", (source_id,)).fetchone()
        target = conn.execute("SELECT * FROM events WHERE id = ?", (target_id,)).fetchone()

        if not source or not target:
            return None

        source = dict(source)
        target = dict(target)
        src_name = source["item_name"]
        tgt_name = target["item_name"]

        if src_name == tgt_name:
            return None

        # Store source event name as alias of target (so items stay linked)
        conn.execute(
            "INSERT OR IGNORE INTO event_aliases (alias_name, canonical_event_name) VALUES (?, ?)",
            (src_name, tgt_name),
        )

        # Re-point any aliases that pointed to the source to now point to the target
        conn.execute(
            "UPDATE event_aliases SET canonical_event_name = ? WHERE canonical_event_name = ?",
            (tgt_name, src_name),
        )

        # Count items that will now link via alias
        items_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM items WHERE item_name = ? AND COALESCE(transaction_status, 'active') = 'active'",
            (src_name,),
        ).fetchone()
        items_linked = items_row["cnt"] if items_row else 0

        # Move RSVPs to target canonical name
        cur = conn.execute("UPDATE rsvps SET matched_event = ? WHERE matched_event = ?",
                           (tgt_name, src_name))
        rsvps_moved = cur.rowcount

        # Move overrides to target canonical name
        cur = conn.execute("UPDATE rsvp_overrides SET event_name = ? WHERE event_name = ?",
                           (tgt_name, src_name))
        overrides_moved = cur.rowcount
        conn.execute("UPDATE rsvp_email_overrides SET event_name = ? WHERE event_name = ?",
                     (tgt_name, src_name))

        # Delete source event
        conn.execute("DELETE FROM events WHERE id = ?", (source_id,))

        conn.commit()

        logger.info("Merged event '%s' (#%d) → '%s' (#%d): %d items linked via alias, %d RSVPs, %d overrides moved",
                    src_name, source_id, tgt_name, target_id,
                    items_linked, rsvps_moved, overrides_moved)

        return {
            "source_event": src_name,
            "target_event": tgt_name,
            "items_linked": items_linked,
            "rsvps_moved": rsvps_moved,
            "overrides_moved": overrides_moved,
        }


def get_orphaned_items(db_path: str | Path | None = None) -> list[dict]:
    """
    Find items whose item_name doesn't match any event directly
    AND doesn't match any alias in event_aliases
    AND that look like events (not memberships, merch, etc.).

    Returns list of dicts with item_name, count, and sample fields.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT i.item_name,
                      COUNT(*) as item_count,
                      MIN(i.event_date) as event_date,
                      MIN(i.course) as course,
                      MIN(i.city) as city,
                      GROUP_CONCAT(DISTINCT i.customer) as customers
               FROM items i
               LEFT JOIN events e ON i.item_name = e.item_name
               LEFT JOIN event_aliases ea ON i.item_name = ea.alias_name
               WHERE e.id IS NULL
                 AND ea.id IS NULL
                 AND COALESCE(i.transaction_status, 'active') IN ('active', 'rsvp_only')
               GROUP BY i.item_name
               ORDER BY i.item_name"""
        ).fetchall()

        # Safety net: include everything EXCEPT obvious non-events.
        # Better to surface a false positive than miss a real event.
        result = []
        for r in rows:
            row = dict(r)
            name = (row["item_name"] or "").lower()
            is_non_event = any(kw in name for kw in _NON_EVENT_KEYWORDS)
            if not is_non_event:
                # Truncate customer list for display
                customers = row.get("customers") or ""
                row["customers"] = customers[:200]
                result.append(row)

        logger.info("Found %d orphaned item groups (safety-net filter)", len(result))
        return result


def resolve_orphaned_items(old_item_name: str, target_event_name: str,
                           db_path: str | Path | None = None) -> dict:
    """
    Resolve orphaned items by adding old_item_name as an alias of target_event_name.

    Items keep their original item_name — the alias table links them to the event.
    RSVPs matched to the old name are updated to the target canonical name.

    Returns summary.
    """
    with _connect(db_path) as conn:

        # Add the orphan's item_name as an alias of the target event
        conn.execute(
            "INSERT OR IGNORE INTO event_aliases (alias_name, canonical_event_name) VALUES (?, ?)",
            (old_item_name, target_event_name),
        )

        # Count how many items this links
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM items WHERE item_name = ? AND COALESCE(transaction_status, 'active') IN ('active', 'rsvp_only')",
            (old_item_name,),
        ).fetchone()
        items_linked = row["cnt"] if row else 0

        # Update RSVPs matched to the old name
        conn.execute("UPDATE rsvps SET matched_event = ? WHERE matched_event = ?",
                     (target_event_name, old_item_name))

        conn.commit()

        logger.info("Resolved orphan '%s' → '%s' (alias created, %d items linked)",
                    old_item_name, target_event_name, items_linked)
        return {
            "old_item_name": old_item_name,
            "target_event": target_event_name,
            "items_linked": items_linked,
        }


# ---------------------------------------------------------------------------
# Customer Merge
# ---------------------------------------------------------------------------


def merge_customers(source_name: str, target_name: str,
                    db_path: str | Path | None = None) -> dict:
    """
    Merge one customer into another by updating all items rows.

    Rewrites items.customer from source_name to target_name.
    Preserves target's email/phone; fills in from source if target lacks them.

    Returns summary with count of items updated.
    """
    with _connect(db_path) as conn:

        # Grab contact info from target (prefer) then source as fallback
        target_row = conn.execute(
            """SELECT customer_email, customer_phone FROM items
               WHERE customer = ? AND (customer_email IS NOT NULL AND customer_email != '')
               ORDER BY order_date DESC LIMIT 1""",
            (target_name,),
        ).fetchone()
        source_row = conn.execute(
            """SELECT customer_email, customer_phone FROM items
               WHERE customer = ? AND (customer_email IS NOT NULL AND customer_email != '')
               ORDER BY order_date DESC LIMIT 1""",
            (source_name,),
        ).fetchone()

        # Determine best email/phone (target wins, source fills gaps)
        best_email = (target_row["customer_email"] if target_row else "") or \
                     (source_row["customer_email"] if source_row else "") or ""
        best_phone = (target_row["customer_phone"] if target_row else "") or \
                     (source_row["customer_phone"] if source_row else "") or ""

        # Update all source items to the target customer name
        cursor = conn.execute(
            "UPDATE items SET customer = ? WHERE customer = ?",
            (target_name, source_name),
        )
        items_updated = cursor.rowcount

        # Backfill email/phone on all target items that are missing them
        if best_email:
            conn.execute(
                "UPDATE items SET customer_email = ? WHERE customer = ? AND (customer_email IS NULL OR customer_email = '')",
                (best_email, target_name),
            )
        if best_phone:
            conn.execute(
                "UPDATE items SET customer_phone = ? WHERE customer = ? AND (customer_phone IS NULL OR customer_phone = '')",
                (best_phone, target_name),
            )

        conn.commit()

        logger.info("Merged customer '%s' → '%s' (%d items updated)",
                    source_name, target_name, items_updated)
        return {
            "source": source_name,
            "target": target_name,
            "items_updated": items_updated,
        }


# ---------------------------------------------------------------------------
# Event Aliases — map variant item names to canonical event names
# ---------------------------------------------------------------------------

def add_event_alias(alias_name: str, canonical_event_name: str,
                    db_path: str | Path | None = None) -> bool:
    """Add an alias mapping.  Returns True if inserted, False if already exists."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO event_aliases (alias_name, canonical_event_name) VALUES (?, ?)",
            (alias_name, canonical_event_name),
        )
        inserted = conn.execute("SELECT changes()").fetchone()[0] > 0
        conn.commit()
        return inserted


def get_aliases_for_event(canonical_event_name: str,
                          db_path: str | Path | None = None) -> list[str]:
    """Return all alias names that map to the given canonical event name."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT alias_name FROM event_aliases WHERE canonical_event_name = ?",
            (canonical_event_name,),
        ).fetchall()
        return [r["alias_name"] for r in rows]


def get_all_event_aliases(db_path: str | Path | None = None) -> dict:
    """Return dict mapping each alias_name → canonical_event_name."""
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT alias_name, canonical_event_name FROM event_aliases").fetchall()
        return {r["alias_name"]: r["canonical_event_name"] for r in rows}


def update_aliases_canonical(old_canonical: str, new_canonical: str,
                             db_path: str | Path | None = None) -> int:
    """Update all aliases that pointed to old_canonical to now point to new_canonical."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE event_aliases SET canonical_event_name = ? WHERE canonical_event_name = ?",
            (new_canonical, old_canonical),
        )
        updated = cur.rowcount
        conn.commit()
        return updated


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

    _validate_column_names(list(safe_fields))
    set_clause = ", ".join(f"{col} = ?" for col in safe_fields)
    values = list(safe_fields.values()) + [item_id]

    with _connect(db_path) as conn:
        cursor = conn.execute(f"UPDATE items SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return cursor.rowcount > 0


def get_item(item_id: int, db_path: str | Path | None = None) -> dict | None:
    """Return a single item by ID, or None if not found."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return dict(row) if row else None


def credit_item(item_id: int, note: str = "", db_path: str | Path | None = None) -> bool:
    """Mark an item as credited (money held for future use)."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE items SET transaction_status = 'credited', credit_note = ? WHERE id = ? AND COALESCE(transaction_status, 'active') = 'active'",
            (note or "Credit on account", item_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def transfer_item(item_id: int, target_event_name: str, note: str = "", db_path: str | Path | None = None) -> dict | None:
    """
    Transfer an item to a different event.

    Marks the original as 'transferred' and creates a new item
    at the target event with $0 price (credit applied).
    Returns the new item dict or None on failure.
    """
    with _connect(db_path) as conn:

        # Fetch the original item
        orig = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not orig:
            return None
        orig = dict(orig)

        if orig.get("transaction_status") not in (None, "active"):
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

        new_values["id"] = new_id
        return new_values


def reverse_credit(item_id: int, db_path: str | Path | None = None) -> bool:
    """
    Reverse a credit or transfer.

    For credits: simply resets to active.
    For transfers: resets original to active and deletes the transferred-to item.
    """
    with _connect(db_path) as conn:
        item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            return False
        item = dict(item)

        status = item.get("transaction_status")
        if status not in ("credited", "transferred"):
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
        return True


def create_event(item_name: str, event_date: str = None, course: str = None,
                 city: str = None, db_path: str | Path | None = None) -> dict | None:
    """Manually create a new event. Returns the event dict or None if duplicate."""
    with _connect(db_path) as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO events (item_name, event_date, course, city, event_type) VALUES (?, ?, ?, ?, 'event')",
                (item_name, event_date, course, city),
            )
            conn.commit()
            new_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM events WHERE id = ?", (new_id,)).fetchone()
            return dict(row) if row else None
        except sqlite3.IntegrityError:
            return None


def seed_events(events: list[dict], db_path: str | Path | None = None) -> dict:
    """
    Batch-insert events. Each dict should have: item_name, event_date, course, city.
    Skips duplicates. Returns {"inserted": N, "skipped": N}.
    """
    with _connect(db_path) as conn:
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
                logger.debug("Duplicate event skipped during seed: %s", ev.get("item_name"))
        conn.commit()
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

    with _connect(db_path) as conn:

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
    with _connect(db_path) as conn:

        item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            return None
        item = dict(item)

        if item.get("transaction_status") != "rsvp_only":
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

        if updated:
            updated = dict(updated)
            logger.info("Upgraded RSVP item %d to paid registration", item_id)
            return updated
        return None


def delete_item(item_id: int, db_path: str | Path | None = None) -> bool:
    """Delete an item row by ID.  Returns True if a row was deleted."""
    with _connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
        return cursor.rowcount > 0


def delete_manual_player(item_id: int, db_path: str | Path | None = None) -> bool:
    """Delete a manually added or unpaid RSVP player.

    Allowed for: manual entries (email_uid starts with 'manual-'),
    rsvp_only items, and gg_rsvp items.
    Returns True if the row was deleted, False if not found or not allowed.
    """
    with _connect(db_path) as conn:
        item = conn.execute(
            "SELECT email_uid, transaction_status FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        if not item:
            return False
        row = dict(item)
        uid = row.get("email_uid") or ""
        tx_status = row.get("transaction_status") or "active"
        # Allow deletion of manual entries, rsvp_only, and gg_rsvp items
        if not uid.startswith("manual-") and tx_status not in ("rsvp_only", "gg_rsvp"):
            logger.warning("Refused to delete paid item %d (uid=%s, status=%s)", item_id, uid, tx_status)
            return False
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
        logger.info("Deleted player item %d (uid=%s, status=%s)", item_id, uid, tx_status)
        return True


# ---------------------------------------------------------------------------
# RSVPs — Golf Genius round signup confirmations
# ---------------------------------------------------------------------------

def get_known_rsvp_uids(db_path: str | Path | None = None) -> set[str]:
    """Return the set of email_uid values already stored in rsvps."""
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT DISTINCT email_uid FROM rsvps").fetchall()
        return {r["email_uid"] for r in rows}


def match_rsvp_to_event(event_identifier: str, event_date: str | None,
                         db_path: str | Path | None = None) -> str | None:
    """Try to match an RSVP event identifier to an events.item_name.

    Only returns a match when confident. Returns None for ambiguous cases
    so they can be resolved manually.

    Strategies (in order of confidence):
      1. item_name contains the full event_identifier substring (exact)
      2. Extract course name from identifier and match course + date
      3. Extract course name from identifier and match course alone (single match)
      4. Match by event_date alone ONLY if single event on that date AND
         the city from the identifier matches the event's city
    """
    with _connect(db_path) as conn:
        identifier_upper = (event_identifier or "").upper().strip()

        # Strategy 1: Direct substring match on full identifier
        rows = conn.execute(
            "SELECT item_name FROM events WHERE UPPER(item_name) LIKE ?",
            (f"%{identifier_upper}%",),
        ).fetchall()
        if len(rows) == 1:
            return rows[0]["item_name"]

        # Extract the course name portion from the identifier.
        # GG identifiers look like: "a18.2 PRIME TIME KICKOFF | SHADOWGLEN"
        # or "s9.1 The Quarry" — the course is typically the last segment.
        from email_parser.parser import _normalize_course_name
        course_part = event_identifier
        if "|" in event_identifier:
            course_part = event_identifier.split("|")[-1].strip()
        elif " " in event_identifier:
            # Try the last word(s) after any prefix like "a18.2"
            parts = event_identifier.split()
            # Skip leading codes like "s9.1", "a18.2"
            import re
            start = 0
            for i, p in enumerate(parts):
                if re.match(r'^[a-z]\d+\.\d+$', p, re.IGNORECASE):
                    start = i + 1
            course_part = " ".join(parts[start:])

        normalized_course = _normalize_course_name(course_part)

        # Strategy 2: Normalized course name + date (high confidence)
        if normalized_course and event_date:
            rows = conn.execute(
                "SELECT item_name FROM events WHERE UPPER(course) LIKE ? AND event_date = ?",
                (f"%{normalized_course.upper()}%", event_date),
            ).fetchall()
            if len(rows) == 1:
                return rows[0]["item_name"]

        # Strategy 3: Normalized course name alone (only if single match)
        if normalized_course:
            rows = conn.execute(
                "SELECT item_name FROM events WHERE UPPER(course) LIKE ?",
                (f"%{normalized_course.upper()}%",),
            ).fetchall()
            if len(rows) == 1:
                return rows[0]["item_name"]

        # Strategy 4: Also try the raw course_part (un-normalized) in item_name
        if course_part and course_part != event_identifier:
            rows = conn.execute(
                "SELECT item_name FROM events WHERE UPPER(item_name) LIKE ?",
                (f"%{course_part.upper()}%",),
            ).fetchall()
            if len(rows) == 1:
                return rows[0]["item_name"]

            # With date as additional filter
            if event_date:
                rows = conn.execute(
                    "SELECT item_name FROM events WHERE UPPER(item_name) LIKE ? AND event_date = ?",
                    (f"%{course_part.upper()}%", event_date),
                ).fetchall()
                if len(rows) == 1:
                    return rows[0]["item_name"]

        # Strategy 5: Check if the identifier matches an alias name
        rows = conn.execute(
            "SELECT canonical_event_name FROM event_aliases WHERE UPPER(alias_name) LIKE ?",
            (f"%{identifier_upper}%",),
        ).fetchall()
        if len(rows) == 1:
            return rows[0]["canonical_event_name"]

        # Also try course part against aliases
        if course_part and course_part != event_identifier:
            rows = conn.execute(
                "SELECT canonical_event_name FROM event_aliases WHERE UPPER(alias_name) LIKE ?",
                (f"%{course_part.upper()}%",),
            ).fetchall()
            if len(rows) == 1:
                return rows[0]["canonical_event_name"]

        # If none of the above matched confidently, return None.
        # Do NOT fall back to date-only matching — too risky for mismatches.
        return None


def match_rsvp_to_item(player_email: str | None, player_name: str | None,
                        event_name: str, db_path: str | Path | None = None) -> int | None:
    """Try to match an RSVP player to an items row (transaction).

    Searches items whose item_name matches the canonical event_name
    OR any alias that maps to it.

    Strategies:
      1. Match by player email + event name (or alias)
      2. Match by player first name + event name (or alias, only if single match)
    """
    with _connect(db_path) as conn:

        # Build list of names to search: canonical + all aliases
        aliases = conn.execute(
            "SELECT alias_name FROM event_aliases WHERE canonical_event_name = ?",
            (event_name,),
        ).fetchall()
        name_list = [event_name] + [r["alias_name"] for r in aliases]
        placeholders = ",".join(["?"] * len(name_list))

        # Strategy 1: Email match
        if player_email:
            row = conn.execute(
                f"""SELECT id FROM items
                   WHERE LOWER(customer_email) = LOWER(?)
                     AND item_name IN ({placeholders})
                     AND COALESCE(transaction_status, 'active') = 'active'""",
                [player_email] + name_list,
            ).fetchone()
            if row:
                return row["id"]

        # Strategy 2: First name match (loose — only if one match)
        if player_name:
            rows = conn.execute(
                f"""SELECT id FROM items
                   WHERE customer LIKE ?
                     AND item_name IN ({placeholders})
                     AND COALESCE(transaction_status, 'active') = 'active'""",
                [f"{player_name}%"] + name_list,
            ).fetchall()
            if len(rows) == 1:
                return rows[0]["id"]

        return None


def save_rsvp(rsvp: dict, db_path: str | Path | None = None) -> int | None:
    """
    Save a parsed RSVP to the database.

    Performs event and item matching before insert.
    Returns the rsvp id, or None if it was a duplicate.
    """
    with _connect(db_path) as conn:

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
                logger.info(
                    "Saved RSVP: %s %s for %s (matched_event=%s, matched_item=%s)",
                    rsvp.get("player_name"), rsvp["response"],
                    rsvp.get("event_identifier"), matched_event, matched_item_id,
                )
                return rsvp_id
        except sqlite3.IntegrityError:
            logger.debug("Duplicate RSVP skipped: email_uid=%s", rsvp.get("email_uid"))

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
    Also resolves the full player name from existing items (player cards)
    by matching on player_email, and flags whether a player card was found.
    """
    with _connect(db_path) as conn:
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

        # Resolve full names from player cards (items table) by email
        results = []
        for r in rows:
            rsvp = dict(r)
            rsvp["resolved_name"] = rsvp.get("player_name")
            rsvp["has_player_card"] = False
            email = (rsvp.get("player_email") or "").strip().lower()
            if email:
                card = conn.execute(
                    """SELECT customer FROM items
                       WHERE LOWER(customer_email) = ?
                         AND customer IS NOT NULL AND customer != ''
                       ORDER BY order_date DESC LIMIT 1""",
                    (email,),
                ).fetchone()
                if card:
                    rsvp["resolved_name"] = card["customer"]
                    rsvp["has_player_card"] = True
            results.append(rsvp)

        return results


def get_all_rsvps(event_name: str = "", response: str = "",
                   db_path: str | Path | None = None) -> list[dict]:
    """Return RSVPs with optional filtering by event and/or response."""
    with _connect(db_path) as conn:
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
        return [dict(r) for r in rows]


def get_rsvp_stats(db_path: str | Path | None = None) -> dict:
    """Return summary RSVP statistics."""
    with _connect(db_path) as conn:
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
    with _connect(db_path) as conn:
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
        logger.info("Rematch: %d events, %d items rematched", rematched_events, rematched_items)
        return {"rematched_events": rematched_events, "rematched_items": rematched_items}


def manual_match_rsvp(rsvp_id: int, event_name: str,
                       db_path: str | Path | None = None) -> bool:
    """Manually set the matched_event for an RSVP.

    Also attempts to match the player to a specific item in that event.
    Returns True if the RSVP was updated.
    """
    with _connect(db_path) as conn:
        rsvp = conn.execute("SELECT * FROM rsvps WHERE id = ?", (rsvp_id,)).fetchone()
        if not rsvp:
            return False
        rsvp = dict(rsvp)

        # Try to match the player to an item
        matched_item_id = match_rsvp_to_item(
            rsvp.get("player_email"), rsvp.get("player_name"),
            event_name, db_path,
        )

        conn.execute(
            "UPDATE rsvps SET matched_event = ?, matched_item_id = ? WHERE id = ?",
            (event_name, matched_item_id, rsvp_id),
        )
        conn.commit()
        logger.info("Manual RSVP match: rsvp #%d → event '%s' (item=%s)",
                    rsvp_id, event_name, matched_item_id)
        return True


def unmatch_rsvp(rsvp_id: int, db_path: str | Path | None = None) -> bool:
    """Clear the matched_event and matched_item_id for an RSVP.

    Returns True if the RSVP was updated.
    """
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE rsvps SET matched_event = NULL, matched_item_id = NULL WHERE id = ?",
            (rsvp_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


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

    with _connect(db_path) as conn:
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
        return updated


# ---------------------------------------------------------------------------
# Manual RSVP Overrides
# ---------------------------------------------------------------------------

def get_rsvp_overrides(event_name: str, db_path=None) -> dict:
    """Return {item_id: status} for all manual overrides on an event."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT item_id, status FROM rsvp_overrides WHERE event_name = ?",
            (event_name,),
        ).fetchall()
        return {r[0]: r[1] for r in rows}


def set_rsvp_override(item_id: int, event_name: str, status: str, db_path=None):
    """Upsert a manual RSVP override. status is 'none', 'playing', or 'not_playing'."""
    with _connect(db_path) as conn:
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


def get_rsvp_email_overrides(event_name: str, db_path=None) -> dict:
    """Return {player_email: status} for email-based overrides (GG RSVP players)."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT player_email, status FROM rsvp_email_overrides WHERE event_name = ?",
            (event_name,),
        ).fetchall()
        return {r[0]: r[1] for r in rows}


def set_rsvp_email_override(player_email: str, event_name: str, status: str, db_path=None):
    """Upsert an email-based RSVP override for GG RSVP players without a real item row."""
    with _connect(db_path) as conn:
        if status == "none":
            conn.execute(
                "DELETE FROM rsvp_email_overrides WHERE player_email = ? AND event_name = ?",
                (player_email, event_name),
            )
        else:
            conn.execute(
                """INSERT INTO rsvp_email_overrides (player_email, event_name, status)
                   VALUES (?, ?, ?)
                   ON CONFLICT(player_email, event_name)
                   DO UPDATE SET status = excluded.status, updated_at = datetime('now')""",
                (player_email, event_name, status),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Support Feedback — bug reports and feature requests
# ---------------------------------------------------------------------------

def save_feedback(feedback_type: str, message: str, page: str = "",
                  role: str = "", db_path: str | Path | None = None) -> dict:
    """Save a bug report or feature request. Returns the new row as a dict."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO feedback (type, message, page, role) VALUES (?, ?, ?, ?)",
            (feedback_type, message, page or None, role or None),
        )
        conn.commit()
        new_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM feedback WHERE id = ?", (new_id,)).fetchone()
        return dict(row) if row else {"id": new_id}


def get_all_feedback(db_path: str | Path | None = None) -> list[dict]:
    """Return all feedback rows, newest first."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM feedback ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def update_feedback_status(feedback_id: int, status: str,
                           db_path: str | Path | None = None) -> bool:
    """Update the status of a feedback row. Returns True if updated."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE feedback SET status = ? WHERE id = ?",
            (status, feedback_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_open_feedback(db_path: str | Path | None = None) -> list[dict]:
    """Return all feedback with status 'open', newest first."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM feedback WHERE status = 'open' ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_feedback(hours: int = 24, db_path: str | Path | None = None) -> list[dict]:
    """Return feedback created within the last N hours."""
    with _connect(db_path) as conn:
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        rows = conn.execute(
            "SELECT * FROM feedback WHERE created_at >= ? ORDER BY created_at DESC",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_rsvps(hours: int = 24, db_path: str | Path | None = None) -> list[dict]:
    """Return RSVPs received within the last N hours."""
    with _connect(db_path) as conn:
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        rows = conn.execute(
            "SELECT * FROM rsvps WHERE received_at >= ? ORDER BY received_at DESC",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_upcoming_events(db_path: str | Path | None = None) -> list[dict]:
    """Return future events with registration counts, sorted by date ascending."""
    with _connect(db_path) as conn:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute(
            """
            SELECT e.*,
                   COUNT(DISTINCT i.id) as registrations,
                   GROUP_CONCAT(DISTINCT ea.alias_name) as aliases
            FROM events e
            LEFT JOIN event_aliases ea ON ea.canonical_event_name = e.item_name
            LEFT JOIN items i
                ON (i.item_name = e.item_name OR i.item_name = ea.alias_name)
                AND COALESCE(i.transaction_status, 'active') = 'active'
            WHERE e.event_date >= ?
            GROUP BY e.id
            ORDER BY e.event_date ASC
            """,
            (today,),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["aliases"] = [a for a in (d.get("aliases") or "").split(",") if a]
            results.append(d)
        return results
