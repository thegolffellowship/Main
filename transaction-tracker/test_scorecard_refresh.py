"""Proof of the scorecard self-heal upgrade (a9.18 Forest Creek, 2026-07-14):
a card imported MID-ROUND (partial holes) must be replaced when the same
round is re-imported COMPLETE — even though GG re-keys the tournament's
aggregate ids when the round finalizes, so the complete card arrives under
a NEW aggregate id that would otherwise skip as "other tournament".

Asserts:
1. Partial card imports (4 of 9 holes).
2. Re-import of the SAME round, COMPLETE, under a DIFFERENT aggregate id
   UPGRADES in place -> one row, holes_played 9 (not skipped, not doubled).
3. A later card with FEWER/equal holes under yet another aggregate id does
   NOT clobber the complete one (still skipped).

Run: python3 test_scorecard_refresh.py
"""

import tempfile
from pathlib import Path

import golf_genius_sync
from email_parser import database as db

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label}")


def card(agg, n_holes, ph=5.0):
    holes = {h: {"strokes": 4, "dots": 0, "result": None}
             for h in range(1, n_holes + 1)}
    return {
        "player_name": "TESTER, Sam", "holes": holes,
        "gg_aggregate_id": agg, "gg_event_id": "9999",
        "gg_profile_id": "111", "playing_handicap": ph,
        "gross": 4 * n_holes, "net": 4 * n_holes - int(ph),
        "flight": None, "net_id": None, "tee": None,
    }


def fake_fetch(players):
    def _f(url, pause=0.15):
        return {"players": players, "raw": [(url, "<html></html>")]}
    return _f


def rounds_for(tmp):
    with db._connect(tmp) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, holes_played FROM scoring_rounds "
            "WHERE LOWER(player_name)=LOWER('TESTER, Sam')").fetchall()]


def main():
    tmp = Path(tempfile.mkdtemp()) / "t.db"
    db.init_db(tmp)
    with db._connect(tmp) as conn:
        conn.execute("INSERT INTO events (id, item_name, event_date, chapter,"
                     " format) VALUES (971, 'a9.71 Test', '2026-07-14',"
                     " 'Austin', '9 Holes')")
        conn.commit()
    url = "https://tgf-austin.golfgenius.com/v2tournaments/1?player_stats_for_portal=true"

    # 1. mid-round partial (4 holes) under aggregate A1
    golf_genius_sync.fetch_tournament_scorecards = fake_fetch([card("A1", 4)])
    r1 = db.import_gg_scorecards(url, event_code="a9.71", db_path=tmp)
    rows = rounds_for(tmp)
    check("1: partial imported", r1["imported"] == 1 and len(rows) == 1)
    check("1: holes_played == 4", rows and rows[0]["holes_played"] == 4)

    # 2. complete (9 holes) under a DIFFERENT aggregate A2 -> upgrade in place
    golf_genius_sync.fetch_tournament_scorecards = fake_fetch([card("A2", 9)])
    r2 = db.import_gg_scorecards(url, event_code="a9.71", db_path=tmp)
    rows = rounds_for(tmp)
    check("2: not skipped (upgraded)", r2["skipped_other_tournament"] == 0)
    check("2: upgraded counted", r2["upgraded_with_handicap"] == 1)
    check("2: still ONE row (no dup)", len(rows) == 1)
    check("2: holes_played now 9", rows and rows[0]["holes_played"] == 9)

    # 3. a fewer-holes card under A3 must NOT clobber the complete one
    golf_genius_sync.fetch_tournament_scorecards = fake_fetch([card("A3", 6)])
    r3 = db.import_gg_scorecards(url, event_code="a9.71", db_path=tmp)
    rows = rounds_for(tmp)
    check("3: fewer-holes card skipped", r3["skipped_other_tournament"] == 1)
    check("3: complete row preserved (9)", rows and rows[0]["holes_played"] == 9)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
