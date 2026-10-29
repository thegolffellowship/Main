"""THE EVENT WAITLIST (Kerry 2026-10-29).

Kerry: "Kelly BARNA, Myself and Michael Mesa need to go on a waitlist for
Saturday. We can't have anymore than 32, so Kelly needs to come off the
active roster." Then: "There of course needs to be the ability to add max
players for an event. I obviously had a max I contracted, but system didn't
know that. Then Kelly texted me and said when he tried to sign up (after
clicking RSVP) it was a dead link to the event...because I turned it off in
GoDaddy. You need to think thru what that means we need and how a waitlist
functions properly and what emails/notifications are received in that
case." And on the claim: "for now B with reopening GoDaddy for them. Later
when we have our own shopping experience it will all deal with itself based
on rules that we design into it."

THE PIECES
- The limit: `events.max_players` (migration 0042, Edit Event). Only a PAID
  registration holds a spot (`capacity`); an RSVP never does.
- The gate: every registration link we send goes to `/register/<event_id>`
  (event_links.event_url_for_message, the invitation's I'm in, the results
  email's UP NEXT, the lead texts). Spots open -> straight on to the store.
  Full -> "This event is full" with Join the waitlist, never the dead link.
- The list: app setting `event_waitlist:<event_id>`, ordered, by
  customer_id. Each entry has a `state`: waiting | offered | claimed |
  expired | removed. Putting an RSVP-only player on it sets the Players
  tab's own `not_playing` RSVP override, so they leave the roster.
- The job (`tick`, every 15 minutes, dial `waitlist_auto`, on):
    * the event FILLS -> one staff email: close registration in GoDaddy;
    * a spot OPENS (paid < max) -> the next waiting person is OFFERED it
      until a deadline (`waitlist_claim_hours`, 2 per Kerry 10/29, never
      later than two hours before the first tee; no offer goes out between
      9 PM and 7 AM, it waits for 7 AM): an email to them, and one to Kerry and
      the chapter manager to REOPEN GoDaddy for that person until then;
    * the offered person PAYS -> claimed, off the list; staff told;
    * the deadline passes -> expired, the next person is offered;
    * event morning (7 AM on) -> those still waiting are told it did not
      open up this time, once.
- Member emails are held until Kerry approves the wording: dial
  `waitlist_member_emails` = on. Staff emails (to @thegolffellowship.com and
  the chapter manager) go from the start. Preview: bridge
  `scoring-waitlist:preview|<kind>`.

A paid registration is never touched here (no credit, no refund). Nothing
here moves money.
"""
from __future__ import annotations

import html as _html
import json
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

KEY = "event_waitlist:{}"
FULL_SENT = "waitlist_full_sent:{}"
MORNING_SENT = "waitlist_morning_sent:{}"
DIAL = "waitlist_auto"
MEMBER_DIAL = "waitlist_member_emails"
CLAIM_HOURS = 2          # Kerry 10/29: "That's a big time window. Probably should be less." -> 2 hours
QUIET = (21, 7)          # no offer goes out 9 PM - 7 AM; it waits for 7 AM
STAFF = "kerry@thegolffellowship.com"
STAFF_DOMAIN = "@thegolffellowship.com"

# The words (Kerry approves them before a member gets one).
TEXT = {
    "joined": ("You're #{pos} on the waitlist: {event}",
               "<p>Hi {first},</p><p>{event} is full, so you're on the waitlist, "
               "<b>#{pos}</b>.</p><p>If a spot opens we'll email you right away with a "
               "link to register and a time to claim it by. Nothing to do until then.</p>"),
    "offered": ("A spot opened: {event}",
                "<p>Hi {first},</p><p>A spot opened up for <b>{event}</b> and it's yours if "
                "you want it.</p><p>Register by <b>{deadline}</b> to claim it. After that it "
                "goes to the next person on the waitlist.</p>{button}"),
    "expired": ("Your waitlist spot has passed: {event}",
                "<p>Hi {first},</p><p>The spot we offered you for {event} wasn't claimed by "
                "{deadline}, so it went to the next person on the waitlist.</p>"
                "<p>We hope to see you at the next one.</p>"),
    "morning": ("No spot opened up this time: {event}",
                "<p>Hi {first},</p><p>No spot opened up for {event}, so you won't be "
                "playing this time. Thank you for your patience, and we hope to see you at "
                "the next one.</p>"),
}


