"""VERIFY BEFORE PAY (Kerry 2026-10-28, Event Ops #2460-B).

Kerry, verbatim: "Definitely doesn't make sense to be verifying money and
games after I've made payouts already. That verification needs to happen
before I make payouts, and raise any flags stopping me from running payouts
before I make them."

When auto_payouts records an event's rows they start as VERIFYING. The Pay
buttons for that event (Payouts page tgf.html, Mark Paid
`/api/tgf/mark-paid`, the admin payout report's button) stay locked until
the Tracker's own cross-check passes:
  1. card parity: engine vs every saved card (`card_parity`);
  2. winners re-derived: the GAMES assembly run again now
     (`assemble_event_game_payouts`, the engine preview), customer ids
     resolved as the preview does (`auto_payouts._with_ids`);
  3. recorded = re-derived: the recorded `tgf_payouts` rows equal the
     re-derived rows line for line (customer_id, category, cents).
A failure keeps Pay locked and raises ONE COO action item
"PAYOUTS HELD: <event>" (the auto_payouts pattern, deduped by subject). A
failed event is re-checked when its recorded rows change or every 15
minutes; recorded rows that change after a pass put it back to verifying.

State per event (events.id): app setting `payout_verify:<event_id>` =
{state: verifying|verified|failed, since, checked_at, reasons, recorded_fp,
retry_at}. An event with no such setting (anything recorded by hand, Golf
Genius era, before the dial) is never locked.

Dial `payout_verify_gate`, OFF unless it reads "on". Off = nothing is marked,
nothing is locked, behaviour unchanged. Read-only bridge
`scoring-payout-verify:<event_id>`. Guard test_payout_verify.py.
"""
from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter

logger = logging.getLogger(__name__)

DIAL = "payout_verify_gate"
KEY = "payout_verify:{event_id}"
KEY_PREFIX = "payout_verify:"
RETRY_MINUTES = 15


def gate_on(db_path=None) -> bool:
    from email_parser.database import get_app_setting
    return (get_app_setting(DIAL, db_path) or "off").strip().lower() == "on"


def _now() -> str:
    from email_parser.timezone_utils import now_central
    return now_central().strftime("%Y-%m-%d %H:%M")


def get_state(event_id, db_path=None) -> dict | None:
    from email_parser.database import get_app_setting
    try:
        v = get_app_setting(KEY.format(event_id=int(event_id)), db_path)
        return json.loads(v) if v else None
    except (ValueError, TypeError):
        return None


def _set_state(event_id, st: dict, db_path=None) -> None:
    from email_parser.database import set_app_setting
    set_app_setting(KEY.format(event_id=int(event_id)), json.dumps(st, sort_keys=True), db_path)


def _recorded(conn, event_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT p.id, p.customer_id, p.category, p.amount, p.paid_at "
        "FROM tgf_payouts p JOIN tgf_events t ON t.id = p.event_id "
        "WHERE t.events_id = ?", (int(event_id),)).fetchall()]


def _key(r) -> tuple:
    return (int(r.get("customer_id") or 0), (r.get("category") or "").strip(),
            int(round(float(r.get("amount") or 0) * 100)))


def recorded_fp(rows: list) -> str:
    return hashlib.sha256(json.dumps(sorted(_key(r) for r in rows)).encode()).hexdigest()[:16]


def current_fp(event_id, db_path=None) -> str:
    from email_parser import database as db
    with db._connect(db_path) as conn:
        return recorded_fp(_recorded(conn, event_id))


def mark_verifying(event_id, db_path=None) -> dict:
    """auto_payouts just recorded this event: Pay locks until checked."""
    st = {"state": "verifying", "since": _now(), "checked_at": None, "reasons": [],
          "recorded_fp": current_fp(event_id, db_path)}
    _set_state(event_id, st, db_path)
    return st


