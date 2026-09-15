"""One-shot pace rulings (Kerry 2026-09-15): Dan Stich (298) and Jeff
Rideout (6) go from a tapped 1 to an explicit 2, once. A later tap is
never undone by a redeploy, and a value already corrected is left alone.
Run: python3 test_pace_rulings.py
"""
import os, sqlite3, sys
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

conn = sqlite3.connect(":memory:"); conn.row_factory = sqlite3.Row
conn.executescript("""
 CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT,
   pace_rating INTEGER, pace_rating_source TEXT);
 INSERT INTO customers VALUES (298, 'Dan', 'Stich', 1, 'manager');
 INSERT INTO customers VALUES (6, 'Jeff', 'Rideout', 3, 'manager');   -- already changed by Kerry
 INSERT INTO customers VALUES (21, 'Richard', 'Palacios', 1, 'manager');
""")
n = db._repair_pace_rulings_2026_09_15(conn)
pace = lambda cid: conn.execute("SELECT pace_rating, pace_rating_source FROM customers WHERE customer_id=?", (cid,)).fetchone()
check("Dan Stich 1 -> 2, source manager", tuple(pace(298)) == (2, "manager"), str(tuple(pace(298))))
check("a value Kerry already moved off 1 is left alone (Rideout 3 stays 3)", pace(6)["pace_rating"] == 3)
check("nobody else is touched (Palacios stays 1)", pace(21)["pace_rating"] == 1)
check("reports one row changed", n == 1, str(n))
conn.execute("UPDATE customers SET pace_rating = 1 WHERE customer_id = 298")   # a later tap back to 1
n2 = db._repair_pace_rulings_2026_09_15(conn)
check("second run is a no-op (flag set) — a later tap survives a redeploy", n2 == 0 and pace(298)["pace_rating"] == 1, str((n2, pace(298)["pace_rating"])))
check("the flag records what it did", conn.execute("SELECT value FROM app_settings WHERE key='pace_rulings_2026_09_15_applied'").fetchone()[0] == "1")
print("\n" + ("FAILED: " + ", ".join(F) if F else "ALL PASSED")); sys.exit(1 if F else 0)
