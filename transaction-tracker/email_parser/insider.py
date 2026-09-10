"""TGF Insider — the Wednesday-morning public recap, auto-drafted into Brevo.

Kerry-ratified via CA (mailbox #381, 2026-09-02), routed to the closeout
lane 2026-09-10 (#453). Process of record: Wednesday AM the Tracker fills
`docs/claude/templates/public-recap-template.html` from last Tuesday's
events (both chapters), creates a Brevo DRAFT (never sends), and emails
Kerry the draft. He edits on his phone and sends Wednesday afternoon.

Rules folded in (event-recaps.md, public variant):
  * money is PROOF, not the promise — "% cashed" is one line in the box;
  * guests / new members are first name + last initial;
  * never "league", POT not purse, no TGF Plus, no DFW / Houston;
  * the ONLY dollar figures are the ratified offer line (in the template)
    and the live Hole-In-One pot (Kerry's own block);
  * recipients = list 3 minus segment 2 (Active members) — proven shape;
  * DRAFTS ONLY.

Bridge: `scoring-brevo-draft[:dry|apply|review]`. Scheduler: Wednesday
13:00 UTC (`weekly_insider_draft`). Dial `insider_autodraft`: draft
(default — Brevo DRAFT + link to Kerry, who reviews it in Brevo and edits
with the session lane), review (preview to Kerry + mailbox, nothing in
Brevo), off. Skipped when no event was played in the window.
"""

from __future__ import annotations

import html as _html
import json
import logging
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from .brevo import BREVO_API, _api_key, _headers
from .event_links import derive_store_url
from .timezone_utils import today_central

logger = logging.getLogger(__name__)

TEMPLATE_PATH = (Path(__file__).resolve().parent.parent
                 / "docs" / "claude" / "templates" / "public-recap-template.html")

# GG results pages per chapter (template comment, Kerry 9/2/26):
#   <portal>/pages/<page>?round_id=<gg league round id>
RESULTS_PAGES = {
    "San Antonio": "https://tgf-sa.golfgenius.com/pages/5783307",
    "Austin": "https://tgf-austin.golfgenius.com/pages/5790752",
}
CHAPTERS = ("San Antonio", "Austin")
LIST_ID = 3               # "TGF CONTACTS"
EXCLUDE_SEGMENT_ID = 2    # "Active members"
SENDER_ID = 1             # kerry@
CAMPAIGN_TAG = "public-recap"
BANNED_WORDS = ("league", "purse", "TGF Plus", "DFW", "Houston")

_NINE_RE = re.compile(r"^[sa]9\.\d+", re.I)
_EIGHTEEN_RE = re.compile(r"^[sa]18\.\d+", re.I)


# ── helpers ─────────────────────────────────────────────────────────────

def _esc(s) -> str:
    return _html.escape(str(s or ""), quote=False)


def _short_name(first: str | None, last: str | None) -> str:
    """Public-send name: first name + last initial (Kannon B.)."""
    first = (first or "").strip()
    last = (last or "").strip()
    if not first and not last:
        return "a first-timer"
    return f"{first} {last[:1]}.".strip() if last else first


def _gg_short(name: str | None) -> str:
    """GG board name ("DONOVAN, Tom", "Espinosa, Christopher Guest") →
    public form "Tom D."."""
    raw = re.sub(r"\s+Guest\b", "", name or "", flags=re.I).strip()
    if "," in raw:
        last, first = [x.strip() for x in raw.split(",", 1)]
    else:
        parts = raw.split()
        first, last = (" ".join(parts[:-1]), parts[-1]) if len(parts) > 1 else (raw, "")
    first = first.split()[0].title() if first else ""
    return _short_name(first, last.title())


def _fmt_day(d: str | None) -> str:
    try:
        dt = datetime.strptime((d or "")[:10], "%Y-%m-%d")
    except ValueError:
        return d or ""
    return f"{dt.strftime('%a')} {dt.strftime('%b')} {dt.day}"


def _fmt_money(v) -> str:
    try:
        return f"${float(v):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _link(url: str, text: str) -> str:
    return (f'<a href="{_esc(url)}" style="color:#e2773d;font-weight:bold;">'
            f'{_esc(text)}</a>')


def _cap(s: str) -> str:
    """Upper-case the first letter only (str.capitalize lower-cases the rest,
    which turned 'San Antonio' into 'san antonio')."""
    return s[:1].upper() + s[1:] if s else s


