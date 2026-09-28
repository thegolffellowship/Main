"""ENGINE PAYOUTS FROM THE FROZEN SELECTION (CA #829 GO) — pure checks.

  * the engine takes each game's flights from the flight board when every
    card is pinned, and falls back (saying so) when any card is not;
  * `flighting.payouts_from_results` pays places down the engine's ranking,
    pools ties (the ratified rule), pays skins per skin per flight, and
    reports a flight with no skin as UNALLOCATED rather than guessing;
  * s9.24 Brackenridge (event 3309), the #815 failure, reproduced: with the
    frozen skins flights (cut at index 12.0) GG's purses come out to the cent.
"""
import sys

from email_parser import flighting as fl
from email_parser import live_scoring as ls

FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label
          + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


print("\n== pinned flights win over the engine's own bands ==")
cards = [{"key": k, "name": k, "playing_handicap": ph, "flight": None}
         for k, ph in (("a", 1), ("b", 3), ("c", 5), ("d", 7))]
pins = {"a": "1", "b": "2", "c": "2", "d": "2"}
got = ls.assign_flights(cards, {"flight_bands": {"9": [[0, None, 2]]}}, "9", pins)
check("every card pinned -> the pins decide",
      {k: [c["key"] for c in v] for k, v in got.items()}
      == {"1": ["a"], "2": ["b", "c", "d"]}, got)
half = ls.assign_flights(cards, {}, "9", {"a": "1"})
check("a partial pin set is NOT used (never a half-pinned field)",
      list(half) == ["1"] and len(half["1"]) == 4, half)
src = ls._flight_source(cards, {"a": "1"})
check("...and the unpinned players are named",
      src["unpinned"] == ["b", "c", "d"], src)

print("\n== places, ties and the gross bonus ==")
entry = {"game": "individual_net", "active": True, "amounts": {"flights": [
    {"flight_no": 1, "pot": 58.5, "places": [{"place": 1, "amount": 58.5}]},
    {"flight_no": 2, "pot": 58.5, "places": [{"place": 1, "amount": 58.5}]}]}}
res = {"active": True, "flights": [
    {"flight": "1", "provisional": False, "rows": [
        {"key": "f", "customer_id": 130, "name": "FEHLIS, Chuck", "place": 1},
        {"key": "m", "customer_id": 142, "name": "MARROQUIN, Scott", "place": 1},
        {"key": "x", "customer_id": 1, "name": "X", "place": 3}]},
    {"flight": "2", "provisional": False, "rows": [
        {"key": "mm", "customer_id": 131, "name": "MURPHY, Mike", "place": 1}]}]}
p = fl.payouts_from_results(entry, res)
amt = {r["name"]: r["amount"] for r in p["rows"]}
check("a tie on 1st pools and splits the place money ($29.25 each, as GG)",
      amt == {"FEHLIS, Chuck": 29.25, "MARROQUIN, Scott": 29.25,
              "MURPHY, Mike": 58.5}, amt)
check("paid + unallocated sums to the pot", p["sum_check"] and p["total"] == 117.0)
res["flights"][0]["provisional"] = True
check("an incomplete card makes the game provisional, not payable",
      fl.payouts_from_results(entry, res)["status"] == "provisional")

g_entry = {"game": "individual_gross", "active": True, "amounts": {
    "bonus": 3.6, "bonus_label": "Overall Low Gross", "flights": [
        {"flight_no": 1, "pot": 10.0, "places": [{"place": 1, "amount": 10.0}]}]}}
g_res = {"active": True, "flights": [{"flight": "1", "rows": [
    {"key": "a", "customer_id": 1, "name": "A", "place": 1, "gross": 40, "thru": 9},
    {"key": "b", "customer_id": 2, "name": "B", "place": 2, "gross": 38, "thru": 9}]}]}
gp = fl.payouts_from_results(g_entry, g_res)
check("Overall Low Gross goes to the lowest GROSS score, not the top place",
      any(r["name"] == "B" and r["amount"] == 3.6 for r in gp["rows"]), gp["rows"])

print("\n== skins: per skin per flight; an empty flight is unallocated ==")
s_entry = {"game": "skins", "active": True, "amounts": {"flights": [
    {"flight_no": 1, "pot": 65.0, "places": []},
    {"flight_no": 2, "pot": 65.0, "places": []}]}}
# s9.24 Brackenridge, GG's own skins, with the frozen flights (12.0 cut):
f1 = [("skinner", 93, "SKINNER, Nic", 1), ("niester", 18, "NIESTER, Kerry", 4),
      ("niester", 18, "NIESTER, Kerry", 6), ("skinner", 93, "SKINNER, Nic", 8),
      ("young", 88, "YOUNG, Jeff", 9)]
