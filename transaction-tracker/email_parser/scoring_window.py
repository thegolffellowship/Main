"""THE LIVE SCORING WINDOW and THE CLOSEOUT START (Kerry 2026-10-26).

Kerry (CoS #2307 item 6): live scoring turns ON one hour before the first tee
or shotgun and OFF 15 minutes after the last score is in, per event.
Kerry (CoS #2329 item 5): "I thought I changed it to 15 minutes after last
score." -- closeout starts 15 minutes after the last score.

What "on" and "off" mean here. `score_entry_events` (score_entry.event_enabled)
is NOT the switch this module moves: it also decides whether the 6:00 AM
Event Info email carries each player's Keep score link, whether the noon
cart signs and scorecards carry their QR codes, whether the boards read the
entered cards, and whether closed cards publish to the record. Those must
exist before the window opens and long after it closes, so the event stays
enabled exactly as live_scoring_default.py already does (from 5:00 PM the day
before). This module is the WINDOW on a player's score SAVES:
- before first tee minus `live_scoring_on_minutes` (default 60) a save is
  refused with "Scoring opens at <time>"; the phone keeps it in its queue
  and sends it once the window opens (a non-200 never drops a queued op);
- once every card of the event is final and the last score is
  `live_scoring_off_minutes` (default 15) old, the event is CLOSED: saves are
  refused ("Scoring has closed for this event"). Cards already lock one by
  one 15 minutes after their own last score (se_card_lock_minutes); an event
  with any card still open is never closed.
- Admin sessions are never gated. Anything unknown (no first tee, no rounds,
  an error) leaves the window open: this must never stop a real scorer.

THE CLOSEOUT START. Closeout is the Event Ops agent routine (the 9:00 PM run
is its backstop); the Tracker cannot start an agent session. So when every
card of an event is final and the last score is `closeout_start_minutes`
(default 15) old, the job records `closeout_start:<event_id>`, logs
agent_action_log `closeout_start`, and posts one mailbox line TO front-desk
and Event Ops (topic closeout): the signal the routine reads.

Job `scoring_window` every 5 minutes, 7:00 AM to 11:55 PM Central; dial
`scoring_window_auto` (on unless off). Read-only bridge
`scoring-scoring-window:<event_id>`. Guard test_live_scoring_timing.py.
"""
from __future__ import annotations

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

DIAL = "scoring_window_auto"
ON_DIAL = "live_scoring_on_minutes"
OFF_DIAL = "live_scoring_off_minutes"
CLOSEOUT_DIAL = "closeout_start_minutes"
CLOSED_KEY = "se_event_closed:{}"
CLOSEOUT_KEY = "closeout_start:{}"


def _minutes(key: str, default: int, db_path=None) -> int:
    from email_parser.database import get_app_setting
    try:
        return max(0, int((get_app_setting(key, db_path=db_path) or "").strip() or default))
    except (TypeError, ValueError):
        return default


def _on(db_path=None) -> bool:
    from email_parser.database import get_app_setting
    return (get_app_setting(DIAL, db_path=db_path) or "").strip().lower() not in ("0", "off", "false")


def label(dt) -> str:
    """'3:08 PM': 12-hour Central, as people read it (#2325)."""
    return dt.strftime("%I:%M %p").lstrip("0") if dt else ""


def event_state(event_id: int, now=None, db_path=None) -> dict:
    """Where one event stands. Times are naive Central."""
    from email_parser import database as db
    from email_parser import score_entry as se
    from email_parser.after_lock import _first_tee
    from email_parser.timezone_utils import now_central, to_central
    now = now or now_central()
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    if not r:
        return {"error": f"no event {event_id}"}
    ev = dict(r)
    first = _first_tee(ev)
    opens = first - timedelta(minutes=_minutes(ON_DIAL, 60, db_path)) if first else None
    read = se.get_entered_scores(int(event_id), db_path=db_path)
    groups = [g for rd in read.get("rounds") or []
              if not str(rd.get("label") or "").startswith(se.PREVIEW_LABEL)
              for g in rd.get("groups") or []]
    last_utc = max((g["last_write_at"] for g in groups if g.get("last_write_at")), default=None)
    last = to_central(last_utc) if last_utc else None
    all_final = bool(groups) and all(g.get("final") for g in groups)
    closes = last + timedelta(minutes=_minutes(OFF_DIAL, 15, db_path)) if (last and all_final) else None
    closeout = (last + timedelta(minutes=_minutes(CLOSEOUT_DIAL, 15, db_path))
                if (last and all_final) else None)
    return {"event_id": int(event_id), "event": ev.get("item_name"),
            "first_tee": first, "opens_at": opens, "groups": len(groups),
            "cards_final": sum(1 for g in groups if g.get("final")),
            "all_final": all_final, "last_score_at": last,
            "closes_at": closes, "closed": bool(closes and now >= closes),
            "closeout_at": closeout, "closeout_due": bool(closeout and now >= closeout),
            "open": bool((opens is None or now >= opens) and not (closes and now >= closes))}


