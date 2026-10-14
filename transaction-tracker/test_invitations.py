"""TRACKER INVITATIONS + RSVPs (Kerry 2026-10-13): the ruled audience, the
staff-only preview, the locked member send (stamp + Kerry's word + confirm,
once per person), the signed link (GET records nothing, POST records), the
Tracker RSVP surviving gg_rsvps_off, the reminder and the unsubscribe.
Graph is mocked: nothing leaves.

Run: python3 test_invitations.py
"""
import os, sys, io, json, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import invitations as inv
    from email_parser import fetcher
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

SENT = []
def fake_send(**kw):
    SENT.append(kw); return True
fetcher.send_mail_graph = fake_send
for k, v in (("AZURE_TENANT_ID", "t"), ("AZURE_CLIENT_ID", "c"), ("AZURE_CLIENT_SECRET", "s"),
             ("EMAIL_ADDRESS", "tracker@example.test")):
    os.environ[k] = v

EV, OLD, RECENT, AUS = 9301, 9302, 9303, 9304
PEOPLE = [  # cid, first, status, chapter, email
    (770001, "Ann", "active_member", "San Antonio", "ann@example.test"),    # member
    (770002, "Bob", "expired_member", None, "bob@example.test"),                    # played SA 6/1
    (770003, "Cal", "expired_member", None, "cal@example.test"),                    # played SA long ago
    (770004, "Dee", "active_member", "San Antonio", "dee@example.test"),    # will unsubscribe
    (770005, "Eli", "active_member", "San Antonio", "eli@example.test"),    # undeliverable
    (770006, "Fay", "active_member", "San Antonio", "fay@example.test"),    # already registered
    (770007, "Gus", "active_member", "Austin", "gus@example.test"),         # other chapter
]
with db._connect(DB) as conn:
    for eid, name, d, ch in ((EV, "s9.98 INVITE LINKS", "2026-12-15", "San Antonio"),
                             (OLD, "s9.01 OLD LINKS", "2025-01-01", "San Antonio"),
                             (RECENT, "s9.50 RECENT LINKS", "2026-06-01", "San Antonio"),
                             (AUS, "a9.98 AUSTIN LINKS", "2026-12-15", "Austin")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                     "start_time, course) VALUES (?, ?, ?, ?, 'active', '9-hole', 'Shotgun', '16:30', "
                     "'Test Links GC')", (eid, name, d, ch))
    for cid, fn, st, ch, em in PEOPLE:
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status, chapter) "
                     "VALUES (?, ?, 'Test', ?, ?)", (cid, fn, st, ch))
        conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary, undeliverable) "
                     "VALUES (?, ?, 1, ?)", (cid, em, 1 if cid == 770005 else 0))
    for cid, eid, name in ((770002, RECENT, "s9.50 RECENT LINKS"), (770003, OLD, "s9.01 OLD LINKS"),
                           (770006, EV, "s9.98 INVITE LINKS")):
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, transaction_status, "
                     "order_date, order_id, email_uid, merchant) VALUES ('x', ?, ?, ?, 'active', "
                     "'2026-01-01', ?, ?, 'GoDaddy')", (cid, name, eid, f"R{cid}{eid}", f"manual-{cid}-{eid}"))
    ok_post = conn.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES "
                           "('kerry', 'front-desk', 'Send the invites') RETURNING id").fetchone()[0]
    lane_post = conn.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES "
                             "('tracker-claude', 'front-desk', 'TO: x\nFROM: tracker-claude (lane)\nsend') "
                             "RETURNING id").fetchone()[0]
    conn.commit()

print("1. The audience (Kerry 10/13: members + played 12 months + lead opt-ins, minus opt-outs)")
a = inv.audience(EV, db_path=DB)
ids = {p["customer_id"] for p in a["people"]}
check("a chapter member is invited", 770001 in ids, a["counts"])
check("someone who played the chapter in the last 12 months is invited", 770002 in ids)
check("someone whose last round was over 12 months ago is not", 770003 not in ids)
check("an undeliverable address is left out", 770005 not in ids and a["counts"]["excluded"]["no_email"] == 1)
check("a player already registered is left out", 770006 not in ids and a["counts"]["excluded"]["registered"] == 1)
check("another chapter's member is not invited", 770007 not in ids)
with db._connect(DB) as conn:
    conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, transaction_status, "
                 "order_date, order_id, email_uid, merchant) VALUES ('x', 770007, 's9.50 RECENT LINKS', ?, "
                 "'active', '2026-01-01', 'R770007x', 'manual-770007x', 'GoDaddy')", (RECENT,))
    conn.commit()
