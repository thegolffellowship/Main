"""Handicap exclusion for partial cards + single-card drop (v2.368.0).

Kerry, 2026-09-10, on s18.10 FALL KICKOFF: "Reimports are correct for
Aguilera and Ayala as I entered the remaining missing scores manually.
Atkinson and their 4th were partial cards that should not be recorded
into handicaps."

  - exclude_scoring_rounds_from_handicaps marks the cards hcp_exclude=1
    and deletes the handicap rounds already bridged to them.
  - drop_scoring_round removes one card; bridged rounds are unlinked, or
    deleted with unpost=True.

Run: python3 test_hcp_exclude.py
"""

import os
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


def fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    with db._connect(p) as conn:
        conn.executescript("""
            CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT);
            CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT, event_date TEXT, course TEXT);
            CREATE TABLE handicap_rounds (id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT, customer_id INTEGER, round_date TEXT,
                adjusted_score INTEGER, rating REAL, slope INTEGER, differential REAL);
            CREATE TABLE action_items (id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT, status TEXT);
            INSERT INTO events VALUES (3298, 's18.10 FALL KICKOFF | Landa Park', '2026-08-29', 'Landa Park');
            INSERT INTO customers VALUES (61, 'Bob', 'Atkinson');
            INSERT INTO customers VALUES (62, 'David', 'Decareaux');
            INSERT INTO customers VALUES (63, 'Hector', 'Aguilera');
        """)
        db._ensure_scoring_tables(conn)
        for rid, cid, name, holes in ((3350, 61, 'ATKINSON, Bob', 18), (3390, 61, 'ATKINSON, Bob', 10),
                                      (3347, 62, 'DECAREAUX, David', 18),
                                      (3348, 63, 'AGUILERA, Hector', 18), (3377, 63, 'AGUILERA, Hector', 18)):
            conn.execute("INSERT INTO scoring_rounds (id, customer_id, player_name, event_id, "
                         "round_date, holes_played, gg_aggregate_id) VALUES (?,?,?,3298,'2026-08-29',?,?)",
                         (rid, cid, name, holes, f"A{rid}"))
            for h in range(1, holes + 1):
                conn.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, strokes) "
                             "VALUES (?,?,5)", (rid, h))
        # Two handicap rounds (front + back) bridged to each 18-hole keeper.
        for rid, cid, name in ((3350, 61, 'Bob Atkinson'), (3347, 62, 'David Decareaux'),
                               (3348, 63, 'Hector Aguilera')):
            for adj in (52, 51):
                conn.execute("INSERT INTO handicap_rounds (player_name, customer_id, round_date, "
                             "adjusted_score, rating, slope, differential, scoring_round_id) "
                             "VALUES (?,?,'2026-08-29',?,36.4,137,12.0,?)", (name, cid, adj, rid))
        conn.execute("INSERT INTO action_items (subject, status) VALUES "
                     "('Scorecard discrepancy: AGUILERA, Hector (round 3348)', 'open')")
        conn.commit()
    return p


CIDS = {"atkinson": 61, "decareaux": 62, "aguilera": 63}
db._resolve_scoring_player = lambda conn, name: CIDS.get(name.lower())

print("\n== 1. exclusion: dry run then apply ==")
p = fresh_db()
dry = db.exclude_scoring_rounds_from_handicaps("FALL KICKOFF", ["Atkinson", "Decareaux"],
                                               note="partial card", apply=False, db_path=p)
check("dry run finds 3 cards (Atkinson x2, Decareaux x1)", len(dry["cards"]) == 3, str(dry))
check("dry run lists 2 bridged rounds on each 18-hole card",
      sorted(len(c["handicap_rounds_unposted"]) for c in dry["cards"]) == [0, 2, 2], str(dry))
with db._connect(p) as conn:
    n_hr = conn.execute("SELECT COUNT(*) FROM handicap_rounds").fetchone()[0]
check("dry run wrote nothing", n_hr == 6)
res = db.exclude_scoring_rounds_from_handicaps("FALL KICKOFF", ["Atkinson", "Decareaux"],
                                               note="partial card", apply=True, db_path=p)
with db._connect(p) as conn:
    flags = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT id, hcp_exclude, hcp_exclude_note FROM scoring_rounds")}
    n_hr = conn.execute("SELECT COUNT(*) FROM handicap_rounds").fetchone()[0]
    agu = conn.execute("SELECT COUNT(*) FROM handicap_rounds WHERE customer_id = 63").fetchone()[0]
check("4 handicap rounds unposted", res["handicap_rounds_unposted"] == 4, str(res))
check("both Atkinson cards and Decareaux's are flagged",
      flags[3350] == (1, "partial card") and flags[3390][0] == 1 and flags[3347][0] == 1, str(flags))
check("Aguilera untouched", flags[3348][0] in (0, None) and agu == 2, str(flags))
check("remaining handicap rounds are Aguilera's two", n_hr == 2)

print("\n== 2. drop_scoring_round with unpost ==")
dry = db.drop_scoring_round(3348, unpost=True, apply=False, db_path=p)
check("dry run shows the 2 bridged rounds and would delete them",
      len(dry["bridged_handicap_rounds"]) == 2 and dry["handicap_rounds"] == "would delete", str(dry))
res = db.drop_scoring_round(3348, unpost=True, apply=True, db_path=p)
with db._connect(p) as conn:
    gone = conn.execute("SELECT COUNT(*) FROM scoring_rounds WHERE id = 3348").fetchone()[0]
    holes = conn.execute("SELECT COUNT(*) FROM scoring_holes WHERE scoring_round_id = 3348").fetchone()[0]
    agu = conn.execute("SELECT COUNT(*) FROM handicap_rounds WHERE customer_id = 63").fetchone()[0]
    item = conn.execute("SELECT status FROM action_items").fetchone()[0]
    kept = conn.execute("SELECT COUNT(*) FROM scoring_rounds WHERE id = 3377").fetchone()[0]
check("card and holes gone", gone == 0 and holes == 0)
check("its wrong differentials gone too", agu == 0)
check("its discrepancy item closed", item == "completed", item)
check("the corrected re-import card survives", kept == 1)
check("unknown id is an error", "error" in db.drop_scoring_round(99999, apply=True, db_path=p))

print("\n== 3. drop without unpost unlinks instead ==")
p = fresh_db()
db.drop_scoring_round(3350, unpost=False, apply=True, db_path=p)
with db._connect(p) as conn:
    row = conn.execute("SELECT COUNT(*), SUM(scoring_round_id IS NULL) FROM handicap_rounds "
                       "WHERE customer_id = 61").fetchone()
check("Atkinson's rounds kept but unlinked", tuple(row) == (2, 2), str(tuple(row)))

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL PASSED")
