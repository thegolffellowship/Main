"""COURSE STAFF (migration 0014; Kerry 2026-10-13, rule 3b "Deploy now" #1737;
shape #1699, db-claude PASS with changes #1701).

Run: python3 test_course_staff.py
"""
import contextlib
import io
import logging
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    db.init_db(DB)
from email_parser import course_staff as cs  # noqa: E402

F = []
HERE = os.path.dirname(os.path.abspath(__file__))


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


def q(sql, *a):
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    try:
        return c.execute(sql, a).fetchall()
    finally:
        c.close()


print("schema (0014, #1701)")
sql = open(os.path.join(HERE, "migrations", "0014_course_staff.sql")).read()
check("the migration applied on init", q("SELECT 1 FROM schema_migrations WHERE name = '0014_course_staff.sql'"))
sql15 = open(os.path.join(HERE, "migrations", "0015_course_staff_scheduling_role.sql")).read()
check("0014 carries its 7 roles; 0015 adds 'scheduling' (Kerry 10/13) and the code knows all 8",
      len(cs.ROLES) == 8 and "scheduling" in cs.ROLES
      and all(f"'{r}'" in sql for r in cs.ROLES if r != "scheduling")
      and all(f"'{r}'" in sql15 for r in cs.ROLES))
check("0015 applied, and the rebuilt table keeps the primary index",
      q("SELECT 1 FROM schema_migrations WHERE name = '0015_course_staff_scheduling_role.sql'")
      and q("SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'ux_course_staff_primary'"))
check("one primary per role per course, among active rows",
      "ux_course_staff_primary" in sql and "WHERE is_primary = 1 AND active = 1" in sql)
check("course cascades, customer restricts; booleans checked; updated_at",
      "ON DELETE CASCADE" in sql and "ON DELETE RESTRICT" in sql and "CHECK (is_primary IN (0, 1))" in sql
      and "CHECK (active IN (0, 1))" in sql and "updated_at" in sql)
check("no email column: the email comes from customer_emails", "email" not in sql.split("CREATE TABLE")[1].split(");")[0].lower())
check("merge safety: course_staff.customer_id is in _CUSTOMER_FK_COLUMNS",
      ("course_staff", "customer_id") in db._CUSTOMER_FK_COLUMNS)

c = sqlite3.connect(DB)
qid = c.execute("INSERT INTO courses (name) VALUES ('The Quarry Golf Club') RETURNING course_id").fetchone()[0]
# an existing MEMBER who will also be a course contact
mid = c.execute("INSERT INTO customers (first_name, last_name, account_status) VALUES ('Miguel', 'Amaya', 'active') "
                "RETURNING customer_id").fetchone()[0]
c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?, 'miguel@quarrygolf.com', 1)", (mid,))
c.execute("INSERT INTO items (email_uid, item_index, customer, customer_id, item_name, merchant, order_date) "
          "VALUES ('t-1', 0, 'Miguel Amaya', ?, 's9.20 The Quarry', 'GoDaddy', '2026-09-20')", (mid,))
c.execute("INSERT INTO platform_dialogue (id, author, topic, body) VALUES (9001, 'kerry', 'database', 'Deploy now')")
c.execute("INSERT INTO platform_dialogue (id, author, topic, body) VALUES (9002, 'tracker-claude', 'database', 'no word')")
c.commit(); c.close()

print("save_staff")
n0 = q("SELECT COUNT(*) n FROM customers")[0]["n"]
d = cs.save_staff(qid, name="Chris Lopez", email="chris@quarrygolf.com", role="tgf_contact", is_primary=True, db_path=DB)
check("dry run by default: nothing written", d.get("dry_run") and q("SELECT COUNT(*) n FROM customers")[0]["n"] == n0, d)
check("a bad role is refused", "refused" in cs.save_staff(qid, name="X Y", role="caddie", db_path=DB))
check("a bad email is refused", "refused" in cs.save_staff(qid, name="X Y", email="nope", db_path=DB))
check("a bridge write needs Kerry's word", "refused" in cs.save_staff(qid, name="X Y", kerry_ok_post=9002, apply=True, db_path=DB))
r = cs.save_staff(qid, name="Chris Lopez", email="chris@quarrygolf.com", role="tgf_contact", is_primary=True,
                  apply=True, kerry_ok_post=9001, db_path=DB)
