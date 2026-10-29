"""THE HANDICAP ASK (Kerry 2026-10-16: "We need some kind of automatic ask
for new people that we don't have handicap for" ... "Build it").

Why: a non-member cannot enter the individual net games or MVP; the
handicap is for the TEAM game, "so that their team and them can compete
together" (Kerry). Mockups approved 10/16 (artifact 7GeWZuGQEaG1iHBDGgmwDC).

WHO: a player on an upcoming event's roster with no TGF index and no
starting handicap (`handicap_warnings.missing_handicaps`, cases `new` and
`few_rounds`, a customer_id and a sendable address). Asked ONCE per person,
the moment their order is saved (Kerry: "as soon as we get a registration"),
whatever events they are on; one reminder when their next event is two days
out and they have not answered.

THE PAGE (`/handicap/<token>`, a signed link, no login; signed links are not
member logins, CA #731). Three answers:
  ghin   GHIN number AND latest index (Kerry: "Along with their GHIN number IT
         SHOULD ASK WHAT THEIR LATEST INDEX IS"). The Tracker cannot look an
         index up: GHIN shows it only to a logged-in account. Sets the
         starting handicap to 75% of the index (the intro rule) and saves the
         GHIN number on the profile. Status `set`.
  other  another service (TheGrint, club, Golf Genius, 18Birdies, Other) and
         its index. 75% applied so they can play; status `check` until a
         manager taps Looks right (Kerry: "you'd want to vet that").
  none   their usual 18-hole score (Kerry: "for 18 holes not just for nine").
         Nothing set; status `need`, the manager sets the number.
The answer is written only by the page's form POST, never by a GET, so a mail
scanner that opens the link answers nothing.

STATE: app setting `handicap_ask` (JSON by customer_id), no new table.

SENDS are locked twice: dial `handicap_ask_auto` = on AND the wording carries
Kerry's stamp (`handicap_ask_approved` = `template_hash()`). Previews go to
staff only (bridge `scoring-handicap-ask`).
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

STATE_KEY = "handicap_ask"
AUTO_DIAL = "handicap_ask_auto"
APPROVAL_KEY = "handicap_ask_approved"
DEFAULT_PREVIEW_TO = "kerry@thegolffellowship.com"
INTRO_PCT = 0.75
LOOKAHEAD_DAYS = 21
REMIND_DAYS_BEFORE = 2
LOCK_REMIND_MINUTES = 60      # Kerry 10/26 (#2307 item 5): one more at 4:00 PM, an hour before the lock
TOKEN_DAYS = 60
SEND_HOURS = (7, 20)          # Central; reminders only by day
SERVICES = ("TheGrint", "Club handicap", "Golf Genius", "18Birdies", "Other")
ASK_CASES = ("new", "few_rounds")

# The words. Structure is in code; changing any of these changes the hash and
# locks the send until Kerry stamps the new hash.
SUBJECT = "One quick thing before {day}, {first_name}"
REMINDER_SUBJECT = "Reminder: your handicap for {day}, {first_name}"
BODY = ("Hi {first_name},<br><br>Thanks for signing up. We're glad you're coming out.")
REMINDER_BODY = ("Hi {first_name},<br><br>We're looking forward to {day}. We still "
                 "don't have a handicap for you.")
WHY = ("We don't have a handicap for you yet. It sets your strokes in the team game, "
       "so you and your group can compete on even terms. It takes about 30 seconds.")
BUTTON = "Add my handicap"
NO_HCP = "No handicap? No problem. Tap the button and tell us what you usually shoot."
SIGN = "See you on the course,<br>The Golf Fellowship"
PAGE_NOTE_HEAD = "TGF keeps its own handicaps"
PAGE_NOTE = ("What you enter here is only a temporary starting point. After just 27 holes "
             "with TGF, you'll have your own TGF handicap, figured from your rounds with us.")
GHIN_NOTE = ("We start new players at 75% of their index for their first rounds with us. "
             "It's used for your group's team score.")
NONE_NOTE = ("The chapter manager uses this to set your starting handicap before {day}. "
             "You don't need to do anything else.")
VENMO_WHY = ("If you win the team game, a closest to the pin, or a side game you entered, "
             "we pay you by Venmo.")
VENMO_GET = "No Venmo? It's free and takes a couple of minutes."
VENMO_URL = "https://venmo.com/"
DONE_VENMO = "Venmo saved: @{venmo}. Winnings go there."
DONE_NO_VENMO = ("When you set up Venmo, tap the button in our email again to add your username, "
                 "so we can pay your winnings.")
VENMO_ONLY_HEAD = "Add your Venmo"
VENMO_ONLY = "We have your handicap answer. Add your Venmo username so we can pay any winnings."
DONE_LABEL = "Your temporary starting handicap"
DONE_SET = "75% of the {index} index you entered."
# Kerry 10/27 (CoS #2426), the no-index rule. Deliberately OUTSIDE
# template_hash(): adding it to the hash would lock the live ask until
# re-stamped. Kerry reviews it with the build.
DONE_RULE = "From the {low} you usually shoot for 18, minus 72."
# Kerry 10/28 (Event Ops #2474-B, #2475-1): name the number, and lock the
# link after the answer. Also OUTSIDE template_hash() so the live ask is not
# re-locked; Kerry stamps the final wording with the build.
DONE_RULE_TGF = "Your starting TGF Handicap Index is {start}, from your low score of {low} minus 72."
DONE_LOCKED = ("Your answer is saved and can't be changed from this link. If something needs "
               "to change, your chapter manager can update it.")
LOCKED_HEAD = "We have your answer"
NONE_HELP = ("Your usual 18-hole total, numbers only: your low score and your high score. "
             "Your starting TGF Handicap Index is your low score minus 72.")
LOW_MIN = 60          # Kerry: "a minimum of 60 in the low one" (no 9-hole totals)
DONE_CHECK = "75% of the {index} index you entered. The chapter manager will confirm it before {day}."
DONE_TEMP = ("This is temporary. After 27 holes with TGF, your own TGF handicap replaces it, "
             "figured from your rounds with us.")
DONE_NEED = ("The chapter manager will set your temporary starting handicap before {day}. "
             "After 27 holes with TGF, you'll have your own TGF handicap.")


def template_hash() -> str:
    raw = "\x1f".join((SUBJECT, REMINDER_SUBJECT, BODY, REMINDER_BODY, WHY, BUTTON, NO_HCP,
                       SIGN, PAGE_NOTE_HEAD, PAGE_NOTE, GHIN_NOTE, NONE_NOTE, DONE_LABEL, DONE_SET,
                       DONE_CHECK, DONE_TEMP, DONE_NEED, VENMO_WHY, VENMO_GET, VENMO_URL,
                       DONE_VENMO, DONE_NO_VENMO, VENMO_ONLY_HEAD, VENMO_ONLY))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _setting(key, db_path=None):
    from email_parser import database as db
    try:
        return db.get_app_setting(key, db_path=db_path)
    except Exception:
        return None


def approval_state(db_path=None) -> dict:
    h = template_hash()
    return {"template_hash": h, "approval_key": APPROVAL_KEY,
            "approved": (_setting(APPROVAL_KEY, db_path) or "").strip() == h}


def load_state(db_path=None) -> dict:
    try:
        s = json.loads(_setting(STATE_KEY, db_path) or "{}")
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}


def _save_state(state: dict, db_path=None) -> None:
    from email_parser import database as db
    db.set_app_setting(STATE_KEY, json.dumps(state, sort_keys=True), db_path=db_path)


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


# ---------------------------------------------------------------------------
# Signed links
# ---------------------------------------------------------------------------

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
    body = base64.urlsafe_b64encode(json.dumps(p, separators=(",", ":")).encode()
                                    ).rstrip(b"=").decode()
    sig = hmac.new(_secret(), b"hcp." + body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def verify_token(token: str) -> dict | None:
    token = (token or "").strip()
    if "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    want = hmac.new(_secret(), b"hcp." + body.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, want):
        return None
    try:
        p = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(p.get("x", 0)) < int(datetime.utcnow().timestamp()):
        return None
    return p


def ask_url(token: str) -> str:
    from email_parser.score_entry import _base_url
    return f"{_base_url()}/handicap/{token}"


# ---------------------------------------------------------------------------
# Parsing an answer (pure)
# ---------------------------------------------------------------------------

def parse_index(text) -> float | None:
    """'14.2' -> 14.2; '+2.1' (a plus handicap) -> -2.1. None when not an index."""
    t = str(text or "").strip().replace(",", ".")
    if not t:
        return None
    plus = t.startswith("+")
    try:
        v = float(t.lstrip("+"))
    except ValueError:
        return None
    if plus:
        v = -abs(v)
    return round(v, 1) if -10.0 <= v <= 54.0 else None


def starting_from_index(index: float) -> float:
    """75% to the tenth, half away from zero (14.2 -> 10.7, never the
    float's 10.6; +2.1 -> +1.6)."""
    from decimal import Decimal, ROUND_HALF_UP
    v = (Decimal(str(abs(index))) * Decimal(str(INTRO_PCT))).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return float(-v if index < 0 else v)


RULE_SET_BY = "rule:low_score_minus_72"


def starting_from_scores(ans: dict) -> float | None:
    """THE NO-INDEX RULE (Kerry 10/27, CoS #2426: "I want you to go with the
    low score minus 72 to establish their starting handicap with TGF."): the
    LOW end of the usual 18-hole score minus 72. A single score is the low
    end; a 9-hole score is doubled first. None when there is no number. A
    stated index always wins (the ghin / other answers never come here)."""
    lo = ans.get("score_low")
    if lo is None:
        return None
    eighteen = int(lo) * (2 if ans.get("nine") else 1)
    return float(eighteen - 72)


def answer_words(ans: dict) -> str:
    """The player's answer in plain words, quoted in the note and the email."""
    k = ans.get("kind")
    if k == "ghin":
        return f"GHIN {ans.get('ghin')}, index {ans.get('index')}"
    if k == "other":
        svc = ans.get("service") + (f" ({ans['service_name']})" if ans.get("service_name") else "")
        return f"{svc}, index {ans.get('index')}"
    if ans.get("score_low") is None:
        return "no handicap, and no usual score given"
    rng = (f"{ans['score_low']}" if ans["score_low"] == ans.get("score_high")
           else f"{ans['score_low']}-{ans['score_high']}")
    return f"usually shoots {rng} for {'9' if ans.get('nine') else '18'}"


def validate(form: dict) -> dict:
    """The page's form -> a clean answer, or {"error": ...}."""
    kind = (form.get("kind") or "").strip()
    if kind == "ghin":
        ghin = "".join(ch for ch in str(form.get("ghin") or "") if ch.isdigit())
        if not (5 <= len(ghin) <= 10):
            return {"error": "Please enter your GHIN number (digits only)."}
        idx = parse_index(form.get("index"))
        if idx is None:
            return {"error": "Please enter your latest handicap index, for example 14.2."}
        return {"kind": "ghin", "ghin": ghin, "index": idx}
    if kind == "other":
        svc = (form.get("service") or "").strip()
        if svc not in SERVICES:
            return {"error": "Please pick your handicap service."}
        name = " ".join(str(form.get("service_name") or "").split())[:80]
        if svc == "Other" and not name:
            return {"error": "Please tell us the name of the club or service."}
        idx = parse_index(form.get("index"))
        if idx is None:
            return {"error": "Please enter your latest handicap index, for example 17.8."}
        return {"kind": "other", "service": svc, "service_name": name, "index": idx}
    if kind == "none":
        # LOW and HIGH, the usual 18-HOLE total, both required, digits only,
        # LOW at least 60, HIGH at least LOW, no cap on HIGH (Kerry 10/28,
        # #2474-B / #2475-1: "They should only be able to enter a number. A
        # low number and a high number. It shouldn't accept non-numbers." /
        # "a minimum of 60 in the low one" / "No cap on high."). The CoS
        # readings for free text (a 9-hole total doubled, a single score is
        # the low end) are retired for this form.
        lo_s = str(form.get("score_low") or "").strip()
        hi_s = str(form.get("score_high") or "").strip()
        if not lo_s or not hi_s:
            return {"error": "Please enter both numbers: your low score and your high score for 18 holes."}
        if not (lo_s.isascii() and lo_s.isdigit() and hi_s.isascii() and hi_s.isdigit()):
            return {"error": "Numbers only, please: your low and high 18-hole scores, for example 90 and 100."}
        lo, hi = int(lo_s), int(hi_s)
        if lo < LOW_MIN:
            return {"error": f"Your low score is for 18 holes, so it should be at least {LOW_MIN}. "
                             "Please enter your usual 18-hole total."}
        if hi < lo:
            return {"error": "Your high score should be at least your low score."}
        return {"kind": "none", "score_low": lo, "score_high": hi}
    return {"error": "Please pick one of the three choices."}


def parse_venmo(text) -> str | None:
    """A Venmo username, bare (no @): 5-30 letters, numbers, - or _.
    '' -> None (not given); a bad value -> raises ValueError."""
    import re
    t = str(text or "").strip()
    if t.lower().startswith("https://venmo.com/"):
        t = t.split("venmo.com/", 1)[1].split("?")[0].strip("/")
        if t.lower().startswith("u/"):
            t = t[2:]
    t = t.lstrip("@").strip()
    if not t:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,30}", t):
        raise ValueError("That doesn't look like a Venmo username. It's the @name in your Venmo app, "
                         "for example @Jane-Smith-12.")
    return t


