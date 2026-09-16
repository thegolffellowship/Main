# Side Games — RATIFIED SPEC v1.0 (2026-07-05)

Status: **RATIFIED by admin** via the platform dialogue reconciliation
(mailbox ids 6-11). Platform-side twin: TGF_Side_Games_Rules_v1_0.md
(OneDrive 7_Web & App Development/ + Project knowledge). Sources: live
GG portal evidence (s9.16, s18.7, a9.16), the Pricing & Services Master
Doc v2.0 (via platform-claude), Kerry's 2026-07-05 rulings, and the
prize matrix (analysis below). Open flags listed at the bottom.

## Buy-in pricing (as sold; pools exclude TGF markup)

- **NET add-on**: $16 sale (9h) = Ind Net $9 + MVP $4 + markup $3;
  standalone 18h $30 = Ind Net $18 + MVP $8 + markup $4.
- **GROSS add-on**: $16 sale (9h) = Skins $9 + Ind Gross $4 + markup
  $3; standalone 18h $30 = Skins $18 + Ind Gross $8 + markup $4.
- **BOTH**: $32 (9h) / $60 (standalone 18h).
- **Combo events (9/18)**: 18-hole players pay 18-hole INCLUDED pots
  but 9-HOLE bundle prices. Standalone 18s (s18.x) use the $30/$60.
- Access: NET & BOTH members only; GROSS & NONE available to all.
- Event entry includes game money: **$7/player (9h)** = Team Net $4 +
  CTP $2 flat + Hole-in-One $1; **$14/player (18h)** = $8 + $4 + $2.

## Included games (every player)

- **TEAM Net** — foursomes, one best NET ball per hole vs par; blind
  draw ("Bl[Name]") fills short teams. 9h winner-take-all; 18h pays
  1st + 2nd; ties split. Guests/cross-chapter included.
- **Closest to Pin** — flat $2 (9h) / $4 (18h) entry, max 2 CTPs per
  nine, winner-take-all each. Fewer par-3s than slots → remaining
  dollar(s) become a **Longest Putt contest on the last hole**. More
  par-3s than slots → automation selects the **shortest** par-3s.
  **"No Winner" pots CARRY OVER to the next event** (carried
  liability, not variance).
- **Hole-in-One** — $1/entrant (9h) / $2 (18h); accrues across events
  until won, pays out, resets to $0. **Members-only eligibility to
  win** (guests/first-timers pay in but cannot win).
- **Match Play** — season singles bracket per city, one match per
  event round, no per-round purse; season payout top 4 at
  50%/25%/15%/10% of pool.

## NET add-on games (buyers only)

- **Individual Net** — flighted (matrix-driven; 9h: 1 flight to 11
  buyers, 2 flights at 12+, split observed at HCP 12.0; 18h: up to 4
  flights by buyer count). Pays 1st/2nd per flight at ~2/3-1/3, adding
  3rd (and 4th on 18s) as buyer counts grow; ties split combined
  place money.
- **MVP** — $4/buyer (9h) / $8 (18h) from the NET bundle. Multiple TGF
  events same day → split evenly: **City MVP $2 + TGF MVP $2** (9h) /
  $4 + $4 (18h). Single-event day → ALL MVP money to City MVP, no TGF
  MVP. City MVP = **highest net Stableford POINTS** (per the MVP
  Assign Points schedule — not the best net stroke score) among
  buyers; tiebreakers:
  1) Individual Net score, 2) Gross score, 3) split. **TGF MVP** = the
  City MVP with the HIGHER points across the day's events; tie →
  split, no tiebreaker. Recorded purse-only in GG (Pos "None").

## GROSS add-on games (buyers only)

- **Skins** — the buyer count selects WHICH SKINS GAME IS PLAYED, not
  merely the pot size (see "½-Net Skins" below — this is the first-level
  governing factor). At 8+ buyers on a nine it is GROSS skins (outright
  low gross on a hole within flight), flighted 2 ways (up to 4 flights
  on 18s); each flight's pot divides equally per skin won. **Below 8
  buyers on a nine the matrix runs Skins ½ Net, a NET game** with a 50%
  allowance off the lowest.
  **Audit it with `scoring-skins-audit:<event>`** (v2.457.0, read-only,
  `database.py skins_audit`; rewritten v2.459.0): it resolves the
  variant the matrix selected, derives THAT game's own strokes, and
  prints the working — every buyer's playing handicap and game strokes,
  and both the gross and the pops on every hole, the low, who held it,
  and why the hole did or did not pay — set against the recorded skins
  money. Built when a player showed skins MONEY with no circled hole
  (Kerry 2026-09-15: "Carlos's skin isn't circled. Audit").
  **When our board and a GG payout diverge, check `game` FIRST — which
  game the buyer count selected — and only then look at the TIED holes.**

  > **CORRECTION (2026-09-16).** This entry previously recorded the
  > a9.23 case as "Golf Genius disagreeing with ITSELF: its skins board
  > paid a birdie on a hole where its own scorecard has a par." **That
  > was wrong, and the error was ours.** The game was ½ Net; GG's board
  > was reporting a NET birdie, and its scorecard's par is the GROSS.
  > Both GG numbers were right and consistent. See below.
- **Individual Gross** — raw gross, flighted. Activates at **16
  buyers (9h) / 12 (18h)** per the LIVE matrix — admin lowered the
  thresholds via the Matrix UI (the old Excel seed said 20/16); 3
  flights in the new bands (9h 16-19, 18h 12-15), 4 flights at 20+/
  16+. 1st per flight (2nd added at large counts on 18s). s18.7's
  observed 13 buyers / 3 flights matches the live rule exactly (it
  was never a manager override).

## Prize matrix — derived rules (verified against the LIVE
## app_settings copy 2026-07-05; seed regenerated to mirror it)

Per-player-count N, closed forms verified across the whole matrix:

| Line | 9-hole | 18-hole |
|---|---|---|
| Event game money | $7×N | $14×N |
| Team Net pot | $6×N CART Net (N=4–15, incl. CTP money; pays 2 places at 12–15); $4×N TEAM Net at 16+ (winner-take-all to 47, 1st+2nd at 48+) | $12×N / $8×N (same shape; TEAM 1st+2nd from N=32 — admin edit, was 36) |
| CTP total | $2×N split evenly over active CTPs | $4×N; CTP count grows 2→3→4 at N=16/24/32, pot splits evenly |
| Hole-in-One | $1×N | $2×N |
| NET pool | $13×N | $26×N |
| Individual Net | $9×N | $26×N − MVP pot |
| City MVP + TGF MVP | $2×N + $2×N | single-event day: min($8×N, $100), excess → Ind Net; multi-event day: $4×N + $4×N |
| GROSS pool | $13×N always (totals column fixed 2026-07-05) | $26×N |
| Skins | $9×N (all of pool below 16) | $18×N (all of pool below 12) |
| Individual Gross | $4×N (active N≥16 — admin edit, was 20) | $8×N (active N≥12 — admin edit, was 16) |
| Gross flight payout | flight pot = pot÷flights, winner-take-all | same; 1st/2nd at 2/3–1/3 from N=48 |
| Net flights | 1 (≤11), 2 (12+) | 1 (≤13), 2 (14-33), 3 (34-49), 4 (50-64) |
| Skins flights | 1 (<8), 2 (8+) | 2 (8-31), 3 (32-47), 4 (48+) |
| Gross flights | off (<16), 3 (16–19), 4 (20+) | off (<12), 3 (12–15), 4 (16+) |

