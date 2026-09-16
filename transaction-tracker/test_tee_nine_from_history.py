"""A tee row's nine is decided by the rounds already played off it.

Kerry 2026-09-16: "Avery Ranch doesn't even show PH or TEAM (Cart)
handicaps" and, after submitting the course's tees to Golf Genius, "Is
this fixed now?"

Avery Ranch's card carries two nine-hole rows per tee and NO 18-hole row,
so the yardage strategies in `label_course_tee_nines` cannot say which
row is the front and which the back, and a sheet that refuses to guess
printed nothing. But each imported round off a row was scored on a night
whose nine we recorded (`events.nine_side`) and posted as a handicap
round naming its nine (`handicap_rounds.nine`). Unanimous history labels
the row; conflicting history leaves it unresolved and says why.

Run: python3 test_tee_nine_from_history.py
"""
import os, sys, tempfile, logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.WARNING)
from email_parser import database as db                          # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

with db._connect(DB) as conn:
    conn.executescript("""
        CREATE TABLE course_tees (tee_id INTEGER PRIMARY KEY, course_id INTEGER,
            tee_name TEXT, rating REAL, slope INTEGER, yardage_total INTEGER);
        CREATE TABLE course_tee_holes (tee_id INTEGER, hole_number INTEGER,
            yardage INTEGER, par INTEGER, stroke_index INTEGER);
        CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT, nine_side TEXT);
        CREATE TABLE scoring_rounds (id INTEGER PRIMARY KEY, tee_id INTEGER,
            course_id INTEGER, event_id INTEGER);
        CREATE TABLE handicap_rounds (id INTEGER PRIMARY KEY, nine TEXT,
            scoring_round_id INTEGER);
    """)
    # Avery Ranch: Blue twice, White twice, Green twice — all nine-hole ratings.
    for tid, nm, rt, sl, y in ((174, "1 - Blue Tee", 35.0, 123, 2988),
                               (885, "1 - Blue Tee", 36.0, 139, 3240),
                               (177, "2 - White Tee", 34.0, 116, 2757),
                               (886, "2 - White Tee", 34.9, 133, 2967),
                               (173, "3 - Green Tee", 32.3, 109, 2372),
                               (892, "3 - Green Tee", 33.1, 126, 2552)):
        conn.execute("INSERT INTO course_tees VALUES (?, 22363, ?, ?, ?, ?)", (tid, nm, rt, sl, y))
    conn.execute("INSERT INTO events VALUES (3314, 'a9.23 Avery Ranch', 'Front')")
    conn.execute("INSERT INTO events VALUES (3200, 'a9.18 Avery Ranch', 'Back')")
    conn.execute("INSERT INTO events VALUES (3100, 'a9.12 Avery Ranch', NULL)")
    # a9.23 (Front) scored off 885 and 886; a9.18 (Back) off 174 and 177.
    for rid, tid, eid in ((1, 885, 3314), (2, 885, 3314), (3, 886, 3314),
                          (4, 174, 3200), (5, 177, 3200)):
        conn.execute("INSERT INTO scoring_rounds VALUES (?, ?, 22363, ?)", (rid, tid, eid))
    # Green 173 was played on a night with no side recorded, but its posted
    # handicap round names the nine.
    conn.execute("INSERT INTO scoring_rounds VALUES (6, 173, 22363, 3100)")
    conn.execute("INSERT INTO handicap_rounds VALUES (1, 'back', 6)")
    # Green 892: played as front on one night and back on another — conflict.
    conn.execute("INSERT INTO scoring_rounds VALUES (7, 892, 22363, 3314)")
    conn.execute("INSERT INTO scoring_rounds VALUES (8, 892, 22363, 3200)")
    conn.commit()
    res = db.label_course_tee_nines(conn, 22363)
    nine = {r["tee_id"]: r["nine"] for r in conn.execute(
        "SELECT tee_id, nine FROM course_tees").fetchall()}

print("Avery Ranch, no 18-hole card")
check("Blue 885 is the FRONT — a9.23 was scored off it on a Front night", nine[885] == "front", nine)
check("White 886 is the FRONT likewise", nine[886] == "front", nine)
check("Blue 174 / White 177 are the BACK — a9.18 was a Back night",
      nine[174] == "back" and nine[177] == "back", nine)
check("a posted handicap round's own nine labels a row when the event never said",
      nine[173] == "back", nine)
check("a row played as BOTH stays unresolved", nine[892] is None, nine)
why = {u["tee_id"]: u["why"] for u in res["unresolved"]}
check("…and says why", why.get(892) == "played as both front and back", why)
check("the report counts match", res["n_decided"] == 5 and res["n_unresolved"] == 1, res)
with db._connect(DB) as conn:
    again = db.label_course_tee_nines(conn, 22363)
check("idempotent", again["n_decided"] == 5 and again["n_unresolved"] == 1)

try:
    os.unlink(DB)
except OSError:
    pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
