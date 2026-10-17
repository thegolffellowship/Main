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

PREVIEW_CID_KEY = "event_invite_preview_cid"
DEFAULT_PREVIEW_CID = 18          # Kerry Niester
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


# Kerry 10/17: "Need to mention in those clarification RSVPs that this is
# for clarification because..." Shown only to someone whose I'm in was
# UNCLEAR (a no within minutes of it, usually a mail scanner). Its own
# words, outside template_hash(), so the approved invitation stamp stands.
CLARIFY_NOTE = ("<b>A quick check:</b> your invitation link recorded \"I'm in\" and then, "
                "a few seconds later, \"{second}\". Sometimes an email security filter taps "
                "every button by itself, so we want to be sure we have you right.{extra} "
                "Please tap the one you meant below.")
CLARIFY_SECOND = {"out": ("Can't make it", ""),
                  "unsub": ("Remove me from invitations",
                            " You're still on our invitation list.")}
UNCLEAR_KEY = "event_invite_unclear:{event_id}"


def unclear_map(event_id: int, db_path=None) -> dict:
    """{customer_id: 'out' | 'unsub'}: whose I'm in was followed within
    seconds by that tap. (An older plain list reads as 'out'.)"""
    try:
        raw = json.loads(_setting(UNCLEAR_KEY.format(event_id=int(event_id)), db_path) or "{}")
    except Exception:
        return {}
    if isinstance(raw, list):
        return {int(x): "out" for x in raw}
    return {int(k): (v if v in CLARIFY_SECOND else "out") for k, v in raw.items()}


def unclear_ids(event_id: int, db_path=None) -> set:
    return set(unclear_map(event_id, db_path))


def clarify_note(second: str | None) -> str:
    label, extra = CLARIFY_SECOND.get(second or "out", CLARIFY_SECOND["out"])
    return CLARIFY_NOTE.format(second=label, extra=extra)


def _set_unclear(event_id: int, cid: int, on, db_path=None) -> None:
    """on = 'out' / 'unsub' (or True = 'out') adds; False removes."""
    from email_parser import database as db
    cur = unclear_map(event_id, db_path)
    new = dict(cur)
    if on:
        new[int(cid)] = on if on in CLARIFY_SECOND else "out"
    else:
        new.pop(int(cid), None)
    if new != cur:
        db.set_app_setting(UNCLEAR_KEY.format(event_id=int(event_id)),
                           json.dumps({str(k): v for k, v in sorted(new.items())}), db_path=db_path)


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


def make_token(customer_id: int, event_id: int, action: str, expires: date,
               preview: bool = False, sent_at: int | None = None) -> str:
    """preview=True marks a staff PREVIEW link (Kerry 10/14: tapping the
    preview recorded Todd McConahy's answers). It opens the same pages and
    records nothing."""
    if action not in ACTIONS:
        raise ValueError("action must be in, out or unsub")
    exp = datetime(expires.year, expires.month, expires.day) + timedelta(days=1)
    payload = {"c": int(customer_id), "v": int(event_id), "a": action,
               "x": int(exp.timestamp())}
    if preview:
        payload["p"] = 1
    if sent_at:
        payload["s"] = int(sent_at)     # when the email went out (scanner grace)
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
               "other_chapter": 0, "registered": 0, "no_email": 0}
        # Kerry 10/13: "Austin members should not be getting invites to SA
        # only events…only combined events and their own events." Anyone whose
        # home chapter is another chapter is left off a single-chapter event,
        # whatever brought them in. A combined (TGF) event invites both lists.
        own = {c.lower() for c in chapters}
        home = {}
        for r in conn.execute(
                "SELECT c.customer_id, lower(COALESCE(ch.name, c.chapter, '')) "
                "FROM customers c LEFT JOIN chapters ch ON ch.chapter_id = c.home_chapter_id").fetchall():
            if r[1]:
                home[int(r[0])] = r[1].strip()
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
            if home.get(cid) in CHAPTER_EVENTS and home.get(cid) not in own:
                out["other_chapter"] += 1; continue
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
        # Kerry 10/13: no event code; "2026 Fall Championship @ Kissing Tree".
        title = event_short_name(left, None).title()
        year = str(ev.get("event_date") or "")[:4]
        title = f"{year} {title}" if year.isdigit() and year not in title else title
        return f"{title} @ {right}" if right else title
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


