"""TGF Live Scoring engine — Stage 1 of the untether-from-GG plan.

Computes EVERY event game from nothing but raw gross hole scores plus the
course/tee facts we already own (par, yardage, stroke index) and each
player's playing handicap. Golf Genius contributes nothing here — that is
the whole point. `docs/claude/game-engine.md` Stage 1:

    "Rely on GG for ONLY the raw gross hole scores; compute EVERYTHING
     ourselves (all games, all races) from those. Stand a live leaderboard
     next to GG's at a real event and diff, game-by-game and race-by-race,
     until we reproduce GG exactly."

Kept deliberately free of DB/Flask (the `match_play.py` / `season_payouts.py`
pattern) so it unit-tests in isolation and carries to the TGF Platform
unchanged. The two pieces of shared math it does NOT reimplement are the
formula layer (`compute_hole_derivations`) and the WHS stroke allocation
(`handicap_calc.allocate_strokes`) — reimplementing either would defeat the
parity harness this engine exists to feed. The formula-layer function is
injected (`derive_hole`) and defaults to a lazy import, so the engine still
imports cleanly with no database module present.

Rules are DATA (Guiding Principle 2): everything that varies by player
count, hole count, or game lives in SEED_LIVE_SCORING_CONFIG, mirroring the
RATIFIED side-games spec v1.0 (`docs/claude/side-games.md`). Nothing in this
module hard-codes a threshold.
"""

from __future__ import annotations

import random

from .handicap_calc import allocate_strokes

# ---------------------------------------------------------------------------
# Rules-as-data. Every threshold below is transcribed from the RATIFIED
# side-games spec v1.0 tables; see docs/claude/side-games.md.
#
# POPS ARE A PROPERTY OF THE GAME, NOT OF THE CARD (2026-09-16).
# Every game declares `pops_per_hole`. ROUND-level games (Individual Net,
# Individual Gross) are `gross total - playing handicap` and never put a
# stroke on a hole; HOLE-level games (Team Net best-ball, Net Points /
# Stableford, half-Net Skins) allocate by stroke index because the hole
# cannot be decided otherwise. Surfaces must READ this flag rather than
# assume — rendering per-hole net everywhere is why a plus handicapper's
# Individual Net view showed circle marks for a mechanic that game does
# not use.
#
# USGA HANDICAP ALLOWANCES (Rules of Handicapping, Appendix C).
# Recorded as data so a non-developer can read it and so no game has to
# carry a percentage in code. VERIFICATION STATE IS PART OF THE DATA: the
# four-player ladder below is confirmed and matches Kerry's ratified Team
# Net figures exactly; the two-player CART Net row is NOT confirmed
# (usga.org and every mirror are blocked by this environment's network
# egress proxy) and is therefore ABSENT rather than guessed at. CA Queue
# #8 carries the ask. Nothing may fall back to a default for it — a game
# that needs it must report, not assume.
# ---------------------------------------------------------------------------

_USGA_ALLOWANCES: dict = {
    # {format_key: {"allowance_pct": n, "confirmed": bool, "source": str}}
    # Four-player team ladder — CONFIRMED, and identical to Kerry's
    # 2026-09-16 ruling ("Team Net is 75% for one ball, 85% for two ball,
    # and 100% for 3 or 4").
    "best_1_of_4": {"allowance_pct": 75, "confirmed": True,
                    "source": "USGA Appendix C, four-player ladder"},
    "best_2_of_4": {"allowance_pct": 85, "confirmed": True,
                    "source": "USGA Appendix C, four-player ladder"},
    "best_3_of_4": {"allowance_pct": 100, "confirmed": True,
                    "source": "USGA Appendix C, four-player ladder"},
    "best_4_of_4": {"allowance_pct": 100, "confirmed": True,
                    "source": "USGA Appendix C, four-player ladder"},
    # Two-player (CART Net) — RULED by Kerry 2026-09-16: "standard should be
    # 85%" for one ball, "Two Ball would be 100%". Best 1 of 2 is also USGA's
    # Four-Ball Stroke Play figure, which agrees independently.
    #
    # Honest provenance: Kerry believed he had already supplied Cart Net
    # setup screenshots ("I thought I already gave you Cart Net screenshots
    # for 1 ball"). NO SUCH SCREENSHOT REACHED THIS SESSION — these rows rest
    # on his ruling, not on a Golf Genius settings screen, which is a weaker
    # footing than the half-Net dials that were verified against a9.23. If a
    # Cart Net event ever fails to reproduce GG, re-check the screen first.
    "best_1_of_2": {"allowance_pct": 85, "confirmed": True,
                    "source": "Kerry ruling 2026-09-16; agrees with USGA "
                              "Four-Ball Stroke Play. NOT screenshot-verified"},
    "best_2_of_2": {"allowance_pct": 100, "confirmed": True,
                    "source": "Kerry ruling 2026-09-16. NOT screenshot-verified"},
    # FIVESOME — Kerry 2026-09-16: "Fivesome 1 ball remains 75% now, but will
    # need a dial specifically for that." Rule 15f made team size follow the
    # GROUP, so a five-player team is reachable by ratified rule. USGA
    # Appendix C stops at four and publishes no one-of-five row.
    #
    # This is its OWN row on purpose rather than a fall-through to the
    # four-player 75%: the two happen to carry the same number today, and a
    # fall-through would make that coincidence invisible on the day Kerry
    # changes it. `confirmed` is True because he ruled it; `provisional` says
    # the number is a holding position, not a settled allowance.
    "best_1_of_5": {"allowance_pct": 75, "confirmed": True, "provisional": True,
                    "source": "Kerry ruling 2026-09-16 — holding at the "
                              "four-player figure; no USGA row exists for "
                              "one of five. CA Queue #9"},
    # Deliberately absent: best_2_of_5 and above. Kerry ruled the ONE-ball
    # case only. A five-player Best 2 must report rather than assume.
}

def team_allowance_pct(game_cfg: dict, team_size: int, balls: int) -> dict:
    """Resolve a team game's handicap allowance, or REFUSE and say why.

    The allowance depends on BOTH how many players are on the team and how
    many balls count. USGA Appendix C publishes the four-player ladder and
    stops there; TGF's other sizes are Kerry's rulings. Where neither exists
    this returns `pct: None` with a reason, because a team game that cannot
    name its allowance must report rather than fall back to a neighbouring
    row — a wrong allowance is a wrong payout, and a silent one is worse.

    Why this is not a plain dict lookup: the five-player one-ball row and the
    four-player one-ball row are both 75% today (Kerry, 2026-09-16: "Fivesome
    1 ball remains 75% now, but will need a dial specifically for that"). If
    a fivesome fell through to the four-player row the two numbers would be
    the SAME NUMBER rather than two numbers that happen to agree, and the day
    Kerry moves one, the other would move with it silently.

    Returns {"pct", "confirmed", "provisional", "source", "reason"}.
    """
    table = game_cfg.get("allowance_pct_by_balls") or {}
    row = table.get(str(team_size))
    if row is None:
        return {"pct": None, "confirmed": False, "provisional": False,
                "source": None,
                "reason": f"no allowance is defined for a {team_size}-player "
                          f"team; sizes on file: "
                          f"{', '.join(sorted(table)) or 'none'}"}
    pct = row.get(str(balls))
    if pct is None:
        return {"pct": None, "confirmed": False, "provisional": False,
                "source": None,
                "reason": f"a {team_size}-player team has no ruled allowance "
                          f"for BEST {balls}; ruled ball counts at that size: "
                          f"{', '.join(sorted(row)) or 'none'}"}
    meta = _USGA_ALLOWANCES.get(f"best_{balls}_of_{team_size}", {})
    return {"pct": pct, "confirmed": bool(meta.get("confirmed")),
            "provisional": bool(meta.get("provisional")),
            "source": meta.get("source"), "reason": None}


