"""THE 7:00 PM TEE-TIMES EMAIL, three versions (CMO #2076 copy, #2101 build).
Graph is mocked: nothing leaves.

Covers: held on blanks; once per event + person; locked until each wording
is stamped AND the job dial is on; course pack line and manager closing line
by what is on file and the weekday; the spots-open dial; the bridge.

Run: python3 test_teetimes_email.py
"""
import contextlib
import io
import json
import logging
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import fetcher
    from email_parser import teetimes_email as tt
    from email_parser import course_staff as cs
    db.init_db(DB)

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


SENT = []


def fake_send(**kw):
    SENT.append(kw)
    return True


fetcher.send_mail_graph = fake_send
for k, v in (("AZURE_TENANT_ID", "t"), ("AZURE_CLIENT_ID", "c"), ("AZURE_CLIENT_SECRET", "s"),
             ("EMAIL_ADDRESS", "tracker@example.test")):
    os.environ[k] = v

# Tue 2026-10-27 (weekday) and Sat 2026-10-31 (weekend). The gg_untether
# default (2026-10-07) puts both in the Tracker era.
EV, EV_WE = 9301, 9302
PEOPLE = [(880101, "Ann", "Able", "ann@example.test"),
          (880102, "Bob", "Baker", "bob@example.test"),
          (880103, "Cal", "Cole", "cal@example.test"),
          (880104, "Dee", "Dunn", None),                 # no email: held
          (880105, "Eve", "East", "eve@example.test")]   # field of 5: 3 open
LEAD = (880199, "Lee", "Lead", "lee@example.test")       # RSVP'd I'm in, not paid
with db._connect(DB) as conn:
    conn.execute("INSERT INTO courses (course_id, name) VALUES (77, 'Test Links GC')")
    for eid, name, d in ((EV, "s9.27 TEST LINKS", "2026-10-27"), (EV_WE, "s18.31 TEST LINKS", "2026-10-31")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                     "start_time, course, course_id, registration_url) VALUES (?, ?, ?, 'San Antonio', "
                     "'active', '9-hole', 'Tee Times', '15:40', 'Test Links GC', 77, "
                     "'https://shop.example.test/reg')", (eid, name, d))
    for cid, fn, ln, em in PEOPLE + [LEAD]:
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
                     "VALUES (?,?,?,'active_member')", (cid, fn, ln))
        if em:
            conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?,?,1)", (cid, em))
    for cid, fn, ln, em in PEOPLE:
        for eid, name in ((EV, "s9.27 TEST LINKS"), (EV_WE, "s18.31 TEST LINKS")):
            conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, tee_choice, "
                         "side_games, transaction_status, order_date, order_id, email_uid, merchant) "
                         "VALUES (?, ?, ?, ?, '9', '50-64', 'NONE', 'active', '2026-10-20', ?, ?, 'GoDaddy')",
                         (f"{fn} {ln}", cid, name, eid, f"R{cid}{eid}", f"manual-{cid}-{eid}"))
    conn.execute("INSERT INTO rsvps (email_uid, player_name, player_email, event_identifier, event_date, "
                 "response, received_at, matched_event, customer_id) VALUES (?, 'Lee Lead', ?, ?, "
                 "'2026-10-27', 'PLAYING', '2026-10-25T12:00:00Z', ?, ?)",
                 (f"tracker:{EV}:{LEAD[0]}", LEAD[3], "s9.27 TEST LINKS", "s9.27 TEST LINKS", LEAD[0]))
    conn.commit()
GROUPS = {"9": [
    {"group_num": 1, "slot_label": "3:40 PM", "players": [
        {"name": "Ann Able", "cart_pos": 1, "customer_id": 880101},
        {"name": "Bob Baker", "cart_pos": 2, "customer_id": 880102},
        {"name": "Cal Cole", "cart_pos": 3, "customer_id": 880103}]},
    {"group_num": 2, "slot_label": "3:50 PM", "players": [
        {"name": "Dee Dunn", "cart_pos": 1, "customer_id": 880104},
        {"name": "Eve East", "cart_pos": 2, "customer_id": 880105}]}]}
db.save_event_pairings(EV, GROUPS, db_path=DB)
db.save_event_pairings(EV_WE, GROUPS, db_path=DB)


def by(built, version):
    return [m for m in built["messages"] if m["version"] == version]


print("1. The templates are seeded; nothing is approved; the dials are off")
appr = tt.approval_state(DB)
check("three templates seeded with a hash each",
      all(appr[v]["template_hash"] for v in tt.VERSIONS), appr)
check("no version is approved out of the box", not any(appr[v]["approved"] for v in tt.VERSIONS))
d = tt.dials(DB)
check("job dial and spots dial default OFF", d == {tt.AUTO_DIAL: "off", tt.SPOTS_DIAL: "off"}, d)
for v in tt.VERSIONS:
    print(f"     {tt.TEMPLATES[v]}: {appr[v]['template_hash']}  ({tt.APPROVAL_KEYS[v]})")

