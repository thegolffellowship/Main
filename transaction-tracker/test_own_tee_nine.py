"""A player on another tee gets ALL his strokes on the nine he played.

s9.27 The Quarry (10/13): Dan Stich played the Blues (back-nine stroke
indexes 4,18,14,10,2,16,12,6,8) while the event's most-played tee was the
Golds. The engine handed the allocator his tee's 18-hole map, so his 6
strokes went to stroke indexes 1-6 across the whole card and only 3 landed
on holes he played: net 41 instead of 38, and he fell out of the Individual
Net Flight 2 tie he shared with Angelone and Burlingame. The nine's own
indexes must collapse to 1-9, exactly as the event's card does.

Run: python3 test_own_tee_nine.py
"""
import sys

from email_parser.database import _SCORING_FORMULA_DEFAULTS
from email_parser import live_scoring as ls

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


PARS = {10: 4, 11: 4, 12: 3, 13: 4, 14: 4, 15: 5, 16: 3, 17: 4, 18: 5}
GOLD = {10: 4, 11: 18, 12: 14, 13: 10, 14: 2, 15: 16, 16: 12, 17: 6, 18: 8}
# The Blue tee's FULL card: odd indexes on the front, even on the back.
BLUE_18 = {h: 2 * h - 1 for h in range(1, 10)}
BLUE_18.update({10: 4, 11: 18, 12: 14, 13: 10, 14: 2, 15: 16, 16: 12, 17: 6, 18: 8})

state = {
    "holes": [{"hole": h, "par": PARS[h], "stroke_index": GOLD[h]} for h in PARS],
    "players": [
        {"key": "stich", "customer_id": 298, "name": "Dan Stich",
         "playing_handicap": 6, "buys_net": True,
         "scores": dict(zip(PARS, [6, 6, 4, 4, 4, 8, 2, 4, 6])),
         "stroke_index_by_hole": BLUE_18},
        {"key": "baker", "customer_id": 87, "name": "Adam Baker",
         "playing_handicap": 5, "buys_net": True,
         "scores": dict(zip(PARS, [5, 4, 3, 5, 3, 6, 4, 4, 5]))},
    ],
}
cards = {c["key"]: c for c in ls.build_cards(state, dict(_SCORING_FORMULA_DEFAULTS))}
stich = cards["stich"]
got = {h["hole"]: h["strokes_received"] for h in stich["holes"]}
check("all 6 of Stich's strokes land on the nine he played",
      sum(got.values()) == 6, got)
check("on the six hardest holes of HIS tee's nine (10, 13, 14, 16, 17, 18)",
      {h for h, n in got.items() if n} == {10, 13, 14, 16, 17, 18}, got)
check("Stich's net is 44 - 6 = 38, the stored card's net", stich["net"] == 38, stich["net"])
check("a player on the event's own tee is unchanged (Baker 39 - 5 = 34)",
      cards["baker"]["net"] == 34, cards["baker"]["net"])
check("the card shows his tee's index on each hole",
      next(h for h in stich["holes"] if h["hole"] == 14)["stroke_index"] == 2)

print(f"\n{len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
