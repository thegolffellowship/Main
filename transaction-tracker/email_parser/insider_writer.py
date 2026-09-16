"""TGF Insider — the WRITER (Kerry 2026-09-16, spun off from the closeout lane).

Kerry: "I'm thinking you don't auto post to Brevo each week, but instead send
me an email of what you suggest, that I can edit and approve. I want it to be
creative though. I don't necessarily want the same format each time with the
'3 things.' I think we need to be more diverse about it. We need to explore
more of The Golf Fellowship and what it provides." And: "yes, I am
comfortable, ultimately, allowing an AI-written draft with options to choose
from. I would ultimately work back and forth with it to hone the message that
can be committed to memory."

What this module does, once a week, behind the `review` dial:

  1. ANGLE ROTATION as data — `ANGLES` is the catalogue; the dial
     `insider_angles` (comma list of keys) is the order Kerry wants; the
     dial `insider_angle_force` names one angle for the next run (consumed
     once); `insider_angle_history` (app_settings JSON) remembers what ran
     so no angle repeats until the rest have had a turn. An angle whose
     facts are missing this week (no first-timer, no Saturday 18 on the
     calendar, no member quote on file) is skipped, never faked.
  2. FACTS — `writer_facts()` turns `insider.gather_week()` into a public
     fact sheet: every name already first name + last initial, the links
     the writer may use, the ratified evergreen lines, and the surnames it
     must NOT print (checked on the way out).
  3. ONE Claude call (Sonnet class; parser.py's client pattern; billing
     alert on auth/credit failures) fed the angle brief, the fact sheet,
     the public rules, the member-recap house style for voice, and Kerry's
     past sent texts as examples. It returns the story box (1–4 beats, so
     the shape varies), the lede, the celebrate line, a headline PLUS two
     alternates, and a one-line "why this angle this week".
  4. VALIDATION — tags whitelisted, links only from the allow-list, no
     surname from the week's roster, no dollar figure but the two allowed,
     and `insider.lint()` on the rendered HTML. One retry with the
     problems fed back; then the deterministic composer takes over so the
     Wednesday 8:00 email always goes out.

Nothing here touches Brevo. The Brevo DRAFT is created only from the text
Kerry approves (`insider.approve_insider`), and Kerry sends.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "claude"
RULES_PATH = DOCS_DIR / "event-recaps.md"
EXAMPLES_PATH = DOCS_DIR / "templates" / "insider-voice-examples.md"

DEFAULT_MODEL = "claude-sonnet-4-5"      # the parser's proven premium route
MAX_TOKENS = 3000

# Public-send names: first name + last initial (CA/Kerry #381).
# ── The angle catalogue ─────────────────────────────────────────────────
# Keys are the dial vocabulary. `needs` names the fact the angle cannot run
# without; `band` pins the highlight band when the angle owns that story.
ANGLES = [
    {"key": "tuesday-story", "title": "A Tuesday story",
     "brief": ("Tell what actually happened on the tee this week as ONE story, not a "
               "list: who showed up in each city, what the night felt like, the one or "
               "two results that say something about TGF (a first-timer cashing, a par "
               "that won a skin, the spread of who went home with money). Money is "
               "proof of fairness, never the promise."),
     "needs": None, "band": None},
    {"key": "first-timer", "title": "A first-timer's night, start to finish",
     "brief": ("Walk a reader through their first Tuesday from the inside: sign up on "
               "the site, get a tee time and a group, play your own ball, the optional "
               "games explained in one clause each, the handicap that makes it fair, "
               "the drink afterward. Anchor it in THIS week's first-timers (public names "
               "only) and whether they cashed. Warm, specific, no hype."),
     "needs": "first_timers", "band": None},
    {"key": "fellowship", "title": "The fellowship afterward",
     "brief": ("The part that is not golf: what happens after the round — the "
               "clubhouse or the spot the group went to, the banter, getting to know "
               "the people you just played with, why members say it is the best part. "
               "Use this week's fellowship spots where recorded; where none is "
               "recorded say 'stick around for food, drink, and banter after the "
               "round'. Never invent a headcount."),
     "needs": None, "band": None},
    {"key": "handicap-fair", "title": "How the handicap makes a 20 and a scratch equal",
     "brief": ("Explain, plainly and without arithmetic, how a TGF Handicap plus "
               "flighting gives a 20-handicap and a scratch player the same shot at the "
               "money. Use the member handicap spread (percent single digits, percent 20 "
               "or higher, lowest to highest) and this week's spread of who cashed. Low, "
               "scratch and plus players must see there are others like them too."),
     "needs": None, "band": "skill"},
    {"key": "saturday-18s", "title": "The Saturday 18s and road trips",
     "brief": ("The other half of the calendar: 18 holes on a Saturday, morning tee "
               "times, sometimes the other city's course as a road trip. Name the "
               "upcoming Saturday 18s with their links. Tuesdays stay the easy first "
               "step; Saturdays are the bigger day out."),
     "needs": "saturdays", "band": None},
    {"key": "season-contests", "title": "The season contests, explained plainly",
     "brief": ("Explain the season contests in public vocabulary, one clause each: "
               "the fall points race (your Tuesday results earn points, best six count, "
               "it ends with the Fall Championship on October 31 at Kissing Tree) and "
               "the monthly points (every member is in automatically, no buy-in, the "
               "month's winner takes the pot). Everything is optional. Link CURRENT "
               "STANDINGS. Print NO dollar figure for these pots."),
     "needs": None, "band": None},
    {"key": "hio-pot", "title": "The Hole-In-One pot",
     "brief": ("The pot that grows every event until a member makes an ace at a TGF "
               "event and takes it all. Where it stands today, how it got there (a "
               "dollar per nine from every player), that 11 members have won it in 20 "
               "seasons. Fun, not a lottery pitch."),
     "needs": None, "band": "hio"},
    {"key": "twenty-seasons", "title": "Twenty seasons of TGF",
     "brief": ("What keeps a golf community going for twenty seasons: the same "
               "Tuesday rhythm, two cities, 150+ members, the people who have stayed. "
               "Use ONLY the history facts provided; do not invent dates, founders' "
               "stories or numbers."),
     "needs": None, "band": None},
    {"key": "course-of-week", "title": "A course of the week",
     "brief": ("Make the course the character: where each city played this week and "
               "where each plays next Tuesday. Say what a public reader can verify (the "
               "name, the city, nine holes late afternoon); no course-condition "
               "reviews, no invented yardages."),
     "needs": None, "band": None},
    {"key": "member-words", "title": "A member's own words",
     "brief": ("Build the issue around ONE member quote Kerry has put on file "
               "(verbatim, attributed as first name + last initial). Set it up in a "
               "sentence, let it stand, then connect it to what a reader can try next "
               "Tuesday. If no quote is on file this angle must not run."),
     "needs": "member_quote", "band": None},
]
ANGLE_KEYS = [a["key"] for a in ANGLES]
ANGLE_BY_KEY = {a["key"]: a for a in ANGLES}

# Evergreen facts the writer may use for the history angle. Kerry can
# replace the text via the dial `insider_facts_history`.
HISTORY_FACTS = ("The Golf Fellowship is in its 20th season. Chapters in San Antonio and "
                 "Austin, Texas. 150+ members. Tuesday-evening nines and Saturday 18s. "
                 "Eleven members have won the Hole-In-One pot over the 20 years.")

# Public rules — the CA/Kerry-ratified guardrails (#381) plus the lessons
# from Insiders #2 and #3, in the writer's own words. These WIN over anything
# in the member-recap house style that says otherwise.
PUBLIC_RULES = """PUBLIC INSIDER RULES (these override the member-recap style below where they differ):
- Audience: people on the TGF contact list who are NOT active members (prospects, alumni, guests). Never assume they know TGF vocabulary. Any game term (skin, closest-to-pin, net, flight, handicap) gets a one-clause plain explanation the first time it appears.
- Names: EVERY person is first name + last initial ("Justin G."). Never a full surname, never CAPS surnames (that is the member recap, not this).
- Money is PROOF, not the promise. The fraction of the field that cashed is one proof line; never "come get paid", never dollar amounts. The ONLY dollar figures allowed anywhere are the verbatim offer "$25 off your first event, plus a drink on us." (already in the template, do not repeat it) and the Hole-In-One pot value exactly as given.
- Never write: "league" (TGF is a golf club / community), "purse" (say POT), "TGF Plus", "DFW", "Houston". Count seasons ("20th season"), never years of founding.
- Humor is never at a person's expense. The buy-in nudge is an invitation, never a jab or a scold ("Play the games, people" is banned). Never say who has NOT bought in.
- Never infer gender; use genderless collectives ("two players at 33", not "two men").
- No handicap arithmetic in prose ("playing plus-3 so his net was…"). The mechanic is one plain clause.
- Never invent: no quotes, no headcounts, no course reviews, no dates or history beyond the fact sheet. If a fact is missing, write around it.
- Skins in plain language: "every hole is its own small contest, so one good hole pays even when the rest of the round doesn't". Never "alone".
- The headline must not repeat any recent headline listed in the fact sheet. Kerry's favourite shape: a plain statement with a little lift ("Half the Field Won Money!"). Keep it under ~45 characters.
- Tone: Kerry's voice — warm, direct, specific, a little wry, never salesy. Short sentences. Contractions fine. No exclamation pile-ups.
- Links: only the URLs on the fact sheet's allow-list, as <a href="..."> around a short label (RESULTS, CURRENT STANDINGS, TGF Handicaps, the course name). Every event mentioned in the lede links to its RESULTS page.
- Structure: the email is a fixed template. You write ONLY the headline, the lede, the story box (1 to 4 beats — vary it; "three things" every week is what Kerry asked us to stop doing), the Celebrate line, and the close-box header. The evergreen "How a TGF Event works", the Try-a-Tuesday buttons and the offer are already there and must not be restated.
- Length: the whole thing is a two-minute read. Lede 1–3 sentences. Each beat 2–4 sentences.
"""

OUTPUT_SCHEMA = """Return ONLY a JSON object, no prose, no code fences, with exactly these keys:
{
  "headline": "the title (plain text, <= 45 chars)",
  "alt_headlines": ["alternate title 1", "alternate title 2"],
  "lede": "1-3 sentences of inline HTML (allowed tags: <strong>, <em>, <a href>). Every event named links to its RESULTS url.",
  "story": [ {"lead": "bold opening phrase, plain text", "body": "2-4 sentences of inline HTML"} ],
  "celebrate": "one or two sentences, plain text, for the Celebrate line (what happens after the round this week)",
  "close_lead": "the close-box header, 2-5 words, plain text",
  "why": "one line to Kerry: why this angle fits this week"
}
"story" holds 1 to 4 items. No key may be empty."""


# ── dials + rotation ────────────────────────────────────────────────────

def angle_order(db_path=None) -> list:
    """The rotation order: dial `insider_angles` (comma list of keys) else
    the catalogue order. Unknown keys are dropped, duplicates collapsed."""
    from . import database as db
    raw = ""
    try:
        raw = db.get_app_setting("insider_angles", db_path=db_path) or ""
    except Exception:
        raw = ""
    keys = [k.strip().lower() for k in raw.split(",") if k.strip()]
    order = []
    for k in keys:
        if k in ANGLE_BY_KEY and k not in order:
            order.append(k)
    return order or list(ANGLE_KEYS)


def angle_history(db_path=None) -> list:
    """[{"as_of": "2026-09-23", "angle": "first-timer"}, …], oldest first."""
    from . import database as db
    try:
        raw = db.get_app_setting("insider_angle_history", db_path=db_path) or "[]"
        hist = json.loads(raw)
        return [h for h in hist if isinstance(h, dict) and h.get("angle")]
    except Exception:
        return []


def record_angle(angle: str, as_of: date, db_path=None) -> None:
    from . import database as db
    hist = angle_history(db_path=db_path)
    hist = [h for h in hist if h.get("as_of") != as_of.isoformat()]
    hist.append({"as_of": as_of.isoformat(), "angle": angle})
    db.set_app_setting("insider_angle_history", json.dumps(hist[-52:]), db_path=db_path)


def forced_angle(db_path=None) -> str | None:
    from . import database as db
    try:
        v = (db.get_app_setting("insider_angle_force", db_path=db_path) or "").strip().lower()
    except Exception:
        v = ""
    return v if v in ANGLE_BY_KEY else None


def clear_forced_angle(db_path=None) -> None:
    from . import database as db
    try:
        db.set_app_setting("insider_angle_force", "", db_path=db_path)
    except Exception:
        pass


def angle_available(key: str, data: dict) -> bool:
    """An angle whose facts are missing this week is skipped, never faked."""
    a = ANGLE_BY_KEY.get(key)
    if not a:
        return False
    need = a["needs"]
    if need is None:
        return True
    if need == "first_timers":
        return any(e.get("first_timers") for e in data.get("events", []))
    if need == "saturdays":
        return bool(data.get("saturdays"))
    if need == "member_quote":
        return bool((data.get("member_quote") or {}).get("quote"))
    return True


def pick_angle(order: list, history: list, data: dict, forced: str | None = None) -> str:
    """The next angle: the forced one if set; else the first in `order` that
    has not run since the rest of the rotation had its turn (least-recently
    used wins ties by order), skipping angles whose facts are missing."""
    if forced and angle_available(forced, data):
        return forced
    avail = [k for k in order if angle_available(k, data)]
    if not avail:
        return order[0] if order else ANGLE_KEYS[0]
    last_used = {}
    for i, h in enumerate(history):
        last_used[h["angle"]] = i
    never = [k for k in avail if k not in last_used]
    if never:
        return never[0]
    return min(avail, key=lambda k: (last_used[k], avail.index(k)))


def rotation_status(data: dict | None = None, db_path=None) -> dict:
    """What `scoring-insider-angles` shows: the order, what ran, what is next."""
    order = angle_order(db_path=db_path)
    hist = angle_history(db_path=db_path)
    forced = forced_angle(db_path=db_path)
    nxt = pick_angle(order, hist, data or {"events": [], "saturdays": []}, forced) if data else None
    return {"order": order,
            "catalogue": [{"key": a["key"], "title": a["title"], "needs": a["needs"]} for a in ANGLES],
            "history": hist[-12:], "forced": forced, "next": nxt,
            "unavailable_this_week": ([k for k in order if not angle_available(k, data)] if data else None),
            "dials": {"insider_angles": "comma list of keys, in order",
                      "insider_angle_force": "one key for the next run (consumed)",
                      "insider_writer": "on | off (off = deterministic composer)",
                      "insider_model": f"Anthropic model id (default {DEFAULT_MODEL})",
                      "insider_member_quote": 'JSON {"name": "Adam B.", "quote": "…"}',
                      "insider_facts_history": "replaces the twenty-seasons facts"}}


# ── facts ───────────────────────────────────────────────────────────────

def _long_date(d: str | None) -> str:
    try:
        dt = datetime.strptime((d or "")[:10], "%Y-%m-%d")
    except ValueError:
        return d or ""
    return f"{dt.strftime('%A, %B')} {dt.day}"


def _short_date(d: str | None) -> str:
    try:
        dt = datetime.strptime((d or "")[:10], "%Y-%m-%d")
    except ValueError:
        return d or ""
    return f"{dt.strftime('%a %b')} {dt.day}"


def recent_headlines(db_path=None, before: date | None = None, limit: int = 6) -> list:
    """Titles of the last few Insiders (draft pings + review mails), so the
    writer never repeats one (Kerry 2026-09-16)."""
    from . import database as db
    from .timezone_utils import today_central
    out = []
    try:
        with db._connect(db_path) as conn:
            rows = conn.execute(
                """SELECT subject FROM message_log
                    WHERE event_name IN ('insider-draft', 'insider-review', 'insider-approved')
                      AND subject IS NOT NULL AND date(sent_at) < ?
                    ORDER BY id DESC LIMIT 40""",
                ((before or today_central()).isoformat(),)).fetchall()
    except Exception:
        return out
    marker = "TGF Insider | "
    for r in rows:
        s = str(r[0])
        h = s.split(marker, 1)[1].strip() if marker in s else s.strip()
        if h and h not in out:
            out.append(h)
        if len(out) >= limit:
            break
    return out


def writer_facts(data: dict, db_path=None) -> dict:
    """The public fact sheet. Every name is already first + initial; the
    surnames the writer must not print ride along under `forbidden_surnames`
    so `validate()` can check the output."""
    from . import database as db
    from .insider import (HANDICAPS_URL, RESULTS_PAGES, _fmt_money, _fraction_phrase,
                          _gg_short, _short_name)
    forbidden: set = set()
    events = []
    for e in data.get("events", []):
        firsts = []
        for f in e.get("first_timers", []):
            ln = (f.get("last_name") or "").strip()
            if len(ln) >= 3:
                forbidden.add(ln.lower())
            src = None
            try:
                with db._connect(db_path) as conn:
                    row = conn.execute("SELECT acquisition_source FROM customers WHERE customer_id = ?",
                                       (f.get("customer_id"),)).fetchone()
                    src = row[0] if row else None
            except Exception:
                src = None
            firsts.append({"name": f.get("short") or _short_name(f.get("first_name"), f.get("last_name")),
                           "cashed": bool(f.get("cashed")),
                           "found_us_through": ("the Facebook & Instagram campaign"
                                                if (src or "").startswith("facebook") else None)})
        story = None
        if e.get("skins_story"):
            s = e["skins_story"]
            raw = re.sub(r"\s+Guest\b", "", s.get("player") or "", flags=re.I)
            last = raw.split(",", 1)[0].strip() if "," in raw else (raw.split()[-1] if raw.split() else "")
            if len(last) >= 3:
                forbidden.add(last.lower())
            who = _gg_short(s.get("player"))
            story = {"score": s["score"], "hole": s["hole"], "player": who,
                     "is_first_timer": any(f["name"] == who for f in firsts),
                     "meaning": "the best score anyone posted on that hole — a skin"}
        spot = e.get("fellowship_spot") or ""
        spot = re.sub(r"\s*\([^)]*\)", "", spot).strip()
        events.append({
            "chapter": e["chapter"], "course": e.get("course") or e.get("name"),
            "date": _long_date(e.get("date")), "holes": e.get("holes", 9),
            "field": e.get("field"), "cashed": e.get("cashed"),
            "cashed_phrase": _fraction_phrase(e.get("cashed") or 0, e.get("field") or 0),
            "first_timers": firsts, "skins_story": story,
            "cashers_playing_handicap_range": ([e["hcp_min"], e["hcp_max"]]
                                              if e.get("hcp_min") is not None else None),
            "fellowship_spot": spot or None,
            "results_url": e.get("results_url"),
        })
    dist = data.get("hcp_dist") or {}
    n = dist.get("members_with_index") or 0
    handicaps = None
    if n:
        lo, hi = dist.get("min"), dist.get("max")
        handicaps = {"members_with_index": n,
                     "pct_single_digits": round(100 * dist.get("single_digit", 0) / n),
                     "pct_20_or_higher": dist.get("pct_20_plus"),
                     "lowest": (f"+{int(round(abs(lo)))}" if lo is not None and lo < 0 else int(round(lo or 0))),
                     "highest": int(round(hi or 0)), "basis": "18-hole handicap index"}
    next_t = {}
    for ch, nt in (data.get("next_tuesday") or {}).items():
        next_t[ch] = {"course": nt.get("course") or nt.get("name"), "date": _short_date(nt.get("date")),
                      "url": nt.get("url")}
    sats = [{"chapter": ("San Antonio" if (s.get("name") or "").lower().startswith("s") else "Austin"),
             "course": s.get("course") or s.get("name"), "date": _short_date(s.get("date")), "url": s.get("url")}
            for s in data.get("saturdays") or []]
    links = {
        "handicaps_page": HANDICAPS_URL,
        "standings_fall_san_antonio": "https://tgf-tracker.up.railway.app/member/contests#race=fall_sa",
        "standings_fall_austin": "https://tgf-tracker.up.railway.app/member/contests#race=fall_austin",
        "standings_monthly": "https://tgf-tracker.up.railway.app/member/contests#race=monthly",
        "season_contests_store": "https://thegolffellowship.com/shop/ols/products/season-contests",
        "membership": "https://thegolffellowship.com/shop/ols/products/tgf-membership",
        "calendar_san_antonio": "https://tgf-sa.golfgenius.com/pages/5783305",
        "calendar_austin": "https://tgf-austin.golfgenius.com/pages/5790750",
        "homepage": "https://thegolffellowship.com/",
    }
    allow = set(links.values())
    for e in events:
        if e.get("results_url"):
            allow.add(e["results_url"])
    for nt in next_t.values():
        if nt.get("url"):
            allow.add(nt["url"])
    for s in sats:
        if s.get("url"):
            allow.add(s["url"])
    for base in RESULTS_PAGES.values():
        allow.add(base)
    quote = None
    hist = HISTORY_FACTS
    try:
        q = db.get_app_setting("insider_member_quote", db_path=db_path)
        if q:
            qq = json.loads(q)
            if isinstance(qq, dict) and qq.get("quote"):
                quote = {"name": qq.get("name") or "a member", "quote": qq["quote"]}
        h = db.get_app_setting("insider_facts_history", db_path=db_path)
        if h and h.strip():
            hist = h.strip()
    except Exception:
        pass
    as_of = datetime.strptime(data["as_of"], "%Y-%m-%d").date()
    monday = as_of - timedelta(days=as_of.weekday())
    return {
        "as_of": data["as_of"], "week_of": f"{monday.strftime('%B')} {monday.day}",
        "events": events,
        "hio_pot": (_fmt_money(data["hio_pot"]) if data.get("hio_pot") is not None else None),
        "hio_winners_in_20_seasons": 11,
        "handicaps": handicaps,
        "next_tuesday": next_t, "saturday_18s": sats,
        "season_contests": {
            "fall_points_race": ("your Tuesday results earn points; best six Tuesdays count; it ends with "
                                 "the Fall Championship on October 31 at Kissing Tree; buy in any time and "
                                 "your points so far activate"),
            "monthly_points": "every member is in automatically, no buy-in; the month's winner takes the pot",
        },
        "history": hist,
        "member_quote": quote,
        "recent_headlines": ([data["last_headline"]] if data.get("last_headline") else [])
                            + [h for h in recent_headlines(db_path=db_path, before=as_of)
                               if h != data.get("last_headline")],
        "links": links,
        "allowed_urls": sorted(allow),
        "forbidden_surnames": sorted(forbidden),
    }


# ── the call ────────────────────────────────────────────────────────────

class WriterError(Exception):
    pass


def writer_enabled(db_path=None) -> bool:
    """Dial `insider_writer` = on (default) | off. Also off without a key."""
    from . import database as db
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False
    try:
        v = (db.get_app_setting("insider_writer", db_path=db_path) or "").strip().lower()
    except Exception:
        v = ""
    return v != "off"


def writer_model(db_path=None) -> str:
    from . import database as db
    try:
        v = (db.get_app_setting("insider_model", db_path=db_path) or "").strip()
    except Exception:
        v = ""
    return v or os.getenv("INSIDER_MODEL") or DEFAULT_MODEL


def _read(path: Path, limit: int = 60000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except Exception:
        return ""


def build_prompt(facts: dict, angle_key: str, problems: list | None = None) -> tuple:
    """(system, user) for the call. The system prompt carries the public
    rules, the member-recap house style (voice + what Kerry corrects) and
    Kerry's sent texts; the user turn carries the angle and the facts."""
    a = ANGLE_BY_KEY[angle_key]
    rules_doc = _read(RULES_PATH)
    examples = _read(EXAMPLES_PATH)
    system = (
        "You write the weekly TGF Insider for The Golf Fellowship, a golf community in San Antonio "
        "and Austin, Texas, in the voice of its founder Kerry Niester. Kerry reads and edits every "
        "draft before it goes anywhere; write so he has little to change.\n\n"
        + PUBLIC_RULES
        + "\n\nKERRY'S SENT TEXTS (voice examples — match the voice, never copy sentences):\n"
        + (examples or "(none on file)")
        + "\n\nMEMBER-RECAP HOUSE STYLE (background: how Kerry writes and what he has corrected; "
          "the PUBLIC RULES above win where they differ — e.g. names are first + initial here, "
          "and no dollar amounts):\n" + rules_doc
    )
    user = (
        f"THIS WEEK'S ANGLE: {a['title']} (key: {a['key']})\n{a['brief']}\n\n"
        f"FACT SHEET (JSON — use only what is here; names are already in public form):\n"
        f"{json.dumps(facts, indent=1, ensure_ascii=False)}\n\n"
        + OUTPUT_SCHEMA
    )
    if problems:
        user += ("\n\nYOUR PREVIOUS DRAFT FAILED THESE CHECKS — fix every one and return the full JSON again:\n- "
                 + "\n- ".join(problems))
    return system, user


