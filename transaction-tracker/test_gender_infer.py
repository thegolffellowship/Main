"""GENDER FROM TEES (Kerry 2026-10-14, #1815/#1840, migration 0019).

- a Forward registration with no rated rounds → F, inferred;
- majority F-rated rounds → F, inferred;
- Forward band but M-rated rounds (a senior man on M-rated Forward) → conflict, nothing set;
- a gender already on file is never overwritten;
- the dry run writes nothing; apply marks gender_source;
- the job does nothing while the dial is off;

Run: python3 test_gender_infer.py
"""
import contextlib, io, logging, os, sqlite3, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-gender-"), "t.db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    db.init_db(DB)
from email_parser import customers_gender as cg  # noqa: E402

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


c = sqlite3.connect(DB)
check("migration 0019 adds customers.gender_source",
      any(r[1] == "gender_source" for r in c.execute("PRAGMA table_info(customers)")))
db._ensure_scoring_tables(c)
course = c.execute("INSERT INTO courses (name, status) VALUES ('G Links', 'active') RETURNING course_id").fetchone()[0]
tf = c.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, nine, rating, slope, source) "
               "VALUES (?, 'Forward', 'F', 9, 'front', 33.0, 110, 'admin') RETURNING tee_id", (course,)).fetchone()[0]
tm = c.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, nine, rating, slope, source) "
               "VALUES (?, 'Forward', 'M', 9, 'front', 31.0, 100, 'admin') RETURNING tee_id", (course,)).fetchone()[0]
people = {801: ("Fran", "Forward", None), 802: ("Rita", "Rounds", None), 803: ("Sam", "Senior", None),
          804: ("Stated", "Male", "M"), 805: ("No", "Signal", None)}
for cid, (fn, ln, g) in people.items():
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, gender) VALUES (?,?,?,?)",
              (cid, fn, ln, g))
for cid in (801, 803, 804):
    c.execute("INSERT INTO items (email_uid, item_index, merchant, customer, customer_id, item_name, "
              "transaction_status, tee_choice, order_date, item_price) VALUES (?, 0, 'Manual Entry', 'x', ?, 's9.28 X', "
              "'active', 'Forward', '2026-10-01', '$50.00')",
              (f"m-{cid}", cid))
for cid, tee, n in ((802, tf, 3), (802, tm, 1), (803, tm, 2), (804, tf, 3)):
    for _ in range(n):
        c.execute("INSERT INTO scoring_rounds (customer_id, player_name, round_date, holes_played, gross, "
                  "tee_id, source) VALUES (?, 'x', '2026-10-01', 9, 45, ?, 'entry')", (cid, tee))
c.commit(); c.close()

dry = cg.infer(db_path=DB)
would = {r["customer_id"] for r in dry["would_set"]}
check("Forward registration, no rated rounds → F", 801 in would, dry)
check("majority F-rated rounds → F", 802 in would, dry)
check("Forward band but M-rated rounds → conflict, not set",
      803 not in would and 803 in {r["customer_id"] for r in dry["conflicts"]}, dry)
check("a stated gender is never a candidate", 804 not in would)
check("no signal, nothing", 805 not in would)
g = {r[0]: (r[1], r[2]) for r in sqlite3.connect(DB).execute(
    "SELECT customer_id, gender, gender_source FROM customers WHERE customer_id BETWEEN 801 AND 805")}
check("the dry run writes nothing", g[801] == (None, None) and g[802] == (None, None), g)

off = cg.run_job(db_path=DB)
check("the job does nothing while the dial is off", off.get("skipped") and
      sqlite3.connect(DB).execute("SELECT gender FROM customers WHERE customer_id = 801").fetchone()[0] is None)

c = sqlite3.connect(DB)
c.execute("UPDATE customers SET gender = 'M', gender_source = 'stated' WHERE customer_id = 802")
c.commit(); c.close()
app = cg.infer(apply=True, db_path=DB)
g = {r[0]: (r[1], r[2]) for r in sqlite3.connect(DB).execute(
    "SELECT customer_id, gender, gender_source FROM customers WHERE customer_id BETWEEN 801 AND 805")}
check("apply sets F and marks it inferred", g[801] == ("F", "inferred_from_tees"), g)
check("a gender stated after the list was read is never overwritten", g[802] == ("M", "stated"), g)
check("the conflict and the stated man are untouched", g[803] == (None, None) and g[804][0] == "M", g)
check("one id only", cg.infer(customer_ids=[805], db_path=DB)["would_set"] == [])

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILED: {F}"))
sys.exit(1 if F else 0)
