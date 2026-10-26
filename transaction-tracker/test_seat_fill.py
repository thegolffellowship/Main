"""SEAT-FILL (Kerry 2026-10-26, CoS #2308/#2331/#2333; rule ruled 10/20):
from the 5:00 PM lock to the first tee a registered late add is seated -- tee
times: the latest threesome first; shotgun: the lowest hole first, B before A.

Run: python3 test_seat_fill.py
"""
import os, sys, io, contextlib, logging, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "test-secret")
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db
    from email_parser import seat_fill as sf
    db.init_db(DB)
from datetime import datetime

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

TT, SG = 9701, 9702      # Tuesday 2099-12-15: a tee-time nine and a shotgun nine
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                 "start_time, course) VALUES (?, 's9.97 TEE TIMES', '2099-12-15', 'San Antonio', 'active', "
                 "'9-hole', 'Tee Times', '16:00', 'Test Links')", (TT,))
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                 "start_time, course) VALUES (?, 's9.96 SHOTGUN', '2099-12-15', 'San Antonio', 'active', "
                 "'9-hole', 'Shotgun', '16:30', 'Test Links')", (SG,))
    n = 0
    for eid, name, count in ((TT, "s9.97 TEE TIMES", 13), (SG, "s9.96 SHOTGUN", 12)):
        for i in range(count):
            n += 1
            cid = 890000 + n
            conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
                         "VALUES (?, ?, 'Test', 'active_member')", (cid, f"P{n}"))
            conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, transaction_status, "
                         "order_date, order_id, email_uid, merchant) VALUES (?, ?, ?, ?, '9', 'active', "
                         "'2099-12-01', ?, ?, 'GoDaddy')", (f"P{n} Test", cid, name, eid, f"R{n}", f"manual-{n}"))
    conn.commit()

def seat(name, cid, pos):
    return {"name": name, "customer_id": cid, "cart_pos": pos}

# Tee times: 4, 3, 3 seated (P1..P10); P11, P12, P13 register late.
tt_groups = [{"group_num": 1, "slot_label": "4:00 PM", "players": [seat(f"P{i} Test", 890000 + i, j + 1) for j, i in enumerate((1, 2, 3, 4))]},
             {"group_num": 2, "slot_label": "4:10 PM", "players": [seat(f"P{i} Test", 890000 + i, j + 1) for j, i in enumerate((5, 6, 7))]},
             {"group_num": 3, "slot_label": "4:20 PM", "players": [seat(f"P{i} Test", 890000 + i, j + 1) for j, i in enumerate((8, 9, 10))]}]
db.save_event_pairings(TT, {"9": tt_groups}, db_path=DB)
# Shotgun: threesomes on 3A, 4A, 4B (P14..P22); P23..P25 register late.
sg_groups = [{"group_num": 1, "slot_label": "3A", "players": [seat(f"P{i} Test", 890000 + i, j + 1) for j, i in enumerate((14, 15, 16))]},
             {"group_num": 2, "slot_label": "4A", "players": [seat(f"P{i} Test", 890000 + i, j + 1) for j, i in enumerate((17, 18, 19))]},
             {"group_num": 3, "slot_label": "4B", "players": [seat(f"P{i} Test", 890000 + i, j + 1) for j, i in enumerate((20, 21, 22))]}]
db.save_event_pairings(SG, {"9": sg_groups}, db_path=DB)

print("1. The order (Kerry 10/20)")
check("tee times: the latest threesome first", [g["slot_label"] for g in sf.fill_order(tt_groups)] == ["4:20 PM", "4:10 PM", "4:00 PM"])
check("shotgun: lowest hole first, B before A (3A, 4B, 4A)", [g["slot_label"] for g in sf.fill_order(sg_groups)] == ["3A", "4B", "4A"])

print("2. The plan (dry run)")
p = sf.run(TT, db_path=DB)
check("dry run writes nothing", p.get("dry_run") and len(db.get_event_pairings(TT, db_path=DB)["9"][2]["players"]) == 3)
check("P11 to 4:20, P12 to 4:10, P13 has no seat",
      [(s["name"], s["slot"]) for s in p["seat"]] == [("P11 Test", "4:20 PM"), ("P12 Test", "4:10 PM")]
      and [u["name"] for u in p["unseated"]] == ["P13 Test"], p)
s = sf.run(SG, db_path=DB)
check("shotgun: the three late adds go 3A, 4B, 4A", [x["slot"] for x in s["seat"]] == ["3A", "4B", "4A"], s)

print("3. The job: lock to first tee")
check("Monday 4:59 PM (before the lock): nothing", sf.check(now=datetime(2099, 12, 14, 16, 59), db_path=DB)["events"] == {})
r = sf.check(now=datetime(2099, 12, 14, 17, 2), db_path=DB)
sheet = db.get_event_pairings(TT, db_path=DB)["9"]
names = {g["slot_label"]: sorted(p["name"] for p in g["players"]) for g in sheet}
check("Monday 5:02 PM: P11 seated at 4:20, P12 at 4:10", "P11 Test" in names["4:20 PM"] and "P12 Test" in names["4:10 PM"], names)
check("every late add has a customer_id on the seat", all(p.get("customer_id") for g in sheet for p in g["players"]))
with db._connect(DB) as conn:
    coo = conn.execute("SELECT summary FROM action_items WHERE subject LIKE 'NO OPEN SEAT%'").fetchall()
    logged = conn.execute("SELECT COUNT(*) FROM agent_action_log WHERE action_type = 'seat_fill'").fetchone()[0]
