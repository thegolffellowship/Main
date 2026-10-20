"""Kerry's pairings rulings of 2026-10-19 (event 3301 regenerated after them).

Kerry, verbatim:
- "You need to add ALL events into the pairings generator history...LSC too."
- "I kind of like that newer players would be able to get foursomes where
  possible to maximize new connections."
- On solo carts: "We need to look at season totals ... Definitely need to be
  counting our own." and "I definitely don't want someone to have 3 solo
  carts in a season before other qualified solo players have even one."
- He wants the generator's reasoning logged so he can review it.

Covers: season solo totals across entry rows; the solo seat going to the
fewest-solo qualified player (seater AND composition); an entered-group pair
and a Lone Star Cup pair counting as history; no double count of an event with
Golf Genius and entry rows; a 3rd repeat avoided when a zero-count option
exists; newer players in foursomes; the generation log; the preview bridge
saving nothing (no sheet, no blinds, no log setting).

Run: python3 test_pairings_gen_fixes.py
"""
import os, sys, tempfile, logging, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
from email_parser import score_entry as se                       # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []
K = db._pair_key_name


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


def hist(c, a, b, eid, date, rode, source, round_id=None):
    c.execute("INSERT INTO pairing_history (player_a,player_b,event_id,event_date,rode,source,round_id) "
              "VALUES (?,?,?,?,?,?,?)", (a, b, eid, date, rode, source, round_id))


NAMES = ["Kerry Niester", "Jeff Rideout", "Michael Mesa", "Mary Wade", "Michael Murphy",
         "Will Peterson", "Nic Skinner", "Reggie Johnson", "Morris Allen", "Dan Stich",
         "Gus Vasquez"]
CID = {n: 700 + i for i, n in enumerate(NAMES)}

with db._connect(DB) as c:
    db._ensure_pairing_tables(c)
    for n, cid in CID.items():
        fn, ln = n.split(" ", 1)
        c.execute("INSERT INTO customers (customer_id,first_name,last_name,current_player_status,group_captain) "
                  "VALUES (?,?,?,?,1)", (cid, fn, ln, "active_member"))
        c.execute("INSERT INTO customer_memberships (customer_id,started_at,expires_at,source) "
                  "VALUES (?,?,?,'manual')", (cid, "2019-02-01", "2027-02-01"))
    for eid, nm, d in ((5001, "s9.24 GG", "2026-09-22"), (5002, "s9.25 GG", "2026-09-29"),
                       (5003, "s9.27 entry", "2026-10-13"), (5004, "Lone Star Cup", "2026-10-09"),
                       (5005, "s9.26 both", "2026-10-06"), (5006, "s9.28 unwritten entry", "2026-10-14")):
        c.execute("INSERT INTO events (id,item_name,event_date,chapter,status) VALUES (?,?,?,?,?)",
                  (eid, nm, d, "San Antonio", "active"))
    # Murphy rode alone on the GG tee sheet 9/22 and 9/29, then with partners.
    hist(c, "Michael Murphy", "Dan Stich", 5001, "2026-09-22", 0, "gg_teesheet")
    hist(c, "Dan Stich", "Gus Vasquez", 5001, "2026-09-22", 1, "gg_teesheet")
    hist(c, "Michael Murphy", "Will Peterson", 5002, "2026-09-29", 0, "gg_teesheet")
    # Mary Wade: one GG solo (9/29) and one ENTRY-era solo (10/13, our own sheet).
    hist(c, "Mary Wade", "Will Peterson", 5002, "2026-09-29", 0, "gg_teesheet")
    hist(c, "Mary Wade", "Gus Vasquez", 5003, "2026-10-13", 0, "entry", "se:91")
    hist(c, "Gus Vasquez", "Michael Murphy", 5003, "2026-10-13", 1, "entry", "se:91")
    # Event 5005 has Golf Genius rows AND entry rows: counted once.
    hist(c, "Kerry Niester", "Jeff Rideout", 5005, "2026-10-06", 1, "gg_teesheet")
    hist(c, "Kerry Niester", "Jeff Rideout", 5005, "2026-10-06", 1, "entry", "se:77")
    hist(c, "Kerry Niester", "Jeff Rideout", 5001, "2026-09-22", 0, "gg_teamnet")
    c.commit()

