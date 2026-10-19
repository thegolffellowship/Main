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
OPTIONAL_VARS = {"cart_block", "games_block", "scoring_block",
                 "games_card", "scoring_button", "teesheet_button"}

# The games tab reader (the Events page's own GAMES tab, run headless).
# A module attribute so a test can hand in a fixture instead of Chromium.
def _read_games_tab(event_id: int) -> dict:
    from email_parser.page_probe import event_games_tab
    return event_games_tab(int(event_id))

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
    t = re.sub(r"(?i)</(li|ul|ol|tr|div|table)\s*>", "\n", t)
    t = re.sub(r"(?i)</td\s*>", " ", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = _html.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
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
# The A2 cards (Kerry 2026-10-12: "A looks the best to me. It would also be
# nice to show a current games breakdown on a card like the Group Card. The
# more graphic (as long as it works on all browsers) the better." then
# "Perfect for now"). Email-safe on purpose: tables, bgcolor and inline
# styles only. No images, SVG, flexbox or <style> blocks, so Gmail,
# Outlook, Apple Mail and phone clients all draw it (Outlook desktop just
# squares the corners). The STRUCTURE is code; the WORDS around it are the
# template, so Kerry can still edit the greeting and sign-off in the UI.
# ---------------------------------------------------------------------------

INK, MUTED, LINE, ORANGE = "#1B1B1B", "#6B7280", "#E5E7EB", "#E87C3E"
GREEN_BG, GREEN_INK = "#bbf7d0", "#15803D"     # the bought-in token
SECTION_COLORS = {"INCLUDED": INK, "NET": ORANGE, "GROSS": "#8FA8B8"}
_EYEBROW = "font:bold 11px Arial,sans-serif;letter-spacing:2px;"
_CODE_RE = re.compile(r"^[a-z]+\d+(\.\d+)?\s+", re.I)
_MONEY_RE = re.compile(r"\$[\d,]+(?:\.\d\d)?")
_T = 'role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'


def event_short_name(item_name: str | None, course: str | None = None) -> str:
    """"s9.27 The Quarry" -> "The Quarry". The internal code never reaches
    a member; the course is the fallback."""
    n = _CODE_RE.sub("", (item_name or "").split("|")[0]).strip()
    return n or (course or "").strip()


def _weekday(d: str | None) -> str:
    try:
        return datetime.strptime((d or "")[:10], "%Y-%m-%d").strftime("%A")
    except ValueError:
        return ""


def _is_shotgun(ev: dict, holes) -> bool:
    key = "start_type_18" if str(holes or "") == "18" else "start_type"
    return (ev.get(key) or ev.get("start_type") or "") == "Shotgun"


def _initials(name: str) -> str:
    parts = [w for w in re.split(r"\s+", (name or "").strip()) if w]
    return ((parts[0][0] if parts else "") + (parts[-1][0] if len(parts) > 1 else "")).upper()


def _pill(text: str, bg: str, ink: str) -> str:
    return (f'<span style="background:{bg};color:{ink};font:bold 11px Arial,sans-serif;'
            f'letter-spacing:1px;padding:3px 8px;border-radius:10px;white-space:nowrap;">{_e(text)}</span>')


def _cart_of(p: dict) -> str:
    pos = p.get("cart_pos") or 0
    return "A" if pos in (1, 2) else ("B" if pos in (3, 4) else "")


def spot_card(g: dict, me: dict, *, start_headline: str, start_sub: str,
              tee: dict | None, format_line: str, card_html: str = "",
              photos: dict | None = None, base_url: str = "") -> str:
    """The orange START header, the group with initials and carts, then
    tees and format. Blinds are not people and are never listed."""
    my_cart = _cart_of(me)
    rows = []
    for p in sorted(g.get("players") or [], key=lambda x: x.get("cart_pos") or 0):
        nm = (p.get("name") or "").strip()
        if not nm:
            continue
        mine = p is me
        cart = _cart_of(p)
        if mine:
            note = "you" + (f" &middot; Cart {cart}" if cart else "")
        elif cart and cart == my_cart:
            note = f"your cart &middot; Cart {cart}"
        else:
            note = f"Cart {cart}" if cart else ""
        bg, ink = (INK, "#ffffff") if mine else ("#D3DDE4", INK)
        # Kerry 10/19: "put player photos with player spotlight links into
        # the player emails so they can see who they're playing with, if we
        # have photos. Otherwise it's the initials."
        cid = p.get("customer_id")
        ver = (photos or {}).get(str(cid)) if cid else None
        # Larger faces, side by side (Kerry 10/19: "photos are larger? I
        # can't see them very well to distinguish features").
        if ver and base_url:
            face = (f'<img src="{_e(base_url)}/member/photo/h/{int(cid)}.jpg?v={int(ver)}" width="72" height="72" '
                    f'alt="{_e(_initials(nm))}" style="display:block;margin:0 auto;width:72px;height:72px;'
                    f'border-radius:36px;object-fit:cover;border:{"3px solid " + ORANGE if mine else "0"};">')
        else:
            face = (f'<div style="width:72px;height:72px;margin:0 auto;border-radius:36px;background:{bg};color:{ink};'
                    f'text-align:center;font:bold 24px Arial,sans-serif;line-height:72px;">{_e(_initials(nm))}</div>')
        link = f"{base_url}/member/spotlight?player={int(cid)}" if (cid and base_url) else ""
        if link:
            face = f'<a href="{_e(link)}" style="text-decoration:none;">{face}</a>'
        label = f"<b>{_e(nm)}</b>" if mine else _e(nm)
        if link:
            label = f'<a href="{_e(link)}" style="color:{INK};text-decoration:none;">{label}</a>'
        rows.append(
            f'<td width="25%" align="center" style="padding:0 4px 10px;vertical-align:top;text-align:center;">'
            f'{face}<div style="font-size:14px;line-height:1.3;padding-top:6px;">{label}</div>'
            + (f'<div style="font-size:12px;color:{MUTED};">{note}</div>' if note else "")
            + "</td>")
    foot = []
    if tee and tee.get("name"):
        sw = (tee.get("color") or "").strip()
        dot = ""
        if sw:
            white = sw.lower() in ("#ffffff", "#fff")
            dot = (f'<span style="display:inline-block;width:12px;height:12px;border-radius:6px;'
                   f'background:{"#ffffff" if white or tee.get("ring") else sw};'
                   f'border:2px solid {"#9CA3AF" if white else sw};vertical-align:middle;"></span> ')
        foot.append(f'<td width="50%" style="font-size:14px;vertical-align:top;">'
                    f'<span style="{_EYEBROW}color:{MUTED};">TEES</span><br>{dot}<b>{_e(tee["name"])}</b></td>')
    if format_line:
        foot.append(f'<td style="font-size:14px;vertical-align:top;">'
                    f'<span style="{_EYEBROW}color:{MUTED};">FORMAT</span><br><b>{_e(format_line)}</b></td>')
    return (
        f'<table {_T} style="border:1px solid {LINE};border-radius:8px;margin:0 0 18px;">'
        f'<tr><td bgcolor="{ORANGE}" style="background:{ORANGE};border-radius:8px 8px 0 0;padding:14px 16px;color:#ffffff;">'
        f'<div style="{_EYEBROW}">YOUR START</div>'
        f'<div style="font:bold 28px/1.15 Georgia,serif;">{_e(start_headline)}</div>'
        f'<div style="font-size:14px;">{_e(start_sub)}</div></td></tr>'
        f'<tr><td style="padding:12px 16px 4px;">'
        f'<div style="{_EYEBROW}color:{MUTED};padding-bottom:8px;">YOUR GROUP</div>'
        f'<table {_T}><tr>{"".join(rows)}</tr></table></td></tr>'
        + (f'<tr><td style="border-top:1px solid {LINE};padding:10px 16px;"><table {_T}><tr>'
           f'{"".join(foot)}</tr></table></td></tr>' if foot else "")
        + (f'<tr><td style="border-top:1px solid {LINE};padding:12px 16px 14px;">{card_html}</td></tr>'
           if card_html else "")
        + "</table>")


def _money(s) -> float:
    m = _MONEY_RE.search(str(s or ""))
    return float(m.group(0)[1:].replace(",", "")) if m else 0.0


def _game_label(name: str) -> str:
    n = re.sub(r"[^\w\s#.&'/+-]", "", name or "").strip()
    n = re.sub(r"^CTP\b", "Closest to the Pin", n)
    n = re.sub(r"^Skins Gross$", "Skins", n)
    n = re.sub(r"^Skins 1/2 Net\b.*$", "Skins \u00bd Net", n)
    n = re.sub(r"^(TEAM|CART)\b", lambda m: m.group(1).title(), n)
    return re.sub(r"^Ind\.\s*", "Individual ", n)


def games_view(tab: dict | None) -> dict:
    """The GAMES tab (page_probe) shaped for the card, once per event.
    {'ok': False, 'why': ...} when it cannot be shown faithfully."""
    if not tab or tab.get("error"):
        return {"ok": False, "why": "games tab unreadable: " + str((tab or {}).get("error") or "no data")}
    if tab.get("buckets") or tab.get("empty"):
        return {"ok": False, "why": "bucket / empty games tab"}
    linked = ", ".join(
        f"{l.get('chapter')} at {event_short_name(l.get('event_name'), l.get('course'))}"
        for l in ((tab.get("mvp_link") or {}).get("linked") or []) if l.get("chapter"))
    sections = []
    for sec in tab.get("sections") or []:
        title = re.sub(r"\s*\(.*\)\s*$", "", sec.get("section") or "").strip().upper()
        key = title.split()[0] if title else ""
        if key == "INCLUDED":
            title = "INCLUDED"
        rows, subs = [], []
        for r in sec.get("rows") or []:
            if r.get("disabled"):
                continue
            if r.get("sub"):
                subs.append(r)
                if rows and (r.get("game") or "").startswith("Per skin:"):
                    pays = {k: "$" + v for k, v in re.findall(r"(\d+)=\$(\d+(?:\.\d+)?)", r["game"])}
                    if pays.get("1"):
                        rows[-1]["note"] = (f"one skin pays {pays['1']}"
                                            + (f", two pay {pays['2']} each" if pays.get("2") else ""))
                continue
            if not r.get("pot"):
                continue
            note = ""
            fl = str(r.get("flights") or "").strip()
            if fl.isdigit() and int(fl) > 1:
                note = f"{fl} flights"
            if "MVP" in (r.get("game") or "").upper() and "TGF" in (r.get("game") or "").upper() and linked:
                note = f"with {linked}"
            rows.append({"game": _game_label(r.get("game")), "pot": r.get("pot"), "note": note})
        # A flighted game paying only 1st in every flight: say what a winner takes.
        for row in rows:
            if row["note"].endswith("flights"):
                firsts = {s.get("1st") for s in subs if s.get("1st") and s.get("1st") != "—"}
                seconds = [s for s in subs if s.get("2nd") and s.get("2nd") != "—"]
                if len(firsts) == 1 and not seconds:
                    row["note"] += f", {next(iter(firsts))} to each flight winner"
        pot = (sec.get("subtotal") or {}).get("pot") or (rows[0]["pot"] if len(rows) == 1 else "")
        if rows:
            sections.append({"key": key, "title": title, "pot": pot,
                             "count": re.search(r"\((\d+)", sec.get("section") or "").group(1)
                             if re.search(r"\((\d+)", sec.get("section") or "") else "",
                             "rows": rows})
    total = (tab.get("total") or {}).get("pot") or ""
    if not sections or _money(total) <= 0:
        return {"ok": False, "why": "no games with a pot on this event"}
    hio = ""
    for line in tab.get("hole_in_one") or []:
        m = re.search(r"Pot:\s*(\$[\d,.]+)", line or "")
        if m:
            hio = m.group(1)
    buyers = tab.get("buyers") or {}
    ids = {k: {int(w["customer_id"]) for w in (buyers.get(k) or []) if w.get("customer_id")}
           for k in ("players", "net", "gross")}
    c = tab.get("counts") or {}
    return {"ok": True, "total": total, "counts": c, "sections": sections, "hio": hio,
            "ids": ids, "team_type": tab.get("team_type") or ""}


def games_card(view: dict, cid: int | None, rsvp_only: bool, as_of: str, day: str) -> str:
    """The Games card: total in play, counts, a split bar, one block per
    section with this player's YOU'RE IN / NOT BOUGHT pill, the HIO pot."""
    if not view.get("ok"):
        return ""
    c = view["counts"]
    chips = [(c.get("players"), "PLAYERS", "#F3F4F6", INK),
             (c.get("net"), "IN NET", "#FEF0E7", "#D06B2E"),
             (c.get("gross"), "IN GROSS", "#E8EEF2", "#4B6B80")]
    chips = [x for x in chips if x[0]]
    chip_html = "".join(
        f'<td width="{100 // len(chips)}%" align="center" style="padding:0 3px;">'
        f'<div style="background:{bg};border-radius:8px;padding:8px 4px;">'
        f'<div style="font:bold 22px Georgia,serif;color:{ink};">{_e(n)}</div>'
        f'<div style="font:bold 10px Arial,sans-serif;letter-spacing:1px;color:{MUTED};">{lab}</div></div></td>'
        for n, lab, bg, ink in chips)
    pots = [(s, _money(s["pot"])) for s in view["sections"]]
    tot = sum(v for _, v in pots) or 1.0
    widths = [max(1, round(100 * v / tot)) for _, v in pots]
    widths[-1] = max(1, 100 - sum(widths[:-1]))
    bar = "".join(
        f'<td width="{w}%" height="12" bgcolor="{SECTION_COLORS.get(s["key"], MUTED)}" '
        f'style="background:{SECTION_COLORS.get(s["key"], MUTED)};font-size:0;line-height:0;">&nbsp;</td>'
        for (s, _), w in zip(pots, widths))
    legend = "".join(
        f'<td width="{w}%" style="padding-top:4px;">{_e(s["title"].replace(" GAMES", "").title())} {_e(s["pot"])}</td>'
        for (s, _), w in zip(pots, widths))
    blocks = []
    for s in view["sections"]:
        col = SECTION_COLORS.get(s["key"], MUTED)
        who = "everyone" if s["key"] == "INCLUDED" else (f'{s["count"]} players' if s["count"] else "")
        pill = ""
        if cid and not rsvp_only:
            if s["key"] == "INCLUDED":
                pill = _pill("YOU'RE IN", GREEN_BG, GREEN_INK) if cid in view["ids"]["players"] else ""
            elif s["key"] in ("NET", "GROSS"):
                inn = cid in view["ids"][s["key"].lower()]
                pill = (_pill("YOU'RE IN", GREEN_BG, GREEN_INK) if inn
                        else _pill("NOT BOUGHT", "#F3F4F6", MUTED))
        lines = "".join(
            f'<tr><td style="padding:3px 0;">{_e(r["game"])}'
            + (f' <span style="color:{MUTED};font-size:13px;">{_e(r["note"])}</span>' if r["note"] else "")
            + f'</td><td align="right" style="padding:3px 0;white-space:nowrap;"><b>{_e(r["pot"])}</b></td></tr>'
            for r in s["rows"])
        blocks.append(
            f'<tr><td style="padding:12px 16px 0;"><table {_T} style="border-left:4px solid {col};">'
            f'<tr><td style="padding:2px 0 6px 10px;"><b style="font:bold 13px Arial,sans-serif;letter-spacing:1px;">'
            f'{_e(s["title"])}</b> <span style="font-size:13px;color:{MUTED};">'
            + " &middot; ".join(x for x in (_e(who), _e(s["pot"])) if x)
            + f'</span></td><td align="right" style="padding:2px 0 6px;">{pill}</td></tr>'
            f'<tr><td colspan="2" style="padding:0 0 4px 10px;"><table {_T} style="font-size:14px;">{lines}</table>'
            f'</td></tr></table></td></tr>')
    hio = (f'<tr><td style="padding:14px 16px 16px;"><table {_T}><tr><td bgcolor="#FFF7ED" '
           f'style="background:#FFF7ED;border:1px dashed {ORANGE};border-radius:8px;padding:10px 12px;font-size:14px;">'
           f'&#9971; <b>Hole-in-One Pot: {_e(view.get("hio_total") or view["hio"])}</b>'
           + (f' <span style="color:{MUTED};">{_e(day)}\'s field adds {_e(view["hio"])}</span>'
              if view.get("hio_total") and view.get("hio") else
              f' <span style="color:{MUTED};">and growing until someone cashes it</span>')
           + '</td></tr></table></td></tr>'
           if (view.get("hio") or view.get("hio_total")) else '<tr><td style="padding:0 0 12px;"></td></tr>')
    return (
        f'<table {_T} style="border:1px solid {LINE};border-radius:8px;margin:0 0 18px;">'
        f'<tr><td bgcolor="{INK}" style="background:{INK};border-radius:8px 8px 0 0;padding:14px 16px;color:#ffffff;">'
        f'<div style="{_EYEBROW}color:{ORANGE};">{_e(day.upper())}\'S GAMES</div>'
        f'<div style="font:bold 28px/1.15 Georgia,serif;">{_e(view["total"])} in play</div>'
        f'<div style="font-size:13px;color:#D1D5DB;">As of {_e(as_of)}. Pots move as players add games.</div></td></tr>'
        f'<tr><td style="padding:14px 13px 6px;"><table {_T}><tr>{chip_html}</tr></table></td></tr>'
        f'<tr><td style="padding:8px 16px 4px;"><table {_T}><tr>{bar}</tr></table>'
        f'<table {_T} style="font-size:12px;color:{MUTED};"><tr>{legend}</tr></table></td></tr>'
        + "".join(blocks) + hio + "</table>")


def scoring_button(url: str) -> str:
    return (f'<table {_T} style="margin:0 0 16px;"><tr><td align="center" bgcolor="{ORANGE}" '
            f'style="background:{ORANGE};border-radius:999px;padding:12px;">'
            f'<a href="{_e(url)}" style="color:#ffffff;text-decoration:none;font:bold 15px Arial,sans-serif;'
            f'display:block;">Keep score on your phone</a></td></tr></table>')


def _dots(n) -> str:
    n = int(n or 0)
    return ("&#9679;" * n) if n > 0 else "&nbsp;"


def card_strip(row: dict, grid: dict, net: dict, dump: dict | None, tee_name: str | None) -> str:
    """YOUR CARD (Kerry 10/13: "a view of their scorecard to see where their
    pops are going ... how their PHs are calculated for each game"): the
    holes played with par and the player's pops for Individual Net and for
    the team game, plus the handicap chain in one line. Every value is the
    PRINTED SCORECARD's (scorecards.build_scorecards: ruled_dots on the
    player's own tee), so the email and the paper card cannot disagree."""
    holes = list(grid.get("holes") or [])
    if not holes or not row.get("si_by_hole"):
        return ""
    par = grid.get("par") or {}
    ph_d, net_d = row.get("ph_dots") or {}, row.get("net_dots") or {}
    net_short = "CART" if (net or {}).get("unit") == "cart" else "TEAM"
    cell = 'align="center" style="padding:3px 0;font-size:12px;border-top:1px solid ' + LINE + ';"'
    lab = f'style="padding:3px 6px 3px 0;font:bold 10px Arial,sans-serif;letter-spacing:1px;color:{MUTED};border-top:1px solid {LINE};white-space:nowrap;"'
    head = "".join(f'<td align="center" style="padding:3px 0;font:bold 12px Arial,sans-serif;color:#ffffff;" bgcolor="{INK}">{h}</td>' for h in holes)
    pars = "".join(f"<td {cell}>{par.get(h, '')}</td>" for h in holes)
    ph_row = "".join(f'<td {cell}><span style="color:{ORANGE};">{_dots(ph_d.get(h))}</span></td>' for h in holes)
    net_row = "".join(f'<td {cell}><span style="color:{INK};">{_dots(net_d.get(h))}</span></td>' for h in holes)
    grid_html = (
        f'<table {_T} style="border:1px solid {LINE};border-radius:6px;">'
        f'<tr><td bgcolor="{INK}" style="padding:3px 6px;font:bold 10px Arial,sans-serif;letter-spacing:1px;color:#ffffff;">HOLE</td>{head}</tr>'
        f'<tr><td {lab}>PAR</td>{pars}</tr>'
        f'<tr><td {lab}>NET</td>{ph_row}</tr>'
        f'<tr><td {lab}>{net_short}</td>{net_row}</tr></table>')
    idx = (dump or {}).get("index")
    bits = []
    if row.get("ph"):
        src = (f"Index {idx:.1f}" if isinstance(idx, (int, float)) else "")
        on = f" on the {tee_name}" if tee_name else ""
        bits.append((f"{src}{on} gives you " if src else "")
                    + f"a Playing Handicap of <b>{_e(row['ph'])}</b> for Individual Net.")
    if row.get("net") and net:
        pct = net.get("pct")
        how = f"{pct}% of your handicap" if pct else "its own allowance"
        if net.get("off_low"):
            how += ", off the lowest in your " + ("cart" if net_short == "CART" else "group")
        bits.append(f"{_e(net.get('name') or 'Team Net')} uses {how}: <b>{_e(row['net'])}</b>.")
    if net and net.get("par3_suppressed"):
        bits.append(f"No {net_short.lower()} pops on par 3s.")
    return (f'<div style="{_EYEBROW}color:{MUTED};padding-bottom:8px;">YOUR CARD '
            f'<span style="letter-spacing:0;font-weight:normal;">&#9679; = a pop on that hole</span></div>'
            + grid_html
            + (f'<div style="font-size:13px;color:#4B5563;padding-top:8px;line-height:1.45;">{" ".join(bits)}</div>'
               if bits else ""))


def teesheet_button(url: str) -> str:
    return (f'<table {_T} style="margin:0 0 16px;"><tr><td align="center" '
            f'style="border:2px solid {INK};border-radius:999px;padding:10px;">'
            f'<a href="{_e(url)}" style="color:{INK};text-decoration:none;font:bold 15px Arial,sans-serif;'
            f'display:block;">See the full tee sheet</a></td></tr></table>')


def frame(inner: str, chapter_label: str, title: str) -> str:
    """The page around the message: grey ground, dark masthead, white panel."""
    return (
        f'<div style="background:#F8F8F8;padding:16px 8px;font-family:\'Helvetica Neue\',Helvetica,'
        f'Arial,sans-serif;color:{INK};"><table {_T} style="max-width:560px;margin:0 auto;">'
        f'<tr><td bgcolor="{INK}" style="background:{INK};border-radius:10px 10px 0 0;padding:16px 18px;">'
        f'<div style="font:bold 12px Georgia,serif;letter-spacing:2px;color:{ORANGE};">{_e(chapter_label)}</div>'
        f'<div style="font:bold 22px Georgia,serif;color:#ffffff;padding-top:4px;">{_e(title)}</div></td></tr>'
        f'<tr><td bgcolor="#ffffff" style="background:#ffffff;border:1px solid {LINE};border-top:0;'
        f'border-radius:0 0 10px 10px;padding:18px;font-size:16px;line-height:1.5;">{inner}</td></tr>'
        f'</table></div>')


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_event_day_emails(event_id: int, db_path=None, games_tab: dict | None = None) -> dict:
    """Render every roster player's message (nothing is sent).

    Returns {event, template_hash, approved, counts, messages, held,
    games_note}. `messages` are sendable; `held` carries a reason each.
    `games_tab` (tests) stands in for the headless GAMES tab read."""
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
        tpl_text = (tpl or {}).get("subject", "") + (tpl or {}).get("html_body", "")
        # The A2 Games card reads the GAMES tab once for the whole event.
        # Unreadable -> the card is left out for everyone and the preview
        # says why; it never blocks the start time from going out.
        gview = {"ok": False, "why": "template has no games card"}
        if "{games_card}" in tpl_text:
            if db.event_games_off(ev):
                gview = {"ok": False, "why": "no games at this event"}
            elif not gctx.get("ok") and gctx.get("why") in ("day-games (championship) event", "package event"):
                gview = {"ok": False, "why": gctx["why"]}
            else:
                try:
                    gview = games_view(games_tab if games_tab is not None
                                       else _read_games_tab(int(event_id)))
                except Exception as exc:
                    logger.exception("event-day email: games tab read failed (non-fatal)")
                    gview = {"ok": False, "why": f"games tab unreadable: {exc}"}
        if gview.get("ok"):
            try:
                pot = float((db.get_hio_pot(db_path=db_path) or {}).get("pot") or 0)
                if pot > 0:
                    gview["hio_total"] = f"${pot:,.0f}" if pot == int(pot) else f"${pot:,.2f}"
            except Exception:
                logger.exception("event-day email: HIO pot unreadable (non-fatal)")
        # YOUR CARD: the printed scorecard's own numbers, read once. qr=off
        # so nothing is seeded; a gap leaves that player's strip out.
        sc_rows, sc_dump, sc_grids, sc_net = {}, {}, {}, {}
        if "{spot_card}" in tpl_text:
            try:
                from email_parser.scorecards import build_scorecards
                sc = build_scorecards(int(event_id), qr="off", allow_gaps=True, db_path=db_path) or {}
                sc_grids, sc_net = sc.get("grids") or {}, sc.get("net") or {}
                for c in sc.get("cards") or []:
                    for rr in c.get("rows") or []:
                        if rr.get("customer_id"):
                            sc_rows[int(rr["customer_id"])] = (rr, c.get("holes"))
                for d in sc.get("dump") or []:
                    if d.get("customer_id"):
                        sc_dump[int(d["customer_id"])] = d
            except Exception:
                logger.exception("event-day email: scorecard read failed (non-fatal)")
        # player photos + Spotlight links in YOUR GROUP (Kerry 10/19)
        try:
            from email_parser.player_photos import photo_index as _pidx
            from email_parser.score_entry import _base_url as _bu
            group_photos = _pidx(db_path).get("h") or {}
            group_base = _bu()
        except Exception:
            logger.exception("event-day email: photo index unavailable (initials only)")
            group_photos, group_base = {}, ""
        scoring_note = None
        if "{scoring_button}" in tpl_text and not links:
            scoring_note = ("Live Scoring is not on for this event, so no player gets a "
                            "Keep score button. Turn it on (Live Scoring page) before sending.")
        try:
            from email_parser.score_entry import _base_url
            teesheet_url = f"{_base_url()}/member/teesheet/{int(event_id)}"
        except Exception:
            teesheet_url = ""
        tees = {str(t.get("band")): {"name": t.get("tee_name"), "color": t.get("color"),
                                     "ring": bool(t.get("ring") or t.get("ladies"))}
                for t in pack.get("tee_legend") or [] if t.get("band") is not None}
        try:
            from email_parser.timezone_utils import now_central
            as_of = now_central().strftime("%A %-I:%M %p")
        except Exception:
            as_of = datetime.now().strftime("%A %-I:%M %p")
        short = event_short_name(ev_info.get("item_name"), ev_info.get("course"))
        day = _weekday(ev_info.get("event_date"))
        title = f"{day} at {short}" if day and short else short
        chap = (ev_info.get("chapter") or "").strip()
        chapter_label = ("THE GOLF FELLOWSHIP" + (f" \u00b7 {chap.upper()}"
                         if chap and chap.upper() != "TGF" else ""))
        try:
            date_short = datetime.strptime((ev_info.get("event_date") or "")[:10],
                                           "%Y-%m-%d").strftime("%A, %B %-d")
        except ValueError:
            date_short = ""

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
            from email_parser.score_entry import short_score_url
            url = (links.get(str(g.get("holes") or "")) or {}).get(g.get("group_num"))
            scoring_block = ""
            if url:
                scoring_block = (f'<p><strong>Keep score on your phone:</strong> '
                                 f'<a href="{_e(short_score_url(url))}">open your group\'s scorecard</a> '
                                 f'(or scan the QR code on your cart sign).</p>')
            # A2 cards (only rendered when the template asks for them).
            holes = str(g.get("holes") or pack.get("holes_key") or "")
            shot = _is_shotgun(ev, holes)
            sl = (g.get("start_line") or "").strip()
            start_headline = sl.replace(" | ", " \u00b7 ")
            start_subject = (f"{sl.replace(' | ', ', ')} shotgun" if shot
                             else f"{sl.split(' | ')[0]} tee time") if sl else ""
            start_sub = " \u00b7 ".join(x for x in (
                "Shotgun" if shot else "Tee time", date_short, ev_info.get("course") or "") if x)
            team = (gview.get("team_type") or "").replace("TEAM", "Team").replace("CART", "Cart")
            format_line = " \u00b7 ".join(x for x in (f"{holes} holes" if holes else "", team) if x)
            tee = tees.get(str(me.get("tee_choice"))) if me.get("tee_choice") else None
            card_html = ""
            hit_sc = sc_rows.get(cid)
            if hit_sc:
                rr, hk = hit_sc
                grid = sc_grids.get(hk) or sc_grids.get(str(hk)) or {}
                try:
                    card_html = card_strip(rr, grid, sc_net, sc_dump.get(cid),
                                           (tee or {}).get("name"))
                except Exception:
                    logger.exception("event-day email: card strip failed for cid %s", cid)
            spot = spot_card(g, me, start_headline=start_headline, start_sub=start_sub,
                             tee=tee, format_line=format_line, card_html=card_html,
                             photos=group_photos, base_url=group_base) if sl else ""
            tbutton = (teesheet_button(f"{teesheet_url}#g{_e(g.get('group_num'))}")
                       if teesheet_url and "{teesheet_button}" in tpl_text else "")
            gcard = games_card(gview, cid, bool(r.get("rsvp_only")), as_of, day) if gview.get("ok") else ""
            sbutton = scoring_button(short_score_url(url)) if url else ""
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
                "event_title": _e(title), "start_subject": _e(start_subject),
                "spot_card": spot, "games_card": gcard, "scoring_button": sbutton,
                "teesheet_button": tbutton,
            }
            subject = html_to_text(render_msg_template(tpl["subject"], vals_html))
            body = normalize_email_html(render_msg_template(tpl["html_body"], vals_html))
            text = html_to_text(body)
            if "{spot_card}" in tpl["html_body"]:
                body = frame(body, chapter_label, title)
            why = _guard(subject, body, text, used, vals_html)
            msg = {**base, "subject": subject, "html": body, "text": text,
                   "start_line": g.get("start_line"), "group": g.get("slot_label"),
                   "games_shown": bool(gcard or games_block),
                   "scoring_link": bool(scoring_block or sbutton)}
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
        "games_note": (
            (None if gview.get("ok") else f"games card omitted for every player: {gview.get('why')}")
            if "{games_card}" in tpl_text else
            (None if gctx.get("ok") else f"games block omitted for every player: {gctx.get('why')}")),
        "scoring_note": scoring_note,
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