# "Off the lowest in the group" is NOT a USGA allowance. USGA applies
# play-off-the-low to MATCH play; TGF/GG apply it to Team and Cart Net
# stroke play as a house convention. It is a SEPARATE dial on every game
# that uses it, never folded into the percentage.
_OFF_LOWEST_IS_TGF_CONVENTION = True


SEED_LIVE_SCORING_CONFIG: dict = {
    "version": 1,
    "games": {
        "individual_net": {
            "label": "Individual Net",
            "basis": "net",
            "format": "stroke",
            "competition": "player_v_flight",
            "eligibility": "net_buyers",
            # ROUND-level. Kerry, 2026-09-16: "Individual Net is not a pops
            # per hole game, so pops don't need to show on individual net
            # views. It is instead a Gross Score - PH = Net Score."
            "pops_per_hole": False,
            # Flight COUNT by buyer count, per holes-type. Bands are
            # [min_buyers, max_buyers_or_None, flights].
            "flight_bands": {
                "9": [[0, 11, 1], [12, None, 2]],
                "18": [[0, 13, 1], [14, 33, 2], [34, 49, 3], [50, 64, 4]],
            },
            # Observed GG split for the 9-hole 2-flight case (side-games.md:
            # "split observed at HCP 12.0"). When a break list is present it
            # WINS over equal-size splitting; the parity harness exists to
            # confirm or refute it at every other band.
            "flight_breaks": {"9": {"2": [12.0]}},
        },
        "individual_gross": {
            "label": "Individual Gross",
            "basis": "gross",
            "format": "stroke",
            "competition": "player_v_flight",
            "eligibility": "gross_buyers",
            # Gross games never see a handicap at all, so there is nothing
            # to put on a hole.
            "pops_per_hole": False,
            # Activation thresholds are the LIVE matrix values (admin
            # lowered them from the Excel seed's 20/16).
            "min_buyers": {"9": 16, "18": 12},
            "flight_bands": {
                "9": [[16, 19, 3], [20, None, 4]],
                "18": [[12, 15, 3], [16, None, 4]],
            },
        },
        "team_net": {
            "label": "Team Net",
            "basis": "net",
            "format": "best_ball_vs_par",
            "competition": "foursome_v_field",
            "eligibility": "all",
            # The DEFAULT team size. Pairing rule 15f (ratified 2026-09-16)
            # makes the real size follow the GROUP — Kerry: "Could be more if
            # fivesomes are selected" — so this is a fallback, not a constant.
            "team_size": 4,
            # HOLE-level: best ball per hole cannot be decided without
            # knowing which ball got a stroke on that hole.
            "pops_per_hole": True,
            # Allowance follows the BALL COUNT **within the team's actual
            # size** (Kerry 2026-09-16). The four-player ladder matches USGA
            # Appendix C exactly. The five-player row is Kerry's ruling
            # ("Fivesome 1 ball remains 75% now, but will need a dial
            # specifically for that") and is its OWN entry rather than a
            # fall-through, so the day he changes it there is one place to
            # change and the 75% coincidence is not load-bearing.
            "allowance_pct_by_balls": {
                "4": {"1": 75, "2": 85, "3": 100, "4": 100},
                "5": {"1": 75},        # Kerry ruling; 2-of-5 and up UNRULED
                "2": {"1": 85, "2": 100},   # CART Net, Kerry ruling
            },
            "off_lowest": True,
            # game-engine.md lists disallow-strokes-on-par-3 as a team-game
            # attribute. TGF's ratified side-games spec does not assert it,
            # so it ships OFF and is a config toggle, never a code branch.
            "no_pops_on_par3": False,
        },
        "skins": {
            "label": "Skins",
            "format": "skins",
            "competition": "player_v_field",
            "eligibility": "gross_buyers",
            # Skins is a HOLE-level game in every variant — the stroke, when
            # there is one, lands on a hole by stroke index. See the
            # "pops_per_hole" note at the top of this config.
            "pops_per_hole": True,
            "flight_bands": {
                "9": [[0, 7, 1], [8, None, 2]],
                "18": [[0, 7, 1], [8, 31, 2], [32, 47, 3], [48, None, 4]],
            },
            # ---------------------------------------------------------------
            # THE MATRIX IS THE GOVERNING LAYER (a9.23 Avery Ranch, 2026-09-15).
            # The buyer count does not merely change the POT — it changes WHICH
            # GAME IS PLAYED. Four players bought the gross bundle on a nine,
            # so the matrix ran "SKINS 1/2 Net $", a NET game, and our engine
            # computed GROSS skins and concluded Golf Genius was contradicting
            # itself. GG was right. The rules of the game it actually ran lived
            # only in a GG settings screen.
            #
            # Variants are therefore DATA, each carrying its own basis and its
            # own handicap dials, and the selection is REPORTED (see
            # `select_variant`) rather than inferred at the point of use.
            # ---------------------------------------------------------------
            "variants": [
                {
                    "name": "half_net",
                    "label": "Skins \u00bd Net",
                    "gg_name": "SKINS 1/2 Net $",
                    # Buyer band per holes-type: [min, max_or_None].
                    "when_buyers": {"9": [0, 7], "18": [0, 7]},
                    "basis": "net",
                    # Allowance % and "off the lowest" are TWO SEPARATE DIALS
                    # and must stay that way. USGA's allowance is a percentage
                    # of each player's own Course Handicap; "off the lowest in
                    # the group" is an additional TGF/GG convention that USGA
                    # applies to MATCH play. Collapsing them gets the maths
                    # wrong in one direction or the other.
                    "handicap": {
                        "method": "usga_net",
                        "allowance_pct": 50,
                        "off_lowest": True,
                        # RATIFIED 2026-09-16 from Kerry's Golf Genius league
                        # handicap settings + GG's own worked example for
                        # Eduardo Melchor on a9.23. Reproduces GG's published
                        # Playing Handicap column for all four players AND its
                        # skins board exactly. See CA Queue #7.
                        #
                        # "Round up" in GG means round HALF up, not ceiling —
                        # its tooltip reads "A handicap allowance 50% applied
                        # to a CH of 13 becomes 7" (6.5 -> 7). Melchor's
                        # 3.444 -> 3 and Zapata's 2.746 -> 3 confirm nearest.
                        "rounding": "half_up",
                        # GG league setting: "Allocate strokes based on the
                        # full card Stroke Index Allocation" (NOT its
                        # "subset of holes played", which GG marks
                        # Recommended and TGF does not use). Ratified from
                        # the settings screen. a9.23 does NOT discriminate
                        # the two — both reproduce its board — so this rests
                        # on the setting, not on the replay.
                        "stroke_allocation": "full_card",
                        "rounding_ratified": True,
                        "ratified_source": (
                            "GG league handicap settings + GG worked example "
                            "(Melchor, a9.23), Kerry 2026-09-16"),
                    },
                },
                {
                    "name": "gross",
                    "label": "Skins",
                    "gg_name": "Skins",
                    "when_buyers": {"9": [8, None], "18": [8, None]},
                    "basis": "gross",
                    # Gross games never see a handicap at all.
                    "handicap": None,
                },
            ],
        },
        "mvp": {
            "label": "MVP",
            "basis": "net",
            "format": "stableford",
            "competition": "player_v_field",
            "eligibility": "net_buyers",
            # HOLE-level: Stableford scores each hole, so the stroke has to
            # land on one. (The PLUS rule is the deliberate exception — a
            # give-back stroke is clamped per hole and the plus comes off
            # the round's total once. See build_cards.)
            "pops_per_hole": True,
            # City MVP = highest net Stableford POINTS among NET buyers;
            # tiebreak Individual Net score -> gross score -> split.
            "tiebreakers": ["net", "gross"],
            # An ace on the adjusted championship scale is the most a single
            # hole can move a player, so a card short of a full round leaves
            # the result provisional while anyone can still catch the leader.
            "max_points_per_hole": 9,
        },
        "ctp": {
            "label": "Closest to Pin",
            "format": "manual",
            "eligibility": "all",
            "pops_per_hole": False,
            "slots_per_nine": 2,
            # More par-3s than slots -> automation selects the SHORTEST.
            "select_par3_by": "shortest",
            # Fewer par-3s than slots -> the leftover dollar(s) become a
            # Longest Putt contest on the last hole.
            "spillover": "longest_putt_last_hole",
        },
        "hio": {
            "label": "Hole-in-One",
            "format": "auto_detect",
            "eligibility": "members_only",
            "pops_per_hole": False,
            # A raw ace is gross strokes == 1. Guests/first-timers pay in
            # but cannot win (side-games.md).
        },
    },
}


