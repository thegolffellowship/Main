# Handicap System — TGF Rules

All handicap calculations are for **9-hole rounds only**. The differential
lookup counts match WHS Rule 5.2a. Adjustments per that rule are also applied.

## Handicap Differential Table (WHS Rule 5.2a)

| 9-Hole Rounds in Record | Differentials Used | Adjustment |
|------------------------|--------------------|-----------:|
| 1–2 | None (no handicap) | — |
| 3 | Lowest 1 | −2.0 |
| 4 | Lowest 1 | −1.0 |
| 5 | Lowest 1 | 0 |
| 6 | Avg Low 2 | −1.0 |
| 7–8 | Avg Low 2 | 0 |
| 9–11 | Avg Low 3 | 0 |
| 12–14 | Avg Low 4 | 0 |
| 15–16 | Avg Low 5 | 0 |
| 17–18 | Avg Low 6 | 0 |
| 19 | Avg Low 7 | 0 |
| 20 | Avg Low 8 (fully established) | 0 |

Formula: `round((avg_of_lowest_N × 0.96) + adjustment, 1)`

## Calculation rules
- **Lookback window:** 12 months (configurable)
- **Pool:** most recent 20 rounds within the window
- **Multiplier:** avg of lowest N × 0.96
- **Rounding:** standard round-to-nearest-tenth per **WHS Rule 5.2** (2020-present):
  *"The result of the calculation is rounded to the nearest tenth."* (.5 rounds up)
  e.g. 6.282 → 6.3; 6.24 → 6.2; −0.228 → −0.2N (plus-handicapper, rounds toward +∞)
  NOTE: the pre-2020 USGA system used truncation — that rule no longer applies.
- **DIFF precision is tenths.** Every per-round differential is rounded to
  1 decimal at write time in `import_handicap_rounds()` and the boot
  migration `_migrate_round_handicap_diffs_to_tenths` keeps legacy rows
  in sync. The handicap-card DIFF column and the underlying averaged
  values are guaranteed to reconcile — earlier versions stored hundredths
  but displayed tenths, so the printed "Avg of lowest N" disagreed with
  the visible numbers.
- **18-hole scores are rejected** at import time (course rating > 50 = error)
- **Handicap index suffix:** "N" indicates a 9-hole index
- **Plus handicap display:** negative computed value → shown with "+" prefix

## Expanded rounds view — INDEX column
The INDEX column shows the running handicap after each round was entered, computed using
**today's fixed lookback cutoff** (not a rolling per-round cutoff). This ensures the most
recent round's INDEX always matches the player's current displayed handicap. Older rounds
show what the handicap would have been including all rounds up to that point, with today's
12-month window applied.

The running index is computed **server-side** in `_attach_running_index_9` (in
`email_parser/database.py`) and returned as `running_index_9` on each row from
`/api/handicaps/rounds?player=…`. The browser used to do this in JS on every
expand — an O(N²) loop per player that was the dominant source of slow page
expands. The server version mirrors the same WHS algorithm and lookback cutoff,
so values are identical and `templates/handicaps.html` just reads the field.

## Expanded rounds view — GROSS + ADJ columns and scorecard expansion (v2.90.0/.1)

Every player's rounds table shows **GROSS** (raw score, joined from the
bridged scorecard via `handicap_rounds.scoring_round_id` — legacy
un-bridged rounds show "—") next to **ADJ** (the WHS adjusted score the
differential is computed from). A capped round renders ADJ in TGF
orange with a strokes-removed tooltip. Bridged rounds carry an orange
chevron on the date that expands the full hole-by-hole scorecard
inline (`toggleHcpScorecard` → `/api/scoring/scorecard/<id>` →
`tgfRenderScorecard`); both scorecard renderers (scorecard-render.js
and points-render.js — keep in sync) now include an **ADJ SCORE row**
that appears only when the WHS cap lowered at least one hole, capped
holes in orange. Applies to admin/manager AND the pinless member view.

