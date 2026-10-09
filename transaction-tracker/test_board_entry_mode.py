"""FINDING 0 (CoS #1333, 2026-10-07): an event in ENTRY MODE (score entry
on for it, with a non-preview score-entry round) puts its ENTERED scores on
the Events leaderboard, and never the Golf Genius import. Kerry (#1313):
"audit actual tracker entered scores ... without any importing from GG.
That should have been off."

- Entry mode: the board shows the phone-entered gross for every entered
  player (part-played cards too), with pops on his own tee; a GG row for
  the same event and player is NOT shown.
- Not in entry mode (switch off, or only a PREVIEW round): the board reads
  the record as before.
- Nothing is written: scoring_rounds / scoring_holes are unchanged.

Run: python3 test_board_entry_mode.py
"""
import contextlib
import io
import json
import logging
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    db.init_db(DB)
from email_parser import score_entry as se  # noqa: E402
from email_parser import entry_publish as ep  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


from email_parser.timezone_utils import today_central_str  # noqa: E402
TODAY = today_central_str()
EV, NAME = 930, "s10.13 Entry Links"
conn = sqlite3.connect(DB)
for cid, fn, ln in [(301, "Kerry", "Niester"), (302, "Adam", "Baker"), (303, "Pat", "Youngs")]:
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)",
                 (cid, fn, ln))
course_id = conn.execute("INSERT INTO courses (name, status) VALUES ('Entry Links', 'active') "
                         "RETURNING course_id").fetchone()[0]
tee = conn.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, nine, rating, "
                   "slope, tgf_bands, source) VALUES (?, 'White', 'M', 9, 'front', 34.0, 120, "
                   "'50-64', 'admin') RETURNING tee_id", (course_id,)).fetchone()[0]
NINE = [(1, 4, 3), (2, 3, 9), (3, 5, 1), (4, 4, 5), (5, 4, 7), (6, 3, 8), (7, 4, 2), (8, 4, 6), (9, 5, 4)]
for h, par, si in NINE:
    conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, stroke_index) "
                 "VALUES (?,?,?,?)", (tee, h, par, si))
conn.execute("INSERT INTO events (id, item_name, event_date, course_id, format) VALUES (?,?,?,?,?)",
             (EV, NAME, TODAY, course_id, "9 Holes"))
# The Golf Genius import that must NOT show in entry mode: Kerry at 50.
gg = conn.execute("INSERT INTO scoring_rounds (customer_id, player_name, event_id, gg_aggregate_id, "
                  "round_date, course_id, tee_id, holes_played, playing_handicap, gross, net, "
                  "source, imported_at) VALUES (301, 'Kerry Niester', ?, 'gg:1', ?, ?, ?, "
                  "9, 5, 50, 45, 'gg', '2026-10-13 23:00:00') RETURNING id",
                  (EV, TODAY, course_id, tee)).fetchone()[0]
for h, par, si in NINE:
    conn.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes, strokes_received) "
                 "VALUES (?,?,?,0)", (gg, h, par + 2 if h <= 5 else par + 1))
db._ensure_scoring_tables(conn)
db._ensure_pairing_tables(conn)
db._ensure_gg_game_flights_tables(conn)
db._ensure_gg_game_results_tables(conn)
conn.commit()
conn.close()


def counts():
    c = sqlite3.connect(DB)
    try:
        return (c.execute("SELECT COUNT(*) FROM scoring_rounds").fetchone()[0],
                c.execute("SELECT COUNT(*) FROM scoring_holes").fetchone()[0])
    finally:
        c.close()


