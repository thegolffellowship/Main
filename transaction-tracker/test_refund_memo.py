"""REFUND MEMOS (Kerry 2026-10-28, Event Ops #2475-2 corrected by #2476-4):
"Memo would say Refund for San Antonio Fall Points Race in that particular
situation. It's the [What] for [Event or Season Contest name]".

One helper, refund_memo(what, name) (+ its JS twin refundMemo), used by every
refund the Tracker starts: the Refunds console (get_refunds_overview), the
season-contest removal refund, the Customers Refund modal, the apply-credit
excess Venmo-back on Customers and Events. Not all caps, not pipe-separated.

Run: python3 test_refund_memo.py
"""
import os, sys, io, json, subprocess, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-rm-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser.refund_memo import refund_memo, contest_name
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

CASES = [
    (("Refund", "San Antonio Fall Points Race"), "Refund for San Antonio Fall Points Race"),
    (("Refund", "a9.29 Teravista"), "Refund for a9.29 Teravista"),
    (("Refund", "SAN ANTONIO FALL POINTS RACE"), "Refund for San Antonio Fall Points Race"),
    (("Refund", "A9.29 TERAVISTA"), "Refund for a9.29 Teravista"),
    (("Refund", "  s9.18   Cedar Creek "), "Refund for s9.18 Cedar Creek"),
    (("", "s9.18 Cedar Creek"), "Refund for s9.18 Cedar Creek"),
    (("Refund", ""), "Refund"),
    (("Refund", "s9.28 TPC CANYONS", "Jeff Young"), "Jeff Young - Refund for s9.28 TPC Canyons"),
    (("Refund", "a9.29 Teravista", "WADE, Mary"), "Mary Wade - Refund for a9.29 Teravista"),
]
for a, want in CASES:
    check(f"refund_memo{a!r} -> {want!r}", refund_memo(*a) == want, refund_memo(*a))
# a leading event code doesn't stop an ALL-CAPS name being cased; acronyms stay (Kerry 10/30)
check("s9.28 TPC CANYONS -> Refund for s9.28 TPC Canyons",
      refund_memo("Refund", "s9.28 TPC CANYONS") == "Refund for s9.28 TPC Canyons", refund_memo("Refund", "s9.28 TPC CANYONS"))
check("2026 TGF CHAMPIONSHIP keeps TGF",
      refund_memo("Refund", "2026 TGF CHAMPIONSHIP") == "Refund for 2026 TGF Championship")
# Kerry 10/30: "[First Name] [Last Name] - [What]..."
check("player first: Jeff Young - Refund for s9.28 TPC Canyons",
      refund_memo("Refund", "s9.28 TPC CANYONS", "Jeff Young") == "Jeff Young - Refund for s9.28 TPC Canyons")
check("a stored 'YOUNG, Jeff' reads 'Jeff Young'",
      refund_memo("Refund", "s9.28 TPC CANYONS", "YOUNG, Jeff") == "Jeff Young - Refund for s9.28 TPC Canyons")
check("contest name: the product bought wins",
      contest_name("NET Points Race", "San Antonio", "2026", "San Antonio Fall Points Race")
      == "San Antonio Fall Points Race")
check("contest name fallback: chapter + contest (no 'City') + season",
      contest_name("City Match Play", None, "2026", "") == "Match Play 2026")

# The JS twin agrees on every case.
js = ("global.window={};require('./static/js/refund-memo.js');"
      "const c=JSON.parse(process.argv[1]);"
      "console.log(JSON.stringify(c.map(x=>window.refundMemo(x[0],x[1],x[2]))));")
try:
    out = subprocess.run(["node", "-e", js, json.dumps([list(a) for a, _ in CASES])],
                         capture_output=True, text=True, timeout=30)
    got = json.loads(out.stdout)
    check("static/js/refund-memo.js gives the same memo for every case",
          got == [w for _, w in CASES], (got, out.stderr[:200]))
except FileNotFoundError:
    print("  SKIP  node not installed: JS twin not run")

