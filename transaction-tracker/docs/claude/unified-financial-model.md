# Unified Financial Model (Issue #242)

## Architecture: acct_transactions as single source of truth

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

## GoDaddy Order-Level Accounting (NEW)

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

## Financial tab P&L model

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

## Critical: Transaction fees vs GoDaddy merchant fees
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

## Parser: item_price extraction
- `item_price` must come from the **Subtotal** or **SKU line** in the GoDaddy email,
  NEVER from the "MEMBER STATUS: MEMBER = $XX" line (that's just the base membership rate
  and excludes side game add-ons). See parser.py extraction prompt.
- `transaction_fees` is parsed directly from the "Transaction Fees 3.5%: $X.XX" line.
- Re-extract force-updates `item_price`, `side_games`, and `holes` (FORCE_UPDATE_FIELDS).

## Operations that create accounting entries
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

## Key functions
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

## Credit/transfer/refund actions
- Credit transfer items now show Credit, WD, and Refund buttons (same as regular items)
- Partial refund supports custom dollar amount input (for credit overpayments like $29)
- **Refund methods: GoDaddy, Venmo, Zelle, Check, PayPal.** PayPal-method refunds route
  the `acct_transactions` entry to a `PayPal` account (parallel to how Venmo refunds
  route to `Venmo`); all other methods route to `TGF Checking`. Supported by
  `api_refund_item`, `api_payout_credit`, and `api_partial_refund_item` plus the
  `payout_credit`, `refund_item`, and partial-refund flows in `database.py`.
- Transfer items carry the original price (e.g., "$102.00 (credit)") not "$0.00 (credit)"
- **Transfer cascade.** `transfer_item` sums the parent's `item_price` with every active
  `+PAY` child and creates ONE new credit-transfer item at the target with the combined
  amount. Children flip to `transferred` alongside the parent and their
  `transferred_to_id` points at the same target. The new row's `credit_note` spells out
  e.g. `"$75.00 parent + $8.37 +PAY"`.

## Payout Credit (WD-credit + standalone credited refunds)

`payout_credit(conn, item_id, method, date, note)` records a real-world refund against a
WD-credit balance or a standalone `credited` row:
- For `transaction_status='credited'`: amount = `item_price`, row flips to `refunded`.
- For `transaction_status='wd'`: amount = `credit_amount`, the field is cleared, status
  stays `wd`.
- Writes an `acct_transactions` expense entry (`category='refund'`, `source=method`,
  `account=Venmo|PayPal|TGF Checking`).
- `credit_note` stamped `Refunded $X.XX via <method> on YYYY-MM-DD`.
- `payout_wd_credit` retained as a Python alias for back-compat.

API: `POST /api/items/<id>/payout-credit` (canonical) and
`/api/items/<id>/payout-wd-credit` (legacy alias). Both admin-only.

## Course fee rounding fix
- **Per-player allocations** store individual post-tax amounts (individually correct)
- **Aggregate calculations** (Financial tab) use corrected formula:
  `base_rate × player_count × (1 + tax_rate)` — totals first, tax second
- Example: $54 × 32 × 1.0825 = $1,870.56 (correct) vs $58.46 × 32 = $1,870.72 (old drift)

## Course fee — 9/18 split rendering

`_calc_aggregate_course_cost` returns `{total, by_holes[]}` where each `by_holes` entry has
`holes`, player count, per-player cost, and bucket total. The fallback path (no event
config, summing from `acct_allocations`) also buckets by hole. The API exposes this as
`expenses.course_fees_by_holes`, and the Financial panel renders indented sub-rows under
Course Fees whenever more than one bucket exists — same pattern as Prize Fund's HIO /
Net / Gross sub-rows.

Two combo bugs the rendering depended on:
1. `is_combo` detection. The actual format string is `"9/18 Combo"` — the equality
   check `format.lower() == "combo"` never matched, so combo events read from the
   single-format columns (`course_cost`, `course_cost_breakdown`) instead of the
   per-hole columns (`_9` / `_18`) and yielded $0. Fixed in both `_calc_event_allocation`
   and `_calc_aggregate_course_cost`.
2. Empty-event fallback. When an event has neither `course_cost` nor
   `course_cost_breakdown` set, `_calc_aggregate_course_cost` used to return `0` even
   when each player's `acct_allocations` row already had a `course_payable` (and
   `course_surcharge`) value budgeted at registration time. Now falls back to summing
   those per-allocation values so projected expenses match what was allocated.

## Books-posted vs Bank-reconciled (Financial tab)

The Financial tab's verification panel shows two independent checks with explicit
prefixes so they don't read as contradictions:

- **Books:** entries posted to ledger (i.e. `acct_transactions` rows exist for the
  event — what `data.accounting_verified` actually measures). Previously rendered as
  the green "Accounting (verified)" badge, which sounded like a bank confirmation.
- **Bank:** `0 of 53 matched to deposits ($0.00 confirmed, 0%)` — the actual
  bank-deposit match status. Red at 0%, amber at partial, green at 100%, with the
  no-entries-yet case handled explicitly.

## Venmo "received" rows — income, not expense

`expense_transactions` is the staging table for every CC/bank/Venmo email alert
regardless of direction. Inbound Venmo balance-due payments are tagged
`transaction_type='received'` to mark them as income. Two consequences:

1. **Ledger sync.** `_sync_expense_ledger_entry` now sets `entry_type='income'` for
   `received` rows (was hardcoded `'expense'`). A one-time idempotent backfill in
   `init_db` flips already-promoted Venmo received rows. The pre-fix bug didn't
   visibly inflate event expense totals because the event financial summary only sums
   `entry_type='expense'` rows whose category is `'refund'` or `'processing_fee'` —
   and these promoted Venmo rows have NULL category — so they were neutral phantoms.
   But other consumers (e.g. `get_event_reconciliation_status`, which counts
   `entry_type='income'` rows for an event) were missing them.
2. **Actual Expenses panel filter.** The Financial tab Actual Expenses panel filters
   `received` rows out before rendering so only true outflows
   (`transaction_type` = expense / payout / transfer) appear in the table. Before,
   inbound balance-due Venmo payments showed up as outflows.

## Venmo balance-due dedup

Each Venmo IN balance-due payment used to produce TWO `acct_transactions` rows: one
from `_sync_expense_ledger_entry` (`source_ref=exp-promoted-{id}`, raw merchant
description) and one from `auto_match_venmo_inbound_to_balance_due`
(`source_ref=venmo-bd-{id}`, category=`addon`, `item_id` linked). Both
`entry_type='income'` for the same payment, so income was double-counted.

Fix:
- `auto_match_venmo_inbound_to_balance_due` soft-deletes the `exp-promoted` row
  (looked up via `expense.acct_transaction_id`) before writing the `venmo-bd` row,
  then re-points `expense_transactions.acct_transaction_id` at the new row.
- `_backfill_approved_expenses_to_ledger` skips Venmo received rows that already have
  `matched_item_id` — `auto_match` owns the ledger entry for those.
- One-time idempotent backfill in `init_db` reverses every `exp-promoted` row whose
  expense has both `matched_item_id` AND a matching active `venmo-bd` row.

## `acct_allocations` table — per-player cost breakdown
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

## Accounting categories (TGF-scoped, seeded by `_seed_unified_financial_categories`)
- **Income:** "Credit Transfer In", "External Payment", "Event Revenue", "Membership Fees"
- **Expense:** "Credit Transfer Out", "Player Refunds", "Golf Course Fees / Green Fees"
