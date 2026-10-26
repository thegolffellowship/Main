"""MANAGER APPROVES THE PAIRINGS, THEN THE PLAYER EMAILS GO (Kerry
2026-10-13). Graph is mocked: nothing leaves.

Run: python3 test_pairings_approval.py
"""
import os, sys, io, contextlib, logging, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import event_day_email as ede
    from email_parser import pairings_approval as pa
    from email_parser import fetcher
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

SENT = []
fetcher.send_mail_graph = lambda **kw: SENT.append(kw) or True
for k, v in (("AZURE_TENANT_ID", "t"), ("AZURE_CLIENT_ID", "c"), ("AZURE_CLIENT_SECRET", "s"),
             ("EMAIL_ADDRESS", "tracker@example.test")):
    os.environ[k] = v
ede._read_games_tab = lambda eid: {"error": "no Chromium in a test"}

SA, AUS = 9301, 9302
with db._connect(DB) as conn:
    for eid, name, ch in ((SA, "s9.60 SA TUESDAY", "San Antonio"), (AUS, "a9.60 AUS TUESDAY", "Austin")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                     "start_time, course) VALUES (?, ?, '2026-10-20', ?, 'active', '9-hole', 'Shotgun', "
                     "'16:30', 'Test GC')", (eid, name, ch))
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (31, 'Robert', 'Straiton')")
    conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (31, 'robert@example.test', 1)")
    for cid, fn, ln in ((990101, "Ann", "Able"), (990102, "Bob", "Baker")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, ?)", (cid, fn, ln))
        conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?, ?, 1)",
                     (cid, f"{fn.lower()}@example.test"))
        for eid, name in ((SA, "s9.60 SA TUESDAY"), (AUS, "a9.60 AUS TUESDAY")):
            conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, side_games, "
                         "transaction_status, order_date, order_id, email_uid, merchant) VALUES "
                         "(?, ?, ?, ?, '9', 'NONE', 'active', '2026-10-01', ?, ?, 'GoDaddy')",
                         (f"{fn} {ln}", cid, name, eid, f"R{cid}{eid}", f"m-{cid}-{eid}"))
    conn.commit()
SHEET = {"9": [{"group_num": 1, "slot_label": "1A", "players": [
    {"name": "Ann Able", "cart_pos": 1, "customer_id": 990101},
    {"name": "Bob Baker", "cart_pos": 2, "customer_id": 990102}]}]}
for eid in (SA, AUS):
    db.save_event_pairings(eid, SHEET, db_path=DB)
db.set_app_setting(ede.APPROVAL_KEY, ede.load_template(DB)["hash"], db_path=DB)

print("1. Who approves")
check("San Antonio's prompt goes to Kerry's TGF address",
      pa.manager_for("San Antonio", DB)["email"] == "kerry@thegolffellowship.com")
check("Austin's goes to Robert's TGF address, not his personal one (Kerry 10/19)",
      pa.manager_for("Austin", DB)["email"] == "robert@thegolffellowship.com", pa.manager_for("Austin", DB))
check("admin may approve anything", pa.may_approve("admin", None, "Austin") is None)
check("the Austin manager may approve Austin", pa.may_approve("manager", "Austin", "Austin") is None)
check("…but not San Antonio", pa.may_approve("manager", "Austin", "San Antonio") is not None)
check("a view-only login may not", pa.may_approve("view-only", None, "Austin") is not None)

print("2. The prompt")
mon_5_05 = datetime(2026, 10, 19, 17, 5)
SENT.clear()
r = pa.prompt_check(mon_5_05, DB)
check("Monday 5:05 PM: one prompt per event, to its manager",
      sorted(s["to_address"] for s in SENT) == ["kerry@thegolffellowship.com", "robert@thegolffellowship.com"], r)
