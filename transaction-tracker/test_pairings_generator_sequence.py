"""REPEATS IN SEQUENCE + the rule fixes + R-C, on Olympia Hills (event 3308).

Kerry 2026-10-06: "I don't play with X twice (unless other pairings rules
dictate) until I've played with all others once." / "Repeats should be in
sequence whenever possible." The 10/5 5 PM auto-generate put Adam Baker and
Jeff Rideout together a 4th time while both had partners they had never
played with. Root cause (mailbox #1256): the repeat cost was 1000 + count,
the rule fixes (7/12/14) ran after the search and never re-optimised, and
the search was unseeded.

The fixture is Olympia Hills (event 3308) as production had it on 10/6:
the 21 players, tees, captain / Ambassador / solo_back_ok flags, the one
request (Saldana -> Bourquin), every 2026 pair count among them, and
Michael Murphy's solo carts on 9/22 and 9/29.

Run: python3 test_pairings_generator_sequence.py [runs]   (default 200)
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
from email_parser.pairings_audit import event_pairing_audit       # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 200


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


P = [  # name, tee, captain, ambassador, solo_back_ok, request
 ("Adam Baker","<50",1,0,1,None),("Jeff Rideout","50-64",0,0,0,None),
 ("Craig Bourquin","50-64",0,0,0,None),("Jesse Saldana","<50",0,0,0,"Craig Bourquin"),
 ("Don Sharitz","65+",1,0,0,None),("Wade Lewis","<50",0,0,0,None),
 ("Richard Palacios","50-64",0,0,0,"Larry Anthis"),("Daniel Miller","<50",0,0,0,None),
 ("Brian Thompson","<50",0,0,0,None),("Nic Skinner","<50",0,0,0,None),
 ("Scott Marroquin","50-64",0,1,0,None),("Daniel South","50-64",1,1,0,None),
 ("Michele McCormick","Forward",0,0,0,None),("Kerry Niester","<50",1,1,1,None),
 ("Justin Angelone","<50",0,0,0,None),("Fred Wicker","50-64",1,0,0,None),
 ("Pat Youngs","50-64",0,0,0,None),("Michael Murphy","65+",0,0,0,None),
 ("Luke Mazanec","<50",0,1,1,None),("Reggie Johnson","65+",0,0,0,None),
 ("Dan Stich","50-64",0,0,0,None)]
PAIRS = {
"Craig Bourquin + Jesse Saldana":7,"Craig Bourquin + Richard Palacios":1,"Craig Bourquin + Luke Mazanec":1,
"Craig Bourquin + Adam Baker":1,"Craig Bourquin + Kerry Niester":1,"Jesse Saldana + Richard Palacios":1,
"Jesse Saldana + Luke Mazanec":1,"Jesse Saldana + Adam Baker":2,"Brian Thompson + Don Sharitz":1,
"Brian Thompson + Richard Palacios":1,"Brian Thompson + Luke Mazanec":2,"Brian Thompson + Adam Baker":1,
"Brian Thompson + Michele McCormick":1,"Brian Thompson + Pat Youngs":1,"Brian Thompson + Michael Murphy":1,
"Brian Thompson + Kerry Niester":1,"Brian Thompson + Daniel South":1,"Brian Thompson + Jeff Rideout":1,
"Daniel Miller + Luke Mazanec":2,"Daniel Miller + Michael Murphy":1,"Daniel Miller + Kerry Niester":1,
"Don Sharitz + Richard Palacios":1,"Don Sharitz + Luke Mazanec":2,"Don Sharitz + Dan Stich":1,
"Don Sharitz + Adam Baker":1,"Don Sharitz + Michele McCormick":1,"Don Sharitz + Pat Youngs":1,
"Don Sharitz + Michael Murphy":3,"Don Sharitz + Kerry Niester":2,"Don Sharitz + Daniel South":1,
"Don Sharitz + Jeff Rideout":4,"Don Sharitz + Scott Marroquin":1,"Wade Lewis + Luke Mazanec":1,
"Wade Lewis + Pat Youngs":1,"Wade Lewis + Kerry Niester":1,"Richard Palacios + Luke Mazanec":2,
"Richard Palacios + Dan Stich":2,"Richard Palacios + Adam Baker":4,"Richard Palacios + Pat Youngs":1,
"Richard Palacios + Michael Murphy":3,"Richard Palacios + Kerry Niester":2,"Richard Palacios + Daniel South":3,
"Richard Palacios + Fred Wicker":1,"Richard Palacios + Jeff Rideout":3,"Richard Palacios + Scott Marroquin":2,
"Nic Skinner + Luke Mazanec":1,"Nic Skinner + Adam Baker":1,"Nic Skinner + Daniel South":1,
"Nic Skinner + Jeff Rideout":1,"Luke Mazanec + Dan Stich":1,"Luke Mazanec + Adam Baker":3,
"Luke Mazanec + Michele McCormick":1,"Luke Mazanec + Pat Youngs":1,"Luke Mazanec + Michael Murphy":2,
"Luke Mazanec + Kerry Niester":4,"Luke Mazanec + Justin Angelone":1,"Luke Mazanec + Daniel South":2,
"Luke Mazanec + Fred Wicker":1,"Luke Mazanec + Jeff Rideout":2,"Luke Mazanec + Scott Marroquin":1,
"Dan Stich + Adam Baker":1,"Dan Stich + Michael Murphy":2,"Dan Stich + Kerry Niester":1,
"Dan Stich + Daniel South":1,"Dan Stich + Jeff Rideout":2,"Dan Stich + Scott Marroquin":1,
"Adam Baker + Michael Murphy":1,"Adam Baker + Kerry Niester":2,"Adam Baker + Daniel South":2,
"Adam Baker + Fred Wicker":1,"Adam Baker + Jeff Rideout":3,"Adam Baker + Scott Marroquin":1,
"Michele McCormick + Jeff Rideout":1,"Michele McCormick + Scott Marroquin":1,"Pat Youngs + Justin Angelone":1,
"Pat Youngs + Daniel South":1,"Pat Youngs + Jeff Rideout":2,"Pat Youngs + Scott Marroquin":1,
"Michael Murphy + Kerry Niester":1,"Michael Murphy + Daniel South":1,"Michael Murphy + Jeff Rideout":2,
"Michael Murphy + Scott Marroquin":1,"Kerry Niester + Daniel South":1,"Kerry Niester + Fred Wicker":1,
"Kerry Niester + Jeff Rideout":2,"Kerry Niester + Scott Marroquin":1,"Justin Angelone + Jeff Rideout":1,
"Daniel South + Fred Wicker":1,"Daniel South + Jeff Rideout":2,"Daniel South + Scott Marroquin":1,
"Jeff Rideout + Scott Marroquin":1}
EV = 3308
K = db._pair_key_name
with db._connect(DB) as c:
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format,start_time,start_type,course) "
              "VALUES (?,?,?,?,?,?,?,?,?)", (EV, "s9.26 Olympia Hills", "2026-12-15", "San Antonio", "active",
                                              "9 Holes", "4:30 PM", "Shotgun", "Olympia Hills"))
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status) VALUES "
              "(3000,'s9.1 Earlier','2026-03-01','San Antonio','active')")
    for i, (n, tee, cap, amb, sok, req) in enumerate(P):
        cid = 900 + i
        fn, ln = n.split(" ", 1)
        c.execute("INSERT INTO customers (customer_id,first_name,last_name,current_player_status,"
                  "group_captain,ambassador,solo_back_ok) VALUES (?,?,?,'active_member',?,?,?)",
                  (cid, fn, ln, cap, amb, sok))
        c.execute("INSERT INTO items (customer,customer_id,item_name,event_id,holes,tee_choice,transaction_status,"
                  "order_date,order_id,email_uid,merchant,user_status,partner_request) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (n, cid, "s9.26 Olympia Hills", EV, "9", tee, "active", "2026-10-01", f"R{cid}",
                   f"manual-{cid}", "GoDaddy", "MEMBER", req))
        # history so nobody reads as a 1st Timer: an earlier order and
        # rounds on file (Reggie Johnson has 2, as on 10/6)
        c.execute("INSERT INTO items (customer,customer_id,item_name,holes,tee_choice,transaction_status,"
                  "order_date,order_id,email_uid,merchant,user_status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (n, cid, "s9.1 Earlier", "9", tee, "active", "2026-03-01", f"E{cid}", f"manual-e{cid}",
                   "GoDaddy", "MEMBER"))
        for r in range(2 if n == "Reggie Johnson" else 6):
            c.execute("INSERT INTO scoring_rounds (customer_id,player_name,round_date,holes_played,gross,source) "
                      "VALUES (?,?,?,9,40,'gg')", (cid, n, f"2026-0{3 + r}-10"))
    db._ensure_pairing_tables(c)
    k = 0
    for pair, cnt in PAIRS.items():          # who played with whom (no cart data)
        a, b = pair.split(" + ")
        for _ in range(cnt):
            k += 1
            c.execute("INSERT INTO pairing_history (player_a,player_b,event_id,event_date,rode,source) "
                      "VALUES (?,?,?,?,0,'gg_teamnet')", (a, b, 20000 + k, "2026-06-01"))
    # Murphy rode alone on 9/22 and 9/29 (tee-sheet rows, no cart partner).
    for eid, d in ((30001, "2026-09-22"), (30002, "2026-09-29")):
        c.execute("INSERT INTO pairing_history (player_a,player_b,event_id,event_date,rode,source) "
                  "VALUES ('Michael Murphy','Somebody Else',?,?,0,'gg_teesheet')", (eid, d))
    c.commit()

counts = db.get_pairing_history_counts(year=2026, db_path=DB, exclude_event_id=EV)
check("fixture: Baker + Rideout have played 3 times",
      db._pair_count(counts, "Adam Baker", "Jeff Rideout") == 3)
with db._connect(DB) as c:
    check("fixture: Murphy has 2 solo carts in a row", db._solo_streaks_from_conn(c, EV).get("michael murphy") == 2)

print("cost: a deeper repeat outweighs any number of shallower ones")
check("one pair at 3 costs more than 100 pairs at 2", db._repeat_cost(3) > 100 * db._repeat_cost(2))
check("one pair at 2 costs more than 100 pairs at 1", db._repeat_cost(2) > 100 * db._repeat_cost(1))


def gen():
    res = db.generate_event_pairings(EV, mode="random", protect_partner_requests=True, db_path=DB)
    return [[p["name"] for p in g["players"]] for g in res["9"]]


def deepest(groups):
    req = frozenset(("craig bourquin", "jesse saldana"))
    return max((db._pair_count(counts, g[i], g[j]) for g in groups for i in range(len(g))
                for j in range(i + 1, len(g)) if frozenset((K(g[i]), K(g[j]))) != req), default=0)


def together(groups, a, b):
    return any(a in g and b in g for g in groups)


def cart_of(groups, n):
    for g in groups:
        if n in g:
            i = g.index(n)
            return (id(g), 0 if i < 2 else 1)


print(f"same seed, same sheet")
check("Generate twice gives the same sheet", gen() == gen())

print(f"{RUNS} independent seeds")
orig_seed = db.PAIRINGS_SEED
bad = {"baker_rideout": 0, "deep": 0, "req_split": 0, "murphy_solo": 0, "maz_flagged": 0, "lone_back": 0}
depths = {}
try:
    for t in range(RUNS):
        db.PAIRINGS_SEED = f"test-{t}"
        G = gen()
        d = deepest(G)
        depths[d] = depths.get(d, 0) + 1
        if together(G, "Adam Baker", "Jeff Rideout"):
            bad["baker_rideout"] += 1
        if d > 1:
            bad["deep"] += 1
        if cart_of(G, "Craig Bourquin") != cart_of(G, "Jesse Saldana"):
            bad["req_split"] += 1
        for g in G:
            if len(g) == 3 and g[2] == "Michael Murphy":
                bad["murphy_solo"] += 1
            backs = [n for n in g if dict((p[0], p[1]) for p in P)[n] == "<50"]
            if len(backs) == 1 and backs[0] not in ("Adam Baker", "Kerry Niester", "Luke Mazanec"):
                bad["lone_back"] += 1
finally:
    db.PAIRINGS_SEED = orig_seed
print(f"     deepest non-requested repeat per sheet: {dict(sorted(depths.items()))}")
check("Baker + Rideout never grouped", bad["baker_rideout"] == 0, bad)
check("no non-requested pair deeper than 1 (a depth-0 option always exists here)", bad["deep"] == 0, bad)
check("Bourquin + Saldana always in the same group AND cart", bad["req_split"] == 0, bad)
check("Murphy never seated alone a 3rd time", bad["murphy_solo"] == 0, bad)
check("no lone <50 except a solo_back_ok player", bad["lone_back"] == 0, bad)

print("audit on the generator's sheet")
G = gen()
db.save_event_pairings(EV, {"9": [{"group_num": i + 1, "slot_label": f"G{i+1}", "players": [
    {"name": n, "cart_pos": j + 1, "customer_id": 900 + [p[0] for p in P].index(n),
     "tee_choice": dict((p[0], p[1]) for p in P)[n]} for j, n in enumerate(g)]} for i, g in enumerate(G)]})
a = event_pairing_audit(EV, db_path=DB)
hard = [f for f in a["flags"] if f["kind"] == "hard"]
check("audit: zero hard flags on the generator's sheet", not hard, hard)
check("audit: no repeat skips a level", a["summary"]["skips_a_level"] == 0, a["summary"])
rd = [x for g in a["groups"] for x in g["rules"] if x["rule"].startswith("R-D")]
check("audit: a solo_back_ok lone <50 is allowed, not flagged", all(x["ok"] for x in rd), rd)
check("audit: deepest repeat on the sheet is 1", a["summary"]["deepest_repeat"] <= 1, a["summary"])

print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED'}")
sys.exit(1 if F else 0)
