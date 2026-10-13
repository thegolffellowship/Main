"""TRACKER EVENT INVITATIONS + RSVPs (Kerry 2026-10-13: "RSVP's are the only
thing that we might need to continue, but would rather switch completely on
that too starting tomorrow for next week's events").

One invitation email per invitee per event, with two buttons, I'm in and
Can't make it, plus the event's registration link. Each button is a signed
link (no login; signed links are not member logins, CA #731). The link opens
a confirm page; the answer is recorded only on its POST, so a mail scanner
that pre-fetches links can never answer for a player.

The answer is an ordinary `rsvps` row, so everything that already reads RSVPs
(the roster via `_event_rsvp_only_players`, the Events tab, the RSVP log,
pairings, the event-day email) picks it up. A Tracker row is told apart from a
Golf Genius row by its email_uid, `tracker:<event_id>:<customer_id>` (Proposal
A, #1747); `gg_rsvps_off` hides only Golf Genius rows.

AUDIENCE (Kerry 2026-10-13: "That audience works, go with it"), per chapter:
active members of the chapter, plus anyone who played that chapter in the last
12 months, plus lead opt-ins for that chapter; minus opted-out people
(membership roster "remove", a lead's "no" to invitations, an invitation
unsubscribe), undeliverable addresses, non-member profiles (course contacts,
vendors) and anyone already registered for the event.

SENDS are locked: the wording must carry Kerry's stamp (app setting
`event_invite_approved` = the template hash), the call must cite a mailbox post
carrying Kerry's word (customer_query._kerry_ok) and pass confirm=True. Once
per event and person per kind (invite / reminder), kept in app settings.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

APPROVAL_KEY = "event_invite_approved"
OPTOUT_KEY = "event_invite_optout"
SENT_KEY = "event_invite_sent:{event_id}"
UID_PREFIX = "tracker:"
LOOKBACK_DAYS = 365
ACTIONS = ("in", "out", "unsub")
RESPONSE = {"in": "PLAYING", "out": "NOT PLAYING"}
ACTIVE_STATUSES = ("active_member", "member_plus")
INACTIVE_ITEM = ("credited", "refunded", "transferred", "cancelled", "wd", "merged",
                 "reversed")
DEFAULT_PREVIEW_TO = "kerry@thegolffellowship.com"

# The words. Structure (buttons, frame) is in code; changing any of these
# changes the hash, so the send locks until Kerry stamps the new hash.
SUBJECT = "{day} at {course}: are you in?"
INTRO = ("Hi {first_name},<br><br>You're invited to {course} on {date_long}. "
         "{start_sentence} Tap a button to let {manager_name} know.")
REMINDER_SUBJECT = "Reminder: {day} at {course}. Are you in?"
REMINDER_INTRO = ("Hi {first_name},<br><br>We haven't heard from you yet for {course} "
                  "on {date_long}. {start_sentence} Pairings go out the day before, "
                  "so a quick tap helps {manager_name} build the groups.")
LASTCALL_SUBJECT = "Last call: sign up by 5:00 PM tonight for {day} at {course}"
LASTCALL_INTRO = ("Hi {first_name},<br><br>Last call for {course} on {date_long}. "
                  "{start_sentence} Sign up by 5:00 PM tonight: that's when "
                  "{manager_name} builds the groups.")
CLOSING = ("Questions? Text {manager_name} at {manager_phone}.<br><br>"
           "See you out there,<br>{manager_name}<br>The Golf Fellowship")
FOOTER = ("You get these because you play with The Golf Fellowship in {chapter}. "
          "<a href=\"{unsub_url}\">Stop event invitations</a>.")


def template_hash() -> str:
    raw = "\x1f".join((SUBJECT, INTRO, REMINDER_SUBJECT, REMINDER_INTRO, LASTCALL_SUBJECT,
                       LASTCALL_INTRO, CLOSING, FOOTER))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _setting(key, db_path=None):
    from email_parser import database as db
    try:
        return db.get_app_setting(key, db_path=db_path)
    except Exception:
        return None


def approval_state(db_path=None) -> dict:
    h = template_hash()
    stamp = (_setting(APPROVAL_KEY, db_path) or "").strip()
    return {"template_hash": h, "approved": stamp == h, "approval_key": APPROVAL_KEY}


# ---------------------------------------------------------------------------
# Signed links
# ---------------------------------------------------------------------------

def _secret() -> bytes:
    from email_parser.memberships import _secret as s
    return s()


def make_token(customer_id: int, event_id: int, action: str, expires: date) -> str:
    if action not in ACTIONS:
        raise ValueError("action must be in, out or unsub")
    exp = datetime(expires.year, expires.month, expires.day) + timedelta(days=1)
    payload = {"c": int(customer_id), "v": int(event_id), "a": action,
               "x": int(exp.timestamp())}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()
                                    ).rstrip(b"=").decode()
    sig = hmac.new(_secret(), b"rsvp." + body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def verify_token(token: str) -> dict | None:
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    want = hmac.new(_secret(), b"rsvp." + body.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, want):
        return None
    try:
        p = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None
    if p.get("a") not in ACTIONS or int(p.get("x", 0)) < int(datetime.utcnow().timestamp()):
        return None
    return p


def _base_url() -> str:
    from email_parser.score_entry import _base_url as b
    return b()


def rsvp_url(token: str) -> str:
    return f"{_base_url()}/rsvp/{token}"


# ---------------------------------------------------------------------------
# Event + audience
# ---------------------------------------------------------------------------

CHAPTER_EVENTS = ("san antonio", "austin")
BOTH_CHAPTERS = ("San Antonio", "Austin")


def audience_chapters(chapter: str | None) -> list[str]:
    """Which chapters' lists an event invites: its own, or both for a TGF
    event (Kerry 10/13, the Fall Championship)."""
    c = (chapter or "").strip()
    if c.lower() in CHAPTER_EVENTS:
        return [c]
    if c.lower() == "tgf":
        return list(BOTH_CHAPTERS)
    return []


def _event(conn, event_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    return dict(r) if r else None


def _opted_out(db_path=None) -> set:
    try:
        return {int(x) for x in json.loads(_setting(OPTOUT_KEY, db_path) or "[]")}
    except Exception:
        return set()


def _send_email(conn, cid: int) -> str | None:
    """The customer's sendable address: primary first, never undeliverable."""
    r = conn.execute(
        "SELECT email FROM customer_emails WHERE customer_id = ? "
        "AND COALESCE(undeliverable, 0) = 0 AND email IS NOT NULL AND email <> '' "
        "ORDER BY is_primary DESC, email_id LIMIT 1", (int(cid),)).fetchone()
    return (r[0] or "").strip() or None if r else None


