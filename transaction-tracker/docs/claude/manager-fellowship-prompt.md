# Manager after-event prompt — SPEC DRAFT (week of 2026-10-13)

Kerry 2026-10-13: "I really don't want to be held hostage by manual information
entry like where everyone went afterward. That would be a nice ad in the future
for managers to add in say if they got a notification directly on their app
about hey enter any info about after and any pics. I'm just not sure how to do
it conveniently." Then: "Yes, start next Tuesday, then build the manager prompt.
Need to spec that this week."

STATUS: draft for Kerry's review. Nothing built. Member-facing output (the recap
and the results email) only changes after his OK (rule 3b).

## The job
After an event, the chapter manager tells the Tracker where the group went, how
many came, and adds any photos, from the phone, in under a minute, without
logging in. Anything that arrives before the recap / results email is used;
nothing blocks the send (event-recaps.md lesson 69).

## Trigger
- When: 30 minutes after the event's last card goes final (auto_payouts already
  knows the moment), or 9:00 PM local if that is earlier than the cards.
- Who: the chapter manager on the event (the `pairings_approval` recipient);
  the TGF-wide events go to Kerry.
- Once per event (state in an app setting, like `pairings_approval`).

## The message (email first; SMS link later)
Subject: "s9.27 The Quarry: how was fellowship?"
Body, three things, each optional:
1. Where did you go? Pre-filled with the event's `fellowship_spot`.
2. How many came? Pre-filled with the FELLOWSHIP YES count from the orders.
3. Photos.
Two ways to answer, whichever is easier:
- REPLY to the email: free text plus attached photos. The Tracker already reads
  the admin@ inbox through Graph; a reply carrying the event's token in the
  subject is parsed into spot + count, and photos are saved.
- TAP the button: a signed one-page form (no login, like the score-entry links):
  spot (pre-filled), count (stepper), photo picker, Save.

## Where it lands
- New table `event_fellowship` (migration, db-claude PASS first): event_id,
  spot, headcount, reported_by customer_id, reported_at, source (reply|form).
  Photos as files beside the DB (the player_photos pattern), rows in
  `event_fellowship_photos`.
- The recap's FELLOWSHIP line and the results email read it first, then the
  planned spot and the YES count, then drop the line.

## Open for Kerry
1. Email only, or email + text?
2. Photos in the member email, or on the event's results page only?
3. Should the manager also be able to add a short note ("great night, ask
   Pat about the 16th") that the recap can quote?
