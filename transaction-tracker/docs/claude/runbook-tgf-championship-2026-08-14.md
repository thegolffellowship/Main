# Runbook — 2026 TGF CHAMPIONSHIP (Fri 08-14 practice · Sat/Sun 08-15/16, Lost Pines)

Second live outing for the Test Center, first on a MULTI-DAY event.
**Golf Genius remains the official scorer all weekend.** We shadow, we
diff, we record payouts afterward. Nothing here changes a score, a
payout, or a member-facing surface on its own.

Pre-flight run 2026-08-12 (Wed) by tracker-claude; findings below.

## The event

| | |
|---|---|
| Event | `2026 TGF CHAMPIONSHIP` (events.id 3291) |
| Days | Fri 08-14 practice (no games) · Sat 08-15 · Sun 08-16 |
| Course | Lost Pines (course_id **22819** — see finding 1) |
| Field | **35 active** (33 paid + 2 comp) as of Wed 08-12 |
| Games | Day-vocabulary event: YES/SAT/SUN/NO (v2.211.0), bucket accounts drive purses |

Buyer split (drives the pools — re-read on the day, late adds self-correct):

- **Full bundles ($100, both days + combined): 27** after the event-link fix
- **Single-day ($30):** Larson SAT + the Aug-10 one-day buyers (Doggett ×2,
  McCormick, Thompson — day from their WHICH DAYS? order notes / dial)
- **No games:** South, Williams ($170 One Day no games), Kaleb's unnamed
  practice-only guest
- Opt-out: **Carlos Zapata** out of Team Net (both days) + Individual Net
  ($36 credited, item 2523; `champ_subgame_optouts` dial) — still in
  Skins, CTPs, Individual Gross

Per-game rates (Kerry 2026-08-07, ratified): Daily $30 = Team Net $8 +
Skins $18 (2 flights) + CTPs ×4 $4 · Combined $40 = Ind Net $20 + Ind
Gross $20.

## Pre-flight findings (2026-08-12)

1. **Lost Pines course data is EMPTY on the current row.** course_id
   22819 ("Lost Pines") holds **0 tees, 0 rounds**; all tee data (White
   133/72.2, Green 126/68.8, Red(L) 129/70.5 — 18-hole rated) and 74
   imported rounds sit on the ARCHIVED row 29653 ("…-OLD - Archived on
   08-27-2025"). **The course-coverage guard will fire until the GG
   event import accretes tees onto the row the import resolves.**
   → **Thursday must-do:** as soon as GG publishes the event, run the
   scorecard import (`scoring-import:<event_code>` with the tournament
   widget URL). Then open the Test Center and confirm NO coverage
   banner. If the import resolves to a different Lost Pines row than
   22819, note it — do NOT hand-merge courses on event week.
2. **Event-link gap (FIXED, v2.231.0).** Eleven Aug 9–10 orders had
   `event_id NULL` (the backfill only ran at boot), so the pools were
   sized off 22 bundles instead of 27 and those players' GAMES cells
   read NO. `backfill_event_links()` now runs after every inbox check;
   Add Player / Add Payment stamp event_id at insert. Verified counts
   and re-derived purses are in the section below.
3. **Kaleb McDonnell has TWO rows by design:** his own Full Weekend
   ($525, id 2535) + an unnamed guest's Practice Round Only ($120, id
   2536, `guest_name` empty). → **Kerry: assign the guest's real name**
   (roster Assign Guest action) so Friday's tee sheet reads right.
4. **Two players have no tee choice:** Bill Barstow (id 2517) and
   Julius Jenkins (id 2511) — both manual adds. → set before pairings.
5. **GG portal reachable** (tgf-austin.golfgenius.com live, schedule
   page 5790750; league manager contact James Jones). The schedule
   renders via widget — use the proven widget-route recipe for import.
   The event was not yet published at pre-flight time.
6. **Handicaps:** roster HCP column populates from the canonical
   handicap tables (items.has_handicap is a dead field — ignore it).
   Playing-handicap projection (`project_playing_handicaps`) needs the
   GG import first → run it Thursday after the import and chase anyone
   blank. Run the GG handicap CSV export/upload before Friday.

## Purses (derived, real money — verified after the v2.231.0 relink)

