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
    # names joined per team line with "&" (Kerry 10/8, CoS #1449)
    assert d["players"][0]["name"] == "#1 & #2"


def test_chapman_team_handicap_is_60_40_not_50_combined():
    # CA #721 (Kerry, rule 3b): the team session is CHAPMAN. Team hcp =
    # 60% of the lower partner + 40% of the higher. These numbers split
    # the two rules: 50%-of-combined makes both teams 10 (no strokes);
    # 60/40 makes Austin 0.6*0 + 0.4*20 = 8 and SA 0.6*10 + 0.4*10 = 10,
    # so SA gets 2 strokes (SI 1 and 2 = holes 3 and 12) on ONE ball.
    session = {"format": "chapman", "n_holes": 18}
    match = {"id": "C1", "austin": [1, 2], "sa": [3, 4]}
    phs = {1: 0, 2: 20, 3: 10, 4: 10}
    d = compute_match_detail(match, session, COURSE, phs, {})
    # pop dots are known before any ball is struck
    got_sa = {h["hole"]: h["p2_pops"] for h in d["holes"] if h["p2_pops"]}
    got_au = {h["hole"]: h["p1_pops"] for h in d["holes"] if h["p1_pops"]}
    assert got_sa == {3: 1, 12: 1} and got_au == {}
    # both SA partners carry the team's strokes, whoever's row holds the ball
    assert d["strokes"]["3"] == d["strokes"]["4"] == {"3": 1, "12": 1}
    assert [p["handicap"] for p in d["players"]] == [8, 10]


def test_chapman_whs_rounding_and_single_ball():
    # Austin 0.6*8 + 0.4*12 = 9.6 -> 10; SA 0.6*5 + 0.4*7 = 5.8 -> 6.
    # Difference 4: Austin's one ball gets strokes on SI 1-4.
    session = {"format": "chapman", "n_holes": 18}
    match = {"id": "C2", "austin": [1, 2], "sa": [3, 4]}
    phs = {1: 12, 2: 8, 3: 5, 4: 7}
    scores = {1: {3: 5}, 3: {3: 5}}   # team gross against either partner
    d = compute_match_detail(match, session, COURSE, phs, scores)
    h = next(x for x in d["holes"] if x["hole"] == 3)
    assert h["p1_strokes"] == 1 and h["p2_strokes"] == 0
    assert h["winner"] == 1           # Austin nets 4 v 5 on its stroke hole
    assert sum(x["p1_pops"] for x in d["holes"]) == 4


def test_old_foursomes_label_plays_as_chapman():
    # A dial still saying "foursomes" must NOT fall back to 50% combined.
    from email_parser.lsc_cup import normalize_format
    for label in ("foursomes", "Foursomes", "alternate shot", "chapman"):
        assert normalize_format(label) == "chapman"
    session = {"format": "foursomes", "n_holes": 18}
    d = compute_match_detail({"id": "F", "austin": [1, 2], "sa": [3, 4]},
                             session, COURSE, {1: 0, 2: 20, 3: 10, 4: 10}, {})
    assert sum(h["p2_pops"] for h in d["holes"]) == 2


def test_fourball_is_90_percent_off_the_low_player():
    # 90% of each PH, WHS-rounded (half up), all off the low player:
    # 15 -> 13.5 -> 14 strokes (100% would give 15); 5 -> 4.5 -> 5.
    session = {"format": "fourball", "n_holes": 18}
    match = {"id": "FB", "austin": [1, 2], "sa": [3, 4]}
    phs = {1: 15, 2: 5, 3: 0, 4: 0}
    d = compute_match_detail(match, session, COURSE, phs, {})
    from email_parser.lsc_cup import session_handicaps
    assert session_handicaps("fourball", [[1, 2], [3, 4]], phs) == \
        {1: 14, 2: 5, 3: 0, 4: 0}
    assert d["players"][0]["handicap"] == [14, 5]
    assert d["players"][0]["course_handicap"] == [15, 5]
    # four-ball partners differ, so the per-player map carries them
    assert sum(d["strokes"]["1"].values()) == 14
    assert sum(d["strokes"]["2"].values()) == 5
    assert all(h["p1_pops"] is None for h in d["holes"])


def test_singles_stays_full_difference():
    from email_parser.lsc_cup import session_handicaps
    assert session_handicaps("singles", [[1], [2]], {1: 17, 2: 4}) == {1: 17, 2: 4}


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


# ---------------------------------------------------------------------------
# PICKUP RULE (Kerry 2026-09-25, via the Front Desk): in match play a triple
# is BALL IN HOLE (pops apply) or PICKED UP (cannot win the hole); both
# sides picked up = a push. Every card still records the triple.
# ---------------------------------------------------------------------------

def test_pickup_ball_in_hole_keeps_pops():
    # hole 3 is SI 1: Austin (PH 10 v 7) gets a stroke there. Both make a
    # triple 7, Austin's ball is IN THE HOLE -> net 6 v 7, Austin wins.
    session = {"format": "singles", "n_holes": 18}
    match = {"id": "M1", "austin": [1], "sa": [2]}
    scores = {1: {3: 7}, 2: {3: 7}}
    d = compute_match_detail(match, session, COURSE, {1: 10, 2: 7}, scores,
                             marks={1: {"3": "holed"}, 2: {"3": "holed"}})
    h = next(x for x in d["holes"] if x["hole"] == 3)
    assert h["p1_strokes"] == 1 and h["winner"] == 1
    assert not h["p1_picked_up"] and not h["p2_picked_up"]


def test_pickup_cannot_win_even_with_a_pop():
    # same hole, but Austin PICKED UP: his stroke can't save him -- SA
    # wins the hole with a holed 7.
    session = {"format": "singles", "n_holes": 18}
    match = {"id": "M1", "austin": [1], "sa": [2]}
    scores = {1: {3: 7}, 2: {3: 7}}
    d = compute_match_detail(match, session, COURSE, {1: 10, 2: 7}, scores,
                             marks={1: {"3": "picked_up"}})
    h = next(x for x in d["holes"] if x["hole"] == 3)
    assert h["winner"] == 2 and h["p1_picked_up"] and not h["p2_picked_up"]
    assert h["p1_gross"] == 7          # the card still shows the triple


def test_both_picked_up_is_a_push():
    session = {"format": "singles", "n_holes": 18}
    match = {"id": "M1", "austin": [1], "sa": [2]}
    scores = {1: {3: 7}, 2: {3: 7}}
    d = compute_match_detail(match, session, COURSE, {1: 10, 2: 7}, scores,
                             marks={1: {"3": "picked_up"}, 2: {"3": "picked_up"}})
    h = next(x for x in d["holes"] if x["hole"] == 3)
    assert h["winner"] == 0 and h["p1_picked_up"] and h["p2_picked_up"]


