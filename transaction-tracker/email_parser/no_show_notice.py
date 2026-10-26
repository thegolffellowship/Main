"""THE COURSE NO-SHOW NOTICE (Kerry 2026-09-30, mailbox #1021, ratified;
Pairings Spec v1.4 12.2; Event Ops NO-SHOW SCORER SEQUENCE item 3; built
10/26 for 10/27).

When the scorer marks a player missing ("Player missing" on /member/score)
and his group has played about 3 holes (dial no_show_course_notice_holes,
default 3; Kerry 10/26: "Both should be at 3p"), the course gets ONE email for the event naming every no-show
so far: "No-shows today at <course>: <names>. Thanks, <manager>".

- To the course's primary TGF contact, CC its other TGF contacts
  (print_pack.course_recipients_for_event, the one reader) and the chapter
  manager (after_lock._manager_cc).
- Once per event (app setting no_show_notice_sent:<event_id>), every send in
  message_log and agent_action_log. Nothing goes with no course contact on file.
- Who counts: a player marked "No, take him off this card", or still
  "Don't know yet" (or blank) once his group has scored the notice's holes.
  "Running late" never counts.
- Dial no_show_course_notice (on unless off). Job every 5 minutes on event
  day. Read-only bridge scoring-no-show-notice:<event_id>[|preview[|<staff>]].
This module never reads se_* tables; score_entry.event_no_shows is its source.
"""
from __future__ import annotations

import html as _html
import json
import logging

logger = logging.getLogger(__name__)

DIAL = "no_show_course_notice"
HOLES_DIAL = "no_show_course_notice_holes"
HOLES_DEFAULT = 3
SENT_KEY = "no_show_notice_sent:{}"

SUBJECT = "No-shows today at {course}"
BODY = "<p>No-shows today at {course}: {names}.</p><p>Thanks,<br>{manager}</p>"


def _setting(key, db_path=None):
    from email_parser.database import get_app_setting
    try:
        return get_app_setting(key, db_path=db_path)
    except Exception:
        return None


def dial_on(db_path=None) -> bool:
    return (_setting(DIAL, db_path) or "").strip().lower() not in ("0", "off", "false", "no")


def notice_holes(db_path=None) -> int:
    try:
        return max(1, int(_setting(HOLES_DIAL, db_path) or HOLES_DEFAULT))
    except (TypeError, ValueError):
        return HOLES_DEFAULT


def _join(names: list) -> str:
    names = [n for n in names if n]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def build(event_id: int, db_path=None) -> dict:
    """{to, cc, subject, html, names, held[], due} for one event. Sends nothing."""
    from email_parser import database as db
    from email_parser.score_entry import event_no_shows
    from email_parser.print_pack import course_recipients_for_event
    from email_parser.after_lock import _manager_cc
    from email_parser.pairings_approval import manager_for
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    if not r:
        return {"error": f"no event {event_id}"}
    ev = dict(r)
    n = notice_holes(db_path)
    rows = event_no_shows(int(event_id), db_path).get("no_shows") or []
    due = [x for x in rows if (x.get("group_holes_played") or 0) >= n and x.get("name")]
    names = sorted({x["name"] for x in due})
    rec = course_recipients_for_event(ev, db_path)
    mgr = manager_for(ev.get("chapter"), db_path) or {}
    held = []
    if not rec.get("ok"):
        held.append(rec.get("why") or "no course contact on file")
    if not (mgr.get("name") or "").strip():
        held.append("no manager name for this chapter")
    course = (ev.get("course") or "").strip()
    if not course:
        held.append("this event has no course name")
    vals = {"course": _html.escape(course), "names": _html.escape(_join(names)),
            "manager": _html.escape((mgr.get("name") or "").strip())}
    cc = list(rec.get("cc") or [])
    m = _manager_cc(ev.get("chapter"), db_path)
    if m and m not in cc and m != rec.get("to"):
        cc.append(m)
    return {"event_id": int(event_id), "event": ev.get("item_name"), "event_date": ev.get("event_date"),
            "to": rec.get("to"), "cc": cc, "names": names, "pending": [x for x in rows if x not in due],
            "holes": n, "held": held, "subject": SUBJECT.format(course=course),
            "html": BODY.format(**vals), "sent": _setting(SENT_KEY.format(int(event_id)), db_path)}


