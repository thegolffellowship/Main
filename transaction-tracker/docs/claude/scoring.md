# Scoring Records & Course Database (Phase 1, v2.23.0)

Tracker-owned scorecards extracted from Golf Genius. Design principles
(admin-established 2026-07-04):

- **Facts vs derivations**: `scoring_holes` → `scoring_rounds` store only
  FACTS (strokes, strokes received per hole via GG's handicap dots, tee,
  GG's own gross/net/result markings). Everything computable — adjusted
  gross (WHS net double bogey = par + 2 + strokes received, PER PLAYER),
  stableford points (model-dependent), vs-par — is DERIVED at read time
  through `get_scoring_formulas()` so the admin can retune formulas or
  toggle to USGA standards later without touching stored data. Defaults in
  `_SCORING_FORMULA_DEFAULTS`; overrides live in handicap_settings keys
  (stableford_net_table / stableford_gross_table / adjusted_gross_method).
- **Own the data / GG unplug path**: every parsed GG response is archived
  gzipped in `gg_raw_archive` (re-parseable even if GG severs access).
  Normalized tables are the record; GG is an input.
- **Parent/child with handicaps**: a differential is derived from a
  scoring round. `handicap_rounds` is the legacy derived layer — it gains
  `scoring_round_id` (bridged on import by customer+date) and collapses to
  a view once differential parity is proven (Phase 2). Goal: kill the
  handicap export/import ritual.
- **Course DB enriches the CANONICAL courses table** (courses /
  course_aliases / events.course_id already existed and feed the Events
  tab datalist — do NOT create a parallel table). Scorecard imports
  resolve GG course names via courses.name then course_aliases, and
  accrete `course_tees` (slope/rating/yardage) + `course_tee_holes`
  (par/yardage/stroke index per hole).

## GG extraction surface

- Tournament page `/v2tournaments/<id>` → aggregate ids via
  `/tournaments2/details/(\d+)` links.
- `GET /tournaments2/details/<agg>` (XHR) → JS partial with net-line rows:
  hole strokes (`score_box`), handicap dots (● count = strokes received),
  par-relative classes (simple/double circle/square — these are
  **NET-relative**, verified live: 2 strokes on a par 3 with a dot renders
  double_circle), playing handicap `(N)` in the expand-tee link,
  sum_front/sum_back/sum/net_sum, /profiles/<gg_profile_id>.
- `GET /tournaments2/nets/<net_id>?event_id=` (XHR) → tee block: course,
  tee, slope, rating, yardage/par/stroke-index rows.
- Parsers + walker in `golf_genius_sync.py`: `_unwrap_js_string`,
  `parse_scorecard_details`, `parse_tee_block`,
  `fetch_tournament_scorecards`.

## One round, many GG tournaments (IMPORTANT for imports)

A single physical round shows up under EVERY GG game that day —
Individual Net, ALL Gross, Skins, MVP, Match Play — each with a
DIFFERENT tournaments2/details aggregate id. The importer therefore
dedupes by identity + round: on a fresh aggregate id it first checks
for an existing scoring_rounds row for the same (customer_id or
player_name) and (round_date or event_id) and SKIPS if found
(`skipped_other_tournament` in the result). Re-importing the same
tournament still replaces (refresh path).

Ordering rule (admin-corrected): **ALL Net and ALL Gross are the gold
standard** — both carry the FULL field. ALL Net has everyone's playing
handicaps + strokes-received dots (Individual Net is a PURCHASED game
under NET Games and only covers buyers — importing it first was the
original mistake that left 11 of 32 s9.16 players without handicaps).
ALL Gross is the raw-score baseline — the layer our own calculations
build on to reverse-engineer GG's derivations and validate in parallel.
Recipe per event: ALL Net first, then ALL Gross to fill anyone left.
Order mistakes self-heal: a net-game card (playing_handicap present)
UPGRADES a stored raw-gross card for the same physical round
(`upgraded_with_handicap` in the result), never the reverse. The
round-N tournament list lives at
`/leagues/<league_id>/widgets/tournament_results?shared=false`
(iframe inside the Event Results portal page).

## Import & identity

`import_gg_scorecards(tournament_url, event_code)` (database.py): walks
the tournament, resolves each GG name via `handicap_player_links` first
(curated GG-name map) then `_gg_name_candidates`+`_lookup_customer_id`;
unresolved rows import with NULL cid (counted in the result). Event
linkage by code prefix → events.item_name (event_id + round_date).
Idempotent on (gg_aggregate_id, player_name). `scoring_rounds.customer_id`
is in `_CUSTOMER_FK_COLUMNS`.

## Verification (parallel-run with GG)

`verify_scoring_round(id)`: hole sums vs GG gross; net = gross − playing
handicap; GG's net-relative circle/square markings vs our course par +
dots. Runs AUTOMATICALLY on every import (v2.23.1); discrepancies file
COO action items (category 'scoring', deduped while open) so mismatches
hit the admin review queue. Import results carry verified_ok +
discrepancies.

## Endpoints & MCP tools (55 total)

- POST /api/scoring/import (admin), GET /api/scoring/rounds,
  GET /api/scoring/scorecard/<id>, GET /api/courses/tees (manager).
- MCP: import_gg_scorecards, get_scoring_rounds, get_scorecard_detail,
  verify_scoring_round_tool, get_courses.
- TEMPORARY bridge (v2.23.3): MCP client sessions freeze their tool
  inventory at session start, so sessions opened before v2.23.0 never see
  the five scoring tools. probe_golf_genius (present in every session)
  dispatches extract values scoring-import:<event_code> (url = tournament
  URL), scoring-rounds:<event>, scoring-verify:<round_id>,
  scoring-card:<round_id>, scoring-courses to the same functions
  (_scoring_dispatch in mcp_server.py). Remove once stale sessions age out.

## UI (v2.24.0)

Contests → Points Races → expand a player: below the GG points
breakdown, a SCORECARDS section lists that customer's imported rounds
(`/api/scoring/rounds?customer_id=`); clicking a round lazy-loads
`/api/scoring/scorecard/<id>` and renders the hole-by-hole card
(PAR/YARDS/S.I. from course_tee_holes, scores with ● strokes-received
dots and GG's net-relative circle/square markings, OUT/IN totals,
stableford + adjusted-gross summary line). Rows carry data-cid so any
resolved player expands even without a GG member card. Rendering fns:
prRenderScoreRounds / prBindScorecardToggles / prRenderScorecard in
templates/contests.html.

## Phase 2 (queued)

Differential reconciliation (scorecards → differentials vs imported
handicap_rounds; then compute_handicap_index reads scoring_rounds and the
export/import ritual dies), points-detail persistence, per-player stats
surfaces (par-3/4/5 splits, stroke-index performance, trends), historical
portals 2016–2025, admin formula-editing UI.
