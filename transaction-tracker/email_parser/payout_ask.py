"""THE PAYOUT HANDLE ASK (Kerry 2026-10-17, CoS #1977: "Have TGF Tracker
Build build something similar to what it did yesterday for handicap email
requests"; mockups artifact MM2hscPx8cHQ56NCaxVjkp; Kerry: "I can pay all of
them. Make the DB change. Deploy it all when done. Send to Mark and Michele.").

WHO: a person with an UNPAID prize payout (tgf_payouts linked to a pending
ledger row) and no way to pay them on file: no customers.venmo_username and
no customers.payment_method. Everyone gets the link, member or not: we owe
them money (CoS #1977-3).

THE PAGE (`/payout/<token>`, signed, no login; only a form POST saves):
  1. Venmo first. The username is shown back large before it is saved
     (Kerry: Venmo "absolutely preferred").
  2. "Don't have Venmo?" sells Venmo (app-store buttons), nothing else.
  3. Only after "I can't use Venmo": TGF credit first, then Zelle, PayPal,
     Cash App, Apple Cash, with the handle each needs. An optional reason;
     "blocked or closed" means we never nudge them about Venmo again
     (Kerry: "some of our members have had their Venmo blocked").
Venmo writes customers.venmo_username; the others write
customers.payment_method + payment_handle (the v2.38.0 columns the Payouts
tab already pays from; Apple Cash is the existing value 'applepay'). An
existing value is never replaced. TGF credit writes NO money: it records the
request and raises one COO action item for the manager / CFO to convert the
payout. The Tracker never pays anyone.

STATE: app setting `payout_ask` (JSON by customer_id), no new table.

SENDS: the job sends only when dial `payout_ask_auto` = on AND the wording
carries Kerry's stamp (`payout_ask_approved` = `template_hash()`).
`send_now(ids)` is the explicit send to people Kerry names; it needs the
stamp too. Previews go to staff only. One ask per person per open balance,
one reminder 2 days later by day.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

STATE_KEY = "payout_ask"
AUTO_DIAL = "payout_ask_auto"
APPROVAL_KEY = "payout_ask_approved"
DEFAULT_PREVIEW_TO = "kerry@thegolffellowship.com"
REMIND_AFTER_DAYS = 2
TOKEN_DAYS = 90
LOOKBACK_DAYS = 120           # payouts older than this are left to the manager
SEND_HOURS = (7, 21)          # Central; asks 7 AM-9 PM
REMIND_HOURS = (7, 20)        # reminders 7 AM-8 PM

METHODS = (  # value stored in customers.payment_method, label, handle hint
    ("zelle", "Zelle", "The phone number or email your bank uses for Zelle"),
    ("paypal", "PayPal", "The email or PayPal.Me name on your PayPal account"),
    ("cashapp", "Cash App", "Your $cashtag"),
    ("applepay", "Apple Cash", "Your iPhone number (iPhone to iPhone only)"),
)
REASONS = (("", "Choose one (optional)"),
           ("blocked", "My Venmo account is blocked or closed"),
           ("dont_want", "I'd rather not use Venmo"),
           ("other", "Another reason"))

# The words (mockup v4, Kerry 10/17). Changing any of these changes the hash
# and locks the send until Kerry stamps the new hash.
SUBJECT = "You won {amount} at {event}: where should we send it?"
SUBJECT_MULTI = "You have {amount} in TGF winnings: where should we send it?"
REMINDER_SUBJECT = "Reminder: your {amount} from {event}"
REMINDER_SUBJECT_MULTI = "Reminder: your {amount} in TGF winnings"
GREETING = "Nice playing, {first_name}."
BODY = "We pay winnings by Venmo, and we don't have yours yet. It takes ten seconds:"
REMINDER_GREETING = "Still holding your winnings, {first_name}."
REMINDER_BODY = "We can't send your {amount} until we know where to send it."
BUTTON = "Tell us your Venmo"
FOOT = "This link is just for you. Questions? Reply to this email."
SIGN = "See you on the course,<br>The Golf Fellowship"
PAGE_HEAD = "Where should we send your {amount}?"
VENMO_LABEL = "Your Venmo username"
VENMO_HINT = "It's the @name in your Venmo app, under your photo."
CONFIRM_HEAD = "Is this right?"
CONFIRM_NOTE = ("Open Venmo and search this name if you're not sure. A wrong username sends "
                "your money to someone else.")
GET_HEAD = "Venmo is the fastest way to get paid."
GET_BODY = ("It's free and takes about two minutes. Winnings sent to Venmo go out within "
            "24 hours, and almost every TGF player uses it.")
GET_AFTER = "Then tap your email link again and add your @name."
OTHER_HEAD = "Other ways to get your {amount}"
CREDIT_LABEL = "Keep it as TGF credit"
CREDIT_NOTE = "On your account, toward your next event"
OTHER_NOTE = "You can switch to Venmo any time from this same link."
DONE_HEAD = "Got it. Thanks, {first_name}."
DONE_VENMO = "Your {amount} goes to @{handle}."
DONE_OTHER = "Your {amount} goes to your {method}: {handle}."
DONE_CREDIT = "Your {amount} will be added to your TGF account as credit."
DONE_NOTE = ("We'll use this for future winnings too. You can change it any time by replying "
             "to one of our emails.")
VENMO_IOS = "https://apps.apple.com/us/app/venmo/id351727428"
VENMO_ANDROID = "https://play.google.com/store/apps/details?id=com.venmo"


def template_hash() -> str:
    raw = "\x1f".join((SUBJECT, SUBJECT_MULTI, REMINDER_SUBJECT, REMINDER_SUBJECT_MULTI,
                       GREETING, BODY, REMINDER_GREETING, REMINDER_BODY, BUTTON, FOOT, SIGN,
                       PAGE_HEAD, VENMO_LABEL, VENMO_HINT, CONFIRM_HEAD, CONFIRM_NOTE, GET_HEAD,
                       GET_BODY, GET_AFTER, OTHER_HEAD, CREDIT_LABEL, CREDIT_NOTE, OTHER_NOTE,
                       DONE_HEAD, DONE_VENMO, DONE_OTHER, DONE_CREDIT, DONE_NOTE,
                       json.dumps(METHODS), json.dumps(REASONS)))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def money(v) -> str:
    return f"${float(v or 0):,.2f}"


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


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.utcnow()).replace(microsecond=0).isoformat() + "Z"


def _parse_iso(s) -> datetime | None:
    try:
        return datetime.fromisoformat(str(s).rstrip("Z"))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Signed links ("pay." prefix: a handicap link can never open this page)
# ---------------------------------------------------------------------------

def _secret() -> bytes:
    from email_parser.memberships import _secret as s
    return s()


def make_token(customer_id: int, preview: bool = False, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    p = {"c": int(customer_id), "x": int((now + timedelta(days=TOKEN_DAYS)).timestamp())}
    if preview:
        p["p"] = 1
    body = base64.urlsafe_b64encode(json.dumps(p, separators=(",", ":")).encode()
                                    ).rstrip(b"=").decode()
    sig = hmac.new(_secret(), b"pay." + body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def verify_token(token: str) -> dict | None:
    token = (token or "").strip()
    if "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    want = hmac.new(_secret(), b"pay." + body.encode(), hashlib.sha256).hexdigest()[:32]
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
    return f"{_base_url()}/payout/{token}"


# ---------------------------------------------------------------------------
# Parsing an answer (pure)
# ---------------------------------------------------------------------------

def parse_venmo(text) -> str | None:
    from email_parser.handicap_ask import parse_venmo as pv
    return pv(text)


def _phone(t: str) -> str | None:
    d = re.sub(r"\D", "", t)
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else None


def _email(t: str) -> str | None:
    t = t.strip().lower()
    return t if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", t) else None


def parse_handle(method: str, text) -> str:
    """A cleaned handle for `method`, or ValueError with a plain message."""
    t = str(text or "").strip()
    if not t:
        raise ValueError("Please enter where to send it.")
    if method == "zelle":
        v = _email(t) or _phone(t)
        if not v:
            raise ValueError("For Zelle, enter the phone number or email your bank uses.")
        return v
    if method == "paypal":
        if "@" in t:
            v = _email(t)
            if not v:
                raise ValueError("That doesn't look like an email address.")
            return v
        u = re.sub(r"^https?://(www\.)?paypal\.me/", "", t, flags=re.I).lstrip("@").strip("/ ")
        if not re.fullmatch(r"[A-Za-z0-9]{1,20}", u):
            raise ValueError("Enter the email on your PayPal account, or your PayPal.Me name.")
        return u
    if method == "cashapp":
        u = re.sub(r"^https?://cash\.app/", "", t, flags=re.I).strip("/ ").lstrip("$").strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,19}", u):
            raise ValueError("That doesn't look like a $cashtag. It's the $name in your Cash App.")
        return "$" + u
    if method == "applepay":
        v = _phone(t)
        if not v:
            raise ValueError("For Apple Cash, enter your iPhone's phone number.")
        return v
    raise ValueError("Please choose how you'd like to be paid.")


# ---------------------------------------------------------------------------
# Who to ask
# ---------------------------------------------------------------------------

def open_payouts(today: datetime | None = None, db_path=None) -> dict:
    """{customer_id: {name, first_name, email, amount, lines:[...], venmo, method}}
    for every UNPAID payout (ledger row still 'pending') in the last
    LOOKBACK_DAYS. Includes people who already have a handle; candidates()
    filters them."""
    from email_parser import database as db
    today = today or datetime.utcnow()
    since = (today - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    conn = db.get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT p.customer_id, p.amount, p.category, p.description,
                      e.name AS event_name, e.code AS event_code, e.event_date,
                      c.first_name, c.last_name, c.venmo_username, c.payment_method,
                      c.payment_handle
               FROM tgf_payouts p
               JOIN tgf_events e ON e.id = p.event_id
               JOIN customers c ON c.customer_id = p.customer_id
               JOIN acct_transactions t ON t.id = p.acct_transaction_id
               WHERE t.source = 'pending' AND COALESCE(t.status, 'active') = 'active'
                 AND e.event_date >= ?
               ORDER BY e.event_date, p.id""", (since,)).fetchall()
    finally:
        conn.close()
    out: dict[int, dict] = {}
    for r in rows:
        cid = int(r["customer_id"])
        o = out.setdefault(cid, {
            "customer_id": cid, "first_name": (r["first_name"] or "").strip(),
            "name": f"{(r['first_name'] or '').strip()} {(r['last_name'] or '').strip()}".strip(),
            "venmo": (r["venmo_username"] or "").strip(),
            "method": (r["payment_method"] or "").strip().lower(),
            "handle": (r["payment_handle"] or "").strip(),
            "amount": 0.0, "lines": [], "events": []})
        amt = round(float(r["amount"] or 0), 2)
        o["amount"] = round(o["amount"] + amt, 2)
        label = (r["description"] or r["category"] or "Winnings").strip()
        o["lines"].append({"event": r["event_name"], "what": label, "amount": amt})
        if r["event_name"] not in o["events"]:
            o["events"].append(r["event_name"])
    for cid, o in out.items():
        try:
            o["email"] = db.resolve_player_email({"customer_id": cid}, db_path=db_path) or ""
        except Exception:
            o["email"] = ""
    return out