def _ensure_scoring(event_id: int, db_path=None) -> None:
    """Kerry 10/13: Live Scoring is on "definitely prior to these emails
    being sent out". Before a preview or a send is built, switch the event on
    and seed its rounds so every message carries its Keep score button."""
    try:
        from email_parser.live_scoring_default import ensure_live_scoring
        ensure_live_scoring(int(event_id), db_path=db_path)
    except Exception:
        logger.exception("event-day email: could not switch Live Scoring on (non-fatal)")


def send_event_day_preview(event_id: int, to_address=None, db_path=None, only=None) -> dict:
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
    _ensure_scoring(event_id, db_path)
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
    for k in ("games_note", "scoring_note"):
        if built.get(k):
            parts.append(f"<p><em>{_e(built[k])}</em></p>")
    # `only` (customer_ids): the preview shows exactly those players' messages,
    # all of them (Kerry 10/8: "send me an email for me and my group").
    picked = ([m for m in built["messages"] if m["customer_id"] in set(only)] if only
              else built["messages"][:PREVIEW_SAMPLES])
    for m in picked:
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


def send_event_day_test(event_id: int, customer_id: int, to_address: str, db_path=None) -> dict:
    """ONE player's ACTUAL message (Kerry 10/13: "The preview looks fine but
    it did before too because it was in a container. Can you resend my
    actual player email?"): the exact subject and body that player gets, no
    preview wrapper, to ONE staff address (recap_mail.staff_only). Not a
    member send: no event_day_email_sends row, so the player's own send is
    untouched. Logged to message_log as a test."""
    from email_parser import database as db
    from email_parser.recap_mail import staff_only, _addrs

    def gs(k):
        try:
            return db.get_app_setting(k, db_path=db_path)
        except Exception:
            return None

    to = _addrs(to_address)
    if len(to) != 1:
        return {"error": "one staff address, please"}
    bad = staff_only(to, gs)
    if bad:
        return {"error": f"a test goes to TGF staff only; refused {bad}"}
    _ensure_scoring(event_id, db_path)
    built = build_event_day_emails(event_id, db_path=db_path)
    if built.get("error"):
        return built
    m = next((x for x in built["messages"] if x["customer_id"] == int(customer_id)), None)
    if not m:
        held = next((h for h in built["held"] if h.get("customer_id") == int(customer_id)), None)
        return {"error": f"no ready message for customer {customer_id}"
                         + (f" (held: {held['reason']})" if held else "")}
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    ok = _graph_send(creds, to[0], m["subject"], m["html"])
    try:
        db.log_message({"event_name": "event-day-test", "channel": "email",
                        "recipient_name": f"test of {m['name']}", "recipient_address": to[0],
                        "subject": m["subject"], "body_preview": f"event {event_id} cid {customer_id}",
                        "status": "sent" if ok else "failed", "sent_by": "event_day_email"},
                       db_path=db_path)
    except Exception:
        pass
    return {"status": "sent" if ok else "failed", "to": to[0], "subject": m["subject"],
            "player": m["name"]}


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
    _ensure_scoring(event_id, db_path)
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


