"""LIVE POINTS (Kerry 2026-10-28: "Shouldn't we know the points standings
updates during the event too? Live? So when the last score is entered we
already know the winners"). Today's entered event that has not published
gives points SO FAR from the saved strokes (live lines). Season races take
them only at a finale (#2462-F); Monthly at every event (#2466-F). Race close
never treats live lines as the published finale.

Run: python3 test_live_points.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                           # noqa: E402
from email_parser import tracker_points as tp                     # noqa: E402
from email_parser import live_scoring as ls                       # noqa: E402
from email_parser import score_entry as se                        # noqa: E402
from email_parser.timezone_utils import today_central_str          # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


T = today_central_str()
with db._connect(DB) as c:
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format) "
              "VALUES (3305,'s18.12 FALL CHAMPIONSHIP | Kissing Tree',?,'TGF','active','18 Holes')", (T,))
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format) "
              "VALUES (3399,'s9.99 TUESDAY TEST',?,'San Antonio','active','9 Holes')", (T,))
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
              "VALUES (87, 'Adam', 'Baker', 'active_member')")
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
              "VALUES (88, 'Neg', 'Player', 'active_member')")
    c.commit()

CARDS = {"s18.12 FALL CHAMPIONSHIP | Kissing Tree":
         [{"customer_id": 87, "thru": 11, "stableford_net": 25, "points_by_nine": [
             {"nine": "front", "points": 20, "thru": 9}, {"nine": "back", "points": 5, "thru": 2}]},
          {"customer_id": 88, "thru": 18, "stableford_net": -3, "points_by_nine": [
             {"nine": "front", "points": -8, "thru": 9}, {"nine": "back", "points": 5, "thru": 9}]}],
         "s9.99 TUESDAY TEST": [{"customer_id": 87, "thru": 4, "points_by_nine": None, "stableford_net": 9}]}
_r = (se.event_enabled, db.event_engine_state, ls.build_cards, tp.cutover)
se.event_enabled = lambda eid, db_path=None: True
db.event_engine_state = lambda name, db_path=None: {"meta": {"championship": "championship" in name.lower()}, "_n": name}
ls.build_cards = lambda st, f: CARDS[st["_n"]]
tp.cutover = lambda: "2026-01-01"
try:
    lines, w = tp.event_lines(db_path=DB)
    fin = [l for l in lines if l["event_id"] == 3305]
    tue = [l for l in lines if l["event_id"] == 3399]
    f87 = [(l["nine"], l["points"]) for l in fin if l["customer_id"] == 87]
    f88 = [(l["nine"], l["points"]) for l in fin if l["customer_id"] == 88]
    check("the championship (plus event) is ONE 18-hole total, not two nines (Kerry 10/28)",
          f87 == [(None, 25.0)] and all(l["live"] for l in fin), fin)
    check("a negative championship total adds 0, never subtracts (not 0 + 5 by nines)", f88 == [(None, 0.0)], f88)
    check("a Tuesday in play gives a live line too (for Monthly)", [(l["points"], l["live"]) for l in tue] == [(9.0, True)], tue)
    kept = [l for l in lines if not l.get("live") or l.get("championship")]
    check("season races keep the finale's live lines, drop the Tuesday's", {l["event_id"] for l in kept} == {3305}, kept)
    import inspect as _i
    check("the published path makes the same single total for a championship",
          'None if st["meta"].get("championship") else c.get("points_by_nine")' in _i.getsource(tp.event_lines))
    import inspect
    check("build_race applies that filter", "not l.get(\"live\") or l.get(\"championship\")" in inspect.getsource(tp.build_race))
    from email_parser import race_close as rc
    check("race close never counts a live line as the published finale",
          "and not l.get(\"live\")" in inspect.getsource(rc.run))
    from email_parser import scoring_window as sw
    check("the 5-minute job rebuilds while an event is in play", "refresh_live_points" in inspect.getsource(sw.tick))
finally:
    se.event_enabled, db.event_engine_state, ls.build_cards, tp.cutover = _r

try:
    os.remove(DB)
except OSError:
    pass
print("\nALL PASS" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
