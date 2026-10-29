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

check("Kelly is on the roster from his RSVP", 39 in roster_ids(), roster_ids())
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
check("a second I'm-in tap keeps Kelly off", 39 not in roster_ids())
wl.remove(eid, 39, apply=True, db_path=DB)
check("taking Kelly off the list puts the RSVP back", 39 in roster_ids() and
      [x["customer_id"] for x in wl.get(eid, DB)] == [18, 703])
check("bridge exists", 'cmd == "scoring-waitlist"' in open("mcp_server.py").read())

print("== the limit, the gate, offers (Kerry 10/29) ==")
from datetime import datetime as _dt
import email_parser.waitlist as W
SENTM = []
CCS = []
W._mail = lambda to, subject, html, db_path=None, who="waitlist", cc=None: (SENTM.append((to, subject)), CCS.append((to, cc))) and True
with db._connect(DB) as c:
    eid2 = c.execute("INSERT INTO events (item_name, event_date, start_time, registration_url, max_players) "
                     "VALUES ('s9.99 Cap', '2099-11-03', '17:00', 'https://www.thegolffellowship.com/product-page/s9-99-cap', 2) "
                     "RETURNING id").fetchone()[0]
    for i, cid in enumerate((87, 18)):
        c.execute("INSERT INTO items (email_uid, item_index, customer, customer_id, item_name, event_id, "
                  "transaction_status, merchant, order_date) VALUES (?, 0, 'x', ?, 's9.99 Cap', ?, 'active', "
                  "'The Golf Fellowship', '2099-10-01')", (f"cap{i}", cid, eid2))
    c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (39, 'kbarna@austin.rr.com', 1)")
    c.commit()
cap = W.capacity(eid2, DB)
check("max 2, 2 paid: full", cap["full"] and cap["paid"] == 2 and cap["open"] == 0, cap)
check("a full event's link shows the waitlist page, not the store", W.register_target(eid2, DB).get("full"))
check("the registration link we send goes through the gate",
      __import__("email_parser.event_links", fromlist=["x"]).event_url_for_message(
          {"id": eid2, "event_date": "2099-11-03", "registration_url": "https://www.thegolffellowship.com/p/x",
           "registration_url_status": "ok"})[0].endswith(f"/register/{eid2}"))
r = W.tick(now=_dt(2099, 11, 1, 9, 0), db_path=DB)
check("the event fills: one staff note to close GoDaddy",
      any("FULL" in s for _, s in SENTM) and all("@thegolffellowship.com" in t for t, _ in SENTM), SENTM)
SENTM.clear(); W.tick(now=_dt(2099, 11, 1, 9, 15), db_path=DB)
check("...only once", not any("FULL" in s for _, s in SENTM), SENTM)
W.add(eid2, 39, apply=True, db_path=DB, notify=False)
W.add(eid2, 703, apply=True, db_path=DB, notify=False)
with db._connect(DB) as c:
    c.execute("UPDATE items SET transaction_status = 'credited' WHERE email_uid = 'cap1'")
    c.commit()
SENTM.clear()
W.tick(now=_dt(2099, 11, 1, 10, 0), db_path=DB)
b = W.board(eid2, DB)
check("a spot opens: #1 is offered it, #2 waits", [r["state"] for r in b["line"]] == ["offered", "waiting"], b["line"])
check("staff are told to reopen GoDaddy for them", any("REOPEN GODADDY" in s for _, s in SENTM), SENTM)
check("member emails are held until Kerry approves the wording",
      not any("kbarna" in t for t, _ in SENTM), SENTM)
check("the held spot is not open to anyone else", W.register_target(eid2, DB).get("full"))
check("the deadline is 2 hours on (Kerry 10/29)", b["line"][0]["deadline"] == "2099-11-01 12:00", b["line"][0])
W.tick(now=_dt(2099, 11, 1, 22, 15), db_path=DB)
b = W.board(eid2, DB)
check("lapsed at night: no new offer until 7 AM", b["line"] and b["line"][0]["state"] == "waiting"
      and b["line"][0]["customer_id"] == 703, b)
