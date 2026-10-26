"""WITHDRAWAL FOLD (Kerry 2026-10-26, CoS #2363-#2366): after a withdrawal the
sheet repairs itself. G = ceil(N/4); a group the field no longer needs
dissolves into the threesomes (seat-fill order) from 7:00 AM event day; a
group under 3 takes from a foursome at once (donor order: shotgun highest hole
first, B before A; tee times the first foursome); never a split request,
match or guest and host; nothing before the lock or inside the hour before the
first tee.

Run: python3 test_withdrawal_fold.py
"""
import os, sys, io, json, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import withdrawal_fold as wf
    from email_parser import after_lock as al
    db.init_db(DB)
from datetime import datetime

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

BASE = 870000
NAME = lambda i: f"W{i} Fold"
with db._connect(DB) as conn:
    for i in range(1, 46):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
                     "VALUES (?, ?, 'Fold', 'active_member')", (BASE + i, f"W{i}"))
    conn.commit()

# Tuesday 2099-12-15 (a weeknight: keep the latest times). Lock Monday 5:00 PM.
AFTER_LOCK = datetime(2099, 12, 14, 18, 0)     # C runs, B waits
SEVEN = datetime(2099, 12, 15, 7, 2)            # B runs too
_next = [9800]

def make(shape, sizes, roster=False, notes=None, requests=None):
    """An event with groups of these sizes. Returns (event_id, [group_nums])."""
    _next[0] += 1
    eid = _next[0]
    name = f"wf{eid} {shape}"
    with db._connect(DB) as conn:
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                     "start_time, tee_time_interval, tee_time_count, course) VALUES (?, ?, '2099-12-15', "
                     "'San Antonio', 'active', '9-hole', ?, ?, 10, ?, 'Test Links')",
                     (eid, name, "Tee Times" if shape == "tee" else "Shotgun",
                      "16:00" if shape == "tee" else "16:30", len(sizes)))
        conn.commit()
        ev = dict(conn.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone())
    labels = db._pairing_time_slots(ev, "9", needed=len(sizes))
    groups, n = [], 0
    for gi, size in enumerate(sizes):
        ps = []
        for pos in range(1, size + 1):
            n += 1
            ps.append({"name": NAME(n), "customer_id": BASE + n, "cart_pos": pos})
        groups.append({"group_num": gi + 1, "slot_label": labels[gi], "players": ps})
    if roster:
        with db._connect(DB) as conn:
            for i in range(1, n + 1):
                conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, "
                             "transaction_status, order_date, order_id, email_uid, merchant, notes, "
                             "partner_request) VALUES (?, ?, ?, ?, '9', 'active', '2099-12-01', ?, ?, "
                             "'GoDaddy', ?, ?)",
                             (NAME(i), BASE + i, name, eid, f"R{eid}-{i}", f"manual-{eid}-{i}",
                              (notes or {}).get(i), (requests or {}).get(i)))
            conn.commit()
    db.save_event_pairings(eid, {"9": groups}, db_path=DB)
    return eid

def sheet(eid):
    return sorted((db.get_event_pairings(eid, db_path=DB) or {}).get("9") or [], key=lambda g: g["group_num"])

def sizes(eid):
    return [len(g["players"]) for g in sheet(eid)]

def withdraw(eid, plan):
    """Players leave as remove_player_from_pairings leaves them: the group
    closes up (Kerry's re-seat), an emptied group is dropped."""
    gs = sheet(eid)
    for idx, k in plan:
        g = gs[idx]
        g["players"] = db._reseat_group_after_removal(sorted(g["players"], key=lambda p: p["cart_pos"])[k:])
    db.save_event_pairings(eid, {"9": [g for g in gs if g["players"]]}, db_path=DB)

def scenario(shape, before, plan, now=SEVEN):
    eid = make(shape, before)
    wf.observe(eid, db_path=DB)              # the job saw the sheet before the withdrawal
    labels = [g["slot_label"] for g in sheet(eid)]
    withdraw(eid, plan)
    res = wf.run(eid, apply=True, now=now, db_path=DB)
    return eid, res, labels

