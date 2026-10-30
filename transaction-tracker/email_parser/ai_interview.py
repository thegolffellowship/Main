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

The page asks three questions one at a time (QUESTIONS). When
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

QUESTIONS = ("What was the shot of the night?",
             "What was working for you out there?",
             "Anything you want to say to the field?")

# The words. Changing any of them changes the hash and locks the send until
# Kerry stamps the new hash.
SUBJECT = "{first_name}, a quick word for the recap?"
BODY = "Hi {first_name},<br><br>Great {day} at {course}. {why}"
ASK = ("We'd love a quote or two for the recap. Three quick questions, about two "
       "minutes, right on your phone.")
CONSENT_NOTE = ("At the end we'll ask whether we have your permission to use your "
                "quotes in the event recap. Nothing is used unless you say yes.")
BUTTON = "Answer 3 quick questions"
SIGN = "See you on the course,<br>The Golf Fellowship"
# Kerry 10/30: a Yes / No permission question, not a tick box
CONSENT_LABEL = "Do you give us permission to use your quotes in the event recap?"
CONSENT_YES = "Yes"
CONSENT_NO = "No"
THANKS = "Thanks! That's everything."
REASON_WORDS = {"mvp": "You were the City MVP.", "tgf_mvp": "You were the TGF MVP.",
                "ace": "A hole-in-one on hole {holes}!",
                "eagle": "Eagle on hole {holes}!", "birdies": "{n} birdies!"}
FOLLOWUP_SYSTEM = (
    "You are a friendly golf reporter for The Golf Fellowship, a golf community in Texas, "
    "doing a two-minute post-round interview by text. Read the player's answer and ask ONE "
    "short, warm follow-up question (at most 20 words) that draws out a specific, quotable "
    "detail: a club, a distance, a moment, a feeling. Plain words, no preamble, no quotes "
    "around it, just the question. If the answer gives nothing to follow up, reply NONE.")


def template_hash() -> str:
    raw = "\x1f".join((SUBJECT, BODY, ASK, CONSENT_NOTE, BUTTON, SIGN, CONSENT_LABEL, CONSENT_YES, CONSENT_NO, THANKS,
                       *QUESTIONS, *[REASON_WORDS[k] for k in sorted(REASON_WORDS)]))
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
                                                   "holes": birdies})
    out = []
    with db._connect(db_path) as conn:
        for cid, reasons in sorted(found.items()):
            r = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                             (cid,)).fetchone()
            first = ((r["first_name"] if r else "") or "").strip()
            name = " ".join(x for x in (first, ((r["last_name"] if r else "") or "").strip()) if x)
            out.append({"customer_id": cid, "name": name or f"#{cid}", "first_name": first or "there",
                        "email": _send_email(conn, cid), "reasons": reasons,
                        "why": reason_text(reasons)})
    return out


def reason_text(reasons: list) -> str:
    parts = []
    for r in reasons:
        w = REASON_WORDS.get(r.get("kind"))
        if not w:
            continue
        holes = ", ".join(str(h) for h in r.get("holes") or [])
        parts.append(w.format(holes=holes, n=r.get("n")))
    return " ".join(parts)


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
    from email_parser import closeout_chain as cc
    return bool((cc.state(event_id, db_path).get("steps") or {}).get("payouts", {}).get("ok"))


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
        people[k] = {"why": p["why"], "sent_at": now.strftime("%Y-%m-%d %H:%M") if ok else None,
                     "failed": not ok}
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
                return (f"waiting up to {int(left) + 1} more minute(s) for the MVP interview "
                        f"invitations (event {eid}: payouts not recorded yet)")
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
    return {"ok": True, "customer_id": p["c"], "event_id": p["v"], "preview": bool(p.get("p")),
            "first_name": ((r[0] if r else "") or "").strip(), "event": ev.get("item_name") or "",
            "day": _day(ev) if ev else "", "why": (st.get("people") or {}).get(str(p["c"]), {}).get("why") or "",
            "questions": list(QUESTIONS), "consent_label": CONSENT_LABEL, "consent_yes": CONSENT_YES, "consent_no": CONSENT_NO, "thanks": THANKS,
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
    if not 0 <= q < len(QUESTIONS):
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
        rec["answers"].append({"q": q, "question": _clean(followup_q) if is_followup else QUESTIONS[q],
                               "answer": text, "followup": is_followup,
                               "at": datetime.utcnow().strftime("%Y-%m-%d %H:%M")})
        _save(key, allans, db_path)
    nxt = None
    if not is_followup and text:
        nxt = followup(QUESTIONS[q], text, ask=ask, db_path=db_path)
    return {"ok": True, "followup": nxt}


def followup(question: str, answer: str, ask=None, db_path=None) -> str | None:
    """One short follow-up question from the recap writer's model, or None."""
    if ask is None:
        if not ai_available():
            return None
        ask = _ask_claude
    try:
        from email_parser.recap_writer import model
        out = (ask(FOLLOWUP_SYSTEM, f"Question: {question}\nPlayer's answer: {answer}",
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
    """The last tap: Yes / No to the permission question (and, from the no-JS form, the three
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
        for i in range(len(QUESTIONS)):
            t = _clean(answers.get(i) or answers.get(str(i)))
            if t:
                rec["answers"] = [a for a in rec.get("answers") or []
                                  if not (a.get("q") == i and not a.get("followup"))]
                rec["answers"].append({"q": i, "question": QUESTIONS[i], "answer": t,
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
