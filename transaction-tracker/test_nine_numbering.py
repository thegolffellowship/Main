"""A named nine numbers its holes 1–9, and a date's handicap rounds can be
re-tagged to the nine actually played (Kerry 2026-09-21, the s9.14 Hill
Country night: "We played the Oaks 9 that night. And even though GG may
have shown 10-18, each 9 is just 1-9, same as Comanche Trace's 27 holes").

Run: python3 test_nine_numbering.py
"""
import os, sys, tempfile, logging
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

with db._connect(DB) as conn:
    conn.execute("INSERT INTO courses (course_id, name) VALUES (22360, 'Oaks')")
    conn.execute("INSERT INTO courses (course_id, name) VALUES (22366, 'Silverhorn Golf Club of Texas')")
    conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, gender, holes, rating, slope) VALUES (75, 22360, 'Blue', 'M', 9, 35.7, 131)")
    conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, gender, holes, rating, slope) VALUES (338, 22366, 'Gold', 'M', 18, 71.0, 125)")
    for h, par in zip(range(10, 19), (4, 4, 4, 4, 3, 5, 4, 3, 5)):
        conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) VALUES (75, ?, ?, 300, ?)", (h, par, h - 9))
        conn.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) VALUES (338, ?, ?, 300, ?)", (h, par, h - 9))
    conn.execute("INSERT INTO scoring_rounds (id, customer_id, player_name, round_date, course_id, tee_id, holes_played, gross) VALUES (50, 18, 'NIESTER, Kerry', '2026-06-16', 22360, 75, 9, 43)")
    conn.execute("INSERT INTO scoring_rounds (id, customer_id, player_name, round_date, course_id, tee_id, holes_played, gross) VALUES (51, 19, 'WADE, Mary', '2026-06-16', 22360, 75, 9, 45)")
    conn.execute("INSERT INTO scoring_rounds (id, customer_id, player_name, round_date, course_id, tee_id, holes_played, gross) VALUES (60, 18, 'NIESTER, Kerry', '2026-09-08', 22366, 338, 9, 39)")
    strokes = (5, 4, 5, 5, 3, 5, 5, 6, 5)
    for rid in (50, 51, 60):
        for h in range(1, 10):
            conn.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes) VALUES (?, ?, NULL)", (rid, h))
        for h, st in zip(range(10, 19), strokes):
            conn.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes) VALUES (?, ?, ?)", (rid, h, st))
    conn.executemany("INSERT INTO handicap_rounds (player_name, round_date, course_name, tee_name, adjusted_score, rating, slope, differential) VALUES (?,?,?,?,?,?,?,?)", [
        ("NIESTER, Kerry", "2026-06-16", "Hill Country | Lakes", "1 - Blue", 42, 35.7, 125, 5.7),
        ("WADE, Mary", "2026-06-16", "Hill Country | Lakes", "1 - Red", 48, 34.2, 120, 13.0),
        ("NIESTER, Kerry", "2026-06-09", "Silverhorn Golf Club Of Texas - Front", "1 - Gold", 35, 36.1, 125, -1.0)])
    conn.commit()

print("1. Renumbering a named nine")
dry = db.renumber_nine_hole_course(22360, apply=False, db_path=DB)
check("dry run names the tee and both rounds that would move", [t["tee_id"] for t in dry["tees"]] == [75]
      and sorted(r["scoring_round_id"] for r in dry["rounds"]) == [50, 51] and not dry["applied"], dry)
with db._connect(DB) as conn:
    check("…and moves nothing", conn.execute("SELECT COUNT(*) FROM scoring_holes WHERE scoring_round_id = 50 AND hole_number = 1 AND strokes IS NOT NULL").fetchone()[0] == 0)
res = db.renumber_nine_hole_course(22360, apply=True, db_path=DB)
with db._connect(DB) as conn:
    holes = [r[0] for r in conn.execute("SELECT strokes FROM scoring_holes WHERE scoring_round_id = 50 ORDER BY hole_number").fetchall()]
    nums = [r[0] for r in conn.execute("SELECT hole_number FROM scoring_holes WHERE scoring_round_id = 50 ORDER BY hole_number").fetchall()]
    tee = [r[0] for r in conn.execute("SELECT hole_number FROM course_tee_holes WHERE tee_id = 75 ORDER BY hole_number").fetchall()]
    sil = [r[0] for r in conn.execute("SELECT hole_number FROM scoring_holes WHERE scoring_round_id = 60 AND strokes IS NOT NULL ORDER BY hole_number").fetchall()]
