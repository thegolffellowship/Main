"""THE PAYER OF AN ORDER (Kerry 2026-10-30: "Yes, build the payer field with
the migration" / "there's definitely a parent payer element that is
assigned"). Migration 0044, `items.payer_customer_id`.

`items.customer_id` is who PLAYS the line; `payer_customer_id` is who PAID the
order: the order header (billing name, email, address). One payer per order.

- Set at import: `stamp_order(conn, order_id, header)` after save_items inserts
  an order's rows. The header is the parsed ORDER-level customer and email,
  which the parser's guest swaps never touch (`_payer` on each parsed row).
- Never changed by a player edit: it is not in ITEM_COLUMNS, so update_item,
  Assign Guest, change customer and merges cannot write it.
- Read first by credit / WD credit / transfer (credit_buyer.buyer_of).
- Orders already in the Tracker: `backfill(apply)` takes the one row per
  order that carries the billing address (only the payer's row has one),
  then the one row with an email and no "Purchased by" note, then a
  single-customer order. Anything else is reported, never guessed.

Case: item 3162, Peter Rundqvist's spot on Jeff Young's order R293121452.
Assign Guest overwrote the only clues (the note and the email), so the $49
credit followed the player.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

COLUMN = "payer_customer_id"
_PURCHASED_BY = re.compile(r"^\s*purchased by\s", re.I)


def has_column(conn) -> bool:
    try:
        return any(r[1] == COLUMN for r in conn.execute("PRAGMA table_info(items)").fetchall())
    except Exception:
        return False


def payer_of(conn, item: dict) -> int | None:
    """The stored payer of this row's order, or None (not set / no column)."""
    if not has_column(conn):
        return None
    v = item.get(COLUMN)
    if v is None and item.get("id"):
        r = conn.execute(f"SELECT {COLUMN} FROM items WHERE id = ?", (item["id"],)).fetchone()
        v = r[0] if r else None
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def stamp_order(conn, order_id: str, payer_cid: int | None) -> int:
    """Set the payer on every row of an order that has none yet. Never
    overwrites a payer already set. Returns rows stamped."""
    if not order_id or not payer_cid or not has_column(conn):
        return 0
    cur = conn.execute(
        f"UPDATE items SET {COLUMN} = ? WHERE order_id = ? AND {COLUMN} IS NULL",
        (int(payer_cid), str(order_id)))
    return cur.rowcount or 0


def _rows(conn, order_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT id, customer, customer_id, customer_email, notes, address, zip, "
        "email_uid, parent_item_id FROM items WHERE order_id = ? ORDER BY id",
        (order_id,)).fetchall()]


def infer(conn, order_id: str) -> dict:
    """{payer, rule} or {ambiguous: why} for an order already in the Tracker."""
    rows = [r for r in _rows(conn, order_id) if not r.get("parent_item_id")]
    imported = [r for r in rows if not str(r.get("email_uid") or "").startswith(("manual", "buyer-credit"))]
    base = imported or rows
    if not base:
        return {"ambiguous": "no rows"}
    billed = {r["customer_id"] for r in base
              if r.get("customer_id") and ((r.get("address") or "").strip() or (r.get("zip") or "").strip())}
    if len(billed) == 1:
        return {"payer": billed.pop(), "rule": "billing address"}
    emailed = {r["customer_id"] for r in base
               if r.get("customer_id") and (r.get("customer_email") or "").strip()
               and not _PURCHASED_BY.match(r.get("notes") or "")}
    if not billed and len(emailed) == 1:
        return {"payer": emailed.pop(), "rule": "the one row with an email and no Purchased-by note"}
    cids = {r["customer_id"] for r in base if r.get("customer_id")}
    if len(cids) == 1 and len(billed) <= 1:
        return {"payer": cids.pop(), "rule": "single-customer order"}
    why = (f"{len(billed)} rows carry a billing address" if len(billed) > 1
           else f"{len(emailed)} candidate rows with an email" if emailed
           else "no billing address, email or single customer")
    return {"ambiguous": why, "customer_ids": sorted(c for c in cids if c)}


def backfill(apply: bool = False, db_path=None, limit_report: int = 50) -> dict:
    """Stamp the payer on orders already in the Tracker. Dry run by default."""
    from email_parser import database as db
    with db._connect(db_path) as conn:
        if not has_column(conn):
            return {"error": "items.payer_customer_id is missing (migration 0044 not applied)"}
        orders = [r[0] for r in conn.execute(
            f"SELECT DISTINCT order_id FROM items WHERE order_id IS NOT NULL AND TRIM(order_id) != '' "
            f"AND {COLUMN} IS NULL").fetchall()]
        done, ambiguous, rules = 0, [], {}
        for oid in orders:
            res = infer(conn, oid)
            if res.get("payer"):
                rules[res["rule"]] = rules.get(res["rule"], 0) + 1
                if apply:
                    done += stamp_order(conn, oid, res["payer"])
            else:
                ambiguous.append({"order_id": oid, **res})
        if apply:
            conn.commit()
    out = {"orders_without_payer": len(orders), "by_rule": rules,
           "ambiguous": len(ambiguous), "ambiguous_sample": ambiguous[:limit_report],
           "applied": bool(apply)}
    if apply:
        out["rows_stamped"] = done
        try:
            db.log_agent_action("payer", "payer_backfill",
                                f"{done} rows stamped; {len(ambiguous)} orders left for review",
                                db_path=db_path)
        except Exception:
            pass
    return out