def _bands_lookup(bands: list, n: int, default=None):
    """Rules-as-data band resolver: [[lo, hi_or_None, value], ...]."""
    for lo, hi, value in bands or []:
        if n >= lo and (hi is None or n <= hi):
            return value
    return default


# ---------------------------------------------------------------------------
# Formula layer (injected — see module docstring)
# ---------------------------------------------------------------------------

def _default_derive_hole(par, strokes, strokes_received, formulas, game=False):
    from .database import compute_hole_derivations
    return compute_hole_derivations(par, strokes, strokes_received, formulas,
                                    game=game)


def _derive_game(derive_hole, par, strokes, strokes_received, formulas):
    """The GAME derivation for one hole — the plus rule applied by the
    mechanism where the injected deriver supports it, and by the clamp
    otherwise. `build_cards` takes `derive_hole` as an injection point
    (the parity harness supplies its own), so this cannot assume the
    engine's own signature."""
    if derive_hole is _default_derive_hole:
        return derive_hole(par, strokes, strokes_received, formulas, game=True)
    # An injected deriver (the parity harness supplies its own) may predate
    # the flag, so clamp at the call instead — the same arithmetic the
    # mechanism performs. Narrowed to this branch deliberately: a blanket
    # try/except TypeError would swallow a real error inside the engine
    # and quietly return a second, differently-computed answer.
    return derive_hole(par, strokes, max(0, strokes_received or 0), formulas)


# ---------------------------------------------------------------------------
# Round state -> per-player cards
# ---------------------------------------------------------------------------

def build_cards(state: dict, formulas: dict, derive_hole=None) -> list[dict]:
    """Turn the raw round state into one derived card per player.

    `state` shape (all plain data, no DB rows):
        holes:   [{"hole": 1, "par": 4, "stroke_index": 5, "yardage": 380}, ...]
        players: [{"key", "customer_id", "name", "playing_handicap",
                   "flight", "team", "buys_net", "buys_gross", "is_member",
                   "scores": {hole: gross_strokes},
                   "strokes_received": {hole: n},    # optional
                   "course_handicap": float          # optional, UNROUNDED
                  }, ...]

    `course_handicap` is the unrounded WHS course handicap for the tee played
    (index x slope/113 + rating - par). Supply it wherever it is known: a
    per-game allowance must be applied to it, NOT to the rounded playing
    handicap, or the result double-rounds and stops matching Golf Genius.
    See `game_handicaps` for the worked example.

    A player's strokes_received is USED AS GIVEN when supplied (that is how
    a GG-seeded card keeps GG's own handicap dots, so a parity diff compares
    scoring math and not allocation math). When absent it is derived from the
    playing handicap by WHS stroke-index allocation — the Stage-2 path, where
    nobody hands us dots.
    """
    derive_hole = derive_hole or _default_derive_hole
    # The league's stroke-allocation setting. TGF's Golf Genius league is set
    # to "full card Stroke Index Allocation", so a nine allocates against the
    # 18-hole card and can deliver fewer strokes than the playing handicap.
    # Deliberately "subset" here, NOT the league's "full_card". This is the
    # headline net game's allocation and it is not this lane's to change: no
    # real GG event has yet been checked that discriminates the two on the
    # card path, and some rounds store stroke indexes re-ranked to 1..N,
    # where "full_card" would silently under-allocate. Carried as CA Queue
    # #10. `game_handicaps` uses the league setting because a9.23 verified it.
    allocation_mode = state.get("stroke_allocation", "subset")
    hole_meta = {h["hole"]: h for h in state.get("holes") or []}
    si_by_hole = {h: (m.get("stroke_index") or 99) for h, m in hole_meta.items()}
    cards = []
    for p in state.get("players") or []:
        scores = {int(k): v for k, v in (p.get("scores") or {}).items()
                  if v is not None}
        ph = p.get("playing_handicap")
        given = {int(k): v for k, v in (p.get("strokes_received") or {}).items()}
        if given:
            received = given
            allocation_source = "given"
        elif ph is None:
            received = {}
            allocation_source = "none"
        else:
            received = allocate_strokes(int(ph), si_by_hole,
                                        mode=allocation_mode)
            allocation_source = "derived"

        holes_out, totals = [], {
            "gross": 0, "net": 0, "stableford_net": 0, "stableford_gross": 0,
            "adjusted_gross": 0, "net_vs_par": 0, "vs_par": 0,
        }
        for hole in sorted(hole_meta):
            meta = hole_meta[hole]
            strokes = scores.get(hole)
            sr = received.get(hole, 0) or 0
            d = derive_hole(meta.get("par"), strokes, sr, formulas)
            # POINTS never make a hole harder (Kerry 2026-09-15): a plus
            # player's give-back stroke reads as zero per hole and the
            # plus comes off the TOTAL once, below. That rule now lives
            # in the MECHANISM (`compute_hole_derivations(..., game=True)`,
            # v2.459.0) instead of in this local `max(0, sr)` — the local
            # version is what two other surfaces never inherited.
            # Stroke-play net keeps the real allocation: the total is the
            # same either way there, and only stableford is hole-shaped.
            d_pts = _derive_game(derive_hole, meta.get("par"), strokes, sr,
                                 formulas) if sr < 0 else d
            row = {"hole": hole, "par": meta.get("par"),
                   "yardage": meta.get("yardage"),
                   "stroke_index": meta.get("stroke_index"),
                   "strokes": strokes, "strokes_received": sr, **d,
                   # POINTS only — the hole's stroke-play net keeps the
                   # real allocation, which Net and Team Net play off.
                   "stableford_net": d_pts["stableford_net"]}
            holes_out.append(row)
            if strokes is None:
                continue
            totals["gross"] += strokes
            totals["net"] += strokes - sr
            totals["stableford_net"] += d_pts["stableford_net"] or 0
            totals["stableford_gross"] += d["stableford_gross"] or 0
            totals["adjusted_gross"] += d["adjusted_strokes"] or 0
            totals["vs_par"] += d["vs_par"] or 0
            totals["net_vs_par"] += d["net_vs_par"] or 0

        # The plus, taken off the round rather than off a hole.
        pts_adjust = 0
        if ph is not None and float(ph) < 0 and any(
                h["strokes"] is not None for h in holes_out):
            from .database import plus_round_deduction
            pts_adjust = -plus_round_deduction(ph)
            totals["stableford_net"] += pts_adjust

        thru = sum(1 for h in holes_out if h["strokes"] is not None)
        cards.append({
            "key": p.get("key"),
            "customer_id": p.get("customer_id"),
            "name": p.get("name"),
            "playing_handicap": ph,
            "course_handicap": p.get("course_handicap"),
            "flight": p.get("flight"),
            "team": p.get("team"),
            "buys_net": bool(p.get("buys_net")),
            "buys_gross": bool(p.get("buys_gross")),
            "is_member": bool(p.get("is_member", True)),
            "holes": holes_out,
            "thru": thru,
            "points_plus_adjust": pts_adjust or None,
            "complete": thru == len(hole_meta) and len(hole_meta) > 0,
            "allocation_source": allocation_source,
            **totals,
        })
    return cards