def _fraction_phrase(n: int, m: int) -> str:
    if not m:
        return ""
    r = n / m
    if r >= 0.66:
        return "nearly two-thirds of the field"
    if r >= 0.5:
        return "half the field"
    if r >= 0.33:
        return "a third of the field"
    return f"{n} of {m} players"


# ── data ────────────────────────────────────────────────────────────────

def gather_week(db_path=None, as_of: date | None = None, days: int = 7) -> dict:
    """Everything the template needs, from Tracker data only.

    Events: for each chapter, the most recent event WITH SCORECARDS played
    inside the window (a Tuesday nine normally; an 18 counts too). Then
    the live HIO pot, the next Tuesday per chapter, and the upcoming
    Saturday 18s.
    """
    from . import database as db
    as_of = as_of or today_central()
    since = (as_of - timedelta(days=days)).isoformat()
    out: dict = {"as_of": as_of.isoformat(), "since": since, "events": [],
                 "next_tuesday": {}, "saturdays": [], "hio_pot": None}
    with db._connect(db_path) as conn:
        played = [dict(r) for r in conn.execute(
            """SELECT e.id, e.item_name, e.event_date, e.course, e.chapter,
                      e.fellowship_spot,
                      COUNT(sr.id) AS cards
                 FROM events e
                 JOIN scoring_rounds sr ON sr.event_id = e.id
                WHERE e.event_date >= ? AND e.event_date <= ?
                GROUP BY e.id
               HAVING cards > 0
                ORDER BY e.event_date DESC""",
            (since, as_of.isoformat())).fetchall()]
        seen_chapters: set = set()
        for ev in played:
            ch = ev["chapter"] or ""
            if ch in seen_chapters or ch not in CHAPTERS:
                continue
            seen_chapters.add(ch)
            eid = ev["id"]
            # Field + cashed (distinct payout recipients through tgf_events.events_id).
            field = ev["cards"]
            cashed = conn.execute(
                """SELECT COUNT(DISTINCT p.customer_id)
                     FROM tgf_payouts p JOIN tgf_events te ON te.id = p.event_id
                    WHERE te.events_id = ?""", (eid,)).fetchone()[0] or 0
            cashed_ids = {r[0] for r in conn.execute(
                """SELECT DISTINCT p.customer_id
                     FROM tgf_payouts p JOIN tgf_events te ON te.id = p.event_id
                    WHERE te.events_id = ?""", (eid,))}
            # First-timers: players who PLAYED (have a card) and registered
            # as "1st TIMER" for this event. The tag is what the player said
            # at checkout; the no-earlier-card heuristic is only the fallback
            # for an event with no store items (scorecards only go back so
            # far, so it over-counts on real data).
            n_items = conn.execute(
                "SELECT COUNT(*) FROM items WHERE event_id = ? "
                "AND COALESCE(transaction_status,'active') = 'active'", (eid,)).fetchone()[0]
            if n_items:
                firsts = [dict(r) for r in conn.execute(
                    """SELECT DISTINCT sr.customer_id, c.first_name, c.last_name,
                              sr.gross, sr.net, sr.playing_handicap
                         FROM scoring_rounds sr
                         JOIN customers c ON c.customer_id = sr.customer_id
                         JOIN items i ON i.customer_id = sr.customer_id
                                     AND i.event_id = sr.event_id
                        WHERE sr.event_id = ? AND sr.customer_id IS NOT NULL
                          AND COALESCE(i.transaction_status,'active') = 'active'
                          AND UPPER(COALESCE(i.user_status,'')) LIKE '1ST%'
                        ORDER BY c.last_name, c.first_name""", (eid,))]
            else:
                firsts = [dict(r) for r in conn.execute(
                    """SELECT sr.customer_id, c.first_name, c.last_name,
                              sr.gross, sr.net, sr.playing_handicap
                         FROM scoring_rounds sr
                         JOIN customers c ON c.customer_id = sr.customer_id
                        WHERE sr.event_id = ? AND sr.customer_id IS NOT NULL
                          AND sr.round_date = (SELECT MIN(round_date) FROM scoring_rounds x
                                                WHERE x.customer_id = sr.customer_id)
                        ORDER BY c.last_name, c.first_name""", (eid,))]
            for f in firsts:
                f["cashed"] = f["customer_id"] in cashed_ids
                f["short"] = _short_name(f["first_name"], f["last_name"])
            # Handicap spread of the players who cashed (fairness proof).
            hcp = conn.execute(
                """SELECT MIN(sr.playing_handicap), MAX(sr.playing_handicap)
                     FROM scoring_rounds sr
                    WHERE sr.event_id = ? AND sr.customer_id IN (
                          SELECT p.customer_id FROM tgf_payouts p
                            JOIN tgf_events te ON te.id = p.event_id
                           WHERE te.events_id = ?)""", (eid, eid)).fetchone()
            # GG boards: a par or bogey that won a skin is the story.
            results = [dict(r) for r in conn.execute(
                """SELECT game, game_label, player_name, detail, purse, gg_round_id,
                          customer_id
                     FROM gg_game_results WHERE event_id = ?""", (eid,))]
            round_id = next((r["gg_round_id"] for r in results if r.get("gg_round_id")),
                            None)
            if not round_id:
                rr = conn.execute(
                    "SELECT gg_league_round_id FROM scoring_rounds WHERE event_id = ? "
                    "AND gg_league_round_id IS NOT NULL LIMIT 1", (eid,)).fetchone()
                round_id = rr[0] if rr else None
            skins_story = None
            for r in results:
                d = (r.get("detail") or "").lower()
                if "skin" in (r.get("game") or "").lower() or "skin" in (r.get("game_label") or "").lower():
                    m = re.search(r"\b(bogey|par)\b[^0-9]*?(\d{1,2})", d)
                    if m and (skins_story is None or m.group(1) == "bogey"):
                        skins_story = {"score": m.group(1), "hole": int(m.group(2)),
                                       "player": r["player_name"]}
            base = RESULTS_PAGES.get(ch)
            out["events"].append({
                "id": eid, "name": ev["item_name"], "date": ev["event_date"],
                "course": ev["course"], "chapter": ch, "field": field,
                "cashed": cashed, "first_timers": firsts,
                "hcp_min": hcp[0] if hcp else None, "hcp_max": hcp[1] if hcp else None,
                "skins_story": skins_story,
                "fellowship_spot": ev["fellowship_spot"],
                "results_url": (f"{base}?round_id={round_id}" if base and round_id
                                else base),
                "holes": 18 if _EIGHTEEN_RE.match(ev["item_name"] or "") else 9,
            })
        # Next Tuesday nine per chapter + Saturday 18s ahead.
        future = [dict(r) for r in conn.execute(
            """SELECT id, item_name, event_date, course, chapter, start_time,
                      registration_url
                 FROM events
                WHERE event_date > ? AND COALESCE(status, 'active') NOT IN ('cancelled', 'canceled')
                ORDER BY event_date""", (as_of.isoformat(),))]
        for ev in future:
            ch = ev["chapter"] or ""
            url = ev.get("registration_url") or derive_store_url(ev["item_name"])
            if _NINE_RE.match(ev["item_name"] or "") and ch in CHAPTERS \
                    and ch not in out["next_tuesday"]:
                out["next_tuesday"][ch] = {
                    "name": ev["item_name"], "course": ev["course"],
                    "date": ev["event_date"], "url": url,
                    "label": f"{ev['course'] or ev['item_name']} · {_fmt_day(ev['event_date'])}",
                }
            elif _EIGHTEEN_RE.match(ev["item_name"] or "") and len(out["saturdays"]) < 4 \
                    and ev["event_date"] <= (as_of + timedelta(days=45)).isoformat():
                out["saturdays"].append({
                    "name": ev["item_name"], "course": ev["course"], "chapter": ch,
                    "date": ev["event_date"], "url": url,
                })
    try:
        pot = db.get_hio_pot(db_path=db_path)
        out["hio_pot"] = pot.get("pot") if isinstance(pot, dict) else None
    except Exception:
        logger.warning("insider: HIO pot unavailable", exc_info=True)
    return out


