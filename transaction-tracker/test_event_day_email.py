"""The EVENT-DAY EMAIL (CA #829): one pairing email per roster player,
built from the saved sheet, HELD at the boundary on any blank, staff-only
preview, member send locked behind Kerry's approval stamp + confirm,
never twice per event + customer. Graph is mocked — nothing leaves.

Run: python3 test_event_day_email.py
"""
import os, sys, io, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import event_day_email as ede
    from email_parser import fetcher
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

# Graph is mocked for the whole file: no real mail can leave.
SENT = []
def fake_send(**kw):
    SENT.append(kw); return True
fetcher.send_mail_graph = fake_send
for k, v in (("AZURE_TENANT_ID", "t"), ("AZURE_CLIENT_ID", "c"), ("AZURE_CLIENT_SECRET", "s"),
             ("EMAIL_ADDRESS", "tracker@example.test")):
    os.environ[k] = v

EV, EV2 = 9101, 9102
PEOPLE = [  # cid, first, last, email, side_games
    (880001, "Ann", "Able", "ann@example.test", "NET"),
    (880002, "Bob", "Baker", "bob@example.test", "BOTH"),
    (880003, "Cal", "Cole", "cal@example.test", "NONE"),
    (880004, "Dee", "Dunn", "dee@example.test", "GROSS"),
    (880005, "Eli", "Eno", None, "NET"),                   # seated, no email
    (880006, "Fay", "Fox", "fay@example.test", "NET"),     # on roster, not seated
    (880007, "Gus", "Gray", "gus@example.test", "NONE"),
]
with db._connect(DB) as conn:
    for eid, name in ((EV, "s9.99 TEST LINKS"), (EV2, "s9.98 UNSAVED LINKS")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, "
                     "start_type, start_time, course) VALUES (?, ?, '2026-10-13', 'San Antonio', "
                     "'active', '9-hole', 'Shotgun', '08:00', 'Test Links GC')", (eid, name))
    for cid, fn, ln, em, sg in PEOPLE:
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
                     "VALUES (?,?,?,'active_member')", (cid, fn, ln))
        if em:
            conn.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?,?,1)", (cid, em))
        for eid, name in ((EV, "s9.99 TEST LINKS"), (EV2, "s9.98 UNSAVED LINKS")):
            conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, tee_choice, "
                         "side_games, transaction_status, order_date, order_id, email_uid, merchant) "
                         "VALUES (?, ?, ?, ?, '9', '50-64', ?, 'active', '2026-10-01', ?, ?, 'GoDaddy')",
                         (f"{fn} {ln}", cid, name, eid, sg, f"R{cid}{eid}", f"manual-{cid}-{eid}"))
    conn.commit()
db.set_event_bundle_offers(EV, ["NET", "GROSS"], db_path=DB)
db.save_event_pairings(EV, {"9": [
    {"group_num": 1, "slot_label": "1A", "players": [
        {"name": "Ann Able", "cart_pos": 1, "customer_id": 880001},
        {"name": "Bob Baker", "cart_pos": 2, "customer_id": 880002},
        {"name": "Cal Cole", "cart_pos": 3, "customer_id": 880003},
        {"name": "Dee Dunn", "cart_pos": 4, "customer_id": 880004}]},
    {"group_num": 2, "slot_label": "1B", "players": [
        {"name": "Eli Eno", "cart_pos": 1, "customer_id": 880005},
        {"name": "Gus Gray", "cart_pos": 2, "customer_id": 880007}]}]}, db_path=DB)

print("1. The dry build")
tpl = ede.load_template(DB)
check("the template is seeded as DATA (message_templates row)", bool(tpl) and "{group_block}" in tpl["html_body"], tpl)
b = ede.build_event_day_emails(EV, db_path=DB)
by = {m["customer_id"]: m for m in b.get("messages", [])}
held = {h["customer_id"]: h["reason"] for h in b.get("held", [])}
ann = by.get(880001, {})
check("Ann's message is ready, to her canonical email", ann.get("email") == "ann@example.test", b)
check("…with her start stated as the Starter Sheet states it", "Your start: Hole 1A | 8:00 AM" in ann.get("text", ""), ann.get("text"))
check("…her three group-mates and not herself",
      all(f"- {n}" in ann.get("text", "") for n in ("Bob Baker", "Cal Cole", "Dee Dunn"))
      and "- Ann Able" not in ann.get("text", ""), ann.get("text"))
