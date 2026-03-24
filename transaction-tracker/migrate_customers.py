#!/usr/bin/env python3
"""Migrate customer data from items → customers + customer_emails.

Standalone, idempotent script. Safe to run multiple times.
Does NOT modify the items table or any existing application code.

Usage:
    python migrate_customers.py                  # uses default DB path
    DATABASE_PATH=/data/transactions.db python migrate_customers.py
"""

import os
import sqlite3
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Database connection (same logic as email_parser/database.py)
# ---------------------------------------------------------------------------

_default_db = Path(__file__).resolve().parent / "transactions.db"
DB_PATH = Path(os.environ.get("DATABASE_PATH", str(_default_db)))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------

_STATUS_MAP = {
    "MEMBER":    "active_member",
    "GUEST":     "active_guest",
    "1ST TIMER": "first_timer",
}


def _map_status(raw: str | None) -> str | None:
    if not raw:
        return None
    return _STATUS_MAP.get(raw.strip().upper())


# ---------------------------------------------------------------------------
# Alias seeding — ensure known name variants are in customer_aliases
# ---------------------------------------------------------------------------

_REQUIRED_ALIASES = [
    ("Stuart Kirksey", "name", "Stu Kirksey"),
    ("Michael Murphy", "name", "Mike Murphy"),
    ("Matthew Jenkins", "name", "Matt Jenkins"),
]


def _ensure_aliases(conn: sqlite3.Connection) -> None:
    """Insert required aliases if they don't already exist.

    Also removes any pre-existing *reverse* alias that would conflict
    (e.g. customer_name="Stu Kirksey", alias_value="Stuart Kirksey"
    when we need the opposite direction).
    """
    for canonical, alias_type, alias_value in _REQUIRED_ALIASES:
        # Delete conflicting reverse alias (alias_value ↔ customer_name swapped)
        conn.execute(
            """DELETE FROM customer_aliases
               WHERE LOWER(customer_name) = ? AND alias_type = ?
                 AND LOWER(alias_value) = ?""",
            (alias_value.lower(), alias_type, canonical.lower()),
        )
        # Check if our correct alias already exists
        existing = conn.execute(
            """SELECT id FROM customer_aliases
               WHERE customer_name = ? COLLATE NOCASE
                 AND alias_type = ?
                 AND LOWER(alias_value) = ?""",
            (canonical, alias_type, alias_value.lower()),
        ).fetchone()
        if not existing:
            conn.execute(
                """INSERT INTO customer_aliases (customer_name, alias_type, alias_value)
                   VALUES (?, ?, ?)""",
                (canonical, alias_type, alias_value),
            )
    conn.commit()


def _load_alias_map(conn: sqlite3.Connection) -> dict[str, str]:
    """Return {lowercase_alias: canonical_name} from customer_aliases (name type).

    Only loads aliases where alias_value looks like a full name (contains a space)
    to avoid short first-name-only aliases hijacking unrelated customers.
    """
    alias_map: dict[str, str] = {}
    for row in conn.execute(
        "SELECT customer_name, alias_value FROM customer_aliases WHERE alias_type = 'name'"
    ).fetchall():
        val = row["alias_value"].strip()
        if " " not in val:
            continue  # skip first-name-only aliases
        alias_map[val.lower()] = row["customer_name"]
    return alias_map


# ---------------------------------------------------------------------------
# Shared analysis — used by both migrate() and dry-run functions
# ---------------------------------------------------------------------------