def _client_create(system: str, user: str, model: str) -> str:
    """The one place the Anthropic SDK is touched (mocked in tests).
    Mirrors parser._call_ai: fatal errors raise; the caller alerts."""
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise WriterError("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(model=model, max_tokens=MAX_TOKENS, system=system,
                                 messages=[{"role": "user", "content": user}])
    return "".join(getattr(b, "text", "") for b in msg.content).strip()


def _parse_json(raw: str) -> dict:
    txt = (raw or "").strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```(?:json)?\s*", "", txt)
        txt = re.sub(r"\s*```$", "", txt)
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    raise WriterError(f"writer returned non-JSON: {txt[:200]!r}")


# ── validation ──────────────────────────────────────────────────────────

_ALLOWED_TAGS = ("strong", "em", "br", "a")


def sanitize_html(fragment: str, allowed_urls: set, notes: list) -> str:
    """Whitelist inline tags; links only to allowed URLs (others unwrap to
    their text and are noted); everything else becomes text."""
    out = re.sub(r"<(script|style)\b[^>]*>.*?</\1\s*>", "", fragment or "", flags=re.S | re.I)

    def _tag(m):
        raw = m.group(0)
        closing = raw.startswith("</")
        name = re.match(r"</?\s*([a-zA-Z0-9]+)", raw)
        name = name.group(1).lower() if name else ""
        if name not in _ALLOWED_TAGS:
            notes.append(f"stripped tag <{name}>")
            return ""
        if name == "a":
            if closing:
                return "</a>"
            href = re.search(r'href\s*=\s*["\']([^"\']+)["\']', raw)
            url = href.group(1).strip() if href else ""
            if url not in allowed_urls:
                notes.append(f"unwrapped link to {url or '(no href)'}")
                return ""
            return f'<a href="{url}" style="color:#e2773d;font-weight:bold;">'
        if name == "br":
            return "<br>"
        return f"</{name}>" if closing else f"<{name}>"

    out = re.sub(r"<[^>]+>", _tag, out)
    # An unwrapped <a> left its </a>; drop orphans.
    opens = len(re.findall(r"<a ", out))
    closes = len(re.findall(r"</a>", out))
    if closes > opens:
        out = out.replace("</a>", "", closes - opens)
    return out.strip()


