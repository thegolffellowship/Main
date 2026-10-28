"""CREDIT GOES TO THE BUYER (Kerry 2026-10-28, Event Ops #2476-#2478):
"Anytime that's under a player purchase any credit would go back to the
person who purchased." / "Jeff was the buyer, he used his coupon code".

Peter Rundqvist's spot (item 3162 shape) on Jeff Young's order with coupon
tgf-jeff: Credit lands on Jeff by the coupon owner (customer_id), never on
Peter; an unmapped personal code on a shared order holds; an extra row with
no coupon credits the order's buyer row; the player's own row is unchanged;
WD credit moves too; Reverse puts everything back.

Run: python3 test_credit_buyer.py
"""
import os, sys, tempfile, logging, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                           # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


def item(c, **kw):
    cols = ",".join(kw)
    return c.execute(f"INSERT INTO items ({cols}) VALUES ({','.join('?' * len(kw))}) RETURNING id",
                     list(kw.values())).fetchone()[0]


with db._connect(DB) as c:
    for cid, fn, ln in ((88, "Jeff", "Young"), (848, "Peter", "Rundqvist"),
                        (90, "Ann", "Buyer"), (91, "Bob", "Guest"), (92, "Cal", "Coupon"), (93, "Dee", "Pal")):
        c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, ?)", (cid, fn, ln))
    c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (88, 'jeff@x.com', 1)")
    base = dict(item_name="s9.29 SILVERHORN", item_price="$49.00", transaction_status="active",
                order_date="2026-10-24", merchant="GoDaddy")
    jeff = item(c, customer="Jeff Young", customer_id=88, customer_email="jeff@x.com", order_id="R1",
                coupon_code="tgf-jeff", email_uid="e1", item_index=0, **base)
    peter = item(c, customer="Peter Rundqvist", customer_id=848, customer_email="peter@x.com", order_id="R1",
                 coupon_code="tgf-jeff", notes="Purchased by Peter (guest From Mavn) & Pat",
                 email_uid="e1", item_index=1, **base)
    ann = item(c, customer="Ann Buyer", customer_id=90, customer_email="ann@x.com", order_id="R2",
               email_uid="e2", item_index=0, **base)
    bob = item(c, customer="Bob Guest", customer_id=91, customer_email="", order_id="R2",
               notes="Purchased by Ann Buyer", email_uid="e2", item_index=1, **base)
    cal = item(c, customer="Cal Coupon", customer_id=92, customer_email="cal@x.com", order_id="R3",
               coupon_code="tgf-cal", email_uid="e3", item_index=0, **base)
    dee = item(c, customer="Dee Pal", customer_id=93, customer_email="dee@x.com", order_id="R3",
               coupon_code="tgf-cal", email_uid="e3", item_index=1, **base)
    c.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('coupon_owners', ?)",
              (json.dumps({"tgf-jeff": 88}),))
    db._ensure_pairing_tables(c)
    c.commit()


def credits(cid):
    return sum(float(r.get("credit_amount") or 0) for r in db.get_player_credits("", db_path=DB, customer_id=cid))


def row(i):
    with db._connect(DB) as c:
        return dict(c.execute("SELECT * FROM items WHERE id = ?", (i,)).fetchone())


print("1. Peter's spot on Jeff's coupon order credits JEFF")
check("credit ok", db.credit_item(peter, note="removed", db_path=DB))
check("Peter holds no credit", credits(848) == 0, credits(848))
check("Jeff holds $49", abs(credits(88) - 49) < 0.01, credits(88))
r = row(peter)
check("Peter's row is off the pool (transferred) and names the move",
      r["transaction_status"] == "transferred" and "Jeff Young" in (r["credit_note"] or ""), r)
moved = row(r["transferred_to_id"])
check("Jeff's credit row names Peter's spot", "Peter Rundqvist" in moved["credit_note"]
      and moved["customer_id"] == 88, moved)

print("2. Reverse puts it back")
check("reverse ok", db.reverse_credit(peter, db_path=DB))
check("Peter active again", row(peter)["transaction_status"] == "active")
check("Jeff's moved credit gone", credits(88) == 0, credits(88))

print("3. Jeff's own row credits Jeff (no move)")
check("credit ok", db.credit_item(jeff, db_path=DB))
check("Jeff's own row stays credited", row(jeff)["transaction_status"] == "credited")
check("Jeff $49", abs(credits(88) - 49) < 0.01, credits(88))

print("4. Extra row with no coupon credits the order's buyer row")
check("credit ok", db.credit_item(bob, db_path=DB))
check("Ann holds $49, Bob none", abs(credits(90) - 49) < 0.01 and credits(91) == 0,
      (credits(90), credits(91)))

print("5. A personal coupon with no owner on a shared order HOLDS")
try:
    db.credit_item(dee, db_path=DB)
    check("held", False, "no CreditHold raised")
except db.CreditHold as e:
    check("held, names the code", "tgf-cal" in str(e), e)
check("Dee untouched", row(dee)["transaction_status"] == "active")

print("6. WD credit on Peter's spot moves to Jeff")
check("wd ok", db.wd_item(peter, note="wd", credit_amount="$30.00", db_path=DB))
check("Jeff gains $30", abs(credits(88) - 79) < 0.01, credits(88))
check("Peter none", credits(848) == 0, credits(848))
check("reverse wd ok", db.reverse_credit(peter, db_path=DB))
check("Jeff back to $49", abs(credits(88) - 49) < 0.01, credits(88))

print("FAILED: " + ", ".join(F) if F else "ALL PASS")
sys.exit(1 if F else 0)
