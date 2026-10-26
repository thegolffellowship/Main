"""THE PAYMENT REMINDER, one email everywhere (Kerry 2026-10-26: "our standard
template for those unpaid DOES include the link. We need to match these up"
... "go with mockup 3" ... "Let's also provide a link to see who's currently
registered. but not in a button").

Before this, the Remind tag, Remind All and the every-other-day 6 AM job each
carried their own copy of an old body with NO registration link, and Remind
All only reached shop RSVP-only rows. Now all of them (and the Messages
composer when it sends this template) build the message here:

- the WORDS are the "Payment Reminder" message template (Messages page), so
  Kerry edits one place;
- the FRAME is the invitation's house frame (dark masthead, chapter, "<Day>
  at <place>"), event_day_email.frame;
- {pay_button} is the store registration link as a button and refuses when
  the link is blank or expired (event_links); {roster_link} is a plain text
  link to the member page that lists who is registered;
- any blank or leftover {tag} HOLDS the message;
- once per person per event per day (app setting payment_reminder_sent:<id>),
  every send logged in message_log with event_id + customer_id;
- STOPS AT THE LOCK (Kerry 2026-10-26, CoS #2313: "Payment Reminders - Those
  stop at the 5:00p lock for any specific event. So the 4:50p you've been
  removed email is it for payment reminders for that event."): from 5:00 PM
  on the event's lock day (database.pairings_auto_weekdays: Monday for a
  Tuesday nine; E-1 for an undialled weekday) every path holds, the 6 AM job
  skips the event, and the composer refuses this template. Dial
  payment_reminder_stop_at_lock (on unless it reads off).
"""
from __future__ import annotations

import html as _html
import json
import logging
import os

logger = logging.getLogger(__name__)

TEMPLATE_NAME = "Payment Reminder"
STOP_DIAL = "payment_reminder_stop_at_lock"
LOCK_HOUR = 17
PAST_LOCK = "past the 5:00 PM lock: payment reminders stop there for this event"
SENT_KEY = "payment_reminder_sent:{event_id}"
ROSTER_LINK_TEXT = "See who's registered so far"

# The shipped words (mockup 3, Kerry 10/26). The live text is the template
# row; this is only the fallback when the row is missing.
DEFAULT_SUBJECT = "Payment Reminder — {event_name}"
DEFAULT_BODY = (
    "<p>Hi {player_name},</p>"
    "<p>This is a friendly reminder that we have you down for "
    "<strong>{event_place} on {event_date_long}</strong>, but we haven't "
    "received your payment yet.</p>"
    "<p>You can take care of it right here:</p>"
    "{pay_button}"
    "<p>{roster_link}</p>"
    "<p>Questions? Text {manager_name} at {manager_phone}.</p>"
    "<p>Thanks,<br>{manager_name}<br>The Golf Fellowship</p>"
)


def roster_url(event_id: int) -> str:
    from email_parser.invitations import _base_url
    return f"{_base_url()}/member/results/{int(event_id)}"


def roster_link_html(event_id: int) -> str:
    """A plain text link, not a button (Kerry 10/26)."""
    return (f'<a href="{_html.escape(roster_url(event_id))}" '
            f'style="color:#2563eb;text-decoration:underline;">{ROSTER_LINK_TEXT}</a>')


def event_vars(ev: dict, db_path=None) -> dict:
    """Every variable the template may use, for one event."""
    from email_parser.event_links import event_url_for_message, pay_button_html
    from email_parser.invitations import _context, _display_name
    ctx = _context(ev, db_path)
    url, problem = event_url_for_message(ev)
    return {
        "event_name": ev.get("item_name") or "",
        "event_place": _display_name(ev),
        "event_date_long": ctx["date_long"],
        "event_day": ctx["day"],
        "event_date": str(ev.get("event_date") or "")[:10],
        "course": ev.get("course") or "",
        "chapter": ctx["chapter"],
        "manager_name": ctx["manager_name"] if ctx["manager_name"] != "TGF" else "",
        "manager_phone": ctx["manager_phone"],
        "event_url": url or "",
        "pay_button": pay_button_html(url or ""),
        "roster_link": roster_link_html(int(ev["id"])),
        "_url_problem": problem or "",
    }


