"""A TRANSFER carries a price check (Kerry 2026-09-22: "I transferred Don
SHARITZ and Pat YOUNGS to next week's s9.25 CANYON SPRINGS event, but
surely there's a price difference either for or against, but I'm not
seeing any information about that in the CREDIT / TRANSFER modal").

Run: python3 test_transfer_price.py
"""
import os, sqlite3, sys, tempfile, contextlib, io, logging
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
logging.getLogger("email_parser.database").setLevel(logging.ERROR)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-xfer-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
c = sqlite3.connect(tmp); c.row_factory = sqlite3.Row
for eid, nm, cc in ((3309, "s9.24 Brackenridge", 43.99), (3304, "s9.25 Canyon Springs", 54.13), (3307, "s9.27 The Quarry", 42.22)):
    c.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, course_cost, tgf_markup, side_game_fee, transaction_fee_pct) "
              "VALUES (?, ?, '2026-09-29', 'San Antonio', 'active', '9 Holes', ?, 8.0, 7.0, 3.5)", (eid, nm, cc))
c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, account_status, venmo_username) VALUES (136, 'Pat', 'Youngs', 'San Antonio', 'active', 'Pat-Youngs')")
src = db._calc_event_pricing_breakdown({"format": "9 Holes", "course_cost": 43.99, "tgf_markup": 8.0, "side_game_fee": 7.0, "transaction_fee_pct": 3.5}, "MEMBER", "9", "NET")
c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status, event_id, holes, side_games, user_status, tee_choice, item_price) "
          "VALUES (900, 'u900', 'GoDaddy', 'Pat Youngs', 136, 's9.24 Brackenridge', '2026-09-10', 'active', 3309, '9', 'NET', 'MEMBER', '50-64', ?)", (f"${src['total']:.2f}",))
c.commit()
paid = round(src["total"], 2)

print("\n== the preview says what the move costs ==")
cs = db._calc_event_pricing_breakdown(dict(c.execute("SELECT * FROM events WHERE id = 3304").fetchone()), "MEMBER", "9", "NET")
pv = db.transfer_preview(900, "s9.25 Canyon Springs", db_path=tmp)
check("credit = what was paid at the source", pv["credit"] == paid, str(pv))
check("the target's SUBTOTAL for the same package (member, 9, NET) is the cost — no card fee on a Venmo difference",
      pv["target_subtotal"] == cs["subtotal"] and pv["selections"]["side_games"] == "NET", str(pv))
check("Canyon Springs is dearer → the player OWES the difference",
      pv["amount_owed"] == round(cs["subtotal"] - paid, 2) and pv["amount_owed"] > 0 and pv["excess"] == 0.0, str(pv))
check("the Venmo handle rides along for the options", pv["venmo_username"] == "Pat-Youngs")
qv = db.transfer_preview(900, "s9.27 The Quarry", db_path=tmp)
qs = db._calc_event_pricing_breakdown(dict(c.execute("SELECT * FROM events WHERE id = 3307").fetchone()), "MEMBER", "9", "NET")
check("The Quarry is cheaper → EXCESS", qv["amount_owed"] < 0 and qv["excess"] == round(paid - qs["subtotal"], 2), str(qv))
check("an unknown target cannot be priced and says so", db.transfer_preview(900, "nowhere", db_path=tmp)["can_calculate"] is False)

print("\n== the transfer settles the difference ==")
new = db.transfer_item(900, "s9.25 Canyon Springs", db_path=tmp)
pc = new["price_check"]
check("a SHORT transfer stamps balance_due on the new row (the Venmo email reads it)",
      pc["amount_owed"] == pv["amount_owed"]
      and c.execute("SELECT credit_note FROM items WHERE id = ?", (new["id"],)).fetchone()[0] == f"balance_due:{pv['amount_owed']:.2f}", str(pc))
check("...and the moved row carries the full credit", c.execute("SELECT item_price FROM items WHERE id = ?", (new["id"],)).fetchone()[0] == f"${paid:.2f} (credit)")
# Now the other way: a second paid row moved to the cheaper event.
c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status, event_id, holes, side_games, user_status, item_price) "
          "VALUES (950, 'u950', 'GoDaddy', 'Pat Youngs', 136, 's9.24 Brackenridge', '2026-09-10', 'active', 3309, '9', 'NET', 'MEMBER', ?)", (f"${paid:.2f}",))
