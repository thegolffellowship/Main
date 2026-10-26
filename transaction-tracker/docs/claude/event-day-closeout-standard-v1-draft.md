# TGF Event-Day Closeout Standard v1 (DRAFT for Kerry)

Owner: Event Ops (CGO), drafted Mon 10/26/2026 with the Librarian (CoS #2307 item 8). Status: **DRAFT, not ratified.** It travels with the Lane Session Close-out and Handoff Standard (Library 26), which covers a different thing: closing a Claude session, not an event night.

Sources:
- `events.md`;
- the event-closeout skill (`.claude/skills/event-closeout/SKILL.md`);
- `docs/claude/closeout-process-2026-10-20.md` (the 10/20 run, step by step);
- CoS #1797 (one payout writer), #1778 (6 AM results), #2307 item 1 (the no-push window);
- Kerry #1761 (card final 15 min after the last score, no signature).

Wording in quotes is Kerry's own.

## 1. Purpose

From the last score of an event night to the members' results email the next morning, every step runs the same way every time. Each step has:
- one owner;
- one record of what happened;
- nothing that waits on Kerry unless he chooses to step in.

## 2. When closeout starts (RULED, Kerry, Monday 10/26, CoS #2329 item 5)

Kerry: *"I thought I changed it to 15 minutes after last score."*
- **Closeout starts 15 minutes after the last score of the event.** That's the moment the last card goes final.
- Closeout means: money recorded and verified, flights, pairings, handicaps, points, recap.
- Until the Tracker starts it by itself (build queue item 6, #2331), Event Ops' check-in is the trigger, with the 9:08 PM run as the backstop.
- **The no-push window still closes one hour after the last score** (§2a), not when closeout starts.

## 2a. The no-push window (RULED, Kerry, CoS #2307 item 1)

- **From one hour before the first tee time or shotgun of ANY event that day, until one hour after the last score of ANY event that day:** no lane pushes or deploys to main.
  - Example, Tue 10/27: Teravista's first tee is 4:08 PM, so the window opens at **3:08 PM**. It closes one hour after the last score of Silverhorn or Teravista, whichever is later.
- **WINDOW OPEN:** posted on the mailbox (topic front-desk) by the **Front Desk**, at the opening time.
- **WINDOW CLOSED:** posted by the **Front Desk** once BOTH are true:
  - one hour has passed since the last score;
  - Event Ops' closeout digest is posted.
  - (Proposal for later: the Tracker posts both itself, from the event times and the last score.)
- **Inside the window:** data changes that run the night are allowed (seating a late add, CTP rulings, unlocking a card, recording payouts). Code, migrations and deploys are not.
- **An emergency fix inside the window** needs CA's OK first (CA #829).

## 3. The steps, owner and trigger

| # | Step | Owner | Trigger |
|---|---|---|---|
| 1 | A card goes **final 15 minutes after its group's last score**. No signature needed. A manager may Unlock it, which reopens it for 15 minutes. | Tracker | auto_payouts job, every minute |
| 2 | **Card parity**: the engine and every saved card agree stroke for stroke. Any difference is a SCORING HOLD: money, points and the results email all stop. | Tracker | every publish |
| 3 | **Entered cards publish** into the scoring record. | Tracker | on publish |
| 4 | **Money recorded** as PENDING payout rows once every card is final. **One writer** (CoS #1797). It holds on: card parity, a manual payout row, an unconfirmed CTP takeover, or a hold by Event Ops or Kerry. Each hold raises one COO item. | Tracker | auto_payouts job, every minute |
| 5 | **CTP takeover confirm or reject** (a claim that unseats another group's player). | Kerry or the manager, on Live Scoring | as it happens |
| 6 | **Verify**: recorded rows = the preview, row for row and in total; cross-check against GAMES, FLIGHTS, pairings and the board. Event Ops **never records, edits or deletes a payout row**; a mismatch is reported to Kerry with the fix. | Event Ops | 15 minutes after the event's last score (§2); today a clock check-in, the Tracker later |
| 7 | **Flights settled.** | Event Ops | same |
| 8 | **Pairing history** written (feeds future pairings). | Event Ops | same |
| 9 | **Handicap rounds posted**; the handicap recap goes to the managers. No per-player handicap card emails (#1799-4). | Event Ops (preview, then apply) | same |
| 10 | **Points** rebuilt and checked: no HELD warnings, nothing pending. | Tracker / Event Ops check | same |
| 11 | **Pace** (once 0037 is live): group pace and slowest holes for the manager report. | Tracker | nightly rebuild |
| 12 | **Recap** in the house style, both chapters in one file, plus Word files. | Event Ops | after verification |
| 13 | **Closeout digest** on the mailbox (TO: front-desk, CC kerry). It covers, per chapter: done, verified, held, open. | Event Ops | after 6–12 |
| 14 | **WINDOW CLOSED.** | Front Desk | §2a |
| 15 | **Recap published** (pushed to main). | Event Ops, on the deploy rule in force | after 14 |
| 16 | **Staff recap drafts**: SA to Kerry; Austin to Robert, CC Kerry. | Event Ops | after 15 |
| 17 | **Results email** planned (must hold nothing), spot-checked, then **scheduled for 6:00 AM** (Kerry #1778). | Event Ops schedules; the Tracker sends | after 15 |
| 18 | **9:00 PM backstop**: the standing closeout routine re-runs everything; it does nothing if done. | agent routine (Tue/Sat 9:08 PM) | clock |
| 19 | **Prizes paid** by Venmo; receipts mark rows PAID within minutes. | **Kerry** (the Tracker never pays) | when he chooses |
| 20 | **5:30 AM catch-up**: finishes anything held overnight, or schedules the results email if the night couldn't. | agent routine (Wed/Sun) | clock |
| 21 | **Results email sends**: one per person, once; held if any guard fails. | Tracker | results_email_auto, every minute |

## 4. What is NOT touched on closeout night

- **Paying anyone.** Kerry pays.
- **Changing or deleting a recorded payout row.** A mismatch is reported; Kerry keeps the Unlock and override.
- **Recording money for an event on or after 10/20 by hand.** The auto_payouts job is the one writer.
- **Sending any member email other than scheduling the 6 AM results email after a clean plan.** No handicap cards, no ad-hoc notices.
- **Deleting anything.** A withdrawn player's placeholder card is dropped only on Kerry's word (10/20 Reed).
- **Code, migrations, settings changes or deploys inside the window.**
- **Ruling a CTP dispute.** Only Kerry or the manager rules it.

## 5. Records (where each step leaves its trace)

- **Cards:** card-lock and score-save times (se_audit).
- **Payouts:** the payout rows, with the `auto:` prefix. COO items for every hold.
- **Mailbox:**
  - the digest;
  - WINDOW OPEN / CLOSED;
  - Kerry's rulings, verbatim.
- **Results email:** `results_email_schedule` (sent count, failed, held).
- **Proposed (rule 3b):** one `event_closeout_log` record per event with the times of steps 1–21, for the Manager Event Report (spec v0 §1f).

## 6. Proposed improvements (not part of the standard until Kerry rules)

From `closeout-process-2026-10-20.md` §6:
- start the closeout from the event (all cards final + 5 minutes), not a clock check-in;
- Confirm / Reject links by email for CTP takeovers;
- recaps in the Library, so publishing one needs no deploy;
- pairing history and handicaps as Tracker steps;
- CTP claims ordered by when the group played the hole (#2220).

## 7. Questions for Kerry (one at a time)

1. Ratify §2–§4 (including §2a) as the standard?
2. Keep the 9:00 PM backstop and the 5:30 AM catch-up once closeout starts from the event? (Recommend yes.)
3. Should the Tracker post WINDOW OPEN / CLOSED itself, from the event times and the last score?
