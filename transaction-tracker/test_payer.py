"""THE PAYER OF AN ORDER (Kerry 2026-10-30: "Yes, build the payer field with
the migration" / "there's definitely a parent payer element that is
assigned"). Migration 0044, email_parser/payer.py.

The case is Jeff Young's order R293121452: his own spot ($80) plus a 1st
TIMER spot ($49) that Peter Rundqvist played. Jeff's partner request was
"Peter (guest from Mavn) & Pat". The $49 credit followed Peter.

Run: python3 test_payer.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-payer-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
from email_parser import database as db          # noqa: E402
from email_parser import parser as P             # noqa: E402
from email_parser import payer as pay            # noqa: E402
from email_parser import credit_buyer as cb      # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

db.init_db(DB)

print("\n== the migration ==")
with db._connect(DB) as c:
    check("items.payer_customer_id exists (0044)", pay.has_column(c))
check("the payer is NOT editable through update_item (not in ITEM_COLUMNS)",
      "payer_customer_id" not in db.ITEM_COLUMNS)

print("\n== the parser: a pairing request is not a guest's name ==")
check("\"Peter (guest from Mavn) & Pat\" is refused", P._single_guest_name("Peter (guest from Mavn) & Pat") == "")
check("\"Bob and Sue Smith\" is refused", P._single_guest_name("Bob and Sue Smith") == "")
check("one clean name passes", P._single_guest_name("Tanner Chalfant") == "Tanner Chalfant")
check("a parenthetical is dropped", P._single_guest_name("Mike Jones (guest)") == "Mike Jones")

hdr = {"name": "Jeff Young", "email": "jeffyoung54@gmail.com", "phone": "(210) 863-1245"}
base = dict(email_uid="uid-R1", order_id="R293121452", order_date="2026-10-24", merchant="The Golf Fellowship",
            customer="Jeff Young", customer_email="jeffyoung54@gmail.com", customer_phone="(210) 863-1245",
            item_name="s9.29 SILVERHORN", quantity=1, transaction_status="active", coupon_code="tgf-nobody",
            address="30135 Raven Ln", zip="78163", _payer=hdr)
rows = [dict(base, item_index=0, item_price="$80.00", user_status="MEMBER",
             partner_request="Peter (guest from Mavn) & Pat"),
        dict(base, item_index=1, item_price="$49.00", user_status="1st TIMER", partner_request="Jeff Y")]
rows = P._promote_guest_customers(rows)
check("the 1st TIMER line is held as \"Guest of Jeff Young\", not the request text",
      rows[1]["customer"] == "Guest of Jeff Young", rows[1]["customer"])
check("...marked Purchased by Jeff Young, with no email of its own",
      rows[1]["notes"] == "Purchased by Jeff Young" and not rows[1]["customer_email"])
check("Jeff's own line is untouched", rows[0]["customer"] == "Jeff Young")

print("\n== import stamps the payer from the order header ==")
with db._connect(DB) as c:
    c.execute("INSERT INTO events (item_name, event_date, course, chapter) "
              "VALUES ('s9.29 SILVERHORN', '2026-10-27', 'Silverhorn Golf Club of Texas', 'San Antonio')")
    c.commit()
rows[0]["course"] = "ShadowGlen"   # the parser's guess on the real order
db.save_items(rows, db_path=DB)
with db._connect(DB) as c:
    crs = [r[0] for r in c.execute("SELECT course FROM items WHERE order_id = 'R293121452' ORDER BY item_index")]
check("the course comes from the event, not the parser's guess",
      crs == ["Silverhorn Golf Club of Texas"] * 2, crs)
with db._connect(DB) as c:
    got = [dict(r) for r in c.execute(
        "SELECT id, customer, customer_id, payer_customer_id FROM items WHERE order_id = 'R293121452' ORDER BY item_index")]
jeff_cid = got[0]["customer_id"]
check("both lines carry the payer: Jeff", all(r["payer_customer_id"] == jeff_cid for r in got) and jeff_cid, got)

print("\n== Assign Guest names the player and cannot move the payer ==")
import app as appmod                                            # noqa: E402
appmod.app.config["TESTING"] = True
cl = appmod.app.test_client()
with cl.session_transaction() as s:
    s["role"] = "admin"
gid = got[1]["id"]
r = cl.post(f"/api/items/{gid}/assign-guest",
            json={"guest_name": "Peter Rundqvist", "guest_email": "peter@viewimaging.com"})
check("assign-guest ok", r.status_code == 200, r.get_data(as_text=True)[:200])
with db._connect(DB) as c:
    pr = dict(c.execute("SELECT * FROM items WHERE id = ?", (gid,)).fetchone())
check("the player is Peter", pr["customer"] == "Peter Rundqvist")
check("the note still names the buyer: Purchased by Jeff Young (not the old row text)",
      pr["notes"] == "Purchased by Jeff Young", pr["notes"])
check("the payer is still Jeff", pr["payer_customer_id"] == jeff_cid)

print("\n== a credit on Peter's spot goes to the payer ==")
with db._connect(DB) as c:
    b = cb.buyer_of(c, pr)
check("buyer_of -> Jeff, as payer of the order", b.get("buyer_id") == jeff_cid and "payer" in b.get("reason", ""), b)
with db._connect(DB) as c:
    b0 = cb.buyer_of(c, dict(c.execute("SELECT * FROM items WHERE id = ?", (got[0]["id"],)).fetchone()))
check("Jeff's own line credits Jeff (no move)", b0 == {}, b0)
check("an unmapped personal coupon no longer holds once the payer is stored",
      "hold" not in b, b)

print("\n== orders already in the Tracker: the backfill ==")
with db._connect(DB) as c:
    c.execute("UPDATE items SET payer_customer_id = NULL")
    # an order where a manager's edit left the guest with his own email
    c.execute("UPDATE items SET customer_email = 'peter@viewimaging.com', notes = 'Purchased by Peter & Pat' WHERE id = ?", (gid,))
    # an ambiguous order: two lines, two people, no billing address on either
    for i, (nm, em) in enumerate((("Ann One", "a@x.com"), ("Bob Two", "b@x.com"))):
        cid = db._resolve_or_create_customer(c, nm, em)
        c.execute("INSERT INTO items (email_uid, item_index, order_id, customer, customer_email, customer_id, item_name, merchant, order_date) "
                  "VALUES ('uid-R2', ?, 'R2', ?, ?, ?, 's9.29 SILVERHORN', 'The Golf Fellowship', '2026-10-24')", (i, nm, em, cid))
    c.commit()
dry = pay.backfill(apply=False, db_path=DB)
check("dry run writes nothing", not dry["applied"])
check("Jeff's order: the billing-address rule, even with Peter's email on his line",
      dry["by_rule"].get("billing address") == 1, dry)
check("the two-person no-address order is reported, never guessed",
      any(a["order_id"] == "R2" for a in dry["ambiguous_sample"]), dry)
pay.backfill(apply=True, db_path=DB)
with db._connect(DB) as c:
    v = [r[0] for r in c.execute("SELECT payer_customer_id FROM items WHERE order_id = 'R293121452'")]
    v2 = [r[0] for r in c.execute("SELECT payer_customer_id FROM items WHERE order_id = 'R2'")]
check("apply stamps Jeff on both lines", v == [jeff_cid, jeff_cid], v)
check("the ambiguous order stays unstamped", v2 == [None, None], v2)
with db._connect(DB) as c:
    c.execute("UPDATE items SET payer_customer_id = 999999 WHERE id = ?", (got[0]["id"],))
    c.commit()
pay.backfill(apply=True, db_path=DB)
with db._connect(DB) as c:
    kept = c.execute("SELECT payer_customer_id FROM items WHERE id = ?", (got[0]["id"],)).fetchone()[0]
check("the backfill never overwrites a payer already set", kept == 999999, kept)

print(f"\n{'ALL PASS' if not F else f'{len(F)} FAILED: {F}'}")
sys.exit(1 if F else 0)
