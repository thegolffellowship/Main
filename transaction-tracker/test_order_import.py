"""Date-range order import: de-dup, membership filter, pipeline, no member
email. Run: python3 test_order_import.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import database as db  # noqa: E402
from email_parser import order_import as oi  # noqa: E402

FAILS = 0


def check(label, cond, detail=""):
    global FAILS
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  -> {detail}"))
    if not cond:
        FAILS += 1


EMAILS = [
    {"uid": "u1", "subject": "New Order #R100000001", "date": "2025-08-05T10:00:00Z",
     "text": "New order from: Aug Member (210) 555-0100 | aug@example.com TGF MEMBERSHIP RETURNING or NEW?: NEW $50.00 Order: R100000001"},
    {"uid": "u2", "subject": "New Order #R100000002", "date": "2025-09-02T10:00:00Z",
     "text": "s9.30 THE QUARRY MEMBER $74.00 Order: R100000002"},
    {"uid": "u3-rekeyed", "subject": "New Order #R100000003", "date": "2025-10-01T10:00:00Z",
     "text": "TGF MEMBERSHIP already in tracker"},
]


def fake_fetch(_from, _to):
    return list(EMAILS)


def fake_parse(email):
    oid = email["subject"].split("#")[1]
    if "MEMBERSHIP" in email["text"]:
        return [{"email_uid": email["uid"], "item_index": 0, "merchant": "The Golf Fellowship",
                 "customer": "Aug Member", "first_name": "Aug", "last_name": "Member",
                 "customer_email": "aug@example.com", "order_id": oid,
                 "order_date": email["date"][:10], "total_amount": "$51.75",
                 "item_name": "TGF MEMBERSHIP", "item_price": "$50.00", "quantity": 1,
                 "returning_or_new": "New", "transaction_fees": "$1.75",
                 "subject": email["subject"], "from_addr": "noreply@mysimplestore.com"}]
    return [{"email_uid": email["uid"], "item_index": 0, "merchant": "The Golf Fellowship",
             "customer": "Sep Player", "first_name": "Sep", "last_name": "Player",
             "customer_email": "sep@example.com", "order_id": oid,
             "order_date": email["date"][:10], "total_amount": "$76.59",
             "item_name": "s9.30 THE QUARRY", "item_price": "$74.00", "quantity": 1,
             "user_status": "MEMBER", "transaction_fees": "$2.59",
             "subject": email["subject"], "from_addr": "noreply@mysimplestore.com"}]


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    os.environ["DATABASE_PATH"] = p
    db.init_db(p)
    with db._connect(p) as conn:      # R100000003 is already here under an OLD uid
        conn.execute("INSERT INTO items (email_uid, item_index, merchant, customer, order_id, "
                     "item_name, item_price, order_date, transaction_status) VALUES "
                     "('u3-old', 0, 'The Golf Fellowship', 'Old Member', 'R100000003', "
                     "'TGF MEMBERSHIP', '$50.00', '2025-10-01', 'active')")
        conn.commit()

    print("Preview")
    pv = oi.preview("2025-08-01", "2025-12-28", db_path=p, fetch=fake_fetch)
    check("finds 3, one already in the Tracker by ORDER NUMBER despite a new message id",
          pv["found"] == 3 and pv["already_in_tracker"] == 1 and pv["new"] == 2, pv)
    check("counts the memberships among the new ones", pv["new_memberships"] == 1, pv)
    check("flags the membership whose buyer has no 2026 renewal in the Tracker",
          pv["memberships_without_2026_renewal"] == 1
          and pv["memberships_without_2026_renewal_list"] == ["2025-08-05 aug@example.com"], pv)
    check("by month", pv["by_month"] == {"2025-08": 1, "2025-09": 1}, pv["by_month"])
    pv2 = oi.preview("2025-08-01", "2025-12-28", membership_only=True, db_path=p, fetch=fake_fetch)
    check("membership-only filters the event order out", pv2["new"] == 1 and pv2["filtered_out"] == 1, pv2)
    with db._connect(p) as conn:
        n = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    check("preview wrote nothing", n == 1, n)

    print("Apply (foreground for the test)")
    st = oi.start("2025-08-01", "2025-12-28", db_path=p, fetch=fake_fetch, parse=fake_parse,
                  background=False)
    check("parsed 2, saved 2 items, done", st["parsed"] == 2 and st["items_saved"] == 2
          and st["message"] == "done" and st["running"] is False, st)
    with db._connect(p) as conn:
        rows = conn.execute("SELECT order_id, item_name FROM items ORDER BY id").fetchall()
        proc = conn.execute("SELECT COUNT(*) FROM processed_emails WHERE email_uid IN ('u1','u2')").fetchone()[0]
        terms = conn.execute("SELECT notice_30d_sent_at, notice_lapsed_sent_at, confirmation_sent_at "
                             "FROM customer_memberships").fetchall()
    check("both new orders landed, the known one was not duplicated",
          [r[0] for r in rows] == ["R100000003", "R100000001", "R100000002"], rows)
    check("both emails marked processed", proc == 2, proc)
    check("the imported membership term carries suppressed notices — no member email",
          len(terms) >= 1 and all(t[0] == oi.SUPPRESSED and t[1] == oi.SUPPRESSED
                                  and t[2] == oi.SUPPRESSED for t in terms), terms)
    st2 = oi.start("2025-08-01", "2025-12-28", db_path=p, fetch=fake_fetch, parse=fake_parse,
                   background=False)
    check("a second run is a no-op (everything already in the Tracker)",
          st2["new"] == 0 and st2["items_saved"] == 0, st2)
    os.unlink(p)
    print()
    print("ALL PASS" if not FAILS else f"{FAILS} FAILED")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
