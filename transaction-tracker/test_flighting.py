"""The RATIFIED flighting & payout rule set (mailbox #571–#575 as revised by
#581/#582), pinned number by number against Kerry's own worked examples.

Every check below cites the post it comes from. If one of these fails, the
rule moved — not the code.

Run: python3 test_flighting.py
"""
import random
import sys

from email_parser import flighting as fl

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


def P(cid, name, idx, ph=None):
    return {"customer_id": cid, "name": name, "index": idx, "ph": ph}


# A slice of the LIVE matrix as read on 2026-09-21 (get_side_games_matrix),
# enough for the games these tests exercise. Values are the app_settings
# copy, not the repo seed.
M18 = {
    8:  {"individualNet": 144.0, "netFlights": 1, "netLow1st": 96.0, "netLow2nd": 48.0,
         "skinsTotal": 208.0, "skinsFlights": 2, "individualGross": "NO_GAME", "grossFlights": None},
    9:  {"individualNet": 162.0, "netFlights": 1, "netLow1st": 108.0, "netLow2nd": 54.0,
         "skinsTotal": 234.0, "skinsFlights": 2, "individualGross": "NO_GAME", "grossFlights": None},
    12: {"individualNet": 216.0, "netFlights": 1, "netLow1st": 108.0, "netLow2nd": 64.8, "netLow3rd": 43.2,
         "skinsTotal": 216, "skinsFlights": 2, "individualGross": 96, "grossFlights": 3},
    13: {"individualNet": 238.0, "netFlights": 1, "netLow1st": 119.0, "netLow2nd": 71.4, "netLow3rd": 47.6,
         "skinsTotal": 234, "skinsFlights": 2, "individualGross": 104, "grossFlights": 3},
    14: {"individualNet": 264.0, "netFlights": 2, "netLow1st": 88.0, "netLow2nd": 44.0,
         "netHigh1st": 88.0, "netHigh2nd": 44.0,
         "skinsTotal": 252, "skinsFlights": 2, "individualGross": 112, "grossFlights": 3},
    15: {"individualNet": 290.0, "netFlights": 2, "netLow1st": 96.67, "netLow2nd": 48.33,
         "netHigh1st": 96.67, "netHigh2nd": 48.33,
         "skinsTotal": 270, "skinsFlights": 2, "individualGross": 120, "grossFlights": 3},
    16: {"individualNet": 316.0, "netFlights": 2, "netLow1st": 105.33, "netLow2nd": 52.67,
         "netHigh1st": 105.33, "netHigh2nd": 52.67,
         "skinsTotal": 288.0, "skinsFlights": 2, "individualGross": 128.0, "grossFlights": 4},
    19: {"individualNet": 394.0, "netFlights": 2, "netLow1st": 98.5, "netLow2nd": 59.1, "netLow3rd": 39.4,
         "netHigh1st": 98.5, "netHigh2nd": 59.1, "netHigh3rd": 39.4,
         "skinsTotal": 342.0, "skinsFlights": 2, "individualGross": 152.0, "grossFlights": 4},
}
M9 = {
    5:  {"individualNet": 45.0, "netFlights": 1, "netLow1st": 45.0,
         "skinsTotal": 65.0, "skinsFlights": 1, "individualGross": "NO_GAME"},
    7:  {"individualNet": 63.0, "netFlights": 1, "netLow1st": 63.0,
         "skinsTotal": 91.0, "skinsFlights": 1, "individualGross": "NO_GAME"},
    8:  {"individualNet": 72.0, "netFlights": 1, "netLow1st": 48.0, "netLow2nd": 24.0,
         "skinsTotal": 104.0, "skinsFlights": 2, "individualGross": "NO_GAME"},
    10: {"individualNet": 90.0, "netFlights": 1, "netLow1st": 60.0, "netLow2nd": 30.0,
         "skinsTotal": 130.0, "skinsFlights": 2, "individualGross": "NO_GAME"},
    14: {"individualNet": 126.0, "netFlights": 2, "netLow1st": 63.0, "netHigh1st": 63.0,
         "skinsTotal": 182.0, "skinsFlights": 2, "individualGross": "NO_GAME"},
    16: {"individualNet": 144.0, "netFlights": 2, "netLow1st": 48.0, "netLow2nd": 24.0,
         "netHigh1st": 48.0, "skinsTotal": 144, "skinsFlights": 2, "individualGross": 64, "grossFlights": 3},
    20: {"individualNet": 180.0, "netFlights": 2, "netLow1st": 60.0, "netLow2nd": 30.0,
         "netHigh1st": 60.0, "skinsTotal": 180.0, "skinsFlights": 2, "individualGross": 80.0, "grossFlights": 4},
}