# ---------------------------------------------------------------------------
# Flighting
# ---------------------------------------------------------------------------

def assign_flights(cards: list[dict], game_cfg: dict, holes_key: str) -> dict:
    """Return {flight_label: [card, ...]} for an eligible field.

    Explicit per-player flights (set in the sandbox, or carried from a GG
    import) always win — that is how the harness pins a known-good GG
    flighting and isolates the SCORING diff from the FLIGHTING diff. With no
    explicit flights the count comes from the ratified band table and the
    field is split by handicap: at a configured break list, on those
    handicap thresholds; otherwise into equal-size bands.
    """
    n = len(cards)
    bands = (game_cfg.get("flight_bands") or {}).get(holes_key)
    count = _bands_lookup(bands, n, 1) if bands else 1
    explicit = [c for c in cards if c.get("flight")]
    if explicit and len(explicit) == n:
        out: dict = {}
        for c in cards:
            out.setdefault(str(c["flight"]), []).append(c)
        return dict(sorted(out.items()))
    if count <= 1 or n == 0:
        return {"1": list(cards)}

    ranked = sorted(cards, key=lambda c: (
        c["playing_handicap"] if c["playing_handicap"] is not None else 99,
        c["name"] or ""))
    breaks = ((game_cfg.get("flight_breaks") or {}).get(holes_key) or {}
              ).get(str(count))
    out = {str(i + 1): [] for i in range(count)}
    if breaks:
        for c in ranked:
            hcp = c["playing_handicap"] if c["playing_handicap"] is not None else 99
            slot = sum(1 for b in breaks if hcp >= b)
            out[str(min(slot + 1, count))].append(c)
    else:
        base, rem = divmod(n, count)
        i = 0
        for f in range(count):
            take = base + (1 if f < rem else 0)
            out[str(f + 1)] = ranked[i:i + take]
            i += take
    return out


# ---------------------------------------------------------------------------
# Flighting rule (Kerry, 2026-07-29) — the last tethered piece
#
# Everything else in this engine already reproduces GG from raw scores.
# Flighting is the one rule we did not own, and `determine_event_game_results`
# deliberately refuses to guess it (GG labels only, else "flights_unknown").
# This is the rule as DATA so we can generate flights ourselves.
#
# Kerry's ruleset so far:
#   - Flight on the RAW TGF HANDICAP INDEX (not the playing handicap).
#   - Two modes, both legitimate: equal-size groups (traditional) and fixed
#     bands (the recent trend). Ideal is fixed bands that also come out even;
#     real fields do not cooperate.
#   - Individual Net splits near the middle, but the LOW flight never goes
#     above 11.9 — 11.9 is a ceiling on the break, not the break itself.
#   - Gross bands harder (a high index has little chance in a low flight) and
#     runs a MINIMUM of three flights whenever it is active, for entry
#     incentive.
#   - Breaks are floors for the upper flight: 12.0 goes UP, 11.9 is the top of
#     the flight below. No value is claimed by two flights.
#   - Flight count may be skewed DOWN when the field's indexes are
#     concentrated (3 -> 2). That falls out of the min-flight merge below
#     rather than needing its own test.
#
# RATIFIED SINCE (mailbox #571-#575, Kerry 2026-09-18/19, revised #582
# 2026-09-21 — the rule set as data lives in `email_parser/flighting.py`):
#   - NO minimum flight size, NO merging, ever (B2 superseded). A flight of
#     1 simply is that size; the min_flight_size dial below is 0 and stays
#     a dial only so the Flighting Lab can still show what merging WOULD do.
#   - the 3-flight ladder <6.0 / 6.0-11.9 / 12.0+ and the 4-flight ladder
#     adding 12.0-17.9 / 18.0+; cut lines never move.
#   - the index is the 18-hole number (ruled 2026-07-30, #253).
# ---------------------------------------------------------------------------

SEED_FLIGHT_CONFIG: dict = {
    # KERRY RULING (2026-07-30, relayed via platform-claude mailbox #253):
    # "Handicap bands for flighting are all based on 18 hole TGF handicaps,
    # which is simply 2 times the 9 hole handicap."
    #
    # The DEFINITION is load-bearing: 18-hole TGF handicap means exactly
    # 2 x the 9-hole index — a TGF convention, not a WHS derivation. Verified
    # across the codebase: every 18-hole index is `round(index_9 * 2, 1)`
    # (get_all_handicap_players, get_customer_scoring_profile, the /api
    # handicap map). No 18-hole handicap index is derived from course
    # ratings anywhere, so the divergence risk raised in #253 does not exist
    # here — but the setting stays explicit so it can never be assumed again.
    "index_scale": "18",             # "9" | "18"  — RULED: 18
    # RATIFIED 2026-09-19 (#572): no minimum, no merging. 0 = off.
    "min_flight_size": 0,
    "tie_direction": "even",         # "even" | "up" | "down"
    "modes": {
        # Kerry 2026-09-21: Individual Net cuts on the same fixed ladder
        # as Skins (<12.0 / 12.0+), not an equal-size split.
        "individual_net": "fixed_bands",
        "individual_gross": "fixed_bands",
        "skins": "fixed_bands",
    },
    # Bands are EXCLUSIVE upper bounds, matching the already-ratified Players
    # Cup ladder living in _POINTS_RACES["players_cup"]["flights"]
    # (min_inclusive, max_exclusive): <6.0 / 6.0-12.0 / 12.0-18.0 / 18.0+.
    # Deliberately the same representation rather than a parallel one that
    # merely agrees at one decimal place — an inclusive-11.9 form and an
    # exclusive-12.0 form diverge the moment an index carries more precision,
    # and "12.0 goes UP" is exactly the boundary Kerry ratified.
    "bands": {
        "2": [12.0],                 # ratified: Net low flight is < 12.0
        "3": [6.0, 12.0],            # RATIFIED 2026-09-18 (#571 B3)
        "4": [6.0, 12.0, 18.0],      # the ratified Players Cup ladder
    },
    # Individual Net splits near the middle, but the low flight never
    # reaches this value. Exclusive, so 12.0 itself goes up. equal_size only.
    "low_flight_ceiling": {"individual_net": 12.0},
}


def _tie_safe_cut(ranked: list[dict], target: int, total: int,
                  tie_direction: str) -> int:
    """Move a count-based cut off a tie group without splitting equal indexes.

    Two players on the same index must never land in different flights —
    identical players competing for different pots is the one outcome that
    cannot be defended. So a cut landing inside a run of equal indexes slides
    to one edge of that run.
    """
    if target <= 0 or target >= total:
        return max(0, min(target, total))
    idx = lambda p: p["index"]
    if idx(ranked[target - 1]) != idx(ranked[target]):
        return target                      # clean break already
    val = idx(ranked[target])
    lo = target
    while lo > 0 and idx(ranked[lo - 1]) == val:
        lo -= 1                            # whole group moves UP a flight
    hi = target
    while hi < total and idx(ranked[hi]) == val:
        hi += 1                            # whole group stays DOWN
    if tie_direction == "up":
        return lo
    if tie_direction == "down":
        return hi
    # "even": whichever edge leaves the two sides closer in size; a dead heat
    # goes UP, consistent with 12.0-goes-up.
    return lo if abs(lo - target) <= abs(hi - target) else hi


