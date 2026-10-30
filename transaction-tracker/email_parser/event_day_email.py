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
              photos: dict | None = None, base_url: str = "", hcp: dict | None = None) -> str:
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
    # THE TEES ROW (Kerry 10/30, mockup approved "New tees row is good"):
    # TEES | FORMAT | INDEX | PLAYING HCP. The index is the event's own (a
    # nine shows the 9-hole index); playing handicap 100% in ink and the
    # team / cart handicap in orange, each labelled under it.
    hcp = hcp or {}
    has_hcp = hcp.get("index") is not None or hcp.get("ph") not in (None, "")
    w_tee, w_fmt = ("22%", "30%") if has_hcp else ("50%", "50%")
    foot = []
    if tee and tee.get("name"):
        sw = (tee.get("color") or "").strip()
        dot = ""
        if sw:
            white = sw.lower() in ("#ffffff", "#fff")
            dot = (f'<span style="display:inline-block;width:12px;height:12px;border-radius:6px;'
                   f'background:{"#ffffff" if white or tee.get("ring") else sw};'
                   f'border:2px solid {"#9CA3AF" if white else sw};vertical-align:middle;margin-right:6px;"></span>')
        foot.append(f'<td width="{w_tee}" style="font-size:14px;vertical-align:top;padding-right:6px;">'
                    f'<span style="{_EYEBROW}color:{MUTED};">TEES</span><br>{dot}<b>{_e(tee["name"])}</b></td>')
    if format_line:
        foot.append(f'<td width="{w_fmt}" style="font-size:14px;vertical-align:top;padding-right:6px;">'
                    f'<span style="{_EYEBROW}color:{MUTED};">FORMAT</span><br><b>{_e(format_line)}</b></td>')
    if has_hcp:
        idx = hcp.get("index")
        try:
            idx_txt = f"{float(idx):.1f}" if idx is not None else "&ndash;"
        except (TypeError, ValueError):
            idx_txt = _e(idx)
        sub = f'<br><span style="font-size:11px;color:{MUTED};">{_e(hcp.get("holes") or "")}-hole</span>' if hcp.get("holes") else ""
        foot.append(f'<td width="17%" style="font-size:14px;vertical-align:top;padding-right:6px;">'
                    f'<span style="{_EYEBROW}color:{MUTED};">INDEX</span><br><b>{idx_txt}</b>{sub}</td>')
        ph, net, lab = hcp.get("ph"), hcp.get("net"), (hcp.get("net_label") or "TEAM")
        slash = '<span style="color:#D1D5DB;"> / </span>'
        top = f'<b style="color:{INK};">{_e(ph if ph not in (None, "") else "&ndash;")}</b>'
        bot = f'<span style="font-size:11px;color:{MUTED};">100%</span>'
        if net not in (None, ""):
            top += f'{slash}<b style="color:{ORANGE};">{_e(net)}</b>'
            bot += f'{slash}<span style="font-size:11px;color:{ORANGE};">{_e(lab)}</span>'
        foot.append(f'<td style="font-size:14px;vertical-align:top;white-space:nowrap;">'
                    f'<span style="{_EYEBROW}color:{MUTED};white-space:nowrap;">PLAYING HCP</span><br>{top}<br>{bot}</td>')
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


def ctp_hole_labels(event_id: int, db_path=None) -> list:
    """The proximity contests in order as their own labels (Kerry 10/30:
    "Closest to Pin should be labelled by actual hole"): "Hole 2", or
    "Longest Putt · Hole 9". The same contests the Proximity report, the
    games sheet and the leaderboard's CTPs tab read. [] when unknown."""
    from email_parser import database as db
    try:
        rep = db.event_proximity_report(int(event_id), db_path=db_path) or {}
    except Exception:
        logger.exception("ctp hole labels: proximity report failed for %s", event_id)
        return []
    out = []
    for c in rep.get("contests") or []:
        if c.get("hole") is None:
            out.append(None)
        elif c.get("kind") == "longest_putt":
            out.append(f"Longest Putt \u00b7 Hole {c['hole']}")
        else:
            out.append(f"Hole {c['hole']}")
    return out


def games_view(tab: dict | None, ctp_holes: list | None = None) -> dict:
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
            label = _game_label(r.get("game"))
            m = re.match(r"^CTP\s*#\s*(\d+)", (r.get("game") or "").strip())
            if m and ctp_holes:
                i = int(m.group(1)) - 1
                h = ctp_holes[i] if 0 <= i < len(ctp_holes) else None
                if h:
                    label = (h if h.startswith("Longest") else f"Closest to the Pin \u00b7 {h}")
            rows.append({"game": label, "pot": r.get("pot"), "note": note})
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


# PACE OF PLAY on the Event Info email (Kerry 10/29: "I think we also need to
# have something about expected pace and an announcement of the Group Pace bar
# in the event info emails"). The course's own standard
# (database.course_pace_targets, Kissing Tree 4:00) and the three-colour bar
# the results email will show. Behind dial `event_day_pace_card` (off until
# Kerry approves the words); words here, not in the approved template, so the
# template's approval hash is untouched.
POINTS_DIAL = "event_day_points_card"
PACE_DIAL = "event_day_pace_card"
_TIME_RE = re.compile(r"(\d{1,2}):(\d\d)\s*([AP]M)", re.I)


def _hm(mins: int) -> str:
    return f"{mins // 60}:{mins % 60:02d}"


def _finish(start_line: str | None, mins: int) -> str | None:
    m = _TIME_RE.search(start_line or "")
    if not m:
        return None
    h, mi, ap = int(m.group(1)) % 12, int(m.group(2)), m.group(3).upper()
    t = (h + (12 if ap == "PM" else 0)) * 60 + mi + mins
    t %= 24 * 60
    hh = t // 60
    return f"{(hh % 12) or 12}:{t % 60:02d} {'PM' if hh >= 12 else 'AM'}"


