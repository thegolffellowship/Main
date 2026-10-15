"""The EVENTS board shows the Tracker's own flights for an event Golf Genius
does not score (Kerry 2026-10-13: "It doesn't look like flights are showing
where they should on the leaderboard"). The flights are the flight board's
SELECTION, the same one the payouts are paid on; Golf Genius flights still
win when they exist.

Run: python3 test_board_engine_flights.py
"""
import contextlib
import io
import logging
import json, os
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


EV, NAME = 951, "s9.27 Flight Links"
PLAYERS = [(601, "Low", "One", 2), (602, "Low", "Two", 6), (603, "High", "One", 15),
           (604, "High", "Two", 18), (605, "Mid", "Nobuy", 9)]
c = sqlite3.connect(DB)
for cid, fn, ln, _ in PLAYERS:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
course_id = c.execute("INSERT INTO courses (name, status) VALUES ('Flight Links', 'active') "
                      "RETURNING course_id").fetchone()[0]
c.execute("INSERT INTO events (id, item_name, event_date, course_id, course, chapter, format) "
          "VALUES (?,?,?,?,?,?,?)",
          (EV, NAME, "2026-10-13", course_id, "Flight Links", "San Antonio", "9 Holes"))
db._ensure_scoring_tables(c); db._ensure_pairing_tables(c)
db._ensure_gg_game_flights_tables(c); db._ensure_gg_game_results_tables(c)
for cid, fn, ln, ph in PLAYERS:
    rid = c.execute(
        "INSERT INTO scoring_rounds (customer_id, player_name, event_id, gg_aggregate_id, round_date, "
        "course_id, holes_played, playing_handicap, gross, net, source, imported_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id",
        (cid, f"{fn} {ln}", EV, "entry:1", "2026-10-13", course_id, 9, ph, 45, 45 - ph,
         "entry", "2026-10-14 00:09:14")).fetchone()[0]
    for h in range(1, 10):
        c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes, strokes_received) "
                  "VALUES (?,?,?,?)", (rid, h, 5, 0))
c.commit(); c.close()


def board(eid, db_path=None):
    def fl(no, band, cids):
        return {"flight_no": no, "band": band, "label": "x",
                "members": [{"customer_id": cid} for cid in cids]}
    return {"games": [
        {"game": "individual_net", "active": True,
         "selection": {"flights": [fl(1, "<12.0", [601, 602]), fl(2, "12.0+", [603, 604])]}},
        {"game": "skins", "active": True,
         "selection": {"flights": [fl(1, "All handicaps", [601, 602, 603, 604])]}},
    ]} if eid == EV else None


db.event_flights_board = board
lb = db.get_event_leaderboard(NAME, db_path=DB) or {}
net = lb.get("net_board") or []
check("Ind Net is sectioned into the flight board's two flights",
      [s["label"] for s in net][:2] == ["Flight 1 (HCP <12.0)", "Flight 2 (HCP 12.0+)"],
      [s["label"] for s in net])
by = {s["label"]: sorted(r["customer_id"] for r in s["rows"]) for s in net}
check("buyers sit in their own flight",
      {601, 602} <= set(by.get("Flight 1 (HCP <12.0)", [])) and
      {603, 604} <= set(by.get("Flight 2 (HCP 12.0+)", [])), by)
check("a non-buyer with no index is listed apart, never dropped (placement is by index)",
      605 in by.get("UNFLIGHTED", []), by)
check("a one-flight game shows no flights", [s["label"] for s in lb.get("skins_board") or []] == [None],
      [s["label"] for s in lb.get("skins_board") or []])
ov = {r["customer_id"]: r for r in lb.get("overall_board") or []}
check("the overall board carries the net flight", ov.get(603, {}).get("net_flight") == 2,
      ov.get(603))

c = sqlite3.connect(DB)
c.execute("INSERT INTO gg_game_flights (event_id, gg_tournament_id, game, flight_label, customer_id, player_name) "
          "VALUES (?,?,?,?,?,?)", (EV, "t1", "individual_net", "LOW FLIGHT", 601, "Low One"))
c.commit(); c.close()
lb = db.get_event_leaderboard(NAME, db_path=DB) or {}
check("a Tracker-scored event ignores a stored Golf Genius flight (GAMES only)",
      "LOW FLIGHT" not in [s["label"] for s in lb.get("net_board") or []]
      and [s["label"] for s in lb.get("net_board") or []][:2] == ["Flight 1 (HCP <12.0)", "Flight 2 (HCP 12.0+)"],
      [s["label"] for s in lb.get("net_board") or []])

# F1 (Kerry 10/14, #1817): the Games tab's winner rows come from the engine
# on the flight board for a Tracker-scored event, never from GG flight labels.
_real_buyers = db._event_game_buyers
db._event_game_buyers = lambda conn, name, kind: (
    {"buyers": {601, 602, 603, 604}, "no_customer_id": []} if name == NAME else _real_buyers(conn, name, kind))
