"""THE RESULTS EMAIL: one personal email per person after an event night.

Kerry 2026-10-13: "I'm just thinking one email that goes out to players with
everything rather than several different emails. For those that didn't play,
they'd get just the recap and what's next stuff. Perhaps with some personal
stuff." Kerry 10/14: "I want the recap emails typically sent 30 minutes after
the last score is posted for an event. For this one let's send it at 6:00a."

Who gets it (`audience`): everyone who played the event, plus the chapter's
active members and anyone who played the chapter in the last 12 months
(the invitation rules, Kerry 10/13), minus invitation opt-outs, roster
removals, course staff / vendors, members of another chapter and anyone with
no deliverable email. Leads are not included. A person who played one of the
night's events gets that event's email only.

What is in it, every figure read from the record (nothing typed in):
  played: YOUR NIGHT (group, start, card with pops, gross / net / points,
          birdies), YOUR WINNINGS (recorded payout rows), YOUR HANDICAP
          (index before -> after, differential), YOUR POINTS (fall race and
          the month, each linked to the player's own row), the recap, UP NEXT.
  didn't play: their race standing if they have one, the recap, UP NEXT.
The recap is the chapter's section of the night's recap file
(docs/claude/recaps/), story part only.

Nothing goes out unless every guard passes (`guards`): the results are final,
the engine and the saved cards agree on every player (card_parity), the
payouts are recorded and equal what the engine pays, and the message has no
blank, leftover tag or unlinked placeholder. Once per event per person
(app setting results_email_sent:<event_id>). Sends are scheduled in app
setting results_email_schedule ({event_id: {at, recap, authority}}) and
delivered by job `results_email_auto` every minute.

Previews go to TGF staff, or to a chapter manager's own address on record.
Bridge `scoring-results-email`; guard `test_results_email.py`.
"""
from __future__ import annotations

import html as _html
import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

BASE = "https://tgf-tracker.up.railway.app"
RECAP_DIR = Path(__file__).resolve().parent.parent / "docs" / "claude" / "recaps"
SCHEDULE_KEY = "results_email_schedule"
SENT_KEY = "results_email_sent:{event_id}"
AFTER_LAST_SCORE_MIN = 30          # Kerry 10/14: 30 minutes after the last score

INK, ORANGE, LINE, MUTED, GREEN, BODY = "#1B1B1B", "#E87C3E", "#E5E7EB", "#6B7280", "#15803D", "#4B5563"
EYE = "font:bold 11px Arial,sans-serif;letter-spacing:2px;"
T = 'role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'

FALL_RACE = {"san antonio": ("san_antonio_fall_net", "fall_sa", "San Antonio"),
             "austin": ("austin_fall_net", "fall_austin", "Austin")}
SIGNATURES = {
    "san antonio": "Kerry Niester<br>The Golf Fellowship<br>210.838.3948",
    "austin": "Robert Straiton<br>The Golf Fellowship — Austin",
}
STORE_CONTESTS = "https://thegolffellowship.com/shop/ols/products/season-contests"


def _e(s) -> str:
    return _html.escape(str(s if s is not None else ""), quote=True)


def _setting(key, db_path=None):
    from email_parser.database import get_app_setting
    return get_app_setting(key, db_path)


def _json_setting(key, db_path=None) -> dict:
    try:
        v = json.loads(_setting(key, db_path) or "{}")
        return v if isinstance(v, dict) else {}
    except (ValueError, TypeError):
        return {}


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _rank_text(rank) -> str:
    r = str(rank or "").strip()
    if r.upper().startswith("T") and r[1:].isdigit():
        return f"T{r[1:]}"
    return _ordinal(int(r)) if r.isdigit() else r


def _to_par(n: int) -> str:
    return "E" if n == 0 else (f"+{n}" if n > 0 else f"−{abs(n)}")


def _first_names(names: list) -> str:
    f = [(n or "").split()[0] for n in names if n]
    if not f:
        return ""
    return f[0] if len(f) == 1 else ", ".join(f[:-1]) + " &amp; " + f[-1]


# ---------------------------------------------------------------------------
# Building blocks (email-safe tables only)
# ---------------------------------------------------------------------------

def card(eyebrow, inner, head=None) -> str:
    top = (f'<tr><td bgcolor="{ORANGE}" style="background:{ORANGE};border-radius:8px 8px 0 0;'
           f'padding:14px 16px;color:#fff;">{head}</td></tr>') if head else ""
    eb = f'<div style="{EYE}color:{MUTED};padding-bottom:8px;">{eyebrow}</div>' if eyebrow else ""
    return (f'<table {T} style="border:1px solid {LINE};border-radius:8px;margin:0 0 18px;">{top}'
            f'<tr><td style="padding:12px 16px 14px;">{eb}{inner}</td></tr></table>')


def button(label, url, solid=True) -> str:
    if solid:
        return (f'<table {T} style="margin:0 0 10px;"><tr><td align="center" bgcolor="{ORANGE}" '
                f'style="background:{ORANGE};border-radius:999px;padding:12px;"><a href="{_e(url)}" '
                f'style="color:#fff;text-decoration:none;font:bold 15px Arial,sans-serif;display:block;">{label}</a></td></tr></table>')
    return (f'<table {T} style="margin:0 0 10px;"><tr><td align="center" style="border:2px solid {INK};'
            f'border-radius:999px;padding:10px;"><a href="{_e(url)}" style="color:{INK};text-decoration:none;'
            f'font:bold 15px Arial,sans-serif;display:block;">{label}</a></td></tr></table>')


