# CPA Question Register: Rick Ruiz, CPA

Owner: CFO › CPA Questions lane (session `session_01Ux2pULvc52TZCuQCauhSQf`, mailbox topic `cpa-questions`).
Reports to: the CFO (tracker-claude, topic `finance-audit`) and Kerry.
Opened: Tue 2026-10-13. Last updated: 2026-10-13 (mail read through #1721).

## What this file is

One living list of every question TGF needs to put to Rick Ruiz, CPA. Each entry carries the facts and amounts, its sources (mailbox ids or files), Kerry's current position, what the books do in the meantime, the status and Rick's answer.

Ground rules:
- Questions are written as questions for Rick. Nothing here is tax advice or a conclusion about what is deductible or taxable. Where a lane has cited a rule (for example IRC §274(m)(3)), it is quoted as context for Rick to confirm or correct.
- This lane never books, restates or reclassifies a ledger row. When Rick answers, the bookkeeping change goes to the CFO as a proposal, and the CFO acts only with Kerry's OK (rule 3b).
- This lane never contacts Rick. Kerry does.
- Account numbers are last 4 only.
- Kerry's rulings are quoted verbatim and are not reopened here. Rick confirms or corrects them.

Status values: **open** (not yet asked), **asked** (Kerry has put it to Rick), **answered** (Rick's answer recorded), **with Kerry** (needs Kerry's own ruling before it can go to Rick), **candidate** (found in the record; waiting for the CFO to confirm it belongs on the list).

As of 10/13 there is no record in the mailbox of a meeting with Rick, so every 9/30 question is still **open**. The 9/30 list was meant for a weekend Board session (CoS #1060, #1075); no outcome of that session is on the record.

## Count

| Status | Count |
|---|---|
| open | 11 (Q2, Q4, Q6, Q7, Q9, Q10, Q11, Q12, Q13, Q14, Q15) |
| with Kerry | 1 (Q16, Chase Slate) |
| candidate | 8 (C1–C8) |
| asked / answered | 0 |

Q1, Q3, Q5 and Q8 from the 9/30 audit were Kerry's own decisions, not CPA questions. They are listed at the end for completeness.

## Ask first

1. **Q4, 1099s and W-9s.** Deadline January 31, 2027, and W-9s must be collected before then.
2. **Q11, the Lone Star Cup markup on the October return.** The October 2026 return is due November 20, 2026.
3. **Q2 + Q7, accounting basis and gross vs net.** These two shape the chart of accounts v2 and every Schedule C line.

---

## Group A: Sales tax

### Q9. Two Man Tour contract income and Texas sales tax
- **Question:** Is the contract income TGF earns from Two Man Tour subject to Texas sales tax? Managing events for another company may be treated differently from TGF's own event sales.
- **Facts:** Two Man Tour is its own company that TGF LLC contracts for. Kerry wants it inside TGF's numbers on one Schedule C, tagged separately (categories prefixed `Two Man Tour:`). Its team skins pots pass through the TGF Venmo (for example David Hooper's $100 on 8/8, acct 13446 / exp 2308).
- **Sources:** #1069, #1070, #1071; Bookkeeping Audit artifact Q9.
- **Kerry's position:** "Two Man Tour is it's own entity, but it is just another company that The Golf Fellowship LLC contracts for. I would like to avoid submitting it as a separate schedule C though and just put it in The Golf Fellowship LLC's numbers." (9/30, #1070). No position on sales tax.
- **Books meanwhile:** entity TGF, `Two Man Tour:` categories. Pot money (Hooper $100) is not revenue and was left out of the August return.
- **Status:** open. **Rick:** —

### Q11. Lone Star Cup markup: October return, not the deposit months
- **Question:** Confirm that the LSC markup is reported on the October sales-tax return (the month the Cup is played), not in the months the deposits came in.
- **Facts:** Deposits came in August–September (CFO counted $8,140 by 9/30). Cup played 10/9–10/11 at The Hideout, Brownwood. Markup per event config: $55 per entry, $12 per practice round (#1049). Revised Cup P&L (#1712): 27 paid entries × $250, 14 Friday × $110, 22 skins × $75, lodging $2,180 pass-through.
- **Sources:** #1049, #1050 (Kerry ruling, cited in #1071), #1071, #1712; artifact Q11.
- **Kerry's position:** deposits are liabilities until the Cup is played ("liabilities right now, for sure", quoted in the artifact); markup goes on the October return (#1050 via #1071).
- **Books meanwhile:** deposits held as Cup money, not revenue (#1337 §2). October return due 11/20/2026.
- **Status:** open. Time-sensitive. **Rick:** —

### Q12. Cup shirts: resale certificate instead of paying sales tax
- **Question:** TGF paid Texas sales tax on shirts that were handed to players as part of a taxable Cup entry. Could TGF have bought them tax-free on a resale certificate? Should it do so for future team shirts?
- **Facts:** MAVN invoice #000035, "The Golf Fellowship October 2026 Shirt Order": $4,086.47 + $337.13 Texas sales tax = $4,423.60, paid 10/8 on Visa 7680 (ledger 16745). About 62–64 shirts (2 per player + extras). No per-shirt, embroidery or shipping breakdown. Shirts are funded by the LSC shirt fund ($10 per membership; 2026 Cup year = 117 × $10 = $1,170).
- **Sources:** #1712, #1714.
- **Kerry's position:** none on the tax. Kerry on the price: Mason Wyatt quoted "about $50 per shirt" plus embroidery, rush shipping and taxes.
- **Books meanwhile:** full $4,423.60 is a Cup cost (team shirts).
- **Status:** open. **Rick:** —

### C1 (candidate). Monthly netting of sales tax, the zero floor, and amending filed months
- **Question:** (a) Is it right to net the taxable margin within a month, so a loss-leader round (a discount larger than the markup) reduces that month's Total Taxable Sales, with the month floored at zero? (b) Has TGF over-remitted on past months, and should those returns be amended?
- **Facts:** The $25 discount is larger than the whole 9-hole markup ($8 + $10 = $18), so some rows have negative margin (#423 §3). Kerry ratified monthly netting on 9/9 (#436). April 2026's workbook computed taxable $4,516.80 (tax $370.77) against the Tracker's $3,474 → $287.25, so April may have been over-remitted by roughly $85, partly from doubled per-item fees (handoff-2026-09-09 §7). The 2025 months are reconstructions and moved twice (#448). January 2026 is UNVERIFIED (sales-tax-register.md).
- **Sources:** #420, #423, #436, #448; `handoff-2026-09-09-financial-audit.md` (D4); `sales-tax-register.md` (branch claude/review-attached-prompt-2nhbqy).
- **Kerry's position:** "Shouldn't minus margins be minus sales tax too? ... Comptroller only asks for Total Sales and Total Taxable Sales for the month, not the per transaction breakdown. So in my mind, that seems like something that should reduce my Total Taxable Sales amount." (#436). "We can always amend past reporting if necessary." (#435/#436).
- **Books meanwhile:** `tax_reserve` signed per row, month floors at zero (v2.352.0). Filed months not restated.
- **Status:** candidate (the CFO to confirm). **Rick:** —

### C2 (candidate). The card-fee spread in the taxable base
- **Question:** TGF charges a flat 3.5% transaction fee; GoDaddy's actual fee is less on most orders. Is the difference (the "spread", +$592 lifetime over 1,979 orders) taxable margin, as TGF now treats it?
- **Facts:** Spread measured at +$592.02, −$0.26 to +$2.99 per order (#423 §1). Since the 9/5 cutover it is inside `tgf_operating` and taxed (#434).
- **Sources:** #420, #421, #423, #434.
- **Kerry's position:** "I believe the right thing to do is to pay Sales Tax on it because that money is not allotted to anything but margin." (9/9, #434).
- **Books meanwhile:** taxed from 9/5; earlier rows frozen.
- **Status:** candidate. Low stakes; a confirmation only. **Rick:** —

### C3 (candidate). Late-filing penalties
- **Question:** Confirm the treatment of Texas sales-tax late-filing penalties: booked as a penalty expense, separate from tax, and (as generally understood) not deductible.
- **Facts:** $194.85 in 2026: April $65.75, June $70.54, August $58.56. Paid with the returns.
- **Sources:** #1301, #1337 §2; `sales-tax-register.md`.
- **Kerry's position:** none stated. The CoS wrote "penalties aren't deductible" (#1301); that is the CoS's statement, not a ruling.
- **Books meanwhile:** penalty expense, not tax.
- **Status:** candidate. **Rick:** —

---

## Group B: Owner, spouse and personal

### Q6. Kerry's own play: comped seats, TGF-funded buy-ins and retained winnings
- **Question:** When Kerry plays, TGF pays his buy-ins (and sometimes comps his seat), and any winnings stay with TGF. How should each piece be recorded: the comped seat, the TGF-funded buy-in, and the winnings TGF keeps? Prize expense, owner draw, or business expense plus a contra?
- **Facts:** 9/30 audit: Kerry's own winnings had been paid in cash from TGF. Lone Star Cup: Kerry's $75 skins buy-in was TGF-funded; he won $35.94, which stayed with TGF (ledger 16822), so TGF's net cost was $39.06. His Cup entry and Friday seat were comped (seat cost $194.85 at The Hideout). Kerry has $1,617 in 2026 prizes (see Q4).
- **Sources:** #1052 (Q6), #1060, #1712; artifact Q6.
- **Kerry's position:** "Anything I win I just mark as cash. Put it back into TGF's operating expenses. Mark it appropriately for bookkeeping. Kind of the same thing as my buy-ins." (10/13, #1712).
- **Books meanwhile:** note on ledger 16822; category unchanged. Tracker Build asked for categories "Owner buy-in (TGF-funded)" and "Owner winnings retained" (#1712).
- **Status:** open (Kerry's 10/13 ruling now answers his half). **Rick:** —

### Q13. Michelle's travel and meals at the Lone Star Cup
- **Question:** Is Michelle's Cup weekend travel and meals deductible? She drove Kerry San Antonio ↔ The Hideout (Brownwood) and back, and ran event errands. She is not on payroll. If not, those rows move to owner draw.
- **Facts:** Cup weekend 10/9–10/11. Her meals and any other costs are on Kerry's personal Sapphire 6159 (amounts not yet in; the October 6159 activity is still to be uploaded). The CFO cited IRC §274(m)(3): a spouse's travel is deductible only if the spouse is an employee with a bona fide business purpose.
- **Sources:** #1715, #1716, #1718.
- **Kerry's position:** "Hers does count as business expenses because she helped me." / "She specifically drove me to and from the event from San Antonio. She also ran errands for me." (10/13).
- **Books meanwhile:** booked as TGF business expense, each row tagged "spouse – worked the event (Kerry 10/13); CPA to confirm".
- **Status:** open. **Rick:** —

### Q14. Kerry's room at the Cup (host lodging)
- **Question:** Confirm that Kerry's King room share, $581.30, is deductible TGF business lodging in full, even though Michelle shared the room.
- **Facts:** Airbnb $2,761.30 (7680, 8/19; ledger 13618) split: $2,155.00 player lodging pass-through, $25.00 Rideout waiver (Cup comp), $581.30 Kerry's room ($600 less $18.70 over-collected). The CFO's reading is that the deductible amount is what the room would cost Kerry alone, so the full share counts.
- **Sources:** #1712, #1715.
- **Kerry's position:** "TGF host cost, Michelle came. I definitely need to write it off as business expense. CODB." (10/13).
- **Books meanwhile:** $581.30 labeled TGF host lodging (Travel) in the note; the split awaits the receipt-split bridge.
- **Status:** open. Added by this lane from #1715 (the CFO raised it; Kerry ruled). **Rick:** —

### Q15. Charitable contribution paid by TGF
- **Question:** TGF paid Charity Golf International $100. Where does it go on the return: the joint personal return, or the business?
- **Facts:** Booked to a separate Charitable Contributions category, ledger 16273.
- **Sources:** #650 (#14), #653.
- **Kerry's position:** a charitable contribution; "the preparer decides the treatment" (9/24, #650).
- **Books meanwhile:** Charitable Contributions category, kept apart from operating expenses, with a preparer note.
- **Status:** open. Added by this lane: the 9/24 ruling already addressed it to the preparer. **Rick:** —

### Q16. Chase Slate 9986: the 2025 tax balance
- **Question (once Kerry re-rules):** Kerry financed TGF's share of the 2025 income tax on a 0% card and pays it down at $400 a month. Is that paydown an owner draw (a personal tax liability), or can it be treated as a TGF liability? The CFO's reading is that a pass-through paying personal income tax is still a draw for tax purposes. Same question for the IRS $1,975 Q3 2026 estimated payment on 9/14 (row 2560).
- **Facts:** Six Slate payments sit in the ledger as uncategorized TGF expenses, $1,762.29: 5/14 $85.34, 6/15 $76.95, 7/22 $400, 8/21 $400, 9/22 $400, 10/22 $400 (scheduled). Likely original charge: row 769, "IRS (via Pay1040)", 5/6, amount blank. The Frost 0341 statements show no Slate debit in July or August, so the $400 may come from a personal account (likely Chase 4153).
- **Sources:** #650 (#15, #16), #653, #1693 item 4, #1706.
- **Kerry's position: CONFLICT, not yet resolved.**
  - 9/24 (#650): "this card was used to pay the 2025 taxes at 0% for 18 months ... book it as owner draw." The $1,975 is "Q3 estimated tax on the joint return ... owner draw."
  - 10/13 (via CoS #1693): "Should be an automated payment for our IRS Taxes that we paid off with that no interest for 18 months card."
  - CFO #1706 asked Kerry to choose A (keep 9/24: personal) or B (TGF assumes the debt). CFO recommends A.
- **Books meanwhile:** nothing restated; the 9/24 owner-draw ruling was never applied to the six rows.
- **Status:** with Kerry. This lane does not resolve it. **Rick:** —

### C4 (candidate). TGF costs paid on Kerry's personal Sapphire 6159
- **Question:** TGF expenses paid on Kerry's personal Chase Sapphire 6159 are booked as TGF expenses paid by the owner (owner contribution). Is that the right treatment, and what documentation does Rick want?
- **Facts:** FACEBK ads 8/31 $75.00, 9/4 $75.00, 9/9 $49.61 (ledger 16269–16271); golf-course charges awaiting Kerry's group ruling (#653 item 4, $137.44 unbooked); Cup weekend costs still to come.
- **Sources:** #648 (via #650), #653, #1715 §3.
- **Kerry's position:** FACEBK is TGF advertising (#648); "there will be some other costs coming from 6159 from this weekend that I need to write off." (10/13, #1715).
- **Books meanwhile:** owner-contribution treatment; golf-course food and drink need Kerry's confirmation before booking.
- **Status:** candidate. **Rick:** —

---

## Group C: Entity and lines of business

### Q10. Two Man Tour pots as held money
- **Question:** Two Man Tour pots (such as team skins buy-ins) pass through the TGF Venmo. Should they be carried as money TGF owes players until paid out, alongside the HIO pot and the Lone Star Cup deposits?
- **Facts:** Hooper $100 (8/8), category "Two Man Tour: Skins Pass-through" (id 83). An earlier $500 "Two-Man Tour" expense (exp 322, April) sits ignored.
- **Sources:** #1069, #1070, #1071; artifact Q10.
- **Kerry's position:** none on the liability question. CFO's reading: yes.
- **Books meanwhile:** pass-through category, not revenue. No liability posted (GL 2000/2100/2200 have no postings).
- **Status:** open. **Rick:** —

### C5 (candidate). The LSC shirt fund
- **Question:** $10 of every membership is set aside for Lone Star Cup shirts. Is it right to treat this as a TGF-owned earmark (TGF's own revenue, set aside internally), not a liability owed to members?
- **Facts:** 2026 Cup year (Aug 2025–Jul 2026): 117 × $10 = $1,170. The 2026 shirts cost $4,423.60, so the fund covered about a quarter. Renewals ($75) and new ($50) both fund it.
- **Sources:** #422 §8, #423 §3, #435/#436 §2, #1712.
- **Kerry's position:** all memberships fund shirts; the Cup in October is the point of the fund (#436 §2).
- **Books meanwhile:** `lsc_shirt_fund` bucket, separate from margin; MAVN not yet tagged to the fund.
- **Status:** candidate. **Rick:** —

---

## Group D: Deductibility

### C6 (candidate). Event travel mileage: standard rate or actual
- **Question:** For TGF event travel by car (for example the San Antonio ↔ Brownwood round trip and Cup errands), should TGF claim the IRS standard mileage rate or actual vehicle costs? What log does Rick need?
- **Facts:** No fuel or vehicle cost for the Cup trip is on TGF's books. The CFO has asked Kerry for round-trip and errand miles. If fuel was charged on 6159, it is either mileage or actual, not both.
- **Sources:** #1718.
- **Kerry's position:** none yet (miles not given).
- **Books meanwhile:** nothing booked.
- **Status:** candidate. **Rick:** —

### C7 (candidate). Event meals: the 50% limit
- **Question:** Confirm that event meals (player meals at the Cup, Kerry's and Michelle's weekend meals) are business meals at 50%, and whether any (for example food provided to all players as part of the event) are 100%.
- **Facts:** Cup meals and entertainment booked so far: $54.85 (Starbucks $19.24, Papoulis $25.61, Pat Youngs $10). 6159 weekend meals still to come. Duplicate categories "Business Meals" vs "Fellowship" exist (artifact scorecard).
- **Sources:** #1706, #1715 §3; artifact scorecard.
- **Kerry's position:** none stated beyond "write it off" (#1715).
- **Books meanwhile:** booked at full amount; the 50% is the preparer's adjustment.
- **Status:** candidate. **Rick:** —

### C8 (candidate). Horizon expense paid on a TGF card
- **Question:** Trimble SketchUp Pro $399 was a Horizon contracting expense paid on the TGF card 7680. Booked as an owner draw on TGF's side. Confirm, and confirm it can be deducted on Kerry's Horizon side.
- **Sources:** #650 (#14), #653 (ledger 16272), #1337 §5.
- **Kerry's position:** "SketchUp is Horizon" (9/24, #650).
- **Books meanwhile:** owner draw, entity Personal (Horizon).
- **Status:** candidate. Low stakes. **Rick:** —

---

## Group E: Process and reporting

### Q2. Basis of accounting
- **Question:** Cash basis for the tax return, with events and deposits deferred for management reporting?
- **Facts:** Revenue is booked on the order date today. LSC deposits were booked as income until Kerry ruled them liabilities. The Tracker is single-entry with no balance sheet; a double-entry journal is proposed (Q1).
- **Sources:** #1052, #1060; artifact Q2 and scorecard.
- **Kerry's position:** none stated.
- **Books meanwhile:** cash-style, order-date revenue; deposits held per Kerry's LSC ruling.
- **Status:** open. **Rick:** —

### Q4. 1099s and W-9s for prize winners
- **Question:** Prize payouts come from player-funded pools. Is TGF the payer for 1099 purposes? Does Kerry's own $1,617 count?
- **Facts:** 21 players have $600+ in 2026 prizes, Kerry included. No W-9 tracking; no 1099 tracking in the code. 1099s are due January 31. The target model plans a `customers.w9_on_file` flag (documents stay in OneDrive).
- **Sources:** #1052, #1060; artifact Q4 and scorecard; `financial-audit-target-model.md` §9 (S2).
- **Kerry's position:** none stated.
- **Books meanwhile:** prize exposure computed by `scoring-fin-audit:prizes=2026`; nothing collected.
- **Status:** open. Time-sensitive: if Rick says yes, W-9 requests must go out well before 1/31/2027. **Rick:** —

### Q7. Course fees and prize pools: gross or net on Schedule C
- **Question:** Report course fees and prize pools gross (revenue plus expense) or net as a pass-through? Same question for the LSC lodging pass-through ($2,155) and Two Man Tour pots. How should the Venmo/PayPal/GoDaddy 1099-K gross tie to the return when much of it is pass-through money?
- **Facts:** 2026 YTD ledger gross vs waterfall differed by $114,533 at 9/9 (#444 §2). The target model plans a 1099-K tie-out per processor (S1).
- **Sources:** #1052; artifact Q7; #444; `financial-audit-target-model.md` §4, §9.
- **Kerry's position:** none stated.
- **Books meanwhile:** mixed: pass-through categories exist for lodging and Two Man Tour skins; course fees and pools flow through income and expense.
- **Status:** open (1099-K and lodging parts added by this lane as part of the same question). **Rick:** —

---

## Kerry's own decisions from the 9/30 audit (not for Rick)

| Id | Decision | Source | Where it stands |
|---|---|---|---|
| Q1 | Make a double-entry journal the ledger of record (rule 3b) | #1052, #1060 | Board session with Sarah proposed (#1060); no ruling on the record |
| Q3 | Engage the CPA now (spend >$100, Sarah) | #1052, #1060 | Kerry named Rick Ruiz on 10/13 (#1719); engagement terms not on the record |
| Q5 | Is Frost …4519 "Personal Savings" a TGF account? | #1052, #1060 | No ruling on the record |
| Q8 | Reclassify "Chase Credit Card Payment" rows from expense to transfer, with a dry run (rule 3b) | #1052, #1060 | No ruling on the record; $26,960 (8/25–9/30) counted twice |

## How new questions get here

Any lane that raises a "CPA" or "preparer" question posts it on mailbox topic `cpa-questions`, CC the CFO. This lane adds it here with its sources, dedupes it against the list, and tells the CFO. Candidates (C-ids) become numbered questions when the CFO confirms them.

## How answers come back

When Kerry relays Rick's answer:
1. This lane records it verbatim under the question, with the date, and sets status to answered.
2. This lane posts the bookkeeping change it implies to the CFO as a proposal (topic `finance-audit`), with the rows affected.
3. The CFO runs the dry run and books it only on Kerry's OK (rule 3b).

## Change log

- 2026-10-13: register opened. Seeded Q1–Q13 from the Bookkeeping Audit artifact, #1071, #1714, #1716/#1718. Added Q14 (#1715), Q15 (#650), Q16 (#1706, with Kerry). Candidates C1–C8 from #420–#448, #1301, #1337, #650/#653, #1715, #1718, #422.
