"""The two narrow write paths behind CA #788 item 5: patch_acct_row can tie a
ledger row to a real customer (and refuses an unknown one), and
set_term_price_paid records one term's price, dry run by default.

Run: python3 test_talamantez_writes.py
"""
import os
import sqlite3
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")
FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILURES.append(label)


def main():
    from email_parser import database as db
    from email_parser import memberships as mem
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db.init_db(p)
    conn = sqlite3.connect(p)
    with db._connect(p) as c2:
        mem.ensure_membership_tables(c2)
    cid = conn.execute("INSERT INTO customers (first_name, last_name) VALUES ('Mark', 'T') "
                       "RETURNING customer_id").fetchone()[0]
    tid = conn.execute("INSERT INTO acct_transactions (date, description, total_amount, type, source) "
                       "VALUES ('2026-06-01', 'Mark Talamantez', 75, 'income', 'test') RETURNING id").fetchone()[0]
    term = conn.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, source, notes) "
                        "VALUES (?, '2026-03-26', '2027-03-26', 'manual', 'Venmo') RETURNING id", (cid,)).fetchone()[0]
    conn.commit()
    conn.close()

    bad = db.patch_acct_row(tid, {"customer_id": 999999}, db_path=p)
    check("an unknown customer is refused", "error" in bad, bad)
    db.patch_acct_row(tid, {"customer_id": cid}, db_path=p)
    conn = sqlite3.connect(p)
    got = conn.execute("SELECT customer_id FROM acct_transactions WHERE id = ?", (tid,)).fetchone()[0]
    conn.close()
    check("ledger row now carries the customer", got == cid, got)

    dry = mem.set_term_price_paid(term, "75", db_path=p)
    conn = sqlite3.connect(p)
    pp = conn.execute("SELECT price_paid FROM customer_memberships WHERE id = ?", (term,)).fetchone()[0]
    conn.close()
    check("price dry run writes nothing", not dry["applied"] and pp is None, (dry, pp))
    mem.set_term_price_paid(term, "75", db_path=p, apply=True)
    conn = sqlite3.connect(p)
    pp = conn.execute("SELECT price_paid FROM customer_memberships WHERE id = ?", (term,)).fetchone()[0]
    conn.close()
    check("price applied", pp == 75.0, pp)
    check("negative price refused", "error" in mem.set_term_price_paid(term, "-1", db_path=p))
    check("unknown term refused", "error" in mem.set_term_price_paid(999999, "75", db_path=p))
    os.remove(p)
    print(f"\n{len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