chris = r.get("customer_id")
check("a new person gets a customer_id, email, course_contact role", r.get("applied") and chris
      and q("SELECT acquisition_source s FROM customers WHERE customer_id = ?", chris)[0]["s"] == "course_contact"
      and q("SELECT 1 FROM customer_emails WHERE customer_id = ? AND email = 'chris@quarrygolf.com'", chris)
      and q("SELECT 1 FROM customer_roles WHERE customer_id = ? AND role_type = 'course_contact'", chris), r)
r2 = cs.save_staff(qid, name="Christopher Lopez", email="CHRIS@quarrygolf.com", role="billing", apply=True, db_path=DB)
check("the same email resolves to the same person (dedupe, case-insensitive)", r2.get("customer_id") == chris, r2)
r3 = cs.save_staff(qid, name="Miguel Amaya", email="miguel@quarrygolf.com", role="head_golf_professional",
                   is_primary=True, apply=True, db_path=DB)
check("an existing member is reused, not duplicated", r3.get("customer_id") == mid and r3.get("person") == "email", r3)
cs.save_staff(qid, name="Alec Cech", email="alec@quarrygolf.com", role="tgf_contact", apply=True, db_path=DB)

rs = cs.save_staff(qid, name="Brenda Willis", email="bwillis@arcisgolf.com", role="scheduling",
                   is_primary=True, apply=True, db_path=DB)
check("a 'scheduling' contact saves", rs.get("applied") and rs["role"] == "scheduling", rs)

print("print recipients")
with db._connect(DB) as conn:
    p = cs.print_recipients(conn, qid)
check("To the primary TGF contact, CC the other TGF contacts (scheduling is not on the print email)",
      p["ok"] and p["to"] == "chris@quarrygolf.com" and p["cc"] == ["alec@quarrygolf.com"], p)
dz = cs.save_staff(qid, name="Alec Cech", email="alec@quarrygolf.com", role="tgf_contact", is_primary=True, apply=True, db_path=DB)
with db._connect(DB) as conn:
    p = cs.print_recipients(conn, qid)
check("a new primary demotes the old one (one primary per role)",
      dz.get("demotes") == "Chris Lopez" and p["to"] == "alec@quarrygolf.com" and p["cc"] == ["chris@quarrygolf.com"], p)
cs.save_staff(qid, customer_id=dz["customer_id"], role="tgf_contact", active=False, apply=True, db_path=DB)
with db._connect(DB) as conn:
    p = cs.print_recipients(conn, qid)
    allrows = cs.for_course(conn, qid, include_inactive=True)
check("no active primary: refused, never guessed", not p["ok"] and "no primary" in p["why"], p)
check("a removed contact is kept (deactivated, not deleted)",
      any(s["customer_id"] == dz["customer_id"] and not s["active"] for s in allrows))
cs.save_staff(qid, customer_id=chris, role="tgf_contact", is_primary=True, apply=True, db_path=DB)
try:
    c = sqlite3.connect(DB)
    c.execute("UPDATE course_staff SET is_primary = 1, active = 1 WHERE role = 'tgf_contact' AND customer_id = ?",
              (dz["customer_id"],))
    c.commit(); dup_ok = True
except sqlite3.IntegrityError:
    dup_ok = False
finally:
    c.close()
check("the database itself refuses two active primaries for one role", not dup_ok)

print("not a member audience (#1701-b)")
with db._connect(DB) as conn:
    nm = cs.non_member_ids(conn)