def test_fourball_partner_still_plays_after_a_pickup():
    # Austin's man 1 picked up at 7; partner 2 holed a 5. SA best is 5.
    # The pickup doesn't sink the side: 5 v 5 halves. Both Austin balls
    # picked up -> SA wins with anything holed.
    session = {"format": "fourball", "n_holes": 18}
    match = {"id": "FB1", "austin": [1, 2], "sa": [3, 4]}
    phs = {1: 5, 2: 5, 3: 5, 4: 5}
    scores = {1: {1: 7, 2: 7}, 2: {1: 5, 2: 7}, 3: {1: 5, 2: 6}, 4: {1: 6, 2: 7}}
    d = compute_match_detail(match, session, COURSE, phs, scores,
                             marks={1: {"1": "picked_up", "2": "picked_up"},
                                    2: {"2": "picked_up"}})
    assert d["holes"][0]["winner"] == 0 and not d["holes"][0]["p1_picked_up"]
    assert d["holes"][1]["winner"] == 2 and d["holes"][1]["p1_picked_up"]


def test_no_marks_is_stroke_play_as_before():
    # without marks a triple is just a number: nothing else changes
    session = {"format": "singles", "n_holes": 18}
    match = {"id": "M1", "austin": [1], "sa": [2]}
    scores = {1: {3: 7}, 2: {3: 6}}
    a = compute_match_detail(match, session, COURSE, {1: 10, 2: 7}, scores)
    b = compute_match_detail(match, session, COURSE, {1: 10, 2: 7}, scores, marks={})
    assert a["holes"] == b["holes"] and a["holes"][2]["winner"] == 0   # net 6 v 6


def test_merge_entry_feed_carries_marks():
    from email_parser.lsc_cup import merge_entry_feed
    dial = {"sessions": [{"id": "s", "se_round": 9}]}
    feed = {"rounds": [{"round_id": 9, "course": [],
                        "players": [{"customer_id": 1, "playing_handicap": 3,
                                     "scores": {"1": 7}, "marks": {"1": "picked_up"}},
                                    {"customer_id": 2, "playing_handicap": 3,
                                     "scores": {"1": 5}}],
                        "teams": [{"team_id": 4, "customer_ids": [5, 6],
                                   "scores": {"1": 7}, "marks": {"1": "holed"}}]}]}
    out = merge_entry_feed(dial, feed)["s"]
    assert out["marks"] == {1: {"1": "picked_up"}, 5: {"1": "holed"}}


# ── Kerry's rulings, CA #717 (2026-09-26) ─────────────────────────────

def _flat_course(n=18):
    return [{"hole": h, "par": 4, "stroke_index": h} for h in range(1, n + 1)]


def test_points_one_and_half_in_every_format():
    from email_parser.lsc_cup import compute_board
    course = _flat_course()
    full = {h: 4 for h in range(1, 19)}
    won1 = {h: (3 if h == 1 else 4) for h in range(1, 19)}
    sessions, scores = [], {}
    for fmt, a, b in (("singles", [1], [2]), ("fourball", [3, 4], [5, 6]),
                      ("foursomes", [7, 8], [9, 10])):
        sessions.append({"id": fmt, "format": fmt, "n_holes": 18,
                         # a stale per-session value must NOT change the payout
                         "points_per_match": 3,
                         "matches": [{"id": fmt + "-W", "austin": a, "sa": b},
                                     {"id": fmt + "-H", "austin": [c + 100 for c in a],
                                      "sa": [c + 100 for c in b]}]})
        for c in a:
            scores[c] = won1                 # Austin wins the W match 1 UP
        for c in b + [x + 100 for x in a + b]:
            scores[c] = full                 # the H match is halved
    data = {s["id"]: {"course": course, "phs": {c: 0 for c in scores},
                      "scores": scores} for s in sessions}
    board = compute_board({"sessions": sessions}, data)
    for sess in board["sessions"]:
        by = {m["match_id"]: m["points"] for m in sess["matches"]}
        assert by[sess["id"] + "-W"] == {"austin": 1.0, "sa": 0.0}, sess["id"]
        assert by[sess["id"] + "-H"] == {"austin": 0.5, "sa": 0.5}, sess["id"]
    assert board["teams"]["austin"]["points"] == 4.5
    assert board["teams"]["sa"]["points"] == 1.5


def test_cup_status_defending_champion_keeps_a_tie():
    from email_parser.lsc_cup import cup_status
    # 14 points on the board: the champion needs 7, the challenger 7.5
    st = cup_status({"austin": 3, "sa": 2}, 14, "sa")
    assert st["status"] == "open" and st["needs"] == {"austin": 4.5, "sa": 5.0}
    st = cup_status({"austin": 6.5, "sa": 7}, 14, "sa")
    assert st["status"] == "retained" and st["winner"] == "sa"
    st = cup_status({"austin": 7.5, "sa": 5}, 14, "sa")
    assert st["status"] == "won" and st["winner"] == "austin"
    # a finished 7-7 tie: the champion keeps it
    st = cup_status({"austin": 7, "sa": 7}, 14, "austin")
    assert st["status"] == "retained" and st["winner"] == "austin"


def test_cup_status_without_a_recorded_champion_never_guesses():
    from email_parser.lsc_cup import cup_status
    st = cup_status({"austin": 7, "sa": 7}, 14, None)
    assert st["status"] == "tied_pending" and st["winner"] is None
    st = cup_status({"austin": 7, "sa": 3}, 14, None)
    assert st["status"] == "open"            # 7 of 14 is not a clinch
    assert st["needs"] == {"austin": 0.5, "sa": 4.5}


def test_skins_count_holes_after_the_closeout_but_never_the_match():
    from email_parser.lsc_cup import compute_board
    # Austin closes the match out 10&8; SA then wins holes 11-18 by a
    # stroke each. The match stays Austin's, and SA takes those skins.
    a = {h: (3 if h <= 10 else 5) for h in range(1, 19)}
    b = {h: 4 for h in range(1, 19)}
    sess = {"id": "sun", "format": "singles", "n_holes": 18,
            "matches": [{"id": "S1", "austin": [1], "sa": [2]}]}
    data = {"sun": {"course": _flat_course(), "phs": {1: 0, 2: 0},
                    "scores": {1: a, 2: b}}}
    board = compute_board({"sessions": [sess]}, data,
                          skins_ctx={"buyers": {1, 2}, "index": {1: 5.0, 2: 6.0}})
    m = board["sessions"][0]["matches"][0]
    assert m["state"] == "final" and m["gg_margin"] == "10&8"
    assert m["points"] == {"austin": 1.0, "sa": 0.0}
    f1 = board["sessions"][0]["skins"]["groups"][0]
    assert {r["key"]: r["skins"] for r in f1["totals"]} == \
        {"S1:austin:1": 10, "S1:sa:2": 8}


