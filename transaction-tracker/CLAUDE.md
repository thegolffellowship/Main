# Transaction Email Tracker — Claude Context

## Deployed URL

**Railway:** `https://tgf-tracker.up.railway.app`

## Inspection Endpoints

When the user asks about transaction data, extraction quality, or anything
about what's been parsed — query these live endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/stats` | High-level counts (total items, orders, spend, date range) |
| `GET /api/audit` | Data-quality report: field fill-rates, rows with missing fields, value distributions |
| `GET /api/data-snapshot?limit=50` | Most recent N items + stats for quick inspection |
| `GET /api/items` | Full dump of all items (can be large) |

### How to check data quality

```
WebFetch https://tgf-tracker.up.railway.app/api/audit
```

This returns:
- `fill_rates` — percentage of rows where each field is populated
- `problems` — list of rows missing critical fields (customer, order_id, item_name, etc.)
- `distributions` — value counts for chapter, course, user_status, tee_choice

### How to inspect recent data

```
WebFetch https://tgf-tracker.up.railway.app/api/data-snapshot?limit=20
```

### How to get full data

```
WebFetch https://tgf-tracker.up.railway.app/api/items
```

## Railway Persistent Volume (IMPORTANT)

SQLite data is lost on every redeploy unless stored on a persistent volume.

### Setup steps in Railway dashboard:
1. Go to your service → **Volumes** → **New Volume**
2. Set mount path: `/data`
3. Add environment variable: `DATABASE_PATH=/data/transactions.db`
4. Redeploy

This ensures the DB survives redeployments. Without this, every push wipes the data.

## MCP Server (Direct Data Access for Claude)

An MCP (Model Context Protocol) server at `mcp_server.py` gives Claude direct
read/write access to the transaction database — no WebFetch needed.

### Claude Code setup

The `.mcp.json` at the repo root auto-configures it. Just restart Claude Code
in this directory and you'll see the `tgf-transactions` server with 21 tools.

### Claude Desktop setup (remote — no local install)

The MCP endpoint is built into the Railway app at `/mcp/mcp`.
Add this to your `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "tgf-transactions": {
      "type": "streamable-http",
      "url": "https://tgf-tracker.up.railway.app/mcp/mcp"
    }
  }
}
```

No Python or local install needed — Claude Desktop connects directly to Railway.

### Available tools (31)

**Read:**
`get_transactions`, `get_transaction_by_id`, `get_statistics`,
`get_data_quality_report`, `get_recent_snapshot`, `list_events`,
`get_event_registrations`, `list_customers`, `get_customer_details`,
`search_transactions`

**Financial & Reconciliation:**
`get_event_financial_summary`, `get_acct_transactions`,
`get_bank_deposits`, `get_reconciliation_detail`,
`get_cashflow_summary`, `get_acct_allocations`,
`get_godaddy_order_splits`, `get_chart_of_accounts`,
`get_mcp_ledger_entries`, `get_venmo_transactions`

**Write:**
`update_transaction`, `credit_transaction`, `transfer_transaction`,
`undo_credit_or_transfer`, `create_new_event`, `update_existing_event`,
`delete_existing_event`, `add_player`, `delete_transaction`,
`sync_events`, `run_autofix`

## Handicap System — TGF Rules (IMPORTANT)

All handicap calculations are for **9-hole rounds only**. The differential
lookup counts match WHS Rule 5.2a. Adjustments per that rule are also applied.

### Handicap Differential Table (WHS Rule 5.2a)

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

### Calculation rules
- **Lookback window:** 12 months (configurable)
- **Pool:** most recent 20 rounds within the window
- **Multiplier:** avg of lowest N × 0.96
- **Rounding:** standard round-to-nearest-tenth per **WHS Rule 5.2** (2020-present):
  *"The result of the calculation is rounded to the nearest tenth."* (.5 rounds up)
  e.g. 6.282 → 6.3; 6.24 → 6.2; −0.228 → −0.2N (plus-handicapper, rounds toward +∞)
  NOTE: the pre-2020 USGA system used truncation — that rule no longer applies.
- **18-hole scores are rejected** at import time (course rating > 50 = error)
- **Handicap index suffix:** "N" indicates a 9-hole index
- **Plus handicap display:** negative computed value → shown with "+" prefix

### Expanded rounds view — INDEX column
The INDEX column shows the running handicap after each round was entered, computed using
**today's fixed lookback cutoff** (not a rolling per-round cutoff). This ensures the most
recent round's INDEX always matches the player's current displayed handicap. Older rounds
show what the handicap would have been including all rounds up to that point, with today's
12-month window applied.

### Expanded rounds view — cutoff lines
Two visual separator rows appear in the expanded rounds table:
- **Red line** — 12-month lookback boundary; rounds below are excluded from the pool
- **Green line** — 20-round pool boundary; rounds below are still active (within 12 months)
  but beyond the 20 most-recent that count toward the index. Only shown when a player
  has more than 20 active rounds.

### Admin controls
- **Import Rounds** button — visible to managers and admins
- **Purge 18-hole Scores** button — admin only; calls `POST /api/handicaps/purge-invalid`
  which deletes all rounds where `rating > 50` (catches any 18-hole scores that slipped in)
- **Settings** button — admin only; configure lookback window and minimum rounds
- Individual round **× delete** buttons — visible to managers and admins in the expanded view;
  there is no bulk "Delete All" for a player

### Auth notes
- Role is stored in the global `currentRole` variable (set by `auth.js`)
- Do **not** use `window._userRole` — that variable is never set

### Player ↔ Customer linking
- `handicap_player_links` table bridges Golf Genius player names to transaction customer names
- **Email-based matching** (highest priority): `_match_customer_by_email()` looks up email in `items.customer_email` and `customer_aliases` (alias_type='email')
- **Name-based matching** (fallback): `_match_customer_name()` tries: exact match, first+last, LIKE, aliases, reversed name, last-name-only (unique)
- Import supports `player_email` column — when present, email matching is tried first before name matching
- Both email and name columns support fill-down format (value on first row, blank on subsequent rows for same player)
- `/api/handicaps/players` auto-runs `relink_all_unlinked_players()` on each request
- Customers page also matches by `player_name` as fallback (not just `customer_name`)

### Key files
- `email_parser/database.py` — `_HANDICAP_DIFF_LOOKUP` (server-side table), `_match_customer_name()` (linking logic)
- `templates/handicaps.html` — `DIFF_LOOKUP` (client-side JS table, must match)
- Both tables must always be kept in sync.

## Customer Identity System

### Tables
- `customers` — Master customer records with `customer_id`, name, phone, chapter, GHIN, status
- `customer_emails` — Multiple emails per customer (supports primary + Golf Genius flags)
- `customer_aliases` — Name and email aliases linking variant names to canonical customers
- `items.customer_id` — FK linking transactions to the `customers` table
- `acct_transactions.customer_id` — FK linking ledger entries to `customers` (backfilled via 5-step cascade)
- `handicap_player_links.customer_id` — FK linking Golf Genius player rows to `customers`

### Customer Lookup Flow (`_lookup_customer_id` — 5-step cascade)
When a new transaction arrives, the system resolves the customer in this order:
1. **Email via `customer_emails`** — exact email match
2. **Alias email via `customer_aliases`** — alias_type='email' JOIN customers
3. **Exact first+last name** in `customers` table
4. **Alias name via `customer_aliases`** — alias_type='name' JOIN customers
5. **Fallback: `items.customer_email`** — checks existing items for pre-migration customers

### Customer Resolution (`_resolve_or_create_customer`)
- Calls `_lookup_customer_id` first
- If no match, creates a new `customers` row + `customer_emails` row
- On email IntegrityError (duplicate), returns the existing owner's customer_id instead of creating an orphan

### Customer Merge (`merge_customers`)
- Reassigns `items.customer` string (all transactions)
- Reassigns `items.customer_id` from source to target
- Moves `customer_emails` from source to target
- Creates name alias for old name
- Deletes orphaned source `customers` row

