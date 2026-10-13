"""A player's LONE STAR CUP record for the Spotlight (Kerry 2026-10-12: "Show
Record where Seat is", link to the matches, and "Gus clinched the 2026 Lone Star
Cup for San Antonio").

Read-only off the FROZEN cup board (`lsc_cup.lsc_board_payload`, source "final"):
nothing here scores or recomputes the Cup. Before the board is final the caller
keeps the seat view. Match order in the board is TEAM_KEYS order, so side 0 is
Austin and side 1 is San Antonio.
"""
from __future__ import annotations

TEAM_KEYS = ("austin", "sa")
TEAM_NAMES = {"austin": "Austin", "sa": "San Antonio"}

# WHO CLINCHED, by season. Not derived at read time: the board has no finish
# times, so this is the scorers' hole-save times worked out once
# (scoring-se-hole-times:20, 2026-10-12). San Antonio held the Cup after the
# Saturday sessions at 9.5 points and, as the defending champion, needed more
# than half of 28 (14). Sunday's singles closed in this order (UTC save time of
# the closing hole): SUN-3 17:40, SUN-5 17:50 (SA 10.5), SUN-4 17:54 (11.5),
# SUN-2 18:05, SUN-12 18:16 (12.5), SUN-6 18:20 (13.5), then SUN-8, Gus Vasquez
# over Kaleb McDonnell 5&3, at 18:21:54 (14.5). The next SA point (SUN-9) came
# 11 minutes later. Kerry said "Gus clinched"; the times agree.
LSC_CLINCH = {
    2026: {"match_id": "SUN-8", "team": "sa", "customer_ids": [42]},
}


def _pts(x: float) -> str:
    whole, half = int(x), x - int(x) >= 0.5
    return f"{whole}½" if half and whole else ("½" if half else str(whole))


def _record_text(w: int, l: int, h: int) -> str:
    return f"{w}–{l}" + (f"–{h}" if h else "")


def player_record(board: dict, customer_id: int, year: int) -> dict | None:
    """The player's cup record and matches, or None when the board is not the
    FINAL cup board or the player never played a match."""
    if not board or not board.get("configured") or board.get("source") != "final":
        return None
    matches, w, l, h = [], 0, 0, 0
    team = None
    for se in board.get("sessions") or []:
        for m in se.get("matches") or []:
            if m.get("state") != "final":
                continue
            sides = m.get("players") or []
            idx = next((i for i, s in enumerate(sides[:2])
                        if customer_id in (s.get("customer_ids") or [])), None)
            if idx is None:
                continue
            mine, theirs = TEAM_KEYS[idx], TEAM_KEYS[1 - idx]
            team = team or mine
            pts = m.get("points") or {}
            a, b = float(pts.get(mine) or 0), float(pts.get(theirs) or 0)
            res = "W" if a > b else ("L" if a < b else "H")
            w, l, h = w + (res == "W"), l + (res == "L"), h + (res == "H")

            def names(side, skip=None):
                return [n for n, c in zip(_display_names(side), side.get("customer_ids") or [])
                        if c != skip]

            matches.append({
                "match_id": m.get("match_id"),
                "session": se.get("id"),
                "format": se.get("title") or (se.get("label") or "").upper(),
                "result": res,
                "margin": None if res == "H" else (m.get("gg_margin") or None),
                "partners": names(sides[idx], customer_id),
                "opponents": names(sides[1 - idx]),
            })
    if not matches:
        return None
    try:   # the cup's own season, not today's: a 2026 board read in 2027 is still 2026
        year = int(str(((board.get("sessions") or [{}])[0]).get("date") or year)[:4])
    except (TypeError, ValueError):
        pass
    cup = board.get("cup") or {}
    teams = board.get("teams") or {}
    winner = cup.get("winner")
    sa, au = float((teams.get("sa") or {}).get("points") or 0), float((teams.get("austin") or {}).get("points") or 0)
    hi, lo = (sa, au) if sa >= au else (au, sa)
    cup_line = None
    if winner in TEAM_NAMES:
        verb = "retained" if winner == cup.get("defending_champion") else "won"
        cup_line = f"Team {TEAM_NAMES[winner]} {verb} the Cup, {_pts(hi)}–{_pts(lo)}"
    clinch = LSC_CLINCH.get(year) or {}
    clinched = bool(clinch and customer_id in clinch.get("customer_ids", [])
                    and any(m["match_id"] == clinch.get("match_id") for m in matches))
    return {"w": w, "l": l, "h": h, "text": _record_text(w, l, h),
            "team": team, "team_name": TEAM_NAMES.get(team),
            "cup_line": cup_line, "cup_winner": winner,
            "clinched": clinched,
            "clinch_team": TEAM_NAMES.get(clinch.get("team")) if clinched else None,
            "year": year, "matches": matches}


def _display_names(side: dict) -> list:
    """'Jay Hogue & Walter Hogue' -> ['Jay Hogue', 'Walter Hogue'], by the side's own
    name; falls back to the display lines."""
    nm = side.get("name") or ""
    parts = [p.strip() for p in nm.split("&")] if "&" in nm else [nm.strip()]
    ids = side.get("customer_ids") or []
    if len(parts) == len(ids):
        return parts
    return [str(x) for x in (side.get("lines") or [])][:len(ids)]
