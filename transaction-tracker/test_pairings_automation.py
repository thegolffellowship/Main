"""Day-before auto-pairings + a profile fact on an RSVP-only row.

Kerry 2026-09-21: "Create a timer to Generate Pairings automatically at
5:00p on Mondays for Tuesday events. Only if they aren't run already."
and "Jeff Young is a 3 for pace of play (POP) on his customer profile.
Why isn't he showing that on his pairing even though he's only an RSVP?"

Run: python3 test_pairings_automation.py
"""
import os, sys, tempfile, logging
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond: F.append(label)

# A Monday "today": tomorrow is a Tuesday event with a roster of eight.
monday = date(2026, 9, 21); tuesday = monday + timedelta(days=1); wednesday = monday + timedelta(days=2)
with db._connect(DB) as conn:
    conn.executemany("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_time, start_type, course) VALUES (?,?,?,?,?,?,?,?,?)", [
        (9201, "s9.24 Brackenridge", tuesday.isoformat(), "San Antonio", "active", "9 Holes", "5:00 PM", "Tee Times", "Brackenridge Park"),
        (9202, "a9.24 Teravista", tuesday.isoformat(), "Austin", "active", "9 Holes", "5:00 PM", "Tee Times", "Teravista"),
        (9203, "s18.12 Wednesday", wednesday.isoformat(), "San Antonio", "active", "18 Holes", "8:00 AM", "Tee Times", "Somewhere")])
    n = 0
    for evid, evname in ((9201, "s9.24 Brackenridge"), (9202, "a9.24 Teravista"), (9203, "s18.12 Wednesday")):
        for i in range(8):
            n += 1
            conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status, pace_rating) VALUES (?,?,?,'active_member',?)",
                         (800000 + n, f"P{n}", f"Test{evid}", 3 if i == 0 else None))
            conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, tee_choice, transaction_status, order_date, order_id, email_uid, merchant, user_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                         (f"P{n} Test{evid}", 800000 + n, evname, evid, "9" if evid != 9203 else "18", "<50", "active", "2026-09-10", f"R{n}", f"manual-{n}", "GoDaddy", "MEMBER"))
    conn.commit()
# Teravista was already paired by hand — must be left alone.
db.save_event_pairings(9202, {"9": [{"group_num": 1, "slot_label": "5:00 PM", "players": [
    {"name": "P9 Test9202", "cart_pos": 1, "customer_id": 800009, "tee_choice": "<50", "handicap_index": None},
    {"name": "P10 Test9202", "cart_pos": 2, "customer_id": 800010, "tee_choice": "<50", "handicap_index": None}]}]})

print("1. The 5 PM day-before routine")
res = db.auto_generate_pairings(DB, today=monday)
by = {r["event_id"]: r for r in res}
check("both chapters' Tuesday events are considered, the Wednesday one is not (rule 3d)", set(by) == {9201, 9202}, res)
check("an unpaired Tuesday event is generated and SAVED", by[9201].get("generated") is True and by[9201].get("seated") == 8, by.get(9201))
check("…as saved pairings the page will load", sum(len(g["players"]) for g in db.get_event_pairings(9201, DB).get("9", [])) == 8)
check("an event Kerry already paired is left exactly as it was ('Only if they aren't run already')",
      by[9202].get("generated") is False and by[9202].get("why") == "already paired"
      and [p["name"] for p in db.get_event_pairings(9202, DB)["9"][0]["players"]] == ["P9 Test9202", "P10 Test9202"], by.get(9202))
res2 = db.auto_generate_pairings(DB, today=monday)
check("a second run changes nothing", all(r.get("generated") is False for r in res2), res2)
check("a Tuesday 'today' (Wednesday event) is outside the dial — nothing runs", db.auto_generate_pairings(DB, today=tuesday) == [])
db.set_app_setting(db.PAIRINGS_AUTO_WEEKDAYS_KEY, "tue, wed", db_path=DB)
res3 = db.auto_generate_pairings(DB, today=tuesday)
check("the weekdays are a DIAL — adding wed covers the Wednesday event without code", [r["event_id"] for r in res3] == [9203] and res3[0].get("generated") is True, res3)
db.set_app_setting(db.PAIRINGS_AUTO_WEEKDAYS_KEY, db.PAIRINGS_AUTO_WEEKDAYS_DEFAULT, db_path=DB)
check("the default dial is tue:1, sat:2 (Kerry: 'Add sat… but make it for Thursday nights at 5:00p')",
      db.pairings_auto_weekdays(DB) == {"tue": 1, "sat": 2}, db.pairings_auto_weekdays(DB))
saturday = date(2026, 9, 26); thursday = saturday - timedelta(days=2); friday = saturday - timedelta(days=1)
with db._connect(DB) as conn:
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, start_time, start_type, course) VALUES (9204, 's18.12 Saturday', ?, 'San Antonio', 'active', '18 Holes', '8:00 AM', 'Tee Times', 'Somewhere')", (saturday.isoformat(),))
    for i in range(4):
        n += 1
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status) VALUES (?,?,?,'active_member')", (800000 + n, f"P{n}", "Test9204"))
        conn.execute("INSERT INTO items (customer, customer_id, item_name, event_id, holes, tee_choice, transaction_status, order_date, order_id, email_uid, merchant, user_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                     (f"P{n} Test9204", 800000 + n, "s18.12 Saturday", 9204, "18", "<50", "active", "2026-09-10", f"R{n}", f"manual-{n}", "GoDaddy", "MEMBER"))
    conn.commit()
check("Friday's run does NOT touch Saturday (its lead is two days)", db.auto_generate_pairings(DB, today=friday) == [])
res4 = db.auto_generate_pairings(DB, today=thursday)
check("Thursday's run pairs Saturday", [r["event_id"] for r in res4] == [9204] and res4[0].get("generated") is True, res4)
check("the routine is registered in the scheduler at 5:00 PM Central",
      'id="pairings_auto_generate"' in open("app.py").read() and "hour=17," in open("app.py").read().split('id="pairings_auto_generate"')[0][-400:])

print("2. A profile fact on an RSVP-only row")
with db._connect(DB) as conn:
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name, current_player_status, pace_rating) VALUES (800999, 'Jeff', 'Young', 'active_member', 3)")
    conn.execute("INSERT INTO rsvps (email_uid, player_name, player_email, matched_event, response, received_at, customer_id) VALUES ('rsvp-jy-1', 'Jeff Young', 'jeff@example.test', 's9.24 Brackenridge', 'PLAYING', '2026-09-20 10:00:00', 800999)")
    conn.commit()
    rows = {r["name"]: r for r in db._event_roster_rows(conn, 9201)}
jy = rows.get("Jeff Young")
check("an RSVP-only player is on the roster", jy is not None and jy.get("rsvp_only"), list(rows)[:3])
check("…and carries the pace rating from his customer profile (was hard-coded None)", jy is not None and jy.get("pace_rating") == 3, jy)
check("an order-row player carries it too (same fact, same path)", rows["P1 Test9201"].get("pace_rating") == 3)
try: os.unlink(DB)
except OSError: pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