def pace_card(lo: int, hi: int, holes: int, course: str | None, start_line: str | None) -> str:
    fin = _finish(start_line, lo)
    seg = 'height:14px;font-size:0;line-height:0;'
    bar = (f'<table {_T}><tr>'
           f'<td width="33%" bgcolor="#22C55E" style="{seg}background:#22C55E;border-radius:7px 0 0 7px;">&nbsp;</td>'
           f'<td width="34%" bgcolor="#FACC15" style="{seg}background:#FACC15;">&nbsp;</td>'
           f'<td width="33%" bgcolor="#EF4444" style="{seg}background:#EF4444;border-radius:0 7px 7px 0;">&nbsp;</td>'
           f'</tr></table>'
           f'<table {_T} style="font-size:12px;color:{MUTED};"><tr>'
           f'<td width="33%" style="padding-top:4px;">{_hm(lo)} or under</td>'
           f'<td width="34%" align="center" style="padding-top:4px;">{_hm(lo)} to {_hm(hi)}</td>'
           f'<td width="33%" align="right" style="padding-top:4px;">over {_hm(hi)}</td></tr></table>')
    where = _e(course) if course else "The course"
    lead = (f'{where} expects {holes} holes in <b>{_hm(lo)}</b>.'
            + (f' Off at {_e(_TIME_RE.search(start_line).group(0))}, that puts your group in by <b>{_e(fin)}</b>.'
               if fin else ""))
    return (
        f'<table {_T} style="border:1px solid {LINE};border-radius:8px;margin:0 0 18px;">'
        f'<tr><td style="padding:14px 16px 6px;">'
        f'<div style="{_EYEBROW}color:{ORANGE};">PACE OF PLAY</div>'
        f'<div style="font-size:15px;line-height:1.5;padding-top:4px;">{lead}</div></td></tr>'
        f'<tr><td style="padding:6px 16px 4px;">{bar}</td></tr>'
        f'<tr><td style="padding:8px 16px 14px;font-size:14px;line-height:1.5;">'
        f'New this time: Live Scoring times every group, and your results email will show '
        f'<b>YOUR GROUP\u2019S PACE</b> on this bar. Keep up with the group ahead and help keep us in the green.'
        f'</td></tr></table>')


def _pace_targets_for(conn, ev: dict, holes, db_path=None):
    from email_parser import database as db
    cid = ev.get("course_id")
    if not cid and ev.get("course"):
        r = conn.execute("SELECT course_id FROM courses WHERE lower(name) = lower(?)", (ev["course"],)).fetchone()
        cid = r[0] if r else None
    h = 18 if int(holes or 9) >= 18 else 9
    lo, hi = db.course_pace_targets(cid, h, db_path=db_path)
    return lo, hi, h


def scoring_button(url: str) -> str:
    return (f'<table {_T} style="margin:0 0 16px;"><tr><td align="center" bgcolor="{ORANGE}" '
            f'style="background:{ORANGE};border-radius:999px;padding:12px;">'
            f'<a href="{_e(url)}" style="color:#ffffff;text-decoration:none;font:bold 15px Arial,sans-serif;'
            f'display:block;">Keep score on your phone</a></td></tr></table>')


def _dots(n) -> str:
    n = int(n or 0)
    return ("&#9679;" * n) if n > 0 else "&nbsp;"


_NUM_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven",
              8: "Eight", 9: "Nine", 10: "Ten"}


def _pts(v) -> str:
    v = float(v or 0)
    return f"{v:.0f}" if v == int(v) else f"{v:.1f}"


