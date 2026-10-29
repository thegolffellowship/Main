"""THE NIGHT'S RECAP, WRITTEN BY THE TRACKER (Kerry 2026-10-28, #2457 BUILD 2,
#2460-A/G; "Build both now for Saturday").

Kerry: "I want Claude side auditing/review checking every step on the
outside as a step, but don't want our events to be Claude dependent." The
recap used to need a Claude session woken by a clock (the 9:08 PM run). Now
the closeout chain (closeout_chain.py) calls this once every event of the
night has closed out:

  facts(event_ids)  -> everything the recap may say, from the Tracker only:
                       cards, recorded payouts, MVPs, Team Net, skins, CTP,
                       birdies, the points races, October, the HIO pot,
                       first-timers and UP NEXT with their store links;
  write(...)        -> one Claude API call (the Insider writer's pattern),
                       house style = docs/claude/event-recaps.md, template =
                       the newest hand-finished recap in docs/claude/recaps/;
  validate(...)     -> no blanks, every bold member name a Spotlight link, every
                       linked customer_id a real person of the night, every
                       dollar figure one the facts carry, every section there;
                       a failing draft is re-asked once with the problems,
                       then held;
  the stored recap  -> recap_store ("db:<date>"), which the staff draft email
                       and the 6:00 AM results email read.

Event Ops stays the verifier: it reads the stored recap and can hold the
6:00 AM send. Dial `recap_writer_auto` (on unless "off"); model from
`recap_model`, else `insider_model`, else the Insider's default.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

DOCS = Path(__file__).resolve().parent.parent / "docs" / "claude"
RULES_PATH = DOCS / "event-recaps.md"
RECAPS_DIR = DOCS / "recaps"
BASE = "https://tgf-tracker.up.railway.app"
STORE_CONTESTS = "https://thegolffellowship.com/shop/ols/products/season-contests"
MAX_TOKENS = 6000
SECTION_OF = {"san antonio": "SAN ANTONIO", "austin": "AUSTIN", "tgf": "TGF"}
RACE_LINK = {"san antonio": f"{BASE}/member/contests#race=fall_sa",
             "austin": f"{BASE}/member/contests#race=fall_austin"}
SIGNATURE = {"SAN ANTONIO": "Kerry Niester\nThe Golf Fellowship\n210.838.3948",
             "TGF": "Kerry Niester\nThe Golf Fellowship\n210.838.3948",
             "AUSTIN": "Robert Straiton\nThe Golf Fellowship — Austin"}
DOLLAR_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)")
LINK_RE = re.compile(r"\[\[([^\]|]+)\|(\d+)\]\]")


class WriterError(Exception):
    pass


def enabled(db_path=None) -> bool:
    from . import database as db
    return (db.get_app_setting("recap_writer_auto", db_path=db_path) or "on").strip().lower() \
        not in ("off", "0", "false", "no")


def model(db_path=None) -> str:
    from . import database as db
    from .insider_writer import DEFAULT_MODEL
    for k in ("recap_model", "insider_model"):
        v = (db.get_app_setting(k, db_path=db_path) or "").strip()
        if v:
            return v
    return DEFAULT_MODEL


# ── facts ───────────────────────────────────────────────────────────────
def _to_par(n) -> str:
    n = int(round(n))
    return "E" if n == 0 else (f"+{n}" if n > 0 else f"−{abs(n)}")


def _player(conn, cid) -> dict:
    from .tracker_points import _non_member
    r = conn.execute("SELECT first_name, last_name, current_player_status FROM customers "
                     "WHERE customer_id = ?", (cid,)).fetchone()
    if not r:
        return {"customer_id": cid}
    member = not _non_member(r["current_player_status"])
    first, last = (r["first_name"] or "").strip(), (r["last_name"] or "").strip()
    return {"customer_id": cid, "first": first, "last": last, "member": member,
            # The house name form (lessons 52/53/67): members bold CAPS surname,
            # linked to the Spotlight; guests plain.
            "write_as": (f"[[{first} {last.upper()}|{cid}]]" if member else f"{first} {last}")}


def event_facts(event_id: int, db_path=None) -> dict:
    from . import database as db
    from .results_email import event_facts as base_facts, _payout_label
    f = base_facts(int(event_id), db_path=db_path)
    ev = f["event"]
    out = {"event_id": ev["id"], "name": ev["item_name"], "date": str(ev["event_date"])[:10],
           "weekday": date.fromisoformat(str(ev["event_date"])[:10]).strftime("%A"),
           "course": ev.get("course"), "chapter": f["chapter"],
           "section": SECTION_OF.get(f["chapter"], (ev.get("chapter") or "").upper()),
           "start": f"{ev.get('start_type') or ''} {ev.get('start_time') or ''}".strip(),
           "results_link": f"{BASE}/member/results/{ev['id']}",
           "players": [], "payouts": [], "teams": {}}
    with db._connect(db_path) as conn:
        for cid, c in sorted(f["cards"].items()):
            r = c["round"]
            p = _player(conn, cid)
            pars = sum(int((c["meta"].get(int(h["hole_number"])) or {}).get("par") or 0)
                       for h in c["holes"] if h["strokes"] is not None)
            birdies, eagles = [], []
            for h in c["holes"]:
                par = (c["meta"].get(int(h["hole_number"])) or {}).get("par")
                if h["strokes"] is None or not par:
                    continue
                d = int(h["strokes"]) - int(par)
                if d == -1:
                    birdies.append(int(h["hole_number"]))
                elif d <= -2:
                    eagles.append(int(h["hole_number"]))
            gross = r.get("gross")
            net = r.get("net")
            p.update({"tee": r.get("tee_name"), "playing_handicap": r.get("playing_handicap"),
                      "gross": gross, "net": net,
                      "gross_to_par": _to_par(gross - pars) if gross is not None and pars else None,
                      "net_to_par": _to_par(net - pars) if net is not None and pars else None,
                      "birdies_on": birdies, "eagles_on": eagles,
                      "won": round(sum(float(x["amount"] or 0) for x in f["payouts"].get(cid, [])), 2)})
            out["players"].append(p)
        for cid, rows in f["payouts"].items():
            p = _player(conn, cid)
            for x in rows:
                out["payouts"].append({"customer_id": cid, "write_as": p.get("write_as"),
                                       "category": x["category"], "amount": float(x["amount"] or 0),
                                       "what": _payout_label(x["category"], x["description"])})
        first_timers = [int(x[0]) for x in conn.execute(
            "SELECT DISTINCT customer_id FROM items WHERE customer_id IS NOT NULL "
            "AND (event_id = ? OR lower(item_name) = lower(?)) AND upper(COALESCE(user_status,'')) "
            "LIKE '%1ST TIMER%'", (ev["id"], ev["item_name"])).fetchall()]
    out["first_timers"] = [p for p in out["players"] if p["customer_id"] in first_timers]
    for g in (db.get_event_print_pack(int(event_id), db_path=db_path) or {}).get("groups") or []:
        out["teams"][str(g.get("group_num"))] = {
            "label": g.get("slot_label") or g.get("label"),
            "players": [p.get("customer_id") for p in g.get("players") or []]}
    out["points"] = _points(f)
    out["field"] = len(out["players"])
    return out


def _points(f) -> dict:
    """The fall race(s) (ENROLLED rows only: lesson 34) and October."""
    out = {"store_link": STORE_CONTESTS, "monthly_link": f"{BASE}/member/contests#race=monthly"}
    for key, race in (f.get("races") or {}).items():
        rows = [r for r in race.get("rows") or [] if r.get("enrolled")]
        out[f"fall_{key}"] = {
            "link": RACE_LINK.get(key), "final": race.get("final"),
            "champions": race.get("champions"),
            "top": [{"rank": r.get("rank"), "customer_id": r.get("customer_id"),
                     "points": r.get("total_points")} for r in rows[:6]]}
    m = f.get("month") or {}
    rows = m.get("standings") or []
    out["month"] = {"month": m.get("name") or m.get("month"), "purse": m.get("purse"),
                    "top": [{"rank": r.get("rank_label") or r.get("rank"),
                             "customer_id": r.get("customer_id"), "points": r.get("points")}
                            for r in rows[:6]]}
    return out


def night_facts(event_ids: list, db_path=None) -> dict:
    from . import database as db
    evs = [event_facts(e, db_path=db_path) for e in event_ids]
    nxt = []
    with db._connect(db_path) as conn:
        d = max(e["date"] for e in evs)
        for r in conn.execute(
                "SELECT id, item_name, event_date, course, chapter, start_type, start_time, "
                "registration_url FROM events WHERE substr(event_date, 1, 10) > ? "
                "AND lower(COALESCE(status, 'active')) NOT IN ('cancelled', 'canceled') "
                "ORDER BY event_date, id LIMIT 6", (d,)).fetchall():
            ev = dict(r)
            ev["lock"] = None
            try:
                lk = db.event_lock_at(ev)
                ev["lock"] = lk.strftime("%A %b %-d, %-I:%M %p") if lk else None
            except Exception:
                pass
            nxt.append(ev)
        ids = {p["customer_id"] for e in evs for p in e["players"]}
        for e in evs:
            for k, v in e["points"].items():
                if isinstance(v, dict):
                    for row in v.get("top") or []:
                        if row.get("customer_id"):
                            ids.add(row["customer_id"])
                            row["write_as"] = _player(conn, row["customer_id"]).get("write_as")
    hio = None
    try:
        hio = db.get_hio_pot(db_path=db_path).get("pot")
    except Exception:
        logger.exception("recap writer: HIO pot unreadable")
    mvp = []
    try:
        mvp = [x for e in evs for x in e["payouts"] if x["category"] in ("mvp", "tgf_mvp")]
    except Exception:
        pass
    return {"events": evs, "up_next": nxt, "hio_pot": hio, "mvps": mvp,
            "known_customer_ids": sorted(ids),
            "greeting": "Good Morning, %first_name%!",
            "signatures": SIGNATURE}


# ── the call ────────────────────────────────────────────────────────────
def _read(p: Path, limit: int = 70000) -> str:
    try:
        return p.read_text(encoding="utf-8")[:limit]
    except Exception:
        return ""


def template_example() -> str:
    """The newest hand-finished recap in the repo: the shape to match."""
    files = sorted(RECAPS_DIR.glob("20*.md"), reverse=True)
    return _read(files[0], 30000) if files else ""


def build_prompt(facts: dict, problems: list | None = None) -> tuple:
    sections = sorted({e["section"] for e in facts["events"]})
    system = (
        "You write the members' event recap for The Golf Fellowship (TGF), a golf community in "
        "San Antonio and Austin, Texas, the morning after an event night. Kerry Niester (founder) "
        "and Robert Straiton (Austin manager) send it; write so they have nothing to change.\n\n"
        "HOUSE STYLE AND EVERY LESSON KERRY HAS TAUGHT (follow all of it):\n"
        + _read(RULES_PATH)
        + "\n\nTEMPLATE OF RECORD (the last recap as finished; match its shape, headings, spacing, "
          "markup and voice exactly; never copy its facts):\n" + template_example()
    )
    user = (
        "Write tonight's recap as ONE markdown document in exactly the template's format:\n"
        "- a '# Recap DRAFTS — ...' title line, a short intro, then '## VERIFY BEFORE SENDING' "
        "(the checks a sender should glance at: money total per event, MVPs, anything unusual in "
        "the facts), then '---', then one section per chapter headed '## <SECTION> — <event name>' "
        f"for these sections in this order: {', '.join(sections)}.\n"
        "- Each section: '**Subject:** TGF Results | ...', the greeting line exactly as given, the "
        "story, FULL EVENT RESULTS link, the points paragraphs with their standings links and the "
        "BUYING IN link, the green Hole-in-One line between *** rules, NEW FACES when there are "
        "first-timers, UP NEXT with REGISTER links, the sign-off, and the section's signature.\n"
        "- Use ONLY the facts below. Every member is written exactly as its write_as value "
        "([[First LAST|id]]); guests plain. Every dollar figure must be one in the facts (a player's "
        "night total is his `won`). Never leave a blank or a placeholder; leave out anything the "
        "facts don't support (no fellowship section without a count, no photos).\n"
        "- Return ONLY the markdown, no commentary.\n\n"
        "FACTS (JSON):\n" + json.dumps(facts, indent=1, ensure_ascii=False, default=str)
    )
    if problems:
        user += ("\n\nYOUR PREVIOUS DRAFT FAILED THESE CHECKS. Fix every one and return the whole "
                 "document again:\n- " + "\n- ".join(problems))
    return system, user


def _client_create(system: str, user: str, model_id: str) -> str:
    """The one place the Anthropic SDK is touched (mocked in tests)."""
    import os
    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise WriterError("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(model=model_id, max_tokens=MAX_TOKENS, system=system,
                                 messages=[{"role": "user", "content": user}])
    return "".join(getattr(b, "text", "") for b in msg.content).strip()


# ── checks ──────────────────────────────────────────────────────────────
def _amounts(facts: dict) -> set:
    vals = set()
    for e in facts["events"]:
        tot = 0.0
        for x in e["payouts"]:
            vals.add(round(x["amount"], 2))
            tot += x["amount"]
        vals.add(round(tot, 2))
        for p in e["players"]:
            if p.get("won"):
                vals.add(round(p["won"], 2))
    if facts.get("hio_pot") is not None:
        vals.add(round(float(facts["hio_pot"]), 2))
    for e in facts["events"]:
        purse = (e.get("points") or {}).get("month", {}).get("purse")
        if purse:
            vals.add(round(float(purse), 2))
    vals.add(1.0)        # "$1 per TGF member at month end" (October race)
    return vals


def validate(md: str, facts: dict) -> list:
    from .recap_mail import BLANK_RE, UNLINKED_NAME_RE
    problems = []
    if BLANK_RE.search(md) or re.search(r"\[(?:TBD|TODO|XX+|\?+)\]", md, re.I):
        problems.append("there is a blank or placeholder; fill it from the facts or leave the line out")
    unl = sorted(set(UNLINKED_NAME_RE.findall(md)))
    if unl:
        problems.append("bold member names without a Spotlight link: " + ", ".join(unl))
    known = set(facts["known_customer_ids"])
    bad = sorted({int(c) for _, c in LINK_RE.findall(md) if int(c) not in known})
    if bad:
        problems.append(f"links to customer ids that are not in the facts: {bad}")
    allowed = _amounts(facts)
    stray = sorted({m for m in DOLLAR_RE.findall(md)
                    if round(float(m.replace(",", "")), 2) not in allowed})
    if stray:
        problems.append("dollar figures not in the facts: " + ", ".join("$" + s for s in stray))
    for e in facts["events"]:
        if not re.search(rf"^## {re.escape(e['section'])}\b", md, re.M):
            problems.append(f"missing the section '## {e['section']} — {e['name']}'")
    if "**Subject:**" not in md:
        problems.append("no **Subject:** line")
    if "%first_name%" not in md:
        problems.append("the greeting must be exactly: " + facts["greeting"])
    return problems


def write(event_ids: list, db_path=None, attempts: int = 2) -> dict:
    """Draft, check, re-ask once. Returns {md, model, attempts, problems}.
    Raises WriterError when no clean draft came back."""
    facts = night_facts(event_ids, db_path=db_path)
    m = model(db_path)
    problems = None
    md = ""
    for attempt in range(1, attempts + 1):
        system, user = build_prompt(facts, problems)
        try:
            md = _client_create(system, user, m)
        except WriterError:
            raise
        except Exception as exc:
            try:
                from .ops_alerts import maybe_alert_anthropic_billing
                maybe_alert_anthropic_billing(exc)
            except Exception:
                pass
            raise WriterError(f"Claude call failed: {type(exc).__name__}: {exc}") from exc
        md = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", md.strip())
        problems = validate(md, facts)
        if not problems:
            return {"md": md, "model": m, "attempts": attempt, "problems": [], "facts": facts}
    raise WriterError("draft failed its checks: " + "; ".join(problems or []))


def night_key(event_ids: list, db_path=None) -> str:
    from . import database as db
    with db._connect(db_path) as conn:
        rows = [conn.execute("SELECT item_name, event_date FROM events WHERE id = ?",
                             (int(e),)).fetchone() for e in event_ids]
    d = max(str(r["event_date"])[:10] for r in rows)
    codes = "-".join(re.sub(r"[^a-z0-9.]+", "-", (r["item_name"] or "").lower()).strip("-")[:40]
                     for r in rows)
    return f"{d}-{codes}"


def write_and_store(event_ids: list, db_path=None) -> dict:
    """Write the night's recap and store it ("db:<key>"). Returns {name, ...}."""
    from . import recap_store
    from .timezone_utils import now_central
    res = write(event_ids, db_path=db_path)
    key = night_key(event_ids, db_path=db_path)
    name = recap_store.save(key, res["md"], {
        "event_ids": [int(e) for e in event_ids], "model": res["model"],
        "attempts": res["attempts"], "written_at": now_central().strftime("%Y-%m-%d %H:%M"),
        "writer": "recap_writer"}, db_path=db_path)
    return {"name": name, "model": res["model"], "attempts": res["attempts"],
            "sections": sorted({e["section"] for e in res["facts"]["events"]})}
