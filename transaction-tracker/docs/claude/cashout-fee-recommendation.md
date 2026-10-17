# Cash-Out Fee: CFO Recommendation (for Kerry beside R15, 10/30)

**Owner:** tracker-claude (CFO lane). Written 2026-10-17.

**Asked by:** CoS #1990 item 1 ("pass through $0.25 exactly or round; per cash-out or per payout").

**Background:**
- **Kerry's ruling, #1988:** "Yes make credit default … cash out each time which will also include fees … They can also cash out whenever they want on request but same fees will apply. Confirm PayPals actual fees."
- **PayPal fees, as confirmed in #1988:**
  - Payouts API: **$0.25 flat per payout item**, US, USD.
  - Web upload: 2% capped at $1.00.
  - Venmo recipients pay the same as US PayPal Payouts.
  - Recipients pay nothing.
- **Status:** recommendation only. Nothing is built, charged or paid. Until 12/1, payouts stay as they are today (#1989).

## Recommendation

**Pass through exactly PayPal's per-item fee, $0.25 today, once per cash-out. Deduct it from the amount sent. Never charge it per prize. Never round it up.**

1. **Charge it once per cash-out, not per prize.** PayPal charges per payout item sent. A wallet cash-out that covers three prizes is one item and one $0.25. Charging per prize would collect $0.75 for a $0.25 cost.
2. **Charge exactly $0.25 and don't round.**
   - Rounding to $0.50 turns $0.25 per cash-out into TGF revenue. Under the Pricing Master's rule, any dollar TGF keeps is taxable markup, so that $0.25 would need a Pricing Master line and sales tax.
   - It would also undercut the message Kerry chose ("save them money in transaction fees").
   - At cost, the fee is a pure pass-through: no margin and no tax.
3. **Mechanics: deduct it from what is sent.**
   - Example: a $16.25 cash-out sends $16.00, and the $0.25 goes to PayPal.
   - The player's held balance closes to exactly $0 and TGF's books net to $0.
   - **Booking:** held money −$16.25; cash out −$16.00 to the player and −$0.25 to PayPal. The fee is recorded as settled from player money, **not** as a TGF expense.
4. **Tie it to the real fee.** Store the fee as one setting (`cashout_fee`, initially $0.25) that matches PayPal's current Payouts API fee. Show it on the onboarding question and the cash-out screen. If PayPal changes its fee, the setting changes, with Kerry's OK.
5. **Set a $1.00 minimum cash-out.** Below that, the fee would take more than 25% of the amount. Smaller balances stay in the wallet until they grow. (Optional; Kerry decides.)
6. **Always use the API route.** The Tracker sends through the Payouts API ($0.25). If a payout is ever sent by web upload instead (2%, capped at $1.00), TGF absorbs any difference above $0.25 rather than changing the player's fee.

## What Kerry decides (one line on 10/30)

"Cash-out fee = PayPal's per-item fee ($0.25 today), once per cash-out, deducted from the amount sent; $1.00 minimum: yes or no?"

## Check before 12/1

This goes into the 11/13 fees-to-the-cent test. The fee and minimum are new cases in the payout tests, alongside the payout-handle ask acceptance test in `payout-handle-ask-acceptance-test.md`.

1. **One cash-out covering three prizes deducts $0.25 once.** The player gets the total less $0.25.
2. **The balance clears to $0.00, and the ledger shows no TGF revenue or expense from the fee.**
3. **A cash-out request below the $1.00 minimum is refused with a plain message,** if Kerry adopts the minimum.
4. **Wallet credit (the default) has no fee.** Applying credit to an event is fee-free.
