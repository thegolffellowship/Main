"""THE NOON COURSE FILES JOB (Kerry 2026-10-26, CoS #2321, #2329-3, #2331
item 4). Kerry: "Event ops - Absolutely should be on Tracker side. Not an
agent routine" and "CC Course Files to Manager too at the Tue noon job."

On event day, from 12:00 PM Central (job every 15 minutes, 12:00 to 2:45 PM),
each active event dated today with saved pairings gets its Course Files
once, through the same path as the Course Files button
(print_pack.send_course_files: To the course's primary TGF contact, CC its
other TGF contacts and Kerry's pack recipients) with the chapter manager
added on CC.

- Already sent (by the button, or an earlier run): skipped. The record is
  after_lock's course_files_sent:<event_id>, which a send writes, so the
  after-lock job's changed-sheet resends keep working from it.
- A gap (scorecards that can't print yet): nothing goes to the course; the
  manager gets one email per event saying why, and the next run tries again
  (it sends once the gap is fixed).
- No course contact on file: nothing new (the morning manager-only pack
  covers it).
- Too late: never inside the hour before the first tee
  (after_lock.course_cutoff_passed, Kerry #2329-4), so a morning event
  whose first tee is before about 1:00 PM is not sent by this job.
Dial course_files_noon_auto (on unless off). Every send in message_log and
agent_action_log. Read-only bridge scoring-course-files-noon:<event_id>.
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

DIAL = "course_files_noon_auto"
GAP_KEY = "course_files_noon_gap_sent:{}"
FROM_HOUR = 12


def _on(db_path=None) -> bool:
    from email_parser import database as db
    return (db.get_app_setting(DIAL, db_path=db_path) or "").strip().lower() not in ("0", "off", "false")


def why_not(ev: dict, now, db_path=None) -> str | None:
    """None when this event's Course Files may go now, else why not."""
    from email_parser import database as db
    from email_parser import after_lock
    from email_parser.print_pack import course_recipients_for_event
    if (ev.get("status") or "active") != "active":
        return "not active"
    if str(ev.get("event_date") or "")[:10] != now.date().isoformat():
        return "not event day"
    if now.hour < FROM_HOUR:
        return "before noon"
    if after_lock._get(after_lock.COURSE_KEY.format(int(ev["id"])), db_path):
        return "Course Files already sent"
    if not db._event_has_saved_pairings(int(ev["id"]), db_path):
        return "no saved pairings"
    if after_lock.course_cutoff_passed(ev, now, db_path):
        return "within the hour before the first tee"
    if not course_recipients_for_event(ev, db_path).get("ok"):
        return "no course contact on file (the morning manager pack covers it)"
    return None