def build_message(ev: dict, person: dict, kind: str = "invite", db_path=None,
                  preview: bool = False, sent_at: int | None = None,
                  clarify=False) -> dict:
    from email_parser.event_day_email import frame
    ctx = _context(ev, db_path)
    cid, eid = person["customer_id"], int(ev["id"])
    links = {a: rsvp_url(make_token(cid, eid, a, ctx["event_date"], preview=preview,
                                    sent_at=sent_at))
             for a in ACTIONS}
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
    note = (f'<p style="background:#FEF3C7;border-radius:8px;padding:10px 12px;">'
            f'{clarify_note(clarify if isinstance(clarify, str) else None)}</p>'
            if clarify else "")
    inner = (f"<p>{intro}</p>{note}{buttons}{reg}<p>{CLOSING.format(**vals)}</p>"
             f'<p style="font-size:12px;color:#6B7280;">{FOOTER.format(**vals)}</p>')
    html_body = frame(inner, (ctx["chapter"] or "").upper(), f"{ctx['day']} at {ctx['course']}")
    blanks = [k for k in ("course", "start_sentence", "manager_name") if not ctx.get(k)]
    if "{" in subject + html_body:
        blanks.append("leftover {tag}")
    return {"subject": subject, "html": html_body, "links": links, "held": blanks}


# ---------------------------------------------------------------------------
# Recording an answer
# ---------------------------------------------------------------------------

# Kerry 10/14 ("yes on the scanner filter", CoS #1794): mail security
# scanners (Defender, Mimecast, Proofpoint, Barracuda) open every link at
# delivery and some run page scripts. A tap is IGNORED (the page still shows
# as normal, nothing is recorded) when it comes within SCANNER_GRACE_S of the
# email going out, or when a DIFFERENT button of the same email was hit
# within BURST_S, which no person does. A burst also undoes the other tap.
SCANNER_GRACE_S = 120
BURST_S = 30


def _ts(iso) -> float | None:
    try:
        return datetime.strptime(str(iso)[:19], "%Y-%m-%dT%H:%M:%S").timestamp()
    except (TypeError, ValueError):
        return None


def _last_taps(eid: int, cid: int, db_path=None) -> dict:
    """When this person's I'm in and Can't make it were last tapped."""
    from email_parser import database as db
    out = {}
    try:
        clicks = json.loads(_setting(CLICKS_KEY.format(event_id=eid), db_path) or "{}")
        out["in"] = _ts(clicks.get(str(cid)))
    except Exception:
        pass
    conn = db.get_connection(db_path)
    try:
        r = conn.execute("SELECT received_at FROM rsvps WHERE email_uid = ? AND response = 'NOT PLAYING'",
                         (f"{UID_PREFIX}{eid}:{cid}",)).fetchone()
        out["out"] = _ts(r[0]) if r else None
    finally:
        conn.close()
    return out


def scanner_check(p: dict, action: str, db_path=None) -> str | None:
    """'grace' / 'burst' when this tap looks like a mail scanner, else None."""
    now = datetime.utcnow().timestamp()
    if p.get("s") and now - int(p["s"]) < SCANNER_GRACE_S:
        return "grace"
    if action == "unsub":
        # Remove me needs a button tap already, and a person naturally goes
        # Can't make it -> Remove me within seconds: grace only, no burst.
        return None
    taps = _last_taps(int(p["v"]), int(p["c"]), db_path)
    for other in ("in", "out"):
        t = taps.get(other)
        if other != action and t and now - t < BURST_S:
            return "burst"
    return None