def _registered_ids(conn, ev: dict) -> set:
    rows = conn.execute(
        "SELECT DISTINCT customer_id FROM items WHERE customer_id IS NOT NULL "
        "AND (event_id = ? OR lower(item_name) = lower(?)) "
        "AND lower(COALESCE(transaction_status, 'active')) NOT IN "
        f"({','.join('?' * len(INACTIVE_ITEM))})",
        (int(ev["id"]), ev.get("item_name") or "", *INACTIVE_ITEM)).fetchall()
    return {int(r[0]) for r in rows}


def audience(event_id: int, db_path=None) -> dict:
    """Who is invited to this event, with the reason each person is in and
    every exclusion counted. Read-only."""
    from email_parser import database as db
    conn = db.get_connection(db_path)
    try:
        ev = _event(conn, event_id)
        if not ev:
            return {"error": f"event {event_id} not found"}
        chapter = (ev.get("chapter") or "").strip()
        chapters = audience_chapters(chapter)
        if not chapters:
            return {"error": f"invitations go to a chapter or TGF event; this one is '{chapter}'"}
        why: dict[int, set] = {}

        def add(cid, reason):
            if cid is None:
                return
            why.setdefault(int(cid), set()).add(reason)

        lead_no_id = 0
        # A TGF (both-chapter) event invites both chapters' lists (Kerry 10/13:
        # "Yes, invite both chapters to the Fall Championship").
        for chapter in chapters:
            # 1. Active members of the chapter (home chapter by id, else the text).
            ch = conn.execute("SELECT chapter_id FROM chapters WHERE lower(name) = lower(?)",
                              (chapter,)).fetchone()
            ch_id = ch[0] if ch else None
            st = ",".join("?" * len(ACTIVE_STATUSES))
            for r in conn.execute(
                    f"SELECT customer_id FROM customers WHERE current_player_status IN ({st}) "
                    "AND (home_chapter_id = ? OR (home_chapter_id IS NULL AND lower(chapter) = lower(?)))",
                    (*ACTIVE_STATUSES, ch_id, chapter)).fetchall():
                add(r[0], "member")
            # 2. Played this chapter in the last 12 months.
            since = (date.fromisoformat(str(ev["event_date"])[:10]) - timedelta(days=LOOKBACK_DAYS)).isoformat()
            for r in conn.execute(
                    "SELECT DISTINCT i.customer_id FROM items i JOIN events e "
                    "ON (i.event_id = e.id OR lower(i.item_name) = lower(e.item_name)) "
                    "WHERE i.customer_id IS NOT NULL AND lower(e.chapter) = lower(?) "
                    "AND substr(e.event_date, 1, 10) >= ? AND substr(e.event_date, 1, 10) < ? "
                    "AND lower(COALESCE(i.transaction_status, 'active')) NOT IN "
                    f"({','.join('?' * len(INACTIVE_ITEM))})",
                    (chapter, since, str(ev["event_date"])[:10], *INACTIVE_ITEM)).fetchall():
                add(r[0], "played_12mo")
            # 3. Lead opt-ins for the chapter (the invite-list CSV's own rule).
            try:
                from email_parser.leads import get_lead_export_rows
                for l in get_lead_export_rows(chapter, db_path=db_path):
                    r = conn.execute("SELECT customer_id FROM customer_emails "
                                     "WHERE lower(email) = lower(?) LIMIT 1",
                                     (l["email"],)).fetchone()
                    if r:
                        add(r[0], "lead_optin")
                    else:
                        lead_no_id += 1
            except Exception:
                logger.exception("invitations: lead opt-ins unreadable (left out)")

        # Exclusions.
        out = {"opted_out": 0, "membership_remove": 0, "non_member": 0,
               "registered": 0, "no_email": 0}
        optout = _opted_out(db_path)
        removed = set()
        try:
            removed = {int(r[0]) for r in conn.execute(
                "SELECT DISTINCT customer_id FROM customer_memberships "
                "WHERE roster_choice = 'remove'").fetchall()}
        except Exception:
            pass
        try:
            from email_parser.course_staff import non_member_ids
            nonmem = non_member_ids(conn)
        except Exception:
            nonmem = set(db.vendor_customer_ids(conn))
        registered = _registered_ids(conn, ev)
        people = []
        for cid in sorted(why):
            if cid in optout:
                out["opted_out"] += 1; continue
            if cid in removed:
                out["membership_remove"] += 1; continue
            if cid in nonmem:
                out["non_member"] += 1; continue
            if cid in registered:
                out["registered"] += 1; continue
            email = _send_email(conn, cid)
            if not email:
                out["no_email"] += 1; continue
            c = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                             (cid,)).fetchone()
            first = ((c["first_name"] if c else "") or "").strip()
            name = " ".join(x for x in ((c["first_name"] if c else ""), (c["last_name"] if c else "")) if x).strip()
            people.append({"customer_id": cid, "name": name or f"#{cid}", "first_name": first or "there",
                           "email": email, "why": sorted(why[cid])})
        by = {k: sum(1 for p in people if k in p["why"]) for k in ("member", "played_12mo", "lead_optin")}
        return {"event": {"id": ev["id"], "name": ev.get("item_name"), "date": ev.get("event_date"),
                          "course": ev.get("course"), "chapter": (ev.get("chapter") or "").strip(),
                          "chapters": chapters},
                "people": people, "counts": {"invited": len(people), "by_source": by,
                                             "excluded": out, "lead_optins_without_profile": lead_no_id}}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The message