# The score-entry reads, stubbed through the module's own API (the only
# reader of se_* is score_entry.py): the Cup's Saturday session (round 18,
# team scores only, alternate shot) with Kerry + Mesa on one side, and an
# entry-era event (5006) the closeout has not written yet.
_ROUNDS = [{"round_id": 18, "event_id": 5004, "round_date": "2026-10-10", "label": "Lone Star Cup · SAT",
            "pairings_holes": "lsc:sat-am", "status": "closed"},
           {"round_id": 20, "event_id": 5004, "round_date": "2026-10-11", "label": "Lone Star Cup · SUN",
            "pairings_holes": "lsc:sun", "status": "closed"},
           {"round_id": 99, "event_id": 5004, "round_date": "2026-10-08", "label": "PREVIEW x",
            "pairings_holes": "lscprev:sat-am", "status": "closed"},
           {"round_id": 31, "event_id": 5006, "round_date": "2026-10-14", "label": "s9.28",
            "pairings_holes": "9", "status": "closed"}]


def _p(cid, gid, scored=True):
    return {"customer_id": cid, "group_id": gid, "scores": {"1": 4} if scored else {}}


_READS = {
    5004: {"rounds": [
        {"round_id": 18, "date": "2026-10-10", "label": "Lone Star Cup · SAT",
         "players": [_p(CID["Kerry Niester"], 1, False), _p(CID["Michael Mesa"], 1, False),
                     _p(CID["Nic Skinner"], 1, False), _p(CID["Dan Stich"], 1, False)],
         "teams": [{"group_id": 1, "customer_ids": [CID["Kerry Niester"], CID["Michael Mesa"]], "scores": {"1": 4}},
                   {"group_id": 1, "customer_ids": [CID["Nic Skinner"], CID["Dan Stich"]], "scores": {"1": 5}}]},
        {"round_id": 20, "date": "2026-10-11", "label": "Lone Star Cup · SUN",
         "players": [_p(CID["Kerry Niester"], 2), _p(CID["Reggie Johnson"], 2),
                     _p(CID["Michael Mesa"], 2), _p(CID["Morris Allen"], 2)], "teams": []},
        {"round_id": 99, "date": "2026-10-08", "label": "PREVIEW x",
         "players": [_p(CID["Kerry Niester"], 3), _p(CID["Morris Allen"], 3)], "teams": []}]},
    5006: {"rounds": [
        {"round_id": 31, "date": "2026-10-14", "label": "s9.28",
         "players": [_p(CID["Mary Wade"], 5), _p(CID["Dan Stich"], 5), _p(CID["Will Peterson"], 5),
                     _p(CID["Nic Skinner"], 6, False)], "teams": []}]},
}
se.rounds_index = lambda db_path=None: list(_ROUNDS)
se.get_entered_scores = lambda event_id, round_id=None, db_path=None: _READS.get(int(event_id), {"rounds": []})
se.event_version = lambda event_id, db_path=None: 1

print("history: every source, the Lone Star Cup included")
counts = db.get_pairing_history_counts(year=2026, db_path=DB)
check("an LSC match pair counts (Kerry + Mesa: Saturday team card + Sunday group = 2)",
      db._pair_count(counts, "Kerry Niester", "Michael Mesa") == 2, counts)
check("an LSC opponent pair counts (Kerry + Skinner on the Saturday card)",
      db._pair_count(counts, "Kerry Niester", "Nic Skinner") == 1)
check("a Cup PREVIEW round never counts (Kerry + Allen only the Sunday card)",
      db._pair_count(counts, "Kerry Niester", "Morris Allen") == 1)
check("an entry-era event without written rows counts from its entered groups",
      db._pair_count(counts, "Mary Wade", "Dan Stich") == 1)
check("a player with no entered score played with nobody",
      db._pair_count(counts, "Mary Wade", "Nic Skinner") == 0)
check("written entry rows count (Wade + Vasquez, 10/13)",
      db._pair_count(counts, "Mary Wade", "Gus Vasquez") == 1)
check("an event with GG rows AND entry rows counts once (+ the GG Team Net row elsewhere)",
      db._pair_count(counts, "Kerry Niester", "Jeff Rideout") == 2, counts)
