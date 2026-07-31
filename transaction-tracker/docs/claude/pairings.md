# TGF Pairing Standards — ruleset of record

Kerry, in-session 2026-07-12 (verbatim intent, lightly structured).
**Explicitly NOT exhaustive** — Kerry's first direction: request the
pairing docs platform-claude (CA) holds and merge them here BEFORE the
engine build (mailbox request posted same session). Per house
principle 2, these ship as named, editable rules-as-data, not code.

## Why this matters (Kerry)

"We are The Golf Fellowship and getting to know everyone is part of
who we are." The engine is heavily based on who's played with whom,
maximizing NEW pairings every round. Who RODE together (cart pairs)
matters too, not just the foursome.

## The rules (Kerry, 2026-07-12)

1. **One playing-partner request per person per event.**
2. **TGF reserves the right to fill the remainder of the foursome.**
3. **Random pairing driven by history** — all-time played-with history
   is tracked and reflected, but the operative goal is SEASON-scoped:
   everyone plays with everyone else at least once each season.
4. **Guests pair with their inviter** unless otherwise requested.
5. **Admin and manager can always override** automated pairings.
6. **Every foursome contains at least one member who has played
   before** (experienced anchor).
7. **Ambassadors are spread across groups as captains** — pace of
   play + welcoming new guests/members.
8. **A match (match play) overrides a request** when the two conflict.
   **AMENDED (Kerry 2026-07-14): Match Play dictates pairings as the
   1st rule — "Match Play is king."** If the Match Play season state
   (pool play or the current knockout round) implies a potential match
   between two rostered players, the generator must pair the opponents
   in the same foursome, ideally in SEPARATE carts, and visually
   denote them as Match Play participants. Partner requests are still
   honored where possible, but never at the match's expense. Before
   generating, the manager gets a per-match CONFIRM question — a "no"
   (match not required this event) drops that constraint and the next
   pairings rule runs normally. (Task #25 — BUILT v2.100.0, see
   "Match Play constraint" section below.)
9. **Members may fill their foursome with first-time guests.**
10. **Request communication is part of signup** (Platform build):
    when someone signs up, notify whom they've requested.
11. **A request from or for a person LOCKS both players** from further
    requests for that event, unless the other declines.

## Ratified (Kerry, in-session 2026-07-12)

- **customer_id amendment: GO** ("Yes on customer id thing") — rebuild
  pairing_history keyed by customer_id + archive-event support +
  played-with/rode-with distinction. event_pairings joins the same
  amendment (see audit below).
- **Cart-pair ruling:** cart partners derive from the SEQUENCE of the
  pairing on the tee sheet / scorecard — **spots 1 & 2 ride together,
  spots 3 & 4 ride together.** (Scorecard groups preserve player order,
  so rode-with history IS recoverable from the archive walks.)
- **Priority order: NOT final.** Kerry + CA are vetting the full
  directive set; final ordering comes back as direction. The order
  sketched under Engine notes remains a non-ratified draft.

## Rule-6 audit (Kerry-directed, run 2026-07-12)

Swept all 104 CREATE TABLEs + the boot-time customer_id migration
registry. Person-bearing tables WITHOUT customer_id — the complete
list of remaining violators:

1. **pairing_history** (player_a/player_b names) — fix ratified above.
2. **event_pairings** (player_name, cart_pos) — same family, rides the
   same amendment.

Everything else person-bearing is compliant via design or boot
migrations (items, rsvps, season_contests, handicap_rounds,
handicap_player_links, customer_aliases, cmp_matches/cmp_bracket via
player/opponent/winner-id columns, all gg_history_*/gg_member_map).
`name_parse_failures` is exempt by nature — it is the log of names
that COULDN'T resolve to a customer.

## Data feeds

- **Played-with history**: scorecard groups (shared
  `scoring_rounds.gg_aggregate_id` = actually teed off together) —
  already banked by every GG-history holes walk (2025 done, more
  seasons as walks run) — plus `event_pairings` for app-run events,
  plus the future tee-sheet scrape (Kerry's ruling: tee sheets
  primary / starter-sheet PDFs cross-check / score groups tiebreaker).
