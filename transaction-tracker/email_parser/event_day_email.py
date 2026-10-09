"""The EVENT-DAY EMAIL (CA #829, GO'd; Kerry OKs the wording before any send).

One email per player on an event's roster: their start (tee time or hole,
stated the way the Starter Sheet states it), their group-mates, their cart
partner when the sheet seats one, the course and the date, and which game
bundles they bought. Golf Genius sends this today and goes away after
10/10; the Tracker sends it for events from 10/13.

Where each fact comes from — nothing here is a second derivation:
- WHO is on the event: `_event_roster_rows` (the one roster builder).
- WHERE they play: `get_event_print_pack` — the saved sheet
  (`get_event_pairings`) with `start_line` composed exactly as the Starter
  Sheet and the Cart Signs print it (slot labels dealt by
  `_pairing_time_slots`; "Hole 3A | 8:00 AM" on a shotgun, "8:10 AM |
  Hole 1" on tee times). Seats 1&2 share a cart, 3&4 the other.
- NAME / EMAIL: `resolve_player_name` / `resolve_player_email`.
- GAMES: `_event_game_buyers` — the Games tab's own buyer rule (parent row
  + child add-on payments, credited/refunded/transferred/RSVP out, a WD
  whose bundle was credited back out) — against the event's GAMES OFFERED
  (`get_event_bundle_offers`) and the bundle catalog. When that cannot be
  read reliably (a day-games championship, a package event, an RSVP-only
  player, no customer_id) the games block is left OUT, never guessed.
- WORDING: the system template "Event Day — Your Pairing" in
  `message_templates` (seeded in database.py, editable in the UI),
  rendered with `render_msg_template` + `normalize_email_html`.

THE BOUNDARY GUARD ("protect the class", handoff 2026-09-08 §7): a message
is HELD, never sendable, when any variable the template uses is empty and
is not one of the optional blocks, when a `{tag}` survives rendering, or
when a `[BRACKETED BLANK]` is left in it. Held messages are reported with
the reason; they never reach `send_mail_graph`.

SENDS:
- `send_event_day_preview` mails ONE combined preview to STAFF ONLY
  (recap_mail.staff_only: @thegolffellowship.com or `recap_draft_allow`).
- `send_event_day_emails` is the member send. It refuses unless app
  setting `event_day_email_approved` equals the CURRENT template hash
  (Kerry's approval stamp — an edit to the wording voids it) AND
  `confirm=True`. One row per event + customer_id in
  `event_day_email_sends` is claimed before the Graph call, so a member is
  never mailed twice for one event.
"""
from __future__ import annotations

import hashlib
import html as _html
import logging
import os
import re
from datetime import datetime

logger = logging.getLogger(__name__)

TEMPLATE_NAME = "Event Day — Your Pairing"
APPROVAL_KEY = "event_day_email_approved"
DEFAULT_PREVIEW_TO = "kerry@thegolffellowship.com"
PREVIEW_SAMPLES = 3

# Blocks that may be legitimately absent: each renders as a whole
# paragraph or nothing, so its absence leaves no dangling words.
OPTIONAL_VARS = {"cart_block", "games_block", "scoring_block"}

_TAG_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_BLANK_RE = re.compile(r"\[[A-Z][A-Z0-9 _/\-]*\]")


# ---------------------------------------------------------------------------
# Schema — one row per event + customer, the never-twice record
# ---------------------------------------------------------------------------

