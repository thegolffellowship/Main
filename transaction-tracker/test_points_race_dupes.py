"""One person = one row on the Season Contests boards (v2.371.5).

Kerry 2026-09-11, Austin Fall Net: "Why is there two Luke Youngs showing?"
GG carried two member records for him (T3 20 pts / 2 rounds and 5th
17 pts / 2 rounds); the snapshot mirrored the page row for row.

  - _merge_duplicate_standings folds rows that resolve to one customer
    (or one unresolved name), re-ranks GG-style, recomputes behind.
  - refresh_points_race_standings applies it at write time + audits.
  - find_points_race_duplicates reports folded rows, anything still
    doubled, and duplicate enrollments.
  - the scraper keeps BOTH member_card_ids when a name repeats.

Run: python3 test_points_race_dupes.py
"""

import json
import os
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402
import golf_genius_sync as gg  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


GG_ROWS = [
    {"rank": "1", "prev_rank": "1", "player_name": "STRAITON, Robert", "affiliation": "TGF Austin",
     "tournaments": 4, "wins": 1, "total_points": 33.0, "points_behind": 0.0, "member_card_id": "901"},
    {"rank": "2", "prev_rank": "3", "player_name": "WADE, John", "affiliation": "TGF Austin",
     "tournaments": 4, "wins": 0, "total_points": 32.0, "points_behind": 1.0, "member_card_id": "902"},
    {"rank": "T3", "prev_rank": "T3", "player_name": "MCCORMICK, Sam", "affiliation": "TGF Austin",
     "tournaments": 2, "wins": 0, "total_points": 20.0, "points_behind": 13.0, "member_card_id": "903"},
    {"rank": "T3", "prev_rank": "T3", "player_name": "YOUNGS, Luke", "affiliation": "TGF Austin",
     "tournaments": 2, "wins": 1, "total_points": 20.0, "points_behind": 13.0, "member_card_id": "904"},
    {"rank": "5", "prev_rank": "13", "player_name": "YOUNGS, Luke", "affiliation": "TGF Austin",
     "tournaments": 2, "wins": 0, "total_points": 17.0, "points_behind": 16.0, "member_card_id": "905"},
    {"rank": "T6", "prev_rank": "5", "player_name": "CHESHIRE, Neil", "affiliation": "TGF Austin",
     "tournaments": 2, "wins": 0, "total_points": 14.0, "points_behind": 19.0, "member_card_id": "906"},
    {"rank": "T6", "prev_rank": "5", "player_name": "HOGUE, Jay", "affiliation": "TGF Austin",
     "tournaments": 2, "wins": 0, "total_points": 14.0, "points_behind": 19.0, "member_card_id": "907"},
    {"rank": "8", "prev_rank": "", "player_name": "Mystery, Guest", "affiliation": "",
     "tournaments": 1, "wins": 0, "total_points": 5.0, "points_behind": 28.0, "member_card_id": "908"},
    {"rank": "9", "prev_rank": "", "player_name": "Mystery,  Guest", "affiliation": "",
     "tournaments": 1, "wins": 0, "total_points": 3.0, "points_behind": 30.0, "member_card_id": "909"},
]
CIDS = {"STRAITON, Robert": 31, "WADE, John": 4, "MCCORMICK, Sam": 700, "YOUNGS, Luke": 13,
        "CHESHIRE, Neil": 701, "HOGUE, Jay": 702}


def fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    with db._connect(p) as conn:
        conn.executescript("""
            CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT,
                chapter TEXT, current_player_status TEXT);
            CREATE TABLE season_contests (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER,
                customer_name TEXT, contest_type TEXT, chapter TEXT, season TEXT, source_item_id INTEGER,
                enrolled_at TEXT, cup_only INTEGER DEFAULT 0);
            CREATE TABLE agent_action_log (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_name TEXT,
                action_type TEXT, description TEXT, source_email_uid TEXT, related_item_id INTEGER,
                outcome TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO customers VALUES (13, 'Luke', 'Youngs', 'Austin', 'active_member');
            INSERT INTO customers VALUES (4, 'John', 'Wade', 'Austin', 'active_member');
            INSERT INTO season_contests (customer_id, customer_name, contest_type, chapter, season)
                VALUES (4, 'John Wade', 'NET Points Race', 'Austin', '2026 Fall'),
                       (4, 'John Wade', 'NET Points Race', 'Austin', '2026 Fall'),
                       (13, 'Luke Youngs', 'NET Points Race', 'Austin', '2026');
        """)
        db._ensure_gg_points_table(conn)
        conn.commit()
    return p


db._resolve_gg_person = lambda conn, name, capture_alias=True: (CIDS.get(name), "test")
gg.fetch_season_points_race = lambda page_id, league_id, host: [dict(r) for r in GG_ROWS]

print("\n== 1. merge: pure function ==")
merged, merges = db._merge_duplicate_standings([dict(r) for r in GG_ROWS[:7]] and
                                               [dict(r, customer_id=CIDS.get(r["player_name"])) for r in GG_ROWS])