def run_event(event_id: int, render, static_dir, confirm: bool = False, now=None,
              db_path=None) -> dict:
    """Send (confirm=True) or preview one event's noon Course Files."""
    from email_parser import database as db
    from email_parser import print_pack as pp
    from email_parser.after_lock import _manager_cc
    if now is None:
        from email_parser.timezone_utils import now_central
        now = now_central()
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    if not r:
        return {"error": f"no event {event_id}"}
    ev = dict(r)
    out = {"event_id": int(event_id), "event": ev.get("item_name")}
    why = why_not(ev, now, db_path)
    if why:
        return {**out, "status": "skipped", "why": why}
    rec = pp.course_recipients_for_event(ev, db_path)
    mgr = _manager_cc(ev.get("chapter"), db_path)
    out.update(to=rec.get("to"), cc=rec.get("cc") or [], manager_cc=mgr)
    if render is None:
        return {**out, "status": "would send", "dry_run": True,
                "note": "no renderer outside the app: the gap check runs at send time"}
    built = pp.build_event_print_pack(render, int(event_id), static_dir, db_path=db_path,
                                      force_scorecards=True)
    if not built or built.get("error"):
        return {**out, "status": "error", "why": (built or {}).get("error") or "nothing to print"}
    held = pp._unprintable(built)
    if held:
        out.update(status="held", why=held)
        if confirm is True:
            out["manager_notice"] = _gap_notice(ev, held, mgr, db_path)
        return out
    if confirm is not True:
        return {**out, "status": "would send", "dry_run": True,
                "parts": [p["slug"] for p in built.get("parts") or [] if p["slug"] in pp.COURSE_FILE_PARTS]}
    res = pp.send_course_files(built, db_path=db_path, extra_cc=mgr)
    try:
        db.log_message({"event_name": ev.get("item_name"), "channel": "email",
                        "recipient_name": "course contact", "recipient_address": rec.get("to"),
                        "subject": f"The Golf Fellowship print files — {ev.get('course') or ''} — {ev.get('event_date')}",
                        "body_preview": "noon Course Files", "status": "sent" if res.get("sent") else "failed",
                        "error_message": None if res.get("sent") else (res.get("why") or "Send failed"),
                        "sent_by": "course-files-noon", "event_id": int(event_id)}, db_path=db_path)
    except Exception:
        logger.exception("course files noon: could not log the send")
    try:
        db.log_agent_action("course-files-noon", "course_files_noon",
                            f"event {event_id}: {'sent' if res.get('sent') else 'FAILED'} to {rec.get('to')}"
                            f" cc {res.get('cc')}")
    except Exception:
        pass
    return {**out, "status": "sent" if res.get("sent") else "failed", "result": res}


def _gap_notice(ev: dict, why: str, mgr: str | None, db_path=None) -> dict:
    """One email per event to the manager: the noon Course Files are held."""
    from email_parser import database as db
    from email_parser.event_day_email import _creds, _graph_send
    from email_parser.invitations import _base_url
    key = GAP_KEY.format(int(ev["id"]))
    if db.get_app_setting(key, db_path=db_path):
        return {"status": "already told"}
    to = mgr or "kerry@thegolffellowship.com"
    creds = _creds()
    if not creds:
        return {"status": "no credentials"}
    link = f"{_base_url()}/events?event={int(ev['id'])}&view=pairings"
    html = (f"<p>The noon Course Files for <b>{ev.get('item_name')}</b> ({ev.get('course') or ''}) "
            f"did not go to the course: {why}.</p>"
            f"<p>Fix it on the event and the Tracker sends them at its next check (every 15 minutes "
            f"until one hour before the first tee), or send them yourself with the Course Files "
            f'button: <a href="{link}">open the event</a>.</p>'
            f"<p>The Tracker</p>")
    ok = _graph_send(creds, to, f"Course Files held: {ev.get('item_name')}", html,
                     cc="kerry@thegolffellowship.com" if to.lower() != "kerry@thegolffellowship.com" else None)
    if ok:
        db.set_app_setting(key, json.dumps({"to": to, "why": why}), db_path=db_path)
        try:
            db.log_agent_action("course-files-noon", "course_files_noon_held",
                                f"event {ev['id']}: {why[:200]}")
        except Exception:
            pass
    return {"status": "sent" if ok else "failed", "to": to}


def check(render, static_dir, now=None, db_path=None) -> dict:
    """The job: every event dated today."""
    from email_parser import database as db
    if not _on(db_path):
        return {"status": "off"}
    if now is None:
        from email_parser.timezone_utils import now_central
        now = now_central()
    with db._connect(db_path) as conn:
        ids = [int(x[0]) for x in conn.execute(
            "SELECT id FROM events WHERE substr(event_date, 1, 10) = ? "
            "AND COALESCE(status, 'active') = 'active'", (now.date().isoformat(),)).fetchall()]
    out = {}
    for eid in ids:
        try:
            out[eid] = run_event(eid, render, static_dir, confirm=True, now=now, db_path=db_path)
        except Exception as exc:
            logger.exception("course files noon failed for %s", eid)
            out[eid] = {"error": str(exc)}
    return {"status": "ran", "events": out}
