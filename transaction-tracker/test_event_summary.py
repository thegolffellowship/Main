"""THE EVENT SUMMARY (Event Ops #2460-E, Kerry 2026-10-29): "a Summary page
... for each event, and a direct link is sent to Managers & Admin to go see
the full report ... Handicap changes, Payout stuff, Financial report, Pace of
Play report ... RECAP could also go in there with the ability to edit it
before it goes to players".

One payload (build_summary) behind the SUMMARY tab, /events/<id>/summary and
the staff-only email; the recap edits through recap_store until it has sent;
dial event_summary_email (default off) replaces the admin payout report and
the handicap recap email. Graph is mocked: nothing leaves.

Run: python3 test_event_summary.py
"""
import os, sys, io, json, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-es-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import event_summary as es
    from email_parser import admin_payout_report as apr
    from email_parser import closeout_checks as cc
    from email_parser import recap_store, fetcher
    db.init_db(DB)
from datetime import datetime

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

DAY = "2099-10-27"
EV, EV_AUS = 9801, 9802
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, course, status) VALUES "
                 "(?, 's9.29 Silverhorn', ?, 'San Antonio', 'Silverhorn', 'active')", (EV, DAY))
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, course, status) VALUES "
                 "(?, 'a9.29 Teravista', '2099-11-03', 'Austin', 'Teravista', 'active')", (EV_AUS,))
    for cid, fn in ((880301, "Ann"), (880302, "Bob"), (880303, "Cal")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?, ?, 'Test')", (cid, fn))
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, transaction_status, order_date, "
                     "order_id, email_uid, merchant, item_price) VALUES (?, ?, 's9.29 Silverhorn', ?, 'active', "
                     "'2099-10-20', ?, ?, 'GoDaddy', '$40.00')", (f"{fn} Test", cid, EV, f"R{cid}", f"manual-{cid}"))
    conn.execute("INSERT INTO tgf_events (id, code, name, event_date, events_id) VALUES (71, 'T71', 'T71', ?, ?)",
                 (DAY, EV))
    conn.execute("INSERT INTO tgf_payouts (event_id, customer_id, category, amount, description, paid_at) VALUES "
                 "(71, 880301, 'net', 25.50, '1st Net', NULL), (71, 880301, 'skins', 10.00, 'Skin #4', NULL), "
                 "(71, 880302, 'net', 15.00, '2nd Net', '2099-10-27 21:00:00')")
    conn.commit()

print("1. One payload: players, payouts, financial, handicaps, pace, recap")
s = es.build_summary(EV, db_path=DB)
h = s.get("headline", {})
check("players from the roster", h.get("players") == 3, h)
check("payouts total / unpaid", h.get("payouts_count") == 3 and h.get("payouts_total") == 50.5
      and h.get("unpaid") == 35.5 and h.get("unpaid_count") == 2, h)
ann = next((w for w in s["payouts"]["winners"] if w["customer_id"] == 880301), {})
check("payouts grouped per golfer by customer_id", ann.get("total") == 35.5 and len(ann.get("items", [])) == 2, ann)
check("financial present for admin", "net_revenue" in s["financial"] or "error" in s["financial"], s["financial"])
check("no handicap rounds yet -> zero, no crash", s["handicaps"]["posted"] == 0, s["handicaps"])
check("no live-scoring round -> no pace, no crash", s["pace"]["rounds"] == [] and h["fastest"] is None, s["pace"])
check("no recap yet -> not editable", s["recap"]["name"] is None and not s["recap"]["editable"], s["recap"])
s2 = es.build_summary(EV, include_financial=False, db_path=DB)
check("financial hidden for a manager", s2["financial"].get("hidden") is True, s2["financial"])
check("the link to the page", s["links"]["summary"].endswith(f"/events/{EV}/summary"), s["links"])
check("an unknown event is an error", "error" in es.build_summary(1, db_path=DB))
check("financial for managers only behind the dial",
      es.may_see_financial("admin", DB) and not es.may_see_financial("manager", DB))

print("2. The recap: editable until it has sent, through recap_store, logged")
name = recap_store.save("2099-10-27-s9.29", "## SAN ANTONIO\nHello, Fellowship.\n", {"event_ids": [EV]}, db_path=DB)
db.set_app_setting(f"closeout_recap_night:{DAY}", name, db_path=DB)
db.set_app_setting("results_email_schedule", json.dumps(
    {str(EV): {"at": "2099-10-28T06:00", "recap": name, "authority": "t", "state": "scheduled"}}), db_path=DB)
