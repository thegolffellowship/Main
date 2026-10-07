"""CREDIT FROM A RECEIVED PAYMENT, and splitting one payment (Kerry 2026-10-06:
"What do you mean no tool records a payment into a credit? We do that with
regular events. We need that tool now if we don't have it.").

A player credit is an `items` row marked transaction_status='credited'; its
price is the credit's value (`database._item_credit_value`) and the Apply
Credit screens read the pool from those rows (`get_player_credits`). Until
now a credit could only be made FROM an existing registration
(credit_transaction / partial_credit_transaction). Money that arrived by
Venmo or bank with no registration behind it (a received
`expense_transactions` row) had no path into the pool, and one payment
could not be split between, say, an entry and lodging.

`post_credit_from_receipt`:
  * dry run by default: the receipt, the customer, the credit row it would
    write and where the rest of the money goes;
  * refused unless the receipt is money IN, unclaimed (matched_item_id
    empty), the customer exists, the parts sum to the receipt to the cent,
    and the cited mailbox post carries Kerry's word (the same guard as
    set_customer_field, `customer_query._kerry_ok`);
  * apply, in one transaction: one credited row (Manual Entry, the amount,
    customer_id, a note naming the receipt and the Kerry post), the receipt
    claimed by it (matched_item_id) so no second credit can take the same
    money, the split written to the receipt's notes, before/after in
    agent_action_log. NO new ledger row: the promoted receipt stays the one
    ledger entry (CA #785), so income is never counted twice.
`undo_credit_from_receipt` marks the credit row reversed and frees the
receipt; nothing is deleted.

No schema change: every column used already exists.
"""
from __future__ import annotations

import json

RECEIVED = ("received", "income")
MERCHANT = "Credit from receipt"


def _money(v) -> float:
    try:
        return round(float(str(v).replace("$", "").replace(",", "").strip()), 2)
    except (TypeError, ValueError):
        return 0.0


def _cents(v) -> int:
    return int(round(_money(v) * 100))


def post_credit_from_receipt(receipt_id: int, customer_id: int, amount, kerry_ok_post,
                             note: str = "", rest=None, apply: bool = False,
                             set_by: str = "mcp-claude", db_path=None) -> dict:
    """See the module docstring. `rest`: the remainder of the receipt, as a
    list of {"item_id": <that customer's registration>, "amount": x} and/or
    {"label": "LSC lodging", "amount": x}. Empty when the whole receipt
    becomes credit."""
    from email_parser import database as db
    from email_parser.customer_query import _kerry_ok

    rest = rest or []
    if isinstance(rest, str):
        try:
            rest = json.loads(rest) if rest.strip() else []
        except ValueError:
            return {"refused": "rest must be a JSON list of {item_id|label, amount}"}
    amt = _money(amount)
    if amt <= 0:
        return {"refused": "amount must be more than $0"}
    with db._connect(db_path) as conn:
        r = conn.execute("SELECT * FROM expense_transactions WHERE id = ?",
                         (int(receipt_id),)).fetchone()
        if not r:
            return {"refused": f"no receipt {receipt_id}"}
        r = dict(r)
        if (r.get("transaction_type") or "").lower() not in RECEIVED:
            return {"refused": f"receipt {receipt_id} is not money received "
                               f"(transaction_type {r.get('transaction_type')!r})"}
        if r.get("matched_item_id"):
            return {"refused": f"receipt {receipt_id} is already claimed by item "
                               f"{r['matched_item_id']}"}
        c = conn.execute(
            "SELECT customer_id, TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')) AS name, "
            "chapter FROM customers WHERE customer_id = ?", (int(customer_id),)).fetchone()
        if not c:
            return {"refused": f"no customer {customer_id}"}
        parts, total = [], _cents(amt)
        for p in rest:
            pa = _money(p.get("amount"))
            if pa <= 0:
                return {"refused": f"every rest part needs an amount: {p}"}
            if p.get("item_id"):
                it = conn.execute("SELECT id, customer_id, item_name, transaction_status FROM items "
                                  "WHERE id = ?", (int(p["item_id"]),)).fetchone()
                if not it:
                    return {"refused": f"rest item {p['item_id']} not found"}
                if it["customer_id"] != int(customer_id):
                    return {"refused": f"rest item {p['item_id']} is not this customer's"}
                parts.append({"item_id": it["id"], "event": it["item_name"], "amount": pa})
            elif (p.get("label") or "").strip():
                parts.append({"label": p["label"].strip(), "amount": pa})
            else:
                return {"refused": f"a rest part needs item_id or label: {p}"}
            total += _cents(pa)
        if total != _cents(r.get("amount")):
            return {"refused": (f"the parts (${total / 100:.2f}) must equal the receipt "
                                f"(${_money(r.get('amount')):.2f}) to the cent")}
        ok, why = _kerry_ok(conn, kerry_ok_post)
        if not ok:
            return {"refused": why}
        credit_note = (f"Credit from receipt #{r['id']} ({r.get('source_type') or 'payment'} "
                       f"{str(r.get('transaction_date') or '')[:10]}, ${_money(r.get('amount')):.2f}) "
                       f"— Kerry OK {why}" + (f" — {note.strip()}" if (note or "").strip() else ""))
        plan = {
            "receipt": {"id": r["id"], "date": str(r.get("transaction_date") or "")[:10],
                        "source": r.get("source_type"), "amount": _money(r.get("amount")),
                        "from": r.get("merchant"), "handle": r.get("other_party_handle"),
                        "notes": r.get("notes")},
            "customer": {"customer_id": c["customer_id"], "name": c["name"]},
            "credit_row": {"merchant": MERCHANT, "customer": c["name"], "item_price": f"${amt:.2f}",
                           "transaction_status": "credited", "credit_note": credit_note},
            "rest": parts, "kerry_ok": why,
            "ledger": "no new ledger row: the receipt stays the one ledger entry (CA #785)",
        }
        if not apply:
            return {"dry_run": True, **plan}
        uid = f"receipt-credit-{r['id']}"
        cur = conn.execute(
            """INSERT INTO items (email_uid, merchant, customer, customer_id, item_name, item_price,
                                  transaction_status, credit_note, order_date, chapter, notes)
               VALUES (?, ?, ?, ?, ?, ?, 'credited', ?, ?, ?, ?) RETURNING id""",
            (uid, MERCHANT, c["name"], c["customer_id"],
             f"Credit from payment received {str(r.get('transaction_date') or '')[:10]}",
             f"${amt:.2f}", credit_note, str(r.get("transaction_date") or "")[:10] or None,
             c["chapter"] or "", json.dumps({"receipt_id": r["id"], "rest": parts})))
        new_id = cur.fetchone()[0]
        split = json.dumps({"credit_item_id": new_id, "credit": amt, "rest": parts,
                            "kerry_ok": why})
        conn.execute(
            "UPDATE expense_transactions SET matched_item_id = ?, customer_id = COALESCE(customer_id, ?), "
            "notes = TRIM(COALESCE(notes, '') || ' [receipt split ' || ? || ']') "
            "WHERE id = ? AND matched_item_id IS NULL",
            (new_id, c["customer_id"], split, r["id"]))
        conn.commit()
    try:
        db.log_agent_action(set_by, "credit_from_receipt",
                            f"receipt #{receipt_id} -> credit item {new_id} ${amt:.2f} for "
                            f"{plan['customer']['name']} (cid {customer_id}); rest {parts}; "
                            f"before: receipt unclaimed; after: matched_item_id={new_id}; {why}",
                            related_item_id=new_id, db_path=db_path)
    except Exception:  # noqa: BLE001 — the write stands; the log is best effort
        pass
    return {"applied": True, "credit_item_id": new_id, **plan}


