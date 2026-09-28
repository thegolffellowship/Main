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
  points, the challenger has to pass half. **San Antonio won the 2025
  cup (Kerry, CA #753, 2026-09-27): the live dial carries
  `defending_champion: "sa"`**, so a finished tie reads "SA retains".
  With no champion recorded a finished tie would read `tied_pending`.
- **CTP: none. Skins instead** (CA #717), scored by `compute_skins()`,
  SEPARATE from the match: team skins in team sessions, individual in
  singles; holes after a close-out count for skins only and never touch
  the match; a picked-up ball never wins; a hole is decided only once
  every entry has posted it.
- **Skins PAYOUT, ratified (CA #725/#726, v2.503.0), STAFF ONLY** —
  `compute_skins_payout()`: GROSS, no carryover (a tie pays nothing).
  Each 18 is its own pot: $25 × the players IN THAT ROUND who bought the
  weekend skins (the SKINS add-on in `oneoff_addons`). Saturday: team
  skins (four-ball best gross ball, Chapman one gross), each team skin
  split evenly between partners. **Mixed pair (only one partner bought),
  RULED CA #759, BUILT v2.514.0:** the team plays for team skins and
  the partner who bought in is paid the FULL team skin; nothing is
  left over or redistributed. A pair where neither bought stays out.
  Staff see who is paid on a mixed team (`mixed`); members never do.
  Sunday:
  individual gross skins flighted on the TGF 18-hole index FROZEN at the
  event (`_event_index_as_of` → `_handicap_index_18_by_customer`):
  Flight 1 < 12.0, Flight 2 ≥ 12.0, half the pot each; a player with no
  index is flagged; flights flagged when one is ≥ 2× the other (or
  empty). Exact cents (`match_play.allocate_cents` / `split_cents`).
  Money hold: `held` until every entry posts every hole. `strip_money()`
  removes every amount and flag for non-staff in `/api/lsc/board`.
- **Handicap allowances: RATIFIED (CA #721, v2.502.0)** — USGA/WHS
  Appendix C: singles 100% (full difference); four-ball 90% of each
  player, all off the low player; the team session is **CHAPMAN**
  (Pinehurst), team handicap = 60% of the lower partner + 40% of the
  higher, the higher team gets the difference. WHS order: allowance →
  `whs_round` (half up) → difference, applied on the locked PH (= course
  handicap at 100%). `session_handicaps()` is the one helper; match and
  net skins both read it. "foursomes" / "alternate shot" normalise to
  Chapman — the old 50%-of-combined is gone. Members see "Chapman".
- **Pop dots before play:** each hole carries `p1_pops` / `p2_pops` (the
  side's strokes before anyone plays it; singles and Chapman) and the
  detail carries a per-player `strokes` map (four-ball). `p*_strokes`
  remain the COUNTING ball's strokes on a played hole.
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

- **`lsc_tentative`** (staff only; nothing reads it) — a player who
  looks likely but hasn't accepted or paid, kept OFF `lsc_roster_final`
  (members see that roster) until he confirms and Kerry OKs the roster
  change. `{"3329": {"San Antonio": [{customer_id, status, accepted,
  paid, pay_expected_by, shirt_size, ...}]}, "shirt_style": {...}}`.
  First use: Michael Mesa (703), SA's 14th, 2026-09-28 (#871/#872).
  If he confirms, the cup is 14 v 14: 7 + 7 + 14 = 28 points, SA
  retains at 14; if not, the 14 v 13 draft stands.

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

## 14 v 13: the odd player (Kerry 2026-09-28, in session) — BUILT v2.514.0

Kerry: the side with the odd player sends him into a THREESOME against
the other side's spare pair (their 13th and 14th players): two singles
matches at once, "one whole point available for each of those
matches". On Saturday the odd player and the two he faces switch
between the AM four-ball and the PM Chapman so the same people aren't
involved twice: 4 singles points on the day. Sunday works the same way:
one player plays two opponents at once. Kept general, "something we
need to always have in our back pocket for future match play events
that have team matches".

- **14 v 13 (if Mesa doesn't play):** Saturday 6 team matches + 2
  singles per session = 16; Sunday 13 singles + the double = 14 → **30
  points**, SA (defending) retains at 15, Austin needs 15½. Nobody sits,
  so the sit-out credit (#787) doesn't arise.
- **Engine (`lsc_cup.py`):** `match_format()` plays a one-v-one match
  inside a team session as SINGLES at 100% (a match may also name its
  own `format`). `skins_team_sides()` counts the odd player ONCE in team
  skins and makes the two he faces ONE team entry, their better ball
  (Kerry: "SA single vs Austin pair"); in singles skins a player in two
  matches is one entry. The dial just lists the odd player in both
  matches.
- The earlier draft (sit one player / one pair each session, 25 points,
  #757) is superseded.

## Handicaps and races (Kerry, CA #787 items 1–2)

- **No cup round posts to TGF handicaps** — not the four-ball, Chapman or
  singles, nor the Friday practice round (3330). Closeout skips the post
  and the card for 3329/3330.
- The board's handicaps read the LOCKED pre-cup index, unchanged: match PHs
  come from Track A's locked snapshot, and Sunday's skins flights read
  `_event_index_as_of` (the index in effect the morning the event starts).
- **The cup feeds no points race** (not Fall NET, not Monthly). Nothing in
  `lsc_cup.py` writes to handicaps, points or standings.
