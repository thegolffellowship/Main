"""THE COURSE SHORTFALL EMAIL (Kerry 2026-10-28, Event Ops #2474-A,
#2475-3, #2476-1).

Kerry: "I just asked Teravista to credit. We'll need to have an automated
email triggered if this happens in future." / "when we're over calculated
price by a whole player (not by less than say 1/2 of a full player course
rate)" / "Approved".

TRIGGER: a course charge booked against an event (an `expense_transactions`
row whose category is a course-fee category, linked by `event_id`, or by the
event's name when the id is blank; ignored rows never count; a later course
credit on the same event counts against it). Then

    overcharge = charged - expected
    expected   = sum over the players who played of the course rate
                 (`events.course_cost`; a 9/18 combo prices each card by its
                 holes from course_cost_9 / course_cost_18)
    played     = the event's TGF scorecards (`scoring_rounds`), one per person

The email goes only when the overcharge is a WHOLE NUMBER OF PLAYERS at our
rate (within WHOLE_TOLERANCE; a 9/18 combo may mix its two rates), i.e. we
were billed for golfers who did not play (Kerry 10/30, after Olympia Hills
10/6: "build it"). Teravista 10/27: $433.00 charged at $54.13, 6 played,
$108.22 over -> "(2 players)". An overcharge under half a player is noise
(Silverhorn 10/27, $0.06). Anything else at half a player or more is a RATE
or TAX DIFFERENCE, never extra players (Olympia Hills: $825.09 = 21 x $35.00
+ $90.09 tax at 12.26% instead of 8.25%, $29.40 over): no email to the
course; one COO item for Kerry with the arithmetic, once per event per
charge (`course_shortfall_review:<event_id>`).

THE EMAIL (the mockup Kerry approved, #2475-3 / #2476-1): From Kerry (the
Tracker mailbox); To the course's primary TGF contact (the event's course
contacts: `print_pack.course_recipients_for_event`, which reads the frozen
snapshot for a completed event); CC the chapter manager and Kerry. A
thank-you line, "charged for 8 players, but 6 played", a table (Date /
Charged / Played / Credit requested), "If we've missed something on our
side, just reply", the signature.

ONCE per event per charge: `course_shortfall_sent:<event_id>` holds the
charge ids sent for; a NEW charge row re-checks. HOLDS on any blank (no
course contact, no manager address, no course rate, no scorecards, no
date, no course name). Nothing is ever paid or changed.

DIAL `course_shortfall_email` (OFF unless "on"). Preview to staff only.
Bridge `scoring-course-shortfall[:<event_id>][|preview[|<staff>]][|send]`.
"""
from __future__ import annotations

import html as _html
import json
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

DIAL = "course_shortfall_email"
SENT_KEY = "course_shortfall_sent:{}"
CC_KEY = "course_shortfall_cc"
CATEGORIES_KEY = "course_shortfall_categories"
KERRY = "kerry@thegolffellowship.com"
LOOKBACK_DAYS = 30
REVIEW_KEY = "course_shortfall_review:{}"
MAX_EXTRA_PLAYERS = 12     # the whole-player search stops here
DEFAULT_CATEGORIES = ("course fees", "course fee", "golf course fees / green fees", "green fees")
CREDIT_TYPES = ("refund", "credit", "income")

# The approved wording (#2475-3 mockup, Kerry "Approved" #2476-1).
SUBJECT = "Credit request: The Golf Fellowship, {when} ({n} {players})"
THANKS = "Thanks for hosting The Golf Fellowship on {when}."
CHARGED_LINE = "We were charged for {charged} players, but {played} played."
MISSED = "If we've missed something on our side, just reply."
SIGN = "Thanks,<br>Kerry Niester<br>The Golf Fellowship"


def _setting(key, db_path=None):
    from email_parser import database as db
    try:
        return db.get_app_setting(key, db_path=db_path)
    except Exception:
        return None


def dial_on(db_path=None) -> bool:
    return (_setting(DIAL, db_path) or "").strip().lower() == "on"


def _categories(db_path=None) -> tuple:
    raw = (_setting(CATEGORIES_KEY, db_path) or "").strip()
    if raw:
        try:
            v = json.loads(raw)
            if isinstance(v, list) and v:
                return tuple(str(x).strip().lower() for x in v if str(x).strip())
        except ValueError:
            pass
    return DEFAULT_CATEGORIES