def scorecard(holes, pars, strokes, dots) -> str:
    cell = f'align="center" style="padding:4px 0;font-size:13px;border-top:1px solid {LINE};"'
    lab = (f'style="padding:4px 6px 4px 0;font:bold 10px Arial,sans-serif;letter-spacing:1px;'
           f'color:{MUTED};border-top:1px solid {LINE};white-space:nowrap;"')
    head = "".join(f'<td align="center" bgcolor="{INK}" style="padding:4px 0;font:bold 12px Arial,sans-serif;color:#fff;">{h}</td>' for h in holes)
    par = "".join(f"<td {cell}>{p}</td>" for p in pars)

    def mark(s, p):
        if s is None:
            return "–"
        d = s - p
        if d <= -1:
            return (f'<span style="display:inline-block;width:20px;height:20px;line-height:20px;'
                    f'border:1.5px solid {INK};border-radius:10px;font-weight:bold;">{s}</span>')
        if d >= 2:
            return (f'<span style="display:inline-block;width:20px;height:20px;line-height:20px;'
                    f'border:1.5px solid {INK};">{s}</span>')
        return f"<b>{s}</b>" if d == 1 else str(s)
    sc = "".join(f"<td {cell}>{mark(s, p)}</td>" for s, p in zip(strokes, pars))
    dot = "".join(f'<td {cell}><span style="color:{ORANGE};">{"&#9679;" * max(0, d) if d else "&nbsp;"}</span></td>'
                  for d in dots)
    tot = "OUT" if holes and holes[0] == 1 and len(holes) == 9 else ("IN" if holes and holes[0] == 10 else "TOT")
    played = [s for s in strokes if s is not None]
    return (f'<table {T} style="border:1px solid {LINE};border-radius:6px;">'
            f'<tr><td bgcolor="{INK}" style="padding:4px 6px;font:bold 10px Arial,sans-serif;letter-spacing:1px;color:#fff;">HOLE</td>{head}'
            f'<td bgcolor="{INK}" align="center" style="font:bold 11px Arial,sans-serif;color:#fff;padding:0 4px;">{tot}</td></tr>'
            f'<tr><td {lab}>PAR</td>{par}<td {cell}>{sum(pars)}</td></tr>'
            f'<tr><td {lab}>YOU</td>{sc}<td {cell}><b>{sum(played)}</b></td></tr>'
            f'<tr><td {lab}>POPS</td>{dot}<td {cell}>{sum(d for d in dots if d > 0)}</td></tr></table>')


def money_rows(rows, total) -> str:
    r = "".join(f'<tr><td style="padding:6px 0;border-top:1px solid {LINE};font-size:15px;">{a}</td>'
                f'<td align="right" style="padding:6px 0;border-top:1px solid {LINE};font-size:15px;font-weight:bold;">{b}</td></tr>'
                for a, b in rows)
    return (f'<table {T}>{r}<tr><td style="padding:8px 0 0;font:bold 16px Georgia,serif;">Total</td>'
            f'<td align="right" style="padding:8px 0 0;font:bold 20px Georgia,serif;color:{GREEN};">{total}</td></tr></table>')


def stat_row(items) -> str:
    def link(it):
        if len(it) < 4 or not it[3]:
            return ""
        return (f'<div style="padding-top:6px;"><a href="{_e(it[3])}" style="color:#2563eb;font:bold 13px Arial,sans-serif;'
                f'text-decoration:none;">See my spot &rsaquo;</a></div>')
    tds = "".join(f'<td width="{100 // len(items)}%" style="vertical-align:top;padding-right:8px;">'
                  f'<div style="{EYE}color:{MUTED};">{it[0]}</div>'
                  f'<div style="font:bold 22px/1.2 Georgia,serif;color:{INK};padding-top:2px;">{it[1]}</div>'
                  f'<div style="font-size:13px;color:{BODY};">{it[2]}</div>{link(it)}</td>' for it in items)
    return f'<table {T}><tr>{tds}</tr></table>'


def note(text) -> str:
    return f'<div style="font-size:13px;color:{BODY};padding-top:8px;line-height:1.45;">{text}</div>'


def frame(eyebrow, title, inner, preheader) -> str:
    return (
        '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{_e(title)}</title></head><body style="margin:0;background:#F8F8F8;">'
        f'<div style="display:none;max-height:0;overflow:hidden;">{_e(preheader)}</div>'
        f'<div style="background:#F8F8F8;padding:16px 8px;font-family:\'Helvetica Neue\',Helvetica,Arial,sans-serif;color:{INK};">'
        f'<table {T} style="max-width:560px;margin:0 auto;">'
        f'<tr><td bgcolor="{INK}" style="background:{INK};border-radius:10px 10px 0 0;padding:16px 18px;">'
        f'<div style="font:bold 12px Georgia,serif;letter-spacing:2px;color:{ORANGE};">{_e(eyebrow)}</div>'
        f'<div style="font:bold 22px Georgia,serif;color:#fff;padding-top:4px;">{_e(title)}</div></td></tr>'
        f'<tr><td bgcolor="#ffffff" style="background:#fff;border:1px solid {LINE};border-top:0;border-radius:0 0 10px 10px;'
        f'padding:18px;font-size:16px;line-height:1.5;">{inner}</td></tr></table></div></body></html>')


# ---------------------------------------------------------------------------
# The night's facts, read once per event
# ---------------------------------------------------------------------------

def _chapter_key(ev: dict) -> str:
    return (ev.get("chapter") or "").strip().lower()


def recap_story(recap_file: str, section: str, enrolled: bool = False) -> str:
    """The chapter's recap, story part only (after the greeting, before UP
    NEXT), rendered by the recap mailer's own renderer. A bought-in reader
    does not get the 'activate them by BUYING IN' sentence."""
    from email_parser.recap_mail import extract_section, render_recap_html
    md = (RECAP_DIR / recap_file).read_text()
    _, body = extract_section(md, section)
    body = body.split("UP NEXT.")[0]
    keep, started = [], False
    for ln in body.split("\n"):
        if ln.startswith("**Subject:**"):
            continue
        if not started and ln.lower().startswith("good morning"):
            started = True
            continue
        if started:
            keep.append(ln)
    text = "\n".join(keep).strip()
    if enrolled:
        text = re.sub(r"\s*Your points are being tallied; activate them by \[BUYING IN\]\([^)]*\)\.", "", text)
    return render_recap_html(text)[1]