# The Refunds console builds them server-side.
with db._connect(DB) as c:
    db._ensure_refund_watch_table(c)
    c.execute("INSERT INTO events (id, item_name, event_date, chapter) VALUES "
              "(701, 'a9.29 Teravista', '2026-10-01', 'Austin')")
    for cid, fn in ((60, "Amy"), (61, "Ben")):
        c.execute("INSERT INTO customers (customer_id, first_name, last_name, venmo_username) "
                  "VALUES (?, ?, 'Memo', ?)", (cid, fn, f"{fn.lower()}-memo"))
    c.execute("INSERT INTO items (id, email_uid, item_index, merchant, order_date, item_name, customer, "
              "customer_id, item_price, transaction_status, event_id) VALUES "
              "(8101, 'u8101', 0, 'GoDaddy', '2026-09-20', 'a9.29 Teravista', 'Amy Memo', 60, '$40.00', "
              "'credited', 701)")
    c.execute("INSERT INTO items (id, email_uid, item_index, merchant, order_date, item_name, customer, "
              "customer_id, item_price, transaction_status) VALUES "
              "(8102, 'u8102', 0, 'GoDaddy', '2026-03-01', 'SAN ANTONIO FALL POINTS RACE', 'Ben Memo', 61, "
              "'$50.00', 'active')")
    c.execute("INSERT INTO season_contest_removals (customer_name, customer_id, contest_type, chapter, season, "
              "source_item_id, removed_at, reason, refund_amount, refund_method) VALUES "
              "('Ben Memo', 61, 'NET Points Race', 'San Antonio', '2026', 8102, '2026-10-20 10:00:00', "
              "'Withdrew - Injury', 50.0, 'Venmo')")
    c.commit()
ov = db.get_refunds_overview(db_path=DB)
memos = {(r.get("item_id") or ("rm", r.get("removal_id"))): r.get("memo") for r in ov.get("outstanding", [])}
check("credit refund memo: 'Amy Memo - Refund for a9.29 Teravista' (Kerry 10/30: name first)",
      memos.get(8101) == "Amy Memo - Refund for a9.29 Teravista", memos)
with db._connect(DB) as c:
    rid = c.execute("SELECT id FROM season_contest_removals WHERE customer_id = 61").fetchone()[0]
check("season-contest removal memo: 'Ben Memo - Refund for San Antonio Fall Points Race'",
      memos.get(("rm", rid)) == "Ben Memo - Refund for San Antonio Fall Points Race", memos)
check("a removal with no source item: '<player> - Refund for Match Play 2026' (seeded rows)",
      any(m.endswith(" - Refund for Match Play 2026") for m in memos.values()), memos)
check("no memo is all caps or pipe-separated",
      all(m and m != m.upper() and "|" not in m for m in memos.values()), memos)

# A memo without a name never verifies another player's refund watch.
with db._connect(DB) as c:
    c.execute("INSERT INTO refund_watches (item_id, customer_id, customer_name, method, handle, amount, memo, "
              "initiated_at) VALUES (8101, 60, 'Amy Memo', 'Venmo', 'amy-memo', 40.0, "
              "'Refund for a9.29 Teravista', '2026-10-20 10:00:00')")
    c.execute("INSERT INTO expense_transactions (email_uid, source_type, merchant, amount, transaction_date, "
              "transaction_type, customer_id, review_status, notes, created_at) VALUES "
              "('rx1', 'venmo', 'Ben Memo', 40.0, '2026-10-21', 'payout', 61, 'approved', "
              "'Refund for a9.29 Teravista', '2026-10-21 10:00:00')")
    c.commit()
res = db.auto_match_refund_watches(db_path=DB)
with db._connect(DB) as c:
    w = c.execute("SELECT verified_at FROM refund_watches WHERE item_id = 8101").fetchone()
check("same memo + amount but a different customer's receipt: watch stays open", w[0] is None, res)

# Wiring: every refund the Tracker starts uses the helper.
cu, ev, tg = (open(f"templates/{n}.html").read() for n in ("customers", "events", "tgf"))
check("customers.html Refund modal uses refundMemo, with the player", 'window.refundMemo("Refund", _custRefundSource().event, (custPayoutCtx || {}).playerName)' in cu)
check("customers.html excess Venmo-back uses refundMemo, with the player", "window.refundMemo(\"Refund\", sourceEvent || '', customerName)" in cu)
check("events.html both excess Venmo-backs use refundMemo", ev.count('window.refundMemo("Refund"') == 2)
check("tgf.html console fallback uses refundMemo, with the player", 'window.refundMemo("Refund", r.event || "", r.customer)' in tg)
check("the three pages load refund-memo.js",
      all('/static/js/refund-memo.js' in s for s in (cu, ev, tg)))
check("no old 'Excess credit from' memo left in the pages",
      "- Excess credit from ${" not in cu + ev)
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
