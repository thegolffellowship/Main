# Bank Reconciliation System

## Architecture
Three new tables link bank statement data to the accounting ledger:
- `bank_accounts` → `bank_deposits` → `reconciliation_matches` → `acct_transactions`

## Import formats
- **Chase CSV**: auto-detected by "Posting Date" header. Imports credits only.
  GoDaddy deposits tagged by description containing "GODADDY".
- **Venmo CSV**: auto-detected by "Datetime" header. Imports completed positive transactions.
- **PDF**: text extracted via `pdfplumber`, parsed by Claude AI into date/description/amount.
- **Idempotency**: deduplicates on `account_id + deposit_date + amount + description`.

## Auto-matching (`run_deposit_auto_match`)
Runs after every import and on-demand via "Auto-match All" button.
- **GoDaddy batch (subset-sum)**: parses the `MM/DD` batch date from
  `"GoDaddy Payments Dep MM/DD ..."` (with year-rollover handling), then runs an exact
  subset-sum search against `godaddy_order` candidates that haven't been claimed earlier
  in the same run.
  - **Tight window:** `batch_date - 1 day .. batch_date`. Falls back to
    `batch_date - 2 .. batch_date + 1` if the tight pass finds no subset.
  - **Subset-sum:** `_subset_sum_match()` does an exact recursive search with suffix-sum
    pruning for `n ≤ 25` candidates, and a greedy descending fit beyond that. Tolerance
    is **$0.50, computed in integer cents.**
  - **Confidence:** `0.92` (matched) on the tight window, `0.75` (partial) on the
    widened fallback.
  - **`claimed_txn_ids` set** is scoped to the run — already-attributed orders are
    removed from later deposits' candidate pools so consecutive batches don't
    double-count. The previous `±5 day` `sum every order in window` heuristic always
    overshot, which is why all recent GoDaddy deposits were returning 0 matches.
- **Venmo**: exact amount match + customer name in description = 0.95.
  Amount only = 0.70, flagged for review.
- **Negative deposits (bank debits / CC charges)**: matches against
  `entry_type='expense'` ledger entries. `ABS(dep_amt)` compared against expense
  `COALESCE(amount, total_amount)`. ±$1 tolerance, ±10 day date window.
  Confidence: 0.85 (desc+amount), 0.65 (desc only), 0.55 (amount only).
- **Zelle/other**: amount + date ±1 day, always flagged for manual confirm (0.60).
- Matched transactions get `status = 'reconciled'` in `acct_transactions`.

## `bank_deposits.account_id` — unified around `acct_accounts`

Both import paths into `bank_deposits` now store `acct_accounts.id` in `account_id`. The
Venmo CSV path used to look the id up from `bank_accounts` instead, so half the deposits
silently dropped out of the dashboard, the auto-match join, and the MCP tools.

- `import_venmo_statement` resolves the Venmo account from `acct_accounts`.
- One-time `init_db` migration rewrites legacy rows that still reference the seeded
  `bank_accounts.Venmo` id.
- `get_bank_deposits` (`database.py`) and the `get_bank_deposits` /
  `get_reconciliation_detail` MCP tools `LEFT JOIN acct_accounts` so any remaining stale
  rows still surface.
- `run_deposit_auto_match` falls back to the deposit's `source` field when the
  `account_type` lookup misses, so Venmo / GoDaddy branch selection keeps working.
- MCP server: dropped the dead `get_reconciliation_summary` (legacy `bank_statement_rows`
  path), exposed `get_reconciliation_dashboard`, and re-pointed `get_reconciliation_summary`
  at `get_monthly_reconciliation`. `mcp_server_remote.py` mirrors the changes against
  the corresponding `/api/reconciliation` routes.

## GoDaddy Reconciliation — net_deposit as amount
Bank statements show the net deposit (after merchant fee). `acct_transactions` rows for
GoDaddy orders now use `net_deposit` (= `total_amount - merchant_fee`) as the comparison
amount in auto-matching, so a $222.53 order with a $6.75 fee matches the $215.78 bank credit.

## Accounting Ledger Improvements

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

## Reconciliation UI (`/accounting/reconcile`)
Three tabs — the standalone page, kept for power-user workflows and the
Monthly Summary CSV export:
1. **Account Dashboard** — cards per account: book/bank balance, variance, unmatched count
2. **Match Queue** — two-column layout: unmatched deposits (left) vs unreconciled transactions (right).
   Click deposit to highlight amount-similar transactions. Manual match + batch-match + auto-match.
3. **Monthly Summary** — income/expense by category, reconciliation %, CSV export.

## Inline Match Queue (v2.8.0) — lives inside the Ledger tab
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