def validate(draft: dict, facts: dict) -> tuple:
    """(clean_draft, problems). Problems are what the retry feeds back."""
    problems: list = []
    notes: list = []
    allow = set(facts.get("allowed_urls") or [])
    clean = {}
    for k in ("headline", "celebrate", "close_lead", "why"):
        v = str(draft.get(k) or "").strip()
        v = re.sub(r"<[^>]+>", "", v)
        if not v:
            problems.append(f"missing {k}")
        clean[k] = v
    alts = draft.get("alt_headlines") or []
    if not isinstance(alts, list):
        alts = [str(alts)]
    alts = [re.sub(r"<[^>]+>", "", str(x)).strip() for x in alts if str(x).strip()]
    if len(alts) < 2:
        problems.append("need two alt_headlines")
    clean["alt_headlines"] = alts[:2]
    clean["lede"] = sanitize_html(str(draft.get("lede") or ""), allow, notes)
    if not clean["lede"]:
        problems.append("missing lede")
    story = draft.get("story") or []
    if not isinstance(story, list) or not (1 <= len(story) <= 4):
        problems.append("story must hold 1 to 4 beats")
        story = story[:4] if isinstance(story, list) else []
    beats = []
    for b in story:
        if not isinstance(b, dict):
            continue
        lead = re.sub(r"<[^>]+>", "", str(b.get("lead") or "")).strip()
        body = sanitize_html(str(b.get("body") or ""), allow, notes)
        if not lead or not body:
            problems.append("a story beat is missing its lead or body")
        beats.append({"lead": lead, "body": body})
    clean["story"] = beats
    # Text-level checks across everything the writer produced.
    blob = " ".join([clean["headline"], " ".join(clean["alt_headlines"]), clean["lede"],
                     clean["celebrate"], clean["close_lead"]]
                    + [f"{b['lead']} {b['body']}" for b in beats])
    text = re.sub(r"<[^>]+>", " ", blob)
    for sn in facts.get("forbidden_surnames") or []:
        if re.search(rf"\b{re.escape(sn)}\b", text, re.I):
            problems.append(f"full surname printed: {sn} — use first name + last initial")
    from .insider import BANNED_WORDS
    for w in BANNED_WORDS:
        if re.search(rf"\b{re.escape(w)}\b", text, re.I):
            problems.append(f"banned word: {w}")
    pot = facts.get("hio_pot")
    for d in re.findall(r"\$[\d,]+(?:\.\d\d)?", text):
        if d == "$25":
            problems.append("do not restate the offer; the template carries it")
        elif not (pot and d == pot):
            problems.append(f"dollar figure not allowed: {d}")
    if re.search(r"\balone\b", text, re.I):
        problems.append("'alone' is banned in the skins explanation")
    for h in facts.get("recent_headlines") or []:
        if h and clean["headline"].strip().lower() == h.strip().lower():
            problems.append(f"headline repeats a recent one: {h}")
    if len(clean["headline"]) > 60:
        problems.append("headline too long (keep under ~45 characters)")
    clean["notes"] = notes
    return clean, problems


