"""THE MEMBER TEE SHEET (Kerry 2026-10-13, on the tee sheet email: "what
about links for their live scoring and for the full tee sheet?").

Before the pairings are saved it lists who is registered so far (names
only; Kerry 10/16).

A public, read-only page at /member/teesheet/<event_id>: every group's
start, its players, carts and tees, from the saved sheet
(`get_event_print_pack`, the Starter Sheet's own reader). Names, starts,
carts and tee names only: no email, phone, handicap or money. Like the
rest of /member it needs no PIN. Each group carries an anchor (#g<group
number>) so the email's button lands on the player's own group.

Kerry 10/20: "Blinds should also show on this tee sheet, along with raw TGF
Handicap Indexes. If a player like Adam doesn't have a handicap, then it
should say no handicap ... and then when the blind is shown it needs to show
the explanation for why the blind is given." Each player shows his 18-hole
TGF index (or "No handicap"); each drawn blind is a row of its own with the
reason: the open seat, or the player it stands in for.
"""
from __future__ import annotations

import html as _html
import re
from datetime import datetime

MEMBER_STATUSES = ("active_member", "member_plus")
SPOTLIGHT_TEASE = ("Names in blue are TGF members: tap one to see their Player Spotlight. "
                   "Members get their own.")
INK, MUTED, LINE, ORANGE = "#1B1B1B", "#6B7280", "#E5E7EB", "#E87C3E"


def _e(s) -> str:
    return _html.escape(str(s or ""), quote=True)


def _cart(p: dict) -> str:
    pos = p.get("cart_pos") or 0
    return "A" if pos in (1, 2) else ("B" if pos in (3, 4) else "")


def _fmt_index(v) -> str:
    """14.24 -> '14.2'; a plus handicap (-1.5) -> '+1.5'; None -> ''."""
    try:
        f = round(float(v), 1)
    except (TypeError, ValueError):
        return ""
    return f"+{abs(f)}" if f < 0 else f"{f}"


def _dot(color: str) -> str:
    if not color:
        return ""
    white = color.lower() in ("#ffffff", "#fff")
    return (f'<span class="dot" style="background:{_e("#fff" if white else color)};'
            f'border-color:{_e("#9CA3AF" if white else color)};"></span>')


def _index_map(db, evrow, db_path=None) -> dict:
    """The 18-HOLE index (Kerry 10/16: "They should show 18"), the same
    number the roster shows (api_handicap_index_map's rule): double the
    9-hole index, or the starting handicap as typed. Keys ("c", cid) and
    the lower-cased name."""
    idx_map = {}
    try:
        as_of = db._event_index_as_of(dict(evrow) if evrow else None)
        for hp in db.get_all_handicap_players(db_path, as_of=as_of):
            i9 = hp.get("handicap_index")
            if i9 is None:
                continue
            i18 = (hp.get("starting_handicap_18")
                   if (hp.get("handicap_source") == "starting"
                       and hp.get("starting_handicap_18") is not None)
                   else round(float(i9) * 2, 1))
            if hp.get("customer_id") is not None:
                idx_map.setdefault(("c", int(hp["customer_id"])), i18)
            for nm in (hp.get("customer_name"), hp.get("player_name")):
                if nm:
                    idx_map.setdefault(nm.strip().lower(), i18)
    except Exception:
        idx_map = {}
    return idx_map


def _lookup(idx_map: dict, cid, name: str):
    idx = idx_map.get(("c", int(cid))) if cid else None
    return idx if idx is not None else idx_map.get((name or "").strip().lower())


