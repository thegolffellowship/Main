"""THE 7:00 PM TEE-TIMES EMAIL, three versions (CMO #2076 copy, build
hand-off #2101; Kerry 10/19: "Can we deploy this now to build").

At 7:00 PM Central the day before the event (E-1), once the pairings are
saved, three emails go at the same moment. They sit BESIDE the 7 PM pairing
auto-send (pairings_approval.auto_send_check), never in place of it.

1. PLAYER: to the registered roster. The "{N} spots still open" box goes
   only to NON-registered recipients and only while the event is not full
   (open seats by the lock rule: field / 4, remainder r leaves 4 - r).
   Who those recipients are is Kerry's open question (#2076 Q2), so it is a
   dial, `teetimes_spots_audience`, default OFF (off | rsvp_in | invited).
   The Register link goes through the invitation scanner filter
   (invitations.make_token "in" -> /rsvp/<token> -> click_in).
   The player version needs the mailing-address footer (CA #1793,
   app setting `tgf_mailing_address`); until it exists every player
   message is HELD on the blank {mailing_address}.
2. COURSE CONTACT: To the course's primary TGF contact, CC the other TGF
   contacts (course_staff.print_recipients). Skipped when there is none.
   Pack line: weekday event "will arrive by email at noon tomorrow";
   weekend event "were sent at noon today".
3. MANAGER: the chapter manager (pairings_approval.manager_for). One
   closing line by what is on file (contact: "You don't need to print
   anything"; none: "Please print them" + an Add course contact link to the
   Courses page Contacts panel).

The TEE SHEET block is built from get_event_print_pack (the Starter Sheet's
own reader): a header (course, date, holes, first tee), one row per group
(start, players with cart pairs together), the "Preliminary" line and a link
to /member/teesheet/<event>. Names and starts only: no money, phones, emails.

GUARDS (the same as invitations / event_day_email):
- any blank required variable or leftover {tag} HOLDS that message;
- once per event + person (app setting `teetimes_email_sent:<event_id>`);
- the preview goes to staff only (recap_mail.staff_only);
- every send is logged to message_log with event_id and customer_id.

THE GATE. Each version's wording is a system template ("Tee Times —
Player", "Tee Times — Course Contact", "Tee Times — Manager", seeded in
database.py). A version sends only when its approval app setting equals its
CURRENT wording hash (the DB template plus the fixed lines held below, so
an edit to either voids the stamp) AND the job dial `teetimes_email_auto`
is 'on' (default off). There is no send bridge: only the 7 PM job sends.
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import logging
import re
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

VERSIONS = ("player", "course", "manager")
# THE FOURTH VERSION, "open spots" (Kerry 10/26, CoS #2386/#2387: "Why would
# there be a spots still open register box sent to those that are already
# paid and seated? The point is to fill our open spots." / "That works. Send
# it to build and deploy."): its own email to invitees who are not on the
# sheet, only while the sheet has open seats. Its words live in code below;
# the stamp is their hash.
OPEN_VERSION = "open_spots"
SEND_ORDER = ("player", OPEN_VERSION, "course", "manager")
OPEN_STAMP = "teetimes_open_spots_approved"
TEMPLATES = {"player": "Tee Times — Player",
             "course": "Tee Times — Course Contact",
             "manager": "Tee Times — Manager"}
APPROVAL_KEYS = {"player": "teetimes_player_approved",
                 "course": "teetimes_course_approved",
                 "manager": "teetimes_manager_approved"}
AUTO_DIAL = "teetimes_email_auto"            # 'on' runs the 7 PM job; default off
SPOTS_DIAL = "teetimes_spots_audience"       # off (default) | rsvp_in | invited
SPOTS_CHOICES = ("off", "rsvp_in", "invited")
MAILING_ADDRESS_KEY = "tgf_mailing_address"  # CA #1793 footer; waits on #1795
SENT_KEY = "teetimes_email_sent:{event_id}"
SEND_HOUR = 19
OPEN_HOUR = 17      # the review window opens with the 5 PM pairings
DEFAULT_PREVIEW_TO = "kerry@thegolffellowship.com"

# Template variables that may be empty (each renders as a whole block or
# nothing). Anything else empty HOLDS the message.
OPTIONAL_VARS = {"spots_block", "footer_block"}

# ---------------------------------------------------------------------------
# The fixed lines. They are part of each version's wording hash.
# ---------------------------------------------------------------------------
PRELIM_LINE = "Preliminary: changes are still possible until the morning of the event."
TEESHEET_LINK = "See the tee sheet on your phone"
SPOTS_BOX = {
    "one": 'There is 1 spot still open. If you want in: <a href="{registration_link}">Register</a>',
    "many": 'There are {spots_left} spots still open. If you want in: <a href="{registration_link}">Register</a>',
}
# The registered players' 7 AM line, and what a NOT-yet-registered recipient
# reads in its place (Kerry 10/19: "Everyone invited except those who said I
# can't make it").
EVENT_INFO_LINE = "Your full Event Info email, with your start, group, cart and games, comes at 7:00 AM tomorrow."
NONREG_LINE = ("Register and we'll fit you into a group; your full Event Info email, with your start, "
               "group, cart and games, follows at 7:00 AM tomorrow.")
PACK_LINE = {
    "weekday": "Print packs (starter sheet, cart signs and scorecards) will arrive by email at noon tomorrow.",
    "weekend": "Print packs (starter sheet, cart signs and scorecards) were sent at noon today.",
}
MANAGER_LINE = {
    ("contact", "weekday"): "The course gets the print packs at noon tomorrow. You don't need to print anything.",
    ("contact", "weekend"): "The course got the print packs at noon today. You don't need to print anything.",
    ("none", "weekday"): ("There is no course contact on file, so the print packs come to you at "
                          "noon tomorrow. Please print them."),
    ("none", "weekend"): ("There is no course contact on file, so the print packs came to you at "
                          "noon today. Please print them."),
}
ADD_CONTACT_LINE = ('Add the course contact here and the system sends the packs to them from now on: '
                    '<a href="{add_contact_url}">Add course contact</a>')
SENT_LINE = {
    "both": "This went to the players and the course at {sent_time}.",
    "players": "This went to the players at {sent_time}.",
    "course": "This went to the course at {sent_time}.",
    "neither": "No tee-times email went to the players or the course.",
}
FOOTER = '<p style="font-size:12px;color:#6B7280;">The Golf Fellowship &middot; {mailing_address}</p>'

# The open-spots email, as Kerry approved it (CoS #2387).
OPEN = {
    "subject_one": "1 spot open at {short} tomorrow, {start}",
    "subject_many": "{n} spots open at {short} tomorrow, {start}",
    "title": "Spots open · {short}",
    "lead": ("Hi {first_name}, tomorrow's field is set, and there's still room for you. "
             "Grab an open spot and join the guys at {short}."),
    "box_one": "1 spot open",
    "box_many": "{n} spots open",
    "button": "Register",
    "table_head": "Who's playing",
    "open_seat": "Open spot",
    "under": "Open spots go to the first players who register. Pairings may change until the morning of the event.",
    "footer": ("You're getting this because you're on the invite list for {short}. "
               "Not this week? No need to reply."),
    "stop": "Stop event invitations",
}

_FIXED = {
    "player": (PRELIM_LINE, TEESHEET_LINK, SPOTS_BOX["one"], SPOTS_BOX["many"], NONREG_LINE),
    "course": (PRELIM_LINE, TEESHEET_LINK, FOOTER, *PACK_LINE.values()),
    "manager": (PRELIM_LINE, TEESHEET_LINK, FOOTER, ADD_CONTACT_LINE,
                *MANAGER_LINE.values(), *SENT_LINE.values()),
}

_TAG_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_BLANK_RE = re.compile(r"\[[A-Z][A-Z0-9 _/\-]*\]")


def _e(s) -> str:
    return _html.escape(str(s if s is not None else ""), quote=True)


def _t(s) -> str:
    """Escape body text (apostrophes stay as they are)."""
    return _html.escape(str(s if s is not None else ""), quote=False)


def _setting(key, db_path=None):
    from email_parser import database as db
    try:
        return db.get_app_setting(key, db_path=db_path)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Templates + the stamp
# ---------------------------------------------------------------------------

def template_hash(version: str, subject: str, html_body: str) -> str:
    raw = f"{subject}\n{html_body}\x1f" + "\x1f".join(_FIXED[version])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def load_template(version: str, db_path=None) -> dict | None:
    from email_parser import database as db
    conn = db.get_connection(db_path)
    try:
        r = conn.execute(
            "SELECT id, subject, html_body FROM message_templates "
            "WHERE lower(name) = lower(?) ORDER BY is_system DESC, id LIMIT 1",
            (TEMPLATES[version],)).fetchone()
    finally:
        conn.close()
    if not r:
        return None
    s, h = r["subject"] or "", r["html_body"] or ""
    return {"id": r["id"], "subject": s, "html_body": h, "hash": template_hash(version, s, h)}


def open_spots_hash() -> str:
    raw = "\x1f".join(f"{k}={OPEN[k]}" for k in sorted(OPEN))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def approval_state(db_path=None) -> dict:
    """{version: {template, template_hash, approval_key, approved}}."""
    out = {}
    oh = open_spots_hash()
    out[OPEN_VERSION] = {"template": "(in code: teetimes_email.OPEN)", "template_hash": oh,
                         "approval_key": OPEN_STAMP,
                         "approved": (_setting(OPEN_STAMP, db_path) or "").strip() == oh}
    for v in VERSIONS:
        tpl = load_template(v, db_path)
        cur = tpl["hash"] if tpl else None
        stamp = (_setting(APPROVAL_KEYS[v], db_path) or "").strip()
        out[v] = {"template": TEMPLATES[v], "template_hash": cur,
                  "approval_key": APPROVAL_KEYS[v],
                  "approved": bool(cur and stamp and stamp == cur)}
    return out


def dials(db_path=None) -> dict:
    auto = (_setting(AUTO_DIAL, db_path) or "").strip().lower() == "on"
    sp = (_setting(SPOTS_DIAL, db_path) or "off").strip().lower()
    return {AUTO_DIAL: "on" if auto else "off",
            SPOTS_DIAL: sp if sp in SPOTS_CHOICES else "off"}


# ---------------------------------------------------------------------------
# Pieces
# ---------------------------------------------------------------------------

def spots_left(field: int) -> int:
    """The lock rule (Error Handling Spec §7): field / 4, remainder r leaves
    4 - r seats (max 3); remainder 0 is full."""
    field = int(field or 0)
    return 0 if field <= 0 else (4 - field % 4) % 4


def is_weekend(event_date) -> bool:
    d = event_date if isinstance(event_date, date) else date.fromisoformat(str(event_date)[:10])
    return d.weekday() in (5, 6)


def _date_long(event_date) -> str:
    try:
        return datetime.strptime(str(event_date or "")[:10], "%Y-%m-%d").strftime("%A, %B %-d")
    except ValueError:
        return ""


def _base_url() -> str:
    try:
        from email_parser.score_entry import _base_url as b
        return b()
    except Exception:
        return ""


def tee_sheet_block(pack: dict, event_id: int) -> tuple[str, list]:
    """(html, problems). Any problem leaves the block empty, which holds
    every message that uses it."""
    ev = pack.get("event") or {}
    groups = [g for g in pack.get("groups") or []
              if any((p.get("name") or "").strip() for p in g.get("players") or [])]
    why = []
    if not groups:
        why.append("pairings not saved")
    if not (ev.get("course") or "").strip():
        why.append("no course on the event")
    dl = _date_long(ev.get("event_date"))
    if not dl:
        why.append("no event date")
    first = " / ".join(x for x in (ev.get("start_label"), ev.get("start_label_18")) if x)
    if not first:
        why.append("no first tee / shotgun time on the event")
    if why:
        return "", why
    hk = sorted({str(g.get("holes")) for g in groups if g.get("holes")}) or [pack.get("holes_key") or ""]
    holes = " and ".join(hk) + " holes"
    header = " · ".join((ev["course"].strip(), dl, holes, first))
    T = 'role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'
    rows = []
    for g in groups:
        players = [p for p in sorted(g.get("players") or [], key=lambda x: x.get("cart_pos") or 0)
                   if (p.get("name") or "").strip()]
        lines = []
        seated = set()
        for cart in g.get("carts") or []:
            names = [p["name"].strip() for p in cart.get("players") or [] if (p.get("name") or "").strip()]
            seated |= {id(p) for p in cart.get("players") or []}
            if names:
                lines.append(" &amp; ".join(_e(n) for n in names))
        for p in players:
            if id(p) not in seated:
                lines.append(_e(p["name"].strip()))
        start = (g.get("start_line") or g.get("slot_label") or "").replace(" | ", " · ")
        rows.append(f'<tr><td style="padding:8px 10px;border-top:1px solid #E5E7EB;vertical-align:top;'
                    f'white-space:nowrap;"><b>{_e(start)}</b></td>'
                    f'<td style="padding:8px 10px;border-top:1px solid #E5E7EB;">{"<br>".join(lines)}</td></tr>')
    url = f"{_base_url()}/member/teesheet/{int(event_id)}"
    html = (f'<table {T} style="border:1px solid #E5E7EB;border-radius:8px;margin:0 0 12px;font-size:15px;">'
            f'<tr><td colspan="2" bgcolor="#1B1B1B" style="background:#1B1B1B;color:#ffffff;'
            f'padding:10px;font-weight:bold;">{_e(header)}</td></tr>' + "".join(rows)
            + f'<tr><td colspan="2" style="padding:8px 10px;border-top:1px solid #E5E7EB;color:#6B7280;'
              f'font-size:13px;">{_e(PRELIM_LINE)}</td></tr></table>'
            + f'<p><a href="{_e(url)}">{_e(TEESHEET_LINK)}</a></p>')
    return html, []


def _guard(subject: str, body: str, used: set, values: dict) -> list:
    why = []
    for v in sorted(used):
        if v in OPTIONAL_VARS:
            continue
        if not str(values.get(v) or "").strip():
            why.append(f"blank: {{{v}}}")
    left = sorted(set(_TAG_RE.findall(subject + " " + body)))
    if left:
        why.append("unrendered: " + ", ".join("{" + x + "}" for x in left))
    from email_parser.event_day_email import html_to_text
    blanks = sorted(set(_BLANK_RE.findall(subject + " " + html_to_text(body))))
    if blanks:
        why.append("bracketed blank: " + ", ".join(blanks))
    return why


MORNING_EVENT_INFO = "went out at noon today"
MORNING_NONREG = "follows as soon as we place you"


def when_words(ev: dict, now: datetime, db_path=None) -> dict:
    """The day words this send needs, seen from the day it goes (Kerry 10/28:
    the tee-times email moves to the LOCK night, so a Saturday event's email
    goes Wednesday and "tomorrow" would be wrong). Event Info: noon the day
    before (morning event) or the event_info_hour on event day; print packs /
    Course Files: noon on course_files_noon.send_day; the event day itself."""
    from email_parser.pairings_approval import info_at, day_word, is_morning_event, info_time
    from email_parser.course_files_noon import send_day
    out = {"event_day": "tomorrow", "info_past": False, "info": None, "packs_past": False,
           "packs_day": "tomorrow"}
    try:
        ed = datetime.strptime(str(ev.get("event_date") or "")[:10], "%Y-%m-%d")
    except ValueError:
        return out
    out["event_day"] = day_word(ed, now)
    ia = info_at(ev, db_path)
    if ia is not None:
        t = "noon" if is_morning_event(ev) else info_time(db_path)
        out["info_past"] = ia <= now
        out["info"] = f"{t} {day_word(ia, now)}"
    try:
        pk = datetime.strptime(send_day(ev), "%Y-%m-%d").replace(hour=12)
        out["packs_past"] = pk <= now
        out["packs_day"] = day_word(pk, now)
    except ValueError:
        pass
    return out


def pack_text(text: str, when: dict | None) -> str:
    """A PACK_LINE / MANAGER_LINE sentence with its day word for this send:
    the stamped text says "noon tomorrow" / "noon today"; a Saturday event's
    Wednesday email reads "noon Friday"."""
    if not when:
        return text
    dw = when.get("packs_day") or "tomorrow"
    return text.replace("noon tomorrow", f"noon {dw}").replace("noon today", f"noon {dw}")


def pack_key(weekend: bool, when: dict | None) -> str:
    """Which stamped variant reads true: the future one ("will arrive", "come
    to you") until the noon send has passed, then the past one."""
    if not when:
        return "weekend" if weekend else "weekday"
    return "weekend" if when.get("packs_past") else "weekday"


def event_info_phrase(body: str, morning: bool = False, when: dict | None = None) -> str:
    """The stamped line names when Event Info comes. A morning event's Event
    Info went at noon the day before, with the Course Files (Kerry 10/26,
    CoS #2355), before this evening email; everyone else's comes at the
    event_info_hour dial's time tomorrow. The template keeps its words and hash.
    With `when` (when_words) the line says the real day: on the lock night of
    a Saturday event, "comes at noon Friday"."""
    if when and when.get("info"):
        if when.get("info_past"):
            past = MORNING_EVENT_INFO if when["info"] == "noon today" else f"went out at {when['info']}"
            return (body.replace("comes at 7:00 AM tomorrow", past)
                        .replace("follows at 7:00 AM tomorrow", MORNING_NONREG))
        return body.replace("at 7:00 AM tomorrow", f"at {when['info']}")
    if morning:
        return (body.replace("comes at 7:00 AM tomorrow", MORNING_EVENT_INFO)
                    .replace("follows at 7:00 AM tomorrow", MORNING_NONREG))
    from email_parser.pairings_approval import info_time
    return body.replace("at 7:00 AM tomorrow", f"at {info_time()} tomorrow")


def _render(version: str, tpl: dict, values: dict) -> tuple[str, str, list]:
    from email_parser.fetcher import render_msg_template, normalize_email_html
    from email_parser.event_day_email import html_to_text
    html_body = tpl["html_body"]
    if not (values.get("mailing_address") or "").strip():
        # Kerry 10/19: send without the footer while no address is on file
        # (a tee sheet to registered players is transactional). The line
        # returns by itself once tgf_mailing_address is set.
        html_body = re.sub(r"<p[^>]*>[^<]*\{mailing_address\}[^<]*</p>", "", html_body)
    used = set(_TAG_RE.findall(tpl["subject"] + html_body))
    subject = html_to_text(render_msg_template(tpl["subject"], values))
    body = normalize_email_html(render_msg_template(html_body, values))
    # The Event Info time follows its dial (Kerry 10/26: "Move event info
    # email to 6:00am"); the stamped template keeps its words and hash.
    body = event_info_phrase(body, values.get("_morning"), values.get("_when"))
    return subject, body, _guard(subject, body, used, values)


# ---------------------------------------------------------------------------
# Build (nothing is sent)
# ---------------------------------------------------------------------------

RELEASED_LINE = "We're releasing these tee times: {times}."


def released_block(ev: dict, db_path=None) -> str:
    """One line naming each tee time the event holds and its saved sheet does
    not use (database.released_tee_times), or "" when none."""
    from email_parser import database as db
    try:
        times = db.released_tee_times(ev, db_path=db_path)
    except Exception:
        return ""
    if not times:
        return ""
    return f"<p><strong>{_t(RELEASED_LINE.format(times=', '.join(times)))}</strong></p>"


def _sent(event_id: int, db_path=None) -> dict:
    try:
        v = json.loads(_setting(SENT_KEY.format(event_id=int(event_id)), db_path) or "{}")
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _spots_people(conn, event_id: int, ev: dict, roster: list, registered: set,
                  mode: str, db_path=None) -> list:
    """Non-registered recipients of the spots box, by the dial."""
    out = {}
    if mode in ("rsvp_in", "invited"):
        # "I'm in" but not paid: the roster's RSVP-only rows.
        for r in roster:
            if r.get("rsvp_only") and r.get("customer_id") and int(r["customer_id"]) not in registered:
                out[int(r["customer_id"])] = None
    if mode == "invited":
        try:
            from email_parser import invitations as inv
            aud = inv.audience(int(event_id), db_path)
            no = inv._answered_ids(int(event_id), db_path)
            for p in aud.get("people") or []:
                if p["customer_id"] not in no and p["customer_id"] not in registered:
                    out[int(p["customer_id"])] = None
        except Exception:
            logger.exception("teetimes: invitation audience unreadable (spots box left out)")
    return sorted(out)


FULL_GROUP = 4


def _open_seats(pack: dict) -> dict:
    """{group index: open seats} on the saved sheet: seats short of a full
    group (a blind seat counts as open; a blind is not a player)."""
    out = {}
    for i, g in enumerate(pack.get("groups") or []):
        n = sum(1 for p in g.get("players") or [] if (p.get("name") or "").strip())
        if 0 < n < FULL_GROUP:
            out[i] = FULL_GROUP - n
    return out


def _open_message(pack: dict, open_list: dict, first: str, reg_url: str, stop_url: str,
                  short: str, event_day: str = "tomorrow") -> tuple[str, str, list]:
    """(subject, body, why) for one invitee. Every word from OPEN; the day
    word follows the send (Kerry 10/28: a Saturday event's open-spots email
    goes Wednesday, so it reads "Saturday", not "tomorrow")."""
    from email_parser.invitations import _button
    ev = pack.get("event") or {}
    n = sum(open_list.values())
    why = []
    if not first:
        why.append("no first name")
    if not reg_url:
        why.append("blank: registration link (the event has no registration link)")
    start = " / ".join(x for x in (ev.get("start_label"), ev.get("start_label_18")) if x)
    if not start:
        why.append("no first tee / shotgun time on the event")
    st = (ev.get("start_type") or "").lower()
    clock = clock12_safe(ev.get("start_clock") or ev.get("start_time"))
    subj_start = (f"{clock} shotgun" if "shotgun" in st else f"first tee {clock}") if clock else start
    subject = (OPEN["subject_one"] if n == 1 else OPEN["subject_many"]).format(n=n, short=short,
                                                                              start=subj_start)
    if event_day != "tomorrow":
        subject = subject.replace(" tomorrow,", f" {event_day},")
    groups = [g for g in pack.get("groups") or []
              if any((p.get("name") or "").strip() for p in g.get("players") or [])]
    hk = sorted({str(g.get("holes")) for g in groups if g.get("holes")}) or [pack.get("holes_key") or ""]
    line = " · ".join(x for x in ((ev.get("course") or "").strip(), _date_long(ev.get("event_date")),
                                  " and ".join(hk) + " holes", start) if x)
    O = "#E87C3E"
    T = 'role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'
    box = (f'<table {T} style="margin:12px 0;"><tr><td bgcolor="#FFF4EC" style="background:#FFF4EC;'
           f'border:2px solid {O};border-radius:10px;padding:14px 16px;">'
           f'<div style="font:bold 22px Georgia,serif;color:{O};">'
           f'{_e(OPEN["box_one"] if n == 1 else OPEN["box_many"].format(n=n))}</div>'
           f'<div style="padding:4px 0 10px;color:#1B1B1B;">{_e(line)}</div>'
           f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
           f'{_button(reg_url, OPEN["button"], O, "#ffffff")}</tr></table></td></tr></table>')
    rows = []
    for i, g in enumerate(pack.get("groups") or []):
        names = [_e(p["name"].strip()) for p in sorted(g.get("players") or [],
                                                         key=lambda x: x.get("cart_pos") or 0)
                 if (p.get("name") or "").strip()]
        if not names:
            continue
        names += [f'<span style="color:{O};font-weight:bold;">{_e(OPEN["open_seat"])}</span>'] * open_list.get(i, 0)
        gstart = (g.get("start_line") or g.get("slot_label") or "").replace(" | ", " · ")
        rows.append(f'<tr><td style="padding:8px 10px;border-top:1px solid #E5E7EB;vertical-align:top;'
                    f'white-space:nowrap;"><b>{_e(gstart)}</b></td>'
                    f'<td style="padding:8px 10px;border-top:1px solid #E5E7EB;">{"<br>".join(names)}</td></tr>')
    if not rows:
        why.append("pairings not saved")
    table = (f'<table {T} style="border:1px solid #E5E7EB;border-radius:8px;margin:0 0 12px;font-size:15px;">'
             f'<tr><td colspan="2" bgcolor="#1B1B1B" style="background:#1B1B1B;color:#ffffff;padding:10px;'
             f'font-weight:bold;">{_e(OPEN["table_head"])}</td></tr>' + "".join(rows) + '</table>')
    lead = OPEN["lead"].format(first_name=first or "there", short=short)
    if event_day != "tomorrow":
        lead = lead.replace("tomorrow's field", f"{event_day[:1].upper()}{event_day[1:]}'s field")
    body = (f'<p>{_e(lead)}</p>' + box + table
            + f'<p>{_e(OPEN["under"])}</p>'
            + f'<p style="font-size:13px;color:#6B7280;">{_e(OPEN["footer"].format(short=short))} '
              f'<a href="{_e(stop_url)}" style="color:#6B7280;">{_e(OPEN["stop"])}</a></p>')
    return subject, body, why


def clock12_safe(v) -> str:
    from email_parser.timezone_utils import clock12
    s = str(v or "").strip()
    if not s:
        return ""
    if re.search(r"[AaPp][Mm]", s):
        return s
    return clock12(s[:5])


def plan_counts(event_id: int, db_path=None) -> dict:
    """Light counts for the approve page (no messages built): registered
    players, open seats on the saved sheet, and the invitees the open-spots
    email would reach (only while its stamp is set and the dial is on)."""
    from email_parser import database as db
    pack = db.get_event_print_pack(int(event_id), db_path=db_path) or {}
    open_list = _open_seats(pack)
    n_open = sum(open_list.values())
    seated = {int(p["customer_id"]) for g in pack.get("groups") or []
              for p in g.get("players") or [] if p.get("customer_id")}
    conn = db.get_connection(db_path)
    try:
        ev = dict(conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone() or {})
        roster = db._event_roster_rows(conn, int(event_id)) if ev else []
        registered = {int(r["customer_id"]) for r in roster if not r.get("rsvp_only") and r.get("customer_id")}
        players = len(registered) or len(seated)
        inv = 0
        dl = dials(db_path)
        if (ev and n_open > 0 and dl[SPOTS_DIAL] != "off"
                and approval_state(db_path)[OPEN_VERSION]["approved"]):
            from email_parser import invitations as inv_mod
            for cid in _spots_people(conn, int(event_id), ev, roster, registered | seated, dl[SPOTS_DIAL], db_path):
                if cid in seated:
                    continue
                try:
                    if inv_mod.known_scanner(int(cid), db_path=db_path):
                        continue
                except Exception:
                    pass
                inv += 1
    finally:
        conn.close()
    return {"players": players, "open_spots": n_open, "invitees": inv}


def build(event_id: int, db_path=None, preview: bool = False, now: datetime | None = None) -> dict:
    """Every recipient's message across the three versions: `ready` (would
    send if the version is stamped and the dial is on), `held` (with the
    reason), `skipped` (no audience) and `already_sent`."""
    from email_parser import database as db
    from email_parser import print_pack as pp
    from email_parser.pairings_approval import manager_for
    from email_parser.event_day_email import event_short_name, frame, html_to_text

    pack = db.get_event_print_pack(int(event_id), db_path=db_path)
    if not pack:
        return {"error": f"event {event_id} not found"}
    evp = pack["event"]
    appr = approval_state(db_path)
    dl = dials(db_path)
    sent = _sent(event_id, db_path)
    sheet, sheet_why = tee_sheet_block(pack, event_id)
    mailing = (_setting(MAILING_ADDRESS_KEY, db_path) or "").strip()
    footer = FOOTER.format(mailing_address=_e(mailing)) if mailing else ""
    weekend = is_weekend(evp.get("event_date")) if evp.get("event_date") else False
    wk = "weekend" if weekend else "weekday"
    short = event_short_name(evp.get("item_name"), evp.get("course"))
    chap = (evp.get("chapter") or "").strip()
    label = "THE GOLF FELLOWSHIP" + (f" · {chap.upper()}" if chap and chap.upper() != "TGF" else "")
    date_long = _date_long(evp.get("event_date"))
    common = {"event_name": _e(short), "course": _e(evp.get("course")),
              "date_long": _e(date_long), "tee_sheet": sheet, "chapter": _e(chap),
              "mailing_address": _e(mailing), "footer_block": footer}
    try:
        from email_parser.pairings_approval import is_morning_event
        with db._connect(db_path) as _c:
            _evr = _c.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
        common["_morning"] = bool(_evr and is_morning_event(dict(_evr)))
    except Exception:
        _evr = None
        common["_morning"] = False
    # The day words for the day this goes out (Kerry 10/28: lock night). With
    # no `now` (a preview, or the approval path) the words are read as of
    # 7:00 PM on the lock night, the moment it goes by default; a real send
    # only ever happens that evening (send_window_ok).
    try:
        _ref = now
        if _ref is None:
            _lk = db.event_lock_at(dict(_evr) if _evr else dict(evp), db_path)
            if _lk is not None:
                _ref = _lk.replace(hour=max(_lk.hour, SEND_HOUR), minute=0)
            else:
                from email_parser.timezone_utils import now_central as _ncw
                _ref = _ncw()
        common["_when"] = when_words(dict(_evr) if _evr else dict(evp), _ref, db_path)
    except Exception:
        logger.exception("teetimes: day words unavailable for %s", event_id)
        common["_when"] = None
    wk = pack_key(weekend, common["_when"])
    ready, held, skipped = [], [], []

    def add(version, key, cid, name, email, subject_body_why, cc=None, extra=None):
        subject, body, why = subject_body_why
        row = {"version": version, "key": key, "customer_id": cid, "name": name, "email": email}
        if cc:
            row["cc"] = cc
        if extra:
            row.update(extra)
        if key in sent:
            skipped.append({**row, "why": f"already sent {sent[key]}"})
            return
        if sheet_why:
            why = [f"tee sheet: {w}" for w in sheet_why] + [w for w in why if w != "blank: {tee_sheet}"]
        if why:
            # keep the rendered draft so the staff preview can SHOW it (Kerry
            # 10/19: "Don't know what I'm looking at"); never sent while held
            held.append({**row, "reason": "; ".join(why), "subject": subject,
                         "html": frame(body, label, f"Tee times · {short}")})
            return
        ready.append({**row, "subject": subject,
                      "html": frame(body, label, f"Tee times · {short}"),
                      "text": html_to_text(body)})

    conn = db.get_connection(db_path)
    try:
        ev = dict(conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone())
        roster = db._event_roster_rows(conn, int(event_id))
        # 1. PLAYER: the registered roster (RSVP-only rows are not registered).
        people, seen = [], set()
        for r in roster:
            if r.get("rsvp_only"):
                continue
            k = ("c", int(r["customer_id"])) if r.get("customer_id") else ("n", (r.get("name") or "").lower())
            if k in seen:
                continue
            seen.add(k)
            people.append(r)
        registered = {int(r["customer_id"]) for r in people if r.get("customer_id")}
        field = len(people)
        open_seats = spots_left(field)
        tpl_p = load_template("player", db_path)
        for r in people:
            cid = int(r["customer_id"]) if r.get("customer_id") else None
            nm = db.resolve_player_name(r, conn=conn)
            full = (f"{nm.get('first_name', '')} {nm.get('last_name', '')}".strip()
                    or (r.get("name") or "").strip())
            if cid is None:
                held.append({"version": "player", "key": None, "customer_id": None, "name": full,
                             "reason": "no customer_id (identity unresolved)"})
                continue
            email = (db.resolve_player_email(r, conn=conn) or "").strip()
            key = f"player:{cid}"
            if not email or "@" not in email:
                held.append({"version": "player", "key": key, "customer_id": cid, "name": full,
                             "reason": "no email on file"})
                continue
            if not tpl_p:
                held.append({"version": "player", "key": key, "customer_id": cid, "name": full,
                             "email": email, "reason": "template missing"})
                continue
            first = nm.get("first_name") or full.split()[0]
            vals = {**common, "first_name": _e(first), "spots_block": ""}
            add("player", key, cid, full, email, _render("player", tpl_p, vals),
                extra={"spots_box": False})
        # 1b. THE OPEN-SPOTS VERSION (Kerry 10/26, CoS #2386/#2387): seated
        # players get their tee times with no Register box; invitees who are
        # not on the sheet get their own email, only while the sheet has
        # open seats. Audience: the invited (dial teetimes_spots_audience),
        # minus anyone seated, anyone who said Can't make it, opt-outs and
        # known mail scanners.
        open_list = _open_seats(pack)
        n_open = sum(open_list.values())
        seated = {int(p["customer_id"]) for g in pack.get("groups") or []
                  for p in g.get("players") or [] if p.get("customer_id")}
        if dl[SPOTS_DIAL] != "off" and n_open > 0:
            from email_parser import invitations as inv
            evd = date.fromisoformat(str(ev["event_date"])[:10])
            reg_url_on = bool((ev.get("registration_url") or "").strip())
            stamp = int((now or datetime.utcnow()).timestamp())
            for cid in _spots_people(conn, int(event_id), ev, roster, registered | seated,
                                     dl[SPOTS_DIAL], db_path):
                if cid in seated:
                    continue
                try:
                    if inv.known_scanner(int(cid), db_path=db_path):
                        skipped.append({"version": OPEN_VERSION, "key": f"open:{cid}", "customer_id": cid,
                                        "why": "known mail scanner"})
                        continue
                except Exception:
                    pass
                c = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                                 (cid,)).fetchone()
                full = " ".join(x for x in ((c[0], c[1]) if c else ()) if x).strip() or f"#{cid}"
                email = inv._send_email(conn, cid)
                key = f"open:{cid}"
                if not email:
                    held.append({"version": OPEN_VERSION, "key": key, "customer_id": cid, "name": full,
                                 "reason": "no deliverable email"})
                    continue
                reg = (inv.rsvp_url(inv.make_token(cid, int(event_id), "in", evd,
                                                   preview=preview, sent_at=stamp))
                       if reg_url_on else "")
                stop = inv.rsvp_url(inv.make_token(cid, int(event_id), "unsub", evd, preview=preview))
                first = ((c[0] if c else "") or "").strip()
                subject, body, why = _open_message(pack, open_list, first, reg, stop, short,
                                                   ((common.get("_when") or {}).get("event_day")
                                                    or "tomorrow"))
                if sheet_why:
                    why = [f"tee sheet: {w}" for w in sheet_why] + why
                row = {"version": OPEN_VERSION, "key": key, "customer_id": cid, "name": full, "email": email,
                       "spots_box": True}
                if key in sent:
                    skipped.append({**row, "why": f"already sent {sent[key]}"})
                elif why:
                    held.append({**row, "reason": "; ".join(why), "subject": subject,
                                 "html": frame(body, label, OPEN["title"].format(short=short))})
                else:
                    ready.append({**row, "subject": subject,
                                  "html": frame(body, label, OPEN["title"].format(short=short)),
                                  "text": html_to_text(body)})
    finally:
        conn.close()

    # 2. COURSE CONTACT.
    rec = pp.course_recipients_for_event(ev, db_path)
    has_contact = bool(rec.get("ok"))
    tpl_c = load_template("course", db_path)
    if not has_contact:
        skipped.append({"version": "course", "key": None, "why": rec.get("why") or "no course contact"})
    else:
        prim = next((s for s in rec.get("staff") or [] if s.get("is_primary")), {})
        cid = prim.get("customer_id")
        key = f"course:{cid or rec['to'].lower()}"
        first = (rec.get("to_name") or "").split()[0] if rec.get("to_name") else ""
        if not tpl_c:
            held.append({"version": "course", "key": key, "customer_id": cid, "name": rec.get("to_name"),
                         "email": rec["to"], "reason": "template missing"})
        else:
            vals = {**common, "first_name": _e(first),
                    "pack_line": _t(pack_text(PACK_LINE[wk], common["_when"]))}
            # THE RELEASED TEE TIMES (Kerry 10/26, CoS #2331 A / #2332: "let
            # the course know which ones"): rendered by code under the tee
            # sheet, inside {tee_sheet}, so the stamped template and its hash
            # are unchanged.
            if common["tee_sheet"]:
                vals["tee_sheet"] = common["tee_sheet"] + released_block(ev, db_path)
            add("course", key, cid, rec.get("to_name"), rec["to"], _render("course", tpl_c, vals),
                cc=list(rec.get("cc") or []))

    # 3. MANAGER: the sent line says what this run actually sends.
    # (already sent counts too: a course stamped earlier went in an earlier run)
    players_go = (any(k.startswith("player:") for k in sent)
                  or (appr["player"]["approved"] and any(m["version"] == "player" for m in ready)))
    course_go = (any(k.startswith("course:") for k in sent)
                 or (appr["course"]["approved"] and any(m["version"] == "course" for m in ready)))
    sent_line = SENT_LINE["both" if players_go and course_go else "players" if players_go
                          else "course" if course_go else "neither"]
    # The time it ACTUALLY went (CoS #2386-2: an approval at 5:16 PM read
    # "at 7:00 PM"): the earliest player/course send on record, else now.
    from email_parser.timezone_utils import clock12, now_central, to_central
    _went = sorted(v for k, v in sent.items() if k.startswith(("player:", "course:")))
    _at = to_central(_went[0]) if _went else (now or now_central())
    sent_line = sent_line.replace("{sent_time}", clock12(_at))
    mgr = manager_for(chap, db_path)
    tpl_m = load_template("manager", db_path)
    if not mgr.get("email"):
        held.append({"version": "manager", "key": None, "customer_id": mgr.get("customer_id"),
                     "name": mgr.get("name"), "reason": f"no manager email for chapter {chap!r}"})
    elif not tpl_m:
        held.append({"version": "manager", "key": None, "customer_id": mgr.get("customer_id"),
                     "name": mgr.get("name"), "email": mgr["email"], "reason": "template missing"})
    else:
        mcid = mgr.get("customer_id")
        key = f"manager:{mcid or mgr['email'].lower()}"
        closing = "<p>" + _t(pack_text(MANAGER_LINE[("contact" if has_contact else "none", wk)],
                                       common["_when"])) + "</p>"
        if not has_contact:
            url = f"{_base_url()}/courses" + (f"?course={int(rec['course_id'])}" if rec.get("course_id") else "")
            closing += "<p>" + ADD_CONTACT_LINE.format(add_contact_url=_e(url)) + "</p>"
        vals = {**common, "first_name": _e((mgr.get("name") or "").split()[0] if mgr.get("name") else ""),
                "sent_line": _t(sent_line), "closing_block": closing}
        add("manager", key, int(mcid) if mcid else None, mgr.get("name"), mgr["email"],
            _render("manager", tpl_m, vals), extra={"course_contact_on_file": has_contact})

    counts = {v: {"ready": sum(1 for m in ready if m["version"] == v),
                  "held": sum(1 for m in held if m["version"] == v),
                  "skipped": sum(1 for m in skipped if m["version"] == v)} for v in SEND_ORDER}
    return {"event": {"id": int(event_id), "name": evp.get("item_name"), "date": evp.get("event_date"),
                      "course": evp.get("course"), "chapter": chap, "weekend": weekend},
            "field": field, "spots_left": open_seats, "approvals": appr, "dials": dl,
            "mailing_address_on_file": bool(mailing), "tee_sheet_problems": sheet_why,
            "counts": counts, "messages": ready, "held": held, "skipped": skipped}


