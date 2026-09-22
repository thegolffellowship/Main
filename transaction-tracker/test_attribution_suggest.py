"""Guessing who referred someone from what the order already says.

Kerry 2026-09-22, on Shahyan Javed: "Shahyan Javed should have
automatically been attributed to Jeff Young because Jeff purchased him.
He should only show up on a 1st Timer attribution list to confirm it was
Jeff, with an option to switch in worst case."
"""
import os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FAIL = []
def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("  " + str(detail) if not cond else ""))
    if not cond: FAIL.append(label)

from email_parser.attribution import suggest_referrer

PEOPLE = [(88, "Jeff", "Young"), (831, "Shahyan", "Javed"),
          (427, "Isaac", "Reyes"), (709, "Justin", "Angelone"),
          (101, "Jesse", "Saldana"), (555, "Jeff", "Otherguy")]

def db(items, people=PEOPLE):
    c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,
            first_name TEXT, last_name TEXT);
        CREATE TABLE customer_emails (email_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER, email TEXT, is_primary INTEGER);
        CREATE TABLE customer_aliases (id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER, customer_name TEXT, alias_type TEXT,
            alias_value TEXT);
        CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER, order_date TEXT, notes TEXT, coupon_code TEXT,
            referred_by TEXT, referral TEXT,
            transaction_status TEXT DEFAULT 'active');
    """)
    for cid, f, l in people:
        c.execute("INSERT INTO customers VALUES (?,?,?)", (cid, f, l))
    for it in items:
        c.execute("INSERT INTO items (customer_id, order_date, notes, "
                  "coupon_code, referred_by, referral) VALUES (?,?,?,?,?,?)",
                  (it.get("cid", 831), it.get("date", "2026-09-21"),
                   it.get("notes"), it.get("coupon"), it.get("referred_by"),
                   it.get("referral")))
    c.commit(); return c

print("Shahyan Javed's actual order")
r = suggest_referrer(831, db([{"notes": "Purchased by Jeff Young",
                               "coupon": "tgf-jeff"}]))
check("it names Jeff Young without being asked", r and r["referrer_customer_id"] == 88, r)
check("...as bought_spot, because the Tracker WATCHED the purchase",
      r and r["source"] == "bought_spot", r)
check("...and says what it is based on", r and "Purchased by Jeff Young" in r["evidence"], r)
check("...with high confidence", r and r["confidence"] == "high", r)

print("The signals, strongest first")
r = suggest_referrer(831, db([{"referred_by": "Isaac Reyes",
                               "notes": "Purchased by Jeff Young"}]))
check("the FORM field beats a purchase note — it is the person's own answer",
      r and r["referrer_customer_id"] == 427 and r["source"] == "lead_form", r)
r = suggest_referrer(831, db([{"referral": "Isaac Reyes"}]))
check("the `referral` column is read too", r and r["referrer_customer_id"] == 427, r)
r = suggest_referrer(831, db([{"coupon": "tgf-referral-jesse"}]))
check("a referral coupon names its owner", r and r["referrer_customer_id"] == 101
      and r["source"] == "coupon", r)
r = suggest_referrer(831, db([{"coupon": "tgf-isaac"}]))
check("a named coupon resolves on an unambiguous first name",
      r and r["referrer_customer_id"] == 427, r)
check("...at MED confidence — a coupon token is a nickname, not an identity",
      r and r["confidence"] == "med", r)

print("When it must refuse to guess")
r = suggest_referrer(831, db([{"coupon": "tgf-jeff"}]))
check("TWO Jeffs means no suggestion — the Tracker does not know which",
      r is None, r)
r = suggest_referrer(831, db([{"notes": "Purchased by Nobody Here"}]))
check("a name that resolves to nobody is not invented", r is None, r)
r = suggest_referrer(831, db([{"notes": "Purchased by Shahyan Javed"}]))
check("nobody refers themselves", r is None, r)
check("an order that says nothing suggests nothing — silence is an answer",
      suggest_referrer(831, db([{"notes": None}])) is None)
check("a customer with no orders at all", suggest_referrer(999, db([])) is None)

print("Degrading safely")
c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
c.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY)")
check("no items table is silence, never a crash", suggest_referrer(1, c) is None)

print("Nothing here WRITES — derive, then confirm")
conn = db([{"notes": "Purchased by Jeff Young"}])
suggest_referrer(831, conn)
got = conn.execute("SELECT COUNT(*) FROM pragma_table_info('customers') "
                   "WHERE name = 'referred_by_customer_id'").fetchone()[0]
check("the suggester never touches the attribution column", got == 0,
      "a suggestion is evidence, not a decision")

print(f"\n{len(FAIL)} FAILURE(S): {FAIL}" if FAIL else "\nALL PASS")
sys.exit(1 if FAIL else 0)
