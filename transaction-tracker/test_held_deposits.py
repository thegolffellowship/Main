"""Pre-sold event deposits are held liabilities (Kerry 2026-09-30, #1050:
"Lone Star Cup is liabilities right now, for sure"). Run: python3 test_held_deposits.py"""
import os, sys, sqlite3, tempfile, contextlib, io, logging, json
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(DB)
from email_parser import margin_ledger as ml
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)
LSC = "LONE STAR CUP | The Hideout"
c = sqlite3.connect(DB)
c.execute("INSERT INTO events (id, item_name, event_date) VALUES (3329, ?, '2026-10-09')", (LSC,))
def row(desc, et, cat, src, amt):
    c.execute("INSERT INTO acct_transactions (date, description, total_amount, type, event_name, entry_type, "
              "amount, category, source) VALUES ('2026-09-11', ?, ?, ?, ?, ?, ?, ?, ?)",
              (desc, amt, et, LSC, et, amt, cat, src))
row("Mary Wade", "income", "addon", "venmo", 285); row("John Wade", "income", "addon", "venmo", 285)
row("Paul Rideout", "income", None, "venmo", 560)          # uncategorized income: counted, flagged
row("W Paul Reed", "expense", None, "venmo", 150)          # refund of a deposit
row("Some Vendor", "expense", "course_fee", "chase_alert", 999)   # not a refund
c.commit(); c.close()
held = db.held_deposits_all(DB)
check("the LSC (code default) is a pre-sold event before 10/12", len(held) == 1 and held[0]["held_now"]
      and held[0]["release_on"] == "2026-10-12", held)
h = held[0]
check("held = received 1130 (all income) - refunded 150 (payment-rail refunds only)",
      h["received"] == 1130 and h["refunded"] == 150 and h["held"] == 980, h)
check("uncategorized income is named for the CFO", [r["amount"] for r in h["uncategorized_income"]] == [560])
lb = ml.liability_buckets(db_path=DB)
check("scoring-liabilities lists the held bucket", lb["held_deposits"][0]["held"] == 980, lb.get("held_deposits"))
s = db.get_event_financial_summary(LSC, db_path=DB)
d = s["deposits"]
check("P&L dry run: headline unchanged, after shows no revenue", not d["live"] and s["net_revenue"] == d["before"]["net_revenue"]
      and d["after"]["net_revenue"] == 0, d)
db.set_app_setting("event_pnl_deposits", "on", db_path=DB)
s2 = db.get_event_financial_summary(LSC, db_path=DB)
check("dial on: net revenue 0, the held amount is a contra line, no profit on deposits",
      s2["net_revenue"] == 0 and s2["contra_revenue"]["deposits_held"] == d["before"]["net_revenue"]
      and s2["projected_profit"] <= 0, (s2["net_revenue"], s2["contra_revenue"], s2["projected_profit"]))
db.set_app_setting("deposit_events", json.dumps({"3329": "2026-09-01"}), db_path=DB)
s3 = db.get_event_financial_summary(LSC, db_path=DB)
check("after the release date the revenue is the event's again", s3["net_revenue"] == d["before"]["net_revenue"]
      and not s3["deposits"]["held_now"] and ml.liability_buckets(db_path=DB)["held_deposits"] == [])
print(f"\n{len(F)} FAILURE(S): {F}" if F else "\nALL PASS")
sys.exit(1 if F else 0)