def summarize(built: dict) -> dict:
    """The dry build as a bridge report: per-recipient ready / held."""
    if built.get("error"):
        return built
    out = {k: v for k, v in built.items() if k != "messages"}
    out["ready"] = [{k: m.get(k) for k in ("version", "customer_id", "name", "email", "cc", "spots_box")}
                    for m in built["messages"]]
    out["would_send_now"] = [m["version"] + ":" + str(m["customer_id"]) for m in built["messages"]
                             if built["approvals"][m["version"]]["approved"]
                             and built["dials"][AUTO_DIAL] == "on"]
    out["samples"] = {}
    for m in built["messages"]:
        out["samples"].setdefault(m["version"], {"to": m["email"], "subject": m["subject"], "text": m["text"]})
    return out


# ---------------------------------------------------------------------------
# Preview (staff only)
# ---------------------------------------------------------------------------

def send_preview(event_id: int, to_address=None, db_path=None) -> dict:
    from email_parser import database as db
    from email_parser.event_day_email import _creds, _graph_send
    from email_parser.recap_mail import staff_only, _addrs
    to = _addrs(to_address) or [DEFAULT_PREVIEW_TO]
    bad = staff_only(to, lambda k: _setting(k, db_path))
    if bad:
        return {"error": f"the tee-times preview goes to TGF staff only; refused {bad}"}
    built = build(event_id, db_path=db_path, preview=True)
    if built.get("error"):
        return built
    ev = built["event"]
    LABEL = {"player": "1. PLAYER version (each registered player)",
             "course": "2. COURSE CONTACT version",
             "manager": "3. MANAGER version"}
    spots_m = next((x for x in built["messages"] + built["held"]
                    if x.get("spots_box") and x.get("html")), None)
    n_spots = sum(1 for x in built["messages"] if x.get("spots_box"))
    parts = [f"<p><strong>Tee-times email preview: {_e(ev['name'])}</strong> ({_e(ev['date'])}). "
             f"Below are the three emails exactly as they would go out. Nothing has been sent.</p>"]
    for v in VERSIONS:
        m = next((x for x in built["messages"] if x["version"] == v and not x.get("spots_box")), None) \
            or next((x for x in built["held"] if x["version"] == v and x.get("html")), None)
        parts.append('<hr style="border:0;border-top:3px solid #E87C3E;margin:24px 0 8px">'
                     f"<p style=\"font:bold 16px Arial,sans-serif\">{LABEL[v]}</p>")
        if not m:
            sk = next((x for x in built["skipped"] if x["version"] == v), None)
            parts.append(f"<p><i>Not sent for this event: {_e((sk or {}).get('why') or 'no recipient')}</i></p>")
            continue
        parts.append(f"<p style=\"color:#6B7280\">To: {_e(m['name'])} &lt;{_e(m['email'])}&gt;"
                     + (f"<br>CC: {_e(', '.join(m['cc']))}" if m.get("cc") else "")
                     + f"<br>Subject: {_e(m['subject'])}</p>" + m["html"])
    parts.append('<hr style="border:0;border-top:3px solid #E87C3E;margin:24px 0 8px">'
                 f"<p style=\"font:bold 16px Arial,sans-serif\">4. NOT REGISTERED version "
                 f"(everyone invited who hasn't registered or said Can't make it: {n_spots} people)</p>")
    if spots_m:
        parts.append(f"<p style=\"color:#6B7280\">To: {_e(spots_m['name'])} &lt;{_e(spots_m['email'])}&gt;"
                     f"<br>Subject: {_e(spots_m['subject'])}</p>" + spots_m["html"])
    else:
        parts.append("<p><i>Not sent: " + ("the event is full." if not built.get("spots_left")
                     else f"the {SPOTS_DIAL} switch is off.") + "</i></p>")
    # Plain-English status at the bottom.
    why_not = []
    if built.get("tee_sheet_problems"):
        why_not.append("tonight's pairings aren't saved yet (5:00 PM)")
    if not built.get("mailing_address_on_file"):
        pass   # no address: the player version sends without its footer line
    unstamped = [v for v in VERSIONS if not built["approvals"][v]["approved"]]
    if unstamped:
        why_not.append("your OK on the wording of: " + ", ".join(unstamped))
    if built["dials"][AUTO_DIAL] != "on":
        why_not.append("the send switch is off")
    parts.append('<hr style="border:0;border-top:3px solid #E87C3E;margin:24px 0 8px">'
                 "<p><strong>What it's waiting on before anything sends:</strong></p><ul>"
                 + "".join(f"<li>{_e(w)}</li>" for w in why_not) + "</ul>"
                 + (f"<p style=\"color:#6B7280;font-size:12px\">Players: {built['counts']['player']['ready']} ready, "
                    f"{built['counts']['player']['held']} waiting. Wording codes: "
                    + ", ".join(f"{v} {built['approvals'][v]['template_hash']}" for v in VERSIONS) + ".</p>"))
    subject = f"PREVIEW: tee-times email: {ev['name']}"
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    ok = _graph_send(creds, ",".join(to), subject, "".join(parts))
    try:
        db.log_message({"event_name": "teetimes-preview", "channel": "email",
                        "recipient_name": "staff preview", "recipient_address": ",".join(to),
                        "subject": subject, "body_preview": f"event {event_id}",
                        "status": "sent" if ok else "failed", "sent_by": "teetimes_email",
                        "event_id": int(event_id)}, db_path=db_path)
    except Exception:
        logger.exception("teetimes preview log failed (non-fatal)")
    return {"status": "sent" if ok else "failed", "to": to, "subject": subject,
            "counts": built["counts"],
            "approvals": {v: built["approvals"][v]["approved"] for v in VERSIONS}}


