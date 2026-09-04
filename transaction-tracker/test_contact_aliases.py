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

    print("Adopt: the RECORD is stale, not the order (Kerry 2026-09-04)")
    # "Is there any way to wire in actual actions or a path to resolution
    # rather than giving me the action item and requiring me to manually
    # address it": a drift warning has TWO honest endings and only one
    # was wired. This is the other — the person changed jobs or numbers,
    # so the order is right and the record is stale.
    with db._connect(p) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS customer_emails ("
                     "email_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                     " customer_id INTEGER NOT NULL, email TEXT NOT NULL,"
                     " is_primary INTEGER NOT NULL DEFAULT 0,"
                     " is_golf_genius INTEGER NOT NULL DEFAULT 0, label TEXT,"
                     " created_at TEXT, undeliverable INTEGER NOT NULL DEFAULT 0,"
                     " undeliverable_at TEXT, undeliverable_reason TEXT,"
                     " UNIQUE(customer_id, email))")
        for col in ("phone_undeliverable INTEGER NOT NULL DEFAULT 0",
                    "phone_undeliverable_at TEXT",
                    "phone_undeliverable_reason TEXT"):
            try:
                conn.execute(f"ALTER TABLE customers ADD COLUMN {col}")
            except Exception:
                pass
        conn.execute("INSERT INTO customer_emails (customer_id, email, "
                     "is_primary) VALUES (1, 'old@crownusa.com', 1)")
        warn(conn, 1, "John Wade", "email", "new@yahoo.com",
             "old@crownusa.com", "uid-adopt")
        conn.commit()

    res = db.adopt_drift_value(1, "email", "new@yahoo.com", db_path=p)
    check("the call succeeds", res.get("ok"), res)
    with db._connect(p) as conn:
        em = {r["email"]: r["is_primary"] for r in conn.execute(
            "SELECT email, is_primary FROM customer_emails WHERE customer_id = 1")}
    check("the order's value becomes the record",
          em.get("new@yahoo.com") == 1, em)
    check("the OLD address is kept, just not primary",
          em.get("old@crownusa.com") == 0, em)
    with db._connect(p) as conn:
        still_matches = db.is_known_contact_alias(conn, 1, "email",
                                                  "old@crownusa.com")
    check("and it is kept as an alias so past orders still match",
          res["old_kept_as_alias"] is True and still_matches, res)
    check("the action item resolves itself — no manual Dismiss",
          res["warnings_cleared"] == 1, res)
    with db._connect(p) as conn:
        st = conn.execute("SELECT status FROM parse_warnings "
                          "WHERE email_uid = 'uid-adopt'").fetchone()["status"]
    check("and the warning is marked resolved, not dismissed",
          st == "resolved", st)

    r_phone = db.adopt_drift_value(1, "phone", "(210) 555-1234", db_path=p)
    with db._connect(p) as conn:
        ph = conn.execute("SELECT phone FROM customers "
                          "WHERE customer_id = 1").fetchone()["phone"]
    check("phones adopt the same way", ph == "(210) 555-1234", ph)
    check("and the old number survives as an alias",
          r_phone["old_kept_as_alias"] is True, r_phone)
    check("a bad field is refused",
          "error" in db.adopt_drift_value(1, "nickname", "x", db_path=p))

    # Kerry 2026-09-04: he added Logan Billeaud's personal address on the
    # Customer Info form and asked whether the action item would stay
    # gone. It would not have: the form writes `customer_aliases` (so the
    # value MATCHES to the right person) while the drift check read only
    # `contact_aliases` (so it still called the value news). Two lists,
    # one human intention — the check now reads both.
    print("An alias added on the Customer Info form also silences the drift item")
    with db._connect(p) as conn:
        conn.execute("""CREATE TABLE customer_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT, customer_name TEXT,
            alias_type TEXT, alias_value TEXT, customer_id INTEGER)""")
        conn.execute("INSERT INTO customer_aliases "
                     "(customer_name, alias_type, alias_value, customer_id) "
                     "VALUES ('Logan Billeaud', 'email', "
                     "'loganrbo@yahoo.com', 2)")
        # typed with the formatting a person actually uses
        conn.execute("INSERT INTO customer_aliases "
                     "(customer_name, alias_type, alias_value, customer_id) "
                     "VALUES ('Logan Billeaud', 'phone', "
                     "'+1 (512) 555-8899', 2)")
        conn.commit()
        check("an email alias from the form now counts",
              db.is_known_contact_alias(conn, 2, "email", "LoganRBO@yahoo.com"))
        check("a phone alias counts on its digits, however it was typed",
              db.is_known_contact_alias(conn, 2, "phone", "5125558899"))
        check("somebody else's alias still does not count",
              not db.is_known_contact_alias(conn, 1, "email",
                                            "loganrbo@yahoo.com"))
        check("and an unrelated value is still news",
              not db.is_known_contact_alias(conn, 2, "email", "nope@x.com"))

    os.unlink(p)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        raise SystemExit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
