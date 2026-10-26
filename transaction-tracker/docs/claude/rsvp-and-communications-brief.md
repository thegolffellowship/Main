# RSVPs and event communications — what is built, for ratification (2026-10-26)

**For:** platform-claude (Chief of Staff), cc Front Desk and Kerry.
**From:** Tracker Build 4, written Mon 10/26 at about 1:00 PM CDT. Refreshed by Tracker Build 5 at 1:25 PM: v2.583.0 is live, and Kerry's #2313 ruling (payment reminders stop at the lock) is folded in.

Kerry, 10/26: "Communicate with Chief of Staff. We need to ratify all of the event timeline and communications items. It needs to know specifically our details for RSVPs."

This is the built state of the Tracker as of v2.584.0 (live, main a3e9a61), stated as facts with their code and dials. It feeds the ratification pass on `docs/claude/event-timeline.md` (a working spec, not ratified) and CoS #2307 / #2308. Section 6 is the list of rulings Kerry still owes.

Times are Central. E = event day. "Lock" = the 5:00 PM pairings run, which is E-1 for a dialled Tuesday nine and two days ahead for a dialled Saturday (`database.pairings_auto_weekdays`).

## 1. Where an RSVP comes from (three kinds, one roster)

| Kind | How it's made | Stored as | Status |
|---|---|---|---|
| Tracker invitation answer | Member taps I'm in / Can't make it in the Tracker invitation email (`/rsvp/<signed token>`) | `rsvps` row, `email_uid = tracker:<event_id>:<customer_id>`, response PLAYING / NOT PLAYING | LIVE since 10/13 |
| Golf Genius RSVP | GG RSVP email parsed (`rsvp_parser.py`) | `rsvps` row | Still counted until app setting `gg_rsvps_off`=1 (Kerry 10/8 "Still using actively") |
| Shop $0 RSVP-only item | A $0 "RSVP only" product in the GoDaddy store | `items` row, `transaction_status='rsvp_only'` | Legacy, rare |

- **One roster:** `_event_roster_rows` (v2.410.0) is the only answer to "who is on this event". It holds paid registrations plus every PLAYING RSVP with no order. Rows carry `rsvp_only`.
- **The Events page:** shows RSVP-only players with the amber **Remind** tag.
- **Pairings:** they are DEALT INTO GROUPS like paid players (v2.571.1, Kerry 10/17: "if players click I'm in ... add them as RSVPs, even if they bounce when the payment page comes up").
- **Overrides:** a manager can mark an RSVP not playing on the Events page (`rsvp_email_overrides`). The roster honours it.

## 2. The invitation tap rules (LIVE)

- **I'm in:** records PLAYING and goes straight to the event's store registration page. A tap is an RSVP even if the person never pays (v2.571.1).
- **Can't make it:** goes to "Thanks for letting us know". From there the member has:
  - **Changed my mind, I'm in;**
  - an optional one-tap reason (Schedule / Weather / Course or price / Injury / Other), stored in `event_decline_reasons`;
  - a small link, "Remove me from ALL event invitations", confirmed on its own page (v2.579.3).
- **A bare link open records nothing.** The page records the answer itself (a POST), so a mail scanner that only fetches the link answers nothing.
- **Mail-scanner guard (v2.580.1):**
  - A tap within 120 s of the email's send, or a burst 30 s apart, is ignored.
  - Someone caught as a scanner twice (dial `invite_scanner_known_after`), or any request with no browser fingerprint (user agent, Accept-Language), gets "One more tap and you're in" with a button. Scanners open links; they don't tap buttons.
  - Every tap is logged with its fingerprint.
  - Dial `invite_scanner_guard`.
- **Removal tools (Kerry-OK post required):** `unplay` takes back I'm in answers a person did not give (upcoming events only, never a registered event). `restore` undoes answers a scanner gave.
- **Staff preview links:** record nothing.

## 3. The member email timeline as built

