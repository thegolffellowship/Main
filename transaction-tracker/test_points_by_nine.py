"""18-hole points as two nine-hole entries (Kerry 2026-10-06, CoS #1338-5).

One 18-hole allocation sets where the pops fall; points are totalled per
nine from those pops; an 18 makes two race entries (D26, the COUNT only).
Golf Genius's per-nine re-allocation is NOT the model.
"""
import sys

from email_parser.database import _SCORING_FORMULA_DEFAULTS
from email_parser import live_scoring as ls
from email_parser.handicap_calc import allocate_strokes

FORMULAS = dict(_SCORING_FORMULA_DEFAULTS)
fails = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"  {detail}"))
    if not cond:
        fails.append(label)


# An 18 with every par 4, stroke index 1..18 alternating front/back the
# usual way (odd SIs on the front, even on the back).
SI = {h: (2 * h - 1 if h <= 9 else 2 * (h - 9)) for h in range(1, 19)}
holes = [{"hole": h, "par": 4, "stroke_index": SI[h]} for h in range(1, 19)]


def card(ph, scores):
    st = {"holes": holes, "players": [{"key": "p", "customer_id": 1, "name": "P",
                                       "playing_handicap": ph, "scores": scores}]}
    return ls.build_cards(st, FORMULAS)[0]


print("== one 18-hole allocation, points per nine ==")
c = card(7, {h: 4 for h in range(1, 19)})
alloc = allocate_strokes(7, SI, mode="full")
front_pops = sum(alloc.get(h, 0) for h in range(1, 10))
check("PH 7 on the full 1-18 card puts 4 pops on the front (SI 1,3,5,7) and 3 on the back",
      front_pops == 4 and sum(alloc.values()) == 7, alloc)
check("the card used that one allocation (not 7 per nine or 3.5 each)",
      sum(h["strokes_received"] for h in c["holes"][:9]) == 4
      and sum(h["strokes_received"] for h in c["holes"][9:]) == 3,
      [h["strokes_received"] for h in c["holes"]])
nb = c["points_by_nine"]
check("two entries, front then back", [n["nine"] for n in nb] == ["front", "back"], nb)
check("front = 9 pars + 4 pops", nb[0]["points"] == 9 * 1 + 4, nb[0])
check("back = 9 pars + 3 pops", nb[1]["points"] == 9 * 1 + 3, nb[1])
check("the two nines add up to the 18-hole total",
      nb[0]["points"] + nb[1]["points"] == c["stableford_net"], (nb, c["stableford_net"]))
check("both complete", nb[0]["complete"] and nb[1]["complete"])

print("\n== a part-played 18 ==")
c = card(7, {h: 4 for h in range(1, 13)})
nb = c["points_by_nine"]
check("front complete, back thru 3", nb[0]["complete"] and nb[1]["thru"] == 3 and not nb[1]["complete"], nb)

print("\n== a nine is one entry ==")
st = {"holes": holes[:9], "players": [{"key": "p", "customer_id": 1, "name": "P",
                                      "playing_handicap": 4, "scores": {h: 4 for h in range(1, 10)}}]}
check("no per-nine split on a nine", ls.build_cards(st, FORMULAS)[0]["points_by_nine"] is None)

print("\n== a plus on an 18: the round deduction is not guessed onto a nine ==")
c = card(-2, {h: 4 for h in range(1, 19)})
nb = c["points_by_nine"]
check("each nine flags the unassigned plus", all(n["plus_unassigned"] for n in nb), nb)
check("nine points carry no plus deduction; the 18 total does",
      nb[0]["points"] + nb[1]["points"] + (c["points_plus_adjust"] or 0) == c["stableford_net"],
      (nb, c["points_plus_adjust"], c["stableford_net"]))

print()
if fails:
    print(f"FAILED ({len(fails)}): {fails}")
    sys.exit(1)
print("ALL PASS")