def standings_going_in(facts: dict, cid: int, first: str, event_name: str,
                       finale: bool = False) -> str:
    """STANDINGS GOING IN, design-claude option 1c (Kerry-approved 10/30,
    mailbox #2564): a navy band with a personal headline, FALL RACE and
    {MONTH} · {prize} columns (place | points, a status line), an orange
    "Points not active" strip with ACTIVATE for a player whose fall points
    are not active, and "See the full standings". Read from the results
    email's own race and month readers (results_email.event_facts), so the
    numbers are the same everywhere. Beyond the spec, per player (Kerry:
    "per player updates that make sense"): a bought-in player within
    results_email.WITHIN_REACH points of the last paid place, and an
    inactive one, are told how far they are from the money. "" when the
    person has no points in either race."""
    from email_parser import results_email as R
    cid = int(cid)
    ch = R._person_chapter(facts, cid)
    race = R._race_of(facts, cid)
    rows = race.get("rows") or []
    r = R._race_row(facts, cid)
    m, _lead = R._month_row(facts, cid)
    has_fall = bool(r and (r.get("total_points") or 0) > 0)
    has_month = bool(m and (m.get("points") or 0) > 0)
    if not (has_fall or has_month):
        return ""
    first = (first or "").strip() or "friend"
    ladder = race.get("payouts") or []
    WR = getattr(R, "WITHIN_REACH", 10)
    # ── FALL ──
    fall_place, fall_pts, fall_line = "—", "0", "No fall points yet"
    fall_lead = fall_tied = False
    back = 0
    out_of_money = None
    far = False
    enrolled = bool(r and r.get("enrolled"))
    inactive_line = ""
    if has_fall:
        pts = float(r["total_points"])
        tots = sorted((float(x.get("total_points") or 0) for x in rows), reverse=True)
        top = tots[0] if tots else pts
        n_top = sum(1 for t in tots if t == top)
        fall_place = R._rank_text(r.get("rank"))
        fall_pts = _pts(pts)
        ins = sorted((float(x.get("total_points") or 0) for x in rows if x.get("enrolled")), reverse=True)
        act_place = 1 + sum(1 for v in ins if v > pts)
        cut_gap = (ins[len(ladder) - 1] - pts) if (ladder and len(ins) >= len(ladder)) else None
        if pts == top and n_top == 1:
            fall_lead = True
            second = tots[1] if len(tots) > 1 else pts
            fall_line = f"Leading by {_pts(pts - second)}"
        elif pts == top:
            fall_tied = True
            fall_line = "Tied for 1st"
        else:
            back = top - pts
            fall_line = "1 point back" if back == 1 else f"{_pts(back)} back"
            if ladder and act_place <= len(ladder):
                if enrolled:
                    fall_line += " \u00b7 in the money"
            elif cut_gap is not None and cut_gap > WR:
                # FAR FROM THE MONEY (Kerry 10/30: "I don't think we try to
                # sell to people that are 10 or more back from the money and
                # not do the orange bar to activate. Just tell them where they
                # are"): place and points back only; no strip, no "not in".
                far = True
            elif cut_gap is not None and cut_gap > 0:
                # OUT OF THE MONEY: the distance that matters is to the last
                # paid place, not to the lead (Kerry 10/30: "Points back for
                # some should be based on how far out of the money they are,
                # not from the lead").
                out_of_money = cut_gap
                fall_line = f"{_pts(cut_gap)} out of the money \u00b7 {fall_line}"
        if not enrolled:
            pay = ladder[act_place - 1] if 0 < act_place <= len(ladder) else None
            if pay:
                inactive_line = f"Active today = {R._ordinal(act_place)} place, {R._usd(pay / 100)}."
            else:
                inactive_line = f"Active today = {R._ordinal(act_place)} place."
                if cut_gap is not None and 0 < cut_gap <= WR:
                    inactive_line = (f"Active today = {R._ordinal(act_place)} place, "
                                     f"{_pts(cut_gap)} out of the money.")
    # ── MONTH ──
    month = facts.get("month") or {}
    mname = (month.get("name") or "").upper() or "THIS MONTH"
    purse = month.get("purse")
    mlabel = f"{mname} \u00b7 ${purse:g}" if purse else mname
    month_place, month_pts, month_line = "—", "0", "No points yet"
    month_lead = False
    if has_month:
        st = month.get("standings") or []
        mp = float(m.get("points") or 0)
        mt = sorted((float(x.get("points") or 0) for x in st), reverse=True)
        mtop = mt[0] if mt else mp
        rl = str(m.get("rank_label") or m.get("rank") or "")
        month_place = R._rank_text(rl)
        month_pts = _pts(mp)
        if mp == mtop and mt.count(mtop) == 1:
            month_lead = True
            month_line = f"Leading by {_pts(mp - (mt[1] if len(mt) > 1 else mp))} \u00b7 winner takes all"
        elif mp == mtop:
            month_line = "Tied for 1st \u00b7 winner takes all"
        else:
            month_line = f"{_pts(mtop - mp)} back \u00b7 leader has {_pts(mtop)}"
    # ── HEADLINE (§3, first match wins) ──
    mword = (month.get("name") or "the month").title()
    if fall_lead and month_lead:
        head = f"You lead both races, {first}"
    elif fall_tied:
        head = f"You're tied for the lead, {first}"
    elif fall_lead:
        head = f"You lead the Fall Race, {first}"
    elif month_lead:
        head = f"You lead {mword}, {first}"
    elif has_fall and far:
        head = f"Here's where you stand, {first}"
    elif has_fall:
        gap = out_of_money if out_of_money else back
        b = int(gap) if gap == int(gap) else gap
        n = _NUM_WORDS.get(b) if isinstance(b, int) else None
        n = n or _pts(gap)
        what = "out of the money" if out_of_money else "back"
        head = (f"{n} {what} with one round to play, {first}" if finale
                else f"{n} {what} going in, {first}")
    else:
        head = f"Here's where you stand, {first}"
    head = _e(head) + ("\u2026 but you're not in!" if (has_fall and not enrolled and not far) else ".")
    ev = _e((event_name or "").upper())
    fall_key = (R.FALL_RACE.get(ch) or (None, "", ""))[1]
    standings_url = (f"{R.BASE}/member/contests#race={fall_key}&player={cid}" if has_fall and fall_key
                     else f"{R.BASE}/member/contests#race=monthly&player={cid}")
    icon = f"{R.BASE}/static/email/trophy-star-orange-68.png"
    num = "font-size:28px;font-weight:bold;color:#FFFFFF;line-height:1;"
    ptsl = ("font-family:Helvetica,Arial,sans-serif;font-size:10px;font-weight:bold;letter-spacing:1.2px;"
            "color:#9DB4D6;padding-left:4px;")
    lab = "font-size:10px;font-weight:bold;letter-spacing:1.6px;color:#9DB4D6;"
    sub = "font-family:Helvetica,Arial,sans-serif;font-size:11.5px;color:#C9D6EA;margin-top:4px;"

    def col(label, place, points, line, place_color, left):
        return (f'<td width="50%" valign="top" style="border-top:1px solid #33517F;'
                + ('border-left:1px solid #33517F;padding:12px 0 0 16px;' if left else 'padding-top:12px;') + '">'
                f'<div style="{lab}">{_e(label)}</div>'
                f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;margin-top:6px;"><tr>'
                f'<td valign="bottom" style="font-size:30px;font-weight:bold;color:{place_color};line-height:1;padding-right:14px;">{_e(place)}</td>'
                f'<td valign="bottom" style="border-left:1px solid #4E6EA5;padding-left:14px;white-space:nowrap;">'
                f'<span style="{num}">{_e(points)}</span><span style="{ptsl}">PTS</span></td></tr></table>'
                f'<div style="{sub}">{_e(line)}</div></td>')

    strip = ""
    if has_fall and not enrolled and not far:
        from email_parser.results_email import STORE_CONTESTS
        strip = (f'<tr><td bgcolor="#E87C3E" style="background:#E87C3E;padding:11px 20px;">'
                 f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;"><tr>'
                 f'<td style="font-family:Helvetica,Arial,sans-serif;font-size:13px;line-height:1.45;color:#FFFFFF;">'
                 f'<b>Points not active.</b> {_e(inactive_line)}</td>'
                 f'<td align="right" style="text-align:right;white-space:nowrap;padding-left:10px;">'
                 f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;display:inline-table;"><tr>'
                 f'<td bgcolor="#FFFFFF" style="background:#FFFFFF;border-radius:9999px;">'
                 f'<a href="{_e(STORE_CONTESTS)}" style="display:inline-block;color:#BF5700;font-family:Georgia,serif;font-weight:bold;'
                 f'padding:8px 16px;font-size:11.5px;letter-spacing:1px;text-decoration:none;">ACTIVATE</a></td>'
                 f'</tr></table></td></tr></table></td></tr>')
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="border-collapse:collapse;width:100%;margin:16px 0;font-family:Georgia,\'Times New Roman\',serif;">'
            f'<tr><td bgcolor="#002868" style="background:#002868;padding:18px 20px 16px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;"><tr>'
            f'<td width="44" valign="middle" style="width:44px;"><img src="{icon}" alt="" width="34" height="34" style="display:block;border:0;"></td>'
            f'<td valign="middle"><div style="font-size:10.5px;font-weight:bold;letter-spacing:2px;color:#9DB4D6;">GOING INTO THE {ev}</div>'
            f'<div style="font-size:22px;font-weight:bold;color:#FFFFFF;line-height:1.2;margin-top:4px;">{head}</div></td>'
            f'</tr></table>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;margin-top:14px;table-layout:fixed;"><tr>'
            + col("FALL RACE", fall_place, fall_pts, fall_line, "#E87C3E", False)
            + col(mlabel, month_place, month_pts, month_line, "#FFFFFF", True)
            + f'</tr></table></td></tr>{strip}'
            f'<tr><td align="center" style="padding:9px 0 0;font-family:Helvetica,Arial,sans-serif;font-size:12px;text-align:center;">'
            f'<a href="{_e(standings_url)}" style="color:#BF5700;font-weight:bold;text-decoration:underline;">See the full standings \u203a</a></td></tr>'
            f'</table>')


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
    # YARDS and SI on the player's OWN tees (Kerry 10/30: "add a yardage and
    # SI row ... based on the tees they're playing, so they can prepare
    # accordingly or really understand"): the printed scorecard's grid
    # yardage for his band, and his own stroke index (which his pops follow).
    yds = ((grid.get("yards") or {}).get(row.get("band")) or {})
    si = row.get("si_by_hole") or {}
    ycell = 'align="center" style="padding:3px 0;font-size:11px;color:#4B5563;border-top:1px solid ' + LINE + ';"'
    # A team pop that falls on a par 3 is dropped (no team pops on par 3s);
    # the card shows it as an orange X there, as the printed scorecard does
    # (Kerry 10/30: "The 7 and 6 needs to be shown correctly ... with the
    # orange X's when a pop falls on a par 3"), so the X's plus the dots add
    # up to the team handicap while TOT counts the pops played.
    ghost = {}
    for k, v in (row.get("net_ghost") or {}).items():
        try:
            ghost[int(k)] = int(v or 0)
        except (TypeError, ValueError):
            pass

    def _net_tot(keys):
        # "4 | 3" when a par 3 took pops in these holes (Kerry 10/30: "show 4/3
        # for the front 9 OUT column and 7/6 for the TOT column ... So a
        # player understands more visually why the 7 from their Team Playing
        # Handicap differs from their actual scorecard pops"): pops the
        # handicap gives / pops played.
        played = _sum(net_d, keys)
        lost = 0
        for h in keys:
            try:
                lost += ghost.get(int(h), 0)
            except (TypeError, ValueError):
                pass
        if not lost:
            return f'<span style="color:{ORANGE};">{played}</span>'
        return (f'<span style="color:{ORANGE};white-space:nowrap;">{played + lost}'
                f'<span style="color:#D1D5DB;font-weight:normal;padding:0 2px;">|</span>{played}</span>')

    def _net_cell(h):
        try:
            g = ghost.get(int(h), 0)
        except (TypeError, ValueError):
            g = 0
        n = int(net_d.get(h) or 0)
        if g <= 0:
            return _dots(n)
        return (("&#9679;" * n) + f'<b style="font-family:Arial,sans-serif;">{"&#10005;" * g}</b>')
    net_short = "CART" if (net or {}).get("unit") == "cart" else "TEAM"
    cell = 'align="center" style="padding:3px 0;font-size:12px;border-top:1px solid ' + LINE + ';"'
    lab = f'style="padding:3px 6px 3px 8px;font:bold 10px Arial,sans-serif;letter-spacing:1px;color:{MUTED};border-top:1px solid {LINE};white-space:nowrap;"'
    # EQUAL HOLE COLUMNS (Kerry 10/29: "I would like scorecard displays to
    # always have equal hole column widths though. Makes it look more
    # professional"): fixed layout, every hole the same share of the width.
    # TOT column (Kerry 10/20): par total, and the pops each game gives.
    def _sum(d, keys):
        t = 0
        for h in keys:
            try:
                t += int(d.get(h) or 0)
            except (TypeError, ValueError):
                pass
        return t
    # FRONT / BACK (Kerry 10/30: "for 18 hole cards ... they need to wrap
    # front 9 back 9. They get real scrunched"): an 18 is two stacked nines,
    # OUT on the front, IN + TOT on the back, the hole columns aligned
    # between the two (the front carries an empty TOT slot). Email clients
    # ignore media queries, so the split is always on. Hole columns are one
    # width (Kerry 10/29); the totals have their own.
    lab_w, tot_w = 16, 10
    split = len(holes) > 9
    segs = ([(holes[:9], "OUT", False), (holes[9:], "IN", True)] if split
            else [(holes, "TOT", False)])
    n_tot = 2 if split else 1
    hw = f"{(100 - lab_w - tot_w * n_tot) / 9 if split else (100 - lab_w - tot_w) / len(holes):.2f}%"
    tcell = ('align="center" style="padding:3px 0;font:bold 12px Arial,sans-serif;border-top:1px solid '
             + LINE + ';border-left:1px solid ' + LINE + ';"')
    thead = (f'width="{tot_w}%" align="center" style="width:{tot_w}%;padding:3px 0;font:bold 10px Arial,sans-serif;'
             f'letter-spacing:1px;color:#ffffff;" bgcolor="{INK}"')
    blank = f'<td width="{tot_w}%" style="width:{tot_w}%;"></td>'
    grids = []
    for hs, tlab, with_tot in segs:
        head = "".join(f'<td width="{hw}" align="center" style="width:{hw};padding:3px 0;font:bold 12px Arial,sans-serif;color:#ffffff;" bgcolor="{INK}">{h}</td>' for h in hs)
        pars = "".join(f"<td {cell}>{par.get(h, '')}</td>" for h in hs)
        yds_row = "".join(f'<td {ycell}>{_e(yds.get(h) or "")}</td>' for h in hs)
        si_row = "".join(f'<td {ycell}>{_e(si.get(h) or si.get(str(h)) or "")}</td>' for h in hs)
        ph_row = "".join(f'<td {cell}><span style="color:{INK};">{_dots(ph_d.get(h))}</span></td>' for h in hs)
        net_row = "".join(f'<td {cell}><span style="color:{ORANGE};">{_net_cell(h)}</span></td>' for h in hs)
        head += f"<td {thead}>{tlab}</td>"
        pars += f"<td {tcell}>{_sum(par, hs) or ''}</td>"
        yds_row += f'<td {tcell}><span style="font-size:11px;">{_sum(yds, hs) or ""}</span></td>'
        si_row += f'<td {tcell}></td>'
        ph_row += f'<td {tcell}><span style="color:{INK};">{_sum(ph_d, hs)}</span></td>'
        net_row += f'<td {tcell}>{_net_tot(hs)}</td>'
        if split:
            if with_tot:
                head += f"<td {thead}>TOT</td>"
                pars += f"<td {tcell}>{_sum(par, holes) or ''}</td>"
                yds_row += f'<td {tcell}><span style="font-size:11px;">{_sum(yds, holes) or ""}</span></td>'
                si_row += f'<td {tcell}></td>'
                ph_row += f'<td {tcell}><span style="color:{INK};">{_sum(ph_d, holes)}</span></td>'
                net_row += f'<td {tcell}>{_net_tot(holes)}</td>'
            else:
                head += f'<td width="{tot_w}%" style="width:{tot_w}%;" bgcolor="{INK}"></td>'
                pars += blank
                yds_row += blank
                si_row += blank
                ph_row += blank
                net_row += blank
        grids.append(
            f'<table {_T} style="border:1px solid {LINE};border-radius:6px;table-layout:fixed;margin:0 0 6px;">'
            f'<tr><td width="{lab_w}%" bgcolor="{INK}" style="width:{lab_w}%;padding:3px 4px 3px 8px;font:bold 10px Arial,sans-serif;letter-spacing:0.5px;color:#ffffff;white-space:nowrap;">HOLE</td>{head}</tr>'
            + (f'<tr><td {lab}>YDS</td>{yds_row}</tr>' if yds else "")
            + f'<tr><td {lab}>PAR</td>{pars}</tr>'
            + (f'<tr><td {lab}>SI</td>{si_row}</tr>' if si else "")
            + f'<tr><td {lab}>NET</td>{ph_row}</tr>'
            f'<tr><td {lab}>{net_short}</td>{net_row}</tr></table>')
    grid_html = "".join(grids)
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
        bits.append(f"No {net_short.lower()} pops on par 3s"
                    + (f": an orange &#10005; marks a {net_short.lower()} pop that lands on one, so your "
                       f"{_e(row.get('net'))} plays as {sum(int(v or 0) for v in net_d.values())}." if ghost else "."))
    return (f'<div style="{_EYEBROW}color:{MUTED};padding-bottom:8px;">YOUR CARD '
            f'<span style="letter-spacing:0;font-weight:normal;">&#9679; = a pop on that hole'
            + (f' &nbsp;<b style="color:{ORANGE};">&#10005;</b> = no {net_short.lower()} pop on a par 3' if ghost else "")
            + '</span></div>'
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

def build_event_day_emails(event_id: int, db_path=None, games_tab: dict | None = None,
                           preview: bool = False) -> dict:
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
                                       else _read_games_tab(int(event_id)),
                                       ctp_holes=ctp_hole_labels(int(event_id), db_path))
                except Exception as exc:
                    logger.exception("event-day email: games tab read failed (non-fatal)")
                    gview = {"ok": False, "why": f"games tab unreadable: {exc}"}
        # PACE OF PLAY card: dial event_day_pace_card on = every send;
        # "preview" = staff previews only (Kerry reviews the words first).
        pace_t = None
        try:
            dial = (db.get_app_setting(PACE_DIAL, db_path=db_path) or "off").strip().lower()
            if dial == "on" or (preview and dial == "preview"):
                hk = next((g.get("holes") for g in groups if g.get("holes")), None) or pack.get("holes_key") or 9
                pace_t = _pace_targets_for(conn, ev, hk, db_path)
        except Exception:
            logger.exception("event-day email: pace card unavailable (non-fatal)")
            pace_t = None
        # STANDINGS GOING IN (Kerry 10/30: "a row that shows their points and
        # standings for the Chapter Fall Points and the Monthly points (similar
        # to the Event Recap) so they get to see their place before going into
        # the event"): the results email's own YOUR POINTS card, read once per
        # build from results_email.event_facts, so both emails show the same
        # numbers. Dial event_day_points_card: on = every send, preview (the
        # default) = staff previews only until Kerry OKs the look.
        pts_facts = None
        try:
            pdial = (db.get_app_setting(POINTS_DIAL, db_path=db_path) or "preview").strip().lower()
            if pdial == "on" or (preview and pdial == "preview"):
                from email_parser import results_email as _rx
                pts_facts = _rx.event_facts(int(event_id), db_path=db_path)
        except Exception:
            logger.exception("event-day email: standings card unavailable (non-fatal)")
            pts_facts = None
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

        try:
            nh_cids = set((db.event_nh_seat_set(conn, int(event_id), db_path=db_path) or {}).get("cids") or ())
        except Exception:
            logger.exception("event-day email: N/H set unavailable for %s", event_id)
            nh_cids = set()
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
            # "18 · Team Net" (Kerry's tees-row mockup, 10/30)
            format_line = " \u00b7 ".join(x for x in ((f"{holes} holes" if not team else holes) if holes else "", team) if x)
            tee = tees.get(str(me.get("tee_choice"))) if me.get("tee_choice") else None
            card_html = ""
            hcp_row = None
            hit_sc = sc_rows.get(cid)
            if hit_sc:
                rr, hk = hit_sc
                grid = sc_grids.get(hk) or sc_grids.get(str(hk)) or {}
                _d = sc_dump.get(cid) or {}
                hcp_row = {"index": _d.get("index"), "ph": rr.get("ph"),
                           "net": rr.get("net") if sc_net else None,
                           "net_label": "CART" if "cart" in (team or "").lower() else "TEAM",
                           "holes": holes}
                try:
                    card_html = card_strip(rr, grid, sc_net, sc_dump.get(cid),
                                           (tee or {}).get("name"))
                except Exception:
                    logger.exception("event-day email: card strip failed for cid %s", cid)
            spot = spot_card(g, me, start_headline=start_headline, start_sub=start_sub,
                             tee=tee, format_line=format_line, card_html=card_html,
                             photos=group_photos, base_url=group_base, hcp=hcp_row) if sl else ""
            from email_parser.link_clicks import tag_url as _tag
            tbutton = (teesheet_button(_tag(f"{teesheet_url}#g{_e(g.get('group_num'))}", cid, event_id, "teesheet"))
                       if teesheet_url and "{teesheet_button}" in tpl_text else "")
            gcard = games_card(gview, cid, bool(r.get("rsvp_only")), as_of, day) if gview.get("ok") else ""
            if pace_t:
                gcard += pace_card(pace_t[0], pace_t[1], pace_t[2], ev_info.get("course"), g.get("start_line"))
            if pts_facts and cid:
                try:
                    from email_parser import results_email as _rx
                    _ch = pts_facts["chapter"]
                    _lab = _rx.FALL_RACE.get(_ch, (None, None, (ev_info.get("chapter") or "").title()))[2]
                    _fin = bool(re.search(r"FALL\s+CHAMPIONSHIP", ev_info.get("item_name") or "", re.I))
                    if _ch == "tgf" or re.search(r"CHAMPIONSHIP", ev_info.get("item_name") or "", re.I):
                        # design-claude 1c (Kerry-approved, #2564)
                        _fn = (nm.get("first_name") if isinstance(nm, dict) else "") or (full.split()[0] if full else "")
                        _pts = standings_going_in(pts_facts, int(cid), _fn,
                                                  event_short_name(ev_info.get("item_name"), None), finale=_fin)
                    else:
                        _pts = _rx._points_card(pts_facts, int(cid), _lab, eyebrow="YOUR STANDINGS GOING IN")[0]
                    # A FINALE puts the standings first, above YOUR START
                    # (Kerry 10/30: "Standing need to be above your card in this
                    # case because this is the finale and perhaps we could
                    # capture one or two more entrants"): a championship or a
                    # TGF event; a regular night keeps them after the games.
                    if _pts and (_ch == "tgf" or re.search(r"CHAMPIONSHIP", ev_info.get("item_name") or "", re.I)):
                        spot = _pts + spot
                    else:
                        gcard += _pts
                except Exception:
                    logger.exception("event-day email: standings card failed for cid %s", cid)
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
            kind = newcomer_kind(r)
            msg = {**base, "subject": subject, "html": body, "text": text,
                   "newcomer": kind, "first_name": first,
                   "start_line": g.get("start_line"), "group": g.get("slot_label"),
                   "games_shown": bool(gcard or games_block),
                   "scoring_link": bool(scoring_block or sbutton)}
            if why:
                held.append({**base, "reason": "; ".join(why)})
                continue
            if cid in nh_cids:
                from email_parser.handicap_ask import ask_url, make_token
                hurl = ask_url(make_token(cid, int(event_id)))
                msg["html"] = with_banner(msg["html"], add_handicap_note(hurl))
                msg["text"] = f"No handicap on file: add yours at {hurl}\n\n" + msg["text"]
                msg["no_handicap"] = True
            if kind:
                msg["html"] = with_banner(msg["html"], rules_note())
                msg["text"] = f"New to TGF? Please review our TGF Rules of Play: {RULES_OF_PLAY_URL}\n\n" + msg["text"]
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