def _has_handle(o: dict) -> bool:
    return bool(o.get("venmo") or o.get("method"))


def candidates(today: datetime | None = None, db_path=None) -> list[dict]:
    return [o for o in open_payouts(today, db_path).values()
            if not _has_handle(o) and o["amount"] > 0.004]


def plan(now: datetime | None = None, db_path=None) -> dict:
    now = now or datetime.utcnow()
    state = load_state(db_path)
    asks, reminders, waiting, no_email = [], [], [], []
    for o in candidates(now, db_path):
        rec = state.get(str(o["customer_id"])) or {}
        if rec.get("answered_at"):
            continue
        if not o["email"]:
            no_email.append(o)
            continue
        if not rec.get("sent_at"):
            asks.append(o)
            continue
        sent = _parse_iso(rec["sent_at"])
        if (not rec.get("reminded_at") and sent
                and now - sent >= timedelta(days=REMIND_AFTER_DAYS)):
            reminders.append(o)
        else:
            waiting.append(o)
    ap = approval_state(db_path)
    return {"asks": asks, "reminders": reminders, "waiting": waiting, "no_email": no_email,
            "approved": ap["approved"], "template_hash": ap["template_hash"],
            "auto": (_setting(AUTO_DIAL, db_path) or "").strip().lower() == "on"}


