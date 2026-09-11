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
check("merged_from records both GG cards + method", json.loads(luke[0]["merged_from"])["records"][0]["member_card_id"] == "904"
      and json.loads(luke[0]["merged_from"])["records"][1]["member_card_id"] == "905"
      and json.loads(luke[0]["merged_from"])["method"] == "sum")
check("merge list names the fold", len(merges) == 2 and merges[0]["member_card_ids"] == ["904", "905"], str(merges))
clean, m2 = db._merge_duplicate_standings([dict(r, customer_id=i) for i, r in enumerate(GG_ROWS[:3], 1)])
check("a clean race is untouched (GG ranks kept verbatim)", m2 == [] and [r["rank"] for r in clean] == ["1", "2", "T3"])

print("\n== 1b. best-N races re-derive over the union of events ==")
DETAIL = {
    "A": [{"date": f"2026-0{m}-01", "event": f"s9.{m}", "points": p} for m, p in
          zip(range(1, 10), [12, 11, 10, 9, 8, 7, 6, 5, 4])]
         + [{"date": "2026-08-15", "event": "TGF CHAMPIONSHIP", "points": 20}],   # 9 regular + champ
    "B": [{"date": "2026-05-12", "event": "s9.10", "points": 9},                  # beats A's 4
          {"date": "2026-05-19", "event": "s9.11", "points": 2}],
}
fetch = lambda card: DETAIL[card]
two = [{"rank": "1", "prev_rank": "", "player_name": "HOGUE, Jay", "customer_id": 37, "tournaments": 10,
        "wins": 0, "total_points": 92.0, "points_behind": 0, "member_card_id": "A"},
       {"rank": "9", "prev_rank": "", "player_name": "HOGUE, Jay", "customer_id": 37, "tournaments": 2,
        "wins": 0, "total_points": 11.0, "points_behind": 81, "member_card_id": "B"},
       {"rank": "2", "prev_rank": "", "player_name": "X, Y", "customer_id": 99, "tournaments": 3,
        "wins": 0, "total_points": 95.0, "points_behind": 0, "member_card_id": "C"}]
m10, mm = db._merge_duplicate_standings([dict(r) for r in two], race={"best_n": 10}, detail_fetcher=fetch)
h = [r for r in m10 if r["customer_id"] == 37][0]
check("best 10 + championship over the union: 11 regular events, the 2 drops → 81 + 20 = 101, not the 103 sum",
      h["total_points"] == 101.0 and mm[0]["method"] == "best_10", str((h["total_points"], mm)))
check("re-rank uses the derived total (101 beats 95)", h["rank"] == "1" and m10[1]["rank"] == "2")
m_fail, mf = db._merge_duplicate_standings([dict(r) for r in two], race={"best_n": 10},
                                           detail_fetcher=lambda c: (_ for _ in ()).throw(RuntimeError("gg down")))
check("detail unavailable → dominant record's total, never the sum",
      [r for r in m_fail if r["customer_id"] == 37][0]["total_points"] == 92.0 and mf[0]["method"] == "max", str(mf))
m_small, ms = db._merge_duplicate_standings([dict(r, tournaments=2) for r in two], race={"best_n": 10},
                                            detail_fetcher=fetch)
m_guard, mg = db._merge_duplicate_standings([dict(r) for r in two], race={"best_n": 10},
                                            detail_fetcher=lambda c: [{"date": "2026-01-01", "event": "x", "points": 1.0}])
check("derived total below the larger record's own total → guard keeps the record total",
      [r for r in m_guard if r["customer_id"] == 37][0]["total_points"] == 92.0 and mg[0]["method"] == "max(guard)", str(mg))
check("under N rounds combined → plain sum, no detail fetch", ms[0]["method"] == "sum"
      and [r for r in m_small if r["customer_id"] == 37][0]["total_points"] == 103.0)
check("same event under both records counts once (max)",
      db._best_n_total([{"date": "2026-05-12", "event": "s9.10", "points": 9},
                        {"date": "2026-05-12", "event": "s9.10", "points": 7}], 10) == 9.0)