def shape_of(eid):
    s = sizes(eid)
    return f"{s.count(4)}F" + (f"+{s.count(3)}T" if s.count(3) else "") + (f"+{len(s) - s.count(4) - s.count(3)}other" if len(s) - s.count(4) - s.count(3) else "")

def moves(res):
    return (res.get("holes", {}).get("9") or {}).get("moves") or []

def by_num(eid):
    return {g["group_num"]: len(g["players"]) for g in sheet(eid)}

F40 = [4] * 10
F41 = [4, 3, 4, 4, 3, 4, 4, 4, 4, 3, 4]     # 8F + 3T (T = groups 2, 5, 10)
F39 = [4, 4, 4, 3, 4, 4, 4, 4, 4, 4]        # 9F + 1T (T = group 4)
F38 = [4, 3, 4, 4, 4, 4, 3, 4, 4, 4]        # 8F + 2T (T = groups 2, 7)
F37 = [4, 3, 4, 4, 3, 4, 4, 3, 4, 4]        # 7F + 3T (T = groups 2, 5, 8)

print("1. The ten cases, tee times and shotgun")
for shape in ("tee", "shotgun"):
    print(f" -- {shape}")
    # 40 -> 39, one from a foursome: no move
    e, r, _ = scenario(shape, F40, [(2, 1)])
    check(f"{shape} 40->39 (1 from F): no move, 9F+1T", not moves(r) and shape_of(e) == "9F+1T", (shape_of(e), r))
    # 40 -> 38, two from the same foursome: one donor -> 8F+2T
    e, r, _ = scenario(shape, F40, [(2, 2)])
    donor = moves(r)[0]["from_group"] if moves(r) else None
    want = 1 if shape == "tee" else 10          # tee: the first foursome; shotgun: 5B (highest hole, B first)
    check(f"{shape} 40->38 same F: one donor ({'first foursome' if shape == 'tee' else '5B'}) -> 8F+2T",
          len(moves(r)) == 1 and donor == want and moves(r)[0]["to_group"] == 3 and shape_of(e) == "8F+2T",
          (shape_of(e), moves(r)))
    # 40 -> 38, one each from two foursomes: no move
    e, r, _ = scenario(shape, F40, [(2, 1), (5, 1)])
    check(f"{shape} 40->38 different F: no move, 8F+2T", not moves(r) and shape_of(e) == "8F+2T", (shape_of(e), r))
    # 41 (8F+3T) -> 40, one from a foursome: the new threesome dissolves into the three -> 10F, release one
    e, r, labels = scenario(shape, F41, [(6, 1)])
    h = r["holes"]["9"]
    check(f"{shape} 41->40 (1 from F): the hit group 7 dissolves into the 3 T -> 10F",
          h.get("dissolved") == [labels[6]] and len(moves(r)) == 3
          and sorted(m["to_group"] for m in moves(r)) == [2, 5, 10] and shape_of(e) == "10F", (shape_of(e), h))
    if shape == "tee":
        with db._connect(DB) as conn:
            ev = dict(conn.execute("SELECT * FROM events WHERE id = ?", (e,)).fetchone())
        check("tee 41->40: group 7's time is released (and released_tee_times names it)",
              h.get("released") == [labels[6]] and labels[6] in db.released_tee_times(ev, db_path=DB),
              (h.get("released"), db.released_tee_times(ev, db_path=DB)))
    else:
        check("shotgun 41->40: no tee time to release", h.get("released") == [])
    # 41 -> 39, two from the same threesome: the single joins a threesome -> 9F+1T, release one
    e, r, labels = scenario(shape, F41, [(4, 2)])
    want = 10 if shape == "tee" else 2          # tee: latest threesome; shotgun: lowest hole, 1B
    check(f"{shape} 41->39 (2 from same T): the single joins group {want} -> 9F+1T",
          len(moves(r)) == 1 and moves(r)[0]["to_group"] == want and r["holes"]["9"]["dissolved"] == [labels[4]]
          and shape_of(e) == "9F+1T", (shape_of(e), moves(r)))
    # 41 -> 39, two from the same foursome: the twosome splits into two threesomes -> 9F+1T
    e, r, labels = scenario(shape, F41, [(6, 2)])
    want = [5, 10] if shape == "tee" else [2, 5]
    check(f"{shape} 41->39 (2 from same F): the twosome splits into groups {want} -> 9F+1T",
          sorted(m["to_group"] for m in moves(r)) == want and r["holes"]["9"]["dissolved"] == [labels[6]]
          and shape_of(e) == "9F+1T", (shape_of(e), moves(r)))
    # 39 (9F+1T) -> 38, one from the threesome: one donor -> 8F+2T
    e, r, _ = scenario(shape, F39, [(3, 1)])
    want = 1 if shape == "tee" else 10
    check(f"{shape} 39->38 (1 from T): one donor (group {want}) -> 8F+2T",
          len(moves(r)) == 1 and moves(r)[0]["from_group"] == want and moves(r)[0]["to_group"] == 4
          and shape_of(e) == "8F+2T", (shape_of(e), moves(r)))
    # 38 (8F+2T) -> 36, two from the same threesome: the single joins the other -> 9F, release one
    e, r, labels = scenario(shape, F38, [(1, 2)])
    check(f"{shape} 38->36 (2 from same T): the single joins the other threesome -> 9F",
          len(moves(r)) == 1 and moves(r)[0]["to_group"] == 7 and r["holes"]["9"]["dissolved"] == [labels[1]]
          and shape_of(e) == "9F", (shape_of(e), moves(r)))
    # 37 (7F+3T) -> 36, one from a threesome: the twosome splits into the other two -> 9F, release one
    e, r, labels = scenario(shape, F37, [(4, 1)])
    check(f"{shape} 37->36 (1 from T): the twosome splits into the other 2 T -> 9F",
          sorted(m["to_group"] for m in moves(r)) == [2, 8] and r["holes"]["9"]["dissolved"] == [labels[4]]
          and shape_of(e) == "9F", (shape_of(e), moves(r)))
    # 37 -> 35, two from the same foursome: the twosome splits into 2 of the 3 threesomes -> 8F+1T
    e, r, labels = scenario(shape, F37, [(0, 2)])
    want = [5, 8] if shape == "tee" else [2, 5]  # tee: latest first; shotgun: 1B, 3A before 4B
    left = 2 if shape == "tee" else 8
    check(f"{shape} 37->35 (2 from same F): the twosome goes to groups {want}, group {left} stays a T -> 8F+1T",
          sorted(m["to_group"] for m in moves(r)) == want and by_num(e).get(left) == 3
          and shape_of(e) == "8F+1T", (shape_of(e), moves(r), by_num(e)))