def _graph_send(creds, to, subject, html_body, cc=None) -> bool:
    from email_parser import fetcher
    return fetcher.send_mail_graph(tenant_id=creds[0], client_id=creds[1],
                                   client_secret=creds[2], from_address=creds[3],
                                   to_address=to, subject=subject, html_body=html_body,
                                   cc_address=cc or None)


#: Kerry 2026-10-20: "CC me on any emails that go out for handicap/venmo for
#: now". App setting `asks_cc` (default Kerry's address; "off" stops it) is
#: copied on every handicap-ask and payout-ask email.
ASKS_CC_DEFAULT = "kerry@thegolffellowship.com"


def asks_cc(db_path=None) -> str | None:
    from email_parser import database as db
    try:
        v = (db.get_app_setting("asks_cc", db_path=db_path) or "").strip()
    except Exception:
        v = ""
    if v.lower() == "off":
        return None
    return v or ASKS_CC_DEFAULT


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
    built = build_event_day_emails(event_id, db_path=db_path, preview=True)
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
    # the sheet these emails carried is the baseline for after-lock changes
    # (Kerry #2139); the first send sets it, a later re-run leaves it alone
    if sent:
        from email_parser import after_lock
        if not after_lock._get(after_lock.STATE_KEY.format(int(event_id)), db_path):
            after_lock.record_sent(event_id, db_path)
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


