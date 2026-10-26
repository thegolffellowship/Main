"""THE PAYMENT REMINDER (Kerry 2026-10-26: "our standard template for those
unpaid DOES include the link. We need to match these up" ... "go with
mockup 3" ... a link to who's registered, "but not in a button").

One builder (email_parser.payment_reminder) behind the Remind tag, Remind
All, the every-other-day 6 AM job and the composer preview. Graph is
mocked: nothing leaves.

Run: python3 test_payment_reminder.py
"""
import os, sys, io, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import payment_reminder as pr
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

EV, NOLINK, CHAMP, PAST = 9401, 9402, 9403, 9404
URL = "https://www.thegolffellowship.com/product-page/s9-98-remind-links"
with db._connect(DB) as conn:
    for eid, name, d, url in ((EV, "s9.98 REMIND LINKS", "2026-12-15", URL),
                              (NOLINK, "s9.97 NO LINK", "2026-12-15", ""),
                              (CHAMP, "s18.99 TEST CHAMPIONSHIP | Test Links", "2026-12-19", URL),
                              (PAST, "s9.01 PAST LINKS", "2025-01-01", URL)):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                     "start_time, course, registration_url, registration_url_status) VALUES "
                     "(?, ?, ?, 'San Antonio', 'active', '9-hole', 'Shotgun', '16:30', 'Test Links GC', ?, "
                     "'verified')", (eid, name, d, url))
    for cid, fn, em in ((880001, "Ann", "ann@example.test"), (880002, "Bob", "bob@example.test"),
                        (880003, "Cal", None)):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status, "
                     "chapter) VALUES (?, ?, 'Test', 'active_member', 'San Antonio')", (cid, fn))
        if em:
            conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?, ?, 1)",
                         (cid, em))
    # Ann: the shop's RSVP-only row. Bob: paid (active) — never reminded.
    for cid, st in ((880001, "rsvp_only"), (880002, "active")):
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, transaction_status, "
                     "order_date, order_id, email_uid, merchant, customer_email) VALUES (?, ?, "
                     "'s9.98 REMIND LINKS', ?, ?, '2026-01-01', ?, ?, 'GoDaddy', ?)",
                     (f"{'Ann' if cid == 880001 else 'Bob'} Test", cid, EV, st, f"R{cid}", f"manual-{cid}",
                      f"{'ann' if cid == 880001 else 'bob'}@example.test"))
    conn.commit()

print("1. The email")
m = pr.preview(EV, 880001, db_path=DB)
check("no hold on a verified link with a manager on file", m["held"] == [], m["held"])
check("greets the player by first name", "Hi Ann," in m["html"])
check("carries the registration link as a button", URL in m["html"] and "Complete Registration" in m["html"])
check("the roster link is a plain link to the member results page",
      f"/member/results/{EV}" in m["html"] and pr.ROSTER_LINK_TEXT.replace("'", "&#x27;") in m["html"]
      or pr.ROSTER_LINK_TEXT in m["html"], m["html"][:300])
check("the roster link is not a button (no bgcolor cell around it)",
      'bgcolor' not in m["html"].split(f"/member/results/{EV}")[0][-400:])
check("sits in the house frame (dark masthead)", "#1a1a1a" in m["html"].lower() or "#1b1b1b" in m["html"].lower()
      or "SAN ANTONIO" in m["html"], m["html"][:200])
check("no leftover {tags}", "{" not in m["subject"] and not pr._tags(m["html"]))

print("2. The holds")
check("a blank link holds the message", any("registration link" in w for w in pr.preview(NOLINK)["held"]))
check("a played event's link holds the message", any("registration link" in w for w in pr.preview(PAST)["held"]))

print("3. The masthead title")
champ = pr.preview(CHAMP)["html"]
check("a name with '@' drops the 'Saturday at'", " at Test Championship" not in champ
      and "Saturday at" not in champ, champ[:400])

print("4. Who Remind All reaches")
people = pr.rsvp_only_people(EV, db_path=DB)
check("RSVP-only Ann, not paid Bob", [p["customer_id"] for p in people] == [880001], people)