def row18(n):
    return M18.get(n)


def row9(n):
    return M9.get(n)


print("\n== the ladders (#571 B3, #582: cut lines never move) ==")
check("3-flight ladder is <6.0 / 6.0-11.9 / 12.0+", fl.ladder_for(3) == [6.0, 12.0], str(fl.ladder_for(3)))
check("4-flight ladder adds 18.0 and keeps 6.0 and 12.0", fl.ladder_for(4) == [6.0, 12.0, 18.0])
check("2-flight (Skins) ladder cuts at 12.0", fl.ladder_for(2) == [12.0])
check("one flight has no edges", fl.ladder_for(1) == [])
bands = fl.cut_by_edges([P(1, "A", 5.9), P(2, "B", 6.0), P(3, "C", 11.9), P(4, "D", 12.0)], [6.0, 12.0])
check("6.0 goes UP, 5.9 stays", [m["name"] for m in bands[0]] == ["A"] and bands[1][0]["name"] == "B")
check("12.0 goes UP, 11.9 stays", [m["name"] for m in bands[1]] == ["B", "C"] and [m["name"] for m in bands[2]] == ["D"])
check("band text states the rule: <6.0 / 6.0–11.9 / 12.0+",
      [fl.band_text(i, [6.0, 12.0]) for i in range(3)] == ["<6.0", "6.0–11.9", "12.0+"],
      str([fl.band_text(i, [6.0, 12.0]) for i in range(3)]))

print("\n== no minimum, no merging (#572 B2 superseded) ==")
check("the seed rules carry min_flight_size 0 and merge False",
      fl.FLIGHT_RULES["min_flight_size"] == 0 and fl.FLIGHT_RULES["merge"] is False)
solo = fl.cut_by_edges([P(1, "A", 0.7), P(2, "B", 7.7), P(3, "C", 8.0), P(4, "D", 9.0), P(5, "E", 11.2)], [6.0, 12.0])
check("a flight of ONE simply is that size — nothing merges", len(solo) == 3 and len(solo[0]) == 1 and len(solo[2]) == 0)
check("an EMPTY band is still a numbered flight on the board", solo[2] == [])

print("\n== labels derived from membership (P2-6, #575) ==")
check("label is the actual range, never a typed band",
      fl.derived_label([P(1, "A", 8.1), P(2, "B", 10.0), P(3, "C", 14.3)]) == "8.1–14.3")
check("a solo flight prints its one index", fl.derived_label([P(1, "A", 5.2)]) == "5.2")
check("an empty band prints a dash", fl.derived_label([]) == "—")
check("a plus handicap prints golf's way", fl.derived_label([P(1, "A", -1.0), P(2, "B", 3.0)]) == "+1.0–3.0")

print("\n== places by FLIGHT size (#573) ==")
check("1–9 → one place", fl.places_for(1) == [1.0] and fl.places_for(9) == [1.0])
check("10–19 → two places 2/3, 1/3", fl.places_for(10) == [2 / 3, 1 / 3] and fl.places_for(19) == [2 / 3, 1 / 3])
check("20+ → three places 50/30/20", fl.places_for(20) == [0.5, 0.3, 0.2] and fl.places_for(40) == [0.5, 0.3, 0.2])
check("an empty flight pays no place", fl.places_for(0) == [])

print("\n== the B4-revised pot with the 10% overall low-gross bonus (#572) ==")
a = fl.gross_amounts("18", [2, 6, 6])
check("field A (14 buyers, $112): bonus $11.20", a["bonus"] == 11.20, str(a["bonus"]))
check("share = 0.9 × $8 = $7.20", a["share"] == 7.20)
check("F1(2) $14.40, F2(6) $43.20, F3(6) $43.20",
      [f["pot"] for f in a["flights"]] == [14.40, 43.20, 43.20], str([f["pot"] for f in a["flights"]]))
