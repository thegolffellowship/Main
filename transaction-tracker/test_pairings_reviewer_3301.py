"""PAIRINGS GENERATOR REVIEWER — s9.28 TPC Canyons (event 3301, Tue 10/20) as a fixture.

Kerry 2026-10-19: "This one is a really good one to use as a test case because
of there being 3 threesomes required." 21 players, six groups (3 threesomes),
one 1st Timer guest (Copeland), six First Year members, seven leaders, and
Jeff Rideout's rule-7 squeeze (2+ meetings with every leader in the field).

The fixture is the generation log of 10/19 7:40 PM (scoring-pairings-gen-log:3301):
every 2026 pair count among the 21, the solo-season totals, and the flags
(captains, Ambassadors, 1Y, 1st Timer, solo_back_ok). Tees are the saved sheet's.

The checks are the scorecard of rule misses per run (the reviewer lane's brief):
the generator's own sheet must have no First Year / 1st Timer rider alone, no
1st Timer without an Ambassador cart-mate, and the audit on it zero hard flags.

Run: python3 test_pairings_reviewer_3301.py [runs]   (default 20)
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
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
K = db._pair_key_name


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


# name, tee, captain, ambassador, solo_back_ok, first-year member, solo carts this season
P = [
 ("Kerry Niester", "<50", 1, 1, 1, 0, 1), ("Nic Skinner", "<50", 0, 0, 0, 0, 0),
 ("Dan Stich", "50-64", 0, 0, 0, 0, 4), ("Gus Vasquez", "50-64", 1, 1, 0, 0, 2),
 ("Steve Kulawik", "50-64", 0, 0, 0, 0, 1), ("Richard Palacios", "50-64", 0, 0, 0, 0, 0),
 ("Luke Mazanec", "<50", 0, 1, 1, 0, 1), ("Michele McCormick", "Forward", 0, 0, 0, 1, 0),
 ("Will Peterson", "50-64", 0, 0, 0, 0, 0), ("Mary Wade", "Forward", 1, 1, 0, 0, 3),
 ("Morris Allen", "50-64", 0, 0, 0, 1, 0), ("Don Sharitz", "65+", 1, 0, 0, 0, 1),
 ("Reggie Johnson", "50-64", 0, 0, 0, 1, 0), ("Jeff Young", "<50", 1, 1, 1, 0, 0),
 ("Michael Copeland", "50-64", 0, 0, 0, 0, 0), ("Jeff Rideout", "50-64", 0, 0, 0, 0, 4),
 ("Wade Lewis", "<50", 0, 0, 0, 1, 0), ("Adam Baker", "<50", 1, 0, 1, 0, 2),
 ("Michael Mesa", "<50", 0, 0, 0, 1, 0), ("Michael Murphy", "65+", 0, 0, 0, 0, 2),
 ("Steven Hunt", "50-64", 0, 0, 0, 1, 1)]
FIRST_TIMER = "Michael Copeland"          # a guest, first event ever
PAIRS = """Adam Baker|Luke Mazanec|5;Gus Vasquez|Jeff Rideout|5;Jeff Rideout|Mary Wade|5;
Adam Baker|Richard Palacios|4;Don Sharitz|Jeff Rideout|4;Jeff Young|Mary Wade|4;Kerry Niester|Luke Mazanec|4;
Kerry Niester|Michael Mesa|4;Adam Baker|Jeff Rideout|3;Adam Baker|Mary Wade|3;Dan Stich|Gus Vasquez|3;
Don Sharitz|Gus Vasquez|3;Don Sharitz|Michael Murphy|3;Gus Vasquez|Kerry Niester|3;Gus Vasquez|Mary Wade|3;
Jeff Rideout|Luke Mazanec|3;Jeff Rideout|Richard Palacios|3;Jeff Rideout|Will Peterson|3;Kerry Niester|Mary Wade|3;
Mary Wade|Richard Palacios|3;Michael Murphy|Richard Palacios|3;Adam Baker|Dan Stich|2;Adam Baker|Kerry Niester|2;
Dan Stich|Jeff Rideout|2;Dan Stich|Luke Mazanec|2;Dan Stich|Mary Wade|2;Dan Stich|Michael Murphy|2;
Dan Stich|Richard Palacios|2;Don Sharitz|Kerry Niester|2;Don Sharitz|Luke Mazanec|2;Don Sharitz|Richard Palacios|2;
Don Sharitz|Will Peterson|2;Gus Vasquez|Luke Mazanec|2;Jeff Rideout|Jeff Young|2;Jeff Rideout|Kerry Niester|2;
Jeff Rideout|Michael Murphy|2;Jeff Young|Kerry Niester|2;Kerry Niester|Richard Palacios|2;Luke Mazanec|Mary Wade|2;
Luke Mazanec|Michael Mesa|2;Luke Mazanec|Michael Murphy|2;Luke Mazanec|Richard Palacios|2;Mary Wade|Michael Murphy|2;
Steven Hunt|Will Peterson|2;Adam Baker|Don Sharitz|1;Adam Baker|Gus Vasquez|1;Adam Baker|Jeff Young|1;
Adam Baker|Michael Murphy|1;Adam Baker|Michele McCormick|1;Adam Baker|Nic Skinner|1;Adam Baker|Steve Kulawik|1;
Adam Baker|Steven Hunt|1;Adam Baker|Wade Lewis|1;Adam Baker|Will Peterson|1;Dan Stich|Don Sharitz|1;
Dan Stich|Kerry Niester|1;Dan Stich|Michele McCormick|1;Dan Stich|Reggie Johnson|1;Dan Stich|Steven Hunt|1;
Dan Stich|Wade Lewis|1;Don Sharitz|Jeff Young|1;Don Sharitz|Mary Wade|1;Don Sharitz|Michele McCormick|1;
Don Sharitz|Nic Skinner|1;Don Sharitz|Steven Hunt|1;Don Sharitz|Wade Lewis|1;Gus Vasquez|Michael Murphy|1;
Gus Vasquez|Morris Allen|1;Gus Vasquez|Richard Palacios|1;Gus Vasquez|Steve Kulawik|1;Gus Vasquez|Steven Hunt|1;
Gus Vasquez|Wade Lewis|1;Jeff Rideout|Michele McCormick|1;Jeff Rideout|Nic Skinner|1;Jeff Rideout|Steve Kulawik|1;
Jeff Rideout|Steven Hunt|1;Jeff Young|Luke Mazanec|1;Jeff Young|Michael Mesa|1;Jeff Young|Michael Murphy|1;
Jeff Young|Steven Hunt|1;Jeff Young|Wade Lewis|1;Kerry Niester|Michael Murphy|1;Kerry Niester|Michele McCormick|1;
Kerry Niester|Steve Kulawik|1;Kerry Niester|Steven Hunt|1;Kerry Niester|Wade Lewis|1;Kerry Niester|Will Peterson|1;
Luke Mazanec|Michele McCormick|1;Luke Mazanec|Nic Skinner|1;Luke Mazanec|Reggie Johnson|1;Luke Mazanec|Steve Kulawik|1;
Luke Mazanec|Steven Hunt|1;Luke Mazanec|Wade Lewis|1;Mary Wade|Michele McCormick|1;Mary Wade|Steve Kulawik|1;
Mary Wade|Steven Hunt|1;Mary Wade|Wade Lewis|1;Mary Wade|Will Peterson|1;Michael Mesa|Michael Murphy|1;
Michael Murphy|Will Peterson|1;Michele McCormick|Steve Kulawik|1;Michele McCormick|Wade Lewis|1;
Morris Allen|Richard Palacios|1;Nic Skinner|Richard Palacios|1;Nic Skinner|Wade Lewis|1;
Reggie Johnson|Richard Palacios|1;Richard Palacios|Steve Kulawik|1;Richard Palacios|Steven Hunt|1;
Richard Palacios|Wade Lewis|1;Richard Palacios|Will Peterson|1"""
EV = 3301
TEE = {p[0]: p[1] for p in P}
CID = {p[0]: 900 + i for i, p in enumerate(P)}

with db._connect(DB) as c:
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format,start_time,start_type,course) "
              "VALUES (?,?,?,?,?,?,?,?,?)", (EV, "s9.28 TPC Canyons", "2026-12-15", "San Antonio", "active",
                                              "9 Holes", "3:40 PM", "Tee Times", "TPC San Antonio - Canyons"))
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status) VALUES "
              "(3000,'s9.1 Earlier','2026-03-01','San Antonio','active')")
    for n, tee, cap, amb, sok, new, _solo in P:
        cid = CID[n]
        fn, ln = n.split(" ", 1)
        ft = n == FIRST_TIMER
        c.execute("INSERT INTO customers (customer_id,first_name,last_name,current_player_status,"
                  "group_captain,ambassador,solo_back_ok) VALUES (?,?,?,?,?,?,?)",
                  (cid, fn, ln, "first_timer" if ft else "active_member", cap, amb, sok))
        c.execute("INSERT INTO items (customer,customer_id,item_name,event_id,holes,tee_choice,transaction_status,"
                  "order_date,order_id,email_uid,merchant,user_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (n, cid, "s9.28 TPC Canyons", EV, "9", tee, "active", "2026-10-15", f"R{cid}",
                   f"manual-{cid}", "GoDaddy", "1ST TIMER" if ft else "MEMBER"))
        if ft:
            continue
        # Everybody else has played before: an earlier order and rounds on
        # file (3+ dates, so no First Year player is in his first three events).
        c.execute("INSERT INTO items (customer,customer_id,item_name,holes,tee_choice,transaction_status,"
                  "order_date,order_id,email_uid,merchant,user_status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (n, cid, "s9.1 Earlier", "9", tee, "active", "2026-03-01", f"E{cid}", f"manual-e{cid}",
                   "GoDaddy", "MEMBER"))
        for r in range(5):
            c.execute("INSERT INTO scoring_rounds (customer_id,player_name,round_date,holes_played,gross,source) "
                      "VALUES (?,?,?,9,40,'gg')", (cid, n, f"2026-0{4 + r}-10"))
        if new:   # joined as a NEW member this year, no handicap round before it (1Y)
            c.execute("INSERT INTO customer_memberships (customer_id,started_at,expires_at,source) VALUES (?,?,?,'manual')",
                      (cid, "2026-03-01", "2027-03-01"))
    db._ensure_pairing_tables(c)
    k = 0
    for item in PAIRS.replace("\n", "").split(";"):
        a, b, cnt = item.split("|")
        for _ in range(int(cnt)):
            k += 1
            c.execute("INSERT INTO pairing_history (player_a,player_b,event_id,event_date,rode,source) "
                      "VALUES (?,?,?,?,0,'gg_teamnet')", (a, b, 20000 + k, "2026-06-01"))
    # Solo carts this season: tee-sheet rounds with no cart partner, each
    # followed by a later shared cart so no streak is running (log: {}).
    for n, *_rest, solo in P:
        for s in range(solo):
            k += 1
            c.execute("INSERT INTO pairing_history (player_a,player_b,event_id,event_date,rode,source) "
                      "VALUES (?,'Solo Witness',?,?,0,'gg_teesheet')", (n, 30000 + k, f"2026-07-{10 + s:02d}"))
        if solo:
            k += 1
            c.execute("INSERT INTO pairing_history (player_a,player_b,event_id,event_date,rode,source) "
                      "VALUES (?,'Cart Witness',?,?,1,'gg_teesheet')", (n, 30000 + k, "2026-09-29"))
    c.commit()

print("fixture matches the 10/19 generation log")
counts = db.get_pairing_history_counts(year=2026, db_path=DB, exclude_event_id=EV)
check("Kerry + Rideout have played 2 times", db._pair_count(counts, "Kerry Niester", "Jeff Rideout") == 2)
with db._connect(DB) as c:
    ss = db._solo_season_from_conn(c, year=2026, exclude_event_id=EV)
check("solo season: Rideout 4, Wade 3, McCormick 0",
      (ss.get("jeff rideout"), ss.get("mary wade"), ss.get("michele mccormick", 0)) == (4, 3, 0), ss)

print("defect 1: one seating must satisfy rules 14/16/18 together")
amb = {K("Gus Vasquez")}
need = {K(FIRST_TIMER)}
no_solo = {K(FIRST_TIMER), K("Michele McCormick")}
check("Vasquez (Amb) + Copeland (1T) + McCormick (1Y) is a rule miss",
      sum(db._group_seat_misses(["Gus Vasquez", FIRST_TIMER, "Michele McCormick"],
                                set(), amb, need, no_solo, None)) >= 1)
check("Vasquez (Amb) + Copeland (1T) + Peterson is not a miss",
      sum(db._group_seat_misses(["Gus Vasquez", FIRST_TIMER, "Will Peterson"],
                                set(), amb, need, no_solo | {K("Will Peterson")} - {K("Will Peterson")},
                                None)) == 0)


def gen():
    res = db.generate_event_pairings(EV, mode="random", protect_partner_requests=True, db_path=DB)
    return [[p["name"] for p in g["players"]] for g in res["9"]], res


def misses(G):
    """Scorecard of hard rule misses on a seated sheet (seats 1&2 / 3&4 ride)."""
    out = []
    no_solo_n = {p[0] for p in P if p[5]} | {FIRST_TIMER}
    ambs = {p[0] for p in P if p[3]}
    leads = ambs | {p[0] for p in P if p[2]}
    for g in G:
        if len(g) % 2 == 1 and g[-1] in no_solo_n:
            out.append(f"{g[-1]} rides alone (rule 16)")
        if FIRST_TIMER in g:
            i = g.index(FIRST_TIMER)
            mate = [g[j] for j in range(len(g)) if j != i and j // 2 == i // 2]
            if not any(m in ambs for m in mate):
                out.append(f"{FIRST_TIMER} without an Ambassador cart-mate (rule 14/18)")
        if not any(n in leads for n in g):
            out.append(f"no leader in {g} (rule 7)")
        backs = [n for n in g if TEE[n] == "<50"]
        if len(backs) == 1 and not [p for p in P if p[0] == backs[0]][0][4]:
            out.append(f"lone <50 {backs[0]} (rule 12)")
    return out


print("the generator's own sheet (default seed)")
G, res = gen()
for g in G:
    print("     ", " / ".join(g))
m = misses(G)
check("no hard rule miss on the generator's sheet", not m, m)
sizes = [len(g) for g in G]
check("tee times: the threesomes tee off first", sizes == sorted(sizes), sizes)
fp = next((p for p in res.get("gen_log", {}).get("holes", {}).get("9", {}).get("passes", [])
           if p.get("pass", "").startswith("final")), {})
bad = [mv for mv in fp.get("moves", []) if mv["cost_change"]["repeat_cost"] > 0
       and mv["cost_change"]["solo_season_cost"] < 0]
check("final pass never trades a deeper repeat for a solo point", not bad, bad)

print(f"{RUNS} independent seeds")
orig_seed = db.PAIRINGS_SEED
tally: dict = {}
try:
    for t in range(RUNS):
        db.PAIRINGS_SEED = f"rev-{t}"
        for x in misses(gen()[0]):
            key = x.split(" (")[-1].rstrip(")")
            tally[key] = tally.get(key, 0) + 1
finally:
    db.PAIRINGS_SEED = orig_seed
print(f"     rule misses over {RUNS} seeds: {tally or 'none'}")
check("no hard rule miss over any seed", not tally, tally)

print("audit on the generator's sheet")
db.save_event_pairings(EV, {"9": [{"group_num": i + 1, "slot_label": f"G{i+1}", "players": [
    {"name": n, "cart_pos": j + 1, "customer_id": CID[n], "tee_choice": TEE[n]}
    for j, n in enumerate(g)]} for i, g in enumerate(G)]})
a = event_pairing_audit(EV, db_path=DB)
hard = [f for f in a["flags"] if f["kind"] == "hard"]
check("audit: zero hard flags", not hard, hard)

print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED'}")
sys.exit(1 if F else 0)
