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
    "both": "This went to the players and the course at 7:00 PM.",
    "players": "This went to the players at 7:00 PM.",
    "course": "This went to the course at 7:00 PM.",
    "neither": "No tee-times email went to the players or the course.",
}
FOOTER = '<p style="font-size:12px;color:#6B7280;">The Golf Fellowship &middot; {mailing_address}</p>'

_FIXED = {
    "player": (PRELIM_LINE, TEESHEET_LINK, SPOTS_BOX["one"], SPOTS_BOX["many"]),
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


def approval_state(db_path=None) -> dict:
    """{version: {template, template_hash, approval_key, approved}}."""
    out = {}
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


def _render(version: str, tpl: dict, values: dict) -> tuple[str, str, list]:
    from email_parser.fetcher import render_msg_template, normalize_email_html
    from email_parser.event_day_email import html_to_text
    used = set(_TAG_RE.findall(tpl["subject"] + tpl["html_body"]))
    subject = html_to_text(render_msg_template(tpl["subject"], values))
    body = normalize_email_html(render_msg_template(tpl["html_body"], values))
    return subject, body, _guard(subject, body, used, values)


# ---------------------------------------------------------------------------
# Build (nothing is sent)
# ---------------------------------------------------------------------------

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
            held.append({**row, "reason": "; ".join(why)})
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
        # 1b. The spots box: non-registered recipients, dial-gated, only while open.
        if dl[SPOTS_DIAL] != "off" and open_seats > 0 and tpl_p:
            from email_parser import invitations as inv
            evd = date.fromisoformat(str(ev["event_date"])[:10])
            reg_url_on = bool((ev.get("registration_url") or "").strip())
            stamp = int((now or datetime.utcnow()).timestamp())
            for cid in _spots_people(conn, int(event_id), ev, roster, registered, dl[SPOTS_DIAL], db_path):
                c = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                                 (cid,)).fetchone()
                full = " ".join(x for x in ((c[0], c[1]) if c else ()) if x).strip() or f"#{cid}"
                email = inv._send_email(conn, cid)
                key = f"player:{cid}"
                if not email:
                    held.append({"version": "player", "key": key, "customer_id": cid, "name": full,
                                 "reason": "no deliverable email"})
                    continue
                link = (inv.rsvp_url(inv.make_token(cid, int(event_id), "in", evd,
                                                    preview=preview, sent_at=stamp))
                        if reg_url_on else "")
                box_t = SPOTS_BOX["one"] if open_seats == 1 else SPOTS_BOX["many"]
                box = ("<p>" + box_t.format(spots_left=open_seats, registration_link=_e(link)) + "</p>"
                       if link else "")
                vals = {**common, "first_name": _e((c[0] if c else "") or "there"),
                        "spots_block": box}
                s, b, why = _render("player", tpl_p, vals)
                if not link:
                    why = why + ["blank: {registration_link} (the event has no registration link)"]
                add("player", key, cid, full, email, (s, b, why), extra={"spots_box": True})
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
            vals = {**common, "first_name": _e(first), "pack_line": _t(PACK_LINE[wk])}
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
        closing = "<p>" + _t(MANAGER_LINE[("contact" if has_contact else "none", wk)]) + "</p>"
        if not has_contact:
            url = f"{_base_url()}/courses" + (f"?course={int(rec['course_id'])}" if rec.get("course_id") else "")
            closing += "<p>" + ADD_CONTACT_LINE.format(add_contact_url=_e(url)) + "</p>"
        vals = {**common, "first_name": _e((mgr.get("name") or "").split()[0] if mgr.get("name") else ""),
                "sent_line": _t(sent_line), "closing_block": closing}
        add("manager", key, int(mcid) if mcid else None, mgr.get("name"), mgr["email"],
            _render("manager", tpl_m, vals), extra={"course_contact_on_file": has_contact})

    counts = {v: {"ready": sum(1 for m in ready if m["version"] == v),
                  "held": sum(1 for m in held if m["version"] == v),
                  "skipped": sum(1 for m in skipped if m["version"] == v)} for v in VERSIONS}
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
    parts = [f"<p><strong>Tee-times email PREVIEW</strong> for <strong>{_e(ev['name'])}</strong> "
             f"({_e(ev['date'])}, {_e(ev['course'])}). Nothing has been sent to any player, course or "
             f"manager.</p><p>Job dial {AUTO_DIAL}: <b>{built['dials'][AUTO_DIAL]}</b>; "
             f"spots dial {SPOTS_DIAL}: <b>{built['dials'][SPOTS_DIAL]}</b>; field {built['field']}, "
             f"spots left {built['spots_left']}.</p><ul>"]
    for v in VERSIONS:
        a = built["approvals"][v]
        c = built["counts"][v]
        parts.append(f"<li><b>{_e(a['template'])}</b>: hash <code>{_e(a['template_hash'])}</code> "
                     f"{'APPROVED' if a['approved'] else 'NOT approved (' + a['approval_key'] + ')'}; "
                     f"ready {c['ready']}, held {c['held']}, skipped {c['skipped']}</li>")
    parts.append("</ul>")
    shown = set()
    for m in built["messages"]:
        tag = (m["version"], m.get("spots_box"))
        if tag in shown:
            continue
        shown.add(tag)
        parts.append('<hr style="border:0;border-top:2px solid #E87C3E">'
                     f"<p><strong>{_e(TEMPLATES[m['version']])}</strong>"
                     + (" (with the spots box)" if m.get("spots_box") else "")
                     + f"<br><strong>To:</strong> {_e(m['name'])} &lt;{_e(m['email'])}&gt;"
                     + (f"<br><strong>CC:</strong> {_e(', '.join(m['cc']))}" if m.get("cc") else "")
                     + f"<br><strong>Subject:</strong> {_e(m['subject'])}</p>" + m["html"])
    parts.append('<hr style="border:0;border-top:2px solid #E87C3E">')
    if built["held"]:
        parts.append("<p><strong>HELD:</strong></p><ul>" + "".join(
            f"<li>{_e(h['version'])}: {_e(h.get('name'))} (cid {_e(h.get('customer_id'))}): "
            f"{_e(h['reason'])}</li>" for h in built["held"]) + "</ul>")
    if built["skipped"]:
        parts.append("<p><strong>Skipped:</strong></p><ul>" + "".join(
            f"<li>{_e(s['version'])}: {_e(s.get('name') or '')} {_e(s['why'])}</li>"
            for s in built["skipped"]) + "</ul>")
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

