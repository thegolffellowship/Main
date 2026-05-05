"""
SQLite storage layer for parsed transactions.

Each row represents a single line item.  One email with 3 items becomes 3 rows.
Dedicated columns for Golf Fellowship fields (chapter, handicap, side_games, etc.)
so they can be filtered and sorted directly from the dashboard.
"""

import io
import json
import math
import os
import re
import shutil
import sqlite3
import logging
from collections import defaultdict
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
    """Backfill: parse customer names into first/last parts.

    Skips customers that have failed 3+ times (tracked in name_parse_failures).
    """
    MAX_ATTEMPTS = 3

    rows = conn.execute(
        """SELECT DISTINCT customer FROM items
           WHERE customer IS NOT NULL AND customer != ''
             AND (first_name IS NULL OR first_name = '')"""
    ).fetchall()

    if not rows:
        return

    names = [r["customer"] for r in rows]

    # Filter out customers that have hit the retry cap
    try:
        failed = {r["customer_name"] for r in conn.execute(
            "SELECT customer_name FROM name_parse_failures WHERE attempts >= ?",
            (MAX_ATTEMPTS,),
        ).fetchall()}
    except sqlite3.OperationalError:
        failed = set()  # table may not exist yet on first run

    names_to_parse = [n for n in names if n not in failed]
    skipped = len(names) - len(names_to_parse)

    if skipped:
        logger.info("Skipping name parse for %d customers (max retries reached)", skipped)
    if not names_to_parse:
        return

    logger.info("Backfilling name parts for %d customers", len(names_to_parse))
    parsed = parse_names_ai(names_to_parse)

    for name, parts in zip(names_to_parse, parsed):
        first = parts.get("first_name")
        if first:
            conn.execute(
                """UPDATE items SET first_name = ?, last_name = ?, middle_name = ?, suffix = ?
                   WHERE customer = ? COLLATE NOCASE
                     AND (first_name IS NULL OR first_name = '')""",
                (first, parts.get("last_name"), parts.get("middle_name"),
                 parts.get("suffix"), name),
            )
            # Clear from failures if previously failed
            conn.execute("DELETE FROM name_parse_failures WHERE customer_name = ?", (name,))
        else:
            # Parse returned no first_name — record the failure
            conn.execute(
                """INSERT INTO name_parse_failures (customer_name, attempts, last_attempt)
                   VALUES (?, 1, datetime('now'))
                   ON CONFLICT(customer_name) DO UPDATE SET
                   attempts = attempts + 1, last_attempt = datetime('now')""",
                (name,),
            )
            # On 3rd failure, create a parse warning so admin sees it
            attempt_row = conn.execute(
                "SELECT attempts FROM name_parse_failures WHERE customer_name = ?",
                (name,),
            ).fetchone()
            if attempt_row and attempt_row["attempts"] >= MAX_ATTEMPTS:
                conn.execute(
                    """INSERT OR IGNORE INTO parse_warnings
                       (email_uid, order_id, customer, item_name, warning_code, message)
                       VALUES (?, NULL, ?, NULL, ?, ?)""",
                    (f"name-parse-{name}", name, "name_parse_failed",
                     f"Customer name \"{name}\" could not be parsed into first/last "
                     f"after {MAX_ATTEMPTS} attempts. Please edit manually."),
                )

    conn.commit()
    logger.info("Backfilled name parts for %d customers", len(names_to_parse))


def _validate_column_names(columns: list[str]) -> None:
    """Raise ValueError if any column name contains unexpected characters."""
    for col in columns:
        if not _SAFE_COL_RE.match(col):
            raise ValueError(f"Invalid column name: {col!r}")


# Allow overriding via env var so Railway can point to a persistent volume.
_default_db = Path(__file__).resolve().parent.parent / "transactions.db"
DB_PATH = Path(os.environ.get("DATABASE_PATH", str(_default_db)))


def backup_database(db_path: str | Path | None = None, label: str = "") -> str | None:
    """Create a timestamped backup of the SQLite database.

    Returns the backup file path, or None if the source doesn't exist.
    Safe to call before migrations — if the backup already exists for this
    label+date, it skips (no duplicate backups).
    """
    src = Path(db_path or DB_PATH)
    if not src.exists():
        logger.info("Backup skipped — source DB does not exist: %s", src)
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"-{label}" if label else ""
    backup_name = f"{src.stem}_backup_{ts}{suffix}{src.suffix}"
    backup_path = src.parent / backup_name

    if backup_path.exists():
        logger.info("Backup already exists: %s", backup_path)
        return str(backup_path)

    shutil.copy2(str(src), str(backup_path))
    size_mb = backup_path.stat().st_size / (1024 * 1024)
    logger.info("Database backup created: %s (%.1f MB)", backup_path, size_mb)
    return str(backup_path)


# All item-level columns (order matches the CREATE TABLE below)
ITEM_COLUMNS = [
    "email_uid", "item_index", "merchant", "customer",
    "first_name", "last_name", "middle_name", "suffix",
    "customer_email", "customer_phone",
    "order_id", "order_date", "order_time", "total_amount", "transaction_fees",
    "coupon_code", "coupon_amount",
    "item_name", "item_price", "quantity",
    "chapter", "course", "handicap", "has_handicap",
    "side_games", "tee_choice",
    "user_status", "post_game", "returning_or_new",
    "partner_request", "fellowship", "notes",
    "holes",
    "address", "address2", "city", "state", "zip",
    "shirt_size", "guest_name", "date_of_birth",
    "net_points_race", "gross_points_race", "city_match_play",
    "subject", "from_addr",
    "transaction_status", "credit_note", "transferred_from_id", "transferred_to_id",
    "wd_reason", "wd_note", "wd_credits", "credit_amount",
    "parent_item_id",
    "parent_snapshot",
    "customer_id",
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


def _migrate_eliminate_tgf_golfers(conn: sqlite3.Connection) -> None:
    """Migrate tgf_payouts.golfer_id → tgf_payouts.customer_id, then drop tgf_golfers.

    Runs inside init_db(). Idempotent — skips if tgf_golfers is already dropped.

    For each existing payout:
      1. Resolve the golfer's name to a customer_id via _lookup_customer_id.
      2. If no match, create a new customer from the golfer record (first+last name,
         carrying venmo_username and chapter).
      3. Backfill tgf_payouts.customer_id.

    Then rebuilds tgf_payouts without the golfer_id column and drops tgf_golfers.
    """
    golfers_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tgf_golfers'"
    ).fetchone()
    if not golfers_exists:
        return  # Already migrated

    logger.info("Starting tgf_golfers elimination migration")

    # Step 1: Add customer_id column to tgf_payouts if not present
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tgf_payouts)").fetchall()]
    if "customer_id" not in cols:
        conn.execute("ALTER TABLE tgf_payouts ADD COLUMN customer_id INTEGER")
        logger.info("Added customer_id column to tgf_payouts")

    # Step 2: Backfill customer_id by resolving each distinct golfer name
    # Build a golfer_id → customer_id map
    golfer_rows = conn.execute(
        "SELECT id, name, venmo_username, chapter FROM tgf_golfers"
    ).fetchall()

    golfer_to_customer: dict[int, int] = {}
    for g in golfer_rows:
        name = (g["name"] or "").strip()
        if not name:
            continue

        # Try to resolve to existing customer (by name + alias cascade)
        cid = _lookup_customer_id(conn, name, None)

        if cid is None:
            # No existing customer — create one from the golfer record
            parts = name.split()
            if len(parts) >= 2:
                first = parts[0]
                last = " ".join(parts[1:])
            else:
                first = name
                last = "(Unknown)"
            try:
                cur = conn.execute(
                    """INSERT INTO customers
                           (first_name, last_name, chapter, venmo_username,
                            account_status, acquisition_source)
                       VALUES (?, ?, ?, ?, 'active', 'tgf_payout_migration')""",
                    (first, last, g["chapter"] or None, g["venmo_username"] or None),
                )
                cid = cur.lastrowid
                logger.info("Created customer %d for former golfer '%s'", cid, name)
            except Exception as exc:
                logger.warning("Failed to create customer for golfer '%s': %s", name, exc)
                continue
        else:
            # Backfill venmo_username/chapter onto existing customer if missing
            if g["venmo_username"]:
                conn.execute(
                    """UPDATE customers SET venmo_username = ?
                       WHERE customer_id = ?
                         AND (venmo_username IS NULL OR venmo_username = '')""",
                    (g["venmo_username"], cid),
                )
            if g["chapter"]:
                conn.execute(
                    """UPDATE customers SET chapter = ?
                       WHERE customer_id = ?
                         AND (chapter IS NULL OR chapter = '')""",
                    (g["chapter"], cid),
                )

        golfer_to_customer[g["id"]] = cid

    # Apply the mapping to payouts
    for golfer_id, customer_id in golfer_to_customer.items():
        conn.execute(
            "UPDATE tgf_payouts SET customer_id = ? WHERE golfer_id = ? AND customer_id IS NULL",
            (customer_id, golfer_id),
        )

    # Step 3: Verify all payouts have customer_id set before dropping golfer linkage
    unmapped = conn.execute(
        "SELECT COUNT(*) as cnt FROM tgf_payouts WHERE customer_id IS NULL"
    ).fetchone()["cnt"]
    if unmapped > 0:
        logger.warning(
            "Aborting tgf_golfers drop — %d payouts still have NULL customer_id",
            unmapped,
        )
        conn.commit()
        return

    # Step 4: Rebuild tgf_payouts with clean schema (remove golfer_id column).
    # SQLite can't drop a column directly in older versions, so use table rebuild.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        """
        CREATE TABLE tgf_payouts_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id        INTEGER NOT NULL REFERENCES tgf_events(id) ON DELETE CASCADE,
            customer_id     INTEGER NOT NULL REFERENCES customers(customer_id),
            category        TEXT NOT NULL,
            amount          REAL NOT NULL,
            description     TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """INSERT INTO tgf_payouts_new
               (id, event_id, customer_id, category, amount, description, created_at)
           SELECT id, event_id, customer_id, category, amount, description, created_at
           FROM tgf_payouts"""
    )
    conn.execute("DROP TABLE tgf_payouts")
    conn.execute("ALTER TABLE tgf_payouts_new RENAME TO tgf_payouts")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tgf_payouts_event ON tgf_payouts(event_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tgf_payouts_customer ON tgf_payouts(customer_id)"
    )

    # Step 5: Drop tgf_golfers
    conn.execute("DROP TABLE tgf_golfers")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    logger.info(
        "tgf_golfers eliminated — migrated %d golfers to customers, dropped tgf_golfers table",
        len(golfer_to_customer),
    )


def _migrate_dedupe_payout_customers(conn: sqlite3.Connection) -> None:
    """One-time cleanup: merge duplicate customers created by tgf_golfers migration.

    The migration stored "LAST, First" names from payout screenshots as
    separate customers instead of matching them to existing "First Last"
    records.  This function merges the confirmed duplicates.

    Idempotent — skips if no acquisition_source='tgf_payout_migration'
    customers remain.
    """
    remaining = conn.execute(
        "SELECT COUNT(*) as c FROM customers WHERE acquisition_source = 'tgf_payout_migration'"
    ).fetchone()["c"]
    if remaining == 0:
        return  # Already cleaned up

    logger.info("Starting payout customer dedup — %d migration customers to process", remaining)

    # Approved merge map: migrated_customer_id → target_customer_id
    # User-confirmed matches from the dedup audit
    MERGE_MAP = {
        363: 296,   # Roland Campos → Rolando Campos
        364: 14,    # MARQUES, Mike → Mike Marques
        365: 15,    # REED, Paul → Paul Reed
        366: 31,    # STRATON, Robert → Robert Straiton (typo)
        367: 29,    # MOORE, Dion → Dion Moore
        368: 37,    # HOGUE, Jay → Jay Hogue
        369: 302,   # Moore, Hunter → Hunter Moore
        370: 39,    # BARNA, Kelly → Kelly Barna
        371: 312,   # GAGE, Erica → Erica Gage
        372: 294,   # JENKINS, Mike → Mike Jenkins
        373: 239,   # COTTRILL, Matt → Matt Cottrill
        374: 299,   # FREUND, Mark → Mark Freund
        375: 236,   # CEDILLO, David → David Cedillo
        376: 296,   # CAMPOS, Roland → Rolando Campos (same target as 363)
        377: 136,   # YOUNGS, Pat → Pat Youngs
        378: 46,    # McCRARY, Justin → Justin McCrary (canonical)
        379: 3,     # WOLIN, Allen → Allen Wolin
        380: 320,   # AGUILERA, Hector → Hector Aguilera
        381: 38,    # SHARITZ, Don → Don Sharitz
        382: 24,    # SOUTH, Daniel → Daniel South
        383: 219,   # ATKINSON, Bob → Bob Atkinson
        384: 325,   # CHALFANT, Tanner → Tanner Chalfant
        385: 31,    # STRAITON, Robert → Robert Straiton (same target as 366)
        386: 61,    # MELCHOR, Eduardo → Eduardo Melchor
        387: 30,    # SHARP, Matt → Matt Sharp
        388: 116,   # COLASANTO, Adam → Adam Colasanto
        389: 109,   # CLOER, Neal → Neal Cloer
        390: 16,    # SARRIA, Al → Al Sarria
        391: 22,    # GARTZ, Joshua → Joshua Bartz (typo in screenshot)
    }

    # Pre-existing duplicates to also clean up
    PRE_EXISTING_MERGES = {
        11: 312,    # Erica Cage (typo) → Erica Gage
        317: 46,    # Justin McCrary (wrong Venmo) → canonical Justin McCrary
        324: 46,    # Justin McCrary (third dup) → canonical Justin McCrary
    }

    merged = 0
    for source_cid, target_cid in {**MERGE_MAP, **PRE_EXISTING_MERGES}.items():
        # Verify source still exists (idempotent)
        source = conn.execute(
            "SELECT customer_id FROM customers WHERE customer_id = ?", (source_cid,)
        ).fetchone()
        if not source:
            continue  # Already merged in a previous run

        target = conn.execute(
            "SELECT customer_id FROM customers WHERE customer_id = ?", (target_cid,)
        ).fetchone()
        if not target:
            logger.warning("Merge target customer_id=%d not found — skipping source %d",
                           target_cid, source_cid)
            continue

        # Reassign tgf_payouts
        conn.execute(
            "UPDATE tgf_payouts SET customer_id = ? WHERE customer_id = ?",
            (target_cid, source_cid),
        )

        # Reassign items (if any)
        conn.execute(
            "UPDATE items SET customer_id = ? WHERE customer_id = ?",
            (target_cid, source_cid),
        )

        # Move emails (skip dupes)
        src_emails = conn.execute(
            "SELECT email FROM customer_emails WHERE customer_id = ?", (source_cid,)
        ).fetchall()
        for e in src_emails:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO customer_emails (customer_id, email, label) VALUES (?, ?, 'merged')",
                    (target_cid, e["email"]),
                )
            except Exception:
                pass
        conn.execute("DELETE FROM customer_emails WHERE customer_id = ?", (source_cid,))

        # Delete the orphaned source customer
        conn.execute("DELETE FROM customers WHERE customer_id = ?", (source_cid,))
        merged += 1

    # Fix wrong Venmo on customer 317 target → customer 46 should NOT inherit tchalfant
    conn.execute(
        """UPDATE customers SET venmo_username = NULL
           WHERE customer_id = 46
             AND venmo_username = 'tchalfant'""",
    )

    # Fix bad email association: tchalfant@sconservices.com was moved into customer 46
    # (Justin McCrary) when the duplicate customer 317 (which incorrectly had tchalfant
    # data) was merged into 46. This caused heal_items_from_customers to overwrite all
    # of Tanner Chalfant's items with McCrary's name/email.
    _CHALFANT_EMAIL = 'tchalfant@sconservices.com'
    _CHALFANT_PHONE = '(432) 661-9022'
    _CHALFANT_CID = 325
    _MCCRARY_CID = 46
    _MCCRARY_EMAIL = 'justinmccrary@elliottelectric.com'
    _MCCRARY_PHONE = '(210) 882-2755'

    removed_email = conn.execute(
        "DELETE FROM customer_emails WHERE customer_id = ? AND LOWER(email) = LOWER(?)",
        (_MCCRARY_CID, _CHALFANT_EMAIL),
    ).rowcount
    if removed_email:
        logger.info("Removed %s from McCrary (customer 46) — bad merge artifact", _CHALFANT_EMAIL)

    # Ensure Chalfant's email is on his own customer record.
    # INSERT OR IGNORE with is_primary=0 first (avoids unique-index violation if another
    # primary already exists), then explicitly promote it to primary after clearing others.
    conn.execute(
        """INSERT OR IGNORE INTO customer_emails (customer_id, email, is_primary, label)
           SELECT ?, ?, 0, 'repaired'
           WHERE EXISTS (SELECT 1 FROM customers WHERE customer_id = ?)""",
        (_CHALFANT_CID, _CHALFANT_EMAIL, _CHALFANT_CID),
    )
    # Clear any other primary for Chalfant so the unique partial index allows the next UPDATE
    conn.execute(
        """UPDATE customer_emails SET is_primary = 0
           WHERE customer_id = ? AND LOWER(email) != LOWER(?) AND is_primary = 1""",
        (_CHALFANT_CID, _CHALFANT_EMAIL),
    )
    conn.execute(
        """UPDATE customer_emails SET is_primary = 1
           WHERE customer_id = ? AND LOWER(email) = LOWER(?)""",
        (_CHALFANT_CID, _CHALFANT_EMAIL),
    )

    # Ensure Chalfant's customers.phone is his real number, not McCrary's contaminated value.
    # heal_items_from_customers reads customers.phone → items after this repair runs, so this
    # must be correct before heal overwrites items.customer_phone at startup.
    conn.execute(
        """UPDATE customers SET phone = ?
           WHERE customer_id = ?
             AND (phone IS NULL OR TRIM(phone) = '' OR phone = ?)""",
        (_CHALFANT_PHONE, _CHALFANT_CID, _MCCRARY_PHONE),
    )

    # Fix items corrupted by the bad association:
    # (a) Known corrupted order R222413986 (confirmed from Audit Log raw email body)
    fixed_a = conn.execute(
        """UPDATE items
           SET customer = 'Tanner Chalfant',
               customer_id = ?,
               customer_email = ?,
               customer_phone = CASE WHEN customer_phone = ? THEN ? ELSE customer_phone END
           WHERE order_id IN ('R222413986', '#R222413986', 'R-222413986', '222413986')""",
        (_CHALFANT_CID, _CHALFANT_EMAIL, _MCCRARY_PHONE, _CHALFANT_PHONE),
    ).rowcount
    # (b) Items with Chalfant's email wrongly under McCrary's customer_id
    fixed_b = conn.execute(
        """UPDATE items
           SET customer = 'Tanner Chalfant',
               customer_id = ?,
               customer_phone = CASE WHEN customer_phone = ? THEN ? ELSE customer_phone END
           WHERE customer_id = ? AND LOWER(customer_email) = LOWER(?)""",
        (_CHALFANT_CID, _MCCRARY_PHONE, _CHALFANT_PHONE, _MCCRARY_CID, _CHALFANT_EMAIL),
    ).rowcount
    # (c) Items still named 'Tanner Chalfant' but carrying McCrary's email (partial heal)
    fixed_c = conn.execute(
        """UPDATE items
           SET customer_email = ?,
               customer_id = ?,
               customer_phone = CASE WHEN customer_phone = ? THEN ? ELSE customer_phone END
           WHERE customer = 'Tanner Chalfant'
             AND LOWER(customer_email) = LOWER(?)""",
        (_CHALFANT_EMAIL, _CHALFANT_CID, _MCCRARY_PHONE, _CHALFANT_PHONE, _MCCRARY_EMAIL),
    ).rowcount
    # (d) Bridge via action_items.email_uid: when the original email was parsed, an
    #     action item was created with from_name='Tanner Chalfant'. The email_uid on
    #     that action item matches email_uid on the items row, letting us find the item
    #     even after its customer/email fields were overwritten by normalization/heal.
    fixed_d = conn.execute(
        """UPDATE items
           SET customer = 'Tanner Chalfant',
               customer_id = ?,
               customer_email = ?,
               customer_phone = CASE WHEN customer_phone = ? THEN ? ELSE customer_phone END
           WHERE customer_id = ?
             AND email_uid IS NOT NULL
             AND email_uid IN (
                 SELECT DISTINCT email_uid FROM action_items
                 WHERE LOWER(from_name) = 'tanner chalfant'
                   AND email_uid IS NOT NULL
             )""",
        (_CHALFANT_CID, _CHALFANT_EMAIL, _MCCRARY_PHONE, _CHALFANT_PHONE, _MCCRARY_CID),
    ).rowcount

    total_fixed = fixed_a + fixed_b + fixed_c + fixed_d
    if total_fixed:
        logger.info(
            "Re-attributed %d Tanner Chalfant item(s) back to customer %d "
            "(cases: a=%d b=%d c=%d d=%d)",
            total_fixed, _CHALFANT_CID, fixed_a, fixed_b, fixed_c, fixed_d,
        )
        # Dismiss the mismatch action items now that the items are correctly attributed
        conn.execute(
            """UPDATE action_items
               SET status = 'dismissed',
                   resolution_notes = 'Auto-fixed: re-attributed to Tanner Chalfant (cid 325)'
               WHERE LOWER(from_name) = 'tanner chalfant'
                 AND status IN ('open', 'in_progress')""",
        )

    conn.commit()
    logger.info("Payout customer dedup complete — merged %d duplicate customers", merged)


def _migrate_create_dedup_aliases(conn: sqlite3.Connection) -> None:
    """Create customer_aliases entries for the dedup-migration name mappings.

    The original _migrate_dedupe_payout_customers merged 29 golfer records
    into existing customers but did NOT create aliases for the original
    names. This means acct_transactions entries stored under old names
    (e.g., "Roland Campos" when canonical is "Rolando Campos") can't
    be resolved via _lookup_customer_id → they fail to match in payout
    reconciliation.

    Idempotent — uses INSERT OR IGNORE.
    """
    # Map: old_name (as stored in venmo/payout data) → canonical customer_id
    ALIAS_SEED = [
        ("Roland Campos", 296),
        ("MARQUES, Mike", 14),
        ("REED, Paul", 15),
        ("STRATON, Robert", 31),      # typo variant
        ("STRAITON, Robert", 31),
        ("MOORE, Dion", 29),
        ("HOGUE, Jay", 37),
        ("Moore, Hunter", 302),
        ("BARNA, Kelly", 39),
        ("GAGE, Erica", 312),
        ("JENKINS, Mike", 294),
        ("COTTRILL, Matt", 239),
        ("FREUND, Mark", 299),
        ("CEDILLO, David", 236),
        ("CAMPOS, Roland", 296),
        ("YOUNGS, Pat", 136),
        ("McCRARY, Justin", 46),
        ("WOLIN, Allen", 3),
        ("AGUILERA, Hector", 320),
        ("SHARITZ, Don", 38),
        ("SOUTH, Daniel", 24),
        ("ATKINSON, Bob", 219),
        ("CHALFANT, Tanner", 325),
        ("MELCHOR, Eduardo", 61),
        ("SHARP, Matt", 30),
        ("COLASANTO, Adam", 116),
        ("CLOER, Neal", 109),
        ("SARRIA, Al", 16),
        ("GARTZ, Joshua", 22),
        ("Erica Cage", 312),            # typo variant
    ]

    created = 0
    for alias_name, target_cid in ALIAS_SEED:
        canonical = conn.execute(
            "SELECT first_name || ' ' || last_name as n FROM customers WHERE customer_id = ?",
            (target_cid,),
        ).fetchone()
        if not canonical:
            continue
        canonical_name = canonical["n"]
        if alias_name.lower() == canonical_name.lower():
            continue  # No alias needed

        # Check if alias already exists
        existing = conn.execute(
            """SELECT id FROM customer_aliases
               WHERE alias_type = 'name'
                 AND LOWER(alias_value) = LOWER(?)
                 AND LOWER(customer_name) = LOWER(?)""",
            (alias_name, canonical_name),
        ).fetchone()
        if existing:
            continue

        try:
            conn.execute(
                """INSERT INTO customer_aliases (customer_name, alias_type, alias_value)
                   VALUES (?, 'name', ?)""",
                (canonical_name, alias_name),
            )
            created += 1
        except Exception as exc:
            logger.debug("Alias insert failed for %r → %r: %s", alias_name, canonical_name, exc)

    if created:
        conn.commit()
        logger.info("Created %d customer_aliases for dedup-merged names", created)


def _migrate_create_dim_tables(conn: sqlite3.Connection) -> None:
    """Seed chapters and courses dimension tables from existing data.

    Idempotent — skips if chapters already has rows.

    1. Seed chapters from the 4 known valid values.
    2. Scan distinct course names from items + events, normalize via
       _COURSE_CANONICAL from parser.py, insert into courses.
    3. Create course_aliases for known spelling variants.
    4. Add chapter_id + course_id FK columns to items and events.
    5. Backfill FK values by matching string columns to dim tables.
    """
    existing_chapters = conn.execute("SELECT COUNT(*) as c FROM chapters").fetchone()["c"]
    existing_courses = conn.execute("SELECT COUNT(*) as c FROM courses").fetchone()["c"]
    items_cols = [r[1] for r in conn.execute("PRAGMA table_info(items)").fetchall()]
    needs_fk = "chapter_id" not in items_cols or "course_id" not in items_cols

    if existing_chapters > 0 and existing_courses > 0 and not needs_fk:
        # Check if any items/events still need backfill (chapter or course)
        try:
            needs_backfill_row = conn.execute(
                """SELECT
                   (SELECT COUNT(*) FROM items
                      WHERE (chapter_id IS NULL AND chapter IS NOT NULL AND chapter != '')
                         OR (course_id IS NULL AND course IS NOT NULL AND course != '')) as items_backfill,
                   (SELECT COUNT(*) FROM events
                      WHERE (chapter_id IS NULL AND chapter IS NOT NULL AND chapter != '')
                         OR (course_id IS NULL AND course IS NOT NULL AND course != '')) as events_backfill"""
            ).fetchone()
            needs_backfill = needs_backfill_row["items_backfill"] + needs_backfill_row["events_backfill"]
        except Exception:
            needs_backfill = 0
        if needs_backfill == 0:
            return  # Already seeded and backfilled

    logger.info("Seeding chapters and courses dimension tables")

    # ── Step 1: Seed chapters ──
    chapter_data = [
        ("San Antonio", "SA", "America/Chicago"),
        ("Austin", "AUS", "America/Chicago"),
        ("DFW", "DFW", "America/Chicago"),
        ("Houston", "HOU", "America/Chicago"),
        ("Hill Country", "HC", "America/Chicago"),
    ]
    for name, code, tz in chapter_data:
        conn.execute(
            "INSERT OR IGNORE INTO chapters (name, short_code, timezone) VALUES (?, ?, ?)",
            (name, code, tz),
        )
    logger.info("Seeded %d chapters", len(chapter_data))

    # Build chapter lookup: lowercase → chapter_id
    chapter_map = {}
    for row in conn.execute("SELECT chapter_id, name FROM chapters").fetchall():
        chapter_map[row["name"].lower()] = row["chapter_id"]

    # Extended chapter alias map for backfill matching
    chapter_aliases = {
        "aus": "austin", "atx": "austin", "sa": "san antonio",
        "sat": "san antonio", "dal": "dfw", "dallas": "dfw",
        "fort worth": "dfw", "hou": "houston",
    }

    def resolve_chapter_id(chapter_str):
        if not chapter_str:
            return None
        key = chapter_str.strip().lower()
        if key in chapter_map:
            return chapter_map[key]
        resolved = chapter_aliases.get(key)
        if resolved and resolved in chapter_map:
            return chapter_map[resolved]
        return None

    # ── Step 2: Seed courses ──
    # Gather distinct course names from items + events
    raw_courses = set()
    for row in conn.execute("SELECT DISTINCT course FROM items WHERE course IS NOT NULL AND course != ''"):
        raw_courses.add(row["course"].strip())
    for row in conn.execute("SELECT DISTINCT course FROM events WHERE course IS NOT NULL AND course != ''"):
        raw_courses.add(row["course"].strip())

    # Canonical mapping from parser.py constants
    from email_parser.parser import _COURSE_CANONICAL

    # Normalize raw courses to canonical names
    canonical_courses: dict[str, set[str]] = {}  # canonical_name → set of raw variants
    for raw in raw_courses:
        key = raw.lower().replace(" golf club", "").replace(" golf course", "").strip()
        canonical = _COURSE_CANONICAL.get(key, raw.strip().title())
        if canonical not in canonical_courses:
            canonical_courses[canonical] = set()
        if raw.lower() != canonical.lower():
            canonical_courses[canonical].add(raw)

    # Determine most common chapter for each course
    course_chapter: dict[str, int | None] = {}
    for canonical in canonical_courses:
        row = conn.execute(
            """SELECT chapter, COUNT(*) as cnt FROM items
               WHERE course IS NOT NULL AND course != ''
               GROUP BY chapter ORDER BY cnt DESC LIMIT 1"""
        ).fetchone()
        # Try matching specifically for this course
        ch_row = conn.execute(
            """SELECT chapter, COUNT(*) as cnt FROM (
                   SELECT chapter FROM items WHERE LOWER(course) = LOWER(?)
                   UNION ALL
                   SELECT chapter FROM events WHERE LOWER(course) = LOWER(?)
               ) GROUP BY chapter ORDER BY cnt DESC LIMIT 1""",
            (canonical, canonical),
        ).fetchone()
        if ch_row and ch_row["chapter"]:
            course_chapter[canonical] = resolve_chapter_id(ch_row["chapter"])
        else:
            course_chapter[canonical] = None

    # Insert courses
    courses_added = 0
    for canonical in sorted(canonical_courses.keys()):
        try:
            conn.execute(
                "INSERT OR IGNORE INTO courses (name, chapter_id) VALUES (?, ?)",
                (canonical, course_chapter.get(canonical)),
            )
            courses_added += 1
        except Exception:
            pass
    logger.info("Seeded %d courses", courses_added)

    # Build course lookup: lowercase → course_id
    course_map = {}
    for row in conn.execute("SELECT course_id, name FROM courses").fetchall():
        course_map[row["name"].lower()] = row["course_id"]

    # ── Step 3: Create course_aliases ──
    aliases_added = 0
    for canonical, variants in canonical_courses.items():
        cid = course_map.get(canonical.lower())
        if not cid:
            continue
        for variant in variants:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO course_aliases (course_id, alias_name) VALUES (?, ?)",
                    (cid, variant),
                )
                aliases_added += 1
            except Exception:
                pass
    # Also add the canonical mapping from _COURSE_CANONICAL keys
    for alias_key, canonical in _COURSE_CANONICAL.items():
        cid = course_map.get(canonical.lower())
        if not cid:
            continue
        # Convert alias_key back to something recognizable (title case)
        alias_display = alias_key.strip().title()
        if alias_display.lower() != canonical.lower():
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO course_aliases (course_id, alias_name) VALUES (?, ?)",
                    (cid, alias_display),
                )
                aliases_added += 1
            except Exception:
                pass
    logger.info("Created %d course_aliases", aliases_added)

    # ── Step 4: Add FK columns ──
    for table in ("items", "events"):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if "chapter_id" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN chapter_id INTEGER REFERENCES chapters(chapter_id)")
        if "course_id" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN course_id INTEGER REFERENCES courses(course_id)")

    # Extended course lookup including aliases
    for row in conn.execute(
        "SELECT course_id, alias_name FROM course_aliases"
    ).fetchall():
        course_map[row["alias_name"].lower()] = row["course_id"]

    def resolve_course_id(course_str):
        if not course_str:
            return None
        key = course_str.strip().lower()
        return course_map.get(key)

    # ── Step 5: Backfill FKs ──
    # Items
    items_updated = 0
    for row in conn.execute(
        "SELECT id, chapter, course FROM items WHERE chapter_id IS NULL OR course_id IS NULL"
    ).fetchall():
        updates = []
        vals = []
        if row["chapter"]:
            cid = resolve_chapter_id(row["chapter"])
            if cid:
                updates.append("chapter_id = ?")
                vals.append(cid)
        if row["course"]:
            crs = resolve_course_id(row["course"])
            if crs:
                updates.append("course_id = ?")
                vals.append(crs)
        if updates:
            vals.append(row["id"])
            conn.execute(f"UPDATE items SET {', '.join(updates)} WHERE id = ?", vals)
            items_updated += 1

    # Events
    events_updated = 0
    for row in conn.execute(
        "SELECT id, chapter, course FROM events WHERE chapter_id IS NULL OR course_id IS NULL"
    ).fetchall():
        updates = []
        vals = []
        if row["chapter"]:
            cid = resolve_chapter_id(row["chapter"])
            if cid:
                updates.append("chapter_id = ?")
                vals.append(cid)
        if row["course"]:
            crs = resolve_course_id(row["course"])
            if crs:
                updates.append("course_id = ?")
                vals.append(crs)
        if updates:
            vals.append(row["id"])
            conn.execute(f"UPDATE events SET {', '.join(updates)} WHERE id = ?", vals)
            events_updated += 1

    conn.commit()
    logger.info(
        "Dim table backfill: %d items updated, %d events updated",
        items_updated, events_updated,
    )


def _migrate_normalize_venmo_customer_names(conn: sqlite3.Connection) -> None:
    """One-shot: rewrite acct_transactions.customer for Venmo prize_payouts to
    the canonical customers.first_name + last_name when the name resolves
    (via _lookup_customer_id) to a customer.

    Fixes cases where Venmo notes used a name variant (e.g., "Roland Campos")
    that doesn't match the canonical record ("Rolando Campos"), preventing
    the payout matcher from linking them.

    Idempotent — safe to run every startup; only updates when the stored
    name doesn't already match the canonical name.
    """
    # Only look at venmo prize_payouts (small scope)
    rows = conn.execute(
        """SELECT id, customer FROM acct_transactions
           WHERE source = 'venmo' AND category = 'prize_payout'
             AND customer IS NOT NULL AND customer != ''"""
    ).fetchall()
    if not rows:
        return

    normalized = 0
    for r in rows:
        stored_name = r["customer"]
        cid = _lookup_customer_id(conn, stored_name, None)
        if cid is None:
            continue
        canonical = conn.execute(
            "SELECT first_name || ' ' || last_name as n FROM customers WHERE customer_id = ?",
            (cid,),
        ).fetchone()
        if not canonical:
            continue
        canonical_name = canonical["n"]
        if canonical_name.lower() == stored_name.lower():
            continue  # Already canonical
        conn.execute(
            "UPDATE acct_transactions SET customer = ? WHERE id = ?",
            (canonical_name, r["id"]),
        )
        normalized += 1

    if normalized:
        conn.commit()
        logger.info("Normalized %d Venmo acct_transactions.customer values to canonical names", normalized)


def _migrate_move_noncanonical_side_games_to_notes(conn: sqlite3.Connection) -> int:
    """Move free-form text out of items.side_games into items.notes so the
    Side Games column stays canonical (NET / GROSS / BOTH / NONE).

    Triggered when admins typed descriptions like 'Difference between ShadowGlen
    & Teravista' into side_games on a manual +PAY because there was no Notes
    column at the time. Naturally idempotent — once moved, side_games is set
    to NULL so subsequent runs find nothing to migrate.
    """
    canonical = ("NET", "GROSS", "BOTH", "NONE")
    rows = conn.execute(
        f"""SELECT id, side_games, notes FROM items
            WHERE side_games IS NOT NULL
              AND TRIM(side_games) != ''
              AND UPPER(TRIM(side_games)) NOT IN ({','.join('?' * len(canonical))})"""
        , canonical,
    ).fetchall()
    moved = 0
    for r in rows:
        text = (r["side_games"] or "").strip()
        if not text:
            continue
        existing = (r["notes"] or "").strip()
        # Skip if the same text is already in notes (avoid duplication on re-runs)
        if existing and text in existing:
            new_notes = existing
        else:
            new_notes = (existing + " — " + text).strip(" —") if existing else text
        conn.execute(
            "UPDATE items SET notes = ?, side_games = NULL WHERE id = ?",
            (new_notes, r["id"]),
        )
        moved += 1
    if moved:
        logger.info("Moved non-canonical side_games text to notes on %d items", moved)
    return moved


def _migrate_relabel_credit_pool_items(conn: sqlite3.Connection) -> int:
    """Rewrite item_name on credit-pool rows so they read as 'Excess credit — <event>'
    or 'Overpayment credit — <event>' instead of looking like a registration on
    the event itself. Idempotent — only touches rows that haven't been relabeled.
    """
    updated = 0
    rows = conn.execute(
        """SELECT id, email_uid, item_name FROM items
           WHERE (email_uid LIKE 'credit-excess-%' OR email_uid LIKE 'overpayment-credit-%')
             AND item_name IS NOT NULL
             AND item_name NOT LIKE 'Excess credit %'
             AND item_name NOT LIKE 'Overpayment credit %'"""
    ).fetchall()
    for r in rows:
        prefix = "Overpayment credit" if (r["email_uid"] or "").startswith("overpayment-credit-") else "Excess credit"
        new_name = f"{prefix} — {r['item_name']}".strip(" —")
        conn.execute("UPDATE items SET item_name = ? WHERE id = ?", (new_name, r["id"]))
        updated += 1
    if updated:
        logger.info("Relabeled %d credit-pool items with descriptive item_name", updated)
    return updated


def _migrate_rename_member_role_to_golfer(conn: sqlite3.Connection) -> None:
    """Rename the 'member' user role to 'golfer' to avoid collision with the
    player_status display value 'MEMBER'. Idempotent.

    Recreates customer_roles with the new CHECK constraint, copying existing
    rows and mapping role_type='member' → 'golfer'. Player_status values like
    'active_member' / 'expired_member' / 'MEMBER' are NOT touched — those are
    a different field.
    """
    # Cheap probe: does the existing CHECK still allow 'member'?
    sql_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='customer_roles'"
    ).fetchone()
    if not sql_row:
        return  # Table doesn't exist yet — fresh CREATE TABLE will use 'golfer'.
    if "'member'" not in (sql_row["sql"] or ""):
        return  # Already migrated.

    logger.info("Migrating customer_roles: renaming role 'member' → 'golfer'")
    conn.executescript(
        """
        CREATE TABLE customer_roles_new (
            role_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL
                        REFERENCES customers(customer_id)
                        ON DELETE CASCADE,
            role_type   VARCHAR(30) NOT NULL
                        CHECK (role_type IN (
                            'golfer', 'manager', 'admin', 'owner',
                            'course_contact', 'sponsor', 'vendor'
                        )),
            granted_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            granted_by  INTEGER REFERENCES customers(customer_id),
            UNIQUE(customer_id, role_type)
        );
        INSERT OR IGNORE INTO customer_roles_new
            (role_id, customer_id, role_type, granted_at, granted_by)
        SELECT role_id, customer_id,
               CASE WHEN role_type = 'member' THEN 'golfer' ELSE role_type END,
               granted_at, granted_by
        FROM customer_roles;
        DROP TABLE customer_roles;
        ALTER TABLE customer_roles_new RENAME TO customer_roles;
        """
    )
    renamed = conn.execute(
        "SELECT COUNT(*) as c FROM customer_roles WHERE role_type = 'golfer'"
    ).fetchone()["c"]
    logger.info("customer_roles migration complete; %d rows now have role 'golfer'", renamed)


def _migrate_seed_customer_roles(conn: sqlite3.Connection) -> None:
    """One-time seed of customer_roles junction table + first_timer_ever backfill.

    Idempotent — skips if customer_roles already has rows.

    Maps to Platform user_types table:
      'golfer', 'manager', 'admin', 'owner' (→ super_admin at migration),
      'course_contact', 'sponsor', 'vendor'

    Seed logic:
      - Kerry Niester → owner + admin + golfer
      - Robert Straiton, James Jones → manager + golfer
      - All customers with current_player_status in (active_member, expired_member) → golfer
      - first_timer_ever backfilled: 0 for anyone with paid registrations, 1 for all others
    """
    existing = conn.execute("SELECT COUNT(*) as c FROM customer_roles").fetchone()["c"]
    if existing > 0:
        return

    logger.info("Seeding customer_roles junction table")

    def _find_customer(conn, first, last):
        row = conn.execute(
            "SELECT customer_id FROM customers WHERE LOWER(first_name) = LOWER(?) AND LOWER(last_name) = LOWER(?)",
            (first, last),
        ).fetchone()
        return row["customer_id"] if row else None

    def _add_role(conn, cid, role, granted_by=None):
        if cid is None:
            return
        conn.execute(
            "INSERT OR IGNORE INTO customer_roles (customer_id, role_type, granted_by) VALUES (?, ?, ?)",
            (cid, role, granted_by),
        )

    # Named leadership roles
    kerry_id = _find_customer(conn, "Kerry", "Niester")
    robert_id = _find_customer(conn, "Robert", "Straiton")
    james_id = _find_customer(conn, "James", "Jones")

    if kerry_id:
        for role in ("owner", "admin", "golfer"):
            _add_role(conn, kerry_id, role)
        logger.info("Assigned owner+admin+golfer to Kerry Niester (customer_id=%s)", kerry_id)

    if robert_id:
        for role in ("manager", "golfer"):
            _add_role(conn, robert_id, role, granted_by=kerry_id)
        logger.info("Assigned manager+golfer to Robert Straiton (customer_id=%s)", robert_id)

    if james_id:
        for role in ("manager", "golfer"):
            _add_role(conn, james_id, role, granted_by=kerry_id)
        logger.info("Assigned manager+golfer to James Jones (customer_id=%s)", james_id)

    # Bulk-assign 'golfer' role to all active/expired members
    golfer_ids = conn.execute(
        """SELECT customer_id FROM customers
           WHERE current_player_status IN ('active_member', 'expired_member')
             AND customer_id NOT IN (SELECT customer_id FROM customer_roles WHERE role_type = 'golfer')"""
    ).fetchall()
    for row in golfer_ids:
        _add_role(conn, row["customer_id"], "golfer")

    total_roles = conn.execute("SELECT COUNT(*) as c FROM customer_roles").fetchone()["c"]
    logger.info("Seeded %d customer_roles entries", total_roles)

    # Backfill first_timer_ever: FALSE for anyone with paid event registrations
    updated = conn.execute(
        """UPDATE customers SET first_timer_ever = 0
           WHERE first_timer_ever IS NULL
             AND customer_id IN (
               SELECT DISTINCT customer_id FROM items
               WHERE customer_id IS NOT NULL
                 AND COALESCE(transaction_status, 'active') IN ('active', 'credited', 'transferred', 'wd', 'refunded')
                 AND item_name != 'TGF MEMBERSHIP'
                 AND merchant NOT IN ('Roster Import', 'Customer Entry', 'RSVP Import', 'RSVP Email Link')
             )"""
    ).rowcount

    # Default everyone else to TRUE (they are a first timer until proven otherwise)
    defaulted = conn.execute(
        "UPDATE customers SET first_timer_ever = 1 WHERE first_timer_ever IS NULL"
    ).rowcount

    conn.commit()
    logger.info("first_timer_ever backfill: %d set to FALSE (played), %d defaulted to TRUE", updated, defaulted)


def _migrate_add_member_plus_status(conn: sqlite3.Connection) -> None:
    """Add 'member_plus' to the customers.current_player_status CHECK constraint."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='customers'"
    ).fetchone()
    if not row or "member_plus" in (row["sql"] or ""):
        return
    logger.info("Migrating customers table: adding member_plus to CHECK constraint")
    conn.executescript("""
        PRAGMA foreign_keys = OFF;
        CREATE TABLE customers_new (
            customer_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            platform_user_id     INTEGER,
            first_name           VARCHAR(100) NOT NULL,
            last_name            VARCHAR(100) NOT NULL,
            phone                VARCHAR(30),
            chapter              VARCHAR(50),
            ghin_number          VARCHAR(20),
            current_player_status VARCHAR(30)
                CHECK (current_player_status IN (
                    'active_member', 'member_plus', 'expired_member',
                    'active_guest', 'inactive', 'first_timer'
                )),
            first_timer_ever     INTEGER,
            acquisition_source   VARCHAR(50),
            account_status       VARCHAR(20) NOT NULL DEFAULT 'active'
                CHECK (account_status IN ('active', 'inactive', 'banned')),
            venmo_username       VARCHAR(50),
            created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO customers_new SELECT * FROM customers;
        DROP TABLE customers;
        ALTER TABLE customers_new RENAME TO customers;
        PRAGMA foreign_keys = ON;
    """)
    logger.info("customers table migrated: member_plus status added")


_ROMAN_RE = re.compile(r"^(i{1,3}|iv|v|vi{0,3}|ix|x)$")

def _proper_case_word(w: str) -> str:
    wl = w.lower()
    if _ROMAN_RE.match(wl):
        return wl.upper()
    if "-" in w:
        return "-".join(_proper_case_word(p) for p in w.split("-"))
    if "'" in w:
        return "'".join(p.capitalize() for p in wl.split("'"))
    if wl.startswith("mc") and len(wl) > 2:
        return "Mc" + wl[2].upper() + wl[3:]
    if wl.startswith("mac") and len(wl) > 3 and wl[3] in "abcdefghijklmnopqrstuvwxyz":
        return "Mac" + wl[3].upper() + wl[4:]
    return wl.capitalize()


def _proper_case(s: str | None) -> str | None:
    if not s:
        return s
    return " ".join(_proper_case_word(w) for w in s.split())


def _migrate_normalize_customer_name_case(conn: sqlite3.Connection) -> int:
    """Convert all-uppercase customer first/last names to proper case.

    Idempotent — only touches names where .isupper() is True (no
    lowercase letters anywhere). Mixed-case names like "McDonald" are
    left alone. Updates customers.first_name / last_name and propagates
    the new values to items.first_name / items.last_name / items.customer
    so the Info-tab form (which pre-fills from items) doesn't write
    stale uppercase back into the customers table on save.
    """
    rows = conn.execute(
        "SELECT customer_id, first_name, last_name FROM customers"
    ).fetchall()
    updated = 0
    for r in rows:
        f, l = r["first_name"] or "", r["last_name"] or ""
        new_f = _proper_case(f) if (f and f.isupper() and any(ch.isalpha() for ch in f)) else f
        new_l = _proper_case(l) if (l and l.isupper() and any(ch.isalpha() for ch in l)) else l
        if new_f == f and new_l == l:
            continue
        conn.execute(
            "UPDATE customers SET first_name = ?, last_name = ? WHERE customer_id = ?",
            (new_f, new_l, r["customer_id"]),
        )
        full = f"{new_f or ''} {new_l or ''}".strip()
        conn.execute(
            "UPDATE items SET first_name = ?, last_name = ?, customer = ? WHERE customer_id = ?",
            (new_f or None, new_l or None, full or None, r["customer_id"]),
        )
        updated += 1

    # Pass 2: items rows whose first_name/last_name are still uppercase but
    # whose linked customer record is already proper-case (e.g. names that
    # got written back via a stale Info-tab save before this fix existed).
    # Re-sync those items to the customers master record.
    item_rows = conn.execute(
        """SELECT i.id, i.first_name AS i_first, i.last_name AS i_last,
                  c.first_name AS c_first, c.last_name AS c_last
           FROM items i
           JOIN customers c ON c.customer_id = i.customer_id
           WHERE (i.first_name IS NOT NULL AND LENGTH(i.first_name) > 0
                  AND i.first_name = UPPER(i.first_name)
                  AND i.first_name GLOB '*[A-Z]*'
                  AND i.first_name != c.first_name)
              OR (i.last_name IS NOT NULL AND LENGTH(i.last_name) > 0
                  AND i.last_name = UPPER(i.last_name)
                  AND i.last_name GLOB '*[A-Z]*'
                  AND i.last_name != c.last_name)"""
    ).fetchall()
    for ir in item_rows:
        full = f"{ir['c_first'] or ''} {ir['c_last'] or ''}".strip()
        conn.execute(
            "UPDATE items SET first_name = ?, last_name = ?, customer = ? WHERE id = ?",
            (ir["c_first"], ir["c_last"], full or None, ir["id"]),
        )

    if updated or item_rows:
        logger.info(
            "Normalized name case for %d customer(s); resynced %d item row(s)",
            updated, len(item_rows),
        )
    return updated


def _migrate_autocorrect_player_status(conn: sqlite3.Connection) -> int:
    """Reconcile stale customers.current_player_status with item history.

    Two passes (idempotent):
    1. Anyone who has bought a TGF Membership but is still flagged
       first_timer / active_guest / NULL → upgrade to active_member.
    2. Anyone still flagged first_timer who has played more than once
       (and didn't get caught by pass 1) → demote to active_guest. They're
       past their first event and should no longer carry the 1st TIMER tag.
    """
    upgraded = conn.execute(
        """UPDATE customers
              SET current_player_status = 'active_member',
                  updated_at = CURRENT_TIMESTAMP
            WHERE customer_id IN (
                SELECT DISTINCT i.customer_id
                FROM items i
                WHERE LOWER(i.item_name) LIKE '%membership%'
                  AND i.customer_id IS NOT NULL
            )
              AND (current_player_status IS NULL
                   OR current_player_status IN ('first_timer', 'active_guest'))"""
    ).rowcount

    demoted = conn.execute(
        """UPDATE customers
              SET current_player_status = 'active_guest',
                  updated_at = CURRENT_TIMESTAMP
            WHERE current_player_status = 'first_timer'
              AND (SELECT COUNT(*) FROM items i WHERE i.customer_id = customers.customer_id) > 1"""
    ).rowcount

    if upgraded or demoted:
        logger.info(
            "Auto-corrected player_status: %d upgraded to active_member, %d demoted to active_guest",
            upgraded, demoted,
        )
    return upgraded + demoted


def _migrate_canonicalize_chapters(conn: sqlite3.Connection) -> int:
    """Ensure the canonical chapters list includes Hill Country, then remap
    legacy items.chapter / events.chapter / customers.chapter values to the
    canonical chapter list. Idempotent — only touches non-canonical strings.

    Cedar Park → Austin (Austin-area sub-locale)
    Pflugerville → Austin (Austin-area sub-locale)
    August → NULL (likely a truncated/typo entry — clear so an admin can re-tag)
    Yes_For_Both → NULL (form-quirk garbage)
    """
    # Ensure Hill Country exists in the chapters dim table — the original
    # seed block early-returns once initialized, so a code-level addition
    # to chapter_data wouldn't otherwise hit the live DB.
    try:
        conn.execute(
            "INSERT OR IGNORE INTO chapters (name, short_code, timezone) VALUES (?, ?, ?)",
            ("Hill Country", "HC", "America/Chicago"),
        )
    except sqlite3.OperationalError:
        pass  # chapters table not yet created on a brand-new DB — handled by full seed

    REMAP = {
        "Cedar Park": "Austin",
        "Pflugerville": "Austin",
        "August": None,
        "Yes_For_Both": None,
    }
    total = 0
    for table in ("items", "events", "customers"):
        # Skip tables that don't have a chapter column (defensive)
        cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "chapter" not in cols:
            continue
        for legacy, canonical in REMAP.items():
            if canonical is None:
                rc = conn.execute(
                    f"UPDATE {table} SET chapter = NULL WHERE chapter = ?",
                    (legacy,),
                ).rowcount
            else:
                rc = conn.execute(
                    f"UPDATE {table} SET chapter = ? WHERE chapter = ?",
                    (canonical, legacy),
                ).rowcount
            total += rc
    if total:
        logger.info("Canonicalized chapter values across items/events/customers (%d rows updated)", total)
    return total


def _migrate_dedup_expense_transactions(conn: sqlite3.Connection) -> None:
    """Remove duplicate expense_transactions rows.

    Two duplicate sources:
    1. Same email processed twice with different UIDs → same merchant/amount/date
    2. NULL email_uid rows where ON CONFLICT(email_uid) never fired

    Keeps the row with the highest id (most recent) for each
    (source_type, merchant, amount, transaction_date) group.
    Idempotent — safe to run on every startup.
    """
    dupes = conn.execute(
        """SELECT MIN(id) as drop_id
           FROM expense_transactions
           GROUP BY source_type,
                    LOWER(COALESCE(merchant, '')),
                    amount,
                    transaction_date
           HAVING COUNT(*) > 1"""
    ).fetchall()
    if not dupes:
        return
    drop_ids = [r["drop_id"] for r in dupes]
    conn.executemany(
        "DELETE FROM expense_transactions WHERE id = ?",
        [(i,) for i in drop_ids],
    )
    conn.commit()
    logger.info("Removed %d duplicate expense_transactions rows", len(drop_ids))


def _migrate_wire_payouts_to_ledger(conn: sqlite3.Connection) -> None:
    """Step 3 migration: wire tgf_payouts into the acct_transactions ledger.

    Adds acct_transaction_id and paid_at columns to tgf_payouts (existing
    installs), then backfills:
      1. Creates a pending acct_transactions expense entry for each historical
         payout that lacks one (category='prize_payout', source='pending').
      2. Attempts exact-amount match against existing Venmo prize_payout
         acct_transactions (same customer_id, exact amount, date within 7 days
         after the event). When matched: links the payout to the Venmo txn
         and marks the pending entry as reversed.

    Idempotent — skips rows that already have acct_transaction_id set.
    """
    # Skip if tgf_payouts doesn't exist yet (fresh install — table gets
    # created later in init_db with the correct schema from the start)
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tgf_payouts'"
    ).fetchone()
    if not table_exists:
        return

    cols = [r[1] for r in conn.execute("PRAGMA table_info(tgf_payouts)").fetchall()]
    added_cols = False
    if "acct_transaction_id" not in cols:
        conn.execute("ALTER TABLE tgf_payouts ADD COLUMN acct_transaction_id INTEGER REFERENCES acct_transactions(id)")
        added_cols = True
    if "paid_at" not in cols:
        conn.execute("ALTER TABLE tgf_payouts ADD COLUMN paid_at TIMESTAMP")
        added_cols = True
    if added_cols:
        logger.info("Added acct_transaction_id + paid_at to tgf_payouts")

    # Backfill pending ledger entries + match
    pending_rows = conn.execute(
        """SELECT p.id, p.event_id, p.customer_id, p.amount, p.category, p.description,
                  e.event_date, e.name as event_name
           FROM tgf_payouts p
           JOIN tgf_events e ON e.id = p.event_id
           WHERE p.acct_transaction_id IS NULL"""
    ).fetchall()

    paired = 0
    if pending_rows:
        logger.info("Wiring %d existing payouts to the ledger", len(pending_rows))
        paired = _reconcile_payouts_with_venmo(conn, pending_rows)

    # Also run the reverse match across ALL currently-pending payouts (including
    # ones wired in a previous run) — this picks up grouped (customer+event) matches
    # that the earlier per-row matcher missed.
    retroactive = _match_pending_payouts_to_new_venmo(conn)

    conn.commit()
    if pending_rows or retroactive:
        logger.info(
            "Payout ledger wiring complete — %d newly wired (%d auto-matched), %d pending retroactively linked to Venmo",
            len(pending_rows), paired, retroactive,
        )


def _reconcile_payouts_with_venmo(conn: sqlite3.Connection, payout_rows) -> int:
    """For a list of unlinked payouts, either match them to an existing Venmo
    prize_payout acct_transaction, or create a pending placeholder.

    Matching is done at the (customer_id, event_id) level — all of a golfer's
    payouts for one event are summed and matched to a single Venmo transaction.
    This handles the common case where one Venmo payment covers multiple
    prize categories (e.g., Kelly Barna's $208.25 = sum of skins + net + gross
    + team + mvp wins at one event).

    Returns count of payouts that matched an existing Venmo payment.
    """
    # Group payouts by (event_id, customer_id)
    groups: dict[tuple[int, int], dict] = {}
    for p in payout_rows:
        key = (p["event_id"], p["customer_id"])
        if key not in groups:
            groups[key] = {
                "event_date": p["event_date"],
                "event_name": p["event_name"],
                "customer_id": p["customer_id"],
                "payouts": [],
            }
        groups[key]["payouts"].append(dict(p))

    matched = 0
    for (event_id, customer_id), g in groups.items():
        group_sum = round(sum(float(p["amount"]) for p in g["payouts"]), 2)
        event_date = g["event_date"]
        event_name = g["event_name"]

        # Find a single Venmo prize_payout matching the group sum
        venmo_match = conn.execute(
            """SELECT t.id, t.date FROM acct_transactions t
               WHERE t.source != 'pending'
                 AND t.category = 'prize_payout'
                 AND COALESCE(t.status, 'active') IN ('active', 'reconciled')
                 AND ROUND(ABS(t.amount), 2) = ?
                 AND DATE(t.date) >= DATE(?)
                 AND DATE(t.date) <= DATE(?, '+7 days')
                 AND NOT EXISTS (
                   SELECT 1 FROM tgf_payouts existing
                   WHERE existing.acct_transaction_id = t.id
                 )
                 AND (
                   -- Direct customer name match
                   EXISTS (
                     SELECT 1 FROM customers c
                     WHERE c.customer_id = ?
                       AND LOWER(t.customer) = LOWER(c.first_name || ' ' || c.last_name)
                   )
                   OR
                   -- Alias match via customer_aliases (handles name variants)
                   EXISTS (
                     SELECT 1 FROM customer_aliases a
                     JOIN customers c2 ON LOWER(c2.first_name || ' ' || c2.last_name) = LOWER(a.customer_name)
                     WHERE a.alias_type = 'name'
                       AND LOWER(a.alias_value) = LOWER(t.customer)
                       AND c2.customer_id = ?
                   )
                 )
               ORDER BY t.date ASC LIMIT 1""",
            (group_sum, event_date, event_date, customer_id, customer_id),
        ).fetchone()

        if venmo_match:
            # Link every payout in the group to this single Venmo transaction
            for p in g["payouts"]:
                conn.execute(
                    "UPDATE tgf_payouts SET acct_transaction_id = ?, paid_at = ? WHERE id = ?",
                    (venmo_match["id"], venmo_match["date"], p["id"]),
                )
                matched += 1
        else:
            # Create per-payout pending entries — each payout gets its own
            # placeholder since we can't resolve them against a Venmo yet
            for p in g["payouts"]:
                cur = conn.execute(
                    """INSERT INTO acct_transactions
                           (date, description, total_amount, type, source, source_ref,
                            customer, order_id, entry_type, category, amount, account,
                            status, event_name)
                       VALUES (?, ?, ?, 'expense', 'pending', ?, ?, ?, 'expense', 'prize_payout',
                               ?, 'Venmo', 'active', ?)""",
                    (
                        event_date, f"Payout: {p['category']} — {event_name}",
                        round(float(p["amount"]), 2),
                        f"payout-{p['id']}",
                        "",  # customer name filled in below
                        f"PAYOUT-{p['id']}",
                        -round(float(p["amount"]), 2),  # signed negative (expense)
                        event_name,
                    ),
                )
                new_txn_id = cur.lastrowid
                conn.execute(
                    "UPDATE tgf_payouts SET acct_transaction_id = ? WHERE id = ?",
                    (new_txn_id, p["id"]),
                )
                # Denormalize customer name onto the acct_transaction
                conn.execute(
                    """UPDATE acct_transactions SET customer = (
                           SELECT first_name || ' ' || last_name FROM customers WHERE customer_id = ?
                       ) WHERE id = ?""",
                    (customer_id, new_txn_id),
                )
    return matched


def _match_pending_payouts_to_new_venmo(conn: sqlite3.Connection) -> int:
    """Reverse reconciliation: Venmo prize_payouts that just arrived may cover
    previously-pending tgf_payouts. Link them.

    Groups pending payouts by (customer_id, event_id), sums each group, and
    looks for a single Venmo prize_payout that matches the sum. When matched:
      - Reverses all pending entries in the group (status='reversed')
      - Points every tgf_payouts row in the group to the Venmo entry
      - Sets paid_at

    Returns count of newly-matched payouts (individual rows, not groups).
    """
    pending = conn.execute(
        """SELECT p.id as payout_id, p.event_id, p.customer_id, p.amount,
                  p.acct_transaction_id,
                  e.event_date, e.name as event_name
           FROM tgf_payouts p
           JOIN tgf_events e ON e.id = p.event_id
           JOIN acct_transactions t ON t.id = p.acct_transaction_id
           WHERE t.source = 'pending' AND COALESCE(t.status, 'active') = 'active'"""
    ).fetchall()
    if not pending:
        return 0

    # Group by (event_id, customer_id)
    groups: dict[tuple[int, int], list] = {}
    for p in pending:
        key = (p["event_id"], p["customer_id"])
        groups.setdefault(key, []).append(dict(p))

    matched = 0
    for (event_id, customer_id), rows in groups.items():
        group_sum = round(sum(float(r["amount"]) for r in rows), 2)
        event_date = rows[0]["event_date"]

        venmo = conn.execute(
            """SELECT t.id, t.date FROM acct_transactions t
               WHERE t.source != 'pending'
                 AND t.category = 'prize_payout'
                 AND COALESCE(t.status, 'active') IN ('active', 'reconciled')
                 AND ROUND(ABS(t.amount), 2) = ?
                 AND DATE(t.date) >= DATE(?)
                 AND DATE(t.date) <= DATE(?, '+7 days')
                 AND NOT EXISTS (
                   SELECT 1 FROM tgf_payouts existing
                   WHERE existing.acct_transaction_id = t.id
                 )
                 AND (
                   EXISTS (
                     SELECT 1 FROM customers c
                     WHERE c.customer_id = ?
                       AND LOWER(t.customer) = LOWER(c.first_name || ' ' || c.last_name)
                   )
                   OR
                   EXISTS (
                     SELECT 1 FROM customer_aliases a
                     JOIN customers c2 ON LOWER(c2.first_name || ' ' || c2.last_name) = LOWER(a.customer_name)
                     WHERE a.alias_type = 'name'
                       AND LOWER(a.alias_value) = LOWER(t.customer)
                       AND c2.customer_id = ?
                   )
                 )
               ORDER BY t.date ASC LIMIT 1""",
            (group_sum, event_date, event_date, customer_id, customer_id),
        ).fetchone()
        if not venmo:
            continue

        # Reverse every pending placeholder in this group + link to the Venmo
        for r in rows:
            conn.execute(
                "UPDATE acct_transactions SET status = 'reversed' WHERE id = ?",
                (r["acct_transaction_id"],),
            )
            conn.execute(
                "UPDATE tgf_payouts SET acct_transaction_id = ?, paid_at = ? WHERE id = ?",
                (venmo["id"], venmo["date"], r["payout_id"]),
            )
            matched += 1

    if matched:
        logger.info("Matched %d pending payouts to Venmo payments (grouped by customer+event)", matched)
    return matched


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
                order_time       TEXT,
                total_amount     TEXT,
                item_name        TEXT NOT NULL,
                item_price       TEXT,
                quantity         INTEGER DEFAULT 1,
                chapter          TEXT,
                course           TEXT,
                handicap         TEXT,
                side_games       TEXT,
                tee_choice       TEXT,
                user_status      TEXT,
                post_game        TEXT,
                returning_or_new TEXT,
                partner_request  TEXT,
                fellowship       TEXT,
                notes            TEXT,
                holes            TEXT,
                address          TEXT,
                address2         TEXT,
                city             TEXT,
                state            TEXT,
                zip              TEXT,
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

        # Items migrations — add columns that may not exist on older databases
        for col, col_type in [
            ("customer_email", "TEXT"), ("customer_phone", "TEXT"),
            ("transaction_status", "TEXT DEFAULT 'active'"),
            ("credit_note", "TEXT"),
            ("transferred_from_id", "INTEGER"), ("transferred_to_id", "INTEGER"),
            ("chapter", "TEXT"), ("has_handicap", "TEXT"),
            ("transaction_fees", "TEXT"), ("partner_request", "TEXT"),
            ("notes", "TEXT"), ("order_time", "TEXT"),
            ("first_name", "TEXT"), ("last_name", "TEXT"),
            ("middle_name", "TEXT"), ("suffix", "TEXT"),
            ("holes", "TEXT"),
            ("address", "TEXT"), ("address2", "TEXT"),
            ("city", "TEXT"), ("state", "TEXT"), ("zip", "TEXT"),
            ("wd_reason", "TEXT"), ("wd_note", "TEXT"),
            ("wd_credits", "TEXT"), ("credit_amount", "TEXT"),
            ("parent_item_id", "INTEGER"), ("parent_snapshot", "TEXT"),
            ("customer_id", "INTEGER"),
            ("archived", "INTEGER DEFAULT 0"),
            ("coupon_code", "TEXT"), ("coupon_amount", "TEXT"),
            ("event_id", "INTEGER REFERENCES events(id)"),
        ]:
            try:
                conn.execute(f"ALTER TABLE items ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

        # Processed emails table — tracks ALL email UIDs we've already sent to
        # the AI, even if no items were extracted.  Prevents re-parsing the same
        # email every 15 minutes and burning API credits.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_emails (
                email_uid   TEXT PRIMARY KEY,
                processed_at TEXT DEFAULT (datetime('now')),
                items_found  INTEGER DEFAULT 0
            )
        """)

        # Backfill processed_emails from existing items table
        conn.execute("""
            INSERT OR IGNORE INTO processed_emails (email_uid, items_found)
            SELECT DISTINCT email_uid, COUNT(*) FROM items
            WHERE email_uid IS NOT NULL AND email_uid != ''
            GROUP BY email_uid
        """)

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

        # Track customers whose name parsing has failed repeatedly
        conn.execute("""
            CREATE TABLE IF NOT EXISTS name_parse_failures (
                customer_name TEXT PRIMARY KEY,
                attempts      INTEGER DEFAULT 0,
                last_attempt  TEXT DEFAULT (datetime('now'))
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
                chapter     TEXT,
                event_type  TEXT DEFAULT 'event',
                format      TEXT,
                start_type  TEXT,
                start_time  TEXT,
                tee_time_count INTEGER,
                tee_time_interval INTEGER,
                start_time_18 TEXT,
                start_type_18 TEXT,
                tee_time_count_18 INTEGER,
                tee_direction TEXT DEFAULT 'First Tee',
                tee_direction_18 TEXT DEFAULT 'First Tee',
                course_cost REAL,
                tgf_markup REAL,
                side_game_fee REAL,
                transaction_fee_pct REAL DEFAULT 3.5,
                created_at  TEXT DEFAULT (datetime('now'))
            )
            """
        )

        # Events migrations — columns that may not exist on older databases
        for col, col_type in [
            ("course_cost_9", "REAL"), ("course_cost_18", "REAL"),
            ("tgf_markup_9", "REAL"), ("tgf_markup_18", "REAL"),
            ("tgf_markup_final", "REAL"), ("tgf_markup_final_9", "REAL"), ("tgf_markup_final_18", "REAL"),
            ("side_game_fee_9", "REAL"), ("side_game_fee_18", "REAL"),
            ("course_surcharge", "REAL DEFAULT 0"),
            ("course_cost_breakdown", "TEXT"), ("course_cost_breakdown_9", "TEXT"), ("course_cost_breakdown_18", "TEXT"),
            ("status", "TEXT DEFAULT 'active'"),
            ("status_reason", "TEXT"),
            ("rescheduled_to_event_id", "INTEGER"),
            ("status_changed_at", "TEXT"),
            ("per_game_addon", "REAL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE events ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

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
            "CREATE INDEX IF NOT EXISTS idx_items_event_id ON items(event_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_event_date ON events(event_date DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rsvps_matched_event ON rsvps(matched_event)"
        )

        # rsvps migration — columns added after initial release
        for col, col_type in [
            ("credit_notified_at", "TEXT"),
            ("customer_id", "INTEGER REFERENCES customers(customer_id)"),
        ]:
            try:
                conn.execute(f"ALTER TABLE rsvps ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rsvps_player_email ON rsvps(player_email)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rsvps_customer_id ON rsvps(customer_id)"
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

        # ── Dimension Tables: Chapters + Courses ────────────────────
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chapters (
                chapter_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                name        VARCHAR(100) NOT NULL UNIQUE,
                short_code  VARCHAR(10),
                timezone    VARCHAR(50) DEFAULT 'America/Chicago',
                status      VARCHAR(20) NOT NULL DEFAULT 'active',
                created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS courses (
                course_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name        VARCHAR(200) NOT NULL UNIQUE,
                chapter_id  INTEGER REFERENCES chapters(chapter_id),
                city        VARCHAR(100),
                state       VARCHAR(2),
                status      VARCHAR(20) NOT NULL DEFAULT 'active',
                created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS course_aliases (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id   INTEGER NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
                alias_name  TEXT NOT NULL UNIQUE,
                created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # MVP unlinks — events explicitly excluded from same-day TGF MVP combining
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_mvp_unlinks (
                event_name  TEXT PRIMARY KEY,
                unlinked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Parse warnings — flagged items that may have been parsed incorrectly
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS parse_warnings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                email_uid    TEXT,
                order_id     TEXT,
                customer     TEXT,
                item_name    TEXT,
                warning_code TEXT NOT NULL,
                message      TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'open'
                    CHECK(status IN ('open', 'dismissed', 'resolved')),
                created_at   TEXT DEFAULT (datetime('now')),
                UNIQUE(email_uid, warning_code, item_name)
            )
            """
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

        # Handicap rounds — 9-hole round data for WHS handicap index calculation
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS handicap_rounds (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name    TEXT NOT NULL,
                round_date     TEXT NOT NULL,
                round_id       TEXT,
                course_name    TEXT,
                tee_name       TEXT,
                adjusted_score INTEGER NOT NULL,
                rating         REAL NOT NULL,
                slope          INTEGER NOT NULL,
                differential   REAL,
                created_at     TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_handicap_rounds_player ON handicap_rounds(player_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_handicap_rounds_date ON handicap_rounds(round_date DESC)"
        )

        # Handicap player → customer links
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS handicap_player_links (
                player_name   TEXT PRIMARY KEY,
                customer_name TEXT,
                linked_at     TEXT DEFAULT (datetime('now'))
            )
            """
        )
        try:
            conn.execute("ALTER TABLE handicap_player_links ADD COLUMN customer_id INTEGER")
        except sqlite3.OperationalError:
            pass

        # Handicap settings — configurable calculation parameters
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS handicap_settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
        )

        # App-level key-value settings (persists across deploys on Railway volume)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
        )

        # Season contest enrollments — tracks who's in NET Points Race,
        # GROSS Points Race, City Match Play, etc.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS season_contests (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name   TEXT NOT NULL,
                contest_type    TEXT NOT NULL,
                chapter         TEXT,
                season          TEXT,
                source_item_id  INTEGER,
                enrolled_at     TEXT DEFAULT (datetime('now')),
                UNIQUE(customer_name, contest_type, chapter, season)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_season_contests_customer ON season_contests(customer_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_season_contests_type ON season_contests(contest_type)"
        )

        # ── Customer identity tables ──────────────────────────────────
        # Core customer record.  Mirrors the TGF Platform MVP users
        # schema so that merging the two systems later is a clean lookup.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                customer_id          INTEGER PRIMARY KEY AUTOINCREMENT,
                platform_user_id     INTEGER,
                first_name           VARCHAR(100) NOT NULL,
                last_name            VARCHAR(100) NOT NULL,
                phone                VARCHAR(30),
                chapter              VARCHAR(50),
                ghin_number          VARCHAR(20),
                current_player_status VARCHAR(30)
                                     CHECK (current_player_status IN (
                                         'active_member', 'expired_member',
                                         'active_guest', 'inactive', 'first_timer'
                                     )),
                first_timer_ever     INTEGER,
                acquisition_source   VARCHAR(50),
                account_status       VARCHAR(20) NOT NULL DEFAULT 'active'
                                     CHECK (account_status IN (
                                         'active', 'inactive', 'banned'
                                     )),
                venmo_username       VARCHAR(50),
                created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Customer roles — multi-role support (maps to Platform user_types)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_roles (
                role_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL
                            REFERENCES customers(customer_id)
                            ON DELETE CASCADE,
                role_type   VARCHAR(30) NOT NULL
                            CHECK (role_type IN (
                                'golfer', 'manager', 'admin', 'owner',
                                'course_contact', 'sponsor', 'vendor'
                            )),
                granted_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                granted_by  INTEGER REFERENCES customers(customer_id),
                UNIQUE(customer_id, role_type)
            )
            """
        )

        # Multiple emails per customer.
        # is_primary  = the canonical identity email (max one per customer).
        # is_golf_genius = the email used for Golf Genius handicap exports
        #                  (max one per customer).
        # These can be the same address or different ones.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_emails (
                email_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id     INTEGER NOT NULL
                                REFERENCES customers(customer_id)
                                ON DELETE CASCADE,
                email           VARCHAR(200) NOT NULL,
                is_primary      INTEGER NOT NULL DEFAULT 0,
                is_golf_genius  INTEGER NOT NULL DEFAULT 0,
                label           VARCHAR(50),
                created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(customer_id, email)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_customer_emails_customer "
            "ON customer_emails(customer_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_customer_emails_email "
            "ON customer_emails(email)"
        )
        # At most one primary email per customer
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_customer_emails_primary "
            "ON customer_emails(customer_id, is_primary) "
            "WHERE is_primary = 1"
        )
        # At most one Golf Genius email per customer
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_customer_emails_gg "
            "ON customer_emails(customer_id, is_golf_genius) "
            "WHERE is_golf_genius = 1"
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

        # Normalize empty-string phone fields to NULL in customers table
        phone_cleaned = conn.execute(
            "UPDATE customers SET phone = NULL WHERE phone = '' OR phone = ' '"
        ).rowcount
        if phone_cleaned:
            logger.info("Normalized %d empty phone fields to NULL in customers table", phone_cleaned)

        # Also normalize in items table
        items_phone_cleaned = conn.execute(
            "UPDATE items SET customer_phone = NULL WHERE customer_phone = '' OR customer_phone = ' '"
        ).rowcount
        if items_phone_cleaned:
            logger.info("Normalized %d empty customer_phone fields to NULL in items table", items_phone_cleaned)

        # Add venmo_username column to customers table (migration for existing DBs)
        try:
            conn.execute("ALTER TABLE customers ADD COLUMN venmo_username VARCHAR(50)")
        except sqlite3.OperationalError:
            pass

        # Add company_name column for vendor/company customers
        try:
            conn.execute("ALTER TABLE customers ADD COLUMN company_name VARCHAR(200)")
        except sqlite3.OperationalError:
            pass

        # One-time migration: eliminate tgf_golfers table, unify into customers.
        # - Adds customer_id column to tgf_payouts
        # - Backfills customer_id from golfer→customer mapping (creates missing customers)
        # - Copies any remaining venmo_username / chapter data to customers
        # - Rebuilds tgf_payouts without golfer_id
        # - Drops tgf_golfers
        try:
            _migrate_eliminate_tgf_golfers(conn)
        except Exception as e:
            logger.warning("tgf_golfers elimination migration failed: %s", e)

        # One-time cleanup: merge duplicate payout customers created by migration
        try:
            _migrate_dedupe_payout_customers(conn)
        except Exception as e:
            logger.warning("Payout customer dedup migration failed: %s", e)

        # Rename 'member' role → 'golfer' (no-op if already migrated).
        # Must run before the seed so the seed sees the new CHECK constraint.
        try:
            _migrate_rename_member_role_to_golfer(conn)
        except Exception as e:
            logger.warning("Member→golfer role rename migration failed: %s", e)

        # Relabel credit-pool items (excess + overpayment) with descriptive names.
        try:
            _migrate_relabel_credit_pool_items(conn)
        except Exception as e:
            logger.warning("Credit-pool relabel migration failed: %s", e)

        # Move non-canonical text from items.side_games to items.notes so the
        # Side Games column stays NET/GROSS/BOTH/NONE only.
        try:
            _migrate_move_noncanonical_side_games_to_notes(conn)
        except Exception as e:
            logger.warning("side_games → notes migration failed: %s", e)

        # Seed customer_roles junction + backfill first_timer_ever
        try:
            _migrate_seed_customer_roles(conn)
        except Exception as e:
            logger.warning("Customer roles seed migration failed: %s", e)

        # Steps 4+5: Create chapters + courses dimension tables
        try:
            _migrate_create_dim_tables(conn)
        except Exception as e:
            logger.warning("Dim table creation failed: %s", e)

        # Create aliases for the dedup-migrated names (so _lookup_customer_id
        # can resolve them during normalization below)
        try:
            _migrate_create_dedup_aliases(conn)
        except Exception as e:
            logger.warning("Dedup alias creation failed: %s", e)

        # Normalize Venmo customer names to canonical so payout matching works
        try:
            _migrate_normalize_venmo_customer_names(conn)
        except Exception as e:
            logger.warning("Venmo customer name normalization failed: %s", e)

        # Step 3: wire tgf_payouts into acct_transactions ledger
        try:
            _migrate_wire_payouts_to_ledger(conn)
        except Exception as e:
            logger.warning("Payouts-to-ledger migration failed: %s", e)

        # Remove duplicate expense_transactions rows
        try:
            _migrate_dedup_expense_transactions(conn)
        except Exception as e:
            logger.warning("Expense transaction dedup migration failed: %s", e)

        # Add member_plus to customers.current_player_status CHECK constraint
        try:
            _migrate_add_member_plus_status(conn)
        except Exception as e:
            logger.warning("member_plus status migration failed: %s", e)

        # Normalize all-uppercase customer names to proper case (idempotent)
        try:
            _migrate_normalize_customer_name_case(conn)
        except Exception as e:
            logger.warning("Customer name case normalization failed: %s", e)

        # Reconcile customers.current_player_status against item history
        try:
            _migrate_autocorrect_player_status(conn)
        except Exception as e:
            logger.warning("player_status autocorrect failed: %s", e)

        # Remap legacy chapter values to the canonical chapter list
        try:
            _migrate_canonicalize_chapters(conn)
        except Exception as e:
            logger.warning("chapter canonicalization failed: %s", e)

        # Customer memberships table + backfill from parsed `membership` items.
        # Idempotent — UNIQUE(customer_id, started_at) prevents dupes.
        try:
            from .memberships import (
                ensure_membership_tables,
                backfill_memberships_from_items,
                sync_player_status_with_terms,
            )
            ensure_membership_tables(conn)
            backfill_memberships_from_items(conn)
            # Reconcile current_player_status against the term data: lapsed
            # terms → expired_member, renewed terms → active_member. Runs
            # AFTER backfill so newly-seeded terms are considered.
            sync_player_status_with_terms(conn)
        except Exception as e:
            logger.warning("customer_memberships migration/backfill failed: %s", e)

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

        # ── Accounting module tables ──────────────────────────────
        # Multi-entity bookkeeping: entities, categories, accounts,
        # transactions with split support, tags, and recurring templates.

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acct_entities (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                short_name  TEXT NOT NULL UNIQUE,
                color       TEXT DEFAULT '#2563eb',
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT DEFAULT (datetime('now'))
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acct_categories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id   INTEGER,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                parent_id   INTEGER,
                icon        TEXT,
                is_active   INTEGER DEFAULT 1,
                sort_order  INTEGER DEFAULT 0,
                FOREIGN KEY (entity_id) REFERENCES acct_entities(id),
                FOREIGN KEY (parent_id) REFERENCES acct_categories(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_acct_categories_entity ON acct_categories(entity_id)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acct_accounts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id       INTEGER,
                name            TEXT NOT NULL,
                account_type    TEXT NOT NULL
                    CHECK(account_type IN ('checking', 'savings', 'credit_card', 'cash', 'venmo', 'paypal', 'other')),
                institution     TEXT,
                last_four       TEXT,
                opening_balance REAL DEFAULT 0,
                is_active       INTEGER DEFAULT 1,
                created_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (entity_id) REFERENCES acct_entities(id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acct_transactions (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                date                   TEXT NOT NULL,
                description            TEXT NOT NULL,
                total_amount           REAL NOT NULL,
                type                   TEXT NOT NULL CHECK(type IN ('income', 'expense', 'transfer')),
                account_id             INTEGER,
                transfer_to_account_id INTEGER,
                notes                  TEXT,
                receipt_path           TEXT,
                source                 TEXT DEFAULT 'manual',
                source_ref             TEXT,
                is_reconciled          INTEGER DEFAULT 0,
                created_at             TEXT DEFAULT (datetime('now')),
                updated_at             TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (account_id) REFERENCES acct_accounts(id),
                FOREIGN KEY (transfer_to_account_id) REFERENCES acct_accounts(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_acct_txn_date ON acct_transactions(date DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_acct_txn_account ON acct_transactions(account_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_acct_txn_type ON acct_transactions(type)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acct_splits (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id  INTEGER NOT NULL,
                entity_id       INTEGER NOT NULL,
                category_id     INTEGER,
                amount          REAL NOT NULL,
                memo            TEXT,
                FOREIGN KEY (transaction_id) REFERENCES acct_transactions(id) ON DELETE CASCADE,
                FOREIGN KEY (entity_id) REFERENCES acct_entities(id),
                FOREIGN KEY (category_id) REFERENCES acct_categories(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_acct_splits_txn ON acct_splits(transaction_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_acct_splits_entity ON acct_splits(entity_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_acct_splits_category ON acct_splits(category_id)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acct_tags (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  TEXT NOT NULL UNIQUE,
                color TEXT DEFAULT '#6b7280'
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acct_transaction_tags (
                transaction_id INTEGER NOT NULL,
                tag_id         INTEGER NOT NULL,
                PRIMARY KEY (transaction_id, tag_id),
                FOREIGN KEY (transaction_id) REFERENCES acct_transactions(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES acct_tags(id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acct_recurring (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                amount      REAL NOT NULL,
                type        TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                entity_id   INTEGER NOT NULL,
                category_id INTEGER,
                account_id  INTEGER,
                frequency   TEXT NOT NULL CHECK(frequency IN ('weekly', 'biweekly', 'monthly', 'quarterly', 'yearly')),
                next_date   TEXT NOT NULL,
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (entity_id) REFERENCES acct_entities(id),
                FOREIGN KEY (category_id) REFERENCES acct_categories(id),
                FOREIGN KEY (account_id) REFERENCES acct_accounts(id)
            )
            """
        )

        # Seed default entities on first run
        existing_entities = conn.execute("SELECT COUNT(*) as cnt FROM acct_entities").fetchone()
        if existing_entities["cnt"] == 0:
            conn.executemany(
                "INSERT INTO acct_entities (name, short_name, color) VALUES (?, ?, ?)",
                [
                    ("The Golf Fellowship", "TGF", "#16a34a"),
                    ("Personal", "Personal", "#2563eb"),
                ],
            )

        # Seed default categories on first run
        existing_cats = conn.execute("SELECT COUNT(*) as cnt FROM acct_categories").fetchone()
        if existing_cats["cnt"] == 0:
            _seed_acct_categories(conn)

        # ── Accounting schema migrations ──
        # Add event_id to splits (links accounting transactions to TGF events)
        for col, col_type in [
            ("event_id", "INTEGER"),
        ]:
            try:
                conn.execute(f"ALTER TABLE acct_splits ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

        conn.execute("CREATE INDEX IF NOT EXISTS idx_acct_splits_event ON acct_splits(event_id)")

        # ── acct_transactions: single-source-of-truth columns ──
        for col, col_type, default in [
            ("item_id", "INTEGER", None),
            ("event_name", "TEXT", None),
            ("customer", "TEXT", None),
            ("order_id", "TEXT", None),
            ("entry_type", "TEXT", None),
            ("category", "TEXT", None),
            ("amount", "REAL", None),
            ("account", "TEXT", None),
            ("status", "TEXT", "'active'"),
            ("reconciled_batch_id", "INTEGER", None),
        ]:
            try:
                default_clause = f" DEFAULT {default}" if default else ""
                conn.execute(
                    f"ALTER TABLE acct_transactions ADD COLUMN {col} {col_type}{default_clause}"
                )
            except sqlite3.OperationalError:
                pass

        conn.execute("CREATE INDEX IF NOT EXISTS idx_acct_txn_item ON acct_transactions(item_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_acct_txn_event_name ON acct_transactions(event_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_acct_txn_entry_type ON acct_transactions(entry_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_acct_txn_status ON acct_transactions(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_acct_txn_source_ref ON acct_transactions(source_ref)")

        # ── Identity FK: customer_id on acct_transactions ────────────
        try:
            conn.execute("ALTER TABLE acct_transactions ADD COLUMN customer_id INTEGER")
        except sqlite3.OperationalError:
            pass
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_acct_txn_customer_id ON acct_transactions(customer_id)"
        )

        # ── Order-level GoDaddy columns ─────────────────────────────
        for col, col_type in [
            ("net_deposit", "REAL"),
            ("merchant_fee", "REAL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE acct_transactions ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

        # ── Unified financial model migrations (Issue #242) ──
        for col, col_type, default in [
            ("payment_method", "TEXT", "'godaddy'"),
            ("acct_transaction_id", "INTEGER", None),
        ]:
            try:
                default_clause = f" DEFAULT {default}" if default else ""
                conn.execute(
                    f"ALTER TABLE acct_allocations ADD COLUMN {col} {col_type}{default_clause}"
                )
            except sqlite3.OperationalError:
                pass

        # ── event_id FK on tables that reference events by string name ──
        _event_id_migrations = [
            ("acct_allocations",     "INTEGER REFERENCES events(id)"),
            ("godaddy_order_splits", "INTEGER REFERENCES events(id)"),
            ("rsvps",                "INTEGER REFERENCES events(id)"),
            ("expense_transactions", "INTEGER REFERENCES events(id)"),
            ("message_log",          "INTEGER REFERENCES events(id)"),
            ("contractor_payouts",   "INTEGER REFERENCES events(id)"),
        ]
        for tbl, col_type in _event_id_migrations:
            try:
                conn.execute(f"ALTER TABLE {tbl} ADD COLUMN event_id {col_type}")
            except sqlite3.OperationalError:
                pass  # column already exists

        # Seed unified financial model categories if missing
        _seed_unified_financial_categories(conn)

        # Account-level rules/heuristics for AI bookkeeper
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acct_account_rules (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id      INTEGER NOT NULL,
                rule_type       TEXT NOT NULL,
                rule_value      TEXT NOT NULL,
                created_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (account_id) REFERENCES acct_accounts(id),
                UNIQUE(account_id, rule_type)
            )
            """
        )

        # Keyword-based categorization rules (user-defined)
        # e.g. "if description contains 'Winnings' → category 'Side Game Payouts', entity 'TGF'"
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acct_keyword_rules (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword         TEXT NOT NULL,
                match_type      TEXT NOT NULL DEFAULT 'contains',
                category_id     INTEGER,
                entity_id       INTEGER,
                is_active       INTEGER DEFAULT 1,
                created_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (category_id) REFERENCES acct_categories(id),
                FOREIGN KEY (entity_id) REFERENCES acct_entities(id)
            )
            """
        )

        # Allocation tracking — breaks down every GoDaddy order's dollars
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acct_allocations (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id            TEXT NOT NULL,
                item_id             INTEGER REFERENCES items(id),
                event_name          TEXT,
                chapter             TEXT,
                allocation_date     TEXT,
                player_count        INTEGER DEFAULT 1,
                course_payable      REAL DEFAULT 0,
                course_surcharge    REAL DEFAULT 0,
                prize_pool          REAL DEFAULT 0,
                tgf_operating       REAL DEFAULT 0,
                godaddy_fee         REAL DEFAULT 0,
                tax_reserve         REAL DEFAULT 0,
                total_collected     REAL DEFAULT 0,
                allocation_status   TEXT DEFAULT 'pending'
                    CHECK(allocation_status IN ('pending', 'complete', 'needs_course_cost')),
                notes               TEXT,
                created_at          TEXT DEFAULT (datetime('now')),
                UNIQUE(order_id, item_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_acct_alloc_order ON acct_allocations(order_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_acct_alloc_event ON acct_allocations(event_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_acct_alloc_date ON acct_allocations(allocation_date)"
        )

        # ── Expense tracking tables ──────────────────────────────────
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expense_transactions (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                email_uid         TEXT UNIQUE,
                source_type       TEXT,
                merchant          TEXT,
                amount            REAL,
                transaction_date  TEXT,
                account_last4     TEXT,
                account_name      TEXT,
                transaction_type  TEXT DEFAULT 'expense',
                category          TEXT,
                entity            TEXT DEFAULT 'TGF',
                event_name        TEXT,
                customer_id       INTEGER REFERENCES customers(customer_id),
                confidence        INTEGER DEFAULT 0,
                review_status     TEXT DEFAULT 'pending'
                    CHECK(review_status IN ('pending', 'approved', 'corrected', 'ignored')),
                reviewed_at       TEXT,
                reviewed_by       TEXT,
                notes             TEXT,
                raw_extract       TEXT,
                created_at        TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expense_txn_date ON expense_transactions(transaction_date)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expense_txn_status ON expense_transactions(review_status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expense_txn_source ON expense_transactions(source_type)"
        )
        # Link promoted expense rows back to their acct_transactions entry
        try:
            conn.execute(
                "ALTER TABLE expense_transactions ADD COLUMN acct_transaction_id INTEGER"
            )
        except sqlite3.OperationalError:
            pass  # column already exists
        # Ensure account_last4 and account_name columns exist (may be missing on older DBs)
        try:
            conn.execute("ALTER TABLE expense_transactions ADD COLUMN account_last4 TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        try:
            conn.execute("ALTER TABLE expense_transactions ADD COLUMN account_name TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        # Add account_id FK so expense rows can be filtered by account like acct_transactions
        try:
            conn.execute(
                "ALTER TABLE expense_transactions ADD COLUMN account_id INTEGER REFERENCES acct_accounts(id)"
            )
        except sqlite3.OperationalError:
            pass  # column already exists
        # Track when a Venmo IN payment is auto-matched to a credit-transfer balance-due item
        try:
            conn.execute(
                "ALTER TABLE expense_transactions ADD COLUMN matched_item_id INTEGER REFERENCES items(id)"
            )
        except sqlite3.OperationalError:
            pass  # column already exists
        # Capture the OTHER party's Venmo @handle from the notification email (sender for IN, recipient for OUT)
        try:
            conn.execute(
                "ALTER TABLE expense_transactions ADD COLUMN other_party_handle TEXT"
            )
        except sqlite3.OperationalError:
            pass  # column already exists
        # Backfill account_id: match by last_four first (reliable), then by name
        try:
            conn.execute("""
                UPDATE expense_transactions
                SET account_id = (
                    SELECT a.id FROM acct_accounts a
                    WHERE (expense_transactions.account_last4 IS NOT NULL
                           AND a.last_four = expense_transactions.account_last4)
                       OR (expense_transactions.account_last4 IS NULL
                           AND expense_transactions.account_name IS NOT NULL
                           AND UPPER(a.name) = UPPER(expense_transactions.account_name))
                    ORDER BY CASE WHEN a.last_four IS NOT NULL
                                  AND a.last_four = expense_transactions.account_last4
                             THEN 0 ELSE 1 END
                    LIMIT 1
                )
                WHERE account_id IS NULL
                  AND (account_last4 IS NOT NULL OR account_name IS NOT NULL)
            """)
        except sqlite3.OperationalError:
            pass  # skip backfill if columns not yet available (old schema)

        # Backfill: promoted Venmo "received" rows were previously written with
        # entry_type='expense' — fix them so they classify as income in P&L.
        try:
            conn.execute("""
                UPDATE acct_transactions
                SET entry_type = 'income'
                WHERE entry_type = 'expense'
                  AND id IN (
                      SELECT acct_transaction_id FROM expense_transactions
                      WHERE transaction_type = 'received'
                        AND acct_transaction_id IS NOT NULL
                  )
            """)
        except sqlite3.OperationalError:
            pass  # skip if columns not yet available (old schema)

        # Backfill: deduplicate Venmo balance-due ledger entries.
        # _sync_expense_ledger_entry historically promoted the expense_transaction
        # to an exp-promoted-{id} row, then auto_match_venmo_inbound_to_balance_due
        # wrote a SECOND venmo-bd-{id} row, so each matched payment was income twice.
        # Soft-delete the exp-promoted row and re-point expense_transactions at the
        # venmo-bd row.
        try:
            conn.execute("""
                UPDATE acct_transactions
                SET status = 'reversed', updated_at = datetime('now')
                WHERE COALESCE(status, 'active') = 'active'
                  AND source_ref LIKE 'exp-promoted-%'
                  AND id IN (
                      SELECT et.acct_transaction_id
                      FROM expense_transactions et
                      WHERE et.matched_item_id IS NOT NULL
                        AND et.acct_transaction_id IS NOT NULL
                        AND EXISTS (
                            SELECT 1 FROM acct_transactions vbd
                            WHERE vbd.source_ref = 'venmo-bd-' || et.id
                              AND COALESCE(vbd.status, 'active') = 'active'
                        )
                  )
            """)
            conn.execute("""
                UPDATE expense_transactions
                SET acct_transaction_id = (
                    SELECT vbd.id FROM acct_transactions vbd
                    WHERE vbd.source_ref = 'venmo-bd-' || expense_transactions.id
                      AND COALESCE(vbd.status, 'active') = 'active'
                    LIMIT 1
                )
                WHERE matched_item_id IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM acct_transactions vbd
                      WHERE vbd.source_ref = 'venmo-bd-' || expense_transactions.id
                        AND COALESCE(vbd.status, 'active') = 'active'
                  )
            """)
        except sqlite3.OperationalError:
            pass  # skip if columns not yet available (old schema)

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS action_items (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                email_uid         TEXT,
                subject           TEXT,
                from_name         TEXT,
                from_email        TEXT,
                summary           TEXT,
                urgency           TEXT DEFAULT 'medium',
                category          TEXT DEFAULT 'other',
                email_date        TEXT,
                status            TEXT DEFAULT 'open'
                    CHECK(status IN ('open', 'in_progress', 'completed', 'dismissed')),
                completed_at      TEXT,
                completed_by      TEXT,
                resolution_notes  TEXT,
                confidence        INTEGER DEFAULT 0,
                created_at        TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_action_items_status ON action_items(status)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS extraction_corrections (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_transaction_id  INTEGER REFERENCES expense_transactions(id),
                field_corrected         TEXT,
                original_value          TEXT,
                corrected_value         TEXT,
                merchant                TEXT,
                corrected_at            TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_corrections_merchant ON extraction_corrections(merchant)"
        )

        # COO manual values — simple key-value store for account balances, debts
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS coo_manual_values (
                key        TEXT PRIMARY KEY,
                value      REAL,
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
        )

        # ── Chart of Accounts & General Ledger ───────────────────────
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chart_of_accounts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                code            TEXT UNIQUE NOT NULL,
                name            TEXT NOT NULL,
                account_type    TEXT NOT NULL
                    CHECK(account_type IN ('income', 'expense', 'asset', 'liability', 'equity')),
                schedule_c_line TEXT,
                parent_code     TEXT,
                is_active       INTEGER DEFAULT 1,
                created_at      TEXT DEFAULT (datetime('now'))
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS general_ledger (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date          TEXT NOT NULL,
                description         TEXT NOT NULL,
                account_code        TEXT NOT NULL REFERENCES chart_of_accounts(code),
                debit               REAL DEFAULT 0,
                credit              REAL DEFAULT 0,
                source_type         TEXT,
                source_id           INTEGER,
                order_id            TEXT,
                reconciled          INTEGER DEFAULT 0,
                reconciled_date     TEXT,
                reconciliation_id   INTEGER,
                created_at          TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_date ON general_ledger(entry_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_account ON general_ledger(account_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_reconciled ON general_ledger(reconciled)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bank_statement_rows (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                import_id           TEXT NOT NULL,
                bank                TEXT,
                account_last4       TEXT,
                transaction_date    TEXT,
                description         TEXT,
                amount              REAL,
                balance             REAL,
                transaction_type    TEXT,
                matched_source      TEXT,
                matched_id          INTEGER,
                reconciled          INTEGER DEFAULT 0,
                created_at          TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_rows_import ON bank_statement_rows(import_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_rows_date ON bank_statement_rows(transaction_date)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS period_closings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                period          TEXT NOT NULL,
                closed_at       TEXT,
                closed_by       TEXT,
                total_income    REAL,
                total_expenses  REAL,
                net             REAL,
                tax_reserve     REAL,
                notes           TEXT
            )
            """
        )

        # ── Bank reconciliation tables ──
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bank_accounts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL UNIQUE,
                account_type TEXT NOT NULL
                    CHECK(account_type IN ('checking', 'venmo', 'credit_card', 'cash')),
                is_active    INTEGER DEFAULT 1,
                created_at   TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bank_deposits (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id      INTEGER NOT NULL,
                deposit_date    TEXT NOT NULL,
                amount          REAL NOT NULL,
                description     TEXT,
                source          TEXT,
                status          TEXT DEFAULT 'unmatched'
                    CHECK(status IN ('unmatched', 'partial', 'matched')),
                import_batch_id TEXT,
                raw_data        TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (account_id) REFERENCES bank_accounts(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_dep_date ON bank_deposits(deposit_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_dep_status ON bank_deposits(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_dep_batch ON bank_deposits(import_batch_id)")
        # Migration: add dismissed column for internal transfers / not-applicable deposits
        _bank_dep_cols = [r[1] for r in conn.execute("PRAGMA table_info(bank_deposits)").fetchall()]
        if "dismissed" not in _bank_dep_cols:
            conn.execute("ALTER TABLE bank_deposits ADD COLUMN dismissed INTEGER NOT NULL DEFAULT 0")
            conn.execute("ALTER TABLE bank_deposits ADD COLUMN dismiss_reason TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reconciliation_matches (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_deposit_id     INTEGER NOT NULL,
                acct_transaction_id INTEGER NOT NULL,
                match_type          TEXT NOT NULL
                    CHECK(match_type IN ('auto', 'manual')),
                match_confidence    REAL,
                created_at          TEXT DEFAULT (datetime('now')),
                UNIQUE(bank_deposit_id, acct_transaction_id),
                FOREIGN KEY (bank_deposit_id) REFERENCES bank_deposits(id),
                FOREIGN KEY (acct_transaction_id) REFERENCES acct_transactions(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_recon_deposit ON reconciliation_matches(bank_deposit_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_recon_txn ON reconciliation_matches(acct_transaction_id)")

        # ── GoDaddy order-level splits ──────────────────────────────
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS godaddy_order_splits (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id  INTEGER NOT NULL,
                item_id         INTEGER,
                event_name      TEXT,
                customer        TEXT,
                split_type      TEXT NOT NULL
                    CHECK(split_type IN ('registration', 'transaction_fee', 'merchant_fee', 'coupon')),
                amount          REAL NOT NULL,
                created_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (transaction_id) REFERENCES acct_transactions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gd_splits_txn ON godaddy_order_splits(transaction_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gd_splits_item ON godaddy_order_splits(item_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gd_splits_event ON godaddy_order_splits(event_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gd_splits_type ON godaddy_order_splits(split_type)")

        # Seed default bank accounts
        for acct_name, acct_type in [("TGF Checking", "checking"), ("Venmo", "venmo")]:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO bank_accounts (name, account_type) VALUES (?, ?)",
                    (acct_name, acct_type),
                )
            except sqlite3.IntegrityError:
                pass

        # One-time migration: import_venmo_statement historically wrote
        # bank_accounts.id into bank_deposits.account_id, while every other
        # import path stores acct_accounts.id. Rewrite the legacy rows so all
        # bank_deposits.account_id values reference acct_accounts.
        try:
            ba_venmo = conn.execute(
                "SELECT id FROM bank_accounts "
                "WHERE LOWER(name) LIKE '%venmo%' OR account_type = 'venmo' "
                "ORDER BY id LIMIT 1"
            ).fetchone()
            aa_venmo = conn.execute(
                "SELECT id FROM acct_accounts "
                "WHERE is_active = 1 AND (LOWER(name) LIKE 'venmo%' OR account_type = 'venmo') "
                "ORDER BY (account_type = 'venmo') DESC, id LIMIT 1"
            ).fetchone()
            if ba_venmo and aa_venmo and ba_venmo["id"] != aa_venmo["id"]:
                conn.execute(
                    "UPDATE bank_deposits SET account_id = ? WHERE account_id = ?",
                    (aa_venmo["id"], ba_venmo["id"]),
                )
        except sqlite3.OperationalError:
            pass

        # Seed chart of accounts on first run
        existing_coa = conn.execute("SELECT COUNT(*) as cnt FROM chart_of_accounts").fetchone()
        if existing_coa["cnt"] == 0:
            _seed_chart_of_accounts(conn)

        # ── COO Agent Registry & Action Log ──────────────────────────
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS coo_agents (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name      TEXT UNIQUE NOT NULL,
                agent_role      TEXT NOT NULL,
                system_prompt   TEXT NOT NULL,
                is_active       INTEGER DEFAULT 1,
                created_at      TEXT DEFAULT (datetime('now'))
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_action_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name      TEXT NOT NULL,
                action_type     TEXT NOT NULL,
                description     TEXT NOT NULL,
                source_email_uid TEXT,
                related_item_id INTEGER,
                outcome         TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_log_name ON agent_action_log(agent_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_log_date ON agent_action_log(created_at)")

        # ── COO Chat Sessions ───────────────────────────────────────
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS coo_chat_sessions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT DEFAULT 'New Chat',
                summary         TEXT DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            )
            """
        )
        # Migration: add summary column if missing
        cols = [r[1] for r in conn.execute("PRAGMA table_info(coo_chat_sessions)").fetchall()]
        if "summary" not in cols:
            conn.execute("ALTER TABLE coo_chat_sessions ADD COLUMN summary TEXT DEFAULT ''")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS coo_chat_messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      INTEGER NOT NULL REFERENCES coo_chat_sessions(id) ON DELETE CASCADE,
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                routed_to       TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_msg_session ON coo_chat_messages(session_id)")

        # ── TGF Payouts ─────────────────────────────────────────────
        # Note: tgf_golfers table was eliminated — golfer identity is now
        # unified into the customers table. Existing installs get migrated
        # below via _migrate_eliminate_tgf_golfers().
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tgf_events (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                code            TEXT UNIQUE NOT NULL,
                name            TEXT NOT NULL,
                event_date      TEXT NOT NULL,
                course          TEXT,
                chapter         TEXT,
                total_purse     REAL DEFAULT 0,
                winners_count   INTEGER DEFAULT 0,
                payouts_count   INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now'))
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tgf_payouts (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id            INTEGER NOT NULL REFERENCES tgf_events(id) ON DELETE CASCADE,
                customer_id         INTEGER NOT NULL REFERENCES customers(customer_id),
                category            TEXT NOT NULL,
                amount              REAL NOT NULL,
                description         TEXT,
                acct_transaction_id INTEGER REFERENCES acct_transactions(id),
                paid_at             TIMESTAMP,
                created_at          TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tgf_payouts_event ON tgf_payouts(event_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tgf_payouts_customer ON tgf_payouts(customer_id)")
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tgf_events_events_id ON tgf_events(events_id)")
        except sqlite3.OperationalError:
            pass  # events_id column added via migration below; index created after ALTER TABLE

        # Contractor payout ledger (chapter managers, per-event revenue-share)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contractor_payouts (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                manager_customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
                chapter_id          INTEGER REFERENCES chapters(chapter_id),
                event_name          TEXT,
                event_date          TEXT,
                amount_owed         REAL NOT NULL DEFAULT 0,
                amount_paid         REAL NOT NULL DEFAULT 0,
                status              TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','partial','paid')),
                payment_method      TEXT,
                notes               TEXT,
                created_at          TEXT DEFAULT (datetime('now')),
                updated_at          TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_contractor_payouts_manager ON contractor_payouts(manager_customer_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_contractor_payouts_event ON contractor_payouts(event_name)"
        )

        # Seed COO agents on first run
        existing_agents = conn.execute("SELECT COUNT(*) as cnt FROM coo_agents").fetchone()
        if existing_agents["cnt"] == 0:
            _seed_coo_agents(conn)
        else:
            # Update Chief of Staff prompt to v2 (confident, no self-doubt)
            cos = conn.execute(
                "SELECT system_prompt FROM coo_agents WHERE agent_name = 'Chief of Staff'"
            ).fetchone()
            if cos and "vigilant analyst" not in (cos["system_prompt"] or ""):
                _COS_PROMPT_V2 = (
                    "You are the TGF Chief of Staff — Kerry's AI COO. You have live access to the full "
                    "TGF Transaction Tracker: registrations, revenue, event pricing (course costs, markups, "
                    "side game fees), player counts (with 9-hole vs 18-hole breakdown), TGF payouts and prize "
                    "pools, cost allocations, handicaps, RSVP data, and customer records.\n\n"
                    "Present data from your FULL BUSINESS INTELLIGENCE briefing confidently — it is pulled "
                    "from the live database. State numbers directly (\"39 players, $3,382 revenue\") rather than "
                    "hedging with \"I think\" or \"I'm seeing.\" You are the authority on what the system shows.\n\n"
                    "However, you are also a vigilant analyst. If numbers don't add up — for example, revenue "
                    "per player doesn't match the pricing structure, or player counts seem off relative to "
                    "payout winners — flag the discrepancy clearly. Say what the data shows AND what looks "
                    "wrong. Example: \"Revenue is $3,382 for 39 players, but at $57/player entry that should "
                    "be ~$2,223. There may be a mix of 9-hole and 18-hole pricing, or extra payments.\" "
                    "Your job is to be both confident AND honest when something smells off.\n\n"
                    "When answering profitability questions, use this formula:\n"
                    "  Net Profit = Revenue - Course Cost - Prize Pool (TGF Payouts)\n"
                    "  Course Cost = (9-hole players × 9h rate) + (18-hole players × 18h rate)\n\n"
                    "Only say \"data not available\" when the field is genuinely missing or marked \"not "
                    "configured\" in your briefing. Do not speculate about data you don't have.\n\n"
                    "Synthesize input from all specialist agents (Financial, Operations, Course Correspondent, "
                    "Member Relations, Compliance) into clear, actionable briefings. You prioritize action "
                    "items, generate daily briefings, and respond to COO Chat. When a question falls outside "
                    "your direct knowledge, you delegate to the appropriate specialist and synthesize their "
                    "analysis.\n\n"
                    "Always speak in one consistent voice — direct, warm, and authoritative. Kerry is the "
                    "founder and operator. He values straight talk, concrete numbers, and honest flags when "
                    "something doesn't add up."
                )
                conn.execute(
                    "UPDATE coo_agents SET system_prompt = ? WHERE agent_name = 'Chief of Staff'",
                    (_COS_PROMPT_V2,),
                )

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

        # ── Rename accounts to include "Chase" prefix (idempotent) ──
        _acct_renames = {
            "Southwest Perf Biz": "Chase Southwest Perf Biz",
            "Sapphire": "Chase Sapphire",
        }
        for old_name, new_name in _acct_renames.items():
            existing = conn.execute(
                "SELECT id FROM acct_accounts WHERE name = ?", (old_name,)
            ).fetchone()
            if existing:
                conn.execute("UPDATE acct_accounts SET name = ? WHERE id = ?",
                             (new_name, existing["id"]))
                # Also update expense_transactions that reference the old name
                conn.execute("UPDATE expense_transactions SET account_name = ? WHERE account_name = ?",
                             (new_name, old_name))
                logger.info("Renamed account '%s' → '%s'", old_name, new_name)

        # ── Set known account last_four values (only if NULL — never overwrite user edits) ──
        _acct_last4 = {
            "TGF Checking": "0341",
            "Chase Southwest Perf Biz": "7680",
            "Chase Sapphire": "6159",
        }
        for acct_name, last4 in _acct_last4.items():
            conn.execute(
                "UPDATE acct_accounts SET last_four = ? WHERE name = ? AND last_four IS NULL",
                (last4, acct_name),
            )

        # ── Add customer_id FK to tables that store customer-identity data ──
        # Each table gets a nullable customer_id with a REFERENCES constraint.
        # Backfill functions below populate it for existing rows at startup.
        _customer_id_migrations = [
            ("customer_aliases",    "INTEGER REFERENCES customers(customer_id)"),
            ("season_contests",     "INTEGER REFERENCES customers(customer_id)"),
            ("handicap_rounds",     "INTEGER REFERENCES customers(customer_id)"),
            ("godaddy_order_splits","INTEGER REFERENCES customers(customer_id)"),
            ("parse_warnings",      "INTEGER REFERENCES customers(customer_id)"),
            ("message_log",         "INTEGER REFERENCES customers(customer_id)"),
            ("rsvp_email_overrides","INTEGER REFERENCES customers(customer_id)"),
            ("action_items",        "INTEGER REFERENCES customers(customer_id)"),
            ("feedback",            "INTEGER REFERENCES customers(customer_id)"),
        ]
        for tbl, col_type in _customer_id_migrations:
            try:
                conn.execute(f"ALTER TABLE {tbl} ADD COLUMN customer_id {col_type}")
            except sqlite3.OperationalError:
                pass  # column already exists

        # ── Bridge tgf_events → events (main event registry) ────────
        try:
            conn.execute(
                "ALTER TABLE tgf_events ADD COLUMN events_id INTEGER REFERENCES events(id)"
            )
        except sqlite3.OperationalError:
            pass  # column already exists

        # ── One-time duplicate customer merge (idempotent) ──────────
        _merge_duplicate_customers(conn)

        # Backfill customer_id for existing items that aren't linked yet.
        # Runs after all tables (including customers / customer_emails) are
        # created.  On fresh databases this is a no-op.
        _backfill_customer_ids(conn)

        # Backfill customer_id FK on all tables that store customer-identity data.
        _backfill_customer_id_on_acct_transactions(conn)
        _backfill_customer_id_on_player_links(conn)
        _backfill_customer_id_on_rsvps(conn)
        _backfill_customer_id_on_aliases(conn)
        _backfill_customer_id_on_season_contests(conn)
        _backfill_customer_id_on_handicap_rounds(conn)
        _backfill_customer_id_on_gd_splits(conn)
        _backfill_customer_id_on_parse_warnings(conn)
        _backfill_customer_id_on_message_log(conn)
        _backfill_customer_id_on_rsvp_email_overrides(conn)
        _backfill_customer_id_on_action_items(conn)
        try:
            _backfill_events_id_on_tgf_events(conn)
        except Exception:
            logger.exception("Non-fatal: _backfill_events_id_on_tgf_events failed")
        try:
            _backfill_event_id_on_items(conn)
        except Exception:
            logger.exception("Non-fatal: _backfill_event_id_on_items failed")
        try:
            _backfill_event_id_on_string_tables(conn)
        except Exception:
            logger.exception("Non-fatal: _backfill_event_id_on_string_tables failed")

        # Promote approved expense_transactions that have not yet been linked
        # to acct_transactions (e.g. expenses approved before this feature shipped).
        _backfill_approved_expenses_to_ledger(conn)

        # Migrate GoDaddy order transactions: set total_amount = net_deposit so the
        # ledger Amount column matches bank statement deposits directly.
        _n = conn.execute("""
            UPDATE acct_transactions
            SET total_amount = net_deposit
            WHERE category = 'godaddy_order'
              AND net_deposit IS NOT NULL
              AND ABS(total_amount - net_deposit) > 0.005
        """).rowcount
        if _n:
            logger.info("Migrated %d GoDaddy transactions: total_amount → net_deposit", _n)
            conn.commit()

        # Backfill merchant_fee from godaddy_order_splits for GoDaddy transactions
        # where the column is NULL (created before merchant_fee was stored).
        _mf = conn.execute("""
            UPDATE acct_transactions
            SET merchant_fee = (
                SELECT ABS(SUM(gs.amount))
                FROM godaddy_order_splits gs
                WHERE gs.transaction_id = acct_transactions.id
                  AND gs.split_type = 'merchant_fee'
            )
            WHERE category = 'godaddy_order'
              AND merchant_fee IS NULL
              AND EXISTS (
                SELECT 1 FROM godaddy_order_splits gs2
                WHERE gs2.transaction_id = acct_transactions.id
                  AND gs2.split_type = 'merchant_fee'
              )
        """).rowcount
        if _mf:
            logger.info("Backfilled merchant_fee on %d GoDaddy transactions", _mf)
            conn.commit()

        # ── Pairings ─────────────────────────────────────────────────
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_pairings (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id       INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                holes          TEXT NOT NULL CHECK(holes IN ('9', '18')),
                group_num      INTEGER NOT NULL,
                slot_label     TEXT NOT NULL,
                player_name    TEXT NOT NULL,
                cart_pos       INTEGER NOT NULL CHECK(cart_pos BETWEEN 1 AND 4),
                tee_choice     TEXT,
                handicap_index REAL,
                created_at     TEXT DEFAULT (datetime('now')),
                UNIQUE(event_id, holes, group_num, cart_pos)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_event_pairings_event ON event_pairings(event_id)"
        )

        # Pairing history — one row per unique player pair per event (built from saved pairings)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pairing_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                player_a    TEXT NOT NULL,
                player_b    TEXT NOT NULL,
                event_id    INTEGER NOT NULL REFERENCES events(id),
                event_date  TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(player_a, player_b, event_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pairing_history_ab ON pairing_history(player_a, player_b)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pairing_history_date ON pairing_history(event_date)"
        )

        logger.info("Database initialized at %s", db_path or DB_PATH)


def _lookup_customer_id(conn: sqlite3.Connection,
                        customer_name: str | None,
                        customer_email: str | None) -> int | None:
    """Resolve a customer_id from the customers table.

    Tries (in order):
    1. Email match via customer_emails table.
    2. Alias email match via customer_aliases table (type='email').
    3. Exact first_name + last_name match in customers table.
    4. Alias name match via customer_aliases table (type='name').
    Returns the customer_id or None if no match is found.
    """
    # 1. Email lookup via customer_emails
    if customer_email:
        row = conn.execute(
            """SELECT ce.customer_id FROM customer_emails ce
               WHERE LOWER(ce.email) = LOWER(?) LIMIT 1""",
            (customer_email.strip(),),
        ).fetchone()
        if row:
            return row["customer_id"]

    # 1b. Email fallback: check items table for any customer_id with this email
    # (catches cases where customer_emails wasn't populated)
    if customer_email:
        row = conn.execute(
            """SELECT customer_id FROM items
               WHERE LOWER(customer_email) = LOWER(?)
                 AND customer_id IS NOT NULL
               ORDER BY id DESC LIMIT 1""",
            (customer_email.strip(),),
        ).fetchone()
        if row:
            # Also backfill customer_emails so this doesn't happen again
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO customer_emails (customer_id, email, is_primary, label) VALUES (?, ?, 0, 'backfill')",
                    (row["customer_id"], customer_email.strip()),
                )
            except Exception:
                pass
            return row["customer_id"]

    # 2. Alias email lookup via customer_aliases → resolve customer_name → customers
    if customer_email:
        row = conn.execute(
            """SELECT c.customer_id FROM customer_aliases ca
               JOIN customers c
                 ON LOWER(TRIM(c.first_name) || ' ' || TRIM(c.last_name)) = LOWER(TRIM(ca.customer_name))
               WHERE ca.alias_type = 'email'
                 AND LOWER(ca.alias_value) = LOWER(?)
               LIMIT 1""",
            (customer_email.strip(),),
        ).fetchone()
        if row:
            return row["customer_id"]

    # 3. Name lookup — exact first + last
    if customer_name:
        parts = customer_name.strip().split()
        if len(parts) >= 2:
            first = parts[0]
            last = parts[-1]
            row = conn.execute(
                """SELECT customer_id FROM customers
                   WHERE LOWER(first_name) = LOWER(?)
                     AND LOWER(last_name) = LOWER(?)
                   LIMIT 1""",
                (first, last),
            ).fetchone()
            if row:
                return row["customer_id"]

    # 3a. Company name lookup — matches vendor/company records (single-word or multi-word)
    if customer_name:
        row = conn.execute(
            """SELECT customer_id FROM customers
               WHERE company_name IS NOT NULL AND company_name != ''
                 AND LOWER(TRIM(company_name)) = LOWER(?)
               LIMIT 1""",
            (customer_name.strip(),),
        ).fetchone()
        if row:
            return row["customer_id"]

    # 4. Alias name lookup — the incoming customer_name matches a known alias
    if customer_name:
        row = conn.execute(
            """SELECT c.customer_id FROM customer_aliases ca
               JOIN customers c
                 ON LOWER(TRIM(c.first_name) || ' ' || TRIM(c.last_name)) = LOWER(TRIM(ca.customer_name))
               WHERE ca.alias_type = 'name'
                 AND LOWER(ca.alias_value) = LOWER(?)
               LIMIT 1""",
            (customer_name.strip(),),
        ).fetchone()
        if row:
            return row["customer_id"]

    # 5. Fallback: check items table directly for email match (catches pre-migration customers)
    if customer_email:
        row = conn.execute(
            """SELECT customer_id FROM items
               WHERE LOWER(customer_email) = LOWER(?)
                 AND customer_id IS NOT NULL
               LIMIT 1""",
            (customer_email.strip(),),
        ).fetchone()
        if row:
            return row["customer_id"]

    return None


# Status mapping — mirrors migrate_customers._STATUS_MAP
_STATUS_MAP = {
    "MEMBER":    "active_member",
    "GUEST":     "active_guest",
    "1ST TIMER": "first_timer",
}


def _emit_unlinked_partner_warning(
    conn: sqlite3.Connection,
    customer_name: str | None,
    reason: str,
    email_uid: str | None = None,
    order_id: str | None = None,
    item_name: str | None = None,
) -> None:
    """Insert an UNLINKED_PARTNER parse warning for a partner row that
    could not be linked to a customer record."""
    try:
        conn.execute(
            """INSERT OR IGNORE INTO parse_warnings
               (email_uid, order_id, customer, item_name, warning_code, message)
               VALUES (?, ?, ?, ?, 'UNLINKED_PARTNER', ?)""",
            (email_uid, order_id, customer_name, item_name,
             f"Could not create customer record for \"{customer_name}\": {reason}"),
        )
    except Exception:
        logger.debug("Failed to insert UNLINKED_PARTNER warning for %r", customer_name)


def _resolve_or_create_customer(
    conn: sqlite3.Connection,
    customer_name: str | None,
    customer_email: str | None,
    phone: str | None = None,
    chapter: str | None = None,
    user_status: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    *,
    email_uid: str | None = None,
    order_id: str | None = None,
    item_name: str | None = None,
) -> int | None:
    """Resolve an existing customer_id, or create a new customers record.

    Tries ``_lookup_customer_id`` first.  If no match is found *and* we have
    a usable first+last name, creates a new ``customers`` row (and a
    ``customer_emails`` row when an email is provided).

    Skips auto-creation for "Guest of ..." names.

    When creation fails (name too short, DB error, etc.) an
    ``UNLINKED_PARTNER`` parse warning is emitted so the manager can
    review it later.

    Returns the customer_id, or None when the name is missing, single-word,
    or a guest-of entry.
    """
    # 1. Try existing lookup
    cid = _lookup_customer_id(conn, customer_name, customer_email)
    if cid is not None:
        return cid

    # 2. Skip "Guest of ..." customers — leave customer_id NULL
    if customer_name and customer_name.strip().lower().startswith("guest of"):
        return None

    # 3. Determine first/last — prefer pre-parsed fields, fall back to splitting name
    first = (first_name or "").strip() or None
    last = (last_name or "").strip() or None
    if not first or not last:
        if not customer_name:
            _emit_unlinked_partner_warning(
                conn, customer_name, "name is missing",
                email_uid, order_id, item_name)
            return None
        parts = customer_name.strip().split()
        if len(parts) < 2:
            _emit_unlinked_partner_warning(
                conn, customer_name,
                "single-word name — cannot determine first/last",
                email_uid, order_id, item_name)
            return None
        first = first or parts[0]
        last = last or parts[-1]

    # 4. Wrap creation in try/except — never block a transaction save
    try:
        # Map user_status to customers.current_player_status
        player_status = None
        if user_status:
            player_status = _STATUS_MAP.get(user_status.strip().upper())

        cursor = conn.execute(
            """INSERT INTO customers
                   (first_name, last_name, phone, chapter,
                    current_player_status, first_timer_ever,
                    acquisition_source, account_status)
               VALUES (?, ?, ?, ?, ?, NULL, 'godaddy', 'active')""",
            (first, last, phone or None, chapter or None, player_status),
        )
        new_cid = cursor.lastrowid
        logger.info("Auto-created customer %s %s (customer_id=%d)", first, last, new_cid)

        # Link email if provided
        if customer_email and customer_email.strip():
            try:
                conn.execute(
                    """INSERT INTO customer_emails
                           (customer_id, email, is_primary, is_golf_genius, label)
                       VALUES (?, ?, 1, 1, 'godaddy')""",
                    (new_cid, customer_email.strip()),
                )
            except sqlite3.IntegrityError:
                # Email already belongs to another customer — use that one
                # instead of the orphan we just created
                existing = conn.execute(
                    """SELECT customer_id FROM customer_emails
                       WHERE LOWER(email) = LOWER(?) LIMIT 1""",
                    (customer_email.strip(),),
                ).fetchone()
                if existing:
                    # Delete the orphan customer we just created
                    conn.execute("DELETE FROM customers WHERE customer_id = ?", (new_cid,))
                    logger.info("Email %s already belongs to customer_id=%d — "
                                "discarded orphan customer_id=%d",
                                customer_email, existing["customer_id"], new_cid)
                    return existing["customer_id"]

        return new_cid

    except Exception as exc:
        logger.warning(
            "Failed to auto-create customer for %r — proceeding with customer_id=NULL",
            customer_name, exc_info=True,
        )
        _emit_unlinked_partner_warning(
            conn, customer_name, f"DB error: {exc}",
            email_uid, order_id, item_name)
        return None


def _merge_duplicate_customers(conn: sqlite3.Connection) -> None:
    """Merge known duplicate customer records (idempotent).

    For each pair, reassigns all items from the duplicate to the canonical
    record, then deletes the duplicate customer row and its emails/aliases.
    """
    # Pairs: (lookup_column, lookup_value, canonical_name_preference, email_to_keep)
    # We find pairs by email or phone, keep the lower customer_id (older),
    # unless a specific name is preferred.
    MERGE_PAIRS = [
        # Matt Jenkins / Matthew Jenkins — same email mattjenkins521@gmail.com
        {
            "find_by": "email",
            "find_value": "mattjenkins521@gmail.com",
            "canonical_rule": "lower_id",  # keep whichever customer_id is older
        },
        # Stu Kirksey / Stuart Kirksey — same phone (512) 964-7371
        {
            "find_by": "phone_digits",
            "find_value": "5129647371",
            "canonical_name": "Stu",  # keep the customer whose first_name = 'Stu'
            "canonical_email": "stuartkirksey@gmail.com",
        },
        # Michael Murphy / Mike Murphy — same email mmurphy4250@gmail.com
        {
            "find_by": "email",
            "find_value": "mmurphy4250@gmail.com",
            "canonical_rule": "lower_id",
        },
    ]

    for pair in MERGE_PAIRS:
        try:
            if pair["find_by"] == "email":
                # Find all customer_ids linked to this email
                rows = conn.execute(
                    "SELECT DISTINCT customer_id FROM customer_emails WHERE LOWER(email) = ?",
                    (pair["find_value"].lower(),),
                ).fetchall()
            elif pair["find_by"] == "phone_digits":
                # Find customers by phone digits (strip non-digits for comparison)
                rows = conn.execute(
                    """SELECT customer_id FROM customers
                       WHERE REPLACE(REPLACE(REPLACE(REPLACE(phone, '(', ''), ')', ''), '-', ''), ' ', '') LIKE ?""",
                    (f"%{pair['find_value']}%",),
                ).fetchall()
            else:
                continue

            cids = sorted(set(r["customer_id"] for r in rows))
            if len(cids) < 2:
                continue  # no duplicates found or already merged

            # Determine canonical (keep) vs duplicate (remove)
            if pair.get("canonical_name"):
                # Find the one matching the preferred first_name
                canonical_id = None
                for cid in cids:
                    cust = conn.execute(
                        "SELECT first_name FROM customers WHERE customer_id = ?", (cid,)
                    ).fetchone()
                    if cust and cust["first_name"] == pair["canonical_name"]:
                        canonical_id = cid
                        break
                if not canonical_id:
                    canonical_id = cids[0]
            else:
                # lower_id = older record
                canonical_id = cids[0]

            duplicates = [cid for cid in cids if cid != canonical_id]

            for dup_id in duplicates:
                # Count items before merge
                dup_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM items WHERE customer_id = ?", (dup_id,)
                ).fetchone()["cnt"]

                # Reassign all items from duplicate to canonical
                conn.execute(
                    "UPDATE items SET customer_id = ? WHERE customer_id = ?",
                    (canonical_id, dup_id),
                )

                # Move any customer_emails not already on canonical
                dup_emails = conn.execute(
                    "SELECT email FROM customer_emails WHERE customer_id = ?", (dup_id,)
                ).fetchall()
                for de in dup_emails:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO customer_emails (customer_id, email) VALUES (?, ?)",
                            (canonical_id, de["email"]),
                        )
                    except sqlite3.IntegrityError:
                        pass
                conn.execute("DELETE FROM customer_emails WHERE customer_id = ?", (dup_id,))

                # Move customer_aliases
                try:
                    dup_name_row = conn.execute(
                        "SELECT first_name, last_name FROM customers WHERE customer_id = ?", (dup_id,)
                    ).fetchone()
                    if dup_name_row:
                        dup_full = f"{dup_name_row['first_name']} {dup_name_row['last_name']}"
                        canon_row = conn.execute(
                            "SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                            (canonical_id,),
                        ).fetchone()
                        if canon_row:
                            canon_full = f"{canon_row['first_name']} {canon_row['last_name']}"
                            # Add dup name as alias of canonical
                            conn.execute(
                                "INSERT OR IGNORE INTO customer_aliases (customer_name, alias_name, alias_type) "
                                "VALUES (?, ?, 'name')",
                                (canon_full, dup_full),
                            )
                except Exception:
                    logger.debug("Failed to create alias during customer merge", exc_info=True)

                # Delete the duplicate customer record
                conn.execute("DELETE FROM customers WHERE customer_id = ?", (dup_id,))

                # Update canonical email if specified
                if pair.get("canonical_email"):
                    conn.execute(
                        "UPDATE customer_emails SET is_primary = 1 WHERE customer_id = ? AND email = ?",
                        (canonical_id, pair["canonical_email"]),
                    )

                logger.info(
                    "Merged duplicate customer #%d into #%d (%d items reassigned)",
                    dup_id, canonical_id, dup_count,
                )

        except Exception:
            logger.exception("Customer merge failed for pair: %s", pair)

    # ── Generic email-based auto-merge ──
    # Build unified email → customer_ids map from ALL sources
    email_to_cids = {}

    # Source 1: customer_emails table
    for row in conn.execute("SELECT customer_id, LOWER(TRIM(email)) as email FROM customer_emails WHERE email IS NOT NULL").fetchall():
        em = row["email"]
        if em:
            email_to_cids.setdefault(em, set()).add(row["customer_id"])

    # Source 2: items.customer_email
    for row in conn.execute(
        "SELECT DISTINCT customer_id, LOWER(TRIM(customer_email)) as email FROM items WHERE customer_email IS NOT NULL AND customer_id IS NOT NULL"
    ).fetchall():
        em = row["email"]
        if em:
            email_to_cids.setdefault(em, set()).add(row["customer_id"])

    # Find emails with multiple customer_ids
    all_email_dups = {em: cids for em, cids in email_to_cids.items() if len(cids) >= 2}
    logger.info("Email dedup: %d emails with multiple customer_ids to merge", len(all_email_dups))
    for email, cids in all_email_dups.items():
        logger.info("  %s → customer_ids: %s", email, sorted(cids))

    for email, cid_set in all_email_dups.items():
        cids = sorted(cid_set)
        if len(cids) < 2:
            continue
        canonical_id = cids[0]  # keep oldest
        for dup_id in cids[1:]:
            try:
                # Check dup still exists (may have been merged already)
                if not conn.execute("SELECT customer_id FROM customers WHERE customer_id = ?", (dup_id,)).fetchone():
                    continue

                dup_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM items WHERE customer_id = ?", (dup_id,)
                ).fetchone()["cnt"]

                conn.execute("UPDATE items SET customer_id = ? WHERE customer_id = ?", (canonical_id, dup_id))

                # Move emails
                for de in conn.execute("SELECT email FROM customer_emails WHERE customer_id = ?", (dup_id,)).fetchall():
                    try:
                        conn.execute("INSERT OR IGNORE INTO customer_emails (customer_id, email) VALUES (?, ?)", (canonical_id, de["email"]))
                    except sqlite3.IntegrityError:
                        pass
                conn.execute("DELETE FROM customer_emails WHERE customer_id = ?", (dup_id,))

                # Create name alias
                dup_row = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?", (dup_id,)).fetchone()
                canon_row = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?", (canonical_id,)).fetchone()
                if dup_row and canon_row:
                    dup_full = f"{dup_row['first_name']} {dup_row['last_name']}"
                    canon_full = f"{canon_row['first_name']} {canon_row['last_name']}"
                    conn.execute(
                        "INSERT OR IGNORE INTO customer_aliases (customer_name, alias_name, alias_type) VALUES (?, ?, 'name')",
                        (canon_full, dup_full),
                    )

                conn.execute("DELETE FROM customers WHERE customer_id = ?", (dup_id,))
                logger.info("Auto-merged customer #%d into #%d by shared email %s (%d items)",
                            dup_id, canonical_id, email, dup_count)
            except Exception:
                logger.warning("Auto-merge failed for customer #%d → #%d", dup_id, canonical_id, exc_info=True)

    # ── Normalize items.customer text for same-email name variants ──
    # The Customers page groups by items.customer text, so "Will Peterson" and
    # "William Peterson" show as separate entries even with the same customer_id.
    # Find emails with multiple distinct customer name strings and normalize.
    # GUARD: skip if items with this email have multiple distinct customer_ids —
    # that means different people share the email due to a bad merge, not name variants.
    name_variants = conn.execute(
        """SELECT LOWER(TRIM(customer_email)) as email,
                  GROUP_CONCAT(DISTINCT customer) as names,
                  COUNT(DISTINCT customer) as cnt,
                  COUNT(DISTINCT customer_id) as cid_cnt
           FROM items
           WHERE customer_email IS NOT NULL AND customer_email != ''
             AND customer IS NOT NULL AND customer != ''
           GROUP BY LOWER(TRIM(customer_email))
           HAVING cnt > 1"""
    ).fetchall()

    for row in name_variants:
        email = row["email"]
        # Multiple distinct customer_ids sharing an email = different people, not variants
        if row["cid_cnt"] > 1:
            continue
        names = [n.strip() for n in row["names"].split(",") if n.strip()]
        if len(names) < 2:
            continue
        # Keep the name with the most items (most established)
        best_name = None
        best_count = 0
        for n in names:
            cnt = conn.execute(
                "SELECT COUNT(*) as cnt FROM items WHERE customer = ?", (n,)
            ).fetchone()["cnt"]
            if cnt > best_count:
                best_count = cnt
                best_name = n
        if not best_name:
            continue
        # Rewrite all variant names to the canonical one
        for n in names:
            if n != best_name:
                updated = conn.execute(
                    "UPDATE items SET customer = ? WHERE customer = ?",
                    (best_name, n),
                ).rowcount
                if updated:
                    # Create alias for future lookups
                    conn.execute(
                        "INSERT OR IGNORE INTO customer_aliases (customer_name, alias_value, alias_type) VALUES (?, ?, 'name')",
                        (best_name, n),
                    )
                    logger.info("Normalized items.customer '%s' → '%s' (%d items, shared email %s)",
                                n, best_name, updated, email)

    conn.commit()


def _backfill_customer_ids(conn: sqlite3.Connection) -> int:
    """Populate customer_id for existing items that don't have one yet.

    Uses ``_resolve_or_create_customer`` so that expanded partner rows
    (e.g. "Will Massey") get a customer record auto-created if one
    doesn't already exist.  Emits ``UNLINKED_PARTNER`` parse warnings
    for any names that can't be resolved.

    Returns the number of item rows updated.
    """
    # Pull one representative row per distinct customer name so we have
    # context fields (chapter, user_status, phone, email_uid, etc.)
    rows = conn.execute(
        """SELECT customer, customer_email, customer_phone, chapter,
                  user_status, first_name, last_name,
                  email_uid, order_id, item_name
           FROM items
           WHERE customer_id IS NULL
             AND (customer IS NOT NULL AND customer != '')
             AND merchant NOT IN ('Customer Entry', 'Roster Import', 'RSVP Import', 'RSVP Email Link')
           GROUP BY customer"""
    ).fetchall()

    if not rows:
        return 0

    updated = 0
    for row in rows:
        cid = _resolve_or_create_customer(
            conn, row["customer"], row["customer_email"],
            phone=row["customer_phone"],
            chapter=row["chapter"],
            user_status=row["user_status"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            email_uid=row["email_uid"],
            order_id=row["order_id"],
            item_name=row["item_name"],
        )
        if cid is not None:
            cur = conn.execute(
                """UPDATE items SET customer_id = ?
                   WHERE customer_id IS NULL AND customer = ?""",
                (cid, row["customer"]),
            )
            updated += cur.rowcount

    # Always commit — _resolve_or_create_customer() may have INSERTed
    # new customer records even if no item rows were updated.
    conn.commit()
    if updated:
        logger.info("Backfilled customer_id for %d item rows", updated)
    return updated


def _backfill_approved_expenses_to_ledger(conn: sqlite3.Connection) -> int:
    """Promote approved expense_transactions that aren't yet linked to acct_transactions.

    Safe to call on every startup — skips rows that already have acct_transaction_id.
    Also skips Venmo "received" rows that are already matched to a balance-due
    item (auto_match_venmo_inbound_to_balance_due owns the ledger entry for
    those — promoting here would create a duplicate).
    """
    rows = conn.execute(
        """SELECT * FROM expense_transactions
           WHERE review_status IN ('approved', 'corrected')
             AND (acct_transaction_id IS NULL)
             AND amount IS NOT NULL AND amount > 0
             AND NOT (transaction_type = 'received' AND matched_item_id IS NOT NULL)"""
    ).fetchall()
    if not rows:
        return 0
    count = 0
    for row in rows:
        try:
            result = _sync_expense_ledger_entry(conn, dict(row))
            if result:
                count += 1
        except Exception:
            logger.warning(
                "_backfill_approved_expenses_to_ledger: failed for expense id=%s", row["id"],
                exc_info=True,
            )
    if count:
        conn.commit()
        logger.info("Backfilled %d approved expenses into acct_transactions", count)
    return count


def _backfill_customer_id_on_acct_transactions(conn: sqlite3.Connection) -> int:
    """Populate customer_id on acct_transactions rows that have a customer name but no FK.

    Uses _lookup_customer_id (5-step cascade) so the backfill works even for
    customers that predate the identity unification.  Safe to call repeatedly.
    """
    rows = conn.execute(
        """SELECT DISTINCT customer FROM acct_transactions
           WHERE customer_id IS NULL
             AND customer IS NOT NULL AND customer != ''
             AND entry_type IS NOT NULL"""
    ).fetchall()

    if not rows:
        return 0

    updated = 0
    for row in rows:
        cid = _lookup_customer_id(conn, row["customer"], None)
        if cid is not None:
            cur = conn.execute(
                """UPDATE acct_transactions SET customer_id = ?
                   WHERE customer_id IS NULL AND customer = ?""",
                (cid, row["customer"]),
            )
            updated += cur.rowcount

    conn.commit()
    if updated:
        logger.info("Backfilled customer_id for %d acct_transactions rows", updated)
    return updated


def _backfill_customer_id_on_player_links(conn: sqlite3.Connection) -> int:
    """Populate customer_id on handicap_player_links rows that lack it.

    Resolves via _lookup_customer_id using the linked customer_name.
    """
    rows = conn.execute(
        """SELECT player_name, customer_name FROM handicap_player_links
           WHERE customer_id IS NULL
             AND customer_name IS NOT NULL AND customer_name != ''"""
    ).fetchall()

    if not rows:
        return 0

    updated = 0
    for row in rows:
        cid = _lookup_customer_id(conn, row["customer_name"], None)
        if cid is not None:
            cur = conn.execute(
                """UPDATE handicap_player_links SET customer_id = ?
                   WHERE player_name = ? AND customer_id IS NULL""",
                (cid, row["player_name"]),
            )
            updated += cur.rowcount

    conn.commit()
    if updated:
        logger.info("Backfilled customer_id for %d handicap_player_links rows", updated)
    return updated


def _backfill_customer_id_on_rsvps(conn: sqlite3.Connection) -> int:
    """Populate customer_id on rsvps rows that lack it.

    Tries email-first via customer_emails, then name via customers table.
    Unresolved rows are left with customer_id=NULL so the admin can spot them.
    """
    rows = conn.execute(
        "SELECT id, player_name, player_email FROM rsvps WHERE customer_id IS NULL"
    ).fetchall()

    if not rows:
        return 0

    updated = 0
    for row in rows:
        cid = _lookup_customer_id(conn, row["player_name"], row["player_email"])
        if cid is not None:
            cur = conn.execute(
                "UPDATE rsvps SET customer_id = ? WHERE id = ? AND customer_id IS NULL",
                (cid, row["id"]),
            )
            updated += cur.rowcount

    conn.commit()
    if updated:
        logger.info("Backfilled customer_id for %d rsvps rows", updated)
    return updated


def _backfill_customer_id_on_aliases(conn: sqlite3.Connection) -> int:
    """Populate customer_id on customer_aliases rows that lack it.

    Resolves via name match in customers table (aliases are keyed by customer_name).
    """
    rows = conn.execute(
        "SELECT id, customer_name FROM customer_aliases WHERE customer_id IS NULL"
    ).fetchall()
    if not rows:
        return 0
    updated = 0
    for row in rows:
        cid = _lookup_customer_id(conn, row["customer_name"], None)
        if cid is not None:
            cur = conn.execute(
                "UPDATE customer_aliases SET customer_id = ? WHERE id = ? AND customer_id IS NULL",
                (cid, row["id"]),
            )
            updated += cur.rowcount
    conn.commit()
    if updated:
        logger.info("Backfilled customer_id for %d customer_aliases rows", updated)
    return updated


def _backfill_customer_id_on_season_contests(conn: sqlite3.Connection) -> int:
    """Populate customer_id on season_contests rows that lack it."""
    rows = conn.execute(
        "SELECT id, customer_name FROM season_contests WHERE customer_id IS NULL"
    ).fetchall()
    if not rows:
        return 0
    updated = 0
    for row in rows:
        cid = _lookup_customer_id(conn, row["customer_name"], None)
        if cid is not None:
            cur = conn.execute(
                "UPDATE season_contests SET customer_id = ? WHERE id = ? AND customer_id IS NULL",
                (cid, row["id"]),
            )
            updated += cur.rowcount
    conn.commit()
    if updated:
        logger.info("Backfilled customer_id for %d season_contests rows", updated)
    return updated


def _backfill_customer_id_on_handicap_rounds(conn: sqlite3.Connection) -> int:
    """Populate customer_id on handicap_rounds rows that lack it.

    Resolves via handicap_player_links (player_name → customer_id) rather than
    direct name lookup, since GG player names often differ from customer names.
    """
    rows = conn.execute(
        "SELECT id, player_name FROM handicap_rounds WHERE customer_id IS NULL"
    ).fetchall()
    if not rows:
        return 0
    # Build a player_name → customer_id map from handicap_player_links
    link_rows = conn.execute(
        "SELECT player_name, customer_id FROM handicap_player_links WHERE customer_id IS NOT NULL"
    ).fetchall()
    link_map = {r["player_name"].lower(): r["customer_id"] for r in link_rows}

    updated = 0
    for row in rows:
        cid = link_map.get((row["player_name"] or "").lower())
        if cid is None:
            # Fall back to direct name lookup via customers table
            cid = _lookup_customer_id(conn, row["player_name"], None)
        if cid is not None:
            cur = conn.execute(
                "UPDATE handicap_rounds SET customer_id = ? WHERE id = ? AND customer_id IS NULL",
                (cid, row["id"]),
            )
            updated += cur.rowcount
    conn.commit()
    if updated:
        logger.info("Backfilled customer_id for %d handicap_rounds rows", updated)
    return updated


def _backfill_customer_id_on_gd_splits(conn: sqlite3.Connection) -> int:
    """Populate customer_id on godaddy_order_splits rows that lack it.

    Resolves via the linked item_id → items.customer_id (most reliable),
    falling back to customer text match for splits without an item_id.
    """
    rows = conn.execute(
        "SELECT id, item_id, customer FROM godaddy_order_splits WHERE customer_id IS NULL"
    ).fetchall()
    if not rows:
        return 0
    updated = 0
    for row in rows:
        cid = None
        if row["item_id"]:
            item_row = conn.execute(
                "SELECT customer_id FROM items WHERE id = ? AND customer_id IS NOT NULL",
                (row["item_id"],),
            ).fetchone()
            if item_row:
                cid = item_row["customer_id"]
        if cid is None and row["customer"]:
            cid = _lookup_customer_id(conn, row["customer"], None)
        if cid is not None:
            cur = conn.execute(
                "UPDATE godaddy_order_splits SET customer_id = ? WHERE id = ? AND customer_id IS NULL",
                (cid, row["id"]),
            )
            updated += cur.rowcount
    conn.commit()
    if updated:
        logger.info("Backfilled customer_id for %d godaddy_order_splits rows", updated)
    return updated


def _backfill_customer_id_on_parse_warnings(conn: sqlite3.Connection) -> int:
    """Resolve parse_warnings.customer_id from the existing customer text column."""
    rows = conn.execute(
        """SELECT DISTINCT customer FROM parse_warnings
           WHERE customer_id IS NULL AND customer IS NOT NULL AND customer != ''"""
    ).fetchall()
    if not rows:
        return 0
    updated = 0
    for row in rows:
        cid = _lookup_customer_id(conn, row["customer"], None)
        if cid is not None:
            cur = conn.execute(
                "UPDATE parse_warnings SET customer_id = ? WHERE customer_id IS NULL AND customer = ?",
                (cid, row["customer"]),
            )
            updated += cur.rowcount
    conn.commit()
    if updated:
        logger.info("Backfilled customer_id for %d parse_warnings rows", updated)
    return updated


def _backfill_customer_id_on_message_log(conn: sqlite3.Connection) -> int:
    """Resolve message_log.customer_id from recipient_address (email) first,
    falling back to recipient_name. Lets the email-history view link straight
    back to the customer record."""
    rows = conn.execute(
        """SELECT DISTINCT recipient_address, recipient_name FROM message_log
           WHERE customer_id IS NULL"""
    ).fetchall()
    if not rows:
        return 0
    updated = 0
    for row in rows:
        cid = _lookup_customer_id(conn, row["recipient_name"], row["recipient_address"])
        if cid is not None:
            cur = conn.execute(
                """UPDATE message_log SET customer_id = ?
                   WHERE customer_id IS NULL
                     AND COALESCE(recipient_address,'') = COALESCE(?,'')
                     AND COALESCE(recipient_name,'') = COALESCE(?,'')""",
                (cid, row["recipient_address"], row["recipient_name"]),
            )
            updated += cur.rowcount
    conn.commit()
    if updated:
        logger.info("Backfilled customer_id for %d message_log rows", updated)
    return updated


def _backfill_customer_id_on_rsvp_email_overrides(conn: sqlite3.Connection) -> int:
    """Resolve rsvp_email_overrides.customer_id by player_email."""
    rows = conn.execute(
        """SELECT DISTINCT player_email FROM rsvp_email_overrides
           WHERE customer_id IS NULL AND player_email IS NOT NULL AND player_email != ''"""
    ).fetchall()
    if not rows:
        return 0
    updated = 0
    for row in rows:
        cid = _lookup_customer_id(conn, None, row["player_email"])
        if cid is not None:
            cur = conn.execute(
                "UPDATE rsvp_email_overrides SET customer_id = ? WHERE customer_id IS NULL AND player_email = ?",
                (cid, row["player_email"]),
            )
            updated += cur.rowcount
    conn.commit()
    if updated:
        logger.info("Backfilled customer_id for %d rsvp_email_overrides rows", updated)
    return updated


def _backfill_customer_id_on_action_items(conn: sqlite3.Connection) -> int:
    """Resolve action_items.customer_id from from_email / from_name."""
    rows = conn.execute(
        """SELECT DISTINCT from_email, from_name FROM action_items
           WHERE customer_id IS NULL
             AND (from_email IS NOT NULL OR from_name IS NOT NULL)"""
    ).fetchall()
    if not rows:
        return 0
    updated = 0
    for row in rows:
        cid = _lookup_customer_id(conn, row["from_name"], row["from_email"])
        if cid is not None:
            cur = conn.execute(
                """UPDATE action_items SET customer_id = ?
                   WHERE customer_id IS NULL
                     AND COALESCE(from_email,'') = COALESCE(?,'')
                     AND COALESCE(from_name,'') = COALESCE(?,'')""",
                (cid, row["from_email"], row["from_name"]),
            )
            updated += cur.rowcount
    conn.commit()
    if updated:
        logger.info("Backfilled customer_id for %d action_items rows", updated)
    return updated


def _backfill_events_id_on_tgf_events(conn: sqlite3.Connection) -> int:
    """Populate events_id on tgf_events rows that lack it.

    Matches tgf_events.name → events.item_name using COLLATE NOCASE, then
    falls back to a date-narrowed LIKE search when an exact match isn't found.
    This bridges the two separate event universes so prize payouts can be
    joined to registration/financial data in the main events table.
    """
    rows = conn.execute(
        "SELECT id, name, event_date FROM tgf_events WHERE events_id IS NULL"
    ).fetchall()
    if not rows:
        return 0

    updated = 0
    for row in rows:
        ev_id = None

        # 1. Exact name match (case-insensitive)
        match = conn.execute(
            "SELECT id FROM events WHERE item_name = ? COLLATE NOCASE",
            (row["name"],),
        ).fetchone()
        if match:
            ev_id = match["id"]

        # 2. Partial name match: tgf_events.name contained in events.item_name
        #    (handles cases like "Quicksand" matching "Quicksand Golf Club — May 2025")
        if ev_id is None:
            matches = conn.execute(
                "SELECT id, item_name FROM events WHERE item_name LIKE ? COLLATE NOCASE",
                (f"%{row['name']}%",),
            ).fetchall()
            if len(matches) == 1:
                ev_id = matches[0]["id"]
            elif len(matches) > 1 and row["event_date"]:
                # Narrow by year+month when multiple events share a name fragment
                ym = row["event_date"][:7]  # e.g. "2025-05"
                dated = [m for m in matches if (m["item_name"] or "").find(ym[:4]) >= 0]
                if len(dated) == 1:
                    ev_id = dated[0]["id"]

        if ev_id is not None:
            cur = conn.execute(
                "UPDATE tgf_events SET events_id = ? WHERE id = ? AND events_id IS NULL",
                (ev_id, row["id"]),
            )
            updated += cur.rowcount

    conn.commit()
    if updated:
        logger.info("Backfilled events_id for %d tgf_events rows", updated)
    return updated


def _backfill_event_id_on_items(conn: sqlite3.Connection) -> int:
    """Populate event_id on items rows that lack it.

    Matches items.item_name → events.item_name (case-insensitive), then
    checks event_aliases for renamed events. Child payment rows (parent_item_id
    IS NOT NULL) are resolved via their parent's event_id to avoid re-querying.
    """
    rows = conn.execute(
        "SELECT id, item_name, parent_item_id FROM items WHERE event_id IS NULL"
    ).fetchall()
    if not rows:
        return 0

    # Build name→event_id map from events table
    ev_map: dict[str, int] = {}
    for e in conn.execute("SELECT id, item_name FROM events").fetchall():
        if e["item_name"]:
            ev_map[e["item_name"].strip().lower()] = e["id"]

    # Build alias→event name map
    alias_map: dict[str, str] = {}
    for a in conn.execute("SELECT alias_name, canonical_event_name FROM event_aliases").fetchall():
        if a["alias_name"] and a["canonical_event_name"]:
            alias_map[a["alias_name"].strip().lower()] = a["canonical_event_name"].strip().lower()

    # Cache parent event_id to avoid re-querying for child rows
    parent_cache: dict[int, int | None] = {}

    updated = 0
    for row in rows:
        ev_id: int | None = None

        if row["parent_item_id"] is not None:
            # Child payment row — use parent's event_id
            pid = row["parent_item_id"]
            if pid not in parent_cache:
                pr = conn.execute("SELECT event_id FROM items WHERE id = ?", (pid,)).fetchone()
                parent_cache[pid] = pr["event_id"] if pr else None
            ev_id = parent_cache[pid]
        else:
            name_key = (row["item_name"] or "").strip().lower()
            ev_id = ev_map.get(name_key)
            if ev_id is None:
                # Try alias lookup
                canonical = alias_map.get(name_key)
                if canonical:
                    ev_id = ev_map.get(canonical)

        if ev_id is not None:
            cur = conn.execute(
                "UPDATE items SET event_id = ? WHERE id = ? AND event_id IS NULL",
                (ev_id, row["id"]),
            )
            updated += cur.rowcount

    conn.commit()
    if updated:
        logger.info("Backfilled event_id for %d items rows", updated)
    return updated


def _backfill_event_id_on_string_tables(conn: sqlite3.Connection) -> None:
    """Populate event_id on tables that reference events via a string name column.

    Covers: acct_allocations (event_name), godaddy_order_splits (event_name),
    rsvps (matched_event), expense_transactions (event_name), message_log (event_name).

    Each table has its own event name column; we resolve via events table
    then event_aliases for renamed events.
    """
    # Build name→event_id map
    ev_map: dict[str, int] = {}
    for e in conn.execute("SELECT id, item_name FROM events").fetchall():
        if e["item_name"]:
            ev_map[e["item_name"].strip().lower()] = e["id"]

    alias_map: dict[str, str] = {}
    for a in conn.execute("SELECT alias_name, canonical_event_name FROM event_aliases").fetchall():
        if a["alias_name"] and a["canonical_event_name"]:
            alias_map[a["alias_name"].strip().lower()] = a["canonical_event_name"].strip().lower()

    def _resolve(name: str | None) -> int | None:
        if not name:
            return None
        key = name.strip().lower()
        ev_id = ev_map.get(key)
        if ev_id is None:
            canonical = alias_map.get(key)
            if canonical:
                ev_id = ev_map.get(canonical)
        return ev_id

    table_cfg = [
        # (table, pk_col, name_col)
        ("acct_allocations",     "id", "event_name"),
        ("godaddy_order_splits", "id", "event_name"),
        ("rsvps",                "id", "matched_event"),
        ("expense_transactions", "id", "event_name"),
        ("message_log",          "id", "event_name"),
        ("contractor_payouts",   "id", "event_name"),
    ]
    for tbl, pk, name_col in table_cfg:
        try:
            rows = conn.execute(
                f"SELECT {pk}, {name_col} FROM {tbl} WHERE event_id IS NULL"
            ).fetchall()
        except sqlite3.OperationalError:
            continue  # table or column missing — skip
        updated = 0
        for row in rows:
            ev_id = _resolve(row[name_col])
            if ev_id is not None:
                cur = conn.execute(
                    f"UPDATE {tbl} SET event_id = ? WHERE {pk} = ? AND event_id IS NULL",
                    (ev_id, row[pk]),
                )
                updated += cur.rowcount
        conn.commit()
        if updated:
            logger.info("Backfilled event_id for %d %s rows", updated, tbl)


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
        _touched_gd_orders = set()  # Track GoDaddy orders for order-level accounting
        for row in rows:
            # ── Cross-email-uid dedup gate ──
            # Microsoft Graph occasionally re-keys the same logical email under
            # a brand-new message id (e.g. after a folder rebuild, mass reply
            # to "New Order …" emails, or PWA resync). The existing UNIQUE
            # constraint on (email_uid, item_index) does not catch that — both
            # rows have legitimate uids. Guard at the order_id level instead:
            # if a row with the same (order_id, item_index) already exists
            # under a different email_uid for a real GoDaddy purchase, this is
            # the same order coming in under a new uid, so skip it.
            _oid = (row.get("order_id") or "").strip()
            _idx = row.get("item_index") if row.get("item_index") is not None else 0
            _uid = (row.get("email_uid") or "").strip()
            if _oid and _uid and not _uid.startswith("manual-"):
                _existing = conn.execute(
                    "SELECT id, email_uid FROM items "
                    "WHERE order_id = ? AND item_index = ? AND email_uid != ? "
                    "LIMIT 1",
                    (_oid, _idx, _uid),
                ).fetchone()
                if _existing:
                    logger.info(
                        "save_items: skipping cross-uid duplicate — order_id=%s "
                        "item_index=%s (existing item id=%d uid=%s vs new uid=%s)",
                        _oid, _idx, _existing["id"], _existing["email_uid"], _uid,
                    )
                    skipped += 1
                    continue

            # Auto-resolve customer_id if not already set
            if not row.get("customer_id"):
                row["customer_id"] = _resolve_or_create_customer(
                    conn, row.get("customer"), row.get("customer_email"),
                    phone=row.get("customer_phone"),
                    chapter=row.get("chapter"),
                    user_status=row.get("user_status"),
                    first_name=row.get("first_name"),
                    last_name=row.get("last_name"),
                    email_uid=row.get("email_uid"),
                    order_id=row.get("order_id"),
                    item_name=row.get("item_name"),
                )

            # ── Identity-drift guard ──
            # If the order's customer_email/phone/chapter differs from what the
            # manager has on the Customer Info page, the canonical record wins.
            # The order's value is overwritten to canonical AND a parse_warning
            # is raised so the manager can review the drift in the COO action-
            # items banner. Prevents the "fredwickee@att.net" class of bug
            # where a single typo'd order keeps polluting downstream reads.
            _drift_cid = row.get("customer_id")
            if _drift_cid:
                _drift_canonical = conn.execute(
                    """SELECT
                          (SELECT email FROM customer_emails
                           WHERE customer_id = c.customer_id AND is_primary = 1
                           LIMIT 1) AS canonical_email,
                          c.phone   AS canonical_phone,
                          c.chapter AS canonical_chapter
                       FROM customers c
                       WHERE c.customer_id = ?
                       LIMIT 1""",
                    (_drift_cid,),
                ).fetchone()
                if _drift_canonical:
                    _checks = (
                        ("customer_email", "EMAIL_DRIFT",
                         _drift_canonical["canonical_email"], True),
                        ("customer_phone", "PHONE_DRIFT",
                         _drift_canonical["canonical_phone"], False),
                        ("chapter", "CHAPTER_DRIFT",
                         _drift_canonical["canonical_chapter"], False),
                    )
                    for _field, _code, _canonical, _normalize_lower in _checks:
                        if not _canonical:
                            continue
                        _order_val = (row.get(_field) or "").strip()
                        _can_val = (_canonical or "").strip()
                        if not _order_val:
                            continue
                        _a = _order_val.lower() if _normalize_lower else _order_val
                        _b = _can_val.lower() if _normalize_lower else _can_val
                        if _a == _b:
                            continue
                        # Drift detected → warn + overwrite to canonical
                        try:
                            conn.execute(
                                """INSERT OR IGNORE INTO parse_warnings
                                   (email_uid, order_id, customer, customer_id,
                                    item_name, warning_code, message)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    row.get("email_uid"),
                                    row.get("order_id"),
                                    row.get("customer"),
                                    _drift_cid,
                                    row.get("item_name"),
                                    _code,
                                    f"Order {_field} '{_order_val}' differs from "
                                    f"canonical '{_can_val}' on Customer Info — "
                                    f"order value ignored, canonical kept. "
                                    f"Review and decide whether to update the "
                                    f"customer record or capture as alias.",
                                ),
                            )
                        except Exception:
                            logger.warning(
                                "save_items: failed to log %s for item %s",
                                _code, row.get("email_uid"), exc_info=True,
                            )
                        # Overwrite the row's value with canonical so what
                        # gets persisted matches the customer record.
                        row[_field] = _canonical

            values = tuple(row.get(col) for col in ITEM_COLUMNS)
            try:
                cursor = conn.execute(sql, values)
                if cursor.rowcount > 0:
                    inserted += 1
                    new_item_id = cursor.lastrowid

                    # ── Auto-replace RSVP placeholder when payment arrives ──
                    # If this is a real payment (GoDaddy), check for existing RSVP item
                    # for the same customer + event and remove it
                    try:
                        cust_id = row.get("customer_id")
                        cust_name = row.get("customer") or ""
                        event_name_val = row.get("item_name") or ""
                        merchant_val = row.get("merchant") or ""
                        if cust_name and event_name_val and merchant_val == "The Golf Fellowship":
                            # Match by customer_id (most reliable) or by name
                            rsvp_match = None
                            if cust_id:
                                rsvp_match = conn.execute(
                                    """SELECT id FROM items
                                       WHERE customer_id = ? AND item_name = ? COLLATE NOCASE
                                         AND transaction_status IN ('rsvp_only', 'gg_rsvp')
                                         AND id != ?
                                       LIMIT 1""",
                                    (cust_id, event_name_val, new_item_id),
                                ).fetchone()
                            if not rsvp_match:
                                rsvp_match = conn.execute(
                                    """SELECT id FROM items
                                       WHERE customer = ? COLLATE NOCASE AND item_name = ? COLLATE NOCASE
                                         AND transaction_status IN ('rsvp_only', 'gg_rsvp')
                                         AND id != ?
                                       LIMIT 1""",
                                    (cust_name, event_name_val, new_item_id),
                                ).fetchone()
                            if rsvp_match:
                                conn.execute("DELETE FROM items WHERE id = ?", (rsvp_match["id"],))
                                logger.info("Auto-replaced RSVP item #%d for %s at %s (paid item #%d)",
                                            rsvp_match["id"], cust_name, event_name_val, new_item_id)
                    except Exception:
                        logger.warning("RSVP replacement check failed for item %s",
                                       row.get("email_uid"), exc_info=True)

                    # ── Track GoDaddy orders for order-level accounting ──
                    try:
                        item_price = _parse_dollar(row.get("item_price"))
                        merchant_val = row.get("merchant") or ""
                        if item_price > 0 and merchant_val == "The Golf Fellowship" and not row.get("transferred_from_id"):
                            oid = row.get("order_id") or ""
                            if oid:
                                _touched_gd_orders.add(oid)
                    except Exception:
                        logger.warning("Failed to track GoDaddy order for item %s",
                                       row.get("email_uid"), exc_info=True)

                    # ── Open a customer_memberships term for membership items ──
                    # The daily scheduler job sends the confirmation email; we
                    # just record the term so reminders for the previous term
                    # stop firing.
                    try:
                        item_name_val = (row.get("item_name") or "").lower()
                        if "membership" in item_name_val:
                            from .memberships import record_renewal_for_item
                            record_renewal_for_item(conn, new_item_id, send_email=None)
                    except Exception:
                        logger.warning("Failed to record membership term for item %s",
                                       row.get("email_uid"), exc_info=True)
            except sqlite3.IntegrityError:
                skipped += 1
                logger.debug("Duplicate item skipped: email_uid=%s item_index=%s",
                             row.get("email_uid"), row.get("item_index"))

        # ── Create order-level accounting entries for touched GoDaddy orders ──
        for oid in _touched_gd_orders:
            try:
                order_items = conn.execute(
                    """SELECT * FROM items
                       WHERE order_id = ? AND merchant = 'The Golf Fellowship'
                       AND COALESCE(transaction_status, 'active') NOT IN ('rsvp_only')
                       AND parent_item_id IS NULL
                       AND transferred_from_id IS NULL""",
                    (oid,),
                ).fetchall()
                valid_items = [
                    dict(r) for r in order_items
                    if _parse_dollar(dict(r).get("item_price")) > 0
                    and dict(r).get("transaction_status") not in ("credited", "refunded", "transferred")
                ]
                if valid_items:
                    _write_godaddy_order_entry(
                        conn,
                        order_id=oid,
                        items=valid_items,
                        date=valid_items[0].get("order_date") or "",
                    )
            except Exception:
                logger.warning("Failed to create order-level accounting for order %s",
                               oid, exc_info=True)

        conn.commit()
        logger.info("Saved %d new item rows, %d duplicates skipped (%d total provided)",
                    inserted, skipped, len(rows))
        return inserted


def get_known_email_uids(db_path: str | Path | None = None) -> set[str]:
    """Return the set of email_uid values already processed (with or without items)."""
    with _connect(db_path) as conn:
        # Check both tables: items (legacy) and processed_emails (new)
        uids = set()
        for row in conn.execute("SELECT DISTINCT email_uid FROM items").fetchall():
            uids.add(row["email_uid"])
        try:
            for row in conn.execute("SELECT email_uid FROM processed_emails").fetchall():
                uids.add(row["email_uid"])
        except sqlite3.OperationalError:
            pass  # table doesn't exist yet (pre-migration)
        return uids


def mark_email_processed(email_uid: str, items_found: int = 0,
                         db_path: str | Path | None = None) -> None:
    """Record that an email has been processed, even if no items were extracted."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_emails (email_uid, items_found) VALUES (?, ?)",
            (email_uid, items_found),
        )
        conn.commit()


def clear_failed_processed(db_path: str | Path | None = None) -> int:
    """Remove processed_emails entries that yielded 0 items so they can be retried."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM processed_emails WHERE items_found = 0"
        )
        conn.commit()
        return cursor.rowcount


def get_all_items(db_path: str | Path | None = None) -> list[dict]:
    """Return all item rows ordered by order_date descending."""
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM items ORDER BY order_date DESC, order_time DESC, id DESC").fetchall()
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
            total_spent += _parse_dollar(r["item_price"])

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
        rows = conn.execute("SELECT * FROM items ORDER BY order_date DESC, order_time DESC, id DESC").fetchall()

        if not rows:
            return {"total_items": 0, "message": "No items in database."}

        items = [dict(r) for r in rows]
        total = len(items)

        # --- Field fill rates ---------------------------------------------------
        critical_fields = [
            "customer", "customer_email", "order_id", "order_date",
            "item_name", "item_price", "chapter", "course",
        ]
        golf_fields = [
            "handicap", "side_games", "tee_choice", "user_status",
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
        for field in ["chapter", "course", "user_status", "tee_choice"]:
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

# Canonical course names — if an item_name is JUST a course name, it's
# probably a parsing error (missing event code like "a9.1").
_KNOWN_COURSE_NAMES = {
    "la cantera", "tpc san antonio", "the quarry", "cowboys golf club",
    "tpc craig ranch", "wolfdancer", "falconhead", "moody gardens",
    "morris williams", "cedar creek", "kissing tree", "plum creek",
    "landa park", "vaaler creek", "hancock park", "shadowglen", "star ranch",
}

# Keywords that indicate an item is NOT an event (membership, merch, etc.)
_NON_EVENT_KEYWORDS = [
    "member", "membership", "shirt", "merch", "hat", "polo",
    "donation", "gift card", "season pass",
    "roster import", "rsvp import", "rsvp email link", "customer entry",
]


def _is_event_item(item_name: str, *, course: str = "", chapter: str = "") -> bool:
    """Heuristic: an item is an event if it has a date-like pattern, course name,
    event-type keyword, series identifier, or course/chapter metadata."""
    if not item_name:
        return False
    lower = item_name.lower()
    # Exclude memberships, merch, etc.
    for kw in _NON_EVENT_KEYWORDS:
        if kw in lower:
            return False
    # If the item row has course or chapter metadata → it's an event
    if (course and course.strip()) or (chapter and chapter.strip()):
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
        "star ranch",
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
            "SELECT DISTINCT item_name, course, chapter FROM items"
        ).fetchall()

        # Load existing aliases so we can skip aliased names (case-insensitive)
        alias_set = set(
            r["alias_name"].lower()
            for r in conn.execute("SELECT alias_name FROM event_aliases").fetchall()
            if r["alias_name"]
        )

        inserted = 0
        skipped_non_event = 0
        skipped_aliased = 0
        suspicious_names = []
        for item in items:
            name = item["item_name"] or ""
            if not _is_event_item(name, course=item["course"] or "", chapter=item["chapter"] or ""):
                skipped_non_event += 1
                continue
            # Skip names that are aliases of another event
            if name.lower() in alias_set:
                skipped_aliased += 1
                continue
            # Case-insensitive duplicate check — auto-create alias when case differs
            existing = conn.execute(
                "SELECT id, item_name FROM events WHERE LOWER(item_name) = LOWER(?)", (name,)
            ).fetchone()
            if existing:
                # If item_name differs only in case, register it as an alias
                if existing["item_name"] != name:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO event_aliases (alias_name, canonical_event_name) VALUES (?, ?)",
                            (name, existing["item_name"]),
                        )
                        alias_set.add(name.lower())
                    except Exception:
                        logger.debug("Failed to auto-create alias for %r", name, exc_info=True)
                continue
            try:
                conn.execute(
                    """INSERT INTO events (item_name, course, chapter, event_type)
                       VALUES (?, ?, ?, 'event')""",
                    (name, item["course"], item["chapter"]),
                )
                inserted += 1
                # Flag events whose name is suspiciously just a course name
                if name.strip().lower() in _KNOWN_COURSE_NAMES:
                    suspicious_names.append(name)
                    logger.warning(
                        "Suspicious event name '%s' — looks like just a course name "
                        "(event code likely missing from parsed item_name)", name,
                    )
                    # Auto-create a parse warning so admins see it
                    try:
                        conn.execute(
                            """INSERT OR IGNORE INTO parse_warnings
                               (email_uid, order_id, customer, item_name,
                                warning_code, message)
                               SELECT i.email_uid, i.order_id, i.customer, i.item_name,
                                      'COURSE_NAME_ONLY',
                                      'Event "' || i.item_name || '" looks like just a course name — the event identifier (e.g. series code) was likely missed during parsing.'
                               FROM items i
                               WHERE i.item_name = ? COLLATE NOCASE
                               LIMIT 1""",
                            (name,),
                        )
                    except Exception:
                        logger.debug("Failed to create COURSE_NAME_ONLY warning for %r", name, exc_info=True)
            except sqlite3.IntegrityError:
                logger.debug("Duplicate event skipped during sync: %s", name)

        conn.commit()
        logger.info("Events sync: %d new, %d non-event skipped, %d aliased skipped",
                    inserted, skipped_non_event, skipped_aliased)
        if suspicious_names:
            logger.warning("Events sync: %d suspicious event names (course-name-only): %s",
                          len(suspicious_names), ", ".join(suspicious_names))
        return {"inserted": inserted, "skipped_non_event": skipped_non_event,
                "skipped_aliased": skipped_aliased, "total_items_scanned": len(items),
                "suspicious_names": suspicious_names}


def get_mvp_unlinked_events(db_path: str | Path | None = None) -> list[str]:
    """Return list of event names that have been explicitly unlinked from
    same-day TGF MVP combining."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT event_name FROM event_mvp_unlinks"
        ).fetchall()
    return [r["event_name"] for r in rows]


def set_mvp_unlink(event_name: str, unlink: bool = True,
                   db_path: str | Path | None = None) -> None:
    """Insert or delete an event from the MVP unlinks table."""
    with _connect(db_path) as conn:
        if unlink:
            conn.execute(
                "INSERT OR IGNORE INTO event_mvp_unlinks (event_name) VALUES (?)",
                (event_name,),
            )
        else:
            conn.execute(
                "DELETE FROM event_mvp_unlinks WHERE event_name = ?",
                (event_name,),
            )
        conn.commit()


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
                ON (i.item_name = e.item_name COLLATE NOCASE OR i.item_name = ea.alias_name COLLATE NOCASE)
                AND COALESCE(i.transaction_status, 'active') = 'active'
                AND i.parent_item_id IS NULL
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
    allowed = {"item_name", "event_date", "course", "chapter", "format", "start_type", "start_time",
                "tee_time_count", "tee_time_interval", "start_time_18", "start_type_18",
                "tee_time_count_18", "event_type", "tee_direction", "tee_direction_18",
                "course_cost", "tgf_markup", "side_game_fee", "transaction_fee_pct",
                "course_cost_9", "course_cost_18", "tgf_markup_9", "tgf_markup_18",
                "side_game_fee_9", "side_game_fee_18",
                "tgf_markup_final", "tgf_markup_final_9", "tgf_markup_final_18",
                "course_surcharge", "per_game_addon",
                "course_cost_breakdown", "course_cost_breakdown_9", "course_cost_breakdown_18",
                "rescheduled_to_event_id"}
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
    """Delete an event by ID.

    If transaction items still reference this event name, the name is
    preserved as an alias (pointing to '_DELETED_') so that
    sync_events_from_items() and seed_events() don't recreate it.
    """
    with _connect(db_path) as conn:
        row = conn.execute("SELECT item_name FROM events WHERE id = ?", (event_id,)).fetchone()
        if row:
            event_name = row["item_name"]
            # Re-point any aliases that targeted this event to _DELETED_
            conn.execute(
                "UPDATE event_aliases SET canonical_event_name = '_DELETED_' "
                "WHERE canonical_event_name = ?",
                (event_name,),
            )
            # If items still use this name, add it as an alias so sync skips it
            has_items = conn.execute(
                "SELECT 1 FROM items WHERE item_name = ? COLLATE NOCASE LIMIT 1",
                (event_name,),
            ).fetchone()
            if has_items:
                conn.execute(
                    "INSERT OR IGNORE INTO event_aliases "
                    "(alias_name, canonical_event_name) VALUES (?, '_DELETED_')",
                    (event_name,),
                )
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
            "SELECT COUNT(*) as cnt FROM items WHERE item_name = ? COLLATE NOCASE AND COALESCE(transaction_status, 'active') = 'active'",
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
                      MIN(i.course) as course,
                      MIN(i.chapter) as chapter,
                      GROUP_CONCAT(DISTINCT i.customer) as customers
               FROM items i
               LEFT JOIN events e ON i.item_name = e.item_name COLLATE NOCASE
               LEFT JOIN event_aliases ea ON i.item_name = ea.alias_name COLLATE NOCASE
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
            "SELECT COUNT(*) as cnt FROM items WHERE item_name = ? COLLATE NOCASE AND COALESCE(transaction_status, 'active') IN ('active', 'rsvp_only')",
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
# Parse Warnings
# ---------------------------------------------------------------------------


def save_parse_warnings(rows: list[dict], db_path: str | Path | None = None) -> int:
    """Persist parse warnings extracted from parsed item rows.

    Looks for ``_parse_warnings`` lists attached by ``_validate_parsed_items()``.
    Deduplicates by (email_uid, warning_code, item_name).
    Returns number of warnings saved.
    """
    saved = 0
    with _connect(db_path) as conn:
        for row in rows:
            warnings = row.get("_parse_warnings")
            if not warnings:
                continue
            for w in warnings:
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO parse_warnings
                           (email_uid, order_id, customer, item_name, warning_code, message)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            row.get("email_uid"),
                            row.get("order_id"),
                            row.get("customer"),
                            row.get("item_name"),
                            w["code"],
                            w["message"],
                        ),
                    )
                    saved += 1
                except Exception:
                    logger.exception("Failed to save parse warning")
        conn.commit()
    if saved:
        logger.warning("Saved %d parse warnings", saved)
    return saved


def get_parse_warnings(status: str = "open",
                       db_path: str | Path | None = None) -> list[dict]:
    """Return parse warnings filtered by status."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM parse_warnings WHERE status = ? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
        return [dict(r) for r in rows]


def dismiss_parse_warning(warning_id: int,
                          db_path: str | Path | None = None) -> bool:
    """Dismiss a parse warning."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE parse_warnings SET status = 'dismissed' WHERE id = ?",
            (warning_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def resolve_parse_warning(warning_id: int,
                          db_path: str | Path | None = None) -> bool:
    """Mark a parse warning as resolved."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE parse_warnings SET status = 'resolved' WHERE id = ?",
            (warning_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def scan_price_games_mismatches(db_path: str | Path | None = None) -> dict:
    """Scan all existing items for item_price vs total_amount mismatches.

    For each GoDaddy item, compares item_price against (total_amount - transaction_fees).
    If they don't match (> $1 tolerance), the parser likely grabbed a description price
    instead of the actual charged amount. Works for ALL events and pricing tiers.

    Creates parse_warnings for any mismatches found. Returns a summary dict.
    """
    results = {"scanned": 0, "warnings_created": 0, "already_warned": 0, "details": []}

    with _connect(db_path) as conn:
        items = conn.execute(
            """SELECT id, email_uid, order_id, customer, item_name,
                      item_price, total_amount, transaction_fees, coupon_amount
               FROM items
               WHERE COALESCE(transaction_status, 'active') = 'active'
               AND parent_item_id IS NULL
               AND item_price IS NOT NULL
               AND total_amount IS NOT NULL
               AND merchant NOT IN ('Manual Entry', 'RSVP Only', 'Roster Import',
                                     'Customer Entry', 'RSVP Import', 'RSVP Email Link')
               AND email_uid NOT LIKE 'manual-%'
               AND email_uid NOT LIKE 'transfer-%'"""
        ).fetchall()

        results["scanned"] = len(items)

        for item in items:
            price = _parse_dollar(item["item_price"])
            total = _parse_dollar(item["total_amount"])
            fees = _parse_dollar(item["transaction_fees"])
            coupon = abs(_parse_dollar(item["coupon_amount"]))

            if price <= 0 or total <= 0:
                continue

            # Coupon discounts reduce total_amount but not item_price; add back.
            expected_price = round(total - fees + coupon, 2)
            if abs(price - expected_price) <= 1.0:
                continue  # within tolerance

            # Check if warning already exists
            existing = conn.execute(
                "SELECT id FROM parse_warnings WHERE email_uid = ? AND warning_code = ? AND item_name = ?",
                (item["email_uid"], "price_total_mismatch", item["item_name"]),
            ).fetchone()

            if existing:
                results["already_warned"] += 1
                continue

            coupon_msg = f" + coupon=${coupon:.2f}" if coupon > 0 else ""
            msg = (f"item_price=${price:.2f} does not match "
                   f"total_amount=${total:.2f} - transaction_fees=${fees:.2f}{coupon_msg} = "
                   f"${expected_price:.2f}. Parser may have grabbed a description "
                   f"price instead of the actual charged amount. "
                   f"Order: {item['order_id'] or '?'}")

            conn.execute(
                """INSERT OR IGNORE INTO parse_warnings
                   (email_uid, order_id, customer, item_name, warning_code, message)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (item["email_uid"], item["order_id"], item["customer"],
                 item["item_name"], "price_total_mismatch", msg),
            )
            results["warnings_created"] += 1
            results["details"].append({
                "id": item["id"], "customer": item["customer"],
                "item_name": item["item_name"], "item_price": price,
                "expected": expected_price, "order_id": item["order_id"],
            })

        conn.commit()

    return results


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
               "first_name", "last_name", "middle_name", "suffix",
               "address", "address2", "city", "state", "zip",
               "venmo_username", "current_player_status"}
    safe = {k: v for k, v in fields.items() if k in allowed}
    if not safe:
        return 0

    # venmo_username is stored on the customers table, not items — extract it
    venmo_username = safe.pop("venmo_username", None)
    if venmo_username is not None:
        # Normalize: strip leading @ if provided
        venmo_username = venmo_username.lstrip("@").strip()

    # current_player_status is stored on the customers table, not items — extract it
    current_player_status = safe.pop("current_player_status", None)
    if current_player_status is not None:
        allowed_ps = {"active_member", "member_plus", "expired_member", "active_guest", "inactive", "first_timer", ""}
        if current_player_status and current_player_status not in allowed_ps:
            raise ValueError(f"Invalid current_player_status: {current_player_status}")

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

    with _connect(db_path) as conn:
        rowcount = 0

        # Update items table (for item-level fields)
        if safe:
            _validate_column_names(list(safe))
            set_clause = ", ".join(f"{col} = ?" for col in safe)
            values = list(safe.values()) + [customer_name]
            cursor = conn.execute(
                f"UPDATE items SET {set_clause} WHERE customer = ? COLLATE NOCASE",
                values,
            )
            rowcount = cursor.rowcount
            # Update alias references if display name changed
            if "customer" in safe and safe["customer"] != customer_name:
                conn.execute(
                    "UPDATE customer_aliases SET customer_name = ? WHERE customer_name = ? COLLATE NOCASE",
                    (safe["customer"], customer_name),
                )
                # Also update handicap_player_links so handicap stays connected
                conn.execute(
                    "UPDATE handicap_player_links SET customer_name = ? WHERE customer_name = ? COLLATE NOCASE",
                    (safe["customer"], customer_name),
                )

        # Resolve customer_id for all canonical-table syncs below
        cid_row = conn.execute(
            """SELECT customer_id FROM items
               WHERE customer = ? COLLATE NOCASE AND customer_id IS NOT NULL
               LIMIT 1""",
            (customer_name,),
        ).fetchone()
        cid = cid_row["customer_id"] if cid_row else None
        if not cid:
            # Fall back to name match in customers table directly
            parts = customer_name.strip().split()
            if len(parts) >= 2:
                cid_row = conn.execute(
                    """SELECT customer_id FROM customers
                       WHERE LOWER(first_name) = LOWER(?) AND LOWER(last_name) = LOWER(?)
                       LIMIT 1""",
                    (parts[0], parts[-1]),
                ).fetchone()
                cid = cid_row["customer_id"] if cid_row else None

        if cid:
            # Sync email to customer_emails (source of truth for customer contact)
            new_email = safe.get("customer_email")
            if new_email is not None:
                if new_email:
                    existing = conn.execute(
                        "SELECT email_id FROM customer_emails WHERE customer_id = ? AND is_primary = 1",
                        (cid,),
                    ).fetchone()
                    if existing:
                        conn.execute(
                            "UPDATE customer_emails SET email = ? WHERE customer_id = ? AND is_primary = 1",
                            (new_email, cid),
                        )
                    else:
                        try:
                            conn.execute(
                                """INSERT INTO customer_emails (customer_id, email, is_primary, label)
                                   VALUES (?, ?, 1, 'manual')""",
                                (cid, new_email),
                            )
                        except sqlite3.IntegrityError:
                            pass  # email already owned by another customer
                else:
                    # Clearing the email — remove primary flag but leave row for audit
                    conn.execute(
                        "UPDATE customer_emails SET is_primary = 0 WHERE customer_id = ? AND is_primary = 1",
                        (cid,),
                    )

            # Sync phone to customers.phone (source of truth)
            new_phone = safe.get("customer_phone")
            if new_phone is not None:
                conn.execute(
                    "UPDATE customers SET phone = ?, updated_at = CURRENT_TIMESTAMP WHERE customer_id = ?",
                    (new_phone or None, cid),
                )

            # Sync first/last name + chapter to the customers master record.
            # The customers row is the authoritative source for chapter — items
            # is denormalized and per-row, so the customers page now reads
            # chapter directly via /api/customer-roles.
            name_fields = {}
            if "first_name" in safe:
                name_fields["first_name"] = safe["first_name"]
            if "last_name" in safe:
                name_fields["last_name"] = safe["last_name"]
            if "chapter" in safe:
                name_fields["chapter"] = safe["chapter"] or None
            if name_fields:
                set_parts = ", ".join(f"{k} = ?" for k in name_fields)
                conn.execute(
                    f"UPDATE customers SET {set_parts}, updated_at = CURRENT_TIMESTAMP WHERE customer_id = ?",
                    list(name_fields.values()) + [cid],
                )

        # Update venmo_username on the customers table (customer-level field)
        if venmo_username is not None:
            conn.execute(
                """UPDATE customers SET venmo_username = ?
                   WHERE customer_id = (
                       SELECT customer_id FROM items
                       WHERE customer = ? COLLATE NOCASE AND customer_id IS NOT NULL
                       LIMIT 1
                   )""",
                (venmo_username or None, customer_name),
            )
            rowcount = max(rowcount, 1)

        # Update current_player_status on the customers table (customer-level field)
        if current_player_status is not None:
            val = current_player_status or None
            conn.execute(
                """UPDATE customers SET current_player_status = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE LOWER(first_name || ' ' || last_name) = LOWER(?)""",
                (val, customer_name),
            )
            rowcount = max(rowcount, 1)

        conn.commit()
        return rowcount


def get_customer_venmo_handles(db_path=None) -> list[dict]:
    """Return all customers that have a venmo_username set.

    Returns list of {customer_name, venmo_username}.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT c.customer_id, i.customer AS customer_name, c.venmo_username
               FROM customers c
               JOIN items i ON i.customer_id = c.customer_id
               WHERE c.venmo_username IS NOT NULL AND c.venmo_username != ''
               GROUP BY c.customer_id"""
        ).fetchall()
        return [{"customer_name": r["customer_name"],
                 "venmo_username": r["venmo_username"]} for r in rows]


def get_all_customers(db_path=None) -> list[dict]:
    """Return all customer records from the canonical customers + customer_emails tables.

    This is the source-of-truth read path for customer identity data.  Every
    field here comes from the customers / customer_emails tables, not from
    items.  The Customers page should overlay this data on top of
    transaction-derived info so canonical contact details always win.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT
                   c.customer_id,
                   c.first_name,
                   c.last_name,
                   TRIM(COALESCE(NULLIF(c.company_name,''),
                        NULLIF(TRIM(c.first_name || ' ' || c.last_name), ''))) AS customer_name,
                   c.phone,
                   c.venmo_username,
                   c.current_player_status,
                   c.chapter,
                   c.ghin_number,
                   c.account_status,
                   c.updated_at,
                   ce.email   AS primary_email,
                   ce.label   AS email_label
               FROM customers c
               LEFT JOIN customer_emails ce
                      ON ce.customer_id = c.customer_id AND ce.is_primary = 1
               ORDER BY c.last_name COLLATE NOCASE, c.first_name COLLATE NOCASE"""
        ).fetchall()
        return [dict(r) for r in rows]


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
        # Link to customers record if one already exists (e.g. vendor created via vendor modal)
        new_values["customer_id"] = _lookup_customer_id(conn, name, email or None)
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

            # Extract venmo_username (stored on customers table, not items)
            venmo_raw = (row.get("venmo_username") or "").strip().lstrip("@").strip()

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

                # Update venmo_username on customers table if provided
                if venmo_raw:
                    conn.execute(
                        """UPDATE customers SET venmo_username = ?
                           WHERE customer_id = (
                               SELECT customer_id FROM items
                               WHERE customer = ? COLLATE NOCASE AND customer_id IS NOT NULL
                               LIMIT 1
                           ) AND (venmo_username IS NULL OR venmo_username = '')""",
                        (venmo_raw, existing_name),
                    )
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

                # Set venmo_username on the new customer record if provided
                if venmo_raw:
                    conn.execute(
                        """UPDATE customers SET venmo_username = ?
                           WHERE customer_id = (
                               SELECT customer_id FROM items
                               WHERE customer = ? COLLATE NOCASE AND customer_id IS NOT NULL
                               LIMIT 1
                           )""",
                        (venmo_raw, name),
                    )

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

        # ---- Merge customers table records (customer_id) ----
        # Find target and source customer_ids
        target_cust = conn.execute(
            """SELECT customer_id FROM customers
               WHERE LOWER(first_name || ' ' || last_name) = LOWER(?)
               LIMIT 1""",
            (target_name.strip(),),
        ).fetchone()
        source_cust = conn.execute(
            """SELECT customer_id FROM customers
               WHERE LOWER(first_name || ' ' || last_name) = LOWER(?)
               LIMIT 1""",
            (source_name.strip(),),
        ).fetchone()

        if target_cust and source_cust and target_cust["customer_id"] != source_cust["customer_id"]:
            target_cid = target_cust["customer_id"]
            source_cid = source_cust["customer_id"]

            # Reassign all items from source customer_id to target
            conn.execute(
                "UPDATE items SET customer_id = ? WHERE customer_id = ?",
                (target_cid, source_cid),
            )

            # Reassign tgf_payouts from source to target
            conn.execute(
                "UPDATE tgf_payouts SET customer_id = ? WHERE customer_id = ?",
                (target_cid, source_cid),
            )

            # Reassign acct_transactions customer field
            conn.execute(
                """UPDATE acct_transactions SET customer = ?
                   WHERE customer = ? COLLATE NOCASE""",
                (target_name, source_name),
            )

            # Move source's customer_emails to target (skip duplicates)
            src_emails = conn.execute(
                "SELECT email FROM customer_emails WHERE customer_id = ?",
                (source_cid,),
            ).fetchall()
            for e in src_emails:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO customer_emails (customer_id, email, label) VALUES (?, ?, 'merged')",
                        (target_cid, e["email"]),
                    )
                except sqlite3.IntegrityError:
                    pass
            conn.execute("DELETE FROM customer_emails WHERE customer_id = ?", (source_cid,))

            # Delete the now-orphaned source customers row
            conn.execute("DELETE FROM customers WHERE customer_id = ?", (source_cid,))
            logger.info("Merged customer_id %d → %d (emails moved, source deleted)",
                        source_cid, target_cid)
        elif target_cust and not source_cust:
            # Source has no customers row — just reassign any items with source name
            conn.execute(
                "UPDATE items SET customer_id = ? WHERE customer = ? AND customer_id IS NULL",
                (target_cust["customer_id"], target_name),
            )

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


def delete_event_alias(alias_name: str, db_path: str | Path | None = None) -> bool:
    """Delete an alias by name. Returns True if deleted, False if not found."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM event_aliases WHERE alias_name = ?", (alias_name,)
        )
        conn.commit()
        return cur.rowcount > 0


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
    """Mark an item as credited (money held for future use). Cascades to child payments."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "UPDATE items SET transaction_status = 'credited', credit_note = ? WHERE id = ? AND COALESCE(transaction_status, 'active') = 'active'",
            (note or "Credit on account", item_id),
        )
        # Cascade to child payment items
        conn.execute(
            "UPDATE items SET transaction_status = 'credited', credit_note = ? "
            "WHERE parent_item_id = ? AND COALESCE(transaction_status, 'active') = 'active'",
            (note or "Credit on account (cascaded from parent)", item_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def refund_item(item_id: int, method: str = "", note: str = "",
                db_path: str | Path | None = None) -> bool:
    """Mark an item as refunded via GoDaddy or Venmo. Cascades to child payments."""
    refund_note = f"Refunded via {method}" if method else "Refunded"
    if note:
        refund_note += f" — {note}"
    with _connect(db_path) as conn:
        # Fetch item details before updating (needed for accounting entry)
        item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()

        cursor = conn.execute(
            "UPDATE items SET transaction_status = 'refunded', credit_note = ? "
            "WHERE id = ? AND COALESCE(transaction_status, 'active') = 'active'",
            (refund_note, item_id),
        )
        # Cascade to child payment items
        conn.execute(
            "UPDATE items SET transaction_status = 'refunded', credit_note = ? "
            "WHERE parent_item_id = ? AND COALESCE(transaction_status, 'active') = 'active'",
            (refund_note + " (cascaded from parent)", item_id),
        )

        # ── Unified Financial Model: create refund accounting entry ──
        if cursor.rowcount > 0 and item:
            try:
                item = dict(item)
                refund_amount = _parse_dollar(item.get("item_price"))
                if refund_amount > 0:
                    source_ref = f"refund-{item_id}"
                    if not conn.execute("SELECT id FROM acct_transactions WHERE source_ref = ?", (source_ref,)).fetchone():
                        event_name = item.get("item_name", "")
                        event_row = conn.execute(
                            "SELECT id FROM events WHERE item_name = ? COLLATE NOCASE",
                            (event_name,),
                        ).fetchone()
                        tgf_entity = conn.execute(
                            "SELECT id FROM acct_entities WHERE short_name = 'TGF'"
                        ).fetchone()
                        cat_refund = conn.execute(
                            "SELECT id FROM acct_categories WHERE name = 'Player Refunds'"
                        ).fetchone()

                        tgf_id = tgf_entity["id"] if tgf_entity else 1
                        event_db_id = event_row["id"] if event_row else None
                        cat_id = cat_refund["id"] if cat_refund else None

                        cur_txn = conn.execute(
                            """INSERT INTO acct_transactions
                               (date, description, total_amount, type, source, source_ref)
                               VALUES (?, ?, ?, 'expense', 'refund', ?)""",
                            (item.get("order_date") or "",
                             f"Refund ({method}): {item.get('customer', '')} — {event_name}",
                             refund_amount, source_ref),
                        )
                        conn.execute(
                            "INSERT INTO acct_splits (transaction_id, entity_id, category_id, amount, memo, event_id) VALUES (?, ?, ?, ?, ?, ?)",
                            (cur_txn.lastrowid, tgf_id, cat_id, refund_amount,
                             refund_note, event_db_id),
                        )
            except Exception:
                logger.warning("Failed to create accounting entry for refund %s", item_id, exc_info=True)

            # ── Flat acct_transactions entry for single-source-of-truth ──
            try:
                item_d = dict(item) if not isinstance(item, dict) else item
                refund_amount = _parse_dollar(item_d.get("item_price"))
                if refund_amount > 0:
                    refund_source = "manual"
                    if method:
                        refund_source = method.lower().replace(" ", "_")
                    _m = (method or "").lower()
                    refund_account = "Venmo" if "venmo" in _m else ("PayPal" if "paypal" in _m else "TGF Checking")
                    _write_acct_entry(
                        conn,
                        item_id=item_id,
                        event_name=item_d.get("item_name", ""),
                        customer=item_d.get("customer", ""),
                        order_id=item_d.get("order_id", ""),
                        entry_type="expense",
                        category="refund",
                        source=refund_source,
                        amount=refund_amount,
                        description=f"Refund ({method}): {item_d.get('customer', '')} — {item_d.get('item_name', '')}",
                        account=refund_account,
                        source_ref=f"refund-flat-{item_id}",
                        date=item_d.get("order_date") or "",
                    )
            except Exception:
                logger.warning("Failed to create flat accounting entry for refund %s", item_id, exc_info=True)

        conn.commit()
        return cursor.rowcount > 0


def payout_credit(
    item_id: int,
    method: str = "",
    note: str = "",
    refund_date: str = "",
    db_path: str | Path | None = None,
) -> dict:
    """Record a cash payout of an outstanding player credit.

    Handles two row shapes:

      * WD rows (transaction_status='wd') — the credit lives in
        ``credit_amount``. After payout, that field is cleared but the
        row stays WD; ``credit_note`` is stamped with the refund summary.
      * Standalone credit rows (transaction_status='credited') — the
        credit lives in ``item_price`` (e.g. excess credits, overpayment
        credits, or full registration credits). After payout, status is
        flipped to 'refunded' so the customer's credit balance no longer
        counts it; ``credit_note`` is stamped with the refund summary.

    In both cases a flat ``acct_transactions`` expense entry is written
    so bank reconciliation can match the actual Venmo/Zelle/Check.

    Returns {"ok": True, "amount": float, "date": str} on success, or
    {"ok": False, "error": str} on validation/lookup failure.
    """
    import datetime as _dt
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "Item not found"}
        item = dict(row)
        status = (item.get("transaction_status") or "").lower()
        if status == "wd":
            amount = _parse_dollar(item.get("credit_amount"))
            if amount <= 0:
                return {"ok": False, "error": "WD row has no outstanding credit to pay out"}
        elif status == "credited":
            amount = _parse_dollar(item.get("item_price"))
            if amount <= 0:
                return {"ok": False, "error": "Credit row has no balance to pay out"}
        else:
            return {"ok": False, "error": "Item is not in WD or credited status"}

        date_str = (refund_date or "").strip() or _dt.datetime.now().strftime("%Y-%m-%d")

        try:
            refund_source = method.lower().replace(" ", "_") if method else "manual"
            _m = (method or "").lower()
            refund_account = "Venmo" if "venmo" in _m else ("PayPal" if "paypal" in _m else "TGF Checking")
            label = "WD credit refund" if status == "wd" else "Credit payout"
            _write_acct_entry(
                conn,
                item_id=item_id,
                event_name=item.get("item_name", ""),
                customer=item.get("customer", ""),
                order_id=item.get("order_id", ""),
                entry_type="expense",
                category="refund",
                source=refund_source,
                amount=amount,
                description=(
                    f"{label} ({method or 'manual'}): "
                    f"{item.get('customer', '')} — {item.get('item_name', '')}"
                ),
                account=refund_account,
                source_ref=f"credit-payout-{item_id}",
                date=date_str,
            )
        except Exception:
            logger.warning("Failed to write acct entry for credit payout %s", item_id, exc_info=True)
            return {"ok": False, "error": "Could not write accounting entry"}

        stamp = f"Refunded ${amount:.2f} via {method or 'manual'} on {date_str}"
        if note:
            stamp += f" — {note}"
        if status == "wd":
            conn.execute(
                "UPDATE items SET credit_amount = NULL, credit_note = ? WHERE id = ?",
                (stamp, item_id),
            )
        else:
            conn.execute(
                "UPDATE items SET transaction_status = 'refunded', credit_note = ? WHERE id = ?",
                (stamp, item_id),
            )
        conn.commit()
        return {"ok": True, "amount": amount, "date": date_str}


# Back-compat alias for the original WD-only entry point.
payout_wd_credit = payout_credit


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
        # Cascade WD to child payment items
        conn.execute(
            "UPDATE items SET transaction_status = 'wd', wd_reason = 'WD', wd_note = ? "
            "WHERE parent_item_id = ? AND COALESCE(transaction_status, 'active') = 'active'",
            (note or "WD (cascaded from parent)", item_id),
        )

        # ── Accounting: liability entry for WD credits ──
        if cursor.rowcount > 0 and credit_amount:
            try:
                wd_credit_val = _parse_dollar(credit_amount)
                if wd_credit_val > 0:
                    item_row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
                    if item_row:
                        item_d = dict(item_row)
                        _write_acct_entry(
                            conn,
                            item_id=item_id,
                            event_name=item_d.get("item_name", ""),
                            customer=item_d.get("customer", ""),
                            order_id=item_d.get("order_id", ""),
                            entry_type="liability",
                            category="credit_issued",
                            source="manual",
                            amount=wd_credit_val,
                            description=f"WD credit issued: {item_d.get('customer', '')} — {item_d.get('item_name', '')}",
                            account="TGF Checking",
                            source_ref=f"wd-credit-{item_id}",
                            date=item_d.get("order_date") or "",
                        )
            except Exception:
                logger.warning("Failed to create liability entry for WD %s", item_id, exc_info=True)

        conn.commit()
        return cursor.rowcount > 0


def transfer_item(item_id: int, target_event_name: str, note: str = "", db_path: str | Path | None = None) -> dict | None:
    """
    Transfer an item to a different event.

    Marks the original (and any active +PAY children) as 'transferred' and
    creates ONE new item at the target event for the combined credit. The
    new item's item_price reflects parent + summed children so the receiving
    event sees the full amount the player paid, not just the parent slice.
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

        # Fetch the target event for date/course/chapter
        target_event = conn.execute(
            "SELECT * FROM events WHERE item_name = ? COLLATE NOCASE", (target_event_name,)
        ).fetchone()
        target_event = dict(target_event) if target_event else {}

        # Sum any active +PAY children so the target sees the combined credit.
        active_children = conn.execute(
            """SELECT id, item_price FROM items
               WHERE parent_item_id = ?
                 AND COALESCE(transaction_status, 'active') = 'active'""",
            (item_id,),
        ).fetchall()
        children_total = sum(_parse_dollar(c["item_price"]) for c in active_children)

        # Mark original as transferred
        transfer_note = note or f"Transferred to {target_event_name}"
        conn.execute(
            "UPDATE items SET transaction_status = 'transferred', credit_note = ? WHERE id = ?",
            (transfer_note, item_id),
        )
        # Cascade transferred status to active +PAY children
        for ch in active_children:
            conn.execute(
                """UPDATE items
                   SET transaction_status = 'transferred',
                       credit_note = ?
                   WHERE id = ?""",
                (f"Transferred to {target_event_name} (cascaded from parent)", ch["id"]),
            )

        # Create new item at target event with COMBINED credit amount
        orig_price_amt = _parse_dollar(orig.get("item_price"))
        combined_amt = round(orig_price_amt + children_total, 2)
        new_values = {col: orig.get(col) for col in ITEM_COLUMNS}
        new_values["item_name"] = target_event_name
        new_values["course"] = target_event.get("course") or orig.get("course")
        new_values["chapter"] = target_event.get("chapter") or orig.get("chapter")
        new_values["item_price"] = f"${combined_amt:.2f} (credit)"
        new_values["email_uid"] = f"transfer-{item_id}"
        new_values["item_index"] = 0
        new_values["order_date"] = orig.get("order_date") or ""
        new_values["transaction_status"] = "active"
        if children_total > 0:
            new_values["credit_note"] = (
                f"Transferred from {orig.get('item_name', '')} (#{item_id}) "
                f"— ${orig_price_amt:.2f} parent + ${children_total:.2f} +PAY"
            )
        else:
            new_values["credit_note"] = f"Transferred from {orig.get('item_name', '')} (#{item_id})"
        new_values["transferred_from_id"] = item_id
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
        # Link children to the same target so the chain is intact
        for ch in active_children:
            conn.execute(
                "UPDATE items SET transferred_to_id = ? WHERE id = ?",
                (new_id, ch["id"]),
            )

        # ── Unified Financial Model: create accounting entries ──
        try:
            source_event_name = orig.get("item_name", "")

            if combined_amt > 0:
                alloc_date = orig.get("order_date") or ""
                customer = orig.get("customer", "")

                # Allocation for the new item at target event (combined amount)
                new_item_for_alloc = dict(new_values)
                new_item_for_alloc["id"] = new_id
                _create_allocation_for_item(
                    new_item_for_alloc, conn,
                    payment_method="credit_transfer",
                    override_price=combined_amt,
                    create_txn=False,
                )

                # Flat ledger entries (single source of truth — no legacy splits)
                _write_acct_entry(
                    conn,
                    item_id=item_id,
                    event_name=source_event_name,
                    customer=customer,
                    order_id=orig.get("order_id", ""),
                    entry_type="contra",
                    category="transfer_out",
                    source="godaddy",
                    amount=combined_amt,
                    description=f"Credit transfer out: {customer} from {source_event_name} to {target_event_name}",
                    account="TGF Checking",
                    source_ref=f"xfer-flat-{item_id}-out",
                    date=alloc_date,
                )
                _write_acct_entry(
                    conn,
                    item_id=new_id,
                    event_name=target_event_name,
                    customer=customer,
                    entry_type="income",
                    category="transfer_in",
                    source="godaddy",
                    amount=combined_amt,
                    description=f"Credit transfer in: {customer} to {target_event_name} from {source_event_name}",
                    account="TGF Checking",
                    source_ref=f"xfer-flat-{item_id}-in",
                    date=alloc_date,
                )
        except Exception:
            logger.warning("Failed to create accounting entries for transfer %s", item_id, exc_info=True)

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
        if status not in ("credited", "transferred", "wd", "refunded"):
            return False

        if status == "transferred" and item.get("transferred_to_id"):
            transferred_to_id = item["transferred_to_id"]
            # Delete the destination item
            conn.execute("DELETE FROM items WHERE id = ?", (transferred_to_id,))
            # Clean up accounting entries for this transfer
            try:
                conn.execute("DELETE FROM acct_splits WHERE transaction_id IN (SELECT id FROM acct_transactions WHERE source_ref LIKE ?)", (f"xfer-{item_id}-%",))
                conn.execute("DELETE FROM acct_transactions WHERE source_ref LIKE ?", (f"xfer-{item_id}-%",))
                conn.execute("DELETE FROM acct_allocations WHERE order_id = ?", (f"XFER-{transferred_to_id}",))
            except Exception:
                logger.warning("Failed to clean up accounting for reversed transfer %s", item_id, exc_info=True)
            # Mark flat entries as reversed
            try:
                conn.execute(
                    "UPDATE acct_transactions SET status = 'reversed' WHERE source_ref LIKE ? AND COALESCE(status, 'active') = 'active'",
                    (f"xfer-flat-{item_id}-%",),
                )
            except Exception:
                logger.warning("Failed to reverse flat transfer entries for %s", item_id, exc_info=True)

        if status == "refunded":
            # Clean up refund accounting entries
            try:
                conn.execute("DELETE FROM acct_splits WHERE transaction_id IN (SELECT id FROM acct_transactions WHERE source_ref = ?)", (f"refund-{item_id}",))
                conn.execute("DELETE FROM acct_transactions WHERE source_ref = ?", (f"refund-{item_id}",))
            except Exception:
                logger.warning("Failed to clean up accounting for reversed refund %s", item_id, exc_info=True)
            # Mark flat entry as reversed
            try:
                conn.execute(
                    "UPDATE acct_transactions SET status = 'reversed' WHERE source_ref = ? AND COALESCE(status, 'active') = 'active'",
                    (f"refund-flat-{item_id}",),
                )
            except Exception:
                logger.warning("Failed to reverse flat refund entry for %s", item_id, exc_info=True)

        if status == "wd":
            # Mark WD credit liability entry as reversed
            try:
                conn.execute(
                    "UPDATE acct_transactions SET status = 'reversed' WHERE source_ref = ? AND COALESCE(status, 'active') = 'active'",
                    (f"wd-credit-{item_id}",),
                )
            except Exception:
                logger.warning("Failed to reverse WD credit entry for %s", item_id, exc_info=True)

        # Reset original
        conn.execute(
            """UPDATE items
               SET transaction_status = 'active', credit_note = NULL,
                   transferred_to_id = NULL,
                   wd_reason = NULL, wd_note = NULL, wd_credits = NULL, credit_amount = NULL
               WHERE id = ?""",
            (item_id,),
        )
        # Also reverse any child payment items
        conn.execute(
            """UPDATE items
               SET transaction_status = 'active', credit_note = NULL,
                   wd_reason = NULL, wd_note = NULL, wd_credits = NULL, credit_amount = NULL
               WHERE parent_item_id = ?""",
            (item_id,),
        )
        conn.commit()
        return True


def _detect_refund_method(item: dict) -> str:
    """Auto-detect the appropriate refund method from the item's merchant field."""
    merchant = (item.get("merchant") or "").lower()
    if merchant == "the golf fellowship":
        return "GoDaddy"
    if "venmo" in merchant:
        return "Venmo"
    if "zelle" in merchant:
        return "Zelle"
    return ""


def set_event_status(event_id: int, status: str, reason: str = "",
                     rescheduled_to_id: int | None = None,
                     db_path: str | Path | None = None) -> bool:
    """Set an event's status to 'cancelled', 'postponed', or 'active'."""
    if status not in ("active", "cancelled", "postponed"):
        return False
    with _connect(db_path) as conn:
        row = conn.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not row:
            return False
        import datetime as _dt
        conn.execute(
            """UPDATE events
               SET status = ?, status_reason = ?, rescheduled_to_event_id = ?,
                   status_changed_at = ?
               WHERE id = ?""",
            (status, reason or None, rescheduled_to_id,
             _dt.datetime.utcnow().isoformat(), event_id),
        )
        conn.commit()
        return True


def can_restore_event(event_id: int, db_path: str | Path | None = None) -> bool:
    """Return True if no player action (credit/refund/wd) has been taken yet for this event."""
    with _connect(db_path) as conn:
        event = conn.execute("SELECT item_name FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            return False
        event_name = event["item_name"]
        # Check for any items with non-active status that were changed (excluding rsvp_only/gg_rsvp)
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM items
               WHERE item_name = ? COLLATE NOCASE
               AND transaction_status IN ('credited', 'refunded', 'transferred', 'wd')""",
            (event_name,),
        ).fetchone()
        return row["cnt"] == 0


def get_cancellation_players(event_id: int, db_path: str | Path | None = None) -> dict:
    """Return players split into 'paid' (need action) and 'silent' (auto-remove) groups."""
    SILENT_MERCHANTS = (
        "Manual Entry", "RSVP Only", "Roster Import",
        "Customer Entry", "RSVP Import", "RSVP Email Link",
    )
    SILENT_STATUSES = ("rsvp_only", "gg_rsvp")
    with _connect(db_path) as conn:
        event = conn.execute("SELECT item_name FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            return {"paid": [], "silent": []}
        event_name = event["item_name"]
        rows = conn.execute(
            """SELECT i.* FROM items i
               WHERE i.item_name = ? COLLATE NOCASE
               AND i.parent_item_id IS NULL
               AND COALESCE(i.transaction_status, 'active') = 'active'
               ORDER BY i.customer""",
            (event_name,),
        ).fetchall()

        paid = []
        silent = []
        for r in rows:
            d = dict(r)
            merchant = d.get("merchant") or ""
            status = d.get("transaction_status") or "active"
            is_silent_merchant = any(merchant == m or merchant.startswith(f"Paid Separately (Cash") for m in SILENT_MERCHANTS)
            # Check if truly a comp (price is $0 or $0.00 (comp))
            price_str = (d.get("item_price") or "").strip().lower()
            is_zero_price = price_str in ("$0.00", "$0.00 (comp)", "$0", "0", "")
            is_rsvp = status in SILENT_STATUSES or merchant == "RSVP Only"

            if is_rsvp or (is_silent_merchant and is_zero_price):
                silent.append(d)
            else:
                d["auto_refund_method"] = _detect_refund_method(d)
                paid.append(d)

        return {"paid": paid, "silent": silent}


def create_event(item_name: str, event_date: str = None, course: str = None,
                 chapter: str = None, format: str = None, start_type: str = None,
                 start_time: str = None, tee_time_count: int = None,
                 tee_time_interval: int = None, start_time_18: str = None,
                 start_type_18: str = None, tee_time_count_18: int = None,
                 tee_direction: str = None, tee_direction_18: str = None,
                 course_cost: float = None, tgf_markup: float = None,
                 side_game_fee: float = None, transaction_fee_pct: float = None,
                 course_cost_9: float = None, course_cost_18: float = None,
                 tgf_markup_9: float = None, tgf_markup_18: float = None,
                 side_game_fee_9: float = None, side_game_fee_18: float = None,
                 tgf_markup_final: float = None, tgf_markup_final_9: float = None,
                 tgf_markup_final_18: float = None, course_surcharge: float = 0,
                 course_cost_breakdown: str = None,
                 course_cost_breakdown_9: str = None,
                 course_cost_breakdown_18: str = None,
                 per_game_addon: float = None,
                 db_path: str | Path | None = None) -> dict | None:
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
                "INSERT INTO events (item_name, event_date, course, chapter, format, start_type, start_time, tee_time_count, tee_time_interval, start_time_18, start_type_18, tee_time_count_18, tee_direction, tee_direction_18, course_cost, tgf_markup, side_game_fee, transaction_fee_pct, course_cost_9, course_cost_18, tgf_markup_9, tgf_markup_18, side_game_fee_9, side_game_fee_18, tgf_markup_final, tgf_markup_final_9, tgf_markup_final_18, course_surcharge, course_cost_breakdown, course_cost_breakdown_9, course_cost_breakdown_18, per_game_addon, event_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'event')",
                (item_name, event_date, course, chapter, format, start_type, start_time, tee_time_count, tee_time_interval, start_time_18, start_type_18, tee_time_count_18, tee_direction, tee_direction_18, course_cost, tgf_markup, side_game_fee, transaction_fee_pct, course_cost_9, course_cost_18, tgf_markup_9, tgf_markup_18, side_game_fee_9, side_game_fee_18, tgf_markup_final, tgf_markup_final_9, tgf_markup_final_18, course_surcharge, course_cost_breakdown, course_cost_breakdown_9, course_cost_breakdown_18, per_game_addon),
            )
            conn.commit()
            new_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM events WHERE id = ?", (new_id,)).fetchone()
            return dict(row) if row else None
        except sqlite3.IntegrityError:
            return None


def seed_events(events: list[dict], db_path: str | Path | None = None) -> dict:
    """
    Batch-insert events. Each dict should have: item_name, event_date, course, chapter.
    Skips duplicates (case-insensitive) and aliased names. Returns {"inserted": N, "skipped": N}.
    """
    with _connect(db_path) as conn:
        # Load aliases so we skip names that were merged into another event
        alias_set = set()
        try:
            for r in conn.execute("SELECT alias_name FROM event_aliases").fetchall():
                alias_set.add(r[0].lower())
        except Exception:
            pass  # table may not exist on first run
        inserted = 0
        skipped = 0
        for ev in events:
            name = ev["item_name"]
            # Skip if this name is an alias for another event (e.g. merged)
            if name.lower() in alias_set:
                skipped += 1
                continue
            # Case-insensitive duplicate check
            existing = conn.execute(
                "SELECT id FROM events WHERE LOWER(item_name) = LOWER(?)",
                (name,)
            ).fetchone()
            if existing:
                skipped += 1
                logger.debug("Duplicate event skipped during seed: %s", name)
                continue
            try:
                conn.execute(
                    "INSERT INTO events (item_name, event_date, course, chapter, event_type) VALUES (?, ?, ?, ?, 'event')",
                    (ev["item_name"], ev.get("event_date"), ev.get("course"), ev.get("chapter")),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1
                logger.debug("Duplicate event skipped during seed: %s", ev.get("item_name"))
        conn.commit()
        return {"inserted": inserted, "skipped": skipped}


def add_player_to_event(event_name: str, customer: str, mode: str = "comp",
                        side_games: str = "", tee_choice: str = "",
                        handicap: str = "", user_status: str = "",
                        payment_amount: str = "", payment_source: str = "",
                        customer_email: str = "", customer_phone: str = "",
                        holes: str = "", order_date: str = "",
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

        # Look up the event for date/course/chapter
        event = conn.execute(
            "SELECT * FROM events WHERE item_name = ? COLLATE NOCASE", (event_name,)
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
        # Use client-provided local date if available, otherwise server UTC
        new_values["order_date"] = order_date if order_date else datetime.now().strftime("%Y-%m-%d")
        new_values["course"] = event.get("course") or ""
        new_values["chapter"] = event.get("chapter") or ""
        new_values["transaction_status"] = "active"

        if mode == "comp":
            new_values["merchant"] = "Manual Entry"
            new_values["item_price"] = "$0.00 (comp)"
            new_values["holes"] = holes or None
            new_values["side_games"] = side_games or None
            new_values["tee_choice"] = tee_choice or None
            new_values["handicap"] = handicap or None
            new_values["user_status"] = user_status or None
        elif mode == "rsvp":
            new_values["merchant"] = "RSVP Only"
            new_values["item_price"] = None
            new_values["transaction_status"] = "rsvp_only"
        elif mode == "paid_separately":
            source_label = payment_source or "External"
            new_values["merchant"] = f"Paid Separately ({source_label})"
            new_values["item_price"] = payment_amount or "$0.00"
            new_values["holes"] = holes or None
            new_values["side_games"] = side_games or None
            new_values["tee_choice"] = tee_choice or None
            new_values["handicap"] = handicap or None
            new_values["user_status"] = user_status or None
        else:
            new_values["merchant"] = "Manual Entry"
            new_values["item_price"] = "$0.00"

        # Resolve or create customer_id from customers table
        new_values["customer_id"] = _resolve_or_create_customer(
            conn, customer, customer_email,
            phone=customer_phone, chapter=new_values.get("chapter"),
            user_status=user_status,
            item_name=event_name,
        )

        cols = ", ".join(ITEM_COLUMNS)
        placeholders = ", ".join(["?"] * len(ITEM_COLUMNS))
        cursor = conn.execute(
            f"INSERT INTO items ({cols}) VALUES ({placeholders})",
            tuple(new_values.get(c) for c in ITEM_COLUMNS),
        )
        new_id = cursor.lastrowid

        # ── Unified Financial Model: create allocation for external payments ──
        if mode == "paid_separately":
            try:
                item_for_alloc = dict(new_values)
                item_for_alloc["id"] = new_id
                pay_method = (payment_source or "external").lower().replace(" ", "_")
                if pay_method not in ("venmo", "cash", "zelle", "check"):
                    pay_method = "cash"  # default for unknown external sources
                _create_allocation_for_item(
                    item_for_alloc, conn,
                    payment_method=pay_method,
                    create_txn=True,
                    txn_description=f"External payment ({payment_source}): {customer} — {event_name}",
                    txn_source="external_payment",
                    txn_category_name="External Payment",
                )
            except Exception:
                logger.warning("Failed to create allocation for external payment item %d", new_id, exc_info=True)

        # ── Accounting: flat acct_transactions entries ──
        try:
            alloc_date = new_values.get("order_date") or ""
            if mode == "comp":
                _write_acct_entry(
                    conn,
                    item_id=new_id,
                    event_name=event_name,
                    customer=customer,
                    entry_type="expense",
                    category="comp",
                    source="manual",
                    amount=0,
                    description=f"Comp — course fee absorbed by TGF: {customer} — {event_name}",
                    account="TGF Checking",
                    source_ref=f"comp-{new_id}",
                    date=alloc_date,
                )
            elif mode == "paid_separately":
                pay_amount = _parse_dollar(payment_amount)
                pay_method = (payment_source or "external").lower().replace(" ", "_")
                if pay_method not in ("venmo", "cash", "zelle", "check"):
                    pay_method = "cash"
                acct = "Venmo" if pay_method == "venmo" else "TGF Checking"
                _write_acct_entry(
                    conn,
                    item_id=new_id,
                    event_name=event_name,
                    customer=customer,
                    entry_type="income",
                    category="addon",
                    source=pay_method,
                    amount=pay_amount,
                    description=f"External payment ({payment_source}): {customer} — {event_name}",
                    account=acct,
                    source_ref=f"ext-pay-{new_id}",
                    date=alloc_date,
                )
        except Exception:
            logger.warning("Failed to create acct_transactions entry for player %d", new_id, exc_info=True)

        conn.commit()

        new_values["id"] = new_id
        logger.info("Added player %s to event %s (mode=%s, id=%d)",
                    customer, event_name, mode, new_id)
        return new_values


def add_payment_to_event(event_name: str, customer: str,
                         payment_item: str = "", payment_amount: str = "",
                         payment_source: str = "", note: str = "",
                         order_date: str = "",
                         db_path: str | Path | None = None) -> dict | None:
    """Add a child payment record linked to an existing player's registration.

    Creates a new item row with parent_item_id pointing to the player's main
    registration. Child payments only carry payment-related fields (games,
    price, order_date) — not holes, tee, status. They are excluded from
    player counts and shown as indented sub-rows under the parent.
    """
    import time as _time

    with _connect(db_path) as conn:
        event = conn.execute(
            "SELECT * FROM events WHERE item_name = ? COLLATE NOCASE", (event_name,)
        ).fetchone()
        event = dict(event) if event else {}

        # Find the parent item (the player's main registration)
        # Also check event aliases — items may be stored under an old event name
        alias_names = [
            r[0] for r in conn.execute(
                "SELECT alias_name FROM event_aliases WHERE canonical_event_name = ? COLLATE NOCASE",
                (event_name,),
            ).fetchall()
        ]
        all_names = [event_name] + alias_names
        placeholders_names = ",".join(["?"] * len(all_names))
        parent = conn.execute(
            f"""SELECT id, customer_email, customer_phone
               FROM items WHERE item_name COLLATE NOCASE IN ({placeholders_names})
               AND customer = ? COLLATE NOCASE
               AND COALESCE(transaction_status, 'active') = 'active'
               AND parent_item_id IS NULL
               ORDER BY id DESC LIMIT 1""",
            all_names + [customer],
        ).fetchone()
        if not parent:
            return None
        parent = dict(parent)
        parent_id = parent["id"]

        uid = f"manual-payment-{int(_time.time() * 1000)}"

        # Snapshot parent's mutable fields BEFORE any modifications
        parent_full = conn.execute("SELECT * FROM items WHERE id = ?", (parent_id,)).fetchone()
        parent_snap = {}
        if parent_full:
            pf = dict(parent_full)
            for fld in ("side_games", "holes", "tee_choice", "user_status"):
                if pf.get(fld) is not None:
                    parent_snap[fld] = pf[fld]

        # Determine side_games from payment_item
        side_games = ""
        is_upgrade = "upgrade" in (payment_item or "").lower()
        if not is_upgrade:
            if "net" in (payment_item or "").lower():
                side_games = "NET"
            elif "gross" in (payment_item or "").lower():
                side_games = "GROSS"
            elif "both" in (payment_item or "").lower():
                side_games = "BOTH"

        # Handle Event Upgrade — update parent's holes from 9 to 18
        if is_upgrade:
            conn.execute("UPDATE items SET holes = '18' WHERE id = ?", (parent_id,))

        new_values = {col: None for col in ITEM_COLUMNS}
        new_values["email_uid"] = uid
        new_values["item_index"] = 0
        new_values["customer"] = customer
        new_values["customer_email"] = parent.get("customer_email")
        new_values["customer_phone"] = parent.get("customer_phone")
        new_values["item_name"] = event_name
        new_values["order_date"] = order_date if order_date else datetime.now().strftime("%Y-%m-%d")
        new_values["course"] = event.get("course") or ""
        new_values["chapter"] = event.get("chapter") or ""
        new_values["transaction_status"] = "active"
        new_values["merchant"] = f"Manual Entry ({payment_source})"
        new_values["item_price"] = payment_amount
        new_values["side_games"] = side_games if side_games else (payment_item if not is_upgrade else "")
        # Child payments do NOT carry holes, tee, status — only the parent has those
        new_values["notes"] = note or f"{payment_item} — {payment_amount} via {payment_source}"
        new_values["parent_item_id"] = parent_id
        new_values["parent_snapshot"] = json.dumps(parent_snap) if parent_snap else None

        # Resolve or create customer_id from customers table
        new_values["customer_id"] = _resolve_or_create_customer(
            conn, customer, parent.get("customer_email"),
            phone=parent.get("customer_phone"),
            chapter=new_values.get("chapter"),
            item_name=event_name,
        )

        cols = ", ".join(ITEM_COLUMNS)
        placeholders = ", ".join(["?"] * len(ITEM_COLUMNS))
        cursor = conn.execute(
            f"INSERT INTO items ({cols}) VALUES ({placeholders})",
            tuple(new_values.get(c) for c in ITEM_COLUMNS),
        )
        new_id = cursor.lastrowid

        # ── Unified Financial Model: create allocation for add-on payment ──
        try:
            pay_amount = _parse_dollar(payment_amount)
            if pay_amount > 0:
                item_for_alloc = dict(new_values)
                item_for_alloc["id"] = new_id
                pay_method = (payment_source or "external").lower().replace(" ", "_")
                if pay_method not in ("venmo", "cash", "zelle", "check", "godaddy"):
                    pay_method = "cash"
                _create_allocation_for_item(
                    item_for_alloc, conn,
                    payment_method=pay_method,
                    create_txn=True,
                    txn_description=f"Add-on payment ({payment_item}): {customer} — {event_name}",
                    txn_source="add_payment",
                    txn_category_name="External Payment" if pay_method != "godaddy" else "Event Revenue",
                )
        except Exception:
            logger.warning("Failed to create allocation for add-payment item %d", new_id, exc_info=True)

        # ── Accounting: flat acct_transactions entry for add-on ──
        try:
            pay_amount = _parse_dollar(payment_amount)
            if pay_amount > 0:
                pay_method = (payment_source or "external").lower().replace(" ", "_")
                if pay_method not in ("venmo", "cash", "zelle", "check", "godaddy"):
                    pay_method = "cash"
                acct = "Venmo" if pay_method == "venmo" else "TGF Checking"
                alloc_date = new_values.get("order_date") or ""
                _write_acct_entry(
                    conn,
                    item_id=new_id,
                    event_name=event_name,
                    customer=customer,
                    entry_type="income",
                    category="addon",
                    source=pay_method,
                    amount=pay_amount,
                    description=f"Add-on payment ({payment_item}): {customer} — {event_name}",
                    account=acct,
                    source_ref=f"addon-{new_id}",
                    date=alloc_date,
                )
        except Exception:
            logger.warning("Failed to create acct_transactions entry for add-payment %d", new_id, exc_info=True)

        conn.commit()

        new_values["id"] = new_id
        logger.info("Added payment %s for %s at %s (id=%d)",
                     payment_item, customer, event_name, new_id)
        return new_values


def upgrade_rsvp_to_paid(item_id: int, payment_amount: str = "",
                         payment_source: str = "", side_games: str = "",
                         tee_choice: str = "", handicap: str = "",
                         user_status: str = "",
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
                user_status = ?,
                transaction_status = 'active'
            WHERE id = ?""",
            (
                f"Paid Separately ({source_label})",
                payment_amount or "$0.00",
                side_games or None,
                tee_choice or None,
                handicap or None,
                user_status or None,
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
    If the item is a child payment (+PAY/-PAY), reverts parent state changes.
    Returns True if the row was deleted, False if not found or not allowed.
    """
    with _connect(db_path) as conn:
        item = conn.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
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

        # If this is a child payment, revert parent to snapshot state
        parent_id = row.get("parent_item_id")
        if parent_id:
            snapshot_json = row.get("parent_snapshot")
            if snapshot_json:
                try:
                    snapshot = json.loads(snapshot_json)
                    if snapshot:
                        set_parts = []
                        vals = []
                        for fld, val in snapshot.items():
                            if fld in ITEM_COLUMNS:
                                set_parts.append(f"{fld} = ?")
                                vals.append(val)
                        if set_parts:
                            vals.append(parent_id)
                            conn.execute(
                                f"UPDATE items SET {', '.join(set_parts)} WHERE id = ?",
                                vals,
                            )
                            logger.info("Reverted parent %d from snapshot: %s", parent_id, snapshot)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Invalid parent_snapshot JSON on item %d", item_id)

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
         the chapter from the identifier matches the event's chapter
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

        # Strip trailing golf-course qualifiers (e.g. "TERAVISTA front" → "TERAVISTA")
        _COURSE_SUFFIXES = {"front", "back", "nine", "side", "course"}
        cp_words = course_part.split()
        if len(cp_words) > 1 and cp_words[-1].lower() in _COURSE_SUFFIXES:
            course_part = " ".join(cp_words[:-1])

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
                     AND item_name COLLATE NOCASE IN ({placeholders})
                     AND COALESCE(transaction_status, 'active') = 'active'""",
                [player_email] + name_list,
            ).fetchone()
            if row:
                return row["id"]

        # Strategy 1b: Match via customer_aliases email lookup
        # If the RSVP email matches a customer alias email, find that customer's items
        if player_email:
            alias_customer = conn.execute(
                """SELECT ca.customer_name FROM customer_aliases ca
                   WHERE ca.alias_type = 'email'
                     AND LOWER(ca.alias_value) = LOWER(?)""",
                (player_email,),
            ).fetchone()
            if alias_customer:
                row = conn.execute(
                    f"""SELECT id FROM items
                       WHERE customer = ?
                         AND item_name COLLATE NOCASE IN ({placeholders})
                         AND COALESCE(transaction_status, 'active') = 'active'""",
                    [alias_customer["customer_name"]] + name_list,
                ).fetchone()
                if row:
                    return row["id"]

        # Strategy 2: First name match (loose — only if exactly one match)
        # Guard: only use first-name matching when there's no ambiguity.
        # If there are multiple items with names starting with the same first name,
        # do NOT match (e.g. "Daniel" could be "Daniel South" or "Daniel Miller").
        if player_name:
            rows = conn.execute(
                f"""SELECT id, customer FROM items
                   WHERE customer LIKE ?
                     AND item_name COLLATE NOCASE IN ({placeholders})
                     AND COALESCE(transaction_status, 'active') = 'active'""",
                [f"{player_name}%"] + name_list,
            ).fetchall()
            if len(rows) == 1:
                return rows[0]["id"]

        return None


# ---------------------------------------------------------------------------
# Credit detection helpers
# ---------------------------------------------------------------------------

_PER_GAME_ADDON = 16.0  # $ per game (NET or GROSS) — 9 Holes and 9/18 Combo
_PER_GAME_ADDON_18 = 30.0  # $ per game for standalone 18 Hole events
_PER_GAME_ADDON_27 = 27.0  # default $ per game for 27 Hole events (overridable per-event via events.per_game_addon)


def get_player_credits(
    customer_name: str,
    db_path: str | Path | None = None,
    customer_id: int | None = None,
    player_email: str | None = None,
) -> list[dict]:
    """Return all unredeemed credited items for a player, most recent first.

    Includes both parent items and child add-on items (e.g. game add-ons that
    were credited when an event was cancelled via credit_item cascade).

    Lookup priority:
    1. customer_id → items.customer_id
    2. Name fallback → items.customer COLLATE NOCASE
    3. Email fallback via customer_emails → resolve customer_id → retry #1
    """
    _CREDIT_SQL = """SELECT i.*, e.item_name as event_canonical
                     FROM items i
                     LEFT JOIN events e ON e.item_name = i.item_name COLLATE NOCASE
                     WHERE {where}
                       AND i.transaction_status = 'credited'
                     ORDER BY i.order_date DESC"""

    with _connect(db_path) as conn:
        rows = []
        if customer_id:
            rows = conn.execute(
                _CREDIT_SQL.format(where="i.customer_id = ?"),
                (customer_id,),
            ).fetchall()

        if not rows:
            # Name lookup (case-insensitive)
            rows = conn.execute(
                _CREDIT_SQL.format(where="i.customer = ? COLLATE NOCASE"),
                (customer_name,),
            ).fetchall()

        # If still empty and we have an email, try resolving via customer_emails table
        if not rows and player_email:
            email_lc = player_email.strip().lower()
            ce_row = conn.execute(
                "SELECT customer_id FROM customer_emails WHERE LOWER(email) = ? LIMIT 1",
                (email_lc,),
            ).fetchone()
            if ce_row and ce_row["customer_id"]:
                rows = conn.execute(
                    _CREDIT_SQL.format(where="i.customer_id = ?"),
                    (ce_row["customer_id"],),
                ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["credit_amount"] = _parse_dollar(d.get("item_price")) + _parse_dollar(d.get("transaction_fees") or "0")
        result.append(d)
    return result


def _calc_event_pricing_breakdown(
    event: dict,
    user_status: str,
    holes: str,
    side_games: str,
) -> dict | None:
    """Server-side pricing breakdown matching the JS calcPricingLine in events.html.

    Returns a dict with:
        subtotal:     ceil(course_cost) + markup + side_game_fee + game_addon
                      (the whole-dollar charge BEFORE the transaction fee)
        tx_fee:       transaction fee on subtotal (typically 3.5%)
        total:        subtotal + tx_fee (full player-facing price)

    Returns None if the event has no pricing configured.
    """
    import math

    # Normalise inputs
    holes_str = str(holes or "").strip()
    status_upper = (user_status or "").upper()
    games_upper = (side_games or "").upper()
    fmt_raw = event.get("format") or ""
    fmt = fmt_raw.lower()
    is_combo = "combo" in fmt or "9/18" in fmt
    is_27 = fmt_raw.strip() == "27 Holes"

    # Pick course cost / markup / side-game-fee based on holes
    if is_combo and holes_str == "18":
        cc = event.get("course_cost_18")
        mu_member = event.get("tgf_markup_18") or event.get("tgf_markup")
        sg = event.get("side_game_fee_18") or event.get("side_game_fee")
    elif is_combo or holes_str == "9":
        cc = event.get("course_cost_9") or event.get("course_cost")
        mu_member = event.get("tgf_markup_9") or event.get("tgf_markup")
        sg = event.get("side_game_fee_9") or event.get("side_game_fee")
    else:
        cc = event.get("course_cost")
        mu_member = event.get("tgf_markup")
        sg = event.get("side_game_fee")

    if cc is None or mu_member is None:
        return None

    cc = float(cc or 0)
    mu_member = float(mu_member or 0)
    sg = float(sg or 0)
    tf = float(event.get("transaction_fee_pct") or 3.5)

    # Player-type markup adjustment.
    # 27 Holes: guest +$25, no 1st Timer tier (1st Timer falls back to guest pricing).
    if is_27:
        guest_extra = 25.0
    elif holes_str == "18" and not is_combo:
        guest_extra = 15.0
    else:
        guest_extra = 10.0

    if "GUEST" in status_upper:
        mu = mu_member + guest_extra
    elif "1ST" in status_upper or "FIRST" in status_upper:
        # 27 Holes does not offer 1st Timer pricing — charge as guest
        mu = mu_member + guest_extra if is_27 else (mu_member + guest_extra - 25.0)
    else:
        mu = mu_member

    # Game addon. 27 Holes uses the per-event override (events.per_game_addon),
    # falling back to $27. 18 Holes standalone = $30, everything else = $16.
    if is_27:
        per_game_override = event.get("per_game_addon")
        if per_game_override is not None and per_game_override != "":
            try:
                per_game = float(per_game_override)
            except (TypeError, ValueError):
                per_game = _PER_GAME_ADDON_27
        else:
            per_game = _PER_GAME_ADDON_27
    elif holes_str == "18" and not is_combo:
        per_game = _PER_GAME_ADDON_18
    else:
        per_game = _PER_GAME_ADDON
    if games_upper in ("BOTH",):
        game_addon = per_game * 2
    elif games_upper in ("NET", "GROSS"):
        game_addon = per_game
    else:
        game_addon = 0.0

    rounded_cc = math.ceil(cc)
    event_charge = rounded_cc + mu + sg + game_addon
    subtotal = float(math.ceil(event_charge))
    tx_fee = round(subtotal * tf / 100, 2)
    return {
        "subtotal": subtotal,
        "tx_fee": tx_fee,
        "total": round(subtotal + tx_fee, 2),
    }


def _calc_event_price_for_player(
    event: dict,
    user_status: str,
    holes: str,
    side_games: str,
) -> float | None:
    """Returns the full player-facing total (including tx fee), or None if the event
    has no pricing configured. Thin wrapper around _calc_event_pricing_breakdown.
    """
    breakdown = _calc_event_pricing_breakdown(event, user_status, holes, side_games)
    return breakdown["total"] if breakdown else None


def get_rsvp_credit_info(rsvp_id: int, db_path: str | Path | None = None) -> dict | None:
    """Full credit analysis for a single RSVP row.

    Returns None if the RSVP isn't matched to an event, or the player has no credits.
    Returns a dict with:
        player_name, player_email, event_name, credits (list), total_credit,
        new_event_price (or None), amount_owed (positive = owes, negative = excess),
        can_calculate, selections (holes/games/tee/status from most recent credit)
    """
    with _connect(db_path) as conn:
        rsvp = conn.execute("SELECT * FROM rsvps WHERE id = ?", (rsvp_id,)).fetchone()
        if not rsvp:
            return None
        rsvp = dict(rsvp)

        if not rsvp.get("matched_event"):
            return None

        # Resolve player name from matched item or RSVP row itself
        customer_name = rsvp.get("player_name") or ""
        if rsvp.get("matched_item_id"):
            item_row = conn.execute(
                "SELECT customer, customer_email FROM items WHERE id = ?",
                (rsvp["matched_item_id"],),
            ).fetchone()
            if item_row:
                customer_name = item_row["customer"] or customer_name

        credits = get_player_credits(customer_name, db_path)
        if not credits:
            return None

        total_credit = sum(c["credit_amount"] for c in credits)

        # Previous selections from the most recent credited item
        most_recent = credits[0]
        selections = {
            "user_status": most_recent.get("user_status") or "MEMBER",
            "holes":       most_recent.get("holes") or "9",
            "side_games":  most_recent.get("side_games") or "NONE",
            "tee_choice":  most_recent.get("tee_choice") or "",
        }

        # New event pricing
        event_row = conn.execute(
            "SELECT * FROM events WHERE item_name = ? COLLATE NOCASE",
            (rsvp["matched_event"],),
        ).fetchone()
        event = dict(event_row) if event_row else {}

        breakdown = _calc_event_pricing_breakdown(
            event,
            selections["user_status"],
            selections["holes"],
            selections["side_games"],
        )
        can_calculate = breakdown is not None
        new_event_price = breakdown["total"] if breakdown else None
        new_event_subtotal = breakdown["subtotal"] if breakdown else None

        # Balance due is computed against the pre-tx-fee subtotal — the difference
        # will be paid via Venmo (no merchant fee), so charging tx fee on it is unnecessary.
        amount_owed = round((new_event_subtotal or 0) - total_credit, 2)

        return {
            "rsvp_id": rsvp_id,
            "player_name": customer_name,
            "player_email": rsvp.get("player_email") or "",
            "event_name": rsvp["matched_event"],
            "event_date": event.get("event_date") or "",
            "course": event.get("course") or "",
            "credits": [
                {
                    "item_id": c["id"],
                    "event_name": c["item_name"],
                    "credit_amount": c["credit_amount"],
                    "user_status": c.get("user_status") or "",
                    "holes": c.get("holes") or "",
                    "side_games": c.get("side_games") or "",
                    "tee_choice": c.get("tee_choice") or "",
                }
                for c in credits
            ],
            "total_credit": total_credit,
            "new_event_price": new_event_price,
            "new_event_subtotal": new_event_subtotal,
            "amount_owed": amount_owed,
            "can_calculate": can_calculate,
            "selections": selections,
        }


def get_event_rsvp_credit_map(event_name: str, db_path: str | Path | None = None) -> dict:
    """Return {customer_name: credit_info} for all RSVP-only players in an event.

    Covers both items-table RSVPs (rsvp_only / gg_rsvp) and unmatched GG RSVPs
    from the rsvps table (synthetic rows on the frontend).
    """
    with _connect(db_path) as conn:
        rsvp_items = conn.execute(
            """SELECT i.id, i.customer, i.customer_id,
                      r.player_email AS gg_email
               FROM items i
               LEFT JOIN rsvps r ON r.matched_item_id = i.id
               WHERE i.item_name = ? COLLATE NOCASE
                 AND COALESCE(i.transaction_status, 'active') IN ('rsvp_only', 'gg_rsvp')
                 AND i.parent_item_id IS NULL""",
            (event_name,),
        ).fetchall()

        # GG RSVPs not matched to an active item (these become synthetic JS rows)
        rsvp_rows = conn.execute(
            """SELECT r.id, r.player_name, r.player_email
               FROM rsvps r
               WHERE r.matched_event = ? COLLATE NOCASE
                 AND r.response = 'PLAYING'
                 AND (r.matched_item_id IS NULL
                      OR NOT EXISTS (
                          SELECT 1 FROM items i
                          WHERE i.id = r.matched_item_id
                            AND COALESCE(i.transaction_status, 'active') = 'active'
                      ))""",
            (event_name,),
        ).fetchall()

        # Build email → canonical customer name lookup for rsvp rows
        email_to_customer = {}
        email_to_customer_id: dict[str, int] = {}
        email_to_canonical_name: dict[str, str] = {}
        for rr in rsvp_rows:
            email = (rr["player_email"] or "").strip().lower()
            if email and email not in email_to_customer:
                card = conn.execute(
                    """SELECT customer FROM items
                       WHERE LOWER(customer_email) = ?
                         AND customer IS NOT NULL AND customer != ''
                       ORDER BY order_date DESC LIMIT 1""",
                    (email,),
                ).fetchone()
                if card:
                    email_to_customer[email] = card["customer"]
            # Also look up customer_id via customer_emails table for robust credit matching
            if email and email not in email_to_customer_id:
                ce_row = conn.execute(
                    """SELECT ce.customer_id,
                              TRIM(c.first_name || ' ' || c.last_name) AS full_name
                       FROM customer_emails ce
                       JOIN customers c ON c.customer_id = ce.customer_id
                       WHERE LOWER(ce.email) = ?
                       LIMIT 1""",
                    (email,),
                ).fetchone()
                if ce_row:
                    email_to_customer_id[email] = ce_row["customer_id"]
                    cname = (ce_row["full_name"] or "").strip()
                    if cname:
                        email_to_canonical_name[email] = cname

    result = {}

    # Item-based RSVPs (rsvp_only / gg_rsvp items in the items table)
    for row in rsvp_items:
        customer = row["customer"]
        if not customer:
            continue
        cust_id = row["customer_id"] if row["customer_id"] else None
        gg_email = (row["gg_email"] or "").strip().lower() or None
        credits = get_player_credits(customer, db_path, customer_id=cust_id, player_email=gg_email)
        if credits:
            result[customer] = {
                "total_credit": sum(c["credit_amount"] for c in credits),
                "credits": [
                    {"item_id": c["id"], "event_name": c["item_name"],
                     "credit_amount": c["credit_amount"]}
                    for c in credits
                ],
                "item_id": row["id"],
                "rsvp_id": None,
            }

    # GG RSVPs from rsvps table (synthetic frontend rows)
    for rr in rsvp_rows:
        email = (rr["player_email"] or "").strip().lower()
        # Prefer name from GoDaddy items (matches frontend resolved_name), then customers
        # table, then raw GG player name as last resort
        customer = (
            email_to_customer.get(email)
            or email_to_canonical_name.get(email)
            or rr["player_name"]
            or ""
        )
        cust_id = email_to_customer_id.get(email) if email else None
        if not customer or customer in result:
            continue
        credits = get_player_credits(
            customer, db_path, customer_id=cust_id, player_email=email or None
        )
        if credits:
            result[customer] = {
                "total_credit": sum(c["credit_amount"] for c in credits),
                "credits": [
                    {"item_id": c["id"], "event_name": c["item_name"],
                     "credit_amount": c["credit_amount"]}
                    for c in credits
                ],
                "item_id": None,
                "rsvp_id": rr["id"],
            }

    return result


def create_rsvp_only_item(
    event_name: str,
    player_name: str,
    player_email: str,
    rsvp_id: int | None = None,
    db_path: str | Path | None = None,
) -> int:
    """Create a rsvp_only items row for a GG RSVP player so credits can be applied.

    Idempotent — returns existing item_id if the row was already created for this rsvp_id.
    """
    import datetime as _dt

    with _connect(db_path) as conn:
        uid = f"manual-gg-rsvp-{rsvp_id}" if rsvp_id else f"manual-gg-rsvp-name-{player_name}"
        existing = conn.execute(
            "SELECT id FROM items WHERE email_uid = ?", (uid,)
        ).fetchone()
        if existing:
            return existing["id"]

        event_row = conn.execute(
            "SELECT chapter FROM events WHERE item_name = ? COLLATE NOCASE",
            (event_name,),
        ).fetchone()
        chapter = event_row["chapter"] if event_row else ""

        conn.execute(
            """INSERT INTO items
               (email_uid, merchant, customer, customer_email, item_name,
                item_price, transaction_status, order_date, chapter)
               VALUES (?, 'Golf Genius RSVP', ?, ?, ?, '', 'rsvp_only', date('now'), ?)""",
            (uid, player_name, player_email or "", event_name, chapter or ""),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]


def reverse_credit_application(item_id: int, db_path: str | Path | None = None) -> dict:
    """Undo a credit application: restore source credits and revert the registration.

    - Finds items that were transferred to item_id and reverts them to 'credited'.
    - Removes the excess credit item if one was created.
    - Marks the transfer accounting entries as reversed.
    - Reverts the target item to 'rsvp_only' (or deletes it if it was a synthetic GG item).
    - Detaches every +PAY child (whether tagged [xfer-consumed:<id>] or attached
      later by auto_match_venmo_inbound_to_balance_due). Any payment-bearing child
      is converted to a standalone 'credited' item so the player keeps the money
      they actually paid.
    """
    import time as _time
    with _connect(db_path) as conn:
        item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            return {"ok": False, "error": "Item not found"}
        item = dict(item)

        if item.get("merchant") != "Paid Separately (Credit Transfer)":
            return {"ok": False, "error": "Not a credit-transfer registration"}

        sources = conn.execute(
            "SELECT * FROM items WHERE transferred_to_id = ? AND transaction_status = 'transferred'",
            (item_id,),
        ).fetchall()
        if not sources:
            return {"ok": False, "error": "No transferred source items found — may already be reversed"}

        for s in sources:
            conn.execute(
                """UPDATE items
                   SET transaction_status = 'credited',
                       credit_note = NULL,
                       transferred_to_id = NULL
                   WHERE id = ?""",
                (s["id"],),
            )
            conn.execute(
                "UPDATE acct_transactions SET status = 'reversed' WHERE source_ref = ?",
                (f"xfer-flat-{s['id']}-out",),
            )

        # ── Handle every +PAY child attached to this parent ──
        # Two distinct paths put rows here:
        #   1. apply_credit_to_rsvp's _consume_unallocated_payments path tags
        #      the child with [xfer-consumed:<id>] (drops the tag, detaches).
        #   2. auto_match_venmo_inbound_to_balance_due creates a fresh +PAY row
        #      with no tag — its underlying Venmo payment is real money in.
        # The fix: detach all of them, and for any row that carries a real
        # item_price, convert it to a standalone 'credited' item so the player
        # keeps the credit on their account.
        consumed_tag = _XFER_CONSUMED_TAG.format(parent_id=item_id)
        children = conn.execute(
            "SELECT * FROM items WHERE parent_item_id = ?",
            (item_id,),
        ).fetchall()
        converted_to_credit = []
        detached_consumed = []
        for cr in children:
            cr = dict(cr)
            notes = cr.get("notes") or ""
            child_status = cr.get("transaction_status") or "active"
            had_consumed_tag = consumed_tag in notes

            if had_consumed_tag:
                cleaned = " ".join(notes.replace(consumed_tag, "").split())
                conn.execute(
                    "UPDATE items SET parent_item_id = NULL, notes = ? WHERE id = ?",
                    (cleaned or None, cr["id"]),
                )
                detached_consumed.append(cr["id"])
                continue

            # Untagged +PAY child — created by Venmo auto-match (or manual entry).
            # Convert to a standalone credited item so the money stays as a credit.
            price_amt = _parse_dollar(cr.get("item_price"))
            if price_amt > 0 and child_status not in ("credited", "refunded"):
                customer_name = cr.get("customer") or item.get("customer", "")
                event_name = cr.get("item_name") or item.get("item_name", "")
                credit_note = (
                    f"Credit from cancelled credit transfer — ${price_amt:.2f} from {event_name}"
                ).strip()
                conn.execute(
                    """UPDATE items
                       SET parent_item_id = NULL,
                           transaction_status = 'credited',
                           credit_note = ?,
                           merchant = COALESCE(NULLIF(merchant, ''), 'Manual Entry')
                       WHERE id = ?""",
                    (credit_note, cr["id"]),
                )
                converted_to_credit.append({"id": cr["id"], "amount": price_amt})
                # Clear matched_item_id on any expense_transaction that pointed
                # here so a future "Match Venmo" run can re-attach it cleanly.
                conn.execute(
                    "UPDATE expense_transactions SET matched_item_id = NULL WHERE matched_item_id = ?",
                    (cr["id"],),
                )
            else:
                # Zero-price or already-credited child — just detach.
                conn.execute(
                    "UPDATE items SET parent_item_id = NULL WHERE id = ?",
                    (cr["id"],),
                )
                detached_consumed.append(cr["id"])

        # Remove excess + overpayment credit items if created
        conn.execute(
            "DELETE FROM items WHERE email_uid LIKE ?",
            (f"credit-excess-{item_id}-%",),
        )
        conn.execute(
            "DELETE FROM items WHERE email_uid LIKE ?",
            (f"overpayment-credit-{item_id}-%",),
        )

        # Reverse transfer_in accounting entry
        conn.execute(
            "UPDATE acct_transactions SET status = 'reversed' WHERE source_ref = ?",
            (f"xfer-flat-{item_id}-in",),
        )

        # Revert or delete target item
        email_uid = item.get("email_uid") or ""
        if email_uid.startswith("manual-gg-rsvp-"):
            conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        else:
            conn.execute(
                """UPDATE items
                   SET transaction_status = 'rsvp_only',
                       merchant = '',
                       item_price = '',
                       holes = '',
                       side_games = '',
                       tee_choice = '',
                       user_status = '',
                       transferred_from_id = NULL,
                       credit_note = NULL
                   WHERE id = ?""",
                (item_id,),
            )

        conn.commit()
        return {
            "ok": True,
            "sources_restored": len(sources),
            "children_converted_to_credit": converted_to_credit,
            "children_detached": detached_consumed,
        }


def mark_rsvp_credit_notified(rsvp_id: int, db_path: str | Path | None = None) -> None:
    """Stamp credit_notified_at on the rsvp row so we don't re-send."""
    import datetime as _dt
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE rsvps SET credit_notified_at = ? WHERE id = ?",
            (_dt.datetime.utcnow().isoformat(), rsvp_id),
        )
        conn.commit()


# Tag appended to a +PAY item's `notes` when its parent_item_id was set by
# Apply Credit / reconcile_orphan_venmo_payments. Lets undo find and detach it.
_XFER_CONSUMED_TAG = "[xfer-consumed:{parent_id}]"


def _sum_existing_child_payments(conn, parent_item_id: int) -> dict:
    """Sum active manual-entry +PAY children already attached to this parent.
    Catches the case where a Venmo / cash payment was entered against the
    credit-transfer parent but the parent's credit_note was never reduced.

    Case-insensitive match on `merchant LIKE 'Manual Entry%'` so we accept
    "Manual Entry", "Manual Entry (venmo)", "Manual Entry (Venmo)",
    "Manual Entry (Cash)", etc.
    """
    rows = conn.execute(
        """SELECT id, item_price
           FROM items
           WHERE parent_item_id = ?
             AND COALESCE(transaction_status, 'active') = 'active'
             AND merchant LIKE 'Manual Entry%' COLLATE NOCASE""",
        (parent_item_id,),
    ).fetchall()
    total = 0.0
    ids: list[int] = []
    for r in rows:
        amt = _parse_dollar(r["item_price"])
        if amt > 0:
            total += amt
            ids.append(r["id"])
    return {"total": round(total, 2), "ids": ids}


def _consume_unallocated_payments_for_credit_transfer(
    conn,
    parent_item_id: int,
    customer: str,
    amount_owed: float,
    max_days_back: int = 14,
    exclude_ids: set | None = None,
) -> dict:
    """Find orphan manual-payment +PAY items for this customer and reparent them
    onto the credit-transfer item, up to (and beyond) amount_owed.

    Greedy: consumes oldest-first until amount_owed is covered. Continues
    consuming any further orphans dated *after* the most recent consumed one
    only if amount_owed > 0; otherwise stops once paid (we don't want to sweep
    unrelated future deposits).

    Returns: {"consumed_total": float, "consumed_ids": list[int], "remaining_owed": float}
    """
    exclude_ids = exclude_ids or set()
    rows = conn.execute(
        """SELECT id, item_price, notes, order_date
           FROM items
           WHERE customer = ? COLLATE NOCASE
             AND parent_item_id IS NULL
             AND COALESCE(transaction_status, 'active') = 'active'
             AND merchant LIKE 'Manual Entry%' COLLATE NOCASE
             AND order_date >= date('now', ?)
           ORDER BY order_date ASC, id ASC""",
        (customer, f"-{int(max_days_back)} days"),
    ).fetchall()

    consumed_total = 0.0
    consumed_ids: list[int] = []
    remaining = max(0.0, float(amount_owed or 0))

    for r in rows:
        rid = r["id"]
        if rid in exclude_ids or rid == parent_item_id:
            continue
        amt = _parse_dollar(r["item_price"])
        if amt <= 0:
            continue
        # Stop once we've covered the owed amount — leaves later deposits
        # untouched so we don't grab unrelated payments.
        if remaining <= 0 and consumed_total >= float(amount_owed or 0):
            break

        tag = _XFER_CONSUMED_TAG.format(parent_id=parent_item_id)
        existing_notes = r["notes"] or ""
        new_notes = (existing_notes + " " + tag).strip() if existing_notes else tag
        conn.execute(
            "UPDATE items SET parent_item_id = ?, notes = ? WHERE id = ?",
            (parent_item_id, new_notes, rid),
        )
        consumed_total += amt
        consumed_ids.append(rid)
        remaining = max(0.0, remaining - amt)

    return {
        "consumed_total": round(consumed_total, 2),
        "consumed_ids": consumed_ids,
        "remaining_owed": round(max(0.0, float(amount_owed or 0) - consumed_total), 2),
    }


def _post_overpayment_credit(
    conn,
    rsvp_item: dict,
    parent_item_id: int,
    overpayment: float,
) -> int | None:
    """Post a new transaction_status='credited' item for an overpayment surplus
    so it shows up in the customer's available credit pool. Returns the new id.
    """
    if overpayment <= 0:
        return None
    import time as _time
    uid = f"overpayment-credit-{parent_item_id}-{int(_time.time() * 1000)}"
    cur = conn.execute(
        """INSERT INTO items
           (email_uid, merchant, customer, customer_email, item_name,
            item_price, transaction_status, credit_note,
            order_date, chapter)
           VALUES (?, 'Manual Entry', ?, ?, ?,
            ?, 'credited', ?,
            date('now'), ?)""",
        (
            uid,
            rsvp_item.get("customer"), rsvp_item.get("customer_email"),
            f"Overpayment credit — {rsvp_item.get('item_name') or ''}".strip(" —"),
            f"${overpayment:.2f}",
            f"Overpayment credit — ${overpayment:.2f} from prior Venmo payment",
            rsvp_item.get("chapter") or "",
        ),
    )
    return cur.lastrowid


def apply_credit_to_rsvp(
    rsvp_item_id: int,
    credited_item_ids: list[int],
    excess_action: str = "keep",
    holes: str = "",
    side_games: str = "",
    tee_choice: str = "",
    user_status: str = "",
    db_path: str | Path | None = None,
) -> dict:
    """Apply player credits to an RSVP-only item, converting it to an active registration.

    - Carries selections (holes, side_games, tee_choice, user_status) onto the item.
    - Marks credited items as 'transferred'.
    - Creates accounting transfer entries.
    - excess_action='keep': leftover credit stays as a new credited item.
    - excess_action='note': just records the excess amount, admin handles manually.
    Returns dict with ok, amount_applied, excess.
    """
    import time as _time
    import datetime as _dt

    with _connect(db_path) as conn:
        # Load the RSVP item
        rsvp_item = conn.execute("SELECT * FROM items WHERE id = ?", (rsvp_item_id,)).fetchone()
        if not rsvp_item:
            return {"ok": False, "error": "RSVP item not found"}
        rsvp_item = dict(rsvp_item)

        # Load the credited items to sum
        credited_items = []
        total_credit = 0.0
        for cid in credited_item_ids:
            row = conn.execute("SELECT * FROM items WHERE id = ?", (cid,)).fetchone()
            if not row:
                continue
            d = dict(row)
            if d.get("transaction_status") != "credited":
                continue
            amt = _parse_dollar(d.get("item_price")) + _parse_dollar(d.get("transaction_fees") or "0")
            total_credit += amt
            credited_items.append(d)

        if not credited_items:
            return {"ok": False, "error": "No valid credited items found"}

        # Determine new event price
        event_row = conn.execute(
            "SELECT * FROM events WHERE item_name = ? COLLATE NOCASE",
            (rsvp_item["item_name"],),
        ).fetchone()
        event = dict(event_row) if event_row else {}

        u_status = user_status or credited_items[0].get("user_status") or "MEMBER"
        # For non-combo events the holes value is fully determined by the event
        # format — must NOT inherit from the credited source item (which can be
        # a 9-hole credit applied at an 18-hole event). Inheriting was producing
        # wrong subtotals (PER_GAME_ADDON $16 vs $30) and writing 9 into the
        # HOLES column on 18-hole registrations.
        _evt_fmt = (event.get("format") or "")
        _is_combo = "combo" in _evt_fmt.lower() or "9/18" in _evt_fmt
        if _evt_fmt == "18 Holes" or _evt_fmt == "27 Holes":
            u_holes = "18"
        elif _evt_fmt == "9 Holes":
            u_holes = "9"
        else:
            # Combo — override > credited source > 9 fallback
            u_holes = holes or credited_items[0].get("holes") or "9"
        u_games = side_games or credited_items[0].get("side_games") or "NONE"
        u_tee = tee_choice or credited_items[0].get("tee_choice") or ""

        breakdown = _calc_event_pricing_breakdown(event, u_status, u_holes, u_games)
        # Compare credit against the pre-tx-fee subtotal: any balance due is paid via
        # Venmo (no merchant fee), so we don't charge tx fee on it.
        new_subtotal = breakdown["subtotal"] if breakdown else None
        applied = min(total_credit, new_subtotal) if new_subtotal else total_credit
        excess = round(total_credit - (new_subtotal or total_credit), 2)

        # Update the RSVP item → active registration
        price_str = f"${applied:.2f} (credit transfer)"
        amount_owed = round((new_subtotal or 0) - applied, 2)

        # Net any prior payments by this customer against the balance due:
        #   1. Existing manual-entry +PAY children already attached to this row.
        #   2. Orphan manual-entry +PAY items dated in the last 14 days.
        existing_children = _sum_existing_child_payments(conn, rsvp_item_id)
        consumed = {"consumed_total": 0.0, "consumed_ids": [], "remaining_owed": amount_owed}
        overpayment_credit_id = None
        already_paid = existing_children["total"]
        if amount_owed > 0 and rsvp_item.get("customer"):
            remainder = max(0.0, round(amount_owed - already_paid, 2))
            if remainder > 0:
                consumed = _consume_unallocated_payments_for_credit_transfer(
                    conn,
                    parent_item_id=rsvp_item_id,
                    customer=rsvp_item["customer"],
                    amount_owed=remainder,
                    max_days_back=14,
                    exclude_ids={rsvp_item_id, *existing_children["ids"],
                                 *(ci["id"] for ci in credited_items)},
                )
        total_paid = round(already_paid + consumed["consumed_total"], 2)
        remaining_after_payments = max(0.0, round(amount_owed - total_paid, 2))
        overpayment = max(0.0, round(total_paid - amount_owed, 2))
        if amount_owed <= 0:
            balance_note = None
        elif remaining_after_payments > 0:
            balance_note = f"balance_due:{remaining_after_payments:.2f}"
        else:
            balance_note = f"paid_at:{_dt.datetime.utcnow().strftime('%Y-%m-%d')}"
            if overpayment > 0:
                overpayment_credit_id = _post_overpayment_credit(
                    conn, rsvp_item, rsvp_item_id, overpayment,
                )

        conn.execute(
            """UPDATE items
               SET transaction_status = 'active',
                   merchant = 'Paid Separately (Credit Transfer)',
                   item_price = ?,
                   holes = ?,
                   side_games = ?,
                   tee_choice = ?,
                   user_status = ?,
                   transferred_from_id = ?,
                   credit_note = ?
               WHERE id = ?""",
            (price_str, u_holes, u_games, u_tee, u_status,
             credited_items[0]["id"], balance_note, rsvp_item_id),
        )

        # Mark all credited items as transferred
        now_str = _dt.datetime.utcnow().isoformat()
        for ci in credited_items:
            conn.execute(
                """UPDATE items
                   SET transaction_status = 'transferred',
                       credit_note = ?,
                       transferred_to_id = ?
                   WHERE id = ?""",
                (f"Applied to {rsvp_item['item_name']} on {now_str[:10]}",
                 rsvp_item_id, ci["id"]),
            )
            # Accounting: transfer_out on source
            try:
                _write_acct_entry(
                    conn,
                    item_id=ci["id"],
                    event_name=ci["item_name"],
                    customer=ci.get("customer", ""),
                    order_id=ci.get("order_id", ""),
                    entry_type="contra",
                    category="transfer_out",
                    source="manual",
                    amount=_parse_dollar(ci.get("item_price")),
                    description=f"Credit transfer out → {rsvp_item['item_name']}",
                    account="TGF Checking",
                    source_ref=f"xfer-flat-{ci['id']}-out",
                    date=now_str[:10],
                )
            except Exception:
                logger.warning("Failed to write transfer_out for credit %s", ci["id"], exc_info=True)

        # Accounting: transfer_in on target
        try:
            _write_acct_entry(
                conn,
                item_id=rsvp_item_id,
                event_name=rsvp_item["item_name"],
                customer=rsvp_item.get("customer", ""),
                order_id=rsvp_item.get("order_id", ""),
                entry_type="income",
                category="transfer_in",
                source="credit_transfer",
                amount=applied,
                description=f"Credit transfer in from {credited_items[0]['item_name']}",
                account="TGF Checking",
                source_ref=f"xfer-flat-{rsvp_item_id}-in",
                date=now_str[:10],
            )
        except Exception:
            logger.warning("Failed to write transfer_in for rsvp item %s", rsvp_item_id, exc_info=True)

        # If excess and keep/venmo: create a new credited item for the remainder.
        # 'venmo' is treated like 'keep' here — the excess credit row is the audit
        # trail; the Venmo refund itself is a manual followup recorded separately.
        if excess > 0 and excess_action in ("keep", "venmo"):
            uid = f"credit-excess-{rsvp_item_id}-{int(_time.time() * 1000)}"
            conn.execute(
                """INSERT INTO items
                   (email_uid, merchant, customer, customer_email, item_name,
                    item_price, transaction_status, credit_note,
                    order_date, chapter)
                   VALUES (?, 'Manual Entry', ?, ?, ?,
                    ?, 'credited', ?,
                    date('now'), ?)""",
                (
                    uid,
                    rsvp_item.get("customer"), rsvp_item.get("customer_email"),
                    f"Excess credit — {rsvp_item['item_name'] or ''}".strip(" —"),
                    f"${excess:.2f}",
                    f"Excess credit from transfer — ${excess:.2f} remaining",
                    rsvp_item.get("chapter") or "",
                ),
            )

        conn.commit()
        return {
            "ok": True,
            "amount_applied": applied,
            "excess": excess,
            "amount_owed": amount_owed,
            "already_paid_via_children": already_paid,
            "existing_child_payment_ids": existing_children["ids"],
            "consumed_payment_ids": consumed["consumed_ids"],
            "consumed_payment_total": consumed["consumed_total"],
            "total_paid": total_paid,
            "remaining_owed": remaining_after_payments,
            "overpayment_credit_id": overpayment_credit_id,
            "new_price": breakdown["total"] if breakdown else None,
            "new_subtotal": new_subtotal,
        }


def capture_venmo_handle_for_customer(
    expense_id: int,
    db_path: str | Path | None = None,
) -> bool:
    """If the expense has both a customer_id and an other_party_handle, set the
    customer's venmo_username (only when currently empty). Returns True if updated.
    Idempotent — safe to call multiple times for the same expense."""
    with _connect(db_path) as conn:
        exp = conn.execute(
            """SELECT customer_id, other_party_handle FROM expense_transactions
               WHERE id = ?""",
            (expense_id,),
        ).fetchone()
        if not exp:
            return False
        cust_id = exp["customer_id"]
        handle = (exp["other_party_handle"] or "").strip().lstrip("@")
        if not cust_id or not handle:
            return False
        cur = conn.execute(
            """UPDATE customers SET venmo_username = ?
               WHERE customer_id = ?
                 AND (venmo_username IS NULL OR venmo_username = '')""",
            (handle, cust_id),
        )
        conn.commit()
        return cur.rowcount > 0


def auto_match_venmo_inbound_to_balance_due(
    expense_ids: list[int] | None = None,
    db_path: str | Path | None = None,
) -> dict:
    """Match incoming Venmo payments to open credit-transfer balance-due items.

    For each approved Venmo IN expense_transaction (optionally limited to
    `expense_ids`), find the unique active credit-transfer item that:
      - belongs to the same customer (case-insensitive name match)
      - has a credit_note starting with 'balance_due:'
      - has a balance amount within ±$1.00 of the expense amount

    On a unique match: create a +PAY child item via add_payment_to_event,
    flip the parent's credit_note from 'balance_due:X.XX' to
    'paid_at:YYYY-MM-DD', and stamp expense_transactions.matched_item_id.

    Returns {matched, ambiguous, no_candidate, already_matched, errors}.
    """
    import time as _time
    summary = {
        "matched": 0,
        "ambiguous": 0,
        "no_candidate": 0,
        "already_matched": 0,
        "errors": 0,
        "matches": [],
    }
    with _connect(db_path) as conn:
        # Pull approved or pending Venmo IN expenses, optionally filtered to specific IDs
        # pending Venmo INs are auto-approved when they match a balance-due item
        params: list = ["venmo", "received"]
        sql = (
            "SELECT * FROM expense_transactions "
            "WHERE source_type = ? AND transaction_type = ? "
            "AND review_status IN ('approved', 'pending') "
            "AND COALESCE(matched_item_id, 0) = 0"
        )
        if expense_ids:
            placeholders = ",".join(["?"] * len(expense_ids))
            sql += f" AND id IN ({placeholders})"
            params.extend(expense_ids)
        expenses = [dict(r) for r in conn.execute(sql, params).fetchall()]

        for exp in expenses:
            try:
                exp_amount = float(exp.get("amount") or 0)
                if exp_amount <= 0:
                    summary["no_candidate"] += 1
                    continue
                payer_name = (exp.get("merchant") or "").strip()
                if not payer_name:
                    summary["no_candidate"] += 1
                    continue

                # Find candidate active credit-transfer items for this customer.
                # Try exact name first, then fall back to customer_aliases lookup
                # so names like "Robert Callaway" match items stored as "Rob Callaway".
                _BALANCE_DUE_SQL = """SELECT id, customer, item_name, credit_note, item_price
                           FROM items
                           WHERE merchant = 'Paid Separately (Credit Transfer)'
                             AND COALESCE(transaction_status, 'active') = 'active'
                             AND credit_note LIKE 'balance_due:%'
                             AND customer = ? COLLATE NOCASE"""
                candidates = [
                    dict(r) for r in conn.execute(_BALANCE_DUE_SQL, (payer_name,)).fetchall()
                ]
                if not candidates:
                    # Try resolving payer_name through customer_aliases to canonical name
                    # (e.g. Venmo email says "James Baker" but customer stored as "Adam Baker")
                    alias_row = conn.execute(
                        """SELECT customer_name AS canonical
                           FROM customer_aliases
                           WHERE alias_value = ? COLLATE NOCASE
                             AND alias_type = 'name'
                           LIMIT 1""",
                        (payer_name,),
                    ).fetchone()
                    if alias_row:
                        candidates = [
                            dict(r) for r in conn.execute(
                                _BALANCE_DUE_SQL, (alias_row["canonical"],)
                            ).fetchall()
                        ]
                # Filter by amount tolerance (±$1.00)
                matched: list[dict] = []
                for c in candidates:
                    cnote = c.get("credit_note") or ""
                    try:
                        owed = float(cnote.split(":", 1)[1])
                    except (ValueError, IndexError):
                        continue
                    if abs(owed - exp_amount) <= 1.00:
                        c["_owed"] = owed
                        matched.append(c)

                if not matched:
                    summary["no_candidate"] += 1
                    continue
                if len(matched) > 1:
                    # Ambiguous — leave for manual handling
                    summary["ambiguous"] += 1
                    continue

                target = matched[0]
                target_id = target["id"]
                event_name = target["item_name"]
                customer_name = target["customer"]

                # Idempotency safety net: skip if any +PAY child already references this expense
                already = conn.execute(
                    """SELECT id FROM items
                       WHERE parent_item_id = ?
                         AND notes LIKE ? LIMIT 1""",
                    (target_id, f"%[venmo-bd-exp:{exp['id']}]%"),
                ).fetchone()
                if already:
                    summary["already_matched"] += 1
                    # Backfill the matched_item_id pointer if missing
                    conn.execute(
                        "UPDATE expense_transactions SET matched_item_id = ? WHERE id = ?",
                        (target_id, exp["id"]),
                    )
                    conn.commit()
                    continue

                # Create the +PAY child item
                txn_date = exp.get("transaction_date") or _dt.datetime.utcnow().strftime("%Y-%m-%d")
                amount_str = f"${exp_amount:.2f}"
                # Marker stays in notes so the match is auditable later
                note = f"Balance due — Venmo {amount_str} [venmo-bd-exp:{exp['id']}]"
                # We bypass add_payment_to_event() to set our own email_uid
                # (add_payment_to_event uses a timestamp uid; we want a deterministic one
                # so re-running the matcher is naturally idempotent on the items table too).
                event = dict(conn.execute(
                    "SELECT * FROM events WHERE item_name = ? COLLATE NOCASE",
                    (event_name,),
                ).fetchone() or {})
                parent_full = dict(conn.execute(
                    "SELECT * FROM items WHERE id = ?", (target_id,),
                ).fetchone() or {})
                parent_snap = {}
                for fld in ("side_games", "holes", "tee_choice", "user_status"):
                    if parent_full.get(fld) is not None:
                        parent_snap[fld] = parent_full[fld]

                uid = f"venmo-bd-{exp['id']}"
                new_values = {col: None for col in ITEM_COLUMNS}
                new_values["email_uid"] = uid
                new_values["item_index"] = 0
                new_values["customer"] = customer_name
                new_values["customer_email"] = parent_full.get("customer_email")
                new_values["customer_phone"] = parent_full.get("customer_phone")
                new_values["item_name"] = event_name
                new_values["order_date"] = txn_date
                new_values["course"] = event.get("course") or parent_full.get("course") or ""
                new_values["chapter"] = event.get("chapter") or parent_full.get("chapter") or ""
                new_values["transaction_status"] = "active"
                new_values["merchant"] = "Manual Entry (venmo)"
                new_values["item_price"] = amount_str
                new_values["side_games"] = ""
                new_values["notes"] = note
                new_values["parent_item_id"] = target_id
                new_values["parent_snapshot"] = json.dumps(parent_snap) if parent_snap else None

                # Resolve customer_id from customers table for FK linking
                cust_id = _resolve_or_create_customer(
                    conn,
                    customer_name=customer_name,
                    customer_email=parent_full.get("customer_email") or "",
                    phone=parent_full.get("customer_phone") or "",
                )
                if cust_id:
                    new_values["customer_id"] = cust_id

                cols = ", ".join(new_values.keys())
                placeholders = ", ".join(["?"] * len(new_values))
                try:
                    cur = conn.execute(
                        f"INSERT INTO items ({cols}) VALUES ({placeholders})",
                        list(new_values.values()),
                    )
                    new_item_id = cur.lastrowid
                except sqlite3.IntegrityError:
                    # Race: a previous run already created this +PAY. Look it up.
                    row = conn.execute(
                        "SELECT id FROM items WHERE email_uid = ? AND item_index = 0",
                        (uid,),
                    ).fetchone()
                    if row:
                        new_item_id = row["id"]
                        summary["already_matched"] += 1
                    else:
                        summary["errors"] += 1
                        continue

                # Flip parent's credit_note from balance_due:X.XX to paid_at:YYYY-MM-DD
                conn.execute(
                    "UPDATE items SET credit_note = ? WHERE id = ?",
                    (f"paid_at:{txn_date}", target_id),
                )

                # Stamp the expense as matched and auto-approve if still pending
                conn.execute(
                    """UPDATE expense_transactions
                       SET matched_item_id = ?,
                           review_status = CASE WHEN review_status = 'pending'
                                                THEN 'approved' ELSE review_status END
                       WHERE id = ?""",
                    (new_item_id, exp["id"]),
                )

                # If _sync_expense_ledger_entry already promoted this expense
                # to acct_transactions (description=merchant, no event/category),
                # soft-delete that row so the venmo-bd entry below is the single
                # source of truth — otherwise we double-count the same payment.
                old_acct_id = exp.get("acct_transaction_id")
                if old_acct_id:
                    conn.execute(
                        "UPDATE acct_transactions SET status = 'reversed', updated_at = datetime('now') WHERE id = ?",
                        (old_acct_id,),
                    )

                # Write accounting entries (income/addon + allocation) for the +PAY child
                try:
                    new_acct_id = _write_acct_entry(
                        conn,
                        item_id=new_item_id,
                        event_name=event_name,
                        customer=customer_name,
                        order_id=f"VENMO-BD-{new_item_id}",
                        entry_type="income",
                        category="addon",
                        source="venmo",
                        amount=exp_amount,
                        description=f"Venmo balance-due payment from {customer_name}",
                        account="Venmo",
                        source_ref=f"venmo-bd-{exp['id']}",
                        date=txn_date,
                    )
                    # Re-point the expense_transaction at the venmo-bd row so
                    # subsequent sync calls don't recreate the exp-promoted dup.
                    if new_acct_id:
                        conn.execute(
                            "UPDATE expense_transactions SET acct_transaction_id = ? WHERE id = ?",
                            (new_acct_id, exp["id"]),
                        )
                except Exception:
                    logger.warning(
                        "Failed to write acct entry for venmo balance-due match (exp %s)",
                        exp["id"], exc_info=True,
                    )

                conn.commit()
                # Also stamp the player's Venmo @handle on their customer record if not set.
                # Best-effort; ignore failures.
                try:
                    capture_venmo_handle_for_customer(exp["id"], db_path=db_path)
                except Exception:
                    logger.warning(
                        "capture_venmo_handle_for_customer failed for exp %s",
                        exp["id"], exc_info=True,
                    )
                summary["matched"] += 1
                summary["matches"].append({
                    "expense_id": exp["id"],
                    "item_id": new_item_id,
                    "parent_item_id": target_id,
                    "customer": customer_name,
                    "event_name": event_name,
                    "amount": exp_amount,
                })
            except Exception:
                logger.warning(
                    "auto_match_venmo_inbound_to_balance_due failed for expense %s",
                    exp.get("id"), exc_info=True,
                )
                summary["errors"] += 1

    return summary


def reconcile_orphan_venmo_payments(
    db_path: str | Path | None = None,
    max_days_back: int = 14,
    dry_run: bool = False,
) -> dict:
    """Sweep credit-transfer items with `balance_due:` notes and net them against:
      1. Existing manual-entry +PAY children already attached to the parent
         (case-insensitive match on `merchant LIKE 'Manual Entry%'`), and
      2. Orphan +PAY items by the same customer in the last `max_days_back`
         days (these get reparented onto the credit-transfer item).

    Fixes both:
      - "Paid via Venmo before RSVP, then Apply Credit" (orphan case)
      - "+PAY entered against the parent but credit_note was never reduced"
        (already-attached child case — Joshua Bartz)

    Idempotent and safe to re-run.

    Returns: {"scanned", "fixed", "fully_paid", "partially_paid",
              "overpayments_posted", "details": [...]}
    """
    import datetime as _dt
    summary = {
        "scanned": 0, "fixed": 0, "fully_paid": 0,
        "partially_paid": 0, "overpayments_posted": 0,
        "details": [],
    }
    with _connect(db_path) as conn:
        parents = conn.execute(
            """SELECT id, customer, customer_email, item_name, chapter, credit_note
               FROM items
               WHERE merchant = 'Paid Separately (Credit Transfer)'
                 AND COALESCE(transaction_status, 'active') = 'active'
                 AND credit_note LIKE 'balance_due:%'"""
        ).fetchall()
        summary["scanned"] = len(parents)

        for p in parents:
            p = dict(p)
            try:
                owed = float((p["credit_note"] or "").split(":", 1)[1])
            except (ValueError, IndexError):
                continue
            if owed <= 0:
                continue
            customer = (p.get("customer") or "").strip()
            if not customer:
                continue

            # Pass 1: existing manual-entry children already attached.
            existing = _sum_existing_child_payments(conn, p["id"])
            already_paid = existing["total"]

            # Pass 2: any remainder consumed from orphan payments by this customer.
            remainder_owed = max(0.0, round(owed - already_paid, 2))
            consumed = {"consumed_total": 0.0, "consumed_ids": [], "remaining_owed": remainder_owed}
            if remainder_owed > 0:
                consumed = _consume_unallocated_payments_for_credit_transfer(
                    conn,
                    parent_item_id=p["id"],
                    customer=customer,
                    amount_owed=remainder_owed,
                    max_days_back=max_days_back,
                    exclude_ids={p["id"], *existing["ids"]},
                )

            total_paid = round(already_paid + consumed["consumed_total"], 2)
            if total_paid <= 0:
                continue  # nothing to apply for this parent

            remaining = max(0.0, round(owed - total_paid, 2))
            overpayment = max(0.0, round(total_paid - owed, 2))
            new_note = (
                f"balance_due:{remaining:.2f}" if remaining > 0
                else f"paid_at:{_dt.datetime.utcnow().strftime('%Y-%m-%d')}"
            )

            if dry_run:
                # Roll back any reparenting so dry-run leaves the DB unchanged.
                tag = _XFER_CONSUMED_TAG.format(parent_id=p["id"])
                for cid in consumed["consumed_ids"]:
                    cur = conn.execute(
                        "SELECT notes FROM items WHERE id = ?", (cid,)
                    ).fetchone()
                    cleaned = " ".join((cur["notes"] or "").replace(tag, "").split())
                    conn.execute(
                        "UPDATE items SET parent_item_id = NULL, notes = ? WHERE id = ?",
                        (cleaned or None, cid),
                    )
            else:
                conn.execute(
                    "UPDATE items SET credit_note = ? WHERE id = ?",
                    (new_note, p["id"]),
                )
                if overpayment > 0:
                    _post_overpayment_credit(conn, p, p["id"], overpayment)
                    summary["overpayments_posted"] += 1

            summary["fixed"] += 1
            if remaining > 0:
                summary["partially_paid"] += 1
            else:
                summary["fully_paid"] += 1
            summary["details"].append({
                "parent_item_id": p["id"],
                "customer": customer,
                "event": p.get("item_name"),
                "owed": owed,
                "already_paid_via_children": already_paid,
                "existing_child_ids": existing["ids"],
                "consumed_orphan_total": consumed["consumed_total"],
                "consumed_orphan_ids": consumed["consumed_ids"],
                "total_paid": total_paid,
                "remaining": remaining,
                "overpayment": overpayment,
            })

        if not dry_run:
            conn.commit()
    return summary


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

        # Resolve customer_id at insert time so the FK is populated immediately
        rsvp_customer_id = _lookup_customer_id(
            conn, rsvp.get("player_name"), rsvp.get("player_email")
        )

        try:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO rsvps
                   (email_uid, player_name, player_email, gg_event_name,
                    event_identifier, event_date, response, received_at,
                    matched_event, matched_item_id, customer_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    rsvp_customer_id,
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

        # Resolve full names. Prefer the customers table via customer_id FK
        # (authoritative for RSVP-only players who never bought a ticket);
        # fall back to items.customer by email; last fall back to player_name.
        results = []
        for r in rows:
            rsvp = dict(r)
            rsvp["resolved_name"] = rsvp.get("player_name")
            rsvp["has_player_card"] = False
            rsvp["customer_status"] = None
            cid = rsvp.get("customer_id")
            if cid:
                cust = conn.execute(
                    """SELECT TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')) AS full_name,
                              c.current_player_status,
                              EXISTS(SELECT 1 FROM customer_roles r
                                     WHERE r.customer_id = c.customer_id
                                       AND r.role_type IN ('manager','owner','admin')) AS is_staff
                       FROM customers c WHERE c.customer_id = ?""",
                    (cid,),
                ).fetchone()
                if cust:
                    if cust["full_name"]:
                        rsvp["resolved_name"] = cust["full_name"]
                    if cust["is_staff"]:
                        rsvp["customer_status"] = "MANAGER"
                    elif cust["current_player_status"] == "active_member":
                        rsvp["customer_status"] = "MEMBER"
                    elif cust["current_player_status"] == "member_plus":
                        rsvp["customer_status"] = "MEMBER+"
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
                    if not cid:
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

        # Resolve canonical full names + member status from customers table via customer_id FK.
        # Authoritative for RSVP-only players who never bought a ticket.
        cust_ids = {r["customer_id"] for r in rows if r["customer_id"]}
        cust_name_map = {}
        cust_status_map = {}
        if cust_ids:
            placeholders = ",".join("?" * len(cust_ids))
            cust_rows = conn.execute(
                f"""SELECT c.customer_id,
                           TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')) AS full_name,
                           c.current_player_status,
                           EXISTS(SELECT 1 FROM customer_roles r
                                  WHERE r.customer_id = c.customer_id
                                    AND r.role_type IN ('manager','owner','admin')) AS is_staff
                    FROM customers c
                    WHERE c.customer_id IN ({placeholders})""",
                list(cust_ids),
            ).fetchall()
            status_label = {"active_member": "MEMBER", "member_plus": "MEMBER+"}
            for c in cust_rows:
                if c["full_name"]:
                    cust_name_map[c["customer_id"]] = c["full_name"]
                if c["is_staff"]:
                    cust_status_map[c["customer_id"]] = "MANAGER"
                elif c["current_player_status"] in status_label:
                    cust_status_map[c["customer_id"]] = status_label[c["current_player_status"]]

        rsvps_by_event = {}
        for r in rows:
            rsvp = dict(r)
            email = (rsvp.get("player_email") or "").strip().lower()
            cid = rsvp.get("customer_id")
            rsvp["resolved_name"] = (
                cust_name_map.get(cid)
                or name_map.get(email)
                or rsvp.get("player_name")
            )
            rsvp["has_player_card"] = email in name_map
            rsvp["customer_status"] = cust_status_map.get(cid)
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
    """Return RSVPs with optional filtering by event and/or response.

    Also resolves the full customer name from the items table and
    customer_aliases (email type) so the frontend can show the canonical
    name and knows which RSVPs still need manual linking.
    """
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

        # Bulk-resolve customer names from items table by email
        emails = {(r["player_email"] or "").strip().lower()
                  for r in rows if r["player_email"]}
        name_map: dict[str, str] = {}
        if emails:
            placeholders = ",".join("?" * len(emails))
            # Primary: match on items.customer_email
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

            # Secondary: match on customer_aliases (email type)
            unresolved = emails - set(name_map.keys())
            if unresolved:
                ph2 = ",".join("?" * len(unresolved))
                alias_rows = conn.execute(
                    f"""SELECT LOWER(alias_value) as email, customer_name
                        FROM customer_aliases
                        WHERE alias_type = 'email'
                          AND LOWER(alias_value) IN ({ph2})""",
                    list(unresolved),
                ).fetchall()
                for a in alias_rows:
                    if a["email"] not in name_map:
                        name_map[a["email"]] = a["customer_name"]

        results = []
        for r in rows:
            rsvp = dict(r)
            email = (rsvp.get("player_email") or "").strip().lower()
            rsvp["resolved_name"] = name_map.get(email, rsvp.get("player_name"))
            rsvp["has_player_card"] = email in name_map
            results.append(rsvp)

        return results


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


def audit_event_rsvps(event_name: str, db_path: str | Path | None = None) -> dict:
    """Audit and fix RSVP-to-item matches for a specific event.

    Checks all RSVPs matched to this event and:
    1. Clears matched_item_id when the RSVP email doesn't match the item's email
       (fixes false positives from first-name matching)
    2. Re-attempts matching for RSVPs with no matched_item_id

    Returns {"cleared": N, "rematched": N, "details": [...]}
    """
    with _connect(db_path) as conn:
        rsvps = conn.execute(
            "SELECT * FROM rsvps WHERE matched_event = ?",
            (event_name,),
        ).fetchall()

        cleared = 0
        rematched = 0
        details = []

        for row in rsvps:
            rsvp = dict(row)

            # Check existing matched_item_id for email mismatch
            if rsvp.get("matched_item_id"):
                item = conn.execute(
                    "SELECT id, customer, customer_email FROM items WHERE id = ?",
                    (rsvp["matched_item_id"],),
                ).fetchone()
                if item:
                    rsvp_email = (rsvp.get("player_email") or "").strip().lower()
                    item_email = (item["customer_email"] or "").strip().lower()
                    if rsvp_email and item_email and rsvp_email != item_email:
                        # Mismatched — clear the bad match
                        conn.execute(
                            "UPDATE rsvps SET matched_item_id = NULL WHERE id = ?",
                            (rsvp["id"],),
                        )
                        details.append({
                            "action": "cleared",
                            "rsvp_player": rsvp.get("player_name"),
                            "rsvp_email": rsvp.get("player_email"),
                            "was_matched_to": item["customer"],
                            "item_email": item["customer_email"],
                        })
                        cleared += 1
                        rsvp["matched_item_id"] = None  # proceed to re-match below
                elif not item:
                    # Item was deleted — clear the stale reference
                    conn.execute(
                        "UPDATE rsvps SET matched_item_id = NULL WHERE id = ?",
                        (rsvp["id"],),
                    )
                    details.append({
                        "action": "cleared_deleted",
                        "rsvp_player": rsvp.get("player_name"),
                        "rsvp_email": rsvp.get("player_email"),
                        "was_matched_to_id": rsvp.get("matched_item_id"),
                    })
                    cleared += 1
                    rsvp["matched_item_id"] = None

            # Re-attempt matching for unmatched RSVPs
            if not rsvp.get("matched_item_id"):
                matched_item = match_rsvp_to_item(
                    rsvp.get("player_email"), rsvp.get("player_name"),
                    event_name, db_path,
                )
                if matched_item:
                    conn.execute(
                        "UPDATE rsvps SET matched_item_id = ? WHERE id = ?",
                        (matched_item, rsvp["id"]),
                    )
                    details.append({
                        "action": "rematched",
                        "rsvp_player": rsvp.get("player_name"),
                        "rsvp_email": rsvp.get("player_email"),
                        "matched_to_item_id": matched_item,
                    })
                    rematched += 1

        conn.commit()
        logger.info("Audit event '%s': cleared %d bad matches, rematched %d",
                     event_name, cleared, rematched)
        return {"cleared": cleared, "rematched": rematched, "details": details}


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
                   COUNT(DISTINCT CASE
                       WHEN COALESCE(i.transaction_status, 'active') IN ('active', 'rsvp_only')
                       THEN i.id END) as total_playing,
                   GROUP_CONCAT(DISTINCT ea.alias_name) as aliases
            FROM events e
            LEFT JOIN event_aliases ea ON ea.canonical_event_name = e.item_name
            LEFT JOIN items i
                ON (i.item_name = e.item_name COLLATE NOCASE OR i.item_name = ea.alias_name COLLATE NOCASE)
                AND COALESCE(i.transaction_status, 'active') IN ('active', 'rsvp_only')
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
            # Count unmatched GG RSVPs (playing, matched to event but not to a
            # specific item row) so the email can mirror the badge totals.
            gg_count = conn.execute(
                """
                SELECT COUNT(*) as cnt FROM rsvps
                WHERE response = 'PLAYING'
                  AND matched_item_id IS NULL
                  AND matched_event = ?
                """,
                (d["item_name"],),
            ).fetchone()["cnt"]
            d["gg_rsvp_count"] = gg_count
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


# ---------------------------------------------------------------------------
# Handicap calculator
# ---------------------------------------------------------------------------

# WHS Rule 5.2a differential lookup: number of differentials to use.
_HANDICAP_DIFF_LOOKUP = {
    3: 1,  4: 1,  5: 1,
    6: 2,  7: 2,  8: 2,
    9: 3, 10: 3, 11: 3,
    12: 4, 13: 4, 14: 4,
    15: 5, 16: 5,
    17: 6, 18: 6,
    19: 7,
    20: 8,
}

# WHS Rule 5.2a adjustments (added after avg × 0.96).
# Applied when fewer rounds yield an index that could be too favourable.
_HANDICAP_ADJUSTMENT = {3: -2.0, 4: -1.0, 6: -1.0}

_HANDICAP_SETTINGS_DEFAULTS = {
    "lookback_months": "12",      # max age of rounds to count
    "min_rounds": "3",            # minimum rounds before index is shown
    "multiplier": "0.96",         # USGA 0.96 factor
}


def _normalize_player_name(raw: str) -> str:
    """Convert 'LAST, First' or 'Last, First' to 'First Last' Title Case.

    If no comma is present, applies Title Case as-is.
    """
    raw = (raw or "").strip()
    if "," in raw:
        parts = raw.split(",", 1)
        last = parts[0].strip().title()
        first = parts[1].strip().title()
        return f"{first} {last}"
    return raw.title()


def get_handicap_settings(db_path: str | Path | None = None) -> dict:
    """Return all handicap settings as a dict of {key: value} strings."""
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT key, value FROM handicap_settings").fetchall()
    result = dict(_HANDICAP_SETTINGS_DEFAULTS)
    for row in rows:
        result[row["key"]] = row["value"]
    return result


def update_handicap_settings(settings: dict,
                               db_path: str | Path | None = None) -> None:
    """Upsert one or more handicap settings keys."""
    with _connect(db_path) as conn:
        for key, value in settings.items():
            conn.execute(
                "INSERT INTO handicap_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "updated_at = datetime('now')",
                (key, str(value)),
            )
        conn.commit()


def compute_handicap_index(differentials: list[float],
                            settings: dict | None = None) -> float | None:
    """Compute 9-hole handicap index from a list of 9-hole differentials.

    Uses up to 20 most-recent differentials, USGA WHS lookup table, and the
    configurable multiplier (default 0.96).  Returns None if fewer than
    min_rounds (default 3) rounds are provided.
    Truncates (floors) to one decimal place.
    """
    cfg = settings or _HANDICAP_SETTINGS_DEFAULTS
    min_rounds = int(cfg.get("min_rounds", 3))
    multiplier = float(cfg.get("multiplier", 0.96))

    n = min(len(differentials), 20)
    if n < min_rounds:
        return None
    n = max(n, 3)  # lookup table starts at 3
    count = _HANDICAP_DIFF_LOOKUP.get(n, 10)
    best = sorted(differentials)[:count]
    avg = sum(best) / count
    adjustment = _HANDICAP_ADJUSTMENT.get(n, 0.0)
    index = avg * multiplier + adjustment
    # WHS Rule 5.2: round to nearest tenth (.5 rounds toward +infinity / toward zero for negatives).
    return round(index * 10) / 10


def _match_customer_by_email(conn: sqlite3.Connection, email: str,
                             player_name: str = "") -> str | None:
    """Match a player to a customer by email address.

    Looks up the email in the items table (customer_email column) and returns
    the canonical customer name. When multiple customers share the same email,
    prefers the one whose name is most similar to ``player_name``.
    """
    if not email:
        return None
    rows = conn.execute(
        """SELECT DISTINCT customer FROM items
           WHERE LOWER(customer_email) = LOWER(?)
           AND customer IS NOT NULL AND customer != ''""",
        (email,),
    ).fetchall()
    if rows:
        if len(rows) == 1:
            return rows[0]["customer"]
        # Multiple customers share this email — pick the best name match
        if player_name:
            pn = player_name.lower().strip()
            best = None
            best_score = -1
            for row in rows:
                cname = (row["customer"] or "").lower().strip()
                # Score: count matching words between player name and customer name
                pn_words = set(pn.split())
                cn_words = set(cname.split())
                score = len(pn_words & cn_words)
                if score > best_score:
                    best_score = score
                    best = row["customer"]
            if best:
                return best
        return rows[0]["customer"]
    # Also check customer_aliases for email aliases
    row = conn.execute(
        """SELECT ca.customer_name FROM customer_aliases ca
           WHERE ca.alias_type = 'email' AND LOWER(ca.alias_value) = LOWER(?)
           LIMIT 1""",
        (email,),
    ).fetchone()
    if row:
        return row["customer_name"]
    return None


def _match_customer_name(conn: sqlite3.Connection, player_name: str) -> str | None:
    """Try to find a matching customer name in the items table.

    Tries in order:
    1. Exact case-insensitive match on the customer field.
    2. Match on first_name + last_name parts (handles 'John Smith' vs stored parts).
    3. LIKE match: customer field contains the player name or vice versa.
    4. Name alias match: check customer_aliases for a matching name alias.
    5. Reversed name match: 'Last First' when player is 'First Last'.
    Returns the canonical customer name as stored in items, or None if no match.
    """
    # 1. Exact name match
    row = conn.execute(
        "SELECT DISTINCT customer FROM items WHERE customer = ? COLLATE NOCASE "
        "AND customer IS NOT NULL AND customer != '' LIMIT 1",
        (player_name,),
    ).fetchone()
    if row:
        return row["customer"]

    parts = player_name.strip().split()

    # 2. First + last name match using parsed name parts
    if len(parts) >= 2:
        first = parts[0].lower()
        last = parts[-1].lower()
        row = conn.execute(
            """SELECT DISTINCT customer FROM items
               WHERE LOWER(first_name) = ? AND LOWER(last_name) = ?
               AND customer IS NOT NULL AND customer != ''
               LIMIT 1""",
            (first, last),
        ).fetchone()
        if row:
            return row["customer"]

    # 3. LIKE match — player name contains within customer field or vice versa
    #    Handles suffixes like "Jr", "III", middle names, etc.
    if len(parts) >= 2:
        first = parts[0]
        last = parts[-1]
        # Customer might be "First Last Jr" while player is "First Last"
        row = conn.execute(
            """SELECT DISTINCT customer FROM items
               WHERE customer LIKE ? COLLATE NOCASE
               AND customer IS NOT NULL AND customer != ''
               LIMIT 1""",
            (f"{first}%{last}%",),
        ).fetchone()
        if row:
            return row["customer"]

        # Also try: customer is "First Last" but player is "First Middle Last"
        row = conn.execute(
            """SELECT DISTINCT customer FROM items
               WHERE customer LIKE ? COLLATE NOCASE
               AND customer IS NOT NULL AND customer != ''
               LIMIT 1""",
            (f"{first}%{last}",),
        ).fetchone()
        if row:
            return row["customer"]

    # 4. Name alias match
    row = conn.execute(
        """SELECT ca.customer_name FROM customer_aliases ca
           WHERE ca.alias_type = 'name' AND ca.alias_value = ? COLLATE NOCASE
           LIMIT 1""",
        (player_name,),
    ).fetchone()
    if row:
        return row["customer_name"]

    # 5. Reversed name: try "Last First" if player is "First Last"
    if len(parts) == 2:
        reversed_name = f"{parts[1]} {parts[0]}"
        row = conn.execute(
            "SELECT DISTINCT customer FROM items WHERE customer = ? COLLATE NOCASE "
            "AND customer IS NOT NULL AND customer != '' LIMIT 1",
            (reversed_name,),
        ).fetchone()
        if row:
            return row["customer"]

    # 6. Last-name-only match: if exactly one customer shares the same last name,
    #    assume it's the same person (handles nickname differences like Rob/Robert).
    if len(parts) >= 2:
        last = parts[-1]
        rows = conn.execute(
            """SELECT DISTINCT customer FROM items
               WHERE LOWER(last_name) = LOWER(?)
               AND customer IS NOT NULL AND customer != ''""",
            (last,),
        ).fetchall()
        if len(rows) == 1:
            return rows[0]["customer"]

    return None


def relink_all_unlinked_players(db_path: str | Path | None = None) -> dict:
    """Try to match every unlinked handicap player to a customer record.

    Runs _match_customer_name for all players in handicap_player_links where
    customer_name IS NULL. Useful after adding new customers or after the initial
    import when auto-linking may have failed.

    Returns {"linked": N, "still_unlinked": M, "total": T}
    """
    with _connect(db_path) as conn:
        unlinked = conn.execute(
            "SELECT player_name FROM handicap_player_links WHERE customer_name IS NULL"
        ).fetchall()

        linked = 0
        for row in unlinked:
            pname = row["player_name"]
            customer_name = _match_customer_name(conn, pname)
            if customer_name:
                cid = _lookup_customer_id(conn, customer_name, None)
                conn.execute(
                    "UPDATE handicap_player_links SET customer_name = ?, customer_id = ? WHERE player_name = ?",
                    (customer_name, cid, pname),
                )
                linked += 1

        still_unlinked = conn.execute(
            "SELECT COUNT(*) FROM handicap_player_links WHERE customer_name IS NULL"
        ).fetchone()[0]
        total = conn.execute(
            "SELECT COUNT(*) FROM handicap_player_links"
        ).fetchone()[0]

    return {"linked": linked, "still_unlinked": still_unlinked, "total": total}


def import_handicap_rounds(rounds: list[dict],
                            db_path: str | Path | None = None) -> dict:
    """Upsert handicap rounds from a Golf Genius / Handicap Server export.

    Each dict should contain:
      player_name (str), round_date (str YYYY-MM-DD), round_id (str|None),
      course_name (str|None), tee_name (str|None),
      adjusted_score (int|str), rating (float|str), slope (int|str),
      differential (float|str|None) — used as-is when provided, else computed.
      player_email (str|None) — optional; when provided, used as first-priority
      method to link the player to a customer record via customer_email.

    Names in 'Last, First' format are normalised to 'First Last' Title Case.
    Dedup key: (player_name, round_date, round_id) when round_id present;
               (player_name, round_date, course_name, tee_name) otherwise.

    Returns {"inserted": N, "skipped": M, "matched": N, "errors": [...]}
    where "matched" is the number of players linked to an existing customer.
    """
    inserted = 0
    skipped = 0
    errors = []
    matched = 0
    # Track which player_names we've already attempted to link this import
    _linked: set[str] = set()

    with _connect(db_path) as conn:
        for i, r in enumerate(rounds):
            try:
                raw_name = (r.get("player_name") or "").strip()
                if not raw_name:
                    errors.append(f"Row {i+1}: missing player_name")
                    continue
                player_name = _normalize_player_name(raw_name)

                # Try to link to a customer (once per unique player_name per import)
                player_email = (r.get("player_email") or "").strip().lower() or None
                if player_name not in _linked:
                    _linked.add(player_name)
                    existing = conn.execute(
                        "SELECT customer_name FROM handicap_player_links WHERE player_name = ?",
                        (player_name,),
                    ).fetchone()
                    # Re-attempt linking if player exists but has no customer_name yet
                    if existing is None:
                        # Try email-based match first (highest confidence)
                        customer_name = None
                        if player_email:
                            customer_name = _match_customer_by_email(conn, player_email, player_name)
                        if not customer_name:
                            customer_name = _match_customer_name(conn, player_name)
                        cid = _lookup_customer_id(conn, customer_name, player_email) if customer_name else None
                        conn.execute(
                            """INSERT INTO handicap_player_links (player_name, customer_name, customer_id)
                               VALUES (?, ?, ?)
                               ON CONFLICT(player_name) DO NOTHING""",
                            (player_name, customer_name, cid),
                        )
                        if customer_name:
                            matched += 1
                    elif not existing["customer_name"]:
                        customer_name = None
                        if player_email:
                            customer_name = _match_customer_by_email(conn, player_email, player_name)
                        if not customer_name:
                            customer_name = _match_customer_name(conn, player_name)
                        if customer_name:
                            cid = _lookup_customer_id(conn, customer_name, player_email)
                            conn.execute(
                                "UPDATE handicap_player_links SET customer_name = ?, customer_id = ? WHERE player_name = ?",
                                (customer_name, cid, player_name),
                            )
                            matched += 1

                round_date = (r.get("round_date") or "").strip()
                if not round_date:
                    errors.append(f"Row {i+1}: missing round_date")
                    continue

                round_id = (r.get("round_id") or "").strip() or None
                course_name = (r.get("course_name") or "").strip() or None
                tee_name = (r.get("tee_name") or "").strip() or None

                adjusted_score = int(float(str(r["adjusted_score"]).strip()))
                rating = float(str(r["rating"]).strip())
                slope = int(float(str(r["slope"]).strip()))

                # Reject 18-hole rounds (9-hole course ratings are ~30–42;
                # 18-hole ratings are ~60–80).
                if rating > 50:
                    errors.append(
                        f"Row {i+1}: course rating {rating} looks like an 18-hole "
                        f"rating (9-hole ratings are typically 30–42). Only 9-hole "
                        f"rounds are supported — please split into two 9-hole scores."
                    )
                    continue

                # Use pre-calculated differential when available
                raw_diff = r.get("differential")
                if raw_diff is not None and str(raw_diff).strip() not in ("", "None"):
                    differential = round(float(str(raw_diff).strip()), 2)
                else:
                    if slope == 0:
                        errors.append(f"Row {i+1}: slope is 0 (invalid)")
                        continue
                    differential = round((adjusted_score - rating) * 113.0 / slope, 2)

                # Dedup check
                if round_id:
                    existing = conn.execute(
                        "SELECT id FROM handicap_rounds "
                        "WHERE player_name = ? AND round_date = ? AND round_id = ?",
                        (player_name, round_date, round_id),
                    ).fetchone()
                else:
                    existing = conn.execute(
                        "SELECT id FROM handicap_rounds "
                        "WHERE player_name = ? AND round_date = ? "
                        "AND COALESCE(course_name,'') = COALESCE(?,'') "
                        "AND COALESCE(tee_name,'') = COALESCE(?,'')",
                        (player_name, round_date, course_name, tee_name),
                    ).fetchone()

                if existing:
                    skipped += 1
                    continue

                conn.execute(
                    "INSERT INTO handicap_rounds "
                    "(player_name, round_date, round_id, course_name, tee_name, "
                    " adjusted_score, rating, slope, differential) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (player_name, round_date, round_id, course_name, tee_name,
                     adjusted_score, rating, slope, differential),
                )
                inserted += 1
            except (KeyError, ValueError, TypeError) as e:
                errors.append(f"Row {i+1}: {e}")

        conn.commit()

    return {"inserted": inserted, "skipped": skipped, "matched": matched, "errors": errors[:50]}


def get_handicap_rounds(player_name: str | None = None,
                         db_path: str | Path | None = None) -> list[dict]:
    """Return handicap rounds, optionally filtered to one player, newest first."""
    with _connect(db_path) as conn:
        if player_name:
            round_rows = conn.execute(
                "SELECT * FROM handicap_rounds WHERE player_name = ? "
                "ORDER BY round_date DESC, id DESC",
                (player_name,),
            ).fetchall()
        else:
            round_rows = conn.execute(
                "SELECT * FROM handicap_rounds ORDER BY round_date DESC, id DESC"
            ).fetchall()
        return [dict(r) for r in round_rows]


def delete_handicap_round(round_id: int,
                           db_path: str | Path | None = None) -> bool:
    """Delete a single handicap round row by primary key. Returns True if deleted."""
    with _connect(db_path) as conn:
        rows_affected = conn.execute(
            "DELETE FROM handicap_rounds WHERE id = ?", (round_id,)
        ).rowcount
        conn.commit()
        return rows_affected > 0


def delete_all_handicap_rounds_for_player(player_name: str,
                                           db_path: str | Path | None = None) -> int:
    """Delete all handicap rounds for a player. Returns count deleted."""
    with _connect(db_path) as conn:
        rows_affected = conn.execute(
            "DELETE FROM handicap_rounds WHERE player_name = ?", (player_name,)
        ).rowcount
        conn.commit()
        return rows_affected


def get_handicap_export_data(chapter: str | None = None,
                             test_player_email: str | None = None,
                             db_path: str | Path | None = None) -> dict:
    """Return handicap data formatted for Golf Genius CSV export.

    Joins handicap players → handicap_player_links → items to get
    email address and chapter for each linked player.

    The 9-hole TGF handicap index is multiplied by 2 to produce the
    18-hole equivalent that Golf Genius stores and displays.

    Args:
        chapter: If given (e.g. "San Antonio" or "Austin"), filters to that chapter only.
        test_player_email: If given, returns only the single matching player — for
                           test runs before committing to a full league sync.

    Returns:
        {
          "rows": [{"email": ..., "player_name": ...,
                    "handicap_index_9": float,   # raw 9-hole index
                    "handicap_index": float,      # ×2 for GG (18-hole)
                    "chapter": ...}],
          "no_email": [player_name, ...],   # have an index but no linked email
          "no_index": [player_name, ...],   # linked but N/A index
          "chapter": chapter or "All",
        }
    """
    players = get_all_handicap_players(db_path)
    player_map = {p["player_name"]: p for p in players}

    with _connect(db_path) as conn:
        links = conn.execute(
            """SELECT l.player_name, l.customer_name,
                      COALESCE(
                        (SELECT LOWER(TRIM(i1.customer_email)) FROM items i1
                         WHERE LOWER(i1.customer) = LOWER(l.customer_name)
                           AND i1.customer_email IS NOT NULL AND TRIM(i1.customer_email) != ''
                         ORDER BY i1.id DESC LIMIT 1),
                        (SELECT LOWER(TRIM(ca.alias_value)) FROM customer_aliases ca
                         WHERE LOWER(ca.customer_name) = LOWER(l.customer_name)
                           AND ca.alias_type = 'email'
                         LIMIT 1),
                        ''
                      ) AS customer_email,
                      COALESCE(
                        (SELECT i2.chapter FROM items i2
                         WHERE LOWER(i2.customer) = LOWER(l.customer_name)
                           AND i2.chapter IS NOT NULL AND TRIM(i2.chapter) != ''
                         ORDER BY i2.id DESC LIMIT 1),
                        ''
                      ) AS chapter,
                      COALESCE(
                        (SELECT i3.last_name FROM items i3
                         WHERE LOWER(i3.customer) = LOWER(l.customer_name)
                           AND i3.last_name IS NOT NULL AND TRIM(i3.last_name) != ''
                         ORDER BY i3.id DESC LIMIT 1),
                        ''
                      ) AS last_name,
                      COALESCE(
                        (SELECT i4.first_name FROM items i4
                         WHERE LOWER(i4.customer) = LOWER(l.customer_name)
                           AND i4.first_name IS NOT NULL AND TRIM(i4.first_name) != ''
                         ORDER BY i4.id DESC LIMIT 1),
                        ''
                      ) AS first_name,
                      COALESCE(
                        (SELECT i5.suffix FROM items i5
                         WHERE LOWER(i5.customer) = LOWER(l.customer_name)
                           AND i5.suffix IS NOT NULL AND TRIM(i5.suffix) != ''
                         ORDER BY i5.id DESC LIMIT 1),
                        ''
                      ) AS suffix
               FROM handicap_player_links l
               WHERE l.customer_name IS NOT NULL""",
        ).fetchall()

        # Also collect ALL chapters per customer for multi-chapter players
        all_chapters = conn.execute(
            """SELECT DISTINCT LOWER(l.customer_name) AS cname_lower,
                      i.chapter
               FROM handicap_player_links l
               JOIN items i ON LOWER(i.customer) = LOWER(l.customer_name)
               WHERE l.customer_name IS NOT NULL
                 AND i.chapter IS NOT NULL AND TRIM(i.chapter) != ''""",
        ).fetchall()

    # Build set of chapters per customer name (lowercase)
    customer_chapters: dict[str, set[str]] = {}
    for row in all_chapters:
        customer_chapters.setdefault(row["cname_lower"], set()).add(
            row["chapter"].lower()
        )

    # Build a map: player_name → (email, chapter, all_chapters) from best linked record
    link_map: dict[str, dict] = {}
    for lnk in links:
        pname = lnk["player_name"]
        if pname not in link_map:
            cname_lower = (lnk["customer_name"] or "").strip().lower()
            link_map[pname] = {
                "email": (lnk["customer_email"] or "").strip().lower(),
                "chapter": lnk["chapter"] or "",
                "all_chapters": customer_chapters.get(cname_lower, set()),
                "last_name": (lnk["last_name"] or "").strip(),
                "first_name": (lnk["first_name"] or "").strip(),
                "suffix": (lnk["suffix"] or "").strip(),
            }

    # Check if ANY linked player has chapter data; if not, skip chapter filtering
    has_chapter_data = any(v["chapter"] for v in link_map.values())

    rows = []
    no_email = []
    no_index = []
    seen_emails: set[str] = set()

    for pname, p in player_map.items():
        info = link_map.get(pname)
        if info is None:
            # No linked customer with email
            if p["handicap_index"] is not None:
                no_email.append(pname)
            continue

        # Chapter filter — include player if they have ANY transaction in the chapter
        if chapter and has_chapter_data:
            if chapter.lower() not in info["all_chapters"]:
                continue

        if p["handicap_index"] is None:
            no_index.append(pname)
            continue

        email = info["email"]
        if not email or email in seen_emails:
            if not email and p["handicap_index"] is not None:
                no_email.append(pname)
            continue

        # Test mode: only include this one player
        if test_player_email and email != test_player_email.strip().lower():
            continue

        seen_emails.add(email)

        # GG stores 18-hole indexes; our index is 9-hole → multiply by 2
        idx_9 = p["handicap_index"]
        idx_18 = round(idx_9 * 2, 1)

        rows.append({
            "email": email,
            "player_name": pname,
            "handicap_index_9": idx_9,   # kept for reference / display
            "handicap_index": idx_18,    # value written to CSV / sent to GG
            "chapter": info["chapter"],
            "last_name": info["last_name"],
            "first_name": info["first_name"],
            "suffix": info["suffix"],
        })

    # Sort by player name
    rows.sort(key=lambda r: (r["last_name"].lower(), r["first_name"].lower()))

    return {
        "rows": rows,
        "no_email": sorted(no_email),
        "no_index": sorted(no_index),
        "chapter": chapter or "All",
        "_debug": {
            "total_players": len(player_map),
            "total_linked": len(link_map),
            "has_chapter_data": has_chapter_data,
            "chapter_filter": chapter,
            "link_sample": [
                {"player": k, "email": v["email"][:3] + "..." if v["email"] else None,
                 "chapter": v["chapter"]}
                for k, v in list(link_map.items())[:10]
            ],
        },
    }


def get_all_handicap_players(db_path: str | Path | None = None) -> list[dict]:
    """Return one record per player with current handicap index and round stats.

    Only rounds within the lookback_months window count toward the index.
    """
    cfg = get_handicap_settings(db_path)
    lookback_months = int(cfg.get("lookback_months", 12))

    # Cutoff date: today minus lookback_months
    cutoff = datetime.now() - timedelta(days=lookback_months * 30.44)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    with _connect(db_path) as conn:
        summary_rows = conn.execute(
            """
            SELECT r.player_name,
                   COUNT(*) AS total_rounds,
                   SUM(CASE WHEN r.round_date >= ? THEN 1 ELSE 0 END) AS active_rounds,
                   MAX(r.round_date) AS latest_round_date,
                   MIN(r.differential) AS best_differential,
                   AVG(r.differential) AS avg_differential,
                   l.customer_name
            FROM handicap_rounds r
            LEFT JOIN handicap_player_links l ON l.player_name = r.player_name
            WHERE r.differential IS NOT NULL
            GROUP BY r.player_name
            ORDER BY r.player_name COLLATE NOCASE
            """,
            (cutoff_str,),
        ).fetchall()

        # Fetch last 20 differentials within the lookback window for each player
        all_diffs = conn.execute(
            """
            SELECT player_name, differential,
                   ROW_NUMBER() OVER (
                       PARTITION BY player_name
                       ORDER BY round_date DESC, id DESC
                   ) AS rn
            FROM handicap_rounds
            WHERE differential IS NOT NULL
              AND round_date >= ?
            """,
            (cutoff_str,),
        ).fetchall()

    player_diffs: dict[str, list[float]] = {}
    for d in all_diffs:
        if d["rn"] <= 20:
            player_diffs.setdefault(d["player_name"], []).append(d["differential"])

    players = []
    for row in summary_rows:
        name = row["player_name"]
        diffs = player_diffs.get(name, [])
        index = compute_handicap_index(diffs, cfg)
        players.append({
            "player_name": name,
            "customer_name": row["customer_name"],
            "handicap_index": index,
            "handicap_index_18": round(index * 2, 1) if index is not None else None,
            "total_rounds": row["total_rounds"],
            "active_rounds": row["active_rounds"],
            "latest_round_date": row["latest_round_date"],
            "best_differential": round(row["best_differential"], 2) if row["best_differential"] is not None else None,
            "avg_differential": round(row["avg_differential"], 2) if row["avg_differential"] is not None else None,
        })

    return players


# ---------------------------------------------------------------------------
# Handicap Email Card — data assembly + HTML builder
# ---------------------------------------------------------------------------

def build_handicap_card_data(player_name: str,
                             db_path: str | Path | None = None) -> dict:
    """Assemble all data needed to render a TGF Handicap Card email.

    Returns a dict with player metadata, index values, annotated rounds
    (each marked USED or ACTIVE), and summary counts.
    """
    cfg = get_handicap_settings(db_path)
    lookback_months = int(cfg.get("lookback_months", 12))
    min_rounds = int(cfg.get("min_rounds", 3))

    cutoff = datetime.now() - timedelta(days=lookback_months * 30.44)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    # Get all rounds for this player
    all_rounds = get_handicap_rounds(player_name=player_name, db_path=db_path)

    # Filter to active rounds (within lookback window, with a differential)
    active_rounds = [
        r for r in all_rounds
        if r.get("differential") is not None and (r.get("round_date") or "") >= cutoff_str
    ]

    # Pool = most recent 20 active rounds (already sorted newest-first by get_handicap_rounds)
    pool = active_rounds[:20]

    # Compute index
    pool_diffs = [r["differential"] for r in pool]
    index_9 = compute_handicap_index(pool_diffs, cfg)
    index_18 = round(index_9 * 2, 1) if index_9 is not None else None

    # Determine which differentials are "USED" (lowest N per lookup table)
    multiplier = float(cfg.get("multiplier", 0.96))
    n = min(len(pool_diffs), 20)
    used_count = 0
    adjustment = 0.0
    if n >= min_rounds:
        n_clamped = max(n, 3)
        used_count = _HANDICAP_DIFF_LOOKUP.get(n_clamped, 8)
        adjustment = _HANDICAP_ADJUSTMENT.get(n_clamped, 0.0)

    # Mark rounds: sort by differential to find the N lowest, then restore date order
    if used_count > 0:
        indexed_pool = [(i, r["differential"]) for i, r in enumerate(pool)]
        indexed_pool.sort(key=lambda x: x[1])
        used_indices = {indexed_pool[j][0] for j in range(min(used_count, len(indexed_pool)))}
    else:
        used_indices = set()

    annotated_rounds = []
    for i, r in enumerate(pool):
        annotated_rounds.append({
            "round_date": r.get("round_date") or "",
            "course_name": r.get("course_name") or "",
            "tee_name": r.get("tee_name") or "",
            "adjusted_score": r.get("adjusted_score"),
            "rating": r.get("rating"),
            "slope": r.get("slope"),
            "differential": r.get("differential"),
            "status": "USED" if i in used_indices else "ACTIVE",
        })

    # Resolve player metadata via the canonical resolver helpers
    # (customers / customer_emails first; items.* only as last-resort fallback).
    email = ""
    chapter = ""
    first_name = ""
    last_name = ""
    with _connect(db_path) as conn:
        link = conn.execute(
            "SELECT customer_name FROM handicap_player_links WHERE player_name = ?",
            (player_name,),
        ).fetchone()
        if link and link["customer_name"]:
            cname = link["customer_name"]

            # Find the most recent items row for this name to seed the
            # resolvers with a customer_id (so they don't fall back to name match).
            seed_row = conn.execute(
                """SELECT customer, customer_id, customer_email, customer_phone,
                          chapter, first_name, last_name, user_status
                   FROM items
                   WHERE LOWER(customer) = LOWER(?)
                   ORDER BY id DESC LIMIT 1""",
                (cname,),
            ).fetchone()
            seed = dict(seed_row) if seed_row else {"customer": cname, "customer_id": None}

            email = resolve_player_email(seed, conn=conn)
            chapter = resolve_player_chapter(seed, conn=conn)
            name_parts = resolve_player_name(seed, conn=conn)
            first_name = name_parts.get("first_name", "")
            last_name = name_parts.get("last_name", "")

            # Last-resort: pick up an email alias if customers had nothing
            if not email:
                alias = conn.execute(
                    """SELECT alias_value FROM customer_aliases
                       WHERE LOWER(customer_name) = LOWER(?)
                         AND alias_type = 'email' LIMIT 1""",
                    (cname,),
                ).fetchone()
                if alias and alias["alias_value"]:
                    email = alias["alias_value"].strip().lower()

    # Gather calculation breakdown for display
    used_diffs = sorted([r["differential"] for r in annotated_rounds if r["status"] == "USED"])
    avg_used = sum(used_diffs) / len(used_diffs) if used_diffs else 0.0

    today_str = datetime.now().strftime("%Y-%m-%d")
    return {
        "player_name": player_name,
        "first_name": first_name,
        "last_name": last_name,
        "chapter": chapter,
        "email": email,
        "handicap_index_9": index_9,
        "handicap_index_18": index_18,
        "rounds": annotated_rounds,
        "rounds_used": used_count,
        "rounds_pool": len(pool),
        "generated_date": today_str,
        "lookback_months": lookback_months,
        "used_diffs": used_diffs,
        "avg_used": avg_used,
        "multiplier": multiplier,
        "adjustment": adjustment,
    }


def _fmt_handicap_display(index_9: float | None) -> str:
    """Format a 9-hole index for display: '+2.1N', '6.3N', or 'N/A'."""
    if index_9 is None:
        return "N/A"
    if index_9 < 0:
        return f"+{abs(index_9):.1f}N"
    return f"{index_9:.1f}N"


def build_handicap_card_html(card_data: dict) -> str:
    """Build a styled HTML email for a TGF Handicap Card.

    Uses only inline CSS and table-based layout for email client compatibility.
    """
    name = card_data["player_name"]
    first = card_data.get("first_name") or ""
    last = card_data.get("last_name") or ""
    display_name = f"{first} {last}".strip() if first or last else name
    chapter = card_data.get("chapter") or ""
    date_str = card_data.get("generated_date") or ""
    idx_9 = card_data.get("handicap_index_9")
    idx_18 = card_data.get("handicap_index_18")
    rounds = card_data.get("rounds") or []
    rounds_used = card_data.get("rounds_used", 0)
    rounds_pool = card_data.get("rounds_pool", 0)
    lookback = card_data.get("lookback_months", 12)

    idx_9_display = _fmt_handicap_display(idx_9)
    idx_18_display = f"{abs(idx_18):.1f}" if idx_18 is not None else "N/A"
    if idx_18 is not None and idx_18 < 0:
        idx_18_display = f"+{abs(idx_18):.1f}"

    idx_color = "#2563eb" if idx_9 is not None else "#94a3b8"

    # Build score history rows
    _font = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
    score_rows = ""
    for i, r in enumerate(rounds):
        diff_val = r.get("differential")
        diff_str = f"{diff_val:.1f}" if diff_val is not None else "—"
        is_used = r.get("status") == "USED"

        if is_used:
            bg = "#dcfce7"
            diff_style = f"font-weight:700; color:#166534; font-family:{_font};"
            status_html = '<span style="color:#16a34a; font-size:15px;">&#9733;</span>'
        else:
            bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
            diff_style = f"color:#475569; font-family:{_font};"
            status_html = ""

        _td = f"padding:4px 8px; border-bottom:1px solid #f1f5f9; font-size:13px; font-family:{_font};"
        _nw = "white-space:nowrap;"
        score_rows += f"""<tr style="background-color:{bg};">
  <td style="{_td} {_nw}">{r.get('round_date', '')}</td>
  <td style="{_td}">{r.get('course_name', '')}</td>
  <td style="{_td} {_nw} text-align:center;">{r.get('tee_name', '')}</td>
  <td style="{_td} {_nw} text-align:center;">{r.get('adjusted_score', '')}</td>
  <td style="{_td} {_nw} text-align:center;">{r.get('rating', '')}</td>
  <td style="{_td} {_nw} text-align:center;">{r.get('slope', '')}</td>
  <td style="{_td} {_nw} text-align:center; {diff_style}">{diff_str}</td>
  <td style="{_td} {_nw} text-align:center;">{status_html}</td>
</tr>"""

    summary_text = ""
    calc_html = ""
    if idx_9 is not None:
        used_diffs = card_data.get("used_diffs") or []
        avg_used = card_data.get("avg_used", 0.0)
        multiplier = card_data.get("multiplier", 0.96)
        adjustment = card_data.get("adjustment", 0.0)

        summary_text = (
            f"Based on best {rounds_used} of {rounds_pool} round{'s' if rounds_pool != 1 else ''} "
            f"(last {lookback} months)"
        )

        # Compact calculation line
        after_mult = avg_used * multiplier
        adj_str = ""
        if adjustment != 0.0:
            sign = "+" if adjustment > 0 else "\u2013"
            adj_str = f" {sign} {abs(adjustment):.1f}"

        calc_html = (
            f'Avg of lowest {rounds_used}: {avg_used:.2f} &#215; {multiplier} = '
            f'{after_mult:.2f}{adj_str} &#8594; <strong style="color:#64748b;">{idx_9_display}</strong>'
        )
    else:
        summary_text = f"Not enough rounds for a handicap index (minimum {card_data.get('min_rounds', 3)} required)"

    chapter_line = f'<div style="font-size:13px; color:#64748b; margin-top:2px;">{chapter}</div>' if chapter else ""

    _f = "Arial, Helvetica, sans-serif"
    _th = f"padding:5px 8px; font-size:11px; font-weight:600; color:#64748b; text-transform:uppercase; border-bottom:2px solid #e2e8f0; font-family:{_f};"

    html = f"""<html><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"></head>
<body style="font-family:{_f};color:#333;margin:0;padding:0;background:#f1f5f9;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f1f5f9;">
<tr><td align="center" style="padding:24px 8px;">
<table cellpadding="0" cellspacing="0" border="0" width="700" style="background:#ffffff;border:1px solid #e2e8f0;">

  <tr>
    <td style="background:#1e40af; padding:20px 24px;">
      <table cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr>
          <td style="vertical-align:middle; font-family:{_f};">
            <span style="font-size:28px; font-weight:800; color:#ffffff; letter-spacing:1px;">TGF</span><br>
            <span style="font-size:12px; color:#93c5fd;">The Golf Fellowship</span>
          </td>
          <td style="text-align:right; vertical-align:middle; font-size:14px; font-weight:600; color:#93c5fd; text-transform:uppercase; letter-spacing:1px; font-family:{_f};">
            Handicap Card
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <tr>
    <td style="padding:24px;">
      <table cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr>
          <td style="vertical-align:top; font-family:{_f};">
            <span style="font-size:22px; font-weight:700; color:#1e293b;">{display_name}</span><br>
            {('<span style="font-size:13px; color:#64748b;">' + chapter + '</span><br>') if chapter else ''}
            <span style="font-size:12px; color:#94a3b8;">As of {date_str}</span>
          </td>
          <td style="text-align:right; vertical-align:top; width:160px;">
            <table cellpadding="0" cellspacing="0" border="0" align="right" style="background:#f0f7ff; border:2px solid #bfdbfe;">
              <tr>
                <td style="padding:12px 20px; text-align:center; font-family:{_f};">
                  <span style="font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:1px;">9-Hole Index</span><br>
                  <span style="font-size:32px; font-weight:800; color:{idx_color};">{idx_9_display}</span><br>
                  <span style="font-size:12px; color:#64748b;">18-Hole: {idx_18_display}</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <tr>
    <td style="padding:0 24px 16px; font-family:{_f};">
      <hr style="border:none; border-top:1px solid #e2e8f0; margin:0 0 12px 0;">
      <span style="font-size:13px; color:#64748b;">{summary_text}</span><br>
      <span style="font-size:12px; color:#94a3b8;">{calc_html}</span>
    </td>
  </tr>

  <tr>
    <td style="padding:0 24px 24px;">
      <table cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse; border:1px solid #e2e8f0;">
        <tr style="background:#f1f5f9;">
          <th style="{_th} text-align:left;">Date</th>
          <th style="{_th} text-align:left;">Course</th>
          <th style="{_th} text-align:center;">Tee</th>
          <th style="{_th} text-align:center;">Score</th>
          <th style="{_th} text-align:center;">Rating</th>
          <th style="{_th} text-align:center;">Slope</th>
          <th style="{_th} text-align:center;">Diff</th>
          <th style="{_th} text-align:center;">Status</th>
        </tr>
        {score_rows}
      </table>
    </td>
  </tr>

  <tr>
    <td style="background:#f8fafc; padding:16px 24px; border-top:1px solid #e2e8f0; font-family:{_f}; text-align:center; font-size:12px; color:#94a3b8;">
        <strong style="color:#64748b;">The Golf Fellowship</strong> &#8212; 9-Hole Handicap Index<br>
        <span style="font-size:11px;">This is not an official USGA handicap.
        Calculated per WHS rules for TGF league play.</span>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Season Contest Enrollment
# ---------------------------------------------------------------------------

def enroll_season_contest(customer_name: str, contest_type: str,
                          chapter: str = "", season: str = "",
                          source_item_id: int | None = None,
                          db_path: str | Path | None = None) -> dict:
    """Enroll a customer in a season contest (NET Points Race, GROSS Points Race, City Match Play).

    Returns the enrollment dict. Idempotent — re-enrolling is a no-op.
    """
    with _connect(db_path) as conn:
        try:
            conn.execute(
                """INSERT INTO season_contests (customer_name, contest_type, chapter, season, source_item_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (customer_name, contest_type, chapter or "", season or "", source_item_id),
            )
            conn.commit()
            logger.info("Enrolled %s in %s (%s/%s)", customer_name, contest_type, chapter, season)
        except sqlite3.IntegrityError:
            pass  # already enrolled
        row = conn.execute(
            "SELECT * FROM season_contests WHERE customer_name = ? AND contest_type = ? AND chapter = ? AND season = ?",
            (customer_name, contest_type, chapter or "", season or ""),
        ).fetchone()
        return dict(row) if row else {}


def get_season_contest_enrollments(contest_type: str | None = None,
                                    chapter: str | None = None,
                                    season: str | None = None,
                                    db_path: str | Path | None = None) -> list[dict]:
    """List season contest enrollments, optionally filtered."""
    clauses = []
    params = []
    if contest_type:
        clauses.append("contest_type = ?")
        params.append(contest_type)
    if chapter:
        clauses.append("chapter = ?")
        params.append(chapter)
    if season:
        clauses.append("season = ?")
        params.append(season)
    where = " AND ".join(clauses) if clauses else "1=1"
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM season_contests WHERE {where} ORDER BY enrolled_at DESC", params
        ).fetchall()
        return [dict(r) for r in rows]


def get_customer_season_contests(customer_name: str,
                                  db_path: str | Path | None = None) -> list[dict]:
    """Get all season contest enrollments for a specific customer."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM season_contests WHERE customer_name = ? COLLATE NOCASE ORDER BY season, contest_type",
            (customer_name,),
        ).fetchall()
        return [dict(r) for r in rows]


def sync_season_contests_from_items(db_path: str | Path | None = None) -> dict:
    """Scan all items and enroll customers in season contests based on their
    net_points_race, gross_points_race, city_match_play fields.

    Also handles standalone SEASON CONTESTS items.
    Returns summary of enrollments made.
    """
    enrolled = 0
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT id, customer, chapter, net_points_race, gross_points_race, city_match_play,
                      item_name, order_date
               FROM items
               WHERE transaction_status IN ('active', NULL)
                 AND (net_points_race = 'YES' OR gross_points_race = 'YES' OR city_match_play = 'YES'
                      OR UPPER(item_name) LIKE '%SEASON CONTEST%')"""
        ).fetchall()

        for row in rows:
            row = dict(row)
            customer = row.get("customer") or ""
            chapter = row.get("chapter") or ""
            # Derive season from order_date (e.g. "2026" from "2026-03-10")
            order_date = row.get("order_date") or ""
            season = order_date[:4] if len(order_date) >= 4 else ""
            item_id = row["id"]

            if (row.get("net_points_race") or "").upper() == "YES":
                try:
                    conn.execute(
                        """INSERT INTO season_contests (customer_name, contest_type, chapter, season, source_item_id)
                           VALUES (?, ?, ?, ?, ?)""",
                        (customer, "NET Points Race", chapter, season, item_id),
                    )
                    enrolled += 1
                except sqlite3.IntegrityError:
                    pass

            if (row.get("gross_points_race") or "").upper() == "YES":
                try:
                    conn.execute(
                        """INSERT INTO season_contests (customer_name, contest_type, chapter, season, source_item_id)
                           VALUES (?, ?, ?, ?, ?)""",
                        (customer, "GROSS Points Race", chapter, season, item_id),
                    )
                    enrolled += 1
                except sqlite3.IntegrityError:
                    pass

            if (row.get("city_match_play") or "").upper() == "YES":
                try:
                    conn.execute(
                        """INSERT INTO season_contests (customer_name, contest_type, chapter, season, source_item_id)
                           VALUES (?, ?, ?, ?, ?)""",
                        (customer, "City Match Play", chapter, season, item_id),
                    )
                    enrolled += 1
                except sqlite3.IntegrityError:
                    pass

        # Handle standalone "SEASON CONTESTS" items with bundle info in notes
        bundle_rows = conn.execute(
            """SELECT id, customer, chapter, item_name, notes, order_date
               FROM items
               WHERE UPPER(item_name) LIKE '%SEASON CONTEST%'
                 AND transaction_status IN ('active', NULL)"""
        ).fetchall()
        for row in bundle_rows:
            row = dict(row)
            customer = row.get("customer") or ""
            chapter = row.get("chapter") or ""
            order_date = row.get("order_date") or ""
            season = order_date[:4] if len(order_date) >= 4 else ""
            item_name = (row.get("item_name") or "").upper()
            item_id = row["id"]

            # "Points NET Bundle" or similar → enroll in both NET Points Race and City Match Play
            if "NET" in item_name or "NET" in (row.get("notes") or "").upper():
                for ct in ["NET Points Race", "City Match Play"]:
                    try:
                        conn.execute(
                            """INSERT INTO season_contests (customer_name, contest_type, chapter, season, source_item_id)
                               VALUES (?, ?, ?, ?, ?)""",
                            (customer, ct, chapter, season, item_id),
                        )
                        enrolled += 1
                    except sqlite3.IntegrityError:
                        pass
            if "GROSS" in item_name or "GROSS" in (row.get("notes") or "").upper():
                for ct in ["GROSS Points Race", "City Match Play"]:
                    try:
                        conn.execute(
                            """INSERT INTO season_contests (customer_name, contest_type, chapter, season, source_item_id)
                               VALUES (?, ?, ?, ?, ?)""",
                            (customer, ct, chapter, season, item_id),
                        )
                        enrolled += 1
                    except sqlite3.IntegrityError:
                        pass

        conn.commit()
    logger.info("Season contest sync: %d new enrollments", enrolled)
    return {"enrolled": enrolled}


# ---------------------------------------------------------------------------
# App Settings — persistent key/value store (survives Railway redeploys)
# ---------------------------------------------------------------------------

def get_app_setting(key: str, db_path: str | Path | None = None) -> str | None:
    """Return a single app setting value, or None if not set."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_app_setting(key: str, value: str, db_path: str | Path | None = None) -> None:
    """Upsert a single app setting."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
            (key, value),
        )
        conn.commit()


# ═══════════════════════════════════════════════════════════════════════════
# Accounting Module — Multi-Entity Bookkeeping
# ═══════════════════════════════════════════════════════════════════════════

def _seed_acct_categories(conn: sqlite3.Connection) -> None:
    """Populate standard accounting categories.

    Business expenses follow IRS Schedule C / standard chart of accounts.
    Personal expenses follow standard personal finance categories.
    TGF-specific categories are entity-scoped.
    """
    # ── Business Expense Categories (standard bookkeeping) ──
    business_expenses = [
        # IRS Schedule C / standard COA categories
        ("Advertising & Marketing", None),
        ("Bank & Processing Fees", None),
        ("Business Insurance", None),
        ("Business Meals", None),
        ("Car & Truck Expenses", None),
        ("Commissions & Fees", None),
        ("Contract Labor", None),
        ("Cost of Goods Sold", None),
        ("Depreciation", None),
        ("Dues & Subscriptions", None),
        ("Equipment & Tools", None),
        ("Interest Expense", None),
        ("Legal & Professional Services", None),
        ("Licenses & Permits", None),
        ("Office Expenses & Supplies", None),
        ("Payroll Expenses", None),
        ("Postage & Shipping", None),
        ("Printing & Reproduction", None),
        ("Rent / Lease — Equipment", None),
        ("Rent / Lease — Space", None),
        ("Repairs & Maintenance", None),
        ("Software & Technology", None),
        ("Taxes — Federal", None),
        ("Taxes — State & Local", None),
        ("Taxes — Payroll", None),
        ("Telephone & Internet", None),
        ("Travel — Lodging", None),
        ("Travel — Transportation", None),
        ("Utilities", None),
        ("Other Business Expense", None),
    ]

    # ── Personal Expense Categories ──
    personal_expenses = [
        ("Groceries", None),
        ("Dining & Restaurants", None),
        ("Gas & Fuel", None),
        ("Auto — Insurance", None),
        ("Auto — Maintenance", None),
        ("Auto — Payment", None),
        ("Healthcare — Medical", None),
        ("Healthcare — Dental", None),
        ("Healthcare — Pharmacy", None),
        ("Housing — Mortgage / Rent", None),
        ("Housing — Insurance", None),
        ("Housing — Property Tax", None),
        ("Housing — Repairs", None),
        ("Utilities — Electric", None),
        ("Utilities — Gas", None),
        ("Utilities — Water", None),
        ("Utilities — Internet / Cable", None),
        ("Utilities — Phone", None),
        ("Clothing & Apparel", None),
        ("Personal Care", None),
        ("Entertainment", None),
        ("Subscriptions & Streaming", None),
        ("Education & Training", None),
        ("Childcare", None),
        ("Pet Care", None),
        ("Gifts & Donations", None),
        ("Charity — Deductible", None),
        ("Home & Garden", None),
        ("Fitness & Recreation", None),
        ("ATM / Cash Withdrawal", None),
        ("Other Personal Expense", None),
    ]

    # ── TGF-Specific Categories (entity-scoped) ──
    # These get linked to the TGF entity (id=1 from seed)
    tgf_entity = conn.execute(
        "SELECT id FROM acct_entities WHERE short_name = 'TGF'"
    ).fetchone()
    tgf_id = tgf_entity["id"] if tgf_entity else None

    tgf_expenses = [
        ("Golf Course Fees / Green Fees", tgf_id),
        ("Event Supplies & Prizes", tgf_id),
        ("Food & Beverage — Events", tgf_id),
        ("Side Game Payouts", tgf_id),
        ("Golf Cart Fees", tgf_id),
        ("Range & Practice Fees", tgf_id),
        ("Tournament Entry Fees", tgf_id),
    ]

    # ── Income Categories (standard) ──
    income_cats = [
        # Business income
        ("Sales Revenue", None),
        ("Service Revenue", None),
        ("Consulting Income", None),
        ("Commission Income", None),
        ("Rental Income", None),
        ("Interest Income", None),
        ("Dividend Income", None),
        ("Refunds & Returns", None),
        ("Reimbursements", None),
        ("Other Business Income", None),
        # Personal income
        ("Salary & Wages", None),
        ("Freelance / Contract Income", None),
        ("Investment Income", None),
        ("Other Personal Income", None),
        # TGF-specific income
        ("Event Revenue", tgf_id),
        ("Membership Fees", tgf_id),
        ("Side Game Fees", tgf_id),
        ("Sponsorship Revenue", tgf_id),
        ("Merchandise Sales", tgf_id),
    ]

    sort = 0
    for name, entity_id in business_expenses + personal_expenses + tgf_expenses:
        conn.execute(
            "INSERT INTO acct_categories (name, type, entity_id, sort_order) VALUES (?, 'expense', ?, ?)",
            (name, entity_id, sort),
        )
        sort += 1
    sort = 0
    for name, entity_id in income_cats:
        conn.execute(
            "INSERT INTO acct_categories (name, type, entity_id, sort_order) VALUES (?, 'income', ?, ?)",
            (name, entity_id, sort),
        )
        sort += 1


def _seed_unified_financial_categories(conn: sqlite3.Connection) -> None:
    """Seed accounting categories needed by the unified financial model (Issue #242).

    Runs on every init_db() call but skips categories that already exist.
    """
    tgf_entity = conn.execute(
        "SELECT id FROM acct_entities WHERE short_name = 'TGF'"
    ).fetchone()
    tgf_id = tgf_entity["id"] if tgf_entity else None

    new_categories = [
        # (name, type, entity_id)
        ("Credit Transfer Out", "expense", tgf_id),
        ("Credit Transfer In", "income", tgf_id),
        ("External Payment", "income", tgf_id),
        ("Player Refunds", "expense", tgf_id),
        ("Transaction Fee Income", "income", tgf_id),
        ("Payment Processing Fees", "expense", tgf_id),
        # General expense categories (entity_id=None → available for all entities)
        ("Internet & Utilities", "expense", None),
    ]
    for name, cat_type, entity_id in new_categories:
        existing = conn.execute(
            "SELECT id FROM acct_categories WHERE name = ? AND type = ?",
            (name, cat_type),
        ).fetchone()
        if not existing:
            max_sort = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 1 AS s FROM acct_categories WHERE type = ?",
                (cat_type,),
            ).fetchone()["s"]
            conn.execute(
                "INSERT INTO acct_categories (name, type, entity_id, sort_order) VALUES (?, ?, ?, ?)",
                (name, cat_type, entity_id, max_sort),
            )
            logger.info("Seeded acct_category: %s (%s)", name, cat_type)
    conn.commit()


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

def get_all_acct_entities(db_path: str | Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM acct_entities WHERE is_active = 1 ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def create_acct_entity(name: str, short_name: str, color: str = "#2563eb",
                       db_path: str | Path | None = None) -> dict:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO acct_entities (name, short_name, color) VALUES (?, ?, ?)",
            (name, short_name, color),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM acct_entities WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def update_acct_entity(entity_id: int, db_path: str | Path | None = None, **fields) -> dict:
    allowed = {"name", "short_name", "color", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return {}
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE acct_entities SET {set_clause} WHERE id = ?",
            (*updates.values(), entity_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM acct_entities WHERE id = ?", (entity_id,)).fetchone()
    return dict(row) if row else {}


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def get_acct_categories(entity_id: int | None = None, cat_type: str | None = None,
                        db_path: str | Path | None = None) -> list[dict]:
    clauses, params = ["is_active = 1"], []
    if entity_id is not None:
        clauses.append("(entity_id = ? OR entity_id IS NULL)")
        params.append(entity_id)
    if cat_type:
        clauses.append("type = ?")
        params.append(cat_type)
    where = " AND ".join(clauses)
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM acct_categories WHERE {where} ORDER BY type, sort_order, name",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def create_acct_category(name: str, cat_type: str, entity_id: int | None = None,
                         parent_id: int | None = None, icon: str | None = None,
                         db_path: str | Path | None = None) -> dict:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO acct_categories (name, type, entity_id, parent_id, icon) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, cat_type, entity_id, parent_id, icon),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM acct_categories WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def update_acct_category(cat_id: int, db_path: str | Path | None = None, **fields) -> dict:
    allowed = {"name", "type", "entity_id", "parent_id", "icon", "is_active", "sort_order"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return {}
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE acct_categories SET {set_clause} WHERE id = ?",
            (*updates.values(), cat_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM acct_categories WHERE id = ?", (cat_id,)).fetchone()
    return dict(row) if row else {}


def delete_acct_category(cat_id: int, db_path: str | Path | None = None) -> bool:
    with _connect(db_path) as conn:
        conn.execute("UPDATE acct_categories SET is_active = 0 WHERE id = ?", (cat_id,))
        conn.commit()
    return True


# ---------------------------------------------------------------------------
# Payment Accounts
# ---------------------------------------------------------------------------

def get_acct_accounts(entity_id: int | None = None,
                      db_path: str | Path | None = None) -> list[dict]:
    if entity_id is not None:
        sql = "SELECT * FROM acct_accounts WHERE is_active = 1 AND entity_id = ? ORDER BY name"
        params: tuple = (entity_id,)
    else:
        sql = "SELECT * FROM acct_accounts WHERE is_active = 1 ORDER BY name"
        params = ()
    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def create_acct_account(name: str, account_type: str, entity_id: int | None = None,
                        institution: str | None = None, last_four: str | None = None,
                        opening_balance: float = 0,
                        db_path: str | Path | None = None) -> dict:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO acct_accounts (name, account_type, entity_id, institution, last_four, opening_balance) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, account_type, entity_id, institution, last_four, opening_balance),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM acct_accounts WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def update_acct_account(account_id: int, db_path: str | Path | None = None, **fields) -> dict:
    allowed = {"name", "account_type", "entity_id", "institution", "last_four", "opening_balance", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return {}
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE acct_accounts SET {set_clause} WHERE id = ?",
            (*updates.values(), account_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM acct_accounts WHERE id = ?", (account_id,)).fetchone()
    return dict(row) if row else {}


def get_acct_account_balances(db_path: str | Path | None = None) -> list[dict]:
    """Return all active accounts with computed current balance."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT a.*,
                   a.opening_balance
                   + COALESCE((SELECT SUM(t.total_amount) FROM acct_transactions t
                               WHERE t.account_id = a.id AND t.type = 'income'), 0)
                   - COALESCE((SELECT SUM(t.total_amount) FROM acct_transactions t
                               WHERE t.account_id = a.id AND t.type = 'expense'), 0)
                   + COALESCE((SELECT SUM(t.total_amount) FROM acct_transactions t
                               WHERE t.transfer_to_account_id = a.id AND t.type = 'transfer'), 0)
                   - COALESCE((SELECT SUM(t.total_amount) FROM acct_transactions t
                               WHERE t.account_id = a.id AND t.type = 'transfer'), 0)
                   AS current_balance
            FROM acct_accounts a
            WHERE a.is_active = 1
            ORDER BY a.name
            """
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Account Rules (AI bookkeeper heuristics)
# ---------------------------------------------------------------------------

def get_acct_account_rules(account_id: int, db_path: str | Path | None = None) -> dict:
    """Return all rules for an account as a dict."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT rule_type, rule_value FROM acct_account_rules WHERE account_id = ?",
            (account_id,),
        ).fetchall()
    return {r["rule_type"]: r["rule_value"] for r in rows}


def set_acct_account_rule(account_id: int, rule_type: str, rule_value: str,
                          db_path: str | Path | None = None) -> None:
    """Upsert an account rule."""
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO acct_account_rules (account_id, rule_type, rule_value)
               VALUES (?, ?, ?)
               ON CONFLICT(account_id, rule_type) DO UPDATE SET rule_value = excluded.rule_value""",
            (account_id, rule_type, rule_value),
        )
        conn.commit()


def get_all_acct_account_rules(db_path: str | Path | None = None) -> dict:
    """Return all account rules keyed by account_id."""
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM acct_account_rules").fetchall()
    result = {}
    for r in rows:
        aid = r["account_id"]
        if aid not in result:
            result[aid] = {}
        result[aid][r["rule_type"]] = r["rule_value"]
    return result


# ---------------------------------------------------------------------------
# Keyword Categorization Rules
# ---------------------------------------------------------------------------

def get_acct_keyword_rules(db_path: str | Path | None = None) -> list[dict]:
    """Return all keyword categorization rules with category/entity names."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT kr.*, c.name as category_name, e.short_name as entity_name
               FROM acct_keyword_rules kr
               LEFT JOIN acct_categories c ON c.id = kr.category_id
               LEFT JOIN acct_entities e ON e.id = kr.entity_id
               ORDER BY kr.keyword"""
        ).fetchall()
    return [dict(r) for r in rows]


def create_acct_keyword_rule(keyword: str, match_type: str = "contains",
                             category_id: int | None = None,
                             entity_id: int | None = None,
                             db_path: str | Path | None = None) -> dict:
    """Create a new keyword rule."""
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO acct_keyword_rules (keyword, match_type, category_id, entity_id)
               VALUES (?, ?, ?, ?)""",
            (keyword.strip(), match_type, category_id, entity_id),
        )
        conn.commit()
        return {"id": conn.execute("SELECT last_insert_rowid()").fetchone()[0]}


def update_acct_keyword_rule(rule_id: int, data: dict,
                             db_path: str | Path | None = None) -> dict:
    """Update an existing keyword rule."""
    fields, values = [], []
    for key in ("keyword", "match_type", "category_id", "entity_id", "is_active"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return {"error": "No fields to update"}
    values.append(rule_id)
    with _connect(db_path) as conn:
        conn.execute(f"UPDATE acct_keyword_rules SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    return {"updated": True}


def delete_acct_keyword_rule(rule_id: int, db_path: str | Path | None = None) -> dict:
    """Delete a keyword rule."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM acct_keyword_rules WHERE id = ?", (rule_id,))
        conn.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Transactions (with splits)
# ---------------------------------------------------------------------------

def get_acct_transactions(entity_id: int | None = None, account_id: int | None = None,
                          category_id: int | None = None,
                          start_date: str | None = None, end_date: str | None = None,
                          search: str | None = None, txn_type: str | None = None,
                          acct_status: str | None = None,
                          limit: int = 200, offset: int = 0,
                          db_path: str | Path | None = None) -> dict:
    """Return transactions with their splits. Filters by entity/account/category/date/search."""
    with _connect(db_path) as conn:
        clauses, params = [], []

        if entity_id is not None:
            clauses.append("t.id IN (SELECT transaction_id FROM acct_splits WHERE entity_id = ?)")
            params.append(entity_id)
        if account_id is not None:
            clauses.append("t.account_id = ?")
            params.append(account_id)
        if category_id is not None:
            clauses.append("t.id IN (SELECT transaction_id FROM acct_splits WHERE category_id = ?)")
            params.append(category_id)
        if start_date:
            clauses.append("t.date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("t.date <= ?")
            params.append(end_date)
        if search:
            clauses.append("(t.description LIKE ? OR t.notes LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if txn_type:
            clauses.append("t.type = ?")
            params.append(txn_type)
        if acct_status:
            clauses.append("COALESCE(t.status, 'active') = ?")
            params.append(acct_status)
        else:
            # Default: hide reversed/merged (internal/historical) entries
            clauses.append("COALESCE(t.status, 'active') NOT IN ('reversed', 'merged')")

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        # Get total count for pagination
        count_row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM acct_transactions t{where}", params
        ).fetchone()
        total = count_row["cnt"]

        # Get transactions
        rows = conn.execute(
            f"""SELECT t.*, a.name as account_name, a.account_type as account_type_name,
                       COALESCE(
                           NULLIF(c.company_name, ''),
                           NULLIF(TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')), ''),
                           t.customer
                       ) as customer_name
                FROM acct_transactions t
                LEFT JOIN acct_accounts a ON a.id = t.account_id
                LEFT JOIN customers c ON c.customer_id = t.customer_id
                {where}
                ORDER BY t.date DESC, t.id DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()

        txns = []
        for r in rows:
            txn = dict(r)
            # Attach splits
            splits = conn.execute(
                """SELECT s.*, e.short_name as entity_name, e.color as entity_color,
                          c.name as category_name,
                          ev.item_name as event_name
                   FROM acct_splits s
                   LEFT JOIN acct_entities e ON e.id = s.entity_id
                   LEFT JOIN acct_categories c ON c.id = s.category_id
                   LEFT JOIN events ev ON ev.id = s.event_id
                   WHERE s.transaction_id = ?
                   ORDER BY s.id""",
                (txn["id"],),
            ).fetchall()
            txn["splits"] = [dict(s) for s in splits]
            # Attach tags
            tags = conn.execute(
                """SELECT t.* FROM acct_tags t
                   JOIN acct_transaction_tags tt ON tt.tag_id = t.id
                   WHERE tt.transaction_id = ?""",
                (txn["id"],),
            ).fetchall()
            txn["tags"] = [dict(tg) for tg in tags]
            txns.append(txn)

    return {"transactions": txns, "total": total, "limit": limit, "offset": offset}


def get_unified_transactions(entity_id: int | None = None, account_id: int | None = None,
                             category_id: int | None = None,
                             start_date: str | None = None, end_date: str | None = None,
                             search: str | None = None, txn_type: str | None = None,
                             source: str | None = None, review_status: str | None = None,
                             ledger_status: str | None = None,
                             limit: int = 200, offset: int = 0,
                             db_path: str | Path | None = None) -> dict:
    """Return both acct_transactions and expense_transactions in a unified list.

    Expense transactions are mapped to a compatible shape with synthetic splits.
    Results are interleaved by date descending with correct pagination.
    """
    # Ledger status pill routing: map UI status to query constraints
    acct_status_filter = None
    if ledger_status == 'pending':
        # Only pending expense_transactions
        include_acct_override = False
        review_status = 'pending'
    elif ledger_status == 'unreconciled':
        include_acct_override = True
        acct_status_filter = 'active'  # active = not yet reconciled/reversed/merged
    elif ledger_status in ('active', 'reconciled', 'reversed', 'merged'):
        include_acct_override = True   # only ledger entries, no expense rows
        acct_status_filter = ledger_status
    else:
        include_acct_override = None  # no override

    with _connect(db_path) as conn:
        # --- Build entity short_name→color lookup ---
        entity_rows = conn.execute(
            "SELECT short_name, color FROM acct_entities WHERE is_active = 1"
        ).fetchall()
        entity_colors = {r["short_name"]: r["color"] for r in entity_rows}

        # --- Determine which sources to include ---
        include_acct = source in (None, "", "manual")
        include_expense = source not in ("manual",)
        if include_acct_override is True:
            include_acct = True
            include_expense = False
        elif include_acct_override is False:
            include_acct = False
        # If source is a specific expense type, only include expense
        if source in ("chase_alert", "venmo", "receipt"):
            include_acct = False
            include_expense = True

        # --- Accounting transactions ---
        acct_txns = []
        acct_total = 0
        if include_acct:
            # Only include acct txns if review_status filter is not set
            # (acct txns don't have review_status)
            if not review_status:
                result = get_acct_transactions(
                    entity_id=entity_id, account_id=account_id,
                    category_id=category_id, start_date=start_date,
                    end_date=end_date, search=search, txn_type=txn_type,
                    acct_status=acct_status_filter,
                    limit=limit + offset,  # fetch enough for merge
                    offset=0, db_path=db_path,
                )
                for t in result["transactions"]:
                    t["_is_expense"] = False
                    t["review_status"] = None
                    t["expense_id"] = None
                    if not t.get("source"):
                        t["source"] = "manual"
                acct_txns = result["transactions"]
                acct_total = result["total"]

        # --- Build suggestion data for expense transactions ---
        suggestion_data = get_expense_suggestions(conn)

        # --- Expense transactions ---
        exp_txns = []
        exp_total = 0
        if include_expense:
            exp_clauses, exp_params = [], []
            if start_date:
                exp_clauses.append("et.transaction_date >= ?")
                exp_params.append(start_date)
            if end_date:
                exp_clauses.append("et.transaction_date <= ?")
                exp_params.append(end_date)
            if source in ("chase_alert", "venmo", "receipt"):
                exp_clauses.append("et.source_type = ?")
                exp_params.append(source)
            if review_status:
                exp_clauses.append("et.review_status = ?")
                exp_params.append(review_status)
            if entity_id is not None:
                # Map entity_id to short_name for text matching
                ent_row = conn.execute(
                    "SELECT short_name FROM acct_entities WHERE id = ?", (entity_id,)
                ).fetchone()
                if ent_row:
                    exp_clauses.append("et.entity = ? COLLATE NOCASE")
                    exp_params.append(ent_row["short_name"])
            if search:
                exp_clauses.append("(et.merchant LIKE ? OR et.notes LIKE ?)")
                exp_params.extend([f"%{search}%", f"%{search}%"])
            if txn_type:
                exp_clauses.append("et.transaction_type = ?")
                exp_params.append(txn_type)
            if account_id is not None:
                # Use account_id FK where backfilled; fallback to text match for legacy rows
                acct_row = conn.execute(
                    "SELECT name, last_four FROM acct_accounts WHERE id = ?", (account_id,)
                ).fetchone()
                if acct_row:
                    if acct_row["last_four"]:
                        exp_clauses.append(
                            "(et.account_id = ? OR (et.account_id IS NULL AND et.account_last4 = ?))"
                        )
                        exp_params.extend([account_id, acct_row["last_four"]])
                    else:
                        exp_clauses.append(
                            "(et.account_id = ? OR (et.account_id IS NULL AND UPPER(et.account_name) = UPPER(?)))"
                        )
                        exp_params.extend([account_id, acct_row["name"]])
                else:
                    exp_clauses.append("1 = 0")  # unknown account → exclude all

            exp_where = (" WHERE " + " AND ".join(exp_clauses)) if exp_clauses else ""

            # Count
            exp_total = conn.execute(
                f"SELECT COUNT(*) as cnt FROM expense_transactions et{exp_where}",
                exp_params,
            ).fetchone()["cnt"]

            # Fetch all matching (expense table is small)
            exp_rows = conn.execute(
                f"""SELECT et.* FROM expense_transactions et{exp_where}
                    ORDER BY et.transaction_date DESC, et.id DESC""",
                exp_params,
            ).fetchall()

            for r in exp_rows:
                r = dict(r)
                ent_name = r.get("entity") or "?"
                merchant = r.get("merchant") or ""

                # Build suggestion for pending expenses
                suggestion = None
                if r.get("review_status") == "pending":
                    suggestion = suggest_for_merchant(merchant, suggestion_data)
                    # Apply suggestion to entity/category if currently empty
                    if suggestion:
                        if not r.get("category") and suggestion.get("category"):
                            ent_name = suggestion.get("entity") or ent_name

                exp_txns.append({
                    "id": f"exp_{r['id']}",
                    "date": r.get("transaction_date"),
                    "description": merchant or "(unknown)",
                    "total_amount": r.get("amount") or 0,
                    "type": r.get("transaction_type") or "expense",
                    "account_id": None,
                    "account_name": r.get("account_name") or (
                        f"...{r['account_last4']}" if r.get("account_last4") else None
                    ),
                    "transfer_to_account_id": None,
                    "notes": r.get("notes"),
                    "receipt_path": None,
                    "source": r.get("source_type"),
                    "source_ref": r.get("email_uid"),
                    "is_reconciled": 0,
                    "created_at": r.get("created_at"),
                    "updated_at": None,
                    "review_status": r.get("review_status"),
                    "expense_id": r["id"],
                    "confidence": r.get("confidence"),
                    "customer_id": r.get("customer_id"),
                    "splits": [{
                        "entity_name": ent_name,
                        "entity_color": entity_colors.get(ent_name, "#6b7280"),
                        "category_name": r.get("category"),
                        "event_name": r.get("event_name"),
                        "amount": r.get("amount") or 0,
                    }],
                    "tags": [],
                    "_is_expense": True,
                    "suggestion": suggestion,
                })

        # --- Cross-table dedup: suppress expense rows already in acct_transactions ---
        # Build a set of (date, amount, source) fingerprints from acct side
        acct_fingerprints = set()
        for t in acct_txns:
            acct_fingerprints.add((
                t.get("date") or "",
                round(float(t.get("total_amount") or 0), 2),
                (t.get("source") or "").lower(),
            ))
        deduped_exp = []
        for t in exp_txns:
            fp = (
                t.get("date") or "",
                round(float(t.get("total_amount") or 0), 2),
                (t.get("source") or "").lower(),
            )
            if fp not in acct_fingerprints:
                deduped_exp.append(t)
        exp_total = len(deduped_exp)

        # --- Merge and paginate ---
        combined = acct_txns + deduped_exp
        combined.sort(key=lambda t: (t.get("date") or "", str(t.get("id") or "")), reverse=True)
        total = acct_total + exp_total
        page = combined[offset:offset + limit]

    return {"transactions": page, "total": total, "limit": limit, "offset": offset}


def get_acct_transaction(txn_id: int, db_path: str | Path | None = None) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            """SELECT t.*, a.name as account_name,
                      COALESCE(NULLIF(c.company_name,''), NULLIF(TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')),'' )) as customer_name
               FROM acct_transactions t
               LEFT JOIN acct_accounts a ON a.id = t.account_id
               LEFT JOIN customers c ON c.customer_id = t.customer_id
               WHERE t.id = ?""",
            (txn_id,),
        ).fetchone()
        if not row:
            return None
        txn = dict(row)
        splits = conn.execute(
            """SELECT s.*, e.short_name as entity_name, e.color as entity_color,
                      c.name as category_name
               FROM acct_splits s
               LEFT JOIN acct_entities e ON e.id = s.entity_id
               LEFT JOIN acct_categories c ON c.id = s.category_id
               WHERE s.transaction_id = ? ORDER BY s.id""",
            (txn_id,),
        ).fetchall()
        txn["splits"] = [dict(s) for s in splits]
        tags = conn.execute(
            """SELECT t.* FROM acct_tags t
               JOIN acct_transaction_tags tt ON tt.tag_id = t.id
               WHERE tt.transaction_id = ?""",
            (txn_id,),
        ).fetchall()
        txn["tags"] = [dict(tg) for tg in tags]
        order_split_rows = conn.execute(
            "SELECT split_type, SUM(amount) as amount FROM godaddy_order_splits WHERE transaction_id = ? GROUP BY split_type",
            (txn_id,),
        ).fetchall()
        txn["order_splits"] = {r["split_type"]: r["amount"] for r in order_split_rows}
    return txn


def _create_acct_ledger_entry(date: str, description: str, total_amount: float,
                            txn_type: str, account_id: int | None = None,
                            transfer_to_account_id: int | None = None,
                            notes: str | None = None, receipt_path: str | None = None,
                            source: str = "manual", source_ref: str | None = None,
                            splits: list[dict] | None = None,
                            tag_ids: list[int] | None = None,
                            customer_id: int | None = None,
                            db_path: str | Path | None = None) -> dict:
    """Create a transaction with splits. Each split: {entity_id, category_id, amount, memo}."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO acct_transactions
               (date, description, total_amount, type, account_id, transfer_to_account_id,
                notes, receipt_path, source, source_ref, customer_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (date, description, total_amount, txn_type, account_id,
             transfer_to_account_id, notes, receipt_path, source, source_ref, customer_id),
        )
        txn_id = cur.lastrowid

        if splits:
            for sp in splits:
                conn.execute(
                    "INSERT INTO acct_splits (transaction_id, entity_id, category_id, amount, memo, event_id) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (txn_id, sp["entity_id"], sp.get("category_id"), sp["amount"], sp.get("memo"), sp.get("event_id")),
                )

        if tag_ids:
            for tid in tag_ids:
                try:
                    conn.execute(
                        "INSERT INTO acct_transaction_tags (transaction_id, tag_id) VALUES (?, ?)",
                        (txn_id, tid),
                    )
                except sqlite3.IntegrityError:
                    pass

        conn.commit()
    return get_acct_transaction(txn_id, db_path)


def update_acct_transaction(txn_id: int, db_path: str | Path | None = None, **kwargs) -> dict:
    """Update transaction fields and optionally replace splits and tags."""
    splits = kwargs.pop("splits", None)
    tag_ids = kwargs.pop("tag_ids", None)

    allowed = {"date", "description", "total_amount", "type", "account_id",
               "transfer_to_account_id", "notes", "receipt_path", "is_reconciled", "customer_id"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}

    with _connect(db_path) as conn:
        if updates:
            updates["updated_at"] = datetime.utcnow().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE acct_transactions SET {set_clause} WHERE id = ?",
                (*updates.values(), txn_id),
            )

        if splits is not None:
            conn.execute("DELETE FROM acct_splits WHERE transaction_id = ?", (txn_id,))
            for sp in splits:
                conn.execute(
                    "INSERT INTO acct_splits (transaction_id, entity_id, category_id, amount, memo, event_id) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (txn_id, sp["entity_id"], sp.get("category_id"), sp["amount"], sp.get("memo"), sp.get("event_id")),
                )

        if tag_ids is not None:
            conn.execute("DELETE FROM acct_transaction_tags WHERE transaction_id = ?", (txn_id,))
            for tid in tag_ids:
                try:
                    conn.execute(
                        "INSERT INTO acct_transaction_tags (transaction_id, tag_id) VALUES (?, ?)",
                        (txn_id, tid),
                    )
                except sqlite3.IntegrityError:
                    pass

        conn.commit()
    return get_acct_transaction(txn_id, db_path)


def delete_acct_transaction(txn_id: int, db_path: str | Path | None = None) -> bool:
    with _connect(db_path) as conn:
        # Enable FK cascade for this connection
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM acct_transactions WHERE id = ?", (txn_id,))
        conn.commit()
    return True


def reconcile_acct_transaction(txn_id: int, reconciled: bool = True,
                               db_path: str | Path | None = None) -> dict:
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE acct_transactions SET is_reconciled = ?, updated_at = datetime('now') WHERE id = ?",
            (1 if reconciled else 0, txn_id),
        )
        conn.commit()
    return get_acct_transaction(txn_id, db_path)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

def get_acct_tags(db_path: str | Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM acct_tags ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def create_acct_tag(name: str, color: str = "#6b7280",
                    db_path: str | Path | None = None) -> dict:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO acct_tags (name, color) VALUES (?, ?)", (name, color),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM acct_tags WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def delete_acct_tag(tag_id: int, db_path: str | Path | None = None) -> bool:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM acct_transaction_tags WHERE tag_id = ?", (tag_id,))
        conn.execute("DELETE FROM acct_tags WHERE id = ?", (tag_id,))
        conn.commit()
    return True


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def get_acct_summary(entity_id: int | None = None,
                     start_date: str | None = None, end_date: str | None = None,
                     db_path: str | Path | None = None) -> dict:
    """P&L summary: total income, expenses, net, by category."""
    with _connect(db_path) as conn:
        clauses, params = [], []
        if start_date:
            clauses.append("t.date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("t.date <= ?")
            params.append(end_date)
        if entity_id is not None:
            clauses.append("s.entity_id = ?")
            params.append(entity_id)

        where = (" AND " + " AND ".join(clauses)) if clauses else ""

        # Income by category
        income_rows = conn.execute(
            f"""SELECT c.name as category, COALESCE(SUM(s.amount), 0) as total
                FROM acct_splits s
                JOIN acct_transactions t ON t.id = s.transaction_id
                LEFT JOIN acct_categories c ON c.id = s.category_id
                WHERE t.type = 'income'{where}
                GROUP BY c.name ORDER BY total DESC""",
            params,
        ).fetchall()

        # Expense by category
        expense_rows = conn.execute(
            f"""SELECT c.name as category, COALESCE(SUM(s.amount), 0) as total
                FROM acct_splits s
                JOIN acct_transactions t ON t.id = s.transaction_id
                LEFT JOIN acct_categories c ON c.id = s.category_id
                WHERE t.type = 'expense'{where}
                GROUP BY c.name ORDER BY total DESC""",
            params,
        ).fetchall()

        total_income = sum(r["total"] for r in income_rows)
        total_expenses = sum(r["total"] for r in expense_rows)

    return {
        "total_income": round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "net": round(total_income - total_expenses, 2),
        "income_by_category": [dict(r) for r in income_rows],
        "expense_by_category": [dict(r) for r in expense_rows],
    }


def get_acct_monthly_totals(entity_id: int | None = None, months: int = 12,
                            db_path: str | Path | None = None) -> list[dict]:
    """Monthly income/expense totals for charting."""
    with _connect(db_path) as conn:
        entity_clause = ""
        params: list = []
        if entity_id is not None:
            entity_clause = "AND s.entity_id = ?"
            params.append(entity_id)

        rows = conn.execute(
            f"""SELECT strftime('%Y-%m', t.date) as month,
                       SUM(CASE WHEN t.type = 'income' THEN s.amount ELSE 0 END) as income,
                       SUM(CASE WHEN t.type = 'expense' THEN s.amount ELSE 0 END) as expenses
                FROM acct_splits s
                JOIN acct_transactions t ON t.id = s.transaction_id
                WHERE t.type IN ('income', 'expense')
                  AND t.date >= date('now', '-' || ? || ' months')
                  {entity_clause}
                GROUP BY month ORDER BY month""",
            [months] + params,
        ).fetchall()

    return [{"month": r["month"],
             "income": round(r["income"], 2),
             "expenses": round(r["expenses"], 2),
             "net": round(r["income"] - r["expenses"], 2)} for r in rows]


def get_acct_category_breakdown(entity_id: int | None = None, txn_type: str = "expense",
                                start_date: str | None = None, end_date: str | None = None,
                                db_path: str | Path | None = None) -> list[dict]:
    """Category breakdown for pie/bar charts."""
    with _connect(db_path) as conn:
        clauses, params = ["t.type = ?"], [txn_type]
        if entity_id is not None:
            clauses.append("s.entity_id = ?")
            params.append(entity_id)
        if start_date:
            clauses.append("t.date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("t.date <= ?")
            params.append(end_date)
        where = " AND ".join(clauses)

        rows = conn.execute(
            f"""SELECT c.id as category_id, COALESCE(c.name, 'Uncategorized') as category,
                       SUM(s.amount) as total, COUNT(*) as count
                FROM acct_splits s
                JOIN acct_transactions t ON t.id = s.transaction_id
                LEFT JOIN acct_categories c ON c.id = s.category_id
                WHERE {where}
                GROUP BY c.id ORDER BY total DESC""",
            params,
        ).fetchall()

    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# CSV Import
# ---------------------------------------------------------------------------

def preview_acct_csv(csv_text: str, db_path: str | Path | None = None, **overrides) -> dict:
    """Parse CSV text, auto-detect column mapping from headers, return preview rows + mapping.

    Recognises common bank export formats (Chase, Amex, Wells Fargo, generic).
    Returns {"headers": [...], "mapping": {...}, "rows": [...], "count": N}.
    """
    import csv
    import io

    reader = csv.reader(io.StringIO(csv_text))
    all_rows = list(reader)
    if not all_rows:
        return {"headers": [], "mapping": {}, "rows": [], "count": 0}

    # ── Auto-detect header row ──
    # Heuristic: first row is a header if it contains common keywords
    _DATE_KW = {"date", "transaction date", "trans date", "post date", "posting date", "posted date"}
    _DESC_KW = {"description", "memo", "details", "payee", "name", "merchant", "narrative", "transaction description"}
    _AMT_KW = {"amount", "debit", "credit", "total", "value", "sum", "transaction amount"}
    _CAT_KW = {"category", "type", "class", "group"}
    _MEMO_KW = {"memo", "note", "notes", "reference", "check", "check or slip #"}

    header_lower = [h.strip().lower() for h in all_rows[0]]
    has_header = any(h in _DATE_KW | _DESC_KW | _AMT_KW for h in header_lower)

    if has_header:
        headers = [h.strip() for h in all_rows[0]]
        data_rows = all_rows[1:]
    else:
        headers = [f"Column {i+1}" for i in range(len(all_rows[0]))]
        data_rows = all_rows

    # ── Auto-map columns ──
    mapping = {"date": None, "description": None, "amount": None, "category": None, "memo": None}

    for i, h in enumerate(header_lower if has_header else []):
        if mapping["date"] is None and h in _DATE_KW:
            mapping["date"] = i
        elif mapping["description"] is None and h in _DESC_KW:
            mapping["description"] = i
        elif mapping["amount"] is None and h in _AMT_KW:
            mapping["amount"] = i
        elif mapping["category"] is None and h in _CAT_KW:
            mapping["category"] = i
        elif mapping["memo"] is None and h in _MEMO_KW:
            mapping["memo"] = i

    # Fallback: if we didn't match by keyword, try smart guessing
    if mapping["date"] is None:
        # First column with date-like values
        for i in range(len(headers)):
            sample = data_rows[0][i] if data_rows and i < len(data_rows[0]) else ""
            if re.match(r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}", sample.strip()):
                mapping["date"] = i
                break

    if mapping["amount"] is None:
        # First column with numeric/currency values
        for i in range(len(headers)):
            sample = data_rows[0][i] if data_rows and i < len(data_rows[0]) else ""
            cleaned = sample.strip().replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
            try:
                float(cleaned)
                mapping["amount"] = i
            except ValueError:
                continue

    if mapping["description"] is None:
        # Longest string column that isn't date or amount
        taken = {mapping["date"], mapping["amount"]}
        best_i, best_len = None, 0
        for i in range(len(headers)):
            if i in taken:
                continue
            sample = data_rows[0][i] if data_rows and i < len(data_rows[0]) else ""
            if len(sample.strip()) > best_len:
                best_i, best_len = i, len(sample.strip())
        mapping["description"] = best_i

    # Allow caller overrides
    for k in ("date", "description", "amount", "category", "memo"):
        key = f"{k}_col"
        if key in overrides and overrides[key] is not None:
            mapping[k] = int(overrides[key])

    # ── Parse rows ──
    date_idx = mapping.get("date")
    desc_idx = mapping.get("description")
    amt_idx = mapping.get("amount")
    cat_idx = mapping.get("category")
    memo_idx = mapping.get("memo")

    preview = []
    for i, row in enumerate(data_rows):
        if not row or all(c.strip() == "" for c in row):
            continue

        # Date
        raw_date = row[date_idx].strip() if date_idx is not None and date_idx < len(row) else ""
        if not raw_date:
            continue
        # Normalise date to YYYY-MM-DD
        parsed_date = _normalise_csv_date(raw_date)
        if not parsed_date:
            continue

        # Amount
        raw_amount = row[amt_idx].strip().replace("$", "").replace(",", "") if amt_idx is not None and amt_idx < len(row) else ""
        raw_amount = raw_amount.replace("(", "-").replace(")", "")
        try:
            amount_val = float(raw_amount)
        except ValueError:
            continue
        is_expense = amount_val < 0
        amount = abs(amount_val)
        if amount == 0:
            continue

        # Description
        desc = row[desc_idx].strip() if desc_idx is not None and desc_idx < len(row) else "(no description)"

        # Category (optional)
        cat = row[cat_idx].strip() if cat_idx is not None and cat_idx < len(row) else ""

        # Memo (optional)
        memo = row[memo_idx].strip() if memo_idx is not None and memo_idx < len(row) else ""

        # ── Smart type classification ──
        # Detect transfers (credit card payments, account transfers, etc.)
        desc_upper = desc.upper()
        txn_type = "expense" if is_expense else "income"

        _TRANSFER_PATTERNS = (
            "AUTOMATIC PAYMENT", "AUTOPAY", "AUTO PAY", "ONLINE PAYMENT",
            "PAYMENT THANK YOU", "PAYMENT - THANK", "MOBILE PAYMENT",
            "ONLINE TRANSFER", "TRANSFER TO", "TRANSFER FROM",
            "FUNDS TRANSFER", "WIRE TRANSFER", "ACH TRANSFER",
            "VENMO CASHOUT", "PAYPAL TRANSFER", "ZELLE",
            "CREDIT CARD PAYMENT", "BALANCE TRANSFER",
        )
        is_transfer = any(p in desc_upper for p in _TRANSFER_PATTERNS)

        # Also check the Category column if present (Chase uses "Payment" category)
        if cat and cat.lower() in ("payment", "transfer", "credit card payment"):
            is_transfer = True

        if is_transfer:
            txn_type = "transfer"

        preview.append({
            "row": i + (2 if has_header else 1),
            "date": parsed_date,
            "description": desc,
            "amount": round(amount, 2),
            "type": txn_type,
            "category": cat,
            "memo": memo,
        })

    return {
        "headers": headers,
        "mapping": {k: v for k, v in mapping.items() if v is not None},
        "rows": preview,
        "count": len(preview),
        "has_header": has_header,
    }


def _normalise_csv_date(raw: str) -> str | None:
    """Try to parse various date formats into YYYY-MM-DD."""
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y",
                "%d/%m/%Y", "%Y/%m/%d", "%m.%d.%Y", "%m.%d.%y"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def import_acct_csv(rows: list[dict], account_id: int, default_entity_id: int,
                    transfer_account_id: int | None = None,
                    db_path: str | Path | None = None) -> dict:
    """Bulk-import transactions from pre-parsed CSV rows.

    Each row: {date, description, amount, type, category?, memo?}.
    For transfers: if transfer_account_id is set, links them.
    Also checks for existing matching transfers to avoid duplicates.
    Returns {"imported": N, "matched": N, "skipped": N}.
    """
    imported = 0
    matched = 0
    skipped = 0

    for row in rows:
        txn_type = row.get("type", "expense")
        amount = float(row["amount"])

        if txn_type == "transfer":
            # Check if the other side of this transfer already exists
            existing = _find_matching_transfer(
                amount=amount,
                date=row["date"],
                account_id=account_id,
                db_path=db_path,
            )
            if existing:
                # Link the existing transaction to this account
                _link_transfer_accounts(
                    txn_id=existing["id"],
                    account_id=account_id,
                    this_is_source=existing["account_id"] != account_id,
                    db_path=db_path,
                )
                matched += 1
                continue

            # Create new transfer with account linkage
            _create_acct_ledger_entry(
                date=row["date"],
                description=row["description"],
                total_amount=amount,
                txn_type="transfer",
                account_id=account_id,
                transfer_to_account_id=transfer_account_id,
                notes=row.get("memo") or None,
                source="csv_import",
                splits=[{"entity_id": default_entity_id, "amount": amount}],
                db_path=db_path,
            )
        else:
            _create_acct_ledger_entry(
                date=row["date"],
                description=row["description"],
                total_amount=amount,
                txn_type=txn_type,
                account_id=account_id,
                notes=row.get("memo") or None,
                source="csv_import",
                splits=[{"entity_id": default_entity_id, "amount": amount}],
                db_path=db_path,
            )
        imported += 1

    return {"imported": imported, "matched": matched, "skipped": skipped}


def _find_matching_transfer(amount: float, date: str,
                            account_id: int,
                            db_path: str | Path | None = None) -> dict | None:
    """Find an existing transfer transaction that matches this one.

    Matches by: same amount, type='transfer', within 5 days, and either
    has no second account linked yet or the second account is this account.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM acct_transactions
               WHERE type = 'transfer'
                 AND ABS(total_amount - ?) < 0.01
                 AND ABS(julianday(date) - julianday(?)) <= 5
                 AND account_id != ?
                 AND (transfer_to_account_id IS NULL OR transfer_to_account_id = ?)
               ORDER BY ABS(julianday(date) - julianday(?))
               LIMIT 1""",
            (amount, date, account_id, account_id, date),
        ).fetchall()
    return dict(rows[0]) if rows else None


def _link_transfer_accounts(txn_id: int, account_id: int, this_is_source: bool,
                            db_path: str | Path | None = None) -> None:
    """Link the second account to an existing transfer transaction."""
    with _connect(db_path) as conn:
        if this_is_source:
            # This account is the source (money leaving) — set as account_id
            # and move the existing account_id to transfer_to
            existing = conn.execute(
                "SELECT account_id FROM acct_transactions WHERE id = ?", (txn_id,)
            ).fetchone()
            conn.execute(
                """UPDATE acct_transactions
                   SET transfer_to_account_id = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (account_id, txn_id),
            )
        else:
            # This account is the destination — set transfer_to_account_id
            conn.execute(
                """UPDATE acct_transactions
                   SET transfer_to_account_id = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (account_id, txn_id),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Recurring Transactions
# ---------------------------------------------------------------------------

def get_acct_recurring(db_path: str | Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT r.*, e.short_name as entity_name, c.name as category_name,
                      a.name as account_name
               FROM acct_recurring r
               LEFT JOIN acct_entities e ON e.id = r.entity_id
               LEFT JOIN acct_categories c ON c.id = r.category_id
               LEFT JOIN acct_accounts a ON a.id = r.account_id
               WHERE r.is_active = 1 ORDER BY r.next_date"""
        ).fetchall()
    return [dict(r) for r in rows]


def create_acct_recurring(description: str, amount: float, txn_type: str,
                          entity_id: int, frequency: str, next_date: str,
                          category_id: int | None = None, account_id: int | None = None,
                          db_path: str | Path | None = None) -> dict:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO acct_recurring
               (description, amount, type, entity_id, category_id, account_id, frequency, next_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (description, amount, txn_type, entity_id, category_id, account_id, frequency, next_date),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM acct_recurring WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def delete_acct_recurring(rec_id: int, db_path: str | Path | None = None) -> bool:
    with _connect(db_path) as conn:
        conn.execute("UPDATE acct_recurring SET is_active = 0 WHERE id = ?", (rec_id,))
        conn.commit()
    return True


def process_acct_recurring(db_path: str | Path | None = None) -> int:
    """Create transactions for any recurring entries whose next_date has passed."""
    from dateutil.relativedelta import relativedelta
    today = datetime.now().strftime("%Y-%m-%d")
    created = 0
    with _connect(db_path) as conn:
        due = conn.execute(
            "SELECT * FROM acct_recurring WHERE is_active = 1 AND next_date <= ?",
            (today,),
        ).fetchall()

    for rec in due:
        _create_acct_ledger_entry(
            date=rec["next_date"],
            description=rec["description"],
            total_amount=rec["amount"],
            txn_type=rec["type"],
            account_id=rec["account_id"],
            source="recurring",
            source_ref=str(rec["id"]),
            splits=[{"entity_id": rec["entity_id"], "category_id": rec["category_id"],
                     "amount": rec["amount"]}],
            db_path=db_path,
        )
        # Advance next_date
        current = datetime.strptime(rec["next_date"], "%Y-%m-%d")
        freq = rec["frequency"]
        if freq == "weekly":
            nxt = current + timedelta(weeks=1)
        elif freq == "biweekly":
            nxt = current + timedelta(weeks=2)
        elif freq == "monthly":
            nxt = current + relativedelta(months=1)
        elif freq == "quarterly":
            nxt = current + relativedelta(months=3)
        elif freq == "yearly":
            nxt = current + relativedelta(years=1)
        else:
            nxt = current + relativedelta(months=1)
        with _connect(db_path) as conn:
            conn.execute(
                "UPDATE acct_recurring SET next_date = ? WHERE id = ?",
                (nxt.strftime("%Y-%m-%d"), rec["id"]),
            )
            conn.commit()
        created += 1
    return created


# ═══════════════════════════════════════════════════════════════════════════
# AI Bookkeeper — Auto-categorization & Review Queue
# ═══════════════════════════════════════════════════════════════════════════

def get_expense_suggestions(conn) -> dict:
    """Build merchant→suggestion map for expense transactions.

    Sources (in priority order):
    1. Past approved/corrected expense transactions (exact merchant match)
    2. User-defined keyword rules (contains/starts_with/exact)
    3. Vendor history from acct_transactions (exact + prefix match)

    Returns: {UPPER_MERCHANT: {category, entity, confidence, source}}
    """
    suggestions = {}  # UPPER(merchant) → suggestion

    # Source 1: Past approved expenses — highest priority (direct learning)
    approved = conn.execute(
        """SELECT UPPER(TRIM(merchant)) as vendor, category, entity,
                  COUNT(*) as cnt
           FROM expense_transactions
           WHERE review_status IN ('approved', 'corrected')
             AND category IS NOT NULL AND category != ''
           GROUP BY UPPER(TRIM(merchant)), category, entity
           ORDER BY cnt DESC"""
    ).fetchall()
    for r in approved:
        v = r["vendor"]
        if v and v not in suggestions:
            suggestions[v] = {
                "category": r["category"],
                "entity": r["entity"],
                "confidence": "learned",
                "source": f"approved {r['cnt']}x",
            }

    # Source 2: Keyword rules
    rules = conn.execute(
        """SELECT kr.keyword, kr.match_type,
                  c.name as category_name, c.type as category_type,
                  e.short_name as entity_name
           FROM acct_keyword_rules kr
           LEFT JOIN acct_categories c ON c.id = kr.category_id
           LEFT JOIN acct_entities e ON e.id = kr.entity_id
           WHERE kr.is_active = 1"""
    ).fetchall()
    kw_rules = [dict(r) for r in rules]

    # Source 3: Vendor history from acct_transactions
    vendor_rows = conn.execute(
        """SELECT UPPER(TRIM(t.description)) as vendor,
                  c.name as category_name, e.short_name as entity_name,
                  COUNT(*) as cnt
           FROM acct_transactions t
           JOIN acct_splits s ON s.transaction_id = t.id
           LEFT JOIN acct_categories c ON c.id = s.category_id
           LEFT JOIN acct_entities e ON e.id = s.entity_id
           WHERE s.category_id IS NOT NULL
           GROUP BY UPPER(TRIM(t.description)), c.name, e.short_name
           ORDER BY cnt DESC"""
    ).fetchall()
    for r in vendor_rows:
        v = r["vendor"]
        if v and v not in suggestions:
            suggestions[v] = {
                "category": r["category_name"],
                "entity": r["entity_name"],
                "confidence": "history",
                "source": f"matched {r['cnt']}x",
            }

    return {"exact": suggestions, "keyword_rules": kw_rules}


def suggest_for_merchant(merchant: str, suggestion_data: dict) -> dict | None:
    """Look up suggestion for a specific merchant using pre-built suggestion data."""
    if not merchant:
        return None
    m_upper = merchant.strip().upper()

    # 1. Exact match from approved expenses or vendor history
    if m_upper in suggestion_data["exact"]:
        return suggestion_data["exact"][m_upper]

    # 2. Keyword rules
    for kr in suggestion_data["keyword_rules"]:
        kw = kr["keyword"].upper()
        mt = kr.get("match_type", "contains")
        if mt == "exact" and m_upper == kw:
            return {"category": kr["category_name"], "entity": kr["entity_name"],
                    "confidence": "rule", "source": f"rule: {kr['keyword']}"}
        elif mt == "starts_with" and m_upper.startswith(kw):
            return {"category": kr["category_name"], "entity": kr["entity_name"],
                    "confidence": "rule", "source": f"rule: {kr['keyword']}"}
        elif mt == "contains" and kw in m_upper:
            return {"category": kr["category_name"], "entity": kr["entity_name"],
                    "confidence": "rule", "source": f"rule: {kr['keyword']}"}

    # 3. Prefix match from exact suggestions (first 12 chars)
    prefix = m_upper[:12] if len(m_upper) >= 12 else m_upper.split()[0] if m_upper else ""
    if len(prefix) >= 4:
        for v, sug in suggestion_data["exact"].items():
            if v.startswith(prefix):
                return {**sug, "confidence": "similar",
                        "source": f"similar to '{v[:30]}'"}

    return None


def _get_category_rules(db_path: str | Path | None = None) -> list[dict]:
    """Return learned vendor→category mappings from past categorisations."""
    with _connect(db_path) as conn:
        # Learn from existing categorised transactions: group by description pattern → category
        rows = conn.execute(
            """SELECT UPPER(TRIM(t.description)) as vendor,
                      s.category_id, c.name as category_name, c.type as category_type,
                      s.entity_id, e.short_name as entity_name,
                      COUNT(*) as times_used
               FROM acct_transactions t
               JOIN acct_splits s ON s.transaction_id = t.id
               LEFT JOIN acct_categories c ON c.id = s.category_id
               LEFT JOIN acct_entities e ON e.id = s.entity_id
               WHERE s.category_id IS NOT NULL
               GROUP BY UPPER(TRIM(t.description)), s.category_id, s.entity_id
               ORDER BY times_used DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def auto_categorize_transactions(descriptions: list[str],
                                 txn_types: list[str] | None = None,
                                 db_path: str | Path | None = None) -> list[dict]:
    """Auto-categorize transaction descriptions using learned rules + AI.

    Returns a list of suggestions: [{description, category_id, category_name,
    entity_id, entity_name, confidence, source}].

    Strategy:
    1. Exact vendor match from past categorisations (confidence: "high")
    2. Fuzzy vendor match — same vendor prefix (confidence: "medium")
    3. User-defined keyword rules (confidence: "rule")
    4. Claude AI classification (confidence: "ai")
    """
    rules = _get_category_rules(db_path)
    keyword_rules = get_acct_keyword_rules(db_path=db_path)
    keyword_rules = [kr for kr in keyword_rules if kr.get("is_active")]
    categories = get_acct_categories(db_path=db_path)
    entities = get_all_acct_entities(db_path=db_path)

    results = []
    ai_batch = []  # descriptions needing AI help

    for i, desc in enumerate(descriptions):
        desc_upper = desc.strip().upper()
        txn_type = (txn_types[i] if txn_types and i < len(txn_types) else "expense")

        # Skip transfers — they don't need categories
        if txn_type == "transfer":
            results.append({
                "description": desc, "category_id": None, "category_name": None,
                "entity_id": None, "entity_name": None,
                "confidence": "skip", "source": "transfer",
            })
            continue

        # 1. Exact match
        exact = [r for r in rules if r["vendor"] == desc_upper]
        if exact:
            best = max(exact, key=lambda r: r["times_used"])
            results.append({
                "description": desc,
                "category_id": best["category_id"],
                "category_name": best["category_name"],
                "entity_id": best["entity_id"],
                "entity_name": best["entity_name"],
                "confidence": "high",
                "source": f"matched {best['times_used']}x",
            })
            continue

        # 2. Prefix match (first 10+ chars or first word)
        prefix = desc_upper[:12] if len(desc_upper) >= 12 else desc_upper.split()[0] if desc_upper else ""
        prefix_matches = [r for r in rules if r["vendor"].startswith(prefix) and len(prefix) >= 4]
        if prefix_matches:
            best = max(prefix_matches, key=lambda r: r["times_used"])
            results.append({
                "description": desc,
                "category_id": best["category_id"],
                "category_name": best["category_name"],
                "entity_id": best["entity_id"],
                "entity_name": best["entity_name"],
                "confidence": "medium",
                "source": f"similar to '{best['vendor'][:30]}'",
            })
            continue

        # 3. User-defined keyword rules
        kw_match = None
        for kr in keyword_rules:
            kw = kr["keyword"].upper()
            mt = kr.get("match_type", "contains")
            if mt == "exact" and desc_upper == kw:
                kw_match = kr
                break
            elif mt == "starts_with" and desc_upper.startswith(kw):
                kw_match = kr
                break
            elif mt == "contains" and kw in desc_upper:
                kw_match = kr
                break
        if kw_match:
            results.append({
                "description": desc,
                "category_id": kw_match["category_id"],
                "category_name": kw_match["category_name"],
                "entity_id": kw_match["entity_id"],
                "entity_name": kw_match["entity_name"],
                "confidence": "rule",
                "source": f"keyword rule: '{kw_match['keyword']}'",
            })
            continue

        # 4. Queue for AI
        ai_batch.append((i, desc, txn_type))
        results.append(None)  # placeholder

    # ── AI batch categorization ──
    if ai_batch:
        ai_results = _ai_categorize_batch(
            [(desc, ttype) for _, desc, ttype in ai_batch],
            categories, entities, db_path,
        )
        for j, (idx, desc, _) in enumerate(ai_batch):
            if j < len(ai_results) and ai_results[j]:
                results[idx] = ai_results[j]
                results[idx]["description"] = desc
            else:
                results[idx] = {
                    "description": desc, "category_id": None, "category_name": None,
                    "entity_id": None, "entity_name": None,
                    "confidence": "none", "source": "uncategorized",
                }

    return results


def _ai_categorize_batch(items: list[tuple[str, str]],
                         categories: list[dict], entities: list[dict],
                         db_path: str | Path | None = None,
                         account_context: str | None = None) -> list[dict]:
    """Use Claude to categorize a batch of transactions.

    Includes event context from the events directory and account-level
    heuristics so the AI knows which account typically maps to which entity.
    """
    if not items:
        return []

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return [None] * len(items)

    # Build category and entity lists for the prompt
    expense_cats = [c for c in categories if c["type"] == "expense" and c["is_active"]]
    income_cats = [c for c in categories if c["type"] == "income" and c["is_active"]]

    cat_list = "EXPENSE CATEGORIES:\n" + "\n".join(
        f"  {c['id']}: {c['name']}" for c in expense_cats
    ) + "\n\nINCOME CATEGORIES:\n" + "\n".join(
        f"  {c['id']}: {c['name']}" for c in income_cats
    )

    entity_list = "\n".join(f"  {e['id']}: {e['name']} ({e['short_name']})" for e in entities)

    # Get upcoming/recent events for context
    event_context = ""
    try:
        with _connect(db_path) as conn:
            events = conn.execute(
                """SELECT id, item_name, event_date, course, chapter
                   FROM events
                   WHERE event_date >= date('now', '-60 days')
                   ORDER BY event_date
                   LIMIT 30"""
            ).fetchall()
        if events:
            event_context = "\n\nRECENT/UPCOMING EVENTS (for linking golf expenses):\n" + "\n".join(
                f"  {ev['id']}: {ev['item_name']} at {ev['course'] or '?'} on {ev['event_date'] or '?'} ({ev['chapter'] or ''})"
                for ev in events
            )
    except Exception:
        pass

    # Account-level heuristics
    acct_hint = ""
    if account_context:
        acct_hint = f"\n\nACCOUNT CONTEXT:\n{account_context}"

    # User-defined keyword rules for AI context
    kw_rules_hint = ""
    try:
        kw_rules = get_acct_keyword_rules(db_path=db_path)
        active_kw = [r for r in kw_rules if r.get("is_active")]
        if active_kw:
            kw_rules_hint = "\n\nUSER-DEFINED KEYWORD RULES (MUST follow these):\n" + "\n".join(
                f"  - If description {r['match_type']} '{r['keyword']}' → "
                f"category_id={r['category_id']} ({r['category_name'] or '?'})"
                f"{', entity_id=' + str(r['entity_id']) + ' (' + (r['entity_name'] or '?') + ')' if r['entity_id'] else ''}"
                for r in active_kw
            )
    except Exception:
        pass

    txn_list = "\n".join(
        f"  {i+1}. [{ttype.upper()}] {desc}"
        for i, (desc, ttype) in enumerate(items)
    )

    prompt = f"""You are an expert bookkeeper for a golf fellowship organization (TGF) and personal finances.
Categorize each transaction and optionally link it to a TGF event.

ENTITIES:
{entity_list}

{cat_list}{event_context}{acct_hint}{kw_rules_hint}

TRANSACTIONS TO CATEGORIZE:
{txn_list}

For each transaction, return a JSON array with one object per transaction:
[
  {{"category_id": <number>, "entity_id": <number>, "event_id": <number or null>}},
  ...
]

Rules:
- Match the category to the transaction type (expense categories for expenses, income for income)
- For personal purchases (groceries, restaurants, gas, Amazon, etc.) use Personal entity
- For golf-related expenses (golf courses, event supplies, course fees), use TGF entity
  and set event_id to the closest matching event by course name and date
- Golf course names in transactions often appear as partial matches (e.g. "THE QUARRY GC" = "The Quarry")
- For business services, software, design tools, use the most appropriate business entity
- Only set event_id when you're reasonably confident the expense relates to a specific event
- If truly ambiguous, use entity_id null and category_id null, event_id null
- Return ONLY the JSON array, no other text"""

    try:
        client = _anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        # Extract JSON from response
        if text.startswith("["):
            data = json.loads(text)
        else:
            # Try to find JSON in the response
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                return [None] * len(items)

        results = []
        for j, item in enumerate(data):
            if j >= len(items):
                break
            cat_id = item.get("category_id")
            ent_id = item.get("entity_id")
            evt_id = item.get("event_id")
            cat_name = next((c["name"] for c in categories if c["id"] == cat_id), None) if cat_id else None
            ent_name = next((e["short_name"] for e in entities if e["id"] == ent_id), None) if ent_id else None
            results.append({
                "category_id": cat_id,
                "category_name": cat_name,
                "entity_id": ent_id,
                "entity_name": ent_name,
                "event_id": evt_id,
                "confidence": "ai",
                "source": "AI suggestion",
            })
        return results

    except Exception as e:
        logger.warning("AI categorization failed: %s", e)
        return [None] * len(items)


def get_acct_review_queue(db_path: str | Path | None = None) -> list[dict]:
    """Return transactions that need attention: uncategorized, untagged, or unsplit."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT t.*, a.name as account_name,
                      (SELECT COUNT(*) FROM acct_splits s WHERE s.transaction_id = t.id AND s.category_id IS NOT NULL) as categorized_splits,
                      (SELECT COUNT(*) FROM acct_splits s WHERE s.transaction_id = t.id) as total_splits
               FROM acct_transactions t
               LEFT JOIN acct_accounts a ON a.id = t.account_id
               WHERE t.type != 'transfer'
                 AND t.id NOT IN (
                     SELECT s.transaction_id FROM acct_splits s WHERE s.category_id IS NOT NULL
                 )
               ORDER BY t.date DESC
               LIMIT 100"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_acct_categorization_stats(db_path: str | Path | None = None) -> dict:
    """Return stats about categorization coverage."""
    with _connect(db_path) as conn:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM acct_transactions WHERE type != 'transfer'"
        ).fetchone()["cnt"]
        categorized = conn.execute(
            """SELECT COUNT(DISTINCT t.id) as cnt
               FROM acct_transactions t
               JOIN acct_splits s ON s.transaction_id = t.id
               WHERE s.category_id IS NOT NULL AND t.type != 'transfer'"""
        ).fetchone()["cnt"]
        uncategorized = total - categorized
        pending_expenses = conn.execute(
            "SELECT COUNT(*) as cnt FROM expense_transactions WHERE review_status = 'pending'"
        ).fetchone()["cnt"]
    return {
        "total": total,
        "categorized": categorized,
        "uncategorized": uncategorized,
        "pct": round(categorized / total * 100, 1) if total > 0 else 0,
        "pending_expenses": pending_expenses,
    }


def reset_acct_data(db_path: str | Path | None = None) -> dict:
    """Wipe all accounting data and re-seed entities + categories."""
    with _connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        # Delete in dependency order
        for table in ("acct_transaction_tags", "acct_splits", "acct_transactions",
                      "acct_recurring", "acct_categories", "acct_accounts",
                      "acct_tags", "acct_entities"):
            conn.execute(f"DELETE FROM {table}")

        # Re-seed entities
        conn.executemany(
            "INSERT INTO acct_entities (name, short_name, color) VALUES (?, ?, ?)",
            [
                ("The Golf Fellowship", "TGF", "#16a34a"),
                ("Personal", "Personal", "#2563eb"),
            ],
        )

        # Re-seed categories
        _seed_acct_categories(conn)

        conn.commit()

        cat_count = conn.execute("SELECT COUNT(*) as cnt FROM acct_categories").fetchone()["cnt"]
        ent_count = conn.execute("SELECT COUNT(*) as cnt FROM acct_entities").fetchone()["cnt"]

    return {"entities": ent_count, "categories": cat_count, "message": "All accounting data reset and re-seeded"}


# ═══════════════════════════════════════════════════════════════════════════
# Allocation Tracking — Per-Order Dollar Breakdown
# ═══════════════════════════════════════════════════════════════════════════


def _create_allocation_for_item(
    item: dict,
    conn: sqlite3.Connection,
    payment_method: str,
    override_price: float | None = None,
    create_txn: bool = True,
    txn_description: str | None = None,
    txn_type: str = "income",
    txn_source: str = "unified_financial",
    txn_category_name: str | None = None,
) -> dict:
    """Create an acct_allocations entry for a non-GoDaddy item.

    Generates a synthetic order_id, runs _calc_event_allocation() for bucket
    breakdown, optionally creates an acct_transactions entry, and returns the
    allocation dict.

    Args:
        item: dict with at least id, item_name, item_price, order_date, chapter,
              holes, side_games fields.
        conn: open sqlite3 connection (caller manages the transaction).
        payment_method: one of 'venmo', 'cash', 'zelle', 'check', 'credit_transfer', 'comp'.
        override_price: if set, used as total_collected instead of parsing item_price.
        create_txn: whether to also create an acct_transactions row.
        txn_description: description for the accounting transaction.
        txn_type: 'income' or 'expense' for the acct_transactions row.
        txn_source: source field for the acct_transactions row.
        txn_category_name: name of acct_categories row to look up for the split.

    Returns:
        dict with allocation fields (including id, acct_transaction_id if created).
    """
    item_id = item["id"]
    item_name = item.get("item_name", "")

    # Synthetic order_id based on payment method
    prefix_map = {
        "venmo": "EXT", "cash": "EXT", "zelle": "EXT", "check": "EXT",
        "credit_transfer": "XFER", "comp": "COMP",
    }
    prefix = prefix_map.get(payment_method, "MANUAL-PAY")
    synthetic_order_id = f"{prefix}-{item_id}"

    # Calculate bucket breakdown
    alloc = _calc_event_allocation(item, conn)

    # Determine total collected
    if override_price is not None:
        total_collected = override_price
    else:
        total_collected = _parse_dollar(item.get("item_price")) or 0

    alloc["order_id"] = synthetic_order_id
    alloc["item_id"] = item_id
    alloc["event_name"] = item_name
    alloc["chapter"] = item.get("chapter")
    alloc["allocation_date"] = item.get("order_date")
    alloc["godaddy_fee"] = 0  # no processing fee on non-GoDaddy payments
    alloc["total_collected"] = total_collected
    alloc["tax_reserve"] = round(alloc.get("tgf_operating", 0) * 0.0825, 2)
    alloc["payment_method"] = payment_method

    # Determine status
    if alloc.pop("_needs_course_cost", False):
        alloc["allocation_status"] = "needs_course_cost"
        alloc["notes"] = "Event pricing not configured — course_cost is NULL"
    else:
        alloc["allocation_status"] = "complete"

    # Upsert allocation
    conn.execute(
        """INSERT INTO acct_allocations
           (order_id, item_id, event_name, chapter, allocation_date,
            player_count, course_payable, course_surcharge, prize_pool,
            tgf_operating, godaddy_fee, tax_reserve, total_collected,
            allocation_status, notes, payment_method)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(order_id, item_id) DO UPDATE SET
            event_name=excluded.event_name, chapter=excluded.chapter,
            allocation_date=excluded.allocation_date, player_count=excluded.player_count,
            course_payable=excluded.course_payable, course_surcharge=excluded.course_surcharge,
            prize_pool=excluded.prize_pool, tgf_operating=excluded.tgf_operating,
            godaddy_fee=excluded.godaddy_fee, tax_reserve=excluded.tax_reserve,
            total_collected=excluded.total_collected,
            allocation_status=excluded.allocation_status, notes=excluded.notes,
            payment_method=excluded.payment_method""",
        (synthetic_order_id, item_id, alloc["event_name"], alloc["chapter"],
         alloc["allocation_date"], alloc.get("player_count", 1),
         alloc.get("course_payable", 0), alloc.get("course_surcharge", 0),
         alloc.get("prize_pool", 0), alloc.get("tgf_operating", 0),
         alloc["godaddy_fee"], alloc["tax_reserve"], alloc["total_collected"],
         alloc["allocation_status"], alloc.get("notes"), payment_method),
    )

    # Optionally create accounting transaction
    txn_id = None
    if create_txn and total_collected != 0:
        source_ref = f"{txn_source}-{item_id}"

        # Skip if already exists (idempotent)
        existing = conn.execute(
            "SELECT id FROM acct_transactions WHERE source_ref = ?",
            (source_ref,),
        ).fetchone()
        if not existing:
            # Look up event_id and category_id
            event_row = conn.execute(
                "SELECT id FROM events WHERE item_name = ? COLLATE NOCASE",
                (item_name,),
            ).fetchone()
            event_db_id = event_row["id"] if event_row else None

            category_id = None
            if txn_category_name:
                cat_row = conn.execute(
                    "SELECT id FROM acct_categories WHERE name = ?",
                    (txn_category_name,),
                ).fetchone()
                category_id = cat_row["id"] if cat_row else None

            tgf_entity = conn.execute(
                "SELECT id FROM acct_entities WHERE short_name = 'TGF'"
            ).fetchone()
            tgf_id = tgf_entity["id"] if tgf_entity else 1

            desc = txn_description or f"{payment_method.title()} payment — {item_name}"
            cur = conn.execute(
                """INSERT INTO acct_transactions
                   (date, description, total_amount, type, source, source_ref)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (alloc["allocation_date"] or "", desc,
                 abs(total_collected), txn_type, txn_source, source_ref),
            )
            txn_id = cur.lastrowid

            # Create split linking to event
            conn.execute(
                """INSERT INTO acct_splits
                   (transaction_id, entity_id, category_id, amount, memo, event_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (txn_id, tgf_id, category_id, abs(total_collected),
                 desc, event_db_id),
            )

            # Link allocation to transaction
            conn.execute(
                "UPDATE acct_allocations SET acct_transaction_id = ? WHERE order_id = ? AND item_id = ?",
                (txn_id, synthetic_order_id, item_id),
            )
            alloc["acct_transaction_id"] = txn_id

    return alloc


def calculate_order_allocation(order_id: str, db_path: str | Path | None = None) -> list[dict]:
    """Calculate how each item in a GoDaddy order is allocated across buckets.

    For EVENT items: course_payable, course_surcharge, prize_pool, tgf_operating,
    godaddy_fee, tax_reserve.
    For MEMBERSHIP items: tgf_operating, prize_pool, godaddy_fee, tax_reserve.

    Returns a list of allocation dicts (one per item in the order).
    """
    with _connect(db_path) as conn:
        items = conn.execute(
            """SELECT * FROM items
               WHERE order_id = ? AND COALESCE(transaction_status, 'active') = 'active'
               ORDER BY item_index""",
            (order_id,),
        ).fetchall()

        if not items:
            return []

        items = [dict(i) for i in items]

        # Parse order total (once per order, from first item)
        order_total = _parse_dollar(items[0].get("total_amount"))

        # GoDaddy fee: 2.9% + $0.30 per order (split evenly across items)
        gd_fee_total = round(order_total * 0.029 + 0.30, 2) if order_total else 0
        gd_fee_per_item = round(gd_fee_total / len(items), 2) if items else 0

        results = []
        for item in items:
            item_name = item.get("item_name", "")
            is_membership = "MEMBERSHIP" in item_name.upper()

            if is_membership:
                alloc = _calc_membership_allocation(item, conn)
            else:
                alloc = _calc_event_allocation(item, conn)

            alloc["order_id"] = order_id
            alloc["item_id"] = item["id"]
            alloc["event_name"] = item_name
            alloc["chapter"] = item.get("chapter")
            alloc["allocation_date"] = item.get("order_date")
            alloc["godaddy_fee"] = gd_fee_per_item
            alloc["total_collected"] = _parse_dollar(item.get("item_price")) or 0

            # Tax reserve: 8.25% of TGF operating revenue
            alloc["tax_reserve"] = round(alloc.get("tgf_operating", 0) * 0.0825, 2)

            # Determine status
            if is_membership:
                alloc["allocation_status"] = "complete"
            elif alloc.get("_needs_course_cost"):
                alloc["allocation_status"] = "needs_course_cost"
                alloc["notes"] = "Event pricing not configured — course_cost is NULL"
            else:
                alloc["allocation_status"] = "complete"

            alloc.pop("_needs_course_cost", None)
            results.append(alloc)

        # Upsert allocations
        for alloc in results:
            conn.execute(
                """INSERT INTO acct_allocations
                   (order_id, item_id, event_name, chapter, allocation_date,
                    player_count, course_payable, course_surcharge, prize_pool,
                    tgf_operating, godaddy_fee, tax_reserve, total_collected,
                    allocation_status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(order_id, item_id) DO UPDATE SET
                    event_name=excluded.event_name, chapter=excluded.chapter,
                    allocation_date=excluded.allocation_date, player_count=excluded.player_count,
                    course_payable=excluded.course_payable, course_surcharge=excluded.course_surcharge,
                    prize_pool=excluded.prize_pool, tgf_operating=excluded.tgf_operating,
                    godaddy_fee=excluded.godaddy_fee, tax_reserve=excluded.tax_reserve,
                    total_collected=excluded.total_collected,
                    allocation_status=excluded.allocation_status, notes=excluded.notes""",
                (alloc["order_id"], alloc["item_id"], alloc["event_name"],
                 alloc["chapter"], alloc["allocation_date"], alloc.get("player_count", 1),
                 alloc.get("course_payable", 0), alloc.get("course_surcharge", 0),
                 alloc.get("prize_pool", 0), alloc.get("tgf_operating", 0),
                 alloc["godaddy_fee"], alloc["tax_reserve"], alloc["total_collected"],
                 alloc["allocation_status"], alloc.get("notes")),
            )
        conn.commit()

    return results


def _write_acct_entry(
    conn: sqlite3.Connection,
    *,
    item_id: int | None = None,
    event_name: str = "",
    customer: str = "",
    customer_id: int | None = None,
    order_id: str = "",
    entry_type: str,
    category: str,
    source: str,
    amount: float,
    description: str = "",
    account: str = "TGF Checking",
    source_ref: str = "",
    date: str = "",
    net_deposit: float | None = None,
    merchant_fee: float | None = None,
) -> int | None:
    """Write a single accounting entry to acct_transactions.

    This is the central helper for the single-source-of-truth ledger.
    Uses source_ref for idempotency — skips if an active entry with the
    same source_ref already exists.

    Returns the new row id, or None if skipped (duplicate).
    """
    if source_ref:
        existing = conn.execute(
            "SELECT id FROM acct_transactions WHERE source_ref = ? AND COALESCE(status, 'active') = 'active'",
            (source_ref,),
        ).fetchone()
        if existing:
            return None

    # Resolve customer_id via lookup if not provided
    if customer_id is None and customer:
        customer_id = _lookup_customer_id(conn, customer, None)

    # Map entry_type to legacy 'type' column for backward compat
    legacy_type_map = {"income": "income", "expense": "expense",
                       "contra": "expense", "liability": "expense"}
    legacy_type = legacy_type_map.get(entry_type, "expense")

    cur = conn.execute(
        """INSERT INTO acct_transactions
           (date, description, total_amount, type, source, source_ref,
            item_id, event_name, customer, customer_id, order_id, entry_type, category,
            amount, account, status, net_deposit, merchant_fee)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
        (date, description, abs(amount), legacy_type, source, source_ref,
         item_id, event_name, customer, customer_id, order_id, entry_type, category,
         amount, account, net_deposit, merchant_fee),
    )
    return cur.lastrowid


def _write_godaddy_order_entry(
    conn: sqlite3.Connection,
    *,
    order_id: str,
    items: list[dict],
    date: str = "",
) -> int | None:
    """Create one order-level acct_transaction with godaddy_order_splits.

    Replaces the old pattern of 2 entries per item (income + fee).
    Now creates ONE transaction per GoDaddy order with child splits for:
      - registration income per item (item_price)
      - transaction fee income per item
      - merchant fee expense (proportional per item)
      - coupon discount per item (if coupon_code present)

    Re-entrant: if an order-level entry already exists for this order_id,
    it is soft-deleted (status='reversed') and its splits removed, then
    a fresh entry is created with the current item set.

    Returns the new transaction id, or None if no valid items.
    """
    if not items:
        return None

    # ── Calculate order totals ───────────────────────────────────
    total_item_prices = 0.0
    total_tx_fees = 0.0

    for item in items:
        total_item_prices += _parse_dollar(item.get("item_price"))
        total_tx_fees += _parse_dollar(item.get("transaction_fees"))

    # total_amount on each item row stores the FULL ORDER total (same value
    # on every item in the order).  Use it from the first item only; fall
    # back to the sum of per-item prices + fees when it's missing/zero.
    first_ta = _parse_dollar(items[0].get("total_amount"))
    order_total = first_ta if first_ta > 0 else (total_item_prices + total_tx_fees)

    if order_total <= 0:
        return None

    merchant_fee_val = round(order_total * 0.029 + 0.30, 2)
    net_deposit_val = round(order_total - merchant_fee_val, 2)

    # ── Determine shared event_name and customer ─────────────────
    event_names = list(dict.fromkeys(
        item.get("item_name") or "" for item in items if item.get("item_name")
    ))
    event_name = event_names[0] if event_names else ""

    customers = list(dict.fromkeys(
        item.get("customer") or "" for item in items if item.get("customer")
    ))
    customer_name = customers[0] if customers else ""

    source_ref = f"godaddy-order-{order_id}"

    # ── Re-entrant: soft-delete existing order entry if present ──
    existing = conn.execute(
        "SELECT id FROM acct_transactions WHERE source_ref = ? AND COALESCE(status, 'active') = 'active'",
        (source_ref,),
    ).fetchone()
    if existing:
        old_id = existing[0]
        conn.execute("UPDATE acct_transactions SET status = 'reversed' WHERE id = ?", (old_id,))
        conn.execute("DELETE FROM godaddy_order_splits WHERE transaction_id = ?", (old_id,))

    # ── Create order-level transaction ───────────────────────────
    n_items = len(items)
    desc_parts = [f"{customer_name}"] if len(customers) == 1 else [f"{n_items} players"]
    desc_parts.append(event_name if len(event_names) == 1 else f"{len(event_names)} events")
    description = f"GoDaddy order {order_id}: {' — '.join(desc_parts)}"

    txn_id = _write_acct_entry(
        conn,
        item_id=None,
        event_name=event_name,
        customer=customer_name,
        order_id=order_id,
        entry_type="income",
        category="godaddy_order",
        source="godaddy",
        amount=net_deposit_val,
        description=description,
        account="TGF Checking",
        source_ref=source_ref,
        date=date,
        net_deposit=net_deposit_val,
        merchant_fee=merchant_fee_val,
    )
    if txn_id is None:
        return None

    # ── Create splits ────────────────────────────────────────────
    for item in items:
        item_id = item.get("id")
        item_event = item.get("item_name") or event_name
        item_customer = item.get("customer") or customer_name
        ip = _parse_dollar(item.get("item_price"))
        tf = _parse_dollar(item.get("transaction_fees"))
        item_total = ip + tf  # per-item contribution to order total

        # Registration income split
        if ip > 0:
            conn.execute(
                """INSERT INTO godaddy_order_splits
                   (transaction_id, item_id, event_name, customer, split_type, amount)
                   VALUES (?, ?, ?, ?, 'registration', ?)""",
                (txn_id, item_id, item_event, item_customer, ip),
            )

        # Transaction fee income split
        if tf > 0:
            conn.execute(
                """INSERT INTO godaddy_order_splits
                   (transaction_id, item_id, event_name, customer, split_type, amount)
                   VALUES (?, ?, ?, ?, 'transaction_fee', ?)""",
                (txn_id, item_id, item_event, item_customer, tf),
            )

        # Coupon discount split (contra-revenue, stored as negative)
        coupon_amt = _parse_dollar(item.get("coupon_amount"))
        if coupon_amt > 0 and item.get("coupon_code"):
            conn.execute(
                """INSERT INTO godaddy_order_splits
                   (transaction_id, item_id, event_name, customer, split_type, amount)
                   VALUES (?, ?, ?, ?, 'coupon', ?)""",
                (txn_id, item_id, item_event, item_customer, -coupon_amt),
            )

        # Merchant fee split (proportional by per-item contribution, negative = expense)
        _sum_items = total_item_prices + total_tx_fees
        if item_total > 0 and _sum_items > 0:
            item_merchant_fee = round(merchant_fee_val * item_total / _sum_items, 2)
            conn.execute(
                """INSERT INTO godaddy_order_splits
                   (transaction_id, item_id, event_name, customer, split_type, amount)
                   VALUES (?, ?, ?, ?, 'merchant_fee', ?)""",
                (txn_id, item_id, item_event, item_customer, -item_merchant_fee),
            )

    return txn_id


def _parse_dollar(val, default: float = 0.0) -> float:
    """Safely parse a dollar amount string to float.

    Handles: "$148.00", "$1,234.00", "$0.00 (comp)", "$102.00 (credit)",
    None, "", "0", integers, floats. Always returns a float. Never raises.
    """
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    # Strip everything except digits, dot, and minus sign
    cleaned = re.sub(r'[^\d.\-]', '', str(val))
    if not cleaned or cleaned == '.':
        return default
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return default


# Public alias
parse_dollar = _parse_dollar


def _calc_event_allocation(item: dict, conn: sqlite3.Connection) -> dict:
    """Calculate allocation for an event registration item.

    Uses per-transaction side_games field (NET/GROSS/BOTH/NONE) with exact
    lookup tables, NOT the event-level side_game_fee field.
    """
    # ── Side game lookup tables ──
    # Prize pool portion (not taxable)
    _SIDE_PRIZE = {
        ("NET", "9"): 13, ("NET", "18"): 26,
        ("GROSS", "9"): 13, ("GROSS", "18"): 26,
        ("BOTH", "9"): 26, ("BOTH", "18"): 52,
        ("NONE", "9"): 0, ("NONE", "18"): 0,
    }
    # Markup portion (taxable — goes to tgf_operating)
    _SIDE_MARKUP = {
        ("NET", "9"): 3, ("NET", "18"): 4,
        ("GROSS", "9"): 3, ("GROSS", "18"): 4,
        ("BOTH", "9"): 6, ("BOTH", "18"): 8,
        ("NONE", "9"): 0, ("NONE", "18"): 0,
    }
    # Included game pots (not taxable — goes to prize_pool)
    # 9-hole: $7 ($4 team net + $2 CTP + $1 HIO)
    # 18-hole: $14 ($8 team net + $4 CTP + $2 HIO)

    item_name = item.get("item_name", "")
    holes = item.get("holes", "")
    side_games = (item.get("side_games") or "NONE").strip().upper()

    # Normalise side_games value
    if side_games in ("NET", "GROSS", "BOTH", "NONE"):
        pass
    elif "BOTH" in side_games or ("NET" in side_games and "GROSS" in side_games):
        side_games = "BOTH"
    elif "NET" in side_games:
        side_games = "NET"
    elif "GROSS" in side_games:
        side_games = "GROSS"
    else:
        side_games = "NONE"

    # Look up event pricing
    event = conn.execute(
        "SELECT * FROM events WHERE item_name = ? COLLATE NOCASE",
        (item_name,),
    ).fetchone()

    # Try aliases if no direct match
    if not event:
        alias = conn.execute(
            "SELECT canonical_event_name FROM event_aliases WHERE alias_name = ? COLLATE NOCASE",
            (item_name,),
        ).fetchone()
        if alias:
            event = conn.execute(
                "SELECT * FROM events WHERE item_name = ? COLLATE NOCASE",
                (alias["canonical_event_name"],),
            ).fetchone()

    if not event:
        return {
            "player_count": 1, "course_payable": 0, "course_surcharge": 0,
            "prize_pool": 0, "tgf_operating": 0, "_needs_course_cost": True,
        }

    event = dict(event)

    # Determine if 9-hole or 18-hole
    # Infer from holes field, or from event name (s9.x = 9-hole, s18.x = 18-hole)
    if not holes:
        if "s18." in item_name.lower() or "18" in (event.get("format") or ""):
            holes = "18"
        else:
            holes = "9"
    is_18 = "18" in str(holes)
    hole_key = "18" if is_18 else "9"
    is_combo = "combo" in (event.get("format") or "").lower()

    if is_combo and is_18:
        tgf_markup = event.get("tgf_markup_18") or event.get("tgf_markup")
    elif is_combo:
        tgf_markup = event.get("tgf_markup_9") or event.get("tgf_markup")
    else:
        tgf_markup = event.get("tgf_markup")

    # Determine course cost — prefer breakdown JSON if available
    breakdown_col = ("course_cost_breakdown_18" if (is_combo and is_18) else
                     "course_cost_breakdown_9" if is_combo else
                     "course_cost_breakdown")
    breakdown_json = event.get(breakdown_col)
    if breakdown_json:
        try:
            breakdown = json.loads(breakdown_json)
            course_cost = round(sum(
                v["amount"] * (1 + v["tax_pct"] / 100)
                for v in breakdown.values()
            ), 2)
            surcharge = 0  # absorbed into breakdown
        except (json.JSONDecodeError, KeyError, TypeError):
            course_cost = None
            surcharge = event.get("course_surcharge") or 0
    else:
        # Legacy path — flat course_cost
        if is_combo and is_18:
            course_cost = event.get("course_cost_18") or event.get("course_cost")
        elif is_combo:
            course_cost = event.get("course_cost_9") or event.get("course_cost")
        else:
            course_cost = event.get("course_cost")
        surcharge = event.get("course_surcharge") or 0

    if course_cost is None:
        return {
            "player_count": 1, "course_payable": 0, "course_surcharge": surcharge,
            "prize_pool": 0, "tgf_operating": 0, "_needs_course_cost": True,
        }

    # Lookup side game allocations from tables
    side_prize = _SIDE_PRIZE.get((side_games, hole_key), 0)
    side_markup = _SIDE_MARKUP.get((side_games, hole_key), 0)
    base_pots = 14.0 if is_18 else 7.0

    return {
        "player_count": 1,
        "course_payable": round(course_cost, 2),
        "course_surcharge": round(surcharge, 2),
        "prize_pool": round(base_pots + side_prize, 2),
        "tgf_operating": round((tgf_markup or 0) + side_markup, 2),
        "_needs_course_cost": False,
    }


def _calc_membership_allocation(item: dict, conn: sqlite3.Connection) -> dict:
    """Calculate allocation for a membership item (Task 7).

    Membership pricing:
    - returning_or_new = 'New': $44 taxable
    - returning_or_new = 'Returning': $69 taxable
    - 'Plus' memberships: $244 taxable
    - Contest markup: $10 per contest enrolled
    - Prize pool: $6 Monthly Points Race pool + contest prize pools
    """
    item_name = (item.get("item_name") or "").upper()
    returning_or_new = (item.get("returning_or_new") or "").upper()
    item_price = _parse_dollar(item.get("item_price"))

    # Determine base membership type
    if "PLUS" in item_name or item_price >= 200:
        base_tgf = 244.0
    elif "NEW" in returning_or_new or "1ST" in returning_or_new or "FIRST" in returning_or_new:
        base_tgf = 44.0
    else:
        # Returning / default
        base_tgf = 69.0

    # Count contests — check for contest-related fields
    contest_count = 0
    for field in ("net_points_race", "gross_points_race", "city_match_play"):
        val = (item.get(field) or "").strip().upper()
        if val and val not in ("", "NO", "NONE", "N/A"):
            contest_count += 1

    contest_markup = contest_count * 10.0  # $10 per contest
    contest_prize = contest_count * 20.0   # contest prize pool portion

    # Monthly Points Race pool contribution
    monthly_prize = 6.0

    return {
        "player_count": 1,
        "course_payable": 0,
        "course_surcharge": 0,
        "prize_pool": round(monthly_prize + contest_prize, 2),
        "tgf_operating": round(base_tgf + contest_markup, 2),
        "_needs_course_cost": False,
    }


def get_acct_allocations(month: str | None = None, event: str | None = None,
                         chapter: str | None = None,
                         db_path: str | Path | None = None) -> dict:
    """Return allocation records with totals grouped by bucket.

    Args:
        month: Filter by YYYY-MM (matches allocation_date)
        event: Filter by event_name (partial match)
        chapter: Filter by chapter
    """
    with _connect(db_path) as conn:
        clauses, params = [], []
        if month:
            clauses.append("a.allocation_date LIKE ?")
            params.append(f"{month}%")
        if event:
            clauses.append("a.event_name LIKE ?")
            params.append(f"%{event}%")
        if chapter:
            clauses.append("a.chapter = ?")
            params.append(chapter)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        rows = conn.execute(
            f"""SELECT a.* FROM acct_allocations a{where}
                ORDER BY a.allocation_date DESC, a.id DESC""",
            params,
        ).fetchall()

        # Compute totals
        totals = {
            "course_payable": 0, "course_surcharge": 0, "prize_pool": 0,
            "tgf_operating": 0, "godaddy_fee": 0, "tax_reserve": 0,
            "total_collected": 0, "count": 0,
        }
        records = []
        for r in rows:
            d = dict(r)
            records.append(d)
            for k in ("course_payable", "course_surcharge", "prize_pool",
                       "tgf_operating", "godaddy_fee", "tax_reserve", "total_collected"):
                totals[k] = round(totals[k] + (d.get(k) or 0), 2)
            totals["count"] += 1

    totals["unallocated"] = round(
        totals["total_collected"]
        - totals["course_payable"] - totals["course_surcharge"]
        - totals["prize_pool"] - totals["tgf_operating"]
        - totals["godaddy_fee"] - totals["tax_reserve"], 2
    )

    return {"allocations": records, "totals": totals}


def get_event_financial_summary(event_name: str, db_path: str | Path | None = None) -> dict:
    """Server-side financial summary for one event.

    Primary path: reads from flat acct_transactions entries grouped by event_name
    (single source of truth).  Falls back to allocation-based calculation when
    no flat entries exist.

    Returns a dict with revenue, expenses, profit, player counts, and an
    ``accounting_verified`` flag indicating which path was used.
    """
    with _connect(db_path) as conn:
        # ── Resolve event ──
        event_row = conn.execute(
            "SELECT * FROM events WHERE item_name = ? COLLATE NOCASE",
            (event_name,),
        ).fetchone()
        event = dict(event_row) if event_row else {}
        event_db_id = event.get("id")

        # Also check aliases
        alias_names = [
            r[0] for r in conn.execute(
                "SELECT alias_name FROM event_aliases WHERE canonical_event_name = ? COLLATE NOCASE",
                (event_name,),
            ).fetchall()
        ]
        all_names = [event_name] + alias_names
        name_placeholders = ",".join(["?"] * len(all_names))

        # ── Count items for this event (player context) ──
        all_items = conn.execute(
            f"""SELECT * FROM items
                WHERE item_name COLLATE NOCASE IN ({name_placeholders})
                ORDER BY id""",
            all_names,
        ).fetchall()
        all_items = [dict(r) for r in all_items]

        parent_items = [i for i in all_items if not i.get("parent_item_id")]
        active_parents = [i for i in parent_items if i.get("transaction_status") not in ("credited", "refunded", "transferred")]
        comp_count = sum(1 for i in active_parents if (i.get("email_uid") or "").startswith("manual-comp") and i.get("transaction_status") != "wd")
        rsvp_count = sum(1 for i in active_parents if i.get("transaction_status") == "rsvp_only")
        wd_count = sum(1 for i in active_parents if i.get("transaction_status") == "wd")
        paid_count = len(active_parents) - comp_count - rsvp_count - wd_count
        total_active = len(active_parents) - rsvp_count - wd_count

        # ── Try flat acct_transactions first (single source of truth) ──
        acct_entries = conn.execute(
            f"""SELECT * FROM acct_transactions
                WHERE event_name COLLATE NOCASE IN ({name_placeholders})
                AND COALESCE(status, 'active') = 'active'
                AND entry_type IS NOT NULL""",
            all_names,
        ).fetchall()
        acct_entries = [dict(r) for r in acct_entries]
        accounting_verified = len(acct_entries) > 0

        if accounting_verified:
            # ── Revenue from acct_transactions ──
            income_entries = [e for e in acct_entries if e["entry_type"] == "income"]
            # Old per-item format (category='registration')
            old_reg_revenue = sum(e["amount"] for e in income_entries if e.get("category") == "registration")
            # New order-level format (from godaddy_order_splits)
            new_reg_row = conn.execute(
                f"""SELECT COALESCE(SUM(s.amount), 0) as total
                    FROM godaddy_order_splits s
                    JOIN acct_transactions t ON t.id = s.transaction_id
                    WHERE s.event_name COLLATE NOCASE IN ({name_placeholders})
                    AND s.split_type = 'registration'
                    AND COALESCE(t.status, 'active') = 'active'""",
                all_names,
            ).fetchone()
            godaddy_revenue = round(old_reg_revenue + (new_reg_row["total"] if new_reg_row else 0), 2)
            external_revenue = round(sum(e["amount"] for e in income_entries if e.get("category") == "addon" and e.get("source") not in ("godaddy",)), 2)
            xfer_in_revenue = round(sum(e["amount"] for e in income_entries if e.get("category") == "transfer_in"), 2)
            addon_revenue = round(sum(e["amount"] for e in income_entries if e.get("category") == "addon" and e.get("source") == "godaddy"), 2)

            # Add transaction fees collected from players (parsed from GoDaddy emails)
            # These are revenue — offset against merchant fees to get net.
            # Only real GoDaddy orders (no transfers, comps, or child payments)
            tx_fee_total = 0.0
            for item in all_items:
                if item.get("transaction_status") in ("credited", "refunded", "transferred"):
                    continue
                if item.get("parent_item_id"):
                    continue
                if item.get("transferred_from_id"):
                    continue  # transfer targets didn't generate a GoDaddy charge
                if (item.get("email_uid") or "").startswith("manual-comp"):
                    continue
                tf = _parse_dollar(item.get("transaction_fees"))
                if tf > 0:
                    tx_fee_total += tf
            tx_fee_total = round(tx_fee_total, 2)

            total_revenue = round(godaddy_revenue + external_revenue + xfer_in_revenue + addon_revenue + tx_fee_total, 2)

            # ── Contra-revenue ──
            contra_entries = [e for e in acct_entries if e["entry_type"] == "contra"]
            xfer_out = round(sum(e["amount"] for e in contra_entries if e.get("category") == "transfer_out"), 2)

            # ── Expenses ──
            expense_entries = [e for e in acct_entries if e["entry_type"] == "expense"]
            refund_total = round(sum(e["amount"] for e in expense_entries if e.get("category") == "refund"), 2)
            # Old per-item format (category='processing_fee')
            old_processing = sum(e["amount"] for e in expense_entries if e.get("category") == "processing_fee")
            # New order-level format (from godaddy_order_splits, stored as negative)
            new_fee_row = conn.execute(
                f"""SELECT COALESCE(SUM(ABS(s.amount)), 0) as total
                    FROM godaddy_order_splits s
                    JOIN acct_transactions t ON t.id = s.transaction_id
                    WHERE s.event_name COLLATE NOCASE IN ({name_placeholders})
                    AND s.split_type = 'merchant_fee'
                    AND COALESCE(t.status, 'active') = 'active'""",
                all_names,
            ).fetchone()
            total_processing = round(old_processing + (new_fee_row["total"] if new_fee_row else 0), 2)

            # Contra = transfers out + refunds only (NOT processing fees — those are expenses)
            contra_total = round(xfer_out + refund_total, 2)
            net_revenue = round(total_revenue - contra_total, 2)

            # Course fees from aggregate calculation (most accurate)
            course_cost_calc = _calc_aggregate_course_cost(event, all_items, conn)
            aggregate_course_cost = course_cost_calc["total"]
            course_fees_by_holes = course_cost_calc["by_holes"]

            # Prize fund: set to 0 so the client uses its game matrix calculation.
            # Allocations only have partial coverage for prize_pool data — the client-side
            # computeGamePotTotals() is authoritative for prize fund amounts.
            allocs = conn.execute(
                f"SELECT * FROM acct_allocations WHERE event_name COLLATE NOCASE IN ({name_placeholders})",
                all_names,
            ).fetchall()
            allocs = [dict(r) for r in allocs]
            total_prize_pool = 0  # client calculates from games matrix
            total_tgf_operating = round(sum(a.get("tgf_operating", 0) for a in allocs), 2)
            total_tax_reserve = round(sum(a.get("tax_reserve", 0) for a in allocs), 2)

            total_expenses = round(aggregate_course_cost + total_prize_pool + total_processing, 2)
            projected_profit = round(net_revenue - total_expenses, 2)

            # Coverage based on acct_transactions entries + order splits
            items_needing_entry = [i for i in all_items
                                   if i.get("transaction_status") in (None, "active")
                                   and not (i.get("email_uid") or "").startswith("manual-comp")
                                   and i.get("transaction_status") != "rsvp_only"
                                   and _parse_dollar(i.get("item_price")) > 0]
            acct_item_ids = {e.get("item_id") for e in acct_entries if e.get("item_id")}
            # Also get item_ids from order-level splits
            split_item_rows = conn.execute(
                f"""SELECT DISTINCT s.item_id FROM godaddy_order_splits s
                    JOIN acct_transactions t ON t.id = s.transaction_id
                    WHERE s.event_name COLLATE NOCASE IN ({name_placeholders})
                    AND COALESCE(t.status, 'active') = 'active'
                    AND s.item_id IS NOT NULL""",
                all_names,
            ).fetchall()
            acct_item_ids.update(r[0] for r in split_item_rows)
            items_with_entry = sum(1 for i in items_needing_entry if i["id"] in acct_item_ids)
            coverage = round(items_with_entry / len(items_needing_entry) * 100, 1) if items_needing_entry else 0

        else:
            # ── Fallback: allocation-based calculation ──
            allocs = conn.execute(
                f"SELECT * FROM acct_allocations WHERE event_name COLLATE NOCASE IN ({name_placeholders})",
                all_names,
            ).fetchall()
            allocs = [dict(r) for r in allocs]

            godaddy_allocs = [a for a in allocs if (a.get("payment_method") or "godaddy") == "godaddy"]
            external_allocs = [a for a in allocs if (a.get("payment_method") or "godaddy") in ("venmo", "cash", "zelle", "check")]
            xfer_allocs = [a for a in allocs if (a.get("payment_method") or "") == "credit_transfer"]

            godaddy_revenue = round(sum(a.get("total_collected", 0) for a in godaddy_allocs), 2)
            external_revenue = round(sum(a.get("total_collected", 0) for a in external_allocs), 2)
            xfer_in_revenue = round(sum(a.get("total_collected", 0) for a in xfer_allocs), 2)

            addon_allocs = [a for a in allocs if (a.get("order_id") or "").startswith("MANUAL-PAY-")]
            addon_revenue = round(sum(a.get("total_collected", 0) for a in addon_allocs), 2)

            total_revenue = round(godaddy_revenue + external_revenue + xfer_in_revenue + addon_revenue, 2)

            xfer_out = 0
            if event_db_id:
                xfer_out_rows = conn.execute(
                    """SELECT COALESCE(SUM(s.amount), 0) as total
                       FROM acct_transactions t
                       JOIN acct_splits s ON s.transaction_id = t.id
                       WHERE t.source = 'credit_transfer' AND t.type = 'expense'
                       AND s.event_id = ?""",
                    (event_db_id,),
                ).fetchone()
                xfer_out = round(xfer_out_rows["total"], 2) if xfer_out_rows else 0

            refund_total = 0
            if event_db_id:
                refund_rows = conn.execute(
                    """SELECT COALESCE(SUM(s.amount), 0) as total
                       FROM acct_transactions t
                       JOIN acct_splits s ON s.transaction_id = t.id
                       WHERE t.source = 'refund' AND t.type = 'expense'
                       AND s.event_id = ?""",
                    (event_db_id,),
                ).fetchone()
                refund_total = round(refund_rows["total"], 2) if refund_rows else 0

            contra_total = round(xfer_out + refund_total, 2)
            net_revenue = round(total_revenue - contra_total, 2)

            course_cost_calc = _calc_aggregate_course_cost(event, all_items, conn)
            aggregate_course_cost = course_cost_calc["total"]
            course_fees_by_holes = course_cost_calc["by_holes"]
            total_prize_pool = round(sum(a.get("prize_pool", 0) for a in allocs), 2)
            total_processing = round(sum(a.get("godaddy_fee", 0) for a in allocs), 2)
            total_tgf_operating = round(sum(a.get("tgf_operating", 0) for a in allocs), 2)
            total_tax_reserve = round(sum(a.get("tax_reserve", 0) for a in allocs), 2)

            total_expenses = round(aggregate_course_cost + total_prize_pool + total_processing, 2)
            projected_profit = round(net_revenue - total_expenses, 2)

            items_needing_alloc = [i for i in all_items
                                   if i.get("transaction_status") in (None, "active")
                                   and not (i.get("email_uid") or "").startswith("manual-comp")
                                   and i.get("transaction_status") != "rsvp_only"
                                   and _parse_dollar(i.get("item_price")) > 0]
            allocated_item_ids = {a.get("item_id") for a in allocs if a.get("item_id")}
            items_with_alloc = sum(1 for i in items_needing_alloc if i["id"] in allocated_item_ids)
            coverage = round(items_with_alloc / len(items_needing_alloc) * 100, 1) if items_needing_alloc else 0

    # ── Revenue sanity check: cross-check item_price vs total_amount - fees ──
    revenue_discrepancy = None
    calc_a = 0.0
    calc_b = 0.0
    for i in all_items:
        if (i.get("transaction_status") or "active") != "active":
            continue
        if i.get("parent_item_id"):
            continue
        if (i.get("email_uid") or "").startswith("manual-comp"):
            continue
        price = _parse_dollar(i.get("item_price"))
        calc_a += price
        total_amt = _parse_dollar(i.get("total_amount"))
        tx_fees = _parse_dollar(i.get("transaction_fees"))
        if total_amt > 0:
            calc_b += round(total_amt - tx_fees, 2)
        elif i.get("transferred_from_id") or (i.get("merchant") or "").startswith("Paid Separately"):
            calc_b += price

    calc_a = round(calc_a, 2)
    calc_b = round(calc_b, 2)
    gap = round(calc_a - calc_b, 2)
    if abs(gap) > 1.0:
        revenue_discrepancy = {
            "item_price_total": calc_a,
            "order_total_crosscheck": calc_b,
            "gap": gap,
            "direction": "item_price is higher" if gap > 0 else "item_price is lower",
        }

    return {
        "event_name": event_name,
        "revenue": {
            "godaddy": godaddy_revenue,
            "external_payments": external_revenue,
            "credit_transfers_in": xfer_in_revenue,
            "add_on_payments": addon_revenue,
            "total": total_revenue,
        },
        "contra_revenue": {
            "credit_transfers_out": xfer_out,
            "refunds": refund_total,
            "total": contra_total,
        },
        "net_revenue": net_revenue,
        "expenses": {
            "course_fees": aggregate_course_cost,
            "course_fees_by_holes": course_fees_by_holes,
            "prize_fund": total_prize_pool,
            "processing_fees": total_processing,
            "tgf_operating": total_tgf_operating,
            "tax_reserve": total_tax_reserve,
            "total": total_expenses,
        },
        "projected_profit": projected_profit,
        "player_counts": {
            "paid": paid_count,
            "comp": comp_count,
            "rsvp": rsvp_count,
            "wd": wd_count,
            "total_active": total_active,
        },
        "has_allocation_data": len(allocs) > 0 if not accounting_verified else True,
        "allocation_coverage_pct": coverage,
        "revenue_discrepancy": revenue_discrepancy,
        "accounting_verified": accounting_verified,
    }


def _calc_aggregate_course_cost(event: dict, all_items: list[dict],
                                conn: sqlite3.Connection) -> dict:
    """Calculate aggregate course cost with correct rounding (Issue #242).

    Instead of: per_player_post_tax × count (rounding drift),
    uses: base_rate × count × (1 + tax_rate) — totals first, tax second.

    If the event has no course-cost config (no course_cost / course_cost_breakdown
    columns set), falls back to summing the per-player course_payable values
    stored on acct_allocations at registration time.

    Returns ``{"total": float, "by_holes": [{"holes": "9"|"18", "count": int,
    "per_player": float, "total": float}]}``.  ``by_holes`` only contains the
    hole buckets that actually have players.
    """
    is_combo = "combo" in (event.get("format") or "").lower()
    default_holes = "18" if event.get("format") in ("18 Holes", "27 Holes") else "9"

    parent_items = [i for i in all_items if not i.get("parent_item_id")]
    active_parents = [i for i in parent_items
                      if i.get("transaction_status") not in ("credited", "refunded", "transferred", "rsvp_only", "wd")]

    if not active_parents:
        return {"total": 0.0, "by_holes": []}

    surcharge_per_player = float(event.get("course_surcharge") or 0)
    by_holes: list[dict] = []
    total_course_cost = 0.0

    # Try breakdown JSON first (most accurate)
    for holes_key in ("9", "18"):
        players_this_holes = []
        for item in active_parents:
            h = str(item.get("holes") or "")
            if "18" in h:
                player_holes = "18"
            elif "9" in h:
                player_holes = "9"
            else:
                player_holes = default_holes
            if player_holes == holes_key:
                players_this_holes.append(item)

        count = len(players_this_holes)
        if count == 0:
            continue

        # Get breakdown JSON for this hole type
        if is_combo and holes_key == "18":
            bd_col = "course_cost_breakdown_18"
            fallback_cost = event.get("course_cost_18") or event.get("course_cost")
        elif is_combo:
            bd_col = "course_cost_breakdown_9"
            fallback_cost = event.get("course_cost_9") or event.get("course_cost")
        else:
            bd_col = "course_cost_breakdown"
            fallback_cost = event.get("course_cost")

        bucket_cost = 0.0
        breakdown_json = event.get(bd_col)
        if breakdown_json:
            try:
                breakdown = json.loads(breakdown_json)
                # Aggregate correctly: sum pre-tax × count, then apply tax
                for val in breakdown.values():
                    base = val["amount"] * count
                    tax = base * (val["tax_pct"] / 100)
                    bucket_cost += base + tax
            except (json.JSONDecodeError, KeyError, TypeError):
                if fallback_cost:
                    bucket_cost = fallback_cost * count
        elif fallback_cost:
            bucket_cost = fallback_cost * count

        # Per-player surcharge belongs to whichever hole bucket the player is in
        bucket_cost += surcharge_per_player * count
        total_course_cost += bucket_cost

        by_holes.append({
            "holes": holes_key,
            "count": count,
            "per_player": round(bucket_cost / count, 2) if count else 0.0,
            "total": round(bucket_cost, 2),
        })

    # Fallback: event config missing → use per-player allocations from registration time.
    # Allocation rows store course_payable (post-tax) and course_surcharge separately,
    # so summing both gives the full per-event course cost without double-counting.
    if total_course_cost == 0:
        active_ids = [i["id"] for i in active_parents]
        placeholders = ",".join("?" * len(active_ids))
        row = conn.execute(
            f"""SELECT
                    COALESCE(SUM(course_payable), 0) AS payable,
                    COALESCE(SUM(course_surcharge), 0) AS surcharge
                FROM acct_allocations
                WHERE item_id IN ({placeholders})""",
            active_ids,
        ).fetchone()
        if row and (row["payable"] or row["surcharge"]):
            fallback_total = round(float(row["payable"]) + float(row["surcharge"]), 2)
            # Bucketise the fallback by summing per-allocation amounts within each hole group
            fallback_buckets = []
            for holes_key in ("9", "18"):
                bucket_ids = []
                for item in active_parents:
                    h = str(item.get("holes") or "")
                    if "18" in h:
                        ph = "18"
                    elif "9" in h:
                        ph = "9"
                    else:
                        ph = default_holes
                    if ph == holes_key:
                        bucket_ids.append(item["id"])
                if not bucket_ids:
                    continue
                bp = ",".join("?" * len(bucket_ids))
                br = conn.execute(
                    f"""SELECT
                            COALESCE(SUM(course_payable), 0) AS payable,
                            COALESCE(SUM(course_surcharge), 0) AS surcharge
                        FROM acct_allocations
                        WHERE item_id IN ({bp})""",
                    bucket_ids,
                ).fetchone()
                btot = round(float(br["payable"]) + float(br["surcharge"]), 2)
                fallback_buckets.append({
                    "holes": holes_key,
                    "count": len(bucket_ids),
                    "per_player": round(btot / len(bucket_ids), 2) if bucket_ids else 0.0,
                    "total": btot,
                })
            return {"total": fallback_total, "by_holes": fallback_buckets}

    return {"total": round(total_course_cost, 2), "by_holes": by_holes}


def backfill_financial_entries(db_path: str | Path | None = None) -> dict:
    """Backfill accounting entries for existing items that lack them (Issue #242).

    Idempotent: checks for existing entries before creating new ones.
    Creates allocations and acct_transactions for:
    1. External payments (Paid Separately items without allocations)
    2. Credit transfers (transferred items without accounting entries)
    3. Add-on child payments (parent_item_id items without allocations)
    4. Refunds (refunded items without accounting entries)
    """
    results = {"external_payments": 0, "credit_transfers": 0,
               "add_on_payments": 0, "refunds": 0, "transfer_prices_fixed": 0, "errors": 0}

    with _connect(db_path) as conn:
        # ── 0. Fix transfer items that still show "$0.00 (credit)" ──
        zero_transfers = conn.execute(
            """SELECT i.id, i.transferred_from_id, orig.item_price as orig_price
               FROM items i
               JOIN items orig ON orig.id = i.transferred_from_id
               WHERE i.transferred_from_id IS NOT NULL
               AND i.item_price = '$0.00 (credit)'
               AND orig.item_price IS NOT NULL
               AND orig.item_price != '$0.00'"""
        ).fetchall()
        for row in zero_transfers:
            try:
                orig_price = row["orig_price"]
                conn.execute(
                    "UPDATE items SET item_price = ? WHERE id = ?",
                    (f"{orig_price} (credit)", row["id"]),
                )
                results["transfer_prices_fixed"] += 1
            except Exception:
                logger.warning("Backfill: failed to fix transfer price for item %s", row["id"], exc_info=True)
                results["errors"] += 1

        # ── 1. External payments ──
        ext_items = conn.execute(
            """SELECT i.* FROM items i
               WHERE i.merchant LIKE 'Paid Separately%'
               AND COALESCE(i.transaction_status, 'active') = 'active'
               AND i.id NOT IN (SELECT item_id FROM acct_allocations WHERE item_id IS NOT NULL)"""
        ).fetchall()
        for row in ext_items:
            try:
                item = dict(row)
                source = (item.get("merchant") or "").replace("Paid Separately (", "").rstrip(")")
                pay_method = source.lower().replace(" ", "_")
                if pay_method not in ("venmo", "cash", "zelle", "check"):
                    pay_method = "cash"
                _create_allocation_for_item(
                    item, conn, payment_method=pay_method,
                    create_txn=True,
                    txn_description=f"External payment ({source}): {item.get('customer', '')} — {item.get('item_name', '')}",
                    txn_source="external_payment",
                    txn_category_name="External Payment",
                )
                results["external_payments"] += 1
            except Exception:
                logger.warning("Backfill: failed ext payment item %s", row["id"], exc_info=True)
                results["errors"] += 1

        # ── 2. Credit transfers ──
        xfer_items = conn.execute(
            """SELECT i.*, i2.id as target_item_id, i2.item_name as target_event
               FROM items i
               JOIN items i2 ON i2.transferred_from_id = i.id
               WHERE i.transaction_status = 'transferred'"""
        ).fetchall()
        for row in xfer_items:
            try:
                item = dict(row)
                orig_price = _parse_dollar(item.get("item_price"))
                target_item_id = item["target_item_id"]
                target_event = item["target_event"]
                source_event = item.get("item_name", "")

                if orig_price <= 0:
                    continue

                # Create contra-revenue (source event)
                source_ref_out = f"xfer-{item['id']}-out"
                if not conn.execute("SELECT id FROM acct_transactions WHERE source_ref = ?", (source_ref_out,)).fetchone():
                    source_event_row = conn.execute("SELECT id FROM events WHERE item_name = ? COLLATE NOCASE", (source_event,)).fetchone()
                    target_event_row = conn.execute("SELECT id FROM events WHERE item_name = ? COLLATE NOCASE", (target_event,)).fetchone()
                    tgf_entity = conn.execute("SELECT id FROM acct_entities WHERE short_name = 'TGF'").fetchone()
                    tgf_id = tgf_entity["id"] if tgf_entity else 1
                    cat_out = conn.execute("SELECT id FROM acct_categories WHERE name = 'Credit Transfer Out'").fetchone()
                    cat_in = conn.execute("SELECT id FROM acct_categories WHERE name = 'Credit Transfer In'").fetchone()
                    alloc_date = item.get("order_date") or ""

                    # Contra-revenue
                    cur_out = conn.execute(
                        """INSERT INTO acct_transactions (date, description, total_amount, type, source, source_ref)
                           VALUES (?, ?, ?, 'expense', 'credit_transfer', ?)""",
                        (alloc_date, f"Credit transfer out: {item.get('customer', '')} from {source_event}",
                         orig_price, source_ref_out),
                    )
                    conn.execute(
                        "INSERT INTO acct_splits (transaction_id, entity_id, category_id, amount, memo, event_id) VALUES (?, ?, ?, ?, ?, ?)",
                        (cur_out.lastrowid, tgf_id, cat_out["id"] if cat_out else None, orig_price,
                         f"Credit transfer to {target_event}", source_event_row["id"] if source_event_row else None),
                    )

                    # Revenue on target
                    source_ref_in = f"xfer-{item['id']}-in"
                    cur_in = conn.execute(
                        """INSERT INTO acct_transactions (date, description, total_amount, type, source, source_ref)
                           VALUES (?, ?, ?, 'income', 'credit_transfer', ?)""",
                        (alloc_date, f"Credit transfer in: {item.get('customer', '')} to {target_event}",
                         orig_price, source_ref_in),
                    )
                    conn.execute(
                        "INSERT INTO acct_splits (transaction_id, entity_id, category_id, amount, memo, event_id) VALUES (?, ?, ?, ?, ?, ?)",
                        (cur_in.lastrowid, tgf_id, cat_in["id"] if cat_in else None, orig_price,
                         f"Credit transfer from {source_event}", target_event_row["id"] if target_event_row else None),
                    )

                # Create allocation for target item
                target_item = conn.execute("SELECT * FROM items WHERE id = ?", (target_item_id,)).fetchone()
                if target_item:
                    alloc_exists = conn.execute(
                        "SELECT id FROM acct_allocations WHERE order_id = ?",
                        (f"XFER-{target_item_id}",),
                    ).fetchone()
                    if not alloc_exists:
                        _create_allocation_for_item(
                            dict(target_item), conn,
                            payment_method="credit_transfer",
                            override_price=orig_price,
                            create_txn=False,
                        )

                results["credit_transfers"] += 1
            except Exception:
                logger.warning("Backfill: failed xfer item %s", row["id"], exc_info=True)
                results["errors"] += 1

        # ── 3. Add-on child payments ──
        child_items = conn.execute(
            """SELECT i.* FROM items i
               WHERE i.parent_item_id IS NOT NULL
               AND COALESCE(i.transaction_status, 'active') = 'active'
               AND i.id NOT IN (SELECT item_id FROM acct_allocations WHERE item_id IS NOT NULL)"""
        ).fetchall()
        for row in child_items:
            try:
                item = dict(row)
                pay_amount = _parse_dollar(item.get("item_price"))
                if pay_amount <= 0:
                    continue
                source = (item.get("merchant") or "").replace("Manual Entry (", "").rstrip(")")
                pay_method = source.lower().replace(" ", "_")
                if pay_method not in ("venmo", "cash", "zelle", "check", "godaddy"):
                    pay_method = "cash"
                _create_allocation_for_item(
                    item, conn, payment_method=pay_method,
                    create_txn=True,
                    txn_description=f"Add-on payment: {item.get('customer', '')} — {item.get('item_name', '')}",
                    txn_source="add_payment",
                    txn_category_name="External Payment" if pay_method != "godaddy" else "Event Revenue",
                )
                results["add_on_payments"] += 1
            except Exception:
                logger.warning("Backfill: failed child item %s", row["id"], exc_info=True)
                results["errors"] += 1

        # ── 4. Refunds ──
        refunded_items = conn.execute(
            "SELECT * FROM items WHERE transaction_status = 'refunded'"
        ).fetchall()
        for row in refunded_items:
            try:
                item = dict(row)
                refund_amount = _parse_dollar(item.get("item_price"))
                if refund_amount <= 0:
                    continue
                source_ref = f"refund-{item['id']}"
                if conn.execute("SELECT id FROM acct_transactions WHERE source_ref = ?", (source_ref,)).fetchone():
                    continue  # already exists
                event_name = item.get("item_name", "")
                event_row = conn.execute("SELECT id FROM events WHERE item_name = ? COLLATE NOCASE", (event_name,)).fetchone()
                tgf_entity = conn.execute("SELECT id FROM acct_entities WHERE short_name = 'TGF'").fetchone()
                cat_refund = conn.execute("SELECT id FROM acct_categories WHERE name = 'Player Refunds'").fetchone()
                tgf_id = tgf_entity["id"] if tgf_entity else 1

                method = ""
                credit_note = item.get("credit_note") or ""
                if "venmo" in credit_note.lower():
                    method = "Venmo"
                elif "godaddy" in credit_note.lower():
                    method = "GoDaddy"

                cur_txn = conn.execute(
                    """INSERT INTO acct_transactions (date, description, total_amount, type, source, source_ref)
                       VALUES (?, ?, ?, 'expense', 'refund', ?)""",
                    (item.get("order_date") or "",
                     f"Refund ({method}): {item.get('customer', '')} — {event_name}",
                     refund_amount, source_ref),
                )
                conn.execute(
                    "INSERT INTO acct_splits (transaction_id, entity_id, category_id, amount, memo, event_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (cur_txn.lastrowid, tgf_id, cat_refund["id"] if cat_refund else None, refund_amount,
                     credit_note, event_row["id"] if event_row else None),
                )
                results["refunds"] += 1
            except Exception:
                logger.warning("Backfill: failed refund item %s", row["id"], exc_info=True)
                results["errors"] += 1

        conn.commit()

    results["total"] = (results["external_payments"] + results["credit_transfers"]
                        + results["add_on_payments"] + results["refunds"])
    return results


# ---------------------------------------------------------------------------
# Canonical player-field resolvers
# ---------------------------------------------------------------------------
# The customers / customer_emails / customer_roles tables are the source of
# truth for a player's identity. items.customer_email/phone/first_name/
# last_name/chapter/user_status are historical snapshots from each order.
# Anywhere a player's *current* identity is needed (display name, email send,
# phone reminder, status badge, chapter lookup), code MUST resolve through
# these helpers so a stale order can't override what the manager set on the
# Customer Info page.
#
# Each helper accepts either:
#   - an items-row-shaped dict (with customer_id and/or customer name), or
#   - just a customer_id integer, or
#   - just a customer_name string,
# and returns "" / None when nothing canonical is available so callers can
# fall back to whatever they were doing before.

def _resolve_db(conn, db_path):
    """Internal: yield a (conn, owns_conn) pair so resolvers can either share
    a caller's connection or open their own.

    When opening our own, use get_connection() directly rather than the
    managed_connection contextmanager — calling .__enter__() on the latter
    without holding a reference to the wrapper causes Python's GC to close
    the underlying connection immediately (the generator's finally runs
    when the wrapper is reclaimed). Callers must call conn.close() in their
    finally when owns is True.
    """
    if conn is not None:
        return conn, False
    return get_connection(db_path), True


def _resolve_lookup_customer_id(conn, item_or_id, name_hint: str = "") -> int | None:
    """Best-effort customer_id lookup from a dict-like item, raw int, or name."""
    if isinstance(item_or_id, int):
        return item_or_id
    if isinstance(item_or_id, dict):
        cid = item_or_id.get("customer_id")
        if cid:
            return int(cid)
        name = (item_or_id.get("customer") or "").strip() or name_hint
    else:
        name = (str(item_or_id) if item_or_id is not None else "").strip() or name_hint
    if not name:
        return None
    row = conn.execute(
        """SELECT customer_id FROM customers
           WHERE LOWER(TRIM(first_name || ' ' || last_name)) = LOWER(?)
              OR LOWER(TRIM(last_name || ', ' || first_name)) = LOWER(?)
           LIMIT 1""",
        (name, name),
    ).fetchone()
    if row:
        return int(row["customer_id"])
    # Alias-name fallback — covers "Stu Kirksey" → Stuart Kirksey, etc.
    row = conn.execute(
        """SELECT c.customer_id FROM customer_aliases ca
           JOIN customers c
             ON LOWER(TRIM(c.first_name) || ' ' || TRIM(c.last_name)) = LOWER(TRIM(ca.customer_name))
           WHERE ca.alias_type = 'name' AND LOWER(ca.alias_value) = LOWER(?)
           LIMIT 1""",
        (name,),
    ).fetchone()
    return int(row["customer_id"]) if row else None


def resolve_player_email(item, conn=None, db_path=None) -> str:
    """customer_emails.is_primary first; items.customer_email as fallback."""
    conn, owns = _resolve_db(conn, db_path)
    try:
        cid = _resolve_lookup_customer_id(conn, item)
        if cid:
            row = conn.execute(
                "SELECT email FROM customer_emails WHERE customer_id = ? AND is_primary = 1 LIMIT 1",
                (cid,),
            ).fetchone()
            if row and row["email"]:
                return row["email"].strip().lower()
        if isinstance(item, dict):
            return (item.get("customer_email") or "").strip()
        return ""
    finally:
        if owns:
            try: conn.close()
            except Exception: pass


def resolve_player_phone(item, conn=None, db_path=None) -> str:
    """customers.phone first; items.customer_phone as fallback."""
    conn, owns = _resolve_db(conn, db_path)
    try:
        cid = _resolve_lookup_customer_id(conn, item)
        if cid:
            row = conn.execute(
                "SELECT phone FROM customers WHERE customer_id = ? LIMIT 1",
                (cid,),
            ).fetchone()
            if row and row["phone"]:
                return row["phone"].strip()
        if isinstance(item, dict):
            return (item.get("customer_phone") or "").strip()
        return ""
    finally:
        if owns:
            try: conn.close()
            except Exception: pass


def resolve_player_name(item, conn=None, db_path=None) -> dict:
    """Returns {first_name, last_name} from customers; falls back to items."""
    conn, owns = _resolve_db(conn, db_path)
    try:
        cid = _resolve_lookup_customer_id(conn, item)
        if cid:
            row = conn.execute(
                "SELECT first_name, last_name FROM customers WHERE customer_id = ? LIMIT 1",
                (cid,),
            ).fetchone()
            if row:
                fn = (row["first_name"] or "").strip()
                ln = (row["last_name"] or "").strip()
                if fn or ln:
                    return {"first_name": fn, "last_name": ln}
        if isinstance(item, dict):
            return {
                "first_name": (item.get("first_name") or "").strip(),
                "last_name": (item.get("last_name") or "").strip(),
            }
        return {"first_name": "", "last_name": ""}
    finally:
        if owns:
            try: conn.close()
            except Exception: pass


def resolve_player_chapter(item, conn=None, db_path=None) -> str:
    """customers.chapter first; items.chapter as fallback."""
    conn, owns = _resolve_db(conn, db_path)
    try:
        cid = _resolve_lookup_customer_id(conn, item)
        if cid:
            row = conn.execute(
                "SELECT chapter FROM customers WHERE customer_id = ? LIMIT 1",
                (cid,),
            ).fetchone()
            if row and row["chapter"]:
                return row["chapter"].strip()
        if isinstance(item, dict):
            return (item.get("chapter") or "").strip()
        return ""
    finally:
        if owns:
            try: conn.close()
            except Exception: pass


def resolve_player_status(item, conn=None, db_path=None) -> str:
    """Resolve player display status from customers.current_player_status +
    customer_roles. Falls back to items.user_status only when no canonical
    record exists.

    Mapping (matches existing UI conventions):
      manager/owner/admin role  → 'MANAGER'
      current_player_status='active_member' + member_plus role → 'MEMBER+'
      current_player_status='active_member' → 'MEMBER'
      current_player_status='active_guest'  → 'GUEST'
      current_player_status='first_timer'   → '1ST TIMER'
      everything else → empty (caller chooses fallback)
    """
    conn, owns = _resolve_db(conn, db_path)
    try:
        cid = _resolve_lookup_customer_id(conn, item)
        if cid:
            cust = conn.execute(
                "SELECT current_player_status FROM customers WHERE customer_id = ? LIMIT 1",
                (cid,),
            ).fetchone()
            roles = {r["role_type"] for r in conn.execute(
                "SELECT role_type FROM customer_roles WHERE customer_id = ?",
                (cid,),
            ).fetchall()}
            if roles & {"manager", "owner", "admin"}:
                return "MANAGER"
            cps = (cust["current_player_status"] if cust else "") or ""
            if cps == "active_member":
                return "MEMBER+" if "member_plus" in roles else "MEMBER"
            if cps == "active_guest":
                return "GUEST"
            if cps == "first_timer":
                return "1ST TIMER"
        if isinstance(item, dict):
            return (item.get("user_status") or "").strip()
        return ""
    finally:
        if owns:
            try: conn.close()
            except Exception: pass


def heal_items_from_customers(db_path: str | Path | None = None) -> dict:
    """One-shot, idempotent data heal for items.customer_email / customer_phone /
    chapter / first_name / last_name. For every items row whose customer_id
    is set:

      - If items.<field> differs from the canonical customers / customer_emails
        value, capture the items value as a customer_alias (alias_type='email'
        for emails; for the others we just overwrite quietly because no alias
        slot exists).
      - Update items.<field> to match the canonical value.

    The Phase-1A resolvers already prefer canonical-over-snapshot at read
    time, so this heal isn't strictly required for correctness — but
    flattening the underlying data eliminates the second-source-of-truth
    problem for any future read site that forgets to use the resolver.

    Idempotent: re-runs are no-ops because the WHERE clauses only match
    when items.<field> still differs.
    Returns counts of rows touched per field.
    """
    counts = {"emails_aliased": 0, "emails_overwritten": 0,
              "phones_overwritten": 0, "chapters_overwritten": 0,
              "first_names_overwritten": 0, "last_names_overwritten": 0}

    with _connect(db_path) as conn:
        # Email: capture as alias before overwriting (preserves the variant
        # for the manager to see on the Customer Info card).
        try:
            counts["emails_aliased"] = capture_email_aliases_from_items(db_path)
        except Exception:
            logger.warning("heal_items_from_customers: email-alias capture failed", exc_info=True)

        # Now flatten items.customer_email to the primary
        cur = conn.execute("""
            UPDATE items SET customer_email = (
                SELECT LOWER(TRIM(e.email)) FROM customer_emails e
                WHERE e.customer_id = items.customer_id AND e.is_primary = 1 LIMIT 1
            )
            WHERE customer_id IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM customer_emails e
                  WHERE e.customer_id = items.customer_id AND e.is_primary = 1
              )
              AND LOWER(COALESCE(TRIM(items.customer_email), '')) != (
                  SELECT LOWER(TRIM(e.email)) FROM customer_emails e
                  WHERE e.customer_id = items.customer_id AND e.is_primary = 1 LIMIT 1
              )
        """)
        counts["emails_overwritten"] = cur.rowcount

        # Phone: overwrite to customers.phone where they differ
        cur = conn.execute("""
            UPDATE items SET customer_phone = (
                SELECT TRIM(c.phone) FROM customers c
                WHERE c.customer_id = items.customer_id LIMIT 1
            )
            WHERE customer_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM customers c
                          WHERE c.customer_id = items.customer_id
                            AND c.phone IS NOT NULL AND TRIM(c.phone) != '')
              AND COALESCE(TRIM(items.customer_phone), '') != (
                  SELECT TRIM(c.phone) FROM customers c
                  WHERE c.customer_id = items.customer_id LIMIT 1
              )
        """)
        counts["phones_overwritten"] = cur.rowcount

        # Chapter: overwrite to customers.chapter where they differ
        cur = conn.execute("""
            UPDATE items SET chapter = (
                SELECT c.chapter FROM customers c
                WHERE c.customer_id = items.customer_id LIMIT 1
            )
            WHERE customer_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM customers c
                          WHERE c.customer_id = items.customer_id
                            AND c.chapter IS NOT NULL AND TRIM(c.chapter) != '')
              AND COALESCE(TRIM(items.chapter), '') != (
                  SELECT TRIM(c.chapter) FROM customers c
                  WHERE c.customer_id = items.customer_id LIMIT 1
              )
        """)
        counts["chapters_overwritten"] = cur.rowcount

        # first_name / last_name: overwrite to customers.first_name / last_name
        cur = conn.execute("""
            UPDATE items SET first_name = (
                SELECT c.first_name FROM customers c
                WHERE c.customer_id = items.customer_id LIMIT 1
            )
            WHERE customer_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM customers c
                          WHERE c.customer_id = items.customer_id
                            AND c.first_name IS NOT NULL AND TRIM(c.first_name) != '')
              AND COALESCE(TRIM(items.first_name), '') != (
                  SELECT TRIM(c.first_name) FROM customers c
                  WHERE c.customer_id = items.customer_id LIMIT 1
              )
        """)
        counts["first_names_overwritten"] = cur.rowcount

        cur = conn.execute("""
            UPDATE items SET last_name = (
                SELECT c.last_name FROM customers c
                WHERE c.customer_id = items.customer_id LIMIT 1
            )
            WHERE customer_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM customers c
                          WHERE c.customer_id = items.customer_id
                            AND c.last_name IS NOT NULL AND TRIM(c.last_name) != '')
              AND COALESCE(TRIM(items.last_name), '') != (
                  SELECT TRIM(c.last_name) FROM customers c
                  WHERE c.customer_id = items.customer_id LIMIT 1
              )
        """)
        counts["last_names_overwritten"] = cur.rowcount

        if any(v for v in counts.values()):
            conn.commit()
            logger.info("heal_items_from_customers: %s", counts)
    return counts


def capture_email_aliases_from_items(db_path: str | Path | None = None) -> int:
    """Promote any items.customer_email value that differs from the linked
    customer's primary email into customer_aliases (alias_type='email').

    The Customer Info card reads email from customer_emails.is_primary, so a
    typo'd address on a single old order (e.g. items.customer_email =
    'fredwickee@att.net' while the primary is 'fredwicker@att.net') is
    invisible to the manager — but other code paths used to read it directly.
    Surfacing variants as aliases makes them visible on the customer page so
    the manager can decide whether to keep them as a legitimate alternate or
    delete them outright.

    Idempotent — only inserts an alias when one with the same
    (customer_name, 'email', alias_value) doesn't already exist.
    Returns the number of new alias rows inserted.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT DISTINCT
                  i.customer AS customer_name,
                  LOWER(TRIM(i.customer_email)) AS email
               FROM items i
               WHERE i.customer IS NOT NULL AND TRIM(i.customer) != ''
                 AND i.customer_email IS NOT NULL AND TRIM(i.customer_email) != ''
                 AND i.customer_id IS NOT NULL
                 AND LOWER(TRIM(i.customer_email)) != COALESCE(
                     (SELECT LOWER(e.email) FROM customer_emails e
                      WHERE e.customer_id = i.customer_id AND e.is_primary = 1
                      LIMIT 1),
                     ''
                 )
                 AND NOT EXISTS (
                     SELECT 1 FROM customer_aliases ca
                     WHERE ca.customer_name = i.customer
                       AND ca.alias_type = 'email'
                       AND LOWER(ca.alias_value) = LOWER(TRIM(i.customer_email))
                 )"""
        ).fetchall()

        inserted = 0
        for r in rows:
            try:
                conn.execute(
                    """INSERT INTO customer_aliases
                       (customer_name, alias_type, alias_value)
                       VALUES (?, 'email', ?)""",
                    (r["customer_name"], r["email"]),
                )
                inserted += 1
            except Exception:
                logger.warning(
                    "capture_email_aliases_from_items: failed for %s / %s",
                    r["customer_name"], r["email"], exc_info=True,
                )
        if inserted:
            conn.commit()
            logger.info(
                "Captured %d email aliases from historical items.customer_email rows",
                inserted,
            )
        return inserted


def repair_orphan_pay_children(db_path: str | Path | None = None) -> dict:
    """Heal +PAY child rows whose parent_item_id points to a row that no longer
    exists or that's stuck in 'rsvp_only' (the residue from a reverse-credit-
    application that ran before the Venmo balance-due cascade was fixed).

    For each orphan:
      - If the same customer has an active item in the same event, re-point
        parent_item_id at it (the +PAY rejoins the player's roster row).
      - Otherwise, convert the child into a standalone 'credited' item so the
        money the player paid stays on their account as a credit.

    Idempotent — only touches rows whose parents are missing or rsvp_only.
    Returns counts of repairs by category.
    """
    repaired = {"reattached": 0, "converted_to_credit": 0, "skipped": 0}
    with _connect(db_path) as conn:
        orphans = conn.execute(
            """SELECT c.* FROM items c
               WHERE c.parent_item_id IS NOT NULL
                 AND COALESCE(c.transaction_status, 'active') = 'active'
                 AND (
                     NOT EXISTS (SELECT 1 FROM items p WHERE p.id = c.parent_item_id)
                     OR EXISTS (
                         SELECT 1 FROM items p
                         WHERE p.id = c.parent_item_id
                           AND p.transaction_status IN ('rsvp_only', 'transferred')
                     )
                 )"""
        ).fetchall()
        if not orphans:
            return repaired

        for row in orphans:
            row = dict(row)
            child_id = row["id"]
            customer = row.get("customer") or ""
            event_name = row.get("item_name") or ""
            if not customer or not event_name:
                repaired["skipped"] += 1
                continue

            # Try to find an active sibling parent (same customer + event).
            sibling = conn.execute(
                """SELECT id FROM items
                   WHERE customer = ? COLLATE NOCASE
                     AND item_name = ? COLLATE NOCASE
                     AND COALESCE(transaction_status, 'active') = 'active'
                     AND parent_item_id IS NULL
                     AND id != ?
                   ORDER BY id DESC LIMIT 1""",
                (customer, event_name, child_id),
            ).fetchone()

            if sibling:
                conn.execute(
                    "UPDATE items SET parent_item_id = ? WHERE id = ?",
                    (sibling["id"], child_id),
                )
                # Re-point any expense_transaction that was tracking the orphan.
                conn.execute(
                    "UPDATE expense_transactions SET matched_item_id = ? WHERE matched_item_id = ?",
                    (child_id, child_id),  # no-op, but keeps the link consistent
                )
                repaired["reattached"] += 1
                logger.info(
                    "repair_orphan_pay_children: re-pointed item %s parent %s -> %s",
                    child_id, row.get("parent_item_id"), sibling["id"],
                )
                continue

            # No sibling parent — convert to standalone credited item so the
            # money the player paid stays on their account.
            price_amt = _parse_dollar(row.get("item_price"))
            if price_amt <= 0:
                conn.execute(
                    "UPDATE items SET parent_item_id = NULL WHERE id = ?",
                    (child_id,),
                )
                repaired["skipped"] += 1
                continue

            credit_note = (
                f"Credit from cancelled credit transfer — ${price_amt:.2f} from {event_name}"
            )
            conn.execute(
                """UPDATE items
                   SET parent_item_id = NULL,
                       transaction_status = 'credited',
                       credit_note = ?,
                       merchant = COALESCE(NULLIF(merchant, ''), 'Manual Entry')
                   WHERE id = ?""",
                (credit_note, child_id),
            )
            conn.execute(
                "UPDATE expense_transactions SET matched_item_id = NULL WHERE matched_item_id = ?",
                (child_id,),
            )
            repaired["converted_to_credit"] += 1
            logger.info(
                "repair_orphan_pay_children: converted item %s ($%.2f) to standalone credit",
                child_id, price_amt,
            )

        conn.commit()
        return repaired


def backfill_missing_godaddy_orders(db_path: str | Path | None = None) -> int:
    """Create order-level acct_transactions entries for GoDaddy orders that
    have items but no active 'godaddy-order-{id}' ledger row.

    Idempotent — only touches orders missing an active entry.  Use as a
    startup hook so events that arrived after the one-shot
    backfill_acct_transactions guard get their ledger entries automatically.
    """
    with _connect(db_path) as conn:
        missing = conn.execute(
            """SELECT DISTINCT i.order_id
               FROM items i
               WHERE i.merchant = 'The Golf Fellowship'
                 AND COALESCE(i.transaction_status, 'active') NOT IN
                     ('rsvp_only', 'credited', 'refunded', 'transferred')
                 AND i.parent_item_id IS NULL
                 AND i.transferred_from_id IS NULL
                 AND i.order_id IS NOT NULL
                 AND i.item_price IS NOT NULL
                 AND i.item_price NOT LIKE '$0.00%'
                 AND NOT EXISTS (
                     SELECT 1 FROM acct_transactions t
                     WHERE t.source_ref = 'godaddy-order-' || i.order_id
                       AND COALESCE(t.status, 'active') = 'active'
                 )"""
        ).fetchall()
        if not missing:
            return 0

        created = 0
        for row in missing:
            oid = row["order_id"]
            try:
                order_items = conn.execute(
                    """SELECT * FROM items
                       WHERE order_id = ? AND merchant = 'The Golf Fellowship'
                         AND COALESCE(transaction_status, 'active') NOT IN ('rsvp_only')
                         AND parent_item_id IS NULL
                         AND transferred_from_id IS NULL""",
                    (oid,),
                ).fetchall()
                valid_items = [
                    dict(r) for r in order_items
                    if _parse_dollar(dict(r).get("item_price")) > 0
                    and dict(r).get("transaction_status") not in ("credited", "refunded", "transferred")
                ]
                if not valid_items:
                    continue
                txn_id = _write_godaddy_order_entry(
                    conn,
                    order_id=oid,
                    items=valid_items,
                    date=valid_items[0].get("order_date") or "",
                )
                if txn_id:
                    created += 1
            except Exception:
                logger.warning(
                    "backfill_missing_godaddy_orders: failed for order %s", oid, exc_info=True
                )

        if created:
            conn.commit()
            logger.info(
                "Backfilled %d missing GoDaddy order entries", created,
            )
        return created


def backfill_acct_transactions(db_path: str | Path | None = None) -> dict:
    """Backfill flat acct_transactions entries for all 2026 items missing them.

    Processes items in order_date ascending.  Idempotent — uses source_ref to
    skip items that already have entries.  Returns counts of entries created.
    """
    results = {"godaddy_orders": 0, "godaddy_items": 0, "comps": 0,
               "external_payments": 0, "addons": 0, "transfers": 0,
               "refunds": 0, "wd_credits": 0, "errors": 0, "items_processed": 0}

    with _connect(db_path) as conn:
        # ── 1. GoDaddy orders — order-level entries with splits ──
        # Only 'The Golf Fellowship' merchant (actual GoDaddy orders).
        # Excludes transfer targets, manual entries, external payments, etc.
        gd_items = conn.execute(
            """SELECT * FROM items
               WHERE order_date >= '2026-01-01'
               AND merchant = 'The Golf Fellowship'
               AND COALESCE(transaction_status, 'active') NOT IN ('rsvp_only')
               AND parent_item_id IS NULL
               AND transferred_from_id IS NULL
               ORDER BY order_date ASC""",
        ).fetchall()

        # Group by order_id
        orders = defaultdict(list)
        for row in gd_items:
            item = dict(row)
            oid = item.get("order_id") or f"solo-{item['id']}"
            orders[oid].append(item)

        for oid, items in orders.items():
            valid_items = [
                i for i in items
                if _parse_dollar(i.get("item_price")) > 0
                and i.get("transaction_status") not in ("credited", "refunded", "transferred")
            ]
            if not valid_items:
                continue
            try:
                txn_id = _write_godaddy_order_entry(
                    conn,
                    order_id=oid,
                    items=valid_items,
                    date=valid_items[0].get("order_date") or "",
                )
                if txn_id:
                    results["godaddy_orders"] += 1
                    results["godaddy_items"] += len(valid_items)
                    results["items_processed"] += len(valid_items)
            except Exception:
                logger.warning("Backfill acct_txn: failed GoDaddy order %s", oid, exc_info=True)
                results["errors"] += 1

        # ── 2. Comps ──
        comp_items = conn.execute(
            """SELECT * FROM items
               WHERE order_date >= '2026-01-01'
               AND email_uid LIKE 'manual-comp%'
               AND COALESCE(transaction_status, 'active') != 'rsvp_only'
               AND id NOT IN (SELECT item_id FROM acct_transactions WHERE item_id IS NOT NULL AND entry_type = 'expense' AND category = 'comp')
               ORDER BY order_date ASC""",
        ).fetchall()
        for row in comp_items:
            try:
                item = dict(row)
                _write_acct_entry(
                    conn,
                    item_id=item["id"],
                    event_name=item.get("item_name", ""),
                    customer=item.get("customer", ""),
                    entry_type="expense",
                    category="comp",
                    source="manual",
                    amount=0,
                    description=f"Comp — course fee absorbed by TGF: {item.get('customer', '')} — {item.get('item_name', '')}",
                    account="TGF Checking",
                    source_ref=f"comp-{item['id']}",
                    date=item.get("order_date") or "",
                )
                results["comps"] += 1
            except Exception:
                logger.warning("Backfill acct_txn: failed comp item %s", row["id"], exc_info=True)
                results["errors"] += 1

        # ── 3. External payments (Paid Separately) ──
        ext_items = conn.execute(
            """SELECT * FROM items
               WHERE order_date >= '2026-01-01'
               AND merchant LIKE 'Paid Separately%'
               AND COALESCE(transaction_status, 'active') = 'active'
               AND parent_item_id IS NULL
               AND id NOT IN (SELECT item_id FROM acct_transactions WHERE item_id IS NOT NULL AND entry_type = 'income' AND category = 'addon')
               ORDER BY order_date ASC""",
        ).fetchall()
        for row in ext_items:
            try:
                item = dict(row)
                pay_amount = _parse_dollar(item.get("item_price"))
                if pay_amount <= 0:
                    continue
                source = (item.get("merchant") or "").replace("Paid Separately (", "").rstrip(")")
                pay_method = source.lower().replace(" ", "_")
                if pay_method not in ("venmo", "cash", "zelle", "check"):
                    pay_method = "cash"
                acct = "Venmo" if pay_method == "venmo" else "TGF Checking"
                _write_acct_entry(
                    conn,
                    item_id=item["id"],
                    event_name=item.get("item_name", ""),
                    customer=item.get("customer", ""),
                    entry_type="income",
                    category="addon",
                    source=pay_method,
                    amount=pay_amount,
                    description=f"External payment ({source}): {item.get('customer', '')} — {item.get('item_name', '')}",
                    account=acct,
                    source_ref=f"ext-pay-{item['id']}",
                    date=item.get("order_date") or "",
                )
                results["external_payments"] += 1
            except Exception:
                logger.warning("Backfill acct_txn: failed ext item %s", row["id"], exc_info=True)
                results["errors"] += 1

        # ── 4. Add-on child payments ──
        child_items = conn.execute(
            """SELECT * FROM items
               WHERE order_date >= '2026-01-01'
               AND parent_item_id IS NOT NULL
               AND COALESCE(transaction_status, 'active') = 'active'
               AND id NOT IN (SELECT item_id FROM acct_transactions WHERE item_id IS NOT NULL AND entry_type = 'income' AND category = 'addon')
               ORDER BY order_date ASC""",
        ).fetchall()
        for row in child_items:
            try:
                item = dict(row)
                pay_amount = _parse_dollar(item.get("item_price"))
                if pay_amount <= 0:
                    continue  # Skip negative (refund) child items — handled separately
                source = (item.get("merchant") or "").replace("Manual Entry (", "").rstrip(")")
                pay_method = source.lower().replace(" ", "_")
                if pay_method not in ("venmo", "cash", "zelle", "check", "godaddy"):
                    pay_method = "cash"
                acct = "Venmo" if pay_method == "venmo" else "TGF Checking"
                _write_acct_entry(
                    conn,
                    item_id=item["id"],
                    event_name=item.get("item_name", ""),
                    customer=item.get("customer", ""),
                    entry_type="income",
                    category="addon",
                    source=pay_method,
                    amount=pay_amount,
                    description=f"Add-on payment: {item.get('customer', '')} — {item.get('item_name', '')}",
                    account=acct,
                    source_ref=f"addon-{item['id']}",
                    date=item.get("order_date") or "",
                )
                results["addons"] += 1
            except Exception:
                logger.warning("Backfill acct_txn: failed child item %s", row["id"], exc_info=True)
                results["errors"] += 1

        # ── 5. Credit transfers ──
        xfer_items = conn.execute(
            """SELECT i.*, i2.id as target_item_id, i2.item_name as target_event
               FROM items i
               JOIN items i2 ON i2.transferred_from_id = i.id
               WHERE i.transaction_status = 'transferred'
               AND i.order_date >= '2026-01-01'
               ORDER BY i.order_date ASC""",
        ).fetchall()
        for row in xfer_items:
            try:
                item = dict(row)
                orig_price = _parse_dollar(item.get("item_price"))
                if orig_price <= 0:
                    continue
                source_event = item.get("item_name", "")
                target_event = item.get("target_event", "")

                _write_acct_entry(
                    conn,
                    item_id=item["id"],
                    event_name=source_event,
                    customer=item.get("customer", ""),
                    order_id=item.get("order_id", ""),
                    entry_type="contra",
                    category="transfer_out",
                    source="godaddy",
                    amount=orig_price,
                    description=f"Credit transfer out: {item.get('customer', '')} from {source_event} to {target_event}",
                    account="TGF Checking",
                    source_ref=f"xfer-flat-{item['id']}-out",
                    date=item.get("order_date") or "",
                )
                _write_acct_entry(
                    conn,
                    item_id=item["target_item_id"],
                    event_name=target_event,
                    customer=item.get("customer", ""),
                    entry_type="income",
                    category="transfer_in",
                    source="godaddy",
                    amount=orig_price,
                    description=f"Credit transfer in: {item.get('customer', '')} to {target_event} from {source_event}",
                    account="TGF Checking",
                    source_ref=f"xfer-flat-{item['id']}-in",
                    date=item.get("order_date") or "",
                )
                results["transfers"] += 1
            except Exception:
                logger.warning("Backfill acct_txn: failed xfer item %s", row["id"], exc_info=True)
                results["errors"] += 1

        # ── 6. Refunds ──
        refund_items = conn.execute(
            """SELECT * FROM items
               WHERE transaction_status = 'refunded'
               AND order_date >= '2026-01-01'
               AND id NOT IN (SELECT item_id FROM acct_transactions WHERE item_id IS NOT NULL AND entry_type = 'expense' AND category = 'refund')
               ORDER BY order_date ASC""",
        ).fetchall()
        for row in refund_items:
            try:
                item = dict(row)
                refund_amount = _parse_dollar(item.get("item_price"))
                if refund_amount <= 0:
                    continue
                credit_note = item.get("credit_note") or ""
                method = "manual"
                if "venmo" in credit_note.lower():
                    method = "venmo"
                elif "zelle" in credit_note.lower():
                    method = "zelle"
                elif "godaddy" in credit_note.lower():
                    method = "godaddy"
                refund_account = "Venmo" if method == "venmo" else "TGF Checking"
                _write_acct_entry(
                    conn,
                    item_id=item["id"],
                    event_name=item.get("item_name", ""),
                    customer=item.get("customer", ""),
                    order_id=item.get("order_id", ""),
                    entry_type="expense",
                    category="refund",
                    source=method,
                    amount=refund_amount,
                    description=f"Refund: {item.get('customer', '')} — {item.get('item_name', '')}",
                    account=refund_account,
                    source_ref=f"refund-flat-{item['id']}",
                    date=item.get("order_date") or "",
                )
                results["refunds"] += 1
            except Exception:
                logger.warning("Backfill acct_txn: failed refund item %s", row["id"], exc_info=True)
                results["errors"] += 1

        # ── 7. WD credits (liability) ──
        wd_items = conn.execute(
            """SELECT * FROM items
               WHERE transaction_status = 'wd'
               AND credit_amount IS NOT NULL AND credit_amount != ''
               AND order_date >= '2026-01-01'
               AND id NOT IN (SELECT item_id FROM acct_transactions WHERE item_id IS NOT NULL AND entry_type = 'liability' AND category = 'credit_issued')
               ORDER BY order_date ASC""",
        ).fetchall()
        for row in wd_items:
            try:
                item = dict(row)
                wd_credit_val = _parse_dollar(item.get("credit_amount"))
                if wd_credit_val <= 0:
                    continue
                _write_acct_entry(
                    conn,
                    item_id=item["id"],
                    event_name=item.get("item_name", ""),
                    customer=item.get("customer", ""),
                    order_id=item.get("order_id", ""),
                    entry_type="liability",
                    category="credit_issued",
                    source="manual",
                    amount=wd_credit_val,
                    description=f"WD credit issued: {item.get('customer', '')} — {item.get('item_name', '')}",
                    account="TGF Checking",
                    source_ref=f"wd-credit-{item['id']}",
                    date=item.get("order_date") or "",
                )
                results["wd_credits"] += 1
            except Exception:
                logger.warning("Backfill acct_txn: failed WD item %s", row["id"], exc_info=True)
                results["errors"] += 1

        # ── 8. Partial refunds (negative child items) ──
        neg_children = conn.execute(
            """SELECT * FROM items
               WHERE parent_item_id IS NOT NULL
               AND COALESCE(transaction_status, 'active') = 'active'
               AND order_date >= '2026-01-01'
               AND item_price LIKE '-%'
               AND id NOT IN (SELECT item_id FROM acct_transactions WHERE item_id IS NOT NULL AND entry_type = 'expense' AND category = 'refund')
               ORDER BY order_date ASC""",
        ).fetchall()
        for row in neg_children:
            try:
                item = dict(row)
                refund_amount = abs(_parse_dollar(item.get("item_price")))
                if refund_amount <= 0:
                    continue
                merchant = item.get("merchant") or ""
                method = "manual"
                if "venmo" in merchant.lower():
                    method = "venmo"
                elif "zelle" in merchant.lower():
                    method = "zelle"
                elif "godaddy" in merchant.lower():
                    method = "godaddy"
                refund_account = "Venmo" if method == "venmo" else "TGF Checking"
                _write_acct_entry(
                    conn,
                    item_id=item["id"],
                    event_name=item.get("item_name", ""),
                    customer=item.get("customer", ""),
                    entry_type="expense",
                    category="refund",
                    source=method,
                    amount=refund_amount,
                    description=f"Partial refund: {item.get('customer', '')} — {item.get('item_name', '')}",
                    account=refund_account,
                    source_ref=f"partial-refund-{item['id']}",
                    date=item.get("order_date") or "",
                )
                results["refunds"] += 1
            except Exception:
                logger.warning("Backfill acct_txn: failed negative child %s", row["id"], exc_info=True)
                results["errors"] += 1

        conn.commit()

    total_entries = sum(v for k, v in results.items() if k not in ("errors", "items_processed"))
    results["total_entries"] = total_entries
    logger.info("Backfilled %d accounting entries for %d items", total_entries, results["items_processed"])
    return results


def migrate_item_to_order_entries(db_path: str | Path | None = None) -> dict:
    """Migrate old per-item GoDaddy entries to order-level entries.

    Old format: 2 entries per item
      - source_ref = 'godaddy-income-{item_id}', category='registration'
      - source_ref = 'godaddy-fee-{item_id}', category='processing_fee'

    New format: 1 entry per order
      - source_ref = 'godaddy-order-{order_id}', category='godaddy_order'
      - child rows in godaddy_order_splits

    Creates a backup before any changes.  Preserves reconciliation_matches by
    re-linking them from old income entries to the new order entry.

    Idempotent: skips orders that already have a 'godaddy-order-*' entry.
    """
    backup_path = backup_database(db_path, label="pre-order-migration")
    logger.info("Migration backup created: %s", backup_path)

    results = {
        "orders_migrated": 0,
        "old_entries_reversed": 0,
        "matches_relinked": 0,
        "skipped_already_migrated": 0,
        "errors": 0,
        "backup_path": backup_path,
    }

    with _connect(db_path) as conn:
        # Find all old-format per-item income entries
        old_income = conn.execute(
            """SELECT at.*, i.order_id
               FROM acct_transactions at
               JOIN items i ON i.id = at.item_id
               WHERE at.source_ref LIKE 'godaddy-income-%'
               AND at.category = 'registration'
               AND COALESCE(at.status, 'active') = 'active'
               ORDER BY at.date ASC""",
        ).fetchall()

        if not old_income:
            logger.info("No old-format per-item GoDaddy entries found — nothing to migrate.")
            return results

        # Group old income entries by order_id
        orders_to_migrate = defaultdict(list)
        for row in old_income:
            r = dict(row)
            oid = r.get("order_id") or f"solo-{r['item_id']}"
            orders_to_migrate[oid].append(r)

        for oid, old_entries in orders_to_migrate.items():
            # Skip if already migrated
            existing_order = conn.execute(
                "SELECT id FROM acct_transactions WHERE source_ref = ? AND COALESCE(status, 'active') = 'active'",
                (f"godaddy-order-{oid}",),
            ).fetchone()
            if existing_order:
                results["skipped_already_migrated"] += 1
                continue

            try:
                # Gather item_ids from old entries
                item_ids = [e["item_id"] for e in old_entries if e.get("item_id")]
                if not item_ids:
                    continue

                # Fetch full item data for these items
                placeholders = ",".join(["?"] * len(item_ids))
                items = [
                    dict(r) for r in conn.execute(
                        f"SELECT * FROM items WHERE id IN ({placeholders})", item_ids
                    ).fetchall()
                ]
                valid_items = [
                    i for i in items
                    if _parse_dollar(i.get("item_price")) > 0
                    and i.get("transaction_status") not in ("credited", "refunded", "transferred")
                ]
                if not valid_items:
                    continue

                # Collect reconciliation_matches from old income entries before reversing
                old_income_ids = [e["id"] for e in old_entries]
                old_fee_ids = []
                for iid in item_ids:
                    fee_row = conn.execute(
                        "SELECT id FROM acct_transactions WHERE source_ref = ? AND COALESCE(status, 'active') = 'active'",
                        (f"godaddy-fee-{iid}",),
                    ).fetchone()
                    if fee_row:
                        old_fee_ids.append(fee_row[0])

                all_old_ids = old_income_ids + old_fee_ids
                old_id_placeholders = ",".join(["?"] * len(all_old_ids))
                saved_matches = conn.execute(
                    f"""SELECT bank_deposit_id, match_type, match_confidence, created_at
                        FROM reconciliation_matches
                        WHERE acct_transaction_id IN ({old_id_placeholders})""",
                    all_old_ids,
                ).fetchall()

                # Soft-delete old income entries
                for eid in old_income_ids:
                    conn.execute("UPDATE acct_transactions SET status = 'reversed' WHERE id = ?", (eid,))
                    results["old_entries_reversed"] += 1

                # Soft-delete old fee entries
                for fid in old_fee_ids:
                    conn.execute("UPDATE acct_transactions SET status = 'reversed' WHERE id = ?", (fid,))
                    results["old_entries_reversed"] += 1

                # Remove old reconciliation_matches (will re-link to new entry)
                if all_old_ids:
                    conn.execute(
                        f"DELETE FROM reconciliation_matches WHERE acct_transaction_id IN ({old_id_placeholders})",
                        all_old_ids,
                    )

                # Create new order-level entry
                txn_id = _write_godaddy_order_entry(
                    conn,
                    order_id=oid,
                    items=valid_items,
                    date=valid_items[0].get("order_date") or "",
                )

                if txn_id:
                    results["orders_migrated"] += 1

                    # Re-link saved reconciliation_matches to new entry
                    for match in saved_matches:
                        try:
                            conn.execute(
                                """INSERT OR IGNORE INTO reconciliation_matches
                                   (bank_deposit_id, acct_transaction_id, match_type, match_confidence, created_at)
                                   VALUES (?, ?, ?, ?, ?)""",
                                (match[0], txn_id, match[1], match[2], match[3]),
                            )
                            results["matches_relinked"] += 1
                        except Exception:
                            pass  # duplicate or constraint — safe to skip

            except Exception:
                logger.warning("Migration failed for order %s", oid, exc_info=True)
                results["errors"] += 1

        conn.commit()

    logger.info(
        "Migration complete: %d orders migrated, %d old entries reversed, %d matches relinked, %d skipped, %d errors",
        results["orders_migrated"], results["old_entries_reversed"],
        results["matches_relinked"], results["skipped_already_migrated"], results["errors"],
    )
    return results


def cleanup_duplicate_godaddy_entries(db_path: str | Path | None = None) -> dict:
    """Reverse old per-item GoDaddy entries superseded by order-level entries.

    The existing migrate_item_to_order_entries() skips orders that already have a
    godaddy-order-{order_id} entry.  This function handles those skipped cases:
    it finds old-style 'GoDaddy registration:' / 'GoDaddy merchant fee:' entries
    (or source_ref godaddy-income-* / godaddy-fee-*) that coexist with a new
    order-level entry and reverses them.  For orders with no order-level entry,
    it creates one then reverses the old per-item entries.

    Safe to run multiple times (idempotent).
    """
    results = {
        "reversed_duplicates": 0,
        "migrated_then_reversed": 0,
        "skipped": 0,
        "errors": 0,
    }

    with _connect(db_path) as conn:
        old_entries = conn.execute(
            """SELECT t.*, i.order_id
               FROM acct_transactions t
               LEFT JOIN items i ON i.id = t.item_id
               WHERE COALESCE(t.status, 'active') = 'active'
               AND (
                   t.source_ref LIKE 'godaddy-income-%'
                   OR t.source_ref LIKE 'godaddy-fee-%'
                   OR t.description LIKE 'GoDaddy registration:%'
                   OR t.description LIKE 'GoDaddy merchant fee:%'
               )
               ORDER BY t.date ASC""",
        ).fetchall()

        if not old_entries:
            return results

        by_order: dict = defaultdict(list)
        no_order = []
        for row in old_entries:
            r = dict(row)
            oid = r.get("order_id")
            if oid:
                by_order[oid].append(r)
            else:
                no_order.append(r)

        for oid, entries in by_order.items():
            try:
                existing = conn.execute(
                    "SELECT id FROM acct_transactions WHERE source_ref = ? AND COALESCE(status, 'active') != 'reversed'",
                    (f"godaddy-order-{oid}",),
                ).fetchone()

                if existing:
                    for e in entries:
                        conn.execute(
                            "UPDATE acct_transactions SET status = 'reversed' WHERE id = ?",
                            (e["id"],),
                        )
                        results["reversed_duplicates"] += 1
                else:
                    item_ids = [e["item_id"] for e in entries if e.get("item_id")]
                    if not item_ids:
                        results["skipped"] += len(entries)
                        continue
                    placeholders = ",".join(["?"] * len(item_ids))
                    items = [
                        dict(r) for r in conn.execute(
                            f"SELECT * FROM items WHERE id IN ({placeholders})", item_ids
                        ).fetchall()
                    ]
                    valid_items = [
                        i for i in items
                        if _parse_dollar(i.get("item_price")) > 0
                        and i.get("transaction_status") not in ("credited", "refunded", "transferred")
                    ]
                    if valid_items:
                        date = valid_items[0].get("order_date") or entries[0]["date"]
                        _write_godaddy_order_entry(conn, order_id=oid, items=valid_items, date=date)
                    for e in entries:
                        conn.execute(
                            "UPDATE acct_transactions SET status = 'reversed' WHERE id = ?",
                            (e["id"],),
                        )
                        results["migrated_then_reversed"] += 1
            except Exception:
                logger.warning("Cleanup duplicate GoDaddy: failed order %s", oid, exc_info=True)
                results["errors"] += 1

        # Entries without a linked order_id — just reverse them
        for e in no_order:
            try:
                conn.execute(
                    "UPDATE acct_transactions SET status = 'reversed' WHERE id = ?",
                    (e["id"],),
                )
                results["skipped"] += 1
            except Exception:
                results["errors"] += 1

        conn.commit()

    logger.info(
        "GoDaddy cleanup: %d reversed (order existed), %d migrated+reversed, %d skipped, %d errors",
        results["reversed_duplicates"], results["migrated_then_reversed"],
        results["skipped"], results["errors"],
    )
    return results


# ═══════════════════════════════════════════════════════════════════════════
# Expense Transactions & Action Items CRUD
# ═══════════════════════════════════════════════════════════════════════════

def get_blocked_merchants(db_path: str | Path | None = None) -> list[str]:
    """Return list of lower-cased merchant names that are permanently blocked."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = 'expense_blocked_merchants'"
        ).fetchone()
    if not row:
        return []
    try:
        return json.loads(row["value"]) or []
    except Exception:
        return []


def block_merchant(merchant: str, db_path: str | Path | None = None) -> list[str]:
    """Add merchant to the permanent block list. Returns updated list."""
    normalized = merchant.strip().lower()
    if not normalized:
        return get_blocked_merchants(db_path)
    blocked = get_blocked_merchants(db_path)
    if normalized not in blocked:
        blocked.append(normalized)
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO app_settings (key, value) VALUES ('expense_blocked_merchants', ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (json.dumps(blocked),),
        )
        conn.commit()
    return blocked


def save_expense_transaction(data: dict, db_path: str | Path | None = None) -> dict:
    """Insert or update an expense transaction. Returns the saved record.

    Dedup strategy (in priority order):
    1. email_uid match — exact ON CONFLICT upsert
    2. Content match — (source_type, merchant, amount, transaction_date) already exists
       → update existing row so the same real-world transaction never appears twice
    3. Insert new row
    """
    # Auto-ignore blocked merchants so they never surface as pending
    merchant_name = (data.get("merchant") or "").strip().lower()
    if merchant_name and merchant_name in get_blocked_merchants(db_path):
        data = {**data, "review_status": "ignored"}

    with _connect(db_path) as conn:
        email_uid = data.get("email_uid")

        # Try email_uid upsert when uid is present
        if email_uid is not None:
            conn.execute(
                """INSERT INTO expense_transactions
                   (email_uid, source_type, merchant, amount, transaction_date,
                    account_last4, account_name, transaction_type, category, entity,
                    event_name, customer_id, confidence, review_status, notes, raw_extract,
                    other_party_handle)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(email_uid) DO UPDATE SET
                    merchant=excluded.merchant, amount=excluded.amount,
                    transaction_date=excluded.transaction_date,
                    account_last4=excluded.account_last4, account_name=excluded.account_name,
                    transaction_type=excluded.transaction_type, category=excluded.category,
                    entity=excluded.entity, event_name=excluded.event_name,
                    customer_id=excluded.customer_id, confidence=excluded.confidence,
                    review_status=CASE WHEN expense_transactions.review_status IN ('ignored','approved','corrected')
                                       THEN expense_transactions.review_status
                                       ELSE excluded.review_status END,
                    notes=excluded.notes,
                    raw_extract=excluded.raw_extract,
                    other_party_handle=COALESCE(expense_transactions.other_party_handle, excluded.other_party_handle)""",
                (email_uid, data.get("source_type"), data.get("merchant"),
                 data.get("amount"), data.get("transaction_date"),
                 data.get("account_last4"), data.get("account_name"),
                 data.get("transaction_type", "expense"), data.get("category"),
                 data.get("entity", "TGF"), data.get("event_name"),
                 data.get("customer_id"), data.get("confidence", 0),
                 data.get("review_status", "pending"), data.get("notes"),
                 data.get("raw_extract"), data.get("other_party_handle")),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM expense_transactions WHERE email_uid = ?", (email_uid,)
            ).fetchone()
            return dict(row) if row else data

        # No email_uid — check content-based dedup before inserting
        existing = conn.execute(
            """SELECT id FROM expense_transactions
               WHERE source_type = ?
                 AND LOWER(COALESCE(merchant, '')) = LOWER(COALESCE(?, ''))
                 AND amount = ?
                 AND transaction_date = ?
               LIMIT 1""",
            (data.get("source_type"), data.get("merchant"),
             data.get("amount"), data.get("transaction_date")),
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE expense_transactions SET
                    account_last4=?, account_name=?, transaction_type=?, category=?,
                    entity=?, event_name=?, customer_id=?, confidence=?,
                    review_status=CASE WHEN review_status IN ('ignored','approved','corrected')
                                       THEN review_status ELSE ? END,
                    notes=?, raw_extract=?
                   WHERE id = ?""",
                (data.get("account_last4"), data.get("account_name"),
                 data.get("transaction_type", "expense"), data.get("category"),
                 data.get("entity", "TGF"), data.get("event_name"),
                 data.get("customer_id"), data.get("confidence", 0),
                 data.get("review_status", "pending"), data.get("notes"),
                 data.get("raw_extract"), existing["id"]),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM expense_transactions WHERE id = ?", (existing["id"],)
            ).fetchone()
            return dict(row) if row else data

        # Genuinely new record
        conn.execute(
            """INSERT INTO expense_transactions
               (email_uid, source_type, merchant, amount, transaction_date,
                account_last4, account_name, transaction_type, category, entity,
                event_name, customer_id, confidence, review_status, notes, raw_extract)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (email_uid, data.get("source_type"), data.get("merchant"),
             data.get("amount"), data.get("transaction_date"),
             data.get("account_last4"), data.get("account_name"),
             data.get("transaction_type", "expense"), data.get("category"),
             data.get("entity", "TGF"), data.get("event_name"),
             data.get("customer_id"), data.get("confidence", 0),
             data.get("review_status", "pending"), data.get("notes"),
             data.get("raw_extract")),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM expense_transactions ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else data


def get_expense_transactions(date_from: str | None = None, date_to: str | None = None,
                             source_type: str | None = None,
                             review_status: str | None = None,
                             event_name: str | None = None, limit: int = 100,
                             db_path: str | Path | None = None) -> list[dict]:
    clauses, params = [], []
    if date_from:
        clauses.append("transaction_date >= ?"); params.append(date_from)
    if date_to:
        clauses.append("transaction_date <= ?"); params.append(date_to)
    if source_type:
        clauses.append("source_type = ?"); params.append(source_type)
    if review_status:
        clauses.append("review_status = ?"); params.append(review_status)
    if event_name:
        clauses.append("event_name = ? COLLATE NOCASE"); params.append(event_name)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM expense_transactions{where} ORDER BY transaction_date DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    return [dict(r) for r in rows]


def _sync_expense_ledger_entry(conn, exp: dict) -> int | None:
    """Create or update the acct_transactions row linked to an expense_transaction.

    Called whenever an expense is saved in approved/corrected state.  Returns
    the acct_transaction id (new or existing), or None if amount is missing.
    """
    amount = float(exp.get("amount") or 0)
    if not amount:
        return None
    merchant = exp.get("merchant") or "(unknown)"
    txn_date = exp.get("transaction_date") or datetime.utcnow().strftime("%Y-%m-%d")
    raw_txn_type = exp.get("transaction_type") or "expense"
    # acct_transactions.type has a CHECK constraint: only income/expense/transfer.
    # Map the raw expense_transactions.transaction_type (which can be 'received',
    # 'payout', etc.) to one of the three allowed values. Without this every
    # Venmo "received" promotion failed with a CHECK constraint error and the
    # ledger sync silently lost rows.
    _type_map = {
        "received": "income",
        "payout": "expense",
        "expense": "expense",
        "transfer": "transfer",
    }
    txn_type = _type_map.get(raw_txn_type, "expense")
    source = exp.get("source_type") or "expense_alert"
    expense_id = exp["id"]
    source_ref = f"exp-promoted-{expense_id}"
    notes = exp.get("notes")
    customer_id = exp.get("customer_id")
    account_id = exp.get("account_id")
    category_name = exp.get("category")
    entity_name = exp.get("entity")
    event_name = exp.get("event_name")

    # Resolve FKs
    category_id = None
    if category_name:
        row = conn.execute(
            "SELECT id FROM acct_categories WHERE LOWER(name) = LOWER(?) LIMIT 1",
            (category_name,),
        ).fetchone()
        category_id = row["id"] if row else None

    entity_id = None
    if entity_name:
        row = conn.execute(
            "SELECT id FROM acct_entities WHERE LOWER(short_name) = LOWER(?) OR LOWER(name) = LOWER(?) LIMIT 1",
            (entity_name, entity_name),
        ).fetchone()
        entity_id = row["id"] if row else None

    event_id = None
    if event_name:
        row = conn.execute(
            "SELECT id FROM events WHERE LOWER(item_name) = LOWER(?) LIMIT 1",
            (event_name,),
        ).fetchone()
        event_id = row["id"] if row else None

    if not account_id:
        row = conn.execute(
            "SELECT id FROM acct_accounts WHERE account_type = 'checking' AND is_active = 1 LIMIT 1"
        ).fetchone()
        account_id = row["id"] if row else None

    existing_id = exp.get("acct_transaction_id")

    # entry_type drives reconciliation matching and P&L classification.
    # Venmo "received" rows are inbound payments (income); everything else
    # (expense / payout / transfer) is an outflow.
    entry_type = "income" if txn_type == "received" else "expense"

    if existing_id:
        conn.execute(
            """UPDATE acct_transactions
               SET date=?, description=?, total_amount=?, amount=?, type=?, entry_type=?,
                   account_id=?, notes=?, customer_id=?, updated_at=datetime('now')
               WHERE id=?""",
            (txn_date, merchant, amount, amount, txn_type, entry_type,
             account_id, notes, customer_id, existing_id),
        )
        split = conn.execute(
            "SELECT id FROM acct_splits WHERE transaction_id = ? LIMIT 1", (existing_id,)
        ).fetchone()
        if split:
            conn.execute(
                "UPDATE acct_splits SET entity_id=?, category_id=?, amount=?, event_id=? WHERE id=?",
                (entity_id, category_id, amount, event_id, split["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO acct_splits (transaction_id, entity_id, category_id, amount, event_id) VALUES (?,?,?,?,?)",
                (existing_id, entity_id, category_id, amount, event_id),
            )
        return existing_id
    else:
        cur = conn.execute(
            """INSERT INTO acct_transactions
               (date, description, total_amount, amount, type, entry_type,
                account_id, source, source_ref, notes, customer_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (txn_date, merchant, amount, amount, txn_type, entry_type,
             account_id, source, source_ref, notes, customer_id),
        )
        new_id = cur.lastrowid
        conn.execute(
            "INSERT INTO acct_splits (transaction_id, entity_id, category_id, amount, event_id) VALUES (?,?,?,?,?)",
            (new_id, entity_id, category_id, amount, event_id),
        )
        conn.execute(
            "UPDATE expense_transactions SET acct_transaction_id = ? WHERE id = ?",
            (new_id, expense_id),
        )
        return new_id


def update_expense_transaction(txn_id: int, fields: dict,
                               db_path: str | Path | None = None) -> dict:
    """Update expense transaction and record corrections for learning."""
    allowed = {"merchant", "amount", "transaction_date", "account_last4", "account_name",
               "account_id", "transaction_type", "category", "entity", "event_name",
               "customer_id", "review_status", "reviewed_at", "reviewed_by", "notes"}
    safe = {k: v for k, v in fields.items() if k in allowed}
    if not safe:
        return {}
    with _connect(db_path) as conn:
        original = conn.execute(
            "SELECT * FROM expense_transactions WHERE id = ?", (txn_id,)
        ).fetchone()
        if original:
            original = dict(original)
            for field, new_val in safe.items():
                old_val = original.get(field)
                if old_val != new_val and field in ("category", "entity", "event_name"):
                    conn.execute(
                        """INSERT INTO extraction_corrections
                           (expense_transaction_id, field_corrected, original_value,
                            corrected_value, merchant) VALUES (?, ?, ?, ?, ?)""",
                        (txn_id, field, str(old_val) if old_val else None,
                         str(new_val) if new_val else None, original.get("merchant")),
                    )
        set_clause = ", ".join(f"{k} = ?" for k in safe)
        conn.execute(f"UPDATE expense_transactions SET {set_clause} WHERE id = ?",
                     (*safe.values(), txn_id))

        # Auto-resolve account_id FK when account_name or account_last4 changes
        if 'account_name' in safe or 'account_last4' in safe:
            row = conn.execute(
                "SELECT account_name, account_last4 FROM expense_transactions WHERE id = ?",
                (txn_id,)
            ).fetchone()
            if row:
                last4 = row["account_last4"]
                name = row["account_name"]
                acct = None
                if last4:
                    acct = conn.execute(
                        "SELECT id FROM acct_accounts WHERE last_four = ? LIMIT 1", (last4,)
                    ).fetchone()
                if not acct and name:
                    acct = conn.execute(
                        "SELECT id FROM acct_accounts WHERE UPPER(name) = UPPER(?) LIMIT 1", (name,)
                    ).fetchone()
                if acct:
                    conn.execute(
                        "UPDATE expense_transactions SET account_id = ? WHERE id = ?",
                        (acct["id"], txn_id)
                    )

        # Auto-learn: create keyword rule when expense is approved with category
        if safe.get("review_status") in ("approved", "corrected"):
            merchant = original.get("merchant", "") if original else ""
            cat_name = safe.get("category") or (original.get("category") if original else None)
            ent_name = safe.get("entity") or (original.get("entity") if original else None)
            if merchant and cat_name:
                # Look up category_id and entity_id by name
                cat_row = conn.execute(
                    "SELECT id FROM acct_categories WHERE name = ? COLLATE NOCASE LIMIT 1",
                    (cat_name,)
                ).fetchone()
                ent_row = conn.execute(
                    "SELECT id FROM acct_entities WHERE short_name = ? COLLATE NOCASE LIMIT 1",
                    (ent_name,)
                ).fetchone() if ent_name else None
                cat_id = cat_row["id"] if cat_row else None
                ent_id = ent_row["id"] if ent_row else None
                if cat_id:
                    # Check if a rule already exists for this merchant
                    existing_rule = conn.execute(
                        "SELECT id FROM acct_keyword_rules WHERE UPPER(keyword) = UPPER(?) LIMIT 1",
                        (merchant.strip(),)
                    ).fetchone()
                    if not existing_rule:
                        conn.execute(
                            """INSERT INTO acct_keyword_rules
                               (keyword, match_type, category_id, entity_id)
                               VALUES (?, 'contains', ?, ?)""",
                            (merchant.strip(), cat_id, ent_id),
                        )

        conn.commit()

        # Sync approved expenses into the main ledger for reconciliation
        fresh = conn.execute(
            "SELECT * FROM expense_transactions WHERE id = ?", (txn_id,)
        ).fetchone()
        if fresh:
            fresh_dict = dict(fresh)
            if fresh_dict.get("review_status") in ("approved", "corrected"):
                try:
                    _sync_expense_ledger_entry(conn, fresh_dict)
                    conn.commit()
                except Exception:
                    logger.warning("_sync_expense_ledger_entry failed for expense %s", txn_id, exc_info=True)

        row = conn.execute("SELECT * FROM expense_transactions WHERE id = ?", (txn_id,)).fetchone()
    return dict(row) if row else {}


def save_action_item(data: dict, db_path: str | Path | None = None) -> dict:
    """Insert a new action item, skipping if a similar open item already exists.

    Dedup checks (in order):
    1. Same email_uid (if provided)
    2. Same subject + category with status 'open' or 'in_progress'
    """
    with _connect(db_path) as conn:
        # Dedup: exact email_uid match
        uid = data.get("email_uid")
        if uid:
            existing = conn.execute(
                "SELECT id FROM action_items WHERE email_uid = ? LIMIT 1", (uid,)
            ).fetchone()
            if existing:
                row = conn.execute("SELECT * FROM action_items WHERE id = ?", (existing["id"],)).fetchone()
                return dict(row) if row else data

        # Dedup: same subject + category still open
        subject = (data.get("subject") or "").strip()
        category = data.get("category", "other")
        if subject:
            existing = conn.execute(
                """SELECT id FROM action_items
                   WHERE subject = ? AND category = ? AND status IN ('open', 'in_progress')
                   LIMIT 1""",
                (subject, category),
            ).fetchone()
            if existing:
                row = conn.execute("SELECT * FROM action_items WHERE id = ?", (existing["id"],)).fetchone()
                return dict(row) if row else data

        cur = conn.execute(
            """INSERT INTO action_items
               (email_uid, subject, from_name, from_email, summary, urgency,
                category, email_date, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (uid, subject, data.get("from_name"),
             data.get("from_email"), data.get("summary"), data.get("urgency", "medium"),
             category, data.get("email_date"),
             data.get("confidence", 0)),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM action_items WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row) if row else data


def get_action_items(status: str | None = None, category: str | None = None,
                     limit: int = 200, db_path: str | Path | None = None) -> list[dict]:
    clauses, params = [], []
    if status:
        clauses.append("status = ?"); params.append(status)
    if category:
        clauses.append("category = ?"); params.append(category)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM action_items{where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    return [dict(r) for r in rows]


def update_action_item(item_id: int, fields: dict,
                       db_path: str | Path | None = None) -> dict:
    allowed = {"status", "completed_at", "completed_by", "resolution_notes"}
    safe = {k: v for k, v in fields.items() if k in allowed}
    if not safe:
        return {}
    set_clause = ", ".join(f"{k} = ?" for k in safe)
    with _connect(db_path) as conn:
        conn.execute(f"UPDATE action_items SET {set_clause} WHERE id = ?",
                     (*safe.values(), item_id))
        conn.commit()
        row = conn.execute("SELECT * FROM action_items WHERE id = ?", (item_id,)).fetchone()
    return dict(row) if row else {}


def batch_dismiss_action_items(item_ids: list[int] | None = None,
                               category: str | None = None,
                               status_filter: str = "open",
                               db_path: str | Path | None = None) -> dict:
    """Batch dismiss action items by IDs or by category.

    If item_ids provided, dismisses those specific items.
    If category provided (and no item_ids), dismisses all open items in that category.
    """
    with _connect(db_path) as conn:
        if item_ids:
            placeholders = ",".join("?" * len(item_ids))
            count = conn.execute(
                f"UPDATE action_items SET status = 'dismissed' WHERE id IN ({placeholders}) AND status = ?",
                (*item_ids, status_filter),
            ).rowcount
        elif category:
            count = conn.execute(
                "UPDATE action_items SET status = 'dismissed' WHERE category = ? AND status = ?",
                (category, status_filter),
            ).rowcount
        else:
            count = conn.execute(
                "UPDATE action_items SET status = 'dismissed' WHERE status = ?",
                (status_filter,),
            ).rowcount
        conn.commit()
    return {"dismissed": count}


def consolidate_action_items(db_path: str | Path | None = None) -> dict:
    """Find and dismiss duplicate/similar open action items.

    Keeps the newest item in each group, dismisses older duplicates.
    Groups by: same subject, or similar subject (first 40 chars + same category).
    """
    with _connect(db_path) as conn:
        # Get all open items
        items = conn.execute(
            """SELECT id, subject, category, from_name, created_at
               FROM action_items WHERE status = 'open'
               ORDER BY created_at DESC"""
        ).fetchall()

        if not items:
            return {"consolidated": 0, "groups": 0}

        # Group by exact subject + category
        groups = {}
        for item in items:
            key = ((item["subject"] or "").strip().lower(), (item["category"] or ""))
            if key not in groups:
                groups[key] = []
            groups[key].append(item)

        # Also group by subject prefix (first 40 chars) + category for near-duplicates
        prefix_groups = {}
        for item in items:
            subj = (item["subject"] or "").strip().lower()
            prefix = subj[:40] if len(subj) > 40 else subj
            key = (prefix, (item["category"] or ""))
            if key not in prefix_groups:
                prefix_groups[key] = []
            prefix_groups[key].append(item)

        # Merge prefix groups into main groups (prefer larger groups)
        for key, members in prefix_groups.items():
            if len(members) > 1:
                # Check if any exact group already covers these
                covered = False
                for exact_key, exact_members in groups.items():
                    if len(exact_members) > 1 and set(m["id"] for m in members) <= set(m["id"] for m in exact_members):
                        covered = True
                        break
                if not covered:
                    groups[key] = members

        # Dismiss all but newest in each group with 2+ items
        dismiss_ids = []
        group_count = 0
        for key, members in groups.items():
            if len(members) > 1:
                group_count += 1
                # Keep first (newest — already sorted DESC by created_at)
                for m in members[1:]:
                    dismiss_ids.append(m["id"])

        if dismiss_ids:
            unique_ids = list(set(dismiss_ids))
            placeholders = ",".join("?" * len(unique_ids))
            conn.execute(
                f"""UPDATE action_items SET status = 'dismissed',
                    resolution_notes = 'Auto-consolidated (duplicate)'
                    WHERE id IN ({placeholders})""",
                unique_ids,
            )
            conn.commit()

        return {"consolidated": len(set(dismiss_ids)), "groups": group_count}


def get_pending_review_count(db_path: str | Path | None = None) -> dict:
    with _connect(db_path) as conn:
        expense_pending = conn.execute(
            "SELECT COUNT(*) as cnt FROM expense_transactions WHERE review_status = 'pending'"
        ).fetchone()["cnt"]
        action_open = conn.execute(
            "SELECT COUNT(*) as cnt FROM action_items WHERE status = 'open'"
        ).fetchone()["cnt"]
        acct_uncat = conn.execute(
            """SELECT COUNT(DISTINCT t.id) as cnt FROM acct_transactions t
               WHERE t.type != 'transfer'
                 AND t.id NOT IN (
                     SELECT s.transaction_id FROM acct_splits s WHERE s.category_id IS NOT NULL
                 )"""
        ).fetchone()["cnt"]
    return {
        "expense_pending": expense_pending,
        "action_open": action_open,
        "acct_uncategorized": acct_uncat,
        "total": expense_pending + action_open + acct_uncat,
    }


# ═══════════════════════════════════════════════════════════════════════════
# COO Dashboard Helpers
# ═══════════════════════════════════════════════════════════════════════════

def get_coo_manual_value(key: str, db_path: str | Path | None = None) -> float | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT value FROM coo_manual_values WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_coo_manual_value(key: str, value: float, db_path: str | Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO coo_manual_values (key, value, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
            (key, value),
        )
        conn.commit()


def get_all_coo_manual_values(db_path: str | Path | None = None) -> dict:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT key, value FROM coo_manual_values").fetchall()
    return {r["key"]: r["value"] for r in rows}


def build_coo_full_context(db_path: str | Path | None = None) -> str:
    """Build a comprehensive, token-efficient context string that gives the COO AI
    full situational awareness across every module of the tracker.

    This is the COO's 'morning briefing' — everything it needs to know about the
    current state of the business, condensed into a format the AI can reason over."""
    from datetime import datetime, timedelta

    today = datetime.now().strftime("%Y-%m-%d")
    month_prefix = datetime.now().strftime("%Y-%m")
    sections = []

    with _connect(db_path) as conn:
        # ── 1. FINANCIAL OVERVIEW ──────────────────────────────
        fin = []
        try:
            manual = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM coo_manual_values").fetchall()}
            checking = manual.get("tgf_checking_0341", 0) or 0
            mm = manual.get("tgf_money_market_8045", 0) or 0
            total_cash = round(checking + mm, 2)

            pp = conn.execute(
                "SELECT COALESCE(SUM(prize_pool), 0) as t FROM acct_allocations WHERE allocation_date >= ?",
                (today,)).fetchone()["t"]
            cf = conn.execute(
                "SELECT COALESCE(SUM(course_payable + course_surcharge), 0) as t FROM acct_allocations WHERE allocation_date >= ?",
                (today,)).fetchone()["t"]
            tr = conn.execute(
                "SELECT COALESCE(SUM(tax_reserve), 0) as t FROM acct_allocations WHERE allocation_date LIKE ?",
                (f"{month_prefix}%",)).fetchone()["t"]
            available = round(total_cash - pp - cf - tr, 2)

            irs = manual.get("irs_balance", 0) or 0
            gp_loan = manual.get("grandparent_loan", 0) or 0
            chase_biz = manual.get("chase_biz_7680", 0) or 0
            chase_saph = manual.get("chase_sapphire_6159", 0) or 0
            total_debt = round(irs + gp_loan + chase_biz + chase_saph, 2)

            fin.append(f"Cash: ${total_cash:,.2f} (Checking: ${checking:,.2f}, Money Market: ${mm:,.2f})")
            fin.append(f"Obligations: Prize Pools ${pp:,.2f}, Course Fees ${cf:,.2f}, Tax Reserve ${tr:,.2f}")
            fin.append(f"Available to Spend: ${available:,.2f}")
            fin.append(f"Debts: IRS ${irs:,.2f}, Grandparent Loan ${gp_loan:,.2f}, Chase Biz ${chase_biz:,.2f}, Chase Sapphire ${chase_saph:,.2f} (Total: ${total_debt:,.2f})")

            # Monthly revenue trend (last 3 months)
            try:
                month_rows = conn.execute(
                    """SELECT strftime('%Y-%m', date) as month,
                              SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
                              SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expenses
                       FROM acct_transactions
                       WHERE date >= date('now', '-3 months')
                       GROUP BY month ORDER BY month DESC LIMIT 3"""
                ).fetchall()
                for mr in month_rows:
                    net = round((mr["income"] or 0) - (mr["expenses"] or 0), 2)
                    fin.append(f"  {mr['month']}: Income ${mr['income'] or 0:,.2f}, Expenses ${mr['expenses'] or 0:,.2f}, Net ${net:+,.2f}")
            except Exception:
                pass
        except Exception as e:
            logger.warning("build_coo_full_context: Financial section error: %s", e)
            fin.append("Financial data not available")

        sections.append("FINANCIAL STATUS\n" + "\n".join(fin))

        # ── 2. EVENTS & OPERATIONS ─────────────────────────────
        ops = []
        try:
            upcoming = conn.execute(
                """SELECT e.item_name, e.event_date, e.course,
                          e.course_cost, e.course_cost_9, e.course_cost_18,
                          e.tgf_markup, e.tgf_markup_9, e.tgf_markup_18,
                          e.side_game_fee, e.side_game_fee_9, e.side_game_fee_18,
                          e.transaction_fee_pct, e.course_surcharge,
                          e.tgf_markup_final, e.tgf_markup_final_9, e.tgf_markup_final_18,
                          COUNT(DISTINCT CASE
                              WHEN COALESCE(i.transaction_status, 'active') IN ('active','rsvp_only')
                                   AND i.parent_item_id IS NULL
                              THEN i.id END) as playing,
                          COUNT(DISTINCT CASE
                              WHEN COALESCE(i.transaction_status, 'active') IN ('active','rsvp_only')
                                   AND i.parent_item_id IS NULL
                                   AND i.holes = '18'
                              THEN i.id END) as playing_18,
                          COALESCE(SUM(CASE
                              WHEN i.transaction_status = 'active' AND i.merchant NOT IN ('Roster Import','Customer Entry','RSVP Import','RSVP Email Link')
                              THEN CAST(REPLACE(REPLACE(i.item_price, '$', ''), ',', '') AS REAL) ELSE 0 END), 0) as revenue
                   FROM events e
                   LEFT JOIN event_aliases ea ON ea.canonical_event_name = e.item_name
                   LEFT JOIN items i ON (i.item_name = e.item_name COLLATE NOCASE
                                         OR i.item_name = ea.alias_name COLLATE NOCASE)
                       AND COALESCE(i.transaction_status, 'active') IN ('active','rsvp_only')
                   WHERE e.event_date >= ?
                   GROUP BY e.id, e.item_name, e.event_date, e.course
                   ORDER BY e.event_date ASC LIMIT 10""",
                (today,),
            ).fetchall()

            if upcoming:
                ops.append(f"{len(upcoming)} upcoming events:")
                for ev in upcoming:
                    rev = ev['revenue'] or 0
                    total = ev['playing'] or 0
                    p18 = ev['playing_18'] or 0
                    p9 = total - p18
                    player_desc = f"{total} registered"
                    if total and p18:
                        player_desc = f"{total} registered ({p9} nine-hole, {p18} eighteen-hole)"
                    line = f"  {ev['event_date']} — {ev['item_name']} at {ev['course'] or '?'} ({player_desc}, ${rev:,.2f} revenue)"
                    # Pricing breakdown
                    pricing_parts = []
                    cc9 = ev['course_cost'] or ev['course_cost_9'] or 0
                    cc18 = ev['course_cost_18'] or 0
                    if cc9:
                        pricing_parts.append(f"course-9h ${cc9:.0f}")
                    if cc18 and cc18 != cc9:
                        pricing_parts.append(f"course-18h ${cc18:.0f}")
                    mk9 = ev['tgf_markup'] or ev['tgf_markup_9'] or 0
                    mk18 = ev['tgf_markup_18'] or 0
                    if mk9:
                        pricing_parts.append(f"markup-9h ${mk9:.2f}")
                    if mk18 and mk18 != mk9:
                        pricing_parts.append(f"markup-18h ${mk18:.2f}")
                    sg9 = ev['side_game_fee'] or ev['side_game_fee_9'] or 0
                    sg18 = ev['side_game_fee_18'] or 0
                    if sg9:
                        pricing_parts.append(f"side-games-9h ${sg9:.2f}")
                    if sg18 and sg18 != sg9:
                        pricing_parts.append(f"side-games-18h ${sg18:.2f}")
                    surcharge = ev['course_surcharge'] or 0
                    if surcharge:
                        pricing_parts.append(f"surcharge ${surcharge:.2f}")
                    txn_pct = ev['transaction_fee_pct']
                    if txn_pct and txn_pct != 3.5:
                        pricing_parts.append(f"txn-fee {txn_pct}%")
                    if pricing_parts:
                        line += f" [pricing: {', '.join(pricing_parts)}]"
                    elif total and rev:
                        line += f" [avg ${rev / total:,.2f}/player, pricing not configured]"
                    # Profitability calculation using 9/18 split
                    if (cc9 or cc18) and total:
                        total_course = (cc9 * p9) + (cc18 * p18)
                        gross_profit = rev - total_course
                        line += f" [course-cost: ${total_course:,.0f}, gross-profit: ${gross_profit:,.0f}]"
                    ops.append(line)
            else:
                ops.append("No upcoming events")

            # RSVP data per upcoming event
            try:
                rsvp_counts = conn.execute(
                    """SELECT matched_event, response, COUNT(*) as cnt
                       FROM rsvps WHERE matched_event IS NOT NULL
                       GROUP BY matched_event, response"""
                ).fetchall()
                rsvp_map = {}
                for r in rsvp_counts:
                    ev_name = r["matched_event"]
                    if ev_name not in rsvp_map:
                        rsvp_map[ev_name] = {"PLAYING": 0, "NOT PLAYING": 0}
                    rsvp_map[ev_name][r["response"]] = r["cnt"]
                if rsvp_map:
                    ops.append("RSVP breakdown:")
                    for ev_name, counts in list(rsvp_map.items())[:8]:
                        ops.append(f"  {ev_name}: {counts.get('PLAYING', 0)} playing, {counts.get('NOT PLAYING', 0)} not playing")
            except Exception:
                pass

            # Recent past events (last 30 days) for context
            recent_events = conn.execute(
                """SELECT e.item_name, e.event_date, e.course,
                          e.course_cost, e.course_cost_9, e.course_cost_18,
                          COUNT(DISTINCT CASE
                              WHEN COALESCE(i.transaction_status, 'active') IN ('active','rsvp_only')
                                   AND i.parent_item_id IS NULL
                              THEN i.id END) as played,
                          COUNT(DISTINCT CASE
                              WHEN COALESCE(i.transaction_status, 'active') IN ('active','rsvp_only')
                                   AND i.parent_item_id IS NULL
                                   AND i.holes = '18'
                              THEN i.id END) as played_18,
                          COALESCE(SUM(CASE
                              WHEN i.transaction_status = 'active' AND i.merchant NOT IN ('Roster Import','Customer Entry','RSVP Import','RSVP Email Link')
                              THEN CAST(REPLACE(REPLACE(i.item_price, '$', ''), ',', '') AS REAL) ELSE 0 END), 0) as revenue
                   FROM events e
                   LEFT JOIN event_aliases ea ON ea.canonical_event_name = e.item_name
                   LEFT JOIN items i ON (i.item_name = e.item_name COLLATE NOCASE
                                         OR i.item_name = ea.alias_name COLLATE NOCASE)
                       AND COALESCE(i.transaction_status, 'active') IN ('active','rsvp_only')
                   WHERE e.event_date < ? AND e.event_date >= date(?, '-30 days')
                   GROUP BY e.id, e.item_name, e.event_date
                   ORDER BY e.event_date DESC LIMIT 5""",
                (today, today),
            ).fetchall()
            if recent_events:
                ops.append(f"Recent events (last 30 days):")
                for ev in recent_events:
                    rev = ev['revenue'] or 0
                    total = ev['played'] or 0
                    p18 = ev['played_18'] or 0
                    p9 = total - p18
                    player_desc = f"{total} players"
                    if total and p18:
                        player_desc = f"{total} players ({p9} nine-hole, {p18} eighteen-hole)"
                    ops.append(f"  {ev['event_date']} — {ev['item_name']} ({player_desc}, ${rev:,.2f} revenue)")
        except Exception as e:
            logger.warning("build_coo_full_context: Events section error: %s", e)
            ops.append("Event data not available")

        # Event cost allocations (for profitability analysis)
        try:
            alloc_rows = conn.execute(
                """SELECT event_name,
                          SUM(course_payable + course_surcharge) as total_course_cost,
                          SUM(prize_pool) as total_prize_pool,
                          SUM(godaddy_fee) as total_processing,
                          SUM(tgf_operating) as total_tgf_operating,
                          SUM(total_collected) as total_collected,
                          COUNT(*) as player_allocs
                   FROM acct_allocations
                   WHERE allocation_date >= ?
                   GROUP BY event_name ORDER BY allocation_date ASC""",
                (today,),
            ).fetchall()
            if alloc_rows:
                ops.append("Event cost allocations (upcoming):")
                for a in alloc_rows:
                    course = a["total_course_cost"] or 0
                    prize = a["total_prize_pool"] or 0
                    processing = a["total_processing"] or 0
                    collected = a["total_collected"] or 0
                    operating = a["total_tgf_operating"] or 0
                    net = collected - course - prize - processing
                    ops.append(f"  {a['event_name']}: {a['player_allocs']} players, ${collected:,.2f} collected, ${course:,.2f} course, ${prize:,.2f} prizes, ${processing:,.2f} processing, ${operating:,.2f} TGF operating (net: ${net:,.2f})")
        except Exception:
            pass

        # TGF payout data (tournament prizes)
        try:
            tgf_events = conn.execute(
                """SELECT te.code, te.event_date, te.course, te.total_purse,
                          te.winners_count, te.payouts_count
                   FROM tgf_events te
                   ORDER BY te.event_date DESC LIMIT 8"""
            ).fetchall()
            if tgf_events:
                ops.append("TGF Event Payouts (actual prizes paid):")
                for te in tgf_events:
                    purse = te['total_purse'] or 0
                    ops.append(f"  {te['event_date']} — {te['code']} at {te['course'] or '?'}: ${purse:,.2f} purse, {te['winners_count']} winners, {te['payouts_count']} payouts")
                latest = tgf_events[0]
                cats = conn.execute(
                    """SELECT p.category, COUNT(*) as cnt, SUM(p.amount) as total
                       FROM tgf_payouts p
                       JOIN tgf_events te ON te.id = p.event_id
                       WHERE te.code = ?
                       GROUP BY p.category ORDER BY total DESC""",
                    (latest['code'],),
                ).fetchall()
                if cats:
                    ops.append(f"  Latest payout breakdown ({latest['code']}):")
                    for c in cats:
                        ops.append(f"    {c['category']}: {c['cnt']} payouts, ${c['total']:,.2f}")
        except Exception:
            pass

        # Full profitability (penny-accurate from acct_allocations)
        try:
            profit_rows = conn.execute(
                """SELECT a.event_name,
                          MIN(a.allocation_date) as event_date,
                          SUM(a.total_collected) as revenue,
                          SUM(a.course_payable + a.course_surcharge) as course_cost,
                          SUM(a.prize_pool) as prize_fund,
                          SUM(a.godaddy_fee) as processing_fees,
                          SUM(a.tgf_operating) as tgf_operating,
                          SUM(a.tax_reserve) as tax_reserve,
                          COUNT(*) as players
                   FROM acct_allocations a
                   WHERE a.allocation_date >= date(?, '-60 days')
                   GROUP BY a.event_name
                   HAVING players > 0
                   ORDER BY event_date DESC LIMIT 8""",
                (today,),
            ).fetchall()
            if profit_rows:
                ops.append("EVENT PROFITABILITY (last 60 days — from allocations, penny-accurate):")
                ops.append("  Formula: Revenue - Course Fees - Prize Fund - Processing Fees = Net Profit")
                for pr in profit_rows:
                    rev = pr['revenue'] or 0
                    course = pr['course_cost'] or 0
                    prizes = pr['prize_fund'] or 0
                    processing = pr['processing_fees'] or 0
                    net = rev - course - prizes - processing
                    ops.append(f"  {pr['event_date']} — {pr['event_name']}: {pr['players']} players, "
                               f"${rev:,.2f} revenue, ${course:,.2f} course, ${prizes:,.2f} prizes, "
                               f"${processing:,.2f} processing → ${net:,.2f} net")
        except Exception as e:
            logger.warning("build_coo_full_context: TGF/profitability section error: %s", e)

        sections.append("EVENTS & OPERATIONS\n" + "\n".join(ops))

        # ── 3. MEMBERS & CUSTOMERS ─────────────────────────────
        mem = []
        try:
            cust_total = conn.execute("SELECT COUNT(*) as c FROM customers").fetchone()["c"]
            active_members = conn.execute(
                "SELECT COUNT(*) as c FROM customers WHERE account_status = 'active'"
            ).fetchone()["c"]

            # Recent new customers (last 30 days)
            new_custs = conn.execute(
                """SELECT COUNT(*) as c FROM customers
                   WHERE created_at >= date('now', '-30 days')"""
            ).fetchone()["c"]

            mem.append(f"Total customers: {cust_total} ({active_members} active)")
            mem.append(f"New customers (30d): {new_custs}")

            # Top spenders this season
            top_spenders = conn.execute(
                """SELECT customer, COUNT(*) as events,
                          SUM(CAST(REPLACE(REPLACE(item_price, '$', ''), ',', '') AS REAL)) as spent
                   FROM items
                   WHERE merchant NOT IN ('Roster Import','Customer Entry','RSVP Import','RSVP Email Link')
                     AND transaction_status = 'active'
                     AND order_date >= date('now', '-6 months')
                   GROUP BY customer ORDER BY events DESC LIMIT 5"""
            ).fetchall()
            if top_spenders:
                mem.append("Top players (6 months):")
                for ts in top_spenders:
                    mem.append(f"  {ts['customer']}: {ts['events']} events, ${ts['spent'] or 0:,.0f}")
        except Exception as e:
            logger.warning("build_coo_full_context: Customers section error: %s", e)
            mem.append("Customer data not available")

        sections.append("MEMBERS & CUSTOMERS\n" + "\n".join(mem))

        # ── 4. TRANSACTION ACTIVITY ────────────────────────────
        txn = []
        try:
            stats = conn.execute(
                """SELECT COUNT(*) as total,
                          COUNT(DISTINCT order_id) as orders,
                          MIN(order_date) as earliest,
                          MAX(order_date) as latest
                   FROM items
                   WHERE merchant NOT IN ('Roster Import','Customer Entry','RSVP Import','RSVP Email Link')"""
            ).fetchone()
            txn.append(f"Total: {stats['total']} items across {stats['orders']} orders ({stats['earliest']} to {stats['latest']})")

            # Recent activity (7 days)
            recent_txn = conn.execute(
                """SELECT COUNT(*) as c,
                          SUM(CAST(REPLACE(REPLACE(item_price, '$', ''), ',', '') AS REAL)) as total
                   FROM items
                   WHERE merchant NOT IN ('Roster Import','Customer Entry','RSVP Import','RSVP Email Link')
                     AND order_date >= date('now', '-7 days')"""
            ).fetchone()
            txn.append(f"Last 7 days: {recent_txn['c']} new items, ${recent_txn['total'] or 0:,.0f}")
        except Exception as e:
            logger.warning("build_coo_full_context: Transactions section error: %s", e)
            txn.append("Transaction data not available")

        sections.append("TRANSACTION ACTIVITY\n" + "\n".join(txn))

        # ── 5. RSVPS ──────────────────────────────────────────
        rsvp = []
        try:
            r_total = conn.execute("SELECT COUNT(*) as c FROM rsvps").fetchone()["c"]
            r_playing = conn.execute("SELECT COUNT(*) as c FROM rsvps WHERE response = 'PLAYING'").fetchone()["c"]
            r_not = conn.execute("SELECT COUNT(*) as c FROM rsvps WHERE response = 'NOT PLAYING'").fetchone()["c"]
            r_unmatched = conn.execute(
                "SELECT COUNT(*) as c FROM rsvps WHERE matched_event IS NOT NULL AND matched_item_id IS NULL AND response = 'PLAYING'"
            ).fetchone()["c"]
            rsvp.append(f"Total RSVPs: {r_total} ({r_playing} playing, {r_not} not playing)")
            if r_unmatched:
                rsvp.append(f"Playing but no payment: {r_unmatched} (need follow-up)")
        except Exception as e:
            logger.warning("build_coo_full_context: RSVPs section error: %s", e)
            rsvp.append("RSVP data not available")
        sections.append("RSVPS\n" + "\n".join(rsvp))

        # ── 6. HANDICAPS ──────────────────────────────────────
        hcp = []
        try:
            player_count = conn.execute("SELECT COUNT(DISTINCT player_name) as c FROM handicap_rounds").fetchone()["c"]
            round_count = conn.execute("SELECT COUNT(*) as c FROM handicap_rounds").fetchone()["c"]
            recent_rounds = conn.execute(
                "SELECT COUNT(*) as c FROM handicap_rounds WHERE round_date >= date('now', '-30 days')"
            ).fetchone()["c"]
            hcp.append(f"Players: {player_count}, Total rounds: {round_count}")
            hcp.append(f"Rounds entered (30d): {recent_rounds}")
        except Exception as e:
            logger.warning("build_coo_full_context: Handicaps section error: %s", e)
            hcp.append("Handicap data not available")
        sections.append("HANDICAPS\n" + "\n".join(hcp))

        # ── 7. ACCOUNTING & COMPLIANCE ─────────────────────────
        acct = []
        try:
            acct_total = conn.execute(
                "SELECT COUNT(*) as cnt FROM acct_transactions WHERE type != 'transfer'"
            ).fetchone()["cnt"]
            acct_catd = conn.execute(
                """SELECT COUNT(DISTINCT t.id) as cnt FROM acct_transactions t
                   JOIN acct_splits s ON s.transaction_id = t.id
                   WHERE s.category_id IS NOT NULL AND t.type != 'transfer'"""
            ).fetchone()["cnt"]
            acct_uncat = acct_total - acct_catd
            pct = round(acct_catd / acct_total * 100, 1) if acct_total else 100
            acct.append(f"Transactions: {acct_total} total, {acct_catd} categorized ({pct}%), {acct_uncat} uncategorized")
        except Exception as e:
            logger.warning("build_coo_full_context: Accounting section error: %s", e)
            acct.append("Accounting data not available")

        # Pending reviews
        try:
            exp_pending = conn.execute(
                "SELECT COUNT(*) as cnt FROM expense_transactions WHERE review_status = 'pending'"
            ).fetchone()["cnt"]
            if exp_pending:
                acct.append(f"Expense reviews pending: {exp_pending}")
        except Exception:
            pass

        sections.append("ACCOUNTING & COMPLIANCE\n" + "\n".join(acct))

        # ── 8. ACTION ITEMS SUMMARY ────────────────────────────
        ai_sec = []
        try:
            ai_open = conn.execute("SELECT COUNT(*) as c FROM action_items WHERE status = 'open'").fetchone()["c"]
            ai_prog = conn.execute("SELECT COUNT(*) as c FROM action_items WHERE status = 'in_progress'").fetchone()["c"]
            ai_high = conn.execute("SELECT COUNT(*) as c FROM action_items WHERE status = 'open' AND urgency = 'high'").fetchone()["c"]
            ai_sec.append(f"Open: {ai_open} ({ai_high} high urgency), In Progress: {ai_prog}")

            # Category breakdown
            cat_rows = conn.execute(
                "SELECT category, COUNT(*) as c FROM action_items WHERE status = 'open' GROUP BY category ORDER BY c DESC LIMIT 5"
            ).fetchall()
            if cat_rows:
                cats = ", ".join(f"{r['category']}: {r['c']}" for r in cat_rows)
                ai_sec.append(f"By category: {cats}")
        except Exception as e:
            logger.warning("build_coo_full_context: Action items section error: %s", e)
            ai_sec.append("Action items data not available")

        sections.append("ACTION ITEMS\n" + "\n".join(ai_sec))

        # ── 9. TGF PAYOUTS ────────────────────────────────────
        pay = []
        try:
            ev_count = conn.execute("SELECT COUNT(*) as c FROM tgf_events").fetchone()["c"]
            winners_count = conn.execute(
                "SELECT COUNT(DISTINCT customer_id) as c FROM tgf_payouts"
            ).fetchone()["c"]
            total_paid = conn.execute("SELECT COALESCE(SUM(amount), 0) as t FROM tgf_payouts").fetchone()["t"]
            pay.append(f"Events with payouts: {ev_count}, Winners: {winners_count}, Total paid: ${total_paid:,.2f}")

            # Recent payout events
            recent_pay = conn.execute(
                """SELECT e.name, e.event_date, e.total_purse, COUNT(p.id) as payouts
                   FROM tgf_events e LEFT JOIN tgf_payouts p ON p.event_id = e.id
                   GROUP BY e.id, e.name, e.event_date, e.total_purse ORDER BY e.event_date DESC LIMIT 3"""
            ).fetchall()
            for rp in recent_pay:
                pay.append(f"  {rp['event_date']} — {rp['name']}: ${rp['total_purse'] or 0:,.0f} purse, {rp['payouts']} payouts")
        except Exception as e:
            logger.warning("build_coo_full_context: Payouts section error: %s", e)
            pay.append("No payout data yet")

        sections.append("TGF PAYOUTS\n" + "\n".join(pay))

        # ── 10. SEASON CONTESTS ────────────────────────────────
        sc = []
        try:
            enrollments = conn.execute(
                "SELECT contest_type, COUNT(*) as c FROM season_contests GROUP BY contest_type"
            ).fetchall()
            if enrollments:
                sc.append("Season contests: " + ", ".join(f"{r['contest_type']}: {r['c']} enrolled" for r in enrollments))
            else:
                sc.append("No season contest enrollments")
        except Exception as e:
            logger.warning("build_coo_full_context: Season contests section error: %s", e)
            sc.append("Season contests not configured")

        sections.append("SEASON CONTESTS\n" + "\n".join(sc))

    return "\n\n".join(sections)


def get_coo_financial_snapshot(db_path: str | Path | None = None) -> dict:
    """Build the complete financial snapshot for the COO dashboard."""
    manual = get_all_coo_manual_values(db_path)
    today = datetime.now().strftime("%Y-%m-%d")
    month_prefix = datetime.now().strftime("%Y-%m")

    with _connect(db_path) as conn:
        # Prize pools owed (future events)
        pp = conn.execute(
            "SELECT COALESCE(SUM(prize_pool), 0) as total FROM acct_allocations WHERE allocation_date >= ?",
            (today,),
        ).fetchone()["total"]

        # Course fees owed (future events)
        cf = conn.execute(
            "SELECT COALESCE(SUM(course_payable + course_surcharge), 0) as total FROM acct_allocations WHERE allocation_date >= ?",
            (today,),
        ).fetchone()["total"]

        # Tax reserve MTD
        tr = conn.execute(
            "SELECT COALESCE(SUM(tax_reserve), 0) as total FROM acct_allocations WHERE allocation_date LIKE ?",
            (f"{month_prefix}%",),
        ).fetchone()["total"]

    checking = manual.get("tgf_checking_0341", 0)
    money_market = manual.get("tgf_money_market_8045", 0)
    tgf_total = round(checking + money_market, 2)
    available = round(tgf_total - pp - cf - tr, 2)

    return {
        "accounts": {
            "tgf_checking_0341": round(checking, 2),
            "tgf_money_market_8045": round(money_market, 2),
            "tgf_total": tgf_total,
        },
        "obligations": {
            "prize_pools_owed": round(pp, 2),
            "course_fees_owed": round(cf, 2),
            "tax_reserve_mtd": round(tr, 2),
            "available_to_spend": available,
        },
        "debts": {
            "irs_balance": manual.get("irs_balance", 0),
            "grandparent_loan": manual.get("grandparent_loan", 0),
            "chase_biz_7680": manual.get("chase_biz_7680", 0),
            "chase_sapphire_6159": manual.get("chase_sapphire_6159", 0),
            "total_obligations": round(
                manual.get("irs_balance", 0) + manual.get("grandparent_loan", 0)
                + manual.get("chase_biz_7680", 0) + manual.get("chase_sapphire_6159", 0), 2
            ),
        },
    }


def get_contractor_payouts(db_path: str | Path | None = None) -> list[dict]:
    """Return all contractor payout records with manager name and chapter."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT cp.id, cp.manager_customer_id,
                      (c.first_name || ' ' || c.last_name) AS manager_name,
                      ch.name AS chapter_name,
                      cp.chapter_id, cp.event_name, cp.event_date,
                      cp.amount_owed, cp.amount_paid, cp.status,
                      cp.payment_method, cp.notes, cp.created_at
               FROM contractor_payouts cp
               JOIN customers c ON c.customer_id = cp.manager_customer_id
               LEFT JOIN chapters ch ON ch.chapter_id = cp.chapter_id
               ORDER BY cp.event_date DESC, cp.created_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_contractor_managers(db_path: str | Path | None = None) -> list[dict]:
    """Return all customers with manager role, for the add-payout dropdown."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT c.customer_id,
                      (c.first_name || ' ' || c.last_name) AS name,
                      c.chapter,
                      ch.name AS chapter_name, ch.chapter_id
               FROM customers c
               JOIN customer_roles cr ON cr.customer_id = c.customer_id
               LEFT JOIN chapters ch ON ch.name = c.chapter
               WHERE cr.role_type = 'manager'
               ORDER BY c.last_name, c.first_name"""
        ).fetchall()
        return [dict(r) for r in rows]


def add_contractor_payout(
    manager_customer_id: int,
    event_name: str | None,
    event_date: str | None,
    amount_owed: float,
    chapter_id: int | None = None,
    notes: str | None = None,
    db_path: str | Path | None = None,
) -> int:
    """Create a new contractor payout record. Returns new id."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO contractor_payouts
               (manager_customer_id, chapter_id, event_name, event_date, amount_owed, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (manager_customer_id, chapter_id, event_name or None, event_date or None,
             round(float(amount_owed), 2), notes or None),
        )
        return cur.lastrowid


def update_contractor_payout(
    payout_id: int,
    amount_paid: float | None = None,
    status: str | None = None,
    payment_method: str | None = None,
    notes: str | None = None,
    db_path: str | Path | None = None,
) -> bool:
    """Update payment info on an existing contractor payout. Returns True if updated."""
    fields, params = [], []
    if amount_paid is not None:
        fields.append("amount_paid = ?")
        params.append(round(float(amount_paid), 2))
    if status is not None:
        fields.append("status = ?")
        params.append(status)
    if payment_method is not None:
        fields.append("payment_method = ?")
        params.append(payment_method)
    if notes is not None:
        fields.append("notes = ?")
        params.append(notes)
    if not fields:
        return False
    fields.append("updated_at = datetime('now')")
    params.append(payout_id)
    with _connect(db_path) as conn:
        cur = conn.execute(
            f"UPDATE contractor_payouts SET {', '.join(fields)} WHERE id = ?", params
        )
        return cur.rowcount > 0


def delete_contractor_payout(payout_id: int, db_path: str | Path | None = None) -> bool:
    """Delete a contractor payout record."""
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM contractor_payouts WHERE id = ?", (payout_id,))
        return cur.rowcount > 0


def get_contractor_liability_total(db_path: str | Path | None = None) -> float:
    """Sum of outstanding balances across all unpaid/partial contractor payouts."""
    with _connect(db_path) as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(amount_owed - amount_paid), 0) as total
               FROM contractor_payouts WHERE status != 'paid'"""
        ).fetchone()
        return round(row["total"] or 0, 2)


def get_accounting_liabilities(db_path: str | Path | None = None) -> dict:
    """Return all 9 liability buckets for the Liabilities Dashboard."""
    manual = get_all_coo_manual_values(db_path)
    today = datetime.now().strftime("%Y-%m-%d")
    month_prefix = datetime.now().strftime("%Y-%m")

    with _connect(db_path) as conn:
        # Prize pools owed — broken out per event (upcoming/future allocations)
        prize_rows = conn.execute(
            """SELECT event_name, COALESCE(SUM(prize_pool), 0) as total
               FROM acct_allocations
               WHERE allocation_date >= ? AND event_name IS NOT NULL
               GROUP BY event_name
               ORDER BY MIN(allocation_date) ASC""",
            (today,),
        ).fetchall()
        prize_per_event = [{"event": r["event_name"], "amount": round(r["total"], 2)} for r in prize_rows]
        prize_total = round(sum(e["amount"] for e in prize_per_event), 2)

        # Course fees owed (future events)
        course_fees = conn.execute(
            "SELECT COALESCE(SUM(course_payable + course_surcharge), 0) as total FROM acct_allocations WHERE allocation_date >= ?",
            (today,),
        ).fetchone()["total"]

        # Tax reserve — full YTD (not just MTD, since it accumulates)
        tax_reserve = conn.execute(
            "SELECT COALESCE(SUM(tax_reserve), 0) as total FROM acct_allocations WHERE allocation_date LIKE ?",
            (f"{month_prefix[:4]}%",),  # full year
        ).fetchone()["total"]

        # Member credits: sum credited items not yet redeemed
        member_credits_calc = conn.execute(
            """SELECT COALESCE(SUM(ABS(item_price)), 0) as total
               FROM items WHERE transaction_status = 'credited'""",
        ).fetchone()["total"]

    # Manual values — editable buckets
    hio_pot = manual.get("hio_pot", 0) or 0
    season_contests = manual.get("season_contests_total", 0) or 0
    lone_star_cup = manual.get("lone_star_cup_shirts", 0) or 0
    chapter_mgr = get_contractor_liability_total(db_path)
    investor_debt = manual.get("grandparent_loan", 0) or 0
    member_credits_manual = manual.get("member_credits_2025", 0) or 0
    # Use the larger of calculated vs manual (manual overrides if explicitly set)
    member_credits = member_credits_manual if member_credits_manual > 0 else round(member_credits_calc, 2)

    # Debt tracker (from existing COO manual values)
    irs_balance = manual.get("irs_balance", 0) or 0
    chase_biz = manual.get("chase_biz_7680", 0) or 0
    chase_saph = manual.get("chase_sapphire_6159", 0) or 0

    return {
        "event_obligations": {
            "prize_pools": {"total": prize_total, "per_event": prize_per_event},
            "course_fees_owed": round(course_fees, 2),
        },
        "running_pools": {
            "hio_pot": round(hio_pot, 2),
            "season_contests": round(season_contests, 2),
            "lone_star_cup_shirts": round(lone_star_cup, 2),
        },
        "operational": {
            "chapter_manager_payouts": round(chapter_mgr, 2),
            "tax_reserve_ytd": round(tax_reserve, 2),
        },
        "debts": {
            "investor_debt": round(investor_debt, 2),
            "member_credits_2025": round(member_credits, 2),
            "irs_balance": round(irs_balance, 2),
            "chase_biz_7680": round(chase_biz, 2),
            "chase_sapphire_6159": round(chase_saph, 2),
        },
        "grand_total": round(
            prize_total + course_fees + hio_pot + season_contests + lone_star_cup
            + chapter_mgr + tax_reserve + investor_debt + member_credits
            + irs_balance + chase_biz + chase_saph, 2
        ),
        "manual_keys": ["hio_pot", "season_contests_total", "lone_star_cup_shirts",
                        "grandparent_loan", "member_credits_2025",
                        "irs_balance", "chase_biz_7680", "chase_sapphire_6159"],
    }


def get_month_close_status(db_path: str | Path | None = None) -> dict:
    """Return all data needed to render the Month Close checklist and Financial Position."""
    try:
        return _get_month_close_status_inner(db_path)
    except Exception as exc:
        logger.warning("get_month_close_status failed: %s", exc, exc_info=True)
        today = datetime.now()
        return {
            "period": {"month": today.strftime("%B %Y"), "year": today.strftime("%Y")},
            "checklist": {
                "uncategorized_ledger": 0, "pending_inbox": 0,
                "unmatched_deposits": 0, "unreconciled_entries": 0,
                "events_no_entries": 0, "tax_reserve_ytd": 0.0,
            },
            "financial_position": {
                "ytd_income": 0.0, "ytd_expenses": 0.0, "ytd_net": 0.0,
                "cash_on_hand": 0.0, "total_liabilities": 0.0, "net_position": 0.0,
            },
            "error": str(exc),
        }


def _get_month_close_status_inner(db_path: str | Path | None = None) -> dict:
    manual = get_all_coo_manual_values(db_path)
    today = datetime.now()
    month_prefix = today.strftime("%Y-%m")
    year_prefix = today.strftime("%Y")

    with _connect(db_path) as conn:
        # --- Checklist items ---
        # 1. Uncategorized ledger entries
        total_txns = conn.execute(
            "SELECT COUNT(*) as cnt FROM acct_transactions WHERE type != 'transfer'"
        ).fetchone()["cnt"]
        categorized = conn.execute(
            """SELECT COUNT(DISTINCT t.id) as cnt
               FROM acct_transactions t
               JOIN acct_splits s ON s.transaction_id = t.id
               WHERE s.category_id IS NOT NULL AND t.type != 'transfer'"""
        ).fetchone()["cnt"]
        uncategorized_ledger = total_txns - categorized

        # 2. Pending inbox (expense_transactions awaiting review)
        pending_inbox = conn.execute(
            "SELECT COUNT(*) as cnt FROM expense_transactions WHERE review_status = 'pending'"
        ).fetchone()["cnt"]

        # 3. Unmatched bank deposits (excluding dismissed internal transfers)
        unmatched_deposits = conn.execute(
            "SELECT COUNT(*) as cnt FROM bank_deposits WHERE status = 'unmatched' AND COALESCE(dismissed, 0) = 0"
        ).fetchone()["cnt"]

        # 4. Unreconciled ledger entries (active income/expense with no bank match)
        unreconciled = conn.execute(
            """SELECT COUNT(*) as cnt FROM acct_transactions t
               WHERE COALESCE(t.status, 'active') = 'active'
               AND t.type IN ('income', 'expense')
               AND NOT EXISTS (
                   SELECT 1 FROM reconciliation_matches rm WHERE rm.acct_transaction_id = t.id
               )"""
        ).fetchone()["cnt"]

        # 5. Events this month with no accounting entries
        events_no_entries = conn.execute(
            """SELECT COUNT(*) as cnt FROM events e
               WHERE e.event_date LIKE ? AND e.item_name IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1 FROM acct_transactions t
                   WHERE t.event_name = e.item_name AND t.entry_type IS NOT NULL
               )""",
            (f"{month_prefix}%",),
        ).fetchone()["cnt"]

        # --- Financial Position ---
        # YTD income/expenses — handles both old rows (type col) and new rows (entry_type col)
        ytd = conn.execute(
            """SELECT
                COALESCE(SUM(CASE
                    WHEN (entry_type = 'income' OR (entry_type IS NULL AND type = 'income'))
                         AND COALESCE(status, 'active') != 'reversed'
                    THEN total_amount ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE
                    WHEN (entry_type = 'expense' OR (entry_type IS NULL AND type = 'expense'))
                         AND COALESCE(status, 'active') != 'reversed'
                    THEN total_amount ELSE 0 END), 0) as expenses
               FROM acct_transactions
               WHERE date LIKE ?""",
            (f"{year_prefix}%",),
        ).fetchone()
        ytd_income = round(ytd["income"] or 0, 2)
        ytd_expenses = round(ytd["expenses"] or 0, 2)
        ytd_net = round(ytd_income - ytd_expenses, 2)

        # Tax reserve YTD
        tax_reserve = conn.execute(
            "SELECT COALESCE(SUM(tax_reserve), 0) as total FROM acct_allocations WHERE allocation_date LIKE ?",
            (f"{year_prefix}%",),
        ).fetchone()["total"]

    # Cash on hand from manual values
    checking = manual.get("tgf_checking_0341", 0) or 0
    money_market = manual.get("tgf_money_market_8045", 0) or 0
    cash_on_hand = round(checking + money_market, 2)

    # Total liabilities (all buckets combined)
    liabilities = get_accounting_liabilities(db_path)
    total_liabilities = liabilities["grand_total"]

    net_position = round(cash_on_hand - total_liabilities, 2)

    return {
        "period": {
            "month": today.strftime("%B %Y"),
            "year": today.strftime("%Y"),
        },
        "checklist": {
            "uncategorized_ledger": uncategorized_ledger,
            "pending_inbox": pending_inbox,
            "unmatched_deposits": unmatched_deposits,
            "unreconciled_entries": unreconciled,
            "events_no_entries": events_no_entries,
            "tax_reserve_ytd": round(tax_reserve, 2),
        },
        "financial_position": {
            "ytd_income": ytd_income,
            "ytd_expenses": ytd_expenses,
            "ytd_net": ytd_net,
            "cash_on_hand": cash_on_hand,
            "total_liabilities": total_liabilities,
            "net_position": net_position,
        },
    }


def get_coo_review_queue(db_path: str | Path | None = None) -> list[dict]:
    """Unified review queue: pending expenses + low-confidence action items."""
    with _connect(db_path) as conn:
        expenses = conn.execute(
            """SELECT id, 'expense' as queue_type, source_type, merchant, amount,
                      transaction_date, category, entity, event_name, confidence,
                      review_status, notes, raw_extract, created_at
               FROM expense_transactions WHERE review_status = 'pending'
               ORDER BY created_at DESC LIMIT 50"""
        ).fetchall()

        actions = conn.execute(
            """SELECT id, 'action' as queue_type, 'action_required' as source_type,
                      subject as merchant, 0 as amount, email_date as transaction_date,
                      category, '' as entity, '' as event_name, confidence,
                      status as review_status, summary as notes, '' as raw_extract,
                      created_at
               FROM action_items WHERE confidence < 95 AND status = 'open'
               ORDER BY created_at DESC LIMIT 50"""
        ).fetchall()

    items = [dict(r) for r in expenses] + [dict(r) for r in actions]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items


# ═══════════════════════════════════════════════════════════════════════════
# Chart of Accounts, General Ledger & Bank Reconciliation
# ═══════════════════════════════════════════════════════════════════════════

def _seed_chart_of_accounts(conn: sqlite3.Connection) -> None:
    """Populate standard chart of accounts with IRS Schedule C categories."""
    accounts = [
        # Assets
        ("1000", "TGF Checking 0341", "asset", None),
        ("1100", "TGF Money Market 8045", "asset", None),
        ("1200", "Accounts Receivable", "asset", None),
        # Liabilities
        ("2000", "Sales Tax Payable", "liability", None),
        ("2100", "Prize Pool Liability", "liability", None),
        ("2200", "Course Payable", "liability", None),
        # Income
        ("4000", "Event Revenue", "income", "Line 1"),
        ("4100", "Membership Revenue", "income", "Line 1"),
        ("4200", "Season Contest Revenue", "income", "Line 1"),
        ("4300", "Transaction Fee Income", "income", "Line 6"),
        # Expenses
        ("6000", "Course Fees", "expense", "Line 27a"),
        ("6100", "Merchant/Processing Fees", "expense", "Line 10"),
        ("6200", "Software Subscriptions", "expense", "Line 27a"),
        ("6300", "Advertising & Marketing", "expense", "Line 8"),
        ("6400", "Prize Payouts", "expense", "Line 27a"),
        ("6500", "Printing & Supplies", "expense", "Line 22"),
        ("6600", "Professional Services", "expense", "Line 17"),
        ("6700", "Bank & Payment Fees", "expense", "Line 27a"),
        ("6800", "Miscellaneous Expense", "expense", "Line 27a"),
    ]
    for code, name, atype, sched_line in accounts:
        conn.execute(
            "INSERT INTO chart_of_accounts (code, name, account_type, schedule_c_line) VALUES (?, ?, ?, ?)",
            (code, name, atype, sched_line),
        )


def get_chart_of_accounts(db_path: str | Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM chart_of_accounts WHERE is_active = 1 ORDER BY code"
        ).fetchall()
    return [dict(r) for r in rows]


def get_ledger_entries(account_code: str | None = None, date_from: str | None = None,
                       date_to: str | None = None, reconciled: int | None = None,
                       limit: int = 500, db_path: str | Path | None = None) -> list[dict]:
    clauses, params = [], []
    if account_code:
        clauses.append("gl.account_code = ?"); params.append(account_code)
    if date_from:
        clauses.append("gl.entry_date >= ?"); params.append(date_from)
    if date_to:
        clauses.append("gl.entry_date <= ?"); params.append(date_to)
    if reconciled is not None:
        clauses.append("gl.reconciled = ?"); params.append(reconciled)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"""SELECT gl.*, coa.name as account_name, coa.account_type
                FROM general_ledger gl
                JOIN chart_of_accounts coa ON coa.code = gl.account_code
                {where} ORDER BY gl.entry_date DESC, gl.id DESC LIMIT ?""",
            params + [limit],
        ).fetchall()
    return [dict(r) for r in rows]


def import_bank_statement(csv_text: str, bank: str, account_last4: str,
                          db_path: str | Path | None = None) -> dict:
    """Parse and import a bank statement CSV. Auto-detects Chase vs Frost format.
    Returns {import_id, imported, skipped, rows}."""
    import csv
    import io
    import uuid

    reader = csv.reader(io.StringIO(csv_text))
    all_rows = list(reader)
    if not all_rows:
        return {"import_id": None, "imported": 0, "skipped": 0, "rows": []}

    header = [h.strip().lower() for h in all_rows[0]]
    data_rows = all_rows[1:]
    import_id = str(uuid.uuid4())[:12]

    # Auto-detect format
    if "posting date" in header:
        # Chase format: Details, Posting Date, Description, Amount, Type, Balance, Check or Slip #
        date_idx = header.index("posting date")
        desc_idx = header.index("description") if "description" in header else 2
        amount_idx = header.index("amount") if "amount" in header else 3
        balance_idx = header.index("balance") if "balance" in header else None
        type_idx = header.index("type") if "type" in header else None
        detected = "Chase"
    elif "date" in header:
        date_idx = header.index("date")
        desc_idx = next((i for i, h in enumerate(header) if "desc" in h or "memo" in h), 1)
        amount_idx = next((i for i, h in enumerate(header) if "amount" in h or "debit" in h), 2)
        balance_idx = next((i for i, h in enumerate(header) if "balance" in h), None)
        type_idx = None
        detected = "Frost"
    else:
        # Fallback: assume date=0, desc=1, amount=2
        date_idx, desc_idx, amount_idx = 0, 1, 2
        balance_idx, type_idx = None, None
        detected = "Generic"

    imported = 0
    skipped = 0
    preview_rows = []

    with _connect(db_path) as conn:
        for row in data_rows:
            if not row or len(row) <= max(date_idx, desc_idx, amount_idx):
                continue

            raw_date = row[date_idx].strip()
            parsed_date = _normalise_csv_date(raw_date) if raw_date else None
            if not parsed_date:
                continue

            desc = row[desc_idx].strip()
            raw_amount = row[amount_idx].strip().replace("$", "").replace(",", "")
            raw_amount = raw_amount.replace("(", "-").replace(")", "")
            try:
                amount = float(raw_amount)
            except ValueError:
                continue

            balance = None
            if balance_idx is not None and balance_idx < len(row):
                try:
                    balance = float(row[balance_idx].strip().replace("$", "").replace(",", ""))
                except ValueError:
                    pass

            txn_type = row[type_idx].strip() if type_idx and type_idx < len(row) else None

            # Duplicate detection
            existing = conn.execute(
                """SELECT id FROM bank_statement_rows
                   WHERE account_last4 = ? AND transaction_date = ?
                     AND description = ? AND ABS(amount - ?) < 0.01""",
                (account_last4, parsed_date, desc, amount),
            ).fetchone()
            if existing:
                skipped += 1
                continue

            conn.execute(
                """INSERT INTO bank_statement_rows
                   (import_id, bank, account_last4, transaction_date, description,
                    amount, balance, transaction_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (import_id, detected, account_last4, parsed_date, desc, amount, balance, txn_type),
            )
            imported += 1
            preview_rows.append({
                "date": parsed_date, "description": desc, "amount": amount,
                "balance": balance, "type": txn_type,
            })

        conn.commit()

    return {
        "import_id": import_id, "imported": imported, "skipped": skipped,
        "detected_format": detected, "rows": preview_rows[:50],
    }


def run_bank_reconciliation(import_id: str | None = None, account_last4: str | None = None,
                            month: str | None = None,
                            db_path: str | Path | None = None) -> dict:
    """Auto-match bank statement rows against Tracker records.
    Returns {matched, unmatched_bank, unmatched_tracker, results}."""
    with _connect(db_path) as conn:
        # Get bank rows to reconcile
        clauses, params = ["reconciled = 0"], []
        if import_id:
            clauses.append("import_id = ?"); params.append(import_id)
        if account_last4:
            clauses.append("account_last4 = ?"); params.append(account_last4)
        if month:
            clauses.append("transaction_date LIKE ?"); params.append(f"{month}%")
        where = " AND ".join(clauses)

        bank_rows = conn.execute(
            f"SELECT * FROM bank_statement_rows WHERE {where} ORDER BY transaction_date",
            params,
        ).fetchall()
        bank_rows = [dict(r) for r in bank_rows]

        matched = 0
        results = []

        for br in bank_rows:
            amt = br["amount"]
            dt = br["transaction_date"]
            match_found = False

            # Match against items (GoDaddy orders) — look at total_amount
            if amt < 0:
                # Bank debit — look for expense in items or expense_transactions
                pass
            else:
                # Bank credit — look for GoDaddy order income
                item = conn.execute(
                    """SELECT id, order_id, customer, item_name, total_amount FROM items
                       WHERE ABS(julianday(order_date) - julianday(?)) <= 2
                         AND COALESCE(transaction_status, 'active') = 'active'
                       ORDER BY ABS(julianday(order_date) - julianday(?))""",
                    (dt, dt),
                ).fetchall()
                for it in item:
                    it_amount = _parse_dollar(it["total_amount"])
                    if abs(it_amount - amt) < 0.01:
                        conn.execute(
                            "UPDATE bank_statement_rows SET matched_source='items', matched_id=?, reconciled=1 WHERE id=?",
                            (it["id"], br["id"]),
                        )
                        match_found = True
                        matched += 1
                        br["match_status"] = "matched"
                        br["matched_source"] = "items"
                        br["matched_detail"] = f"Order {it['order_id']} — {it['customer']}"
                        break

            if not match_found and amt < 0:
                # Match against expense_transactions
                exp = conn.execute(
                    """SELECT id, merchant, amount FROM expense_transactions
                       WHERE ABS(julianday(transaction_date) - julianday(?)) <= 2
                         AND ABS(amount - ?) < 0.01
                       ORDER BY ABS(julianday(transaction_date) - julianday(?))
                       LIMIT 1""",
                    (dt, abs(amt), dt),
                ).fetchone()
                if exp:
                    conn.execute(
                        "UPDATE bank_statement_rows SET matched_source='expense_transactions', matched_id=?, reconciled=1 WHERE id=?",
                        (exp["id"], br["id"]),
                    )
                    match_found = True
                    matched += 1
                    br["match_status"] = "matched"
                    br["matched_source"] = "expense_transactions"
                    br["matched_detail"] = f"{exp['merchant']} — {_fmt_dollar(exp['amount'])}"

            if not match_found:
                br["match_status"] = "unmatched_bank"
                br["matched_source"] = None
                br["matched_detail"] = None

            results.append(br)

        conn.commit()

        # Find Tracker records not in bank (for the same period)
        unmatched_tracker = []
        if month:
            tracker_items = conn.execute(
                """SELECT id, order_id, customer, item_name, total_amount, order_date FROM items
                   WHERE order_date LIKE ? AND COALESCE(transaction_status, 'active') = 'active'
                     AND id NOT IN (SELECT matched_id FROM bank_statement_rows WHERE matched_source='items' AND reconciled=1)
                   ORDER BY order_date""",
                (f"{month}%",),
            ).fetchall()
            for it in tracker_items:
                unmatched_tracker.append({
                    "match_status": "unmatched_tracker",
                    "source": "items",
                    "id": it["id"],
                    "description": f"{it['customer']} — {it['item_name']}",
                    "amount": _parse_dollar(it["total_amount"]),
                    "date": it["order_date"],
                })

    return {
        "matched": matched,
        "unmatched_bank": len([r for r in results if r["match_status"] == "unmatched_bank"]),
        "unmatched_tracker": len(unmatched_tracker),
        "bank_results": results,
        "tracker_unmatched": unmatched_tracker,
    }


def _fmt_dollar(n) -> str:
    return f"${n:,.2f}" if n else "$0.00"


def close_period(period: str, closed_by: str = "admin",
                 db_path: str | Path | None = None) -> dict:
    """Close a monthly period. Verifies all bank rows reconciled, generates summary."""
    with _connect(db_path) as conn:
        # Check for unreconciled bank rows
        unreconciled = conn.execute(
            "SELECT COUNT(*) as cnt FROM bank_statement_rows WHERE transaction_date LIKE ? AND reconciled = 0",
            (f"{period}%",),
        ).fetchone()["cnt"]

        # Calculate period totals from allocations
        income = conn.execute(
            "SELECT COALESCE(SUM(tgf_operating), 0) as total FROM acct_allocations WHERE allocation_date LIKE ?",
            (f"{period}%",),
        ).fetchone()["total"]
        expenses = conn.execute(
            "SELECT COALESCE(SUM(course_payable + course_surcharge + godaddy_fee), 0) as total FROM acct_allocations WHERE allocation_date LIKE ?",
            (f"{period}%",),
        ).fetchone()["total"]
        tax = conn.execute(
            "SELECT COALESCE(SUM(tax_reserve), 0) as total FROM acct_allocations WHERE allocation_date LIKE ?",
            (f"{period}%",),
        ).fetchone()["total"]
        net = round(income - expenses, 2)

        conn.execute(
            """INSERT INTO period_closings (period, closed_at, closed_by, total_income, total_expenses, net, tax_reserve, notes)
               VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?)""",
            (period, closed_by, round(income, 2), round(expenses, 2), net, round(tax, 2),
             f"{unreconciled} unreconciled rows" if unreconciled else "All reconciled"),
        )
        conn.commit()

    return {
        "period": period, "total_income": round(income, 2),
        "total_expenses": round(expenses, 2), "net": net,
        "tax_reserve": round(tax, 2), "unreconciled": unreconciled,
    }


def get_reconciliation_summary(month: str, db_path: str | Path | None = None) -> dict:
    """Summary for MCP tool: matched/unmatched counts + dollar totals."""
    with _connect(db_path) as conn:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM bank_statement_rows WHERE transaction_date LIKE ?",
            (f"{month}%",),
        ).fetchone()["cnt"]
        matched = conn.execute(
            "SELECT COUNT(*) as cnt FROM bank_statement_rows WHERE transaction_date LIKE ? AND reconciled = 1",
            (f"{month}%",),
        ).fetchone()["cnt"]
        unmatched = total - matched
        matched_total = conn.execute(
            "SELECT COALESCE(SUM(ABS(amount)), 0) as total FROM bank_statement_rows WHERE transaction_date LIKE ? AND reconciled = 1",
            (f"{month}%",),
        ).fetchone()["total"]
        unmatched_total = conn.execute(
            "SELECT COALESCE(SUM(ABS(amount)), 0) as total FROM bank_statement_rows WHERE transaction_date LIKE ? AND reconciled = 0",
            (f"{month}%",),
        ).fetchone()["total"]
        closing = conn.execute(
            "SELECT * FROM period_closings WHERE period = ?", (month,)
        ).fetchone()

    return {
        "month": month,
        "total_rows": total, "matched": matched, "unmatched": unmatched,
        "matched_dollars": round(matched_total, 2),
        "unmatched_dollars": round(unmatched_total, 2),
        "period_closed": closing is not None,
        "closing": dict(closing) if closing else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Bank Deposit Import & Reconciliation (new tables)
# ═══════════════════════════════════════════════════════════════════════════


def get_bank_accounts(db_path: str | Path | None = None) -> list[dict]:
    """Return all accounts from acct_accounts (the existing accounting system)."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM acct_accounts WHERE is_active = 1 ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]


def import_bank_deposits(file_bytes: bytes, filename: str, account_id: int,
                         db_path: str | Path | None = None) -> dict:
    """Import bank statement file (Chase CSV, Venmo CSV, or PDF).

    Returns {import_batch_id, imported, skipped, format, rows_preview}.
    """
    import csv
    import hashlib
    import io

    batch_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{hashlib.md5(file_bytes).hexdigest()[:8]}"
    text = file_bytes.decode("utf-8", errors="replace")
    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        return _import_pdf_deposits(file_bytes, batch_id, account_id, db_path)

    # CSV parsing
    reader = csv.reader(io.StringIO(text))
    all_rows = list(reader)
    if len(all_rows) < 2:
        return {"import_batch_id": batch_id, "imported": 0, "skipped": 0,
                "format": "empty", "rows_preview": []}

    header = [h.strip().lower() for h in all_rows[0]]
    data_rows = all_rows[1:]

    # Auto-detect format
    if "posting date" in header:
        return _import_chase_csv(data_rows, header, batch_id, account_id, db_path)
    elif any("datetime" in h for h in header) or any("funding" in h for h in header):
        return _import_venmo_csv(data_rows, header, batch_id, account_id, db_path)
    else:
        # Generic CSV: try date/description/amount columns
        return _import_generic_csv(data_rows, header, batch_id, account_id, db_path)


def _import_chase_csv(data_rows, header, batch_id, account_id, db_path):
    """Chase CSV: Details, Posting Date, Description, Amount, Type, Balance, Check or Slip #
    Imports ALL transactions (credits and debits) for full reconciliation."""
    date_idx = header.index("posting date")
    desc_idx = header.index("description") if "description" in header else 2
    amount_idx = header.index("amount") if "amount" in header else 3

    imported, skipped = 0, 0
    preview = []

    with _connect(db_path) as conn:
        for row in data_rows:
            if not row or len(row) <= max(date_idx, desc_idx, amount_idx):
                continue
            raw_date = row[date_idx].strip()
            parsed_date = _normalise_csv_date(raw_date) if raw_date else None
            if not parsed_date:
                continue

            raw_amt = row[amount_idx].strip().replace("$", "").replace(",", "")
            raw_amt = raw_amt.replace("(", "-").replace(")", "")
            try:
                amount = float(raw_amt)
            except (ValueError, TypeError):
                continue
            if amount == 0:
                continue

            desc = row[desc_idx].strip()
            source = "godaddy" if "GODADDY" in desc.upper() else "other"

            existing = conn.execute(
                """SELECT id FROM bank_deposits
                   WHERE account_id = ? AND deposit_date = ? AND ABS(amount - ?) < 0.01
                   AND description = ?""",
                (account_id, parsed_date, amount, desc),
            ).fetchone()
            if existing:
                skipped += 1
                continue

            conn.execute(
                """INSERT INTO bank_deposits
                   (account_id, deposit_date, amount, description, source, import_batch_id, raw_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (account_id, parsed_date, amount, desc, source, batch_id,
                 ",".join(row)),
            )
            imported += 1
            if len(preview) < 50:
                preview.append({"date": parsed_date, "description": desc,
                                "amount": amount, "source": source})

        conn.commit()

    return {"import_batch_id": batch_id, "imported": imported, "skipped": skipped,
            "format": "Chase", "rows_preview": preview}


def _import_venmo_csv(data_rows, header, batch_id, account_id, db_path):
    """Venmo CSV: ID, Datetime, Type, Status, Note, From, To, Amount (total), ..."""
    status_idx = next((i for i, h in enumerate(header) if "status" in h), 3)
    note_idx = next((i for i, h in enumerate(header) if "note" in h), 4)
    from_idx = next((i for i, h in enumerate(header) if h.strip() == "from"), 5)
    amount_idx = next((i for i, h in enumerate(header) if "amount" in h), 7)
    datetime_idx = next((i for i, h in enumerate(header) if "datetime" in h), 1)

    imported, skipped = 0, 0
    preview = []

    with _connect(db_path) as conn:
        for row in data_rows:
            if not row or len(row) <= max(status_idx, amount_idx):
                continue

            status = row[status_idx].strip() if status_idx < len(row) else ""
            if status.lower() != "complete":
                continue

            raw_amt = (row[amount_idx] if amount_idx < len(row) else "0").strip()
            raw_amt = raw_amt.replace("$", "").replace(",", "").replace(" ", "")
            try:
                amount = float(raw_amt) if raw_amt else 0
            except (ValueError, TypeError):
                continue
            if amount == 0:
                continue

            raw_dt = row[datetime_idx].strip() if datetime_idx < len(row) else ""
            parsed_date = _normalise_csv_date(raw_dt.split("T")[0] if "T" in raw_dt else raw_dt)
            if not parsed_date:
                continue

            note = row[note_idx].strip() if note_idx < len(row) else ""
            from_name = row[from_idx].strip() if from_idx < len(row) else ""
            desc = f"{from_name}: {note}" if from_name else note

            existing = conn.execute(
                """SELECT id FROM bank_deposits
                   WHERE account_id = ? AND deposit_date = ? AND ABS(amount - ?) < 0.01
                   AND description = ?""",
                (account_id, parsed_date, amount, desc),
            ).fetchone()
            if existing:
                skipped += 1
                continue

            conn.execute(
                """INSERT INTO bank_deposits
                   (account_id, deposit_date, amount, description, source, import_batch_id, raw_data)
                   VALUES (?, ?, ?, ?, 'venmo', ?, ?)""",
                (account_id, parsed_date, amount, desc, batch_id, ",".join(row)),
            )
            imported += 1
            if len(preview) < 50:
                preview.append({"date": parsed_date, "description": desc,
                                "amount": amount, "source": "venmo"})

        conn.commit()

    return {"import_batch_id": batch_id, "imported": imported, "skipped": skipped,
            "format": "Venmo", "rows_preview": preview}


def import_venmo_statement(csv_text: str, account_label: str,
                           db_path: str | Path | None = None) -> dict:
    """Import Venmo CSV statement with auto-categorization and accounting entries.

    Handles two formats:
      - Format 1 (Personal): starts with "Account Statement" header row
      - Format 2 (Business): starts with "Transaction ID" header row

    Writes to both bank_deposits and acct_transactions for each row.

    Returns {imported, skipped, format, categorized: {category: count, ...},
             rows_preview}.
    """
    import csv
    import hashlib
    import io
    import re

    batch_id = (f"{datetime.now().strftime('%Y%m%d%H%M%S')}-"
                f"{hashlib.md5(csv_text.encode()).hexdigest()[:8]}")

    reader = csv.reader(io.StringIO(csv_text))
    all_rows = list(reader)
    if len(all_rows) < 2:
        return {"imported": 0, "skipped": 0, "format": "empty",
                "categorized": {}, "rows_preview": []}

    # --- Detect format ---
    first_row_joined = ",".join(all_rows[0]).strip()

    if "Account Statement" in first_row_joined:
        fmt = "Venmo Personal"
        # Row 0 = account header, Row 1 = "Account Activity",
        # Row 2 = column headers (starts with blank), Row 3 = balance (skip),
        # data starts at Row 4
        if len(all_rows) < 5:
            return {"imported": 0, "skipped": 0, "format": fmt,
                    "categorized": {}, "rows_preview": []}
        header = [h.strip().lower() for h in all_rows[2]]
        data_rows = all_rows[4:]
        # Column indices (header has leading blank col)
        id_idx = next((i for i, h in enumerate(header) if h == "id"), 1)
        dt_idx = next((i for i, h in enumerate(header) if "datetime" in h), 2)
        type_idx = next((i for i, h in enumerate(header) if h == "type"), 3)
        status_idx = next((i for i, h in enumerate(header) if "status" in h), 4)
        note_idx = next((i for i, h in enumerate(header) if "note" in h), 5)
        from_idx = next((i for i, h in enumerate(header) if h == "from"), 6)
        to_idx = next((i for i, h in enumerate(header) if h == "to"), 7)
        amt_idx = next((i for i, h in enumerate(header)
                        if "amount" in h and "total" in h), 8)
        if amt_idx == 8:
            amt_idx = next((i for i, h in enumerate(header) if "amount" in h), 8)

    elif first_row_joined.lower().startswith("transaction id"):
        fmt = "Venmo Business"
        header = [h.strip().lower() for h in all_rows[0]]
        data_rows = all_rows[1:]
        id_idx = next((i for i, h in enumerate(header) if "transaction id" in h), 0)
        # Date and Time are separate columns
        date_col_idx = next((i for i, h in enumerate(header) if h == "date"), 1)
        time_col_idx = next((i for i, h in enumerate(header)
                             if h.startswith("time")), 2)
        type_idx = next((i for i, h in enumerate(header) if h == "type"), 3)
        status_idx = next((i for i, h in enumerate(header) if "status" in h), 4)
        note_idx = next((i for i, h in enumerate(header) if "note" in h), 5)
        from_idx = next((i for i, h in enumerate(header) if h == "from"), 6)
        to_idx = next((i for i, h in enumerate(header) if h == "to"), 7)
        amt_idx = next((i for i, h in enumerate(header)
                        if "amount" in h and "total" in h), 8)
        if amt_idx == 8:
            amt_idx = next((i for i, h in enumerate(header) if "amount" in h), 8)
        dt_idx = None  # handled via date_col_idx + time_col_idx
    else:
        return {"imported": 0, "skipped": 0, "format": "unknown",
                "categorized": {}, "rows_preview": [],
                "error": "Unrecognized Venmo CSV format"}

    # --- Helpers ---
    def _parse_venmo_amount(raw: str) -> float | None:
        """Parse '- $16.00' or '+ $5.00' into signed float."""
        cleaned = raw.replace("$", "").replace(",", "").replace(" ", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _extract_customer(note: str, to_name: str, is_outgoing: bool) -> str:
        """Extract customer name from Note or To field."""
        # Try 'FIRSTNAME LASTNAME - reason' pattern in note
        m = re.match(r"^(.+?)\s*-\s+", note)
        if m:
            raw_name = m.group(1).strip()
            # Normalize to Title Case (notes use ALL CAPS for last names)
            return raw_name.title()
        # For outgoing, use the To field
        if is_outgoing and to_name:
            return to_name.title()
        # Fallback: use full note as-is (title-cased)
        if note:
            return note.strip().title()
        return ""

    def _categorize(note: str, is_incoming: bool) -> tuple[str, str]:
        """Return (category, entry_type) from note content."""
        note_upper = note.upper()
        if "WINNINGS" in note_upper or "WINNING" in note_upper:
            return "prize_payout", "expense"
        if "REFUND" in note_upper:
            return "refund", "expense"
        if "DRINKS" in note_upper or "DRINK" in note_upper:
            return "event_expense", "expense"
        if is_incoming:
            return "addon", "income"
        return "miscellaneous", "expense"

    imported, skipped = 0, 0
    preview: list[dict] = []
    categorized: dict[str, int] = {}

    with _connect(db_path) as conn:
        # Look up Venmo account_id from acct_accounts so the value stored in
        # bank_deposits.account_id matches every other import path (Chase /
        # generic CSV imports also store an acct_accounts.id).
        acct_row = conn.execute(
            "SELECT id FROM acct_accounts "
            "WHERE is_active = 1 AND LOWER(name) LIKE 'venmo%' AND account_type = 'venmo' "
            "LIMIT 1"
        ).fetchone()
        if not acct_row:
            acct_row = conn.execute(
                "SELECT id FROM acct_accounts "
                "WHERE is_active = 1 AND account_type = 'venmo' LIMIT 1"
            ).fetchone()
        account_id = acct_row["id"] if acct_row else None
        if account_id is None:
            return {"imported": 0, "skipped": 0, "format": fmt,
                    "categorized": {}, "rows_preview": [],
                    "error": "No Venmo account found in acct_accounts"}

        for row in data_rows:
            if not row:
                continue

            # --- Extract venmo_id ---
            raw_id = row[id_idx].strip() if id_idx < len(row) else ""
            # Business format uses triple-quoted IDs: """4548432077528504170"""
            venmo_id = raw_id.strip('"').strip()
            if not venmo_id:
                continue  # Skip disclaimer rows / empty rows

            # --- Extract status ---
            status = row[status_idx].strip() if status_idx < len(row) else ""
            if status.lower() != "complete":
                continue

            # --- Parse amount ---
            raw_amt = row[amt_idx].strip() if amt_idx < len(row) else ""
            amount = _parse_venmo_amount(raw_amt)
            if amount is None or amount == 0:
                continue

            is_incoming = amount > 0

            # --- Parse date ---
            if fmt == "Venmo Personal":
                raw_dt = row[dt_idx].strip() if dt_idx < len(row) else ""
                # ISO 8601: 2026-03-01T23:15:56
                parsed_date = _normalise_csv_date(
                    raw_dt.split("T")[0] if "T" in raw_dt else raw_dt)
            else:
                # Business: separate Date and Time columns
                raw_date_str = (row[date_col_idx].strip()
                                if date_col_idx < len(row) else "")
                parsed_date = _normalise_csv_date(raw_date_str)

            if not parsed_date:
                continue

            # --- Extract fields ---
            note = row[note_idx].strip() if note_idx < len(row) else ""
            from_name = row[from_idx].strip() if from_idx < len(row) else ""
            to_name = row[to_idx].strip() if to_idx < len(row) else ""

            # --- Auto-categorize ---
            category, entry_type = _categorize(note, is_incoming)
            categorized[category] = categorized.get(category, 0) + 1

            # --- Extract customer name ---
            customer = _extract_customer(note, to_name, not is_incoming)

            # --- Build description ---
            if is_incoming and from_name:
                desc = f"{from_name}: {note}" if note else from_name
            elif not is_incoming and to_name:
                desc = f"{to_name}: {note}" if note else to_name
            else:
                desc = note or "(no note)"

            source_ref = f"venmo-{venmo_id}"

            # --- Dedup: bank_deposits via source_ref in raw_data ---
            existing_dep = conn.execute(
                "SELECT id FROM bank_deposits WHERE raw_data = ?",
                (source_ref,),
            ).fetchone()

            # --- Dedup: acct_transactions via source_ref ---
            existing_txn = conn.execute(
                "SELECT id FROM acct_transactions WHERE source_ref = ? "
                "AND COALESCE(status, 'active') = 'active'",
                (source_ref,),
            ).fetchone()

            if existing_dep and existing_txn:
                skipped += 1
                continue

            # --- Write bank_deposit ---
            if not existing_dep:
                conn.execute(
                    """INSERT INTO bank_deposits
                       (account_id, deposit_date, amount, description,
                        source, import_batch_id, raw_data)
                       VALUES (?, ?, ?, ?, 'venmo', ?, ?)""",
                    (account_id, parsed_date, amount, desc,
                     batch_id, source_ref),
                )

            # --- Write acct_transaction ---
            if not existing_txn:
                _write_acct_entry(
                    conn,
                    entry_type=entry_type,
                    category=category,
                    source="venmo",
                    amount=amount,
                    description=desc,
                    account="Venmo",
                    source_ref=source_ref,
                    date=parsed_date,
                    customer=customer,
                )

            imported += 1
            if len(preview) < 50:
                preview.append({
                    "date": parsed_date, "description": desc,
                    "amount": amount, "category": category,
                    "entry_type": entry_type, "customer": customer,
                })

        # Reverse-match: newly imported Venmo prize_payouts may cover
        # previously-pending tgf_payouts. Try to link them now.
        matched_payouts = _match_pending_payouts_to_new_venmo(conn)

        conn.commit()

    return {"imported": imported, "skipped": skipped, "format": fmt,
            "categorized": categorized, "rows_preview": preview,
            "payouts_matched": matched_payouts}


def _import_generic_csv(data_rows, header, batch_id, account_id, db_path):
    """Fallback for unknown CSV formats."""
    date_idx = next((i for i, h in enumerate(header) if "date" in h), 0)
    desc_idx = next((i for i, h in enumerate(header) if "desc" in h or "memo" in h), 1)
    amount_idx = next((i for i, h in enumerate(header) if "amount" in h or "credit" in h), 2)

    imported, skipped = 0, 0
    preview = []

    with _connect(db_path) as conn:
        for row in data_rows:
            if not row or len(row) <= max(date_idx, desc_idx, amount_idx):
                continue
            raw_date = row[date_idx].strip()
            parsed_date = _normalise_csv_date(raw_date) if raw_date else None
            if not parsed_date:
                continue

            raw_amt = row[amount_idx].strip().replace("$", "").replace(",", "")
            raw_amt = raw_amt.replace("(", "-").replace(")", "")
            try:
                amount = float(raw_amt) if raw_amt else 0
            except (ValueError, TypeError):
                continue
            if amount == 0:
                continue

            desc = row[desc_idx].strip()
            source = "godaddy" if "GODADDY" in desc.upper() else "other"
            existing = conn.execute(
                """SELECT id FROM bank_deposits
                   WHERE account_id = ? AND deposit_date = ? AND ABS(amount - ?) < 0.01
                   AND description = ?""",
                (account_id, parsed_date, amount, desc),
            ).fetchone()
            if existing:
                skipped += 1
                continue

            conn.execute(
                """INSERT INTO bank_deposits
                   (account_id, deposit_date, amount, description, source, import_batch_id, raw_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (account_id, parsed_date, amount, desc, source, batch_id, ",".join(row)),
            )
            imported += 1
            if len(preview) < 50:
                preview.append({"date": parsed_date, "description": desc,
                                "amount": amount, "source": "other"})

        conn.commit()

    return {"import_batch_id": batch_id, "imported": imported, "skipped": skipped,
            "format": "Generic", "rows_preview": preview}


def _import_pdf_deposits(file_bytes, batch_id, account_id, db_path):
    """Extract deposits from a PDF bank statement using pdfplumber + Claude AI."""
    try:
        import pdfplumber
    except ImportError:
        return {"import_batch_id": batch_id, "imported": 0, "skipped": 0,
                "format": "PDF", "error": "pdfplumber not installed",
                "rows_preview": []}

    text_pages = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text_pages.append(page.extract_text() or "")
    full_text = "\n---PAGE BREAK---\n".join(text_pages)

    if not full_text.strip():
        return {"import_batch_id": batch_id, "imported": 0, "skipped": 0,
                "format": "PDF", "error": "No text extracted from PDF",
                "rows_preview": []}

    # Use Claude to parse transaction rows
    try:
        client = _anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            messages=[{"role": "user", "content": (
                "Parse this bank statement text into a JSON array of ALL transactions "
                "(both deposits/credits AND withdrawals/debits). "
                "Use POSITIVE amounts for deposits/credits and NEGATIVE amounts for withdrawals/debits. "
                "Include the full description (transaction type + payee/description + any reference numbers). "
                "Return ONLY valid JSON:\n"
                '[{"date": "YYYY-MM-DD", "description": "...", "amount": 123.45}]\n\n'
                f"Bank statement text:\n{full_text[:30000]}"
            )}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed_rows = json.loads(raw)
    except Exception as e:
        return {"import_batch_id": batch_id, "imported": 0, "skipped": 0,
                "format": "PDF", "error": f"AI parsing failed: {e}",
                "rows_preview": []}

    imported, skipped = 0, 0
    preview = []

    with _connect(db_path) as conn:
        for pr in parsed_rows:
            deposit_date = pr.get("date", "")
            raw_amt = pr.get("amount")
            if isinstance(raw_amt, (int, float)):
                amount = float(raw_amt)
            else:
                amount = _parse_dollar(raw_amt)
                # Restore negative sign if original had it
                if raw_amt and str(raw_amt).strip().startswith("-"):
                    amount = -abs(amount)
            desc = pr.get("description", "")
            if not deposit_date or amount == 0:
                continue

            existing = conn.execute(
                """SELECT id FROM bank_deposits
                   WHERE account_id = ? AND deposit_date = ? AND ABS(amount - ?) < 0.01
                   AND description = ?""",
                (account_id, deposit_date, amount, desc),
            ).fetchone()
            if existing:
                skipped += 1
                continue

            source = "godaddy" if "GODADDY" in desc.upper() else "other"
            conn.execute(
                """INSERT INTO bank_deposits
                   (account_id, deposit_date, amount, description, source, import_batch_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (account_id, deposit_date, amount, desc, source, batch_id),
            )
            imported += 1
            if len(preview) < 50:
                preview.append({"date": deposit_date, "description": desc,
                                "amount": amount, "source": source})

        conn.commit()

    return {"import_batch_id": batch_id, "imported": imported, "skipped": skipped,
            "format": "PDF (AI-parsed)", "rows_preview": preview}


_GODADDY_BATCH_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})\b")


def _parse_godaddy_batch_date(description: str, deposit_date: str) -> str:
    """Extract MM/DD from a GoDaddy deposit description and resolve to ISO date.

    GoDaddy descriptions look like "GoDaddy Payments Dep 04/26 80229e16-e5e6-4".
    The MM/DD is the batch close date, which is typically deposit_date - 1 day.
    Falls back to deposit_date - 1 day if the description has no MM/DD token.
    Handles year rollover (a 12/31 batch deposited on 01/02 of the next year).
    """
    try:
        dep_dt = datetime.strptime(deposit_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return deposit_date
    fallback = (dep_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    if not description:
        return fallback
    match = _GODADDY_BATCH_DATE_RE.search(description)
    if not match:
        return fallback
    try:
        month, day = int(match.group(1)), int(match.group(2))
        candidate = datetime(dep_dt.year, month, day)
        if candidate > dep_dt:
            candidate = datetime(dep_dt.year - 1, month, day)
        return candidate.strftime("%Y-%m-%d")
    except ValueError:
        return fallback


def _subset_sum_match(values: list[float], target: float,
                      tolerance: float = 0.50) -> list[int] | None:
    """Find indices of a subset of `values` whose sum ≈ `target`.

    Exact recursive search with suffix-sum pruning for n ≤ 25; greedy
    descending fit for larger pools. Returns indices into the input list,
    or None if no subset is within `tolerance` of `target`. Works in
    integer cents internally to avoid float drift.
    """
    n = len(values)
    if n == 0:
        return None
    for i, v in enumerate(values):
        if abs(v - target) < tolerance:
            return [i]
    positive_total = sum(v for v in values if v > 0)
    if positive_total < target - tolerance:
        return None

    if n <= 25:
        cents = [round(v * 100) for v in values]
        target_c = round(target * 100)
        tol_c = round(tolerance * 100)
        order = sorted(range(n), key=lambda i: -cents[i])
        sc = [cents[i] for i in order]
        suffix = [0] * (n + 1)
        for i in range(n - 1, -1, -1):
            suffix[i] = suffix[i + 1] + max(sc[i], 0)
        found: list[int] = []

        def dfs(idx: int, remaining: int, picked: list[int]) -> bool:
            if abs(remaining) <= tol_c:
                found.extend(picked)
                return True
            if idx >= n:
                return False
            if suffix[idx] < remaining - tol_c:
                return False
            if sc[idx] <= remaining + tol_c:
                picked.append(idx)
                if dfs(idx + 1, remaining - sc[idx], picked):
                    return True
                picked.pop()
            return dfs(idx + 1, remaining, picked)

        if dfs(0, target_c, []):
            return [order[i] for i in found]
        return None

    indexed = sorted(range(n), key=lambda i: -values[i])
    picked: list[int] = []
    running = 0.0
    for idx in indexed:
        v = values[idx]
        if v <= 0:
            continue
        if running + v <= target + tolerance:
            picked.append(idx)
            running += v
            if abs(running - target) < tolerance:
                return picked
    return picked if abs(running - target) < tolerance else None


def run_deposit_auto_match(account_id: int | None = None,
                           db_path: str | Path | None = None) -> dict:
    """Auto-match bank_deposits to acct_transactions.

    GoDaddy batches: parse MM/DD from description, subset-sum match in a
    2-day window around the batch date, sequentially claim orders so
    consecutive batches don't double-count.
    Venmo: match by amount + customer name in description.
    Other: match by amount + date ± 1 day, flag for manual.

    Returns {auto_matched, partial, unmatched, details}.
    """
    results = {"auto_matched": 0, "partial": 0, "unmatched": 0, "details": []}

    with _connect(db_path) as conn:
        where = "d.status != 'matched'"
        params = []
        if account_id:
            where += " AND d.account_id = ?"
            params.append(account_id)

        deposits = conn.execute(
            f"""SELECT d.*, ba.account_type
                FROM bank_deposits d
                JOIN acct_accounts ba ON ba.id = d.account_id
                WHERE {where}
                ORDER BY d.deposit_date""",
            params,
        ).fetchall()
        deposits = [dict(d) for d in deposits]

        # Track acct_transaction IDs claimed by earlier GoDaddy deposits in this
        # run. Sequential claiming prevents the same order from satisfying two
        # consecutive batch deposits.
        claimed_txn_ids: set[int] = set()

        for dep in deposits:
            dep_id = dep["id"]
            dep_date = dep["deposit_date"]
            dep_amt = dep["amount"]
            dep_desc = (dep["description"] or "").upper()
            dep_source = dep.get("source", "")
            acct_type = dep.get("account_type", "") or ""
            # Defensive fallback: if the account join returned no row (legacy
            # row referencing a stale id, or an as-yet-unmigrated import path),
            # use the deposit's source field to drive branch selection so the
            # Venmo / GoDaddy logic still fires.
            if not acct_type and dep_source:
                acct_type = dep_source

            matched_txn_ids = []
            confidence = 0.0
            detail = ""

            if dep_source == "godaddy" or "GODADDY" in dep_desc:
                # Parse the MM/DD batch date out of the description
                # ("GoDaddy Payments Dep 04/26 ..."). Falls back to
                # deposit_date - 1 day if absent.
                batch_date = _parse_godaddy_batch_date(
                    dep.get("description") or "", dep_date,
                )
                try:
                    bd_obj = datetime.strptime(batch_date, "%Y-%m-%d")
                except ValueError:
                    bd_obj = None

                matched_indices: list[int] | None = None
                candidates: list[dict] = []
                used_widened = False

                if bd_obj is not None:
                    # Two passes: a tight 2-day window keyed on the batch
                    # date, then a 4-day fallback for delayed deposits.
                    windows = [
                        ((-1, 0), False),
                        ((-2, 1), True),
                    ]
                    for (off_lo, off_hi), is_wide in windows:
                        win_start = (bd_obj + timedelta(days=off_lo)).strftime("%Y-%m-%d")
                        win_end = (bd_obj + timedelta(days=off_hi)).strftime("%Y-%m-%d")
                        excluded = list(claimed_txn_ids)
                        excl_clause = ""
                        if excluded:
                            excl_clause = (
                                f" AND id NOT IN ({','.join('?' * len(excluded))})"
                            )
                        rows = conn.execute(
                            f"""SELECT id, amount, net_deposit, merchant_fee,
                                       date, customer, event_name, order_id
                                FROM acct_transactions
                                WHERE category = 'godaddy_order'
                                  AND COALESCE(status, 'active') NOT IN ('reversed', 'merged')
                                  AND date BETWEEN ? AND ?
                                  AND id NOT IN (
                                      SELECT acct_transaction_id
                                      FROM reconciliation_matches
                                  )
                                  {excl_clause}
                                ORDER BY date""",
                            [win_start, win_end, *excluded],
                        ).fetchall()
                        candidates = [dict(r) for r in rows]
                        if not candidates:
                            continue
                        values = [
                            (c.get("net_deposit") or c["amount"]) for c in candidates
                        ]
                        matched_indices = _subset_sum_match(
                            values, dep_amt, tolerance=0.50,
                        )
                        if matched_indices:
                            used_widened = is_wide
                            break

                if matched_indices:
                    matched_txn_ids = [candidates[i]["id"] for i in matched_indices]
                    sub_sum = sum(
                        (candidates[i].get("net_deposit") or candidates[i]["amount"])
                        for i in matched_indices
                    )
                    gap = abs(sub_sum - dep_amt)
                    if used_widened:
                        confidence = 0.75
                        detail = (
                            f"Wide subset match: {len(matched_txn_ids)} orders, "
                            f"gap ${gap:.2f}, batch {batch_date}"
                        )
                    else:
                        confidence = 0.92
                        detail = (
                            f"Batch subset match: {len(matched_txn_ids)} orders, "
                            f"gap ${gap:.2f}, batch {batch_date}"
                        )
                    # Claim these IDs so subsequent GoDaddy deposits in this
                    # run won't re-pull them as candidates.
                    claimed_txn_ids.update(matched_txn_ids)
                else:
                    logger.info(
                        "GoDaddy auto-match: no subset found dep_id=%s "
                        "amt=%.2f batch=%s",
                        dep_id, dep_amt, batch_date,
                    )

            elif acct_type == "venmo" or dep_source == "venmo":
                # Venmo: match by exact amount + customer name
                candidates = conn.execute(
                    """SELECT id, amount, date, customer, event_name
                       FROM acct_transactions
                       WHERE entry_type = 'income'
                       AND source IN ('venmo', 'cash', 'zelle')
                       AND COALESCE(status, 'active') = 'active'
                       AND ABS(amount - ?) < 0.01
                       AND ABS(julianday(date) - julianday(?)) <= 1
                       AND id NOT IN (SELECT acct_transaction_id FROM reconciliation_matches)""",
                    (dep_amt, dep_date),
                ).fetchall()
                candidates = [dict(c) for c in candidates]

                for c in candidates:
                    cust_upper = (c.get("customer") or "").upper()
                    if cust_upper and cust_upper in dep_desc:
                        matched_txn_ids = [c["id"]]
                        confidence = 0.95
                        detail = f"Venmo name match: {c['customer']}"
                        break
                if not matched_txn_ids and len(candidates) == 1:
                    matched_txn_ids = [candidates[0]["id"]]
                    confidence = 0.70
                    detail = f"Venmo amount match (no name): {candidates[0]['customer']}"

            elif dep_amt < 0:
                # Negative deposit = bank debit → match against expense ledger entries.
                # Chase alerts arrive days after posting, so use a wider date window (±10 days).
                # Amount may differ by a few cents, so use ±$1 tolerance.
                abs_dep = abs(dep_amt)
                candidates = conn.execute(
                    """SELECT id, COALESCE(amount, total_amount, 0) as amt,
                              date, description, customer
                       FROM acct_transactions
                       WHERE entry_type = 'expense'
                       AND COALESCE(status, 'active') NOT IN ('reversed', 'merged', 'reconciled')
                       AND ABS(COALESCE(amount, total_amount, 0) - ?) < 1.00
                       AND ABS(julianday(date) - julianday(?)) <= 10
                       AND id NOT IN (SELECT acct_transaction_id FROM reconciliation_matches)
                       ORDER BY ABS(COALESCE(amount, total_amount, 0) - ?),
                                ABS(julianday(date) - julianday(?))""",
                    (abs_dep, dep_date, abs_dep, dep_date),
                ).fetchall()
                candidates = [dict(c) for c in candidates]

                for c in candidates:
                    c_desc_up = (c.get("description") or "").upper()
                    c_cust_up = (c.get("customer") or "").upper()
                    # Boost confidence when description/merchant appears in bank desc or vice versa
                    desc_match = (c_desc_up and c_desc_up in dep_desc) or \
                                 (c_cust_up and c_cust_up in dep_desc) or \
                                 (dep_desc and c_desc_up and dep_desc in c_desc_up)
                    amt_exact = abs(c["amt"] - abs_dep) < 0.02
                    if desc_match and amt_exact:
                        matched_txn_ids = [c["id"]]
                        confidence = 0.85
                        detail = f"Expense match: {c['description']} (desc+amount)"
                        break
                    elif desc_match:
                        matched_txn_ids = [c["id"]]
                        confidence = 0.65
                        detail = f"Expense match: {c['description']} (desc, amount ~${c['amt']:.2f})"
                        break

                if not matched_txn_ids and len(candidates) == 1:
                    matched_txn_ids = [candidates[0]["id"]]
                    confidence = 0.55
                    detail = f"Expense amount match: {candidates[0]['description']} (needs confirm)"

            else:
                # Zelle/other: match by amount + date ± 1 day, always flag
                candidates = conn.execute(
                    """SELECT id, amount, date, customer, event_name
                       FROM acct_transactions
                       WHERE entry_type = 'income'
                       AND COALESCE(status, 'active') = 'active'
                       AND ABS(amount - ?) < 0.01
                       AND ABS(julianday(date) - julianday(?)) <= 1
                       AND id NOT IN (SELECT acct_transaction_id FROM reconciliation_matches)""",
                    (dep_amt, dep_date),
                ).fetchall()
                candidates = [dict(c) for c in candidates]
                if candidates:
                    matched_txn_ids = [candidates[0]["id"]]
                    confidence = 0.60
                    detail = f"Amount+date match: {candidates[0]['customer']} (needs manual confirm)"

            # Create matches and update status
            if matched_txn_ids:
                for txn_id in matched_txn_ids:
                    try:
                        conn.execute(
                            """INSERT OR IGNORE INTO reconciliation_matches
                               (bank_deposit_id, acct_transaction_id, match_type, match_confidence)
                               VALUES (?, ?, 'auto', ?)""",
                            (dep_id, txn_id, confidence),
                        )
                    except sqlite3.IntegrityError:
                        pass

                new_status = "matched" if confidence >= 0.85 else "partial"
                conn.execute(
                    "UPDATE bank_deposits SET status = ? WHERE id = ?",
                    (new_status, dep_id),
                )

                # Mark matched acct_transactions as reconciled
                if new_status == "matched":
                    for txn_id in matched_txn_ids:
                        conn.execute(
                            "UPDATE acct_transactions SET status = 'reconciled' WHERE id = ?",
                            (txn_id,),
                        )

                if new_status == "matched":
                    results["auto_matched"] += 1
                else:
                    results["partial"] += 1
                results["details"].append({
                    "deposit_id": dep_id, "date": dep_date, "amount": dep_amt,
                    "status": new_status, "confidence": confidence,
                    "matched_txns": len(matched_txn_ids), "detail": detail,
                })
            else:
                results["unmatched"] += 1

        conn.commit()

    return results


def create_entry_from_deposit(deposit_id: int, txn_type: str = "expense",
                              category_name: str | None = None,
                              entity_name: str | None = None,
                              notes: str | None = None,
                              description: str | None = None,
                              date_override: str | None = None,
                              amount_override: float | None = None,
                              event_name: str | None = None,
                              entry_type: str | None = None,
                              db_path: str | Path | None = None) -> dict:
    """Create an acct_transaction from a bank deposit and immediately reconcile it.

    Use this for deposits that have no matching system transaction — e.g. a bank
    row for a manual payment, transfer, or any transaction not parsed from email.
    The new ledger entry is marked reconciled and the deposit status → matched.
    """
    with _connect(db_path) as conn:
        dep = conn.execute(
            "SELECT * FROM bank_deposits WHERE id = ?", (deposit_id,)
        ).fetchone()
        if not dep:
            return {"error": f"deposit {deposit_id} not found"}
        dep = dict(dep)

        # Resolve category FK
        category_id = None
        if category_name:
            row = conn.execute(
                "SELECT id FROM acct_categories WHERE LOWER(name) = LOWER(?) LIMIT 1",
                (category_name,),
            ).fetchone()
            if row:
                category_id = row["id"]

        # Resolve entity FK
        entity_id = None
        if entity_name:
            row = conn.execute(
                "SELECT id FROM acct_entities WHERE LOWER(short_name) = LOWER(?) OR LOWER(name) = LOWER(?) LIMIT 1",
                (entity_name, entity_name),
            ).fetchone()
            if row:
                entity_id = row["id"]

        # acct_splits.entity_id is NOT NULL. If the caller did not pass an
        # entity_name, or the name didn't resolve, fall back to the first
        # active entity so the split insert doesn't crash.
        if entity_id is None:
            row = conn.execute(
                "SELECT id FROM acct_entities WHERE is_active = 1 ORDER BY id LIMIT 1"
            ).fetchone()
            if row:
                entity_id = row["id"]

        # Use the deposit's bank account → map to acct_accounts by type
        account_id = dep.get("account_id")
        acct_account_id = None
        if account_id:
            # Try to find a matching acct_account by name or type
            ba = conn.execute(
                "SELECT name, account_type FROM bank_accounts WHERE id = ?", (account_id,)
            ).fetchone()
            if ba:
                acct_row = conn.execute(
                    """SELECT id FROM acct_accounts
                       WHERE is_active = 1
                         AND (LOWER(name) LIKE LOWER(?) OR account_type = ?)
                       LIMIT 1""",
                    (f"%{ba['name']}%", ba["account_type"]),
                ).fetchone()
                if acct_row:
                    acct_account_id = acct_row["id"]

        amount    = amount_override if amount_override is not None else float(dep.get("amount") or 0)
        desc      = description or dep.get("description") or "Bank deposit"
        date      = date_override or dep.get("deposit_date") or datetime.utcnow().strftime("%Y-%m-%d")
        source_ref = f"bank-deposit-{deposit_id}"
        # Map entry_type to legacy type column
        if entry_type:
            txn_type = {"income": "income", "expense": "expense",
                        "contra": "expense", "liability": "expense"}.get(entry_type, txn_type)

        # Check idempotency
        existing = conn.execute(
            "SELECT id FROM acct_transactions WHERE source_ref = ?", (source_ref,)
        ).fetchone()
        if existing:
            return {"skipped": True, "acct_transaction_id": existing["id"]}

        cur = conn.execute(
            """INSERT INTO acct_transactions
               (date, description, total_amount, type, account_id, source, source_ref,
                notes, status, entry_type, event_name)
               VALUES (?, ?, ?, ?, ?, 'manual', ?, ?, 'reconciled', ?, ?)""",
            (date, desc, abs(amount), txn_type, acct_account_id, source_ref, notes,
             entry_type or txn_type, event_name),
        )
        txn_id = cur.lastrowid

        # Create split
        conn.execute(
            """INSERT INTO acct_splits (transaction_id, entity_id, category_id, amount)
               VALUES (?, ?, ?, ?)""",
            (txn_id, entity_id, category_id, amount),
        )

        # Immediately reconcile: match deposit → new transaction
        conn.execute(
            """INSERT OR IGNORE INTO reconciliation_matches
               (bank_deposit_id, acct_transaction_id, match_type, match_confidence)
               VALUES (?, ?, 'manual', 1.0)""",
            (deposit_id, txn_id),
        )
        conn.execute(
            "UPDATE bank_deposits SET status = 'matched' WHERE id = ?", (deposit_id,)
        )
        conn.commit()

    return {"created": True, "acct_transaction_id": txn_id, "deposit_id": deposit_id}


def manual_match_deposit(bank_deposit_id: int, acct_transaction_id: int,
                         db_path: str | Path | None = None) -> dict:
    """Manually match a bank deposit to an acct_transaction."""
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO reconciliation_matches
               (bank_deposit_id, acct_transaction_id, match_type, match_confidence)
               VALUES (?, ?, 'manual', 1.0)""",
            (bank_deposit_id, acct_transaction_id),
        )
        # Check if all matches for this deposit are confirmed
        conn.execute(
            "UPDATE bank_deposits SET status = 'matched' WHERE id = ?",
            (bank_deposit_id,),
        )
        conn.execute(
            "UPDATE acct_transactions SET status = 'reconciled' WHERE id = ?",
            (acct_transaction_id,),
        )
        conn.commit()
    return {"status": "ok"}


def batch_match_deposit(bank_deposit_id: int, acct_transaction_ids: list[int],
                        db_path: str | Path | None = None) -> dict:
    """Match multiple acct_transactions to a single bank deposit (1:many).

    Used for GoDaddy daily batch deposits that contain multiple orders.
    """
    with _connect(db_path) as conn:
        matched = 0
        for tid in acct_transaction_ids:
            conn.execute(
                """INSERT OR IGNORE INTO reconciliation_matches
                   (bank_deposit_id, acct_transaction_id, match_type, match_confidence)
                   VALUES (?, ?, 'manual', 1.0)""",
                (bank_deposit_id, tid),
            )
            conn.execute(
                "UPDATE acct_transactions SET status = 'reconciled' WHERE id = ?",
                (tid,),
            )
            matched += 1
        conn.execute(
            "UPDATE bank_deposits SET status = 'matched' WHERE id = ?",
            (bank_deposit_id,),
        )
        conn.commit()
    return {"status": "ok", "matched": matched}


def unmatch_deposit(bank_deposit_id: int, acct_transaction_id: int | None = None,
                    db_path: str | Path | None = None) -> dict:
    """Remove a reconciliation match. If acct_transaction_id is None, remove all matches."""
    with _connect(db_path) as conn:
        if acct_transaction_id:
            conn.execute(
                "DELETE FROM reconciliation_matches WHERE bank_deposit_id = ? AND acct_transaction_id = ?",
                (bank_deposit_id, acct_transaction_id),
            )
            conn.execute(
                "UPDATE acct_transactions SET status = 'active' WHERE id = ?",
                (acct_transaction_id,),
            )
        else:
            txn_ids = [r[0] for r in conn.execute(
                "SELECT acct_transaction_id FROM reconciliation_matches WHERE bank_deposit_id = ?",
                (bank_deposit_id,),
            ).fetchall()]
            conn.execute(
                "DELETE FROM reconciliation_matches WHERE bank_deposit_id = ?",
                (bank_deposit_id,),
            )
            for tid in txn_ids:
                conn.execute(
                    "UPDATE acct_transactions SET status = 'active' WHERE id = ?", (tid,),
                )

        # Reset deposit status
        remaining = conn.execute(
            "SELECT COUNT(*) as cnt FROM reconciliation_matches WHERE bank_deposit_id = ?",
            (bank_deposit_id,),
        ).fetchone()["cnt"]
        new_status = "matched" if remaining > 0 else "unmatched"
        conn.execute(
            "UPDATE bank_deposits SET status = ? WHERE id = ?",
            (new_status, bank_deposit_id),
        )
        conn.commit()
    return {"status": "ok"}


def record_internal_transfer(deposit_id: int, from_account: str, to_account: str,
                             notes: str = "", db_path: str | Path | None = None) -> dict:
    """Record a bank-to-bank internal transfer (e.g. Chase → Venmo funding sweep).

    Creates a transfer acct_transaction, links it to the bank deposit, and marks
    the deposit as matched so it no longer appears in the unmatched queue.
    """
    with _connect(db_path) as conn:
        dep = conn.execute("SELECT * FROM bank_deposits WHERE id = ?", (deposit_id,)).fetchone()
        if not dep:
            return {"error": "deposit not found"}
        dep = dict(dep)
        amount = abs(dep["amount"])
        dep_date = dep["deposit_date"]
        description = notes or f"Internal transfer: {from_account} → {to_account}"

        cur = conn.execute(
            """INSERT INTO acct_transactions
               (date, description, total_amount, type, source, source_ref,
                entry_type, category, amount, account, status)
               VALUES (?, ?, ?, 'transfer', 'manual', ?,
                       'transfer', 'account_transfer', ?, ?, 'reconciled')""",
            (dep_date, description, amount,
             f"INTXFER-{deposit_id}", amount, from_account),
        )
        txn_id = cur.lastrowid

        conn.execute(
            """INSERT OR IGNORE INTO reconciliation_matches
               (bank_deposit_id, acct_transaction_id, match_type, match_confidence)
               VALUES (?, ?, 'manual', 1.0)""",
            (deposit_id, txn_id),
        )
        conn.execute(
            "UPDATE bank_deposits SET status = 'matched' WHERE id = ?", (deposit_id,)
        )
        conn.commit()

    return {"created": True, "acct_transaction_id": txn_id, "deposit_id": deposit_id,
            "from_account": from_account, "to_account": to_account}


def dismiss_bank_deposit(deposit_id: int, reason: str = "not_applicable",
                         db_path: str | Path | None = None) -> dict:
    """Mark a bank deposit as dismissed (not applicable — no ledger entry needed)."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE bank_deposits SET dismissed = 1, dismiss_reason = ? WHERE id = ?",
            (reason, deposit_id),
        )
        conn.commit()
    return {"dismissed": True, "id": deposit_id, "reason": reason}


def get_bank_deposits(account_id: int | None = None, status: str | None = None,
                      month: str | None = None, include_dismissed: bool = False,
                      db_path: str | Path | None = None) -> list[dict]:
    """Return bank deposits with match info."""
    with _connect(db_path) as conn:
        clauses, params = [], []
        if account_id:
            clauses.append("d.account_id = ?"); params.append(account_id)
        if status:
            clauses.append("d.status = ?"); params.append(status)
        if month:
            clauses.append("d.deposit_date LIKE ?"); params.append(f"{month}%")
        if not include_dismissed:
            clauses.append("COALESCE(d.dismissed, 0) = 0")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        rows = conn.execute(
            f"""SELECT d.*, ba.name as account_name, ba.account_type,
                       GROUP_CONCAT(rm.acct_transaction_id) as matched_txn_ids,
                       GROUP_CONCAT(rm.match_confidence) as match_confidences
                FROM bank_deposits d
                LEFT JOIN acct_accounts ba ON ba.id = d.account_id
                LEFT JOIN reconciliation_matches rm ON rm.bank_deposit_id = d.id
                {where}
                GROUP BY d.id
                ORDER BY d.deposit_date DESC""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def get_unreconciled_transactions(account: str | None = None, month: str | None = None,
                                  date_from: str | None = None, date_to: str | None = None,
                                  source: str | None = None,
                                  db_path: str | Path | None = None) -> list[dict]:
    """Return acct_transactions not yet matched to any bank deposit.
    Shows all entry types (income, expense, contra) — not just income.
    Does NOT filter by account name since acct_transactions.account
    doesn't match acct_accounts.name consistently.

    Optional filters: date_from/date_to (YYYY-MM-DD), source (godaddy/venmo/etc).
    """
    with _connect(db_path) as conn:
        clauses = [
            "t.entry_type IS NOT NULL",
            "COALESCE(t.status, 'active') NOT IN ('reversed', 'merged')",
            "t.id NOT IN (SELECT acct_transaction_id FROM reconciliation_matches)",
        ]
        params = []
        if month:
            clauses.append("t.date LIKE ?"); params.append(f"{month}%")
        if date_from:
            clauses.append("t.date >= ?"); params.append(date_from)
        if date_to:
            clauses.append("t.date <= ?"); params.append(date_to)
        if source:
            clauses.append("t.source = ?"); params.append(source)
        where = " AND ".join(clauses)
        rows = conn.execute(
            f"""SELECT t.* FROM acct_transactions t
                WHERE {where}
                ORDER BY t.date DESC
                LIMIT 500""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def merge_transactions(acct_transaction_ids: list[int],
                       db_path: str | Path | None = None) -> dict:
    """Merge multiple GoDaddy order transactions into a single batch entry.

    Creates a new 'godaddy_batch' transaction with the combined net_deposit
    and merchant_fee, then marks the original entries as 'merged'.
    The batch entry can then be matched to a single bank deposit.

    Returns the new batch transaction id.
    """
    if len(acct_transaction_ids) < 2:
        return {"error": "Need at least 2 transactions to merge"}

    with _connect(db_path) as conn:
        placeholders = ",".join(["?"] * len(acct_transaction_ids))
        txns = conn.execute(
            f"""SELECT * FROM acct_transactions
                WHERE id IN ({placeholders})
                AND COALESCE(status, 'active') = 'active'
                AND entry_type IS NOT NULL""",
            acct_transaction_ids,
        ).fetchall()

        if len(txns) < 2:
            return {"error": "Less than 2 active transactions found"}

        txns = [dict(t) for t in txns]

        total_amount = sum(t.get("amount", 0) or 0 for t in txns)
        total_merchant = sum(t.get("merchant_fee", 0) or 0 for t in txns)
        total_net = sum((t.get("net_deposit") or t.get("amount", 0) or 0) for t in txns)

        # Use the earliest date as batch date
        dates = sorted(t.get("date", "") for t in txns if t.get("date"))
        batch_date = dates[0] if dates else ""

        order_ids = [t.get("order_id", "") for t in txns if t.get("order_id")]
        batch_ref = f"godaddy-batch-{'-'.join(str(i) for i in sorted(acct_transaction_ids))}"

        # Check if batch already exists
        existing = conn.execute(
            "SELECT id FROM acct_transactions WHERE source_ref = ? AND COALESCE(status, 'active') = 'active'",
            (batch_ref,),
        ).fetchone()
        if existing:
            return {"error": "These transactions are already merged", "batch_id": existing[0]}

        description = f"GoDaddy batch: {len(txns)} orders ({batch_date})"
        batch_id = _write_acct_entry(
            conn,
            item_id=None,
            event_name="",
            customer="",
            order_id=",".join(order_ids[:5]),
            entry_type="income",
            category="godaddy_batch",
            source="godaddy",
            amount=total_amount,
            description=description,
            account="TGF Checking",
            source_ref=batch_ref,
            date=batch_date,
            net_deposit=total_net,
            merchant_fee=total_merchant,
        )

        if batch_id is None:
            return {"error": "Failed to create batch entry"}

        # Mark original entries as merged (preserves data but removes from active matching)
        for tid in acct_transaction_ids:
            conn.execute(
                "UPDATE acct_transactions SET reconciled_batch_id = ?, status = 'merged' WHERE id = ?",
                (batch_id, tid),
            )

        conn.commit()

    return {"status": "ok", "batch_id": batch_id, "merged_count": len(txns),
            "net_deposit": round(total_net, 2), "merchant_fee": round(total_merchant, 2)}


def get_match_suggestions(bank_deposit_id: int,
                          db_path: str | Path | None = None) -> list[dict]:
    """Return ranked match candidates for a specific bank deposit.

    Scores candidates by: amount proximity, date proximity, description match.
    Returns up to 20 suggestions sorted by score descending.
    """
    with _connect(db_path) as conn:
        dep = conn.execute("SELECT * FROM bank_deposits WHERE id = ?",
                           (bank_deposit_id,)).fetchone()
        if not dep:
            return []
        dep = dict(dep)
        dep_amt = dep["amount"]
        dep_date = dep["deposit_date"]
        dep_desc = (dep["description"] or "").upper()

        # Wider window for GoDaddy deposits (batches span multiple days)
        is_godaddy = "GODADDY" in dep_desc
        day_window = 14 if is_godaddy else 7

        # Match direction: negative bank amount = expense outflow, positive = income inflow
        is_expense_deposit = dep_amt < 0
        if is_expense_deposit:
            type_filter = "AND t.entry_type IN ('expense', 'contra')"
        else:
            type_filter = "AND t.entry_type IN ('income')"

        # Get all unmatched acct_transactions within date window, filtered by direction
        candidates = conn.execute(
            f"""SELECT t.* FROM acct_transactions t
               WHERE t.entry_type IS NOT NULL
               {type_filter}
               AND COALESCE(t.status, 'active') NOT IN ('reversed', 'merged')
               AND t.id NOT IN (SELECT acct_transaction_id FROM reconciliation_matches)
               AND ABS(julianday(t.date) - julianday(?)) <= ?
               ORDER BY t.date DESC""",
            (dep_date, day_window),
        ).fetchall()

        results = []
        for c in candidates:
            c = dict(c)
            # Use net_deposit for GoDaddy orders; fall back to amount then total_amount
            c_amt = c.get("net_deposit") or c.get("amount") or c.get("total_amount", 0) or 0
            c_date = c.get("date", "")
            c_customer = (c.get("customer") or "").upper()
            c_event = (c.get("event_name") or "").upper()
            c_desc = (c.get("description") or "").upper()

            # For expense ledger entries (positive) matched to negative bank deposits,
            # compare absolute values so a $21.34 expense matches a -$21.37 debit.
            compare_dep_amt = abs(dep_amt) if is_expense_deposit else dep_amt

            # Score: amount proximity (0-50 points)
            amt_diff = abs(compare_dep_amt - c_amt)
            if amt_diff < 0.01:
                amt_score = 50
            elif amt_diff < 1.00:
                amt_score = 40
            elif amt_diff < 5.00:
                amt_score = 25
            elif amt_diff < 20.00:
                amt_score = 10
            else:
                amt_score = max(0, 5 - int(amt_diff / 100))

            # Score: date proximity (0-30 points)
            # GoDaddy batches span multiple days, so penalize less per day
            try:
                from datetime import datetime as _dt
                d1 = _dt.strptime(dep_date, "%Y-%m-%d")
                d2 = _dt.strptime(c_date, "%Y-%m-%d")
                day_diff = abs((d1 - d2).days)
            except (ValueError, TypeError):
                day_diff = 99
            day_penalty = 3 if is_godaddy else 5
            date_score = max(0, 30 - day_diff * day_penalty)

            # Score: description match (0-20 points)
            desc_score = 0
            if c_customer and c_customer in dep_desc:
                desc_score += 15
            elif c_desc and (c_desc in dep_desc or dep_desc in c_desc):
                desc_score += 12
            if c_event and c_event in dep_desc:
                desc_score += 5
            if "GODADDY" in dep_desc and c.get("source") == "godaddy":
                desc_score += 10

            total_score = amt_score + date_score + desc_score
            if total_score < 5:
                continue

            reason_parts = []
            if amt_diff < 0.01:
                reason_parts.append("exact amount")
            elif amt_diff < 5:
                reason_parts.append(f"amount ±${amt_diff:.2f}")
            if day_diff == 0:
                reason_parts.append("same day")
            elif day_diff <= 2:
                reason_parts.append(f"{day_diff}d apart")
            if c_customer and c_customer in dep_desc:
                reason_parts.append("name match")
            if "GODADDY" in dep_desc and c.get("source") == "godaddy":
                reason_parts.append("GoDaddy")

            c["_score"] = total_score
            c["_reason"] = ", ".join(reason_parts) if reason_parts else "date range"
            c["_amt_diff"] = round(amt_diff, 2)
            results.append(c)

        results.sort(key=lambda x: x["_score"], reverse=True)
        max_results = 50 if is_godaddy else 20
        return results[:max_results]


def get_reconciliation_dashboard(db_path: str | Path | None = None) -> dict:
    """Summary data for the reconciliation dashboard cards."""
    with _connect(db_path) as conn:
        accounts = conn.execute(
            "SELECT * FROM acct_accounts WHERE is_active = 1 ORDER BY name"
        ).fetchall()
        result = []
        for acct in accounts:
            acct = dict(acct)
            aid = acct["id"]

            last_import = conn.execute(
                "SELECT MAX(created_at) as last_import FROM bank_deposits WHERE account_id = ?",
                (aid,),
            ).fetchone()

            book_balance = conn.execute(
                """SELECT COALESCE(SUM(t.amount), 0) as total
                   FROM acct_transactions t
                   JOIN reconciliation_matches rm ON rm.acct_transaction_id = t.id
                   JOIN bank_deposits d ON d.id = rm.bank_deposit_id AND d.account_id = ?""",
                (aid,),
            ).fetchone()["total"]

            bank_balance = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM bank_deposits WHERE account_id = ? AND status = 'matched'",
                (aid,),
            ).fetchone()["total"]

            unmatched_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM bank_deposits WHERE account_id = ? AND status = 'unmatched' AND COALESCE(dismissed, 0) = 0",
                (aid,),
            ).fetchone()["cnt"]

            partial_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM bank_deposits WHERE account_id = ? AND status = 'partial'",
                (aid,),
            ).fetchone()["cnt"]

            acct["last_import"] = last_import["last_import"] if last_import else None
            acct["book_balance"] = round(book_balance, 2)
            acct["bank_balance"] = round(bank_balance, 2)
            acct["variance"] = round(bank_balance - book_balance, 2)
            acct["unmatched_count"] = unmatched_count
            acct["partial_count"] = partial_count
            result.append(acct)

        return {"accounts": result}


def get_monthly_reconciliation(month: str, db_path: str | Path | None = None) -> dict:
    """Monthly summary for the reconciliation reports tab."""
    with _connect(db_path) as conn:
        # Income by category from acct_transactions
        # Use net_deposit for GoDaddy order entries (actual cash arriving)
        income_rows = conn.execute(
            """SELECT category, COALESCE(SUM(COALESCE(net_deposit, amount)), 0) as total, COUNT(*) as cnt
               FROM acct_transactions
               WHERE entry_type = 'income' AND date LIKE ?
               AND COALESCE(status, 'active') NOT IN ('reversed', 'merged')
               AND entry_type IS NOT NULL
               GROUP BY category""",
            (f"{month}%",),
        ).fetchall()

        # Expenses by category
        expense_rows = conn.execute(
            """SELECT category, COALESCE(SUM(amount), 0) as total, COUNT(*) as cnt
               FROM acct_transactions
               WHERE entry_type IN ('expense', 'contra') AND date LIKE ?
               AND COALESCE(status, 'active') NOT IN ('reversed', 'merged')
               AND entry_type IS NOT NULL
               GROUP BY category""",
            (f"{month}%",),
        ).fetchall()

        # Reconciliation stats
        total_txns = conn.execute(
            "SELECT COUNT(*) as cnt FROM acct_transactions WHERE date LIKE ? AND entry_type IS NOT NULL AND COALESCE(status, 'active') NOT IN ('reversed', 'merged')",
            (f"{month}%",),
        ).fetchone()["cnt"]

        reconciled_txns = conn.execute(
            """SELECT COUNT(DISTINCT rm.acct_transaction_id) as cnt
               FROM reconciliation_matches rm
               JOIN acct_transactions t ON t.id = rm.acct_transaction_id
               WHERE t.date LIKE ?""",
            (f"{month}%",),
        ).fetchone()["cnt"]

        return {
            "month": month,
            "income": [dict(r) for r in income_rows],
            "expenses": [dict(r) for r in expense_rows],
            "total_transactions": total_txns,
            "reconciled_transactions": reconciled_txns,
            "reconciliation_pct": round(reconciled_txns / total_txns * 100, 1) if total_txns else 0,
        }


def get_event_reconciliation_status(event_name: str,
                                    db_path: str | Path | None = None) -> dict:
    """Reconciliation status for a specific event (for Financial tab indicator)."""
    with _connect(db_path) as conn:
        alias_names = [
            r[0] for r in conn.execute(
                "SELECT alias_name FROM event_aliases WHERE canonical_event_name = ? COLLATE NOCASE",
                (event_name,),
            ).fetchall()
        ]
        all_names = [event_name] + alias_names
        placeholders = ",".join(["?"] * len(all_names))

        total = conn.execute(
            f"""SELECT COUNT(*) as cnt FROM acct_transactions
                WHERE event_name COLLATE NOCASE IN ({placeholders})
                AND entry_type = 'income'
                AND COALESCE(status, 'active') NOT IN ('reversed', 'merged')
                AND entry_type IS NOT NULL""",
            all_names,
        ).fetchone()["cnt"]

        reconciled = conn.execute(
            f"""SELECT COUNT(DISTINCT rm.acct_transaction_id) as cnt
                FROM reconciliation_matches rm
                JOIN acct_transactions t ON t.id = rm.acct_transaction_id
                WHERE t.event_name COLLATE NOCASE IN ({placeholders})
                AND t.entry_type = 'income'""",
            all_names,
        ).fetchone()["cnt"]

        matched_amt = conn.execute(
            f"""SELECT COALESCE(SUM(COALESCE(t.net_deposit, t.amount)), 0) as total
                FROM reconciliation_matches rm
                JOIN acct_transactions t ON t.id = rm.acct_transaction_id
                WHERE t.event_name COLLATE NOCASE IN ({placeholders})
                AND t.entry_type = 'income'""",
            all_names,
        ).fetchone()["total"]

        return {
            "total_transactions": total,
            "reconciled_transactions": reconciled,
            "matched_amount": round(matched_amt, 2),
        }


def get_cashflow_data(weeks: int = 13, db_path: str | Path | None = None) -> list[dict]:
    """Return weekly cash flow data for the rolling view (default 13 weeks = ~90 days)."""
    from datetime import date as _date

    today = _date.today()
    # Start from the beginning of the current week (Monday)
    start = today - timedelta(days=today.weekday())
    # Go back 'weeks' weeks
    start = start - timedelta(weeks=weeks - 1)

    result = []

    with _connect(db_path) as conn:
        running_balance = 0.0

        for w in range(weeks):
            week_start = start + timedelta(weeks=w)
            week_end = week_start + timedelta(days=6)
            ws = week_start.strftime("%Y-%m-%d")
            we = week_end.strftime("%Y-%m-%d")

            # Expected income (use net_deposit for GoDaddy orders = actual cash arriving)
            expected = conn.execute(
                """SELECT COALESCE(SUM(COALESCE(net_deposit, amount)), 0) as total FROM acct_transactions
                   WHERE entry_type = 'income' AND date BETWEEN ? AND ?
                   AND COALESCE(status, 'active') NOT IN ('reversed', 'merged')
                   AND entry_type IS NOT NULL""",
                (ws, we),
            ).fetchone()["total"]

            # Confirmed income (reconciled to bank)
            confirmed = conn.execute(
                """SELECT COALESCE(SUM(COALESCE(t.net_deposit, t.amount)), 0) as total
                   FROM acct_transactions t
                   JOIN reconciliation_matches rm ON rm.acct_transaction_id = t.id
                   WHERE t.entry_type = 'income' AND t.date BETWEEN ? AND ?""",
                (ws, we),
            ).fetchone()["total"]

            # Projected expenses (processing fees + refunds + contra)
            proj_expenses = conn.execute(
                """SELECT COALESCE(SUM(amount), 0) as total FROM acct_transactions
                   WHERE entry_type IN ('expense', 'contra') AND date BETWEEN ? AND ?
                   AND COALESCE(status, 'active') NOT IN ('reversed', 'merged')
                   AND entry_type IS NOT NULL""",
                (ws, we),
            ).fetchone()["total"]

            # Actual expenses (reconciled outflows)
            actual_expenses = conn.execute(
                """SELECT COALESCE(SUM(t.amount), 0) as total
                   FROM acct_transactions t
                   JOIN reconciliation_matches rm ON rm.acct_transaction_id = t.id
                   WHERE t.entry_type IN ('expense', 'contra') AND t.date BETWEEN ? AND ?""",
                (ws, we),
            ).fetchone()["total"]

            net = round(expected - proj_expenses, 2)
            running_balance += net

            result.append({
                "week_ending": we,
                "expected_income": round(expected, 2),
                "confirmed_income": round(confirmed, 2),
                "projected_expenses": round(proj_expenses, 2),
                "actual_expenses": round(actual_expenses, 2),
                "net": net,
                "running_balance": round(running_balance, 2),
                "warning": proj_expenses > confirmed and confirmed > 0,
            })

    return result


# ═══════════════════════════════════════════════════════════════════════════
# COO Agent Registry & Action Log
# ═══════════════════════════════════════════════════════════════════════════

def _seed_coo_agents(conn: sqlite3.Connection) -> None:
    """Populate the six specialist COO agents."""
    agents = [
        ("Chief of Staff",
         "Liaison with Kerry. Synthesizes input from all specialist agents.",
         """You are the TGF Chief of Staff — Kerry's AI COO. You have live access to the full
TGF Transaction Tracker: registrations, revenue, event pricing (course costs, markups,
side game fees), player counts (with 9-hole vs 18-hole breakdown), TGF payouts and prize
pools, cost allocations, handicaps, RSVP data, and customer records.

Present data from your FULL BUSINESS INTELLIGENCE briefing confidently — it is pulled
from the live database. State numbers directly ("39 players, $3,382 revenue") rather than
hedging with "I think" or "I'm seeing." You are the authority on what the system shows.

However, you are also a vigilant analyst. If numbers don't add up — for example, revenue
per player doesn't match the pricing structure, or player counts seem off relative to
payout winners — flag the discrepancy clearly. Say what the data shows AND what looks
wrong. Example: "Revenue is $3,382 for 39 players, but at $57/player entry that should
be ~$2,223. There may be a mix of 9-hole and 18-hole pricing, or extra payments."
Your job is to be both confident AND honest when something smells off.

When answering profitability questions, use this formula:
  Net Profit = Revenue - Course Cost - Prize Pool (TGF Payouts)
  Course Cost = (9-hole players × 9h rate) + (18-hole players × 18h rate)

Only say "data not available" when the field is genuinely missing or marked "not
configured" in your briefing. Do not speculate about data you don't have.

Synthesize input from all specialist agents (Financial, Operations, Course Correspondent,
Member Relations, Compliance) into clear, actionable briefings. You prioritize action
items, generate daily briefings, and respond to COO Chat. When a question falls outside
your direct knowledge, you delegate to the appropriate specialist and synthesize their
analysis.

Always speak in one consistent voice — direct, warm, and authoritative. Kerry is the
founder and operator. He values straight talk, concrete numbers, and honest flags when
something doesn't add up."""),

        ("Financial Agent",
         "Owns all money tracking: allocations, expenses, reconciliation, tax reserve.",
         """You are the TGF Financial Agent. You own all money tracking:
- acct_allocations: per-order dollar breakdown (course payable, prize pool, TGF operating, GoDaddy fees, tax reserve)
- expense_transactions: Chase alerts, Venmo payments, receipts
- Bank reconciliation: matching bank statements to Tracker records
- Tax reserve: 8.25% of TGF operating revenue, tracked monthly
- Prize pool obligations: funds held for future payouts
- Course payables: fees owed to golf courses
Answer "where is the money" questions with specific numbers. Flag when available cash is low."""),

        ("Operations Agent",
         "Owns events, registrations, rosters, breakeven calculations.",
         """You are the TGF Operations Agent. You own:
- Events: scheduling, course bookings, registration counts, breakeven calculations
- Rosters: player registrations, RSVP status, no-shows
- Venue logistics: start times, tee time intervals, shotgun vs lottery
- Registration tracking: who's registered, who's RSVP-only, who hasn't paid
Calculate breakeven as: course_cost × minimum_players. Flag events below breakeven
with registration count warnings. Monitor upcoming events for operational readiness."""),

        ("Course Correspondent Agent",
         "Tracks relationships with each course coordinator.",
         """You are the TGF Course Correspondent Agent. You track relationships with each golf course:
- Unsigned contracts: flag courses without current agreements
- Event confirmations: ensure upcoming events are confirmed with the course
- Payment due dates: track when course fees are due (usually day-of or net-30)
- Pairings submission: most courses need pairings 2-4 days before the event
- Course coordinator contacts: maintain relationship context
Flag anything requiring Kerry's direct response to a course contact."""),

        ("Member Relations Agent",
         "Tracks member communications, winnings, credits, follow-ups.",
         """You are the TGF Member Relations Agent. You track:
- Member communications: inquiries, complaints, requests
- Winnings history: who won what at which event (via Venmo payouts)
- Credits and refunds: which members have outstanding credits
- Follow-ups needed: members who need a response or check-in
- RSVP patterns: members who frequently no-show or cancel late
- Membership renewals: tracking returning vs new vs expired members
Prioritize member satisfaction and retention."""),

        ("Compliance Agent",
         "Owns sales tax, IRS installment tracking, filing deadlines.",
         """You are the TGF Compliance Agent. You own:
- Sales tax: Texas 8.25% on TGF operating revenue, filed monthly by the 20th
- IRS installment agreement: tracking payment schedule and balance
- 1099 threshold monitoring: flag any vendor/contractor paid $600+ in a year
- Monthly filing deadlines: sales tax due by 20th, IRS installment timing
- State compliance: Texas franchise tax, any other state obligations
Alert proactively when deadlines are approaching. Generate tax reserve calculations."""),
    ]
    for name, role, prompt in agents:
        conn.execute(
            "INSERT INTO coo_agents (agent_name, agent_role, system_prompt) VALUES (?, ?, ?)",
            (name, role, prompt),
        )


def get_coo_agents(db_path: str | Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM coo_agents WHERE is_active = 1 ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def get_coo_agent(agent_name: str, db_path: str | Path | None = None) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM coo_agents WHERE agent_name = ?", (agent_name,)
        ).fetchone()
    return dict(row) if row else None


def log_agent_action(agent_name: str, action_type: str, description: str,
                     source_email_uid: str | None = None,
                     related_item_id: int | None = None,
                     outcome: str | None = None,
                     db_path: str | Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO agent_action_log
               (agent_name, action_type, description, source_email_uid, related_item_id, outcome)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (agent_name, action_type, description, source_email_uid, related_item_id, outcome),
        )
        conn.commit()


def get_agent_action_log(agent_name: str | None = None, date_from: str | None = None,
                         date_to: str | None = None, limit: int = 50,
                         db_path: str | Path | None = None) -> list[dict]:
    clauses, params = [], []
    if agent_name:
        clauses.append("agent_name = ?"); params.append(agent_name)
    if date_from:
        clauses.append("created_at >= ?"); params.append(date_from)
    if date_to:
        clauses.append("created_at <= ?"); params.append(date_to + "T23:59:59")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM agent_action_log{where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    return [dict(r) for r in rows]


def route_to_agent(message: str) -> str:
    """Route a user message to the appropriate specialist agent by keyword matching."""
    msg_lower = message.lower()

    financial_kw = ["money", "allocation", "expense", "balance", "tax", "reconcil",
                    "revenue", "income", "godaddy fee", "prize pool", "course payable",
                    "available to spend", "checking", "cash"]
    operations_kw = ["event", "roster", "registration", "breakeven", "venue",
                     "course cost", "tee time", "start time", "format"]
    correspondent_kw = ["contract", "course coordinator", "pairings", "payment due",
                        "confirmation", "pro shop", "course contact"]
    member_kw = ["member", "credit", "winnings", "rsvp", "player", "handicap",
                 "renewal", "no-show"]
    compliance_kw = ["sales tax", "irs", "1099", "filing", "compliance",
                     "franchise tax", "installment"]

    for kw in compliance_kw:
        if kw in msg_lower:
            return "Compliance Agent"
    for kw in correspondent_kw:
        if kw in msg_lower:
            return "Course Correspondent Agent"
    for kw in financial_kw:
        if kw in msg_lower:
            return "Financial Agent"
    for kw in operations_kw:
        if kw in msg_lower:
            return "Operations Agent"
    for kw in member_kw:
        if kw in msg_lower:
            return "Member Relations Agent"

    return "Chief of Staff"


def run_compliance_checks(db_path: str | Path | None = None) -> list[dict]:
    """Run daily compliance checks. Returns list of action items created."""
    today = datetime.now()
    day = today.day
    month_str = today.strftime("%Y-%m")
    created = []
    pending_logs = []  # collect log entries to write after conn closes

    with _connect(db_path) as conn:
        # 1. Sales tax reminder: between 15th-20th of month
        if 15 <= day <= 20:
            due_date = today.strftime("%Y-%m-20")
            existing = conn.execute(
                "SELECT id FROM action_items WHERE subject LIKE ? AND status = 'open'",
                (f"%sales tax due%{month_str}%",),
            ).fetchone()
            if not existing:
                conn.execute(
                    """INSERT INTO action_items
                       (subject, from_name, from_email, summary, urgency, category, email_date, confidence)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (f"Monthly sales tax due {due_date}",
                     "Compliance Agent", "system@tgf",
                     f"Texas sales tax filing is due by {due_date}. Calculate TGF operating revenue for {month_str} and file.",
                     "high", "payment", today.strftime("%Y-%m-%d"), 99),
                )
                created.append({"type": "sales_tax", "due": due_date})
                pending_logs.append(("Compliance Agent", "compliance_check",
                                     f"Created sales tax reminder for {due_date}"))

        # 2. IRS installment check
        irs_due = get_coo_manual_value(f"irs_due_{month_str}", db_path)
        if irs_due and irs_due > 0:
            existing = conn.execute(
                "SELECT id FROM action_items WHERE subject LIKE ? AND status = 'open'",
                (f"%IRS installment%{month_str}%",),
            ).fetchone()
            if not existing:
                conn.execute(
                    """INSERT INTO action_items
                       (subject, from_name, from_email, summary, urgency, category, email_date, confidence)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (f"IRS installment due {month_str}",
                     "Compliance Agent", "system@tgf",
                     f"IRS installment payment of ${irs_due:,.2f} is due this month.",
                     "high", "payment", today.strftime("%Y-%m-%d"), 99),
                )
                created.append({"type": "irs_installment", "amount": irs_due})

        # 3. Upcoming event pairings (events within 4 days)
        cutoff = (today + timedelta(days=4)).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")
        upcoming = conn.execute(
            "SELECT id, item_name, event_date, course FROM events WHERE event_date BETWEEN ? AND ?",
            (today_str, cutoff),
        ).fetchall()

        for ev in upcoming:
            submit_by = (datetime.strptime(ev["event_date"], "%Y-%m-%d") - timedelta(days=2)).strftime("%Y-%m-%d")
            # Dedup: check by event name OR by course+date to catch near-duplicates
            existing = conn.execute(
                """SELECT id FROM action_items WHERE status = 'open'
                   AND category = 'course_correspondence'
                   AND (subject LIKE ? OR summary LIKE ?)""",
                (f"%pairings%{ev['item_name']}%",
                 f"%{ev['course']}%{ev['event_date']}%"),
            ).fetchone()
            if not existing:
                conn.execute(
                    """INSERT INTO action_items
                       (subject, from_name, from_email, summary, urgency, category, email_date, confidence)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (f"Submit pairings to {ev['course']} for {ev['item_name']}",
                     "Course Correspondent Agent", "system@tgf",
                     f"Submit pairings to {ev['course']} for {ev['item_name']} by {submit_by}. Event date: {ev['event_date']}.",
                     "high", "course_correspondence", today.strftime("%Y-%m-%d"), 99),
                )
                created.append({"type": "pairings", "event": ev["item_name"], "submit_by": submit_by})
                pending_logs.append(("Course Correspondent Agent", "compliance_check",
                                     f"Created pairings reminder for {ev['item_name']}"))

        conn.commit()

    # Write logs after connection is released
    for agent, action, desc in pending_logs:
        log_agent_action(agent, action, desc, outcome="action_item_created", db_path=db_path)

    return created


# ---------------------------------------------------------------------------
# TGF Payouts
# ---------------------------------------------------------------------------

def _resolve_customer_for_payout(conn: sqlite3.Connection, name: str) -> int:
    """Return customer_id for a payout entry, creating a customer if needed.

    Handles both "First Last" and "LAST, First" formats (the latter is common
    in tournament leaderboard screenshots).

    Uses the same resolution cascade as email parsing (_lookup_customer_id):
    exact name, alias, etc.  If the raw name doesn't match, tries the reversed
    "LAST, First" → "First Last" interpretation.  If no customer matches,
    creates one from the normalized name with acquisition_source='tgf_payout'.

    Raises ValueError if the name is empty or cannot be parsed into first+last.
    """
    if not name or not name.strip():
        raise ValueError("Cannot resolve payout customer: name is empty")

    clean_name = name.strip()

    # Detect and normalize "LAST, First" format
    if "," in clean_name:
        parts = [p.strip() for p in clean_name.split(",", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            # "CAMPOS, Roland" → first="Roland", last="Campos"
            normalized_first = parts[1].title()
            normalized_last = parts[0].title()
            normalized_name = f"{normalized_first} {normalized_last}"

            # Try normalized name first (most likely to match existing customer)
            cid = _lookup_customer_id(conn, normalized_name, None)
            if cid is not None:
                return cid

            # Also try the raw format in case it was stored that way
            cid = _lookup_customer_id(conn, clean_name, None)
            if cid is not None:
                return cid

            # Create customer using the properly-ordered name
            cur = conn.execute(
                """INSERT INTO customers
                       (first_name, last_name, account_status, acquisition_source)
                   VALUES (?, ?, 'active', 'tgf_payout')""",
                (normalized_first, normalized_last),
            )
            new_cid = cur.lastrowid
            logger.info("Created customer %d for payout entry '%s' (normalized: %s)",
                        new_cid, clean_name, normalized_name)
            return new_cid

    # Standard "First Last" format
    cid = _lookup_customer_id(conn, clean_name, None)
    if cid is not None:
        return cid

    parts = clean_name.split()
    if len(parts) >= 2:
        first = parts[0]
        last = " ".join(parts[1:])
    else:
        first = clean_name
        last = "(Unknown)"
    cur = conn.execute(
        """INSERT INTO customers
               (first_name, last_name, account_status, acquisition_source)
           VALUES (?, ?, 'active', 'tgf_payout')""",
        (first, last),
    )
    new_cid = cur.lastrowid
    logger.info("Created customer %d for payout entry '%s'", new_cid, clean_name)
    return new_cid


def get_tgf_data(db_path=None):
    """Return all customers with payouts and events with payouts.

    Returns {customers: [...], events: [...], winnings: {customer_id: {...}}}.
    """
    with _connect(db_path) as conn:
        # Customers who have received payouts
        customers = [dict(r) for r in conn.execute(
            """SELECT DISTINCT c.customer_id as id,
                      (c.first_name || ' ' || c.last_name) as name,
                      c.venmo_username, c.chapter
               FROM customers c
               JOIN tgf_payouts p ON p.customer_id = c.customer_id
               ORDER BY c.last_name, c.first_name"""
        ).fetchall()]

        events = []
        for ev in conn.execute("SELECT * FROM tgf_events ORDER BY event_date DESC").fetchall():
            ev_dict = dict(ev)
            payouts = []
            for p in conn.execute(
                """SELECT p.*,
                          (c.first_name || ' ' || c.last_name) as customer_name,
                          t.source as txn_source,
                          COALESCE(t.status, 'active') as txn_status
                   FROM tgf_payouts p
                   JOIN customers c ON c.customer_id = p.customer_id
                   LEFT JOIN acct_transactions t ON t.id = p.acct_transaction_id
                   WHERE p.event_id = ?
                   ORDER BY p.amount DESC""",
                (ev["id"],),
            ).fetchall():
                pd = dict(p)
                # Derive payment status
                if pd.get("acct_transaction_id") is None:
                    pd["payment_status"] = "unwired"  # pre-Step 3 legacy
                elif pd.get("txn_source") == "pending":
                    pd["payment_status"] = "pending"
                elif pd.get("txn_source") == "venmo":
                    pd["payment_status"] = "paid"
                else:
                    pd["payment_status"] = "paid"  # any other ledger link counts as paid
                payouts.append(pd)
            ev_dict["payouts"] = payouts
            events.append(ev_dict)

        # Compute all-time winnings per customer who has received at least one payout
        winnings = {}
        for row in conn.execute(
            """SELECT c.customer_id as id,
                      (c.first_name || ' ' || c.last_name) as name,
                      c.venmo_username,
                      c.chapter,
                      COALESCE(SUM(p.amount), 0) as total_winnings,
                      COUNT(DISTINCT p.event_id) as events_played
               FROM customers c
               JOIN tgf_payouts p ON p.customer_id = c.customer_id
               GROUP BY c.customer_id
               ORDER BY total_winnings DESC"""
        ).fetchall():
            winnings[row["id"]] = dict(row)

        return {"customers": customers, "events": events, "winnings": winnings}


def add_tgf_event(data: dict, db_path=None) -> dict:
    """Add a new TGF event with payouts.

    data: {code, name, event_date, course, chapter, total_purse, winners_count, payouts: [{golferName, category, amount, description}]}
    """
    with _connect(db_path) as conn:
        # Check for duplicate
        existing = conn.execute("SELECT id FROM tgf_events WHERE code = ?", (data["code"],)).fetchone()
        if existing:
            return {"error": f"Event {data['code']} already exists", "event_id": existing["id"]}

        conn.execute(
            """INSERT INTO tgf_events (code, name, event_date, course, chapter, total_purse, winners_count, payouts_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["code"], data["name"], data["event_date"], data.get("course", ""),
             data.get("chapter", ""), data.get("total_purse", 0),
             data.get("winners_count", 0), len(data.get("payouts", []))),
        )
        event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        new_payout_ids: list[int] = []
        for p in data.get("payouts", []):
            customer_id = _resolve_customer_for_payout(conn, p["golferName"])
            cur = conn.execute(
                """INSERT INTO tgf_payouts (event_id, customer_id, category, amount, description)
                   VALUES (?, ?, ?, ?, ?)""",
                (event_id, customer_id, p["category"], p["amount"], p.get("description", "")),
            )
            new_payout_ids.append(cur.lastrowid)

        # Wire new payouts to the ledger + match existing Venmo payments
        matched = 0
        if new_payout_ids:
            placeholders = ",".join("?" * len(new_payout_ids))
            new_rows = conn.execute(
                f"""SELECT p.id, p.event_id, p.customer_id, p.amount, p.category, p.description,
                           e.event_date, e.name as event_name
                    FROM tgf_payouts p
                    JOIN tgf_events e ON e.id = p.event_id
                    WHERE p.id IN ({placeholders})""",
                new_payout_ids,
            ).fetchall()
            matched = _reconcile_payouts_with_venmo(conn, new_rows)

        conn.commit()
        return {
            "event_id": event_id,
            "payouts_added": len(data.get("payouts", [])),
            "matched": matched,
        }


def import_tgf_payouts(event_id: int, payouts: list, db_path=None) -> dict:
    """Add payouts to an existing TGF event.

    payouts: [{golferName, category, amount, description}]
      (golferName field retained for backward-compatible API; resolves to customer_id internally)

    Each new payout gets a corresponding acct_transactions entry
    (category='prize_payout'). If a matching Venmo payment already exists
    (exact amount + same customer + within 7 days of event), the payout is
    linked to it. Otherwise a pending expense entry is created.

    Returns {payouts_added, matched, pending, event_id} or {error}.
    """
    if not payouts:
        return {"error": "No payouts provided"}
    with _connect(db_path) as conn:
        ev = conn.execute("SELECT id, name, event_date FROM tgf_events WHERE id = ?", (event_id,)).fetchone()
        if not ev:
            return {"error": f"Event {event_id} not found"}

        added = 0
        new_payout_ids: list[int] = []
        for p in payouts:
            customer_id = _resolve_customer_for_payout(conn, p["golferName"])
            cur = conn.execute(
                """INSERT INTO tgf_payouts (event_id, customer_id, category, amount, description)
                   VALUES (?, ?, ?, ?, ?)""",
                (event_id, customer_id, p["category"], p["amount"], p.get("description", "")),
            )
            new_payout_ids.append(cur.lastrowid)
            added += 1

        # Reconcile new payouts with existing Venmo prize_payouts + create pending entries
        matched = 0
        if new_payout_ids:
            placeholders = ",".join("?" * len(new_payout_ids))
            new_rows = conn.execute(
                f"""SELECT p.id, p.event_id, p.customer_id, p.amount, p.category, p.description,
                           e.event_date, e.name as event_name
                    FROM tgf_payouts p
                    JOIN tgf_events e ON e.id = p.event_id
                    WHERE p.id IN ({placeholders})""",
                new_payout_ids,
            ).fetchall()
            matched = _reconcile_payouts_with_venmo(conn, new_rows)

        # Update event aggregates
        stats = conn.execute(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total,
                      COUNT(DISTINCT customer_id) as winners
               FROM tgf_payouts WHERE event_id = ?""",
            (event_id,),
        ).fetchone()
        conn.execute(
            "UPDATE tgf_events SET total_purse = ?, winners_count = ?, payouts_count = ? WHERE id = ?",
            (stats["total"], stats["winners"], stats["cnt"], event_id),
        )
        conn.commit()
        return {
            "event_id": event_id,
            "payouts_added": added,
            "matched": matched,
            "pending": added - matched,
            "total_purse": stats["total"],
        }


def update_tgf_event(event_id: int, data: dict, db_path=None) -> dict:
    """Update event metadata (not payouts)."""
    with _connect(db_path) as conn:
        fields = []
        values = []
        for key in ("name", "event_date", "course", "chapter", "total_purse", "winners_count"):
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if not fields:
            return {"error": "No fields to update"}
        values.append(event_id)
        conn.execute(f"UPDATE tgf_events SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
        return {"updated": True}


def delete_tgf_event(event_id: int, db_path=None) -> dict:
    """Delete event and its payouts."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM tgf_payouts WHERE event_id = ?", (event_id,))
        conn.execute("DELETE FROM tgf_events WHERE id = ?", (event_id,))
        conn.commit()
        return {"deleted": True}


def add_tgf_golfer(data: dict, db_path=None) -> dict:
    """Add or update a customer's golfer-related info (venmo_username, chapter).

    Backward-compatible name — the API still accepts {name, venmo_username?, chapter?}
    but now operates on the customers table instead of a separate tgf_golfers table.
    """
    with _connect(db_path) as conn:
        customer_id = _resolve_customer_for_payout(conn, data["name"])
        updates = []
        vals = []
        if "venmo_username" in data:
            updates.append("venmo_username = ?")
            vals.append(data["venmo_username"] or None)
        if "chapter" in data:
            updates.append("chapter = ?")
            vals.append(data["chapter"] or None)
        if updates:
            vals.append(customer_id)
            conn.execute(
                f"UPDATE customers SET {', '.join(updates)} WHERE customer_id = ?",
                vals,
            )
        conn.commit()
        return {"customer_id": customer_id, "updated": True}


def import_tgf_golfers(golfers: list[dict], db_path=None) -> dict:
    """Bulk import/update golfer-related fields on customers.

    Each dict: {name, venmo_username?, chapter?}. Resolves each name to a
    customer record (creating one if necessary) and updates its venmo/chapter.
    """
    added = 0
    updated = 0
    with _connect(db_path) as conn:
        for g in golfers:
            name = g.get("name", "").strip()
            if not name:
                continue
            existing_cid = _lookup_customer_id(conn, name, None)
            customer_id = _resolve_customer_for_payout(conn, name)
            if existing_cid is None:
                added += 1  # New customer was created
            else:
                updates = []
                vals = []
                for key in ("venmo_username", "chapter"):
                    if g.get(key):
                        updates.append(f"{key} = ?")
                        vals.append(g[key])
                if updates:
                    vals.append(customer_id)
                    conn.execute(
                        f"UPDATE customers SET {', '.join(updates)} WHERE customer_id = ?",
                        vals,
                    )
                    updated += 1
        conn.commit()
    return {"added": added, "updated": updated}


def get_customer_winnings(customer_name: str, db_path=None) -> dict:
    """Look up payout/winnings history for a customer by customer_id.

    Resolves the provided name to a customer via the standard lookup cascade,
    then queries tgf_payouts by customer_id directly.

    Returns {golfer_name, total_winnings, payouts: [{event_name, event_date, category, amount, description}]}.
    The field name 'golfer_name' is retained for backward-compatible API response shape.
    """
    with _connect(db_path) as conn:
        customer_id = _lookup_customer_id(conn, customer_name, None)
        if customer_id is None:
            return {"golfer_name": None, "total_winnings": 0, "payouts": []}

        cust = conn.execute(
            "SELECT first_name, last_name FROM customers WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()
        display_name = f"{cust['first_name']} {cust['last_name']}" if cust else customer_name

        payouts = [dict(r) for r in conn.execute(
            """SELECT p.amount, p.category, p.description,
                      e.name as event_name, e.event_date, e.course
               FROM tgf_payouts p
               JOIN tgf_events e ON e.id = p.event_id
               WHERE p.customer_id = ?
               ORDER BY e.event_date DESC, p.amount DESC""",
            (customer_id,),
        ).fetchall()]

        total = sum(p["amount"] for p in payouts)

        return {
            "golfer_name": display_name,
            "total_winnings": round(total, 2),
            "payouts": payouts,
        }


# ═══════════════════════════════════════════════════════════════
#  COO CHAT SESSION PERSISTENCE
# ═══════════════════════════════════════════════════════════════

def get_chat_sessions(limit: int = 20, db_path=None) -> list[dict]:
    """Return recent chat sessions (newest first)."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT s.*, COUNT(m.id) AS message_count
               FROM coo_chat_sessions s
               LEFT JOIN coo_chat_messages m ON m.session_id = s.id
               GROUP BY s.id ORDER BY s.updated_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_chat_session(session_id: int, db_path=None) -> dict | None:
    """Return a single session with all its messages."""
    with _connect(db_path) as conn:
        sess = conn.execute("SELECT * FROM coo_chat_sessions WHERE id = ?", (session_id,)).fetchone()
        if not sess:
            return None
        msgs = conn.execute(
            "SELECT * FROM coo_chat_messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        result = dict(sess)
        result["messages"] = [dict(m) for m in msgs]
        return result


def create_chat_session(title: str = "New Chat", db_path=None) -> dict:
    """Create a new chat session and return it."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO coo_chat_sessions (title) VALUES (?)", (title,)
        )
        conn.commit()
        sess = conn.execute("SELECT * FROM coo_chat_sessions WHERE id = ?", (cur.lastrowid,)).fetchone()
        result = dict(sess)
        result["messages"] = []
        return result


def add_chat_message(session_id: int, role: str, content: str, routed_to: str | None = None, db_path=None) -> dict:
    """Append a message to a chat session."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO coo_chat_messages (session_id, role, content, routed_to) VALUES (?, ?, ?, ?)",
            (session_id, role, content, routed_to),
        )
        conn.execute(
            "UPDATE coo_chat_sessions SET updated_at = datetime('now') WHERE id = ?",
            (session_id,),
        )
        conn.commit()
        msg = conn.execute("SELECT * FROM coo_chat_messages WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(msg)


def update_chat_session_title(session_id: int, title: str, db_path=None) -> dict:
    """Rename a chat session."""
    with _connect(db_path) as conn:
        conn.execute("UPDATE coo_chat_sessions SET title = ? WHERE id = ?", (title, session_id))
        conn.commit()
        sess = conn.execute("SELECT * FROM coo_chat_sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(sess)


def update_chat_session_summary(session_id: int, summary: str, db_path=None) -> dict:
    """Update the running summary of a chat session."""
    with _connect(db_path) as conn:
        conn.execute("UPDATE coo_chat_sessions SET summary = ? WHERE id = ?", (summary, session_id))
        conn.commit()
        sess = conn.execute("SELECT * FROM coo_chat_sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(sess)


def get_chat_master_context(exclude_session_id: int | None = None, db_path=None) -> str:
    """Build a master context string from all past session summaries.
    This gives the AI a 'table of contents' of all prior conversations,
    so it can maintain context across sessions."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT id, title, summary, updated_at,
                      (SELECT COUNT(*) FROM coo_chat_messages WHERE session_id = s.id) AS msg_count
               FROM coo_chat_sessions s
               WHERE summary != '' AND summary IS NOT NULL
               ORDER BY updated_at DESC LIMIT 50""",
        ).fetchall()
    if not rows:
        return ""

    lines = ["MASTER CONVERSATION LOG — Table of Contents"]
    lines.append("You have persistent memory of all past conversations with Kerry:")
    lines.append("")
    for r in rows:
        if exclude_session_id and r["id"] == exclude_session_id:
            continue
        date = r["updated_at"] or "unknown"
        lines.append(f"[Session #{r['id']}] {date} — \"{r['title']}\" ({r['msg_count']} messages)")
        if r["summary"]:
            lines.append(f"  Summary: {r['summary']}")
        lines.append("")
    lines.append("Reference these naturally when relevant. If Kerry asks about something discussed before, recall it.")
    return "\n".join(lines)


def delete_chat_session(session_id: int, db_path=None) -> dict:
    """Delete a chat session and all its messages."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM coo_chat_messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM coo_chat_sessions WHERE id = ?", (session_id,))
        conn.commit()
    return {"deleted": session_id}


# ── Batch Categorization Preview & Promotion ─────────────────────────────────

def get_expense_batch_preview(limit: int = 20, offset: int = 0,
                              db_path: str | Path | None = None) -> dict:
    """Return a unified batch of ALL uncategorized transactions with AI suggestions.

    Merges two pools (both sorted by date desc, interleaved):
    - Pool A: expense_transactions WHERE review_status='pending'
      → item_type='expense', on approve: promote to acct_transactions
    - Pool B: acct_transactions with no categorized splits (type != transfer)
      → item_type='acct', on approve: update existing split category

    Each item includes:
    - suggestion: {category_name, entity_name, confidence, source}
    - is_duplicate: True if a matching acct_transaction already covers this
    """
    with _connect(db_path) as conn:
        # --- Count both pools ---
        exp_total = conn.execute(
            "SELECT COUNT(*) as c FROM expense_transactions WHERE review_status = 'pending'"
        ).fetchone()["c"]

        acct_uncategorized_total = conn.execute(
            """SELECT COUNT(*) as c FROM acct_transactions t
               WHERE t.type != 'transfer'
                 AND t.id NOT IN (
                     SELECT s.transaction_id FROM acct_splits s WHERE s.category_id IS NOT NULL
                 )"""
        ).fetchone()["c"]

        total = exp_total + acct_uncategorized_total

        # --- Fetch ALL unprocessed items (both pools, sorted by date) ---
        exp_rows = conn.execute(
            """SELECT id, transaction_date as date, merchant as description,
                      amount as total_amount, source_type as source,
                      transaction_type as type, account_last4, account_name,
                      event_name, notes, 'expense' as item_type
               FROM expense_transactions
               WHERE review_status = 'pending'"""
        ).fetchall()

        acct_rows = conn.execute(
            """SELECT t.id, t.date, t.description, t.total_amount, t.source,
                      t.type, NULL as account_last4, a.name as account_name,
                      t.event_name, t.notes, 'acct' as item_type
               FROM acct_transactions t
               LEFT JOIN acct_accounts a ON a.id = t.account_id
               WHERE t.type != 'transfer'
                 AND t.id NOT IN (
                     SELECT s.transaction_id FROM acct_splits s WHERE s.category_id IS NOT NULL
                 )"""
        ).fetchall()

        # Merge and sort by date descending
        all_rows = sorted(
            [dict(r) for r in exp_rows] + [dict(r) for r in acct_rows],
            key=lambda r: (r.get("date") or ""),
            reverse=True,
        )
        page_rows = all_rows[offset: offset + limit]

        suggestion_data = get_expense_suggestions(conn)

        # Fingerprints of existing acct_transactions for duplicate detection
        # (only used to flag expense items — acct items are already in the ledger)
        acct_fps = set()
        for r in conn.execute(
            "SELECT date, total_amount, source FROM acct_transactions WHERE COALESCE(status,'active') != 'reversed'"
        ).fetchall():
            acct_fps.add((r["date"] or "", round(float(r["total_amount"] or 0), 2),
                         (r["source"] or "").lower()))

        # Run AI suggestions on the page's descriptions in one batch
        descriptions = [r.get("description") or "" for r in page_rows]
        types        = [r.get("type") or "expense" for r in page_rows]
        ai_suggestions = auto_categorize_transactions(descriptions, types, db_path)

        items = []
        for r, ai_sug in zip(page_rows, ai_suggestions):
            item_type = r.get("item_type", "expense")
            merchant  = r.get("description") or ""
            src       = r.get("source") or ""

            # Prefer AI suggestion; fall back to merchant-based lookup for expense items
            if ai_sug and ai_sug.get("confidence") not in (None, "none", "skip"):
                sug_cat  = ai_sug.get("category_name") or ""
                sug_ent  = ai_sug.get("entity_name") or ""
                sug_conf = ai_sug.get("confidence") or "none"
                sug_src  = ai_sug.get("source") or ""
            else:
                fallback = suggest_for_merchant(merchant, suggestion_data) or {}
                sug_cat  = fallback.get("category") or ""
                sug_ent  = fallback.get("entity") or ""
                sug_conf = fallback.get("confidence") or "none"
                sug_src  = fallback.get("source") or ""

            # Duplicate flag only relevant for expense items
            is_duplicate = False
            if item_type == "expense":
                fp = (r.get("date") or "",
                      round(float(r.get("total_amount") or 0), 2),
                      src.lower())
                is_duplicate = fp in acct_fps

            items.append({
                "id":               r["id"],
                "item_type":        item_type,
                "date":             r.get("date"),
                "merchant":         merchant,
                "amount":           r.get("total_amount"),
                "source_type":      src,
                "transaction_type": r.get("type") or "expense",
                "account_last4":    r.get("account_last4"),
                "account_name":     r.get("account_name"),
                "event_name":       r.get("event_name"),
                "notes":            r.get("notes"),
                "suggestion": {
                    "category_name": sug_cat,
                    "entity_name":   sug_ent,
                    "confidence":    sug_conf,
                    "source":        sug_src,
                },
                "is_duplicate": is_duplicate,
            })

    categories = get_acct_categories(db_path=db_path)
    entities   = get_all_acct_entities(db_path=db_path)

    return {
        "items":      items,
        "total":      total,
        "exp_total":  exp_total,
        "acct_total": acct_uncategorized_total,
        "limit":      limit,
        "offset":     offset,
        "categories": categories,
        "entities":   entities,
    }


def promote_expense_to_ledger(expense_id: int, category_name: str | None,
                               entity_name: str | None, account_id: int | None = None,
                               event_name: str | None = None, notes: str | None = None,
                               db_path: str | Path | None = None) -> dict:
    """Promote an approved expense_transaction into acct_transactions.

    Creates a proper ledger entry + split, links the two tables via
    expense_transactions.acct_transaction_id, and learns a keyword rule
    if a confident category assignment was made.
    """
    with _connect(db_path) as conn:
        exp = conn.execute(
            "SELECT * FROM expense_transactions WHERE id = ?", (expense_id,)
        ).fetchone()
        if not exp:
            return {"error": f"expense_transaction {expense_id} not found"}
        exp = dict(exp)

        # If already promoted, return the linked acct_transaction
        if exp.get("acct_transaction_id"):
            return {"skipped": True, "acct_transaction_id": exp["acct_transaction_id"]}

        # Resolve category FK
        category_id = None
        if category_name:
            cat_row = conn.execute(
                "SELECT id FROM acct_categories WHERE LOWER(name) = LOWER(?) LIMIT 1",
                (category_name,),
            ).fetchone()
            if cat_row:
                category_id = cat_row["id"]

        # Resolve entity FK
        entity_id = None
        if entity_name:
            ent_row = conn.execute(
                "SELECT id FROM acct_entities WHERE LOWER(short_name) = LOWER(?) OR LOWER(name) = LOWER(?) LIMIT 1",
                (entity_name, entity_name),
            ).fetchone()
            if ent_row:
                entity_id = ent_row["id"]

        # Resolve event FK for split
        event_id = None
        lookup_event = event_name or exp.get("event_name")
        if lookup_event:
            ev_row = conn.execute(
                "SELECT id FROM events WHERE LOWER(item_name) = LOWER(?) LIMIT 1",
                (lookup_event,),
            ).fetchone()
            if ev_row:
                event_id = ev_row["id"]

        # Use default checking account if none provided
        if not account_id:
            acc_row = conn.execute(
                "SELECT id FROM acct_accounts WHERE account_type = 'checking' AND is_active = 1 LIMIT 1"
            ).fetchone()
            if acc_row:
                account_id = acc_row["id"]

        # Map raw transaction_type to the CHECK-allowed type values
        # ('income', 'expense', 'transfer'). Same map as in
        # _sync_expense_ledger_entry — kept in sync.
        _raw_txn_type = exp.get("transaction_type") or "expense"
        _type_map = {"received": "income", "payout": "expense",
                     "expense": "expense", "transfer": "transfer"}
        txn_type = _type_map.get(_raw_txn_type, "expense")
        amount = float(exp.get("amount") or 0)
        merchant = exp.get("merchant") or "(unknown)"
        txn_date = exp.get("transaction_date") or datetime.utcnow().strftime("%Y-%m-%d")
        source = exp.get("source_type") or "manual"
        source_ref = f"exp-promoted-{expense_id}"
        final_notes = notes or exp.get("notes")

        cur = conn.execute(
            """INSERT INTO acct_transactions
               (date, description, total_amount, amount, type, entry_type,
                account_id, source, source_ref, notes, event_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (txn_date, merchant, amount, amount, txn_type, txn_type,
             account_id, source, source_ref, final_notes, lookup_event),
        )
        txn_id = cur.lastrowid

        conn.execute(
            """INSERT INTO acct_splits
               (transaction_id, entity_id, category_id, amount, event_id)
               VALUES (?, ?, ?, ?, ?)""",
            (txn_id, entity_id, category_id, amount, event_id),
        )

        # Mark expense as promoted
        conn.execute(
            """UPDATE expense_transactions
               SET review_status = 'approved', acct_transaction_id = ?,
                   reviewed_at = datetime('now')
               WHERE id = ?""",
            (txn_id, expense_id),
        )

        # Learn a keyword rule for future auto-categorization
        if category_id and merchant:
            existing_rule = conn.execute(
                "SELECT id FROM acct_keyword_rules WHERE LOWER(keyword) = LOWER(?) AND category_id = ? LIMIT 1",
                (merchant, category_id),
            ).fetchone()
            if not existing_rule:
                try:
                    conn.execute(
                        """INSERT INTO acct_keyword_rules (keyword, match_type, category_id, entity_id, is_active)
                           VALUES (?, 'contains', ?, ?, 1)""",
                        (merchant, category_id, entity_id),
                    )
                except sqlite3.IntegrityError:
                    pass

        conn.commit()

    return {"promoted": True, "acct_transaction_id": txn_id, "expense_id": expense_id}


def _approve_acct_item(txn_id: int, category_name: str | None,
                        entity_name: str | None, event_name: str | None = None,
                        db_path: str | Path | None = None) -> None:
    """Apply a category + entity to an existing acct_transaction's split."""
    with _connect(db_path) as conn:
        category_id = None
        if category_name:
            row = conn.execute(
                "SELECT id FROM acct_categories WHERE LOWER(name) = LOWER(?) LIMIT 1",
                (category_name,),
            ).fetchone()
            if row:
                category_id = row["id"]

        entity_id = None
        if entity_name:
            row = conn.execute(
                "SELECT id FROM acct_entities WHERE LOWER(short_name) = LOWER(?) OR LOWER(name) = LOWER(?) LIMIT 1",
                (entity_name, entity_name),
            ).fetchone()
            if row:
                entity_id = row["id"]

        event_id = None
        if event_name:
            row = conn.execute(
                "SELECT id FROM events WHERE LOWER(item_name) = LOWER(?) LIMIT 1",
                (event_name,),
            ).fetchone()
            if row:
                event_id = row["id"]

        split = conn.execute(
            "SELECT id FROM acct_splits WHERE transaction_id = ? LIMIT 1", (txn_id,)
        ).fetchone()

        if split:
            conn.execute(
                """UPDATE acct_splits SET category_id = ?, entity_id = ?,
                   event_id = COALESCE(?, event_id) WHERE id = ?""",
                (category_id, entity_id, event_id, split["id"]),
            )
        else:
            # No split yet — create one
            txn = conn.execute(
                "SELECT total_amount FROM acct_transactions WHERE id = ?", (txn_id,)
            ).fetchone()
            if txn:
                conn.execute(
                    """INSERT INTO acct_splits (transaction_id, entity_id, category_id, amount, event_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (txn_id, entity_id, category_id, txn["total_amount"], event_id),
                )
        conn.commit()


def batch_approve_expenses(items: list[dict],
                           db_path: str | Path | None = None) -> dict:
    """Approve a mixed batch of expense_transactions and acct_transactions.

    Each item: {id, item_type, category_name, entity_name, account_id?, event_name?, notes?}
    - item_type='expense' → promote via promote_expense_to_ledger
    - item_type='acct'    → update existing split via _approve_acct_item

    Returns {approved, skipped, errors}.
    """
    approved, skipped, errors = 0, 0, []
    for item in items:
        item_id   = item.get("id")
        item_type = item.get("item_type", "expense")
        if not item_id:
            continue
        if item.get("skip"):
            skipped += 1
            continue
        try:
            if item_type == "acct":
                _approve_acct_item(
                    txn_id=item_id,
                    category_name=item.get("category_name"),
                    entity_name=item.get("entity_name"),
                    event_name=item.get("event_name"),
                    db_path=db_path,
                )
                approved += 1
            else:
                result = promote_expense_to_ledger(
                    expense_id=item_id,
                    category_name=item.get("category_name"),
                    entity_name=item.get("entity_name"),
                    account_id=item.get("account_id"),
                    event_name=item.get("event_name"),
                    notes=item.get("notes"),
                    db_path=db_path,
                )
                if result.get("skipped"):
                    skipped += 1
                else:
                    approved += 1
        except Exception as e:
            errors.append({"id": item_id, "error": str(e)})
    return {"approved": approved, "skipped": skipped, "errors": errors}


# ─────────────────────────────────────────────────────────────────────────────
# Pairings
# ─────────────────────────────────────────────────────────────────────────────

def _pairing_time_slots(event: dict, holes: str) -> list[str]:
    """Compute ordered slot labels for a given holes type (9 or 18).

    For tee-time events returns formatted clock strings ("8:00 AM", …).
    For shotgun events returns hole identifiers ("1A", "1B", "2A", …).
    """
    combo = (event.get("format") or "").strip() == "9/18 Combo"
    if combo and holes == "18":
        start_type = event.get("start_type_18") or "Tee Times"
        start_time = event.get("start_time_18")
        count = event.get("tee_time_count_18") or 0
    else:
        start_type = event.get("start_type") or "Tee Times"
        start_time = event.get("start_time")
        count = event.get("tee_time_count") or 0

    interval = event.get("tee_time_interval") or 10
    count = int(count)
    interval = int(interval)

    if count == 0:
        return []

    if start_type == "Shotgun":
        return [f"{(i // 2) + 1}{'A' if i % 2 == 0 else 'B'}" for i in range(count)]

    if not start_time:
        return [f"Group {i + 1}" for i in range(count)]

    try:
        base = datetime.strptime(start_time, "%H:%M")
    except ValueError:
        return [f"Group {i + 1}" for i in range(count)]

    slots = []
    for i in range(count):
        t = base + timedelta(minutes=i * interval)
        label = t.strftime("%I:%M %p").lstrip("0") or "12:00 AM"
        slots.append(label)
    return slots


def _ensure_pairing_tables(conn: sqlite3.Connection) -> None:
    """Create pairing tables if they don't exist (handles live DB migration)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_pairings (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id       INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            holes          TEXT NOT NULL CHECK(holes IN ('9', '18')),
            group_num      INTEGER NOT NULL,
            slot_label     TEXT NOT NULL,
            player_name    TEXT NOT NULL,
            cart_pos       INTEGER NOT NULL CHECK(cart_pos BETWEEN 1 AND 4),
            tee_choice     TEXT,
            handicap_index REAL,
            created_at     TEXT DEFAULT (datetime('now')),
            UNIQUE(event_id, holes, group_num, cart_pos)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_event_pairings_event ON event_pairings(event_id)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pairing_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            player_a    TEXT NOT NULL,
            player_b    TEXT NOT NULL,
            event_id    INTEGER NOT NULL REFERENCES events(id),
            event_date  TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(player_a, player_b, event_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pairing_history_ab ON pairing_history(player_a, player_b)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pairing_history_date ON pairing_history(event_date)"
    )
    conn.commit()


def get_event_pairings(event_id: int, db_path=None) -> dict:
    """Return saved pairings for an event keyed by holes ('9' / '18').

    Each value is a list of groups:
        [{"group_num": int, "slot_label": str, "players": [...]}, ...]
    Players: {"name", "cart_pos", "tee_choice", "handicap_index"}
    """
    with _connect(db_path) as conn:
        _ensure_pairing_tables(conn)
        rows = conn.execute(
            """
            SELECT holes, group_num, slot_label, player_name,
                   cart_pos, tee_choice, handicap_index
            FROM event_pairings
            WHERE event_id = ?
            ORDER BY holes, group_num, cart_pos
            """,
            (event_id,),
        ).fetchall()

    result: dict = {}
    for r in rows:
        h = r["holes"]
        if h not in result:
            result[h] = []
        grp_list = result[h]
        # Find or create the group entry
        grp = next((g for g in grp_list if g["group_num"] == r["group_num"]), None)
        if grp is None:
            grp = {"group_num": r["group_num"], "slot_label": r["slot_label"], "players": []}
            grp_list.append(grp)
        grp["players"].append({
            "name": r["player_name"],
            "cart_pos": r["cart_pos"],
            "tee_choice": r["tee_choice"],
            "handicap_index": r["handicap_index"],
        })
    return result


def save_event_pairings(event_id: int, groups_by_holes: dict, db_path=None) -> None:
    """Persist pairings for an event and rebuild pairing_history rows.

    groups_by_holes: {"9": [...], "18": [...]}
    Each group: {"group_num", "slot_label", "players": [{"name", "cart_pos",
                  "tee_choice", "handicap_index"}]}
    """
    with _connect(db_path) as conn:
        _ensure_pairing_tables(conn)
        # Load event date for history
        ev_row = conn.execute(
            "SELECT event_date FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        event_date = ev_row["event_date"] if ev_row else datetime.now().strftime("%Y-%m-%d")

        # Replace existing pairings for this event
        conn.execute("DELETE FROM event_pairings WHERE event_id = ?", (event_id,))
        conn.execute("DELETE FROM pairing_history WHERE event_id = ?", (event_id,))

        for holes, groups in groups_by_holes.items():
            for grp in groups:
                group_num = grp["group_num"]
                slot_label = grp["slot_label"]
                for p in grp["players"]:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO event_pairings
                            (event_id, holes, group_num, slot_label, player_name,
                             cart_pos, tee_choice, handicap_index)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id, holes, group_num, slot_label,
                            p["name"], p["cart_pos"],
                            p.get("tee_choice"), p.get("handicap_index"),
                        ),
                    )

                # Record every pair in history
                player_names = [p["name"] for p in grp["players"]]
                for i in range(len(player_names)):
                    for j in range(i + 1, len(player_names)):
                        a = min(player_names[i], player_names[j])
                        b = max(player_names[i], player_names[j])
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO pairing_history
                                (player_a, player_b, event_id, event_date)
                            VALUES (?, ?, ?, ?)
                            """,
                            (a, b, event_id, event_date),
                        )

        conn.commit()


def delete_event_pairings(event_id: int, db_path=None) -> None:
    """Remove saved pairings (and their history) for an event."""
    with _connect(db_path) as conn:
        _ensure_pairing_tables(conn)
        conn.execute("DELETE FROM event_pairings WHERE event_id = ?", (event_id,))
        conn.execute("DELETE FROM pairing_history WHERE event_id = ?", (event_id,))
        conn.commit()


def get_pairing_history_counts(year: int | None = None, db_path=None) -> dict:
    """Return a dict mapping (player_a, player_b) → count for the given calendar year.

    player_a < player_b alphabetically (canonical key order).
    If year is None uses the current year.
    """
    if year is None:
        year = datetime.now().year
    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"

    with _connect(db_path) as conn:
        _ensure_pairing_tables(conn)
        rows = conn.execute(
            """
            SELECT player_a, player_b, COUNT(*) as cnt
            FROM pairing_history
            WHERE event_date BETWEEN ? AND ?
            GROUP BY player_a, player_b
            """,
            (year_start, year_end),
        ).fetchall()

    return {(r["player_a"], r["player_b"]): r["cnt"] for r in rows}


def _pair_count(pair_counts: dict, a: str, b: str) -> int:
    """Look up play count for two players (key is alphabetically ordered)."""
    key = (min(a, b), max(a, b))
    return pair_counts.get(key, 0)


def _group_score(players: list[str], pair_counts: dict) -> int:
    """Total pairings count for all combinations within a group."""
    total = 0
    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            total += _pair_count(pair_counts, players[i], players[j])
    return total


def _find_partner_name(request_text: str, all_names: list[str], requester: str) -> str | None:
    """Fuzzy-match a partner_request string against available player names."""
    if not request_text:
        return None
    req = request_text.lower().strip()
    for name in all_names:
        if name.lower() == requester.lower():
            continue
        if req in name.lower() or name.lower() in req:
            return name
    return None


def generate_event_pairings(
    event_id: int,
    mode: str = "random",
    protect_partner_requests: bool = True,
    seeds: list | None = None,
    db_path=None,
) -> dict:
    """Generate pairings for an event and return (but do NOT save) the result.

    mode: 'random' | 'abcd'
    protect_partner_requests: honor partner_request field (random mode only)
    seeds: list of pre-assigned player locks:
        [{"holes": "9"|"18", "slot_index": int (0-based), "players": [{"name", "cart_pos"}]}]

    Returns:
        {
            "9":  [{"group_num", "slot_label", "players": [...]}],
            "18": [...],
            "slots_9":  [str, ...],
            "slots_18": [str, ...],
        }
    """
    import random as _random

    seeds = seeds or []
    with _connect(db_path) as conn:
        # ── Load event ────────────────────────────────────────────────
        ev = conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        if not ev:
            raise ValueError(f"Event {event_id} not found")
        ev = dict(ev)

        fmt = (ev.get("format") or "").strip()
        is_combo = fmt == "9/18 Combo"

        # ── Active players for this event ─────────────────────────────
        # Start from events → aliases → items (mirrors get_all_events join order)
        INACTIVE = ("credited", "refunded", "transferred", "wd")
        ph = ",".join("?" * len(INACTIVE))
        items = conn.execute(
            f"""
            SELECT DISTINCT i.customer, i.holes, i.tee_choice, i.partner_request
            FROM events e
            LEFT JOIN event_aliases ea ON ea.canonical_event_name = e.item_name
            JOIN items i ON (
                i.item_name = e.item_name COLLATE NOCASE
                OR i.item_name = ea.alias_name COLLATE NOCASE
                OR i.event_id = e.id
            )
            WHERE e.id = ?
              AND COALESCE(i.transaction_status, 'active') NOT IN ({ph})
              AND i.parent_item_id IS NULL
            ORDER BY i.customer COLLATE NOCASE
            """,
            (event_id, *INACTIVE),
        ).fetchall()
        items = [dict(r) for r in items]

        # ── Handicap index map ────────────────────────────────────────
        hcp_rows = conn.execute(
            """
            SELECT l.customer_name, p.handicap_index
            FROM (
                SELECT player_name,
                       AVG(differential) as handicap_index
                FROM (
                    SELECT player_name, differential,
                           ROW_NUMBER() OVER (
                               PARTITION BY player_name
                               ORDER BY round_date DESC, id DESC
                           ) as rn
                    FROM handicap_rounds
                    WHERE differential IS NOT NULL
                      AND round_date >= date('now', '-12 months')
                )
                WHERE rn <= 20
                GROUP BY player_name
            ) p
            JOIN handicap_player_links l ON l.player_name = p.player_name
            WHERE l.customer_name IS NOT NULL
            """
        ).fetchall()
        hcp_map = {r["customer_name"].lower(): r["handicap_index"] for r in hcp_rows}

    # ── Normalise holes per player ────────────────────────────────────
    def player_holes(item):
        h = (item.get("holes") or "").strip()
        if h in ("9", "18"):
            return h
        return "18" if fmt in ("18 Holes", "27 Holes") else "9"

    # ── Separate players by holes ─────────────────────────────────────
    nines = [i for i in items if player_holes(i) == "9"]
    eighteens = [i for i in items if player_holes(i) == "18"]
    if not is_combo:
        if fmt in ("18 Holes", "27 Holes"):
            eighteens, nines = items, []
        else:
            nines, eighteens = items, []

    # ── Pairing history for current year ─────────────────────────────
    pair_counts = get_pairing_history_counts(db_path=db_path)

    # ── Generate slots ────────────────────────────────────────────────
    slots_9 = _pairing_time_slots(ev, "9")
    slots_18 = _pairing_time_slots(ev, "18")

    # ── Seed map: holes → {slot_index: {cart_pos: name}} ─────────────
    seed_map: dict[str, dict[int, dict[int, str]]] = {"9": {}, "18": {}}
    seeded_players: dict[str, set] = {"9": set(), "18": set()}
    for s in seeds:
        h = s.get("holes", "9")
        si = s.get("slot_index", 0)
        if si not in seed_map[h]:
            seed_map[h][si] = {}
        for sp in s.get("players", []):
            seed_map[h][si][sp["cart_pos"]] = sp["name"]
            seeded_players[h].add(sp["name"])

    result: dict = {}

    for holes, player_items, slots in [("9", nines, slots_9), ("18", eighteens, slots_18)]:
        if not player_items and not seed_map[holes]:
            continue

        all_names = [p["customer"] for p in player_items if p.get("customer")]
        # Build quick lookup dicts
        tee_map = {p["customer"]: p.get("tee_choice") for p in player_items if p.get("customer")}
        partner_map = {p["customer"]: p.get("partner_request") for p in player_items if p.get("customer")}

        # Players available for free assignment (not seeded)
        free_players = [n for n in all_names if n not in seeded_players[holes]]

        # ── Determine groups to fill ──────────────────────────────────
        n_free = len(free_players)
        # Seeded slots may be partially or fully locked
        n_slots = len(slots) if slots else max(
            1,
            -(-len(all_names) // 4)  # ceil(n/4)
        )

        # Count how many positions are pre-filled per seed slot
        seed_space_used = {si: len(v) for si, v in seed_map[holes].items()}
        # Positions still open in seeded slots
        seed_space_open = {si: 4 - len(v) for si, v in seed_map[holes].items() if len(v) < 4}

        if mode == "abcd":
            groups_players = _abcd_groups(free_players, hcp_map)
        else:
            groups_players = _random_groups(
                free_players, partner_map, pair_counts, protect_partner_requests
            )

        # ── Build final group list with slot labels ───────────────────
        is_shotgun = (ev.get("start_type" if holes == "9" else "start_type_18") == "Shotgun")

        # Start with seeded groups (already filled positions)
        seeded_groups: dict[int, list] = {}
        for si, pos_map in seed_map[holes].items():
            seeded_groups[si] = [
                {"name": pos_map[cp], "cart_pos": cp,
                 "tee_choice": tee_map.get(pos_map[cp]),
                 "handicap_index": hcp_map.get((pos_map[cp] or "").lower())}
                for cp in sorted(pos_map)
            ]

        # Assign free groups to remaining slots
        all_groups: list[dict] = []
        group_num = 1
        free_group_idx = 0

        for si in range(n_slots):
            if si in seeded_groups:
                existing = seeded_groups[si]
                # Fill remaining spots from free groups
                if free_group_idx < len(groups_players):
                    needed = 4 - len(existing)
                    fill_players = groups_players[free_group_idx][:needed]
                    if len(fill_players) == needed:
                        free_group_idx += 1
                    else:
                        free_group_idx += 1
                    next_cart = max((p["cart_pos"] for p in existing), default=0) + 1
                    for fname in fill_players:
                        existing.append({
                            "name": fname,
                            "cart_pos": next_cart,
                            "tee_choice": tee_map.get(fname),
                            "handicap_index": hcp_map.get((fname or "").lower()),
                        })
                        next_cart += 1
                all_groups.append({
                    "slot_label": slots[si] if si < len(slots) else f"Group {si+1}",
                    "players": existing,
                })
            else:
                if free_group_idx < len(groups_players):
                    gp = groups_players[free_group_idx]
                    free_group_idx += 1
                    players_out = []
                    for cp, name in enumerate(gp, start=1):
                        players_out.append({
                            "name": name,
                            "cart_pos": cp,
                            "tee_choice": tee_map.get(name),
                            "handicap_index": hcp_map.get((name or "").lower()),
                        })
                    all_groups.append({
                        "slot_label": slots[si] if si < len(slots) else f"Group {si+1}",
                        "players": players_out,
                    })
                else:
                    # Empty slot (more slots than groups)
                    all_groups.append({
                        "slot_label": slots[si] if si < len(slots) else f"Group {si+1}",
                        "players": [],
                    })

        # Handle overflow: free groups beyond available slots
        while free_group_idx < len(groups_players):
            gp = groups_players[free_group_idx]
            free_group_idx += 1
            players_out = []
            for cp, name in enumerate(gp, start=1):
                players_out.append({
                    "name": name,
                    "cart_pos": cp,
                    "tee_choice": tee_map.get(name),
                    "handicap_index": hcp_map.get((name or "").lower()),
                })
            label = slots[len(all_groups)] if len(all_groups) < len(slots) else f"Group {len(all_groups)+1}"
            all_groups.append({"slot_label": label, "players": players_out})

        # Remove empty groups
        all_groups = [g for g in all_groups if g["players"]]

        # For shotgun: push threesomes to last slots
        if is_shotgun and slots:
            foursomes = [g for g in all_groups if len(g["players"]) >= 4]
            smalls = [g for g in all_groups if len(g["players"]) < 4]
            ordered = foursomes + smalls
            for i, g in enumerate(ordered):
                g["slot_label"] = slots[i] if i < len(slots) else f"Group {i+1}"
        else:
            ordered = all_groups

        # Assign final group_num
        for i, g in enumerate(ordered):
            g["group_num"] = i + 1

        result[holes] = ordered

    result["slots_9"] = slots_9
    result["slots_18"] = slots_18
    return result


def _make_group_sizes(n: int) -> list[int]:
    """Return group sizes summing to n with max 4 per group and no onesomes."""
    if n <= 0:
        return []
    if n <= 4:
        return [n]
    q, r = divmod(n, 4)
    if r == 0:
        return [4] * q
    elif r == 1:
        if q == 1:  # n == 5
            return [2, 3]
        return [4] * (q - 2) + [3, 3, 3]  # e.g. 9→[3,3,3], 13→[4,3,3,3]
    elif r == 2:
        return [4] * (q - 1) + [3, 3]     # e.g. 6→[3,3], 10→[4,3,3]
    else:  # r == 3
        return [4] * q + [3]              # e.g. 7→[4,3], 11→[4,4,3]


def _random_groups(
    players: list[str],
    partner_map: dict,
    pair_counts: dict,
    protect_partner_requests: bool,
) -> list[list[str]]:
    """Form groups using weighted random (history-aware) assignment."""
    import random as _random

    used: set = set()
    units: list[list[str]] = []

    # Build partner pairs first
    if protect_partner_requests:
        for requester, req_text in partner_map.items():
            if requester not in players or requester in used:
                continue
            partner = _find_partner_name(req_text, players, requester)
            if partner and partner not in used:
                units.append([requester, partner])
                used.add(requester)
                used.add(partner)

    # Remaining singles — shuffle for randomness
    singles = [p for p in players if p not in used]
    _random.shuffle(singles)
    for s in singles:
        units.append([s])

    # Determine target group sizes to avoid onesomes
    target_sizes = _make_group_sizes(len(players))
    groups: list[list[str]] = []
    remaining = list(units)

    for target in target_sizes:
        group: list[str] = []
        while len(group) < target and remaining:
            needed = target - len(group)
            fittable = [u for u in remaining if len(u) <= needed]
            if not fittable:
                fittable = remaining
            best_idx = 0
            best_score = float("inf")
            for idx, unit in enumerate(fittable):
                score = sum(
                    _pair_count(pair_counts, g, u)
                    for g in group
                    for u in unit
                )
                if score < best_score:
                    best_score = score
                    best_idx = idx
            chosen = fittable[best_idx]
            remaining.remove(chosen)
            group.extend(chosen)
        if group:
            groups.append(group)

    # Absorb any leftover units (e.g. oversized partner pair) into the last group
    for leftover in remaining:
        if groups:
            groups[-1].extend(leftover)
        else:
            groups.append(leftover)

    return groups


def _abcd_groups(players: list[str], hcp_map: dict) -> list[list[str]]:
    """Form ABCD groups: one A/B/C/D tier player per group, sorted by handicap."""
    if not players:
        return []

    # Sort by handicap index ascending (lower = better = A)
    with_hcp = sorted(
        [(p, hcp_map.get(p.lower())) for p in players if hcp_map.get(p.lower()) is not None],
        key=lambda x: x[1],
    )
    without_hcp = [(p, None) for p in players if hcp_map.get(p.lower()) is None]
    sorted_players = [p for p, _ in with_hcp] + [p for p, _ in without_hcp]

    n = len(sorted_players)
    if n == 0:
        return []

    group_sizes = _make_group_sizes(n)
    num_groups = len(group_sizes)

    if num_groups == 0:
        return []

    # Distribute round-robin: player i goes to group (i % num_groups)
    # Result: each group gets one player from each tier (A/B/C/D), last tier may be short
    groups: list[list[str]] = [[] for _ in range(num_groups)]
    for i, player in enumerate(sorted_players):
        groups[i % num_groups].append(player)

    return groups
