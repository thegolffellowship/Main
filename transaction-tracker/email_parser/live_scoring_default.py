"""LIVE SCORING ON BY DEFAULT (Kerry 2026-10-13: "Turn live scoring on for
an event should be default after 5:00p Monday pairings are turned on and
definitely prior to these emails being sent out.").

Until now score entry was strictly opt-in: an event reached the phones only
when staff added its id to `score_entry_events` (score_entry.py, Kerry
9/28, when it was a San Antonio test). Kerry's rule replaces "staff turn it
on" for regular events:

- From 5:00 PM Central the DAY BEFORE an event (the evening pairings go out),
  and all of event day, an event with saved pairings is switched on and its
  rounds are seeded from the sheet, so every group has its scoring link.
  The job runs every 15 minutes (`live_scoring_auto_job` in app.py).
- The event-day email turns it on itself before it builds a message to
  send or preview (`ensure_live_scoring`), so no email goes out without the
  Keep score button.

Seeding is safe to do early: a round re-syncs to the saved pairings
whenever they change (score_entry's pairings fingerprint) and re-seeding
never touches a score. Nothing here turns an event OFF.

Skipped: events not 'active', events with no saved pairings, events before
the untether date (the Golf Genius era), and the Lone Star Cup weekend
(its rounds come from the Cup draw). Dial `live_scoring_auto`: "0"/"off"
stops the job; the email path still ensures its own event.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DIAL = "live_scoring_auto"
SWITCH_ON_HOUR = 17          # 5:00 PM Central the day before


def _enable(event_id: int, db_path=None) -> bool:
    """Add the event to score_entry_events. True when it was newly added."""
    from email_parser import score_entry as se
    from email_parser.database import set_app_setting
    on = se.enabled_events(db_path)
    if int(event_id) in on:
        return False
    on.add(int(event_id))
    set_app_setting(se.EVENTS_SETTING, json.dumps(sorted(on)), db_path=db_path)
    return True


def _skip_reason(ev: dict, db_path=None) -> str | None:
    if (ev.get("status") or "active") != "active":
        return f"status {ev.get('status')}"
    try:
        from email_parser.gg_untether import gg_allowed
        if ev.get("event_date") and gg_allowed(ev["event_date"], db_path=db_path):
            return "Golf Genius era event"
    except Exception:
        pass
    try:
        from email_parser import lsc_cup
        if lsc_cup.lsc_report_context(int(ev["id"]), db_path=db_path):
            return "Lone Star Cup event"
    except Exception:
        pass
    return None


def ensure_live_scoring(event_id: int, db_path=None, now=None) -> dict:
    """Switch the event on and seed a round per saved hole set. Idempotent.
    {'enabled': bool, 'newly_enabled': bool, 'rounds': {holes: round_id},
     'skipped': reason or None}"""
    from email_parser import database as db
    from email_parser import score_entry as se
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT id, item_name, event_date, status FROM events WHERE id = ?",
                         (int(event_id),)).fetchone()
    if not r:
        return {"enabled": False, "skipped": "no such event"}
    ev = dict(r)
    why = _skip_reason(ev, db_path)
    if why:
        return {"enabled": se.event_enabled(event_id, db_path), "skipped": why}
    pack = db.get_event_print_pack(int(event_id), db_path=db_path) or {}
    hole_sets = sorted({str(g.get("holes")) for g in pack.get("groups") or [] if g.get("holes")})
    if not hole_sets:
        return {"enabled": se.event_enabled(event_id, db_path), "skipped": "no saved pairings"}
    newly = _enable(int(event_id), db_path)
    rounds, held = {}, {}
    started = _started(int(event_id), db_path, now)
    for hk in hole_sets:
        # The round follows the sheet UNTIL FIRST TEE (Kerry 10/27, CoS
        # #2429-2). After it, a re-seed could relink a group mid-round; a
        # change on the course goes through the card (+ Player, missing).
        if started and se_round_id(int(event_id), hk, db_path):
            held[hk] = "first tee passed"
            continue
        res = se.seed_round_from_pairings(int(event_id), hk, db_path=db_path)
        if res.get("round_id"):
            rounds[hk] = res["round_id"]
    if newly:
        try:
            db.log_agent_action("live-scoring-auto", "enable_live_scoring",
                                f"event {event_id} ({ev.get('item_name')}): on, rounds {rounds}",
                                db_path=db_path)
        except Exception:
            pass
    out = {"enabled": True, "newly_enabled": newly, "rounds": rounds, "skipped": None}
    if held:
        out["held"] = held
    return out


def se_round_id(event_id: int, holes: str, db_path=None):
    from email_parser import score_entry as se
    return se.round_id_for(event_id, holes, db_path)


def _started(event_id: int, db_path=None, now=None) -> bool:
    """First tee (or shotgun) has come, Central."""
    from email_parser import database as db
    from email_parser.after_lock import _first_tee_passed
    from email_parser.timezone_utils import now_central
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    return bool(r) and _first_tee_passed(dict(r), now or now_central())


def follow_sheet(event_id: int, db_path=None, now=None) -> dict:
    """LIVE ROUND FOLLOWS THE SHEET (Kerry 10/27, CoS #2429-2: "live, not
    snapshot"). Called after every saved change to an event's pairings or a
    player's tee (app.py `_follow_sheet_after_save`): if the event already has
    a live round, re-derive it from the saved sheet now (groups, players,
    tees, playing handicaps; groups no longer on the sheet dropped). Never
    creates a round (the 5:00 PM job does that), never runs after first tee,
    never touches a score."""
    from email_parser import score_entry as se
    if not se.event_enabled(int(event_id), db_path):
        return {"skipped": "live scoring not on for this event"}
    if not se.event_has_round(int(event_id), db_path):
        return {"skipped": "no live round yet"}
    return ensure_live_scoring(int(event_id), db_path=db_path, now=now)


def due_event_ids(now=None, db_path=None) -> list[int]:
    """Events whose switch-on time has come: dated today, or dated tomorrow
    once it is 5:00 PM Central or later."""
    from email_parser import database as db
    if now is None:
        from email_parser.timezone_utils import now_central
        now = now_central()
    today = now.date()
    days = [today.isoformat()]
    if now.hour >= SWITCH_ON_HOUR:
        days.append((today + timedelta(days=1)).isoformat())
    with db._connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id FROM events WHERE substr(event_date, 1, 10) IN ({}) "
            "AND COALESCE(status, 'active') = 'active'".format(",".join("?" * len(days))),
            days).fetchall()
    return [int(x[0]) for x in rows]


def live_scoring_auto_check(now=None, db_path=None) -> dict:
    from email_parser.database import get_app_setting
    if (get_app_setting(DIAL, db_path=db_path) or "").strip().lower() in ("0", "off", "false"):
        return {"status": "off"}
    out = {}
    for eid in due_event_ids(now, db_path):
        try:
            out[eid] = ensure_live_scoring(eid, db_path=db_path, now=now)
        except Exception as exc:
            logger.exception("live scoring auto: event %s failed", eid)
            out[eid] = {"error": str(exc)}
    return {"status": "ran", "events": out}