### Vendor Customers

Vendors (suppliers, payment processors, etc.) are stored in the `customers` table with
a `vendor` role in `customer_roles`.

**Key columns:**
- `company_name` VARCHAR(200) — single-name field for vendors/companies (migration-added).
  Display logic: `COALESCE(NULLIF(company_name,''), NULLIF(TRIM(first_name||' '||last_name),''))`.
  Backend stores vendor name in `company_name` + `last_name`; `first_name=''`.

**API endpoints:**
- `GET  /api/accounting/customers` — all customers, returns `display_name` (prefers company_name)
- `GET  /api/accounting/vendors` — customers with `vendor` role, returns `display_name`
- `POST /api/accounting/vendors` — create vendor; body: `{name}`. Creates customer row +
  assigns vendor role. Idempotent (adds role if customer already exists by name).

**Vendor typeahead in accounting modals:**
- All vendors shown at top of dropdown when field is focused (empty) — discoverable without typing
- Type to filter from all customers/vendors
- "＋ New Vendor" option always visible at bottom of dropdown; opens New Vendor modal
- After save, new vendor is immediately selected in the form
- Vendors appear with amber chip color (vs. green for non-vendor customers)
- Applies to: income/ledger modal (`#customer-id`), expense modal (`#exp-customer-id`)

### Customer Status and Role Editing (Info Tab)

Admins can edit a customer's **Member Status** and **Roles** from the Info tab
on any customer profile (all three rendering paths: inline expand, detail panel, mobile card).

**Member Status dropdown options:**
`1ST TIMER` / `GUEST` / `MEMBER` / `MEMBER+` / `FORMER`
- `member_plus` — new status (migration-adds to CHECK constraint); displayed as "MEMBER+"
- `expired_member` kept in DB for backward compat; displayed as "FORMER"

**Roles checkboxes:** `member`, `manager`, `admin`, `vendor`, `course_contact`, `sponsor`

**Save flow:**
1. `PATCH /api/customers/<id>` — updates `current_player_status` via `update_customer_info()`
2. `POST /api/customers/sync-roles` — `{customer_id, roles[]}` replaces all roles atomically

**API:**
- `GET  /api/customer-roles` — returns roles per customer + `_by_name` map (name→customer_id);
  frontend uses `_by_name` as fallback when `items.customer_id` is null (pre-identity items)
- `POST /api/customers/sync-roles` — `{customer_id, roles}` replaces full role set

## Architecture

- **Flask app** in `transaction-tracker/app.py` (~5900 lines, 200+ routes)
- **Email parsing** via Claude Sonnet in `email_parser/parser.py`
- **Email fetching** via Microsoft Graph API in `email_parser/fetcher.py` — only processes emails with "New Order" subject lines; all processed email UIDs tracked in `processed_emails` table to prevent re-parsing
- **SQLite DB** at `transaction-tracker/transactions.db` (local is empty; live data on Railway)
- **Database layer** in `email_parser/database.py` (~10000+ lines) — schema, CRUD, allocations, COO context
- **Scheduler** checks inbox every 15 minutes via APScheduler
- **Dashboard** at `/` with search, filter, sort, CSV export
- **COO AI** — Claude-powered business intelligence chat with 6 specialist agents
- **TGF Payouts** — tournament payout tracking with screenshot import via Claude Vision
- **Golf Genius sync** via direct HTTP requests in `golf_genius_sync.py` (rewritten from Playwright)
- **MCP Server** in `mcp_server.py` — 31 tools for Claude direct DB access
- **Auth** — PIN-based with roles: `admin`, `manager`, `view-only`; `@require_role()` decorator
- **`initAuth()`** must be called on every page for nav link visibility (DATABASE link, etc.)

## Transactions Page — Key Behaviors

### RSVP-only filtering
- Items with `transaction_status = "rsvp_only"` are filtered OUT of the Transactions tab
- They only appear in the Events tab (with amber background)
- Filter: `allItems = raw.filter(i => !PLACEHOLDER_MERCHANTS.includes(i.merchant) && i.transaction_status !== "rsvp_only")`

### Transaction deep-linking
- URL parameter `?txn=<item_id>` scrolls to and highlights a specific transaction row
- Used by Customers page click-to-navigate feature
- Auto-expands collapsed order groups if the target row is inside one
- Highlight uses yellow pulse animation (`txn-highlight` class)

### Order grouping
- Multi-item orders (same `order_id`) display as collapsible groups
- Summary row shows item count and total; expands to show individual items

## Customers Page — Key Behaviors

### Name display format
- All customer/player names display as **"Last, First"** across all pages
- `displayName()` helper converts "First Last" → "Last, First" with suffix handling
- Suffixes (Jr, Sr, II, III, IV, V) are preserved after the first name
- Example: "Victor Arias III" → "Arias, Victor III"
- The underlying data (`items.customer`) remains "First Last" — only display changes

### Name sorting
- `lastNameSortKey()` sorts by last name, stripping suffixes before comparison
- Used on all pages: Transactions, Events, Customers, Handicaps, RSVP Log
- "Victor Arias III" and "Victor Arias JR" sort together under "Arias"

### Merge customer modal
- Uses typeahead autocomplete input (not a dropdown)
- Type to search, click to select from suggestions
- Candidates sorted by last name with purchase counts

### "Purchased by" badge
- When `item.notes` contains "Purchased by X", a blue badge shows on the transaction row
- Indicates someone else paid for this player's registration

### Click-to-navigate
- Transaction rows in customer detail have `data-txn-id` and are clickable
- Clicking navigates to `/?txn=<id>` which deep-links to the Transactions tab

## Events Page — Player Status Architecture

### Transaction statuses
- `active` — normal registration, shown in main table
- `rsvp_only` — RSVP without payment, shown in main table (yellow background)
- `gg_rsvp` — Golf Genius RSVP, shown in main table (yellow background)
- `credited` — payment credited back, shown in **Inactive** section below table
- `refunded` — payment refunded, shown in **Inactive** section below table. Creates `acct_transactions` expense entry.
- `transferred` — transferred to another event, shown in **Inactive** section below table. Creates contra-revenue on source event + revenue on target event in `acct_transactions`, plus allocation at target.
- `wd` — withdrawn, shown in **Inactive** section below table

### Event detail view sections (top to bottom)
1. **Toggle bar** — PLAYERS | PAIRINGS | GAMES + 9|18 holes filter + NET | GROSS | NONE
2. **Registrations table** — only active/rsvp players (compact rows)
3. **Inactive section** — credited/refunded/transferred/WD players in a gray box with Reverse buttons
4. **Not Playing section** — GG RSVP players marked as not playing (red box)
5. **Message History** — collapsible section

### Columns in registrations table
Order: RSVP circle → Customer → HCP → Holes → Games → Tee → Status → Order → Price → Actions

### Status normalization
The `user_status` field is cleaned at display time via `_cleanStatus()`:
- Strips parenthetical notes like "($25 Off + FREE Drink)"
- Normalizes to: "1st TIMER", "MEMBER", "MEMBER+", "GUEST", or "MANAGER"

### Holes field
- Parsed from emails: "9 or 18 HOLES?" field → stored as `holes` TEXT column
- Shown as column in both Transactions and Events tables
- Mobile collapsed view: amber badge showing "9h" or "18h" (first of three badges: Holes, Games, Tees)
- 9|18 toggle filter in Events: filters registrants by hole count
- Can be backfilled via `/api/audit/re-extract-fields`

### Game stats computation (`computeGameStats`)
- Excludes credited/refunded/transferred players from counts
- WD players: complex logic based on which game components were credited
- RSVP-only players: counted in PLAYERS total but as NONE (no games)

### GUEST registration handling
- When a member buys two items (one for themselves, one for a guest), the parser's
  `_promote_guest_customers()` auto-swaps the GUEST item's customer to the actual
  guest name (from `guest_name` field) and adds a "Purchased by <buyer>" note