# ---------------------------------------------------------------------------
# Who to ask
# ---------------------------------------------------------------------------

def _upcoming_events(conn, today: str, days: int = LOOKAHEAD_DAYS) -> list[dict]:
    # TODAY counts (Kerry 2026-10-20, Adam Wilson signed up at 9:02 AM for that
    # evening: "there should be no limitations on an email being sent to
    # someone that we don't have a handicap for...or Venmo").
    end = (date.fromisoformat(today) + timedelta(days=days)).isoformat()
    return [dict(r) for r in conn.execute(
        "SELECT * FROM events WHERE COALESCE(status, 'active') = 'active' "
        "AND substr(event_date, 1, 10) >= ? AND substr(event_date, 1, 10) <= ? "
        "ORDER BY event_date, id", (today, end)).fetchall()]


def candidates(today: str | None = None, db_path=None) -> list[dict]:
    """One row per person with no handicap on an upcoming roster (earliest
    event first), with their address. Read-only."""
    from email_parser import database as db
    from email_parser.handicap_warnings import missing_handicaps
    from email_parser.invitations import _send_email
    from email_parser.timezone_utils import today_central_str
    today = today or today_central_str()
    conn = db.get_connection(db_path)
    try:
        evs = _upcoming_events(conn, today)
        out, seen = [], set()
        for ev in evs:
            try:
                m = missing_handicaps(ev["id"], db_path=db_path)
            except Exception:
                logger.exception("handicap ask: missing read failed for event %s", ev["id"])
                continue
            for p in m.get("players") or []:
                cid = p.get("customer_id")
                if not cid or p.get("case") not in ASK_CASES or int(cid) in seen:
                    continue
                seen.add(int(cid))
                r = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                                 (int(cid),)).fetchone()
                out.append({"customer_id": int(cid), "name": p.get("name"),
                            "first_name": (r[0] if r else "") or "",
                            "email": _send_email(conn, int(cid)),
                            "event_id": int(ev["id"]), "event": ev.get("item_name"),
                            "event_date": str(ev.get("event_date") or "")[:10]})
        return out
    finally:
        conn.close()