Derivation: SAT/SUN = $30 × (full + that day's singles) − opted-out
rates · COMBINED = $40 × full − opted-out rates. Re-run any time with
`scoring-champ-buckets`; numbers move with the roster by design.

Verified after the v2.231.0 relink (Wed 08-12, 27 full bundles, 5 SAT
singles — Larson, B. Doggett, H. Doggett, McCormick, Thompson — all
self-assigned from order notes; 0 unassigned):

| Bucket | Purse | Math |
|---|---:|---|
| SATURDAY | **$952** | 30 × (27+5) − $8 Zapata Team Net |
| SUNDAY | **$802** | 30 × 27 − $8 Zapata Team Net |
| COMBINED | **$1,060** | 40 × 27 − $20 Zapata Ind Net |

Pre-fix these read $682 / $652 / $860 — the eleven unlinked orders were
worth $270 / $150 / $200 of pool money.

## PAYOUT SCHEDULE OF RECORD (Kerry-ratified 2026-08-12: "Lock those.")

**Robert Straiton runs the weekend** (Kerry is away — family). The GAMES
tab on the event shows this same schedule live (the
`event_payout_schedules` dial, v2.232.0), with a LOCKED banner.

| Day | Game | Pot | Pays |
|---|---|---:|---|
| SAT | Skins (2 flights, capped $10/hole) | $360 | $180/flight ÷ skins won |
| SAT | Team Net | $360 | 1st $240 / 2nd $120 (2/3–1/3) |
| SAT | Closest to Pin ×4 | $232 | $58 per hole |
| SUN | Skins (2 flights, capped $10/hole) | $360 | $180/flight ÷ skins won |
| SUN | Team Net | $250 | winner-take-all |
| SUN | Closest to Pin ×4 | $192 | $48 per hole |
| COMB | Individual Net (2 flights) | $520 | per flight $260: $130/$78/$52 (50/30/20) |
| COMB | Individual Gross (4 flights) | $540 | F1 $120/$60 (incl. $60 top-cut, 2/3–1/3) · F2–4 $80/$40 |

**Weekend total $2,814** = the three bucket purses exactly. Up to 27
fixed checks + variable skins. Zapata is OUT of Team Net (both days) and
Ind Net; IN Skins/CTP/Ind Gross.

The skins cap frees $216 SAT / $126 SUN from the uncapped derivation;
the reallocation to Team Net (+$112 / +$42) and CTP (+$104 / +$84) is
part of the lock. **Dollar figures are locked for the 08-12 field (32
SAT / 27 SUN / 27 combined).** If anyone buys in or drops before
Saturday, the bucket purses recompute — re-derive and re-confirm the
per-game numbers with Kerry/Robert rather than assuming the ratios.

## Thursday (08-13) checklist

1. GG event published? → run the scorecard import; confirm Test Center
   shows no coverage banner, 18 holes, correct par.
2. `project_playing_handicaps('2026 TGF CHAMPIONSHIP')` → chase blanks.
3. GG handicap CSV export → upload in GG.
4. Kerry: name Kaleb's guest; set Barstow/Jenkins tees; seed pairings.
5. Re-run `scoring-champ-buckets`; read the counts OFF THE PAGE — do
   not trust this document's numbers on the day.

## Sat/Sun (same drill as the SA runbook, per day)

1. Before the shotgun: seed/reuse the day's session; no coverage
   banner; field right; teams from pairings.
2. Paste the GG tournament URL once; **Pull from GG** to move the board.
3. Read GG's flights off its leaderboard and TYPE them into the Flight
   column (flight capture at import is still unbuilt — same workaround
   as SA).
4. Watch the Parity tab; record disagreements, don't fix them live.
5. CTPs are adjudicated on-course — record by hand. Carlos is OUT of
   Team Net and Ind Net; he IS in Skins/CTP/Ind Gross.
6. COMBINED (Ind Net/Gross) totals span both days — GG's combined
   leaderboard is the source; our Test Center sessions are per-day, so
   combined parity is a manual diff of Sat+Sun totals. (Known limit;
   fine for a shadow.)
7. No payouts off the shadow board. Record real payouts against the
   three bucket accounts (`2026 TGF CHAMPIONSHIP — SATURDAY / SUNDAY /
   COMBINED`) through the normal payout flows after play.

## After the weekend

- Record payouts per bucket; purses are already derived from real money
  (including the Zapata opt-out and any late roster moves).
- Sales tax filing due **08-20** — pricing skill certified 08-07,
  unblocked.

## CUP RESOLUTION (wired + verified 2026-08-13 vs Kerry's test scores)

Both cups resolve **POINTS RESET + Round 1 + Round 2** on the Contests
page (grouped TGF CHAMP header, CUP TOTAL decides; champ rows expand to
per-round hole-by-hole cards with Round toggles). Verified consistent on
the 08-13 test boards (v2.234.1): every row reads reset + rounds exactly.

- Boards (dedicated portal `tgf-champ26.golfgenius.com`, league 546813;
  rounds: practice 1692726 · **R1 1692724** · **R2 1692725**):
  `gg_champ_points_boards` → fellowship_cup 4749234 ("THE FELLOWSHIP
  CUP"), players_cup_gross 4749239 ("THE PLAYERS CUP - Overall");
  `gg_champ_scorecard_boards` repointed (v2.235.x) to the SAME points
  boards 4749234/4749239 — the ALL Net partial (4749269) only carries
  front-nine strokes on this portal, while the points boards' partials
  hold all 18 + GG's per-hole Stableford. All Round 1, `round_index=2`.
- Phones show the SLIM cup layout (v2.236.0, Kerry-ratified): # |
  Player | RESET | RD 1 | RD 2 | CUP TOTAL on one screen; CITY RANK is
  in the row expansion, THRU sits under the player's name, names wrap.
  Desktop keeps the full column set.
- **TOURNAMENT MODE IS ACTIVE (2026-08-14, Kerry: "We can clear TEST
  and activate for tournament")**: `gg_champ_test_phase` = "0" (banner
  gone), test scores wiped by Kerry, both cups verified live — R1
  active showing tee times in THRU, R2 a blank pending column. The
  banner dial stays available if scoring ever needs to be flagged
  mid-weekend (`scoring-setting-set:gg_champ_test_phase|1`).
- **ROUND 2 IS AUTOMATIC (v2.237.0, tested live 2026-08-13 on Kerry's
  random R2 scores):** the R2 entries in `gg_champ_points_boards` carry
  `discover` (the round-1692725 tournament_results widget) + `match`
  ("FELLOWSHIP CUP - Round 2" / "PLAYERS CUP - Overall"); the moment GG
  releases the round, the next leaderboard poll resolves the board URL,
  persists it, and mirrors a scorecard entry — RD 2 column, summing,
  and the Round 2 card toggle all appeared with zero manual steps.
  Discovered ids for the record: fellowship 4749235, players cup
  4749243 (both `round_index=3`). Sunday needs only a VERIFY, not a
  wiring step. Per-round cards compare against their own round's board
  figure (v2.237.1).
- **R2 IS DATE-GATED (done 2026-08-14):** both R2 points entries carry
  the auto-discovered urls (4749235 / 4749243) plus
  `"not_before": "2026-08-16"` — a blank pending RD 2 column until
  Sunday Central date, then it activates itself. NOTHING to do Sunday
  morning; verify only. Scorecard-dial R2 entries stay in place (used
  only when the Round 2 toggle asks for that board).
- **Do NOT award cup/season points in GG at close-out** — the Tracker owns
  cup resolution (reset + rounds). The 08-06 emergency (double-added
  Players Cup) is why the city boards' dial entries stay disabled. The
  city-era absorption baseline is archived at
  `gg_champ_absorb_baseline_players_cup_gross_2026city`; clear the
  still-in-place `gg_champ_final_board_players_cup_gross` before ever
  declaring players_cup_gross final.
- **Plus handicaps (OPEN — needs Kerry/Robert):** the champ ALL Net board
  exposes no PlayingHandicap column, so the tracker's per-day plus
  deduction cannot fire. If GG's champ points games do NOT net out plus
  give-backs (they did not at the city champs), Larson's (+) totals will
  read high — rule it before payouts.
- **Handicaps between rounds (Kerry 2026-08-13):** TGF handicaps are
  already updated in GG; they will be re-updated AFTER Round 1 for
  Round 2. Run the GG handicap CSV export/upload Saturday evening.
- **COMPUTE-FILL: everyone's cup totals calculate (R1 live, v2.239.0/.1
  — Kerry's Option B):** GG's FELLOWSHIP CUP points game rosters only
  the 19 cup entrants, so the other ~15 field players (Young, Sharp,
  Lee Vasquez, ...) had no championship points on the tracker board.
  `fill_missing_from: "players_cup_gross"` on both fellowship entries in
  `gg_champ_points_boards` computes their net Stableford from the
  PLAYERS CUP board's scorecard partials (full field, 18 strokes + dots)
  via `_champ_points_fill_rows`. Cup MONEY is untouched — enrollment
  still decides green rows/pot/projections. **Incident note:** the first
  enable (v2.239.0) hung the live board — the fill's card fetches called
  back into `fetch_champ_points` for the board-figure comparison before
  its cache was written (re-entrant recursion). v2.239.1 skips that
  lookup on fill cards (`roster_race` set) and walks the missing players
  with a 6-worker pool; verified live at 34/34 scoring, ~6s first walk,
  <1s cached. If the fellowship endpoint ever hangs again, pull the
  `fill_missing_from` keys from the dial to instantly disable.
