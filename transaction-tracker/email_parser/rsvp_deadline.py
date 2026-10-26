"""THE RSVP PAYMENT DEADLINE (Kerry 2026-10-26, CoS #2307 item 4, Kerry's own
proposal): "I want the last 'warning' email to go out ... at 1:00p to let him
know we haven't received payment, and the implications if not received by
5:00p. And then the 5:00p email if he hasn't made payment" ... "Those should
be automated emails sent thru the tracker based on our RSVP rules."

For each event whose groups the 5:00 PM pairings run builds today (its
lock day: Monday for a Tuesday nine; database.pairings_auto_weekdays):
- WARN, from 1:00 PM: every unpaid RSVP-only player (the Events page's
  RSVP-only rows, payment_reminder.rsvp_only_people) gets one email: pay
  before 5:00 PM or the spot is released when the groups are built.
- RELEASE, 4:50-4:59 PM, before the 5:00 PM pairings run: anyone still
  RSVP-only WHO WAS WARNED is taken off the roster and gets one email
  saying so (an RSVP made after the last warning is never released). If seats
  are open they can still register; if not, reply for the waitlist.

How a spot is released: an `rsvp_email_overrides` row (status not_playing),
the same mark the Events page sets by hand and the roster already honours.
Nothing is deleted; clearing the override on the Events page undoes it. A
registration later puts the person back on the roster as registered. A
shop $0 RSVP-only ORDER row is never touched here (it is a row in the
order ledger); it is reported and raises one COO item instead.

Never sent to a known mail scanner (invitations.known_scanner, #2307: "Do
NOT send 'pay or lose your spot' to known or likely scanners") and never to
an event in payment_reminder_exclude_events. Once per person per event per
kind (app setting rsvp_deadline_sent:<event_id>). Every send in message_log
with event_id + customer_id; every release in agent_action_log.
Dial rsvp_deadline_auto (on unless it reads off).

Kerry 2026-10-26: "Can you make the RSVP emails cc me for the after NOON
Monday emails?" Every warning and release is CC'd to app setting
rsvp_deadline_cc (default Kerry's address; "off" stops it).
"""
from __future__ import annotations

import html as _html
import json
import logging
import os

logger = logging.getLogger(__name__)

DIAL = "rsvp_deadline_auto"
CC_KEY = "rsvp_deadline_cc"
CC_DEFAULT = "kerry@thegolffellowship.com"
SENT_KEY = "rsvp_deadline_sent:{event_id}"
WARN_FROM = (13, 0)        # 1:00 PM Central, E-1
RELEASE_FROM = (16, 50)    # 4:50 PM, before the 5:00 PM pairings run
RELEASE_UNTIL = (17, 0)

WARN_SUBJECT = "{event_place} tomorrow: payment needed by 5:00 PM today"
WARN_BODY = (
    "<p>Hi {player_name},</p>"
    "<p>We have you down for <strong>{event_place} on {event_date_long}</strong>, but we "
    "haven't received your payment yet.</p>"
    "<p>Groups are set at <strong>5:00 PM today</strong>. If your payment isn't in by then, "
    "we'll have to release your spot so the groups can be built without you.</p>"
    "<p>You can take care of it right here:</p>"
    "{pay_button}"
    "<p>{roster_link}</p>"
    "<p>If you can't make it this week, just reply and let us know.</p>"
    "<p>Questions? Text {manager_name} at {manager_phone}.</p>"
    "<p>Thanks,<br>{manager_name}<br>The Golf Fellowship</p>"
)
RELEASE_SUBJECT = "{event_place}: your spot has been released"
RELEASE_BODY = (
    "<p>Hi {player_name},</p>"
    "<p>We didn't receive your payment by 5:00 PM, so we've released your spot for "
    "<strong>{event_place} on {event_date_long}</strong>, and the groups are being built "
    "without you.</p>"
    "<p>If a spot is still open, you can still register and we'll fit you in:</p>"
    "{pay_button}"
    "<p>If the groups are full, reply to this email and we'll put you on the waitlist.</p>"
    "<p>We hope to see you at the next one.</p>"
    "<p>Thanks,<br>{manager_name}<br>The Golf Fellowship</p>"
)