def _payout_label(category: str, desc: str) -> str:
    d = re.sub(r"^auto:\s*", "", desc or "").strip()
    d = re.sub(r"\s*\(GG \$\)", "", d)
    m = re.match(r"Skins F(\d+) ×(\d+) holes? (.+)", d)
    if m:
        holes = m.group(3).strip()
        return f"Skins · Flight {m.group(1)} · hole{'s' if ',' in holes else ''} {holes}"
    m = re.match(r"Skins ×(\d+) holes? (.+)", d)
    if m:
        holes = m.group(2).strip()
        return f"Skins · hole{'s' if ',' in holes else ''} {holes}"
    m = re.match(r"Ind (Net|Gross) F(\d+) place (\d+)( \(T\))?", d)
    if m:
        place = f"T{m.group(3)}" if m.group(4) else _ordinal(int(m.group(3)))
        return f"Individual {m.group(1)} · Flight {m.group(2)} · {place}"
    m = re.match(r"Ind (Net|Gross) place (\d+)( \(T\))?", d)
    if m:
        return f"Individual {m.group(1)} · {'T' + m.group(2) if m.group(3) else _ordinal(int(m.group(2)))}"
    m = re.match(r"(TEAM|CART) Net (\d+)\w* ?(\(T\))?", d)
    if m:
        place = f"T{m.group(2)}" if m.group(3) else _ordinal(int(m.group(2)))
        return f"{m.group(1).title()} Net · {place}"
    m = re.match(r"CTP hole (\d+)", d)
    if m:
        return f"Closest to the Pin · hole {m.group(1)}"
    return _e(d or category)


