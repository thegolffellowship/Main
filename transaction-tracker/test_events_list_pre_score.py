"""The EVENTS leaderboard lists a live event as soon as its groups exist, before
anyone has scored (Kerry 2026-10-13: "Tonight's events not showing yet. They
should show starting when tee times are generated").

Run: python3 test_events_list_pre_score.py
"""
import contextlib
import io
import json
import logging
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    db.init_db(DB)
from email_parser import score_entry as se  # noqa: E402
from email_parser.timezone_utils import today_central_str  # noqa: E402

F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


TODAY = today_central_str()
EV, NAME = 931, "s9.27 Pre Score"
conn = sqlite3.connect(DB)
for cid, fn, ln in [(401, "Kerry", "Niester"), (402, "Adam", "Baker"), (403, "Pat", "Youngs")]:
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
course_id = conn.execute("INSERT INTO courses (name, status) VALUES ('Pre Links', 'active') "
                         "RETURNING course_id").fetchone()[0]
conn.execute("INSERT INTO events (id, item_name, event_date, course_id, course, chapter, format) "
             "VALUES (?,?,?,?,?,?,?)", (EV, NAME, TODAY, course_id, "Pre Links", "San Antonio", "9 Holes"))
db._ensure_scoring_tables(conn)
db._ensure_pairing_tables(conn)
db._ensure_gg_game_flights_tables(conn)
db._ensure_gg_game_results_tables(conn)
conn.commit()
conn.close()


def listed():
    return {e["id"]: e for e in db.get_events_leaderboard(db_path=DB)["events"]}


COURSE = [{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 10)]
rid = se.create_round(EV, 9, round_date=TODAY, label="s9.27", course_holes=COURSE,
                      course_id=course_id, db_path=DB)["round_id"]
se.upsert_group(rid, 1, players=[
    {"customer_id": 401, "display_name": "Kerry N", "tee": "50-64", "playing_handicap": 5},
    {"customer_id": 402, "display_name": "Adam B", "tee": "50-64", "playing_handicap": 3},
], db_path=DB)
se.upsert_group(rid, 2, players=[
    {"customer_id": 403, "display_name": "Pat Y", "tee": "50-64", "playing_handicap": 8},
], db_path=DB)

check("score entry off: not listed", EV not in listed())
db.set_app_setting("score_entry_live", "1", db_path=DB)
db.set_app_setting("score_entry_events", json.dumps([EV]), db_path=DB)
ls = listed()
check("groups exist, no scores: the event is listed", EV in ls, list(ls))
e = ls.get(EV, {})
check("field = players seated in the groups (3)", e.get("field") == 3, e.get("field"))
check("live entry, no money shown yet", e.get("live_entry") and e.get("money_visible") is False and not e.get("pot"), e)
check("its board opens without error", db.get_event_leaderboard(NAME, db_path=DB) is not None)
check("list API no longer carries the 'Unofficial' line in the page",
      "Golf Genius is the official scorer<span" not in open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                          "templates", "contests.html")).read())
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