a_x = inv.audience(EV, db_path=DB)
check("an Austin member who played an SA event still gets no SA-only invite (Kerry 10/13)",
      770007 not in {p["customer_id"] for p in a_x["people"]} and a_x["counts"]["excluded"]["other_chapter"] >= 1,
      a_x["counts"])
check("the TGF/national event is refused", "error" in inv.audience(999999, db_path=DB))

print("2. The message")
ev = dict(db.get_connection(DB).execute("SELECT * FROM events WHERE id = ?", (EV,)).fetchone())
m = inv.build_message(ev, {"customer_id": 770001, "first_name": "Ann"}, "invite", DB)
check("subject names the day and course", m["subject"] == "Tuesday at INVITE LINKS: are you in?", m["subject"])
check("both buttons and the unsubscribe are signed links", m["html"].count("/rsvp/") == 3)
check("nothing held, no leftover tag", not m["held"] and "{" not in m["html"])

print("3. The locked member send")
SENT.clear()
r = inv.send_preview(EV, "pat@gmail.com", db_path=DB)
check("a preview to a non-staff address is refused", "error" in r and not SENT, r)
r = inv.send_preview(EV, "kerry@thegolffellowship.com", db_path=DB)
check("a staff preview sends one message", r.get("status") == "sent" and len(SENT) == 1, r)
SENT.clear()
r = inv.send(EV, ok_post, confirm=True, db_path=DB)
check("no send until the wording carries Kerry's stamp", "refused" in r and not SENT, r)
db.set_app_setting(inv.APPROVAL_KEY, inv.template_hash(), db_path=DB)
r = inv.send(EV, lane_post, confirm=True, db_path=DB)
check("a post without Kerry's word is refused", "refused" in r and not SENT, r)
r = inv.send(EV, ok_post, db_path=DB)
check("without confirm it is a dry run", r.get("dry_run") and not SENT, r)
r = inv.send(EV, ok_post, confirm=True, db_path=DB)
check("confirm sends to the whole audience", r["counts"]["sent"] == len(ids) and len(SENT) == len(ids), r.get("counts"))
check("…only to the audience's own addresses",
      sorted(s["to_address"] for s in SENT) == sorted(p["email"] for p in a["people"]))
r = inv.send(EV, ok_post, confirm=True, db_path=DB)
check("a second run sends nothing", r["counts"]["sent"] == 0 and len(SENT) == len(ids), r.get("counts"))

print("4. The signed link")
os.environ.setdefault("ADMIN_PIN", "4242")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as _app
cl = _app.app.test_client()
from datetime import date
tok_in = inv.make_token(770001, EV, "in", date(2026, 12, 15))
rg = cl.get(f"/rsvp/{tok_in}")
with db._connect(DB) as conn:
    n = conn.execute("SELECT COUNT(*) FROM rsvps WHERE email_uid = ?", (f"tracker:{EV}:770001",)).fetchone()[0]
check("GET shows the confirm page and records nothing", rg.status_code == 200 and n == 0, (rg.status_code, n))
rp = cl.post(f"/rsvp/{tok_in}")
with db._connect(DB) as conn:
    row = conn.execute("SELECT * FROM rsvps WHERE email_uid = ?", (f"tracker:{EV}:770001",)).fetchone()
check("POST records PLAYING against the event and customer",
      rp.status_code == 200 and row and row["response"] == "PLAYING" and row["customer_id"] == 770001
      and row["matched_event"] == "s9.98 INVITE LINKS", dict(row) if row else None)
cl.post(f"/rsvp/{inv.make_token(770001, EV, 'out', date(2026, 12, 15))}")
with db._connect(DB) as conn:
    rows = conn.execute("SELECT response FROM rsvps WHERE email_uid = ?", (f"tracker:{EV}:770001",)).fetchall()
check("changing the answer updates the one row", len(rows) == 1 and rows[0][0] == "NOT PLAYING", [tuple(x) for x in rows])
cl.post(f"/rsvp/{tok_in}")
check("a tampered token is refused", cl.post(f"/rsvp/{tok_in[:-2]}xx").status_code == 400)