def handicap_distribution(db_path=None) -> dict:
    """The "Am I good enough to play?" facts (Kerry 2026-09-10): the spread
    of established TGF handicap indexes across current members, as 18-hole
    equivalents (index_18 = 2 × the 9-hole index the board carries).
    Members = active_member / member_plus with an established index."""
    from . import database as db
    players = db.get_all_handicap_players(db_path=db_path)
    rows = [p for p in players
            if p.get("handicap_index") is not None
            and (p.get("player_status") or "") in ("active_member", "member_plus")]
    idx = sorted(p["handicap_index_18"] for p in rows)
    n = len(idx)

    def pct(k):  # share of members at or above k (18-hole index)
        return round(100 * sum(1 for v in idx if v >= k) / n) if n else 0

    def q(f):
        return idx[min(n - 1, int(f * (n - 1)))] if n else None

    bands = [("0–5", 0, 5), ("5–10", 5, 10), ("10–15", 10, 15),
             ("15–20", 15, 20), ("20–25", 20, 25), ("25+", 25, 999)]
    by_band = {lab: sum(1 for v in idx if lo <= v < hi) for lab, lo, hi in bands}
    return {
        "members_with_index": n,
        "members_total": sum(1 for p in players
                             if (p.get("player_status") or "") in ("active_member", "member_plus")),
        "min": idx[0] if n else None, "max": idx[-1] if n else None,
        "median": q(0.5), "q1": q(0.25), "q3": q(0.75),
        "pct_10_plus": pct(10), "pct_15_plus": pct(15), "pct_20_plus": pct(20),
        "single_digit": sum(1 for v in idx if v < 10),
        "by_band": by_band,
        "by_chapter": {ch: sorted(p["handicap_index_18"] for p in rows if p.get("chapter") == ch)
                       for ch in CHAPTERS},
    }