def _undo_burst(eid: int, cid: int, db_path=None) -> None:
    """A burst means the earlier tap was the scanner too: drop it."""
    from email_parser import database as db
    now = datetime.utcnow().timestamp()
    taps = _last_taps(eid, cid, db_path)
    if taps.get("out") and now - taps["out"] < BURST_S:
        conn = db.get_connection(db_path)
        try:
            conn.execute("DELETE FROM rsvps WHERE email_uid = ? AND response = 'NOT PLAYING'",
                         (f"{UID_PREFIX}{eid}:{cid}",))
            conn.commit()
        finally:
            conn.close()
    if taps.get("in") and now - taps["in"] < BURST_S:
        # The I'm in tap wrote a PLAYING RSVP too (Kerry 10/17): the scanner's
        # tap must leave nothing behind.
        conn = db.get_connection(db_path)
        try:
            conn.execute("DELETE FROM rsvps WHERE email_uid = ? AND response = 'PLAYING'",
                         (f"{UID_PREFIX}{eid}:{cid}",))
            conn.commit()
        finally:
            conn.close()
        key = CLICKS_KEY.format(event_id=eid)
        try:
            clicks = json.loads(_setting(key, db_path) or "{}")
            clicks.pop(str(cid), None)
            db.set_app_setting(key, json.dumps(clicks), db_path=db_path)
        except Exception:
            logger.exception("invitations: could not drop a scanner click")


def _scanner_ignored(p: dict, action: str, db_path=None) -> str | None:
    why = scanner_check(p, action, db_path)
    if not why:
        return None
    if why == "burst":
        _undo_burst(int(p["v"]), int(p["c"]), db_path)
        try:
            _set_unclear(int(p["v"]), int(p["c"]), "unsub" if action == "unsub" else "out", db_path)
        except Exception:
            logger.exception("invitations: could not mark an unclear answer")
    try:
        from email_parser import database as db
        db.log_agent_action("rsvp-link", "event_invite_scanner_ignored",
                            f"event {int(p['v'])} customer {int(p['c'])} {action} ({why})")
    except Exception:
        pass
    return why


def record_answer(token: str, db_path=None) -> dict:
    """POST side of the link. Records I'm in / Can't make it as a Tracker
    rsvps row (one per event + person, the latest answer wins), or the
    invitation unsubscribe. Returns what the page shows."""
    from email_parser import database as db
    p = verify_token(token)
    if not p:
        return {"ok": False, "error": "This link is invalid or has expired."}
    cid, eid, action = int(p["c"]), int(p["v"]), p["a"]
    if p.get("p"):
        return {"ok": True, "action": action, "preview": True}
    why = _scanner_ignored(p, action, db_path)
    if why:
        return {"ok": True, "action": action, "ignored": why}
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
        _set_unclear(eid, cid, False, db_path)
    except Exception:
        pass
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


def record_click_rsvp(event_id: int, customer_id: int, when: str | None = None,
                      db_path=None) -> bool:
    """An I'm in tap is an RSVP (Kerry 10/17: "if players click I'm in on
    the invites, add them as RSVPs, even if they bounce when the payment page
    comes up"): a Tracker PLAYING row, one per event + person. It never
    replaces a Can't make it given AFTER the tap. Returns True when written."""
    from email_parser import database as db
    when = when or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    uid = f"{UID_PREFIX}{int(event_id)}:{int(customer_id)}"
    conn = db.get_connection(db_path)
    try:
        ev = _event(conn, int(event_id))
        if not ev:
            return False
        later_no = conn.execute(
            "SELECT 1 FROM rsvps WHERE customer_id = ? AND response = 'NOT PLAYING' "
            "AND (event_id = ? OR lower(matched_event) = lower(?)) AND received_at > ? LIMIT 1",
            (int(customer_id), int(event_id), ev.get("item_name") or "", when)).fetchone()
        if later_no:
            return False
        c = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                         (int(customer_id),)).fetchone()
        name = " ".join(x for x in ((c["first_name"] if c else ""), (c["last_name"] if c else "")) if x).strip()
        email = _send_email(conn, int(customer_id)) or ""
        conn.execute(
            "INSERT INTO rsvps (email_uid, player_name, player_email, gg_event_name, "
            "event_identifier, event_date, response, received_at, matched_event, "
            "matched_item_id, customer_id) VALUES (?, ?, ?, NULL, ?, ?, 'PLAYING', ?, ?, NULL, ?) "
            "ON CONFLICT(email_uid) DO UPDATE SET response = excluded.response, "
            "received_at = excluded.received_at",
            (uid, name, email, ev.get("item_name"), str(ev.get("event_date") or "")[:10], when,
             ev.get("item_name"), int(customer_id)))
        conn.commit()
    finally:
        conn.close()
    return True