# ---------------------------------------------------------------------------
# The email
# ---------------------------------------------------------------------------

def build_message(person: dict, kind: str = "ask", preview: bool = False) -> dict:
    from email_parser.event_day_email import frame
    first = person.get("first_name") or "there"
    amount = money(person.get("amount"))
    events = person.get("events") or []
    one = len(events) == 1
    if kind == "reminder":
        subject = (REMINDER_SUBJECT.format(amount=amount, event=events[0]) if one
                   else REMINDER_SUBJECT_MULTI.format(amount=amount))
    else:
        subject = (SUBJECT.format(amount=amount, event=events[0]) if one
                   else SUBJECT_MULTI.format(amount=amount))
    link = ask_url(make_token(person["customer_id"], preview=preview))
    def _row(l):
        sub = ("" if one else '<br><span style="color:#6B7280;font-size:13px;">'
               + _e(l["event"]) + "</span>")
        return (f'<tr><td style="padding:4px 0;">{_e(l["what"])}{sub}</td>'
                f'<td style="padding:4px 0;text-align:right;white-space:nowrap;">'
                f'{money(l["amount"])}</td></tr>')
    rows = "".join(_row(l) for l in person.get("lines") or [])
    box = (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
           f'style="width:100%;margin:12px 0;"><tr><td style="background:#F8F8F8;'
           f'border:1px solid #E5E7EB;border-radius:10px;padding:10px 12px;font-size:15px;">'
           f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}'
           f'<tr><td style="padding-top:6px;border-top:1px solid #E5E7EB;"><b>Total</b></td>'
           f'<td style="padding-top:6px;border-top:1px solid #E5E7EB;text-align:right;"><b>{amount}</b>'
           f'</td></tr></table></td></tr></table>')
    button = (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
              f'style="margin:16px 0;"><tr><td><a href="{_e(link)}" style="display:inline-block;'
              f'background:#E87C3E;color:#ffffff;font:bold 16px Georgia,serif;text-decoration:none;'
              f'padding:12px 24px;border-radius:999px;">{_e(BUTTON)}</a></td></tr></table>')
    if kind == "reminder":
        lead = (f"<p><b>{_e(REMINDER_GREETING.format(first_name=first))}</b></p>"
                f"<p>{_e(REMINDER_BODY.format(amount=amount))}</p>")
    else:
        lead = (f"<p><b>{_e(GREETING.format(first_name=first))}</b></p>"
                f"<p>You won <b>{amount}</b>{' at ' + _e(events[0]) if one else ''}.</p>")
    inner = (f"{lead}{box}" + ("" if kind == "reminder" else f"<p>{_e(BODY)}</p>")
             + f'{button}<p style="color:#6B7280;font-size:14px;">{_e(FOOT)}</p><p>{SIGN}</p>')
    html_body = frame(inner, "THE GOLF FELLOWSHIP", "Your winnings")
    held = ["leftover {tag}"] if "{" in subject + html_body else []
    if not person.get("lines"):
        held.append("no payout lines")
    return {"subject": subject, "html": html_body, "link": link, "held": held}


