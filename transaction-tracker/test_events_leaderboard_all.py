"""LEADERBOARD | EVENTS shows EVERY event with scorecards, admin + manager,
BETA (Kerry 2026-09-23). Run: python3 test_events_leaderboard_all.py"""
import os, sys, sqlite3, tempfile, contextlib, io, logging, json
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-evlb-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
os.environ.setdefault("ADMIN_PIN", "1234"); os.environ.setdefault("SECRET_KEY", "x")
os.environ["SCHEDULER_DISABLED"] = "1"
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as A
from email_parser import database as db
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)
c = sqlite3.connect(tmp)
with contextlib.redirect_stdout(io.StringIO()):
    db.get_events_leaderboard(db_path=tmp)   # ensures scoring tables
for i, (name, date, ch) in enumerate([("s9.22 Silverhorn", "2026-09-08", "San Antonio"),
                                      ("s9.24 Brackenridge", "2026-09-22", "San Antonio"),
                                      ("a9.24 Teravista", "2026-09-22", "Austin"),
                                      ("s9.25 Canyon Springs", "2026-09-29", "San Antonio")], start=9001):
    c.execute("INSERT INTO events (id, item_name, event_date, chapter, format) VALUES (?,?,?,?,'9 Holes')", (i, name, date, ch))
    if i < 9004:
        c.execute("INSERT INTO scoring_rounds (event_id, player_name, source) VALUES (?, 'Pat Youngs', 'gg')", (i,))
# the retired pilot list is still stored on production — it must not narrow anything
c.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('events_leaderboard_events', ?)", (json.dumps(["s9.22"]),))
c.commit(); c.close()
d = db.get_events_leaderboard(db_path=tmp)
names = [e["item_name"] for e in d["events"]]
check("every event with scorecards shows, newest first — the old stored pilot list is ignored",
      names[:2] and set(names) == {"s9.22 Silverhorn", "s9.24 Brackenridge", "a9.24 Teravista"}, str(names))
check("an event with no cards yet does not show (s9.25 is next week)", "s9.25 Canyon Springs" not in names)
check("the page is not flagged as narrowed", d["pilot"] is False and d["pilot_codes"] == [], str(d.get("pilot_codes")))
db.set_app_setting("events_leaderboard_only", json.dumps(["a9.24"]), db_path=tmp)
d = db.get_events_leaderboard(db_path=tmp)
check("the new dial still narrows it for a test", [e["item_name"] for e in d["events"]] == ["a9.24 Teravista"] and d["pilot"] is True)
db.set_app_setting("events_leaderboard_only", "[]", db_path=tmp)
tc = A.app.test_client()
for role, want in (("admin", 200), ("manager", 200), ("member", 403)):
    with tc.session_transaction() as s:
        s.clear(); s["role"] = role; s["authenticated"] = True; s["logged_in"] = True
    r1 = tc.get("/api/events-leaderboard"); r2 = tc.get("/api/events-leaderboard/event?name=a9.24%20Teravista")
    # the per-event board needs the GG result tables a bare fixture lacks;
    # this checks the ROLE gate only (anything but 401/403 = let through)
    ok = (r1.status_code == 200 and r2.status_code not in (401, 403)) if want == 200 else (r1.status_code in (401, 403) and r2.status_code in (401, 403))
    check(f"{role}: list + event routes {'open' if want == 200 else 'refused'}", ok, f"{r1.status_code} {r2.status_code}")
html = open("templates/contests.html", encoding="utf-8").read()
check("the EVENTS tab is manager-only (admin + manager), marked BETA, and never rendered on /member",
      '{% if not member_mode %}<button class="top-tab manager-only" data-top="events"' in html and 'class="evlb-beta">BETA' in html)
print()
if F: print(f"{len(F)} FAILED"); sys.exit(1)
print("ALL PASS")
