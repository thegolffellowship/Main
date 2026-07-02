# Transaction Email Tracker — Claude Context

Before working on a specific area, Read the relevant sub-doc:
- `docs/claude/schema.md` (database/FKs)
- `docs/claude/unified-financial-model.md` (acct_transactions, GoDaddy model, P&L)
- `docs/claude/bank-reconciliation.md` (bank match queue, cash flow)
- `docs/claude/duplicate-detective.md` (ledger cleanup admin tool — see below)
- `docs/claude/expense-workflow.md` (CC/bank alert ingestion, vendor categorization)
- `docs/claude/events.md` (events/RSVPs/pricing/cancellation/TGF payouts)
- `docs/claude/customers.md` (customer identity, **membership renewal system**)
- `docs/claude/handicaps.md` (handicap rules)
- `docs/claude/participation.md` (participation analysis + re-engagement emails)
- `docs/claude/coo.md` (COO dashboard + AI chat)
- `docs/claude/customer-merge-repair.md` (playbook for fixing absorbed customer profiles)

## Guiding Principles

These are durable design principles that apply to **every** feature in this app and to the future TGF Platform. When in doubt, default to these.

1. **Automate toward 0% manual input.** The ultimate TGF Platform is the goal; this Tracker is the live sandbox/bridge that preps for it. Every feature should drive manual user input as close to zero as possible by encoding behavior in rules, defaults, and auto-derived data. Manager-side screens should compute, not collect. If a value can be derived (from rules, from event type, from player count, from history) — derive it, don't ask for it.
2. **Rules-based, not magic.** Behavior that changes by player count, event type, chapter, etc., lives in named rules a non-developer can read and edit through a UI. Hard-coded thresholds in code are a smell — they should be data.
3. **Portable to TGF Platform.** Anything we build here should be implementable on the Platform backend with minimal rework. Avoid baking SQLite-specific quirks or Flask-specific shapes into the domain model. When the same concept exists in both products (e.g. side games matrix), cross-reference the Platform docs and keep the data model aligned.
4. **Past events are frozen.** Anything that affects how an event was scored, paid, or invoiced must snapshot the rules in effect at the time. Editing a template later must never silently change historical events.
5. **Admin-edits, manager-runs, customer-views.** Three layers of access. Admins configure (templates, rules, rates, permissions). Managers operate (run events, see auto-computed numbers). Customers view (their own data, public schedules). Build pages with the layer in mind.
6. **`customer_id` is the one true identity key — use it as the lookup standard everywhere.** No table may track a customer by name alone. Any table row that refers to a customer — enrollment, pool membership, match result, score, prize, RSVP, bracket slot, or anything else — **must** include a `customer_id` column that is a FK to `customers(customer_id)`. A `customer_name` column may exist alongside it as a display label and parse-time snapshot, but **`customer_id` is the authoritative identity for every query, dedup, cleanup, and cross-table join**. Specific rules:
   - **New tables**: add `customer_id INTEGER REFERENCES customers(customer_id)` at design time. Never add it later as a migration afterthought.
   - **Lookups**: when checking whether "Stuart Kirksey" and "Stu Kirksey" are the same person, join through `customer_id` — never compare name strings. Name aliases live in `customer_aliases`; `customer_id` is what makes two rows the same person.
   - **Dedup / cleanup**: any reconciliation pass that collapses duplicate rows or removes orphaned records must group/filter by `customer_id`, not by `customer_name`. The `season_contests` sync cleanup is the canonical example: it groups by `(customer_id, contest_type, season)` and resolves to the canonical name from `customers.customer_name`.
   - **Write paths**: resolve and store `customer_id` at insert time. If resolution fails (new customer not yet in table), add the table to the boot-time backfill registry (`_backfill_customer_id_on_<table>`) so it gets linked on next deploy.
   - **Auto-cleanup integrity**: enrollment-type tables (season_contests, pool members, etc.) should have a reconciliation step in their sync that removes rows where `customer_id` is known but no valid backing purchase exists — cross-checking via `customer_id`, not name. Rows marked `manually_enrolled = 1` are protected from auto-cleanup (admin confirmed, e.g. cash payment).
   - This rule exists because name-only references are the root cause of every "double entry" and "who is this person?" bug we have encountered. Every new feature that skips this rule will produce the same bugs.

## Duplicate Detective