def event_facts(event_id: int, db_path=None) -> dict:
    """Everything the night's emails read, once."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        ev = dict(conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone())
        rounds = [dict(r) for r in conn.execute(
            "SELECT sr.*, ct.tee_name FROM scoring_rounds sr LEFT JOIN course_tees ct ON ct.tee_id = sr.tee_id "
            "WHERE sr.event_id = ? AND sr.customer_id IS NOT NULL", (int(event_id),)).fetchall()]
        cards = {}
        for r in rounds:
            holes = [dict(h) for h in conn.execute(
                "SELECT hole_number, strokes, strokes_received FROM scoring_holes "
                "WHERE scoring_round_id = ? ORDER BY hole_number", (r["id"],)).fetchall()]
            meta = {int(h["hole_number"]): h for h in db._ls_tee_holes(conn, r["tee_id"])} if r["tee_id"] else {}
            cards[int(r["customer_id"])] = {"round": r, "holes": holes, "meta": meta}
        tgf = conn.execute("SELECT id FROM tgf_events WHERE events_id = ? ORDER BY id DESC LIMIT 1",
                           (int(event_id),)).fetchone()
        pays = {}
        if tgf:
            for p in conn.execute("SELECT customer_id, category, amount, description FROM tgf_payouts "
                                  "WHERE event_id = ? AND customer_id IS NOT NULL", (tgf[0],)).fetchall():
                pays.setdefault(int(p["customer_id"]), []).append(dict(p))
        upcoming = [dict(r) for r in conn.execute(
            "SELECT * FROM events WHERE substr(event_date, 1, 10) > ? "
            "AND lower(COALESCE(status, 'active')) NOT IN ('cancelled', 'canceled') "
            "ORDER BY event_date, id", (str(ev["event_date"])[:10],)).fetchall()]
        reg = {}
        for u in upcoming:
            reg[u["id"]] = {int(x[0]) for x in conn.execute(
                "SELECT DISTINCT customer_id FROM items WHERE customer_id IS NOT NULL "
                "AND (event_id = ? OR lower(item_name) = lower(?)) "
                "AND lower(COALESCE(transaction_status, 'active')) NOT IN "
                "('credited','refunded','transferred','cancelled','wd','merged')",
                (u["id"], u["item_name"] or "")).fetchall()}
    ch = _chapter_key(ev)
    nxt = [u for u in upcoming if _chapter_key(u) in (ch, "tgf")][:3]
    pack = db.get_event_print_pack(int(event_id), db_path=db_path) or {}
    groups = {}
    for g in pack.get("groups") or []:
        names = [(p.get("customer_id"), p.get("name")) for p in g.get("players") or []]
        for cid, _ in names:
            if cid:
                groups[int(cid)] = {"group": g.get("group_num"), "start": g.get("start_line") or "",
                                    "mates": [n for c, n in names if c != cid]}
    hcp = {}
    try:
        for r in db.get_scoring_handicap_preview(ev["item_name"], db_path=db_path).get("rounds") or []:
            if r.get("customer_id"):
                hcp[int(r["customer_id"])] = r
    except Exception:
        logger.exception("results email: handicap preview failed for %s", ev.get("item_name"))
    race = {}
    if ch in FALL_RACE:
        try:
            data = db.get_points_race_standings(FALL_RACE[ch][0], db_path=db_path, no_network=True)
            race = {"rows": data.get("standings") or []}
        except Exception:
            logger.exception("results email: fall race unreadable")
    month = {}
    try:
        mk = str(ev["event_date"])[:7]
        # The saved snapshot the member page serves (never a Golf Genius fetch).
        for m in (db.load_gg_snapshot("monthly_points", db_path) or {}).get("months") or []:
            if m.get("month") == mk:
                month = m
    except Exception:
        logger.exception("results email: monthly points unreadable")
    return {"event": ev, "chapter": ch, "cards": cards, "payouts": pays, "next": nxt, "registered": reg,
            "groups": groups, "hcp": hcp, "race": race, "month": month, "db_path": db_path}


# ---------------------------------------------------------------------------
# The message
# ---------------------------------------------------------------------------

def _race_row(facts, cid):
    for r in (facts.get("race") or {}).get("rows") or []:
        if r.get("customer_id") == cid:
            return r
    return None


def _month_row(facts, cid):
    st = (facts.get("month") or {}).get("standings") or []
    for s in st:
        if s.get("customer_id") == cid:
            return s, (st[0] if st else None)
    return None, (st[0] if st else None)


def _points_card(facts, cid, chapter_label) -> tuple[str, bool]:
    """(html, bought_in) — empty html when the person is in neither standing."""
    ch = facts["chapter"]
    r = _race_row(facts, cid)
    m, leader = _month_row(facts, cid)
    items, lines = [], []
    enrolled = bool(r and r.get("enrolled"))
    if r and (r.get("total_points") or 0) > 0:
        rows = (facts.get("race") or {}).get("rows") or []
        top = max((x.get("total_points") or 0) for x in rows) if rows else 0
        behind = top - (r.get("total_points") or 0)
        sub = f"{_rank_text(r.get('rank'))} in {chapter_label}" + (f" · {behind:g} back" if behind > 0 else " · leading")
        items.append(("FALL RACE", f"{r['total_points']:g}", sub,
                      f"{BASE}/member/contests#race={FALL_RACE[ch][1]}&player={cid}"))
        if not enrolled:
            lines.append(f"Your {r['total_points']:g} fall points are being tallied but aren’t <b>active</b> yet. "
                         f"Buy in and they count toward the race payouts: "
                         f'<a href="{STORE_CONTESTS}" style="color:#2563eb;">activate my points</a>.')
    if m and (m.get("points") or 0) > 0:
        lead = (f"leader has {leader['points']:g}" if leader and leader.get("customer_id") != cid
                else "you lead")
        items.append(("OCTOBER" if str(facts["event"]["event_date"])[5:7] == "10"
                      else (facts["month"].get("name") or "THIS MONTH").upper(),
                      f"{m['points']:g}", f"{m.get('rank_label') or m.get('rank')} · {lead}",
                      f"{BASE}/member/contests#race=monthly&player={cid}"))
        purse = facts["month"].get("purse")
        if purse:
            lines.append(f"The month is automatic for every member: winner takes all, ${purse:g}.")
    if not items:
        return "", enrolled
    return card("YOUR POINTS", stat_row(items) + (note(" ".join(lines)) if lines else "")), enrolled


def _up_next(facts, cid) -> str:
    from email_parser.invitations import _display_name, _fmt_time
    rows, first_open = [], None
    for u in facts["next"]:
        d = date.fromisoformat(str(u["event_date"])[:10])
        when = d.strftime("%a %b %-d")
        t = _fmt_time(u.get("start_time"))
        if t:
            when += f" · {t}{' shotgun' if (u.get('start_type') or '').lower().startswith('shotgun') else ''}"
        url = (u.get("registration_url") or "").strip()
        mine = cid in facts["registered"].get(u["id"], set())
        tag = ("You’re signed up" if mine else
               ("You’re not signed up yet" if first_open is None and url else ""))
        if not mine and url and first_open is None:
            first_open = (u, url)
        color = GREEN if mine else ORANGE
        note_html = f'<div style="font-size:13px;color:{color};font-weight:bold;padding-top:2px;">{tag}</div>' if tag else ""
        reg = (f'<a href="{_e(url)}" style="display:inline-block;border:2px solid {ORANGE};border-radius:999px;'
               f'padding:6px 12px;color:{ORANGE};font:bold 12px Arial,sans-serif;letter-spacing:1px;'
               f'text-decoration:none;">REGISTER</a>') if (url and not mine) else ""
        rows.append(f'<tr><td style="padding:9px 0;border-top:1px solid {LINE};vertical-align:middle;">'
                    f'<div style="font-size:12px;color:{MUTED};letter-spacing:.5px;">{_e(when)}</div>'
                    f'<div style="font-size:16px;font-weight:bold;">{_e(_display_name(u))}</div>{note_html}</td>'
                    f'<td align="right" style="padding:9px 0;border-top:1px solid {LINE};vertical-align:middle;white-space:nowrap;">{reg}</td></tr>')
    if not rows:
        return ""
    out = card("UP NEXT", f'<table {T}>{"".join(rows)}</table>')
    if first_open:
        out += button(f"I’m in for {_e(_display_name(first_open[0]))}", first_open[1])
    return out


def _your_night(facts, cid, person) -> tuple[str, str]:
    c = facts["cards"][cid]
    r, holes, meta = c["round"], c["holes"], c["meta"]
    hn = [int(h["hole_number"]) for h in holes]
    pars = [int((meta.get(h) or {}).get("par") or 0) for h in hn]
    strokes = [h["strokes"] for h in holes]
    dots = [int(h["strokes_received"] or 0) for h in holes]
    gross = sum(s for s in strokes if s is not None)
    par_total = sum(p for p, s in zip(pars, strokes) if s is not None)
    net = gross - sum(d for d, s in zip(dots, strokes) if s is not None)
    ph = r.get("playing_handicap")
    ph_txt = f"PH {int(ph) if ph is not None and float(ph).is_integer() else ph}" if ph is not None else ""
    from email_parser import database as db
    pts = None
    try:
        dbp = facts.get("db_path")
        sc = db.get_scorecard(r["id"], db_path=dbp) if dbp else db.get_scorecard(r["id"])
        pts = (sc or {}).get("derived_totals", {}).get("game_stableford_net_after_plus")
    except Exception:
        pts = None
    stats = [("GROSS", f"{gross}", f"{_e(r.get('tee_name') or '')} tees · {_to_par(gross - par_total)}".strip(" ·")),
             ("NET", f"{net}", f"{_to_par(net - par_total)} · {ph_txt}".strip(" ·"))]
    if pts is not None:
        stats.append(("POINTS", f"{pts:g}", "net Stableford"))
    birdies = []
    for h, p, s in zip(hn, pars, strokes):
        if s is not None and p and s <= p - 1:
            yd = (meta.get(h) or {}).get("yardage")
            what = ("a hole-in-one" if s == 1 else
                    {2: "an eagle", 3: "an albatross"}.get(p - s, ""))
            label = f"a <b>{s} on the {f'{yd}-yard ' if yd else ''}{_ordinal(h)}</b>" + (f" ({what})" if what else "")
            birdies.append(label)
    skins = [x for x in facts["payouts"].get(cid, []) if (x.get("category") or "") == "skins"]
    hl = ""
    if birdies:
        hl = " The highlight" + ("s: " if len(birdies) > 1 else ": ") + ", ".join(birdies[:-1]) + \
             (" and " if len(birdies) > 1 else "") + birdies[-1] + "."
    legend = "Circle = birdie, box = double or worse" + \
             (f', <span style="color:{ORANGE};">&#9679;</span> = a handicap pop.' if any(d > 0 for d in dots) else ".")
    g = facts["groups"].get(cid) or {}
    sub = " · ".join(x for x in (
        f"Group {g['group']}" if g.get("group") else "",
        _e(g.get("start", "").split("|")[0].strip() + " start") if g.get("start") else "",
        f"with {_first_names(g.get('mates') or [])}" if g.get("mates") else "") if x)
    head = (f'<div style="{EYE}">YOUR NIGHT</div><div style="font:bold 26px/1.15 Georgia,serif;">{_e(person["name"])}</div>'
            + (f'<div style="font-size:14px;">{sub}</div>' if sub else ""))
    html = card(None, stat_row(stats) + '<div style="height:12px"></div>' + scorecard(hn, pars, strokes, dots)
                + note(legend + hl), head=head)
    pre_bits = []
    won = sum(float(x["amount"] or 0) for x in facts["payouts"].get(cid, []))
    if won > 0:
        pre_bits.append(f"you won ${won:,.2f}")
    if birdies:
        pre_bits.append(f"{len(birdies)} birdie{'s' if len(birdies) > 1 else ''} or better")
    return html, (f"{person['first_name']}, " + " and ".join(pre_bits) + "." if pre_bits else
                  f"{person['first_name']}, your card, handicap and points inside.")


def _winnings(facts, cid) -> str:
    rows = facts["payouts"].get(cid) or []
    if not rows:
        return ""
    total = sum(float(x["amount"] or 0) for x in rows)
    if total <= 0:
        return ""
    lines = [(_payout_label(x.get("category"), x.get("description")), f"${float(x['amount']):,.2f}") for x in rows]
    return card("YOUR WINNINGS", money_rows(lines, f"${total:,.2f}") +
                note("Paid by Venmo to the handle on file."))


def _handicap(facts, cid) -> str:
    h = facts["hcp"].get(cid)
    if not h or h.get("hcp_excluded") or h.get("differential_ndb") is None:
        return ""
    if h.get("index_now") is None:
        items = [("THIS ROUND", f"{h['differential_ndb']:.1f}", "differential")]
        extra = "Your TGF index is still being established."
    else:
        items = [("INDEX", f"{h['index_now']:.1f} → {h['index_after_ndb']:.1f}", "nine-hole, after this round"),
                 ("THIS ROUND", f"{h['differential_ndb']:.1f}", "differential")]
        extra = ""
    capped = h.get("capped_holes") or 0
    if capped:
        extra += (" " if extra else "") + f"{capped} hole{'s' if capped > 1 else ''} counted at net double bogey."
    link = f'<a href="{BASE}/member/spotlight?player={cid}" style="color:#2563eb;">Your Spotlight</a> has every round.'
    return card("YOUR HANDICAP", stat_row(items) + note((extra + " " if extra else "") + link))


def build_message(facts: dict, person: dict, recap_file: str) -> dict:
    """{subject, html, preheader, played, held: [reasons]}."""
    ev, ch = facts["event"], facts["chapter"]
    cid = int(person["customer_id"])
    from email_parser.invitations import _display_name
    course = _display_name(ev)
    d = date.fromisoformat(str(ev["event_date"])[:10])
    chapter_label = FALL_RACE.get(ch, (None, None, (ev.get("chapter") or "").title()))[2]
    eyebrow = f"{chapter_label.upper()} · {d.strftime('%a %b %-d').upper()}"
    played = cid in facts["cards"]
    pts_html, enrolled = _points_card(facts, cid, chapter_label)
    section = chapter_label.upper()
    try:
        story = recap_story(recap_file, section, enrolled=enrolled)
    except Exception as e:
        return {"held": [f"recap section {section} unreadable in {recap_file}: {e}"]}
    parts = [f'<p style="margin:0 0 14px;">Good morning, {_e(person["first_name"])}!</p>']
    if played:
        night, pre = _your_night(facts, cid, person)
        parts += [f'<p style="margin:0 0 18px;">Here’s your night at {_e(course)}, then the recap and what’s next.</p>',
                  night, _winnings(facts, cid), _handicap(facts, cid), pts_html,
                  button(f"See full results from {_e(course)}", f"{BASE}/member/results/{ev['id']}"),
                  button("Your Spotlight", f"{BASE}/member/spotlight?player={cid}", solid=False)]
        title = f"{ev['item_name']} — your results"
    else:
        day = d.strftime("%A")
        parts += [f'<p style="margin:0 0 18px;">We missed you at {_e(course)} {day}. '
                  f'{"Here’s where you stand, what happened, and what’s next." if pts_html else "Here’s what happened and what’s next."}</p>',
                  pts_html,
                  button(f"See full results from {_e(course)}", f"{BASE}/member/results/{ev['id']}", solid=False)]
        pre = f"{person['first_name']}, here’s {day}’s recap from {course} and what’s next."
        title = f"{ev['item_name']} — the results"
    parts += [f'<div style="{EYE}color:{ORANGE};padding:18px 0 6px;border-top:2px solid {ORANGE};margin-top:14px;">THE RECAP</div>',
              story, '<div style="height:18px"></div>', _up_next(facts, cid),
              f'<p style="margin:18px 0 0;">{_see_you(facts)}<br><br>{SIGNATURES.get(ch, "The Golf Fellowship")}</p>',
              f'<p style="margin:18px 0 0;font-size:12px;color:{MUTED};">You’re getting this as a TGF {chapter_label} player. '
              f'Reply to this email if you’d rather not get results emails.</p>']
    html = frame(eyebrow, title, "".join(p for p in parts if p), pre)
    return {"subject": f"TGF Results | {title}", "html": html, "preheader": pre, "played": played,
            "held": lint(html)}


def _see_you(facts) -> str:
    own = [u for u in facts["next"] if _chapter_key(u) == facts["chapter"]]
    if not own:
        return "See you soon!"
    return f"See you next {date.fromisoformat(str(own[0]['event_date'])[:10]).strftime('%A')}!"


def lint(html: str) -> list:
    """Anything that must never reach a member."""
    bad = []
    text = re.sub(r"<style[\s\S]*?</style>", "", html)
    for pat, why in ((r"\[__", "a [__ blank __]"), (r"\[BLANK\]", "a [BLANK]"),
                     (r"\[\[[^\]]+\]\]", "an unrendered [[name|id]] link"),
                     (r"%first_name%|\{[a-z_]+\}", "a leftover template tag"),
                     (r">\s*None\s*<|\bNone\b ·|· None\b", "a 'None'"), (r"\bnan\b", "a 'nan'")):
        if re.search(pat, text):
            bad.append(f"contains {why}")
    return bad


# ---------------------------------------------------------------------------
# Who gets it
# ---------------------------------------------------------------------------

def audience(event_id: int, db_path=None) -> dict:
    """Players of the event + the chapter's members + played the chapter in
    12 months, minus the invitation exclusions. Read-only."""
    from email_parser import database as db
    from email_parser import invitations as inv
    conn = db.get_connection(db_path)
    try:
        ev = inv._event(conn, event_id)
        if not ev:
            return {"error": f"event {event_id} not found"}
        chapters = inv.audience_chapters(ev.get("chapter"))
        why: dict = {}
        for cid, in conn.execute("SELECT DISTINCT customer_id FROM scoring_rounds WHERE event_id = ? "
                                 "AND customer_id IS NOT NULL", (int(event_id),)).fetchall():
            why.setdefault(int(cid), set()).add("played")
        for chapter in chapters:
            ch = conn.execute("SELECT chapter_id FROM chapters WHERE lower(name) = lower(?)", (chapter,)).fetchone()
            st = ",".join("?" * len(inv.ACTIVE_STATUSES))
            for r in conn.execute(
                    f"SELECT customer_id FROM customers WHERE current_player_status IN ({st}) "
                    "AND (home_chapter_id = ? OR (home_chapter_id IS NULL AND lower(chapter) = lower(?)))",
                    (*inv.ACTIVE_STATUSES, ch[0] if ch else None, chapter)).fetchall():
                why.setdefault(int(r[0]), set()).add("member")
            since = (date.fromisoformat(str(ev["event_date"])[:10]) - timedelta(days=inv.LOOKBACK_DAYS)).isoformat()
            for r in conn.execute(
                    "SELECT DISTINCT i.customer_id FROM items i JOIN events e "
                    "ON (i.event_id = e.id OR lower(i.item_name) = lower(e.item_name)) "
                    "WHERE i.customer_id IS NOT NULL AND lower(e.chapter) = lower(?) "
                    "AND substr(e.event_date, 1, 10) >= ? AND substr(e.event_date, 1, 10) <= ? "
                    "AND lower(COALESCE(i.transaction_status, 'active')) NOT IN "
                    f"({','.join('?' * len(inv.INACTIVE_ITEM))})",
                    (chapter, since, str(ev["event_date"])[:10], *inv.INACTIVE_ITEM)).fetchall():
                why.setdefault(int(r[0]), set()).add("played_12mo")
        excluded = {"opted_out": 0, "membership_remove": 0, "non_member": 0, "other_chapter": 0, "no_email": 0}
        own = {c.lower() for c in chapters}
        home = {int(r[0]): (r[1] or "").strip() for r in conn.execute(
            "SELECT c.customer_id, lower(COALESCE(ch.name, c.chapter, '')) FROM customers c "
            "LEFT JOIN chapters ch ON ch.chapter_id = c.home_chapter_id").fetchall()}
        optout = inv._opted_out(db_path)
        try:
            removed = {int(r[0]) for r in conn.execute(
                "SELECT DISTINCT customer_id FROM customer_memberships WHERE roster_choice = 'remove'").fetchall()}
        except Exception:
            removed = set()
        try:
            from email_parser.course_staff import non_member_ids
            nonmem = non_member_ids(conn)
        except Exception:
            nonmem = set(db.vendor_customer_ids(conn))
        people = []
        for cid in sorted(why):
            played = "played" in why[cid]
            if cid in optout:
                excluded["opted_out"] += 1; continue
            if cid in removed and not played:
                excluded["membership_remove"] += 1; continue
            if cid in nonmem:
                excluded["non_member"] += 1; continue
            if not played and home.get(cid) in inv.CHAPTER_EVENTS and home.get(cid) not in own:
                excluded["other_chapter"] += 1; continue
            email = inv._send_email(conn, cid)
            if not email:
                excluded["no_email"] += 1; continue
            c = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?", (cid,)).fetchone()
            first = ((c["first_name"] if c else "") or "").strip()
            name = " ".join(x for x in ((c["first_name"] if c else ""), (c["last_name"] if c else "")) if x).strip()
            people.append({"customer_id": cid, "name": name or f"#{cid}", "first_name": first or "there",
                           "email": email, "played": played, "why": sorted(why[cid])})
        return {"event": {"id": ev["id"], "name": ev["item_name"], "chapter": ev.get("chapter")},
                "people": people,
                "counts": {"recipients": len(people), "played": sum(p["played"] for p in people),
                           "excluded": excluded}}
    finally:
        conn.close()


def night_plan(event_ids: list, db_path=None) -> dict:
    """One email per person across the night's events: a player gets the
    event he played; anyone else gets his home chapter's (else the first)."""
    auds = {int(e): audience(int(e), db_path) for e in event_ids}
    errors = {e: a["error"] for e, a in auds.items() if a.get("error")}
    by_cid: dict = {}
    for e, a in auds.items():
        for p in a.get("people") or []:
            cur = by_cid.get(p["customer_id"])
            if cur is None or (p["played"] and not cur[1]["played"]):
                by_cid[p["customer_id"]] = (e, p)
    plan: dict = {e: [] for e in auds}
    for e, p in by_cid.values():
        plan[e].append(p)
    return {"plan": plan, "errors": errors,
            "counts": {e: {"recipients": len(v), "played": sum(p["played"] for p in v)} for e, v in plan.items()}}