def _sender(sender):
    if sender is not None:
        return sender
    from email_parser.event_day_email import _creds, _graph_send, asks_cc
    creds = _creds()
    if not creds:
        return None
    _cc = asks_cc()
    return lambda to, s, h: _graph_send(creds, to, s, h, cc=_cc)   # noqa: E731


def _deliver(people: list[dict], kind: str, db_path=None, sender=None) -> dict:
    from email_parser import database as db
    sender = _sender(sender)
    if sender is None:
        return {"error": "Email credentials not configured on server"}
    sent, failed, held = [], [], []
    for p in people:
        msg = build_message(p, kind)
        if msg["held"]:
            held.append({"customer_id": p["customer_id"], "why": msg["held"]})
            continue
        good = False
        try:
            good = bool(sender(p["email"], msg["subject"], msg["html"]))
        except Exception:
            logger.exception("payout ask send failed for cid %s", p["customer_id"])
        (sent if good else failed).append({"customer_id": p["customer_id"], "name": p["name"],
                                           "amount": p["amount"]})
        if good:
            state = load_state(db_path)
            rec = state.setdefault(str(p["customer_id"]), {})
            rec["amount"] = p["amount"]
            rec["sent_at" if kind == "ask" else "reminded_at"] = _now_iso()
            _save_state(state, db_path)
        try:
            db.log_message({"event_name": ", ".join(p.get("events") or []), "channel": "email",
                            "recipient_name": p["name"], "recipient_address": p["email"],
                            "subject": msg["subject"], "body_preview": f"payout ask ({kind})",
                            "status": "sent" if good else "failed",
                            "sent_by": f"payout_ask_{kind}"}, db_path=db_path)
        except Exception:
            pass
    return {"sent": sent, "failed": failed, "held": held}


