# Results email that sends itself, with a manager window — SPEC DRAFT (week of 2026-10-13)

Kerry 2026-10-13: "I really don't want to be held hostage by manual information
entry like where everyone went afterward. That would be a nice ad in the future
for managers to add in say if they got a notification directly on their app
about hey enter any info about after and any pics. I'm just not sure how to do
it conveniently." Then: "Yes, start next Tuesday, then build the manager prompt.
Need to spec that this week."

STATUS: draft for Kerry's review. Nothing built. Member-facing output (the recap
and the results email) only changes after his OK (rule 3b).

Kerry, later the same night: "I'm leaning to trusting you with the recaps and
everything it autosend to everyone. Again there might be an approval step
(within a window) where a manager could add photos or details that could enhance
the message, but there's a deadline. I think there's also a potential future
build for members to submit photos for inclusion and perhaps comments about
anything else like fellowship location and details too."
("Leaning" — this design is for his ruling, not yet ratified.)

## The whole flow
1. Event night, once the closeout's cross-check is clean and payouts are
   recorded: the Tracker builds ONE results email per person (samples sent to
   Kerry 10/13):
   - players get their own night first (card, winnings, handicap, points with
     "See my spot" links), then the recap and Up Next;
   - members who didn't play get their race standing, the recap and Up Next.
   It replaces the separate handicap-card email and the recap send.
2. The chapter manager gets a preview plus the ENHANCE window (below).
3. At the DEADLINE it sends to everyone, with or without the manager's
   additions. The manager can also tap Send now, or Hold (holds it and alerts
   Kerry; nothing else stops it).
4. Guards that HOLD the send automatically and alert Kerry and the manager,
   instead of sending:
   - the closeout cross-check is not clean, or payouts are not recorded;
   - any player's engine net or points differ from the stored card;
   - a blank, a leftover {tag}, or an unlinked name is left in the text;
   - a dollar figure in the recap doesn't match the recorded payouts.
5. Proposed timing (Kerry decides): built by ~9:30 PM; deadline 9:00 AM the
   next morning; Saturday events the same.

## The manager's ENHANCE window
### The job
After an event, the chapter manager tells the Tracker where the group went, how
many came, and adds any photos, from the phone, in under a minute, without
logging in. Anything that arrives before the recap / results email is used;
nothing blocks the send (event-recaps.md lesson 69).

### Trigger
- When: 30 minutes after the event's last card goes final (auto_payouts already
  knows the moment), or 9:00 PM local if that is earlier than the cards.
- Who: the chapter manager on the event (the `pairings_approval` recipient);
  the TGF-wide events go to Kerry.
- Once per event (state in an app setting, like `pairings_approval`).

### The message (email first; SMS link later)
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

### Where it lands
- New table `event_fellowship` (migration, db-claude PASS first): event_id,
  spot, headcount, reported_by customer_id, reported_at, source (reply|form).
  Photos as files beside the DB (the player_photos pattern), rows in
  `event_fellowship_photos`.
- The recap's FELLOWSHIP line and the results email read it first, then the
  planned spot and the YES count, then drop the line.

## Later: members add photos and notes
- The results email carries "Got a photo from Tuesday? Add it": a signed,
  no-login link per member per event, the same pattern as the score-entry and
  RSVP links.
- A member can add photos and a short note (where everyone went, a moment from
  the round).
- Everything submitted goes to the manager's queue first. Nothing a member
  submits reaches another member until a manager approves it.
- Approved photos can go on the event's results page, the next recap and the
  TGF Insider.

## Open for Kerry
1. The deadline: 9:00 AM next morning, or another time?
2. Email only, or email + text for the manager's prompt?
3. Photos in the member email, or on the event's results page only?
4. Should the manager also be able to add a short note ("great night, ask
   Pat about the 16th") that the recap can quote?