print("\n== 1c. GG's real detail table (Hogue card 7124833, austin_net, 2026-09-11) ==")
REAL = {"tables": [[["Event", "Tournament", "Awarded Date", "Position", "Points"],
    ["TGF Austin 2026", "2026 Austin Championship - POINTS Net", "2026-08-01", "14", "24"],
    ["TGF Austin 2026", "a9.12 POINTS Net - AUSTIN Net", "2026-06-02", "T2", "12"],
    ["TGF Austin 2026", "a9.14 POINTS Net - AUSTIN Net", "2026-06-16", "T1", "11"],
    ["TGF Austin 2026", "a9.19 POINTS Net - AUSTIN Net", "2026-07-21", "3", "10"],
    ["2026 Hill Country Matches", "hcmR2 POINTS Net - AUSTIN Net", "2026-05-16", "T1", "10"],
    ["2026 Hill Country Matches", "hcmR1 POINTS Net - AUSTIN Net", "2026-05-16", "2", "9"],
    ["TGF Austin 2026", "a9.1 POINTS Net - AUSTIN Net", "2026-03-17", "T2", "9"],
    ["TGF Austin 2026", "a9.17 POINTS Net - AUSTIN Net", "2026-07-07", "1", "9"],
    ["TGF Austin 2026", "a9.7 POINTS Net - AUSTIN Net", "2026-04-28", "T4", "8"],
    ["TGF Austin 2026", "a9.13 POINTS Net - AUSTIN Net", "2026-06-09", "T12", "7"],
    ["TGF Austin 2026", "a9.15 POINTS Net - AUSTIN Net", "2026-06-23", "T6", "7"],
    ["The following points are not counted in standings"],
    ["TGF Austin 2026", "a9.2 POINTS Net - AUSTIN Net", "2026-03-24", "T7", "7"],
    ["TGF Austin 2026", "a9.9 POINTS Net - AUSTIN Net", "2026-05-12", "T5", "6"],
    ["TGF Austin 2026", "a9.3 POINTS Net - AUSTIN Net", "2026-03-31", "T8", "6"],
    ["TGF Austin 2026", "a9.8 POINTS Net - AUSTIN Net", "2026-05-05", "T6", "6"],
    ["TGF Austin 2026", "a9.16 POINTS Net - AUSTIN Net", "2026-06-30", "T9", "5"],
    ["TGF Austin 2026", "Kickoff POINTS Net - Front - AUSTIN Net", "2026-03-14", "T9", "4"],
    ["TGF Austin 2026", "a9.10 POINTS Net - AUSTIN Net", "2026-05-19", "T14", "4"],
    ["2026 Hill Country Matches", "hcmR3 POINTS Net - AUSTIN Net", "2026-05-16", "T5", "4"],
    ["TGF Austin 2026", "a9.4 POINTS Net - AUSTIN Net", "2026-04-07", "T8", "3"],
    ["TGF Austin 2026", "Kickoff POINTS Net - Back - AUSTIN Net", "2026-03-14", "T15", "3"]]]}
ev = db.parse_member_detail_events(REAL)
check("21 event lines, tournament column is the identity, separator honoured",
      len(ev) == 21 and ev[0]["event"].startswith("2026 Austin Championship") and ev[0]["counted"]
      and sum(1 for e in ev if e["counted"]) == 11 and not ev[-1]["counted"], str(ev[:2]))
check("best 10 + championship over ONE record reproduces GG's own 116",
      db._best_n_total(ev, 10) == 116.0, str(db._best_n_total(ev, 10)))
check("a second record with an 8 replaces a counted 7 → 117; with a 6 and a 2 → still 116",
      db._best_n_total(ev + [{"date": "2026-09-01", "event": "a9.21 POINTS Net", "points": 8.0}], 10) == 117.0
      and db._best_n_total(ev + [{"date": "2026-09-01", "event": "a9.21 POINTS Net", "points": 6.0},
                                 {"date": "2026-09-08", "event": "a9.22 POINTS Net", "points": 2.0}], 10) == 116.0)

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

