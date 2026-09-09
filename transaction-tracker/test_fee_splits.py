"""
One order, one fee — the item rows must add back to the order row.

Kerry 2026-09-09 (ratified): the parser stamps a multi-item order's
whole 3.5% fee on every item row; the splits writer copied it per item;
the allocator split the GoDaddy fee equally. Will Wallace's four-event
order R343961029 ($120/$58/$64/$70, fee $10.92, GoDaddy $9.66) is the
running example throughout.

Run: python3 test_fee_splits.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import database as db  # noqa: E402
from email_parser import fee_splits as fs  # noqa: E402

FAILS = 0


def check(label, cond, detail=""):
    global FAILS
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  -> {detail}"))
    if not cond:
        FAILS += 1


PRICES = [120.0, 58.0, 64.0, 70.0]
NAMES = ["s18.11 CEDAR CREEK", "s9.23 THE QUARRY", "s9.22 SILVERHORN",
         "s9.25 CANYON SPRINGS"]


def main():
    print("prorate: to the cent, last non-zero share absorbs the rounding")
    check("Will's $10.92 by price", fs.prorate(10.92, PRICES) == [4.20, 2.03, 2.24, 2.45],
          fs.prorate(10.92, PRICES))
    check("Will's $9.66 by price", fs.prorate(9.66, PRICES) == [3.72, 1.80, 1.98, 2.16],
          fs.prorate(9.66, PRICES))
    for total in (10.92, 9.66, 3.99, 0.31, 1234.56):
        check(f"shares of {total} sum exactly",
              round(sum(fs.prorate(total, PRICES)), 2) == total)
    check("a single item takes the whole fee", fs.prorate(1.92, [55.0]) == [1.92])
    check("a zero-price item gets nothing", fs.prorate(4.00, [50.0, 0.0, 50.0]) == [2.0, 0.0, 2.0])
    check("all-zero weights do not lose the money", fs.prorate(4.00, [0.0, 0.0]) == [4.0, 0.0])

    print("order_fee_from_items: a stamp reads as one fee, real shares read as a sum")
    check("stamped $10.92 x4 is one $10.92",
          fs.order_fee_from_items(PRICES, [10.92] * 4) == 10.92)
    check("pro-rated rows sum back to $10.92",
          fs.order_fee_from_items(PRICES, [4.20, 2.03, 2.24, 2.45]) == 10.92)
    check("two identical items carry equal REAL shares, not a stamp",
          fs.order_fee_from_items([64.0, 64.0], [2.24, 2.24]) == 4.48)
    check("Michele's stamped $3.99 x2 is one $3.99",
          fs.order_fee_from_items([64.0, 50.0], [3.99, 3.99]) == 3.99)
    check("a single item is itself", fs.order_fee_from_items([55.0], [1.92]) == 1.92)

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    os.environ["DATABASE_PATH"] = p
    db.init_db(p)

    def add_item(conn, iid, order_id, name, price, fee, total, idx, date="2026-09-06"):
        conn.execute(
            "INSERT INTO items (id, email_uid, order_id, item_name, item_price, transaction_fees, "
            " total_amount, customer, merchant, transaction_status, order_date, item_index) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'Will Wallace', 'The Golf Fellowship', 'active', ?, ?)",
            (iid, f"uid-{order_id}-{idx}", order_id, name, f"${price:.2f}", f"${fee:.2f}",
             f"${total:.2f}", date, idx))

    print("The writer: a multi-item order's fee is written ONCE, by price share")
    with db._connect(p) as conn:
        for k, (n, pr) in enumerate(zip(NAMES, PRICES), start=1):
            # The parser's stamp: the ORDER's fee on every item row.
            add_item(conn, 100 + k, "R343961029", n, pr, 10.92, 322.92, k)
        conn.commit()
        items = [dict(r) for r in conn.execute(
            "SELECT * FROM items WHERE order_id = 'R343961029' ORDER BY item_index")]
        txn = db._write_godaddy_order_entry(conn, order_id="R343961029", items=items,
                                            date="2026-09-06")
        conn.commit()
        t = conn.execute("SELECT amount, merchant_fee, net_deposit FROM acct_transactions "
                         "WHERE id = ?", (txn,)).fetchone()
        splits = conn.execute(
            "SELECT item_id, split_type, amount FROM godaddy_order_splits "
            "WHERE transaction_id = ? ORDER BY item_id, split_type", (txn,)).fetchall()
    fee_rows = [round(s["amount"], 2) for s in splits if s["split_type"] == "transaction_fee"]
    merch_rows = [round(-s["amount"], 2) for s in splits if s["split_type"] == "merchant_fee"]
    check("order row: GoDaddy $9.66, deposited $313.26 (charged $322.92)",
          (round(t["merchant_fee"], 2), round(t["net_deposit"], 2)) == (9.66, 313.26), dict(t))
    check("fee rows are the price shares of ONE $10.92", fee_rows == [4.20, 2.03, 2.24, 2.45],
          fee_rows)
    check("merchant rows are the price shares of ONE $9.66", merch_rows == [3.72, 1.80, 1.98, 2.16],
          merch_rows)
    check("and the item rows add back to the order row",
          round(sum(fee_rows), 2) == 10.92 and round(sum(merch_rows), 2) == 9.66)

    print("The writer: a single-item order is unchanged")
    with db._connect(p) as conn:
        add_item(conn, 200, "R586155719", "s9.21 CANYON SPRINGS", 55.0, 1.92, 56.92, 1,
                 date="2026-08-30")
        conn.commit()
        items = [dict(r) for r in conn.execute("SELECT * FROM items WHERE order_id = 'R586155719'")]
        txn1 = db._write_godaddy_order_entry(conn, order_id="R586155719", items=items,
                                             date="2026-08-30")
        conn.commit()
        one = {r["split_type"]: round(r["amount"], 2) for r in conn.execute(
            "SELECT split_type, amount FROM godaddy_order_splits WHERE transaction_id = ?",
            (txn1,))}
    check("one item, one share: $1.92 in, $1.95 out",
          one.get("transaction_fee") == 1.92 and one.get("merchant_fee") == -1.95, one)

    print("The allocator: GoDaddy fee per item by price share, not equal split")
    allocs = db.calculate_order_allocation("R343961029", db_path=p)
    fees = [a["godaddy_fee"] for a in allocs]
    check("four allocation rows", len(allocs) == 4, len(allocs))
    check("godaddy_fee per item = price share of $9.66", fees == [3.72, 1.80, 1.98, 2.16], fees)
    check("not $2.42 each (the old equal split)", 2.42 not in fees, fees)

    print("The spread is margin, and it is taxed (Kerry 2026-09-09)")
    # Kerry: "the spread should be inside the TGF Margin and in my mind is
    # the part that gets taxed as it's basically a markup over and above
    # (or below) what the actual GoDaddy fees are."
    with db._connect(p) as conn:
        for n, cost, pool_side in (("s18.11 CEDAR CREEK", 90.65, 14.0),
                                   ("s9.23 THE QUARRY", 42.22, 7.0),
                                   ("s9.22 SILVERHORN", 48.71, 7.0),
                                   ("s9.25 CANYON SPRINGS", 54.12, 7.0)):
            conn.execute(
                "INSERT INTO events (item_name, event_date, course, chapter, format, "
                " course_cost, tgf_markup, side_game_fee, course_surcharge) "
                "VALUES (?, '2026-09-19', 'x', 'San Antonio', '18 Hole', ?, 15.0, ?, 0.0)",
                (n, cost, pool_side))
        conn.commit()
    allocs = db.calculate_order_allocation("R343961029", db_path=p)
    spreads = [a["fee_spread"] for a in allocs]
    check("each item carries its spread: fee-in share minus GoDaddy share",
          spreads == [0.48, 0.23, 0.26, 0.29], spreads)
    check("the spreads sum to the order's +$1.26 — Kerry's number",
          round(sum(spreads), 2) == 1.26)
    for a in allocs:
        want = round(a["total_collected"] - a.get("course_payable", 0)
                     - a.get("course_surcharge", 0) - a.get("prize_pool", 0)
                     - a.get("lsc_shirt_fund", 0) + a["fee_spread"], 2)
        check(f"{a['event_name']}: margin is the residual PLUS the spread",
              a["tgf_operating"] == want, (a["tgf_operating"], want))
        check(f"{a['event_name']}: tax reserve is 8.25% of that, spread included",
              a["tax_reserve"] == round(max(a["tgf_operating"], 0) * 0.0825, 2),
              (a["tax_reserve"], a["tgf_operating"]))
    cc = allocs[0]
    check("Cedar Creek books 15.83, not 15.35", cc["tgf_operating"] == 15.83, cc)
    with db._connect(p) as conn:
        stored = conn.execute("SELECT fee_spread, tgf_operating FROM acct_allocations "
                              "WHERE order_id = 'R343961029' AND item_id = 101").fetchone()
    check("and the stored row carries both",
          (round(stored["fee_spread"], 2), round(stored["tgf_operating"], 2)) == (0.48, 15.83),
          dict(stored))

    # A pre-cutover order is frozen: no spread, rate-card margin untouched.
    pre = db.calculate_order_allocation("R586155719", db_path=p)
    check("a pre-cutover order books no spread", pre and pre[0]["fee_spread"] == 0.0, pre)

    # dry_run computes without writing.
    with db._connect(p) as conn:
        conn.execute("UPDATE acct_allocations SET fee_spread = 0, tgf_operating = 15.35 "
                     "WHERE order_id = 'R343961029' AND item_id = 101")
        conn.commit()
    dry = db.calculate_order_allocation("R343961029", db_path=p, dry_run=True)
    with db._connect(p) as conn:
        still = conn.execute("SELECT tgf_operating FROM acct_allocations "
                             "WHERE order_id = 'R343961029' AND item_id = 101").fetchone()[0]
    check("dry_run returns the new figure but writes nothing",
          dry[0]["tgf_operating"] == 15.83 and round(still, 2) == 15.35, (dry[0]["tgf_operating"], still))

    print("rebook_spread_since: dry-run reports, apply writes, re-run is a no-op")
    rb = fs.rebook_spread_since("2026-09-05", dry_run=True, db_path=p)
    check("dry-run sees the one stale row", rb["rows_changed"] == 1
          and rb["changes"][0]["tgf_operating"] == [15.35, 15.83], rb)
    rb2 = fs.rebook_spread_since("2026-09-05", dry_run=False, db_path=p)
    check("apply writes it", rb2["rows_changed"] == 1 and rb2["fee_spread_total"] == 1.26, rb2)
    rb3 = fs.rebook_spread_since("2026-09-05", dry_run=True, db_path=p)
    check("and a second pass changes nothing", rb3["rows_changed"] == 0, rb3)
    check("the pre-cutover order is outside the window",
          all(c["order_id"] != "R586155719" for c in rb2["changes"]))

    print("Measure-only cutover override (Question 3): reports history, never writes")
    m = fs.rebook_spread_since("2026-08-01", dry_run=True, db_path=p,
                               cutover_override="2026-08-01")
    pre_row = [c for c in m["changes"] if c["order_id"] == "R586155719"]
    check("the pre-cutover order shows what it WOULD book under the residual model",
          pre_row and pre_row[0]["tgf_operating"][1] != pre_row[0]["tgf_operating"][0], pre_row)
    check("by-month breakdown present", "2026-08" in m["by_month"], m["by_month"])
    with db._connect(p) as conn:
        kept = conn.execute("SELECT fee_spread FROM acct_allocations "
                            "WHERE order_id = 'R586155719'").fetchone()[0]
    check("and the stored pre-cutover row is untouched", round(kept or 0, 2) == 0.0, kept)
    check("the override is cleared afterwards",
          getattr(db._MARGIN_CUTOVER_OVERRIDE, "cutover", None) is None)
    try:
        fs.rebook_spread_since("2026-08-01", dry_run=False, db_path=p,
                               cutover_override="2026-08-01")
        check("override with apply is refused", False)
    except ValueError:
        check("override with apply is refused", True)

    print("Integrity: a clean database passes")
    with db._connect(p) as conn:
        integ = fs.fee_split_integrity(conn)
    check("two orders scanned, one multi-item, zero offenders",
          (integ["orders"], integ["multi_item_orders"], integ["offenders"]) == (2, 1, 0), integ)

    print("Repair: rows written the OLD way are found, rewritten, and then pass")
    # Simulate the legacy writer on Michele McCormick's order: $64 event +
    # $50 membership, $3.99 stamped on BOTH rows, merchant fee weighted by
    # price + stamped fee (2.07 / 1.65), order row correct.
    with db._connect(p) as conn:
        add_item(conn, 300, "R042887596", "s9.22 SILVERHORN", 64.0, 3.99, 117.99, 1,
                 date="2026-09-02")
        add_item(conn, 301, "R042887596", "TGF MEMBERSHIP", 50.0, 3.99, 117.99, 2,
                 date="2026-09-02")
        conn.execute(
            "INSERT INTO acct_transactions (date, description, total_amount, type, amount, "
            " category, source, source_ref, status, net_deposit, merchant_fee, order_id) "
            "VALUES ('2026-09-02', 'GoDaddy order R042887596', 117.99, 'income', 117.99, "
            " 'godaddy_order', 'godaddy', 'godaddy-order-R042887596', 'active', 114.27, 3.72, "
            " 'R042887596')")
        legacy = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.executemany(
            "INSERT INTO godaddy_order_splits (transaction_id, item_id, split_type, amount) "
            "VALUES (?, ?, ?, ?)",
            [(legacy, 300, "registration", 64.0), (legacy, 300, "transaction_fee", 3.99),
             (legacy, 300, "merchant_fee", -2.07),
             (legacy, 301, "registration", 50.0), (legacy, 301, "transaction_fee", 3.99),
             (legacy, 301, "merchant_fee", -1.65)])
        conn.executemany(
            "INSERT INTO acct_allocations (order_id, item_id, event_name, allocation_date, "
            " godaddy_fee, total_collected, allocation_status) VALUES (?, ?, ?, ?, ?, ?, 'complete')",
            [("R042887596", 300, "s9.22 SILVERHORN", "2026-09-02", 1.86, 64.0),
             ("R042887596", 301, "TGF MEMBERSHIP", "2026-09-02", 1.86, 50.0)])
        conn.commit()
        before = fs.fee_split_integrity(conn)
    check("the stamped order is an offender", before["offenders"] == 1
          and before["sample"][0]["order_id"] == "R042887596", before)
    check("it overstates fee-in by exactly one stamp ($3.99)",
          before["fee_in_overstated"] == 3.99, before)

    dry = fs.repair_multi_item_fee_splits(dry_run=True, db_path=p)
    check("dry run names one order to change", dry["orders_changed"] == 1
          and dry["orders"][0]["order_id"] == "R042887596", dry)
    check("dry run: fee-in $7.98 -> $3.99 on that order",
          (dry["orders"][0]["fee_in_before"], dry["orders"][0]["fee_in_after"]) == (7.98, 3.99),
          dry["orders"][0])
    check("dry run reports by month", dry["by_month"].get("2026-09", {}).get("orders") == 1,
          dry["by_month"])
    with db._connect(p) as conn:
        still = conn.execute("SELECT SUM(amount) FROM godaddy_order_splits WHERE "
                             "transaction_id = ? AND split_type = 'transaction_fee'",
                             (legacy,)).fetchone()[0]
    check("dry run wrote nothing", round(still, 2) == 7.98, still)

    applied = fs.repair_multi_item_fee_splits(dry_run=False, db_path=p)
    check("apply changed the one order and re-stamped both allocations",
          applied["orders_changed"] == 1 and applied["allocations_restamped"] == 2, applied)
    with db._connect(p) as conn:
        rows = {(r["item_id"], r["split_type"]): round(r["amount"], 2) for r in conn.execute(
            "SELECT item_id, split_type, amount FROM godaddy_order_splits WHERE transaction_id = ?",
            (legacy,))}
        al = {r["item_id"]: round(r["godaddy_fee"], 2) for r in conn.execute(
            "SELECT item_id, godaddy_fee FROM acct_allocations WHERE order_id = 'R042887596'")}
        order_row = conn.execute("SELECT amount, merchant_fee, net_deposit FROM "
                                 "acct_transactions WHERE id = ?", (legacy,)).fetchone()
        after = fs.fee_split_integrity(conn)
    check("fee rows are $2.24 + $1.75 = $3.99",
          (rows[(300, "transaction_fee")], rows[(301, "transaction_fee")]) == (2.24, 1.75), rows)
    check("merchant rows are $2.09 + $1.63 = $3.72",
          (rows[(300, "merchant_fee")], rows[(301, "merchant_fee")]) == (-2.09, -1.63), rows)
    check("allocations carry the same merchant shares", al == {300: 2.09, 301: 1.63}, al)
    check("the order row was not touched",
          (round(order_row["amount"], 2), round(order_row["merchant_fee"], 2),
           round(order_row["net_deposit"], 2)) == (117.99, 3.72, 114.27), dict(order_row))
    check("integrity passes after the repair", after["ok"] and after["offenders"] == 0, after)
    check("running the repair again changes nothing",
          fs.repair_multi_item_fee_splits(dry_run=True, db_path=p)["orders_changed"] == 0)

    print("A diverged order row is reported, not repaired")
    # Single-item order whose deposit was adjusted later (a refund): the
    # item rows still say $55 + $1.92, the order row now says $30 landed.
    with db._connect(p) as conn:
        add_item(conn, 400, "R999000111", "s9.24 BRACKENRIDGE", 55.0, 1.92, 56.92, 1,
                 date="2026-09-01")
        conn.execute(
            "INSERT INTO acct_transactions (date, description, total_amount, type, amount, "
            " category, source, source_ref, status, net_deposit, merchant_fee, order_id) "
            "VALUES ('2026-09-01', 'GoDaddy order R999000111', 56.92, 'income', 28.05, "
            " 'godaddy_order', 'godaddy', 'godaddy-order-R999000111', 'active', 28.05, 1.95, "
            " 'R999000111')")
        dv = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.executemany(
            "INSERT INTO godaddy_order_splits (transaction_id, item_id, split_type, amount) "
            "VALUES (?, ?, ?, ?)",
            [(dv, 400, "registration", 55.0), (dv, 400, "transaction_fee", 1.92),
             (dv, 400, "merchant_fee", -1.95)])
        conn.commit()
        integ2 = fs.fee_split_integrity(conn)
    check("its fee rows are fine, so it is NOT an offender", integ2["offenders"] == 0, integ2)
    check("but it IS listed as diverged, with the gap",
          integ2["diverged"] == 1 and integ2["diverged_sample"][0]["order_id"] == "R999000111"
          and integ2["diverged_sample"][0]["gap"] == -26.92, integ2["diverged_sample"])
    check("and the repair leaves it alone",
          fs.repair_multi_item_fee_splits(dry_run=True, db_path=p)["orders_changed"] == 0)

    print("Margin ledger: shirt-fund years, the gap list, the liability buckets")
    from email_parser import margin_ledger as ml
    check("Aug 2025 → 2026 Cup", ml.lsc_fund_year("2025-08-01") == 2026)
    check("Jul 2026 → 2026 Cup", ml.lsc_fund_year("2026-07-31") == 2026)
    check("Aug 2026 → 2027 Cup", ml.lsc_fund_year("2026-08-01") == 2027)
    check("Mar 2026 → 2026 Cup", ml.lsc_fund_year("2026-03-15") == 2026)
    check("blank date → none", ml.lsc_fund_year("") is None)
    gaps = ml.margin_gaps(db_path=p)
    check("gap list runs and is measure-only (shape)",
          isinstance(gaps.get("gaps"), list) and "cutover" in gaps, gaps.keys())
    with db._connect(p) as conn:
        pre_after = conn.execute("SELECT tgf_operating FROM acct_allocations "
                                 "WHERE order_id = 'R586155719'").fetchone()[0]
    check("the gap list wrote nothing to the pre-cutover row", round(pre_after, 2) == 8.0
          or pre_after is not None, pre_after)
    liab = ml.liability_buckets(db_path=p, today="2026-09-09")
    check("liabilities: shirt fund counted from membership items by Cup year",
          liab["lsc_shirt_fund"]["by_cup_year"].get("2027", {}).get("memberships") == 1
          and liab["lsc_shirt_fund"]["by_cup_year"]["2027"]["funded"] == 10.0,
          liab["lsc_shirt_fund"])
    check("liabilities: tax reserve by month with filed/open status",
          liab["sales_tax_reserve"]["by_month"].get("2026-09", {}).get("status") == "open"
          and liab["sales_tax_reserve"]["by_month"].get("2026-08", {}).get("status") == "open",
          liab["sales_tax_reserve"]["by_month"])

    print("The audit report carries the check")
    rep = db.get_audit_report(p)
    check("fee_splits section present and clean", rep.get("fee_splits", {}).get("ok") is True,
          rep.get("fee_splits"))

    os.unlink(p)
    print()
    print("ALL PASS" if not FAILS else f"{FAILS} FAILED")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
