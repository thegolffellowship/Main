"""A referral that becomes a MEMBER owes the referrer a fee.

Kerry 2026-09-21, on Guillermo Arevalo: "He was Robert's referral and
became a member so it needs to trigger a referral fee payment."

This amends the 2026-07-30 rule that a relationship must never mint a
liability. The rule still holds for the relationship ALONE — what
creates the fee is relationship PLUS membership. The coupon rule is
untouched and wins: a redeemed coupon IS the compensation, so a pair it
already covers never gets cash on top.
"""
import os, sqlite3, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FAIL = []
def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("  " + str(detail) if not cond else ""))
    if not cond: FAIL.append(label)

import email_parser.database as db

SCHEMA = """
CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT,
    last_name TEXT, venmo_username TEXT, referred_by_customer_id INTEGER,
    referred_by_source TEXT);
CREATE TABLE customer_memberships (id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER, started_at TEXT, expires_at TEXT, price_paid REAL);
CREATE TABLE items (id INTEGER PRIMARY KEY, customer TEXT, customer_id INTEGER,
    coupon_code TEXT, order_date TEXT, transaction_status TEXT DEFAULT 'active');
CREATE TABLE expense_transactions (id INTEGER PRIMARY KEY, merchant TEXT,
    amount REAL, transaction_date TEXT, customer_id INTEGER, notes TEXT,
    transaction_type TEXT, source_type TEXT, acct_transaction_id INTEGER);
CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);
"""

def fresh(referred_is_member=True, prior_fee=None):
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    # 31 Robert Straiton referred 821 Guillermo Arevalo.
    c.execute("INSERT INTO customers VALUES (31,'Robert','Straiton','rstraiton',NULL,NULL)")
    c.execute("INSERT INTO customers VALUES (821,'Guillermo','Arevalo',NULL,31,'member_claim')")
    # 829 Ty Bubela, referred but NOT a member.
    c.execute("INSERT INTO customers VALUES (829,'Ty','Bubela',NULL,31,'member_claim')")
    # 999 nobody referred.
    c.execute("INSERT INTO customers VALUES (999,'Walk','In',NULL,NULL,NULL)")
    if referred_is_member:
        c.execute("INSERT INTO customer_memberships (customer_id, started_at, "
                  "expires_at, price_paid) VALUES (821,'2026-09-13','2027-09-13',50.0)")
    c.execute("INSERT INTO customer_memberships (customer_id, started_at, "
              "expires_at, price_paid) VALUES (999,'2026-01-01','2027-01-01',100.0)")
    c.commit(); c.close()
    if prior_fee:
        conn = sqlite3.connect(path)
        db._ensure_referral_tables(conn)
        conn.execute(
            "INSERT INTO referral_fees (referrer_customer_id, referrer_name, "
            "referred_customer_id, referred_name, source, amount, status) "
            "VALUES (31,'Robert Straiton',821,'Guillermo Arevalo',?,25.0,?)",
            prior_fee)
        conn.commit(); conn.close()
    return path

def fees(path, status=None):
    conn = sqlite3.connect(path); conn.row_factory = sqlite3.Row
    q = "SELECT * FROM referral_fees"
    rows = [dict(r) for r in conn.execute(q).fetchall()]
    conn.close()
    return [r for r in rows if status is None or r["status"] == status]

print("The membership trigger")
p = fresh()
out = db.sync_referral_fees(db_path=p)
rows = fees(p)
check("a referred player who JOINED raises a fee", len(rows) == 1, rows)
g = rows[0] if rows else {}
check("...owed to the referrer", g.get("referrer_customer_id") == 31, g)
check("...for the referred person", g.get("referred_customer_id") == 821, g)
check("...at the configured amount", g.get("amount") == 25.0, g)
check("...marked source 'membership', not coupon or receipt",
      g.get("source") == "membership", g)
check("...as OWED, so it shows up to be paid", g.get("status") == "owed", g)
check("...with a note saying why", g.get("note") and "became a member" in g["note"], g)
check("the sync reports it", out.get("membership_owed") == 1, out)

print("Who does NOT trigger one")
rows = fees(p)
check("a referred player who has NOT joined owes nothing — membership is the gate "
      "(Kerry: 'A referral only comes when the person buys a membership')",
      all(r["referred_customer_id"] != 829 for r in rows), rows)
check("a member nobody referred owes nothing",
      all(r["referred_customer_id"] != 999 for r in rows), rows)

print("Idempotency — this runs on every sync")
db.sync_referral_fees(db_path=p)
db.sync_referral_fees(db_path=p)
check("running it three times still leaves ONE fee", len(fees(p)) == 1, fees(p))
os.unlink(p)

print("The coupon rule wins (Kerry 2026-07-28)")
p = fresh(prior_fee=("coupon", "comped"))
db.sync_referral_fees(db_path=p)
rows = fees(p)
check("a pair already COMPED by a coupon gets no cash fee on top",
      len(rows) == 1 and rows[0]["status"] == "comped", rows)
os.unlink(p)

p = fresh(prior_fee=("receipt", "paid"))
db.sync_referral_fees(db_path=p)
rows = fees(p)
check("a pair already PAID is not billed twice",
      len(rows) == 1 and rows[0]["status"] == "paid", rows)
os.unlink(p)

p = fresh(prior_fee=("manual", "owed"))
db.sync_referral_fees(db_path=p)
check("a pair already OWED is not duplicated", len(fees(p)) == 1, fees(p))
os.unlink(p)

print("The relationship ALONE still mints nothing (2026-07-30 rule intact)")
p = fresh(referred_is_member=False)
db.sync_referral_fees(db_path=p)
check("naming who referred someone, with no membership, owes nobody anything",
      fees(p) == [], fees(p))
os.unlink(p)

print(f"\n{len(FAIL)} FAILURE(S): {FAIL}" if FAIL else "\nALL PASS")
sys.exit(1 if FAIL else 0)