def _cc_admin(db_path=None) -> list:
    from email_parser.recap_mail import _addrs
    return _addrs(_setting(CC_KEY, db_path)) or [KERRY]


def _money(v: float) -> str:
    return f"${v:,.2f}"


def _when(event_date: str) -> str:
    try:
        d = date.fromisoformat(str(event_date)[:10])
    except ValueError:
        return ""
    return f"{d.strftime('%A, %B')} {d.day}"


def charges(conn, ev: dict, db_path=None) -> list[dict]:
    """The course-fee rows booked against one event, oldest first. A course
    credit (refund/credit/income on a course-fee category) comes back with a
    negative amount."""
    cats = _categories(db_path)
    ph = ",".join("?" * len(cats))
    base = f"""SELECT id, amount, transaction_date, merchant, transaction_type
              FROM expense_transactions
             WHERE lower(COALESCE(category, '')) IN ({ph})
               AND COALESCE(review_status, 'pending') <> 'ignored'"""
    try:
        rows = conn.execute(
            base + """ AND (event_id = ? OR (event_id IS NULL
                    AND lower(COALESCE(event_name, '')) = lower(?)))
             ORDER BY transaction_date, id""",
            (*cats, int(ev["id"]), ev.get("item_name") or "")).fetchall()
    except Exception:
        # an older database with no expense_transactions.event_id: by name
        rows = conn.execute(
            base + " AND lower(COALESCE(event_name, '')) = lower(?) ORDER BY transaction_date, id",
            (*cats, ev.get("item_name") or "")).fetchall()
    out = []
    for r in rows:
        amt = abs(float(r["amount"] or 0))
        kind = (r["transaction_type"] or "expense").lower()
        out.append({"id": int(r["id"]), "amount": -amt if kind in CREDIT_TYPES else amt,
                    "date": r["transaction_date"], "merchant": r["merchant"], "type": kind})
    return out


def played(conn, event_id: int) -> list[dict]:
    """One row per person with a TGF scorecard on the event (customer_id,
    else the card's name), with the most holes they played."""
    rows = conn.execute(
        "SELECT customer_id, player_name, holes_played FROM scoring_rounds WHERE event_id = ?",
        (int(event_id),)).fetchall()
    people: dict = {}
    for r in rows:
        key = f"c{r['customer_id']}" if r["customer_id"] else f"n{(r['player_name'] or '').strip().lower()}"
        if key == "n":
            continue
        holes = int(r["holes_played"] or 0)
        people[key] = max(people.get(key, 0), holes)
    return [{"key": k, "holes": h} for k, h in people.items()]


def _rate_for(ev: dict, holes: int):
    c9, c18, c = ev.get("course_cost_9"), ev.get("course_cost_18"), ev.get("course_cost")
    if c9 and c18 and float(c9) != float(c18):
        return float(c18) if holes > 9 else float(c9)
    for v in (c, c18 if holes > 9 else c9, c9, c18):
        if v:
            return float(v)
    return None


def _tolerance(rate: float) -> float:
    """How close to a whole player the overcharge must be: $1.00, or 2% of
    the rate when that is more (rounding and card surcharges)."""
    return max(1.00, round(0.02 * rate, 2))


def whole_players(over: float, rates: list) -> int | None:
    """The number of extra players the overcharge is, when it is (within the
    tolerance) a whole count at the event's rate(s); a 9/18 combo may mix its
    two rates. None when it is not whole players."""
    rs = sorted({round(float(r), 2) for r in rates if r})
    if not rs or over <= 0:
        return None
    tol = _tolerance(min(rs))
    best = None
    if len(rs) == 1:
        n = int(round(over / rs[0]))
        if n >= 1 and abs(over - n * rs[0]) <= tol:
            best = n
    else:
        lo, hi = rs[0], rs[-1]
        for a in range(0, MAX_EXTRA_PLAYERS + 1):
            for b in range(0, MAX_EXTRA_PLAYERS + 1 - a):
                if a + b and abs(over - (a * lo + b * hi)) <= tol:
                    if best is None or a + b < best:
                        best = a + b
    return best