**Nine display + resolution (v2.90.3, Kerry):** records that are one
nine of an 18-hole round label the COURSE, not the score: "- Front" /
"- Back" appended, or the nine's own name when the course name carries
named nines ("Hyatt Hill Country | Lakes/Oaks" → "… | Oaks";
`hcpNineLabel` in handicaps.html). Their expansion renders ONLY that
nine (holes sliced client-side, 18-hole derived_totals dropped) — TGF
handicaps are every-9-holes; full-18 cards belong on player scoring
records. The bridge repair gained a CORRECTION pass: an unmatched
record whose stored adjusted equals a nine's RAW gross while the WHS
adjusted differs is an uncapped Composer-era import (the workbook
repair skipped 18-hole rounds) — corrected to WHS, differential
recomputed, bridged. Suspect days include any day with an unbridged
record + an existing card. Kerry's standing rule: dashes are a bug
symptom to RESOLVE, not a display state to accept — only records
matching neither WHS nor raw totals stay unbridged (logged).

**Bridge integrity (v2.90.2):** the handicap↔scorecard bridge is
RECONCILING — each nine of an imported card claims at most one
unbridged record whose adjusted_score equals that nine's WHS-adjusted
total (`_bridge_handicap_records`); the legacy date-only claim
survives only for the safe single-card/single-record case. The old
player+date-only UPDATE let the first card of a multi-round day claim
every record (Hill Country Matches: Comanche CREEKS/HILLS/VALLEY all
rendered one card's gross beside their own ADJ values — "adjusted"
above gross, impossible). Boot repair
`_repair_handicap_bridge_assignments` re-derives all suspect days
(player with >1 card on a date, or >1 record sharing a card) — 
idempotent; unmatched records stay NULL. `get_handicap_rounds` also
guards at read time: adjusted > bridged gross ⇒ gross renders "—".

**Twin-nine ties (v2.90.4):** nine-resolution in `get_handicap_rounds`
is per CARD, not per row — records sharing a scoring_round_id claim
nines together (id order, front first), so a round whose nines have
identical adjusted totals (Flying L 5/30: 41/41) assigns cleanly
instead of failing the unique-match test and dashing out.

**18-hole bridges (v2.90.1):** an 18-hole round posts as TWO 9-hole
handicap records, so `get_handicap_rounds` NULLs the raw join for
18-hole cards and (player-scoped calls only) resolves each record's
nine via `_nine_totals_for_card` — per-nine gross + WHS-adjusted
totals matched against the record's adjusted_score. Rows then show
that nine's gross with an F9/B9 tag, and the expanded card leads with
a which-nine note. An unresolvable match (adjusted differs from both
nines) shows "—" rather than guessing. The naive join briefly showed
"80 | 41" with a phantom "39-stroke cap" tooltip (Kerry screenshots,
same day).

## Logged future work (Kerry 2026-07-14, tasks #16–#18)
- **Strokes-received projection** (untether from GG dots): our index →
  course handicap (index × slope/113 + (CR − par)) → playing handicap →
  allocation by stroke index, with TGF rules as versioned config
  (**max 2 pops per hole**; game variants like **Team Net: no pops on
  par 3s** live in the game-engine layer). Validate via parity sweep of
  projected dots vs GG's stored dots across all bridged rounds.
- **Pseudo-GHIN 18-hole index** for comparison to the TGF 9-hole index
  (9→18 differential method needs a spec ruling: post-2024 WHS
  expected-score vs legacy consecutive-nines pairing).
- **Automated Stableford cross-check** vs GG's awarded points lines.

## Expanded rounds view — cutoff lines
Two visual separator rows appear in the expanded rounds table:
- **Red line** — 12-month lookback boundary; rounds below are excluded from the pool
- **Green line** — 20-round pool boundary; rounds below are still active (within 12 months)
  but beyond the 20 most-recent that count toward the index. Only shown when a player
  has more than 20 active rounds.

## Admin controls
- **Import Rounds** button — visible to managers and admins
- **Purge 18-hole Scores** button — admin only; calls `POST /api/handicaps/purge-invalid`
  which deletes all rounds where `rating > 50` (catches any 18-hole scores that slipped in)
- **Settings** button — admin only; configure lookback window and minimum rounds
- Individual round **× delete** buttons — visible to managers and admins in the expanded view;
  there is no bulk "Delete All" for a player

## Auth notes
- Role is stored in the global `currentRole` variable (set by `auth.js`)
- Do **not** use `window._userRole` — that variable is never set

