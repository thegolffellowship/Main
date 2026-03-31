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

### Available tools (21)

**Read:**
`get_transactions`, `get_transaction_by_id`, `get_statistics`,
`get_data_quality_report`, `get_recent_snapshot`, `list_events`,
`get_event_registrations`, `list_customers`, `get_customer_details`,
`search_transactions`

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

## Architecture

- **Flask app** in `transaction-tracker/app.py` (~3900+ lines, 98 routes)
- **Email parsing** via Claude Sonnet in `email_parser/parser.py`
- **Email fetching** via Microsoft Graph API in `email_parser/fetcher.py` — only processes emails with "New Order" subject lines; all processed email UIDs tracked in `processed_emails` table to prevent re-parsing
- **SQLite DB** at `transaction-tracker/transactions.db` (local is empty; live data on Railway)
- **Scheduler** checks inbox every 15 minutes via APScheduler
- **Dashboard** at `/` with search, filter, sort, CSV export
- **Golf Genius sync** via direct HTTP requests in `golf_genius_sync.py` (rewritten from Playwright)
- **MCP Server** in `mcp_server.py` — 21 tools for Claude direct DB access

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
- `refunded` — payment refunded, shown in **Inactive** section below table
- `transferred` — transferred to another player, shown in **Inactive** section below table
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
- Normalizes to: "1st TIMER", "MEMBER", "GUEST", or "MANAGER"

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

- `app.py` — routes, scheduler, webhook (~3900 lines)
- `email_parser/parser.py` — AI extraction prompt and logic
- `email_parser/database.py` — schema, CRUD, audit queries, customer matching (~3500 lines)
- `email_parser/fetcher.py` — Microsoft Graph email fetching
- `email_parser/report.py` — Daily digest email builder + sender
- `email_parser/rsvp_parser.py` — Golf Genius RSVP email parser (regex, no AI)
- `templates/index.html` — Transactions dashboard
- `templates/events.html` — Events management + Tee Time Advisor
- `templates/customers.html` — Customer directory + roster import
- `templates/handicaps.html` — Handicap management page
- `templates/matrix.html` — Side games prize matrix
- `templates/audit.html` — Email audit/QA (admin)
- `templates/rsvps.html` — RSVP log
- `templates/database.html` — Admin database browser
- `templates/changelog.html` — Version changelog
- `static/js/dashboard.js` — Transactions page logic (largest JS file)
- `static/js/auth.js` — PIN auth + role management + sticky nav offsets
- `static/js/games-matrix.js` — Prize matrix data (9-hole & 18-hole, 2-64 players)
- `static/js/version.js` — Version number + changelog data
- `static/js/chat-widget.js` — Support/feedback chat widget
- `golf_genius_sync.py` — Golf Genius handicap sync via HTTP
- `mcp_server.py` — MCP server (21 tools for Claude direct DB access)

## Database Tables (20 total)

`items`, `processed_emails`, `events`, `event_aliases`, `rsvps`, `rsvp_overrides`,
`rsvp_email_overrides`, `customers`, `customer_emails`, `customer_aliases`,
`handicap_rounds`, `handicap_player_links`, `handicap_settings`,
`message_templates`, `message_log`, `feedback`, `parse_warnings`,
`season_contests`, `app_settings`

Key tables not documented elsewhere in this file:
- `app_settings` — persistent key-value store (matrix data, feature flags)
- `season_contests` — contest enrollment tracking (NET/GROSS points race, city match play)
- `parse_warnings` — flagged items with potential parsing errors (open/dismissed/resolved)

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
