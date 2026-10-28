# The event closeout, start to finish (as run Tue 10/20/2026)

Written Wed 10/21 by Event Ops (CGO) for the working session Kerry asked for
("Closeout Routine - Let's go over it in its entirety", #2067 item 2). Plain
words. Times are Central. Events: **3301 s9.28 TPC Canyons** (San Antonio, 23
players, first tee 3:40 PM) and **3319 a9.28 Avery Ranch** (Austin, 7 players,
first tee 4:03 PM). The screenshot sequence (item 6) is in
`docs/claude/screenshots/closeout-chain-2026-10-20/index.md`.

## 1. The short version

- **Two kinds of machinery run the night.**
  - **The Tracker itself.** Jobs inside the app that run on a timer, around the clock: every minute, every 15 minutes, or at a fixed time. Nobody has to be awake. These do the real work: they lock cards, record the money and send the 6 AM email.
  - **Agent routines.** A Claude session (Event Ops) is woken on a clock: 7:00 PM check-in, 9:08 PM backstop, 5:30 AM catch-up. It reads what the Tracker did, checks it, writes the recap and posts on the mailbox. It does not record money and it does not send member email, except scheduling the 6 AM email once the plan is clean.
- **Kerry (or the manager) presses a few buttons by hand:**
  - approve the pairings;
  - confirm or reject closest-to-the-pin takeovers;
  - pay the Venmo payouts;
  - say "Deploy" when code has to go live.
- **Tuesday's result:**
  - Avery Ranch was closed out by 7:15 PM.
  - TPC was closed out by 8:00 PM. It waited 37 minutes on the two CTP confirmations.
  - The recap and the staff drafts went out at 8:40 PM.
  - The results email went to 204 people at 6:00 AM, with none failed.
  - Kerry paid every prize overnight.

## 2. Words used below

- **Card goes final.** A player's scorecard locks 15 minutes after their group's last score is entered. No signature is needed (Kerry #1761). A manager can Unlock it, which gives another 15 minutes.
- **Card parity.** The Tracker checks that the scoring engine and each saved scorecard agree, stroke for stroke. Any difference is a "SCORING HOLD": money, points and the results email all stop until it's fixed.
- **Auto payouts job.** It runs every minute. Once the whole field has scores, it shows the GAMES-tab money on the board as a preview, marked not final. Once every card is final, it **records** the payout rows as PENDING. It never pays. It holds instead of recording when:
  - card parity fails;
  - a manual payout row exists;
  - a CTP takeover is unconfirmed;
  - Kerry or Event Ops has placed a hold.

  From 10/20 it is the **only writer** of payouts (CoS #1797).
- **Verifier.** Event Ops checks the recorded rows against the preview row for row, then against the GAMES tab, the flights, the pairings and the board. It never changes a payout row; a mismatch is reported to Kerry.
- **Check-in.** A one-time Routine that wakes the Event Ops session at a set time to look at an event. If the event isn't ready, it re-arms itself 15 minutes later. Tuesday's check-ins:
  - 7:00 PM, the start of Kerry's interim 20-minute rule (#2067);
  - 7:15, 7:38 and 7:56 PM re-checks.
- **The 9:08 PM run.** The standing Tuesday/Saturday closeout Routine. It goes through the whole closeout skill for every event that day. With the check-ins in place it is the **backstop**: if a check-in failed or the session was down, 9:08 picks it up. Tuesday it found nothing left to do.
- **The 5:30 AM catch-up.** The standing Wednesday/Sunday Routine. It finishes anything the night held, for example a recap that couldn't be pushed. If the 6 AM email isn't scheduled by then, it schedules it.
- **No-push window.** From first tee until the closeout digest is posted, nobody deploys, because a deploy restarts the app and drops scores in flight. The Front Desk posts WINDOW OPEN and WINDOW CLOSED by hand.

## 3. Step by step: last score → 6:00 AM results email

| # | Step | Who / what triggers it | Tue 10/20 |
|---|---|---|---|
| 1 | Last score entered on the phone | A player | Avery about 6:37 PM, TPC about 7:04 PM |
| 2 | Each card goes final 15 min after its group's last score | **Tracker**, part of the auto payouts job (every minute) | Avery all final 6:52 PM; TPC all final 7:19 PM |
| 3 | Card parity check | **Tracker**, each publish and before recording | ok 8/8 Avery, 23/23 TPC |
| 4 | Entered cards publish into scoring rounds (the record) | **Tracker** (auto payouts / publish) | Avery 6:38 PM; TPC 7:04 PM |
| 5 | Money recorded as PENDING payout rows | **Tracker**, auto payouts job (every minute) | Avery 6:52 PM, 7 rows $160. TPC **held** until 7:56 PM on 2 CTP takeovers, then 17 rows $462 |
| 6 | CTP takeover confirm / reject | **Kerry or manager**, Live Scoring page (button) | Hole 4 Baker confirmed; hole 8 Wade's takeover not confirmed (Pat Youngs keeps it), ~7:55 PM |
| 7 | Payout handle ask to winners with no Venmo | **Tracker**, payout ask job (every 15 min, 7 AM–9 PM, dial on) | Adam Wilson ($99.50, no Venmo on file): asked 8:02 PM, 6 min after TPC recorded and 4 min after verification |
| 8 | Verify: recorded = preview, cross-check GAMES / FLIGHTS / pairings / board | **Event Ops**, 7 PM check-in and re-checks | Avery 7:15 PM; TPC 7:58 PM |
| 9 | Flights settled (frozen selection, amounts recomputed) | **Event Ops** (bridge, dry run then apply) | both, by 7:41 PM |
| 10 | Pairing history written ("who played together", feeds future pairings) | **Event Ops** (bridge) | TPC 33 pairs, by 7:41 PM. Avery 9 pairs at ~8:30 PM, after Kerry's Reed ruling |
| 11 | Handicap rounds posted; recap emailed to Kerry + Robert | **Event Ops** (bridge; the email is automatic with the import) | Avery 7 rounds (Reed excluded); TPC 23 rounds |
| 12 | Points rebuilt (fall races, October) | **Tracker** on publish; Event Ops dry run confirms no changes pending | no changes pending |
| 13 | Recap written, both chapters in one file, plus Word files | **Event Ops** | drafted 7:45–8:00 PM; CTP lines added 7:58 PM |
| 14 | Closeout digest on the mailbox (TO front-desk, CC Kerry) | **Event Ops** | #2156 at 8:00 PM |
| 15 | WINDOW CLOSED | **Front Desk** (by hand, on reading the digest) | #2157 at 8:08 PM |
| 16 | Recap pushed to main and deployed | **Event Ops + Kerry's "Deploy"** | blocked 8:20 PM (permission); Kerry said Deploy; live ~8:35 PM |
| 17 | Staff recap drafts: SA to Kerry; Austin to Robert, CC Kerry | **Event Ops** (bridge, dry run then apply) | sent ~8:40 PM |
| 18 | Results email: plan (holds nothing?), spot-check, schedule 6:00 AM | **Event Ops** schedules; **Tracker** sends | scheduled ~8:45 PM (202, then 204 after Lou + Chris restored) |
| 19 | 9:08 PM backstop | **Agent routine** | fired 9:10, nothing to do |
| 20 | Kerry pays the Venmo payouts | **Kerry** | overnight; Venmo receipts flip rows to PAID within minutes |
| 21 | 5:30 AM catch-up | **Agent routine** | 5:38 AM, clean |
| 22 | Results email sends (one per person, once) | **Tracker**, results_email_auto (every minute, at the scheduled time) | 6:00 AM, 204 sent, 0 failed |

## 4. Every message the chain sends (who gets what, and when)

**Before the event.**
- **Pairings ready (Mon, about 5:05–5:20 PM).**
  - To the chapter manager: Kerry for SA, robert@ for Austin.
  - Trigger: Tracker job every 15 minutes from :05, after the 5:00 PM generator saves the sheet. Once per sheet; a changed sheet re-prompts at most hourly.
- **Player pairing email ("your start", with the Keep score link).** To each player.
  - Trigger: the manager presses **Approve**, or at **7:00 PM the day before** if nobody approved (v2.571.25).
  - Tuesday: Robert approved Avery at 5:18 PM Mon; Kerry approved TPC at 7:57 PM Mon.
- **7:00 PM tee-times email, three versions: player, course contact, manager.**
  - Trigger: Tracker job at 7 PM the day before. Dial on, wording approved by Kerry (#2107).
- **Handicap ask.** To a new registrant with no handicap.
  - Trigger: Tracker, at order time plus every 15 minutes; one reminder 2 days before.
  - Tuesday: Adam Wilson. He said the morning ask never arrived; Kerry then found his index himself (#2139, #2140).
- **Print pack to staff (6:05 AM, hourly to 9:05 on event day).** To Kerry; Robert gets Austin's.
  - Trigger: Tracker job. Sends once per change.
- **Course Files (noon on event day).** To the course contact, CC Kerry (and Robert for Austin).
  - Trigger: currently an **agent Routine at noon** with a gap and QR check; the button exists for by-hand sends.
  - Tuesday: Avery went to Skyler at 12:04 PM. TPC was held on Adam Wilson's missing handicap; Kerry sent the corrected TPC scorecards to Justin himself (#2138, #2142).
- **After-lock change notices (new v2.577.0, from Sat 10/24).** To the moved player and their old and new groups.
  - The course gets only the changed sheets; the manager is CC'd (#2169).

**During and after.**
- **Payout handle ask.** To a winner with no Venmo or other handle on file. Tracker, within 15 minutes of the money recording (7 AM–9 PM).
- **Handicap recap to staff.** Kerry and Robert, automatic with the handicap import (step 11).
- **Staff recap drafts.** Kerry (SA); Robert with Kerry CC'd (Austin). Event Ops, after the recap is on main (step 17).
- **The results email (6:00 AM next morning).**
  - Who: every player, every chapter member, and anyone who played the chapter in the last 12 months.
  - Who's left out: invitation opt-outs and non-members.
  - What's in it:
    - players get their card, winnings, handicap and points;
    - everyone else gets their standing;
    - everyone gets the recap story and Up Next.
  - Trigger: Tracker job, scheduled by Event Ops (step 18).

**Managers on the night.**
- Nothing automatic yet: the manager hears about CTP takeovers only by looking at Live Scoring or reading Event Ops' mailbox post. See bottleneck B2.

## 5. What actually happened Tue 10/20 (from the mailbox)

| Time | What happened | Ref |
|---|---|---|
| 3:36 PM | WINDOW OPEN | #2151 |
| 3:40 / 4:03 PM | First tees, TPC / Avery | |
| ~6:37 PM | Avery's last score | |
| 6:52 PM | Avery all final; money recorded (7 rows, $160) | |
| 7:05 PM | 7:00 check-in: TPC has 2 CTP takeovers waiting for a manager; asked Kerry | #2152 |
| 7:15 PM | Avery verified. One question: Paul Reed (credited "Back pain") had an all-par placeholder card | #2153 |
| ~7:04 PM | TPC's last score | |
| 7:19 PM | TPC all 23 cards final; money HELD on the CTPs | #2154 |
| 7:41 PM | Still held; other steps for both events done | #2155 |
| ~7:55 PM | Kerry decided both CTPs on Live Scoring | |
| 7:56 PM | TPC money recorded (17 rows, $462), verified = preview and = GAMES total | |
| 8:00 PM | Closeout digest posted | #2156 |
| 8:02 PM | Payout ask to Adam Wilson ($99.50, no Venmo on file) | payout_ask state |
| 8:08 PM | WINDOW CLOSED | #2157 |
| 8:10 PM | Another lane deployed v2.575.16 (live scoring drops an off-sheet player; Reed's live card removed) | #2158 |
| 8:20 PM | Recap push to main refused by this session's permission check; asked Kerry | #2159 |
| ~8:28 PM | Kerry: "Deploy" and "Drop Paul's par card" | #2160 |
| ~8:35 PM | Recap live; Reed's card dropped; Avery pairing history written | |
| ~8:40 PM | Staff drafts sent | |
| ~8:45 PM | Results email planned (nothing held) and scheduled for 6:00 AM | #2164 |
| ~8:50 PM–9:35 PM | Kerry asked about Lou Schneider's opt-out; restore built + deployed (v2.575.17); Lou and Chris Best back on | #2165, #2166 |
| 9:10 PM | 9:08 backstop: nothing to do | |
| Overnight | Kerry paid every prize (receipts matched) | #2174 |
| 5:38 AM | Catch-up: clean | #2175 |
| 6:00 AM | Results email: 204 sent, 0 failed | |

**Where the time went:**
- Avery was done 23 minutes after its last card went final.
- TPC: the cards were final at 7:19, but the money waited 37 minutes on a human confirming two CTP takeovers.
- The recap waited 28 minutes, from the 8:00 digest to Kerry's Deploy, on the no-push window and the deploy permission.

Everything after that was minutes.

## 6. Bottlenecks, and what could become event-driven inside the Tracker

**B1. Closeout starts on a clock (7:00 PM check-in), not on the event.**
- The Tracker already knows the moment the last card goes final. Kerry's rule is that closeout starts 20 minutes after the last score (#2074).
- **Proposal (Tracker Build spec #2057, Part 2):** when every card is final, plus 5 minutes (dial), the Tracker runs the final check, records, and marks results OFFICIAL. It then raises one "closeout ready" event that wakes Event Ops to verify and write the recap.
- Keep the 9:08 PM run as the backstop.

**B2. CTP takeovers wait on someone looking.**
- An unconfirmed takeover holds the whole event's money, and the only signal today is the board and the mailbox.
- **Proposal:** the moment a takeover is claimed, email (and later push) the chapter manager with one-tap Confirm / Reject links (signed, like the RSVP links). The money then records the minute they tap.
- A second option for Kerry: auto-confirm a takeover once its hole's group has finished and nobody disputes it within N minutes.

**B3. The no-push window and the deploy permission gate the recap.**
- The recap is a docs file, but publishing it needs a push to main, which restarts the app. That needs WINDOW CLOSED (posted by hand) and, in this session, Kerry's "Deploy".
- **Proposal:** store the recap as a Library document (`library_put`, which writes to the database, so no deploy) and point the staff-draft and results-email builders at the Library copy. The recap stops needing a deploy at all.
- Also: let the Tracker post WINDOW CLOSED itself when the closeout digest posts, or drop the window to "first tee → all cards final".

**B4. Pairing history and handicaps are agent steps.**
- Both are deterministic once the cards are final.
- **Proposal:** run them in the Tracker right after recording, keeping the dry-run report for Event Ops to read. Handicaps keep the "absurd move" check as a hold rather than a person reading it.

**B5. Withdrawn players with placeholder cards (Paul Reed).**
- Fixed on the live side by v2.575.16: a player taken off the sheet leaves live scoring.
- **Still open:** a credited player's already-published round should be flagged by the final check, not found by a person.

**B6. The results-email audience follows the invitation opt-out.**
- A player who taps "Remove me" loses his own results (Lou).
- **Ruling needed:** should a player who played always get their own results, even if opted out of invitations?

**B7. Course Files at noon is an agent routine.**
- It should be a Tracker job with the same QR and gap checks, the same way the 6:05 AM staff pack already is.
- A held send (TPC's missing handicap) should email the manager a one-tap "send as is / wait" choice.

**B8. Payout handle ask timing (H3, #2055).**
- It can reach a winner before verification. Kerry accepted that for now (#2067). Tuesday it went at 8:02 PM, after verification, only because the CTP hold delayed the recording.
- If B1 lands (OFFICIAL at +20), tie the ask to OFFICIAL instead of to recording.

## 7. Questions for the working session (one at a time)

1. B1: build the event-driven closeout start (+20 min), keeping the 9:08 PM backstop?
2. B2: manager Confirm/Reject links by email for CTP takeovers? And should an undisputed takeover auto-confirm?
3. B3: move recaps into the Library so they never need a deploy?
4. B6: does a player always get their own results email, even if they opted out of invitations?
5. Should results go OFFICIAL at +20 but prizes be paid only the next morning (#2057 concern 2)? Tuesday Kerry paid the same night.