# ---------------------------------------------------------------------------

def _e(s) -> str:
    import html
    return html.escape(str(s if s is not None else ""), quote=True)


def _fmt_time(t: str | None) -> str:
    if not t:
        return ""
    try:
        return datetime.strptime(str(t)[:5], "%H:%M").strftime("%-I:%M %p")
    except ValueError:
        return str(t)


def _display_name(ev: dict) -> str:
    """'s9.28 TPC Canyons' -> 'TPC Canyons'; a named event such as
    's18.12 FALL CHAMPIONSHIP | Kissing Tree' -> 'Kissing Tree (Fall Championship)'."""
    from email_parser.event_day_email import event_short_name
    name = ev.get("item_name") or ""
    if "|" in name:
        left, right = (x.strip() for x in name.split("|", 1))
        title = event_short_name(left, None).title()
        return f"{right} ({title})" if right else title
    return event_short_name(name, ev.get("course"))


def _context(ev: dict, db_path=None) -> dict:
    from email_parser import database as db
    from email_parser.event_day_email import event_short_name
    d = date.fromisoformat(str(ev["event_date"])[:10])
    start = (ev.get("start_type") or "").strip()
    t = _fmt_time(ev.get("start_time"))
    holes = "18 holes" if "18" in str(ev.get("format") or ev.get("item_name") or "")[:4] else "9 holes"
    if start.lower().startswith("shotgun") and t:
        sentence = f"{holes}, {t} shotgun."
    elif t:
        sentence = f"{holes}, tee times from {t}."
    else:
        sentence = f"{holes}."
    mgrs = db.get_chapter_managers(db_path=db_path) or {}
    chs = audience_chapters(ev.get("chapter"))
    # A TGF event is signed by the San Antonio manager (Kerry).
    mgr = mgrs.get(chs[0] if len(chs) == 1 else "San Antonio", {})
    chapter_text = " and ".join(chs) if chs else (ev.get("chapter") or "")
    return {"day": d.strftime("%A"), "date_long": d.strftime("%A, %B %-d"),
            "course": _display_name(ev),
            "start_sentence": sentence, "manager_name": mgr.get("name") or "TGF",
            "manager_phone": mgr.get("phone") or "", "chapter": chapter_text,
            "registration_url": (ev.get("registration_url") or "").strip(),
            "event_date": d}


