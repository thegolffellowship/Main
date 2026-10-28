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
check("reverse keeps hole 1, then 18 backward (Kerry 10/28)", L("reverse", 1, 18, 4) == ["1A", "1B", "18A", "18B"])
check("reverse on a back nine: 10, then 18 backward to 11", L("reverse", 10, 18, 18)[:4] == ["10A", "10B", "18A", "18B"]
      and L("reverse", 10, 18, 18)[-2:] == ["11A", "11B"])
check("reverse on a front nine: 1, then 9", L("reverse", 1, 9, 3) == ["1A", "1B", "9A"])
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
check("the generator deals 1A, 1B, 18A", got == ["1A", "1B", "18A"], got)
check("the events list carries the order for Edit Event",
      next(e for e in db.get_all_events(DB) if e["id"] == SG).get("shotgun_order") == "reverse")

r = db.set_shotgun_order(SG, "1 10", db_path=DB)
got = labels(SG)
check("changed after the generator: the saved sheet relabels by position",
      got == ["1A", "1B", "10A"] and r["relabelled"] == 1, (got, r))
db.update_event(SG, {"shotgun_order": ""}, db_path=DB)
got = labels(SG)
check("cleared: back to the standard", got == ["1A", "1B", "2A"], got)
check("cleared removes the setting", db.get_app_setting("shotgun_order:%d" % SG, db_path=DB) is None)

db.update_event(TT, {"shotgun_order": "reverse"}, db_path=DB)
res = db.generate_event_pairings(TT, db_path=DB, save_log=False)
got = [g["slot_label"] for g in sorted(res.get("18") or [], key=lambda g: g["group_num"])]
check("a tee-time event ignores it", got == ["8:00 AM", "8:10 AM", "8:20 AM"], got)

print("4. One group on a par 3 or a par 4 under 325 from the <50 tees (Kerry 10/28)")
# Kissing Tree's Back (<50) card: (par, yards) by hole.
KT = {1: (4, 305), 2: (3, 165), 3: (5, 533), 4: (3, 177), 5: (5, 550), 6: (4, 413), 7: (4, 400),
      8: (4, 362), 9: (4, 320), 10: (4, 345), 11: (4, 415), 12: (3, 206), 13: (4, 444), 14: (5, 567),
      15: (3, 132), 16: (4, 367), 17: (5, 500), 18: (4, 283)}
CRS, KTE = 99881, 9813
with db._connect(DB) as conn:
    conn.execute("INSERT INTO courses (course_id, name) VALUES (?, 'Test Kissing Tree')", (CRS,))
    cur = conn.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, tgf_bands) "
                       "VALUES (?, 'Back', 'M', 18, '<50')", (CRS,))
    tid = cur.lastrowid
    for h, (par, yd) in KT.items():
        conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage) VALUES (?, ?, ?, ?)",
                     (tid, h, par, yd))
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, start_time, "
                 "tee_time_count, course, course_id) VALUES (?, 's18.83 KT', '2099-12-19', 'TGF', 'active', "
                 "'18 Holes', 'Shotgun', '08:00', 7, 'Test Kissing Tree', ?)", (KTE, CRS))
    conn.commit()
    e = dict(conn.execute("SELECT * FROM events WHERE id = ?", (KTE,)).fetchone())
    caps = db._shotgun_caps_conn(conn, e)
check("short holes take one: 1 (305), 2, 4, 9 (320), 12, 15, 18 (283)",
      sorted(h for h, c in caps.items() if c == 1) == [1, 2, 4, 9, 12, 15, 18], caps)
check("a 345-yard par 4 takes two", caps.get(10) == 2)
e["shotgun_caps"], e["shotgun_order"] = caps, ""
got = db._pairing_time_slots(e, "18")
check("standard: 1A, 2A, 3A, 3B, 4A, 5A, 5B", got == ["1A", "2A", "3A", "3B", "4A", "5A", "5B"], got)
e["shotgun_order"] = "reverse"
got = db._pairing_time_slots(e, "18")
check("reverse: hole 1 takes two by default (Kerry 10/28), then 18 down",
      got == ["1A", "1B", "18A", "17A", "17B", "16A", "16B"], got)
