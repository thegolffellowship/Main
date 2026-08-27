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

**Completeness upgrade (v2.109.0) — the mid-round self-heal.** GG re-keys
a tournament's aggregate ids when the round FINALIZES, so a card first
grabbed mid-round (partial holes, imported while entry was still in
progress) can't be refreshed by a plain re-import: the finished card
arrives under a NEW aggregate id and the cross-tournament dedupe skips it
as "other tournament", freezing the partial card. Fix: the upgrade rule
now also fires on completeness — an incoming card whose `holes_played`
exceeds the stored row's replaces it in place (counted as
`upgraded_with_handicap`). So re-importing any event first captured
mid-round pulls the complete scores. (a9.18 Forest Creek, 2026-07-14:
imported ~23:00 with 4-7 of 9 holes; the finished import self-heals to 9.)
The fewer-holes direction never clobbers a more-complete stored card.

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

**Future-event guard (v2.256.0).** GG's own round numbering can collide
with a STORE code: the 2026 SA CHAMPIONSHIP's GG round was coded
`s18.10` (SA's 10th 18-holer), which matched the store's `s18.10 FALL
KICKOFF | Landa Park` — 64 Quarry cards, the GG game winners, and the
MVP marker all attached to the unplayed 8/29 event while the
championship sat with zero rounds (boot repair
`_repair_fall_kickoff_champ_mislink` moved them home). Since results
can never belong to an event that hasn't been played,
`import_gg_scorecards` now refuses an `event_code` that resolves to an
event with a FUTURE `event_date` (an explicit `round_date` is the
deliberate override, e.g. a multi-day championship's R2), and the
round→event code maps in `import_gg_game_results`,
`import_gg_event_mvps`, and `import_gg_game_flights` skip a code that
resolves to an unplayed event (the game-results pass records the
refusal in its `notes`).

Archive imports (v2.74.0, GG-history Phase B): two extra params —
`round_date` (explicit date when no Tracker events row exists; without
it the cross-tournament dedupe can't scope and ALL Net + ALL Gross
would double-import) and `source` (scoring_rounds.source tag,
`'gg_history:<subdomain>'`; live sync stays `'gg'`). The Phase-B walker
`ingest_portal_holes` in email_parser/gg_history.py drives this — see
docs/claude/gg-history.md.

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
url = the tournament_results widget.

**Live GG portals** (the Event Results page carries the round dropdown;
its iframe is the `tournament_results` widget):
- San Antonio — `https://tgf-sa.golfgenius.com`
- Austin — `https://tgf-austin.golfgenius.com`
Archive/history portals (past seasons) are cataloged in `gg-history.md`.

### Self-computed MVP badges (Kerry-ratified 2026-07-16) — the source of truth
The scorecard badge no longer depends on the GG "MVP $" import (which
lags — it must be manually re-walked, so recent events showed no badge
for weeks). We OWN the determination from our scorecards + formula layer:

- **Rule:** City MVP = whoever scored the **most points in the event's MVP
  side game** (net Stableford among the game's players). Ties break
  **1) Net score, 2) Gross score**; still tied ⇒ **split → Co-MVP**. TGF
  MVP = the City MVP with the most points across the day's linked events;
  a tie ⇒ **Co-TGF MVP**. (This is exactly what `determine_tgf_mvp`
  already computed — we just materialize it for the badge.)
- **Storage:** `event_mvp_computed(event_id, customer_id, kind
  ['mvp'|'tgf_mvp'], split, player_name, points)` — `split=1` means a Co-
  winner. In `_CUSTOMER_FK_COLUMNS` intent (customer_id FK per rule 6).
- **Populate:** `recompute_computed_mvps(scope_event=None)` clears+rewrites
  a day's rows from `determine_tgf_mvp`. Auto-runs after every
  `import_gg_scorecards` for that event's day (badge appears as soon as
  scores land), a one-time daemon backfill on boot when the table is empty,
  and the bridge `scoring-mvp-recompute[:event]` for a manual run.
