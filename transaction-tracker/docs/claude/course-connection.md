# Course Connection: concepts and the first slice (DRAFT for Kerry and CA)

Customer Communications lane, under the CCO umbrella. Tue 10/13/2026.
**Concepts and spec only. No code, schema, sends or money.** Kerry and CA dig
in from here.

Kerry, 10/13: "We need to start developing some correspondence automations
with course contacts to be able to update them on upcoming events. This would
be the start and part of our Course Connection module." Course Connection
covers the FULL lifecycle: scheduling, contracting, setup, operating, close
out and payment. It should be as autonomous as possible per course, with a
course-contact interface where courses see the full event details, interact,
and lock down pricing, while they keep working inside their own systems where
needed (mailbox #1685).

**Why now (the lesson from today, #1681):** Miguel Amaya's 8/20 agreement
with The Quarry (Oct 13, 4:30 shotgun, Back 9, $39 + tax) went to Kerry's
personal inbox. It never reached an organization record on either side.
Chris Lopez had no copy, and the start was disputed on event day. **Every
agreement must be written, sent from TGF, sent to the course's primary
contact, acknowledged, and logged against the event.**

---

## 1. FIRST SLICE: the course-facing messages

### Who gets what (by contact role)

Contacts come from Tracker Build's `course_contacts` proposal (#1683). It
gives each person a customer_id, a title, and To / CC / none. I suggest the
To/CC choice be made **per message type**, not once per person. A GM wants
the agreement and the close-out but not tonight's cart signs.

| Message | Primary contact | Backup | GM | Head pro / AGM | Billing (new role) | TGF copy |
|---|---|---|---|---|---|---|
| M1 Event confirmation (the agreement) | To | CC | CC | CC | CC | chapter manager + Kerry |
| M2 One-week check-in | To | CC | – | – | – | chapter manager |
| M3 Final count + course files | To | CC | – | CC | – | chapter manager |
| M4 Change after final count | To | CC | – | CC | – | chapter manager |
| M5 Thank-you + close-out | To | CC | CC | – | To | chapter manager + Kerry |

With no primary contact on file, every message is **refused, never guessed**
(the same rule as the course files today).

### The messages

**M1. Event confirmation (the written agreement).** This is the fix for
today's problem.
- **When:** as soon as the event's date, course and price are set in Event
  setup, and again whenever any confirmed term changes (a "REVISED" version).
- **The system fills in:**
  - the event name and date;
  - the course, nine (front / back / 18), start type, start time, and start
    holes or tee-time block;
  - the expected player count range;
  - the agreed price per player (`course_cost`, plus tax);
  - carts, the TGF contact and phone, and a reference number.
  - **Not stored today** (needs Kerry's call on where they live): rain or
    cancellation terms, minimum guarantee, food and beverage, the final-count
    deadline.
- **The ask:** "Reply CONFIRMED, or tell us what's different." In a later
  phase, a one-tap Confirm link (section 2).
- **Logged:** the exact text sent, who it went to, when, and the course's
  reply, all against the event.

**M2. One-week check-in (T-7).**
- **Fills in:** current registrations, the projected range, and the same
  terms as M1 marked "unchanged since your confirmation of <date>". It flags
  any change since M1.
- **The ask:** confirm the start and any course needs (carts, a rules sheet
  or local-rules changes).

**M3. Final count + course files (T-1, after the manager approves the
pairings).**
- This rides the new pairings-approval flow: the manager's Approve sends the
  player emails and this together.
- **Fills in:** the final count, the start holes per group and the tee
  sheet, with the existing Course Files attached (Starter Sheet, Cart Signs,
  Scorecards, Proximity, Rules of Play; Tracker Build v2.556.x).
- This replaces today's manual Course Files button send.

**M4. Change after the final count (event eve or day).**
- **Trigger:** a WD or add, a start change, or weather. The manager approves
  a one-screen "what changed" message: old count to new count, and which
  groups or files changed. Updated files are attached.

**M5. Thank-you + close-out (the day after).**
- **Fills in:** players who actually teed off (from the scores), the amount
  due under the M1 terms, and the payment method and date.
- **The ask:** "Please send your invoice to <billing address>." This links
  to the CFO lane: the payment is recorded against the event, and the invoice
  is matched to the receipt.
- A short thank-you in the house voice, plus the next date already booked at
  that course, if there is one.

### Approval and safety (the same rules as the event-day email)

- **Approval:** Kerry approves each message type's wording once. Every send
  waits on an OK: Kerry's, or the chapter manager's for M3 and M4 (the
  pairings approval already covers M3). Nothing auto-sends until Kerry says
  he is comfortable. Then individual message types can move to automatic,
  one at a time.
- **Sending:** it goes from TGF's mailbox, never a personal one, through
  Track B's send-path spec (SPF / DKIM, and TNEF now off, 10/13). Reply-to
  is the chapter manager, and ideally a shared TGF bookings mailbox (an open
  question below) so the course's reply lands on an org record.
- **The record:** every send and every reply is kept against the event and
  the course. It is the agreement history the course and TGF can both point
  to.
- **Staff test:** the same staff-preview and test path as the event-day
  email.

---

## 2. BEYOND THE FIRST SLICE: concepts across the lifecycle

**Scheduling**
- A per-course calendar of TGF dates (booked, held, proposed). A season
  booking request: "here are the 12 Tuesdays we'd like in 2027", with
  per-date accept or counter.
- Holds that expire if not confirmed, with a reminder to both sides.

**Contracting**
- A **course agreement record** per event (or per season, with per-event
  overrides): price, tax, carts, minimums, rain / cancellation, F&B, the
  final-count deadline, and the nine / start format. Versioned: a change
  makes a new version, and the old one is kept (past events are frozen).
- **Course portal, one link per event:** the course sees the event and the
  agreement and taps **Accept**. That one tap would have prevented today's
  dispute. It is a signed link for the course; courses are not Tracker users
  (Kerry to rule, as he did for managers).
- Templates per course group or chain where several courses share terms.

**Setup**
- Event setup shows the course's contacts and agreement status: draft, sent,
  accepted, revised.
- Course preferences as data: how they want counts (email, portal, their own
  booking system), how often, cart-sign format, starter-sheet style, where
  local rules come from.

**Operating**
- The course portal shows live registrations, the final sheet when approved,
  and any changes, so fewer emails are needed.
- Event-day contact card: who is on site from TGF and from the course.

**Close-out and payment**
- Players actually played compared with the agreement's minimum, giving the
  amount due. The invoice is matched against the payment in the ledger (CFO
  lane). Disputes are kept against the event.
- A per-course scorecard for TGF: rounds per year, money to the course,
  on-time starts, issues. It is useful when negotiating next season.

**Working inside the course's own systems**
- Many courses run their own tee sheet (foreUP, Club Prophet, Lightspeed,
  GolfNow and others). Offer the files in the format they import (CSV / PDF)
  rather than asking them to re-key. Golf Genius is not the ruler any more,
  but some courses may still like its format.
- Their own contract paperwork stays theirs. The portal attaches their
  signed copy to the agreement record.

**Scale (the national goal)**
- Everything here is per course and per chapter, run by a "people manager"
  chapter leader, not a technician. The system writes, times and logs. The
  leader approves and builds the relationship.

---

## 3. Questions for Kerry (one at a time when you're ready)

1. **Who signs the confirmation (M1):** you for every chapter, or each
   chapter manager?
2. **A shared bookings mailbox** (e.g. a bookings@ address on
   thegolffellowship.com) for course replies, so nothing lives in a personal
   inbox again?
3. **The course portal:** a signed one-tap link per event (courses never log
   in), or a course login?
4. **Agreement terms we don't store yet:** rain / cancellation, minimums,
   F&B, final-count deadline. Do you want these captured per event, or per
   course season with per-event overrides?
5. **M5 billing:** do courses invoice you, or do you pay on the day? That
   decides whether M5 asks for an invoice or confirms a payment.

## 4. Dependencies (already in flight)

- `course_contacts` schema and roles: Tracker Build #1683, then db-claude,
  then your rule 3b.
- The send path (SPF / DKIM / TNEF): Track B #1607. TNEF was fixed 10/13.
- Pairings approval, which M3 rides on: live v2.555.0.
- Course Files: Tracker Build v2.556.x.
- The Quarry course-facing HOLD stays until you release it (#1681).
