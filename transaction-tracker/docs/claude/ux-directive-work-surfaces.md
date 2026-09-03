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

## 4. Target structure (a starting proposal, not a spec — argue with it)

**Tier 1 — always visible (target: 3 controls, first lead card above the fold
at 390×844):**
- Page title and one status sentence, e.g. *"86 leads · 0 new · 0 overdue ·
  33 responded."* Red only when something is actually wrong.
- One scope control: chapter (All / Austin / SA).
- One **Filters** button carrying a count badge when filters are active.

**Tier 2 — one tap (a bottom sheet on mobile, a popover on desktop):**
- Status, campaign, availability, importance, invites, search, sort.
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
  1. Queue, default state, top of page through the first three rows.
  2. Filters sheet open, two filters active, badge visible.
  3. Row card anatomy, called out: new · touched · responded · overdue ·
     converted · dismissed · snoozed.
  4. Stats view with the campaign panels and the ad-set table.
  5. Empty, loading, and filtered-to-nothing states. These are where the
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

1. At 390×844 the **first lead card is visible without scrolling**.
2. **At most three** always-visible controls sit between the page title and the
   first row on mobile.
3. **Every control available today is still reachable in two taps or fewer.**
4. **No control appears twice** on the same screen.
5. A manager can go from cold open to a sent text in **three taps**: open,
   pick a lead, Text.
6. Active filters are **visible without opening the sheet** (the badge).
7. Empty, loading, and no-results states are designed, not accidental.

---

## 8. Process and sequence

1. CA ratifies §2 and the cut list with Kerry.
2. CD authors the canvas and delivers it per `handoffs/README.md`.
3. tracker-claude commits and deploys the bundle so both of you can read it
   through `get_tracker_source`.
4. CA reviews against the acceptance criteria; Kerry ratifies.
5. tracker-claude implements the Lead Center as the reference build.
6. Kerry uses it for a week on the phone. Then the pattern rolls to Events,
   Transactions, and Customers, one page per release.

**Nothing is implemented before Kerry ratifies the design.** Plan first, build
second.

---

## 9. Standing rule that comes out of this

Every future feature wave that wants to add a control to a work surface names
the tier it belongs to, and if it lands in Tier 1 it names what leaves. That
rule is the actual fix. The redesign is just paying off the debt we already
have.