def build_teesheet(event_id: int, db_path=None) -> dict | None:
    """The page's data, PII-free. None for an unknown event."""
    from email_parser import database as db
    pack = db.get_event_print_pack(int(event_id), db_path=db_path)
    if not pack:
        return None
    ev = pack.get("event") or {}
    tees = {str(t.get("band")): {"name": t.get("tee_name"), "color": t.get("color")}
            for t in pack.get("tee_legend") or [] if t.get("band") is not None}
    groups = []
    idx_map, blinds = {}, {}
    if pack.get("groups"):
        conn = db.get_connection(db_path)
        try:
            evrow = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
            idx_map = _index_map(db, evrow, db_path)
            blinds = db.get_event_blinds(int(event_id), conn=conn) or {}
        except Exception:
            blinds = blinds or {}
        finally:
            conn.close()
    for g in pack.get("groups") or []:
        players = []
        for p in sorted(g.get("players") or [], key=lambda x: x.get("cart_pos") or 0):
            if not (p.get("name") or "").strip():
                continue
            t = tees.get(str(p.get("tee_choice"))) or {}
            idx = _lookup(idx_map, p.get("customer_id"), p["name"])
            players.append({"name": p["name"].strip(), "cart": _cart(p),
                            "cart_pos": p.get("cart_pos"),
                            "index": _fmt_index(idx) if idx is not None else "",
                            "tee": t.get("name") or "", "color": t.get("color") or ""})
        by_pos = {pl["cart_pos"]: pl for pl in players}
        brows = []
        for b in (blinds.get(str(g.get("holes"))) or blinds.get(g.get("holes")) or {}).get(g.get("group_num")) or []:
            if not (b.get("name") or "").strip():
                continue
            if b.get("reason") == "nh":
                who = (by_pos.get(b.get("cart_pos")) or {}).get("name")
                why = (f"Blind for {who}, who has no TGF handicap yet" if who
                       else "Blind for a player with no TGF handicap yet")
            else:
                why = "Blind for the open seat"
            idx = _lookup(idx_map, b.get("customer_id"), b["name"])
            brows.append({"name": b["name"].strip(), "why": why,
                          "index": _fmt_index(idx) if idx is not None else ""})
        groups.append({"group_num": g.get("group_num"),
                       "start": (g.get("start_line") or g.get("slot_label") or "").replace(" | ", " · "),
                       "players": players, "blinds": brows})
    from email_parser.event_day_email import event_short_name, _weekday
    try:
        date = datetime.strptime((ev.get("event_date") or "")[:10], "%Y-%m-%d").strftime("%A, %B %-d")
    except ValueError:
        date = ""
    chap = (ev.get("chapter") or "").strip()
    # Before the pairings are set, the page still shows WHO is registered
    # (Kerry 10/16: "You could still show who is registered"). Names only,
    # from THE pairings roster; "playing, not paid" RSVP rows are left out.
    # Each name links to the player's Spotlight and shows the index in
    # effect for this event (THE roster index map) and the tee they play at
    # this course with its colour (Kerry 10/16).
    registered = []
    if not groups:
        conn = db.get_connection(db_path)
        try:
            evrow = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
            idx_map = _index_map(db, evrow, db_path)
            seen = set()
            for r in db._event_roster_rows(conn, int(event_id)):
                name = (r.get("customer") or r.get("name") or "").strip()
                if not name or r.get("rsvp_only"):
                    continue
                cid = r.get("customer_id")
                key = ("c", int(cid)) if cid else ("n", name.lower())
                if key in seen:
                    continue
                seen.add(key)
                idx = idx_map.get(("c", int(cid))) if cid else None
                if idx is None:
                    idx = idx_map.get(name.lower())
                t = tees.get(str((r.get("tee_choice") or "").strip())) or {}
                # The Spotlight is a MEMBER perk (Kerry 10/16: "don't put links in for
                # non-TGF Members. That's a perk that I want to tease").
                member = (r.get("current_player_status") or "") in MEMBER_STATUSES
                registered.append({"name": name, "customer_id": int(cid) if cid else None,
                                   "member": member,
                                   "index": _fmt_index(idx), "tee": t.get("name") or "",
                                   "color": t.get("color") or ""})
        finally:
            conn.close()
        registered.sort(key=lambda p: (p["name"].split()[-1].lower(), p["name"].lower()))
    return {"event_id": int(event_id),
            "registered": registered,
            "title": event_short_name(ev.get("item_name"), ev.get("course")),
            "day": _weekday(ev.get("event_date")), "date": date,
            "course": ev.get("course") or "",
            "chapter": "" if chap.upper() == "TGF" else chap,
            "groups": groups, "player_count": sum(len(g["players"]) for g in groups)}


