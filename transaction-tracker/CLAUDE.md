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