def auto_check(now: datetime | None = None, db_path=None, sender=None) -> dict:
    """Every 15 minutes. Nothing unless the dial is on and the wording
    carries Kerry's stamp."""
    from email_parser.timezone_utils import now_central
    if (_setting(AUTO_DIAL, db_path) or "").strip().lower() != "on":
        return {"skipped": f"{AUTO_DIAL} is not on"}
    if not approval_state(db_path)["approved"]:
        return {"skipped": "wording not approved"}
    local = now or now_central()
    pl = plan(db_path=db_path)
    a = (_deliver(pl["asks"], "ask", db_path, sender)
         if pl["asks"] and SEND_HOURS[0] <= local.hour < SEND_HOURS[1] else {})
    r = (_deliver(pl["reminders"], "reminder", db_path, sender)
         if pl["reminders"] and REMIND_HOURS[0] <= local.hour < REMIND_HOURS[1] else {})
    return {"asks": a, "reminders": r}


def send_now(customer_ids, db_path=None, sender=None) -> dict:
    """The explicit send to people Kerry names (10/17: "Send to Mark and
    Michele"). Needs the wording stamp; never re-asks someone already asked
    or answered, never asks someone with a handle or no open payout."""
    if not approval_state(db_path)["approved"]:
        return {"error": "wording not approved"}
    want = {int(c) for c in customer_ids}
    state = load_state(db_path)
    by = {o["customer_id"]: o for o in candidates(db_path=db_path)}
    go, refused = [], []
    for cid in sorted(want):
        o = by.get(cid)
        rec = state.get(str(cid)) or {}
        if not o:
            refused.append({"customer_id": cid, "why": "no open payout without a handle"})
        elif rec.get("sent_at") or rec.get("answered_at"):
            refused.append({"customer_id": cid, "why": "already asked or answered"})
        elif not o["email"]:
            refused.append({"customer_id": cid, "why": "no email on file"})
        else:
            go.append(o)
    res = _deliver(go, "ask", db_path, sender) if go else {"sent": [], "failed": [], "held": []}
    res["refused"] = refused
    return res


def send_preview(customer_id: int | None = None, to_address: str | None = None,
                 kind: str = "ask", db_path=None, sender=None) -> dict:
    """ONE sample email to STAFF only. Its link is a preview link: the page
    works and saves nothing."""
    from email_parser.recap_mail import staff_only, _addrs
    to = _addrs(to_address) or [DEFAULT_PREVIEW_TO]
    bad = staff_only(to, lambda k: _setting(k, db_path))
    if bad:
        return {"error": f"a payout-ask preview goes to TGF staff only; refused {bad}"}
    sample = None
    if customer_id:
        sample = open_payouts(db_path=db_path).get(int(customer_id))
    sample = sample or {"customer_id": 18, "first_name": "Kerry", "name": "Kerry Niester",
                        "amount": 16.25, "events": ["a9.26 Avery Ranch"],
                        "lines": [{"event": "a9.26 Avery Ranch", "what": "Team Net 2nd",
                                   "amount": 16.25}]}
    msg = build_message(sample, kind, preview=True)
    snd = _sender(sender)
    if snd is None:
        return {"error": "Email credentials not configured on server"}
    subject = f"PREVIEW: {msg['subject']}"
    ok = snd(",".join(to), subject, "<p><strong>Payout ask PREVIEW</strong>. Nothing sent to "
             "any player; the link saves nothing.</p><hr>" + msg["html"])
    return {"status": "sent" if ok else "failed", "to": to, "link": msg["link"]}


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

def describe(token: str, db_path=None) -> dict:
    p = verify_token(token)
    if not p:
        return {"ok": False, "error": "This link isn't valid any more. Reply to our email and "
                                      "we'll sort it out."}
    cid = int(p["c"])
    o = open_payouts(db_path=db_path).get(cid)
    from email_parser import database as db
    conn = db.get_connection(db_path)
    try:
        r = conn.execute("SELECT first_name, last_name, venmo_username, payment_method, payment_handle "
                         "FROM customers WHERE customer_id = ?", (cid,)).fetchone()
    finally:
        conn.close()
    if not r:
        return {"ok": False, "error": "This link isn't valid any more."}
    rec = load_state(db_path).get(str(cid)) or {}
    amount = o["amount"] if o else float(rec.get("amount") or 0)
    return {"ok": True, "customer_id": cid, "preview": bool(p.get("p")),
            "first_name": (r["first_name"] or "").strip() or "there",
            "name": f"{(r['first_name'] or '').strip()} {(r['last_name'] or '').strip()}".strip(),
            "amount": amount, "amount_text": money(amount) if amount else "winnings",
            "venmo": (r["venmo_username"] or "").strip(),
            "method": (r["payment_method"] or "").strip().lower(),
            "handle": (r["payment_handle"] or "").strip(),
            "answer": rec.get("answer")}


