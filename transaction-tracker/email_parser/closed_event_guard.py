"""THE CLOSED-EVENT REACTIVATION CHECK (Kerry 2026-10-28, Event Ops #2477-3).

What happened: Kerry pressed REVERSE on item 3162 (Peter Rundqvist) on the
closed event 3303 (s9.29 Silverhorn). Peter became active again, the GAMES
tab went from 24 players / $505 to 25 / $511, and the field count, the HIO
pot line, the financial summary and the results audience would have
followed. Peter did not play.

The guard WARNS and RECORDS; it never blocks (Kerry may mean it):
- `check(item_id)`: is the item's event closed (payouts recorded, or the
  closeout's own `closeout_final_check` passes)? The UI asks it before the
  Reverse confirm (`GET /api/items/<id>/reactivation-check`) and puts the
  warning in the confirm text.
- `after_reactivate(item_id, how, by)`: after a reverse (credit / WD /
  transfer / refund) or a status set back to active on a closed event,
  ONE COO action item naming the event and the item (de-duped by subject
  while open) and an agent_action_log line.
Callers: app.py `/api/items/<id>/reverse-credit`, PATCH `/api/items/<id>`
(transaction_status -> active), MCP `undo_credit_or_transfer`.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

WARNING = "This event is closed: reactivating changes its field count and games."
ACTIVE_LIKE = ("active", "", None)


def _item(conn, item_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM items WHERE id = ?", (int(item_id),)).fetchone()
    return dict(r) if r else None


def _event_for(conn, item: dict) -> dict | None:
    if item.get("event_id"):
        r = conn.execute("SELECT * FROM events WHERE id = ?", (int(item["event_id"]),)).fetchone()
        if r:
            return dict(r)
    name = (item.get("item_name") or "").strip()
    if not name:
        return None
    r = conn.execute("SELECT * FROM events WHERE lower(item_name) = lower(?) ORDER BY id DESC",
                     (name,)).fetchone()
    return dict(r) if r else None


def event_closed(ev: dict, db_path=None) -> tuple[bool, str]:
    """(closed, why). Payouts recorded is enough; else the closeout's own
    final check, only for an event whose date has passed."""
    from email_parser import database as db
    from email_parser.closeout_checks import _payout_rows, closeout_final_check
    from email_parser.timezone_utils import today_central_str
    with db._connect(db_path) as conn:
        pays = _payout_rows(conn, int(ev["id"]))
    if pays:
        return True, f"payouts recorded ({len(pays)})"
    if str(ev.get("event_date") or "")[:10] >= today_central_str():
        return False, "not played yet"
    try:
        if closeout_final_check(int(ev["id"]), db_path=db_path).get("final"):
            return True, "closeout final"
    except Exception:
        logger.exception("closed-event guard: final check failed for %s", ev.get("id"))
    return False, "not closed"


def check(item_id: int, db_path=None) -> dict:
    """{closed, warning, event_id, event, why} for the item's event. Never
    raises: a failed check reads as not closed, so the action still runs."""
    try:
        return _check(item_id, db_path)
    except Exception:
        logger.exception("closed-event guard: check failed for item %s", item_id)
        return {"closed": False, "why": "check failed", "item_id": int(item_id)}


def _check(item_id: int, db_path=None) -> dict:
    from email_parser import database as db
    with db._connect(db_path) as conn:
        it = _item(conn, item_id)
        if not it:
            return {"closed": False, "why": "no such item"}
        ev = _event_for(conn, it)
    if not ev:
        return {"closed": False, "why": "no event for this item", "item_id": int(item_id)}
    closed, why = event_closed(ev, db_path)
    return {"closed": closed, "why": why, "warning": WARNING if closed else None,
            "item_id": int(item_id), "event_id": int(ev["id"]), "event": ev.get("item_name"),
            "customer": it.get("customer"), "customer_id": it.get("customer_id"),
            "status": it.get("transaction_status")}


def after_reactivate(item_id: int, how: str, by: str = "", pre: dict | None = None,
                     db_path=None) -> dict | None:
    """Raise one COO item when an item on a CLOSED event became active.
    `pre` is the check() taken before the change (the status before)."""
    from email_parser import database as db
    try:
        c = pre if pre is not None else check(item_id, db_path)
        if not c.get("closed"):
            return None
        subject = f"CLOSED EVENT REACTIVATED: {c.get('event')} item {int(item_id)}"
        summary = (f"{c.get('customer') or 'A player'} (customer {c.get('customer_id')}, item {int(item_id)}) "
                   f"on {c.get('event')} (event {c.get('event_id')}, {c.get('why')}) was made active "
                   f"again by {how}{' (' + by + ')' if by else ''}; it was "
                   f"{c.get('status') or 'not active'}. The event is closed: its field count, games, "
                   "HIO pot line, financial summary and results audience now count this player. "
                   "If he did not play, put the row back (Credit / WD); if he did, nothing to do.")
        row = db.save_action_item({"subject": subject, "from_name": "Closed-event guard",
                                   "summary": summary, "urgency": "high", "category": "other",
                                   "confidence": 100}, db_path=db_path)
        try:
            db.log_agent_action("closed-event-guard", "closed_event_reactivated", summary[:500],
                                db_path=db_path)
        except Exception:
            pass
        return {"action_item_id": row.get("id"), "subject": subject}
    except Exception:
        logger.exception("closed-event guard failed for item %s", item_id)
        return None


def reverse_and_recredit(item_id: int, by: str = "", db_path=None) -> dict:
    """Reverse on a CLOSED event, answered "He didn't play" (Kerry 10/30,
    option A: "A reversed slot on a closed event should be asked right there
    one or the other" / "A"). Undo the credit and credit the BUYER in the
    same step: the row never stays active, so the closed event's field,
    games, HIO line and results audience never count him, and the money
    never sits on nobody. Refuses before changing anything when the buyer
    can't be told (a personal coupon with no owner on file)."""
    from email_parser import database as db
    from email_parser import credit_buyer as cb
    with db._connect(db_path) as conn:
        it = _item(conn, item_id)
        if not it:
            return {"error": "no such item"}
        if (it.get("transaction_status") or "active") not in ("credited", "transferred", "wd"):
            return {"error": "Item is not credited, transferred or WD; nothing to reverse."}
        b = cb.buyer_of(conn, it)
    if b.get("hold"):
        return {"error": f"Nothing changed. Credit held: {b['hold']}"}
    if not db.reverse_credit(item_id, db_path=db_path):
        return {"error": "Item not found or not in credited/transferred state."}
    try:
        ok = db.credit_item(item_id, note="Re-credited after Reverse on a closed event: did not play",
                            db_path=db_path)
    except db.CreditHold as e:
        ok, why = False, str(e)
    else:
        why = ""
    if not ok:
        # The row is active again on a closed event: say so loudly, once.
        after_reactivate(item_id, "Reverse (re-credit failed)", by, db_path=db_path)
        return {"error": f"Reversed, but the re-credit did not run{': ' + why if why else ''}. "
                         "The spot is active again; press Credit."}
    who = b.get("buyer_name") or it.get("customer") or "the player"
    msg = (f"Credit moved to {who} (bought on their order). The event stays as it closed."
           if b.get("buyer_id") else
           f"Credit put back on {who}. The event stays as it closed.")
    try:
        db.log_agent_action("closed-event-guard", "closed_event_recredit",
                            f"item {int(item_id)} on closed event: reversed and re-credited to "
                            f"{who} (customer {b.get('buyer_id') or it.get('customer_id')}); by {by or '?'}",
                            db_path=db_path)
    except Exception:
        pass
    return {"status": "ok", "recredited_to": who, "buyer_id": b.get("buyer_id"), "message": msg}
