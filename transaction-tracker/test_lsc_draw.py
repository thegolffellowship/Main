"""LONE STAR CUP DRAW into the live dial (Kerry 10/8 via CoS #1432). The
entrants come from lsc_matches.pairs / lsc_handicap_lock, each landed match
is written into its session, the server re-checks the page's rules, and a
clear reverses it. Data shaped like production. Run: python3 test_lsc_draw.py"""
import contextlib, io, json, logging, os, random, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-only"); os.environ["TGF_REHEARSAL"] = "1"; os.environ["ADMIN_PIN"] = "4242"
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as appmod
    from email_parser import database as db
    db.init_db(DB)
from email_parser import lsc_draw, lsc_cup  # noqa: E402
F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond: F.append(label)

# the locked table and pairs as on production 10/8 (abridged names)
LOCK = {"13": ("Luke Youngs", "austin", 0.2), "7": ("Matt Jenkins", "austin", 2.8), "109": ("Neal Cloer", "austin", 4.2),
        "438": ("Chris Cannon", "austin", 7.6), "4": ("John Wade", "austin", 8.6), "672": ("David Wetz", "austin", 7.7),
        "834": ("Walter Hogue", "austin", 10.9), "37": ("Jay Hogue", "austin", 12.2), "304": ("Julius Jenkins", "austin", 13.2),
        "315": ("Kyle Franz", "austin", 15.2), "294": ("Mike Jenkins", "austin", 15.4), "62": ("Bill Barstow", "austin", 17.8),
        "30": ("Matt Sharp", "austin", 20.2), "688": ("Kaleb McDonnell", "austin", 20.2),
        "136": ("Pat Youngs", "sa", -1.0), "703": ("Michael Mesa", "sa", 0.4), "18": ("Kerry Niester", "sa", 1.2),
        "88": ("Jeff Young", "sa", 2.0), "87": ("Adam Baker", "sa", 7.2), "82": ("Luke Mazanec", "sa", 7.6),
        "24": ("Daniel South", "sa", 9.8), "42": ("Gus Vasquez", "sa", 10.6), "306": ("James Wilson Jr", "sa", 12.4),
        "35": ("Rob Callaway", "sa", 12.0), "130": ("Chuck Fehlis", "sa", 13.0), "23": ("Mary Wade", "sa", 16.4),
        "291": ("Will Peterson", "sa", 16.6), "6": ("Jeff Rideout", "sa", 27.0)}
db.set_app_setting("lsc_handicap_lock", json.dumps({"3329": {"players": {
    c: {"name": n, "team": t, "index": i, "ch": round(i)} for c, (n, t, i) in LOCK.items()}}}), db_path=DB)
def pr(i, a, b, pool, ci): return {"id": i, "cids": [a, b], "pool": pool, "combined_index": ci}
dial = {"event_id": 3329, "board_live": False, "defending_champion": "sa",
        "pairs": {"rule": "a note", "source": "CoS #1343",
                  "sa": [pr("SA-P1", 136, 88, "low", 1.0), pr("SA-P2", 18, 703, "low", 1.6), pr("SA-P3", 87, 82, "low", 14.8),
                         pr("SA-P5", 42, 130, "high", 23.6), pr("SA-P4", 35, 306, "high", 24.4), pr("SA-P6", 24, 23, "high", 26.2),
                         pr("SA-P7", 291, 6, "high", 43.6)],
                  "austin": [pr("AUS-P1", 13, 438, "low", 7.8), pr("AUS-P2", 109, 4, "low", 12.8), pr("AUS-P7", 7, 294, "low", 18.2),
                             pr("AUS-P3", 37, 834, "high", 23.1), pr("AUS-P4", 672, 62, "high", 25.5),
                             pr("AUS-P6", 304, 688, "high", 33.4), pr("AUS-P5", 315, 30, "high", 35.4)]},
        "sessions": [
            {"id": "sat-am", "label": "FOURBALL", "format": "fourball", "date": "2026-10-10", "n_holes": 18, "se_round": None,
             "matches": [{"id": "SAT-AM-1", "tee_time": "8:30", "austin": [7, 4], "sa": [35, 130]}]},
            {"id": "sat-pm", "label": "FOURSOMES", "format": "chapman", "date": "2026-10-10", "n_holes": 18, "se_round": None,
             "matches": [{"id": "SAT-PM-1", "tee_time": "1:30", "austin": [30, 438], "sa": [23, 291]}]},
            {"id": "sun", "label": "SINGLES", "format": "singles", "date": "2026-10-11", "n_holes": 18, "se_round": None,
             "matches": [{"id": "SUN-1", "tee_time": "8:30", "austin": [7], "sa": [35]}]}]}
