"""Proof of the inbound balance-due MEMO fallback (Kerry 2026-07-15):
when a player's spouse pays their balance due from the spouse's own Venmo,
the payer's handle/name doesn't resolve — but the balance-due link we
emailed the player prefills the memo with the PLAYER's name, so the matcher
reads the memo and ties the payment back to the right open balance.

Asserts:
1. Unknown payer + memo naming the player + matching amount -> auto-matched
   (parent flips to paid_at, +PAY child carries [memo-match], expense stamped).
2. Memo WITHOUT the player's name -> no_candidate (no misfire).
3. Right memo name but wrong amount -> no match.
4. Single first-name token in memo -> no match (full name required).
5. Known handle still resolves via handle, not memo (regression).

Run: python3 test_inbound_memo_match.py
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


def add_balance_item(conn, item_id, name, cid, event, owed):
    conn.execute(
        "INSERT INTO items (id, email_uid, item_index, merchant, order_date,"
        " item_name, customer, customer_id, item_price, transaction_status,"
        " credit_note) VALUES (?, ?, 0, 'Paid Separately (Credit Transfer)',"
        " '2026-07-12', ?, ?, ?, ?, 'active', ?)",
        (item_id, f"bd-{item_id}", event, name, cid, f"${owed:.2f}",
         f"balance_due:{owed:.2f}"))


def add_inbound(conn, eid, amount, merchant, notes="", handle=""):
    conn.execute(
        "INSERT INTO expense_transactions (id, source_type, transaction_type,"
        " merchant, amount, transaction_date, review_status, notes,"
        " other_party_handle, created_at) VALUES (?, 'venmo', 'received', ?, ?,"
        " '2026-07-15', 'approved', ?, ?, '2026-07-15 12:00:00')",
        (eid, merchant, amount, notes, handle))


def paid(conn, item_id):
    row = conn.execute("SELECT credit_note FROM items WHERE id = ?",
                       (item_id,)).fetchone()
    return (row["credit_note"] or "").startswith("paid_at:")


def child_memo_match(conn, parent_id):
    row = conn.execute(
        "SELECT notes FROM items WHERE parent_item_id = ? LIMIT 1",
        (parent_id,)).fetchone()
    return bool(row) and "[memo-match]" in (row["notes"] or "")


def main():
    tmp = Path(tempfile.mkdtemp()) / "t.db"
    db.init_db(tmp)
    with db._connect(tmp) as conn:
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter,"
                     " format) VALUES (880, 's18.8 Vaaler Creek', '2026-07-16',"
                     " 'San Antonio', '18 Holes')")
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter,"
                     " format) VALUES (881, 's18.9 Silverhorn', '2026-07-18',"
                     " 'San Antonio', '18 Holes')")
        # Richard: pays via spouse (no handle on file for the spouse)
        conn.execute("INSERT INTO customers (customer_id, first_name,"
                     " last_name) VALUES (30, 'Richard', 'Palacios')")
        add_balance_item(conn, 8001, "Richard Palacios", 30,
                         "s18.8 Vaaler Creek", 45.00)
        # Larry: known handle, for the regression case
        conn.execute("INSERT INTO customers (customer_id, first_name,"
                     " last_name, venmo_username) VALUES (31, 'Larry',"
                     " 'Anthis', 'Larry-Anthis-7')")
        add_balance_item(conn, 8002, "Larry Anthis", 31,
                         "s18.9 Silverhorn", 60.00)
        conn.commit()

    # 2. Memo WITHOUT the name -> no match (run first, before 8001 is settled)
    with db._connect(tmp) as conn:
        add_inbound(conn, 9002, 45.00, "Someone Else",
                    notes="here you go", handle="rando-1")
        conn.commit()
    r = db.auto_match_venmo_inbound_to_balance_due([9002], tmp)
    check("no name in memo -> not matched", r["matched"] == 0)
    with db._connect(tmp) as conn:
        check("2: 8001 still open", not paid(conn, 8001))

    # 3. Right name, wrong amount -> no match
    with db._connect(tmp) as conn:
        add_inbound(conn, 9003, 20.00, "Wife Palacios",
                    notes="Richard Palacios - Balance due for s18.8 Vaaler Creek",
                    handle="wife-p")
        conn.commit()
    r = db.auto_match_venmo_inbound_to_balance_due([9003], tmp)
    check("wrong amount -> not matched", r["matched"] == 0)

    # 4. First name only -> no match (full name required)
    with db._connect(tmp) as conn:
        add_inbound(conn, 9004, 45.00, "Wife Palacios",
                    notes="from Richard", handle="wife-p")
        conn.commit()
    r = db.auto_match_venmo_inbound_to_balance_due([9004], tmp)
    check("first-name-only memo -> not matched", r["matched"] == 0)

    # 1. The real case: unknown payer, full name in memo, amount matches
    with db._connect(tmp) as conn:
        add_inbound(conn, 9001, 45.00, "Wife Palacios",
                    notes="Richard Palacios - Balance due for s18.8 Vaaler Creek",
                    handle="wife-p")
        conn.commit()
    r = db.auto_match_venmo_inbound_to_balance_due([9001], tmp)
    check("1: spouse memo -> matched", r["matched"] == 1)
    with db._connect(tmp) as conn:
        check("1: parent flipped to paid_at", paid(conn, 8001))
        check("1: +PAY child carries [memo-match]", child_memo_match(conn, 8001))
        mid = conn.execute("SELECT matched_item_id FROM expense_transactions"
                           " WHERE id = 9001").fetchone()["matched_item_id"]
        check("1: expense stamped matched_item_id", bool(mid))

    # 5. Regression: known handle resolves via handle (generic memo)
    with db._connect(tmp) as conn:
        add_inbound(conn, 9005, 60.00, "LA",
                    notes="thanks", handle="Larry-Anthis-7")
        conn.commit()
    r = db.auto_match_venmo_inbound_to_balance_due([9005], tmp)
    check("5: known handle -> matched", r["matched"] == 1)
    with db._connect(tmp) as conn:
        check("5: Larry balance flipped to paid", paid(conn, 8002))
        # handle path, NOT memo path
        check("5: not tagged memo-match", not child_memo_match(conn, 8002))

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
