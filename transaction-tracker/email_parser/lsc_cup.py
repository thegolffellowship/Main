"""Lone Star Cup match engine (Track B, #654/#659).

Computes Ryder Cup-style match state — per-hole winner flags, running
margin, close-out, team points — from LOCALLY entered gross scores
(Track A's score entry feed), the locked playing handicaps, and the
course stroke index. It deliberately emits the SAME match-detail dict
that gg_match_play.parse_match_play_detail produces from Golf Genius
({players, holes:[{hole, order, p1_gross, p2_gross, p1_strokes,
p2_strokes, winner}], hole_pars, thru, gg_margin, ...}), so the
existing dormie-correct close-out walk and the Match Play tab's
mp-match-card renderer are reused unchanged. CMP's GG-scraping live
path is untouched.

Rules live in the `lsc_matches` dial (rules-as-data, #659):
{"event_id": 3329, "points_to_win": null, "halved_match": 0.5,
 "sessions": [{"id": "sat-am", "label": "...", "date": "2026-10-10",
               "format": "singles"|"fourball", "points_per_match": 1,
               "se_round": null, "n_holes": 18,
               "matches": [{"id": "SAT-AM-1", "tee_time": "8:30",
                            "austin": [cid, ...], "sa": [cid, ...]}]}]}

The weekend format is already ratified in the LSC How-It-Works popup
(contests.html): Sat AM Fourball, Sat PM Foursomes, Sun Singles.
Handicapping (proposed default, Kerry corrects via #659 Q3): full
difference of LOCKED playing handicaps off the match's low man,
strokes taken on the lowest stroke-index holes; four-ball plays
everyone off the low man of all four; foursomes takes the standard
50%-of-combined-difference at team level. Playing handicaps come from
Track A's payload (the locked snapshot) and are never re-derived here.

Scores while Track A's se_* tables aren't live yet: the
`lsc_mock_scores` dial ({"<session_id>": {"course": [{hole, par,
stroke_index}], "phs": {"<cid>": 12}, "scores": {"<cid>": {"1": 4}}}})
feeds the same pipeline, so the member page renders real match cards
on mock data for Kerry's rule-3b phone review before any live wire.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# Teams in fixed display order: p1/team1 = Austin, p2/team2 = San Antonio
# (matches the ops roster colors — Austin #BF5700, SA #4B6274).
TEAM_KEYS = ("austin", "sa")


# ---------------------------------------------------------------------------
# Stroke allocation
# ---------------------------------------------------------------------------

def strokes_received(ph: float, low_ph: float, course: list[dict],
                     n_holes: int) -> dict[int, int]:
    """Per-hole strokes a player RECEIVES playing off `low_ph`.

    Full difference (rounded to a whole number), one stroke on each of
    the N lowest-stroke-index holes; a difference beyond n_holes wraps
    (second stroke on the hardest holes again). Holes missing a
    stroke_index fall back to hole-number order, so a course loaded
    without SI still allocates deterministically.
    """
    diff = int(round((ph or 0) - (low_ph or 0)))
    if diff <= 0:
        return {}
    holes = sorted((c for c in course if c.get("hole")),
                   key=lambda c: (c.get("stroke_index") or c["hole"]))
    holes = holes[:n_holes] if len(holes) > n_holes else holes
    if not holes:
        return {}
    out: dict[int, int] = {}
    base, extra = divmod(diff, len(holes))
    for i, c in enumerate(holes):
        s = base + (1 if i < extra else 0)
        if s:
            out[int(c["hole"])] = s
    return out


# ---------------------------------------------------------------------------
# Match detail (the gg_match_play-shaped dict)
# ---------------------------------------------------------------------------

def _hole_numbers(course: list[dict], n_holes: int) -> list[int]:
    nums = sorted(int(c["hole"]) for c in course if c.get("hole"))
    if not nums:
        nums = list(range(1, n_holes + 1))
    return nums[:n_holes]


def _team_line(cids: list[int], hole: int, scores: dict, strokes: dict):
    """Best-NET ball for one team on one hole → (gross, strokes, net) of
    the counting player, or (None, 0, None) when no ball is in. A
    partner without a score simply doesn't count (a pickup in
    four-ball); singles passes one-man teams so the same path serves
    both formats."""
    best = None
    for cid in cids:
        g = (scores.get(cid) or {}).get(hole)
        if g is None:
            continue
        s = (strokes.get(cid) or {}).get(hole, 0)
        net = g - s
        if best is None or net < best[2]:
            best = (g, s, net)
    return best or (None, 0, None)


def compute_match_detail(match: dict, session: dict, course: list[dict],
                         phs: dict, scores: dict,
                         names: dict | None = None) -> dict:
    """One match → the gg_match_play-shaped detail dict.

    match:   {"id", "austin": [cid, ...], "sa": [cid, ...], "tee_time"?}
    session: the dial session (format, n_holes)
    course:  [{hole, par, stroke_index}]
    phs:     {cid: locked playing handicap}
    scores:  {cid: {hole:int → gross:int}}  (missing holes ABSENT, not 0)
    names:   {cid: display name} (roster); falls back to "#<cid>".
    """
    names = names or {}
    n_holes = int(session.get("n_holes") or 18)
    fmt = (session.get("format") or "singles").strip().lower()
    teams = [[int(c) for c in (match.get(k) or [])] for k in TEAM_KEYS]
    everyone = [c for t in teams for c in t]
    if fmt == "foursomes":
        # Alternate shot: ONE ball per team (Track A enters the team's
        # gross against either partner). Strokes at TEAM level — the
        # standard foursomes allowance, 50% of the combined-handicap
        # difference, on the lowest stroke-index holes — assigned to
        # every member so whichever partner's row carries the gross
        # gets the team's strokes.
        combined = [sum(phs.get(c) or 0 for c in t) for t in teams]
        low_comb = min(combined) if combined else 0
        strokes = {}
        for t, comb in zip(teams, combined):
            smap = strokes_received(comb * 0.5, low_comb * 0.5,
                                    course, n_holes)
            for c in t:
                strokes[c] = smap
    else:
        # singles + four-ball: full difference off the match's low man
        low_ph = min((phs.get(c) or 0) for c in everyone) if everyone else 0
        strokes = {c: strokes_received(phs.get(c) or 0, low_ph,
                                       course, n_holes)
                   for c in everyone}
    # normalize per-player scores to int hole keys
    sc = {c: {int(h): g for h, g in (scores.get(c) or scores.get(str(c)) or {}).items()
              if g is not None}
          for c in everyone}

    holes_out = []
    for order, hn in enumerate(_hole_numbers(course, n_holes), start=1):
        g1, s1, n1 = _team_line(teams[0], hn, sc, strokes)
        g2, s2, n2 = _team_line(teams[1], hn, sc, strokes)
        if n1 is None or n2 is None:
            winner = None          # hole not complete for both sides
        elif n1 < n2:
            winner = 1
        elif n2 < n1:
            winner = 2
        else:
            winner = 0
        holes_out.append({"hole": hn, "order": order,
                          "p1_gross": g1, "p2_gross": g2,
                          "p1_strokes": s1, "p2_strokes": s2,
                          "winner": winner})

    def _line_name(cids):
        return " / ".join(names.get(c) or names.get(str(c)) or f"#{c}"
                          for c in cids)

    players = [{"name": _line_name(t), "customer_ids": t,
                "handicap": (phs.get(t[0]) if len(t) == 1 else
                             [phs.get(c) for c in t])}
               for t in teams]
    detail = {
        "match_id": match.get("id"),
        "players": players,
        # start_hole None (not 1): cup matches all start on 1, and the
        # card's "Started on hole N" caption is noise when N is 1.
        # match_len tells mpMatchHoleCount the true length outright so
        # a closed-out card still renders its full 18 (dead holes grey).
        "start_hole": None,
        "match_len": n_holes,
        "holes": holes_out,
        "n_holes": n_holes,
        "hole_pars": {str(int(c["hole"])): c.get("par")
                      for c in course if c.get("hole") and c.get("par")},
    }
    from email_parser.gg_match_play import rederive_close_out
    rederive_close_out(detail, n_holes)
    return detail


# ---------------------------------------------------------------------------
# Board rollup
# ---------------------------------------------------------------------------

def _match_state(detail: dict) -> str:
    played = sum(1 for h in detail["holes"] if h["winner"] is not None)
    if played == 0:
        return "upcoming"
    if detail.get("gg_winner_idx") and (detail.get("closed_at_order")
                                        or played >= detail["n_holes"]):
        return "final"
    if played >= detail["n_holes"]:
        return "final"           # halved match, all holes in
    return "live"


def compute_board(dial: dict, session_data: dict,
                  names: dict | None = None) -> dict:
    """The full cup board.

    dial:          the lsc_matches dial.
    session_data:  {session_id: {"course": [...], "phs": {cid: ph},
                    "scores": {cid: {hole: gross}}}} — from Track A's
                    feed or the lsc_mock_scores dial; a session with no
                    entry renders every match "upcoming".
    Points: a FINAL match pays points_per_match to the winner, or
    halved_match (default 0.5) each on a halve. A LIVE leader counts
    toward the projected totals only.
    """
    halved = float(dial.get("halved_match") or 0.5)
    board = {"event_id": dial.get("event_id"),
             "points_to_win": dial.get("points_to_win"),
             "teams": {"austin": {"points": 0.0, "projected": 0.0},
                       "sa": {"points": 0.0, "projected": 0.0}},
             "sessions": []}
    for sess in dial.get("sessions") or []:
        data = (session_data or {}).get(sess.get("id")) or {}
        course = data.get("course") or []
        phs = {int(k): v for k, v in (data.get("phs") or {}).items()}
        scores = {int(k): v for k, v in (data.get("scores") or {}).items()}
        ppm = float(sess.get("points_per_match") or 1)
        s_out = {"id": sess.get("id"), "label": sess.get("label"),
                 "date": sess.get("date"), "format": sess.get("format"),
                 "points_per_match": ppm, "matches": []}
        for m in sess.get("matches") or []:
            detail = compute_match_detail(m, sess, course, phs, scores, names)
            state = _match_state(detail)
            pts = {"austin": 0.0, "sa": 0.0}
            if state == "final":
                w = detail.get("gg_winner_idx")
                if w == 1:
                    pts["austin"] = ppm
                elif w == 2:
                    pts["sa"] = ppm
                else:
                    pts["austin"] = pts["sa"] = ppm * halved
                for k in pts:
                    board["teams"][k]["points"] += pts[k]
                    board["teams"][k]["projected"] += pts[k]
            elif state == "live":
                w = detail.get("gg_winner_idx")   # current leader (lead != 0)
                if w == 1:
                    board["teams"]["austin"]["projected"] += ppm
                elif w == 2:
                    board["teams"]["sa"]["projected"] += ppm
                else:
                    board["teams"]["austin"]["projected"] += ppm / 2.0
                    board["teams"]["sa"]["projected"] += ppm / 2.0
            s_out["matches"].append({**detail, "tee_time": m.get("tee_time"),
                                     "state": state, "points": pts})
        board["sessions"].append(s_out)
    for t in board["teams"].values():
        t["points"] = round(t["points"], 2)
        t["projected"] = round(t["projected"], 2)
    return board


# ---------------------------------------------------------------------------
# DB wiring (dial + roster + mock scores)
# ---------------------------------------------------------------------------

def _setting_json(conn, key):
    row = conn.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key = ?",
        (key,)).fetchone()
    if not row or not row[0]:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        logger.warning("lsc_cup: %s dial is not valid JSON", key)
        return None


def _nice_case(word: str) -> str:
    """SHOUTING roster names → display case, keeping Mc/Mac and O'
    prefixes right (MCDONNELL → McDonnell, O'BRIEN → O'Brien). Mixed-
    case input is left alone — it's already how the person writes it."""
    if not word or word != word.upper():
        return word
    w = word.title()
    import re as _re
    w = _re.sub(r"^(Mc)(\w)", lambda m: "Mc" + m.group(2).upper(), w)
    w = _re.sub(r"^(Mac)([b-z]\w{2,})", lambda m: "Mac" + m.group(2).capitalize(), w)
    w = _re.sub(r"^(O')(\w)", lambda m: "O'" + m.group(2).upper(), w)
    return w


