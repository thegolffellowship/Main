"""THE HANDICAP ASK (Kerry 2026-10-16, "Build it"; mockups approved the same
day). A new player with no handicap is emailed a signed link; GHIN number +
latest index sets 75%; another service sets 75% and asks a manager to check;
no handicap sends their usual 18-hole score to the manager. Nothing is sent
unless the dial is on AND the wording carries Kerry's stamp.

Run: python3 test_handicap_ask.py
"""
import contextlib, io, logging, os, sqlite3, sys, tempfile
from datetime import date, datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    DB = os.environ["DATABASE_PATH"]
    db.init_db(DB)
    import app as appmod  # noqa: E402
from email_parser import handicap_ask as ha, handicap_warnings as hw  # noqa: E402
from email_parser.timezone_utils import today_central  # noqa: E402

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {str(detail)[:400]}"))
    if not cond:
        F.append(label)


TODAY = today_central()
EV_DATE = (TODAY + timedelta(days=4)).isoformat()
EV = "s9.99 Test Canyons"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
db._ensure_scoring_tables._ensure_inner(c)
# A fresh test DB: clear any boot-seeded rows so only this fixture is on a roster.
for _t in ("items", "customer_emails", "customers", "events", "rsvps"):
    c.execute(f"DELETE FROM {_t}")
c.execute("INSERT INTO events (id, item_name, event_date, course, chapter, format, status) "
          "VALUES (9001, ?, ?, 'TPC San Antonio', 'San Antonio', '9 Holes', 'active')", (EV, EV_DATE))
people = [(1, "Gus", "Ghin"), (2, "Olly", "Other"), (3, "Nora", "None"), (4, "Mia", "Manager"),
          (5, "Ned", "Noemail")]
for cid, fn, ln in people:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
              "VALUES (?,?,?, 'first_timer')", (cid, fn, ln))
    if cid != 5:
        c.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (?,?,1)",
                  (cid, f"p{cid}@example.com"))
    c.execute("INSERT INTO items (email_uid, merchant, customer, customer_id, customer_email, item_name, "
              "holes, transaction_status, order_date, created_at, event_id) "
              "VALUES (?,'GoDaddy',?,?,?,?,'9','active',?,?,9001)",
              (f"u{cid}", f"{fn} {ln}", cid, f"p{cid}@example.com", EV, TODAY.isoformat(),
               TODAY.isoformat() + " 10:00:00"))
c.commit(); c.close()
db.set_starting_handicap(4, 20.0, set_by="manager:test", db_path=DB)

print("parsing")
check("14.2 is an index", ha.parse_index("14.2") == 14.2)
check("+2.1 is a plus handicap, stored negative", ha.parse_index("+2.1") == -2.1)
check("a comma decimal works", ha.parse_index("9,5") == 9.5)
check("nonsense is refused", ha.parse_index("abc") is None and ha.parse_index("88") is None)
check("75% of 14.2 is 10.7", ha.starting_from_index(14.2) == 10.7)
check("GHIN needs the number AND the latest index",
      ha.validate({"kind": "ghin", "ghin": "1234567"}).get("error")
      and ha.validate({"kind": "ghin", "index": "14.2"}).get("error")
      and ha.validate({"kind": "ghin", "ghin": "1234567", "index": "14.2"}).get("index") == 14.2)
check("another service must be one of the list",
      ha.validate({"kind": "other", "service": "Made Up", "index": "10"}).get("error"))
check("Other needs a name", ha.validate({"kind": "other", "service": "Other", "index": "10"}).get("error"))
check("no handicap asks a RANGE for 18 holes (Kerry: between x and x)",
      ha.validate({"kind": "none", "score_low": "45", "score_high": "50"}).get("error")
      and ha.validate({"kind": "none", "score_low": "90", "score_high": "100"}).get("score_high") == 100)
check("a range typed backwards is put right", ha.validate(
      {"kind": "none", "score_low": "105", "score_high": "95"}).get("score_low") == 95)

print("who is asked")
pl = ha.plan(db_path=DB)
asked = {p["customer_id"] for p in pl["asks"]}
check("the players with no handicap and an email are asked", asked == {1, 2, 3}, pl["asks"])
check("a player a manager already set is not asked", 4 not in asked)
check("no email: skipped and said so", [s["customer_id"] for s in pl["skipped"]] == [5])

print("the locks")
SENT = []
fake = lambda to, s, h: SENT.append((to, s, h)) or True  # noqa: E731
noon = datetime.combine(TODAY, datetime.min.time()).replace(hour=12)
check("dial off: nothing", ha.auto_check(now=noon, db_path=DB, sender=fake).get("skipped") and not SENT)
db.set_app_setting("handicap_ask_auto", "on", db_path=DB)
check("dial on but wording not stamped: nothing",
      ha.auto_check(now=noon, db_path=DB, sender=fake).get("skipped") == "wording not approved" and not SENT)
