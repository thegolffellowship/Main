"""The event P&L subtracts the prize fund (CA #834, Margin & Fee Standard
v1.0 §1; CFO #818/#820/#822). On the verified path prize_fund is the
RECORDED, EVENT-FUNDED payouts; payouts funded from money held elsewhere
(HIO pot, season / points-race pots, monthly points, the LSC skins pot)
are excluded and listed. With no payouts recorded the source says
"matrix_client" and the Events page supplies its own figure, as before.

Funding source of every category the test uses:
  individual_net / skins / team_net / ctp / mvp / tgf_mvp  -> this event's entries
  "Individual Net" (a display label on a hand-entered row) -> this event (folded)
  hole_in_one  -> the HIO pot (liability)           -> excluded
  City Net     -> the season points-race pot         -> excluded
  monthly_points -> the monthly points pot           -> excluded
  skins on a Lone Star Cup event -> the LSC skins pot -> excluded

Run: python3 test_prize_fund.py
"""
import contextlib
import io
import logging
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    db.init_db(DB)

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


conn = sqlite3.connect(DB)
conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (1,'A','One')")
EV, CUP, EMPTY = 3309, 3400, 3401
for eid, name, d in [(EV, "s9.24 Brackenridge", "2026-09-24"),
                     (CUP, "Lone Star Cup 2026", "2026-10-10"),
                     (EMPTY, "s9.29 Canyon Springs", "2026-09-29")]:
    conn.execute("INSERT INTO events (id, item_name, event_date) VALUES (?,?,?)", (eid, name, d))
    # one flat income entry puts the event on the VERIFIED path
    conn.execute("INSERT INTO acct_transactions (date, description, total_amount, type, "
                 "event_name, entry_type, amount, category) VALUES "
                 "(?, 'reg', 1000, 'income', ?, 'income', 1000, 'registration')", (d, name))
tgf = {}
for eid, name, d in [(EV, "s9.24 Brackenridge", "2026-09-24"), (CUP, "Lone Star Cup 2026", "2026-10-10")]:
    tgf[eid] = conn.execute("INSERT INTO tgf_events (code, name, event_date, events_id) "
                            "VALUES (?,?,?,?) RETURNING id", (name, name, d, eid)).fetchone()[0]
P = [  # (event, category, amount, paid)
    (EV, "individual_net", 100.0, True), (EV, "skins", 130.0, True),
    (EV, "team_net", 80.0, False), (EV, "ctp", 25.0, True),
    (EV, "mvp", 26.0, True), (EV, "tgf_mvp", 44.0, True),
    (EV, "Individual Net", 44.0, True),                      # display label, folded
    (EV, "hole_in_one", 500.0, True), (EV, "City Net", 60.0, True),
    (EV, "monthly_points", 15.0, True),
    (CUP, "skins", 300.0, True), (CUP, "team_net", 50.0, True),
]
for eid, cat, amt, paid in P:
    conn.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount, paid_at) "
                 "VALUES (?, 1, ?, ?, ?)", (tgf[eid], cat, amt, "2026-09-25" if paid else None))
conn.commit()
conn.close()

print("a played event with recorded payouts")
s = db.get_event_financial_summary("s9.24 Brackenridge", db_path=DB)
exp = s["expenses"]
check("prize fund = event-funded payouts only (449)", exp["prize_fund"] == 449.0, exp)
check("source says payouts", exp["prize_fund_source"] == "payouts", exp)
det = exp["prize_fund_detail"]
check("paid / unpaid split", det["paid"] == 369.0 and det["unpaid"] == 80.0, det)
exc = {e["category"]: e["amount"] for e in det["excluded"]}
check("held-pot payouts are excluded and listed",
      exc == {"hole_in_one": 500.0, "City Net": 60.0, "monthly_points": 15.0}, exc)
check("expenses total includes the prize fund",
      abs(exp["total"] - round(exp["course_fees"] + 449.0 + exp["processing_fees"], 2)) < 0.01, exp)
check("profit is net revenue minus expenses",
      abs(s["projected_profit"] - round(s["net_revenue"] - exp["total"], 2)) < 0.01, s)

print("the Lone Star Cup")
c = db.get_event_financial_summary("Lone Star Cup 2026", db_path=DB)
check("cup skins come from the held LSC pot, not the event",
      c["expenses"]["prize_fund"] == 50.0
      and any(e["category"] == "skins" for e in c["expenses"]["prize_fund_detail"]["excluded"]),
      c["expenses"])

print("an event with no payouts yet")
e = db.get_event_financial_summary("s9.29 Canyon Springs", db_path=DB)
check("prize fund 0 and the page supplies it (matrix_client)",
      e["expenses"]["prize_fund"] == 0 and e["expenses"]["prize_fund_source"] == "matrix_client",
      e["expenses"])

print(f"\n{len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
