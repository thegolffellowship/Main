"""THE COURSE UPDATE BEFORE THE LOCK (Kerry 2026-10-26, CoS #2307 item 2):
noon the day before the lock, the registered list + live link + lock notice
to the course contact, manager CC'd; locked behind the dial and Kerry's stamp.

Run: python3 test_course_update.py
"""
import os, sys, io, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import course_update as cu
    from email_parser import print_pack as pp
    db.init_db(DB)
from datetime import datetime

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

EV, SAT = 9801, 9802     # Tuesday 2099-12-15 (locks Monday 12/14 5:00 PM) and Saturday 2099-12-19 (locks Wed 12/16)
with db._connect(DB) as conn:
    for eid, name, d in ((EV, "s9.98 COURSE UPDATE", "2099-12-15"), (SAT, "s18.98 SATURDAY", "2099-12-19")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, start_time, "
                     "course) VALUES (?, ?, ?, 'San Antonio', 'active', '9-hole', 'Tee Times', '16:00', 'Test Links GC')",
                     (eid, name, d))
        for i, fn in enumerate(("Ann", "Bob")):
            cid = 897000 + eid % 100 * 10 + i
            conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
                         "VALUES (?, ?, 'Test', 'active_member')", (cid, fn))
            conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, transaction_status, "
                         "order_date, order_id, email_uid, merchant) VALUES (?, ?, ?, ?, '9', 'active', '2099-12-01', ?, ?, "
                         "'GoDaddy')", (f"{fn} Test", cid, name, eid, f"R{cid}", f"manual-{cid}"))
    conn.commit()
pp.course_recipients_for_event = lambda ev, db_path=None: {
    "ok": True, "to": "pro@course.test", "to_name": "Pat Pro", "cc": ["shop@course.test"], "course_id": 1}

print("1. The email")
b = cu.build(EV, DB)
check("noon the day before the lock: Sunday noon for a Tuesday nine", b["send_at"] == "2099-12-13T12:00:00", b["send_at"])
check("Saturday event: noon Tuesday (it locks Wednesday)", cu.build(SAT, DB)["send_at"] == "2099-12-15T12:00:00")
check("to the primary contact, CC the other contacts and the manager",
      b["to"] == "pro@course.test" and "shop@course.test" in b["cc"] and len(b["cc"]) >= 2, (b["to"], b["cc"]))
check("the registered list, the live link and the lock notice",
      "Ann Test" in b["html"] and "Bob Test" in b["html"] and f"/member/teesheet/{EV}" in b["html"]
      and "5:00 PM Monday" in b["html"] and b["players"] == 2, b["html"][-700:])
check("greets the contact by first name", "Hi Pat," in b["html"])
check("nothing held", b["held"] == [], b["held"])

print("2. The locks")
SENT = []
fake = lambda to, s, h, cc: SENT.append((to, s, cc)) or True
check("dial off: nothing", cu.check(now=datetime(2099, 12, 13, 12, 1), db_path=DB, sender=fake)["status"].endswith("not on") and not SENT)
db.set_app_setting(cu.DIAL, "on", db_path=DB)
check("dial on but wording not stamped: nothing", cu.check(now=datetime(2099, 12, 13, 12, 1), db_path=DB, sender=fake)["status"] == "wording not approved")
db.set_app_setting(cu.STAMP, cu.template_hash(), db_path=DB)
check("Sunday 11:46 AM: not yet", cu.check(now=datetime(2099, 12, 13, 11, 46), db_path=DB, sender=fake)["events"] == {})
r = cu.check(now=datetime(2099, 12, 13, 12, 1), db_path=DB, sender=fake)
check("Sunday 12:01 PM: sent once to the course", [s[0] for s in SENT] == ["pro@course.test"], (r, SENT))
cu.check(now=datetime(2099, 12, 13, 12, 16), db_path=DB, sender=fake)
check("never twice", len(SENT) == 1, SENT)
check("a changed wording voids the stamp", (setattr(cu, "BODY", cu.BODY + " ") or True)
      and not cu.approval_state(DB)["approved"])

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