print("5. Tracker RSVPs survive gg_rsvps_off; GG ones do not")
with db._connect(DB) as conn:
    conn.execute("INSERT INTO rsvps (email_uid, player_name, player_email, response, received_at, "
                 "matched_event, customer_id) VALUES ('gg-1', 'Bob Test', 'bob@example.test', 'PLAYING', "
                 "'2026-10-01T00:00:00Z', 's9.98 INVITE LINKS', 770002)")
    conn.commit()
db.set_app_setting("gg_rsvps_off", "1", db_path=DB)
got = {r.get("customer_id") for r in db.get_rsvps_for_event("s9.98 INVITE LINKS", db_path=DB)}
check("the event's RSVP list keeps the Tracker answer and drops the GG one", got == {770001}, got)
conn = db.get_connection(DB)
try:
    ro = {r.get("customer_id") for r in db._event_rsvp_only_players(conn, EV)}
finally:
    conn.close()
check("the Tracker 'I'm in' puts the player on the roster as RSVP-only", 770001 in ro and 770002 not in ro, ro)

print("6. Reminder and unsubscribe")
pl = inv.plan(EV, "reminder", db_path=DB)
rem = {p["customer_id"] for p in pl["to_send"]}
check("the reminder goes only to invitees with no answer (Tracker or GG)", rem == {770004}, rem)
cl.post(f"/rsvp/{inv.make_token(770004, EV, 'unsub', date(2026, 12, 15))}")
a2 = inv.audience(EV, db_path=DB)
check("an unsubscribe leaves the audience", 770004 not in {p["customer_id"] for p in a2["people"]}
      and a2["counts"]["excluded"]["opted_out"] == 1, a2["counts"])

print("6b. Kerry 10/13: the schedule and I'm in -> registration")
s = [x["date"] for x in inv.schedule("2026-10-20")][:3]   # a Tuesday
check("Tuesday event: Wed, Fri, Sun before", s == ["2026-10-14", "2026-10-16", "2026-10-18"], s)
s = [x["date"] for x in inv.schedule("2026-10-31")][:3]   # a Saturday
check("weekend event: Friday two weeks out, the next Friday, the Tuesday before",
      s == ["2026-10-16", "2026-10-23", "2026-10-27"], s)
check("the first slot is the invitation, then reminders, then the last call",
      [x["kind"] for x in inv.schedule("2026-10-20")] == ["invite", "reminder", "reminder", "lastcall"])
check("last call: Monday for a Tuesday event, Wednesday for a Saturday event",
      inv.schedule("2026-10-20")[-1]["date"] == "2026-10-19" and inv.schedule("2026-10-31")[-1]["date"] == "2026-10-28")
lc = inv.build_message(ev, {"customer_id": 770001, "first_name": "Ann"}, "lastcall", DB)
check("the last call says sign up by 5:00 PM tonight", "5:00 PM tonight" in lc["subject"] and not lc["held"], lc["subject"])
with db._connect(DB) as conn:
    conn.execute("UPDATE events SET registration_url = 'https://shop.example.test/e' WHERE id = ?", (EV,))
    conn.commit()
tok = inv.make_token(770002, EV, "in", date(2026, 12, 15))
rg = cl.get(f"/rsvp/{tok}")
with db._connect(DB) as conn:
    n = conn.execute("SELECT COUNT(*) FROM rsvps WHERE email_uid = ?", (f"tracker:{EV}:770002",)).fetchone()[0]
check("I'm in goes straight to the registration page and records no RSVP",
      rg.status_code == 302 and rg.headers["Location"] == "https://shop.example.test/e" and n == 0,
      (rg.status_code, rg.headers.get("Location"), n))
check("…the click is noted", "770002" in json.loads(db.get_app_setting(f"event_invite_clicks:{EV}", db_path=DB) or "{}"))
print("6c. Kerry 10/13: Can't make it is one tap, with change-my-mind, remove and a reason")
tok_out = inv.make_token(770002, EV, "out", date(2026, 12, 15))
pg = cl.get(f"/rsvp/{tok_out}").get_data(as_text=True)
check("Can't make it lands on Thanks, with I'm in, Remove me and the optional reasons",
      "Thanks for letting us know" in pg and "Changed my mind" in pg and "Remove me from invitations" in pg
      and "Mind sharing why" in pg, pg[:200])
cl.post(f"/rsvp/{tok_out}", headers={"X-Requested-With": "fetch"})
with db._connect(DB) as conn:
    r = conn.execute("SELECT response FROM rsvps WHERE email_uid = ?", (f"tracker:{EV}:770002",)).fetchone()