check("the round's strokes now sit on holes 1–9, nothing left at 10–18", nums == list(range(1, 10)) and holes == list(strokes), (nums, holes))
check("the tee's hole rows moved with them", tee == list(range(1, 10)), tee)
check("a real back nine on an 18-hole course is untouched", sil == list(range(10, 19)), sil)
check("a second apply is a no-op", db.renumber_nine_hole_course(22360, apply=True, db_path=DB)["rounds"] == [])
check("a course record with an 18-hole tee is refused", "error" in db.renumber_nine_hole_course(22366, apply=True, db_path=DB))

print("2. Re-tagging a date's handicap rounds")
dry = db.retag_handicap_rounds("2026-06-16", "Hill Country | Lakes", "Hill Country | Oaks", 131, apply=False, db_path=DB)
check("dry run plans every player on that date (rule 3d), differential recomputed from the row's own adjusted score",
      dry["rows"] == 2 and dry["plan"][0]["differential_after"] == 5.4 and dry["plan"][0]["differential_before"] == 5.7, dry)
with db._connect(DB) as conn:
    check("…and changes nothing", conn.execute("SELECT course_name FROM handicap_rounds WHERE player_name = 'NIESTER, Kerry' AND round_date = '2026-06-16'").fetchone()[0] == "Hill Country | Lakes")
db.retag_handicap_rounds("2026-06-16", "Hill Country | Lakes", "Hill Country | Oaks", 131, apply=True, db_path=DB)
with db._connect(DB) as conn:
    k = dict(conn.execute("SELECT * FROM handicap_rounds WHERE player_name = 'NIESTER, Kerry' AND round_date = '2026-06-16'").fetchone())
    other = dict(conn.execute("SELECT * FROM handicap_rounds WHERE player_name = 'NIESTER, Kerry' AND round_date = '2026-06-09'").fetchone())
check("applied: course, slope and differential follow; rating and tee stay", k["course_name"] == "Hill Country | Oaks" and k["slope"] == 131
      and k["differential"] == 5.4 and k["rating"] == 35.7 and k["tee_name"] == "1 - Blue", k)
check("another date is untouched", other["course_name"].startswith("Silverhorn") and other["slope"] == 125)
miss = db.retag_handicap_rounds("2026-06-09", "Hill Country | Lakes", "Hill Country | Oaks", 131, apply=False, db_path=DB)
check("a miss answers with the course names actually stored on that date", miss["rows"] == 0 and miss["courses_on_date"] == ["Silverhorn Golf Club Of Texas - Front"], miss)
# Per-tee from the course record: the night had Blue, White and Red (women) players.
with db._connect(DB) as conn:
    conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, gender, holes, rating, slope) VALUES (77, 22360, 'White', 'M', 9, 33.9, 128)")
    conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, gender, holes, rating, slope) VALUES (93, 22360, 'Red', 'F', 9, 34.2, 120)")
    conn.executemany("INSERT INTO handicap_rounds (player_name, round_date, course_name, tee_name, adjusted_score, rating, slope, differential) VALUES (?,?,?,?,?,?,?,?)", [
        ("STICH, Dan", "2026-06-17", "Hyatt Hill Country | Lakes/Oaks", "2 - White", 45, 34.1, 122, 10.1),
        ("WADE, Mary", "2026-06-17", "Hyatt Hill Country | Lakes/Oaks", "3 - Red (L)", 46, 34.3, 116, 11.4),
        ("NIESTER, Kerry", "2026-06-17", "Hyatt Hill Country | Lakes/Oaks", "1 - Blue", 42, 35.7, 125, 5.7),
        ("ODD, Player", "2026-06-17", "Hyatt Hill Country | Lakes/Oaks", "4 - Gold", 44, 34.0, 120, 9.4)])
    conn.commit()
per = db.retag_handicap_rounds("2026-06-17", "Hyatt Hill Country | Lakes/Oaks", "Hyatt Hill Country | Oaks", apply=False, db_path=DB, course_id=22360)
got = {p["player_name"]: (p["rating_after"], p["slope_after"], p["differential_after"]) for p in per["plan"]}
check("course= takes each row's tee rating/slope off the record: Blue 35.7/131, White 33.9/128, Red (women) 34.2/120",
      got.get("NIESTER, Kerry") == (35.7, 131, 5.4) and got.get("STICH, Dan") == (33.9, 128, 9.8) and got.get("WADE, Mary") == (34.2, 120, 11.1), got)
check("a tee the record does not carry is reported and left alone", [u["player_name"] for u in per["unmatched_tees"]] == ["ODD, Player"], per["unmatched_tees"])
check("matching ignores spacing and case", db.retag_handicap_rounds("2026-06-09", "silverhorn golf club of texas  -  front", "X", 125, apply=False, db_path=DB)["rows"] == 1)
try: os.unlink(DB)
except OSError: pass
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
