"""Duplicate-scorecard guard + repair (v2.365.0).

Cause of record — a9.22 ShadowGlen, 2026-09-09: the closeout's targeted
re-import (`scoring-import-event:a9.22@1702842`) stamped the league round
key onto the 16 auto-synced cards; Kerry then added the Skins/CTP boards on
GG, which re-keyed the tournament's aggregate ids; the hourly auto-sync
(which passes NO round key) saw new aggregates, found no keyless twin, and
inserted a second full set — 32 scoring_rounds for 16 players. Handicaps
had already posted off the first set, so the preview showed 16 imported +
16 "new" cards waiting to double-post.

What this file proves:
  1. A missing round key on EITHER side is a wildcard in the
     cross-tournament dedupe, not a different round.
  2. A keyless re-import never erases a stored round key.
  3. Two keyed rounds with DIFFERENT keys (multi-round days) still stay
     apart.
  4. dedupe_scoring_rounds finds the a9.22 shape, keeps the bridged card,
     moves the bridge, deletes the loser's holes + row, closes its open
     discrepancy item — and leaves genuine multi-round rows alone.

Run: python3 test_scoring_dedupe.py
"""

import os
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
import golf_genius_sync  # noqa: E402

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
            CREATE TABLE customers (customer_id INTEGER PRIMARY KEY,
                first_name TEXT, last_name TEXT);
            CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT,
                event_date TEXT, course TEXT);
            CREATE TABLE handicap_rounds (id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT, customer_id INTEGER, round_date TEXT,
                adjusted_score INTEGER, rating REAL, slope INTEGER,
                differential REAL);
            CREATE TABLE action_items (id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT, status TEXT);
            INSERT INTO customers VALUES (13, 'Luke', 'Youngs');
            INSERT INTO customers VALUES (109, 'Neal', 'Cloer');
            INSERT INTO events VALUES (3313, 'a9.22 ShadowGlen', '2026-09-08',
                'ShadowGlen Golf Club');
            INSERT INTO events VALUES (9001, 'HCM Matches', '2026-05-02',
                'Comanche Trace');
        """)
        db._ensure_scoring_tables(conn)
        conn.commit()
    return p


# The import path's collaborators that need a full production schema are
# stubbed: identity resolution (a name→cid map), the handicap bridge, and
# the post-import GG verification. The dedupe logic under test is untouched.
CIDS = {"YOUNGS, Luke": 13, "CLOER, Neal": 109}
db._resolve_scoring_player = lambda conn, name: CIDS.get(name)
db._bridge_handicap_records = lambda *a, **k: 0
db.verify_scoring_round = lambda srid, db_path=None: {"all_ok": True}
db.recompute_computed_mvps = lambda *a, **k: None


def card(name, agg, ph=2.0, gross=39):
    holes = {h: {"strokes": 4 + (h % 2), "dots": 0, "result": None}
             for h in range(1, 10)}
    return {"player_name": name, "gg_aggregate_id": agg, "gg_event_id": "4810193",
            "gg_profile_id": None, "playing_handicap": ph, "gross": gross,
            "net": gross - ph, "flight": None, "tee": None, "holes": holes}


def fake_fetch(players):
    golf_genius_sync.fetch_tournament_scorecards = \
        lambda url: {"players": players, "raw": []}


def rows(p, event_id=3313):
    with db._connect(p) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, player_name, gg_league_round_id, gg_aggregate_id "
            "FROM scoring_rounds WHERE event_id = ? ORDER BY id", (event_id,))]


print("\n== 1. keyed first, then keyless with NEW aggregate ids (the a9.22 shape) ==")
p = fresh_db()
fake_fetch([card("YOUNGS, Luke", "A1"), card("CLOER, Neal", "A2")])
r1 = db.import_gg_scorecards("https://x/t/1", event_code="a9.22 ShadowGlen",
                             round_key="1702842", db_path=p)
check("first import lands 2 cards", r1.get("imported") == 2, str(r1))
fake_fetch([card("YOUNGS, Luke", "B1"), card("CLOER, Neal", "B2")])
r2 = db.import_gg_scorecards("https://x/t/2", event_code="a9.22 ShadowGlen",
                             db_path=p)   # NO round key — the auto-sync's call
rs = rows(p)
check("keyless re-import adds NO rows", len(rs) == 2,
      f"{len(rs)} rows: {rs}")
check("it is counted as a replace/skip, not an import",
      r2.get("imported") == 0, str(r2))
check("the stored round key survives the keyless pass",
      all(r["gg_league_round_id"] == "1702842" for r in rs), str(rs))

print("\n== 2. keyless first, then keyed with new aggregates ==")
p = fresh_db()
fake_fetch([card("YOUNGS, Luke", "A1")])
db.import_gg_scorecards("https://x/t/1", event_code="a9.22 ShadowGlen", db_path=p)
fake_fetch([card("YOUNGS, Luke", "B1")])
db.import_gg_scorecards("https://x/t/2", event_code="a9.22 ShadowGlen",
                        round_key="1702842", db_path=p)
rs = rows(p)
check("still one card", len(rs) == 1, str(rs))
check("the keyed pass stamps the key", rs[0]["gg_league_round_id"] == "1702842",
      str(rs))

print("\n== 3. two keyed rounds with DIFFERENT keys stay apart (multi-round day) ==")
p = fresh_db()
fake_fetch([card("YOUNGS, Luke", "M1")])
db.import_gg_scorecards("https://x/t/1", event_code="HCM Matches",
                        round_key="R1", db_path=p)
fake_fetch([card("YOUNGS, Luke", "M2")])
db.import_gg_scorecards("https://x/t/2", event_code="HCM Matches",
                        round_key="R2", db_path=p)
rs = rows(p, 9001)
check("two rounds, two rows", len(rs) == 2 and
      {r["gg_league_round_id"] for r in rs} == {"R1", "R2"}, str(rs))
fake_fetch([card("YOUNGS, Luke", "M2b")])
db.import_gg_scorecards("https://x/t/3", event_code="HCM Matches",
                        round_key="R2", db_path=p)
rs = rows(p, 9001)
check("a re-keyed R2 aggregate adds no third row and leaves R1 alone",
      len(rs) == 2 and rs[0]["gg_aggregate_id"] == "M1"
      and [r["gg_league_round_id"] for r in rs] == ["R1", "R2"], str(rs))

print("\n== 4. dedupe_scoring_rounds on the a9.22 shape ==")
p = fresh_db()
with db._connect(p) as conn:
    # Set one: keyed, bridged to a posted handicap round (the keeper).
    conn.execute("""INSERT INTO scoring_rounds (id, customer_id, player_name, event_id,
                    gg_aggregate_id, round_date, holes_played, gross, net,
                    gg_league_round_id, imported_at)
                    VALUES (3452, 13, 'YOUNGS, Luke', 3313, 'A1', '2026-09-08', 9,
                            39, 37, '1702842', '2026-09-08 23:12:13')""")
    conn.execute("""INSERT INTO scoring_rounds (id, customer_id, player_name, event_id,
                    gg_aggregate_id, round_date, holes_played, gross, net,
                    gg_league_round_id, imported_at)
                    VALUES (3448, 109, 'CLOER, Neal', 3313, 'A2', '2026-09-08', 9,
                            39, 37, '1702842', '2026-09-08 23:12:13')""")
    # Set two: keyless, newer, not bridged (the auto-sync's second set).
    conn.execute("""INSERT INTO scoring_rounds (id, customer_id, player_name, event_id,
                    gg_aggregate_id, round_date, holes_played, gross, net,
                    gg_league_round_id, imported_at)
                    VALUES (3465, 13, 'YOUNGS, Luke', 3313, 'B1', '2026-09-08', 9,
                            39, 37, NULL, '2026-09-09 18:12:21')""")
    conn.execute("""INSERT INTO scoring_rounds (id, customer_id, player_name, event_id,
                    gg_aggregate_id, round_date, holes_played, gross, net,
                    gg_league_round_id, imported_at)
                    VALUES (3464, 109, 'CLOER, Neal', 3313, 'B2', '2026-09-08', 9,
                            39, 37, NULL, '2026-09-09 18:12:21')""")
    for rid in (3452, 3448, 3465, 3464):
        for h in range(1, 10):
            conn.execute("INSERT INTO scoring_holes (scoring_round_id, hole_number, "
                         "strokes) VALUES (?, ?, 4)", (rid, h))
    # Handicap rounds posted off set one.
    conn.execute("INSERT INTO handicap_rounds (player_name, customer_id, round_date, "
                 "adjusted_score, rating, slope, differential, scoring_round_id) "
                 "VALUES ('Luke Youngs', 13, '2026-09-08', 39, 36.3, 138, 2.2, 3452)")
    conn.execute("INSERT INTO handicap_rounds (player_name, customer_id, round_date, "
                 "adjusted_score, rating, slope, differential, scoring_round_id) "
                 "VALUES ('Neal Cloer', 109, '2026-09-08', 39, 35.3, 135, 3.1, 3448)")
    conn.execute("INSERT INTO action_items (subject, status) VALUES "
                 "('Scorecard discrepancy: YOUNGS, Luke (round 3465)', 'open')")
    # A genuine multi-round day for the same player must NOT be grouped.
    conn.execute("""INSERT INTO scoring_rounds (id, customer_id, player_name, event_id,
                    gg_aggregate_id, round_date, holes_played, gg_league_round_id)
                    VALUES (7001, 13, 'YOUNGS, Luke', 9001, 'M1', '2026-05-02', 9, 'R1')""")
    conn.execute("""INSERT INTO scoring_rounds (id, customer_id, player_name, event_id,
                    gg_aggregate_id, round_date, holes_played, gg_league_round_id)
                    VALUES (7002, 13, 'YOUNGS, Luke', 9001, 'M2', '2026-05-02', 9, 'R2')""")
    conn.commit()

dry = db.dedupe_scoring_rounds("a9.22 ShadowGlen", apply=False, db_path=p)
check("dry run finds 2 groups", dry["duplicate_groups"] == 2, str(dry))
check("dry run would drop the 2 keyless newer rows",
      sorted(sum((g["drop"] for g in dry["groups"]), [])) == [3464, 3465], str(dry))
check("keepers are the bridged rows",
      sorted(g["keep"] for g in dry["groups"]) == [3448, 3452], str(dry))
check("dry run writes nothing", len(rows(p)) == 4)

scan = db.dedupe_scoring_rounds("all", apply=False, db_path=p)
check("the all-events scan does NOT group the HCM R1/R2 rounds",
      scan["duplicate_groups"] == 2 and
      all(g["event"] == "a9.22 ShadowGlen" for g in scan["groups"]), str(scan))

res = db.dedupe_scoring_rounds("a9.22 ShadowGlen", apply=True, db_path=p)
check("apply drops 2 rows", res["rows_dropped"] == 2, str(res))
rs = rows(p)
check("two cards remain, the keyed ones",
      [r["id"] for r in rs] == [3448, 3452] and
      all(r["gg_league_round_id"] == "1702842" for r in rs), str(rs))
with db._connect(p) as conn:
    holes_left = conn.execute("SELECT COUNT(*) FROM scoring_holes").fetchone()[0]
    bridges = [r[0] for r in conn.execute(
        "SELECT scoring_round_id FROM handicap_rounds ORDER BY id")]
    hr_n = conn.execute("SELECT COUNT(*) FROM handicap_rounds").fetchone()[0]
    item = conn.execute("SELECT status FROM action_items").fetchone()[0]
    hcm = conn.execute("SELECT COUNT(*) FROM scoring_rounds WHERE event_id = 9001"
                       ).fetchone()[0]
check("losers' holes are gone (18 of 36 remain)", holes_left == 18, str(holes_left))
check("handicap rounds untouched in number", hr_n == 2, str(hr_n))
check("handicap bridges still point at the keepers", bridges == [3452, 3448],
      str(bridges))
check("the loser's open discrepancy item is closed", item == "completed", item)
check("the multi-round day is untouched", hcm == 2, str(hcm))
again = db.dedupe_scoring_rounds("a9.22 ShadowGlen", apply=True, db_path=p)
check("idempotent: a second apply finds nothing", again["duplicate_groups"] == 0,
      str(again))

print("\n== 5. a loser that holds the bridge is kept instead ==")
p = fresh_db()
with db._connect(p) as conn:
    conn.execute("""INSERT INTO scoring_rounds (id, customer_id, player_name, event_id,
                    gg_aggregate_id, round_date, holes_played, gg_league_round_id)
                    VALUES (1, 13, 'YOUNGS, Luke', 3313, 'A1', '2026-09-08', 9, NULL)""")
    conn.execute("""INSERT INTO scoring_rounds (id, customer_id, player_name, event_id,
                    gg_aggregate_id, round_date, holes_played, gg_league_round_id)
                    VALUES (2, 13, 'YOUNGS, Luke', 3313, 'B1', '2026-09-08', 9, '1702842')""")
    conn.execute("INSERT INTO handicap_rounds (player_name, customer_id, round_date, "
                 "adjusted_score, rating, slope, differential, scoring_round_id) "
                 "VALUES ('Luke Youngs', 13, '2026-09-08', 39, 36.3, 138, 2.2, 2)")
    conn.commit()
res = db.dedupe_scoring_rounds("a9.22", apply=True, db_path=p)
rs = rows(p)
check("the newer-but-bridged row is the keeper",
      [r["id"] for r in rs] == [2], str(rs))

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL PASSED")