check("sums to $100.80 + $11.20 = $112", a["total_pot"] == 112.0 and a["sum_check"])
check("a solo 18-hole flight's player receives his $7.20 share", fl.gross_amounts("18", [1])["flights"][0]["pot"] == 7.20)
check("a solo nine-hole flight's player receives his $3.60 share", fl.gross_amounts("9", [1])["flights"][0]["pot"] == 3.60)
check("the bonus line names Overall Low Gross", a["bonus_label"] == "Overall Low Gross")

print("\n== #573 worked examples, 18-hole $8 gross, share $7.20 ==")
def places(hk, size):
    f = fl.gross_amounts(hk, [size])["flights"][0]
    return f["pot"], [p["amount"] for p in f["places"]]
check("flight of 10: pot $72.00 → $48.00 / $24.00", places("18", 10) == (72.0, [48.0, 24.0]), str(places("18", 10)))
check("flight of 12: pot $86.40 → $57.60 / $28.80", places("18", 12) == (86.4, [57.6, 28.8]), str(places("18", 12)))
check("flight of 20: pot $144.00 → $72.00 / $43.20 / $28.80", places("18", 20) == (144.0, [72.0, 43.2, 28.8]), str(places("18", 20)))
check("flight of 24: pot $172.80 → $86.40 / $51.84 / $34.56", places("18", 24) == (172.8, [86.4, 51.84, 34.56]), str(places("18", 24)))
print("== #573 worked examples, 9-hole $4 gross, share $3.60 ==")
check("flight of 10: pot $36.00 → $24.00 / $12.00", places("9", 10) == (36.0, [24.0, 12.0]), str(places("9", 10)))
check("flight of 12: pot $43.20 → $28.80 / $14.40", places("9", 12) == (43.2, [28.8, 14.4]), str(places("9", 12)))
check("flight of 20: pot $72.00 → $36.00 / $21.60 / $14.40", places("9", 20) == (72.0, [36.0, 21.6, 14.4]), str(places("9", 20)))
check("a flight of 9 pays one place, winner takes the pot", places("18", 9) == (64.8, [64.8]))

print("\n== Landa Park s18.10 (completed): 15 gross buyers, ladder 6/5/4 ==")
lp = fl.gross_amounts("18", [6, 5, 4])
check("total $120: bonus $12, pots $43.20 / $36.00 / $28.80, one place each",
      lp["total_pot"] == 120.0 and lp["bonus"] == 12.0
      and [f["pot"] for f in lp["flights"]] == [43.2, 36.0, 28.8]
      and all(len(f["places"]) == 1 for f in lp["flights"]),
      str(lp))
check("(GG paid 48/36/36 with no bonus — the ratified rule moves $12 to Overall Low Gross)",
      round(sum(f["pot"] for f in lp["flights"]), 2) == 108.0)

print("\n== ties: combine the tied places' money, split evenly, sums to the pot ==")
check("T1 ×3 in a one-place flight pools first only", fl.tie_split([64.8], 1, 3) == [21.6, 21.6, 21.6])
t = fl.tie_split([48.0, 24.0], 1, 2)
check("T1 ×2 in a two-place flight pools 1st+2nd: $36 each", t == [36.0, 36.0], str(t))
t = fl.tie_split([72.0, 43.2, 28.8], 2, 2)
check("T2 ×2 pools 2nd+3rd: $36.00 each", t == [36.0, 36.0], str(t))
t = fl.tie_split([100.0], 1, 3)
check("exact cents: $100 three ways = 33.34 / 33.33 / 33.33, sums to $100",
      sorted(t) == [33.33, 33.33, 33.34] and round(sum(t), 2) == 100.0, str(t))
check("Cedar Creek Ind Net: T1 ×3 on a 108/54 ladder = $54 each (what GG paid)",
      fl.tie_split([108.0, 54.0], 1, 3) == [54.0, 54.0, 54.0])