| When (Tuesday nine example) | Email | Code / dial | Status |
|---|---|---|---|
| Wed 7:00 AM (E-6) | Invitation (I'm in / Can't make it) | `invitations.py`, job `event_invite_auto` (7–9 AM, every 15 min resend sweep), stamp `event_invite_approved` | LIVE |
| Fri + Sun 7:00 AM | Reminder (to people with no answer) | same | LIVE |
| Mon 7:00 AM (E-1) | Last call: "Sign up by 5:00 PM tonight: that's when Kerry builds the groups" | same | LIVE |
| Weekend events | Fri two weeks out, next Fri, Tue, Wed last call | same | LIVE; Kerry wants to talk the weekend schedule through again (timeline §6) |
| Every other day 6:00 AM | Payment reminder to every RSVP-only person on upcoming events | `payment_reminder.py`, job `send_auto_payment_reminders`, exclusions `payment_reminder_exclude_events` | LIVE v2.581.0 (one email for Remind, Remind All, the job and the composer; once per person per event per day). Kerry 10/26 (#2313): stops at the event's 5:00 PM lock. The stop-at-lock guard is NOT built yet: as built, the job still covers an event on its own day |
| Lock day 1:00 PM | **Deadline warning**: "pay before 5:00 PM or your spot is released" | `rsvp_deadline.py`, job `rsvp_deadline` (every 10 min 1–5 PM), dial `rsvp_deadline_auto` | LIVE v2.583.0 since 1:01 PM 10/26. First send: Christopher Espinosa (802), Silverhorn, 1:10 PM |
| Lock day 4:50 PM | **Release**: unpaid and warned → not-playing mark + "your spot has been released" email | same | LIVE v2.583.0. First run today at 4:50 PM. Kerry (#2313): this is the last payment email for the event |
| Lock day 5:00 PM | Pairings auto-generate (if nobody paired it). Manager review prompt | `auto_generate_pairings`, `pairings_approval.py` | LIVE |
| Lock day 7:00 PM or on approval | Tee-times email: player / course contact / manager | `teetimes_email.py`, dial `teetimes_email_auto` | ON since 10/19 (CoS #2307 item 2) |
| On manager approval | Event-day email (YOUR START card, games, personal scoring link) | `event_day_email.py` via `approve_and_send` | LIVE |
| E 7:00 AM | Event Info email | — | Kerry ruled a move to **6:00 AM** (#2307 item 3). NOT BUILT |
| After lock until first tee | Changes: a moved, added or removed player and both groups (UPDATED GROUP); only the changed sheets to the course | `after_lock.py`, job every 15 min, dial `after_lock_auto` | LIVE |
| E+1 6:00 AM | Results email | `results_email.py` | LIVE |

**Deadline-email rules (v2.583.0, live).** Built exactly to Kerry's 10/26 ask and to #2307 item 4.
- **Who:** the Events page's RSVP-only people.
- **Never emailed:** known mail scanners, people with no email, and events in `payment_reminder_exclude_events` (money collected outside the store, such as the Lone Star Cup).
- **Release:**
  - Only someone who was warned is released; an RSVP after the last warning is never released.
  - A release is the Events page's own not-playing mark: nothing is deleted, the page can undo it, and a later registration puts the person back as registered.
  - A shop $0 RSVP-only order row is never released automatically; it raises one COO item.
- **Once each:** once per person per event per kind, and logged.
- **Wording (shown to Kerry 10/26):**
  - Warning: "We have you down for {place} on {date}, but we haven't received your payment yet. Groups are set at 5:00 PM today. If your payment isn't in by then, we'll have to release your spot so the groups can be built without you." It has the registration button, the "See who's registered so far" link, "If you can't make it this week, just reply", and the manager's text line.
  - Release: "We didn't receive your payment by 5:00 PM, so we've released your spot ... If a spot is still open, you can still register and we'll fit you in [button]. If the groups are full, reply ... waitlist."
  - Both are in Screens (`/admin/screens#rsvp-deadline`) on three devices.

## 4. What happens after the release / after lock

- **Pays after release, before 5:00 PM:** they're registered, so the 5:00 PM run deals them in.
- **Pays after 5:00 PM:** they're a late add. Seat-fill is RULED (10/20) but NOT BUILT; today they sit Unassigned and the manager places them. Sized at one session for after Tuesday (#2310).
- **No open seat:** the waitlist is Kerry's ruling at lock (remainder 0: event full, waitlist). No waitlist mechanism is built.
- **Requests after lock:** not honoured automatically (RULED 10/20).

## 5. Known gaps and conflicts to settle

1. **Payment reminders after the lock.** RULED (#2313), Kerry: "Payment Reminders - Those stop at the 5:00p lock for any specific event. So the 4:50p you've been removed email is it for payment reminders for that event." As built, the 6:00 AM job still covers an event on its own day, so Tue 10/27 at 6:00 AM it would remind anyone still RSVP-only for Silverhorn and Teravista (people never warned, such as known scanners, or anyone who RSVPs after 4:50 PM). The stop-at-lock guard is being built for Kerry's Deploy tonight. Still open: the 6:00 AM reminder and the 1:00 PM warning can both reach the same person on the lock day.
2. **Last call vs the deadline.** The Mon 7:00 AM last call says "Sign up by 5:00 PM tonight". It goes to people with NO answer. The 1:00 PM warning goes to people who said I'm in but haven't paid. They don't overlap, but the wording should match ("5:00 PM, when groups are set").
3. **The 18-hole lock.** The Error Handling Spec says 18-hole events lock E-3 at 5:00 PM. The pairings dial uses E-2 for a dialled Saturday. The deadline follows the pairings dial. Which is right for the Fall Championship (Sat 10/31)?
4. **Texting** (Twilio) is not built. Every step above is email only.
5. **Weekend invitation schedule** is open (timeline §6).
6. **Event Info at 6:00 AM** (#2307 item 3) is not built.
7. **Golf Genius RSVPs** are still counted until `gg_rsvps_off`. Should they be switched off now that the Tracker invitation is the RSVP?
8. **The scanner exclusion** uses the known-scanner rule. "Unconfirmed taps" (#2307 item 4) has no separate state beyond the one-tap confirm.

## 6. Rulings Kerry owes (one line each)

1. Ratify the RSVP model in §1–2: a tap is an RSVP, dealt into pairings, released at lock if unpaid.
2. Ratify the §3 timeline, row by row, and the deadline wording.
3. §5-1: reminders stop at lock is RULED (#2313). Still open: skip the 6:00 AM reminder on the lock day itself, since the 1:00 PM warning follows? (Proposal: yes.)
4. §5-3: the 18-hole lock day, E-2 or E-3.
5. §5-7: switch Golf Genius RSVPs off (`gg_rsvps_off`)?
6. Seat-fill for paid late adds (#2310) and the waitlist: build after Tuesday?
7. Event Info at 6:00 AM: build after Tuesday?
8. The weekend invitation schedule.
