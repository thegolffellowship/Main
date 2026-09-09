"""
One order, one fee — and the item rows underneath must add back to it.

Kerry, 2026-09-09, on the campaign margin table: "I don't think the FEE
NET lines are correct for Will Wallace's transactions. Transaction fee
on the one attached with multiple line items was $10.92. My calculation
for GoDaddy fees is $9.66. So the diff is +$1.26 which would be prorated
across all of those line items." And, on the wider pattern: "it seems
like we're working with error resolution or differences of amounts as
an accepted standard."

The bookkeeping layer was already right: one `acct_transactions` row per
GoDaddy order carrying what the card was charged, what GoDaddy took and
what was deposited. The reporting layer under it was not. The parser
stamps the ORDER's 3.5% fee onto every item row of a multi-item order,
the splits writer copied that stamp into a `transaction_fee` split per
item, the allocator split the GoDaddy fee EQUALLY per item, and the
campaign table split the deposit by registration share. One fee, three
apportionments — which is how a $10.92 fee became $43.68 of fee-in and
how Monthly Money Flow's RETAINED overstated by ~$1,098 across 145
multi-item orders (mailbox #423 §2).

Ratified 2026-09-09 (Kerry: "it seems like you can go ahead, yes"), the
standard is the one every processor and ledger uses:

  * The fee is recorded ONCE, per order.  (Unchanged — already true.)
  * Each item's share, for reporting, is pro rata BY ITEM PRICE, and the
    shares add back to the order's fee to the cent.  Never an equal
    split; never the order's fee stamped per item.
  * The invariant is checked, not assumed: `fee_split_integrity` runs in
    the data-quality audit and reports any order whose item rows do not
    sum to its order row.

This module holds the one pro-rata routine every writer uses, the
integrity check, and the one-time repair of the rows written before
today. Single-item orders are untouched by all of it.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Tolerance for "adds back to the order": one cent of rounding per leg.
TOLERANCE = 0.02


def prorate(total: float, weights: list[float]) -> list[float]:
    """Split `total` across `weights` in proportion, to the cent, with
    the LAST non-zero share absorbing the rounding so the parts always
    sum to the whole. A zero or negative weight gets nothing."""
    total = round(float(total or 0), 2)
    ws = [max(float(w or 0), 0.0) for w in weights]
    base = sum(ws)
    if not ws:
        return []
    if base <= 0:
        # Nothing to weight by: give it all to the first item rather
        # than lose it. (An order of $0 items never gets here in
        # practice — the writer skips zero-price items.)
        return [total] + [0.0] * (len(ws) - 1)
    shares = [round(total * w / base, 2) for w in ws]
    drift = round(total - sum(shares), 2)
    if abs(drift) >= 0.005:
        last = max(i for i, w in enumerate(ws) if w > 0)
        shares[last] = round(shares[last] + drift, 2)
    return shares


def order_fee_from_items(prices: list[float], fees: list[float],
                         pct: float = 3.5) -> float:
    """The ORDER's transaction fee, from per-item rows that may carry it
    either way. The parser stamps the whole order fee on every item of a
    multi-item order; a correctly pro-rated row set sums to it. Decide
    by which reading lands nearer the nominal percentage of the item
    total — two identical items legitimately carry equal shares, so
    "all equal" alone is not proof of a stamp."""
    fees = [round(float(f or 0), 2) for f in fees]
    if len(fees) <= 1:
        return round(sum(fees), 2)
    nominal = round(sum(float(p or 0) for p in prices) * pct / 100.0, 2)
    stamped = fees[0] if len({f for f in fees}) == 1 else None
    summed = round(sum(fees), 2)
    if stamped is None:
        return summed
    return stamped if abs(stamped - nominal) <= abs(summed - nominal) else summed


def _order_rows(conn: sqlite3.Connection) -> list[dict]:
    """Every active GoDaddy order entry with its per-item splits folded
    into one dict: {txn, order_id, charged, merchant_fee, items: {item_id:
    {reg, fee, merchant, coupon}}}."""
    txns = conn.execute(
        """SELECT id, source_ref, merchant_fee, net_deposit
           FROM acct_transactions
           WHERE category = 'godaddy_order'
             AND source_ref LIKE 'godaddy-order-%'
             AND COALESCE(status, 'active') = 'active'"""
    ).fetchall()
    by_id = {}
    for t in txns:
        # What the card was CHARGED = what GoDaddy deposited + what it
        # kept. (`amount` is not used: the writer stores the deposit
        # there while an older repair stored the charged total, so it
        # means different things on different rows.)
        _nd = None if t["net_deposit"] is None else float(t["net_deposit"])
        _mf = None if t["merchant_fee"] is None else float(t["merchant_fee"])
        by_id[t["id"]] = {
            "txn": t["id"],
            "order_id": (t["source_ref"] or "").replace("godaddy-order-", ""),
            "charged": (round(_nd + _mf, 2) if _nd is not None and _mf is not None
                        else None),
            "merchant_fee": _mf,
            "items": {},
        }
    if not by_id:
        return []
    for s in conn.execute(
            """SELECT id, transaction_id, item_id, split_type, amount
               FROM godaddy_order_splits
               WHERE item_id IS NOT NULL
               ORDER BY transaction_id, item_id, id"""):
        o = by_id.get(s["transaction_id"])
        if o is None:
            continue
        it = o["items"].setdefault(
            s["item_id"], {"reg": 0.0, "fee": 0.0, "merchant": 0.0,
                           "coupon": 0.0, "fee_ids": [], "merchant_ids": []})
        amt = float(s["amount"] or 0)
        if s["split_type"] == "registration":
            it["reg"] += amt
        elif s["split_type"] == "transaction_fee":
            it["fee"] += amt
            it["fee_ids"].append(s["id"])
        elif s["split_type"] == "merchant_fee":
            it["merchant"] += abs(amt)
            it["merchant_ids"].append(s["id"])
        elif s["split_type"] == "coupon":
            it["coupon"] += amt
    return [o for o in by_id.values() if o["items"]]


def _item_fee_total(o: dict) -> float:
    """The ORDER's transaction fee as its item rows carry it — stamped
    once per item (the defect) or already shared out — decided by
    `order_fee_from_items`. Read from the item rows on purpose: the
    order row's deposit can legitimately drift from the item rows later
    (a refund or credit adjusts what was deposited; the splits stay as
    sold), so "charged minus registrations" is NOT the fee on those
    orders. That divergence is reported separately, never "repaired"."""
    prices = [i["reg"] for i in o["items"].values()]
    fees = [i["fee"] for i in o["items"].values()]
    return order_fee_from_items(prices, fees)


def _order_row_gap(o: dict, fee_total: float) -> float | None:
    """How far the order row's charged total sits from what its item
    rows add up to (registrations + fee + coupons). None when the order
    row has no deposit/fee recorded. Non-zero means the order row and
    its splits have diverged — a different class of problem from the
    fee stamp, listed for a human, not rewritten by the repair."""
    if o["charged"] is None:
        return None
    reg = sum(i["reg"] for i in o["items"].values())
    coupon = sum(i["coupon"] for i in o["items"].values())
    return round(o["charged"] - (reg + fee_total + coupon), 2)


def fee_split_integrity(conn: sqlite3.Connection, limit: int = 25) -> dict:
    """Do the item rows of every order add back to ONE order fee?
    Reported, never assumed. `offenders` are orders whose fee rows do
    not (the stamp, or a merchant split that does not sum to the order's
    merchant fee). `diverged` are orders whose ORDER ROW no longer
    matches its item rows at all — a refund or credit moved the deposit
    after the splits were written — listed so a person can look, and
    deliberately outside the repair's reach."""
    orders = _order_rows(conn)
    offenders, diverged = [], []
    multi = 0
    for o in orders:
        items = o["items"]
        if len(items) > 1:
            multi += 1
        fee_expected = _item_fee_total(o)
        fee_actual = round(sum(i["fee"] for i in items.values()), 2)
        merch_expected = (round(o["merchant_fee"], 2)
                          if o["merchant_fee"] is not None else None)
        merch_actual = round(sum(i["merchant"] for i in items.values()), 2)
        bad_fee = abs(fee_actual - fee_expected) > TOLERANCE
        bad_merch = (merch_expected is not None
                     and abs(merch_actual - merch_expected) > TOLERANCE)
        if bad_fee or bad_merch:
            offenders.append({
                "order_id": o["order_id"], "items": len(items),
                "fee_in_expected": fee_expected, "fee_in_actual": fee_actual,
                "merchant_expected": merch_expected,
                "merchant_actual": merch_actual,
            })
        gap = _order_row_gap(o, fee_expected)
        if gap is not None and abs(gap) > 0.05:
            diverged.append({
                "order_id": o["order_id"], "items": len(items),
                "charged_on_order_row": o["charged"],
                "items_add_up_to": round(o["charged"] - gap, 2),
                "gap": gap,
            })
    offenders.sort(key=lambda r: -abs(r["fee_in_actual"] - r["fee_in_expected"]))
    diverged.sort(key=lambda r: -abs(r["gap"]))
    return {
        "orders": len(orders),
        "multi_item_orders": multi,
        "offenders": len(offenders),
        "fee_in_overstated": round(sum(r["fee_in_actual"] - r["fee_in_expected"]
                                       for r in offenders), 2),
        "ok": not offenders,
        "sample": offenders[:limit],
        "diverged": len(diverged),
        "diverged_note": ("order row (deposit + GoDaddy fee) does not equal the "
                          "item rows; usually a later refund/credit. Not touched "
                          "by the fee repair."),
        "diverged_sample": diverged[:limit],
    }


