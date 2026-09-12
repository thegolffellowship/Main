"""An expense dismissed as 'ignored' after it reached the ledger must
REVERSE its acct_transactions row (Chase alerts on charges only; a
same-day issuer reversal never arrives) — v2.387.5. Also: patch_acct_row
accepts status 'reversed' for rows with no expense backing."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from email_parser import database as db

tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False); tmp.close(); p = tmp.name
db.init_db(p)
with db._connect(p) as conn:
    conn.execute("""INSERT INTO expense_transactions
        (id, source_type, merchant, amount, transaction_date, transaction_type,
         entity, review_status) VALUES
        (2550, 'chase_alert', 'LS Forest Creek Golf', 2270.0, '2026-09-12',
         'expense', 'TGF', 'approved')""")
    conn.commit()
r = db.promote_expense_to_ledger(2550, None, "TGF", db_path=p)
with db._connect(p) as conn:
    acct_id = conn.execute("SELECT acct_transaction_id FROM expense_transactions WHERE id=2550").fetchone()[0]
    assert acct_id, r
    assert conn.execute("SELECT COALESCE(status,'active') FROM acct_transactions WHERE id=?", (acct_id,)).fetchone()[0] == "active"

out = db.patch_expense_row(2550, {"review_status": "ignored", "append_note": "reversed same day"}, db_path=p)
assert out.get("ledger_row_reversed") == acct_id, out
assert out["expense"]["review_status"] == "ignored", out
with db._connect(p) as conn:
    st, notes = conn.execute("SELECT status, notes FROM acct_transactions WHERE id=?", (acct_id,)).fetchone()
    assert st == "reversed", st
    assert "reversed same day" in (notes or ""), notes
    # a later non-status patch must NOT resurrect the ledger row
db.patch_expense_row(2550, {"append_note": "second note"}, db_path=p)
with db._connect(p) as conn:
    st = conn.execute("SELECT status FROM acct_transactions WHERE id=?", (acct_id,)).fetchone()[0]
    assert st == "reversed", f"re-sync resurrected the row: {st}"

# patch_acct_row status=reversed on a bare ledger row, then back to active
with db._connect(p) as conn:
    conn.execute("""INSERT INTO acct_transactions (date, description, total_amount, amount, type, entry_type, source, source_ref)
                    VALUES ('2026-09-12','bare row',5,5,'expense','flat','manual','t-1')""")
    bare = conn.execute("SELECT last_insert_rowid()").fetchone()[0]; conn.commit()
r = db.patch_acct_row(bare, {"status": "reversed"}, db_path=p)
assert "status:reversed" in r["applied"], r
with db._connect(p) as conn:
    assert conn.execute("SELECT status FROM acct_transactions WHERE id=?", (bare,)).fetchone()[0] == "reversed"
r = db.patch_acct_row(bare, {"status": "active"}, db_path=p)
with db._connect(p) as conn:
    assert conn.execute("SELECT status FROM acct_transactions WHERE id=?", (bare,)).fetchone()[0] == "active"
r = db.patch_acct_row(bare, {"status": "bogus"}, db_path=p)
assert "error" in r, r
os.unlink(p)
print("ALL PASSED")