# ── copy ────────────────────────────────────────────────────────────────

def compose(data: dict) -> dict:
    """Turn the gathered facts into the template's slots. Deterministic
    sentences; every proper noun that has a page is linked; nothing a
    named member could read as a dig."""
    evs = data["events"]
    by_ch = {e["chapter"]: e for e in evs}
    when = "Tuesday night" if all(e["holes"] == 9 for e in evs) else "This week"
    when_mid = when if when.startswith("Tuesday") else "this week"   # mid-sentence form
    monday = (datetime.strptime(data["as_of"], "%Y-%m-%d").date()
              - timedelta(days=datetime.strptime(data["as_of"], "%Y-%m-%d").weekday()))
    slots = {"EYEBROW": f"TGF Insider · Week of {monday.strftime('%B')} {monday.day}"}

    # Lede.
    parts = []
    for ch in CHAPTERS:
        e = by_ch.get(ch)
        if e:
            parts.append(f"<strong>{_esc(ch)} at {_esc(e['course'] or e['name'])}</strong>"
                         + (f" ({_link(e['results_url'], 'RESULTS')})" if e["results_url"] else ""))
    if len(parts) == 2:
        lede = (f"{when} both of our cities were on the tee — {parts[0]}, {parts[1]}. "
                "Three things happened that say more about TGF than any brochure could.")
    elif parts:
        lede = f"{when} we were on the tee — {parts[0]}. Three things worth telling."
    else:
        lede = "A quiet week on the tee sheet, and three things worth telling anyway."
    slots["LEDE_WITH_RESULTS_LINKS"] = lede

    # Beat 1 — money as proof (fraction, not dollars).
    cashed_lines = []
    total_c = total_f = 0
    for ch in CHAPTERS:
        e = by_ch.get(ch)
        if e and e["field"]:
            cashed_lines.append(f"{e['cashed']} of {e['field']} players in {ch}")
            total_c += e["cashed"]
            total_f += e["field"]
    if cashed_lines:
        slots["BEAT_1_LEAD"] = (f"{_cap(_fraction_phrase(total_c, total_f))} went home "
                                f"with money.")
        slots["BEAT_1_BODY"] = (_cap(" and ".join(cashed_lines))
                                + " cashed something Tuesday — a skin, a closest-to-pin, "
                                  "a share of a team pot. Your own ball, your own handicap, "
                                  "your own shot at it.")
    else:
        slots["BEAT_1_LEAD"] = "Money went home in both cities."
        slots["BEAT_1_BODY"] = ("Skins, closest-to-pin, team pots — every game is optional, "
                                "and every one of them paid somebody who is not a scratch golfer.")

    # Beat 2 — first-timers.
    firsts = [f for e in evs for f in e["first_timers"]]
    cashed_firsts = [f for f in firsts if f["cashed"]]
    if cashed_firsts:
        f = cashed_firsts[0]
        others = len(firsts) - 1
        k = len(cashed_firsts) - 1          # the other first-timers who cashed
        if others and k >= 1:
            tail = (f" — and so did {k} of the other {others} first-timer"
                    f"{'s' if others != 1 else ''} on the sheet.")
        elif others:
            tail = f" — one of {len(firsts)} first-timers on the sheet."
        else:
            tail = "."
        slots["BEAT_2_LEAD"] = "First round, first payday."
        slots["BEAT_2_BODY"] = (f"{_esc(f['short'])} teed it up with us for the first time "
                                f"{when_mid} and left with money" + tail
                                + " Nobody gets a special tee. Everybody gets a fair game.")
    elif firsts:
        slots["BEAT_2_LEAD"] = f"{len(firsts)} new face{'s' if len(firsts) != 1 else ''} in the groups."
        slots["BEAT_2_BODY"] = (", ".join(_esc(f["short"]) for f in firsts[:4])
                                + (" and more" if len(firsts) > 4 else "")
                                + f" played {'their' if len(firsts) != 1 else 'a'} first TGF round "
                                  f"{when_mid}. Show up once and you will know everyone by the turn.")
    else:
        slots["BEAT_2_LEAD"] = "Everybody was new once."
        slots["BEAT_2_BODY"] = ("Every group we send out has room for one more. Show up once and "
                                "you will know everyone by the turn.")

    # Beat 3 — fairness: a bogey / par that won, else the handicap spread.
    story = next((e for e in evs if e["skins_story"] and e["skins_story"]["score"] == "bogey"),
                 None) or next((e for e in evs if e["skins_story"]), None)
    if story:
        s = story["skins_story"]
        who = _gg_short(s.get("player"))
        is_first = any(f["short"] == who for f in story["first_timers"])
        slots["BEAT_3_LEAD"] = f"A {s['score']} won money."
        slots["BEAT_3_BODY"] = (
            f"On the {_ordinal(s['hole'])} hole in {_esc(story['chapter'])}, {_esc(who)}"
            f"{' — in his first TGF round —' if is_first else ''} made {s['score']}, and it was "
            f"the best score anyone posted on that hole. In our skins game every hole is its "
            f"own small contest, so one good hole pays even when the rest of the round doesn't. "
            f"That is how a {s['score']} beats a birdie made two holes later.")
    else:
        spreads = [(e["hcp_min"], e["hcp_max"]) for e in evs
                   if e["hcp_min"] is not None and e["hcp_max"] is not None]
        if spreads:
            lo = min(s[0] for s in spreads)
            hi = max(s[1] for s in spreads)
            slots["BEAT_3_LEAD"] = "The winners were not the low handicaps."
            slots["BEAT_3_BODY"] = (f"The players who cashed {when_mid} carried playing "
                                    f"handicaps from {int(lo)} to {int(hi)}. A TGF handicap keeps "
                                    "it fair, so a 20-handicap has the same shot as a scratch player.")
        else:
            slots["BEAT_3_LEAD"] = "Fair is the whole point."
            slots["BEAT_3_BODY"] = ("A TGF handicap keeps it fair, so a 20-handicap has the same "
                                    "shot as a scratch player.")

    # Headline follows the strongest beat.
    if cashed_firsts:
        slots["HEADLINE"] = "First round. First payday."
    elif story and story["skins_story"]["score"] == "bogey":
        slots["HEADLINE"] = "A bogey won money Tuesday"
    else:
        slots["HEADLINE"] = "You don't have to be the best golfer out here to get paid"

    slots["HIO_POT"] = _fmt_money(data.get("hio_pot")) if data.get("hio_pot") is not None else "growing"

    spots = [(e["chapter"], re.sub(r"\s*\([^)]*\)", "", e["fellowship_spot"]).strip())
             for e in evs if e.get("fellowship_spot")]
    if spots:
        slots["CELEBRATE_PROOF"] = (f"{when} the crowd landed at "
                                    + " and ".join(f"{_esc(s)} in {_esc(ch)}" for ch, s in spots)
                                    + ".")
    else:
        slots["CELEBRATE_PROOF"] = f"{when} most of the field stayed for a drink."

    for ch, key in (("San Antonio", "SA"), ("Austin", "AUS")):
        nt = data["next_tuesday"].get(ch)
        slots[f"{key}_NEXT_URL"] = nt["url"] if nt else RESULTS_PAGES[ch].rsplit("/pages", 1)[0]
        slots[f"{key}_NEXT_LABEL"] = nt["label"] if nt else "See the calendar"

    items = []
    for s in data["saturdays"]:
        city = "San Antonio" if (s["name"] or "").lower().startswith("s") else "Austin"
        items.append(f'<li><a href="{_esc(s["url"])}" style="color:#e2773d;">'
                     f'<strong>{_esc(city)} · {_esc(_fmt_day(s["date"]))}</strong></a> '
                     f'{_esc(s["course"] or s["name"])}</li>')
    slots["SATURDAY_18_ITEMS"] = "\n".join(items) if items else \
        "<li>Fall 18s are on both calendars below.</li>"
    slots["CLOSE_LEAD"] = "Jump in any time."
    return slots


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def render(slots: dict, template_path: Path = TEMPLATE_PATH) -> str:
    tpl = Path(template_path).read_text(encoding="utf-8")
    for k, v in slots.items():
        tpl = tpl.replace("{{" + k + "}}", str(v))
    tpl = tpl.replace("<title>TGF Fall Kicks Off</title>",
                      f"<title>{_esc(slots.get('HEADLINE', 'TGF Insider'))}</title>")
    # The template's author notes (<!-- example: ... -->) never ship.
    tpl = re.sub(r"<!--.*?-->\s*", "", tpl, flags=re.S)
    return tpl


