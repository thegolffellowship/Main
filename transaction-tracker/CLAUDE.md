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
- `docs/claude/scoring.md` (scorecards, course DB w/ tees, formula layer, GG extraction)
- `docs/claude/member-portal.md` (member-facing profile + email summaries — proposed design)
- `docs/claude/customer-merge-repair.md` (playbook for fixing absorbed customer profiles)
- `docs/claude/state-of-the-tracker.md` (Platform-facing brief for the claude.ai Golf Fellowship Project — refresh after major build waves)
- `docs/claude/side-games.md` (side-games RATIFIED SPEC v1.0 — buy-ins, game rules, prize-matrix derivation; open flags at bottom)
- `docs/claude/game-engine.md` (Game Creator engine + untether-from-GG staging — versioned game/season-contest definitions; design of record)
- `docs/claude/gg-history.md` (GG archive coverage map: 29 portals SA 2016–2025 / Austin 2019–2025 / DFW 2020–2024 / Houston 2021–2024 / one-offs, the proven widget-route ingest recipe, and the proposed gg_history_* schema — schema pending Kerry rule-3b ratification)
- `docs/claude/pairings.md` (TGF Pairing Standards — Kerry's ruleset of record for the pairings engine, 2026-07-12; CA docs merge + pairing_history amendment pending)
- `docs/claude/handicap-projection.md` (Task #16 — self-computed playing handicap from index + selected tee; SHADOW/parity-validated 100% vs GG allocation, awaiting Kerry+CA ratification; `handicap_calc.py`)

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

3b. **Explicit ratification BEFORE shipping high-stakes changes (mailbox #47, Kerry via platform-claude, 2026-07-09).** Anything touching **money, schema, member-facing behavior, or scope** needs an explicit "Kerry ratifies X" checkpoint BEFORE it ships — two-Claude consensus (tracker-claude + design-claude/platform-claude agreeing) is NOT Kerry's approval. Style-tier items (fonts, colors, spacing, hit targets, IA labels) may converge fast and be flagged for ratification after the fact.

3c. **Role lanes (Kerry-ratified via mailbox #50, 2026-07-09 — supersedes the earlier "content/data manager" framing):**
   - **tracker-claude** (this repo): owns and builds the Tracker. Authoritative on what's actually live in the app (data, IA, current behavior) and on implementation within the Tracker's stack. Ships on own judgment; pauses for Kerry's ratification per rule 3b. This authority is scoped to the TRACKER — once the Platform exists as a live system, Platform data-model questions route through platform-claude (architecture) and Marcus, with tracker-claude as an important input, not default owner.
   - **design-claude**: owns visual/UX design + prototyping (Tracker, eventually Platform). Authoritative on typography, color, spacing, interaction states. NOT authoritative on business vocabulary or IA — verifies contest names/tabs/structure with tracker-claude before speccing.
   - **platform-claude**: owns the future Platform's architecture, scope, 8-stage roadmap, and continuity between systems (Tracker decisions/data models/lessons carry forward). Authoritative on v1.0/v1.5/v2.0 scope calls and Stage-gate status. Defers to tracker-claude/design-claude on live Tracker specifics.
   - **Kerry**: final ratification on anything crossing money, schema, member-facing behavior, or scope, in any lane; tie-breaker.

4. **Platform dialogue mailbox.** At the START of a session, read the mailbox for new posts (`read_platform_dialogue`, since the last id you've seen). At the END of a substantive session, post a digest (author='tracker-claude'): what shipped, findings that affect Platform planning, open questions. Refresh `docs/claude/state-of-the-tracker.md` after major build waves so `get_tracker_docs` always serves a current brief.
   **Three-party lane convention (v2.54.2, Kerry — mailbox post #42):** authors are `tracker-claude` (this repo, implements), `platform-claude` (claude.ai Project, plans the TGF Platform), `design-claude` (Claude Design, prototypes + design standards), `kerry`. Every post starts with a `TO:` line; only act on posts addressed to you. Topic prefixes: `design-*`, `platform-*`, `session-digest`. **Design handoffs are delivered THROUGH THE MAILBOX** (v2.54.4 — design-claude can't write to other Claude Design projects): topic `design-handoff`, one post per file part with header lines `HANDOFF: <name>` / `FILE: <name> (part i/N)` then `---8<---` then raw content; >~60KB files split at line boundaries; a final `HANDOFF COMPLETE` manifest lists files/parts/char counts for reassembly verification (protocol spec: mailbox post #45). Prototypes must be self-contained HTML/CSS referencing DS assets by name only — the "TGF Design System" Claude Design project is READ-able via DesignSync for assets/tokens. OneDrive `Design Standards/` is the fallback for images (its connector blocks `.svg`).

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

The `.mcp.json` at the repo root auto-configures it. Just restart Claude Code in this directory and you'll see the `tgf-transactions` server with 61 tools.

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

### Available tools (61)

**Read:** `get_transactions`, `get_transaction_by_id`, `get_statistics`, `get_data_quality_report`, `get_recent_snapshot`, `list_events`, `get_event_registrations`, `list_customers`, `get_customer_details`, `get_customer_profile` (full identity snapshot: canonical row, emails, aliases, statuses, memberships, handicap links, contest enrollments/removals — flags nameless shell profiles), `search_transactions`, `get_season_contest_enrollments`, `get_season_contest_removals`, `get_customer_data_audit` (all-customer identity health sweep: shells, splits, missing/shared emails, dangling ids, unlinked rows, shadowing aliases), `list_customer_contacts` (bulk name/chapter/status/email/venmo/phone export for cross-referencing external rosters)

**Financial & Reconciliation:** `get_event_financial_summary`, `get_acct_transactions`, `get_bank_deposits`, `get_reconciliation_detail`, `get_cashflow_summary`, `get_acct_allocations`, `get_godaddy_order_splits`, `get_chart_of_accounts`, `get_mcp_ledger_entries`, `get_venmo_transactions`

**Write:** `update_transaction`, `credit_transaction`, `transfer_transaction`, `undo_credit_or_transfer`, `create_new_event`, `update_existing_event`, `delete_existing_event`, `add_player`, `delete_transaction`, `sync_events`, `run_autofix`, `sync_season_contests`

**Scoring (v2.23.0):** `import_gg_scorecards` (walk a GG tournament page into scoring_rounds/scoring_holes + course tees), `get_scoring_rounds`, `get_scorecard_detail` (facts + formula-layer derivations), `verify_scoring_round_tool` (parallel-run checks vs GG's numbers), `get_courses` (course DB w/ tees), `get_differential_parity_tool` (Phase 2 parity proof vs GG handicap export), `determine_tgf_mvp` (v2.33.0 — City MVP per linked same-day event from our scorecards + formula layer, TGF MVP winner comparison; see `docs/claude/events.md`). See `docs/claude/scoring.md`.

**Platform collaboration (v2.32.0):** `get_tracker_docs` (list/read CLAUDE.md + docs/claude/*.md — the authoritative built-state picture for the claude.ai Golf Fellowship Project), `get_side_games_matrix` (the LIVE prize matrix from app_settings — the repo's games-matrix.js is a seed that UI saves rewrite only on ephemeral disk, so it drifts; never audit from the seed), `read_platform_dialogue` / `post_platform_dialogue` (the tracker-claude ↔ platform-claude mailbox: durable two-way planning channel in the `platform_dialogue` table; boot seeds a welcome post). See **Workflow rules** #4.

**External:** `probe_golf_genius` — fetch a PUBLIC `*.golfgenius.com` page server-side (no login) and return parsed title/headings/links/tables/text/raw. Host-allowlisted incl. redirect targets (SSRF guard). Exploration path for GG results import; helpers `fetch_public_page`/`parse_page_structure` live in `golf_genius_sync.py`.

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
  so frequency is decoupled from cost. Because it's cost-neutral it runs
  MORE often than the order inbox — **every 2 min** by default
  (`EXPENSE_CHECK_INTERVAL_MINUTES`, v2.81.1) so Venmo payout receipts flip
  the payout to PAID within a couple minutes even when the admin pays
  outside the app (no in-app Pay tap → no fast 75s/180s sweep). Its window
  is 48h steady-state (`EXPENSE_LOOKBACK_HOURS`) with a one-time
  `EXPENSE_BACKFILL_DAYS` cold-start backfill. See
  `docs/claude/expense-workflow.md` → **Dedup & Cost Control**. Boot logs
  a loud warning if `DATABASE_PATH` is unset (dedup memory is ephemeral
  without a Railway volume → re-bills the backfill window every redeploy).
- **Landing page is EVENTS** (v2.44.0, Kerry): `/` 302-redirects to
  `/events` (or to `/transactions?<qs>` when query params are present, so
  old `/?txn=` deep links keep working); the Transactions dashboard lives
  at `/transactions` (search, filter, sort, CSV export). auth.js's
  fresh-launch redirect and manifest.json start_url also point at
  `/events`; admin-page guards for non-admins redirect to `/events`.
  The fresh-launch redirect stays put ONLY for real deep links
  (`?txn=`/`?item=`/`?cid=`, v2.49.3) — iOS resurrects the PWA's last
  URL on relaunch, and a blanket any-query-string exemption made stale
  filter URLs (e.g. `/customers?name=…`) the landing page.
- **COO AI** — Claude-powered business intelligence chat with 6 specialist agents
- **TGF Payouts** — tournament payout tracking with screenshot import via Claude Vision
- **Golf Genius sync** via direct HTTP requests in `golf_genius_sync.py` (rewritten from Playwright). The nightly 02:00 job is removed as of v2.18.0 (never established a reliable connection) — the live path is the manual CSV export (`/api/handicaps/export-csv`) the admin uploads in the GG UI; see `docs/claude/handicaps.md`
- **MCP Server** in `mcp_server.py` — 61 tools for Claude direct DB access
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
- **Auth** — PIN-based with roles ranked `member` < `view-only` < `manager` < `admin`; `@require_role(minimum)` enforces the hierarchy (as of v2.16.15). **`member` is the PUBLIC read tier (v2.53.0, Kerry)**: `@require_role("member")` endpoints serve anonymous visitors with no PIN — only PII-free GET reads may declare it (season contests, points races, monthly points, handicaps, scoring reads, match-play GETs). `/api/customers` (emails/phones) and `/api/events` (course_cost/markup) must stay at view-only+. The pinless member pages live at `/member` → **lands on `/member/spotlight`** (Kerry 2026-07-14, v2.85.0: member view is player-first) + `/member/contests` + `/member/handicaps` (spotlight.html/contests.html/handicaps.html rendered with `member_mode=True`): `window.MEMBER_MODE` makes auth.js skip the login modal (currentRole stays null so manager/admin UI stays hidden), the member nav is **SPOTLIGHT | LEADERBOARD | HANDICAPS** (LEADERBOARD is the Season-Contests page relabeled for members; the admin/manager nav keeps "Season Contests", and the paid "Enter Season Contests" signup CTA is unchanged), and player-name links to /customers render as plain text. `manifest-member.json` start_url + the first-visit welcome nudge (member-nudges.js) follow the landing to Spotlight. PINs (v2.47.0, Kerry): `ADMIN_PIN`→admin; `AUSTIN_MANAGER_PIN`/`SA_MANAGER_PIN`→manager with `session["chapter"]` set (chapter managers land pre-scoped: Events chapter tab, Contests race, Customers filter, Participation chapter); `VIEWONLY_PIN`→view-only; the LEGACY shared `MANAGER_PIN` is demoted to view-only. View-only nav = EVENTS | CONTESTS | HANDICAPS only; /transactions, /customers, /rsvps, /participation redirect view-only sessions to /events. Login rate limiter keys on the LAST X-Forwarded-For hop (Railway-appended; the first entry is client-spoofable)
- **`initAuth()`** must be called on every page for nav link visibility (DATABASE link, etc.)
- **External links open in a new window (Kerry-ratified 2026-07-20).** A capture-phase click handler at the bottom of `auth.js` stamps `target="_blank" rel="noopener"` on any off-origin http(s) anchor app-wide — do NOT add per-link `target` attributes for external URLs (and don't remove the handler). Protocol handoffs (`venmo://`, `mailto:`, `tel:`) are deliberately excluded.

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
- URL parameter `?txn=<item_id>` (on `/transactions`; bare `/?txn=` redirects there) scrolls to and highlights a specific transaction row
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
- `email_parser/match_play.py` — pure Match Play engine (versioned-config evaluation: structure, seeded bracket w/ byes, exact-cents payout ladders); seed = the ratified 29-column matrix; tests in `test_match_play.py`; see `docs/claude/game-engine.md`
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
- `templates/moneyflow.html` — Monthly Money Flow (admin): pass-through vs
  TGF-keep waterfall per month over the allocations layer (v2.143.0,
  mailbox #242; see `docs/claude/unified-financial-model.md`)
- `templates/coo.html` — COO Dashboard: action items, financial snapshot, review queue, AI chat
- `templates/tgf.html` — TGF Payouts: events, golfers, screenshot import,
  Unpaid work queue, and the **REFUNDS console** (admin, v2.108.0 —
  OUTSTANDING/IN FLIGHT/COMPLETED credit refunds via
  `GET /api/refunds/overview` → `get_refunds_overview`; see `docs/claude/events.md`)
- `templates/traffic.html` — Member Traffic (admin): anonymous open/click
  counters from the pinless member pages (`member_analytics` table; beacon in
  auth.js under `window.MEMBER_MODE`; POST /api/member-metric is the only
  anonymous write in the app — whitelisted events, truncated fields, no PII)
- `templates/spotlight.html` — Player Spotlight (ADMIN PREVIEW v1): name
  typeahead → per-player overview (handicap, stats, standings in every race,
  projected LSC seat, winnings). PII-free payloads, member-tier-destined —
  see `docs/claude/member-portal.md`
- `templates/gg_history.html` — GG History review (admin): pending-names
  identity queue (Link/Guest/Not-a-person), per-portal archive coverage,
  standings browser; backend in `email_parser/gg_history.py` (see
  `docs/claude/gg-history.md`)
- `templates/database.html` — Admin database browser
- `templates/changelog.html` — Version changelog
- `static/js/dashboard.js` — Transactions page logic (largest JS file)
- `static/js/coo-dashboard.js` — COO Dashboard logic: chat, agents, editable values, action items
- `static/js/auth.js` — PIN auth + role management + sticky nav offsets
- `static/js/games-matrix.js` — Prize matrix data (9-hole & 18-hole, 2-64 players)
- `static/js/points-render.js` — Shared Points Races drill-down renderers (Contests page + Customers Points tab); injects its own table CSS
- `static/js/version.js` — Version number + changelog data
- `static/js/chat-widget.js` — Support/feedback chat widget
- `golf_genius_sync.py` — Golf Genius handicap sync via HTTP
- `mcp_server.py` — MCP server (61 tools for Claude direct DB access)
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

## TGF Design System rollout (v2.54.0 — Phase 1)

Claude Design's handoff (Kerry's OneDrive → `Design Standards/design_handoff_transaction_tracker`)
defines the target look: dark `#1B1B1B` top nav (TGF icon + "Tracker" +
version chip; uppercase **Bitter**-serif nav links; orange role pill),
white sub-tab bar with admin-only tabs rendered as right-aligned solid
orange pills, Bitter headings/stats + Helvetica Neue body, pill buttons
(inputs stay 8px radius + orange focus ring), chapter-colored band
headers, and a payout **category color map**. **Typography rule
(RATIFIED, Kerry 2026-07-09, mailbox #44): Bitter serif only for
headings, nav/CTA labels, eyebrows, and large stat numerals; dense data
(table cells, list rows, numeric columns) is system sans with
tabular-nums — be judicious with Bitter.** `templates/tgf.html` is the
Phase 1 reference implementation (dark nav, sub-tab pill convention, and
the GOLFERS "Command Ledger": dark leaderboard rail + golfer winnings
detail with collapsible chapter bands). Tokens live in `dashboard.css`
`:root` (`--surface-dark`, `--money-green[-dark]`, `--cat-*`). The
handoff README wrongly assumes a Next.js/Tailwind stack — translate to
this repo's Flask/Jinja/vanilla stack, matching the visuals exactly.
**Nav Shell v2 is LIVE app-wide (v2.55.0** — handoff nav-shell-070926,
Kerry-ratified mailbox #58): every page renders the dark nav via the
shared `templates/_shell_nav.html` include (+ `static/css/shell.css`,
`static/js/shell.js`), gated by the **`SHELL_V2` env var kill switch**
(default on; flip to 0 on Railway to instantly revert all pages to the
legacy headers preserved in their `{% else %}` branches — remove those in
a cleanup release only after Kerry's bake-in sign-off). Shell rules:
mobile hamburger drawer for manager/admin; **Kerry's drawer threshold
rule** — roles with ≤3 sections (member, view-only) get inline tabs, no
drawer; page-ops buttons live in the `SHELL_OPS` toolbar row (tiered
pills: primary filled dark / secondary 2px outline / maintenance gray /
destructive red outline isolated right) with a "⋯ Actions" bottom sheet
on mobile — **ops never go in the drawer**; one global dropdown pattern
(`.shell-menu`). auth.js drives role gating for shell links
(`.shell-nav-links a`, `.shell-drawer-nav a`) and calls
`window.shellApplyRole`. Official TGF icon marks: `static/tgf-icon.svg`
+ `static/tgf-icon-white.svg`. shell.js also provides **pull-to-refresh**
(v2.82.0): app-wide, but gated to the iOS installed PWA
(`navigator.standalone`) where the native gesture is absent — a mobile
browser and Android already have native PTR, so custom PTR there would
double-fire. Pull down at page top past a 70px threshold → `location
.reload()`; a `.tgf-ptr` spinner (shell.css) follows the drag; pulls
starting inside a drawer/sheet/dialog (`SKIP` selector, `.no-ptr` /
`[data-ptr-skip]` opt-out) are ignored. The Contests/Handicaps CONTENT redesign
is the next design-claude handoff, built into this fixed shell.

## Desktop width + density standard (v2.130.0 — Kerry-ratified 2026-07-20)

**1080px is the desktop content width for ALL pages — Admin, Manager, and
Member.** The global `main` rule in `dashboard.css` caps and centers every
page's work column (`max-width: 1080px; margin: 0 auto`); the dark nav
header/shell stays full width. Do NOT add page-local `main` width overrides
(wider or narrower) — `/me` (720px personal page) and the print sheets
(cart signs, starter sheet, which don't load dashboard.css) are the only
exceptions. **Admin table density is the app-wide default**: global
`thead th` 4px / `tbody td` 5px vertical padding, 10px horizontal — the
ratified TGF-console density ("functional, not all this beautiful white
space"). Pages with their own table CSS keep their local values.

## Standard color palette (v2.49.0)

Kerry's ratified brand palette lives as CSS vars in `static/css/dashboard.css`
`:root`: TGF Orange `#E87C3E` is `--primary` (hover `--primary-hover` `#D06B2E`),
text `#1B1B1B` on `#F8F8F8`/white surfaces, border `#E5E7EB`, muted `#6B7280`
(FG2 `--text-body #4B5563`, FG4 `--text-placeholder #9CA3AF` defined for future
use). Chapter semantic layer: `--chapter-austin #BF5700` (white text),
`--chapter-sa #D3DDE4` (dark text, alt `--chapter-sa-alt #8FA8B8`),
`--chapter-national #374151` — applied to the Events/Handicaps chapter pills.
PWA `theme-color` metas + manifest are TGF orange. Do not reintroduce royal
blue for interactive/CTA states. EXCEPTION (v2.49.2, Kerry): HYPERLINKS keep
the universal hyperlink blue — `--link #2563eb` / `--link-hover #1d4ed8` on
`.cell-link` (and the already-blue participation links). Table-row text that
is not a hyperlink, a badge, or an action is plain black.

## Global CSS gotcha: tbody td is nowrap everywhere (IMPORTANT)

`static/css/dashboard.css` declares a global `tbody td { white-space: nowrap; }`
(transactions-table heritage). Every table on every page inherits it — text in
ANY table cell will never wrap, and block children inside a cell inherit nowrap
too. This silently defeated `overflow-wrap`/`word-break` on the Contests
drill-down for several releases (v2.28.9–v2.28.11) before being identified.
If a new page needs wrapping table text, override with
`white-space: normal` on that table's `td` (see `.enrollment-table td` in
contests.html) and set nowrap back inline on the specific cells that need it
(dates, numbers).

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