print("2. Timing")
e = make("tee", F41)
wf.observe(e, db_path=DB)
withdraw(e, [(6, 1)])                      # 41 -> 40: a dissolve is due
r = wf.run(e, apply=True, now=datetime(2099, 12, 14, 16, 59), db_path=DB)
check("before the lock: nothing", r.get("skipped") == "before the lock" and sizes(e).count(3) == 4, r)
r = wf.run(e, apply=True, now=AFTER_LOCK, db_path=DB)
check("Monday 6:00 PM: the dissolve waits for 7:00 AM (a late add may take the seat)",
      not r.get("applied") and r["holes"]["9"]["pending_dissolve"] and len(sizes(e)) == 11, r)
r = wf.run(e, apply=True, now=datetime(2099, 12, 15, 6, 47), db_path=DB)
check("6:47 AM event day: still waits", not r.get("applied") and len(sizes(e)) == 11)
r = wf.run(e, apply=True, now=SEVEN, db_path=DB)
check("7:02 AM event day: dissolved -> 10F", r.get("applied") and shape_of(e) == "10F", (r, shape_of(e)))
e2 = make("tee", F40)
wf.observe(e2, db_path=DB)
withdraw(e2, [(2, 2)])                     # a twosome: repaired at once
r = wf.run(e2, apply=True, now=AFTER_LOCK, db_path=DB)
check("a group under 3 is repaired at once (Monday 6:00 PM)", r.get("applied") and shape_of(e2) == "8F+2T", r)
e3 = make("tee", F40)
wf.observe(e3, db_path=DB)
withdraw(e3, [(2, 2)])
r = wf.run(e3, apply=True, now=datetime(2099, 12, 15, 15, 5), db_path=DB)
check("inside the hour before the 4:00 PM first tee: nothing (no-show sequence)",
      "within the hour" in (r.get("skipped") or "") and 2 in sizes(e3), r)
