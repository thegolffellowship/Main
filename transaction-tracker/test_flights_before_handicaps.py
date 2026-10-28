"""FLIGHTS BEFORE HANDICAPS, a hard order (Kerry 2026-10-28 via Event Ops
#2462: "Definitely need to make sure flights are frozen before handicaps are
posted an updated"). Posting handicap rounds for a Tracker-scored event first
brings its flights board to FROZEN (freeze + settle); if that fails, nothing
posts. A dry run says it would. A Golf Genius-era event is left alone.

Run: python3 test_flights_before_handicaps.py
"""
import os, sys, tempfile, logging, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                           # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


with db._connect(DB) as c:
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format) "
              "VALUES (3303,'s9.29 SILVERHORN','2026-10-27','San Antonio','active','9 Holes')")
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format) "
              "VALUES (3000,'s9.10 OLD GG','2026-09-01','San Antonio','active','9 Holes')")
    c.commit()

calls = []
_real_prev, _real_close = db.get_scoring_handicap_preview, db.close_event_flights


def fake_prev(q, db_path=None):
    return {"events_matched": [q], "rounds": [], "summary": {"cap_changes_differential": 0}}


def traced_close(eid, **kw):
    calls.append(("close", eid))
    return _real_close(eid, **kw)


db.get_scoring_handicap_preview = fake_prev
db.close_event_flights = traced_close
try:
    d = db.derive_handicap_rounds_from_scoring("s9.29 SILVERHORN", dry_run=True, db_path=DB)
    check("dry run: says it would freeze + settle first, freezes nothing",
          not calls and d["flights_first"] and "freeze" in d["flights_first"][0].get("would", ""), d)
    a = db.derive_handicap_rounds_from_scoring("s9.29 SILVERHORN", dry_run=False, db_path=DB)
    check("apply: the flights are closed out BEFORE the post", calls == [("close", 3303)] and not a.get("error"), (calls, a))
    with db._connect(DB) as c:
        snaps = db._active_flight_snapshots(c, 3303)
    check("the board is frozen/settled after the post", bool(snaps["frozen"] or snaps["settled"]))
    calls.clear()
    db.derive_handicap_rounds_from_scoring("s9.29 SILVERHORN", dry_run=False, db_path=DB)
    check("already frozen: no second close", calls == [], calls)
    db.derive_handicap_rounds_from_scoring("s9.10 OLD GG", dry_run=False, db_path=DB)
    check("a Golf Genius-era event is left alone", calls == [], calls)

    with db._connect(DB) as c:
        c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format) "
                  "VALUES (3304,'s9.30 FAILS','2026-10-27','San Antonio','active','9 Holes')")
        c.commit()
    db.close_event_flights = lambda eid, **kw: {"ok": False, "error": "board unreadable"}
    r = db.derive_handicap_rounds_from_scoring("s9.30 FAILS", dry_run=False, db_path=DB)
    check("a failed freeze refuses the post with the reason", "flights could not be frozen" in (r.get("error") or "")
          and "written" not in r, r)
finally:
    db.get_scoring_handicap_preview, db.close_event_flights = _real_prev, _real_close

try:
    os.remove(DB)
except OSError:
    pass
print("\nALL PASS" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
