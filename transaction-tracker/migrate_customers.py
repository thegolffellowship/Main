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
    """Insert required aliases if they don't already exist."""
    for canonical, alias_type, alias_value in _REQUIRED_ALIASES:
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
    """Return {lowercase_alias: canonical_name} from customer_aliases (name type)."""
    alias_map: dict[str, str] = {}
    for row in conn.execute(
        "SELECT customer_name, alias_value FROM customer_aliases WHERE alias_type = 'name'"
    ).fetchall():
        alias_map[row["alias_value"].lower()] = row["customer_name"]
    return alias_map


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def migrate(conn: sqlite3.Connection) -> dict:
    """Run the migration. Returns a summary dict."""

    _ensure_aliases(conn)
    alias_map = _load_alias_map(conn)

    stats = {
        "customers_created": 0,
        "customers_skipped_existing": 0,
        "emails_linked": 0,
        "emails_skipped_conflict": 0,
        "customers_no_email": 0,
        "rows_skipped_null": 0,
        "rows_skipped_guest": 0,
    }

    # ------------------------------------------------------------------
    # 1. Fetch all relevant items rows, ordered by order_date DESC
    #    so row[0] for a group is the most recent.
    # ------------------------------------------------------------------
    rows = conn.execute("""
        SELECT customer, first_name, last_name,
               customer_email, customer_phone,
               chapter, user_status, order_date,
               transaction_status
        FROM items
        WHERE customer IS NOT NULL AND customer != ''
          AND customer NOT LIKE 'Guest of %'
        ORDER BY order_date DESC
    """).fetchall()

    # ------------------------------------------------------------------
    # 2. Group by customer name (case-insensitive, alias-aware)
    # ------------------------------------------------------------------
    groups: dict[str, list[sqlite3.Row]] = {}
    seen_lower: dict[str, str] = {}  # lowercase canonical → canonical name

    for row in rows:
        name = row["customer"].strip()
        lower = name.lower()
        # Resolve alias → canonical name
        canonical = alias_map.get(lower, name)
        canonical_lower = canonical.lower()
        if canonical_lower not in seen_lower:
            seen_lower[canonical_lower] = canonical
            groups[canonical] = []
        groups[seen_lower[canonical_lower]].append(row)

    # ------------------------------------------------------------------
    # 3. Track which emails have been claimed (most-recent-use wins)
    #    Build a map: email → (customer_name, order_date)
    #    Skip GUEST rows — the email on a guest row belongs to the
    #    payer, not the guest.
    # ------------------------------------------------------------------
    email_owner: dict[str, tuple[str, str]] = {}  # email_lower → (customer, order_date)

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

    # ------------------------------------------------------------------
    # 4. Migrate each customer
    # ------------------------------------------------------------------
    for name, item_rows in groups.items():
        # Check if already migrated (idempotent)
        existing = conn.execute(
            "SELECT customer_id FROM customers WHERE first_name = ? AND last_name = ?",
            (_first_name(item_rows), _last_name(item_rows)),
        ).fetchone()
        if existing:
            stats["customers_skipped_existing"] += 1
            continue

        # -- first_name / last_name --
        first = _first_name(item_rows)
        last = _last_name(item_rows)

        # -- phone: most recent non-NULL --
        phone = None
        for r in item_rows:  # already sorted by order_date DESC
            if r["customer_phone"]:
                phone = r["customer_phone"]
                break

        # -- chapter: most frequent --
        chapters = [r["chapter"] for r in item_rows if r["chapter"]]
        chapter = Counter(chapters).most_common(1)[0][0] if chapters else None

        # -- current_player_status: from most recent *active* row --
        #    (skip credited/refunded rows for status determination)
        _inactive = ("credited", "refunded")
        current_status = None
        for r in item_rows:
            if (r["transaction_status"] or "") in _inactive:
                continue
            mapped = _map_status(r["user_status"])
            if mapped:
                current_status = mapped
                break

        # -- first_timer_ever (only from active rows) --
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

        # -- Insert customer --
        cursor = conn.execute("""
            INSERT INTO customers
                (first_name, last_name, phone, chapter,
                 current_player_status, first_timer_ever,
                 acquisition_source, account_status)
            VALUES (?, ?, ?, ?, ?, ?, 'godaddy', 'active')
        """, (first, last, phone, chapter, current_status, first_timer_ever))

        customer_id = cursor.lastrowid
        stats["customers_created"] += 1

        # -- Collect emails owned by this customer --
        emails_for_customer: list[tuple[str, str]] = []  # (email, order_date)
        seen_emails: set[str] = set()

        for r in item_rows:
            email = (r["customer_email"] or "").strip()
            if not email:
                continue
            e_lower = email.lower()
            # Only claim if this customer is the rightful owner
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

        # Sort by order_date DESC — first entry is most recent
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

    # Count skipped rows for summary
    null_count = conn.execute(
        "SELECT COUNT(*) FROM items WHERE customer IS NULL OR customer = ''"
    ).fetchone()[0]
    guest_count = conn.execute(
        "SELECT COUNT(*) FROM items WHERE customer LIKE 'Guest of %'"
    ).fetchone()[0]
    stats["rows_skipped_null"] = null_count
    stats["rows_skipped_guest"] = guest_count

    return stats


