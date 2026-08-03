# Handicap System — TGF Rules

All handicap calculations are for **9-hole rounds only**. The differential
lookup counts match WHS Rule 5.2a. Adjustments per that rule are also applied.

## ═══ RATIFIED RULINGS OF RECORD (Kerry, mailbox #196/#197, 2026-07-16) ═══

The go-live rulings package. Full ratification language lives in
`handicap-projection.md`; this is the enforcement mirror. **Nothing beyond
the ratified items below changes code or data without Kerry's sign-off.**

- **D1 (RATIFIED 2026-07-16) — tee-based playing handicap is the TGF
  standard.** Course Handicap = index × slope/113 + (CR − par), unrounded;
  Playing Handicap = whs_round at **100% allowance, no cap except the 18.0
  nine-hole CH cap**; per-hole allocation by stroke index, **max 2 pops**.
  Plus-handicap treatment + per-game adjustments explicitly EXCLUDED (own
  rulings pending). Index provenance is a separate layer, does not gate D1.
- **D4 (CLOSED) — nine-hole CH cap = the 2-pop rule.** GG's "Maximum Nine
  Hole Course Handicap 18.0" is the same constraint. **Ordering note:** GG
  rounds THEN caps; our spec caps THEN rounds — equivalent at integer caps,
  but **pin the order in config before any fractional/per-game cap exists.**
