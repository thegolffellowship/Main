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
check("every status is a known one", all(s["status"] in ("current", "built", "mockup", "superseded", "reference", "archived", "needed")
                                         for s in cat["sequences"]))
check("nothing on disk is left uncatalogued", cat["not_catalogued"] == [], cat["not_catalogued"])

print("1b. Screenshots stay current (Kerry 10/26: an absolute requirement)")
from email_parser import screens_capture as sc
stale = [x["id"] for x in cat["sequences"] if x.get("watch") and x.get("watch_hash") != sc.watch_hash(x["watch"])]
check("every sequence's screenshots match the code they show (else run: python3 tools/screens_refresh.py <id>)",
      not stale, stale)
nowatch = [x["id"] for x in cat["sequences"] if any(st.get("capture") for st in x["steps"]) and not x.get("watch")]
check("every sequence with capture recipes watches its source files", not nowatch, nowatch)
bad = [(x["id"], st["file"]) for x in cat["sequences"] for st in x["steps"]
       if st.get("capture", {}).get("render") and st["capture"]["render"] not in sc.RENDERS]
check("every render recipe names a real builder", not bad, bad)

n_before = len(db.get_all_events(db_path=DB))
check("in production, no upcoming event means no render and NO demo event written",
      sc._context(DB) is None and len(db.get_all_events(db_path=DB)) == n_before)

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

print("6. A missed capture is visible; the demo runner holds no credentials (Kerry 10/26)")
import subprocess as _sp, shutil as _sh
def _failed_rows():
    with db._connect(DB) as conn:
        return [r[0] for r in conn.execute("SELECT description FROM agent_action_log "
                                           "WHERE action_type = 'screens_capture_failed' ORDER BY id")]
_ca, _cd = sc.capture_all, sc.capture_demos
sc.capture_demos = lambda *a, **k: {"captured": [], "errors": []}
sc.capture_all = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no Chromium"))
r6 = sc.capture_live(force=True, db_path=DB)
check("a capture that blows up returns the error", "no Chromium" in (r6.get("error") or ""), r6)
check("and writes screens_capture_failed", any("FAILED" in d and "no Chromium" in d for d in _failed_rows()),
      _failed_rows())
sc.capture_all = lambda *a, **k: {"captured": ["x/1.png"], "errors": [{"name": "x/2.png", "error": "Bitter did not load"}]}
sc.capture_live(force=True, db_path=DB)
check("a partial capture writes screens_capture_failed too", any("partial" in d and "Bitter" in d for d in _failed_rows()),
      _failed_rows())
n_fail = len(_failed_rows())
sc.capture_all = lambda *a, **k: {"captured": ["x/1.png"], "errors": []}
sc.capture_live(force=True, db_path=DB)
check("a clean capture writes no failure", len(_failed_rows()) == n_fail)
sc.capture_all, sc.capture_demos = _ca, _cd
_sh.rmtree(sc.live_root(), ignore_errors=True)
check("the live capture runs the demo recipes too",
      'capture_demos(str(root), live=True)' in open("email_parser/screens_capture.py").read())

seen = {}
_run = _sp.run
def _fake_run(args, **kw):
    seen["args"], seen["env"] = args, kw.get("env") or {}
    return _sp.CompletedProcess(args, 0, stdout='{"captured": [], "errors": []}\n', stderr="")
for k, v in (("AZURE_CLIENT_SECRET", "s"), ("EMAIL_ADDRESS", "a@b.c"), ("ADMIN_PIN", "1"), ("BREVO_API_KEY", "k"),
             ("HUBSPOT_TOKEN", "t"), ("STRIPE_SECRET", "x")):
    os.environ[k] = v
_sp.run = _fake_run
try:
    rd6 = sc.capture_demos("", live=False)
finally:
    _sp.run = _run
env6 = seen.get("env") or {}
check("capture_demos runs tools/screens_demo.py in its own process",
      seen.get("args") and seen["args"][1].endswith("tools/screens_demo.py") and rd6 == {"captured": [], "errors": []},
      seen.get("args"))
check("on a throwaway database, never this one", env6.get("DATABASE_PATH", "").endswith(".db")
      and env6.get("DATABASE_PATH") != DB and env6.get("SCREENS_DEMO") == "1")
check("with no mail, money, PIN or API credential", not [k for k in env6 if k in (
      "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS", "ADMIN_PIN", "BREVO_API_KEY", "HUBSPOT_TOKEN", "STRIPE_SECRET")],
      [k for k in env6 if "PIN" in k or "SECRET" in k or "TOKEN" in k])
check("and its own session key", env6.get("SECRET_KEY") and env6["SECRET_KEY"] != os.environ.get("SECRET_KEY"))
bare = {k: v for k, v in os.environ.items() if k not in ("SCREENS_DEMO",)}
bare["DATABASE_PATH"] = DB
rr6 = _sp.run([sys.executable, "tools/screens_demo.py", "--repo"], env=bare, capture_output=True, text=True, timeout=60)
check("the demo runner refuses to start outside capture_demos", rr6.returncode != 0 and "throwaway" in rr6.stderr,
      rr6.stderr[-200:])
known = {"event", "t", "t2"}
import string as _string
bad6 = [(x["id"], st["file"]) for x in cat["sequences"] for st in x["steps"] if "demo" in (st.get("capture") or {})
        and {f for _, f, _, _ in _string.Formatter().parse(st["capture"].get("path", "")) if f} - known]
check("every demo recipe names only what the demo seeds (event, t, t2)", not bad6, bad6)
demo_seqs = [x["id"] for x in cat["sequences"] if any("demo" in (st.get("capture") or {}) for st in x["steps"])]
check("live scoring and the member tee sheet are taken from the demo",
      {"score-entry-live", "member-teesheet"} <= set(demo_seqs), demo_seqs)
manual = [x["id"] for x in cat["sequences"] if x["status"] == "current" and x["steps"]
          and not any(st.get("capture") for st in x["steps"]) and not x.get("automation")]
check("every current sequence is automated or says why not", not manual, manual)

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
