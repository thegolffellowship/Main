"""Event P&L revenue by the Margin & Fee Standard v1.1 (platform-claude #1029
§8.1, 8.5, 8.6; CFO #1024/#1027; Kerry 9/9 + 9/30):
  - a credited item leaves event revenue (its fees stay: never refunded);
  - the 3.5% fee comes from the prorated transaction_fee splits, not the
    order fee repeated on every item;
  - a coupon is subtracted ONCE per order (its split repeats on each item);
  - events before the margin-model cutover stay frozen;
  - DRY RUN until the `event_pnl_v11` dial is on.
Run: python3 test_event_pnl_v11.py
"""
import contextlib, io, logging, os, sqlite3, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(DB)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

c = sqlite3.connect(DB)
EVN, OTHER, OLD = "s9.98 Testhorn", "s9.97 Elsewhere", "s9.01 Oldhorn"
for eid, n, d in [(5001, EVN, "2026-09-29"), (5002, OTHER, "2026-09-29"), (5003, OLD, "2026-08-25")]:
    c.execute("INSERT INTO events (id, item_name, event_date) VALUES (?,?,?)", (eid, n, d))

def item(iid, name, cust, price, fee, status="active", order="R1", coupon=None):
    c.execute("INSERT INTO items (id, order_date, email_uid, order_id, item_index, merchant, customer, item_name, "
              "item_price, transaction_fees, transaction_status, coupon_code, coupon_amount) "
              "VALUES (?,'2026-09-28',?,?,?,?,?,?,?,?,?,?,?)",
              (iid, f"uid-{order}", order, iid, "The Golf Fellowship", cust, name, f"${price:.2f}",
               f"${fee:.2f}", status, "tgf-x" if coupon else None, f"${coupon:.2f}" if coupon else None))

def txn(order, event):
    return c.execute("INSERT INTO acct_transactions (date, description, total_amount, type, event_name, "
                     "entry_type, amount, category, source) VALUES ('2026-09-28', ?, 0, 'income', ?, "
                     "'income', 0, 'godaddy_order', 'godaddy') RETURNING id", (order, event)).fetchone()[0]

def split(t, iid, ev, typ, amt):
    c.execute("INSERT INTO godaddy_order_splits (transaction_id, item_id, event_name, customer, "
              "split_type, amount) VALUES (?,?,?,?,?,?)", (t, iid, ev, "x", typ, amt))

# A: plain paid entry, $86 + $3.01
item(1, EVN, "A", 86, 3.01, order="R1"); t = txn("R1", EVN)
split(t, 1, EVN, "registration", 86); split(t, 1, EVN, "transaction_fee", 3.01); split(t, 1, EVN, "merchant_fee", -2.88)
# B: credited no-show, $86 + $3.01 (fee is kept)
item(2, EVN, "B", 86, 3.01, status="credited", order="R2"); t = txn("R2", EVN)
split(t, 2, EVN, "registration", 86); split(t, 2, EVN, "transaction_fee", 3.01); split(t, 2, EVN, "merchant_fee", -2.88)
# C: one order, two players on this event, ONE $10 coupon repeated on both rows
item(3, EVN, "C1", 86, 5.67, order="R3", coupon=10); item(4, EVN, "C2", 86, 5.67, order="R3", coupon=10)
t = txn("R3", EVN)
for i in (3, 4):
    split(t, i, EVN, "registration", 86); split(t, i, EVN, "transaction_fee", 2.84 if i == 3 else 2.83)
    split(t, i, EVN, "coupon", -10); split(t, i, EVN, "merchant_fee", -2.6)
# D: one order across two events, order fee $5.60 repeated on both item rows
item(5, EVN, "D", 80, 5.60, order="R4"); item(6, OTHER, "D", 80, 5.60, order="R4")
t = txn("R4", EVN)
split(t, 5, EVN, "registration", 80); split(t, 5, EVN, "transaction_fee", 2.80)
split(t, 6, OTHER, "registration", 80); split(t, 6, OTHER, "transaction_fee", 2.80)
txn("R4-other", OTHER)   # the other event's own ledger row puts it on the verified path
# OLD: pre-cutover event with a credited item
item(7, OLD, "E", 70, 2.45, status="credited", order="R5"); t = txn("R5", OLD)
split(t, 7, OLD, "registration", 70); split(t, 7, OLD, "transaction_fee", 2.45)
c.commit(); c.close()

s = db.get_event_financial_summary(EVN, db_path=DB)
v = s["standard_v11"]
check("v1.1 block rides along; applies (after the 9/5 cutover); DRY RUN by default",
      v and v["applies"] and not v["live"], v)
b, a = v["before"], v["after"]
check("before: credited $86 counted, fees = the item fields (credited dropped, D's order fee whole)",
      b["godaddy"] == 424.0 and b["tx_fees"] == round(3.01 + 5.67 + 5.67 + 5.60, 2), b)
check("after: credited item out of registration revenue (424 - 86 = 338)", a["godaddy"] == 338.0, a)
check("credited rows named", v["credited_removed"] == 86.0
      and [r["item_id"] for r in v["credited_rows"]] == [2], v["credited_rows"])
check("after: fees from the prorated splits, credited fee KEPT, D's share only (3.01+3.01+2.84+2.83+2.80)",
      a["tx_fees"] == round(3.01 + 3.01 + 2.84 + 2.83 + 2.80, 2), a)
check("coupon subtracted ONCE per order ($10, not $20)", a["coupons"] == -10.0
      and v["coupon_orders"][0]["dup_splits"] == 2, v["coupon_orders"])
check("after: net revenue = 338 - 10 + 14.49", a["net_revenue"] == round(338 - 10 + 14.49, 2), a)
check("headline unchanged while the dial is off", s["net_revenue"] == b["net_revenue"]
      and s["projected_profit"] == b["projected_profit"])
check("delta_profit = after - before", v["delta_profit"] == round(a["projected_profit"] - b["projected_profit"], 2))

o = db.get_event_financial_summary(OTHER, db_path=DB)["standard_v11"]
check("the other event of a split order gets only ITS fee share (2.80)", o["after"]["tx_fees"] == 2.80, o)

old = db.get_event_financial_summary(OLD, db_path=DB)["standard_v11"]
db.set_app_setting("event_pnl_v11", "on", db_path=DB)
oldh = db.get_event_financial_summary(OLD, db_path=DB)
check("pre-cutover event: not applied, even with the dial on (past periods frozen)",
      not old["applies"] and not oldh["standard_v11"]["live"]
      and oldh["net_revenue"] == oldh["standard_v11"]["before"]["net_revenue"])
s2 = db.get_event_financial_summary(EVN, db_path=DB)
check("dial on: the headline takes the v1.1 figures", s2["standard_v11"]["live"]
      and s2["net_revenue"] == a["net_revenue"] and s2["projected_profit"] == a["projected_profit"]
      and s2["revenue"]["godaddy"] == 338.0, (s2["net_revenue"], s2["revenue"]))
print(f"\n{len(F)} FAILURE(S): {F}" if F else "\nALL PASS")
sys.exit(1 if F else 0)