def test_skins_team_vs_individual_and_pending_until_all_posted():
    from email_parser.lsc_cup import compute_skins
    course = _flat_course(2)
    fb = {"id": "am", "format": "fourball", "n_holes": 2,
          "matches": [{"id": "M1", "austin": [1, 2], "sa": [3, 4]},
                      {"id": "M2", "austin": [5, 6], "sa": [7, 8]}]}
    scores = {1: {1: 4, 2: 5}, 2: {1: 5}, 3: {1: 5, 2: 5}, 4: {1: 6},
              5: {1: 5, 2: 5}, 6: {1: 5}, 7: {1: 5}, 8: {1: 5}}
    out = compute_skins(fb, course, {}, scores, basis="gross")
    assert out["kind"] == "team"
    h1, h2 = out["holes"]
    assert h1["status"] == "won" and h1["winner"] == "M1:austin"   # 4 vs 5s
    assert h2["status"] == "pending"          # M2's SA side hasn't posted 2
    singles = {"id": "sun", "format": "singles", "n_holes": 2,
               "matches": [{"id": "S1", "austin": [1], "sa": [3]}]}
    out = compute_skins(singles, course, {}, scores, basis="gross")
    assert out["kind"] == "individual"
    assert [r["key"] for r in out["totals"]] == ["S1:austin:1", "S1:sa:3"]


def test_skins_net_uses_full_locked_ph_and_ties_carry_only_when_on():
    from email_parser.lsc_cup import compute_skins
    course = _flat_course(3)
    sess = {"id": "sun", "format": "singles", "n_holes": 3,
            "matches": [{"id": "S1", "austin": [1], "sa": [2]}]}
    # player 2 gets 1 stroke (SI 1 = hole 1): gross 5 nets 4 = tie
    scores = {1: {1: 4, 2: 4, 3: 3}, 2: {1: 5, 2: 4, 3: 4}}
    gross = compute_skins(sess, course, {1: 0, 2: 1}, scores, basis="gross")
    assert [h["status"] for h in gross["holes"]] == ["won", "tied", "won"]
    net = compute_skins(sess, course, {1: 0, 2: 1}, scores, basis="net")
    assert [h["status"] for h in net["holes"]] == ["tied", "tied", "won"]
    assert net["holes"][2]["value"] == 1                 # no carryover
    carry = compute_skins(sess, course, {1: 0, 2: 1}, scores, basis="net",
                          carryover=True)
    assert carry["holes"][2]["value"] == 3                # 2 carried + 1


def test_skins_a_picked_up_ball_never_wins():
    from email_parser.lsc_cup import compute_skins
    sess = {"id": "sun", "format": "singles", "n_holes": 1,
            "matches": [{"id": "S1", "austin": [1], "sa": [2]}]}
    out = compute_skins(sess, _flat_course(1), {}, {1: {1: 7}, 2: {1: 7}},
                        marks={1: {1: "picked_up"}}, basis="gross")
    assert out["holes"][0]["winner"] == "S1:sa:2"


def test_skins_chapman_net_uses_the_team_handicap_off_zero():
    from email_parser.lsc_cup import compute_skins
    sess = {"id": "pm", "format": "chapman", "n_holes": 18,
            "matches": [{"id": "C1", "austin": [1, 2], "sa": [3, 4]}]}
    # Team handicaps off zero: Austin 0.6*0 + 0.4*20 = 8 (strokes on SI
    # 1-8), SA 0.6*10 + 0.4*10 = 10 (SI 1-10). Holes 3 (SI 1) and 10
    # (SI 8): both gross 5, both net 4 -> tied. Hole 9 (SI 11): no
    # strokes for either -> gross 4 beats 5, Austin wins the skin.
    course = COURSE
    scores = {1: {3: 5, 10: 5, 9: 4}, 3: {3: 5, 10: 5, 9: 5}}
    out = compute_skins(sess, course, {1: 0, 2: 20, 3: 10, 4: 10}, scores,
                        basis="net")
    by = {h["hole"]: h for h in out["holes"]}
    assert by[3]["status"] == "tied" and by[10]["status"] == "tied"
    assert by[9]["winner"] == "C1:austin"


# ── Skins payout, Kerry's rulings CA #725/#726 (2026-09-26) ───────────

def _fb_session():
    return {"id": "am", "format": "fourball", "n_holes": 2,
            "matches": [{"id": "M1", "austin": [1, 2], "sa": [3, 4]},
                        {"id": "M2", "austin": [5, 6], "sa": [7, 8]}]}


def _all_fours(cids, holes=2):
    return {c: {h: 4 for h in range(1, holes + 1)} for c in cids}


def test_pot_is_25_per_buyer_in_the_round_and_team_skin_splits():
    from email_parser.lsc_cup import compute_skins_payout
    scores = _all_fours(range(1, 9))
    scores[1][1] = 3                    # M1 Austin best ball wins hole 1
    scores[7][2] = 3                    # M2 SA best ball wins hole 2
    out = compute_skins_payout(_fb_session(), _flat_course(2), {}, scores,
                               buyers=set(range(1, 9)))
    assert out["basis"] == "net" and out["pot_cents"] == 8 * 2500   # #1357-1
    g = out["groups"][0]
    assert g["complete"] and g["skins_won"] == 2
    pay = {p["key"]: p for p in g["payouts"]}
    assert pay["M1:austin"]["cents"] == 10000 and pay["M2:sa"]["cents"] == 10000
    # a team skin is split evenly between the partners
    assert [pp["cents"] for pp in pay["M1:austin"]["per_player"]] == [5000, 5000]
    assert sum(p["cents"] for p in g["payouts"]) == out["pot_cents"]


def test_uneven_money_splits_exactly_to_the_cent():
    from email_parser.lsc_cup import compute_skins_payout
    sess = {"id": "am", "format": "fourball", "n_holes": 3,
            "matches": [{"id": "M1", "austin": [1, 2], "sa": [3, 4]},
                        {"id": "M2", "austin": [5, 6], "sa": [7]}]}
    scores = _all_fours([1, 2, 3, 4, 5, 6, 7], 3)
    scores[1][1] = 3
    scores[3][2] = 3
    scores[5][3] = 3
    out = compute_skins_payout(sess, _flat_course(3), {}, scores,
                               buyers={1, 2, 3, 4, 5, 6, 7})
    g = out["groups"][0]
    assert out["pot_cents"] == 7 * 2500                  # $175 / 3 skins
    assert sorted(p["cents"] for p in g["payouts"]) == [5833, 5833, 5834]
    assert sum(p["cents"] for p in g["payouts"]) == 17500


def test_mixed_team_plays_and_its_buyer_gets_the_full_team_skin():
    # Kerry, CA #759: one partner bought, one didn't -> the team plays
    # and the buyer is paid the WHOLE team skin; nothing left over.
    from email_parser.lsc_cup import compute_skins_payout
    scores = _all_fours(range(1, 9))
    scores[1][1] = 3                    # mixed M1 Austin wins hole 1
    scores[7][2] = 3                    # M2 SA (both bought) wins hole 2
    out = compute_skins_payout(_fb_session(), _flat_course(2), {}, scores,
                               buyers={1, 3, 4, 5, 6, 7, 8})   # 2 didn't buy
    assert out["pot_cents"] == 7 * 2500                        # $175
    assert out["excluded"] == [] and out["flags"] == []
    assert out["mixed"] and out["mixed"][0]["team"] == "austin"
    g = out["groups"][0]
    pay = {p["key"]: p for p in g["payouts"]}
    assert pay["M1:austin"]["cents"] == 8750                   # half the pot
    assert pay["M1:austin"]["per_player"] == [{"customer_id": 1, "cents": 8750}]
    assert [p["cents"] for p in pay["M2:sa"]["per_player"]] == [4375, 4375]
    paid = sum(pp["cents"] for p in g["payouts"] for pp in p["per_player"])
    assert paid == out["pot_cents"] and g["unpaid_cents"] == 0