## Cash Flow (`/accounting/cashflow`)
90-day rolling weekly view (configurable: 8/13/26 weeks).
Columns: expected income, confirmed (banked), projected expenses, actual expenses, net, running balance.
Red warning rows where projected expenses exceed confirmed income.

## Visual indicators
- **Events Financial tab**: "Reconciliation: X of Y transactions confirmed in bank ($Z matched)"
  Loaded async via `/api/reconciliation/event/<name>`.
- **Transactions page**: colored dot on each row:
  - Yellow = active item, awaiting bank match
  - Grey = comp, RSVP, or inactive (no bank match expected)

## Key endpoints
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
| `/api/admin/run-recon-drift-fix` | POST | admin | Apply 2026-04 recon-drift fixes (see below) |
| `/api/accounting/auto-match-venmo-balance-due` | POST | admin | Re-runs the Venmo IN matcher on demand |
| `/api/admin/reconcile-orphan-venmo` | POST | admin | Sweeps existing credit-transfer rows for orphan Venmo +PAY items (`?dry_run=1` supported) |
| `/api/audit/duplicate-items-diagnostic` | GET | admin | Group duplicate items by `(order_id, customer, item_name, item_price)` (default `since=2026-04-26`) |
| `/api/audit/delete-phantom-duplicates` | POST | admin | One-shot dedup cleanup (no longer surfaced in UI) |
| `/api/audit/membership-mashup-scan` | GET | admin | Find suspect TGF MEMBERSHIP rows that have non-null event-side fields |
| `/api/audit/reextract-order` | POST | admin | Re-fetch and re-parse an order's email; UPDATEs existing rows |
| `/api/audit/reimport-order` | POST | admin | Re-fetch and re-parse an order's email; INSERTs rows (cross-uid dedup gate prevents duplicates if rows already exist) |

## Recon-Drift Fix (2026-04 maintenance)

`apply_recon_drift_fix()` in `email_parser/recon_drift_fix.py` is a structured replay of
the 2026-04 `scripts/fix_recon_drift_2026_04.py` remediation. Returns a dict (not
prints), idempotent (every UPDATE has a precondition predicate;
`create_entry_from_deposit` checks `source_ref`; `run_deposit_auto_match` uses
`INSERT OR IGNORE` on `reconciliation_matches`).

Steps:
1. Void duplicate Municipal Golf promotion (`acct_transactions.id=2740 → status='merged'`)
2. Re-point `expense_transactions.acct_transaction_id` at the surviving promotion
3. Restore null `entry_type` / `amount` / `source` on Canyon Springs (`id=2742`)
4. Backfill `entry_type=type, amount=total_amount` on every promoted row whose
   `source_ref LIKE 'exp-promoted-%'` and has `entry_type IS NULL` — copies from the
   legacy `type` column instead of hardcoding `'expense'`, so any promoted Venmo
   `received` row keeps `entry_type='income'`.
5. `run_deposit_auto_match(account_id=3)` — first pass.
6. `create_entry_from_deposit(...)` for whichever Canyon Springs deposit (760 or 761)
   the auto-match did NOT claim.
7. `run_deposit_auto_match(account_id=3)` — final pass.

**Per-step transactions:** each UPDATE opens its own connection, runs, commits, closes —
earlier fixes are not rolled back if a later fix raises. Every step is wrapped in
`try/except`; failures land in `result["step_errors"]` and execution continues.

**Upstream fix in `promote_expense_to_ledger`:** the INSERT into `acct_transactions`
was missing `entry_type`, `amount`, and `event_name` columns, so promoted rows landed
with NULL `entry_type` and `amount` — invisible to `run_deposit_auto_match`'s
negative-deposit branch (filters `WHERE entry_type = 'expense'`). The INSERT now maps
`txn_type → entry_type` 1:1 and copies the existing amount into both `total_amount`
and `amount`. `event_name` is sourced from `lookup_event` (caller arg or the
`expense_transactions` row).

**Upstream fix in `create_entry_from_deposit`:** `acct_splits.entity_id` is `NOT NULL`,
but the function passed NULL when the caller didn't supply `entity_name` (or the name
didn't resolve), causing `NOT NULL constraint failed: acct_splits.entity_id`. Added a
fallback: if `entity_id` is still None after the name lookup, pick the first active row
from `acct_entities`. Default-entity fallback is preferred over loosening the schema
since the column is referentially required by downstream P&L / allocation code.

UI: maintenance panel in the Database page sidebar with a "Run Recon Drift Fix
(April 2026)" button. Click → confirm → `POST /api/admin/run-recon-drift-fix` → modal
shows the before/after fixes, rowcounts, backfill diagnostic, both auto-match results,
and the `create_entry` result, plus a collapsible raw-JSON view for audit. Renders
`result["step_errors"]` in a red banner when any step failed, green banner when all
succeeded.