UNCLEAR_S = 300


def _no_near_tap(event_id: int, cid: int, when: str, db_path=None) -> str | None:
    """A Can't make it or Remove me logged for this person within UNCLEAR_S of
    the I'm in tap, or None. Read from the action log, which keeps answers a
    later clean-up removed from the rsvps table."""
    from email_parser import database as db
    t = _ts(when)
    if t is None:
        return None
    lo = datetime.utcfromtimestamp(t - UNCLEAR_S).strftime("%Y-%m-%d %H:%M:%S")
    hi = datetime.utcfromtimestamp(t + UNCLEAR_S).strftime("%Y-%m-%d %H:%M:%S")
    conn = db.get_connection(db_path)
    try:
        r = conn.execute(
            "SELECT action_type, created_at FROM agent_action_log WHERE agent_name = 'rsvp-link' "
            "AND created_at BETWEEN ? AND ? AND ("
            "(action_type = 'event_rsvp' AND description = ?) OR "
            "(action_type = 'event_invite_unsubscribe' AND description = ?)) "
            "ORDER BY created_at LIMIT 1",
            (lo, hi, f"event {int(event_id)} customer {int(cid)} NOT PLAYING",
             f"customer {int(cid)}")).fetchone()
    except Exception:
        return None
    finally:
        conn.close()
    if not r:
        return None
    what = "Can't make it" if r[0] == "event_rsvp" else "Remove me"
    return f"{what} at {r[1]} UTC"


def clicks_to_rsvps(event_id: int, apply: bool = False, db_path=None) -> dict:
    """Backfill (Kerry 10/17: "Do you still have those clicks for this
    week?"): every noted I'm in tap on the event becomes a PLAYING RSVP,
    except people already registered or who said Can't make it after the
    tap. Dry run unless apply."""
    from email_parser import database as db
    try:
        clicks = json.loads(_setting(CLICKS_KEY.format(event_id=int(event_id)), db_path) or "{}")
    except Exception:
        clicks = {}
    conn = db.get_connection(db_path)
    try:
        ev = _event(conn, int(event_id))
        if not ev:
            return {"error": f"no event {event_id}"}
        reg = _registered_ids(conn, ev)
        names = {int(r[0]): f"{r[1] or ''} {r[2] or ''}".strip() for r in conn.execute(
            f"SELECT customer_id, first_name, last_name FROM customers WHERE customer_id IN "
            f"({','.join('?' * len(clicks)) or 'NULL'})", [int(k) for k in clicks]).fetchall()}
    finally:
        conn.close()
    out = {"event_id": int(event_id), "event": ev.get("item_name"), "registered": [],
           "rsvp": [], "skipped_later_no": [], "ambiguous": [], "applied": bool(apply)}
    for k, when in sorted(clicks.items(), key=lambda kv: kv[1]):
        cid = int(k)
        row = {"customer_id": cid, "name": names.get(cid, ""), "clicked": when}
        if cid in reg:
            out["registered"].append(row)
            continue
        near = _no_near_tap(int(event_id), cid, when, db_path)
        if near:
            # Kerry 10/17: "If we don't have a clear understanding if they're
            # in then we need to ask them again." A Can't make it or Remove me
            # within minutes of the tap (the 10/14 mail-scanner storm) makes
            # the tap unclear: no RSVP; an earlier one is taken back, so the
            # reminders and the last call ask them again.
            row["near"] = near
            out["ambiguous"].append(row)
            if apply:
                _set_unclear(int(event_id), cid,
                             "unsub" if near.startswith("Remove me") else "out", db_path)
                conn = db.get_connection(db_path)
                try:
                    conn.execute("DELETE FROM rsvps WHERE email_uid = ? AND response = 'PLAYING'",
                                 (f"{UID_PREFIX}{int(event_id)}:{cid}",))
                    conn.commit()
                finally:
                    conn.close()
            continue
        if apply:
            ok = record_click_rsvp(int(event_id), cid, when, db_path)
        else:
            conn = db.get_connection(db_path)
            try:
                ok = not conn.execute(
                    "SELECT 1 FROM rsvps WHERE customer_id = ? AND response = 'NOT PLAYING' "
                    "AND (event_id = ? OR lower(matched_event) = lower(?)) AND received_at > ? LIMIT 1",
                    (cid, int(event_id), ev.get("item_name") or "", when)).fetchone()
            finally:
                conn.close()
        (out["rsvp"] if ok else out["skipped_later_no"]).append(row)
    if apply:
        try:
            db.log_agent_action("rsvp-link", "event_invite_clicks_to_rsvps",
                                f"event {event_id}: {len(out['rsvp'])} PLAYING", db_path=db_path)
        except Exception:
            pass
    return out