- **Rode-with history (cart pairs)**: `event_pairings.cart_pos` for
  app-run events. GG scorecard groups do NOT carry cart splits;
  archive cart data only where tee sheets published it.
- **`pairing_history` amendment (RULE 3B — awaiting Kerry's explicit
  ratification):** key pairs by customer_id (currently name-keyed —
  rule-6 violation) + allow archive events (events-FK is NOT NULL
  today) + distinguish played-with vs rode-with.

## CA/platform-claude docs merge (mailbox #134, 2026-07-12)

Vetting verdict: NO conflicts with Kerry's 11 rules. Additions:
- **Pairing MODES are first-class per event**: standard | **ABCD
  Night** (one A/B/C/D handicap-band player per foursome) | **Dream
  Team** (full player choice, no random assignment). From the live
  website FAQ — Kerry's list omitted these.
- **Foursome Lock System is the engine's runtime** (Error Handling
  Spec §7, ratified): lock at 5pm day-before (9-hole) / 3-days-before
  (18-hole) / custom; pairings generate at/after lock; post-lock only
  complete foursomes may add (max 3, until start); withdrawal reopen
  scenarios defined there.
- **Constraint inputs beyond foursome composition**: TEE-TIME
  preference ("need latest tee time") and CART needs — engine places
  constrained players into compatible slots; cart-pair assignment
  (1&2 / 3&4) honors them.
- **Guest-host association is already structural** (registration +
  roster "Guest of [Member]") → feeds guest-with-inviter directly.
- **Lane ruling**: Tracker builds the V2-era engine (correct home);
  Platform V1.0 only captures the request at signup; Kerry's rule 10
  (signup request-notification) needs a Platform scope decision
  (CA recommends V1.5).
- **CA's proposed build order** (Kerry to finalize): history banking
  (running) → customer_id migration (ratified) → standard-mode rules
  engine → tee/cart/match constraint layer → ABCD/Dream Team modes →
  manager override UI → Platform signup flow.

## GG tee-sheet ingest (v2.94.0 — Kerry overnight directive 2026-07-14)

Bridge commands (`scoring-pairings:` on probe_golf_genius):
`rounds|<sa|austin|page_url>` lists the portal TEE SHEETS widget's
rounds; `round|<portal>|<round_id>[|apply]` parses/writes one;
`all|<portal>[|apply]` walks everything (time-budgeted, resumable).
Discovery: portal menu → TEE SHEETS page → iframe widget (cached).
Parsing (`_parse_teesheet_groups`) handles fill-down time-cell rows
and one-row-per-group layouts; unknown layouts return debug_tables
over the bridge for diagnosis without a redeploy. Players resolve via
`_resolve_scoring_player`; rows store canonical names + customer ids.
**Apply REPLACES the event's pairing_history rows** (tee sheet =
ruled primary source) — same replace semantics as an app-side save,
so app-save and GG-ingest can't double-count an event.

**Ratified customer_id amendment: implemented ADDITIVELY** —
pairing_history gains customer_a_id / customer_b_id / rode / source
('app'|'gg_teesheet'); `save_event_pairings` writes all four (rode by
cart_pos 1&2 / 3&4). The full name-key retirement still pends the
archive-events (nullable event_id) design.

`get_pairing_history_counts(year)` — the generator's season-scoped
repeat-minimizing signal — reads this table unchanged, so ingested
history immediately drives maximize-new-pairings.

## GG TEAM/CART Net board ingest (v2.95.0 — the route that WORKS)

The tee-sheet route above hit two walls the night it shipped: the
public TEE SHEETS page hosts a `next_round` widget (upcoming event
only, no round selector, unpublished pairings render as an
alphabetized confirmed-players grid), and the PLAYER TIMES TOGETHER
page (5783331) is login-gated. **Working source:** each played
round's `tournament_results` widget lists a **TEAM Net $** board
(SA, foursomes; "TEAM Net 18 $" on 18-hole rounds) or **CART Net $**
board (Austin, cart pairs) whose rows are the ACTUAL playing groups
in seat order — e.g. "SOUTH, Daniel + MORENO, Robert + WADE, Mary +
Bl[HAMILTON, Doug] TGF San Antonio".