# ── the list ────────────────────────────────────────────────────────────
def _event(conn, event_id):
    r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    return dict(r) if r else None


def get(event_id: int, db_path=None) -> list:
    from . import database as db
    raw = db.get_app_setting(KEY.format(int(event_id)), db_path=db_path)
    try:
        rows = json.loads(raw) if raw else []
    except ValueError:
        return []
    for r in rows:
        r.setdefault("state", "waiting")
    return rows


def _save(event_id, rows, db_path=None):
    from . import database as db
    db.set_app_setting(KEY.format(int(event_id)), json.dumps(rows), db_path=db_path)


def active(rows: list) -> list:
    """The people still in line (waiting or holding an offer), in order."""
    return [r for r in rows if r.get("state") in ("waiting", "offered")]


def position(rows: list, customer_id: int) -> int | None:
    line = active(rows)
    for i, r in enumerate(line, 1):
        if int(r["customer_id"]) == int(customer_id):
            return i
    return None


def _rsvp_emails(conn, event_name, cid) -> list:
    rows = conn.execute(
        "SELECT DISTINCT lower(trim(player_email)) FROM rsvps WHERE customer_id = ? "
        "AND lower(COALESCE(matched_event, event_identifier, '')) = lower(?) "
        "AND COALESCE(player_email, '') <> ''", (int(cid), event_name)).fetchall()
    return [r[0] for r in rows]


def _paid_rows(conn, event_id, event_name, cid) -> list:
    from .database import PAIRING_INACTIVE_STATUSES
    ph = ",".join("?" * len(PAIRING_INACTIVE_STATUSES))
    return [int(r[0]) for r in conn.execute(
        f"SELECT id FROM items WHERE customer_id = ? AND (event_id = ? OR lower(item_name) = lower(?)) "
        f"AND COALESCE(transaction_status, 'active') NOT IN ({ph}) "
        f"AND COALESCE(transaction_status, 'active') <> 'rsvp_only'",
        (int(cid), int(event_id), event_name, *PAIRING_INACTIVE_STATUSES)).fetchall()]


def add(event_id: int, customer_id: int, note: str = "", by: str = "", apply: bool = False,
        db_path=None, notify: bool = True) -> dict:
    """Put a person at the END of the line; an RSVP-only player leaves the
    roster. Dry run unless apply."""
    from . import database as db
    from .timezone_utils import now_central
    with db._connect(db_path) as conn:
        ev = _event(conn, event_id)
        if not ev:
            return {"error": f"no event {event_id}"}
        c = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                         (int(customer_id),)).fetchone()
        if not c:
            return {"error": f"no customer {customer_id}"}
        name = f"{c['first_name'] or ''} {c['last_name'] or ''}".strip()
        emails = _rsvp_emails(conn, ev["item_name"], customer_id)
        paid = _paid_rows(conn, event_id, ev["item_name"], customer_id)
    rows = get(event_id, db_path)
    mine = [r for r in rows if int(r["customer_id"]) == int(customer_id)
            and r.get("state") in ("waiting", "offered")]
    if mine:
        return {"already": True, "position": position(rows, customer_id), "waitlist": rows}
    entry = {"customer_id": int(customer_id), "name": name, "note": note, "by": by,
             "added_at": now_central().strftime("%Y-%m-%d %H:%M"), "overrides": emails,
             "state": "waiting"}
    out = {"dry_run": not apply, "event_id": int(event_id), "event": ev["item_name"],
           "add": entry, "position": len(active(rows)) + 1,
           "roster": (f"RSVP not playing for {', '.join(emails)}: off the roster" if emails
                      else "no RSVP on this event: not on the roster"),
           "paid_registration": paid,
           "note_paid": ("a paid registration is left as it is; credit or WD is the manager's call"
                         if paid else None)}
    if not apply:
        return out
    for e in emails:
        db.set_rsvp_email_override(e, ev["item_name"], "not_playing", db_path=db_path)
    rows = [r for r in rows if not (int(r["customer_id"]) == int(customer_id)
                                    and r.get("state") not in ("waiting", "offered"))]
    rows.append(entry)
    _save(event_id, rows, db_path)
    _log(db_path, "waitlist_add", f"event {event_id}: {name} ({customer_id}) #{out['position']}; {note}")
    out["waitlist"] = rows
    if notify:
        out["emails"] = _notify_join(ev, entry, out["position"], db_path)
    return out


