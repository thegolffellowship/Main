# Lone Star Cup live board (Track B)

*Directives: mailbox #654 (CA/Kerry), #655 (standards), #659 (design).
Shipped v2.489.0–.2 (2026-09-24). Owner: COO › Event Ops: Lone Star Cup
(session_01XsCfrW7UsaAy5VXEdv1Mnb). Scores come from Track A
(CTO › Live Score Entry); paper scorecards decide any disagreement on
cup day.*

## What it is

A Ryder Cup-style board on the member Lone Star Cup tab
(`/member/lonestarcup`): AUSTIN vs SAN ANTONIO points header with live
projections, session groups (Sat AM Four-Ball · Sat PM Foursomes ·
Sun Singles — the schedule ratified in the LSC How-It-Works popup),
and one Match Play card per match with live running margins and
tap-open hole-by-hole scorecards.

## How it computes

`email_parser/lsc_cup.py` — pure compute, guarded by
`tests/test_lsc_cup.py`:

- **Reuses, does not fork:** emits the SAME match-detail dict
  `gg_match_play.parse_match_play_detail` produces from Golf Genius,
  runs the same dormie-correct `_close_out_walk`, and the front end
  reuses `mpMatchCard` / `mpLiveLead` / the delegated card toggle from
  the Match Play tab. Team colors re-theme via the `--mp-slate` /
  `--mp-clay` CSS vars scoped inside `#lsc-board` only. Cup details
  carry `match_len` (GG details never do) so `mpMatchHoleCount` draws
  the full 18 on a closed-out card; CMP is untouched.
- **Handicapping (default, Kerry corrects via #659 Q3):** full
  difference of LOCKED playing handicaps off the match's low man,
  strokes on the lowest stroke-index holes. Four-ball: everyone off
  the low man of all four, best net ball counts (a partner without a
  score is a pickup). Foursomes: ONE team ball, strokes at team level
  = 50% of the combined-handicap difference. PHs come from Track A's
  locked snapshot — never re-derived here.
- **Points:** a final match pays `points_per_match` to the winner;
  halved pays `points_per_match × halved_match` (default 0.5) each.
  A live leader counts toward `projected` only.

## Dials (rules-as-data, set via scoring-setting-set)

- **`lsc_matches`** — the cup rules: `event_id`, `points_to_win`,
  `halved_match`, `board_live`, and `sessions:[{id, label, date,
  format: singles|fourball|foursomes, points_per_match, n_holes,
  se_round, matches:[{id, tee_time, austin:[cid…], sa:[cid…]}]}]`.
  Kerry sets the real pairings here; cids come from the frozen
  `lsc_roster_final`.
- **`lsc_mock_scores`** — `{<session_id>: {course:[{hole, par,
  stroke_index}], phs:{cid: ph}, scores:{cid: {hole: gross}}}}`.
  Feeds the same pipeline until Track A's `se_*` tables land; also the
  rule-3b staged preview. Missing holes are ABSENT, never zero.
  Cleared before cup weekend.

## Rule-3b gate (member visibility)

`GET /api/lsc/board` (member tier) returns `{configured: false}` until
the `lsc_matches` dial exists — and, while `board_live` is false, for
every non-staff session. Admin/manager sessions always get the board,
so Kerry previews the staged demo on his phone signed in as staff.
Nothing member-visible until Kerry flips `board_live` after his OK.

## Wiring plan (Track A)

When Track A's read shape lands (#657/#658): bind each session's
`se_round`, prefer real entered scores over `lsc_mock_scores` in
`lsc_board_payload`, keep the 15s poll + versioning server-side.
Foursomes needs one team score line from entry — flagged in #659.
The Fri 10/9 practice round renders a plain gross leaderboard from the
same feed (no matches that day).
