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

Bridge: `scoring-brevo-draft[:dry|apply|review][|<angle>]`. Scheduler:
Wednesday 13:00 UTC (`weekly_insider_draft`). Dial `insider_autodraft`:
draft (Brevo DRAFT + link to Kerry), review (SET 2026-09-16 — the writer's
suggestion emailed to Kerry + posted to the mailbox, nothing in Brevo),
off. Skipped when no event was played in the window.

THE WRITER (2026-09-16, `insider_writer.py`): in review mode the story is
written by one Claude call on a rotating ANGLE (dial `insider_angles`),
with two alternate headlines and a one-line "why this angle"; `lint()`
still gates it; when the call fails the deterministic `compose()` below
is the fallback so the 8:00 email always goes out. The Brevo DRAFT is
created only from the text Kerry approves (`approve_insider`).
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


def _fraction_headline(n: int, m: int) -> str | None:
    """Kerry's headline shape (2026-09-16, s9.23 week): "Half the Field Won
    Money!" — the beat-1 fraction, capitalised, as the title."""
    if not m:
        return None
    r = n / m
    if r >= 0.66:
        return "Two-Thirds of the Field Won Money!"
    if r >= 0.5:
        return "Half the Field Won Money!"
    if r >= 0.45:
        return "Nearly Half the Field Won Money!"
    if r >= 0.33:
        return "A Third of the Field Won Money!"
    return None


def pick_headline(candidates: list, last_headline: str | None) -> str:
    """Strongest candidate that is NOT last week's title. Kerry 2026-09-16:
    "We copied the Brevo title from last week" — two Insiders in a row led
    "First round. First payday." because a first-timer cashed both weeks.
    The last candidate is the ratified default and is allowed to repeat
    only when nothing else is left."""
    cands = [c for c in candidates if c]
    last = (last_headline or "").strip().lower()
    for c in cands:
        if c.strip().lower() != last:
            return c
    return cands[-1] if cands else "TGF Insider"


def _fraction_phrase(n: int, m: int) -> str:
    if not m:
        return ""
    r = n / m
    if r >= 0.66:
        return "nearly two-thirds of the field"
    if r >= 0.5:
        return "half the field"
    if r >= 0.45:
        return "nearly half the field"
    if r >= 0.33:
        return "a third of the field"
    return f"{n} of {m} players"


def _hio_pot_as_of(pot, as_of: date):
    """The pot AS OF a date. get_hio_pot() adds every event's registrations
    into the running total, FUTURE events included (closeout skill OPEN 8:
    Cedar Creek's 8 signups were in the 9/16 figure). The Insider prints
    what the pot IS today, so take the running total at the last PLAYED
    event; fall back to the tool's headline when the event list is absent."""
    if not isinstance(pot, dict):
        return None
    cutoff = as_of.isoformat()
    played = [e for e in (pot.get("events") or [])
              if (e.get("date") or "") <= cutoff and e.get("running") is not None]
    if played:
        return max(float(e["running"]) for e in played)
    return pot.get("pot")


# ── data ────────────────────────────────────────────────────────────────

