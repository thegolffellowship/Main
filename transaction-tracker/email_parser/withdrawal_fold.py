"""WITHDRAWAL FOLD: the sheet repairs itself after a withdrawal (Kerry
2026-10-26, relayed verbatim by the Chief of Staff, mailbox #2363-#2366).

Kerry: "Yes. In a shotgun, that should be the foursome with the highest hole
number and B before A. In a tee time, that should be the first foursome. ...
We don't want 4 threesomes on the course if we can help it. That's the key.
And we don't want twosomes out there if we can help it, even though we've had
those situations."
Kerry: "Only thing is with two players leaving it depends if we've reduced
multiples of four or stayed the same. Like if we had 41, and two dipping from
the same group left 39. Of course two could leave from a foursome too, leaving
only two. We'd want to fill to at least 3. We need to address all the
scenarios to code for it in the tracker."
Kerry on timing: "Yes that way for now. May need to come back to the within an
hour of tee time later. Let's see how this works for now."

ONE algorithm, recomputed every run from the saved sheet (each holes set):
A. N players -> G = ceil(N/4) groups, T = 4G - N threesomes, every group 3-4.
B. More groups than G (the field crossed a multiple of 4 downward): dissolve
   the SHORTEST group (tie: the one a withdrawal hit; then, tee times, the
   time the keep/release rule gives back -- weeknight the earliest, weekend
   the latest; shotgun, the highest hole, B before A). Its players go one
   each into the open groups -- a group under 3 first, then the threesomes
   in seat-fill order (tee times latest threesome first; shotgun lowest hole
   first, B before A). The dissolved group's time is released. Repeat.
C. A group under 3 takes one player from each foursome in DONOR order
   (shotgun: highest hole first, B before A; tee times: the first/earliest
   foursome), the donor's highest untied seat, until it has 3.
D. Never split a partner request, a match or a guest from the host: a unit
   moves whole or not at all; a blocked candidate passes to the next. If
   nothing works, NOTHING changes and one COO item is raised.
E. Seat-fill runs first in the same after-lock job run; the fold follows.
F. The fold only writes the saved sheet (save_event_pairings). The after-lock
   job, in the same run, diffs that sheet against what the Event Info carried
   and sends UPDATED GROUP to the moved players and both groups (manager
   CC'd) and only the changed sheets to the course inside its window. Before
   the Event Info goes, the fold simply rides in the sheet it sends.

TIMING (ruled #2366): only from the event's lock (database.event_lock_at) to
first tee. C (a group under 3) runs at once. B waits for 7:00 AM on event day
(dial withdrawal_fold_dissolve_at, "07:00") so a late add can still take the
seat; after that it runs at once. Nothing within the hour before the first tee
(dial withdrawal_fold_cutoff_min, 60): the scorer no-show sequence takes over.
Dial withdrawal_fold_auto (on unless off). Read-only bridge
scoring-withdrawal-fold:<event_id>. Every move in agent_action_log
(withdrawal_fold). Guard test_withdrawal_fold.py.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DIAL = "withdrawal_fold_auto"
DISSOLVE_AT_DIAL = "withdrawal_fold_dissolve_at"
CUTOFF_DIAL = "withdrawal_fold_cutoff_min"
STATE_KEY = "withdrawal_fold_seen:{}"
RAISED_KEY = "withdrawal_fold_raised:{}"
TEAM = 4
MIN_GROUP = 3
_SHOTGUN = re.compile(r"^\s*(\d+)\s*([AB])\s*$", re.I)


def _on(db_path=None) -> bool:
    from email_parser import database as db
    return (db.get_app_setting(DIAL, db_path=db_path) or "").strip().lower() not in ("0", "off", "false")


def _is_shotgun(groups: list) -> bool:
    return bool(groups) and all(_SHOTGUN.match(g.get("slot_label") or "") for g in groups)


def _hole_key(g: dict):
    m = _SHOTGUN.match(g.get("slot_label") or "")
    return (int(m.group(1)), 0 if m.group(2).upper() == "B" else 1) if m else (0, 0)


def donor_order(groups: list) -> list:
    """The groups in the order they give a player to a short group (Kerry
    10/26): shotgun, the highest hole first, B before A; tee times, the first
    (earliest) group first. The mirror of seat-fill, so threesomes stay out
    front."""
    if _is_shotgun(groups):
        # Front of the pack in PLAY order (Kerry 10/28: a reverse or staged
        # shotgun's front is not its highest hole number).
        from email_parser.seat_fill import shotgun_front_key
        return sorted(groups, key=shotgun_front_key(groups))
    return sorted(groups, key=lambda g: int(g.get("group_num") or 0))


def _fill_order(groups: list) -> list:
    from email_parser.seat_fill import fill_order
    return fill_order(groups)


def _pkey(p: dict) -> str:
    from email_parser import database as db
    return db._pair_key_name(p.get("name") or "")


def _units(g: dict, ties: dict) -> list:
    """The group's players as unsplittable units: players joined by a partner
    request, a match or guest-and-host stay together."""
    ps = list(g.get("players") or [])
    parent = list(range(len(ps)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    keys = [_pkey(p) for p in ps]
    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            if frozenset((keys[i], keys[j])) in ties:
                parent[find(i)] = find(j)
    by = {}
    for i, p in enumerate(ps):
        by.setdefault(find(i), []).append(p)
    return sorted(by.values(), key=lambda u: (-len(u), min(q.get("cart_pos") or 9 for q in u)))


def _tied(p: dict, g: dict, ties: dict) -> str | None:
    k = _pkey(p)
    for q in g.get("players") or []:
        if q is not p and frozenset((k, _pkey(q))) in ties:
            return ties[frozenset((k, _pkey(q)))]
    return None


def _seat(p: dict, g: dict) -> int:
    taken = {q.get("cart_pos") for q in g["players"]}
    return next(i for i in range(1, TEAM + 1) if i not in taken)


def _label(g: dict) -> str:
    return g.get("slot_label") or f"group {g.get('group_num')}"


def fold(groups: list, ties: dict | None = None, hit: set | None = None,
         dissolve: bool = True, keep_mode: str = "latest") -> dict:
    """Steps A-D on one holes set. Pure: `groups` is not changed. `hit` is the
    group numbers a withdrawal touched; `dissolve` False holds step B (before
    7:00 AM event day). Returns {groups, moves, dissolved, released, N, G, T,
    pending_dissolve} or {blocked: reason}."""
    ties = ties or {}
    hit = set(hit or ())
    gs = [g for g in copy.deepcopy(groups) if g.get("players")]
    n = sum(len(g["players"]) for g in gs)
    G = max(1, -(-n // TEAM))
    out = {"N": n, "G": G, "T": TEAM * G - n, "groups_before": len(gs),
           "moves": [], "dissolved": [], "released": [], "pending_dissolve": False}
    if n == 0:
        return {**out, "groups": gs}
    shotgun = _is_shotgun(gs)

    def move(p, src, dst, step, why=""):
        src["players"].remove(p)
        old = p.get("cart_pos")
        p = {**p, "cart_pos": _seat(p, dst)}
        dst["players"].append(p)
        out["moves"].append({"name": p.get("name"), "customer_id": p.get("customer_id"),
                             "from": _label(src), "from_group": src.get("group_num"), "from_seat": old,
                             "to": _label(dst), "to_group": dst.get("group_num"),
                             "seat": p["cart_pos"], "step": step, **({"why": why} if why else {})})

    from email_parser.seat_fill import shotgun_front_key
    _front_key = shotgun_front_key(gs) if shotgun else None

    def dissolve_rank(g):
        if shotgun:
            tie2 = _front_key(g)
        else:
            gn = int(g.get("group_num") or 0)
            tie2 = (gn,) if keep_mode == "latest" else (-gn,)
        return (len(g["players"]), 0 if g.get("group_num") in hit else 1, tie2)

    def place(c, others):
        """Where each unit of c goes, or None. Groups under 3 first (up to 3),
        then the threesomes in seat-fill order, one each; then any room."""
        fo = {id(g): i for i, g in enumerate(_fill_order(others))}
        order = sorted(others, key=lambda g: (0 if len(g["players"]) < MIN_GROUP else 1, fo[id(g)]))
        room = {id(g): TEAM - len(g["players"]) for g in others}
        got = {id(g): 0 for g in others}
        cap = {id(g): max(1, MIN_GROUP - len(g["players"])) for g in others}
        plan = []
        for u in _units(c, ties):
            dst = (next((g for g in order if room[id(g)] >= len(u) and got[id(g)] + len(u) <= cap[id(g)]), None)
                   or next((g for g in order if room[id(g)] >= len(u)), None))
            if dst is None:
                return None
            room[id(dst)] -= len(u)
            got[id(dst)] += len(u)
            plan += [(p, dst) for p in u]
        return plan

    # B: dissolve while there are more groups than the field needs
    if len(gs) > G and not dissolve:
        out["pending_dissolve"] = True
    while dissolve and len(gs) > G:
        done = False
        for c in sorted(gs, key=dissolve_rank):
            others = [g for g in gs if g is not c]
            plan = place(c, others)
            if plan is None:
                continue
            for p, dst in plan:
                move(p, c, dst, "dissolve")
            out["dissolved"].append(_label(c))
            if not shotgun:
                out["released"].append(c.get("slot_label"))
            gs = others
            done = True
            break
        if not done:
            return {**out, "blocked": "every group that could dissolve holds a partner request, "
                                      "a match or a guest and host that no open group can take whole"}

    # C: every group under 3 takes from the foursomes, donor order
    gave = set()
    shorts = sorted([g for g in gs if len(g["players"]) < MIN_GROUP],
                    key=lambda g: (len(g["players"]), {id(x): i for i, x in enumerate(_fill_order(gs))}[id(g)]))
    for g in shorts:
        while len(g["players"]) < MIN_GROUP:
            took = False
            for d in donor_order([x for x in gs if x is not g and len(x["players"]) >= TEAM
                                  and id(x) not in gave]):
                free = [p for p in sorted(d["players"], key=lambda p: -(p.get("cart_pos") or 0))
                        if not _tied(p, d, ties)]
                if not free:
                    continue
                move(free[0], d, g, "repair")
                gave.add(id(d))
                took = True
                break
            if not took:
                return {**out, "blocked": f"{_label(g)} has {len(g['players'])} and no foursome can give "
                                          "a player without splitting a partner request, a match or a "
                                          "guest and host"}
    for g in gs:
        g["players"].sort(key=lambda p: p.get("cart_pos") or 0)
    return {**out, "groups": sorted(gs, key=lambda g: int(g.get("group_num") or 0)),
            "groups_after": len(gs)}


def _ties(event_id: int, db_path=None) -> dict:
    """{frozenset(key, key): kind} for every pair the fold may not split:
    partner requests (not suppressed), guest and host, Match Play."""
    from email_parser import database as db
    K = db._pair_key_name
    out = {}
    with db._connect(db_path) as conn:
        roster = db._event_roster_rows(conn, int(event_id))
    try:
        for rq in db.get_event_partner_requests(int(event_id), db_path=db_path,
                                                roster_rows=roster).get("requests", []):
            if rq.get("requester") and rq.get("partner") and not rq.get("suppressed"):
                out[frozenset((K(rq["requester"]), K(rq["partner"])))] = "partner request"
    except Exception:
        logger.exception("withdrawal fold: requests unreadable for %s", event_id)
    try:
        names = [r["customer"] for r in roster if r.get("customer")]
        ids = {r["customer"]: r["customer_id"] for r in roster if r.get("customer_id") and r.get("customer")}
        for gk, hk in db._host_of_map(roster, names, roster_ids=ids).items():
            out[frozenset((gk, hk))] = "guest and host"
        # guests of one host stay with each other too
    except Exception:
        logger.exception("withdrawal fold: hosts unreadable for %s", event_id)
    try:
        for m in db.detect_match_play_pairings(int(event_id), db_path=db_path,
                                               roster_rows=roster).get("matches", []):
            if m.get("player1") and m.get("player2"):
                out[frozenset((K(m["player1"]), K(m["player2"])))] = "match"
    except Exception:
        logger.exception("withdrawal fold: Match Play unreadable for %s", event_id)
    return {k: v for k, v in out.items() if len(k) == 2}


def _seen(sheet: dict) -> dict:
    out = {}
    for h in ("9", "18"):
        for g in sheet.get(h) or []:
            for p in g.get("players") or []:
                k = str(p.get("customer_id") or "") or "n:" + _pkey(p)
                out[k] = f"{h}|{g.get('group_num')}"
    return out


def _state(event_id: int, sheet: dict, db_path=None) -> dict:
    """{seen, hit}: the groups a withdrawal touched since the fold last looked
    (a player who was on the sheet and is not now). Not saved here."""
    from email_parser import database as db
    try:
        st = json.loads(db.get_app_setting(STATE_KEY.format(int(event_id)), db_path=db_path) or "null") or {}
    except (TypeError, ValueError):
        st = {}
    now = _seen(sheet)
    hit = set(st.get("hit") or [])
    for k, gk in (st.get("seen") or {}).items():
        if k not in now:
            hit.add(gk)
    live = {f"{h}|{g.get('group_num')}" for h in ("9", "18") for g in sheet.get(h) or [] if g.get("players")}
    return {"seen": now, "hit": sorted(hit & live), "first_look": not st}


def observe(event_id: int, db_path=None) -> dict:
    """Save what the fold has seen on the sheet (the job does this every run)."""
    from email_parser import database as db
    st = _state(event_id, db.get_event_pairings(int(event_id), db_path=db_path) or {}, db_path)
    db.set_app_setting(STATE_KEY.format(int(event_id)),
                       json.dumps({"seen": st["seen"], "hit": st["hit"]}, sort_keys=True), db_path=db_path)
    return st


def _dissolve_at(ev: dict, db_path=None):
    from email_parser import database as db
    raw = (db.get_app_setting(DISSOLVE_AT_DIAL, db_path=db_path) or "07:00").strip()
    try:
        t = datetime.strptime(raw, "%H:%M").time()
    except ValueError:
        t = datetime.strptime("07:00", "%H:%M").time()
    try:
        return datetime.combine(datetime.strptime(str(ev.get("event_date"))[:10], "%Y-%m-%d").date(), t)
    except ValueError:
        return None


def _cutoff(ev: dict, db_path=None):
    from email_parser import database as db
    from email_parser.after_lock import _first_tee
    t = _first_tee(ev)
    if t is None:
        return None, None
    try:
        mins = int((db.get_app_setting(CUTOFF_DIAL, db_path=db_path) or "60").strip())
    except (TypeError, ValueError):
        mins = 60
    return t, t - timedelta(minutes=max(0, mins))


def plan(event_id: int, now=None, db_path=None) -> dict:
    """What the fold would do now. Writes nothing."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    if not r:
        return {"error": f"no event {event_id}"}
    ev = dict(r)
    if now is None:
        from email_parser.timezone_utils import now_central
        now = now_central()
    lock = db.event_lock_at(ev, db_path)
    first, cutoff = _cutoff(ev, db_path)
    dis_at = _dissolve_at(ev, db_path)
    out = {"event_id": int(event_id), "event": ev.get("item_name"), "now": str(now),
           "lock": str(lock) if lock else None, "first_tee": str(first) if first else None,
           "dissolve_from": str(dis_at) if dis_at else None, "holes": {}}
    if int(ev.get("allow_fivesomes") or 0):
        return {**out, "skipped": "fivesome event: the fold is for foursomes"}
    if lock is None or now < lock:
        return {**out, "skipped": "before the lock"}
    if first is not None and now >= first:
        return {**out, "skipped": "first tee passed"}
    if cutoff is not None and now >= cutoff:
        return {**out, "skipped": "within the hour before the first tee: the scorer no-show sequence takes over"}
    sheet = db.get_event_pairings(int(event_id), db_path=db_path) or {}
    if not any(g.get("players") for h in ("9", "18") for g in sheet.get(h) or []):
        return {**out, "skipped": "no saved pairings"}
    st = _state(event_id, sheet, db_path)
    ties = _ties(event_id, db_path)
    dissolve = dis_at is None or now >= dis_at
    keep = db.tee_keep_mode(ev)
    for h in ("9", "18"):
        groups = [g for g in sheet.get(h) or [] if g.get("players")]
        if not groups:
            continue
        hit = {int(x.split("|")[1]) for x in st["hit"] if x.split("|")[0] == h}
        res = fold(groups, ties, hit, dissolve=dissolve, keep_mode=keep)
        if res.get("blocked") and res.get("pending_dissolve"):
            # A group under 3 that no foursome can repair while the dissolve
            # still waits: the dissolve runs now instead (flagged in events.md).
            res2 = fold(groups, ties, hit, dissolve=True, keep_mode=keep)
            if not res2.get("blocked"):
                res = {**res2, "early_dissolve": "a group under 3 could not be repaired from a foursome"}
        res["hit"] = sorted(hit)
        out["holes"][h] = res
    out["changed"] = any(x.get("moves") for x in out["holes"].values())
    out["blocked"] = {h: x["blocked"] for h, x in out["holes"].items() if x.get("blocked")}
    out["_state"] = st
    return out