def _deliver(event_id: int, db_path=None) -> dict:
    from email_parser import database as db
    from email_parser.event_day_email import _creds
    from email_parser import fetcher
    if dials(db_path)[AUTO_DIAL] != "on":
        return {"refused": f"{AUTO_DIAL} is not on"}
    built = build(event_id, db_path=db_path)
    if built.get("error"):
        return built
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    key = SENT_KEY.format(event_id=int(event_id))
    sent_map = _sent(event_id, db_path)
    sent, failed, locked = [], [], []
    # Players and course first, then the manager (whose line says what went).
    order = sorted(built["messages"], key=lambda m: VERSIONS.index(m["version"]))
    for m in order:
        if not built["approvals"][m["version"]]["approved"]:
            locked.append({"version": m["version"], "customer_id": m["customer_id"],
                           "why": f"wording not stamped ({APPROVAL_KEYS[m['version']]})"})
            continue
        if m["key"] in sent_map:
            continue
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
            sent_map[m["key"]] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            db.set_app_setting(key, json.dumps(sent_map, sort_keys=True), db_path=db_path)
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
    if now.hour < SEND_HOUR:
        return {"status": "not yet"}
    tomorrow = (now.date() + timedelta(days=1)).isoformat()
    with db._connect(db_path) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT id, item_name, event_date, status FROM events WHERE substr(event_date, 1, 10) = ? "
            "AND COALESCE(status, 'active') = 'active'", (tomorrow,)).fetchall()]
    out = {}
    for ev in rows:
        eid = int(ev["id"])
        try:
            why = _skip_reason(ev, db_path)
            if why:
                out[eid] = {"skipped": why}
                continue
            from email_parser.pairings_approval import sheet_fingerprint
            if not sheet_fingerprint(eid, db_path):
                out[eid] = {"skipped": "no saved pairings"}
                continue
            out[eid] = _deliver(eid, db_path)
        except Exception as exc:
            logger.exception("teetimes auto failed for %s", eid)
            out[eid] = {"error": str(exc)}
    return {"status": "ran", "events": out}
