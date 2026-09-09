"""A one-field rename must not produce a surname-less customer.

Kerry 2026-09-09: "Tom Donovan should be the base member's name and Thomas
Donovan the alias." The fix was one bridge call, scoring-customer-set:
796|first_name|Tom. update_customer_info built the display name from the
INCOMING fields alone, so the display became "Tom" — and that label was
written to items.customer, cascaded into customer_aliases.customer_name
and handicap_player_links.customer_name, and his registration stopped
resolving by name. The UI card never hit it because it always sends first
and last together; the bridge sends one field.

Class, not instance: the display name is now built from the merged name
parts (incoming over on-record), and the cascade is keyed on customer_id
with a name sweep only for unlinked rows — so a repair pass can also
re-stamp rows an earlier bad label left behind.

Run: python3 test_customer_rename_cascade.py
"""

import os
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label
          + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILURES.append(label)


def fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    with db._connect(p) as conn:
        conn.executescript("""
            CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,
                first_name TEXT, last_name TEXT, suffix TEXT, phone TEXT,
                chapter TEXT, venmo_username TEXT, payment_method TEXT,
                payment_handle TEXT, current_player_status TEXT,
                updated_at TEXT);
            CREATE TABLE items (id INTEGER PRIMARY KEY, customer TEXT,
                customer_id INTEGER, first_name TEXT, last_name TEXT,
                suffix TEXT, customer_email TEXT, customer_phone TEXT,
                chapter TEXT, item_name TEXT);
            CREATE TABLE customer_aliases (id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL, alias_type TEXT NOT NULL,
                alias_value TEXT NOT NULL, customer_id INTEGER, note TEXT);
            CREATE TABLE handicap_player_links (player_name TEXT PRIMARY KEY,
                customer_name TEXT, customer_id INTEGER);
            CREATE TABLE customer_emails (email_id INTEGER PRIMARY KEY,
                customer_id INTEGER, email TEXT, is_primary INTEGER, label TEXT);
        """)
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) "
                     "VALUES (796, 'Thomas', 'Donovan')")
        conn.execute("INSERT INTO items (id, customer, customer_id, first_name, "
                     "last_name, item_name) VALUES (1, 'Tom Donovan', 796, "
                     "'Thomas', 'Donovan', 'a9.22 SHADOWGLEN')")
        conn.execute("INSERT INTO customer_aliases (customer_name, alias_type, "
                     "alias_value, customer_id) VALUES "
                     "('Thomas Donovan', 'name', 'Tom Donovan', 796)")
        # An unlinked alias row (the bridge used to insert without a cid).
        conn.execute("INSERT INTO customer_aliases (customer_name, alias_type, "
                     "alias_value, customer_id) VALUES "
                     "('Thomas Donovan', 'name', 'T. Donovan', NULL)")
        conn.execute("INSERT INTO handicap_player_links VALUES "
                     "('Tom Donovan', 'Thomas Donovan', 796)")
        # Somebody else with a similar name must be untouched.
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) "
                     "VALUES (5, 'Tom', 'Donovan-Smith')")
        conn.execute("INSERT INTO handicap_player_links VALUES "
                     "('Tom Donovan-Smith', 'Tom Donovan-Smith', 5)")
        conn.commit()
    return p


def snapshot(p):
    with db._connect(p) as conn:
        cust = dict(conn.execute(
            "SELECT first_name, last_name FROM customers WHERE customer_id = 796"
        ).fetchone())
        item = conn.execute("SELECT customer FROM items WHERE id = 1").fetchone()[0]
        aliases = [dict(r) for r in conn.execute(
            "SELECT customer_name, alias_value, customer_id FROM customer_aliases "
            "ORDER BY id").fetchall()]
        links = {r["player_name"]: r["customer_name"] for r in conn.execute(
            "SELECT player_name, customer_name FROM handicap_player_links")}
    return cust, item, aliases, links


def main():
    # 1. The exact call that went wrong: one field, first_name only.
    p = fresh_db()
    n = db.update_customer_info("Thomas Donovan", {"first_name": "Tom"},
                                db_path=p, customer_id=796)
    cust, item, aliases, links = snapshot(p)
    check("the items row was updated", n == 1, n)
    check("customers row: first name changed, surname kept",
          cust == {"first_name": "Tom", "last_name": "Donovan"}, cust)
    check("items.customer is the FULL merged name, not 'Tom'",
          item == "Tom Donovan", item)
    check("linked alias row re-labelled by customer_id",
          all(a["customer_name"] == "Tom Donovan" for a in aliases
              if a["customer_id"] == 796 and a["alias_value"] != "Tom Donovan"),
          aliases)
    check("unlinked alias row re-labelled by the name sweep",
          any(a["alias_value"] == "T. Donovan"
              and a["customer_name"] == "Tom Donovan" for a in aliases), aliases)
    check("a name alias equal to the new canonical name is removed",
          not any(a["alias_value"] == "Tom Donovan" for a in aliases), aliases)
    check("handicap link re-labelled by customer_id",
          links.get("Tom Donovan") == "Tom Donovan", links)
    check("the other Tom is untouched",
          links.get("Tom Donovan-Smith") == "Tom Donovan-Smith", links)

    # 2. Last name alone, same rule.
    p = fresh_db()
    db.update_customer_info("Thomas Donovan", {"last_name": "Donavan"},
                            db_path=p, customer_id=796)
    cust, item, aliases, links = snapshot(p)
    check("last-name-only rename keeps the first name",
          item == "Thomas Donavan", item)

    # 3. Both fields together — the UI path — still works exactly as before.
    p = fresh_db()
    db.update_customer_info("Thomas Donovan",
                            {"first_name": "Tom", "last_name": "Donovan"},
                            db_path=p, customer_id=796)
    cust, item, aliases, links = snapshot(p)
    check("two-field rename gives the same result", item == "Tom Donovan", item)

    # 4. Repair pass: the damage the bug left ("Tom" everywhere) is undone by
    #    re-sending the same one field, even though the customers row already
    #    reads Tom Donovan and the label does not "change".
    p = fresh_db()
    with db._connect(p) as conn:
        conn.execute("UPDATE customers SET first_name = 'Tom' WHERE customer_id = 796")
        conn.execute("UPDATE items SET customer = 'Tom' WHERE id = 1")
        conn.execute("UPDATE customer_aliases SET customer_name = 'Tom'")
        conn.execute("UPDATE handicap_player_links SET customer_name = 'Tom' "
                     "WHERE customer_id = 796")
        conn.commit()
    db.update_customer_info("Tom Donovan", {"first_name": "Tom"},
                            db_path=p, customer_id=796)
    cust, item, aliases, links = snapshot(p)
    check("repair: items.customer restored", item == "Tom Donovan", item)
    check("repair: linked alias label restored",
          all(a["customer_name"] == "Tom Donovan" for a in aliases
              if a["customer_id"] == 796), aliases)
    check("repair: handicap link label restored",
          links.get("Tom Donovan") == "Tom Donovan", links)

    # 5. A non-name field never touches the display name.
    p = fresh_db()
    db.update_customer_info("Thomas Donovan", {"chapter": "Austin"},
                            db_path=p, customer_id=796)
    cust, item, aliases, links = snapshot(p)
    check("non-name update leaves items.customer alone",
          item == "Tom Donovan", item)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
