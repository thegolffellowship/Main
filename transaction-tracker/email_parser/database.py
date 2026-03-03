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

import anthropic as _anthropic

logger = logging.getLogger(__name__)

_SAFE_COL_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# ---------------------------------------------------------------------------
# Email / phone validation & normalization
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def validate_email(email: str) -> str | None:
    """Return cleaned email or None if invalid."""
    email = (email or "").strip().lower()
    if not email:
        return None
    if _EMAIL_RE.match(email):
        return email
    return None


def normalize_phone(phone: str) -> str:
    """Normalize phone to (XXX) XXX-XXXX for 10-digit US numbers, passthrough otherwise."""
    phone = (phone or "").strip()
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    # Strip leading 1 for US numbers
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    # Return original for international / non-standard numbers
    return phone


def validate_phone(phone: str) -> str | None:
    """Return normalized phone or None if clearly invalid (fewer than 7 digits)."""
    phone = (phone or "").strip()
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        return None
    return normalize_phone(phone)


# ---------------------------------------------------------------------------
# AI-powered name parsing
# ---------------------------------------------------------------------------

_NAME_PARSE_PROMPT = """\
You are a name parsing assistant. Given a list of raw name strings, parse each \
one into its component parts and return a JSON array. Each element should be an \
object with these keys:
- "first_name": The person's first/given name, in Title Case
- "last_name": The person's last/family name, in Title Case
- "middle_name": Middle name or initial if present, in Title Case, else null
- "suffix": Generational suffix like Jr., Sr., III, IV, etc., else null

RULES:
- Handle ALL common formats: "First Last", "LAST, First", "First Middle Last", \
  "Last, First Middle", "LASTNAME, First M.", etc.
- ALL-CAPS names should be converted to Title Case (ARONBERG → Aronberg).
- Strip extra whitespace and punctuation artifacts.
- If a name is ambiguous or cannot be parsed, make your best guess.
- Return ONLY the JSON array — no markdown, no explanation.

Examples:
Input: ["ARONBERG, Mark", "John Michael Smith Jr.", "Jane Doe"]
Output: [{"first_name":"Mark","last_name":"Aronberg","middle_name":null,"suffix":null},{"first_name":"John","last_name":"Smith","middle_name":"Michael","suffix":"Jr."},{"first_name":"Jane","last_name":"Doe","middle_name":null,"suffix":null}]
"""


def parse_names_ai(names: list[str]) -> list[dict]:
    """Use Claude to parse a batch of name strings into first/last/middle/suffix.

    Falls back to simple splitting if the AI call fails.
    """
    if not names:
        return []

    # Try AI parsing in batches of 100
    results = []
    batch_size = 100
    for i in range(0, len(names), batch_size):
        batch = names[i:i + batch_size]
        try:
            client = _anthropic.Anthropic()
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": _NAME_PARSE_PROMPT + "\n\nInput: " + json.dumps(batch),
                }],
            )
            text = resp.content[0].text.strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                text = re.sub(r"^```\w*\n?", "", text)
                text = re.sub(r"\n?```$", "", text)
            parsed = json.loads(text)
            if isinstance(parsed, list) and len(parsed) == len(batch):
                results.extend(parsed)
            else:
                results.extend(_parse_names_fallback(batch))
        except Exception:
            logger.warning("AI name parsing failed for batch %d, using fallback", i)
            results.extend(_parse_names_fallback(batch))

    return results


def _parse_names_fallback(names: list[str]) -> list[dict]:
    """Simple regex-based fallback for name parsing."""
    results = []
    suffixes = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}
    for raw in names:
        name = (raw or "").strip()
        if not name:
            results.append({"first_name": None, "last_name": None,
                            "middle_name": None, "suffix": None})
            continue

        # Title-case if all upper
        if name == name.upper():
            name = name.title()

        # Detect "Last, First [Middle]" format
        if "," in name:
            parts = [p.strip() for p in name.split(",", 1)]
            last = parts[0]
            rest = parts[1].split() if len(parts) > 1 else []
        else:
            parts = name.split()
            if len(parts) == 1:
                results.append({"first_name": parts[0], "last_name": None,
                                "middle_name": None, "suffix": None})
                continue
            last = parts[-1]
            rest = parts[:-1]

        # Extract suffix
        sfx = None
        if rest and rest[-1].lower().rstrip(".") in {s.rstrip(".") for s in suffixes}:
            sfx = rest.pop()
        elif last.lower().rstrip(".") in {s.rstrip(".") for s in suffixes}:
            sfx = last
            # Last was actually suffix, need to re-parse
            if "," not in raw:
                all_parts = name.split()
                sfx = all_parts[-1]
                last = all_parts[-2] if len(all_parts) > 2 else None
                rest = all_parts[:-2]

        first = rest[0] if rest else None
        middle = " ".join(rest[1:]) if len(rest) > 1 else None

        results.append({
            "first_name": first,
            "last_name": last,
            "middle_name": middle,
            "suffix": sfx,
        })

    return results


def _backfill_name_parts(conn: sqlite3.Connection) -> None:
    """One-time backfill: parse existing customer names into first/last parts."""
    # Only process rows that have a customer but no first_name yet
    rows = conn.execute(
        """SELECT DISTINCT customer FROM items
           WHERE customer IS NOT NULL AND customer != ''
             AND (first_name IS NULL OR first_name = '')"""
    ).fetchall()

    if not rows:
        return

    names = [r["customer"] for r in rows]
    logger.info("Backfilling name parts for %d customers", len(names))

    parsed = parse_names_ai(names)

    for name, parts in zip(names, parsed):
        conn.execute(
            """UPDATE items SET first_name = ?, last_name = ?, middle_name = ?, suffix = ?
               WHERE customer = ? COLLATE NOCASE
                 AND (first_name IS NULL OR first_name = '')""",
            (parts.get("first_name"), parts.get("last_name"),
             parts.get("middle_name"), parts.get("suffix"), name),
        )
    conn.commit()
    logger.info("Backfilled name parts for %d customers", len(names))


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
    "first_name", "last_name", "middle_name", "suffix",
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
    "wd_reason", "wd_note", "wd_credits", "credit_amount",
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
def managed_connection(db_path: str | Path | None = None):
    """Context manager that guarantees connection is closed even on exceptions."""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