def compute(ev: dict, chg: list[dict], who: list[dict]) -> dict:
    """The pure arithmetic. {charged, expected, overcharge, rate, played,
    charged_players, credit_players, due, rate_gap, per_round, held[]}."""
    held = []
    charged = round(sum(c["amount"] for c in chg), 2)
    rates = [_rate_for(ev, p["holes"]) for p in who] if who else [_rate_for(ev, 0)]
    if not rates or any(r is None for r in rates):
        held.append("no course rate on the event (course_cost)")
        return {"charged": charged, "played": len(who), "held": held, "due": False}
    rate = min(rates)
    expected = round(sum(rates), 2) if who else 0.0
    over = round(charged - expected, 2)
    n = whole_players(over, rates) if over >= round(rate / 2.0, 2) else None
    out = {"charged": charged, "expected": expected, "overcharge": over, "rate": rate,
           "played": len(who), "held": held,
           "per_round": round(charged / len(who), 2) if who else None,
           "charged_players": (len(who) + n) if n else len(who),
           "credit_players": n or 0}
    out["due"] = bool(chg) and bool(n)
    # half a player or more, but not whole players: a rate or tax difference
    out["rate_gap"] = bool(chg) and not n and over >= round(rate / 2.0, 2)
    return out


def review_text(b: dict) -> str:
    """The arithmetic Kerry needs before he contacts the course."""
    lines = [f"Charged {_money(b['charged'])} for {b['event']} ({b.get('event_date')}).",
             f"Expected {_money(b['expected'])}: {b['played']} played at our rate {_money(b['rate'])}.",
             f"Over by {_money(b['overcharge'])}, which is not a whole number of players."]
    if b.get("per_round"):
        lines.append(f"Charged works out to {_money(b['per_round'])} a round for the {b['played']} who played "
                     f"({_money(b['per_round'] - b['rate'])} a round more than our rate): a rate, tax or comp "
                     "difference, not extra players.")
    lines.append("Nothing was sent to the course. Check the course's itemized receipt (base rate, tax, any "
                 "comped round) and contact the course yourself if it's wrong.")
    return "\n".join(lines)


def build(event_id: int, db_path=None) -> dict:
    """Everything about one event's shortfall, and the email. Sends nothing."""
    from email_parser import database as db
    from email_parser.print_pack import course_recipients_for_event
    from email_parser.pairings_approval import manager_for
    from email_parser.event_day_email import frame
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(event_id),)).fetchone()
        if not r:
            return {"error": f"no event {event_id}"}
        ev = dict(r)
        chg = charges(conn, ev, db_path)
        who = played(conn, int(event_id))
    calc = compute(ev, chg, who)
    held = list(calc.get("held") or [])
    out = {"event_id": int(event_id), "event": ev.get("item_name"),
           "event_date": str(ev.get("event_date") or "")[:10], "course": ev.get("course"),
           "charges": chg, "charge_ids": sorted(c["id"] for c in chg), **calc}
    if not chg:
        return {**out, "status": "no course charge"}
    if calc.get("rate_gap"):
        return {**out, "status": "rate difference: for Kerry",
                "why": review_text(out)}
    if not calc.get("due"):
        return {**out, "status": "within half a player",
                "why": (f"over by {_money(calc.get('overcharge') or 0)}, under half of "
                        f"{_money(calc['rate'])}") if calc.get("rate") else "no rate"}
    if not who:
        held.append("no TGF scorecards for this event (played count unknown)")
    when = _when(ev.get("event_date"))
    if not when:
        held.append("the event has no date")
    course = (ev.get("course") or "").strip()
    if not course:
        held.append("the event has no course name")
    rec = course_recipients_for_event(ev, db_path)
    if not rec.get("ok"):
        held.append(rec.get("why") or "no course contact on file")
    mgr = manager_for(ev.get("chapter"), db_path) or {}
    if not (mgr.get("email") or "").strip():
        held.append("no chapter manager address")
    from email_parser.recap_mail import staff_only
    adm = _cc_admin(db_path)
    if staff_only(adm, lambda k: _setting(k, db_path)):
        held.append("course_shortfall_cc must be TGF staff addresses")
    cc = []
    for a in [mgr.get("email")] + adm:
        a = (a or "").strip()
        if a and a.lower() not in {x.lower() for x in cc} and a.lower() != (rec.get("to") or "").lower():
            cc.append(a)
    n = calc["credit_players"]
    e = _html.escape
    first = ((rec.get("to_name") or "").split(" ") or [""])[0].strip() or "there"
    td = 'style="padding:6px 8px;border-bottom:1px solid #E5E7EB;"'
    th = 'align="left" style="padding:6px 8px;border-bottom:2px solid #1B1B1B;font-size:13px;"'
    table = ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
             'style="border-collapse:collapse;margin:8px 0 14px;">'
             f'<tr><th {th}>Date</th><th {th}>Charged</th><th {th}>Played</th><th {th}>Credit requested</th></tr>'
             f'<tr><td {td}>{e(when)}</td>'
             f'<td {td}>{_money(calc["charged"])} ({calc["charged_players"]} players)</td>'
             f'<td {td}>{calc["played"]}</td>'
             f'<td {td}><strong>{_money(calc["overcharge"])}</strong> ({n} {"player" if n == 1 else "players"})</td></tr>'
             '</table>')
    inner = (f"<p>Hi {e(first)},</p>"
             f"<p>{e(THANKS.format(when=when))}</p>"
             f"<p>{e(CHARGED_LINE.format(charged=calc['charged_players'], played=calc['played']))}</p>"
             + table + f"<p>{e(MISSED)}</p><p>{SIGN}</p>")
    subject = SUBJECT.format(when=when, n=n, players="player" if n == 1 else "players")
    html = frame(inner, "THE GOLF FELLOWSHIP", "Credit request")
    if "{" in subject + html:
        held.append("leftover {tag}")
    sent = json.loads(_setting(SENT_KEY.format(int(event_id)), db_path) or "{}")
    already = sorted(sent.get("charge_ids") or []) == out["charge_ids"]
    return {**out, "to": rec.get("to"), "to_name": rec.get("to_name"), "cc": cc,
            "subject": subject, "html": html, "held": held, "already_sent": already,
            "sent": sent or None,
            "status": "already sent" if already else ("held" if held else "would send")}