gr0 = db.determine_event_game_results(NAME, "individual_net", flights=2, db_path=DB)
check("F1: no tee on the cards → awaiting results with the engine's reason, never GG",
      gr0.get("source") == "engine" and gr0.get("status") == "awaiting_results" and "tee" in (gr0.get("why") or ""), gr0)
# The engine itself is covered elsewhere; here, its board → the Games tab shape.
from email_parser import live_scoring as _lsm
_real_state, _real_lb = db.event_engine_state, _lsm.compute_leaderboard
db.event_engine_state = lambda name, db_path=None: {"players": [{"key": "c:601"}], "meta": {}}
def _row(cid, nm, place, score, ph):
    return {"customer_id": cid, "name": nm, "place": place, "score": score,
            "playing_handicap": ph, "complete": True}
_lsm.compute_leaderboard = lambda st, f: {"games": {
    "individual_net": {"active": True, "flight_source": "frozen", "flights": [
        {"flight": 1, "players": 2, "rows": [_row(601, "Low One", 1, 43, 2), _row(602, "Low Two", 2, 39 + 5, 6)]},
        {"flight": 2, "players": 2, "rows": [_row(603, "High One", 1, 30, 15), _row(604, "High Two", 1, 30, 18)]}]},
    "skins": {"active": True, "flights": [
        {"flight": 1, "players": 4, "tally": [{"name": "Low One", "skins": 2}, {"name": "High Two", "skins": 1}]}]}}}
gr = db.determine_event_game_results(NAME, "individual_net", flights=2, db_path=DB)
check("F1: Games tab Ind Net winners come from the engine on the flight board",
      gr.get("source") == "engine" and gr.get("status") == "determined"
      and [f["flight"] for f in gr.get("flights") or []] == ["Flight 1", "Flight 2"]
      and sorted(r["customer_id"] for r in gr["flights"][0]["ranking"]) == [601, 602], gr)
check("F1: no Golf Genius flight label reaches the Games tab",
      "LOW FLIGHT" not in json.dumps(gr) and gr.get("status") != "flights_unknown", gr)
sk = db.determine_event_game_results(NAME, "skins", flights=1, db_path=DB)
check("F1: skins come back in the Games tab's shape (skin_count, per_player)",
      sk.get("source") == "engine" and sk.get("status") == "determined"
      and all("per_player" in f and "skin_count" in f for f in sk.get("flights") or []), sk)
check("F1: a tie keeps its shared place", [r["position"] for r in gr["flights"][1]["ranking"]] == [1, 1], gr)
check("F1: skins tally per player", sk["flights"][0]["per_player"] == {"Low One": 2, "High Two": 1}
      and sk["flights"][0]["skin_count"] == 3, sk)
db._event_game_buyers = _real_buyers
db.event_engine_state, _lsm.compute_leaderboard = _real_state, _real_lb

# A GG-era event (before the untether date) keeps the record it was played under.
OLD, OLD_NAME = 952, "s9.1 Old Links"
c = sqlite3.connect(DB)
c.execute("INSERT INTO events (id, item_name, event_date, course_id, course, chapter, format) "
          "VALUES (?,?,?,?,?,?,?)", (OLD, OLD_NAME, "2026-09-01", course_id, "Flight Links",
                                     "San Antonio", "9 Holes"))
for cid, fn, ln, ph in PLAYERS[:2]:
    rid = c.execute(
        "INSERT INTO scoring_rounds (customer_id, player_name, event_id, gg_aggregate_id, round_date, "
        "course_id, holes_played, playing_handicap, gross, net, source, imported_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id",
        (cid, f"{fn} {ln}", OLD, f"gg:{cid}", "2026-09-01", course_id, 9, ph, 45, 45 - ph,
         "gg", "2026-09-02 00:09:14")).fetchone()[0]
    for h in range(1, 10):
        c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes, strokes_received) "
                  "VALUES (?,?,?,?)", (rid, h, 5, 0))
for cid, lab in ((601, "LOW FLIGHT"), (602, "HIGH FLIGHT")):
    c.execute("INSERT INTO gg_game_flights (event_id, gg_tournament_id, game, flight_label, customer_id, "
              "player_name) VALUES (?,?,?,?,?,?)", (OLD, "t2", "individual_net", lab, cid, str(cid)))
c.commit(); c.close()
lb = db.get_event_leaderboard(OLD_NAME, db_path=DB) or {}
check("a GG-era event keeps its Golf Genius flights (history)",
      sorted(s["label"] for s in lb.get("net_board") or []) == ["HIGH FLIGHT", "LOW FLIGHT"],
      [s["label"] for s in lb.get("net_board") or []])
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_parser", "database.py")).read()
check("the board reads GG results only for a GG-era event",
      'FROM gg_game_results WHERE event_id = ? AND ? = 1' in src
      and 'FROM gg_game_flights WHERE event_id = ? AND ? = 1' in src)
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
