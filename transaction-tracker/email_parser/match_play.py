"""City Match Play engine — pure functions over a versioned config.

This module is the scoring/structure/payout engine for the City Match Play
season contest (CONTESTS page). It holds NO database access and NO Flask —
everything here is a pure function of (config, inputs) so it is unit-testable
and lifts to the TGF Platform (Supabase) unchanged. See
docs/claude/game-engine.md → "NEXT BUILD DIRECTIVE".

The config shape is the first concrete instance of the Game Creator
season-contest config (season_contest_templates / season_contest_versions in
database.py). The seed below reproduces the ratified 29-column
"Prizes-Match Play Matrix.xlsx" (OneDrive/01_STANDARDS/Prizes/, July 6 final)
exactly — see test_match_play.py for the column-by-column proof. It is SEED
data: the live source of truth is the versioned config an admin edits in the
CONTESTS UI, never this constant.

All money is computed in integer cents ("exact-division cents" rule): a
payout ladder must always sum to the adjusted pot to the cent, with no lost
or invented pennies. `allocate_cents` implements largest-remainder
apportionment; hand-tuned whole-dollar columns that a percentage can't
reproduce (N=4, N=5) live in `amount_overrides`.
"""

from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# Seed config — the ratified matrix as RULES (admin-editable via versions)
# ---------------------------------------------------------------------------

def _seed_structure() -> dict:
    """Per-N structure table from the matrix (N = 4..32)."""
    def row(n: int) -> dict:
        if n <= 5:
            pools = 1
        elif n <= 10:
            pools = 2
        elif n <= 15:
            pools = 3
        elif n <= 19:
            pools = 4
        elif n <= 23:
            pools = 5
        elif n <= 27:
            pools = 6
        elif n <= 31:
            pools = 7
        else:
            pools = 8
        if n <= 5:
            knockout = 2
        elif n <= 10:
            knockout = 4
        elif n <= 19:
            knockout = 8
        elif n <= 23:
            knockout = 12
        else:
            knockout = 16
        if 11 <= n <= 15 or 20 <= n <= 23 or 28 <= n <= 31:
            wildcards = 2
        elif 24 <= n <= 27:
            wildcards = 4
        else:
            wildcards = 0
        return {"pools": pools, "knockout": knockout, "wildcards": wildcards}

    return {str(n): row(n) for n in range(4, 33)}


SEED_MATCH_PLAY_CONFIG: dict = {
    "kind": "match_play",
    "entry_fee": 40.0,
    "n_min": 4,
    "n_max": 32,
    "pool_size_min": 3,
    "pool_size_max": 5,
    # Target pool matches per player. Pools of 5 can't land everyone on
    # exactly 3 (5×3/2 isn't whole) — the matrix notes "some may have to
    # have 4". The UI shows all pairings; the manager records those played.
    "matches_per_player": 3,
    "advance_per_pool": 2,
    "structure": _seed_structure(),
    # $/pool winner, taken off the pot before the ladder. N=4 is the
    # single-pool exception ($25).
    "pool_winner_bonus": {"default": 20.0, "overrides": {"4": 25.0}},
    # bracket_size → number of top seeds that skip round 1. Only the
    # 12-player bracket (N=20-23) has byes in the ratified matrix; other
    # sizes are full power-of-2 fields.
    "byes": {"12": 4},
    # Ladder bands: percentages of the ADJUSTED pot (pot − pool bonuses).
    # n_max null = open-ended.
    "ladder": [
        {"n_min": 4, "n_max": 4, "pcts": [71.5, 28.5]},
        {"n_min": 5, "n_max": 5, "pcts": [66.67, 33.33]},
        {"n_min": 6, "n_max": 6, "pcts": [62.5, 22.5, 15.0]},
        {"n_min": 7, "n_max": 7, "pcts": [55.0, 25.0, 20.0]},
        {"n_min": 8, "n_max": 10, "pcts": [50.0, 30.0, 20.0]},
        {"n_min": 11, "n_max": None, "pcts": [50.0, 25.0, 15.0, 10.0]},
    ],
    # Hand-tuned whole-dollar columns where the band percentage doesn't
    # divide the adjusted pot evenly (kept faithful to the xlsx).
    "amount_overrides": {"4": [97.0, 38.0], "5": [120.0, 60.0]},
    # Tied finishers (e.g. both semifinal losers) split the combined money
    # of the places they jointly occupy. Default pending Kerry confirm.
    "tie_policy": "split_combined_places",
    # Knockout seeds = most Stableford points accumulated across the pool
    # matches (ratified).
    "seeding": "stableford_pool_matches",
    "notes": "Seeded from Prizes-Match Play Matrix.xlsx (July 6 final).",
}


