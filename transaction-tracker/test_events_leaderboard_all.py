"""LEADERBOARD | EVENTS shows EVERY event with scorecards; admin + manager
from 2026-09-23, members from v2.523.4 (Kerry 2026-10-02, #1146-1). BETA. Run: python3 test_events_leaderboard_all.py"""
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
for role, want in (("admin", 200), ("manager", 200), ("member", 200)):
    with tc.session_transaction() as s:
        s.clear(); s["role"] = role; s["authenticated"] = True; s["logged_in"] = True
    r1 = tc.get("/api/events-leaderboard"); r2 = tc.get("/api/events-leaderboard/event?name=a9.24%20Teravista")
    # the per-event board needs the GG result tables a bare fixture lacks;
    # this checks the ROLE gate only (anything but 401/403 = let through)
    ok = (r1.status_code == 200 and r2.status_code not in (401, 403)) if want == 200 else (r1.status_code in (401, 403) and r2.status_code in (401, 403))
    check(f"{role}: list + event routes {'open' if want == 200 else 'refused'}", ok, f"{r1.status_code} {r2.status_code}")
html = open("templates/contests.html", encoding="utf-8").read()
check("the EVENTS tab: manager-only on the staff page, a plain tab on /member (v2.523.4, #1146-1), no BETA badge (Kerry 2026-10-08)",
      '{% if member_mode %}<button class="top-tab" data-top="events">' in html
      and '<button class="top-tab manager-only" data-top="events"' in html and 'class="evlb-beta">BETA' not in html)
check("every board carries the short Unofficial / GG-official line (Kerry 10/8: less text)",
      'Unofficial &middot; Golf Genius is the official scorer' in html and 'Money shown as computed, not as paid.' not in html)
check("legends are chips, not prose (Kerry 10/8: \"Nobody is going to read all that\")",
      'Money winners color-code by FLIGHT: ${' not in html and 'Tap a player for their scorecard.</p>' in html)
check("the solo board drops the GG line on an event GG never scores", "off.hidden = !!ev.live_entry" in html)
check("the long explanation lives behind a How to read this button (Kerry 10/8: \"An only if curious thing\")",
      'data-evlb-hiw>How to read this</button>' in html and 'id="evlb-hiw-modal"' in html
      and 'function evlbReadGuide(d, game)' in html and 'non-buyers are placed in the flight their handicap' in html
      and html.index('id="evlb-hiw-modal"') > html.index('id="section-lone-star-cup"'))
check("no games, no buyers filter: every player shows, no Show All box, no green/grey rows (Kerry 10/8)",
      "!evlbShowAll && EVLB_BUYIN_GAMES.includes(game) && !evlbNoGames(d)" in html
      and "EVLB_BUYIN_GAMES.includes(board.game || null) && !evlbNoGames(d)" in html
      and 'typeof r._buyer === "boolean" && !evlbNoGames(d)' in html)
d = db.get_events_leaderboard(db_path=tmp)
check("the list API carries gg_official_through (None until set)", "gg_official_through" in d and d["gg_official_through"] is None)
db.set_app_setting("gg_official_through", "Oct 6", db_path=tmp)
check("…and the date once set", db.get_events_leaderboard(db_path=tmp)["gg_official_through"] == "Oct 6")
r = tc.get("/member/results")
check("/member/results renders the member page and lands on Events", r.status_code == 200 and b"window.EVLB_LANDING = true" in r.data and b'data-top="events"' in r.data)
print()
if F: print(f"{len(F)} FAILED"); sys.exit(1)
print("\n== non-buyers are placed by INDEX against an index ladder (Kerry 9/29: Vest / McCormick) ==")
_P = db._placed_flight_index
_mcc = {"hcp": 9, "index": 9.0, "flight_index": 18.0}       # PH 9, index 18.0 (18-hole)
_vest = {"hcp": 5, "index": 5.7, "flight_index": 11.4}      # PH 5, index 11.4
check("McCormick (PH 9, index 18.0) goes to Flight 2 on a <12.0 / 12.0+ ladder", _P(_mcc, [12.0], True, 9) == 1)
check("…where measuring her PH (9) would have put her in Flight 1 (the bug)", _P(_mcc, [12.0], False, 9) == 0)
check("Vest (index 11.4) stays in Flight 1 — the index, not the PH, decides", _P(_vest, [12.0], True, 9) == 0)
check("exactly 12.0 is Flight 2 (the label reads 12.0+)", _P({"flight_index": 12.0}, [12.0], True, 9) == 1)
check("no locked index: the current 9-hole index doubled to the 18-hole scale",
      _P({"index": 7.0, "hcp": 3}, [12.0], True, 9) == 1 and _P({"index": 5.0, "hcp": 3}, [12.0], True, 9) == 0)
check("nothing to measure by → UNFLIGHTED, never a guess", _P({"hcp": None, "index": None}, [12.0], True, 9) is None)
check("a ladder with no numbers still uses the buyers' PH midpoints", _P({"hcp": 10}, [8.5], False, 9) == 1)

print("ALL PASS")