def lint(html_out: str) -> list:
    """Boundary check before anything reaches Brevo: no unfilled slot, no
    banned word, no dollar figure outside the two allowed."""
    problems = []
    for m in re.findall(r"\{\{[A-Z0-9_]+\}\}", html_out):
        problems.append(f"unfilled slot {m}")
    text = re.sub(r"<[^>]+>", " ", html_out)
    for w in BANNED_WORDS:
        if re.search(rf"\b{re.escape(w)}\b", text, re.I):
            problems.append(f"banned word: {w}")
    dollars = re.findall(r"\$[\d,]+(?:\.\d\d)?", text)
    allowed = {"$25"}
    for d in dollars:
        if d in allowed:
            continue
        if "Hole-In-One Pot = " + d in text:
            continue
        problems.append(f"dollar figure outside the allowed two: {d}")
    return problems


# ── Brevo ───────────────────────────────────────────────────────────────

def create_brevo_draft(html_out: str, subject: str, name: str) -> dict:
    key = _api_key()
    if not key:
        return {"error": "BREVO_API_KEY not set"}
    payload = {
        "name": name, "subject": subject, "sender": {"id": SENDER_ID},
        "type": "classic", "htmlContent": html_out,
        "recipients": {"listIds": [LIST_ID], "exclusionSegmentIds": [EXCLUDE_SEGMENT_ID]},
        "tag": CAMPAIGN_TAG,
    }
    r = requests.post(f"{BREVO_API}/emailCampaigns", headers=_headers(key),
                      json=payload, timeout=30)
    if not r.ok:
        return {"error": f"HTTP {r.status_code}: {r.text[:300]}"}
    cid = (r.json() or {}).get("id")
    return {"campaign_id": cid,
            "url": f"https://app.brevo.com/camp/classic/{cid}/setup" if cid else None}


