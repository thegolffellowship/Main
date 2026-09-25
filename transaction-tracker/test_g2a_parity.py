"""G2a compute parity — the GRADING CONTRACT, tested without a database.

The maths is not this module's; it belongs to live_scoring, ls_parity and
the matrix, all of which have their own tests. What this file pins is the
part that decides what counts as a PASS — because that is where a parity
harness goes wrong. A harness that grades generously reports green and
teaches nobody anything, which is exactly the defect found in
test_live_scoring_center.py's "PARITY" block (it builds GG's dots with our
own allocator and then asserts we reproduce them).

Run: python3 test_g2a_parity.py
"""

import sys
from email_parser import g2a_parity as g2

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


print("\n== A1 is zero tolerance: the DEFAULT is FAIL ==")

check("a clean row matches",
      g2._classify_player_row({"status": "match"})[0] == "match")
check("a gross delta FAILS — gross is never explained",
      g2._classify_player_row(
          {"status": "mismatch", "allocation_source": "derived",
           "deltas": [{"field": "gross", "delta": 1}]})[0] == "fail")
check("an unrecognised residual FAILS rather than inventing a third class",
      g2._classify_player_row(
          {"status": "mismatch", "allocation_source": "derived",
           "deltas": [{"field": "stableford_gross", "delta": -1}]})[0] == "fail")
check("a mismatch with NO deltas still fails (no benefit of the doubt)",
      g2._classify_player_row(
          {"status": "mismatch", "deltas": []})[0] == "fail")


print("\n== A2 allows exactly TWO classes, and they must qualify exactly ==")

_i = {"status": "mismatch", "allocation_source": "derived",
      "deltas": [{"field": "playing_handicap", "delta": 1},
                 {"field": "net", "delta": -1}]}
v, cls = g2._classify_player_row(_i)
check("class (i): derived dots, PH exactly +1, is EXPLAINED",
      v == "explained" and cls == g2.RESIDUAL_DERIVED_DOTS_PLUS1, f"{v}/{cls}")
check("  ...but PH +2 is NOT class (i) — the rule says exactly +1",
      g2._classify_player_row(
          dict(_i, deltas=[{"field": "playing_handicap", "delta": 2}]))[0]
      == "fail")
check("  ...and GIVEN dots are NOT class (i) — the rule says derived mode",
      g2._classify_player_row(dict(_i, allocation_source="given"))[0] == "fail")
check("  ...and a gross delta riding along disqualifies it",
      g2._classify_player_row(
          dict(_i, deltas=_i["deltas"] + [{"field": "gross", "delta": 1}]))[0]
      == "fail")
check("exactly two classes are defined, no more",
      len(g2.A2_CLASSES) == 2, str(g2.A2_CLASSES))


print("\n== A3: Team Net and Skins 1/2 Net are REPORTED, not graded ==")

_gg = {"results": [
    {"game": "team_net", "player_name": "A", "position": "1", "purse": 40.0},
    {"game": "skins_half_net", "player_name": "B", "position": "1", "purse": 13.0},
    {"game": "individual_net", "player_name": "C", "position": "1", "purse": 25.0},
]}
_d = g2._diff_games(_gg, "evt", None)
check("team_net is flagged report-only",
      _d["games"]["team_net"]["a3_report_only"] is True)
check("skins_half_net is flagged report-only",
      _d["games"]["skins_half_net"]["a3_report_only"] is True)
check("individual_net IS graded",
      _d["games"]["individual_net"]["graded"] is True)
check("GG's board is captured verbatim for audit",
      _d["games"]["individual_net"]["gg_winners"][0]["player"] == "C")

check("an event with NO GG board is neither pass nor fail",
      g2._diff_games({"results": []}, "evt", None)["status"] == "no_gg_data")


print("\n== the race tier refuses to grade itself ==")
# Our standings are a snapshot fetched FROM Golf Genius. Diffing them against
# GG compares GG to itself. This must never read as a pass.
_races = {"tiers": {"players": {"status": "graded", "fail": 0}},
          "blockers": ["races tier is UNGRADEABLE"]}
check("a clean player tier with a blocker is INCOMPLETE, never PASS",
      g2._verdict(_races)["result"] == "INCOMPLETE",
      str(g2._verdict(_races)))
check("  ...and the verdict says why, in words a reader can act on",
      "UNGRADEABLE" in g2._verdict(_races)["why"])


print("\n== the verdict cannot be talked into a PASS ==")

check("any A1 failure is a FAIL for the whole gate",
      g2._verdict({"tiers": {"players": {"status": "graded", "fail": 1,
                                         "failed_players": ["X"]}},
                   "blockers": []})["result"] == "FAIL")
check("  ...and it names the player, per A2's 'listed by player name'",
      "X" in g2._verdict({"tiers": {"players": {"status": "graded", "fail": 1,
                                                "failed_players": ["X"]}},
                          "blockers": []})["why"])
check("PASS requires zero fails AND zero blockers",
      g2._verdict({"tiers": {"players": {"status": "graded", "fail": 0}},
                   "blockers": []})["result"] == "PASS")
check("a seeding error is an ERROR, not a quiet pass",
      g2._verdict({"tiers": {"players": {"status": "error",
                                         "error": "event not found"}},
                   "blockers": []})["result"] == "ERROR")


print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1)
print("ALL G2a GRADING-CONTRACT TESTS PASSED")