f2 = [("marroquin", 142, "MARROQUIN, Scott", 6),
      ("marroquin", 142, "MARROQUIN, Scott", 9)]
s_res = {"active": True, "flights": [
    {"flight": "1", "skins": [{"key": k, "customer_id": c, "winner": n, "hole": h}
                              for k, c, n, h in f1]},
    {"flight": "2", "skins": [{"key": k, "customer_id": c, "winner": n, "hole": h}
                              for k, c, n, h in f2]}]}
sp = fl.payouts_from_results(s_entry, s_res)
samt = {r["name"]: r["amount"] for r in sp["rows"]}
check("3309 skins reproduce GG's purses to the cent",
      samt == {"MARROQUIN, Scott": 65.0, "NIESTER, Kerry": 26.0,
               "SKINNER, Nic": 26.0, "YOUNG, Jeff": 13.0}, samt)
s_res["flights"][1]["skins"] = []
ep = fl.payouts_from_results(s_entry, s_res)
check("a flight with no skin reports its pot UNALLOCATED, never guessed",
      ep["unallocated"] and ep["unallocated"][0]["amount"] == 65.0
      and ep["sum_check"], ep["unallocated"])
check("a game not running pays nothing and says why",
      fl.payouts_from_results({"game": "skins", "active": False,
                               "inactive_reason": "nobody bought"}, None)
      ["status"] == "not_running")

print("\n== Individual Net is STROKE play; equal net scores TIE (CA #832) ==")
def _card(key, pts, net):
    return {"key": key, "customer_id": None, "name": key, "playing_handicap": 5,
            "stableford_net": pts, "stableford_gross": 0, "net": net,
            "gross": net + 5, "thru": 9, "complete": True, "flight": None,
            "team": None, "buys_net": True, "buys_gross": False,
            "is_member": True}
cfg = ls.SEED_LIVE_SCORING_CONFIG
# 3309: Fehlis and Marroquin both net 34 — Marroquin had MORE Stableford
# points (a capped blow-up hole), which is how the engine used to split them.
tie = ls.game_individual([_card("Fehlis", 10, 34), _card("Marroquin", 12, 34),
                          _card("Other", 14, 35)], cfg, "9", "net")
places = {r["name"]: r["place"] for f in tie["flights"] for r in f["rows"]}
check("lowest NET score wins, not most Stableford points",
      places["Other"] == 3, places)
check("equal net scores share 1st — no tiebreak",
      places["Fehlis"] == 1 and places["Marroquin"] == 1, places)
check("the dial says so, for both Individual games",
      cfg["games"]["individual_net"]["tiebreak"] == "none"
      and cfg["games"]["individual_gross"]["tiebreak"] == "none")

print("\n== a frozen skins VARIANT holds when the buyer count crosses 8 (B5) ==")
def _sk(key, gross_by_hole, ph=10):
    holes = [{"hole": h, "par": 4, "stroke_index": h, "strokes": g,
              "strokes_received": 0} for h, g in gross_by_hole.items()]
    return {"key": key, "customer_id": None, "name": key, "playing_handicap": ph,
            "course_handicap_unrounded": None, "holes": holes, "thru": 9,
            "complete": True, "buys_net": True, "buys_gross": True,
            "is_member": True, "flight": None, "team": None,
            "stableford_net": 0, "stableford_gross": 0, "net": 0, "gross": 0}
field7 = [_sk(f"p{i}", {h: 4 for h in range(1, 10)}) for i in range(7)]
live = ls.game_skins(field7, cfg, "9")
froze = ls.game_skins(field7, cfg, "9", variant_name="gross")
check("7 buyers on a nine select ½ Net when nothing froze",
      live["variant"] != "gross", live["variant"])
check("a frozen gross Skins stays gross at 7 buyers",
      froze["variant"] == "gross" and froze["selection"].get("frozen"),
      froze.get("selection"))

print("\n== a card with no tee is refused, never scored as empty holes ==")
import os, tempfile
from email_parser import database as db
_tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-engpay-"), "t.db")
db.init_db(_tmp)
with db._connect(_tmp) as _c:
    db._ensure_scoring_tables(_c)
    _eid = _c.execute("INSERT INTO events (item_name, event_date) VALUES "
                      "('s9.99 Nowhere', '2026-10-13')").lastrowid
    _c.execute("INSERT INTO scoring_rounds (player_name, event_id, holes_played, "
               "playing_handicap, source) VALUES ('A B', ?, 9, 5, 'entry')", (_eid,))
    _c.commit()
