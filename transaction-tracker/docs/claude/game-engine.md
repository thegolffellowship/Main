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