def _public(p: dict) -> dict:
    return {k: ({h: {kk: vv for kk, vv in x.items() if kk != "groups"} for h, x in v.items()}
                if k == "holes" else v)
            for k, v in p.items() if k != "_state"}


def run(event_id: int, apply: bool = False, now=None, db_path=None) -> dict:
    """Fold one event. Dry run unless apply."""
    from email_parser import database as db
    p = plan(event_id, now=now, db_path=db_path)
    if p.get("error") or p.get("skipped"):
        return _public(p)
    out = _public(p)
    if not apply:
        return {**out, "dry_run": True}
    st = p["_state"]
    if p["blocked"]:
        _raise_blocked(event_id, p, db_path)
        db.set_app_setting(STATE_KEY.format(int(event_id)),
                           json.dumps({"seen": st["seen"], "hit": st["hit"]}, sort_keys=True), db_path=db_path)
        return {**out, "applied": False}
    if not p["changed"]:
        db.set_app_setting(STATE_KEY.format(int(event_id)),
                           json.dumps({"seen": st["seen"], "hit": st["hit"]}, sort_keys=True), db_path=db_path)
        return {**out, "applied": False}
    sheet = db.get_event_pairings(int(event_id), db_path=db_path) or {}
    new = {h: gs for h, gs in sheet.items() if h in ("9", "18")}
    for h, res in p["holes"].items():
        if res.get("moves"):
            new[h] = [{"group_num": g["group_num"], "slot_label": g.get("slot_label"),
                       "players": [{k: q.get(k) for k in ("name", "customer_id", "cart_pos", "tee_choice",
                                                            "handicap_index")} for q in g["players"]]}
                      for g in res["groups"]]
    # a mover takes a real seat: a blind drawn for that seat is cleared, as seat-fill does
    blinds = db.get_event_blinds(int(event_id), db_path=db_path) or {}
    db.save_event_pairings(int(event_id), new, db_path=db_path)
    for h, res in p["holes"].items():
        for m in res.get("moves") or []:
            have = blinds.get(h, {}).get(m["to_group"]) or []
            if any(b.get("cart_pos") == m["seat"] for b in have):
                try:
                    db.set_event_blind(int(event_id), h, int(m["to_group"]), int(m["seat"]), None,
                                       db_path=db_path)
                except Exception:
                    logger.exception("withdrawal fold: could not clear the blind for %s", m)
            db.log_agent_action("withdrawal-fold", "withdrawal_fold",
                                f"event {event_id} customer {m['customer_id']} {m['name']}: "
                                f"{'group dissolved' if m['step'] == 'dissolve' else 'short group repaired'}, "
                                f"{m['from']} -> {m['to']} seat {m['seat']} "
                                f"(N={res['N']}, groups {res['groups_before']} -> {res.get('groups_after')})")
        for t in res.get("released") or []:
            db.log_agent_action("withdrawal-fold", "withdrawal_fold",
                                f"event {event_id}: tee time {t} released (group dissolved)")
    after = db.get_event_pairings(int(event_id), db_path=db_path) or {}
    left = {f"{h}|{g.get('group_num')}" for h in ("9", "18") for g in after.get(h) or [] if g.get("players")}
    db.set_app_setting(STATE_KEY.format(int(event_id)),
                       json.dumps({"seen": _seen(after), "hit": sorted(set(st["hit"]) & left)}, sort_keys=True),
                       db_path=db_path)
    return {**out, "applied": True}