check("no open seat: one COO item naming P13", len(coo) == 1 and "P13 Test" in coo[0][0], coo)
check("each seat is logged", logged == 5, logged)
sf.check(now=datetime(2099, 12, 14, 17, 17), db_path=DB)
with db._connect(DB) as conn:
    coo2 = conn.execute("SELECT COUNT(*) FROM action_items WHERE subject LIKE 'NO OPEN SEAT%'").fetchone()[0]
check("the next run does not raise P13 again", coo2 == 1, coo2)

with db._connect(DB) as conn:   # an unpaid RSVP is never seated
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (899999, 'Rsvp', 'Only')")
    conn.execute("INSERT INTO rsvps (email_uid, player_name, player_email, response, matched_event, event_date, "
                 "customer_id, received_at) VALUES (?, 'Rsvp Only', 'r@example.test', 'PLAYING', 's9.96 SHOTGUN', "
                 "'2099-12-15', 899999, '2099-12-14 17:30:00')", (f"tracker:{SG}:899999",))
    conn.commit()
check("an unpaid RSVP is never seated", all(u["name"] != "Rsvp Only" for u in sf.run(SG, db_path=DB)["unseated"])
      and all(x["name"] != "Rsvp Only" for x in sf.run(SG, db_path=DB)["seat"]))
check("after the first tee: nothing", sf.check(now=datetime(2099, 12, 15, 16, 35), db_path=DB)["events"] == {})

print("3b. The late add takes the seat's blind; seated players keep tee and index")
BL = 9703
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_type, "
                 "start_time, course) VALUES (?, 's9.95 BLIND', '2099-12-15', 'San Antonio', 'active', "
                 "'9-hole', 'Tee Times', '16:00', 'Test Links')", (BL,))
    for i, cid in enumerate((891001, 891002, 891003, 891004)):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) "
                     "VALUES (?, ?, 'Blind', 'active_member')", (cid, f"B{i}"))
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, transaction_status, "
                     "order_date, order_id, email_uid, merchant) VALUES (?, ?, 's9.95 BLIND', ?, '9', 'active', "
                     "'2099-12-01', ?, ?, 'GoDaddy')", (f"B{i} Blind", cid, BL, f"RB{i}", f"manual-b{i}"))
    conn.commit()
db.save_event_pairings(BL, {"9": [{"group_num": 1, "slot_label": "4:00 PM", "players": [
    {"name": f"B{i} Blind", "customer_id": 891001 + i, "cart_pos": i + 1, "tee_choice": "50-64",
     "handicap_index": 12.3} for i in range(3)]}]}, db_path=DB)
with db._connect(DB) as conn:
    db._ensure_pairing_tables(conn)
    conn.execute("INSERT INTO blind_draws (event_id, holes, group_num, cart_pos, customer_id, player_name, source, "
                 "event_date, slot_key) VALUES (?, '9', 1, 4, 890005, 'P5 Test', 'app', '2099-12-15', ?)",
                 (BL, db._blind_slot_key("9", 1, 4)))
    conn.commit()
check("before: seat 4 holds a blind", any(b["cart_pos"] == 4 for b in db.get_event_blinds(BL, db_path=DB).get("9", {}).get(1, [])))
sf.run(BL, apply=True, db_path=DB)
g = db.get_event_pairings(BL, db_path=DB)["9"][0]
check("the late add sits in seat 4", any(p["name"] == "B3 Blind" and p["cart_pos"] == 4 for p in g["players"]), g["players"])
check("and the blind on that seat is gone", not any(b["cart_pos"] == 4 for b in db.get_event_blinds(BL, db_path=DB).get("9", {}).get(1, [])),
      db.get_event_blinds(BL, db_path=DB))
with db._connect(DB) as conn:
    t = conn.execute("SELECT tee_choice, handicap_index FROM event_pairings WHERE event_id = ? AND cart_pos = 1", (BL,)).fetchone()
check("a seated player keeps the tee and index saved on his seat", t and t[0] == "50-64" and t[1] == 12.3, t and tuple(t))

print("4. The dial")
db.set_app_setting(sf.DIAL, "off", db_path=DB)
check("seat_fill_auto=off stops it", sf.check(now=datetime(2099, 12, 14, 18, 0), db_path=DB)["status"] == "off")
db.set_app_setting(sf.DIAL, "", db_path=DB)

print("5. Wiring")
_a = open("app.py", encoding="utf-8").read()
check("seat-fill runs first inside the after-lock job",
      _a.index("seat_fill import check as _seat_fill") < _a.index("res = check(_print_pack_render, app.static_folder)"))

try:
    os.remove(DB)
except OSError:
    pass
print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