def click_in(token: str, db_path=None) -> dict:
    """GET of an I'm in link. With a registration link on the event, the
    player goes straight there; the tap is noted AND recorded as a PLAYING
    RSVP (Kerry 10/17), even if they never pay. Mail-scanner taps (the grace
    window and the in/out burst) record nothing. With no registration link,
    the confirm page is shown and its POST records PLAYING as before."""
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
    if p.get("p"):
        return {"ok": True, "redirect": url, "preview": True}
    why = _scanner_ignored(p, "in", db_path)
    if why:
        return {"ok": True, "redirect": url, "ignored": why}
    key = CLICKS_KEY.format(event_id=int(p["v"]))
    try:
        clicks = json.loads(_setting(key, db_path) or "{}")
    except Exception:
        clicks = {}
    clicks[str(int(p["c"]))] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
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
    try:
        record_click_rsvp(int(p["v"]), int(p["c"]), db_path=db_path)
        _set_unclear(int(p["v"]), int(p["c"]), False, db_path)
    except Exception:
        logger.exception("invitations: could not record the I'm in RSVP")
    return {"ok": True, "redirect": url}


def sibling_links(token: str) -> dict:
    """The other buttons for the same person and event: {in, out, unsub}."""
    p = verify_token(token)
    if not p:
        return {}
    exp = (datetime.utcfromtimestamp(int(p["x"])) - timedelta(days=1)).date()
    return {a: rsvp_url(make_token(int(p["c"]), int(p["v"]), a, exp, preview=bool(p.get("p")),
                                   sent_at=p.get("s")))
            for a in ACTIONS}


REASONS = ("Schedule", "Weather", "Course or price", "Injury", "Other")


def record_reason(token: str, reason: str, db_path=None) -> bool:
    """The optional one-tap reason on the Can't make it page (Kerry 10/13:
    "track whatever people are willing to give us"). One row per event and
    person in event_decline_reasons (migrations/0016); a later tap updates
    it. Only the listed reasons are accepted."""
    from email_parser import database as db
    p = verify_token(token)
    if not p or reason not in REASONS:
        return False
    if p.get("p"):
        return True
    conn = db.get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO event_decline_reasons (event_id, customer_id, reason, source) "
            "VALUES (?, ?, ?, 'invitation') ON CONFLICT(event_id, customer_id) DO UPDATE SET "
            "reason = excluded.reason, updated_at = CURRENT_TIMESTAMP",
            (int(p["v"]), int(p["c"]), reason))
        conn.commit()
    finally:
        conn.close()
    return True


def decline_reasons(event_id: int, db_path=None) -> dict:
    """Counts by reason for one event, plus who gave which (customer_id)."""
    from email_parser import database as db
    conn = db.get_connection(db_path)
    try:
        rows = conn.execute("SELECT customer_id, reason FROM event_decline_reasons "
                            "WHERE event_id = ? ORDER BY reason", (int(event_id),)).fetchall()
    finally:
        conn.close()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r[1]] = counts.get(r[1], 0) + 1
    return {"counts": counts, "rows": [{"customer_id": r[0], "reason": r[1]} for r in rows]}


