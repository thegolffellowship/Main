"""SCREENS (Kerry 2026-10-26): the Librarian's screenshot catalogue, the
admin-only page and file route, and comments that become mailbox posts to
the Librarian, never a Kerry OK.

Run: python3 test_screens.py
"""
import os, sys, io, json, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import screens as scr
    from email_parser.customer_query import _kerry_ok
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

print("1. The catalogue in the repo")
cat = scr.catalog()
ids = [s["id"] for s in cat["sequences"]]
check("it loads with sequences", len(ids) >= 10, len(ids))
check("ids are unique", len(ids) == len(set(ids)))
missing = [(s["id"], st["file"], st["missing"]) for s in cat["sequences"] for st in s["steps"] if st["missing"]]
check("every catalogued file is on disk", not missing, missing[:5])
check("every sequence has an area the page lists",
      all(s["area"] in cat["areas"] for s in cat["sequences"]))
check("every status is a known one", all(s["status"] in ("current", "built", "mockup", "superseded", "reference", "needed")
                                         for s in cat["sequences"]))
check("nothing on disk is left uncatalogued", cat["not_catalogued"] == [], cat["not_catalogued"])

print("2. Paths")
s0 = cat["sequences"][0]
check("a catalogued file resolves", scr.safe_file(f"{s0['folder']}/{s0['steps'][0]['file']}") is not None)
check("climbing out is refused", scr.safe_file("../../../app.py") is None
      and scr.safe_file("../catalog.json") is None)
check("a non-image is refused", scr.safe_file("catalog.json") is None)
check("an unknown base is refused", scr.safe_file("x.png", base="templates") is None)
check("a static picture resolves under its base", scr.safe_file("live-scoring/03-hole.jpg", base="static") is not None
      and scr.safe_file("../../app.py", base="static") is None)

print("3. Comments are mailbox posts to the Librarian")
seq = cat["sequences"][0]
r = scr.add_comment(seq["id"], "Improve", "The button is too small.", step_file=seq["steps"][0]["file"],
                    db_path=DB)
check("posted", r.get("id") and r["topic"] == "screens" and r["author"] == "screens-page", r)
check("addressed to the Librarian, cc Front Desk",
      r["body"].startswith("TO: librarian-claude") and "CC: front-desk" in r["body"])
check("names the sequence and the step", f"SEQUENCE: {seq['id']} " in r["body"] and "STEP: " in r["body"])
with db._connect(DB) as conn:
    ok, why = _kerry_ok(conn, r["id"])
check("a comment is never Kerry's OK", not ok, why)
with db._connect(DB) as conn:
    kc = conn.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES ('screens-page', 'screens', ?)",
                      ("TO: librarian-claude\nCC: front-desk\nFROM: screens-page\nKIND: Note\n"
                       f"SEQUENCE: {seq['id']} — x\n\nKerry, verbatim: \"Deploy\"",)).lastrowid
    conn.commit()
    ok2, _ = _kerry_ok(conn, kc)
check("even one quoting Kerry is not his OK", not ok2)
reply = db.post_platform_dialogue_entry("tracker-claude", f"TO: kerry\nFROM: librarian-claude\nSEQUENCE: {seq['id']}\n\nFiled.",
                                        "screens", db_path=DB)
other = scr.add_comment(cat["sequences"][1]["id"], "Note", "Other one.", db_path=DB)
th = scr.thread(seq["id"], db_path=DB)
check("the thread holds this sequence's posts and the Librarian's reply, in order",
      [p["id"] for p in th] == [r["id"], kc, reply["id"]], [p["id"] for p in th])
check("counts per sequence", scr.counts(db_path=DB).get(seq["id"]) == 3
      and scr.counts(db_path=DB).get(cat["sequences"][1]["id"]) == 1)