def frame_for(ev: dict, inner: str, db_path=None) -> str:
    """The invitation's house frame around a message body."""
    from email_parser.event_day_email import frame
    from email_parser.invitations import _context, _display_name
    ctx = _context(ev, db_path)
    place = _display_name(ev)
    # "2026 Fall Championship @ Kissing Tree" already names the place;
    # "Saturday at" only reads right in front of a plain course name.
    title = place if "@" in place else f"{ctx['day']} at {place}"
    return frame(inner, (ctx["chapter"] or "").upper(), title)


def _template(db_path=None) -> tuple:
    from email_parser import database as db
    try:
        for t in db.get_message_templates(db_path=db_path) or []:
            if (t.get("name") or "").strip().lower() == TEMPLATE_NAME.lower():
                return (t.get("id"), t.get("subject") or DEFAULT_SUBJECT,
                        t.get("html_body") or DEFAULT_BODY)
    except Exception:
        logger.exception("payment reminder: could not read the template")
    return None, DEFAULT_SUBJECT, DEFAULT_BODY


def lock_at(ev: dict, db_path=None):
    """When this event's groups are locked: 5:00 PM on its pairings day
    (the weekday dial's lead; the day before for an undialled weekday).
    None when the event has no date."""
    from datetime import date, datetime, time, timedelta
    from email_parser import database as db
    try:
        d = date.fromisoformat(str(ev.get("event_date") or "")[:10])
    except ValueError:
        return None
    lead = db.pairings_auto_weekdays(db_path).get(db._WEEKDAY_NAMES[d.weekday()], 1)
    return datetime.combine(d - timedelta(days=lead), time(LOCK_HOUR, 0))


def past_lock(ev: dict, now=None, db_path=None) -> bool:
    """True from the event's lock on, unless dial payment_reminder_stop_at_lock
    reads off."""
    from email_parser import database as db
    from email_parser.timezone_utils import now_central
    try:
        if (db.get_app_setting(STOP_DIAL, db_path=db_path) or "").strip().lower() in (
                "off", "0", "false", "no"):
            return False
    except Exception:
        pass
    lock = lock_at(ev, db_path)
    return lock is not None and (now or now_central()) >= lock


def build(ev: dict, person: dict, db_path=None) -> dict:
    """{subject, html, held, template_id} for one person on one event."""
    from email_parser.fetcher import normalize_email_html, render_msg_template
    tid, subj_t, body_t = _template(db_path)
    v = event_vars(ev, db_path)
    first = (person.get("first_name") or (person.get("name") or "").split(" ")[0] or "there").strip()
    v = {**v, "player_name": _html.escape(first)}
    held = []
    if "{pay_button}" in body_t or "{event_url}" in body_t:
        if not v["event_url"]:
            held.append(f"no registration link ({v['_url_problem'] or 'not set'})")
    for k in ("manager_name", "manager_phone"):
        if "{%s}" % k in body_t and not v[k]:
            held.append(f"no {k.replace('_', ' ')} for {v['chapter'] or 'this chapter'}")
    vars_ = {k: x for k, x in v.items() if not k.startswith("_")}
    subject = render_msg_template(subj_t, vars_)
    inner = render_msg_template(normalize_email_html(body_t), vars_)
    left = _tags(subject + inner)
    if left:
        held.append("leftover {" + "}, {".join(sorted(set(left))) + "}")
    return {"subject": subject, "html": frame_for(ev, inner, db_path), "held": held,
            "template_id": tid}


def _tags(text: str) -> list:
    import re
    return re.findall(r"\{([a-z_]+)\}", text)


def _sent_today(event_id: int, db_path=None) -> dict:
    from email_parser import database as db
    try:
        return json.loads(db.get_app_setting(SENT_KEY.format(event_id=int(event_id)),
                                              db_path=db_path) or "{}")
    except Exception:
        return {}


def rsvp_only_people(event_id: int, db_path=None) -> list:
    """Everyone the Events page shows as RSVP-only for this event (shop
    RSVP-only rows AND RSVPs from invitations / Golf Genius), by customer_id."""
    from email_parser import database as db
    conn = db.get_connection(db_path)
    try:
        rows = db._event_roster_rows(conn, int(event_id))
    finally:
        conn.close()
    out, seen = [], set()
    for r in rows:
        if not r.get("rsvp_only"):
            continue
        cid = r.get("customer_id")
        email = (r.get("customer_email") or "").strip()
        key = int(cid) if cid is not None else email.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({"customer_id": int(cid) if cid is not None else None, "email": email,
                    "name": r.get("name") or r.get("customer") or ""})
    return out


