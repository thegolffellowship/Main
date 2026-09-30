"""The monthly points race is FINAL the day after its last event (Kerry
2026-09-29: "September points is over now so the winner should be
highlighted") — display only; the $ share still waits for the month to close.

Run: python3 test_monthly_final.py
"""
import os, sys, tempfile, sqlite3, contextlib, io, logging
from datetime import date
tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-mfinal-"), "t.db")
os.environ["DATABASE_PATH"] = tmp
logging.disable(logging.CRITICAL)
from email_parser import database as db
import golf_genius_sync as ggs
import email_parser.timezone_utils as tz
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
c = sqlite3.connect(tmp)
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES (1, 's9.25 X', '2026-09-29', 'San Antonio', 'active')")
c.execute("INSERT INTO events (id, item_name, event_date, chapter, status) VALUES (2, 's9.26 X', '2026-09-30', 'San Antonio', 'cancelled')")
c.commit(); c.close()

# one "September Points" page per portal, two players
ggs.fetch_public_page = lambda url: {"html": "", "final_url": url}
ggs.parse_page_structure = lambda html, url: {"links": [{"text": "September Points", "href": "/pages/77"}]}
ggs.fetch_season_points_race = lambda pid, league, host: [
    {"player_name": "Luke Mazanec", "total_points": 60, "tournaments": 4, "affiliation": "TGF San Antonio"},
    {"player_name": "Pat Youngs", "total_points": 59, "tournaments": 4, "affiliation": "TGF San Antonio"}]

def sept(day):
    tz.today_central = lambda: day
    return next(m for m in db.get_monthly_points(db_path=tmp)["months"] if m["month"] == "2026-09")

m = sept(date(2026, 9, 29))
check("on the day of the last event: not final yet", m["final"] is False and not m["final_winners"], m.get("final"))
m = sept(date(2026, 9, 30))
check("the day after the month's last (non-cancelled) event: FINAL", m["final"] is True and m["last_event_date"] == "2026-09-29", m)
check("…the winner comes from the final numbers, not a hand pick",
      [w["player_name"] for w in m["final_winners"]] == ["Luke Mazanec"] and m["final_winners"][0]["points"] == 60)
check("…but the month is not COMPLETE, so no $ share and no payout recording yet",
      m["complete"] is False and m["winners"] == [])
m = sept(date(2026, 10, 1))
check("Oct 1: complete, winners carry the share (payout path unchanged)", m["complete"] is True and m["winners"])

print("\nALL PASSED" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