db.set_app_setting("lsc_matches", json.dumps(dial), db_path=DB)
def dial_now(): return json.loads(db.get_app_setting("lsc_matches", db_path=DB))
def sess(sid): return next(s for s in dial_now()["sessions"] if s["id"] == sid)

P = lsc_draw.pools(3329, db_path=DB)
check("Saturday pools: 3 v 3 low, 4 v 4 high, from the dial's pairs",
      [len(P["fb"][p][t]) for p in ("low", "high") for t in ("austin", "sa")] == [3, 3, 4, 4])
check("pair labels from the lock, index beside", P["fb"]["low"]["austin"][2]["label"] == "Matt Jenkins & Mike Jenkins"
      and P["fb"]["low"]["austin"][2]["idx"] == 18.2, P["fb"]["low"]["austin"])
check("Sunday Low 7 Austin by locked raw index (Track B #1412)",
      [e["label"] for e in P["sg"]["low"]["austin"]] == ["Luke Youngs", "Matt Jenkins", "Neal Cloer", "Chris Cannon",
                                                       "David Wetz", "John Wade", "Walter Hogue"], [e["label"] for e in P["sg"]["low"]["austin"]])
check("Sunday Low 7 SA by locked raw index",
      [e["label"].title() for e in P["sg"]["low"]["sa"]] == ["Pat Youngs", "Michael Mesa", "Kerry Niester", "Jeff Young",
                                                   "Adam Baker", "Luke Mazanec", "Daniel South"])

r = lsc_draw.land(3329, "fs", "low", "AUS-P1", "SA-P1", db_path=DB)
check("FOURSOMES refuses before FOURBALL is drawn", r.get("error") == "Draw Saturday AM first", r)
r = lsc_draw.land(3329, "fb", "low", "AUS-P1", "SA-P1", db_path=DB)
am = sess("sat-am")
check("first landed match drops the staged demo matches and goes live",
      r.get("ok") and r["dropped_staged"] == 1 and [m["id"] for m in am["matches"]] == ["SAT-AM-1"]
      and am["matches"][0]["austin"] == [13, 438] and am["matches"][0]["tee_time"] == "8:30", am)
check("the other sessions' staged matches are untouched", len(sess("sat-pm")["matches"]) == 1 and len(sess("sun")["matches"]) == 1)
check("an entrant can't be drawn twice", lsc_draw.land(3329, "fb", "low", "AUS-P1", "SA-P2", db_path=DB).get("error"))
check("an entrant from another pool is refused", lsc_draw.land(3329, "fb", "low", "AUS-P3", "SA-P2", db_path=DB).get("error"))
r = lsc_draw.land(3329, "fb", "high", "AUS-P4", "SA-P6", db_path=DB)
check("high pool numbering starts at 4 (9:00)", r["match"]["id"] == "SAT-AM-4" and r["match"]["tee_time"] == "9:00", r)

def finish(sk):
    rnd = random.Random(7)
    st = lsc_draw.state(3329, db_path=DB)[sk]
    for pool in ("low", "high"):
        while len(st[pool]) < len(P[sk][pool]["austin"]):
            done = st[pool]
            ra = [e["key"] for e in P[sk][pool]["austin"] if not any(m[0] == e["key"] for m in done)]
            rs = [e["key"] for e in P[sk][pool]["sa"] if not any(m[1] == e["key"] for m in done)]
            ok = None
            for a in ra:
                for s in rs:
                    if lsc_draw.land(3329, sk, pool, a, s, db_path=DB).get("ok"):
                        ok = True; break
                if ok: break
            assert ok, (sk, pool)
            st = lsc_draw.state(3329, db_path=DB)[sk]
finish("fb")
am = sess("sat-am")
check("FOURBALL fully drawn: 7 matches, numbered 1-7, tee 8:30..9:30",
      [m["id"] for m in am["matches"]] == [f"SAT-AM-{i}" for i in range(1, 8)]
      and [m["tee_time"] for m in am["matches"]] == ["8:30", "8:40", "8:50", "9:00", "9:10", "9:20", "9:30"], am["matches"])
fb = lsc_draw.state(3329, db_path=DB)["fb"]
a0, s0 = fb["low"][0]
check("a FOURSOMES pairing that repeats FOURBALL is refused",
      lsc_draw.land(3329, "fs", "low", a0, s0, db_path=DB).get("error") == "that pairing already met on Saturday AM")
