"""LONE STAR CUP STAFF PREVIEW (Kerry 2026-10-07, CoS #1398-B): "populate it
with scores thru a certain portion just so I can see it all and interact with
it."

Everything here lives on its OWN dial (`lsc_preview_matches`) and its OWN
score-entry rounds, labelled PREVIEW and keyed `lscprev:<session>`:
- the live dial (`lsc_matches`) and the live session rounds (`lsc:<session>`)
  are never read or written;
- PREVIEW rounds never publish to the scoring record (entry_publish) and never
  put an event in entry mode (Finding 0);
- the member board never reads this dial (lsc_board_payload stays on
  `lsc_matches`); staff read it through preview_board_payload.

Demo state (#1398-B): FOURBALL all 7 matches final with full cards (one
picked-up hole, one hole where every ball is picked up); FOURSOMES 7 matches
live through holes 9-13; SINGLES not started (tee times shown). Pairs, pools
and tee sheet come from the live dial's REAL blocks; handicaps from the lock.

`teardown` closes the PREVIEW rounds and clears the demo dial. Nothing is
sent, paid or deleted.
"""
from __future__ import annotations

import json
import logging
import random

from email_parser import score_entry as se

logger = logging.getLogger(__name__)

EVENT_ID = 3329
DIAL = se.PREVIEW_DIAL
KEY_PREFIX = "lscprev:"
DEVICE = "lsc-preview-seed"
TITLES = {"sat-am": "FOURBALL", "sat-pm": "FOURSOMES", "sun": "SINGLES"}


def _setting(key, db_path=None) -> dict:
    from email_parser.database import get_app_setting
    try:
        raw = get_app_setting(key, db_path=db_path) or ""
        return json.loads(raw) if raw.strip() else {}
    except (ValueError, TypeError):
        return {}


def _hhmm(t: str, pm: bool) -> str:
    t = str(t or "").strip()
    if not t or "M" in t.upper():
        return t
    return f"{t} {'PM' if pm else 'AM'}"


