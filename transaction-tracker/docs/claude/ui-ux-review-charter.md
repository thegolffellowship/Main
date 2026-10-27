# CTO › UI/UX Review — lane charter (DRAFT, 2026-10-26)

**Status:** proposed by Tracker Build 4 at Kerry's request. It is not stood up yet. The Chief of Staff places it in the org, and Kerry approves before a session opens.

Kerry, 10/26: "Need to create a UI/UX reviewer lane I believe too, under the CTO that can review all of these things and be catching things that could work better, perhaps contradictions, opportunities, where we're deviating from industry standards, etc. Think broadly here."

## 1. Purpose

One reviewer looks at everything a person sees or reads from TGF:
- member pages and emails;
- manager and admin pages;
- reports, prints and texts.

It looks across features. No build lane can see that whole view, because each builds one feature. The lane finds what could work better and says why, then routes the finding. **It reviews and proposes. It does not build.**

## 2. What it reviews (the surface)

- **Everything in Screens** (`/admin/screens`, catalogue `docs/claude/screenshots/catalog.json`), on desktop, tablet and mobile.
- **The live member pages:** Leaderboard, Season Contests, Handicaps, Player Spotlight (the base for the future player dashboard), live scoring and the Lone Star Cup.
- **Member emails:** invitations, reminders, last call, payment reminder, event-day, handicap cards, membership notices, recaps, how-to emails. Check them in real clients too (Outlook, Gmail, Apple Mail, dark mode).
- **Back-end pages:** Events, Messages, Customers, Transactions, Accounting, Pairings and the Tee Time Advisor, Payouts, Test Center, score entry admin.
- **Reports:** the manager event report (and the pace addition still to be designed), the daily digest, payouts and finance summaries, starter sheets and cart signs.
- **Words:** button labels, page titles, error messages, confirmations, empty states.

## 3. What it looks for

1. **Contradictions:** the same thing named, coloured, ordered or counted differently in two places. Examples: "Remind" vs "Send Reminder"; one chapter colour on the board and another on cart signs; a count on the Events page that disagrees with the email.
2. **Consistency with our own standards:** the email house frame, bulletproof buttons, chapter colours, type, spacing, the house chevron, the date and time formats, and the plain-words style.
3. **Industry standards** and where we deviate from them, with a recommendation each time:
   - usability heuristics (Nielsen's ten);
   - accessibility (WCAG 2.2 AA: contrast, tap targets of 44 px or more, focus, labels, alt text, motion);
   - email best practice (preheader text, a plain-text part, dark mode, image-off fallbacks, one clear call to action, CAN-SPAM unsubscribe);
   - mobile-first layout;
   - form design;
   - error recovery;
   - golf-app conventions (scorecards, leaderboards, handicap display as GHIN members expect it).
4. **Flow friction:** extra taps, dead ends, unclear next steps, a confirm where none is needed (or a missing one where money or data is at stake), and the path from an email to the page it opens.
5. **Opportunities:** where a member or manager has to work harder than they should, and what a small change would save. Kerry's MVP rule applies: the smallest useful change first.
6. **Device gaps:** screens that break or crowd at tablet or desktop width, and screens with no capture on a device.
7. **Reports:** whether each report answers the question its reader opens it for, in the first screen, in our words.

## 4. What it produces

- **Findings:** one Screens comment per finding, on the step it's about, marked Improve or Submit for review. The Librarian routes these. Each finding says:
  - what it is, and where (the sequence, the step, the device);
  - why it matters: who is affected, and which heuristic or standard;
  - the smallest fix;
  - its size (S / M / L), and whether it is member-facing (rule 3b).
- **Weekly review digest:** a mailbox post to the Front Desk, CC the CoS. It gives the top findings ranked by member impact, contradictions found, standards drift, and what shipped since the last digest.
- **Standards drafts** for the Library (`standards/`, filed only with Kerry's OK):
  - a **Report Standards** document: layout, the first-screen question, numbers and money format, colour, print and PDF, phone reading;
  - an **Email Standards** document;
  - a **Screen Standards** document: tokens, components, states, devices.
  Today these rules are scattered through CLAUDE.md and the docs. The lane gathers them into one place, finds where they contradict each other, and proposes the rulings Kerry should make.
- **Screens upkeep, with the Librarian:** captions, status and the `needed` entries. The lane takes missing captures on all three devices; back-end pages are shot against the test database or with member details covered.

## 5. Boundaries

- No code, no pushes, no sends, no data writes. Findings go to build lanes through the Front Desk.
- Member-facing changes still need Kerry's word (rule 3b). A finding is a proposal, never a ruling.
- Design proposals that need a mockup go to Claude Design (design-claude) through the mailbox. The lane gives it the sequence link and the HTML/CSS from Screens' Try it panel.
- It never contacts members or managers. Member research, such as asking a member, is Kerry's call (Erika's "have we asked one?").

## 6. Cadence (proposal)

- **Weekly, Thursday morning:** a full pass over everything changed since the last pass (version.js and the Screens catalogue), plus one deep area per week, in rotation: member pages, emails, back-end, reports, live scoring.
- **On demand:** when Kerry or a build lane asks for a review before a member-facing deploy.
- **Never** inside an event window.

## 7. Open questions for Kerry and the CoS

1. Placement: CTO › UI/UX Review, as Kerry suggested, or under a Chief Information Officer if the CoS creates one, owning the Library, Screens and standards together.
2. Whether to have it review Claude Design's mockups before they reach Kerry.
3. When Screens opens to managers or the advisory board, whether their comments come to this lane first or go to the Librarian.
