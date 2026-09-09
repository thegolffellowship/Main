# Finance lane — session record, 2026-09-09 (evening): the financial audit

**Lane:** tracker-claude, Finance (new lane, spun off per `session-prompt-financial-audit.md`).
**Branch:** `claude/review-attached-prompt-2nhbqy` (docs only; nothing deployed, nothing written to production).
**Read-only session.** Every figure below came from the deployed bridges and MCP reads on 2026-09-09 between 6:15 and 7:30 PM CDT. No data, schema or dial was changed. Rule 3b applies to every proposal in §5–§7.

Kerry's charge, verbatim: *"Our bookkeeping needs to be above reproach and account for every penny and I need to know what needs to be in our liability buckets too."* And: *"We need to spin off a different chat session with a prompt to fully audit our FINANCIAL side of things and see how we can make it simpler and above reproach."*

Deliverable 1 (the money map) is published: https://claude.ai/code/artifact/878d544b-ceee-4b09-8cc6-085f998511ed. Deliverables 2 and 3 are designed here and wait on Kerry, one decision at a time (§8). Deliverable 4 is this file plus mailbox #444.

---

## 1. What this session read (so the next one does not)

`CLAUDE.md`; `docs/claude/unified-financial-model.md`, `sales-growth-2026-09-09.md`, `bank-reconciliation.md`, `expense-workflow.md`, `duplicate-detective.md`, `events.md` (refunds console, HIO pot, payout credit, referral fees); the July audit set that the Finance prompt did not mention but which is the same charter — `financial-audit-charter.md`, `financial-audit-gap-report.md` (Deliverable 1, 2026-07-16), `financial-audit-target-model.md` (Deliverable 2), `june-2026-tax-slice.md`, `k3-payout-variance-characterization.md`; mailbox #420–#443 in full; skills `tgf-pricing` and `tgf-sales-tax`; CA's `TGF_Margin_and_Fee_Calculation_Standard_v1_0.md` and `UF_2026-09-07`; the March 2026 filing workbook (`TGF Financial/Sales Tax/2026/TGF_SalesTax_2026_03.xlsx`) and the April detail workbook (`Seasons/2026/0 Financial/TGF_April2026_SalesTax_Detail.xlsx`).

Code: `email_parser/margin_ledger.py`, `fee_splits.py`, `fin_audit.py`, `database.py` (`calculate_order_allocation`, `_calc_membership_allocation`, `_calc_season_contest_allocation`, `get_accounting_liabilities`, `get_hio_pot`, `get_monthly_money_flow`, `close_period`, `remove_season_contest_enrollment`, the payout ledger writers), `templates/accounting.html` Liabilities tab, `static/js/acct-dashboard.js`.

Live reads: `scoring-liabilities`, `scoring-margin-gaps:80`, `scoring-fee-splits-check`, `scoring-hio-pot`, `scoring-payouts-coverage`, `scoring-money-flow:2026-08|debug`, `scoring-money-flow:2026-09|ytd`, `scoring-fin-audit:summary`, `get_reconciliation_dashboard`, `get_chart_of_accounts`, `get_app_settings`, `get_expense_transactions(pending)`, `get_acct_allocations`.

**The July audit is the same audit.** The charter of 2026-07-16 already found the structural problems (367 unattributed Venmo rows, four ledger designs, money as TEXT, no `event_id` on the ledger, 158 duplicate candidates, reconciliation stalled). Its Deliverable 3 (the ratified migration plan) never happened; the Sales & Growth lane then fixed the fee and margin model on top of the same foundation. This record inherits all of it rather than re-deriving it, and §4 says which July findings are still live.

---

## 2. The money map in one paragraph