def flight_plan(players: list[dict], count: int, game: str = "individual_net",
                config: dict | None = None, mode: str | None = None) -> dict:
    """Assign a field to flights by raw handicap index. Rules-as-data.

    players: [{"key", "name", "index"}] — index is the RAW TGF index.
    Returns the flights plus a trace of every decision (boundaries, merges,
    tie slides) so the reasoning is visible instead of implied.
    """
    cfg = config or SEED_FLIGHT_CONFIG
    mode = mode or (cfg.get("modes") or {}).get(game, "fixed_bands")
    notes, merges = [], []
    known = [p for p in players if p.get("index") is not None]
    unknown = [p for p in players if p.get("index") is None]
    if unknown:
        notes.append(
            f"{len(unknown)} player(s) have no handicap index and cannot be "
            f"flighted: {', '.join(sorted(p['name'] for p in unknown))}.")
    ranked = sorted(known, key=lambda p: (p["index"], p["name"] or ""))
    n = len(ranked)
    count = max(1, int(count or 1))
    if n == 0:
        return {"mode": mode, "requested_count": count, "effective_count": 0,
                "flights": [], "unflighted": unknown, "merges": [],
                "notes": notes}

    groups: list[list[dict]] = []
    if mode == "fixed_bands" or count == 1:
        bands = list((cfg.get("bands") or {}).get(str(count)) or [])
        if count == 1:
            groups = [ranked]
        elif not bands:
            notes.append(f"No band ladder configured for {count} flights — "
                         f"fell back to equal-size groups.")
            mode = "equal_size"
        else:
            edges = bands + [float("inf")]
            groups = [[] for _ in edges]
            for p in ranked:
                for i, hi in enumerate(edges):
                    if p["index"] < hi:      # EXCLUSIVE — 12.0 goes UP
                        groups[i].append(p)
                        break
            notes.append("Bands (upper bound per flight, exclusive): "
                         + " / ".join(f"<{b}" for b in bands) + " / rest.")
    if mode == "equal_size" and count > 1:
        base, rem = divmod(n, count)
        cuts, acc = [], 0
        for f in range(count - 1):
            acc += base + (1 if f < rem else 0)
            cut = _tie_safe_cut(ranked, acc, n, cfg.get("tie_direction", "even"))
            if cut != acc:
                notes.append(
                    f"Cut {f + 1} moved {acc} -> {cut} so players sharing "
                    f"index {ranked[min(acc, n - 1)]['index']} stay together.")
            cuts.append(cut)
            acc = cut
        bounds = [0] + cuts + [n]
        groups = [ranked[bounds[i]:bounds[i + 1]] for i in range(count)]
        ceiling = (cfg.get("low_flight_ceiling") or {}).get(game)
        if ceiling is not None and groups and groups[0]:
            over = [p for p in groups[0] if p["index"] >= ceiling]
            if over:
                groups[0] = [p for p in groups[0] if p["index"] < ceiling]
                groups[1] = over + groups[1]
                notes.append(
                    f"Low-flight ceiling {ceiling} (exclusive): moved "
                    f"{len(over)} player(s) up so flight 1 stays below "
                    f"{ceiling}.")

    # Thin flights merge into their nearest neighbour. This is also where
    # "3 flights down to 2 because the handicaps were concentrated" comes
    # from — no separate concentration test needed.
    min_size = int(cfg.get("min_flight_size") or 0)
    if min_size > 1:
        changed = True
        while changed and len([g for g in groups if g]) > 1:
            changed = False
            for i, g in enumerate(groups):
                if g and len(g) < min_size:
                    j = i + 1 if i == 0 else i - 1
                    while 0 <= j < len(groups) and not groups[j]:
                        j = j + 1 if j > i else j - 1
                    if not (0 <= j < len(groups)):
                        break
                    merges.append({"from": i + 1, "into": j + 1,
                                   "players": len(g),
                                   "why": f"fewer than {min_size} players"})
                    groups[j] = sorted(groups[j] + g,
                                       key=lambda p: (p["index"], p["name"] or ""))
                    groups[i] = []
                    changed = True
                    break

    flights, label = [], 0
    for g in groups:
        if not g:
            continue
        label += 1
        flights.append({
            "flight": str(label), "players": len(g),
            "min_index": g[0]["index"], "max_index": g[-1]["index"],
            "members": [{"key": p["key"], "name": p["name"],
                         "index": p["index"]} for p in g]})
    if merges:
        notes.append(f"{len(merges)} flight(s) merged for being under the "
                     f"{min_size}-player minimum — effective count "
                     f"{len(flights)}, not {count}.")
    return {"mode": mode, "requested_count": count,
            "effective_count": len(flights), "flights": flights,
            "unflighted": unknown, "merges": merges, "notes": notes}


def _eligible(cards: list[dict], eligibility: str) -> list[dict]:
    if eligibility == "net_buyers":
        return [c for c in cards if c["buys_net"]]
    if eligibility == "gross_buyers":
        return [c for c in cards if c["buys_gross"]]
    if eligibility == "members_only":
        return [c for c in cards if c["is_member"]]
    return list(cards)


def _rank(rows: list[dict], key, reverse: bool) -> list[dict]:
    """Competition ranking (1,2,2,4) over an already-sorted-by-key list."""
    ordered = sorted(rows, key=key, reverse=reverse)
    place, prev = 0, object()
    for i, r in enumerate(ordered):
        k = key(r)
        if k != prev:
            place, prev = i + 1, k
        r["place"] = place
    return ordered


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------

def game_individual(cards: list[dict], cfg: dict, holes_key: str,
                    basis: str) -> dict:
    """Individual Net / Individual Gross — flighted Stableford."""
    gkey = "individual_net" if basis == "net" else "individual_gross"
    gc = cfg["games"][gkey]
    field = _eligible(cards, gc["eligibility"])
    out = {"game": gkey, "label": gc["label"], "basis": basis,
           "buyers": len(field), "flights": [], "warnings": []}
    min_buyers = (gc.get("min_buyers") or {}).get(holes_key)
    if min_buyers is not None and len(field) < min_buyers:
        out["active"] = False
        out["warnings"].append(
            f"{gc['label']} activates at {min_buyers} buyers "
            f"({holes_key}-hole); {len(field)} bought in.")
        return out
    out["active"] = True
    pts_key = "stableford_net" if basis == "net" else "stableford_gross"
    score_key = "net" if basis == "net" else "gross"
    for label, members in assign_flights(field, gc, holes_key).items():
        rows = [{"key": c["key"], "customer_id": c["customer_id"],
                 "name": c["name"], "playing_handicap": c["playing_handicap"],
                 "points": c[pts_key], "score": c[score_key],
                 "gross": c["gross"], "thru": c["thru"],
                 "complete": c["complete"]} for c in members]
        # Stableford: most points wins; the stroke score breaks ties.
        ranked = _rank(rows, key=lambda r: (-r["points"], r["score"]),
                       reverse=False)
        out["flights"].append({
            "flight": label, "players": len(members), "rows": ranked,
            "provisional": any(not r["complete"] for r in ranked)})
    return out


