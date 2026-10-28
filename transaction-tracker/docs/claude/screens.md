# Screens — the Librarian's screenshot library (v2.582.0, Kerry 2026-10-26)

Kerry: "I want to be able to go to a page and select whatever I want to look at to review standard screenshot layouts and sequences" ... "managed by the Librarian" ... "review/comment on these while in the interface if we see things we want to improve on or submit for review. That information would go to the librarian who would submit back to the Front Desk or Chief of Staff".

## Where things live

- **Page:** `/admin/screens` (Admin › Screens). It is admin only. The dial `screens_viewer_role` ("admin" by default, or "manager") opens it to managers. A link `/admin/screens#<sequence id>` opens that sequence directly, even on a fresh app launch.
- **Pictures:** in the repo, under `docs/claude/screenshots/<folder>/`. The route `/admin/screens/file/<folder>/<file>` serves them under the same role check. Only image and PDF files inside that folder are served.
- **Catalogue:** `docs/claude/screenshots/catalog.json`. **The Librarian owns it.** Each sequence has an id, title, area, audience, status, version, taken date, folder, source_doc, notes and steps. Each step has a file, caption, view (phone / desktop / email) and an optional state.
  - The page lists the areas in the order of `areas`.
  - The statuses are:
    - **current:** what members and managers see now.
    - **built:** on a branch, not live.
    - **mockup:** a proposal.
    - **superseded:** kept for history.
    - **reference:** taken at build time; the screen may have moved on.
  - A step's state overrides its sequence's status.
- **Gaps:** a file on disk that isn't in the catalogue shows under **Not catalogued**. `test_screens.py` fails on one, and also fails on a catalogued file that is missing.

## Devices, demos and source (Kerry 10/26, same day)

- **Device toggle:** each step's `shots` maps `desktop` / `tablet` / `mobile` (or `any`, for prints, cart signs and PDFs) to a file. The page's Desktop / Tablet / Mobile toggle shows each device's count (for example "Tablet 0/5"), and the viewer remembers the choice. A missing device shows "No tablet screenshot yet" with a button to show one the step does have.
  - Standard capture sizes: mobile 390 px at 2x, tablet 820 px, desktop 1280 px.
  - Name the files `<name>.png` (mobile), `<name>.tablet.png` and `<name>.desktop.png`.
- **Pictures already in use elsewhere** are catalogued where they live, not copied. A sequence's `base` is `screenshots` (the default), `static` (static/img, for example the live scoring guide pictures) or `mockups` (docs/claude/mockups).
- **Try it:** a sequence's `demo` list is links the page opens in a frame sized to the chosen device. Every demo must be read-only or preview-only:
  - the live member pages;
  - `/admin/screens/demo/invitation`, the invitation on the staff preview person with PREVIEW links, so taps open the real pages and record nothing;
  - `/admin/screens/demo/payment-reminder`, the reminder for the next event, only rendered;
  - the mockups;
  - the Test Center, which writes only to test tables.
  Never add a demo that can send, pay or write a real row.
- **HTML/CSS tab:** shows the exact source the demo serves, with Copy and Download .html, so Claude Design and the CA can take a screen straight into their work.
- **Status `archived`:** a by-hand folder that no longer shows a live screen; kept for the record (below).
- **Status `needed`:** a screen we should have and don't yet. Reports and Back-end pages start as `needed` entries. Back-end pages must be shot against the test database, or with member details covered, because they show money and contact details.

## Screens stay current by themselves (v2.584.0, Kerry 10/26: "an absolute requirement")

- **Recipes:** a step's `capture` is `{"url": "/member/..."}` (a public page) or `{"render": "<name>"}` (`email_parser/screens_capture.RENDERS`). A render is HTML from the SAME builder that sends or serves it (`invitations.build_message`, `payment_reminder.preview`, `rsvp_deadline.build`, the `/rsvp/<token>` routes on preview tokens, `app._rsvp_confirm_page`), so a capture can never drift from the live code.
- **Production:** job `screens_capture_deploy` runs 10 minutes after each boot (once per deployed version, app setting `screens_capture_version`), and job `screens_capture_nightly` runs at 3:37 AM. Both take every recipe on desktop, tablet and mobile into `<data dir>/screens_live/<sequence id>/`. The page shows these first ("Auto-captured ... on vX") and the repo copy otherwise.
  - Renders use the next upcoming event and the staff preview person. With nothing upcoming, renders wait; production never writes a demo event.