def remove(event_id: int, customer_id: int, apply: bool = False, db_path=None) -> dict:
    """Take a person off the line; clears only the overrides the list set
    (they are back on the roster if their RSVP still says PLAYING)."""
    from . import database as db
    rows = get(event_id, db_path)
    hit = [r for r in rows if int(r["customer_id"]) == int(customer_id)
           and r.get("state") in ("waiting", "offered")]
    if not hit:
        return {"error": "not on the waitlist", "waitlist": rows}
    if not apply:
        return {"dry_run": True, "remove": hit[0]}
    with db._connect(db_path) as conn:
        ev = _event(conn, event_id)
    for e in hit[0].get("overrides") or []:
        db.set_rsvp_email_override(e, ev["item_name"], "none", db_path=db_path)
    rows = [r for r in rows if r is not hit[0]]
    _save(event_id, rows, db_path)
    _log(db_path, "waitlist_remove", f"event {event_id}: {hit[0]['name']} ({customer_id})")
    return {"removed": hit[0], "waitlist": rows}


def move(event_id: int, customer_id: int, to_position: int, db_path=None) -> dict:
    """Move a person to a place in the line (1 = first)."""
    rows = get(event_id, db_path)
    line = active(rows)
    me = next((r for r in line if int(r["customer_id"]) == int(customer_id)), None)
    if not me:
        return {"error": "not on the waitlist"}
    line.remove(me)
    line.insert(max(0, min(len(line), int(to_position) - 1)), me)
    rest = [r for r in rows if r not in active(rows)]
    _save(event_id, line + rest, db_path)
    return {"waitlist": line + rest}


# ── capacity ────────────────────────────────────────────────────────────
def capacity(event_id: int, db_path=None) -> dict:
    """{max, paid, open, full}. Only a paid registration holds a spot; an
    event with no max is never full."""
    from . import database as db
    with db._connect(db_path) as conn:
        ev = _event(conn, event_id)
        if not ev:
            return {"error": f"no event {event_id}"}
        try:
            mx = int(ev.get("max_players")) if ev.get("max_players") not in (None, "") else None
        except (TypeError, ValueError):
            mx = None
        roster = db._event_roster_rows(conn, int(event_id))
    paid = len({r.get("customer_id") or r.get("customer") for r in roster if not r.get("rsvp_only")})
    if not mx:
        return {"max": None, "paid": paid, "open": None, "full": False}
    return {"max": mx, "paid": paid, "open": max(0, mx - paid), "full": paid >= mx}


def register_target(event_id: int, db_path=None) -> dict:
    """Where a registration link goes: {redirect} when spots are open and the
    store link is live, else {full: True, ...} for the waitlist page."""
    from . import database as db
    from .event_links import link_state, STATE_EXPIRED
    with db._connect(db_path) as conn:
        ev = _event(conn, event_id)
    if not ev:
        return {"error": "no such event"}
    cap = capacity(event_id, db_path)
    st = link_state(ev)
    # A spot held for an offered waitlister is not open to anyone else
    # (their offer email links to the store directly).
    held = len([r for r in get(event_id, db_path) if r.get("state") == "offered"])
    if cap.get("max") and not cap["full"] and (cap["open"] or 0) <= held:
        cap = {**cap, "full": True, "held_for_waitlist": held}
    out = {"event": ev, "capacity": cap}
    if st["state"] == STATE_EXPIRED:
        out["closed"] = "This event has already been played."
        return out
    if cap["full"]:
        out["full"] = True
        return out
    if st["url"]:
        out["redirect"] = st["url"]
        return out
    out["closed"] = "Registration for this event isn't open online. Please contact your chapter manager."
    return out


# ── the job ─────────────────────────────────────────────────────────────
def _first_tee(ev) -> datetime | None:
    d = str(ev.get("event_date") or "")[:10]
    if not d:
        return None
    t = (ev.get("start_time") or "08:00").strip()[:5]
    try:
        return datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            return datetime.strptime(f"{d} 08:00", "%Y-%m-%d %H:%M")
        except ValueError:
            return None