def test_mixed_team_tie_is_still_a_tie():
    from email_parser.lsc_cup import compute_skins_payout
    scores = _all_fours(range(1, 9))
    scores[1][1] = 3                    # mixed M1 Austin ties M2 SA on 1
    scores[7][1] = 3
    out = compute_skins_payout(_fb_session(), _flat_course(2), {}, scores,
                               buyers={1, 3, 4, 5, 6, 7, 8})
    g = out["groups"][0]
    assert g["skins_won"] == 0 and g["unpaid_cents"] == out["pot_cents"]


def test_team_where_neither_partner_bought_stays_out():
    from email_parser.lsc_cup import compute_skins_payout
    scores = _all_fours(range(1, 9))
    scores[1][1] = 3                    # would win, but 1 and 2 didn't buy
    out = compute_skins_payout(_fb_session(), _flat_course(2), {}, scores,
                               buyers={3, 4, 5, 6, 7, 8})
    assert out["pot_cents"] == 6 * 2500 and out["mixed"] == []
    assert any(e["reason"] == "not bought in" for e in out["excluded"])
    assert "M1:austin" not in {t["key"] for t in out["groups"][0]["totals"]}


def test_member_view_never_sees_who_is_paid_on_a_mixed_team():
    from email_parser.lsc_cup import compute_skins_payout, strip_money
    scores = _all_fours(range(1, 9))
    scores[1][1] = 3
    sk = compute_skins_payout(_fb_session(), _flat_course(2), {}, scores,
                              buyers={1, 3, 4, 5, 6, 7, 8})
    msk = strip_money({"sessions": [{"id": "am", "skins": sk}]})["sessions"][0]["skins"]
    assert "mixed" not in msk and "pot_cents" not in msk
    assert all("payouts" not in g for g in msk["groups"])


# -- 14 v 13: the odd player (Kerry 2026-09-28) --------------------------
# The side with the odd player sends him into a THREESOME against the
# other side's spare pair: two singles matches at once, a full point each.

def _odd_session(fmt):
    return {"id": "x", "format": fmt, "n_holes": 18,
            "matches": [{"id": "M1", "austin": [1, 2], "sa": [3, 4]},
                        {"id": "T1", "austin": [5], "sa": [9]},
                        {"id": "T2", "austin": [6], "sa": [9]}]}


def test_singles_inside_a_team_session_is_played_at_100_percent():
    from email_parser.lsc_cup import compute_match_detail, match_format
    course = _flat_course()
    phs = {5: 11, 9: 0}
    for fmt in ("fourball", "chapman"):
        sess = _odd_session(fmt)
        t1 = sess["matches"][1]
        assert match_format(t1, sess) == "singles"
        d = compute_match_detail(t1, sess, course, phs, {})
        # 100% -> 11 strokes (four-ball's 90% would be 9.9 -> 10)
        assert d["format"] == "singles"
        assert sum(sum(v.values()) for v in [d["strokes"].get(5, {}) or
                   d["strokes"].get("5", {})]) == 11
    assert match_format(sess["matches"][0], sess) == "chapman"
    assert match_format({"format": "fourball", "austin": [1], "sa": [2]},
                        sess) == "fourball"             # explicit wins


def test_odd_player_two_matches_are_two_full_points():
    from email_parser.lsc_cup import compute_board
    course = _flat_course()
    sess = _odd_session("fourball")
    phs = {c: 6 for c in (1, 2, 3, 4, 5, 6, 9)}
    sc = {c: {h: 4 for h in range(1, 19)} for c in phs}
    sc[9][1] = 3                        # the odd SA player wins both on hole 1
    b = compute_board({"sessions": [sess], "defending_champion": "sa"},
                      {"x": {"course": course, "phs": phs, "scores": sc}}, {})
    res = {m["match_id"]: (m["state"], m["points"]) for m in b["sessions"][0]["matches"]}
    assert res["T1"] == ("final", {"austin": 0.0, "sa": 1.0})
    assert res["T2"] == ("final", {"austin": 0.0, "sa": 1.0})
    assert b["cup"]["total"] == 3.0 and b["teams"]["sa"]["points"] == 2.5


def test_odd_player_counted_once_in_team_skins_pair_is_one_entry():
    # Kerry 2026-09-28: SA single vs Austin pair. The odd player's lone
    # birdie WINS the skin (he can't tie himself), and the two players
    # he faces are one team entry sharing their skin.
    from email_parser.lsc_cup import compute_skins_payout, skins_team_sides
    sess = _odd_session("fourball")
    sides = skins_team_sides(sess["matches"])
    assert {"id": "T1+T2", "sa": [9], "austin": [5, 6]} in sides
    assert skins_team_sides(sides) == sides                      # idempotent
    sc = {c: {1: 4, 2: 4} for c in (1, 2, 3, 4, 5, 6, 9)}
    sc[9][1] = 3                        # odd player alone on hole 1
    sc[6][2] = 3                        # Austin pair's better ball on 2
    out = compute_skins_payout({**sess, "n_holes": 2}, _flat_course(2), {}, sc,
                               buyers={1, 2, 3, 4, 5, 6, 9})
    assert out["pot_cents"] == 7 * 2500                     # 9 counted once
    g = out["groups"][0]
    pay = {p["key"]: [pp["cents"] for pp in p["per_player"]] for p in g["payouts"]}
    assert pay == {"T1+T2:sa": [8750], "T1+T2:austin": [4375, 4375]}


def test_odd_player_in_two_sunday_singles_is_one_skins_entry():
    from email_parser.lsc_cup import compute_skins_payout
    sess = {"id": "sun", "format": "singles", "n_holes": 2,
            "matches": [{"id": "S1", "austin": [5], "sa": [9]},
                        {"id": "S2", "austin": [6], "sa": [9]},
                        {"id": "S3", "austin": [7], "sa": [8]}]}
    sc = {c: {1: 4, 2: 4} for c in (5, 6, 7, 8, 9)}
    sc[9][1] = 3                        # alone on hole 1 -> wins, no self-tie
    idx = {5: 5.0, 6: 5.0, 7: 20.0, 8: 20.0, 9: 5.0}
    out = compute_skins_payout(sess, _flat_course(2), {}, sc,
                               buyers={5, 6, 7, 8, 9}, index=idx)
    assert out["pot_cents"] == 5 * 2500
    f1 = next(g for g in out["groups"] if g["flight"] == 1)
    assert f1["entrants"] == 3 and f1["skins_won"] == 1
    assert [pp["customer_id"] for p in f1["payouts"] for pp in p["per_player"]] == [9]