def _raise_blocked(event_id: int, p: dict, db_path=None) -> None:
    """ONE COO item per blocked sheet (the same block is not raised twice)."""
    from email_parser import database as db
    sig = hashlib.sha1(json.dumps(
        {h: [sorted(_pkey(q) for q in g.get("players") or [])
             for g in (db.get_event_pairings(int(event_id), db_path=db_path) or {}).get(h) or []]
         for h in p["blocked"]}, sort_keys=True).encode()).hexdigest()[:16]
    key = RAISED_KEY.format(int(event_id))
    if (db.get_app_setting(key, db_path=db_path) or "") == sig:
        return
    try:
        from email_parser.timezone_utils import today_central_str
        db.save_action_item({
            "subject": f"WITHDRAWAL FOLD BLOCKED: {p['event']}", "from_name": "Withdrawal fold",
            "summary": "After a withdrawal the groups could not be made 3 or 4 without splitting a "
                       "partner request, a match or a guest and host, so nothing was moved: "
                       + "; ".join(f"{h} holes: {why}" for h, why in p["blocked"].items())
                       + ". Fix it by hand on the pairings page.",
            "urgency": "high", "category": "other",
            "email_date": today_central_str(), "confidence": 100}, db_path=db_path)
        db.set_app_setting(key, sig, db_path=db_path)
    except Exception:
        logger.exception("withdrawal fold: could not raise the COO item")


def check(now=None, db_path=None) -> dict:
    """The job step (inside after_lock_changes, right after seat-fill): every
    active event from its lock to the hour before its first tee."""
    from email_parser import database as db
    if not _on(db_path):
        return {"status": "off"}
    if now is None:
        from email_parser.timezone_utils import now_central
        now = now_central()
    days = [(now.date() + timedelta(days=i)).isoformat() for i in range(0, 4)]
    with db._connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM events WHERE substr(event_date, 1, 10) IN (?, ?, ?, ?) "
            "AND COALESCE(status, 'active') = 'active'", days)]
    out = {}
    for ev in rows:
        lock = db.event_lock_at(ev, db_path)
        if lock is None or now < lock:
            continue
        try:
            res = run(int(ev["id"]), apply=True, now=now, db_path=db_path)
            if res.get("applied") or res.get("blocked"):
                out[ev["id"]] = res
        except Exception as exc:
            logger.exception("withdrawal fold failed for %s", ev["id"])
            out[ev["id"]] = {"error": str(exc)}
    return {"status": "ran", "events": out}