def game_team_net(cards: list[dict], cfg: dict) -> dict:
    """Team Net — foursomes, one best NET ball per hole vs par."""
    gc = cfg["games"]["team_net"]
    out = {"game": "team_net", "label": gc["label"], "teams": [],
           "warnings": []}
    teams: dict = {}
    for c in cards:
        if c.get("team") is None:
            continue
        teams.setdefault(c["team"], []).append(c)
    if not teams:
        out["warnings"].append(
            "No team assignments — Team Net needs players grouped into "
            "foursomes (the pairings are the teams).")
        return out
    size = gc.get("team_size") or 4
    no_par3 = bool(gc.get("no_pops_on_par3"))
    for team_num in sorted(teams):
        members = teams[team_num]
        if len(members) < size:
            out["warnings"].append(
                f"Team {team_num} has {len(members)} of {size} players — the "
                f"ratified rule fills short teams with a blind draw "
                f"(\"Bl[Name]\"), which this engine does not yet generate.")
        hole_rows, total, thru = [], 0, 0
        hole_numbers = sorted({h["hole"] for c in members for h in c["holes"]})
        for hole in hole_numbers:
            best, best_by = None, None
            par = None
            for c in members:
                h = next((x for x in c["holes"] if x["hole"] == hole), None)
                if not h or h["strokes"] is None:
                    continue
                par = h["par"]
                sr = h["strokes_received"] or 0
                if no_par3 and h["par"] == 3 and sr > 0:
                    sr = 0
                net_vs_par = (h["strokes"] - sr - h["par"]
                              if h["par"] is not None else None)
                if net_vs_par is None:
                    continue
                if best is None or net_vs_par < best:
                    best, best_by = net_vs_par, c["name"]
            if best is None:
                hole_rows.append({"hole": hole, "par": par, "best": None,
                                  "by": None})
                continue
            total += best
            thru += 1
            hole_rows.append({"hole": hole, "par": par, "best": best,
                              "by": best_by})
        out["teams"].append({
            "team": team_num,
            "members": [c["name"] for c in members],
            "vs_par": total, "thru": thru,
            "complete": thru == len(hole_numbers) and bool(hole_numbers),
            "holes": hole_rows})
    _rank(out["teams"], key=lambda t: (t["vs_par"], -t["thru"]), reverse=False)
    out["teams"].sort(key=lambda t: t["place"])
    out["provisional"] = any(not t["complete"] for t in out["teams"])
    return out


def _round_allowance(value: float, mode: str) -> int:
    """Round an allowanced handicap to whole strokes under a NAMED mode.

    The mode is data, never a code branch, because which one Golf Genius
    uses is not yet ratified (CA Queue #7). a9.23 proves only that 0.5 goes
    DOWN — GG calls Luke Youngs' hole 5 an Eagle, and with a stroke it would
    have been an Albatross — which eliminates "half_up" and nothing else.
    """
    import math
    neg = value < 0
    v = abs(value)
    if mode == "half_up":
        out = math.floor(v + 0.5)
    elif mode == "half_even":
        out = round(v)
    elif mode == "floor":
        out = math.floor(v)
    else:                                     # "half_down" (the default)
        out = math.ceil(v - 0.5)
    return int(-out if neg else out)


def select_variant(game_cfg: dict, holes_key: str, buyers: int) -> dict:
    """Pick which VARIANT of a game the side-games matrix selects, and say so.

    This is the layer the a9.23 skins confusion existed for. The buyer count
    is the first-level governing factor for the game decision (Kerry,
    2026-09-16: "the game shifted due to buy ins based off of the side game
    matrix built in. That is the 1st level governing factor for game
    decision") — so the selection is made ONCE, here, and REPORTED on the
    result, rather than each surface inferring it from a basis field.

    Returns the variant dict with a `selection` record attached. A game with
    no variants reports the game itself as its own single variant, so every
    caller can read the same shape.
    """
    variants = game_cfg.get("variants") or []
    if not variants:
        return {
            "name": "default",
            "label": game_cfg.get("label"),
            "basis": game_cfg.get("basis"),
            "handicap": None,
            "selection": {"reason": "game has a single form", "buyers": buyers},
        }
    for v in variants:
        band = (v.get("when_buyers") or {}).get(holes_key)
        if not band:
            continue
        lo, hi = band[0], band[1]
        if buyers >= lo and (hi is None or buyers <= hi):
            hi_txt = hi if hi is not None else "+"
            out = dict(v)
            out["selection"] = {
                "buyers": buyers,
                "holes": holes_key,
                "band": [lo, hi],
                "reason": (f"{buyers} buyers on a {holes_key}-hole event falls "
                           f"in the {lo}-{hi_txt} band, so the matrix runs "
                           f"{v.get('gg_name') or v.get('label')}"),
            }
            return out
    out = dict(variants[-1])
    out["selection"] = {
        "buyers": buyers, "holes": holes_key, "band": None,
        "reason": (f"{buyers} buyers matched NO configured band on a "
                   f"{holes_key}-hole event — fell back to "
                   f"{out.get('label')}. This is a gap in the matrix, "
                   f"not a rule."),
        "unmatched": True,
    }
    return out


def game_handicaps(cards: list[dict], handicap_cfg: dict | None,
                   si_by_hole: dict) -> dict:
    """The GAME's own stroke allocation — not the card's.

    Pops are a property of the GAME (2026-09-16). A card carries whatever
    allocation the event's headline net game used; a different game on the
    same card has a different allowance, and may have none at all. So each
    game that needs strokes derives them here, under its own dials.

    THE ORDER IS GOLF GENIUS'S, AND IT IS LOAD-BEARING (Kerry's GG handicap
    settings + the Melchor worked example, 2026-09-16):

      1. start from the UNROUNDED course handicap
                     index x (slope/113) + (rating - par)
      2. allowance:  x allowance_pct / 100
      3. round ONCE, here, and only here
      4. off lowest: subtract the lowest ROUNDED handicap in the group
      5. allocate:   by stroke index under the `stroke_allocation` dial

    Step 1 is the one this function got wrong until 2026-09-16, and it is
    why our a9.23 board would not reproduce GG's. We applied the allowance
    to an already-ROUNDED playing handicap, which double-rounds. GG states
    the rule on its own settings page: "The World Handicap System requires
    full precision to be maintained in intermediary calculations. Rounding
    is performed only once and as the last step."

    Worked, from GG's own detail line for Eduardo Melchor on a9.23:
        index 5.6, Blue (slope 139 / rating 36.0 / par 36), front nine
        CH  = 5.6 x 139/113 = 6.888...          <- unrounded, carried
        x50% = 3.444...                          <- allowance on the float
        round once -> 3                          <- GG's published column
    Double-rounding instead gives round(6.888)=7, 7x50%=3.5, which is a
    different number and pays a different skin.

    When a card cannot supply an unrounded course handicap this falls back
    to the rounded playing handicap and REPORTS `precision_loss: True` per
    player rather than pretending the two are the same.

    Returns {"by_key": {key: {"raw", "course_handicap", "allowanced",
             "strokes", "by_hole", "precision_loss"}}, "dials": {...}}
    so a surface can print the working.
    """
    out = {"by_key": {}, "dials": dict(handicap_cfg or {}) or None}
    if not handicap_cfg:
        for c in cards:
            out["by_key"][c["key"]] = {
                "raw": c.get("playing_handicap"), "course_handicap": None,
                "allowanced": 0, "strokes": 0, "precision_loss": False,
                "by_hole": {h: 0 for h in si_by_hole}}
        return out

    pct = handicap_cfg.get("allowance_pct", 100)
    mode = handicap_cfg.get("rounding", "half_up")
    alloc_mode = handicap_cfg.get("stroke_allocation", "full_card")

    # Step 1-3: allowance on the unrounded course handicap, rounded ONCE.
    rounded, lossy = {}, {}
    for c in cards:
        ch = c.get("course_handicap")
        lossy[c["key"]] = ch is None
        if ch is None:
            ch = c.get("playing_handicap")
        base = 0.0 if ch is None else float(ch)
        rounded[c["key"]] = (base, _round_allowance(base * pct / 100.0, mode))

    # Step 4: off lowest, applied to the ROUNDED handicaps, as GG prints it
    # ("After rounding, the PH is 3. The lowest handicap in the group is
    # 0.0. After applying 'off lowest', the handicap becomes 3.0.").
    # …and never below zero: a plus player in the field means nobody is
    # RAISED (Kerry 2026-09-22 — subtracting a negative lowest handed the
    # Brackenridge field two strokes above their playing handicaps).
    low = max(min((v[1] for v in rounded.values()), default=0), 0) \
        if handicap_cfg.get("off_lowest") else 0

    for c in cards:
        base, strokes = rounded[c["key"]]
        strokes -= low
        out["by_key"][c["key"]] = {
            "raw": c.get("playing_handicap"),
            "course_handicap": (None if lossy[c["key"]]
                                else round(base, 3)),
            "allowanced": round(base * pct / 100.0, 3),
            "strokes": strokes,
            "precision_loss": lossy[c["key"]],
            "by_hole": (allocate_strokes(strokes, si_by_hole, mode=alloc_mode)
                        if si_by_hole else {}),
        }
    return out