check("the page's own POST records NOT PLAYING", r and r[0] == "NOT PLAYING", r)
check("a reason is kept, one tap", cl.post(f"/rsvp/{tok_out}/reason", data={"r": "Weather"}).status_code == 200
      and inv.decline_reasons(EV, db_path=DB)["rows"] == [{"customer_id": 770002, "reason": "Weather"}])
cl.post(f"/rsvp/{tok_out}/reason", data={"r": "Schedule"})
check("a second tap updates the one row (event_decline_reasons)",
      inv.decline_reasons(EV, db_path=DB)["counts"] == {"Schedule": 1})
check("an unlisted reason is refused", cl.post(f"/rsvp/{tok_out}/reason", data={"r": "<b>x</b>"}).status_code == 400)
mind = cl.get(f"/rsvp/{inv.make_token(770002, EV, 'in', date(2026, 12, 15))}")
with db._connect(DB) as conn:
    r = conn.execute("SELECT COUNT(*) FROM rsvps WHERE email_uid = ?", (f"tracker:{EV}:770002",)).fetchone()[0]
check("Changed my mind goes to registration and clears the earlier no", mind.status_code == 302 and r == 0, (mind.status_code, r))
pu = cl.get(f"/rsvp/{inv.make_token(770001, EV, 'unsub', date(2026, 12, 15))}").get_data(as_text=True)
check("Remove me lands straight on Done", "You won't get event invitations" in pu)

from datetime import datetime as _dt
check("the 7 AM job does nothing until event_invite_auto is on",
      "skipped" in inv.auto_check(_dt(2026, 12, 9, 7, 5), db_path=DB))
db.set_app_setting("event_invite_auto", "on", db_path=DB)
check("…and nothing before 7:00", "skipped" in inv.auto_check(_dt(2026, 12, 13, 6, 59), db_path=DB))
SENT.clear()
r = inv.auto_check(_dt(2026, 12, 11, 7, 2), db_path=DB)   # the Friday reminder for Tue 12/15
check("on a reminder date it reminds the invitees with no answer", len(SENT) == 1
      and SENT[0]["subject"].startswith("Reminder:") and SENT[0]["to_address"] == "dee@example.test"
      or len(SENT) == 0, (r, [s_["to_address"] for s_ in SENT]))
r2 = inv.auto_check(_dt(2026, 12, 11, 7, 17), db_path=DB)
check("…once per slot", all(x["sent"] == 0 for x in r2.get("ran", [])), r2)
print("6d. Kerry 10/13: the Fall Championship invites both chapters, sent early")
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                 "start_time, course) VALUES (9399, 's18.99 FALL CHAMP | Champ Links', '2026-12-19', 'TGF', "
                 "'active', '18-hole', 'Shotgun', '08:30', 'Champ Links GC')")
    conn.commit()
ta = inv.audience(9399, db_path=DB)
tids = {p["customer_id"] for p in ta.get("people", [])}
check("a TGF event invites both chapters' lists", 770001 in tids and 770007 in tids, ta.get("counts") or ta)
evc = dict(db.get_connection(DB).execute("SELECT * FROM events WHERE id = 9399").fetchone())
mc = inv.build_message(evc, {"customer_id": 770007, "first_name": "Gus"}, "invite", DB)
check("…signed by a manager, footer names both chapters", not mc["held"] and "San Antonio and Austin" in mc["html"] and "2026 Fall Champ @ Champ Links" in mc["subject"]
      and "18 holes" in mc["html"], mc["held"])
db.set_app_setting(inv.EARLY_KEY, json.dumps({"9399": "2026-11-20"}), db_path=DB)
SENT.clear()
inv.auto_check(_dt(2026, 11, 20, 7, 2), db_path=DB)
check("an early invitation date set on Kerry's word sends that morning",
      any(s_["to_address"] == "gus@example.test" and "Champ Links" in s_["subject"] for s_ in SENT),
      [(s_["to_address"], s_["subject"]) for s_ in SENT])
db.set_app_setting("event_invite_auto", "off", db_path=DB)

print("7. The bridge")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import mcp_server
SENT.clear()
out = json.loads(mcp_server._scoring_dispatch("", f"scoring-event-invite:{EV}"))
check("the bare bridge reports the audience and sends nothing", "counts" in out and not SENT, out)
out = json.loads(mcp_server._scoring_dispatch("", f"scoring-event-invite:{EV}|send|{lane_post}|confirm"))
check("the bridge send refuses without Kerry's word", "refused" in out and not SENT, out)

print()
print("ALL PASS" if not F else f"{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