p = next((s for s in SENT if s["to_address"] == "robert@thegolffellowship.com"), {})
check("…naming the event, the player count and the review link (login)",
      "a9.60 AUS TUESDAY" in p.get("subject", "") and "2 players" in p.get("html_body", "")
      and f"/events/{AUS}/approve-pairings" in p.get("html_body", "")
      and "log in" in p.get("html_body", ""), p.get("html_body", "")[:400])
check("…with the groups and a sample player email",
      "Ann Able" in p.get("html_body", "") and "6:00 AM Event Info email" in p.get("html_body", "") and "Edit pairings" in p.get("html_body", ""))
check("no player was emailed by the prompt",
      not any(s["to_address"].endswith("@example.test") for s in SENT))
SENT.clear()
pa.prompt_check(mon_5_05 + timedelta(minutes=15), DB)
check("the same sheet is never prompted twice", not SENT)
db.save_event_pairings(AUS, {"9": [{"group_num": 1, "slot_label": "1A", "players": [
    {"name": "Bob Baker", "cart_pos": 1, "customer_id": 990102},
    {"name": "Ann Able", "cart_pos": 2, "customer_id": 990101}]}]}, db_path=DB)
r2 = pa.prompt_check(mon_5_05 + timedelta(minutes=20), DB)
check("a changed sheet does not prompt again (Kerry 10/26: \"Just once\")",
      not SENT and "once" in (r2["events"][AUS].get("skipped") or ""), r2["events"].get(AUS))
st = pa._load(DB); st[str(AUS)]["prompted_at"] = "2000-01-01 00:00:00"; pa._save(st, DB)
for _m in (80, 140, 200):
    pa.prompt_check(mon_5_05 + timedelta(minutes=_m), DB)
check("…not an hour later, nor at any later tick that evening", not SENT, [s["to_address"] for s in SENT])
check("the job has no re-prompt timer any more", not hasattr(pa, "REPROMPT_MINUTES"))

print("3. Approve")
fp = pa.sheet_fingerprint(AUS, DB)
SENT.clear()
r = pa.approve_and_send(AUS, fp, role="manager", session_chapter="San Antonio", approved_by="x", db_path=DB)
check("the other chapter's manager is refused", r.get("code") == 403 and not SENT, r)
r = pa.approve_and_send(AUS, "stale", role="manager", session_chapter="Austin", approved_by="x", db_path=DB)
check("an old sheet's approval is refused (409, with the new fingerprint)",
      r.get("code") == 409 and r.get("fingerprint") == fp and not SENT, r)
r = pa.approve_and_send(AUS, fp, role="manager", session_chapter="Austin",
                        approved_by="manager (Austin)", db_path=DB)
check("Robert's approval signs off the sheet and emails NO player tonight (Kerry 10/19)",
      r.get("status") == "approved" and not SENT and pa.emails_sent(AUS, DB) == 0, r)
check("…and records who approved which sheet",
      pa.event_state(AUS, DB).get("approved_fp") == fp
      and pa.event_state(AUS, DB).get("approved_by") == "manager (Austin)")
SENT.clear()
check("an approved sheet is never prompted again, even on a resend (Kerry 10/19)",
      "already approved" in (pa.send_prompt(AUS, DB).get("skipped") or "") and not SENT)
st = pa._load(DB); st[str(AUS)]["prompted_at"] = "2000-01-01 00:00:00"; pa._save(st, DB)
db.set_app_setting(pa.DIAL, "0", db_path=DB)
check("dial off: no prompts", pa.prompt_check(mon_5_05, DB) == {"status": "off"})
db.set_app_setting(pa.DIAL, "", db_path=DB)
print("2c. A weekend event is prompted at ITS lock, three days before (Kerry 10/26)")
WE = 9303
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, start_time, course) "
                 "VALUES (?, 's18.60 SA SATURDAY', '2026-10-24', 'San Antonio', 'active', '18 Holes', 'Tee Times', '08:00', 'Test GC')", (WE,))
    conn.commit()
