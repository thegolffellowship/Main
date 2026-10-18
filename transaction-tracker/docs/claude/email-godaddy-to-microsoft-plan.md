# Email: Move Microsoft 365 Off GoDaddy (Step-by-Step Plan, v0.1)

**Owner:** tracker-claude (CFO lane) drafted this on 2026-10-18 at Kerry's request: "need a full step by step plan for moving from GoDaddy to Microsoft wherever that makes sense."
**Who does what:** Priya (launch ops) leads. Kerry makes the GoDaddy call and buys the licenses. Tracker Build verifies the Tracker's mail jobs.
**Status:** draft for Kerry and Priya. Nothing has been changed, cancelled or bought.

## Why

TGF pays GoDaddy **$1,226.49 a year** for email (from Kerry's GoDaddy billing export, 10/18):

| Address | Plan via GoDaddy | Cost per year |
|---|---|---|
| admin@ | M365 Business Professional + Advanced Email Security | $255.71 + $63.83 = **$319.54** |
| kerry@ | M365 Email Plus + Advanced Email Security (3-year, prepaid to 3/16/28) | $574.87 / 3 = **$191.62** |
| austin@, robert@, dfw@, james@ | Email Essentials + Advanced Email Security, each | $115.00 + $63.83 = **$178.83** x 4 = $715.33 |

- Essentials alone has gone from $71.88 (2023) to $107.88 (2026) per mailbox.
- "Advanced Email Security" is Proofpoint, resold by GoDaddy. It's charged per mailbox.
- Buying from Microsoft directly costs much less. List prices from the July 2026 Microsoft increase, as reported by resellers; confirm on Microsoft's site at purchase:
  - Business Basic: about $7.00 per user per month, annual.
  - Business Standard (desktop Office apps): about $14.00 per user per month, annual.
- **Shared mailboxes are free:** no license up to 50 GB. People open them with their own login (Microsoft Learn, "About shared mailboxes").

## What changes and what doesn't

- **Domain registration stays at GoDaddy.** thegolffellowship.com costs $23.19 plus $24.99 privacy a year (Kerry's ruling, #1997). That's not where the money goes.
- **The Microsoft 365 tenant stays the same.**
  - All mail, OneDrive and the admin@ account stay where they are.
  - Only the *seller* changes: GoDaddy hands the tenant back to Microsoft ("defederation").
  - Source: GoDaddy, "Move my Microsoft 365 email away from GoDaddy"; Microsoft Learn, "Defederation Process for Microsoft 365 Admins Using GoDaddy".
- **One-way.** GoDaddy states the organization can't move back to GoDaddy. Preparation is the only safety net.

## Target end state (Kerry decides the rows marked DECIDE)

| Address | After the move | Cost per year (approx.) |
|---|---|---|
| admin@ | Licensed user, Business Standard (keeps desktop Office, OneDrive, and the Tracker's order inbox) | ~$168 |
| kerry@ | DECIDE: (a) convert to a free shared mailbox that admin@ opens and sends as, or (b) its own Business Basic | $0 or ~$84 |
| robert@ (Robert Straiton, Austin) | DECIDE: own login (Business Basic) or a shared mailbox | ~$84 or $0 |
| james@ (James Jones; was houston@) | DECIDE: own login, or shared mailbox renamed back to houston@ | ~$84 or $0 |
| austin@, dfw@, houston@ | Shared mailboxes, opened by the chapter manager or Kerry | $0 |
| Advanced Email Security | Dropped. Microsoft's built-in Exchange Online Protection (spam, malware) stays on | $0 |

**Total: about $168 to $420 a year instead of $1,226.49. Saving: about $800 to $1,050 a year.**

## Timing

- GoDaddy renewals: admin@ on **1/16/27**; the four Essentials boxes on **2/10/27**; kerry@ prepaid to 3/16/28.
- **Target move week: Mon 1/4/27.**
  - That's before the 1/16 renewal.
  - It avoids the 12/1 payments cutover month.
  - It must not overlap the website domain cutover in mid-January (CoS #2004). Never change email DNS and website DNS in the same week.
- Not during an event window.
- Keep GoDaddy auto-renew **ON** until the move is confirmed. If it slips past 1/16, paying one more month is safer than letting admin@ lapse.

## Step by step

### Phase 0: decisions (Kerry, by Tue 12/15)

1. Decide the rows marked DECIDE above: kerry@, robert@, james@/houston@.
2. Confirm who opens each shared mailbox.

### Phase 1: preparation (Priya and Tracker Build, by Fri 12/18)

3. **Inventory.** List every mailbox, alias, forwarding rule and mailbox size. Shared mailboxes must be under 50 GB.
4. **List everything that signs in to the tenant.**
   - The Tracker's mail jobs: order inbox, RSVP inbox, expense alerts, bounce inbox.
   - Claude's Microsoft 365 connector.
   - OneDrive sync, phones and Outlook on each device.
   - Find out whether the Tracker reads mail with an app registration (survives the move) or a user password (breaks when passwords reset in step 11).
5. **Check GoDaddy's prerequisites:**
   - the GoDaddy account can be validated;
   - the GoDaddy account's contact email is **not** a thegolffellowship.com address. Today it's niester@mac.com, which is correct; keep it that way, because the temporary password goes there;
   - all email plans are active and in good billing standing;
   - no mailbox expires within 5 business days of the move;
   - every admin can reach their MFA methods.
6. **Release anything worth keeping from Proofpoint quarantine.** Quarantine digests stop after the move.
7. **Two days before the move, lower the MX record's TTL to 300 seconds** in GoDaddy DNS.

### Phase 2: the move (a weekday morning, week of 1/4)

8. **Switch mail delivery off Proofpoint first** (GoDaddy's instruction for Advanced Email Security customers):
   - Replace MX `mx1-us1.ppe-hosted.com` and `mx2-us1.ppe-hosted.com` with `thegolffellowship-com.mail.protection.outlook.com`, priority 0.
   - Check that the SPF record includes `spf.protection.outlook.com` and drop the Proofpoint include.
   - Send test messages in and out.
9. **Call GoDaddy** (a GoDaddy Guide) and ask to "move my Microsoft 365 email away from GoDaddy." They open a ticket.
10. **Next business day:**
    - GoDaddy emails a temporary password to niester@mac.com.
    - Sign in at admin.microsoft.com as admin@ with it, and set a new password at once.
    - MFA isn't reset.
11. **Buy licenses from Microsoft inside this same tenant** (Billing > Purchase services).
    - **Don't buy anything from Microsoft before step 10.** That would create a second tenant that can't be merged.
    - Assign the new licenses, then remove the GoDaddy licenses from each user.
    - Reset passwords for the other licensed users.
12. **Convert the chapter boxes to shared mailboxes.** The mailbox must still be licensed at the moment you convert it; remove the license afterwards. Grant access to the right people.
13. **Sign back in everywhere:**
    - phones and Outlook;
    - Claude's Microsoft 365 connector (re-authorize);
    - any Tracker mail credential found in step 4.
14. **Verify the Tracker** (Tracker Build). New orders, RSVPs, Chase alerts and bounces all arrive. Watch the 5:00 AM health digest the next morning.

### Phase 3: clean-up (within 7 days)

15. In GoDaddy, remove the email plans and turn off their renewals. GoDaddy deletes add-ons as part of the move, then suspends its plans 7 days after the addresses leave its database.
16. Ask GoDaddy for a refund of unused prepaid time, mainly kerry@ (prepaid to 3/2028), under its refund policy. **Don't count on it.**
17. Books (CFO): the new Microsoft charges go on the TGF card (the replacement for 7680) as Software & Technology. Record the GoDaddy refund if one comes.

## Risks

- **Licence gap:** buy and assign in the same sitting as step 10.
- **Second tenant:** never buy from Microsoft before GoDaddy finishes.
- **Lost sign-ins after the password reset:** step 4 inventory, step 13 checklist.
- **Mail delivery gap:** MX first (step 8), low TTL (step 7), test before calling GoDaddy.
- **DNS collision with the website cutover:** separate weeks.

## Not recommended now

Moving the domain registration itself off GoDaddy saves only about $25–40 a year. It would add DNS risk during the website move. Revisit after the website settles.

A smaller saving that can be done any time: GoDaddy's "Full Domain Privacy and Protection" ($24.99 a year) is an upsell. Check whether the free basic privacy covers you before the 4/2/27 renewal.
