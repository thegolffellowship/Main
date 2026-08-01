# Game Creator engine + untether-from-GG (design of record, 2026-07-06)

Admin direction (2026-07-06): build TGF's own **Game Creator engine** —
create / edit / **version-control** every event game AND season contest —
and progressively **untether from Golf Genius** so GG is eventually only
a raw-score source (and later, not even that). Everything customizable,
but standardizable. This is Platform V2.0 (scoring) territory; the
Tracker prototypes the schema + the shadow leaderboard first.

> Reconcile with the Platform planning: the claude.ai TGF Project + the
> OneDrive docs already outline a Game Creator. This is the Tracker-side
> design to align with that — treat as a starting point, not a rewrite.

## Untether staging (prove parity before we cut the cord)

- **Stage 0 — NOW (done):** GG is the official scorer. We import GG
  scorecards, compute net/gross Stableford, MVP, and points in our own
  formula layer, and `verify_scoring_round` proves per-hole parity
  (strokes, net, GG's circle/square markings). Both points schedules are
  GG-config-validated (see scoring.md).
- **Stage 1 — parallel shadow leaderboard. HARNESS BUILT (v2.150.0),
  PARITY NOT YET PROVEN ON REAL EVENTS.** Rely on GG for ONLY the raw
  gross hole scores; compute EVERYTHING ourselves (all games, all races)
  from those. Stand a live leaderboard next to GG's at a real event and
  diff, game-by-game and race-by-race, until we reproduce GG exactly. GG
  stays official; we shadow. This is the confidence gate.

  The **Live Scoring Test Center** (`/admin/test-center`, admin-only) is
  that leaderboard + diff harness: `email_parser/live_scoring.py` computes
  Individual Net, Individual Gross, Team Net, Skins, MVP and CTP/HIO from
  raw gross hole scores plus our own course/tee facts and playing
  handicaps, and seeding a session from a real event diffs every number
  against what GG recorded. Rules-as-data throughout
  (`SEED_LIVE_SCORING_CONFIG`, transcribed from the ratified side-games
  spec), customer_id-keyed, no DB/Flask in the engine — the portability
  conditions this doc's Gateways section sets. Full spec:
  `docs/claude/live-scoring-test-center.md`.

  **What remains before Stage 1 can be called done:** run the harness
  against real events until the parity report reads clean across a
  meaningful sample. Known gaps it will surface first — flighting beyond
  the one observed 9-hole HCP-12.0 split is a fallback equal-size guess;
  Skins ½ Net (sub-8-buyer nines) is detected but not computed; the blind
  draw for short Team Net foursomes is warned but not generated; and no
  game pays out yet (the prize matrix + `season_payouts.py` are the next
  join). Race-by-race diffing is also still outstanding — the harness is
  per-round today.
- **Stage 2 — FINAL: own score entry.** Customers enter raw gross hole
  scores directly in our app (mobile, offline queue, magic-link auth we
  already have from the member portal). Our engine computes the rest; GG
  leaves the loop entirely. Concurrent writes + realtime => Supabase (the
  scoped Platform stack; see member-portal.md).

Everything upstream of "raw gross hole scores" is already ours — so the
only genuinely new build for Stage 1 is the leaderboard surface + the
diff harness (both now built; see Stage 1 above). Stage 2 adds the
score-entry UI + write path — the Test Center's score grid is that path
in miniature (one hole, one player, board recomputed on read) against
sandbox tables, so the shape is proven before it touches real rounds.

## Two definition layers (both versioned, append-only, per-event/season frozen)

### 1. Game definitions (per-event games)

One versioned template per game type: Team Net, MVP, Individual Net,
Skins, Individual Gross, CTP / Longest Putt, Hole-in-One, Match Play,
and the POINTS games (net + gross). A version's config JSON holds every
attribute we've been reverse-engineering from GG (which are TGF
standards, not GG's — see side-games.md):

- **Format**: Stableford / Stroke / Match / Skins.
- **Competition**: Player v Field / v Flight / Foursome v Field.
- **Scoring basis**: net / gross / net-off-lowest.
- **Points schedule**: the Assign-Points tables (net + gross, regular +
  championship) — already in `_SCORING_FORMULA_DEFAULTS` /
  `get_championship_formulas`.
- **Handicap**: allowance %, Max Playing Handicap cap (36/18),
  disallow-strokes-on-par-3 (team games), Max Triple gross cap.
- **Payout**: driven by the prize matrix — player-count-adaptive,
  flight bands, place splits (games-matrix + the matrix audit rules).
- **Eligibility**: members-only, buyers-only, guests-pay-cannot-win, etc.

### 2. Season-contest definitions (cross-event races)

City Net, THE PLAYERS CUP (gross), Monthly, Match Play season,
Fellowship Cup, City/TGF Championships. Attributes (admin's examples):

- **Scope**: chapter / TGF-wide / **regional** (future, as TGF grows).
- **Basis**: net / gross.
- **Accumulation**: best-X-of-total / all-events (+ always-count events
  like City Championship).
- **Months toggle** (for Monthly): which months on/off (currently
  Mar-Jul + Sep + Oct; August & off-season off).
- **Funding**: dues-funded ($1/mo/membership), buy-in, or none;
  auto-entry vs opt-in.
- **Weighting / reset**: championship +1 schedule, season reset, etc.

Monthly Points is the canonical worked example: a TGF-wide, net,
all-events, dues-funded, auto-entry seasonal contest with a
months-on/off attribute — every one of those is a toggle in the engine,
not hard-code.

## Data model sketch (portable to Supabase / Postgres)

Mirror the ratified **payout_templates pattern** (append-only versions,
per-event/season snapshots, past events frozen — Guiding Principle 4):

- `game_templates(id, name, kind)` + `game_template_versions(template_id,
  version, effective_from, config_json, created_by, created_at)`.
- `event_games(event_id, game_template_version_id)` — the per-event
  SNAPSHOT; frozen once the event is scored (editing a template later
  never rewrites history).
- `season_contest_templates(id, name)` +
  `season_contest_versions(template_id, version, config_json, ...)`.
- `season_contest_snapshots(season, contest_template_version_id, scope,
  ...)` — one per season/scope.

`config_json` carries the attribute set above so a non-developer edits a
game in a UI (Guiding Principle 2: rules-are-data, not code). All
customer references by `customer_id` FK (Principle 6). Points routing
joins `scoring_rounds.customer_id -> customers.chapter` — NO items table.

## Reuses what already exists

Formula layer (net/gross/championship Stableford, admin-tunable) ·
`verify_scoring_round` (the diff harness's core) · games-matrix +
matrix audit (payout structures) · `determine_tgf_mvp` (a game
computed entirely from our data) · magic-link auth + member portal
(Stage 2 score entry) · gg_data_snapshots (persisted standings).

## Gateways

Per the discipline: no TGF Platform coding until gateways pass. The
Game Creator + own-scoring is V2.0 (2027 target). What the Tracker does
NOW: prototype the definition schema, and run the Stage-1 shadow
leaderboard as a portable experiment — everything built rules-based and
customer_id-keyed so it lifts to the Platform (Supabase) with minimal
rework.


## Platform reconciliation (mailbox ids 16-20, 2026-07-06)

**Key finding (id 16):** the Platform's "Game Creator" is COMMERCE
configuration only (what's sold, price, who can buy) — scoring/
execution config was deliberately never designed. **This doc is the
first scoring-config design in TGF's documentation = the V2.0
prototype.** Platform entity model is LOCKED; stay portable to it:

- `games` (master library: name, category enum, default buy-ins,
  requires_handicap; NO scoring columns) · `bundles`/`bundle_games`
  (price = SUM(buy-ins) + markup, never stored) ·
  `event_included_games` (event↔game junction w/ buy_in_override).
- `season_contests` — chapter_id FK → **org_units (hierarchical:
  chapter → region → national)**, contest_type enum, best_of_count,
  **scoring_config JSONB ← the V2.0 hook: every attribute in this doc
  must serialize into it unchanged**, lsc_qualifying, lifecycle.
- `season_contest_enrollments` (user + chapter CAPTURED AT ENROLLMENT
  + order_item linkage) · `season_contest_events` (points_multiplier
  column exists but is NOT the championship mechanism — inert at 1.00
  per the id 17 ratification; championships = required-add).
- **Scope**: resolve our scope attribute to an org_unit reference
  (TGF-wide = national node, regional = region node) — no scope column.
- **Versioning**: Platform V1.0 does NOT version definitions (archive
  only; point-in-time truth on purchase records). V2.0 ADDS our
  versioned tables on top — design them to key to games.game_id /
  season_contests ids so the migration is additive.
- **Identity**: Platform has ZERO scoring tables; key all scoring
  records by customer_id, which maps 1:1 to users.user_id at Stage 4.
  Chapter routing equivalent: users.home_chapter_id + enrollment-time
  snapshot.
- Alignment asks accepted: keep entity names close; JSON-shaped
  attributes; our attribute-driven design will obsolete contest_type
  enum (acceptable V2.0 evolution, noted).

**Season-contest payout economics (id 18, Kerry-ratified; full spec
TGF_Season_Contest_Payouts_v1_0.md, OneDrive 7_Web & App Development/):**
NET Bundle $90 = $40 City Net (chapter) + $40 Fellowship Cup
(TGF-wide) + $10 markup; Players Cup $50 = $40 + $10; Match Play $50 =
$40 + $10 (CHAPTER scope). Universal: exact-division rounding; places
graduate by field size (places = round(N × %paid(N)), %paid decays
linearly); 1st never decreases as N grows; City = broad, Cup =
top-heavy. City Net %paid 30%@N=10 → 20%@N=60 (min 2). Fellowship Cup
15%@N=20 → 10%@N=100 (min 3); **Cup 1st = 45% flat until $1,008 at
N=56, then $1,008 + 20% of pot above $2,240**. Players Cup: 4 fixed
flights (<6.0 / 6-11.9 / 12-17.9 / 18+), 10% Champion off top, 90% ÷ 4
flights, 67/33 within flight. Config needs: pot rate/entry,
places-curve (two endpoints + min), ladder families, fixed-share
anchors w/ dollar-threshold tapers, flight structures + champion
bonus, pool-structure lookup + per-pool bonus, per-win payout mode.

**IMPLEMENTED (v2.58.0, Kerry directive 2026-07-10):**
`email_parser/season_payouts.py` — pure engine (Platform-portable, no
DB/Flask) with `SEED_SEASON_PAYOUT_CONFIG` rules-as-data:
`city_net_payouts(n)` / `fellowship_cup_payouts(n)` /
`players_cup_payouts(n)`, reusing match_play's largest-remainder
`allocate_cents`. `test_season_payouts.py` proves parity with every
worked matrix in the v1.0 spec (SA N=18 $252/$180/$129.60/$86.40/$72;
Austin N=9; Cup N=27; Players Cup N=16 champ $64 + $96.48/$47.52) plus
invariants (pot always fully paid, ladders descending, Cup 1st
monotonic through the $1,008 taper). The points-race API payloads carry
`projected_payouts` computed from the LIVE buy-in count (ranked +
enrolled_not_ranked; Cup N = both chapters' NET buy-ins), and the
CONTESTS standings render a purse strip (PURSE pill + per-place chips)
plus green $ badges on the rows that would cash if the season ended
today — only bought-in players are eligible, so the money visibly
flows past non-enrolled rows (the conversion nudge, Kerry). Players
Cup: champion badge stacks with flight-1st on the same player.
Interpretation choices pending Kerry (spec §8): Cup remainder ladders
are the proposed defaults; past the $2,240 pot threshold the remainder
ladder is renormalized over (pot − 1st); tie rows are paid down the
ladder sequentially (no split display); Cup places capped at 5 and City
at 7 until Kerry extends the ladder families.

**FALL NET races (Kerry, 2026-07-10):** SA FALL NET + AUSTIN FALL NET
start Saturday 2026-08-29; season total = **best 6 event totals + the
Fall Championship**, and that DECIDES the race — the fall races are
STANDALONE chapter contests: no points reset, no feed into the
cups/TGF Championship (Kerry, 2026-07-10 — do not apply the four-step
structure here). Preview
pages live in the CONTESTS race selector (below Monthly, burnt-orange
"upcoming" chips) with an inline sign-up CTA; enrollments stored as
season_contests rows with season='<year> Fall'. **AUTOMATIC as of
v2.63.0 (Kerry: the umbrella SEASON CONTESTS product carries the fall
option — no separate product):** the parser extracts
`items.fall_net_points_race` (new column; prompt keys on any
FALL+NET/Points field label) and sync_season_contests_from_items maps
YES → NET Points Race / '<year> Fall', chapter from the canonical
customer — fall pages populate on receipt of new orders like
everything else. `scoring-fall-enroll:<customer_id>[:<item_id>]`
remains as the manual fallback (Kerry/no-purchase cases);
manually_enrolled=1 rows are cleanup-protected. First three: Luke
Mazanec (item 2258), Kerry Niester (manual), Adam Baker (item 2259). Wire the GG
league/page ids into _GG_POINTS_RACES when the fall races are created
and the preview pages inherit standings/payouts automatically.

## Wallet/refund contract notes (mailbox ids 22/24, Kerry-ratified 2026-07-06)

Platform-side decisions banked for the Stage-4 bridge (no Tracker code
change yet): (1) **VOID verb ratified** — wallet contract is ADD (Tracker)
/ VOID (Tracker requests, Platform executes, returns `voided_remaining`)
/ SPEND (Platform checkout); when a wallet credit is cashed out via
Venmo, VOID first and Venmo only the returned `voided_remaining`;
idempotent on the credit's `external_ref` (= our Tracker credit id —
every ADD must carry it). (2) **"Money goes back the way it came"** —
the 30-day NEW-member membership guarantee refunds via **Stripe from
the Platform** (guarantee-only exception; new members, not renewals);
all Tracker-era money still refunds via Venmo from the Tracker; never
cross rails. (3) New-member membership revenue is held (Platform
`held_until`) during the guarantee window — no effect on our $1/active-
member monthly purse counting.

## Match Play in CONTESTS — BUILT v2.34.0 (directive: Kerry via ids 19-20)

Shipped 2026-07-06. The 29-column **Prizes-Match Play Matrix.xlsx**
(OneDrive/01_STANDARDS/Prizes/, July 6 final) is implemented as
versioned rules-as-data; `test_match_play.py` proves engine↔xlsx parity
on every column. Matrix by N (4-32):
- POOLS: 4-5→1 | 6-10→2 | 11-15→3 | 16-19→4 | 20-23→5 | 24-27→6 |
  28-31→7 | 32→8 (pool sizes 3-5, balanced; 2 advance per pool;
  ~3 matches/player — pools of 5 may play 4)
- KNOCKOUT: 4-5→2 | 6-10→4 | 11-19→8 | 20-23→12 **w/ first-round byes
  for top 4 seeds** | 24-32→16
- WILDCARDS: 0 (4-10, 16-19, 32) | 2 (11-15, 20-23, 28-31) | 4 (24-27)
  — filled by the best non-advancing pool finishers by the seeding metric
- SEEDING: knockout seeds = most Stableford points accumulated across
  the pool matches (ratified); classic placement 1v8/4v5/2v7/3v6, a
  12-field plays inside a 16 template (missing seeds = byes).
  **EXCEPTION — 4-player knockout (Kerry 2026-07-14): semis are
  CROSS-POOL — each pool winner vs the OTHER pool's runner-up.
  Stableford does NOT seed that bracket; it only breaks record ties in
  pool finishes (pool rank amended by D-MP-09 to points-of-3 →
  aggregate H2H → Stableford — see register below).**
  Engine: `cross_pool_semi_order()` in match_play.py; config key
  `seeding_knockout4` (default `cross_pool` — old snapshots without the
  key get the rule too); `cmp_seed_knockout` falls back to Stableford
  seeding with a warning if the field isn't two pools × two advancers.
- POOL WINNER BONUS: flat $20/pool winner, off the pot first (the
  earlier "$25 at N=4" is stale — #181 fold; the badge is flat $20 at
  every N, confirmed in the CD canvas review #213).
- LADDERS (% of adjusted pot): 4→71.5/28.5 (=$100.10/$39.90) |
  5→66.67/33.33 (=$120/$60) | 6→62.5/22.5/15 | 7→55/25/20 | 8-10→50/30/20
  | 11+→50/25/15/10. (The xlsx supersedes the earlier "4-5→75/25" note;
  the earlier "$97/$38" N=4 figure was computed off the stale $25 bonus —
  with the flat $20 bonus the N=4 adjusted pot is $160−$20=$140 →
  $100.10/$39.90. #181 fold.) Pot = $40×N. Largest-remainder cents
  allocation → payouts always sum exactly. TIE-SPLIT: closed as D-MP-08
  (see register below) — consolation match is primary at N≥6, the
  SF-losers combined-place split is the FALLBACK.

### D-MP RULES REGISTER — COMPLETE (ratified 2026-07-16/17, mailbox #213–#217)

The full Match Play rules register **D-MP-01 → 09 is closed** (D-MP-09
closed the last #21 item, pools-of-5 scheduling). This register is the
ruling of record and supersedes the "Open questions (id 21)" defaults
below wherever they conflict.

- **D-MP-03 · pool assignment default = `random`.** `pool_assignment_mode`
  defaults to random draw (not handicap-snake). Pool-view copy renders
  random-draw language by default.

- **D-MP-04 · asymmetric knockout placement (P1–P4), all ratified:**
  - **P1 SEED ORDER:** tiers are absolute — pool winners (1–3) > runners-up
    > wildcards. Within a tier, rank by pool-play Stableford. Residual
    ties: pool W–L → head-to-head (where played) → **lower TGF index takes
    the higher seed (index SNAPSHOTTED at bracket-seeding time)** →
    **earliest Match Play enrollment date** (final backstop). Fully
    deterministic, zero manager steps — the witnessed-draw step is
    replaced by the index + enrollment-date chain. (New vs current code:
    the index-snapshot + enrollment-date steps did not previously exist.)
  - **P2 SLOTTING:** classic 1v8/4v5 top half, 2v7/3v6 bottom; 12-in-16
    band byes to seeds 1–4.
  - **P3 SEPARATION:** any same-pool round-one pairing → the LOWER seed
    swaps to the nearest seed line in the OPPOSITE half (same-tier trade
    preferred; minimal cross-tier swap otherwise; unavoidable collisions
    land on the lowest seed lines). **The higher seed never moves.**
  - **P4 TRANSPARENCY (requirement, not a design choice):** seed numbers
    + WC chips visible on every bracket surface (member, manager, CD
    canvas). The bracket must show its math.
  - The **4-player cross-pool exception** (2026-07-14, above) stands
    unchanged — P1–P3 govern 8/12/16 brackets only.

- **D-MP-08 · 3rd-place consolation + fallback (N≥6).** The consolation
  match between the two semifinal losers is the STANDARD mechanism at
  N≥6 — it decides 3rd vs 4th money (or 3rd vs nothing on 3-place
  ladders). **No consolation at N=4–5** (2 places only). **FALLBACK when
  the match can't be coordinated:** split the remaining place money
  evenly — 3-place ladders (N=8–10) split 3rd (20% → 10/10); 4-place
  ladders (N=11+) split 3rd+4th combined (25% → 12.5/12.5). Stableford
  tiebreak rejected for this purpose. Encode as a consolation-match
  entity with played/unplayed state; the previously-coded SF-losers-split
  becomes the FALLBACK path, not the primary. (Side effect: confirms
  split-combined for Match Play ties of this class.)

- **D-MP-09 · unified pool counting — every player counts exactly 3
  matches, at every pool size.**
  - Pool of 4: clean round robin, 3 matches, all count.
  - Pool of 5: 8 matches total — one player plays a forced 4th (parity
    makes "all play 3" impossible).
  - Pool of 3: **5 matches total** (single RR + two repeats) — same shape;
    one player plays a forced 4th, each player's counting schedule
    includes one repeat opponent.
  - **Counting rule for the 4-match player: FIRST 3 BY MATCH DATE count —
    record AND Stableford; the 4th counts only for its opponent.** (Chosen
    over best-3-of-4 and over win-%/per-match-average; the extra match must
    never advantage its player.)
  - **Pool RANK = match points of 3 (win 1, TIE ½, loss 0) → head-to-head
    (AGGREGATE across repeat meetings; may be empty in 5-pools → fall
    through) → pool Stableford (first-3-only for the 4-match player).**
    This supersedes the earlier `wins → W−L → Stableford`.
  - **4th-match assignment** (banked as pairings-generator requirement #1,
    NOT the full pairings spec): when multiple pool-mates are available
    for the forced 4th, assign to lower TGF index, then earliest signup.
  - Member-facing sentence: "Everyone counts three matches."

- **D-MP-10 · handicap allowance is OFF LOWEST; percentage differs
  historical-vs-future (Kerry 2026-07-17).** Every TGF match plays OFF THE
  LOWEST: the lower course handicap is subtracted from both, so the lower
  handicapper plays scratch and the higher receives the (rounded) difference,
  allocated on the hardest holes by stroke index; equal handicaps play
  straight up.
  - **Historical (GG-originated) events — allowance was PER CHAPTER:** San
    Antonio **75%**, Austin **100%**. Robert ran Austin at 100%; Kerry ran SA
    at 75%. The read-only reconciler (`cmp_reconcile_match_play_75`,
    `_CMP_ALLOWANCE_BY_CHAPTER`) must use each chapter's real historical
    allowance when checking stored results against GG.
  - **Future (Tracker-originated) events — ONE uniform, adjustable allowance
    for ALL chapters:** default **75%**, settable (e.g. 90%, 100%). Single
    game-engine config value, not per-chapter. **Config encode PENDING Kerry's
    ship-approval** (money/member-facing → rule 3b); the design intent is
    ratified, the durable config key is not yet written.
  - Why it matters: the earlier reconciliation derived pops from the
    stroke-play `strokes_received` in the GG import — 100% allowance, full
    field allocation, NOT off-lowest — so its margins/all-square calls were
    wrong (Chandler/Rideout s9.15 computed AS while GG shows Chandler 1 up).

- **D-MP-11 · match mechanics uncovered 2026-07-17 (→ CA for the end-to-end
  Match Play documentation; several are Tracker GAPS).** The GG-source audit
  (`cmp_import_gg_match_play`, `email_parser/gg_match_play.py`) surfaced
  mechanics that affect SETUP, RECORDATION, and WINNER DETERMINATION and are
  not yet fully modeled. **North star (Kerry): simplicity for MANY chapters +
  scaling** — one rule over per-chapter special cases, derive-don't-ask,
  near-zero bespoke setup per chapter (the future uniform allowance is the
  model for collapsing per-chapter divergence):
  - **Starting hole (shotgun).** Each match may begin on a different hole
    (Niester/Wade started on 5; a9.17 matches on 10, the back nine). Winner /
    margin must be computed in PLAY ORDER from the starting hole ("X up with Y
    to play"), and the member scorecard + dots must render from the starting
    hole, wrapping (5→9→1→4). GG marks it (`starting_hole_mark`); we read it.
    **DONE in the reconcilers as of v2.125.0** (Kerry 2026-07-20: "a match
    that starts on 4 goes to 1 after 9 — it doesn't go to 10"): both read-only
    reconcilers previously walked holes in ascending number order, producing
    wrong X&Y margins for every shotgun start — the source of the false
    margin-mismatch reports; stored results were correct. `_cmp_derive_match`
    now takes a play order from `_cmp_gg_play_order` (GG snapshot's explicit
    per-hole `order`, else `_cmp_play_order` wrap from `start_hole`).
  - **NET matches.** net = gross − off-lowest strokes; per-hole handicap stroke
    dots must be recorded and shown.
  - **Extra holes / sudden death (GAP — not modeled).** A match all-square after
    regulation goes to extra hole(s); the winner wins the next hole (e.g. Youngs
    v Marques and Barna v Cloer were AS after 9, decided on the first extra hole
    — currently stored `1 UP`, GG's 9-hole card shows AS). The Tracker has NO
    extra-hole entity. **Notation (Ryder Cup, Kerry):** holes PLAYED + "H" — a
    9-hole match decided on the first extra hole = `10H` (holes played, not the
    physical hole number; a shotgun match started on 5 also reads `10H`). **Needs:
    score entry for the extra hole(s) that ALSO configures handicap pops**
    (continue the off-lowest allocation onto extra holes by stroke index → net
    decides the hole), the recorded `NH` result, and a member-display treatment.
  - **Putt-offs (GAP).** Another all-square resolution class (Chandler/Peterson
    s9.12, Niester/Wade s9.15). Needs a recordation path + display.
  - **All-square resolution ladder — notation RATIFIED (Kerry 2026-07-20):
    KEEP BOTH conventions; the label describes the MECHANISM.** `NH`
    (holes played + H, Ryder style — e.g. `10H`) when extra hole(s) were
    actually played; `Putt Off` when a putt-off decided it. Nothing
    relabels; both are live (Austin's two 10H matches, SA's three
    Putt Offs). The future untethered app PRESENTS the directional choice
    to players on an AS knockout match (Putt-Off vs Extra Holes, with
    practical constraints surfaced) and the pick drives recordation +
    label — see the tie-resolution decision flow below. **NH is a COUNT,
    not a fixed label (Kerry 2026-07-20):** `10H` means a 9-hole match won
    on the FIRST extra hole; a second extra hole makes it `11H`, and an
    18-hole match won on the first extra hole is `19H`. The app provides
    leaderboard score ENTRY for each extra hole (as many as needed, pops
    continuing off-lowest by stroke index) and the final label reflects
    the actual holes played.
  - **Tie-resolution decision flow (ultimate-app).** At end of regulation on an
    All Square match the app presents STAGE-AWARE options (rules-derived): a
    **pool** round (tie-allowed stage) offers "End in a tie / Halved" (½ each
    under D-MP-09); a **knockout** (must-produce-a-winner) prompts "How do you
    want to determine the match? Putt-Off or Extra Holes?", surfacing practical
    constraints ("has to be completed tonight" — daylight/pace/availability).
    The choice feeds recordation (extra holes / putt-off) + display and yields
    the winner or recorded halve.
  - **Matches span events.** A match may be played/made-up at a DIFFERENT event
    than its home/pool event (Hogue/Kirksey is on a9.12 in our data, a9.17 in
    GG). Recordation must not tie a match to one event; alignment is by pool
    PAIR, not event.
  - **2026 season rulings (Kerry 2026-07-20):** NO 3rd-place consolation
    matches this season — semifinal losers SPLIT the combined 3rd/4th
    money (the D-MP-08 `split_combined_places` fallback; the payout sheet
    already does this when no consolation match is recorded, and the
    manager-only consolation recording stays hidden). **WD standings
    display**: a withdrawn player who PLAYED matches sorts to the bottom
    of the pool standings keeping the WD tag + record (Campos); a
    withdrawn player with NO played matches is a clean removal + refund
    and disappears from standings (`_cmp_apply_wd_sort`, both rank
    paths).
  - **GG is the audit source; frozen results never move.** Winners, W-L-T
    records, knockout qualifiers, and seeding are frozen; reconciliation reads
    GG's computed match (concessions/gimmes included) to align DISPLAY detail
    to the recorded winner — never to change it.
  - **Result hardening (v2.125.0, Kerry 2026-07-20: "once we get these
    verified we need to harden these in the database so they don't change
    again").** `cmp_matches.result_locked_at`/`result_locked_note`;
    `cmp_lock_verified_results` (bridge `scoring-mp-lock:<season>|<chapter>
    [|apply]`, dry-run default) locks every played match whose stored result
    matches GG's own card exactly, or where GG shows AS and we recorded the
    extra-holes/putt-off outcome. Conflicts and no-GG-card matches are
    reported, never auto-locked. Locked rows refuse winner/margin changes and
    deletion in `cmp_save_match` (API returns 409), `cmp_relabel_margins`
    (`locked_skip`), and `cmp_clear_match` — `force=True` overrides
    deliberately. The GG snapshot refresh (`gg_match_detail`) stays allowed:
    it is display detail, not the result. **Manual lock path (v2.125.3):**
    the two played matches GG never carded (Hamilton/Wade s9.17,
    Straiton/Cloer a18.3) lock via `cmp_lock_match_manual` (bridge
    `scoring-mp-lock-one:<chapter>|<A>|<B>[|apply]`), stamping a
    "Kerry-confirmed <date>, no GG card" note — run only on Kerry's
    explicit per-match confirmation. **Identity backfill (v2.125.4):** the
    reconcilers' `no_hole_scores_imported` bucket had been reporting cards
    that WERE imported — `cmp_pool_members` rows with NULL `customer_id`
    broke the id-based round lookup (the "Austin missing 11", all of which
    had cards). Boot backfill `_backfill_customer_id_on_cmp_pool_members`
    links pool members + `cmp_matches` player/winner ids; both reconcilers
    also fall back to a nickname-robust person-key name match
    (`_cmp_round_row_for`); `scoring-mp-pools-audit` lists any
    still-unlinked member rows. Post-fix: 30/30 matches checkable, zero
    uncheckable in both chapters — residual margin deltas are the known
    concession/gimme class plus the two 10H extra-hole matches (hole data
    correctly shows AS through regulation).
  - **Registration / eligibility (front of the lifecycle, for CA).** Signup
    timing + prerequisites. Notably an **established-handicap gate**: a player
    without an established handicap is held out of Match Play until they have
    **X qualifying rounds** (value of X, what qualifies, hard-block vs flag,
    and refund/hold/defer interaction TBD). Also membership/chapter/
    good-standing prerequisites. Gates who may be pooled and seeded.
  - **Participation & communication layer (for CA).** Match Play demands more
    participation, so idle players break the pool/bracket. Needs: per-match/round
    **completion deadlines** (complete-by X) with automated reminders/escalation;
    **DQ boundaries** for non-participation (missed matches / past-deadline / N
    weeks idle) and the walkover/forfeit + standings/bracket handling; **matches
    played outside TGF events** (self-scheduled makeups, event-independent,
    pair-keyed recordation); and automated participant comms driven by match
    state (no manual chasing). Format note: an earlier double-elimination format
    (playback to the championship) produced MORE matches than the current
    pools→knockout — format choice weighs fairness vs match volume vs the
    simplicity/scaling north star.

**Live scoring + one-tap record (SHIPPED 2026-07-18, v2.120–v2.121; Match
Play LIVE app-wide, `MATCHPLAY_V2` default ON, env kill switch preserved).**
The new bracket cards read GG's *current* match state during a round:
`cmp_fetch_live_match(chapter, a, b)` walks the chapter's
`tournament_results` widget (in-mem cached ~25s) → `GET /api/cmp/live-match`
(member/public read). The front end (`contests.html`) live-polls each
in-progress card (both players present, no recorded winner): quick retries
on load then 60s steady, an on-card status line while connecting, and a
localStorage cache so a reload paints the last-known score instantly. The
card renders the FULL match scorecard (hole count from the GG event code —
`s18.8`→18, `a9.16`→9), running net dots from the starting hole in play
order, per-hole points, and a "LIVE · thru N" chip. **One-tap record
(Kerry-ratified):** on a DECISIVE GG final (closeout margin, or `thru ==
n_holes` with a winner — NOT a mid-round lead and NOT all-square-through-18,
which still needs the human extra-holes decision) the manager card pre-fills
the winner + margin and shows a "Record from GG: <winner> <margin>" button
that reuses the existing Save path (records + auto-advances) and stays
editable afterward. The stored `gg_match_detail` snapshot remains the frozen
display source once recorded.

**Close-out walk is match-length-aware (v2.138.1, Kerry 2026-07-22):**
the clinch test in `gg_match_play._close_out_walk` (and the raw-score
derive `_cmp_derive_match`) counts holes remaining **in the match**
(`match_len − play-order position`), never "flags GG has posted so far."
The old flag-count walk clinched one hole early whenever the deciding
hole HALVED and the post-clinch holes were never posted — Youngs v
Jenkins (a9.19, 2&1) was dormie through 7 and decided ON hole 8 by a net
halve (Youngs' stroke), but the stored snapshot said `closed_at_order:
7`, greying the deciding hole on the card. `rederive_close_out(detail,
match_len=None)` recomputes a stored summary in place;
`cmp_fetch_live_match` re-derives with the TGF-code length (`a9.x`→9)
before persisting, and the boot heal `_repair_cmp_detail_close_out`
rewrites any frozen `cmp_bracket`/`cmp_matches` snapshot whose summary
changes (per-hole data and the row's frozen winner/margin untouched).
Regression tests: `test_gg_match_play.py` (halve-clinch + rederive).

**Implementation status (2026-07-17):** config **v2** authored + both
2026 snapshots **pinned** (`cmp_repin_2026_to_dmp_register`, #223);
**D-MP-09 pool rank LIVE** (`cmp_get_standings` honors
`pool_rank_rule='dmp09'`); **D-MP-08 consolation RECORDING live** —
`cmp_record_consolation(season, chapter, loser_a, loser_b, winner_name)`
stores one `cmp_bracket` row (round `consolation`), `POST
/api/cmp/consolation` records/clears it, and `cmp_get_payout_sheet`
awards 3rd (+4th on 4-place ladders) to the consolation winner, falling
back to the combined-place split when unrecorded (the `consolation`
block in the payout return drives the UI). **P1–P4 re-seed code**
(cmp_seed_knockout) is the remaining code adoption — latent for 2026's
cross-pool brackets, required before any 6+-field bracket.

**Live-2026 adoption (#217):** both chapters (SA + Austin) are already
into the knockout; **brackets and played results STAND** — protected
exactly like the handicap retroactivity boundary. The pool-round
recompute under D-MP-09 is accounting-hardening only: if any row moves
it is a **documentation decision, never a bracket/advancer change**.
D-MP-08 applies FORWARD — this season's semifinal losers are the first
consolation matches under the new rule (encode before the semis
complete). Re-pin both 2026 season snapshots to the new config version
after the standings diff reports, on Kerry's go.

**Implementation (the Game Creator engine's first concrete instance):**
- `email_parser/match_play.py` — pure engine (no DB/Flask; Platform-
  portable): `SEED_MATCH_PLAY_CONFIG`, `structure_for_n`,
  `allocate_cents`/`split_cents`, `seed_order`/`seed_bracket` (byes),
  `ladder_payout_rows`.
- Tables: `season_contest_templates` + `season_contest_versions`
  (append-only config_json versions, payout_templates pattern) +
  `season_contest_config_snapshots` (season+chapter pinned to a version
  on first structural action → seasons in flight are frozen; admin can
  re-pin). Boot seed `_seed_match_play_template` creates v1.
  `cmp_bracket` gains `player_seed`/`is_wildcard`.
- DB ops (database.py): `sct_get_active_config`/`sct_list_versions`/
  `sct_get_version`/`sct_save_version` (validates every N before
  accepting)/`sct_ensure_snapshot`/`sct_pin_snapshot`;
  `cmp_enrolled_entrants` (customer_id-deduped, canonical names),
  `cmp_auto_assign_pools` (guards recorded results),
  `cmp_seed_knockout` (advancers+wildcards+seeds+byes, guards recorded
  results), `cmp_get_payout_sheet`.
- API: `/api/cmp/config` (+`/versions`, `/versions/<id>`, `/snapshot`),
  `/api/cmp/structure` (?n= | full matrix | ?version_id= preview),
  `/api/cmp/pools/auto-assign`, `/api/cmp/bracket/seed`,
  `/api/cmp/payouts`. Reads = view-only, actions = manager, config
  writes/pins = admin.
- UI (contests.html → Match Play): structure banner (N → matrix chips,
  config-version badge w/ pinned state, Auto-Assign + Config buttons),
  server-side Seed Knockout w/ seed/WC chips + Round-of-16 + bye
  rendering, Payouts view (bonus + ladder tables, provisional/final/TBD
  statuses), admin Config editor modal (version history, JSON edit,
  computed-matrix preview via ?version_id, save-as-new-version,
  pin-season-to-version).
- **Admin SETUP sub-tab (v2.138.0, Kerry 2026-07-22):** in the v2
  (MATCHPLAY_V2) view the pill row is POOLS | KNOCKOUT | PAYOUTS |
  SETUP, with SETUP an admin-only orange pill. All structural controls
  — + Add Pool, Auto-Assign Pools, Seed Knockout, Clear Bracket, Config
  editor — live ONLY on that panel (`#mp-panel-setup`, static buttons
  keeping their historical ids so the one-time wiring near
  `cmpAddPool`/`cmpSeedBracket` is unchanged). The header card is
  informational-only and the Knockout panel has no bracket-controls
  row. These controls are now **admin-only** (previously
  manager-visible) per Kerry's call — the whole `.mp-setup` wrapper is
  `.admin-only`-gated, and `#tab=mp&mp=setup` deep links show
  non-admins an empty panel (server-side role checks unchanged). The
  legacy non-v2 view keeps the old button placement.

Open-questions thread (mailbox topic **match-play-implementation**, id
21) is now **CLOSED** — every item ratified in the D-MP register above:
N=4/5 ladder (D-MP-01/xlsx), tie-split (D-MP-08), wildcard rule
(D-MP-04/06 + P1 chain), bye scope (P2), random vs handicap-snake pool
assignment (D-MP-03 default = random), pools-of-5 scheduling (D-MP-09).
The encode work (D-MP-08 consolation entity, D-MP-09 counting + rank
chain, P1–P4 placement) lands in `match_play.py` + a new config version;
`cmp_seed_knockout` is being reconciled against P1–P3.

## Season-total rule: Best 10 + City Championship (RATIFIED, Kerry 2026-07-09, mailbox #65)

AUTHORITATIVE SPEC (mailbox #71, Kerry-confirmed 2026-07-09):
- **Best 10 + City Championship applies to BOTH race types**: the NET
  races (San Antonio NET, Austin NET — and therefore THE FELLOWSHIP
  CUP, which shares the NET points) AND THE PLAYERS CUP (gross).
- "Best 10" = a player's ten highest event point totals from
  regular-season events carrying a POINTS game in that race. Points
  per event = Stableford score in that race's POINTS game, floored at
  zero (net for NET races, gross for the Players Cup).
- The **City Championship always adds on top** of the best-10 at face
  value — it never competes for a best-10 slot. No multiplier or
  special weighting on championship events.
- **Exception: MONTHLY races count everything earned in the month** —
  no best-10 cap.
- **Monthly calendar (Kerry-RATIFIED, mailbox #95, 2026-07-10):** the
  Monthly Points Race runs **March through October with NO race in
  August** (Championship month — few events scheduled, top players
  already rewarded). Member copy states "Runs March through October
  (no race in August)".
- Computation lives on the Golf Genius side today; the Tracker ingests
  GG season totals and may mark counted (top 10 + championship) vs
  not-counted events in drill-downs.

**Four-step championship structure (ratified, #71):**
1. Regular Season — standings = best-10 counting events.
2. City Championship — required addition at face value on top of best-10.
3. Points Reset — conversion onto the master ladder per the #64 formula
   (position p → 100 − 0.5×(p−1); race rank r → master ROUND(1+coef×(r−1));
   NET races prorated by anchor-chapter coefficient; Players Cup coef=1,
   flights dismissed; ties share the higher value). Implemented in
   `get_points_race_standings`.
4. TGF Championship — championship round points at face value added to
   reset totals; final standings decide THE FELLOWSHIP CUP (net) and
   THE PLAYERS CUP (gross).
The championship-phase UI (design view 1b) is HELD per Kerry's #65
ruling — functionality first; do not build until cleared.

## How It Works popups (v2.65.0 — handoff hiw-popup-final-071026, Kerry-RATIFIED per view, mailbox #95)

The CONTESTS page popups are the member-facing rules explainer of
record. One data-driven modal in `templates/contests.html` (`HIW`
object inside the popup IIFE) renders six views: **City NET** (generic
— shared by SA + Austin), **The Fellowship Cup**, **The Players Cup**,
**City Match Play**, **Monthly Points Race**, **Fall Points Race**.
Structure per view: orange game-name title → chip row → THE RACE / THE
MONEY / THE POINTS scan blocks (Match Play: THE FORMAT / THE MONEY /
THE SEEDING) → ratified per-hole chart (net REG|CHAMP; gross REG-only,
aces-only championship bonus in the footnote per ruling R4; none on
Match Play) → worked example scorecard (ruling R3; net races stack
GROSS over NET with stroke dots, Players Cup GROSS-only, none on Match
Play) → muted footnote → Got it. Phones get a bottom-sheet presentation
(handoff view 1g). The modal is hoisted to `<body>` at boot so it
renders over the Match Play tab too. Copy is verbatim from the ratified
file (banked by platform-claude as TGF_HIW_Popup_Copy_v1_1) — edit only
with Kerry's ratification. Chip shorthand ratified: PLYR, CHAMP
acceptable on chips to save real estate (#95 items 1/3).

**Nomenclature (Kerry-RATIFIED, mailbox #90 + "rename everywhere"
2026-07-10): POT, not PURSE, on every surface** — member contest pages
(standings pill, Monthly column header, pay-notes, popups, roster
lines) AND admin pages (TGF Payouts / Events financial "Total Pot").
Internal field names (`total_purse`, `sel.purse`, …) unchanged.

## The Lone Star Cup — member section + projection engine (v2.66.0; spec mailbox #85–#88, Kerry-RATIFIED 2026-07-10)

Third top-level member tab (POINTS RACES | MATCH PLAY | LONE STAR CUP,
hash `#tab=lsc`). `get_lone_star_cup_projection()` in `database.py`
computes per-chapter projected 12-seat rosters live from current
standings; `GET /api/season-contests/lone-star-cup` (member tier)
serves it; renderer `lscLoad()` in `templates/contests.html`.

**Roster (12/chapter):** 1 Captain = City NET Champion · 6 = The
Fellowship Cup final standings (top 6 from the chapter, TGF-wide list)
· 1 = City Match Play Champion · 4 = The Players Cup final standings
(top 4 from the chapter, overall list — flights don't gate seats).

**Rules encoded:** enrolled-only; double-qualifiers keep the seat where
they placed HIGHER by absolute place (#86 INTERIM — Kerry's
"proportional valuation" edge-case tweak is NOT ratified; must be
settled before selection day); vacancies fill from the unified
per-chapter alternates pool ranked by percentile finish (place ÷ field
size), tiebreak events played (#87); MP decline cascade winner →
runner-up → pool, one level deep (#88 — declines only, never fires in
a projection); MP seat = bracket final winner else TO BE DECIDED
(Kerry 2026-07-10, no seeding speculation). Cross-contest place ties
break by seat order Captain → Fellowship → Match Play → Players.

**NOT BUILT YET (required before selection day, post-Championships):**
the admin actual-roster surface with manual adds/overrides at every
level — #87 HARD REQUIREMENT ("system proposes, Kerry approves and
fills"; guests/past members per the 6-level invitation hierarchy live
outside standings). Member page shows projections only.

Test: scratchpad `test_lsc.py` — synthetic 22-player fixture proving
captain precedence, no double-seating, pool fill, alternates order,
small-field exhaustion. Note: synthetic season_contests rows must set
`manually_enrolled=1` or boot cleanup removes them (no backing
purchases).

## D-MP-08 consolation: change + clear (v2.170.0, Kerry 2026-07-31)

Robert recorded the Austin 3rd-place result and could not undo it. The
backend never lacked the capability — `cmp_record_consolation(...,
winner_name=None)` has always meant CLEAR, and `POST /api/cmp/consolation`
with an empty `winner_name` reaches it. The gap was purely in
`templates/contests.html`, which gated the manager control on
`!(cons && cons.recorded)`, so the select and button vanished the moment a
winner existed.

The block now renders the control whenever the manager is viewing and both
semifinal losers are known, with the recorded winner pre-selected,
"Update 3rd place", and a red **Clear** button (confirm-gated). Clearing
writes a NULL winner and KEEPS the bracket row, so the pairing stays on the
bracket and the payout sheet falls back to the even split.

**Semantics worth restating**, because "winner takes all" vs "split" reads
like a config choice and is not:
- A RECORDED winner takes the whole 3rd-place amount. On the 8-10 ladder
  (`[50, 30, 20]`) 4th pays nothing, so the loser gets nothing; on the 11+
  ladder (`[50, 25, 15, 10]`) the match decides 3rd vs 4th and both are paid.
- The even split (`tie_policy: split_combined_places`) is the FALLBACK for
  an unplayable match, not an alternative policy to toggle.
- The ladder total is invariant across both — the match moves money only.

Tests: `test_cmp_consolation_undo.py`.

### The 3rd-place match runs LIVE (v2.171.0, Kerry 2026-07-31)

*"Both the 1st place and 3rd place match will be going at the same time."*
It would not have. `mpStartBracketLive` polls only
`.mp-match-card[data-live-a]`, and the consolation block rendered two bare
`mpBracketSlot` pills inside a plain `.bracket-match` div — no card, no
`data-live-*`, so the poller could not see it. The Final would have run
live beside a dead 3rd-place block.

It now renders through `mpMatchCardFromSlots(..., 'consolation', ...)`,
the same builder every other match uses, so it inherits the live
attributes and joins the 60s poll with no extra plumbing.

- `ROUND_DEFS.consolation = { label: "3rd Place", matchCount: 1 }`.
- `cmp_fetch_live_match(chapter, a, b)` resolves a match by CHAPTER + the
  two player names, so the consolation needs no `event_id` — which is
  fortunate, because `cmp_record_consolation` does not write one.
- Event name / date / course in the card header are inherited from the
  FINAL bracket row (`slotMap['final:0']`), since the consolation is
  played at the same event. Those only drive the header text and the
  "Connecting to live scoring…" note; the GG lookup does not use them.
- **GG auto-fill is deliberately out of reach.** `mpMaybeOfferRecord`
  requires a `.bracket-save-btn` inside `card.closest('.bracket-match')`;
  the consolation control uses `.cmp-cons-save`, so the function early-
  returns. A manager records the 3rd-place result deliberately.

Known gap: the consolation has no event selector of its own, so if it is
ever played at a DIFFERENT event than the final, the header date will be
wrong (the live lookup still works). Adding `event_id` to
`cmp_record_consolation` + a dropdown is the follow-up.