with db._connect(DB) as c:
    rode = db._rode_counts_from_conn(c)
    season = db._solo_season_from_conn(c, year=2026)
    streak = db._solo_streaks_from_conn(c)
check("Cup pairs are never a shared cart", rode.get((K("Kerry Niester"), K("Michael Mesa")), 0) == 0, rode)
check("entered-group carts count as rode (Wade + Stich, seats 1&2 on 10/14)",
      rode.get((K("Dan Stich"), K("Mary Wade")), 0) == 1, rode)

print("solo carts: SEASON totals, our own sheets counted")
check("Murphy: 2 solos this season (GG 9/22, 9/29)", season.get(K("Michael Murphy")) == 2, season)
check("Murphy's streak reads 0 after riding with a partner on 10/13", streak.get(K("Michael Murphy"), 0) == 0, streak)
check("Mary Wade: GG 9/29 + ENTRY 10/13 = 2 (entry rows are counted)",
      season.get(K("Mary Wade")) == 2, season)
check("the 10/14 entered threesome: Peterson rode alone in seat 3",
      season.get(K("Will Peterson")) == 2, season)   # GG 9/29 + entry 10/14
check("Cup sessions carry no cart record", season.get(K("Kerry Niester"), 0) == 0, season)

print("seater: the fewest-solo qualified player takes seat 3")
seat = db._arrange_group_seats(["Hi Solo", "Mid Solo", "Low Solo"], set(), set(),
                               {"Hi Solo": "<50", "Mid Solo": "<50", "Low Solo": "<50"},
                               solo_season={K("Hi Solo"): 3, K("Mid Solo"): 1})
check("Low Solo (0) rides alone, not Hi Solo (3)", seat[2] == "Low Solo", seat)
seat2 = db._arrange_group_seats(["Hi Solo", "New N", "Low Solo"], set(), set(),
                                {"Hi Solo": "<50", "New N": "<50", "Low Solo": "<50"},
                                no_solo={"New N"}, solo_season={K("Hi Solo"): 3})
check("a First Year player is not qualified: still never alone", seat2[2] != "New N", seat2)
check("a 1st Timer / First Year rule still outranks the season count",
      db._arrange_group_seats(["Hi Solo", "New N", "New M"], set(), set(), {},
                              no_solo={"New N", "New M"}, solo_season={K("Hi Solo"): 4})[2] == "Hi Solo")

# ── generator fixtures ────────────────────────────────────────────────
TODAY = "2026-12-15"
with db._connect(DB) as c:   # an earlier event, so nobody reads as a 1st Timer
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status) VALUES "
              "(5999,'earlier','2026-03-01','San Antonio','active')")
    c.commit()


def make_event(eid, players, pairs=(), solos=(), new=()):
    """players: names; pairs: (a, b, count); solos: (name, n); new: 1Y names."""
    with db._connect(DB) as c:
        c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format,start_time,start_type,course) "
                  "VALUES (?,?,?,?,?,?,?,?,?)", (eid, f"Gen {eid}", TODAY, "San Antonio", "active",
                                                  "9 Holes", "4:30 PM", "Tee Times", "Course"))
        for i, n in enumerate(players):
            cid = eid * 100 + i
            fn, ln = n.split(" ", 1)
            c.execute("INSERT INTO customers (customer_id,first_name,last_name,current_player_status,group_captain) "
                      "VALUES (?,?,?,?,1)", (cid, fn, ln, "active_member"))
            c.execute("INSERT INTO customer_memberships (customer_id,started_at,expires_at,source) "
                      "VALUES (?,?,?,'manual')", (cid, "2026-02-01" if n in new else "2019-02-01", "2027-02-01"))
            c.execute("INSERT INTO items (customer,customer_id,item_name,holes,tee_choice,transaction_status,"
                      "order_date,order_id,email_uid,merchant,user_status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (n, cid, "earlier", "9", "50-64", "active", "2026-03-01", f"E{cid}", f"manual-e{cid}",
                       "GoDaddy", "MEMBER"))
            c.execute("INSERT INTO items (customer,customer_id,item_name,event_id,holes,tee_choice,"
                      "transaction_status,order_date,order_id,email_uid,merchant,user_status) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                      (n, cid, f"Gen {eid}", eid, "9", "50-64", "active", "2026-12-01",
                       f"R{cid}", f"manual-r{cid}", "GoDaddy", "MEMBER"))
            if n not in new:
                for r in range(5):
                    c.execute("INSERT INTO scoring_rounds (customer_id,player_name,round_date,holes_played,gross,source) "
                              "VALUES (?,?,?,9,40,'gg')", (cid, n, f"2026-0{3 + r}-10"))
        k = 0
        for a, b, cnt in pairs:
            for _ in range(cnt):
                k += 1
                hist(c, a, b, eid * 1000 + k, "2026-06-01", 0, "gg_teamnet")
        for n, cnt in solos:
            for _ in range(cnt):
                k += 1
                hist(c, n, "Somebody Else", eid * 1000 + k, "2026-07-01", 0, "gg_teesheet")
        c.commit()