def build_dial(event_id: int = EVENT_ID, db_path=None) -> dict:
    """The demo dial from the live dial's real pairs + tee sheet: Saturday
    pair i v pair i inside each pool (low 3, high 4) in tee order; Sunday
    each team's 14 players by locked CH, low 7 v low 7 and high 7 v high 7,
    two singles matches per tee time."""
    live = _setting("lsc_matches", db_path)
    if int(live.get("event_id") or 0) != int(event_id):
        return {"error": "lsc_matches is not set for this event"}
    pairs = live.get("pairs") or {}
    tee = live.get("tee_sheet") or {}
    lock = ((_setting("lsc_handicap_lock", db_path).get(str(event_id)) or {}).get("players") or {})

    def pool(team, which):
        return sorted([p for p in pairs.get(team) or [] if p.get("pool") == which],
                      key=lambda p: (p.get("combined_ch") or 0, p.get("id")))
    sat = []
    for which in ("low", "high"):
        sat += list(zip(pool("austin", which), pool("sa", which)))
    def sess(sid, fmt, date, pm, matches):
        return {"id": sid, "label": TITLES[sid], "date": date, "format": fmt,
                "points_per_match": 1, "n_holes": 18, "se_round": None, "matches": matches}
    am = [{"id": f"PV-AM-{i}", "tee_time": _hhmm((tee.get("sat-am") or [""] * 7)[i - 1], False),
           "austin": a["cids"], "sa": s["cids"]} for i, (a, s) in enumerate(sat, 1)]
    pmm = [{"id": f"PV-PM-{i}", "tee_time": _hhmm((tee.get("sat-pm") or [""] * 7)[i - 1], True),
            "austin": a["cids"], "sa": s["cids"]} for i, (a, s) in enumerate(sat, 1)]

    def by_ch(team):
        cids = [c for p in pairs.get(team) or [] for c in p.get("cids") or []]
        return sorted(cids, key=lambda c: ((lock.get(str(c)) or {}).get("ch") or 99, c))
    au, sa = by_ch("austin"), by_ch("sa")
    sun_t = tee.get("sun") or [""] * 7
    sun = [{"id": f"PV-SUN-{i + 1}", "tee_time": _hhmm(sun_t[min(i // 2, len(sun_t) - 1)], False),
            "austin": [a], "sa": [s]} for i, (a, s) in enumerate(zip(au, sa))]
    return {"event_id": event_id, "preview": True, "board_live": False,
            "defending_champion": live.get("defending_champion"),
            "halved_match": live.get("halved_match", 0.5),
            "skins": live.get("skins"), "pairs": pairs, "tee_sheet": tee,
            "_note": "STAFF PREVIEW demo dial (CoS #1398-B). Not the live Cup; torn down before Saturday.",
            "sessions": [sess("sat-am", "fourball", "2026-10-10", False, am),
                         sess("sat-pm", "chapman", "2026-10-10", True, pmm),
                         sess("sun", "singles", "2026-10-11", False, sun)]}


def _card(rng, pars, quality):
    out = {}
    for h, par in pars.items():
        r = rng.random()
        d = -1 if r < 0.08 * quality else 0 if r < 0.55 + 0.1 * quality else 1 if r < 0.9 else 2
        out[h] = max(par - 1, min(par + 3, par + d))
    return out


def _close_two_and_one(event_id, match_id, gid, pars, db_path):
    """FOURSOMES match 1 closed out 2&1 (CoS #1398 seed state), whatever
    the team handicaps: both sides par through 17, then Austin's card is
    rewritten net of each hole's pops so Austin wins 1 and 2 and halves
    the rest. Pops come from the board's own match detail."""
    gc = se.get_group_card(gid, DEVICE, db_path=db_path)
    teams = gc.get("teams") or []
    if len(teams) < 2:
        return
    seventeen = {h: p for h, p in pars.items() if h <= 17}
    for t in teams:
        _write(gid, t["team_id"], seventeen, is_team=True, db_path=db_path)
    from email_parser import lsc_cup
    b = lsc_cup.preview_board_payload(db_path=db_path)
    m = next((m for s_ in b.get("sessions") or [] for m in s_.get("matches") or []
              if (m.get("match_id") or m.get("id")) == match_id), None)
    holes = {int(h["hole"]): h for h in ((m or {}).get("detail") or m or {}).get("holes") or []}
    aus = {}
    for h, par in seventeen.items():
        d = holes.get(h) or {}
        g = par + int(d.get("p1_pops") or 0) - int(d.get("p2_pops") or 0) - (1 if h <= 2 else 0)
        aus[h] = max(2, g)
    _write(gid, teams[0]["team_id"], aus, is_team=True, db_path=db_path, tag="r")


def _write(gid, cid_or_team, holes_scores, marks=None, is_team=False, db_path=None, tag=""):
    ops, n = [], 0
    for h, g in holes_scores.items():
        n += 1
        op = {"op_id": f"pv{tag}-{gid}-{cid_or_team}-{h}", "hole": int(h), "gross": int(g)}
        if marks and h in marks:
            op["mark"] = marks[h]
        op["team_id" if is_team else "customer_id"] = int(cid_or_team)
        ops.append(op)
    return se.write_scores(gid, DEVICE, None, ops, db_path=db_path)


def seed(event_id: int = EVENT_ID, apply: bool = False, db_path=None) -> dict:
    """Dry run by default. Apply: write the demo dial, seed PREVIEW rounds
    (cup_seed on the demo dial), bind them, write the demo scores."""
    from email_parser.database import set_app_setting
    dial = build_dial(event_id, db_path)
    if dial.get("error"):
        return dial
    plan = {"dry_run": not apply, "event_id": event_id,
            "sessions": [{"id": s["id"], "title": s["label"], "matches": len(s["matches"])}
                         for s in dial["sessions"]]}
    if not apply:
        return plan
    set_app_setting(DIAL, json.dumps(dial), db_path=db_path)
    res = se.cup_seed(event_id, apply=True, db_path=db_path, dial_key=DIAL,
                      round_key_prefix=KEY_PREFIX, label_prefix=se.PREVIEW_LABEL)
    if res.get("error") or res.get("gaps", {}).get("not_a_customer"):
        return {**plan, "error": res.get("error") or "seed gaps", "seed": res}
    rid_of = {s["session"]: s.get("round_id") for s in res.get("sessions") or []}
    for s in dial["sessions"]:
        s["se_round"] = rid_of.get(s["id"])
    set_app_setting(DIAL, json.dumps(dial), db_path=db_path)
    rng = random.Random(1010)
    out_rounds = {}
    for s in dial["sessions"]:
        rid = s["se_round"]
        out_rounds[s["label"]] = rid
        if s["id"] == "sun" or not rid:
            continue                                  # SINGLES: not started
        card = se.get_entered_scores(event_id, rid, db_path=db_path)["rounds"][0]
        pars = {int(h["hole"]): int(h["par"] or 4) for h in card.get("course") or []}
        groups = card.get("groups") or []
        for gi, g in enumerate(groups):
            gid = g["group_id"]
            se.claim_group(gid, DEVICE, None, db_path=db_path)
            gc = se.get_group_card(gid, DEVICE, db_path=db_path)   # makes FOURSOMES team rows
            if s["format"] == "fourball":
                players = [p["customer_id"] for p in gc.get("players") or []]
                for pi, cid in enumerate(players):
                    sc = _card(rng, pars, 1.0 - 0.08 * pi)
                    marks = {}
                    if gi == 0 and pi == 0:                 # one picked-up ball
                        sc[5] = pars[5] + 3
                        marks[5] = "picked_up"
                    if gi == 1:                             # every ball picked up on 9
                        sc[9] = pars[9] + 3
                        marks[9] = "picked_up"
                    _write(gid, cid, sc, marks, db_path=db_path)
            else:                                           # FOURSOMES: live, thru 9-13
                thru = 9 + (gi % 5)
                if gi == 0:                                 # closed out 2&1, below
                    continue
                for ti, t in enumerate(gc.get("teams") or []):
                    sc = _card(rng, {h: p for h, p in pars.items() if h <= thru},
                               1.4 if (gi == 0 and ti == 0) else 1.0)
                    _write(gid, t["team_id"], sc, is_team=True, db_path=db_path)
        if s["format"] == "chapman" and groups:
            _close_two_and_one(event_id, s["matches"][0]["id"], groups[0]["group_id"],
                               pars, db_path)
        # The seeder's scorer seat comes off every demo group so each
        # scoring link opens on its card; FOURSOMES group 2 stays held
        # (the HELD screen).
        se.release_preview_seed_locks(
            rid, DEVICE, [groups[1]["group_id"]] if s["format"] == "chapman" and len(groups) > 1 else [],
            db_path=db_path)
        # FOURBALL stays OPEN with every card full: the board reads the
        # matches as final from the holes, and an open round keeps its
        # scoring links alive so the preview can show the finished card
        # (a closed round revokes every link).
    plan["rounds"] = out_rounds
    plan["seeded"] = True
    return plan


def teardown(event_id: int = EVENT_ID, db_path=None) -> dict:
    """Close every PREVIEW round on the event and clear the demo dial. The
    rounds and their scores stay on file (nothing is deleted)."""
    from email_parser.database import set_app_setting
    dial = _setting(DIAL, db_path)
    closed = []
    for s in dial.get("sessions") or []:
        if s.get("se_round"):
            try:
                se.close_round(int(s["se_round"]), db_path=db_path)
                closed.append(s["se_round"])
            except Exception:
                logger.exception("preview teardown: close round %s failed", s["se_round"])
    set_app_setting(DIAL, "", db_path=db_path)
    return {"closed_rounds": closed, "dial_cleared": True}