check("a listed short hole still takes one", L(N("2 3"), 1, 18, 3, caps) == ["2A", "3A", "3B"])
check("a typed B on a short hole is used as typed", L(N("2A 2B"), 1, 18, 2, caps) == ["2A", "2B"])
check("a full course: the short holes take a B before any overflow",
      len(L("", 1, 18, 30, caps)) == 30 and L("", 1, 18, 30, caps)[-1] == "1B" and "19A" not in L("", 1, 18, 36, caps))
check("no card: every hole takes two (the old standard)", L("", 1, 18, 3, {}) == ["1A", "1B", "2A"])

print("5. The staging grid on Edit Event (Kerry 10/28)")
for i in range(28):
    cid = 895000 + i
    with db._connect(DB) as conn:
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
                     "VALUES (?, ?, 'Stage', 'active_member')", (cid, f"S{i}"))
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, transaction_status, "
                     "order_date, order_id, email_uid, merchant) VALUES (?, ?, 's18.83 KT', ?, '18', 'active', "
                     "'2099-12-01', ?, ?, 'GoDaddy')", (f"S{i} Stage", cid, KTE, f"RG{i}", f"manual-g{i}"))
        conn.commit()
st = db.shotgun_staging(KTE, db_path=DB)
check("28 players need 7 groups", st["groups_needed"] == 7, st["groups_needed"])
check("the grid shows 18 holes in order with par and yards",
      [r["hole"] for r in st["rows"]] == list(range(1, 19)) and st["rows"][1]["par"] == 3 and st["rows"][0]["yards"] == 305)
check("default counts follow the rule: 1,1,2,1,2 then 0",
      [r["groups"] for r in st["rows"]][:6] == [1, 1, 2, 1, 2, 0], [r["groups"] for r in st["rows"]][:6])
rv = db.shotgun_staging(KTE, reverse=True, db_path=DB)
check("Reverse previews 1 then 18 backward: 1,18,17,16,15",
      [(r["hole"], r["groups"]) for r in rv["rows"]][:5] == [(1, 2), (18, 1), (17, 2), (16, 2), (15, 0)])
db.update_event(KTE, {"shotgun_staging": {"reverse": False, "locked": True,
                                           "counts": {"1": 2, "2": 1, "10": 2, "11": 2},
                                           "hole_order": list(range(1, 19))}}, db_path=DB)
st = db.shotgun_staging(KTE, db_path=DB)
check("Lock keeps the manager's counts", st["locked"] and
      {r["hole"]: r["groups"] for r in st["rows"] if r["groups"]} == {1: 2, 2: 1, 10: 2, 11: 2}, st["rows"])
check("the generator deals the locked grid",
      db.shotgun_hole_labels(db.shotgun_order_of({"id": KTE, "shotgun_order": st["order"]}), 1, 18, 7, caps)
      == ["1A", "1B", "2A", "10A", "10B", "11A", "11B"], st["order"])
db.update_event(KTE, {"shotgun_staging": {"reverse": True, "locked": False}}, db_path=DB)
st = db.shotgun_staging(KTE, db_path=DB)
check("unlocked + Reverse goes back to the rule, reversed", st["order"] == "reverse" and not st["locked"]
      and st["labels"][:3] == ["1A", "1B", "18A"], st)

print("6. After par 3s, one group (Kerry 10/28) and the front of the pack")
info = {h: v for h, v in KT.items()}
c2 = db.shotgun_caps_from_info(info, after_par3=True)
check("a par 3 takes two and the hole after it one (2->3, 4->5, 12->13, 15->16)",
      c2[2] == 2 and c2[3] == 1 and c2[5] == 1 and c2[13] == 1 and c2[16] == 1, c2)