def _deadline(ev, now, db_path=None) -> datetime:
    from . import database as db
    try:
        hrs = int(db.get_app_setting("waitlist_claim_hours", db_path=db_path) or CLAIM_HOURS)
    except (TypeError, ValueError):
        hrs = CLAIM_HOURS
    d = now + timedelta(hours=hrs)
    ft = _first_tee(ev)
    if ft:
        d = min(d, ft - timedelta(hours=2))
    return d


def _fmt(dt: datetime) -> str:
    return dt.strftime("%A %-m/%-d at %-I:%M %p")


def tick(now=None, db_path=None) -> dict:
    """Every 15 minutes: full alert, claims, expiries, offers, the morning
    note. Only events with a max or a waitlist, not yet played."""
    from . import database as db
    from .timezone_utils import now_central
    if (db.get_app_setting(DIAL, db_path=db_path) or "on").strip().lower() in ("off", "0", "false", "no"):
        return {"status": "off"}
    now = now or now_central()
    today = now.date().isoformat()
    with db._connect(db_path) as conn:
        evs = [dict(r) for r in conn.execute(
            "SELECT * FROM events WHERE substr(event_date, 1, 10) >= ? "
            "AND COALESCE(status, 'active') = 'active'", (today,)).fetchall()]
        keyed = {int(r[0].split(":", 1)[1]) for r in conn.execute(
            "SELECT key FROM app_settings WHERE key LIKE 'event_waitlist:%'").fetchall()
            if r[0].split(":", 1)[1].isdigit()}
    out = {}
    for ev in evs:
        if not ev.get("max_players") and int(ev["id"]) not in keyed:
            continue
        try:
            r = _tick_event(ev, now, db_path)
            if r:
                out[ev["id"]] = r
        except Exception as exc:
            logger.exception("waitlist tick failed for %s", ev["id"])
            out[ev["id"]] = {"error": str(exc)}
    return {"status": "ran", "events": out}


