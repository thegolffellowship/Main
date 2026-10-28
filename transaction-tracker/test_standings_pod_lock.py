"""STANDINGS PODS ARE LOCKED (Kerry 2026-10-28, Event Ops #2483). On 3305 the
pods were built right (Mazanec, Marroquin, Vasquez + Fehlis in group 2) and
then rule 7 "spread leaders" and the rule-miss swaps pulled Marroquin and
Mazanec out. Kerry: "Luke Maz & Scott should have been paired together
because they were next on the points list, and then Gus Vasquez and Chuck
Fehlis with them".

Field: 2 Austin racers, 6 SA racers, Vasquez + Fehlis requested, eight
unranked players with no leader. Group 2 must stay Mazanec, Marroquin,
Vasquez, Fehlis, and the leaderless random groups are reported, not fixed
by breaking a pod.

Run: python3 test_standings_pod_lock.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                           # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


SA = ["Adam Baker", "Jeff Rideout", "Luke Mazanec", "Scott Marroquin", "Gus Vasquez", "Don Sharitz"]
AU = ["Luke Youngs", "Chris Cannon"]
OTHERS = ["Chuck Fehlis"] + [f"Rand{i} Player" for i in range(1, 8)]
CAPTAINS = {"Adam Baker", "Jeff Rideout", "Luke Youngs", "Chris Cannon", "Luke Mazanec", "Scott Marroquin"}
ids = {}
with db._connect(DB) as c:
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format,start_type,start_time,tee_time_count,course) "
              "VALUES (3305,'s18.12 FALL CHAMPIONSHIP','2099-10-31','TGF','active','18 Holes','Shotgun','08:30',0,'K')")
    for i, name in enumerate(SA + AU + OTHERS):
        cid = 500 + i
        ids[name] = cid
        fn, ln = name.split(" ", 1)
        c.execute("INSERT INTO customers (customer_id,first_name,last_name,current_player_status,group_captain) "
                  "VALUES (?,?,?,'active_member',?)", (cid, fn, ln, 1 if name in CAPTAINS else 0))
        c.execute("INSERT INTO items (customer,customer_id,item_name,event_id,holes,transaction_status,order_date,"
                  "order_id,email_uid,merchant,partner_request,customer_email) VALUES (?,?,'s18.12 FALL CHAMPIONSHIP',3305,'18',"
                  "'active','2099-10-01',?,?,'GoDaddy',?,?)",
                  (name, cid, f"R{cid}", f"e{cid}", "Chuck Fehlis" if name == "Gus Vasquez" else None, f"p{cid}@x.com"))
    c.commit()

_real = db._standings_rank_map


def fake(chapter, race_key=None, **kw):
    names = SA if race_key == "san_antonio_fall_net" else AU
    rm = {ids[n]: i + 1 for i, n in enumerate(names)}
    meta = {"points": {}, "enrolled": {}}
    return rm, race_key, [], meta


db._standings_rank_map = fake
r = db.generate_event_pairings(3305, mode="standings", race_key="san_antonio_fall_net,austin_fall_net",
                               db_path=DB, save_log=False)
db._standings_rank_map = _real
groups = [set(g["players"]) if isinstance(g["players"][0], str) else {p.get("name") or p.get("customer") for p in g["players"]}
          for g in r.get("18", [])]
want = {"Luke Mazanec", "Scott Marroquin", "Gus Vasquez", "Chuck Fehlis"}
check("Mazanec, Marroquin, Vasquez and Fehlis play together", any(want <= g for g in groups), groups)
check("the top pod stays together (Baker, Rideout, Youngs, Cannon)",
      any({"Adam Baker", "Jeff Rideout", "Luke Youngs", "Chris Cannon"} <= g for g in groups), groups)
notes = " ".join(r.get("notes") or r.get("mp_notes") or [])
check("leaderless groups are reported, not fixed by breaking a pod",
      "standings pods were kept" in notes, notes[:400])

try:
    os.remove(DB)
except OSError:
    pass
print("\nALL PASS" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
