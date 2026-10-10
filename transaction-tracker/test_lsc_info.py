"""LONE STAR CUP EVENT INFO (Kerry 10/8, CoS #1428): /member/lonestarcup/info
renders SCHEDULE | TEAMS | FORMATS with every anchor Track A's HOW IT WORKS
pill and the preview link to, teams from the live dial's pairs by pool, and
no dollars. Run: python3 test_lsc_info.py"""
import contextlib, io, json, logging, os, sqlite3, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-only"); os.environ["TGF_REHEARSAL"] = "1"
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as appmod
    from email_parser import database as db
    db.init_db(DB)
F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond: F.append(label)

c = sqlite3.connect(DB)
for cid, f, l in [(9001, "Neal", "Cloer"), (9002, "John", "Wade"), (9003, "Matt", "Jenkins"), (9004, "Mike", "Jenkins"),
                  (9011, "Kerry", "Niester"), (9012, "Michael", "Mesa"), (9013, "Mary", "Wade"), (9014, "Ryan", "South")]:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, f, l))
c.commit(); c.close()
db.set_app_setting("lsc_matches", json.dumps({"event_id": 3329, "pairs": {
    "rule": "Fixed two-person teams (a note, as on the live dial)", "source": "CoS #1343",
    "austin": [{"id": "A1", "cids": [9001, 9002], "pool": "low", "combined_ch": 13},
               {"id": "A2", "cids": [9003, 9004], "pool": "high", "combined_ch": 18}],
    "sa": [{"id": "S1", "cids": [9011, 9012], "pool": "low", "combined_ch": 2},
           {"id": "S2", "cids": [9014, 9013], "pool": "high", "combined_ch": 26}]},
    "sessions": [{"id": "sat-am", "matches": [{"id": "M1"}]}]}), db_path=DB)

cl = appmod.app.test_client()
r = cl.get("/member/lonestarcup/info")
h = r.get_data(as_text=True)
check("the page is public and renders", r.status_code == 200, r.status_code)
for a in ("schedule", "teams", "formats", "fourball", "foursomes", "singles", "skins"):
    check(f"anchor #{a} exists", f'id="{a}"' in h)
check("pairs from the dial, by pool", "Low pool" in h and "High pool" in h and "Cloer &amp; John Wade" in h, h[h.find("Low pool") - 200:h.find("Low pool") + 400])
check("a shared last name gets the first name", "Matt Jenkins &amp; Mike Jenkins" in h and " / " not in h[h.find("Low pool"):h.find("Saturday pairs play")] and "Ryan South" not in h)
check("captains", "Matt Jenkins (C)" in h and "Rob Callaway (C)" in h)
check("before the draw it says so", "posted after Thursday" in h)
check("no dollars", "$" not in h)
check("the Cup logo, white-border version on the navy banner", "/static/lsc-logo-dark.png" in h and os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "lsc-logo-dark.png")))
check("the standalone page wires the shared script", "/static/js/lsc-info.js" in h and "Share link" in h and "Download PDF" in h)
check("?print=1 prints", "print" in h)

# The same body is the EVENT INFO view on LEADERBOARD > Lone Star Cup
# (Kerry 10/8: "I need that added to the Lone Star cup Members page").
r = cl.get("/member/lonestarcup/info?embed=1")
e = r.get_data(as_text=True)
check("the embed is public and bare", r.status_code == 200 and "<html" not in e.lower() and 'class="lsc-info embed"' in e, r.status_code)
check("the embed carries every section and row hook", all(f'data-sec="{k}"' in e for k in ("schedule", "teams", "formats"))
      and all(f'data-a="{k}"' in e for k in ("fourball", "foursomes", "singles", "skins")))
check("the embed adds no page ids (no clash on the Cup tab)", 'id="teams"' not in e and 'id="skins"' not in e)
check("the embed has the same pairs", "Cloer &amp; John Wade" in e and "no dollars" and "$" not in e)
check("Download PDF opens the printable page", "/member/lonestarcup/info?print=1" in e)
check("Cup ink is navy, not black", "#1B1B1B" not in e)

# members and alumni print a capital LAST name (Kerry 10/8 standard)
db.set_app_setting("lsc_handicap_lock", json.dumps({"3329": {"players": {str(c): {"ch": 5} for c in
    (9001, 9002, 9003, 9004, 9011, 9012, 9013, 9014)}}}), db_path=DB)
db.set_app_setting("lsc_member_ruling", json.dumps({"3329": {"guests": [9014]}}), db_path=DB)
e = cl.get("/member/lonestarcup/info?embed=1").get_data(as_text=True)
check("members/alumni LAST in caps, the guest not", "CLOER &amp; John WADE" in e and "Matt JENKINS &amp; Mike JENKINS" in e
      and "NIESTER &amp; MESA" in e and "South &amp; Mary WADE" in e, e[e.find("Low pool"):e.find("Saturday pairs")])

# the practice-round head count comes from the roster of the Friday add-on event
check("no practice event, no count", "players</dd>" not in e)

# the Cup tab offers the view and loads it from the embed
ct = cl.get("/member/lonestarcup").get_data(as_text=True)
check("Cup tab: Event Info view + shared script", '"Event Info"' in ct and "/member/lonestarcup/info?embed=1" in ct
      and "/static/js/lsc-info.js" in ct and "?info=" in ct)
# Kerry 10/10: "Formats does not show detail on how each format is played"
fm = cl.get("/member/lonestarcup/info").get_data(as_text=True)
check("Formats opens with how each session is played, before the handicaps",
      fm.index("How each session is played") < fm.index("Handicaps &amp; points") < fm.index("Chapman relief rule")
      and "better net ball" in fm and "alternates shots until it" in fm and "One against one" in fm
      and "can't win the hole" in fm)
check("Skins ties carry the 10/9 session carryover ruling", "passes its whole pot to the next session" in fm
      and "No carryover" not in fm)
print("ALL PASS" if not F else f"{len(F)} FAILED: {F}"); sys.exit(1 if F else 0)