- **Badge read + RETROACTIVITY BOUNDARY:** `get_scoring_rounds_list` emits
  mvp/co_mvp/tgf_mvp/co_tgf_mvp. Our computation is authoritative for events
  **on/after the ratified boundary `_MVP_RETRO_BOUNDARY = "2026-07-14"`**
  (a9.18 forward — a9.18 is the first event the cap affects, `>=`). Before the
  boundary GG is bible (Kerry standing rule):
  where GG recorded an MVP (`event_mvps`) we defer to it — our post-cap
  handicaps must not re-crown a frozen result (e.g. s18.6 Flying L, where our
  net points make Sanford City MVP but GG's tiebreaker MVP is Jeff Young) —
  and our computation only fills events GG never recorded (import lag: a9.18
  Kelly, s9.17 Jeff). `points-render.js` `prMvpBadges` renders amber
  **MVP**/**Co-MVP** + teal **TGF MVP**/**Co-TGF MVP**. GG `event_mvps` stays
  the money/purse record + pre-boundary authority.
- **GG split → Co-MVP (Kerry 2026-07-16):** when GG recorded MORE THAN ONE
  MVP winner for a pre-boundary event, it PAID THE POT IN SHARES rather than
  applying a tiebreaker (e.g. s18.6 Flying L: Young/Sanford/Fehlis $33.33
  each). The badge honors that — every GG winner shows **Co-MVP**, not sole
  MVP (winner count from `event_mvps`). This split is an OUTLIER to our
  Net→Gross tiebreaker; **FUTURE: only an admin override may force a split
  over our computed sole winner** (post-a9.18 our engine tiebreaks to a sole
  MVP by default). Same rule for a multi-winner GG TGF MVP → Co-TGF MVP.
- **TGF MVP multi-chapter gate (Kerry ruling B):** TGF MVP only exists when
  ≥2 chapters fielded the game that day; a lone City MVP on a single-chapter
  day (other event rained out / no players) is NOT elevated (matches GG).

event_mvps is in _CUSTOMER_FK_COLUMNS (merge-safe).

## Shared drill-down renderers (v2.31.0)

The Points Races drill-down renderers — prRenderDetailTables,
prRenderScoreRounds, prRenderScorecard, prBindScorecardToggles, and
their helpers (prIsCompact, prFmtAwardDate, prMvpBadges, prBadgeLayout,
prPrettyEvent, prNineSuffix, prFmtHcp) — live in
`static/js/points-render.js` (moved out of contests.html), exported on
window and consumed by BOTH the Contests page and the Customers Points
tab. The module injects its own .enrollment-table/.pr-wrap/.pr-compact
CSS so host pages don't need the Contests stylesheet. Edit the module,
never re-inline copies. (scorecard-render.js remains the member-portal
twin of prRenderScorecard — keep the two in sync until unified.)

## Points-race scoring model (VERIFIED 2026-07-05)

Race points are NOT a position schedule. For every race:
POINTS(player, event, race) = max(0, Stableford score in that race's
POINTS game) — net Stableford for the NET races, gross Stableford for
THE PLAYERS CUP. Season standing = best 10 + City Championship (BOTH
race types). Monthly races count all points. Verified against live GG
member details: NET via Callaway/Baker full histories + the complete
s9.16 event table (T18/Stableford 1 -> 1 pt; T2/8 -> 8 pts;
same-position-different-points cases kill position tables); GROSS via
Pat Youngs (pos 3 / gross Stableford 13 -> 13 pts; five 1st places
paying 25/23/22/21/19) and floor-at-0 via Mike Murphy (-6 gross
Stableford -> 0 awarded). Consequence for live standings: GG's live
POINTS-game Stableford totals ARE the provisional race points — no
mapping needed, and our formula layer can parallel-verify them.

### Assign Points schedules (admin-ratified 2026-07-06)

Points are computed per hole by (net- or gross-)vs-par through the
formula layer (`_SCORING_FORMULA_DEFAULTS` / `compute_hole_derivations`),
admin-tunable via handicap_settings. **Regular-season** values (match
the GG game setups):

| Result (by vs-par) | NET | GROSS |
|---|---|---|
| Triple Eagle or better (-4) | 4 | 16 |
| Double Eagle (-3) | 4 | 16 |
| Eagle (-2) | 3 | 8 |
| Birdie (-1) | 2 | 4 |
| Par (0) | 1 | 2 |
| Bogey (+1) | 0 | 1 |
| Double Bogey (+2) | -1 | 0 |
| Triple Bogey & worse (+3) | -1 | -1 |
| **Raw hole-in-one bonus** | **8** | **8** |

**Raw hole-in-one rule (both tables):** an actual ace (gross strokes
== 1) is ALSO a hole result, so it awards the HIGHER of the HIO bonus
and its vs-par value — never both. So a **par-3 ace = 8** (its eagle
value equals the HIO bonus), a **par-4 ace = 16 gross** (double eagle
beats the HIO bonus), 8 net. A "net hole-in-one" — a net score of 1
reached through handicap strokes (a gross 2 on a par 3, a gross 3 on a
par 4) — is NOT a raw ace and is scored normally by its vs-par. Only a
literal 1 on the card triggers the HIO bonus. (Implemented as
`max(hio_bonus, table_value)` on `strokes == 1`.)

**NET schedule VALIDATED against GG (2026-07-06):** the admin's GG
setup for the SAN ANTONIO Net points game (category 26-SAn) shows
Assign Points HIO 8 / Triple Eagle-or-Better 4 / Double Eagle 4 /
Eagle 3 / Birdie 2 / Par 1 / Bogey 0 / Double Bogey -1 / Triple Bogey
-1 / Others -1 — an EXACT match to our net table on every category,
including Others = -1 (a direct match to our clamp). One net game
feeds both the season (26-SAn) and monthly (26-Jun) categories from
the same per-event net Stableford. (The MVP $ game uses Others = 0;
our single net table matches the POINTS game and diverges from MVP
only on played quads, unreachable under Max Triple.)

**GROSS schedule VALIDATED against GG (2026-07-06):** the admin's
GG setup screenshot for THE PLAYERS CUP gross points game (category
TPC26reg, Handicap None/Gross) shows Assign Points HIO 8 / Triple
Eagle-or-Better 16 / Double Eagle 16 / Eagle 8 / Birdie 4 / Par 2 /
Bogey 1 / Double Bogey 0 / Triple Bogey -1 / Others 0 — an EXACT match
to our table on every reachable category. GG lists both a Hole-in-One
box (8) and a Triple-Eagle box (16), which together with the admin's
"award the higher" rule confirms the max(HIO, vs-par) implementation.
GG's "Others = 0" is a no-score / worse-than-triple catch-all,
unreachable for played holes under Max Triple (which caps gross at
triple = -1, exactly what our clamp yields); null holes are skipped
(contribute 0). No code change needed.

The gross ladder doubles the birdie/eagle/albatross line (4/8/16).
Codebase history: an earlier gross table read eagle 4 / double eagle 8
(both wrong) and the net -4 bucket read 8 (a stray HIO encoding);
corrected v2.33.1-.3. Ordinary net totals (par/birdie/bogey) are
unchanged, so MVP and net standings for normal scores are unaffected;
only aces, net-triple-eagles, and gross eagle-or-better shift.

**Championship schedule (RATIFIED 2026-07-06 — resolves the earlier
contradiction; ASYMMETRIC):**
- **NET table: +1 on EVERY category**, including the HIO bonus →
  Triple 0 / Double 0 / Bogey 1 / Par 2 / Birdie 3 / Eagle 4 / Double
  Eagle 5 / Triple-Eagle+ 5 / raw-HIO bonus 9.
- **GROSS table: +1 on the raw-HIO bonus ONLY** (8 → 9); the vs-par
  gross values are unchanged (birdie 4 / eagle 8 / double eagle 16).
  Consequence: a championship **par-3 ace = 9 gross** (HIO 9 now beats
  the eagle 8), while a par-4 ace stays 16 (double eagle > 9).

`get_championship_formulas()` builds this from the regular config; the
live-standings engine passes it for championship events (which need an
is-championship flag — future wiring). The net +1 gives championships a
real per-hole weighting on top of the City Championship being an
always-counted event in the best-10+CC standing.

**Season progression (RATIFIED via mailbox id 17, 2026-07-06 — closes
the reset-mechanics open item). NO multiplier anywhere:**
1. **Regular season**: 9-hole Stableford values accrue; season total =
   best 10 added together.
2. **City Championship**: the full 18-hole Stableford total is added at
   FACE VALUE as an additional, REQUIRED amount on top of the Best 10 —
   it can never be dropped or swapped into the best-10 set. Placewinners
   paid; the winner is named **Captain of that chapter's Lone Star Cup
   team**.
3. **Points Reset**: compresses the field ahead of the finals (the
   v2.22.0 reset methodology stands as the mechanism); the reset value
   is each player's starting number.
4. **TGF Championship**: 36-hole/2-day, scored with the championship
   (+1) values; ALL championship points add to the reset number.
   Placewinners paid; X net + gross placewinners fill the remaining
   Lone Star Cup roster spots (exact count per side unspecified).

Engine consequence: the accumulation model has THREE phases — best-X
(regular), required-add (championships, never droppable), and
reset-checkpoint (between City Champ and TGF Champ). The Platform's
season_contest_events.points_multiplier column is confirmed NOT the
mechanism (stays inert at 1.00).

### Cross-chapter points routing (TGF standard — automation requirement, admin 2026-07-06)

Every event can draw members from other chapters. A player earns
season points toward **their HOME chapter's race**, not (only) the
host event's chapter. Example: two Austin members played a San Antonio
event; their net Stableford must feed the AUSTIN Net race (26-An), not
just SAN ANTONIO Net. In GG this is a MANUAL wire-up each time (GG does
not auto-recognize the visitor's home chapter) — the admin had to hand-
attach the Austin division to that event's game.

**Our system must automate this — with NO dependency on the items
table.** The routing key is `customers.chapter`, reached through the
`customer_id` FK that `scoring_rounds` already carries. Points routing
is a clean FK join `scoring_rounds.customer_id -> customers.chapter`;
it NEVER reads `items.chapter` (that field is only a per-order
event-location snapshot and is deliberately excluded from identity and
routing — `customer_id` is the one true key, per CLAUDE.md Guiding
Principle 6). So the engine computes each player's net/gross Stableford
once, then routes by scope:

**Routing rules (RATIFIED admin 2026-07-06):**
- **CITY NET (season Net race) = HOME-chapter only.** A member can be
  in exactly ONE city Net race (their home chapter) — this may change
  in future, but today a visitor's Net points go ONLY to their home
  Net race, never the host chapter's. (This is why the SA event's net
  game had AUSTIN Net wired in — to send the two Austin visitors' Net
  points home.) The engine routes Net by `customers.chapter`.
- **THE PLAYERS CUP (gross season race) = TGF-WIDE.** One gross race
  across all of TGF; every player's gross points count regardless of
  chapter. No per-chapter routing — everyone feeds the single race.
- **MONTHLY races = TGF-WIDE.** See below — all members auto-entered,
  everyone's points count toward the single TGF-wide monthly race.

### These are TGF standards, not GG's (framing, admin 2026-07-06)

The point values, game rules, flight bands, and matrix are **TGF
standards the admin authored** — GG is a general, highly-configurable
game engine that happens to be the current entry surface. GG does not
"lock" a game's definition for subsequent events (its Tournament
Library templates only some of it, not enough). The automation goal:
the Tracker/Platform persists every game as an admin-editable,
VERSIONED definition (payout_templates pattern) that applies to every
future event by default and auto-adapts (player counts, flights,
cross-chapter routing) — so a manager never re-enters or re-wires a
game. The game definitions captured in side-games.md ARE that lock;
GG cross-checks confirm our encoding matches the admin's current
standard, but the standard is TGF's, not GG's.

