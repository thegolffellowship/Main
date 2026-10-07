"""A player's strokes fall on HIS tee's stroke index (v2.525.5, Kerry
2026-10-06 "go now", Tracker Build #1277).

The phone card put every player's PH and Team Net pops on the round's one
stroke-index column (the <50 tee's); the printed scorecard already used
each player's own tee. Olympia Hills 10/6: Michele McCormick's Red (L)
order differs from White's on 8 of 9 holes. Checks: a Forward player is
ranked over the Forward tee's index, a <50 player over the round's; Team
Net pops follow the same rule; a band whose tee has no complete index
keeps the round's column.

Run: python3 test_strokes_own_tee.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
from email_parser import score_entry as se                        # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


COURSE, EV = 930001, 9501
WHITE_SI = {1: 11, 2: 7, 3: 15, 4: 17, 5: 9, 6: 3, 7: 5, 8: 1, 9: 13}     # Olympia Hills White
RED_SI = {1: 13, 2: 5, 3: 7, 4: 15, 5: 9, 6: 1, 7: 11, 8: 3, 9: 17}       # Olympia Hills Red (L)
PAR = {1: 4, 2: 5, 3: 4, 4: 4, 5: 3, 6: 5, 7: 3, 8: 4, 9: 4}
with db._connect(DB) as conn:
    conn.execute("INSERT INTO courses (course_id, name, status) VALUES (?, 'Own Tee GC', 'active')", (COURSE,))
    for tid, nm, g, band, si, full in ((930101, "White", "M", "<50", WHITE_SI, True),
                                       (930102, "Red (L)", "F", "Forward", RED_SI, True),
                                       (930103, "Gold", "M", "65+", WHITE_SI, False)):
        conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, gender, holes, rating, slope, "
                     "tgf_bands, nine, source) VALUES (?,?,?,?,9,34.0,120,?,'front','import')",
                     (tid, COURSE, nm, g, band))
        for h in range(1, 10):
            conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) "
                         "VALUES (?,?,?,300,?)", (tid, h, PAR[h], si[h] if (full or h != 9) else None))
    conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, course, course_id, "
                 "nine_side) VALUES (?, 's9.99 Own Tee', '2099-10-06', 'San Antonio', 'active', '9 Holes', "
                 "'Own Tee GC', ?, 'Front')", (EV, COURSE))
    for cid, fn, ln in ((1, "Nic", "White"), (2, "Michele", "Red"), (3, "Don", "Gold")):
        conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
    conn.commit()

course_holes = [{"hole": h, "par": PAR[h], "stroke_index": WHITE_SI[h], "yardage": 300} for h in range(1, 10)]
rid = se.create_round(EV, 9, course_holes=course_holes, course_id=COURSE, db_path=DB)["round_id"]
g = se.upsert_group(rid, 1, start_hole=1, players=[
    {"customer_id": 1, "display_name": "Nic White", "tee": "<50", "playing_handicap": 3},
    {"customer_id": 2, "display_name": "Michele Red", "tee": "Forward", "playing_handicap": 3},
    {"customer_id": 3, "display_name": "Don Gold", "tee": "65+", "playing_handicap": 3}], db_path=DB)["group_id"]
se.set_game_handicaps(rid, {1: 2, 2: 2, 3: 2}, unit="group", basis="75%", db_path=DB)

card = se.get_group_card(g, db_path=DB)
st, ts = card["strokes"], card["team_strokes"]
check("<50 player: PH 3 on White's three hardest (8, 6, 7)", st.get("1") == {"8": 1, "6": 1, "7": 1}, st.get("1"))
check("Forward player: PH 3 on Red (L)'s three hardest (6, 8, 2)", st.get("2") == {"6": 1, "8": 1, "2": 1}, st.get("2"))
check("a band whose tee has no complete index keeps the round's column",
      st.get("3") == {"8": 1, "6": 1, "7": 1}, st.get("3"))
# Team Net: 2 pops each; par 3s (holes 5 and 7) take none, removed not moved.
check("team pops follow the player's own tee: Forward 6 and 8", ts.get("2") == {"6": 1, "8": 1}, ts.get("2"))
check("team pops for the <50 player: 8 and 6", ts.get("1") == {"8": 1, "6": 1}, ts.get("1"))

with db._connect(DB) as conn:
    sib = se._si_by_band(conn, EV, list(range(1, 10)))
check("per-band index carries <50 and Forward, not the incomplete 65+", set(sib) == {"<50", "Forward"}, sib)
check("the Forward map is Red (L)'s own", sib.get("Forward") == RED_SI, sib.get("Forward"))
with db._connect(DB) as conn:
    check("an unknown event yields nothing and never raises", se._si_by_band(conn, 424242, [1, 2]) == {})

print()
print("FAILURES:", F or "none")
sys.exit(1 if F else 0)