def render_teesheet(data: dict) -> str:
    """One self-contained, phone-first page."""
    eyebrow = "THE GOLF FELLOWSHIP" + (f" · {data['chapter'].upper()}" if data["chapter"] else "")
    if not data["groups"]:
        reg = data.get("registered") or []
        body = (f'<p style="color:{MUTED};margin:0;">The tee sheet for this event '
                f'is not posted yet. Check back after the pairings are set.</p>')
        if reg:
            rows = []
            for p in reg:
                nm = (f'<a class="n" href="/member/spotlight?player={p["customer_id"]}">{_e(p["name"])}</a>'
                      if p.get("customer_id") and p.get("member") else f'<span class="n">{_e(p["name"])}</span>')
                meta = " · ".join(x for x in (p.get("tee"), f"HCP {p['index']}" if p.get("index") else "") if x)
                rows.append(f'<div class="p">{nm}<span class="m">{_dot(p.get("color"))}{_e(meta)}</span></div>')
            body += (f'<section class="g"><div class="s">Registered so far · {len(reg)}</div>'
                     + "".join(rows) + "</section>")
            if any(p.get("member") for p in reg):
                body += f'<p class="tease">{_e(SPOTLIGHT_TEASE)}</p>'
    else:
        cards = []
        for g in data["groups"]:
            rows = []
            for p in g["players"]:
                sw = p["color"]
                white = sw.lower() in ("#ffffff", "#fff")
                dot = (f'<span class="dot" style="background:{_e("#fff" if white else sw)};'
                       f'border-color:{_e("#9CA3AF" if white else sw)};"></span>' if sw else "")
                meta = " · ".join(x for x in (f"Cart {p['cart']}" if p["cart"] else "", p["tee"]) if x)
                hcp = (f'<span class="h">HCP {_e(p["index"])}</span>' if p.get("index")
                       else '<span class="h nh">No handicap</span>')
                rows.append(f'<div class="p"><span class="n">{_e(p["name"])}{hcp}</span>'
                            f'<span class="m">{dot}{_e(meta)}</span></div>')
            for b in g.get("blinds") or []:
                bh = f' <span class="h">HCP {_e(b["index"])}</span>' if b.get("index") else ""
                rows.append(f'<div class="p bl"><span class="n"><span class="bt">BLIND</span> '
                            f'{_e(b["name"])}{bh}<span class="why">{_e(b["why"])}</span></span></div>')
            cards.append(f'<section class="g" id="g{_e(g["group_num"])}"><div class="s">{_e(g["start"])}</div>'
                         + "".join(rows) + "</section>")
        body = "".join(cards)
    title = f"{data['day']} at {data['title']}" if data["day"] else data["title"]
    sub = " · ".join(x for x in (data["date"], data["course"],
                                     f"{data['player_count']} players" if data["player_count"] else
                                     (f"{len(data.get('registered') or [])} registered"
                                      if data.get("registered") else "")) if x)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tee Sheet · {_e(title)}</title>
<style>
:root {{ --ink:{INK}; --muted:{MUTED}; --line:{LINE}; --orange:{ORANGE}; --bg:#F8F8F8; --card:#fff; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.45 "Helvetica Neue",Helvetica,Arial,sans-serif; }}
header {{ background:var(--ink); color:#fff; padding:18px 16px 16px; }}
.e {{ font:bold 12px Georgia,serif; letter-spacing:2px; color:var(--orange); }}
h1 {{ font:bold 24px Georgia,serif; margin:4px 0 2px; }}
.sub {{ font-size:14px; color:#D1D5DB; }}
main {{ max-width:640px; margin:0 auto; padding:16px; display:grid; gap:12px; }}
.g {{ background:var(--card); border:1px solid var(--line); border-radius:10px; overflow:hidden; scroll-margin-top:12px; }}
.g:target {{ border-color:var(--orange); box-shadow:0 0 0 2px var(--orange); }}
.s {{ background:var(--orange); color:#fff; font:bold 18px Georgia,serif; padding:10px 14px; }}
.p {{ display:flex; justify-content:space-between; gap:12px; padding:9px 14px; border-top:1px solid var(--line); }}
.p:first-of-type {{ border-top:0; }}
.n {{ font-weight:600; }}
a.n {{ color:#2563eb; text-decoration:none; }}
.tease {{ color:var(--muted); font-size:14px; margin:0; text-align:center; }}
.m {{ color:var(--muted); font-size:14px; white-space:nowrap; display:flex; align-items:center; gap:6px; }}
.h {{ display:block; font-weight:normal; font-size:13px; color:var(--muted); }}
.h.nh {{ color:#B45309; }}
.bl {{ background:#FFFBEB; }}
.bl .n {{ font-style:italic; color:#92400E; }}
.bt {{ font:bold 10px Arial,sans-serif; letter-spacing:1px; font-style:normal; color:#fff; background:#D97706; border-radius:4px; padding:2px 5px; vertical-align:middle; }}
.why {{ display:block; font-weight:normal; font-size:13px; color:#92400E; }}
.dot {{ width:11px; height:11px; border-radius:50%; border:2px solid; display:inline-block; }}
footer {{ text-align:center; color:var(--muted); font-size:13px; padding:8px 16px 24px; }}
</style></head><body>
<header><div class="e">{_e(eyebrow)}</div><h1>{_e(title)}</h1><div class="sub">{_e(sub)}</div></header>
<main>{body}</main>
<footer>The Golf Fellowship · tee sheet as posted</footer>
</body></html>"""
