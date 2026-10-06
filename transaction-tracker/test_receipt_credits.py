"""CREDIT FROM A RECEIVED PAYMENT (Kerry 2026-10-06: "What do you mean no tool
records a payment into a credit? ... We need that tool now if we don't have
it."). Dry run writes nothing; a credit lands in the player's pool; a split
must sum to the receipt; a claimed receipt is refused; no Kerry quote is
refused; undo restores the receipt and zeroes the row.

Run: python3 test_receipt_credits.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                           # noqa: E402
from email_parser import receipt_credits as rc                     # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


with db._connect(DB) as c:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter) "
              "VALUES (700, 'Hamilton', 'Test', 'San Antonio')")
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (701, 'Other', 'Person')")
    rid = c.execute("INSERT INTO expense_transactions (source_type, merchant, amount, transaction_date, "
                    "transaction_type, other_party_handle) VALUES ('venmo', 'Hamilton Test', 325, "
                    "'2026-10-05', 'received', '@ham') RETURNING id").fetchone()[0]
    rid2 = c.execute("INSERT INTO expense_transactions (source_type, merchant, amount, transaction_date, "
                     "transaction_type) VALUES ('venmo', 'Hamilton Test', 450, '2026-10-05', 'received') "
                     "RETURNING id").fetchone()[0]
    out_id = c.execute("INSERT INTO expense_transactions (source_type, merchant, amount, transaction_date, "
                       "transaction_type) VALUES ('venmo', 'Somebody', 50, '2026-10-05', 'payout') "
                       "RETURNING id").fetchone()[0]
    reg = c.execute("INSERT INTO items (customer, customer_id, item_name, item_price, transaction_status, "
                    "order_date, email_uid, merchant) VALUES ('Hamilton Test', 700, 'LSC 2026', '$300.00', "
                    "'active', '2026-09-01', 'manual-reg', 'GoDaddy') RETURNING id").fetchone()[0]
    db._ensure_pairing_tables(c)
    c.commit()
with db._connect(DB) as c:
    k_id = c.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES ('kerry', 'money', "
                     "'Yes, post the credits') RETURNING id").fetchone()[0]
    lane_id = c.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES ('tracker-claude', "
                        "'money', 'TO: kerry\\nI think we should credit him') RETURNING id").fetchone()[0]
    c.commit()


def snapshot():
    with db._connect(DB) as c:
        return (c.execute("SELECT COUNT(*) FROM items").fetchone()[0],
                [tuple(r) for r in c.execute("SELECT id, matched_item_id, notes FROM expense_transactions")])


before = snapshot()
d = rc.post_credit_from_receipt(rid, 700, 325, k_id, db_path=DB)
check("dry run previews the receipt, customer and credit row", d.get("dry_run") and
      d["receipt"]["amount"] == 325 and d["customer"]["customer_id"] == 700, d)
check("dry run writes nothing", snapshot() == before)
check("no Kerry quote is refused", "refused" in rc.post_credit_from_receipt(rid, 700, 325, lane_id, db_path=DB))
check("money paid OUT is refused", "refused" in rc.post_credit_from_receipt(out_id, 700, 50, k_id, db_path=DB))
check("a part that does not sum to the receipt is refused",
      "refused" in rc.post_credit_from_receipt(rid, 700, 300, k_id, db_path=DB))
check("a split onto another customer's registration is refused",
      "refused" in rc.post_credit_from_receipt(rid2, 701, 150, k_id, rest=[{"item_id": reg, "amount": 300}],
                                               db_path=DB))

a = rc.post_credit_from_receipt(rid, 700, 325, k_id, apply=True, db_path=DB)
check("apply writes one credited row", a.get("applied") and a.get("credit_item_id"), a)
pool = db.get_player_credits("Hamilton Test", customer_id=700, db_path=DB)
check("the credit is in the player's pool at $325", any(p["id"] == a["credit_item_id"] and
                                                        p["credit_amount"] == 325 for p in pool), pool)
check("the receipt is claimed by the credit", snapshot()[1][0][1] == a["credit_item_id"])
check("the same receipt cannot be credited twice",
      "refused" in rc.post_credit_from_receipt(rid, 700, 325, k_id, apply=True, db_path=DB))

s = rc.post_credit_from_receipt(rid2, 700, 150, k_id, rest=[{"label": "LSC lodging", "amount": 300}],
                                apply=True, db_path=DB)
check("a split: $150 credit + $300 lodging from one $450 payment", s.get("applied") and
      s["rest"] == [{"label": "LSC lodging", "amount": 300.0}], s)
with db._connect(DB) as c:
    n = c.execute("SELECT notes FROM expense_transactions WHERE id = ?", (rid2,)).fetchone()[0]
check("the split is written on the receipt", "receipt split" in (n or "") and "LSC lodging" in n, n)

u = rc.undo_credit_from_receipt(a["credit_item_id"], k_id, apply=True, db_path=DB)
with db._connect(DB) as c:
    row = c.execute("SELECT transaction_status, item_price FROM items WHERE id = ?",
                    (a["credit_item_id"],)).fetchone()
    m = c.execute("SELECT matched_item_id FROM expense_transactions WHERE id = ?", (rid,)).fetchone()[0]
check("undo keeps the row, zeroes it and frees the receipt",
      u.get("applied") and row[0] == "reversed" and row[1] == "$0.00" and m is None, (u, tuple(row), m))
check("an undone credit leaves the pool",
      not any(p["id"] == a["credit_item_id"] for p in db.get_player_credits("Hamilton Test", customer_id=700,
                                                                              db_path=DB)))

print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED'}")
sys.exit(1 if F else 0)