def game_skins(cards: list[dict], cfg: dict, holes_key: str,
               strokes_override: dict | None = None) -> dict:
    """Skins — computed as the VARIANT the side-games matrix actually selects.

    The buyer count decides which game is played, not merely how big the pot
    is. Above the threshold this is GROSS skins (outright low gross on a hole
    within flight); below it the matrix runs half-Net Skins, a NET game with
    its own allowance. Both are computed here off the same code path, because
    the difference between them is DATA.

    This is the a9.23 Avery Ranch lesson. Four players bought the gross
    bundle on a nine, GG ran "SKINS 1/2 Net $", and this function used to
    compute gross skins regardless and report a warning nobody acted on — so
    we compared a net result against a gross computation and concluded Golf
    Genius was contradicting itself. It was not.

    `strokes_override` ({player_key: {hole: strokes_received}}) forces a known
    allocation, which is how the parity harness pins GG's own dots and
    isolates the SCORING diff from the ALLOCATION diff.
    """
    gc = cfg["games"]["skins"]
    field = _eligible(cards, gc["eligibility"])
    variant = select_variant(gc, holes_key, len(field))
    hcfg = variant.get("handicap")
    si_by_hole = {}
    for c in field:
        for h in c["holes"]:
            if h.get("stroke_index") is not None:
                si_by_hole[h["hole"]] = h["stroke_index"]

    hcaps = game_handicaps(field, hcfg, si_by_hole)
    if strokes_override:
        for key, by_hole in strokes_override.items():
            if key in hcaps["by_key"]:
                hcaps["by_key"][key]["by_hole"] = dict(by_hole)
                hcaps["by_key"][key]["strokes"] = sum(by_hole.values())
                hcaps["by_key"][key]["source"] = "override"

    out = {
        "game": "skins",
        "label": variant.get("label") or gc["label"],
        "buyers": len(field),
        "active": True,
        "basis": variant.get("basis"),
        "pops_per_hole": gc.get("pops_per_hole", True),
        "variant": variant.get("name"),
        "gg_name": variant.get("gg_name"),
        "selection": variant.get("selection"),
        "handicaps": hcaps,
        "flights": [],
        "warnings": [],
    }
    if variant.get("selection", {}).get("unmatched"):
        out["warnings"].append(out["selection"]["reason"])
    # Money computed off an unratified dial is reported as such rather than
    # quietly paid. CA Queue #7.
    if hcfg and not hcfg.get("rounding_ratified", True):
        out["handicap_ratified"] = False
        out["warnings"].append(
            f"{out['label']} applies a {hcfg.get('allowance_pct')}% allowance"
            f"{' off the lowest' if hcfg.get('off_lowest') else ''}, but HOW "
            f"the half stroke rounds is NOT ratified (CA Queue #7) — this "
            f"board is provisional, using '{hcfg.get('rounding')}'.")
    # A handicap we could only take at ROUNDED precision is money computed on
    # a number GG would not have used, so it is reported and never silent.
    lossy = sorted(k for k, v in hcaps.get("by_key", {}).items()
                   if v.get("precision_loss"))
    if hcfg and lossy:
        out["warnings"].append(
            f"{out['label']} applied its {hcfg.get('allowance_pct')}% "
            f"allowance to a ROUNDED handicap for {len(lossy)} player(s) "
            f"({', '.join(lossy[:4])}{'...' if len(lossy) > 4 else ''}) "
            f"because no unrounded course handicap was available. GG rounds "
            f"ONCE, at the end — these strokes may differ from GG's.")

    for label, members in assign_flights(field, gc, holes_key).items():
        hole_numbers = sorted({h["hole"] for c in members for h in c["holes"]})
        skins, carried = [], 0
        for hole in hole_numbers:
            best, winners, par = None, [], None
            played = 0
            for c in members:
                h = next((x for x in c["holes"] if x["hole"] == hole), None)
                if not h or h["strokes"] is None:
                    continue
                played += 1
                par = h["par"]
                pops = (hcaps["by_key"].get(c["key"], {})
                        .get("by_hole", {}).get(hole, 0) or 0)
                value = h["strokes"] - pops
                if best is None or value < best:
                    best, winners = value, [c]
                elif value == best:
                    winners.append(c)
            if best is None:
                continue
            settled = played == len(members)
            if len(winners) == 1:
                skins.append({"hole": hole, "par": par,
                              "gross": next(x["strokes"] for x in
                                            winners[0]["holes"]
                                            if x["hole"] == hole),
                              "score": best,
                              "pops": (hcaps["by_key"]
                                       .get(winners[0]["key"], {})
                                       .get("by_hole", {}).get(hole, 0) or 0),
                              "vs_par": (best - par) if par is not None
                              else None,
                              "winner": winners[0]["name"],
                              "key": winners[0]["key"],
                              "customer_id": winners[0]["customer_id"],
                              "settled": settled})
            else:
                carried += 1
        tally: dict = {}
        for sk in skins:
            tally[sk["winner"]] = tally.get(sk["winner"], 0) + 1
        out["flights"].append({
            "flight": label, "players": len(members), "skins": skins,
            "tied_holes": carried,
            "tally": [{"name": k, "skins": v} for k, v in
                      sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))],
            "provisional": any(not sk["settled"] for sk in skins)})
    return out


def game_mvp(cards: list[dict], cfg: dict, holes_count: int) -> dict:
    """City MVP — highest net Stableford among NET buyers.

    Mirrors `determine_tgf_mvp`'s ruleset exactly, INCLUDING the
    incomplete-card guard (Kerry's s9.20 catch): a card short of a full
    round leaves the result provisional while its player could still catch
    the leader.
    """
    gc = cfg["games"]["mvp"]
    field = _eligible(cards, gc["eligibility"])
    out = {"game": "mvp", "label": gc["label"], "buyers": len(field),
           "winners": [], "field": [], "warnings": []}
    entrants = [c for c in field if c["thru"] > 0]
    if not field:
        out["status"] = "no_net_buyers"
        return out
    if not entrants:
        out["status"] = "awaiting_results"
        return out
    entrants.sort(key=lambda c: (-c["stableford_net"], c["net"], c["gross"]))
    out["field"] = [{"key": c["key"], "customer_id": c["customer_id"],
                     "name": c["name"], "points": c["stableford_net"],
                     "net": c["net"], "gross": c["gross"], "thru": c["thru"]}
                    for c in entrants[:10]]
    top = entrants[0]
    max_pts = gc.get("max_points_per_hole") or 9
    unsettled = [
        {"name": c["name"], "thru": c["thru"], "points_so_far": c["stableford_net"]}
        for c in entrants
        if (holes_count - c["thru"]) > 0
        and top["stableford_net"] - c["stableford_net"]
        <= (holes_count - c["thru"]) * max_pts]
    if unsettled:
        out["status"] = "incomplete_cards"
        out["incomplete"] = unsettled
        out["note"] = ("cards missing holes could still change the winner — "
                       "the MVP is not decided yet")
        return out
    winners = [c for c in entrants
               if c["stableford_net"] == top["stableford_net"]
               and c["net"] == top["net"] and c["gross"] == top["gross"]]
    out["status"] = "determined"
    out["split"] = len(winners) > 1
    out["winners"] = [{"key": c["key"], "customer_id": c["customer_id"],
                       "name": c["name"], "points": c["stableford_net"],
                       "net": c["net"], "gross": c["gross"]} for c in winners]
    return out


