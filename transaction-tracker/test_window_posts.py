"""WINDOW OPEN / WINDOW CLOSED posted by the Tracker (Event Ops #2460-I).

Event Ops: "WINDOW OPEN / CLOSED, the deploy freeze, can be posted by the
Tracker itself from first tee minus 1 hour, last score plus 1 hour, and the
clean closeout."

Covers: dial window_posts_auto OFF by default (nothing posts); WINDOW OPEN at
first tee - 60 min, once, TO: front-desk, topic front-desk, author
tracker-claude, naming the event + first tee + "no pushes to main until
WINDOW CLOSED"; WINDOW CLOSED on a clean closeout (closeout_final_check
final), else at last score + 60 min saying it is not final, once; nothing
before the times; the read-only bridge writes nothing; the tick wiring; the
mailbox only (no email path is imported).

Run: python3 test_window_posts.py
"""
import os, sys, io, contextlib, logging, tempfile, inspect
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
    from email_parser import window_posts as wp
    db.init_db(DB)
    db.set_app_setting("closeout_chain_auto", "off", db_path=DB)

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


def posts():
    with db._connect(DB) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT author, topic, body FROM platform_dialogue WHERE topic = 'front-desk' ORDER BY id")]


EV = 9401
DAY = "2026-11-03"
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                 "start_time, course) VALUES (?, 's9.70 FREEZE', ?, 'San Antonio', 'active', "
                 "'9-hole', 'Shotgun', '16:30', 'Test GC')", (EV, DAY))
    for cid, fn in ((990201, "Ann"), (990202, "Bob")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, 'Test')", (cid, fn))
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, side_games, "
                     "transaction_status, order_date, order_id, email_uid, merchant) VALUES "
                     "(?, ?, 's9.70 FREEZE', ?, '9', 'NONE', 'active', '2026-10-01', ?, ?, 'GoDaddy')",
                     (f"{fn} Test", cid, EV, f"R{cid}", f"m-{cid}"))
    conn.commit()
db.save_event_pairings(EV, {"9": [{"group_num": 1, "slot_label": "1A", "players": [
    {"name": "Ann Test", "cart_pos": 1, "customer_id": 990201},
    {"name": "Bob Test", "cart_pos": 2, "customer_id": 990202}]}]}, db_path=DB)
lsd.ensure_live_scoring(EV, db_path=DB)
FIRST = datetime(2026, 11, 3, 16, 30)

print("1. Dial OFF by default")
check("window_posts_auto is off unless set", not wp.dial_on(DB))
sw.tick(now=FIRST - timedelta(minutes=50), db_path=DB)
check("the tick posts nothing with the dial off", posts() == [], posts())
pv = wp.preview(EV, now=FIRST - timedelta(minutes=50), db_path=DB)
check("the bridge shows what WOULD post (open) and writes nothing",
      pv["events"][0]["post"] == "open" and posts() == []
      and not db.get_app_setting(wp.OPEN_KEY.format(EV), db_path=DB), pv)

print("2. WINDOW OPEN at first tee - 60 min, once")
db.set_app_setting(wp.DIAL, "on", db_path=DB)
r = sw.tick(now=FIRST - timedelta(minutes=61), db_path=DB)
check("3:29 PM: nothing yet", posts() == [], posts())
r = sw.tick(now=FIRST - timedelta(minutes=60), db_path=DB)
p = posts()
check("3:30 PM: one WINDOW OPEN", len(p) == 1 and r["events"].get(EV, {}).get("window_post") == "open", (r, p))
b = p[0]["body"] if p else ""
check("author tracker-claude, topic front-desk, first line TO: front-desk",
      p and p[0]["author"] == "tracker-claude" and b.splitlines()[0] == "TO: front-desk", p)
check("names the event, the first tee, and the freeze",
      "WINDOW OPEN: s9.70 FREEZE (event 9401)" in b and "4:30 PM" in b
      and "No pushes to main until WINDOW CLOSED" in b, b)
sw.tick(now=FIRST - timedelta(minutes=55), db_path=DB)
sw.tick(now=FIRST + timedelta(minutes=30), db_path=DB)
check("once per event", len(posts()) == 1, posts())

print("3. WINDOW CLOSED: clean closeout, else last score + 60 min")
LAST = FIRST + timedelta(hours=2)
st = {"event_id": EV, "event": "s9.70 FREEZE", "first_tee": FIRST, "last_score_at": LAST}
real_final = wp._final
try:
    wp._final = lambda eid, db_path=None: (False, ["2 cards not signed"])
    pl = wp.plan_event(EV, st=dict(st), now=LAST + timedelta(minutes=20), db_path=DB)
    check("closeout not started: no CLOSED", pl["post"] is None, pl)
    db.set_app_setting(sw.CLOSEOUT_KEY.format(EV), "x", db_path=DB)
    pl = wp.plan_event(EV, st=dict(st), now=LAST + timedelta(minutes=59), db_path=DB)
    check("not final and under an hour since the last score: no CLOSED", pl["post"] is None, pl)
    pl = wp.plan_event(EV, st=dict(st), now=LAST + timedelta(minutes=60), db_path=DB)
    check("last score + 60 min: CLOSED, says NOT final and why",
          pl["post"] == "closed" and pl["how"] == "last score + fallback"
          and "NOT final" in pl["body"] and "2 cards not signed" in pl["body"], pl)
    wp._final = lambda eid, db_path=None: (True, [])
    pl = wp.plan_event(EV, st=dict(st), now=LAST + timedelta(minutes=20), db_path=DB)
    check("clean closeout before the hour: CLOSED, says clean",
          pl["post"] == "closed" and "close-out is clean" in pl["body"]
          and pl["body"].startswith("TO: front-desk"), pl)
    k = wp.tick_event(EV, dict(st), now=LAST + timedelta(minutes=20), db_path=DB)
    k2 = wp.tick_event(EV, dict(st), now=LAST + timedelta(minutes=90), db_path=DB)
    p = posts()
    check("posted once", k == "closed" and k2 is None and len(p) == 2 and "WINDOW CLOSED" in p[1]["body"], p)
    db.set_app_setting(wp.DIAL, "off", db_path=DB)
    check("dial off: tick_event posts nothing",
          wp.tick_event(EV + 1, dict(st, event_id=EV + 1), now=LAST + timedelta(hours=3), db_path=DB) is None)
finally:
    wp._final = real_final

print("4. Wiring and limits")
_src = inspect.getsource(sw.tick)
check("scoring_window.tick calls window_posts.tick_event", "_wp.tick_event(" in _src)
_wsrc = inspect.getsource(wp)
check("mailbox only: no email or social sender in window_posts",
      "send_mail" not in _wsrc and "fetcher" not in _wsrc and "graph.facebook" not in _wsrc)
check("no pairings writer in window_posts",
      "save_event_pairings" not in _wsrc and "generate_event_pairings" not in _wsrc)
_a = open("app.py", encoding="utf-8").read()
check("the job starts at 5 AM so a 7 AM tee's WINDOW OPEN is on time",
      'hour="5-23"' in _a.split('id="scoring_window"')[0][-500:])
_m = open("mcp_server.py", encoding="utf-8").read()
check("bridge scoring-window-posts registered (read only: preview)",
      'cmd == "scoring-window-posts"' in _m and "_wpo.preview(" in _m)

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