def plan(today: str | None = None, db_path=None, now: datetime | None = None) -> dict:
    """What the job would send now: first asks, reminders, and the lock-day
    reminder (an hour before the event's lock: 4:00 PM for a 5:00 PM lock)."""
    from email_parser import database as db
    from email_parser.timezone_utils import today_central_str
    today = today or today_central_str()
    state = load_state(db_path)
    asks, reminders, skipped, lock_reminders = [], [], [], []
    for c in candidates(today, db_path):
        rec = state.get(str(c["customer_id"])) or {}
        if rec.get("answer"):
            continue
        if not c["email"]:
            skipped.append({**c, "why": "no sendable email"})
            continue
        if not rec.get("sent_at"):
            asks.append(c)
            continue
        # THE LOCK-DAY REMINDER (Kerry 10/26, CoS #2307 item 5: "an automated
        # reminder at E-1 4:00 PM to anyone registered without a handicap";
        # #2341: "I approve today's handicap reminder email."). Same reminder
        # wording and signed link, once per person per event, in the hour
        # before that event's lock (database.event_lock_at).
        if now is not None:
            ev = _event_row(c["event_id"], db_path)
            lock = db.event_lock_at(ev, db_path) if ev else None
            key = f"lock_reminded_{c['event_id']}"
            if (lock is not None and not rec.get(key)
                    and lock - timedelta(minutes=LOCK_REMIND_MINUTES) <= now < lock):
                lock_reminders.append(c)
                continue
        days_out = (date.fromisoformat(c["event_date"]) - date.fromisoformat(today)).days
        sent_day = str(rec.get("sent_at"))[:10]
        if (not rec.get("reminded_at") and days_out <= REMIND_DAYS_BEFORE
                and sent_day < today):
            reminders.append(c)
    return {"today": today, "asks": asks, "reminders": reminders, "skipped": skipped,
            "lock_reminders": lock_reminders, **approval_state(db_path)}