## Points-race rank movement (v2.42.0)

The season races (SAN ANTONIO Net / AUSTIN Net / THE PLAYERS CUP)
show a compact GG-style movement chip in the Rank column: green
▲N / red ▼N vs GG's own Previous Rank column (already persisted on
gg_points_standings.prev_rank; "-" previous = no chip, matching GG).
Ties compare on the numeric part ("T11" vs "13" → ▲2). Compact
(phone) tables stack the chip under the rank number so the narrow
column never widens.

Fellowship Cup (v2.43.0): no GG reference exists (our own computed
projection), so `_apply_rank_movement_history()` records the Cup's
ordering in `rank_history_snapshots`/`rank_history_rows` (generic by
list_key; keyed by customer_id, name fallback; keeps last 12
snapshots) and rotates ONLY when the order changes — prev_rank comes
from the superseded snapshot, so chips appear on a standings change
and persist until the next one (GG's between-events semantics).
Monthly races still carry no chip — they can adopt the same
mechanism with their own list_key when wanted.
Backfill (v2.43.1): `seed_fellowship_cup_history()` (bridge
`scoring-fc-seed`) reconstructs the pre-latest-event Cup ordering
from the NET races' GG Previous Rank columns (reset = pure function
of race position via the master ladder; first-round-on-latest-date
players excluded as newcomers), replaces the Cup's history with that
seed, and rotates the current order on top — chips show the last
event's movement without waiting for the next one.