def build_public_recap_draft(dry_run: bool = True, db_path=None,
                             as_of: date | None = None) -> dict:
    """The Wednesday job. dry_run returns the rendered HTML and the facts;
    apply creates the Brevo DRAFT and emails Kerry the link. Never sends."""
    from . import database as db
    data = gather_week(db_path=db_path, as_of=as_of)
    if not data["events"]:
        return {"skipped": "no event with scorecards in the window", "data": data}
    slots = compose(data)
    html_out = render(slots)
    problems = lint(html_out)
    subject = f"TGF Insider | {slots['HEADLINE']}"
    out = {"dry_run": dry_run, "subject": subject, "slots": slots,
           "events": [{k: e[k] for k in ("name", "date", "field", "cashed", "results_url")}
                      for e in data["events"]],
           "first_timers": [f["short"] for e in data["events"] for f in e["first_timers"]],
           "lint": problems, "html": html_out}
    if dry_run:
        return out
    if problems:
        out["error"] = "lint failed — draft not created"
        return out
    week = data["as_of"]
    res = create_brevo_draft(html_out, subject, f"TGF Insider {week}")
    out.update(res)
    try:
        db.log_agent_action("insider-draft", "brevo-insider-draft",
                            f"week={week} campaign_id={res.get('campaign_id')} "
                            f"error={res.get('error')}", db_path=db_path)
    except Exception:
        pass
    if res.get("campaign_id"):
        out["ping"] = _ping_kerry(subject, res, data, db_path=db_path)
    return out