r = wf.run(e3, apply=True, now=datetime(2099, 12, 15, 16, 30), db_path=DB)
check("after the first tee: nothing", r.get("skipped") == "first tee passed" and 2 in sizes(e3), r)
e4 = make("tee", [4, 3, 3, 3])             # 13 -> 12 (Kerry 10/17's W3)
wf.observe(e4, db_path=DB)
withdraw(e4, [(3, 1)])                     # 4,3,3,2 before 7 AM: repaired at once, dissolve waits
wf.run(e4, apply=True, now=AFTER_LOCK, db_path=DB)
check("13->12 at night: the twosome takes one from the foursome -> 3,3,3,3 (four open seats kept)",
      sizes(e4) == [3, 3, 3, 3], sizes(e4))
wf.run(e4, apply=True, now=SEVEN, db_path=DB)
check("13->12 at 7:02 AM: the hit threesome dissolves into the others -> 4,4,4",
      sorted(sizes(e4)) == [4, 4, 4] and 4 not in by_num(e4), by_num(e4))

print("3. Constraints")
# a requested pair is the twosome left by 37 -> 36: they never split; a threesome dissolves instead
e = make("tee", F37, roster=True, requests={17: "W18 Fold", 18: "W17 Fold"})
wf.observe(e, db_path=DB)
withdraw(e, [(4, 1)])                      # group 5 (W16, W17, W18) loses W16: W17 + W18 requested each other
pair_grp = lambda: [g["group_num"] for g in sheet(e) for p in g["players"] if p["name"] in ("W17 Fold", "W18 Fold")]
r = wf.run(e, apply=True, now=SEVEN, db_path=DB)
g = pair_grp()
check("the requested pair is never split: a threesome dissolves instead, every group 3-4, 9 groups",
      len(set(g)) == 1 and len(sizes(e)) == 9 and all(3 <= s <= 4 for s in sizes(e))
      and not any(m["name"] in ("W17 Fold", "W18 Fold") for m in moves(r)), (g, sizes(e), moves(r)))
# guest + host: the first foursome is a host with three guests, so the donor is the next foursome
e = make("tee", F40, roster=True, notes={2: "Purchased by W1 Fold", 3: "Purchased by W1 Fold",
                                         4: "Purchased by W1 Fold"})
wf.observe(e, db_path=DB)
withdraw(e, [(2, 2)])
r = wf.run(e, apply=True, now=AFTER_LOCK, db_path=DB)
check("a guest is never taken from the host: the donor is group 2, group 1 is intact",
      len(moves(r)) == 1 and moves(r)[0]["from_group"] == 2 and by_num(e)[1] == 4, moves(r))
# blocked: both foursomes are host + three guests -> nothing changes, ONE COO item
e = make("tee", [4, 4, 4], roster=True, notes={2: "Purchased by W1 Fold", 3: "Purchased by W1 Fold",
                                               4: "Purchased by W1 Fold", 6: "Purchased by W5 Fold",
                                               7: "Purchased by W5 Fold", 8: "Purchased by W5 Fold"})
