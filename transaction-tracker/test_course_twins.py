"""One course, one registry row (Kerry 2026-09-22, Brackenridge: the
event sat on a CRDB-seeded twin with no hole card and the CTP markers
went blind). `_find_course_loose` resolves a new spelling to the row
that already exists — exact name, alias, normalized key or pinned short
name — and aliases it, so nothing seeds a twin again.

Run: python3 test_course_twins.py
"""
import os, sqlite3, sys, tempfile, contextlib, io, logging
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
logging.getLogger("email_parser.database").setLevel(logging.ERROR)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-twin-"), "t.db")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(tmp)
c = sqlite3.connect(tmp); c.row_factory = sqlite3.Row
c.execute("INSERT INTO courses (course_id, name, short_name, status) VALUES (22371, 'Brackenridge Golf Course', 'Brackenridge', 'active')")
c.execute("INSERT INTO courses (course_id, name, short_name, status) VALUES (71981, 'Brackenridge Park Golf Course (OLD) - Archived on 07-07-2023', 'Brackenridge Park Golf Course (OLD) - Archived on 07-07-2023', 'active')")
c.execute("INSERT INTO courses (course_id, name, short_name, status) VALUES (22375, 'The Golf Club Star Ranch', 'Star Ranch', 'active')")
c.execute("INSERT INTO courses (course_id, name, short_name, status) VALUES (22368, 'ACGT | Riverside Golf Course', 'Riverside | SA', 'active')")
c.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, slope, rating) VALUES (1, 22371, 'Blue', 131, 35.6)")
c.execute("INSERT INTO scoring_rounds (customer_id, player_name, event_id, round_date, course_id, tee_id, holes_played, source) VALUES (1, 'X', NULL, '2026-04-14', 22371, 1, 9, 'gg')")
c.commit()

print("\n== a new spelling of an existing course ==")
cid = db._find_course_loose(c, "Brackenridge Park Golf Course")
check("'Brackenridge Park Golf Course' resolves to the Brackenridge row (pinned short name), not the archived twin",
      cid == 22371, str(cid))
check("…and the spelling is aliased so the next lookup is exact",
      c.execute("SELECT course_id FROM course_aliases WHERE alias_name = 'Brackenridge Park Golf Course'").fetchone()[0] == 22371)
check("'The Golf Club At Star Ranch' resolves to 'The Golf Club Star Ranch' (same normalized key)",
      db._find_course_loose(c, "The Golf Club At Star Ranch") == 22375)
check("an exact name (any case) still resolves first",
      db._find_course_loose(c, "brackenridge golf course") == 22371)
check("a genuinely new course is None — it may be created",
      db._find_course_loose(c, "Cordillera Ranch") is None)
check("Austin's Riverside is not San Antonio's (the pins keep them apart)",
      db._find_course_loose(c, "Riverside Golf Course (Austin)") is None)
check("a bare 'Riverside Golf Club' (could be DFW) is NOT folded into SA's row on the pin alone (Kerry 2026-09-22)",
      db._find_course_loose(c, "Riverside Golf Club") is None)
check("…nor a DFW spelling, which pins apart",
      db._course_short_pin("Riverside Golf Club - Fort Worth") == "Riverside | DFW"
      and db._find_course_loose(c, "Riverside Golf Club - Fort Worth") is None)
check("…while SA's own spelling still resolves",
      db._find_course_loose(c, "Riverside Golf Course San Antonio") == 22368)

c.commit()
print("\n== the tee import goes through the same door ==")
with db._connect(tmp) as conn:
    course_id, tee_id = db._upsert_course_tee(conn, {
        "course": "Brackenridge Park Golf Course", "tee_name": "1 - White Tee",
        "rating": 34.5, "slope": 124, "holes": 9, "gender": "M",
        "yardage": {1: 322}, "par": {1: 4}, "stroke_index": {1: 15}})
    conn.commit()
check("a scorecard import for the new spelling lands its tee on the existing row",
      course_id == 22371, str(course_id))
check("…and no twin row exists",
      c.execute("SELECT COUNT(*) FROM courses WHERE name LIKE 'Brackenridge%'").fetchone()[0] == 2)

print("\n" + ("ALL PASSED" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
