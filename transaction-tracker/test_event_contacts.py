"""AN EVENT'S COURSE CONTACTS FREEZE WHEN IT COMPLETES (Kerry 2026-10-28,
Event Ops #2476-3: "after an event is completed all of that hardens to that
event's contact info ... her contact would still show if we dug into the
archives for that event"). course_staff stays the standard going forward.

Run: python3 test_event_contacts.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-ec-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
from email_parser import database as db            # noqa: E402
from email_parser import event_contacts as ec      # noqa: E402
from email_parser import print_pack as pp          # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

db.init_db(DB)
with db._connect(DB) as c:
    tv = c.execute("INSERT INTO courses (name) VALUES ('Teravista Golf Club') RETURNING course_id").fetchone()[0]
    sky = c.execute("INSERT INTO customers (first_name, last_name, phone) VALUES ('Skyler', 'Morrow', '512-555-0101') "
                    "RETURNING customer_id").fetchone()[0]
    c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?, 'skyler@teravista.example', 1)", (sky,))
    gm = c.execute("INSERT INTO customers (first_name, last_name) VALUES ('Gina', 'Manager') RETURNING customer_id").fetchone()[0]
    c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?, 'gina@teravista.example', 1)", (gm,))
    c.execute("INSERT INTO course_staff (course_id, customer_id, role, is_primary, active) VALUES (?, ?, 'tgf_contact', 1, 1)", (tv, sky))
    c.execute("INSERT INTO course_staff (course_id, customer_id, role, is_primary, active) VALUES (?, ?, 'tgf_contact', 0, 1)", (tv, gm))
    past = c.execute("INSERT INTO events (item_name, event_date, course, chapter, course_id) "
                     "VALUES ('a9.29 Teravista', '2026-10-27', 'Teravista', 'Austin', ?) RETURNING id", (tv,)).fetchone()[0]
    past2 = c.execute("INSERT INTO events (item_name, event_date, course, chapter, course_id) "
                      "VALUES ('a9.25 Teravista', '2026-09-29', 'Teravista', 'Austin', ?) RETURNING id", (tv,)).fetchone()[0]
    nocourse = c.execute("INSERT INTO events (item_name, event_date) VALUES ('x9.1 Nowhere', '2026-09-01') RETURNING id").fetchone()[0]
    future = c.execute("INSERT INTO events (item_name, event_date, course, chapter, course_id) "
                       "VALUES ('a9.30 Teravista', '2099-11-03', 'Teravista', 'Austin', ?) RETURNING id", (tv,)).fetchone()[0]
    c.commit()

def ev(i):
    with db._connect(DB) as c:
        return dict(c.execute("SELECT * FROM events WHERE id = ?", (i,)).fetchone())

print("the backfill (dry run first)")
d = ec.backfill(db_path=DB)
check("dry run: two completed events with a course lack a snapshot, nothing written",
      d["dry_run"] and d["missing"] == 2 and ec.stored(past, DB) is None, d)
check("the future event and the course-less one are not in it",
      {x["event_id"] for x in d["events"]} == {past, past2})
a = ec.backfill(apply=True, db_path=DB)
s = ec.stored(past, DB)
check("apply freezes them", a["missing"] == 2 and s and len(s["contacts"]) == 2, a)
sk = next(x for x in s["contacts"] if x["customer_id"] == sky)
check("the snapshot carries name, role, email, phone, company and customer_id",
      sk["name"] == "Skyler Morrow" and sk["role"] == "tgf_contact" and sk["is_primary"]
      and sk["email"] == "skyler@teravista.example" and sk["phone"] == "512-555-0101"
      and sk["company"] == "Teravista Golf Club", sk)
check("running it again finds nothing to do", ec.backfill(apply=True, db_path=DB)["missing"] == 0)

print("the course contact changes; the archive does not")
with db._connect(DB) as c:
    c.execute("UPDATE course_staff SET active = 0 WHERE customer_id = ?", (sky,))
    new = c.execute("INSERT INTO customers (first_name, last_name) VALUES ('Nate', 'New') RETURNING customer_id").fetchone()[0]
    c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?, 'nate@teravista.example', 1)", (new,))
    c.execute("UPDATE course_staff SET is_primary = 0 WHERE course_id = ?", (tv,))
    c.execute("INSERT INTO course_staff (course_id, customer_id, role, is_primary, active) VALUES (?, ?, 'tgf_contact', 1, 1)", (tv, new))
    c.execute("UPDATE customer_emails SET email = 'skyler@othercompany.example' WHERE customer_id = ?", (sky,))
    c.commit()
r_past = pp.course_recipients_for_event(ev(past), DB)
check("the completed event still names Skyler (Kerry: 'her contact would still show')",
      r_past["ok"] and r_past["to"] == "skyler@teravista.example" and r_past.get("frozen"), r_past)
r_fut = pp.course_recipients_for_event(ev(future), DB)
check("an upcoming event reads course_staff live (the new standard)",
      r_fut["ok"] and r_fut["to"] == "nate@teravista.example" and not r_fut.get("frozen"), r_fut)
check("a frozen snapshot is never rewritten without force",
      ec.snapshot(past, apply=True, db_path=DB)["status"] == "already frozen")

print("first read freezes a completed event the backfill missed")
with db._connect(DB) as c:
    late = c.execute("INSERT INTO events (item_name, event_date, course, chapter, course_id) "
                     "VALUES ('a9.28 Teravista', '2026-10-20', 'Teravista', 'Austin', ?) RETURNING id", (tv,)).fetchone()[0]
    c.commit()
r_late = pp.course_recipients_for_event(ev(late), DB)
check("frozen on first read, from the standard at that moment",
      r_late["to"] == "nate@teravista.example" and ec.stored(late, DB)["source"] == "first_read", r_late)
check("a completed event with no course says so", not pp.course_recipients_for_event(ev(nocourse), DB)["ok"])
with db._connect(DB) as c:
    bare = c.execute("INSERT INTO courses (name) VALUES ('Bare Links') RETURNING course_id").fetchone()[0]
    bev = c.execute("INSERT INTO events (item_name, event_date, course_id) VALUES ('b9.1 Bare', '2026-10-01', ?) "
                    "RETURNING id", (bare,)).fetchone()[0]
    c.commit()
pp.course_recipients_for_event(ev(bev), DB)
check("an empty contact list is never frozen (contacts added later still show)",
      ec.stored(bev, DB) is None and ec.snapshot(bev, apply=True, db_path=DB)["status"] == "no contacts on file")

src = open("mcp_server.py").read()
check("bridge scoring-event-contacts exists", 'cmd == "scoring-event-contacts"' in src)
check("the daily + boot backfill is scheduled", 'id="event_contacts_backfill"' in open("app.py").read()
      and 'id="event_contacts_backfill_boot"' in open("app.py").read())
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
