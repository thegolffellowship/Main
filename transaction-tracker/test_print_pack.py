"""The event PRINT PACK: every print sheet bound into one PDF, mailed the
evening before (v2.465.0).

Kerry 2026-09-18: "a bound PDF with all of them in one that I could
print, rather than each separately" / "Build the PDF routine and have
it emailed to me."

Run: python3 test_print_pack.py   (needs weasyprint importable)
"""
import os, sys, io, contextlib, logging, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
os.environ.setdefault("ADMIN_PIN", "0000")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import print_pack as pp
    db.init_db(os.environ["DATABASE_PATH"])
    import app as appmod
F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond: F.append(label)

DB = os.environ["DATABASE_PATH"]
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_time, course) "
                 "VALUES (9001, 's18.11 CEDAR CREEK', '2026-09-19', 'San Antonio', 'active', '18-hole', '8:10 AM', 'Cedar Creek Golf Course')")
    for cid, fn, ln in ((777001, 'Jeff', 'Rideout'), (777002, 'Mary', 'Wade'), (777003, 'Gus', 'Vasquez'), (777004, 'Dan', 'Stich')):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) VALUES (?,?,?,'active_member')", (cid, fn, ln))
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, tee_choice, transaction_status, order_date, order_id, email_uid, merchant) VALUES (?, ?, 's18.11 CEDAR CREEK', 9001, '18', '50-64', 'active', '2026-09-10', ?, ?, 'GoDaddy')", (f"{fn} {ln}", cid, f"R{cid}", f"manual-{cid}"))
    conn.commit()
db.save_event_pairings(9001, {"18": [{"group_num": 1, "slot_label": "8:10 AM", "players": [
    {"name": "Jeff Rideout", "cart_pos": 1, "customer_id": 777001, "tee_choice": "50-64", "handicap_index": None},
    {"name": "Mary Wade", "cart_pos": 2, "customer_id": 777002, "tee_choice": "50-64", "handicap_index": None},
    {"name": "Gus Vasquez", "cart_pos": 3, "customer_id": 777003, "tee_choice": "50-64", "handicap_index": None},
    {"name": "Dan Stich", "cart_pos": 4, "customer_id": 777004, "tee_choice": "50-64", "handicap_index": None}]}]})

print("1. The pack binds")
built = appmod.build_print_pack_for_event(9001)
check("a pack is built for a saved sheet", bool(built) and not built.get("error"), built and built.get("error"))
check("it is a PDF", bool(built) and built.get("pdf", b"")[:4] == b"%PDF")
check("the starter sheet and cart signs are in it, in print order",
      bool(built) and [p["slug"] for p in built["parts"]][:2] == ["starter-sheet", "cart-signs"], built and built["parts"])
check("every part has at least one page", bool(built) and all(p["pages"] >= 1 for p in built["parts"]), built and built["parts"])
check("it rendered through Chromium here (the same engine as the browser's Download PDF)",
      bool(built) and built.get("engine") == "chromium", built and built.get("engine"))
check("the logo was actually served to the renderer (root-relative /static/ refs resolve; Kerry: 'the logo is not rendering')",
      bool(built) and "tgf-logo-r.svg" in (built.get("assets") or []), built and built.get("assets"))
check("the content hash ignores the printed-at stamp (a clock is not a change)",
      bool(built) and appmod.build_print_pack_for_event(9001)["sha"] == built["sha"]
      and pp._hash_view('<p>x</p><span class="pstamp">Printed Mon 9/21 12:30 PM.</span>') == "<p>x</p>")
_body = pp.print_pack_email_body(built) if built else ""
check("the mail body carries the first tee, every seated player and the blinds (Kerry 2026-09-21: 'build the email body')",
      all(n in _body for n in ("Jeff Rideout", "Mary Wade", "Gus Vasquez", "Dan Stich")) and "8:10 AM" in _body
      and "1T" in _body and "Attached:" in _body, _body[:400])
check("…and is escaped HTML with no template leftovers", "{{" not in _body and "<script" not in _body)
check("the filename names the event and the date",
      bool(built) and "s18.11 CEDAR CREEK" in built["filename"] and "2026-09-19" in built["filename"])
check("unknown event → None", appmod.build_print_pack_for_event(424242) is None)

print("2. The route")
c = appmod.app.test_client()
with c.session_transaction() as s:
    s["role"] = "admin"; s["authenticated"] = True
r = c.get("/events/9001/print-pack.pdf")
check("GET /events/<id>/print-pack.pdf serves the PDF", r.status_code == 200 and r.mimetype == "application/pdf"
      and r.get_data()[:4] == b"%PDF", (r.status_code, r.mimetype))

print("3. The routine and the mail")
from email_parser import timezone_utils as tz
from datetime import timedelta
with db._connect(DB) as conn:
    conn.execute("UPDATE events SET event_date = ? WHERE id = 9001", ((tz.today_central() + timedelta(days=1)).isoformat(),))
    conn.commit()
check("an event dated tomorrow is due", [e["id"] for e in pp.print_packs_due()] == [9001])
sent = []
def fake_send(**kw):
    sent.append(kw); return True
import email_parser.fetcher as fetcher
orig = fetcher.send_mail_graph; fetcher.send_mail_graph = fake_send
for k, v in (("AZURE_TENANT_ID", "t"), ("AZURE_CLIENT_ID", "c"), ("AZURE_CLIENT_SECRET", "s"),
             ("EMAIL_ADDRESS", "tracker@example.test"), ("PRINT_PACK_EMAIL_TO", "kerry@example.test")):
    os.environ[k] = v
res = pp.send_due_print_packs(appmod._print_pack_render, appmod.app.static_folder)
check("the routine sends tomorrow's pack once", len(sent) == 1 and res and res[0].get("sent") is True, res)
check("…as a PDF attachment to the configured recipient",
      sent and sent[0]["to_address"] == "kerry@example.test"
      and sent[0]["attachments"][0][2] == "application/pdf" and sent[0]["attachments"][0][1][:4] == b"%PDF")
res2 = pp.send_due_print_packs(appmod._print_pack_render, appmod.app.static_folder)
check("an unchanged sheet is not sent again", len(sent) == 1 and res2[0].get("why") == "unchanged since last send", res2)
db.save_event_pairings(9001, {"18": [{"group_num": 1, "slot_label": "8:20 AM", "players": [
    {"name": "Jeff Rideout", "cart_pos": 1, "customer_id": 777001, "tee_choice": "50-64", "handicap_index": None}]}]})
res3 = pp.send_due_print_packs(appmod._print_pack_render, appmod.app.static_folder)
check("a changed sheet is sent again", len(sent) == 2 and res3[0].get("sent") is True, res3)
fetcher.send_mail_graph = orig

print("4. Graph attachments")
src = open("email_parser/fetcher.py", encoding="utf-8").read()
check("send_mail_graph takes attachments as fileAttachment", "#microsoft.graph.fileAttachment" in src and "attachments: list | None = None" in src)
asrc = open("app.py", encoding="utf-8").read()
check("the evening-before routine is scheduled 5–10 PM Central", 'id="print_packs_evening_before"' in asrc and 'hour="17-22"' in asrc)
try: os.unlink(DB)
except OSError: pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
