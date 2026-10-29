# Twilio texting: toll-free 833 number (WORKING DRAFT, not ratified)

> **UPDATE 2026-10-29 (Kerry): the 833 number is being RELEASED.** Twilio support (Oscar G., ticket #29975540) offered the one-time refund of the -$67.32 balance only if the number was released; Kerry authorized the release by email the same day ("No, release it"). The number was never verified, used or published. When texting is ready, buy a new toll-free number and run verification with it; everything below that names +1 (833) 440-2738 is history.

Started 2026-10-17 with Kerry. Nothing is sent, built or paid from this doc.
Rule 3b: the consent field, the opt-in page and every member-facing word need
Kerry's OK first (CoS #1990-4: "SMS consent is its own field and its own
consent, separate from email").

## Rulings

- Kerry 10/17: "Seems like we might be at a good point to get Twilio."
- Kerry 10/17 on the number: "Ok, we'll stick with the 833." The number is
  **+1 (833) 440-2738**, toll-free, already on the account, SMS + MMS capable.
  Why toll-free: one number for every chapter (not tied to 210 or 512),
  simpler carrier approval with no brand or monthly campaign fee, higher
  throughput. A local number for Kerry's own lead conversations can come later.
- Texts stay small and personal for now; a native app with push takes over most
  of them later (Kerry 10/17: "maybe texts reduce considerably once we have a
  native app").

## Account state (10/17)

- Account "My first Twilio account" (SID in the Twilio Console only, never in the repo),
  owner Kerry. SUSPENDED for lack of funds, balance **-$67.32**.
- Statements: May 2023 $0.05; Jun 2023-Feb 2024 $2.29/month (the toll-free
  number, $2.15 + tax); $0.00 every month since March 2024. Likely cause
  (inference, not confirmed): the number's $2.15/month kept accruing to the
  balance while suspended (31 months x $2.15 = $66.65).
- Support ticket **#29975540** (P3) asks for the itemization and a waiver.
  Correction comment to add: the 833 number is still on the account.
- Messaging status on the number: "Toll free verification required".
- The Auth Token is a password: Railway variable only, never chat, email or repo.

## Order of work

1. Twilio answers #29975540; Kerry settles what is left plus ~$20 on the TGF
   card (Sarah: don't pay an unexplained bill). Account reactivates.
2. Prerequisites for verification (all must be live, public URLs):
   a. **Privacy Policy.** thegolffellowship.com/privacy-policy-1 currently
      says only "Privacy Policy coming soon". Verification is rejected
      without a real one (Twilio requires separate Privacy Policy and Terms
      URLs from 9/15/2026, error 30493). It must NOT say we share or sell
      opt-in data. Draft below for Kerry.
   b. **Terms / SMS Terms.** thegolffellowship.com/policies is event policies
      only. An SMS terms section is needed (draft below).
   c. **Opt-in proof page.** A public page showing exactly where and how a
      person agrees to texts (error 30476 if missing, 30509 if behind a login).
      Plan: a public Tracker page `/sms` showing the consent box and the SMS terms.
   d. **Business profile** in Trust Hub with the EIN matching "The Golf
      Fellowship, LLC" (Kerry enters the EIN and address himself).
3. Kerry submits toll-free verification with the answers below.
4. Build (after Kerry ratifies): `customers` SMS consent field via db-claude
   migration (separate from email consent, with consent time + source), the
   consent box on registration / profile / invitation page, STOP/HELP handling
   back into the Tracker, the send path behind a dial + wording stamp like every
   other member send.

## Draft verification answers (for Kerry to paste)

- **Business name:** The Golf Fellowship, LLC
- **Website:** https://www.thegolffellowship.com
- **Business registration:** EIN (Kerry enters)
- **Contact:** Kerry Niester, thegolffellowship email
- **Use case category:** Account Notifications (or "Mixed" if invitations by
  text are added later; open question to Kerry)
- **Estimated monthly volume:** 1,000
- **Use case description:**
  > The Golf Fellowship runs weekly golf events for its members in San Antonio
  > and Austin, Texas. We text members and players who have opted in about
  > their own events: tee times and group assignments, a seat opening or a
  > change to their group, the morning-of event link, reminders to complete
  > their profile (handicap, payout details), and replies to people who asked
  > us about joining. We do not send promotional texts to anyone who has not
  > opted in, and we never share or sell phone numbers or consent.
- **Opt-in type:** Web form
- **Opt-in description:**
  > Players opt in by checking an unchecked box when they register for an
  > event or update their profile on our site. The box is separate from email
  > consent and is not required to register or pay. The box states what we
  > send, that frequency varies, that message and data rates may apply, and
  > that they can reply STOP to opt out or HELP for help, with links to our
  > SMS Terms and Privacy Policy.
- **Opt-in proof URL:** the public `/sms` page (to be built)
- **Sample messages:**
  1. `TGF: You're in for Tue 10/27 at TPC Canyons. Tee time 4:10 PM, Group 3 with Mark, Tom and Jeff. Details: <link> Reply STOP to opt out.`
  2. `TGF: A spot just opened in Tuesday's game at Avery Ranch (1 seat left). Grab it here: <link> Reply STOP to opt out.`
  3. `TGF: Congrats on your $16.25 win at Avery Ranch! Tell us where to send it: <link> Reply STOP to opt out.`
- **Opt-in confirmation message:**
  `TGF: You're signed up for texts about your Golf Fellowship events. Msg frequency varies. Msg & data rates may apply. Reply HELP for help, STOP to opt out.`

## Draft consent box (member-facing, Kerry ratifies)

> [ ] Text me about my TGF events (tee times, group changes, open spots and
> winnings). Message frequency varies. Message and data rates may apply.
> Reply HELP for help or STOP to opt out. Not required to register or pay.
> SMS Terms | Privacy Policy

## Draft SMS Terms (for the website, Kerry ratifies)

> **TGF Text Messages.** By checking the text box, you agree to receive text
> messages from The Golf Fellowship at the number you provided about your
> events: tee times, group changes, open spots, payouts and account reminders.
> Message frequency varies. Message and data rates may apply. Reply STOP to
> stop at any time; you'll get one confirmation and no more texts. Reply HELP
> for help, or contact us at <email>. Consent is not a condition of any
> purchase. Carriers are not liable for delayed or undelivered messages.

## Privacy Policy

Needed before verification. A short plain policy covering what TGF collects
(name, email, phone, handicap, payment handles, scores), why (running events,
payouts, handicaps, member communication), who it goes to (only service
providers that run those things, such as payment, email and text providers),
that we never sell personal data or share text-message opt-in data with third
parties for their marketing, how to ask for changes or deletion, and a contact.
Draft: `privacy-policy-draft.md` (10/17). It is a legal page, so his OK (and his judgment on any
outside review) comes first.

## Sources

- Twilio Toll-Free Verification Onboarding Guide:
  https://support.twilio.com/hc/en-us/articles/13264118705051-Toll-Free-Verification-Onboarding-Guide
- Opt-in rejection 30476: https://www.twilio.com/docs/api/errors/30476
- Business registration number change:
  https://www.twilio.com/en-us/changelog/we-re-adding-business-registration-numbers-to-toll-free-verifica
- Tollfree verification resource:
  https://www.twilio.com/docs/messaging/api/tollfree-verification-resource