# Alias so both names work (feature code uses _connect, audit code uses managed_connection)
_connect = managed_connection


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
                first_name       TEXT,
                last_name        TEXT,
                middle_name      TEXT,
                suffix           TEXT,
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
            ("wd_reason", "TEXT"),
            ("wd_note", "TEXT"),
            ("wd_credits", "TEXT"),
            ("credit_amount", "TEXT"),
            ("first_name", "TEXT"),
            ("last_name", "TEXT"),
            ("middle_name", "TEXT"),
            ("suffix", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE items ADD COLUMN {col} {col_type}")
                logger.info("Added new column: %s", col)
            except sqlite3.OperationalError:
                pass  # column already exists

        # Customer aliases table — supports multiple alias names/emails per customer
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customer_aliases (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name   TEXT NOT NULL,
                alias_type      TEXT NOT NULL CHECK(alias_type IN ('name', 'email')),
                alias_value     TEXT NOT NULL,
                created_at      TEXT DEFAULT (datetime('now'))
            )
        """)

        # Backfill: parse existing customer names into first/last name parts.
        # Only runs once — skips rows that already have first_name populated.
        _backfill_name_parts(conn)

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

        # Message templates — reusable email/SMS message templates
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_templates (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                channel    TEXT NOT NULL DEFAULT 'email',
                subject    TEXT,
                html_body  TEXT,
                sms_body   TEXT,
                is_system  INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT
            )
            """
        )

        # Message log — tracks every message sent (email or SMS)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_log (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name        TEXT,
                template_id       INTEGER,
                channel           TEXT NOT NULL,
                recipient_name    TEXT,
                recipient_address TEXT NOT NULL,
                subject           TEXT,
                body_preview      TEXT,
                status            TEXT DEFAULT 'sent',
                error_message     TEXT,
                sent_by           TEXT,
                sent_at           TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_message_log_event ON message_log(event_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_message_log_sent_at ON message_log(sent_at DESC)"
        )

        # Seed built-in message templates on first run
        existing = conn.execute("SELECT COUNT(*) as cnt FROM message_templates WHERE is_system = 1").fetchone()
        if existing["cnt"] == 0:
            system_templates = [
                (
                    "Payment Reminder", "email",
                    "Payment Reminder — {event_name}",
                    "<p>Hi {player_name},</p>"
                    "<p>This is a friendly reminder that we have you down for "
                    "<strong>{event_name}</strong>, but we haven't received your payment yet.</p>"
                    "<p>Please complete your registration at your earliest convenience.</p>"
                    "<p>Thanks,<br>The Golf Fellowship</p>",
                    None,
                ),
                (
                    "Event Announcement", "both",
                    "{event_name} — You're Registered!",
                    "<p>Hi {player_name},</p>"
                    "<p>You're registered for <strong>{event_name}</strong> at "
                    "<strong>{course}</strong> on <strong>{event_date}</strong>!</p>"
                    "<p>We look forward to seeing you there.</p>"
                    "<p>Thanks,<br>The Golf Fellowship</p>",
                    "You're registered for {event_name} at {course} on {event_date}! See you there.",
                ),
                (
                    "Tee Time Update", "both",
                    "Tee Times — {event_name}",
                    "<p>Hi {player_name},</p>"
                    "<p>Tee times are set for <strong>{event_name}</strong> at "
                    "<strong>{course}</strong> on <strong>{event_date}</strong>.</p>"
                    "<p>Thanks,<br>The Golf Fellowship</p>",
                    "Tee times are set for {event_name} at {course} on {event_date}.",
                ),
                (
                    "Weather Alert", "both",
                    "Weather Update — {event_name}",
                    "<p>Hi {player_name},</p>"
                    "<p>Weather update for <strong>{event_name}</strong> on "
                    "<strong>{event_date}</strong>.</p>"
                    "<p>Thanks,<br>The Golf Fellowship</p>",
                    "Weather update for {event_name} on {event_date}.",
                ),
                (
                    "Event Cancellation", "both",
                    "{event_name} — Cancelled",
                    "<p>Hi {player_name},</p>"
                    "<p>Unfortunately, <strong>{event_name}</strong> scheduled for "
                    "<strong>{event_date}</strong> at <strong>{course}</strong> has been "
                    "cancelled.</p>"
                    "<p>We'll be in touch with more details.</p>"
                    "<p>Thanks,<br>The Golf Fellowship</p>",
                    "{event_name} on {event_date} at {course} has been cancelled. More details to follow.",
                ),
                (
                    "Day-Of Reminder", "both",
                    "See You Today — {event_name}",
                    "<p>Hi {player_name},</p>"
                    "<p>See you today at <strong>{course}</strong> for "
                    "<strong>{event_name}</strong>!</p>"
                    "<p>Thanks,<br>The Golf Fellowship</p>",
                    "See you today at {course} for {event_name}!",
                ),
                (
                    "Post-Event Results", "email",
                    "Results — {event_name}",
                    "<p>Hi {player_name},</p>"
                    "<p>Results are in for <strong>{event_name}</strong> at "
                    "<strong>{course}</strong>!</p>"
                    "<p>Thanks for playing,<br>The Golf Fellowship</p>",
                    None,
                ),
            ]
            for name, channel, subj, html, sms in system_templates:
                conn.execute(
                    "INSERT INTO message_templates (name, channel, subject, html_body, sms_body, is_system) "
                    "VALUES (?, ?, ?, ?, ?, 1)",
                    (name, channel, subj, html, sms),
                )

        # Backfill NULL/empty values in critical columns
        conn.execute("UPDATE items SET customer = '(Unknown)' WHERE customer IS NULL OR customer = ''")
        conn.execute("UPDATE items SET item_name = '(Unknown Item)' WHERE item_name IS NULL OR item_name = ''")

        # Enforce NOT NULL on critical columns via triggers (SQLite doesn't
        # support ALTER TABLE ADD CONSTRAINT).  The triggers reject inserts
        # and updates that would set these columns to NULL or empty string.
        for col, label in [("customer", "customer"), ("item_name", "item_name")]:
            conn.execute(f"""
                CREATE TRIGGER IF NOT EXISTS trg_items_{col}_not_null_insert
                BEFORE INSERT ON items
                WHEN NEW.{col} IS NULL OR NEW.{col} = ''
                BEGIN
                    SELECT RAISE(ABORT, '{label} cannot be NULL or empty');
                END
            """)
            conn.execute(f"""
                CREATE TRIGGER IF NOT EXISTS trg_items_{col}_not_null_update
                BEFORE UPDATE OF {col} ON items
                WHEN NEW.{col} IS NULL OR NEW.{col} = ''
                BEGIN
                    SELECT RAISE(ABORT, '{label} cannot be NULL or empty');
                END
            """)

        # Repair: clear matched_item_id on RSVPs that point to wrong items.
        # Two cases:
        #   1. Points to non-event items (Customer Entry, RSVP Import, etc.)
        #   2. Points to an item whose item_name doesn't match the RSVP's
        #      matched_event (e.g. linked to a customer's item for event Y
        #      but the RSVP is for event X)
        try:
            # Case 1: non-event merchant items
            r1 = conn.execute(
                """UPDATE rsvps SET matched_item_id = NULL
                   WHERE matched_item_id IS NOT NULL
                     AND matched_item_id IN (
                         SELECT id FROM items
                         WHERE merchant IN ('Customer Entry', 'RSVP Import',
                                            'RSVP Email Link', 'Roster Import')
                     )"""
            ).rowcount

            # Case 2: matched_item_id points to item for a different event.
            # An RSVP for event X should only have matched_item_id pointing
            # to an item whose item_name = X or is an alias of X.
            r2 = conn.execute(
                """UPDATE rsvps SET matched_item_id = NULL
                   WHERE id IN (
                       SELECT r.id FROM rsvps r
                       JOIN items i ON i.id = r.matched_item_id
                       WHERE r.matched_item_id IS NOT NULL
                         AND r.matched_event IS NOT NULL
                         AND i.item_name != r.matched_event
                         AND i.item_name NOT IN (
                             SELECT alias_name FROM event_aliases
                             WHERE canonical_event_name = r.matched_event
                         )
                   )"""
            ).rowcount

            repaired = r1 + r2
            if repaired:
                logger.info("Repaired %d RSVPs with bad matched_item_id (%d non-event, %d wrong-event)",
                            repaired, r1, r2)
        except sqlite3.OperationalError:
            pass  # rsvps table may not exist yet on first run

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
    with managed_connection(db_path) as conn:
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

        _exclude = """WHERE merchant NOT IN ('Roster Import', 'Customer Entry',
                                              'RSVP Import', 'RSVP Email Link')"""
        row = conn.execute(
            f"""
            SELECT
                COUNT(*)                 AS total_items,
                COUNT(DISTINCT order_id) AS total_orders,
                MIN(order_date)          AS earliest,
                MAX(order_date)          AS latest
            FROM items {_exclude}
            """
        ).fetchone()

        # Sum item prices (strip $ and commas)
        price_rows = conn.execute(f"SELECT item_price FROM items {_exclude}").fetchall()

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
        _exclude = """WHERE merchant NOT IN ('Roster Import', 'Customer Entry',
                                              'RSVP Import', 'RSVP Email Link')"""

        # Stats
        row = conn.execute(
            f"""
            SELECT
                COUNT(*)                 AS total_items,
                COUNT(DISTINCT order_id) AS total_orders,
                COUNT(DISTINCT customer) AS unique_customers,
                MIN(order_date)          AS earliest,
                MAX(order_date)          AS latest
            FROM items {_exclude}
            """
        ).fetchone()

        # Most recent items
        recent = conn.execute(
            f"SELECT * FROM items {_exclude} ORDER BY created_at DESC, id DESC LIMIT ?",
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
    "roster import", "rsvp import", "rsvp email link", "customer entry",
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
            # Case-insensitive duplicate check
            existing = conn.execute(
                "SELECT id FROM events WHERE LOWER(item_name) = LOWER(?)", (name,)
            ).fetchone()
            if existing:
                continue
            try:
                conn.execute(
                    """INSERT INTO events (item_name, event_date, course, city, event_type)
                       VALUES (?, ?, ?, ?, 'event')""",
                    (name, item["event_date"], item["course"], item["city"]),
                )
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
                 AND i.merchant NOT IN ('Roster Import', 'Customer Entry',
                                        'RSVP Import', 'RSVP Email Link')
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


def update_customer_info(customer_name: str, fields: dict,
                        db_path: str | Path | None = None) -> int:
    """Update personal info fields across all items for a customer.

    Only updates columns in the provided dict. Returns count of rows updated.
    Validates email/phone. Syncs display name from first/last if changed.
    """
    allowed = {"customer_email", "customer_phone", "chapter", "handicap",
               "date_of_birth", "shirt_size", "customer",
               "first_name", "last_name", "middle_name", "suffix"}
    safe = {k: v for k, v in fields.items() if k in allowed}
    if not safe:
        return 0

    # Validate email and phone if provided
    if "customer_email" in safe and safe["customer_email"]:
        valid = validate_email(safe["customer_email"])
        if valid is None:
            raise ValueError(f"Invalid email: {safe['customer_email']}")
        safe["customer_email"] = valid
    if "customer_phone" in safe and safe["customer_phone"]:
        valid = validate_phone(safe["customer_phone"])
        if valid is None:
            raise ValueError(f"Invalid phone: {safe['customer_phone']}")
        safe["customer_phone"] = valid

    # If first/last name changed, sync the display name
    if any(k in safe for k in ("first_name", "last_name", "suffix")):
        display = " ".join(filter(None, [
            safe.get("first_name", ""), safe.get("last_name", ""),
            safe.get("suffix", ""),
        ]))
        if display:
            safe["customer"] = display

    _validate_column_names(list(safe))
    set_clause = ", ".join(f"{col} = ?" for col in safe)
    values = list(safe.values()) + [customer_name]

    with _connect(db_path) as conn:
        cursor = conn.execute(
            f"UPDATE items SET {set_clause} WHERE customer = ? COLLATE NOCASE",
            values,
        )
        # Update alias references if display name changed
        if "customer" in safe and safe["customer"] != customer_name:
            conn.execute(
                "UPDATE customer_aliases SET customer_name = ? WHERE customer_name = ? COLLATE NOCASE",
                (safe["customer"], customer_name),
            )
        conn.commit()
        return cursor.rowcount


def create_customer(name: str, email: str = "", phone: str = "",
                    chapter: str = "", first_name: str = "",
                    last_name: str = "", middle_name: str = "",
                    suffix: str = "",
                    db_path: str | Path | None = None) -> dict | None:
    """Create a standalone customer by inserting a minimal item row.

    Parses name into first/last parts via AI if not provided explicitly.
    Validates email/phone. Returns the new item dict or None if already exists.
    """
    name = (name or "").strip()
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()

    # Build display name from parts if not provided
    if not name and (first_name or last_name):
        name = " ".join(filter(None, [first_name, last_name, (suffix or "").strip()]))
    if not name:
        return None

    # Parse name into parts if not provided
    if not first_name and not last_name:
        parsed = parse_names_ai([name])
        if parsed:
            first_name = parsed[0].get("first_name") or ""
            last_name = parsed[0].get("last_name") or ""
            middle_name = parsed[0].get("middle_name") or middle_name or ""
            suffix = parsed[0].get("suffix") or suffix or ""

    # Validate email/phone
    if email:
        email = validate_email(email) or ""
    if phone:
        phone = validate_phone(phone) or ""

    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM items WHERE customer = ? COLLATE NOCASE LIMIT 1",
            (name,),
        ).fetchone()
        if existing:
            return None

        today = datetime.now().strftime("%Y-%m-%d")
        new_values = {c: None for c in ITEM_COLUMNS}
        new_values["customer"] = name
        new_values["first_name"] = first_name or None
        new_values["last_name"] = last_name or None
        new_values["middle_name"] = middle_name or None
        new_values["suffix"] = suffix or None
        new_values["customer_email"] = email or None
        new_values["customer_phone"] = phone or None
        new_values["chapter"] = chapter or None
        new_values["merchant"] = "Customer Entry"
        new_values["item_name"] = "Customer Entry"
        new_values["order_date"] = today
        new_values["email_uid"] = f"customer_entry_{name}_{today}"
        new_values["item_index"] = 0

        cols = ", ".join(ITEM_COLUMNS)
        placeholders = ", ".join(["?"] * len(ITEM_COLUMNS))
        cursor = conn.execute(
            f"INSERT INTO items ({cols}) VALUES ({placeholders})",
            tuple(new_values.get(c) for c in ITEM_COLUMNS),
        )
        new_id = cursor.lastrowid
        conn.commit()

        new_values["id"] = new_id
        logger.info("Created customer %s (id=%d)", name, new_id)
        return new_values