print("\n== Individual Net and Skins amounts read the LIVE matrix ==")
na = fl.net_amounts(M18[9], [9], True)
check("Cedar Creek Ind Net: 9 buyers, one flight, places 108 / 54 from the matrix",
      na["total_pot"] == 162.0 and [p["amount"] for p in na["flights"][0]["places"]] == [108.0, 54.0], str(na))
na = fl.net_amounts(M18[14], [7, 7], True)
check("14 net buyers on an 18: two flights, Low 88/44 and High 88/44",
      [[p["amount"] for p in f["places"]] for f in na["flights"]] == [[88.0, 44.0], [88.0, 44.0]]
      and na["flights"][1]["matrix_column"] == "netHigh")
sa = fl.skins_amounts(M18[8], [5, 3])
check("Cedar Creek Skins: $208 split equally, $104 per flight, per skin", [f["pot"] for f in sa["flights"]] == [104.0, 104.0])
sa = fl.skins_amounts(M18[15], [11, 4])
check("Landa Park Skins: $270 → $135 / $135 (uneven flights, equal pots)", [f["pot"] for f in sa["flights"]] == [135.0, 135.0])

print("\n== SELECTION: the buyer count selects the game (a9.23), the ladder cuts it ==")
cedar_gross = [P(31, "Robert Straiton", 1.2), P(18, "Kerry Niester", 1.4), P(767, "Bear Clarkson", 6.0),
               P(82, "Luke Mazanec", 7.6), P(85, "Louis Schneider", 9.6), P(21, "Richard Palacios", 15.4),
               P(298, "Dan Stich", 16.0), P(41, "Larry Anthis", 16.0)]
cfg = fl._games_cfg()
s = fl.select_game("skins", "Skins", "GROSS", cedar_gross, "18", M18[8], cfg["skins"])
check("Cedar Creek Skins: 8 buyers → gross skins, 2 flights at 12.0, cut 5/3",
      s["variant"]["name"] == "gross" and s["flight_count"] == 2 and [f["players"] for f in s["flights"]] == [5, 3], str(s))
check("...Schneider (9.6) sits in flight 1 under the ladder (GG had him in flight 2 — P2-6 class)",
      "Louis Schneider" in [m["name"] for m in s["flights"][0]["members"]])
check("...flight labels derive from membership: 1.2–9.6 and 15.4–16.0",
      [f["label"] for f in s["flights"]] == ["1.2–9.6", "15.4–16.0"], str([f["label"] for f in s["flights"]]))
s = fl.select_game("skins", "Skins", "GROSS", cedar_gross[:5], "9", M9[5], cfg["skins"])
check("5 gross buyers on a nine → the matrix runs Skins ½ Net, one flight",
      s["variant"]["name"] == "half_net" and s["flight_count"] == 1 and s["flights"][0]["band"] == "All handicaps", str(s["variant"]))
s = fl.select_game("individual_gross", "Individual Gross", "GROSS", cedar_gross, "18", M18[8], cfg["individual_gross"])
check("Ind Gross does not run at 8 on an 18 (matrix NO_GAME), and says why",
      not s["active"] and "activates at 12" in (s["inactive_reason"] or ""), str(s))
landa_gross = [P(31, "Robert Straiton", 1.4), P(2, "Jeff Young", 1.8), P(18, "Kerry Niester", 2.0),
               P(13, "Luke Youngs", 3.8), P(5, "Scott Hammond", 4.1), P(9, "Hayden Doggett", 5.2),
               P(10, "Bryce Doggett", 7.4), P(11, "Andy Sanford", 9.2), P(4, "John Wade", 9.4),
               P(12, "Gus Vasquez", 11.2), P(37, "Jay Hogue", 11.8), P(14, "Paul Reed", 16.8),
               P(298, "Dan Stich", 17.0), P(15, "Don Sharitz", 17.8), P(113, "Sam McCormick", 19.0)]
s = fl.select_game("individual_gross", "Individual Gross", "GROSS", landa_gross, "18", M18[15], cfg["individual_gross"])
check("Landa Park Ind Gross: 15 buyers → 3 flights on the ladder, 6/5/4",
      s["active"] and s["flight_count"] == 3 and [f["players"] for f in s["flights"]] == [6, 5, 4], str(s["flights"]))