print("2. No mailing address: the player version sends without its footer (Kerry 10/19)")
b = tt.build(EV, db_path=DB)
held_p = [h for h in b["held"] if h["version"] == "player"]
check("every player with an email is ready, the footer line dropped",
      len(by(b, "player")) == 4 and not any("{mailing_address}" in h["reason"] for h in held_p)
      and not any("The Golf Fellowship &middot;" in m["html"] for m in by(b, "player")), held_p)
check("the player with no email is held for that", any(h["customer_id"] == 880104 and "no email" in h["reason"]
                                                       for h in held_p))
db.set_app_setting(tt.MAILING_ADDRESS_KEY, "PO Box 1, San Antonio, TX 78201", db_path=DB)
b = tt.build(EV, db_path=DB)
check("with the address on file four players are ready", len(by(b, "player")) == 4, b["counts"])
m = by(b, "player")[0]
check("tee sheet: header, cart pairs together, preliminary line, member tee sheet link",
      "Test Links GC" in m["html"] and "Ann Able &amp; Bob Baker" in m["html"]
      and tt.PRELIM_LINE in m["html"] and f"/member/teesheet/{EV}" in m["html"]
      and "First tee 3:40 PM" in m["html"], m["text"][:400])
check("the Event Info line says 6:00 AM (Kerry 10/26), never 7:00 AM",
      "comes at 6:00 AM tomorrow" in m["html"] and "7:00 AM" not in m["html"], m["text"][-300:])
check("no money, phone numbers or emails in the tee sheet",
      "$" not in m["text"] and "@" not in m["text"].replace(m["email"], ""), m["text"])
check("no registered player sees the spots box", all(not x["spots_box"] for x in by(b, "player"))
      and "spots still open" not in m["html"])
print("3. Course and manager lines by what is on file")
check("no course contact: the course version is skipped, not held",
      not by(b, "course") and any(s["version"] == "course" for s in b["skipped"]))
mg = by(b, "manager")
check("no contact: the manager is told to print, with the Add course contact link",
      len(mg) == 1 and "Please print them" in mg[0]["html"] and "/courses?course=77" in mg[0]["html"]
      and "come to you at noon tomorrow" in mg[0]["html"], mg and mg[0]["text"])
cs.save_staff(77, name="Chris Lopez", email="chris@course.example.test", role="tgf_contact",
              is_primary=True, apply=True, db_path=DB)
cs.save_staff(77, name="Alec Cech", email="alec@course.example.test", role="tgf_contact",
              is_primary=False, apply=True, db_path=DB)
b = tt.build(EV, db_path=DB)
c = by(b, "course")
check("course version: To the primary, CC the other TGF contact",
      len(c) == 1 and c[0]["email"] == "chris@course.example.test"
      and c[0]["cc"] == ["alec@course.example.test"] and c[0]["customer_id"], c)
check("weekday pack line: will arrive at noon tomorrow", tt.PACK_LINE["weekday"] in c[0]["html"])
mg = by(b, "manager")[0]
check("contact on file: the manager need not print, no Add contact link",
      "You don't need to print anything" in mg["html"] and "Add course contact" not in mg["html"])
# A leftover {tag} in an edited template holds.
with db._connect(DB) as conn:
    conn.execute("UPDATE message_templates SET html_body = html_body || '<p>{oops}</p>' "
                 "WHERE name = ?", (tt.TEMPLATES["course"],))
    conn.commit()
b2 = tt.build(EV, db_path=DB)
check("a leftover {tag} holds that message", not by(b2, "course")
      and any(h["version"] == "course" and "{oops}" in h["reason"] for h in b2["held"]), b2["held"])
with db._connect(DB) as conn:
    conn.execute("UPDATE message_templates SET html_body = replace(html_body, '<p>{oops}</p>', '') "
                 "WHERE name = ?", (tt.TEMPLATES["course"],))
    conn.commit()

bw = tt.build(EV_WE, db_path=DB)
check("weekend pack line: were sent at noon today", tt.PACK_LINE["weekend"] in by(bw, "course")[0]["html"])
check("weekend manager line in the past tense", "got the print packs at noon today" in by(bw, "manager")[0]["html"])

print("4. Locked until stamped AND the dial is on; once per person")
SENT.clear()
r = tt.auto_check(now=datetime(2026, 10, 26, 19, 0), db_path=DB)
check("dial off: the job does nothing", r == {"status": "off"} and not SENT, r)
db.set_app_setting(tt.AUTO_DIAL, "on", db_path=DB)
r = tt.auto_check(now=datetime(2026, 10, 26, 18, 45), db_path=DB)
check("6:45 PM, nobody approved: waits for approval or 7 PM (Kerry 10/19)",
      "approval or 7 PM" in (r["events"].get(EV, {}).get("skipped") or "") and not SENT, r)
