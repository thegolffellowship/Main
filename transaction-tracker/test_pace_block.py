"""YOUR GROUP'S PACE in the players' results email (Kerry 10/28, Event Ops
#2466-H/#2467-H v2): one bar of three equal thirds, the arrow at the group's
time, the time as its only label, no text under the bar; 9 holes 2:15|2:30,
18 holes 4:30|5:00.

Run: python3 test_pace_block.py
"""
import os, sys, re, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="tgf-pace-"), "t.db")
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
from email_parser import results_email as re_   # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

def pos(html):
    return int(re.search(r'<td width="(\d+)%"', html).group(1))

b = re_.pace_bar(135, 9)
check("9 holes at 2:15 sits on the green|yellow line (one third)", pos(b) == 33 and ">2:15<" in b, pos(b))
check("2:30 sits on the yellow|red line", pos(re_.pace_bar(150, 9)) == 67)
check("2:00 or faster is pinned at the left end", pos(re_.pace_bar(110, 9)) == 0)
check("far behind is pinned at the right end", pos(re_.pace_bar(200, 9)) == 100)
check("18 holes: 4:30 and 5:00 are the lines", pos(re_.pace_bar(270, 18)) == 33 and pos(re_.pace_bar(300, 18)) == 67)
check("three equal-ish segments, green yellow red",
      all(c in b for c in ("#22C55E", "#FACC15", "#EF4444")) and b.split('#22C55E')[0].count('width="33%"') == 2)
check("no text under the bar: the bar is the last thing", b.rstrip().endswith("</tr></table>")
      and "ahead" not in b.lower() and "behind" not in b.lower())
check("the card says YOUR GROUP'S PACE", "YOUR GROUP" in re_.card("YOUR GROUP’S PACE", b))
check("no pace data, no block", re_._pace({"event": {"id": 999999}, "db_path": None}, 1) == "")

print("\n== the course's own standard (Kerry 10/29: Kissing Tree 4:00 / 4:30) ==")
from email_parser import database as db   # noqa: E402
DBP = os.environ["DATABASE_PATH"]
db.init_db(DBP)
check("no entry: the defaults", db.course_pace_targets(22362, 18, db_path=DBP) == (270, 300)
      and db.course_pace_targets(22362, 9, db_path=DBP) == (135, 150))
db.set_course_pace(22362, 18, "4:00", db_path=DBP)
check("set 4:00 on the 18: lines 4:00 and 4:30", db.course_pace_targets(22362, 18, db_path=DBP) == (240, 270))
check("the nine keeps its default", db.course_pace_targets(22362, 9, db_path=DBP) == (135, 150))
check("another course is untouched", db.course_pace_targets(1, 18, db_path=DBP) == (270, 300))
check("4:00 sits on green|yellow, 4:30 on yellow|red",
      pos(re_.pace_bar(240, 18, (240, 270))) == 33 and pos(re_.pace_bar(270, 18, (240, 270))) == 67)
db.set_course_pace(22362, 18, "", db_path=DBP)
check("clearing it goes back to the default", db.course_pace_targets(22362, 18, db_path=DBP) == (270, 300))
for bad in ("0:30", "9:00", "abc"):
    try:
        db.set_course_pace(22362, 18, bad, db_path=DBP); ok = False
    except ValueError:
        ok = True
    check(f"refuses {bad!r}", ok)
with db._connect(DBP) as c:
    c.execute("INSERT INTO courses (course_id, name) VALUES (22362, 'Kissing Tree Golf Club')")
    eid = c.execute("INSERT INTO events (item_name, event_date, course) VALUES ('s18.12 FALL', '2026-10-31', "
                    "'Kissing Tree Golf Club') RETURNING id").fetchone()[0]
    c.commit()
check("an event row with no course_id finds its course by name",
      re_._event_course_id({"event": {"id": eid}, "db_path": DBP}) == 22362)

print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
