# Database Schema

## Database Tables (40+)

`items`, `processed_emails`, `events`, `event_aliases`, `chapters`, `courses`, `course_aliases`,
`rsvps`, `rsvp_overrides`,
`rsvp_email_overrides`, `customers`, `customer_emails`, `customer_aliases`, `customer_roles`,
`roles`, `statuses`, `customer_statuses`,
`handicap_rounds`, `handicap_player_links`, `handicap_settings`,
`message_templates`, `message_log`, `feedback`, `parse_warnings`,
`season_contests`, `app_settings`, `action_items`,
`acct_allocations`, `acct_transactions`, `godaddy_order_splits`, `bank_statement_rows`,
`period_closings`, `bank_accounts`, `bank_deposits`, `reconciliation_matches`,
`expense_transactions`, `acct_keyword_rules`,
`coo_agents`, `coo_chat_sessions`, `coo_chat_messages`, `coo_manual_values`,
`agent_action_log`, `tgf_events`, `tgf_payouts`, `contractor_payouts`,
`event_pairings`, `pairing_history`,
`duplicate_merge_audit`, `duplicate_dismissed_pairs`,
`payout_templates`, `payout_template_versions`, `event_type_template_map`

Key tables not documented elsewhere in CLAUDE sub-docs:
- `chapters` — chapter dimension table. Five canonical entries: San Antonio, Austin, DFW, Houston, Hill Country (Hill Country added via `_migrate_canonicalize_chapters` after the original seed block early-returns once initialized). Maps to Platform `org_units`. FK from `items.chapter_id` and `events.chapter_id`. **Note:** `customers.chapter` is still a `VARCHAR(50)` text column — it does **not** have a `chapter_id` FK. Chapter selection on the Customers Info tab is constrained to canonical names via the UI, and `update_customer_info` writes the chapter string to both `items.chapter` (per-row) and `customers.chapter` (master). Adding `customers.chapter_id INTEGER REFERENCES chapters(chapter_id)` and phasing out the text column is deferred — see "Deferred / Known Concessions" below.
- `courses` — golf course directory with canonical names and chapter linkage (nullable — courses can serve multiple chapters). Maps to Platform `courses`. FK from `items.course_id` and `events.course_id`.
- `course_aliases` — spelling variants for courses (e.g., "shadow glen" → ShadowGlen, "la cantera" → La Cantera). Used during import to normalize free-text course names to canonical IDs.
- `customer_roles` — multi-role junction table (maps to Platform `user_types`). Roles: `golfer` (renamed from `member` in v2.x), `manager`, `admin`, `owner` (→ Platform `super_admin`), `course_contact`, `sponsor`, `vendor`. UNIQUE(customer_id, role_type). `granted_by` tracks who assigned the role. **Roles do not drive status** (v2.13.0) — see `customer_statuses`.
- `roles` — reference table for valid role names. Seeded at boot with the seven canonical roles. Used by Platform integrations and to validate role-write API calls.
- `statuses` — reference table for valid customer status values: `1st_timer`, `guest`, `member`, `member_plus`, `former`. Each row carries a `display_name` (`'1ST TIMER'`, `'GUEST'`, `'MEMBER'`, `'MEMBER+'`, `'FORMER'`).
- `customer_statuses` — append-only history table. One row per status change per customer. Current status = most recent row by `set_at DESC`. Columns: `customer_id` (FK to `customers`, ON DELETE CASCADE), `status_id` (FK to `statuses`), `set_at` (timestamp), `set_by` (FK to customers — who made the change), `notes` (free text). Indexed on `(customer_id, set_at DESC)`. The denormalized `customers.current_player_status` column is kept in sync as a snapshot for legacy reads, but `customer_statuses` is canonical. `email_parser/memberships.py` writes FORMER rows on lapse and MEMBER rows on renewal; the `set_customer_status` helper enforces idempotency (skips inserting a duplicate row when the customer is already at that status).
- `app_settings` — persistent key-value store (matrix data, feature flags)
- `season_contests` — contest enrollment tracking (NET/GROSS points race, city match play)
- `parse_warnings` — flagged items with potential parsing errors (open/dismissed/resolved)
- `acct_allocations` — per-player event cost breakdown (course, prizes, fees, operating margin, payment_method, acct_transaction_id). Covers GoDaddy orders AND non-GoDaddy items (Venmo, cash, credit transfers) via synthetic order_ids.
- `acct_transactions` — single source of truth flat ledger. Every financial event writes entry_type/category/amount/account/status. Flat entries link to items via item_id. Status transitions: active → reconciled (matched to bank), reversed, or **merged** (soft-deleted by Duplicate Detective; `merged_into_id` FK points at the surviving row).
- `duplicate_merge_audit` — one row per Duplicate Detective merge: surviving_txn_id, merged_txn_id, merge_reason, confidence_score, merged_at, merged_by, notes, reversible flag, reversed_at. Every merge is logged here; reverse is a 1-click operation from `/admin/duplicate-detective/audit`. See `docs/claude/duplicate-detective.md`.
- `duplicate_dismissed_pairs` — pairs Kerry has explicitly rejected as not a duplicate. UNIQUE(txn_a_id, txn_b_id) so re-running the detector does not resurface them.
- `bank_statement_rows` — legacy imported bank statement data (older reconciliation system)
- `bank_accounts` — bank/payment accounts: TGF Checking (checking), Venmo (venmo). Seeded at init.
- `bank_deposits` — imported bank statement rows with status (unmatched/partial/matched). Linked to bank_accounts. Deduped on account + date + amount + description.
- `reconciliation_matches` — links bank_deposits to acct_transactions with match_type (auto/manual) and confidence score. UNIQUE(bank_deposit_id, acct_transaction_id).
- `coo_agents` — AI agent definitions with system prompts (6 specialists)
- `coo_chat_sessions` / `coo_chat_messages` — persistent AI chat history
- `coo_manual_values` — manually entered financial values (account balances, debts)
- `tgf_events` — tournament events with purse totals. `events_id` FK bridges to the main `events` table (backfilled at startup by `_backfill_events_id_on_tgf_events()`).
- `tgf_payouts` — individual prize payouts linked to events via `event_id` and to customers via `customer_id` (no separate golfer table; identity is unified in `customers`)
- `contractor_payouts` — revenue-share payouts to chapter managers; `manager_customer_id` FK to `customers`, `chapter_id` FK to `chapters`, `event_id` FK to `events` (backfilled from `event_name`)
- `expense_transactions` — staging table for CC/bank alert emails; rows are created by the AI bookkeeper and require human approval. Approved rows are promoted to `acct_transactions` via `_sync_expense_ledger_entry` (sets `entry_type='expense'`). Linked back via `acct_transaction_id` FK.
- `acct_keyword_rules` — auto-categorization rules (`match_type='contains'`, `COLLATE NOCASE`). Created when an expense is approved with a category; used to pre-categorize future alerts from the same merchant before the AI bookkeeper runs.
- `event_pairings` — saved pairings per event: `event_id`, `holes`, `group_num`, `slot_label` (e.g. `1A`, `1B`, `2A`), `cart_pos` (1–4 within the foursome), `customer_id` / `item_id`. Created lazily on first pairing operation by `_ensure_pairing_tables()` so existing live deployments self-migrate.
- `pairing_history` — round-robin tracking: who played with whom, per event. Calendar-year window feeds the random-mode generator's history-aware weighting. Also created lazily by `_ensure_pairing_tables()`.
- `customer_memberships` — one row per membership term (year). Columns: `customer_id` FK, `started_at` / `expires_at` (DATE), `source` (`parsed` / `manual` / `renewal` / `backfill`), `source_item_id` FK → `items(id)`, `price_paid`, `notes`, the four notice-sent timestamps (`notice_30d_sent_at`, `notice_7d_sent_at`, `notice_dayof_sent_at`, `notice_lapsed_sent_at`), `confirmation_sent_at`, `roster_choice` (`keep`/`remove`/null), `roster_choice_at`, `roster_admin_notified_at`. Unique on `(customer_id, started_at)`. Created via `email_parser.memberships.ensure_membership_tables()` and backfilled at boot from every parsed `items` row whose `item_name LIKE '%membership%'`. See `docs/claude/customers.md → Membership renewal system`.

