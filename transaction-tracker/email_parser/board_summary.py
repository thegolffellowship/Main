"""EVENTS BOARD: state, SUMMARY, projected WON, pots, Match Play (Kerry
2026-10-19, leaderboard review sections 12-13, build items B10-B12).

Everything here READS. Nothing records a payout, nothing writes a row. It
decorates the payload `get_event_leaderboard` already built, at the API
boundary (`attach`), so the board's own numbers are never computed twice.

- `board_state`: UPCOMING / LIVE / IN REVIEW / FINAL, the four words of 12.1.
  FINAL = closeout fired: payouts recorded for the event, or the auto-payouts
  preview says every card is final. A hold keeps it at IN REVIEW.
- `projected_money` (B11): while LIVE, what each player would win if play
  ended now. The SAME assembly the auto-payouts preview runs
  (`assemble_event_game_payouts`, here with projected=True: the engine on the
  live entered cards, the board's own teams and CTP holders, the points
  leader for City MVP), resolved to customer_id the way the preview is
  (`auto_payouts._with_ids`). Display only; the board marks it PROJ.
- `game_pots` (B11): each game's pot per flight, read off the flight board's
  AMOUNTS layer (the GAMES tab's numbers) and the live matrix for Team / CTP.
- `event_matches` (B12): City Match Play matches tied to this event by
  `cmp_matches.event_id` / `cmp_bracket.event_id`, in the shape the standard
  match-play cards (`mpMatchCardFromMatch`) read.
"""
from __future__ import annotations

import json
import logging
import threading
import time

logger = logging.getLogger(__name__)

# projected money is recomputed only when a score moves (the score-entry
# version bumps on every score, unlock and CTP ruling); a board polled by a
# hundred phones collapses to one engine run per change
_PROJ_CACHE: dict = {}
_PROJ_LOCK = threading.Lock()
_PROJ_TTL_S = 120.0

TAB_CATS = {
    # Money only on its own game's tab (Kerry 10/19): the categories each
    # tab owns. Mirrors EVLB_GAME_CATS in contests.html.
    "team": ("team_net",),
    "points": ("mvp", "tgf_mvp"),
    "net": ("individual_net",),
    "gross": ("individual_gross",),
    "skins": ("skins",),
    "prox": ("ctp", "closest_to_pin", "longest_putt", "hole_in_one"),
}


def board_state(lb: dict, recorded: int = 0, preview_final: bool = False) -> str:
    """The board's player-facing word (12.1): upcoming | live | in_review | final."""
    if not lb:
        return "upcoming"
    if not lb.get("field") and not lb.get("holes_posted"):
        return "upcoming"
    if lb.get("field_complete") is False:
        return "live"
    if recorded > 0 or preview_final:
        return "final"
    return "in_review"


def _recorded_count(conn, event_name: str) -> int:
    try:
        r = conn.execute(
            """SELECT COUNT(*) AS n FROM tgf_payouts p
               JOIN tgf_events te ON te.id = p.event_id
               WHERE lower(trim(te.code)) = lower(trim(?))""",
            (event_name or "",)).fetchone()
        return int(r["n"] or 0) if r else 0
    except Exception:
        return 0


def projected_money(lb: dict, db_path=None) -> dict | None:
    """{rows, by_cid: {cid: {cat: dollars}}, teams: [{index, purse,
    slots: {rid: dollars}}], total, notes} or None when there is nothing to
    project (no entered cards). The rows are exactly what the auto-payouts
    preview would hold if the field were in now."""
    from email_parser import database as db
    from email_parser import auto_payouts as ap
    from email_parser import score_entry as se
    ev = (lb or {}).get("event") or {}
    eid, name = ev.get("id"), ev.get("name")
    if not eid or not name:
        return None
    try:
        version = se.event_version(int(eid), db_path=db_path)
    except Exception:
        version = None
    key = (str(db_path), int(eid))
    now = time.monotonic()
    with _PROJ_LOCK:
        hit = _PROJ_CACHE.get(key)
        if hit and hit["v"] == version and now - hit["at"] < _PROJ_TTL_S:
            return hit["out"]
    try:
        asm = db.assemble_event_game_payouts(name, db_path=db_path,
                                             projected=True, lb=lb)
    except Exception:
        logger.exception("projected money failed for %s", name)
        return None
    if asm.get("error"):
        return {"rows": [], "by_cid": {}, "teams": [], "total": 0.0,
                "notes": [asm["error"]]}
    try:
        read = se.get_entered_scores(int(eid), db_path=db_path)
    except Exception:
        read = {}
    rows = ap._with_ids(asm.get("rows") or [], read, db_path)
    out = shape_projection(lb, rows)
    out["notes"] = asm.get("notes") or []
    with _PROJ_LOCK:
        _PROJ_CACHE[key] = {"v": version, "at": now, "out": out}
    return out


