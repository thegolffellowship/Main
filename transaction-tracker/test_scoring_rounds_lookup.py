"""`get_scoring_rounds_list(event=...)` must not answer an id with silence.

The filter is an item_name LIKE. An events.id passed into it matched no
name and returned [], which reads exactly like "this event has no
scorecards". On 2026-09-09 that is how `scoring-rounds:3306` was
mis-reported to Kerry and to CA as "closeout has not started" when 24
Silverhorn cards had been imported the night before.

A false negative that looks like a clean result is worse than an error,
so: a numeric value is treated as the id it plainly is, and an id with no
event raises.

Run: python3 test_scoring_rounds_lookup.py
"""
import sqlite3
import tempfile
from pathlib import Path

import email_parser.database as db


def _db():
    d = Path(tempfile.mkdtemp()) / "t.db"
    db.init_db(str(d))
    with sqlite3.connect(d) as c:
        c.execute("INSERT INTO events (id, item_name, event_date) "
                  "VALUES (3306, 's9.22 Silverhorn', '2026-09-08')")
        c.execute("INSERT INTO events (id, item_name, event_date) "
                  "VALUES (3313, 'a9.22 ShadowGlen', '2026-09-08')")
    return d


def _add_round(d, event_id, player):
    with sqlite3.connect(d) as c:
        db._ensure_scoring_tables(c)
        c.execute("INSERT INTO scoring_rounds "
                  "(player_name, event_id, round_date, holes_played, source) "
                  "VALUES (?, ?, '2026-09-08', 9, 'gg')", (player, event_id))


def main():
    d = _db()
    _add_round(d, 3306, "RIDEOUT, Jeff")
    _add_round(d, 3306, "SOUTH, Daniel")
    _add_round(d, 3313, "CLOER, Neal")

    fails = 0

    def check(label, cond, detail=""):
        nonlocal fails
        if cond:
            print("  PASS  " + label)
        else:
            print("  FAIL  " + label + ("  " + detail if detail else ""))
            fails += 1

    by_id = db.get_scoring_rounds_list(None, "3306", None, 200, db_path=str(d))
    check("an events.id finds that event's rounds", len(by_id) == 2,
          f"got {len(by_id)}")
    check("and does NOT bleed in another event's rounds",
          all(r["event_id"] == 3306 for r in by_id))

    by_name = db.get_scoring_rounds_list(None, "Silverhorn", None, 200,
                                         db_path=str(d))
    check("a name substring still works", len(by_name) == 2,
          f"got {len(by_name)}")
    check("id and name agree",
          {r["id"] for r in by_id} == {r["id"] for r in by_name})

    # The whole point: an unknown id must not look like "no scorecards".
    try:
        db.get_scoring_rounds_list(None, "999999", None, 200, db_path=str(d))
        check("an id with no event raises rather than returning []", False,
              "returned instead of raising")
    except ValueError as exc:
        check("an id with no event raises rather than returning []",
              "999999" in str(exc))

    empty = db.get_scoring_rounds_list(None, "3313", None, 200, db_path=str(d))
    check("a real event with one round returns it", len(empty) == 1)

    print()
    if fails:
        print(f"{fails} FAILURE(S)")
        raise SystemExit(1)
    print("All scoring-rounds lookup assertions passed.")


if __name__ == "__main__":
    main()
