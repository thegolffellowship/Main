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
worth $270 / $150 / $200 of pool money. Per-game pots derive on the
GAMES tab with Zapata's "1 opted out" notes on Team Net and Ind Net.

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
