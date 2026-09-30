# TGF Texas Sales Tax — Filing & Payment Register

**Owner: tracker-claude (CFO lane).** Kerry, 2026-09-30: "create a monthly
routine to send me what my obligations for Texas Comptroller are … emailed to
me at the beginning of each month so I can quickly go and make payment … I
haven't paid August's yet, because I don't think we ever ran it and I forgot.
Can't happen obviously. Of course, you need to track Sales Tax payments
completely for the year."

- **Taxpayer:** THE GOLF FELLOWSHIP LLC. Texas taxpayer ID 32086231571. WebFile user `kerryniester`. Location 00001.
- **Filing frequency:** monthly, due on the 20th of the following month. Pay by electronic check from TGF Checking …0341.
- **Rates:** state 6.25% and local 2.0%, 8.25% total. A 0.5% timely-filing discount applies only if the return is filed on time.
- **Routine:** `trig_01FwwncqoaN72PVHcH58W7kx` runs at 7:52 AM Central on the 1st and the 15th, into the CFO session. The 1st sends the obligation email; the 15th sends a reminder only if a month is still unpaid.

## The rule: a month is PAID only with evidence

The evidence is the WebFile **"Confirmation: You Have Filed Successfully"** PDF,
saved to OneDrive. Save each new one to
`Seasons/<YYYY>/0 Financial/Sales Tax/<YY>-<MM> Payment Confirmation.pdf`.
Older confirmations live in `3_Events/2025/0 Financial/Sales Tax/` and
`TGF Financial/TGF Transaction Logs/Bookkeeping/Sales Tax/<YYYY>/`.

**Not evidence:** the Tracker's `scoring-liabilities`
`sales_tax_reserve.by_month.status: "filed"`. It is set by the calendar
(`"filed" if due < today`, margin_ledger.py), so August showed "filed" while
it was never filed. The Tracker's `tax_reserve` is also not a filing figure.
It has understated every return checked: July 2025 reserve $38.36 against
$280.50 filed, and February 2026 reserve $97.39 against $140.17 filed.

## Register (verified 2026-09-30 from the OneDrive confirmations)

| Period | Due | Status | Filed | Total TX sales | Taxable | Tax | Discount | Paid | Reference |
|---|---|---|---|---|---|---|---|---|---|
| 2025-01 | 2/20/25 | PAID | 2/20/25 | 2,433 | 1,250 | 103.13 | −0.52 | **102.61** | 5125311547 |
| 2025-02 | 3/20/25 | PAID | 3/20/25 | 2,675 | 1,343 | 110.80 | −0.55 | **110.25** | 7925264448 |
| 2025-03 | 4/21/25 (4/20 was a Sunday) | PAID | 4/21/25 | 6,271 | 1,752 | 144.54 | −0.73 | **143.81** | 11125470461 |
| 2025-04 | 5/20/25 | UNVERIFIED | | | | | | | |
| 2025-05 | 6/20/25 | UNVERIFIED | | | | | | | |
| 2025-06 | 7/20/25 | UNVERIFIED | | | | | | | |
| 2025-07 | 8/20/25 | PAID | 8/18/25 | 25,440 | 3,400 | 280.50 | −1.40 | **279.10** | 23025237478 |
| 2025-08 | 9/20/25 | UNVERIFIED | | | | | | | |
| 2025-09 | 10/20/25 | UNVERIFIED | | | | | | | |
| 2025-10 | 11/20/25 | UNVERIFIED | | | | | | | |
| 2025-11 | 12/20/25 | UNVERIFIED | | | | | | | |
| 2025-12 | 1/20/26 | UNVERIFIED | | | | | | | |
| 2026-01 | 2/20/26 | UNVERIFIED | | | | | | | |
| 2026-02 | 3/20/26 | PAID | 3/20/26 | 7,810 | 1,699 | 140.17 | −0.70 | **139.47** | 7926255547 |
| 2026-03 | 4/20/26 | PAID | 4/4/26 | 22,057 | 3,515 | 289.99 | −1.45 | **288.54** | 9426022559 |
| 2026-04 | 5/20/26 | UNVERIFIED | | | | | | | |
| 2026-05 | 6/20/26 | UNVERIFIED | | | | | | | |
| 2026-06 | 7/20/26 | UNVERIFIED | | | | | | | |
| 2026-07 | 8/20/26 | UNVERIFIED | | | | | | | |
| **2026-08** | **9/20/26** | **NOT FILED — LATE** (Kerry, 9/30) | | | | | | | |
| 2026-09 | 10/20/26 | OPEN | | | | | | | |

- **UNVERIFIED** means no confirmation PDF was found in OneDrive and there is no other record. The month may well have been filed. Kerry can confirm in one pass from WebFile → Sales Tax → "View/Print filed returns", and should save any missing confirmations to OneDrive.
- **Paid with evidence, 2025:** $635.77 across 4 months.
- **Paid with evidence, 2026 to date:** $428.01 across 2 months.

## Late-filing terms (Texas Comptroller)

- Late penalty: $50 per late report, plus 5% of the tax due if 1–30 days late, or 10% if more than 30 days late.
- Interest starts 61 days after the due date.
- The timely-filing discount is lost.
- WebFile works these out on the payment screen. Its figure is the one to pay.
- For August 2026 (due 9/20), filing and paying by **10/20/2026** keeps the penalty at 5% rather than 10%.

## Procedure (the routine follows this)

1. Check the Tracker mailbox, then `get_current_time`.
2. Load `tgf-pricing`, then `tgf-sales-tax`.
   - The latest Pricing & Services Master Document is required. Look in OneDrive `01_STANDARDS/`, then the mailbox (Chief of Staff), then this repo.
   - If it is missing, mark taxable sales NOT COMPUTED. Never compute from memory.
3. Re-verify every month in the table against OneDrive confirmations, and update this file.
4. For the month just ended, and for every UNVERIFIED or NOT FILED month past its due date, compute the WebFile inputs by the skill:
   - Total Texas Sales: gross per unique order, including Venmo and manual payments;
   - Taxable Sales, with its breakdown;
   - tax, discount and balance due.
   Apply Margin Standard v1.1 §8: coupons net once per order; credited items leave revenue; fees are never refunded. WebFile rounds sales to whole dollars.
5. Email `kerry@thegolffellowship.com` (Microsoft 365 `outlook_send_mail`, HTML, short enough for a phone). Include:
   - the amounts to pay now, past-due first;
   - the WebFile link;
   - the instruction to save the confirmation PDF;
   - the register.
6. Commit this file, then post a record to the mailbox (topic `sales-tax`).
7. Never file, never pay, and never email anyone but Kerry.

## Known data issues that affect the return (see also `finance-variance-register.md`)

- **The 2026 TGF Championship has 13 August allocation rows still `pending`,** all at $0 taxable, so the Tracker figure understates August. Compute the Championship from the Pricing Master; don't rely on the allocations.
- **The live `margin_model_cutover` setting is 8/27, but Standard v1.1 §2 says 9/5.** August orders dated 8/27–8/31 were therefore allocated on the residual model, which produces negative first-timer rows. The filing method (the rate card, per the skill) is not affected.