Bridge commands: `scoring-pairings:teamrounds|<portal>` (round
selector off the results widget), `team|<portal>|<round_id>[|apply]`,
`teamall|<portal>[|apply]` (budgeted, resumable). Source column:
`'gg_teamnet'`; same replace-per-event semantics.

Caveats of record:
- **Blind-draw fills** (`Bl[Name]`) are on the card but not in the
  group: parsed as EMPTY seats — excluded from played-with pairs,
  but the seat is kept so the 1&2 / 3&4 cart split stays aligned.
- **SA rode flags assume board order = tee-sheet seat order** (team
  boards are built from the tee sheet; verify against a published
  tee sheet when one appears). Austin CART rows are cart pairs by
  definition — rode=1 is exact.
- **Austin has NO foursome board** — only cart pairs land; the
  other-cart half of each Austin foursome is not publicly derivable
  (scorecard aggregates are per-player on the 2026 portals).
- Rounds whose label carries no event code and a truncated date
  (preseason: KICKOFF/LA CANTERA/CEDAR CREEK options are cut off
  mid-date by GG) may not match a Tracker event — they surface in
  the walk report as unmatched, not silently skipped. The `team|`
  subcommand takes an event override (`|apply|<event id or name>`).

### 2026 grab COMPLETE (overnight 2026-07-14, Kerry directive)

All 41 played rounds ingested with source `'gg_teamnet'`:
- **SA (22 rounds)**: s9.1–s9.17 (no s9.6/s9.11 — not in GG's round
  list, both 0-registration Tracker events, presumed rained out),
  s18.1–s18.7, LA CANTERA + the two override applies (KICKOFF → 609,
  Feb CEDAR CREEK → 3). ~865 pairs. s18.5 WILLOW SPRINGS used a
  "CART Net 18 $" board → cart pairs only (7).
- **Austin (19 rounds)**: a9.1–a9.17 (no a9.6, same pattern),
  a18.1–a18.3. ~490 pairs. a9.17 Falconhead + a18.3 CRYSTAL FALLS
  are CART-board rounds (pairs only); the rest have TEAM boards, so
  Austin DOES get foursomes most weeks.
- Zero unresolved player names across both portals.
- **Kerry flags from the walk**: (1) Tracker has BOTH
  `a18.2 AUSTIN KICKOFF | ShadowGlen` (id 2578, Mar 14 — the real
  a18.2, matches GG) and `a18.2 CRYSTAL FALLS` (id 3267, May 30,
  11 regs) alongside `a18.3 CRYSTAL FALLS` (id 3263, May 30, 12
  regs) — 3267 looks like a mislabeled twin of 3263 and its
  registrations may need merging; (2) HILL COUNTRY MATCHES |
  Comanche Trace (May 16) is not on either league portal's round
  list — no pairings ingested for it.
- Tonight's s9.18 / a9.18 post AFTER play: re-run
  `scoring-pairings:teamall|<portal>|apply` any time — replace
  semantics make it idempotent, and new rounds are picked up.

### FINAL STATE (2026-07-14 morning): final tee sheets are the source

Kerry's route ended the scraping saga: every portal's SCHEDULE
calendar lists a public per-round **Tee Sheet** page, and its
`next_round` widget serves the HISTORICAL final sheet when given
`round_id=` (the original attempt used `round=` — that's the whole
reason the tee-sheet route looked dead). `scoring-pairings:round|` /
`all|` now walk these (round ids + labels from the tournament_results
selector). Parser handles the By-Tee-Times layout: `(time, [hole,]
players)` windows, two-column rows + single-column repeats deduped,
shotgun hole labels (1A/1B) accepted, and the alphabetical
By-Individual table excluded (its `Other Players` cells carry ` + `
separators — never a group; 18-hole layouts put them inside the
window).