def test_singles_flight_at_12_with_half_the_pot_each():
    from email_parser.lsc_cup import compute_skins_payout
    sess = {"id": "sun", "format": "singles", "n_holes": 1,
            "matches": [{"id": "S1", "austin": [1], "sa": [2]},
                        {"id": "S2", "austin": [3], "sa": [4]}]}
    idx = {1: 11.9, 2: 4.0, 3: 12.0, 4: 20.5}         # F1: 1,2  F2: 3,4
    scores = {1: {1: 3}, 2: {1: 4}, 3: {1: 5}, 4: {1: 4}}
    out = compute_skins_payout(sess, _flat_course(1), {}, scores,
                               buyers={1, 2, 3, 4}, index=idx)
    f1, f2 = out["groups"]
    assert (f1["flight"], f2["flight"]) == (1, 2)
    assert f1["pot_cents"] == f2["pot_cents"] == 5000   # $100 split in half
    assert f1["payouts"][0]["key"] == "S1:austin:1"     # 3 beats 4 in F1
    assert f2["payouts"][0]["key"] == "S2:sa:4"         # 4 beats 5 in F2
    assert not any("uneven" in f for f in out["flags"])


def test_uneven_flights_and_unflighted_players_are_flagged():
    from email_parser.lsc_cup import compute_skins_payout
    sess = {"id": "sun", "format": "singles", "n_holes": 1,
            "matches": [{"id": f"S{i}", "austin": [i], "sa": [i + 10]}
                        for i in range(1, 4)]}
    idx = {1: 5, 11: 6, 2: 7, 12: 8, 3: 20}           # 5 in F1, 1 in F2
    out = compute_skins_payout(sess, _flat_course(1), {}, {},
                               buyers={1, 2, 3, 11, 12, 13}, index=idx)
    assert any("uneven" in f for f in out["flags"])
    assert any("no TGF index" in e["reason"] for e in out["excluded"])  # 13


def test_no_dollar_until_every_entry_has_posted_every_hole():
    from email_parser.lsc_cup import compute_skins_payout
    scores = _all_fours(range(1, 9))
    del scores[8][2], scores[7][2]                    # M2 SA hasn't posted 2
    out = compute_skins_payout(_fb_session(), _flat_course(2), {}, scores,
                               buyers=set(range(1, 9)))
    g = out["groups"][0]
    assert g["held"] is True and g["payouts"] is None


def test_no_skin_won_leaves_the_pot_unallocated_and_flags_it():
    from email_parser.lsc_cup import compute_skins_payout
    out = compute_skins_payout(_fb_session(), _flat_course(2), {},
                               _all_fours(range(1, 9)),
                               buyers=set(range(1, 9)))
    g = out["groups"][0]
    assert g["complete"] and g["skins_won"] == 0
    assert g["unpaid_cents"] == out["pot_cents"] and g["payouts"] == []
    assert any("unallocated" in f for f in out["flags"])


def test_member_view_strips_every_dollar():
    from email_parser.lsc_cup import compute_board, strip_money
    scores = _all_fours(range(1, 9))
    scores[1][1] = 3
    board = compute_board({"sessions": [_fb_session()]},
                          {"am": {"course": _flat_course(2), "phs": {},
                                  "scores": scores}},
                          skins_ctx={"buyers": set(range(1, 9))})
    assert board["sessions"][0]["skins"]["pot_cents"] == 20000
    member = strip_money(board)
    blob = str(member["sessions"][0]["skins"])
    assert "cents" not in blob and "flags" not in blob
    assert member["sessions"][0]["skins"]["groups"][0]["totals"]
    assert board["sessions"][0]["skins"]["pot_cents"] == 20000  # original intact


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} passed")


# -- Pivots (Kerry 2026-09-28): a withdrawal mid-weekend ------------------

def test_13_v_13_pm_one_lone_singles_match_and_its_own_skins():
    # "if it was 13 v 13 on Saturday PM after being 13 v 14 in AM, there
    # would only then be one singles match in the PM session for the odd
    # players 1 v 1. Skins would still apply if they were able to get one
    # on their own."
    from email_parser.lsc_cup import compute_board, compute_skins_payout
    course = _flat_course()
    sess = {"id": "pm", "format": "chapman", "n_holes": 18,
            "matches": [{"id": "C1", "austin": [1, 2], "sa": [3, 4]},
                        {"id": "S1", "austin": [5], "sa": [9]}]}
    phs = {1: 10, 2: 10, 3: 10, 4: 10, 5: 11, 9: 0}
    sc = {c: {h: 4 for h in range(1, 19)} for c in phs}
    sc[5][7] = 3                        # the Austin odd player, on his own
    b = compute_board({"sessions": [sess]}, {"pm": {"course": course,
                                                    "phs": phs, "scores": sc}}, {})
    s1 = next(m for m in b["sessions"][0]["matches"] if m["match_id"] == "S1")
    assert s1["format"] == "singles"
    assert s1["players"][0]["handicap"] == 11          # 100%, not Chapman
    sk = compute_skins_payout(sess, course, phs, sc, buyers=set(phs))
    g = sk["groups"][0]
    assert {"S1:austin", "S1:sa"} <= {t["key"] for t in g["totals"]}
    assert [(p["key"], [pp["cents"] for pp in p["per_player"]])
            for p in g["payouts"]] == [("S1:austin", [15000])]


def test_recorded_result_closes_a_match_an_injury_stopped():
    from email_parser.lsc_cup import compute_board, strip_money
    course = _flat_course()
    sess = {"id": "sun", "format": "singles", "n_holes": 18,
            "matches": [{"id": "S1", "austin": [1], "sa": [2],
                         "result": {"winner": "sa", "note": "1 hurt on 6"}},
                        {"id": "S2", "austin": [3], "sa": [4],
                         "result": {"winner": "halved"}}]}
    phs = {1: 5, 2: 5, 3: 5, 4: 5}
    sc = {c: {h: 4 for h in range(1, 6)} for c in phs}   # stopped after 5
    b = compute_board({"sessions": [sess], "defending_champion": "sa"},
                      {"sun": {"course": course, "phs": phs, "scores": sc}}, {})
    m = {x["match_id"]: x for x in b["sessions"][0]["matches"]}
    assert m["S1"]["state"] == "final" and m["S1"]["points"] == {"austin": 0.0, "sa": 1.0}
    assert m["S1"]["gg_margin"] == "Conceded"
    assert m["S2"]["points"] == {"austin": 0.5, "sa": 0.5}
    assert b["cup"]["status"] == "won" and b["cup"]["winner"] == "sa"
    member = strip_money(b)
    assert "note" not in member["sessions"][0]["matches"][0]["result_override"]


def test_withdrawn_player_does_not_hold_skins_for_everyone():
    from email_parser.lsc_cup import compute_skins
    sess = {"id": "sun", "format": "singles", "n_holes": 3,
            "matches": [{"id": "S1", "austin": [1], "sa": [2]},
                        {"id": "S2", "austin": [3], "sa": [4]}]}
    sc = {1: {1: 4, 2: 4, 3: 3}, 2: {1: 4, 2: 4, 3: 4},
          3: {1: 4, 2: 4, 3: 4}, 4: {1: 4}}          # 4 hurt after hole 1
    held = compute_skins(sess, _flat_course(3), {}, sc, basis="gross")
    assert held["holes"][2]["status"] == "pending"
    done = compute_skins({**sess, "withdrawn": [4]}, _flat_course(3), {}, sc,
                         basis="gross")
    assert done["holes"][2]["status"] == "won"