def season_decline_report(year: int | None = None, db_path=None) -> dict:
    """Kerry 10/14: "Yes, add the season-wide view by chapter". Every
    standing Can't make it to our invitations (a Tracker NOT PLAYING row; a
    player who later registered or changed their mind is no longer one) in a
    calendar year, with the reason they picked if any, grouped by the event's
    chapter (a combined TGF event is "Combined"). Read-only."""
    from email_parser import database as db
    from email_parser.timezone_utils import today_central
    year = int(year or today_central().year)
    conn = db.get_connection(db_path)
    try:
        answers = conn.execute(
            "SELECT email_uid, customer_id FROM rsvps "
            "WHERE substr(email_uid, 1, 8) = 'tracker:' AND response = 'NOT PLAYING'").fetchall()
        reasons = {(int(r[0]), int(r[1])): r[2] for r in conn.execute(
            "SELECT event_id, customer_id, reason FROM event_decline_reasons").fetchall()}
        events = {int(r[0]): r for r in conn.execute(
            "SELECT id, item_name, event_date, chapter FROM events "
            "WHERE substr(event_date, 1, 4) = ?", (str(year),)).fetchall()}
        rows = []
        for uid, cid in answers:
            try:
                eid = int(str(uid).split(":")[1])
            except (IndexError, ValueError):
                continue
            e = events.get(eid)
            if e:
                rows.append((eid, e[1], e[2], e[3], cid, reasons.get((eid, int(cid or 0)))))
        rows.sort(key=lambda x: (str(x[2] or ""), x[1] or ""))
    finally:
        conn.close()
    chapters: dict = {}
    for eid, name, edate, chap, cid, reason in rows:
        c = (chap or "").strip()
        label = "Combined" if c.lower() in ("tgf", "") else c
        ch = chapters.setdefault(label, {"declines": 0, "no_reason": 0, "reasons": {}, "events": {}})
        ev = ch["events"].setdefault(eid, {"event_id": eid, "event": name,
                                           "date": str(edate or "")[:10],
                                           "declines": 0, "no_reason": 0, "reasons": {}})
        for bucket in (ch, ev):
            bucket["declines"] += 1
            if reason:
                bucket["reasons"][reason] = bucket["reasons"].get(reason, 0) + 1
            else:
                bucket["no_reason"] += 1
    for ch in chapters.values():
        ch["events"] = list(ch["events"].values())
    order = {"San Antonio": 0, "Austin": 1, "Combined": 9}
    return {"year": year, "reasons": list(REASONS),
            "chapters": dict(sorted(chapters.items(), key=lambda kv: (order.get(kv[0], 5), kv[0])))}


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
    """Who the reminders and the last call skip: anyone who said Can't make
    it. An I'm in that has not paid still gets them (Kerry 10/17: "Turn it
    on"); registered players are already out of the audience."""
    from email_parser import database as db
    conn = db.get_connection(db_path)
    try:
        ev = _event(conn, event_id)
        rows = conn.execute("SELECT DISTINCT customer_id FROM rsvps WHERE customer_id IS NOT NULL "
                            "AND lower(matched_event) = lower(?) AND response = 'NOT PLAYING'",
                            (ev.get("item_name") or "",)).fetchall()
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
                 db_path=None, clarify: bool = False) -> dict:
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
    # Kerry 10/14 (CoS #1793): the preview shows a staff member's OWN
    # invitation (app setting event_invite_preview_cid, default Kerry), never
    # a member's, so no tap on it can touch a member's record.
    pcid = int(_setting(PREVIEW_CID_KEY, db_path) or DEFAULT_PREVIEW_CID)
    conn = db.get_connection(db_path)
    try:
        r = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                         (pcid,)).fetchone()
    finally:
        conn.close()
    sample = {"customer_id": pcid, "first_name": (r[0] if r else "") or "Kerry",
              "name": " ".join(x for x in ((r[0], r[1]) if r else ("Kerry", "")) if x)}
    msg = build_message(ev, sample, kind, db_path, preview=True,
                        clarify=(clarify if isinstance(clarify, str) else ("out" if clarify else False)))
    c = pl["counts"]
    sched = ", ".join(f"{s['kind']} {s['date']}" for s in pl["schedule"])
    head = (f"<p><strong>Invitation PREVIEW ({kind})</strong> for {_e(ev.get('item_name'))}. "
            f"Nothing has been sent to any player.</p><p>Would send: {len(pl['to_send'])}. "
            f"Audience {c['invited']} (members {c['by_source']['member']}, played in 12 months "
            f"{c['by_source']['played_12mo']}, lead opt-ins {c['by_source']['lead_optin']}). "
            f"Excluded: {_e(json.dumps(c['excluded']))}. Schedule (7:00 AM): {_e(sched)}. "
            f"Template <code>{pl['template_hash']}</code>: "
            f"{'APPROVED' if pl['approved'] else 'NOT approved'}.</p>"
            f"<p>Sample: {_e(sample['name'])}'s own invitation. The buttons open the real "
            f"pages and record nothing.</p><hr>")
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
    unclear = unclear_map(ev["id"], db_path)
    for p in pl["to_send"]:
        msg = build_message(ev, p, pl["kind"], db_path,
                            sent_at=int(datetime.utcnow().timestamp()),
                            clarify=unclear.get(int(p["customer_id"]), False))
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


