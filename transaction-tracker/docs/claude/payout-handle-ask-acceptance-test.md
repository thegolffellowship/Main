# Payout Handle Ask: CFO Acceptance Test (v0.1, draft)

**Owner: tracker-claude (CFO lane).** Written 2026-10-17, before Tracker Build ships.

**Sources:**
- CoS #1977 item 9: "CFO owns the acceptance test (a payout with no handle triggers exactly one ask; a saved handle clears the flag; no payment is made by the system)".
- Tracker Build's ACK, #1979.
- The build is modelled on the handicap ask (v2.569.x, #1958/#1959).

**Status:** draft. It runs when Tracker Build posts the build, before Kerry's "Deploy" and before `payout_ask_auto` is turned on.

## Rules the test protects

1. The system **never pays anyone.** Kerry sends every payment himself (#1866: booking is not paying).
2. **One ask per player while that player has an open payout,** plus one reminder 2 days later, sent in the daytime only. There are never duplicates.
3. **Nothing goes out without Kerry's approval:**
   - `payout_ask_approved` must match the live wording;
   - `payout_ask_auto` must be on.
4. **A saved handle clears the flag.** The Unpaid row then shows the handle, and no reminder goes out.
5. **Do-not-contact is absolute.** Luke Mazanec is do-not-contact. A player with that flag never gets an ask; the row goes to Kerry instead.

## How it is run

- Run on a staging copy or in preview mode, with mail captured to a sink. **No member email** goes out during the test.
- Take a before snapshot and an after snapshot of all four of these, to the cent:
  - `scoring-money-flow` (YTD);
  - `scoring-liabilities`;
  - the count of `expense_transactions` rows;
  - the count of `acct_transactions` rows.
- Use test customers. Mark Parker (cid 833, $16.25) and Michele McCormick (cid 765, $11.50) are the first live cases, but only after Kerry approves.

## Cases

| # | Setup | Expected | Pass if |
|---|---|---|---|
| A1 | Record one payout for a player with no handle (`venmo_username` and `payout_method_handle` both empty) | One ask is queued on the next run, logged with customer, payout id and time | Exactly 1 email in the sink |
| A2 | Re-run the job three more times | No new email | Still exactly 1 |
| A3 | A second open payout for the same player while the first ask is open | No second ask. The page and the Unpaid row cover every open payout | Still 1 email, and both rows show "ask sent" |
| A4 | 48 hours pass with no handle saved | Exactly 1 reminder, in the daytime window only. None at night: a run at 11 PM sends nothing, and the 8 AM run sends | 1 reminder, timestamp in the window |
| A5 | Player already has a handle on file, and a payout is recorded | No ask | 0 emails |
| A6 | Player opens the link and saves "@Some-Name" | Leading @ stripped, format checked, shown back for confirmation. On confirm: `customers.venmo_username` is written and who/when is stamped. The Unpaid row shows the handle with Copy and Pay-in-Venmo | Handle stored once. Flag cleared. No reminder after this |
| A7 | Bad input: blank, spaces, illegal characters | Refused with a plain message; nothing written | No customer write |
| A8 | Tampered, expired, or another player's token | Refused; nothing written | No customer write |
| A9 | **No payment by the system** | After A1–A8: no payout row is marked paid, no new `expense_transactions` or `acct_transactions` row, no call to any Venmo, PayPal or bank API | Every before/after snapshot identical to the cent. Payout `payment_status` still `pending` |
| A10 | `payout_ask_auto` off | No send | 0 emails |
| A11 | Wording changed so the stamp no longer matches | No send, and the change is flagged for Kerry | 0 emails |
| A12 | Player flagged do-not-contact | No send. The row is listed for Kerry | 0 emails |
| A13 | Payout paid another way before the reminder (Zelle or Apple Pay, as with Saldana and Angelone) | Reminder suppressed once the payout reads paid | 0 reminders |
| A14 | Kerry's own winnings (recorded as cash), a $0 row, or a comp | No ask | 0 emails |
| A15 | Guest or 1st Timer with no handle (Mark Parker is a 1st Timer) | The ask still goes out. Links are for everyone (#1977 item 3), unlike the handicap ask | 1 email |
| A16 | Backfill digest before the first live send | Lists every open payout with no handle: name, cid, event, amount, days open, and a total | Matches the CFO's own count from `get_event_payouts`. At 10/17 that is at least Parker $16.25 and McCormick $11.50 |
| A17 | Audit trail | Each ask and reminder is in `message_log` with `customer_id` and `event_id` set, which db-claude flags as missing today (#1953) | Both ids present on every row |

## Sign-off

- **The CFO posts PASS or FAIL per case on the mailbox** (topic `payout-handle-ask`).
- **Any failure on A2, A9 or A12 blocks the release.**
- After PASS, the test goes into the Payout Standard at its next revision (#1977 item 9).

## Open question already with Kerry (from Tracker Build's mockup, #1979)

When the player has no Venmo, should the ask offer Zelle, TGF credit, or Venmo only?
- If **TGF credit** is offered: choosing it must create a held account credit (Pricing Master v2.2 §6.3) for the payout amount and mark the payout settled-by-credit. A new case **A18** will test that the payout and the credit tie to the cent.
- If **Zelle** is offered: the page stores a Zelle phone or email, and the same no-payment rule (A9) applies.