def test_validate_matches_catches_a_bad_quick_edit():
    from email_parser.lsc_cup import validate_matches
    ok = {"sessions": [_odd_session("fourball")]}
    assert validate_matches(ok) == []
    bad = {"sessions": [{"id": "am", "format": "fourball", "matches": [
        {"id": "M1", "austin": [1, 2], "sa": [3, 4]},
        {"id": "M2", "austin": [1, 5], "sa": [6, 7]},        # 1 twice, team
        {"id": "M3", "austin": [8], "sa": [8]},              # both teams
        {"id": "M4", "austin": [9], "sa": [],                # empty side
         "result": {"winner": "nobody"}}],
        "withdrawn": [42]}]}
    w = " | ".join(validate_matches(bad))
    for frag in ("player 1 is in two matches", "player 8 is on both teams",
                 "M4: no sa player", "M4: result must name",
                 "withdrawn player 42"):
        assert frag in w, frag


def test_results_snapshot_freezes_the_final_board(tmp_path):
    import json
    import sqlite3
    from email_parser import lsc_cup
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
    sess = {"id": "sun", "format": "singles", "n_holes": 2,
            "matches": [{"id": "S1", "austin": [1], "sa": [2]}]}
    dial = {"event_id": 3329, "defending_champion": "sa", "sessions": [sess]}
    mock = {"sun": {"course": _flat_course(2), "phs": {"1": 0, "2": 0},
                    "scores": {"1": {"1": 4}, "2": {"1": 4}}}}     # hole 2 open
    for k, v in (("lsc_matches", dial), ("lsc_mock_scores", mock)):
        conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?)",
                     (k, json.dumps(v)))
    conn.commit()
    refused = lsc_cup.freeze_cup_results(db_path=str(db))
    assert refused["frozen"] is False and refused["blockers"]
    mock["sun"]["scores"] = {"1": {"1": 4, "2": 3}, "2": {"1": 4, "2": 4}}
    conn.execute("UPDATE app_settings SET value = ? WHERE key = 'lsc_mock_scores'",
                 (json.dumps(mock),))
    conn.commit()
    res = lsc_cup.freeze_cup_results(db_path=str(db))
    assert res["frozen"] is True and res["cup"]["winner"] == "austin"
    # a later score edit does NOT change the frozen result
    mock["sun"]["scores"]["2"]["2"] = 2
    conn.execute("UPDATE app_settings SET value = ? WHERE key = 'lsc_mock_scores'",
                 (json.dumps(mock),))
    conn.commit()
    b = lsc_cup.lsc_board_payload(db_path=str(db))
    assert b["source"] == "final" and b["cup"]["winner"] == "austin"
    assert b["results_frozen"]["forced"] is False
    lsc_cup.clear_cup_results(db_path=str(db))
    assert lsc_cup.lsc_board_payload(db_path=str(db))["cup"]["winner"] == "sa"


# -- Mixed tees (Kerry 2026-09-28): WHS, each player on his own tee --------
_MEN_SI = [17, 15, 3, 1, 11, 7, 5, 13, 9, 16, 14, 6, 8, 2, 10, 18, 4, 12]
_TEAL_SI = [11, 17, 5, 1, 15, 7, 9, 13, 3, 16, 4, 10, 18, 6, 14, 2, 8, 12]


def test_teal_player_takes_strokes_on_her_own_stroke_index():
    # The Hideout: a Teal (forward) player 3 strokes worse than a
    # men's-tee player gets them on HER SI 1-3 (holes 4, 16, 9), not the
    # men's SI 1-3 (holes 4, 14, 3).
    from email_parser.lsc_cup import compute_match_detail
    course = [{"hole": h, "par": 4, "stroke_index": _MEN_SI[h - 1]} for h in range(1, 19)]
    sess = {"id": "sun", "format": "singles", "n_holes": 18}
    m = {"id": "S1", "austin": [1], "sa": [23]}
    teal = {23: {h: _TEAL_SI[h - 1] for h in range(1, 19)}}
    d = compute_match_detail(m, sess, course, {1: 5, 23: 8}, {}, si_by_player=teal)
    got = d["strokes"].get(23) or d["strokes"].get("23")
    assert sorted(int(h) for h in got) == [4, 9, 16]
    plain = compute_match_detail(m, sess, course, {1: 5, 23: 8}, {})
    assert sorted(int(h) for h in (plain["strokes"].get(23) or plain["strokes"]["23"])) == [3, 4, 14]


def test_player_stroke_index_resolves_tee_name_or_band(tmp_path):
    import sqlite3
    from email_parser.lsc_cup import _attach_player_stroke_index
    conn = sqlite3.connect(tmp_path / "c.db")
    conn.execute("CREATE TABLE course_tees (tee_id INTEGER, course_id INTEGER, "
                 "tee_name TEXT, tgf_bands TEXT, gender TEXT)")
    conn.execute("CREATE TABLE course_tee_holes (tee_id INTEGER, hole_number INTEGER, "
                 "par INTEGER, yardage INTEGER, stroke_index INTEGER)")
    conn.executemany("INSERT INTO course_tees VALUES (?,?,?,?,?)",
                     [(1, 65112, "Blue", "<50", "M"), (2, 65112, "Teal", "Forward", "F")])
    for tid, si in ((1, _MEN_SI), (2, _TEAL_SI)):
        conn.executemany("INSERT INTO course_tee_holes VALUES (?,?,?,?,?)",
                         [(tid, h, 4, 400, si[h - 1]) for h in range(1, 19)])
    course = [{"hole": h, "par": 4, "stroke_index": _MEN_SI[h - 1]} for h in range(1, 19)]
    data = {"sun": {"course": course, "course_id": 65112,
                    "tees": {7: "<50", 23: "Forward", 30: "teal", 99: "Nowhere"}}}
    data["_note"] = "STAGED DEMO scores"      # the mock dial carries a string
    _attach_player_stroke_index(conn, data)
    si = data["sun"]["si_by_player"]
    assert set(si) == {23, 30}                 # men's-tee and unknown: round list
    assert si[23][9] == 3 and si[30][16] == 2
    assert data["sun"]["tee_gender"] == {7: "M", 23: "F", 30: "F"}


def _chapman_pops(tee_gender, si_by_player):
    from email_parser.lsc_cup import compute_match_detail
    course = [{"hole": h, "par": 4, "stroke_index": _MEN_SI[h - 1]} for h in range(1, 19)]
    sess = {"id": "pm", "format": "chapman", "n_holes": 18}
    m = {"id": "C1", "austin": [1, 2], "sa": [23, 24]}
    # SA pair 60/40 of (5, 5) = 5 strokes more than Austin's (0)
    phs = {1: 0, 2: 0, 23: 5, 24: 5}
    d = compute_match_detail(m, sess, course, phs, {}, si_by_player=si_by_player,
                             tee_gender=tee_gender)
    return sorted(int(h) for h in (d["strokes"].get(23) or d["strokes"]["23"]))


