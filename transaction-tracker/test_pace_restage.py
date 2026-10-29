"""RE-STAGE BY PACE (Kerry 10/28, Event Ops #2483-3): after hand edits a
saved sheet re-orders its STARTS by pace; every group keeps its players and
its blinds.

Run: python3 test_pace_restage.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-pr-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
from email_parser import database as db       # noqa: E402
from email_parser import pace_restage as pr   # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

db.init_db(DB)
# pace: 1 slowest .. 3 fastest
PEOPLE = {
    # slow foursome
    1: ("Sam", "Slow", 1), 2: ("Sid", "Slow", 1), 3: ("Sal", "Slow", 1), 4: ("Sue", "Slow", 1),
    # fast foursome
    5: ("Fay", "Fast", 3), 6: ("Fin", "Fast", 3), 7: ("Flo", "Fast", 3), 8: ("Fred", "Fast", 3),
    # a threesome, unrated (reads as 2)
    9: ("Tom", "Three", None), 10: ("Tim", "Three", None), 11: ("Ted", "Three", None),
}
with db._connect(DB) as c:
    db._ensure_pairing_tables(c)
    for cid, (f, l, pace) in PEOPLE.items():
        c.execute("INSERT INTO customers (customer_id, first_name, last_name, pace_rating) VALUES (?,?,?,?)",
                  (cid, f, l, pace))
    sg = c.execute("INSERT INTO events (item_name, event_date, start_type) "
                   "VALUES ('s18 Shotgun', '2026-11-07', 'Shotgun') RETURNING id").fetchone()[0]
    tt = c.execute("INSERT INTO events (item_name, event_date, start_type) "
                   "VALUES ('s18 Tees', '2026-11-14', 'Tee Times') RETURNING id").fetchone()[0]
    st = c.execute("INSERT INTO events (item_name, event_date, start_type, pairing_mode) "
                   "VALUES ('s18 Standings', '2026-11-21', 'Tee Times', 'standings') RETURNING id").fetchone()[0]
    c.commit()


def seat(pos, cid):
    f, l, _ = PEOPLE[cid]
    return {"name": f"{f} {l}", "cart_pos": pos, "customer_id": cid, "tee_choice": None,
            "handicap_index": 10.0}


def group(gn, label, cids):
    return {"group_num": gn, "slot_label": label, "players": [seat(i + 1, c) for i, c in enumerate(cids)]}


def sheet(labels):
    # Hand-edited the wrong way round: slow first, the threesome last.
    return {"18": [group(1, labels[0], [1, 2, 3, 4]), group(2, labels[1], [5, 6, 7, 8]),
                   group(3, labels[2], [9, 10, 11])]}


def who(ev):
    with db._connect(DB) as c:
        rows = c.execute("SELECT group_num, slot_label, player_name FROM event_pairings "
                         "WHERE event_id = ? ORDER BY group_num, cart_pos", (ev,)).fetchall()
    out = {}
    for g, lab, n in rows:
        out.setdefault((g, lab), []).append(n.split()[1])
    return {k: v[0] for k, v in out.items()}


print("\n== tee times: the threesome first, then fastest; groups intact ==")
db.save_event_pairings(tt, sheet(["8:00 AM", "8:10 AM", "8:20 AM"]), db_path=DB)
p = pr.plan(tt, DB)
check("preview names 2 changes (the fast group already holds 8:10)", p["legs"]["18"]["changes"] == 2, p)
check("preview writes nothing", who(tt) == {(1, "8:00 AM"): "Slow", (2, "8:10 AM"): "Fast", (3, "8:20 AM"): "Three"},
      who(tt))
pr.apply(tt, DB, by="test")
check("applied: Three 8:00, Fast 8:10, Slow 8:20",
      who(tt) == {(1, "8:00 AM"): "Three", (2, "8:10 AM"): "Fast", (3, "8:20 AM"): "Slow"}, who(tt))
with db._connect(DB) as c:
    sizes = [r[0] for r in c.execute("SELECT COUNT(*) FROM event_pairings WHERE event_id = ? "
                                     "GROUP BY group_num ORDER BY group_num", (tt,))]
check("every player kept their group (3, 4, 4)", sizes == [3, 4, 4], sizes)
check("running it again moves nothing", pr.plan(tt, DB)["legs"]["18"]["changes"] == 0)

print("\n== shotgun: a blind travels with its group ==")
db.save_event_pairings(sg, sheet(["1A", "2A", "3A"]), db_path=DB)
with db._connect(DB) as c:
    # a blind in the threesome's open seat 4 (group 3)
    c.execute("INSERT INTO blind_draws (event_id, event_date, chapter, holes, group_num, slot_label, cart_pos, "
              "customer_id, player_name, slot_key, source) VALUES (?, '2026-11-07', 'San Antonio', '18', 3, "
              "'3A', 4, 1, 'Sam Slow', '18:3:4', 'app')", (sg,))
    c.commit()
r = pr.apply(sg, DB, by="test")
after = who(sg)
three_at = [k for k, v in after.items() if v == "Three"][0]
check("the threesome leads the train (3A, the front of a 1-3 shotgun)", three_at[1] == "3A", after)
with db._connect(DB) as c:
    b = c.execute("SELECT group_num, slot_label, slot_key FROM blind_draws WHERE event_id = ?", (sg,)).fetchone()
check("the blind follows the threesome to its new start",
      (b[0], b[1], b[2]) == (three_at[0], three_at[1], f"18:{three_at[0]}:4"), (tuple(b), three_at))
slow_at = [k for k, v in after.items() if v == "Slow"][0]
fast_at = [k for k, v in after.items() if v == "Fast"][0]
order = db.shotgun_train_order(["1A", "2A", "3A"], 18)
check("fast foursome goes off ahead of the slow one",
      order.index(fast_at[1]) < order.index(slow_at[1]), (order, fast_at, slow_at))

print("\n== standings on tee times: left alone ==")
db.save_event_pairings(st, sheet(["8:00 AM", "8:10 AM", "8:20 AM"]), db_path=DB)
p = pr.apply(st, DB, by="test")
check("skipped with the reason", "skipped" in p["legs"]["18"], p)
check("nothing moved", who(st) == {(1, "8:00 AM"): "Slow", (2, "8:10 AM"): "Fast", (3, "8:20 AM"): "Three"})

print("\n== an event with no sheet ==")
check("a clear error", "error" in pr.plan(99999, DB))

print(f"\n{'ALL PASS' if not F else f'{len(F)} FAILED: {F}'}")
sys.exit(1 if F else 0)