def shape_projection(lb: dict, rows: list) -> dict:
    """Preview-shaped rows -> what the board reads: per-customer money by
    category, and each team's purse + per-slot shares through the SAME
    slot rule the recorded money uses (`team_slot_money`)."""
    import copy
    from email_parser.database import team_slot_money
    by_cid: dict = {}
    won: dict = {}
    for r in rows:
        cid, amt = r.get("customer_id"), float(r.get("amount") or 0)
        if not cid or amt <= 0:
            continue
        cat = r.get("category") or "other"
        m = by_cid.setdefault(str(int(cid)), {})
        m[cat] = round(m.get(cat, 0.0) + amt, 2)
        won.setdefault(int(cid), []).append({"category": cat, "cents": round(amt * 100)})
    teams_out = []
    teams = copy.deepcopy((lb or {}).get("teams") or [])
    if teams:
        try:
            team_slot_money(teams, won)
        except Exception:
            logger.exception("projected team slots failed")
        for i, t in enumerate(teams):
            slots = {str(p.get("scoring_round_id")): p.get("team_won")
                     for p in t.get("players") or []
                     if p.get("team_won")}
            if t.get("purse") or slots:
                teams_out.append({"index": i, "purse": t.get("purse"), "slots": slots})
    return {"rows": rows, "by_cid": by_cid, "teams": teams_out,
            "total": round(sum(float(r.get("amount") or 0) for r in rows), 2)}


def game_pots(lb: dict, db_path=None) -> dict:
    """{net|gross|skins: {total, bonus, bonus_label, flights: [{flight_no,
    players, pot, places: [amount]}]}, team: {total, places}, prox: {total,
    each}}. Read from the flight board's AMOUNTS (the GAMES tab's numbers)
    and the live matrix — never recomputed from scores."""
    from email_parser import database as db
    out: dict = {}
    ev = (lb or {}).get("event") or {}
    eid = ev.get("id")
    if not eid or (lb or {}).get("no_games"):
        return out
    tab = {"individual_net": "net", "individual_gross": "gross", "skins": "skins"}
    try:
        fb = db.event_flights_board(int(eid), db_path=db_path) or {}
    except Exception:
        logger.exception("pots: flight board unavailable for %s", eid)
        fb = {}
    for entry in fb.get("games") or []:
        k = tab.get(entry.get("game"))
        am = entry.get("amounts") or {}
        if not k or not entry.get("active") or not am:
            continue
        out[k] = {
            "total": round(float(am.get("total_pot") or 0), 2),
            "bonus": round(float(am.get("bonus") or 0), 2),
            "bonus_label": am.get("bonus_label"),
            "flights": [{"flight_no": f.get("flight_no"),
                         "players": f.get("players"),
                         "pot": round(float(f.get("pot") or 0), 2),
                         "places": [round(float(p.get("amount") or 0), 2)
                                    for p in f.get("places") or []]}
                        for f in am.get("flights") or []],
        }
    try:
        m9, m18 = db._load_games_matrix(db_path=db_path)
        with db._connect(db_path) as conn:
            counts = db._event_player_counts(conn, ev.get("name") or "")
        mat = m9 if int(ev.get("holes") or 9) == 9 else m18
        g = mat.get(str(counts.get("players"))) or {}
        places = [a for a in (db._matrix_num(g.get("team1st")),
                              db._matrix_num(g.get("team2nd"))) if a > 0]
        if places and g.get("teamTotal") not in (None, "NO_EVENT"):
            out["team"] = {"total": round(sum(places), 2), "places": places}
        ctp = [v for v in (db._matrix_num(g.get(f"ctp{i}")) for i in range(1, 5)) if v > 0]
        if ctp:
            out["prox"] = {"total": round(sum(ctp), 2), "each": ctp}
    except Exception:
        logger.exception("pots: matrix unavailable for %s", eid)
    return out