LATE_ADD_PREFIX = "UPDATED GROUP: "
RULES_OF_PLAY_URL = "https://tgf-tracker.up.railway.app/static/print/TGF_Rules_of_Play.pdf"


def newcomer_kind(r: dict) -> str | None:
    """Kerry 10/20: "1st Timers, Guests or New Members". 'first' (first TGF
    event, _mark_first_timers), 'guest', 'new' (joined as a new member this
    year), else None."""
    if r.get("is_first_timer"):
        return "first"
    st = f"{r.get('user_status') or ''} {r.get('current_player_status') or ''}".lower()
    if "guest" in st:
        return "guest"
    if r.get("is_new"):
        return "new"
    return None


def add_handicap_note(url: str) -> str:
    """Kerry 10/20: a player with no handicap sees it in his own email, with
    a button to the handicap ask page (/handicap/<token>)."""
    return (f'<table {_T} style="margin:0 0 14px;"><tr><td bgcolor="#FFF7ED" style="background:#FFF7ED;'
            f'border:2px solid {ORANGE};border-radius:8px;padding:12px 14px;">'
            f'<div style="font:bold 13px Georgia,serif;letter-spacing:1px;color:{ORANGE};">NO HANDICAP ON FILE</div>'
            f'<div style="padding-top:4px;color:{INK};">We don\'t have a handicap for you yet, so a blind '
            f'stands in for your team score. Add yours and the blind comes off.</div>'
            f'<div style="padding-top:10px;"><table {_T}><tr><td bgcolor="{ORANGE}" style="background:{ORANGE};'
            f'border-radius:999px;"><a href="{_e(url)}" style="display:inline-block;background:{ORANGE};'
            f'color:#ffffff;text-decoration:none;font:bold 14px Arial,sans-serif;border-radius:999px;'
            f'padding:9px 18px;">ADD HANDICAP</a></td></tr></table></div></td></tr></table>')