def _ping_kerry(subject: str, res: dict, data: dict, db_path=None) -> dict:
    """Email Kerry the draft link (Graph, same credentials as every other
    outgoing mail). Logged to message_log under 'insider-draft'."""
    from . import database as db
    from .fetcher import send_mail_graph
    tenant = os.getenv("AZURE_TENANT_ID"); client = os.getenv("AZURE_CLIENT_ID")
    secret = os.getenv("AZURE_CLIENT_SECRET"); frm = os.getenv("EMAIL_ADDRESS")
    to = (os.getenv("COO_EMAIL_TO") or frm or "").strip()
    if not all([tenant, client, secret, frm, to]):
        return {"sent": False, "reason": "mail not configured"}
    evs = ", ".join(e["name"] for e in data["events"])
    body = (f"<p>The Wednesday Insider draft is in Brevo, ready for your edit and send.</p>"
            f"<p><a href=\"{_esc(res['url'])}\">Open campaign #{res['campaign_id']}</a></p>"
            f"<p>Subject: {_esc(subject)}<br>Events: {_esc(evs)}<br>"
            f"Recipients: list {LIST_ID} minus segment {EXCLUDE_SEGMENT_ID} (Active members).</p>"
            f"<p>It will not send itself.</p>")
    try:
        ok = send_mail_graph(tenant_id=tenant, client_id=client, client_secret=secret,
                             from_address=frm, to_address=to,
                             subject=f"Insider draft ready — {subject}", html_body=body)
    except Exception as exc:
        ok = False
        logger.warning("insider ping failed: %s", exc)
    try:
        db.log_message({"event_name": "insider-draft", "channel": "email",
                        "recipient_name": "Kerry", "recipient_address": to,
                        "subject": subject, "body_preview": body[:200],
                        "status": "sent" if ok else "failed", "sent_by": "scheduler"},
                       db_path=db_path)
    except Exception:
        pass
    return {"sent": bool(ok), "to": to}