Admin tool at `/admin/duplicate-detective` that detects duplicate
`acct_transactions` rows accumulated from the multiple writers that
record the same financial event (Venmo CSV import, Venmo email parser
via `exp-promoted-N`, in-app refund/credit-payout operations). Use it
when reconciliation variance is unexplained.

- Code: `email_parser/database.py` `find_duplicate_candidates()`,
  `merge_duplicate_pair()`, `reverse_duplicate_merge()`,
  `get_duplicate_merge_audit()`.
- Routes: in `app.py` under `# Duplicate Detective (admin)`.
- First-run default is `dry_run_only` (no DB changes — exports CSV +
  Markdown reports only). Switch mode in the UI dropdown:
  `review_each` (per-card buttons) or `auto_high_confidence` (batch
  button for pairs ≥0.90 confidence with no FK warnings).
- Soft-delete: merging sets the loser to `status='merged'` and
  populates `acct_transactions.merged_into_id` (FK to the survivor).
  Read paths that aggregate (`get_acct_account_balances`,
  `get_reconciliation_dashboard`, MCP ledger entries) exclude merged
  rows by default.
- Reverse a bad merge from `/admin/duplicate-detective/audit`. Reverse
  flips status back to active but does NOT restore FK re-points
  (allocations / reconciliation matches / expense_transactions) — the
  audit row notes record this caveat for manual cleanup.
- See `docs/claude/duplicate-detective.md` for the full pattern matrix,
  confidence scoring, survivor selection rule, and schema additions.

## Workflow rules (always)

These run on every session — no need to remind me.

1. **After every commit/push, bump `static/js/version.js`.**
   - Increment patch version (e.g. `2.12.1` → `2.12.2`); minor bump (`2.12.x` → `2.13.0`) for user-visible features; major bump only for breaking changes.
   - Add a new entry at the TOP of `TGF_CHANGELOG` with: version, today's date (YYYY-MM-DD), short title, and a `changes` array of 1-N bullet strings.
   - Style match the existing entries: each bullet is a self-contained sentence/paragraph, written for someone re-reading later (what changed AND why).
   - Update `TGF_VERSION` to match the new top entry.
   - Include this in the same commit as the code change when feasible; otherwise commit it as a follow-up labelled `chore: bump version to X.Y.Z`.

2. **After every commit/push, update affected documentation.**
   - If the change touches behavior described in any `docs/claude/*.md` sub-doc, update that sub-doc.
   - If the change adds/renames a key file, route, table, or column referenced in `CLAUDE.md`, update the matching section here.
   - Don't write doc updates for trivial fixes (typo, formatting, log-string change). Use judgement: if a future reader could be misled by the existing docs, update them.

3. **Don't ask permission before performing rules 1 and 2** — do them as part of finishing the work. Mention what you updated in the wrap-up summary.

## Deployed URL

**Railway:** `https://tgf-tracker.up.railway.app`

## Inspection Endpoints

When the user asks about transaction data, extraction quality, or anything about what's been parsed — prefer the MCP server tools (below), which carry their own auth. The HTTP endpoints **require an authenticated session as of v2.16.10** (they were previously unauthenticated, which exposed the full customer PII set — names, emails, phones, addresses, DOBs — to any anonymous caller; do not remove the `@require_role` decorators):

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

The `.mcp.json` at the repo root auto-configures it. Just restart Claude Code in this directory and you'll see the `tgf-transactions` server with 36 tools.

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

### Available tools (36)

**Read:** `get_transactions`, `get_transaction_by_id`, `get_statistics`, `get_data_quality_report`, `get_recent_snapshot`, `list_events`, `get_event_registrations`, `list_customers`, `get_customer_details`, `get_customer_profile` (full identity snapshot: canonical row, emails, aliases, statuses, memberships, handicap links, contest enrollments/removals — flags nameless shell profiles), `search_transactions`, `get_season_contest_enrollments`, `get_season_contest_removals`, `get_customer_data_audit` (all-customer identity health sweep: shells, splits, missing/shared emails, dangling ids, unlinked rows, shadowing aliases)

**Financial & Reconciliation:** `get_event_financial_summary`, `get_acct_transactions`, `get_bank_deposits`, `get_reconciliation_detail`, `get_cashflow_summary`, `get_acct_allocations`, `get_godaddy_order_splits`, `get_chart_of_accounts`, `get_mcp_ledger_entries`, `get_venmo_transactions`