def check(event_id, db_path=None) -> dict:
    """The cross-check. Writes nothing. {ok, reasons, recorded_fp, ...}."""
    from email_parser import database as db
    from email_parser import card_parity as cp
    from email_parser import auto_payouts as ap
    from email_parser import score_entry as se
    with db._connect(db_path) as conn:
        ev = conn.execute("SELECT id, item_name FROM events WHERE id = ?",
                          (int(event_id),)).fetchone()
        if not ev:
            return {"error": f"no event {event_id}"}
        rec = _recorded(conn, event_id)
        names = {}
        for r in rec:
            if r["customer_id"] and r["customer_id"] not in names:
                c = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                                 (r["customer_id"],)).fetchone()
                names[r["customer_id"]] = (f"{c['first_name'] or ''} {c['last_name'] or ''}".strip()
                                           if c else f"customer {r['customer_id']}")
    name = ev["item_name"]
    reasons: list[str] = []
    if not rec:
        reasons.append("no payouts are recorded for this event")
    par = cp.engine_card_parity(int(event_id), db_path=db_path)
    if par.get("error"):
        reasons.append(f"card parity could not run: {par['error']}")
    else:
        why = cp.blocking_reason(par)
        if why:
            reasons.append(why)
    asm = db.assemble_event_game_payouts(name, db_path=db_path)
    derived = []
    if asm.get("error"):
        reasons.append(f"the GAMES payouts could not be re-derived: {asm['error']}")
    else:
        read = se.get_entered_scores(int(event_id), db_path=db_path)
        derived = ap._with_ids(asm.get("rows") or [], read, db_path)
        for d in derived:
            if d.get("customer_id") and d["customer_id"] not in names:
                names[d["customer_id"]] = d.get("name") or f"customer {d['customer_id']}"
        if any(not d.get("customer_id") for d in derived):
            reasons.append("re-derived winner(s) with no customer: " + ", ".join(
                sorted({d.get("name") or "?" for d in derived if not d.get("customer_id")})))
        a, b = Counter(_key(r) for r in rec), Counter(_key(d) for d in derived)

        def _line(k):
            return f"{names.get(k[0], f'customer {k[0]}')} {k[1]} ${k[2] / 100:.2f}"
        extra = sorted((a - b).elements())
        missing = sorted((b - a).elements())
        if extra:
            reasons.append("recorded but not won on GAMES now: " + "; ".join(_line(k) for k in extra))
        if missing:
            reasons.append("won on GAMES but not recorded: " + "; ".join(_line(k) for k in missing))
    return {"event_id": int(event_id), "event": name, "ok": not reasons, "reasons": reasons,
            "recorded_rows": len(rec), "recorded_total": round(sum(float(r["amount"] or 0) for r in rec), 2),
            "derived_rows": len(derived),
            "derived_total": round(sum(float(d["amount"] or 0) for d in derived), 2),
            "recorded_fp": recorded_fp(rec)}


def _alarm(name: str, reasons: list, db_path=None) -> None:
    from email_parser import database as db
    try:
        db.save_action_item({
            "subject": f"PAYOUTS HELD: {name}",
            "from_name": "Payout verification",
            "summary": ("Pay is locked for this event: the Tracker's check before paying did not pass.\n"
                        + "\n".join(f"- {r}" for r in reasons)
                        + "\nNothing is paid. Fix the cause (or re-record) and the check runs again."),
            "urgency": "high", "category": "scoring"}, db_path=db_path)
    except Exception:
        logger.exception("payout verify alarm failed for %s", name)


def verify(event_id, db_path=None) -> dict:
    """Run the check and store the verdict; a failure raises one COO item."""
    from email_parser.auto_payouts import _later
    res = check(event_id, db_path)
    if res.get("error"):
        return res
    prev = get_state(event_id, db_path) or {}
    st = {"state": "verified" if res["ok"] else "failed", "since": prev.get("since") or _now(),
          "checked_at": _now(), "reasons": res["reasons"], "recorded_fp": res["recorded_fp"]}
    if not res["ok"]:
        st["retry_at"] = _later(RETRY_MINUTES)
        if prev.get("state") != "failed" or prev.get("reasons") != res["reasons"]:
            _alarm(res["event"], res["reasons"], db_path)
    _set_state(event_id, st, db_path)
    try:
        from email_parser import database as db
        db.log_agent_action("payout-verify", "payout_verify",
                            f"{res['event']}: {st['state']}" + (f" ({'; '.join(res['reasons'])})"
                                                                 if res["reasons"] else ""),
                            outcome=st["state"], db_path=db_path)
    except Exception:
        logger.debug("payout verify action log failed", exc_info=True)
    return {**res, "state": st["state"]}