def repair_multi_item_fee_splits(dry_run: bool = True,
                                 db_path: str | Path | None = None) -> dict:
    """Rewrite the per-item fee rows of every multi-item order so they
    are that order's fee pro rata by item price, and the merchant-fee
    rows likewise. The order row (`acct_transactions`) is NOT touched —
    it was right. `acct_allocations.godaddy_fee` for the same items is
    re-stamped with the merchant share so the allocator agrees with the
    splits. Single-item orders are skipped: one item, one share.

    Ratified by Kerry 2026-09-09. Dry-run by default; the report carries
    before/after totals per order and per month so the apply can be
    checked against what was promised."""
    from . import database as db
    out = {"dry_run": dry_run, "orders_scanned": 0, "multi_item_orders": 0,
           "orders_changed": 0, "fee_in_before": 0.0, "fee_in_after": 0.0,
           "merchant_before": 0.0, "merchant_after": 0.0,
           "allocations_restamped": 0, "by_month": {}, "orders": []}
    with db._connect(db_path) as conn:
        orders = _order_rows(conn)
        out["orders_scanned"] = len(orders)
        for o in orders:
            items = o["items"]
            if len(items) < 2:
                continue
            out["multi_item_orders"] += 1
            item_ids = list(items.keys())
            prices = [items[i]["reg"] for i in item_ids]
            # The fee comes from the item rows (see _item_fee_total); the
            # merchant total from the order row when the splits already
            # agree with it to a nickel, otherwise from the splits
            # themselves — a diverged order keeps its own total and only
            # has its SHARES corrected.
            fee_total = _item_fee_total(o)
            _split_merch = round(sum(items[i]["merchant"] for i in item_ids), 2)
            merch_total = _split_merch
            if (o["merchant_fee"] is not None
                    and abs(round(o["merchant_fee"], 2) - _split_merch) <= 0.05):
                merch_total = round(o["merchant_fee"], 2)
            fee_shares = prorate(fee_total, prices)
            merch_shares = prorate(merch_total, prices)
            before_fee = round(sum(items[i]["fee"] for i in item_ids), 2)
            before_merch = round(sum(items[i]["merchant"] for i in item_ids), 2)
            changed = any(
                abs(items[i]["fee"] - fee_shares[k]) > 0.005
                or abs(items[i]["merchant"] - merch_shares[k]) > 0.005
                for k, i in enumerate(item_ids))
            out["fee_in_before"] = round(out["fee_in_before"] + before_fee, 2)
            out["fee_in_after"] = round(out["fee_in_after"] + fee_total, 2)
            out["merchant_before"] = round(out["merchant_before"] + before_merch, 2)
            out["merchant_after"] = round(out["merchant_after"] + merch_total, 2)
            if not changed:
                continue
            out["orders_changed"] += 1
            month = (conn.execute(
                "SELECT COALESCE(MIN(order_date),'') AS d FROM items "
                "WHERE order_id = ?", (o["order_id"],)).fetchone()["d"] or "")[:7]
            m = out["by_month"].setdefault(month or "?", {"orders": 0, "fee_in_delta": 0.0})
            m["orders"] += 1
            m["fee_in_delta"] = round(m["fee_in_delta"] + (fee_total - before_fee), 2)
            rows = []
            for k, iid in enumerate(item_ids):
                rows.append({"item_id": iid, "price": prices[k],
                             "fee_before": round(items[iid]["fee"], 2),
                             "fee_after": fee_shares[k],
                             "merchant_before": round(items[iid]["merchant"], 2),
                             "merchant_after": merch_shares[k]})
                if dry_run:
                    continue
                # transaction_fee rows: keep the first, retarget it, drop
                # any duplicates; create one if the item had none.
                fids = items[iid]["fee_ids"]
                if fids:
                    conn.execute("UPDATE godaddy_order_splits SET amount = ? "
                                 "WHERE id = ?", (fee_shares[k], fids[0]))
                    for extra in fids[1:]:
                        conn.execute("DELETE FROM godaddy_order_splits WHERE id = ?",
                                     (extra,))
                elif fee_shares[k] > 0:
                    conn.execute(
                        "INSERT INTO godaddy_order_splits (transaction_id, item_id, "
                        "split_type, amount) VALUES (?, ?, 'transaction_fee', ?)",
                        (o["txn"], iid, fee_shares[k]))
                mids = items[iid]["merchant_ids"]
                if mids:
                    conn.execute("UPDATE godaddy_order_splits SET amount = ? "
                                 "WHERE id = ?", (-merch_shares[k], mids[0]))
                    for extra in mids[1:]:
                        conn.execute("DELETE FROM godaddy_order_splits WHERE id = ?",
                                     (extra,))
                elif merch_shares[k] > 0:
                    conn.execute(
                        "INSERT INTO godaddy_order_splits (transaction_id, item_id, "
                        "split_type, amount) VALUES (?, ?, 'merchant_fee', ?)",
                        (o["txn"], iid, -merch_shares[k]))
                cur = conn.execute(
                    "UPDATE acct_allocations SET godaddy_fee = ? "
                    "WHERE order_id = ? AND item_id = ?",
                    (merch_shares[k], o["order_id"], iid))
                out["allocations_restamped"] += cur.rowcount or 0
            out["orders"].append({
                "order_id": o["order_id"], "items": len(item_ids),
                "fee_in_before": before_fee, "fee_in_after": fee_total,
                "merchant_before": before_merch, "merchant_after": merch_total,
                "rows": rows})
        if not dry_run:
            conn.commit()
            out["integrity_after"] = fee_split_integrity(conn)
        else:
            out["integrity_now"] = fee_split_integrity(conn)
    out["fee_in_delta"] = round(out["fee_in_after"] - out["fee_in_before"], 2)
    return out