check("...bands read <6.0 / 6.0–11.9 / 12.0+", [f["band"] for f in s["flights"]] == ["<6.0", "6.0–11.9", "12.0+"])
net14 = [P(i, f"N{i}", x) for i, x in enumerate([-1.0, 1.6, 11.0, 11.2, 12.4, 13.8, 14.6, 15.8, 16.4, 16.6, 18.0, 24.0, 27.2, 34.0], start=100)]
s = fl.select_game("individual_net", "Individual Net", "NET", net14, "9", M9[14], cfg["individual_net"])
check("Brackenridge Ind Net: 14 buyers on a nine → 2 flights split DOWN THE MIDDLE by default, 7/7 (Kerry 2026-09-22: 'historically we've always just split the field down the middle… start off with that as a default for Individual Net')",
      s["mode"] == "equal_size" and s["mode_source"] == "default" and [f["players"] for f in s["flights"]] == [7, 7], str(s["flights"]))
check("...no ceiling nudges the cut: the edge is simply the next flight's lowest index (15.8), and the bands read from it",
      s["edges"] == [15.8] and [f["band"] for f in s["flights"]] == ["<15.8", "15.8+"], (s["edges"], [f["band"] for f in s["flights"]]))
s = fl.select_game("individual_net", "Individual Net", "NET", net14, "9", M9[14], cfg["individual_net"], mode="fixed_bands")
check("...the HCP break is one toggle away: fixed_bands cuts on the ladder's 12.0 like Skins (4/10) — the 2026-09-21 reading, now the option",
      s["mode"] == "fixed_bands" and s["mode_source"] == "event toggle" and [f["players"] for f in s["flights"]] == [4, 10]
      and s["edges"] == [12.0] and [f["band"] for f in s["flights"]] == ["<12.0", "12.0+"], str(s["flights"]))
s = fl.select_game("individual_gross", "Individual Gross", "GROSS", landa_gross, "18", M18[15], cfg["individual_gross"])
check("Skins / Gross default to the ratified bands (Landa Park Ind Gross 6/5/4 unchanged)",
      s["mode"] == "fixed_bands" and s["mode_source"] == "default" and [f["players"] for f in s["flights"]] == [6, 5, 4], str(s["flights"]))
s = fl.select_game("individual_gross", "Individual Gross", "GROSS", landa_gross, "18", M18[15], cfg["individual_gross"], mode="equal_size")
check("...and their even-split toggle cuts 15 into 5/5/5",
      s["mode"] == "equal_size" and [f["players"] for f in s["flights"]] == [5, 5, 5], str(s["flights"]))
check("an unknown mode falls back to the game's default", fl.select_game("skins", "Skins", "GROSS", landa_gross, "18", M18[15], cfg["skins"], mode="sideways")["mode"] == "fixed_bands")
bt = fl.build({"NET": net14, "GROSS": landa_gross}, "18", row18, modes={"skins": "equal_size"})
check("build() takes the event's per-game toggles; a game not named keeps its default",
      next(g for g in bt["games"] if g["game"] == "skins")["selection"]["mode"] == "equal_size"
      and next(g for g in bt["games"] if g["game"] == "individual_gross")["selection"]["mode"] == "fixed_bands")
s = fl.select_game("individual_net", "Individual Net", "NET", net14 + [P(200, "X", None)], "9", M9[14], cfg["individual_net"])
check("a player with no index is listed apart, never dropped into a flight",
      [u["name"] for u in s["unflighted"]] == ["X"] and any("no handicap index" in n for n in s["notes"]))

print("\n== build(): a LIVE board, both layers from one field ==")
field = {"NET": net14, "GROSS": landa_gross}
b = fl.build(field, "18", row18)
check("three games in print order", [g["game"] for g in b["games"]] == ["individual_net", "skins", "individual_gross"])
check("state LIVE, rules version stamped", b["state"] == "live" and b["rules_version"] == fl.FLIGHT_RULES["version"])
ig = next(g for g in b["games"] if g["game"] == "individual_gross")
check("Ind Gross carries SELECTION (frozen layer) and AMOUNTS (recomputed layer) side by side",
      ig["selection"]["flight_count"] == 3 and ig["amounts"]["bonus"] == 12.0 and ig["amounts"]["sum_check"])
