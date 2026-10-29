"""The R-A HOST EXCEPTION in the generator (Kerry 2026-10-29).

Kerry, verbatim: "Eric Carstens is with the person, Matthew Jenkins, who
invited him and he requested. So no ambassador needed."

The pairings AUDIT already knew it; the GENERATOR (`_rules_fix`: rule 14's
`_pair_first_timers_with_ambassadors` and the rules 16/18 rule-miss swaps)
did not, and moved an Ambassador into the 1st Timer's group anyway. Both now
read ONE definition, `database._host_in_group`.

Covers: the helper (host by order, request either way, nobody); rule 14's
fixer leaves a covered group alone and still fixes an uncovered one; the
generator keeps the Ambassador away from a 1st Timer who is with his host
when history says so, and (control) puts him there when the exception is
switched off; the audit and the generator share the helper.

Run: python3 test_pairings_host_exception.py
"""
import os, sys, tempfile, logging, inspect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
from email_parser import pairings_audit                           # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []
K = db._pair_key_name


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


print("unit: _host_in_group")
host_of = {K("Eric Carstens"): K("Matthew Jenkins")}
G = ["Eric Carstens", "Matthew Jenkins", "Pat One", "Sam Two"]
check("host by order / Purchased-by", db._host_in_group("Eric Carstens", G, host_of, set()) == "Matthew Jenkins")
rq = {frozenset((K("Matthew Jenkins"), K("Eric Carstens")))}
check("requested (either direction)", db._host_in_group("Eric Carstens", G, {}, rq) == "Matthew Jenkins")
check("host not in the group: None",
      db._host_in_group("Eric Carstens", ["Eric Carstens", "Pat One"], host_of, rq) is None)
check("nobody: None", db._host_in_group("Eric Carstens", G, {}, set()) is None)

print("unit: rule 14 fixer")
groups = [["Eric Carstens", "Matthew Jenkins", "Pat One", "Sam Two"],
          ["Amb One", "Cap Two", "Lee Three", "Max Four"]]
tees = {n: "50-64" for g in groups for n in g}
out, _n = db._pair_first_timers_with_ambassadors(
    groups, {"Amb One"}, {"Eric Carstens"}, tees, set(), {}, set(),
    host_of=host_of, req_keys=rq)
check("1st Timer with his host: no swap", out == groups, out)
out2, _n = db._pair_first_timers_with_ambassadors(
    groups, {"Amb One"}, {"Eric Carstens"}, tees, set(), {}, set())
check("control, no host information: the Ambassador is swapped in",
      "Amb One" in out2[0], out2)
g3 = [["Eric Carstens", "Pat One", "Sam Two", "Matthew Jenkins"][:3] + ["Lee Three"],
      ["Amb One", "Cap Two", "Matthew Jenkins", "Max Four"]]
out3, _n = db._pair_first_timers_with_ambassadors(
    g3, {"Amb One"}, {"Eric Carstens"}, {n: "50-64" for g in g3 for n in g}, set(), {}, set(),
    host_of=host_of, req_keys=rq)
check("host in ANOTHER group: still fixed (the exception is the group, not the sheet)",
      "Amb One" in out3[0], out3)

print("generator: guest + host requested together, Ambassador nearby")
EV = 7100
PLAYERS = [  # name, status, user_status, ambassador, captain, request
    ("Matthew Jenkins", "active_member", "MEMBER", 0, 0, "Eric Carstens"),
    ("Eric Carstens", "first_timer", "1ST TIMER", 0, 0, "Matthew Jenkins"),
    ("Amb One", "active_member", "MEMBER", 1, 1, None),
    ("Cap Two", "active_member", "MEMBER", 0, 1, None),
    ("Pat One", "active_member", "MEMBER", 0, 0, None),
    ("Sam Two", "active_member", "MEMBER", 0, 0, None),
    ("Lee Three", "active_member", "MEMBER", 0, 0, None),
    ("Max Four", "active_member", "MEMBER", 0, 0, None)]