def create_customer_from_rsvp(
    name: str, email: str, rsvp_event: str = "",
    db_path: str | Path | None = None,
) -> dict:
    """Create a customer entry from an unmatched RSVP.

    If a customer with this email already exists, returns info about them
    instead of creating a duplicate (for the frontend to offer merge).

    Does NOT set matched_item_id on RSVPs — that field links RSVPs to
    event-specific registrations, not to generic customer entries.
    The has_player_card flag will resolve to True automatically because
    the customer's email now exists in the items table.

    Returns {status: "created"|"exists"|"linked", customer: {...}, item_id: int}.
    """
    name = (name or "").strip()
    email = (email or "").strip().lower()
    if not name:
        raise ValueError("Customer name is required")

    with _connect(db_path) as conn:
        # Check if email already belongs to an existing customer
        if email:
            existing = conn.execute(
                """SELECT id, customer FROM items
                   WHERE LOWER(customer_email) = ?
                     AND customer IS NOT NULL AND customer != ''
                   ORDER BY order_date DESC LIMIT 1""",
                (email,),
            ).fetchone()
            if existing:
                return {
                    "status": "exists",
                    "customer": {"id": existing["id"], "name": existing["customer"]},
                    "item_id": existing["id"],
                }

        # Check by name (case-insensitive)
        by_name = conn.execute(
            "SELECT id, customer, customer_email FROM items WHERE customer = ? COLLATE NOCASE LIMIT 1",
            (name,),
        ).fetchone()
        if by_name:
            item_id = by_name["id"]
            # If existing customer has no email, set it so has_player_card resolves
            if email and not (by_name["customer_email"] or "").strip():
                conn.execute(
                    "UPDATE items SET customer_email = ? WHERE customer = ? COLLATE NOCASE",
                    (email, name),
                )
        else:
            # Create new customer entry with parsed name parts
            parsed = parse_names_ai([name])
            parts = parsed[0] if parsed else {}

            today = datetime.now().strftime("%Y-%m-%d")
            new_values = {c: None for c in ITEM_COLUMNS}
            new_values["customer"] = name
            new_values["first_name"] = parts.get("first_name") or None
            new_values["last_name"] = parts.get("last_name") or None
            new_values["middle_name"] = parts.get("middle_name") or None
            new_values["suffix"] = parts.get("suffix") or None
            new_values["customer_email"] = email or None
            new_values["merchant"] = "RSVP Import"
            new_values["item_name"] = "RSVP Import"
            new_values["order_date"] = today
            new_values["email_uid"] = f"rsvp_import_{email or name}_{today}"
            new_values["item_index"] = 0

            cols = ", ".join(ITEM_COLUMNS)
            placeholders = ", ".join(["?"] * len(ITEM_COLUMNS))
            cursor = conn.execute(
                f"INSERT INTO items ({cols}) VALUES ({placeholders})",
                tuple(new_values.get(c) for c in ITEM_COLUMNS),
            )
            item_id = cursor.lastrowid
            logger.info("Created customer from RSVP: %s <%s> (id=%d)", name, email, item_id)

        conn.commit()

        return {
            "status": "created" if not by_name else "linked",
            "customer": {"id": item_id, "name": name},
            "item_id": item_id,
        }