def gen(eid, seed=None):
    orig = db.PAIRINGS_SEED
    if seed is not None:
        db.PAIRINGS_SEED = seed
    try:
        res = db.generate_event_pairings(eid, mode="random", protect_partner_requests=True, db_path=DB)
    finally:
        db.PAIRINGS_SEED = orig
    return [[p["name"] for p in sorted(g["players"], key=lambda p: p["cart_pos"])] for g in res["9"]], res


print("composition: the threesome's solo seat goes to the fewest-solo qualified player")
S = ["Low Zero", "Ann Two", "Bob Two", "Cy Three", "Di Two", "Ed Three", "Flo Two"]
make_event(6001, S, solos=[("Ann Two", 2), ("Bob Two", 2), ("Cy Three", 3), ("Di Two", 2),
                           ("Ed Three", 3), ("Flo Two", 2)])
bad = 0
for t in range(12):
    G, _ = gen(6001, f"solo-{t}")
    three = [g for g in G if len(g) == 3]
    if not three or three[0][2] != "Low Zero":
        bad += 1
check("over 12 seeds the only 0-solo player is always the one riding alone", bad == 0, G)

print("repeats: a 3rd meeting is avoided when a zero-count option exists")
R = ["Kerry Niester2", "Jeff Rideout2", "Pa One", "Pb One", "Pc One", "Pd One", "Pe One", "Pf One"]
make_event(6002, R, pairs=[("Kerry Niester2", "Jeff Rideout2", 2)])
bad = 0
for t in range(12):
    G, res = gen(6002, f"rep-{t}")
    if any("Kerry Niester2" in g and "Jeff Rideout2" in g for g in G):
        bad += 1
check("Kerry + Rideout never grouped a 3rd time over 12 seeds", bad == 0)

print("newer players in foursomes (Kerry 10/19)")
N = ["New One", "New Two", "New Three", "Old A", "Old B", "Old C", "Old D", "Old E", "Old F", "Old G", "Old H"]
make_event(6003, N, new={"New One", "New Two", "New Three"})
bad = 0
for t in range(8):
    G, res = gen(6003, f"new-{t}")
    for g in G:
        if len(g) < 4 and any(n.startswith("New") for n in g):
            bad += 1
check("11 players (4,4,3): no new player in the threesome over 8 seeds", bad == 0, G)

print("generation log")
G, res = gen(6002)
lg = res.get("gen_log") or {}
h9 = (lg.get("holes") or {}).get("9") or {}
check("log returned with inputs, groups, final cost and alternatives",
      all(k in h9 for k in ("inputs", "groups", "final_cost", "alternatives", "passes", "repeat_reasons")), list(h9))
check("inputs carry the history counts used for the roster pairs",
      any(r["count"] == 2 for r in h9.get("inputs", {}).get("history_counts", [])), h9.get("inputs"))
check("inputs carry the season solo totals", "solo_season" in h9.get("inputs", {}))
saved = db.get_app_setting("pairings_gen_log:6002", DB)
check("a Generate keeps its log in app setting pairings_gen_log:<id>", bool(saved) and json.loads(saved)["event_id"] == 6002)

print("preview bridge: nothing saved")
import mcp_server as _ms                                          # noqa: E402
with db._connect(DB) as c:
    c.execute("DELETE FROM app_settings WHERE key = 'pairings_gen_log:6003'")
    c.commit()