with db._connect(DB) as c:
    db._ensure_pairing_tables(c)
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status) VALUES "
              "(7000,'earlier','2026-03-01','San Antonio','active')")
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format,start_time,start_type,course) "
              "VALUES (?,?,?,?,?,?,?,?,?)", (EV, "Host Exception", "2026-12-15", "San Antonio", "active",
                                              "9 Holes", "4:30 PM", "Tee Times", "Course"))
    for i, (n, st, us, amb, cap, req) in enumerate(PLAYERS):
        cid = 7100 + i
        fn, ln = n.split(" ", 1)
        c.execute("INSERT INTO customers (customer_id,first_name,last_name,current_player_status,"
                  "group_captain,ambassador) VALUES (?,?,?,?,?,?)", (cid, fn, ln, st, cap, amb))
        if st != "first_timer":
            c.execute("INSERT INTO customer_memberships (customer_id,started_at,expires_at,source) "
                      "VALUES (?,?,?,'manual')", (cid, "2019-02-01", "2027-02-01"))
            c.execute("INSERT INTO items (customer,customer_id,item_name,holes,tee_choice,transaction_status,"
                      "order_date,order_id,email_uid,merchant,user_status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (n, cid, "earlier", "9", "50-64", "active", "2026-03-01", f"E{cid}", f"manual-e{cid}",
                       "GoDaddy", "MEMBER"))
        # Jenkins bought Carstens's spot: one order, Carstens's row Purchased-by
        same = n in ("Matthew Jenkins", "Eric Carstens")
        c.execute("INSERT INTO items (customer,customer_id,item_name,event_id,holes,tee_choice,"
                  "transaction_status,order_date,order_id,email_uid,merchant,user_status,partner_request,"
                  "notes,customer_email) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (n, cid, "Host Exception", EV, "9", "50-64", "active", "2026-12-01",
                   "R7100J" if same else f"R{cid}", f"gm-{cid}", "GoDaddy", us, req,
                   "Purchased by Matthew Jenkins" if n == "Eric Carstens" else None,
                   None if n == "Eric Carstens" else f"p{cid}@example.com"))
    # The Ambassador has played with Jenkins three times: history keeps him away.
    for k in range(3):
        c.execute("INSERT INTO pairing_history (player_a,player_b,event_id,event_date,rode,source) "
                  "VALUES (?,?,?,?,0,'gg_teamnet')", ("Amb One", "Matthew Jenkins", 7000 + k, "2026-06-01"))
    c.commit()


def gen(seed):
    orig = db.PAIRINGS_SEED
    db.PAIRINGS_SEED = seed
    try:
        res = db.generate_event_pairings(EV, mode="random", protect_partner_requests=True, db_path=DB)
    finally:
        db.PAIRINGS_SEED = orig
    return [[p["name"] for p in g["players"]] for g in res["9"]], res


with db._connect(DB) as c:
    rows = db._event_roster_rows(c, EV)
ft = {r["customer"] for r in rows if r.get("is_first_timer")}
check("fixture: Eric Carstens reads as a 1st Timer", "Eric Carstens" in ft, ft)

bad, last = 0, None
for t in range(8):
    G2, res = gen(f"host-{t}")
    last = G2
    eg = next(g for g in G2 if "Eric Carstens" in g)
    if "Matthew Jenkins" not in eg or "Amb One" in eg:
        bad += 1
    passes = (((res.get("gen_log") or {}).get("holes") or {}).get("9") or {}).get("passes")
    if passes is None:
        bad += 100   # the log moved: the check below would read nothing
        passes = []
    moved = [p for p in passes
             if p.get("pass", "").startswith(("1st Timer + Ambassador", "rule-miss swaps"))
             and any("Amb One" in m for m in p.get("moved", []))]
    if moved:
        bad += 1
check("over 8 seeds: Carstens with Jenkins, no Ambassador moved in for him", bad == 0, last)

# Control: switch the exception off and the old behaviour comes back.
_orig = db._host_in_group
db._host_in_group = lambda *a, **k: None
try:
    G3, _ = gen("host-0")
finally:
    db._host_in_group = _orig
eg3 = next(g for g in G3 if "Eric Carstens" in g)
check("control: without the exception the Ambassador is moved to him", "Amb One" in eg3, G3)

print("one definition")
src = inspect.getsource(pairings_audit)
check("the audit calls db._host_in_group", "db._host_in_group(" in src)
check("the audit has no second copy of the test", 'K(p.get("invited_by") or "") == K(x["name"])' not in src)

print()
print("ALL PASS" if not F else f"{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