def link_rsvp_to_customer(
    rsvp_email: str, target_customer_name: str,
    rsvp_player_name: str = "",
    db_path: str | Path | None = None,
) -> dict:
    """Link an unmatched RSVP email to an existing customer.

    Updates the customer's email if they don't have one so that
    has_player_card resolves to True for RSVPs from this address.
    Adds the RSVP email as a customer alias so future matching works.
    Updates RSVPs from this email to show the full customer name.

    Does NOT set matched_item_id on RSVPs — that field links RSVPs to
    event-specific registrations, not to generic customer entries.

    Returns {linked: bool, customer_name: str}.
    """
    rsvp_email = (rsvp_email or "").strip().lower()
    target_customer_name = (target_customer_name or "").strip()
    if not rsvp_email or not target_customer_name:
        raise ValueError("Both rsvp_email and target_customer_name are required")

    with _connect(db_path) as conn:
        # Find target customer's item
        target = conn.execute(
            """SELECT id, customer_email FROM items
               WHERE customer = ? COLLATE NOCASE
               ORDER BY order_date DESC LIMIT 1""",
            (target_customer_name,),
        ).fetchone()
        if not target:
            raise ValueError(f"Customer '{target_customer_name}' not found")

        existing_email = (target["customer_email"] or "").strip().lower()

        # If target customer has no email, set it so has_player_card resolves
        if not existing_email:
            conn.execute(
                "UPDATE items SET customer_email = ? WHERE customer = ? COLLATE NOCASE",
                (rsvp_email, target_customer_name),
            )
            logger.info("Set email <%s> on customer %s", rsvp_email, target_customer_name)
        elif existing_email != rsvp_email:
            # Customer has a DIFFERENT email — create a secondary item entry
            # with the RSVP email so has_player_card can find them
            today = datetime.now().strftime("%Y-%m-%d")
            new_values = {c: None for c in ITEM_COLUMNS}
            new_values["customer"] = target_customer_name
            new_values["customer_email"] = rsvp_email
            new_values["merchant"] = "RSVP Email Link"
            new_values["item_name"] = "RSVP Email Link"
            new_values["order_date"] = today
            new_values["email_uid"] = f"rsvp_link_{rsvp_email}_{today}"
            new_values["item_index"] = 0

            cols = ", ".join(ITEM_COLUMNS)
            placeholders = ", ".join(["?"] * len(ITEM_COLUMNS))
            conn.execute(
                f"INSERT INTO items ({cols}) VALUES ({placeholders})",
                tuple(new_values.get(c) for c in ITEM_COLUMNS),
            )
            logger.info("Linked RSVP email <%s> to customer %s (secondary email entry)",
                         rsvp_email, target_customer_name)

        # Add the RSVP email as an alias so future imports/matching find this customer
        if rsvp_email and rsvp_email != existing_email:
            existing_alias = conn.execute(
                """SELECT id FROM customer_aliases
                   WHERE customer_name = ? COLLATE NOCASE AND alias_type = 'email'
                     AND LOWER(alias_value) = ?""",
                (target_customer_name, rsvp_email),
            ).fetchone()
            if not existing_alias:
                conn.execute(
                    "INSERT INTO customer_aliases (customer_name, alias_type, alias_value) VALUES (?, 'email', ?)",
                    (target_customer_name, rsvp_email),
                )
                logger.info("Added alias email <%s> for customer %s",
                             rsvp_email, target_customer_name)

        # Update RSVPs from this email to show the full customer name
        rsvp_player_name = (rsvp_player_name or "").strip()
        if rsvp_player_name and rsvp_player_name.lower() != target_customer_name.lower():
            conn.execute(
                "UPDATE rsvps SET player_name = ? WHERE LOWER(player_email) = ?",
                (target_customer_name, rsvp_email),
            )
            # Add the short RSVP name as an alias too
            existing_name_alias = conn.execute(
                """SELECT id FROM customer_aliases
                   WHERE customer_name = ? COLLATE NOCASE AND alias_type = 'name'
                     AND LOWER(alias_value) = ?""",
                (target_customer_name, rsvp_player_name.lower()),
            ).fetchone()
            if not existing_name_alias:
                conn.execute(
                    "INSERT INTO customer_aliases (customer_name, alias_type, alias_value) VALUES (?, 'name', ?)",
                    (target_customer_name, rsvp_player_name),
                )
                logger.info("Added alias name '%s' for customer %s",
                             rsvp_player_name, target_customer_name)

        conn.commit()
        return {"linked": True, "customer_name": target_customer_name}