Three doors in: a GoDaddy store order (parser → `items` → one `acct_transactions` row per order with `net_deposit` and `merchant_fee` → `godaddy_order_splits` per item), a P2P receipt (Venmo / Zelle / PayPal / Cash App → `expense_transactions` `received` → an `exp-promoted-N` income row, linked to an item when a matcher finds one, otherwise floating), and cash or a manual Add Payment (child item + `addon` row). One spine: `acct_transactions`. One splitter: `calculate_order_allocation` writes `acct_allocations` per item, lazily, into course / prize pool / shirt fund / spread / tax reserve / margin. Money out: prize payouts (`tgf_payouts`, keyed by event and category, settled on a `payout-N` ledger row), the ace payout (`category='hio'`), credit refunds (`payout_credit` → `expense/refund`), and everything else through `expense_transactions` with no reference to the bucket it draws from. Bank truth: `bank_deposits` + `reconciliation_matches`, last imported 2026-07-28 (checking), 2026-04-28 (Venmo), 2026-04-30 (Chase 7680).

Ten buckets, and whether each has an outflow side today:

| Bucket | In | Out recorded? | Balance exists? |
|---|---|---|---|
| Course fees | `course_payable` + `course_surcharge` | No (course bill untagged in the expense feed) | No |
| Event prize pools | `prize_pool` (event rows) | **Yes** — `tgf_payouts` | Both sides exist, nothing nets them |
| HIO pot | matrix per player, computed (`get_hio_pot`) | **Yes** — `tgf_payouts.category='hio'` | Yes, $3,350 |
| Monthly Points pool | $6 per membership | By NAME only (`tgf_events` "MARCH Points 2026") | Derivable |
| Season contest pools | contest + membership `prize_pool` | Payouts yes; **refunds no** (`season_contest_removals` + Venmo feed only) | Derivable, $120 high on Match Play |
| LSC shirt fund by Cup year | `lsc_shirt_fund` $10/membership | No | No |
| Sales-tax reserve by month | `tax_reserve` signed | No (webfile payment untagged) | Open months only |
| TGF margin | `tgf_operating` | n/a (P&L) | n/a |
| Credits held | `credit_amount` / credited rows | **Yes** — refund rows, transfer_in | Yes, $110.70 |
| LSC deposits | 22 × $150 income rows, no item, no event | No | No bucket exists |

---

## 3. Findings, ranked by what they do to "above reproach"

Sarah's framing first, marked as hers because it sets the order:

> **Sarah:** *"Above reproach means three things and only three. One, every dollar you hold for someone else has a balance you can produce on demand, today, from the books. Two, you never remit a tax from a spreadsheet that disagrees with your books; one source, and the books are it. Three, an expense queue five months deep means your P&L is a story, not a statement. Everything else is housekeeping."*

### F1 — Five liability buckets have inflows only (P0)
Course fees, shirt fund, tax reserve, contest refunds and LSC deposits leave the business through `expense_transactions` rows that carry no bucket key. No balance can be computed for them, which is why the Liabilities tab has Kerry typing `hio_pot`, `season_contests_total`, `lone_star_cup_shirts`, `member_credits_2025`, `grandparent_loan`, `irs_balance`, `chase_biz_7680`, `chase_sapphire_6159` by hand (`coo_manual_values`, eight keys). The two "calculated" rows on that tab are wrong by construction: "Prize Pools Owed" and "Course Fees Owed" sum allocations whose `allocation_date >= today`, which is *orders placed today or later*, not money unpaid. "Tax Reserve (YTD)" sums every month of the year including the seven already remitted. **The page that is supposed to answer "what do we owe" cannot.**

### F2 — The expense review queue is five months deep (P0)
170 rows pending, $84,101, oldest 2026-04-14, newest 2026-09-08: 105 receipts ($38,264), 35 Chase alerts ($34,470), 10 Venmo payouts ($5,848), 11 Venmo received ($2,735), 3 transfers ($1,975, incl. IRS), 2 Zelle payouts, 1 Zelle received, 3 with no type. It contains the duplicates CA identified in #428 §5 (Hyatt $9,534.95, TPC $3,876.43, Quarry $3,429.36, Silverhorn $476.30, Avery ×3) and two Delaware Springs rows of $9,204.80 each. Until this queue is worked, course-fee outflows, the Comptroller payment, LSC spend and shirts cannot be tagged even after F1 is built, because they have not been booked.