def roster_names(conn) -> dict[int, str]:
    """cid → display name from the FROZEN lsc_roster_final dial
    (\"LAST, First\" → \"First Last\")."""
    dial = _setting_json(conn, "lsc_roster_final") or {}
    out: dict[int, str] = {}
    for ch in dial.get("chapters") or []:
        for seat in ch.get("seats") or []:
            cid, nm = seat.get("customer_id"), seat.get("player_name") or ""
            if not cid:
                continue
            if "," in nm:
                last, _, first = nm.partition(",")
                nm = " ".join(_nice_case(p) for p in first.strip().split()) \
                    + " " + " ".join(_nice_case(p) for p in last.strip().split())
            out[int(cid)] = nm
    return out


def lsc_board_payload(db_path=None) -> dict:
    """The member-page read: dial + roster + best available scores
    (Track A's feed once its tables land; the lsc_mock_scores dial until
    then, and for the rule-3b static review). One cheap read — the
    member endpoint serves this."""
    from email_parser.database import _connect
    with _connect(db_path) as conn:
        dial = _setting_json(conn, "lsc_matches")
        if not dial:
            return {"configured": False}
        names = roster_names(conn)
        session_data = _setting_json(conn, "lsc_mock_scores") or {}
        # TODO(Track A): when se_* lands, prefer real entered scores per
        # session (se_round binding) over the mock dial.
        board = compute_board(dial, session_data, names)
        board["configured"] = True
        board["source"] = "mock" if session_data else "none"
        # Rule 3b: the member page shows the board only once Kerry flips
        # board_live in the dial (after his phone OK). Admin/manager
        # sessions preview it regardless — the route enforces this.
        board["board_live"] = bool(dial.get("board_live"))
        return board