sk = next(g for g in b["games"] if g["game"] == "skins")
check("Skins on the same 15 buyers: 2 flights, $135 each", [f["pot"] for f in sk["amounts"]["flights"]] == [135.0, 135.0])
inn = next(g for g in b["games"] if g["game"] == "individual_net")
check("Ind Net on 14 buyers (18h): 2 flights, amounts Low 88/44 High 88/44",
      [f["pot"] for f in inn["amounts"]["flights"]] == [132.0, 132.0], str(inn["amounts"]))

print("\n== settle(): SELECTION frozen, AMOUNTS recomputed, delta reported (B5) ==")
gross14 = [P(1, "A", 0.7), P(2, "B", 3.9), P(3, "C", 7.7), P(4, "D", 8.0), P(5, "E", 9.0), P(6, "F", 9.5),
           P(7, "G", 10.0), P(8, "H", 11.2), P(9, "I", 12.0), P(10, "J", 13.0), P(11, "K", 15.0),
           P(12, "L", 18.0), P(13, "M", 21.0), P(14, "N", 26.0)]
frozen = fl.build({"NET": [], "GROSS": gross14}, "18", row18)
frozen["state"] = "frozen"
ig0 = next(g for g in frozen["games"] if g["game"] == "individual_gross")
check("frozen field A: 3 flights 2/6/6, pots 14.40 / 43.20 / 43.20",
      [f["players"] for f in ig0["selection"]["flights"]] == [2, 6, 6]
      and [f["pot"] for f in ig0["amounts"]["flights"]] == [14.4, 43.2, 43.2])
# A credited WD (F drops out of flight 2), a late add at 3.0 (fits flight 1 by
# the frozen edges), and a late add at exactly 12.0 (goes UP into flight 3).
now = [p for p in gross14 if p["name"] != "F"] + [P(15, "Late Low", 3.0), P(16, "Late Twelve", 12.0)]
settled = fl.settle(frozen, {"NET": [], "GROSS": now}, row18)
ig1 = next(g for g in settled["games"] if g["game"] == "individual_gross")
check("state SETTLED", settled["state"] == "settled")
check("flight count and edges did not move", ig1["selection"]["flight_count"] == 3 and ig1["selection"]["edges"] == [6.0, 12.0])
check("headcounts now 3/5/7 (late low → F1, WD out of F2, 12.0 → F3)",
      [f["players"] for f in ig1["selection"]["flights"]] == [3, 5, 7], str([f["players"] for f in ig1["selection"]["flights"]]))
check("pots recomputed from ACTUAL buyers: 21.60 / 36.00 / 50.40, bonus $12.00 on 15 × $8",
      [f["pot"] for f in ig1["amounts"]["flights"]] == [21.6, 36.0, 50.4] and ig1["amounts"]["bonus"] == 12.0, str(ig1["amounts"]))
d = ig1["delta"]
check("delta names who added and who dropped, with their flight",
      sorted(x["name"] for x in d["added"]) == ["Late Low", "Late Twelve"]
      and [x["name"] for x in d["dropped"]] == ["F"] and d["dropped"][0]["flight_no"] == 2, str(d))
check("delta carries pot then vs now per flight and the total",
      d["flights"][0]["pot_before"] == 14.4 and d["flights"][0]["pot_after"] == 21.6
      and d["total_pot_before"] == 112.0 and d["total_pot_after"] == 120.0 and d["changed"])
check("labels re-derive from the settled membership", ig1["selection"]["flights"][0]["label"] == "0.7–3.9")
check("money out = money in after settlement", ig1["amounts"]["sum_check"])

# Places recompute at settlement from the FINAL flight headcount (#573).
ten = [P(i, f"T{i}", 6.0 + i * 0.3) for i in range(10)]        # all in the 6.0–11.9 band
b10 = fl.build({"NET": [], "GROSS": ten + [P(50, "Low", 1.0), P(51, "Low2", 2.0), P(52, "Hi", 14.0),
                                             P(53, "Hi2", 15.0), P(54, "Hi3", 16.0)]}, "18", row18)
