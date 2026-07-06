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
- **Stage 1 — NEXT: parallel shadow leaderboard.** Rely on GG for ONLY
  the raw gross hole scores; compute EVERYTHING ourselves (all games,
  all races) from those. Stand a live leaderboard next to GG's at a real
  event and diff, game-by-game and race-by-race, until we reproduce GG
  exactly. GG stays official; we shadow. This is the confidence gate.
- **Stage 2 — FINAL: own score entry.** Customers enter raw gross hole
  scores directly in our app (mobile, offline queue, magic-link auth we
  already have from the member portal). Our engine computes the rest; GG
  leaves the loop entirely. Concurrent writes + realtime => Supabase (the
  scoped Platform stack; see member-portal.md).

Everything upstream of "raw gross hole scores" is already ours — so the
only genuinely new build for Stage 1 is the leaderboard surface + the
diff harness. Stage 2 adds the score-entry UI + write path.

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
  12-field plays inside a 16 template (missing seeds = byes)
- POOL WINNER BONUS: $20/pool winner ($25 at N=4), off the pot first
- LADDERS (% of adjusted pot): 4→71.5/28.5 (=$97/$38) | 5→66.67/33.33
  (=$120/$60) | 6→62.5/22.5/15 | 7→55/25/20 | 8-10→50/30/20 |
  11+→50/25/15/10. (The xlsx supersedes the earlier "4-5→75/25" note.)
  Pot = $40×N. Largest-remainder cents allocation → payouts always sum
  exactly. Ties split combined places (SF losers split 3rd+4th);
  default pending Kerry confirm, posted as mailbox id 21 Q2.

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

Open questions to Kerry live in mailbox topic
**match-play-implementation** (id 21): N=4/5 ladder per xlsx, tie-split
default, wildcard rule, bye scope, random vs handicap-snake pool
assignment, pools-of-5 scheduling. Defaults are implemented; answers
only require a config edit or small rule tweak.