def _on(db_path=None) -> bool:
    from email_parser import database as db
    try:
        return (db.get_app_setting(DIAL, db_path=db_path) or "on").strip().lower() != "off"
    except Exception:
        return True


def cc_address(db_path=None) -> str | None:
    """Who is copied on every warning and release (rsvp_deadline_cc)."""
    from email_parser import database as db
    try:
        v = (db.get_app_setting(CC_KEY, db_path=db_path) or "").strip()
    except Exception:
        v = ""
    if v.lower() == "off":
        return None
    return v or CC_DEFAULT


def _sent(event_id: int, db_path=None) -> dict:
    from email_parser import database as db
    try:
        return json.loads(db.get_app_setting(SENT_KEY.format(event_id=int(event_id)),
                                              db_path=db_path) or "{}")
    except Exception:
        return {}


def _save_sent(event_id: int, m: dict, db_path=None) -> None:
    from email_parser import database as db
    db.set_app_setting(SENT_KEY.format(event_id=int(event_id)), json.dumps(m), db_path=db_path)


def _excluded_events(db_path=None) -> set:
    from email_parser import database as db
    try:
        return {int(x) for x in json.loads(
            db.get_app_setting("payment_reminder_exclude_events", db_path=db_path) or "[]")}
    except Exception:
        return set()


def build(ev: dict, person: dict, kind: str, db_path=None) -> dict:
    """{subject, html, held} for one person. Same variables, frame and holds
    as the payment reminder (payment_reminder.event_vars / frame_for)."""
    from email_parser.fetcher import normalize_email_html, render_msg_template
    from email_parser import payment_reminder as pr
    subj_t, body_t = ((WARN_SUBJECT, WARN_BODY) if kind == "warn"
                      else (RELEASE_SUBJECT, RELEASE_BODY))
    v = pr.event_vars(ev, db_path)
    first = (person.get("first_name") or (person.get("name") or "").split(" ")[0] or "there").strip()
    held = []
    if not v["event_url"]:
        held.append(f"no registration link ({v['_url_problem'] or 'not set'})")
    for k in ("manager_name", "manager_phone"):
        if "{%s}" % k in body_t and not v[k]:
            held.append(f"no {k.replace('_', ' ')} for {v['chapter'] or 'this chapter'}")
    vars_ = {k: x for k, x in v.items() if not k.startswith("_")}
    vars_["player_name"] = _html.escape(first)
    subject = render_msg_template(subj_t, {**vars_, "event_place": v["event_place"]})
    inner = render_msg_template(normalize_email_html(body_t), vars_)
    left = pr._tags(subject + inner)
    if left:
        held.append("leftover {" + "}, {".join(sorted(set(left))) + "}")
    return {"subject": subject, "html": pr.frame_for(ev, inner, db_path), "held": held}