def _tick_event(ev, now, db_path=None) -> dict:
    from . import database as db
    eid = int(ev["id"])
    did = {}
    cap = capacity(eid, db_path)
    rows = get(eid, db_path)
    changed = False
    ft = _first_tee(ev)
    # 1. the event fills: one staff note to close registration.
    if cap["full"] and not db.get_app_setting(FULL_SENT.format(eid), db_path=db_path):
        _staff(ev, f"FULL: {ev['item_name']} ({cap['paid']} of {cap['max']})",
               f"<p>{_h(ev['item_name'])} is full: {cap['paid']} paid of {cap['max']}.</p>"
               "<p><b>Please turn off registration in GoDaddy.</b> Anyone who taps a "
               "registration link from now on sees the Tracker's waitlist page, never a dead link.</p>",
               db_path)
        db.set_app_setting(FULL_SENT.format(eid), now.strftime("%Y-%m-%d %H:%M"), db_path=db_path)
        did["full_alert"] = True
    if not cap["full"] and db.get_app_setting(FULL_SENT.format(eid), db_path=db_path):
        db.set_app_setting(FULL_SENT.format(eid), "", db_path=db_path)   # re-arm
    with db._connect(db_path) as conn:
        for r in rows:
            if r.get("state") == "offered" and _paid_rows(conn, eid, ev["item_name"], r["customer_id"]):
                r["state"], r["claimed_at"] = "claimed", now.strftime("%Y-%m-%d %H:%M")
                changed = True
                did.setdefault("claimed", []).append(r["name"])
                _staff(ev, f"Waitlist spot claimed: {r['name']}, {ev['item_name']}",
                       f"<p>{_h(r['name'])} paid and is in. "
                       + ("The event is full again: <b>turn GoDaddy registration back off.</b>"
                          if capacity(eid, db_path)["full"] else "") + "</p>", db_path)
    # 3. expiries.
    for r in rows:
        if r.get("state") == "offered" and r.get("deadline") and now >= datetime.strptime(
                r["deadline"], "%Y-%m-%d %H:%M"):
            r["state"], r["expired_at"] = "expired", now.strftime("%Y-%m-%d %H:%M")
            changed = True
            did.setdefault("expired", []).append(r["name"])
            _member(ev, r, "expired", db_path, deadline=_fmt(datetime.strptime(r["deadline"], "%Y-%m-%d %H:%M")))
            _staff(ev, f"Waitlist offer not claimed: {r['name']}, {ev['item_name']}",
                   f"<p>{_h(r['name'])} did not claim the spot by the deadline. "
                   "It goes to the next person on the waitlist.</p>", db_path)
            # A lapsed offer never leaves RSVP overrides behind silently: the
            # person stays off the roster (they did not pay).
    # 4. offers: one per open spot, while there is time to claim.
    quiet = now.hour >= QUIET[0] or now.hour < QUIET[1]
    if cap.get("max") and not quiet and (not ft or now < ft - timedelta(hours=2)):
        cap = capacity(eid, db_path)
        holding = [r for r in rows if r.get("state") == "offered"]
        free = (cap["open"] or 0) - len(holding)
        for r in [r for r in rows if r.get("state") == "waiting"]:
            if free <= 0:
                break
            dl = _deadline(ev, now, db_path)
            if dl <= now:
                break
            r["state"], r["offered_at"] = "offered", now.strftime("%Y-%m-%d %H:%M")
            r["deadline"] = dl.strftime("%Y-%m-%d %H:%M")
            changed = True
            free -= 1
            did.setdefault("offered", []).append(r["name"])
            _member(ev, r, "offered", db_path, deadline=_fmt(dl))
            _staff(ev, f"REOPEN GODADDY: spot offered to {r['name']}, {ev['item_name']}",
                   f"<p>A spot opened ({cap['paid']} paid of {cap['max']}). It is offered to "
                   f"<b>{_h(r['name'])}</b> until <b>{_fmt(dl)}</b>.</p>"
                   "<p><b>Please turn GoDaddy registration back on so they can pay</b>, and off "
                   "again once they have (the Tracker tells you when they do, or when the offer "
                   "lapses and goes to the next person).</p>", db_path)
    # 5. event morning: those still waiting hear it did not open up.
    if (now.date().isoformat() == str(ev["event_date"])[:10] and now.hour >= 7
            and not db.get_app_setting(MORNING_SENT.format(eid), db_path=db_path)):
        n = 0
        for r in rows:
            if r.get("state") in ("waiting", "offered"):
                _member(ev, r, "morning", db_path)
                n += 1
        db.set_app_setting(MORNING_SENT.format(eid), now.strftime("%Y-%m-%d %H:%M"), db_path=db_path)
        if n:
            did["morning"] = n
    if changed:
        _save(eid, rows, db_path)
    return did


# ── email ───────────────────────────────────────────────────────────────
def _h(s) -> str:
    return _html.escape(str(s or ""))


def _log(db_path, action, text):
    from . import database as db
    try:
        db.log_agent_action("waitlist", action, text, db_path=db_path)
    except Exception:
        pass


def staff_recipients(ev, db_path=None) -> list:
    from .pairings_approval import manager_for
    to = [STAFF]
    m = (manager_for(ev.get("chapter"), db_path) or {}).get("email") or ""
    if m and m.lower() not in (x.lower() for x in to):
        to.append(m)
    return to


def _mail(to, subject, html, db_path=None, who="waitlist") -> bool:
    creds = [os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET",
                                    "EMAIL_ADDRESS")]
    if not all(creds):
        logger.info("waitlist: no mail credentials; would send %r to %s", subject, to)
        return False
    from .fetcher import send_mail_graph
    try:
        return bool(send_mail_graph(tenant_id=creds[0], client_id=creds[1], client_secret=creds[2],
                                    from_address=creds[3], to_address=to, subject=subject,
                                    html_body=html))
    except Exception:
        logger.exception("waitlist: send failed")
        return False


def _staff(ev, subject, inner, db_path=None) -> bool:
    to = ", ".join(staff_recipients(ev, db_path))
    ok = _mail(to, subject, inner + f"<p><a href=\"{_events_link(ev)}\">Open the event</a></p>", db_path)
    _log(db_path, "waitlist_staff_email", f"event {ev['id']}: {subject} -> {to} ({'sent' if ok else 'not sent'})")
    return ok


def _events_link(ev) -> str:
    from .invitations import _base_url
    return f"{_base_url()}/events?event={ev['id']}"


