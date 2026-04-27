# Database Schema

## Database Tables (38+)

`items`, `processed_emails`, `events`, `event_aliases`, `chapters`, `courses`, `course_aliases`,
`rsvps`, `rsvp_overrides`,
`rsvp_email_overrides`, `customers`, `customer_emails`, `customer_aliases`, `customer_roles`,
`handicap_rounds`, `handicap_player_links`, `handicap_settings`,
`message_templates`, `message_log`, `feedback`, `parse_warnings`,
`season_contests`, `app_settings`, `action_items`,
`acct_allocations`, `acct_transactions`, `godaddy_order_splits`, `bank_statement_rows`,
`period_closings`, `bank_accounts`, `bank_deposits`, `reconciliation_matches`,
`expense_transactions`, `acct_keyword_rules`,
`coo_agents`, `coo_chat_sessions`, `coo_chat_messages`, `coo_manual_values`,
`agent_action_log`, `tgf_events`, `tgf_payouts`, `contractor_payouts`

Key tables not documented elsewhere in CLAUDE sub-docs:
- `chapters` — chapter dimension table. Five canonical entries: San Antonio, Austin, DFW, Houston, Hill Country (Hill Country added via `_migrate_canonicalize_chapters` after the original seed block early-returns once initialized). Maps to Platform `org_units`. FK from `items.chapter_id` and `events.chapter_id`. **Note:** `customers.chapter` is still a `VARCHAR(50)` text column — it does **not** have a `chapter_id` FK. Chapter selection on the Customers Info tab is constrained to canonical names via the UI, and `update_customer_info` writes the chapter string to both `items.chapter` (per-row) and `customers.chapter` (master). Adding `customers.chapter_id INTEGER REFERENCES chapters(chapter_id)` and phasing out the text column is deferred — see "Deferred / Known Concessions" below.
- `courses` — golf course directory with canonical names and chapter linkage (nullable — courses can serve multiple chapters). Maps to Platform `courses`. FK from `items.course_id` and `events.course_id`.
- `course_aliases` — spelling variants for courses (e.g., "shadow glen" → ShadowGlen, "la cantera" → La Cantera). Used during import to normalize free-text course names to canonical IDs.
- `customer_roles` — multi-role junction table (maps to Platform `user_types`). Roles: `member`, `manager`, `admin`, `owner` (→ Platform `super_admin`), `course_contact`, `sponsor`, `vendor`. UNIQUE(customer_id, role_type). `granted_by` tracks who assigned the role.
- `app_settings` — persistent key-value store (matrix data, feature flags)
- `season_contests` — contest enrollment tracking (NET/GROSS points race, city match play)
- `parse_warnings` — flagged items with potential parsing errors (open/dismissed/resolved)
- `acct_allocations` — per-player event cost breakdown (course, prizes, fees, operating margin, payment_method, acct_transaction_id). Covers GoDaddy orders AND non-GoDaddy items (Venmo, cash, credit transfers) via synthetic order_ids.
- `acct_transactions` — single source of truth flat ledger. Every financial event writes entry_type/category/amount/account/status. Flat entries link to items via item_id. Status transitions: active → reconciled (matched to bank) or reversed.
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
