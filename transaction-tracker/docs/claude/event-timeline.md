# Event Timeline: lock, pairings, counts, sends (WORKING SPEC, not ratified)

Started 2026-10-16/17 with Kerry, one step at a time ("We need to run thru the
full timeline one at a time so I can sign off on it"). Each section says
whether Kerry has agreed (RULED) or it is a PROPOSAL. Rule 3b: nothing here
ships until Kerry ratifies the build.

Sources: Error Handling & Edge Cases Spec v1.2 §6-§9 (OneDrive
`7_Web & App Development/Phase_1_Specs/`), Pairings Engine Spec v1.4 §4, §12
(Library `tgf-pairings-engine-spec`), mailbox #134, #739, #767.

## 0. Times are relative to the event, not to Tuesday/Saturday

Kerry 10/17: "I think we need to prepare for non-Tuesday/Saturday events. So
it's more of a days in advance of the event that get the
invitations/reminders/last calls and all the other stuff."
Every step below is stated as an offset from the event date (E). Tuesday 9s
are the worked example. The weekend invitation schedule is OPEN (Kerry wants
to talk it through again).

## 1. Lock (Error Handling Spec §7, ratified Feb 2026)

- Lock: 9-hole E-1 at 5 PM; 18-hole E-3 at 5 PM; custom per event.
- At lock, field ÷ 4: remainder 0 = LOCKED + CLOSED (waitlist only);
  remainder 1-3 = LOCKED + OPEN for those seats only (max 3), open until the
  first tee. Never start a new foursome after lock.
- Withdrawal after lock reopens that seat.

RULED (Kerry 10/17) at lock:
- Remainder 1-3: a push/message that X spots remain.
- Remainder 0: a message that the event is full, with the roster; waitlist.

## 2. The sequence (Tuesday 9 example)

| When | What | Status |
|---|---|---|
| E-1 5:00 PM | Lock. Pairings build. Manager review prompt. Course gets the tee-time count; open times released; more times requested if over | RULED "Yes on all" + release/request added by Kerry |
| E-1 5-7 PM | Manager review window; approval not required | RULED "Agreed" |
| E-1 7:00 PM | Preliminary tee sheet to players, NO personal link | RULED (Kerry: "I don't think personal link would go then") |
| E 7:00 AM | Personal Event Info email to every player (the full breakdown sent 10/13), with the personal link | RULED |
| E 12:00 PM | Print pack to course contact, TGF CC'd (TGF only if no contact). Revised Event Info ONLY to players whose details changed since 7 AM | RULED |
| E noon → first tee | Late adds into open seats (see §3) | RULED |

Kerry 10/17 on single changes: "A group adding a fourth is not reason to send
out a whole new set of updates. There would just be an email sent to that
player and the players group letting them know they now have a 4th. In
future these are push notifications as well as emails."

Late add (RULED): the player gets their own info email right after signing
up; the group is told they have a 4th and who; the course is told there is
another player on that time, with that group's scorecard and cart sign only
(not the whole print pack). The scorer is NOT chosen in advance (decided at
the course).

## 3. Adds and withdrawals after lock (PROPOSAL, Kerry: "the messiest and most complex of all")

Kerry 10/17: "if there were open seats after a foursome lock and then
withdraws happen reducing players to a multiple of 4, then there would be
another lock and a regeneration of pairings ... Maybe not a full regeneration
of pairings but perhaps just a redistribution as needed. Definitely needs
manager notification ... Manager may have to be the one that gets a phone
call for someone canceling and has to manually remove them himself."

Principles proposed:
1. After lock, never regenerate; REDISTRIBUTE with the fewest moves.
   Never split a partner request, a guest from their host, or a locked group.
2. Every change notifies the manager (what happened, what moved).
3. Who may move people depends on the clock:
   - lock → 7 PM: automatic, nobody told yet.
   - 7 PM → 7 AM: automatic, manager notified; sheet was "preliminary".
   - 7 AM → noon: system PROPOSES, manager approves with one tap.
   - after noon: manual only (Pairings §12); system notifies.
4. Manager phone-call cancellation: "Remove player" on the phone runs the
   same flow as an online withdrawal (credit per policy).

Scenarios (N = players, G = tee times held):

| # | Event | Result |
|---|---|---|
| A1 | Add, open seat exists | Into the open seat (rule-best group if several). Player info email; group told; course gets that group's card + cart sign; manager FYI. Field now ÷4 → close + waitlist |
| A2 | Add when full | Waitlist (from Jan 1 the shop blocks it). Today GoDaddy can sell it: manager decides: request a time from the course + redistribute, or credit/refund |
| W1 | Withdraw, group keeps 3+ | Seat reopens; group told; course gets that group's card; manager FYI |
| W2 | Withdraw leaves a twosome | Move one player from a foursome into it (fewest rule breaks) → two threesomes |
| W3 | Withdrawals leave a spare time (4G-N ≥ 4, e.g. 13→12 in 4,3,3,3) | "Re-lock": dissolve one group into the threesomes, release that time to the course, close registration if N÷4 |
| W4 | Host withdraws, guest stays | Guest asked keep or cancel (Error Handling §8.2) |
| W5 | Withdraw at the course / no-show | Scorer + manager flow (Pairings §12) |
| S1 | Transfer of a spot to someone else | Same seat, no movement; group + course told |

OPEN: W3 timing (compress vs keep groups and reopen seats), course deadlines.

## 4. Counts to the course before lock (PROPOSAL, OPEN)

Kerry 10/17: Sunday NOON count "for sure", "possibly something that Friday",
deadlines may depend on the course's request; "we'll release x times back to
course too if we're WAY short"; request more if we may exceed. Rules to be
written per course (Course Connection).

## 5. Payments era (Kerry correction 10/17)

Kerry: "I don't think we can have a step for stripe memberships without
stripe event payments. I don't see how we can do that in December without
events too." So there is no Dec 1 memberships-only step; Stripe memberships
and Stripe event payments start together. Date OPEN (CoS/CFO; #739 said Dec 1
memberships, Jan 1 events).

## 6. Other items Kerry raised 10/17 (queued, OPEN)

- Balance reminders: likely none needed now that invitations go straight to
  payment (GG RSVPs had no pay step). Future invitations: push, email or text
  (Twilio).
- Cancellation windows: TGF standard 24h (9) / 72h (18), plus per-course
  variables, possibly set in Course Connection.
- Course payments: today a CCA form PDF with card details per course; to be
  automated so nobody has to remember it.
- Sign-ups earlier: the weekly field signs up late; needs ideas.
- Weekend invitation schedule: talk through again.
- First run: 10/20 or 10/27 depends on what Kerry finishes this weekend.
