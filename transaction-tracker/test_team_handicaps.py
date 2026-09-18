"""The TEAM column is the game being played, computed the WHS way.

Kerry 2026-09-18, s18.11 Cedar Creek starter sheet: "the cart net
handicaps do not all look correct. Specifically people like Larry Anthis
and Richard Palacios. We have Cart Net going tomorrow which is 85%
handicaps." And: "For an 18 hole event, the TGF Handicap to be shown
should be the 18 hole handicap."

The sheet computed a foursome's Team Net (75%, off the lowest in the
GROUP) on a Cart Net night (85%, off the lowest in the CART), and applied
the allowance to the already-rounded PH (the double-rounding CA Queue #7
found). `team_handicaps_for_groups` now takes the unrounded course
handicap, applies the allowance, rounds once, and plays each unit off
its own lowest.

Run: python3 test_team_handicaps.py
"""
import os, sys, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_PATH", ":memory:")
logging.disable(logging.WARNING)
from email_parser import database as db                          # noqa: E402
from email_parser.handicap_calc import course_handicap, whs_round  # noqa: E402
F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond: F.append(label)

# Cedar Creek's 8:40 group off the Gold tees (18-hole card): slope 125,
# rating 70.1, par 71 — indexes as printed on the sheet (18-hole scale).
SLOPE, RATING, PAR = 125, 70.1, 71
def player(pos, name, idx18):
    return {"name": name, "cart_pos": pos,
            "course_handicap_raw": course_handicap(idx18, SLOPE, RATING, PAR)}
g = {"players": [player(1, "Richard Palacios", 15.4), player(2, "Larry Anthis", 16.0),
                 player(3, "Dan Stich", 16.0), player(4, "Will Wallace", 15.8)]}

print("Cart Net: 85%, off the lowest in the CART")
db.team_handicaps_for_groups([g], 0.85, "cart")
by = {p["name"]: p for p in g["players"]}
exp = {n: whs_round(course_handicap(i, SLOPE, RATING, PAR) * 0.85)
       for n, i in (("Richard Palacios", 15.4), ("Larry Anthis", 16.0), ("Dan Stich", 16.0), ("Will Wallace", 15.8))}
check("allowance is applied to the UNROUNDED course handicap and rounded once",
      all(by[n]["team_allowed"] == exp[n] for n in by), {n: (by[n]["team_allowed"], exp[n]) for n in by})
check("cart A plays off its own lowest (Palacios 0, Anthis the difference)",
      by["Richard Palacios"]["team_handicap"] == 0
      and by["Larry Anthis"]["team_handicap"] == exp["Larry Anthis"] - exp["Richard Palacios"], by)
check("cart B plays off ITS lowest, not cart A's",
      min(by["Dan Stich"]["team_handicap"], by["Will Wallace"]["team_handicap"]) == 0
      and by["Dan Stich"]["team_handicap"] == exp["Dan Stich"] - min(exp["Dan Stich"], exp["Will Wallace"]), by)

print("Team Net: off the lowest in the GROUP")
db.team_handicaps_for_groups([g], 0.75, "group")
by = {p["name"]: p for p in g["players"]}
low = min(whs_round(course_handicap(i, SLOPE, RATING, PAR) * 0.75) for i in (15.4, 16.0, 16.0, 15.8))
check("one lowest for the whole group", sum(1 for p in by.values() if p["team_handicap"] == 0) >= 1
      and all(p["team_allowed"] - low == p["team_handicap"] for p in by.values()), by)

print("The double-rounding is gone")
# 16.0 x 125/113 + (70.1-71) = 16.80; x0.85 = 14.28 -> 14. The OLD path rounded 16.80 -> 17 first, then 17 x 0.85 = 14.45 -> 14 here,
# but at 15.8: CH 16.58 -> 17 -> 14.45 -> 14 vs correct 16.58 x .85 = 14.09 -> 14; use a value that discriminates:
p = {"name": "x", "cart_pos": 1, "course_handicap_raw": 13.5}   # 13.5 x .85 = 11.475 -> 11; old: 14 x .85 = 11.9 -> 12
db.team_handicaps_for_groups([{"players": [p]}], 0.85, "cart")
check("13.5 course handicap at 85% is 11, not 12", p["team_allowed"] == 11, p)

print("Unit decision")
check("below 16 players with no matrix row is CART Net", db._event_team_unit(15, "18", db_path=":memory:")[0] == "cart")
check("16+ players with no matrix row is Team Net", db._event_team_unit(21, "9", db_path=":memory:")[0] == "group")

print("The sheet prints the event-scale index")
src = open(os.path.join(os.path.dirname(__file__), "templates/starter_sheet.html"), encoding="utf-8").read()
check("IDX cells read handicap_index_display", src.count("handicap_index_display") >= 2)
check("the footnote says which scale", "TGF handicap index ({{ pack.holes_key }}-hole)" in src)
check("the TEAM column is named for the game", "{% if pack.team_unit == 'cart' %}CART{% else %}TEAM{% endif %}" in src)
html = open(os.path.join(os.path.dirname(__file__), "templates/events.html"), encoding="utf-8").read()
check("the pairings cards show the index on the event's scale", "state.hcpScale === 18 ? 2 : 1" in html)
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