def _remember(cid: int, answer: dict, db_path=None) -> None:
    state = load_state(db_path)
    rec = state.setdefault(str(cid), {})
    rec["answer"] = answer
    rec["answered_at"] = _now_iso()
    _save_state(state, db_path)


def record_venmo(token: str, venmo_text, db_path=None) -> dict:
    from email_parser import database as db
    info = describe(token, db_path)
    if not info.get("ok"):
        return info
    try:
        venmo = parse_venmo(venmo_text)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if not venmo:
        return {"ok": False, "error": "Please enter your Venmo username."}
    out = {"ok": True, "kind": "venmo", "handle": venmo, "preview": info["preview"]}
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
    _remember(cid, {"kind": "venmo", "handle": venmo}, db_path)
    try:
        db.log_agent_action("payout-ask", "payout_ask_venmo", f"customer {cid}: venmo @{venmo}",
                            db_path=db_path)
    except Exception:
        pass
    return out


def record_other(token: str, form: dict, db_path=None) -> dict:
    from email_parser import database as db
    info = describe(token, db_path)
    if not info.get("ok"):
        return info
    method = (form.get("method") or "").strip().lower()
    reason = (form.get("reason") or "").strip()
    if reason not in dict(REASONS):
        reason = ""
    if method == "credit":
        out = {"ok": True, "kind": "credit", "preview": info["preview"]}
        if info["preview"]:
            return out
        cid = info["customer_id"]
        _remember(cid, {"kind": "credit", "reason": reason}, db_path)
        try:
            db.save_action_item({
                "subject": f"PAYOUT AS CREDIT: {info['name']} ({info['amount_text']})",
                "from_name": "Payout ask",
                "summary": (f"{info['name']} (customer {cid}) chose to keep {info['amount_text']} "
                            "as TGF credit on the payout ask page. Convert the open payout to "
                            "account credit. Nothing has been paid or credited by the Tracker."),
                "urgency": "medium", "category": "payouts"}, db_path=db_path)
        except Exception:
            logger.exception("payout ask: action item failed for cid %s", cid)
        try:
            db.log_agent_action("payout-ask", "payout_ask_credit", f"customer {cid}: credit",
                                db_path=db_path)
        except Exception:
            pass
        return out
    if method not in dict((m, l) for m, l, _ in METHODS):
        return {"ok": False, "error": "Please choose how you'd like to be paid."}
    try:
        handle = parse_handle(method, form.get(f"handle_{method}") or form.get("handle"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    out = {"ok": True, "kind": method, "handle": handle, "preview": info["preview"],
           "label": dict((m, l) for m, l, _ in METHODS)[method]}
    if info["preview"]:
        return out
    cid = info["customer_id"]
    conn = db.get_connection(db_path)
    try:
        conn.execute("UPDATE customers SET payment_method = ?, payment_handle = ? "
                     "WHERE customer_id = ? AND (payment_method IS NULL OR trim(payment_method) = '')",
                     (method, handle, cid))
        conn.commit()
    finally:
        conn.close()
    _remember(cid, {"kind": method, "handle": handle, "reason": reason}, db_path)
    try:
        db.log_agent_action("payout-ask", "payout_ask_other",
                            f"customer {cid}: {method} {handle} (reason {reason or '-'})",
                            db_path=db_path)
    except Exception:
        pass
    return out


def status_rows(db_path=None) -> dict:
    """{customer_id: chip} for the Payouts → Unpaid rows."""
    out = {}
    for cid, rec in load_state(db_path).items():
        a = rec.get("answer") or {}
        if rec.get("answered_at"):
            chip = {"state": "in", "kind": a.get("kind"), "handle": a.get("handle"),
                    "at": rec["answered_at"]}
        elif rec.get("reminded_at"):
            chip = {"state": "reminded", "at": rec["reminded_at"], "asked": rec.get("sent_at")}
        elif rec.get("sent_at"):
            chip = {"state": "asked", "at": rec["sent_at"]}
        else:
            continue
        if chip["state"] != "in":
            try:  # THE CLICK LOG (Kerry 10/29): did they open it?
                from email_parser.link_clicks import opened
                o = opened("payout", int(cid), db_path=db_path)
                chip["opened"] = (o or {}).get("last")
                chip["scanner_only"] = bool(o and o.get("scanner_only"))
            except Exception:
                pass
        out[cid] = chip
    return out