def send(event_id: int, people: list, sent_by: str = "manager", force: bool = False,
         db_path=None) -> dict:
    """Send the reminder to each person (by customer_id, or by `email` for an
    RSVP with no customer card). Once per person per event per day unless
    force. Returns what happened to each."""
    from email_parser import database as db
    from email_parser.fetcher import send_mail_graph
    from email_parser.invitations import _event, _send_email
    from email_parser.timezone_utils import today_central_str
    conn = db.get_connection(db_path)
    try:
        ev = _event(conn, int(event_id))
        if not ev:
            return {"error": f"no event {event_id}"}
        emails = {}
        for p in people:
            if p.get("customer_id") is not None:
                emails[int(p["customer_id"])] = _send_email(conn, int(p["customer_id"]))
        firsts = {int(r[0]): r[1] for r in conn.execute(
            f"SELECT customer_id, first_name FROM customers WHERE customer_id IN "
            f"({','.join('?' * len(emails)) or 'NULL'})", tuple(emails)).fetchall()}
    finally:
        conn.close()
    creds = [os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID",
                                    "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")]
    if not all(creds):
        return {"error": "Email credentials not configured"}
    today = today_central_str()
    sent_map = _sent_today(event_id, db_path)
    out = {"event_id": int(event_id), "sent": [], "failed": [], "held": [],
           "no_email": [], "already_today": []}
    if past_lock(ev, db_path=db_path):
        out["held"] = [{"customer_id": p.get("customer_id"), "name": p.get("name") or "",
                        "why": [PAST_LOCK]} for p in people]
        return out
    for p in people:
        cid = p.get("customer_id")
        name = p.get("name") or ""
        if cid is not None:
            cid = int(cid)
            to = emails.get(cid) or (p.get("email") or "").strip()
            key = str(cid)
        else:
            to = (p.get("email") or "").strip()
            key = to.lower()
        if not to:
            out["no_email"].append({"customer_id": cid, "name": name})
            continue
        if not force and sent_map.get(key) == today:
            out["already_today"].append({"customer_id": cid, "name": name})
            continue
        msg = build(ev, {"first_name": firsts.get(cid) if cid is not None else None,
                         "name": name}, db_path)
        if msg["held"]:
            out["held"].append({"customer_id": cid, "name": name, "why": msg["held"]})
            continue
        ok = False
        try:
            ok = send_mail_graph(tenant_id=creds[0], client_id=creds[1], client_secret=creds[2],
                                 from_address=creds[3], to_address=to,
                                 subject=msg["subject"], html_body=msg["html"])
        except Exception:
            logger.exception("payment reminder: send failed for %s", cid)
        try:
            db.log_message({"event_name": ev.get("item_name"), "template_id": msg["template_id"],
                            "channel": "email", "recipient_name": name, "recipient_address": to,
                            "subject": msg["subject"], "body_preview": "payment reminder",
                            "status": "sent" if ok else "failed",
                            "error_message": None if ok else "Send failed",
                            "sent_by": sent_by, "event_id": int(event_id), "customer_id": cid},
                           db_path=db_path)
        except Exception:
            logger.exception("payment reminder: could not log the send")
        if ok:
            sent_map[key] = today
            out["sent"].append({"customer_id": cid, "name": name})
        else:
            out["failed"].append({"customer_id": cid, "name": name})
    try:
        db.set_app_setting(SENT_KEY.format(event_id=int(event_id)), json.dumps(sent_map),
                           db_path=db_path)
    except Exception:
        logger.exception("payment reminder: could not save the sent map")
    return out


def preview(event_id: int, customer_id: int | None = None, db_path=None) -> dict:
    """Render the reminder for one person (or a sample) without sending."""
    from email_parser import database as db
    from email_parser.invitations import _event
    conn = db.get_connection(db_path)
    try:
        ev = _event(conn, int(event_id))
        first = None
        if customer_id is not None:
            r = conn.execute("SELECT first_name FROM customers WHERE customer_id = ?",
                             (int(customer_id),)).fetchone()
            first = r[0] if r else None
    finally:
        conn.close()
    if not ev:
        return {"error": f"no event {event_id}"}
    return build(ev, {"first_name": first or "Neal"}, db_path)