print("\n== 2b. concluded races are never folded (Kerry 2026-09-11) ==")
n2 = db.refresh_points_race_standings("austin_net", db_path=p)
with db._connect(p) as conn:
    lk2 = conn.execute("SELECT COUNT(*), SUM(merged_from IS NOT NULL) FROM gg_points_standings "
                       "WHERE race_key='austin_net' AND customer_id=13").fetchone()
check("austin_net (concluded) keeps GG's rows verbatim: Luke twice, nothing folded",
      n2 == 9 and tuple(lk2) == (2, 0), str((n2, tuple(lk2))))
rep0 = db.find_points_race_duplicates(db_path=p)
check("the concluded double is reported, flagged report-only",
      any(u["race_key"] == "austin_net" and u["folding"] is False and "concluded" in u["note"] for u in rep0["unmerged"]),
      str(rep0["unmerged"]))
with db._connect(p) as conn:
    conn.execute("DELETE FROM gg_points_standings WHERE race_key='austin_net'"); conn.commit()

print("\n== 3. duplicates report ==")
rep = db.find_points_race_duplicates(db_path=p)
check("merged fold reported with both GG cards + method", len(rep["merged"]) == 2
      and any(m["player_name"] == "YOUNGS, Luke" and [g["member_card_id"] for g in m["gg_records"]] == ["904", "905"]
              and m["method"] == "sum" for m in rep["merged"]), str(rep["merged"]))
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

print("\n== 3b. folded row's detail combines every GG record ==")
T_A = [[["Event", "Tournament", "Awarded Date", "Position", "Points"],
        ["TGF Austin 2026", "a9.21 POINTS Net - AUSTIN Fall Net", "2026-09-01", "3", "9"],
        ["TGF Austin 2026", "a9.22 POINTS Net - AUSTIN Fall Net", "2026-09-08", "T2", "8"]]]
T_B = [[["Event", "Tournament", "Awarded Date", "Position", "Points"],
        ["TGF San Antonio 2026", "s18.10 POINTS Net - Back - AUSTIN Fall Net", "2026-08-29", "3", "11"],
        ["TGF San Antonio 2026", "s18.10 POINTS Net - Front - AUSTIN Fall Net", "2026-08-29", "T1", "9"],
        ["TGF Austin 2026", "a9.22 POINTS Net - AUSTIN Fall Net", "2026-09-08", "T2", "8"]]]   # shared line
comb = db.combine_member_detail_tables([T_A, T_B], 6)
check("one table: header + 4 distinct lines (shared a9.22 once), all counted under best 6, no separator",
      len(comb) == 5 and comb[0][1] == "Tournament" and [r[4] for r in comb[1:]] == ["11", "9", "9", "8"]
      and not any(len(r) == 1 for r in comb), str(comb))
comb3 = db.combine_member_detail_tables([T_A, T_B], 3)
check("best 3 → separator after three lines, the 8 below it",
      len(comb3) == 6 and len(comb3[4]) == 1 and "not counted" in comb3[4][0] and comb3[5][4] == "8", str(comb3))
champ = db.combine_member_detail_tables([[[["Event", "Tournament", "Awarded Date", "Position", "Points"],
        ["x", "2026 Austin Championship - POINTS Net", "2026-08-01", "14", "2"],
        ["x", "a9.1 POINTS Net", "2026-03-17", "T2", "9"], ["x", "a9.2 POINTS Net", "2026-03-24", "T7", "7"]]]], 1)
check("championship always counts, even at 2 pts", [r[4] for r in champ[1:3]] == ["2", "9"] and len(champ[3]) == 1, str(champ))
# the folded snapshot row fronts the dominant record's card and combines on read
with db._connect(p) as conn:
    card = conn.execute("SELECT member_card_id FROM gg_points_standings WHERE race_key='austin_fall_net' "
                        "AND customer_id=13").fetchone()[0]