def import_roster(rows: list[dict], db_path: str | Path | None = None) -> dict:
    """Bulk-import customer rows from a roster spreadsheet.

    Each dict should have 'customer' (required, OR first_name+last_name) plus
    optional fields like customer_email, customer_phone, chapter, handicap, etc.

    Name handling:
    - If first_name/last_name are provided directly, uses them as-is.
    - If only 'customer' (full name string), runs AI name parsing to split into parts.
    - Reconstructs display name as "First Last" (+ suffix) from parsed parts.

    Matching: finds existing customers by name (case-insensitive) first, then
    by alias name, then falls back to email matching, then alias email matching.

    Aliases: alias_name and alias_email fields are stored in customer_aliases table.

    Validation: emails are validated, phones are normalized to (XXX) XXX-XXXX.

    Returns { created, updated, skipped, errors, validation_warnings }.
    """
    allowed_fields = set(ITEM_COLUMNS) - {
        "email_uid", "item_index", "merchant", "order_id", "order_date",
        "total_amount", "item_name", "item_price", "quantity",
        "subject", "from_addr", "transaction_status", "credit_note",
        "transferred_from_id", "transferred_to_id",
        "wd_reason", "wd_note", "wd_credits", "credit_amount",
    }
    result = {"created": 0, "updated": 0, "skipped": 0, "errors": [],
              "validation_warnings": []}
    today = datetime.now().strftime("%Y-%m-%d")

    # --- Phase 1: resolve names via AI parsing if needed ---
    needs_parsing = []
    for i, row in enumerate(rows):
        has_parts = (row.get("first_name") or "").strip() and (row.get("last_name") or "").strip()
        has_full = (row.get("customer") or "").strip()
        if has_full and not has_parts:
            needs_parsing.append((i, row["customer"].strip()))

    if needs_parsing:
        logger.info("Parsing %d names via AI...", len(needs_parsing))
        raw_names = [n for _, n in needs_parsing]
        parsed = parse_names_ai(raw_names)
        for (idx, _raw), parts in zip(needs_parsing, parsed):
            rows[idx]["first_name"] = parts.get("first_name") or ""
            rows[idx]["last_name"] = parts.get("last_name") or ""
            rows[idx]["middle_name"] = parts.get("middle_name") or ""
            rows[idx]["suffix"] = parts.get("suffix") or ""
            # Rebuild display name from parsed parts
            display = " ".join(filter(None, [
                parts.get("first_name"), parts.get("last_name"),
                parts.get("suffix"),
            ]))
            if display:
                rows[idx]["customer"] = display

    # --- Phase 2: validate and normalize ---
    for i, row in enumerate(rows):
        email = row.get("customer_email", "")
        if email:
            valid = validate_email(email)
            if valid is None:
                result["validation_warnings"].append(
                    f"Row {i+1}: invalid email '{email}' — skipped email field")
                row["customer_email"] = ""
            else:
                row["customer_email"] = valid
        phone = row.get("customer_phone", "")
        if phone:
            valid = validate_phone(phone)
            if valid is None:
                result["validation_warnings"].append(
                    f"Row {i+1}: invalid phone '{phone}' — skipped phone field")
                row["customer_phone"] = ""
            else:
                row["customer_phone"] = valid

    # --- Phase 3: deduplicate within the spreadsheet ---
    seen_names = {}  # lowercase name → first row index
    seen_emails = {}  # lowercase email → first row index
    for i, row in enumerate(rows):
        name = (row.get("customer") or "").strip().lower()
        email = (row.get("customer_email") or "").strip().lower()
        if name and name in seen_names:
            # Mark as duplicate within spreadsheet — will be merged into first occurrence
            row["_dedup_target_idx"] = seen_names[name]
        elif email and email in seen_emails:
            row["_dedup_target_idx"] = seen_emails[email]
        else:
            if name:
                seen_names[name] = i
            if email:
                seen_emails[email] = i

    with _connect(db_path) as conn:
        # Build alias lookup for matching
        alias_name_map = {}  # lowercase alias → customer_name
        alias_email_map = {}  # lowercase alias → customer_name
        for arow in conn.execute("SELECT customer_name, alias_type, alias_value FROM customer_aliases").fetchall():
            val = (arow["alias_value"] or "").strip().lower()
            if arow["alias_type"] == "name":
                alias_name_map[val] = arow["customer_name"]
            elif arow["alias_type"] == "email":
                alias_email_map[val] = arow["customer_name"]

        for i, row in enumerate(rows):
            # Skip spreadsheet-internal duplicates (already handled by first occurrence)
            if "_dedup_target_idx" in row:
                result["skipped"] += 1
                continue

            name = (row.get("customer") or "").strip()
            if not name:
                # Try to build name from first/last
                first = (row.get("first_name") or "").strip()
                last = (row.get("last_name") or "").strip()
                if first or last:
                    name = " ".join(filter(None, [first, last, (row.get("suffix") or "").strip()]))
                    row["customer"] = name
            if not name:
                result["skipped"] += 1
                continue

            email = (row.get("customer_email") or "").strip().lower()

            # 1) Try matching by name (case-insensitive)
            existing = conn.execute(
                "SELECT id, customer FROM items WHERE customer = ? COLLATE NOCASE LIMIT 1",
                (name,),
            ).fetchone()

            # 2) Try matching by alias name
            if not existing:
                alias_target = alias_name_map.get(name.lower())
                if alias_target:
                    existing = conn.execute(
                        "SELECT id, customer FROM items WHERE customer = ? COLLATE NOCASE LIMIT 1",
                        (alias_target,),
                    ).fetchone()

            # 3) Try matching by email
            if not existing and email:
                existing = conn.execute(
                    """SELECT id, customer FROM items
                       WHERE LOWER(customer_email) = ?
                         AND customer IS NOT NULL AND customer != ''
                       ORDER BY order_date DESC LIMIT 1""",
                    (email,),
                ).fetchone()

            # 4) Try matching by alias email
            if not existing and email:
                alias_target = alias_email_map.get(email)
                if alias_target:
                    existing = conn.execute(
                        "SELECT id, customer FROM items WHERE customer = ? COLLATE NOCASE LIMIT 1",
                        (alias_target,),
                    ).fetchone()

            safe = {k: v for k, v in row.items()
                    if k in allowed_fields and k != "customer" and v
                    and not k.startswith("_")}

            # Extract alias fields (not stored in items table)
            alias_names = [v.strip() for v in (row.get("alias_name") or "").split(",") if v.strip()]
            alias_emails = [v.strip().lower() for v in (row.get("alias_email") or "").split(",") if v.strip()]

            if existing:
                existing_name = existing["customer"]
                if safe:
                    _validate_column_names(list(safe))
                    current = conn.execute(
                        """SELECT * FROM items
                           WHERE customer = ? COLLATE NOCASE
                           ORDER BY order_date DESC LIMIT 1""",
                        (existing_name,),
                    ).fetchone()
                    blanks = {}
                    if current:
                        for col, val in safe.items():
                            existing_val = current[col] if col in current.keys() else None
                            if not existing_val or not str(existing_val).strip():
                                blanks[col] = val
                    else:
                        blanks = safe

                    if blanks:
                        set_clause = ", ".join(f"{col} = ?" for col in blanks)
                        values = list(blanks.values()) + [existing_name]
                        conn.execute(
                            f"UPDATE items SET {set_clause} WHERE customer = ? COLLATE NOCASE",
                            values,
                        )
                        result["updated"] += 1
                    else:
                        result["skipped"] += 1
                else:
                    result["skipped"] += 1

                # Store aliases for existing customer
                _save_customer_aliases(conn, existing_name, alias_names, alias_emails)
            else:
                # Create new customer entry
                new_values = {c: None for c in ITEM_COLUMNS}
                new_values["customer"] = name
                new_values["first_name"] = (row.get("first_name") or "").strip() or None
                new_values["last_name"] = (row.get("last_name") or "").strip() or None
                new_values["middle_name"] = (row.get("middle_name") or "").strip() or None
                new_values["suffix"] = (row.get("suffix") or "").strip() or None
                new_values["merchant"] = "Roster Import"
                new_values["item_name"] = "Roster Import"
                new_values["order_date"] = today
                new_values["email_uid"] = f"roster_import_{name}_{today}"
                new_values["item_index"] = 0
                for k, v in safe.items():
                    new_values[k] = v

                cols = ", ".join(ITEM_COLUMNS)
                placeholders = ", ".join(["?"] * len(ITEM_COLUMNS))
                conn.execute(
                    f"INSERT INTO items ({cols}) VALUES ({placeholders})",
                    tuple(new_values.get(c) for c in ITEM_COLUMNS),
                )
                result["created"] += 1

                # Store aliases for new customer
                _save_customer_aliases(conn, name, alias_names, alias_emails)

        conn.commit()
    logger.info("Roster import: %d created, %d updated, %d skipped",
                result["created"], result["updated"], result["skipped"])
    return result