def run_event(event_id: int, confirm: bool = False, db_path=None, sender=None) -> dict:
    """Send (confirm=True, dial on) or dry-run one event's credit request."""
    from email_parser import database as db
    b = build(event_id, db_path)
    if b.get("error"):
        return b
    out = {k: v for k, v in b.items() if k != "html"}
    if b["status"] != "would send":
        return out
    if confirm is not True:
        return {**out, "dry_run": True}
    if not dial_on(db_path):
        return {**out, "status": "off", "why": f"{DIAL} is not on"}
    if sender is None:
        from email_parser.event_day_email import _creds, _graph_send
        creds = _creds()
        if not creds:
            return {**out, "status": "error", "why": "Email credentials not configured on server"}
        sender = lambda to, s, h, cc: _graph_send(creds, to, s, h, cc=",".join(cc) or None)  # noqa: E731
    ok = False
    try:
        ok = bool(sender(b["to"], b["subject"], b["html"], b["cc"]))
    except Exception:
        logger.exception("course shortfall send failed for %s", event_id)
    summary = (f"charged {_money(b['charged'])} ({b['charged_players']}), played {b['played']}, "
               f"credit requested {_money(b['overcharge'])} ({b['credit_players']})")
    try:
        db.log_message({"event_name": b["event"], "channel": "email", "recipient_name": "course contact",
                        "recipient_address": b["to"], "subject": b["subject"], "body_preview": summary,
                        "status": "sent" if ok else "failed", "sent_by": "course-shortfall",
                        "event_id": int(event_id)}, db_path=db_path)
        db.log_agent_action("course-shortfall", "course_shortfall_email",
                            f"event {event_id}: {'sent' if ok else 'FAILED'} to {b['to']} cc {b['cc']}: {summary}",
                            db_path=db_path)
    except Exception:
        pass
    if ok:
        db.set_app_setting(SENT_KEY.format(int(event_id)), json.dumps(
            {"charge_ids": b["charge_ids"], "to": b["to"], "overcharge": b["overcharge"],
             "credit_players": b["credit_players"]}), db_path=db_path)
    return {**out, "status": "sent" if ok else "failed"}