print("5. Sending, once a day")
SENT.clear()
r1 = pr.send(EV, people, db_path=DB)
check("sends to Ann", [s["customer_id"] for s in r1["sent"]] == [880001] and len(SENT) == 1, r1)
check("the sent email is the framed build", SENT and URL in SENT[0]["html_body"])
r2 = pr.send(EV, people, db_path=DB)
check("a second send the same day is skipped", r2["already_today"] and not r2["sent"] and len(SENT) == 1, r2)
r3 = pr.send(EV, people, force=True, db_path=DB)
check("force sends again", len(r3["sent"]) == 1 and len(SENT) == 2, r3)
with db._connect(DB) as conn:
    n = conn.execute("SELECT COUNT(*) FROM message_log WHERE event_id = ? AND customer_id = 880001",
                     (EV,)).fetchone()[0]
check("each send is logged against the event and customer", n == 2, n)
r4 = pr.send(EV, [{"customer_id": 880003, "name": "Cal Test"}], db_path=DB)
check("no address on file is reported, not sent", r4["no_email"] and not r4["sent"], r4)
r5 = pr.send(EV, [{"customer_id": None, "email": "guest@example.test", "name": "Guest Player"}], db_path=DB)
check("an RSVP with no customer card sends by email", r5["sent"] and SENT[-1]["to_address"] == "guest@example.test", r5)
r6 = pr.send(NOLINK, [{"customer_id": 880001}], db_path=DB)
check("a held message is not sent", r6["held"] and not r6["sent"], r6)

print("6. The routes")
os.environ.setdefault("ADMIN_PIN", "4242")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as _app
cl = _app.app.test_client()
with cl.session_transaction() as s_:
    s_["role"] = "manager"; s_["authenticated"] = True
SENT.clear()
rv = cl.post("/api/events/send-reminder", json={"event_id": EV, "customer_id": 880002, "player_name": "Bob Test"})
check("the Remind tag sends the same email", rv.status_code == 200 and SENT and URL in SENT[-1]["html_body"],
      (rv.status_code, rv.get_json()))
rv = cl.post("/api/events/send-reminder", json={"event_id": EV, "customer_id": 880002})
check("a second Remind the same day says so", rv.status_code == 409 and "today" in rv.get_json()["error"],
      (rv.status_code, rv.get_json()))
rv = cl.post("/api/events/send-reminder", json={"event_name": "s9.97 no link", "customer_id": 880001})
check("Remind on an event with no link is held and says why", rv.status_code == 409
      and "registration link" in rv.get_json()["error"], (rv.status_code, rv.get_json()))
rv = cl.post("/api/events/send-reminder-all", json={"event_name": "s9.98 REMIND LINKS"})
check("Remind All resolves the event by name and reports already-today",
      rv.status_code == 409 and rv.get_json()["already_today_count"] == 1, (rv.status_code, rv.get_json()))

print("7. The 6 AM job")
SENT.clear()
with db._connect(DB) as conn:
    conn.execute("DELETE FROM app_settings WHERE key LIKE 'payment_reminder_sent:%'")
    conn.commit()
db.set_app_setting("payment_reminder_exclude_events", "[]")
_app.send_auto_payment_reminders()
check("the job sends the same email to the RSVP-only player",
      [s["to_address"] for s in SENT] == ["ann@example.test"] and URL in SENT[0]["html_body"],
      [s["to_address"] for s in SENT])
SENT.clear()
with db._connect(DB) as conn:
    conn.execute("DELETE FROM app_settings WHERE key LIKE 'payment_reminder_sent:%'")
    conn.commit()
db.set_app_setting("payment_reminder_exclude_events", f"[{EV}]")
_app.send_auto_payment_reminders()
check("the exclude dial still keeps an event out", SENT == [], SENT)

print("8. The composer preview")
tid = next(t["id"] for t in db.get_message_templates() if t["name"] == "Payment Reminder")
pv = cl.post("/api/messages/preview", json={"template_id": tid, "event_name": "s9.98 REMIND LINKS",
                                             "event_url": URL})