## Player ↔ Customer linking
- `handicap_player_links` table bridges Golf Genius player names to transaction customer names
- **Email-based matching** (highest priority): `_match_customer_by_email()` looks up email in `items.customer_email` and `customer_aliases` (alias_type='email')
- **Name-based matching** (fallback): `_match_customer_name()` tries: exact match, first+last, LIKE, aliases, reversed name, last-name-only (unique)
- Import supports `player_email` column — when present, email matching is tried first before name matching
- Both email and name columns support fill-down format (value on first row, blank on subsequent rows for same player)
- `/api/handicaps/players` auto-runs `relink_all_unlinked_players()` on each request
- Customers page also matches by `player_name` as fallback (not just `customer_name`)

## Golf Genius sync email — canonical-first (v2.16.26)

`get_handicap_export_data` (feeds the nightly 02:00 GG sync and the manual
Sync button) resolves each linked player's email canonical-first via
`handicap_player_links.customer_id`:
`customer_emails.is_golf_genius = 1` (the per-customer designated GG email —
the flag existed since the schema was created but the export never read it)
→ `is_primary = 1` → any profile email → legacy latest `items.customer_email`
snapshot by name → email alias by name. Golf Genius matches league members BY
EMAIL, so the legacy snapshot-first order could sync a player under a
guest-purchase blank or an old typo and silently never update their real GG
member. Emails can only be gained or corrected by this change, never lost
(legacy paths remain as fallback). `_log_gg_export_email_changes()` runs at
every boot (log-only) and lists players whose sync address changed or who are
newly included, so the deploy log shows the effect before the next 02:00 sync.

**Link identity repair (`_repair_player_link_identities`, boot):** three
passes, all idempotent, all re-point the link AND its player's
handicap_rounds (moved rounds get `scoring_round_id = NULL` so the next
scorecard import re-bridges them to the right card).
Pass 1 (v2.16.x): links whose `customer_name` (who the link is FOR)
resolves uniquely to a different profile than `customer_id` — the
buyer-email misattribution class (Will Massey → Colby Johnson).
Pass 2 (v2.24.2): links with NO customer_name are checked against the GG
`player_name` itself, re-pointed only when that name is a customer's
EXACT canonical name (alias-mediated or ambiguous matches left alone).
Pass 3 (v2.24.3): the email auto-matcher sometimes fills BOTH fields
with the buyer — Kailey Lopez's link recorded customer_name='Steve
Kulawik' AND cid 44 because her guest spots were bought on his email, so
pass 1 saw it as self-consistent. Re-points (and corrects
customer_name) only when the GG player_name is EXACTLY one other
customer's canonical name AND the linked customer separately holds a
link under their own name — proof the row can't be their display-name
variant. Nickname links (GG "Mike Murphy" → Michael Murphy) are never
touched. Symptoms of this class: one player's rounds silently feed
another's handicap record, and scorecard imports skip the victim as the
other player's cross-tournament "duplicate".

**Admin exclusions (v2.17.14):** `_GG_SYNC_EXCLUDES` in `database.py` lists
players the admin intentionally REMOVED from Golf Genius (inactive members
kept fully active in the tracker — currently Matt/Matthew Lawyer). The
export skips them (returned under `"excluded"`), so the nightly sync can
never silently re-add them to GG. Matched case-insensitively against both
the handicap player_name and the link's customer_name. As of v2.17.15 the
boot-time `_log_gg_export_email_changes` diff logger skips them too — it
queries `handicap_player_links` directly rather than going through
`get_handicap_export_data`, so before that fix it kept printing excluded
players as "NEWLY included" even though the export correctly omitted them.

**The nightly sync is removed (v2.18.0, admin decision):**
`golf_genius_sync.py` is a screen-scraping HTTP automation (logs into
golfgenius.com with `GOLF_GENIUS_EMAIL`/`GOLF_GENIUS_PASSWORD` env vars and
POSTs a roster CSV) — there is no official GG API and the admin reports a
reliable connection was never established, despite the creds being set on
Railway (the job was attempting the upload nightly). As of v2.18.0 the
02:00 APScheduler job is no longer registered at all; do not re-add it
without an explicit admin request. Handicap data reaches Golf Genius
manually: the admin downloads `/api/handicaps/export-csv` (same
`get_handicap_export_data`, same exclusions) and uploads it in the GG UI.
The on-demand `POST /api/handicaps/sync-golf-genius` endpoint remains for
explicit admin-triggered attempts. Keep the exclusion registry — it
governs the manual CSV and any future working sync. Longer term the admin
plans for the TGF Platform to replace Golf Genius outright.