# ---------------------------------------------------------------------------
# Guards, preview, send, schedule
# ---------------------------------------------------------------------------

def guards(event_id: int, db_path=None) -> list:
    """Every reason the event's emails must wait. Empty = clear to send."""
    from email_parser import database as db
    from email_parser.card_parity import engine_card_parity, blocking_reason
    from email_parser.closeout_checks import closeout_final_check
    out = []
    f = closeout_final_check(int(event_id), db_path=db_path)
    if f.get("error"):
        out.append(f["error"])
    elif not f.get("final"):
        out += [f"not final: {b}" for b in f.get("blocking") or []] or ["results are not final"]
    why = blocking_reason(engine_card_parity(int(event_id), db_path=db_path))
    if why:
        out.append(why)
    try:
        with db._connect(db_path) as conn:
            name = conn.execute("SELECT item_name FROM events WHERE id = ?", (int(event_id),)).fetchone()[0]
            tgf = conn.execute("SELECT id FROM tgf_events WHERE events_id = ? ORDER BY id DESC LIMIT 1",
                               (int(event_id),)).fetchone()
            recorded = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM tgf_payouts WHERE event_id = ?",
                                    (tgf[0],)).fetchone()[0] if tgf else 0
        asm = db.assemble_event_game_payouts(name, db_path=db_path)
        if asm.get("error"):
            out.append(f"payouts: {asm['error']}")
        elif round(float(recorded or 0), 2) != round(float(asm.get("total") or 0), 2):
            out.append(f"recorded payouts ${float(recorded or 0):,.2f} differ from the engine's "
                       f"${float(asm.get('total') or 0):,.2f}")
    except Exception as e:
        out.append(f"payout check failed: {e}")
    return out


