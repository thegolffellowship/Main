"""The EVENTS board shows Closest to Pin winners from the PHONE claims for an
event Golf Genius does not score (Kerry 2026-10-13: "Why aren't closest to pins
showing?"). Golf Genius rows still win when they exist.

Run: python3 test_board_phone_ctp.py
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
EV, NAME = 941, "s9.27 Phone CTP"
c = sqlite3.connect(DB)
for cid, fn, ln in [(501, "Adam", "Baker"), (502, "Dan", "Stich")]:
    c.execute("INSERT INTO customers (customer_id, first_name, last_name) VALUES (?,?,?)", (cid, fn, ln))
course_id = c.execute("INSERT INTO courses (name, status) VALUES ('Phone Links', 'active') RETURNING course_id").fetchone()[0]
c.execute("INSERT INTO events (id, item_name, event_date, course_id, course, chapter, format) VALUES (?,?,?,?,?,?,?)",
          (EV, NAME, TODAY, course_id, "Phone Links", "San Antonio", "9 Holes"))
db._ensure_scoring_tables(c); db._ensure_pairing_tables(c)
db._ensure_gg_game_flights_tables(c); db._ensure_gg_game_results_tables(c)
c.commit(); c.close()

se.event_ctp_holders = lambda event_id, db_path=None: [
    {"round_id": 1, "hole": 12, "kind": "ctp", "customer_id": 501, "name": "Adam B"},
    {"round_id": 1, "hole": 16, "kind": "ctp", "customer_id": 502, "name": "Dan S"},
] if event_id == EV else []

with db._connect(DB) as conn:
    px = db._entry_ctp_proxies(conn, {"id": EV, "item_name": NAME, "format": "9 Holes"}, db_path=DB)
check("one row per contest hole, canonical names, hole in the detail",
      [(p["player"], p["detail"], p["label"]) for p in px]
      == [("Adam Baker", "Hole 12", "Closest to Pin"), ("Dan Stich", "Hole 16", "Closest to Pin")], px)
check("rows carry customer_id", [p["customer_id"] for p in px] == [501, 502], px)

se.event_ctp_holders = lambda event_id, db_path=None: [
    {"round_id": 1, "hole": 12, "kind": "ctp", "customer_id": None, "name": None}]
with db._connect(DB) as conn:
    px = db._entry_ctp_proxies(conn, {"id": EV, "item_name": NAME, "format": "9 Holes"}, db_path=DB)
check("a hole nobody holds says No winner, no money", px and px[0]["player"] == "No winner" and px[0]["purse"] is None, px)

se.event_ctp_holders = lambda event_id, db_path=None: [
    {"round_id": 1, "hole": 12, "kind": "ctp", "customer_id": 501, "name": "Adam B"}] if event_id == EV else []
lb = db.get_event_leaderboard(NAME, db_path=DB) or {}
check("the event's board carries the phone CTP winner",
      [(p["player"], p["detail"]) for p in lb.get("proxies") or []] == [("Adam Baker", "Hole 12")], lb.get("proxies"))
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_parser", "database.py")).read()
check("the board falls back to the phones only when Golf Genius has no CTP rows",
      "if not proxies:\n            try:\n                proxies = _entry_ctp_proxies(conn, ev, db_path=db_path)" in src)
print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