def _first_name(item_rows: list[sqlite3.Row]) -> str:
    """Get first_name from the most recent row that has it, or split customer."""
    for r in item_rows:
        if r["first_name"]:
            return r["first_name"]
    # Fallback: split customer on first space
    name = item_rows[0]["customer"].strip()
    parts = name.split(None, 1)
    return parts[0] if parts else name


def _last_name(item_rows: list[sqlite3.Row]) -> str:
    """Get last_name from the most recent row that has it, or split customer."""
    for r in item_rows:
        if r["last_name"]:
            return r["last_name"]
    # Fallback: split customer on first space
    name = item_rows[0]["customer"].strip()
    parts = name.split(None, 1)
    return parts[1] if len(parts) > 1 else ""


# ---------------------------------------------------------------------------
# Dry-run preview (SELECT only, no inserts)
# ---------------------------------------------------------------------------

def dry_run(conn: sqlite3.Connection) -> None:
    """Print a preview of what the migration would do. No writes."""

    _ensure_aliases(conn)

    print("=== Dry-Run Preview (read-only) ===\n")

    # 1. Unique customer names that would be processed (alias-aware)
    processable = conn.execute("""
        SELECT COUNT(DISTINCT LOWER(COALESCE(ca.customer_name, i.customer)))
        FROM items i
        LEFT JOIN customer_aliases ca
          ON LOWER(i.customer) = LOWER(ca.alias_value) AND ca.alias_type = 'name'
        WHERE i.customer IS NOT NULL AND i.customer != ''
          AND i.customer NOT LIKE 'Guest of %'
    """).fetchone()[0]
    print(f"1. Unique customers to process:  {processable}")

    # 2. Skipped rows
    null_blank = conn.execute(
        "SELECT COUNT(*) FROM items WHERE customer IS NULL OR customer = ''"
    ).fetchone()[0]
    guest_of = conn.execute(
        "SELECT COUNT(*) FROM items WHERE customer LIKE 'Guest of %'"
    ).fetchone()[0]
    print(f"2. Items rows skipped (NULL/blank customer): {null_blank}")
    print(f"   Items rows skipped (Guest of %):          {guest_of}")

    # 3. Unique emails that would be linked
    unique_emails = conn.execute("""
        SELECT COUNT(DISTINCT LOWER(customer_email)) FROM items
        WHERE customer IS NOT NULL AND customer != ''
          AND customer NOT LIKE 'Guest of %'
          AND customer_email IS NOT NULL AND customer_email != ''
    """).fetchone()[0]
    print(f"3. Unique emails to link:        {unique_emails}")

    # 4. Customers with zero emails (alias-aware)
    no_email = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT LOWER(COALESCE(ca.customer_name, i.customer)) AS canonical
            FROM items i
            LEFT JOIN customer_aliases ca
              ON LOWER(i.customer) = LOWER(ca.alias_value) AND ca.alias_type = 'name'
            WHERE i.customer IS NOT NULL AND i.customer != ''
              AND i.customer NOT LIKE 'Guest of %'
            GROUP BY canonical
            HAVING SUM(CASE WHEN i.customer_email IS NOT NULL
                             AND i.customer_email != '' THEN 1 ELSE 0 END) = 0
        )
    """).fetchone()[0]
    print(f"4. Customers with zero emails:   {no_email}")

    # 5. Email conflicts — alias-aware, excluding GUEST rows
    #    (guest rows carry the payer's email, not the guest's)
    conflicts = conn.execute("""
        SELECT LOWER(i.customer_email) AS email,
               GROUP_CONCAT(DISTINCT COALESCE(ca.customer_name, i.customer)) AS customer_names,
               COUNT(DISTINCT LOWER(COALESCE(ca.customer_name, i.customer))) AS name_count
        FROM items i
        LEFT JOIN customer_aliases ca
          ON LOWER(i.customer) = LOWER(ca.alias_value) AND ca.alias_type = 'name'
        WHERE i.customer IS NOT NULL AND i.customer != ''
          AND i.customer NOT LIKE 'Guest of %'
          AND i.customer_email IS NOT NULL AND i.customer_email != ''
          AND UPPER(TRIM(COALESCE(i.user_status, ''))) NOT LIKE 'GUEST%'
        GROUP BY LOWER(i.customer_email)
        HAVING COUNT(DISTINCT LOWER(COALESCE(ca.customer_name, i.customer))) > 1
        ORDER BY name_count DESC
    """).fetchall()

    print(f"5. Email conflicts (same email, multiple names): {len(conflicts)}")
    if conflicts:
        print()
        print("   EMAIL                              CUSTOMER NAMES")
        print("   " + "-" * 70)
        for row in conflicts:
            email = row["email"]
            names = row["customer_names"]
            print(f"   {email:<37} {names}")
    else:
        print("   (none)")

    # Bonus: customers already in the customers table
    existing = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    if existing:
        print(f"\n   NOTE: {existing} customers already exist in the customers table.")
    print()


def dry_run_json(conn: sqlite3.Connection) -> dict:
    """Return dry-run preview as a JSON-serializable dict (for the API endpoint)."""

    _ensure_aliases(conn)

    processable = conn.execute("""
        SELECT COUNT(DISTINCT LOWER(COALESCE(ca.customer_name, i.customer)))
        FROM items i
        LEFT JOIN customer_aliases ca
          ON LOWER(i.customer) = LOWER(ca.alias_value) AND ca.alias_type = 'name'
        WHERE i.customer IS NOT NULL AND i.customer != ''
          AND i.customer NOT LIKE 'Guest of %'
    """).fetchone()[0]

    null_blank = conn.execute(
        "SELECT COUNT(*) FROM items WHERE customer IS NULL OR customer = ''"
    ).fetchone()[0]
    guest_of = conn.execute(
        "SELECT COUNT(*) FROM items WHERE customer LIKE 'Guest of %'"
    ).fetchone()[0]

    unique_emails = conn.execute("""
        SELECT COUNT(DISTINCT LOWER(customer_email)) FROM items
        WHERE customer IS NOT NULL AND customer != ''
          AND customer NOT LIKE 'Guest of %'
          AND customer_email IS NOT NULL AND customer_email != ''
    """).fetchone()[0]

    no_email = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT LOWER(COALESCE(ca.customer_name, i.customer)) AS canonical
            FROM items i
            LEFT JOIN customer_aliases ca
              ON LOWER(i.customer) = LOWER(ca.alias_value) AND ca.alias_type = 'name'
            WHERE i.customer IS NOT NULL AND i.customer != ''
              AND i.customer NOT LIKE 'Guest of %'
            GROUP BY canonical
            HAVING SUM(CASE WHEN i.customer_email IS NOT NULL
                             AND i.customer_email != '' THEN 1 ELSE 0 END) = 0
        )
    """).fetchone()[0]

    conflicts = conn.execute("""
        SELECT LOWER(i.customer_email) AS email,
               GROUP_CONCAT(DISTINCT COALESCE(ca.customer_name, i.customer)) AS customer_names,
               COUNT(DISTINCT LOWER(COALESCE(ca.customer_name, i.customer))) AS name_count
        FROM items i
        LEFT JOIN customer_aliases ca
          ON LOWER(i.customer) = LOWER(ca.alias_value) AND ca.alias_type = 'name'
        WHERE i.customer IS NOT NULL AND i.customer != ''
          AND i.customer NOT LIKE 'Guest of %'
          AND i.customer_email IS NOT NULL AND i.customer_email != ''
          AND UPPER(TRIM(COALESCE(i.user_status, ''))) NOT LIKE 'GUEST%'
        GROUP BY LOWER(i.customer_email)
        HAVING COUNT(DISTINCT LOWER(COALESCE(ca.customer_name, i.customer))) > 1
        ORDER BY name_count DESC
    """).fetchall()

    existing = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

    # Diagnostic: inspect alias table and conflict rows
    aliases = conn.execute(
        "SELECT customer_name, alias_type, alias_value FROM customer_aliases WHERE alias_type = 'name'"
    ).fetchall()
    stu_rows = conn.execute(
        "SELECT customer, customer_email, user_status, order_date, transaction_status "
        "FROM items WHERE LOWER(customer) LIKE '%kirksey%'"
    ).fetchall()
    will_rows = conn.execute(
        "SELECT customer, customer_email, user_status, order_date, transaction_status "
        "FROM items WHERE LOWER(customer_email) = 'colbyjohnson8@gmail.com'"
    ).fetchall()

    return {
        "unique_customers_to_process": processable,
        "rows_skipped_null_blank": null_blank,
        "rows_skipped_guest_of": guest_of,
        "unique_emails_to_link": unique_emails,
        "customers_with_no_email": no_email,
        "email_conflicts": [
            {"email": r["email"], "customer_names": r["customer_names"].split(",")}
            for r in conflicts
        ],
        "customers_already_in_table": existing,
        "_debug_aliases": [
            {"customer_name": r["customer_name"], "alias_value": r["alias_value"]}
            for r in aliases
        ],
        "_debug_kirksey_rows": [
            {"customer": r["customer"], "email": r["customer_email"],
             "user_status": r["user_status"], "order_date": r["order_date"],
             "transaction_status": r["transaction_status"]}
            for r in stu_rows
        ],
        "_debug_colby_email_rows": [
            {"customer": r["customer"], "email": r["customer_email"],
             "user_status": r["user_status"], "order_date": r["order_date"],
             "transaction_status": r["transaction_status"]}
            for r in will_rows
        ],
    }


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