def board_gross():
    d = db.get_event_leaderboard(NAME, db_path=DB) or {}
    found = {}
    def walk(x):
        if isinstance(x, dict):
            if x.get("customer_id") in (301, 302, 303) and "gross" in x:
                found.setdefault(x["customer_id"], x["gross"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(d)
    return d, found


print("before any score entry: the board reads the record (GG Kerry 50)")
d0, g0 = board_gross()
check("record mode shows the GG gross", g0.get(301) == 50, g0)
check("score_source says record", (d0.get("event") or {}).get("score_source") == "record",
      (d0.get("event") or {}).get("score_source"))

COURSE = [{"hole": h, "par": p, "stroke_index": si} for h, p, si in NINE]
rid = se.create_round(EV, 9, round_date=TODAY, label="s10.13", course_holes=COURSE,
                      course_id=course_id, db_path=DB)["round_id"]
gid = se.upsert_group(rid, 1, players=[
    {"customer_id": 301, "display_name": "Kerry N", "tee": "50-64", "playing_handicap": 5},
    {"customer_id": 302, "display_name": "Adam B", "tee": "50-64", "playing_handicap": 3},
], db_path=DB)["group_id"]
se.claim_group(gid, "dev1", 301, db_path=DB)
CARD = {1: 5, 2: 3, 3: 6, 4: 4, 5: 5, 6: 3, 7: 4, 8: 5, 9: 6}   # 41
ops, n = [], 0
for h, g in CARD.items():
    n += 1
    ops.append({"op_id": f"k{n}", "hole": h, "gross": g, "customer_id": 301})
for h in (1, 2, 3):                                              # Adam part-played: 3 holes
    n += 1
    ops.append({"op_id": f"a{n}", "hole": h, "gross": CARD[h], "customer_id": 302})
r = se.write_scores(gid, "dev1", 301, ops, db_path=DB)
assert all(x["result"] == "ok" for x in r["results"]), r

print("score entry OFF for the event: still the record")
_, g1 = board_gross()
check("switch off -> GG gross still shown", g1.get(301) == 50, g1)

db.set_app_setting("score_entry_live", "1", db_path=DB)
db.set_app_setting("score_entry_events", json.dumps([EV]), db_path=DB)
before = counts()
print("ENTRY MODE: entered scores only")
d2, g2 = board_gross()
check("entry_mode is true", ep.entry_mode(EV, db_path=DB))
check("Kerry shows his ENTERED 41, not GG's 50", g2.get(301) == 41, g2)
check("Adam's part-played card shows (3 holes, 14)", g2.get(302) == 14, g2)
check("score_source says entry", (d2.get("event") or {}).get("score_source") == "entry")
check("nothing written to scoring_rounds / scoring_holes", counts() == before, f"{before} -> {counts()}")
rows = ep.live_board_rows(sqlite3.connect(DB), EV, db_path=DB) if False else None
c = db.get_connection(DB)
live = {r["customer_id"]: r for r in ep.live_board_rows(c, EV, db_path=DB)}
c.close()
check("Kerry's live pops follow his PH 5 on the stroke index (SI 1-5 holes 3,7,1,9,4)",
      sorted(h for h, v in live[301]["strokes_received"].items() if v) == [1, 3, 4, 7, 9],
      live[301]["strokes_received"])
check("Adam's pops on the played holes keep their full-round places (PH 3: SI 1-3 = holes 3,7,1)",
      sorted(h for h, v in live[302]["strokes_received"].items() if v) == [1, 3],
      live[302]["strokes_received"])

print("a round dated another day is not entry mode (past events stay frozen)")
c = sqlite3.connect(DB)
c.execute("UPDATE se_rounds SET round_date = '2026-09-29' WHERE id = ?", (rid,))
c.commit()
c.close()
_, g3 = board_gross()
check("the day after: the board reads the record again (GG 50)", g3.get(301) == 50, g3)
check("entry_mode false for a past-dated round", not ep.entry_mode(EV, db_path=DB))

print("a PREVIEW round alone is not entry mode")
db.set_app_setting("score_entry_events", json.dumps([]), db_path=DB)
EV2, NAME2 = 931, "s10.20 Entry Links"
c = sqlite3.connect(DB)
c.execute("INSERT INTO events (id, item_name, event_date, course_id, format) VALUES (?,?,?,?,?)",
          (EV2, NAME2, "2026-10-20", course_id, "9 Holes"))
c.commit()
c.close()
db.set_app_setting("score_entry_events", json.dumps([EV2]), db_path=DB)
try:
    se.create_preview_round(EV2, [301], db_path=DB)
    check("preview-only event is not in entry mode", not ep.entry_mode(EV2, db_path=DB))
except Exception as e:  # noqa: BLE001
    check("preview round fixture", False, repr(e))

print("a round dated TOMORROW with no GG import (Kerry 10/8, testing Friday's practice round Thursday night)")
import datetime as _dt
TOMORROW = (_dt.date.fromisoformat(TODAY) + _dt.timedelta(days=1)).isoformat()
EV3, NAME3 = 932, "LSC PRACTICE ROUND | Entry Links"
c = sqlite3.connect(DB)
c.execute("INSERT INTO events (id, item_name, event_date, course_id, format) VALUES (?,?,?,?,?)",
          (EV3, NAME3, TOMORROW, course_id, "9 Holes"))
c.commit()
c.close()
db.set_app_setting("score_entry_events", json.dumps([EV, EV2, EV3]), db_path=DB)
r3 = se.create_round(EV3, 9, round_date=TOMORROW, label="practice", course_holes=COURSE,
                     course_id=course_id, db_path=DB)["round_id"]
g3id = se.upsert_group(r3, 1, players=[
    {"customer_id": 301, "display_name": "Kerry N", "tee": "50-64", "playing_handicap": 5},
    {"customer_id": 303, "display_name": "Pat Y", "tee": "50-64", "playing_handicap": 0}], db_path=DB)["group_id"]
lst = lambda: {e["id"]: e for e in db.get_events_leaderboard(db_path=DB)["events"]}
check("no score yet: not listed", EV3 not in lst())
se.claim_group(g3id, "dev3", 301, db_path=DB)
se.write_scores(g3id, "dev3", 301, [{"op_id": f"p{h}-{cid}", "hole": h, "gross": 4, "customer_id": cid}
                                     for h in (1, 2, 3, 4) for cid in (301, 303)], db_path=DB)
check("a future-dated round with scores is entry mode", ep.entry_mode(EV3, db_path=DB))
L = lst()
check("the events list carries it (no Golf Genius rows needed)", EV3 in L and L[EV3]["field"] == 2, L.get(EV3))
check("it is in play, not final (holes still to post)", L.get(EV3, {}).get("money_visible") is False
      and L.get(EV3, {}).get("money_reason") == "scores", L.get(EV3))
d3 = db.get_event_leaderboard(NAME3, db_path=DB) or {}
check("its board reads the entered cards", (d3.get("event") or {}).get("score_source") == "entry",
      (d3.get("event") or {}).get("score_source"))
check("the list leaves no temp tables behind (the record reads normally after)",
      lst().get(EV, {}).get("field") is not None)
before3 = counts()
check("listing wrote nothing to the record", before3 == counts())

print(f"\n{'ALL PASS' if not FAILURES else str(len(FAILURES)) + ' FAILED: ' + str(FAILURES)}")
sys.exit(1 if FAILURES else 0)
