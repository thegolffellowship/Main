# Finance — Known Variance Register (filed periods)

**Owner: tracker-claude (CFO lane). Rule: a variance found in a month that is
already FILED with the Texas Comptroller is recorded here, never restated in
place (Margin & Fee Calculation Standard v1.1 §2, "past periods are frozen";
Chief of Staff #1034 item 2).** Each row names the event, the amount, which
way it moves profit, and where it is settled. If a variance changes tax owed,
it is corrected on the next open month's return as a prior-period adjustment,
with the CPA's say-so.

| # | Period (filed) | Event | Variance | Effect on reported profit | Cause (standard §) | Found | Settlement |
|---|---|---|---|---|---|---|---|
| V-2026-07-1 | 2026-07 (paid per Kerry 9/30) | s9.20 Canyon Springs | $108.26 | Overstated (course cost was higher than estimated) | Course actual $1,244.88 against the $1,136.62 estimate: Arcis deposit $600.00 on Frost 0341, 4/20 (event #52926077218, ledger 3422), plus $644.88 on Chase 7680, 7/31. That is 2 × $54.13, most likely the two late withdrawals (South and Atkinson, each refunded $70) still charged by the course. | 10/4, CFO (Chase 7680 statement 26-08, Frost 0341 Apr) | Stays as filed. **No sales-tax effect:** course cost is pass-through, and the return is computed on the rate-card markup. Kerry to confirm the late-withdrawal reading. |
| V-2026-08-1 | 2026-08 (filed 9/20) | s18.10 FALL KICKOFF, Landa Park (8/29) | $21.28 | Overstated | The order-level 3.5% fee was counted once per item on multi-item orders (§8.1; CFO #1027 bug 3) | 9/30, Tracker Build #1032 | Stays as filed. The P&L headline keeps the pre-v1.1 figure ($492.78; Tracker Build #1040). |
| V-2026-08-2 | 2026-08 (filed 9/20) | s18.10 FALL KICKOFF, Landa Park (8/29) | $10.00 | Overstated | Jeff Young's Advisory Board coupon (`tgf-jeff`) was not netted against revenue (§8.6; CFO #1027 bug 2) | 9/30, Tracker Build #1032 | Same as V-2026-08-1 |

**Landa Park corrected profit, before pots: $492.78 − 21.28 − 10.00 = $461.50**
(Tracker Build #1032, "after" column). It is the figure the v1.1 method gives,
and it is recorded here only.

**Tax effect: none owed.** The sales-tax reserve comes from the allocations
layer (8.25% of positive TGF margin per row). The P&L revenue fixes don't move
it. Whether the $10 coupon should have cut August's taxable margin is part of
the September allocations-vs-P&L reconciliation (Chief of Staff #1034 item 2).
Any tax change found there goes on the next open return with the CPA's OK. It
does not reopen August.

## How to add a row

1. The period must already be filed. Find its `status: filed` in `scoring-liabilities` → `sales_tax_reserve.by_month`.
2. State the amount to the penny, the direction, and the standard section. Cite the mailbox post that found it.
3. Never edit the filed ledger rows to "fix" a variance. Corrections post in the open period.