by_name = {}
for r in merged:
    by_name.setdefault(r["player_name"].strip().lower().replace("  ", " "), []).append(r)
luke = [r for r in merged if r["player_name"] == "YOUNGS, Luke"]
check("two Luke rows become one", len(luke) == 1, str(len(luke)))
check("points, rounds and wins summed", luke[0]["total_points"] == 37.0 and luke[0]["tournaments"] == 4
      and luke[0]["wins"] == 1, str(luke[0]))
check("field re-ranked: Luke leads, Straiton 2nd, Wade 3rd",
      luke[0]["rank"] == "1" and [r["rank"] for r in merged[:3]] == ["1", "2", "3"], str([(r["player_name"], r["rank"]) for r in merged]))
check("ties keep GG's T prefix", [r["rank"] for r in merged if r["total_points"] == 14.0] == ["T5", "T5"],
      str([(r["player_name"], r["rank"]) for r in merged]))
check("behind recomputed from the new leader", luke[0]["points_behind"] == 0.0
      and [r for r in merged if r["player_name"] == "STRAITON, Robert"][0]["points_behind"] == 4.0)
check("unresolved twins fold on the normalised name", sum(1 for r in merged if "mystery" in r["player_name"].lower()) == 1
      and [r for r in merged if "mystery" in r["player_name"].lower()][0]["total_points"] == 8.0)
check("merged_from records both GG cards", json.loads(luke[0]["merged_from"])[0]["member_card_id"] == "904"
      and json.loads(luke[0]["merged_from"])[1]["member_card_id"] == "905")
check("merge list names the fold", len(merges) == 2 and merges[0]["member_card_ids"] == ["904", "905"], str(merges))
clean, m2 = db._merge_duplicate_standings([dict(r, customer_id=i) for i, r in enumerate(GG_ROWS[:3], 1)])
check("a clean race is untouched (GG ranks kept verbatim)", m2 == [] and [r["rank"] for r in clean] == ["1", "2", "T3"])

print("\n== 2. refresh writes the folded snapshot ==")
p = fresh_db()
n = db.refresh_points_race_standings("austin_fall_net", db_path=p)
with db._connect(p) as conn:
    rows = [dict(r) for r in conn.execute(
        "SELECT rank, player_name, customer_id, tournaments, total_points, merged_from "
        "FROM gg_points_standings WHERE race_key='austin_fall_net' ORDER BY id")]
    audit = conn.execute("SELECT description FROM agent_action_log WHERE action_type='standings-duplicate-merge'").fetchone()
check("9 GG rows → 7 stored", n == 7 and len(rows) == 7, str((n, len(rows))))
lk = [r for r in rows if r["customer_id"] == 13]
check("Luke once, 37 pts, rank 1, merged_from set", len(lk) == 1 and lk[0]["total_points"] == 37.0
      and lk[0]["rank"] == "1" and lk[0]["merged_from"], str(lk))
check("audit row written", audit and "YOUNGS, Luke x2" in audit[0], str(audit))

print("\n== 3. duplicates report ==")
rep = db.find_points_race_duplicates(db_path=p)
check("merged fold reported with both GG cards", len(rep["merged"]) == 2
      and any(m["player_name"] == "YOUNGS, Luke" and [g["member_card_id"] for g in m["gg_records"]] == ["904", "905"]
              for m in rep["merged"]), str(rep["merged"]))
check("nothing left doubled in the snapshot", rep["unmerged"] == [], str(rep["unmerged"]))
check("duplicate enrollment (Wade x2, 2026 Fall) reported; Luke's single 2026 entry is not",
      len(rep["enrollment_dupes"]) == 1 and rep["enrollment_dupes"][0]["customer_id"] == 4
      and rep["enrollment_dupes"][0]["n"] == 2, str(rep["enrollment_dupes"]))
with db._connect(p) as conn:   # a legacy snapshot that was never folded
    conn.execute("INSERT INTO gg_points_standings (race_key, rank, player_name, customer_id, total_points) "
                 "VALUES ('austin_net','4','YOUNGS, Luke',13,10), ('austin_net','9','YOUNGS, Luke',13,4)")
    conn.commit()
rep = db.find_points_race_duplicates(db_path=p)
check("pre-merge doubles are reported as unmerged", len(rep["unmerged"]) == 1
      and rep["unmerged"][0]["race_key"] == "austin_net" and len(rep["unmerged"][0]["rows"]) == 2, str(rep["unmerged"]))

print("\n== 4. scraper keeps both member card ids for a repeated name ==")
html = ('<a data-member-card-id="904" class="x"> YOUNGS, Luke </a>'
        '<a data-member-card-id="903" class="x">MCCORMICK, Sam</a>'
        '<a data-member-card-id="905" class="x">YOUNGS, Luke</a>')
q = gg._card_ids_by_name_ordered(html)
check("ids queued in page order per name", q == {"YOUNGS, Luke": ["904", "905"], "MCCORMICK, Sam": ["903"]}, str(q))

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL PASSED")