## Monthly points races (v2.30.0)

Contests -> Points Races -> MONTHLY: month nav bar over combined-chapter
standings pulled live from each portal's "<MONTH> Points" pages
(discovered from the portal page menu; season_points_v2 widget via
fetch_season_points_race). ALL points in the month count (no best-10).

**Monthly race rules (RATIFIED admin 2026-07-06):**
- **TGF-WIDE, not per chapter.** One monthly race across all chapters;
  everyone's points count. `get_monthly_points()` already merges the
  chapter portals into one standing (cross-chapter players keep their
  higher portal total, never the sum).
- **All members AUTOMATICALLY entered** — no buy-in, no opt-in; it is
  a membership benefit, funded by the dues.
- **Funding: $1 per month from every membership** → purse = $1 x active
  memberships that month (this is what the code computes at month
  close: customer_memberships started_at/expires_at spanning the
  month-end date), split across tied winners.
- **Active months: March, April, May, June, July, September, October**
  (7 months). NO monthly race in August or the off-season (Nov-Feb).
  Encoded as `_ACTIVE_MONTHLY_MONTHS = {3,4,5,6,7,9,10}` in
  get_monthly_points() (v2.49.0) — it gates the current-month
  synthesizer so the system never invents a phantom August race.

**Current-month synthesizer (v2.49.0, Kerry: "Add JULY"):** the GG
"<MONTH> Points" portal pages are built by hand each month, so early in
a month the MONTHLY tab had nothing to discover. When the current month
(within the active-months rule) has no portal page, `get_monthly_points`
calls `_synthesize_month_points()`: players with a `scoring_rounds` row
in that month are looked up in `gg_points_standings` for their
member_card_id, each one's season-points detail
(`fetch_points_race_member_detail` — same XHR as the drill-down) is
fetched, and points lines dated in-month are summed (rounds = line
count). Best-of-both-portals merge, same as the page path. Only players
who actually played are fetched, keeping GG traffic bounded; the fetch
runs inside the daily 05:30 snapshot job and ?force=1. Once Kerry
builds the GG page for that month, link discovery takes over
automatically.