def _save_customer_aliases(conn: sqlite3.Connection, customer_name: str,
                           alias_names: list[str], alias_emails: list[str]) -> None:
    """Insert alias names/emails for a customer, skipping duplicates."""
    for alias in alias_names:
        if not alias:
            continue
        existing = conn.execute(
            """SELECT id FROM customer_aliases
               WHERE customer_name = ? COLLATE NOCASE AND alias_type = 'name'
                 AND LOWER(alias_value) = ?""",
            (customer_name, alias.lower()),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO customer_aliases (customer_name, alias_type, alias_value) VALUES (?, 'name', ?)",
                (customer_name, alias),
            )

    for alias in alias_emails:
        if not alias:
            continue
        existing = conn.execute(
            """SELECT id FROM customer_aliases
               WHERE customer_name = ? COLLATE NOCASE AND alias_type = 'email'
                 AND LOWER(alias_value) = ?""",
            (customer_name, alias.lower()),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO customer_aliases (customer_name, alias_type, alias_value) VALUES (?, 'email', ?)",
                (customer_name, alias),
            )


def get_customer_aliases(customer_name: str,
                         db_path: str | Path | None = None) -> list[dict]:
    """Return all aliases for a customer."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, alias_type, alias_value FROM customer_aliases WHERE customer_name = ? COLLATE NOCASE ORDER BY alias_type, alias_value",
            (customer_name,),
        ).fetchall()
        return [{"id": r["id"], "type": r["alias_type"], "value": r["alias_value"]} for r in rows]


def add_customer_alias(customer_name: str, alias_type: str, alias_value: str,
                       db_path: str | Path | None = None) -> dict:
    """Add an alias (name or email) for a customer."""
    if alias_type not in ("name", "email"):
        raise ValueError("alias_type must be 'name' or 'email'")
    alias_value = alias_value.strip()
    if not alias_value:
        raise ValueError("alias_value cannot be empty")
    if alias_type == "email":
        alias_value = alias_value.lower()
    with _connect(db_path) as conn:
        existing = conn.execute(
            """SELECT id FROM customer_aliases
               WHERE customer_name = ? COLLATE NOCASE AND alias_type = ?
                 AND LOWER(alias_value) = ?""",
            (customer_name, alias_type, alias_value.lower()),
        ).fetchone()
        if existing:
            return {"id": existing["id"], "type": alias_type, "value": alias_value, "existed": True}
        cursor = conn.execute(
            "INSERT INTO customer_aliases (customer_name, alias_type, alias_value) VALUES (?, ?, ?)",
            (customer_name, alias_type, alias_value),
        )
        conn.commit()
        return {"id": cursor.lastrowid, "type": alias_type, "value": alias_value, "existed": False}


def delete_customer_alias(alias_id: int, db_path: str | Path | None = None) -> bool:
    """Delete an alias by ID."""
    with _connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM customer_aliases WHERE id = ?", (alias_id,))
        conn.commit()
        return cursor.rowcount > 0


def preview_roster_import(rows: list[dict], db_path: str | Path | None = None) -> dict:
    """Preview a roster import: run AI name parsing + duplicate detection, return enriched rows.

    Returns { rows: [{...original fields + parsed name parts + match_status + match_detail}],
              validation_warnings: [...] }.
    """
    warnings = []

    # AI-parse names that need it
    needs_parsing = []
    for i, row in enumerate(rows):
        has_parts = (row.get("first_name") or "").strip() and (row.get("last_name") or "").strip()
        has_full = (row.get("customer") or "").strip()
        if has_full and not has_parts:
            needs_parsing.append((i, row["customer"].strip()))

    if needs_parsing:
        raw_names = [n for _, n in needs_parsing]
        parsed = parse_names_ai(raw_names)
        for (idx, _raw), parts in zip(needs_parsing, parsed):
            rows[idx]["first_name"] = parts.get("first_name") or ""
            rows[idx]["last_name"] = parts.get("last_name") or ""
            rows[idx]["middle_name"] = parts.get("middle_name") or ""
            rows[idx]["suffix"] = parts.get("suffix") or ""
            display = " ".join(filter(None, [
                parts.get("first_name"), parts.get("last_name"),
                parts.get("suffix"),
            ]))
            if display:
                rows[idx]["_parsed_name"] = display

    # Validate emails/phones
    for i, row in enumerate(rows):
        email = row.get("customer_email", "")
        if email and validate_email(email) is None:
            warnings.append(f"Row {i+1}: invalid email '{email}'")
        phone = row.get("customer_phone", "")
        if phone and validate_phone(phone) is None:
            warnings.append(f"Row {i+1}: invalid phone '{phone}'")

    # Detect duplicates within spreadsheet
    seen_names = {}
    seen_emails = {}
    for i, row in enumerate(rows):
        name = (row.get("_parsed_name") or row.get("customer") or "").strip().lower()
        email = (row.get("customer_email") or "").strip().lower()
        if name and name in seen_names:
            row["_dupe_of_row"] = seen_names[name] + 1  # 1-indexed
        elif email and email in seen_emails:
            row["_dupe_of_row"] = seen_emails[email] + 1
        else:
            if name:
                seen_names[name] = i
            if email:
                seen_emails[email] = i

    # Check against database
    with _connect(db_path) as conn:
        alias_name_map = {}
        alias_email_map = {}
        for arow in conn.execute("SELECT customer_name, alias_type, alias_value FROM customer_aliases").fetchall():
            val = (arow["alias_value"] or "").strip().lower()
            if arow["alias_type"] == "name":
                alias_name_map[val] = arow["customer_name"]
            elif arow["alias_type"] == "email":
                alias_email_map[val] = arow["customer_name"]

        for i, row in enumerate(rows):
            name = (row.get("_parsed_name") or row.get("customer") or "").strip()
            email = (row.get("customer_email") or "").strip().lower()

            if not name and not email:
                row["_match_status"] = "skip"
                continue

            # Exact name match
            match = conn.execute(
                "SELECT customer, customer_email FROM items WHERE customer = ? COLLATE NOCASE LIMIT 1",
                (name,),
            ).fetchone() if name else None

            if match:
                row["_match_status"] = "update"
                row["_match_detail"] = f"Name match: {match['customer']}"
                # Figure out which fields will be filled in
                current = conn.execute(
                    """SELECT * FROM items WHERE customer = ? COLLATE NOCASE
                       ORDER BY order_date DESC LIMIT 1""",
                    (match["customer"],),
                ).fetchone()
                if current:
                    blanks = []
                    for col in ["customer_email", "customer_phone", "chapter",
                                "handicap", "date_of_birth", "shirt_size",
                                "first_name", "last_name"]:
                        cur_val = current[col] if col in current.keys() else None
                        row_val = row.get(col, "")
                        if row_val and (not cur_val or not str(cur_val).strip()):
                            blanks.append(col)
                    if blanks:
                        row["_will_fill"] = blanks
                continue

            # Alias name match
            if name:
                alias_target = alias_name_map.get(name.lower())
                if alias_target:
                    row["_match_status"] = "update"
                    row["_match_detail"] = f"Alias name match → {alias_target}"
                    continue

            # Email match
            if email:
                ematch = conn.execute(
                    """SELECT customer FROM items
                       WHERE LOWER(customer_email) = ?
                         AND customer IS NOT NULL AND customer != ''
                       ORDER BY order_date DESC LIMIT 1""",
                    (email,),
                ).fetchone()
                if ematch:
                    row["_match_status"] = "update"
                    row["_match_detail"] = f"Email match → {ematch['customer']}"
                    continue

                # Alias email match
                alias_target = alias_email_map.get(email)
                if alias_target:
                    row["_match_status"] = "update"
                    row["_match_detail"] = f"Alias email match → {alias_target}"
                    continue

            row["_match_status"] = "new"

    return {"rows": rows, "validation_warnings": warnings}


def add_custom_field(field_name: str, db_path: str | Path | None = None) -> bool:
    """Add a new custom TEXT column to the items table at runtime.

    Validates the name, adds the column via ALTER TABLE, and appends to
    ITEM_COLUMNS so the rest of the app recognises it immediately.
    Returns True if the column was created, False if it already exists.
    """
    field_name = (field_name or "").strip().lower().replace(" ", "_")
    if not _SAFE_COL_RE.match(field_name):
        raise ValueError(f"Invalid field name: {field_name!r}")
    if field_name in ITEM_COLUMNS:
        return False  # already exists

    with _connect(db_path) as conn:
        try:
            conn.execute(f"ALTER TABLE items ADD COLUMN {field_name} TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            return False  # column already exists in DB

    ITEM_COLUMNS.append(field_name)
    logger.info("Added custom field: %s", field_name)
    return True


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

        # Update all source items to the target customer name (case-insensitive match)
        cursor = conn.execute(
            "UPDATE items SET customer = ? WHERE customer = ? COLLATE NOCASE",
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

        # Backfill name parts from source if target lacks them
        target_parts = conn.execute(
            """SELECT first_name, last_name, middle_name, suffix FROM items
               WHERE customer = ? AND first_name IS NOT NULL AND first_name != ''
               ORDER BY order_date DESC LIMIT 1""",
            (target_name,),
        ).fetchone()
        source_parts = conn.execute(
            """SELECT first_name, last_name, middle_name, suffix FROM items
               WHERE customer = ? COLLATE NOCASE AND first_name IS NOT NULL AND first_name != ''
               ORDER BY order_date DESC LIMIT 1""",
            (source_name,),
        ).fetchone()
        if source_parts and not target_parts:
            conn.execute(
                """UPDATE items SET first_name = ?, last_name = ?, middle_name = ?, suffix = ?
                   WHERE customer = ? AND (first_name IS NULL OR first_name = '')""",
                (source_parts["first_name"], source_parts["last_name"],
                 source_parts["middle_name"], source_parts["suffix"], target_name),
            )

        # Merge aliases: move source's aliases to target, add source name as alias
        conn.execute(
            "UPDATE customer_aliases SET customer_name = ? WHERE customer_name = ? COLLATE NOCASE",
            (target_name, source_name),
        )
        # Add the source's name as an alias of the target (for future matching)
        existing_alias = conn.execute(
            """SELECT id FROM customer_aliases
               WHERE customer_name = ? COLLATE NOCASE AND alias_type = 'name'
                 AND LOWER(alias_value) = ?""",
            (target_name, source_name.lower()),
        ).fetchone()
        if not existing_alias:
            conn.execute(
                "INSERT INTO customer_aliases (customer_name, alias_type, alias_value) VALUES (?, 'name', ?)",
                (target_name, source_name),
            )
        # If source had a different email, add it as alias email
        source_email = (source_row["customer_email"] if source_row else "") or ""
        target_email = (target_row["customer_email"] if target_row else "") or ""
        if source_email and source_email.lower() != target_email.lower():
            existing_alias = conn.execute(
                """SELECT id FROM customer_aliases
                   WHERE customer_name = ? COLLATE NOCASE AND alias_type = 'email'
                     AND LOWER(alias_value) = ?""",
                (target_name, source_email.lower()),
            ).fetchone()
            if not existing_alias:
                conn.execute(
                    "INSERT INTO customer_aliases (customer_name, alias_type, alias_value) VALUES (?, 'email', ?)",
                    (target_name, source_email),
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


def wd_item(
    item_id: int,
    note: str = "",
    credits: dict | None = None,
    credit_amount: str = "",
    db_path: str | Path | None = None,
) -> bool:
    """Mark an item as WD (withdrawn). Player stays on list but may be
    excluded from counts based on which credit components are selected.

    ``credits`` is a dict like {"included_games": 14, "net_games": 30, ...}.
    ``credit_amount`` is the formatted total credit string, e.g. "$59.00".
    """
    import json as _json

    credits_json = _json.dumps(credits) if credits else None
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """UPDATE items
               SET transaction_status = 'wd',
                   wd_reason = 'WD',
                   wd_note = ?,
                   wd_credits = ?,
                   credit_amount = ?
               WHERE id = ? AND COALESCE(transaction_status, 'active') = 'active'""",
            (note or "", credits_json or "", credit_amount or "", item_id),
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
    Reverse a credit, transfer, or WD.

    For credits: simply resets to active.
    For transfers: resets original to active and deletes the transferred-to item.
    For WD: resets to active and clears WD fields.
    """
    with _connect(db_path) as conn:
        item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            return False
        item = dict(item)

        status = item.get("transaction_status")
        if status not in ("credited", "transferred", "wd"):
            return False

        if status == "transferred" and item.get("transferred_to_id"):
            # Delete the destination item
            conn.execute("DELETE FROM items WHERE id = ?", (item["transferred_to_id"],))

        # Reset original
        conn.execute(
            """UPDATE items
               SET transaction_status = 'active', credit_note = NULL,
                   transferred_to_id = NULL,
                   wd_reason = NULL, wd_note = NULL, wd_credits = NULL, credit_amount = NULL
               WHERE id = ?""",
            (item_id,),
        )
        conn.commit()
        return True