def _preview_allowed(to: list, db_path=None) -> list:
    """Addresses NOT allowed for a preview: staff, or a chapter manager's own."""
    from email_parser import database as db
    from email_parser.recap_mail import staff_only
    bad = staff_only(to, lambda k: _setting(k, db_path))
    if not bad:
        return []
    mgr_ids = {m.get("customer_id") for m in (db.get_chapter_managers(db_path=db_path) or {}).values()
               if m.get("customer_id")}
    ok = set()
    with db._connect(db_path) as conn:
        for cid in mgr_ids:
            ok |= {(r[0] or "").lower() for r in conn.execute(
                "SELECT email FROM customer_emails WHERE customer_id = ?", (int(cid),)).fetchall()}
    return [a for a in bad if a.lower() not in ok]


def preview(event_id: int, customer_id: int, recap_file: str, to_address: str | None = None,
            send: bool = False, db_path=None) -> dict:
    """Build ONE person's email. With send=True it goes to `to_address`
    (default: that person's own address on record), staff or a chapter
    manager's own address only."""
    from email_parser.event_day_email import _creds, _graph_send
    from email_parser.recap_mail import _addrs
    from email_parser import invitations as inv
    from email_parser import database as db
    facts = event_facts(event_id, db_path)
    conn = db.get_connection(db_path)
    try:
        email = inv._send_email(conn, int(customer_id))
        c = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                         (int(customer_id),)).fetchone()
    finally:
        conn.close()
    person = {"customer_id": int(customer_id), "first_name": (c["first_name"] or "there") if c else "there",
              "name": " ".join(x for x in ((c["first_name"], c["last_name"]) if c else ()) if x) or f"#{customer_id}",
              "email": email}
    msg = build_message(facts, person, recap_file)
    out = {"customer_id": customer_id, "subject": msg.get("subject"), "played": msg.get("played"),
           "held": msg.get("held"), "guards": guards(event_id, db_path), "html_chars": len(msg.get("html") or "")}
    if not send:
        out["html"] = msg.get("html")
        return out
    to = _addrs(to_address) or ([email] if email else [])
    bad = _preview_allowed(to, db_path)
    if not to or bad:
        return {**out, "error": f"a preview goes to staff or a chapter manager's own address; refused {bad or 'no address'}"}
    if msg.get("held"):
        return {**out, "error": "held: " + "; ".join(msg["held"])}
    creds = _creds()
    if not creds:
        return {**out, "error": "Email credentials not configured on server"}
    ok = _graph_send(creds, ",".join(to), f"PREVIEW: {msg['subject']}", msg["html"])
    return {**out, "status": "sent" if ok else "failed", "to": to}


