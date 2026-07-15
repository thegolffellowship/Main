"""Proof of get_refunds_overview() — the consolidated REFUNDS console
(Kerry 2026-07-15): OUTSTANDING / IN FLIGHT / COMPLETED, one place.

Asserts:
1. OUTSTANDING lists WD credits (credit_amount) + standalone credited rows
   (item_price), positive only, oldest first.
2. A credit with an OPEN watch is excluded from OUTSTANDING and appears in
   IN FLIGHT instead.
3. COMPLETED parses the 'Refunded $X via M on DATE' stamp; rows older than
   the window are dropped; newest first.
4. Totals sum each bucket.

Run: python3 test_refunds_overview.py
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


def main():
    tmp = Path(tempfile.mkdtemp()) / "t.db"
    db.init_db(tmp)
    with db._connect(tmp) as conn:
        db._ensure_refund_watch_table(conn)
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter,"
                     " format) VALUES (700, 's9.70 Rained', '2026-07-10',"
                     " 'San Antonio', '9 Holes')")
        for cid, fn, ln in ((40, 'Amy', 'Alpha'), (41, 'Ben', 'Bravo'),
                            (42, 'Cy', 'Charlie'), (43, 'Dee', 'Delta'),
                            (44, 'Ed', 'Echo')):
            conn.execute("INSERT INTO customers (customer_id, first_name,"
                         " last_name) VALUES (?,?,?)", (cid, fn, ln))

        def item(iid, cust, cid, status, price=None, credamt=None,
                 order_date='2026-07-10', note=None):
            conn.execute(
                "INSERT INTO items (id, email_uid, item_index, merchant,"
                " order_date, item_name, customer, customer_id, item_price,"
                " credit_amount, transaction_status, credit_note) VALUES"
                " (?,?,0,'GoDaddy',?,'s9.70 Rained',?,?,?,?,?,?)",
                (iid, f"u{iid}", order_date, cust, cid, price, credamt,
                 status, note))

        # OUTSTANDING: WD credit + standalone credited (different ages)
        item(7101, 'Amy Alpha', 40, 'wd', credamt='$74.00',
             order_date='2026-07-01')                    # oldest
        item(7102, 'Ben Bravo', 41, 'credited', price='$25.00',
             order_date='2026-07-08')                    # newer
        item(7103, 'Cy Charlie', 42, 'credited', price='$0.00')   # zero -> skip
        # IN FLIGHT: a credited row that also has an open watch -> not outstanding
        item(7104, 'Dee Delta', 43, 'credited', price='$50.00',
             order_date='2026-07-05')
        conn.execute(
            "INSERT INTO refund_watches (item_id, customer_id, customer_name,"
            " method, handle, amount, memo, initiated_at) VALUES"
            " (7104, 43, 'Dee Delta', 'Venmo', 'dee-d', 50.00,"
            " 'Dee Delta - Credit from s9.70 Rained', '2026-07-14 10:00:00')")
        # COMPLETED: one recent, one too old (beyond 120d window)
        item(7105, 'Ed Echo', 44, 'refunded', price='$30.00',
             note='Refunded $30.00 via Venmo on 2026-07-13 — rain credit')
        item(7106, 'Ed Echo', 44, 'refunded', price='$12.00',
             note='Refunded $12.00 via Check on 2025-01-01')
        conn.commit()

    ov = db.get_refunds_overview(tmp, completed_days=120)
    out = ov["outstanding"]
    inf = ov["in_flight"]
    comp = ov["completed"]

    check("OUTSTANDING has 2 (WD + credited, zero+in-flight excluded)",
          len(out) == 2)
    ids = [o["item_id"] for o in out]
    check("OUTSTANDING excludes zero-amount 7103", 7103 not in ids)
    check("OUTSTANDING excludes in-flight 7104", 7104 not in ids)
    check("OUTSTANDING oldest first (7101 before 7102)",
          ids == [7101, 7102])
    check("OUTSTANDING WD amount read from credit_amount",
          any(o["item_id"] == 7101 and o["amount"] == 74.00 for o in out))

    check("IN FLIGHT has the open watch", len(inf) == 1 and inf[0]["item_id"] == 7104)
    check("IN FLIGHT carries method + event", inf[0]["method"] == "Venmo"
          and inf[0]["event"] == "s9.70 Rained")

    check("COMPLETED has 1 (old one dropped)", len(comp) == 1)
    check("COMPLETED parsed amount/method/date",
          comp[0]["amount"] == 30.00 and comp[0]["method"] == "Venmo"
          and comp[0]["date"] == "2026-07-13")

    t = ov["totals"]
    check("totals outstanding_amount = 99.00", t["outstanding_amount"] == 99.00)
    check("totals in_flight_amount = 50.00", t["in_flight_amount"] == 50.00)
    check("totals completed_amount = 30.00", t["completed_amount"] == 30.00)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