db.save_event_pairings(WE, {"18": SHEET["9"]}, db_path=DB)
SENT.clear()
pa.prompt_check(datetime(2026, 10, 21, 16, 55), DB)
check("Wednesday 4:55 PM: not yet", not pa.event_state(WE, DB).get("prompted_at"))
r_we = pa.prompt_check(datetime(2026, 10, 21, 17, 5), DB)
check("Wednesday 5:05 PM: the Saturday event's manager is prompted", bool(pa.event_state(WE, DB).get("prompted_at")), r_we.get("events", {}).get(WE))

print("3b. 7 PM locks, 7 AM sends the Event Info email (Kerry 10/19)")
db.set_app_setting(pa.DIAL, "1", db_path=DB)
db.set_app_setting(ede.APPROVAL_KEY, ede.load_template(DB)["hash"], db_path=DB)
E_APP, E_AUTO = 9311, 9312
with db._connect(DB) as conn:
    for eid, name, ch in ((E_APP, "s9.61 APPROVED EARLY", "San Antonio"), (E_AUTO, "a9.61 NOBODY APPROVED", "Austin")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                     "start_time, course) VALUES (?, ?, '2026-10-27', ?, 'active', '9-hole', 'Shotgun', "
                     "'16:30', 'Test GC')", (eid, name, ch))
        for cid, fn, ln in ((990101, "Ann", "Able"), (990102, "Bob", "Baker")):
            conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, side_games, "
                         "transaction_status, order_date, order_id, email_uid, merchant) VALUES "
                         "(?, ?, ?, ?, '9', 'NONE', 'active', '2026-10-01', ?, ?, 'GoDaddy')",
                         (f"{fn} {ln}", cid, name, eid, f"R{cid}{eid}", f"m-{cid}-{eid}"))
    conn.commit()
for eid in (E_APP, E_AUTO):
    db.save_event_pairings(eid, SHEET, db_path=DB)
SENT.clear()
check("6:00 PM the day before: nothing happens", pa.auto_send_check(datetime(2026, 10, 26, 18, 0), DB).get("status") == "not yet")
pa.approve_and_send(E_APP, pa.sheet_fingerprint(E_APP, DB), role="admin", session_chapter=None,
                    approved_by="admin", db_path=DB)
r = pa.auto_send_check(datetime(2026, 10, 26, 19, 0), DB)
check("7:00 PM: the approved sheet stays as approved", "approved" in (r["events"].get(E_APP, {}).get("skipped") or ""), r["events"].get(E_APP))
check("7:00 PM: the unapproved sheet is auto-approved, no email",
      r["events"].get(E_AUTO, {}).get("status") == "auto-approved"
      and pa.event_state(E_AUTO, DB).get("approved_by", "").startswith("auto 7 PM"), r["events"].get(E_AUTO))
check("7 PM sends no player email at all", not SENT and pa.emails_sent(E_APP, DB) == 0 and pa.emails_sent(E_AUTO, DB) == 0, len(SENT))
check("5:45 AM event day: not yet (Event Info is 6:00 AM, Kerry 10/26)",
      pa.auto_send_check(datetime(2026, 10, 27, 5, 45), DB).get("status") == "not yet")
check("the Event Info hour is 6 by default", pa.info_hour(DB) == 6 and pa.info_time(DB) == "6:00 AM")
db.set_app_setting("event_info_hour", "7", db_path=DB)
check("dial event_info_hour=7: 6:45 AM is not yet", pa.auto_send_check(datetime(2026, 10, 27, 6, 45), DB).get("status") == "not yet")
db.set_app_setting("event_info_hour", "", db_path=DB)
r = pa.auto_send_check(datetime(2026, 10, 27, 7, 0), DB)
check("7:00 AM: both events' players get the Event Info email",
      pa.emails_sent(E_APP, DB) >= 2 and pa.emails_sent(E_AUTO, DB) >= 2, r)