def rules_note() -> str:
    """Rules of Play link for a new player (Kerry 10/20)."""
    return (f'<table {_T} style="margin:0 0 14px;"><tr><td style="border:1px solid {LINE};'
            f'border-radius:8px;padding:12px 14px;">'
            f'<div style="font:bold 13px Georgia,serif;letter-spacing:1px;color:{INK};">NEW TO TGF?</div>'
            f'<div style="padding-top:4px;color:{INK};">Please review our '
            f'<a href="{RULES_OF_PLAY_URL}" style="color:{ORANGE};font-weight:bold;">TGF Rules of Play</a> '
            f'before your round.</div></td></tr></table>')


def welcome_line(first: str, kind: str | None, gender: str | None = None) -> str:
    """The UPDATED GROUP line for a newcomer (Kerry 10/20: "This is Adam's
    first time playing with us! Welcome him in and help him understand our
    rules."). Pronoun from the profile's gender; they/them when unknown."""
    if not kind:
        return ""
    g = (gender or "").strip().upper()[:1]
    pr = "him" if g == "M" else "her" if g == "F" else "them"
    nm = _e(first)
    lead = {"first": f"This is {nm}'s first time playing with us!",
            "guest": f"{nm} is joining us as a guest!",
            "new": f"{nm} is one of our new members!"}[kind]
    return f"{lead} Welcome {pr} in and help {pr} understand our rules."


