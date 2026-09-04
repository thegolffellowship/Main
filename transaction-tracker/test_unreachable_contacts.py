"""Unreachable contact details (Kerry 2026-09-04, Hayden Cooper).

  "Remove hayden's email. I guess it could be an alias, but not
   something that he'd ever be sent an email thru. He doesn't work
   there anymore. He didn't provide me with a new one."

A work address dies when someone changes jobs. DELETING the row loses
the match on their historical GoDaddy / Golf Genius records; leaving it
live keeps mailing a dead mailbox. The address stays for MATCHING and is
barred from SENDING. Checks:

  - the resolver stops handing it out — including its promote-to-primary
    step, which would otherwise pick a dead address straight back up;
  - a surviving live address is promoted in its place;
  - with nothing left, an action item says so, because the alternative
    is a member silently receiving nothing;
  - undo puts it back;
  - the row itself is never deleted — matching still works;
  - the PHONE gets the same treatment ("It was his work number"), and
    the two share ONE action item per person that escalates when both
    channels are gone and closes itself when either comes back.

Run: python3 test_unreachable_contacts.py
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


def emails(p, cid):
    with db._connect(p) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT email, is_primary, undeliverable FROM customer_emails "
            "WHERE customer_id = ? ORDER BY email_id", (cid,))]


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    with db._connect(p) as conn:
        conn.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,"
                     " first_name TEXT, last_name TEXT, phone TEXT,"
                     " phone_undeliverable INTEGER NOT NULL DEFAULT 0,"
                     " phone_undeliverable_at TIMESTAMP,"
                     " phone_undeliverable_reason TEXT)")
        conn.execute("""CREATE TABLE customer_emails (
            email_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL, email VARCHAR(200) NOT NULL,
            is_primary INTEGER NOT NULL DEFAULT 0,
            is_golf_genius INTEGER NOT NULL DEFAULT 0, label VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            undeliverable INTEGER NOT NULL DEFAULT 0,
            undeliverable_at TIMESTAMP, undeliverable_reason TEXT,
            UNIQUE(customer_id, email))""")
        conn.execute("""CREATE TABLE action_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT,
            from_name TEXT, summary TEXT, urgency TEXT, category TEXT,
            status TEXT NOT NULL DEFAULT 'open', customer_id INTEGER,
            completed_at TIMESTAMP, completed_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("CREATE TABLE customer_aliases (customer_name TEXT, "
                     "alias_type TEXT, alias_value TEXT)")
        conn.executemany(
            "INSERT INTO customers (customer_id, first_name, last_name, phone)"
            " VALUES (?,?,?,?)",
            [(161, "Hayden", "Cooper", "(737) 268-9959"),
             (9, "Two", "Address", "(210) 555-0000")])
        conn.executemany(
            "INSERT INTO customer_emails (customer_id, email, is_primary) "
            "VALUES (?,?,?)",
            [(161, "hayden@hdroofingandrepairs.com", 1),
             (9, "work@deadcompany.com", 1), (9, "personal@gmail.com", 0)])
        conn.commit()

    print("The Hayden case — one address, and it is gone")
    res = db.set_email_undeliverable(
        161, "hayden@hdroofingandrepairs.com",
        reason="left the company, no new address given", db_path=p)
    check("call succeeds", res.get("ok") and res["undeliverable"], res)
    rows = emails(p, 161)
    check("the row is NOT deleted — matching still works",
          len(rows) == 1 and rows[0]["email"] == "hayden@hdroofingandrepairs.com",
          rows)
    check("it is flagged undeliverable and no longer primary",
          rows[0]["undeliverable"] == 1 and rows[0]["is_primary"] == 0, rows)
    check("the resolver refuses to hand it out",
          db.resolve_player_email({"customer_id": 161}, db_path=p) == "",
          db.resolve_player_email({"customer_id": 161}, db_path=p))
    check("resolving does not resurrect it as primary",
          emails(p, 161)[0]["is_primary"] == 0, emails(p, 161))
    check("the call reports there is nothing left to reach them on",
          res["no_deliverable_address"] is True and res["now_primary"] is None,
          res)
    with db._connect(p) as conn:
        ai = [dict(r) for r in conn.execute(
            "SELECT subject, summary, urgency FROM action_items")]
    check("an action item says so — silence is the failure mode here",
          len(ai) == 1 and "Hayden Cooper" in ai[0]["subject"]
          and "SKIP" in ai[0]["summary"], ai)
    check("while the phone still works it is medium, not high, and says so",
          ai[0]["urgency"] == "medium" and "no email address" in ai[0]["summary"]
          and "no usable phone" not in ai[0]["summary"], ai[0])
    db.set_email_undeliverable(161, "hayden@hdroofingandrepairs.com",
                               reason="again", db_path=p)
    with db._connect(p) as conn:
        n = conn.execute("SELECT COUNT(*) c FROM action_items").fetchone()["c"]
    check("marking it twice does not raise a second item", n == 1, n)

    print("A live address survives")
    res2 = db.set_email_undeliverable(9, "work@deadcompany.com",
                                      reason="changed jobs", db_path=p)
    check("the other address is promoted in its place",
          res2["now_primary"] == "personal@gmail.com"
          and res2["no_deliverable_address"] is False, res2)
    check("and the resolver hands out the live one",
          db.resolve_player_email({"customer_id": 9}, db_path=p)
          == "personal@gmail.com",
          db.resolve_player_email({"customer_id": 9}, db_path=p))
    with db._connect(p) as conn:
        n = conn.execute("SELECT COUNT(*) c FROM action_items").fetchone()["c"]
    check("no action item — they are still reachable", n == 1, n)

    print("The phone goes too — it was his work number")
    pr = db.set_phone_undeliverable(
        161, reason="work number at HD Roofing, no longer his", db_path=p)
    check("call succeeds", pr.get("ok") and pr["undeliverable"], pr)
    with db._connect(p) as conn:
        c = dict(conn.execute(
            "SELECT phone, phone_undeliverable, phone_undeliverable_reason "
            "FROM customers WHERE customer_id = 161").fetchone())
    check("the number is NOT wiped — old orders still match on it",
          c["phone"] == "(737) 268-9959" and c["phone_undeliverable"] == 1, c)
    check("the resolver refuses to hand it out",
          db.resolve_player_phone({"customer_id": 161}, db_path=p) == "",
          db.resolve_player_phone({"customer_id": 161}, db_path=p))
    with db._connect(p) as conn:
        ai = [dict(r) for r in conn.execute(
            "SELECT subject, summary, urgency, status FROM action_items "
            "WHERE subject LIKE '%Hayden%'")]
    check("still ONE item per person, not one per channel", len(ai) == 1, ai)
    check("it escalates to high once BOTH channels are gone",
          ai[0]["urgency"] == "high", ai[0])
    check("and it names both",
          "no email address" in ai[0]["summary"]
          and "no usable phone number" in ai[0]["summary"], ai[0]["summary"])

    print("Reachable again closes it")
    db.set_phone_undeliverable(161, undo=True, db_path=p)
    with db._connect(p) as conn:
        ai = dict(conn.execute(
            "SELECT urgency, summary, status FROM action_items "
            "WHERE subject LIKE '%Hayden%'").fetchone())
    check("restoring one channel drops it back to medium",
          ai["urgency"] == "medium" and ai["status"] == "open", ai)
    check("the phone resolves again",
          db.resolve_player_phone({"customer_id": 161}, db_path=p)
          == "(737) 268-9959")
    db.set_email_undeliverable(161, "hayden@hdroofingandrepairs.com",
                               undo=True, db_path=p)
    with db._connect(p) as conn:
        ai = dict(conn.execute(
            "SELECT status, completed_by FROM action_items "
            "WHERE subject LIKE '%Hayden%'").fetchone())
    check("with both channels back the item closes itself",
          ai["status"] == "completed" and ai["completed_by"] == "contact-watch",
          ai)
    # put him back where the earlier section left him
    db.set_email_undeliverable(161, "hayden@hdroofingandrepairs.com",
                               reason="left the company", db_path=p)

    print("Undo")
    r3 = db.set_email_undeliverable(161, "HAYDEN@HDRoofingAndRepairs.com",
                                    undo=True, db_path=p)
    check("undo is case-insensitive on the address", r3.get("ok"), r3)
    check("the address is deliverable again",
          db.resolve_player_email({"customer_id": 161}, db_path=p)
          == "hayden@hdroofingandrepairs.com",
          db.resolve_player_email({"customer_id": 161}, db_path=p))

    print("Guards")
    check("an address not on the customer is refused",
          "error" in db.set_email_undeliverable(161, "nobody@x.com", db_path=p))
    check("missing arguments are refused",
          "error" in db.set_email_undeliverable(0, "", db_path=p))

    os.unlink(p)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        raise SystemExit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
