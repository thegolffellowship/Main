"""Home-chapter audit (read-only evidence) and the ruling-gated setter (CA #784)."""
import os, sqlite3, sys, tempfile
from email_parser import home_chapter as hc
import email_parser.database as db

FAIL = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    cond or FAIL.append(label)

path = os.path.join(tempfile.mkdtemp(), "t.db")
c = sqlite3.connect(path)
c.executescript("""
CREATE TABLE chapters (chapter_id INTEGER PRIMARY KEY, name TEXT UNIQUE);
INSERT INTO chapters (name) VALUES ('San Antonio'), ('Austin'), ('DFW');
CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT,
                        last_name TEXT, chapter TEXT);
INSERT INTO customers VALUES (50,'Eric','Pollard','San Antonio'),
  (1,'Sam','Home','San Antonio'), (2,'Al','Barna','Austin'), (3,'Bo','Blank',NULL);
CREATE TABLE events (id INTEGER PRIMARY KEY, chapter TEXT);
INSERT INTO events VALUES (10,'San Antonio'),(11,'San Antonio'),(20,'Austin');
CREATE TABLE scoring_rounds (id INTEGER PRIMARY KEY, customer_id INT,
                             event_id INT, round_date TEXT);
INSERT INTO scoring_rounds (customer_id,event_id,round_date) VALUES
  (1,10,'2026-09-01'),(1,11,'2026-09-08'),
  (2,10,'2026-09-01'),(2,11,'2026-09-08'),(2,20,'2026-09-15'),
  (3,20,'2026-09-15'),(50,20,'2026-09-15');
""")
c.commit(); c.close()
LOG = []
db.log_agent_action = lambda *a, **k: LOG.append(a)

a = hc.audit_home_chapters("2026", db_path=path)
f = {p["customer_id"]: p for p in a["flagged"]}
print("\n== audit: evidence only ==")
check("a player who plays only at home is NOT flagged", 1 not in f)
check("a named player (Barna) is listed", 2 in f and "named in CA #784" in f[2]["reasons"])
check("  ...with where he plays shown as evidence",
      f[2]["events_by_chapter"] == {"San Antonio": 2, "Austin": 1}, f.get(2))
check("a blank home chapter is flagged", 3 in f and "blank home chapter" in f[3]["reasons"])
check("someone who never plays at home is flagged", 50 in f)
check("named players sort first", a["flagged"][0]["customer_id"] == 2)
conn = sqlite3.connect(path)
check("the audit wrote nothing", conn.execute(
      "SELECT chapter FROM customers WHERE customer_id=50").fetchone()[0] == "San Antonio")
conn.close()

print("\n== setter: ruling-gated ==")
check("refuses without a ruling reference",
      "error" in hc.set_home_chapter(50, "DFW", "", db_path=path))
check("refuses a chapter not in the chapters table",
      "error" in hc.set_home_chapter(50, "Houston", "CA #784", db_path=path))
r = hc.set_home_chapter(50, "dfw", "CA #784", db_path=path)
check("sets Pollard to DFW under CA #784 (canonical case)",
      r.get("after") == "DFW" and r.get("before") == "San Antonio", r)
check("and logs before/after with the ruling", LOG and "CA #784" in LOG[-1][2])
check("a repeat is a no-op", hc.set_home_chapter(50, "DFW", "CA #784",
      db_path=path).get("unchanged") is True)
print("\n" + "=" * 50)
if FAIL: print(f"{len(FAIL)} FAILED: {FAIL}"); sys.exit(1)
print("ALL HOME-CHAPTER TESTS PASSED")