def deliver(event_ids: list, recap_file: str, confirm: bool = False, db_path=None) -> dict:
    """THE MEMBER SEND for one night. Guards first (any failure holds every
    event's emails), then once per person per event."""
    from email_parser import database as db
    from email_parser.event_day_email import _creds, _graph_send
    held = {e: guards(int(e), db_path) for e in event_ids}
    held = {e: g for e, g in held.items() if g}
    pl = night_plan(event_ids, db_path)
    if pl["errors"]:
        held.update({e: [w] for e, w in pl["errors"].items()})
    res = {"events": event_ids, "counts": pl["counts"], "held_events": held}
    if held:
        return {**res, "state": "held"}
    facts = {int(e): event_facts(int(e), db_path) for e in event_ids}
    msgs, bad = {}, []
    for e, people in pl["plan"].items():
        for p in people:
            m = build_message(facts[int(e)], p, recap_file)
            if m.get("held"):
                bad.append({"customer_id": p["customer_id"], "name": p["name"], "why": m["held"]})
            else:
                msgs[(int(e), p["customer_id"])] = (p, m)
    if bad:
        return {**res, "state": "held", "held_messages": bad}
    if not confirm:
        return {**res, "state": "dry_run", "would_send": len(msgs)}
    creds = _creds()
    if not creds:
        return {**res, "state": "error", "error": "Email credentials not configured on server"}
    sent, failed, skipped = [], [], 0
    for (e, cid), (p, m) in msgs.items():
        key = SENT_KEY.format(event_id=e)
        done = _json_setting(key, db_path)
        if str(cid) in done:
            skipped += 1
            continue
        ok = False
        try:
            ok = _graph_send(creds, p["email"], m["subject"], m["html"])
        except Exception:
            logger.exception("results email failed for cid %s", cid)
        (sent if ok else failed).append(cid)
        if ok:
            done[str(cid)] = datetime.utcnow().isoformat(timespec="seconds")
            db.set_app_setting(key, json.dumps(done), db_path=db_path)
        try:
            db.log_message({"event_name": facts[e]["event"]["item_name"], "channel": "email",
                            "recipient_name": p["name"], "recipient_address": p["email"],
                            "subject": m["subject"],
                            "body_preview": f"results email ({'played' if p['played'] else 'recap'})",
                            "status": "sent" if ok else "failed", "sent_by": "results_email"}, db_path=db_path)
        except Exception:
            pass
    return {**res, "state": "sent", "sent": len(sent), "failed": failed, "already_sent": skipped}