def last_insider_headline(db_path=None, before: date | None = None) -> str | None:
    """The previous Insider's headline, from the draft ping logged to
    message_log ('insider-draft', subject "TGF Insider | <headline>" or
    "Insider draft ready — TGF Insider | <headline>"). Only drafts BEFORE
    the as-of date count, so re-running today's draft does not rotate
    itself away."""
    from . import database as db
    try:
        with db._connect(db_path) as conn:
            row = conn.execute(
                """SELECT subject FROM message_log
                    WHERE event_name = 'insider-draft' AND subject IS NOT NULL
                      AND date(sent_at) < ?
                    ORDER BY id DESC LIMIT 1""",
                ((before or today_central()).isoformat(),)).fetchone()
    except Exception:
        logger.warning("insider: last headline unavailable", exc_info=True)
        return None
    if not row or not row[0]:
        return None
    subj = str(row[0])
    marker = "TGF Insider | "
    return subj.split(marker, 1)[1].strip() if marker in subj else subj.strip()


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
                      e.fellowship_spot, e.start_time,
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
                # Two doors in (Kerry 2026-09-10: "2 more members were first
                # timers, right? There were 4 first timers in each city's
                # events."): the 1st TIMER tag, OR a brand-new member — first
                # TGF purchase inside 90 days and no earlier card.
                firsts = [dict(r) for r in conn.execute(
                    """SELECT DISTINCT sr.customer_id, c.first_name, c.last_name,
                              sr.gross, sr.net, sr.playing_handicap
                         FROM scoring_rounds sr
                         JOIN customers c ON c.customer_id = sr.customer_id
                        WHERE sr.event_id = ? AND sr.customer_id IS NOT NULL
                          AND (
                            EXISTS (SELECT 1 FROM items i
                                     WHERE i.customer_id = sr.customer_id AND i.event_id = sr.event_id
                                       AND COALESCE(i.transaction_status,'active') = 'active'
                                       AND UPPER(COALESCE(i.user_status,'')) LIKE '1ST%')
                            OR (
                              NOT EXISTS (SELECT 1 FROM scoring_rounds x
                                           WHERE x.customer_id = sr.customer_id
                                             AND x.round_date < sr.round_date)
                              AND (SELECT MIN(order_date) FROM items i2
                                    WHERE i2.customer_id = sr.customer_id
                                      AND COALESCE(i2.transaction_status,'active') = 'active')
                                  >= date(sr.round_date, '-90 days')
                            )
                          )
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
                "start_time": ev["start_time"],
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
                    "date": ev["event_date"], "url": url, "start_time": ev.get("start_time"),
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
        out["hio_pot"] = _hio_pot_as_of(pot, as_of)
    except Exception:
        logger.warning("insider: HIO pot unavailable", exc_info=True)
    out["last_headline"] = last_insider_headline(db_path=db_path, before=as_of)
    try:
        out["hcp_dist"] = handicap_distribution(db_path=db_path)
    except Exception:
        logger.warning("insider: handicap distribution unavailable", exc_info=True)
        out["hcp_dist"] = None
    try:
        out["highlight_forced"] = db.get_app_setting("insider_highlight", db_path=db_path)
    except Exception:
        out["highlight_forced"] = None
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

HIGHLIGHT_ROTATION = ("skill", "hio")
ROTATION_EPOCH = date(2026, 9, 7)      # week 0 = skill (Kerry 2026-09-10)
HANDICAPS_URL = "https://tgf-tracker.up.railway.app/member/handicaps"
_DARK_OPEN = ('<tr><td style="padding:14px 32px 4px;">\n<table role="presentation" width="100%" '
              'cellpadding="0" cellspacing="0" style="background:#1b1b1b;border-radius:8px;"><tbody>')
_DARK_CLOSE = "</tbody></table>\n</td></tr>"


def pick_highlight(as_of: date, forced: str | None = None) -> str:
    """skill | hio | none. The dial insider_highlight forces one; otherwise
    alternate weekly from ROTATION_EPOCH."""
    f = (forced or "").strip().lower()
    if f in HIGHLIGHT_ROTATION or f == "none":
        return f
    weeks = (as_of - ROTATION_EPOCH).days // 7
    return HIGHLIGHT_ROTATION[weeks % len(HIGHLIGHT_ROTATION)]


def hio_block(pot) -> str:
    val = _fmt_money(pot) if pot is not None else "growing"
    return (_DARK_OPEN + '<tr><td style="padding:14px 18px;">\n'
            '<p style="margin:0;font-size:16px;line-height:1.55;color:#ffffff;text-align:center;">'
            '<strong style="color:#e2773d;"><span style="font-size:36px;">Hole-In-One Pot = '
            f'{val}</span></strong></p>\n'
            '<p style="margin:0;font-size:16px;line-height:1.55;color:#ffffff;">Every player at every '
            'TGF event kicks a dollar into it per 9, and it keeps growing until a member jars one '
            'during a TGF round and takes the whole thing. 11 have won over our 20 years. Join and '
            'you could be next!</p>\n</td></tr>' + _DARK_CLOSE)


def skill_block(dist: dict | None) -> str:
    """Am I good enough to play? — three big percentages (Kerry 2026-09-10:
    "big number, very limited text graphic ... It goes both ways. Low,
    scratch and plus handicappers need to see there's others like them")."""
    if not dist or not dist.get("members_with_index"):
        return ""
    n = dist["members_with_index"]
    pct_single = round(100 * dist["single_digit"] / n)
    pct_20 = dist["pct_20_plus"]
    lo, hi = dist["min"], dist["max"]
    lo_s = f"+{int(round(abs(lo)))}" if lo is not None and lo < 0 else f"{int(round(lo or 0))}"
    hi_s = f"{int(round(hi or 0))}"
    num = 'style="margin:0;font-size:44px;line-height:1;color:#e2773d;font-weight:bold;"'
    cap = 'style="margin:6px 0 0;font-size:13px;line-height:1.4;color:#ffffff;"'
    cell = 'align="center" valign="top" style="padding:8px 6px 4px;'
    return (_DARK_OPEN +
            '<tr><td colspan="3" style="padding:16px 18px 4px;text-align:center;">'
            '<p style="margin:0;font-size:20px;line-height:1.3;color:#ffffff;font-weight:bold;">'
            'Am I good enough to play?</p></td></tr>\n<tr>\n'
            f'<td width="33%" {cell}"><p {num}>{pct_single}%</p><p {cap}>play to<br>single digits</p></td>\n'
            f'<td width="34%" {cell}border-left:1px solid #3b3f44;border-right:1px solid #3b3f44;">'
            f'<p {num}>{lo_s}<span style="font-size:26px;color:#d3dde4;">&nbsp;to&nbsp;</span>{hi_s}</p>'
            f'<p {cap}>every handicap<br>in the group</p></td>\n'
            f'<td width="33%" {cell}"><p {num}>{pct_20}%</p><p {cap}>play to 20<br>or higher</p></td>\n'
            '</tr>\n<tr><td colspan="3" style="padding:8px 18px 16px;text-align:center;">'
            '<p style="margin:0;font-size:16px;line-height:1.55;color:#d3dde4;">The other half of us '
            f'are in between.<br>Check out our <a href="{HANDICAPS_URL}" style="color:#e2773d;'
            'font-weight:bold;">TGF Handicaps</a>.</p></td></tr>' + _DARK_CLOSE)


def highlight_block(data: dict) -> str:
    choice = pick_highlight(datetime.strptime(data["as_of"], "%Y-%m-%d").date(),
                            data.get("highlight_forced"))
    if choice == "skill":
        blk = skill_block(data.get("hcp_dist"))
        return blk or hio_block(data.get("hio_pot"))
    if choice == "hio":
        return hio_block(data.get("hio_pot"))
    return ""


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
            # Kerry 2026-09-10: count the whole group, not "the others".
            tail = (f" — {k + 1} of the {others + 1} first-timers on the sheet did.")
        elif others:
            tail = f" — one of {len(firsts)} first-timers on the sheet."
        else:
            tail = "."
        slots["BEAT_2_LEAD"] = "First round, first payday."
        slots["BEAT_2_BODY"] = (f"{_esc(f['short'])} teed it up with us for the first time "
                                f"{when_mid} and left with money" + tail
                                + " Everybody gets a fair game.")
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

    # Headline follows the strongest beat — but never repeats last week's
    # title (Kerry 2026-09-16). Candidates in strength order; the ratified
    # default sits last and may repeat only when nothing else remains.
    candidates = [
        "First round. First payday." if cashed_firsts else None,
        _fraction_headline(total_c, total_f),      # Kerry's pick, week 3
        (f"A {story['skins_story']['score']} won money Tuesday"
         if story and story["skins_story"]["score"] in ("bogey", "par") else None),
        "You don't have to be the best golfer out here to get paid",
    ]
    slots["HEADLINE"] = pick_headline(candidates, data.get("last_headline"))

    slots["HIO_POT"] = _fmt_money(data.get("hio_pot")) if data.get("hio_pot") is not None else "growing"

    # Kerry's shape (2026-09-10): "Austin grabbed drinks in the clubhouse.
    # San Antonio went to Max & Louie's for food and fellowship."
    spots = [(e["chapter"], re.sub(r"\s*\([^)]*\)", "", e["fellowship_spot"]).strip())
             for e in evs if e.get("fellowship_spot")]
    lines = []
    for ch, spot in spots:
        if re.search(r"clubhouse|on[- ]site|19th|grill|patio|bar$", spot, re.I):
            lines.append(f"{_esc(ch)} grabbed drinks in the clubhouse.")
        else:
            lines.append(f"{_esc(ch)} went to {_esc(spot)} for food and fellowship.")
    slots["CELEBRATE_PROOF"] = (" ".join(lines) if lines
                                else "Most of the field stayed for a drink after.")

    # Highlight band — one per week, rotated (Kerry: "rotate our highlight
    # sections each week to not overwhelm").
    slots["HIGHLIGHT_BLOCK"] = highlight_block(data)

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


_BEAT_BLOCK_RE = re.compile(
    r'<p style="([^"]*)"><strong>\{\{BEAT_1_LEAD\}\}</strong> \{\{BEAT_1_BODY\}\}</p>\s*'
    r'<p style="[^"]*"><strong>\{\{BEAT_2_LEAD\}\}</strong> \{\{BEAT_2_BODY\}\}</p>\s*'
    r'<p style="([^"]*)"><strong>\{\{BEAT_3_LEAD\}\}</strong> \{\{BEAT_3_BODY\}\}</p>')


def story_paragraphs_html(story: list, mid_style: str, last_style: str) -> str:
    """The story box with 1–4 beats (the writer varies the count — Kerry:
    not 'the same format each time with the 3 things')."""
    out = []
    for i, b in enumerate(story):
        style = last_style if i == len(story) - 1 else mid_style
        out.append(f'<p style="{style}"><strong>{_esc(b["lead"])}</strong> {b["body"]}</p>')
    return "\n".join(out)


def render(slots: dict, template_path: Path = TEMPLATE_PATH, story: list | None = None) -> str:
    """Fill the template. `story` (a list of {lead, body}) replaces the
    fixed three-beat box with as many beats as the writer produced."""
    tpl = Path(template_path).read_text(encoding="utf-8")
    if story:
        m = _BEAT_BLOCK_RE.search(tpl)
        if m:
            tpl = tpl[:m.start()] + story_paragraphs_html(story, m.group(1), m.group(2)) + tpl[m.end():]
    for k, v in slots.items():
        tpl = tpl.replace("{{" + k + "}}", str(v))
    tpl = tpl.replace("<title>TGF Fall Kicks Off</title>",
                      f"<title>{_esc(slots.get('HEADLINE', 'TGF Insider'))}</title>")
    # The template's author notes (<!-- example: ... -->) never ship.
    tpl = re.sub(r"<!--.*?-->\s*", "", tpl, flags=re.S)
    return tpl


def _allowed_dollars(db_path=None) -> set:
    """Dollar figures the dial `insider_join_offer` carries (Kerry 2026-09-17
    ratified printing the join price); empty when the dial is blank."""
    try:
        from .insider_writer import dollars_in, join_offer_text
        return dollars_in(join_offer_text(db_path=db_path))
    except Exception:
        return set()


def lint(html_out: str, allowed_extra=()) -> list:
    """Boundary check before anything reaches Brevo: no unfilled slot, no
    banned word, no dollar figure outside the allowed ones ($25 offer, the
    pot line, and the join-offer figures on the dial)."""
    problems = []
    for m in re.findall(r"\{\{[A-Z0-9_]+\}\}", html_out):
        problems.append(f"unfilled slot {m}")
    text = re.sub(r"<[^>]+>", " ", html_out)
    for w in BANNED_WORDS:
        if re.search(rf"\b{re.escape(w)}\b", text, re.I):
            problems.append(f"banned word: {w}")
    dollars = re.findall(r"\$[\d,]+(?:\.\d\d)?", text)
    allowed = {"$25"} | set(allowed_extra or ())
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


def compose_from_writer(data: dict, draft: dict) -> tuple:
    """(slots, story) — the writer's text in the template's slots, with the
    deterministic parts (eyebrow, highlight band, buttons, Saturdays, pot)
    from compose(). The band follows the angle when the angle owns that
    story (handicap-fair → skill, hio-pot → pot), else the weekly rotation."""
    from .insider_writer import ANGLE_BY_KEY
    slots = compose(data)
    slots["HEADLINE"] = draft["headline"]
    slots["LEDE_WITH_RESULTS_LINKS"] = draft["lede"]
    slots["CELEBRATE_PROOF"] = _esc(draft["celebrate"])
    slots["CLOSE_LEAD"] = _esc(draft["close_lead"])
    band = (ANGLE_BY_KEY.get(draft.get("angle") or "") or {}).get("band")
    if band:
        slots["HIGHLIGHT_BLOCK"] = highlight_block({**data, "highlight_forced": band})
    story = draft["story"]
    for i in range(3):
        b = story[i] if i < len(story) else {"lead": "", "body": ""}
        slots[f"BEAT_{i + 1}_LEAD"] = b["lead"]
        slots[f"BEAT_{i + 1}_BODY"] = b["body"]
    return slots, story


def build_public_recap_draft(dry_run: bool = True, db_path=None,
                             as_of: date | None = None, angle: str | None = None,
                             writer: bool | None = None, record: bool = False) -> dict:
    """The Wednesday job. dry_run returns the rendered HTML and the facts;
    apply creates the Brevo DRAFT and emails Kerry the link. Never sends.

    `angle` names the writer's angle (else the rotation picks; the dial
    `insider_angle_force` wins). `writer` forces the writer on/off (None =
    dial `insider_writer` + key present). `record=True` (the scheduled
    run) writes the angle into the rotation history and consumes the
    force dial. When the writer fails, `compose()` is the draft and
    `out["writer"]["error"]` says why — the email still goes out."""
    from . import database as db
    from . import insider_writer as iw
    data = gather_week(db_path=db_path, as_of=as_of)
    if not data["events"]:
        return {"skipped": "no event with scorecards in the window", "data": data}
    try:
        data["member_quote"] = json.loads(db.get_app_setting("insider_member_quote", db_path=db_path) or "null")
    except Exception:
        data["member_quote"] = None
    use_writer = iw.writer_enabled(db_path=db_path) if writer is None else writer
    forced = iw.forced_angle(db_path=db_path)
    angle_key = angle or iw.pick_angle(iw.angle_order(db_path=db_path), iw.angle_history(db_path=db_path),
                                       data, forced)
    writer_info = {"enabled": bool(use_writer), "angle": angle_key,
                   "angle_title": iw.ANGLE_BY_KEY.get(angle_key, {}).get("title"),
                   "forced": bool(forced and forced == angle_key), "ok": False, "error": None}
    story = None
    draft = None
    if use_writer:
        try:
            facts = iw.writer_facts(data, db_path=db_path)
            draft = iw.write_insider(facts, angle_key, db_path=db_path)
            slots, story = compose_from_writer(data, draft)
            writer_info.update({"ok": True, "model": draft.get("model"), "attempts": draft.get("attempts"),
                                "notes": draft.get("notes") or []})
        except iw.WriterError as exc:
            writer_info["error"] = str(exc)
            logger.warning("insider writer fell back to compose(): %s", exc)
            draft = None
    if draft is None:
        slots = compose(data)
    extra = _allowed_dollars(db_path=db_path)
    html_out = render(slots, story=story)
    problems = lint(html_out, extra)
    if problems and draft is not None:
        # The gate holds even on the writer's output: fall back rather than ship a rule break.
        writer_info.update({"ok": False, "error": f"lint after render: {'; '.join(problems)}"})
        draft = None
        story = None
        slots = compose(data)
        html_out = render(slots)
        problems = lint(html_out, extra)
    subject = f"TGF Insider | {slots['HEADLINE']}"
    out = {"dry_run": dry_run, "subject": subject, "slots": slots, "story": story,
           "events": [{k: e[k] for k in ("name", "date", "field", "cashed", "results_url")}
                      for e in data["events"]],
           "first_timers": [f["short"] for e in data["events"] for f in e["first_timers"]],
           "lint": problems, "html": html_out,
           "angle": angle_key, "writer": writer_info,
           "alt_headlines": (draft or {}).get("alt_headlines") or [],
           "why": (draft or {}).get("why") or ("deterministic draft — the writer did not run"
                                                if not use_writer else
                                                f"deterministic fallback — {writer_info.get('error')}")}
    if record:
        try:
            iw.record_angle(angle_key, datetime.strptime(data["as_of"], "%Y-%m-%d").date(), db_path=db_path)
            if forced:
                iw.clear_forced_angle(db_path=db_path)
        except Exception:
            logger.warning("insider: angle history not recorded", exc_info=True)
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


def _ping_kerry(subject: str, res: dict, data: dict, db_path=None,
                event_name: str = "insider-draft", intro: str | None = None) -> dict:
    """Email Kerry the draft link (Graph, same credentials as every other
    outgoing mail). Logged to message_log under `event_name`."""
    from . import database as db
    from .fetcher import send_mail_graph
    tenant = os.getenv("AZURE_TENANT_ID"); client = os.getenv("AZURE_CLIENT_ID")
    secret = os.getenv("AZURE_CLIENT_SECRET"); frm = os.getenv("EMAIL_ADDRESS")
    to = (os.getenv("COO_EMAIL_TO") or frm or "").strip()
    if not all([tenant, client, secret, frm, to]):
        return {"sent": False, "reason": "mail not configured"}
    evs = ", ".join(e["name"] for e in data.get("events") or [])
    body = (f"<p>{_esc(intro or 'The Wednesday Insider draft is in Brevo, ready for your edit and send.')}</p>"
            f"<p><a href=\"{_esc(res['url'])}\">Open campaign #{res['campaign_id']}</a></p>"
            f"<p>Subject: {_esc(subject)}" + (f"<br>Events: {_esc(evs)}" if evs else "") + "<br>"
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
        db.log_message({"event_name": event_name, "channel": "email",
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
    banner = review_banner(res, evs=evs, firsts=firsts)
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
        body = (f"TO: kerry, Insider writer lane — INSIDER DRAFT FOR REVIEW (week of {week}). "
                f"Events: {evs}. First-timers: {firsts}. Lint: {', '.join(lint) if lint else 'clean'}.\n"
                + review_summary_text(res)
                + "\nNot in Brevo. Kerry edits in chat; the lane folds the edits, then "
                  "scoring-insider-approve:<subject>|<html> creates the Brevo DRAFT from his text. "
                  "Re-render any time with scoring-brevo-draft:dry|<angle>.")
        post = db.post_platform_dialogue_entry("tracker-claude", body, topic="insider-review",
                                               db_path=db_path or db.DB_PATH)
        out["mailbox_post"] = post.get("id") if isinstance(post, dict) else True
    except Exception as exc:
        logger.warning("insider review mailbox post failed: %s", exc)
    return out


def review_summary_text(res: dict) -> str:
    """Plain-text digest of one draft: angle, why, the headline options, the beats."""
    w = res.get("writer") or {}
    alts = res.get("alt_headlines") or []
    lines = [f"Angle: {w.get('angle_title') or res.get('angle')} ({res.get('angle')}). "
             f"Writer: {'ok, ' + str(w.get('model')) if w.get('ok') else 'deterministic fallback'}"
             + (f" — {w.get('error')}" if w.get('error') else "") + ".",
             f"Why this angle: {res.get('why') or ''}",
             f"Headline options: 1) {res.get('subject', '').replace('TGF Insider | ', '')}"
             + "".join(f"  {i + 2}) {a}" for i, a in enumerate(alts))]
    story = res.get("story")
    if story:
        for i, b in enumerate(story):
            lines.append(f"Beat {i + 1}: {b['lead']} {re.sub('<[^>]+>', '', b['body'])}")
    else:
        slots = res.get("slots") or {}
        for i in (1, 2, 3):
            lines.append(f"Beat {i}: {re.sub('<[^>]+>', '', slots.get(f'BEAT_{i}_LEAD', ''))} "
                         f"{re.sub('<[^>]+>', '', slots.get(f'BEAT_{i}_BODY', ''))}")
    return "\n".join(lines)


def review_banner(res: dict, evs: str = "", firsts: str = "", label: str | None = None) -> str:
    """The orange box above a draft in the review email: what it is, the
    angle and why, the headline options, lint, what happens next."""
    w = res.get("writer") or {}
    lint_ = res.get("lint") or []
    alts = res.get("alt_headlines") or []
    head = res.get("subject", "").replace("TGF Insider | ", "")
    opts = f"<ol style=\"margin:4px 0 0 18px;padding:0;\"><li><strong>{_esc(head)}</strong> (used below)</li>" \
           + "".join(f"<li>{_esc(a)}</li>" for a in alts) + "</ol>"
    writer_line = (f"Written by the Insider writer ({_esc(w.get('model') or '')})"
                   if w.get("ok") else
                   "Deterministic draft" + (f" — writer fell back: {_esc(w.get('error'))}" if w.get("error") else ""))
    title = label or "INSIDER DRAFT FOR REVIEW — not in Brevo yet."
    return (
        '<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.5;'
        'background:#fff7ed;border:2px solid #e2773d;padding:12px 16px;margin:0 0 16px;">'
        f'<strong>{_esc(title)}</strong><br>'
        f'<strong>Angle:</strong> {_esc(w.get("angle_title") or res.get("angle") or "")}'
        f'{" (forced by dial)" if w.get("forced") else ""}<br>'
        f'<strong>Why this angle this week:</strong> {_esc(res.get("why") or "")}<br>'
        f'<strong>Headline / subject options:</strong>{opts}'
        f'{writer_line}<br>'
        + (f'Events: {_esc(evs)}<br>' if evs else '')
        + (f'First-timers named: {_esc(firsts)}<br>' if firsts else '')
        + f'Lint: {_esc(", ".join(lint_) if lint_ else "clean")}<br>'
        'Reply with edits in the Tracker session (or pick a headline). The Brevo draft is created '
        'only from the text you approve; nothing sends itself.</div>')


def send_review_samples(results: list, db_path=None, subject: str | None = None) -> dict:
    """Several angles in ONE review email (Kerry 2026-09-16: "an AI-written
    draft with options to choose from"). Each draft gets its own banner;
    the mailbox gets the digest of all of them. Nothing in Brevo."""
    from . import database as db
    from .fetcher import send_mail_graph
    results = [r for r in results if r and not r.get("skipped")]
    if not results:
        return {"emailed": False, "reason": "no drafts"}
    week = (results[0].get("events") or [{}])[0].get("date") or today_central().isoformat()
    subject = subject or f"REVIEW: {len(results)} Insider angles — week of {week}"
    parts = []
    for i, r in enumerate(results):
        parts.append(review_banner(r, label=f"OPTION {i + 1} of {len(results)} — not in Brevo."))
        parts.append(r.get("html") or "")
        if i < len(results) - 1:
            parts.append('<hr style="border:0;border-top:6px solid #1b1b1b;margin:32px 0;">')
    html_out = "".join(parts)
    out = {"emailed": False, "mailbox_post": None, "angles": [r.get("angle") for r in results]}
    tenant = os.getenv("AZURE_TENANT_ID"); client = os.getenv("AZURE_CLIENT_ID")
    secret = os.getenv("AZURE_CLIENT_SECRET"); frm = os.getenv("EMAIL_ADDRESS")
    to = (os.getenv("COO_EMAIL_TO") or frm or "").strip()
    if all([tenant, client, secret, frm, to]):
        try:
            ok = send_mail_graph(tenant_id=tenant, client_id=client, client_secret=secret,
                                 from_address=frm, to_address=to, subject=subject, html_body=html_out)
        except Exception as exc:
            ok = False
            logger.warning("insider samples mail failed: %s", exc)
        out["emailed"] = bool(ok); out["to"] = to
        try:
            db.log_message({"event_name": "insider-review", "channel": "email", "recipient_name": "Kerry",
                            "recipient_address": to, "subject": subject,
                            "body_preview": ", ".join(out["angles"])[:200],
                            "status": "sent" if ok else "failed", "sent_by": "insider-writer"},
                           db_path=db_path)
        except Exception:
            pass
    else:
        out["reason"] = "mail not configured"
    try:
        body = (f"TO: kerry, Insider writer lane — {len(results)} INSIDER OPTIONS FOR REVIEW (week of {week}), "
                f"emailed as one message. Nothing in Brevo.\n\n"
                + "\n\n".join(f"OPTION {i + 1}\n{review_summary_text(r)}" for i, r in enumerate(results))
                + "\n\nKerry picks one (or mixes), edits in chat; the lane folds the edits into "
                  "event-recaps.md + the voice examples, then scoring-insider-approve creates the Brevo DRAFT.")
        post = db.post_platform_dialogue_entry("tracker-claude", body, topic="insider-review",
                                               db_path=db_path or db.DB_PATH)
        out["mailbox_post"] = post.get("id") if isinstance(post, dict) else True
    except Exception as exc:
        logger.warning("insider samples mailbox post failed: %s", exc)
    return out


def approve_insider(subject: str, html_out: str, db_path=None, dry_run: bool = False) -> dict:
    """Kerry's approved text → the Brevo DRAFT (never sent). The lint gate
    runs on HIS html too (banned words, stray dollars, unfilled slots,
    the merge tags must survive); on any hit nothing is created. Logged as
    'insider-approved' so the headline rotation sees it."""
    from . import database as db
    subject = (subject or "").strip()
    if subject and not subject.lower().startswith("tgf insider |"):
        subject = f"TGF Insider | {subject}"
    problems = lint(html_out or "", _allowed_dollars(db_path=db_path))
    for tag in ("{{ contact.FIRSTNAME }}", "{{ unsubscribe }}", "{{ update_profile }}"):
        if tag not in (html_out or ""):
            problems.append(f"merge tag missing: {tag}")
    if not subject:
        problems.append("subject is empty")
    out = {"subject": subject, "lint": problems, "dry_run": dry_run, "created": False}
    if problems or dry_run:
        return out
    week = today_central().isoformat()
    res = create_brevo_draft(html_out, subject, f"TGF Insider {week} (approved)")
    out.update(res)
    try:
        db.log_agent_action("insider-draft", "brevo-insider-approved",
                            f"week={week} campaign_id={res.get('campaign_id')} error={res.get('error')}",
                            db_path=db_path)
    except Exception:
        pass
    if res.get("campaign_id"):
        out["created"] = True
        out["ping"] = _ping_kerry(subject, res, {"events": []}, db_path=db_path,
                                  event_name="insider-approved",
                                  intro="Your approved Insider is in Brevo as a DRAFT, ready to send.")
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
            # The writer runs here (angle from the rotation, recorded), the
            # deterministic composer is its fallback; Kerry gets the email.
            res = build_public_recap_draft(dry_run=True, record=True)
            if res.get("skipped"):
                logger.info("Insider review: %s", res["skipped"])
                return
            rv = send_review_preview(res)
            try:
                db.log_agent_action("insider-draft", "brevo-insider-review",
                                    f"subject={res.get('subject')} angle={res.get('angle')} "
                                    f"writer={(res.get('writer') or {}).get('ok')} "
                                    f"emailed={rv.get('emailed')} "
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