def lock_reason(st: dict | None, fp_now: str | None) -> str | None:
    """Why Pay is locked for a stored state, or None."""
    if not st:
        return None
    if st.get("state") == "verified":
        if fp_now is not None and st.get("recorded_fp") and fp_now != st["recorded_fp"]:
            return "Verifying: the recorded payouts changed since the check"
        return None
    if st.get("state") == "failed":
        return "Verification failed: " + "; ".join(st.get("reasons") or ["see the COO item"])
    return "Verifying: the Tracker is cross-checking these payouts against the GAMES tab and the cards"


def lock_for(event_id, db_path=None) -> str | None:
    """None = Pay is open. Gate off or never marked = always open."""
    if not event_id or not gate_on(db_path):
        return None
    st = get_state(event_id, db_path)
    return lock_reason(st, current_fp(event_id, db_path) if st else None)


def lock_for_tgf_event(tgf_event_id, db_path=None) -> str | None:
    """Same, from a Payouts-page (tgf_events) id."""
    if not tgf_event_id or not gate_on(db_path):
        return None
    from email_parser import database as db
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT events_id FROM tgf_events WHERE id = ?",
                         (int(tgf_event_id),)).fetchone()
    return lock_for(r[0], db_path) if r and r[0] else None


def annotate(data: dict, db_path=None) -> dict:
    """For /api/tgf: each event gets `pay_locked` (reason or null) and
    `payout_verify` (stored state); each payout row gets `paid_time`
    (Central "YYYY-MM-DD HH:MM", payout_timing). Never raises."""
    try:
        from email_parser.payout_timing import paid_times
        on = gate_on(db_path)
        for ev in data.get("events") or []:
            try:
                pts = paid_times(ev["id"], db_path) if any(
                    p.get("paid_at") for p in ev.get("payouts") or []) else {}
                for p in ev.get("payouts") or []:
                    p["paid_time"] = (pts.get(str(p.get("id"))) or {}).get("at")
                ev["pay_locked"] = None
                if on and ev.get("events_id"):
                    st = get_state(ev["events_id"], db_path)
                    if st:
                        ev["payout_verify"] = st
                        ev["pay_locked"] = lock_reason(st, recorded_fp(ev.get("payouts") or []))
            except Exception:
                logger.exception("payout verify annotate failed for tgf_event %s", ev.get("id"))
    except Exception:
        logger.exception("payout verify annotate failed")
    return data


def sweep(db_path=None) -> list[dict]:
    """The auto_payouts job, each minute: check every event that is
    verifying, failed and due for a retry, or changed since it passed."""
    if not gate_on(db_path):
        return []
    from email_parser import database as db
    from email_parser.auto_payouts import _due
    with db._connect(db_path) as conn:
        keys = [(r[0], r[1]) for r in conn.execute(
            "SELECT key, value FROM app_settings WHERE substr(key, 1, ?) = ?",
            (len(KEY_PREFIX), KEY_PREFIX)).fetchall()]
    out = []
    for k, v in keys:
        try:
            eid = int(k[len(KEY_PREFIX):])
            st = json.loads(v) if v else {}
        except (ValueError, TypeError):
            continue
        fp = current_fp(eid, db_path)
        changed = st.get("recorded_fp") and fp != st.get("recorded_fp")
        due = (st.get("state") == "verifying" or changed
               or (st.get("state") == "failed" and _due(st.get("retry_at"))))
        if not due:
            continue
        try:
            out.append(verify(eid, db_path))
        except Exception as e:
            logger.exception("payout verify failed for event %s", eid)
            out.append({"event_id": eid, "error": str(e)})
    return out
