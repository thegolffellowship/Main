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
               "format": "singles"|"fourball"|"foursomes",
               "se_round": null, "n_holes": 18,
               "matches": [{"id": "SAT-AM-1", "tee_time": "8:30",
                            "austin": [cid, ...], "sa": [cid, ...]}]}]}

The weekend format is already ratified in the LSC How-It-Works popup
(contests.html): Sat AM Fourball, Sat PM Foursomes, Sun Singles.
Points (Kerry, CA #717): 1 for a win, 1/2 for a halve, every format;
level points = the defending champion keeps the cup. Skins replace
CTP and are scored separately from the match (compute_skins); their
basis, pot and carryover are still Kerry's to rule.
Handicapping (still PENDING Kerry, CA #717): full difference of LOCKED
playing handicaps off the match's low man on the lowest stroke-index
holes; four-ball plays everyone off the low man of all four; the team
format holds 50% of the combined difference until Kerry confirms it
is Greensomes (60% of the low + 40% of the high). Playing handicaps
come from Track A's payload (the locked snapshot), never re-derived.

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
                         marks: dict | None = None) -> dict:
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

    picked = {c: {int(h) for h, m in ((marks or {}).get(c) or (marks or {}).get(str(c)) or {}).items()
                  if m == "picked_up"}
              for c in everyone}
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
                          "p1_picked_up": pu1, "p2_picked_up": pu2,
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
                  carryover: bool = False) -> dict:
    """Skins for one session, a calculation SEPARATE from the match
    (Kerry, CA #717). It reads raw scores only, never the match state, so
    holes played after a match is decided count here and nothing here
    can change a match result.

    - Team sessions (fourball, foursomes) play TEAM skins: each side of
      each match is one entry, across the whole session. Singles play
      INDIVIDUAL skins: every player is an entry.
    - basis "net" | "gross". Kerry has not ruled which (CA #717), so the
      board only calls this once the dial names one. Net strokes are the
      full LOCKED playing handicap off zero on the stroke-index holes
      (skins are a field game, not off the low man); a plus handicap
      gets nothing on a hole, per the plus rule (it comes off the round,
      never a hole). Foursomes use the team ball with the allowance the
      engine holds (50% of combined) until Kerry confirms Greensomes.
    - A picked-up ball never wins a skin.
    - A hole is decided only when EVERY entry has posted it (the money
      hold: no win shows before the field is in); until then "pending".
    - One lowest score wins the skin. A tie wins nothing, and carries the
      skin to the next hole only when carryover is on (unruled, so off).
    """
    names = names or {}
    marks = marks or {}
    fmt = (session.get("format") or "singles").strip().lower()
    n_holes = int(session.get("n_holes") or 18)
    team_game = fmt in ("fourball", "foursomes")

    entries = []
    for m in session.get("matches") or []:
        for side in TEAM_KEYS:
            cids = [int(c) for c in (m.get(side) or [])]
            if not cids:
                continue
            if team_game:
                entries.append({"key": f"{m.get('id')}:{side}",
                                "team": side, "cids": cids})
            else:
                for c in cids:
                    entries.append({"key": f"{m.get('id')}:{side}:{c}",
                                    "team": side, "cids": [c]})
    for e in entries:
        e["label"] = " / ".join(names.get(c) or names.get(str(c)) or f"#{c}"
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
        if fmt == "foursomes":
            team_ph = sum(phs.get(c) or phs.get(str(c)) or 0
                          for c in e["cids"]) * 0.5
            smap = strokes_received(team_ph, 0, course, n_holes)
            return {c: smap for c in e["cids"]}
        return {c: strokes_received(phs.get(c) or phs.get(str(c)) or 0, 0,
                                    course, n_holes)
                for c in e["cids"]}

    strokes = {e["key"]: _strokes_for(e) for e in entries}
    totals = {e["key"]: 0 for e in entries}
    holes_out = []
    carry = 0
    for hn in _hole_numbers(course, n_holes):
        posted_all = True
        best_by_entry = {}
        for e in entries:
            posted = False
            best = None
            for c in e["cids"]:
                g = sc.get(c, {}).get(hn)
                if g is None:
                    continue
                posted = True
                if hn in picked.get(c, set()):
                    continue            # a picked-up ball can't win a skin
                v = g - strokes[e["key"]].get(c, {}).get(hn, 0)
                if best is None or v < best:
                    best = v
            if not posted:
                posted_all = False
            best_by_entry[e["key"]] = best
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
    return {"kind": "team" if team_game else "individual",
            "basis": basis, "carryover": bool(carryover),
            "carried": carry, "holes": holes_out, "totals": board}


def compute_board(dial: dict, session_data: dict,
                  names: dict | None = None) -> dict:
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
    skins_cfg = dial.get("skins") or {}
    skins_basis = skins_cfg.get("basis")
    skins_on = skins_basis in ("net", "gross")
    board = {"event_id": dial.get("event_id"),
             "teams": {"austin": {"points": 0.0, "projected": 0.0},
                       "sa": {"points": 0.0, "projected": 0.0}},
             "points_win": win, "points_halve": halve,
             "skins_pending": not skins_on,
             "sessions": []}
    total = 0.0
    for sess in dial.get("sessions") or []:
        data = (session_data or {}).get(sess.get("id")) or {}
        course = data.get("course") or []
        phs = {int(k): v for k, v in (data.get("phs") or {}).items()}
        scores = {int(k): v for k, v in (data.get("scores") or {}).items()}
        marks = {int(k): v for k, v in (data.get("marks") or {}).items()}
        s_out = {"id": sess.get("id"), "label": sess.get("label"),
                 "date": sess.get("date"), "format": sess.get("format"),
                 "points_per_match": win, "matches": [], "skins": None}
        for m in sess.get("matches") or []:
            total += win
            detail = compute_match_detail(m, sess, course, phs, scores, names, marks)
            state = _match_state(detail)
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
        if skins_on and scores:
            s_out["skins"] = compute_skins(
                sess, course, phs, scores, marks, names, basis=skins_basis,
                carryover=bool(skins_cfg.get("carryover")))
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
        out[sess.get("id")] = {"course": r.get("course") or [],
                               "phs": phs, "scores": scores, "marks": marks}
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
        # Real entered scores (Track A, live on main v2.493.0) take
        # precedence per session: any session bound via se_round reads
        # the rounds-plural event feed; unbound sessions keep the mock
        # dial (staging) or stay empty (upcoming).
        entry_used = False
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
            except Exception:
                logger.exception("lsc_cup: entered-scores feed read "
                                 "failed — board falls back to the "
                                 "mock dial")
        board = compute_board(dial, session_data, names)
        board["configured"] = True
        board["source"] = ("entry" if entry_used
                           else "mock" if session_data else "none")
        # Rule 3b: the member page shows the board only once Kerry flips
        # board_live in the dial (after his phone OK). Admin/manager
        # sessions preview it regardless — the route enforces this.
        board["board_live"] = bool(dial.get("board_live"))
        return board