ev = es.event_row(EV, DB)
rc = es.recap_info(ev, DB)
check("found from the closeout night key, editable", rc["name"] == name and rc["editable"] and "Hello" in rc["md"], rc)
check("shows when it goes", rc["send_at"] == "2099-10-28T06:00", rc)
r = es.save_recap(EV, "", "manager (San Antonio)", db_path=DB)
check("an empty recap is refused", r.get("code") == 400, r)
r = es.save_recap(EV, "## SAN ANTONIO\nHello, Fellowship. Edited.", "manager (San Antonio)", db_path=DB)
check("saved", r.get("ok") and r.get("changed"), r)
rec = recap_store.load(name, db_path=DB)
check("written through recap_store with who, when and the text it replaced",
      "Edited." in rec["md"] and rec["meta"].get("edited_by") == "manager (San Antonio)"
      and rec["meta"].get("edited_at") and "Edited." not in (rec["meta"].get("previous_md") or "x Edited."), rec["meta"])
check("the meta it had is kept", rec["meta"].get("event_ids") == [EV], rec["meta"])
with db._connect(DB) as conn:
    n = conn.execute("SELECT COUNT(*) FROM agent_action_log WHERE action_type = 'recap_edit'").fetchone()[0]
check("the edit is logged", n == 1, n)
db.set_app_setting("results_email_schedule", json.dumps(
    {str(EV): {"at": "2099-10-28T06:00", "recap": name, "authority": "t", "state": "sent",
               "sent_at": "2099-10-28T06:01"}}), db_path=DB)
rc = es.recap_info(ev, DB)
check("once sent it locks", not rc["editable"] and rc["sent_at"] and "Locked" in (rc["why"] or ""), rc)
r = es.save_recap(EV, "late edit", "admin", db_path=DB)
check("a save after the send is refused (409)", r.get("code") == 409, r)
db.set_app_setting("results_email_schedule", json.dumps(
    {f"{EV}|played": {"at": "2099-10-27T21:00", "recap": None, "state": "sent"},
     str(EV): {"at": "2099-10-28T06:00", "recap": name, "authority": "t", "state": "held",
               "last_run": {"state": "held", "sent": 0}}}), db_path=DB)
check("the players' same-day send (no recap) does not lock it; held still editable",
      es.recap_info(ev, DB)["editable"])

print("3. The email: staff only, once per event")
SENT.clear()
d = es.send_summary_email(EV, dry_run=True, db_path=DB)
check("dry run sends nothing and returns the payload", d["status"] == "would send" and not SENT
      and d["payload"]["headline"]["players"] == 3, {k: d.get(k) for k in ("status", "to")})
check("to the chapter manager and the admin (staff)", "kerry@thegolffellowship.com" in d["to"], d["to"])
check("the manager email never carries the financial report", d["payload"]["financial"].get("hidden") is True)
r = es.send_summary_email(EV, to="someone@gmail.com", db_path=DB)
check("a preview to a non-staff address is refused", "error" in r and not SENT, r)
r = es.send_summary_email(EV, to="robert@thegolffellowship.com", db_path=DB)
check("a preview to staff goes and stamps nothing", r["status"] == "sent" and len(SENT) == 1
      and not db.get_app_setting(es.SENT_KEY.format(EV), db_path=DB), r)
m = SENT[-1]
check("headline numbers + a button to the page",
      "$35.50" in m["html_body"] and f"/events/{EV}/summary" in m["html_body"]
      and "Open the full summary" in m["html_body"] and "Handicap changes" in m["html_body"], m["subject"])
db.set_app_setting("chapter_managers", json.dumps({"San Antonio": {"name": "X", "email": "x@gmail.com"}}), db_path=DB)
to, bad = es.recipients("San Antonio", DB)
check("a non-staff manager address is refused, never mailed", "x@gmail.com" in bad and "x@gmail.com" not in to,
      (to, bad))
db.set_app_setting("chapter_managers", "", db_path=DB)

print("4. The dial: off = the admin payout report as before; on = the summary replaces it")
cc.closeout_final_check = lambda eid, db_path=None, _read=None: {"final": True, "blocking": []}
EVENING = datetime(2099, 10, 27, 21, 15)
SENT.clear()
check("dial off by default", not es.dial_on(DB))
r = apr.run(day=DAY, confirm=True, now=EVENING, db_path=DB)
check("off: the admin payout report sends its own", r["status"] == "sent" and "Ready to pay" in SENT[-1]["subject"], r)
db.set_app_setting(apr.SENT_KEY.format(day=DAY), "", db_path=DB)
db.set_app_setting(es.DIAL, "on", db_path=DB)
SENT.clear()
r = apr.run(day=DAY, confirm=False, now=EVENING, db_path=DB)
check("on, dry run: would send the summary, nothing sent", r["status"] == "would send"
      and r["replaced_by"] == es.DIAL and not SENT, r)
r = apr.run(day=DAY, confirm=True, now=EVENING, db_path=DB)
check("on: the summary goes instead of the admin report", r["status"] == "sent" and len(SENT) == 1
      and SENT[0]["subject"].startswith("Event summary:"), r)
