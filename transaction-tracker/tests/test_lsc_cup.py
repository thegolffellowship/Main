"""Guard tests for the Lone Star Cup match engine (Track B, #659).

Pure-compute tests on mock data: stroke allocation off the low man,
singles + four-ball winner flags, the dormie-correct close-out reused
from gg_match_play, and the board points rollup (win / halve / live
projection). No DB, no network.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from email_parser.lsc_cup import (strokes_received, compute_match_detail,
                                  compute_board)


COURSE = [{"hole": h, "par": 4, "stroke_index": si}
          for h, si in zip(range(1, 19),
                           [7, 13, 1, 15, 9, 3, 17, 5, 11,
                            8, 14, 2, 16, 10, 4, 18, 6, 12])]


def _even(cids, gross, holes=18):
    return {c: {h: gross for h in range(1, holes + 1)} for c in cids}


def test_stroke_allocation_low_man_hardest_holes():
    # 5 strokes → one on each of the 5 lowest stroke indexes (SI 1-5:
    # holes 3, 12, 6, 15, 8)
    s = strokes_received(12, 7, COURSE, 18)
    assert s == {3: 1, 12: 1, 6: 1, 15: 1, 8: 1}
    # low man gets nothing; equal PHs get nothing
    assert strokes_received(7, 7, COURSE, 18) == {}
    # 20 strokes wraps: 1 everywhere, 2 on the two hardest (SI 1, 2)
    s = strokes_received(27, 7, COURSE, 18)
    assert sum(s.values()) == 20 and s[3] == 2 and s[12] == 2 and s[1] == 1


def test_singles_net_winner_and_margin():
    session = {"format": "singles", "n_holes": 18}
    match = {"id": "M1", "austin": [7], "sa": [58]}
    phs = {7: 10, 58: 7}          # Austin man gets 3 strokes (SI 1-3)
    scores = _even([7, 58], 4)    # all square gross everywhere
    d = compute_match_detail(match, session, COURSE, phs, scores)
    # Austin wins exactly the 3 stroke holes (SI 1,2,3 = holes 3,12,6);
    # after hole 16 that's 3 up with 2 to play — a genuine closeout, 3&2
    won = [h["hole"] for h in d["holes"] if h["winner"] == 1]
    assert sorted(won) == [3, 6, 12]
    assert d["gg_winner_idx"] == 1 and d["gg_margin"] == "3&2"
    assert d["closed_at_order"] == 16 and d["thru"] == 16


def test_closeout_is_dormie_correct():
    # p1 wins holes 1-10 gross, rest halved: 10 up with 8 to play →
    # closed at hole 10, margin 10&8 (the gg close-out walk, reused)
    session = {"format": "singles", "n_holes": 18}
    match = {"id": "M1", "austin": [1], "sa": [2]}
    scores = {1: {h: (3 if h <= 10 else 4) for h in range(1, 19)},
              2: {h: 4 for h in range(1, 19)}}
    d = compute_match_detail(match, session, COURSE, {1: 5, 2: 5}, scores)
    assert d["closed_at_order"] == 10
    assert d["gg_margin"] == "10&8"
    assert d["gg_winner_idx"] == 1


def test_incomplete_holes_are_not_flagged():
    # missing holes are ABSENT, not zero (Track A contract): a hole one
    # side hasn't entered has winner None and doesn't count toward thru
    session = {"format": "singles", "n_holes": 18}
    match = {"id": "M1", "austin": [1], "sa": [2]}
    scores = {1: {1: 4, 2: 4}, 2: {1: 5}}
    d = compute_match_detail(match, session, COURSE, {1: 0, 2: 0}, scores)
    assert d["holes"][0]["winner"] == 1
    assert d["holes"][1]["winner"] is None      # SA's hole 2 not in yet
    assert d["thru"] == 1 and d["gg_margin"] == "1 UP"


def test_fourball_best_ball_and_pickup():
    session = {"format": "fourball", "n_holes": 18}
    match = {"id": "FB1", "austin": [1, 2], "sa": [3, 4]}
    phs = {1: 5, 2: 5, 3: 5, 4: 5}
    scores = {1: {1: 5}, 2: {1: 3},            # Austin best ball 3
              3: {1: 4}}                       # SA partner picked up
    d = compute_match_detail(match, session, COURSE, phs, scores)
    h1 = d["holes"][0]
    assert h1["winner"] == 1 and h1["p1_gross"] == 3 and h1["p2_gross"] == 4
    # names joined per team line
    assert "/" in d["players"][0]["name"]


def test_foursomes_team_strokes_and_single_ball():
    # Alternate shot: 50% of combined-difference at team level.
    # Austin combined 20 v SA combined 12 → Austin gets round(4) strokes
    # on SI 1-4 (holes 3, 12, 6, 15), on the ONE team ball.
    session = {"format": "foursomes", "n_holes": 18}
    match = {"id": "FS1", "austin": [1, 2], "sa": [3, 4]}
    phs = {1: 12, 2: 8, 3: 5, 4: 7}
    # team gross entered against one partner only (either works)
    scores = {1: {3: 5}, 3: {3: 5}}   # gross tied on hole 3 (SI 1)
    d = compute_match_detail(match, session, COURSE, phs, scores)
    h = next(x for x in d["holes"] if x["hole"] == 3)
    assert h["p1_strokes"] == 1 and h["p2_strokes"] == 0
    assert h["winner"] == 1           # Austin nets 4 v 5 on its stroke hole


def test_board_points_win_halve_and_projection():
    dial = {"event_id": 3329, "halved_match": 0.5,
            "sessions": [{"id": "s1", "format": "singles", "n_holes": 18,
                          "points_per_match": 1,
                          "matches": [
                              {"id": "A", "austin": [1], "sa": [2]},
                              {"id": "B", "austin": [3], "sa": [4]},
                              {"id": "C", "austin": [5], "sa": [6]},
                              {"id": "D", "austin": [7], "sa": [8]}]}]}
    full = {h: 4 for h in range(1, 19)}
    win1 = {h: (3 if h == 1 else 4) for h in range(1, 19)}
    data = {"s1": {"course": COURSE,
                   "phs": {c: 5 for c in range(1, 9)},
                   "scores": {
                       1: win1, 2: full,                 # A: Austin 1 UP, final
                       3: full, 4: full,                 # B: halved, final
                       5: {1: 3, 2: 4}, 6: {1: 4, 2: 4},  # C: live, Austin leads
                       # D: no scores → upcoming
                   }}}
    board = compute_board(dial, data)
    a, s = board["teams"]["austin"], board["teams"]["sa"]
    assert a["points"] == 1.5 and s["points"] == 0.5        # win + halve
    states = {m["match_id"]: m["state"]
              for m in board["sessions"][0]["matches"]}
    assert states == {"A": "final", "B": "final", "C": "live", "D": "upcoming"}
    # projection: finals carry over, live leader (C → Austin) adds 1
    assert a["projected"] == 2.5 and s["projected"] == 0.5


def test_merge_entry_feed_binds_rounds_and_team_ball():
    from email_parser.lsc_cup import merge_entry_feed
    dial = {"sessions": [
        {"id": "sat-am", "se_round": 5},
        {"id": "sat-pm", "se_round": 6},
        {"id": "sun", "se_round": None}]}          # unbound → untouched
    feed = {"rounds": [
        {"round_id": 5,
         "course": [{"hole": 1, "par": 4, "stroke_index": 1}],
         "players": [
             {"customer_id": 7, "playing_handicap": 9,
              "scores": {"1": 4, "2": 5}},
             {"customer_id": 35, "playing_handicap": 12,
              "scores": {"1": 5}}],
         "teams": []},
        {"round_id": 6,
         "course": [{"hole": 1, "par": 4, "stroke_index": 1}],
         "players": [{"customer_id": 30, "playing_handicap": 10,
                      "scores": {"1": 9}}],       # stray individual entry
         "teams": [{"team_id": 1, "customer_ids": [30, 438],
                    "scores": {"1": 5, "2": 4}}]},
    ]}
    out = merge_entry_feed(dial, feed)
    assert set(out) == {"sat-am", "sat-pm"}       # sun stays unbound
    am = out["sat-am"]
    assert am["phs"][7] == 9 and am["scores"][7] == {"1": 4, "2": 5}
    # foursomes: the team ball lands on the first partner and WINS over
    # the stray individual score on the same hole
    pm = out["sat-pm"]
    assert pm["scores"][30] == {"1": 5, "2": 4}


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} passed")