wf.observe(e, db_path=DB)
withdraw(e, [(2, 2)])
before = sizes(e)
r = wf.run(e, apply=True, now=AFTER_LOCK, db_path=DB)
wf.run(e, apply=True, now=datetime(2099, 12, 14, 18, 15), db_path=DB)
with db._connect(DB) as conn:
    coo = conn.execute("SELECT summary FROM action_items WHERE subject LIKE 'WITHDRAWAL FOLD BLOCKED%'").fetchall()
check("blocked: nothing moves", sizes(e) == before == [4, 4, 2] and r.get("blocked"), (sizes(e), r))
check("blocked: ONE COO item, not raised again on the next run", len(coo) == 1, coo)

print("4. The job, the dial, the log, the bridge")
e = make("shotgun", F40)
wf.observe(e, db_path=DB)
withdraw(e, [(0, 2)])
dry = wf.run(e, apply=False, now=AFTER_LOCK, db_path=DB)
check("the read-only plan writes nothing", dry.get("dry_run") and 2 in sizes(e) and moves(dry), dry)
db.set_app_setting(wf.DIAL, "off", db_path=DB)
check("withdrawal_fold_auto=off stops it", wf.check(now=AFTER_LOCK, db_path=DB)["status"] == "off" and 2 in sizes(e))
db.set_app_setting(wf.DIAL, "", db_path=DB)
res = wf.check(now=AFTER_LOCK, db_path=DB)
check("the job folds it", e in res["events"] and 2 not in sizes(e), res["events"].get(e))
with db._connect(DB) as conn:
    logged = conn.execute("SELECT COUNT(*) FROM agent_action_log WHERE action_type = 'withdrawal_fold' "
                          "AND description LIKE ?", (f"event {e} %",)).fetchone()[0]
check("every applied move is in agent_action_log", logged == 1, logged)
_m = open("mcp_server.py", encoding="utf-8").read()
check("bridge scoring-withdrawal-fold is read only", 'cmd == "scoring-withdrawal-fold"' in _m
      and "_wf.run(int(_p[0]), apply=False)" in _m)
_a = open("app.py", encoding="utf-8").read()
check("the fold runs right after seat-fill, before the after-lock emails",
      _a.index("seat_fill import check as _seat_fill") < _a.index("withdrawal_fold import check as _fold")
      < _a.index("res = check(_print_pack_render, app.static_folder)"))

print("5. after_lock sees the fold")
e = make("tee", F40)
wf.observe(e, db_path=DB)
withdraw(e, [(2, 2)])
al.record_sent(e, db_path=DB)              # the sheet as the Event Info carried it
r = wf.run(e, apply=True, now=AFTER_LOCK, db_path=DB)
p = al.plan(e, db_path=DB)
mover = str(moves(r)[0]["customer_id"]) if moves(r) else None
check("after_lock's diff shows the moved player and both groups",
      p.get("changed") and p["diff"]["moved"] == [mover] and p["diff"]["groups"] == {"9|1", "9|3"},
      p.get("diff"))

print("6. Rule 17's re-deal waits for the fold after the lock")
e = make("tee", [4, 4, 4, 3, 3, 2])
with db._connect(DB) as conn:
    conn.execute("UPDATE events SET lock_override = '2000-01-01 17:00' WHERE id = ?", (e,))
    conn.commit()
out = db.remove_player_from_pairings(e, NAME(20), dry_run=True, db_path=DB)
check("after the lock, a removal closes up the group and leaves the regroup to the fold",
      out["regrouped"] and "withdrawal fold" in (out["regrouped"][0].get("reason") or ""), out["regrouped"])
db.set_app_setting(wf.DIAL, "off", db_path=DB)
out = db.remove_player_from_pairings(e, NAME(20), dry_run=True, db_path=DB)
check("with the fold off, rule 17 runs as before",
      "withdrawal fold" not in (out["regrouped"][0].get("reason") or ""), out["regrouped"])
db.set_app_setting(wf.DIAL, "", db_path=DB)

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
