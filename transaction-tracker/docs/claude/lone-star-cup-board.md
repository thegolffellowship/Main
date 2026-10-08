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
  `compute_skins_payout()`: no carryover (a tie pays nothing).
  **Basis by session (Kerry 2026-10-07, #1357-1, v2.525.19):** Saturday
  TEAM skins are NET at the full session allowance taken off zero, never
  off the lowest in the match (four-ball 90% of each PH, best net ball;
  Chapman the 60/40 team handicap, one net ball), with pops on each
  player's own tee's stroke index; Sunday singles stay GROSS
  (`SKINS_TEAM_BASIS` / `SKINS_SINGLES_BASIS`).
  Each 18 is its own pot: $25 × the players IN THAT ROUND who bought the
  weekend skins (the SKINS add-on in `oneoff_addons`). Saturday: team
  skins (four-ball best net ball, Chapman one net ball), each team skin
  split evenly between partners. **Mixed pair (only one partner bought),
  RULED CA #759, BUILT v2.514.0:** the team plays for team skins and
  the partner who bought in is paid the FULL team skin; nothing is
  left over or redistributed. A pair where neither bought is out of the
  hole entirely: its score neither wins nor ties out a skin (#1357-2).
  Staff see who is paid on a mixed team (`mixed`); members never do.
  **SKINS PANE (v2.525.25, #1398, mockup `docs/claude/lsc-mockups/Skins.dc.html`):**
  `lscSkinsPane` in contests.html, every session with the selected one first:
  a row per won hole (team/player + count), tied holes on one line, open
  holes on one line; Sunday shows each flight's size and lowest-to-highest
  index range (`groups[].members` from `compute_skins_payout`). `strip_money`
  keeps holes/members/entrants for members (no money); pot, payouts, flags
  stay staff only. Guard `test_lsc_skins_pane.js`.
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

## Pivots when someone withdraws (Kerry 2026-09-28) — BUILT v2.515.0

"There's always also the possibility that someone would have to WD due
to injury. We'd need ability to pivot quickly, adjusting formats in
worst case scenarios." Example he gave: 13 v 13 on Saturday PM after
13 v 14 in the AM leaves ONE singles match for the odd players, 1 v 1,
and "skins would still apply if they were able to get one on their own".

- **Re-pair a session:** edit that session's `matches` in `lsc_matches`
  (the dial is per session, so AM and PM can differ). A 1 v 1 inside a
  team session plays as singles at 100%; the odd players are each their
  own skins entry. Then run **`scoring-lsc-check`** (read-only): match
  count and points per session, and every problem `validate_matches`
  finds (a player on both teams, in two team matches, in more than two
  matches, an empty side, a bad recorded result, a stray withdrawal).
  The staff board carries the same list as `dial_warnings`.
- **A match an injury stops, or a concession:** put
  `"result": {"winner": "austin"|"sa"|"halved", "note": "..."}` on the
  match. It reads FINAL with that result ("Conceded" / "Halved" unless a
  `margin` is given). Which way an injury goes is staff's call case by
  case; the board never guesses. The note is staff-only.
- **Skins after a mid-round withdrawal:** list him in the session's
  `withdrawn`. An entry made only of withdrawn players stops holding
  holes open (the money hold); the scores he posted still count.

## Results snapshot — BUILT v2.515.0 (Kerry 2026-09-28: "go ahead")

`scoring-lsc-results` reads the status (snapshot held? what would block
a freeze now?). `scoring-lsc-results:freeze` stores the final board in
the **`lsc_results`** app setting: points, every match, and the staff
skins payouts. It refuses while a match is open or a skins group with
entrants is still held; `freeze|force` stores it anyway with the
blockers recorded. From then on `/api/lsc/board` serves the snapshot
(`source: "final"`), so a later score edit can't change the result
(principle 4). `:clear` goes back to live computing. No schema, no money
moves. The recap and closeout read the snapshot.

## The Hideout's card — LOADED 2026-09-28 (course 65112)

From Kerry's GG tee screenshots, via Tracker Build's `scoring-course-card`:
Gold 73.7/131 (7,003), Blue 71.7/129 (6,543), White 69.7/124 (6,109),
Red (M) 66.7/117 (5,453), Teal (F) 69.4/118 (4,979), each with front
and back nine ratings. Par 37/35/72 on every tee. The four men's tees
share one stroke-index order; **Teal has its own.** Tees 14680-14684.
**Bands (Kerry 2026-09-28: players play our standard yardage brackets;
"the 7000 yard tees wouldn't be played"):** set with `scoring-tee-bands-apply`
from the yardage standards, and it matches Kerry's own GG numbering
(0 - Gold, 1 - Blue, 2 - White, 3 - Red, 4 - Teal): **Blue <50 (6,543),
White 50-64 (6,109), Red 65+ (5,453), Teal Forward (4,979); Gold not
played.**

**Each player's tee: `lsc_tees`** (staff only): the tee of his usual 2026
band ("check where they normally play"), with the order count as the
source. 12 Blue, 12 White, Hogue Red, Mary Wade Teal. To confirm:
Barstow (62) and Wetz (672) have no 2026 TGF orders; John Wade (4) is
13 <50 / 10 50-64 (latest <50); Julius Jenkins (304) 2 of 3. Track A
seeds the cup rounds' player tees from it.

**Handicaps across tees (Kerry 2026-09-28): WHS.** Course handicap from
the player's OWN tee (index x slope/113 + rating - par,
`handicap_calc.course_handicap`), then the session allowance, then off
the lowest. **Where strokes fall (v2.516.0):** each player takes his
strokes on the stroke index of the tee he plays (`si_by_player`, read
from the course record by the seat's tee name or band), so Mary Wade on
Teal gets hers on Teal's SI 1-3 (holes 4, 16, 9), not the men's (4, 14,
3). Singles and four-ball, per player.

**Chapman pairs on two tees (Kerry 2026-09-28, BUILT v2.517.0):** WHS
sets each partner's course handicap and the 60/40 team allowance, and
the Rules of Golf let the Committee set each partner's tees, but which
stroke-index table a mixed pair plays on is left to the Committee. TGF's
term of competition: **a pair takes its strokes on the men's stroke
index when either partner plays a men's tee, and on the women's when
both play women's tees.** The tee's gender comes from the course record
(`tee_gender`, beside `si_by_player`); tees that can't be resolved keep
the round's list.

## Handicaps and races (Kerry, CA #787 items 1–2)

- **No cup round posts to TGF handicaps** — not the four-ball, Chapman or
  singles, nor the Friday practice round (3330). Closeout skips the post
  and the card for 3329/3330.
- The board's handicaps read the LOCKED pre-cup index, unchanged: match PHs
  come from Track A's locked snapshot, and Sunday's skins flights read
  `_event_index_as_of` (the index in effect the morning the event starts).
- **The cup feeds no points race** (not Fall NET, not Monthly). Nothing in
  `lsc_cup.py` writes to handicaps, points or standings.

## Events-list paid badge — v2.524.3 (Kerry 2026-10-04)

Kerry: "Can you mark the tracker accordingly in the badge? It shouldn't
only be shown as one paid." The Cup's 28 roster rows are RSVP-only
placeholders (all on event_id 3329); the money arrives by Venmo/Zelle
into `expense_transactions`. The players/paid badge therefore reads
`oneoff_paid` from `get_oneoff_roster_finance` (balance settled =
entry $250 + the add-ons in `oneoff_addons`, lodging deducted), not the
count of active order rows, on BOTH the desktop table and the phone card
(the phone card read `registrations` and showed 1 until v2.524.3). On a
team event the count is the frozen roster only; off-roster money (James
Wilson Jr's $325, McCrary's unrefunded $150) stays in the money view and
is not a paid player. Placeholder rows are left as they are: converting
them to Paid Separately would book allocations on top of the held
deposit ledger. Guard: `test_oneoff_paid_badge.py`.

## Roster swap, payments and format prep — 2026-10-05 (CoS #1206–#1210, Track B #1215)

- **Marques out, Walter Hogue in (Kerry).** Walter (cid 834, Jay's brother)
  takes Marques's Austin seat "PLAYERS CUP · 2" on `lsc_roster_final`
  (seat carries `replaced` and `age: 69`); Marques moves to Austin's
  `declined` list (withdrew 10/5, paid $0, no refund). `lsc_accepted`
  swaps 14 → 834. Walter: starting handicap 10.9 (#1207), 1st Timer, Red
  tee (65+ bracket, `lsc_tees`), shirt = Marques's freed XL set (no 2XL
  exists in the order; `oneoff_shirt_notes`). Do NOT re-freeze the roster
  from standings: it would drop Walter.
- **Payments (all linked to 3329 with `scoring-expense-event`):** Peterson
  2726 $325 and Julius Jenkins 2729 $175 ("Mr Bozack", Kerry) → both
  entry + skins, marked SKINS; Matt Jenkins 2730 $210 → balance + Friday,
  marked FRI (practice roster row 3042). Kerry's own seat is comp:
  `oneoff_charges` override `18 → 0` (Kerry 10/4, "Yes I should be paid").
  Jay Hogue's $540 (2725) is unapplied pending Kerry: on totals he is
  $160 over ($1,015 in vs $250 + $75 + $530 room).
- **Format stays open** until both captains answer (Sat PM `chapman` or
  `fourball` is one field on the `sat-pm` session). Kerry's flighted draw
  is a proposal: pools sort PAIRS by session team handicap (3 low pairs =
  matches 1–3, 4 high = 4–7); a match may carry a `pool` label, which the
  engine ignores. No draw screen exists; a Zoom draw is entered into
  `lsc_matches` by hand afterward (settings write, no push).
- **Pars:** every Hideout tee is par 72 (37/35), so no relative-par
  adjustment applies across Blue/White/Red/Teal.
## FOLLOW THE CUP from a scorer link — v2.525.19 (Kerry 2026-10-07, #1357-6)

A scanned scoring link lands on SCORE THIS GROUP / FOLLOW THE CUP (score-entry.md).
FOLLOW opens `/member/lonestarcup?match=<dial match id>`: `lscBoardRender` stamps
`data-lsc-match` on every card, opens that one once (`mpCardToggle`) and scrolls to
it, and re-opens whatever cards were open before each 20 s live refresh. The per-group
QR signs for the Cup's rounds print from `/events/<id>/cup-signs`.

## Austin pairs + Wetz's index — 2026-10-07 (CoS #1382, Side Games #1383-2)

- `lsc_matches.pairs.austin` (settings write, no push): AUS-P1 L. Youngs/Cannon 8,
  P2 Cloer/J. Wade 12, P3 Jay/Walter Hogue 13 (low pool); P4 Wetz/Barstow 25,
  P5 Franz/Sharp 40 (high). P6 McDonnell + one Jenkins and P7 the other two
  Jenkins are `held` until Kerry says which Jenkins (Matt 7 / Mike 294 /
  Julius 304) partners McDonnell. Every combination lands 15–38, above the low
  cut of 13, so the split is settled; the closest is Matt+Julius 15. Re-derive
  at the 10/10 lock.
- **Wetz (672) had no index on the by-customer map** although his 7.7 starting
  handicap was stored: old DFW rounds sit under his name with no handicap link,
  and the starting merge left that row's `customer_id` empty. That map feeds the
  Cup seed's playing handicaps (`score_entry.cup_seed` → `_preview_handicaps`)
  and the Sunday skins flights, so his matches would have seeded with no PH. No
  data-only fix exists (no link-writer bridge; `relink_all_unlinked_players`
  only fills existing link rows). Code fix v2.525.20
  (`get_all_handicap_players` stamps the cid), guard
  `test_starting_handicap_by_customer.py`, rides Thursday's push.

## HANDICAP LOCK — 2026-10-07 (Kerry via CoS #1389) — v2.525.21

KERRY: "Handicaps should lock now. They won't change." Staff setting
`lsc_handicap_lock` = `{"3329": {"players": {"<cid>": {name, team, tee, index,
ch, sun_flight}}}}`, from the 10/5 list (#1215) with Wetz 7.7, Walter 10.9,
Wilson 12.4 and Mesa 0.4 (his stored starting handicap; #1389 said 0.2, CH 0
either way). CH = whs_round(index × slope/113 + (rating − 72)).
- `score_entry.cup_seed` takes the locked CH as each player's playing
  handicap in all three sessions (the dry run reports `handicap_lock`).
- `lsc_cup._skins_ctx` takes the locked index for the Sunday flights
  (Flight 1 < 12.0): 11 v 11 among the 22 buyers.
- Pools in `lsc_matches.pairs` are summed from the lock. No re-derivation on
  10/10. Why it matters: by 10/7 Wilson's live index was 10.8 (CH 6, Flight 1)
  and South's 10.0 (CH 9).
- Sunday Low 7 | High 7: SA has four at CH 8 (Baker, Mazanec, South, Wilson);
  by index Wilson is 8th, so High.

## STAFF PREVIEW — /events/3329/cup-preview (Kerry 10/7, CoS #1398)

Every Cup screen on demo rounds behind one jump bar, in a phone frame, with a
red "PREVIEW · demo scores" band. Admin only, never linked from a member page.

- **Engine:** `email_parser/lsc_preview.py` (`build_dial` / `seed` / `teardown`).
  The demo lives on its OWN dial `lsc_preview_matches` (`se.PREVIEW_DIAL`) and
  on score-entry rounds keyed `lscprev:<session>` and labelled
  `se.PREVIEW_LABEL · FOURBALL|FOURSOMES|SINGLES`, so `entry_publish` refuses
  them and `entry_mode` (Finding 0) ignores them. The live `lsc_matches` dial,
  the live rounds and the member board are never touched.
- **Seed state (#1398):** FOURBALL all 7 matches final with full cards, one
  picked-up ball and one hole where every ball was picked up (the round stays
  OPEN so its scoring links still open the finished card; a closed round
  revokes every link). FOURSOMES live thru 9–13, match 1 closed out 2&1
  (written net of the board's own pops, so it holds whatever the handicaps).
  SINGLES not started. The seeder's scorer seat is released on every group
  except FOURSOMES group 2, which is the HELD screen
  (`se.release_preview_seed_locks`, PREVIEW rounds only).
- **Board:** `/api/lsc/board?preview=1` returns `lsc_cup.preview_board_payload()`
  for an admin/manager session only; anyone else gets the live board. The
  contests page passes `?preview=1` through and shows the red band.
  `round_matches` reads both dials; `_cup_standings` uses the preview payload
  for a preview-bound round.
- **Bridge:** `scoring-lsc-preview:seed` (dry run) · `seed|apply` · `teardown`.
- **Screenshots:** `docs/claude/screenshots/lsc-preview/`.
- **Teardown** before the live round opens Saturday (closes the PREVIEW
  rounds, clears the dial).

## EVENT INFO — /member/lonestarcup/info (Kerry 10/8, CoS #1428) — v2.525.25

`templates/lsc_info.html`, route `member_lonestarcup_info` in app.py. Public
like the member Cup page; no dollars. SCHEDULE | TEAMS | FORMATS from
`docs/claude/lsc-mockups/EventInfo.dc.html` (byte-exact, raw-index wording),
one tab at a time; anchors `#schedule #teams #formats #fourball #foursomes
#singles #skins` (Track A's HOW IT WORKS pill links to the format anchors and
highlights that row). TEAMS reads `lsc_matches.pairs` (low pool, then high
pool, by combined index when the dial carries it, else combined CH); a last
name shared on the roster shows the first name too. Captains are the
mockup's (`LSC_CAPTAINS`). "Match draws" reads "posted after Thursday's
draw" until every session has its 7+ matches. Share link / Download PDF
(print CSS shows all three sections). Guard `test_lsc_info.py`.

The staff preview header is one slim line that folds to a "PREVIEW ▾" tab
after the first jump (Kerry 10/8: "the preview header is really in the
way"); Event Info is its first stop. Logo: `static/lsc-logo.png` (sha256
8d771633…, CoS MANIFEST #1416).

## THE DRAW — /events/3329/cup-draw (Kerry 10/8, CoS #1432) — v2.525.29

The Chief of Staff's draw board (`cup_draw.template.html`), ported as is to
`templates/cup_draw.html`, admin only, screen-shared on the draw Zoom. Data
and the one write path: `email_parser/lsc_draw.py`.
- **Entrants:** Saturday = `lsc_matches.pairs` (low/high pool by combined
  raw index; labels from the lock); Sunday = `lsc_handicap_lock.players`
  per team by locked index, Low 7 / High 7.
- **Each landed match** is written into its session of `lsc_matches` via
  `POST /api/events/<id>/cup-draw/land` {session fb|fs|sg, pool, a, s}. The
  server re-checks: entrant in pool and undrawn; FOURSOMES only after its
  FOURBALL pool is full; no FOURBALL repeat; the rest of the pool still
  completable (canComplete). Match = `{id SAT-AM-n|SAT-PM-n|SUN-n,
  tee_time, austin, sa, draw: {pool, a, s, n}}`; n = tee order (Saturday 1-3
  low, 4-7 high; Sunday 1-7 low, 8-14 high), tee = session start + 10 min per
  match, two per tee on Sunday. The first drawn match in a session drops the
  session's STAGED (no `draw`) matches. se_round and board_live untouched.
- **Clear** (`/clear` {session}) removes drawn matches; FOURBALL takes
  FOURSOMES with it. Every land/clear writes agent_action_log (`cup-draw`).
- **After the draw** the Cup seed (`scoring-se-cup-seed:3329|apply`, Track B)
  still makes the session rounds and scoring links.
- Guard `test_lsc_draw.py` (production-shaped dial and lock).

## CART SIGNS — /events/3329/cup-cart-signs (CoS #1397-2) — v2.525.30

`templates/cup_cart_signs.html` from `docs/claude/lsc-mockups/CartSign.dc.html`
(cart_signs.html shape, team band, Cup logo `static/lsc-logo.png`), data from
`app.cup_cart_signs_data` over `score_entry.cup_sign_sheets` (now carries each
player's `side` and `match_id`, and takes `round_key_prefix`). One sign per
cart pair = a group's Austin players, then its SA players; QR = the group's
scoring link. `?session=sat-am|sat-pm|sun`; `?preview=1` reads the demo
(`lscprev:`) rounds. Empty until the Cup seed after the draw. Guard: the
cart-sign checks in `test_lsc_preview.py`.
