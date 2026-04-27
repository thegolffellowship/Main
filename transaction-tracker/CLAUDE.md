# Transaction Email Tracker — Claude Context

Before working on a specific area, Read the relevant sub-doc:
- `docs/claude/schema.md` (database/FKs)
- `docs/claude/unified-financial-model.md` (acct_transactions, GoDaddy model, P&L)
- `docs/claude/bank-reconciliation.md` (bank match queue, cash flow)
- `docs/claude/expense-workflow.md` (CC/bank alert ingestion, vendor categorization)
- `docs/claude/events.md` (events/RSVPs/pricing/cancellation/TGF payouts)
- `docs/claude/customers.md` (customer identity)
- `docs/claude/handicaps.md` (handicap rules)
- `docs/claude/coo.md` (COO dashboard + AI chat)

## Deployed URL

**Railway:** `https://tgf-tracker.up.railway.app`

## Inspection Endpoints

When the user asks about transaction data, extraction quality, or anything about what's been parsed — query these live endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/stats` | High-level counts (total items, orders, spend, date range) |
| `GET /api/audit` | Data-quality report: field fill-rates, rows with missing fields, value distributions |
| `GET /api/data-snapshot?limit=50` | Most recent N items + stats for quick inspection |
| `GET /api/items` | Full dump of all items (can be large) |

`/api/audit` returns: `fill_rates` (% of rows where each field is populated),
`problems` (rows missing critical fields), `distributions` (value counts for
chapter, course, user_status, tee_choice).

## Railway Persistent Volume (IMPORTANT)

SQLite data is lost on every redeploy unless stored on a persistent volume.

### Setup steps in Railway dashboard:
1. Go to your service → **Volumes** → **New Volume**
2. Set mount path: `/data`
3. Add environment variable: `DATABASE_PATH=/data/transactions.db`
4. Redeploy

This ensures the DB survives redeployments. Without this, every push wipes the data.

## MCP Server (Direct Data Access for Claude)

An MCP (Model Context Protocol) server at `mcp_server.py` gives Claude direct read/write access to the transaction database — no WebFetch needed.

### Claude Code setup

The `.mcp.json` at the repo root auto-configures it. Just restart Claude Code in this directory and you'll see the `tgf-transactions` server with 21 tools.

### Claude Desktop setup (remote — no local install)

The MCP endpoint is built into the Railway app at `/mcp/mcp`. Add this to your `claude_desktop_config.json` (Settings → Developer → Edit Config):

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

**Read:** `get_transactions`, `get_transaction_by_id`, `get_statistics`, `get_data_quality_report`, `get_recent_snapshot`, `list_events`, `get_event_registrations`, `list_customers`, `get_customer_details`, `search_transactions`

**Financial & Reconciliation:** `get_event_financial_summary`, `get_acct_transactions`, `get_bank_deposits`, `get_reconciliation_detail`, `get_cashflow_summary`, `get_acct_allocations`, `get_godaddy_order_splits`, `get_chart_of_accounts`, `get_mcp_ledger_entries`, `get_venmo_transactions`

**Write:** `update_transaction`, `credit_transaction`, `transfer_transaction`, `undo_credit_or_transfer`, `create_new_event`, `update_existing_event`, `delete_existing_event`, `add_player`, `delete_transaction`, `sync_events`, `run_autofix`

## Architecture

- **Flask app** in `transaction-tracker/app.py` (~6200 lines, 200+ routes)
- **Email parsing** via Claude Sonnet in `email_parser/parser.py`
- **Email fetching** via Microsoft Graph API in `email_parser/fetcher.py` — only processes emails with "New Order" subject lines; all processed email UIDs tracked in `processed_emails` table to prevent re-parsing
- **SQLite DB** at `transaction-tracker/transactions.db` (local is empty; live data on Railway)
- **Database layer** in `email_parser/database.py` (~12000+ lines) — schema, CRUD, allocations, COO context
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

## Sticky Navigation

- `header` is sticky globally: `position: sticky; top: 0; z-index: 100;`
- `.tab-nav` is sticky globally: `position: sticky; z-index: 99;`
- `auth.js` runs `_setStickyOffsets()` at module level (self-executing, not inside `initAuth()`) to compute `.tab-nav`'s `top` offset from `header.offsetHeight`
- Runs on DOMContentLoaded, load, and resize events
- Works on ALL pages that include `auth.js`, even ones that don't call `initAuth()`
- `_setStickyOffsets()` also runs after `initAuth()` completes — critical because `onAuthReady()` may show/hide header buttons that change header height (e.g. Handicaps page shows Import, Sync, Settings buttons for admin, which increases header height)
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

## Jinja gotcha in inline CSS (IMPORTANT)

Flask templates are parsed by Jinja2, which treats `{#` as the start of a comment and `#}` as the end. **CSS rules that pack `{` directly against `#`** (e.g. `@media(max-width:900px){#some-id{...}}`) will crash template rendering with `TemplateSyntaxError: Missing end of comment tag` and the global 500 handler returns `{"error":"Internal server error"}`.

This hit `/accounting` in v2.8.0. The fix is a one-character space: `@media(...){ #some-id{...} }` — the brace no longer abuts the hash so Jinja stops reading it as a comment opener.

Same rule for `{%` (statement), `{{` (expression). When embedding CSS inside a Jinja-rendered template, always insert whitespace between an opening brace and a literal `#`, `%`, or `{`. Verify with:

```
python3 -c "from jinja2 import Environment, FileSystemLoader; \
    Environment(loader=FileSystemLoader('templates')).get_template('accounting.html').render()"
```

## Git Merge & PR Best Practices

When merging branches that have diverged (especially long-running feature branches), follow these steps to avoid losing work:

### Before merging

1. **Inventory both sides** — Run `git log main..feature` and `git log feature..main` to see exactly what commits exist on each side. Every commit must survive the merge.
2. **Back up the branch** — Create a safety tag: `git tag pre-merge-backup` so you can always recover.

### During conflict resolution

3. **Never blindly accept one side** — Use `git diff` to understand each conflict. Most conflicts need *both* sides combined, not one or the other.
4. **Watch for duplicate declarations** — When both branches add similar code (e.g., a `const` variable), merging both creates a syntax error. Keep only one declaration but preserve the logic from both.
5. **Check the surrounding context** — Conflict markers only show the changed lines. Read 20+ lines above and below to make sure the merge fits the larger function.

### After merging

6. **Verify nothing was lost** — Search for key identifiers from each branch (function names, variable names, CSS classes) to confirm they're still present.
7. **Test the app** — Run the server locally or deploy to a staging environment before merging to `main`.
8. **Keep commits atomic** — Don't squash a 26-commit feature branch into one commit. Preserve individual commits so `git log` tells the full story.

### Common pitfalls

- **Rebase vs merge** — Prefer `git merge` for long-lived branches with many commits. Rebase rewrites history and can silently drop changes.
- **Force-push** — Never `git push --force` to a shared branch. If a push is rejected, investigate why before overriding.
- **Large template files** — Files like `events.html` (3000+ lines) are conflict-prone. When resolving, check every function/block boundary carefully.