ALL 41 played 2026 rounds now carry final-tee-sheet groups (source
`'gg_teesheet'`, true seat order → exact rode pairs) with two ruled
exceptions: **s9.12 Canyon Springs** (sheet never published in GG —
page shows the alphabetized confirmed grid; its TEAM-board groups
stand, per tee-sheets-primary / score-groups-tiebreaker) and **HILL
COUNTRY MATCHES** (own portal; ingested from the OneDrive Starter
Sheet PDF, source `'tee_sheet'`). The team-board route (`team|` etc.)
remains as the fallback/cross-check.

### Generator objective: NEW PAIRINGS FIRST (v2.97.0, Kerry-ratified)

Rule 3 verbatim is MAXIMIZE NEW PAIRINGS — a once-played pair and a
thrice-played pair are equally "not new". `_pair_cost` therefore makes
any repeat cost 1000 + count: the optimizer minimizes the NUMBER of
repeat-pairs first and uses play counts only to break ties (prefer
re-pairing 1s over 3s when repeats are forced). The earlier
summed-count objective could trade an extra repeat-pair for a lower
total, which contradicts rule 3.

### Generator: history-optimal (v2.95.3–v2.95.7, live-verified)

Kerry's live s9.18 report ("pairing me with players I've played with")
had TWO layered causes, both fixed:
1. Single greedy pass → best-of-30 restarts + case/whitespace-
   normalized pair keys (v2.95.3).
2. **Last-group attractor** (the real killer, root-caused via the
   `gen|` probe): the greedy fills groups in order, so the most-played
   players get avoided until the end and pool together in the final
   group — restarts never escape it. Every candidate now runs a
   pairwise-swap hill-climb between groups (partner-request pairs are
   never split) (v2.95.7).
Verified against the live s9.18 matrix: the generator's answer (17)
equals the true optimum (4,000-restart offline search; 57 of 91
roster pairs already had history — 10 of the 17 is the Palacios↔
Anthis locked request alone). Debug bridge: `scoring-pairings:
gen|<event_id>` (seedless run + per-group repeat math + roster
submatrix), `hist|<event id or name>` (raw rows + totals by source).

### Kerry corrections + generator fix (2026-07-14, morning)