def event_matches(event_id: int, db_path=None) -> list:
    """City Match Play matches played at this event, read-only, in the
    `cmp_get_matches` row shape (pool matches) plus the knockout pairs from
    `cmp_bracket` folded into the same shape. The link is the match row's
    own `event_id`; a bracket row with no event_id is matched the way
    `cmp_get_bracket` self-heals it (the hardened GG detail's event code)."""
    from email_parser import database as db
    out: list = []
    with db._connect(db_path) as conn:
        ev = conn.execute("SELECT id, item_name, event_date FROM events WHERE id = ?",
                          (int(event_id),)).fetchone()
        if not ev:
            return out
        _pc: dict = {}
        try:
            for r in conn.execute(
                    """SELECT m.*, p.chapter AS chapter, p.pool_name AS pool_name
                         FROM cmp_matches m
                         LEFT JOIN cmp_pools p ON p.id = m.pool_id
                        WHERE m.event_id = ? ORDER BY m.id""", (int(event_id),)):
                m = dict(r)
                m["event_name"], m["event_date_val"] = ev["item_name"], ev["event_date"]
                m["hole_pars"] = db._cmp_hole_pars_for_event(conn, ev["id"], _pc)
                m["kind"] = "pool"
                out.append(m)
        except Exception:
            logger.exception("event matches: pool read failed for %s", event_id)
        try:
            code = (ev["item_name"] or "").split(" ")[0].lower()
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM cmp_bracket ORDER BY season, chapter, round, slot")]
            mine = []
            for b in rows:
                link = b.get("event_id")
                if not link and b.get("gg_match_detail") and code:
                    try:
                        det = json.loads(b["gg_match_detail"]) \
                            if isinstance(b["gg_match_detail"], str) else (b["gg_match_detail"] or {})
                        if (det.get("gg_event") or "").strip().lower() == code:
                            link = ev["id"]
                    except Exception:
                        pass
                if link == ev["id"]:
                    mine.append(b)
            # a knockout match is the odd slot + the next even slot
            by = {(b["season"], b["chapter"], b["round"], int(b["slot"])): b for b in mine}
            seen = set()
            for (s, c, rd, sl), b in sorted(by.items()):
                base = sl if sl % 2 else sl - 1
                k = (s, c, rd, base)
                if k in seen:
                    continue
                seen.add(k)
                a = by.get((s, c, rd, base)) or b
                z = by.get((s, c, rd, base + 1))
                p1 = a.get("player_name")
                p2 = (z or {}).get("player_name") or a.get("opponent_name")
                if not p1 or not p2:
                    continue
                win = a.get("winner_name") or (z or {}).get("winner_name")
                det = (z or {}).get("gg_match_detail") or a.get("gg_match_detail")
                out.append({
                    "kind": "knockout", "chapter": c, "pool_name": rd,
                    "player1_name": p1, "player2_name": p2,
                    "winner_name": win,
                    "margin": a.get("margin") or (z or {}).get("margin"),
                    "played_at": "1" if win else None,
                    "gg_match_detail": det,
                    "event_name": ev["item_name"], "event_date_val": ev["event_date"],
                    "hole_pars": db._cmp_hole_pars_for_event(conn, ev["id"], _pc),
                })
        except Exception:
            logger.exception("event matches: bracket read failed for %s", event_id)
    return out


def attach(lb: dict, db_path=None) -> dict:
    """Decorate one event's board payload (in place, and returned) with
    board_state, projected (LIVE only), pots and match_play."""
    if not lb or not isinstance(lb, dict):
        return lb
    from email_parser import database as db
    ev = lb.get("event") or {}
    recorded, preview_final = 0, False
    try:
        with db._connect(db_path) as conn:
            recorded = _recorded_count(conn, ev.get("name") or "")
    except Exception:
        recorded = 0
    try:
        from email_parser import auto_payouts as ap
        pv = ap.preview_for(ev.get("id"), db_path) if ev.get("id") else None
        preview_final = bool(pv and pv.get("final"))
    except Exception:
        preview_final = False
    # ONE state value (R2, design-claude #2147; pain point 1): the board
    # payload already carries it from database.evlb_state, the same rule
    # the strip, the list chip and the tab landing read. Recomputing it
    # here is how a LIVE-coloured strip could read UPCOMING, or a held
    # board turn FINAL. Only a payload without one falls back.
    state = lb.get("board_state") or board_state(lb, recorded, preview_final)
    lb["board_state"] = state
    lb["money_recorded"] = recorded > 0
    lb["projected"] = None
    if (state == "live" and ev.get("score_source") == "entry"
            and not lb.get("no_games")):
        lb["projected"] = projected_money(lb, db_path)
    try:
        lb["pots"] = game_pots(lb, db_path)
    except Exception:
        logger.exception("pots failed for %s", ev.get("name"))
        lb["pots"] = {}
    try:
        lb["match_play"] = event_matches(ev["id"], db_path) if ev.get("id") else []
    except Exception:
        logger.exception("match play failed for %s", ev.get("name"))
        lb["match_play"] = []
    return lb