db.set_app_setting("handicap_ask_approved", ha.template_hash(), db_path=DB)
res = ha.auto_check(now=noon.replace(hour=22), db_path=DB, sender=fake)
check("the first ask goes at once, any hour (Kerry: as soon as we get a registration)",
      len(SENT) == 3 and len(res["asks"]["sent"]) == 3, res)
src_app = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")).read()
check("the inbox check runs the ask right after saving new orders",
      "from email_parser.handicap_ask import auto_check as _hcp_ask" in src_app)
subj = SENT[0][1]
check("the subject is personal", subj.startswith("One quick thing before") and "{" not in subj, subj)
body = SENT[0][2]
check("the email says it is for the team game", "team game" in body and "Add my handicap" in body)
check("the email carries a signed /handicap/ link", "/handicap/" in body)
SENT.clear()
ha.auto_check(now=noon, db_path=DB, sender=fake)
check("asked once per person, not every run", not SENT, SENT)

print("the page")
cl = appmod.app.test_client()
tok = {cid: ha.make_token(cid, 9001) for cid in (1, 2, 3)}
r = cl.get(f"/handicap/{tok[1]}")
page = r.data.decode()
check("the link opens the page", r.status_code == 200 and "Your handicap, Gus" in page, r.status_code)
check("the TGF-handicap note is the highlighted box at the top", 'class="tgf-hcp"' in page
      and page.index('class="tgf-hcp"') < page.index("I have a GHIN number"))
check("the three choices and the 27-hole note", "I have a GHIN number" in page
      and "another handicap service" in page and "27 holes" in page)
check("opening it saves nothing (mail scanners)", not (ha.load_state(DB).get("1") or {}).get("answer"))
check("a bad link says so", cl.get("/handicap/abc.def").status_code == 400)
r = cl.post(f"/handicap/{tok[1]}", data={"go": "ghin", "ghin": "1234567", "index_ghin": ""})
check("a missing index is refused with the reason", r.status_code == 400
      and b"latest handicap index" in r.data)
check("the Venmo box says what they can win: team game, closest to the pin, side games",
      "team game, a closest to the pin, or a side game you entered" in page)
check("the page asks for Venmo, with a link to get it", 'name="venmo"' in page
      and "I don't have Venmo yet" in page and "https://venmo.com/" in page)
r = cl.post(f"/handicap/{tok[1]}", data={"go": "ghin", "ghin": "1234567", "index_ghin": "14.2",
                                          "venmo": "not a handle!"})
check("a bad Venmo username is refused with the reason", r.status_code == 400
      and b"Venmo username" in r.data)
r = cl.post(f"/handicap/{tok[1]}", data={"go": "ghin", "ghin": "1234567", "index_ghin": "14.2",
                                          "venmo": "@Gus-Ghin-7"})
check("GHIN answer: thanks page with 10.7", r.status_code == 200 and b"10.7" in r.data
      and b"27 holes" in r.data, r.data[:300])
con = sqlite3.connect(DB)
row = con.execute("SELECT starting_handicap_18, starting_handicap_set_by, ghin_number FROM customers "
                  "WHERE customer_id = 1").fetchone()
check("Venmo saved bare (no @) where payouts read it",
      con.execute("SELECT venmo_username FROM customers WHERE customer_id = 1").fetchone()[0] == "Gus-Ghin-7")
check("the thanks page confirms the Venmo", b"Venmo saved: @Gus-Ghin-7" in r.data)
check("starting handicap 10.7 set, GHIN saved", row[0] == 10.7 and row[1].startswith("handicap_ask")
      and row[2] == "1234567", row)
r = cl.post(f"/handicap/{tok[2]}", data={"kind": "other", "go": "ghin", "service": "TheGrint",
                                          "index_other": "17.8"})
check("the ticked choice wins over the keyboard's Go (it submits the first Save)",
      r.status_code == 200, r.data[-400:])
check("other service: 13.4 applied, manager will confirm",
      r.status_code == 200 and b"13.4" in r.data and b"confirm" in r.data)
check("the thanks page shows the temporary starting handicap and the 27-hole rule",
      b"temporary starting handicap" in r.data and b"27 holes" in r.data and b"17.8 index you entered" in r.data)
r = cl.post(f"/handicap/{tok[3]}", data={"go": "none", "score_low": "90", "score_high": "100", "no_venmo": "1"})
check("no Venmo yet: told to tap the same email button later, with the link",
      b"tap the button in our email again" in r.data and b"Get Venmo" in r.data)
check("no doubled Thanks", b"Thanks. The chapter" not in r.data)

check("no handicap: manager will set it", r.status_code == 200 and b"chapter manager will set" in r.data)
check("...and nothing was set", con.execute("SELECT starting_handicap_18 FROM customers WHERE customer_id = 3")
      .fetchone()[0] is None)
pg = cl.get(f"/handicap/{tok[3]}").data.decode()
check("back on the same link: only the Venmo question", "Add your Venmo" in pg
      and "I have a GHIN number" not in pg, pg[-800:])
