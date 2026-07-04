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

Multi-round days (v2.28.0): Hill Country Matches is its own league
(tgf-hcm2026.golfgenius.com, league 537708) with SIX rounds all dated
the same Saturday (Matches 1-3, Shootout, Non-Matches 1-2). The
importer takes a `round_key` (the GG league round id; bridge syntax
`scoring-import:<event_code>@<round_key>`) stored as
scoring_rounds.gg_league_round_id — the cross-tournament dedupe scopes
to it, so same-day rounds don't collapse while ALL Net/ALL Gross of the
SAME round still dedupe. NULL round_key keeps one-round behavior.

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

## Plus handicaps (v2.26.0)

GG renders plus playing handicaps as "(+1)". Parsed to a NEGATIVE
playing_handicap so arithmetic stays uniform (net = gross − ph; Texas
Terry gross 36 → net 37 with ph −1). UI displays "+1" (prFmtHcp). The
give-back stroke gets NO dot on GG's card, so the importer derives it:
strokes_received = −1 on the |ph| easiest holes played (highest stroke
index — WHS allocation), and verification re-checks the result against
GG's own net markings. Derivations handle negatives naturally: net
double bogey cap = par + 2 + strokes_received (par+1 on give-back
holes). Found when the 3-week backfill flagged 6 cards, all scratch-or-
better players. Round selection for backfills: the Event Results widget
`?shared=false&round=<round_id>` (selector `select[name=round]`; note
unreleased rounds are absent from the selector and cannot be imported
until the admin releases results in GG).

## Empty cards (v2.26.1)

A card with no strokes on any hole is a tee-sheet artifact (no-show/WD
left on the sheet — GG publishes it with sums of 0 and it fails the net
math check), not a scoring record. The importer skips them
(`skipped_empty_cards`); `_cleanup_empty_scoring_rounds` (boot) deletes
any stored earlier, resets their handicap bridges, and completes their
discrepancy action items.

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

## UI (v2.24.0, reworked v2.25.0)

