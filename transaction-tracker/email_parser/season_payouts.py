"""Season-contest PAYOUT engine — pure functions, no DB/Flask.

Source of truth: TGF_Season_Contest_Payouts_v1_0.md (Kerry-ratified
2026-07-06; OneDrive 7_Web & App Development/), summarized in
docs/claude/game-engine.md ("Season-contest payout economics", mailbox
id 18). Every payout is computable from the entrant count N — these are
RULES, not lookup tables, per the ratified game-configuration standard.

Money model: every entry contributes $40 to its pot ($90 NET bundle =
$40 City Net + $40 Fellowship Cup + $10 TGF; $50 Players Cup / Match
Play = $40 + $10). Universal rules: exact division (cents fall where
they fall — largest-remainder keeps sums exact), City pays BROAD, Cup
pays TOP-HEAVY, places graduate by field size, 1st never decreases as
N grows.

Match Play ladders live in match_play.py (the xlsx-parity engine);
this module covers the three points-race families.
"""

from .match_play import allocate_cents

ENTRY_TO_POT_CENTS = 4000  # $40 of every entry lands in the pot

SEED_SEASON_PAYOUT_CONFIG: dict = {
    # %paid decays linearly between the two anchors; extrapolate outside.
    # places = ROUND(N x %paid(N)), floored at min_places.
    "city_net": {
        "places_curve": {"n0": 10, "pct0": 30.0, "n1": 60, "pct1": 20.0,
                         "min_places": 2},
        # % of pot by place; 8+ places to be defined at Kerry's direction
        # when a field demands it (spec section 8.5) — capped at 7 here.
        "ladders": {
            2: [60, 40],
            3: [45, 30, 25],
            4: [40, 30, 20, 10],
            5: [35, 25, 18, 12, 10],
            6: [32, 23, 16, 12, 9, 8],
            7: [28, 20, 16, 12, 9, 8, 7],
        },
    },
    "fellowship_cup": {
        "places_curve": {"n0": 20, "pct0": 15.0, "n1": 100, "pct1": 10.0,
                         "min_places": 3},
        # 1st = 45% of pot FLAT until the winner's check hits $1,008 at
        # N=56 (pot $2,240); past that, 1st = $1,008 + 20% of every pot
        # dollar above $2,240 (the ratified winner-growth engine — $8 of
        # each new $40 buy-in).
        "first_pct": 45.0,
        "first_cap_cents": 100800,
        "cap_pot_cents": 224000,
        "marginal_pct": 20.0,
        # Remainder ladders (% of TOTAL pot; sums with 45 to 100).
        # Spec section 8.2 flags these as proposed defaults.
        "remainder_ladders": {
            3: [32.0, 23.0],
            4: [25.0, 17.5, 12.5],
            5: [22.0, 14.0, 11.0, 8.0],
        },
    },
    "players_cup": {
        "champion_pct": 10.0,   # off the top to the overall Champion
        "n_flights": 4,         # fixed handicap bands, defined per-race
        "flight_split": [67.0, 33.0],
    },
}


def _places_for_n(curve: dict, n: int, max_places: int) -> int:
    """places = ROUND(N x %paid(N)) with the linear %paid decay
    (Excel-style half-up round, matching the spec's worked matrices)."""
    if n <= 0:
        return 0
    pct = (curve["pct0"]
           + (n - curve["n0"])
           * (curve["pct1"] - curve["pct0"]) / (curve["n1"] - curve["n0"]))
    places = int(n * pct / 100.0 + 0.5)
    places = max(curve["min_places"], places)
    return min(places, max_places, n)


def city_net_payouts(n: int, config: dict | None = None) -> dict | None:
    """City NET race ladder for a chapter field of N buy-ins."""
    cfg = (config or SEED_SEASON_PAYOUT_CONFIG)["city_net"]
    if n <= 0:
        return None
    pot = ENTRY_TO_POT_CENTS * n
    places = _places_for_n(cfg["places_curve"], n, max(cfg["ladders"]))
    if places < min(cfg["ladders"]):
        places = min(cfg["ladders"])
    ladder = cfg["ladders"][places]
    return {
        "kind": "ladder",
        "n_basis": n,
        "pot_cents": pot,
        "amounts_cents": allocate_cents(pot, ladder),
    }


def fellowship_cup_payouts(n: int, config: dict | None = None) -> dict | None:
    """THE FELLOWSHIP CUP ladder for N total NET-bundle buy-ins."""
    cfg = (config or SEED_SEASON_PAYOUT_CONFIG)["fellowship_cup"]
    if n <= 0:
        return None
    pot = ENTRY_TO_POT_CENTS * n
    places = _places_for_n(cfg["places_curve"], n,
                           max(cfg["remainder_ladders"]) + 1)
    places = max(places, cfg["places_curve"]["min_places"])
    if pot <= cfg["cap_pot_cents"]:
        first = round(pot * cfg["first_pct"] / 100.0)
    else:
        # winner-growth engine: dollars keep rising with every buy-in
        first = cfg["first_cap_cents"] + round(
            (pot - cfg["cap_pot_cents"]) * cfg["marginal_pct"] / 100.0)
    # clamp to the defined remainder ladders (3-5 places; larger fields
    # pending Kerry's ladder extension, spec section 8)
    rem_key = min(max(places, min(cfg["remainder_ladders"])),
                  max(cfg["remainder_ladders"]))
    rem_ladder = cfg["remainder_ladders"][rem_key]
    rest = allocate_cents(pot - first, [p * 100.0 / sum(rem_ladder)
                                        for p in rem_ladder])
    return {
        "kind": "ladder",
        "n_basis": n,
        "pot_cents": pot,
        "amounts_cents": [first] + rest,
    }


def players_cup_payouts(n: int, config: dict | None = None) -> dict | None:
    """THE PLAYERS CUP: Champion bonus off the top, the rest split
    equally across the 4 fixed flights, 67/33 within each flight."""
    cfg = (config or SEED_SEASON_PAYOUT_CONFIG)["players_cup"]
    if n <= 0:
        return None
    pot = ENTRY_TO_POT_CENTS * n
    champion = round(pot * cfg["champion_pct"] / 100.0)
    flight_pot = (pot - champion) // cfg["n_flights"]
    f1, f2 = allocate_cents(flight_pot, cfg["flight_split"])
    return {
        "kind": "flights",
        "n_basis": n,
        "pot_cents": pot,
        "champion_cents": champion,
        "flight_pot_cents": flight_pot,
        "flight_first_cents": f1,
        "flight_second_cents": f2,
    }
