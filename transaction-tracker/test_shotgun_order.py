"""SHOTGUN HOLE ORDER (Kerry 2026-10-28: "configure for different type of
starts and allowances for easily entering staging holes. Like I'm asking about
a reverse shotgun for Saturday ... I'd like to know that and enter it before
the generator runs so it generates correctly"). Per event, Edit Event's
"Shotgun hole order": blank = 1A, 1B, 2A…; "reverse" = the last hole first; a
list = the course's staging order. The generator deals it, and changing it
relabels a saved sheet by slot position.

Run: python3 test_shotgun_order.py
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

L, N = db.shotgun_hole_labels, db.normalize_shotgun_order

print("1. The labels")
check("blank is the standard 1A, 1B, 2A", L("", 1, 18, 4) == ["1A", "1B", "2A", "2B"])
check("reverse starts on 18", L("reverse", 1, 18, 4) == ["18A", "18B", "17A", "17B"])
check("reverse on a back nine starts on 18 and stays on the back", L("reverse", 10, 18, 18)[-2:] == ["10A", "10B"])
check("reverse on a front nine starts on 9", L("reverse", 1, 9, 2) == ["9A", "9B"])
check("a hole list deals A then B per hole", L(N("1 10 2 11"), 1, 18, 6) == ["1A", "1B", "10A", "10B", "2A", "2B"])
check("typed labels are used as typed, the rest follow in order",
      L(N("18A 18B 1A 3A"), 1, 18, 6) == ["18A", "18B", "1A", "3A", "1B", "2A"])
check("a hole off this nine is skipped", L(N("12 1"), 1, 9, 2) == ["1A", "1B"])
check("never runs short of groups", len(L(N("5"), 1, 9, 20)) == 20 and len(set(L(N("5"), 1, 9, 20))) == 20)

print("2. What a manager may type")
check("blank / standard store as blank", N("") == "" and N("Standard") == "")
check("reverse stores as reverse", N("Reverse") == "reverse" and N("reverse shotgun") == "reverse")
check("a list is tidied", N("1,10;2  11b") == "1, 10, 2, 11B")
for bad, why in (("19", "hole 19"), ("1A 1", "1A twice"), ("hole1", "not a hole")):
    try:
        N(bad)
        check(f"refuses {why}", False)
    except ValueError:
        check(f"refuses {why}", True)

print("3. The generator and the saved sheet")
SG, TT = 9811, 9812
with db._connect(DB) as conn:
    for eid, name, st in ((SG, "s18.81 SHOTGUN", "Shotgun"), (TT, "s18.82 TEE TIMES", "Tee Times")):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, start_time, "
                     "tee_time_count, tee_time_interval, course) VALUES (?, ?, '2099-12-19', 'San Antonio', 'active', "
                     "'18 Holes', ?, '08:00', 0, 10, 'Test Links')", (eid, name, st))
        for i in range(12):
            cid = 893000 + eid % 10 * 100 + i
            conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
                         "VALUES (?, ?, 'Gun', 'active_member')", (cid, f"G{eid}{i}"))
            conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, transaction_status, "
                         "order_date, order_id, email_uid, merchant) VALUES (?, ?, ?, ?, '18', 'active', '2099-12-01', "
                         "?, ?, 'GoDaddy')", (f"G{eid}{i} Gun", cid, name, eid, f"RS{eid}{i}", f"manual-s{eid}{i}"))
    conn.commit()

def labels(eid):
    sheet = db.get_event_pairings(eid, db_path=DB) or {}
    return [g["slot_label"] for g in sorted(sheet.get("18") or [], key=lambda g: g["group_num"])]

check("entered before the generator", db.update_event(SG, {"shotgun_order": "reverse"}, db_path=DB))
res = db.generate_event_pairings(SG, db_path=DB, save_log=False)
db.save_event_pairings(SG, {"18": res.get("18") or []}, db_path=DB)
got = labels(SG)
check("the generator deals 18A, 18B, 17A", got == ["18A", "18B", "17A"], got)
check("the events list carries the order for Edit Event",
      next(e for e in db.get_all_events(DB) if e["id"] == SG).get("shotgun_order") == "reverse")

r = db.set_shotgun_order(SG, "1 10", db_path=DB)
got = labels(SG)
check("changed after the generator: the saved sheet relabels by position",
      got == ["1A", "1B", "10A"] and r["relabelled"] == 3, (got, r))
db.update_event(SG, {"shotgun_order": ""}, db_path=DB)
got = labels(SG)
check("cleared: back to the standard", got == ["1A", "1B", "2A"], got)
check("cleared removes the setting", db.get_app_setting("shotgun_order:%d" % SG, db_path=DB) is None)

db.update_event(TT, {"shotgun_order": "reverse"}, db_path=DB)
res = db.generate_event_pairings(TT, db_path=DB, save_log=False)
got = [g["slot_label"] for g in sorted(res.get("18") or [], key=lambda g: g["group_num"])]
check("a tee-time event ignores it", got == ["8:00 AM", "8:10 AM", "8:20 AM"], got)

try:
    os.remove(DB)
except OSError:
    pass
print("\nALL PASS" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