W.tick(now=_dt(2099, 11, 2, 7, 5), db_path=DB)
b = W.board(eid2, DB)
check("the offer lapses: Mesa is offered next", [r["customer_id"] for r in b["line"]] == [703]
      and b["line"][0]["state"] == "offered" and b["past"][0]["state"] == "expired", b)
with db._connect(DB) as c:
    c.execute("INSERT INTO items (email_uid, item_index, customer, customer_id, item_name, event_id, "
              "transaction_status, merchant, order_date) VALUES ('cap9', 0, 'Mesa', 703, 's9.99 Cap', ?, "
              "'active', 'The Golf Fellowship', '2099-11-01')", (eid2,))
    c.commit()
SENTM.clear(); W.tick(now=_dt(2099, 11, 2, 8, 0), db_path=DB)
b = W.board(eid2, DB)
check("Mesa pays: claimed, off the line, staff told",
      not b["line"] and any(r["state"] == "claimed" for r in b["past"]) and any("claimed" in s for _, s in SENTM), b)
db.set_app_setting("waitlist_member_emails", "on", db_path=DB)
CCS.clear()
W._member({"id": eid2, "item_name": "s9.99 Cap", "chapter": "San Antonio", "event_date": "2099-11-03"},
          {"name": "Kelly Barna", "customer_id": 39}, "joined", DB, pos=1)
check("every player email copies Kerry (Kerry 10/29)",
      CCS and CCS[-1] == ("kbarna@austin.rr.com", "kerry@thegolffellowship.com"), CCS)
pv = W.preview("offered", eid2, DB)
check("a chapter event is signed by the chapter manager (Kerry 10/29)",
      "Kerry Niester" in W.render({**{"id": eid2, "item_name": "s9.99 Cap", "chapter": "San Antonio",
                                       "event_date": "2099-11-03"}}, {"name": "Kelly Barna"}, "joined", DB, pos=1)["html"])
check("a joint event is signed The Golf Fellowship",
      W.signature({"chapter": "TGF"}) == "The Golf Fellowship")
check("Austin is signed by Robert", "Robert Straiton" in W.signature({"chapter": "Austin"}))
check("the offer email names the deadline and links the store",
      "Register now" in pv["html"] and "product-page/s9-99-cap" in pv["html"], pv["subject"])
from email_parser.pairings_audit import event_pairing_audit  # noqa: F401  (import check)

print("== the page ==")
import app as _app
cl = _app.app.test_client()
with db._connect(DB) as c:
    c.execute("UPDATE items SET transaction_status = 'active' WHERE email_uid = 'cap1'")
    c.commit()
g = cl.get(f"/register/{eid2}")
check("full: the page says so and offers the waitlist", g.status_code == 200 and b"is full" in g.data
      and b"Join the waitlist" in g.data, g.status_code)
po = cl.post(f"/register/{eid2}", data={"email": "KBarna@austin.rr.com", "name": "Kelly"})
check("joining by the email on file puts Kelly on the line", b"on the waitlist" in po.data
      and W.position(W.get(eid2, DB), 39), po.data[:200])
with db._connect(DB) as c:
    c.execute("UPDATE events SET max_players = 10 WHERE id = ?", (eid2,))
    c.commit()
g2 = cl.get(f"/register/{eid2}")
check("spots open: straight on to the store", g2.status_code == 302 and "product-page/s9-99-cap" in g2.headers["Location"])
from email_parser import invitations as _inv
from datetime import date as _date
with db._connect(DB) as c:
    c.execute("UPDATE events SET max_players = 2 WHERE id = ?", (eid2,))
    c.commit()
tok = _inv.make_token(703, eid2, "in", _date(2099, 11, 3))
ci = _inv.click_in(tok, db_path=DB)
check("an I'm in on a full event goes to the waitlist page and records nothing",
      ci.get("full") and f"/register/{eid2}?t=" in ci["redirect"], ci)
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
