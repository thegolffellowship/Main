# Expense Transaction Workflow

## Tables
- `expense_transactions` — staging table for CC/bank alert emails parsed by the AI bookkeeper.
  Fields include: `merchant`, `amount`, `txn_date`, `category`, `review_status`,
  `account_name`, `account_last4`, `account_id` (FK → `bank_accounts`), `customer_id`,
  `acct_transaction_id` (FK → `acct_transactions`; set when promoted to ledger).
- `acct_keyword_rules` — auto-learned categorization rules. When an expense is approved with
  a category, a `match_type='contains'` rule is created so future alerts from the same
  merchant get auto-categorized (`COLLATE NOCASE` — case-insensitive).
- `expense_seen_emails` — dedup memory for the classifier (`email_uid` PK,
  `classified_as`, `seen_at`). Records **every** email the classifier has looked
  at, regardless of outcome. See **Dedup & Cost Control** below.

## Dedup & Cost Control (IMPORTANT — read before touching `check_expense_inbox`)

The classifier makes a paid Claude call per email. The cost rule is: **an
email is classified at most once, ever.** Polling frequency is therefore
decoupled from cost — running every 5 minutes costs the same as once a day.

- **Gate:** `check_expense_inbox` skips any uid in
  `get_known_email_uids() | expense_uids | action_uids | get_expense_seen_uids()`.
  `expense_seen_emails` is the comprehensive one; the others are
  defense-in-depth for pre-table rows.
- **Marking:** `mark_expense_email_seen(uid, type)` is called the moment an
  email is classified — **before** the per-type branches (several `continue`).
  This is the fix for the original leak: `unknown` / `godaddy_order` /
  `golf_genius_rsvp` emails used to be skipped without being recorded, so they
  were re-classified (and re-billed) on every scheduler cycle. A `classify_email()`
  exception leaves the uid unmarked so it retries next cycle (matches the
  GoDaddy parser).
- **Never** write the expense classifier's "seen" marker into
  `processed_emails` — that table gates the GoDaddy order parser, and a
  not-yet-parsed order seen by the expense classifier would be lost.
- **Lookback window** (Graph fetch bound only — does not affect Anthropic
  spend once dedup is correct):
  - Scheduled call (`days_back=None`): `EXPENSE_LOOKBACK_HOURS` (default 48h).
  - Cold start (empty `expense_seen_emails` → fresh DB or wiped volume):
    one-time `EXPENSE_BACKFILL_DAYS` (default 14) days, logged as a WARNING.
  - Admin/manual (`/api/accounting/check-expense-inbox`) may pass explicit
    `days_back`.
- **Re-key protection:** `save_expense_transaction()` adopts an existing row
  with the same `(source_type, merchant, amount, transaction_date)` under a
  different `email_uid` instead of double-inserting when Graph re-keys an
  already-seen email. NULL amount/date falls through to the normal insert.
  **Twin-payment veto (v2.140.3):** before adopting (both the re-key path and
  the no-uid content match), the platform `transaction_id` from each row's
  `raw_extract` is compared — different ids mean two REAL payments that
  coincide on payee/amount/date, and the new receipt inserts as its own row.
  Discovered via Bob Atkinson 7/21: two $58 credit refunds + two $25 referral
  fees each folded into one row, dropping $83 from the ledger (healed by boot
  repair `_repair_atkinson_folded_receipts`; the recreated rows deliberately
  carry no transaction_id so a late re-delivery of the original emails adopts
  them instead of duplicating).
- **Persistence:** the dedup table lives in SQLite. Without a Railway
  persistent volume + `DATABASE_PATH`, every redeploy wipes it and re-bills
  the full backfill window. `start_scheduler()` logs a loud WARNING if
  `DATABASE_PATH` is unset. A console.anthropic.com spend cap is the backstop.

## Statement-feed reconciliation (v2.147.0 — Kerry 2026-07-28)

"Feed things to you and you reconcile … create ledger entries where we
don't have something." `reconcile_statement_lines(account_last4,
statement, lines, create_missing)` + bridge cmd
`scoring-statement-reconcile` (JSON: account / statement / lines of
{date, desc, amount, kind: purchase|payment|credit}). Per line: match an
expense_transactions row (±$0.01, ±7 days), else an acct_transactions
row; unmatched lines become expense rows with source_type='statement',
synthetic uid `stmt-<last4>-<date>-<cents>` (idempotent re-feed),
statement label + raw line in raw_extract, review 'approved', promoted
to the ledger immediately. `kind: payment` books transaction_type
'transfer' (card payments are checking→card moves, not P&L expense).
Chase alert emails are threshold-y and miss small recurring
subscriptions — statements are ground truth; this is the fill.

**Match guards (v2.149.5 — both the expense-match and ledger-fallback
paths):** (1) P2P payout rows (`transaction_type='payout'` with
source venmo/paypal/cashapp/zelle; the ledger path joins
`exp-promoted-N` rows back to their expense row for this check) are
NEVER candidates — a member payout can't be the books entry for a
card/bank purchase; (2) `source_type='statement'` candidates must
match on the EXACT date (statement dates are authoritative, so twins
days apart can't cross-match); (3) candidates sharing no ≥3-char
name token with the statement line only match within ±2 days.
Candidates are scanned nearest-date-first (LIMIT 8). Same-run
created/matched rows stay excluded, and repeated (date, amount)
lines get ordinal-suffixed uids (v2.149.1–2). Statement saves bypass
the email re-key guard entirely (v2.149.4).

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

## Vendor Auto-Suggest (v2.18.0)

Opening the unified expense review modal (`openExpenseReview` in
`static/js/acct-transactions.js`) for a transaction with **no linked
customer_id** runs `_suggestExpenseVendor(exp)`:

1. `_matchProfileForMerchant(merchant)` scans `ACCT.customers` for a
   name hit (exact or substring, ≥4 chars, against company/display and
   "First Last" forms). Vendors win over customers; a customer hit still
   suggests (covers Venmo payouts to members). Match → one-click **Link**
   suggestion under the Vendor/Customer field (`#exp-vendor-suggest`).
2. No match and `transaction_type === 'expense'` → **＋ Create vendor &
   link** with a cleaned name from `_cleanVendorName()`: strips processor
   prefixes (`SQ *`, `TST*`, `PAYPAL *`…) and trailing store/reference
   numbers, title-cases bank ALL-CAPS, keeps mixed case as-is. The button
   POSTs `/api/accounting/vendors` (dedup-safe: reuses an existing
   company-name or first+last match instead of inserting) and selects the
   vendor via `setExpCustomer`.

Transfers never suggest (no counterparty); income only suggests links,
never vendor creation. Suggestion is confirm-only — nothing is created or
linked without a click. Dismiss hides it for that open of the modal.
