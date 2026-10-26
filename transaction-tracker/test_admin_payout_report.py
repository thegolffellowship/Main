"""THE SAME-NIGHT ADMIN PAYOUT REPORT (Kerry 2026-10-26, CoS #2329 item 6):
"I like to pay same night as a standard. ... Needs an automated Admin report
once all events are completed that would carry a link to PAYMENTS."

Once every active event dated today is closed (the closeout's own
closeout_final_check, stubbed here), ONE email to Kerry with each event's
players, payouts and unpaid total, and a button to /tgf?view=unpaid.
Graph is mocked: nothing leaves.

Run: python3 test_admin_payout_report.py
"""
import os, sys, io, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import admin_payout_report as apr
    from email_parser import closeout_checks as cc
    from email_parser import fetcher
    db.init_db(DB)
from datetime import datetime

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

SENT = []
fetcher.send_mail_graph = lambda **kw: SENT.append(kw) or True
for k, v in (("AZURE_TENANT_ID", "t"), ("AZURE_CLIENT_ID", "c"), ("AZURE_CLIENT_SECRET", "s"),
             ("EMAIL_ADDRESS", "tracker@example.test")):
    os.environ[k] = v

DAY = "2099-10-27"
EV_A, EV_B, EV_EMPTY = 9701, 9702, 9703
with db._connect(DB) as conn:
    for eid, name in ((EV_A, "s9.29 Silverhorn"), (EV_B, "a9.29 Teravista"), (EV_EMPTY, "x9.29 Nobody")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES "
                     "(?, ?, ?, 'San Antonio', 'active')", (eid, name, DAY))
    for cid, fn in ((880201, "Ann"), (880202, "Bob"), (880203, "Cal")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, 'Test')", (cid, fn))
    for cid, eid, nm in ((880201, EV_A, "s9.29 Silverhorn"), (880202, EV_A, "s9.29 Silverhorn"),
                         (880203, EV_B, "a9.29 Teravista")):
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, transaction_status, order_date, "
                     "order_id, email_uid, merchant) VALUES (?, ?, ?, ?, 'active', '2099-10-20', ?, ?, 'GoDaddy')",
                     (f"P{cid}", cid, nm, eid, f"R{cid}", f"manual-{cid}"))
    for tid, eid in ((1, EV_A), (2, EV_B)):
        conn.execute("INSERT INTO tgf_events (id, code, name, event_date, events_id) VALUES (?, ?, ?, ?, ?)",
                     (tid, f"T{tid}", f"T{tid}", DAY, eid))
    conn.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount, paid_at) VALUES "
                 "(1, 880201, 'net', 25.50, NULL), (1, 880202, 'skins', 10.00, '2099-10-27 21:00:00'), "
                 "(2, 880203, 'net', 40.00, NULL)")
    conn.commit()

CLOSED = {EV_A: True, EV_B: False}
cc.closeout_final_check = lambda eid, db_path=None, _read=None: (
    {"final": CLOSED.get(int(eid), False), "blocking": [] if CLOSED.get(int(eid)) else ["2 cards not final"]})

EVENING = datetime(2099, 10, 27, 21, 15)

print("1. Waits until every event today is closed")
r = apr.tick(now=datetime(2099, 10, 27, 16, 45), db_path=DB)
check("before 5:00 PM: not yet", r["status"] == "not yet", r)
r = apr.tick(now=EVENING, db_path=DB)
check("one event still open: waiting, nothing sent", r["status"] == "waiting" and not SENT, r)
check("it names the open event and why", r.get("open") and r["open"][0]["event"] == "a9.29 Teravista"
      and "not final" in r["open"][0]["blocking"][0], r)
p = apr.plan(DAY, DB)
check("an event with nobody on its roster never holds the report",
      all(e["event_id"] != EV_EMPTY for e in p["events"]), p)

print("2. Once all are closed: one email to Kerry")
CLOSED[EV_B] = True
d = apr.run(day=DAY, now=EVENING, db_path=DB)
check("a dry run sends nothing", d["status"] == "would send" and not SENT, d)
r = apr.tick(now=EVENING, db_path=DB)
check("it sends", r["status"] == "sent" and len(SENT) == 1, r)
m = SENT[0] if SENT else {}
check("to Kerry", m.get("to_address") == "kerry@thegolffellowship.com", m.get("to_address"))
h = m.get("html_body", "")
check("each event, players and the unpaid totals",
      "s9.29 Silverhorn" in h and "a9.29 Teravista" in h and "$25.50" in h and "$40.00" in h
      and "$65.50" in m.get("subject", ""), m.get("subject"))
check("a button to PAYMENTS (Payouts -> Unpaid)", "/tgf?view=unpaid" in h and "Open PAYMENTS" in h)
check("12-hour wording, the day named", "Tuesday, October 27" in m.get("subject", ""), m.get("subject"))
r = apr.tick(now=datetime(2099, 10, 27, 21, 30), db_path=DB)
check("once a day", r["status"] == "already sent" and len(SENT) == 1, r)
with db._connect(DB) as conn:
    ml = conn.execute("SELECT COUNT(*) FROM message_log WHERE sent_by = 'admin-payout-report'").fetchone()[0]
    al = conn.execute("SELECT COUNT(*) FROM agent_action_log WHERE action_type = 'admin_payout_report'").fetchone()[0]
check("logged in message_log and agent_action_log", ml == 1 and al == 1, (ml, al))

print("3. Staff only, and the dial")
db.set_app_setting(apr.TO_KEY, "member@gmail.com", db_path=DB)
check("a non-staff address is refused", apr.recipient(DB) is None)
r = apr.run(day="2099-10-28", now=EVENING, db_path=DB)
check("no events that day: nothing", r["status"] == "no events today", r)
db.set_app_setting(apr.TO_KEY, "", db_path=DB)
db.set_app_setting(apr.DIAL, "off", db_path=DB)
check("dial off: nothing runs", apr.run(day=DAY, now=EVENING, db_path=DB)["status"] == "off")
db.set_app_setting(apr.DIAL, "", db_path=DB)

print("4. Wiring")
_a = open("app.py", encoding="utf-8").read()
check("the 15-minute job is registered", 'id="admin_payout_report"' in _a and "admin_payout_report import tick" in _a)
_t = open("templates/tgf.html", encoding="utf-8").read()
check("Payouts opens the Unpaid queue from ?view=unpaid", 'get("view")' in _t and 'v === "unpaid"' in _t)
_m = open("mcp_server.py", encoding="utf-8").read()
check("read-only bridge scoring-admin-payout-report", 'cmd == "scoring-admin-payout-report"' in _m)

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
