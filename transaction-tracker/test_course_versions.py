"""VERSIONED COURSE CORRECTION (Kerry 10/30, Kissing Tree: "Those past events
are what they are and nothing should change for them. Version control
updates to the course's tees"). course_card.archive_tee_versions, then
load_course_card.

Run: python3 test_course_versions.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-cv-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
from email_parser import database as db          # noqa: E402
from email_parser import course_card as cc       # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

db.init_db(DB)
PAR = {h: p for h, p in zip(range(1, 19), [4, 3, 5, 3, 5, 4, 4, 4, 4, 4, 4, 3, 4, 5, 3, 4, 5, 4])}
OLD_SI = dict(zip(range(1, 19), [11, 5, 13, 9, 15, 1, 3, 7, 17, 8, 4, 10, 2, 12, 16, 14, 6, 18]))
NEW_SI = dict(zip(range(1, 19), [16, 10, 8, 18, 2, 6, 4, 12, 14, 15, 3, 7, 1, 5, 17, 9, 11, 13]))
with db._connect(DB) as c:
    db._ensure_scoring_tables(c)
    cid = c.execute("INSERT INTO courses (name) VALUES ('Test Tree Golf Club') RETURNING course_id").fetchone()[0]
    tee = c.execute("INSERT INTO course_tees (course_id, tee_name, tgf_bands, gender, holes, nine, par, slope, rating, "
                    "yardage_total, source) VALUES (?, 'Back', '<50', 'M', 18, 'full', 72, 143, 71.4, 6484, 'import') "
                    "RETURNING tee_id", (cid,)).fetchone()[0]
    for h in range(1, 19):
        c.execute("INSERT INTO course_tee_holes (tee_id, hole_number, par, yardage, stroke_index) VALUES (?,?,?,?,?)",
                  (tee, h, PAR[h], 300 + h, OLD_SI[h]))
    c.execute("INSERT INTO tee_set_ratings (tee_id, rating_type, course_rating, slope, source) "
              "VALUES (?, 'total', 71.4, 143, 'usga_crdb')", (tee,))
    old_r = c.execute("INSERT INTO scoring_rounds (player_name, round_date, course_id, tee_id) "
                      "VALUES ('Past Player', '2026-06-27', ?, ?) RETURNING id", (cid, tee)).fetchone()[0]
    new_r = c.execute("INSERT INTO scoring_rounds (player_name, round_date, course_id, tee_id) "
                      "VALUES ('Saturday Player', '2026-10-31', ?, ?) RETURNING id", (cid, tee)).fetchone()[0]
    c.commit()

print("\n== archive ==")
dry = cc.archive_tee_versions(cid, "2026-10-30", "GG import (before club card 2026-10-30)", db_path=DB)
check("dry run writes nothing", not dry["applied"] and dry["tees"][0]["past_rounds"] == 1, dry)
res = cc.archive_tee_versions(cid, "2026-10-30", "GG import (before club card 2026-10-30)", apply=True, db_path=DB)
arc = res["tees"][0]["archive_tee_id"]
with db._connect(DB) as c:
    a = dict(c.execute("SELECT * FROM course_tees WHERE tee_id = ?", (arc,)).fetchone())
    past_tee = c.execute("SELECT tee_id FROM scoring_rounds WHERE id = ?", (old_r,)).fetchone()[0]
    sat_tee = c.execute("SELECT tee_id FROM scoring_rounds WHERE id = ?", (new_r,)).fetchone()[0]
    a_si = {r[0]: r[1] for r in c.execute("SELECT hole_number, stroke_index FROM course_tee_holes WHERE tee_id = ?", (arc,))}
    a_rt = c.execute("SELECT course_rating, slope FROM tee_set_ratings WHERE tee_id = ?", (arc,)).fetchone()
check("the archive has no bands and the version label", a["tgf_bands"] is None and a["version_label"].startswith("GG import"), a)
check("...valid to the day before", a["valid_to"] == "2026-10-29", a["valid_to"])
check("...the old stroke index and rating", a_si == OLD_SI and tuple(a_rt) == (71.4, 143), (a_si, tuple(a_rt)))
check("the past round now reads the archive", past_tee == arc, past_tee)
check("Saturday's round stays on the live tee", sat_tee == tee, sat_tee)
again = cc.archive_tee_versions(cid, "2026-10-30", "GG import (before club card 2026-10-30)", apply=True, db_path=DB)
check("running it again archives nothing new", again["tees"][0]["action"].startswith("skip"), again)

print("\n== the club's card onto the live tee ==")
card = {"holes": 18, "par": {str(h): p for h, p in PAR.items()},
        "tees": [{"tee_name": "Back", "gender": "M", "bands": ["<50"], "rating": 71.4, "slope": 143,
                  "stroke_index": {str(h): v for h, v in NEW_SI.items()},
                  "yardage": {str(h): 310 + h for h in range(1, 19)}}]}
r = cc.load_course_card(cid, card, apply=True, db_path=DB)
check("the card updates the live tee in place", r["applied"] and r["tees"][0]["tee_id"] == tee, r)
with db._connect(DB) as c:
    live = {x[0]: x[1] for x in c.execute("SELECT hole_number, stroke_index FROM course_tee_holes WHERE tee_id = ?", (tee,))}
    arch = {x[0]: x[1] for x in c.execute("SELECT hole_number, stroke_index FROM course_tee_holes WHERE tee_id = ?", (arc,))}
    bands = c.execute("SELECT tgf_bands FROM course_tees WHERE tee_id = ?", (tee,)).fetchone()[0]
check("live tee: the club's stroke index", live == NEW_SI, live)
check("archive untouched", arch == OLD_SI, arch)
check("live tee keeps its band", bands == "<50", bands)

print(f"\n{'ALL PASS' if not F else f'{len(F)} FAILED: {F}'}")
sys.exit(1 if F else 0)
