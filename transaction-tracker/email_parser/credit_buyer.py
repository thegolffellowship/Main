"""CREDIT GOES TO THE BUYER (Kerry 2026-10-28, Event Ops #2476-#2478).

Kerry: "Anytime that's under a player purchase any credit would go back to
the person who purchased." and "Jeff was the buyer, he used his coupon code".

A row bought on someone else's order (Peter Rundqvist's spot on Jeff Young's
order, item 3162) used to credit the PLAYER on the row. Now Credit and WD
credit move the money to the BUYER:

- the buyer is the owner of a personal coupon code on the order
  (``tgf-<name>``, mapped to a customer_id in app setting ``coupon_owners``,
  never by name); a personal code with no owner on file on an order that
  holds more than one player HOLDS the credit and asks;
- otherwise, when the row is an extra on the order ("Purchased by" note or
  no customer_email of its own), the buyer is the order's buyer row, the
  same rule ``pickBuyerRow`` uses on Transactions;
- otherwise the player is the buyer and nothing changes.

The move: the original row leaves the credit pool (``transferred`` for a
credit, its ``credit_amount`` cleared for a WD) and a standalone credited
row for the buyer carries the amount, its note naming whose spot it was.
``reverse_credit`` removes that row while it is still unspent.
"""
from __future__ import annotations

import json
import logging
import re
import time

logger = logging.getLogger(__name__)

PERSONAL_COUPON_RE = re.compile(r"^tgf-(?!referr?al)[a-z0-9][a-z0-9-]*$", re.I)
BUYER_CREDIT_UID = "buyer-credit-{item_id}-{ms}"


def coupon_owners(conn) -> dict:
    """{lower(code): customer_id} from app setting ``coupon_owners``."""
    try:
        row = conn.execute("SELECT value FROM app_settings WHERE key = 'coupon_owners'").fetchone()
        raw = json.loads(row[0]) if row and row[0] else {}
        return {str(k).strip().lower(): int(v) for k, v in raw.items() if v}
    except Exception:
        logger.warning("coupon_owners setting unreadable", exc_info=True)
        return {}


def _is_extra(row: dict) -> bool:
    note = (row.get("notes") or "")
    return ("purchased by" in note.lower()) or not (row.get("customer_email") or "").strip()


def buyer_of(conn, item: dict) -> dict:
    """Who a credit on ``item`` belongs to.

    Returns {"buyer_id", "buyer_name", "reason"} when someone else bought the
    spot, {"hold": reason} when it can't be told, or {} when the player on
    the row is the buyer."""
    cid = item.get("customer_id")
    order_id = (item.get("order_id") or "").strip()
    if not order_id or item.get("parent_item_id"):
        return {}
    rows = [dict(r) for r in conn.execute(
        "SELECT id, customer, customer_id, customer_email, notes, coupon_code "
        "FROM items WHERE order_id = ? AND parent_item_id IS NULL ORDER BY id",
        (order_id,)).fetchall()]
    players = {r["customer_id"] for r in rows if r.get("customer_id")}
    code = next((str(r["coupon_code"]).strip() for r in rows
                 if r.get("coupon_code") and PERSONAL_COUPON_RE.match(str(r["coupon_code"]).strip())), "")
    if code:
        owner = coupon_owners(conn).get(code.lower())
        if owner:
            if owner == cid:
                return {}
            return _named(conn, owner, f"coupon {code}")
    # THE STORED PAYER (Kerry 10/30, migration 0044): who paid the order,
    # set at import and never moved by a player edit. A mapped personal
    # coupon's owner (above) still wins; otherwise the stored payer is the
    # answer, and the coupon hold and the note/email clues below are only
    # for rows without one.
    from email_parser.payer import payer_of
    payer = payer_of(conn, item)
    if payer:
        if payer == cid:
            return {}
        return _named(conn, payer, f"payer of order {order_id}")
    if code and len(players) > 1:
        return {"hold": f"coupon {code} has no owner on file (app setting coupon_owners); "
                        "set it before crediting this order"}
    if not _is_extra(item):
        return {}
    buyer = next((r for r in rows if (r.get("customer_email") or "").strip()
                  and "purchased by" not in (r.get("notes") or "").lower()), None)
    if not buyer or not buyer.get("customer_id"):
        return {"hold": f"order {order_id}: no buyer row with a customer_id"}
    if buyer["customer_id"] == cid:
        return {}
    return _named(conn, buyer["customer_id"], f"buyer of order {order_id}")


def _named(conn, customer_id: int, reason: str) -> dict:
    r = conn.execute("SELECT first_name, last_name FROM customers WHERE customer_id = ?",
                     (customer_id,)).fetchone()
    name = f"{r[0] or ''} {r[1] or ''}".strip() if r else ""
    return {"buyer_id": customer_id, "buyer_name": name, "reason": reason}


def post_buyer_credit(conn, item: dict, amount: float, buyer: dict) -> int:
    """Insert the buyer's standalone credited row; returns its id."""
    from .timezone_utils import today_central_str
    uid = BUYER_CREDIT_UID.format(item_id=item["id"], ms=int(time.time() * 1000))
    email = conn.execute(
        "SELECT email FROM customer_emails WHERE customer_id = ? ORDER BY is_primary DESC, email_id LIMIT 1",
        (buyer["buyer_id"],)).fetchone()
    note = (f"Credit for {item.get('customer') or 'player'}'s spot (item {item['id']}), "
            f"bought by {buyer['buyer_name']} ({buyer['reason']})")
    cur = conn.execute(
        """INSERT INTO items
           (email_uid, merchant, customer, customer_email, item_name, item_price,
            transaction_status, credit_note, order_date, chapter, customer_id,
            order_id, notes)
           VALUES (?, 'Manual Entry', ?, ?, ?, ?, 'credited', ?, ?, ?, ?, ?, ?)
           RETURNING id""",
        (uid, buyer["buyer_name"], email[0] if email else None, item.get("item_name"),
         f"${amount:.2f}", note, today_central_str(), item.get("chapter") or "",
         buyer["buyer_id"], item.get("order_id"), note))
    return cur.fetchone()[0]


def personal_coupons(conn) -> list[dict]:
    """Every personal code seen on orders, how many orders carry it, and its
    owner on file (bridge ``scoring-coupon-owners``, read-only)."""
    owners = coupon_owners(conn)
    out = {}
    for r in conn.execute(
            "SELECT lower(trim(coupon_code)) AS code, order_id, customer_id FROM items "
            "WHERE coupon_code IS NOT NULL AND trim(coupon_code) != '' AND parent_item_id IS NULL").fetchall():
        if not PERSONAL_COUPON_RE.match(r[0] or ""):
            continue
        d = out.setdefault(r[0], {"code": r[0], "orders": set(), "players": set()})
        d["orders"].add(r[1])
        if r[2]:
            d["players"].add(r[2])
    return sorted(({"code": d["code"], "orders": len(d["orders"]), "player_ids": sorted(d["players"]),
                    "owner_id": owners.get(d["code"])} for d in out.values()), key=lambda x: x["code"])