def plan(event_id: int, kind: str, db_path=None) -> dict:
    """Who would get the WARN or the RELEASE for this event right now."""
    from email_parser import database as db
    from email_parser import invitations as inv
    from email_parser import payment_reminder as pr
    conn = db.get_connection(db_path)
    try:
        ev = inv._event(conn, int(event_id))
        people = pr.rsvp_only_people(int(event_id), db_path=db_path) if ev else []
        firsts, emails, order_rows = {}, {}, set()
        for p in people:
            cid = p.get("customer_id")
            if cid is None:
                continue
            r = conn.execute("SELECT first_name FROM customers WHERE customer_id = ?",
                             (int(cid),)).fetchone()
            firsts[int(cid)] = r[0] if r else None
            emails[int(cid)] = inv._send_email(conn, int(cid))
        if ev:
            for r in conn.execute(
                    "SELECT customer_id FROM items WHERE customer_id IS NOT NULL "
                    "AND COALESCE(transaction_status, 'active') = 'rsvp_only' "
                    "AND (event_id = ? OR lower(item_name) = lower(?))",
                    (int(event_id), ev.get("item_name") or "")).fetchall():
                order_rows.add(int(r[0]))
    finally:
        conn.close()
    if not ev:
        return {"error": f"no event {event_id}"}
    sent = _sent(event_id, db_path)
    out = {"event_id": int(event_id), "event": ev.get("item_name"), "kind": kind,
           "send": [], "skip": []}
    for p in people:
        cid = p.get("customer_id")
        key = str(cid) if cid is not None else (p.get("email") or "").lower()
        row = {"customer_id": cid, "name": p.get("name") or "",
               "email": emails.get(int(cid)) if cid is not None else (p.get("email") or None)}
        if cid is not None and inv.known_scanner(int(cid), db_path=db_path):
            out["skip"].append({**row, "why": "known mail scanner"})
        elif not row["email"]:
            out["skip"].append({**row, "why": "no email on file"})
        elif sent.get(f"{kind}:{key}"):
            out["skip"].append({**row, "why": f"{kind} already sent {sent[f'{kind}:{key}']}"})
        elif kind == "release" and not sent.get(f"warn:{key}"):
            out["skip"].append({**row, "why": "never warned: not released"})
        elif kind == "release" and cid is not None and int(cid) in order_rows:
            out["skip"].append({**row, "why": "shop RSVP-only order row: release by hand"})
        else:
            out["send"].append({**row, "key": key, "first_name": firsts.get(int(cid)) if cid is not None else None})
    return out


def _release_mark(ev: dict, email: str, cid, db_path=None) -> None:
    """Take the RSVP off the roster: the Events page's own not_playing mark."""
    from email_parser import database as db
    conn = db.get_connection(db_path)
    try:
        addrs = {email.strip().lower()}
        if cid is not None:
            for r in conn.execute("SELECT DISTINCT lower(player_email) FROM rsvps WHERE customer_id = ? "
                                  "AND player_email IS NOT NULL AND player_email <> ''",
                                  (int(cid),)).fetchall():
                addrs.add(r[0])
    finally:
        conn.close()
    for a in sorted(x for x in addrs if x):
        db.set_rsvp_email_override(a, ev["item_name"], "not_playing", db_path=db_path)