# ---------------------------------------------------------------------------
# Re-issue after a start change (Kerry 2026-10-13, the Quarry: "Re-issue to
# players", then in the Customer Communications session "Approved to send
# yourself" and "Send it - GO")
# ---------------------------------------------------------------------------

REISSUE_PREFIX = "UPDATED START: "
_PANEL_OPEN = 'padding:18px;font-size:16px;line-height:1.5;">'


def reissue_banner(start_line: str) -> str:
    """The orange notice at the top of a re-issued message."""
    st = _e((start_line or "").replace(" | ", " · "))
    return (f'<table {_T} style="margin:0 0 14px;"><tr><td bgcolor="#FFF7ED" '
            f'style="background:#FFF7ED;border:2px solid {ORANGE};border-radius:8px;padding:12px 14px;">'
            f'<div style="font:bold 13px Georgia,serif;letter-spacing:1px;color:{ORANGE};">UPDATED START</div>'
            f'<div style="padding-top:4px;color:{INK};">Your starting hole has changed. '
            f'You now start on <strong>{st}</strong>. This replaces the earlier email. '
            f'Your group and cart are the same.</div></td></tr></table>')


def with_banner(html_body: str, banner: str) -> str:
    """Put the notice at the top of the white panel (or first, unframed)."""
    i = html_body.find(_PANEL_OPEN)
    if i < 0:
        return banner + html_body
    i += len(_PANEL_OPEN)
    return html_body[:i] + banner + html_body[i:]


