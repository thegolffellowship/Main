# June 2026 Sales-Tax Slice (READ-ONLY) — for the Mon Jul 20 webfile

**tracker-claude, 2026-07-16 evening. Scope: A4 (#207) + Kerry's session
directive. Source: live ledger, active rows (nothing after April can be
`reconciled` — bank imports stalled 04-28 — so active = complete for
June). Method: month slice of the ±1-day cross-writer twin scan + the
floating-income check. Nothing mutated.**

## Bottom line

**Yes, the June taxable-sales base moves — down — if it is derived from
the Tracker's income ledger:** June ledger income is **$33,845.15**, of
which **$549.00 is confirmed double-counted** (6 income twins) and a
further **$16.00 is a confirmed triple-book** (Lee Vasquez a9.13). A
corrected June ledger-income figure is **$33,280.15**, minus up to
**$182.32** more if the two same-day GoDaddy pairs below are confirmed
duplicates. Separately, **$2,141.00 of June income is floating**
(attributed to no customer/event/order) — whether any of it is taxable
needs Kerry's classification, and an event-derived base would MISS it
entirely.

If Kerry's webfile base is instead derived only from GoDaddy orders
($29,707.28 in June) or his own spreadsheet, the twins don't distort it —
but the floating Venmo income below is invisible to that base too.

## June income composition (live ledger)

| category / source | rows | total |
|---|---|---|
| godaddy_order / godaddy | 247 | $29,707.28 |
| (uncategorized) / venmo | 13 | $2,749.00 |
| addon / venmo | 13 | $822.37 |
| transfer_in / credit_transfer | 6 | $478.50 |
| transfer_in / godaddy | 1 | $88.00 |
| **total** | **280** | **$33,845.15** |

## Confirmed income double-counts touching June ($549.00)

Each pair = the app's own record (ext-pay/addon, customer-attributed)
PLUS the Venmo receipt email promoted separately (`exp-promoted`,
customer NULL). The exp-promoted leg is the duplicate:

| $ | in-app row | exp-promoted dup | person |
|---|---|---|---|
| 219.00 | ext-pay-2140 (06-24) | #4728 exp-promoted-1480 (06-24) | Julius Jenkins |
| 88.00 | ext-pay-1954 (06-07) | #4639 exp-promoted-1364 (06-07) | Sam McCormick |
| 88.00 | ext-pay-1953 (06-07) | #4638 exp-promoted-1363 (06-07) | Ryan Estes |
| 88.00 | ext-pay-2035 (06-15) | #4673 exp-promoted-1411 (06-14) | Daniel South |
| 50.00 | ext-pay-2195 (06-30) | #4839 exp-promoted-1540 (06-29) | Jeff Young |
| 16.00 | addon-1955/1956 (06-07) | #4637 exp-promoted-1361 (06-07) | Lee Vasquez |

Two pairs are date-off-by-one — the same-day scan alone would have
missed them (the ±1-day window is now standard).

**Lee Vasquez a9.13 is a TRIPLE-book:** `addon-1955` AND `addon-1956`
(both $16, both "GROSS Games — a9.13 Star Ranch", cid 99, same day) plus
the unattributed receipt #4637. Unless Lee genuinely paid twice, June
carries $48 booked against ≤$32 real — one addon row + the exp-promoted
row are dups (−$32), conservatively −$16 beyond the table above.

**Cross-month heads-up for JULY:** Lee's a9.12 $16 receipt
(#4613, exp-promoted-1330, 06-02 — the charter's "lost buy-in") was
finally recorded in-app on 07-16 (`addon-2328`). June correctly counts
it once; **July's books now carry the duplicate** and must drop one leg
in the cleanup.

## Floating June income — $2,141.00, needs Kerry's classification

| row | date | $ | payer | note |
|---|---|---|---|---|
| #4672 | 06-13 | 1,200.00 | Joe Warring | uncategorized Venmo — what is this? (sponsorship? private event?) |
| #4680 | 06-17 | 609.00 | Joe Warring | same question |
| #4634/35/36 | 06-06 | 100.00 ×3 | Marshall Meyer, Sentheran Naidoo, Richard Eisemann | pattern = contest entry (City Match Play $100?); if so → prize pool, likely NOT taxable — but currently invisible to any event/contest view |
| #4613 | 06-02 | 16.00 | Leonel (Lee) Vasquez | a9.12 buy-in — now known, see July note above |
| #4637 | 06-07 | 16.00 | Leonel (Lee) Vasquez | a9.13 — the triple-book above |

The Warring $1,809 is the swing item: if it's taxable June revenue, an
event-derived base misses it; if it's not (loan/reimbursement/pass-
through), a raw-ledger base overstates.

## For review (not confirmed duplicates)

Same customer, same day, same amount, DIFFERENT GoDaddy order ids —
either genuine double purchases or re-keyed orders:
- Hayden Doggett 06-29: R460335142 + R759039303, $75.08 each
- W Paul Reed 06-14: R362794343 + R420514347, $107.24 each

## venmo-bd regression (F12) — clear for June

The one active exp-promoted/venmo-bd twin found in the whole-DB scan is
NOT in the Apr–Jul window (one leg is likely an older reconciled row).
It cannot affect the June filing.

## Expense-side June twins (don't touch taxable sales; distort P&L)

6 pairs ≈ $790 where an in-app credit-payout/refund AND its Venmo
receipt both posted as expenses (Mary Wade $317.52 + $219.00, W Paul
Reed $107.00, Justin McCrary $93.15, Andy Sanford $39.67, Andy Donovan
$14.00). Queue for the Duplicate Detective pass — no filing impact.

## Caveats

- CONFIRMED by the deployed bridge (`scoring-fin-audit:taxslice=2026-06`,
  item_id-aware): identical floating list (7 rows, $2,141.00) and twin
  set (the bridge's $533 same-customer income pairs + the cid-NULL Lee
  pair = the $549 above). The June income composition table matches
  row-for-row.
- The app's own `tax_reserve` MTD reads from `acct_allocations` (21 rows
  total, effectively dead — K4). Do not use it for the filing.
- Nothing in this report was changed in the DB; every duplicate above
  awaits the ratified Duplicate Detective pass (rule 3b).
