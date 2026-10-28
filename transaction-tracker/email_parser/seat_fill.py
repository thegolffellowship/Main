"""SEAT-FILL: late adds seat themselves (Kerry 2026-10-26, CoS #2308, #2331
C, #2333; sized in #2310). Kerry: "Sign-ups between 5 and 7p. We need
something here to automate adding to groups ... We've got to get to the point
of zero manager reliance. The show must go on."

From an event's 5:00 PM lock to its first tee, every REGISTERED (paid) player
on the roster who has no seat on the saved sheet is seated by the ruled rule
(event-timeline.md, Kerry 10/20):
- tee times: the LATEST threesome first, then earlier;
- shotgun: the LOWEST hole first; on one hole, B before A.
A seat is open when the group has fewer than the team size (4). The late add
takes the lowest free cart position in that group, and any blind drawn for
that seat is cleared (the late add replaces it). Requests after the lock are
not honoured (ruled 10/20). RSVP-only players are never seated (#2310).

It writes the saved sheet with save_event_pairings, the one writer the
pairings page, the print pack and the after-lock job read, so the emails that
follow are the existing ones: before the Event Info send the new seat rides in
the draft sheet and the 6:00 AM Event Info; after it, the after-lock job sends
the player, the group (UPDATED GROUP) and the course sheets. It runs as the
first step of that job, so the seat is saved before the update emails go
(Kerry, #2331 C).

No open seat: the player stays Unassigned and one COO item is raised per
person per event (the waitlist is not ruled). Dial seat_fill_auto (on unless
off); read-only bridge scoring-seat-fill:<event_id>[|apply]; every seat in
agent_action_log (seat_fill).
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

DIAL = "seat_fill_auto"
RAISED_KEY = "seat_fill_unseated:{}"
TEAM_SIZE = 4
_SHOTGUN = re.compile(r"^\s*(\d+)\s*([AB])?\s*$", re.I)  # one group on a hole = no letter


def _on(db_path=None) -> bool:
    from email_parser import database as db
    return (db.get_app_setting(DIAL, db_path=db_path) or "").strip().lower() not in ("0", "off", "false")


def _holes_key(ev: dict, sheet: dict) -> str | None:
    fmt = (ev.get("format") or "").strip()
    want = "18" if fmt in ("18 Holes", "27 Holes") else "9"
    if sheet.get(want):
        return want
    for h in ("9", "18"):
        if sheet.get(h):
            return h
    return None


def shotgun_train_rank(labels: list) -> dict:
    """{hole: place in the pack, 0 = the FRONT} in play order (Kerry 10/28:
    a reverse or staged shotgun's front is not its highest hole number;
    database.shotgun_train_order). A sheet whose holes span at most nine is
    treated as one nine, which loops on itself."""
    from email_parser import database as db
    hs = [int(m.group(1)) for m in (_SHOTGUN.match(x or "") for x in labels) if m]
    if not hs:
        return {}
    ring = 9 if max(hs) - min(hs) <= 8 else 18
    order = db.shotgun_train_order([f"{h}A" for h in sorted(set(hs))], ring)
    return {int(x[:-1]): i for i, x in enumerate(order)}


def shotgun_back_key(groups: list):
    """Sort key BACK of the pack first, B before A on a hole: the old 'lowest
    hole first, B before A' read in play order."""
    rank = shotgun_train_rank([g.get("slot_label") or "" for g in groups])
    def key(g):
        m = _SHOTGUN.match(g.get("slot_label") or "")
        return (-rank.get(int(m.group(1)), 0), 0 if (m.group(2) or "A").upper() == "B" else 1)
    return key


def shotgun_front_key(groups: list):
    """Sort key FRONT of the pack first, B before A on a hole: the old 'highest
    hole first, B before A' read in play order."""
    rank = shotgun_train_rank([g.get("slot_label") or "" for g in groups])
    def key(g):
        m = _SHOTGUN.match(g.get("slot_label") or "")
        return (rank.get(int(m.group(1)), 0), 0 if (m.group(2) or "A").upper() == "B" else 1)
    return key


def fill_order(groups: list) -> list:
    """The groups in the order a late add takes them (Kerry 10/20): on a
    shotgun the BACK of the pack first (in play order, Kerry 10/28), B
    before A; tee times the latest group first."""
    labels = [g.get("slot_label") or "" for g in groups]
    if groups and all(_SHOTGUN.match(x) for x in labels):
        return sorted(groups, key=shotgun_back_key(groups))
    return sorted(groups, key=lambda g: int(g.get("group_num") or 0), reverse=True)


