"""query_customers: read-only field read of customers (CoS #1048). Run: python3 test_query_customers.py"""
import os, sys, json, sqlite3, tempfile, contextlib, io, logging
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-qc-"), "t.db")
os.environ["DATABASE_PATH"] = DB; os.environ.setdefault("SECRET_KEY", "x")
logging.disable(logging.CRITICAL)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(DB)
    import mcp_server
c = sqlite3.connect(DB)
for cid, fn, ln, ch, st, g in [(901, "Mary", "Wade", "San Antonio", "active_member", "F"),
                               (902, "Pat", "Youngs", "San Antonio", "active_member", "M"),
                               (903, "Lee", "Nogender", "Austin", "active_member", None),
                               (904, "Old", "Timer", "Austin", "expired_member", None)]:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, chapter, current_player_status, gender) "
              "VALUES (?,?,?,?,?,?)", (cid, fn, ln, ch, st, g))
c.execute("INSERT INTO events (id, item_name, event_date) VALUES (77, 's9.9 X', '2026-09-01')")
c.execute("INSERT INTO scoring_rounds (event_id, customer_id, player_name) VALUES (77, 903, 'Lee Nogender')")
c.commit(); before = c.execute("SELECT COUNT(*), SUM(COALESCE(length(gender),0)) FROM customers").fetchone(); c.close()
from email_parser.customer_query import query_customers as qc
f = qc("F", db_path=DB)
check("F list: Mary Wade only, with id/name/chapter/status", [x["customer_id"] for x in f["customers"]] == [901]
      and f["customers"][0]["status"] == "active_member", f)
n = qc("NULL", db_path=DB)
check("NULL list: active members first, then the rest", [x["customer_id"] for x in n["customers"]] == [903, 904], n)
check("rounds this year counted", n["customers"][0]["rounds_since"] == 1)
check("chapter filter", [x["customer_id"] for x in qc("", "austin", db_path=DB)["customers"]] == [903, 904])
check("bad gender refused", "error" in qc("X", db_path=DB))
b = json.loads(mcp_server._scoring_dispatch("", "scoring-query-customers:F||||"))
check("bridge returns the same F list", [x["customer_id"] for x in b["customers"]] == [901], b)
c = sqlite3.connect(DB)
check("read-only: customers unchanged", c.execute("SELECT COUNT(*), SUM(COALESCE(length(gender),0)) FROM customers").fetchone() == before)
print(f"\n{len(F)} FAILURE(S): {F}" if F else "\nALL PASS")
sys.exit(1 if F else 0)