r = cl.post(f"/handicap/{tok[3]}", data={"venmo_only": "1", "venmo": "@Nora-None"})
check("adding Venmo later saves it to the profile", r.status_code == 200
      and con.execute("SELECT venmo_username FROM customers WHERE customer_id = 3").fetchone()[0] == "Nora-None"
      and ha.load_state(DB)["3"]["answer"]["venmo"] == "Nora-None")
m = hw.missing_handicaps(9001, db_path=DB)
st = {a["customer_id"]: a["status"] for a in m["asks"]}
check("the manager banner: Set from GHIN / Check this one / Needs a number",
      st == {1: "set", 2: "check", 3: "need"}, m["asks"])
check("Nora (score only) is still in the missing list", [p["customer_id"] for p in m["players"]] == [3, 5]
      or {p["customer_id"] for p in m["players"]} == {3, 5}, m["players"])
check("the banner line names the range", "usually shoots 90–100 for 18" in
      next(a["line"] for a in m["asks"] if a["customer_id"] == 3))
check("the banner shows Venmo or that they have none",
      "Venmo @Gus-Ghin-7" in next(a["line"] for a in m["asks"] if a["customer_id"] == 1)
      and "Venmo @Nora-None" in next(a["line"] for a in m["asks"] if a["customer_id"] == 3))
check("a handle already on file: the page doesn't ask again",
      'name="venmo"' not in cl.get(f"/handicap/{tok[1]}").data.decode())
pv = ha.make_token(4, 9001, preview=True)
cl.post(f"/handicap/{pv}", data={"go": "ghin", "ghin": "7654321", "index_ghin": "2.0"})
check("a preview link saves nothing", con.execute("SELECT starting_handicap_18, ghin_number FROM customers "
      "WHERE customer_id = 4").fetchone() == (20.0, None))
ha.make_token  # noqa
r2 = cl.post(f"/handicap/{ha.make_token(4, 9001)}", data={"go": "ghin", "ghin": "7654321", "index_ghin": "2.0"})
check("a number a manager typed is never overwritten by the player",
      con.execute("SELECT starting_handicap_18 FROM customers WHERE customer_id = 4").fetchone()[0] == 20.0)

print("manager confirm")
mg = appmod.app.test_client()
with mg.session_transaction() as s:
    s["role"] = "manager"
check("anonymous cannot confirm", cl.post("/api/handicap-ask/2/confirm").status_code in (401, 403))
check("manager taps Looks right", mg.post("/api/handicap-ask/2/confirm").status_code == 200
      and ha.load_state(DB)["2"]["status"] == "confirmed")
check("the events banner renders the asks", "hcpAskRowsHtml" in open(
      os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "events.html")).read())

print("reminder")
SENT.clear()
st = ha.load_state(DB)
for k in st:
    st[k]["sent_at"] = (TODAY - timedelta(days=3)).isoformat() + "T12:00:00Z"
st["6"] = {"sent_at": st["1"]["sent_at"]}
ha._save_state(st, DB)
con.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (6, 'Rae', 'Reminder')")
con.execute("INSERT INTO customer_emails (customer_id, email, is_primary) VALUES (6, 'p6@example.com', 1)")
con.execute("INSERT INTO items (email_uid, merchant, customer, customer_id, customer_email, item_name, holes, "
            "transaction_status, order_date, created_at, event_id) VALUES ('u6','GoDaddy','Rae Reminder',6,"
            "'p6@example.com',?,'9','active',?,?,9001)", (EV, TODAY.isoformat(), TODAY.isoformat() + " 10:00:00"))
con.commit()
far = noon
ha.auto_check(now=far, db_path=DB, sender=fake)
check("no reminder while the event is 4 days out", not SENT, SENT)
near = datetime.combine(TODAY + timedelta(days=2), datetime.min.time()).replace(hour=9)
ha.auto_check(now=near.replace(hour=23), db_path=DB, sender=fake)
check("no reminder at night", not SENT, SENT)
ha.auto_check(now=near, db_path=DB, sender=fake)
check("one reminder, 2 days before, only to who has not answered",
      [s[0] for s in SENT] == ["p6@example.com"] and SENT[0][1].startswith("Reminder"), SENT)
SENT.clear()
ha.auto_check(now=near, db_path=DB, sender=fake)
check("never a second reminder", not SENT)

print("source guards")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "handicap_ask.html")).read()
check("the page keeps the one 560px phone rule", "@media (max-width: 560px)" in src and "768" not in src)
check("inputs are 16px (no iOS zoom)", "font-size:16px" in src)

# Same-day sign-up (Kerry 10/20, Adam Wilson: "there should be no limitations
# on an email being sent to someone that we don't have a handicap for")
_c2 = sqlite3.connect(DB); _c2.row_factory = sqlite3.Row
check("an event dated TODAY is in the ask window",
      9001 in [e["id"] for e in ha._upcoming_events(_c2, EV_DATE)])
_c2.close()

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILED: {F}"))
sys.exit(1 if F else 0)