# ---------------------------------------------------------------------------
# The email
# ---------------------------------------------------------------------------

def _day(event_date: str) -> str:
    try:
        return date.fromisoformat(str(event_date)[:10]).strftime("%A")
    except ValueError:
        return "your round"


def build_message(person: dict, ev: dict, kind: str = "ask", preview: bool = False,
                  db_path=None) -> dict:
    from email_parser.event_day_email import frame
    from email_parser.invitations import _display_name
    day = _day(ev.get("event_date"))
    first = person.get("first_name") or "there"
    link = ask_url(make_token(person["customer_id"], ev["id"], preview=preview))
    try:
        d = date.fromisoformat(str(ev.get("event_date"))[:10])
        when = f"{d.strftime('%A, %b')} {d.day}"
    except ValueError:
        when = ""
    course = ev.get("course") or ""
    subj_t, body_t = ((REMINDER_SUBJECT, REMINDER_BODY) if kind == "reminder"
                      else (SUBJECT, BODY))
    subject = subj_t.format(day=day, first_name=first)
    evbox = (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
             f'style="width:100%;margin:12px 0;"><tr><td style="background:#F8F8F8;'
             f'border:1px solid #E5E7EB;border-radius:10px;padding:10px 12px;font-size:15px;">'
             f'<b style="font-family:Georgia,serif;">{_e(ev.get("item_name"))}</b><br>'
             f'{_e(when)}{" &middot; " + _e(course) if course else ""}</td></tr></table>')
    button = (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
              f'style="margin:16px 0;"><tr><td><a href="{_e(link)}" style="display:inline-block;'
              f'background:#E87C3E;color:#ffffff;font:bold 16px Georgia,serif;text-decoration:none;'
              f'padding:12px 24px;border-radius:999px;">{_e(BUTTON)}</a></td></tr></table>')
    inner = (f"<p>{body_t.format(first_name=_e(first), day=_e(day))}</p>{evbox}"
             f"<p>{WHY}</p>{button}"
             f'<p style="color:#6B7280;font-size:14px;">{NO_HCP}</p><p>{SIGN}</p>')
    html_body = frame(inner, "THE GOLF FELLOWSHIP", f"{day} at {_display_name(ev)}")
    held = []
    if "{" in subject + html_body:
        held.append("leftover {tag}")
    return {"subject": subject, "html": html_body, "link": link, "held": held}