check("4:45 PM: before the review window, nothing",
      tt.auto_check(now=datetime(2026, 10, 26, 16, 45), db_path=DB).get("status") == "not yet" and not SENT)
r = tt.auto_check(now=datetime(2026, 10, 26, 19, 0), db_path=DB)
res = r["events"].get(EV) or {}
check("dial on but no stamp: every version locked, nothing sent",
      not SENT and len(res.get("locked", [])) == 6, res)
check("the weekend event (not tomorrow) is not touched", EV_WE not in r["events"], r["events"].keys())
appr = tt.approval_state(DB)
db.set_app_setting(tt.APPROVAL_KEYS["course"], appr["course"]["template_hash"], db_path=DB)
r = tt.auto_check(now=datetime(2026, 10, 26, 19, 0), db_path=DB)
check("only the stamped version (course) goes; To + CC as built",
      len(SENT) == 1 and SENT[0]["to_address"] == "chris@course.example.test"
      and SENT[0]["cc_address"] == "alec@course.example.test", SENT)
for v in ("player", "manager"):
    db.set_app_setting(tt.APPROVAL_KEYS[v], appr[v]["template_hash"], db_path=DB)
SENT.clear()
r = tt.auto_check(now=datetime(2026, 10, 26, 19, 15), db_path=DB)
to = sorted(s["to_address"] for s in SENT)
check("then the players and the manager go; the course is not sent twice",
      to == sorted(["ann@example.test", "bob@example.test", "cal@example.test", "eve@example.test",
                    "kerry@thegolffellowship.com"]), to)
mgr_mail = next(s for s in SENT if s["to_address"] == "kerry@thegolffellowship.com")
check("the manager's line says what went", "This went to the players and the course" in mgr_mail["html_body"])
SENT.clear()
r = tt.auto_check(now=datetime(2026, 10, 26, 19, 30), db_path=DB)
check("a later run sends nobody twice", not SENT, SENT)
with db._connect(DB) as conn:
    rows = conn.execute("SELECT event_id, customer_id, sent_by FROM message_log "
                        "WHERE sent_by LIKE 'teetimes_%' AND sent_by <> 'teetimes_email'").fetchall()
check("every send logged with event_id and customer_id",
      len(rows) == 6 and all(x[0] == EV and x[1] for x in rows), [tuple(x) for x in rows])
# 10/26 5:16 PM: the approval and the job delivered the same approved sheet
# at once and every Silverhorn email went twice. Two senders racing now send
# each message exactly once.
import threading, time as _time
key = tt.SENT_KEY.format(event_id=EV)
with db._connect(DB) as conn:
    conn.execute("DELETE FROM app_settings WHERE key = ? OR key LIKE ?", (key, f"teetimes_claim:{EV}:%"))
    conn.commit()
SENT.clear()
def slow_send(**kw):
    _time.sleep(0.05)
    SENT.append(kw)
    return True
fetcher.send_mail_graph = slow_send
ths = [threading.Thread(target=tt._deliver, args=(EV, DB), kwargs={"now": datetime(2026, 10, 26, 19, 0)})
       for _ in range(2)]
[t.start() for t in ths]
[t.join() for t in ths]
fetcher.send_mail_graph = fake_send
to = sorted(s["to_address"] for s in SENT)
check("two senders at once: each email goes exactly once (10/26 double send)",
      to == sorted(["ann@example.test", "bob@example.test", "cal@example.test", "eve@example.test",
                    "kerry@thegolffellowship.com", "chris@course.example.test"]), to)
check("and the sent map records all six", len(tt._sent(EV, DB)) == 6, tt._sent(EV, DB))
SENT.clear()
fetcher.send_mail_graph = lambda **kw: False
with db._connect(DB) as conn:
    conn.execute("DELETE FROM app_settings WHERE key = ? OR key LIKE ?", (key, f"teetimes_claim:{EV}:%"))
    conn.commit()
tt._deliver(EV, DB, now=datetime(2026, 10, 26, 19, 0))
fetcher.send_mail_graph = fake_send
tt._deliver(EV, DB, now=datetime(2026, 10, 26, 19, 15))
check("a failed send gives its claim back, so the next run sends it", len(SENT) == 6, len(SENT))
# An edit to the wording voids the stamp.
with db._connect(DB) as conn:
    conn.execute("UPDATE message_templates SET subject = subject || '!' WHERE name = ?", (tt.TEMPLATES["player"],))
    conn.commit()
