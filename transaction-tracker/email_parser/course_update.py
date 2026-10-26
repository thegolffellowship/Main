"""THE COURSE UPDATE BEFORE THE LOCK (Kerry 2026-10-26, CoS #2307 item 2,
#2331 item 9; spec docs/claude/spec-course-staff-timeline-v0.md row "Sunday
noon"): "update to the course contact with the currently registered list,
manager CC'd, a live link so they can follow along, and notice that we lock
foursome counts at 5:00 PM Monday, so please allow us to grow."

When: noon the day before the event's lock (database.event_lock_at): Sunday
noon for a Tuesday nine (locks Monday 5:00 PM), Tuesday noon for a Saturday
event (locks Wednesday). Once per event. Job every 15 minutes, noon to 2:45 PM.
To the course's primary TGF contact, CC the other TGF contacts and the
chapter manager (print_pack.course_recipients_for_event, the one reader).
Nothing goes when no contact is on file.

The words are below; they send only when app setting course_update_approved
equals their hash (Kerry's stamp) AND dial course_update_auto is on. Any blank
holds the message. Staff-only preview; read-only bridge
scoring-course-update:<event_id>[|preview[|<staff addr>]].
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DIAL = "course_update_auto"
STAMP = "course_update_approved"
SENT_KEY = "course_update_sent"
SEND_HOUR = 12
SEND_UNTIL_HOUR = 15

SUBJECT = "TGF {day}: who's registered so far ({n} players)"
BODY = ("<p>Hi {first_name},</p>"
        "<p>Here's who's registered for <strong>{day}, {date_long}</strong> at {course} so far "
        "({n} players):</p>{roster}"
        "<p>You can follow along live here: {link}</p>"
        "<p>We lock our foursome counts at <strong>5:00 PM {lock_day}</strong>. Please allow us "
        "room to grow until then.</p>"
        "<p>Thanks,<br>{manager_name}<br>The Golf Fellowship</p>")


def template_hash() -> str:
    return hashlib.sha256(("\x1f".join((SUBJECT, BODY))).encode()).hexdigest()[:16]


def _setting(key, db_path=None):
    from email_parser.database import get_app_setting
    try:
        return get_app_setting(key, db_path=db_path)
    except Exception:
        return None


def approval_state(db_path=None) -> dict:
    h = template_hash()
    return {"template_hash": h, "approved": (_setting(STAMP, db_path) or "") == h,
            "dial_on": (_setting(DIAL, db_path) or "").strip().lower() == "on"}


def send_at(ev: dict, db_path=None):
    """Noon the day before the lock."""
    from email_parser import database as db
    lock = db.event_lock_at(ev, db_path)
    if lock is None:
        return None
    return datetime.combine(lock.date() - timedelta(days=1), datetime.min.time()).replace(hour=SEND_HOUR)


def build(event_id: int, db_path=None, preview_to_name: str | None = None) -> dict:
    """{to, cc, subject, html, held[]} for one event. Sends nothing."""
    from email_parser import database as db
    from email_parser.event_day_email import frame
    from email_parser.invitations import _context, _display_name, _base_url
    from email_parser.print_pack import course_recipients_for_event
    from email_parser.after_lock import _manager_cc
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
        if not r:
            return {"error": f"no event {event_id}"}
        ev = dict(r)
        roster = [x for x in db._event_roster_rows(conn, int(event_id)) if not x.get("rsvp_only")]
    ctx = _context(ev, db_path)
    rec = course_recipients_for_event(ev, db_path)
    lock = db.event_lock_at(ev, db_path)
    names = sorted({(x.get("name") or "").strip() for x in roster if (x.get("name") or "").strip()})
    held = []
    if not rec.get("ok"):
        held.append(rec.get("why") or "no course contact")
    if not names:
        held.append("nobody registered yet")
    mgr = (ctx.get("manager_name") or "").strip()
    if not mgr or mgr == "TGF":
        held.append("no manager name for this chapter")
    first = (preview_to_name or (rec.get("to_name") or "").split(" ")[0] or "").strip()
    if not first:
        held.append("no first name for the course contact")
    link = f"{_base_url()}/member/teesheet/{int(event_id)}"
    vals = {"first_name": _html.escape(first or "there"), "day": _html.escape(ctx["day"]),
            "date_long": _html.escape(ctx["date_long"]),
            "course": _html.escape(_display_name(ev) or ev.get("course") or ""),
            "n": len(names),
            "roster": "<ul>" + "".join(f"<li>{_html.escape(n)}</li>" for n in names) + "</ul>",
            "link": f'<a href="{_html.escape(link)}" style="color:#2563eb;">{_html.escape(link)}</a>',
            "lock_day": (lock.strftime("%A") if lock else ""),
            "manager_name": _html.escape(mgr)}
    if not vals["lock_day"]:
        held.append("no lock date")
    subject = SUBJECT.format(**vals)
    inner = BODY.format(**vals)
    cc = list(rec.get("cc") or [])
    m = _manager_cc(ev.get("chapter"), db_path)
    if m and m not in cc and m != rec.get("to"):
        cc.append(m)
    return {"event_id": int(event_id), "event": ev.get("item_name"), "to": rec.get("to"), "cc": cc,
            "subject": subject, "held": held, "players": len(names),
            "send_at": (send_at(ev, db_path).isoformat() if send_at(ev, db_path) else None),
            "html": frame(inner, (ctx.get("chapter") or "").upper(), f"{ctx['day']} at {vals['course']}"),
            **approval_state(db_path)}


def _sent(db_path=None) -> dict:
    try:
        v = json.loads(_setting(SENT_KEY, db_path) or "{}")
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def check(now=None, db_path=None, sender=None) -> dict:
    """The job: each event whose send time has come, once."""
    from email_parser import database as db
    st = approval_state(db_path)
    if not st["dial_on"]:
        return {"status": f"{DIAL} is not on"}
    if not st["approved"]:
        return {"status": "wording not approved"}
    if now is None:
        from email_parser.timezone_utils import now_central
        now = now_central()
    sent = _sent(db_path)
    days = [(now.date() + timedelta(days=i)).isoformat() for i in range(1, 6)]
    with db._connect(db_path) as conn:
        evs = [dict(r) for r in conn.execute(
            "SELECT * FROM events WHERE COALESCE(status, 'active') = 'active' AND substr(event_date, 1, 10) "
            "IN (?, ?, ?, ?, ?)", days)]
    out = {}
    for ev in evs:
        eid = str(ev["id"])
        at = send_at(ev, db_path)
        if at is None or eid in sent or not (at <= now < at.replace(hour=SEND_UNTIL_HOUR)):
            continue
        b = build(int(ev["id"]), db_path)
        if b.get("error") or b["held"]:
            out[ev["id"]] = {"held": b.get("held") or b.get("error")}
            continue
        if sender is None:
            from email_parser.event_day_email import _creds, _graph_send
            creds = _creds()
            if not creds:
                return {"error": "Email credentials not configured on server"}
            sender = lambda to, s, h, cc: _graph_send(creds, to, s, h, cc=",".join(cc) or None)  # noqa: E731
        ok = False
        try:
            ok = bool(sender(b["to"], b["subject"], b["html"], b["cc"]))
        except Exception:
            logger.exception("course update send failed for %s", eid)
        try:
            db.log_message({"event_name": ev.get("item_name"), "channel": "email", "recipient_name": "course contact",
                            "recipient_address": b["to"], "subject": b["subject"],
                            "body_preview": f"course update ({b['players']} players)",
                            "status": "sent" if ok else "failed", "sent_by": "course_update",
                            "event_id": int(ev["id"])}, db_path=db_path)
            db.log_agent_action("course-update", "course_update",
                                f"event {eid} {ev.get('item_name')}: {'sent' if ok else 'FAILED'} to {b['to']}")
        except Exception:
            pass
        if ok:
            sent[eid] = now.strftime("%Y-%m-%d %H:%M")
            db.set_app_setting(SENT_KEY, json.dumps(sent), db_path=db_path)
        out[ev["id"]] = {"sent": ok, "to": b["to"], "cc": b["cc"]}
    return {"status": "ran", "events": out}


def send_preview(event_id: int, to_address: str | None = None, db_path=None) -> dict:
    """ONE sample to staff only, for Kerry's wording stamp."""
    from email_parser.event_day_email import _creds, _graph_send
    from email_parser.recap_mail import staff_only, _addrs
    to = _addrs(to_address) or ["kerry@thegolffellowship.com"]
    bad = staff_only(to, lambda k: _setting(k, db_path))
    if bad:
        return {"error": f"a course-update preview goes to TGF staff only; refused {bad}"}
    b = build(event_id, db_path, preview_to_name="Kerry")
    if b.get("error"):
        return b
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    head = (f"<p><strong>Course update PREVIEW</strong>. Nothing went to the course. Would go To "
            f"{_html.escape(str(b['to']))}, CC {_html.escape(', '.join(b['cc']) or 'nobody')}. "
            f"Wording <code>{b['template_hash']}</code>: {'APPROVED' if b['approved'] else 'NOT approved'}."
            f" Held now: {_html.escape('; '.join(b['held']) or 'nothing')}.</p><hr>")
    ok = _graph_send(creds, ",".join(to), "PREVIEW: " + b["subject"], head + b["html"])
    return {"status": "sent" if ok else "failed", "to": to, "template_hash": b["template_hash"]}
