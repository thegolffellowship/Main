"""THE EVENT WAITLIST (Kerry 2026-10-29: "Kelly BARNA, Myself and Michael Mesa
need to go on a waitlist for Saturday ... Kelly needs to come off the active
roster."). An RSVP-only player put on the list leaves the roster and a second
"I'm in" can't put them back; a paid row is untouched; order is kept.

Run: python3 test_waitlist.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-wl-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
from email_parser import database as db        # noqa: E402
from email_parser import waitlist as wl        # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

db.init_db(DB)
NAME = "s18.12 FALL CHAMPIONSHIP | Kissing Tree"
with db._connect(DB) as c:
    for cid, f, l in ((39, "Kelly", "Barna"), (18, "Kerry", "Niester"), (703, "Michael", "Mesa"), (87, "Adam", "Baker")):
        c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, ?)", (cid, f, l))
    eid = c.execute("INSERT INTO events (item_name, event_date) VALUES (?, '2099-10-31')", (NAME,)).lastrowid
    c.execute("INSERT INTO items (email_uid, item_index, customer, customer_id, item_name, event_id, "
              "transaction_status, customer_email, merchant, order_date) VALUES ('o1', 0, 'Adam Baker', 87, ?, ?, 'active', 'ab@x.com', 'The Golf Fellowship', '2099-10-01')",
              (NAME, eid))
    c.execute("INSERT INTO rsvps (email_uid, player_name, player_email, event_identifier, event_date, response, received_at, "
              "matched_event, customer_id) VALUES ('tracker:1:39', 'Kelly Barna', 'kbarna@austin.rr.com', ?, "
              "'2099-10-31', 'PLAYING', '2099-10-29', ?, 39)", (NAME, NAME))
    c.commit()

def roster_ids():
    with db._connect(DB) as c:
        return {r.get("customer_id") for r in db._event_rsvp_only_players(c, eid)}

check("Kelly is on the roster from her RSVP", 39 in roster_ids(), roster_ids())
dry = wl.add(eid, 39, note="over 32", apply=False, db_path=DB)
check("dry run changes nothing", dry["dry_run"] and 39 in roster_ids() and wl.get(eid, DB) == [], dry)
r = wl.add(eid, 39, note="over 32", apply=True, db_path=DB)
check("Kelly is #1 and off the roster", r["position"] == 1 and 39 not in roster_ids(), (r, roster_ids()))
wl.add(eid, 18, apply=True, db_path=DB)
wl.add(eid, 703, apply=True, db_path=DB)
check("order kept: Kelly, Kerry, Mesa", [x["customer_id"] for x in wl.get(eid, DB)] == [39, 18, 703])
check("adding twice keeps the place", wl.add(eid, 39, apply=True, db_path=DB).get("position") == 1)
p = wl.add(eid, 87, apply=False, db_path=DB)
check("a paid registration is reported, never touched", p["paid_registration"] and p["note_paid"], p)
with db._connect(DB) as c:
    c.execute("UPDATE rsvps SET received_at = '2099-10-30' WHERE email_uid = 'tracker:1:39'")
    c.commit()
check("a second I'm-in tap keeps her off", 39 not in roster_ids())
wl.remove(eid, 39, apply=True, db_path=DB)
check("taking her off the list puts the RSVP back", 39 in roster_ids() and
      [x["customer_id"] for x in wl.get(eid, DB)] == [18, 703])
check("bridge exists", 'cmd == "scoring-waitlist"' in open("mcp_server.py").read())
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