def schedule_send(event_ids: list, at: str, recap_file: str, authority: str, db_path=None) -> dict:
    """Schedule the night's send at `at` (YYYY-MM-DDTHH:MM, Central)."""
    from email_parser import database as db
    datetime.fromisoformat(at)
    if not (RECAP_DIR / recap_file).exists():
        return {"error": f"no recap file {recap_file}"}
    sch = _json_setting(SCHEDULE_KEY, db_path)
    key = ",".join(str(int(e)) for e in event_ids)
    sch[key] = {"at": at, "recap": recap_file, "authority": authority, "state": "scheduled"}
    db.set_app_setting(SCHEDULE_KEY, json.dumps(sch), db_path=db_path)
    return {"scheduled": key, **sch[key]}


def auto_check(now: datetime | None = None, db_path=None) -> dict:
    """Every minute: send any scheduled night whose time has come. A held
    night is retried each run and raises one COO item."""
    from email_parser import database as db
    from email_parser.timezone_utils import now_central
    now = now or now_central()
    sch = _json_setting(SCHEDULE_KEY, db_path)
    out = {}
    for key, s in sch.items():
        if s.get("state") in ("sent", "cancelled") or datetime.fromisoformat(s["at"]) > now:
            continue
        # A held night is re-checked every 10 minutes, not every minute.
        if s.get("state") == "held" and s.get("last_try") and \
                datetime.fromisoformat(s["last_try"]) > now - timedelta(minutes=10):
            continue
        ids = [int(x) for x in key.split(",")]
        r = deliver(ids, s["recap"], confirm=True, db_path=db_path)
        out[key] = {k: r.get(k) for k in ("state", "sent", "failed", "held_events", "held_messages")}
        sch = _json_setting(SCHEDULE_KEY, db_path)
        if r.get("state") == "sent" and not r.get("failed"):
            sch[key]["state"] = "sent"
            sch[key]["sent_at"] = now.isoformat(timespec="minutes")
        elif r.get("state") == "held":
            sch[key]["state"] = "held"
            try:
                db.save_action_item({
                    "subject": f"RESULTS EMAIL HELD: events {key}",
                    "from_name": "Results email",
                    "summary": json.dumps({"held_events": r.get("held_events"),
                                           "held_messages": r.get("held_messages")}, default=str)[:3000],
                    "urgency": "high", "category": "scoring"}, db_path=db_path)
            except Exception:
                logger.exception("results email hold alarm failed")
        sch[key]["last_run"] = out[key]
        sch[key]["last_try"] = now.isoformat(timespec="seconds")
        db.set_app_setting(SCHEDULE_KEY, json.dumps(sch, default=str), db_path=db_path)
    return out
