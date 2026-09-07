"""The event registration count follows event_id, not just the name.

Kerry 2026-09-07: "something's wrong with the ShadowGlen counts." The
a9.22 ShadowGlen card read 15/1 — fifteen people on the roster, one
registration. Fourteen of the fifteen orders arrived from the store as
"a9.22 SHADOWGLEN" while the event is "a9.22 ShadowGlen", the counter
matched on NAME only, and every one of those items already carried
event_id = 3313. The id was sitting right there.

Run: python3 test_event_registration_count.py
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
            CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT,
                                 event_date TEXT);
            CREATE TABLE event_aliases (alias_name TEXT,
                                        canonical_event_name TEXT);
            CREATE TABLE items (id INTEGER PRIMARY KEY, item_name TEXT,
                                transaction_status TEXT,
                                parent_item_id INTEGER, event_id INTEGER);
        """)
        conn.execute("INSERT INTO events VALUES (3313,'a9.22 ShadowGlen',"
                     "'2026-09-08')")
        conn.execute("INSERT INTO events VALUES (3306,'s9.22 Silverhorn',"
                     "'2026-09-08')")
        conn.execute("INSERT INTO events VALUES (9001,'x9.1 Legacy',"
                     "'2024-01-01')")
        # The live shape: linked by id, named differently.
        for _ in range(14):
            conn.execute("INSERT INTO items (item_name, transaction_status, "
                         "event_id) VALUES ('a9.22 SHADOWGLEN','active',3313)")
        conn.execute("INSERT INTO items (item_name, transaction_status, "
                     "event_id) VALUES ('a9.22 ShadowGlen','active',3313)")
        # The case that ONLY event_id can catch: a name the event and its
        # aliases do not know at all. Case-folding alone would miss it,
        # which is why the id has to lead rather than merely assist.
        conn.execute("INSERT INTO items (item_name, transaction_status, "
                     "event_id) VALUES ('a9.22 Shadow Glen','active',3313)")
        # An event whose items match by name AND id — must not double.
        for _ in range(18):
            conn.execute("INSERT INTO items (item_name, transaction_status, "
                         "event_id) VALUES ('s9.22 Silverhorn','active',3306)")
        # Legacy rows predating items.event_id: name only, no id.
        for _ in range(3):
            conn.execute("INSERT INTO items (item_name, transaction_status, "
                         "event_id) VALUES ('x9.1 Legacy','active',NULL)")
        # Excluded either way: cancelled, and a child row of a multi.
        conn.execute("INSERT INTO items (item_name, transaction_status, "
                     "event_id) VALUES ('a9.22 SHADOWGLEN','credited',3313)")
        conn.execute("INSERT INTO items (item_name, transaction_status, "
                     "parent_item_id, event_id) "
                     "VALUES ('a9.22 SHADOWGLEN','active',1,3313)")
        conn.commit()

    by_id = {e["id"]: e for e in db.get_all_events(db_path=p)}

    check("an item linked by event_id counts even when the name differs",
          by_id[3313]["registrations"] == 16,
          by_id[3313]["registrations"])
    check("a name no alias knows still counts through the id "
          "(case-folding alone would miss it)",
          by_id[3313]["registrations"] == 16,
          by_id[3313]["registrations"])
    check("matching by BOTH id and name counts a row once, not twice",
          by_id[3306]["registrations"] == 18, by_id[3306]["registrations"])
    check("legacy rows with no event_id still count by name",
          by_id[9001]["registrations"] == 3, by_id[9001]["registrations"])
    check("a credited row is still excluded",
          by_id[3313]["registrations"] == 16)
    check("a child row of a multi-item order is still excluded",
          by_id[3313]["registrations"] == 16)

    # The number on the card must not contradict the roster under it.
    with db._connect(p) as conn:
        roster = conn.execute(
            "SELECT COUNT(*) FROM items WHERE event_id = 3313 "
            "AND COALESCE(transaction_status,'active') = 'active' "
            "AND parent_item_id IS NULL").fetchone()[0]
    check("the count agrees with the event's own roster",
          by_id[3313]["registrations"] == roster,
          (by_id[3313]["registrations"], roster))

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: " + ", ".join(FAILURES))
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
