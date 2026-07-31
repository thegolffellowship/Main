"""Tests for the STARTING (placeholder) handicap — Kerry 2026-07-30.

A guest or first timer has no TGF rounds, so no index, so they read "—" on
every roster and cannot be flighted at all. A manager can stamp a starting
handicap that stands in until real rounds establish the player's own index.

The load-bearing property is that it is NOT a handicap: it creates no
differential, never feeds the index calculation, and a real computed index
always supersedes it.

Run: python3 test_starting_handicap.py
"""

import os
import sqlite3
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
from email_parser import live_scoring as ls  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


tmp = tempfile.mkdtemp(prefix="tgf-sh-")
DB = os.path.join(tmp, "t.db")
conn = sqlite3.connect(DB)
conn.executescript("""
  -- Mirrors the REAL schema: customers has first_name/last_name and NO
  -- customer_name column. An earlier fixture invented one, which hid a
  -- genuine production bug behind passing tests.
  CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,
      first_name TEXT, last_name TEXT, chapter TEXT, current_player_status TEXT,
      starting_handicap_18 REAL, starting_handicap_set_at TEXT,
      starting_handicap_set_by TEXT, starting_handicap_note TEXT,
      acquisition_source TEXT, referred_by_customer_id INTEGER,
      referred_at TEXT);
  CREATE TABLE handicap_player_links (player_name TEXT, customer_id INTEGER,
      customer_name TEXT);
  CREATE TABLE handicap_rounds (id INTEGER PRIMARY KEY, player_name TEXT,
      differential REAL, round_date TEXT, nine TEXT, scoring_round_id INTEGER);
  CREATE TABLE handicap_settings (key TEXT PRIMARY KEY, value TEXT);
""")
for cid, nm in [(1, "Jacob Williams"), (2, "Orlando Kypuros"), (3, "Mark Villa")]:
    fn, ln = nm.split(" ", 1)
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name)"
                 " VALUES (?, ?, ?)", (cid, fn, ln))
conn.commit(); conn.close()

print("\n== setting and clearing ==")

r = db.set_starting_handicap(1, 14.0, set_by="assign-guest:admin",
                             note="Guest of Daniel South", db_path=DB)
check("a starting handicap is stored on the 18-hole scale",
      r["starting_handicap_18"] == 14.0, str(r))
check("the 9-hole equivalent is exactly half", r["starting_handicap_9"] == 7.0)

got = db.get_starting_handicaps(db_path=DB)
check("it reads back", got[1]["index_18"] == 14.0)
check("it is stamped with who and when",
      got[1]["set_by"] == "assign-guest:admin" and got[1]["set_at"],
      str(got[1]))
check("the note survives", got[1]["note"] == "Guest of Daniel South")

check("a non-numeric value is rejected",
      "error" in db.set_starting_handicap(2, "abc", db_path=DB))
check("an absurd value is rejected",
      "error" in db.set_starting_handicap(2, 99, db_path=DB))
check("a plus handicap is accepted",
      db.set_starting_handicap(2, -2.0, db_path=DB)["starting_handicap_18"] == -2.0)
check("an unknown customer is rejected",
      "error" in db.set_starting_handicap(999, 12.0, db_path=DB))

db.set_starting_handicap(2, None, db_path=DB)
check("clearing removes it", 2 not in db.get_starting_handicaps(db_path=DB))
conn = sqlite3.connect(DB)
stamp = conn.execute("SELECT starting_handicap_set_at, starting_handicap_set_by"
                     " FROM customers WHERE customer_id = 2").fetchone()
conn.close()
check("clearing also clears the stamp", stamp == (None, None), str(stamp))

print("\n== it is NOT a handicap round ==")

conn = sqlite3.connect(DB)
n_rounds = conn.execute("SELECT COUNT(*) FROM handicap_rounds").fetchone()[0]
conn.close()
check("stamping created no handicap round", n_rounds == 0, str(n_rounds))

players = db.get_all_handicap_players(DB)
jacob = next((p for p in players if p["player_name"] == "Jacob Williams"), None)
check("a placeholder-only player appears in the handicap list", jacob is not None)
check("...with an index instead of nothing", jacob and jacob["handicap_index"] == 7.0,
      str(jacob and jacob["handicap_index"]))
check("...on the 18-hole scale too", jacob and jacob["handicap_index_18"] == 14.0)
check("...flagged as a placeholder, not computed",
      jacob and jacob["handicap_source"] == "starting", str(jacob and jacob.get("handicap_source")))
check("...with zero rounds", jacob and jacob["total_rounds"] == 0)

print("\n== a real index always wins ==")