def create_event(item_name: str, event_date: str = None, course: str = None,
                 city: str = None, db_path: str | Path | None = None) -> dict | None:
    """Manually create a new event. Returns the event dict or None if duplicate (case-insensitive)."""
    with _connect(db_path) as conn:
        # Case-insensitive duplicate check
        existing = conn.execute(
            "SELECT id FROM events WHERE LOWER(item_name) = LOWER(?)", (item_name,)
        ).fetchone()
        if existing:
            return None
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
    Skips duplicates (case-insensitive). Returns {"inserted": N, "skipped": N}.
    """
    with _connect(db_path) as conn:
        inserted = 0
        skipped = 0
        for ev in events:
            # Case-insensitive duplicate check
            existing = conn.execute(
                "SELECT id FROM events WHERE LOWER(item_name) = LOWER(?)",
                (ev["item_name"],)
            ).fetchone()
            if existing:
                skipped += 1
                logger.debug("Duplicate event skipped during seed: %s", ev.get("item_name"))
                continue
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
    import time as _time

    with _connect(db_path) as conn:

        # Look up the event for date/course/city
        event = conn.execute(
            "SELECT * FROM events WHERE item_name = ?", (event_name,)
        ).fetchone()
        event = dict(event) if event else {}

        uid = f"manual-{mode}-{int(_time.time() * 1000)}"

        new_values = {col: None for col in ITEM_COLUMNS}
        new_values["email_uid"] = uid
        new_values["item_index"] = 0
        new_values["customer"] = customer
        new_values["customer_email"] = customer_email or None
        new_values["customer_phone"] = customer_phone or None
        new_values["item_name"] = event_name
        new_values["order_date"] = datetime.now().strftime("%Y-%m-%d")
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


def get_all_rsvps_bulk(db_path: str | Path | None = None) -> dict:
    """Return latest RSVP per player per event, grouped by event name.

    Also includes all rsvp_overrides and rsvp_email_overrides so the
    frontend can compute accurate player counts without per-event fetches.

    Returns {
        rsvps: {event_name: [rsvp, ...]},
        overrides: {event_name: {item_id: status, ...}},
        email_overrides: {event_name: {email: status, ...}},
    }
    """
    with _connect(db_path) as conn:
        # Latest RSVP per player per event
        rows = conn.execute(
            """SELECT r1.*
               FROM rsvps r1
               INNER JOIN (
                   SELECT matched_event, player_email, MAX(received_at) AS max_date
                   FROM rsvps
                   WHERE matched_event IS NOT NULL AND matched_event != ''
                     AND player_email IS NOT NULL AND player_email != ''
                   GROUP BY matched_event, player_email
               ) r2 ON r1.matched_event = r2.matched_event
                    AND r1.player_email = r2.player_email
                    AND r1.received_at = r2.max_date
               ORDER BY r1.matched_event, r1.player_name ASC"""
        ).fetchall()

        # Resolve player names from items table (bulk)
        emails = {(r["player_email"] or "").strip().lower() for r in rows if r["player_email"]}
        name_map = {}
        if emails:
            placeholders = ",".join("?" * len(emails))
            cards = conn.execute(
                f"""SELECT LOWER(customer_email) as email, customer
                    FROM items
                    WHERE LOWER(customer_email) IN ({placeholders})
                      AND customer IS NOT NULL AND customer != ''
                    ORDER BY order_date DESC""",
                list(emails),
            ).fetchall()
            for c in cards:
                if c["email"] not in name_map:
                    name_map[c["email"]] = c["customer"]

        rsvps_by_event = {}
        for r in rows:
            rsvp = dict(r)
            email = (rsvp.get("player_email") or "").strip().lower()
            rsvp["resolved_name"] = name_map.get(email, rsvp.get("player_name"))
            rsvp["has_player_card"] = email in name_map
            evt = rsvp.get("matched_event") or ""
            rsvps_by_event.setdefault(evt, []).append(rsvp)

        # All overrides by event
        ov_rows = conn.execute("SELECT item_id, event_name, status FROM rsvp_overrides").fetchall()
        overrides = {}
        for r in ov_rows:
            overrides.setdefault(r["event_name"], {})[r["item_id"]] = r["status"]

        # All email overrides by event
        eov_rows = conn.execute("SELECT player_email, event_name, status FROM rsvp_email_overrides").fetchall()
        email_overrides = {}
        for r in eov_rows:
            email_overrides.setdefault(r["event_name"], {})[r["player_email"]] = r["status"]

        return {
            "rsvps": rsvps_by_event,
            "overrides": overrides,
            "email_overrides": email_overrides,
        }


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


# ---------------------------------------------------------------------------
# Messaging — templates & send log
# ---------------------------------------------------------------------------


def get_message_templates(db_path: str | Path | None = None) -> list[dict]:
    """Return all message templates, system templates first."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM message_templates ORDER BY is_system DESC, name ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_message_template(template_id: int, db_path: str | Path | None = None) -> dict | None:
    """Return a single template by ID."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM message_templates WHERE id = ?", (template_id,)
        ).fetchone()
        return dict(row) if row else None


def create_message_template(data: dict, db_path: str | Path | None = None) -> dict:
    """Create a new message template. Returns the created template."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO message_templates (name, channel, subject, html_body, sms_body) "
            "VALUES (?, ?, ?, ?, ?)",
            (data["name"], data.get("channel", "email"), data.get("subject"),
             data.get("html_body"), data.get("sms_body")),
        )
        conn.commit()
        return dict(conn.execute(
            "SELECT * FROM message_templates WHERE id = ?", (cur.lastrowid,)
        ).fetchone())