check("…her cart partner (seats 1&2)", "Your cart partner: Bob Baker" in ann.get("text", ""), ann.get("text"))
check("…course, date, and the chapter manager",
      "Test Links GC" in ann.get("text", "") and "Tuesday, October 13, 2026" in ann.get("text", "")
      and "Kerry" in ann.get("text", ""), ann.get("text"))
check("…games: NET in, GROSS not bought",
      "NET games (Individual Net + MVP): you're in" in ann.get("text", "")
      and "GROSS games (Skins + Individual Gross): not bought" in ann.get("text", ""), ann.get("text"))
check("BOTH buyer is in both", by.get(880002, {}).get("text", "").count("you're in") == 2)
check("Cal's cart partner is Dee (seats 3&4)", "Your cart partner: Dee Dunn" in by.get(880003, {}).get("text", ""))
check("house paragraph spacing applied (normalize_email_html)", 'style="margin:0 0 1em;"' in ann.get("html", ""))
check("no brace survives in any ready message",
      not any("{" in m["html"] or "{" in m["subject"] for m in b["messages"]))
check("seated player with no email is HELD", "no email" in held.get(880005, ""), held)
check("roster player not on the sheet is HELD", "not in a group" in held.get(880006, ""), held)
check("Gus (group 2) is ready with Eli as his mate", "- Eli Eno" in by.get(880007, {}).get("text", ""))
check("counts add up", b["counts"] == {"roster": 7, "ready": 5, "held": 2}, b["counts"])
check("unapproved by default", b["approved"] is False)
b2 = ede.build_event_day_emails(EV2, db_path=DB)
check("an unsaved sheet holds everybody", b2["counts"]["ready"] == 0
      and all("pairings not saved" in h["reason"] for h in b2["held"] if h.get("email")), b2["counts"])

print("2. The boundary guard")
with db._connect(DB) as conn:
    conn.execute("UPDATE events SET chapter = 'Nowhere' WHERE id = ?", (EV,)); conn.commit()
b3 = ede.build_event_day_emails(EV, db_path=DB)
check("a blank {manager_name} holds every message", b3["counts"]["ready"] == 0
      and all("blank: {manager_name}" in h["reason"] for h in b3["held"]
              if h.get("email") and "not in a group" not in h["reason"]), b3["held"][:2])
with db._connect(DB) as conn:
    conn.execute("UPDATE events SET chapter = 'San Antonio' WHERE id = ?", (EV,)); conn.commit()
orig_body = tpl["html_body"]
def set_body(body):
    with db._connect(DB) as conn:
        conn.execute("UPDATE message_templates SET html_body = ? WHERE id = ?", (body, tpl["id"])); conn.commit()
set_body(orig_body + "<p>{x}</p>")
b4 = ede.build_event_day_emails(EV, db_path=DB)
check("a leftover {x} holds the message", b4["counts"]["ready"] == 0
      and any("{x}" in h["reason"] for h in b4["held"]), b4["held"][:2])
set_body(orig_body + "<p>Meet at [MEETING SPOT].</p>")
b5 = ede.build_event_day_emails(EV, db_path=DB)
check("a [BRACKETED BLANK] holds the message", b5["counts"]["ready"] == 0, b5["held"][:2])
set_body(orig_body)

