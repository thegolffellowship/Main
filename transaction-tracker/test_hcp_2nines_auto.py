"""The per-nine ratings for an 18-hole posting come off the COURSE RECORD.

Kerry 2026-09-19, after Cedar Creek s18.11 was asked for its front/back
ratings twice: "Aren't we checking course_ids and their information for
course info for ratings and indexes as a standard?"

v2.466.0 (mailbox #576): the record is the USGA/WHS shape. An 18-hole tee
set carries its FRONT and BACK rating rows (each with its own slope) in
tee_set_ratings; `resolve_per_nine_from_course_tees` reads those first
and only falls back to pairing the course's Tuesday nine-hole rows of the
same tee name and gender when a set has none. `store_tee_nines` writes
rating rows, so identical halves (Forest Creek White, 35.2/125 both ways)
are simply two rows. `derive_18hole_rounds_as_two_nines` reads the map by
default and a hand-passed map only overrides it.

Run: python3 test_hcp_2nines_auto.py
"""
import os, sys, tempfile, logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.WARNING)
from email_parser import database as db                          # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

with db._connect(DB) as conn:
    # The OLD shape on disk, exactly as a live DB had it before v2.466.0:
    # the migration must rebuild it in place.
    conn.executescript("""
        CREATE TABLE course_tees (tee_id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER,
            tee_name TEXT, slope INTEGER, rating REAL, yardage_total INTEGER,
            created_at TEXT, UNIQUE(course_id, tee_name, slope, rating));
        CREATE TABLE course_tee_holes (tee_id INTEGER, hole_number INTEGER,
            par INTEGER, yardage INTEGER, stroke_index INTEGER, PRIMARY KEY (tee_id, hole_number));
        CREATE TABLE courses (course_id INTEGER PRIMARY KEY, name TEXT, status TEXT);
        CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT, nine_side TEXT,
            course_id INTEGER, event_date TEXT);
        CREATE TABLE scoring_rounds (id INTEGER PRIMARY KEY, tee_id INTEGER,
            course_id INTEGER, event_id INTEGER, customer_id INTEGER, player_name TEXT,
            gg_aggregate_id TEXT, gg_round_id TEXT, round_date TEXT);
        CREATE TABLE handicap_rounds (id INTEGER PRIMARY KEY, nine TEXT,
            scoring_round_id INTEGER);
        CREATE TABLE agent_action_log (id INTEGER PRIMARY KEY, agent TEXT, action TEXT,
            detail TEXT, created_at TEXT);
    """)
    conn.execute("INSERT INTO courses VALUES (35670, 'Cedar Creek Golf Course', 'active')")
    # Cedar Creek as the course record held it on 2026-09-19: an 18-hole
    # row per tee plus the Tuesday nine-hole rows (front 3236 / back 3271
    # yards on the White). Numbers are the real ones.
    tees = [
        (717, "1 - White Tee", 71.4, 125, 6507),
        (4433, "1 - White Tee", 35.5, 126, 3236),
        (2971, "1 - White Tee", 35.9, 123, 3271),
        (711, "2 - Gold Tee", 69.4, 118, 6025),
        (4436, "2 - Gold Tee", 34.8, 116, 3035),
        (2973, "2 - Gold Tee", 34.6, 119, 2990),
        (710, "3 - Red (L) Tee", 72.9, 120, 5439),
        (2441, "3 - Red (L) Tee", 36.4, 124, 2709),
        (2978, "3 - Red (L) Tee", 36.5, 116, 2730),
        # A tee with an 18-hole row but NO nines on file: must stay unresolved.
        (2975, "0 - Blue Tee", 74.0, 139, 6800),
    ]
    for tid, nm, rt, sl, y in tees:
        conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, rating, slope, yardage_total) "
                     "VALUES (?, 35670, ?, ?, ?, ?)", (tid, nm, rt, sl, y))
    # Hole yardages for the 18-hole rows so the labeller can match halves.
    white_f = [362, 406, 327, 494, 159, 372, 180, 390, 546]
    white_b = [387, 329, 388, 373, 487, 347, 371, 200, 389]
    gold_f = [344, 380, 304, 469, 137, 346, 156, 368, 531]
    gold_b = [357, 304, 358, 347, 449, 321, 345, 185, 324]
    red_f = [301, 324, 279, 442, 119, 322, 133, 309, 480]
    red_b = [312, 272, 334, 313, 429, 300, 297, 172, 301]
    for full, nines in ((717, (white_f, white_b)), (711, (gold_f, gold_b)), (710, (red_f, red_b))):
        for i, y in enumerate(nines[0] + nines[1], start=1):
            conn.execute("INSERT INTO course_tee_holes VALUES (?, ?, 4, ?, ?)", (full, i, y, i))
    for tid, ys in ((4433, white_f), (2971, white_b), (4436, gold_f),
                    (2973, gold_b), (2441, red_f), (2978, red_b)):
        for i, y in enumerate(ys, start=1):
            conn.execute("INSERT INTO course_tee_holes VALUES (?, ?, 4, ?, ?)", (tid, i, y, i))
    conn.commit()
    mig = db._migrate_course_tees_v2(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(course_tees)")}
    print("The rebuild (mailbox #576)")
    check("an old-shape table is rebuilt in place, every row kept",
          mig["rebuilt"] and mig["rows"] == 10 and mig["dropped"] == 0, mig)
    check("…with the USGA/WHS columns",
          {"gender", "holes", "nine", "par", "bogey_rating", "is_combo", "gg_tee_id",
           "usga_tee_label", "source"} <= cols, sorted(cols))
    g = {r[0]: (r[1], r[2], r[3]) for r in conn.execute(
        "SELECT tee_id, gender, holes, nine FROM course_tees")}
    check("the (L) tee became gender F; 18-hole rows are holes 18 / nine 'full'; nines are holes 9",
          g[710] == ("F", 18, "full") and g[2441][:2] == ("F", 9) and g[717] == ("M", 18, "full")
          and g[4433][:2] == ("M", 9), g)
    check("tee ids are unchanged — every scoring_rounds.tee_id still points home",
          sorted(g) == sorted(t[0] for t in tees), sorted(g))
    check("every set got its TOTAL rating row",
          conn.execute("SELECT COUNT(*) FROM tee_set_ratings WHERE rating_type = 'total'")
          .fetchone()[0] == 10)
    check("running the migration again is a no-op",
          db._migrate_course_tees_v2(conn)["rebuilt"] is False)
    res = db.resolve_per_nine_from_course_tees(conn, 35670)

pn = res["per_nine"]
print("Cedar Creek, ratings off the course record")
check("White 717: front 35.5/126, back 35.9/123 (paired from the Tuesday rows)",
      pn.get(717) == {"front": (35.5, 126), "back": (35.9, 123)}, pn.get(717))
check("Gold 711: front 34.8/116, back 34.6/119",
      pn.get(711) == {"front": (34.8, 116), "back": (34.6, 119)}, pn.get(711))
check("Red (L) 710: front 36.4/124, back 36.5/116 — paired within gender F",
      pn.get(710) == {"front": (36.4, 124), "back": (36.5, 116)}, pn.get(710))
check("each pair is corroborated against the 18-hole rating and says how",
      all("vs" in d["check"] and d["how"] == "paired nine-hole rows" for d in res["derivation"])
      and len(res["derivation"]) == 3, res["derivation"])
check("Blue 2975, no rating rows and no nines on file, is UNRESOLVED and says why",
      any(u["tee_id"] == 2975 and "no front/back rating rows" in u["why"] for u in res["unresolved"]),
      res["unresolved"])
check("…and is NOT in the map (never guessed)", 2975 not in pn, sorted(pn))

# The posting path reads the same map when none is passed, and a passed
# map overrides per tee.
import inspect
src = inspect.getsource(db.derive_18hole_rounds_as_two_nines)
check("derive_18hole_rounds_as_two_nines resolves from the course record by default",
      "resolve_per_nine_from_course_tees" in src and "per_nine_source" in src)
check("an explicit map is merged OVER the resolved one",
      "{**resolved, **{int(k): v for k, v in (per_nine or {}).items()}}" in src)

# ---- store_tee_nines: rating rows ON the 18-hole set ----
print("store_tee_nines writes rating rows")
with db._connect(DB) as conn:
    bad = db.store_tee_nines(conn, 2975, (37.3, 139), (36.0, 135), dry_run=True)
    check("a pair that does not sum to the 18 is REFUSED", bad["ok"] is False and "not storing" in bad["error"], bad)
    nine_row = db.store_tee_nines(conn, 4433, (17.0, 100), (18.5, 100), dry_run=True)
    check("a nine-hole set is refused as the target", nine_row["ok"] is False, nine_row)
    dry = db.store_tee_nines(conn, 2975, (37.3, 139), (36.7, 135), dry_run=True)
    n_rows = lambda: conn.execute("SELECT COUNT(*) FROM tee_set_ratings WHERE tee_id = 2975").fetchone()[0]
    check("dry run plans two rating rows and writes nothing",
          dry["ok"] and [r["action"] for r in dry["rows"]] == ["would insert", "would insert"]
          and n_rows() == 1, dry)
    done = db.store_tee_nines(conn, 2975, (37.3, 139), (36.7, 135), dry_run=False, bogey=101.2)
    check("apply writes front + back rating rows (each with its own slope) and the bogey",
          done["ok"] and n_rows() == 3
          and conn.execute("SELECT slope FROM tee_set_ratings WHERE tee_id = 2975 AND rating_type = 'back'")
          .fetchone()[0] == 135
          and conn.execute("SELECT bogey_rating FROM course_tees WHERE tee_id = 2975").fetchone()[0] == 101.2, done)
    check("no sibling nine-hole rows were created",
          conn.execute("SELECT COUNT(*) FROM course_tees WHERE course_id = 35670").fetchone()[0] == 10)
    again = db.store_tee_nines(conn, 2975, (37.3, 139), (36.7, 135), dry_run=False)
    check("a second apply keeps the rows, never duplicates",
          all("kept" in r["action"] for r in again["rows"]) and n_rows() == 3, again)
    res2 = db.resolve_per_nine_from_course_tees(conn, 35670)
    check("…and the resolver now resolves Blue from the rating rows",
          res2["per_nine"].get(2975) == {"front": (37.3, 139), "back": (36.7, 135)}
          and next(d for d in res2["derivation"] if d["tee_id"] == 2975)["how"] == "tee_set_ratings",
          res2["per_nine"].get(2975))
    # Identical halves (Forest Creek White is 35.2/125 both ways): two
    # rating rows on one set. No natural-key clash, nothing blocked.
    conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, gender, holes, nine, rating, slope, yardage_total) "
                 "VALUES (9001, 35670, '5 - Twin Tee', 'M', 18, 'full', 70.4, 125, 6400)")
    conn.commit()
    twin = db.store_tee_nines(conn, 9001, (35.2, 125), (35.2, 125), dry_run=False)
    check("identical halves are two rating rows on one set — the v2.465 BLOCK is gone",
          twin["ok"] and [r["action"] for r in twin["rows"]] == ["inserted", "inserted"]
          and db.resolve_per_nine_from_course_tees(conn, 35670)["per_nine"].get(9001)
          == {"front": (35.2, 125), "back": (35.2, 125)}, twin)
    # A men's and a women's set share a name under the new key.
    conn.execute("INSERT INTO course_tees (course_id, tee_name, gender, holes, nine, rating, slope) "
                 "VALUES (35670, '5 - Twin Tee', 'F', 18, 'full', 75.6, 138)")
    conn.commit()
    check("a women's set with the same tee name coexists (gender is in the key)",
          conn.execute("SELECT COUNT(*) FROM course_tees WHERE tee_name = '5 - Twin Tee'").fetchone()[0] == 2)
    conn.execute("INSERT INTO events (id, item_name, course_id, event_date) VALUES (1, 's18.99 CEDAR CREEK', 35670, '2099-01-01')")
    conn.commit()
    audit = db.audit_course_per_nine(conn)
    c0 = audit["courses"][0]
    check("the audit lists the course with its next event, the resolved sets and the women's Twin set unresolved",
          c0["course_id"] == 35670 and c0["next_event"] == 's18.99 CEDAR CREEK'
          and len(c0["resolved"]) == 5
          and [u["tee_name"] + "/" + u["gender"] for u in c0["unresolved"]] == ["5 - Twin Tee/F"], c0)

