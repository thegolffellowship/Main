"""The roster shows the customer's name, not the order's snapshot.

Kerry 2026-09-08: "Adam Baker came in as James Baker. That should not be.
They should have merged."

They HAD merged — customer 87, with "James Baker" already recorded as a
name alias. What was wrong was the label. Every order stores a snapshot
of the name it arrived under; his 9/7 registration came in as James, and
the roster and pairings rendered that snapshot rather than the canonical
customer.

Fixed in get_all_items because that payload feeds the roster, the
pairings sheet, the GG export and the print pack — patching the one
screen where it was noticed would have left the wrong name on the rest.

Run: python3 test_canonical_display_name.py
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


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    with db._connect(p) as conn:
        conn.executescript("""
            CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,
                                    first_name TEXT, last_name TEXT);
            CREATE TABLE items (id INTEGER PRIMARY KEY, customer TEXT,
                                customer_id INTEGER, item_name TEXT,
                                order_date TEXT, order_time TEXT);
        """)
        conn.execute("INSERT INTO customers VALUES (87, 'Adam', 'Baker')")
        conn.execute("INSERT INTO customers VALUES (99, NULL, NULL)")
        conn.execute("INSERT INTO items VALUES "
                     "(1, 'James Baker', 87, 's9.22', '2026-09-07', NULL)")
        conn.execute("INSERT INTO items VALUES "
                     "(2, 'Adam Baker', 87, 's9.21', '2026-09-01', NULL)")
        # No customer_id at all — nothing to resolve to.
        conn.execute("INSERT INTO items VALUES "
                     "(3, 'Walk Up', NULL, 's9.22', '2026-09-07', NULL)")
        # A nameless shell customer must not blank the row.
        conn.execute("INSERT INTO items VALUES "
                     "(4, 'Real Name', 99, 's9.22', '2026-09-07', NULL)")
        conn.commit()

    by_id = {i["id"]: i for i in db.get_all_items(db_path=p)}

    check("the order's snapshot name is replaced by the canonical one",
          by_id[1]["customer"] == "Adam Baker", by_id[1]["customer"])
    check("what the order actually said is still available",
          by_id[1]["customer_order_name"] == "James Baker",
          by_id[1].get("customer_order_name"))
    check("both of his orders now read the same name",
          by_id[1]["customer"] == by_id[2]["customer"])
    check("a row with no customer_id keeps its own name",
          by_id[3]["customer"] == "Walk Up", by_id[3]["customer"])
    check("a NAMELESS customer record never blanks the row",
          by_id[4]["customer"] == "Real Name", by_id[4]["customer"])
    check("ordering is unchanged (newest first)",
          [i["id"] for i in db.get_all_items(db_path=p)][:1] == [1] or
          [i["id"] for i in db.get_all_items(db_path=p)][0] in (1, 3, 4),
          [i["id"] for i in db.get_all_items(db_path=p)])

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: " + ", ".join(FAILURES))
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
