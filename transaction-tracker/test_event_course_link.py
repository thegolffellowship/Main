"""THE COURSE LINK FOLLOWS THE COURSE NAME (v2.524.6, Kerry 2026-10-06).

a9.26 Avery Ranch (event 3316) was named Avery Ranch but linked to
ShadowGlen, so the scorer card showed ShadowGlen's holes, tees and ratings.
Editing an event's course name never re-pointed `events.course_id`, and the
boot backfill only fills NULL links. Kerry: "audit all the courses then, and
make sure we don't have any other situations like that."

Checks: update_event re-resolves the link from the name (name or alias,
lower() both sides, live row beats an archived twin); a name no course
carries clears the link; event_course_audit reports wrong / unlinked /
unknown and nothing else; a re-seed refreshes the round's course link.

Run: python3 test_event_course_link.py
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


AVERY, SHADOW, AVERY_OLD = 910001, 910002, 910003
EV_WRONG, EV_OK, EV_UNLINKED, EV_UNKNOWN, EV_PAST = 9401, 9402, 9403, 9404, 9405
with db._connect(DB) as conn:
    conn.execute("INSERT INTO courses (course_id, name, status) VALUES (?,?,?)",
                 (AVERY, "Avery Ranch Golf Club", "active"))
    conn.execute("INSERT INTO courses (course_id, name, status) VALUES (?,?,?)",
                 (SHADOW, "ShadowGlen Golf Club", "active"))
    conn.execute("INSERT INTO courses (course_id, name, status) VALUES (?,?,?)",
                 (AVERY_OLD, "Avery Ranch Golf Club (OLD) - Archived on 07-07-2023", "active"))
    # alias_name is UNIQUE: one alias row per spelling. "Avery Ranch" is the
    # live course's alias; the archived twin carries "Avery Ranch Old".
    conn.execute("INSERT OR IGNORE INTO course_aliases (course_id, alias_name) VALUES (?,?)",
                 (AVERY, "Avery Ranch"))
    conn.execute("INSERT OR IGNORE INTO course_aliases (course_id, alias_name) VALUES (?,?)",
                 (AVERY_OLD, "Avery Ranch Old"))
    # A live row NAMED what an archived row is only ALIASED as: the name wins.
    conn.execute("INSERT INTO courses (course_id, name, status) VALUES (?,?,?)",
                 (AVERY_OLD + 1, "Twin Links", "active"))
    conn.execute("INSERT OR IGNORE INTO course_aliases (course_id, alias_name) VALUES (?,?)",
                 (AVERY_OLD, "Twin Links"))
    for _id, nm, date, course, cid in (
            (EV_WRONG, "a9.26 Avery Ranch TEST", "2099-10-06", "Avery Ranch Golf Club", SHADOW),
            (EV_OK, "a9.22 ShadowGlen TEST", "2099-09-08", "  shadowglen golf club ", SHADOW),
            (EV_UNLINKED, "a9.28 Avery Ranch TEST", "2099-10-20", "Avery Ranch", None),
            (EV_UNKNOWN, "a9.30 Nowhere TEST", "2099-11-03", "Nowhere Links", SHADOW),
            (EV_PAST, "a9.1 Avery Ranch PAST", "2020-01-01", "Avery Ranch Golf Club", SHADOW)):
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter, status, format, course, course_id) "
                     "VALUES (?,?,?,?,?,?,?,?)", (_id, nm, date, "Austin", "active", "9 Holes", course, cid))
    conn.commit()

print("course_id_for_name")
with db._connect(DB) as conn:
    check("exact name, any case and spacing", db.course_id_for_name(conn, "  avery ranch GOLF club ") == AVERY)
    check("alias resolves", db.course_id_for_name(conn, "avery ranch") == AVERY)
    check("archived twin's alias still resolves to it", db.course_id_for_name(conn, "Avery Ranch Old") == AVERY_OLD)
    check("a row's own name beats another row's alias", db.course_id_for_name(conn, "Twin Links") == AVERY_OLD + 1)
    check("unknown name is None", db.course_id_for_name(conn, "Nowhere Links") is None)
    check("blank is None", db.course_id_for_name(conn, "  ") is None)

print("event_course_audit (upcoming)")
a = db.event_course_audit("upcoming", db_path=DB)
by = {p["event_id"]: p for p in a["problems"]}
check("wrong link reported with the fix", by.get(EV_WRONG, {}).get("state") == "wrong"
      and by[EV_WRONG]["should_be_course_id"] == AVERY and by[EV_WRONG]["linked_course_id"] == SHADOW, str(by.get(EV_WRONG)))
check("unlinked reported", by.get(EV_UNLINKED, {}).get("state") == "unlinked"
      and by[EV_UNLINKED]["should_be_course_id"] == AVERY)
check("unknown name reported", by.get(EV_UNKNOWN, {}).get("state") == "unknown")
check("a right link is not a problem", EV_OK not in by)
check("past events stay out of 'upcoming'", EV_PAST not in by)
check("counts add up", a["counts"]["wrong"] >= 1 and a["counts"]["ok"] >= 1)
a_all = db.event_course_audit("all", db_path=DB)
check("'all' includes the past event", any(p["event_id"] == EV_PAST for p in a_all["problems"]))
one = db.event_course_audit(event_id=EV_OK, db_path=DB)
check("one event reads back even when ok", one["problems"] and one["problems"][0]["state"] == "ok")

print("update_event re-resolves the link")
with db._connect(DB) as conn:
    before = conn.execute("SELECT course_id FROM events WHERE id = ?", (EV_WRONG,)).fetchone()[0]
check("starts wrong", before == SHADOW)
ok = db.update_event(EV_WRONG, {"course": "Avery Ranch Golf Club"}, db_path=DB)
with db._connect(DB) as conn:
    after = conn.execute("SELECT course, course_id FROM events WHERE id = ?", (EV_WRONG,)).fetchone()
check("same name re-points the link", ok and after[1] == AVERY and after[0] == "Avery Ranch Golf Club", str(tuple(after)))
db.update_event(EV_UNLINKED, {"course": "Avery Ranch"}, db_path=DB)
with db._connect(DB) as conn:
    r = conn.execute("SELECT course_id FROM events WHERE id = ?", (EV_UNLINKED,)).fetchone()[0]
check("an alias links to the live row", r == AVERY)
db.update_event(EV_UNKNOWN, {"course": "Nowhere Links"}, db_path=DB)
with db._connect(DB) as conn:
    r = conn.execute("SELECT course_id FROM events WHERE id = ?", (EV_UNKNOWN,)).fetchone()[0]
check("a name no course carries clears the link (no link beats a wrong one)", r is None)
db.update_event(EV_OK, {"tgf_markup": 9.0}, db_path=DB)
with db._connect(DB) as conn:
    r = conn.execute("SELECT course_id FROM events WHERE id = ?", (EV_OK,)).fetchone()[0]
check("an update without 'course' leaves the link alone", r == SHADOW)
check("audit is clean after the fixes",
      {p["state"] for p in db.event_course_audit("upcoming", db_path=DB)["problems"]} <= {"unknown"})

print("a round follows the event's course link")
rid = se.create_round(EV_WRONG, 9, course_id=SHADOW, pairings_holes=None, db_path=DB)["round_id"]
check("round starts on the old link", se.sync_round_course(rid, AVERY, db_path=DB) is True)
check("second sync is a no-op", se.sync_round_course(rid, AVERY, db_path=DB) is False)
check("a missing course id is a no-op", se.sync_round_course(rid, None, db_path=DB) is False)
with db._connect(DB) as conn:
    r = conn.execute("SELECT course_id FROM se_rounds WHERE id = ?", (rid,)).fetchone()[0]
check("round now reads the event's course", r == AVERY)

print()
print("FAILURES:", F or "none")
sys.exit(1 if F else 0)
