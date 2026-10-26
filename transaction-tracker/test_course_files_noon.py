"""THE NOON COURSE FILES JOB (Kerry 2026-10-26, CoS #2321, #2329-3, #2331
item 4): "Event ops - Absolutely should be on Tracker side. Not an agent
routine" / "CC Course Files to Manager too at the Tue noon job."

Event day from 12:00 PM: the Course Files once per event, To the course
contact, CC the TGF contacts + pack recipients + the chapter manager. A gap
holds the send and tells the manager once. Graph is mocked: nothing leaves.

Run: python3 test_course_files_noon.py
"""
import os, sys, io, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import print_pack as pp
    from email_parser import after_lock as al
    from email_parser import course_files_noon as cfn
    from email_parser import event_day_email as ede
    db.init_db(DB)
from datetime import datetime

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

for k, v in (("AZURE_TENANT_ID", "t"), ("AZURE_CLIENT_ID", "c"), ("AZURE_CLIENT_SECRET", "s"),
             ("EMAIL_ADDRESS", "tracker@example.test")):
    os.environ[k] = v

EV, NOCONTACT = 9801, 9802
with db._connect(DB) as conn:
    for eid, name in ((EV, "s9.80 NOON LINKS"), (NOCONTACT, "s9.81 NO CONTACT")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                     "start_time, course) VALUES (?, ?, '2099-12-15', 'San Antonio', 'active', '9-hole', "
                     "'Shotgun', '16:30', 'Test Links GC')", (eid, name))
    conn.commit()
for eid in (EV, NOCONTACT):
    db.save_event_pairings(eid, {"9": [{"group_num": 1, "slot_label": "1A", "players": [
        {"name": "Ann Test", "customer_id": None, "cart_pos": 1}]}]}, db_path=DB)

# The course contact (course_staff is its own reader; stubbed here), the
# pack recipients, the manager, and the mail.
pp.course_recipients_for_event = lambda ev, db_path=None: (
    {"ok": True, "to": "pro@course.test", "cc": ["shop@course.test"], "course_id": 1}
    if int(ev.get("id")) == EV else {"ok": False, "why": "no primary contact"})
pp.print_pack_recipient = lambda ev=None, db_path=None: "kerry@thegolffellowship.com"
al._manager_cc = lambda chapter, db_path=None: "manager@thegolffellowship.com"
SENT, NOTICES = [], []
pp.send_print_pack_files = lambda built, to_address=None, db_path=None, files=None, cc_address=None, \
    for_course=False, updated=False: SENT.append({"to": to_address, "cc": cc_address, "course": for_course}) \
    or {"sent": True, "to": to_address, "cc": cc_address}
ede._graph_send = lambda creds, to, subject, html, cc=None: NOTICES.append({"to": to, "subject": subject, "cc": cc}) or True
GAP = {"on": False}
def fake_build(render, eid, sd, db_path=None, allow_gaps=False, force_scorecards=False):
    sc = {"gaps": ["Ann Test has no handicap"]} if GAP["on"] else {"grouping": "group", "cards": 1}
    return {"event": {"id": eid, "item_name": "s9.80 NOON LINKS", "event_date": "2099-12-15", "course": "Test Links GC"},
            "parts": [{"slug": s, "pages": 1} for s in pp.COURSE_FILE_PARTS], "scorecards": sc,
            "part_shas": {s: "v1" for s in pp.COURSE_FILE_PARTS}, "pdf": b""}
pp.build_event_print_pack = fake_build
R = object()

print("1. When")
check("11:45 AM event day: not yet", cfn.run_event(EV, R, "", now=datetime(2099, 12, 15, 11, 45), db_path=DB)["why"] == "before noon")
check("the day before: not event day", cfn.run_event(EV, R, "", now=datetime(2099, 12, 14, 12, 0), db_path=DB)["why"] == "not event day")
check("3:30 PM (inside the hour before the 4:30 shotgun): too late",
      cfn.run_event(EV, R, "", now=datetime(2099, 12, 15, 15, 30), db_path=DB)["why"] == "within the hour before the first tee")
check("no course contact on file: nothing new",
      "no course contact" in cfn.run_event(NOCONTACT, R, "", now=datetime(2099, 12, 15, 12, 0), db_path=DB)["why"])

print("2. A gap holds it and tells the manager once")
GAP["on"] = True
r = cfn.run_event(EV, R, "", confirm=True, now=datetime(2099, 12, 15, 12, 0), db_path=DB)
check("held, nothing to the course", r["status"] == "held" and SENT == [], r)
check("the manager is told, Kerry copied", len(NOTICES) == 1 and NOTICES[0]["to"] == "manager@thegolffellowship.com"
      and NOTICES[0]["cc"] == "kerry@thegolffellowship.com" and "held" in NOTICES[0]["subject"].lower(), NOTICES)
cfn.run_event(EV, R, "", confirm=True, now=datetime(2099, 12, 15, 12, 15), db_path=DB)
check("the next run does not tell the manager again", len(NOTICES) == 1, NOTICES)

print("3. The send, once, manager CC'd")
GAP["on"] = False
d = cfn.run_event(EV, R, "", confirm=False, now=datetime(2099, 12, 15, 12, 30), db_path=DB)
check("dry run sends nothing and names the recipients", d.get("dry_run") and not SENT
      and d["to"] == "pro@course.test" and d["manager_cc"] == "manager@thegolffellowship.com", d)
r = cfn.check(R, "", now=datetime(2099, 12, 15, 12, 30), db_path=DB)
ev_r = r["events"].get(EV, {})
check("sent to the course contact", ev_r.get("status") == "sent" and len(SENT) == 1 and SENT[0]["to"] == "pro@course.test"
      and SENT[0]["course"], (ev_r, SENT))
cc = (SENT[0]["cc"] or "") if SENT else ""
check("CC: the course's other TGF contact, the pack recipient and the chapter manager",
      all(a in cc for a in ("shop@course.test", "kerry@thegolffellowship.com", "manager@thegolffellowship.com")), cc)
check("recorded for the after-lock job's changed-sheet resends",
      (al._get(al.COURSE_KEY.format(EV), DB) or {}).get("parts", {}).get("starter-sheet") == "v1")
r2 = cfn.run_event(EV, R, "", confirm=True, now=datetime(2099, 12, 15, 12, 45), db_path=DB)
check("never sent twice (a button send counts too)", r2["why"] == "Course Files already sent" and len(SENT) == 1, r2)
with db._connect(DB) as conn:
    n_log = conn.execute("SELECT COUNT(*) FROM message_log WHERE sent_by = 'course-files-noon'").fetchone()[0]
    n_act = conn.execute("SELECT COUNT(*) FROM agent_action_log WHERE action_type = 'course_files_noon'").fetchone()[0]
check("logged in message_log and agent_action_log", n_log == 1 and n_act == 1, (n_log, n_act))

print("4. The dial and the wiring")
db.set_app_setting(cfn.DIAL, "off", db_path=DB)
check("course_files_noon_auto=off stops it", cfn.check(R, "", now=datetime(2099, 12, 15, 13, 0), db_path=DB)["status"] == "off")
db.set_app_setting(cfn.DIAL, "", db_path=DB)
_a = open("app.py", encoding="utf-8").read()
check("the job is registered noon to 2:45 PM Central", 'id="course_files_noon"' in _a
      and 'hour="12-14", minute="0-59/15"' in _a.split('id="course_files_noon"')[0][-300:])
check("the read-only bridge exists", 'cmd == "scoring-course-files-noon"' in open("mcp_server.py", encoding="utf-8").read())

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