- **"Guest?" tag** — amber clickable tag on GUEST items in multi-item orders where
  the guest name is unknown. Only appears when: same buyer has a peer item in the
  same order AND no `guest_name` or `partner_request` is set
- **"Paid by" badge** — blue badge on GUEST items where guest-swap has already occurred
- **Assign guest endpoint**: `POST /api/items/:id/assign-guest` (manager+)
- Detection is conservative: standalone GUEST registrations (guest signed up themselves)
  are NOT flagged

### Add Payment
- Creates a child payment row linked to parent registration via `parent_item_id`
- Child rows excluded from player counts, shown as indented "+PAY" sub-rows
- Item types: NET Games, GROSS Games, BOTH Games, Event Upgrade (9→18 holes), Other
- **Event Upgrade** updates the parent item's `holes` to "18" but does NOT affect games
- Child payment `side_games` is empty for Event Upgrade (prevents false game merging)
- Player dropdown filters out child payment rows to avoid duplicates
- Supports event aliases (course changes) for parent lookup
- **Unified financial model:** creates `acct_allocations` row + `acct_transactions` entry
  for each add-on payment (allocation uses synthetic `order_id = MANUAL-PAY-{item_id}`)

### Clickable game switching
- GAMES column is clickable for active registrations with NET or GROSS games
- Click toggles between NET ↔ GROSS (no-cost swap only)
- BOTH and NONE are NOT clickable — those involve money changes
- Uses `PATCH /api/items/:id` (admin only) to update `side_games`

### Action Items banner
- Red notification banner on Transactions and Events pages for admin/manager
- Aggregates: parse warnings + GUEST items needing guest name assignment
- `GET /api/action-items` endpoint returns combined list
- Auto-expands on page load; items can be dismissed or acted on inline
- Parse warning dismiss/resolve accessible to managers (was admin-only)

### Per-order re-extract
- Audit page email cards have "Re-extract This Order" button
- Calls `POST /api/audit/reextract-order` with `{order_id: "R..."}`
- Re-fetches original email from Graph API, re-runs AI extraction
- Backfills missing fields AND applies guest-swap if parser detects GUEST items
- Also available via browser console for immediate use

### Event deletion / merge persistence
- **Merge** creates an alias (source → target) so sync skips the old name
- **Delete** now preserves the deleted name as an alias (→ `_DELETED_`) when
  items still reference it, preventing `sync_events_from_items()` from recreating
- `seed_events()` also checks aliases before inserting

### Event Cancellation / Postponement

Events can be cancelled or postponed from the event detail view (admin only).
New columns on `events` table: `status` TEXT (`active`/`cancelled`/`postponed`),
`status_reason` TEXT, `rescheduled_to_event_id` INTEGER, `status_changed_at` TEXT.

**Cancel Event modal — 4 steps:**
1. Choose `Cancelled` or `Postponed` + enter reason text (required).
2. Choose refund/credit mode: **Bulk** (Credit All / Refund All in one click) or **One-by-One**.
3. (One-by-One) Staging list with per-row Credit / Refund / Skip buttons → Apply All.
4. Completion summary + optional "Send Cancellation Email" prompt.

**Key behaviors:**
- Refund method auto-detected from original payment (`godaddy` → GoDaddy, `venmo` → Venmo, etc.)
- Add-on payments cascade automatically via existing `credit_item` / `refund_item` logic
- Comp and RSVP-only players are silently removed (no credit/refund needed)
- **Restore Event** button appears on cancelled/postponed events until the first player
  action is taken (`can_restore_event(conn, event_name)` checks for any credited/refunded items)
- Cancelled/postponed badges shown on the event list rows
- Status banner shown at top of event detail view

**API endpoints (all admin):**
- `POST /api/events/<name>/cancel` — `{status, reason}` → sets event status
- `POST /api/events/<name>/restore` — clears status back to active
- `GET  /api/events/<name>/cancellation-players` — list of active players with payment info
- `POST /api/events/<name>/cancel-bulk` — `{action: 'credit'|'refund', method?}` → bulk apply
- `POST /api/events/<name>/cancel-apply` — `{actions: [{item_id, action, method?}]}` → one-by-one apply

**Key DB functions:**
- `set_event_status(conn, event_name, status, reason)` — writes status + timestamp
- `can_restore_event(conn, event_name)` — returns True if no credited/refunded items yet
- `get_cancellation_players(conn, event_name)` — returns active players with payment method

### RSVP Credit Application (from Events page)

When an event is cancelled, players who had credits from that event and are now RSVPing
to a future event can have their credit applied directly from the RSVP row.

**How it works:**
- After RSVP inbox check, `_send_rsvp_credit_alerts()` auto-sends email alerts to players
  with outstanding credits who have RSVPed to an upcoming event.
- Green **Credit** badge appears on RSVP-only rows in the event detail view when the player
  has an outstanding credit (checked via `get_rsvp_credit_info`).
- **Apply Credit** button opens a modal showing: previous selections, event price table for
  their player type, amount owed (if price > credit) or excess credit (if credit > price),
  and disposition choice for excess (keep vs. Venmo note).
- On confirm, calls `apply_credit_to_rsvp(conn, rsvp_id, item_id, disposition)` which:
  - Creates the transferred registration item linking credit source → new event
  - Marks the credit item as used
  - Calculates and records any balance-due or excess
- `rsvps` table new column: `credit_notified_at` TEXT — tracks when the alert email was sent.

**Key DB functions:**
- `get_player_credits(conn, customer_id)` — player's outstanding credit items
- `get_rsvp_credit_info(conn, rsvp_id)` — credit info for a single RSVP row
- `get_event_rsvp_credit_map(conn, event_name)` — map of rsvp_id → credit info for all RSVPs in an event
- `apply_credit_to_rsvp(conn, rsvp_id, item_id, disposition)` — executes the credit transfer
- `mark_rsvp_credit_notified(conn, rsvp_id)` — records credit_notified_at timestamp

**GG RSVP synthetic row support:**
- `get_event_rsvp_credit_map` queries both `items` table rows AND unmatched `rsvps`
  table rows (GG RSVPs without a linked items row). Resolves canonical customer name
  via email lookup so name-keyed map matches frontend JS.
- `create_rsvp_only_item()` — promotes a GG RSVP to a real `items` row (idempotent
  via `email_uid`) before credit application runs.
- `GET  /api/rsvps/gg/<id>/credit-info` — credit-info for a synthetic GG RSVP row
- `POST /api/rsvps/gg/<id>/apply-credit` — apply credit to a synthetic GG RSVP row

**API endpoints:**
- `GET  /api/rsvps/<id>/credit-info` — credit info for a specific RSVP
- `GET  /api/events/<name>/rsvp-credits` — all RSVP credit info for an event
- `POST /api/rsvps/<id>/apply-credit` — `{item_id, disposition}` → apply credit

**Undo Credit Application:**
- `reverse_credit_application(conn, item_id)` — restores transferred source credits
  to `credited`, removes any excess credit item, reverses accounting entries, reverts
  target item to `rsvp_only` (or deletes if it was a promoted GG RSVP item).
- `POST /api/items/<id>/reverse-credit-application` (admin only)

### Apply Credit to Event from Customers Page

Credited items in customer detail views have an **Apply** button (alongside Reverse).
Clicking opens a modal to select an upcoming event, shows a price preview (credit vs. event
price, balance-due or excess handling), and applies the credit.

**API endpoints:**
- `GET  /api/items/<id>/apply-credit-info?event_name=<name>` — preview amount owed / excess
- `POST /api/items/<id>/apply-to-event` — `{event_name, disposition}` → apply credit

Uses idempotent uid `manual-credit-{credit_item_id}` to prevent double-apply.
All three rendering paths on the Customers page (inline expand, detail panel, mobile card) updated.

## Event Pricing Architecture

### Edit/Add Event Modal — Pricing Tab

The Pricing tab has a **compact layout** with collapsible calculators and live-updating pricing cards.

