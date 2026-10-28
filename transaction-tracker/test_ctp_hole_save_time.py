"""CTP: THE LATEST CLAIM BY HOLE-SAVE TIME HOLDS THE HOLE (Kerry 2026-10-28,
Event Ops #2462-C / #2466-C / #2467-C, "Sounds good"). The question is asked
when the group saves the hole's scores; the claim counts at that first save,
and a later edit keeps it. No manager confirm, no takeover hold.

Run: python3 test_ctp_hole_save_time.py
"""
import os, sys, json, sqlite3, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import score_entry as se                        # noqa: E402
F = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


c = sqlite3.connect(":memory:")
c.row_factory = sqlite3.Row
c.executescript("""
CREATE TABLE se_groups (id INTEGER PRIMARY KEY, group_num INTEGER);
CREATE TABLE se_players (round_id INTEGER, customer_id INTEGER, display_name TEXT);
CREATE TABLE se_ctp_claims (id INTEGER PRIMARY KEY AUTOINCREMENT, round_id INTEGER, group_id INTEGER,
  hole_number INTEGER, customer_id INTEGER, kind TEXT, at TEXT);
CREATE TABLE se_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER, kind TEXT, result TEXT,
  detail TEXT, at TEXT);
INSERT INTO se_groups VALUES (1, 1), (2, 2);
INSERT INTO se_players VALUES (7, 45, 'Wade Winters'), (7, 99, 'Pat Youngs');
""")


def save(group, hole, at):
    c.execute("INSERT INTO se_audit (group_id, kind, result, detail, at) VALUES (?, 'write', 'ok', ?, ?)",
              (group, json.dumps({"hole": hole, "gross": 3, "customer_id": 1}), at))


def claim(group, hole, cid, at, kind="claim"):
    c.execute("INSERT INTO se_ctp_claims (round_id, group_id, hole_number, customer_id, kind, at) "
              "VALUES (7, ?, ?, ?, ?, ?)", (group, hole, cid, kind, at))


# Hole 8: Wade's group played it first (saved 17:10) but entered its claim
# late (17:40); Pat's group played it after (saved 17:25) and claimed at 17:26.
save(1, 8, "2026-10-31 17:10:00")
save(2, 8, "2026-10-31 17:25:00")
claim(2, 8, 99, "2026-10-31 17:26:00")
claim(1, 8, 45, "2026-10-31 17:40:00")
cur = se._ctp_current(c, 7, 8)
check("the later HOLE SAVE holds (Pat), though Wade's claim was entered last",
      cur["customer_id"] == 99, dict(cur))

# A later edit by Wade's group keeps the 17:10 save time.
save(1, 8, "2026-10-31 17:50:00")
claim(1, 8, 45, "2026-10-31 17:51:00")
check("an edit keeps the group's first save time", se._ctp_current(c, 7, 8)["customer_id"] == 99)

# A group that played later and is closer takes it.
save(1, 3, "2026-10-31 17:00:00")
save(2, 3, "2026-10-31 17:20:00")
claim(1, 3, 45, "2026-10-31 17:01:00")
claim(2, 3, 99, "2026-10-31 17:21:00")
check("a later group's closer claim takes the hole", se._ctp_current(c, 7, 3)["customer_id"] == 99)

# No hole save on record: the claim's own time.
claim(1, 5, 45, "2026-10-31 17:30:00")
check("no save on record: the claim's own time", se._ctp_current(c, 7, 5)["customer_id"] == 45)

check("no manager confirm (takeover retired)", se.ctp_takeover(c, 7, 3) is None)

print("\nALL PASS" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