Contests → Points Races → expand a player: points lines that have an
imported scorecard are themselves clickable (chevron on the EVENT cell)
and expand the hole-by-hole card in place — matched by event name, then
event-code prefix, then (for code-less league lines like Hill Country
Matches) base-name prefix + qualifier-vs-course matching; Front/Back
suffixes stripped. Rounds NOT represented by a points line fall back to
a SCORECARDS WITHOUT A POINTS LINE list below — that includes rounds GG
never awarded race points for (e.g. s9.12/s9.5/s18.1/s18.2 as of
2026-07-04: verified absent from GG's own member cards) and guest
rounds. Server-side, substitute_gg_tournament_names swaps GG labels for
tracker event names by code, handling compound codes with letter
suffixes (hcmR1nm -> hcmr1 override fallback). Grid rows: PAR / YARDS / HCP
(stroke index — relabeled per admin; 1 = hardest, decides where
handicap dots land) / SCORE (● dots + GG's net-relative circle/square
markings) / NET PTS / GROSS PTS (per-hole stableford through the admin
formula settings; totals show 0/negative correctly), plus a stableford
+ adjusted-gross summary line. Data: `/api/scoring/rounds?customer_id=`
+ `/api/scoring/scorecard/<id>`; rows carry data-cid so any resolved
player expands even without a GG member card. Rendering fns:
prRenderDetailTables (matching) / prRenderScoreRounds /
prBindScorecardToggles / prRenderScorecard in templates/contests.html.

Card layout (v2.28.x): GROSS and NET sections each open with a thick
border — bold score row (vs-par circle/square marks computed from
tracker facts: gross row from `vs_par`, net row from `net_vs_par`) over
a grey points band; handicap stroke dots (● received / ○ given back)
sit on the NET row only, absolutely pinned to the cell corner so they
never displace the number. Phones (prIsCompact(): media query max-width
640px OR physical screen ≤ 640 — the latter catches desktop-site mode)
compact ALL THREE drill-down levels: standings, round-by-round points
tables, and the scorecard (tight cells, short labels, abbreviated
chapters). Compact enrollment tables use table-layout:fixed so declared
column widths are binding — an expanded scorecard pans inside its own
row instead of stretching the parent tables.
The member portal shares this via `static/js/scorecard-render.js` —
keep it in sync with prRenderScorecard until unified.

**iOS font-boosting gotcha (v2.28.6):** Safari inflates text on any
page whose content is wider than the screen ("font boosting"), and the
Contests page's wide fixed-width standings tables trigger it — text
grew on player expand and the scorecard showed ~1 hole. Fix: pin
`html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }`
(contests.html + me.html) and cap the scorecard scroll container at
`max-width: calc(100vw - 2rem)` so it pans inside its own box. Any new
page with wide tables intended for phone viewing needs the same pin.

## Event MVPs (v2.29.0)

`event_mvps` records each event's "MVP $" and "TGF MVP $" game winners
(one MVP per city per event, tiebreaker resolved; TGF MVP can be
shared). Winner detection = purse>0 rows on the GG tournament table
(that's where GG records the tiebreaker outcome); an MVP table with no
purse falls back to the outright Pos 1 row, and unresolved T1 ties
record nothing. `import_gg_event_mvps(widget_url)` walks a portal's
Event Results rounds (mvp_import_rounds tracks progress; time-budgeted
— call until rounds_left==0); bridge command `scoring-mvp-import` with
url = the tournament_results widget. `/api/scoring/rounds` rows carry
`mvp` / `tgf_mvp` flags (EXISTS on event_id+customer_id); the Contests
drill-down renders amber MVP / teal TGF MVP pills after the event name.
event_mvps is in _CUSTOMER_FK_COLUMNS (merge-safe).

## Monthly points races (v2.30.0)

Contests -> Points Races -> MONTHLY: month nav bar over combined-chapter
standings pulled live from each portal's "<MONTH> Points" pages
(discovered from the portal page menu; season_points_v2 widget via
fetch_season_points_race). ALL points in the month count (no best-10).
get_monthly_points() (database.py) merges chapters — cross-chapter
players keep their higher portal total, never the sum — recomputes
ranks, and computes the award: $1 x active TGF members at month close
(customer_memberships started_at/expires_at spanning the month-end
date), split across tied winners. Route
/api/season-contests/monthly-points (manager; 10-min cache; ?force=1).
Winner rows highlight gold with a trophy on completed months.
Rows expand (v2.30.2) to the standard points-detail table: the row's
member_card_id + chapter pick the season race (Austin -> austin_net,
else san_antonio_net), prRenderDetailTables runs with
{monthFilter: "YYYY-MM", plain: true} — plain skips the counted /
not-counted banners and CITY row (no best-10 monthly), monthFilter
keeps only rows whose GG date cell starts with that month. Imported
rounds without a points line render below as OTHER ROUNDS THIS MONTH.

## Phase 2 — differential parity (v2.27.0, step 1 live)

`get_differential_parity()` (MCP: get_differential_parity_tool; bridge:
scoring-parity) recomputes each bridged handicap round's adjusted gross
(WHS net double bogey via the formula layer) and differential
(113/slope x (adj − rating), PCC 0) from OUR facts and compares to the
values imported from GG's handicap export. 9-hole rounds only for now —
an 18-hole scoring round bridges TWO 9-hole differentials (front/back
split is the next pass). Tee rows whose slope/rating disagree with the
handicap row are counted as tee_data_mismatches. When parity holds,
step 2: compute_handicap_index reads scoring_rounds directly,
handicap_rounds becomes a view, and the manual export/import ritual
dies.

## Phase 2 (queued)

Differential reconciliation (scorecards → differentials vs imported
handicap_rounds; then compute_handicap_index reads scoring_rounds and the
export/import ritual dies), points-detail persistence, per-player stats
surfaces (par-3/4/5 splits, stroke-index performance, trends), historical
portals 2016–2025, admin formula-editing UI.