def restore_answers(customer_ids, kerry_ok_post, confirm: bool = False, db_path=None) -> dict:
    """Undo answers that a person did not give (Kerry 10/14: "Yes, restore
    them"). On 10/14 mail scanners opened every button, and taps on a staff
    preview answered for the sample person. For each customer_id this puts
    them back on the invitation list, deletes their Tracker NOT PLAYING rows
    on upcoming events (so reminders reach them), and deletes their decline
    reasons on those events. A registration or a Golf Genius RSVP is never
    touched. Kerry's word on the mailbox; dry run unless confirm."""
    from email_parser import database as db
    from email_parser.customer_query import _kerry_ok
    from email_parser.timezone_utils import today_central_str as today_iso
    cids = sorted({int(c) for c in customer_ids})
    if not cids:
        return {"error": "no customer ids"}
    conn = db.get_connection(db_path)
    try:
        ok, why = _kerry_ok(conn, kerry_ok_post)
        if not ok:
            return {"refused": f"rule 3b: {why}"}
        marks = ",".join("?" * len(cids))
        nos = [dict(r) for r in conn.execute(
            f"SELECT email_uid, customer_id, matched_event FROM rsvps "
            f"WHERE customer_id IN ({marks}) AND response = 'NOT PLAYING' "
            f"AND substr(email_uid, 1, 8) = 'tracker:' AND event_date >= ?",
            (*cids, today_iso())).fetchall()]
        reasons = [dict(r) for r in conn.execute(
            f"SELECT r.event_id, r.customer_id, r.reason FROM event_decline_reasons r "
            f"JOIN events e ON e.id = r.event_id WHERE r.customer_id IN ({marks}) "
            f"AND e.event_date >= ?", (*cids, today_iso())).fetchall()]
        opted = _opted_out(db_path)
        out = {"authority": why, "customer_ids": cids,
               "back_on_invitations": [c for c in cids if c in opted],
               "not_playing_rows_removed": nos, "decline_reasons_removed": reasons}
        if confirm is not True:
            return {**out, "dry_run": True}
        for r in nos:
            conn.execute("DELETE FROM rsvps WHERE email_uid = ?", (r["email_uid"],))
        for r in reasons:
            conn.execute("DELETE FROM event_decline_reasons WHERE event_id = ? AND customer_id = ?",
                         (r["event_id"], r["customer_id"]))
        conn.commit()
    finally:
        conn.close()
    db.set_app_setting(OPTOUT_KEY, json.dumps(sorted(opted - set(cids))), db_path=db_path)
    db.log_agent_action("mcp-claude", "event_invite_restore",
                        f"post {kerry_ok_post}: customers {cids}")
    return {**out, "applied": True}


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