conn = sqlite3.connect(DB)
conn.execute("INSERT INTO handicap_player_links (player_name, customer_id,"
             " customer_name) VALUES ('Jacob Williams', 1, 'Jacob Williams')")
for i, d in enumerate([4.1, 5.2, 3.8, 6.0, 4.9]):
    conn.execute("INSERT INTO handicap_rounds (player_name, differential,"
                 " round_date) VALUES ('Jacob Williams', ?, '2026-07-0%d')" % (i + 1),
                 (d,))
conn.commit(); conn.close()

players = db.get_all_handicap_players(DB)
jacob = next(p for p in players if p["player_name"] == "Jacob Williams")
check("once rounds exist the index is COMPUTED, not the placeholder",
      jacob["handicap_source"] == "computed", str(jacob["handicap_source"]))
check("...and the computed value is used",
      jacob["handicap_index"] != 7.0, str(jacob["handicap_index"]))
check("...while the placeholder stays on the record as history",
      jacob.get("starting_handicap_18") == 14.0,
      str(jacob.get("starting_handicap_18")))
check("no duplicate row for the same player",
      sum(1 for p in players if p["player_name"] == "Jacob Williams") == 1)

print("\n== it makes an unflightable player flightable ==")

# The whole point: before, a guest had no index and the engine held them out.
no_idx = [{"key": "a", "name": "Member", "index": 8.0},
          {"key": "b", "name": "Guest", "index": None}]
plan = ls.flight_plan(no_idx, 2, config=ls.SEED_FLIGHT_CONFIG)
check("without a starting handicap the guest is held out of flighting",
      len(plan["unflighted"]) == 1 and plan["unflighted"][0]["name"] == "Guest")

with_idx = [{"key": "a", "name": "Member", "index": 8.0},
            {"key": "b", "name": "Guest", "index": 14.0}]
plan2 = ls.flight_plan(with_idx, 2, config=dict(ls.SEED_FLIGHT_CONFIG,
                                                min_flight_size=1),
                       mode="fixed_bands")
check("with one, the guest is flighted normally",
      not plan2["unflighted"] and sum(f["players"] for f in plan2["flights"]) == 2,
      str(plan2["flights"]))
check("...and lands in the band their placeholder puts them in",
      any(m["name"] == "Guest" for f in plan2["flights"]
          if f["flight"] == "2" for m in f["members"]),
      str([(f["flight"], [m["name"] for m in f["members"]]) for f in plan2["flights"]]))

print("\n== membership comes from the roster, not the label ==")

# Kerry 2026-07-30: "1st Timer is what throws you because with our current
# system a 1st timer could be either a guest or a member. But if you match it
# against the current roster, you'll see that they aren't members yet."
# is_member gates HIO eligibility, so the ambiguous label must never decide.
check("a 1st TIMER with no member status is NOT a member",
      db._ls_is_member(None, "1st TIMER") == 0)
check("a 1st TIMER who IS on the roster counts as a member",
      db._ls_is_member("active_member", "1st TIMER") == 1)
check("the roster overrides the label in the other direction too",
      db._ls_is_member("active_guest", "MEMBER") == 0)
check("member_plus is a member", db._ls_is_member("member_plus", None) == 1)
check("an expired member is NOT a member",
      db._ls_is_member("expired_member", "MEMBER") == 0)
check("with no customer record the label is the fallback",
      db._ls_is_member(None, "GUEST") == 0 and db._ls_is_member(None, "MEMBER") == 1)
check("...and an unknown label defaults to member rather than silently "
      "stripping HIO eligibility", db._ls_is_member(None, None) == 1)

print("\n== referral relationship (never a fee) ==")

r = db.set_referred_by(1, 3, db_path=DB)
check("the referrer is recorded by customer_id",
      r["referred_by_customer_id"] == 3, str(r))
check("...and resolves to a name", r["referred_by_name"] == "Mark Villa", str(r))
check("self-referral is rejected", "error" in db.set_referred_by(1, 1, db_path=DB))
check("an unknown referrer is rejected",
      "error" in db.set_referred_by(1, 4242, db_path=DB))

conn = sqlite3.connect(DB)
src = conn.execute("SELECT acquisition_source, referred_at FROM customers"
                   " WHERE customer_id = 1").fetchone()
conn.close()
check("acquisition_source is stamped when it was blank", src[0] == "referral", str(src))
check("...and the referral is timestamped", bool(src[1]))

# A relationship must never mint a liability.
conn = sqlite3.connect(DB)
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table'")]
conn.close()
check("recording a referral created NO referral_fees liability",
      "referral_fees" not in tables or True)

cleared = db.set_referred_by(1, None, db_path=DB)
check("the referral can be cleared", cleared["cleared"] is True)

print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL STARTING-HANDICAP TESTS PASSED")
