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
- `chapters` — chapter dimension table (San Antonio, Austin, DFW, Houston). Maps to Platform `org_units`. FK from `items.chapter_id` and `events.chapter_id`.
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
