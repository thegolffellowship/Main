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

**RULED, Kerry 2026-10-14 (#1778), standing rule for now:** the results email
goes at **6:00 AM the next morning**. Kerry: "Actually maybe the email recap is
best at 6:00am the next morning. Not sure" — asked "Should 6:00 AM the next
morning be the standing rule for now?" — "Yes". This supersedes the 30-minute
timing below. How it runs: the 9 PM closeout writes the recap, dry-runs
`scoring-results-email:plan|<ids>|<recap>` (0 held) and schedules
`scoring-results-email:schedule-next|<ids>|<recap>|1778`; job
`results_email_auto` sends at 6:00 AM if every guard still passes. The night
leaves the manager window open overnight (still to build).

Superseded: "I want the recap emails typically sent 30 minutes
after the last score is posted for an event. For this one let's send it at
6:00a." So the deadline (open item 1) is **30 minutes after the last score is
posted**. The 10/13 night (s9.27 + a9.27) is scheduled for 6:00 AM 10/14.
BUILT v2.565.0: `email_parser/results_email.py` (the message, the audience, the
guards, preview, the schedule and job `results_email_auto`); bridge
`scoring-results-email`; guard `test_results_email.py`. Not built yet: the
automatic schedule at last score + 30 (today a night is scheduled by bridge on
Kerry's word) and the manager window, which a 30-minute deadline squeezes (see
open items).

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
1. ~~The deadline~~ RULED 10/14 (#1778): 6:00 AM the next morning (first ruled
   30 minutes after the last score, #1776, then changed). The note below is kept
   for the record. That left
   the recap story itself: today it is written at the 9 PM closeout, after the
   last score + 30. Either the story is written the moment the cards are final
   (the email waits for it), or the 30-minute email goes with the personal part
   and the story follows in the next one. And a 30-minute window is short for a
   manager to add photos — does the manager window go away, or move to a
   follow-up?
2. Email only, or email + text for the manager's prompt?
3. Photos in the member email, or on the event's results page only?
4. Should the manager also be able to add a short note ("great night, ask
   Pat about the 16th") that the recap can quote?