def reissue_key(event_id: int, messages: list) -> str:
    """One key per sheet state: the start line of every ready player."""
    sig = "|".join(sorted(f"{m['customer_id']}:{m.get('start_line') or ''}" for m in messages))
    return f"event_day_reissue:{int(event_id)}:{hashlib.sha256(sig.encode()).hexdigest()[:12]}"


def send_event_day_reissue(event_id: int, kerry_ok_post, confirm: bool = False,
                           db_path=None) -> dict:
    """RE-ISSUE the event-day email after the start holes change: every ready
    player gets the same approved message with "UPDATED START: " before the
    subject and an orange notice at the top. The template hash must still
    match Kerry's stamp; the cited mailbox post must carry Kerry's word
    (customer_query._kerry_ok, unchanged); confirm=True sends, anything else
    is a dry run. Once per player per sheet state (app setting
    reissue_key(...) holds the customer_ids sent), so a repeat run skips them
    and a later change can be re-issued again. event_day_email_sends is not
    touched; every message is logged to message_log."""
    import json as _json
    from email_parser import database as db
    from email_parser.customer_query import _kerry_ok
    tpl = load_template(db_path)
    appr = approval_state(tpl, db_path)
    if not appr["approved"]:
        return {"refused": "template not approved: app setting "
                           f"{APPROVAL_KEY} must equal the current template hash", **appr}
    conn = db.get_connection(db_path)
    try:
        ok, why = _kerry_ok(conn, kerry_ok_post)
    finally:
        conn.close()
    if not ok:
        return {"refused": f"rule 3b: {why}"}
    _ensure_scoring(event_id, db_path)
    built = build_event_day_emails(event_id, db_path=db_path)
    if built.get("error"):
        return built
    if built["template_hash"] != appr["template_hash"]:
        return {"refused": "template changed during the build"}
    key = reissue_key(event_id, built["messages"])
    try:
        done = set(_json.loads(db.get_app_setting(key, db_path=db_path) or "[]"))
    except Exception:
        done = set()
    todo = [m for m in built["messages"] if m["customer_id"] not in done]
    out = {"event": built["event"], "authority": why, "key": key, "held": built["held"],
           "already_reissued": sorted(done),
           "counts": {**built["counts"], "to_send": len(todo)}}
    if confirm is not True:
        return {**out, "dry_run": True,
                "plan": [{"customer_id": m["customer_id"], "name": m["name"],
                          "email": m["email"], "start_line": m.get("start_line")} for m in todo],
                "sample_subject": (REISSUE_PREFIX + todo[0]["subject"]) if todo else None}
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    sent, failed = [], []
    for m in todo:
        subject = REISSUE_PREFIX + m["subject"]
        html = with_banner(m["html"], reissue_banner(m.get("start_line")))
        good = False
        try:
            good = _graph_send(creds, m["email"], subject, html)
        except Exception:
            logger.exception("event-day re-issue failed for cid %s", m["customer_id"])
        row = {"customer_id": m["customer_id"], "name": m["name"], "email": m["email"],
               "start_line": m.get("start_line")}
        (sent if good else failed).append(row)
        if good:
            done.add(m["customer_id"])
            try:
                db.set_app_setting(key, _json.dumps(sorted(done)), db_path=db_path)
            except Exception:
                logger.exception("event-day re-issue: could not record cid %s", m["customer_id"])
        try:
            db.log_message({"event_name": built["event"]["name"], "channel": "email",
                            "recipient_name": m["name"], "recipient_address": m["email"],
                            "subject": subject, "body_preview": "RE-ISSUE " + m["text"][:180],
                            "status": "sent" if good else "failed",
                            "sent_by": "event_day_email_reissue"}, db_path=db_path)
        except Exception:
            pass
    return {**out, "sent": sent, "failed": failed,
            "counts": {**out["counts"], "sent": len(sent), "failed": len(failed)}}
