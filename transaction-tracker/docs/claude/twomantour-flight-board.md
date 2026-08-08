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
  score column, buy-in, last event ids) for the working session, plus
  (v2.217.0) **server-side tag+save**: Save Event snapshots the whole
  board (teams w/ players + hole cards, cuts, flights, buy-in) into the
  isolated `twomantour_saves` table (Tracker SQLite on the Railway
  persistent volume — deliberately NO FKs/joins to TGF tables); Saved
  lists/loads/deletes snapshots. Routes: GET/POST
  `/twomantour/api/saves`, GET/DELETE `/twomantour/api/saves/<id>`,
  all `@require_role("admin")`.
- (v2.222.0) **Inline per-flight payouts** — a payout strip renders
  INSIDE each flight box (under its teams): pot (teams × 2 × buy-in)
  split among the top `payPct`% (default 25, ≥1 place) on a step-down
  curve (weights n..1), whole-dollar rounding conserves the pot. It's
  part of the flight window, so it moves with the flight line. Controls
  (Buy-in, Pay-top-%, Whole-$) are in the toolbar; Payouts button
  toggles; persists per event; in Copy Flights. (Replaced the v2.220.0
  right-side pane per Kerry.)
- (v2.220.0) Live fetch, post-login: the authenticated event page is a
  JS shell; the server scans it + its external scripts for scoring URLs,
  tries known display/leaderboard endpoints, and parses HTML or a JSON
  leaderboard (`_teams_from_json`). Unresolved probes are dumped with
  samples in the diagnostics panel.
- (v2.221.0) **Data-feed discovery** — the standings live in UG's `.ukg`
  JSON endpoints (`leaderboard.ukg`/`gameResult.ukg`), which need
  eventId+tourId+an action code (a bare call returns "request is not
  recognized"). `discover_data_feed()` opens the display pages
  (tvLeaderboard.jsp, event.jsp), extracts the AJAX call their scripts
  make to a `.ukg` endpoint (`_extract_ajax_calls`, balanced-brace so the
  nested `data:{…}` isn't truncated), resolves the data object against
  the real ids (`_resolve_data`), replays it with the cookie, and parses
  the JSON. Per-endpoint probes (params + sample) go to diagnostics on
  failure. NOTE: the exact `.ukg` param set is still unconfirmed against
  the live site — if discovery fails, the diagnostics sample of the
  display page's AJAX call is the last missing piece.
- (v2.216.0) Tap a team row to expand its **18-hole scorecard** (front/
  back nines, OUT/IN/TOT/PAR, parsed from the 22-column hole row; raw
  fallback), and a **Buy-in $/player** input that shows each flight's
  pot (teams × 2 × buy-in) live in the flight headers and Copy Flights.

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

## The REAL page format (learned live, 2026-08-08)

Kerry's first live use showed the event page is NOT a name+score
leaderboard table — it renders **per-team scorecard blocks**:

```
player HC 1 2 3 4 5 6 7 8 9 F 10 ... 18 B Total (vs Par)   <- header
Weapons of Grass Destruction                               <- team name
Todd Albert (0)                                            <- players (HC in parens)
Josiah Prindle (0)
Tpc San Antonio - Canyons                                  <- course
- - - - - - 3 3 4 3 4 - 17 17 (-2)                         <- hole row, (vs par) last
Unofficial Score                                           <- block terminator
```

v2.214.0: `parse_scorecard_blocks()` (twomantour.py, mirrored in the
template's JS for paste) parses this into teams; v2.215.0 also captures
each block's player names (handicap parens stripped) — shown under the
team name and included in Copy Flights. Key rules: a bare line
only becomes a team name once a player/hole row follows it (headings and
course lines never leak); the trailing parenthesized vs-par is the score,
falling back to a signed token, then the last number. The server prefers
block results over the generic table guess whenever ≥2 teams parse
(or the table path found nothing); the client uses `payload.teams`
directly. When neither parser reads the page, the response includes
`sample_lines` (first 80 page-text lines) for evidence-based fixes.

**Unknown Golf login contract (confirmed from doLogin() source, 2026-08-08).**
The login is formless: `<input id="idEmail">` / `<input id="idPassword">`
and a jQuery `doLogin()` that POSTs **form-encoded** to `/account.ukg`
with `{a:"1", userEmail, userPsswd, ac:"null"}` (`dataType:"json"` is the
RESPONSE type; the request body is form-encoded). Success returns JSON
with `urlRedirect`. `_js_login()` finds doLogin's source, parses its
`data:{…}` object (constants kept, #idEmail/#idPassword fields mapped),
posts that payload, and verifies via urlRedirect + a re-fetch past the
wall. `site_login()` returns rich `diag` (doLogin snippet, endpoints,
parsed template, per-attempt results) on failure for screenshot-driven
fixes.

**v2.219.0 — LOGIN WALL (root cause of every live-fetch failure).**
Kerry's diagnostics screenshot proved the event page serves Unknown
Golf's sign-in page ("Welcome back, player!") to anonymous fetches.
`site_login()` does a browser-equivalent form login (locates the
password form, keeps hidden/CSRF fields, same-host-only post) and
stores ONLY the session cookie in `twomantour_kv` (`ug_cookie`) — the
password is never persisted. `fetch_live()` sends the stored cookie
automatically; when the site expires it the wall is re-detected and
the UI's "Log in to Unknown Golf" button reappears. Route: POST
`/twomantour/api/login` (admin).

Also v2.219.0: the hole-row → card mapper is self-validating — layout
`[team HC] h1-9 OUT h10-18 IN [Total]` tried at each offset, accepted
only when OUT/IN/TOTAL match the summed hole scores. The card renders
as a typical scorecard (HOLE/SCORE rows per nine, gold OUT/IN/TOT,
TEAM HC + TOTAL · vs-par header strip).

v2.218.0: when the top-level page yields nothing, the server chases
same-host embedded sub-pages (iframes first, then scoring-looking
`.jsp` URLs; host-locked, max 4) and parses each until teams appear.
Persistent failures render an on-page "What the server saw" panel
(tried URLs, table count, sample lines) and flag a suspected login
wall — so diagnosis works from Kerry's screenshot, not guesses.

## Known limits / future

- The block parser is built from Kerry's mid-event screenshot; a Clear
  button resets a bad import instantly.
- Flight assignments are not persisted server-side and nothing feeds payouts
  — this is a decision aid Kerry reads from during flighting. If Two Man
  Tour ever needs money math in the Tracker, that's a new scope (rule 3b).
