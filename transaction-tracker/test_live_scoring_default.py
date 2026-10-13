"""LIVE SCORING ON BY DEFAULT (Kerry 2026-10-13: "Turn live scoring on for
an event should be default after 5:00p Monday pairings are turned on and
definitely prior to these emails being sent out.").

Run: python3 test_live_scoring_default.py
"""
import os, sys, io, contextlib, logging, tempfile
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import score_entry as se
    from email_parser import live_scoring_default as lsd
    from email_parser import event_day_email as ede
    from email_parser import fetcher
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

fetcher.send_mail_graph = lambda **kw: True
for k, v in (("AZURE_TENANT_ID", "t"), ("AZURE_CLIENT_ID", "c"), ("AZURE_CLIENT_SECRET", "s"),
             ("EMAIL_ADDRESS", "tracker@example.test")):
    os.environ[k] = v

TUE, NEXT, OLD, NOSHEET = 9201, 9202, 9203, 9204
with db._connect(DB) as conn:
    for eid, name, d in ((TUE, "s9.50 TUESDAY", "2026-10-20"), (NEXT, "s9.51 NEXT WEEK", "2026-10-27"),
                         (OLD, "s9.10 GG ERA", "2026-10-06"), (NOSHEET, "a9.50 NO SHEET", "2026-10-20")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                     "start_time, course) VALUES (?, ?, ?, 'San Antonio', 'active', '9-hole', 'Shotgun', "
                     "'16:30', 'Test GC')", (eid, name, d))
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (990001, 'Ann', 'Able')")
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (990002, 'Bob', 'Baker')")
    for cid, nm in ((990001, "Ann Able"), (990002, "Bob Baker")):
        for eid, name in ((TUE, "s9.50 TUESDAY"), (NEXT, "s9.51 NEXT WEEK"), (OLD, "s9.10 GG ERA")):
            conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, side_games, "
                         "transaction_status, order_date, order_id, email_uid, merchant) VALUES "
                         "(?, ?, ?, ?, '9', 'NONE', 'active', '2026-10-01', ?, ?, 'GoDaddy')",
                         (nm, cid, name, eid, f"R{cid}{eid}", f"m-{cid}-{eid}"))
    conn.commit()
for eid in (TUE, NEXT, OLD):
    db.save_event_pairings(eid, {"9": [{"group_num": 1, "slot_label": "1A", "players": [
        {"name": "Ann Able", "cart_pos": 1, "customer_id": 990001},
        {"name": "Bob Baker", "cart_pos": 2, "customer_id": 990002}]}]}, db_path=DB)

print("1. When an event comes due")
mon_4pm = datetime(2026, 10, 19, 16, 59)
mon_5pm = datetime(2026, 10, 19, 17, 0)
tue_noon = datetime(2026, 10, 20, 12, 0)
check("Monday 4:59 PM: Tuesday's event is not due yet", TUE not in lsd.due_event_ids(mon_4pm, DB))
check("Monday 5:00 PM: Tuesday's events are due", {TUE, NOSHEET} <= set(lsd.due_event_ids(mon_5pm, DB)))
check("…next week's is not", NEXT not in lsd.due_event_ids(mon_5pm, DB))
check("event day: still due", TUE in lsd.due_event_ids(tue_noon, DB))

print("2. The job switches it on and seeds the rounds")
check("off before the job", not se.event_enabled(TUE, DB))
res = lsd.live_scoring_auto_check(mon_5pm, DB)
r = res["events"][TUE]
check("Tuesday's event is on, newly", se.event_enabled(TUE, DB) and r.get("newly_enabled"), r)
check("…with a seeded 9-hole round and a scoring link per group",
      r["rounds"].get("9") and se.event_group_links(TUE, "9", db_path=DB).get(1), r)
check("an event with no saved pairings is left off, with the reason",
      not se.event_enabled(NOSHEET, DB) and res["events"][NOSHEET]["skipped"] == "no saved pairings",
      res["events"][NOSHEET])
again = lsd.live_scoring_auto_check(mon_5pm, DB)["events"][TUE]
check("a second run changes nothing (idempotent)", again.get("newly_enabled") is False
      and again["rounds"] == r["rounds"], again)

print("3. Never the Golf Genius era; the dial stops the job")
o = lsd.ensure_live_scoring(OLD, db_path=DB)
check("a GG-era event is skipped", not se.event_enabled(OLD, DB) and "Golf Genius" in (o.get("skipped") or ""), o)
db.set_app_setting(lsd.DIAL, "0", db_path=DB)
check("dial off: the job does nothing", lsd.live_scoring_auto_check(mon_5pm, DB) == {"status": "off"})
db.set_app_setting(lsd.DIAL, "", db_path=DB)

print("4. The event-day email turns it on before it previews")
check("next week's event is off", not se.event_enabled(NEXT, DB))
ede.send_event_day_preview(NEXT, db_path=DB)
check("the preview switched it on and seeded its round",
      se.event_enabled(NEXT, DB) and se.event_group_links(NEXT, "9", db_path=DB).get(1))
check("…and both stay listed with Tuesday's", {TUE, NEXT} <= se.enabled_events(DB))

try: os.unlink(DB)
except OSError: pass
print("ALL PASS" if not F else f"{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