check("short par 4s still take one", c2[1] == 1 and c2[9] == 1 and c2[18] == 1)
ap = db.shotgun_staging(KTE, reverse=False, after_par3=True, db_path=DB)
check("the grid previews the option", ap["after_par3"] and [r["groups"] for r in ap["rows"]][:5] == [1, 2, 1, 2, 1], [r["groups"] for r in ap["rows"]][:6])
check("standard front of the pack: highest loaded hole first",
      db.shotgun_train_order(["1A", "2A", "3A", "3B", "4A", "5A", "5B"]) == ["5A", "5B", "4A", "3A", "3B", "2A", "1A"])
check("reverse front of the pack: hole 1 leads, 15 is last",
      db.shotgun_train_order(["1A", "18A", "17A", "17B", "16A", "15A"]) == ["1A", "18A", "17A", "17B", "16A", "15A"])
check("a back nine loops on itself", db.shotgun_train_order(["10A", "18A", "17A"], ring=9) == ["10A", "18A", "17A"])
groups = [["a", "b", "c", "d"], ["e", "f", "g"], ["h", "i", "j", "k"]]
out = db._stage_shotgun_smalls_lead(groups, ["1A", "18A", "17A"], lambda g: 2, lambda g: 0)
check("the threesome leads a reverse shotgun from hole 1", out[0] == ["e", "f", "g"], out)
db.update_event(KTE, {"shotgun_staging": {"reverse": False, "locked": False, "after_par3": True}}, db_path=DB)
check("saving the option keeps it", db.shotgun_staging(KTE, db_path=DB)["after_par3"])

print("7. Late adds and withdrawals follow the pack in play order")
from email_parser.seat_fill import fill_order
from email_parser.withdrawal_fold import donor_order
G = lambda l: {"slot_label": l, "group_num": 0, "players": []}
std = [G(x) for x in ["1A", "1B", "2A", "3A", "3B"]]
check("standard: late adds fill from the back (1B first), unchanged",
      [g["slot_label"] for g in fill_order(std)] == ["1B", "1A", "2A", "3B", "3A"])
check("standard: donors from the front (3B first), unchanged",
      [g["slot_label"] for g in donor_order(std)] == ["3B", "3A", "2A", "1B", "1A"])
rev = [G(x) for x in ["1A", "18A", "17A", "17B", "16A"]]
check("reverse: late adds fill from the back of the pack (16 first)",
      [g["slot_label"] for g in fill_order(rev)] == ["16A", "17B", "17A", "18A", "1A"])
check("reverse: donors from the front of the pack (1 first)",
      [g["slot_label"] for g in donor_order(rev)] == ["1A", "18A", "17B", "17A", "16A"])

# Kerry 10/28: "If for instance we had 3somes in hole 1A (lead group), 1B, and
# 18A, then the first late add would go to the threesome in 18A. A second late
# add would go to 1B, then the next to 1A. If it was threesomes on single stage
# holes like 1 then 18, then 17A, it would start to fill at 17a on late adds."
def first_open(groups):
    return [g["slot_label"] for g in fill_order(groups) if len(g["players"]) < 4]
P = lambda n: [{}] * n
k1 = [{"slot_label": l, "group_num": 0, "players": P(n)} for l, n in
      (("1A", 3), ("1B", 3), ("18A", 3), ("17A", 4), ("17B", 4), ("16A", 4))]
check("Kerry's example: late adds go 18A, then 1B, then 1A", first_open(k1) == ["18A", "1B", "1A"], first_open(k1))
k2 = [{"slot_label": l, "group_num": 0, "players": P(n)} for l, n in
      (("1A", 3), ("18A", 3), ("17A", 3), ("17B", 4), ("16A", 4))]
check("Kerry's example: threesomes on 1, 18, 17A fill from 17A", first_open(k2)[0] == "17A", first_open(k2))

try:
    os.remove(DB)
except OSError:
    pass
print("\nALL PASS" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