**Write:** `update_transaction`, `credit_transaction`, `transfer_transaction`, `undo_credit_or_transfer`, `create_new_event`, `update_existing_event`, `delete_existing_event`, `add_player`, `delete_transaction`, `sync_events`, `run_autofix`, `sync_season_contests`

## Architecture

- **Flask app** in `transaction-tracker/app.py` (~6200 lines, 200+ routes)
- **Email parsing** via Claude in `email_parser/parser.py`. Default model is Haiku
  (`CLAUDE_MODEL` env var); orders whose body matches
  `/TGF\s+MEMBERSHIP|SKU:\s*MEM-[A-Z]-[A-Z]/i` route to `claude-sonnet-4-5`
  (`CLAUDE_MODEL_PREMIUM` env var to override). Membership + EVENT combo orders
  consistently mash up on Haiku — the Sonnet route is the fix. `_call_ai()` logs the
  model selected and whether membership routing fired so the choice is visible in
  Railway logs.
- **Email fetching** via Microsoft Graph API in `email_parser/fetcher.py` — only processes emails with "New Order" subject lines; all processed email UIDs tracked in `processed_emails` table to prevent re-parsing. **Cross-uid dedup gate** in `save_items()` rejects rows whose `(order_id, item_index)` already exists under a different `email_uid` for a real (non-manual) order — Graph occasionally re-keys an already-imported email under a brand-new message id (folder rebuild, mass reply, PWA resync).
- **SQLite DB** at `transaction-tracker/transactions.db` (local is empty; live data on Railway)
- **Database layer** in `email_parser/database.py` (~12000+ lines) — schema, CRUD, allocations, COO context, pairings generator
- **Scheduler** checks inbox every 5 minutes via APScheduler (default;
  override with `CHECK_INTERVAL_MINUTES` env var). Both the transaction
  inbox and the RSVP inbox use a 7-day lookback window when fetching
  from Microsoft Graph (was 90 days). Dedup via `processed_emails`
  ensures already-parsed emails are skipped, so the lookback only
  bounds the Graph query — Anthropic spend is unchanged. The **expense
  classifier** (`check_expense_inbox`) now follows the same rule via the
  `expense_seen_emails` table: every email it touches is recorded once,
  so frequency is decoupled from cost (kept at 5 min, 24/7). Its window
  is 48h steady-state (`EXPENSE_LOOKBACK_HOURS`) with a one-time
  `EXPENSE_BACKFILL_DAYS` cold-start backfill. See
  `docs/claude/expense-workflow.md` → **Dedup & Cost Control**. Boot logs
  a loud warning if `DATABASE_PATH` is unset (dedup memory is ephemeral
  without a Railway volume → re-bills the backfill window every redeploy).
- **Dashboard** at `/` with search, filter, sort, CSV export
- **COO AI** — Claude-powered business intelligence chat with 6 specialist agents
- **TGF Payouts** — tournament payout tracking with screenshot import via Claude Vision
- **Golf Genius sync** via direct HTTP requests in `golf_genius_sync.py` (rewritten from Playwright)
- **MCP Server** in `mcp_server.py` — 36 tools for Claude direct DB access
- **Pairings generator** with seed/lock, cart pairs, and round-robin history.
  Tables (`event_pairings`, `pairing_history`) are created lazily by
  `_ensure_pairing_tables()` on first pairing operation so existing live deployments
  self-migrate. UI has four modes: Player swap, Cart Pair swap, Group swap, and
  **Move** (place a player into a group without swapping). An **Unassigned Players**
  panel appears below groups for any registered players not yet in a group.
- **Boot-time self-healing** — `init_db()` runs idempotent repair functions on every
  startup. Current repairs: `_repair_chalfant_attribution()` and
  `_repair_massey_attribution()` re-attribute transactions absorbed by bad customer
  merges. Each runs in its own try/except so one failure doesn't block others. See
  `docs/claude/customer-merge-repair.md` for the repair pattern and gotchas.
- **Daily digest** (`email_parser/report.py`) — includes a **DB Health Check** section
  with 7 metrics (total items, active items, open parse warnings, open action items,
  credited duplicates, membership mashups, items missing customer ID) plus delta arrows
  (↑/↓) vs the previous day's snapshot.
