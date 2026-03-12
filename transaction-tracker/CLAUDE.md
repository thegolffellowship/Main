# Transaction Email Tracker — Claude Context

## Deployed URL

**Railway:** `https://main-production-b95c.up.railway.app`

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
WebFetch https://main-production-b95c.up.railway.app/api/audit
```

This returns:
- `fill_rates` — percentage of rows where each field is populated
- `problems` — list of rows missing critical fields (customer, order_id, item_name, etc.)
- `distributions` — value counts for city, course, member_status, golf_or_compete, tee_choice

### How to inspect recent data

```
WebFetch https://main-production-b95c.up.railway.app/api/data-snapshot?limit=20
```

### How to get full data

```
WebFetch https://main-production-b95c.up.railway.app/api/items
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
      "url": "https://main-production-b95c.up.railway.app/mcp/mcp"
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

All handicap calculations are for **9-hole rounds only**. The system uses a
custom TGF differential table — do NOT use or derive a USGA 18-hole table.

### TGF Handicap Differential Table

| 9-Hole Rounds in Record | Differentials Used |
|------------------------|--------------------|
| 1–2 | None (no handicap) |
| 3–5 | Lowest 1 |
| 6–8 | Avg Low 2 |
| 9–11 | Avg Low 3 |
| 12–14 | Avg Low 4 |
| 15–16 | Avg Low 5 |
| 17–18 | Avg Low 6 |
| 19 | Avg Low 7 |
| 20 | Avg Low 8 (fully established) |

### Calculation rules
- **Lookback window:** 12 months (configurable)
- **Pool:** most recent 20 rounds within the window
- **Multiplier:** avg of lowest N × 0.96
- **Truncation:** `math.trunc` (toward zero), NOT `math.floor`, and NOT standard rounding —
  per USGA WHS Section 5.2: *"Delete all numbers after the tenths' digit. Do not round to
  the nearest tenth."* e.g. 6.282 → 6.2 (not 6.3); −0.228 → −0.2N (plus-handicapper)
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

### Key files
- `email_parser/database.py` — `_HANDICAP_DIFF_LOOKUP` (server-side table)
- `templates/handicaps.html` — `DIFF_LOOKUP` (client-side JS table, must match)
- Both tables must always be kept in sync.

## Architecture

- **Flask app** in `transaction-tracker/app.py`
- **Email parsing** via Claude AI in `email_parser/parser.py`
- **Email fetching** via Microsoft Graph API in `email_parser/fetcher.py`
- **SQLite DB** at `transaction-tracker/transactions.db` (local is empty; live data on Railway)
- **Scheduler** checks inbox every 15 minutes via APScheduler
- **Dashboard** at `/` with search, filter, sort, CSV export

## Key files

- `app.py` — routes, scheduler, webhook
- `email_parser/parser.py` — AI extraction prompt and logic
- `email_parser/database.py` — schema, CRUD, audit queries
- `email_parser/fetcher.py` — Microsoft Graph email fetching
- `templates/index.html` — dashboard HTML
- `static/js/dashboard.js` — client-side search/filter/export

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
