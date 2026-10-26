"""RSVP PAYMENT DEADLINE (Kerry 2026-10-26, CoS #2307 item 4): on the lock
day, the 1:00 PM warning to unpaid RSVP-only players and the 4:50 PM
release (roster mark + email) before the 5:00 PM pairings run. Graph is
mocked: nothing leaves.

Run: python3 test_rsvp_deadline.py
"""
import os, sys, io, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import rsvp_deadline as rd
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

# Monday 2099-10-26 is the lock day of Tuesday 2099-10-27 (default dial: Tuesdays, one day ahead).
EV, OTHER = 9601, 9602
URL = "https://www.thegolffellowship.com/product-page/s9-29-silverhorn"
with db._connect(DB) as conn:
    for eid, name, d in ((EV, "s9.29 Silverhorn", "2099-10-27"), (OTHER, "s9.30 Later", "2099-11-03")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                     "start_time, course, registration_url, registration_url_status) VALUES "
                     "(?, ?, ?, 'San Antonio', 'active', '9-hole', 'Shotgun', '16:30', 'Silverhorn Golf Club', ?, "
                     "'verified')", (eid, name, d, URL))
    for cid, fn, em in ((880101, "Christopher", "chris@example.test"), (880102, "Paid", "paid@example.test"),
                        (880103, "Scanner", "scan@example.test")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status, chapter) "
                     "VALUES (?, ?, 'Test', 'active_member', 'San Antonio')", (cid, fn))
        conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?, ?, 1)", (cid, em))
    # Christopher and Scanner: Tracker PLAYING RSVPs, no order. Paid: a real registration.
    for cid, em, nm in ((880101, "chris@example.test", "Christopher Test"), (880103, "scan@example.test", "Scanner Test")):
        conn.execute("INSERT INTO rsvps (email_uid, player_name, player_email, response, matched_event, event_date, "
                     "customer_id, received_at) VALUES (?, ?, ?, 'PLAYING', 's9.29 Silverhorn', '2099-10-27', ?, "
                     "'2099-10-20 12:00:00')", (f"tracker:{EV}:{cid}", nm, em, cid))
    conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, transaction_status, order_date, "
                 "order_id, email_uid, merchant, customer_email) VALUES ('Paid Test', 880102, 's9.29 Silverhorn', ?, "
                 "'active', '2099-10-20', 'R1', 'manual-1', 'GoDaddy', 'paid@example.test')", (EV,))
    for i in range(3):   # Scanner has been caught as a mail scanner before
        conn.execute("INSERT INTO agent_action_log (agent_name, action_type, description) VALUES "
                     "('rsvp-link', 'event_invite_scanner_ignored', ?)", (f"event {EV} customer 880103 tap",))
    conn.commit()


def roster_names():
    conn = db.get_connection(DB)
    try:
        return sorted((r.get("name") or r.get("customer") or "") for r in db._event_roster_rows(conn, EV))
    finally:
        conn.close()

print("1. Who")
check("the lock day targets tomorrow's Tuesday", rd.lock_targets(datetime(2099, 10, 26).date(), DB) == {"2099-10-27"},
      rd.lock_targets(datetime(2099, 10, 26).date(), DB))
pl = rd.plan(EV, "warn", DB)
check("the unpaid RSVP is warned", [p["customer_id"] for p in pl["send"]] == [880101], pl)
check("a known mail scanner is skipped", any(s["customer_id"] == 880103 and "scanner" in s["why"] for s in pl["skip"]))
check("a registered player is never in it", all(p["customer_id"] != 880102 for p in pl["send"] + pl["skip"]))

print("2. The clock")
check("nothing before 1:00 PM", rd.tick(datetime(2099, 10, 26, 12, 50), DB) == [] and not SENT)
check("nothing on a non-lock day", rd.tick(datetime(2099, 10, 27, 13, 10), DB) == [] and not SENT)
r = rd.tick(datetime(2099, 10, 26, 13, 10), DB)
check("1:10 PM sends the warning once", len(SENT) == 1 and SENT[0]["to_address"] == "chris@example.test", (r, SENT))
w = SENT[0] if SENT else {}
check("the warning names 5:00 PM and carries the registration button",
      "5:00 PM" in w.get("html_body", "") and URL in w.get("html_body", "") and "Silverhorn" in w.get("subject", ""),
      w.get("subject"))
rd.tick(datetime(2099, 10, 26, 13, 20), DB)
check("the next tick does not send it again", len(SENT) == 1)
check("the roster still has him after the warning", "Christopher Test" in roster_names(), roster_names())

print("3. The release")
with db._connect(DB) as conn:   # a late RSVP, never warned
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (880104, 'Late', 'Test')")
    conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (880104, 'late@example.test', 1)")
    conn.execute("INSERT INTO rsvps (email_uid, player_name, player_email, response, matched_event, event_date, "
                 "customer_id, received_at) VALUES (?, 'Late Test', 'late@example.test', 'PLAYING', 's9.29 Silverhorn', "
                 "'2099-10-27', 880104, '2099-10-26 16:45:00')", (f"tracker:{EV}:880104",))
    conn.commit()
SENT.clear()
rd.tick(datetime(2099, 10, 26, 16, 50), DB)
check("4:50 PM releases the warned, unpaid player and emails him",
      [s["to_address"] for s in SENT] == ["chris@example.test"] and "released" in SENT[0]["subject"], SENT)
names = roster_names()
check("he is off the roster before the 5:00 PM pairings run", "Christopher Test" not in names, names)
check("a player who was never warned is not released", "Late Test" in names, names)
check("the registered player stays", "Paid Test" in names, names)
with db._connect(DB) as conn:
    n = conn.execute("SELECT COUNT(*) FROM rsvps WHERE email_uid = ?", (f"tracker:{EV}:880101",)).fetchone()[0]
    o = conn.execute("SELECT status FROM rsvp_email_overrides WHERE player_email = 'chris@example.test'").fetchone()
check("the RSVP row is kept and marked not_playing (undo on the Events page)", n == 1 and o and o[0] == "not_playing")
SENT.clear()
rd.tick(datetime(2099, 10, 26, 16, 55), DB)
check("the release is sent once", SENT == [], SENT)
check("nothing after 5:00 PM", rd.tick(datetime(2099, 10, 26, 17, 0), DB) == [])

print("4. Dials")
db.set_app_setting("rsvp_deadline_auto", "off", db_path=DB)
check("the dial turns it off", rd.tick(datetime(2099, 10, 26, 13, 30), DB) == [])
db.set_app_setting("rsvp_deadline_auto", "on", db_path=DB)
db.set_app_setting("payment_reminder_exclude_events", f"[{EV}]", db_path=DB)
SENT.clear()
rd.tick(datetime(2099, 10, 26, 13, 40), DB)
check("an excluded event (money collected outside the store) is skipped", SENT == [], SENT)

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