def member_on(db_path=None) -> bool:
    from . import database as db
    return (db.get_app_setting(MEMBER_DIAL, db_path=db_path) or "off").strip().lower() in (
        "on", "1", "true", "yes")


def signature(ev) -> str:
    """Kerry 10/29: "Each needs a signature line from the chapter manager. If
    it's a joint event, it just says The Golf Fellowship." The chapter's
    sign-off is the results email's (results_email.SIGNATURES)."""
    from .results_email import SIGNATURES
    return SIGNATURES.get((ev.get("chapter") or "").strip().lower()) or "The Golf Fellowship"


def render(ev, entry, kind, db_path=None, **kw) -> dict:
    """{subject, html} for one member email, in the house frame."""
    from .payment_reminder import frame_for
    from .event_links import pay_button_html
    first = (entry.get("name") or "").split(" ")[0] or "there"
    subj, body = TEXT[kind]
    try:
        # The frame's own title: "2026 Fall Championship @ Kissing Tree" or
        # "Tuesday at Silverhorn" (payment_reminder.frame_for).
        from .invitations import _display_name, _context
        place = _display_name(ev) or ev["item_name"]
        evname = place if "@" in place else f"{_context(ev, db_path)['day']} at {place}"
    except Exception:
        evname = ev["item_name"]
    vals = {"first": _h(first), "event": _h(evname), "pos": kw.get("pos", ""),
            "deadline": _h(kw.get("deadline", "")),
            # The offer goes straight to the store (Kerry reopens it for
            # them); the gate would show everyone else the spot as held.
            "button": pay_button_html((ev.get("registration_url") or "").strip(), "Register now")
            if kind == "offered" else ""}
    inner = body.format(**vals) + f"<p>{signature(ev)}</p>"
    try:
        html = frame_for(ev, inner, db_path)
    except Exception:
        html = inner
    return {"subject": subj.format(**{**vals, "event": evname}), "html": html}


def _member(ev, entry, kind, db_path=None, **kw) -> bool:
    from . import database as db
    if not member_on(db_path):
        _log(db_path, "waitlist_member_email_held",
             f"event {ev['id']}: {kind} to {entry['name']} held (waitlist_member_emails is off)")
        return False
    from .invitations import _send_email
    with db._connect(db_path) as conn:
        addr = _send_email(conn, int(entry["customer_id"]))
    if not addr:
        return False
    msg = render(ev, entry, kind, db_path, **kw)
    ok = _mail(addr, msg["subject"], msg["html"], db_path)
    try:
        db.log_message({"event_name": ev["item_name"], "template_id": None, "channel": "email",
                        "recipient_name": entry["name"], "recipient_address": addr,
                        "subject": msg["subject"], "body_preview": f"waitlist {kind}",
                        "status": "sent" if ok else "failed", "error_message": None if ok else "Send failed",
                        "sent_by": "waitlist"}, db_path=db_path)
    except Exception:
        pass
    return ok


def _notify_join(ev, entry, pos, db_path=None) -> dict:
    m = _member(ev, entry, "joined", db_path, pos=pos)
    s = _staff(ev, f"Waitlist #{pos}: {entry['name']}, {ev['item_name']}",
               f"<p>{_h(entry['name'])} joined the waitlist for {_h(ev['item_name'])} at #{pos}.</p>",
               db_path)
    return {"member": m, "staff": s}


def register_url(event_id: int) -> str:
    from .invitations import _base_url
    return f"{_base_url()}/register/{int(event_id)}"


def preview(kind: str, event_id: int, db_path=None) -> dict:
    from . import database as db
    with db._connect(db_path) as conn:
        ev = _event(conn, event_id)
    if not ev or kind not in TEXT:
        return {"error": f"kinds: {', '.join(TEXT)}"}
    return render(ev, {"name": "Kelly Barna", "customer_id": 0}, kind, db_path,
                  pos=2, deadline=_fmt(datetime(2026, 10, 30, 20, 0)))


def board(event_id: int, db_path=None) -> dict:
    """The Players tab read: capacity, the line, and the history."""
    rows = get(event_id, db_path)
    line = active(rows)
    for i, r in enumerate(line, 1):
        r["position"] = i
    return {"capacity": capacity(event_id, db_path), "line": line,
            "past": [r for r in rows if r.get("state") not in ("waiting", "offered")],
            "member_emails": member_on(db_path)}
