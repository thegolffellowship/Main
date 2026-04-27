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
- Refund methods: GoDaddy, Venmo, Zelle
- Transfer items carry the original price (e.g., "$102.00 (credit)") not "$0.00 (credit)"

## Course fee rounding fix
- **Per-player allocations** store individual post-tax amounts (individually correct)
- **Aggregate calculations** (Financial tab) use corrected formula:
  `base_rate × player_count × (1 + tax_rate)` — totals first, tax second
- Example: $54 × 32 × 1.0825 = $1,870.56 (correct) vs $58.46 × 32 = $1,870.72 (old drift)

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
