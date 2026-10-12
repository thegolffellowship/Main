"""CUP CHAMPION TITLES for the Player Spotlight header (Kerry 2026-10-12:
"if someone was either The Fellowship Cup or The Players Cup Champion, they
need that listed in the header ... 'The Fellowship Cup - 2026 Champion' for Gus
Vasquez. For Robert Straiton 'The Players Cup - 2024 & 2026 Champion'").

Only the OVERALL winner of a cup gets a title (Kerry): never a flight winner,
never a player who topped the standings without being bought in. The current
season is DERIVED from the cup's own declared champion(s) (`champions` in the
race payload: final, enrolled, best rank, the same rule as the plaque and the
money). Past seasons are not in the Spotlight data, so they come from
CUP_CHAMPION_HISTORY below: a list Kerry states, never inferred. Add a year
only on Kerry's word.
"""
from __future__ import annotations

# cup -> season -> customer_ids. Kerry, 2026-10-12, verbatim: "Robert 2024"
# (Players Cup, Robert Straiton); "Jay Horton was 2025 winner for both cups";
# "Mark Freund was 2024 Fellowship Cup". "We'll get into the rest later."
# Kerry, same day: "Jay Horton was also 2023 champion of The Players Cup which was
# the first year we awarded that trophy. The Fellowship Cup has been around for all
# 20 years" (so Fellowship Cup history is long and still to come from Kerry).
CUP_CHAMPION_HISTORY = {
    "fellowship_cup": {2024: [299], 2025: [289]},   # Mark Freund; Jay Horton
    "players_cup": {2023: [289], 2024: [31], 2025: [289]},   # Jay Horton; Robert Straiton; Jay Horton
}

CUP_NAMES = {"fellowship_cup": "The Fellowship Cup",
             "players_cup": "The Players Cup"}
CUP_ORDER = ("fellowship_cup", "players_cup")   # Fellowship above Players (Kerry 2026-07-12)


def _years_text(years: list) -> str:
    ys = [str(y) for y in sorted(set(years))]
    if len(ys) <= 1:
        return "".join(ys)
    return ", ".join(ys[:-1]) + " & " + ys[-1]


def title_line(cup: str, years: list) -> str:
    """'The Fellowship Cup - 2026 Champion', 'The Players Cup - 2024 & 2026
    Champion', 'The Players Cup - 2022, 2024 & 2026 Champion'."""
    return f"{CUP_NAMES[cup]} - {_years_text(years)} Champion"


def cup_titles(customer_id: int, season: int, current: dict | None = None) -> list:
    """The player's titles, Fellowship Cup first. `current` maps cup key to the
    declared champion customer_ids of THIS season (None/empty when the cup is
    not final), e.g. {"fellowship_cup": [42], "players_cup": [31]}."""
    out = []
    for cup in CUP_ORDER:
        years = {y for y, ids in CUP_CHAMPION_HISTORY.get(cup, {}).items()
                 if customer_id in ids}
        if customer_id in ((current or {}).get(cup) or []):
            years.add(season)
        if years:
            ys = sorted(years)
            out.append({"cup": cup, "years": ys, "line": title_line(cup, ys)})
    return out
