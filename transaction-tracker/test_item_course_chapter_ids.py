"""COURSE / CHAPTER TEXT AND ITS ID MOVE TOGETHER (Kerry 2026-10-29, item
3162: Peter Rundqvist's Silverhorn row read ShadowGlen / Austin).
update_item re-resolves course_id / chapter_id whenever the text changes.

Run: python3 test_item_course_chapter_ids.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(tempfile.mkdtemp(prefix="tgf-ids-"), "t.db")
os.environ["DATABASE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "t" * 32)
logging.disable(logging.CRITICAL)
from email_parser import database as db   # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

db.init_db(DB)
with db._connect(DB) as c:
    sa = c.execute("SELECT chapter_id FROM chapters WHERE name = 'San Antonio'").fetchone()
    aus = c.execute("SELECT chapter_id FROM chapters WHERE name = 'Austin'").fetchone()
    if not sa:
        c.execute("INSERT INTO chapters (name, short_code, timezone) VALUES ('San Antonio','SA','America/Chicago')")
        c.execute("INSERT INTO chapters (name, short_code, timezone) VALUES ('Austin','AUS','America/Chicago')")
    c.execute("INSERT INTO courses (name) VALUES ('Silverhorn Golf Club of Texas')")
    c.execute("INSERT INTO courses (name) VALUES ('ShadowGlen')")
    sa = c.execute("SELECT chapter_id FROM chapters WHERE name = 'San Antonio'").fetchone()[0]
    aus = c.execute("SELECT chapter_id FROM chapters WHERE name = 'Austin'").fetchone()[0]
    silver = c.execute("SELECT course_id FROM courses WHERE name = 'Silverhorn Golf Club of Texas'").fetchone()[0]
    shadow = c.execute("SELECT course_id FROM courses WHERE name = 'ShadowGlen'").fetchone()[0]
    iid = c.execute("INSERT INTO items (email_uid, item_index, merchant, order_date, customer, item_name, course, chapter, "
                    "course_id, chapter_id) VALUES ('x', 1, 'TGF', '2026-10-24', 'Peter Rundqvist', 's9.29 SILVERHORN', "
                    "'ShadowGlen', 'Austin', ?, ?)", (shadow, aus)).lastrowid
    c.commit()

check("update succeeds", db.update_item(iid, {"course": "Silverhorn Golf Club of Texas",
                                              "chapter": "San Antonio"}, db_path=DB))
with db._connect(DB) as c:
    row = c.execute("SELECT course, chapter, course_id, chapter_id FROM items WHERE id = ?", (iid,)).fetchone()
check("the ids follow the text", tuple(row) == ("Silverhorn Golf Club of Texas", "San Antonio", silver, sa), tuple(row))
db.update_item(iid, {"chapter": "atx"}, db_path=DB)
with db._connect(DB) as c:
    cid = c.execute("SELECT chapter_id FROM items WHERE id = ?", (iid,)).fetchone()[0]
check("a chapter alias resolves", cid == aus, cid)
db.update_item(iid, {"course": "Nowhere GC"}, db_path=DB)
with db._connect(DB) as c:
    crs = c.execute("SELECT course_id FROM items WHERE id = ?", (iid,)).fetchone()[0]
check("an unknown course clears the old id, never keeps it", crs is None, crs)
db.update_item(iid, {"notes": "x"}, db_path=DB)
with db._connect(DB) as c:
    cid2 = c.execute("SELECT chapter_id FROM items WHERE id = ?", (iid,)).fetchone()[0]
check("an unrelated edit leaves the ids alone", cid2 == aus, cid2)

print(f"\n{'ALL PASS' if not F else str(len(F)) + ' FAILED: ' + ', '.join(F)}")
sys.exit(1 if F else 0)