def run_event(event_id: int, confirm: bool = False, db_path=None, sender=None) -> dict:
    """Send (confirm=True) or preview one event's notice."""
    from email_parser import database as db
    b = build(event_id, db_path)
    if b.get("error"):
        return b
    out = {k: v for k, v in b.items() if k != "html"}
    if b["sent"]:
        return {**out, "status": "already sent"}
    if not b["names"]:
        return {**out, "status": "nothing to send", "why": f"no no-show whose group has played {b['holes']} holes"}
    if b["held"]:
        return {**out, "status": "held"}
    if confirm is not True:
        return {**out, "status": "would send", "dry_run": True}
    if sender is None:
        from email_parser.event_day_email import _creds, _graph_send
        creds = _creds()
        if not creds:
            return {**out, "status": "error", "why": "Email credentials not configured on server"}
        sender = lambda to, s, h, cc: _graph_send(creds, to, s, h, cc=",".join(cc) or None)  # noqa: E731
    ok = False
    try:
        ok = bool(sender(b["to"], b["subject"], b["html"], b["cc"]))
    except Exception:
        logger.exception("no-show notice send failed for %s", event_id)
    try:
        db.log_message({"event_name": b["event"], "channel": "email", "recipient_name": "course contact",
                        "recipient_address": b["to"], "subject": b["subject"],
                        "body_preview": "no-shows: " + ", ".join(b["names"]),
                        "status": "sent" if ok else "failed", "sent_by": "no-show-notice",
                        "event_id": int(event_id)}, db_path=db_path)
        db.log_agent_action("no-show-notice", "no_show_notice",
                            f"event {event_id}: {'sent' if ok else 'FAILED'} to {b['to']} cc {b['cc']}: "
                            + ", ".join(b["names"]))
    except Exception:
        pass
    if ok:
        db.set_app_setting(SENT_KEY.format(int(event_id)),
                           json.dumps({"names": b["names"], "to": b["to"]}), db_path=db_path)
    return {**out, "status": "sent" if ok else "failed"}


def check(now=None, db_path=None, sender=None) -> dict:
    """The job: every active event dated today."""
    from email_parser import database as db
    if not dial_on(db_path):
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
            r = run_event(eid, confirm=True, db_path=db_path, sender=sender)
            if r.get("status") not in ("nothing to send", "already sent"):
                out[eid] = r.get("status")
        except Exception as exc:
            logger.exception("no-show notice failed for %s", eid)
            out[eid] = f"error: {exc}"
    return {"status": "ran", "events": out}


def send_preview(event_id: int, to_address: str | None = None, db_path=None) -> dict:
    """ONE sample to staff only. Nothing goes to the course."""
    from email_parser.event_day_email import _creds, _graph_send
    from email_parser.recap_mail import staff_only, _addrs
    to = _addrs(to_address) or ["kerry@thegolffellowship.com"]
    bad = staff_only(to, lambda k: _setting(k, db_path))
    if bad:
        return {"error": f"a no-show notice preview goes to TGF staff only; refused {bad}"}
    b = build(event_id, db_path)
    if b.get("error"):
        return b
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    head = (f"<p><strong>No-show notice PREVIEW</strong>. Nothing went to the course. Would go To "
            f"{_html.escape(str(b['to']))}, CC {_html.escape(', '.join(b['cc']) or 'nobody')}. "
            f"Held now: {_html.escape('; '.join(b['held']) or 'nothing')}.</p><hr>")
    ok = _graph_send(creds, ",".join(to), "PREVIEW: " + b["subject"], head + b["html"])
    return {"status": "sent" if ok else "failed", "to": to}
