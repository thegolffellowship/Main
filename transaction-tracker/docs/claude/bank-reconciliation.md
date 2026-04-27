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
