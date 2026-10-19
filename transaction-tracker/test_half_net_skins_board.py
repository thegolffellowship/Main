"""½ Net Skins on the EVENTS leaderboard (Kerry 10/19: "Skins 1/2 Net is
simple because there's only one flight, so it's the field of players who
actually bought in...not the whole field... Build the 1/2 Net Skins today").

Below the matrix's buyer band the Skins game is ½ Net: each BUYER plays off
50% of his playing handicap, rounded once, off the lowest BUYER, on his own
tee's stroke index. The board circles the low NET score on a hole and shows
those pops; a frozen flight board's variant wins over the buyer count.

Run: python3 test_half_net_skins_board.py
"""
import contextlib
import io
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

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


EV, NAME = 961, "s9.29 Half Net Links"
# cid, name, playing handicap, {hole: gross} (every other hole is a 5)
PLAYERS = [(701, "Al Low", 2, {1: 4, 9: 4}),
           (702, "Bo Mid", 10, {}),
           (703, "Cy High", 18, {}),
           (704, "Di Six", 6, {}),
           (705, "Ed Nobuy", 30, {7: 4})]
BUYERS = {701, 702, 703, 704}
c = sqlite3.connect(DB)
course_id = c.execute("INSERT INTO courses (name, status) VALUES ('Half Net Links', 'active') "
                      "RETURNING course_id").fetchone()[0]
tee = c.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, nine, rating, "
                "slope, tgf_bands, source) VALUES (?, 'White', 'M', 9, 'front', 34.0, 120, "
                "'50-64', 'admin') RETURNING tee_id", (course_id,)).fetchone()[0]
for h in range(1, 10):
    c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, stroke_index) "
              "VALUES (?,?,?,?)", (tee, h, 4, h))
c.execute("INSERT INTO events (id, item_name, event_date, course_id, course, chapter, format) "
          "VALUES (?,?,?,?,?,?,?)",
          (EV, NAME, "2026-10-20", course_id, "Half Net Links", "San Antonio", "9 Holes"))
db._ensure_scoring_tables(c); db._ensure_pairing_tables(c)
db._ensure_gg_game_flights_tables(c); db._ensure_gg_game_results_tables(c)
for cid, nm, ph, hs in PLAYERS:
    fn, ln = nm.split()
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
    gross = sum(hs.get(h, 5) for h in range(1, 10))
    rid = c.execute(
        "INSERT INTO scoring_rounds (customer_id, player_name, event_id, gg_aggregate_id, round_date, "
        "course_id, tee_id, holes_played, playing_handicap, gross, net, source, imported_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id",
        (cid, nm, EV, "entry:1", "2026-10-20", course_id, tee, 9, ph, gross, gross - ph,
         "entry", "2026-10-20 23:09:14")).fetchone()[0]
    for h in range(1, 10):
        c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes, strokes_received) "
                  "VALUES (?,?,?,?)", (rid, h, hs.get(h, 5), 0))
c.commit(); c.close()

_real_buyers = db._event_game_buyers
db._event_game_buyers = lambda conn, name, kind: (
    {"buyers": {b: {} for b in BUYERS}, "no_customer_id": []} if name == NAME else _real_buyers(conn, name, kind))
FB = {"board": None}
db.event_flights_board = lambda eid, db_path=None: FB["board"] if eid == EV else None

lb = db.get_event_leaderboard(NAME, db_path=DB) or {}
rid = {r["customer_id"]: str(r["scoring_round_id"]) for r in lb.get("overall_board") or []}
sv = lb.get("skins_variant") or {}
check("4 buyers on a nine runs ½ Net Skins", sv.get("name") == "half_net" and sv.get("basis") == "net", sv)
check("the dials are 50%, off the lowest", sv.get("allowance_pct") == 50 and sv.get("off_lowest") is True, sv)

pops = lb.get("skin_pops") or {}
# PH 2/10/18/6 -> x50% half-up 1/5/9/3 -> off the lowest buyer (1): 0/4/8/2
check("Al (lowest buyer) plays off 0", (pops.get(rid[701]) or {}).get("strokes") == 0, pops.get(rid[701]))
check("Bo: 10 x 50% = 5, less the lowest 1 = 4 strokes on SI 1-4",
      (pops.get(rid[702]) or {}).get("strokes") == 4
      and (pops.get(rid[702]) or {}).get("by_hole") == {"1": 1, "2": 1, "3": 1, "4": 1}, pops.get(rid[702]))
check("Cy: 18 x 50% = 9, less 1 = 8", (pops.get(rid[703]) or {}).get("strokes") == 8, pops.get(rid[703]))
check("Di: 6 x 50% = 3, less 1 = 2", (pops.get(rid[704]) or {}).get("strokes") == 2, pops.get(rid[704]))
check("a non-buyer carries no game pops (he is not in the game)", rid[705] not in pops, sorted(pops))

cells = lb.get("skin_cells") or {}
check("hole 1: Al's gross 4 ties three net 4s, so NO skin (gross skins would have paid him)",
      1 not in (cells.get(rid[701]) or []), cells)
check("hole 9: Al's 4 is the low net alone -> his skin", cells.get(rid[701]) == [9], cells)
check("holes 5-8: Cy's pop makes his 5 a net 4, alone -> his skins",
      cells.get(rid[703]) == [5, 6, 7, 8], cells)
check("nobody else wins a skin", set(cells) <= {rid[701], rid[703]}, cells)
ghost = lb.get("ghost_skin_cells") or {}
check("the non-buyer's would-be net win on 7 is a ghost circle only",
      7 in (ghost.get(rid[705]) or []) and rid[705] not in cells, ghost)

# The board and the money agree: the engine that pays Skins circles the same holes.
from email_parser import live_scoring as _ls
_st = db.event_engine_state(NAME, db_path=DB)
_eng = _ls.compute_leaderboard(_st, db.get_scoring_formulas(DB))["games"]["skins"]
_won = {}
for f in _eng["flights"]:
    for sk in f["skins"]:
        _won.setdefault(sk["key"], []).append(sk["hole"])
check("the paying engine runs the same game", _eng.get("variant") == "half_net", _eng.get("variant"))
check("the paying engine circles the same holes", _won == cells, (_won, cells))

# A frozen flight board that froze GROSS skins holds the game (B5).
FB["board"] = {"state": "frozen", "games": [
    {"game": "skins", "active": True,
     "selection": {"variant": {"name": "gross"}, "flights": []}}]}
lb = db.get_event_leaderboard(NAME, db_path=DB) or {}
check("a frozen GROSS selection keeps gross skins", (lb.get("skins_variant") or {}).get("basis") == "gross",
      lb.get("skins_variant"))
check("gross skins: Al's 4 on hole 1 and 9 are skins, no pops",
      (lb.get("skin_cells") or {}).get(rid[701]) == [1, 9] and not lb.get("skin_pops"),
      (lb.get("skin_cells"), lb.get("skin_pops")))

os.unlink(DB)
print("\nALL PASS" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
