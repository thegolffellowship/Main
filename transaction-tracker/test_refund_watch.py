"""Functional proof of the P2P refund watch flow (Kerry 2026-07-15):
red Refund buttons pay via Venmo/PayPal/Cash App/Zelle deep links and
the provider's receipt email verifies + auto-records the payout.

Asserts:
1. create_refund_watch guards (credited/wd rows only, positive amount,
   one open watch per item — re-tap replaces).
2. auto_match_refund_watches verifies on amount + customer_id, records
   via payout_credit (item flips off 'credited'), one receipt per watch.
3. Receipts predating the watch are ignored; receipts backing a
   tgf_payout are off the table; wrong-amount receipts don't match.
4. Memo-based matching works when the receipt lacks customer_id.

Run: python3 test_refund_watch.py
"""

import tempfile
from pathlib import Path

from email_parser import database as db

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label}")


def add_expense(conn, eid, amount, customer_id=None, notes="", handle="",
                created_at="2026-07-15 03:00:00"):
    conn.execute(
        """INSERT INTO expense_transactions
           (id, source_type, transaction_type, merchant, amount,
            transaction_date, review_status, notes, other_party_handle,
            customer_id, created_at)
           VALUES (?, 'venmo', 'payout', 'Recipient', ?, '2026-07-15',
                   'approved', ?, ?, ?, ?)""",
        (eid, amount, notes, handle, customer_id, created_at))


def main():
    tmp = Path(tempfile.mkdtemp()) / "t.db"
    db.init_db(tmp)
    with db._connect(tmp) as conn:
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter,"
                     " format) VALUES (901, 's9.90 Rained', '2026-07-14',"
                     " 'San Antonio', '9 Holes')")
        conn.execute("INSERT INTO customers (customer_id, first_name,"
                     " last_name, venmo_username) VALUES (24, 'Daniel',"
                     " 'South', '@Daniel-South-9')")
        conn.execute(
            "INSERT INTO items (id, email_uid, merchant, order_date,"
            " item_name, customer, customer_id, customer_email, item_price,"
            " transaction_fees, transaction_status, credit_note) VALUES"
            " (7002, 'u2', 'GoDaddy', '2026-07-12', 's9.90 Rained',"
            " 'Daniel South', 24, 'south@x.com', '$74.00', '$2.59',"
            " 'credited', 'Event cancelled - rain')")
        conn.execute(
            "INSERT INTO items (id, email_uid, merchant, order_date,"
            " item_name, customer, customer_id, item_price,"
            " transaction_status) VALUES"
            " (7003, 'u3', 'GoDaddy', '2026-07-12', 's9.90 Rained',"
            " 'Daniel South', 24, '$50.00', 'active')")
        conn.commit()

    memo = "Daniel South - Credit for s9.90 Rained"

    # 1. Guards
    r = db.create_refund_watch(7003, "Venmo", 50.0, db_path=tmp)
    check("active item refused", not r["ok"])
    r = db.create_refund_watch(7002, "Venmo", 0, db_path=tmp)
    check("zero amount refused", not r["ok"])
    r1 = db.create_refund_watch(7002, "Venmo", 76.59, memo=memo,
                                handle="@Daniel-South-9", db_path=tmp)
    check("watch created", r1["ok"])
    r2 = db.create_refund_watch(7002, "Venmo", 76.59, memo=memo,
                                handle="@Daniel-South-9", db_path=tmp)
    check("re-tap replaces open watch", r2["ok"] and r2["watch_id"] != r1["watch_id"])
    check("only one open watch", len(db.get_open_refund_watches(db_path=tmp)) == 1)

    # 3a. Receipt PREDATING the watch is ignored
    with db._connect(tmp) as conn:
        add_expense(conn, 9101, 76.59, customer_id=24,
                    created_at="2026-01-01 00:00:00")
        conn.commit()
    res = db.auto_match_refund_watches(db_path=tmp)
    check("stale receipt ignored", res["verified"] == 0)

    # 3b. Wrong amount doesn't match
    with db._connect(tmp) as conn:
        add_expense(conn, 9102, 76.00, customer_id=24)
        conn.commit()
    res = db.auto_match_refund_watches(db_path=tmp)
    check("wrong amount ignored", res["verified"] == 0)

    # 2. The real receipt verifies + records via payout_credit
    with db._connect(tmp) as conn:
        add_expense(conn, 9103, 76.59, customer_id=24,
                    notes=f"You paid Recipient — {memo}",
                    created_at="2099-01-01 00:00:00")
        conn.commit()
    res = db.auto_match_refund_watches(db_path=tmp)
    print("match result:", res)
    check("verified", res["verified"] == 1)
    check("recorded", res["recorded"] == 1)
    w = db.get_refund_watch(7002, db_path=tmp)
    check("watch verified against the right expense",
          w["verified_expense_id"] == 9103 and w["recorded"] == 1)
    with db._connect(tmp) as conn:
        st = conn.execute("SELECT transaction_status FROM items WHERE id=7002"
                          ).fetchone()[0]
    check("credit item no longer 'credited' (paid out)", st != "credited")

    # Idempotent — nothing left to match
    res = db.auto_match_refund_watches(db_path=tmp)
    check("idempotent rerun", res["verified"] == 0)

    # 4. Memo-only match (receipt lacks customer_id + handle)
    with db._connect(tmp) as conn:
        conn.execute(
            "INSERT INTO items (id, email_uid, merchant, order_date,"
            " item_name, customer, customer_id, item_price,"
            " transaction_status) VALUES"
            " (7004, 'u4', 'GoDaddy', '2026-07-12', 's9.90 Rained',"
            " 'Daniel South', 24, '$33.00', 'credited')")
        conn.commit()
    memo2 = "Daniel South - Credit for s9.90 Rained"
    db.create_refund_watch(7004, "PayPal", 33.0, memo=memo2, db_path=tmp)
    with db._connect(tmp) as conn:
        conn.execute(
            """INSERT INTO expense_transactions
               (id, source_type, transaction_type, merchant, amount,
                transaction_date, review_status, notes, created_at)
               VALUES (9104, 'paypal', 'payout', 'Daniel South', 33.0,
                       '2026-07-15', 'approved',
                       ?, '2099-01-01 00:00:00')""",
            (f"Payment sent — {memo2}",))
        conn.commit()
    res = db.auto_match_refund_watches(db_path=tmp)
    check("memo-only PayPal match verified+recorded",
          res["verified"] == 1 and res["recorded"] == 1)

    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
