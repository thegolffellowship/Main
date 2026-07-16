"""WHS playing-handicap calculation — Task #16 (Kerry 2026-07-16).

Pure, portable primitives for turning a player's handicap INDEX + the
SELECTED TEE (slope / rating / par) into a course handicap, a playing
handicap, and a per-hole stroke allocation — with NO Golf Genius input.
This is the keystone that untethers NET scoring: gross needs none of this,
net needs all of it.

Kept deliberately free of DB/Flask so it can be unit-tested in isolation,
carried to the TGF Platform unchanged, and reviewed by CA as a spec.

Scope note — everything here is on ONE scope. TGF plays 9-hole rounds, so
the index is a 9-hole index and slope/rating/par are the 9-hole tee values
GG's tee block carries. The same formulas hold for 18 if fed 18-hole values.

FIRST milestone (Kerry): perfect 100% playing handicap from the selected
tee. Per-game adjustments (allowance %, max-handicap caps, Team-Net
no-pops-on-par-3) layer on TOP of this base and are handled by callers /
the game-engine config — this module only exposes the hooks (`allowance`,
`max_hcp`, and the caller choosing which holes to allocate over).
"""

import math


def whs_round(x: float) -> int:
    """WHS rounding: to the nearest whole number, 0.5 rounds UP (toward
    +infinity, so a +0.5 plus-handicap value rounds toward 0). Python's
    built-in round() is banker's rounding (half-to-even) and must NOT be
    used for handicaps."""
    return math.floor(x + 0.5)


def course_handicap(index: float, slope: float, rating: float,
                    par: float) -> float:
    """WHS Course Handicap (unrounded):  index x (slope / 113) + (rating - par).

    All four inputs MUST be on the same scope (9-hole index with 9-hole
    slope/rating/par). Returns the raw float; round with whs_round when a
    whole number is needed."""
    return index * (slope / 113.0) + (rating - par)


def playing_handicap(index: float, slope: float, rating: float, par: float,
                     allowance: float = 1.0, max_hcp: float | None = None) -> int:
    """Playing Handicap = whs_round(Course Handicap x allowance), optionally
    capped at max_hcp BEFORE rounding.

    allowance defaults to 1.0 (100%) — the TGF base milestone. A game's
    handicap allowance (e.g. 0.85) and Max Playing Handicap cap are passed
    by the caller from game config; at 100% with no cap this is simply
    whs_round(course_handicap)."""
    ch = course_handicap(index, slope, rating, par) * allowance
    if max_hcp is not None:
        ch = min(ch, max_hcp)
    return whs_round(ch)


def allocate_strokes(playing_hcp: int, stroke_index_by_hole: dict,
                     max_pops: int = 2) -> dict:
    """Distribute a playing handicap across holes by stroke index.

    stroke_index_by_hole: {hole_number: stroke_index} for the holes played
    (stroke_index 1 = hardest). Allocation is over exactly those holes, so a
    9-hole round allocates over its 9 (their 18-hole stroke indexes are fine
    — only their RELATIVE order matters).

    Positive handicap: one stroke to each hole, hardest first; if the
    handicap exceeds the hole count it wraps for a 2nd stroke, capped at
    max_pops per hole (TGF rule: max 2 pops/hole). Plus handicap (negative):
    give a stroke BACK on the easiest holes (highest stroke index) first.

    Returns {hole_number: strokes_received} — positive = strokes received,
    negative = strokes given back, 0 = none. Sums to the playing handicap
    unless the max_pops cap or hole count truncates an extreme handicap.
    """
    holes = sorted(stroke_index_by_hole, key=lambda h: stroke_index_by_hole[h])
    n = len(holes)
    out = {h: 0 for h in holes}
    if n == 0 or playing_hcp == 0:
        return out
    if playing_hcp > 0:
        full, rem = divmod(playing_hcp, n)
        for rank, h in enumerate(holes):            # hardest first
            out[h] = min(full + (1 if rank < rem else 0), max_pops)
    else:
        give = -playing_hcp
        full, rem = divmod(give, n)
        for rank, h in enumerate(reversed(holes)):  # easiest first
            out[h] = -min(full + (1 if rank < rem else 0), max_pops)
    return out
