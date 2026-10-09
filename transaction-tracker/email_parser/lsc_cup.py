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
{"event_id": 3329, "defending_champion": "austin"|"sa"|null,
 "skins": {"basis": null|"net"|"gross", "carryover": null|bool},
 "sessions": [{"id": "sat-am", "label": "...", "date": "2026-10-10",
               "format": "singles"|"fourball"|"chapman",
               "se_round": null, "n_holes": 18,
               "matches": [{"id": "SAT-AM-1", "tee_time": "8:30",
                            "austin": [cid, ...], "sa": [cid, ...]}]}]}

The weekend format is already ratified in the LSC How-It-Works popup
(contests.html): Sat AM Four-Ball, Sat PM Chapman, Sun Singles.
Points (Kerry, CA #717): 1 for a win, 1/2 for a halve, every format;
level points = the defending champion keeps the cup. Skins replace
CTP and are scored separately from the match (compute_skins); their
basis, pot and carryover are still Kerry's to rule.
Handicap allowances (Kerry RATIFIED, CA #721, USGA/WHS Appendix C):
singles 100% (full difference); four-ball 90% of each player, all off
the low player; the team session is CHAPMAN, team handicap = 60% of the
lower partner + 40% of the higher, the higher team getting the
difference. WHS order: allowance, round, then difference. Applied on
the locked playing handicap from Track A's payload (100% of course
handicap, rounded), never re-derived.

Scores while Track A's se_* tables aren't live yet: the
`lsc_mock_scores` dial ({"<session_id>": {"course": [{hole, par,
stroke_index}], "phs": {"<cid>": 12}, "scores": {"<cid>": {"1": 4}}}})
feeds the same pipeline, so the member page renders real match cards
on mock data for Kerry's rule-3b phone review before any live wire.
"""

from __future__ import annotations

import json
import logging

from email_parser.handicap_calc import whs_round

logger = logging.getLogger(__name__)

# Teams in fixed display order: p1/team1 = Austin, p2/team2 = San Antonio
# (matches the ops roster colors — Austin #BF5700, SA #4B6274).
TEAM_KEYS = ("austin", "sa")


# ---------------------------------------------------------------------------
# Stroke allocation
# ---------------------------------------------------------------------------

# Kerry's ratified allowances (CA #721, 2026-09-26, rule 3b), the USGA/WHS
# Appendix C match-play recommendations. They apply to the LOCKED playing
# handicap score entry carries, which is the course handicap at 100%,
# rounded (handicap_calc.playing_handicap, allowance 1.0). WHS order:
# allowance on the course handicap, round, then take the difference.
SINGLES_ALLOWANCE = 1.00              # the higher player gets the full difference
FOURBALL_ALLOWANCE = 0.90             # each player's 90%, all off the low player
CHAPMAN_LOW_SHARE, CHAPMAN_HIGH_SHARE = 0.60, 0.40   # team = 60% low + 40% high

# The team alternate-shot session is CHAPMAN (Pinehurst), not straight
# foursomes (CA #721). Older dials and Track A's one-ball set name it
# "foursomes" or "alternate shot"; for this event every one of them IS
# Chapman, so they normalise here and can never fall back to the old
# 50%-of-combined number.
ONE_BALL_FORMATS = {"chapman", "foursomes", "alternate_shot", "alternate-shot",
                    "alternate shot", "pinehurst"}


# Session TITLES (Kerry 2026-10-07, CoS #1397-1, binding everywhere):
# "FOURBALL, FOURSOMES, SINGLES, not FOUR-BALL or CHAPMAN - Chapman is
# just the type of FOURSOMES we're playing."
SESSION_TITLES = {"fourball": "FOURBALL", "chapman": "FOURSOMES",
                  "singles": "SINGLES"}


def session_title(fmt: str | None) -> str:
    f = normalize_format(fmt)
    return SESSION_TITLES.get(f, f.upper())


def normalize_format(fmt: str | None) -> str:
    f = (fmt or "singles").strip().lower()
    if f in ONE_BALL_FORMATS:
        return "chapman"
    if f in ("four-ball", "four ball", "fourball", "best ball", "best-ball"):
        return "fourball"
    return "singles" if f in ("singles", "single", "") else f


def _course_for(course: list[dict], si_by_player: dict | None, cid) -> list[dict]:
    """The round's holes with THIS player's tee stroke index, when his
    tee has its own (WHS: strokes fall on the index of the tee played)."""
    si = (si_by_player or {}).get(cid) or (si_by_player or {}).get(str(cid))
    if not si:
        return course
    return [{**h, "stroke_index": si.get(h.get("hole"), si.get(str(h.get("hole")),
                                                                h.get("stroke_index")))}
            for h in course]


def _chapman_course(course: list[dict], si_by_player: dict | None,
                    tee_gender: dict | None, team: list) -> list[dict]:
    """The stroke-index table a Chapman pair plays on (Kerry 2026-09-28):
    the men's when either partner plays a men's tee, the women's when
    both play women's tees; the round's list when the tees are unknown."""
    g = {c: ((tee_gender or {}).get(c) or (tee_gender or {}).get(str(c)) or "").upper()
         for c in team}
    men = [c for c in team if g[c] == "M"]
    if men:
        return _course_for(course, si_by_player, men[0])
    women = [c for c in team if g[c] == "F"]
    if women and len(women) == len(team):
        return _course_for(course, si_by_player, women[0])
    return course


def match_format(match: dict, session: dict) -> str:
    """The format ONE match is played and handicapped under.

    A match may name its own format; otherwise a one-v-one match inside a
    team session (four-ball / Chapman) is SINGLES at 100% (Kerry
    2026-09-28: with an odd player, he plays singles matches against the
    other side's spare pair in the team sessions, "one whole point
    available for each of those matches"). Everything else takes the
    session's format. Kept general for any team match-play event."""
    if match.get("format"):
        return normalize_format(match.get("format"))
    fmt = normalize_format(session.get("format"))
    if fmt in ("fourball", "chapman") and all(
            len(match.get(k) or []) == 1 for k in TEAM_KEYS):
        return "singles"
    return fmt


def skins_team_sides(matches: list) -> list:
    """The TEAM-SKINS entries of a team session, as match-shaped dicts
    ({"id", "austin": [...], "sa": [...]}) that compute_skins keys as
    "<id>:<side>".

    Ordinary team matches stay as they are. Singles matches inside a
    team session are regrouped so nobody is entered twice (Kerry
    2026-09-28): a player who plays SEVERAL singles matches at once (the
    odd player's threesome) is one entry, counted once, and the players
    he faces are ONE team entry (their better ball). A lone one-v-one
    match keeps one entry per side. Idempotent: regrouped output passes
    through unchanged."""
    singles, out = [], []
    for m in matches or []:
        if all(len(m.get(k) or []) == 1 for k in TEAM_KEYS):
            singles.append(m)
        else:
            out.append(m)
    seen = {}
    for m in singles:
        for k in TEAM_KEYS:
            seen.setdefault(int(m[k][0]), []).append(m)
    used = set()
    for m in singles:
        if m.get("id") in used:
            continue
        hub_side = next((k for k in TEAM_KEYS if len(seen[int(m[k][0])]) > 1), None)
        if hub_side is None:
            out.append(m)
            used.add(m.get("id"))
            continue
        hub = int(m[hub_side][0])
        other = "sa" if hub_side == "austin" else "austin"
        group = [x for x in seen[hub] if x.get("id") not in used]
        opps = []
        for x in group:
            c = int(x[other][0])
            if c not in opps:
                opps.append(c)
            used.add(x.get("id"))
        out.append({"id": "+".join(str(x.get("id")) for x in group),
                    hub_side: [hub], other: opps})
    return out


def chapman_team_handicap(phs: list) -> int:
    """60% of the lower partner + 40% of the higher, rounded per WHS."""
    vals = sorted(float(v or 0) for v in phs) or [0.0]
    lo, hi = vals[0], vals[-1]
    return whs_round(CHAPMAN_LOW_SHARE * lo + CHAPMAN_HIGH_SHARE * hi)


def session_handicaps(fmt: str, teams: list[list[int]], phs: dict) -> dict:
    """The handicap each side plays off in this session, after the
    ratified allowance and WHS rounding: {cid: value} for singles and
    four-ball, {"team:<i>": value} for Chapman (one ball per team)."""
    fmt = normalize_format(fmt)

    def _ph(c):
        v = phs.get(c)
        if v is None:
            v = phs.get(str(c))
        return float(v or 0)

    if fmt == "chapman":
        return {f"team:{i}": chapman_team_handicap([_ph(c) for c in t])
                for i, t in enumerate(teams)}
    pct = FOURBALL_ALLOWANCE if fmt == "fourball" else SINGLES_ALLOWANCE
    return {c: whs_round(_ph(c) * pct) for t in teams for c in t}


def strokes_received(ph: float, low_ph: float, course: list[dict],
                     n_holes: int) -> dict[int, int]:
    """Per-hole strokes a player RECEIVES playing off `low_ph`.

    Full difference (WHS-rounded), one stroke on each of
    the N lowest-stroke-index holes; a difference beyond n_holes wraps
    (second stroke on the hardest holes again). Holes missing a
    stroke_index fall back to hole-number order, so a course loaded
    without SI still allocates deterministically.
    """
    diff = whs_round((ph or 0) - (low_ph or 0))
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


def _team_line(cids: list[int], hole: int, scores: dict, strokes: dict,
               picked: dict | None = None):
    """Best-NET ball for one team on one hole → (gross, strokes, net,
    all_picked) of the counting player, or (None, 0, None, False) when no
    ball is in. A partner without a score simply doesn't count; singles
    passes one-man teams so the same path serves both formats.

    PICKED UP (Kerry 2026-09-25): a ball marked picked_up (entered at
    triple, the max) cannot win the hole, so it never counts while a
    live ball does. When every entered ball on the side is picked up the
    line carries that ball's gross for display, net None and all_picked
    True -- the side cannot win the hole."""
    picked = picked or {}
    best = None
    fallback = None
    for cid in cids:
        g = (scores.get(cid) or {}).get(hole)
        if g is None:
            continue
        s = (strokes.get(cid) or {}).get(hole, 0)
        if hole in (picked.get(cid) or ()):
            if fallback is None:
                fallback = (g, s, None, True)
            continue
        net = g - s
        if best is None or net < best[2]:
            best = (g, s, net, False)
    return best or fallback or (None, 0, None, False)


def compute_match_detail(match: dict, session: dict, course: list[dict],
                         phs: dict, scores: dict,
                         names: dict | None = None,
                         marks: dict | None = None,
                         si_by_player: dict | None = None,
                         tee_gender: dict | None = None) -> dict:
    """One match → the gg_match_play-shaped detail dict.

    match:   {"id", "austin": [cid, ...], "sa": [cid, ...], "tee_time"?}
    session: the dial session (format, n_holes)
    course:  [{hole, par, stroke_index}]
    phs:     {cid: locked playing handicap}
    scores:  {cid: {hole:int → gross:int}}  (missing holes ABSENT, not 0)
    names:   {cid: display name} (roster); falls back to "#<cid>".
    marks:   {cid: {hole: "picked_up" | "holed"}} from score entry (a
             triple in a match is ball-in-hole or picked up). Picked up
             cannot win the hole; both sides picked up = a push.
    si_by_player: {cid: {hole: stroke_index}} for a player whose tee has
             its OWN stroke index (a women's tee). WHS: each player's
             strokes fall on the stroke index of the tee HE plays (Kerry
             2026-09-28: "Shouldn't matter where players play from").
             Singles and four-ball use it per player.
    tee_gender: {cid: "M" | "F"}, the gender of the tee each player
             plays. A CHAPMAN pair (one ball) takes its strokes on the
             men's stroke index when either partner plays a men's tee,
             and on the women's when both play women's tees (Kerry
             2026-09-28, a TGF term of competition: WHS leaves which
             table a mixed pair uses to the Committee). Unknown tees
             keep the round's list.
    """
    names = names or {}
    n_holes = int(session.get("n_holes") or 18)
    fmt = match_format(match, session)
    teams = [[int(c) for c in (match.get(k) or [])] for k in TEAM_KEYS]
    everyone = [c for t in teams for c in t]
    hcp = session_handicaps(fmt, teams, phs)
    if fmt == "chapman":
        # ONE ball per team (Track A enters the team's gross against
        # either partner). Team handicap = 60% low + 40% high, WHS-rounded;
        # the higher team gets the difference on the lowest stroke-index
        # holes, assigned to every member so whichever partner's row
        # carries the gross gets the team's strokes.
        team_vals = [hcp[f"team:{i}"] for i in range(len(teams))]
        low = min(team_vals) if team_vals else 0
        strokes = {}
        for t, th in zip(teams, team_vals):
            smap = strokes_received(
                th, low, _chapman_course(course, si_by_player, tee_gender, t),
                n_holes)
            for c in t:
                strokes[c] = smap
    else:
        # singles 100% / four-ball 90%: every player off the low player,
        # each on the stroke index of his own tee
        low = min(hcp.values()) if hcp else 0
        strokes = {c: strokes_received(hcp[c], low,
                                       _course_for(course, si_by_player, c),
                                       n_holes)
                   for c in everyone}
    # normalize per-player scores to int hole keys
    sc = {c: {int(h): g for h, g in (scores.get(c) or scores.get(str(c)) or {}).items()
              if g is not None}
          for c in everyone}

    picked = {c: {int(h) for h, m in ((marks or {}).get(c) or (marks or {}).get(str(c)) or {}).items()
                  if m == "picked_up"}
              for c in everyone}
    def _side_pops(cids, hn):
        if fmt == "fourball" or not cids:
            return None
        return (strokes.get(cids[0]) or {}).get(hn, 0)

    holes_out = []
    for order, hn in enumerate(_hole_numbers(course, n_holes), start=1):
        g1, s1, n1, pu1 = _team_line(teams[0], hn, sc, strokes, picked)
        g2, s2, n2, pu2 = _team_line(teams[1], hn, sc, strokes, picked)
        if g1 is None or g2 is None:
            winner = None          # hole not complete for both sides
        elif pu1 and pu2:
            winner = 0             # both picked up / over max: a push
        elif pu1:
            winner = 2             # side 1 cannot win the hole
        elif pu2:
            winner = 1
        elif n1 < n2:
            winner = 1
        elif n2 < n1:
            winner = 2
        else:
            winner = 0
        holes_out.append({"hole": hn, "order": order,
                          "p1_gross": g1, "p2_gross": g2,
                          "p1_strokes": s1, "p2_strokes": s2,
                          # the side's strokes on this hole BEFORE anyone
                          # plays it (pop dots): one ball per side in
                          # singles and Chapman; four-ball partners differ,
                          # so read detail["strokes"] per player there.
                          "p1_pops": _side_pops(teams[0], hn),
                          "p2_pops": _side_pops(teams[1], hn),
                          "p1_picked_up": pu1, "p2_picked_up": pu2,
                          "winner": winner})

    def _line_name(cids):
        return " & ".join(names.get(c) or names.get(str(c)) or f"#{c}"
                          for c in cids)

    # "handicap" is what the side PLAYS OFF after the session allowance;
    # course_handicap keeps the locked 100% figure(s) it came from.
    players = [{"name": _line_name(t), "customer_ids": t,
                "handicap": (hcp.get(f"team:{i}") if fmt == "chapman"
                             else (hcp.get(t[0]) if len(t) == 1
                                   else [hcp.get(c) for c in t])),
                "course_handicap": (phs.get(t[0]) if len(t) == 1
                                    else [phs.get(c) for c in t])}
               for i, t in enumerate(teams)]
    detail = {
        "match_id": match.get("id"),
        "players": players,
        # start_hole None (not 1): cup matches all start on 1, and the
        # card's "Started on hole N" caption is noise when N is 1.
        # match_len tells mpMatchHoleCount the true length outright so
        # a closed-out card still renders its full 18 (dead holes grey).
        "start_hole": None,
        "match_len": n_holes,
        "format": fmt,
        # every player's allowance-applied match strokes by hole, known
        # before a ball is struck (Chapman partners share the team's)
        "strokes": {str(c): {str(h): n for h, n in (strokes.get(c) or {}).items()}
                    for c in everyone},
        # every player's own gross by hole (Kerry 10/9: the opened card follows
        # the City Match Play standards, and a four-ball card shows both
        # partners' balls, not only the side's best one). Gross is public on
        # the events board already; no money here.
        "scores": {str(c): {str(h): g for h, g in sorted(sc[c].items())} for c in everyone},
        "picked_up": {str(c): sorted(picked[c]) for c in everyone if picked[c]},
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


# Kerry's ruling (CA #717, 2026-09-26, rule 3b): 1 point for a win and
# ½ for a halve, the SAME in every format. These are the event-level
# defaults; the dial may carry points_win / halved_match, but no
# per-session value exists any more, because the ruling is one value for
# every session.
POINTS_WIN = 1.0
POINTS_HALVE = 0.5


def cup_status(points: dict, total: float,
               defending_champion: str | None) -> dict:
    """Who holds the cup, and what each side still needs.

    Tiebreak (Kerry, CA #717): if the points finish level, the DEFENDING
    CHAMPION keeps the cup. So the champion clinches at exactly half the
    points on the board, and the challenger has to pass half. With no
    champion recorded (the dial's defending_champion unset) both sides
    need more than half, and a finished tie reads "tied_pending" rather
    than guessing who keeps it.

    Returns {total, half, defending_champion, status, winner, needs}:
    status is open | won | retained | tied_pending; winner is the team
    that has clinched (won or retained) or None; needs[team] is the
    points still required to clinch, 0 once clinched."""
    total = float(total or 0)
    half = total / 2.0
    champ = defending_champion if defending_champion in TEAM_KEYS else None
    pts = {k: float((points or {}).get(k) or 0) for k in TEAM_KEYS}
    step = POINTS_HALVE            # scores move in half-point steps
    target = {k: (half if k == champ else half + step) for k in TEAM_KEYS}
    status, winner = "open", None
    if total > 0:
        for k in TEAM_KEYS:
            if pts[k] > half:
                status, winner = "won", k
        if winner is None and champ and pts[champ] >= half:
            status, winner = "retained", champ
        if winner is None and sum(pts.values()) >= total \
                and pts["austin"] == pts["sa"]:
            status = "tied_pending"   # no champion on record to keep it
    needs = {k: (0.0 if winner == k else round(max(0.0, target[k] - pts[k]), 2))
             for k in TEAM_KEYS}
    return {"total": round(total, 2), "half": round(half, 2),
            "defending_champion": champ, "status": status,
            "winner": winner, "needs": needs}


def compute_skins(session: dict, course: list[dict], phs: dict,
                  scores: dict, marks: dict | None = None,
                  names: dict | None = None, basis: str = "net",
                  carryover: bool = False, si_by_player: dict | None = None,
                  tee_gender: dict | None = None) -> dict:
    """Skins for one session, a calculation SEPARATE from the match
    (Kerry, CA #717). It reads raw scores only, never the match state, so
    holes played after a match is decided count here and nothing here
    can change a match result.

    - Team sessions (four-ball, Chapman) play TEAM skins: each side of
      each match is one entry, across the whole session. Singles play
      INDIVIDUAL skins: every player is an entry.
    - basis "net" | "gross". Kerry has not ruled which (CA #717), so the
      board only calls this once the dial names one. Net strokes use the
      SESSION's ratified allowance (CA #721: singles 100%, four-ball
      90%, Chapman 60/40 team) taken off zero, not off the low man
      (skins are a field game); a plus handicap gets nothing on a hole,
      per the plus rule (it comes off the round, never a hole).
    - A picked-up ball never wins a skin.
    - A hole is decided only when EVERY entry has posted it (the money
      hold: no win shows before the field is in); until then "pending".
    - One lowest score wins the skin. A tie wins nothing, and carries the
      skin to the next hole only when carryover is on (unruled, so off).
    """
    names = names or {}
    marks = marks or {}
    fmt = normalize_format(session.get("format"))
    n_holes = int(session.get("n_holes") or 18)
    team_game = fmt in ("fourball", "chapman")
    # A player who withdrew mid-round (injury, Kerry 2026-09-28) stops
    # posting; an entry made only of withdrawn players no longer holds a
    # hole open for everyone else. Scores he did post still count.
    withdrawn = {int(c) for c in session.get("withdrawn") or []}

    entries = []
    smatches = (skins_team_sides(session.get("matches") or []) if team_game
                else (session.get("matches") or []))
    for m in smatches:
        for side in TEAM_KEYS:
            cids = [int(c) for c in (m.get(side) or [])]
            if not cids:
                continue
            if team_game:
                entries.append({"key": f"{m.get('id')}:{side}",
                                "team": side, "cids": cids})
            else:
                for c in cids:
                    # a player in two singles matches at once (the odd
                    # player) is one skins entry, never two
                    if any(c in e["cids"] for e in entries):
                        continue
                    entries.append({"key": f"{m.get('id')}:{side}:{c}",
                                    "team": side, "cids": [c]})
    for e in entries:
        e["label"] = " & ".join(names.get(c) or names.get(str(c)) or f"#{c}"
                                for c in e["cids"])

    sc = {}
    picked = {}
    for e in entries:
        for c in e["cids"]:
            raw = scores.get(c) or scores.get(str(c)) or {}
            sc[c] = {int(h): g for h, g in raw.items() if g is not None}
            mk = marks.get(c) or marks.get(str(c)) or {}
            picked[c] = {int(h) for h, v in mk.items() if v == "picked_up"}

    def _strokes_for(e):
        if basis != "net":
            return {c: {} for c in e["cids"]}
        # The session's ratified allowance (CA #721), taken off ZERO:
        # skins are a field game, not a head-to-head off the low man.
        # Pops fall on each player's OWN tee's stroke index (Kerry
        # 2026-10-06: "Dots ALWAYS use the SI's from that set of tees"); a
        # Chapman pair plays the table the match engine gives it.
        if fmt == "chapman":
            th = chapman_team_handicap([phs.get(c) if phs.get(c) is not None
                                        else phs.get(str(c)) for c in e["cids"]])
            tcourse = _chapman_course(course, si_by_player, tee_gender, e["cids"])
            smap = strokes_received(th, 0, tcourse, n_holes)
            return {c: smap for c in e["cids"]}
        hc = session_handicaps(fmt, [e["cids"]], phs)
        return {c: strokes_received(hc[c], 0, _course_for(course, si_by_player, c),
                                    n_holes)
                for c in e["cids"]}

    strokes = {e["key"]: _strokes_for(e) for e in entries}
    totals = {e["key"]: 0 for e in entries}
    # The ball each entry played for skins on each hole, for the Skins
    # board (Kerry 10/9: "Skins leaderboard should look just like the event
    # leaderboard"): {key: {hole: [gross, pops]}} — the counting ball's
    # gross and the strokes it got (team net: the best net ball; gross
    # skins: no pops). Scores only, no money: members get it too.
    cards = {e["key"]: {} for e in entries}
    holes_out = []
    carry = 0
    for hn in _hole_numbers(course, n_holes):
        posted_all = True
        best_by_entry = {}
        for e in entries:
            posted = False
            best = None
            shown = None                # [gross, pops] of the ball shown
            for c in e["cids"]:
                g = sc.get(c, {}).get(hn)
                if g is None:
                    continue
                posted = True
                pops = strokes[e["key"]].get(c, {}).get(hn, 0)
                if hn in picked.get(c, set()):
                    if shown is None:
                        shown = [g, pops]
                    continue            # a picked-up ball can't win a skin
                v = g - pops
                if best is None or v < best:
                    best = v
                    shown = [g, pops]
            if not posted and not all(c in withdrawn for c in e["cids"]):
                posted_all = False
            best_by_entry[e["key"]] = best
            if shown is not None:
                cards[e["key"]][hn] = shown
        if not entries or not posted_all:
            holes_out.append({"hole": hn, "status": "pending",
                              "winner": None, "score": None, "value": 0})
            continue
        live = {k: v for k, v in best_by_entry.items() if v is not None}
        low = min(live.values()) if live else None
        at_low = [k for k, v in live.items() if v == low]
        if len(at_low) == 1:
            value = 1 + carry
            carry = 0
            totals[at_low[0]] += value
            holes_out.append({"hole": hn, "status": "won",
                              "winner": at_low[0], "score": low,
                              "value": value})
        else:
            if carryover:
                carry += 1
            holes_out.append({"hole": hn, "status": "tied", "winner": None,
                              "score": low, "value": 0})
    by_key = {e["key"]: e for e in entries}
    board = [{"key": k, "label": by_key[k]["label"],
              "team": by_key[k]["team"], "skins": v}
             for k, v in totals.items()]
    board.sort(key=lambda r: (-r["skins"], r["label"]))
    par = {int(h["hole"]): h.get("par") for h in course
           if h.get("hole") is not None and h.get("par") is not None}
    return {"kind": "team" if team_game else "individual",
            "basis": basis, "carryover": bool(carryover),
            "carried": carry, "holes": holes_out, "totals": board,
            "cards": {k: {str(h): v for h, v in hs.items()}
                      for k, hs in cards.items()},
            "par": {str(h): p for h, p in par.items()},
            "entry_cids": {e["key"]: e["cids"] for e in entries}}


# Kerry's ratified skins rules (CA #725/#726, 2026-09-26, rule 3b).
# SATURDAY TEAM SKINS ARE NET (Kerry 2026-10-07, CoS #1357-1: "Definitely
# want Team Skins to be full session allowance, not by Off Lowest within
# match."): four-ball = each player's PH at the session's 90%, best net
# ball per side; Chapman = the 60/40 team handicap on the one ball. Both
# taken off ZERO (a field game), never off the lowest in the match.
# Sunday singles stay individual GROSS in two flights (#1351-C).
SKINS_TEAM_BASIS = "net"
SKINS_SINGLES_BASIS = "gross"
SKINS_BASIS = SKINS_SINGLES_BASIS     # kept for old readers: the singles basis
SKINS_CARRYOVER = False               # a tied low score = no skin, nothing carries
SKINS_PER_ROUND_CENTS = 2500          # $75 weekend = $25 per player per round
SINGLES_FLIGHT_BREAK = 12.0           # Flight 1 <= 11.9, Flight 2 >= 12.0 (TGF 18-hole index)
SINGLES_FLIGHT_SHARES = (50.0, 50.0)  # Sunday pot split in half by default
UNEVEN_FLIGHT_RATIO = 2.0             # flag when one flight is 2x the other (or empty)


def compute_skins_payout(session: dict, course: list[dict], phs: dict,
                         scores: dict, marks: dict | None = None,
                         names: dict | None = None,
                         buyers: set | None = None,
                         index: dict | None = None,
                         si_by_player: dict | None = None,
                         tee_gender: dict | None = None) -> dict:
    """One round's skins pot and payout (Kerry, CA #725/#726). Staff
    only: the member payload strips every amount (strip_money).

    - Each 18 is its own pot: $25 x the players IN THIS SESSION who
      bought the weekend skins (buyers = the SKINS add-on on the cup
      roster). Pots are never pooled across rounds.
    - Saturday team sessions: team NET skins (Kerry 2026-10-07, #1357-1)
      at the full session allowance off zero, never off the lowest in
      the match: four-ball best net ball at 90% of each PH, Chapman one
      net score off the 60/40 team handicap; pops on each player's own
      tee's stroke index. One flight. Each team skin is split evenly
      between the partners. A MIXED team (one partner bought, one
      didn't) still plays, and the buyer is paid the FULL team skin
      (Kerry, CA #759): nothing is left over, nothing redistributed. A
      team where neither bought is out of the hole entirely: its score
      can neither win a skin nor tie one out (#1357-2). An odd player's singles matches
      inside a team session count him ONCE, and the pair he faces is one
      team entry (skins_team_sides, Kerry 2026-09-28).
    - Sunday singles: individual gross skins flighted on the TGF
      18-hole index frozen at the event: Flight 1 below 12.0, Flight 2
      at 12.0 and up, each playing for half the pot. A player with no
      index on record can't be flighted and is flagged. Badly uneven
      flights are flagged for Kerry BEFORE the round.
    - No carryover: a hole with a tied low score pays nothing, and a
      pot where nobody wins a skin stays unallocated (flagged).
    - Money hold: no dollar is shown until every entry in the group
      has posted every hole; until then the group reads held.
    - Every split is exact to the cent (largest-remainder), so what is
      paid always sums to the pot.
    """
    from email_parser.match_play import allocate_cents, split_cents
    names = names or {}
    index = index or {}
    fmt = normalize_format(session.get("format"))
    team_game = fmt in ("fourball", "chapman")
    basis = SKINS_TEAM_BASIS if team_game else SKINS_SINGLES_BASIS

    def _bought(c):
        return buyers is None or c in buyers

    def _label(cids):
        return " & ".join(names.get(c) or names.get(str(c)) or f"#{c}"
                          for c in cids)

    flags, excluded, mixed = [], [], []
    flight_members: dict = {}
    paid_cids = {}      # team key -> the partners who are paid (the buyers)
    in_round = set()
    for m in session.get("matches") or []:
        for side in TEAM_KEYS:
            for c in (m.get(side) or []):
                if _bought(int(c)):
                    in_round.add(int(c))
    pot_cents = SKINS_PER_ROUND_CENTS * len(in_round)

    # entrants per group: [(group_key, label, pot_share_pct, matches)]
    if team_game:
        matches = []
        for m in skins_team_sides(session.get("matches") or []):
            mm = {"id": m.get("id")}
            for side in TEAM_KEYS:
                cids = [int(c) for c in (m.get(side) or [])]
                got = [c for c in cids if _bought(c)]
                if cids and len(got) == len(cids):
                    mm[side] = cids
                elif got:
                    # plays for team skins; only the buyer is paid, and
                    # he takes the whole team skin (CA #759)
                    mm[side] = cids
                    paid_cids[f"{m.get('id')}:{side}"] = got
                    mixed.append({"label": _label(cids), "team": side,
                                  "paid": _label(got),
                                  "not_paid": _label([c for c in cids
                                                      if c not in got])})
                elif cids:
                    mm[side] = []
                    excluded.append({"label": _label(cids), "team": side,
                                     "reason": "not bought in"})
            matches.append(mm)
        groups = [(None, "Team skins", 100.0, matches)]
    else:
        fl = {1: [], 2: []}
        placed = set()
        for m in session.get("matches") or []:
            for side in TEAM_KEYS:
                for c in (m.get(side) or []):
                    c = int(c)
                    if c in placed:          # the odd player: one entry
                        continue
                    placed.add(c)
                    if not _bought(c):
                        excluded.append({"label": _label([c]), "team": side,
                                         "reason": "not bought in"})
                        continue
                    ix = index.get(c)
                    if ix is None:
                        ix = index.get(str(c))
                    if ix is None:
                        excluded.append({"label": _label([c]), "team": side,
                                         "reason": "no TGF index on record "
                                         "to flight"})
                        flags.append(f"{_label([c])} has no TGF index on "
                                     "record, so can't be flighted.")
                        continue
                    f = 1 if float(ix) < SINGLES_FLIGHT_BREAK else 2
                    fl[f].append((m.get("id"), side, c, float(ix)))
        n1, n2 = len(fl[1]), len(fl[2])
        if min(n1, n2) == 0 or max(n1, n2) >= UNEVEN_FLIGHT_RATIO * min(n1, n2):
            flags.append(f"Flights are uneven ({n1} in Flight 1, {n2} in "
                         "Flight 2) on a half-and-half split: flag to Kerry "
                         "before the round.")
        groups = []
        for f, share in zip((1, 2), SINGLES_FLIGHT_SHARES):
            lbl = (f"Flight {f} (index "
                   + ("under 12.0" if f == 1 else "12.0 and up") + ")")
            groups.append((f, lbl, share,
                           [{"id": mid, side: [c]} for mid, side, c, _ix in fl[f]]))
            # Who is in the flight, lowest index first: the Skins pane's
            # "12 players · Pat Youngs to Wilson" (#1398). Names only, no
            # money, so members get it too.
            flight_members[f] = [{"customer_id": c, "name": _label([c])}
                                 for _m, _s, c, _ix in sorted(fl[f], key=lambda t: (t[3], _label([t[2]])))]

    shares = allocate_cents(pot_cents, [g[2] for g in groups]) \
        if groups else []
    out_groups = []
    for (flight, lbl, _pct, matches), gpot in zip(groups, shares):
        sk = compute_skins({**session, "matches": matches}, course, phs,
                           scores, marks, names, basis=basis,
                           carryover=SKINS_CARRYOVER,
                           si_by_player=si_by_player, tee_gender=tee_gender)
        entrants = len(sk["totals"])
        complete = entrants > 0 and all(h["status"] != "pending"
                                        for h in sk["holes"])
        won = sum(t["skins"] for t in sk["totals"])
        payouts, unpaid = None, None
        if complete:
            payouts, unpaid = [], 0
            winners = [t for t in sk["totals"] if t["skins"] > 0]
            if won == 0 or gpot == 0:
                unpaid = gpot
            else:
                cents = allocate_cents(gpot, [t["skins"] * 100.0 / won
                                              for t in winners])
                # compute_skins keys a team "<match>:<side>" and a
                # singles player "<match>:<side>:<cid>"
                key_cids = {}
                for m in matches:
                    for side in TEAM_KEYS:
                        cids = m.get(side) or []
                        if team_game and cids:
                            k = f"{m.get('id')}:{side}"
                            key_cids[k] = paid_cids.get(k, cids)
                        for c in ([] if team_game else cids):
                            key_cids[f"{m.get('id')}:{side}:{c}"] = [c]
                for t, c in zip(winners, cents):
                    ent_cids = key_cids.get(t["key"], [])
                    per = split_cents(c, max(1, len(ent_cids)))
                    payouts.append({**t, "cents": c,
                                    "per_player": [{"customer_id": cid, "cents": pc}
                                                   for cid, pc in zip(ent_cids, per)]})
        if entrants == 0 and gpot:
            flags.append(f"{lbl}: nobody is entered, so its "
                         f"${gpot / 100:.2f} can't be won.")
        elif complete and won == 0:
            flags.append(f"{lbl}: no skin was won, so ${gpot / 100:.2f} "
                         "is unallocated (no carryovers).")
        # Per entry: the index and the handicap the skin was played off,
        # for the board's Idx / PH columns (no money, members get it).
        meta = {}
        for k, cids in (sk.get("entry_cids") or {}).items():
            if team_game:
                ph = None
                if fmt == "chapman":
                    vals = [phs.get(c) if phs.get(c) is not None
                            else phs.get(str(c)) for c in cids]
                    if vals and all(v is not None for v in vals):
                        ph = chapman_team_handicap(vals)
                meta[k] = {"index": None, "ph": ph}
            else:
                c = cids[0]
                ix = index.get(c) if index.get(c) is not None else index.get(str(c))
                ph = phs.get(c) if phs.get(c) is not None else phs.get(str(c))
                meta[k] = {"index": ix, "ph": ph}
        out_groups.append({"flight": flight, "label": lbl,
                           "members": flight_members.get(flight),
                           "pot_cents": gpot, "entrants": entrants,
                           "complete": complete, "held": not complete,
                           "skins_won": won, "holes": sk["holes"],
                           "totals": sk["totals"], "payouts": payouts,
                           "unpaid_cents": unpaid,
                           "cards": sk.get("cards") or {},
                           "par": sk.get("par") or {},
                           "entries": meta})
    return {"kind": "team" if team_game else "individual",
            "basis": basis, "carryover": SKINS_CARRYOVER,
            "buyers_in_round": len(in_round), "pot_cents": pot_cents,
            "groups": out_groups, "excluded": excluded, "mixed": mixed,
            "flags": flags}


def strip_money(board: dict) -> dict:
    """The member view of a board: skins COUNTS stay, every dollar and
    every staff flag goes (CA #726: the payout is staff only)."""
    import copy
    b = copy.deepcopy(board)
    b.pop("dial_warnings", None)
    b.pop("results_frozen", None)
    for sess in b.get("sessions") or []:
        for m in sess.get("matches") or []:
            if isinstance(m.get("result_override"), dict):
                m["result_override"] = {k: v for k, v in m["result_override"].items()
                                        if k != "note"}
        sk = sess.get("skins")
        if not sk:
            continue
        # The Skins pane (#1398) shows which hole each skin came from and
        # who is in each Sunday flight: hole results, entrants and flight
        # members carry no money, so members get them; pot, payouts,
        # unpaid, excluded/mixed and flags stay staff only.
        sess["skins"] = {"kind": sk.get("kind"), "basis": sk.get("basis"),
                         "groups": [{"flight": g.get("flight"),
                                     "label": g.get("label"),
                                     "totals": g.get("totals"),
                                     "holes": [{k: h.get(k) for k in
                                                ("hole", "status", "winner", "value")}
                                               for h in g.get("holes") or []],
                                     "members": g.get("members"),
                                     "entrants": g.get("entrants"),
                                     "complete": g.get("complete"),
                                     # the Skins board's hole scores +
                                     # Idx/PH (Kerry 10/9): scores only
                                     "cards": g.get("cards"),
                                     "par": g.get("par"),
                                     "entries": g.get("entries")}
                                    for g in sk.get("groups") or []]}
    return b


def match_result_override(match: dict) -> dict | None:
    """A result staff record on the match in the dial:
    "result": {"winner": "austin" | "sa" | "halved", "margin"?, "note"?}.
    For a concession or a match an injury stopped (Kerry 2026-09-28:
    "ability to pivot quickly ... in worst case scenarios"). Which way an
    injury goes (conceded or halved) is decided by staff case by case;
    the board records it and never guesses. None when absent or bad."""
    r = match.get("result")
    if not isinstance(r, dict):
        return None
    w = (r.get("winner") or "").strip().lower()
    if w not in ("austin", "sa", "halved"):
        return None
    return {"winner": w,
            "margin": r.get("margin") or ("Halved" if w == "halved" else "Conceded"),
            "note": r.get("note")}


def validate_matches(dial: dict) -> list[str]:
    """Plain-sentence problems with the lsc_matches pairings, so a quick
    change at the course (a withdrawal, the odd player) is checked before
    it goes live. Empty = the dial is consistent.

    Rules: every match has a player on each side; nobody plays for both
    teams; a player is in at most one team match per session; only the
    odd player may be in two matches in one session, and only as SINGLES
    matches (his threesome); withdrawn players must be in the session."""
    out = []
    for sess in dial.get("sessions") or []:
        sid = sess.get("id")
        fmt = normalize_format(sess.get("format"))
        if fmt not in ("singles", "fourball", "chapman"):
            out.append(f"{sid}: unknown format {sess.get('format')!r}")
        count, sides, singles_only = {}, {}, {}
        for m in sess.get("matches") or []:
            mid = m.get("id")
            if match_result_override(m) is None and m.get("result") is not None:
                out.append(f"{sid} {mid}: result must name winner austin, sa or halved")
            one_v_one = all(len(m.get(k) or []) == 1 for k in TEAM_KEYS)
            for k in TEAM_KEYS:
                if not m.get(k):
                    out.append(f"{sid} {mid}: no {k} player")
                for c in m.get(k) or []:
                    c = int(c)
                    count[c] = count.get(c, 0) + 1
                    sides.setdefault(c, set()).add(k)
                    singles_only[c] = singles_only.get(c, True) and one_v_one
        for c, n in count.items():
            if len(sides[c]) > 1:
                out.append(f"{sid}: player {c} is on both teams")
            if n > 2:
                out.append(f"{sid}: player {c} is in {n} matches (2 at most)")
            elif n == 2 and not singles_only[c]:
                out.append(f"{sid}: player {c} is in two matches, and only "
                           "the odd player's singles threesome allows that")
        for c in sess.get("withdrawn") or []:
            if int(c) not in count:
                out.append(f"{sid}: withdrawn player {c} isn't in this session")
    return out


def compute_board(dial: dict, session_data: dict,
                  names: dict | None = None,
                  skins_ctx: dict | None = None) -> dict:
    """The full cup board.

    dial:          the lsc_matches dial.
    session_data:  {session_id: {"course": [...], "phs": {cid: ph},
                    "scores": {cid: {hole: gross}}, "marks": {...}}} from
                    Track A's feed or the lsc_mock_scores dial; a session
                    with no entry renders every match "upcoming".
    Points (Kerry, CA #717): a FINAL match pays POINTS_WIN (1) to the
    winner or POINTS_HALVE (½) to each side on a halve, in every
    format. A live leader counts toward the projection only. A match
    decided at the close-out is FINAL, and holes played after it feed
    skins only (compute_skins), never the match.
    """
    win = float(dial.get("points_win") or POINTS_WIN)
    halve = float(dial.get("halved_match") or POINTS_HALVE)
    # skins_ctx: {"buyers": set of cids who bought the weekend skins,
    # "index": {cid: frozen TGF 18-hole index}} (lsc_board_payload).
    skins_ctx = skins_ctx or {}
    board = {"event_id": dial.get("event_id"),
             "teams": {"austin": {"points": 0.0, "projected": 0.0},
                       "sa": {"points": 0.0, "projected": 0.0}},
             "points_win": win, "points_halve": halve,
             "sessions": []}
    total = 0.0
    for sess in dial.get("sessions") or []:
        data = (session_data or {}).get(sess.get("id")) or {}
        course = data.get("course") or []
        phs = {int(k): v for k, v in (data.get("phs") or {}).items()}
        scores = {int(k): v for k, v in (data.get("scores") or {}).items()}
        marks = {int(k): v for k, v in (data.get("marks") or {}).items()}
        si_by_player = {int(k): {int(h): int(x) for h, x in v.items()}
                        for k, v in (data.get("si_by_player") or {}).items()}
        tee_gender = {int(k): v for k, v in (data.get("tee_gender") or {}).items()}
        s_out = {"id": sess.get("id"), "label": sess.get("label"),
                 "title": session_title(sess.get("format")),
                 "date": sess.get("date"), "format": sess.get("format"),
                 "points_per_match": win, "matches": [], "skins": None}
        for m in sess.get("matches") or []:
            total += win
            detail = compute_match_detail(m, sess, course, phs, scores, names, marks,
                                          si_by_player, tee_gender)
            state = _match_state(detail)
            ov = match_result_override(m)
            if ov:
                # a result recorded by staff (a concession, or a match an
                # injury stopped, Kerry 2026-09-28) is FINAL as recorded
                detail["gg_winner_idx"] = {"austin": 1, "sa": 2}.get(ov["winner"], 0)
                detail["gg_margin"] = ov["margin"]
                detail["result_override"] = ov
                state = "final"
            pts = {"austin": 0.0, "sa": 0.0}
            if state == "final":
                w = detail.get("gg_winner_idx")
                if w == 1:
                    pts["austin"] = win
                elif w == 2:
                    pts["sa"] = win
                else:
                    pts["austin"] = pts["sa"] = halve
                for k in pts:
                    board["teams"][k]["points"] += pts[k]
                    board["teams"][k]["projected"] += pts[k]
            elif state == "live":
                w = detail.get("gg_winner_idx")   # current leader (lead != 0)
                if w == 1:
                    board["teams"]["austin"]["projected"] += win
                elif w == 2:
                    board["teams"]["sa"]["projected"] += win
                else:
                    board["teams"]["austin"]["projected"] += halve
                    board["teams"]["sa"]["projected"] += halve
            s_out["matches"].append({**detail, "tee_time": m.get("tee_time"),
                                     "state": state, "points": pts})
        s_out["skins"] = compute_skins_payout(
            sess, course, phs, scores, marks, names,
            buyers=skins_ctx.get("buyers"), index=skins_ctx.get("index"),
            si_by_player=si_by_player, tee_gender=tee_gender)
        # a session still being drawn counts its full match count toward
        # the points on the board (the dial's n_matches: 7 / 7 / 14), so the
        # Cup reads "14½ to win" from the first landed match
        total += win * max(0, int(sess.get("n_matches") or 0)
                           - len(sess.get("matches") or []))
        board["sessions"].append(s_out)
    for t in board["teams"].values():
        t["points"] = round(t["points"], 2)
        t["projected"] = round(t["projected"], 2)
    board["cup"] = cup_status({k: v["points"] for k, v in board["teams"].items()},
                              total, dial.get("defending_champion"))
    return board


# ---------------------------------------------------------------------------
# DB wiring (dial + roster + mock scores)
# ---------------------------------------------------------------------------

def _setting_json(conn, key):
    # app_settings columns are key/value (see database.py's CREATE TABLE)
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
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


def merge_entry_feed(dial: dict, feed: dict) -> dict:
    """Track A's entered-scores read (score_entry.get_entered_scores,
    the rounds-plural event-scoped shape CA ruled in #661) → the
    {session_id: {course, phs, scores}} overrides compute_board takes.

    Only sessions bound to a round (se_round = that read's round_id)
    are produced — everything else keeps whatever source it had (the
    lsc_mock_scores dial during staging). Playing handicaps are taken
    from the feed AS-IS: the locked PH snapshot, never re-derived
    (#661 item 4). A foursomes TEAM row (one ball, customer_ids pair)
    lands on its first listed partner — the engine's team line reads
    any partner's ball, and team-level strokes cover both."""
    out: dict = {}
    rounds = {r.get("round_id"): r for r in (feed or {}).get("rounds") or []}
    for sess in dial.get("sessions") or []:
        rid = sess.get("se_round")
        r = rounds.get(rid) if rid is not None else None
        if not r:
            continue
        phs = {int(p["customer_id"]): p.get("playing_handicap")
               for p in r.get("players") or [] if p.get("customer_id")}
        scores = {int(p["customer_id"]): dict(p.get("scores") or {})
                  for p in r.get("players") or [] if p.get("customer_id")}
        # pickup marks (Kerry 2026-09-25) travel beside the scores
        marks = {int(p["customer_id"]): dict(p.get("marks") or {})
                 for p in r.get("players") or [] if p.get("customer_id") and p.get("marks")}
        for t in r.get("teams") or []:
            cids = [c for c in (t.get("customer_ids") or []) if c]
            if not cids or not t.get("scores"):
                continue
            slot = scores.setdefault(int(cids[0]), {})
            # the team ball wins over any stray individual entry
            slot.update(t["scores"])
            if t.get("marks"):
                marks.setdefault(int(cids[0]), {}).update(t["marks"])
        tees = {int(p["customer_id"]): p.get("tee")
                for p in r.get("players") or [] if p.get("customer_id") and p.get("tee")}
        out[sess.get("id")] = {"course": r.get("course") or [],
                               "phs": phs, "scores": scores, "marks": marks,
                               "tees": tees, "course_id": r.get("course_id")}
    return out


def _tee_info(conn, course_id, tee) -> tuple:
    """(gender, {hole: stroke_index}) for a player's tee on the course
    record. The seat's tee may be a tee NAME ("Teal") or a TGF band
    ("Forward"); lower() on both sides (#682). (None, {}) when it can't
    be resolved."""
    t = (str(tee or "")).strip().lower()
    if not course_id or not t:
        return None, {}
    rows = conn.execute(
        "SELECT tee_id, tee_name, tgf_bands, gender FROM course_tees WHERE course_id = ?",
        (int(course_id),)).fetchall()
    pick = None
    for r in rows:
        if lower_eq(r[1], t) or t in [b.strip().lower() for b in str(r[2] or "").split(",")]:
            pick = r
            break
    if pick is None:
        return None, {}
    si = {int(h): int(x) for h, x in conn.execute(
        "SELECT hole_number, stroke_index FROM course_tee_holes "
        "WHERE tee_id = ? AND stroke_index IS NOT NULL", (pick[0],)).fetchall()}
    return ((pick[3] or "").upper() or None), si


def _tee_stroke_index(conn, course_id, tee) -> dict:
    return _tee_info(conn, course_id, tee)[1]


def lower_eq(a, b) -> bool:
    return str(a or "").strip().lower() == str(b or "").strip().lower()


def _attach_player_stroke_index(conn, session_data: dict) -> None:
    """For every session read from score entry, give each player whose
    tee carries a DIFFERENT stroke index from the round's holes his own
    list (si_by_player). Read-only; a failure leaves the round's list."""
    for data in (session_data or {}).values():
        if not isinstance(data, dict):      # e.g. the mock dial's "_note"
            continue
        tees, cid_course = data.get("tees") or {}, data.get("course_id")
        if not tees or not cid_course:
            continue
        base = {int(h["hole"]): h.get("stroke_index") for h in data.get("course") or []}
        cache, out, genders = {}, {}, {}
        try:
            for cid, tee in tees.items():
                if tee not in cache:
                    cache[tee] = _tee_info(conn, cid_course, tee)
                gender, si = cache[tee]
                if gender:
                    genders[int(cid)] = gender
                if si and any(si.get(h) != v for h, v in base.items()):
                    out[int(cid)] = si
        except Exception:
            logger.exception("lsc_cup: per-player stroke index read failed")
            continue
        if out:
            data["si_by_player"] = out
        if genders:
            data["tee_gender"] = genders


def _skins_ctx(conn, dial: dict, db_path=None) -> dict:
    """Who bought the weekend skins (the SKINS add-on on the cup's
    one-off roster, oneoff_addons) and each player's TGF 18-hole index
    frozen at the event (the handicap lock: _event_index_as_of). A read
    that fails returns None for that part, and the payout says so
    rather than guessing."""
    ctx = {"buyers": None, "index": {}}
    eid = dial.get("event_id")
    if not eid:
        return ctx
    try:
        add = (_setting_json(conn, "oneoff_addons") or {}).get(str(eid)) or {}
        ctx["buyers"] = {int(c) for c, keys in add.items()
                         if "skins" in (keys or [])}
    except Exception:
        logger.exception("lsc_cup: skins buyers read failed")
    try:
        from email_parser import database as db
        ev = conn.execute("SELECT * FROM events WHERE id = ?",
                          (int(eid),)).fetchone()
        as_of = db._event_index_as_of(dict(ev)) if ev else None
        ctx["index"] = db._handicap_index_18_by_customer(db_path,
                                                         as_of=as_of) or {}
    except Exception:
        logger.exception("lsc_cup: frozen index read failed")
    # The HANDICAP LOCK (Kerry 2026-10-07, CoS #1389): an index stored for
    # this event in `lsc_handicap_lock` is the index of record for the
    # Sunday flights and wins over the computed one.
    try:
        lock = ((_setting_json(conn, "lsc_handicap_lock") or {}).get(str(eid))
                or {}).get("players") or {}
        for c, v in lock.items():
            if isinstance(v, dict) and v.get("index") is not None:
                ctx["index"][int(c)] = float(v["index"])
    except Exception:
        logger.exception("lsc_cup: handicap lock read failed")
    return ctx


def lsc_board_payload(db_path=None) -> dict:
    """The member-page read: dial + roster + best available scores
    (Track A's feed once its tables land; the lsc_mock_scores dial until
    then, and for the rule-3b static review). One cheap read — the
    member endpoint serves this."""
    return _board_payload(db_path, use_frozen=True)


RESULTS_KEY = "lsc_results"


def _apply_handicap_lock(conn, dial: dict, session_data: dict) -> dict:
    """Fill each match player's course handicap from `lsc_handicap_lock`
    (Kerry 2026-10-07, CoS #1389) where the session's feed has none, so
    the board shows the locked CH and the match strokes before a ball is
    struck. A PH the score-entry feed carries is never replaced (it was
    seeded FROM the lock). Returns a new session_data."""
    lock = ((_setting_json(conn, "lsc_handicap_lock") or {})
            .get(str(dial.get("event_id"))) or {}).get("players") or {}
    if not lock:
        return session_data
    out = dict(session_data or {})
    for sess in dial.get("sessions") or []:
        sid = sess.get("id")
        data = dict(out.get(sid) or {})
        phs = {int(k): v for k, v in (data.get("phs") or {}).items()}
        for m in sess.get("matches") or []:
            for side in TEAM_KEYS:
                for c in m.get(side) or []:
                    v = lock.get(str(c)) or {}
                    if phs.get(int(c)) is None and v.get("ch") is not None:
                        phs[int(c)] = int(v["ch"])
        if phs:
            data["phs"] = phs
            out[sid] = data
    return out


def _fill_event_course(conn, dial: dict, session_data: dict) -> dict:
    """A session with no course yet (its Live Scoring round isn't seeded)
    takes the Cup event's course: par and stroke index from the course
    record, so the member board shows where the pops fall the moment THE
    DRAW lands (Kerry 10/8: "All should be expandable to see the scorecards
    for each match and where pops will be"). A seeded round's course is
    never replaced. Never raises."""
    try:
        eid = int(dial.get("event_id") or 0)
        if not eid:
            return session_data
        row = conn.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone()
        if not row:
            return session_data
        from email_parser.score_entry import _event_course_holes
        out = dict(session_data or {})
        cache = {}
        for sess in dial.get("sessions") or []:
            sid = sess.get("id")
            data = dict(out.get(sid) or {})
            if data.get("course"):
                continue
            n = int(sess.get("n_holes") or 18)
            if n not in cache:
                cache[n] = _event_course_holes(conn, dict(row), n)
            if cache[n]:
                data["course"] = cache[n]
                out[sid] = data
        return out
    except Exception:
        logger.exception("lsc_cup: event course fill failed")
        return session_data


def for_viewer(board: dict, customer_id) -> dict:
    """The board as one player sees it (Kerry 10/7, CoS #1398): in every
    session his own match comes first and carries `yours: True`, and
    `your_matches` lists {session, match_id}. Anyone not in a match (a
    spectator) gets the board unchanged."""
    import copy
    b = copy.deepcopy(board)
    try:
        cid = int(customer_id)
    except (TypeError, ValueError):
        return b
    mine = []
    for sess in b.get("sessions") or []:
        ms = sess.get("matches") or []
        hit = [m for m in ms
               if any(cid in [int(x) for x in (p.get("customer_ids") or [])]
                      for p in m.get("players") or [])]
        for m in hit:
            m["yours"] = True
            mine.append({"session": sess.get("id"), "match_id": m.get("match_id")})
        sess["matches"] = hit + [m for m in ms if m not in hit]
    b["your_matches"] = mine
    return b


PREVIEW_DIAL = "lsc_preview_matches"
PREVIEW_KEY = PREVIEW_DIAL


def build_preview_dial(dial: dict, lock: dict) -> dict:
    """DEMO matches for Kerry's staff preview (CoS #1398-B) from the REAL
    pairs, pools, tee sheet and locked handicaps, never the real draw
    (that is Thursday's Zoom). Saturday: pair N of a pool v pair N of the
    other team's same pool, both sessions (Foursomes rotates the SA pairs
    one place inside each pool so the matchups differ). Sunday: each
    team's 14 by locked raw INDEX (ties by CH), 1 v 1 ... 14 v 14, two
    matches per tee time. Every session starts unbound (se_round None);
    the preview seeding binds its demo rounds."""
    pairs = dial.get("pairs") or {}
    tees = dial.get("tee_sheet") or {}
    players = (lock or {}).get("players") or {}

    def pool(team, name):
        return [p for p in pairs.get(team) or [] if p.get("pool") == name]

    def rotate(xs):
        return xs[1:] + xs[:1] if len(xs) > 1 else xs

    def sat(sid, rot):
        out, n = [], 0
        for name in ("low", "high"):
            a, s_ = pool("austin", name), pool("sa", name)
            if rot:
                s_ = rotate(s_)
            for pa, ps in zip(a, s_):
                n += 1
                tl = tees.get(sid) or []
                tt = tl[n - 1] if n <= len(tl) else None
                out.append({"id": f"{sid.upper()}-{n}", "tee_time": tt, "pool": name,
                            "austin": list(pa["cids"]), "sa": list(ps["cids"])})
        return out

    # Breakouts sort on the RAW index, never the course handicap (Kerry
    # 2026-10-07: "Handicap breakouts start with raw indexes not course
    # handicaps"); CH only breaks an exact index tie.
    def ranked(team):
        cids = [int(c) for c, v in players.items() if v.get("team") == team]
        return sorted(cids, key=lambda c: (players[str(c)].get("index", 99),
                                           players[str(c)].get("ch", 99)))

    sun, aus, sa = [], ranked("austin"), ranked("sa")
    st = tees.get("sun") or []
    for i, (a, s_) in enumerate(zip(aus, sa)):
        sun.append({"id": f"SUN-{i + 1}", "tee_time": st[i // 2] if i // 2 < len(st) else None,
                    "pool": "low" if i < 7 else "high", "austin": [a], "sa": [s_]})
    sess = {s.get("id"): s for s in dial.get("sessions") or []}
    out = {k: v for k, v in dial.items() if k != "sessions"}
    out["_note"] = ("DEMO matches for Kerry's staff preview only (CoS #1398-B), "
                    "built from the real pairs and locked handicaps. NOT the draw.")
    out["board_live"] = False
    out["sessions"] = []
    for sid, matches in (("sat-am", sat("sat-am", False)), ("sat-pm", sat("sat-pm", True)),
                         ("sun", sun)):
        base = sess.get(sid) or {}
        fmt = base.get("format") or {"sat-am": "fourball", "sat-pm": "chapman"}.get(sid, "singles")
        out["sessions"].append({"id": sid, "label": session_title(fmt), "format": fmt,
                                "date": base.get("date"), "points_per_match": 1,
                                "n_holes": 18, "se_round": None, "matches": matches})
    return out


def preview_board_payload(db_path=None, dial: dict | None = None) -> dict:
    """The STAFF PREVIEW board (Kerry 10/7, CoS #1398-B): the same engine on
    the demo dial and its PREVIEW rounds. Never the live dial, never the
    frozen results, never the mock scores; served to staff only. `dial`
    computes from a supplied dial instead of the stored one."""
    if dial is not None:
        from email_parser.database import _connect
        if not dial.get("sessions"):
            return {"configured": False}
        with _connect(db_path) as conn:
            b = _board_from_dial(conn, dial, db_path, use_mock=False,
                                 source_label="preview")
    else:
        b = _board_payload(db_path, use_frozen=False, dial_key=PREVIEW_DIAL)
    if b.get("configured"):
        b["preview"] = True
    return b


def _board_payload(db_path=None, use_frozen: bool = True, dial_key: str = "lsc_matches") -> dict:
    from email_parser.database import _connect
    with _connect(db_path) as conn:
        dial = _setting_json(conn, dial_key)
        if not dial:
            return {"configured": False}
        if use_frozen:
            # Past events are frozen (principle 4): once the final result
            # is snapshotted the board serves the snapshot, so a later
            # score edit can't quietly change who won the Cup.
            res = _setting_json(conn, RESULTS_KEY)
            if res and res.get("event_id") == dial.get("event_id") and res.get("board"):
                b = dict(res["board"])
                b["configured"] = True
                b["source"] = "final"
                b["results_frozen"] = {"frozen_at": res.get("frozen_at"),
                                       "forced": res.get("forced", False)}
                b["board_live"] = bool(dial.get("board_live"))
                return b
        return _board_from_dial(conn, dial, db_path,
                                use_mock=(dial_key == "lsc_matches"))


def _board_from_dial(conn, dial: dict, db_path=None, use_mock: bool = True,
                     source_label: str | None = None) -> dict:
    names = roster_names(conn)
    session_data = (_setting_json(conn, "lsc_mock_scores") or {}) if use_mock else {}
    # Real entered scores (Track A, live on main v2.493.0) take
    # precedence per session: any session bound via se_round reads
    # the rounds-plural event feed; unbound sessions keep the mock
    # dial (staging) or stay empty (upcoming).
    entry_used = False
    entry_sids: list = []
    bound = any(s.get("se_round") is not None
                for s in dial.get("sessions") or [])
    if bound and dial.get("event_id"):
        try:
            from email_parser.score_entry import get_entered_scores
            feed = get_entered_scores(int(dial["event_id"]),
                                      db_path=db_path)
            overrides = merge_entry_feed(dial, feed)
            if overrides:
                session_data = {**session_data, **overrides}
                entry_used = True
                entry_sids = sorted(overrides)
        except Exception:
            logger.exception("lsc_cup: entered-scores feed read "
                             "failed — board falls back to the "
                             "mock dial")
    has_scores = bool(session_data)
    session_data = _apply_handicap_lock(conn, dial, session_data)
    session_data = _fill_event_course(conn, dial, session_data)
    _attach_player_stroke_index(conn, session_data)
    skins_ctx = _skins_ctx(conn, dial, db_path)
    board = compute_board(dial, session_data, names, skins_ctx)
    board["configured"] = True
    board["source"] = source_label or ("entry" if entry_used
                                       else "mock" if has_scores else "none")
    # Rule 3b: the member page shows the board only once Kerry flips
    # board_live in the dial (after his phone OK). Admin/manager
    # sessions preview it regardless — the route enforces this.
    board["board_live"] = bool(dial.get("board_live"))
    # which sessions are scored from REAL entered cards (not the mock
    # dial): the skins payout writer pays from these and nothing else
    board["entry_sessions"] = entry_sids
    board["dial_warnings"] = validate_matches(dial)
    _attach_display_lines(conn, dial, board, db_path)
    return board


def _attach_display_lines(conn, dial: dict, board: dict, db_path=None) -> None:
    """Each match side's players as their own lines, "First LAST" with the
    LAST name in capitals for members and alumni (Kerry 10/8, on the member
    board: "Make sure each player gets their names in Bitters and last names
    are caps per our rules. Stack full names rather than wrap"). The same
    names THE DRAW shows (`lsc_draw._display_names`, Kerry's member ruling
    included). Never raises."""
    try:
        from email_parser.lsc_draw import _display_names
        eid = int(dial.get("event_id") or 0)
        lock = ((_setting_json(conn, "lsc_handicap_lock") or {}).get(str(eid)) or {}).get("players") or {}
        cids = sorted({int(c) for sess in board.get("sessions") or [] for m in sess.get("matches") or []
                       for p in m.get("players") or [] for c in p.get("customer_ids") or []})
        shown = _display_names(eid, cids, lock, db_path)
        names = roster_names(conn)
        for sess in board.get("sessions") or []:
            for m in sess.get("matches") or []:
                for p in m.get("players") or []:
                    p["lines"] = [shown.get(int(c)) or (lock.get(str(c)) or {}).get("name")
                                  or names.get(int(c)) or names.get(str(c)) or f"#{c}"
                                  for c in p.get("customer_ids") or []]
    except Exception:
        logger.exception("lsc_cup: display lines failed")


def results_blockers(board: dict) -> list[str]:
    """Why the Cup can't be snapshotted as final yet. Empty = final."""
    out = []
    cup = board.get("cup") or {}
    if cup.get("status") not in ("won", "retained", "tied_pending"):
        out.append(f"the Cup isn't decided (status {cup.get('status')})")
    for sess in board.get("sessions") or []:
        for m in sess.get("matches") or []:
            if m.get("state") != "final":
                out.append(f"{sess.get('id')} {m.get('match_id')} is {m.get('state')}")
        sk = sess.get("skins") or {}
        for g in sk.get("groups") or []:
            # a group nobody is entered in can never finish; it's flagged
            # on the board already and doesn't hold up the final result
            if g.get("entrants") and not g.get("complete"):
                out.append(f"{sess.get('id')} {g.get('label')}: skins still held")
    return out


def freeze_cup_results(db_path=None, force: bool = False) -> dict:
    """Snapshot the FINAL Cup (Kerry 2026-09-28: "go ahead and build the
    results snapshot"): points, every match, and the staff skins payouts,
    into the lsc_results app setting. Refuses while anything is still
    open unless forced (the blockers are stored with a forced snapshot).
    The board then serves the snapshot; clear_cup_results() goes back to
    live computing. No schema, no money moves: the payouts are a record
    for staff, paid (or not) elsewhere."""
    from datetime import datetime
    from email_parser.database import set_app_setting
    board = _board_payload(db_path, use_frozen=False)
    if not board.get("configured"):
        return {"frozen": False, "error": "no lsc_matches dial"}
    blockers = results_blockers(board)
    if blockers and not force:
        return {"frozen": False, "blockers": blockers}
    snap = {"event_id": board.get("event_id"),
            "frozen_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "forced": bool(blockers), "blockers": blockers,
            "board": {k: v for k, v in board.items()
                      if k not in ("configured", "board_live", "source")}}
    set_app_setting(RESULTS_KEY, json.dumps(snap, default=str), db_path=db_path)
    return {"frozen": True, "frozen_at": snap["frozen_at"],
            "forced": snap["forced"], "blockers": blockers,
            "cup": board.get("cup"), "teams": board.get("teams")}


def clear_cup_results(db_path=None) -> dict:
    from email_parser.database import set_app_setting
    set_app_setting(RESULTS_KEY, "", db_path=db_path)
    return {"frozen": False, "cleared": True}


def cup_results_status(db_path=None) -> dict:
    """Read-only: is a snapshot stored, and what the live board would
    freeze right now (its blockers and the dial check)."""
    from email_parser.database import _connect
    with _connect(db_path) as conn:
        res = _setting_json(conn, RESULTS_KEY)
    live = _board_payload(db_path, use_frozen=False)
    return {"snapshot": ({"frozen_at": res.get("frozen_at"),
                          "forced": res.get("forced"),
                          "blockers": res.get("blockers"),
                          "cup": (res.get("board") or {}).get("cup")}
                         if res else None),
            "live_cup": live.get("cup"),
            "live_blockers": results_blockers(live) if live.get("configured") else None,
            "dial_warnings": live.get("dial_warnings")}


# ---------------------------------------------------------------------------
# THE CUP'S PRINTED REPORTS (Kerry 10/8: "Reports aren't showing with the
# updated Lone Star Cup formatting"; design-claude #1467)
# ---------------------------------------------------------------------------

LSC_NAVY = "#002855"          # the logo's own navy (#1467 §2), not #002868
LSC_TEAM_COLORS = {"austin": "#BF5700", "sa": "#44596B"}   # as the cart signs (#1463)
NAVY_QR = "#002855"


def lsc_report_context(event_id: int, db_path=None) -> dict | None:
    """Is this event a Lone Star Cup round, and which? Read from data,
    never from the day (#1467 §1):
      * the Cup  = the event `lsc_matches.event_id` names;
      * PRACTICE = the event the Cup's `friday` add-on points at
        (`oneoff_charges[<cup>].addons[key=friday].event_id`).
    Returns {"kind": "cup"|"practice", "cup_event_id"} or None."""
    from email_parser.database import get_app_setting
    try:
        dial = json.loads(get_app_setting("lsc_matches", db_path=db_path) or "{}")
    except Exception:
        dial = {}
    cup = dial.get("event_id") if isinstance(dial, dict) else None
    if not cup:
        return None
    if int(cup) == int(event_id):
        return {"kind": "cup", "cup_event_id": int(cup)}
    try:
        cfg = json.loads(get_app_setting("oneoff_charges", db_path=db_path) or "{}").get(str(cup)) or {}
    except Exception:
        cfg = {}
    for a in cfg.get("addons") or []:
        if isinstance(a, dict) and a.get("key") == "friday" and a.get("event_id") \
                and int(a["event_id"]) == int(event_id):
            return {"kind": "practice", "cup_event_id": int(cup)}
    return None


def cup_print_groups(event_id: int, session_id: str | None = None, preview: bool = False,
                     db_path=None) -> dict:
    """The Cup's drawn matches as printable GROUPS, in the seat order the
    scorecard reads (#1467 §5, load-bearing):
      FOURBALL / FOURSOMES: one card per match, seats 1-2 Austin, 3-4 SA;
      SINGLES: two matches per card (the two that share a tee time),
               seats 1 & 2 = match 1, 3 & 4 = match 2, Austin first.
    Each player carries the LOCKED course handicap as PH (the same value
    the cup seed gives score entry) and his band from `lsc_tees`.
    ``preview`` reads the staff preview's demo dial instead of the live one.
    Returns {"groups", "gaps", "log", "sessions"}."""
    from email_parser.database import get_app_setting
    key = "lsc_preview_matches" if preview else "lsc_matches"
    gaps, log = [], []
    try:
        dial = json.loads(get_app_setting(key, db_path=db_path) or "{}")
        lock = (json.loads(get_app_setting("lsc_handicap_lock", db_path=db_path) or "{}")
                .get(str(event_id)) or {}).get("players") or {}
        tees = json.loads(get_app_setting("lsc_tees", db_path=db_path) or "{}").get(str(event_id)) or {}
    except Exception as e:  # noqa: BLE001
        return {"groups": [], "gaps": [f"The Cup dials don't read: {str(e)[:120]}"],
                "log": [], "sessions": []}
    band_of_tee = {str(v).lower(): k for k, v in (tees.get("bands") or {}).items()}
    tee_players = tees.get("players") or {}

    def _player(cid, side, seat):
        c = str(cid)
        lk = lock.get(c) or {}
        band = (tee_players.get(c) or {}).get("band") or band_of_tee.get(str(lk.get("tee") or "").lower())
        return {"customer_id": int(cid), "name": lk.get("name") or f"#{cid}", "team": side,
                "tee_choice": band or "", "playing_handicap": lk.get("ch"),
                "handicap_index_display": lk.get("index"), "cart_pos": seat}

    groups, sessions = [], []
    n = 0
    for s in dial.get("sessions") or []:
        sid = s.get("id")
        if session_id and sid != session_id:
            continue
        raw_fmt = (s.get("format") or "").strip()
        title = session_title(raw_fmt) if raw_fmt else None
        sessions.append({"id": sid, "title": title or sid, "matches": len(s.get("matches") or [])})
        if not s.get("matches"):
            log.append(f"{title or sid}: no matches drawn yet.")
            continue
        if not raw_fmt:
            gaps.append(f"LSC round has no format ({sid}).")
            continue
        fmt = normalize_format(raw_fmt)
        per_side = 1 if fmt == "singles" else 2
        bad = [m.get("id") for m in s["matches"]
               if len(m.get("austin") or []) != per_side or len(m.get("sa") or []) != per_side]
        if bad:
            gaps.append(f"{title}: match{'es' if len(bad) > 1 else ''} {', '.join(map(str, bad))} "
                        f"don't seat {per_side} Austin + {per_side} San Antonio; the card's seat "
                        "order would be wrong, so nothing prints.")
            continue
        if fmt == "singles":
            by_time: dict = {}
            for m in s["matches"]:
                by_time.setdefault(m.get("tee_time") or "", []).append(m)
            cards = []
            for tt, ms in by_time.items():
                for i in range(0, len(ms), 2):
                    cards.append((tt, ms[i:i + 2]))
        else:
            cards = [(m.get("tee_time") or "", [m]) for m in s["matches"]]
        for tt, ms in cards:
            n += 1
            players = []
            for mi, m in enumerate(ms):
                if fmt == "singles":
                    players += [_player(m["austin"][0], "austin", 2 * mi + 1),
                                _player(m["sa"][0], "sa", 2 * mi + 2)]
                else:
                    players += [_player(c, "austin", i + 1) for i, c in enumerate(m["austin"])]
                    players += [_player(c, "sa", i + 3) for i, c in enumerate(m["sa"])]
            groups.append({"group_num": n, "holes": str(s.get("n_holes") or 18),
                           "slot_label": tt, "players": players, "ggid": None,
                           "lsc_format": fmt, "lsc_title": title, "session": sid,
                           "date": s.get("date"), "match_ids": [m.get("id") for m in ms]})
    return {"groups": groups, "gaps": gaps, "log": log, "sessions": sessions}


def member_or_alumni(event_id: int, cids, db_path=None) -> set:
    """WHO PRINTS A CAPITAL LAST NAME on the Cup's pages (the #1481 §5D
    standard: members and alumni). The derived status
    (`derive_member_financial_status_bulk`), plus Kerry's roster ruling in
    the `lsc_member_ruling` dial: {"<cup event>": {"guests": [cid, ...]}},
    meaning every player in the Cup's handicap lock is a member or alumni
    except the guests named. Kerry 10/8: "BARSTOW, J JENKINS and WETZ are all
    either members or alumni and should be last name caps. Only player not
    either member or alumni is Walter Hogue" (some are dormant-DFW players
    with no membership on file). Works for the Cup and its practice round."""
    from email_parser import database as db
    cids = [int(c) for c in cids if c]
    out = set()
    if not cids:
        return out
    try:
        with db._connect(db_path) as conn:
            st = db.derive_member_financial_status_bulk(conn, cids)
        out = {c for c in cids if st.get(c) in ("member", "alumni")}
    except Exception:
        pass
    ctx = lsc_report_context(int(event_id), db_path=db_path)
    if not ctx:
        return out
    cup = str(ctx["cup_event_id"])
    try:
        ruling = (json.loads(db.get_app_setting("lsc_member_ruling", db_path=db_path) or "{}").get(cup)) or {}
        lock = ((json.loads(db.get_app_setting("lsc_handicap_lock", db_path=db_path) or "{}").get(cup)) or {}).get("players") or {}
    except (ValueError, TypeError):
        return out
    if "guests" in ruling:
        guests = {int(g) for g in ruling.get("guests") or []}
        out |= {c for c in cids if str(c) in lock and c not in guests}
    return out


def lsc_card_math(fmt: str, rows: list[dict]) -> list[dict]:
    """The handicap cell for one Cup card (#1467 §4/§5), from the engine's
    own allowance math (`session_handicaps`, so the card and the board
    cannot disagree). rows: [{"cid", "ph", "team", "seat"}] in seat order.
    Returns, per row, {"hcp", "off"} where hcp is the upper-left value
    (fourball 90% of PH, singles PH, foursomes the TEAM value on the
    team's first row) and off is strokes off the lowest in the match
    (never below 0). Singles is two matches: OFF within each pair."""
    fmt = normalize_format(fmt)
    out = [{"hcp": None, "off": None} for _ in rows]
    phs = {r["cid"]: r["ph"] for r in rows}
    if any(r["ph"] is None for r in rows):
        return out
    if fmt == "singles":
        for i in range(0, len(rows), 2):
            pair = rows[i:i + 2]
            h = session_handicaps("singles", [[r["cid"]] for r in pair], phs)
            low = min(h.values())
            for j, r in enumerate(pair):
                out[i + j] = {"hcp": h[r["cid"]], "off": max(0, h[r["cid"]] - low)}
        return out
    teams = [[r["cid"] for r in rows if r["team"] == t] for t in TEAM_KEYS]
    teams = [t for t in teams if t]
    h = session_handicaps(fmt, teams, phs)
    if fmt == "chapman":
        vals = {i: h[f"team:{i}"] for i in range(len(teams))}
        low = min(vals.values())
        for i, t in enumerate(teams):
            for c in t:
                k = next(j for j, r in enumerate(rows) if r["cid"] == c)
                out[k] = {"hcp": vals[i], "off": max(0, vals[i] - low)}
        return out
    low = min(h.values())
    return [{"hcp": h[r["cid"]], "off": max(0, h[r["cid"]] - low)} for r in rows]


def practice_cart_signs(event_id: int, db_path=None) -> dict:
    """The Friday PRACTICE ROUND's cart signs in the Cup's design 3e
    (design-claude #1463, templates/cup_cart_signs.html). Kerry 10/8, on
    the TGF-layout sign with the Cup logo swapped in: "This isn't like what
    we designed at all". Read from the SAVED pairings (the practice round
    has no draw): one sign per cart, seats 1-2 = cart A, 3-4 = cart B, the
    team band from each rider's Cup team (`lsc_handicap_lock`), names from
    customers by customer_id. A cart whose riders are on different teams,
    or a rider with no Cup team, is named in `problems` and doesn't print:
    the band would be wrong. QR as the regular sign: only when the event is
    in score entry and the QR dial names the group.
    Returns the shape `cup_cart_signs.html` reads."""
    import re as _re
    from email_parser.database import (get_app_setting, get_connection,
                                       get_event_print_pack)
    pack = get_event_print_pack(int(event_id), db_path=db_path)
    if not pack:
        return {"error": "Event not found"}
    ctx = lsc_report_context(int(event_id), db_path=db_path) or {}
    cup = ctx.get("cup_event_id")
    try:
        lock = (json.loads(get_app_setting("lsc_handicap_lock", db_path=db_path) or "{}")
                .get(str(cup)) or {}).get("players") or {}
    except Exception:
        lock = {}
    qr_on = False
    try:
        from email_parser.score_entry import attach_cart_sign_qr, event_enabled, _qr_dial
        qr_on = bool(event_enabled(int(event_id), db_path) and _qr_dial(int(event_id), db_path))
        attach_cart_sign_qr(pack, db_path=db_path)
    except Exception:
        qr_on = False
    cids = {int(p["customer_id"]) for g in pack["groups"] for p in g["players"] if p.get("customer_id")}
    names: dict = {}
    if cids:
        conn = get_connection(db_path) if db_path else get_connection()
        try:
            q = ",".join("?" * len(cids))
            for r in conn.execute(f"SELECT customer_id, first_name, last_name FROM customers "
                                  f"WHERE customer_id IN ({q})", tuple(cids)):
                names[r[0]] = ((r[1] or "").strip(), (r[2] or "").strip())
        finally:
            conn.close()
    shotgun = str((pack.get("event") or {}).get("start_type") or "").lower().startswith("shotgun")
    signs, problems = [], []
    for g in pack["groups"]:
        slot = _re.sub(r"^HOLE\s+", "", g.get("slot_label") or "", flags=_re.I)
        tee_time = (pack["event"].get("start_clock") or "") if shotgun else slot
        hole = slot if shotgun else "1"
        # the navy QR, as the Cup's own signs (Kerry 10/8: "make the black
        # text the LSC navy as well as the QR code")
        _url = (g.get("score_qr") or {}).get("url")
        try:
            from email_parser.score_entry import qr_svg as _qr
            qr = _qr(_url, dark=NAVY_QR) if _url else None
        except Exception:
            qr = (g.get("score_qr") or {}).get("svg")
        players = sorted(g["players"], key=lambda p: p.get("cart_pos") or 0)
        for lo, hi in ((1, 2), (3, 4)):
            riders = [p for p in players if lo <= (p.get("cart_pos") or 0) <= hi]
            if not riders:
                continue
            teams = {(lock.get(str(p.get("customer_id"))) or {}).get("team") for p in riders}
            label = f"group {g.get('group_num')} cart {'A' if lo == 1 else 'B'}"
            if None in teams or len(teams) != 1:
                problems.append(f"{label}: riders' Cup teams are {sorted(t or 'none' for t in teams)}; "
                                "the team band would be wrong, so this sign doesn't print.")
                continue
            side = teams.pop()
            color = LSC_TEAM_COLORS.get(side)
            if not color:
                problems.append(f"{label}: no team colour for {side}.")
                continue
            rows = []
            for p in riders:
                f, l = names.get(int(p["customer_id"]), ("", "")) if p.get("customer_id") else ("", "")
                if not (f or l):
                    parts = (p.get("name") or "").split()
                    f, l = (" ".join(parts[:-1]), parts[-1]) if len(parts) > 1 else ("", p.get("name") or "")
                rows.append({"first": f, "last": l.upper()})
            signs.append({"team": "AUSTIN" if side == "austin" else "SAN ANTONIO", "color": color,
                          "riders": rows, "tee_time": tee_time, "hole": hole, "qr_svg": qr,
                          "session": "practice", "match": "PRACTICE ROUND"})
    return {"event": pack["event"], "pages": [signs[i:i + 2] for i in range(0, len(signs), 2)],
            "count": len(signs), "preview": False, "qr_on": qr_on, "problems": problems,
            "empty_note": "No saved pairings yet, so there are no cart signs. Save PAIRINGS first."}


def cup_round_pack(event_id: int, session_id: str, preview: bool = False, db_path=None) -> dict | None:
    """ONE ROUND'S STARTER SHEET, filled from THE DRAW (Kerry 10/8: "we'll
    have different pairings for each round on different tee times. Of course
    those will be determined tonight at THE DRAW and autopopulate, but it
    needs to have a place to autopopulate that then feeds into all the
    reports."). The place is the round's session in `lsc_matches` (the draw
    page writes it); this shapes it as the Starter Sheet's pack: one group
    per card (the scorecard's grouping), tee time, seats in the
    load-bearing order, team colour, band, the locked index and course
    handicap. The tee legend and logo come from the event's own pack."""
    from email_parser.database import get_event_print_pack
    base = get_event_print_pack(int(event_id), db_path=db_path)
    if not base:
        return None
    cg = cup_print_groups(int(event_id), session_id=session_id, preview=preview, db_path=db_path)
    bands = {str(t.get("band")).lower(): t.get("band") for t in base.get("tee_legend") or []}
    sess = next((s for s in cg["sessions"] if s["id"] == session_id), None)
    title = (sess or {}).get("title") or session_id
    groups, alpha = [], []
    for g in cg["groups"]:
        players = []
        for p in g["players"]:
            band = bands.get(str(p.get("tee_choice") or "").lower(), p.get("tee_choice"))
            last = (p["name"].split() or [""])[-1]
            first = " ".join(p["name"].split()[:-1])
            row = {"name": p["name"], "customer_id": p["customer_id"], "cart_pos": p["cart_pos"],
                   "tee_choice": band, "handicap_index": p.get("handicap_index_display"),
                   "handicap_index_display": p.get("handicap_index_display"),
                   "playing_handicap": p.get("playing_handicap"), "team_handicap": None,
                   "team_allowed": None, "course_handicap_raw": None,
                   "is_new": False, "is_first_timer": False,
                   "team": p.get("team"), "team_color": LSC_TEAM_COLORS.get(p.get("team") or "")}
            players.append(row)
            alpha.append({**row, "sort_name": f"{last}, {first}".strip().strip(","),
                          "slot_label": g["slot_label"], "slot_short": g["slot_label"],
                          "group_num": g["group_num"], "holes": g["holes"],
                          "cart": "A" if (p["cart_pos"] or 0) <= 2 else "B"})
        groups.append({"group_num": g["group_num"], "holes": g["holes"], "slot_label": g["slot_label"],
                       "start_line": f"{g['slot_label']} · {' + '.join(m for m in g['match_ids'] if m)}",
                       "players": players, "ggid": None, "blinds": []})
    alpha.sort(key=lambda r: r["sort_name"].lower())
    ev = dict(base["event"])
    ev.update({"item_name": f"LONE STAR CUP · {title}", "event_date": (sess and next(
        (g["date"] for g in cg["groups"] if g.get("date")), None)) or ev.get("event_date"),
        "format": "18 Holes", "start_type": "Tee Times",
        "start_label": f"First tee {groups[0]['slot_label']}" if groups else None,
        "start_label_18": None})
    from email_parser.database import _connect, report_heading
    with _connect(db_path) as _c:
        _evr = dict(_c.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone())
    heading = report_heading(_evr, title=title, date=ev.get("event_date"), db_path=db_path)
    return {**base, "event": ev, "groups": groups, "group_count": len(groups), "alpha": alpha,
            "heading": heading,
            "player_count": len(alpha), "games_off": True, "ph_note": "",
            "ph_basis": "the Cup's LOCKED course handicap (lsc_handicap_lock)",
            "lsc_round": {"id": session_id, "title": title, "gaps": cg["gaps"], "log": cg["log"],
                          "preview": bool(preview)}}


def cup_round_cart_signs(event_id: int, session_id: str | None, db_path=None) -> list:
    """Cart signs straight from THE DRAW, for a round the Cup seed hasn't
    reached yet (no scorer QR until it has). Same sign shape as
    `cup_cart_signs_data`: one per side per card."""
    cg = cup_print_groups(int(event_id), session_id=session_id, db_path=db_path)
    labels = {"austin": "AUSTIN", "sa": "SAN ANTONIO"}
    signs = []
    for g in cg["groups"]:
        for side in TEAM_KEYS:
            riders = [p for p in g["players"] if p.get("team") == side]
            if not riders:
                continue
            rows = []
            for p in riders:
                parts = (p.get("name") or "").split()
                rows.append({"first": " ".join(parts[:-1]), "last": (parts[-1] if parts else "").upper()})
            signs.append({"team": labels[side], "color": LSC_TEAM_COLORS[side], "riders": rows,
                          "tee_time": g["slot_label"], "hole": "1", "qr_svg": None,
                          "session": g.get("session"), "match": g.get("lsc_title")})
    return signs