get_monthly_points() (database.py) merges chapters, recomputes ranks,
and computes the award as above, split across tied winners. Route
/api/season-contests/monthly-points (manager). Served from the
persisted gg_data_snapshots table (v2.30.3) — no GG wait on tab open;
?force=1 (Refresh button) live-refetches and re-persists, and a daily
scheduler job (05:30 Central, id monthly_points_snapshot) bounds
staleness at ~24h; boot queues a bootstrap fetch when no snapshot
exists. Helpers: save_gg_snapshot / load_gg_snapshot /
refresh_monthly_points_snapshot (database.py). load adds fetched_at
(Central, display-ready) to the payload.
Winner rows highlight gold with a trophy on completed months.
Rows expand (v2.30.2) to the standard points-detail table: the row's
member_card_id + chapter pick the season race (Austin -> austin_net,
else san_antonio_net), prRenderDetailTables runs with
{monthFilter: "YYYY-MM", plain: true} — plain skips the counted /
not-counted banners and CITY row (no best-10 monthly), monthFilter
keeps only rows whose GG date cell starts with that month. Imported
rounds without a points line render below as OTHER ROUNDS THIS MONTH.

## Phase 2 — differential parity (v2.27.0, step 1 live; triaged v2.88.0)

`get_differential_parity()` (MCP: get_differential_parity_tool; bridge:
scoring-parity) recomputes each bridged handicap round's adjusted gross
(WHS net double bogey via the formula layer) and differential
(113/slope x (adj − rating), PCC 0) from OUR facts and compares to the
values imported from GG's handicap export. 9-hole rounds only for now —
an 18-hole scoring round bridges TWO 9-hole differentials (front/back
split is the next pass). Tee rows whose slope/rating disagree with the
handicap row are counted as tee_data_mismatches (v2.88.0: plus
tee_mismatch_detail — tee-row hole range vs the nine played, to tell
front/back rating pairs from stale rows). When parity holds, step 2:
compute_handicap_index reads scoring_rounds directly, handicap_rounds
becomes a view, and the manual export/import ritual dies.

**Parity triage (v2.88.0, 2026-07-14 run: 2277 compared, 90.6% exact):**
mismatches are classified in `mismatch_families`. Dominant family
CONFIRMED on real cards — GG's export "adjusted" == RAW gross (no NDB
cap) while ours caps per WHS; a policy difference needing Kerry's
ruling, not a bug. Smaller `gg_below_ours` family = mis-bridges
(Victor Arias Jr/III double-bridge class) / allocation differences —
per-case queue. The read-only preview of the export-free path is
`get_scoring_handicap_preview` (bridge scoring-hcp-preview:<event>) —
see docs/claude/handicaps.md → Self-derived handicap preview.

