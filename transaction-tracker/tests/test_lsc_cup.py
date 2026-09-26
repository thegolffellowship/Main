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
    board = compute_board({"sessions": [sess],
                           "skins": {"basis": "gross"}}, data)
    m = board["sessions"][0]["matches"][0]
    assert m["state"] == "final" and m["gg_margin"] == "10&8"
    assert m["points"] == {"austin": 1.0, "sa": 0.0}
    sk = {r["key"]: r["skins"] for r in board["sessions"][0]["skins"]["totals"]}
    assert sk == {"S1:austin:1": 10, "S1:sa:2": 8}


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


def test_board_holds_skins_until_kerry_rules_the_basis():
    from email_parser.lsc_cup import compute_board
    sess = {"id": "sun", "format": "singles", "n_holes": 1,
            "matches": [{"id": "S1", "austin": [1], "sa": [2]}]}
    data = {"sun": {"course": _flat_course(1), "phs": {},
                    "scores": {1: {1: 3}, 2: {1: 4}}}}
    board = compute_board({"sessions": [sess]}, data)
    assert board["skins_pending"] is True
    assert board["sessions"][0]["skins"] is None


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} passed")