def run(event_id: int, kind: str, confirm: bool = False, db_path=None) -> dict:
    """Send the WARN or the RELEASE (with its roster release) for one event.
    Dry run unless confirm."""
    from email_parser import database as db
    from email_parser import invitations as inv
    from email_parser.fetcher import send_mail_graph
    from email_parser.timezone_utils import now_central
    if kind not in ("warn", "release"):
        return {"error": "kind must be warn or release"}
    pl = plan(event_id, kind, db_path)
    if pl.get("error"):
        return pl
    conn = db.get_connection(db_path)
    try:
        ev = inv._event(conn, int(event_id))
    finally:
        conn.close()
    held = []
    msgs = []
    for p in pl["send"]:
        m = build(ev, p, kind, db_path)
        (held if m["held"] else msgs).append({**p, **({"why": m["held"]} if m["held"] else {"msg": m})})
    out = {**{k: pl[k] for k in ("event_id", "event", "kind", "skip")},
           "send": [{k: x[k] for k in ("customer_id", "name", "email")} for x in msgs],
           "held": [{k: x[k] for k in ("customer_id", "name", "why")} for x in held]}
    if confirm is not True:
        if msgs:
            out["sample"] = {"subject": msgs[0]["msg"]["subject"], "html": msgs[0]["msg"]["html"]}
        return {**out, "dry_run": True}
    creds = [os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID",
                                    "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")]
    if not all(creds):
        return {**out, "error": "Email credentials not configured"}
    sent = _sent(event_id, db_path)
    cc = cc_address(db_path)
    stamp = now_central().strftime("%Y-%m-%d %H:%M")
    done, failed = [], []
    for x in msgs:
        if kind == "release":
            try:
                _release_mark(ev, x["email"], x["customer_id"], db_path)
                db.log_agent_action("rsvp-deadline", "rsvp_deadline_release",
                                    f"event {event_id} customer {x['customer_id']} {x['name']}: "
                                    "unpaid at 5:00 PM, marked not_playing")
            except Exception:
                logger.exception("rsvp deadline: release failed for %s", x["customer_id"])
                failed.append(x["name"])
                continue
        ok = False
        try:
            ok = send_mail_graph(tenant_id=creds[0], client_id=creds[1], client_secret=creds[2],
                                 from_address=creds[3], to_address=x["email"],
                                 subject=x["msg"]["subject"], html_body=x["msg"]["html"],
                                 cc_address=cc)
        except Exception:
            logger.exception("rsvp deadline: send failed for %s", x["customer_id"])
        try:
            db.log_message({"event_name": ev.get("item_name"), "template_id": None, "channel": "email",
                            "recipient_name": x["name"], "recipient_address": x["email"],
                            "subject": x["msg"]["subject"], "body_preview": f"rsvp deadline {kind}",
                            "status": "sent" if ok else "failed",
                            "error_message": None if ok else "Send failed", "sent_by": "rsvp-deadline",
                            "event_id": int(event_id), "customer_id": x["customer_id"]},
                           db_path=db_path)
        except Exception:
            logger.exception("rsvp deadline: could not log the send")
        if ok:
            sent[f"{kind}:{x['key']}"] = stamp
            done.append(x["name"])
        else:
            failed.append(x["name"])
    _save_sent(event_id, sent, db_path)
    if kind == "release":
        hand = [s for s in pl["skip"] if s["why"].startswith("shop RSVP-only")]
        if hand:
            try:
                from email_parser.timezone_utils import today_central_str
                db.save_action_item({
                    "subject": f"RSVP DEADLINE: {ev.get('item_name')}", "from_name": "RSVP deadline",
                    "summary": "Unpaid shop RSVP-only order rows at 5:00 PM, release by hand: "
                               + ", ".join(s["name"] for s in hand),
                    "urgency": "high", "category": "other",
                    "email_date": today_central_str(), "confidence": 100}, db_path=db_path)
            except Exception:
                logger.exception("rsvp deadline: could not raise the COO item")
    return {**out, "sent": done, "failed": failed, "applied": True}


def lock_targets(today, db_path=None) -> set:
    """Event dates whose groups the 5:00 PM pairings run builds TODAY: the
    same weekday dial and lead (database.pairings_auto_weekdays), so the
    deadline is always the lock of the event it names (Monday for a Tuesday
    nine, two days before a Saturday)."""
    from datetime import timedelta
    from email_parser import database as db
    out = set()
    for wd, lead in db.pairings_auto_weekdays(db_path).items():
        target = today + timedelta(days=lead)
        if db._WEEKDAY_NAMES[target.weekday()] == wd:
            out.add(target.isoformat())
    return out


def tick(now=None, db_path=None) -> list:
    """The scheduler step (every 10 minutes, 1:00-5:00 PM Central): for the
    events whose groups are built at 5:00 PM today, WARN once the clock
    passes 1:00 PM and RELEASE in the 4:50-4:59 PM slot, each once per person."""
    from email_parser import database as db
    from email_parser.timezone_utils import now_central
    if not _on(db_path):
        return []
    now = now or now_central()
    hm = (now.hour, now.minute)
    if hm < WARN_FROM or hm >= RELEASE_UNTIL:
        return []
    kind = "release" if hm >= RELEASE_FROM else "warn"
    targets = lock_targets(now.date(), db_path)
    skip = _excluded_events(db_path)
    out = []
    for ev in db.get_all_events(db_path=db_path):
        if str(ev.get("event_date") or "")[:10] not in targets:
            continue
        if (ev.get("status") or "active") != "active" or int(ev["id"]) in skip:
            continue
        res = run(int(ev["id"]), kind, confirm=True, db_path=db_path)
        if res.get("send") or res.get("held"):
            out.append({k: res.get(k) for k in ("event", "kind", "sent", "failed", "held", "skip")})
    return out