# ---------------------------------------------------------------------------
# The send (only the 7 PM job calls this)
# ---------------------------------------------------------------------------

def send_window_ok(event, now: datetime | None = None, db_path=None) -> str | None:
    """None when the tee-times email may go now, else why not. It goes on the
    LOCK evening (Kerry 10/28: "That would need to be moved to the night of
    the lock and pairings generation...same as Tuesday events"): from the
    event's lock (database.event_lock_at: 5:00 PM the day before a Tuesday,
    Wednesday 5:00 PM for a Saturday) to midnight that day, and never on event
    day (handoff 10/20 §4 risk 1: an approval on event morning sent it).
    `event` is the events row (a dict) or, for older callers, its date."""
    from email_parser import database as db
    from email_parser.timezone_utils import clock12
    if now is None:
        from email_parser.timezone_utils import now_central
        now = now_central()
    ev = event if isinstance(event, dict) else {"event_date": str(event or "")[:10]}
    try:
        ev_day = datetime.strptime(str(ev.get("event_date") or "")[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return "event date unreadable"
    lock = db.event_lock_at(ev, db_path)
    if lock is None:
        return "event date unreadable"
    when = f"{lock.strftime('%A')} from the {clock12(lock)} lock to midnight"
    if now.date() >= ev_day or now.date() != lock.date():
        return f"the tee-times email goes only on the lock evening ({when})"
    if now < lock:
        return f"the tee-times email goes from the {clock12(lock)} lock, not before"
    return None


CLAIM_KEY = "teetimes_claim:{event_id}:{key}"


def _claim(event_id: int, key: str, db_path=None) -> bool:
    """Atomically claim one message before it is sent. Two senders can run at
    once (the manager's approval and the every-5-minute job both deliver an
    approved sheet); on 10/26 at 5:16 PM both read an empty sent-map and
    every Silverhorn email went twice. Exactly one caller wins the claim:
    the row is inserted only if it is not there (app_settings.key is the
    primary key), and the winner is the one whose insert landed."""
    from email_parser import database as db
    ck = CLAIM_KEY.format(event_id=int(event_id), key=key)
    with db._connect(db_path) as conn:
        cur = conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
                           (ck, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return (cur.rowcount or 0) == 1


def _release_claim(event_id: int, key: str, db_path=None) -> None:
    """A failed send gives its claim back so the next run can try again."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        conn.execute("DELETE FROM app_settings WHERE key = ?",
                     (CLAIM_KEY.format(event_id=int(event_id), key=key),))
        conn.commit()


def _mark_sent(setting_key: str, msg_key: str, db_path=None) -> None:
    """Add one message to the sent map as ONE write transaction. Two senders
    each re-reading and rewriting the whole map lost an entry when their
    writes crossed (test_teetimes_email, two senders at once): BEGIN
    IMMEDIATE holds the write lock from the read to the commit."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        r = conn.execute("SELECT value FROM app_settings WHERE key = ?", (setting_key,)).fetchone()
        try:
            cur = json.loads((r[0] if r else None) or "{}")
            cur = cur if isinstance(cur, dict) else {}
        except Exception:
            cur = {}
        cur[msg_key] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
                     (setting_key, json.dumps(cur, sort_keys=True)))
        conn.commit()


def _deliver(event_id: int, db_path=None, now: datetime | None = None) -> dict:
    from email_parser import database as db
    from email_parser.event_day_email import _creds
    from email_parser import fetcher
    if dials(db_path)[AUTO_DIAL] != "on":
        return {"refused": f"{AUTO_DIAL} is not on"}
    # every sender comes through here (the 7 PM job and a manager's approval),
    # so the evening-before window is checked once, for all of them
    with db._connect(db_path) as conn:
        _r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    _why = send_window_ok(dict(_r) if _r else None, now, db_path)
    if _why:
        return {"refused": _why}
    built = build(event_id, db_path=db_path, now=now)
    if built.get("error"):
        return built
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    key = SENT_KEY.format(event_id=int(event_id))
    sent_map = _sent(event_id, db_path)
    sent, failed, locked = [], [], []
    # Players and course first, then the manager (whose line says what went).
    order = sorted(built["messages"], key=lambda m: SEND_ORDER.index(m["version"]))
    for m in order:
        if not built["approvals"][m["version"]]["approved"]:
            locked.append({"version": m["version"], "customer_id": m["customer_id"],
                           "why": f"wording not stamped ({APPROVAL_KEYS[m['version']]})"})
            continue
        if m["key"] in sent_map:
            continue
        if not _claim(event_id, m["key"], db_path):
            continue          # another sender has it (or already sent it)
        ok = False
        try:
            ok = fetcher.send_mail_graph(tenant_id=creds[0], client_id=creds[1], client_secret=creds[2],
                                         from_address=creds[3], to_address=m["email"],
                                         subject=m["subject"], html_body=m["html"],
                                         cc_address=", ".join(m.get("cc") or []) or None)
        except Exception:
            logger.exception("teetimes send failed for %s", m["key"])
        row = {"version": m["version"], "customer_id": m["customer_id"], "name": m["name"],
               "email": m["email"]}
        (sent if ok else failed).append(row)
        if ok:
            _mark_sent(key, m["key"], db_path)
        else:
            _release_claim(event_id, m["key"], db_path)
        try:
            db.log_message({"event_name": built["event"]["name"], "channel": "email",
                            "recipient_name": m["name"], "recipient_address": m["email"],
                            "subject": m["subject"], "body_preview": f"tee times ({m['version']})",
                            "status": "sent" if ok else "failed", "sent_by": f"teetimes_{m['version']}",
                            "event_id": int(event_id), "customer_id": m["customer_id"]},
                           db_path=db_path)
        except Exception:
            logger.exception("teetimes log failed (non-fatal)")
    return {"event": built["event"], "sent": sent, "failed": failed, "locked": locked,
            "held": built["held"], "skipped": built["skipped"]}


def auto_check(now: datetime | None = None, db_path=None) -> dict:
    """The 7:00 PM job. Nothing unless `teetimes_email_auto` is 'on'. Each
    active event dated TOMORROW with a saved sheet gets the three versions,
    from 7:00 PM to midnight Central; each version only if stamped."""
    from email_parser import database as db
    from email_parser.live_scoring_default import _skip_reason
    if dials(db_path)[AUTO_DIAL] != "on":
        return {"status": "off"}
    if now is None:
        from email_parser.timezone_utils import now_central
        now = now_central()
    # Kerry 10/19: "goes out to the parties as designated between 5-7 either
    # upon manager approval or 7pm end of review window". From 5 PM an
    # approved sheet goes at once; at 7 PM every sheet goes.
    if now.hour < OPEN_HOUR:
        return {"status": "not yet"}
    # Events whose LOCK is tonight (Kerry 10/28): a Tuesday event the evening
    # before, a Saturday event on Wednesday.
    with db._connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM events WHERE substr(event_date, 1, 10) > ? AND substr(event_date, 1, 10) <= ? "
            "AND COALESCE(status, 'active') = 'active'",
            (now.date().isoformat(), (now.date() + timedelta(days=7)).isoformat())).fetchall()]
    rows = [r for r in rows if send_window_ok(r, now, db_path) is None]
    out = {}
    for ev in rows:
        eid = int(ev["id"])
        try:
            why = _skip_reason(ev, db_path)
            if why:
                out[eid] = {"skipped": why}
                continue
            from email_parser.pairings_approval import sheet_fingerprint
            fp = sheet_fingerprint(eid, db_path)
            if not fp:
                out[eid] = {"skipped": "no saved pairings"}
                continue
            if now.hour < SEND_HOUR:
                from email_parser.pairings_approval import event_state
                if event_state(eid, db_path).get("approved_fp") != fp:
                    out[eid] = {"skipped": "waiting for the manager's approval or 7 PM"}
                    continue
            out[eid] = _deliver(eid, db_path, now=now)
        except Exception as exc:
            logger.exception("teetimes auto failed for %s", eid)
            out[eid] = {"error": str(exc)}
    return {"status": "ran", "events": out}