check("stamped event_summary_sent:<id>", bool(db.get_app_setting(es.SENT_KEY.format(EV), db_path=DB)))
check("the admin report's day stamp is set so it never also sends",
      bool(db.get_app_setting(apr.SENT_KEY.format(day=DAY), db_path=DB)))
r = apr.run(day=DAY, confirm=True, now=EVENING, db_path=DB)
check("once", r["status"] == "already sent" and len(SENT) == 1, r)
r = es.send_summary_email(EV, db_path=DB)
check("a direct second send is refused too", r["status"] == "already sent" and len(SENT) == 1, r)
db.set_app_setting(apr.DIAL, "off", db_path=DB)
db.set_app_setting(apr.SENT_KEY.format(day=DAY), "", db_path=DB)
r = apr.run(day=DAY, confirm=False, now=EVENING, db_path=DB)
check("admin report dial off, summary dial on: the summary still has its moment", r["status"] == "would send", r)
db.set_app_setting(apr.DIAL, "", db_path=DB)
row = [{"player_name": "Ann Test", "scoring_round_id": 0, "course_name": "Silverhorn", "round_date": DAY,
        "tee_name": "White", "gross": 40, "adjusted_score": 39, "differential": 5.0,
        "index_now": 10.0, "index_after": 9.5, "capped_holes": 0}]
SENT.clear()
r = db.send_handicap_recap_email("s9.29 Silverhorn", row, db_path=DB)
check("on: the handicap recap email skips", r.get("skipped") and not SENT, r)
r = db.send_handicap_recap_email("s9.29 Silverhorn", row, db_path=DB, force=True)
check("a manual resend (force) still goes", r.get("ok") and len(SENT) == 1, r)
db.set_app_setting(es.DIAL, "", db_path=DB)
SENT.clear()
r = db.send_handicap_recap_email("s9.29 Silverhorn", row, db_path=DB)
check("off: the handicap recap sends as before", r.get("ok") and len(SENT) == 1, r)

print("5. The page and the API: manager of the chapter, or admin")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as appmod
client = appmod.app.test_client()
def as_role(role, chapter=None):
    with client.session_transaction() as ss:
        ss.clear()
        ss["role"] = role
        if chapter:
            ss["chapter"] = chapter
as_role("manager", "Austin")
check("another chapter's manager is refused", client.get(f"/api/events/{EV}/summary").status_code == 403)
as_role("manager", "San Antonio")
rv = client.get(f"/api/events/{EV}/summary")
j = rv.get_json() or {}
check("own chapter's manager reads it; financial hidden", rv.status_code == 200
      and j.get("financial", {}).get("hidden") is True and j["headline"]["players"] == 3, rv.status_code)
pg = client.get(f"/events/{EV}/summary")
body = pg.get_data(as_text=True)
check("the phone page renders every section", pg.status_code == 200 and "EVENT SUMMARY" in body
      and all(k in body for k in ('id="financial"', 'id="payouts"', 'id="handicaps"', 'id="pace"', 'id="recap"'))
      and 'name="viewport"' in body, pg.status_code)
check("the editable recap is a textarea with Save", 'id="recap-md"' in body and "Save recap" in body)
rv = client.post(f"/api/events/{EV}/summary/recap", json={"md": "## SAN ANTONIO\nFrom the page."})
check("the page's Save writes", rv.status_code == 200 and "From the page." in recap_store.read_text(name, db_path=DB),
      rv.get_json())
as_role("admin")
j = client.get(f"/api/events/{EV}/summary").get_json() or {}
check("admin sees the financial report", not j.get("financial", {}).get("hidden"), j.get("financial"))
as_role("view-only")
check("view-only is refused", client.get(f"/api/events/{EV}/summary").status_code == 403)

print("6. Wiring")
_t = open("templates/events.html", encoding="utf-8").read()
check("SUMMARY tab is view 8, manager+", 'data-toggle-games="8"' in _t and '"8": "summary"' in _t
      and "summaryBadgeHtml(ev, summaryView)" in _t and "summaryBadgeHtml(ev, mobileSummaryView)" in _t)
check("five sections", all(k in _t for k in ('["financial", "FINANCIAL"]', '["payouts", "PAYOUTS"]',
                                              '["handicaps", "HANDICAPS"]', '["pace", "PACE"]', '["recap", "RECAP"]')))
check("admin reuses the FINANCIAL and PAYOUTS renderers",
      "body.innerHTML = renderFinancialPanel(ev, regs)" in _t and "renderPayoutsPanel(ev, regs)" in _t)
check("FINANCIAL and PAYOUTS tabs still there", 'data-toggle-games="3">FINANCIAL' in _t
      and 'data-toggle-games="4">PAYOUTS' in _t)
_m = open("mcp_server.py", encoding="utf-8").read()
check("bridge scoring-event-summary", 'cmd == "scoring-event-summary"' in _m)
_s = open("email_parser/event_summary.py", encoding="utf-8").read()
check("no member send path: staff_only on every recipient", _s.count("staff_only(") >= 2)

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