_st = db.event_engine_state("s9.99 Nowhere", db_path=_tmp)
check("event_engine_state refuses and names the missing tee",
      "no tee" in (_st.get("error") or ""), _st.get("error"))
check("...and engine payouts pass the refusal through",
      "no tee" in (db.engine_game_payouts("s9.99 Nowhere", db_path=_tmp)
                   .get("error") or ""))

print("\n== one tee-less card among tee'd ones is NAMED and holds the money ==")
from unittest import mock
_fake_state = {"holes": [{"hole": h, "par": 4, "yardage": 350, "stroke_index": h}
                         for h in range(1, 10)],
               "players": [], "contests": [],
               "meta": {"event_id": 1, "event_name": "x", "holes": 9,
                        "championship": False},
               "warnings": ["1 card(s) carry no tee ..."], "tee_less": ["WADE, Mary"]}
_board = {"state": "settled", "games": [{
    "game": "individual_net", "active": True,
    "selection": {"flights": [], "variant": {"name": "default"}},
    "amounts": {"flights": []}}]}
with mock.patch.object(db, "get_scoring_formulas", return_value={}):
    _ep = db.engine_game_payouts("x", db_path=_tmp, state=_fake_state, board=_board)
_g = _ep["games"]["individual_net"]
check("a game with a tee-less card is provisional, and names her",
      _g["status"] in ("provisional", "no_result") and _ep["tee_less"] == ["WADE, Mary"],
      (_g["status"], _ep.get("tee_less")))

print("\n== an ENTERED card's placeholder zero dots are derived, never read ==")
with db._connect(_tmp) as _c:
    _cols = {r[1] for r in _c.execute("PRAGMA table_info(course_tees)")}
    _cid = 900001
    _c.execute("INSERT INTO course_tees (course_id, tee_name) VALUES (?, 'White')", (_cid,))
    _tee = _c.execute("SELECT max(tee_id) FROM course_tees").fetchone()[0]
    for _h in range(1, 10):
        _c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, stroke_index) "
                   "VALUES (?, ?, 4, ?)", (_tee, _h, _h))
    _eid2 = _c.execute("INSERT INTO events (item_name, event_date) VALUES "
                       "('s9.98 Entered', '2026-10-13')").lastrowid
    _r = _c.execute("INSERT INTO scoring_rounds (player_name, event_id, holes_played, "
                    "playing_handicap, tee_id, source) VALUES ('C D', ?, 9, 5, ?, 'entry')",
                    (_eid2, _tee)).lastrowid
    for _h in range(1, 10):
        _c.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes, "
                   "strokes_received) VALUES (?, ?, 5, 0)", (_r, _h))
    _c.commit()
_st2 = db.event_engine_state("s9.98 Entered", db_path=_tmp)
check("entered card: the stored zeros are NOT taken as given dots",
      _st2.get("players") and _st2["players"][0]["strokes_received"] == {},
      _st2.get("error") or _st2["players"][0]["strokes_received"])
_cards = ls.build_cards(_st2, db.get_scoring_formulas(_tmp))
check("...so the engine derives PH 5 over the nine (net = gross - 5)",
      _cards[0]["allocation_source"] == "derived" and _cards[0]["net"] == 40,
      (_cards[0]["allocation_source"], _cards[0]["net"]))

print("\n== a COMP plays but does not fund the games (CA #882-4) ==")
with db._connect(_tmp) as _c:
    for _uid, _cust, _price, _sg in (("e1", "Paid One", "$55.00", "NET"),
                                     ("e2", "Paid Two", "$86.00", "Both"),
                                     ("manual-comp-1", "Comp Kerry", "$0.00 (comp)", "Both"),
                                     ("legacy-0", "Zero Legacy", "$0.00", "NET")):
        _c.execute("INSERT INTO items (email_uid, item_index, merchant, customer, "
                   "item_name, item_price, side_games, transaction_status, order_date) "
                   "VALUES (?, 0, 'x', ?, 's9.97 Comp', ?, ?, 'active', '2026-10-13')",
                   (_uid, _cust, _price, _sg))
    _c.commit()
    _cnt = db._event_player_counts(_c, "s9.97 Comp")
check("the explicit comp is out of players / net / gross",
      (_cnt["players"], _cnt["net"], _cnt["gross"]) == (3, 3, 1), _cnt)
check("...and is NAMED as a comp", [c["name"] for c in _cnt["comps"]] == ["Comp Kerry"],
      _cnt["comps"])
check("a bare $0.00 with no comp marker is NOT treated as a comp (transfer / legacy)",
      _cnt["players"] == 3)

print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL ENGINE-PAYOUT TESTS PASSED")
