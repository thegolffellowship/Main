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
- `distributions` — value counts for city, course, member_status, golf_or_compete, tee_choice

### How to inspect recent data

```
WebFetch https://tgf-tracker.up.railway.app/api/data-snapshot?limit=20
```

### How to get full data

```
WebFetch https://tgf-tracker.up.railway.app/api/items
```

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