check("folded row fronts the dominant record's card (904: same rounds, more points)", card == "904", card)
gg.fetch_points_race_member_detail = lambda page_id, member_card_id, league_id, host: {
    "member_card_id": member_card_id, "headings": [], "tables": T_A if member_card_id == "904" else T_B}
det = db.points_race_member_detail_combined("austin_fall_net", "904", db_path=p)
check("combined detail fetched both cards and rebuilt one table", det.get("combined") and det["cards"] == ["904", "905"]
      and len(det["tables"]) == 1 and len(det["tables"][0]) == 5, str(det.get("cards")))
det1 = db.points_race_member_detail_combined("austin_fall_net", "901", db_path=p)
check("a plain row passes GG's detail through", not det1.get("combined") and det1["cards"] == ["901"])

print("\n== 3c. member caps + customer duplicate report ==")
check("member caps follows GG's shape",
      db.member_caps_name("Espinosa, Christopher") == "ESPINOSA, Christopher"
      and db.member_caps_name("McCrary, Justin") == "McCRARY, Justin"
      and db.member_caps_name("DelCarmen, Michelle") == "DelCARMEN, Michelle"
      and db.member_caps_name("YOUNGS, Luke") == "YOUNGS, Luke"
      and db.member_caps_name("Williams, Jacob GUEST") == "WILLIAMS, Jacob GUEST"
      and db.member_caps_name("Kerry Niester") == "Kerry Niester",
      str([db.member_caps_name(x) for x in ("Espinosa, Christopher", "McCrary, Justin", "DelCarmen, Michelle")]))
with db._connect(p) as conn:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS customer_emails (email_id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER,
            email TEXT, is_primary INTEGER DEFAULT 0, is_golf_genius INTEGER DEFAULT 0, label TEXT);
        CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, customer TEXT,
            customer_email TEXT, customer_phone TEXT, order_date TEXT, transaction_status TEXT);
        ALTER TABLE customers ADD COLUMN phone TEXT;
        ALTER TABLE customers ADD COLUMN created_at TEXT;
        INSERT INTO customers (customer_id, first_name, last_name, chapter, current_player_status, phone)
            VALUES (801, 'Chris', 'Espinosa', 'San Antonio', 'guest', '(210) 555-0101'),
                   (802, 'Christopher', 'Espinosa', 'San Antonio', 'active_member', '210-555-0101'),
                   (803, 'Luke', 'Youngs', 'San Antonio', 'expired_member', NULL),
                   (804, 'Sam', 'Jones', NULL, 'guest', NULL), (805, 'Sam', 'Jones', NULL, 'guest', NULL);
        INSERT INTO customer_emails (customer_id, email) VALUES (801, 'chris@x.com'), (802, 'Chris@X.com');
        INSERT INTO items (customer_id, customer, customer_email, order_date) VALUES
            (802, 'Christopher Espinosa', 'chris@x.com', '2026-09-06'), (801, 'Chris Espinosa', 'chris@x.com', '2026-05-01');
    """)
    conn.commit()
rep = db.find_customer_duplicates(db_path=p)
keys = {g["key"] for g in rep["same_email"]} | {g["key"] for g in rep["same_phone"]} | {g["key"] for g in rep["same_name"]}
check("email door finds Chris/Christopher Espinosa (the phone door sees the same pair, reported once); "
      "the two Luke Youngs (13 and 803) and the Sam Joneses by name",
      "chris@x.com" in keys and "2105550101" not in keys and "Sam Jones" in keys and "Luke Youngs" in keys, str(keys))
esp = next(g for g in rep["same_email"] if g["key"] == "chris@x.com")
check("suggest_keep = the active member with the items", esp["suggest_keep"] == 802
      and {pr["customer_id"] for pr in esp["profiles"]} == {801, 802}, str(esp))
check("a group is reported once even when two doors find it",
      sum(1 for b in ("same_name", "same_email", "same_phone") for g in rep[b]
          if {pr["customer_id"] for pr in g["profiles"]} == {801, 802}) == 1)

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