**For 9/18 Combo events:**
- Two side-by-side columns: "9-Hole Calculator" (green) and "18-Hole Calculator" (blue)
- Each column has: collapsible Course Cost Calculator, Markup ($), Inc. Games ($)
- "Event Cost" total at bottom of each card = `ceil(courseCost) + markup + incGames`
- Shared Transaction Fee (%) input below
- Side-by-side pricing summary with colored cards below

**Course Cost Calculator** (collapsible):
- Collapsed (default): header + green fees row only + rounded total in header
- Expanded: all 5 items (Green Fees, Cart Fees, Range Balls, Printing, Other)
- Header shows `Math.ceil(total)` (rounded-up course cost)
- Auto-expands if non-green-fees items have saved data

### Pricing Calculation Flow

```
roundedCC     = Math.ceil(courseCost)
eventCharge   = roundedCC + markup + incGames + gameAddon
actualCharge  = Math.ceil(eventCharge)       // whole dollar rounding
txFee         = round(actualCharge × txPct) / 100
playerTotal   = actualCharge + txFee
```

Key function: `calcPricingLine(cc, mu, sg, tf)` in `events.html`

### Player Type Markup Rules

The Markup ($) input = **Member** markup. Guest and 1st Timer are auto-derived:
- **Guest** = Member + $10 (9 Holes and 9/18 Combo) or + $15 (18 Holes standalone)
- **1st Timer** = Guest − $25 (can go negative as discount)
- Determined by `getPlayerMarkups(memberMarkup, format)` function
- For combo events: Guests/1st Timers can ONLY play 9-hole (18-hole shows N/A)

### Game Add-On Tiers

- **Event Only**: base price (includes Inc. Games fee)
- **With One Game (+$16)**: adds `PER_GAME_ADDON` ($16 constant)
- **With Both Games (+$32)**: adds `PER_GAME_ADDON × 2`
- Both Games = N/A for Guest and 1st Timer

### Pricing Summary Cards

