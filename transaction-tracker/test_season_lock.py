"""THE REGULAR SEASON LOCK (Kerry 2026-10-28: "The regular season is over as of
yesterday so the current scores (best 6) should be locked. So there's an
automatic starting point that won't update similar to our city and TGF
championship live leaderboards"). A locked race's totals through the lock
date stay put; a rebuild reads only later events (the finale), so the board
can refresh every minute on the day.

Run: python3 test_season_lock.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                           # noqa: E402
from email_parser import tracker_points as tp                     # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []
RK = "san_antonio_fall_net"


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


with db._connect(DB) as c:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (999001, 'Zed', 'Tester')")
    c.commit()


def ln(date, pts, champ=False, live=False, eid=1):
    return {"customer_id": 999001, "player_name": "Zed Tester", "chapter": "San Antonio", "member": True,
            "date": date, "event_id": eid, "code": "s9.1", "championship": champ, "live": live,
            "nine": None, "points": pts}


REG = [ln("2026-10-20", 10, eid=1), ln("2026-10-27", 8, eid=2)]
calls = []
_real = tp.event_lines


def fake(db_path=None, through=None, since=None):
    calls.append(since)
    rows = REG + [ln("2026-10-31", 20, champ=True, live=True, eid=3)]
    rows = [r for r in rows if (not through or r["date"] <= through) and (not since or r["date"] > since)]
    return [dict(r) for r in rows], []


tp.event_lines = fake
try:
    z = lambda b: next((r for r in b["rows"] if r["customer_id"] == 999001), None)
    before = z(tp.build_race(RK, db_path=DB))["total_points"]
    d = tp.lock_season(RK, "2026-10-27", apply=False, db_path=DB)
    check("dry run locks nothing", tp.season_lock(RK, db_path=DB) is None and d["players"] > 0, d)
    a = tp.lock_season(RK, "2026-10-27", apply=True, db_path=DB)
    lk = tp.season_lock(RK, db_path=DB)
    check("locked through 10/27", lk and lk["through"] == "2026-10-27", lk and lk["through"])
    calls.clear()
    b = tp.build_race(RK, db_path=DB)
    check("a locked rebuild reads only events after the lock", calls == ["2026-10-27"], calls)
    check("total = locked regular season + the finale's points", z(b)["total_points"] == before, (z(b), before))
    REG.append(ln("2026-10-25", 50, eid=9))   # a late change to the regular season
    b2 = tp.build_race(RK, db_path=DB)
    check("the regular season no longer moves", z(b2)["total_points"] == before, z(b2))
    check("unlock clears it", tp.unlock_season(RK, db_path=DB)["unlocked"] and tp.season_lock(RK, db_path=DB) is None)
finally:
    tp.event_lines = _real

try:
    os.remove(DB)
except OSError:
    pass
print("\nALL PASS" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
