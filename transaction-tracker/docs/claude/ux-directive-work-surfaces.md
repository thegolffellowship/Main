# UX Directive — Tracker Work Surfaces (Kerry, 2026-09-03)

**To:** platform-claude (CA) and design-claude (CD)
**From:** Kerry, via tracker-claude
**Pilot surface:** Lead Center (`/admin/leads`). **Then:** every work list in
the Tracker.

> "Way too much going on up top. Especially on mobile. I really don't need
> that data between the top stats and the tabs." — Kerry, 2026-09-03

That comment is about one line of text, and the line is already gone
(v2.292.1). The directive is about the reason it accumulated.

---

## 1. The problem, counted

The Lead Center works. It has also taken eleven feature waves in five weeks
(#352 through #391), and every wave added a control to the top of the page
because that is where there was room. Nobody ever removed one.

Before the first lead row, a manager now passes:

| Band | Contents | Controls |
|---|---|---|
| Shell nav | brand, version, 7 links, Two Man Tour, Admin, Log out | 11 |
| Stat cards | New · Touched · Converted · Past 48h untouched (all clickable filters) | 4 |
| Toolbar 1 | chapter segment (3), status chips (5), search, sort, campaign, Stats | 12 |
| Toolbar 2 | Availability (4), Importance (4), Invites (4) | 12 |
| Exports | SA CSV, Austin CSV | 2 |

**26 controls inside the page, 41 counting the shell, before one lead is
visible.** On a phone the stat cards hide and the rest wraps into five or six
stacked rows, so the first card lands below the fold. Each lead row then
carries eight more targets.

**The clearest single finding: the header duplicates itself.** The four stat
cards and four of the five status chips are the same filter, rendered twice,
eight tap targets doing four jobs.

This is not a Lead Center problem. Events, Transactions, and Customers grew the
same way. We want a pattern, not a patch.

---

## 2. The job to be done

Anchor every decision to this, in Erika's framing:

> **What is the member — here, the chapter manager — actually trying to do?**

At 8 AM on a phone, Kerry or Robert is doing exactly one thing:

**"Who do I contact next, and what do I say?"**

Everything else on the page serves a different job on a different day:
measuring the campaign (weekly, at a desk), exporting an invite list
(occasionally, at a desk), slicing leads by survey answer (rarely, when
planning a push). Those are real jobs. They are not *this* job, and they should
not compete with it for the first screen.

---

## 3. Principles

1. **One job per screen.** The queue is a work list. If a control does not help
   decide who to contact next, it is not in the queue's first screen.
2. **Progressive disclosure, three tiers.** Tier 1 is always visible and should
   be about three controls. Tier 2 is one tap away (a sheet or a menu). Tier 3
   is its own view. Nothing gets deleted; things get filed.
3. **Never render the same control twice.** One way to do a thing.
4. **Mobile is the design target, desktop is the wide case.** Design the 390 px
   artboard first. If it works there, the desktop version has room to breathe.
5. **The list is the interface.** Chrome earns its space by helping the list;
   otherwise it goes in a drawer.
6. **State is a sentence, not a scoreboard.** One line telling the manager
   where they stand beats four cards restating the same counts.
7. **Density is not the enemy; undifferentiated density is.** A dense row is
   fine when one thing is clearly primary.

---

## 3A. Mobile is the PRIMARY surface, not the small one (Kerry, 2026-09-03)

**This section overrides any default assumption that desktop is the real
design and mobile is the adaptation. On this page the reverse is true, and the
reason is not preference. It is capability.**

> "Need to specifically be clear about mobile views. It's the most logical
> first use because of texting working only with my iPhone currently. It's
> particularly cumbersome." — Kerry, 2026-09-03

**The desktop cannot do the job.** The Lead Center's primary action is a
`sms:` deep link. That link only opens a composer on Kerry's iPhone. On the
desktop the Text button is decoration: it can show him the message, but he
cannot send it. Until the business texting number lands (#385, scoped to start
after Sep 6), **every first touch TGF makes is physically performed on a
phone.**

So the hierarchy is:

- **iPhone = the production surface.** Working the queue, texting, logging the
  touch. This is where the money is made and where the 48-hour gate is won or
  lost.
- **Desktop = the reporting and admin surface.** Stats, CSV exports, campaign
  setup, bulk cleanup, anything at a keyboard.

Design the phone first, in full, and let the desktop inherit. A layout that is
excellent at 1280 and merely survivable at 390 has optimized the surface that
cannot do the work.

### What is actually wrong on the phone right now

From Kerry's own screenshot at roughly 390 px wide:

1. **The first lead card starts past the halfway point of the screen.** Nine or
   ten stacked bands of chrome come first: status sentence, chapter segment,
   status chips wrapping onto two rows, search, sort, campaign, Stats, then
   three filter groups, then two CSV buttons. He scrolls before he can work.
2. **The filter rows wrap badly, not just densely.** "IMPORTANCE" sits alone on
   its own line. "INVITES" dangles off the right end of the Importance options
   row, orphaned from the buttons it labels. That is a broken layout, not a
   dense one.
3. **The card has five equal-weight action boxes** — Text, preset ▾, Call,
   Email, Note — in a grid where nothing is primary. **Texting is the entire
   job on this device**, and it is rendered as one fifth of a button grid.
4. **Each card carries a second action row** (tag select plus ⋯) for actions
   used far less often than Text, pushing the next lead further down.
5. **CSV export buttons are on the phone**, where a downloaded CSV is close to
   useless.

### The workflow nobody has designed for: the Messages round trip

This is the heart of the cumbersome feeling, and it is invisible on desktop.

The real loop is: **open the queue → find who is due → tap Text → iOS switches
to Messages → send → switch back to Safari → log the touch → find the next
lead.** Kerry does that up to a dozen times in a sitting, and the app switch
happens in the middle of every single pass.

Requirements that follow, and they are not optional:

- **State must survive the app switch.** Coming back from Messages must return
  him exactly where he was: same scroll position, same filters, same expanded
  card. A full reload that dumps him at the top of 86 leads makes him re-find
  his place a dozen times a morning. Use the back/forward cache, and persist
  filter and scroll state so a real reload restores it too.
- **Logging the touch must not be a second errand.** On return, the card he
  just texted should offer a single obvious confirmation, e.g. *"Texted Hector?
  Yes"*, which marks touched, sets the tag, and moves on. Today he has to find
  the card again, open a select, and pick a value.
- **Give him a next.** After a touch is logged, the queue should surface the
  next lead to work rather than making him hunt the list again. CD should
  propose whether that is an auto-advance, a persistent "Next lead" affordance,
  or a focused run mode. Kerry decides which.
- **The preset picker must be one-handed.** The ▾ opens near the top of a card
  today. On a phone it should be a bottom sheet in the thumb zone, showing the
  full message text at a readable size before he commits.
- **Respect what iOS does to `sms:` bodies.** Long pre-filled bodies can be
  truncated or dropped depending on iOS version and whether the thread is
  iMessage or SMS. CD and CA should specify a target body length, and a
  copy-to-clipboard fallback for anything long, so a preset never arrives
  half-written.

### Mobile design requirements

- **Design canvas 390 × 844** (iPhone 15/16 class, Safari, with the browser
  chrome accounted for — the usable height is roughly 780, not 844).
- **Thumb zone.** Primary actions live in the lower two thirds of the screen.
  Nothing essential in the top corners.
- **Tap targets at least 44 × 44 pt** with at least 8 pt between them, per
  Apple's HIG. Several current controls are under that.
- **One primary action per card.** Text is dominant and full width or nearly
  so. Call, Email, Note, tag, and ⋯ are secondary and may collapse behind one
  overflow.
- **A collapsing header.** Chrome may be present at the top of the scroll, but
  it should shrink or hide as he scrolls into the list, and the scope control
  should remain reachable.
- **Filters as a bottom sheet**, opened by thumb, with Apply and Clear all, and
  a count badge on the button so active filters are never a mystery.
- **No hover-only affordances**, anywhere. If it only reveals on hover it does
  not exist on this device.
- **Support Dynamic Type and one-handed reach**; do not assume the smallest
  system font size.
- **Move to desktop-only:** CSV exports, campaign administration, bulk edits.
  The Stats view can be readable on a phone, but it should not be optimized for
  it. It is a desk job.

### How this gets verified

Not in a desktop browser's responsive mode. **On Kerry's actual iPhone, in
Safari, on cellular, outdoors in daylight**, working real leads. The
acceptance criteria in §7 that are marked *(mobile)* are the contract, and the
final check is his: a morning run through ten leads that feels faster than
today.

---

## 4. Target structure (a starting proposal, not a spec — argue with it)

**Tier 1 — always visible (target: 3 controls, first lead card above the fold
at 390×844):**
- Page title and one status sentence, e.g. *"86 leads · 0 new · 0 overdue ·
  33 responded."* Red only when something is actually wrong.
- One scope control: chapter (All / Austin / SA).
- One **Filters** button carrying a count badge when filters are active.

**Tier 2 — one tap (a bottom sheet on mobile, a popover on desktop):**
- Status, campaign, availability, importance, invites, search, sort.
- **Multi-select within a group, ANDed across groups** (Kerry 2026-09-03,
  shipped v2.293.0): picking Availability **Sat + Both** must mean "everyone
  who can play Saturdays," because "Both" is also Saturday-available. The same
  holds for Importance and Invites. Design the controls so that
  more-than-one-selected is the obvious, native state — not a single-choice
  segmented control that happens to allow it. Show the count of active picks,
  and give a one-tap Clear.
- Apply and Clear all. The badge tells the manager filters are on, so they
  never wonder why the list looks short.

**Tier 3 — its own view (already exists as 📊 Stats):**
- Campaign stats, ad-set table, CSV exports, campaign administration.

**The row.** It answers three questions in reading order: **who**, **how hot**,
**what next**. One primary action (Text, with the auto-picked preset), the rest
behind ⋯. Today's eight targets should come down to about four.

---

## 5. What we are asking each of you for

### design-claude (CD) — own the visual answer

Author a canvas in the Claude Design project, delivered per
`handoffs/README.md` (mailbox topic `design-handoff`, lowercase-hyphen
filename, no spaces or em-dashes):

- **Artboards, mobile 390 px first, then desktop 1280 px:**
  1. Queue, default state, top of page through the first three rows. **The
     first lead card must be above the fold at 390 × 844.**
  2. Filters sheet open (bottom sheet on mobile) with **two picks selected
     inside one group** (Availability Sat + Both) plus one in another, badge
     showing the count. Multi-select must read as native, not accidental.
  3. Row card anatomy, called out: new · touched · responded · overdue ·
     converted · dismissed · snoozed. Show the primary action clearly dominant.
  4. **The Messages round trip (mobile only, §3A):** the card at rest → the
     preset bottom sheet open with the full message readable → the return state
     after iOS switches back, including the one-tap "log the touch"
     confirmation and how the next lead is surfaced.
  5. **A thumb-zone overlay** on the mobile queue artboard showing what falls
     inside comfortable one-handed reach and what does not.
  6. Stats view with the campaign panels and the ad-set table (desktop-led;
     readable on a phone, not optimized for one).
  7. Empty, loading, and filtered-to-nothing states. These are where the
     current page is weakest.
- **A component inventory** mapping every element to the existing tokens in
  `static/css/dashboard.css` (`--primary #E87C3E`, `--text #1B1B1B`,
  `--text-muted #6B7280`, `--border #E5E7EB`, `--link #2563eb`, `--green`,
  `--red`, chapter colors, `--radius`, `--shadow`). Bitter for numerals, as
  the stat cards already do.
- **The generalized pattern**, named and documented, so Events, Transactions,
  and Customers can adopt it: header + status sentence, scope control, filter
  sheet, list, row card, detail expansion.

### platform-claude (CA) — own the decisions

- Put the **cut list** to Kerry. Moving things down a tier means he stops
  seeing them at a glance, and that is his call, not ours. Specifically:
  the four stat cards versus the status chips (one has to go); whether the
  Availability / Importance / Invites row survives outside the sheet; whether
  the CSV buttons belong in Stats or in an overflow menu.
- **Ratify the job-to-be-done statement** in §2 with him. If the queue's job is
  something other than "who do I contact next," every recommendation below it
  changes.
- Hold the line on **scope**: this is a layout and hierarchy pass. No new
  features ride along.
- Sequence it against the live work: the Fall campaign closes **Sep 6**, and
  the business texting number (#385) is scoped to start after that.

---

## 6. Constraints

- **No new dependencies.** No component library, no build step, no framework.
  Server-rendered Jinja plus vanilla JS, as today.
- **Existing tokens and the v2 shell.** `_shell_nav.html` stays; this is about
  what sits under it.
- **Manager tier and roles unchanged.** Admin-only actions stay admin-only.
- **iOS Safari is the reference browser**, not Chrome on a desktop. Honor the
  back/forward cache, safe-area insets, and momentum scrolling; assume the app
  switch to Messages and back happens constantly.
- **Behavior that must survive the redesign, exactly:**
  - the priority sort ladder and its section bars (new · follow-ups due ·
    responded · no response · members · converted · dismissed);
  - the 48-hour touch gate and its overdue signal — that is the conversion
    gate, and it must be impossible to miss;
  - one-tap Text carrying the auto-picked SMS preset, with the ▾ picker
    reachable;
  - the notes log and its newest-note preview;
  - follow-up / snooze dates, disposition tags, and the no-loop auto-dismiss.

---

## 7. Acceptance criteria (measurable, so we know when it is done)

1. *(mobile)* At 390 × 844 the **first lead card is visible without
   scrolling**.
2. *(mobile)* **At most three** always-visible controls sit between the page
   title and the first row.
3. **Every control available today is still reachable in two taps or fewer.**
4. **No control appears twice** on the same screen.
5. *(mobile)* A manager goes from cold open to a sent text in **three taps**:
   open, pick a lead, Text.
6. *(mobile)* **Returning from Messages restores scroll position, filters, and
   expanded state** — he never re-finds his place.
7. *(mobile)* **Logging a touch after a text is one tap**, offered on the card
   he just texted.
8. *(mobile)* Every tap target is **at least 44 × 44 pt** with 8 pt spacing,
   and the primary action sits in the lower two thirds of the screen.
9. *(mobile)* **Ten leads worked end to end feels faster than today**, judged
   by Kerry on his own iPhone, on cellular. This is the criterion that
   outranks the rest.
10. Active filters are **visible without opening the sheet** (the badge).
11. Empty, loading, and no-results states are designed, not accidental.

---

## 8. Process and sequence

1. CA ratifies §2 and the cut list with Kerry.
2. CD authors the canvas and delivers it per `handoffs/README.md`.
3. tracker-claude commits and deploys the bundle so both of you can read it
   through `get_tracker_source`.
4. CA reviews against the acceptance criteria; Kerry ratifies.
5. tracker-claude implements the Lead Center as the reference build.
6. Kerry works a real morning run on his iPhone — ten leads, cellular, no
   desktop. If it does not feel faster, it is not done, whatever the artboards
   look like. Then the pattern rolls to Events, Transactions, and Customers,
   one page per release, **phone layout designed first every time**.

**Nothing is implemented before Kerry ratifies the design.** Plan first, build
second.

---

## 9. Standing rule that comes out of this

Every future feature wave that wants to add a control to a work surface names
the tier it belongs to, and if it lands in Tier 1 it names what leaves. That
rule is the actual fix. The redesign is just paying off the debt we already
have.
