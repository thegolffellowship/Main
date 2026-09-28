"""DEDUPE ON INGEST (CA #785 item 6, rule 3b, Kerry APPROVED): one money
event must not become two ledger rows because it arrived as two emails.

"#17 DEDUPE ON INGEST, APPROVED: a new expense row that matches an already
approved or promoted row on amount and merchant within ±3 days lands as
'ignored: duplicate of N', never pending and never promoted. A P2P receipt
matching an open credit-payout row by customer and amount links to it
(stamp_credit_refunded) instead of promoting."

Pins the four known shapes (CA Queue #17) as positives, the quote-vs-charge
and >3-day cases as negatives, the first-row-wins contract, shape 4 taking
the stamp path instead of a second ledger row, P2P twins staying separate,
and the 'approved but never promoted' guard (CFO 9/27) as a query, a
health finding and the read-only bridge.

Run: python3 test_expense_dedupe.py
"""

import contextlib
import io
import json
import logging
import os
import sqlite3
import sys
import tempfile

# The app binds DB_PATH at import (mcp_server reads it), so name the temp
# file BEFORE anything imports.
TMP = os.path.join(tempfile.mkdtemp(prefix="tgf-dedupe-"), "t.db")
os.environ["DATABASE_PATH"] = TMP
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PIN", "0000")

from email_parser import database as db  # noqa: E402

logging.getLogger("email_parser.database").setLevel(logging.ERROR)

FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label
          + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILURES.append(label)


P = TMP
_uid = [0]


def save(**kw):
    _uid[0] += 1
    data = {"email_uid": f"uid-{_uid[0]}", "review_status": "approved",
            "confidence": 97, "transaction_type": "expense"}
    data.update(kw)
    return db.save_expense_transaction(data, db_path=P)


def promote(exp_id):
    return db.update_expense_transaction(exp_id, {"review_status": "approved"},
                                         db_path=P)


def q(sql, args=()):
    c = sqlite3.connect(P)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, args).fetchall()]
    finally:
        c.close()


def run(sql, args=()):
    c = sqlite3.connect(P)
    try:
        c.execute(sql, args)
        c.commit()
    finally:
        c.close()


def backfill():
    with db._connect(P) as conn:
        return db._backfill_approved_expenses_to_ledger(conn)


def ledger_count(amount):
    return q("SELECT COUNT(*) AS n FROM acct_transactions "
             "WHERE abs(amount - ?) < 0.005 AND COALESCE(status,'active') = 'active'",
             (amount,))[0]["n"]


def is_dup_of(row, first_id):
    return (row["review_status"] == "ignored"
            and (row.get("notes") or "").startswith(f"ignored: duplicate of {first_id} ")
            and not row.get("acct_transaction_id"))