def _event_row(event_id: int, db_path=None) -> dict | None:
    from email_parser import database as db
    conn = db.get_connection(db_path)
    try:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _deliver(people: list[dict], kind: str, db_path=None, sender=None) -> dict:
    from email_parser import database as db
    if sender is None:
        from email_parser.event_day_email import _creds, _graph_send, asks_cc
        creds = _creds()
        if not creds:
            return {"error": "Email credentials not configured on server"}
        _cc = asks_cc(db_path)
        sender = lambda to, s, h: _graph_send(creds, to, s, h, cc=_cc)   # noqa: E731
    sent, failed, held = [], [], []
    for p in people:
        ev = _event_row(p["event_id"], db_path)
        if not ev:
            continue
        msg = build_message(p, ev, "reminder" if kind == "lock" else kind, db_path=db_path)
        if msg["held"]:
            held.append({"customer_id": p["customer_id"], "why": msg["held"]})
            continue
        good = False
        try:
            good = bool(sender(p["email"], msg["subject"], msg["html"]))
        except Exception:
            logger.exception("handicap ask send failed for cid %s", p["customer_id"])
        (sent if good else failed).append({"customer_id": p["customer_id"], "name": p["name"]})
        if good:
            state = load_state(db_path)
            rec = state.setdefault(str(p["customer_id"]), {})
            rec["event_id"] = p["event_id"]
            if kind == "lock":
                rec[f"lock_reminded_{p['event_id']}"] = _now_iso()
            else:
                rec["sent_at" if kind == "ask" else "reminded_at"] = _now_iso()
            _save_state(state, db_path)
        try:
            db.log_message({"event_name": p.get("event"), "channel": "email",
                            "recipient_name": p["name"], "recipient_address": p["email"],
                            "subject": msg["subject"], "body_preview": f"handicap ask ({kind})",
                            "status": "sent" if good else "failed",
                            "sent_by": f"handicap_ask_{kind}"}, db_path=db_path)
        except Exception:
            pass
    return {"sent": sent, "failed": failed, "held": held}


def auto_check(now: datetime | None = None, db_path=None, sender=None) -> dict:
    """Runs right after the inbox check saves new orders, and every 15
    minutes. Nothing unless the dial is on and the wording carries Kerry's
    stamp."""
    from email_parser.timezone_utils import now_central
    if (_setting(AUTO_DIAL, db_path) or "").strip().lower() != "on":
        return {"skipped": f"{AUTO_DIAL} is not on"}
    if not approval_state(db_path)["approved"]:
        return {"skipped": "wording not approved"}
    now = now or now_central()
    pl = plan(now.date().isoformat(), db_path, now=now)
    # The first ask goes the moment the registration lands, any hour (Kerry
    # 10/16: "as soon as we get a registration"); a reminder only by day.
    a = _deliver(pl["asks"], "ask", db_path, sender) if pl["asks"] else {}
    by_day = SEND_HOURS[0] <= now.hour < SEND_HOURS[1]
    r = (_deliver(pl["reminders"], "reminder", db_path, sender)
         if pl["reminders"] and by_day else {})
    lk = (_deliver(pl["lock_reminders"], "lock", db_path, sender)
          if pl["lock_reminders"] else {})
    return {"asks": a, "reminders": r, "lock_reminders": lk}


def resend(customer_id: int, kerry_ok_post, confirm: bool = False, db_path=None) -> dict:
    """The ask again to ONE player, on Kerry's word (Kerry 2026-10-20: "Have
    another email sent to Adam requesting his handicap & venmo. He said he
    didn't receive the one this morning."). Same message and link as the
    first ask, CC asks_cc; refused without a mailbox post carrying Kerry's
    word; dry run without confirm; never to someone who has answered."""
    from email_parser import database as db
    from email_parser.customer_query import _kerry_ok
    conn = db.get_connection(db_path)
    try:
        ok, why = _kerry_ok(conn, kerry_ok_post)
    finally:
        conn.close()
    if not ok:
        return {"refused": f"rule 3b: {why}"}
    if (load_state(db_path).get(str(int(customer_id))) or {}).get("answer"):
        return {"refused": "already answered"}
    person = next((c for c in candidates(db_path=db_path) if int(c["customer_id"]) == int(customer_id)), None)
    if not person:
        return {"refused": f"customer {customer_id} is not on an upcoming roster without a handicap"}
    if not person.get("email"):
        return {"refused": "no sendable email"}
    if confirm is not True:
        return {"dry_run": True, "authority": why, "to": person["email"], "event_id": person["event_id"]}
    return {"authority": why, **_deliver([person], "ask", db_path=db_path)}


def send_preview(event_id: int, to_address: str | None = None, kind: str = "ask",
                 db_path=None) -> dict:
    """ONE sample email to STAFF only, for Kerry's wording approval. Its link
    is a preview link: the page works and saves nothing."""
    from email_parser.event_day_email import _creds, _graph_send
    from email_parser.recap_mail import staff_only, _addrs
    to = _addrs(to_address) or [DEFAULT_PREVIEW_TO]
    bad = staff_only(to, lambda k: _setting(k, db_path))
    if bad:
        return {"error": f"a handicap-ask preview goes to TGF staff only; refused {bad}"}
    ev = _event_row(event_id, db_path)
    if not ev:
        return {"error": f"no event {event_id}"}
    sample = {"customer_id": 18, "first_name": "Kerry", "name": "Kerry Niester"}
    msg = build_message(sample, ev, kind, preview=True, db_path=db_path)
    pl = plan(db_path=db_path)
    head = (f"<p><strong>Handicap ask PREVIEW ({kind})</strong>. Nothing has been sent to any "
            f"player. The button opens the real page; a preview link saves nothing.</p>"
            f"<p>Would ask now: {len(pl['asks'])}; reminders now: {len(pl['reminders'])}. "
            f"Wording <code>{pl['template_hash']}</code>: "
            f"{'APPROVED' if pl['approved'] else 'NOT approved'}.</p><hr>")
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    subject = f"PREVIEW: {msg['subject']}"
    ok = _graph_send(creds, ",".join(to), subject, head + msg["html"])
    return {"status": "sent" if ok else "failed", "to": to, "subject": subject,
            "link": msg["link"], "approved": pl["approved"], "template_hash": pl["template_hash"]}