def late_add_banner(names: list, welcomes: list | None = None) -> str:
    """The orange notice for a group that just gained a late add."""
    who = _e(" and ".join(n for n in names if n))
    verb = "join" if len(names) > 1 else "joins"
    return (f'<table {_T} style="margin:0 0 14px;"><tr><td bgcolor="#FFF7ED" '
            f'style="background:#FFF7ED;border:2px solid {ORANGE};border-radius:8px;padding:12px 14px;">'
            f'<div style="font:bold 13px Georgia,serif;letter-spacing:1px;color:{ORANGE};">UPDATED GROUP</div>'
            f'<div style="padding-top:4px;color:{INK};"><strong>{who}</strong> {verb} your group. '
            f'Your start is the same. This replaces the earlier email; '
            f'your group and cart are below.</div>'
            + "".join(f'<div style="padding-top:6px;color:{INK};font-weight:bold;">{w}</div>'
                      for w in (welcomes or []) if w)
            + '</td></tr></table>')


def send_event_day_late_adds(event_id: int, late_cids, kerry_ok_post, confirm: bool = False,
                             db_path=None) -> dict:
    """LATE ADD (event-timeline.md, Kerry 10/17 + 10/20): each late add gets
    the approved event-day email as-is, and everyone already in that group
    gets it again with "UPDATED GROUP: " before the subject and a notice
    naming who joined. Nobody else is mailed. Same gates as the re-issue
    (approved template hash, Kerry-OK mailbox post, confirm=True to send);
    once per player per group state (app setting event_day_lateadd:...)."""
    import json as _json
    from email_parser import database as db
    from email_parser.customer_query import _kerry_ok
    late = {int(c) for c in late_cids}
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
    msgs = built["messages"]
    missing = sorted(late - {m["customer_id"] for m in msgs})
    if missing:
        held = [h for h in built["held"] if h.get("customer_id") in late]
        return {"refused": f"no sendable message for late add(s) {missing}", "held": held}
    groups, welcomes = {}, {}
    conn = db.get_connection(db_path)
    try:
        for m in msgs:
            if m["customer_id"] in late:
                groups.setdefault(m.get("group"), []).append(m["name"])
                g = conn.execute("SELECT gender FROM customers WHERE customer_id = ?",
                                 (m["customer_id"],)).fetchone()
                welcomes.setdefault(m.get("group"), []).append(
                    welcome_line(m.get("first_name") or m["name"].split()[0],
                                 m.get("newcomer"), g["gender"] if g else None))
    finally:
        conn.close()
    todo = [m for m in msgs if m.get("group") in groups]
    sig = "|".join(sorted(f"{m['customer_id']}:{m.get('group')}" for m in todo))
    key = f"event_day_lateadd:{int(event_id)}:{hashlib.sha256(sig.encode()).hexdigest()[:12]}"
    try:
        done = set(_json.loads(db.get_app_setting(key, db_path=db_path) or "[]"))
    except Exception:
        done = set()
    todo = [m for m in todo if m["customer_id"] not in done]

    def _shape(m):
        if m["customer_id"] in late:
            return m["subject"], m["html"], "LATE ADD "
        return (LATE_ADD_PREFIX + m["subject"],
                with_banner(m["html"], late_add_banner(groups[m.get("group")], welcomes.get(m.get("group")))),
                "LATE-ADD GROUP ")

    out = {"event": built["event"], "authority": why, "key": key,
           "late_adds": {g: n for g, n in groups.items()}, "already_sent": sorted(done),
           "counts": {"to_send": len(todo)}}
    if confirm is not True:
        return {**out, "dry_run": True,
                "plan": [{"customer_id": m["customer_id"], "name": m["name"], "email": m["email"],
                          "group": m.get("group"), "subject": _shape(m)[0]} for m in todo]}
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    sent, failed = [], []
    for m in todo:
        subject, html, tag = _shape(m)
        good = False
        try:
            good = _graph_send(creds, m["email"], subject, html)
        except Exception:
            logger.exception("event-day late add failed for cid %s", m["customer_id"])
        row = {"customer_id": m["customer_id"], "name": m["name"], "email": m["email"],
               "group": m.get("group")}
        (sent if good else failed).append(row)
        if good:
            done.add(m["customer_id"])
            try:
                db.set_app_setting(key, _json.dumps(sorted(done)), db_path=db_path)
            except Exception:
                logger.exception("event-day late add: could not record cid %s", m["customer_id"])
        try:
            db.log_message({"event_name": built["event"]["name"], "channel": "email",
                            "recipient_name": m["name"], "recipient_address": m["email"],
                            "subject": subject, "body_preview": tag + m["text"][:180],
                            "status": "sent" if good else "failed",
                            "sent_by": "event_day_email_late_add"}, db_path=db_path)
        except Exception:
            pass
    if sent and not failed:
        # a hand-run late add moves the after-lock baseline, so the job never
        # mails the same change again
        from email_parser import after_lock
        if after_lock._get(after_lock.STATE_KEY.format(int(event_id)), db_path):
            after_lock.record_sent(event_id, db_path)
    return {**out, "sent": sent, "failed": failed,
            "counts": {**out["counts"], "sent": len(sent), "failed": len(failed)}}