finish("fs")
fs = lsc_draw.state(3329, db_path=DB)["fs"]
check("no FOURSOMES match repeats a FOURBALL match",
      not ({tuple(m) for p in ("low", "high") for m in fb[p]} & {tuple(m) for p in ("low", "high") for m in fs[p]}))
check("FOURSOMES tee times 1:30..2:30", [m["tee_time"] for m in sess("sat-pm")["matches"]] ==
      ["1:30", "1:40", "1:50", "2:00", "2:10", "2:20", "2:30"])
finish("sg")
sun = sess("sun")["matches"]
check("SINGLES: 14 matches, two per tee time, low 1-7 then high 8-14",
      len(sun) == 14 and [m["tee_time"] for m in sun][:4] == ["8:30", "8:30", "8:40", "8:40"] and sun[-1]["tee_time"] == "9:30"
      and all(m["draw"]["pool"] == ("low" if m["draw"]["n"] <= 7 else "high") for m in sun), [m["tee_time"] for m in sun])
b = lsc_cup.lsc_board_payload(db_path=DB)
check("the Cup board reads the drawn dial (28 matches)",
      sum(len(s["matches"]) for s in b.get("sessions") or []) == 28, b.get("sessions") and [len(s["matches"]) for s in b["sessions"]])
check("board_live untouched", dial_now()["board_live"] is False)
r = lsc_draw.clear(3329, "fb", db_path=DB)
check("clearing FOURBALL clears FOURSOMES too, SINGLES stays",
      r.get("ok") and not sess("sat-am")["matches"] and not sess("sat-pm")["matches"] and len(sess("sun")["matches"]) == 14, r)
check("every write is logged", len(db.get_agent_action_log(agent_name="cup-draw", limit=100, db_path=DB)) >= 29)

cl = appmod.app.test_client()
check("the page is admin only", cl.get("/events/3329/cup-draw").status_code in (401, 302, 403))
check("the write is admin only", cl.post("/api/events/3329/cup-draw/land", json={}).status_code in (401, 302, 403))
cl.post("/api/auth/login", json={"pin": "4242"})
h = cl.get("/events/3329/cup-draw")
_k = next(e for e in P["sg"]["low"]["sa"] if e["key"] == "18")
check("members and alumni print a capital LAST name (Kerry 10/8)", _k["label"] == "Kerry NIESTER" and _k["names"] == ["Kerry NIESTER"], _k)
check("the page renders for admin with the live entrants", h.status_code == 200 and "Kerry NIESTER" in h.get_data(as_text=True))
r = cl.post("/api/events/3329/cup-draw/land", json={"session": "fb", "pool": "low", "a": "AUS-P2", "s": "SA-P2"})
check("POST land writes and returns the new state", r.status_code == 200 and r.get_json()["state"]["fb"]["low"] == [["AUS-P2", "SA-P2"]], r.get_json())
r = cl.post("/api/events/3329/cup-draw/land", json={"session": "fb", "pool": "low", "a": "AUS-P2", "s": "SA-P1"})
check("a refused draw is a 409 with the reason", r.status_code == 409 and r.get_json().get("error"))
h = cl.get("/events/3329/cup-draw").get_data(as_text=True)
check("the page opens on the Cup intro and waits for Start The Draw (Kerry 10/8)",
      'id="intro"' in h and 'id="startDraw"' in h and "Start The Draw" in h and "lsc-logo-dark.png" in h)
check("the splash carries the Cup's dates from its rounds (Kerry 10/8)",
      lsc_draw.dates_label(3329, db_path=DB) == "OCTOBER 10\u201311, 2026" and "OCTOBER 10\u201311, 2026" in h
      and "2026 \u00b7 THE DRAW" not in h, lsc_draw.dates_label(3329, db_path=DB))
with db._connect(DB) as _c:
    _c.execute("INSERT INTO events (id, item_name, event_date) VALUES (3330, 'LSC practice', '2026-10-09')"); _c.commit()
db.set_app_setting("oneoff_charges", json.dumps({"3329": {"addons": [{"key": "friday", "event_id": 3330}]}}), db_path=DB)
check("the Friday practice round opens the dates", lsc_draw.dates_label(3329, db_path=DB) == "OCTOBER 9\u201311, 2026",
      lsc_draw.dates_label(3329, db_path=DB))
print("ALL PASS" if not F else f"{len(F)} FAILED: {F}"); sys.exit(1 if F else 0)
