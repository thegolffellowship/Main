# Opt-out by category: SPEC, not built (2026-10-21)

Status: proposal for Kerry. Nothing here is built. The storage change is schema
(rule 3b) and every word a member reads needs Kerry's stamp. The member-facing
wording comes from CMO.

## Kerry's ruling, verbatim (10/21, via the Front Desk)

"Players who opted out of invitations should only get results emails if they
played in the event. We're probably going to need to have a step on the opt out
for what they want to opt out of which would also allow us a second step for them
to catch themselves. We have EVENT INVITATIONS - EVENT RESULTS - TGF INSIDER so far"

The first half is built on the branch as v2.577.4 (results_email.audience). It is
waiting on "Deploy".

Kerry, 10/21 addition (via the Front Desk): "Opt-out: I imagine there's some
schema there to build. Also needs an opt out (unsubscribe) from all option."
So step 1 carries a fourth choice, UNSUBSCRIBE FROM ALL, and storage leans to
option A. db-claude designs the schema and gives it a PASS, and Kerry sees it
before anything is filed.

## How it works today

- There is one opt-out list. App setting `event_invite_optout` holds a JSON list
  of customer_ids, filled by the invitation's "Stop invitations" link
  (`invitations.record_answer`, action `unsub`). It is recorded only on the
  confirm page's POST, and the scanner grace (120 s after the send) applies.
- The results email reads the same list (as of v2.577.4, only for people who
  did not play).
- The TGF Insider is sent from Brevo, and Brevo's own unsubscribe link governs
  it. The Tracker does not know who left.
- The 10/14 mail-scanner storm (Chris Best and others; restored with
  `restore_answers(keep_answers=True)`, v2.575.17) is why a link tap must
  never record anything on its own.

## The flow (proposed)

1. **Every optional email carries one link**, "Email preferences" (CMO names
   it). That covers invitations, reminders, last calls, results and the
   Insider. The link is signed per person (the existing token, a new action
   `prefs`) and names the category the email belongs to.
2. **Step 1, CHOOSE (GET, records nothing).** A page with the person's first
   name and the three categories:
   - EVENT INVITATIONS (invites, reminders, last call);
   - EVENT RESULTS;
   - TGF INSIDER.

   Each category shows its current state and gets a tick box. Only the
   category of the email they came from is pre-ticked. Below the three,
   set apart, is UNSUBSCRIBE FROM ALL, which ticks all three (and any
   category added later). Button: Continue.
3. **Step 2, CONFIRM (POST of step 1, still records nothing).** "You will stop
   getting: ... You will still get: ..." Then a fixed line: emails about an
   event you have registered for are not affected (Event Info, tee times, the
   handicap ask, the payout ask). If UNSUBSCRIBE FROM ALL (or all three) is
   ticked, the page asks once more: "Stop everything?", showing what they
   will miss. "Unsubscribe from all" is stored as one opt-out per category,
   so a later category starts off for that person too. Buttons:
   - "Yes, stop these";
   - "Go back".
4. **Done (POST of step 2, the only write).** It shows what changed and a
   "Turn back on" control, which uses the same page and is recorded the same
   way.

## Mail scanners

Scanners open links. Some run scripts. None fill in and submit two chained
forms:

- Nothing is recorded on any GET.
- Step 2 needs a one-time value issued by step 1.
- The write needs the one-time value issued by step 2.
- The existing 120 s scanner grace after the send still applies to the final
  POST.
- Every write is logged (`agent_action_log`, `email_prefs_change`) with the
  categories, source email and time, so a scanner write could be found and
  undone like the 10/14 restore.

## Storage: db-claude designs it, Kerry sees it first (schema, rule 3b)

The shape below is the input for db-claude. A person on UNSUBSCRIBE FROM ALL
also needs an `all` flag (or an `all` category row), so that a category added
later is off for them.

- **A (recommended).** A new table `customer_email_prefs`, with migration:
  - `customer_id` (FK customers);
  - `category` (`event_invitations` | `event_results` | `tgf_insider`, a
    lookup so more can be added);
  - `opted_out` (0/1);
  - `changed_at`, `source` (link / manager / brevo).

  A change writes a new row and the latest row wins, so the history is kept.
  The migration copies `event_invite_optout` into `event_invitations` rows.
  Invitations, the results email and the Brevo sync read only this table, and
  per CLAUDE.md principle 6 everything is keyed by customer_id.
