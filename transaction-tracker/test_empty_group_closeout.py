"""AN EMPTY GROUP NEVER HOLDS CLOSEOUT (Kerry 2026-10-28 via Event Ops #2457:
"the system needs to resolve that and not be held up by it"). On s9.29
Silverhorn (10/27) a "Hole 3B" group with 0 players never went final, so
scoring never closed and CLOSEOUT START never fired. Every card that holds a
player is final here, plus one empty group: scoring closes, closeout is due,
and auto payouts read the event as final.

Run: python3 test_empty_group_closeout.py
"""
import os, sys, tempfile, logging
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                           # noqa: E402
from email_parser import score_entry as se                        # noqa: E402
from email_parser import scoring_window as sw                     # noqa: E402
from email_parser import auto_payouts as ap                       # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


with db._connect(DB) as c:
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format,start_type,start_time,course) "
              "VALUES (3303,'s9.29 SILVERHORN','2026-10-27','San Antonio','active','9 Holes','Shotgun','16:30','S')")
    c.commit()

last = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=40)).strftime("%Y-%m-%d %H:%M:%S")
final_at = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M:%S")
ROUND = {"round_id": 1, "label": "s9.29", "holes": 9,
         "groups": [{"group_id": 1, "group_num": 1, "label": "1A", "last_write_at": last,
                     "final_at": final_at, "final": True},
                    {"group_id": 6, "group_num": 6, "label": "3B", "last_write_at": None,
                     "final_at": None, "final": False}],
         "players": [{"customer_id": 10, "group_id": 1, "scores": {str(h): 4 for h in range(1, 10)}}],
         "teams": []}
READ = {"event_id": 3303, "rounds": [ROUND]}

check("scored_groups drops the empty group", [g["group_id"] for g in se.scored_groups(ROUND)] == [1])

_real = se.get_entered_scores
se.get_entered_scores = lambda *a, **k: READ
try:
    st = sw.event_state(3303, now=datetime.now() + timedelta(days=1), db_path=DB)
finally:
    se.get_entered_scores = _real
check("all cards final despite the empty group", st.get("all_final") is True, st)
check("scoring closes", st.get("closed") is True, st)
check("CLOSEOUT START is due", st.get("closeout_due") is True, st)
check("the empty group isn't counted", st.get("groups") == 1, st)

ok, _when = ap._event_final(READ)
check("auto payouts read the event as final", ok is True, (ok, _when))

try:
    os.remove(DB)
except OSError:
    pass
print("\nALL PASS" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