def _button(url: str, label: str, bg: str, ink: str) -> str:
    return (f'<td style="padding:4px 6px;"><a href="{_e(url)}" style="display:inline-block;'
            f'background:{bg};color:{ink};font:bold 16px Georgia,serif;text-decoration:none;'
            f'padding:12px 22px;border-radius:999px;">{_e(label)}</a></td>')


def build_message(ev: dict, person: dict, kind: str = "invite", db_path=None) -> dict:
    from email_parser.event_day_email import frame
    ctx = _context(ev, db_path)
    cid, eid = person["customer_id"], int(ev["id"])
    links = {a: rsvp_url(make_token(cid, eid, a, ctx["event_date"])) for a in ACTIONS}
    vals = {**{k: _e(v) for k, v in ctx.items() if k != "event_date"},
            "first_name": _e(person.get("first_name") or "there"),
            "unsub_url": _e(links["unsub"])}
    subj_t, intro_t = {"reminder": (REMINDER_SUBJECT, REMINDER_INTRO),
                       "lastcall": (LASTCALL_SUBJECT, LASTCALL_INTRO)}.get(kind, (SUBJECT, INTRO))
    subject = subj_t.format(day=ctx["day"], course=ctx["course"])
    intro = intro_t.format(**vals)
    buttons = ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
               'style="margin:16px 0;"><tr>'
               + _button(links["in"], "I'm in", "#15803D", "#ffffff")
               + _button(links["out"], "Can't make it", "#E5E7EB", "#1B1B1B")
               + "</tr></table>")
    reg = ""   # I'm in goes straight to registration (Kerry 10/13)
    inner = (f"<p>{intro}</p>{buttons}{reg}<p>{CLOSING.format(**vals)}</p>"
             f'<p style="font-size:12px;color:#6B7280;">{FOOTER.format(**vals)}</p>')
    html_body = frame(inner, (ctx["chapter"] or "").upper(), f"{ctx['day']} at {ctx['course']}")
    blanks = [k for k in ("course", "start_sentence", "manager_name") if not ctx.get(k)]
    if "{" in subject + html_body:
        blanks.append("leftover {tag}")
    return {"subject": subject, "html": html_body, "links": links, "held": blanks}


# ---------------------------------------------------------------------------
# Recording an answer
# ---------------------------------------------------------------------------