# ---- the USGA CRDB seed ----
print("USGA CRDB seed")
with db._connect(DB) as conn:
    conn.execute("INSERT INTO courses (course_id, name, status) VALUES (29522, 'Forest Creek Golf Club', 'active')")
    # The record as the audit found it on 2026-09-19: three 18-hole rows
    # (Red (L) is the women's Red) and the Austin-Tuesday front rows.
    for tid, nm, rt, sl in ((3447, "1 - Blue Tee", 72.2, 132), (3448, "2 - White Tee", 70.4, 125),
                            (3462, "4 - Red (L) Tee", 68.5, 121), (3510, "1 - Blue Tee", 35.9, 133),
                            (3509, "2 - White Tee", 35.2, 125), (3511, "4 - Red (L) Tee", 34.1, 121)):
        conn.execute("INSERT INTO course_tees (tee_id, course_id, tee_name, gender, holes, nine, rating, slope) "
                     "VALUES (?, 29522, ?, ?, ?, ?, ?, ?)",
                     (tid, nm, "F" if "(L)" in nm else "M", 18 if rt >= 50 else 9,
                      "full" if rt >= 50 else "front", rt, sl))
    conn.commit()
    dry = db.seed_usga_crdb(conn, 29522, dry_run=True)
    acts = {(s["name"], s["gender"]): s["action"] for s in dry["sets"]}
    check("Blue M / White M match their rows by gender + rating/slope",
          acts[("Blue", "M")].startswith("matched by gender") and acts[("White", "M")].startswith("matched by gender"), acts)
    check("Red F matches the '(L)' row — gender is a rating dimension, not a name",
          acts[("Red", "F")].startswith("matched by gender")
          and next(s for s in dry["sets"] if s["name"] == "Red" and s["gender"] == "F")["tee_id"] == 3462, acts)
    check("the four sets with no row would be inserted (Green M, Red M, White F, Green F)",
          sorted(k for k, v in acts.items() if v == "would insert")
          == [("Green", "F"), ("Green", "M"), ("Red", "M"), ("White", "F")], acts)
    check("dry run wrote nothing",
          conn.execute("SELECT COUNT(*) FROM course_tees WHERE course_id = 29522").fetchone()[0] == 6)
    done = db.seed_usga_crdb(conn, 29522, dry_run=False)
    check("apply: 10 tee sets on the record, 7 with front/back rating rows from the CRDB",
          conn.execute("SELECT COUNT(*) FROM course_tees WHERE course_id = 29522").fetchone()[0] == 10
          and conn.execute("""SELECT COUNT(*) FROM tee_set_ratings r JOIN course_tees ct ON ct.tee_id = r.tee_id
                              WHERE ct.course_id = 29522 AND r.rating_type = 'front' AND r.source = 'usga_crdb'""")
          .fetchone()[0] == 7, done)
    r = db.resolve_per_nine_from_course_tees(conn, 29522)
    check("Forest Creek White M resolves 35.2/125 + 35.2/125 off the rating rows (identical halves)",
          r["per_nine"].get(3448) == {"front": (35.2, 125), "back": (35.2, 125)}, r["per_nine"].get(3448))
    check("…and every 18-hole set of the course resolves, none unresolved",
          len(r["per_nine"]) == 7 and r["unresolved"] == [], r["unresolved"])
    bogey = conn.execute("SELECT bogey_rating FROM course_tees WHERE tee_id = 3447").fetchone()[0]
    check("bogey rating stored on the set (used by nothing, kept for completeness)", bogey == 96.8, bogey)
    par = conn.execute("SELECT par, usga_tee_label, is_combo FROM course_tees WHERE tee_id = 3447").fetchone()
    check("par and the CRDB tee name recorded", tuple(par) == (72, "Blue", 0), tuple(par))
    again = db.seed_usga_crdb(conn, 29522, dry_run=False)
    check("re-seeding matches every set and inserts nothing",
          all(s["action"].startswith("matched") for s in again["sets"])
          and conn.execute("SELECT COUNT(*) FROM course_tees WHERE course_id = 29522").fetchone()[0] == 10, again)
    unknown = db.seed_usga_crdb(conn, 1, dry_run=True)
    check("a course with no seed says so and lists the known ones", unknown["ok"] is False and 22362 in unknown["known"])
    # The import writer (GG scorecards) dedupes on the new key and sets gender/holes.
    cid, tid = db._upsert_course_tee(conn, {"course": "Forest Creek Golf Club", "tee_name": "2 - White Tee",
                                            "rating": 70.4, "slope": 125, "yardage": {}})
    check("the scorecard import reuses the existing men's White row", (cid, tid) == (29522, 3448), (cid, tid))
    # A CRDB-seeded set is named the USGA way ("White"); the same set arrives
    # from Golf Genius as "2 - White (L) Tee" — ONE row, GG's name adopted.
    n_before = conn.execute("SELECT COUNT(*) FROM course_tees WHERE course_id = 29522").fetchone()[0]
    cid, tid2 = db._upsert_course_tee(conn, {"course": "Forest Creek Golf Club", "tee_name": "2 - White (L) Tee",
                                             "rating": 75.6, "slope": 138, "yardage": {}})
    row = conn.execute("SELECT tee_name, usga_tee_label, gender, holes, nine, source FROM course_tees WHERE tee_id = ?",
                       (tid2,)).fetchone()
    n_after = conn.execute("SELECT COUNT(*) FROM course_tees WHERE course_id = 29522").fetchone()[0]
    check("the GG import ADOPTS the CRDB-seeded women's White: renamed to GG's name, label kept, no new row",
          tuple(row) == ("2 - White (L) Tee", "White", "F", 18, "full", "usga_crdb") and n_after == n_before,
          (tuple(row), n_before, n_after))
    cid, tid3 = db._upsert_course_tee(conn, {"course": "Forest Creek Golf Club", "tee_name": "2 - White (L) Tee",
                                             "rating": 75.6, "slope": 138, "yardage": {}})
    check("and a second import of it hits the exact name", tid3 == tid2, (tid2, tid3))
    cid, tid4 = db._upsert_course_tee(conn, {"course": "Forest Creek Golf Club", "tee_name": "5 - Gold (L) Tee",
                                             "rating": 77.0, "slope": 140, "yardage": {}})
    row = conn.execute("SELECT gender, holes, nine, source FROM course_tees WHERE tee_id = ?", (tid4,)).fetchone()
    check("a women's tee the CRDB did not carry imports as gender F, holes 18, nine 'full', source import",
          tuple(row) == ("F", 18, "full", "import") and tid4 not in (tid2, 3448), tuple(row))
    # The course card does the same for its 18-hole row (Green M 68.5/120 was
    # CRDB-inserted as "Green"; the card calls it "3 - Green Tee").
    conn.commit()
    card = db.import_course_card("29522", dry_run=False, db_path=DB)
    green = [r for r in card["rows"] if r["tee_name"] == "3 - Green Tee" and r["nine"] == "full"]
    green_rows = conn.execute("SELECT COUNT(*) FROM course_tees WHERE course_id = 29522 AND gender = 'M' "
                              "AND holes = 18 AND rating = 68.5 AND slope = 120").fetchone()[0]
    check("the course card adopts the CRDB Green set instead of inserting a second one",
          green and green[0]["action"].startswith("existing") and green_rows == 1, (green, green_rows))

print()
print("ALL PASS" if not F else f"FAILED: {F}")
sys.exit(1 if F else 0)