# ---------------------------------------------------------------------------
# Recording an answer
# ---------------------------------------------------------------------------

def describe(token: str, db_path=None) -> dict:
    from email_parser import database as db
    p = verify_token(token)
    if not p:
        return {"ok": False, "error": "This link isn't valid any more."}
    conn = db.get_connection(db_path)
    try:
        r = conn.execute("SELECT first_name, last_name, venmo_username, payment_handle "
                         "FROM customers WHERE customer_id = ?", (p["c"],)).fetchone()
    finally:
        conn.close()
    ev = _event_row(p["v"], db_path) or {}
    # A staff PREVIEW always shows the Venmo question (Kerry's own is on file).
    has_venmo = (not p.get("p")) and bool(r and ((r[2] or "").strip() or (r[3] or "").strip()))
    rec = load_state(db_path).get(str(p["c"])) or {}
    return {"ok": True, "customer_id": p["c"], "event_id": p["v"], "preview": bool(p.get("p")),
            "first_name": (r[0] if r else "") or "", "event": ev.get("item_name") or "",
            "event_date": str(ev.get("event_date") or "")[:10], "day": _day(ev.get("event_date")),
            "answer": rec.get("answer"), "status": rec.get("status"), "has_venmo": has_venmo}


def record(token: str, form: dict, db_path=None) -> dict:
    """The page's POST. Applies the answer (or, on a preview link, only
    reports what it would do)."""
    from email_parser import database as db
    info = describe(token, db_path)
    if not info.get("ok"):
        return info
    # LOCKED after the answer (Kerry 10/28, #2474-B: "Don't allow them to go
    # back to change it to avoid tampering."). Only a manager changes the
    # number (the roster HCP cell). A preview link never saves, so never locks.
    if info.get("answer") and not info.get("preview"):
        return {"ok": False, "locked": True,
                "error": "We already have your answer. " + DONE_LOCKED}
    ans = validate(form)
    if ans.get("error"):
        return {"ok": False, "error": ans["error"], "form_error": True}
    venmo, no_venmo = None, False
    if not info.get("has_venmo"):
        try:
            venmo = parse_venmo(form.get("venmo"))
        except ValueError as exc:
            return {"ok": False, "error": str(exc), "form_error": True}
        no_venmo = not venmo and str(form.get("no_venmo") or "") in ("1", "on", "true")
    ans["venmo"] = venmo
    ans["no_venmo"] = no_venmo
    cid = info["customer_id"]
    start = (starting_from_index(ans["index"]) if "index" in ans
             else starting_from_scores(ans) if ans["kind"] == "none" else None)
    status = {"ghin": "set", "other": "check", "none": "rule" if start is not None else "need"}[ans["kind"]]
    out = {"ok": True, "status": status, "starting": start, "answer": ans,
           "day": info["day"], "event_id": info["event_id"], "preview": info["preview"]}
    if info["preview"]:
        return out
    applied = False
    if start is not None:
        conn = db.get_connection(db_path)
        try:
            r = conn.execute("SELECT starting_handicap_18, starting_handicap_set_by FROM customers "
                             "WHERE customer_id = ?", (cid,)).fetchone()
        finally:
            conn.close()
        # A number a manager typed is never overwritten by the player's answer.
        by = (r[1] if r else "") or ""
        if r is None or r[0] is None or by.startswith("handicap_ask") or by.startswith(RULE_SET_BY):
            set_by = "handicap_ask (player)"
            if ans["kind"] == "ghin":
                note = f"Player: GHIN {ans['ghin']}, index {ans['index']}, 75%"
            elif ans["kind"] == "none":
                set_by = RULE_SET_BY
                note = f'Player: "{answer_words(ans)}"; low score minus 72 (Kerry 10/27)'
            else:
                svc = ans["service"] + (f" ({ans['service_name']})" if ans.get("service_name") else "")
                note = f"Player: {svc}, index {ans['index']}, 75%, manager to check"
            res = db.set_starting_handicap(cid, start, set_by=set_by, note=note, db_path=db_path)
            applied = not res.get("error")
        else:
            out["kept_manager_value"] = r[0]
    if ans["kind"] == "ghin" or venmo:
        conn = db.get_connection(db_path)
        try:
            if ans["kind"] == "ghin":
                conn.execute("UPDATE customers SET ghin_number = ? WHERE customer_id = ?",
                             (ans["ghin"], cid))
            if venmo:
                # Payouts read customers.venmo_username (bare, no @). Never
                # replaces a handle already on file.
                conn.execute("UPDATE customers SET venmo_username = ? WHERE customer_id = ? "
                             "AND (venmo_username IS NULL OR trim(venmo_username) = '')",
                             (venmo, cid))
            conn.commit()
        finally:
            conn.close()
    state = load_state(db_path)
    rec = state.setdefault(str(cid), {})
    rec.update({"answer": ans, "answered_at": _now_iso(), "status": status,
                "event_id": rec.get("event_id") or info["event_id"], "applied": applied})
    _save_state(state, db_path)
    try:
        db.log_agent_action("handicap-ask", "handicap_ask_answer",
                            f"customer {cid}: {ans['kind']}"
                            + f", {answer_words(ans)}"
                            + (f" -> starting {start}" if start is not None else ", nothing set")
                            + (f", venmo @{venmo}" if venmo else (", no Venmo yet" if no_venmo else "")),
                            db_path=db_path)
    except Exception:
        pass
    try:
        out["manager_email"] = notify_manager(cid, info["event_id"], ans, start,
                                              applied=applied, kept=out.get("kept_manager_value"),
                                              db_path=db_path)
    except Exception:
        logger.exception("handicap ask: manager email failed for cid %s", cid)
    return out


