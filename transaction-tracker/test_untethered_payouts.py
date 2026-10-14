"""PAYOUTS WITHOUT GOLF GENIUS (Kerry 2026-10-13: "we're not running Golf
Genius at all tonight, so I'm relying on you and what we've built to make it
all happen now").

An event on/after gg_untether_from has no GG board, so Record Payouts takes:
  * Team / CART Net from the Tracker's own EVENTS leaderboard (its teams,
    blinds included), through the same split / tie / blind rules;
  * CTP / Longest Putt from the holders claimed on the phones;
  * Individual Net, Skins, Individual Gross from the engine on the flight
    board (engine_game_payouts) — never the GG-label path.
Money waits for a complete field. Rows carry customer_id, and the writer
records to it. A GG-era event is untouched.
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.WARNING)
import app as _appmod                                   # noqa: E402,F401
from email_parser import database as db                 # noqa: E402
from email_parser import score_entry as se              # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

with db._connect(DB) as c:
    c.execute("INSERT INTO events (item_name, event_date, course, chapter) VALUES "
              "('s9.27 The Quarry', '2026-10-13', 'The Quarry', 'San Antonio')")
    c.execute("INSERT INTO events (item_name, event_date, course, chapter) VALUES "
              "('s9.20 Old', '2026-08-25', 'X', 'San Antonio')")
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (501, 'Jesse', 'Saldana')")
    c.commit()
    ev_id = c.execute("SELECT id FROM events WHERE item_name = 's9.27 The Quarry'").fetchone()[0]

ROW = {"teamTotal": 92, "team1st": 92, "team2nd": "NO_EVENT", "teamType": "Team Net",
       "ctp1": 23, "ctp2": 23, "individualNet": 126, "netFlights": 2,
       "skinsTotal": 130, "skinsFlights": 2, "individualGross": "NO_EVENT"}
db._load_games_matrix = lambda db_path=None: ({"23": ROW, "14": ROW, "10": ROW}, {})
db._event_player_counts = lambda conn, name: {"players": 23, "net": 14, "gross": 10}
db._event_looks_rained_out = lambda conn, name: None
db.determine_tgf_mvp = lambda name, db_path=None: {"error": "stub"}
db.get_gg_game_results = lambda name, db_path=None: {"results": []}
calls = {"determine": 0}
_orig_det = db.determine_event_game_results
def _no_gg_path(*a, **k):
    calls["determine"] += 1
    return {"status": "flights_unknown"}
db.determine_event_game_results = _no_gg_path

LB = {"field_complete": False, "holes_posted": 100, "holes_needed": 207, "teams": []}
db.get_event_leaderboard = lambda name, db_path=None: LB
se.event_ctp_holders = lambda event_id, db_path=None: [
    {"round_id": 1, "hole": 12, "kind": "ctp", "customer_id": 501, "name": "Jesse Saldana"},
    {"round_id": 1, "hole": 16, "kind": "ctp", "customer_id": None, "name": None}]
ENG = {"error": "no scorecards for this event yet"}
db.engine_game_payouts = lambda name, db_path=None: ENG

print("== before the field is complete ==")
a = db.assemble_event_game_payouts("s9.27 The Quarry", db_path=DB)
check("no money while the field is incomplete", a["rows"] == [], a["rows"])
check("...and it says why", any("not complete yet" in n for n in a["notes"]), a["notes"])
check("engine says publish first", any("publish the entered cards" in n for n in a["notes"]), a["notes"])
check("the GG-label path is never asked for an untethered event", calls["determine"] == 0)
check("no 'GG-recorded' notes on a night without GG",
      not any("GG-recorded" in n for n in a["notes"]), a["notes"])

print("== the field is in, cards published ==")
LB.update(field_complete=True, teams=[
    {"team_num": 3, "total_net": -6, "position": "1",
     "players": [{"player_name": "RIDEOUT, Jeff"}, {"player_name": "HUNT, Bob"},
                 {"player_name": "MAZANEC, Luke"}, {"player_name": "Bl[McCORMICK, Michele]"}]},
    {"team_num": 1, "total_net": -3, "position": "2",
     "players": [{"player_name": "A"}, {"player_name": "B"}]}])
ENG.clear()
ENG.update({"games": {
    "individual_net": {"status": "paid", "sum_check": True, "unallocated": [], "rows": [
        {"customer_id": 501, "name": "SALDANA, Jesse", "amount": 63.0, "detail": "F1 place 1"},
        {"customer_id": 6, "name": "RIDEOUT, Jeff", "amount": 63.0, "detail": "F2 place 1"}]},
    "skins": {"status": "paid", "sum_check": True, "rows": [
        {"customer_id": 82, "name": "MAZANEC, Luke", "amount": 65.0, "detail": "Skins F1 ×1 holes 12"}],
        "unallocated": [{"flight_no": 2, "amount": 65.0, "why": "no skin won in this flight"}]},
    "individual_gross": {"status": "not_running", "rows": []}}, "warnings": []})
a = db.assemble_event_game_payouts("s9.27 The Quarry", db_path=DB)
by = {}
for r in a["rows"]:
    by.setdefault(r["category"], []).append(r)
team = by.get("team_net") or []
check("Team Net 1st pays the leaderboard's winning team, blind included ($23 x 4)",
      sorted(r["golferName"] for r in team) == ["HUNT, Bob", "MAZANEC, Luke", "McCORMICK, Michele", "RIDEOUT, Jeff"]
      and all(abs(r["amount"] - 23.0) < 0.001 for r in team), team)
ctp = by.get("ctp") or []
check("CTP pays the phone-claimed holder by customer_id", len(ctp) == 1 and ctp[0]["customer_id"] == 501
      and ctp[0]["amount"] == 23 and "hole 12" in ctp[0]["description"], ctp)

# CTP VERIFICATION (Kerry 10/13): a takeover the manager has not confirmed is not paid
se.event_ctp_holders = lambda event_id, db_path=None: [
    {"round_id": 1, "hole": 12, "kind": "ctp", "customer_id": 501, "name": "Jesse Saldana"},
    {"round_id": 1, "hole": 16, "kind": "ctp", "customer_id": 298, "name": "Dan Stich",
     "needs_confirm": {"from": {"customer_id": 136, "name": "Pat Youngs", "group_num": 6},
                       "to": {"customer_id": 298, "name": "Dan Stich", "group_num": 3}}}]
a2 = db.assemble_event_game_payouts("s9.27 The Quarry", db_path=DB)
ctp2 = [r for r in a2["rows"] if r.get("category") == "ctp"]
check("an unconfirmed takeover is not paid; the confirmed hole still is",
      [r["customer_id"] for r in ctp2] == [501], ctp2)
check("...and the note says confirm it on the Live Scoring page",
      any("hole 16" in n and "confirm it on the Live Scoring page" in n for n in a2["notes"]), a2["notes"])
se.event_ctp_holders = lambda event_id, db_path=None: [
    {"round_id": 1, "hole": 12, "kind": "ctp", "customer_id": 501, "name": "Jesse Saldana"},
    {"round_id": 1, "hole": 16, "kind": "ctp", "customer_id": None, "name": None}]
check("an unclaimed CTP hole is named, not paid", any("hole 16: nobody holds it" in n for n in a["notes"]), a["notes"])
net = by.get("individual_net") or []
check("Ind Net comes from the engine on the flight board, per flight",
      sorted((r["golferName"], r["amount"], r["customer_id"]) for r in net)
      == [("RIDEOUT, Jeff", 63.0, 6), ("SALDANA, Jesse", 63.0, 501)], net)
check("...with readable descriptions", net and net[0]["description"].startswith("Ind Net F"), net)
sk = by.get("skins") or []
check("Skins from the engine; the skinless flight is reported, not guessed",
      len(sk) == 1 and sk[0]["amount"] == 65.0
      and any("$65.00 not paid" in n for n in a["notes"]), (sk, a["notes"]))
check("still no GG-label determination", calls["determine"] == 0)

print("== the writer records to the row's customer_id ==")
db.add_tgf_event({"name": "s9.27 The Quarry", "code": "s9.27 The Quarry",
                  "event_date": "2026-10-13"}, db_path=DB)
with db._connect(DB) as c:
    te = c.execute("SELECT id FROM tgf_events").fetchone()[0]
res = db.import_tgf_payouts(te, [{"golferName": "Somebody Else Entirely", "customer_id": 501,
                                  "category": "ctp", "amount": 23, "description": "x"}], db_path=DB)
with db._connect(DB) as c:
    got = c.execute("SELECT customer_id FROM tgf_payouts WHERE event_id = ?",
                    (res["event_id"],)).fetchall()
check("customer_id wins over the name", [r[0] for r in got] == [501], (res, [tuple(r) for r in got]))

print("== a GG-era event keeps the GG path ==")
calls["determine"] = 0
db.assemble_event_game_payouts("s9.20 Old", db_path=DB)
check("pre-untether events still ask the GG-label path", calls["determine"] > 0)

print("\nALL PASS" if not F else f"\n{len(F)} FAILED: " + "; ".join(F))
sys.exit(1 if F else 0)