check("an empty comment is refused", "error" in scr.add_comment(seq["id"], "Note", "  ", db_path=DB))
check("an unknown sequence is refused", "error" in scr.add_comment("nope", "Note", "x", db_path=DB))
check("an unknown kind becomes Note", "KIND: Note" in scr.add_comment(seq["id"], "Bogus", "x", db_path=DB)["body"])

print("4. The page and its routes")
os.environ.setdefault("ADMIN_PIN", "4242")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as _app
cl = _app.app.test_client()
check("signed out, the API is refused", cl.get("/api/screens").status_code == 403)
with cl.session_transaction() as s_:
    s_["role"] = "manager"; s_["authenticated"] = True
check("a manager is refused while the dial says admin", cl.get("/api/screens").status_code == 403
      and cl.get(f"/admin/screens/file/screenshots/{s0['folder']}/{s0['steps'][0]['file']}").status_code == 403)
db.set_app_setting("screens_viewer_role", "manager")
check("the dial opens it to managers", cl.get("/api/screens").status_code == 200)
db.set_app_setting("screens_viewer_role", "admin")
with cl.session_transaction() as s_:
    s_["role"] = "admin"
rp = cl.get("/admin/screens")
check("the page renders for an admin", rp.status_code == 200 and b"Screens" in rp.data)
ra = cl.get("/api/screens").get_json()
check("the API returns the catalogue with kinds and counts", ra["sequences"] and ra["kinds"] and "comment_counts" in ra)
rf = cl.get(f"/admin/screens/file/screenshots/{s0['folder']}/{s0['steps'][0]['file']}")
check("a screenshot is served", rf.status_code == 200 and rf.data[:4] == b"\x89PNG", rf.status_code)
check("climbing out of the folder is 404", cl.get("/admin/screens/file/screenshots/..%2F..%2F..%2Fapp.py").status_code == 404)
rc = cl.post(f"/api/screens/{seq['id']}/comments", json={"kind": "Submit for review", "text": "Please review."})
check("the page's comment posts to the mailbox", rc.status_code == 200 and rc.get_json()["post"]["author"] == "screens-page",
      rc.get_json())
check("and shows in the thread", any(p["id"] == rc.get_json()["post"]["id"]
                                     for p in cl.get(f"/api/screens/{seq['id']}/comments").get_json()["comments"]))

print("5. Try it")
rd = cl.get("/admin/screens/demo/nope")
check("an unknown demo is 404", rd.status_code == 404)
demos = [d["url"] for s in cat["sequences"] for d in s.get("demo", [])]
check("every demo is a same-site page", demos and all(u.startswith("/") and not u.startswith("//") for u in demos), demos)
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, start_time, "
                 "course, registration_url, registration_url_status) VALUES (9501, 's9.99 DEMO LINKS', '2099-01-06', "
                 "'San Antonio', 'active', '9-hole', 'Shotgun', '16:30', 'Demo Links GC', "
                 "'https://www.thegolffellowship.com/product-page/s9-99-demo-links', 'verified')")
    conn.execute("INSERT OR IGNORE INTO customers (customer_id, first_name, last_name) VALUES (18, 'Kerry', 'Niester')")
    conn.commit()
ri = cl.get("/admin/screens/demo/invitation")
from email_parser import invitations as _inv
toks = [t for t in __import__("re").findall(r"/rsvp/([A-Za-z0-9_.-]+)", ri.get_data(as_text=True))]
check("the invitation demo renders with PREVIEW links only", ri.status_code == 200 and toks
      and all((_inv.verify_token(t) or {}).get("p") == 1 for t in toks), (ri.status_code, len(toks)))
rr = cl.get("/admin/screens/demo/payment-reminder")
check("the reminder demo renders the framed reminder", rr.status_code == 200 and b"Complete Registration" in rr.data,
      rr.status_code)
with cl.session_transaction() as s_:
    s_["role"] = "manager"
check("a demo needs the Screens role", cl.get("/admin/screens/demo/invitation").status_code == 403)
with cl.session_transaction() as s_:
    s_["role"] = "admin"

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