# ── entry point ─────────────────────────────────────────────────────────

def write_insider(facts: dict, angle_key: str, db_path=None, model: str | None = None) -> dict:
    """One Claude call (plus one retry with the problems fed back). Returns
    the clean draft with `model`, `attempts`, `notes`. Raises WriterError
    when the writer cannot produce a clean draft — the caller falls back to
    the deterministic composer so the Wednesday email still goes out."""
    if angle_key not in ANGLE_BY_KEY:
        raise WriterError(f"unknown angle {angle_key!r}")
    model = model or writer_model(db_path=db_path)
    problems: list = []
    last_err = None
    for attempt in (1, 2):
        system, user = build_prompt(facts, angle_key, problems or None)
        try:
            raw = _client_create(system, user, model)
        except WriterError:
            raise
        except Exception as exc:           # SDK errors: alert on the billing class, then fall back
            try:
                from .ops_alerts import maybe_alert_anthropic_billing
                maybe_alert_anthropic_billing(exc)
            except Exception:
                pass
            logger.warning("insider writer call failed (attempt %d): %s", attempt, exc)
            raise WriterError(f"{type(exc).__name__}: {str(exc)[:200]}") from exc
        try:
            draft = _parse_json(raw)
        except WriterError as exc:
            last_err = str(exc)
            problems = ["return ONLY the JSON object"]
            continue
        clean, problems = validate(draft, facts)
        if not problems:
            clean.update({"angle": angle_key, "model": model, "attempts": attempt, "raw": raw})
            return clean
        last_err = "; ".join(problems)
        logger.info("insider writer attempt %d rejected: %s", attempt, last_err)
    raise WriterError(f"writer draft rejected after 2 attempts: {last_err}")