print("3. The staff-only preview")
SENT.clear()
r = ede.send_event_day_preview(EV, to_address="pat@gmail.com", db_path=DB)
check("a non-staff address is refused", "error" in r and "staff only" in r["error"] and not SENT, r)
r = ede.send_event_day_preview(EV, to_address="kerry@thegolffellowship.com, pat@gmail.com", db_path=DB)
check("a mixed list is refused whole", "error" in r and not SENT, r)
r = ede.send_event_day_preview(EV, db_path=DB)
check("default preview goes to Kerry, ONE mail",
      r.get("status") == "sent" and len(SENT) == 1 and SENT[0]["to_address"] == "kerry@thegolffellowship.com", r)
check("…carries 3 samples, the held list and the counts",
      SENT and SENT[0]["html_body"].count("<strong>To:</strong>") == 3 and "HELD" in SENT[0]["html_body"]
      and "Eli Eno" in SENT[0]["html_body"] and "NOT approved" in SENT[0]["html_body"])

print("4. The member send")
SENT.clear()
r = ede.send_event_day_emails(EV, confirm=True, db_path=DB)
check("refused without the approval stamp", "refused" in r and not SENT, r)
db.set_app_setting(ede.APPROVAL_KEY, tpl["hash"], db_path=DB)
r = ede.send_event_day_emails(EV, confirm=False, db_path=DB)
check("refused without confirm, even when approved", "refused" in r and not SENT, r)
set_body(orig_body.replace("See you out there", "See you soon"))
r = ede.send_event_day_emails(EV, confirm=True, db_path=DB)
check("an edited template voids the stamp", "refused" in r and not SENT, r)
set_body(orig_body)
r = ede.send_event_day_emails(EV, confirm=True, db_path=DB)
check("approved + confirm sends every ready message once",
      r.get("counts", {}).get("sent") == 5 and len(SENT) == 5, r.get("counts"))
check("…only to the fixture's own addresses",
      sorted(s["to_address"] for s in SENT) == sorted(["ann@example.test", "bob@example.test",
                                                         "cal@example.test", "dee@example.test",
                                                         "gus@example.test"]))
r2 = ede.send_event_day_emails(EV, confirm=True, db_path=DB)
check("a second run sends nothing (idempotent per event + customer)",
      len(SENT) == 5 and r2["counts"]["sent"] == 0 and r2["counts"]["skipped"] == 5, r2.get("counts"))
with db._connect(DB) as conn:
    rows = conn.execute("SELECT customer_id, status FROM event_day_email_sends WHERE event_id = ?", (EV,)).fetchall()
check("one 'sent' row per customer", len(rows) == 5 and all(x["status"] == "sent" for x in rows), [tuple(x) for x in rows])

print("5. The bridge")
os.environ["DATABASE_PATH"] = DB
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import mcp_server
import json
SENT.clear()
out = json.loads(mcp_server._scoring_dispatch("", f"scoring-event-day-email:{EV}"))
check("dry bridge reports counts and a sample, sends nothing",
      out.get("counts", {}).get("ready") == 5 and len(out.get("samples", [])) == 1 and not SENT, out.get("counts"))
out = json.loads(mcp_server._scoring_dispatch("", f"scoring-event-day-email:{EV}|preview|pat@gmail.com"))
check("preview bridge refuses a non-staff address", "error" in out and not SENT, out)
out = json.loads(mcp_server._scoring_dispatch("", f"scoring-event-day-email:{EV}|send"))
check("there is no member-send bridge", "error" in out and not SENT, out)

# EMAIL PLAYERS (Kerry 2026-10-08): the scoring link and the admin routes
check("the template carries each player's scoring link ({scoring_block})",
      "{scoring_block}" in (tpl or {}).get("html_body", ""))
check("no Live Scoring on the event: no scoring line, nothing held for it",
      all("Keep score on your phone" not in m["text"] for m in b["messages"]))
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PIN", "4242")
import app as _app
_cl = _app.app.test_client()
check("the Email Players preview is admin only", _cl.get("/api/events/1/event-day-email").status_code in (401, 302, 403))
check("the Email Players send is admin only",
      _cl.post("/api/events/1/event-day-email/send", json={}).status_code in (401, 302, 403))

try: os.unlink(DB)
except OSError: pass
print("ALL PASS" if not F else f"{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