check("editing a wording voids its stamp", not tt.approval_state(DB)["player"]["approved"])
with db._connect(DB) as conn:
    conn.execute("UPDATE message_templates SET subject = rtrim(subject, '!') WHERE name = ?", (tt.TEMPLATES["player"],))
    conn.commit()
check("restoring it restores the stamp", tt.approval_state(DB)["player"]["approved"])

print("5. The spots-open dial")
b = tt.build(EV, db_path=DB)
check("field 5 leaves 3 open seats (lock rule)", b["field"] == 5 and b["spots_left"] == 3, (b["field"], b["spots_left"]))
check("lock rule: 8 full, 9 leaves 3, 11 leaves 1",
      tt.spots_left(8) == 0 and tt.spots_left(9) == 3 and tt.spots_left(11) == 1)
check("dial off: the unpaid I'm-in gets nothing", not any(x["customer_id"] == LEAD[0] for x in b["messages"]))
db.set_app_setting(tt.SPOTS_DIAL, "rsvp_in", db_path=DB)
b = tt.build(EV, db_path=DB)
lee = [x for x in b["messages"] if x["customer_id"] == LEAD[0]]
check("dial rsvp_in: the unpaid I'm-in gets the sheet WITH the box",
      len(lee) == 1 and lee[0]["spots_box"] and "There are 3 spots still open" in lee[0]["html"]
      and "/rsvp/" in lee[0]["html"], lee and lee[0]["text"])
check("…the Register link goes through the scanner filter (/rsvp/<token>, not the shop URL)",
      lee and "shop.example.test" not in lee[0]["html"])
check("…and registered players still never see it",
      all(not x["spots_box"] for x in b["messages"] if x["version"] == "player" and x["customer_id"] != LEAD[0]))
# Full field: no box for anyone.
with db._connect(DB) as conn:
    for cid in (880106, 880107, 880108):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, 'X', ?)", (cid, f"P{cid}"))
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, transaction_status, "
                     "order_date, order_id, email_uid, merchant) VALUES (?, ?, 's9.27 TEST LINKS', ?, '9', "
                     "'active', '2026-10-20', ?, ?, 'GoDaddy')", (f"X P{cid}", cid, EV, f"R{cid}", f"manual-{cid}"))
    conn.commit()
b = tt.build(EV, db_path=DB)
check("event full (8): spots 0 and no spots-box message",
      b["spots_left"] == 0 and not any(x.get("spots_box") for x in b["messages"]), b["spots_left"])

print("6. The bridge")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import mcp_server
SENT.clear()
out = json.loads(mcp_server._scoring_dispatch("", f"scoring-teetimes-email:{EV}"))
check("dry bridge: per-recipient ready/held, hashes, dials; sends nothing",
      "ready" in out and "held" in out and "approvals" in out and "dials" in out and not SENT, list(out))
out = json.loads(mcp_server._scoring_dispatch("", f"scoring-teetimes-email:{EV}|preview|pat@gmail.com"))
check("preview refuses a non-staff address", "error" in out and not SENT, out)
out = json.loads(mcp_server._scoring_dispatch("", f"scoring-teetimes-email:{EV}|preview"))
check("preview goes to staff only, one message",
      out.get("status") == "sent" and len(SENT) == 1
      and SENT[0]["to_address"] == "kerry@thegolffellowship.com", out)
SENT.clear()
out = json.loads(mcp_server._scoring_dispatch("", f"scoring-teetimes-email:{EV}|send"))
check("there is no send bridge", "error" in out and not SENT, out)

print("6. The evening-before window (handoff 10/20 §4 risk 1)")
# an approval on event morning used to send "comes at 7:00 AM tomorrow"
check("event morning: refused", "evening before" in (tt.send_window_ok("2026-10-27", datetime(2026, 10, 27, 6, 30)) or ""))
check("the day before at 4 PM: refused (the lock is 5 PM)", "5 PM" in (tt.send_window_ok("2026-10-27", datetime(2026, 10, 26, 16, 0)) or ""))
check("the day before at 5:30 PM (a manager's approval): allowed", tt.send_window_ok("2026-10-27", datetime(2026, 10, 26, 17, 30)) is None)
check("the day before at 11:45 PM: allowed", tt.send_window_ok("2026-10-27", datetime(2026, 10, 26, 23, 45)) is None)
check("two days before: refused", tt.send_window_ok("2026-10-27", datetime(2026, 10, 25, 19, 0)) is not None)
SENT.clear()
r = tt._deliver(EV_WE, DB, now=datetime(2026, 10, 31, 7, 0))
check("an approval on event morning sends nothing", "refused" in r and not SENT, r)
_pa = open("email_parser/pairings_approval.py", encoding="utf-8").read()
check("the approval path goes through the same _deliver", "from email_parser.teetimes_email import _deliver" in _pa)

try:
    os.unlink(DB)
except OSError:
    pass
print("ALL PASS" if not F else f"{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