def test_chapman_mixed_pair_takes_strokes_on_the_mens_holes():
    # Kerry 2026-09-28: a man-and-woman Chapman pair plays on the men's
    # stroke index; two women play on the women's.
    teal = {h: _TEAL_SI[h - 1] for h in range(1, 19)}
    mixed = _chapman_pops({1: "M", 2: "M", 23: "F", 24: "M"}, {23: teal})
    assert mixed == [3, 4, 7, 14, 17]                    # men's SI 1-5
    two_women = _chapman_pops({1: "M", 2: "M", 23: "F", 24: "F"},
                              {23: teal, 24: teal})
    assert two_women == [3, 4, 9, 11, 16]                # Teal SI 1-5
    unknown = _chapman_pops({}, {23: teal})
    assert unknown == [3, 4, 7, 14, 17]                  # round's list


# ── Saturday team skins are NET at the full session allowance (Kerry
#    2026-10-07, CoS #1357-1/-2) ────────────────────────────────────────

def test_team_skins_are_net_at_90pct_off_zero_not_off_the_low():
    # Four-ball: PH 10 -> 9 strokes (90%) off ZERO. Off the lowest in the
    # match (PH 0 opponent) would be the same here, so make the low man
    # PH 4: off-low would give the PH-10 player only 5 strokes.
    from email_parser.lsc_cup import compute_skins_payout
    sess = {"id": "am", "format": "fourball", "n_holes": 9,
            "matches": [{"id": "M1", "austin": [1, 2], "sa": [3, 4]}]}
    course = [{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 10)]
    scores = _all_fours([1, 2, 3, 4], 9)
    scores[1][9] = 5       # PH 10 player: 5 on SI-9 hole, a stroke -> net 4 (90%: 9 pops)
    scores[2][9] = 6       # partner PH 10 too
    scores[3][9] = 4       # low man PH 4: 90% -> 4 pops on SI 1-4 only -> net 4 on 9
    scores[4][9] = 4
    for c in (3, 4):
        for h in range(1, 9):
            scores[c][h] = 5
    phs = {1: 10, 2: 10, 3: 4, 4: 4}
    out = compute_skins_payout(sess, course, phs, scores, buyers={1, 2, 3, 4})
    assert out["basis"] == "net"
    g = out["groups"][0]
    holes = {h["hole"]: h for h in g["holes"]}
    # hole 9: Austin best net = 5 - 1 = 4; SA best net = 4 - 0 = 4 -> tied
    assert holes[9]["status"] == "tied"
    # holes 5-8: Austin net 4-1 = 3 beats SA 5-0 = 5 (SA's 4 pops are on 1-4)
    assert all(holes[h]["winner"] == "M1:austin" for h in (5, 6, 7, 8))
    # holes 1-4: Austin 4-1 = 3, SA 5-1 = 4 -> Austin
    assert all(holes[h]["winner"] == "M1:austin" for h in (1, 2, 3, 4))


def test_chapman_team_skins_are_net_off_the_60_40_team_handicap():
    from email_parser.lsc_cup import compute_skins_payout
    sess = {"id": "pm", "format": "foursomes", "n_holes": 2,
            "matches": [{"id": "C1", "austin": [1, 2], "sa": [3, 4]}]}
    course = [{"hole": 1, "par": 4, "stroke_index": 1},
              {"hole": 2, "par": 4, "stroke_index": 2}]
    # team ball = the first partner's score (one ball per pair)
    scores = {1: {1: 5, 2: 4}, 3: {1: 4, 2: 4}}
    phs = {1: 0, 2: 5, 3: 0, 4: 0}        # Austin 60/40 = 0.6*0 + 0.4*5 = 2 strokes
    out = compute_skins_payout(sess, course, phs, scores, buyers={1, 2, 3, 4})
    g = out["groups"][0]
    holes = {h["hole"]: h for h in g["holes"]}
    assert out["basis"] == "net"
    assert holes[1]["status"] == "tied"                 # 5-1 = 4 vs 4
    assert holes[2]["winner"] == "C1:austin"            # 4-1 = 3 vs 4


def test_no_buyer_pair_cannot_win_or_tie_out_a_skin():
    # #1357-2: neither partner bought -> out of the hole entirely.
    from email_parser.lsc_cup import compute_skins_payout
    scores = _all_fours(range(1, 9))
    scores[5][1] = 3          # M2 Austin (no buyers) low on hole 1
    scores[1][1] = 3          # M1 Austin (buyers) ties it
    out = compute_skins_payout(_fb_session(), _flat_course(2), {}, scores,
                               buyers={1, 2, 3, 4, 7, 8})
    g = out["groups"][0]
    h1 = [h for h in g["holes"] if h["hole"] == 1][0]
    assert h1["winner"] == "M1:austin", h1           # the no-buyer 3 doesn't tie it out
    assert any(e["reason"] == "not bought in" for e in out["excluded"])


def test_singles_skins_stay_gross():
    from email_parser.lsc_cup import compute_skins_payout
    sess = {"id": "sun", "format": "singles", "n_holes": 1,
            "matches": [{"id": "S1", "austin": [1], "sa": [2]}]}
    out = compute_skins_payout(sess, [{"hole": 1, "par": 4, "stroke_index": 1}],
                               {1: 20, 2: 0}, {1: {1: 5}, 2: {1: 4}},
                               buyers={1, 2}, index={1: 5.0, 2: 5.0})
    assert out["basis"] == "gross"
    h = out["groups"][0]["holes"][0]
    assert h["winner"] == "S1:sa:2"                  # no pops: gross 4 beats 5


def test_team_skins_pops_use_each_players_own_tee_si():
    from email_parser.lsc_cup import compute_skins_payout
    sess = {"id": "am", "format": "fourball", "n_holes": 2,
            "matches": [{"id": "M1", "austin": [1], "sa": [3]}]}
    course = [{"hole": 1, "par": 4, "stroke_index": 1},
              {"hole": 2, "par": 4, "stroke_index": 2}]
    # player 1 plays a tee where hole 2 is the hardest
    si = {1: {1: 2, 2: 1}}
    phs = {1: 1, 3: 0}                  # 90% of 1 -> 1 pop
    scores = {1: {1: 4, 2: 5}, 3: {1: 4, 2: 4}}
    out = compute_skins_payout(sess, course, phs, scores, buyers={1, 3},
                               si_by_player=si)
    holes = {h["hole"]: h for h in out["groups"][0]["holes"]}
    assert holes[1]["status"] == "tied"          # no pop on hole 1 for player 1
    assert holes[2]["status"] == "tied"          # his pop lands on hole 2: 5-1 = 4


# ── Skins pane data (#1398): flight members in index order; the member
#    view keeps hole results and members, never money ─────────────────

