"""The standings total and the rows beside it must agree.

Kerry, 2026-09-16, looking at the SA FALL NET board on event night:
"Why aren't these points adding correctly?" Jeff Rideout's five counted
rows read 11 + 10 + 8 + 6 + 1 = 36 over a total of 30 — and 30 is
exactly those same rows MINUS the 9/15 Quarry line worth 6.

Two caches on one page, ~72x apart. The row expansion is fetched live
from Golf Genius and cached 10 MINUTES; the total beside it came from
the `gg_points_standings` snapshot on a 12 HOUR timer. Golf Genius
awards season points when the manager closes an event out — hours after
the snapshot that is still serving the page — so on event night the rows
carried the night's points and the total did not.

`get_points_race_standings` already knew standings move with events, but
the guard was armed in ONE DIRECTION ONLY: "no event since" could let a
time-stale snapshot stand, and nothing could ever make a time-fresh one
stale. The clock alone decided, and the clock cannot tell that a round
finished twenty minutes ago.

Run: python3 test_points_race_staleness.py
"""
import os, sys, tempfile, logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.WARNING)
import app as _appmod                                            # noqa: E402,F401
from email_parser import database as db                          # noqa: E402
from email_parser.timezone_utils import today_central_str        # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

RACE = "san_antonio_fall_net"
TODAY = today_central_str()

# Count refreshes instead of hitting Golf Genius.
_calls = []
db.refresh_points_race_standings = (
    lambda race_key, **kw: _calls.append(race_key))


def reset(hours_ago, events):
    """One snapshot row `hours_ago` old, plus the given (date, status) events."""
    _calls.clear()
    with db._connect(DB) as conn:
        db._ensure_gg_points_table(conn)
        conn.execute("DELETE FROM gg_points_standings WHERE race_key = ?", (RACE,))
        conn.execute("DELETE FROM events WHERE id >= 990000")
        conn.execute(
            """INSERT INTO gg_points_standings
                   (race_key, rank, player_name, total_points,
                    member_card_id, fetched_at)
               VALUES (?, '3', 'RIDEOUT, Jeff', 30.0, '12351479',
                       datetime('now', ?))""",
            (RACE, f"-{hours_ago} hours"))
        for i, (d, status) in enumerate(events):
            conn.execute(
                """INSERT INTO events (id, item_name, event_date, chapter, status)
                   VALUES (?, ?, ?, 'San Antonio', ?)""",
                (990000 + i, f"s9.9{i} Test", d, status))
        conn.commit()


def refreshed(hours_ago, events):
    reset(hours_ago, events)
    try:
        db.get_points_race_standings(RACE, db_path=DB)
    except Exception as exc:                       # render needs tables we
        if not _calls:                             # don't care about here —
            raise                                  # only the decision matters
        _ = exc
    return bool(_calls)


print("\n== the defect: an event closes out INSIDE the 12-hour window ==")
check("a snapshot 2 hours old refreshes when an event was played today",
      refreshed(2, [(TODAY, "active")]),
      "the board stays hours behind the rows beside it")
check("…and so does one taken earlier the same day as the event",
      refreshed(6, [(TODAY, "active")]))

print("\n== but it must not thrash ==")
check("a fresh snapshot with NO recent event keeps the long window",
      not refreshed(2, [("2026-01-05", "active")]),
      "a quiet week is making a GG round-trip on every page load")
check("NEXT WEEK's fixture never holds the board open",
      not refreshed(2, [("2099-01-01", "active")]),
      "a scheduled event pins the race in the short window forever")
check("a CANCELLED event on the day awards nothing and triggers nothing",
      not refreshed(2, [(TODAY, "cancelled")]))
check("inside the short window, a just-refreshed snapshot settles",
      not refreshed(0, [(TODAY, "active")]),
      "one refresh per window, not one per page load")

print("\n== the long window and the old guard are intact ==")
check("a 20-hour-old snapshot refreshes once an event has happened since",
      refreshed(20, [(TODAY, "active")]))
check("…but NOT when nothing has happened since it was taken "
      "(Kerry 2026-07-08 — the guard that was already there)",
      not refreshed(20, []))
check("…nor when the only events predate the snapshot entirely",
      not refreshed(20, [("2026-01-05", "active")]))
reset(2, [])
with db._connect(DB) as _c:
    _c.execute("DELETE FROM gg_points_standings WHERE race_key = ?", (RACE,))
    _c.commit()
_calls.clear()
try:
    db.get_points_race_standings(RACE, db_path=DB)
except Exception:
    pass
check("an EMPTY snapshot always refreshes, whatever the calendar says",
      bool(_calls))

print("\n== the timezone trap, which is what actually hid it ==")
# 9:30 PM Central on an event day is already TOMORROW in UTC. Taking
# date() off the stored value put the snapshot a day ahead of the event
# that had just finished, so "an event on or after the snapshot's day"
# excluded it — on exactly the night it mattered.
_snap_utc = "2026-09-16 02:30:00"          # = 2026-09-15 21:30 Central
from email_parser.timezone_utils import to_central as _tc    # noqa: E402
check("a 9:30 PM Central snapshot reads as the EVENT's day, not the next",
      _tc(_snap_utc).date().isoformat() == "2026-09-15",
      str(_tc(_snap_utc)))
check("…and taking date() off the raw stored value would have been wrong",
      _snap_utc[:10] == "2026-09-16")

print("\n== the threshold is a named rule, not a literal ==")
src = open("email_parser/database.py", encoding="utf-8").read()
check("the event-day window has a name",
      "_POINTS_EVENT_DAY_REFRESH_HOURS" in src)
_i = src.index("def get_points_race_standings")
_fn = src[_i:src.index("\ndef ", _i + 1)]
check("…and the staleness test reads it rather than a magic number",
      "_POINTS_EVENT_DAY_REFRESH_HOURS" in _fn
      and f"{db._POINTS_EVENT_DAY_REFRESH_HOURS}" not in _fn.replace(
          "auto_refresh_hours", ""),
      "the number is inlined in the function")
check("the window is shorter than the ordinary one",
      db._POINTS_EVENT_DAY_REFRESH_HOURS < 12,
      str(db._POINTS_EVENT_DAY_REFRESH_HOURS))
check("the 'played since' test is bounded by CENTRAL today, not UTC "
      "(the trap of 2026-09-15, twice in one night)",
      "today_central_str()" in _fn, "bounded by the wrong clock")
check("…and the snapshot's own day is read in Central too",
      "to_central(stat[\"fetched_at\"])" in _fn,
      "date() taken straight off a stored UTC timestamp")
check("the OLD guard was moved onto the same Central day (rule 3d — "
      "across the board, not just the case in front of us)",
      "event_date >= ? LIMIT 1" in _fn and "date(?)" not in _fn,
      "the pre-existing guard still compares against a UTC date")

try:
    os.unlink(DB)
except OSError:
    pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