def entry_open(event_id, now=None, db_path=None) -> tuple:
    """(True, None) when a player's save may land now, else (False, why).
    Fails OPEN on anything unknown."""
    try:
        if event_id is None or not _on(db_path):
            return True, None
        st = event_state(int(event_id), now=now, db_path=db_path)
        if st.get("error"):
            return True, None
        n = now
        if n is None:
            from email_parser.timezone_utils import now_central
            n = now_central()
        if st["opens_at"] and n < st["opens_at"]:
            return False, f"Scoring opens at {label(st['opens_at'])}"
        if st["closed"]:
            return False, "Scoring has closed for this event"
        return True, None
    except Exception:
        logger.exception("scoring window: could not read event %s; left open", event_id)
        return True, None


def tick(now=None, db_path=None) -> dict:
    """The job: record each of today's events closing, and post the closeout
    start signal once per event."""
    from email_parser import database as db
    from email_parser import score_entry as se
    from email_parser.timezone_utils import now_central
    if not _on(db_path):
        return {"status": "off"}
    now = now or now_central()
    with db._connect(db_path) as conn:
        ids = [int(x[0]) for x in conn.execute(
            "SELECT id FROM events WHERE substr(event_date, 1, 10) = ? "
            "AND COALESCE(status, 'active') = 'active'", (now.date().isoformat(),))]
    out = {}
    for eid in ids:
        if not se.event_enabled(eid, db_path):
            continue
        try:
            st = event_state(eid, now=now, db_path=db_path)
        except Exception as exc:
            logger.exception("scoring window: event %s failed", eid)
            out[eid] = {"error": str(exc)}
            continue
        did = {}
        if st.get("closed") and not db.get_app_setting(CLOSED_KEY.format(eid), db_path=db_path):
            db.set_app_setting(CLOSED_KEY.format(eid), now.strftime("%Y-%m-%d %H:%M"), db_path=db_path)
            db.log_agent_action("scoring-window", "live_scoring_closed",
                                f"event {eid} ({st['event']}): all {st['groups']} cards final, "
                                f"last score {label(st['last_score_at'])}; scoring closed",
                                db_path=db_path)
            did["closed"] = True
        if st.get("closeout_due") and not db.get_app_setting(CLOSEOUT_KEY.format(eid), db_path=db_path):
            db.set_app_setting(CLOSEOUT_KEY.format(eid), now.strftime("%Y-%m-%d %H:%M"), db_path=db_path)
            db.log_agent_action("scoring-window", "closeout_start",
                                f"event {eid} ({st['event']}): last score {label(st['last_score_at'])}, "
                                f"closeout starts {label(st['closeout_at'])}", db_path=db_path)
            body = (f"TO: front-desk, Event Ops (closeout)\nCC: kerry\n"
                    f"FROM: the Tracker (scoring window job), {now.strftime('%A %m/%d')}, {label(now)}.\n\n"
                    f"CLOSEOUT START: {st['event']} (event {eid}). All {st['groups']} cards are final; "
                    f"the last score was saved at {label(st['last_score_at'])}, so closeout starts now "
                    f"({label(st['closeout_at'])}, 15 minutes after the last score; Kerry 10/26). "
                    f"The 9:00 PM run stays the backstop.")
            try:
                kw = {"db_path": db_path} if db_path else {}
                db.post_platform_dialogue_entry("tracker-claude", body, "closeout", **kw)
            except Exception:
                logger.exception("scoring window: could not post the closeout start for %s", eid)
            did["closeout_start"] = True
        if did:
            out[eid] = did
    return {"status": "ran", "events": out}
