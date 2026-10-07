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

## Delivery rule (Kerry, 9/30)

"Go with the Tracker mailer. I believe that's standard now for our other emails, and should be standard when I request that moving forward."

- Every email to Kerry goes through the Tracker's own mail path (bridge `scoring-mail-kerry`, requested in mailbox #1049/#1050). No Claude connector sends it; Microsoft 365 is read-only.
- Until that bridge ships, the fallback is the mailbox plus the session notification.

## System of record (from 9/30, v2.522.44)

The Tracker's `sales_tax_filings` table is authoritative for filing status (bridges `scoring-sales-tax-filings` and `scoring-sales-tax-filing:<json>[|apply]`).

- The six confirmed months are recorded with evidence `confirmation`. The 13 months Kerry says are paid are recorded as `kerry_word` (#1058, #1060).
- August 2026 has no row, so it reads LATE.
- This file keeps the working and the August return.
- Delivery is `scoring-mail-kerry-send`: Kerry-only and live, with a dry run first through `scoring-mail-kerry`.

## The rule: a month is PAID only with evidence or Kerry's word

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
| 2025-04 | 5/20/25 | PAID (Kerry, 9/30; confirmation in iCloud, not yet in OneDrive) | | | | | | | |
| 2025-05 | 6/20/25 | PAID (Kerry, 9/30; confirmation in iCloud, not yet in OneDrive) | | | | | | | |
| 2025-06 | 7/20/25 | PAID (Kerry, 9/30; confirmation in iCloud, not yet in OneDrive) | | | | | | | |
| 2025-07 | 8/20/25 | PAID | 8/18/25 | 25,440 | 3,400 | 280.50 | −1.40 | **279.10** | 23025237478 |
| 2025-08 | 9/20/25 | PAID (Kerry, 9/30; confirmation in iCloud, not yet in OneDrive) | | | | | | | |
| 2025-09 | 10/20/25 | PAID (Kerry, 9/30; confirmation in iCloud, not yet in OneDrive) | | | | | | | |
| 2025-10 | 11/20/25 | PAID (Kerry, 9/30; confirmation in iCloud, not yet in OneDrive) | | | | | | | |
| 2025-11 | 12/20/25 | PAID (Kerry, 9/30; confirmation in iCloud, not yet in OneDrive) | | | | | | | |
| 2025-12 | 1/20/26 | PAID (Kerry, 9/30; confirmation in iCloud, not yet in OneDrive) | | | | | | | |
| 2026-01 | 2/20/26 | **UNVERIFIED** (Kerry's word 9/30; no confirmation on file anywhere, CoS #1302) | | | | | | | |
| 2026-02 | 3/20/26 | PAID | 3/20/26 | 7,810 | 1,699 | 140.17 | −0.70 | **139.47** | 7926255547 |
| 2026-03 | 4/20/26 | PAID | 4/4/26 | 22,057 | 3,515 | 289.99 | −1.45 | **288.54** | 9426022559 |
| 2026-04 | 5/20/26 | PAID **LATE**; penalty $65.75 ($50 + $15.75) | 6/15/26 | 21,850 | 3,816 | 314.82 | none | **380.57** | 16626146585 (pmt 16626147038) |
| 2026-05 | 6/20/26 | PAID | 6/15/26 | 32,683 | 5,047 | 416.38 | −2.08 | **414.30** | 16626147465 (pmt 16626147643) |
| 2026-06 | 7/20/26 | PAID **LATE**; penalty $70.54 ($50 + $20.54) | 8/19/26 | 31,466 | 4,979 | 410.77 | none | **481.31** | 23126134775 (pmt 23126135233) |
| 2026-07 | 8/20/26 | PAID | 8/19/26 | ?1,262 (see note) | 4,099 | 338.17 | −1.69 | **336.48** | 23126135678 (pmt 23126135880) |
| 2026-08 | 9/20/26 | PAID **LATE**; penalty $58.56 ($50 + $8.56) | 10/6/26 | 19,152 | 2,075 | 171.19 | none | **229.75** | 27926104778 (pmt 27926105381) |
| 2026-09 | 10/20/26 | PAID | 10/6/26 | 18,577 | 2,964 | 244.53 | −1.23 | **243.30** | 27926105769 (pmt 27926105881) |

- **Kerry, 9/30:** "We have record of all of those, but some are in another part of iCloud. I've made payment on all but August." So every month except 2026-08 is PAID. Where the confirmation is in iCloud, the amounts are left blank until a copy is saved to OneDrive. Copying them over is housekeeping and does not block anything.
- **Paid with evidence, 2025:** $635.77 across 4 months.
- **Paid with evidence, 2026 to date:** $428.01 across 2 months.
- **Update 10/7 (CFO, from the WebFile PDFs; CoS #1301/#1302):** 2026-02 through 2026-09 are all filed and paid, with the confirmations in `OneDrive: TGF_iCloud_Files_2026-10-01/00 Seasons/2026/0 Financial/Sales Tax/`. Every row is also in `sales_tax_filings` (evidence `confirmation`). 2026-01 stays **UNVERIFIED**.
  - **Paid with evidence, 2026: $2,513.72 across 8 months.** Of that, **$194.85 is late-filing penalties** (April $65.75, June $70.54, August $58.56). Book penalties as an expense, never as tax, and not deductible.
  - The 10/4 bank-evidence inference below is **confirmed**: April and June were each paid late, together with the next month.
  - **How the figures were read:** April and May are plain text. June–September are glyph-encoded; the figures were decoded and each one ties (state + local = total tax; tax + penalty + discount = paid).
  - **July's Total Texas Sales** decodes as ?1,262: the first digit's glyph appears nowhere else in that PDF, so it is 3 or 7. The field is left blank in the database. Read it by eye.
  - **September's discount was $1.23,** not the $1.22 estimated on 10/1. WebFile is the record.
- **The iCloud copy (CoS #1181, 10/3) adds no confirmations.** `TGF_iCloud_Files_2026-10-01/00 Seasons/2026/0 Financial/Sales Tax/` holds only 26-02 and 26-03, the same two already above (CFO read, 10/4). The 2025 and Jan/Apr–Jul 2026 confirmations are still not in OneDrive.

### Bank evidence: Comptroller debits on Frost 0341 (CFO, 10/4)

Read from the Frost 0341 statements in `TGF Financial/.../Statements/TGF LLC Checking-0341/`. It is evidence that money left. It is not a confirmation, and it names no period.

| Debit date | Amount | Most likely period | Basis |
|---|---|---|---|
| 04/07/26 | 288.54 | 2026-03 | Ties to the penny to the 2026-03 confirmation (filed 4/4) |
| 06/16/26 | 380.57 | 2026-04 or 2026-05 | Two debits the same day. No Comptroller debit on the May statement. |
| 06/16/26 | 414.30 | 2026-04 or 2026-05 | (same) |
| 08/20/26 | 336.48 | 2026-06 or 2026-07 | Two debits the same day |
| 08/20/26 | 481.31 | 2026-06 or 2026-07 | (same) |

- **Read:** if each pair is two returns paid together, then April (due 5/20) and June (due 7/20) were each paid about a month late. A late payment carries the $50 late-filing penalty plus 5% (see Late-filing terms), and that would be inside these amounts. **This is an inference.** It needs the confirmations, or Kerry's word, before any period is marked.
- **No debit for 2026-01 (paid 2/20 per Kerry) or 2026-02 ($139.47 on 3/20) was checked on Frost this pass.** Those may have been paid from another account.
- Frost September is not in OneDrive yet (Kerry to drop it). The August return (due 9/20, not filed) will show there when it is paid.

## August 2026 return: FINAL (Kerry 9/30: "Those markups are right (I believe), go ahead with August")

| Taxable component | Amount |
|---|---|
| Memberships (3 New at $44, including Kannon Brown's $100 = $50 membership plus the Fall NET markup; 2 Returning at $69) | 280.00 |
| Season contest markups at $10 each. Includes the Fall NET points bundled into the Burlingame, Vasquez and South event orders (not refunded), J. Wade's $150 (3 contests: Fellowship Cup, Players Cup, Austin Fall NET) and Marques's $100 (2 contests), both paid by Venmo | 160.00 |
| Regular-season event markups plus rounding surplus (s9.21, a9.21, a18.5, s18.10, SA Match Play Finals) | 887.92 |
| 2026 TGF Championship: markup backed out from the Lost Pines invoice. Includes Marroquin's $105 Friday practice round (Venmo 8/18) and Y. Williams's Sunday round ($170 Venmo 8/15, "TGF Sunday-Lost Pines") | 711.79 |
| Coupons (tgf-jeff ×2, Advisory Board) | −20.00 |
| TGF retained transaction fees (3.5% collected less GoDaddy 2.9% + $0.30, per order) | 55.29 |
| **Taxable sales** | **2,075.00** |

- **Total Texas Sales: $19,152.07 (WebFile 19,152).** That is:
  - 92 GoDaddy orders at $17,194.53;
  - Venmo and manual event and contest payments at $1,957.54: J. Jenkins, Callaway and Mazanec (Championship), three Match Play Finals, J. Wade $150, Marques $100, Marroquin $105 and Y. Williams $170.
- **Tax:** 2,075 × 6.25% = $129.69 state, plus 2,075 × 2% = $41.50 local, for **$171.19**.
  - The return is late, so there is no timely discount.
  - WebFile adds $50 plus 5% (if filed by 10/20), about $58.56, for an expected balance of about **$229.75**. Pay what WebFile shows.
- **Championship markups (Kerry-confirmed 9/30).** The Lost Pines invoice was $9,534.95: 62 rounds at $146.1375 ($135 + 8.25%) plus 5 practice rounds at $94.885.
  - Each package's base price = course + HIO $2 per day + markup. The NET/GROSS bundles carry no markup (Kerry).
  - Markups: Both Days $23.73; One Day $21.86; Practice Round $10.11; One Day guest $41.86. Full Weekend = $33.84.
- **Excluded:**
  - comps (Straiton ×2, Kerry);
  - fully refunded items (Sharitz contest, McDonnell guest practice);
  - the WD (Reed a9.21);
  - refunded Fall points portions (Mazanec, Vasquez s9.21, Sharitz, Baker, Rideout s18.10);
  - refunded practice rounds (Young, McDonnell);
  - Mazanec's $313, which completes a July credit-transfer order.
- **Not sales, so reclassify** (tracked, not changed; rule 3b):
  - Ann Jaber $100 on 8/25 (memo "Happy Birthday. I love you") is personal, not TGF revenue;
  - David Hooper $100 on 8/8 was sent from @tgf-payments itself, which looks like an internal move.
  - Both sit in the ledger as TGF income.
- **Lone Star Cup deposits:** $8,140 was received by Venmo/Zelle from August through September and recorded against the event, not against items. It is excluded from August and September. The LSC markup ($55 per entry, $12 per practice round, per event config) is reported on the **October** return, for the month the Cup is played. Deposits are customer money until then. **Kerry ruled 9/30: "Lone Star Cup is liabilities right now, for sure."** The deposits are customer deposits held until the Cup is played, and are not revenue before then.

## September 2026 return: computed 10/1 by the routine (rate card; Pricing Master v2.2, #1045)

| Taxable component | Amount |
|---|---|
| Event markups plus rounding surplus. Each item is backed out from its price: price less the bundle pools, less the exact course cost, less the included games ($7/$14). The base is floored at $0 for 1st Timers, then $3/$4 is added per bundle. Covers s9.21–s9.28, a9.22–a9.26, s18.11 and a18.5 | 2,177.14 |
| Memberships: 13 New at $44, Wade Lewis New $100 ($44 + the Fall NET $10), 2 Returning at $69 (Post, Mazanec) | 764.00 |
| Season contest markups: Fall NET at $10 each (L. Youngs, McCrary, M. Wade) | 30.00 |
| Coupons (tgf-jeff ×4, Advisory Board, once per order) | −40.00 |
| TGF retained transaction fees (3.5% collected less GoDaddy 2.9% + $0.30, per order; fees are never refunded) | 32.73 |
| **Taxable sales** | **2,963.87 → WebFile 2,964** |

- **Total Texas Sales: $18,577.46 (WebFile 18,577).** That is:
  - 189 GoDaddy orders at $18,436.46;
  - manual and Venmo event payments at $141: Cloer $99 (a18.5 balance), Compton $15 (a18.5 guest fee), M. Wade $16 (s9.21 NET), P. Youngs $11 (s9.25 balance).
- **Tax:** 2,964 × 6.25% = $185.25 state, plus 2,964 × 2% = $59.28 local, for **$244.53**. If filed by 10/20, less the 0.5% timely discount of $1.22, the total is **$243.31**.
- **Method rulings applied (Margin Standard v1.1 §8):**
  - **Credited items leave revenue.** Excluded: Wallace s9.23 $58 and s9.25 $70, Burlingame s9.25 $86, and the excess-credit rows.
  - **Transfers.** A transferred item is not a sale; the redemption row (credit or credit transfer) is taxed as the standard member package of the event the money landed on. That covers Cloer a9.21 → a18.5 (full $203 BOTH via the $99 top-up), South a18.5 → s9.23 + s9.24 ($26 refunded), Melchor a9.24 → a9.25, P. Youngs and Sharitz s9.24 → s9.25, and the redemptions by J. Wilson (s9.25) and Sharitz (s9.22).
  - **Also excluded:** refunds (both Billeauds and Clarkson's s9.23), Rideout's Fall NET $50 (refunded, so his s9.25 is taxed as NET $86), comps (Straiton, Kerry), Espinosa's $0 contest row, and **all Lone Star Cup money**: Cannon's $325 item, the 6 practice-round rows, and the Venmo/Zelle deposits. Those are liabilities until the Cup (Kerry 9/30); the October return carries the markup.
- **Open question (not in the return):** a $203 Venmo "external payment" for Kaleb McDonnell on a18.5 (9/10, ledger `ext-pay-2843`) points at item 2843, which no longer exists. His a18.5 entry was paid on GoDaddy order R514052706. His $250 Venmo on 9/25 has no event tag, and he is on the LSC roster, so it is treated as an LSC deposit. Both are logged for the CFO daily.
- **Working:** the scratchpad `sep_tax.py` (the CFO session), with per-item lines.

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
3. Re-verify every month in the table against OneDrive confirmations, and update this file. A month Kerry has stated is paid stays PAID; a new month becomes PAID only when its confirmation PDF appears in OneDrive or Kerry says so.
4. For the month just ended, and for every UNVERIFIED or NOT FILED month past its due date, compute the WebFile inputs by the skill:
   - Total Texas Sales: gross per unique order, including Venmo and manual payments;
   - Taxable Sales, with its breakdown;
   - tax, discount and balance due.
   Apply Margin Standard v1.1 §8: coupons net once per order; credited items leave revenue; fees are never refunded. WebFile rounds sales to whole dollars.
5. Email Kerry through the Tracker mailer: the dry run `scoring-mail-kerry:<subject>|<html>`, then `scoring-mail-kerry-send:` (Kerry-only, and no `|` inside the content). Keep it HTML and short enough for a phone. Include:
   - the amounts to pay now, past-due first;
   - the WebFile link;
   - the instruction to save the confirmation PDF;
   - the register.
6. Commit this file, then post a record to the mailbox (topic `sales-tax`).
7. Never file, never pay, and never email anyone but Kerry.

## Known data issues that affect the return (see also `finance-variance-register.md`)

- **The 2026 TGF Championship has 13 August allocation rows still `pending`,** all at $0 taxable, so the Tracker figure understates August. Compute the Championship from the Pricing Master; don't rely on the allocations.
- **The live `margin_model_cutover` setting is 8/27, but Standard v1.1 §2 says 9/5.** August orders dated 8/27–8/31 were therefore allocated on the residual model, which produces negative first-timer rows. The filing method (the rate card, per the skill) is not affected.
