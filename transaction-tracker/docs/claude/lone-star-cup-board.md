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

## Kerry's format rulings (CA #717, 2026-09-26, rule 3b) — in the engine v2.501.0

- **Points:** 1 for a win, ½ for a halve, the same in every format
  (`POINTS_WIN` / `POINTS_HALVE`, event level — a per-session value no
  longer changes a payout).
- **Tiebreak:** level points = the **defending champion keeps the cup**.
  `cup_status()` decides: the champion clinches at exactly half the
  points, the challenger has to pass half. `defending_champion` in the
  dial stays EMPTY until Kerry names the 2025 winner (the repo has the
  GG archive rows but not the result, so nobody guesses); with none
  recorded a finished tie reads `tied_pending`.
- **CTP: none. Skins instead**, scored by `compute_skins()`, SEPARATE
  from the match: team skins in team sessions, individual skins in
  singles; holes after a close-out count for skins only and never touch
  the match; a picked-up ball never wins; a hole is decided only once
  every entry has posted it. Net strokes = full locked PH off zero,
  plus handicaps get nothing on a hole. **Still Kerry's:** net or gross,
  the pot, carryovers — so the board shows skins only once
  `skins.basis` is set (`carryover` supported, off).
- **Handicap allowances: PENDING.** The team format may be Greensomes
  (60% of the low + 40% of the high); the engine HOLDS 50% of combined
  until Kerry confirms.
- **Match play pickups (Track A, v2.496.0):** a hole marked Picked up
  can't win; both sides picked up = a push. Score entry stays open after
  a match is decided (Track A, CA #717).

## Dials (rules-as-data, set via scoring-setting-set)

- **`lsc_matches`** — the cup rules: `event_id`, `defending_champion`
  (austin|sa|null), `skins: {basis: null|net|gross, carryover}`,
  `board_live`, optional `points_win` / `halved_match` overrides, and
  `sessions:[{id, label, date, format: singles|fourball|foursomes,
  n_holes, se_round, matches:[{id, tee_time, austin:[cid…], sa:[cid…]}]}]`.
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

## Wiring plan (Track A) — per CA rulings #661 (2026-09-25)

- **Read shape RULED: rounds plural, event-scoped.** One event read
  carries `rounds: [{round_id, date, label, holes, course, groups,
  players}]` and ONE version for the whole event (Event Builder
  ladder: EVENT → ROUND → NINE → HOLE). `?round_id=` stays as an
  optional filter. 15s poll with since_version + 304 stands.
- Each `lsc_matches` session binds by `se_round` = that read's
  `round_id`. When the feed exists, `lsc_board_payload` prefers real
  entered scores over `lsc_mock_scores`.
- **Foursomes team row RULED in scope for Track A** (#661 item 2):
  se_hole_scores accepts a pair-keyed entry with both customer_ids and
  one gross per hole. The engine's foursomes path already scores one
  team ball however it's keyed.
- **Playing handicap comes from the locked handicap ONLY** (#661 item
  4). This module never derives it a second way — it reads the PH the
  feed carries, full stop. (The nine-hole stroke-allocation convention
  open in CA Queue #10/#11 doesn't touch the cup: 18-hole rounds.)
- The Fri 10/9 practice round renders a plain gross leaderboard from
  the same feed (no matches that day).

*Rule-3b record: the member gate missed its intended commit on
2026-09-24, caught by the lane's own push check before any deploy
exposed the board — CA logged it as strike one (#661 item 3). A second
slip on a member-facing gate stops Track B.*

## Shirt notes (CA #716)

`oneoff_shirt_notes` `{"<event_id>": {"<cid>": "note"}}` marks a pick in
`oneoff_shirts` as UNCONFIRMED (Luke Youngs' L was Kerry's guess for the
FootJoy order). The SHIRT column shows it amber with a "?"; the boot
seed never copies a noted pick onto `customers.shirt_size`; a size
picked in the column confirms it and clears the note.
