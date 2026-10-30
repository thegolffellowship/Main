"""THE POST-ROUND INTERVIEW, BY EMAIL (Kerry 2026-10-29, Event Ops #2462: "a
trigger that sends a text via Twilio to the MVP/TGF MVP for the evening and
perhaps anyone that has an eagle or better, or 3 or more birdies a link to do
a quick AI interactive interview to get some quotes for inclusion in the
recap"). The Twilio number is released, so this is the EMAIL version.

At CLOSEOUT START, 15 minutes after the last score (scoring_window.tick
calls `closeout_hook`), every player who qualifies gets ONE email with a
signed link `/interview/<token>` (Kerry 10/30: "Invitations should go out
immediately after the 15 min buffer from last score entered"). The MVPs come
from the recorded payouts, so they get theirs in a second pass once the
closeout chain's `payouts` step is done, while the recap is still waiting:

  City MVP / TGF MVP   a recorded payout row of category mvp / tgf_mvp
  eagle or better      a hole at par - 2 or better on his published card
  3+ birdies           three or more holes at par - 1

The page asks the person's questions one at a time (questions_for: they
follow the achievement, Kerry 10/30). When
ANTHROPIC_API_KEY is set it may ask ONE short follow-up per answer, written
by the recap writer's model (recap_writer.model(), same SDK call shape),
at most three, so the whole thing stays near two minutes; without a key, or
on any error, it is a plain form. Answers are kept in app setting
`ai_interview_answers:<event_id>`; nothing is used without the explicit
Yes to "Do you give us permission to use your quotes in the event recap?". `consented_quotes(event_id)` is what the
recap writer reads.

LOCKED twice, like the handicap ask: dial `ai_interview_email` = on (default
OFF) AND the wording carries Kerry's stamp (`ai_interview_approved` =
`template_hash()`). Staff preview: bridge `scoring-ai-interview:<event_id>
[|preview[|<staff addr>]]` lists who qualifies and why; preview mail goes to
staff only and its link saves nothing. The hook never raises.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

DIAL = "ai_interview_email"
APPROVAL_KEY = "ai_interview_approved"
STATE_KEY = "ai_interview:{}"
ANSWERS_KEY = "ai_interview_answers:{}"
WAIT_KEY = "ai_interview_wait_minutes"       # the recap waits this long for answers
# Kerry 10/30: "I'm willing to allow 90 minutes from that point" (closeout start)
DEFAULT_WAIT = 90
TOKEN_DAYS = 7
MAX_ANSWER = 1200
MAX_FOLLOWUPS = 3
AI_TIMEOUT = 8.0
DEFAULT_PREVIEW_TO = "kerry@thegolffellowship.com"

# The questions follow the achievement (Kerry 10/30: "A leading comment
# about why they're receiving it ... followed by the questionnaire that
# might adapt to the achievement"). The biggest achievement sets the first
# two questions; each other one adds its own question (at most two), and
# everyone ends with LAST_QUESTION.
QUESTION_SETS = {
    # a points race won (Kerry 10/30: "keeping in mind these were season
    # contests that took the whole fall or month to achieve")
    "champ": ("What's been the secret for you this {span}?",
              "Were you tracking the leaderboard? When did you know you had a real shot?",
              "Which round this {span} stands out, and why?"),
    "ace": ("Tell us about the hole-in-one on {holes}: the club, the yardage, who saw it.",
            "What went through your head when it dropped?"),
    "eagle": ("Walk us through the eagle on {holes}: the shots, the distances, the clubs, "
              "how it went in.",
              "How did the rest of your round go?"),
    "mvp": ("Where did the round turn your way?",
            "What was working for you out there?"),
    "birdies": ("Which birdie was the best, and what happened?",
                "What was working for you out there?"),
}
EXTRA_QUESTION = {
    "champ": "What's been the secret for you this {span}?",
    "ace": "Tell us about the hole-in-one on {holes}.",
    "eagle": "Tell us about the eagle on {holes}: the shots and the clubs.",
    "mvp": "Where did the round turn your way?",
    "birdies": "Which of your {n} birdies was the best, and what happened?",
}
LAST_QUESTION = "Is there anything else you'd like to add?"
PRIORITY = ("champ", "ace", "eagle", "mvp", "birdies")   # mvp covers tgf_mvp
MAX_EXTRA = 2
# kept for the plain default (a link whose reasons can't be read)
QUESTIONS = (QUESTION_SETS["mvp"][0], QUESTION_SETS["mvp"][1], LAST_QUESTION)

# The words. Changing any of them changes the hash and locks the send until
# Kerry stamps the new hash.
SUBJECT = "{first_name}, a quick word for the recap?"
BODY = "Hi {first_name},<br><br>Great {day} at {course}. {why}"
ASK = ("We'd love a quote or two for the recap. A few quick questions, about two "
       "minutes, right on your phone.")
CONSENT_NOTE = ("At the end we'll ask whether we have your permission to use your "
                "quotes in the event recap. Nothing is used unless you say yes.")
BUTTON = "Answer a few quick questions"
SIGN = "See you on the course,<br>The Golf Fellowship"
# Kerry 10/30: a Yes / No permission question, not a tick box
CONSENT_LABEL = "Do you give us permission to use your quotes in the event recap?"
CONSENT_YES = "Yes"
CONSENT_NO = "No"
THANKS = "Thanks! That's everything."
REASON_WORDS = {"champ": "You won the {race}!",
                "champ_tied": "You're a co-champion of the {race}!",
                "mvp": "You were the City MVP!", "tgf_mvp": "You were the TGF MVP!",
                "both_mvp": "You were the City MVP and the TGF MVP!",
                "ace": "Hole-in-one on hole {holes}!",
                "eagle": "Eagle on hole {holes}!",
                "birdies": "{n} birdies!",
                "birdies_row": "{n} birdies in a row!",
                "birdies_some_row": "{n} birdies, and {streak} were in a row!",
                # with an MVP: what got them there (Kerry: "You were city MVP,
                # and you had 4 birdies that helped get you there!")
                "mvp_with": "{mvp_lead}, and {what} helped get you there!",
                # several card achievements, no MVP
                "plus": "{first}, plus {rest}!"}
NOUNS = {"ace": "the hole-in-one on {holes}", "eagle": "the eagle on {holes}",
         "birdies": "your {n} birdies", "birdies_row": "your {n} birdies in a row",
         "birdies_some_row": "your {n} birdies ({streak} in a row)"}
PLUS_NOUNS = {"ace": "a hole-in-one on hole {holes}", "eagle": "an eagle on hole {holes}",
              "birdies": "{n} birdies", "birdies_row": "{n} birdies in a row",
              "birdies_some_row": "{n} birdies ({streak} in a row)"}
FOLLOWUP_SYSTEM = (
    "You are a friendly golf reporter for The Golf Fellowship, a golf community in Texas, "
    "doing a two-minute post-round interview by text. You know why the player was asked "
    "(their achievement today); when it fits, tie your question to it. Read the player's "
    "answer and ask ONE "
    "short, warm follow-up question (at most 20 words) that draws out a specific, quotable "
    "detail: a club, a distance, a moment, a feeling. Plain words, no preamble, no quotes "
    "around it, just the question. If the answer gives nothing to follow up, reply NONE.")


def template_hash() -> str:
    raw = "\x1f".join((SUBJECT, BODY, ASK, CONSENT_NOTE, BUTTON, SIGN, CONSENT_LABEL, CONSENT_YES, CONSENT_NO, THANKS,
                       LAST_QUESTION, *[q for k in sorted(QUESTION_SETS) for q in QUESTION_SETS[k]],
                       *[EXTRA_QUESTION[k] for k in sorted(EXTRA_QUESTION)],
                       *[REASON_WORDS[k] for k in sorted(REASON_WORDS)],
                       *[NOUNS[k] for k in sorted(NOUNS)], *[PLUS_NOUNS[k] for k in sorted(PLUS_NOUNS)]))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _setting(key, db_path=None):
    from email_parser import database as db
    try:
        return db.get_app_setting(key, db_path=db_path)
    except Exception:
        return None


def _json(key, db_path=None) -> dict:
    try:
        v = json.loads(_setting(key, db_path) or "{}")
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def _save(key, obj, db_path=None) -> None:
    from email_parser import database as db
    db.set_app_setting(key, json.dumps(obj, sort_keys=True, default=str), db_path=db_path)


def dial_on(db_path=None) -> bool:
    return (_setting(DIAL, db_path) or "").strip().lower() == "on"


def approved(db_path=None) -> bool:
    return (_setting(APPROVAL_KEY, db_path) or "").strip() == template_hash()


# ── who qualifies ──────────────────────────────────────────────────────────
def qualify(event_id: int, db_path=None) -> list:
    """[{customer_id, name, first_name, email, reasons: [{kind, ...}], why}]
    from the published cards and the recorded payouts. Read-only."""
    from email_parser import database as db
    from email_parser.results_email import event_facts
    from email_parser.invitations import _send_email
    f = event_facts(int(event_id), db_path=db_path)
    found: dict = {}
    for cid, rows in (f.get("payouts") or {}).items():
        for x in rows:
            if x.get("category") in ("mvp", "tgf_mvp"):
                found.setdefault(int(cid), []).append({"kind": x["category"]})
    for cid, c in (f.get("cards") or {}).items():
        birdies, eagles, aces = [], [], []
        for h in c["holes"]:
            par = (c["meta"].get(int(h["hole_number"])) or {}).get("par")
            if h["strokes"] is None or not par:
                continue
            d = int(h["strokes"]) - int(par)
            if int(h["strokes"]) == 1:
                aces.append(int(h["hole_number"]))
            elif d <= -2:
                eagles.append(int(h["hole_number"]))
            elif d == -1:
                birdies.append(int(h["hole_number"]))
        if aces:
            found.setdefault(int(cid), []).append({"kind": "ace", "holes": aces})
        if eagles:
            found.setdefault(int(cid), []).append({"kind": "eagle", "holes": eagles})
        if len(birdies) >= 3:
            found.setdefault(int(cid), []).append({"kind": "birdies", "n": len(birdies),
                                                   "holes": birdies, "streak": _streak(birdies)})
    for cid, r in race_winners(int(event_id), f, db_path=db_path):
        found.setdefault(int(cid), []).insert(0, r)
    out = []
    with db._connect(db_path) as conn:
        for cid, reasons in sorted(found.items()):
            r = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                             (cid,)).fetchone()
            first = ((r["first_name"] if r else "") or "").strip()
            name = " ".join(x for x in (first, ((r["last_name"] if r else "") or "").strip()) if x)
            out.append({"customer_id": cid, "name": name or f"#{cid}", "first_name": first or "there",
                        "email": _send_email(conn, cid), "reasons": reasons,
                        "why": reason_text(reasons), "questions": questions_for(reasons)})
    return out


def race_final_event(event_id: int, db_path=None) -> dict:
    """Which races END at this event: {"fall": bool, "month": bool}.
    Fall: the FALL CHAMPIONSHIP (the races' last event, as the event-day
    email reads it). Month: no other event later in the same month."""
    import re
    ev = _event(event_id, db_path) or {}
    name = ev.get("item_name") or ""
    d = str(ev.get("event_date") or "")[:10]
    month = False
    if len(d) == 10:
        from email_parser import database as db
        with db._connect(db_path) as conn:
            later = conn.execute(
                "SELECT COUNT(*) FROM events WHERE substr(event_date, 1, 7) = ? "
                "AND substr(event_date, 1, 10) > ? AND id != ?",
                (d[:7], d, int(event_id))).fetchone()[0]
        month = not later
    return {"fall": bool(re.search(r"FALL\s+CHAMPIONSHIP", name, re.I)), "month": month}


def race_winners(event_id: int, facts: dict, db_path=None) -> list:
    """[(customer_id, reason)] for the points races this event finishes, read
    from the standings the closeout chain's points step has just rebuilt
    (Kerry 10/30: "Same timeline for the race winners. Points need to be
    tallied and finalized at same time as the rest of the leaderboard
    results"). Fall: the best-ranked ENROLLED player(s), as the money and
    the title are decided (database._race_champions). Month: the top
    points (winner takes all; ties share)."""
    out = []
    try:
        ends = race_final_event(event_id, db_path)
        if ends["fall"]:
            from email_parser.database import _race_champions
            from email_parser.results_email import FALL_RACE
            for key, race in (facts.get("races") or {}).items():
                champs = _race_champions(race.get("rows") or [])
                label = FALL_RACE.get(key, (None, None, key.title()))[2]
                for c in champs:
                    if c.get("customer_id"):
                        out.append((int(c["customer_id"]),
                                    {"kind": "champ", "race": f"{label} Fall Points Race",
                                     "span": "Fall", "tied": len(champs) > 1}))
        st = (facts.get("month") or {}).get("standings") or []
        if ends["month"] and st and (st[0].get("points") or 0) > 0:
            top = st[0].get("points")
            name = ((facts.get("month") or {}).get("name") or "").strip() or "this month"
            name = name.split()[0].title() if name != "this month" else name
            winners = [x for x in st if x.get("points") == top and x.get("customer_id")]
            for x in winners:
                out.append((int(x["customer_id"]),
                            {"kind": "champ", "race": f"{name} Points Race",
                             "span": "month", "tied": len(winners) > 1}))
    except Exception:
        logger.exception("ai interview: race winners unreadable for %s", event_id)
    return out


def _streak(holes: list) -> int:
    """The longest run of birdies on consecutive holes."""
    best = run = 0
    prev = None
    for h in sorted(holes):
        run = run + 1 if prev is not None and h == prev + 1 else 1
        best, prev = max(best, run), h
    return best


def _holes(r: dict) -> str:
    hs = [str(h) for h in r.get("holes") or []]
    return hs[0] if len(hs) == 1 else ", ".join(hs[:-1]) + " and " + hs[-1] if hs else ""


def _birdie_key(r: dict) -> str:
    n, k = int(r.get("n") or 0), int(r.get("streak") or 0)
    return "birdies_row" if n and k == n else "birdies_some_row" if k >= 3 else "birdies"


def _fmt(w: str, r: dict) -> str:
    return w.format(holes=_holes(r), n=r.get("n"), streak=r.get("streak"),
                    race=r.get("race") or "", span=r.get("span") or "season")


def _cap(t: str) -> str:
    return t[:1].upper() + t[1:]


def _primary(reasons: list) -> list:
    """The reasons, biggest first (ace, eagle, MVP, birdies); both MVPs count once."""
    def key(r):
        k = "mvp" if r.get("kind") in ("mvp", "tgf_mvp") else r.get("kind")
        return PRIORITY.index(k) if k in PRIORITY else len(PRIORITY)
    out, seen_mvp = [], False
    for r in sorted(reasons, key=key):
        if r.get("kind") in ("mvp", "tgf_mvp"):
            if seen_mvp:
                continue
            seen_mvp = True
        out.append(r)
    return out


def reason_text(reasons: list) -> str:
    """The leading comment: why they're being asked, every achievement in one line."""
    champs = [_fmt(REASON_WORDS["champ_tied" if r.get("tied") else "champ"], r)
              for r in reasons if r.get("kind") == "champ"]
    rest = reason_text([r for r in reasons if r.get("kind") != "champ"]) if champs else ""
    if champs:
        return " ".join(champs + ([rest] if rest else []))
    kinds = {r.get("kind") for r in reasons}
    mvp = ("both_mvp" if {"mvp", "tgf_mvp"} <= kinds else "mvp" if "mvp" in kinds
           else "tgf_mvp" if "tgf_mvp" in kinds else None)
    card = [r for r in _primary(reasons) if r.get("kind") in ("ace", "eagle", "birdies")]
    def key(r):
        return _birdie_key(r) if r["kind"] == "birdies" else r["kind"]
    if mvp and card:
        what = " and ".join(_fmt(NOUNS[key(r)], r) for r in card)
        return REASON_WORDS["mvp_with"].format(mvp_lead=REASON_WORDS[mvp].rstrip("!"), what=what)
    if mvp:
        return REASON_WORDS[mvp]
    if len(card) == 1:
        return _fmt(REASON_WORDS[key(card[0])], card[0])
    if card:
        nouns = [_fmt(PLUS_NOUNS[key(r)], r) for r in card]
        return REASON_WORDS["plus"].format(first=_cap(nouns[0]), rest=" and ".join(nouns[1:]))
    return ""


def questions_for(reasons: list) -> list:
    """The biggest achievement's two questions, one more for each other
    achievement (at most MAX_EXTRA), then LAST_QUESTION."""
    rs = _primary(reasons)
    if not rs:
        return list(QUESTIONS)
    def k(r):
        return "mvp" if r.get("kind") in ("mvp", "tgf_mvp") else r.get("kind")
    first = rs[0]
    out = [_fmt(q, first) for q in QUESTION_SETS[k(first)]]
    for r in rs[1:1 + MAX_EXTRA]:
        q = _fmt(EXTRA_QUESTION[k(r)], r)
        if q not in out:
            out.append(q)
    if k(first) == "champ":
        out = out[:3] + [q for q in out[3:] if q not in out[:3]]
    return out + [LAST_QUESTION]


def person_questions(event_id: int, customer_id: int, db_path=None) -> list:
    """This person's questions: as sent (saved with the invitation), else
    worked out now (a staff preview), else the plain default."""
    rec = (_json(STATE_KEY.format(int(event_id)), db_path).get("people") or {}).get(str(customer_id)) or {}
    if rec.get("questions"):
        return list(rec["questions"])
    try:
        for p in qualify(int(event_id), db_path=db_path):
            if p["customer_id"] == int(customer_id):
                return list(p["questions"])
    except Exception:
        logger.warning("ai interview: questions for %s/%s unreadable", event_id, customer_id,
                       exc_info=True)
    return list(QUESTIONS)


# ── signed links (the handicap ask's pattern, its own prefix) ─────────────
def _secret() -> bytes:
    from email_parser.memberships import _secret as s
    return s()


def make_token(customer_id: int, event_id: int, preview: bool = False,
               now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    p = {"c": int(customer_id), "v": int(event_id),
         "x": int((now + timedelta(days=TOKEN_DAYS)).timestamp())}
    if preview:
        p["p"] = 1
    body = base64.urlsafe_b64encode(json.dumps(p, separators=(",", ":")).encode()).rstrip(b"=").decode()
    sig = hmac.new(_secret(), b"ivw." + body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def verify_token(token: str) -> dict | None:
    token = (token or "").strip()
    if "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    want = hmac.new(_secret(), b"ivw." + body.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, want):
        return None
    try:
        p = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(p.get("x", 0)) < int(datetime.utcnow().timestamp()):
        return None
    return p


def interview_url(token: str) -> str:
    from email_parser.score_entry import _base_url
    return f"{_base_url()}/interview/{token}"


# ── the email ──────────────────────────────────────────────────────────────
def _event(event_id: int, db_path=None) -> dict | None:
    from email_parser import database as db
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
    return dict(r) if r else None


def _day(ev: dict) -> str:
    try:
        return date.fromisoformat(str(ev.get("event_date"))[:10]).strftime("%A")
    except ValueError:
        return "round"


def build_message(person: dict, ev: dict, preview: bool = False) -> dict:
    from email_parser.event_day_email import frame
    from email_parser.invitations import _display_name
    first = person.get("first_name") or "there"
    link = interview_url(make_token(person["customer_id"], ev["id"], preview=preview))
    course = _display_name(ev)
    subject = SUBJECT.format(first_name=first)
    button = (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
              f'style="margin:16px 0;"><tr><td><a href="{_e(link)}" style="display:inline-block;'
              f'background:#E87C3E;color:#ffffff;font:bold 16px Georgia,serif;text-decoration:none;'
              f'padding:12px 24px;border-radius:999px;">{_e(BUTTON)}</a></td></tr></table>')
    inner = (f"<p>{BODY.format(first_name=_e(first), day=_e(_day(ev)), course=_e(course), why=_e(person.get('why') or ''))}</p>"
             f"<p>{ASK}</p>{button}"
             f'<p style="color:#6B7280;font-size:14px;">{CONSENT_NOTE}</p><p>{SIGN}</p>')
    body = frame(inner, "THE GOLF FELLOWSHIP", "A quick word for the recap")
    held = []
    if "{" in subject + body:
        held.append("leftover {tag}")
    if not person.get("why"):
        held.append("no reason to ask")
    return {"subject": subject, "html": body, "link": link, "held": held}


def plan(event_id: int, db_path=None) -> dict:
    """The staff view: who qualifies and why, what has been sent, the locks."""
    st = _json(STATE_KEY.format(int(event_id)), db_path)
    people = []
    try:
        q = qualify(event_id, db_path=db_path)
    except Exception as exc:
        logger.exception("ai interview: qualify failed for %s", event_id)
        return {"error": f"{type(exc).__name__}: {exc}"}
    sent = st.get("people") or {}
    for p in q:
        people.append({"customer_id": p["customer_id"], "name": p["name"], "why": p["why"],
                       "email_on_file": bool(p["email"]),
                       "sent": (sent.get(str(p["customer_id"])) or {}).get("sent_at")})
    ans = _json(ANSWERS_KEY.format(int(event_id)), db_path)
    return {"event_id": int(event_id), "dial": DIAL, "dial_on": dial_on(db_path),
            "template_hash": template_hash(), "approval_key": APPROVAL_KEY,
            "approved": approved(db_path), "qualifies": people,
            "sent_at": st.get("sent_at"),
            "answers": {k: {"consent": v.get("consent"), "answered": len(v.get("answers") or []),
                            "finished_at": v.get("finished_at")} for k, v in ans.items()},
            "consented_quotes": consented_quotes(event_id, db_path=db_path)}


def send_preview(event_id: int, to_address: str | None = None, db_path=None) -> dict:
    """ONE sample to STAFF only. The link is a preview link: it saves nothing."""
    from email_parser.event_day_email import _creds, _graph_send
    from email_parser.recap_mail import staff_only, _addrs
    to = _addrs(to_address) or [DEFAULT_PREVIEW_TO]
    bad = staff_only(to, lambda k: _setting(k, db_path))
    if bad:
        return {"error": f"an interview preview goes to TGF staff only; refused {bad}"}
    ev = _event(event_id, db_path)
    if not ev:
        return {"error": f"no event {event_id}"}
    pl = plan(event_id, db_path=db_path)
    q = [p for p in (pl.get("qualifies") or [])]
    sample = ({"customer_id": q[0]["customer_id"], "first_name": (q[0]["name"] or "there").split()[0],
               "why": q[0]["why"]} if q else
              {"customer_id": 18, "first_name": "Kerry", "why": REASON_WORDS["birdies"].format(n=3)})
    msg = build_message(sample, ev, preview=True)
    lines = "".join(f"<li>{_e(p['name'])}: {_e(p['why'])}"
                    f"{'' if p['email_on_file'] else ' (no email on file)'}</li>" for p in q) or "<li>nobody yet</li>"
    head = (f"<p><strong>Interview PREVIEW</strong> for {_e(ev.get('item_name'))}. Nothing has been sent "
            f"to any player. The button opens the real page; a preview link saves nothing.</p>"
            f"<p>Qualifies now:</p><ul>{lines}</ul>"
            f"<p>Dial <code>{DIAL}</code>: {'ON' if pl.get('dial_on') else 'off'}. Wording "
            f"<code>{template_hash()}</code>: {'APPROVED' if pl.get('approved') else 'NOT approved'}.</p><hr>")
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server", "link": msg["link"]}
    subject = f"PREVIEW: {msg['subject']}"
    ok = _graph_send(creds, ",".join(to), subject, head + msg["html"])
    return {"status": "sent" if ok else "failed", "to": to, "subject": subject, "link": msg["link"]}


def _payouts_recorded(event_id: int, db_path=None) -> bool:
    """The MVPs (recorded payouts) are known, and, when a points race ends
    at this event, the points are tallied (the chain's points step)."""
    from email_parser import closeout_chain as cc
    steps = cc.state(event_id, db_path).get("steps") or {}
    if not steps.get("payouts", {}).get("ok"):
        return False
    ends = race_final_event(event_id, db_path)
    if ends["fall"] or ends["month"]:
        return bool(steps.get("points", {}).get("ok"))
    return True


def _wait_minutes(db_path=None) -> int:
    try:
        return int(_setting(WAIT_KEY, db_path) or DEFAULT_WAIT)
    except ValueError:
        return DEFAULT_WAIT


def closeout_hook(event_id: int, db_path=None, now=None, sender=None) -> dict | None:
    """From scoring_window.tick after CLOSEOUT START. Nothing while the dial is
    off or the wording is unstamped; once per event; never raises."""
    try:
        if not dial_on(db_path) or not approved(db_path):
            return None
        key = STATE_KEY.format(int(event_id))
        st = _json(key, db_path)
        if not st.get("sent_at"):
            # first pass at CLOSEOUT START: eagles and birdies from the cards,
            # and the MVPs too if the money is already recorded
            if _payouts_recorded(event_id, db_path):
                st["payouts_pass"] = "with the first pass"
            return _send_all(event_id, st, db_path=db_path, now=now, sender=sender)
        if st.get("payouts_pass") or not _payouts_recorded(event_id, db_path):
            return None
        # second pass: the MVPs, once payouts are recorded, while the recap
        # still waits; after the wait the recap has gone, so nobody new is asked
        from email_parser.timezone_utils import now_central
        t = (now or now_central()).replace(tzinfo=None)
        t0 = datetime.strptime(st["sent_at"], "%Y-%m-%d %H:%M")
        if (t - t0).total_seconds() / 60 >= _wait_minutes(db_path):
            st["payouts_pass"] = "skipped: payouts recorded after the recap wait"
            _save(key, st, db_path)
            return {"skipped": st["payouts_pass"]}
        st["payouts_pass"] = t.strftime("%Y-%m-%d %H:%M")
        return _send_all(event_id, st, db_path=db_path, now=now, sender=sender)
    except Exception:
        logger.exception("ai interview: closeout hook failed for %s", event_id)
        return {"error": "failed (logged)"}


def _send_all(event_id, st, db_path=None, now=None, sender=None) -> dict:
    from email_parser import database as db
    from email_parser.timezone_utils import now_central
    ev = _event(event_id, db_path)
    if not ev:
        return {"error": f"no event {event_id}"}
    if sender is None:
        from email_parser.event_day_email import _creds, _graph_send
        creds = _creds()
        if not creds:
            return {"error": "Email credentials not configured on server"}
        sender = lambda to, s, h: _graph_send(creds, to, s, h)   # noqa: E731
    now = now or now_central()
    people = st.setdefault("people", {})
    sent, skipped = [], []
    for p in qualify(event_id, db_path=db_path):
        k = str(p["customer_id"])
        if (people.get(k) or {}).get("sent_at"):
            continue
        if not p["email"]:
            skipped.append({"customer_id": p["customer_id"], "why": "no email on file"})
            people[k] = {"why": p["why"], "skipped": "no email on file"}
            continue
        msg = build_message(p, ev)
        if msg["held"]:
            skipped.append({"customer_id": p["customer_id"], "why": msg["held"]})
            continue
        ok = False
        try:
            ok = bool(sender(p["email"], msg["subject"], msg["html"]))
        except Exception:
            logger.exception("ai interview send failed for %s", p["customer_id"])
        people[k] = {"why": p["why"], "questions": p["questions"],
                     "sent_at": now.strftime("%Y-%m-%d %H:%M") if ok else None, "failed": not ok}
        if ok:
            sent.append(p["customer_id"])
        try:
            db.log_message({"event_name": ev.get("item_name"), "channel": "email",
                            "recipient_name": p["name"], "recipient_address": p["email"],
                            "subject": msg["subject"], "body_preview": "post-round interview",
                            "status": "sent" if ok else "failed", "sent_by": "ai_interview"},
                           db_path=db_path)
        except Exception:
            pass
    st.setdefault("sent_at", now.strftime("%Y-%m-%d %H:%M"))   # the first pass starts the wait
    _save(STATE_KEY.format(int(event_id)), st, db_path)
    try:
        db.log_agent_action("ai-interview", "ai_interview_sent",
                            f"event {event_id}: {len(sent)} sent, {len(skipped)} skipped",
                            db_path=db_path)
    except Exception:
        pass
    return {"sent": sent, "skipped": skipped}


def recap_wait(event_ids: list, db_path=None, now=None) -> str | None:
    """The recap step waits (closeout_chain.step_recap) while the first
    invitations went out less than `ai_interview_wait_minutes` (90) ago and
    someone has not finished.
    None when the dial is off, nothing was sent, or every invitee finished."""
    try:
        if not dial_on(db_path):
            return None
        from email_parser.timezone_utils import now_central
        now = (now or now_central()).replace(tzinfo=None)
        wait = _wait_minutes(db_path)
        for eid in event_ids:
            st = _json(STATE_KEY.format(int(eid)), db_path)
            if not st.get("sent_at"):
                continue
            t0 = datetime.strptime(st["sent_at"], "%Y-%m-%d %H:%M")
            left = wait - (now - t0).total_seconds() / 60
            if left > 0 and not st.get("payouts_pass"):
                # the MVPs' invitations go when the money is recorded; the
                # recap never goes before them
                return (f"waiting up to {int(left) + 1} more minute(s) for the MVP and race "
                        f"winner interview invitations (event {eid}: payouts or points not in yet)")
            invited = {k for k, v in (st.get("people") or {}).items() if v.get("sent_at")}
            done = {k for k, v in _json(ANSWERS_KEY.format(int(eid)), db_path).items()
                    if v.get("finished_at")}
            if not invited - done:
                continue
            if left > 0:
                return (f"waiting up to {int(left) + 1} more minute(s) for interview answers "
                        f"(event {eid}: {len(invited - done)} not finished)")
        return None
    except Exception:
        logger.exception("ai interview: recap wait check failed")
        return None


# ── the page ───────────────────────────────────────────────────────────────
def describe(token: str, db_path=None) -> dict:
    p = verify_token(token)
    if not p:
        return {"ok": False, "error": "This link isn't valid any more."}
    from email_parser import database as db
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT first_name FROM customers WHERE customer_id = ?", (p["c"],)).fetchone()
    ev = _event(p["v"], db_path) or {}
    st = _json(STATE_KEY.format(int(p["v"])), db_path)
    rec = _json(ANSWERS_KEY.format(int(p["v"])), db_path).get(str(p["c"])) or {}
    why = (st.get("people") or {}).get(str(p["c"]), {}).get("why") or ""
    if not why:
        try:
            why = next((x["why"] for x in qualify(int(p["v"]), db_path=db_path)
                        if x["customer_id"] == int(p["c"])), "")
        except Exception:
            why = ""
    return {"ok": True, "customer_id": p["c"], "event_id": p["v"], "preview": bool(p.get("p")),
            "first_name": ((r[0] if r else "") or "").strip(), "event": ev.get("item_name") or "",
            "day": _day(ev) if ev else "", "why": why,
            "questions": person_questions(p["v"], p["c"], db_path=db_path), "consent_label": CONSENT_LABEL, "consent_yes": CONSENT_YES, "consent_no": CONSENT_NO, "thanks": THANKS,
            "finished": bool(rec.get("finished_at")), "consent": rec.get("consent"),
            "ai": ai_available()}


def ai_available() -> bool:
    import os
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _clean(text) -> str:
    return " ".join(str(text or "").split())[:MAX_ANSWER]


def record_answer(token: str, q: int, text: str, followup_q: str | None = None,
                  db_path=None, ask=None) -> dict:
    """Store one answer (a main question, or the follow-up to it). Returns the
    follow-up to ask, if any. A preview link stores nothing."""
    p = verify_token(token)
    if not p:
        return {"ok": False, "error": "This link isn't valid any more."}
    try:
        q = int(q)
    except (TypeError, ValueError):
        return {"ok": False, "error": "bad question"}
    qs = person_questions(p["v"], p["c"], db_path=db_path)
    if not 0 <= q < len(qs):
        return {"ok": False, "error": "bad question"}
    text = _clean(text)
    is_followup = bool(followup_q)
    if not p.get("p"):
        key = ANSWERS_KEY.format(int(p["v"]))
        allans = _json(key, db_path)
        rec = allans.setdefault(str(p["c"]), {"answers": []})
        if rec.get("finished_at"):
            return {"ok": False, "error": "Already finished. Thank you!"}
        rec.setdefault("answers", [])
        rec["answers"] = [a for a in rec["answers"]
                          if not (a.get("q") == q and bool(a.get("followup")) == is_followup)]
        rec["answers"].append({"q": q, "question": _clean(followup_q) if is_followup else qs[q],
                               "answer": text, "followup": is_followup,
                               "at": datetime.utcnow().strftime("%Y-%m-%d %H:%M")})
        _save(key, allans, db_path)
    nxt = None
    if not is_followup and text:
        why = ((_json(STATE_KEY.format(int(p["v"])), db_path).get("people") or {})
               .get(str(p["c"])) or {}).get("why") or ""
        nxt = followup(qs[q], text, ask=ask, db_path=db_path, why=why)
    return {"ok": True, "followup": nxt}


def followup(question: str, answer: str, ask=None, db_path=None, why: str = "") -> str | None:
    """One short follow-up question from the recap writer's model, or None."""
    if ask is None:
        if not ai_available():
            return None
        ask = _ask_claude
    try:
        from email_parser.recap_writer import model
        out = (ask(FOLLOWUP_SYSTEM, (f"Why they were asked: {why}\n" if why else "") + f"Question: {question}\nPlayer's answer: {answer}",
                   model(db_path)) or "").strip().strip('"').strip()
    except Exception:
        logger.warning("ai interview: follow-up failed (plain form continues)", exc_info=True)
        return None
    if not out or out.upper().startswith("NONE") or len(out) > 200:
        return None
    return out


def _ask_claude(system: str, user: str, model_id: str) -> str:
    """The recap writer's call shape (recap_writer._client_create), short and
    with a timeout so the page never hangs."""
    import os
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=AI_TIMEOUT,
                                 max_retries=0)
    msg = client.messages.create(model=model_id, max_tokens=1024, system=system,
                                 messages=[{"role": "user", "content": user}])
    return "".join(getattr(b, "text", "") for b in msg.content).strip()


def finish(token: str, consent: bool, answers: dict | None = None, db_path=None) -> dict:
    """The last tap: Yes / No to the permission question (and, from the no-JS form, all the
    answers at once)."""
    p = verify_token(token)
    if not p:
        return {"ok": False, "error": "This link isn't valid any more."}
    if p.get("p"):
        return {"ok": True, "preview": True}
    key = ANSWERS_KEY.format(int(p["v"]))
    allans = _json(key, db_path)
    rec = allans.setdefault(str(p["c"]), {"answers": []})
    if answers:
        qs = person_questions(p["v"], p["c"], db_path=db_path)
        for i in range(len(qs)):
            t = _clean(answers.get(i) or answers.get(str(i)))
            if t:
                rec["answers"] = [a for a in rec.get("answers") or []
                                  if not (a.get("q") == i and not a.get("followup"))]
                rec["answers"].append({"q": i, "question": qs[i], "answer": t,
                                       "followup": False,
                                       "at": datetime.utcnow().strftime("%Y-%m-%d %H:%M")})
    rec["consent"] = bool(consent)
    rec["finished_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    _save(key, allans, db_path)
    return {"ok": True, "consent": bool(consent)}


def consented_quotes(event_id: int, db_path=None) -> list:
    """What the recap may choose from: answers from players who said Yes to
    the permission question. The recap writer picks the best one or two; it
    never has to use them all."""
    out = []
    for cid, rec in _json(ANSWERS_KEY.format(int(event_id)), db_path).items():
        if rec.get("consent") is not True:
            continue
        for a in sorted(rec.get("answers") or [], key=lambda a: (a.get("q", 0), bool(a.get("followup")))):
            if a.get("answer"):
                out.append({"customer_id": int(cid), "question": a.get("question"),
                            "answer": a["answer"]})
    return out