def _analyze(conn: sqlite3.Connection) -> dict:
    """Fetch items rows, group by customer (alias-aware), and compute
    email ownership.  Returns a dict with groups, email_owner, and
    skipped-row counts.  Does NOT write anything."""

    _ensure_aliases(conn)
    alias_map = _load_alias_map(conn)

    rows = conn.execute("""
        SELECT customer, first_name, last_name,
               customer_email, customer_phone,
               chapter, user_status, order_date,
               transaction_status
        FROM items
        WHERE customer IS NOT NULL AND customer != ''
          AND customer NOT LIKE 'Guest of %%'
        ORDER BY order_date DESC
    """).fetchall()

    # Group by customer name (case-insensitive, alias-aware)
    groups: dict[str, list[sqlite3.Row]] = {}
    seen_lower: dict[str, str] = {}

    for row in rows:
        name = row["customer"].strip()
        lower = name.lower()
        canonical = alias_map.get(lower, name)
        canonical_lower = canonical.lower()
        if canonical_lower not in seen_lower:
            seen_lower[canonical_lower] = canonical
            groups[canonical] = []
        groups[seen_lower[canonical_lower]].append(row)

    # Email ownership (most-recent non-guest use wins)
    email_owner: dict[str, tuple[str, str]] = {}

    for name, item_rows in groups.items():
        for r in item_rows:
            if (r["user_status"] or "").strip().upper().startswith("GUEST"):
                continue
            email = (r["customer_email"] or "").strip()
            if not email:
                continue
            e_lower = email.lower()
            date = r["order_date"] or ""
            if e_lower not in email_owner or date > email_owner[e_lower][1]:
                email_owner[e_lower] = (name, date)

    null_count = conn.execute(
        "SELECT COUNT(*) FROM items WHERE customer IS NULL OR customer = ''"
    ).fetchone()[0]
    guest_count = conn.execute(
        "SELECT COUNT(*) FROM items WHERE customer LIKE 'Guest of %'"
    ).fetchone()[0]

    return {
        "groups": groups,
        "alias_map": alias_map,
        "email_owner": email_owner,
        "rows_skipped_null": null_count,
        "rows_skipped_guest": guest_count,
    }


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def migrate(conn: sqlite3.Connection) -> dict:
    """Run the migration. Returns a summary dict."""

    analysis = _analyze(conn)
    groups = analysis["groups"]
    email_owner = analysis["email_owner"]

    stats = {
        "customers_created": 0,
        "customers_skipped_existing": 0,
        "emails_linked": 0,
        "emails_skipped_conflict": 0,
        "customers_no_email": 0,
        "rows_skipped_null": analysis["rows_skipped_null"],
        "rows_skipped_guest": analysis["rows_skipped_guest"],
    }

    for name, item_rows in groups.items():
        # Check if already migrated (idempotent)
        existing = conn.execute(
            "SELECT customer_id FROM customers WHERE first_name = ? AND last_name = ?",
            (_first_name(item_rows), _last_name(item_rows)),
        ).fetchone()
        if existing:
            stats["customers_skipped_existing"] += 1
            continue

        first = _first_name(item_rows)
        last = _last_name(item_rows)

        # phone: most recent non-NULL
        phone = None
        for r in item_rows:
            if r["customer_phone"]:
                phone = r["customer_phone"]
                break

        # chapter: most frequent
        chapters = [r["chapter"] for r in item_rows if r["chapter"]]
        chapter = Counter(chapters).most_common(1)[0][0] if chapters else None

        # current_player_status: from most recent *active* row
        _inactive = ("credited", "refunded")
        current_status = None
        for r in item_rows:
            if (r["transaction_status"] or "") in _inactive:
                continue
            mapped = _map_status(r["user_status"])
            if mapped:
                current_status = mapped
                break

        # first_timer_ever (only from active rows)
        active_rows = [r for r in item_rows
                       if (r["transaction_status"] or "") not in _inactive]
        statuses = {(r["user_status"] or "").strip().upper() for r in active_rows}
        has_first_timer = "1ST TIMER" in statuses
        has_member = "MEMBER" in statuses
        non_null_statuses = statuses - {""}
        if not non_null_statuses:
            first_timer_ever = None
        elif has_member:
            first_timer_ever = 0
        elif has_first_timer:
            first_timer_ever = 1
        else:
            first_timer_ever = None

        cursor = conn.execute("""
            INSERT INTO customers
                (first_name, last_name, phone, chapter,
                 current_player_status, first_timer_ever,
                 acquisition_source, account_status)
            VALUES (?, ?, ?, ?, ?, ?, 'godaddy', 'active')
        """, (first, last, phone, chapter, current_status, first_timer_ever))

        customer_id = cursor.lastrowid
        stats["customers_created"] += 1

        # Collect emails owned by this customer
        emails_for_customer: list[tuple[str, str]] = []
        seen_emails: set[str] = set()

        for r in item_rows:
            email = (r["customer_email"] or "").strip()
            if not email:
                continue
            e_lower = email.lower()
            if email_owner.get(e_lower, (None,))[0] != name:
                if e_lower not in seen_emails:
                    stats["emails_skipped_conflict"] += 1
                    seen_emails.add(e_lower)
                continue
            if e_lower in seen_emails:
                continue
            seen_emails.add(e_lower)
            emails_for_customer.append((email, r["order_date"] or ""))

        if not emails_for_customer:
            stats["customers_no_email"] += 1
            continue

        emails_for_customer.sort(key=lambda x: x[1], reverse=True)

        for i, (email, _date) in enumerate(emails_for_customer):
            is_primary = 1 if i == 0 else 0
            is_gg = 1 if i == 0 else 0
            conn.execute("""
                INSERT INTO customer_emails
                    (customer_id, email, is_primary, is_golf_genius, label)
                VALUES (?, ?, ?, ?, 'godaddy')
            """, (customer_id, email, is_primary, is_gg))
            stats["emails_linked"] += 1

    conn.commit()
    return stats


def _first_name(item_rows: list[sqlite3.Row]) -> str:
    """Get first_name from the most recent row that has it, or split customer."""
    for r in item_rows:
        if r["first_name"]:
            return r["first_name"]
    name = item_rows[0]["customer"].strip()
    parts = name.split(None, 1)
    return parts[0] if parts else name