### F3 — Bank reconciliation is abandoned, and its numbers are noise (P1)
Checking last imported 2026-07-28, Venmo 2026-04-28, Chase 7680 2026-04-30; `period_closings` has 0 rows (no month has ever been closed). The dashboard's "book balance" for checking reads $155,147 against a bank balance of $55,486, variance −$99,661 — meaningless because the ledger's expense rows mix sign conventions (July audit A1: `expense` category NULL sums +$347,890, `prize_payout` sums −$23,318). YTD statements: $204,156 of deposits imported, $109,202 matched; books $272,933, matched $113,984. **Nothing since July is reconciled, and what was reconciled before July cannot be trusted as a balance.**

### F4 — Income with no home (P1)
Money Flow YTD: ledger gross $280,865 vs waterfall $166,332, delta $114,533. August alone: $23,374 vs $14,708. The August debug breaks it down: 29 income rows with no category and no allocation ($5,086 — the LSC deposits and other inbound P2P), 3 add-on rows ($1,067), 4 GoDaddy orders never allocated ($467). The YTD gap is dominated by the same classes over nine months plus the doubled exp-promoted/venmo twins the July audit counted (40 groups, 179 live duplicate candidates, 77 at ≥0.90 confidence, **0 ever merged**). Every dollar of that delta is a dollar the waterfall cannot place in a bucket.

