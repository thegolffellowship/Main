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


def ruled_allocation_mode(mode: str, si_by_hole: dict) -> str:
    """Resolve the "ruled" stroke-allocation mode to a concrete one.

    Kerry, CA Queue #10/#11 (rule 3b, CA #771, 2026-09-27):
      * 9-HOLE ROUND  -> collapse the nine's stroke indexes to 1-9 and
        allocate over them ("subset"). "9 hole events collapse to 1-9 si.
        So it gets the full 3." A 9-hole PH of 3 receives all 3 strokes,
        and the front and back nines pay the same.
      * 18-HOLE ROUND -> the full 1-18 card ("full_card").

    Any explicit mode passes through unchanged, so a test or a sandbox can
    still ask for the other convention side by side (G2a reports both). The
    `full_card` guard in `allocate_strokes` stays: handed re-ranked 1..N
    indexes with a handicap it cannot carry, it RAISES rather than silently
    under-allocating.
    """
    if mode != "ruled":
        return mode
    return "subset" if len(si_by_hole) <= 9 else "full_card"


def ruled_dots(playing_hcp, stroke_index_by_hole: dict) -> dict:
    """{hole: strokes} for a playing handicap under the RULED allocation
    (CA #771: a nine collapses to 1-9, an 18 uses the full card). The ONE
    call both the G-0 publish (stored pops) and the printed scorecard
    (dots before the round) make, so the card and the record cannot
    disagree. None -> {}. A plus handicap is returned as the allocator
    gives it (strokes back, negative); a printer shows no dot for it
    because the plus comes off the ROUND (Kerry 2026-09-15)."""
    if playing_hcp is None or not stroke_index_by_hole:
        return {}
    return allocate_strokes(int(round(playing_hcp)), stroke_index_by_hole,
                            mode=ruled_allocation_mode("ruled", stroke_index_by_hole))


def allocate_strokes(playing_hcp: int, stroke_index_by_hole: dict,
                     max_pops: int = 2, mode: str = "subset") -> dict:
    """Distribute a playing handicap across holes by stroke index.

    stroke_index_by_hole: {hole_number: stroke_index} for the holes played
    (stroke_index 1 = hardest).

    `mode` is the LEAGUE SETTING for a round played over a subset of the card
    (e.g. a TGF nine), and the two modes give different stroke counts:

      "full_card" — a hole gets a stroke when its stroke index on
          the FULL 18-hole card is <= the playing handicap. A playing handicap
          of 3 played over the front nine therefore lands only TWO strokes,
          because stroke index 2 is on the back nine and is simply not played.
          This is Golf Genius's "Allocate strokes based on the full card
          Stroke Index Allocation", which is the setting on the TGF league
          (Kerry's handicap-settings screenshot, 2026-09-16).

      "subset"  (default) — re-rank the holes played and allocate over them, so a
          playing handicap of 3 always lands three strokes. This is GG's
          "Allocate strokes for the subset of holes played", which GG labels
          Recommended and TGF does NOT use.

    Under "subset" only the RELATIVE order of the stroke indexes matters;
    under "full_card" their ABSOLUTE values do.

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
    if mode == "full_card":
        # Absolute stroke index against the full card. A stroke lands only on
        # a hole actually played, so a subset round can deliver fewer strokes
        # than the playing handicap — that is the setting working, not a bug.
        #
        # GUARD. "full_card" is only meaningful when the stored stroke indexes
        # ARE the full card's. Two conventions exist in our data: a9.23 Avery
        # Ranch carries real GG indexes (1, 3, 5 ... 17 on a front nine),
        # while some rounds carry indexes re-ranked to 1..N over the holes
        # played. Applying "full_card" to a re-ranked nine silently caps every
        # handicap above 9 at one stroke per hole — a 14 would land 9 strokes
        # and nobody would see why. Refuse instead: a caller that means the
        # re-ranked convention should say "subset".
        if n and sorted(stroke_index_by_hole.values()) == list(range(1, n + 1)) \
                and n < 18 and abs(playing_hcp) > n:
            raise ValueError(
                f"full_card allocation needs FULL-CARD stroke indexes, but got "
                f"{n} holes indexed 1..{n} (the re-ranked subset convention) "
                f"with a handicap of {playing_hcp}. Pass mode='subset', or "
                f"store the holes' real 18-hole stroke indexes.")
        if playing_hcp > 0:
            for h, si in stroke_index_by_hole.items():
                out[h] = min(playing_hcp // 18 + (1 if si <= playing_hcp % 18
                                                  else 0), max_pops)
        else:
            give = -playing_hcp
            for h, si in stroke_index_by_hole.items():
                # Strokes are given BACK from the easiest hole down: on an
                # 18-hole card that is stroke index 18, 17, ...
                out[h] = -min(give // 18 + (1 if si > 18 - (give % 18) else 0),
                              max_pops)
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
