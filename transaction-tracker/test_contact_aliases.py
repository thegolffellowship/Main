"""Tests for known contact variants (Kerry 2026-09-03).

  "This is a recurring thing with John Wade (Jdub Wade) and it's getting
   annoying that we're not able to deal with this automatically."

The drift warning has always ended with "capture as alias" — but there
was no alias to capture into, so a member whose orders carry a
permanently wrong number re-raised the SAME action item on every order,
forever. Checks:

  - a recorded variant stops the warning being raised again, while the
    CANONICAL value still wins on the saved record (the alias changes
    who gets interrupted, never whose number is right);
  - recording a variant also closes the warnings it already generated;
  - phone matching is on the last 10 digits, so formatting and country
    code never matter, and email matching is case-insensitive;
  - an alias for one customer never silences another customer, and an
    alias on one field never silences the other;
  - a genuinely NEW wrong value still raises, which is the whole point.

Run: python3 test_contact_aliases.py
"""

import os
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


JW_GOOD = "(817) 455-9708"
JW_BAD = "8171559708"


def warn(conn, cid, customer, field, order_val, canonical, uid):
    conn.execute(
        "INSERT OR IGNORE INTO parse_warnings (email_uid, order_id, customer, "
        "customer_id, item_name, warning_code, message) VALUES (?,?,?,?,?,?,?)",
        (uid, uid, customer, cid, "a9.22 SHADOWGLEN",
         "PHONE_DRIFT" if field == "phone" else "EMAIL_DRIFT",
         f"Order customer_{field} '{order_val}' differs from canonical "
         f"'{canonical}' on Customer Info — order value ignored, canonical "
         f"kept. Review and decide whether to update the customer record or "
         f"capture as alias."))


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    with db._connect(p) as conn:
        conn.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, "
                     "first_name TEXT, last_name TEXT, phone TEXT)")
        conn.executemany("INSERT INTO customers VALUES (?,?,?,?)",
                         [(1, "John", "Wade", JW_GOOD),
                          (2, "Other", "Member", "(210) 555-0000")])
        conn.execute("""CREATE TABLE parse_warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, email_uid TEXT, order_id TEXT,
            customer TEXT, customer_id INTEGER, item_name TEXT,
            warning_code TEXT NOT NULL, message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open', created_at TEXT,
            UNIQUE(email_uid, warning_code, item_name))""")
        db.ensure_contact_alias_table(conn)
        # Three orders' worth of the same nuisance, exactly as Kerry sees it
        for i in range(3):
            warn(conn, 1, "Jdub Wade", "phone", JW_BAD, JW_GOOD, f"uid-{i}")
        warn(conn, 2, "Other Member", "phone", "2105559999",
             "(210) 555-0000", "uid-other")
        conn.commit()

    print("Message parsing")
    msg = "Order customer_phone '8171559708' differs from canonical '(817) 455-9708' on Customer Info"
    check("parses field + order value", db.parse_drift_warning(msg) == ("phone", JW_BAD),
          db.parse_drift_warning(msg))
    check("parses the email variant",
          db.parse_drift_warning("Order customer_email 'a@B.com' differs from canonical 'a@b.com'")
          == ("email", "a@B.com"))
    check("ignores an unrelated message", db.parse_drift_warning("some other warning") is None)

    print("Normalization")
    check("phone compares on the last 10 digits",
          db.normalize_contact_value("phone", "+1 (817) 455-9708")
          == db.normalize_contact_value("phone", "817-455-9708") == "8174559708")
    check("email compares lowercased",
          db.normalize_contact_value("email", "  A@B.COM ") == "a@b.com")

    print("Recording the variant")
    with db._connect(p) as conn:
        open_before = conn.execute(
            "SELECT COUNT(*) FROM parse_warnings WHERE status='open'").fetchone()[0]
    check("Kerry is looking at 4 open warnings", open_before == 4, open_before)
    res = db.add_contact_alias(1, "phone", JW_BAD, note="Jdub types it wrong",
                               db_path=p)
    check("alias recorded", res.get("ok"), res)
    check("all three of John's warnings closed at once",
          res.get("warnings_cleared") == 3, res)
    with db._connect(p) as conn:
        still = conn.execute(
            "SELECT COUNT(*) FROM parse_warnings WHERE status='open'").fetchone()[0]
        who = conn.execute(
            "SELECT customer FROM parse_warnings WHERE status='open'").fetchone()
    check("the other member's warning is untouched", still == 1, still)
    check("and it is the OTHER member's", who["customer"] == "Other Member", dict(who))

    print("Suppression from here on")
    with db._connect(p) as conn:
        check("the recorded variant is now known",
              db.is_known_contact_alias(conn, 1, "phone", JW_BAD))
        check("...in any formatting",
              db.is_known_contact_alias(conn, 1, "phone", "+1 817-155-9708"))
        check("a DIFFERENT wrong number still raises",
              not db.is_known_contact_alias(conn, 1, "phone", "8179999999"))
        check("the alias does not leak to another customer",
              not db.is_known_contact_alias(conn, 2, "phone", JW_BAD))
        check("a phone alias does not silence email drift",
              not db.is_known_contact_alias(conn, 1, "email", JW_BAD))

    print("Idempotence and guards")
    again = db.add_contact_alias(1, "phone", "817-155-9708", db_path=p)
    check("re-recording the same variant is a no-op, not a duplicate",
          again.get("ok") and len(db.list_contact_aliases(1, db_path=p)) == 1,
          db.list_contact_aliases(1, db_path=p))
    check("customer_phone is accepted as a field name",
          db.add_contact_alias(1, "customer_phone", JW_BAD, db_path=p).get("ok"))
    check("a bad field is refused",
          db.add_contact_alias(1, "address", "x", db_path=p).get("error"))
    check("an unknown customer is refused",
          db.add_contact_alias(999, "phone", "2105551234", db_path=p).get("error"))
    check("an unnormalizable value is refused",
          db.add_contact_alias(1, "phone", "abc", db_path=p).get("error"))

    print("Listing")
    rows = db.list_contact_aliases(db_path=p)
    check("listing carries the customer name", rows and rows[0]["last_name"] == "Wade",
          rows[:1])
    check("and the note Kerry left",
          rows[0]["note"] == "Jdub types it wrong", rows[0].get("note"))

    os.unlink(p)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        raise SystemExit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
