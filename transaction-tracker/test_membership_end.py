"""A member who no longer wants to be one (Kerry 2026-10-18: "Randy no longer
wants to be a member so he can be noted as such."). end_membership ends the
running term yesterday, marks every term roster_choice remove, stamps every
notice so no renewal or lapsed email goes, and leaves him expired_member even
after the status sync runs.

Run: python3 test_membership_end.py
"""
import contextlib, io, logging, os, sys, tempfile
from datetime import timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import memberships as m
    from email_parser.timezone_utils import today_central
    DB = os.environ["DATABASE_PATH"]
    db.init_db(DB)

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


today = today_central()
with db._connect(DB) as c:
    m.ensure_membership_tables(c)
    cid = c.execute("INSERT INTO customers (first_name, last_name, current_player_status) "
                    "VALUES ('Randy', 'Test', 'active_member') RETURNING customer_id").fetchone()[0]
    c.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, source, price_paid) "
              "VALUES (?, ?, ?, 'manual', 75)",
              (cid, (today - timedelta(days=100)).isoformat(), (today + timedelta(days=265)).isoformat()))
    c.execute("INSERT INTO customer_memberships (customer_id, started_at, expires_at, source, price_paid) "
              "VALUES (?, ?, ?, 'manual', 75)",
              (cid, (today - timedelta(days=465)).isoformat(), (today - timedelta(days=100)).isoformat()))
    lane = c.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES "
                     "('tracker-claude', 'x', 'Kerry wants it') RETURNING id").fetchone()[0]
    ok = c.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES "
                   "('kerry', 'x', 'Randy no longer wants to be a member') RETURNING id").fetchone()[0]
    c.commit()

print("end_membership")
check("a lane's own post is refused", "refused" in m.end_membership(cid, lane, db_path=DB))
dry = m.end_membership(cid, ok, db_path=DB)
with db._connect(DB) as c:
    st = c.execute("SELECT current_player_status FROM customers WHERE customer_id = ?", (cid,)).fetchone()[0]
check("dry run changes nothing", dry.get("dry_run") and st == "active_member", (dry, st))
res = m.end_membership(cid, ok, apply=True, db_path=DB)
with db._connect(DB) as c:
    m.sync_player_status_with_terms(c)
    c.commit()
    st = c.execute("SELECT current_player_status FROM customers WHERE customer_id = ?", (cid,)).fetchone()[0]
    terms = [dict(r) for r in c.execute("SELECT * FROM customer_memberships WHERE customer_id = ?", (cid,))]
yday = (today - timedelta(days=1)).isoformat()
check("applied", res.get("applied"), res)
check("status stays expired_member after the status sync", st == "expired_member", st)
check("the running term ends yesterday", max(t["expires_at"] for t in terms) == yday, terms)
check("every term is roster_choice remove", all(t["roster_choice"] == "remove" for t in terms))
check("every notice is stamped (no renewal or lapsed email)",
      all(t[col] for t in terms for col, _o, _l in m.NOTICE_WINDOWS))
check("the original end date is kept in notes", any("was to" in (t["notes"] or "") for t in terms))

print("undo (Kerry #2031)")
u = m.undo_end_membership(cid, ok, apply=True, db_path=DB)
with db._connect(DB) as c:
    st = c.execute("SELECT current_player_status FROM customers WHERE customer_id = ?", (cid,)).fetchone()[0]
    terms2 = [dict(r) for r in c.execute("SELECT * FROM customer_memberships WHERE customer_id = ?", (cid,))]
check("undo applied", u.get("applied"), u)
check("the running term's end date is back", max(t["expires_at"] for t in terms2) == (today + timedelta(days=265)).isoformat(), terms2)
check("roster_choice is cleared", all(t["roster_choice"] is None for t in terms2))
check("the stamps end_membership set are cleared", all(t[col] is None for t in terms2 for col, _o, _l in m.NOTICE_WINDOWS))
check("no 'ended early' note remains", not any("ended early" in (t["notes"] or "") for t in terms2), terms2)
check("status is active_member again", st == "active_member", st)

print()
if F:
    print(f"{len(F)} FAILED")
    sys.exit(1)
print("ALL PASS")