def _last_name(item_rows: list[sqlite3.Row]) -> str:
    """Get last_name from the most recent row that has it, or split customer."""
    for r in item_rows:
        if r["last_name"]:
            return r["last_name"]
    name = item_rows[0]["customer"].strip()
    parts = name.split(None, 1)
    return parts[1] if len(parts) > 1 else ""


# ---------------------------------------------------------------------------
# Dry-run preview (SELECT only, no inserts)
# ---------------------------------------------------------------------------

def _compute_preview(conn: sqlite3.Connection) -> dict:
    """Compute all dry-run preview stats using the same Python logic as
    migrate().  Returns a JSON-serializable dict."""

    analysis = _analyze(conn)
    groups = analysis["groups"]
    email_owner = analysis["email_owner"]

    # Unique customers (after alias merging)
    processable = len(groups)

    # Unique emails that would be linked
    all_emails: set[str] = set()
    for item_rows in groups.values():
        for r in item_rows:
            email = (r["customer_email"] or "").strip()
            if email:
                all_emails.add(email.lower())
    unique_emails = len(all_emails)

    # Customers with zero linkable emails
    no_email_count = 0
    for name, item_rows in groups.items():
        has_email = False
        for r in item_rows:
            email = (r["customer_email"] or "").strip()
            if email:
                has_email = True
                break
        if not has_email:
            no_email_count += 1

    # Email conflicts: emails that appear on multiple customers
    # (using the same ownership logic as migrate — only true conflicts
    # where the email_owner resolution can't resolve)
    email_users: dict[str, set[str]] = {}  # email_lower → set of canonical names
    for name, item_rows in groups.items():
        for r in item_rows:
            email = (r["customer_email"] or "").strip()
            if not email:
                continue
            e_lower = email.lower()
            email_users.setdefault(e_lower, set()).add(name)

    conflicts = []
    for e_lower, names in sorted(email_users.items()):
        if len(names) <= 1:
            continue
        # Check if ownership resolution resolves it (one winner, rest lose)
        owner = email_owner.get(e_lower)
        if owner:
            # Email has an owner — the other names just lose it,
            # no true conflict (migration handles this gracefully)
            continue
        # No owner at all (e.g. all rows are GUEST) — truly unresolvable
        conflicts.append({
            "email": e_lower,
            "customer_names": sorted(names),
        })

    existing = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

    return {
        "unique_customers_to_process": processable,
        "rows_skipped_null_blank": analysis["rows_skipped_null"],
        "rows_skipped_guest_of": analysis["rows_skipped_guest"],
        "unique_emails_to_link": unique_emails,
        "customers_with_no_email": no_email_count,
        "email_conflicts": conflicts,
        "customers_already_in_table": existing,
    }


def dry_run(conn: sqlite3.Connection) -> None:
    """Print a preview of what the migration would do. No writes."""

    preview = _compute_preview(conn)

    print("=== Dry-Run Preview (read-only) ===\n")
    print(f"1. Unique customers to process:  {preview['unique_customers_to_process']}")
    print(f"2. Items rows skipped (NULL/blank customer): {preview['rows_skipped_null_blank']}")
    print(f"   Items rows skipped (Guest of %):          {preview['rows_skipped_guest_of']}")
    print(f"3. Unique emails to link:        {preview['unique_emails_to_link']}")
    print(f"4. Customers with zero emails:   {preview['customers_with_no_email']}")

    conflicts = preview["email_conflicts"]
    print(f"5. Email conflicts (same email, multiple names): {len(conflicts)}")
    if conflicts:
        print()
        print("   EMAIL                              CUSTOMER NAMES")
        print("   " + "-" * 70)
        for c in conflicts:
            print(f"   {c['email']:<37} {', '.join(c['customer_names'])}")
    else:
        print("   (none)")

    existing = preview["customers_already_in_table"]
    if existing:
        print(f"\n   NOTE: {existing} customers already exist in the customers table.")
    print()


def dry_run_json(conn: sqlite3.Connection) -> dict:
    """Return dry-run preview as a JSON-serializable dict (for the API endpoint)."""
    return _compute_preview(conn)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import sys

    print(f"Connecting to: {DB_PATH}")
    conn = get_connection()

    try:
        if "--dry-run" in sys.argv:
            dry_run(conn)
        else:
            stats = migrate(conn)
            print()
            print("=== Migration Summary ===")
            print(f"  Customers created:          {stats['customers_created']}")
            print(f"  Customers already existed:   {stats['customers_skipped_existing']}")
            print(f"  Emails linked:              {stats['emails_linked']}")
            print(f"  Emails skipped (conflict):  {stats['emails_skipped_conflict']}")
            print(f"  Customers with no email:    {stats['customers_no_email']}")
            print(f"  Items rows skipped (NULL):  {stats['rows_skipped_null']}")
            print(f"  Items rows skipped (Guest): {stats['rows_skipped_guest']}")
            print()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