## Phase 2 (queued)

Differential reconciliation (scorecards → differentials vs imported
handicap_rounds; then compute_handicap_index reads scoring_rounds and the
export/import ritual dies), points-detail persistence, per-player stats
surfaces (par-3/4/5 splits, stroke-index performance, trends), historical
portals 2016–2025, admin formula-editing UI.

## Course DB editor (v2.57.0, Kerry)

`/courses` (admin-only page; COURSES in the admin sub-nav) edits the
`courses` dimension table: **short_name** (what phones display in round
histories — exact-name matches flow through `course_short` on
`/api/handicaps/rounds`, otherwise the JS derivation fallback), chapter
(by name), city, state, status (archived rows dim + hide from the
default view). Course **names stay read-only** — imports and dim
backfills join on them; renames need an alias-aware flow. API:
`GET /api/course-db` (list + chapter names; `list_courses` now returns
short_name/city/state/status/chapter), `PATCH /api/course-db/<id>`
(`update_course`, whitelisted fields). NOTE: `/api/courses` was already
taken by the scoring API — the editor uses `/api/course-db`.

## Course registry v1 (v2.126.0, Kerry-ratified 2026-07-20)

**One course_id per real course per city, forever.** The boot migration
`_migrate_course_registry_v1` (idempotent, explicit live-DB ids like the
attribution repairs) resolved the 26 duplicate clusters from the 7/19
audit: 6 GG "(OLD) - Archived on <date>" version rows merged into their
canonical course, 26 zero-round stubs/misspellings deleted. Every merged
or deleted row's name becomes a `course_aliases` entry on the survivor so
name-based lookups (handicap course names, items/events dim backfills)
keep resolving. Riverside stays separated **by city** (ATX row untouched;
the five zero-data SA spellings collapsed to one).

- **Facilities layer.** `facilities(facility_id, name, city, state,
  address, notes)`; every course row carries `facility_id` — 1:1
  auto-created for single-course properties, prefix-grouped for
  multi-course ones (Cypresswood, Comanche Trace, Hyatt, TPC SA, Bear
  Creek). Property info (address etc.) lives on the facility only.
- **Tee versioning.** `course_tees` gain `version_label` / `valid_from` /
  `valid_to`. Ratings/slopes live per-tee and every historical round pins
  its `tee_id`, so merging an archived course row moves its tees across
  as dated versions and **past rounds keep their frozen period ratings**.
  Archive dates parse from GG's "(OLD) - Archived on <date>" names.
- **27-hole facilities: the NINE is the course row** (Comanche Creeks/
  Hills/Valley, Hyatt's nines). `course_combos(facility_id, name,
  nine1_course_id, nine2_course_id)` + `course_combo_tees` carry the
  OFFICIAL 18-hole ratings for the named combos (A/B, B/C, C/A).
- **Handicap rule (Kerry): PLAY OFF THE 18, POST BY THE 9.** Course
  handicap for an 18-hole event comes from the tee's (or combo's) 18-hole
  rating/slope; differentials always post per nine against each nine's
  own 9-hole data (TGF is a 9-hole-index league — Vaaler two-posting
  precedent). 27-hole facilities by application: single-nine day → that
  nine's data; 18-hole event → the combo's official 18-hole tee data;
  27-hole match-play day (Hill Country Matches) → three separate 9-hole
  matches, each off its nine. Derived from event structure, never asked.
- **Gender** (`_migrate_gender_v1`): `customers.gender`; tees named with
  the (L) marker are `course_tees.is_ladies`; backfill from tees actually
  played (ladies-tee round → F, only other tees → M, no rounds → NULL for
  manual entry). Only NULL genders are filled — manual edits stick.
- **Stale-card repair**: `scoring-import-event:<code>[@<round>]
  |refresh=<A>[,<B>]` force-replaces named players' stored cards from
  GG's current board (deletes round + holes + bridged handicap rows
  first). Exists because GG score corrections made after our import can't
  self-heal — the cross-tournament dedup treats the stored row as owned
  (s18.8 Wilson: GG edited his front nine post-import, 97 → 91).
- Verification reads: `scoring-facilities` (facility census — any
  facility with ≠1 course), `scoring-courses-audit` (should show the
  clusters gone).