body = (pv.get_json() or {}).get("html_body", "")
check("the preview shows the framed reminder with the roster link",
      pv.status_code == 200 and f"/member/results/{EV}" in body and "{" not in body.split("<style")[0][-1:],
      (pv.status_code, body[:200]))

print("9. Stop at the lock (Kerry 10/26, #2313)")
from datetime import datetime as _dt
from email_parser import timezone_utils as _tz
_real_now = _tz.now_central
db.set_app_setting("payment_reminder_exclude_events", "[]")
ev_row = {"event_date": "2026-12-15"}  # a Tuesday nine: locks Monday 5:00 PM
check("a Tuesday nine locks Monday at 5:00 PM", pr.lock_at(ev_row, DB) == _dt(2026, 12, 14, 17, 0),
      pr.lock_at(ev_row, DB))
check("a dialled Saturday locks two days ahead",
      pr.lock_at({"event_date": "2026-12-19"}, DB) == _dt(2026, 12, 17, 17, 0))
check("an undialled weekday locks the day before",
      pr.lock_at({"event_date": "2026-12-17"}, DB) == _dt(2026, 12, 16, 17, 0))
check("4:59 PM on the lock day is not past the lock",
      not pr.past_lock(ev_row, now=_dt(2026, 12, 14, 16, 59), db_path=DB))
check("5:00 PM on the lock day is past the lock", pr.past_lock(ev_row, now=_dt(2026, 12, 14, 17, 0), db_path=DB))
check("event day 6:00 AM is past the lock", pr.past_lock(ev_row, now=_dt(2026, 12, 15, 6, 0), db_path=DB))
_tz.now_central = lambda: _dt(2026, 12, 15, 6, 0)
try:
    with db._connect(DB) as conn:
        conn.execute("DELETE FROM app_settings WHERE key LIKE 'payment_reminder_sent:%'")
        conn.commit()
    SENT.clear()
    _app.send_auto_payment_reminders()
    check("the 6 AM job skips an event past its lock", SENT == [], [s["to_address"] for s in SENT])
    r = pr.send(EV, people, db_path=DB)
    check("send() holds everyone past the lock and says why",
          not r["sent"] and r["held"] and r["held"][0]["why"] == [pr.PAST_LOCK] and SENT == [], r)
    rv = cl.post("/api/events/send-reminder", json={"event_id": EV, "customer_id": 880001})
    check("the Remind tag refuses past the lock", rv.status_code == 409 and "5:00 PM lock" in rv.get_json()["error"],
          (rv.status_code, rv.get_json()))
    rv = cl.post("/api/events/send-reminder-all", json={"event_id": EV})
    check("Remind All refuses past the lock", rv.status_code == 409 and "5:00 PM lock" in rv.get_json()["error"],
          (rv.status_code, rv.get_json()))
    rv = cl.post("/api/messages/send", json={"template_id": tid, "event_name": "s9.98 REMIND LINKS",
                                            "recipients": [{"name": "Ann Test", "email": "ann@example.test"}],
                                            "event_url": URL})
    check("the composer refuses the Payment Reminder template past the lock",
          rv.status_code == 409 and "5:00 PM lock" in (rv.get_json() or {}).get("error", "") and SENT == [],
          (rv.status_code, rv.get_json()))
    db.set_app_setting(pr.STOP_DIAL, "off")
    _app.send_auto_payment_reminders()
    check("dial payment_reminder_stop_at_lock=off sends again", [s["to_address"] for s in SENT] == ["ann@example.test"],
          [s["to_address"] for s in SENT])
    db.set_app_setting(pr.STOP_DIAL, "")
    _tz.now_central = lambda: _dt(2026, 12, 14, 16, 0)
    with db._connect(DB) as conn:
        conn.execute("DELETE FROM app_settings WHERE key LIKE 'payment_reminder_sent:%'")
        conn.commit()
    SENT.clear()
    _app.send_auto_payment_reminders()
    check("before the lock the job still reminds", [s["to_address"] for s in SENT] == ["ann@example.test"],
          [s["to_address"] for s in SENT])
finally:
    _tz.now_central = _real_now

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
