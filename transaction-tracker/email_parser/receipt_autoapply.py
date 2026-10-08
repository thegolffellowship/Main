"""AUTO-APPLY a received payment to a one-off event roster (Kerry 2026-10-07,
CoS #1377-1: "Ok. Build it.").

The rule, exactly as approved: a Venmo or Cash App receipt that the retriever
matched to a customer at confidence >= 85, where that customer is on the roster
of an OPEN one-off event (an event in the `oneoff_charges` dial dated today or
later), and the amount equals that player's open balance, or the balance plus
one add-on he is not yet marked for (Friday, skins), is linked to the event.
The roster reads PAID at once (it reads expense_transactions.event_id). The
row stays `pending` and carries "auto · CFO to confirm" in its notes; the
CFO's review confirms (promotes) or reverses it. Anything that doesn't match
exactly stays pending, untouched.

What it writes: expense_transactions.event_id / event_name / notes, and, for
the balance + add-on case, the player's add-on mark (set_oneoff_addon, so his
expected matches what he paid). No ledger row, no money moved, nothing sent.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 85
SOURCES = ("venmo", "cashapp", "cash_app", "cash app")
FLAG = "auto · CFO to confirm"


def _cents(v) -> int:
    try:
        return int(round(float(v) * 100))
    except (TypeError, ValueError):
        return 0


def _open_oneoff_events(conn, db_path=None) -> list[dict]:
    import json
    from email_parser import database as db
    from email_parser.timezone_utils import today_central_str
    try:
        cfgs = json.loads(db.get_app_setting("oneoff_charges", db_path=db_path) or "{}")
    except Exception:
        return []
    ids = []
    for k in cfgs:
        try:
            ids.append(int(k))
        except (TypeError, ValueError):
            continue
    if not ids:
        return []
    today = today_central_str()
    ph = ",".join("?" for _ in ids)
    return [dict(r) for r in conn.execute(
        f"SELECT id, item_name, event_date FROM events WHERE id IN ({ph}) "
        "AND COALESCE(event_date, '') >= ? ORDER BY event_date", (*ids, today))]


def plan_auto_apply(expense_id: int, db_path=None) -> dict:
    """What auto-apply would do for one receipt, without writing."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM expense_transactions WHERE id = ?",
                         (int(expense_id),)).fetchone()
        if not r:
            return {"apply": False, "why": "no such receipt"}
        r = dict(r)
        if (r.get("transaction_type") or "").lower() != "received":
            return {"apply": False, "why": "not money received"}
        if (r.get("source_type") or "").lower() not in SOURCES:
            return {"apply": False, "why": f"source {r.get('source_type')} is not Venmo or Cash App"}
        if (r.get("review_status") or "") != "pending":
            return {"apply": False, "why": f"review_status is {r.get('review_status')}, not pending"}
        if r.get("event_id"):
            return {"apply": False, "why": "already linked to an event"}
        if not r.get("customer_id"):
            return {"apply": False, "why": "no customer matched"}
        if int(r.get("confidence") or 0) < MIN_CONFIDENCE:
            return {"apply": False, "why": f"match confidence {r.get('confidence')} < {MIN_CONFIDENCE}"}
        events = _open_oneoff_events(conn, db_path)
    cid, amt = int(r["customer_id"]), _cents(r.get("amount"))
    hits = []
    for ev in events:
        fin = db.get_oneoff_roster_finance(ev["id"], db_path=db_path, include_shirts=False) or {}
        p = (fin.get("players") or {}).get(str(cid))
        if not p or p.get("expected") is None:
            continue
        bal = _cents(p.get("balance"))
        if bal <= 0:
            continue
        if amt == bal:
            hits.append({"event_id": ev["id"], "event_name": ev["item_name"], "addon": None,
                         "balance": bal / 100})
            continue
        for a in (fin.get("config") or {}).get("addons") or []:
            marked = (p.get("addons") or {}).get(a["key"])
            if not marked and amt == bal + _cents(a.get("amount")):
                hits.append({"event_id": ev["id"], "event_name": ev["item_name"],
                             "addon": a["key"], "addon_label": a.get("label") or a["key"],
                             "balance": bal / 100})
                break
    if len(hits) != 1:
        return {"apply": False, "why": ("no open roster balance equals this amount" if not hits
                                        else "more than one event matches; left for the CFO"),
                "candidates": hits}
    return {"apply": True, "expense_id": int(expense_id), "customer_id": cid,
            "amount": amt / 100, **hits[0]}


def auto_apply_receipt(expense_id: int, db_path=None) -> dict:
    """Apply the plan. Never raises; returns the plan with applied True/False."""
    from email_parser import database as db
    try:
        plan = plan_auto_apply(expense_id, db_path=db_path)
        if not plan.get("apply"):
            return {**plan, "applied": False}
        note = (f"{FLAG}: linked to {plan['event_name']} (event {plan['event_id']}), "
                f"amount = open balance ${plan['balance']:.2f}"
                + (f" + {plan['addon_label']}" if plan.get("addon") else ""))
        with db._connect(db_path) as conn:
            cur = conn.execute(
                "UPDATE expense_transactions SET event_id = ?, event_name = ?, "
                "notes = TRIM(COALESCE(notes, '') || ' · ' || ?) "
                "WHERE id = ? AND event_id IS NULL AND review_status = 'pending'",
                (plan["event_id"], plan["event_name"], note, plan["expense_id"]))
            conn.commit()
            if cur.rowcount != 1:
                return {**plan, "applied": False, "why": "the receipt changed before it was applied"}
        if plan.get("addon"):
            db.set_oneoff_addon(plan["event_id"], plan["customer_id"], plan["addon"], True,
                                db_path=db_path)
        try:
            db.log_agent_action("auto-apply", "receipt_auto_apply", note,
                                db_path=db_path)
        except Exception:  # noqa: BLE001 — the write stands; the log is best effort
            pass
        return {**plan, "applied": True, "note": note}
    except Exception:
        logger.exception("receipt auto-apply failed for expense %s", expense_id)
        return {"applied": False, "why": "error; left pending"}
