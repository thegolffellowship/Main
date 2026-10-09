"""Two live-round fixes (Kerry 2026-10-09, practice round at The Hideout):
"The photo of scorecard is not taking when I try to add it with the tracker"
and a leaderboard row tap reading "Couldn't load the card (The string did not
match the expected pattern.)".

Pins: (1) while the camera is open no reload rebuilds the scoring screen, and
the photo input carries its own change handler (a re-rendered, detached input
still delivers the photo; proven in Chromium with the scratch harness
phototest.py); (2) a live-entry leaderboard row (negative id) renders its card
from the board payload instead of fetching /api/scoring/scorecard/<negative>.

Run: python3 test_photo_pick_live_card.py
"""
import os, sys, subprocess, json
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


se = open("templates/score_entry.html", encoding="utf-8").read()
print("photo: the camera is open")
check("the 15-second refresh waits while picking", "!busy && !pickingNow()) load();" in se)
check("returning to the page doesn't rebuild while picking", "if (!pickingNow()) load();" in se)
check("the input gets its own change handler at the tap", 'inp.addEventListener("change"' in se and "inp._direct = true" in se)
check("the delegated handler skips an input that took it itself", "if (e.target._direct) return;" in se)
check("a cancelled camera clears the hold", 'inp.addEventListener("cancel"' in se)

ct = open("templates/contests.html", encoding="utf-8").read()
print("leaderboard: a live-entry card")
check("negative ids render from the payload", "evlbLiveCard(d, rid) || {holes: []}" in ct
      and "const live = Number(rid) < 0" in ct)
i = ct.index("function evlbLiveCard(d, rid)")
fn = ct[i:ct.index("\n    function evlbWireEvent", i)]
js = fn + """
const d = {cards: {"-9": [[1,5,2],[2,4,1]]}, hole_par: {"1":5,"2":3},
           overall_board: [{scoring_round_id: -9, hcp: 27, net: 59}]};
const c = evlbLiveCard(d, -9);
console.log(JSON.stringify({n: c.holes.length, h1: c.holes[0], ph: c.round.playing_handicap,
  net: c.derived_totals.net, empty: evlbLiveCard({cards:{}, hole_par:{"1":4}}, -1)}));
"""
out = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True).stdout)
check("holes from the payload with par, gross, pops", out["n"] == 2 and out["h1"] == {
    "hole_number": 1, "par": 5, "strokes": 5, "strokes_received": 2, "vs_par": 0, "net_vs_par": -2}, out)
check("PH and net from the row", out["ph"] == 27 and out["net"] == 59, out)
check("no scores yet: nothing to render (the page shows 'No hole data')", out["empty"] is None, out)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