## Handicap email — canonical email priority

`build_handicap_card_data` looks up the customer_id via the most recent items row that
has one, then reads `customer_emails.is_primary` first. The earlier implementation
preferred the most-recent `items.customer_email` and only fell back to
`customer_emails.is_primary` if items had nothing — so any historical typo on an items
row (e.g. Fred Wicker's `fredwickee@att.net` from one old order) would override the
canonical `fredwicker@att.net` primary the user maintains on the Customer Info page.

`build_handicap_card_data` is also refactored to use the
`resolve_player_email / phone / name / chapter / status` canonical resolvers (see
`docs/claude/customers.md → Canonical Identity Resolvers`). The bespoke email/chapter/name
lookup that was the source of the typo'd-email bug is gone. Items.* fallbacks remain only
for the few records where no primary email is set yet.

## items.handicap is no longer parsed from orders

The LLM email parser used to pull a `handicap` value from each order email and write it
to `items.handicap`. That column is no longer fed by orders:
- The `handicap` field is stripped from the LLM prompt schema in `email_parser/parser.py`.
- `_save_items` sets the persisted value to `None` so `items.handicap` stays empty on new
  rows.
- `has_handicap` (a separate membership-only YES/NO flag) is unaffected.

Handicap data effectively never came through GoDaddy orders in practice — the canonical
source is `handicap_rounds` (per-round differentials, re-aggregated by the WHS calculator)
joined via `handicap_player_links`. Stale `items.handicap` values on old order rows
looked authoritative but didn't update when the player's real handicap changed, so any
code path that read them silently drifted.

## Export dedup logic (CSV / Golf Genius sync)

`get_handicap_export_data` (in `email_parser/database.py`) returns one row per
**customer email**, not per `handicap_rounds` `player_name`. Multiple player_name
variants can link to the same customer (e.g. a legacy un-normalized name alongside the
current `First Last` form produced by `_normalize_player_name`), so the export groups
candidates by email and picks the one with the most recent round date (tiebreak: most
active rounds, then most total rounds, then player_name for determinism). This
guarantees the exported / GG-synced index always matches the freshest data the UI shows
for that customer — even when stale duplicate player records still exist in
`handicap_rounds`.

The earlier implementation iterated players in alphabetical order and skipped any whose
email was already `seen`, so a stale variant alphabetizing earlier than the current one
could win the export (e.g. Daniel Lehan exported as 4.4 / 9-hole 2.2 while the UI
correctly showed 17.2 / 8.6N).

When duplicates are collapsed, the `_debug.duplicate_emails` block in
`/api/handicaps/export-preview` lists every collision with which player_name was
chosen, which were dropped, and their indexes — useful for tracking down the source
duplicates and merging or deleting the stale ones via
`/api/handicaps/players/<player_name>` DELETE.

## Import dedup logic

When a handicap file contains a `round_id` column, the duplicate check matches on
`(player_name, round_date, round_id, course_name)`. This allows multi-course events
(e.g. Comanche Trace VALLEY / HILLS / CREEKS on the same day) to import correctly even
when Golf Genius assigns the same `round_id` to every round in the event.

When no `round_id` is present the fallback key is `(player_name, round_date, course_name, tee_name)`.

## Key files
- `email_parser/database.py` — `_HANDICAP_DIFF_LOOKUP` (server-side table), `_match_customer_name()` (linking logic)
- `templates/handicaps.html` — `DIFF_LOOKUP` (client-side JS table, must match)
- Both tables must always be kept in sync.

## Self-derived handicap import (v2.89.0 — Kerry-ratified WHS standard)

**RULING (Kerry, 2026-07-14): WHS standards for adjusted gross.** Basis
verified on Kerry's own GG "Spreadsheet Composer" downloads for a9.17
Falconhead + s9.17 Silverhorn: the export's only score column ("Score
1") is the RAW gross — all 42 rows byte-identical to scoring_rounds
.gross, no adjusted column, no slope/rating columns. The historical
handicap_rounds record therefore never had net-double-bogey capping;
our WHS derivation is the correction, not the deviation.

`derive_handicap_rounds_from_scoring(event_query, dry_run=True)`
(bridge: `scoring-hcp-import:<event>` dry-run / `<event>|apply` write)
writes one handicap_rounds row per eligible 9-hole scoring round of the
event: adjusted_score = WHS NDB adjusted gross via the formula layer,
slope/rating from the round's OWN tee row, differential computed,
`scoring_round_id` bridged at birth. Skips (listed in the response):
already-bridged rounds, dedup-key hits, 18-hole rounds, missing tee or
par data. Identity: reuses the customer's EXISTING handicap
player_name variant (freshest record wins — the export-dedup rule) so
a self-derived round extends the record instead of forking it; new
players get a handicap_player_links row on apply.

**First live run (v2.89.1, Kerry 'apply'):** s9.17 Silverhorn (27) +
a9.17 Falconhead (15) written export-free, after verifying all 42
self-derived adjusted values byte-identical to GG's own "Adjusted
Gross Score" sheets in Kerry's season-scores workbooks
(TGF_<city>_2026_Season_Scores.xls — the GG report that DOES carry
true adjusted gross; the Spreadsheet Composer report does not).

**Composer-import repair (v2.89.1, Kerry 'run it'):**
`repair_handicap_adjusted_scores(cells, dry_run=True)` (bridge
`scoring-hcp-repair:<json>[|apply]`) fixes 2026 rows whose
adjusted_score was imported as raw gross, using GG's true Adjusted
Gross from the workbooks. Guards: 2026 only; adjusted < gross; unique
(normalized name, date) match; stored value must EQUAL the file's
gross — 'already correct' and 'matches neither' rows skip (never
guess). Differential recomputed from the row's OWN stored slope/rating
(tee-rating discrepancies intentionally out of scope). Idempotent.

**CAVEAT:** never ALSO import the GG export file for an event that was
self-derived here — a file carrying round_ids bypasses the fallback
dedup key and would double-count the rounds. Per event it's one path
or the other. Rounds already recorded from a GG file are skipped by
the writer, so mixed history is safe; only the same-event double
import is not.

**Max-triple interplay (documented for the record):** TGF games cap
ENTERED scores at triple bogey, so with 0 strokes received on a hole
the WHS cap (par+2) still bites below the entered triple; with 1
stroke received the two caps coincide (par+3); with 2+ received the
NDB cap (par+4+) exceeds the entered triple so it never binds — and a
true blow-up beyond triple was already recorded as triple at entry,
which slightly UNDERSTATES the differential vs pure WHS in that rare
case (favors the player; inherent in max-triple score entry, accepted).

## Self-derived handicap preview (v2.88.0 — read-only, Phase 2 step 2 prep)

`get_scoring_handicap_preview(event_query)` (bridge:
`scoring-hcp-preview:<event>`) computes, from OUR imported scorecards,
the handicap round each player of one event WOULD get — per player:
adjusted gross, differential, current index, and the index the new
round would produce. **Writes nothing.** Built (Kerry 2026-07-14) so
the manual GG handicap export/import ritual can be retired on evidence:
preview an event, eyeball it against GG, only then consider a real
self-derived import.

**Confirmed parity finding (2026-07-14, McKinley a9.1 / Barna a9.4
cards):** GG's handicap export carries the RAW GROSS as the round's
"adjusted" score — no WHS net-double-bogey cap — while our formula
layer caps per WHS. This is the dominant family of the ~9% parity
mismatches (2026 cluster, GG exactly ours+1 whenever one hole capped),
a POLICY difference, not a math bug. The preview therefore reports BOTH
variants side by side (`differential_ndb` / `differential_raw`, and
`index_after_*` for each) plus `capped_holes` and a
`cap_changes_differential` summary count. **RESOLVED same day: Kerry
ratified WHS standards (see Self-derived handicap import above)** —
the raw-gross variant stays in the preview output as a reference
column only. The smaller opposite family (GG BELOW our capped value —
mis-bridged cards like the Victor Arias Jr/III double-bridge, or
different strokes-received allocation) is a per-case review queue;
`get_differential_parity` now classifies both under
`mismatch_families` and lists `tee_mismatch_detail` (tee-row hole
range vs the nine actually played) to separate legitimate front/back
rating pairs from stale tee rows.

Mechanics: slope/rating come from the round's OWN tee row (captured
from GG's tee block at scorecard import) — per-round truth, immune to
a course carrying front/back or re-rated variants under one tee name.
The player's existing differential pool is gathered across ALL
`handicap_rounds` player_name variants linked to their customer_id,
window/pool/index math via the same `compute_handicap_index` the
handicap card uses. Rounds already bridged to a handicap_rounds row
are flagged `already_imported` with GG's stored values for
side-by-side. 18-hole rounds are skipped (front/back split still
unbuilt — same Phase 2 gap as parity).

## Golf Genius public-portal probe (v2.18.1)

MCP tool `probe_golf_genius(url, extract, max_chars)` fetches a public GG
portal page from the Railway side (Claude's sandbox network policy blocks
golfgenius.com; Railway has open egress) and returns parsed structure.
`extract`: summary | links | tables | text | raw. Hard host allowlist —
https + `*.golfgenius.com` only, re-validated after redirects — because an
MCP-exposed fetcher without it is an open proxy into the Railway network.
Helpers: `fetch_public_page()` / `parse_page_structure()` (stdlib
HTMLParser, no bs4) in `golf_genius_sync.py`. Admin's public SA entry
point: https://tgf-sa.golfgenius.com/pages/5783305. This is the
exploration path toward importing GG results/standings into the tracker.

## Chapter tabs (v2.48.0, Kerry)
ALL | AUSTIN | SAN ANTONIO pills above the players table (TGF-orange
active). Chapter comes from customers.chapter via
handicap_player_links.customer_id (get_all_handicap_players now
returns `chapter`); unlinked players have none and only show under
ALL. Chapter-manager sessions land pre-filtered to their chapter;
admin lands on ALL. Import Rounds + the three CSV exports are
consolidated into one Import/Export dropdown (admin + manager); Email
Cards stays standalone.

## Public member view (v2.53.0, Kerry)

`/member/handicaps` renders this page pinlessly (`member_mode=True` +
the `member` role tier — see CLAUDE.md → Auth and
docs/claude/member-portal.md). The GET endpoints
`/api/handicaps/players|rounds|index-map|settings` serve anonymous
callers (names/stats/chapter only — no emails or phones in the
payload). All write/import/email endpoints keep their manager/admin
requirements; with currentRole null the header ops buttons and
per-player action buttons stay hidden, and player names render
without their /customers links.

## Default filter: current members (v2.53.1, Kerry)

The players list defaults to CURRENT MEMBERS only — a MEMBERS |
EVERYONE pill pair sits after the chapter tabs (MEMBERS active on
load). "Member" = customers.current_player_status IN ('active_member',
'member_plus') via handicap_player_links; guests, first-timers,
expired/inactive, and UNLINKED players are hidden until EVERYONE is
selected — flip to EVERYONE when working the link/auto-link queue.
get_all_handicap_players returns `player_status` for this. The stats
row (Players Tracked / Total Rounds / avg index) stays global,
matching the chapter filter's existing behavior.

## Trend column + member table (v2.56.1, handoff contests-handicaps-071026)

`get_all_handicap_players` returns `handicap_trend`: the index delta vs
the index recomputed WITHOUT the most recent round (needs both pools
computable, else null). Negative = improving (▼ success-green
#16A34A), positive = ▲ red, 0/null = — gray. The pinless member table
renders the ratified 5-column view (chevron | Player | Index | Trend |
Rounds, right-aligned numerics); admin/manager keep the full 9-column
table with the trend chip beside HCP. MEMBERS|EVERYONE active pill is
now dark (--surface-dark) per view 1a; table headers wear the Bitter
hairline treatment; stat cards Bitter labels + dark numerals. The
expanded round-history interior keeps its current functional styling —
its 1a cosmetic pass rides with the admin-density handoff.
