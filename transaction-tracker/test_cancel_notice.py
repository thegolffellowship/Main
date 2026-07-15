"""Functional proof of the one-tap cancellation notification plan
(Kerry-ratified 2026-07-14 after the s9.18 rain-out).

Covers plan_event_cancellation_notice():
1. Amounts come from ACTIVE parent items + their active add-on children.
2. A player with multiple parent items is ONE recipient with the summed total.
3. RSVP-only players land as kind='silent' with $0.
4. The plan is computed pre-credit; after crediting, the amounts a fresh
   plan would lose are exactly why the execute endpoint plans first —
   asserted by re-planning post-credit and seeing the player gone.

Run: python3 test_cancel_notice.py
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
        conn.execute(
            "INSERT INTO events (id, item_name, event_date, chapter, format)"
            " VALUES (700, 's9.96 Rainout', '2026-07-14', 'San Antonio', '9 Holes')")
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name)"
                     " VALUES (1, 'Rae', 'Paid')")
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name)"
                     " VALUES (2, 'Sol', 'Rsvp')")
        conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary)"
                     " VALUES (1, 'rae@example.com', 1)")
        conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary)"
                     " VALUES (2, 'sol@example.com', 1)")
        # Paid player: entry $52 + active add-on child $14 + a second
        # parent item $10 (separate order) = $76 total
        conn.execute(
            "INSERT INTO items (id, email_uid, merchant, order_date, item_name,"
            " customer, customer_id, item_price, transaction_status) VALUES"
            " (9001, 'u1', 'GoDaddy', '2026-07-01', 's9.96 Rainout',"
            " 'Rae Paid', 1, '$52.00', 'active')")
        conn.execute(
            "INSERT INTO items (id, email_uid, merchant, order_date, item_name,"
            " customer, customer_id, item_price, transaction_status,"
            " parent_item_id) VALUES"
            " (9002, 'u2', 'GoDaddy', '2026-07-01', 's9.96 Rainout',"
            " 'Rae Paid', 1, '$14.00', 'active', 9001)")
        conn.execute(
            "INSERT INTO items (id, email_uid, merchant, order_date, item_name,"
            " customer, customer_id, item_price, transaction_status) VALUES"
            " (9003, 'u3', 'GoDaddy', '2026-07-02', 's9.96 Rainout',"
            " 'Rae Paid', 1, '$10.00', 'active')")
        # RSVP-only player (nothing owed, still notified)
        conn.execute(
            "INSERT INTO items (id, email_uid, merchant, order_date, item_name,"
            " customer, customer_id, item_price, transaction_status) VALUES"
            " (9004, 'u4', 'RSVP Only', '2026-07-03', 's9.96 Rainout',"
            " 'Sol Rsvp', 2, '', 'rsvp_only')")
        conn.commit()

    plan = db.plan_event_cancellation_notice(700, db_path=tmp)
    recs = {r["customer"]: r for r in plan["recipients"]}
    print("recipients:", [(r["customer"], r["kind"], r["amount"]) for r in plan["recipients"]])

    check("two recipients (one per player)", len(plan["recipients"]) == 2)
    rae = recs.get("Rae Paid")
    check("Rae is paid kind", rae and rae["kind"] == "paid")
    check("Rae total = $76.00 (entry + add-on child + second order)",
          rae and abs(rae["amount"] - 76.0) < 0.005)
    check("Rae email resolved canonically", rae and rae["email"] == "rae@example.com")
    check("Rae covers both parent items", rae and sorted(rae["item_ids"]) == [9001, 9003])
    sol = recs.get("Sol Rsvp")
    check("Sol is silent kind with $0", sol and sol["kind"] == "silent" and sol["amount"] == 0)
    check("paid_items excludes the add-on child", sorted(plan["paid_items"]) == [9001, 9003])
    # rsvp_only rows are NOTIFICATION recipients, not credit actions —
    # they never paid, so there is nothing to credit (silent_items covers
    # active comp/manual rows only, matching the legacy cancel behavior)
    check("no credit actions for the RSVP row", plan["silent_items"] == [])

    # Credit everything (what execute does after planning) and re-plan:
    # the amounts are gone — proving plan-before-credit is load-bearing.
    for iid in plan["silent_items"]:
        db.credit_item(iid, note="Event cancelled — test", db_path=tmp)
    for iid in plan["paid_items"]:
        db.credit_item(iid, note="Event cancelled — test", db_path=tmp)
    with db._connect(tmp) as conn:
        child = conn.execute("SELECT transaction_status FROM items WHERE id = 9002").fetchone()
        check("add-on child cascaded to credited", child["transaction_status"] == "credited")
    plan2 = db.plan_event_cancellation_notice(700, db_path=tmp)
    check("post-credit plan has lost the paid amounts (why we plan FIRST)",
          not [r for r in plan2["recipients"] if r["kind"] == "paid"])

    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
