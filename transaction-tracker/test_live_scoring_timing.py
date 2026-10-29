"""THE LIVE SCORING WINDOW and THE CLOSEOUT START (Kerry 2026-10-26, CoS
#2307 item 6, #2329 item 5): a player's saves open one hour before the first
tee and close 15 minutes after the last score once every card is final; the
closeout start signal goes 15 minutes after the last score. Saves only: the
event stays enabled (links, QR codes, boards, publishing). Graph is mocked.

Run: python3 test_live_scoring_timing.py
"""
import os, sys, io, contextlib, logging, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import score_entry as se
    from email_parser import live_scoring_default as lsd
    from email_parser import scoring_window as sw
    from email_parser import timezone_utils as tz
    db.init_db(DB)
    # The closeout chain has its own test (test_closeout_chain.py).
    db.set_app_setting("closeout_chain_auto", "off", db_path=DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

EV = 9301          # Tuesday 2026-10-20, shotgun 4:30 PM
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                 "start_time, course) VALUES (?, 's9.60 WINDOW', '2026-10-20', 'San Antonio', 'active', "
                 "'9-hole', 'Shotgun', '16:30', 'Test GC')", (EV,))
    for cid, fn in ((990101, "Ann"), (990102, "Bob")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, 'Test')", (cid, fn))
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, side_games, "
                     "transaction_status, order_date, order_id, email_uid, merchant) VALUES "
                     "(?, ?, 's9.60 WINDOW', ?, '9', 'NONE', 'active', '2026-10-01', ?, ?, 'GoDaddy')",
                     (f"{fn} Test", cid, EV, f"R{cid}", f"m-{cid}"))
    conn.commit()
db.save_event_pairings(EV, {"9": [{"group_num": 1, "slot_label": "1A", "players": [
    {"name": "Ann Test", "cart_pos": 1, "customer_id": 990101},
    {"name": "Bob Test", "cart_pos": 2, "customer_id": 990102}]}]}, db_path=DB)
lsd.ensure_live_scoring(EV, db_path=DB)

print("1. The event stays enabled; only saves have a window")
check("live_scoring_default still switches the event on the day before (links, QR, boards)",
      se.event_enabled(EV, DB))
st = sw.event_state(EV, now=datetime(2026, 10, 20, 15, 0), db_path=DB)
check("the first tee is the 4:30 PM shotgun", st["first_tee"] == datetime(2026, 10, 20, 16, 30), st)
check("saves open at 3:30 PM (one hour before)", st["opens_at"] == datetime(2026, 10, 20, 15, 30), st)
ok, why = sw.entry_open(EV, now=datetime(2026, 10, 20, 15, 29), db_path=DB)
check("3:29 PM: refused with the opening time, 12-hour", not ok and why == "Scoring opens at 3:30 PM", why)
check("3:30 PM: open", sw.entry_open(EV, now=datetime(2026, 10, 20, 15, 30), db_path=DB)[0])
db.set_app_setting(sw.ON_DIAL, "90", db_path=DB)
check("dial live_scoring_on_minutes=90 opens at 3:00 PM",
      sw.entry_open(EV, now=datetime(2026, 10, 20, 15, 0), db_path=DB)[0])
db.set_app_setting(sw.ON_DIAL, "", db_path=DB)
check("an unknown event or no first tee fails OPEN", sw.entry_open(999999, db_path=DB) == (True, None))
db.set_app_setting(sw.DIAL, "off", db_path=DB)
check("dial scoring_window_auto=off: always open",
      sw.entry_open(EV, now=datetime(2026, 10, 20, 9, 0), db_path=DB) == (True, None))
db.set_app_setting(sw.DIAL, "", db_path=DB)

print("2. Off 15 minutes after the last score, only once every card is final")
read = se.get_entered_scores(EV, db_path=DB)
gid = read["rounds"][0]["groups"][0]["group_id"]
se.claim_group(gid, "dev1", 990101, db_path=DB)
ops = [{"op_id": f"o{c}-{h}", "hole": h, "gross": 5, "customer_id": c}
       for c in (990101, 990102) for h in range(1, 10) if not (c == 990102 and h == 9)]