pv = json.loads(_ms._scoring_dispatch_inner("", "scoring-pairings-generate-preview:6003"))
check("preview returns proposed groups, cost, audit and the log",
      pv.get("groups", {}).get("9") and pv.get("cost") and "audit" in pv and pv.get("gen_log"), list(pv))
check("preview audit ran on the proposed sheet", "summary" in (pv.get("audit") or {}), pv.get("audit"))
with db._connect(DB) as c:
    n_pair = c.execute("SELECT COUNT(*) FROM event_pairings WHERE event_id = 6003").fetchone()[0]
    try:
        n_bl = c.execute("SELECT COUNT(*) FROM blind_draws WHERE event_id = 6003").fetchone()[0]
    except Exception:
        n_bl = 0
    n_log = c.execute("SELECT COUNT(*) FROM app_settings WHERE key = 'pairings_gen_log:6003'").fetchone()[0]
check("preview saved no sheet", n_pair == 0, n_pair)
check("preview drew no blinds", n_bl == 0, n_bl)
check("preview kept no log setting", n_log == 0, n_log)
gl = json.loads(_ms._scoring_dispatch_inner("", "scoring-pairings-gen-log:6002"))
check("gen-log bridge reads the latest Generate's log", (gl.get("log") or {}).get("event_id") == 6002, gl)

# scoring-pairings-set-sheet (Kerry 10/19 "Yes, use that sheet"): replace the
# saved sheet with hand-picked groups; everyone seated exactly once.
_g9 = pv["groups"]["9"]
db.save_event_pairings(6003, {"9": [{"group_num": i + 1, "slot_label": g["slot"],
                                      "players": [{"name": n, "cart_pos": j + 1} for j, n in enumerate(g["players"])]}
                                     for i, g in enumerate(_g9)]}, db_path=DB)
_names = [n for g in _g9 for n in g["players"]]
_new = [_names[i:i + 4] for i in range(0, len(_names), 4)][::-1]
_arg = "6003|" + "/".join(";".join(g) for g in _new)
ss = json.loads(_ms._scoring_dispatch_inner("", "scoring-pairings-set-sheet:" + _arg))
check("set-sheet dry run returns the groups and an audit, saves nothing",
      ss.get("applied") is False and len(ss.get("groups") or []) == len(_new) and "audit" in ss, ss)
bad = json.loads(_ms._scoring_dispatch_inner("", "scoring-pairings-set-sheet:" + _arg.rsplit(";", 1)[0]))
check("set-sheet refuses a sheet that leaves a player out", "left out" in (bad.get("refused") or {}), bad)
ss = json.loads(_ms._scoring_dispatch_inner("", "scoring-pairings-set-sheet:" + _arg + "|apply"))
_saved = db.get_event_pairings(6003, db_path=DB).get("9") or []
check("set-sheet apply saves the groups in the order given",
      ss.get("applied") and [[p["name"] for p in sorted(g["players"], key=lambda p: p["cart_pos"])] for g in _saved] == _new,
      ([[p["name"] for p in g["players"]] for g in _saved], _new))

# scoring-pace-set (Kerry 10/19: "I do want you to add a tool for it").
with db._connect(DB) as c:
    _pcid = c.execute("SELECT customer_id FROM customers ORDER BY customer_id LIMIT 1").fetchone()[0]
ps = json.loads(_ms._scoring_dispatch_inner("", f"scoring-pace-set:{_pcid}|1"))
check("pace-set dry run writes nothing", ps.get("applied") is False and ps["players"][0]["customer_id"] == _pcid, ps)
ps = json.loads(_ms._scoring_dispatch_inner("", f"scoring-pace-set:{_pcid}|1|apply"))
with db._connect(DB) as c:
    _pr = c.execute("SELECT pace_rating, pace_rating_source FROM customers WHERE customer_id = ?", (_pcid,)).fetchone()
check("pace-set apply writes 1 as a manager rating", ps.get("applied") and tuple(_pr) == (1, "manager"), tuple(_pr))
check("pace-set refuses a rating of 4", "error" in json.loads(_ms._scoring_dispatch_inner("", f"scoring-pace-set:{_pcid}|4")))

print()
print("ALL PASS" if not F else f"FAILED: {F}")
sys.exit(1 if F else 0)