CARD_PREFIX = "UPDATED SCORECARD: "


def card_banner(course: str | None) -> str:
    """The notice at the top of a re-issue after the course card was
    corrected (Kerry 10/30, Kissing Tree)."""
    c = _e(course or "the course")
    return (f'<table {_T} style="margin:0 0 14px;"><tr><td bgcolor="#FFF7ED" '
            f'style="background:#FFF7ED;border:2px solid {ORANGE};border-radius:8px;padding:12px 14px;">'
            f'<div style="font:bold 13px Georgia,serif;letter-spacing:1px;color:{ORANGE};">UPDATED SCORECARD</div>'
            f'<div style="padding-top:4px;color:{INK};">We corrected {c}\u2019s scorecard to the club\u2019s '
            f'own card: the hole handicaps (stroke index) and yardages. Your pops may be on different holes '
            f'than in our earlier email. This replaces it. Your start, group and cart are the same.</div>'
            f'</td></tr></table>')


def send_event_day_reissue(event_id: int, kerry_ok_post, confirm: bool = False,
                           db_path=None, kind: str = "start") -> dict:
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
    card = (kind == "card")
    if card:
        # one card correction per event per sheet state
        key += ":card"
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
                "sample_subject": ((CARD_PREFIX if card else REISSUE_PREFIX) + todo[0]["subject"]) if todo else None}
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    sent, failed = [], []
    for m in todo:
        subject = (CARD_PREFIX if card else REISSUE_PREFIX) + m["subject"]
        html = with_banner(m["html"], card_banner((built.get("event") or {}).get("course"))
                           if card else reissue_banner(m.get("start_line")))
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
    if sent and not failed:
        from email_parser import after_lock
        if after_lock._get(after_lock.STATE_KEY.format(int(event_id)), db_path):
            after_lock.record_sent(event_id, db_path)
    return {**out, "sent": sent, "failed": failed,
            "counts": {**out["counts"], "sent": len(sent), "failed": len(failed)}}