def record_answer(token: str, db_path=None) -> dict:
    """POST side of the link. Records I'm in / Can't make it as a Tracker
    rsvps row (one per event + person, the latest answer wins), or the
    invitation unsubscribe. Returns what the page shows."""
    from email_parser import database as db
    p = verify_token(token)
    if not p:
        return {"ok": False, "error": "This link is invalid or has expired."}
    cid, eid, action = int(p["c"]), int(p["v"]), p["a"]
    if action == "unsub":
        opt = _opted_out(db_path)
        opt.add(cid)
        db.set_app_setting(OPTOUT_KEY, json.dumps(sorted(opt)), db_path=db_path)
        db.log_agent_action("rsvp-link", "event_invite_unsubscribe", f"customer {cid}")
        return {"ok": True, "action": "unsub"}
    conn = db.get_connection(db_path)
    try:
        ev = _event(conn, eid)
        if not ev:
            return {"ok": False, "error": "That event is no longer on the schedule."}
        c = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                         (cid,)).fetchone()
        name = " ".join(x for x in ((c["first_name"] if c else ""), (c["last_name"] if c else "")) if x).strip()
        email = _send_email(conn, cid) or ""
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "INSERT INTO rsvps (email_uid, player_name, player_email, gg_event_name, "
            "event_identifier, event_date, response, received_at, matched_event, "
            "matched_item_id, customer_id) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, NULL, ?) "
            "ON CONFLICT(email_uid) DO UPDATE SET response = excluded.response, "
            "received_at = excluded.received_at, player_email = excluded.player_email, "
            "player_name = excluded.player_name",
            (f"{UID_PREFIX}{eid}:{cid}", name, email, ev.get("item_name"),
             str(ev.get("event_date") or "")[:10], RESPONSE[action], now,
             ev.get("item_name"), cid))
        conn.commit()
    finally:
        conn.close()
    try:
        db.log_agent_action("rsvp-link", "event_rsvp", f"event {eid} customer {cid} {RESPONSE[action]}")
    except Exception:
        pass
    ctx_ev = {"name": ev.get("item_name"), "date": ev.get("event_date"),
              "registration_url": (ev.get("registration_url") or "").strip()}
    return {"ok": True, "action": action, "response": RESPONSE[action], "name": name,
            "event": ctx_ev}


def describe_token(token: str, db_path=None) -> dict:
    """GET side: what the confirm page shows. Records nothing."""
    from email_parser import database as db
    p = verify_token(token)
    if not p:
        return {"ok": False, "error": "This link is invalid or has expired."}
    conn = db.get_connection(db_path)
    try:
        ev = _event(conn, int(p["v"]))
    finally:
        conn.close()
    if not ev:
        return {"ok": False, "error": "That event is no longer on the schedule."}
    ctx = _context(ev, db_path)
    return {"ok": True, "action": p["a"], "course": ctx["course"], "date_long": ctx["date_long"],
            "start_sentence": ctx["start_sentence"], "manager_name": ctx["manager_name"]}


# ---------------------------------------------------------------------------
# "I'm in" goes straight to registration (Kerry 10/13: "My thought is to go
# straight to the event registration page if they click I'm In")
# ---------------------------------------------------------------------------

CLICKS_KEY = "event_invite_clicks:{event_id}"