se.write_scores(gid, "dev1", 990101, ops, db_path=DB)
real_now = se._now
now_utc = datetime.utcnow()
st = sw.event_state(EV, now=tz.now_central() + timedelta(hours=2), db_path=DB)
check("a card with a blank hole is never final, so scoring never closes",
      not st["all_final"] and not st["closed"] and not st["closeout_due"], st)
se.write_scores(gid, "dev1", 990101, [{"op_id": "last", "hole": 9, "gross": 5, "customer_id": 990102}], db_path=DB)
last = sw.event_state(EV, db_path=DB)["last_score_at"]
check("the last score time is read in Central", last is not None and abs((tz.now_central() - last).total_seconds()) < 120, last)
st14 = sw.event_state(EV, now=last + timedelta(minutes=14), db_path=DB)
check("14 minutes after the last score: still open", not st14["closed"] and st14["open"], st14)
# the card goes final 15 minutes after its last score (se_card_lock_minutes)
se._now = lambda: (now_utc + timedelta(minutes=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
try:
    st16 = sw.event_state(EV, now=last + timedelta(minutes=16), db_path=DB)
    check("16 minutes after: every card final, scoring CLOSED", st16["all_final"] and st16["closed"], st16)
    ok, why = sw.entry_open(EV, now=last + timedelta(minutes=16), db_path=DB)
    check("…a save is refused: 'Scoring has closed for this event'", not ok and "closed" in why, why)

    print("3. The closeout start signal")
    with db._connect(DB) as conn:   # the job works on today's events
        conn.execute("UPDATE events SET event_date = ? WHERE id = ?", (last.date().isoformat(), EV))
        conn.commit()
    r = sw.tick(now=last + timedelta(minutes=16), db_path=DB)
    check("the job records the close and the closeout start", {k: v for k, v in r["events"].get(EV, {}).items() if k in ("closed", "closeout_start")}
          == {"closed": True, "closeout_start": True}
          and r["events"][EV].get("results_same_day") == "scheduled", r)
    with db._connect(DB) as conn:
        post = conn.execute("SELECT author, topic, body FROM platform_dialogue WHERE topic = 'closeout'").fetchall()
        acts = [x[0] for x in conn.execute("SELECT action_type FROM agent_action_log WHERE agent_name = 'scoring-window'")]
    check("one mailbox line TO front-desk and Event Ops, 12-hour times",
          len(post) == 1 and "CLOSEOUT START: s9.60 WINDOW" in post[0][2] and " PM" in post[0][2]
          and ":00 " not in post[0][2].split("saved at")[0][-6:], post)
    check("logged as live_scoring_closed and closeout_start", "live_scoring_closed" in acts and "closeout_start" in acts, acts)
    r2 = sw.tick(now=last + timedelta(minutes=30), db_path=DB)
    with db._connect(DB) as conn:
        n = conn.execute("SELECT COUNT(*) FROM platform_dialogue WHERE topic = 'closeout'").fetchone()[0]
    check("once per event: the next run posts nothing", r2["events"] == {} and n == 1, (r2, n))
    db.set_app_setting(sw.CLOSEOUT_DIAL, "30", db_path=DB)
    check("dial closeout_start_minutes moves the start",
          sw.event_state(EV, now=last + timedelta(minutes=16), db_path=DB)["closeout_at"] == last + timedelta(minutes=30))
    db.set_app_setting(sw.CLOSEOUT_DIAL, "", db_path=DB)
finally:
    se._now = real_now

print("4. Wiring")
_a = open("app.py", encoding="utf-8").read()
check("the save route checks the window for non-admins, 409 keeps the phone's queue",
      "from email_parser.scoring_window import entry_open" in _a.split("def api_se_write")[1].split("def api_se_sign")[0]
      and "409" in _a.split("def api_se_write")[1].split("def api_se_sign")[0])
check("the job is registered every 5 minutes", 'id="scoring_window"' in _a and 'minute="*/5"' in _a.split('id="scoring_window"')[0][-300:])

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