- **The repo, enforced:** each sequence with recipes lists `watch` (files, or `path::function` for one function in app.py) and carries `watch_hash`. `test_screens.py` FAILS when the watched code changed and the hash did not. The fix is `python3 tools/screens_refresh.py <sequence>`: it retakes the recipes from the code on a throwaway database and stamps the new hash. Use `--hash-only` when no recipe can show the change.
  - In a sandbox without Python Playwright it runs through `tools/screens_capture.js` (Node Playwright).
- **Demo recipes** (Kerry 10/26: "want updated screens to be automated to mirror with what's live"): `{"demo": "event", "path": "/member/score?t={t}"}` is a page that needs an event, a round or a link. `screens_capture.capture_demos` starts `tools/screens_demo.py` as its OWN process:
  - on a throwaway database (`DATABASE_PATH` a fresh temp file, `SCREENS_DEMO=1`; the runner refuses to start otherwise);
  - with every credential stripped (mail, Azure, Anthropic, Brevo, HubSpot, Meta, Twilio, payments, Railway, MCP, Golf Genius, and anything ending `_PIN`, `_TOKEN`, `_KEY`, `_SECRET`) and its own session key, so nothing in it can reach mail, money or a member;
  - it seeds one event dated today ("s9.99 Demo Links", eight made-up people with ids 990001-990008, two foursomes, a live-scoring round) and serves the Tracker's own app on 127.0.0.1. Path variables: `{event}`, `{t}` (group 1's signed link), `{t2}` (group 2's).
  Production runs it after every deploy and nightly beside the other recipes; `screens_refresh.py` runs it for the repo. Never production data.
- **Clicks:** any recipe may add `"click": [css selectors]` (the first match of each is tapped in order before the picture) and `"wait"` (ms after each click). Example: the Leaderboard with the latest event opened clicks `details.evlb-ev > summary`; the hole screen clicks `[data-act="gate-score"]` then `[data-act="pick"]`.
- **A missed capture is visible:** a failed or partial production capture writes `agent_action_log` `screens_capture_failed` ("FAILED" or "partial", the error count and the first error). Before 10/26 a failure logged nothing.
- **Automated (10/26):** invitations, payment-reminder (the built email), rsvp-deadline, member-pages (Leaderboard list and an opened event, Season Contests, Handicaps, Spotlight, the live scoring guide page), lone-star-cup-live (board, info, draw), score-entry-live (join, pick your name, hole, scorer's board, from the demo) and member-teesheet (from the demo).
- **Not automated, and why** (each sequence's `automation` field, shown on the page):
  - back-end pages (`be-*`) and reports (`report-*`): "not automated: PII". They show member names, emails and money, are never captured from production, and the demo runner has no signed-in admin session yet;
  - live-scoring-guide-pictures: these files ARE the guide's pictures, curated one full iPhone screen each; score-entry-live retakes the same screens from the code for comparison;
  - mockups (`mockups-*`) and leaderboard-review-2026-10-19: not live screens.
- **Status `archived`:** a hand-taken folder that shows screens no longer live. It is kept, never deleted, and its notes name the sequence that replaced it (the 9/25-9/28 score-entry sets, the Cup sets after the 2026 Cup, events-leaderboard-batch1).

## Comments go to the Librarian, through the mailbox

A comment on the page is a mailbox post:
- **Topic and author:** `screens`, author `screens-page`.
- **Header:**
  ```
  TO: librarian-claude (COO › Library)
  CC: front-desk
  FROM: screens-page (signed in as <role>), <time>
  KIND: Improve | Submit for review | Note
  SEQUENCE: <id> — <title>
  STEP: <file> — <caption>        (when one step is picked)
  ```
- **Body:** the text.

The thread under a sequence shows every `screens` post whose SEQUENCE line names it. **Librarian:** reply with topic `screens` and the same `SEQUENCE: <id>` line, and your reply shows in the thread on the page.

**Routing:** the Librarian files each comment, then routes it to the Front Desk, which hands it to the right lane. The Chief of Staff gets it only when it needs a ruling. The Librarian says on the thread where it went.

**A comment is never a ruling.** Its author is not `kerry`, and its header names no relay, so `customer_query._kerry_ok` refuses it, even when someone types a Kerry quote into it. A change a comment asks for still needs Kerry's word in the usual way.

## Keeping it current (standing rule for every lane)

When a member-facing or manager-facing screen or email changes how it looks:
1. Retake its sequence in the same commit as the change (Playwright, 390 px phone at 2x; email at its real width).
2. Replace the old files, or keep them with `"state": "superseded"`.
3. Update `catalog.json`.
4. Tell the Librarian on the mailbox.

New sequences go in a new folder. Name it `<area>-<yyyy-mm-dd>`, or after the feature.

Guard: `test_screens.py`.