- **Auth** — PIN-based with roles ranked `view-only` < `manager` < `admin`; `@require_role(minimum)` enforces the hierarchy (as of v2.16.15 — before that only `admin` was checked and view-only sessions passed manager endpoints). Login rate limiter keys on the LAST X-Forwarded-For hop (Railway-appended; the first entry is client-spoofable)
- **`initAuth()`** must be called on every page for nav link visibility (DATABASE link, etc.)

## Audit Log

- `/audit` — admin/QA page for inspecting Microsoft Graph emails vs. parsed `items` rows.
- `GET /api/audit/emails` accepts `days_back` / `max_emails` (defaults lowered to 7 / 25
  for a faster Run Audit), and now also accepts `start_date` / `end_date` for a custom
  window — needed to reach orders older than the longest preset (e.g. a Feb 21 order from
  a May 4 session).
- The `email_uid` lookup falls back to an `order_id` lookup when the uid lookup misses
  (re-keyed Graph emails would otherwise falsely report as "Not Parsed"). The `order_id`
  is parsed from the subject (`#R805080852`).
- `Apply` button next to the filter selects re-runs the audit (the existing Run Audit
  button is in the page header and isn't visually associated with the filter row); auto-
  applies on dropdown change once results are already on screen.
- **Re-extract This Order** — `POST /api/audit/reextract-order` UPDATEs existing rows
  using the original email + AI parser. Force-updates `item_price`, `side_games`, and
  `holes` (`FORCE_UPDATE_FIELDS`).
- **Re-import This Order** — `POST /api/audit/reimport-order` INSERTs rows for orders
  whose items were deleted (e.g. after cleaning up a parser mis-extraction). The cross-uid
  dedup gate prevents duplicates if rows already exist. Renders next to Re-extract on the
  Audit Log card when `comp.email_uid` is present, not `manual-*`, AND `comp.status != "ok"`.
- **Membership-mashup scanner** — `GET /api/audit/membership-mashup-scan` lists every
  active TGF MEMBERSHIP row that has non-null event-side fields (`holes`, `side_games`
  != NONE, `tee_choice`). Those are likely victims of the Haiku parser mash-up.
- **Duplicate-items diagnostic** — `GET /api/audit/duplicate-items-diagnostic` (default
  `since=2026-04-26`) groups by `(order_id, customer, item_name, item_price)` to surface
  cross-email-uid duplicates. The companion `POST /api/audit/delete-phantom-duplicates`
  is kept as a quiet safety net; UI button removed since the cross-uid dedup gate
  prevents recurrence.

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
- The summary's customer name comes from `pickBuyerRow(group)` in `dashboard.js`
  — NOT `group[0].customer`. Per the parser's `_expand_quantity_rows`, only
  the buyer's row keeps `customer_email`; extras have it cleared and get a
  `"Purchased by <buyer>"` note. `pickBuyerRow` picks the row with
  `customer_email` set and no Purchased-by note, then falls back to first
  non-extra, then first row. Using `group[0]` directly would attribute the
  whole order to whichever playing partner happened to sort first
  alphabetically (e.g. a 3-spot Hamilton order shown as "Chris Best").

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
- `email_parser/memberships.py` — `customer_memberships` schema/backfill, renewal detection, reminder email templates, daily scheduler job, signed roster opt-in/out tokens
- `email_parser/fetcher.py` — Microsoft Graph email fetching
- `email_parser/report.py` — Daily digest email builder + sender
- `email_parser/rsvp_parser.py` — Golf Genius RSVP email parser (regex, no AI)
- `templates/index.html` — Transactions dashboard
- `templates/events.html` — Events management + Tee Time Advisor + Financial tab (hybrid server/client rendering)
- `templates/customers.html` — Customer directory + roster import + 5-tab detail (Transactions, Scores, Winnings, Points, Info)
- `templates/handicaps.html` — Handicap management page
- `templates/participation.html` — Participation analysis (last-played, frequency, trend) + re-engagement email composer; see `docs/claude/participation.md`
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
- `mcp_server.py` — MCP server (36 tools for Claude direct DB access)
- `email_parser/timezone_utils.py` — `now_central()`/`today_central()`/
  `today_central_str()` (pytz America/Chicago, naive). See **Timezone** below.
- `email_parser/ops_alerts.py` — `maybe_alert_anthropic_billing(exc)`:
  call it from any "Claude call failed" except handler. Emails the owner
  (env `ANTHROPIC_ALERT_EMAIL_TO` → `COO_EMAIL_TO` → `EMAIL_ADDRESS`) when
  the org is out of API credit or the key is dead. Throttled to 1/6h via
  the `system_alert_state` table; never raises. Already wired into
  `expense_parser._call_llm`, `parser.parse_emails`, and
  `app._check_inbox_background` — add a call to any new recurring
  Anthropic path you introduce.

## Timezone (IMPORTANT — Railway runs in UTC)

The container clock is UTC, so any naive `datetime.now()`/`utcnow()`/
`date.today()` used for a **calendar-day boundary or a stamped business
date** rolls over at 00:00 UTC ≈ 6–7 PM US/Central. For every user-facing
"what day is it", date default (order_date, transaction_date, deposit/refund
date), "today/this month" dashboard window, daily-email date label, and
membership "expires today" check, use `email_parser/timezone_utils.py`
(`now_central` / `today_central` / `today_central_str`).

Do **not** Central-ize: audit `created_at` columns
(SQLite `datetime('now')`, stored and read back consistently in UTC),
`report.py get_recent_items()`'s rolling 24h cutoff (it compares against
the UTC `items.created_at` — Central-izing it would add a 5h skew), signed
roster token TTLs in `memberships.py` (epoch, correctly UTC), and the many
benign elapsed-time/logging/rate-limit `datetime.now()` calls. Never rewrite
stored historical timestamps — fix only new-record defaults and live
"today"-relative computations so the **past-events-are-frozen** principle holds.

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