def click_in(token: str, db_path=None) -> dict:
    """GET of an I'm in link. With a registration link on the event, the
    player goes straight there and the CLICK is noted (not an RSVP: a mail
    scanner can follow the link too, so a click never puts anyone on the
    roster; paying does). With no registration link, the confirm page is
    shown and its POST records PLAYING as before."""
    from email_parser import database as db
    p = verify_token(token)
    if not p or p.get("a") != "in":
        return {"ok": False}
    conn = db.get_connection(db_path)
    try:
        ev = _event(conn, int(p["v"]))
    finally:
        conn.close()
    url = ((ev or {}).get("registration_url") or "").strip()
    if not url:
        return {"ok": False}
    key = CLICKS_KEY.format(event_id=int(p["v"]))
    try:
        clicks = json.loads(_setting(key, db_path) or "{}")
    except Exception:
        clicks = {}
    clicks.setdefault(str(int(p["c"])), datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    try:
        db.set_app_setting(key, json.dumps(clicks), db_path=db_path)
    except Exception:
        logger.exception("invitations: could not note the I'm in click")
    # "Changed my mind, I'm in" (Kerry 10/13): an earlier Can't make it no
    # longer stands, so reminders reach them again until they register.
    try:
        conn = db.get_connection(db_path)
        try:
            conn.execute("DELETE FROM rsvps WHERE email_uid = ? AND response = 'NOT PLAYING'",
                         (f"{UID_PREFIX}{int(p['v'])}:{int(p['c'])}",))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.exception("invitations: could not clear the earlier no")
    return {"ok": True, "redirect": url}


def sibling_links(token: str) -> dict:
    """The other buttons for the same person and event: {in, out, unsub}."""
    p = verify_token(token)
    if not p:
        return {}
    exp = (datetime.utcfromtimestamp(int(p["x"])) - timedelta(days=1)).date()
    return {a: rsvp_url(make_token(int(p["c"]), int(p["v"]), a, exp)) for a in ACTIONS}


REASONS = ("Schedule", "Weather", "Course or price", "Injury", "Other")
REASONS_KEY = "event_invite_reasons:{event_id}"


def record_reason(token: str, reason: str, db_path=None) -> bool:
    """The optional one-tap reason on the Can't make it page (Kerry 10/13).
    Kept per event, by customer_id, in an app setting; only listed reasons."""
    from email_parser import database as db
    p = verify_token(token)
    if not p or reason not in REASONS:
        return False
    key = REASONS_KEY.format(event_id=int(p["v"]))
    try:
        got = json.loads(_setting(key, db_path) or "{}")
    except Exception:
        got = {}
    got[str(int(p["c"]))] = reason
    db.set_app_setting(key, json.dumps(got), db_path=db_path)
    return True


# ---------------------------------------------------------------------------
# The schedule (Kerry 10/13): 7:00 AM Central.
#   Tuesday (and any weekday) event: Wednesday, Friday and Sunday before.
#   Weekend event: the Friday two weeks before, the following Friday, and the
#   Tuesday before.
# The first date is the invitation; the later ones are reminders, to invitees
# who have neither registered nor answered.
# ---------------------------------------------------------------------------

SEND_HOUR = 7
# {event_id: "YYYY-MM-DD"}: send that event's invitation early (Kerry 10/13:
# "I want it sent tomorrow morning along with the next two Tuesday events").
EARLY_KEY = "event_invite_early"
AUTO_DIAL = "event_invite_auto"


def schedule(event_date) -> list[dict]:
    d = event_date if isinstance(event_date, date) else date.fromisoformat(str(event_date)[:10])
    wd = d.weekday()                       # Mon 0 .. Sun 6
    if wd in (5, 6):                       # weekend
        fri_before = d - timedelta(days=(wd - 4))
        tue_before = d - timedelta(days=(wd - 1))
        days = [fri_before - timedelta(days=14), fri_before - timedelta(days=7), tue_before]
    else:                                  # Tuesday rule, by offset from the event day
        prev_sun = d - timedelta(days=(wd + 1))
        days = [prev_sun - timedelta(days=4), prev_sun - timedelta(days=2), prev_sun]
    out = []
    for i, day in enumerate(days):
        out.append({"slot": "invite" if i == 0 else f"reminder:{day.isoformat()}",
                    "kind": "invite" if i == 0 else "reminder", "date": day.isoformat()})
    # LAST CALL (Kerry 10/13): "Sign up by 5:00p tonight" on the morning the
    # pairings are built: Monday for a Tuesday event, Wednesday for a
    # Saturday (and Sunday) event, the day before otherwise.
    if wd in (5, 6):
        lc = d - timedelta(days=(wd - 2))
    else:
        lc = d - timedelta(days=1)
    out.append({"slot": f"lastcall:{lc.isoformat()}", "kind": "lastcall", "date": lc.isoformat()})
    return out


# ---------------------------------------------------------------------------
# Sends
# ---------------------------------------------------------------------------

def _sent_map(event_id: int, db_path=None) -> dict:
    """{customer_id: [slot, ...]} for this event."""
    try:
        raw = json.loads(_setting(SENT_KEY.format(event_id=int(event_id)), db_path) or "{}")
    except Exception:
        return {}
    return {k: (v if isinstance(v, list) else [v]) for k, v in raw.items()}


def _answered_ids(event_id: int, db_path=None) -> set:
    """Anyone with an RSVP answer on the event, either way."""
    from email_parser import database as db
    conn = db.get_connection(db_path)
    try:
        ev = _event(conn, event_id)
        rows = conn.execute("SELECT DISTINCT customer_id FROM rsvps WHERE customer_id IS NOT NULL "
                            "AND lower(matched_event) = lower(?)", (ev.get("item_name") or "",)).fetchall()
        return {int(r[0]) for r in rows}
    finally:
        conn.close()


def plan(event_id: int, kind: str = "invite", db_path=None, slot: str | None = None) -> dict:
    """Who a send would reach right now. Read-only. The audience already
    leaves out anyone registered."""
    aud = audience(event_id, db_path)
    if aud.get("error"):
        return aud
    slot = slot or ("invite" if kind == "invite" else f"{kind}:{date.today().isoformat()}")
    sent = _sent_map(event_id, db_path)
    if kind in ("reminder", "lastcall"):
        answered = _answered_ids(event_id, db_path)
        todo = [p for p in aud["people"] if "invite" in sent.get(str(p["customer_id"]), [])
                and slot not in sent.get(str(p["customer_id"]), [])
                and p["customer_id"] not in answered]
    else:
        todo = [p for p in aud["people"] if "invite" not in sent.get(str(p["customer_id"]), [])]
    return {**aud, "kind": kind, "slot": slot, "to_send": todo, "already_sent": len(sent),
            "schedule": schedule(aud["event"]["date"]), **approval_state(db_path)}


def send_preview(event_id: int, to_address: str | None = None, kind: str = "invite",
                 db_path=None) -> dict:
    """ONE sample message plus the audience counts, to STAFF only."""
    from email_parser import database as db
    from email_parser.event_day_email import _creds, _graph_send
    from email_parser.recap_mail import staff_only, _addrs
    to = _addrs(to_address) or [DEFAULT_PREVIEW_TO]
    bad = staff_only(to, lambda k: _setting(k, db_path))
    if bad:
        return {"error": f"an invitation preview goes to TGF staff only; refused {bad}"}
    pl = plan(event_id, kind, db_path)
    if pl.get("error"):
        return pl
    conn = db.get_connection(db_path)
    try:
        ev = _event(conn, event_id)
    finally:
        conn.close()
    sample = (pl["to_send"] or pl["people"] or [{"customer_id": 0, "first_name": "Sample",
                                                  "name": "Sample", "email": ""}])[0]
    msg = build_message(ev, sample, kind, db_path)
    c = pl["counts"]
    sched = ", ".join(f"{s['kind']} {s['date']}" for s in pl["schedule"])
    head = (f"<p><strong>Invitation PREVIEW ({kind})</strong> for {_e(ev.get('item_name'))}. "
            f"Nothing has been sent to any player.</p><p>Would send: {len(pl['to_send'])}. "
            f"Audience {c['invited']} (members {c['by_source']['member']}, played in 12 months "
            f"{c['by_source']['played_12mo']}, lead opt-ins {c['by_source']['lead_optin']}). "
            f"Excluded: {_e(json.dumps(c['excluded']))}. Schedule (7:00 AM): {_e(sched)}. "
            f"Template <code>{pl['template_hash']}</code>: "
            f"{'APPROVED' if pl['approved'] else 'NOT approved'}.</p>"
            f"<p>Sample to {_e(sample['name'])}. The buttons in a preview are live links for "
            f"that person: do not tap them.</p><hr>")
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    subject = f"PREVIEW: {msg['subject']}"
    ok = _graph_send(creds, ",".join(to), subject, head + msg["html"])
    return {"status": "sent" if ok else "failed", "to": to, "subject": subject,
            "would_send": len(pl["to_send"]), "counts": c, "approved": pl["approved"]}


def _deliver(ev: dict, pl: dict, db_path=None) -> dict:
    from email_parser import database as db
    from email_parser.event_day_email import _creds, _graph_send
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    key = SENT_KEY.format(event_id=int(ev["id"]))
    sent_map = _sent_map(ev["id"], db_path)
    sent, failed, held = [], [], []
    for p in pl["to_send"]:
        msg = build_message(ev, p, pl["kind"], db_path)
        if msg["held"]:
            held.append({"customer_id": p["customer_id"], "why": msg["held"]}); continue
        good = False
        try:
            good = _graph_send(creds, p["email"], msg["subject"], msg["html"])
        except Exception:
            logger.exception("invitation send failed for cid %s", p["customer_id"])
        (sent if good else failed).append({"customer_id": p["customer_id"], "name": p["name"],
                                           "email": p["email"]})
        if good:
            sent_map.setdefault(str(p["customer_id"]), []).append(pl["slot"])
            db.set_app_setting(key, json.dumps(sent_map), db_path=db_path)
        try:
            db.log_message({"event_name": ev.get("item_name"), "channel": "email",
                            "recipient_name": p["name"], "recipient_address": p["email"],
                            "subject": msg["subject"], "body_preview": f"event invitation ({pl['slot']})",
                            "status": "sent" if good else "failed",
                            "sent_by": f"event_invite_{pl['kind']}"}, db_path=db_path)
        except Exception:
            pass
    return {"sent": sent, "failed": failed, "held": held}


def send(event_id: int, kerry_ok_post, kind: str = "invite", confirm: bool = False,
         db_path=None) -> dict:
    """THE MEMBER SEND by hand. Stamp + Kerry's word on the mailbox + confirm."""
    from email_parser import database as db
    from email_parser.customer_query import _kerry_ok
    if kind not in ("invite", "reminder", "lastcall"):
        return {"error": "kind is invite, reminder or lastcall"}
    appr = approval_state(db_path)
    if not appr["approved"]:
        return {"refused": f"wording not approved: app setting {APPROVAL_KEY} must equal "
                           f"{appr['template_hash']}", **appr}
    conn = db.get_connection(db_path)
    try:
        ok, why = _kerry_ok(conn, kerry_ok_post)
        ev = _event(conn, event_id)
    finally:
        conn.close()
    if not ok:
        return {"refused": f"rule 3b: {why}"}
    pl = plan(event_id, kind, db_path)
    if pl.get("error"):
        return pl
    out = {"event": pl["event"], "kind": kind, "slot": pl["slot"], "authority": why,
           "counts": pl["counts"], "to_send": len(pl["to_send"])}
    if confirm is not True:
        return {**out, "dry_run": True,
                "plan": [{k: p[k] for k in ("customer_id", "name", "email", "why")}
                         for p in pl["to_send"]]}
    res = _deliver(ev, pl, db_path)
    if res.get("error"):
        return res
    return {**out, **res, "counts": {**out["counts"], "sent": len(res["sent"]),
                                     "failed": len(res["failed"]), "held": len(res["held"])}}


def auto_check(now: datetime | None = None, db_path=None) -> dict:
    """The 7:00 AM job. Does nothing unless app setting event_invite_auto is
    'on' (Kerry's word) AND the wording carries his stamp. Each upcoming
    chapter event whose slot falls today sends that slot once."""
    from email_parser import database as db
    from email_parser.timezone_utils import now_central
    if (_setting(AUTO_DIAL, db_path) or "").strip().lower() != "on":
        return {"skipped": f"{AUTO_DIAL} is not on"}
    if not approval_state(db_path)["approved"]:
        return {"skipped": "wording not approved"}
    now = now or now_central()
    if now.hour < SEND_HOUR:
        return {"skipped": "before 7:00 AM"}
    today = now.date().isoformat()
    conn = db.get_connection(db_path)
    try:
        evs = [dict(r) for r in conn.execute(
            "SELECT * FROM events WHERE COALESCE(status, 'active') = 'active' "
            "AND substr(event_date, 1, 10) > ? AND lower(chapter) IN ('san antonio', 'austin', 'tgf')",
            (today,)).fetchall()]
    finally:
        conn.close()
    try:
        early = json.loads(_setting(EARLY_KEY, db_path) or "{}")
    except Exception:
        early = {}
    done = []
    for ev in evs:
        slots = schedule(ev["event_date"])
        # An earlier invitation date set on Kerry's word (EARLY_KEY). The
        # regular invitation date then reaches only people added since.
        if early.get(str(ev["id"])):
            slots = [{"slot": "invite", "kind": "invite", "date": early[str(ev["id"])]}] + slots
        for s in slots:
            if s["date"] != today:
                continue
            pl = plan(ev["id"], s["kind"], db_path, slot=s["slot"])
            if pl.get("error") or not pl["to_send"]:
                continue
            res = _deliver(ev, pl, db_path)
            done.append({"event_id": ev["id"], "slot": s["slot"],
                         "sent": len(res.get("sent", [])), "failed": len(res.get("failed", []))})
    return {"ran": done}
