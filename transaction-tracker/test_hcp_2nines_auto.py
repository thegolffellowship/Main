"""The per-nine ratings for an 18-hole posting come off the COURSE RECORD.

Kerry 2026-09-19, after Cedar Creek s18.11 was asked for its front/back
ratings twice: "Aren't we checking course_ids and their information for
course info for ratings and indexes as a standard?"

Golf Genius files each Tuesday nine as its own course_tees row (same tee
name, rating under 50), so a course TGF plays on Tuesdays already carries
front and back ratings beside its 18-hole row. `resolve_per_nine_from_
course_tees` pairs them per tee and accepts a pair only when front + back
equals the 18-hole rating; `derive_18hole_rounds_as_two_nines` reads that
map by default and a hand-passed map only overrides it.

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
    conn.executescript("""
        CREATE TABLE course_tees (tee_id INTEGER PRIMARY KEY, course_id INTEGER,
            tee_name TEXT, rating REAL, slope INTEGER, yardage_total INTEGER);
        CREATE TABLE course_tee_holes (tee_id INTEGER, hole_number INTEGER,
            yardage INTEGER, par INTEGER, stroke_index INTEGER);
        CREATE TABLE events (id INTEGER PRIMARY KEY, item_name TEXT, nine_side TEXT);
        CREATE TABLE scoring_rounds (id INTEGER PRIMARY KEY, tee_id INTEGER,
            course_id INTEGER, event_id INTEGER);
        CREATE TABLE handicap_rounds (id INTEGER PRIMARY KEY, nine TEXT,
            scoring_round_id INTEGER);
    """)
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
        conn.execute("INSERT INTO course_tees VALUES (?, 35670, ?, ?, ?, ?)", (tid, nm, rt, sl, y))
    # Hole yardages for the 18-hole rows so the labeller can match halves.
    white_f = [362, 406, 327, 494, 159, 372, 180, 390, 546]
    white_b = [387, 329, 388, 373, 487, 347, 371, 200, 389]
    gold_f = [344, 380, 304, 469, 137, 346, 156, 368, 531]
    gold_b = [357, 304, 358, 347, 449, 321, 345, 185, 324]
    red_f = [301, 324, 279, 442, 119, 322, 133, 309, 480]
    red_b = [312, 272, 334, 313, 429, 300, 297, 172, 301]
    for full, nines in ((717, (white_f, white_b)), (711, (gold_f, gold_b)), (710, (red_f, red_b))):
        for i, y in enumerate(nines[0] + nines[1], start=1):
            conn.execute("INSERT INTO course_tee_holes VALUES (?, ?, ?, 4, ?)", (full, i, y, i))
    for tid, ys in ((4433, white_f), (2971, white_b), (4436, gold_f),
                    (2973, gold_b), (2441, red_f), (2978, red_b)):
        for i, y in enumerate(ys, start=1):
            conn.execute("INSERT INTO course_tee_holes VALUES (?, ?, ?, 4, ?)", (tid, i, y, i))
    conn.commit()
    res = db.resolve_per_nine_from_course_tees(conn, 35670)

pn = res["per_nine"]
print("Cedar Creek, ratings off the course record")
check("White 717: front 35.5/126, back 35.9/123",
      pn.get(717) == {"front": (35.5, 126), "back": (35.9, 123)}, pn.get(717))
check("Gold 711: front 34.8/116, back 34.6/119",
      pn.get(711) == {"front": (34.8, 116), "back": (34.6, 119)}, pn.get(711))
check("Red (L) 710: front 36.4/124, back 36.5/116",
      pn.get(710) == {"front": (36.4, 124), "back": (36.5, 116)}, pn.get(710))
check("each pair is corroborated against the 18-hole rating",
      all("vs" in d["check"] for d in res["derivation"]) and len(res["derivation"]) == 3,
      res["derivation"])
check("Blue 2975, no nines on file, is UNRESOLVED and says why",
      any(u["tee_id"] == 2975 and "no front+back pair" in u["why"] for u in res["unresolved"]),
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

print()
print("ALL PASS" if not F else f"FAILED: {F}")
sys.exit(1 if F else 0)