def undo_credit_from_receipt(credit_item_id: int, kerry_ok_post, apply: bool = False,
                             set_by: str = "mcp-claude", db_path=None) -> dict:
    """Reverse one credit made here: the row is marked 'reversed' (kept), the
    receipt is freed. Refused once any of the credit has been used."""
    from email_parser import database as db
    from email_parser.customer_query import _kerry_ok
    with db._connect(db_path) as conn:
        it = conn.execute("SELECT * FROM items WHERE id = ?", (int(credit_item_id),)).fetchone()
        if not it or it["merchant"] != MERCHANT:
            return {"refused": f"item {credit_item_id} is not a credit from a receipt"}
        if (it["transaction_status"] or "") != "credited":
            return {"refused": f"item {credit_item_id} is {it['transaction_status']}, not an unused credit"}
        used = conn.execute("SELECT COUNT(*) FROM items WHERE CAST(parent_item_id AS INTEGER) = ?",
                            (it["id"],)).fetchone()[0]
        if used:
            return {"refused": "part of this credit has been applied or paid; undo that first"}
        ok, why = _kerry_ok(conn, kerry_ok_post)
        if not ok:
            return {"refused": why}
        rec = conn.execute("SELECT id FROM expense_transactions WHERE matched_item_id = ?",
                           (it["id"],)).fetchone()
        plan = {"credit_item_id": it["id"], "receipt_id": rec[0] if rec else None, "kerry_ok": why}
        if not apply:
            return {"dry_run": True, **plan}
        # Price to $0 so no total that counts unknown statuses as live reads
        # it as money; the original amount stays in the note.
        conn.execute("UPDATE items SET transaction_status = 'reversed', item_price = '$0.00', "
                     "credit_note = COALESCE(credit_note, '') || ' — REVERSED (was ' || "
                     "COALESCE(item_price, '') || ') ' || ? WHERE id = ?",
                     (why, it["id"]))
        if rec:
            conn.execute("UPDATE expense_transactions SET matched_item_id = NULL WHERE id = ?", (rec[0],))
        conn.commit()
    try:
        db.log_agent_action(set_by, "credit_from_receipt_undo",
                            f"credit item {credit_item_id} reversed; receipt {plan['receipt_id']} freed; {why}",
                            related_item_id=int(credit_item_id), db_path=db_path)
    except Exception:  # noqa: BLE001
        pass
    return {"applied": True, **plan}