## Identity drift watch (IMPORTANT for any code that reads `items.*`)

`items.customer_email` / `customer_phone` / `first_name` / `last_name` / `chapter` /
`user_status` are historical snapshots captured per-order. **Never read them directly**
for customer-facing operations (sending email, building previews, derived UI badges)
without going through one of:

- `resolve_player_email`, `resolve_player_phone`, `resolve_player_name`,
  `resolve_player_chapter`, `resolve_player_status` — five canonical resolvers in
  `database.py` that look up the canonical value via `items.customer_id` and fall back
  to `items.*` only when nothing canonical exists. Always open the resolver's connection
  with `get_connection()` and close it with `conn.close()` (never use
  `_connect(db_path).__enter__()` without holding the contextmanager reference — see
  `docs/claude/customers.md`).
- `_resolve_player_email(item, conn=None)` — top-level helper in `app.py` used by every
  customer-facing send path (`_send_rsvp_credit_alerts`, `_build_balance_due_email`,
  `/api/items/<id>/send-payment-reminder`, the bulk-send composer). Skips rows that
  resolve to no email at send time, so manually-added RSVPs whose email lives only in
  `customer_emails` are no longer excluded.

`save_items()` raises `EMAIL_DRIFT` / `PHONE_DRIFT` parse warnings when a new GoDaddy
order's value differs from the canonical record (canonical wins; the manager sees the
discrepancy in the COO action-items banner). `resolve_low_risk_email_drift_warnings()`
(boot step) auto-resolves an `EMAIL_DRIFT` when the drifted email plausibly belongs to
the same person (surname token in the local-part, or same address family / typo of the
canonical) and captures it into `customer_aliases` — the drift guard overwrites the order
email before insert, so `capture_email_aliases_from_items()` never sees it. Genuine
stranger-email drift (the cross-person contamination class) stays open for human review.
`chapter` is intentionally NOT drift-checked:
`items.chapter` is the event/course location while `customers.chapter` is the member's
home chapter, so cross-chapter play would drift every time and the canonical overwrite
would corrupt the correct event-location value. A boot step resolves any historical open
`CHAPTER_DRIFT` warnings.

Three idempotent boot migrations enforce the same shape:
`capture_email_aliases_from_items` (promotes typos to aliases),
`_heal_items_identity_fields` (Phase 1B; flattens stale items.* values to canonical), and
`_migrate_normalize_customer_name_case` (proper-cases names, propagates to items rows).

## items.handicap is NOT fed by orders

The LLM email parser no longer extracts `handicap` from order emails — `items.handicap`
stays empty on every new row. The canonical source is `handicap_rounds` joined via
`handicap_player_links`. Stale `items.handicap` values on old order rows look
authoritative but don't update when the player's real handicap changes. See
`docs/claude/handicaps.md`.