SENT.clear()
r = pa.auto_send_check(datetime(2026, 10, 27, 7, 15), DB)
check("7:15 AM: nothing resends", not SENT, r)
E_FAIL = 9313
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                 "start_time, course) VALUES (?, 's9.62 WILL FAIL', '2026-10-27', 'San Antonio', 'active', "
                 "'9-hole', 'Shotgun', '16:30', 'Test GC')", (E_FAIL,))
    for cid, fn, ln in ((990101, "Ann", "Able"), (990102, "Bob", "Baker")):
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, side_games, "
                     "transaction_status, order_date, order_id, email_uid, merchant) VALUES "
                     "(?, ?, 's9.62 WILL FAIL', ?, '9', 'NONE', 'active', '2026-10-01', ?, ?, 'GoDaddy')",
                     (f"{fn} {ln}", cid, E_FAIL, f"R{cid}{E_FAIL}", f"m-{cid}-{E_FAIL}"))
    conn.commit()
db.save_event_pairings(E_FAIL, SHEET, db_path=DB)
db.set_app_setting(ede.APPROVAL_KEY, "", db_path=DB)        # wording unapproved -> send refused
SENT.clear()
r = pa.auto_send_check(datetime(2026, 10, 27, 7, 30), DB)
check("a failed 7 AM send emails Kerry",
      "error" in r["events"].get(E_FAIL, {}) and any("FAILED" in x.get("subject", "") and
      x.get("to_address") == "kerry@thegolffellowship.com" for x in SENT), (r["events"].get(E_FAIL), [x.get("subject") for x in SENT]))
r = pa.auto_send_check(datetime(2026, 10, 27, 7, 45), DB)
check("…and does not retry inside the hour", "hourly" in (r["events"].get(E_FAIL, {}).get("skipped") or ""), r["events"].get(E_FAIL))
db.set_app_setting(ede.APPROVAL_KEY, ede.load_template(DB)["hash"], db_path=DB)
db.set_app_setting(pa.AUTO_DIAL, "off", db_path=DB)
check("dial off: auto-send stops", pa.auto_send_check(datetime(2026, 10, 27, 7, 30), DB) == {"status": "off"})

print("4. The routes: log in first")
os.environ.setdefault("SECRET_KEY", "test-secret")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as _app
cl = _app.app.test_client()
check("the review page asks for a login", cl.get(f"/events/{AUS}/approve-pairings",
                                                 headers={"Accept": "text/html"}).status_code == 401)
check("the approve API refuses without a login", cl.post(f"/api/events/{AUS}/approve-pairings", json={}).status_code == 401)
with cl.session_transaction() as s:
    s["role"] = "manager"; s["chapter"] = "San Antonio"; s["authenticated"] = True
check("a San Antonio manager cannot open an Austin approval", cl.get(f"/events/{AUS}/approve-pairings").status_code == 403)
with cl.session_transaction() as s:
    s["chapter"] = "Austin"
page = cl.get(f"/events/{AUS}/approve-pairings")
check("the Austin manager sees the review with the approved state",
      page.status_code == 200 and b"Event Info emails go to" in page.data, page.status_code)

with cl.session_transaction() as s:
    s["role"] = "admin"; s.pop("chapter", None)
_fp = pa.sheet_fingerprint(SA, DB)
cl.get(f"/events/{SA}/approve-pairings?approve=stale")
check("a stale one-tap link approves nothing", pa.event_state(SA, DB).get("approved_fp") != _fp)
page = cl.get(f"/events/{SA}/approve-pairings?approve={_fp}")
check("the email's one-tap Approve approves the sheet (Kerry 10/19)",
      page.status_code == 200 and pa.event_state(SA, DB).get("approved_fp") == _fp, page.status_code)

try: os.unlink(DB)
except OSError: pass
print("ALL PASS" if not F else f"{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
