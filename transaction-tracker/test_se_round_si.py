"""A seeded round re-reads par + stroke index from the course record
(Kerry 2026-10-09: the Hideout's printed 07/26 card has a different stroke
index order than the card loaded 9/28; "Check this course scorecard against
our tracker card for hideout").

Pins: refresh_round_stroke_index dry-runs by default, applies only par/SI,
leaves scores alone, and a second run has nothing to change.

Run: python3 test_se_round_si.py
"""
import os, sys, tempfile, logging, contextlib, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(tempfile.mkdtemp(prefix="tgf-sesi-"), "t.db")
os.environ["DATABASE_PATH"] = p
logging.disable(logging.ERROR)
from email_parser import database as db                    # noqa: E402
from email_parser import score_entry as se                 # noqa: E402
from email_parser.course_card import load_course_card      # noqa: E402
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    db.init_db(p)
with db._connect(p) as c:
    db._ensure_scoring_tables(c)
    cid = c.execute("INSERT INTO courses (name) VALUES ('The Hideout') RETURNING course_id").fetchone()[0]
    c.execute("INSERT INTO events (id, item_name, event_date, course_id) VALUES (3329, 'LSC', '2026-10-10', ?)", (cid,))
    c.commit()
PAR = [5, 3, 4, 4, 3, 4, 5, 4, 5, 4, 4, 4, 3, 4, 3, 5, 4, 4]
OLD = [17, 15, 3, 1, 11, 7, 5, 13, 9, 16, 14, 6, 8, 2, 10, 18, 4, 12]
NEW = [5, 17, 3, 7, 15, 11, 1, 12, 4, 18, 14, 16, 6, 10, 8, 2, 13, 9]
m = lambda a: {str(i + 1): x for i, x in enumerate(a)}  # noqa: E731


def card(si):
    return {"holes": 18, "par": m(PAR), "stroke_index": m(si), "tees": [
        {"tee_name": "Blue", "gender": "M", "bands": ["<50"], "rating": 71.7, "slope": 129}]}


r = load_course_card(cid, card(OLD), apply=True, db_path=p)
check("old card loads", r.get("applied"), r)
rid = se.create_round(3329, 18, course_id=cid, db_path=p,
                      course_holes=[{"hole": i + 1, "par": PAR[i], "stroke_index": OLD[i]} for i in range(18)])["round_id"]
check("nothing to change while the card matches", se.refresh_round_stroke_index(rid, db_path=p)["changes"] == [])
load_course_card(cid, card(NEW), apply=True, db_path=p)
dry = se.refresh_round_stroke_index(rid, db_path=p)
check("dry run lists every hole whose SI moved, writes nothing",
      len(dry["changes"]) == sum(1 for a, b in zip(OLD, NEW) if a != b) and not dry["applied"], dry)
with db._connect(p) as c:
    si1 = c.execute("SELECT stroke_index FROM se_round_holes WHERE round_id = ? AND hole_number = 1", (rid,)).fetchone()[0]
check("dry run left the round alone", si1 == 17, si1)
ap = se.refresh_round_stroke_index(rid, apply=True, db_path=p)
with db._connect(p) as c:
    got = [r[0] for r in c.execute("SELECT stroke_index FROM se_round_holes WHERE round_id = ? ORDER BY hole_number", (rid,))]
    pars = [r[0] for r in c.execute("SELECT par FROM se_round_holes WHERE round_id = ? ORDER BY hole_number", (rid,))]
check("apply writes the new stroke indexes", ap["applied"] and got == NEW, got)
check("pars unchanged", pars == PAR, pars)
check("a second run has nothing to change", se.refresh_round_stroke_index(rid, apply=True, db_path=p)["changes"] == [])
src = open("mcp_server.py", encoding="utf-8").read()
check("bridge scoring-se-round-si is wired, dry run default", 'cmd == "scoring-se-round-si"' in src
      and "refresh_round_stroke_index(_r, apply=" in src)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