def _ensure_event_day_tables_inner(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS event_day_email_sends (
               id            INTEGER PRIMARY KEY AUTOINCREMENT,
               event_id      INTEGER NOT NULL REFERENCES events(id),
               customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
               email         TEXT NOT NULL,
               template_hash TEXT NOT NULL,
               status        TEXT NOT NULL,
               sent_at       TEXT,
               UNIQUE (event_id, customer_id)
           )""")
    conn.commit()


_ensure_once = None


def ensure_event_day_tables(conn) -> None:
    """Lazy DDL, once per database file per process (CLAUDE.md)."""
    from email_parser.database import _once_per_db
    global _ensure_once
    if _ensure_once is None:
        _ensure_once = _once_per_db(_ensure_event_day_tables_inner)
    _ensure_once(conn)


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

def load_template(db_path=None) -> dict | None:
    from email_parser import database as db
    conn = db.get_connection(db_path)
    try:
        r = conn.execute(
            "SELECT id, subject, html_body FROM message_templates "
            "WHERE lower(name) = lower(?) ORDER BY is_system DESC, id LIMIT 1",
            (TEMPLATE_NAME,)).fetchone()
    finally:
        conn.close()
    if not r:
        return None
    return {"id": r["id"], "subject": r["subject"] or "",
            "html_body": r["html_body"] or "",
            "hash": template_hash(r["subject"] or "", r["html_body"] or "")}


def template_hash(subject: str, html_body: str) -> str:
    return hashlib.sha256(f"{subject}\n{html_body}".encode("utf-8")).hexdigest()[:16]


def approval_state(tpl: dict | None, db_path=None) -> dict:
    from email_parser import database as db
    try:
        stamp = (db.get_app_setting(APPROVAL_KEY, db_path=db_path) or "").strip()
    except Exception:
        stamp = ""
    cur = tpl["hash"] if tpl else None
    return {"template_hash": cur, "approved_hash": stamp or None,
            "approved": bool(cur and stamp and stamp == cur)}


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _e(s) -> str:
    return _html.escape(str(s or ""), quote=False)


def _pretty_date(d: str | None) -> str:
    try:
        return datetime.strptime((d or "")[:10], "%Y-%m-%d").strftime("%A, %B %-d, %Y")
    except ValueError:
        return ""


def html_to_text(h: str) -> str:
    t = re.sub(r"(?i)<br\s*/?>", "\n", h or "")
    t = re.sub(r"(?i)</p\s*>", "\n\n", t)
    t = re.sub(r"(?i)<li[^>]*>", "- ", t)
    t = re.sub(r"(?i)</(li|ul|ol)\s*>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = _html.unescape(t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _guard(subject: str, html_body: str, text: str, used: set, values: dict) -> list:
    """Every reason this rendered message must not leave. Empty = sendable."""
    why = []
    for v in sorted(used):
        if v in OPTIONAL_VARS:
            continue
        if not str(values.get(v) or "").strip():
            why.append(f"blank: {{{v}}}")
    left = sorted(set(_TAG_RE.findall(subject + " " + html_body + " " + text)))
    if left:
        why.append("unrendered: " + ", ".join("{" + x + "}" for x in left))
    blanks = sorted(set(_BLANK_RE.findall(subject + " " + text)))
    if blanks:
        why.append("bracketed blank: " + ", ".join(blanks))
    return why


def _games_context(conn, ev: dict, db_path=None) -> dict:
    """{'ok': bool, 'why': str, 'offered': [...], 'names': {NET: '...'},
    'buyers': {'NET': {cid}, 'GROSS': {cid}}} — ok False means the games
    block is left out for everyone on this event."""
    from email_parser import database as db
    eid = int(ev["id"])
    try:
        if str(eid) in (db.get_event_games_axis(db_path) or {}):
            return {"ok": False, "why": "day-games (championship) event"}
    except Exception:
        return {"ok": False, "why": "games axis unreadable"}
    try:
        if (db.get_all_event_packages(db_path) or {}).get(str(eid)):
            return {"ok": False, "why": "package event"}
    except Exception:
        return {"ok": False, "why": "package config unreadable"}
    try:
        offered = [k for k in (db.get_event_bundle_offers(eid, db_path).get("offered") or [])
                   if k in ("NET", "GROSS")]
    except Exception:
        return {"ok": False, "why": "games offered unreadable"}
    if not offered:
        return {"ok": False, "why": "event offers no game bundles"}
    names = {}
    try:
        cat = db.get_bundle_catalog(db_path)
        gname = {g["game_key"]: g["name"] for g in cat.get("games") or []}
        for b in cat.get("bundles") or []:
            if b["bundle_key"] in offered:
                names[b["bundle_key"]] = " + ".join(gname.get(k, k) for k in b.get("games") or [])
    except Exception:
        names = {}
    buyers = {}
    for kind in offered:
        res = db._event_game_buyers(conn, ev.get("item_name") or "", kind)
        buyers[kind] = {int(c) for c in (res.get("buyers") or {})}
    return {"ok": True, "offered": offered, "names": names, "buyers": buyers}


def _games_block(gctx: dict, roster_row: dict) -> tuple[str, str]:
    """(html, why-empty). Only for an ORDER row with a customer_id on an
    event whose games can be read; otherwise nothing."""
    if not gctx.get("ok"):
        return "", gctx.get("why") or "games unknown"
    if roster_row.get("rsvp_only"):
        return "", "RSVP only — no purchase to read"
    cid = roster_row.get("customer_id")
    if not cid:
        return "", "no customer_id"
    items = []
    for kind in gctx["offered"]:
        inside = gctx["names"].get(kind)
        label = f"{kind} games" + (f" ({inside})" if inside else "")
        state = "you're in" if int(cid) in gctx["buyers"].get(kind, set()) else "not bought"
        items.append(f"<li>{_e(label)}: <strong>{_e(state)}</strong></li>")
    return "<p><strong>Your games:</strong></p><ul>" + "".join(items) + "</ul>", ""


def _seat_index(groups: list) -> dict:
    from email_parser.database import _pair_key_name
    idx = {}
    for g in groups:
        for p in g.get("players") or []:
            if p.get("customer_id") is not None:
                idx.setdefault(("c", int(p["customer_id"])), (g, p))
            if p.get("name"):
                idx.setdefault(("n", _pair_key_name(p["name"])), (g, p))
    return idx


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_event_day_emails(event_id: int, db_path=None) -> dict:
    """Render every roster player's message (nothing is sent).

    Returns {event, template_hash, approved, counts, messages, held,
    games_note}. `messages` are sendable; `held` carries a reason each."""
    from email_parser import database as db
    from email_parser.fetcher import render_msg_template, normalize_email_html

    tpl = load_template(db_path)
    appr = approval_state(tpl, db_path)
    pack = db.get_event_print_pack(int(event_id), db_path=db_path)
    if not pack:
        return {"error": f"event {event_id} not found"}
    ev_info = pack["event"]
    groups = pack.get("groups") or []
    seats = _seat_index(groups)
    manager = db.get_chapter_manager(ev_info.get("chapter"), db_path=db_path)
    # Each player's own group scoring link (Kerry 10/8, the practice round:
    # "send all of tomorrow's info"): only when the event is in Live Scoring
    # and its round is seeded; READ ONLY, never seeds a round.
    links = {}
    try:
        from email_parser import score_entry as _se
        if _se.event_enabled(int(event_id), db_path=db_path):
            for hk in {str(g.get("holes") or "") for g in groups if g.get("holes")}:
                links[hk] = _se.event_group_links(int(event_id), hk, db_path=db_path)
    except Exception:
        logger.exception("event-day email: scoring links unavailable (non-fatal)")
        links = {}

    conn = db.get_connection(db_path)
    try:
        ev = dict(conn.execute("SELECT * FROM events WHERE id = ?",
                               (int(event_id),)).fetchone())
        roster = db._event_roster_rows(conn, int(event_id))
        gctx = _games_context(conn, ev, db_path)

        # One person, one message: dedupe the roster by customer_id, then
        # by name for a row with none.
        people, seen = [], set()
        for r in roster:
            key = (("c", int(r["customer_id"])) if r.get("customer_id")
                   else ("n", db._pair_key_name(r.get("name") or "")))
            if key in seen:
                continue
            seen.add(key)
            people.append(r)

        messages, held = [], []
        used = set(_TAG_RE.findall((tpl or {}).get("subject", "") + (tpl or {}).get("html_body", "")))
        for r in people:
            cid = int(r["customer_id"]) if r.get("customer_id") else None
            nm = db.resolve_player_name(r, conn=conn)
            full = (f"{nm.get('first_name', '')} {nm.get('last_name', '')}".strip()
                    or (r.get("name") or "").strip())
            base = {"customer_id": cid, "name": full}
            if not tpl:
                held.append({**base, "reason": f"template {TEMPLATE_NAME!r} missing"})
                continue
            if cid is None:
                held.append({**base, "reason": "no customer_id (identity unresolved)"})
                continue
            email = (db.resolve_player_email(r, conn=conn) or "").strip()
            if not email or "@" not in email:
                held.append({**base, "reason": "no email on file"})
                continue
            base["email"] = email
            if not groups:
                held.append({**base, "reason": "pairings not saved for this event"})
                continue
            hit = seats.get(("c", cid)) or seats.get(("n", db._pair_key_name(full)))
            if not hit:
                held.append({**base, "reason": "not in a group on the saved sheet"})
                continue
            g, me = hit
            mates = [p for p in g.get("players") or [] if p is not me]
            group_block = ("<ul>" + "".join(f"<li>{_e(p.get('name'))}</li>" for p in mates
                                             if (p.get("name") or "").strip()) + "</ul>"
                           if any((p.get("name") or "").strip() for p in mates) else "")
            cart_block = ""
            pos = me.get("cart_pos") or 0
            if pos:
                pair = (1, 2) if pos in (1, 2) else (3, 4)
                partner = [p for p in mates if (p.get("cart_pos") or 0) in pair]
                if len(partner) == 1 and (partner[0].get("name") or "").strip():
                    cart_block = (f"<p><strong>Your cart partner:</strong> "
                                  f"{_e(partner[0]['name'])}</p>")
            games_block, _gwhy = _games_block(gctx, r)
            url = (links.get(str(g.get("holes") or "")) or {}).get(g.get("group_num"))
            scoring_block = ""
            if url:
                from email_parser.score_entry import short_score_url
                scoring_block = (f'<p><strong>Keep score on your phone:</strong> '
                                 f'<a href="{_e(short_score_url(url))}">open your group\'s scorecard</a> '
                                 f'(or scan the QR code on your cart sign).</p>')
            first = nm.get("first_name") or (full.split()[0] if full else "")
            vals_html = {
                "first_name": _e(first), "player_name": _e(full),
                "event_name": _e(ev_info.get("item_name")),
                "course": _e(ev_info.get("course")),
                "event_date": _e(_pretty_date(ev_info.get("event_date"))),
                "start_line": _e(g.get("start_line")),
                "group_label": _e(g.get("slot_label")),
                "group_block": group_block, "cart_block": cart_block,
                "games_block": games_block, "scoring_block": scoring_block,
                "manager_name": _e(manager.get("name")),
                "manager_phone": _e(manager.get("phone")),
            }
            subject = html_to_text(render_msg_template(tpl["subject"], vals_html))
            body = normalize_email_html(render_msg_template(tpl["html_body"], vals_html))
            text = html_to_text(body)
            why = _guard(subject, body, text, used, vals_html)
            msg = {**base, "subject": subject, "html": body, "text": text,
                   "start_line": g.get("start_line"), "group": g.get("slot_label"),
                   "games_shown": bool(games_block), "scoring_link": bool(scoring_block)}
            if why:
                held.append({**base, "reason": "; ".join(why)})
                continue
            messages.append(msg)
    finally:
        conn.close()

    return {
        "event": {"id": int(event_id), "name": ev_info.get("item_name"),
                  "date": ev_info.get("event_date"), "course": ev_info.get("course"),
                  "chapter": ev_info.get("chapter")},
        "template": TEMPLATE_NAME,
        "template_hash": appr["template_hash"],
        "approved": appr["approved"],
        "pairings_saved": bool(groups),
        "games_note": (None if gctx.get("ok") else
                       f"games block omitted for every player: {gctx.get('why')}"),
        "counts": {"roster": len(people), "ready": len(messages), "held": len(held)},
        "messages": messages,
        "held": held,
    }


def summarize(built: dict, samples: int = 1) -> dict:
    """The build as a bridge report: no bodies except `samples` texts."""
    if built.get("error"):
        return built
    out = {k: v for k, v in built.items() if k not in ("messages",)}
    out["ready"] = [{"customer_id": m["customer_id"], "name": m["name"],
                     "email": m["email"], "group": m["group"],
                     "start_line": m["start_line"], "games_shown": m["games_shown"]}
                    for m in built["messages"]]
    out["samples"] = [{"to": m["email"], "subject": m["subject"], "text": m["text"]}
                      for m in built["messages"][:samples]]
    return out


# ---------------------------------------------------------------------------
# Sends
# ---------------------------------------------------------------------------

def _creds():
    c = [os.getenv(k) for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID",
                                 "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS")]
    return c if all(c) else None


def _graph_send(creds, to, subject, html_body) -> bool:
    from email_parser import fetcher
    return fetcher.send_mail_graph(tenant_id=creds[0], client_id=creds[1],
                                   client_secret=creds[2], from_address=creds[3],
                                   to_address=to, subject=subject, html_body=html_body)


def send_event_day_preview(event_id: int, to_address=None, db_path=None) -> dict:
    """ONE combined preview (first few rendered messages + the held list +
    counts) to STAFF ONLY. A non-staff address is refused."""
    from email_parser import database as db
    from email_parser.recap_mail import staff_only, _addrs

    def gs(k):
        try:
            return db.get_app_setting(k, db_path=db_path)
        except Exception:
            return None

    to = _addrs(to_address) or [DEFAULT_PREVIEW_TO]
    bad = staff_only(to, gs)
    if bad:
        return {"error": f"the event-day preview goes to TGF staff only; refused {bad}"}
    built = build_event_day_emails(event_id, db_path=db_path)
    if built.get("error"):
        return built
    ev = built["event"]
    c = built["counts"]
    parts = [
        f"<p><strong>Event-day email PREVIEW</strong> for <strong>{_e(ev['name'])}</strong> "
        f"({_e(ev['date'])}, {_e(ev['course'])}). Nothing has been sent to any player.</p>",
        f"<p>Roster {c['roster']} · ready {c['ready']} · held {c['held']}. "
        f"Template hash <code>{_e(built['template_hash'])}</code> — "
        f"{'APPROVED' if built['approved'] else 'NOT approved: the member send is locked until app setting ' + APPROVAL_KEY + ' carries this hash'}.</p>",
    ]
    if built.get("games_note"):
        parts.append(f"<p><em>{_e(built['games_note'])}</em></p>")
    for m in built["messages"][:PREVIEW_SAMPLES]:
        parts.append('<hr style="border:0;border-top:2px solid #E87C3E">'
                     f"<p><strong>To:</strong> {_e(m['name'])} &lt;{_e(m['email'])}&gt;<br>"
                     f"<strong>Subject:</strong> {_e(m['subject'])}</p>" + m["html"])
    parts.append('<hr style="border:0;border-top:2px solid #E87C3E">')
    if built["held"]:
        parts.append("<p><strong>HELD — these players would get nothing:</strong></p><ul>"
                     + "".join(f"<li>{_e(h['name'])} (cid {_e(h.get('customer_id'))}): "
                               f"{_e(h['reason'])}</li>" for h in built["held"]) + "</ul>")
    else:
        parts.append("<p>No player is held.</p>")
    subject = f"PREVIEW — event-day email — {ev['name']}"
    html_body = "".join(parts)
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server", "counts": c}
    ok = _graph_send(creds, ",".join(to), subject, html_body)
    status = "sent" if ok else "failed"
    try:
        db.log_message({"event_name": "event-day-preview", "channel": "email",
                        "recipient_name": "staff preview",
                        "recipient_address": ",".join(to), "subject": subject,
                        "body_preview": f"event {event_id} hash {built['template_hash']}",
                        "status": status, "sent_by": "event_day_email"}, db_path=db_path)
    except Exception:
        logger.exception("event-day preview log failed (non-fatal)")
    return {"status": status, "to": to, "subject": subject, "counts": c,
            "template_hash": built["template_hash"], "approved": built["approved"],
            "held": built["held"]}


def send_event_day_emails(event_id: int, confirm: bool = False, db_path=None) -> dict:
    """The MEMBER send. Refuses unless the approval stamp matches the
    current template AND confirm is True. Never twice per event+customer."""
    from email_parser import database as db
    tpl = load_template(db_path)
    appr = approval_state(tpl, db_path)
    if not appr["approved"]:
        return {"refused": "template not approved: app setting "
                           f"{APPROVAL_KEY} must equal the current template hash",
                **appr}
    if confirm is not True:
        return {"refused": "confirm=True required for the member send", **appr}
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    built = build_event_day_emails(event_id, db_path=db_path)
    if built.get("error"):
        return built
    if built["template_hash"] != appr["template_hash"]:
        return {"refused": "template changed during the build"}

    sent, skipped, failed = [], [], []
    conn = db.get_connection(db_path)
    try:
        ensure_event_day_tables(conn)
        for m in built["messages"]:
            # Claim the row first: a second run (or a concurrent one) finds
            # it and skips. A FAILED send may be claimed again.
            row = conn.execute(
                "INSERT INTO event_day_email_sends "
                "(event_id, customer_id, email, template_hash, status) "
                "VALUES (?, ?, ?, ?, 'sending') "
                "ON CONFLICT(event_id, customer_id) DO UPDATE SET "
                "status = 'sending', email = excluded.email, "
                "template_hash = excluded.template_hash "
                "WHERE event_day_email_sends.status = 'failed' RETURNING id",
                (int(event_id), m["customer_id"], m["email"], built["template_hash"])).fetchone()
            conn.commit()
            if not row:
                skipped.append({"customer_id": m["customer_id"], "name": m["name"],
                                "why": "already sent for this event"})
                continue
            ok = False
            try:
                ok = _graph_send(creds, m["email"], m["subject"], m["html"])
            except Exception:
                logger.exception("event-day send failed for cid %s", m["customer_id"])
            conn.execute(
                "UPDATE event_day_email_sends SET status = ?, sent_at = datetime('now') "
                "WHERE id = ?", ("sent" if ok else "failed", row[0]))
            conn.commit()
            (sent if ok else failed).append({"customer_id": m["customer_id"],
                                             "name": m["name"], "email": m["email"]})
            try:
                db.log_message({"event_name": built["event"]["name"], "channel": "email",
                                "recipient_name": m["name"], "recipient_address": m["email"],
                                "subject": m["subject"], "body_preview": m["text"][:200],
                                "status": "sent" if ok else "failed",
                                "sent_by": "event_day_email"}, db_path=db_path)
            except Exception:
                pass
    finally:
        conn.close()
    return {"event": built["event"], "sent": sent, "skipped": skipped,
            "failed": failed, "held": built["held"],
            "counts": {**built["counts"], "sent": len(sent), "skipped": len(skipped),
                       "failed": len(failed)}}
