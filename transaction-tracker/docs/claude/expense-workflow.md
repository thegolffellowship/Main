# Expense Transaction Workflow

## Tables
- `expense_transactions` — staging table for CC/bank alert emails parsed by the AI bookkeeper.
  Fields include: `merchant`, `amount`, `txn_date`, `category`, `review_status`,
  `account_name`, `account_last4`, `account_id` (FK → `bank_accounts`), `customer_id`,
  `acct_transaction_id` (FK → `acct_transactions`; set when promoted to ledger).
- `acct_keyword_rules` — auto-learned categorization rules. When an expense is approved with
  a category, a `match_type='contains'` rule is created so future alerts from the same
  merchant get auto-categorized (`COLLATE NOCASE` — case-insensitive).

## Approval → Ledger Promotion
`_sync_expense_ledger_entry(conn, exp)` — called by `update_expense_transaction()` whenever
an expense is set to `review_status IN ('approved', 'corrected')`.

- Creates (or updates) a row in `acct_transactions` with:
  - `entry_type = 'expense'`
  - `amount = COALESCE(amount, total_amount)` — must be set so reconciliation can compare
  - `description = merchant`, `date = txn_date`, `type = 'expense'`
  - `source_ref = 'expense-{id}'` for idempotency
- Sets `expense_transactions.acct_transaction_id` back to the new/existing ledger row ID.
- `_backfill_approved_expenses_to_ledger(conn)` runs at startup in `init_db()` to promote
  any already-approved expenses that were missing a ledger row (one-time catch-up).

## Vendor / Customer Typeahead on Expense Modal
The expense review modal has the same Vendor/Customer typeahead as the income/ledger modal.
IDs use `exp-*` prefix (`#exp-customer-id`, `#exp-customer-search`, `#exp-customer-dropdown`).

Key JS functions in `acct-transactions.js`:
- `setExpCustomer(id, name, isVendor)` — populates the selected-chip display
- `clearExpCustomer()` — resets the field
- `initExpCustomerTypeahead()` — wires the search-input debounce/dropdown
- `saveNewVendor()` — routes to `setExpCustomer` vs `setTxnCustomer` based on which modal
  is open (`$('#expense-review-modal').style.display !== 'none'`)

## Category Learning
When an expense is approved with a category, `acct_keyword_rules` auto-gets a new row:
`match_type='contains'`, `keyword=merchant`, `category=category`, `COLLATE NOCASE`.
Future alerts from the same merchant (or containing that merchant name) are pre-categorized.
Vendor (`customer_id`) auto-suggestion is NOT yet implemented — that requires a separate
lookup of which `customer_id` most frequently maps to a given keyword rule.

## Expense Parser — Email Classification and Null Safety

`email_parser/expense_parser.py` uses Claude Haiku to classify and extract financial
emails. Classification types: `godaddy_order`, `golf_genius_rsvp`, `chase_transaction_alert`,
`venmo_payment`, `expense_receipt`, `action_required`, `unknown`.

Each extraction function (`parse_chase_alert`, `parse_expense_receipt`) returns a dict.
**Null field safety:** both functions guard against the LLM returning `null` for
numeric fields before type conversion:

```python
if result.get("amount") is not None:
    result["amount"] = abs(float(result["amount"]))
```

Without this guard, `abs(float(None))` raises `TypeError` and the email is silently
skipped for that scheduler run (logged as ERROR but not retried). Missing amounts should
be filled in manually during the review/approval step. The same pattern should be used
for any new numeric fields added to extraction prompts.

## GoDaddy Merchant Fee Split
GoDaddy transactions store up to 3 splits in `acct_splits`: registration, tx_fee, and
negative merchant_fee. When the edit modal opens for a GoDaddy transaction:
- If existing splits in DB already include a negative split (`amount < 0`), use DB splits.
- If existing splits lack the negative merchant_fee (pre-fix data), call `_buildSmartSplit(txn)`
  which generates all 3 splits from `txn.merchant_fee` or `txn.order_splits.merchant_fee`.

```javascript
const isGoDaddy = txn.category === 'godaddy_order' || txn.order_splits?.registration != null;
const hasMerchantFeeSplit = txn.splits.some(s => (s.amount || 0) < 0);
const useDbSplits = txn.splits.length > 0 && (!isGoDaddy || hasMerchantFeeSplit);
const splitsData = useDbSplits ? txn.splits.map(...) : _buildSmartSplit(txn);
```