- **R1 — REMOVE the ×0.96 multiplier** (pre-2020 USGA "bonus for
  excellence," deleted by WHS). **APPLIED 2026-08-03** per the ratified
  sequence: sweep (`scoring-hcp-r1-impact`) reported 158/168 indexes rise,
  mean +0.31, max +0.8 → dial + default flipped to 1.0. Record layer
  updates retroactively (by design); no paid result touched.
- **R2 — 12-month lookback window is a DELIBERATE deviation, ratified**
  (deviation register).
- **R3 — Plus handling = "fall-where-it-falls" for now.** Website ÷2 rule
  NOT practiced. Full plus design HELD for a dedicated session. Do NOT ship
  the engine's "give a stroke back on easiest holes" as ratified behavior.
  Banked intents: no per-hole penalty; points games play off zero + subtract
  plus strokes from the point TOTAL post-event; team games off LOWEST shift.
- **LAYERING PRINCIPLE.** The handicap-record layer only ever sees raw gross
  adjusted at 100% handicaps. Game-layer adjustments (off-lowest, allowances,
  plus zeroing) live downstream and NEVER feed back into caps/differentials.
  One-way flow — no game rule can contaminate a handicap.
- **RESULTS AUTHORITY HIERARCHY (Kerry, 2026-07-16):**
  1. **Actual Venmo payouts are the HIGHEST authority — IMMUTABLE.** Nothing
     already paid may ever change. The audit reconciles our records DOWN to
     what was actually paid; it never proposes altering a paid amount.
  2. **GG results are bible for every event BEFORE a9.18/s9.18.**
  3. **Our self-computed determination is authoritative from a9.18 FORWARD.**
- **RETROACTIVITY BOUNDARY (STANDING RULE).** The handicap **RECORD** layer
  (indexes/differentials) **DOES update retroactively** to include the WHS
  caps — that is correct and desired. But that record change must have altered
  **ZERO RESULTS before a9.18 Forest Creek / s9.18 Cedar Creek**. a9.18
  (2026-07-14) is the **first event the cap affects results** (and is not yet
  paid, so our capped computation drives it); s9.18 rained out (moot). The MVP
  badge enforces this with `_MVP_RETRO_BOUNDARY = "2026-07-14"`: events
  `>=` it are ours, events before it defer to GG. **RECORDS change
  historically; RESULTS do not, pre-a9.18.**
- **H-5 (CLOSED) — Star Ranch tee values stand.** Our per-round capture
  carries the correct BACK-9 tee values; GG's handicap export shipped
  FRONT-9 values nine-blind. The 177 rounds are an explained legacy export
  defect — our per-round values are correct.

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

Formula: `round(avg_of_lowest_N + adjustment, 1)` (×0.96 removed 2026-08-03, R1)

## Calculation rules
- **Lookback window:** 12 months (configurable)
- **Pool:** most recent 20 rounds within the window
- **Multiplier:** none — avg of lowest N (the 0.96 was removed 2026-08-03, R1)
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

**Played side is RECORDED, not derived live (v2.122.0, Kerry-ratified
2026-07-19).** The nine a 9-hole handicap posting represents is stored in
`handicap_rounds.nine` ('front' | 'back' | NULL), populated at import time
from the round's scorecard — **front = holes 1-9 scored, back = 10-18**;
an 18-hole card is split by matching the posting's adjusted score to the
nine's WHS-adjusted total. Previously the side was re-derived live in
`get_handicap_rounds` on every page load from each round's bridged card,
so a posting with a missing/ambiguous bridge showed a BLANK side even when
a scorecard proving the nine existed. The read path still surfaces the
stored value (via `hr.*`), and the live derivation remains a self-healing
fallback for not-yet-stamped bridged rounds. **Named-nine courses stay
NULL** (their nine is in course_name). Backfill/going-forward:
`persist_handicap_round_nines(dry_run)` (bridge `scoring-hcp-nines:dry|
apply`) resolves the side from the bridged card, else any scorecard for
the same **customer_id** (via `handicap_player_links`) or normalized name
(`LAST, First` ↔ `First Last`) + date; idempotent, only fills NULL, never
overwrites, never touches scores/differentials (frozen-safe). It runs
after every CSV import and after the single-nine/two-nine self-derives, so
new rounds get a side immediately. Rounds with **no imported scorecard
anywhere** (the ~10.8k legacy no-card bucket) genuinely can't get a side
and stay blank until their card is imported. **Multi-18-course facilities**
(TPC San Antonio Oaks/Canyons, Squaw Valley Apache Links/Comanche Lakes)
are NOT named-nine — their side reads Front/Back like any 18-hole course;
`_MULTI_COURSE_18_FACILITIES` + `_course_names_its_nines` in database.py.

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

**Full-table audit (v2.91.0):** `audit_handicap_bridges()` (bridge
`scoring-hcp-audit`, READ-ONLY) classifies every handicap record.
First live run (2026-07-14, 14,992 records): 3,453 bridged+reconciled,
**17 bridged_mismatch** (two families: stored==raw-nine-gross uncapped
imports on single-record 18h days the repair's suspect net missed, and
2025 rows where GG's stored adjusted is LOWER than our WHS — likely
GG allocating dots from full course handicap; per-case queue, do NOT
auto-fix), **42 unbridged_card_exists** (incl. literal duplicate
record pairs — Rohrmann/Garcia/J.Jenkins/Baker twins — deletion needs
Kerry), 1,717 unbridged_no_customer (identity backlog), 9,763
unbridged_no_card (pre-scorecard eras — expected). 9-hole records now
also carry `nine` (the physically played nine from hole numbers), so
back-nine events label "- Back"/named nine like 18s.

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

**Manager recap email (v2.149.27, Kerry 2026-07-29: "auto send manager
handicap reports for each chapter after each posting"):** every `|apply`
that writes rounds auto-emails a per-chapter recap — header (event /
course / date / standard), biggest index movers (|Δ| ≥ 0.4, green
down / amber up), then the full per-player table (gross, NDB-adjusted,
differential, index before → after, † capped-hole marker; brand-new
players show "new"). Non-fatal: a mail failure never rolls back the
posting (result carries `recap_email`). Recipients are rules-as-data:
app_setting `hcp_recap_email_<chapter_slug>` (`hcp_recap_email_austin`,
`hcp_recap_email_san_antonio`), then `hcp_recap_email_default`, then
env `COO_EMAIL_TO` → `EMAIL_ADDRESS` (Kerry's inbox) — so recaps flow
to Kerry until per-chapter manager addresses are configured. Manual
(re)send for an already-posted event: bridge `scoring-hcp-recap:<event>`
(`send_handicap_recap_for_event` rebuilds before/after from the preview,
whose pool excludes each card's own bridged round, so post-hoc numbers
stay correct).

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

## STARTING handicaps: one shared map, editable from both screens (v2.167.0)

Kerry, 2026-07-31: *"When I added Mark Villa's handicap on PAIRINGS, it did
not add it to him in ROSTER. Those need to be immediately synced. They also
both need to be editable."*

**The value was never lost.** Villa (customer_id 692) persisted at 12.5.
The bug was display-side and worth remembering, because it is the
name-keyed-payload trap again:

- The ROSTER handicap cell reads **only** `handicapIndexMap`, keyed by
  lowercased customer name (`/api/handicaps/index-map`).
- The PAIRINGS card patched its own in-memory copy after a save, so it
  showed the number while the roster still showed a dash.

Fixes, all in `templates/events.html` unless noted:

- `patchLocalHandicapIndex(customerId, extraNames, index18)` writes the
  saved value into the SHARED map under every name associable with that
  `customer_id` (from `allItems` and `state.event_players`), then both
  views repaint before any round-trip. Never overwrites a `computed` entry.
- `fetchHandicapIndexMap()` uses `cache: "no-store"` — it is called
  immediately after a save, and a cached copy defeats the refresh.
- The roster cell renders a `starting`-source value as the same
  `.btn-set-hcp` control the pairing card uses (`.roster-hcp-prelim`,
  `data-current` prefills the prompt). A `computed` index stays
  uneditable on both screens.
- **`app.py` `api_handicap_index_map`**: `index_18` now comes from
  `starting_handicap_18` directly when the source is `starting`. It was
  being re-derived as `round(index_9 * 2, 1)` from an already-rounded
  half, so a typed 12.5 displayed as 12.4 (every odd tenth was affected).
  The stored value was always correct.

A rounds-less player reaches the map via `get_starting_handicaps` →
`get_all_handicap_players`, which APPENDS placeholder-only customers to a
list that otherwise starts from `handicap_rounds`. Tests:
`test_starting_handicap_sync.py`.

### The map is keyed by customer_id (v2.168.0)

Kerry, same evening: *"I added in ROSTER and it showed in PAIRINGS, but
when I edited in PAIRINGS, it disappeared in ROSTER."*

v2.167.0 made both screens read one shared map and patch it on save — but
that map was still keyed by NAME, so the whole arrangement rested on a
player being spelled the same on `items.customer` as on
`customers.first_name || last_name`. Where they differ, an edit resolves
to a key the other screen never reads, and the value looks gone.

- `api_handicap_index_map` emits `cid:<customer_id>` keys alongside the
  lowercased-name keys, pointing at the SAME entry object; the entry also
  carries `customer_id`.
- `get_all_handicap_players` stamps `customer_id` on EVERY player (it was
  resolved only to merge starting handicaps in, so computed players
  arrived with none).
- `templates/events.html` `hcpEntryFor(name, customerId)` is the one
  accessor both the roster cell and the pairing card use — id first, name
  as fallback. `patchLocalHandicapIndex` writes the id key too.

Name keys are retained as a fallback, so nothing that still looks up by
name breaks.

## 18-hole events post as TWO 9-hole rounds (championships)

TGF is a 9-hole-index league — an 18-hole event posts as two 9-hole
`handicap_rounds` per player (front + back), each with its OWN per-nine
course rating + slope. `derive_18hole_rounds_as_two_nines(event_query,
per_nine, dry_run)` in database.py; bridge `scoring-hcp-2nines:<event>|
<per_nine_json>[|apply]` (generic successor to the Vaaler-specific
command; JSON maps tee_id -> {"front": [rating, slope], "back": [...]}).
Rules of record:

- **Per-nine numbers come from GG course setup** (Kerry reads them off
  the course's tee editor — front/back rating & slope are the first-class
  fields there). Never derive slopes by inverting the 18-hole value: GG
  stores the 18-hole slope independently (The Quarry Blue is 103/115
  per nine yet 113 for 18 — not the average). Ratings DO sum exactly
  (F + B = 18-hole rating), which is the validation check.
- **Intra-run dedup** (v2.191.4): the ALL Net → ALL Gross scorecard
  backfill banks TWO scoring_rounds per player per event; the derive
  plans each (player, date, tee-nine) once and skips the twin.
- **Recap emails**: `scoring-hcp-recap:<event>` detects two-nine postings
  (the 9-hole preview path skips 18-hole rounds) and rebuilds recap rows
  from the POSTED handicap_rounds via `_two_nine_recap_rows` (v2.191.5).
- **Posted 2026-08-03**: TGF SAN ANTONIO CHAMPIONSHIP (The Quarry — Gold
  F 34.2/117 B 35.6/128, Blue F 32.5/103 B 34.2/115, Red F 31.3/103
  B 32.3/98, Red(L) F 34.1/119 B 35.0/121; 32 players / 64 rounds) and
  TGF AUSTIN CHAMPIONSHIP (Falconhead — Blue F 36.4/130 B 36.1/136,
  White F 35.1/121 B 34.8/126, Red F 33.2/116 B 33.2/119; 16 players /
  32 rounds). All numbers Kerry-read from GG course setup.