def _raise_review(event_id: int, b: dict, db_path=None) -> bool:
    """One COO item for Kerry per event per set of charges; never an email."""
    from email_parser import database as db
    key = REVIEW_KEY.format(int(event_id))
    ids = sorted(b.get("charge_ids") or [])
    try:
        if json.loads(_setting(key, db_path) or "{}").get("charge_ids") == ids:
            return False
    except ValueError:
        pass
    try:
        db.save_action_item({
            "subject": f"COURSE CHARGE DIFFERS: {b.get('event')}",
            "from_name": "Course shortfall check",
            "summary": b.get("why") or review_text(b),
            "urgency": "medium", "category": "finance"}, db_path=db_path)
        db.set_app_setting(key, json.dumps({"charge_ids": ids, "overcharge": b.get("overcharge")}),
                           db_path=db_path)
        return True
    except Exception:
        logger.exception("course shortfall review item failed for %s", event_id)
        return False


def recent_event_ids(today: str | None = None, days: int = LOOKBACK_DAYS, db_path=None) -> list[int]:
    """Events played in the last `days` days (not today) that carry a course charge."""
    from email_parser import database as db
    from email_parser.timezone_utils import today_central_str
    today = today or today_central_str()
    start = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    with db._connect(db_path) as conn:
        return [int(x[0]) for x in conn.execute(
            "SELECT id FROM events WHERE substr(event_date, 1, 10) >= ? "
            "AND substr(event_date, 1, 10) < ? AND COALESCE(status, 'active') = 'active' "
            "ORDER BY event_date, id", (start, today)).fetchall()]


def check(today: str | None = None, db_path=None, sender=None) -> dict:
    """The job. Nothing unless the dial is on."""
    if not dial_on(db_path):
        return {"status": "off"}
    out = {}
    for eid in recent_event_ids(today, db_path=db_path):
        try:
            r = run_event(eid, confirm=True, db_path=db_path, sender=sender)
            if r.get("status") == "rate difference: for Kerry":
                if _raise_review(eid, r, db_path):
                    out[eid] = "review raised for Kerry"
                continue
            if r.get("status") not in ("no course charge", "within half a player", "already sent"):
                out[eid] = r.get("status")
        except Exception as exc:
            logger.exception("course shortfall failed for %s", eid)
            out[eid] = f"error: {exc}"
    return {"status": "ran", "events": out}


def scan(today: str | None = None, db_path=None) -> dict:
    """Read-only: every recent event with a course charge, and its verdict."""
    rows = []
    for eid in recent_event_ids(today, db_path=db_path):
        b = build(eid, db_path)
        if b.get("status") == "no course charge":
            continue
        rows.append({k: b.get(k) for k in ("event_id", "event", "event_date", "charged", "played",
                                             "rate", "overcharge", "credit_players", "status",
                                             "held", "to", "cc", "subject", "why")})
    return {"dial": "on" if dial_on(db_path) else "off", "events": rows}


def send_preview(event_id: int, to_address: str | None = None, db_path=None) -> dict:
    """ONE sample to staff only. Nothing goes to the course."""
    from email_parser.event_day_email import _creds, _graph_send
    from email_parser.recap_mail import staff_only, _addrs
    to = _addrs(to_address) or [KERRY]
    bad = staff_only(to, lambda k: _setting(k, db_path))
    if bad:
        return {"error": f"a course shortfall preview goes to TGF staff only; refused {bad}"}
    b = build(event_id, db_path)
    if b.get("error"):
        return b
    if not b.get("html"):
        return {"error": f"nothing to preview: {b.get('status')}", **{k: b.get(k) for k in ("why",)}}
    creds = _creds()
    if not creds:
        return {"error": "Email credentials not configured on server"}
    e = _html.escape
    head = (f"<p><strong>Course credit request PREVIEW</strong>. Nothing went to the course. "
            f"Would go To {e(str(b.get('to')))}, CC {e(', '.join(b.get('cc') or []) or 'nobody')}. "
            f"Held now: {e('; '.join(b.get('held') or []) or 'nothing')}. "
            f"Dial {DIAL}: {'on' if dial_on(db_path) else 'OFF'}.</p><hr>")
    ok = _graph_send(creds, ",".join(to), "PREVIEW: " + b["subject"], head + b["html"])
    return {"status": "sent" if ok else "failed", "to": to, "subject": b["subject"]}