- **B.** Two more app-setting lists beside `event_invite_optout`. No schema
  change, but no history, and it does not carry to the Platform.

## Rules each category follows (proposed)

- **EVENT INVITATIONS off:** no invites, reminders or last calls. They still
  get the results of an event they played (v2.577.4).
- **EVENT RESULTS off:** no results email, even for an event they played.
  This needs Kerry's confirmation.
- **TGF INSIDER off:** the nightly Brevo sync removes them from the Insider
  list. A Brevo unsubscribe comes back into the table as `source=brevo`. Brevo
  keeps its own footer link, because a working unsubscribe in a marketing
  email is required.

## Open questions for Kerry (one at a time)

1. Storage A or B.
2. Does EVENT RESULTS off also stop the results of an event they played?
3. The Insider footer: our preferences page, Brevo's link, or both?
4. Is the list of registered-event emails that cannot be turned off right?
   (Event Info, tee times, after-lock updates, the handicap ask, the payout
   ask, membership renewal.)

## HOLD (Kerry 10/21, Front Desk #2202)

Kerry, verbatim: "Who is handling the Opt-Out schema work? I want to see mockups
for the user flow for it first. Do these meet industry standards + requirements?"
Nothing is built, filed or migrated for this flow until Kerry has seen
design-claude's mockups (variants A and B in #2202) and ruled. The results-email
rule (v2.577.4) is separate and not held.

## Compliance notes (not legal advice; Kerry may want counsel)

**CAN-SPAM's single-page rule: Variant A is at risk.** The recipient may not be
required to do more than reply by email or visit ONE web page. Variant A asks
for choose (page 1), then confirm (page 2), and sometimes "Stop everything?"
(a third press). That makes two or three steps before the opt-out takes effect,
which reads as more than one page. Variant B meets the rule:
- one page with the category pre-ticked;
- "Unsubscribe from all" works in one press;
- the "catch yourself" step comes AFTER the press, as a done state with a
  prominent Undo.

Recommendation: B. Kerry's second step becomes the Undo, not a gate in front
of the opt-out. A scanner still cannot opt anyone out, because GETs never
write and only the button press (a POST) does.

**One-click headers (RFC 8058), added to the plan.**
- Every invitation, reminder and results email carries:
  - `List-Unsubscribe: <https://.../unsubscribe/<signed token>>, <mailto:...>`
  - `List-Unsubscribe-Post: List-Unsubscribe=One-Click`
- The Tracker answers a POST to that URL with body `List-Unsubscribe=One-Click`
  by writing the opt-out for that email's category at once, with
  source='one_click'. That source value needs adding to 0018's CHECK.
  - Mail providers send this POST when the person presses Gmail's or Apple
    Mail's Unsubscribe.
  - Scanners use GET. The GET shows the page and writes nothing.
- Gmail and Yahoo require one-click for bulk senders (5,000+ a day). We are
  far below that, so this is best practice rather than a requirement. It also
  keeps our mail out of spam.
- **To verify before building:** Microsoft Graph sendMail may accept only
  custom headers that begin with `x-` (internetMessageHeaders). If so, the
  Tracker's Graph sends cannot carry List-Unsubscribe. We would then need
  another send path for these emails, such as Brevo transactional SMTP or
  SMTP AUTH. That is a decision for Kerry.

**Brevo side (Insider).** Brevo adds its own unsubscribe link and the one-click
List-Unsubscribe headers to campaign mail. Confirm it from the raw headers of
the next Insider in a staff inbox before relying on it. A Brevo unsubscribe
must come back into the Tracker as source='brevo', and ours must go out to
Brevo. That sync writes to an outside system, so it needs Kerry's OK.

**Also required in every marketing email:**
- a physical postal address (app setting `tgf_mailing_address`, still empty
  for the tee-times email);
- an accurate From and subject;
- the link keeps working for at least 30 days after the send;
- an unsubscribed address is never sold or shared.