c.commit()
new2 = db.transfer_item(950, "s9.27 The Quarry", db_path=tmp, excess_action="keep")
pc2 = new2["price_check"]
row2 = c.execute("SELECT item_price, credit_note FROM items WHERE id = ?", (new2["id"],)).fetchone()
check("an EXCESS transfer prices the new row at the target's subtotal",
      row2["item_price"] == f"${qs['subtotal']:.2f} (credit)" and "excess to credit" in row2["credit_note"], str(dict(row2)))
ex = c.execute("SELECT * FROM items WHERE id = ?", (pc2["excess_credit_id"],)).fetchone()
check("...and posts the leftover as an 'Excess credit — <source>' row in the player's pool",
      ex is not None and ex["transaction_status"] == "credited" and ex["item_price"] == f"${pc2['excess']:.2f}"
      and ex["item_name"] == "Excess credit — s9.24 Brackenridge" and ex["customer_id"] == 136, str(dict(ex)) if ex else "none")
check("...which the credit pool sees", any(cr["id"] == pc2["excess_credit_id"] for cr in db.get_player_credits("Pat Youngs", customer_id=136, db_path=tmp)))

print("\n== credit already on the account goes toward the move (Sharitz's $6) ==")
c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status, item_price, credit_note) "
          "VALUES (960, 'credit-excess-old', 'Manual Entry', 'Pat Youngs', 136, 'Excess credit — s9.22 Silverhorn', '2026-09-08', 'credited', '$6.00', 'Excess credit from transfer — $6.00 remaining')")
c.execute("INSERT INTO items (id, email_uid, merchant, customer, customer_id, item_name, order_date, transaction_status, event_id, holes, side_games, user_status, item_price) "
          "VALUES (961, 'u961', 'GoDaddy', 'Pat Youngs', 136, 's9.24 Brackenridge', '2026-09-10', 'active', 3309, '9', 'NET', 'MEMBER', ?)", (f"${paid:.2f}",))
c.commit()
pv3 = db.transfer_preview(961, "s9.25 Canyon Springs", db_path=tmp)
check("the preview lists the $6.00 sitting on the account, for the manager to tick",
      (960, 6.0) in [(a["id"], a["amount"]) for a in pv3["available_credits"]]
      and pv3["available_credits_total"] == round(sum(a["amount"] for a in pv3["available_credits"]), 2), str(pv3["available_credits"]))
new3 = db.transfer_item(961, "s9.25 Canyon Springs", db_path=tmp, apply_credit_ids=[960])
pc3 = new3["price_check"]
check("ticked: the $6 joins the credit and the balance due drops by it",
      pc3["credits_applied"] == 6.0 and pc3["credit"] == round(paid + 6.0, 2)
      and pc3["amount_owed"] == round(pv3["amount_owed"] - 6.0, 2)
      and c.execute("SELECT credit_note FROM items WHERE id = ?", (new3["id"],)).fetchone()[0] == f"balance_due:{pc3['amount_owed']:.2f}", str(pc3))
check("...the credit row is consumed the way Apply Credit consumes one",
      c.execute("SELECT transaction_status, transferred_to_id FROM items WHERE id = 960").fetchone()[:] == ("transferred", new3["id"]))
check("...and the moved row carries the combined credit", c.execute("SELECT item_price FROM items WHERE id = ?", (new3["id"],)).fetchone()[0] == f"${paid + 6.0:.2f} (credit)")
check("a credit that is not this player's is ignored", db.transfer_preview(961, "s9.25 Canyon Springs", db_path=tmp) is not None)
check("reverse puts the $6 back on the account",
      db.reverse_credit(961, db_path=tmp)
      and c.execute("SELECT transaction_status, transferred_to_id FROM items WHERE id = 960").fetchone()[:] == ("credited", None)
      and any(cr["id"] == 960 and cr["credit_amount"] == 6.0 for cr in db.get_player_credits("Pat Youngs", customer_id=136, db_path=tmp)))

print("\n== undoing the transfer undoes the price check ==")
check("reverse: the moved row goes, and the unapplied excess-credit row goes with it",
      db.reverse_credit(950, db_path=tmp)
      and c.execute("SELECT COUNT(*) FROM items WHERE id IN (?, ?)", (new2["id"], pc2["excess_credit_id"])).fetchone()[0] == 0
      and c.execute("SELECT transaction_status FROM items WHERE id = 950").fetchone()[0] == "active")
check("reverse of a SHORT transfer restores the original (nothing else to clean)",
      db.reverse_credit(900, db_path=tmp) and c.execute("SELECT COUNT(*) FROM items WHERE id = ?", (new["id"],)).fetchone()[0] == 0)

print("\n" + ("ALL PASSED" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
