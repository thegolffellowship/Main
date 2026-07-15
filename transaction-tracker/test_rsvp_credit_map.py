"""Regression proof for the mis-matched-RSVP credit bug (2026-07-15).

Live case: Daniel South held a $74 rain-out credit; his Vaaler Creek
RSVP was pinned by the first-name matcher to Daniel LEHAN's active
purchase. The frontend's email-mismatch guard re-displayed him as his
own row, but the backend credit map lacked that branch, so his Credit
badge vanished — and the per-rsvp credit lookup resolved the player
THROUGH the matched item, i.e. the WRONG person's credits.

Asserts:
1. get_event_rsvp_credit_map includes a PLAYING rsvp whose matched item
   is active but carries a different email (frontend parity), resolved
   to the rsvp's own customer_id.
2. get_rsvp_credit_info resolves the rsvp's own customer (South), never
   the matched item's owner (Lehan), and lists only South's credit items.
3. A correctly-matched rsvp (same email) stays excluded from the map.

Run: python3 test_rsvp_credit_map.py
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
            "INSERT INTO events (id, item_name, event_date, chapter, format,"
            " course_cost, tgf_markup, side_game_fee, transaction_fee_pct)"
            " VALUES (900, 's18.9 Testfall', '2026-07-25', 'San Antonio',"
            " '18 Holes', 90, 15, 14, 3.5)")
        conn.execute(
            "INSERT INTO events (id, item_name, event_date, chapter, format)"
            " VALUES (901, 's9.90 Rained', '2026-07-14', 'San Antonio',"
            " '9 Holes')")
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name)"
                     " VALUES (24, 'Daniel', 'South')")
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name)"
                     " VALUES (27, 'Daniel', 'Lehan')")
        conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary)"
                     " VALUES (24, 'south@x.com', 1)")
        conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary)"
                     " VALUES (27, 'lehan@x.com', 1)")
        # Lehan's ACTIVE purchase of the new event
        conn.execute(
            "INSERT INTO items (id, email_uid, merchant, order_date, item_name,"
            " customer, customer_id, customer_email, item_price,"
            " transaction_status) VALUES"
            " (7001, 'u1', 'GoDaddy', '2026-06-30', 's18.9 Testfall',"
            " 'Daniel Lehan', 27, 'lehan@x.com', '$122.00', 'active')")
        # South's rain-out CREDIT
        conn.execute(
            "INSERT INTO items (id, email_uid, merchant, order_date, item_name,"
            " customer, customer_id, customer_email, item_price,"
            " transaction_fees, transaction_status, credit_note, holes,"
            " side_games, tee_choice, user_status) VALUES"
            " (7002, 'u2', 'GoDaddy', '2026-07-12', 's9.90 Rained',"
            " 'Daniel South', 24, 'south@x.com', '$74.00', '$2.59',"
            " 'credited', 'Event cancelled - rain', '9', 'NONE', '50-64',"
            " 'MEMBER')")
        # South's rsvp for the NEW event, MIS-MATCHED to Lehan's item
        conn.execute(
            "INSERT INTO rsvps (id, email_uid, player_name, player_email,"
            " gg_event_name, event_identifier, event_date, response,"
            " received_at, matched_event, matched_item_id, customer_id) VALUES"
            " (501, 'r1', 'Daniel', 'south@x.com', 'TGF - s18.9', 's18.9',"
            " '2026-07-25', 'PLAYING', '2026-07-15T02:07:13Z',"
            " 's18.9 Testfall', 7001, 24)")
        # Lehan's own rsvp, CORRECTLY matched (same email) — must stay excluded
        conn.execute(
            "INSERT INTO rsvps (id, email_uid, player_name, player_email,"
            " gg_event_name, event_identifier, event_date, response,"
            " received_at, matched_event, matched_item_id, customer_id) VALUES"
            " (502, 'r2', 'Daniel', 'lehan@x.com', 'TGF - s18.9', 's18.9',"
            " '2026-07-25', 'PLAYING', '2026-07-10T00:00:00Z',"
            " 's18.9 Testfall', 7001, 27)")
        conn.commit()

    m = db.get_event_rsvp_credit_map("s18.9 Testfall", db_path=tmp)
    print("credit map keys:", sorted(m))
    check("badge map includes mis-matched Daniel South", "Daniel South" in m)
    if "Daniel South" in m:
        check("total credit = $76.59 (price + tx fee)",
              abs(m["Daniel South"]["total_credit"] - 76.59) < 0.01)
        check("keyed to his rsvp id", m["Daniel South"]["rsvp_id"] == 501)
        check("only South's credit items",
              [c["item_id"] for c in m["Daniel South"]["credits"]] == [7002])
    check("correctly-matched active buyer (Lehan) NOT in map",
          "Daniel Lehan" not in m)

    info = db.get_rsvp_credit_info(501, db_path=tmp)
    check("credit info resolves", info is not None)
    if info:
        print("credit info player:", info["player_name"],
              "total:", info["total_credit"])
        check("resolved to Daniel SOUTH, not the matched item's owner",
              info["player_name"] == "Daniel South")
        check("info total = $76.59", abs(info["total_credit"] - 76.59) < 0.01)
        check("credits are South's items only",
              all(c["item_id"] == 7002 for c in info["credits"]))

    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
