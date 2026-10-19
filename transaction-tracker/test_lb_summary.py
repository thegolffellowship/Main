"""EVENTS BOARD server side: state words, projected WON, pots, Match Play
(Kerry 2026-10-19, leaderboard review sections 12-13, B10-B12).

- board_state: UPCOMING / LIVE / IN REVIEW / FINAL from the board payload,
  recorded payouts and the auto-payouts preview.
- Projected money reuses the payouts assembly: `assemble_event_game_payouts`
  with projected=True lets a game still in play ('provisional') pay what it
  would now, reads the LIVE entered cards (event_engine_state(live=True)),
  and the default path is unchanged. City MVP projects off the board's
  points order. Team purses go through the recorded slot rule.
- attach() decorates the payload and WRITES NOTHING.
- Match Play: matches tied to the event by cmp_matches.event_id /
  cmp_bracket.event_id, in the standard card's row shape.

Run: python3 test_lb_summary.py
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
from email_parser import board_summary as bs  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


print("board_state (the four words)")
check("no cards -> upcoming", bs.board_state({"field": 0, "holes_posted": 0}) == "upcoming")
check("cards out -> live", bs.board_state({"field": 4, "holes_posted": 10, "field_complete": False}) == "live")
check("field in, nothing recorded -> in review",
      bs.board_state({"field": 4, "holes_posted": 36, "field_complete": True}) == "in_review")
check("field in, preview not final -> in review",
      bs.board_state({"field": 4, "field_complete": True}, 0, False) == "in_review")
check("field in, every card final -> final",
      bs.board_state({"field": 4, "field_complete": True}, 0, True) == "final")
check("field in, payouts recorded -> final",
      bs.board_state({"field": 4, "field_complete": True}, 3, False) == "final")
check("an unlock (card out again) -> live, not final",
      bs.board_state({"field": 4, "field_complete": False}, 3, True) == "live")

print("projected rows: a game still in play pays what it would now")
_real_egp = db.engine_game_payouts
_real_ees = db.event_engine_state
SEEN = {}


def _fake_egp(name, db_path=None, state=None, board=None):
    SEEN["state"] = state
    return {"games": {
        "individual_net": {"status": "provisional", "notes": ["in play"], "unallocated": [],
                           "rows": [{"customer_id": 1, "name": "Adam Baker", "amount": 60.0,
                                     "detail": "F1 1st"}]},
        "skins": {"status": "paid", "unallocated": [],
                  "rows": [{"customer_id": 2, "name": "Bob Skins", "amount": 22.5,
                            "detail": "Skins F1 ×1 holes 2"}]}}}


db.engine_game_payouts = _fake_egp
db.event_engine_state = lambda name, db_path=None, live=False: {"live": live}
notes = []
proj = db._engine_flight_payout_rows("x", notes, db_path=DB, projected=True)
check("projected: the provisional Net row is paid", any(r["category"] == "individual_net" and r["amount"] == 60.0
                                                        for r in proj), proj)
check("projected: the engine read the LIVE cards", SEEN.get("state") == {"live": True}, SEEN)
notes = []
rec = db._engine_flight_payout_rows("x", notes, db_path=DB)
check("record path unchanged: a provisional game is skipped",
      not any(r["category"] == "individual_net" for r in rec) and any("provisional" in n for n in notes), (rec, notes))
check("record path unchanged: the engine reads the record (no state passed)", SEEN.get("state") is None)
check("both paths pay the finished game", any(r["category"] == "skins" for r in rec)
      and any(r["category"] == "skins" for r in proj))
db.engine_game_payouts, db.event_engine_state = _real_egp, _real_ees

print("City MVP projected off the board's points order")
pb = [{"player_name": "Mike Mvp", "customer_id": 3, "buyer": True, "net_pts": 14, "mvp_note": "MVP tiebreak 1"},
      {"player_name": "Ann Two", "customer_id": 5, "buyer": True, "net_pts": 14, "mvp_note": "MVP tiebreak: Net 37"},
      {"player_name": "Non Buyer", "customer_id": 6, "buyer": False, "net_pts": 20}]
cm = db._projected_city_mvp({"points_board": pb})
check("the first MVP-eligible buyer wins (non-buyer ignored)",
      cm and cm["status"] == "determined" and [w["customer_id"] for w in cm["winners"]] == [3], cm)
pb2 = [dict(pb[0], mvp_note="MVP tiebreak 3 — split pot"), dict(pb[1], mvp_note="MVP tiebreak 3 — split pot")]
cm2 = db._projected_city_mvp({"points_board": pb2})
check("tiebreak 3 splits the pot", cm2["split"] and len(cm2["winners"]) == 2, cm2)
check("nobody with points -> nothing", db._projected_city_mvp({"points_board": []}) is None)

print("projection shape: per-customer by category, team purse by slot rule")
lb = {"teams": [{"players": [{"customer_id": 1, "scoring_round_id": -1, "player_name": "Adam Baker"},
                             {"customer_id": 4, "scoring_round_id": -4, "player_name": "Pat Plain"}]}]}
rows = [{"customer_id": 1, "category": "individual_net", "amount": 60.0},
        {"customer_id": 1, "category": "team_net", "amount": 40.0},
        {"customer_id": 4, "category": "team_net", "amount": 40.0},
        {"customer_id": 2, "category": "skins", "amount": 22.5},
        {"customer_id": None, "category": "ctp", "amount": 15.0}]
sh = bs.shape_projection(lb, rows)
check("by customer, by category", sh["by_cid"].get("1") == {"individual_net": 60.0, "team_net": 40.0}
      and sh["by_cid"].get("2") == {"skins": 22.5}, sh["by_cid"])
check("an unresolved row is not credited to anybody", all(c in ("1", "2", "4") for c in sh["by_cid"]))
check("team purse = sum of its slots ($80)", sh["teams"] and sh["teams"][0]["purse"] == 80.0, sh["teams"])
check("each slot carries its share", sh["teams"][0]["slots"] == {"-1": 40.0, "-4": 40.0}, sh["teams"])
check("the board's own teams are not mutated", "purse" not in lb["teams"][0])

print("projected_money calls the SAME assembly, projected, with the board")
_real_asm = db.assemble_event_game_payouts
CALL = {}


def _fake_asm(name, db_path=None, projected=False, lb=None):
    CALL.update(name=name, projected=projected, lb=lb)
    return {"rows": [{"golferName": "Adam Baker", "customer_id": 1, "category": "individual_net",
                      "amount": 60.0, "description": "Ind Net F1 1st"}], "notes": []}


db.assemble_event_game_payouts = _fake_asm
bs._PROJ_CACHE.clear()
lbx = {"event": {"id": 77, "name": "s10.20 Proj"}, "teams": []}
pm = bs.projected_money(lbx, db_path=DB)
check("assembly ran projected=True with the board", CALL.get("projected") is True and CALL.get("lb") is lbx, CALL)
check("money keyed by customer", pm and pm["by_cid"].get("1") == {"individual_net": 60.0}, pm)
CALL.clear()
bs.projected_money(lbx, db_path=DB)
check("unchanged scores: served from cache (no second engine run)", not CALL, CALL)
db.assemble_event_game_payouts = _real_asm

print("a real entry-mode event mid-round: attach() reads, writes nothing")
from email_parser.timezone_utils import today_central_str  # noqa: E402
TODAY = today_central_str()
EV, NAME = 940, "s10.20 Summary Links"
conn = sqlite3.connect(DB)
for cid, fn, ln in [(301, "Kerry", "Niester"), (302, "Adam", "Baker")]:
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
course_id = conn.execute("INSERT INTO courses (name, status) VALUES ('Summary Links', 'active') "
                         "RETURNING course_id").fetchone()[0]
tee = conn.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, nine, rating, "
                   "slope, tgf_bands, source) VALUES (?, 'White', 'M', 9, 'front', 34.0, 120, "
                   "'50-64', 'admin') RETURNING tee_id", (course_id,)).fetchone()[0]
NINE = [(1, 4, 3), (2, 3, 9), (3, 5, 1), (4, 4, 5), (5, 4, 7), (6, 3, 8), (7, 4, 2), (8, 4, 6), (9, 5, 4)]
for h, par, si in NINE:
    conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, stroke_index) VALUES (?,?,?,?)",
                 (tee, h, par, si))
conn.execute("INSERT INTO events (id, item_name, event_date, course_id, format) VALUES (?,?,?,?,?)",
             (EV, NAME, TODAY, course_id, "9 Holes"))
db._ensure_scoring_tables(conn)
db._ensure_pairing_tables(conn)
db._ensure_gg_game_flights_tables(conn)
db._ensure_gg_game_results_tables(conn)
conn.commit()
conn.close()
COURSE = [{"hole": h, "par": p, "stroke_index": si} for h, p, si in NINE]
rid = se.create_round(EV, 9, round_date=TODAY, label="s10.20", course_holes=COURSE,
                      course_id=course_id, db_path=DB)["round_id"]
gid = se.upsert_group(rid, 1, players=[
    {"customer_id": 301, "display_name": "Kerry N", "tee": "50-64", "playing_handicap": 5},
    {"customer_id": 302, "display_name": "Adam B", "tee": "50-64", "playing_handicap": 3},
], db_path=DB)["group_id"]
se.claim_group(gid, "dev1", 301, db_path=DB)
ops = [{"op_id": f"k{h}", "hole": h, "gross": 5, "customer_id": 301} for h in range(1, 10)]
ops += [{"op_id": f"a{h}", "hole": h, "gross": 4, "customer_id": 302} for h in (1, 2, 3)]
r = se.write_scores(gid, "dev1", 301, ops, db_path=DB)
assert all(x["result"] == "ok" for x in r["results"]), r
db.set_app_setting("score_entry_live", "1", db_path=DB)
db.set_app_setting("score_entry_events", json.dumps([EV]), db_path=DB)


def counts():
    c = sqlite3.connect(DB)
    try:
        return tuple(c.execute(q).fetchone()[0] for q in (
            "SELECT COUNT(*) FROM scoring_rounds", "SELECT COUNT(*) FROM scoring_holes",
            "SELECT COUNT(*) FROM tgf_payouts",
            "SELECT COUNT(*) FROM app_settings WHERE key = 'auto_payouts_preview'"))
    finally:
        c.close()


st_rec = db.event_engine_state(NAME, db_path=DB)
st_live = db.event_engine_state(NAME, db_path=DB, live=True)
check("the record has no cards yet (nothing published)", bool(st_rec.get("error")), st_rec.get("error"))
check("live=True reads the entered cards", not st_live.get("error")
      and {p["customer_id"] for p in st_live.get("players") or []} == {301, 302},
      st_live.get("error"))
before = counts()
lbd = db.get_event_leaderboard(NAME, db_path=DB)
bs._PROJ_CACHE.clear()
bs.attach(lbd, db_path=DB)
check("mid-round board is LIVE", lbd.get("board_state") == "live", lbd.get("board_state"))
check("a projection was attempted (dict, not None)", isinstance(lbd.get("projected"), dict), lbd.get("projected"))
check("pots present as a dict", isinstance(lbd.get("pots"), dict))
check("no matches -> empty match_play", lbd.get("match_play") == [])
check("attach wrote nothing (cards, payouts, preview)", counts() == before, f"{before} -> {counts()}")
# the board itself still blanks its own money mid-round
check("money still held on the board mid-round", lbd.get("money_visible") is False)

print("City Match Play tied to the event")
conn = sqlite3.connect(DB)
pool = conn.execute("INSERT INTO cmp_pools (season, chapter, pool_name) VALUES ('2026', 'San Antonio', 'Pool A') "
                    "RETURNING id").fetchone()[0]
conn.execute("INSERT INTO cmp_matches (pool_id, player1_name, player2_name, winner_name, margin, played_at, event_id) "
             "VALUES (?, 'Kerry Niester', 'Adam Baker', 'Kerry Niester', '2&1', '2026-10-20', ?)", (pool, EV))
conn.execute("INSERT INTO cmp_matches (pool_id, player1_name, player2_name, played_at) "
             "VALUES (?, 'Other One', 'Other Two', '2026-10-01')", (pool,))
conn.execute("INSERT INTO cmp_bracket (season, chapter, round, slot, player_name, winner_name, margin, event_id) "
             "VALUES ('2026', 'San Antonio', 'Semifinal', 1, 'Kerry Niester', 'Kerry Niester', '3&2', ?)", (EV,))
conn.execute("INSERT INTO cmp_bracket (season, chapter, round, slot, player_name, event_id) "
             "VALUES ('2026', 'San Antonio', 'Semifinal', 2, 'Pat Youngs', ?)", (EV,))
conn.commit()
conn.close()
ms = bs.event_matches(EV, db_path=DB)
pool_ms = [m for m in ms if m["kind"] == "pool"]
ko = [m for m in ms if m["kind"] == "knockout"]
check("the event's pool match only (the private one is left out)",
      len(pool_ms) == 1 and pool_ms[0]["player2_name"] == "Adam Baker", pool_ms)
check("pool match carries the card's fields", pool_ms and pool_ms[0]["event_name"] == NAME
      and pool_ms[0]["pool_name"] == "Pool A" and "hole_pars" in pool_ms[0], pool_ms)
check("the knockout pair folds into one match", len(ko) == 1 and ko[0]["player1_name"] == "Kerry Niester"
      and ko[0]["player2_name"] == "Pat Youngs" and ko[0]["winner_name"] == "Kerry Niester", ko)
lbd2 = db.get_event_leaderboard(NAME, db_path=DB)
bs.attach(lbd2, db_path=DB)
check("attach carries the matches", len(lbd2.get("match_play") or []) == 2)

print("the API decorates the event payload")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")).read()
i = src.find("def api_events_leaderboard_event")
check("api_events_leaderboard_event calls board_summary.attach",
      i > 0 and "board_summary import attach" in src[i:i + 1500])

print("\nALL PASS" if not FAILURES else f"\n{len(FAILURES)} FAILURE(S): {FAILURES}")
sys.exit(1 if FAILURES else 0)