## Customer Identity — Tables with `customer_id`

The full identity system (lookup cascade, merge, vendor model) lives in
`docs/claude/customers.md`. The set of tables that carry a `customer_id`
column:

- `customers` — Master customer records with `customer_id`, name, phone, chapter, GHIN, status
- `customer_emails` — Multiple emails per customer (supports primary + Golf Genius flags); **canonical email source**
- `customer_aliases` — Name and email aliases linking variant names to canonical customers; `customer_id` FK backfilled at startup
- `items.customer_id` — FK linking transactions to the `customers` table
- `acct_transactions.customer_id` — FK linking ledger entries to `customers` (backfilled via 5-step cascade)
- `handicap_player_links.customer_id` — FK linking Golf Genius player rows to `customers`
- `rsvps.customer_id` — FK backfilled at startup
- `season_contests.customer_id` — FK backfilled at startup
- `handicap_rounds.customer_id` — FK backfilled at startup
- `godaddy_order_splits.customer_id` — FK backfilled at startup
- `parse_warnings.customer_id` — FK (Phase 2); backfilled by `_backfill_customer_id_on_parse_warnings` (by customer name) so the COO action-items banner can deep-link from a parse warning to the linked player
- `message_log.customer_id` — FK (Phase 2); backfilled by `_backfill_customer_id_on_message_log` (by recipient email + name) so a customer's full email history doesn't depend on fragile name/email string matching
- `rsvp_email_overrides.customer_id` — FK (Phase 2); backfilled by `_backfill_customer_id_on_rsvp_email_overrides` (by `player_email`) so overrides don't drift when a player changes their email
- `action_items.customer_id` — FK (Phase 2); backfilled by `_backfill_customer_id_on_action_items` (by `from_email` + `from_name`)
- `feedback.customer_id` — FK (Phase 2); column added but no backfill helper today (no submitter identity field exists yet); future submissions populate it directly

