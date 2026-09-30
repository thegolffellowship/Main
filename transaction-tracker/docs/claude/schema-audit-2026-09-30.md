# Schema audit: redundant and denormalized data (2026-09-30)

Kerry, 2026-09-30 (CoS #1067-2): *"We need to find other situations like the
chapters text field in our schema. That's a problem. I thought we had rooted
all of that out, but that's a bad example with redundant data that dominoes
through things."*

**Read-only. Nothing was changed.** Kerry rules on each fix (rule 3b), in order
of blast radius. Counts are from production on 2026-09-30 (v2.522.51) via
`scoring-schema-audit:scan` and `scoring-schema-audit:chapter`
(`email_parser/schema_audit.py`). The scan covered 158 tables and raised 161
flags: 45 twins, 40 entity-text, 66 free enums, 10 money-as-text.

**How to read the counts.**
- *No match* means the text names nothing, even after a lower-case compare and
  the alias tables.
- *No id* means the text is filled but the sibling id column is empty.
- *Readers* are code sites that read the column, where I counted them.

## Compared with what was supposed to be fixed

The April 26 **Tracker → Platform Alignment Audit v1.0**
(OneDrive `7_Web & App Development/Phase_2_Specs/`) is built on
`TGF_Complete_Database_Schema_v3_0` and quotes it. Its §2.1 lists these gaps,
and all are **still open**:

| April §2.1 / §3.4 gap | Schema v3.0 shape | Today |
|---|---|---|
| Chapter as a text field | `org_units` table, `org_unit_id` FK | `customers.chapter` text; 12 other tables carry chapter text (A-4) |
| Credits on `items` (`credit_note`, `credit_amount`) | one `credits` table | still on `items` (and `credit_amount` is TEXT) |
| Side games as a parsed text field | `games`, `bundles`, `order_item_games` | the `games`/`bundles` tables exist (v2.475.0); purchases, contests and results still name games as text (A-5) |
| TEXT dollars (§3.4) | `DECIMAL(10,2)` everywhere | `items` money columns are TEXT on 2,060 rows (C) |

**I could not open Schema v3.0 itself.** It isn't in the OneDrive search
index; only documents that mention it are. The comparison above therefore
rests on the April audit's reading of it. The CrossRef Audit wasn't found
either. If the Chief of Staff has their paths, I'll read both and add a
column.

**Naming point for Kerry.** v3.0 calls a chapter an **org unit**
(`org_units.org_unit_id`). The home-chapter migration below keeps the
Tracker's existing `chapters` table (already FK'd from `events`, `items`,
`courses` and `customer_ambassadors`). Renaming it to match v3.0 is a
separate choice, best made at the Postgres move (#728).

## A. Entity stored as text, no id column (the chapter disease)

| # | table.column | duplicates | rows filled | no match | readers | proposed fix | size |
|---|---|---|---|---|---|---|---|
| A-1 | `acct_transactions.event_name` | `events` | 7,152 of 9,412 | **492** | P&L, reconciliation, allocations | add `event_id` FK; backfill from allocations/items/aliases; list the unmatched for the CFO | L |
| A-2 | `customers.chapter` | `chapters` | 590 of 768 (178 blank) | 0 | ~40 code sites (database.py 22, app.py 5, mcp_server 4, home_chapter 3, gg_history 2, customer_query 2, parser 1, brevo 1) | **#1064-2 migration below** | M |
| A-3 | `handicap_rounds.course_name` (+ `tee_name`) | `courses`, `course_tees` | 15,657 | **849** | handicap index, cards, differentials | add `course_id` + `tee_id` FKs; backfill; list the unmatched | M |
| A-4 | chapter text on `tgf_events` (12 no match), `acct_allocations` (3 no match), `season_contests`, `season_contest_removals`, `cmp_pools`, `cmp_bracket`, `event_mvps`, `gg_game_results`, `gg_history_events/portals/standings`, `leads`, `blind_draws`, `season_contest_config_snapshots` | `chapters` | 13 tables | 15 in all (mostly `TGF`, the neutral chapter) | standings, contests, blinds | `chapter_id` FK + backfill, one migration after A-2 | M |
| A-5 | game text: `season_contests.contest_type`, `season_contest_removals.contest_type`, `gg_game_results.game`, `gg_game_flights.game`, `event_flight_snapshot_members.game`, `se_game_handicaps.game` | `games` | 5 tables | (no resolver yet) | contests, flights, payouts | `game_id` FK to `games`; backfill by name map | M |
| A-6 | tee text: `items.tee_choice` (1,650), `event_pairings.tee_choice` (117), `se_players.tee` (70), `handicap_rounds.tee_name` (15,657) | `course_tees` / tee bands | 4 tables | (bands are labels, not tee rows) | pairings, starter sheet, scorecards | decide first: a player's *band* (<50 / 50-64 / 65+ / Forward) is its own small table; the tee *set* played is `course_tees` | M |
| A-7 | event names on overrides: `rsvp_overrides.event_name` (729), `rsvp_email_overrides.event_name` (86), `event_aliases.canonical_event_name` (125: alias name → name, no event id) | `events` | 3 tables | 0 | RSVP matching | `event_id` FK; `event_aliases` gains `event_id` | S |
| A-8 | `cmp_bracket.player_name`, `cmp_bracket.winner_name`, `cmp_matches.winner_name` | `customers` | 13 / 13 / 29 | (verify) | Match Play bracket | verify whether these tables carry a customer id under another name; if not, add `customer_id` (principle 6) | S |

**Scanner false positives, listed so nobody chases them:**
- `member_analytics.event` is an analytics event type.
- `action_items.category`, `games.category` and `tgf_payouts.category` are enums, not accounts.
- `events.course_cost_breakdown*` is JSON, not a money scalar.
- `pairing_history.player_b` pairs with `customer_b_id`, not `customer_a_id` as the scanner guessed; no gap there.

## B. The same fact twice (text beside its own id), rows where the id is missing

| # | table.column | id column | filled | **text but no id** | no match | note | size |
|---|---|---|---|---|---|---|---|
| B-1 | `godaddy_order_splits.event_name` | `event_id` | 7,301 | **802** | 802 | money rows; the CFO's "separate store" (#1052) | M |
| B-2 | `acct_allocations.event_name` | `event_id` | 1,501 | **200** | 200 | money rows | M |
| B-3 | `message_log.event_name` | `event_id` | 1,679 | **1,197** | 1,197 | older sends logged by name only | S |
| B-4 | `items.item_name` | `event_id` | 2,365 | **480** | 479 | many are memberships/contests (not events); needs a breakdown before a fix | S |
| B-5 | `acct_transactions.category` / `.account` | `account_id` | 7,547 / 7,501 | **7,465** | — | category is free text; the chart of accounts has ids (`acct_categories`) | L, with the CFO's CoA v2 (#1052) |
| B-6 | `expense_transactions.category` / `.account_name` | `account_id` | 1,073 / 362 | 125 / 209 | — | 71 distinct free-text categories | M, with CoA v2 |
| B-7 | `player_name` without `customer_id`: `gg_history_results` 5,480, `handicap_rounds` 1,713, `scoring_rounds` 1,284, `gg_history_standings` 1,075, `gg_game_results` 135, `acct_transactions.customer` 23, `rsvps` 16, `parse_warnings` 6, `gg_points_standings` 2, `event_pairings` 1, `gg_game_flights` 1, `handicap_player_links` 1 | `customer_id` | — | 9,737 in all | — | mostly historical guests from the GG archive; the live tables are small | M (identity backlog) |
| B-8 | `events.chapter` | `chapter_id` | 96 | 5 | 6 | the neutral `TGF` chapter has no row | S |

## C. Money stored as TEXT (the D10 inventory; hard gate (c), #731)

| table.column | rows | stored as TEXT |
|---|---|---|
| `items.item_price` | 2,365 | **2,060** |
| `items.total_amount` | 2,365 | **1,726** |
| `items.transaction_fees` | 2,365 | **1,693** |
| `items.coupon_amount` | 2,365 | 24 |
| `items.wd_credits` | 2,365 | 9 |
| `items.credit_amount` | 2,365 | 1 |
| `events.fellowship_spot` | 98 | 6 |

Fix: numeric columns plus a conversion migration. The inventory is now done, so
this waits only on the conversion ruling. Size M.

## D. Free-text status/type columns (no CHECK)

66 columns. Most are written only by code (perf, sources, page kinds) and are
low risk. The ones with real drift:
- `items.user_status`: `MEMBER`, `1st TIMER` **and** `1st Timer` (a case
  variant), `MANAGER`, `GUEST`, NULL (699). It is also a snapshot of
  `customers.current_player_status`, the same fact twice. Fix: read status from
  the customer (the resolvers already do); enum the snapshot.
- `pairing_history.source`: `gg_teesheet` (1,906) and `tee_sheet` (45) mean
  the same thing. Harmless to the pair counts (both count), but it's a variant.
- `items.state`: 77 empty strings beside 522 NULLs.
- `expense_transactions.category`: 71 distinct free-text values (see B-6).

## Proposed order (by blast radius; each a separate Kerry ruling)

1. **A-2 home chapter** (#1064-2): **APPROVED by Kerry (#1084) and built in v2.522.56** (migration 0005, backfill bridge, the one setter). 0 rows fail to resolve.
2. **Money rows keyed by event name** (A-1, B-1, B-2): `event_id` on
   `acct_transactions`, backfilled on `godaddy_order_splits` and
   `acct_allocations`, with the unmatched listed. This touches the CFO's audit
   and the weekend Board session (#1061-6), so it goes after that session,
   not before.
3. **Money as TEXT** (C): the conversion ruling for hard gate (c).
4. **Chapter text elsewhere** (A-4, B-8) in one migration once A-2 lands.
5. **Games** (A-5) and **tees** (A-6): the tee decision first.
6. **Identity backlog** (B-7, A-8).
7. **Enum hygiene** (D).

## Home-chapter migration (#1064-2): shape and dry run

**Dry run (production, read-only):**
- 768 customers: **590 resolve** to a `chapter_id` (San Antonio 297, Austin
  214, DFW 42, Houston 36, Hill Country 1). **178 are blank.** **0 fail to
  resolve.**
- `events.chapter` has 5 rows with text but no `chapter_id`.
- 12 members play most often in a chapter other than their home chapter. That
  is evidence only: CA #784 rules that home chapter is never derived from
  where someone plays.

**Shape (proposed, not applied):**
- `customers.home_chapter_id INTEGER REFERENCES chapters(chapter_id)`: one
  home chapter by id.
- `customer_chapter_history (id, customer_id, chapter_id, from_date, to_date,
  set_by, reason, created_at)`: a move closes the open row and opens a new
  one, never an overwrite.
- **Backfill:** `home_chapter_id` is copied from `customers.chapter` (the ruled
  source, CA #784), with one open history row per customer (`from_date` = first
  event played, else `created_at`; `set_by` = `backfill`). The 178 blanks
  stay NULL and are listed.
- `customers.chapter` stays, **read-only**, until its ~40 readers move to
  `home_chapter_id`; then it's dropped in its own migration.
- The ruled setter `home_chapter.set_home_chapter` (CA #784) becomes the only
  writer. It writes the id and the history row together.
- `customer_ambassadors (customer_id, chapter_id)` already fits.

**Chapter fields to add** (`chapter_id`, `name`, `short_code`, `timezone` and
`status` already exist):

| field | why |
|---|---|
| `city`, `state` | display, lead routing |
| `manager_customer_id` → customers | today the chapter manager is a dial; managers are people |
| `gg_portal_ids` (JSON) | the GG portals per chapter (the archive map) |
| `default_tee_band` | pairings and scorecard defaults |
| `sender_email` | the chapter's outgoing mailbox (recaps, event emails) |
| `launched_on` | history and participation series |

Migration file, portable SQL (#682), shipped outside any window. The full
text is in `scoring-schema-audit:chapter` → `proposed_migration`.