check("a course-contact-only person is not a member", chris in nm)
check("a member who is also a course contact stays a member", mid not in nm)
c = sqlite3.connect(DB)
c.execute("CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY, customer_id INTEGER, chapter TEXT)")
c.commit(); c.close()
from email_parser import brevo  # noqa: E402
targets = brevo.tracker_contact_targets(DB)
check("Brevo sync never sees a course contact", "chris@quarrygolf.com" not in targets
      and "miguel@quarrygolf.com" in targets, sorted(targets))
from email_parser import customer_query  # noqa: E402
qc = customer_query.query_customers(db_path=DB) if hasattr(customer_query, "query_customers") else {}
_lst = next((v for v in qc.values() if isinstance(v, list)), []) if isinstance(qc, dict) else []
names = {x.get("customer_id") for x in _lst}
check("query_customers never lists a course contact, but lists the member",
      chris not in names and mid in names, qc)
src = open(os.path.join(HERE, "email_parser", "database.py")).read()
check("the pairings roster reads the same predicate", "_vendors = _non_member_ids(conn)" in src)

print("seed (The Quarry, #1699)")
c = sqlite3.connect(DB)
qid2 = c.execute("INSERT INTO courses (name) VALUES ('Quarry Seed Test') RETURNING course_id").fetchone()[0]
c.commit(); c.close()
s = cs.seed_quarry(qid2, kerry_ok_post=9001, db_path=DB)
check("the seed is a dry run first: 5 rows planned, nothing written",
      s["count"] == 5 and all(r.get("dry_run") for r in s["rows"])
      and not q("SELECT 1 FROM course_staff WHERE course_id = ?", qid2), s)
s = cs.seed_quarry(qid2, kerry_ok_post=9001, apply=True, db_path=DB)
rows = q("SELECT customer_id, role, is_primary FROM course_staff WHERE course_id = ?", qid2)
check("applied: 5 course_staff rows, Miguel twice as one person",
      len(rows) == 5 and len({r["customer_id"] for r in rows}) == 4
      and sum(1 for r in rows if r["customer_id"] == mid) == 2, [dict(r) for r in rows])

print("0015 rebuild keeps every row (run 0015 again on a copy that holds rows)")
import shutil  # noqa: E402
cp = DB + ".copy"
shutil.copy(DB, cp)
c = sqlite3.connect(cp)
before = c.execute("SELECT course_staff_id, course_id, customer_id, role, is_primary, active FROM course_staff ORDER BY 1").fetchall()
c.executescript(sql15)
after = c.execute("SELECT course_staff_id, course_id, customer_id, role, is_primary, active FROM course_staff ORDER BY 1").fetchall()
idx = c.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'course_staff'").fetchall()
c.close()
check("same rows, same ids, same flags after the rebuild", before == after and len(before) > 3, (before, after))
check("all three indexes re-created", {"idx_course_staff_course", "idx_course_staff_customer",
      "ux_course_staff_primary"} <= {r[0] for r in idx}, idx)

print("surfaces")
app_src = open(os.path.join(HERE, "app.py")).read()
ev_src = open(os.path.join(HERE, "templates", "events.html")).read()
cd_src = open(os.path.join(HERE, "templates", "course_db.html")).read()
mcp = open(os.path.join(HERE, "mcp_server.py")).read()
check("staff API: GET for managers, POST admin only",
      '@app.route("/api/courses/<int:course_id>/staff", methods=["GET", "POST"])' in app_src
      and 'if session.get("role") != "admin":\n        return jsonify({"error": "Admin access required."}), 403' in app_src)
check("event setup shows the course's contacts", 'id="edit-event-course-staff"' in ev_src
      and 'id="add-event-course-staff"' in ev_src and "async function showCourseStaff(" in ev_src)
check("Courses page manages them", "async function openStaff(" in cd_src and '"Contacts"' not in cd_src
      and ">Contacts</button>" in cd_src)
check("bridges: read, set (Kerry's word), seed", all(f'"{b}"' in mcp for b in
      ("scoring-course-staff", "scoring-course-staff-set", "scoring-course-staff-seed"))
      and '"scoring-course-contact"' not in mcp)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