All Phase 2 ALTERs are wrapped in `try/except sqlite3.OperationalError` so re-running is a no-op on already-migrated DBs.

## Event ID FK System

All tables that reference events now have an `event_id INTEGER REFERENCES events(id)` column,
populated at startup by backfill functions that resolve via `events.item_name` then `event_aliases`:

| Table | String column | Backfill function |
|-------|--------------|-------------------|
| `items` | `item_name` | `_backfill_event_id_on_items()` — also resolves child rows via parent |
| `acct_allocations` | `event_name` | `_backfill_event_id_on_string_tables()` |
| `godaddy_order_splits` | `event_name` | `_backfill_event_id_on_string_tables()` |
| `rsvps` | `matched_event` | `_backfill_event_id_on_string_tables()` |
| `expense_transactions` | `event_name` | `_backfill_event_id_on_string_tables()` |
| `message_log` | `event_name` | `_backfill_event_id_on_string_tables()` |
| `contractor_payouts` | `event_name` | `_backfill_event_id_on_string_tables()` |
| `tgf_events` | (name match) | `_backfill_events_id_on_tgf_events()` — stored as `events_id` |

String name columns are kept as denormalized display caches. All joins should prefer `event_id`
where available. Backfills are idempotent (skip rows where `event_id IS NOT NULL`).

See `PROJECT.md → Technical Debt & Known Concessions` for SQLite FK limitations and
the full migration checklist for Supabase/PostgreSQL.

## Data-Hygiene Migrations (idempotent, run on every `init_db`)

These run from `init_db()` and are safe to re-run on every startup. Each only touches
rows that don't already match the canonical state.

