"""Course-card entry (CA #786 GO 3): a card typed in once writes the same
tables the Golf Genius import writes, is validated whole before any write,
dry-runs by default, and re-loads in place.

Run: python3 test_course_card.py
"""

import os
import sqlite3
import sys
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")

FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label
          + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILURES.append(label)


PAR = {str(h): p for h, p in zip(range(1, 19), [4, 5, 3, 4, 4, 4, 3, 5, 4,
                                                  4, 4, 3, 5, 4, 4, 3, 4, 5])}
SI = {str(h): s for h, s in zip(range(1, 19), [7, 3, 15, 1, 11, 5, 17, 9, 13,
                                                 8, 2, 16, 4, 12, 6, 18, 14, 10])}


def card(**over):
    c = {"holes": 18, "par": PAR, "stroke_index": SI, "tees": [
        {"tee_name": "Blue", "gender": "M", "bands": ["<50"], "rating": 71.2, "slope": 128,
         "front": {"rating": 35.7, "slope": 127}, "back": {"rating": 35.5, "slope": 129}},
        {"tee_name": "White", "gender": "M", "bands": ["50-64", "65+"], "rating": 69.0, "slope": 121},
        {"tee_name": "Red", "gender": "F", "bands": ["L"], "rating": 70.1, "slope": 119},
    ]}
    c.update(over)
    return c


def main():
    from email_parser import database as db
    from email_parser.course_card import load_course_card, validate_card
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db.init_db(p)
    conn = sqlite3.connect(p)
    with db._connect(p) as c2:
        db._ensure_scoring_tables(c2)
    cid = conn.execute("INSERT INTO courses (name) VALUES ('The Hideout Golf Club') "
                       "RETURNING course_id").fetchone()[0]
    conn.commit()
    conn.close()

    check("a good card validates", validate_card(card()) == [], validate_card(card()))
    bad_si = dict(SI, **{"18": 1})
    errs = validate_card(card(stroke_index=bad_si))
    check("duplicate stroke index is refused", any("once each" in e for e in errs), errs)
    errs = validate_card(card(par={k: v for k, v in PAR.items() if k != "9"}))
    check("a missing hole is refused", any("par must list" in e for e in errs), errs)
    errs = validate_card(card(tees=[{"tee_name": "Blue", "rating": 7.1, "slope": 128}]))
    check("a mistyped rating is refused", any("outside" in e for e in errs), errs)
    errs = validate_card(card(tees=[{"tee_name": "Blue", "rating": 71, "slope": 128,
                                     "bands": ["senior"]}]))
    check("an unknown band is refused", any("unknown TGF band" in e for e in errs), errs)

    dry = load_course_card(cid, card(), db_path=p)
    conn = sqlite3.connect(p)
    n = conn.execute("SELECT COUNT(*) FROM course_tees WHERE course_id = ?", (cid,)).fetchone()[0]
    conn.close()
    check("dry run plans three tees, writes nothing",
          len(dry["tees"]) == 3 and not dry["applied"] and n == 0, (dry, n))

    bad = load_course_card(cid, card(stroke_index=bad_si), apply=True, db_path=p)
    conn = sqlite3.connect(p)
    n = conn.execute("SELECT COUNT(*) FROM course_tees WHERE course_id = ?", (cid,)).fetchone()[0]
    conn.close()
    check("a bad card writes nothing even with apply", not bad["applied"] and n == 0, bad)

    res = load_course_card(cid, card(), apply=True, db_path=p)
    check("apply loads the card", res["applied"] and not res["errors"], res)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    tees = [dict(r) for r in conn.execute(
        "SELECT * FROM course_tees WHERE course_id = ? ORDER BY tee_id", (cid,))]
    check("three tee rows, source course_card",
          len(tees) == 3 and all(t["source"] == "course_card" for t in tees), tees)
    blue = next(t for t in tees if t["tee_name"] == "Blue")
    check("Blue carries rating, slope, par 72, band",
          blue["rating"] == 71.2 and blue["slope"] == 128 and blue["par"] == 72
          and blue["tgf_bands"] == "<50", blue)
    red = next(t for t in tees if t["tee_name"] == "Red")
    check("Red is the women's tee", red["gender"] == "F" and red["is_ladies"] == 1, red)
    rt = {r["rating_type"]: (r["course_rating"], r["slope"]) for r in conn.execute(
        "SELECT * FROM tee_set_ratings WHERE tee_id = ?", (blue["tee_id"],))}
    check("Blue has total, front and back ratings",
          rt == {"total": (71.2, 128), "front": (35.7, 127), "back": (35.5, 129)}, rt)
    holes = {r["hole_number"]: (r["par"], r["stroke_index"]) for r in conn.execute(
        "SELECT * FROM course_tee_holes WHERE tee_id = ?", (blue["tee_id"],))}
    check("18 holes with par and SI", len(holes) == 18 and holes[4] == (4, 1)
          and holes[18] == (5, 10), holes)
    conn.close()

    fixed = card()
    fixed["tees"][0] = dict(fixed["tees"][0], slope=130)
    again = load_course_card(cid, fixed, apply=True, db_path=p)
    conn = sqlite3.connect(p)
    n = conn.execute("SELECT COUNT(*) FROM course_tees WHERE course_id = ?", (cid,)).fetchone()[0]
    s = conn.execute("SELECT slope FROM course_tees WHERE tee_id = ?", (blue["tee_id"],)).fetchone()[0]
    rs = conn.execute("SELECT slope FROM tee_set_ratings WHERE tee_id = ? AND rating_type = 'total'",
                      (blue["tee_id"],)).fetchone()[0]
    conn.close()
    check("re-loading updates in place, no new rows",
          n == 3 and s == 130 and rs == 130 and again["tees"][0]["action"] == "update", (n, s, rs))

    nine = {"holes": 9, "par": {str(h): 4 for h in range(1, 10)},
            "stroke_index": {str(h): h for h in range(1, 10)},
            "tees": [{"tee_name": "Nine White", "rating": 34.5, "slope": 118}]}
    r9 = load_course_card(cid, nine, apply=True, db_path=p)
    check("a 9-hole card loads", r9["applied"] and not r9["errors"], r9)
    check("a 9-hole card may not carry front/back",
          any("no front" in e for e in validate_card(dict(nine, tees=[dict(
              nine["tees"][0], front={"rating": 34, "slope": 118})]))))
    from email_parser.course_card import read_course_card
    rb = read_course_card(cid, db_path=p)
    b = next((t for t in rb["tees"] if t["tee_name"] == "Blue"), {})
    check("read-back shows the loaded card",
          rb["n_tees"] == 4 and len(b.get("holes", [])) == 18
          and b.get("ratings", {}).get("front", {}).get("rating") == 35.7, rb)
    check("unknown course is refused", load_course_card(999999, card(), db_path=p)["errors"])
    os.remove(p)

    print(f"\n{len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