# ---------------------------------------------------------------------------
# Money — exact-division cents
# ---------------------------------------------------------------------------

def allocate_cents(total_cents: int, pcts: list[float]) -> list[int]:
    """Apportion total_cents by percentages, largest-remainder method.

    Guarantees sum(result) == total_cents. Ties in remainder go to the
    earlier (higher) place so the split is deterministic.
    """
    raw = [total_cents * p / 100.0 for p in pcts]
    floors = [int(math.floor(r)) for r in raw]
    short = total_cents - sum(floors)
    # Rank places by fractional remainder, biggest first; stable on index.
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - floors[i]), i))
    for i in order[:short]:
        floors[i] += 1
    return floors


def split_cents(total_cents: int, ways: int) -> list[int]:
    """Split evenly across `ways` recipients, spare cents to earlier ones."""
    base, spare = divmod(total_cents, ways)
    return [base + (1 if i < spare else 0) for i in range(ways)]


# ---------------------------------------------------------------------------
# Structure lookup
# ---------------------------------------------------------------------------

def pool_sizes(n: int, pools: int) -> list[int]:
    """Balanced pool sizes (differ by at most 1), biggest pools first."""
    base, rem = divmod(n, pools)
    return [base + 1] * rem + [base] * (pools - rem)


def ladder_pcts_for_n(config: dict, n: int) -> list[float]:
    for band in config.get("ladder", []):
        lo = band.get("n_min") or 0
        hi = band.get("n_max")
        if n >= lo and (hi is None or n <= hi):
            return list(band["pcts"])
    return []


def structure_for_n(config: dict, n: int) -> dict:
    """Everything the matrix says about a field of N: structure + money.

    Returns dollars as floats (whole cents) plus the raw cents for exact
    arithmetic downstream.
    """
    row = config.get("structure", {}).get(str(n))
    if not row:
        raise ValueError(
            f"N={n} outside configured range "
            f"{config.get('n_min')}–{config.get('n_max')}"
        )
    entry_fee = float(config.get("entry_fee", 40.0))
    pot_cents = round(entry_fee * 100) * n

    bonus_cfg = config.get("pool_winner_bonus", {})
    bonus_each = float(
        bonus_cfg.get("overrides", {}).get(str(n), bonus_cfg.get("default", 0.0))
    )
    bonus_each_cents = round(bonus_each * 100)
    pools = int(row["pools"])
    bonus_total_cents = bonus_each_cents * pools
    adjusted_cents = pot_cents - bonus_total_cents

    pcts = ladder_pcts_for_n(config, n)
    override = config.get("amount_overrides", {}).get(str(n))
    if override:
        amounts_cents = [round(float(a) * 100) for a in override]
    else:
        amounts_cents = allocate_cents(adjusted_cents, pcts)

    knockout = int(row["knockout"])
    byes = int(config.get("byes", {}).get(str(knockout), 0))

    return {
        "n": n,
        "pools": pools,
        "pool_sizes": pool_sizes(n, pools),
        "matches_per_player": int(config.get("matches_per_player", 3)),
        "advance_per_pool": int(config.get("advance_per_pool", 2)),
        "knockout": knockout,
        "wildcards": int(row["wildcards"]),
        "byes": byes,
        "entry_fee": entry_fee,
        "pot": pot_cents / 100.0,
        "pool_winner_bonus_each": bonus_each_cents / 100.0,
        "pool_winner_bonus_total": bonus_total_cents / 100.0,
        "adjusted_pot": adjusted_cents / 100.0,
        "ladder_pcts": pcts,
        "ladder_amounts": [c / 100.0 for c in amounts_cents],
        "pot_cents": pot_cents,
        "adjusted_pot_cents": adjusted_cents,
        "ladder_amounts_cents": amounts_cents,
        "bonus_each_cents": bonus_each_cents,
    }


# ---------------------------------------------------------------------------
# Knockout seeding — standard single-elimination placement with byes
# ---------------------------------------------------------------------------