def plan(event_id: int, db_path=None) -> dict:
    """Who would be seated where, now. Writes nothing."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
        if not r:
            return {"error": f"no event {event_id}"}
        ev = dict(r)
        roster = db._event_roster_rows(conn, int(event_id))
    sheet = db.get_event_pairings(int(event_id), db_path=db_path) or {}
    holes = _holes_key(ev, sheet)
    out = {"event_id": int(event_id), "event": ev.get("item_name"), "holes": holes,
           "seat": [], "unseated": []}
    if not holes:
        return {**out, "skipped": "no saved pairings"}
    groups = [dict(g, players=list(g.get("players") or [])) for g in sheet[holes]]
    seated_ids = {p.get("customer_id") for g in groups for p in g["players"] if p.get("customer_id")}
    seated_names = {db._pair_key_name(p.get("name") or "") for g in groups for p in g["players"]}
    late, seen = [], set()
    for row in roster:
        if row.get("rsvp_only"):
            continue
        cid = row.get("customer_id")
        k = db._pair_key_name(row.get("name") or "")
        if not k or k in seen:
            continue
        seen.add(k)
        if (cid and cid in seated_ids) or k in seated_names:
            continue
        late.append({"name": row.get("name"), "customer_id": cid})
    order = fill_order(groups)
    for p in late:
        g = next((x for x in order if 0 < len(x["players"]) < TEAM_SIZE), None)
        if g is None:
            out["unseated"].append(p)
            continue
        taken = {q.get("cart_pos") for q in g["players"]}
        pos = next(i for i in range(1, TEAM_SIZE + 1) if i not in taken)
        g["players"].append({"name": p["name"], "customer_id": p["customer_id"], "cart_pos": pos})
        out["seat"].append({**p, "group_num": g.get("group_num"), "slot": g.get("slot_label"),
                            "cart_pos": pos})
    out["_sheet"] = {**{h: gs for h, gs in sheet.items() if h in ("9", "18")},
                     holes: sorted(groups, key=lambda g: int(g.get("group_num") or 0))}
    return out


def run(event_id: int, apply: bool = False, db_path=None) -> dict:
    """Seat the late adds. Dry run unless apply."""
    from email_parser import database as db
    p = plan(event_id, db_path)
    if p.get("error") or p.get("skipped"):
        return {k: v for k, v in p.items() if k != "_sheet"}
    out = {k: v for k, v in p.items() if k != "_sheet"}
    if not apply:
        return {**out, "dry_run": True}
    if p["seat"]:
        db.save_event_pairings(int(event_id), p["_sheet"], db_path=db_path)
        blinds = db.get_event_blinds(int(event_id), db_path=db_path) or {}
        for s in p["seat"]:
            have = blinds.get(p["holes"], {}).get(s["group_num"]) or []
            if any(b.get("cart_pos") == s["cart_pos"] for b in have):
                try:
                    db.set_event_blind(int(event_id), p["holes"], int(s["group_num"]),
                                       int(s["cart_pos"]), None, db_path=db_path)
                except Exception:
                    logger.exception("seat fill: could not clear the blind for %s", s)
            db.log_agent_action("seat-fill", "seat_fill",
                                f"event {event_id} customer {s['customer_id']} {s['name']}: "
                                f"seated in {s['slot'] or 'group ' + str(s['group_num'])}, seat {s['cart_pos']}")
    if p["unseated"]:
        try:
            raised = set(json.loads(db.get_app_setting(RAISED_KEY.format(int(event_id)),
                                                       db_path=db_path) or "[]"))
        except Exception:
            raised = set()
        new = [u for u in p["unseated"] if str(u["customer_id"] or u["name"]) not in raised]
        if new:
            try:
                from email_parser.timezone_utils import today_central_str
                db.save_action_item({
                    "subject": f"NO OPEN SEAT: {p['event']}", "from_name": "Seat-fill",
                    "summary": "Registered after the 5:00 PM lock and no group has an open seat: "
                               + ", ".join(u["name"] for u in new)
                               + ". They are in Unassigned on the pairings page.",
                    "urgency": "high", "category": "other",
                    "email_date": today_central_str(), "confidence": 100}, db_path=db_path)
                raised |= {str(u["customer_id"] or u["name"]) for u in new}
                db.set_app_setting(RAISED_KEY.format(int(event_id)), json.dumps(sorted(raised)),
                                   db_path=db_path)
            except Exception:
                logger.exception("seat fill: could not raise the COO item")
    return {**out, "applied": True}


def check(now=None, db_path=None) -> dict:
    """The job step: every active event past its lock and before its first tee."""
    from datetime import timedelta
    from email_parser import database as db
    from email_parser.after_lock import _first_tee_passed
    from email_parser.payment_reminder import lock_at
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
        lock = lock_at(ev, db_path)
        if lock is None or now < lock or _first_tee_passed(ev, now):
            continue
        try:
            res = run(int(ev["id"]), apply=True, db_path=db_path)
            if res.get("seat") or res.get("unseated"):
                out[ev["id"]] = res
        except Exception as exc:
            logger.exception("seat fill failed for %s", ev["id"])
            out[ev["id"]] = {"error": str(exc)}
    return {"status": "ran", "events": out}