Skins payout arrays = flight pot ÷ skins count — verified exact
across the LIVE matrix after the 2026-07-05 repairs (the old 9h N=18
24.67 anomaly was superseded by the admin's threshold edit).

## teamMWP — RESOLVED (admin, 2026-07-05)

**MWP = Maximum Winnings Potential.** Not a game: it is the largest
amount one person can win from the team game = team1st ÷ team size
(verified exact across the matrix once team type is known). Consumed
by the Events page GAMES tab, which shows an MWP column per game and
sums an event-level Max Winnings Potential. KEEP — earlier deletion
recommendation retracted. (The Platform docs' "Team MVP" label remains
a separate naming slip for Team Net.)

## Matrix audit (admin-requested, run 2026-07-05)

Programmatic audit of every cell in both matrices against the ratified
pool model ($13-of-$16 / $26-of-$30 to pots, rollover rules). Results:

**Real defects (both FIXED — boot repair `_repair_matrix_gross_totals`
patches the DB copy; static seed corrected in-repo):**
1. 9h `grossTotalPot` column read $15×N for every N≥20 while its own
   game pots correctly sum to $13×N (Skins 9 + Ind Gross 4). Display
   column only — but it fed the Events Games-tab gross subtotal, which
   overstated. 45 cells corrected to 13×N. (This was the source of the
   earlier "$15/buyer" confusion; the 18h totals were always correct.)
2. 9h N=18 skins array, 3-skin cell: 24.67 → 39.00 (= flight pot 117
   ÷ 3, the ratified formula). 1 cell corrected.
3. Cosmetic, unfixed: N=2–3 rows show eventTotalPot $7×N while every
   event game is NO_EVENT.

## LIVE-matrix audit (2026-07-05, via get_side_games_matrix)

Admin flagged that the earlier audit ran against the repo seed, which
drifts from the live app_settings copy (Matrix UI saves rewrite the
static file only on Railway's ephemeral disk). Full re-audit against
the LIVE copy (source: `app_settings`):

- **Admin's threshold edits CONFIRMED**: Individual Gross activates
  at N=16 (9h) / N=12 (18h) in the live matrix, exactly as stated;
  new rows are self-consistent (ig=$4×N/$8×N, skins drop to $9×N/
  $18×N, gross total stays $13×N/$26×N, 3 gross flights in the new
  bands). The 9h band's skins arrays were correctly recomputed.
- **Earlier repairs confirmed applied, no collateral**: live 9h
  grossTotalPot reads $13×N everywhere; the value guards left every
  admin-edited row untouched; the 24.67 anomaly row was superseded by
  the admin's own edit.
- **Two stale-companion families found** (cells the Matrix UI edit
  did not recompute), both now fixed by the extended boot repair:
  1. 18h N=12–15 skins arrays still paid FULL-pool values (implied
     $26×N: 312/338/364/390) on the new $18×N pots — would overpay
     skins ~44% at those buyer counts. 36 cells → flight pot ÷ count.
  2. 18h N=32–35 teamMWP still showed the winner-take-all value
     (teamTotal÷4) after the admin added a 2/3–1/3 1st/2nd split;
     4 cells → team1st÷4 (e.g. N=32: $64 → $42.67).
- Boot repair now covers BOTH matrices + the MWP formula; the repo
  seed was regenerated from the repaired live copy so a fresh DB
  no longer regresses the thresholds to 20/16.
- **RESOLVED (admin ruling, same day)**: 9h N=16–19 grossLow1st was
  hand-entered at whole dollars ($21/22/23/24) vs exact pot÷3 —
  admin ruled it should be exact; repaired to $21.33/$22.67/$24/
  $25.33. The boot repair now enforces the gross-flight payout
  formula everywhere: flight pot = Ind Gross pot ÷ flights, winner-
  take-all per flight, 2/3–1/3 once a 2nd place is in play (18h
  N≥48 — verified exact across the live matrix).

**Not defects — the "removed Excel formulas" survive as encoded rules:**
- **CART Net below 16 players**: teamType switches to CART Net
  (2-person cart teams) for N=4–15 with team pot $6×N — the $2×N CTP
  money rides in the team pot because no CTPs run below 16; TEAM Net
  foursomes at $4×N + CTPs $2×N from N=16. Event money is $7×N either
  way. (18h mirror: $12×N cart pot below 16, $8×N + $4×N CTPs at 16+.)
- **Ind Gross → Skins rollover**: below ~20 gross buyers (9h) / 16
  (18h) Individual Gross cancels and its $4×N/$8×N rolls into Skins
  (skins pot = full $13×N/$26×N). Real-world confirmed: s9.16 ran
  Skins-only with total purse $195.01 = 13 × 15 gross buyers.
- **18h MVP cap**: mvp = min($8×N, $100), and Individual Net = $26×N −
  mvp — the excess above the cap flows to Individual Net automatically.
  Matches admin intent for SINGLE-event days (below).

## 18h MVP day-type rule — **RATIFIED (Kerry, 2026-07-31)**

Confirmed verbatim, closing the 2026-07-05 open question:

1. *"For two or more 18 whole days there is no cap just like the nine
   hole events."*
2. *"Both cities' MVP totals are $ x N/2 = MVP and TGF MVP pots. Then
   combine each city…exactly like 9s. It's just a bigger $/player"*
3. Cross-course comparability: *"Is what it is. No adjustments for
   difficulty."*
4. *"No mixed format TGF MVPs it's either nine or 18."*
5. The GAMES tab on each event must show the totals the way the 9-hole
   events do.
6. *"for a single 18 hole event day we would max out at $100 and then
   put the rest into the individual net game. There will not be any
   residual for multiple 18 hole events just like the nine hole
   multiple events."*

**Single 18h event that day**: all MVP money to City MVP, capped at
$100; the money above the cap reroutes to Individual Net. The matrix
rows encode exactly this — `mvp = min($8xN, $100)`,
`individualNet = $26xN - mvp`.

**Two or more 18h events that day**: no cap, no residual. City MVP
$4/buyer + TGF MVP $4/buyer per city; the TGF halves from every linked
city COMBINE into one pot. Individual Net becomes the full
`$26xN - $8xN = $18xN` — it must give the capped-away residual back, or
the same dollars appear twice on the tab. Worked example at N=22:
single-event 472 + 100 = 572; multi-event 396 + 88 + 88 = 572.

### How it is implemented (v2.169.0)

- `templates/events.html` `mvpSplitFor(entry, holes, netPC)` — the split
  is DERIVED from the buyer count ($4/buyer at 9h, $8/buyer at 18h,
  halved), with matrix `cityMVP`/`tgfMVP` winning where present. Derived
  rather than seeded because the LIVE matrix comes from `app_settings`
  and overrides `games-matrix.js` wholesale — a new seed column would
  simply be absent in production (see the `get_side_games_matrix` note
  in CLAUDE.md).
- `getMvpLinkedEvents(ev)` works for BOTH formats and links **same
  format only**. It previously returned null for any 18-hole event and
  skipped 18-hole events when scanning the day, so two 18-hole events
  could never share a TGF MVP.
- Multi-event 18h days scale Individual Net (and its place ladder,
  proportionally — the ladder is a fixed percentage structure) and mark
  the row "(multi-event day)". **The matrix itself still has no
  multi-event 18-hole rows**; adding them to the generator is the
  authoritative follow-up.
- `database.py determine_tgf_mvp` pools the day by the anchor event's
  format. It used to drop every 18-hole event from the pool outright.

## GG game SETUP layer (admin-supplied screenshots — versioned
## game definitions; first arrived 2026-07-05)

**Framing (admin, 2026-07-06):** these are **TGF standards the admin
authored**, not GG's — GG is a configurable engine and the current
entry surface, but the source of truth is TGF. GG cross-checks below
confirm our engine matches the admin's current config; the goal is for
the Tracker to LOCK these as versioned definitions (which GG does not
do well) so they apply automatically to every future event.

The admin supplies Golf Genius setup screenshots per game rather than
have setup reverse-engineered. Target per the ratified requirement:
every setting below becomes an admin-editable, VERSIONED game
definition with standard defaults — GG's tournament library exists
but managers must manually re-verify setup each event; TGF builds
toward full automation (see governing docs).

### Global standards (ALL games and events — admin, 2026-07-05)

- **Maximum Playing Handicap™: 36 (M and F) for 18-hole competitions,
  18 (M and F) for 9-hole** — TGF never awards more than 2 pops per
  hole in any competition.
- **Team competitions**: Handicaps → "Disallow Strokes on Par 3
  Holes" (all team games).
- **Max Triple** (advanced hole-by-hole maximum score rule): gross
  triple bogey is the maximum recorded score in ALL games, net or
  not — net pops are applied FROM the capped gross. Players know to
  pick up once they're not holed out after attempting double bogey.
  (admin, 2026-07-05)
- Payout places are selected per the prize matrix when a game pays
  multiple places (the matrix is the source of truth for amounts).
- **Tie / multi-winner rounding — MONEY OUT = MONEY IN (Kerry
  RATIFIED 2026-07-12).** When a place-group pot or a skins pot does
  not divide into whole cents, our payout splits (`split_cents` in
  `_rows_from_place_ladder`, and the largest-remainder skins
  apportionment in `assemble_event_game_payouts`) apportion so the
  shares sum EXACTLY to the pot collected — the last player in a tied
  group absorbs the sub-cent shortfall (e.g. two players splitting
  $22.67 → $11.34 / $11.33, not $11.34 / $11.34). This is INTENTIONAL
  and correct: the pool pays out exactly what it took in. **Golf
  Genius rounds each tied share half-up independently, so its printed
  shares can total a penny or two OVER the nominal pot** (verified on
  s9.17 Silverhorn 2026-07-07: GG's Individual Gross shares summed to
  $68.03 under a "Total Purse Allocated: $68.01" line — GG paid two
  cents it never collected). Kerry's ruling: keep our exact-to-pot
  behavior; do NOT "fix" it to match GG. Consequence to expect: on odd
  splits an individual's amount may read one penny below GG's
  published figure — that is the pot balancing, not an error.

**Blind-draw partners ARE PAID (Kerry RATIFIED 2026-07-13).** When a
team is completed with a blind draw, GG renders that slot as
`Bl[LAST, First]` in the team name and pays it a full equal share of
the team purse. `assemble_event_game_payouts` used to EXCLUDE the
blind-draw member and split the team pot among the real members only
(over-paying them, zeroing the drawn player). Verified wrong vs GG's
Player Purse Summary on s9.17 Silverhorn (2026-07-07): GG split the
winning team's $54 across all four slots incl. `Bl[HAMILTON, Doug]` →
$13.50 each; the old code paid South/Moreno/Wade $18 and Hamilton $0.
Fix: unwrap `Bl[...]` to the real name and include it in the split, so
we match GG (Hamilton's team share $13.50 restored; the other three
drop from $18 to $13.50). NOTE: my initial payout audit compared game
TOTALS and per-board figures but not the team per-player distribution,
so the ~$0.03 total-level agreement masked $4.50–$13.50 per-player
errors — team splits must be audited player-by-player, not by total.
**Repairing events recorded BEFORE the fix (Kerry-scoped 2026-07-13):**
the code fix only changes NEW recordings; events already recorded keep
the bad split. A full re-record is wrong when some rows are already
PAID (it deletes/re-creates paid rows). Use
`repair_teamnet_blind_draw_shares(event_name, dry_run)` (bridge
`scoring-teamnet-repair:<event>` / `<event>|apply`, v2.79.3) — it
corrects ONLY the unpaid team_net rows of the affected group (adjusting
the pending payout row + its mirror pending ledger entry in lockstep,
or inserting a fresh pending row for the excluded blind-draw member),
SKIPS any teammate already paid, and nets $0 across the group. s9.17
Silverhorn was repaired this way (South/Moreno/Wade $18→$13.50,
Hamilton $0→$13.50; Young/Watson already paid at $13.50, untouched).

**GG-posted purses are the money of record for GG-recorded games
(Kerry 2026-08-02: "we need to allow me to adjust GAMES money").** The
assembly takes a Team Net position group's pool from the GG board's
Purse column (summed across tied teams) and a CTP/Longest Putt purse
from its board row, falling back to the matrix only when no purse is
posted. Kerry adjusts game money ON GG (e.g. rounding the 2026-08-01 SA
championship team places to $170/$86 for clean $42.50/$21.50 member
shares); re-walks refresh `gg_game_results.purse`, so his edits flow
through every subsequent (auto or manual) re-record. The
shadow-computed games (Ind Net/Gross, Skins, MVP) remain matrix+dial
driven — per-event adjustments for those are the pending FLIGHTS
mechanism.

**GUESTS are paid their team share too (Kerry RATIFIED 2026-08-02,
verbatim: "Guests can have a share of the team/cart Net pot because
it's something included with event fees.").** Same principle as the
blind-draw rule: every slot on a winning team gets an equal share,
member or not. GG renders a guest either as a first-last guest profile
("Matt Larson") or with a "Guest" host decoration on a member's slot
("SHARP, Matt Guest" — that slot is the MEMBER's own share, not the
guest's; the guest's share rides on their own profile row). Verified
on the 2026-08-01 Austin Championship: winning team Larson (guest) /
McDonnell / Reed / Sharp each took $32, matching GG's purse summary
player-by-player. Guest payout rows typically have no Venmo handle on
file — the Payouts page shows "+ Add Payment" for them.

### TEAM Net — definition v1 (s9.16 TPC San Antonio | Oaks setup)

| Setting | Value |
|---|---|
| GG name | "TEAM Net $" |
| Divisions | All Golfers only (no points/skins/match-play divisions) |
| Format | Stroke · Foursome v. Field · Best Ball on each hole · 9 Holes (Front or Back) |
| Handicap | USGA Net (off lowest) · allowance **75%** · Drop Worst 0 holes |
| Tie-breaking | Retain Ties |
| Payout | Purse & Points "by Winner takes all" · purse pot from matrix (s9.16: $128 = $4 × 32 players — matrix cross-check exact) · points 0 |
| Max scores | Advanced hole-by-hole: "Max Triple" (gross) |
| Handicaps (advanced) | Disallow Strokes on Par 3 Holes |
| Enter One Team Score | OFF (individual scores entered) |

**Variant rules (admin answers, 2026-07-05):**

- Allowance IS tied to ball count — they are the standard USGA
  recommendations: **Best 1 → 75%, Best 2 → 85%, Best 3 → 100%,
  Best 4 → 100%**. Encode the pairing; the % follows the ball count.
- Scheduling rule for automation: **standard rotation every other
  event between Best 1 and Best 2**, admin/manager-overridable to
  Best 3/Best 4 (or to run Best 1 in lieu of Best 2).
- 18-hole Team Net is the same shape (18 holes; payout selector set
  for 1st+2nd when the matrix pays two places).
- **"Off lowest" handicapping** (admin: "essentially yes, strokes
  play off the lowest handicap — the nuance lies in how it's
  applied"): the reduction scope follows the competition scope —
  flighted games apply it WITHIN each flight, field games across the
  field, match play just between the two players in the match.
  Details to be worked in a dedicated session before our own engine
  implements it.

### MVP (City MVP) — definition v1 (s9.16 "s9.16 MVP $" setup)

| Setting | Value |
|---|---|
| GG name | "s9.16 MVP $" (per-event) |
| Divisions | the event's NET division ONLY (s9.16 Net) — matches members-only NET-bundle eligibility |
| Format | **Stableford** · Player v. Field · Own Ball on each hole · 9 Holes (Front or Back) |
| Assign Points | HIO **8** · Triple Eagle+ **4** · Double Eagle **4** · Eagle **3** · Birdie **2** · Par **1** · Bogey **0** · Double Bogey **-1** · Triple Bogey **-1** · Others **0** |
| Handicap | USGA Net (plain, NOT off-lowest) · allowance **100%** · Drop Worst 0 |
| Tie-breaking | Retain Ties (admin settles via the ratified tiebreaker chain — Ind Net, then Gross, then split — recorded through payment) |
| Payout | Purse & Points "by Winner takes all" · purse pot $42 = **$2 × 21 NET buyers** (multi-event-day City MVP half-share — cross-checks the ratified $2/$2 split exactly) · points 0 |
| Season Points | none |

Schedule notes: (a) the schedule scores **NET** results (net
Stableford — admin confirmed 2026-07-05); (b) a hole-in-one pays 8
regardless of par; (c) the "Others" (worse than triple) slot at 0 is
unreachable in practice — the global gross Max Triple rule caps every
recorded score at triple bogey (which scores -1); (d) this custom
schedule is NOT classic Stableford — whether the POINTS games use
the same Assign Points table is the key open question for live
standings math (awaiting the points-game setup screenshot; the -6
gross total once observed on THE PLAYERS CUP is only producible with
negative per-hole values like these, so a shared schedule is likely).

**Championship schedule (admin, 2026-07-05):** City Championship
and TGF Championship events use the same table shifted **+1 per
category**. Net: Triple 0 · Double 0 · Bogey 1 · Par 2 · Birdie 3 ·
Eagle 4 · Double Eagle 5 · HIO 9. (~+1 point per hole vs regular
events — the championship weighting in the season race; see
scoring.md points model.)
**NET ceiling (Kerry-ratified 2026-08-14):** the net table MAXES at
**5** — double eagle pays 5 and anything rarer (net triple eagle+,
reachable only via handicap dots stacking on a gross eagle) ALSO pays
5. Verbatim: "We need to max out at 5 for Net scoring which would be
for double eagle. Triple eagle net would be 5 too." Matches GG's
"Double Eagle or Better" bucket; surfaced on the 08-13 R2 test card
(gross eagle + two dots on a par 5 = net 4-under — our formula paid 6,
GG paid 5). `_champ_stableford` caps accordingly (v2.237.2); the
GROSS-ace 9 is unaffected.

**MVP vs POINTS structure (admin, 2026-07-05):** MVP is a per-event
game restricted to NET buyers; the POINTS game is a SEPARATE GG game
capturing the same net Stableford for EVERYONE in the field (that
race's division). Same math, different rosters and payouts.

**Points schedules (admin-ratified 2026-07-06 — full table in
scoring.md):** NET (net-vs-par) birdie 2 / par 1 / bogey 0 / eagle 3 /
double eagle 4. GROSS (gross-vs-par) birdie 4 / par 2 / bogey 1 /
eagle 8 / double eagle 16. A RAW ace (gross 1) awards the HIGHER of an
8-pt HIO bonus and its vs-par value (par-3 ace 8, par-4 ace 16 gross),
in both net and gross; a net-1 via strokes is NOT a HIO. Championship
is asymmetric: NET +1 on every category (incl. HIO -> 9); GROSS +1 on
the HIO bonus only (-> 9), vs-par gross unchanged. The GROSS table is
VALIDATED against GG's own game config (TPC26reg screenshot, 2026-07-06)
— exact match on every reachable category; see the gross POINTS game
definition below.

### Platform consolidation concept (admin direction, 2026-07-05)

GG currently needs three games per event (MVP $, net POINTS, gross
POINTS). On the Platform / live leaderboard these consolidate into
ONE computation over the whole field:

- Compute net AND gross Stableford for every player (the Tracker's
  formula layer already produces both per scorecard).
- One leaderboard, three outputs: net points column = the points
  race for everyone; gross points column = THE PLAYERS CUP race;
  MVP = best net among the color-coded MVP ENTRANTS (buy-in flag
  from commerce data — non-entrants still accrue points, just
  aren't payout-eligible).
- Entrant color-coding replaces roster-splitting; payout eligibility
  is a flag, not a separate game. Fits the versioned game-definition
  standard (one points-schedule definition, per-event snapshots).
- **Leaderboard IA (admin, 2026-07-06):** horizontal tab nav —
  **Team · Gross · Net · Skins · Points · Proxies** — instead of
  GG's vertically stacked game lists. ("Proxies" = CTP / Longest
  Putt.) Match Play could be a seventh tab but may be too busy —
  candidate for a "More" overflow or showing only when a bracket
  round is live. Goal: one simplified, logical results surface per
  event.
- GG friction this replaces (admin): points games require dedicated
  divisions with season points attached before GG will award them,
  and points post only AFTER the round — an anticlimactic finish.
  The live leaderboard computes points during play.

### Individual Net — definition v1 (s9.16 "INDIVIDUAL Net $" setup)

| Setting | Value |
|---|---|
| GG name | "INDIVIDUAL Net $" (per-event) |
| Divisions | the event's NET division ONLY (s9.16 Net) |
| Format | **Stroke** (not Stableford) · **Player v. Flight** · Own Ball on each hole · 9 Holes (Front or Back) |
| Handicap | USGA Net (plain) · allowance **100%** · Drop Worst 0 |
| Tie-breaking | Retain Ties (ties split combined place money per ratified rules) |
| Payout | Purse & Points "by 1st, 2nd, … Nth" **per flight**: 1st $63 / 2nd $31.50 (flight total $94.50) · points 0 |
| Max scores | Advanced: "Max Triple" (gross) |
| Leaderboard | ALSO displays total gross score + Playing Handicap™ as separate columns |
| Season Points | none |

Cross-check (exact): 2 flights × $94.50 = $189 = $9 × 21 NET buyers
— the same 21 buyers the MVP pot implied, and the matrix N=21 row
verbatim (netFlights 2 at 12+ buyers, places at 2/3–1/3). Flights
are configured under Cut Lines & Sections (split observed at HCP
12.0). Note the handicap dropdown: individual games use plain "USGA
Net"; only TEAM games use "USGA Net (off lowest)".

**TGF MVP recording (admin, 2026-07-05):** GG CANNOT configure TGF
MVP — it was a fully manual step (admin compared the City MVPs'
points across the day's events and recorded the payout by hand).
**AUTOMATED in v2.33.0** (admin: "Build it"): `determine_tgf_mvp()`
(database.py) computes each linked event's City MVP from OUR imported
scorecards + the formula layer — highest net Stableford POINTS among
NET-bundle buyers, tiebreakers Ind Net stroke score → Gross → split —
then names the TGF MVP (higher day points, tie splits). Buyer
eligibility mirrors the Games-tab rules (credited/refunded/
transferred/rsvp_only out; wd out only if net_games credited; child
add-on payments upgrade the parent's game type). Surfaced three ways:
`/api/events/tgf-mvp?event=` (manager), the MCP tool
`determine_tgf_mvp`, and 🏆 winner rows on the Events Games tab
(City MVP row + TGF MVP block, lazy-hydrated; shows
awaiting-results/single-event-day states). GG-recorded event_mvps
names ride along for cross-checking. Verified on a synthetic DB: 5
scenarios incl. both tiebreaker layers and tie splits.

### THE PLAYERS CUP gross POINTS game — definition v1 (regular, VALIDATES the gross schedule)

Admin-supplied GG setup (2026-07-06) for the season GROSS points game.
This is the authoritative source that VALIDATES our gross Stableford
table (see scoring.md) — every reachable category matches exactly.

| Setting | Value |
|---|---|
| Format | **Stableford** · Player v. Field · Own Ball on each hole · 9 Holes (Front or Back) |
| Handicap | **None (Gross)** — raw gross, no strokes (confirms gross games use no handicap) |
| Assign Points | HIO **8** · Triple Eagle or Better **16** · Double Eagle **16** · Eagle **8** · Birdie **4** · Par **2** · Bogey **1** · Double Bogey **0** · Triple Bogey **-1** · Others **0** |
| Drop Worst | 0 |
| Tie-breaking | Retain Ties |
| Payout | Purse & Points **None** (points-only game — no purse; feeds the season race) |
| Division / Point Category | **THE PLAYERS CUP / TPC26reg** (the "reg" = regular-season category; the championship uses a separate category) |

Validation notes (all confirmed 2026-07-06):
- Every reachable gross category matches our engine's table exactly:
  eagle 8, double eagle 16, birdie 4, par 2, bogey 1, double bogey 0,
  triple bogey -1. This is GG's own config — definitive, no eagle
  round needed.
- GG lists **both** "Hole in One = 8" AND "Triple Eagle or Better =
  16" as separate boxes. Combined with the admin's "award the higher
  value" rule, this VALIDATES our max(HIO, vs-par) implementation: a
  par-5 ace (a triple-eagle by vs-par) scores max(8, 16) = 16, not 8.
- "**Others = 0**" is GG's catch-all for no-score / worse-than-triple.
  It is unreachable for a PLAYED hole because the global Max Triple
  rule caps every gross hole at triple bogey (-1); our clamp gives the
  same -1 for a played quad, and a genuine no-score (null hole) is
  skipped in our totals (contributes 0) — matching GG both ways. No
  code change needed.
- The separate `TPC26reg` point category confirms the regular/
  championship split is realized in GG as distinct categories (the
  championship category carries the +1-on-HIO gross variant).

### NET POINTS game — definition v1 (SAN ANTONIO Net, VALIDATES the net schedule)

Admin-supplied GG setup (2026-07-06) for the season NET points game.
Authoritative source that VALIDATES our net Stableford table.

| Setting | Value |
|---|---|
| Format | **Stableford** · Player v. Field · Own Ball on each hole · 9 Holes (Front or Back) |
| Handicap | net (USGA Net — the Advanced Options show a Handicaps section; unlike the gross game's None/Gross) |
| Assign Points | HIO **8** · Triple Eagle or Better **4** · Double Eagle **4** · Eagle **3** · Birdie **2** · Par **1** · Bogey **0** · Double Bogey **-1** · Triple Bogey **-1** · Others **-1** |
| Tie-breaking | Retain Ties |
| Season Points (Division / Category) | **SAN ANTONIO Net / 26-SAn**, **JUNE Points / 26-Jun**, **AUSTIN Net / 26-An** |

Validation notes (confirmed 2026-07-06):
- Every net category matches our engine's table exactly — including
  **Others = -1** (a DIRECT match to our clamp, unlike the gross game
  where Others = 0). HIO = 8 is validated via the max(HIO, vs-par)
  rule (same as gross).
- **One net game feeds MULTIPLE point categories**: the season chapter
  race (26-SAn) AND the monthly race (26-Jun) draw from the SAME
  per-event net Stableford — confirming the model that monthly (all
  points) and season (best-10 + CC) accumulate the same numbers
  differently. (This is why GG forces divisions-with-season-points to
  be attached inside each game — the friction the live leaderboard
  removes.)
- **Curiosity for admin**: this net game also lists **AUSTIN Net /
  26-An**. A San Antonio net game feeding the Austin race is
  unexpected — confirm whether this screenshot is a combined/cross-
  chapter event, a shared template, or an intentional cross-award.
- **Net "Others" differs between games**: this POINTS game uses -1,
  while the MVP $ game uses 0. Our single net table (Others -> -1)
  matches the POINTS game exactly; the MVP divergence is only on
  played quads, which Max Triple makes unreachable. No code change.

### Definitions still to capture

CTP / Longest Putt, Hole-in-One, Skins, Individual Gross, Match
Play, and the CHAMPIONSHIP point categories (TPC26champ / net
championship variants) — as admin supplies screenshots.

## Shadow-computed game winners (v2.35.0)

The Games tab hydrates 🏆 winner rows for every side game computable
from our imported scorecards, mirroring the MVP wiring (v2.33.0):

- Engine: `determine_event_game_results(event, game, flights)` in
  database.py; route `GET /api/events/game-results` (manager). Games:
  `individual_net` (net stroke, flighted), `individual_gross` (raw
  gross, flighted), `skins` (GROSS skins: outright low gross per hole
  within flight; ties kill the hole; per-player counts — the UI divides
  the flight pot by skin count).
- Buyer eligibility: `_event_game_buyers(conn, event, 'NET'|'GROSS')`
  (generalized from the MVP's `_event_net_buyers`, which remains as a
  wrapper) — same Games-tab rules (credited/refunded/transferred/
  rsvp_only out; wd out only when that bundle was credited; child
  add-on payments upgrade the parent).
- Flights: **GG flight labels ONLY, per game** (Kerry rulings
  2026-07-07). Flighting differs per game (Net, Gross, Skins cut
  differently), so a player's flight is a property of (game, event):
  `gg_game_flights` (v2.37.0) holds "Joe is in flight X for THIS game",
  captured by `import_gg_game_flights(widget_url)` (bridge command
  `scoring-flights-import`) which walks each flighted game's own GG
  leaderboard — the per-player details fragments carry the "Flight …"
  section label (same parse as the scorecard importer). The engine
  prefers gg_game_flights and NEVER mixes sources within a game;
  `scoring_rounds.flight` (one label per round, last-import-wins)
  remains only as a legacy fallback when a game has no per-game rows.
  Missing labels on a multi-flight game → `flights_unknown` ("flights
  pending GG import"). Austin fallback (v2.41.2): Austin's flighted
  boards have NO detail fragments — flight sections ("LOW Flight"/
  "HIGH Flight") render inside the leaderboard table itself; when the
  fragment walk records nothing, `_flight_sections_from_leaderboard`
  parses the section headings off the board (a9.17 Falconhead). Flights order low→high by average playing
  handicap so the matrix-named rows align by index; the response
  carries `flight_source` for transparency. Ties = golf-style shared
  positions; the ratified split-combined-places rule applies to the
  money (UI). Two v2.188.9 hardenings from the 2026-08-01 championships:
  (a) a buyer's MULTIPLE scoring_rounds rows for the same physical round
  (one per imported GG board — the ALL Gross row has net/playing_handicap
  NULL) are merged per buyer, later rows filling only missing fields —
  last-row-wins used to make Individual Net report `awaiting_results` on
  a fully-scored event; (b) `import_gg_game_flights` stamps `event_id`
  via scoring_rounds' own `gg_league_round_id` linkage when the round
  carries no `[sa]N.N` code (championship names), and a `?round=<id>` on
  the widget URL scopes `reset` to that one round.
- **Flight-consolidation precedent (Kerry, 2026-08-02, NOT yet a
  ratified rule):** at the 2026-08-01 SA Championship he consolidated
  Ind Gross from the matrix's 4 flights to 3 in GG (Flight 4 had a
  single player) and split the pot EVENLY among the 3 flights. The
  championships were recorded with `gross_flight_pot_mode=even`
  (temporarily flipped, then restored to `buyins`, the s18.8-matching
  interim default — which the hourly auto-sync promptly clobbered: it
  force-re-records recent events' payouts, so the temporary global flip
  reverted on the next sync. v2.188.13 added the per-event override
  `gross_flight_pot_mode_overrides` — a JSON app_settings dial
  `{event_name_lower: mode}` consulted before the global dial; both
  championships are pinned to `even` there).
  Kerry wants a proper mechanism for per-event flight adjustments —
  likely a FLIGHTS tab under EVENTS or inside the GAMES tab, layout
  undecided ("near the final component of the EVENTS tab"). Do not
  build until he settles the layout.
- Display-only (Stage 1 shadow discipline): GG stays official; no
  payout-ledger writes.
- Games-tab layout (v2.37.0, Kerry): TEAM Net / Individual Net (per
  flight) / Skins / Ind. Gross winners render on their OWN sub-rows
  (`.games-winner-row`, hidden until hydrated) below the game/flight
  rows; CTP and City MVP winners stay inline next to the name; TGF MVP
  winner is inline next to the heading, and each TGF MVP event-breakout
  line shows that event's City MVP winner (non-bold). All game headings
  are bold. Winner sub-rows wrap freely — this is also the mobile
  answer (no long inline chips).
- **GG-RECORDED games (v2.36.0)** — CTP / Longest Putt / Hole-in-One /
  TEAM Net winners are manually entered into GG post-round (Kerry,
  2026-07-07), so the portal is the source of record:
  `import_gg_game_results(widget_url)` walks the Event Results rounds
  (same mechanism + time budget as `import_gg_event_mvps`; bridge
  command `scoring-games-import` on probe_golf_genius) and records
  winners into `gg_game_results` (purse>0 rows, else position 1/T1;
  team rows keep the full "A + B + C + D" string with is_team=1 and no
  single customer_id; CTP Details column captured). Real-page shapes
  verified 2026-07-07 (s9.17): CTP = Pos./Player/Details, TEAM Net =
  Pos./Foursome/…/TotalNet. Read path GET /api/events/gg-game-results;
  the Games tab hydrates 🏆 chips on the Team Net/CTP rows and the HIO
  banner (Longest Putt winners ride on the CTP rows). For the future
  untethering, manager or in-round player entry replaces this pull.
  **Check-back-later (v2.139.0, Kerry 2026-07-22 — "CTPs are almost
  inherently later because they're not live"):** a round whose game
  board exists but carries NO winners yet is NOT marked done — it
  lands in `gg_game_recheck` (round, host, event_id, awaiting labels)
  and re-walks on every import pass until winners appear or the event
  is `recheck_days` (14) old, then gives up and marks done. The
  import's `events_updated` return lists events whose winner set
  actually changed (set-compared per tournament, so the routine
  rewalk_recent upserts don't count); `import_all_gg_side_data` feeds
  those into `record_all_event_game_payouts(force_events=…)` so a late
  CTP re-records that event's auto payouts even outside the
  recent_force_days window, and its no-event-today gate also runs when
  any recheck is outstanding (off-day sweeps until the CTPs land).
  The manual heal for a stale round remains `&round=<id>` on the
  scoring-games-import bridge URL. Origin case: s9.19 The Quarry's two
  CTPs (Kulawik #12, Mary Wade #16, $26 each) were entered in GG after
  the round was walked and sat invisible to the Tracker.
- **Ind Gross flight pots follow each flight's buy-ins (v2.140.1,
  INTERIM — final rule pending Kerry ratification, see Open flags):** gross flights are handicap
  BANDS with uneven headcounts, so the matrix's flat `grossLow1st`
  (individualGross ÷ grossFlights, an even-split assumption) is only
  the display seed — the assembler apportions `individualGross` across
  the determined flights by headcount (exact cents, largest remainder;
  per-player rate × flight size, GG's model) and splits places within a
  flight by the ladder's proportions. s18.8: 16 buyers × $8 cut 4/5/7 →
  $32/$40/$56, not $32 flat.
- **Record Payouts (v2.38.0, Kerry directive)** — the Games tab's
  "💸 Record Payouts" button (ADMIN-only as of v2.45.0; was manager) assembles every DETERMINED
  winner into PAYOUTS-tab rows: City MVP (+TGF MVP once, from the
  event you click — combined pot, warning shown), Ind Net per-flight
  place ladders with exact-cent tie splits, Skins per player (flight
  pot ÷ skins × count), Ind Gross per flight, GG-recorded Team Net
  (split per member, blind draws excluded) and CTP/Longest Putt.
  HIO is never auto-recorded (accruing cross-event pot).
  Team Net ties (v2.41.0, s9.17): tied teams (GG "T1"/"T1") split the
  combined place money before the member split — one team place at
  $108 with two T1 teams → $54/team, matching GG's recorded purses.
  Previously list order gave the first team the whole place and the
  tied team nothing.
  TGF MVP single owner (v2.41.2): the combined same-day pot is
  assembled ONLY by the winner's own event — both linked events
  previously assembled it, so force-refreshing both in one pass
  (3-day heal window / Populate All) double-recorded it. The
  non-owner event's notes say where it went.
  `record_event_game_payouts()` finds/creates the tgf_events row by
  event code, stamps rows `auto:` and delegates to import_tgf_payouts
  (customer resolution + Venmo-ledger reconciliation + aggregates);
  re-recording replaces prior auto rows (pending ledger entries
  deleted, matched real Venmo txns preserved). Every row ties to a
  customer_id (Principle 6 / Kerry: non-negotiable).
- **Payment links (v2.38.0)** — customers gain payment_method /
  payment_handle; default is Venmo via venmo_username. Boot-seeded
  exceptions (Kerry): Don Sharitz→PayPal, Brian Thompson→Cash App,
  Gus Vasquez + Michelle DelCarmen→Zelle. The PAYOUTS tab's pay
  button is method-aware: Venmo/PayPal.me/Cash App deep links with
  amount+note prefilled; Zelle (no deep link) shows a badge with the
  handle and amount, Mark Paid closes it out. Missing handles show
  "add handle" badges until supplied.
- **AUTO SYNC (v2.40.0)** — `auto_gg_results_sync()` runs hourly
  (12:10–23:10 Central, APScheduler; AUTO_GG_SYNC=0 disables; bridge
  `scoring-auto-sync` on demand): per portal it imports the newest
  rounds' ALL Net → ALL Gross scorecards, re-walks the newest rounds
  for GG-recorded winners + per-game flights (live rounds are marked
  walked before results exist, so recent rounds ALWAYS re-walk —
  upserts make it safe), then refreshes auto payouts force-replacing
  events from the last 3 days. Closing an event in GG is the last
  manual step: within the hour the Games tab shows winners and the
  PAYOUTS tab has customer-tied rows with payment links. Manual
  (screenshot) payout events are never touched.
  Step isolation (v2.41.0): scorecards, games, and flights each run
  in their own try/except per portal — a transient GG fetch failure
  in the scorecard walk previously aborted the whole portal, skipping
  the games/flights walks while the payout refresh still ran, which
  is how s9.17 Silverhorn got its payouts recorded WITHOUT Team
  Net/CTP attached (the data was finalized in GG the whole time; the
  next pass' 3-day force-refresh window then heals it).
  Board-name matching (v2.41.1): scorecard boards are matched by
  PREFIX — SA names them "ALL Net"/"ALL Gross" but Austin uses
  "ALL Net 9"/"ALL Gross 9", and the original exact match meant
  Austin events never got scorecards from the sync (a9.17
  Falconhead). Every matching board imports (future "ALL Net 18"
  combo days included).
- **OPEN — gross flight-pot levers (Kerry 2026-07-22, previously
  flagged):** the by-headcount rule shipped in v2.140.1 is the INTERIM
  setting — it matches GG and cleared s18.8, but Kerry wants the final
  policy designed: sometimes pots should follow the players in the
  flight (buy-ins), sometimes a straight split across flights. The
  lever exists as app_setting `gross_flight_pot_mode` ('buyins' default
  | 'even', v2.140.2, editable via scoring-setting-set). Decision
  points to finalize with Kerry: (a) when does each mode apply — per
  hole-count, per flight-cut style (handicap bands vs even cuts), or
  per event? (b) within-flight ladder — winner-take-all vs 1st/2nd
  proportions at which flight sizes? (c) does the same question apply
  to flighted SKINS pots (currently straight split)?
- Still manual: Skins ½ Net at <8 gross buyers on 9h (half-pop
  allocation rule unratified — the row shows "manual — ½-net rule
  pending").

## Next phase (ratified direction, mailbox ids 10-11)

Extract the GG game SETUP layer (handicap %, scoring basis, par-3
strokes, etc.) for every side game AND POINTS game into this doc.
Standard confirmed: all game configuration = admin-editable, VERSIONED
definitions (payout_templates pattern: append-only versions, per-event
snapshots, past events frozen) — never hard-coded rules.

## Not covered

HCM league games ($100 prize fund included; Skins Gross add-on $27),
Lone Star Cup (Side Games $75 add-on), TGF Championship special
add-ons (NET $50: R1 $15 + R2 $15 + Overall $20; GROSS $52: Skins
$18×2 + Weekend Individual $16), pre-season events. Per Pricing doc
§7.11 special-event side games are defined per event.

## Hole-In-One pot carry-in (v2.172.0, Kerry 2026-07-31)

*"Hole In One Pot is not persisting."* → follow-up: *"$3101 would show
for a bit, but would just disappear. $3101 is correct."*

**The real cause was a duplicate HTML id, not persistence.** The value was
stored and computed correctly throughout. `templates/events.html` renders
each event panel TWICE — into `#events-body` (desktop table) and
`#events-mobile-cards` (mobile list), CSS hiding one — and the running-pot
line carried `id="hio-running-inline"`. Two elements shared that id, and
`document.getElementById` returns only the FIRST in document order: the
desktop copy, which is the hidden one on a phone. On a render where only
the mobile copy existed the figure appeared; the next full `renderEvents()`
recreated both, the fetch filled the hidden desktop line, and the visible
one stayed blank. Same bug on the FINANCIAL panel's `id="hio-pot-running"`.

Fixed in v2.173.0: both lines are addressed by data attributes
(`data-hio-running`, `data-hio-pot-total`) and `paintHioLines()` fills
EVERY match. The payload is cached in `_hioPotData` and painted
synchronously while the panel HTML is built, so a repaint never flashes
empty, and a failed refresh leaves the last good value rather than wiping
it. **Never use a bare `id` in any per-event panel on this page** — the
double render makes every one of them ambiguous.

Separately (v2.172.0, NOT the cause of the above): `get_hio_pot` has read
`app_settings.hio_pot_carry_in` since 2026-07-20 (ratified $1,822) and
**no write path existed anywhere in the codebase**. That gap is real and
now closed, but the carry-in was already set in production.

- `POST /api/hio-pot/carry-in` (admin) → `set_app_setting`. Body:
  `carry_in` (required; `$` and `,` tolerated, negatives refused) and an
  optional `note` → `hio_pot_carry_in_note`.
- The GAMES-tab banner exposes it: admins with no carry-in set see a
  "no carry-in set" prompt; once set the line reads
  "Running pot thru X: $N (incl. $C carried in)".
- The banner's fetch no longer swallows failures. It previously mapped a
  non-OK response to null and had an empty `.catch()`, so a 500, a
  permission failure and a slow load were indistinguishable from each
  other — all rendered an empty line. It now prints the reason and uses
  `cache: "no-store"` so a fresh save is visible immediately.

Related dials, still with NO write path (set them by hand if needed):
`hio_27h_event_patterns` (27-hole days contribute $3/player) and
`hio_player_count_overrides` (field-size corrections). Worth an admin
screen if they ever need changing again.

Tests: `test_hio_carry_in.py`.

## 2026 TGF CHAMPIONSHIP — GAMES vocabulary + per-game breakdown (Kerry, 2026-08-07, RATIFIED)

Kerry's ruling on the open GAMES-axis question (session prompt 2026-08-07):
**YES / SAT / SUN / NO REPLACES NET | GROSS | NONE — but ONLY for the TGF
Championship.** It is not a second axis: the championship's games are
structured differently from normal events, so the event's vocabulary is a
per-event replacement, not a global change. Normal events keep NET/GROSS/NONE.

Kerry's per-game breakdown (2026-08-07, verbatim structure):

| Bucket | Game | Price |
|---|---|---:|
| Daily (per day) | Team Game | $8 |
| Daily (per day) | Skins | $18 |
| Daily (per day) | CTPs × 4 | $4 |
| Combined | Individual Net | $20 |
| Combined | Individual Gross | $20 |

Checks: Daily $8 + $18 + $4 = **$30/day** and Combined $20 + $20 = **$40** —
exactly the ratified bundle split ($100 = $30 SAT / $30 SUN / $40 COMBINED,
mailbox #276/#279), so the breakdown and the bundle economics agree.

Implementation status: NOT BUILT. This is carry-forward #3 (event-specific
GAME options) — money path (pot sizing, `_champ_roster_bundles`, payouts),
to be scoped with CA and not half-shipped before 08-15. The
`champ_single_day_assignments` dial remains the interim mechanism. The
hole-tab precedent (derive the tab set and cell vocabulary from the EVENT)
is the working model when it is built.

### Implementation (v2.211.0) — display axis + per-game opt-outs

- **Roster GAMES vocabulary is LIVE** on bucket-account events:
  `get_event_games_axis()` (database.py) classifies the roster via
  `_champ_roster_bundles` (full → YES, single-day → SAT/SUN, unassigned →
  DAY?, else NO), served at `GET /api/events/games-axis`; events.html
  renders YES|SAT|SUN|NO tabs + a read-only GAMES cell from it
  (`EVENT_GAMES_AXIS` / `axisGameValue` / `axisTabsHtml`). Normal events
  keep NET|GROSS|NONE. The cell is read-only because the value derives
  from the package + day assignment — fix a day via the
  `champ_single_day_assignments` dial (or the order's WHICH DAYS? note).
- **Per-game opt-outs** — `champ_subgame_optouts` app setting
  (`{"Carlos Zapata": {"SAT": ["Team Net"], "SUN": ["Team Net"],
  "COMBINED": ["Individual Net"]}}`). `record_championship_bucket_accounts`
  subtracts the opted-out rates from the bucket purses (real money — the
  player was credited exactly that), and `_bucket_subgames` recovers the
  full-field head count by adding those dollars back before dividing, so
  ONLY the named games lose heads ('N opted out' note). First case:
  Carlos Zapata (item 2453) — $36 credit = Team Net $8×2 + Individual
  Net $20; stays in Skins, CTPs, Individual Gross.
- The money path for such a credit is `partial_credit_transaction` /
  `scoring-partial-credit` (no holes change, no package change), then set
  the dial, then re-run `scoring-champ-buckets` to re-derive purses.

### 2026 TGF CHAMPIONSHIP — LOCKED payout schedule (Kerry, 2026-08-12: "Lock those.")

Full table in `docs/claude/runbook-tgf-championship-2026-08-14.md`. Mechanism
(v2.232.0): the `event_payout_schedules` app setting (keyed by event id →
bucket → game) overlays the derived per-game pots in
`get_event_bucket_accounts` — a lock REALLOCATES inside a bucket (skins
capped $10/hole, freed money to Team Net + CTPs) but never changes the
bucket's derived purse, and each game carries its payout lines onto the
GAMES tab with a LOCKED banner. Headline numbers: SAT skins $360 / Team Net
$360 ($240/$120) / CTP $58×4 · SUN skins $360 / Team Net $250 WTA / CTP
$48×4 · COMBINED Ind Net 2 flights × ($130/$78/$52) / Ind Gross 4 flights,
F1 $120/$60 (incl. $60 top-cut) F2–4 $80/$40. Total $2,814. Locked against
the 08-12 field — field moves ⇒ re-derive + re-confirm.

## A plus handicap comes off the ROUND, never off a hole (2026-09-16)

Kerry, watching Pat Youngs (+3) on the s9.23 MVP board:

> "For MVP nobody is allowed to have to add strokes on any given hole, so
> there should be no pluses on any holes. But his +3 PH still stands. The
> way it works on our side is that his total points gets deducted that 3
> strokes. It's not fair to make a player have to perform on any one
> hole, but it should be applied across a round."

Golf Genius allocates a plus handicap onto the easiest holes, so the
player must birdie a specific hole just to score what a scratch player
scores for a par. **This is the rule GG cannot express, and it is ours.**

**The rule.** For POINTS (MVP / Points Races):

1. Every hole is scored off **no strokes** for a plus player — a
   give-back stroke is clamped to zero, so no hole is ever harder than
   the card says.
2. The plus is subtracted from the **round's points total**, once:
   `points = Σ(hole points at scratch) − |PH|`.

The aggregate lands in the same place as GG's per-hole allocation; what
changes is that no single hole decides it.

**What is NOT changed.** Stroke-play **Individual Net** and **Team Net**
keep the real per-hole allocation — there the total is the total either
way, and Team Net's best ball is a ratified per-hole game. Gross games
(Skins, Individual Gross) never saw a handicap at all.

**Where it lives.** `get_event_leaderboard` (the EVENTS board) and
`live_scoring.build_cards` (the engine) apply the same two steps, and
both publish the deduction — `pts_plus_adjust` / `points_plus_adjust` —
so the board can print it. The PTS row shows the deduction beside the
label, because hole points that deliberately do not add up to the total
otherwise read as a bug. Test: `test_plus_handicap_points.py`.

### The rule lives in the MECHANISM (v2.459.0, 2026-09-16)

**Kerry, 2026-09-15 ~9:15 PM, looking at Pat Youngs' Quarry Front card on
`/handicaps`:** *"We just determined this isn't how we do Net Points with
pluses on holes."* The card showed NET SCORE 4 where GROSS was 3, the
`○` plus-stroke mark, and NET PTS 0 on a hole he parred.

v2.450.0 had implemented the rule **at the two call sites in front of
us**, not at the mechanism — the third instance in one night of a fix
landing on the instance instead of the class. v2.459.0 moves it:

- **`compute_hole_derivations(par, strokes, strokes_received, formulas,
  game=False)`** — with `game=True`, a NEGATIVE `strokes_received` (a
  stroke given back) reads as ZERO for `net`, `net_vs_par` and
  `stableford_net`. `adjusted_strokes` keeps the TRUE value in both
  modes. The flag is explicit and defaults OFF, so every WHS call site
  keeps its behaviour by doing nothing.
- **`plus_round_deduction(playing_handicap)`** — the round half, written
  once. `get_event_leaderboard`, `live_scoring.build_cards`,
  `get_scorecard` and `fetch_champ_player_card` all call it; the two
  v2.450.0 local patches are deleted. `test_plus_handicap_card.py`
  asserts there is exactly one executable copy of the arithmetic.

**Call-site table, settled.**

| Call site | Purpose | Plus strokes on holes |
|---|---|---|
| `get_differential_parity` | WHS | **KEEP** — untouched, no flag |
| `get_scoring_handicap_preview` | WHS | **KEEP** — untouched, no flag |
| `_two_nine_recap_rows` | WHS | **KEEP** — untouched, no flag |
| `derive_18hole_rounds_as_two_nines` | WHS | **KEEP** — untouched, no flag |
| `_nine_totals_for_card` | adjusted gross | **KEEP** — untouched, no flag |
| `get_event_leaderboard` | game | `game=True` (local patch removed) |
| `live_scoring.build_cards` | game | `game=True` (local patch removed) |
| `get_scorecard` | display | publishes BOTH views (see below) |
| `fetch_champ_player_card` | display | give-back dots clamped |

**Why `get_scorecard` publishes both.** `verify_scoring_round` compares
Golf Genius's own circle/square markings against `net_vs_par`, and GG
marks a plus player's hole WITH the give-back stroke. Clamping the base
keys would have turned every plus player's round into a false parity
failure. So the unflagged keys stay the true WHS derivation and the card
renders the `game_*` keys beside them: `game_strokes_received`,
`game_net_vs_par`, `game_stableford_net`, `strokes_given_back`, plus
round-level `plus_points_adjust` / `plus_strokes_adjust` /
`game_net_after_plus` / `game_stableford_net_after_plus`.

**The `○ = plus stroke` mark is gone** from `scorecard-render.js` and
`points-render.js`, legend entry included — there is no give-back on any
hole to mark. Both cards state the adjustment once instead: *"Plus
handicap +3: applied to the ROUND, not to any hole · NET 36 · NET PTS
8."* Nothing renders for a player who is not a plus.

**The worked example (the fixture in `test_plus_handicap_card.py`).** Pat
Youngs, 2026-09-15, The Quarry front, 2-Blue, playing handicap −3, gross
4,4,3,3,5,4,4,2,4 = 33.

| | before | after |
|---|---|---|
| NET row | 4,4,**4**,**4**,5,4,4,**3**,4 = 36, `○` on 3/4/8 | 4,4,3,3,5,4,4,2,4 = 33, no marks |
| NET PTS | 1,1,**0**,1,1,1,1,1,1 = 8 | 1,1,1,**2**,1,1,1,**2**,1 = 11 |
| round adjustment | none shown | −3 pts / +3 strokes |
| totals | NET 36 · NET PTS 8 | NET 36 · NET PTS 8 |

The totals match here because each affected hole sat in the linear part
of the net table, where one stroke is worth exactly one point. It is the
DISTRIBUTION that was wrong — and at the table edges (`nvp ≥ 2` flattens
at −1, `nvp −3` and `−4` are both 4) the totals diverge as well.

### RULED by Kerry 2026-09-16 (were OPEN under rule 3b)

1. **Rounding of the round deduction — HALF AWAY FROM ZERO** ("Standard
   rounding where .5 goes away from 0", CA Queue #5). `plus_round_deduction`
   is `int(abs(ph) + 0.5)` for a plus, never Python's banker's `round()`:
   −0.5 gives back 1, −2.5 gives back 3. This is the ROUND-level rule
   only; the per-player allowance rounding in ½ Net Skins is a different
   mechanism and is still open (CA Queue #7, side-games lane #533).
2. **The card's NET total — GROSS − PH = NET across the totals** ("Individual
   Net is not a pops per hole game... Gross Score - PH = Net Score";
   "I accept your recommendation"). The expanded scorecard carries PH and
   NET total columns beside OUT/IN, filled on the GROSS SCORE row of the
   block that closes the round; hole columns do not move. NET is
   `game_net_after_plus` (= gross − PH for everyone who is not a plus).
3. **`determine_tgf_mvp` reads the GAME view, FORWARD ONLY** ("MVP -
   Proceed"). For events on or after `PLUS_RULE_EFFECTIVE_DATE`
   (2026-09-15) the points are `game_stableford_net_after_plus`; before it
   the frozen WHS `stableford_net` — no MVP already decided can move
   (guiding principle 4). Pat's s9.23 total is 8 either way.

---

## The buy-in count selects WHICH GAME IS PLAYED (a9.23, RATIFIED 2026-09-16)

**Kerry, 2026-09-16, on the a9.23 skins:**

> "Yep, the game shifted due to buy ins based off of the side game matrix
> built in. That is the 1st level governing factor for game decision and
> different rules/controls come with that obviously for this situation
> changing it from a gross game to a net game with an applied percentage.
> I've attached the GG setup for review. Needs to be codified into the
> Tracker along with all other game settings."

### The finding, and the correction

a9.23 Avery Ranch, $52 of skins. Only **4 players bought the gross bundle**
on a nine, and the matrix switches Skins to ½ Net below 8 buyers on a nine.
So Golf Genius ran **"SKINS 1/2 Net $"** — a NET game.

Our engine computed skins on `"basis": "gross"` and carried
`"half_net_below": {"9": 8}` beside a comment saying the engine *"does not
yet implement"* it — and then computed gross anyway, behind a warning
nobody acted on. **A rule that only warns is not a rule.**

So we compared a net result against a gross computation, and reported that
Golf Genius was contradicting itself about Carlos Zapata's hole 7.
**It was not. We were wrong.** Zapata made **gross 4 on a par 4**, received
a stroke there under the 50% allowance, and **netted 3 — an outright net
birdie**, which is exactly what GG's detail line says. GG's scorecard par
and GG's skins-board birdie are the *gross* and the *net* of the same hole,
both correct.

**No money moves.** a9.23 was always paid correctly: Luke Youngs $39 (holes
2/3/5), Carlos Zapata $13 (hole 7), $52 across 4 skins. Zapata's handicap
differential (7.7 off gross 44) is untouched — the differential is computed
off gross and never saw the allowance.

### What is PROVEN, and what is still OPEN

GG's own detail lines are stated relative to par, which pins the allocation
from the outside:

| Player | GG detail | GG purse |
|---|---|---|
| YOUNGS, Luke | "Par on 2, Birdie on 3, Eagle on 5" | $39 |
| ZAPATA, Carlos | "Birdie on 7" | $13 |

- **PROVEN — Youngs received ZERO strokes.** Hole 5 is a par 5 he made in 3.
  GG calls it an **Eagle**; with a stroke it would have been an Albatross.
  His playing handicap is 1.0, so 50% = 0.5 and it **rounded DOWN**.
  Round-half-up is refuted by GG's own words, not merely by the payout.
- **PROVEN — the engine reproduces GG exactly.** Given the allocation those
  strings pin, `game_skins` independently returns Youngs holes 2/3/5 and
  Zapata hole 7, with the same vs-par labels and the same $39/$13 of $52.
- **OPEN (CA Queue #7) — how the half stroke ROUNDS.** Nothing pins what
  Zapata's 2.5 and Melchor's 3.5 do. **Every naive independent rounding
  awards Eduardo Melchor a fifth skin GG did not pay** (half-up 5 skins and
  contradicts the Eagle; banker's 6; floor 5). Brute force over all stroke
  counts leaves 21 allocations consistent with GG's board, and in *every*
  one Melchor ends up **≤** Zapata — which no independent per-player
  rounding of 2.5 and 3.5 produces. **The dial cannot be reverse-engineered
  from outcomes and must come from the GG setup screen or from Kerry.**

**RESOLVED 2026-09-16, and the bug was OURS — in two places.**

Kerry supplied the Golf Genius league handicap settings and GG's own worked
example for Eduardo Melchor. Neither was a rounding-mode question.

**(1) We applied the allowance to the ROUNDED playing handicap.** That
double-rounds. GG states the rule on its own settings page — *"The World
Handicap System requires full precision to be maintained in intermediary
calculations. Rounding is performed only once and as the last step"* — and
its Melchor line shows it:

```
index 5.6, Blue (slope 139 / rating 36.0 / par 36), front nine
CH   = 5.6 x 139/113 = 6.888...      <- unrounded, CARRIED
x50% = 3.444...                       <- allowance applied to the float
round ONCE -> PH 3                    <- GG's published column
```

We were computing `round(6.888) = 7`, then `7 x 50% = 3.5`. Zapata the same:
CH 5.491 (White, slope 133, rating 34.9 — a −1.1 course-rating-minus-par
adjustment), ×50% = 2.746 → **3**.

So **Melchor and Zapata both land on 3.** The "2.5 and 3.5" this lane spent
its time trying to round correctly *never existed* — they were artifacts of
our own double-rounding. That is why brute force found Melchor ≤ Zapata in
all 21 consistent allocations, and why no independent rounding of those two
numbers was ever going to work.

**(2) Stroke allocation.** GG is set to *"Allocate strokes based on the full
card Stroke Index Allocation"*, not its *"subset of holes played"* (which GG
marks Recommended and TGF does not use). A stroke lands only where the
18-hole stroke index is ≤ the playing handicap — so on a front nine with odd
indexes, **a playing handicap of 3 delivers only TWO strokes**, because index
2 is on the back nine and is not played.

**Rounding is half-up.** GG's "Round up" means round *half* up, not ceiling:
its tooltip reads *"A handicap allowance 50% applied to a CH of 13 becomes
7"* (6.5 → 7), and 3.444 → 3 confirms nearest. This does **not** conflict
with the CA Queue #5 plus-handicap ruling — that is a round-level deduction,
a different mechanism, exactly as mailbox #530 said.

**What is ratified by what.** The distinction is recorded in code and asserted
in `test_half_net_skins.py`:

| Dial | Ratified by | Strength |
|---|---|---|
| Allowance on the unrounded CH, rounded once | replay | **Proven** — reproduces GG's published handicap column for all four players |
| Rounding half-up | GG settings screen | Confirmed, and consistent with a9.23 |
| Full-card allocation | GG settings screen **only** | a9.23 does **not** discriminate it — both modes reproduce its board |

Matching GG's board alone could be luck. Matching the Playing Handicap column
GG printed, from index and tee, cannot — that is what closed this.

**Where an unrounded course handicap is not available**, the engine falls
back to the rounded playing handicap and reports `precision_loss` with a
warning on the board, rather than silently computing a number GG would not
have used.

### The governing rule when we and GG disagree

**Kerry, 2026-09-16: "Until we detach from GG, GG rules. When untethered,
obviously we rule everything."**

That is the tie-breaker for every future conflict of this shape, and it is
why the dials above are set to reproduce Golf Genius rather than to express
TGF's own preference. The half-Net rounding and the plus-handicap deduction
(CA Queue #5) round differently *on purpose*: one is GG's mechanism and we
match it, the other is TGF's own and we rule it.

### The GG setup screen IS the schema

Kerry's attached a9.23 setup maps almost one-for-one onto what a
`game_template_versions.config_json` must carry (game-engine.md):

| GG field | a9.23 Skins value | Where it lives now |
|---|---|---|
| Name | SKINS 1/2 Net $ | variant `gg_name` |
| Format | Basic Skins | `format: "skins"` |
| Competition | Player v. Field | `competition` |
| Balls | Own Ball on each hole | — |
| Holes | 9 Holes (Front or Back) | `when_buyers` key |
| Skins with Carry | No | *(not yet modelled — see open items)* |
| To win Skin, score must be | Any score | *(not yet modelled)* |
| Validated on next hole by | No validation | *(not yet modelled)* |
| **Handicap** | **USGA Net (off lowest)** | `handicap.method` + `off_lowest` |
| **Handicap Allowance** | **50%** | `handicap.allowance_pct` |
| Purse & Points | pro-rata to Skins won | matrix |
| Purse pot | 52.0 | matrix ($13×N, all of the gross pool below 16) |
| Round allocated purse down to | 0 (no rounding) | matrix |

**Allowance % and "off lowest" are TWO SEPARATE DIALS.** USGA's allowance is
a percentage of each player's own Course Handicap; "off the lowest in the
group" is an additional TGF/GG convention (USGA applies play-off-the-low to
**match** play). The starter sheet's own footnote carries both: *"TEAM —
Team Net handicap: Best 1 net ball, 75% of PH, off the lowest in the
group."* They are stored as separate fields or the maths goes wrong in one
direction or the other.

*(Note: on a9.23 "off lowest" happened to be a no-op — Robert Straiton
played off 0.0 and was the low — so this event does not test that dial
either.)*

---

## Pops are a property of the GAME, not of the card (2026-09-16)

**Kerry, 2026-09-16, on Individual Net:**

> "Individual Net is not a pops per hole game, so pops don't need to show on
> individual net views. It is instead a Gross Score - PH = Net Score. It's
> based off the raw gross total minus their playing handicap (Pat +3).
> Typically on a scorecard the playing handicap is displayed between the
> GROSS Score and the NET Score columns."

**The rule.** Every game DECLARES `pops_per_hole`:

| Game | `pops_per_hole` | Why |
|---|---|---|
| Individual Net | **false** | round-level: `gross total − playing handicap` |
| Individual Gross | **false** | never sees a handicap at all |
| Team Net (best ball) | **true** | the best ball on a hole can't be picked without knowing which ball got the stroke |
| Net Points / MVP (Stableford) | **true** | Stableford scores each hole |
| ½-Net Skins | **true** | the hole is the unit of the game |
| CTP / Hole-in-One | **false** | not handicap games |

**Every surface must READ this flag rather than assume.** Rendering per-hole
net everywhere is precisely why a plus handicapper's Individual Net view
showed `○` marks for a mechanic that game does not use.

**And a game derives its OWN strokes.** A card carries whatever allocation
the event's headline net game used; a *different* game on the same card has
a different allowance and may have none. `live_scoring.game_handicaps`
therefore derives each game's allocation from the playing handicap under
that game's own dials — allowance → rounding → off-lowest → allocate by
stroke index — rather than borrowing the card's.

---

## USGA handicap allowances (Rules of Handicapping, Appendix C)

Recorded as DATA in `live_scoring._USGA_ALLOWANCES`, **with its verification
state**, so no game carries a percentage in code and no reader has to guess
how sure we are.

**Kerry, 2026-09-16:** *"Team Net is 75% for one ball, 85% for two ball, and
100% for 3 or 4. Cart Net is (I believe) 85% for one ball and 100% for 2
ball...need you to check USGA's recommendations."*

### CONFIRMED — the four-player ladder (TEAM Net)

| Format | Allowance | State |
|---|---|---|
| Best 1 of 4 | **75%** | confirmed |
| Best 2 of 4 | **85%** | confirmed |
| Best 3 of 4 | **100%** | confirmed |
| Best 4 of 4 | **100%** | confirmed |

Matches Kerry's ruling exactly, and matches the Team Net definition v1
already in this doc ("Best 1 → 75%, Best 2 → 85%, Best 3 → 100%, Best 4 →
100%"). Team Net's allowance now follows the **ball count**, as data
(`allowance_pct_by_balls`), so the standard Best-1/Best-2 rotation carries
its percentage automatically.

### NOT CONFIRMED — the two-player ladder (CART Net). CA Queue #8.

| Format | Kerry's recollection | State |
|---|---|---|
| Best 1 of 2 | 85% | **unconfirmed** (USGA's Four-Ball Stroke Play *is* 85%, which agrees, but unverified here) |
| Best 2 of 2 (both count) | 100% | **UNRESOLVED — carries no value** |

**Why it is not simply taken.** `usga.org` is blocked by the network egress
proxy (403 on CONNECT) — as it was for the parent session — and so are
`randa.org`, the mirrored Appendix C PDFs, and FORE Magazine. Only search
**snippets** were reachable, and a snippet is not the Rules of Handicapping.
The four-player ladder was corroborated by two independent searches agreeing
exactly with what Kerry had already ratified, which is why it is recorded;
the two-ball Cart Net row had no such agreement.

**The unconfirmed rows carry `allowance_pct: None` rather than a plausible
number.** Nothing may fall back to a default for them — a game that needs
one must report, not assume. This is money.