### F5 — The tax reserve is right in the books and unverifiable against the returns (P1)
The Tracker's reserve is now sound (signed per row, month floors at zero, membership rebook applied, spread taxed). But the returns were filed from hand-built workbooks, and only March's is reachable from here. March: filed taxable $3,515 / paid $288.54; Tracker March margin $3,646 → reserve $301.30. **The Tracker reserves $12.76 MORE than March's return, so March did not overshoot.** April's workbook computed taxable $4,516.80 (tax $370.77 after discount) against the Tracker's $3,474 → $287.25. If April was filed at the workbook figure it over-remitted by roughly $85, and the workbook shows why: a "TXN Fee Taxable" column carrying the doubled per-item fees the one-order-one-fee repair since removed ($66.85, $102.42, $96.38, $60.46, $16.28 on single rows), plus side-game markups computed row by row. Jan, Feb, May, Jun, Jul: the confirmations are not in OneDrive's index (2025's are, as `YY-MM-SalesTax.pdf`) and not in Outlook under any search tried. **Need from Kerry: the seven Comptroller confirmations, or the figures from them, before "amend past reporting" can be sized.** Sarah's rule two follows: from the September return on, the return is generated from `acct_allocations` and the workbook is retired.

### F6 — Contest refunds are un-sales in the books (P2)
Campos $40, Cheshire $51.75, Lourigan $50 were refunded by Venmo and recorded in `season_contest_removals.refund_amount` and the expense feed. `acct_allocations` still books $50 of pool + $10 of markup each, so the 2026 Match Play pool reads $120 high and the tax base $30 high (#440). A refund is a contra against the bucket it came from; today it is an expense with no bucket.

### F7 — HIO pot pre-counts a future field, and only ever drains one way (P2)
`get_hio_pot` includes the next-in-line event's registrations by rule (a18.5 Forest Creek 9/12, $14 today). Fine for the Games tab; for a liability balance that is money not yet collected. The read should carry both numbers (played / with next event). Also: the pot is inside `prize_pool` on every event allocation, so any per-event pool balance must subtract it or it is counted twice.

### F8 — The July structural findings still live (P2)
Unattributed money: 907 of 1,808 `expense_transactions` rows have no `customer_id` ($459,525 gross); 961 of 8,888 ledger rows ($313,277). Dangling FKs: 217 `godaddy_order_splits.item_id`, 85 `acct_transactions.item_id`, 803 `bank_deposits.account_id` pointing at the vestigial `bank_accounts`. `acct_allocations` has no `customer_id` column (rule 6) and 1,381 of 1,404 rows have no ledger link. Money still TEXT in `items`. `chart_of_accounts` (19 rows) and `general_ledger` (0 rows) are decorative. 12 approved expenses never promoted ($125.80). One $30,000 transfer sits `ignored`. Payout variance: 25 lumps, $72.87 absolute, K3 codes still unratified.

### F9 — Three of the four "diverged" fee-split classes are cheap to close (P3)
28 orders (`scoring-fee-splits-check`): six multi-item orders where items add to exactly 2× the order row (quantity-2 expansion doubling registrations — overstates collected and margin for those players), ten single-item orders with no `transaction_fee` split (parser missed the fee line), two with an unrecorded −$25 coupon, ten single-item orders whose order row exceeds the item by a round amount (credit/transfer drift, expected). Kerry: "later look, not urgent". Recorded so it stays on the list.

### What is healthy, protect it
One order, one fee: 0 offenders across 1,375 orders. Every `tgf_payouts` row (1,087) has a customer, an event and a ledger link; 1,083 paid. Memberships decompose to the cent in all 16 price groups (Bartz 2025 excepted). Refund watches close credits paid by four P2P rails. The margin model (residual, spread inside, signed tax) is ratified and applied through 2026-08-27. Backups run and have been verified once (#443 era).

---

## 4. Inherited open items (do not re-derive)

- Four membership misfits → resolved (parser misses + refunds, v2.355–v2.356). Bartz 2025 $150 New + Fall is the one open price question.
- 28 diverged orders (F9). 73 pre-cutover event gaps (`scoring-margin-gaps`: 74 events, 1,268 rows, books $22,843 vs would-book $28,742 after the membership rebook; the membership group now reads $6,096 vs $6,103, closed). Kerry wants these one at a time; recommendation stands: the eight "no events row" names first (HILL COUNTRY MATCHES, both Kickoffs, s9.9, s9.16, s9.10, Northern Hills, a18.2), because they carry $5,500 of the $5,900 swing and each is one course cost + one prize structure.
- 2025 event orders (449) wait for the events phase.
- #428 asks 1–7: LSC as an event (blocked on entry price, course cost, prize structure), Luke Youngs → `lsc_accepted`, referral field, follow-up notifier, reply-rate denominator, four ad sets. Not this lane's, noted so they do not decay.
- CA's standard v1.1 amendments: #434 §3 (spread in the tax base), #435 §3 (shirt fund by Cup year, Aug–Jul), #436 §1 (signed tax, month floors), #440 (a refunded entry is a sale plus a refund).

---

## 5. Deliverable 2 — the liability ledger, design of record (pre-ratification)

> **LT:** *"The bottleneck is a person typing five numbers into a tab from memory. You do not fix that by asking the person to type more carefully. You fix it by making the buckets fill themselves and by giving the untagged dollar somewhere it cannot hide."*

> **Marcus:** *"One truth per fact. Inflows already live in `acct_allocations`; do not copy them into a second table that a rebook can forget. Outflows already live in `acct_transactions`; do not build a parallel ledger for them either. Put the bucket key on the row that moves the money, derive the balance in one function, and make the untagged class a number on a dashboard so it cannot be zero by accident."*

### 5.1 Shape

**A registry, as data.** `fund_buckets` — one row per bucket TGF holds money in for someone else or for a purpose it chose:

| column | meaning |
|---|---|
| `key` | e.g. `pool:event:3306`, `pool:hio`, `pool:monthly:2026`, `pool:contest:2026:city_match_play:SA`, `earmark:shirts:2026`, `reserve:tax:2026-08`, `held:credits`, `held:lsc_deposits:2026`, `owed:course:3306` |
| `kind` | `obligation` (owed to someone, must exist as cash) · `earmark` (TGF-owned, changeable) · `reserve` (owed to a government) · `held` (someone else's money until an event) · `payable` (a vendor bill) |
| `label`, `holding_account` (FK `acct_accounts`: checking 0341, the HYSA once it exists, money market 8045), `opened_on`, `closed_on`, `notes` |

Per-event and per-month keys are created by the code that first needs them (the allocator for events and months, the season-contest sync for contests, the membership allocator for Cup years), never by hand. The registry exists so a bucket's *kind* and *holding account* are facts a page can read and Kerry can edit, and so the HIO-to-HYSA move is one field, not a memory.

**Inflows are derived, never copied.** `fund_balances()` reads them straight from `acct_allocations`:
- `owed:course:<event>` ← `course_payable + course_surcharge` on that event's rows
- `pool:event:<event>` ← `prize_pool` on event rows **minus** the event's HIO share (matrix per player, the same function `get_hio_pot` uses) so the pot is not counted twice
- `pool:hio` ← carry-in + per-event HIO shares for **played** events (a second figure includes the next-in-line field, for the Games tab; the liability figure is the played one)
- `pool:monthly:<year>` ← $6 per membership row
- `pool:contest:<season>:<contest>:<chapter>` ← contest pool per membership flag and SEASON CONTESTS row (the decomposition already knows which contest each dollar belongs to; it needs to store that per row rather than as one `prize_pool` sum — see 5.3)
- `earmark:shirts:<cup year>` ← `lsc_shirt_fund` by `lsc_fund_year(order_date)`
- `reserve:tax:<month>` ← signed `tax_reserve` by month, floored at zero
- `held:credits` ← the refunds-console outstanding set (already one function)
- `held:lsc_deposits:<year>` ← income rows tagged to the bucket (these have no allocation; the tag IS the inflow record)

**Outflows are the ledger rows that already exist, with one new column.** `acct_transactions.fund_bucket TEXT` (FK-by-convention to `fund_buckets.key`). Stamped automatically wherever the writer knows the bucket:
- payout rows ← `pool:event:<event_id>` or `pool:hio` / `pool:monthly:<y>` / `pool:contest:…` from `tgf_payouts.event_id` + `category` (1,087 rows backfill mechanically)
- credit refund rows (`payout_credit`, partial refunds) ← `held:credits`
- contest removal refunds ← `pool:contest:…` (the removal routine writes the contra row it does not write today, F6)
- course bills matched to an event in expense review ← `owed:course:<event>`
- everything else ← a one-tap tag in the expense review modal (shirts, the Comptroller payment, LSC lodging and course), with a keyword rule so the second Comptroller payment tags itself (`acct_keyword_rules` already learns categories; it learns buckets the same way)

**Balance = derived in − Σ tagged out**, one function, one page, no manual keys. Three invariants surface as counts next to the balances, the way `pending review` does: *untagged outflows that look like bucket draws* (payee matches a course, a shirt vendor, the Comptroller, or a memo says "Lone Star"); *buckets with an outflow and no inflow*; *obligation buckets whose balance is negative*.

### 5.2 The page
A LIABILITIES tab on `/accounting` (replacing the current one, same tab slot): one row per bucket with kind, holding account, in, out, balance, last movement, and a drill-down to the rows. Grouped by kind, with obligation + reserve + held totals as "must exist as cash" and earmarks separate, per #422 §8 (never let the shirt fund read as owed). The eight manual keys retire; the three debt balances (IRS, two cards) move to a Debts card read from imported statements when those resume, and until then stay typed, labelled as typed.

### 5.3 Schema touches (Kerry ratifies; Marcus reviews)
1. `fund_buckets` (new table, seeded at boot with the non-per-event keys).
2. `acct_transactions.fund_bucket TEXT` (nullable; backfilled for payouts and refunds).
3. `acct_allocations.pool_detail TEXT` (JSON: `{"hio": 1.0, "team_net": 4.0, "ctp": 2.0, "net_side": 13.0, "monthly": 6.0, "contest:city_match_play:SA": 40.0}`) so a single `prize_pool` figure can be attributed to the pool it belongs to. The decomposers already compute these parts and throw the detail away.
4. `acct_allocations.customer_id` (rule 6, July audit P3) while the table is being touched.
No column is dropped; nothing existing is re-typed.

### 5.4 Order of build, once ratified
1. Registry + balance read (bridge `scoring-fund-balances`, measure-only) — proves the arithmetic on live data before any page.
2. Payout / refund backfill of `fund_bucket` (mechanical, audited, backup first).
3. Contest-refund contra rows (F6) — the first liability-ledger case Kerry named.
4. LSC deposit tagging (22 rows) so `held:lsc_deposits:2026` exists before the Cup on 10/10.
5. Expense-review tag control + keyword rules.
6. The page; retire the manual keys.
7. `pool_detail` on the allocator + rebook (the only step that rewrites money records).

---

## 6. Deliverable 3 — the simplification list

### 6.1 Surfaces today, and what each is for
| Surface | What it does | Overlaps with |
|---|---|---|
| `/accounting` → Dashboard, Accounts, Categories, Reports, Liabilities, Contractors, Rules, Ledger | multi-entity ledger, inline match queue, month-close checklist, manual liabilities | everything below |
| `/accounting/reconcile` (Account Dashboard, Match Queue, Monthly Summary) | the original match queue and CSV export | the inline queue on the Ledger tab |
| `/accounting/cashflow` | 13-week projection | nothing usable — no opening balance, actuals discarded (#428 §5) |
| `/accounting/money-flow` | pass-through vs keep waterfall over allocations | the Reports tab |
| `/tgf` → Payouts, Unpaid, Refunds | prize money out, credits out | the ledger's payout and refund rows |
| `/transactions` | items and orders | the ledger's income rows |
| Duplicate Detective | ledger de-duplication | never run in anger (0 merges) |
| COO financial snapshot | manual cash + liabilities | the Liabilities tab |
| `chart_of_accounts` + `general_ledger` | Schedule C mapping | empty; nothing posts to it |

### 6.2 Collapse to one monthly close, in this order
The close is a checklist the Tracker fills in itself, on the Accounting page, and it is the only finance routine Kerry runs. Each step is a count that must reach zero or a figure that must be signed off:
1. **Inbox zero.** `expense_transactions` pending for the month = 0. Duplicate Detective runs as part of this step (it is a review, not a tool), so twins are settled while the receipt is in front of someone.
2. **Bank matched.** Statement feed for checking, Venmo and Chase 7680 fed; unmatched lines = 0 or explained.
3. **Payouts and refunds settled.** `tgf_payouts.paid_at` null = 0 for played events; Refunds console OUTSTANDING reviewed.
4. **Buckets snapshotted.** `fund_balances()` written to `period_closings` for the month (the table exists and has never been used).
5. **Sales tax from the books.** The month's return figures (Total Sales = collected per unique order + non-GoDaddy income; Taxable = Σ `tgf_operating`, signed, floored at zero) rendered by the Tracker; the workbook retires; the Comptroller payment is tagged to `reserve:tax:<month>` when it posts.

### 6.3 Retire, in order of least risk
1. `/accounting/cashflow` (unusable; nothing reads it).
2. The eight manual liability keys (replaced by §5).
3. The standalone `/accounting/reconcile` Match Queue tab (the inline queue is the same thing); keep the Monthly Summary export until step 5 above exists.
4. `general_ledger`, `bank_statement_rows`, `bank_accounts` (vestigial; 803 deposits still point at `bank_accounts` ids that are really `acct_accounts` ids — fix the pointer when dropping).
5. `chart_of_accounts` unless the CPA wants Schedule C lines; if kept, map `fund_buckets.kind` to it rather than posting to it.

Not on the list: `/tgf` Payouts and Refunds (they are the outflow writers the ledger depends on) and Money Flow (it becomes the Reports tab's waterfall, not a separate page).

---

## 7. Sales tax, filed vs Tracker

| Month | Tracker margin | Tracker reserve | Filed taxable | Filed tax | Note |
|---|---:|---:|---:|---:|---|
| 2026-01 | $442.00 | $36.51 | ? | ? | confirmation not found |
| 2026-02 | $1,179.00 | $97.39 | ? | ? | confirmation not found |
| 2026-03 | $3,646.00 | $301.30 | $3,515.00 | $288.54 | Tracker reserves $12.76 more than filed |
| 2026-04 | $3,474.00 | $287.25 | ? ($4,516.80 in the workbook) | ? ($370.77 in the workbook) | if filed as computed, ~$85 over |
| 2026-05 | $4,732.00 | $391.01 | ? | ? | |
| 2026-06 | $4,538.00 | $375.17 | ? | ? | June ledger twins ($549) per `june-2026-tax-slice.md` |
| 2026-07 | $3,674.00 | $301.31 | ? | ? | |
| 2026-08 | $1,704.70 | $140.20 | open, due 9/20 | | first month the Tracker can file from |
| 2026-09 | $745.95 | $61.56 | open | | |

Tracker reserve, 2026 filed months: $1,789.94. The 2025 months carry $33.45 of retroactive reserve from the imported memberships; those returns were filed in 2025 and are outside this table.

---

## 8. Decision register — one at a time, in this order

| # | Decision | Recommendation | Why first |
|---|---|---|---|
| **D1** | **The bucket registry: which buckets exist, what kind each is, and which account holds it** (§5.1 list; HIO + 2027 shirts → HYSA, 2026 shirts + everything else → checking; LSC deposits as `held`, not revenue) | Ratify the ten as listed | It is Kerry's own question ("what needs to be in our liability buckets") and every build step needs the list |
| D2 | Schema: `fund_buckets`, `acct_transactions.fund_bucket`, `acct_allocations.pool_detail` + `customer_id` (§5.3) | Ratify; Marcus reviews the migration | Unlocks the balance read |
| D3 | Contest refunds post as contra rows against the contest pool (F6), backfilled for the three 2026 Match Play refunds | Ratify | Kerry named it; smallest money migration |
| D4 | The Comptroller confirmations for Jan–Jul 2026 (or their figures) so §7 can be completed, and whether to amend | Kerry supplies | Sizes "amend past reporting" |
| D5 | The September return is produced by the Tracker from allocations; the workbook retires | Ratify | Sarah's rule two |
| D6 | Work the 170-row expense queue as the first close step, with the #428 duplicates rejected | Kerry does, with a one-tap bucket tag once D2 lands | Nothing can be tagged until it is booked |
| D7 | Retire `/accounting/cashflow` and the manual keys | Ratify after the page exists | Simplification, zero risk |
| D8 | The eight "no events row" gaps, one event at a time (course cost + prize structure) | Kerry supplies | Closes $5,500 of the $5,900 pre-cutover swing |
| D9 | The 28 diverged orders, class (a) first (six quantity-2 orders doubling registrations) | Later, Kerry's word | "later look" |

D1 is the only question this session puts to Kerry.

---

## 9. What this session did not do, on purpose
- No code, no schema, no dial, no data write. Rule 3b covers every item in §5–§6.
- No push to `main`; the record lives on the lane branch until Kerry's D1 so the deploy that follows carries the ratified shape.
- Did not read the 2025 Comptroller PDFs or the earlier years (they exist in OneDrive; not this lane's period).
- Did not run Duplicate Detective, even dry-run (its report is the July gap report's F10 and is unchanged: 179 candidates).
- Did not mirror this record to OneDrive (`scoring-docs-mirror` mirrors the deployed `main`, which does not carry this file yet).

## 10. Next session, start here
Read this file, then `scoring-liabilities` and `scoring-fee-splits-check` for drift since 2026-09-09. If Kerry has ratified D1, build §5.4 step 1 (the measure-only balance read) before anything else and bring D2 with its numbers. If he has not, ask D1 again in one sentence and wait.
