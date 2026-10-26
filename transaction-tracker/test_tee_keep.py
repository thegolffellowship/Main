"""UNUSED TEE TIMES (Kerry 2026-10-26, CoS #2331 A / #2332): when a tee-time
event holds more times than its groups need, a weeknight keeps the LATEST
times and releases the earliest; a weekend keeps the EARLIEST and releases the
latest; events.tee_keep (Edit Event) flips one event. The course's tee-times
email names each released time. Shotguns are untouched.

Run: python3 test_tee_keep.py
"""
import os, sys, io, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import teetimes_email as tt
    db.init_db(DB)

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

# Five tee times from 3:40 PM, ten minutes apart; twelve players = three groups.
TUE, SAT, FLIP, SG = 9801, 9802, 9803, 9804
EVENTS = ((TUE, "s9.91 TUESDAY", "2099-12-15", "Tee Times", None),
          (SAT, "s18.91 SATURDAY", "2099-12-19", "Tee Times", None),
          (FLIP, "s9.92 TUESDAY FLIP", "2099-12-15", "Tee Times", "earliest"),
          (SG, "s9.93 SHOTGUN", "2099-12-15", "Shotgun", None))
with db._connect(DB) as conn:
    n = 0
    for eid, name, d, st, keep in EVENTS:
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, start_time, "
                     "tee_time_count, tee_time_interval, course, tee_keep) VALUES (?, ?, ?, 'San Antonio', 'active', "
                     "'9-hole', ?, '15:40', 5, 10, 'Test Links', ?)", (eid, name, d, st, keep))
        for i in range(12):
            n += 1
            cid = 892000 + n
            conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
                         "VALUES (?, ?, 'Keep', 'active_member')", (cid, f"K{n}"))
            conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, transaction_status, "
                         "order_date, order_id, email_uid, merchant) VALUES (?, ?, ?, ?, '9', 'active', '2099-12-01', "
                         "?, ?, 'GoDaddy')", (f"K{n} Keep", cid, name, eid, f"RK{n}", f"manual-k{n}"))
    conn.commit()

def ev(eid):
    c = db.get_connection(DB)
    try:
        return dict(c.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone())
    finally:
        c.close()

def gen_labels(eid):
    res = db.generate_event_pairings(eid, db_path=DB, save_log=False)
    groups = res.get("9") or []
    db.save_event_pairings(eid, {"9": groups}, db_path=DB)
    return [g["slot_label"] for g in sorted(groups, key=lambda g: g["group_num"])]

print("1. The rule by weekday")
check("a weeknight keeps the latest", db.tee_keep_mode(ev(TUE)) == "latest")
check("a weekend keeps the earliest", db.tee_keep_mode(ev(SAT)) == "earliest")
check("the event's own tee_keep wins", db.tee_keep_mode(ev(FLIP)) == "earliest")
slots = ["3:40 PM", "3:50 PM", "4:00 PM", "4:10 PM", "4:20 PM"]
check("kept_tee_slots: weeknight, 3 of 5 = the last three", db.kept_tee_slots(ev(TUE), slots, 3) == slots[2:])
check("kept_tee_slots: weekend, 3 of 5 = the first three", db.kept_tee_slots(ev(SAT), slots, 3) == slots[:3])
check("kept_tee_slots: shotgun holes are left in order", db.kept_tee_slots(ev(TUE), ["1A", "1B", "2A"], 2) == ["1A", "1B"])

print("2. The generator uses the kept times")
t = gen_labels(TUE)
check("Tuesday: groups at 4:00, 4:10, 4:20 PM", t == ["4:00 PM", "4:10 PM", "4:20 PM"], t)
s = gen_labels(SAT)
check("Saturday: groups at 3:40, 3:50, 4:00 PM", s == ["3:40 PM", "3:50 PM", "4:00 PM"], s)
f = gen_labels(FLIP)
check("Tuesday set to keep earliest: 3:40, 3:50, 4:00 PM", f == ["3:40 PM", "3:50 PM", "4:00 PM"], f)
g = gen_labels(SG)
check("a shotgun is untouched (holes, not times)", all(not db._is_tee_time_slot(x) for x in g), g)

print("3. The released times")
check("Tuesday releases 3:40 and 3:50 PM", db.released_tee_times(ev(TUE), DB) == ["3:40 PM", "3:50 PM"], db.released_tee_times(ev(TUE), DB))
check("Saturday releases 4:10 and 4:20 PM", db.released_tee_times(ev(SAT), DB) == ["4:10 PM", "4:20 PM"])
check("a shotgun releases nothing", db.released_tee_times(ev(SG), DB) == [])
blk = tt.released_block(ev(TUE), DB)
check("the course email line names each released time",
      "We're releasing these tee times: 3:40 PM, 3:50 PM." in blk, blk)
check("no line when nothing is released", tt.released_block(ev(SG), DB) == "")

print("4. Edit Event")
check("update_event stores keep earliest", db.update_event(TUE, {"tee_keep": "earliest"}, db_path=DB) and ev(TUE)["tee_keep"] == "earliest")
check("Default clears it", db.update_event(TUE, {"tee_keep": ""}, db_path=DB) and ev(TUE)["tee_keep"] is None)
check("a bad value is ignored", not db.update_event(TUE, {"tee_keep": "middle"}, db_path=DB) and ev(TUE)["tee_keep"] is None)

print("5. The stamp")
_c = open("email_parser/teetimes_email.py", encoding="utf-8").read()
check("the released line is not part of any version's fixed (hashed) lines",
      "RELEASED_LINE" not in _c.split("_FIXED = {")[1].split("}")[0])

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