def ctp_slots(state: dict, cfg: dict) -> dict:
    """Which holes carry a CTP, per the ratified selection rules.

    Max 2 per nine. More par-3s than slots -> the SHORTEST par-3s are
    selected. Fewer par-3s than slots -> the leftover dollar(s) become a
    Longest Putt contest on the last hole.
    """
    gc = cfg["games"]["ctp"]
    holes = sorted(state.get("holes") or [], key=lambda h: h["hole"])
    per_nine = gc.get("slots_per_nine") or 2
    slots, spillover = [], []
    for start in range(0, len(holes), 9):
        nine = holes[start:start + 9]
        if not nine:
            continue
        par3s = [h for h in nine if h.get("par") == 3]
        par3s.sort(key=lambda h: (h.get("yardage") if h.get("yardage")
                                  is not None else 10 ** 6, h["hole"]))
        chosen = par3s[:per_nine]
        slots.extend({"hole": h["hole"], "par": h.get("par"),
                      "yardage": h.get("yardage"), "kind": "ctp"}
                     for h in sorted(chosen, key=lambda h: h["hole"]))
        for _ in range(per_nine - len(chosen)):
            spillover.append({"hole": nine[-1]["hole"], "kind": "longest_putt"})
    return {"game": "ctp", "label": gc["label"], "slots": slots,
            "spillover": spillover,
            "note": "CTP and Longest Putt are measured on course — winners "
                    "are recorded by hand, never derived from scores."}


def game_hio(cards: list[dict], cfg: dict) -> dict:
    """Hole-in-One — a RAW ace (gross strokes == 1). Members-only to win."""
    gc = cfg["games"]["hio"]
    aces = []
    for c in cards:
        for h in c["holes"]:
            if h["strokes"] == 1:
                aces.append({"key": c["key"], "customer_id": c["customer_id"],
                             "name": c["name"], "hole": h["hole"],
                             "par": h["par"], "eligible": c["is_member"],
                             "note": None if c["is_member"] else
                             "guests/first-timers pay in but cannot win"})
    return {"game": "hio", "label": gc["label"], "aces": aces}


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------

def compute_leaderboard(state: dict, formulas: dict,
                        config: dict | None = None,
                        derive_hole=None) -> dict:
    """Every game, computed from raw gross hole scores. The Stage-1 surface."""
    cfg = config or SEED_LIVE_SCORING_CONFIG
    cards = build_cards(state, formulas, derive_hole=derive_hole)
    holes_count = len(state.get("holes") or [])
    holes_key = "18" if holes_count > 9 else "9"
    overall = _rank(
        [{"key": c["key"], "customer_id": c["customer_id"], "name": c["name"],
          "playing_handicap": c["playing_handicap"],
          "points": c["stableford_net"], "gross_points": c["stableford_gross"],
          "gross": c["gross"], "net": c["net"], "thru": c["thru"],
          "complete": c["complete"], "flight": c["flight"], "team": c["team"],
          "allocation_source": c["allocation_source"]} for c in cards],
        key=lambda r: (-r["points"], r["net"]), reverse=False)
    return {
        "holes": holes_count,
        "holes_key": holes_key,
        "players": len(cards),
        "cards": cards,
        "overall": overall,
        "games": {
            "individual_net": game_individual(cards, cfg, holes_key, "net"),
            "individual_gross": game_individual(cards, cfg, holes_key, "gross"),
            "team_net": game_team_net(cards, cfg),
            "skins": game_skins(cards, cfg, holes_key),
            "mvp": game_mvp(cards, cfg, holes_count),
            "ctp": ctp_slots(state, cfg),
            "hio": game_hio(cards, cfg),
        },
    }


# ---------------------------------------------------------------------------
# Parity diff — the Stage-1 confidence gate
# ---------------------------------------------------------------------------

def parity_diff(cards: list[dict], gg_rows: dict) -> dict:
    """Diff our engine's per-player numbers against GG's own.

    `gg_rows` is {player_key: {"gross", "net", "playing_handicap",
    "stableford_net", "stableford_gross", "strokes_received": {hole: n}}} —
    whatever GG told us, straight from the imported scoring round. Any field
    that is None on the GG side is SKIPPED rather than counted as a match, so
    a thin GG row can never manufacture a clean parity report.
    """
    fields = ["gross", "net", "playing_handicap", "stableford_net",
              "stableford_gross"]
    rows, checked, matched = [], 0, 0
    for c in cards:
        gg = gg_rows.get(c["key"])
        if not gg:
            rows.append({"key": c["key"], "name": c["name"],
                         "status": "no_gg_row", "deltas": []})
            continue
        deltas = []
        for f in fields:
            ours, theirs = c.get(f), gg.get(f)
            if theirs is None or ours is None:
                continue
            checked += 1
            if abs(float(ours) - float(theirs)) < 1e-9:
                matched += 1
            else:
                deltas.append({"field": f, "ours": ours, "gg": theirs,
                               "delta": round(float(ours) - float(theirs), 4)})
        # Stroke allocation is its own parity question: when we DERIVED the
        # dots and GG supplied its own, disagreement means our WHS allocation
        # differs from GG's — the exact thing Stage 2 depends on.
        gg_sr = gg.get("strokes_received") or {}
        if gg_sr and c["allocation_source"] == "derived":
            for h in c["holes"]:
                theirs = gg_sr.get(h["hole"])
                if theirs is None:
                    continue
                checked += 1
                if (h["strokes_received"] or 0) == theirs:
                    matched += 1
                else:
                    deltas.append({"field": f"dots@{h['hole']}",
                                   "ours": h["strokes_received"],
                                   "gg": theirs,
                                   "delta": (h["strokes_received"] or 0) - theirs})
        rows.append({"key": c["key"], "name": c["name"],
                     "status": "match" if not deltas else "mismatch",
                     "deltas": deltas})
    return {"checked": checked, "matched": matched,
            "mismatched": checked - matched,
            "players_clean": sum(1 for r in rows if r["status"] == "match"),
            "players_mismatched": sum(1 for r in rows
                                      if r["status"] == "mismatch"),
            "players_without_gg": sum(1 for r in rows
                                      if r["status"] == "no_gg_row"),
            "parity": (matched == checked and checked > 0),
            "rows": rows}


# ---------------------------------------------------------------------------
# Simulation — drives the live surface without a real round
# ---------------------------------------------------------------------------

def simulate_strokes(par: int, playing_handicap: float | None,
                     rng: random.Random) -> int:
    """A plausible gross score: par, nudged by skill and a fat tail.

    Not a golf model — just enough spread that a simulated leaderboard
    moves the way a real one does (birdies rare, blow-ups occasional).
    """
    ph = 8.0 if playing_handicap is None else float(playing_handicap)
    expected = par + max(-0.4, ph / 9.0)
    roll = rng.random()
    if roll < 0.04:
        delta = -1                      # birdie-ish
    elif roll < 0.09:
        delta = 2                       # blow-up
    else:
        delta = round(rng.gauss(0, 0.9))
    return max(1, int(round(expected + delta)))