Cards use `_priceCard()` function with `PLAYER_CARD_STYLES` colors:
- Member: green (#f0fdf4 bg, #16a34a border)
- Guest: blue (#eff6ff bg, #2563eb border)
- 1st Timer: gold (#fefce8 bg, #a16207 border)
- N/A: gray (#f3f4f6 bg, #d1d5db border)

Cards display the **event charge** (whole dollars, before tx fee).

### Field Name Mapping

| UI Label | DB Field | Notes |
|----------|----------|-------|
| Markup ($) | `tgf_markup` / `tgf_markup_9` / `tgf_markup_18` | Member rate |
| Inc. Games ($) | `side_game_fee` / `side_game_fee_9` / `side_game_fee_18` | Included games admin fee |
| Transaction Fee (%) | `transaction_fee_pct` | Default 3.5% |
| Course Cost | `course_cost` / `course_cost_9` / `course_cost_18` | From calculator |
| Course Cost Breakdown | `course_cost_breakdown` / `_9` / `_18` | JSON of 5 line items |

## Side Games Matrix

### Persistence
- Matrix data is stored in `app_settings` table (key: `matrix_9h` / `matrix_18h`)
- Also cached in `static/js/games-matrix.js` as fallback
- `PUT /api/matrix` saves to DB primary, file as cache
- Templates receive matrix data server-side via Jinja: `var db9 = {{ matrix9 | tojson }};`

### Skins labels
- "Skins ½ Net" when gross player count < 8
- "Skins Gross" when gross player count >= 8

### Skins Type row
- Computed row in matrix showing which skins format applies per player count

## Sticky Navigation

- `header` is sticky globally: `position: sticky; top: 0; z-index: 100;`
- `.tab-nav` is sticky globally: `position: sticky; z-index: 99;`
- `auth.js` runs `_setStickyOffsets()` at module level (self-executing, not inside `initAuth()`)
  to compute `.tab-nav`'s `top` offset from `header.offsetHeight`
- Runs on DOMContentLoaded, load, and resize events
- Works on ALL pages that include `auth.js`, even ones that don't call `initAuth()`
- `_setStickyOffsets()` also runs after `initAuth()` completes — critical because
  `onAuthReady()` may show/hide header buttons that change header height (e.g. Handicaps
  page shows Import, Sync, Settings buttons for admin, which increases header height)
- Page-specific sticky elements (e.g. `.matrix-controls`) add their own offsets on top

## Key files

- `app.py` — routes, scheduler, webhook (~6200 lines)
- `email_parser/parser.py` — AI extraction prompt and logic
- `email_parser/database.py` — schema, CRUD, audit queries, customer matching, COO context, bank reconciliation (~12000+ lines)
- `email_parser/fetcher.py` — Microsoft Graph email fetching
- `email_parser/report.py` — Daily digest email builder + sender
- `email_parser/rsvp_parser.py` — Golf Genius RSVP email parser (regex, no AI)
- `templates/index.html` — Transactions dashboard
- `templates/events.html` — Events management + Tee Time Advisor + Financial tab (hybrid server/client rendering)
- `templates/customers.html` — Customer directory + roster import + 5-tab detail (Transactions, Scores, Winnings, Points, Info)
- `templates/handicaps.html` — Handicap management page
- `templates/matrix.html` — Side games prize matrix
- `templates/audit.html` — Email audit/QA (admin) + per-order re-extract
- `templates/rsvps.html` — RSVP log
- `templates/accounting.html` — Accounting: multi-entity tracking, bank reconciliation, month-end close
- `templates/reconcile.html` — Bank reconciliation: account dashboard, match queue, monthly summary
- `templates/cashflow.html` — Cash flow: 90-day rolling weekly view with warning indicators
- `templates/coo.html` — COO Dashboard: action items, financial snapshot, review queue, AI chat
- `templates/tgf.html` — TGF Payouts: events, golfers, screenshot import
- `templates/database.html` — Admin database browser
- `templates/changelog.html` — Version changelog
- `static/js/dashboard.js` — Transactions page logic (largest JS file)
- `static/js/coo-dashboard.js` — COO Dashboard logic: chat, agents, editable values, action items
- `static/js/auth.js` — PIN auth + role management + sticky nav offsets
- `static/js/games-matrix.js` — Prize matrix data (9-hole & 18-hole, 2-64 players)
- `static/js/version.js` — Version number + changelog data
- `static/js/chat-widget.js` — Support/feedback chat widget
- `golf_genius_sync.py` — Golf Genius handicap sync via HTTP
- `mcp_server.py` — MCP server (31 tools for Claude direct DB access)

## COO Dashboard & AI Chat

### Architecture
- **COO page** at `/coo` — dashboard with action items, financial snapshot, and AI chat
- **AI Chat** uses Anthropic Claude API (`claude-sonnet-4-5-20250929`) with full business context
- **Agent routing** — `route_to_agent()` maps user questions to specialist agents (Financial,
  Operations, Course Correspondent, Member Relations, Compliance)
- **Chief of Staff** is the primary voice — always responds, with specialist context injected
- **Chat sessions** persist in `coo_chat_sessions` / `coo_chat_messages` tables
- **Master context** — summaries of all past sessions injected as "persistent memory"

### COO Agent System (`coo_agents` table)
Six specialist agents seeded on first run via `_seed_coo_agents()`:
1. **Chief of Staff** — primary voice, synthesizes all specialist input
2. **Financial Agent** — allocations, expenses, reconciliation, tax reserve
3. **Operations Agent** — events, registrations, rosters, breakeven
4. **Course Correspondent Agent** — course relationships, contracts, confirmations
5. **Member Relations Agent** — member communications, winnings, credits
6. **Compliance Agent** — sales tax, IRS installments, filing deadlines

Prompt updates: Use `_seed_coo_agents()` for new installs. For existing DBs, add a
migration check in `init_db()` (see "vigilant analyst" check pattern).

### `build_coo_full_context()` — Live Business Intelligence
Located in `database.py`, generates a text briefing from 10 modules for the AI.
All sections wrapped in try/except with `logger.warning()` logging.

**Section 2 — Events & Operations (key data):**
- **Upcoming events:** player counts (9/18 split), revenue (includes add-on payments),
  pricing structure (course_cost, markup, side_game_fee for 9h and 18h variants)
- **Player counts:** `parent_item_id IS NULL` filter in COUNT expression only —
  ensures child payment items excluded from player count but included in revenue SUM
- **Recent events:** last 30 days with player/revenue data
- **RSVP breakdown:** per-event playing vs not-playing counts
- **Cost allocations:** from `acct_allocations` table — course_payable, prize_pool,
  godaddy_fee, tgf_operating, total_collected (penny-accurate)
- **TGF payouts:** tournament prize pools with category breakdowns
- **Full profitability:** from allocations table, formula:
  `Net = Revenue - Course Fees - Prize Fund - Processing Fees`

### Event Pricing Data Model
The `events` table has extensive pricing columns:
- `course_cost` / `course_cost_9` / `course_cost_18` — post-tax course fee per player
- `tgf_markup` / `tgf_markup_9` / `tgf_markup_18` — TGF margin per player
- `side_game_fee` / `side_game_fee_9` / `side_game_fee_18` — side games fee
- `transaction_fee_pct` REAL DEFAULT 3.5 — blanket fee charged to players
- `course_surcharge` — per-player surcharge (e.g., $1 ACGT printing)
- `course_cost_breakdown` / `_9` / `_18` — JSON with tax-inclusive line items

**Course cost calculation:**
- Base amount × (1 + tax_pct/100) = post-tax cost (e.g., $39 × 1.0825 = $42.22)
- Player-facing price rounds up to nearest dollar ($43)
- `acct_allocations.course_payable` stores the exact post-tax amount (not rounded)

**Course cost rounding fix (Issue #242):**
- **Per-player allocations** store individual post-tax amounts (individually correct)
- **Aggregate calculations** (Financial tab, COO dashboard) use corrected formula:
  `base_rate × player_count × (1 + tax_rate)` — totals first, tax second
- Old way: $54 × 1.0825 = $58.46/player → $58.46 × 32 = **$1,870.72** (rounding drift)
- New way: $54 × 32 = $1,728 × 1.0825 = **$1,870.40** (correct)
- Server: `_calc_aggregate_course_cost()` in database.py
- Client: `calcAggregateCost()` in events.html (fallback path)

**Processing fee (GoDaddy merchant fee):**
- Actual formula: `order_total × 2.9% + $0.30` per order
- Stored in `acct_allocations.godaddy_fee` per player
- The 3.5% `transaction_fee_pct` is the blanket fee charged to players —
  the difference between 3.5% revenue and actual 2.9%+$0.30 cost is TGF margin

### COO Chat UI Features
- **Copy button** — clipboard icon on hover for all AI responses (coo-dashboard.js)
- **Chat session rename** — pencil icon on hover in sidebar, calls `PATCH /api/coo/chat-sessions/<id>`
- **Session management** — new chat, delete, load previous sessions
- **Collapse state** — `COO.collapsedGroups` Set tracks which topic groups are open/closed
- **Dismiss persistence** — dismissed action items survive re-renders

### Key COO endpoints
- `POST /api/coo/chat` — send message, get AI response
- `GET /api/coo/chat-sessions` — list all sessions
- `GET /api/coo/chat-sessions/<id>` — load session with messages
- `PATCH /api/coo/chat-sessions/<id>` — rename session
- `DELETE /api/coo/chat-sessions/<id>` — delete session
- `GET /api/coo/agents` — list active agents

## TGF Payouts Page

### Architecture
- **Page** at `/tgf` — two top-level tabs: EVENTS and GOLFERS
- **Data** from `tgf_events` and `tgf_payouts` tables; golfer identity is the `customers` table (tgf_golfers was eliminated)
- **API:** `GET /api/tgf` returns `{customers, events, winnings}` where customers is the list of payout recipients

### Events Tab
- Sidebar lists events by date with total purse amounts
- Main area shows payouts table grouped by golfer (sorted by total descending)
- Expandable rows show category breakdowns (team_net, individual_net, skins, etc.)
- Venmo pay links generated for golfers with venmo_username set

### Screenshot Paste / Import
- **Drop zone** appears below the payouts table when an event is selected
- **Three input methods:** Ctrl+V paste, drag & drop, click to upload
- **AI parsing:** `POST /api/tgf/parse-screenshot` sends image to Claude Vision
  (`claude-sonnet-4-20250514`), returns JSON with golfer names, categories, amounts
- **Preview table** shows parsed payouts with Save/Cancel buttons
- **Save** calls `POST /api/tgf` with `action: "import_payouts"` — adds payouts to
  the currently selected event (does NOT create a new event)
- **Backend:** `import_tgf_payouts(event_id, payouts)` inserts payouts, updates event
  aggregates (total_purse, winners_count, payouts_count)
- **Paste only fires** when events tab is active AND an event is selected

### Golfer name resolution
- `_resolve_customer_for_payout(conn, name)` — resolves payout recipient to a `customer_id` via the standard `_lookup_customer_id` cascade; creates a new customer with `acquisition_source='tgf_payout'` if no match found
- Payouts linked to identity via `tgf_payouts.customer_id` (FK to `customers.customer_id`)

### Category types
`team_net`, `individual_net`, `individual_gross`, `skins`, `closest_to_pin`,
`hole_in_one`, `mvp`, `other`

### Key TGF endpoints
- `GET /api/tgf` — all data (events + payouts + golfer winnings)
- `POST /api/tgf` — actions: `add_event`, `import_payouts`, `add_golfer`,
  `import_golfers`, `update_event`, `delete_event`
- `POST /api/tgf/parse-screenshot` — AI screenshot parsing (manager+ role)

## Customers Page — Tab System

### Three rendering paths (IMPORTANT)
The Customers page has 3 separate rendering paths that must be kept in sync:
1. **Inline expanded card** (desktop list view, click to expand) — ~line 1150 in customers.html
2. **Detail panel** (`selectCustomer()`, used in Cards view) — ~line 1674
3. **Mobile card view** (responsive layout) — ~line 663

### Five tabs on all views
Each rendering path has 5 tabs: **Transactions**, **Scores**, **Winnings**, **Points**, **Info**

- **Transactions** — customer's purchase history with click-to-navigate to `/` page
- **Scores** — handicap data loaded via `/api/handicaps/players`, shows index + round history
- **Winnings** — TGF payout history loaded via `/api/customers/winnings`
- **Points** — placeholder for future points system
- **Info** — customer metadata (email, phone, chapter, GHIN, status)

### Customer winnings API
- `GET /api/customers/winnings?customer_name=<name>` — returns payout history
- `get_customer_winnings()` uses multi-step name matching:
  exact → case-insensitive → alias → name reversal
- Returns `{golfer_name, total_winnings, payouts: [{event_name, date, category, amount}]}`

## Unified Financial Model (Issue #242)

### Architecture: acct_transactions as single source of truth

Every financial event writes a flat entry to `acct_transactions` via `_write_acct_entry()`.
The verified path in `get_event_financial_summary()` reads from these entries first, falling
back to allocation-based calculation only when no flat entries exist.

**New columns on acct_transactions:**
`item_id`, `event_name`, `customer`, `order_id`, `entry_type`, `category`, `amount`,
`account`, `status`, `reconciled_batch_id`, `net_deposit`, `merchant_fee`

**Entry types:** `income`, `expense`, `contra`, `liability`
**Categories:** `registration`, `processing_fee`, `comp`, `addon`, `refund`,
`credit_issued`, `transfer_in`, `transfer_out`, `godaddy_order`, `godaddy_batch`
**Sources:** `godaddy`, `venmo`, `zelle`, `cash`, `manual`
**Status:** `active`, `reversed`, `reconciled`, `merged`

### GoDaddy Order-Level Accounting (NEW)

GoDaddy orders now create **one `acct_transaction` per order** (not per item):
- `category='godaddy_order'`, `amount=order_total` (gross), `net_deposit=order_total - merchant_fee`
- `merchant_fee = order_total * 0.029 + 0.30` per ORDER
- Child rows in `godaddy_order_splits` table: registration, transaction_fee, merchant_fee, coupon
- `net_deposit` is what actually hits the bank — used for reconciliation and cash flow

**`godaddy_order_splits` table:**
- `transaction_id` FK → `acct_transactions.id`
- `item_id`, `event_name`, `customer`, `split_type`, `amount`
- `split_type` IN ('registration', 'transaction_fee', 'merchant_fee', 'coupon')
- Registration/tx_fee amounts are positive; merchant_fee/coupon are negative

**Migration:** `migrate_item_to_order_entries()` converts old per-item entries
(`godaddy-income-{id}` + `godaddy-fee-{id}`) to new order-level format.
Runs automatically at startup if old entries exist. Admin endpoint:
`POST /api/reconciliation/migrate-to-order-level`

**Batch matching:** `batch_match_deposit()` matches multiple order transactions
to a single bank deposit (1:many). `merge_transactions()` combines multiple
orders into a `godaddy_batch` entry (marks originals as `status='merged'`).

### Financial tab P&L model

The Financial tab uses a dual-path rendering:
1. **Verified path** (server-side): `renderFinancialPanelServer()` reads from
   `get_event_financial_summary()` which queries `acct_transactions` flat entries.
   Shows "Accounting (verified)" badge + reconciliation count.
2. **Fallback path** (client-side): `renderFinancialPanel()` calculates from raw items.
   Shows "Calculated (estimated)" badge.

The verified path fires when flat `acct_transactions` entries with `entry_type IS NOT NULL`
exist for the event. After backfill, all 2026 events use the verified path.

Both render paths include a **Payouts Made vs. Budget** section (below the profit bar) that compares
the GAMES matrix prize fund budget (HIO + Included + NET + GROSS pools) against actual payouts from
`tgfPayoutData.events[].total_purse`. Shows budget, paid out, and variance (UNDERPAID/OVERPAID/BALANCED).
The `_renderPayoutsBudgetSection(ev, gamePots)` helper in events.html is called from both render functions.

**Net revenue formula (verified path):**
```
Total Income = registration + addon + transfer_in + tx_fees (from items.transaction_fees)
Contra = transfer_out + refunds + merchant_fees (from processing_fee entries)
Net Revenue = Total Income - Contra
```

**Client-side fallback model:**

```
INCOME
  Paid Players (item_price from GoDaddy items)
  Credit Transfers In (original price from transferred items)
  Add-on Payments (positive child items only)
  ─────────────────────────────────
  Subtotal
  + Transaction Fees (actual parsed value from each GoDaddy email, NOT calculated)
  = Gross Revenue
  - GoDaddy Merchant Fees (2.9% + $0.30 PER ORDER, calculated per-order)
  - Refunds (negative child items = contra-revenue)
  ─────────────────────────────────
  = NET INCOME

EXPENSES
  Course Fees (aggregate: base × count × tax — no per-player rounding)
  Prize Fund (from GAMES matrix: HIO + Included + NET + GROSS)
  ─────────────────────────────────
  = TOTAL EXPENSES

PROJECTED PROFIT = Net Income - Total Expenses
```

### Critical: Transaction fees vs GoDaddy merchant fees
- **Transaction fees (3.5%)** are intentionally collected revenue from players, parsed from
  each GoDaddy email invoice and stored in `items.transaction_fees`. They are NOT calculated —
  the actual value from the email is used. These offset the GoDaddy merchant fees.
- **GoDaddy merchant fees (2.9% + $0.30)** are calculated PER INDIVIDUAL GoDaddy ORDER
  on the order total (item_price + transaction_fee). Stored in the `merchant_fee` column
  on the order-level `acct_transaction` and as proportional `merchant_fee` splits in
  `godaddy_order_splits`. Formula: `order_total * 0.029 + 0.30`.
  Only items with `merchant = 'The Golf Fellowship'` get GoDaddy order entries.
  Transfer targets (`transferred_from_id IS NOT NULL`) are excluded.
- **Refunds** are contra-revenue (deducted from Income), not expenses. They appear as
  negative child payment items (e.g., -$29 partial refund via Zelle).

### Parser: item_price extraction
- `item_price` must come from the **Subtotal** or **SKU line** in the GoDaddy email,
  NEVER from the "MEMBER STATUS: MEMBER = $XX" line (that's just the base membership rate
  and excludes side game add-ons). See parser.py extraction prompt.
- `transaction_fees` is parsed directly from the "Transaction Fees 3.5%: $X.XX" line.
- Re-extract force-updates `item_price`, `side_games`, and `holes` (FORCE_UPDATE_FIELDS).

### Operations that create accounting entries
| Operation | What Happens |
|-----------|-------------|
| GoDaddy order saved | `income/godaddy_order` with splits (registration, tx_fee, merchant_fee, coupon) via `_write_godaddy_order_entry()` |
| Manual comp added | `expense/comp` (amount=0) via `_write_acct_entry()` |
| External payment (Venmo/cash) | `income/addon` + `acct_allocations` via `_create_allocation_for_item()` |
| Add-on payment (child item) | `income/addon` + `acct_allocations` entry |
| Credit transfer (player A→B) | `contra/transfer_out` on source + `income/transfer_in` on target, plus allocation |
| Refund issued | `expense/refund` entry |
| Partial refund | `expense/refund` entry for the refunded amount |
| WD with credits | `liability/credit_issued` entry for credit amount |
| Reverse any of the above | Original flat entries marked `status='reversed'`, legacy entries deleted |

### Key functions
- `_write_acct_entry(conn, ...)` — central helper for all flat ledger writes; idempotent via `source_ref`. Accepts `net_deposit`/`merchant_fee` kwargs. Auto-resolves `customer_id` via `_lookup_customer_id` if not provided.
- `_write_godaddy_order_entry(conn, *, order_id, items, date)` — creates order-level transaction + splits. Re-entrant (soft-deletes + recreates).
- `_create_allocation_for_item(item, conn, payment_method, ...)` — creates allocation for
  non-GoDaddy items using synthetic `order_id` (prefixes: `EXT-`, `XFER-`, `MANUAL-PAY-`, `COMP-`)
- `get_event_financial_summary(event_name)` — reads from flat `acct_transactions` + `godaddy_order_splits` (verified path), falls back to allocations
- `_calc_aggregate_course_cost(event, items, conn)` — correct aggregate rounding (base × count × tax)
- `backfill_acct_transactions()` — one-time backfill of flat entries for all 2026 items (runs at startup). Groups GoDaddy items by order_id.
- `migrate_item_to_order_entries()` — converts old per-item entries to order-level. Creates backup first.
- `batch_match_deposit()` — match multiple transactions to one bank deposit (1:many)
- `merge_transactions()` — combine multiple orders into a godaddy_batch entry
- `backup_database()` — creates timestamped .db backup before migrations
- `backfill_financial_entries()` — retrofits allocations/legacy transactions for existing data
- `_backfill_customer_id_on_acct_transactions(conn)` — populates `customer_id` FK on existing acct_transactions rows
- `_backfill_customer_id_on_player_links(conn)` — populates `customer_id` FK on existing handicap_player_links rows
- `_create_acct_ledger_entry(...)` — accounting ledger path for bank imports and recurring entries (entity splits, account_id). Distinct from `_write_acct_entry()` which is for the event financial model.
- `transfer_item()` — stores actual credit amount on transferred item (not $0.00); creates only flat acct_transactions entries (no legacy acct_splits)

### Credit/transfer/refund actions
- Credit transfer items now show Credit, WD, and Refund buttons (same as regular items)
- Partial refund supports custom dollar amount input (for credit overpayments like $29)
- Refund methods: GoDaddy, Venmo, Zelle
- Transfer items carry the original price (e.g., "$102.00 (credit)") not "$0.00 (credit)"

### Course fee rounding fix
- **Per-player allocations** store individual post-tax amounts (individually correct)
- **Aggregate calculations** (Financial tab) use corrected formula:
  `base_rate × player_count × (1 + tax_rate)` — totals first, tax second
- Example: $54 × 32 × 1.0825 = $1,870.56 (correct) vs $58.46 × 32 = $1,870.72 (old drift)

### `acct_allocations` table — per-player cost breakdown
Each row represents one player's cost allocation for one event:
- `course_payable` REAL — exact course fee (post-tax, not rounded)
- `course_surcharge` REAL — per-player surcharge
- `prize_pool` REAL — player's contribution to prize fund
- `tgf_operating` REAL — TGF's operating margin
- `godaddy_fee` REAL — actual GoDaddy merchant fee share
- `tax_reserve` REAL — sales tax reserve (8.25% of tgf_operating)
- `total_collected` REAL — total revenue collected from this player
- `payment_method` TEXT — `godaddy`, `venmo`, `cash`, `zelle`, `check`, `credit_transfer`, `comp`
- `acct_transaction_id` INTEGER — FK to `acct_transactions.id` (links allocation to accounting entry)
- `order_id` uses synthetic prefixes for non-GoDaddy items: `EXT-`, `XFER-`, `MANUAL-PAY-`, `COMP-`

### Accounting categories (TGF-scoped, seeded by `_seed_unified_financial_categories`)
- **Income:** "Credit Transfer In", "External Payment", "Event Revenue", "Membership Fees"
- **Expense:** "Credit Transfer Out", "Player Refunds", "Golf Course Fees / Green Fees"

## Database Tables (37+)

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
`agent_action_log`, `tgf_events`, `tgf_payouts`

Key tables not documented elsewhere in this file:
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
- `tgf_events` — tournament events with purse totals
- `tgf_payouts` — individual prize payouts linked to events via `event_id` and to customers via `customer_id` (no separate golfer table; identity is unified in `customers`)
- `expense_transactions` — staging table for CC/bank alert emails; rows are created by the AI bookkeeper and require human approval. Approved rows are promoted to `acct_transactions` via `_sync_expense_ledger_entry` (sets `entry_type='expense'`). Linked back via `acct_transaction_id` FK.
- `acct_keyword_rules` — auto-categorization rules (`match_type='contains'`, `COLLATE NOCASE`). Created when an expense is approved with a category; used to pre-categorize future alerts from the same merchant before the AI bookkeeper runs.

## Expense Transaction Workflow

### Tables
- `expense_transactions` — staging table for CC/bank alert emails parsed by the AI bookkeeper.
  Fields include: `merchant`, `amount`, `txn_date`, `category`, `review_status`,
  `account_name`, `account_last4`, `account_id` (FK → `bank_accounts`), `customer_id`,
  `acct_transaction_id` (FK → `acct_transactions`; set when promoted to ledger).
- `acct_keyword_rules` — auto-learned categorization rules. When an expense is approved with
  a category, a `match_type='contains'` rule is created so future alerts from the same
  merchant get auto-categorized (`COLLATE NOCASE` — case-insensitive).

### Approval → Ledger Promotion
`_sync_expense_ledger_entry(conn, exp)` — called by `update_expense_transaction()` whenever
an expense is set to `review_status IN ('approved', 'corrected')`.

- Creates (or updates) a row in `acct_transactions` with:
  - `entry_type = 'expense'`
  - `amount = COALESCE(amount, total_amount)` — must be set so reconciliation can compare
  - `description = merchant`, `date = txn_date`, `type = 'expense'`
  - `source_ref = 'expense-{id}'` for idempotency
- Sets `expense_transactions.acct_transaction_id` back to the new/existing ledger row ID.
- `_backfill_approved_expenses_to_ledger(conn)` runs at startup in `init_db()` to promote
  any already-approved expenses that were missing a ledger row (one-time catch-up).

### Vendor / Customer Typeahead on Expense Modal
The expense review modal has the same Vendor/Customer typeahead as the income/ledger modal.
IDs use `exp-*` prefix (`#exp-customer-id`, `#exp-customer-search`, `#exp-customer-dropdown`).

Key JS functions in `acct-transactions.js`:
- `setExpCustomer(id, name, isVendor)` — populates the selected-chip display
- `clearExpCustomer()` — resets the field
- `initExpCustomerTypeahead()` — wires the search-input debounce/dropdown
- `saveNewVendor()` — routes to `setExpCustomer` vs `setTxnCustomer` based on which modal
  is open (`$('#expense-review-modal').style.display !== 'none'`)

### Category Learning
When an expense is approved with a category, `acct_keyword_rules` auto-gets a new row:
`match_type='contains'`, `keyword=merchant`, `category=category`, `COLLATE NOCASE`.
Future alerts from the same merchant (or containing that merchant name) are pre-categorized.
Vendor (`customer_id`) auto-suggestion is NOT yet implemented — that requires a separate
lookup of which `customer_id` most frequently maps to a given keyword rule.

### GoDaddy Merchant Fee Split
GoDaddy transactions store up to 3 splits in `acct_splits`: registration, tx_fee, and
negative merchant_fee. When the edit modal opens for a GoDaddy transaction:
- If existing splits in DB already include a negative split (`amount < 0`), use DB splits.
- If existing splits lack the negative merchant_fee (pre-fix data), call `_buildSmartSplit(txn)`
  which generates all 3 splits from `txn.merchant_fee` or `txn.order_splits.merchant_fee`.

```javascript
const isGoDaddy = txn.category === 'godaddy_order' || txn.order_splits?.registration != null;
const hasMerchantFeeSplit = txn.splits.some(s => (s.amount || 0) < 0);
const useDbSplits = txn.splits.length > 0 && (!isGoDaddy || hasMerchantFeeSplit);
const splitsData = useDbSplits ? txn.splits.map(...) : _buildSmartSplit(txn);
```

## Bank Reconciliation System

### Architecture
Three new tables link bank statement data to the accounting ledger:
- `bank_accounts` → `bank_deposits` → `reconciliation_matches` → `acct_transactions`

### Import formats
- **Chase CSV**: auto-detected by "Posting Date" header. Imports credits only.
  GoDaddy deposits tagged by description containing "GODADDY".
- **Venmo CSV**: auto-detected by "Datetime" header. Imports completed positive transactions.
- **PDF**: text extracted via `pdfplumber`, parsed by Claude AI into date/description/amount.
- **Idempotency**: deduplicates on `account_id + deposit_date + amount + description`.

### Auto-matching (`run_deposit_auto_match`)
Runs after every import and on-demand via "Auto-match All" button.
- **GoDaddy batch**: finds income transactions within ±2 days, compares sum.
  Within $1 = auto-match (confidence 0.95), within $5 = partial (0.70).
- **Venmo**: exact amount match + customer name in description = 0.95.
  Amount only = 0.70, flagged for review.
- **Negative deposits (bank debits / CC charges)**: matches against
  `entry_type='expense'` ledger entries. `ABS(dep_amt)` compared against expense
  `COALESCE(amount, total_amount)`. ±$1 tolerance, ±10 day date window.
  Confidence: 0.85 (desc+amount), 0.65 (desc only), 0.55 (amount only).
- **Zelle/other**: amount + date ±1 day, always flagged for manual confirm (0.60).
- Matched transactions get `status = 'reconciled'` in `acct_transactions`.

### GoDaddy Reconciliation — net_deposit as amount
Bank statements show the net deposit (after merchant fee). `acct_transactions` rows for
GoDaddy orders now use `net_deposit` (= `total_amount - merchant_fee`) as the comparison
amount in auto-matching, so a $222.53 order with a $6.75 fee matches the $215.78 bank credit.

### Accounting Ledger Improvements

**Customer/Vendor column:**
- Ledger table has a Customer/Vendor column (between Date and Description).
- `get_acct_transactions()` LEFT JOINs `customers`, returns `customer_name`
  using `COALESCE(NULLIF(company_name,''), NULLIF(TRIM(first_name||' '||last_name),''), legacy_customer_text)`.
- **Column visibility toggle:** "Columns" button in filter bar opens a dropdown with checkboxes
  for Customer/Vendor, Category, Type, Account. Choices persisted in localStorage.
  CSS class toggle on the table element (`acct-hide-X`) so visibility survives re-renders.

**Smart Fill:**
- `POST /api/accounting/smart-fill` with `{dry_run: true}` previews changes; `dry_run: false` applies.
- For all unsplit active `acct_transactions`: assigns `account_id` via `_guessAccountId()`
  (matches "GODADDY" → TGF Checking, "VENMO" → Venmo, etc.) and creates a default single split
  via `_buildSmartSplit()` (uses `Event Revenue` category for income).
- **Smart Fill button** in the ledger filter bar runs dry-run first, shows confirm dialog with counts, then applies.
- `openEditTransaction()` also auto-assigns account and pre-populates a smart split when
  creating/editing a transaction with no splits.

**Ledger display changes:**
- Category column shows just the category name (e.g. "Event Revenue") not a verbose badge;
  multi-split rows show `[split]`.
- Edit modal shows GoDaddy fee and net deposit below split total when `merchant_fee > 0`.

### Reconciliation UI (`/accounting/reconcile`)
Three tabs — the standalone page, kept for power-user workflows and the
Monthly Summary CSV export:
1. **Account Dashboard** — cards per account: book/bank balance, variance, unmatched count
2. **Match Queue** — two-column layout: unmatched deposits (left) vs unreconciled transactions (right).
   Click deposit to highlight amount-similar transactions. Manual match + batch-match + auto-match.
3. **Monthly Summary** — income/expense by category, reconciliation %, CSV export.

### Inline Match Queue (v2.8.0) — lives inside the Ledger tab
The day-to-day reconciliation workflow is embedded directly in the Accounting
Ledger tab so admins don't have to leave the main view.

- When the **Unreconciled** status pill is active in `/accounting` → Ledger,
  the `#ledger-split` container toggles to `.split-on` (CSS grid: `minmax(280px,1fr) minmax(420px,1.4fr)`).
- **Left pane** (`#ledger-deposits-pane`) — unmatched bank deposits from
  `GET /api/reconciliation/deposits?status=unmatched`. Optionally filtered
  client-side by the active account pill (matches by `account_name`).
- **Right pane** (`#txn-list`) — the existing unreconciled ledger entries.
- **Click a deposit** → `highlightAmountMatches()` adds `.lmq-candidate` to
  right-pane rows whose amount is within ±$1.00 (the Amount td cell `td:nth-child(4)`
  gets an amber `#fef3c7` background).
- **Click a ledger row in split mode** → `setSelectedLedgerTxn()` picks it as the
  match candidate (blue outline + `.lmq-selected`) instead of opening the edit modal.
- **Match button** → `POST /api/reconciliation/match` with `{bank_deposit_id, acct_transaction_id}`.
  Matched row fades out via `.lmq-matched`, deposit card removed from left pane.
- **Auto-Match All button** → `POST /api/reconciliation/auto-match` with empty body;
  auto/partial/unmatched counts flash in the header, then `loadTransactions()` refreshes both panes.
- Other status pills (All / Reconciled / Pending Review) keep the normal flat table layout —
  the split pane only appears under **Unreconciled**.
- State lives in a module-level `LMQ` object in `static/js/acct-transactions.js`.

### Cash Flow (`/accounting/cashflow`)
90-day rolling weekly view (configurable: 8/13/26 weeks).
Columns: expected income, confirmed (banked), projected expenses, actual expenses, net, running balance.
Red warning rows where projected expenses exceed confirmed income.

### Visual indicators
- **Events Financial tab**: "Reconciliation: X of Y transactions confirmed in bank ($Z matched)"
  Loaded async via `/api/reconciliation/event/<name>`.
- **Transactions page**: colored dot on each row:
  - Yellow = active item, awaiting bank match
  - Grey = comp, RSVP, or inactive (no bank match expected)

### Key endpoints
| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/accounting/reconcile` | GET | admin | Reconciliation UI page |
| `/accounting/cashflow` | GET | admin | Cash flow page |
| `/api/reconciliation/import` | POST | admin | Upload bank statement (file + account_id) |
| `/api/reconciliation/auto-match` | POST | admin | Run auto-matching |
| `/api/reconciliation/match` | POST | admin | Manual match (deposit + txn) |
| `/api/reconciliation/match-batch` | POST | admin | Batch match (1 deposit : N txns) |
| `/api/reconciliation/merge-transactions` | POST | admin | Merge orders into batch entry |
| `/api/reconciliation/migrate-to-order-level` | POST | admin | Migrate old per-item to order-level |
| `/api/reconciliation/unmatch` | POST | admin | Remove a match |
| `/api/reconciliation/deposits` | GET | admin | List deposits (filterable) |
| `/api/reconciliation/unreconciled` | GET | admin | Unmatched accounting entries |
| `/api/reconciliation/dashboard` | GET | admin | Account summary cards |
| `/api/reconciliation/monthly` | GET | admin | Monthly breakdown |
| `/api/reconciliation/event/<name>` | GET | manager | Event reconciliation status |
| `/api/reconciliation/cashflow` | GET | admin | Weekly cash flow data |

## Jinja gotcha in inline CSS (IMPORTANT)

Flask templates are parsed by Jinja2, which treats `{#` as the start of a
comment and `#}` as the end. **CSS rules that pack `{` directly against `#`**
(e.g. `@media(max-width:900px){#some-id{...}}`) will crash template rendering
with `TemplateSyntaxError: Missing end of comment tag` and the global 500
handler returns `{"error":"Internal server error"}`.

This hit `/accounting` in v2.8.0. The fix is a one-character space:
`@media(...){ #some-id{...} }` — the brace no longer abuts the hash so Jinja
stops reading it as a comment opener.

Same rule for `{%` (statement), `{{` (expression). When embedding CSS inside
a Jinja-rendered template, always insert whitespace between an opening
brace and a literal `#`, `%`, or `{`. Verify with:

```
python3 -c "from jinja2 import Environment, FileSystemLoader; \
    Environment(loader=FileSystemLoader('templates')).get_template('accounting.html').render()"
```

## Git Merge & PR Best Practices

When merging branches that have diverged (especially long-running feature branches),
follow these steps to avoid losing work:

### Before merging

1. **Inventory both sides** — Run `git log main..feature` and `git log feature..main`
   to see exactly what commits exist on each side. Every commit must survive the merge.
2. **Back up the branch** — Create a safety tag: `git tag pre-merge-backup`
   so you can always recover.

### During conflict resolution

3. **Never blindly accept one side** — Use `git diff` to understand each conflict.
   Most conflicts need *both* sides combined, not one or the other.
4. **Watch for duplicate declarations** — When both branches add similar code
   (e.g., a `const` variable), merging both creates a syntax error.
   Keep only one declaration but preserve the logic from both.
5. **Check the surrounding context** — Conflict markers only show the changed lines.
   Read 20+ lines above and below to make sure the merge fits the larger function.

### After merging

6. **Verify nothing was lost** — Search for key identifiers from each branch
   (function names, variable names, CSS classes) to confirm they're still present.
7. **Test the app** — Run the server locally or deploy to a staging environment
   before merging to `main`.
8. **Keep commits atomic** — Don't squash a 26-commit feature branch into one commit.
   Preserve individual commits so `git log` tells the full story.

### Common pitfalls

- **Rebase vs merge** — Prefer `git merge` for long-lived branches with many commits.
  Rebase rewrites history and can silently drop changes.
- **Force-push** — Never `git push --force` to a shared branch. If a push is
  rejected, investigate why before overriding.
- **Large template files** — Files like `events.html` (3000+ lines) are
  conflict-prone. When resolving, check every function/block boundary carefully.