igA = next(g for g in b10["games"] if g["game"] == "individual_gross")
check("a flight published at 10 pays two places (48.00 / 24.00)",
      [p["amount"] for p in igA["amounts"]["flights"][1]["places"]] == [48.0, 24.0], str(igA["amounts"]["flights"][1]))
nine_now = [p for p in ten if p["name"] != "T9"] + [P(50, "Low", 1.0), P(51, "Low2", 2.0), P(52, "Hi", 14.0),
                                                     P(53, "Hi2", 15.0), P(54, "Hi3", 16.0)]
sA = fl.settle(b10, {"NET": [], "GROSS": nine_now}, row18)
igB = next(g for g in sA["games"] if g["game"] == "individual_gross")
check("...and settling at 9 pays ONE place ($64.80) — places are AMOUNTS, not structure",
      [p["amount"] for p in igB["amounts"]["flights"][1]["places"]] == [64.8], str(igB["amounts"]["flights"][1]))
check("...the delta says the places changed", igB["delta"]["flights"][1]["places_before"] == [48.0, 24.0]
      and igB["delta"]["flights"][1]["places_after"] == [64.8])

# The VARIANT is frozen: ½ Net at 7 buyers on a nine stays ½ Net when an 8th
# arrives after the freeze (every matrix game-selection threshold freezes).
seven = [P(i, f"S{i}", 5.0 + i) for i in range(7)]
fz = fl.build({"NET": [], "GROSS": seven}, "9", row9)
sk0 = next(g for g in fz["games"] if g["game"] == "skins")
check("7 gross buyers on a nine froze as Skins ½ Net, one flight", sk0["selection"]["variant"]["name"] == "half_net" and sk0["selection"]["flight_count"] == 1)
st = fl.settle(fz, {"NET": [], "GROSS": seven + [P(99, "Eighth", 3.0)]}, row9)
sk1 = next(g for g in st["games"] if g["game"] == "skins")
check("an 8th buyer after the freeze does NOT flip the game to gross skins or add a flight",
      sk1["selection"]["variant"]["name"] == "half_net" and sk1["selection"]["flight_count"] == 1
      and sk1["selection"]["flights"][0]["players"] == 8)
check("...but the skins pot recomputes at 8 buyers ($104)", sk1["amounts"]["total_pot"] == 104.0)
ig_off = next(g for g in st["games"] if g["game"] == "individual_gross")
check("a game NOT running at the freeze stays not running at settlement",
      not ig_off["active"] and ig_off["delta"]["note"] == "game selection frozen: not running")

print("\n== invariants over random fields ==")
rnd = random.Random(7)
bad = 0
for _ in range(300):
    hk = rnd.choice(["9", "18"])
    n = rnd.randint(1, 40)
    fld = [P(i, f"R{i}", round(rnd.uniform(-2.0, 36.0), 1)) for i in range(n)]
    count = rnd.choice([1, 2, 3, 4])
    edges = fl.ladder_for(count)
    bands_ = fl.cut_by_edges(fld, edges)
    every_once = sorted(m["customer_id"] for b_ in bands_ for m in b_) == list(range(n))
    am = fl.gross_amounts(hk, [len(b_) for b_ in bands_])
    rate = fl.FLIGHT_RULES["gross"]["rate"][hk]
    paid = round(sum(f["pot"] for f in am["flights"]) + am["bonus"], 2)
    places_ok = all(abs(round(sum(p["amount"] for p in f["places"]), 2) - f["pot"]) < 0.005
                    for f in am["flights"] if f["players"])
    if not (every_once and abs(paid - round(rate * n, 2)) < 0.005 and places_ok and am["sum_check"]):
        bad += 1
check("300 random fields: every player in exactly one flight; flights + bonus = rate × N to the cent; places sum to each pot",
      bad == 0, f"{bad} bad")

print()
if F:
    print(f"FAILED ({len(F)}):")
    for f in F:
        print("  -", f)
    sys.exit(1)
print("ALL PASSED")