ADMIN_CC = "kerry@thegolffellowship.com"


def manager_message(name: str, ev: dict, ans: dict, start, applied: bool, kept=None,
                    base_url: str = "") -> dict:
    """The manager's email for one answer (Kerry 10/27, CoS #2425/#2426):
    what the player said in their own words, what was set, and a one-tap
    link to change it on the roster. No number: says nothing was set."""
    words = answer_words(ans)
    link = f"{base_url}/events?event={int(ev['id'])}"
    if kept is not None:
        head = f"{name}: kept the starting handicap you set ({kept})"
        line = f'They answered "{words}". Your number stays.'
    elif start is None:
        head = f"{name}: no handicap, NOTHING SET"
        line = (f'They answered "{words}". No starting handicap was set. '
                "Set one before the lock, or they play as a blind for their team.")
    elif ans.get("kind") == "none":
        head = f"{name}: starting handicap {start} from \"{words}\""
        line = (f"Low score minus 72{' (9-hole score doubled)' if ans.get('nine') else ''} "
                f"= {start}{'' if applied else ' (not applied)'}.")
    elif ans.get("kind") == "other":
        head = f"{name}: starting handicap {start}, please check it"
        line = f'They answered "{words}". 75% of that index = {start}.'
    else:
        head = f"{name}: starting handicap {start} from GHIN"
        line = f'They answered "{words}". 75% of that index = {start}.'
    subject = f"Handicap answer for {ev.get('item_name') or 'your event'}: {head}"
    html = (f'<div style="font-family:Helvetica,Arial,sans-serif;color:#1B1B1B;max-width:560px;">'
            f'<p style="margin:0 0 1em;font:bold 18px Georgia,serif;">{_e(head)}</p>'
            f'<p style="margin:0 0 1em;">{_e(line)}</p>'
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td bgcolor="#E87C3E" style="border-radius:999px;">'
            f'<a href="{_e(link)}" style="display:inline-block;padding:12px 22px;color:#ffffff;'
            f'font:bold 16px Georgia,serif;text-decoration:none;">Change it on the roster</a></td></tr></table>'
            f'<p style="font-size:12px;color:#6B7280;margin-top:1.5em;">{_e(ev.get("item_name") or "")} · '
            f'set it from the HCP cell on ROSTER.</p></div>')
    return {"subject": subject, "html": html, "head": head, "link": link}


def notify_manager(customer_id: int, event_id: int, ans: dict, start, applied: bool = False,
                   kept=None, db_path=None, sender=None) -> dict:
    """Email the event's chapter manager, Kerry CC'd, for EVERY answer
    (Alex Porter answered Monday 5:30 PM and nobody saw it, #2425)."""
    from email_parser import database as db
    from email_parser.pairings_approval import manager_for
    ev = _event_row(event_id, db_path)
    if not ev:
        return {"skipped": "no event"}
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                         (int(customer_id),)).fetchone()
    name = (" ".join(x for x in ((r[0] if r else ""), (r[1] if r else "")) if x)).strip() or f"Player {customer_id}"
    mgr = manager_for(ev.get("chapter"), db_path)
    to = (mgr.get("email") or ADMIN_CC).strip()
    cc = None if to.lower() == ADMIN_CC else ADMIN_CC
    try:
        from email_parser.invitations import _base_url
        base = _base_url()
    except Exception:
        base = ""
    msg = manager_message(name, ev, ans, start, applied, kept, base)
    if sender is None:
        from email_parser.event_day_email import _creds, _graph_send
        creds = _creds()
        if not creds:
            return {"error": "Email credentials not configured on server"}
        sender = lambda t, s, h, c: _graph_send(creds, t, s, h, cc=c)   # noqa: E731
    ok = bool(sender(to, msg["subject"], msg["html"], cc))
    try:
        db.log_message({"event_name": ev.get("item_name"), "channel": "email",
                        "recipient_name": mgr.get("name") or "manager", "recipient_address": to,
                        "subject": msg["subject"], "body_preview": "handicap answer (manager)",
                        "status": "sent" if ok else "failed", "sent_by": "handicap_ask_manager",
                        "event_id": int(event_id), "customer_id": int(customer_id)}, db_path=db_path)
    except Exception:
        pass
    return {"to": to, "cc": cc, "sent": ok, "subject": msg["subject"]}


