# Two Man Tour — Flight Board (admin-only, separate brand)

Shipped v2.212.0 (2026-08-08, Kerry-directed, built for that night's event).
The Two Man Tour is a **sibling brand, not TGF** (see `gg-history.md`) — this
page deliberately shares nothing with the Tracker's TGF surface: no nav
shell, no database reads/writes, its own dark-gold branding.

## What it does

`/twomantour` ranks the live teams of an unknowngolf event low → high and
lets Kerry set flights interactively:

- **Flights** count (1–8) with **draggable gold flight lines** that start at
  equal spacing across the field. Dragging a line moves the flight break one
  team at a time; a flight can never go below 1 team; lines can't cross.
- Flight headers show team count + score range; **Copy flights** puts the
  final flight list on the clipboard as text.
- **Auto 60s** re-fetches while scores are still coming in. Flight lines are
  kept (by position index) across refreshes.
- Per-event **localStorage** persistence (flight count, line positions,
  score column, last event ids) — nothing is stored server-side.

## Getting there

v2.213.0: the Tracker nav carries an **admin-only gold "Two Man Tour" pill**
(desktop `.shell-tmt-pill` + mobile drawer `.shell-tmt-drawer` in
`_shell_nav.html`) linking to `/twomantour`. It rides the existing
`admin-nav` gating in `auth.js` — only admin sessions see it. Gold
`#d4af37`, deliberately not TGF orange: it's a doorway out of the Tracker.

## Data path

- Route `GET /twomantour` (page shell, public — shows its own PIN gate;
  admin PIN via the existing `/api/auth/login`).
- Route `GET /twomantour/api/live?eventId=&tourId=` — `@require_role("admin")`.
  Server-side proxy (browser can't cross-origin fetch unknowngolf) →
  `twomantour.fetch_live()`:
  - Host-locked to `league.unknowngolf.com`, ids must be numeric (SSRF guard).
  - Optional `TWOMANTOUR_COOKIE` env var is sent as a Cookie header if the
    page ever requires a login (untested — the live-scoring page is
    expected to be public).
- `twomantour.py` — stdlib-only parser (`html.parser`, no bs4): extracts
  EVERY table (nested layout tables included), scores each by how many rows
  look like *name + numeric score*, returns the best table's headers + rows
  plus name-column / numeric-column guesses. Position/Thru/Rank columns are
  filtered out of the score-column candidates.
- The **client** picks the score column: auto-prefers header /net/, then
  /total|score/, then /gross/, else last numeric column — with a manual
  dropdown override, because the unknowngolf markup is not under our
  control and was NOT inspectable from the build sandbox (egress blocked).

## Event-night fallback (important)

If the auto-fetch fails or the parser can't find the leaderboard (JS-rendered
page, login wall, markup change), **Paste scores** takes the leaderboard text
copied straight off the live page — one team per line, score as the last
token (`E`, `+2`, `-5`, `68` all parse; leading positions and thru markers
are stripped). Everything downstream (sorting, flights, dragging, copy)
works identically on pasted data.

## Known limits / future

- Verified against synthetic JSP-style markup + Playwright UI tests, not the
  real event page (sandbox egress blocked `league.unknowngolf.com`); the
  column picker + paste fallback are the insurance. After first live use,
  note here what the real page's table actually looks like.
- Flight assignments are not persisted server-side and nothing feeds payouts
  — this is a decision aid Kerry reads from during flighting. If Two Man
  Tour ever needs money math in the Tracker, that's a new scope (rule 3b).