| Function | What it does |
|----------|--------------|
| `_migrate_normalize_customer_name_case` | Converts customer first/last names that are entirely uppercase (e.g., `HORTON`) to proper case (`Horton`). Handles `Mc`/`Mac` prefixes, apostrophes (`O'Brien`), hyphens (`Smith-Jones`), and Roman-numeral suffixes (`II`, `III`, `IV`). After updating the customers master record, it propagates the new first/last/customer values to **every** matching `items` row (both the `customer` denormalized full name and the per-row `first_name` / `last_name` fields). A second pass re-syncs items rows whose `first_name`/`last_name` are still uppercase but whose linked customers row is already proper-cased. |
| `_migrate_autocorrect_player_status` | Reconciles `customers.current_player_status` against item history. Pass 1 — anyone with a `membership` item but flagged `first_timer` / `active_guest` / NULL → upgraded to `active_member`. Pass 2 — anyone still flagged `first_timer` who has more than one item → demoted to `active_guest`. Roles in `customer_roles` are intentionally not modified. |
| `_migrate_canonicalize_chapters` | Inserts `Hill Country` into `chapters` if missing (the original seed block early-returns once initialized, so a code-level addition wouldn't otherwise reach a live DB). Then remaps legacy chapter strings across `items.chapter`, `events.chapter`, and `customers.chapter`: `Cedar Park` → `Austin`, `Pflugerville` → `Austin`, `August` → `NULL`, `Yes_For_Both` → `NULL`. |
| `_migrate_rename_member_role_to_golfer` | Recreates `customer_roles` with a CHECK that lists `golfer` instead of `member`, copying existing rows with `role_type='member'` mapped to `'golfer'`. Detects whether the migration has already run by inspecting the stored `CREATE TABLE` SQL — idempotent. Wired ahead of `_migrate_seed_customer_roles` in the startup sequence. Player_status values (`MEMBER`, `MEMBER+`, etc.) and `membership` item names are unchanged. |
| `_migrate_create_status_tables` (v2.13.0) | Creates `roles`, `statuses`, `customer_statuses` if missing; seeds the seven role names and five status names; and backfills `customer_statuses` with one row per customer mapped from the existing `customers.current_player_status` snapshot. Idempotent — uses `INSERT OR IGNORE` for seeds and only inserts a `customer_statuses` row when the customer has zero history rows. After this migration runs, the canonical store of customer status is the history table; `current_player_status` is kept in sync as a denormalized snapshot. |
| ALTER TABLE `customers` ADD COLUMN `suffix TEXT` / `middle_name TEXT` (v2.13.0) | Idempotent column-adds at boot. The columns existed in the schema-creation SQL but were missing from the live Railway DB, causing a 500 on `/api/customers` after `get_all_customers()` started referencing them. The migration wraps each `ALTER TABLE` in a try/except that swallows "duplicate column name" so it's safe to re-run. |
| `_migrate_relabel_credit_pool_items` | Backfills descriptive `item_name` on credit-pool rows: `Excess credit — <event>` (from `apply_credit_to_rsvp`) and `Overpayment credit — <event>` (from `_post_overpayment_credit`). Idempotent — skips rows whose `item_name` already starts with the new prefix. |
| `_migrate_move_noncanonical_side_games_to_notes` | Items where `side_games` is non-empty and not in `(NET, GROSS, BOTH, NONE)` have the text appended to `notes` (with `' — '` separator if notes already had content), then `side_games` is cleared. Skips rows whose exact text is already in `notes`. Idempotent. |
| `capture_email_aliases_from_items` | Promotes every `items.customer_email` value differing from the linked customer's primary email into `customer_aliases` (alias_type='email'). Skips matches-primary, case-only variants, and already-aliased typos. |
| `_heal_items_identity_fields` (Phase 1B) | Flattens `items.customer_email` / `customer_phone` / `chapter` / `first_name` / `last_name` to match the linked `customers` / `customer_emails` record. Captures stale emails as aliases first; overwrites other fields silently. |
| `repair_orphan_pay_children` | Heals `+PAY` children whose parent is missing, `rsvp_only`, or `transferred`: re-points `parent_item_id` at an active sibling parent for the same customer + event when one exists, otherwise converts the child to a standalone `credited` item with a descriptive `credit_note`. |
| `backfill_missing_godaddy_orders` | Targeted, idempotent helper that finds every GoDaddy order whose items exist but lack an active `godaddy-order-{id}` `acct_transactions` row, then calls `_write_godaddy_order_entry` for each. Wired into the startup block unconditionally (replaces the old `if-empty` gate that meant any order whose post-save write failed stayed un-promoted forever). |

## `events` table — recent column additions

| Column | Type | Notes |
|---|---|---|
| `per_game_addon` | REAL | Per-event game add-on price for NET / GROSS / BOTH tiers. Defaults to $27 on the new "27 Holes" format. Plumbed through `create_event()`, `_validate_update_fields` allow-list, and `POST /api/events`. The server-side `_calc_event_pricing_breakdown` reads this when present; the client-side modal also picks it up. Existing 9-hole / 18-hole / Combo formats fall back to the old $16 / $30 constants. |
| `format` | TEXT | Now accepts `9 Holes`, `18 Holes`, `9/18 Combo`, **or `27 Holes`**. 27 Holes is treated as a single-day event using the same start-time / tee-sheet / 5-hour-duration rules as 18 Holes; pairings, default holes, and the side-games matrix all map 27 Holes to the 18-hole code path. **Combo detection bug fix:** `is_combo` was comparing `format.lower() == "combo"`, but the actual string is `"9/18 Combo"` — the equality check never matched. Use `"combo" in format.lower()` (or pre-canonicalize) in any new code. |
| `payout_template_version_id` | INTEGER FK → `payout_template_versions(id)` | Snapshots the template version this event uses for its GAMES tab. Nullable — events created before Payout Templates rolled out (or before any default template was seeded) fall back to the chapter-default 9-hole or 18-hole template at render time. **Once stamped, never auto-updated** — editing a template after this column is set has no effect on this event. Per-event override on the event detail page rewrites the column to a different version_id. See "Payout Templates" section below. |

## Payout Templates (v2.14.x — schema + v1 seed; UI in subsequent chunks)

DB-backed replacement for the static `25-SideGame-PrizeMatrix.xlsx` + auto-generated `static/js/games-matrix.js`. Five tables introduced (three core + a games catalog + a per-version games junction). The existing `app_settings.games_matrix_9` / `games_matrix_18` JSON keys remain temporarily as the seed source for v1 templates and will be retired once the cutover (Chunk 4) ships.

### `payout_templates`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `name` | TEXT NOT NULL UNIQUE | Human-readable: `"Standard 9-Hole"`, `"Major Championship 18"`, etc. |
| `holes` | INTEGER NOT NULL CHECK(holes IN (9, 18)) | 9 or 18 only. 27-Hole and 9/18 Combo events use the 18-hole template (mirrors the existing matrix mapping; the per-side combo enablement noted in PROJECT.md Future Considerations is a later enhancement). |
| `is_default` | INTEGER NOT NULL DEFAULT 0 | At most one default per `holes` value, enforced by the partial unique index `idx_payout_templates_default ON payout_templates(holes) WHERE is_default = 1 AND archived = 0`. |
| `current_version_id` | INTEGER FK → `payout_template_versions(id)` | Points at the active version. Updated on every save. Reads should join to this for "current" template state. |
| `notes`, `created_at`, `created_by`, `archived` | | Standard metadata. `archived = 1` hides from list views and frees the default slot for that `holes` value. |

### `payout_template_versions`

Append-only — every save creates a new row. Never UPDATE in place; never DELETE (rollback creates a *new* version with the older payload).

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `template_id` | INTEGER NOT NULL FK → `payout_templates(id)` | |
| `version_no` | INTEGER NOT NULL | 1, 2, 3, … per template. UNIQUE per `(template_id, version_no)`. |
| `rates_json` | TEXT NOT NULL | **DEPRECATED as of chunk 1.5 (v2.14.4).** The simple `$/player` per game. Shape: `{ "team": 4, "ctp": 1, "hole_in_one": 1, "individual_net": 9, "city_mvp": 2, "tgf_mvp": 2, "skins": 9, "individual_gross": 4 }`. Replaced by per-game rows in `payout_template_version_games` (`buy_in` + `source`). New versions can write `'{}'`; existing rows keep the populated payload until Chunk 4 cutover removes the column. |
| `rules_json` | TEXT NOT NULL | The harder business logic: per-game flight thresholds, place splits, min-players, overflow targets (e.g. `individual_gross.overflow_to = "skins"` when below threshold). The rules engine is the read-side that turns rates+rules into the computed matrix. See PROJECT.md "Future Considerations → Side Games" for the rule-shape requirements (flexibility + game-to-game dependencies). |
| `computed_matrix_json` | TEXT NOT NULL | The expanded "matrix by player count" — the same shape `static/js/games-matrix.js` exports today. Recomputed and persisted on every save so reads (the GAMES tab) are O(1) lookups, not O(rules-engine-eval). |
| `max_players` | INTEGER NOT NULL DEFAULT 64 | Ceiling for the expanded matrix. 9-hole templates default to 64; 18-hole templates can be raised (128+) when player counts grow. Editable in admin UI. |
| `saved_at`, `saved_by`, `notes` | | Audit fields. `notes` holds a free-text reason for the change shown in the History view. |

### `event_type_template_map`

Maps an event's `event_type` (and `holes`) to its default template. Used at event creation to auto-stamp `events.payout_template_version_id`. UNIQUE on `(event_type, holes)`.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `event_type` | TEXT NOT NULL | Matches `events.event_type` (today defaults to `'event'`; future values per Future Considerations). |
| `holes` | INTEGER NOT NULL CHECK(holes IN (9, 18)) | Two rows per event_type — one for 9-hole, one for 18-hole — so the same event type can have different templates per hole count. |
| `template_id` | INTEGER NOT NULL FK → `payout_templates(id)` | |
| `created_at` | | |

### `games`

Canonical games catalog. One row per side game the system knows about. Codes are stable identifiers used by the rules engine and any cross-table joins; names are admin-/manager-facing. Categories group the game into one of three buy-in pots and mirror what `payout_template_version_games.source` carries.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `code` | TEXT NOT NULL UNIQUE | `'team_net'`, `'ctp_1'`, `'individual_net'`, etc. Stable across templates and versions. |
| `name` | TEXT NOT NULL UNIQUE | Display name: `'Team Net'`, `'CTP #1'`, `'Individual Net'`, etc. |
| `category` | TEXT | Buy-in pot grouping: `'event'` / `'net'` / `'gross'`. |
| `sort_order` | INTEGER NOT NULL DEFAULT 0 | Default render order. |
| `archived` | INTEGER NOT NULL DEFAULT 0 | Hides from new template editors without breaking old templates that reference the row. |
| `notes`, `created_at` | | |

Seed = 11 canonical games matching the live matrix: `team_net`, `ctp_1`, `ctp_2`, `ctp_3`, `ctp_4`, `hole_in_one`, `individual_net`, `city_mvp`, `tgf_mvp`, `skins`, `individual_gross`. Inserted via `INSERT OR IGNORE` so re-running `init_db` is a no-op.

### `payout_template_version_games`

One row per game included in a given template version. Replaces the simple key→amount shape of `rates_json` with normalized rows so games can be added, removed, reordered, and re-rated without touching a JSON blob — the same data shape that ports cleanly to the future Platform backend.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `template_version_id` | INTEGER NOT NULL FK → `payout_template_versions(id)` ON DELETE CASCADE | Junction key. Cascade delete because a version's game list dies with the version. |
| `game_id` | INTEGER NOT NULL FK → `games(id)` | Catalog reference. |
| `buy_in` | REAL NOT NULL DEFAULT 0 | `$/player` charged for this game in this template version. Replaces the corresponding `rates_json` key. |
| `source` | TEXT | Buy-in pot: `'event'` / `'net'` / `'gross'`. Denormalized from `games.category` so a per-template override (moving a game between pots for one template only) doesn't have to mutate the catalog. |
| `display_order` | INTEGER NOT NULL DEFAULT 0 | Ordering within the template's game list. |
| `rules_json` | TEXT | Per-game rule overrides (overflow target, min-players, flight thresholds). Distinct from the template-wide `payout_template_versions.rules_json` which holds cross-game logic. |
| `created_at` | | |
| **UNIQUE** `(template_version_id, game_id)` | | A game appears at most once per version. |

Seeded for v1 by `_seed_payout_templates_v1`: 9-Hole template gets 9 games (drops `ctp_3`, `ctp_4`); 18-Hole template gets all 11. Buy-ins seeded from the legacy rates-json shape (`team=4`, `ctp=1`, `hole_in_one=1`, `individual_net=9`, `city_mvp=2`, `tgf_mvp=2`, `skins=9`, `individual_gross=4`).

### v1 seed (Chunk 2 — v2.14.4)

`_seed_payout_templates_v1` runs at the bottom of `init_db` after the games / junction tables are created. It seeds:

- 11 canonical games into `games` (idempotent on UNIQUE `code`).
- Two templates into `payout_templates`: **Standard 9-Hole** (`max_players=64`) and **Standard 18-Hole** (`max_players=128`), both `is_default=1` for their `holes` value.
- One v1 row each into `payout_template_versions`. `computed_matrix_json` is the full live matrix (loaded from `app_settings.games_matrix_9/18` if present, else parsed out of `static/js/games-matrix.js`); `rates_json` is the legacy shape (kept for back-compat, deprecated); `rules_json` is `'{}'` (rule extraction lands in a later chunk).
- `payout_template_version_games` rows for every game in each template's manifest, using `_DEFAULT_BUY_INS` for `buy_in` and `games.category` for `source`.

Seed is idempotent across all four tables. `payout_templates.current_version_id` is set to the v1 id after every run (a no-op once stamped).

### Important constraints to know about

- **`init_db` requires `conn.commit()` after the new tables** — `_connect()` (alias for `managed_connection`) does **not** autocommit. CREATE TABLE statements added after the last explicit commit (line 4134) are rolled back on connection close. The Payout Templates block at the bottom of `init_db` ends with an explicit `conn.commit()`, then `_seed_payout_templates_v1` runs (it commits internally). The existing `event_pairings` / `pairing_history` blocks just above also lack a commit, but they're self-healed by `_ensure_pairing_tables()` on demand. If anyone adds further tables at the bottom of `init_db`, they need their own commit.
- **Snapshot semantics on `events.payout_template_version_id`** — never overwrite this without explicit user action (per-event override). Auto-stamp at event create only. Editing a template version is a forward-only operation that creates a new version_id; existing events stay pointed at the version they were stamped with.
- **Read path for "the current matrix for this event"** — join `events → payout_template_versions ON events.payout_template_version_id`. If null, look up `event_type_template_map(event_type, holes) → payout_templates → current_version_id`. If still null, fall back to `app_settings.games_matrix_9` or `static/js/games-matrix.js` (legacy). The fallback path is removed once Chunk 4 cutover is verified.
- **Read path for "what games does this template version include?"** — join `payout_template_version_games → games ON game_id` ordered by `display_order`. The legacy `rates_json` blob is deprecated but still populated on existing rows; new readers should always go through the junction.

## `items` cross-uid dedup gate

`save_items()` rejects a row whose `(order_id, item_index)` already exists under a
different `email_uid` for a real (non-manual) order — Microsoft Graph occasionally
re-keys an already-imported email under a brand-new message id (folder rebuild, mass
reply, PWA resync). The existing `UNIQUE(email_uid, item_index)` constraint stays in
place. Without this gate the same orders re-parsed and inserted as identical sibling
rows under the buyer's name (the May 3 phantom-duplicates incident).

`/api/audit/emails` similarly falls back to an `order_id` lookup when the `email_uid`
lookup misses (re-keyed emails would otherwise falsely report as "Not Parsed").

`POST /api/audit/delete-phantom-duplicates` (admin-only) is kept as a quiet safety net
but is no longer surfaced in the UI; it finds groups of items sharing
`(order_id, customer, item_name, item_price)` with `COUNT > 1`, keeps the lowest-id
(original) row, deletes each later duplicate. Skips any row with downstream refs
(`acct_allocations.item_id`, `acct_transactions.item_id`, `items.transferred_from_id`
/ `transferred_to_id` / `parent_item_id`). Supports `?dry_run=1` and
`?since=YYYY-MM-DD` (default `2026-04-26`).

## `acct_transactions.type` CHECK constraint

`acct_transactions.type` has a `CHECK (type IN ('income', 'expense', 'transfer'))`
constraint. `_sync_expense_ledger_entry` and `_promote_expense_to_ledger` map
`expense_transactions.transaction_type` → ledger `type` via:

```
{received → income, payout → expense, expense → expense, transfer → transfer}
```

Without the mapping, raw values like `"received"` or `"payout"` hit the constraint and
the ledger sync silently fails (the calling try/except logs and continues). The mapping
also matters for `entry_type`: `received` rows now write `entry_type='income'`
(previously hardcoded `'expense'`), which is what `get_event_reconciliation_status` and
the negative-deposit auto-match branch both require. A one-time idempotent backfill in
`init_db` flips already-promoted Venmo received rows from `entry_type='expense'` to
`'income'`.

## Deferred / Known Concessions

- **`customers.chapter` is `VARCHAR(50)` text, not an FK.** `items` and `events` got
  `chapter_id INTEGER REFERENCES chapters(chapter_id)` columns in an earlier session,
  but `customers` was never given a `chapter_id` column. The Info-tab chapter
  dropdown is locked to canonical chapter names from `/api/chapters`, and saves
  flow through `update_customer_info` which writes the chapter string to
  `customers.chapter` (and to `items.chapter` for that customer). Eventual cleanup
  path: add `customers.chapter_id INTEGER REFERENCES chapters(chapter_id)`,
  backfill from the existing text via name lookup, switch reads/writes to the
  FK, then drop the text column.
- **`require_role` decorator only enforces `"admin"`.** For any other requirement
  (`"manager"`, `"view-only"`), the decorator only checks that the user is
  authenticated. So `@require_role("manager")` in practice = "any authenticated
  user". Not exploitable today (only `admin` and `manager` logins exist), but if a
  view-only login is ever introduced, the decorator needs a true hierarchy check
  before extending its surface.