def main():
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        db.init_db(P)

    # ── the merchant rule ────────────────────────────────────────────────
    m = db.expense_merchants_match
    for a, b in [("Railway Corp", "RAILWAY"), ("VERCEL INC.", "Vercel"),
                 ("Zoom Video Communications", "ZOOM.US 888-799-9666"),
                 ("MAKE.COM", "Make"), ("HUBSPOT INC", "HubSpot"),
                 ("Brevo", "BREVO"), ("LA QUINTA INNS #0123", "La Quinta"),
                 ("Hyatt Regency San Antonio", "HYATT REGENCY SAN AN"),
                 ("AIRBNB * HMXYZ12", "Airbnb"),
                 ("SQ *SILVERHORN GOLF", "Silverhorn Golf Club")]:
        check(f"merchants match: {a!r} ~ {b!r}", m(a, b))
    for a, b in [("Railway", "Vercel"), ("Hyatt Regency", "Hilton Garden Inn"),
                 ("", "Railway"), ("Inc", "Corp")]:
        check(f"merchants differ: {a!r} vs {b!r}", not m(a, b))

    # ── SHAPE 1: vendor receipt + Chase card alert (Railway $20.00) ─────
    r1 = save(source_type="receipt", merchant="Railway Corp", amount=20.00,
              transaction_date="2026-09-20", category="Software")
    promote(r1["id"])
    r1 = q("SELECT * FROM expense_transactions WHERE id = ?", (r1["id"],))[0]
    check("shape 1: the receipt is approved and promoted", bool(r1["acct_transaction_id"]), r1)
    a1 = save(source_type="chase_alert", merchant="RAILWAY", amount=20.00,
              transaction_date="2026-09-21", account_last4="7680")
    check("shape 1: the card alert lands 'ignored: duplicate of <receipt>'",
          is_dup_of(a1, r1["id"]), a1)
    check("...never pending, never approved", a1["review_status"] == "ignored", a1["review_status"])
    backfill()
    a1 = q("SELECT * FROM expense_transactions WHERE id = ?", (a1["id"],))[0]
    check("...and the boot backfill never promotes it", a1["acct_transaction_id"] is None, a1)
    check("...one ledger row for the $20.00 Railway charge", ledger_count(20.00) == 1, ledger_count(20.00))

    # Hyatt $9,534.95: the first row approved but NOT yet promoted still wins
    h1 = save(source_type="receipt", merchant="Hyatt Regency San Antonio", amount=9534.95,
              transaction_date="2026-08-10")
    h2 = save(source_type="chase_alert", merchant="HYATT REGENCY SAN AN", amount=9534.95,
              transaction_date="2026-08-11", account_last4="7680")
    check("shape 1: an approved (not yet promoted) first row is the record", is_dup_of(h2, h1["id"]), h2)
    backfill()
    check("...one ledger row for Hyatt $9,534.95", ledger_count(9534.95) == 1, ledger_count(9534.95))

    # A PENDING second copy is still deduped ("never pending")
    z1 = save(source_type="chase_alert", merchant="ZOOM.US 888-799-9666", amount=15.99,
              transaction_date="2026-09-02")
    z2 = save(source_type="receipt", merchant="Zoom Video Communications", amount=15.99,
              transaction_date="2026-09-02", review_status="pending", confidence=80)
    check("shape 1: a would-be PENDING receipt lands ignored too", is_dup_of(z2, z1["id"]), z2)

    # ── NEGATIVE: quote vs final charge is NOT the same amount ──────────
    q1 = save(source_type="receipt", merchant="The Quarry Golf Club", amount=3168.00,
              transaction_date="2026-08-01", notes="Quote for SA Championship")
    q2 = save(source_type="chase_alert", merchant="THE QUARRY GOLF CLUB", amount=3429.36,
              transaction_date="2026-08-02", account_last4="7680")
    check("negative: $3,168 quote does not dedupe the $3,429.36 charge",
          q2["review_status"] == "approved" and "duplicate" not in (q2.get("notes") or ""), q2)

    # ── SHAPE 2: Chase pending then posted alert, same merchant+amount ──
    q3 = save(source_type="chase_alert", merchant="QUARRY GOLF CLUB", amount=3429.36,
              transaction_date="2026-08-04", account_last4="7680")
    check("shape 2: the posted Quarry alert is a duplicate of the pending one",
          is_dup_of(q3, q2["id"]), q3)
    ab1 = save(source_type="chase_alert", merchant="AIRBNB * HMXYZ12", amount=2761.30,
               transaction_date="2026-07-01", account_last4="4321")
    ab2 = save(source_type="chase_alert", merchant="Airbnb", amount=2761.30,
               transaction_date="2026-07-03", account_last4="4321")
    check("shape 2: Airbnb pending→posted 2 days apart", is_dup_of(ab2, ab1["id"]), ab2)
    s1 = save(source_type="chase_alert", merchant="SQ *SILVERHORN GOLF", amount=476.30,
              transaction_date="2026-09-08", account_last4="7680")
    s2 = save(source_type="chase_alert", merchant="Silverhorn Golf Club", amount=476.30,
              transaction_date="2026-09-11", account_last4="7680")
    check("shape 2: Silverhorn exactly 3 days apart still dedupes", is_dup_of(s2, s1["id"]), s2)
    backfill()
    check("...one ledger row for Airbnb $2,761.30", ledger_count(2761.30) == 1, ledger_count(2761.30))
    check("...one ledger row for Quarry $3,429.36", ledger_count(3429.36) == 1, ledger_count(3429.36))

    # ── NEGATIVE: same merchant + amount more than 3 days apart ─────────
    b1 = save(source_type="chase_alert", merchant="BREVO", amount=25.00,
              transaction_date="2026-09-01", account_last4="7680")
    b2 = save(source_type="chase_alert", merchant="Brevo", amount=25.00,
              transaction_date="2026-09-05", account_last4="7680")
    check("negative: same merchant/amount 4 days apart is a second charge",
          b2["review_status"] == "approved" and b2["id"] != b1["id"], b2)

    # ── SHAPE 3: a card payment alerted from BOTH sides ─────────────────
    t1 = save(source_type="chase_alert", merchant="Payment to Chase card ending in 4321",
              amount=14301.75, transaction_date="2026-07-12", account_last4="7680",
              transaction_type="transfer")
    promote(t1["id"])
    t2 = save(source_type="chase_alert", merchant="Payment Thank You", amount=14301.75,
              transaction_date="2026-07-13", account_last4="4321",
              transaction_type="transfer")
    check("shape 3: the card-side alert of the $14,301.75 payment is a duplicate",
          is_dup_of(t2, t1["id"]), t2)
    sp1 = save(source_type="chase_alert", merchant="CHASE SAPPHIRE AUTOPAY", amount=2241.01,
               transaction_date="2026-09-24", account_last4="7680", transaction_type="transfer")
    sp2 = save(source_type="chase_alert", merchant="Sapphire payment received", amount=2241.01,
               transaction_date="2026-09-24", account_last4="9911", transaction_type="transfer")
    check("shape 3: 9/24 Sapphire $2,241.01 from two Chase alerts", is_dup_of(sp2, sp1["id"]), sp2)
    backfill()
    check("...one ledger row per card payment", ledger_count(14301.75) == 1 and ledger_count(2241.01) == 1,
          (ledger_count(14301.75), ledger_count(2241.01)))
    p1 = save(source_type="chase_alert", merchant="Payment to Chase card ending in 4321",
              amount=400.00, transaction_date="2026-07-22", account_last4="7680",
              transaction_type="transfer")
    p2 = save(source_type="chase_alert", merchant="Payment to Chase card ending in 4321",
              amount=400.00, transaction_date="2026-08-21", account_last4="7680",
              transaction_type="transfer")
    check("negative: the 7/22 and 8/21 $400 payments are two payments", p2["review_status"] == "approved", p2)
    p3 = save(source_type="chase_alert", merchant="Online transfer to savings", amount=400.00,
              transaction_date="2026-08-22", account_last4="7680", transaction_type="transfer")
    check("negative: same account, different payee, is a separate transfer",
          p3["review_status"] == "approved", p3)
    x1 = save(source_type="chase_alert", merchant="Payment Thank You", amount=88.00,
              transaction_date="2026-09-10", account_last4="4321", transaction_type="transfer")
    x2 = save(source_type="chase_alert", merchant="Payment Thank You", amount=88.00,
              transaction_date="2026-09-11", account_last4="4321", transaction_type="expense")
    check("negative: a transfer never dedupes an expense of the same amount",
          x2["review_status"] == "approved", x2)

    # ── re-save of the SAME email never marks itself ────────────────────
    again = db.save_expense_transaction({
        "email_uid": r1["email_uid"], "source_type": "receipt", "merchant": "Railway Corp",
        "amount": 20.00, "transaction_date": "2026-09-20", "review_status": "approved",
        "confidence": 97}, db_path=P)
    check("re-saving the first row's own email keeps it the record",
          again["id"] == r1["id"] and again["review_status"] == "approved", again)

    # ── statement lines are never ingest-deduped (twins are real) ───────
    st = db.save_expense_transaction({
        "email_uid": "stmt-7680-2026-09-21-2000", "source_type": "statement",
        "merchant": "RAILWAY", "amount": 20.00, "transaction_date": "2026-09-21",
        "review_status": "approved"}, db_path=P)
    check("statement lines bypass the ingest dedupe", st["review_status"] == "approved", st)

    # ── no email uid: the content path dedupes too ──────────────────────
    nu = db.save_expense_transaction({
        "source_type": "chase_alert", "merchant": "VERCEL INC.", "amount": 20.00,
        "transaction_date": "2026-09-22", "review_status": "approved"}, db_path=P)
    check("no-uid path: Vercel $20 alert vs the Railway $20 receipt is NOT a duplicate",
          nu["review_status"] == "approved", nu)
    nu2 = db.save_expense_transaction({
        "source_type": "receipt", "merchant": "Vercel", "amount": 20.00,
        "transaction_date": "2026-09-22", "review_status": "approved"}, db_path=P)
    check("no-uid path: the Vercel receipt IS a duplicate of the Vercel alert",
          is_dup_of(nu2, nu["id"]), nu2)

    # ── P2P twins stay separate (the Bob Atkinson rule) ─────────────────
    v1 = save(source_type="venmo", merchant="Bob Atkinson", amount=25.00,
              transaction_date="2026-07-21", transaction_type="payout",
              raw_extract=json.dumps({"transaction_id": "111"}))
    v2 = save(source_type="venmo", merchant="Bob Atkinson", amount=25.00,
              transaction_date="2026-07-21", transaction_type="payout",
              raw_extract=json.dumps({"transaction_id": "222"}))
    check("P2P twins with different transaction ids are two payments",
          v1["id"] != v2["id"] and v2["review_status"] == "approved", (v1["id"], v2))

    # ── SHAPE 4: P2P credit refund vs the credit-payout row ─────────────
    run("INSERT INTO customers (customer_id, first_name, last_name) VALUES (31, 'Bear', 'Clarkson')")
    run("INSERT INTO customers (customer_id, first_name, last_name) VALUES (24, 'Daniel', 'South')")
    run("INSERT INTO customers (customer_id, first_name, last_name) VALUES (40, 'Matt', 'Griffin')")
    for iid, cust, cid, price in [(8001, "Bear Clarkson", 31, "$59.00"),
                                  (8002, "Daniel South", 24, "$26.00"),
                                  (8003, "Matt Griffin", 40, "$30.00"),
                                  (8004, "Daniel South", 24, "$44.00")]:
        run("INSERT INTO items (id, email_uid, merchant, order_date, item_name, customer,"
            " customer_id, item_price, transaction_status) VALUES"
            " (?, ?, 'GoDaddy', '2026-09-01', 's9.20 Rained', ?, ?, ?, 'credited')",
            (iid, f"item-{iid}", cust, cid, price))
    today = db.today_central_str()

    # 4a: the in-app Refund already booked a credit-payout ledger row
    pc = db.payout_credit(8001, method="Venmo", db_path=P)
    check("setup: payout_credit booked the credit-payout row", pc.get("ok"), pc)
    cp = q("SELECT id FROM acct_transactions WHERE source_ref = 'credit-payout-8001'")[0]["id"]
    bc = save(source_type="venmo", merchant="Bear Clarkson", amount=59.00,
              transaction_date=today, transaction_type="payout", customer_id=31,
              notes="Bear Clarkson - Credit refund s9.20")
    check("shape 4a: the receipt LINKS to the credit-payout ledger row",
          bc["acct_transaction_id"] == cp and bc["matched_item_id"] == 8001, bc)
    backfill()
    check("...and is never promoted beside it (one $59 ledger row)", ledger_count(59.00) == 1,
          ledger_count(59.00))
    check("...no exp-promoted row for the receipt",
          not q("SELECT 1 FROM acct_transactions WHERE source_ref = ?",
                (f"exp-promoted-{bc['id']}",)))

    # 4b: the credit is still OPEN — the stamp path, not a second ledger row
    ds = save(source_type="venmo", merchant="Daniel South", amount=26.00,
              transaction_date=today, transaction_type="payout", customer_id=24,
              notes="Daniel South - Credit for s9.20 Rained")
    it = q("SELECT transaction_status, credit_note FROM items WHERE id = 8002")[0]
    check("shape 4b: stamp_credit_refunded closed the open credit",
          it["transaction_status"] == "refunded"
          and (it["credit_note"] or "").startswith("Refunded $26.00"), it)
    check("...the receipt is claimed for that item", ds["matched_item_id"] == 8002, ds)
    check("...and NO credit-payout ledger row was written",
          not q("SELECT 1 FROM acct_transactions WHERE source_ref = 'credit-payout-8002'"))
    rw = db.auto_match_refund_watches([ds["id"]], db_path=P)
    backfill()
    check("...the refund matcher adds nothing after it (one $26 ledger row, the receipt)",
          ledger_count(26.00) == 1
          and q("SELECT 1 FROM acct_transactions WHERE source_ref = ?", (f"exp-promoted-{ds['id']}",)),
          (ledger_count(26.00), rw))

    # The CLASS: the auto refund path itself stamps instead of payout_credit
    run("INSERT INTO expense_transactions (id, source_type, transaction_type, merchant,"
        " amount, transaction_date, review_status, notes, customer_id, created_at)"
        " VALUES (9901, 'venmo', 'payout', 'Daniel South', 44.00, ?, 'approved',"
        " 'Daniel South - refund of credit', 24, '2099-01-01 00:00:00')", (today,))
    res = db.auto_match_refund_watches([9901], db_path=P)
    it = q("SELECT transaction_status FROM items WHERE id = 8004")[0]
    check("auto_match_refund_watches (watchless) stamps the credit refunded",
          res.get("watchless_recorded") == 1 and it["transaction_status"] == "refunded", (res, it))
    check("...without a credit-payout ledger row",
          not q("SELECT 1 FROM acct_transactions WHERE source_ref = 'credit-payout-8004'"))
    backfill()
    check("...so the promoted receipt is the one $44 ledger row", ledger_count(44.00) == 1,
          ledger_count(44.00))

    # Negative: a winnings receipt is never claimed for a credit
    mg = save(source_type="venmo", merchant="Matt Griffin", amount=30.00,
              transaction_date=today, transaction_type="payout", customer_id=40,
              notes="Matt Griffin - Winnings for s9.17 Silverhorn")
    it = q("SELECT transaction_status FROM items WHERE id = 8003")[0]
    check("negative: a winnings receipt leaves the open credit alone",
          it["transaction_status"] == "credited" and not mg.get("matched_item_id"), (it, mg))

    # ── THE GUARD: approved but never promoted (CFO 9/27) ───────────────
    hs = save(source_type="receipt", merchant="HubSpot", amount=42.64,
              transaction_date="2026-09-26")
    run("UPDATE expense_transactions SET created_at = datetime('now', '-2 days') WHERE id = ?",
        (hs["id"],))
    run("UPDATE expense_transactions SET created_at = datetime('now', '-2 days') WHERE id = ?",
        (r1["id"],))
    fresh = save(source_type="receipt", merchant="Canva", amount=12.99,
                 transaction_date="2026-09-28")
    g = db.get_expense_unpromoted(24, db_path=P)
    ids = {r["id"] for r in g["rows"]}
    check("guard lists the approved-but-unpromoted HubSpot $42.64", hs["id"] in ids, g)
    check("...not a promoted row", r1["id"] not in ids, ids)
    check("...not an ignored duplicate", a1["id"] not in ids, ids)
    check("...not a row younger than the window", fresh["id"] not in ids, ids)
    check("...the window is a parameter (0h lists the fresh one too)",
          fresh["id"] in {r["id"] for r in db.get_expense_unpromoted(0, db_path=P)["rows"]})
    check("guard default window is 24 hours", g["hours"] == 24.0, g["hours"])

    from email_parser import health, perf
    perf._DB_PATH_OVERRIDE = P
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rep = health.build_health_report(1, db_path=P)
    f = [x for x in rep["findings"] if x["key"] == "expense_unpromoted"]
    check("the daily health digest carries it as a finding",
          len(f) == 1 and f[0]["severity"] == "medium" and f"#{hs['id']} HubSpot" in f[0]["text"], f)

    # Importing mcp_server boots the app (init_db), whose backfill promotes
    # every approved row — the guard's rows are gone afterwards, which is
    # the guard working. A new unpromoted row is aged after the import.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        import mcp_server as mcp
    check("the boot backfill promoted HubSpot, so the guard drops it",
          hs["id"] not in {r["id"] for r in db.get_expense_unpromoted(24, db_path=P)["rows"]})
    mk = save(source_type="receipt", merchant="Make", amount=10.59,
              transaction_date="2026-09-26")
    run("UPDATE expense_transactions SET created_at = datetime('now', '-2 days') WHERE id = ?",
        (mk["id"],))
    out = json.loads(mcp._scoring_dispatch("https://tgf-sa.golfgenius.com/",
                                           "scoring-expense-unpromoted"))
    check("bridge scoring-expense-unpromoted (default 24h) lists the unpromoted row",
          mk["id"] in {r["id"] for r in out.get("rows", [])} and out.get("hours") == 24.0, out)
    out = json.loads(mcp._scoring_dispatch("https://tgf-sa.golfgenius.com/",
                                           "scoring-expense-unpromoted:72"))
    check("...scoring-expense-unpromoted:72 narrows the window",
          mk["id"] not in {r["id"] for r in out.get("rows", [])} and out.get("hours") == 72.0, out)
    out = json.loads(mcp._scoring_dispatch("https://tgf-sa.golfgenius.com/",
                                           "scoring-expense-unpromoted:abc"))
    check("...and refuses a bad window with a usage line", "usage" in (out.get("error") or ""), out)
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py"),
               encoding="utf-8").read()
    check("the bridge list names it", "      scoring-expense-unpromoted[:<hours>]" in src)

    print(f"\n{len(FAILURES)} failure(s)")
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