def bracket_template_size(k: int) -> int:
    """Next power of two ≥ k (a 12-field plays inside a 16 template)."""
    size = 2
    while size < k:
        size *= 2
    return size


def seed_order(size: int) -> list[int]:
    """Classic bracket seed placement for a power-of-2 draw.

    Returns seeds in slot order, e.g. size=8 → [1,8,4,5,2,7,3,6]:
    match 0 is 1v8, match 1 is 4v5, … so seeds 1 and 2 can only meet in
    the final.
    """
    order = [1]
    while len(order) < size:
        doubled = len(order) * 2
        nxt = []
        for s in order:
            nxt.append(s)
            nxt.append(doubled + 1 - s)
        order = nxt
    return order


def round_names(template_size: int) -> list[str]:
    """Round keys from first round to final for a template size (2..16)."""
    names = {16: ["r16", "qf", "sf", "final"],
             8: ["qf", "sf", "final"],
             4: ["sf", "final"],
             2: ["final"]}
    if template_size not in names:
        raise ValueError(f"Unsupported bracket size {template_size}")
    return names[template_size]


def seed_bracket(entrants: list[dict], bracket_size: int) -> dict:
    """Place seeded entrants into a bracket, byes resolved automatically.

    entrants: seed-ordered list (index 0 = #1 seed) of dicts with at least
    player_name; extra keys (customer_id, stableford, wildcard) pass through.
    bracket_size: the configured knockout size (may be non-power-of-2, e.g.
    12 → byes inside a 16 template for every seed whose round-1 opponent
    seed number exceeds bracket_size).

    Returns {"template_size", "rounds", "first_round", "bye_placements"}:
    - first_round: [{"slot", "player"}] rows for the opening round (both
      slots of every real match; bye matches are omitted entirely).
    - bye_placements: [{"slot", "player"}] rows for the SECOND round —
      where bye seeds land directly (slot = their round-1 match index).
    """
    k = min(bracket_size, len(entrants))
    template = bracket_template_size(bracket_size)
    order = seed_order(template)
    rounds = round_names(template)

    slots: list[dict | None] = []
    for s in order:
        slots.append(entrants[s - 1] if s <= k else None)

    first_round, bye_placements = [], []
    for match_idx in range(template // 2):
        a = slots[match_idx * 2]
        b = slots[match_idx * 2 + 1]
        if a is not None and b is not None:
            first_round.append({"slot": match_idx * 2, "player": a})
            first_round.append({"slot": match_idx * 2 + 1, "player": b})
        elif a is not None or b is not None:
            # Bye: the present seed advances straight to the next round.
            bye_placements.append(
                {"slot": match_idx, "player": a if a is not None else b}
            )
        # both None: dead match (bracket_size < template/2 pairs) — skip.
    return {
        "template_size": template,
        "rounds": rounds,
        "first_round": first_round,
        "bye_placements": bye_placements,
    }


# ---------------------------------------------------------------------------
# Final placement → payouts (ties split combined places)
# ---------------------------------------------------------------------------

def ladder_payout_rows(structure: dict, placements: list[list[str]],
                       tie_policy: str = "split_combined_places") -> list[dict]:
    """Turn ordered placement groups into payout rows.

    placements: list of place-groups from 1st down, each a list of player
    names. A group with more than one name is a tie occupying the next
    len(group) places (e.g. [["Ann"], ["Bo"], ["Cy", "Di"]] = champion,
    runner-up, and two semifinal losers sharing places 3-4).

    Returns one row per player: place_label, player_name, amount (dollars).
    The sum of all amounts always equals the ladder total exactly.
    """
    amounts = list(structure["ladder_amounts_cents"])
    rows: list[dict] = []
    place = 1
    for group in placements:
        span = len(group)
        pool = sum(amounts[place - 1: place - 1 + span]) if place <= len(amounts) else 0
        if tie_policy == "split_combined_places" and span > 1:
            shares = split_cents(pool, span)
        else:
            # Single player takes the place money (span==1), or unknown
            # policy falls back to even split too.
            shares = split_cents(pool, span)
        label = (f"{_ordinal(place)}" if span == 1
                 else f"{_ordinal(place)}–{_ordinal(place + span - 1)} (T)")
        for name, cents in zip(group, shares):
            rows.append({"place_label": label, "player_name": name,
                         "amount": cents / 100.0})
        place += span
    return rows


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
