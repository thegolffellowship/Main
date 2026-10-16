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
"""
from __future__ import annotations

import html as _html
import re
from datetime import datetime

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
    for g in pack.get("groups") or []:
        players = []
        for p in sorted(g.get("players") or [], key=lambda x: x.get("cart_pos") or 0):
            if not (p.get("name") or "").strip():
                continue
            t = tees.get(str(p.get("tee_choice"))) or {}
            players.append({"name": p["name"].strip(), "cart": _cart(p),
                            "tee": t.get("name") or "", "color": t.get("color") or ""})
        groups.append({"group_num": g.get("group_num"),
                       "start": (g.get("start_line") or g.get("slot_label") or "").replace(" | ", " · "),
                       "players": players})
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
            try:
                idx_map = db._roster_handicap_index_map(
                    conn, as_of=db._event_index_as_of(dict(evrow) if evrow else None), db_path=db_path)
            except Exception:
                idx_map = {}
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
                registered.append({"name": name, "customer_id": int(cid) if cid else None,
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
                      if p.get("customer_id") else f'<span class="n">{_e(p["name"])}</span>')
                meta = " · ".join(x for x in (p.get("tee"), f"HCP {p['index']}" if p.get("index") else "") if x)
                rows.append(f'<div class="p">{nm}<span class="m">{_dot(p.get("color"))}{_e(meta)}</span></div>')
            body += (f'<section class="g"><div class="s">Registered so far · {len(reg)}</div>'
                     + "".join(rows) + "</section>")
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
                rows.append(f'<div class="p"><span class="n">{_e(p["name"])}</span>'
                            f'<span class="m">{dot}{_e(meta)}</span></div>')
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
.m {{ color:var(--muted); font-size:14px; white-space:nowrap; display:flex; align-items:center; gap:6px; }}
.dot {{ width:11px; height:11px; border-radius:50%; border:2px solid; display:inline-block; }}
footer {{ text-align:center; color:var(--muted); font-size:13px; padding:8px 16px 24px; }}
</style></head><body>
<header><div class="e">{_e(eyebrow)}</div><h1>{_e(title)}</h1><div class="sub">{_e(sub)}</div></header>
<main>{body}</main>
<footer>The Golf Fellowship · tee sheet as posted</footer>
</body></html>"""