def rebook_spread_since(since: str, dry_run: bool = True,
                        db_path: str | Path | None = None,
                        cutover_override: str | None = None,
                        item_class: str | None = None) -> dict:
    """Recompute the allocations of every GoDaddy order dated on or after
    `since` so they carry the fee spread (Kerry 2026-09-09: the spread is
    margin and is taxed as margin). The whole allocation is recomputed
    through the ordinary allocator, so the report shows every bucket
    that moved, not just the spread — anything else that changed (a
    course cost edited since) is visible rather than absorbed.

    Dry-run by default. `since` should be the margin-model cutover
    (2026-09-05) or later; rows before it are frozen at the rate card and
    the allocator leaves their spread at zero regardless.

    `cutover_override` (DRY-RUN ONLY, ignored on apply) answers "what
    would these rows book under the residual model?" for rows dated
    before the real cutover — the measurement behind Kerry's Question 3
    (restate history or leave it frozen). It never writes.

    `item_class="membership"` restricts the rebook to MEMBERSHIP items:
    only orders holding one are visited and only those rows are reported
    or written, so the frozen event rows in the same order stay as they
    are (the membership restatement, Kerry 2026-09-09: memberships are
    the first gap group)."""
    from . import database as db
    since = (since or "").strip()[:10]
    _class_sql = ""
    if item_class == "membership":
        _class_sql = " AND UPPER(COALESCE(item_name,'')) LIKE '%MEMBERSHIP%'"
    elif item_class:
        raise ValueError(f"unknown item_class {item_class!r}")
    if cutover_override and not dry_run:
        raise ValueError("cutover_override is measure-only: use dry_run=True")
    out = {"dry_run": dry_run, "since": since, "item_class": item_class,
           "cutover_override": (cutover_override or None) if dry_run else None,
           "orders": 0, "rows": 0,
           "rows_changed": 0, "tgf_operating_before": 0.0,
           "tgf_operating_after": 0.0, "tax_reserve_before": 0.0,
           "tax_reserve_after": 0.0, "fee_spread_total": 0.0,
           "by_month": {}, "changes": []}
    with db._connect(db_path) as conn:
        order_ids = [r["order_id"] for r in conn.execute(
            """SELECT DISTINCT order_id FROM items
               WHERE merchant = 'The Golf Fellowship'
                 AND COALESCE(transaction_status, 'active') = 'active'
                 AND order_id IS NOT NULL AND order_id != ''
                 AND substr(COALESCE(order_date, ''), 1, 10) >= ?"""
            + _class_sql +
            """ ORDER BY order_date, order_id""", (since,)).fetchall()]
        only_ids: dict = {}
        if _class_sql and order_ids:
            for r in conn.execute(
                    """SELECT order_id, id FROM items
                       WHERE COALESCE(transaction_status, 'active') = 'active'
                         AND order_id IN (%s)""" % ",".join("?" * len(order_ids))
                    + _class_sql, tuple(order_ids)):
                only_ids.setdefault(r["order_id"], set()).add(r["id"])
        before = {}
        for r in conn.execute(
                """SELECT order_id, item_id, tgf_operating, tax_reserve,
                          fee_spread, godaddy_fee
                   FROM acct_allocations WHERE order_id IN (%s)"""
                % ",".join("?" * len(order_ids)) if order_ids else
                "SELECT order_id, item_id, tgf_operating, tax_reserve, "
                "fee_spread, godaddy_fee FROM acct_allocations WHERE 0",
                tuple(order_ids)).fetchall():
            before[(r["order_id"], r["item_id"])] = dict(r)
    if dry_run and cutover_override:
        db._MARGIN_CUTOVER_OVERRIDE.cutover = str(cutover_override)[:10]
    try:
        for oid in order_ids:
            rows = db.calculate_order_allocation(
                oid, db_path=db_path, dry_run=dry_run,
                only_item_ids=only_ids.get(oid) if _class_sql else None)
            out["orders"] += 1
            for a in rows:
                out["rows"] += 1
                b = before.get((oid, a["item_id"]), {})
                t0 = float(b.get("tgf_operating") or 0)
                x0 = float(b.get("tax_reserve") or 0)
                t1 = float(a.get("tgf_operating") or 0)
                x1 = float(a.get("tax_reserve") or 0)
                out["tgf_operating_before"] = round(out["tgf_operating_before"] + t0, 2)
                out["tgf_operating_after"] = round(out["tgf_operating_after"] + t1, 2)
                out["tax_reserve_before"] = round(out["tax_reserve_before"] + x0, 2)
                out["tax_reserve_after"] = round(out["tax_reserve_after"] + x1, 2)
                out["fee_spread_total"] = round(
                    out["fee_spread_total"] + float(a.get("fee_spread") or 0), 2)
                _m = str(a.get("allocation_date") or "")[:7] or "?"
                _bm = out["by_month"].setdefault(
                    _m, {"rows": 0, "rows_changed": 0, "new_rows": 0,
                         "tgf_operating_delta": 0.0, "tax_reserve_delta": 0.0})
                _bm["rows"] += 1
                _bm["tgf_operating_delta"] = round(_bm["tgf_operating_delta"] + (t1 - t0), 2)
                _bm["tax_reserve_delta"] = round(_bm["tax_reserve_delta"] + (x1 - x0), 2)
                if abs(t1 - t0) > 0.005 or abs(x1 - x0) > 0.005 or not b:
                    out["rows_changed"] += 1
                    _bm["rows_changed"] += 1
                    if not b:
                        _bm["new_rows"] += 1
                    out["changes"].append({
                        "order_id": oid, "item_id": a["item_id"],
                        "event_name": a.get("event_name"),
                        "allocation_date": str(a.get("allocation_date") or "")[:10],
                        "prize_pool": round(float(a.get("prize_pool") or 0), 2),
                        "lsc_shirt_fund": round(float(a.get("lsc_shirt_fund") or 0), 2),
                        "tgf_operating": [round(t0, 2), round(t1, 2)],
                        "fee_spread": round(float(a.get("fee_spread") or 0), 2),
                        "tax_reserve": [round(x0, 2), round(x1, 2)],
                        "new_row": not b,
                    })
    finally:
        if dry_run and cutover_override:
            db._MARGIN_CUTOVER_OVERRIDE.cutover = None
    out["tgf_operating_delta"] = round(
        out["tgf_operating_after"] - out["tgf_operating_before"], 2)
    out["tax_reserve_delta"] = round(
        out["tax_reserve_after"] - out["tax_reserve_before"], 2)
    return out