def update_message_template(template_id: int, data: dict, db_path: str | Path | None = None) -> dict | None:
    """Update a message template. Cannot edit system template names. Returns updated template."""
    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM message_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not existing:
            return None
        fields = []
        values = []
        for col in ("name", "channel", "subject", "html_body", "sms_body"):
            if col in data:
                if col == "name" and existing["is_system"]:
                    continue
                fields.append(f"{col} = ?")
                values.append(data[col])
        if not fields:
            return dict(existing)
        fields.append("updated_at = datetime('now')")
        values.append(template_id)
        conn.execute(
            f"UPDATE message_templates SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
        return dict(conn.execute(
            "SELECT * FROM message_templates WHERE id = ?", (template_id,)
        ).fetchone())


def delete_message_template(template_id: int, db_path: str | Path | None = None) -> bool:
    """Delete a non-system template. Returns True if deleted."""
    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT is_system FROM message_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not existing or existing["is_system"]:
            return False
        conn.execute("DELETE FROM message_templates WHERE id = ?", (template_id,))
        conn.commit()
        return True


def log_message(data: dict, db_path: str | Path | None = None) -> int:
    """Log a sent message. Returns the new log entry ID."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO message_log "
            "(event_name, template_id, channel, recipient_name, recipient_address, "
            " subject, body_preview, status, error_message, sent_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data.get("event_name"),
                data.get("template_id"),
                data["channel"],
                data.get("recipient_name"),
                data["recipient_address"],
                data.get("subject"),
                data.get("body_preview"),
                data.get("status", "sent"),
                data.get("error_message"),
                data.get("sent_by"),
            ),
        )
        conn.commit()
        return cur.lastrowid


def get_message_log(event_name: str | None = None, limit: int = 200,
                    db_path: str | Path | None = None) -> list[dict]:
    """Return message log entries, optionally filtered by event."""
    with _connect(db_path) as conn:
        if event_name:
            rows = conn.execute(
                "SELECT * FROM message_log WHERE event_name = ? ORDER BY sent_at DESC LIMIT ?",
                (event_name, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM message_log ORDER BY sent_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