def test_singles_flights_list_members_lowest_index_first():
    from email_parser.lsc_cup import compute_skins_payout
    sess = {"id": "sun", "format": "singles", "n_holes": 1,
            "matches": [{"id": "S1", "austin": [1], "sa": [2]},
                        {"id": "S2", "austin": [3], "sa": [4]}]}
    out = compute_skins_payout(sess, [{"hole": 1, "par": 4, "stroke_index": 1}], {},
                               {1: {1: 4}, 2: {1: 4}, 3: {1: 4}, 4: {1: 3}},
                               names={1: "Ann", 2: "Bob", 3: "Cy", 4: "Di"},
                               buyers={1, 2, 3, 4}, index={1: 9.0, 2: 1.0, 3: 15.0, 4: 12.0})
    f1, f2 = out["groups"]
    assert [m["name"] for m in f1["members"]] == ["Bob", "Ann"]
    assert [m["name"] for m in f2["members"]] == ["Di", "Cy"]


def test_member_view_keeps_holes_and_members_but_no_money():
    from email_parser.lsc_cup import compute_skins_payout, strip_money
    sess = {"id": "sun", "format": "singles", "n_holes": 1,
            "matches": [{"id": "S1", "austin": [1], "sa": [2]}]}
    sk = compute_skins_payout(sess, [{"hole": 1, "par": 4, "stroke_index": 1}], {},
                              {1: {1: 3}, 2: {1: 4}}, names={1: "Ann", 2: "Bob"},
                              buyers={1, 2}, index={1: 5.0, 2: 5.0})
    board = {"sessions": [{"id": "sun", "skins": sk, "matches": []}]}
    m = strip_money(board)["sessions"][0]["skins"]
    g = m["groups"][0]
    assert g["holes"][0]["status"] == "won" and g["members"][0]["name"] == "Ann"
    flat = repr(m)
    for k in ("pot_cents", "payouts", "cents", "unpaid_cents", "flags", "excluded", "mixed"):
        assert k not in flat, k


def test_pair_labels_use_an_ampersand():
    # Kerry 2026-10-08 (#1449): "Make the teams have an &, not / between the names."
    from email_parser.lsc_cup import compute_skins_payout
    out = compute_skins_payout(_fb_session(), _flat_course(2), {}, _all_fours(range(1, 9)),
                               names={1: "Luke Youngs", 2: "Chris Cannon"}, buyers=set(range(1, 9)))
    labels = {t["key"]: t["label"] for t in out["groups"][0]["totals"]}
    assert labels["M1:austin"] == "Luke Youngs & Chris Cannon"
    # the partners one by one, so the board can stack them (Kerry 10/9:
    # "Stack player names in team skins")
    assert out["groups"][0]["entries"]["M1:austin"]["names"] == ["Luke Youngs", "Chris Cannon"]


# ── Kerry 10/9 (verbatim): "So $575 available for each skins session.
#    Session pots standalone. Team skins is Net based off of full team
#    handicaps (not Off lowest) for that session. ... Singles is gross skins
#    and divides Sunday pot evenly between high and low flights." ──────────

def test_kerry_10_9_skins_rules_pinned():
    from email_parser import lsc_cup as L
    assert L.SKINS_PER_ROUND_CENTS == 2500             # $25 a buyer a session
    assert L.SKINS_TEAM_BASIS == "net" and L.SKINS_SINGLES_BASIS == "gross"
    assert L.SKINS_CARRYOVER is False
    assert L.SINGLES_FLIGHT_SHARES == (50.0, 50.0)     # evenly, high and low
    assert L.SINGLES_FLIGHT_BREAK == 12.0              # #1351-C, unchanged


def test_kerry_10_9_each_session_pot_is_standalone_575_with_23_buyers():
    cids = list(range(1, 29))                          # 28 players, 14 a side
    buyers = set(range(1, 24))                         # 23 bought the skins
    quads = [cids[i:i + 4] for i in range(0, 28, 4)]   # 7 team matches

    def team(p, swap=None):
        out = []
        for i, q in enumerate(quads):
            q = [swap.get(c, c) for c in q] if swap else q
            out.append({"id": f"{p}{i + 1}", "austin": q[:2], "sa": q[2:]})
        return out
    dial = {"event_id": 3329, "sessions": [
        {"id": "sat-am", "date": "2026-10-10", "format": "fourball", "n_holes": 1,
         "matches": team("A")},
        # buyer 23 sits out the PM for a non-buyer (99): the PM pot counts
        # only the buyers in the PM, nothing carries over from the AM
        {"id": "sat-pm", "date": "2026-10-10", "format": "chapman", "n_holes": 1,
         "matches": team("P", {23: 99})},
        {"id": "sun", "date": "2026-10-11", "format": "singles", "n_holes": 1,
         "matches": [{"id": f"S{i + 1}", "austin": [cids[2 * i]], "sa": [cids[2 * i + 1]]}
                     for i in range(14)]}]}
    course = [{"hole": 1, "par": 4, "stroke_index": 1}]
    index = {c: (5.0 if c % 2 else 15.0) for c in cids}
    data = {sid: {"course": course, "phs": {}, "scores": {}}
            for sid in ("sat-am", "sat-pm", "sun")}
    b = compute_board(dial, data, {}, {"buyers": buyers, "index": index})
    pots = {s["id"]: s["skins"]["pot_cents"] for s in b["sessions"]}
    assert pots["sat-am"] == 57500                     # 23 x $25 = $575
    assert pots["sat-pm"] == 55000                     # 22 in THIS session: standalone
    assert pots["sun"] == 57500
    sun = next(s for s in b["sessions"] if s["id"] == "sun")["skins"]
    assert sun["basis"] == "gross"                     # gross, two flights, split evenly
    assert [g["pot_cents"] for g in sun["groups"]] == [28750, 28750]
    sat = next(s for s in b["sessions"] if s["id"] == "sat-am")["skins"]
    assert sat["basis"] == "net" and len(sat["groups"]) == 1


def test_kerry_10_9_fourball_team_net_is_full_allowance_off_zero():
    # 90% of EACH player's PH taken off zero (a 20 gets 18 strokes) though
    # his opponents are scratch: never off the lowest in the match
    from email_parser.lsc_cup import compute_skins
    course = [{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 19)]
    sess = {"id": "am", "format": "fourball", "n_holes": 18,
            "matches": [{"id": "M1", "austin": [1, 2], "sa": [3, 4]}]}
    phs = {1: 20, 2: 10, 3: 4, 4: 4}
    scores = {c: {h: 4 for h in range(1, 19)} for c in (1, 2, 3, 4)}
    out = compute_skins(sess, course, phs, scores, basis="net")
    by = {h["hole"]: h for h in out["holes"]}
    # off zero: player 1 gets 18 (a stroke a hole), SA's 4s get 4 (SI 1-4):
    # holes 1-4 tie at net 3, Austin takes 5-18. Off the low man (4) would
    # have given player 1 only 14 and tied 15-18 instead.
    assert all(by[h]["status"] == "tied" for h in (1, 2, 3, 4))
    assert all(by[h]["winner"] == "M1:austin" for h in range(5, 19))
    # the board shows ONE ball per team per hole: the counting ball
    card = out["cards"]["M1:austin"]
    assert card["1"] == [4, 1] and len(card) == 18