def send_review_preview(res: dict, db_path=None) -> dict:
    """Review mode (Kerry 2026-09-10: "We always need to review and discuss
    the Insider mailings until I'm confident enough to automate it a
    little more"): email Kerry the rendered Insider itself, wrapped in a
    review banner, and post the dry run to the Tracker mailbox so the
    session lane discusses it with him before anything reaches Brevo."""
    from . import database as db
    from .fetcher import send_mail_graph
    subject = res.get("subject") or "TGF Insider"
    week = (res.get("events") or [{}])[0].get("date") or today_central().isoformat()
    evs = ", ".join(e["name"] for e in res.get("events", []))
    firsts = ", ".join(res.get("first_timers") or []) or "none"
    lint = res.get("lint") or []
    banner = (
        '<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.5;'
        'background:#fff7ed;border:2px solid #e2773d;padding:12px 16px;margin:0 0 16px;">'
        f'<strong>INSIDER DRAFT FOR REVIEW — not in Brevo yet.</strong><br>'
        f'Events: {_esc(evs)}<br>First-timers named: {_esc(firsts)}<br>'
        f'Lint: {_esc(", ".join(lint) if lint else "clean")}<br>'
        'Reply with edits or say "go" in the Tracker session; the Brevo draft is created '
        'with <code>scoring-brevo-draft:apply</code> only after that.</div>')
    html_out = banner + (res.get("html") or "")
    out = {"emailed": False, "mailbox_post": None}
    tenant = os.getenv("AZURE_TENANT_ID"); client = os.getenv("AZURE_CLIENT_ID")
    secret = os.getenv("AZURE_CLIENT_SECRET"); frm = os.getenv("EMAIL_ADDRESS")
    to = (os.getenv("COO_EMAIL_TO") or frm or "").strip()
    if all([tenant, client, secret, frm, to]):
        try:
            ok = send_mail_graph(tenant_id=tenant, client_id=client, client_secret=secret,
                                 from_address=frm, to_address=to,
                                 subject=f"REVIEW: {subject}", html_body=html_out)
        except Exception as exc:
            ok = False
            logger.warning("insider review mail failed: %s", exc)
        out["emailed"] = bool(ok); out["to"] = to
        try:
            db.log_message({"event_name": "insider-review", "channel": "email",
                            "recipient_name": "Kerry", "recipient_address": to,
                            "subject": subject, "body_preview": (res.get("slots") or {}).get("BEAT_1_BODY", "")[:200],
                            "status": "sent" if ok else "failed", "sent_by": "scheduler"},
                           db_path=db_path)
        except Exception:
            pass
    else:
        out["reason"] = "mail not configured"
    try:
        slots = res.get("slots") or {}
        body = (f"TO: kerry, Event closeout lane — INSIDER DRAFT FOR REVIEW (week of {week}). "
                f"Subject: {subject}. Events: {evs}. First-timers: {firsts}. Lint: "
                f"{', '.join(lint) if lint else 'clean'}.\n"
                f"Beat 1: {re.sub('<[^>]+>', '', slots.get('BEAT_1_LEAD', ''))} {re.sub('<[^>]+>', '', slots.get('BEAT_1_BODY', ''))}\n"
                f"Beat 2: {slots.get('BEAT_2_LEAD', '')} {slots.get('BEAT_2_BODY', '')}\n"
                f"Beat 3: {slots.get('BEAT_3_LEAD', '')} {slots.get('BEAT_3_BODY', '')}\n"
                f"Not in Brevo. Discuss with Kerry, then scoring-brevo-draft:apply. "
                f"Re-render any time with scoring-brevo-draft (dry).")
        post = db.post_platform_dialogue_entry("tracker-claude", body, topic="insider-review",
                                               db_path=db_path or db.DB_PATH)
        out["mailbox_post"] = post.get("id") if isinstance(post, dict) else True
    except Exception as exc:
        logger.warning("insider review mailbox post failed: %s", exc)
    return out


def insider_mode(db_path=None) -> str:
    """draft (default, Kerry 2026-09-10) | review | off. INSIDER_AUTODRAFT=0 is 'off'."""
    from . import database as db
    if os.getenv("INSIDER_AUTODRAFT", "1") == "0":
        return "off"
    try:
        v = (db.get_app_setting("insider_autodraft", db_path=db_path) or "").strip().lower()
    except Exception:
        v = ""
    return v if v in ("review", "draft", "off") else "draft"


def weekly_insider_draft() -> None:
    """Scheduler entry point — Wednesday 13:00 UTC (8 AM Central).

    Mode from the dial `insider_autodraft`:
      draft (default)  — create the Brevo DRAFT and email Kerry the link. Kerry
                         2026-09-10: "Update the dial to create the Brevo draft
                         directly each wednesday at 8am. I'll review it there
                         because I can see all the visual with it too. And then
                         I'll work with you for edits before sending." Edits go
                         through the session lane; nothing sends itself.
      review           — render the dry run, email Kerry the preview, post it
                         to the Tracker mailbox; nothing goes to Brevo.
      off              — do nothing.
    """
    from . import database as db
    mode = insider_mode()
    if mode == "off":
        logger.info("Insider auto-draft disabled")
        return
    if mode == "draft" and not _api_key():
        logger.info("Insider auto-draft idle — BREVO_API_KEY not set")
        return
    try:
        if mode == "review":
            res = build_public_recap_draft(dry_run=True)
            if res.get("skipped"):
                logger.info("Insider review: %s", res["skipped"])
                return
            rv = send_review_preview(res)
            try:
                db.log_agent_action("insider-draft", "brevo-insider-review",
                                    f"subject={res.get('subject')} emailed={rv.get('emailed')} "
                                    f"mailbox={rv.get('mailbox_post')} lint={res.get('lint')}")
            except Exception:
                pass
            logger.info("Insider review preview: %s", json.dumps(rv, default=str))
            return
        res = build_public_recap_draft(dry_run=False)
        logger.info("Insider auto-draft: %s", json.dumps(
            {k: res.get(k) for k in ("skipped", "campaign_id", "error", "lint", "subject")},
            default=str))
    except Exception:
        logger.exception("Insider auto-draft failed")
