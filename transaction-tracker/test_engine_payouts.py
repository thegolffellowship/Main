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

print("\n== Individual Net: equal points are a TIE (CA #832) ==")
def _card(key, pts, net):
    return {"key": key, "customer_id": None, "name": key, "playing_handicap": 5,
            "stableford_net": pts, "stableford_gross": 0, "net": net,
            "gross": net + 5, "thru": 9, "complete": True, "flight": None,
            "team": None, "buys_net": True, "buys_gross": False,
            "is_member": True}
cfg = ls.SEED_LIVE_SCORING_CONFIG
tie = ls.game_individual([_card("Fehlis", 12, 30), _card("Marroquin", 12, 29),
                          _card("Other", 10, 33)], cfg, "9", "net")
places = {r["name"]: r["place"] for f in tie["flights"] for r in f["rows"]}
check("equal points share 1st — no stroke-score tiebreak",
      places["Fehlis"] == 1 and places["Marroquin"] == 1 and places["Other"] == 3,
      places)
check("the dial says so, for both Individual games",
      cfg["games"]["individual_net"]["tiebreak"] == "none"
      and cfg["games"]["individual_gross"]["tiebreak"] == "none")

print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL ENGINE-PAYOUT TESTS PASSED")