1. **CART-board weeks still played in real 3/4-somes** (Kerry). The
   foursomes come from the OneDrive `Seasons/<year>/2 Events` starter
   sheets via `scoring-pairings:manual|<event_id>|<json>[|apply]`
   (source `'tee_sheet'` — the ruled PRIMARY source; replaces the
   event's rows). DONE: s18.5 WILLOW SPRINGS (271, 21 pairs) and
   HILL COUNTRY MATCHES (274, 45 pairs — from its Starter Sheet PDF;
   its own GG portal wasn't needed). STILL CART-ONLY: a9.17
   Falconhead + a18.3 CRYSTAL FALLS — no starter sheets on OneDrive,
   Kerry to supply a tee-sheet source.
   `!Name` seat prefix = literal guest, NO customer resolution (the
   fuzzy cascade mis-attached guest 'Cleary, Paul' to a member).
2. **Cart-sequence ruling VERIFIED against a real event**: Willow
   Springs `CartSigns.pdf` cart pairs exactly match starter-sheet
   seat order 1&2 / 3&4.
3. **Generator fix (v2.95.3)** — Kerry's live report: s9.18 generate
   repeated his s9.17 foursome-mates. History rows were correct and
   name-keyed identically (verified via `hist|`); the failure was the
   SINGLE greedy pass. Now: best-of-30 restarts keeping the
   fewest-repeat arrangement, plus case/whitespace-normalized pair
   keys (`_pair_key_name`) so name drift between writers can never
   silently zero the history again.
   `scoring-pairings:hist|<event id or name>` = read-only debug view.

## Kerry's GG workflow + validation vs GG (2026-07-14)

- **Operating pattern:** GG Automatic + Random + Keep Together (requests)
  for league nights; Manual pairings for HCM/Championships. Target:
  full automation, manager approval only.
- **Head-to-head on live s9.18 draft (14 players / 18 pairings):** GG
  random scheduler = 11 new/7 repeats by its own league-scoped count,
  truly 10/8 (missed Niester+Baker from the HCM portal). Tracker
  optimizer = 12 new / 6 repeats (the floor). Cross-portal
  customer_id-keyed history is the structural edge; GG's
  pair-frequency histogram is a readout worth replicating on the
  approval screen.
- **GG friction to eliminate:** per-round course/tee/times/shotgun
  re-entry after pairing — data the Tracker already holds.

## Match Play constraint — BUILT v2.100.0 (task #25, rule 8 amendment)

**Detection** (`detect_match_play_pairings(event_id)` in database.py;
bridge `scoring-pairings:mp|<event_id>`; API `GET /api/events/<id>/
pairings/matchplay`, manager): season = event year, chapter = event
chapter. Phase rule: ANY `cmp_bracket` rows for season+chapter = pool
play is over → pending matchups only (slot pairs 2i/2i+1 with both
players placed, no winner, both rostered). Otherwise pool phase: every
pool-mate pair on the roster with **no PLAYED cmp_matches row** — a
scheduled-but-unplayed row and a never-created row both count (rows are
only created when a result/schedule is saved, so row-existence alone
would miss most pending matches). Roster membership by customer_id
first, `_pair_key_name` fallback.

**Manager confirm gate** (events.html PAIRINGS tab): first Generate
click fetches detection; if matches exist an orange MATCH PLAY DETECTED
panel lists each one (pool name / round label) with a checkbox
(default confirmed) — "Generate with Matches" proceeds; unchecking =
"not required this event", constraint drops. A `⚔ Match Play: n/N`
chip reopens the panel; choices persist for the session.

**Generator** (`generate_event_pairings(..., mp_pairs=[[a,b],...])`):
confirmed opponents form unsplittable `fixed_units` placed before
partner pairing ("Match Play is king"); overlapping pool matches merge
into one unit up to a foursome. Composition never packs a partner PAIR
into an MP foursome — MP opponents take one seat in EACH cart, so the
leftover seats are split across carts and a pair there could never
ride together; pairs go to other groups instead. A partner request
pointing INTO a match unit attaches to that foursome when there's room
(rider joins the requester's cart). Seat order for constrained groups
is exact (≤4! permutations): MP opponents OPPOSITE carts (weight 1000,
seats 1/2 vs 3/4) > partner pairs SAME cart (100) > same-tee cart-
mates (1). Side effect fix: partner pairs now share a cart everywhere
(pre-v2.100 "adjacent" could straddle seats 2/3 = two carts). Seed
locks beat matches (rule 5); everything undoable is reported in
`mp_notes`, surfaced under the controls bar. ABCD mode ignores
mp_pairs (noted). Constrained players carry `mp_opponent` in the
response; `GET /pairings` returns `mp_matches` so SAVED pairings badge
too — orange `⚔ MP` chip, tooltip names the opponent.

**Tests**: `test_mp_pairings.py` (22 checks — both phases, roster
filtering, opposite-cart, request-around-match, decline, knockout
labels, decided-match exclusion).

## Pace-of-play STAGING project (Kerry, 2026-07-14 — task #23)

Per-player pace ratings (manager-tagged v1; later derived from
GPS/score-entry timing) → group pace = aggregate → STAGING ordered by
group pace (shotgun hole assignments / tee-time order). **HARD RULE:
pace never dictates pairing composition — staging only.** Pipeline:
compose → stage → approve. pace_rating storage must be
customer_id-keyed (rule 6); the staging ordering rule ships as
editable data (principle 2). Spec relay: mailbox #165.

### Ratings v1 — SEEDED (Kerry-ratified 2026-07-14, v2.99.2)

Scale **1 = slowest → 3 = fastest**, stored on
`customers.pace_rating` (INTEGER) with `pace_rating_source` TEXT
(`'manager'` for ratified/manual values; `'derived'`/`'gps'` reserved).
**NULL reads as 2 everywhere** — Kerry: "Anyone else that isn't
marked/discussed, gets a 2 in the system until further notice." Boot
seed `_seed_pace_ratings()` (database.py, init_db) is
**fill-only-if-NULL**: any manager edit wins over the seed forever.
Read back: `scoring-pairings:pace|` bridge.

Ratified values (derived from staging history, then Kerry-adjusted —
Parch/Miller/Dealy back to 2, Ellis flipped to 3, Dyal/Newman promoted,
DelCarmen 1):

- **3**: Jeff Young, John White, Chuck Fehlis, Fred Wicker, Steve
  Kulawik, Pat Youngs, Gus Vasquez, Rob Callaway, Gilbert Ellis, Mark
  Dyal, Tom Newman, Kerry Niester + Austin exceptions Jay Hogue, Neal
  Cloer, Robert Straiton (all other Austin members stay 2 until Robert
  reviews).
- **1**: Richard Palacios, Larry Anthis, Allen Wolin, Victor Arias III
  + Victor Arias Jr (they always ride/stage together; Kerry said
  "Victor Arias" — both seeded, flag for adjustment if only one),
  Roberto Moreno, Michael Murphy, Michelle Delcarmen.

### Editor + staging engine — BUILT v2.101.0

**One-tap editor** (Customers page, manager tier): PACE column on the
list view + inline control on mobile cards — a 1|2|3 segmented tap.
NULL renders as the gray "implied" 2; a tap always writes an EXPLICIT
value with `pace_rating_source='manager'` (no clear option — the boot
seed is fill-only-if-NULL, so clearing a seeded player would resurrect
the seed on the next deploy). `POST /api/customers/<id>/pace`
(`set_customer_pace_rating`); `/api/customers` carries
pace_rating/source.

**Staging engine** (inside `generate_event_pairings`, after
composition is settled): groups are ordered by aggregate pace =
average member rating (unrated = 2; lookup joins customers via
items.customer_id — rule 6, suffix-proof). Sequential tee times: fast
groups FIRST. Shotgun: fast groups at the FRONT of the hole train =
HIGHER hole numbers = later sheet slots (slowest at 1A). **AMENDED
(Kerry 2026-07-21, The Quarry, v2.131.0–.1): group SIZE beats pace.**
Tee times: short groups take the EARLIEST times. Shotgun: short
groups take the furthest-out loaded hole's **A** slot, then its **B**
slot, then the **A** slot one hole back (4A → 4B → 3A — Kerry's
clarified order; `_stage_shotgun_smalls_lead`), fastest/smallest
short group furthest forward; foursomes fill the remaining slots in
the SAME true play order (hole DESC, **A before B** — the A group
tees off ahead of the B group on a shared hole; v2.135.2 fixed the
sheet-order fill that put a fast foursome at 12B behind a slower
12A) fastest-first, slowest at the back (lowest hole's B). And
never more than three 3-somes within a 9-hole or 18-hole grouping —
`_make_group_sizes` guarantees it (worst case n ≡ 1 mod 4 →
[4, …, 3, 3, 3]). Rules-as-data: `smalls_lead: true` in
`PAIRING_STAGING_DEFAULTS` / `pairing_staging_rules` (set false to
restore pure pace ordering).
**Pace-tie tiebreak (Kerry 2026-07-28, v2.149.15): groups tied on
pace average order by LOWER TOTAL handicap index first** — the better
foursome goes out ahead (applies within each size class, both start
types; a player with no stored index counts 20.0 so unknowns never
jump the queue). Rules-as-data: `pace_tie_break: "low_total_hcp"`
(set `"none"` to disable).
Seeded groups stay where the manager put them (rule 5). Composition
is NEVER affected — proven by test_pace_staging.py (46 checks). The
rule is data: `PAIRING_STAGING_DEFAULTS` overridable via the
`pairing_staging_rules` app_settings JSON (enabled / shotgun /
tee_times / aggregate / default_rating / smalls_lead). Each
generated group carries `group_pace`, rendered as a ⏱ chip on the
PAIRINGS group headers. **v2.133.0 (Kerry 2026-07-21):** every player
line (seated + unassigned) carries a per-player ⏱1/2/3 badge (green
3 / gray 2 / amber 1; unrated = dimmed implied 2), fed by
`pace_rating` on GET /pairings `event_players`; and the group chip is
computed CLIENT-side from current membership (`groupPaceOf`), so
swaps/moves update it live and saved-pairings views show it too
(`group_pace` from the generator is now just the fallback).

Next (pace v2, parked): derive ratings from GPS/score-entry timing.

## Cart seating + Front/Back nine (Kerry 2026-07-21, v2.131.0)

The Quarry-night rulings, all built:

1. **Short groups beat pace in staging** — see the staging amendment
   above (`smalls_lead`): earliest tee times / furthest-out hole
   A → B → next hole back A on shotguns; max three 3-somes per
   grouping.
2. **Same-tee cart mates unless requests supersede.** After foursomes
   are decided, EVERY group runs the exact seat arranger
   (`_arrange_group_seats`, ≤24 permutations): Match Play opponents in
   OPPOSITE carts (weight 1000) > partner-request pairs in the SAME
   cart (100) > same-tee players share a cart (1). Tee comparison is
   case/whitespace-normalized. The old sort-by-tee path for
   unconstrained groups (`_order_group_by_tee`) is retired — it could
   split a tee pair across carts whenever a third tee was present.
3a. **Signup-order request priority (v2.134.0, Kerry same day).**
   Rules 1 + 11 sharpened: requests are honored FIRST-COME. The
   generator sorts the roster by `_request_time_key` (order_date →
   created_at → item id) before building `partner_map`, and every
   consumer of that dict iterates insertion order — so the earliest
   request wins any 3/4-person cross-request, and once a player is
   claimed in EITHER direction all later requests touching them
   (including their own later request) drop. The requests list runs
   the same simulation: entries return in signup order with
   `order_date`, `locked_out`, and `locked_reason`; the panel shows
   #priority numbers and a red OUTRANKED badge. The override is
   manager suppression of the earlier request, which promotes the
   next request in line. (Caveat of record: the list simulates locks
   across the whole roster while the generator matches within a
   holes bucket — on 9/18 combo events a cross-bucket request shows
   as matched here but is unenforceable in the generator.)
3a'. **Manual request matching (v2.134.0, Kerry same day).** Signup
   text that doesn't auto-resolve ('Dave Decareaux' vs roster 'David
   Decareaux') is fixable: the requests panel's 'no roster match'
   chip is a roster picker; the binding lands in
   `pairing_request_matches` (event_id + requester/partner names +
   customer ids, UNIQUE per requester, lazy-created). The generator
   substitutes the bound EXACT roster name for the raw text before
   pairing logic runs (`set_partner_request_match` /
   POST `…/pairings/requests/match`; partner=null clears). A manual
   match only holds while the bound player is still rostered — if
   they withdraw, the row falls back to unmatched. Rows show a
   ✎ manual badge (click to clear). **Multi-name texts (v2.135.0):**
   when the request text contains 2+ rostered names, the row carries
   `multi: true` + `candidates` and the panel shows an amber
   "N names — link one…" picker — one partner honored (rule 1), the
   manager links which; auto-match's first hit stands until then;
   extras are honored via manual moves after Generate (Kerry's
   ruling).
3b. **Request visibility + manager suppression (v2.132.0, same day).**
   The PAIRINGS controls bar's Requests chip opens the full request
   list — who asked for whom (`get_event_partner_requests`, same
   `_find_partner_name` matching the generator uses; unmatched raw
   text shown too). **Remove suppresses the request before Generate**:
   a `pairing_request_suppressions` row (event_id + requester_name +
   requester_customer_id, created lazily in
   `_ensure_pairing_tables`) makes `generate_event_pairings` blank
   that requester's partner_request before any pairing logic runs.
   The row stays listed, badged SUPPRESSED, until restored
   (`set_partner_request_suppression`). Suppression is per REQUESTER —
   mutual requests are two rows, two toggles. API: GET
   `/api/events/<id>/pairings/requests`, POST `…/requests/suppress`
   {requester, suppressed}; the list also rides on GET `/pairings`
   so the chip needs no extra round trip.
3c. **Request-name resolution runs on customer_id (v2.153.0, Kerry
   2026-07-30: "why not just reference actual aliases in customer_id
   profiles?").** `_find_partner_name` is a ladder, safest rung first:
   (1) exact full name; (2) **customer_id identity** — the request text
   AND each rostered player are resolved to a customer_id via
   `_partner_identity_map` (canonical profile name + every
   `customer_aliases` name row carrying that id, cached 300s), and a
   match means the SAME id; (3) nickname person key (surname + first
   initial — the Dan/Daniel, Matt/Matthew class, for players with no
   alias on file); (4) substring. Every rung requires a UNIQUE hit, so
   ambiguity yields "no roster match — fix" and a dropdown rather than
   a wrong pairing. `get_event_partner_requests` passes the roster's
   own `customer_id`s (`roster_ids=`), which are authoritative for the
   roster side — an alias pointing at a different id BLOCKS the match
   instead of making it. Names two real customers answer to are dropped
   from the index rather than pointed at a guess (same stance as
   `_lookup_customer_id`). Guiding principle 6: two names are the same
   person because they resolve to the same `customer_id`, never because
   the strings look alike. Exception, deliberate: initial-CHANGING
   nicknames (Dick/Richard, Bill/William) do not auto-resolve — a
   profile alias is the mechanism for that class.
3d. **Three request rules from the SA Championship field (v2.152.7 /
   v2.153.0, Kerry 2026-07-30):**
   - **Reciprocal = CONFIRMED, not OUTRANKED.** "Chuck Fehlis → Gus
     Vasquez" landing after "Gus Vasquez → Chuck Fehlis" is the same
     pairing restated. `locked_pair` tracks which pair claimed each
     player; a later request whose pair matches gets `status:
     "confirmed"` and a green badge. Badging it a loser read as a
     denial.
   - **Paying for someone implies the pairing.** Assign Guest stamps
     the item `"Purchased by <buyer>"`, so a bought-for player gets an
     IMPLIED request pointed at their host even when they wrote none
     (`implied: true`, PAID FOR badge). It enters at the guest's signup
     position, so priority order is unchanged.
   - **A host plus up to three guests is one approved foursome.** "A
     member can bring as many guests as they want and play with up to
     3" — same-host-group requests are CONFIRMED until the group hits
     `HOST_GROUP_MAX = 4`; the fourth guest is outranked with "a
     foursome is full", not silently dropped.
3e. **Managers can ADD a request (v2.153.0, Kerry 2026-07-30).**
   Requests arrive by text and at the first tee. The requests panel's
   "Add a request" row offers players with no existing request and
   writes through the same `set_partner_request_match` path; the entry
   surfaces at that player's SIGNUP position (`added: true`, ADDED
   badge) so it takes its honest place in the priority order rather
   than jumping the queue for being entered late. A requester who
   isn't on the roster is refused.
4. **Front/Back 9 side.** `events.nine_side` ('Front' default |
   'Back') says which nine the 9-hole leg plays. Shotgun slot labels
   follow (`_pairing_time_slots`: Back → 10A/10B…). Event setup (add +
   edit modals) has a "9-Hole Side" segmented control, shown whenever
   the format has a 9-hole leg; the PAIRINGS tab controls bar has a
   ⛳ Front 9 / Back 9 toggle → `POST /api/events/<id>/pairings/
   switch-side` (`switch_event_pairings_side`), which flips the
   setting AND shifts any SAVED 9-hole shotgun labels (1A ↔ 10A …) so
   the tab and the printables (starter sheet / cart signs read saved
   labels) follow without a regenerate; unsaved client-side groups are
   remapped in the browser with the same rule. `nine_side` is also
   settable via PATCH /api/events, POST /api/events (create), and the
   `update_existing_event` MCP tool.

## Engine notes (design, not yet built)

- Season-coverage objective (rule 3) is the optimizer's primary term;
  all-time history is the tiebreak/novelty signal.
- Constraint order when they conflict: manager override (5) > match
  assignment (8) > request lock (1/11) > guest-inviter binding (4) >
  experienced-anchor (6) + ambassador-spread (7) > coverage
  maximization (3).  ← the match-over-request portion is now RATIFIED
  (Kerry 2026-07-14, rule 8 amendment: "Match Play is king", with a
  manager confirm gate per detected match); the rest of the order is
  still inferred — confirm with Kerry.
- Requests: one per person per event; mutual locking per rule 11;
  decline releases the lock.