def record_venmo(token: str, form: dict, db_path=None) -> dict:
    """Coming back to the same link later (Kerry 10/16) to add Venmo only:
    the handicap answer stands; the username goes straight onto the profile
    where payouts read it (never replacing one on file)."""
    from email_parser import database as db
    info = describe(token, db_path)
    if not info.get("ok"):
        return info
    try:
        venmo = parse_venmo(form.get("venmo"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "form_error": True}
    if not venmo:
        return {"ok": False, "error": "Please enter your Venmo username.", "form_error": True}
    out = {"ok": True, "venmo_only": True, "venmo": venmo, "preview": info["preview"]}
    if info["preview"]:
        return out
    cid = info["customer_id"]
    conn = db.get_connection(db_path)
    try:
        conn.execute("UPDATE customers SET venmo_username = ? WHERE customer_id = ? "
                     "AND (venmo_username IS NULL OR trim(venmo_username) = '')", (venmo, cid))
        conn.commit()
    finally:
        conn.close()
    state = load_state(db_path)
    rec = state.setdefault(str(cid), {})
    ans = rec.setdefault("answer", {})
    ans["venmo"], ans["no_venmo"] = venmo, False
    _save_state(state, db_path)
    try:
        db.log_agent_action("handicap-ask", "handicap_ask_venmo", f"customer {cid}: venmo @{venmo}",
                            db_path=db_path)
    except Exception:
        pass
    return out


def confirm(customer_id: int, by: str = "", db_path=None) -> dict:
    """A manager's Looks right on a `check` answer."""
    state = load_state(db_path)
    rec = state.get(str(int(customer_id)))
    if not rec or rec.get("status") != "check":
        return {"error": "nothing to confirm for this player"}
    rec.update({"status": "confirmed", "confirmed_by": by or "manager", "confirmed_at": _now_iso()})
    _save_state(state, db_path)
    return {"customer_id": int(customer_id), "status": "confirmed"}


# ---------------------------------------------------------------------------
# For the manager's banner
# ---------------------------------------------------------------------------

def _when(iso) -> str:
    try:
        from email_parser.timezone_utils import now_central  # noqa: F401
        import pytz
        d = datetime.fromisoformat(str(iso).rstrip("Z")).replace(tzinfo=pytz.utc)
        d = d.astimezone(pytz.timezone("America/Chicago"))
        return d.strftime("%a %-I:%M %p")
    except Exception:
        return str(iso or "")[:16]


def status_rows(customer_ids, missing_ids=(), db_path=None) -> list[dict]:
    """One row per roster player the ask has touched, for the banner.
    `missing_ids` are the players still without a handicap."""
    state = load_state(db_path)
    missing = {int(c) for c in missing_ids if c}
    rows = []
    for cid in customer_ids:
        if not cid:
            continue
        rec = state.get(str(int(cid)))
        if not rec:
            continue
        a = rec.get("answer") or {}
        st = rec.get("status") or ("asked" if rec.get("sent_at") else "")
        if not st:
            continue
        if st == "asked":
            if int(cid) not in missing:
                continue          # a manager set it meanwhile
            line = (f"Emailed {_when(rec.get('sent_at'))}"
                    + (f"; reminded {_when(rec.get('reminded_at'))}" if rec.get("reminded_at")
                       else f"; reminder {REMIND_DAYS_BEFORE} days before the event"))
            try:  # THE CLICK LOG (Kerry 10/29): did they open it?
                from email_parser.link_clicks import opened_line
                line += f"; {opened_line('handicap', int(cid), db_path=db_path)}"
            except Exception:
                pass
        elif a.get("kind") == "ghin":
            line = (f"GHIN {a.get('ghin')} · index {a.get('index')} → starting "
                    f"{starting_from_index(a['index'])} · answered {_when(rec.get('answered_at'))}")
        elif a.get("kind") == "other":
            svc = a.get("service") + (f" ({a['service_name']})" if a.get("service_name") else "")
            line = (f"{svc} · index {a.get('index')} → starting "
                    f"{starting_from_index(a['index'])} (applied)")
        elif a.get("kind") == "none":
            line = (f"No handicap · {answer_words(a)}"
                    + (f" · plays {a['rounds_year']} rounds a year" if a.get("rounds_year") else ""))
            if st == "rule" and a.get("score_low") is not None:
                line += f" → starting {starting_from_scores(a)} (low score minus 72)"
        else:
            line = ""
        # A number the manager typed since the answer settles it (Alex Porter
        # read "Needs a number" after Kerry set 18.0 by hand, 10/27).
        if st in ("need", "check", "rule") and int(cid) not in missing:
            mv = _manager_value(int(cid), db_path)
            if mv is not None:
                st = "manager_set"
                line += f" · set by manager: {mv}"
        if a.get("venmo"):
            line += f" · Venmo @{a['venmo']}"
        elif a.get("no_venmo"):
            line += " · no Venmo yet"
        rows.append({"customer_id": int(cid), "status": st, "line": line})
    return rows


def _manager_value(customer_id: int, db_path=None):
    """The starting handicap when a person (not the ask, not the rule) set it."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT starting_handicap_18, starting_handicap_set_by FROM customers "
                         "WHERE customer_id = ?", (int(customer_id),)).fetchone()
    if not r or r[0] is None:
        return None
    by = r[1] or ""
    return None if by.startswith("handicap_ask") or by.startswith(RULE_SET_BY) else r[0]
