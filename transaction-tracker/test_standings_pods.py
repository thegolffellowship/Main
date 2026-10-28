"""MULTI-RACE STANDINGS PODS (Kerry 2026-10-28, the Fall Championship): pick
two races and each group takes the top 2 of each, then the next 2; when one
race runs out the other carries on, then everyone else at random; partner
requests trump; the 5:00 PM run uses the saved choice; only active races are
offered.

Run: python3 test_standings_pods.py
"""
import os, sys, io, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

K = db._pair_key_name
sa = {K(f"S{i} Sa"): i for i in range(1, 7)}       # 6 in the SA race
au = {K(f"A{i} Au"): i for i in range(1, 5)}       # 4 in the Austin race
others = [f"X{i} Guest" for i in range(1, 7)]
players = [f"S{i} Sa" for i in range(6, 0, -1)] + [f"A{i} Au" for i in range(4, 0, -1)] + others
g, notes = db._standings_pods(players, [sa, au], {}, True, max_group=4, seed=1)
check("16 players, 4 foursomes", sorted(len(x) for x in g) == [4, 4, 4, 4], g)
check("group 1 = SA top 2 + Austin top 2", set(g[0]) == {"S1 Sa", "S2 Sa", "A1 Au", "A2 Au"}, g[0])
check("group 2 = the next two of each", set(g[1]) == {"S3 Sa", "S4 Sa", "A3 Au", "A4 Au"}, g[1])
check("Austin runs out: SA carries on (S5, S6) then the rest at random",
      {"S5 Sa", "S6 Sa"} <= set(g[2]) and len(set(g[2]) & set(others)) == 2, g[2])
check("everyone placed once", sorted(sum(g, [])) == sorted(players))

pm = {"S1 Sa": "X3 Guest"}
g2, _ = db._standings_pods(players, [sa, au], pm, True, max_group=4, seed=1)
check("a partner request trumps: S1's partner rides with him in group 1",
      {"S1 Sa", "X3 Guest"} <= set(g2[0]), g2[0])
g3, _ = db._standings_pods(players, [sa, au], pm, False, max_group=4, seed=1)
check("requests off: back to pure pods", set(g3[0]) == {"S1 Sa", "S2 Sa", "A1 Au", "A2 Au"}, g3[0])

print("2. Only active races are offered")
opts = db.pairing_race_options("TGF", "s18.12 FALL CHAMPIONSHIP", db_path=DB)
keys = [o["race_key"] for o in opts]
check("only the active fall races, both default on a TGF event",
      sorted(keys) == ["austin_fall_net", "san_antonio_fall_net"] and all(o["is_default"] for o in opts), opts)
sa_opts = db.pairing_race_options("San Antonio", "s9.30 X", db_path=DB)
check("a chapter event defaults to its own race",
      [o["race_key"] for o in sa_opts if o["is_default"]] == ["san_antonio_fall_net"], sa_opts)

print("3. The 5:00 PM run uses the saved choice")
import inspect
src = inspect.getsource(db.auto_generate_pairings)
check("auto run passes the saved pairing_mode and race keys",
      'ev.get("pairing_mode")' in src and 'ev.get("pairing_race_key")' in src)

print("4. Shotgun: pace decides the order; tee times: leaders last (Kerry 10/28)")
with db._connect(DB) as c:
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format,start_type,start_time,tee_time_count,course) "
              "VALUES (77,'s18.97 SG','2099-12-19','TGF','active','18 Holes','Shotgun','08:30',0,'T')")
    for i in range(10):
        c.execute("INSERT INTO customers (customer_id,first_name,last_name,current_player_status) VALUES (?,?,'Q','active_member')", (970 + i, f"Q{i}"))
        c.execute("INSERT INTO items (customer,customer_id,item_name,event_id,holes,transaction_status,order_date,order_id,email_uid,merchant) "
                  "VALUES (?,?,'s18.97 SG',77,'18','active','2099-12-01',?,?,'GoDaddy')", (f"Q{i} Q", 970 + i, f"RQ{i}", f"manual-q{i}"))
    c.commit()
for mode, rk in (("random", None), ("standings", "san_antonio_fall_net"), ("standings", "san_antonio_fall_net,austin_fall_net")):
    r = db.generate_event_pairings(77, mode=mode, race_key=rk, db_path=DB, save_log=False)
    sizes = {g["slot_label"]: len(g["players"]) for g in r.get("18", [])}
    check(f"an 18-hole shotgun ({mode}{', ' + rk if rk else ''}): threesomes lead the pack (2A, 1A), the foursome behind (1B)",
          sizes == {"2": 3, "1A": 3, "1B": 4}, sizes)
import inspect
src = inspect.getsource(db.generate_event_pairings)
check("leaders-last only when not a shotgun", "and not is_shotgun)" in src)

print("5. The PAIRINGS tab reads the SAVED races (Kerry 10/28: both Fall races green, POINTS toggle)")
_app_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")).read()
check("GET /pairings falls back to the event's pairing_race_key, not the chapter default",
      'request.args.get("race_key") or ev.get("pairing_race_key")' in _app_src)

try:
    os.remove(DB)
except OSError:
    pass
print("\nALL PASS" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
