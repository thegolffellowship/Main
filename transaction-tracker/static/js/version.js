window.TGF_VERSION = "2.232.0";
window.TGF_CHANGELOG = [
  {
    version: "2.232.0",
    date: "2026-08-12",
    changes: [
      "The championship's LOCKED payout schedule is on the GAMES tab (Kerry-ratified 2026-08-12: 'Lock those.'). New event_payout_schedules app setting (rules-as-data, keyed by event id) overlays the derived bucket games: a lock reallocates money INSIDE a bucket — the $10/hole skins cap frees $216 Sat / $126 Sun into Team Net and Closest to Pins — while the bucket purses stay derived from the live field, and every game now shows its payout lines ($240/$120 Team Net Sat, $58- and $48-per-hole CTPs, Ind Net 2 flights at $130/$78/$52, Ind Gross 4 flights with the $60 top-cut folded into Flight 1's $120/$60). A LOCKED banner marks the schedule of record so Robert can run the weekend off the tracker page, not a chat thread.",
    ],
  },
  {
    version: "2.231.1",
    date: "2026-08-12",
    changes: [
      "docs: championship weekend runbook (docs/claude/runbook-tgf-championship-2026-08-14.md) — pre-flight findings (empty Lost Pines course row 22819 pending the GG import; Kaleb's unnamed practice guest; Barstow/Jenkins missing tees), the verified post-relink purses (SAT $952 / SUN $802 / COMBINED $1,060), and the Thursday + game-day checklists.",
    ],
  },
  {
    version: "2.231.0",
    date: "2026-08-12",
    changes: [
      "Championship pre-flight catch: every purchase since the last deploy (Aug 8) was missing from the derived game pools. items.event_id was only backfilled at BOOT, so eleven Aug 9–10 championship orders — five of them full games-bundle buyers, four single-day games buyers — sat unlinked and _champ_roster_bundles (which filters on event_id) undercounted the SAT/SUN/COMBINED purses by roughly $150 a bucket, and the roster's YES|SAT|SUN|NO cells read those players as NO. Three fixes: the backfill is now callable (backfill_event_links) and runs after every scheduler inbox check, so a late add self-corrects the pools within minutes instead of at the next deploy; Add Player and Add Payment stamp event_id at insert; and this deploy's boot pass links the eleven stranded rows immediately.",
    ],
  },
  {
    version: "2.230.0",
    date: "2026-08-09",
    changes: [
      "Flight Board LOCKS (Kerry): two toggle buttons next to Payouts. 🔒 Flights freezes the flight lines — dragging is disabled, the flight-count/mode/reset controls grey out, and new pasted/refreshed scores won't re-flight (lines stay put, just clamped). 🔒 Payouts freezes the dollar amounts — it snapshots the current payouts so changing buy-in, pot, or rules no longer moves them, and clicking a payout to edit is blocked until you unlock. Both locks persist per event and are covered by undo/redo. Unlocking payouts recomputes live again.",
    ],
  },
  {
    version: "2.229.0",
    date: "2026-08-09",
    changes: [
      "Flight Board THRU column (Kerry): each team row now shows its progress — 'thru N' (holes scored) while a round is in progress, flipping to the actual GROSS TOTAL (bold, e.g. 69) once all 18 holes are in. Derived from the parsed scorecard (counts scored holes; shows card total when complete). The to-par score stays in its own column, so you see both gross total and vs-par at a glance.",
    ],
  },
  {
    version: "2.228.0",
    date: "2026-08-09",
    changes: [
      "Flight Board payout rounding reworked (Kerry): the last paid place in each flight now rounds DOWN to the nearest $20 (configurable $5–$50 in Rules), and each flight's leftover collects into a new REMAINING POT chip shown up top — it is NOT dumped onto 1st place. Middle places still round to the chosen increment ($50 default); 1st is a clean rounded number too. Payouts + remaining pot always sum to the total pot. Replaces the old 'last place absorbs remainder / 1st to $100' scheme (the 1st-to-$100 toggle is gone). Copy Flights and manual overrides respect the new model.",
    ],
  },
  {
    version: "2.227.0",
    date: "2026-08-09",
    changes: [
      "Flight Board — lockable PAID-TEAMS count for the pot (Kerry: 46 teams paid, only some have posted scores). New 'Paid teams' field: leave it blank to use the teams shown, or lock it to the full field (e.g. 46) so TOTAL POT = 46 × 2 × buy-in even while fewer teams are on the board. The header shows '46 paid teams (locked · 30 scored)', and the full pot is distributed across the current flights so payouts always sum to it; as more teams post scores it stays consistent. Undo/redo covers the lock.",
      "Undo/redo arms instantly: a change made within the history debounce window is now immediately undoable (the arrow enables the moment you change something, and undo/redo flush any pending snapshot first).",
    ],
  },
  {
    version: "2.226.0",
    date: "2026-08-09",
    changes: [
      "Flight Board UNDO/REDO (Kerry): ↶ ↷ arrows in the toolbar plus Ctrl/Cmd+Z and Ctrl+Shift+Z (or Ctrl+Y). A debounced history stack snapshots the whole board (teams, flight lines, flight count/mode, buy-in, pay %, all payout rules, manual payout edits, score column) after every committed change; undo/redo restore the state AND the toolbar/modal controls. Up to 120 steps; buttons disable at the ends.",
      "Flight Board scorecards are now an ACCORDION (Kerry): expanding one team's hole-by-hole card auto-collapses any other, so only one is open at a time.",
    ],
  },
  {
    version: "2.225.0",
    date: "2026-08-08",
    changes: [
      "Flight Board — EDITABLE PAYOUTS (Kerry): click any payout amount on the board to type a value; that place locks (cyan with a ● dot) and the other paid places redistribute the remaining pot by weight, so the flight pot stays exact. Multiple locks supported (if they exceed the pot they scale to fit). 'Clear manual payout edits' in the Rules modal, and any structural change (drag a flight line, change flight count/mode, reload teams) clears the edits since the places no longer map. Overrides persist per event otherwise.",
      "Flight Board — 1st ≥ 2nd ≥ 3rd is now always enforced (Kerry): payouts are ordered descending after all rounding/overrides (sum preserved, so each flight still equals its pot). This also fixes the earlier even-split + $100-rounding inversion. And places-paid now has a MINIMUM of 25% of each flight (Kerry) — the Pay-top-% control floors at 25%.",
    ],
  },
  {
    version: "2.224.0",
    date: "2026-08-08",
    changes: [
      "Flight Board — TOTAL POT header + full payout & flight rules (Kerry's spec). Top bar shows TOTAL POT (teams × 2 × buy-in). New Rules ⚙ modal: PAYOUTS — pot across flights Pro-rata/self-funded (default) or Even; split within flight Places (step-down) or Even; a Top-flight bonus slider that skims X% of the total pot off the top into Flight 1; rounding to a chosen increment (default $50) with 1st place to nearest $100 and the last paid place absorbing the remainder so each flight sums to its pot exactly (total always conserved via largest-remainder across flights). Payouts stay in the right-side per-row column.",
      "Flight Board — FLIGHT RULES. Tied scores now NEVER split across flights (always on): flight lines snap across equal-score blocks, and equal-spacing/auto all respect it. Two flighting modes: By count, or By stroke band (width default 4) + Max flights cap — bands run from the leader and the last flight absorbs the widest range, with no unnecessary flights added when the field is tight. New Lock-lower-flights toggle: dragging a line shifts the lines below it by the same size so you can move just the top flight and push the rest down intact. Known edge: Even-split + '1st→$100' on an odd pot can print 2nd above 1st; Places split (default) stays ordered.",
    ],
  },
  {
    version: "2.223.0",
    date: "2026-08-08",
    changes: [
      "Payouts moved to a RIGHT-SIDE COLUMN aligned per team row (Kerry: 'locked to the right side, not the bottom; payout rows align with the flight rows'). Each paying place shows its dollar amount on the right edge of that team's row (1st $133, 2nd $67, …), with 'POT $X · $ pays N' in the flight header. Replaces the bottom strip; still the step-down curve, whole-$ rounding conserves the pot, recomputes as flight lines drag, toggled by Payouts, in Copy Flights.",
    ],
  },
  {
    version: "2.222.0",
    date: "2026-08-08",
    changes: [
      "Payouts moved INLINE into each flight box (Kerry: 'I want it literally next to the flights as part of that window'). The right-side pane is gone; each flight now shows a payout strip directly under its teams — 'Payouts · top N of M · Pot $X' with the paid places and amounts — so it's visually part of the flight and moves with the flight line. Pay-top-% and Whole-$ controls now live in the top toolbar next to Buy-in; the Payouts button toggles the strips; all persist per event, and Copy Flights still includes them.",
      "Live-feed fix — stop pulling the wrong list (Kerry saw golf-course names, not teams). The JSON leaderboard reader now REQUIRES records to carry a score/position field, so a course dropdown or player list (names only) is rejected; only a real scored leaderboard is accepted (early-round rows with the score keys present but values still empty are still recognized). Feed discovery also skips course/search/roster/autocomplete *.ukg endpoints outright.",
    ],
  },
  {
    version: "2.221.0",
    date: "2026-08-08",
    changes: [
      "Flight Board live DATA FEED discovery (Kerry's probe screenshot pinpointed it): the standings come from Unknown Golf's *.ukg JSON endpoints (leaderboard.ukg / gameResult.ukg), which reject a bare call ('Your request is not recognized') because they need the event/tour ids + an action code. The server now opens the score-display pages (tvLeaderboard.jsp, the event page), finds the AJAX call their scripts make to a .ukg endpoint (balanced-brace JS parse of $.ajax/$.post/$.get), resolves its data object against the real ids (eventId/tourId filled, constants kept, unknown JS vars dropped), replays it with the session cookie, and parses the JSON leaderboard. If it still can't read scores, the diagnostics now include each replayed endpoint, the exact params sent, and a response sample.",
      "Payouts pane confirmed locked to the flight lines — the pane recomputes from the same flight boundaries as the board, so dragging a flight line moves the pot, paid-place count, and named payees together (already the behavior; verified).",
    ],
  },
  {
    version: "2.220.0",
    date: "2026-08-08",
    changes: [
      "Flight Board POTENTIAL PAYOUTS pane (Kerry): a right-side pane (collapses below the board on mobile) that splits each flight's pot among its top finishers. 'Pay top N% of teams' (default 25%, min 1 place) with a standard step-down curve (weights n,n-1,…,1) so 1st > 2nd > 3rd; whole-dollar rounding conserves the pot exactly (remainder lands on 1st). Recomputes as flight lines drag and buy-in changes; included in Copy Flights. Toggle with the Payouts button; the % and pane state persist per event.",
      "Flight Board live fetch — the login now WORKS (server reads the authenticated event page), but the standings load from a separate JS feed. The server now hunts that feed: it scans the authenticated page AND its external script files for same-host scoring URLs, tries Unknown Golf's known display/leaderboard endpoints (tvLeaderboard, eventLeaderboard(Standings), result summary, *.ukg), and parses either HTML blocks/tables OR a JSON leaderboard. When it still can't read scores, the diagnostics panel now lists every data-endpoint it probed with a content sample — so the exact feed URL/shape is one screenshot away.",
    ],
  },
  {
    version: "2.219.3",
    date: "2026-08-08",
    changes: [
      "UG login round 4 — nailed the exact contract from Kerry's doLogin() dump: POST /account.ukg (form-encoded) with a=1, userEmail, userPsswd, ac=null. The replay failed before because (a) it dropped the constant a/ac fields the endpoint requires and (b) userPsswd didn't match the old pass-key heuristic. Now the server parses doLogin's jQuery `data:{…}` object literally — keeping every constant and mapping the fields that reference #idEmail / #idPassword — and posts that full payload. Also fixed a request-encoding trap: jQuery's `dataType:'json'` describes the RESPONSE, so the body is sent form-encoded (only JSON.stringify / an explicit JSON contentType switches the request to JSON). Success is confirmed by the JSON urlRedirect and a post-login re-fetch past the wall before the session cookie is stored.",
    ],
  },
  {
    version: "2.219.2",
    date: "2026-08-08",
    changes: [
      "UG login round 3 (Kerry's diagnostics: id-only inputs idEmail/idPassword, form_count 0, a JS doLogin() submits) — the server now REPLAYS doLogin(): it locates the function's source (inline scripts, then same-host external scripts), extracts the endpoint URL (xhr.open/fetch/url:/action:) and the parameter names it sends ('email='+… style and JSON keys), posts the credentials the same way (form-encoded or JSON), and verifies success by re-fetching the event page past the login wall before storing the session cookie. On failure the diagnostics now include the doLogin source snippet, endpoints, params, and per-attempt HTTP results — the next fix reads the exact JS off Kerry's screenshot.",
    ],
  },
  {
    version: "2.219.1",
    date: "2026-08-08",
    changes: [
      "Unknown Golf login fix (Kerry hit 'Couldn't find the login form'): the event page draws its login with JavaScript, so its raw HTML has no form. site_login now walks a candidate list — entry page, the platform's real login URLs (/platform/login.jsp and /platform/signin/, found via public site recon), plus any same-host login links it encounters (cap 6) — and posts the first genuine password form it finds. When every page is a JS shell, the response carries per-page diagnostics (form counts, raw <input> tags, auth-looking URLs) that the login modal renders into the on-page panel, so the next fix reads evidence off Kerry's screenshot.",
    ],
  },
  {
    version: "2.219.0",
    date: "2026-08-08",
    changes: [
      "MYSTERY SOLVED — the Flight Board's live fetch was blocked by a LOGIN WALL (Kerry's diagnostics screenshot showed the server receiving Unknown Golf's 'Welcome back, player!' sign-in page, not scores). New 'Log in to Unknown Golf' flow: the button appears when the wall is detected, Kerry enters his UG email/password once, the SERVER performs the same form login a browser would (finds the password form, carries hidden/CSRF fields, posts same-host only) and stores ONLY the resulting session cookie in twomantour_kv — the password is never persisted. Every subsequent fetch (Refresh, Auto-60s) rides that cookie until the site expires it, at which point the wall is re-detected and the button reappears.",
      "Typical-looking expandable scorecard (Kerry request): proper HOLE/SCORE rows for each nine with aligned columns, gold OUT/IN/TOT cells, dimmed dashes for unplayed holes, and a header strip showing TEAM HC and TOTAL · vs-par. Under the hood the hole-row mapper is now SELF-VALIDATING: the row layout ([team HC] holes 1-9, OUT, holes 10-18, IN, [Total]) is tried at each offset and only accepted when the arithmetic checks (OUT = sum of scored front holes, IN = sum of back, TOTAL = OUT+IN) — this is what fixed the raw-text fallback Kerry screenshotted, whose rows carry a leading team-HC column the old fixed-width mapper couldn't place.",
    ],
  },
  {
    version: "2.218.0",
    date: "2026-08-08",
    changes: [
      "Flight Board live fetch: SUBPAGE CHASING + visible diagnostics (Kerry: 'still not grabbing from the page live'). JSP live-scoring pages often render the actual leaderboard in an embedded iframe/secondary .jsp the browser loads but a top-level server fetch never sees — the server now scans the event page for same-host scoring-looking sub-URLs (iframes first, then *.jsp mentioning score/leader/live/card/result/board, host-locked, capped at 4) and parses each until teams appear. When every attempt still fails, the page shows a 'What the server saw' panel — URLs tried, table count, first 80 text lines of the page — so the next fix works from a screenshot of evidence, and a heuristic calls out when the server is being served a LOGIN page instead of scores (the likely cause if Kerry is logged in on his browser but the server isn't).",
    ],
  },
  {
    version: "2.217.0",
    date: "2026-08-08",
    changes: [
      "Flight Board: TAG + SAVE EVENTS server-side (Kerry: 'Is it built to persist? Can I tag and save events?'). Save Event snapshots the whole board — teams with players and hole-by-hole cards, flight lines, flight count, buy-in — under a tag into a new isolated twomantour_saves table (Tracker SQLite on the Railway persistent volume; deliberately zero FKs/joins to any TGF table). The Saved button lists every snapshot (tag, team count, timestamp) with one-tap Load and Delete; loading restores the full board including pots. All endpoints admin-only. Until now persistence was browser-localStorage only (lines/buy-in per event on one device); saves now survive devices, browsers, and redeploys.",
    ],
  },
  {
    version: "2.216.0",
    date: "2026-08-08",
    changes: [
      "Flight Board: tap any team to EXPAND ITS 18-HOLE SCORECARD (Kerry, mid-event) — the parsers now map the 22-column hole row (holes 1-9, F, 10-18, B, Total, vs-Par) into a card, rendered as front/back nine tables with OUT / IN / TOT / PAR, chevron on every expandable row, expansion state survives refreshes and line drags. Rows whose hole row doesn't match the 22-column shape still expand to the raw line, so nothing is ever hidden.",
      "Flight Board: BUY-IN $/PLAYER input → live POT TOTALS per flight (Kerry, mid-event). Enter the per-player buy-in and every flight header shows its pot (teams × 2 players × buy-in) in green; pots recompute instantly as flight lines drag and are included in Copy Flights ('FLIGHT 1 — POT $120'). Buy-in persists per event in localStorage like the flight lines.",
    ],
  },
  {
    version: "2.215.0",
    date: "2026-08-08",
    changes: [
      "Flight Board shows the PLAYERS on every team (Kerry, mid-event): the scorecard-block parsers (server fetch + paste) already walked past each team's player lines — now they keep them, so every row shows the team name with its two players underneath in dim text ('Team #44 / Jerod Durst · Kwinton Reno'). Copy Flights includes them too, so the texted flight list names actual people, not just Team #NN.",
    ],
  },
  {
    version: "2.214.0",
    date: "2026-08-08",
    changes: [
      "Two Man Tour Flight Board learns the REAL unknowngolf page format (Kerry's live screenshot, mid-event): the page isn't a name+score leaderboard table — it renders per-team SCORECARD BLOCKS (team name / players with handicaps in parens / course / hole-by-hole row ending in the vs-par total like '(-2)' / 'Unofficial Score'). Both the server fetch AND the Paste-scores importer now parse that block format into a clean team list, so Kerry's drag-copy of the whole page produces exactly the field, not 42 junk rows. A bare line only becomes a team name once a player or hole row follows it, so page headings and course lines never leak in; the vs-par value in trailing parens is the ranking score, with signed/last-number fallbacks.",
      "New CLEAR button on the Flight Board (Kerry request) — wipes the board, flight lines, pasted text, and auto-refresh in one tap so a bad paste never has to be picked apart by hand. Plus diagnostics: when the live fetch can't read the page, the API response now carries the first 80 text lines of what it actually saw (admin-only), so the next parser fix works from evidence instead of guesses.",
    ],
  },
  {
    version: "2.213.0",
    date: "2026-08-08",
    changes: [
      "Admin-only TWO MAN TOUR button in the Tracker nav (Kerry, 2026-08-08) — a gold pill (Two Man Tour brand #d4af37, deliberately NOT TGF orange, so it reads as a doorway out of the Tracker) linking straight to the /twomantour Flight Board. Desktop nav + mobile drawer; rides the existing admin-nav gating in auth.js, so only an admin session ever sees it.",
    ],
  },
  {
    version: "2.212.0",
    date: "2026-08-08",
    changes: [
      "TWO MAN TOUR FLIGHT BOARD (Kerry, 2026-08-08, for tonight's event) — a completely separate, admin-only page at /twomantour with its own Two Man Tour branding (no TGF nav, no TGF data). It proxies the league.unknowngolf.com live-scoring page server-side (new twomantour.py — stdlib HTML table extractor that scores every table on the page and picks the one that looks like a leaderboard; host-locked to league.unknowngolf.com, numeric-id validated), ranks teams low-to-high, and gives Kerry a Flights count with draggable gold flight lines that start at equal spacing across the field. Drag a line to move the flight break; flight headers show live team counts and score ranges; Copy Flights puts the final list on the clipboard.",
      "Resilience for event night: a Score column picker (auto-prefers NET, falls back TOTAL/SCORE then GROSS; position/thru columns are filtered out of the candidates), a Paste Scores fallback that parses a leaderboard copied straight off the live page (positions and thru markers stripped automatically), Auto-60s refresh, and per-event localStorage persistence of flight count + line positions. The page shell is public but every data call is @require_role('admin'); the page shows its own PIN gate, so nothing TGF-branded appears in the flow.",
    ],
  },
  {
    version: "2.211.1",
    date: "2026-08-07",
    changes: [
      "chore: correct the ruling date in the champ_subgame_optouts docstring (Kerry's Carlos Zapata directive came 2026-08-07, not 08-08).",
    ],
  },
  {
    version: "2.211.0",
    date: "2026-08-07",
    changes: [
      "The championship roster speaks DAYS, not net/gross (Kerry-ratified 2026-08-07, verbatim: 'GAMES tabs NET | GROSS | NONE should show YES | SAT | SUN | NO'). On an event with bucket accounts the games tabs are now YES (both days, $100 bundle) | SAT | SUN | NO with counts, the GAMES column shows the same value, and both are DERIVED server-side from the matched package plus the single-day day assignment (dial or the order's WHICH DAYS? answer) — the same event-owns-its-vocabulary shape as the hole tabs. A single-day games buyer with no day yet shows an amber DAY? tab instead of being silently miscounted. Replacement is per-event: every normal event keeps NET | GROSS | NONE untouched. Desktop and mobile.",
      "Per-game pool opt-outs (Kerry, the Carlos Zapata one-off: credit the handicap games — Team Net both days + Individual Net — while staying in Skins, CTPs and Individual Gross). New champ_subgame_optouts dial: bucket purses drop by exactly the opted-out rates (real money, matching the registration credit) and ONLY the named games lose heads — every other pot keeps the full field, with an 'N opted out' note on the affected game. The scoring-partial-credit path moves the money; this dial makes the derived pot math agree with it.",
    ],
  },
  {
    version: "2.210.1",
    date: "2026-08-07",
    changes: [
      "scoring-partial-credit bridge command — the probe_golf_genius scoring-* bridge exists precisely because MCP client sessions freeze their tool list at session start, and the session that shipped partial_credit_transaction could not itself call it. The bridge twin takes the same JSON (item_id, amount, optional new_holes / package_index / note), is credit-only like the tool, and audits to agent_action_log the same way. First use: Jeff Young's Kerry-ratified $105 practice-round drop.",
    ],
  },
  {
    version: "2.210.0",
    date: "2026-08-07",
    changes: [
      "Package Downgrade refunds (Kerry-ratified 2026-08-07 — carry-forward #2 from the handoff). On a package-config event the Credit/Partial Refund modal replaces the hardcoded net/gross component list with a Package Downgrade picker built from the EVENT's own ladder: refund = current package price − target package price, straight off Kerry's entered prices, never derived from parts. Submitting flips the registration's holes to the target package's count and re-pins the assignment, so the roster badge, Holes column, and due math all follow the downgrade. Side games are deliberately untouched — whether a downgrade that drops a games-carrying day should also adjust the bundle is still an open Kerry question. First real case: Jeff Young dropping the Friday practice round, Full Weekend → Both Days + Side Games – Member, $105 credit, 54 → 36 holes.",
      "The partial-refund new_holes validator accepted only 9 and 18 (app.py) — it now accepts 36 and 54, the blocker that would have rejected any multi-day downgrade.",
      "The partial-refund implementation moved out of app.py into apply_partial_refund() in database.py — one function now serves both the route and the new MCP tool, so the two surfaces cannot drift.",
      "New MCP tool partial_credit_transaction (70 tools now; the destructive set grows to seven): a partial CREDIT against a registration, credit-only by design — outbound partial refunds stay UI-only. Takes amount, optional new holes, optional package re-pin index; returns a preview until confirm=true and audits every call per the v2.208.0 guardrail.",
    ],
  },
  {
    version: "2.209.0",
    date: "2026-08-07",
    changes: [
      "Add Player speaks the event's language (task #34, carry-forward #1 from the 2026-08-07 handoff). On an event with package configs the modal now leads with a Package dropdown — picking one sets holes, side games and (in Paid Separately mode) the price together, and the saved registration is PINNED to that package so the roster badge, the package-derived Holes column, and the due math all read from it, comp rows included. This is the modal that let Robert Straiton be comped in as 18 holes on a both-days entry: nothing on the old flat Holes list said 'both days'. Manual fields stay live as the fallback, and events without packages see no change.",
      "New MCP tool assign_event_package — the programmatic twin of the roster's package dropdown. Called with just an event_id it lists the packages and current pins (read-only preview); with item_id + package_index it pins, with clear=true it unpins. Only the assignments map is ever touched — package labels and prices are Kerry-entered and this tool cannot modify them. Every call is audited (v2.208.0 guardrail). Until now pinning was UI-only, which is why the previous session could fix Straiton's hole count but not his badge.",
    ],
  },
  {
    version: "2.208.1",
    date: "2026-08-07",
    changes: [
      "A COMP row can be assigned a package (Kerry, on Robert Straiton: 'Add a BOTH DAYS + SIDE GAMES - MEMBER badge'). The package picker only rendered for rows that matched a package by price or were credit transfers — a $0.00 (comp) row matched nothing and got no control at all, so there was no way to say what a comped player actually bought. Any unmatched ACTIVE row on a package event now gets the '— assign package —' dropdown.",
      "A comp is never invoiced. Pinning a comp to the $420 Both Days + Side Games package would previously have rendered a '$320.00 due' badge against it, because the balance-due math only saw $100 of +PAY covering a $420 package. A comp owes nothing by definition, so the due badge is suppressed on comp rows.",
    ],
  },
  {
    version: "2.208.0",
    date: "2026-08-07",
    changes: [
      "MCP write guardrail (Kerry-ratified 2026-08-07). Two gaps closed on the agent-facing write surface. First, NOTHING an agent wrote through MCP was ever recorded — the agent_action_log table and log_agent_action() both existed and mcp_server.py called them zero times, so every agent change to live financial data was invisible after the fact. Every write tool now logs what it did, visible through get_agent_action_log. Second, the destructive tools fired on a single call with no preview: delete_transaction's own docstring says 'cannot be undone'. delete_transaction, delete_existing_event, credit_transaction, transfer_transaction, undo_credit_or_transfer and run_autofix now return a preview of the exact row and the exact effect, and change nothing until a second call passes confirm=true. Reads are untouched, and the non-destructive writes (update_transaction, add_player, create/update event, the syncs) run as before but are now logged.",
    ],
  },
  {
    version: "2.207.2",
    date: "2026-08-07",
    changes: [
      "Package hole counts count ROUNDS, not phrases. Read against the championship's real 14-package list (not the three visible on one screen), the previous rule got 'Both Days + Practice' ($425 member / $450 guest) wrong — it matched 'both days' and stopped at 36, but a practice round is another 18 on top of the tournament days, so that package is 54. The label now resolves to a round count: both days = 2, one day = 1, '+ practice' adds one, and 'Full Weekend' / 'All Three' short-circuit to 54 before the count (they contain 'Both Days' themselves). All 14 live packages now resolve correctly, including 'Practice Round Only' at 18. Verified against the live roster: 18 (2) | 36 (16) | 54 (6), with Callaway's and Mazanec's credit-transfer rows reading 36 off their pinned Both Days + Side Games assignments.",
    ],
  },
  {
    version: "2.207.1",
    date: "2026-08-07",
    changes: [
      "Sorting the Holes column does nothing (Kerry). The sort compared items.holes, which on a package event is 18 for every row — every pair tied, so the stable sort left the roster in whatever order it was already in and only the header arrow moved. It now sorts the value the column actually SHOWS (the package-derived count), so 18 / 36 / 54 order correctly in both directions with the hole-less RSVP rows last.",
      "A hole tab was showing RSVPs that have no hole count (Kerry). The GG RSVP rows are appended AFTER the hole filter runs, gated only on the NET/GROSS/NONE filter, so they came straight back in — 36 would show the 36-hole players plus everyone who had merely RSVP'd. A hole tab now excludes them outright: an RSVP is not a purchase, it belongs under no hole tab. rowHoles() also refuses to read a hole count off a package for any RSVP row, so a $0 package can't match a blank price and file an RSVP under a tab.",
    ],
  },
  {
    version: "2.207.0",
    date: "2026-08-07",
    changes: [
      "The Holes column reads the PACKAGE, not the order (Kerry, on the 2026 TGF CHAMPIONSHIP roster: v2.206.0 gave the tabs somewhere to put 36 and 54, but every row still said 18 because that is what the order carries — a championship sells DAYS, and one round is one round no matter how many you bought). A registration matched to a package now shows the holes that package buys: BOTH DAYS + SIDE GAMES reads 36, FULL WEEKEND (BOTH DAYS + PRACTICE + GAMES) reads 54, ONE DAY + SIDE GAMES reads 18. The cell carries a tooltip naming the package it came from. Rows with no package — every normal event — keep showing the order's own value exactly as before.",
      "Each package row in the Event Creator gets a Holes selector (Auto / 9 / 18 / 36 / 54). On Auto the count is read off the label: 'full weekend' / 'all three' / 'three day' → 54, 'both days' / 'two day' → 36, 'one day' / 'single day' → 18. Longest claim wins, so 'FULL WEEKEND (BOTH DAYS + PRACTICE + GAMES)' reads 54 rather than being caught by the BOTH DAYS inside it. Set the selector on any package whose label doesn't say, or to overrule what was read.",
      "Everything hole-shaped on the roster now agrees with what the column shows: the event-specific tabs and their counts, the tab filter, the mobile card badge and its Holes detail row, and the HCP column's 18-only rule (in the sort as well as the display).",
    ],
  },
  {
    version: "2.206.0",
    date: "2026-08-07",
    changes: [
      "Roster hole tabs are EVENT SPECIFIC (Kerry, on the 2026 TGF CHAMPIONSHIP roster: 'can we add to the Holes column 36 and 54 and tabs/counts along with the 9|18? Make the tabs event specific'): the fixed 9|18 pair is gone. The tab group is now built from the hole counts the event's live roster actually holds, in play order, each with its count — 18|36|54 on a multi-day championship, 9|18 on a combo Tuesday, a single 18 tab on a standard 18-hole event (no more '9 0' on every event that never sold a 9). Credited/refunded/transferred/WD rows and +PAY children are excluded from the counts, exactly as before; RSVP-only rows carry no hole count and are counted under no tab. A filter left on a hole count that no longer exists on the roster clears itself instead of showing an empty table. Same treatment on desktop and mobile.",
      "36 and 54 are first-class hole counts. Add Player offers '36 (two days)' and '54 (three days)' alongside 9 and 18, the Holes column sorts numerically (9 used to sort above 54 as a string, and rows with no hole count now sort last in both directions), and the HCP column's 18-only rule counts 36 and 54 as 18-hole play — a 36/54 roster was previously falling back to the 9-hole net index because nobody on it was literally '18'.",
      "Event PACKAGES can no longer be wiped by one click. Save Packages on an empty editor used to delete the event's whole package config with a cheerful 'Saved 0 packages ✓' — and the roster's purchase chips and exact '$X due' badges are computed from that list, so they vanished with it. An empty save over an existing config now asks first, and a row with a name but no price (silently dropped on collect) blocks the save with a message instead of quietly deleting that package.",
    ],
  },
  {
    version: "2.205.1",
    date: "2026-08-06",
    changes: [
      "Players Cup flights are LOCKED (Kerry: handicap updates land after Day 1 of the TGF Championship, 'but I don't want anyone to move flights in The Players Cup because of it'): the first board read after this deploy stamps every player's current flight into the flight_lock_players_cup_gross setting, and every read after that serves the locked flight. Handicap indexes keep updating on the board — the HCP column moves, the flight never does. Players appearing on the board for the first time lock at first sight; deleting the dial re-locks everyone from then-current handicaps. Everything downstream (chase-email flight gate, Rob's 1st-in-flight rank, flight pots) reads the locked assignment automatically.",
    ],
  },
  {
    version: "2.205.0",
    date: "2026-08-06",
    changes: [
      "Queue window tightened (Kerry: 'Move these 16 or more from the Fellowship Cup to the Normal tab'): the points window is now the ONE gate — a player more than 15 off the lead on his best path goes to Normal even when his Lone Star Cup seat gap looks close. The seat-line criterion had been independently qualifying players sitting 15.5–19 off the Fellowship lead (Ingram, White, Horton, Decker, Moore, Fieber, Lee, Romero, Cannon, Reyes…) into Push Entry/Defend; the seat gap stays visible on every row but no longer changes the tab.",
    ],
  },
  {
    version: "2.204.7",
    date: "2026-08-06",
    changes: [
      "Players Cup pitch cards get a sign-up link (Kerry, on Rob Callaway's 1st-in-flight card: 'there should be a link for signing up for The Players Cup. For him'): an orange SIGN UP FOR THE PLAYERS CUP · $50 bar renders above the CLICK FOR STANDINGS bar, linking to the store buy-in URL — only on cards pitching a player who isn't in the PC yet (the secured trophy-and-money card and the state-C flight-money card). Players already bought in never see it.",
    ],
  },
  {
    version: "2.204.6",
    date: "2026-08-06",
    changes: [
      "Secured Players Cup card ranks the player WITHIN his flight (Kerry, Rob Callaway: 'Keep the rank for his flight. That's important! He'd be in 1st Place!'): 'you sit 1st in 3rd Flight with a points reset of 93, and The Players Cup title and the flight money are still up for grabs at the Championship.' The flight rank uses the same everyone-in flight pool as the from-winning number; chapter place remains the fallback when no flight is assigned.",
    ],
  },
  {
    version: "2.204.5",
    date: "2026-08-06",
    changes: [
      "Secured Players Cup card names the player's flight (Kerry, Rob Callaway): 'The Players Cup title and the 1st Flight money are still up for grabs at the Championship' — the flight rides the money, not the rank, because the 'you sit 6th' number is the chapter-board place, not a flight-scoped one. Falls back to 'its purse' when no flight is assigned.",
    ],
  },
  {
    version: "2.204.4",
    date: "2026-08-06",
    changes: [
      "The 'One thing's for sure' closer now hides for EVERY signed-up player, secured seats included (Kerry, Robert Straiton: 'for those that are signed up for everything, they don't need the One thing's for sure line'). v2.204.3 hid it for regular signed-up renders but a secured signed-up player (Straiton: NET Champion captain, registered, in the cups) still got the secured 'None of it happens if you don't tee it up' version — an ask to play aimed at someone already playing. The hide now runs before the secured swap; a secured player NOT yet signed up (Luke Youngs) keeps the secured closer, since for him it IS the pitch.",
    ],
  },
  {
    version: "2.204.3",
    date: "2026-08-06",
    changes: [
      "All-in players read right (Kerry, Gus Vasquez: signed up + in the Fellowship Cup): the 'One thing's for sure — if you don't play, there's no chance to qualify' paragraph is hidden for every signed-up player (it's false — they're playing; secured renders already carry their own closer), and the otherwise-suppressed Players Cup slot comes back as a flight-money incentive for state-C players not yet in the PC: 'Not in The Players Cup yet — and there's flight money in it: buy in and race 2nd Flight for The Players Cup purse. Your 96 points reset is already on the board.' No seat talk, no weekend talk — just the flight fight.",
    ],
  },
  {
    version: "2.204.2",
    date: "2026-08-06",
    changes: [
      "1st-Flight gate on the Players Cup path (Kerry: 'Nobody below 1st Flight should have The Players Cup as the way in. Like Lance Rohrmann or John White.'): the chase email's auto path rule only leads with the gross path for 1st Flight players; below it the second-road Players Cup card is suppressed regardless of gap, and the $50 Players Cup buy-in card's caption sells the flight money ('Race your flight for the Players Cup money') instead of the seat line. The chase_path_overrides dial still forces either path explicitly per player.",
      "Secured-seat second-road card (Kerry follow-up on Luke Youngs: 'the Players Cup block also needs to support the money and cup incentive... not the Lone Star Cup weekend'): for a locked-seat player, whichever second cup card renders drops the 'second road to the Lone Star Cup weekend' pitch for 'Your seat's already locked — this one's about the trophy and the money', naming the cup's title and purse. Secured players keep the card even below 1st Flight — for them it's a money pitch, not a way-in pitch.",
    ],
  },
  {
    version: "2.204.1",
    date: "2026-08-06",
    changes: [
      "SECURED-seat chase variant (Kerry, Luke Youngs: Austin's Match Play champion holds a LOCKED Lone Star Cup seat but isn't signed up for the Championship or the cups — 'There's money and the Cups on the line'): when the LSC projection marks a player's seat status=secured, the email stops selling the seat. Navy block reads LOCKED / YOUR SEAT ON AUSTIN'S LONE STAR CUP TEAM — SECURED; the lead paragraph says the seat is locked (named by how it was earned, e.g. 2026 Austin Match Play Champion) and pivots to the Cup title + Championship money with the points-from-winning number; the qualify-or-miss-out closer becomes 'the seat is yours, but the trophies and the money still have to be won'; the CTA head becomes YOUR SEAT IS LOCKED — TWO STEPS (or ONE STEP) TO GET IN ON THE MONEY; subject: 'your Lone Star Cup seat is locked. The Cup itself isn't.' RSVP'd-not-paid acknowledgment outranks the secured CTA head when both apply.",
    ],
  },
  {
    version: "2.204.0",
    date: "2026-08-06",
    changes: [
      "RSVP'd-but-not-paid is its own email state (Kerry, Mike Marques case): the champ-signup check no longer lumps YES RSVPs (or their rsvp_only placeholder rows) in with registration purchases. A player who RSVP'd but hasn't paid now gets 'You're RSVP'd for the TGF Championship. Two steps left: 1. Sign up for the TGF Championship 2. Get in on the Cup races' — or the one-step version if they already hold a cup buy-in. Paid registrations keep the 'You're signed up' render.",
      "Command Center TGF CHAMP column shows the middle tier: amber '◐ RSVP · not paid' between green ✓ IN (paid) and red ✗ Not signed up, so the queue tells you who needs the payment chased, not just the weekend sold. The retired R5 builder's weekend pitch also now keys off PAID registrations only.",
    ],
  },
  {
    version: "2.203.2",
    date: "2026-08-06",
    changes: [
      "Command Center says WHICH cup (Kerry: 'I can't tell which cup the stat columns apply to'): OFF LEAD and SEAT LINE are the player's best number across the two cup boards — and could silently mix sources on one row. Each value now carries a small FC/PC tag naming its board, hovering either cell shows the full both-cups breakdown (off-lead + seat gap + bought-in per cup), and the CUP column's single checkmark becomes per-cup FC/PC chips (green = bought in, gray = not).",
    ],
  },
  {
    version: "2.203.1",
    date: "2026-08-06",
    changes: [
      "HOW IT WORKS buttons left-justify; badges go right (Kerry). Points-race header: the pill now sits beside the race title with the Regular Season phase chip pushed to the right edge (Refresh from Golf Genius rides far right for managers). LSC tab: pill left, PROJECTED ROSTERS chip right. Legacy Match Play row flips from right- to left-justified (admin preview link moves right); Handicaps' pill leaves the right edge to sit after the tab filters. The mpv2 Match Play row was already left-justified.",
    ],
  },
  {
    version: "2.203.0",
    date: "2026-08-06",
    changes: [
      "EXPAND ARROW standard (Kerry): every expand/collapse indicator on the member-facing pages is now the same solid TGF-orange triangle — one glyph (▶ closed, ▼ or a 90° rotation when open), one 14px size, defined once as .tgf-exp in dashboard.css. Converted: Spotlight recent-winnings event rows, Handicaps table expand buttons + mobile-card and scorecard-date chevrons (were slate gray and three different sizes), the Leaderboard's Pot & Details fold chip, Match Play row accordions (were gray ›), and every points-race drill-down chevron in points-render.js including the live hole-by-hole and Points Not Counted banners. Restyle arrows in dashboard.css only — never per page.",
    ],
  },
  {
    version: "2.202.0",
    date: "2026-08-06",
    changes: [
      "Email open/click tracking is LIVE (Kerry: 'Build the email tracking'). Every chase-email send now carries a per-send token: a 1x1 pixel (/t/o/<token>.gif) records opens and every http(s) link is rewritten through /t/c/<token>?u=... which records the click and 302s to the real destination — allowlisted hosts only (tracker + thegolffellowship.com), so the redirect can never be aimed elsewhere; mailto (unsubscribe) links stay untouched. New tables email_sends (per-send aggregates: opened_at/open_count/clicked_at/click_count, customer_id FK per rule 6) and email_send_events (raw beacon stream with user-agent), created lazily. Test sends to the recap inbox are flagged is_test so Kerry's own opens never pollute the member signal.",
      "Snapshot Command Center shows the result: green OPENED and orange CLICKED chips (with first-open/first-click timestamps and ×N counts) join the mark chip on each queue row, from the latest REAL send per player. Caveat shown by design: opens are a floor — Apple/Gmail image proxies can prefetch the pixel and image-blocking clients never report one; clicks are the hard signal.",
    ],
  },
  {
    version: "2.201.37",
    date: "2026-08-06",
    changes: [
      "LSC tab uses the full desktop width (Kerry: 'We're not using the full width of the standard 1280 page for desktop. I'd like to.'): the 720px caps on the navy banner, intro, legend, and footnote are gone, so the whole tab spans the standard work column (1080px member / 1280px manager-admin) like the team-card grid already did.",
      "The Lone Star Cup gets a HOW IT WORKS button (Kerry) next to the PROJECTED ROSTERS chip, on the same modal chrome as the races: THE WEEKEND schedule (Fri Oct 9 Practice Round · Sat Oct 10 AM Fourball / PM Foursomes · Sun Oct 11 Singles), the How-You-Qualify 12-seat breakdown (moved into the modal from the inline box, which is retired), and a Seats & Alternates explainer. The venue chip follows the lsc_event_info dial.",
    ],
  },
  {
    version: "2.201.36",
    date: "2026-08-06",
    changes: [
      "The LSC tab's navy banner becomes the section header (Kerry): CD's star-on-trophy mark + 'The Lone Star Cup' title live inside the banner with the date and venue (3px orange top rule, matching the email's LSC card), and the PROJECTED ROSTERS chip moves below it. The separate plain-text title row is gone.",
    ],
  },
  {
    version: "2.201.35",
    date: "2026-08-06",
    changes: [
      "SEE YOUR FULL SPOTLIGHT renders as a true pill (Kerry): the border-radius sat on a td inside a border-collapse table, which email clients render square — the border + radius now live on the link itself, so the button rounds like the orange sign-up pill.",
    ],
  },
  {
    version: "2.201.34",
    date: "2026-08-06",
    changes: [
      "Hybrid-state ruling (Kerry, closing #312 fix 3): a player already in a cup but not registered gets ONE STEP TO GET IN with the sign-up button and NOTHING else — no buy-in cards ('If it's actually 2 steps that we're offering then say two steps... What he needs to do most is sign up... so I'd say just ONE Thing'). The other cup's story stays in the second-road standings card above as information, not an ask.",
    ],
  },
  {
    version: "2.201.33",
    date: "2026-08-06",
    changes: [
      "Design-claude R6 addendum applied (#311/#312, Kerry-ratified): the payoff star is a true five-point Texas star (new star-texas-white asset), the LSC gets its own STAR-ON-TROPHY mark (trophy-star-white, 32px), and the email's LSC details card adopts the production A3 markup — navy with 3px orange top rule, icon column, eyebrow/date/venue, deep-link bar (whole card tappable; CLICK strip kept at 10px per Kerry's block-text ruling). Fellowship second-path card switches to the plain black outline trophy; inside-the-line gross phrase now reads 'via your gross path' (was 'off'). The hybrid one-step/two-step question (#312 fix 3) awaits Kerry's pick.",
    ],
  },
  {
    version: "2.201.32",
    date: "2026-08-06",
    changes: [
      "LSC seat strings substitute the chapter name for 'City' everywhere (Kerry): '2026 Austin NET Champion' / '2026 San Antonio Match Play Champion', the AUSTIN/SAN ANTONIO MATCH PLAY seat labels, and the alternates-pool context lines ('9th of 85 in San Antonio NET'). Co-champion variants follow the same pattern.",
    ],
  },
  {
    version: "2.201.31",
    date: "2026-08-06",
    changes: [
      "LSC lock icon is now a solid padlock (inline SVG) tinted in the TEAM color — burnt orange on Team AUSTIN rows, steel on Team SAN ANTONIO — at 1.5× the old emoji size (Kerry, with reference image; the emoji couldn't be tinted). New legend under the rosters explains both badges: Lock = seat SECURED (champion declared / result final), Pool = seat projected to fill from the Alternates Pool.",
    ],
  },
  {
    version: "2.201.30",
    date: "2026-08-06",
    changes: [
      "Chase email P1 (Kerry): 'The rest is decided at the TGF Championship, Aug 15–16 at Lost Pines' is now bold and names the venue.",
    ],
  },
  {
    version: "2.201.29",
    date: "2026-08-06",
    changes: [
      "LSC secured seats get fanfare instead of a chip (Kerry): the amber SECURED pill is gone — a locked player's row now fills with a bold chapter-color band (deep burnt-orange tint for Team AUSTIN, steel for Team SAN ANTONIO), the name goes heavy in the chapter's deep color, and a lock icon sits at the far right of the row. Team cards are now titled 'Team AUSTIN' / 'Team SAN ANTONIO'.",
      "The chase email's LONE STAR CUP banner block now links to the member tracker's Lone Star Cup page (whole banner tappable + a CLICK FOR THE LONE STAR CUP strip, matching the other cards).",
    ],
  },
  {
    version: "2.201.28",
    date: "2026-08-06",
    changes: [
      "Chase email LSC event info gets its own navy banner block (Kerry: the in-card line was 'too garbled') — 'THE LONE STAR CUP / 🏆 October 10–11, 2026 / The Hideout · Brownwood, TX', mirroring the tracker's LSC tab banner, placed below the second cup's card and above the ONE/TWO STEPS TO GET IN line. The cramped line inside the navy chain card is removed.",
    ],
  },
  {
    version: "2.201.27",
    date: "2026-08-06",
    changes: [
      "LSC tab polish (Kerry): the navy event banner (Oct 10–11 · The Hideout · Brownwood) moves up directly under The Lone Star Cup title, and the two team cards are chapter-branded instead of generic dark — Austin in burnt orange (white header text), San Antonio in the steel-blue chapter palette (dark header text, steel captain-row tint), matching the app's chapter color semantics.",
    ],
  },
  {
    version: "2.201.26",
    date: "2026-08-06",
    changes: [
      "THE LONE STAR CUP finally says when and where (Kerry: 'October 10-11 at The Hideout in Brownwood, TX'): the member LSC tab gets a navy event banner (dates + venue above the projected rosters) and the chase email's navy card carries the same line under the seat numbers. Both read the new lsc_event_info dial ({dates, venue, city}) — one source, edits without a deploy.",
    ],
  },
  {
    version: "2.201.25",
    date: "2026-08-06",
    changes: [
      "Players-path chase email box 1 drops the flight (Kerry: 'Remove flight from the 1st chain block. Irrelevant for making the Lone Star Cup team') — the label is simply THE PLAYERS CUP and the rank is the overall visible board rank (the board's own re-rank, tie notation preserved). The 'from winning' line stays flight-scoped since the pot pays per flight.",
      "New CTA state A1 (Kerry): a player already in one or both cups but not signed up gets ONE STEP TO GET IN — the sign-up button ('Get in the field — your buy-in is already working.') — instead of the two-step block, and the buy-in card for an already-purchased cup is removed (only the missing cup's card shows; none when both are owned). Matt Griffin is the first case: Players Cup owned, so his render is sign-up + the Fellowship Cup card only.",
    ],
  },
  {
    version: "2.201.24",
    date: "2026-08-06",
    changes: [
      "'From winning The Players Cup' now measures against the flight leader AS IF EVERYONE WAS IN (Kerry: 'base it off if everyone was in. Otherwise it will be confusing... 98.5 is 1.5 behind 100. Logical math') — Pat Youngs' 100, not bought in, is the reference line, so Matt Griffin reads 1.5 instead of 1. Players-path previews now report pc_flight_rank and pc_back for verification.",
    ],
  },
  {
    version: "2.201.23",
    date: "2026-08-06",
    changes: [
      "Players-path chase email box 1 now shows the VISIBLE flight rank ('4th · PLAYERS CUP · 1ST FLIGHT') instead of the enrolled-only chapter place that read Matt Griffin as '2nd' (Kerry: 'I'm showing 3rd in San Antonio and 4th overall') — everyone on the board counts toward the regular-season finish, bought in or not, flight-scoped per the ratified 2026-07-12 convention. The 'from winning The Players Cup' line deliberately stays measured against the BOUGHT-IN flight leader (only entrants can win the pot — Pat Youngs at 100, not in, is not the reference line); the enrolled-only place convention remains on the fellowship-mode PC card per #296.",
    ],
  },
  {
    version: "2.201.22",
    date: "2026-08-06",
    changes: [
      "Chase email PATH EMPHASIS (Kerry, Matt Griffin/Jeff Young cases): the email can now lead with THE PLAYERS CUP road to the Lone Star Cup instead of The Fellowship Cup — same visual skeleton, data flipped per Kerry's spec: box 1 = Players Cup regular-season finish, box 2 = Players Cup points reset, navy row 1 = gross-path seat gap, navy row 2 = points from winning the Players Cup (flight-scoped), and THE FELLOWSHIP CUP becomes the suppressible second-road card. Path picked per player: the chase_path_overrides dial is the manual toggle ({customer_id: 'players'|'fellowship'}, seeded for Griffin + Young); with no override the auto rule leads players when that seat line is strictly better (inside beats outside, smaller gap wins; ties keep fellowship). Gross-flavored ladder + subjects ('you're holding a Lone Star Cup seat' when inside).",
    ],
  },
  {
    version: "2.201.21",
    date: "2026-08-06",
    changes: [
      "Snapshot Command Center preview window is drag-resizable (Kerry): grab the right edge, bottom edge, or the striped bottom-right corner grip to size it up to nearly full screen (min 340×320). The email iframe ignores pointer events during the drag so the resize doesn't die when the cursor crosses the preview; the chosen size holds until the page reloads.",
    ],
  },
  {
    version: "2.201.20",
    date: "2026-08-06",
    changes: [
      "GAMES tab bucket cards break each championship purse into its sub-game pots (Kerry's rates, one-off for the TGF Championship): DAILY $30/player/day = Team Net $8 + Skins $18 (divided by 2 flights, per-flight amount shown) + Closest to Pins $4; COMBINED $40/player = Individual Net $20 + Individual Gross $20. Pots derive from each bucket's purse (players = purse / rate-sum) so they re-scale automatically as the roster changes.",
    ],
  },
  {
    version: "2.201.19",
    date: "2026-08-06",
    changes: [
      "Snapshot Command Center now previews and sends the R6 CHASE email — the Kerry-approved format with the chain cards, TRUE STORY block, and the two-step CTA (Kerry, previewing Luke Youngs: 'Not our current email format'). The old R5 snapshot builder is retired from the Center's preview/test/send paths; every gate is unchanged (test sends to the recap inbox, real sends require the per-player APPROVED mark and mark the row SENT).",
    ],
  },
  {
    version: "2.201.18",
    date: "2026-08-06",
    changes: [
      "Future-contest status badges (STARTS AUG 29) go solid TGF orange with white text (Kerry: amber was 'boring and non-descriptive... either green or tgf orange' — orange chosen over green so the chip can't be confused with the green IN enrollment pills). Final badge palette: past = gray fill, current = black outline, future = TGF orange fill.",
    ],
  },
  {
    version: "2.201.17",
    date: "2026-08-06",
    changes: [
      "Current-contest status badges restyled per Kerry: black border, black text, no background (outline chip) — past stays gray-filled COMPLETED, future stays amber STARTS AUG 29.",
    ],
  },
  {
    version: "2.201.16",
    date: "2026-08-06",
    changes: [
      "Spotlight status badges now use three tiers (Kerry: 'Past, current, future all need different color badges'): past = gray COMPLETED, current = green (active races with a status note — the cups' 'Ends at TGF Championship'), future = amber (the fall 'STARTS AUG 29' chips). Cup wording also updated to 'Ends at TGF Championship' via the race_status_notes dial.",
    ],
  },
  {
    version: "2.201.15",
    date: "2026-08-06",
    changes: [
      "Spotlight race cards carry a contest-status badge next to the race name (Kerry: 'some type of badge next to these that gives status of the contest'): finished races show a gray COMPLETED chip (derived from the race_final dial — AUSTIN NET 2026 / SAN ANTONIO NET 2026 today), the dormant fall cards show an amber 'STARTS AUG 29' chip, and the cups show an editable free-text chip from the new race_status_notes app-settings dial (seeded 'Ends Aug 15–16' for THE FELLOWSHIP CUP and THE PLAYERS CUP) — wording changes are a dial edit, not a deploy.",
    ],
  },
  {
    version: "2.201.14",
    date: "2026-08-06",
    changes: [
      "Follow-up to the cup-only fix (Kerry: 'Still showing in on Austin Net 2026'): the race boards' enrollment query had NO season scoping, so John Wade's '2026 Fall' NET row (a legitimate Austin Fall Net buy-in) was lighting the finished AUSTIN NET 2026 board's IN pill even after his main-season row was flagged cup-only. Main-season boards now exclude '<year> Fall' enrollment rows from their pill and pot counts; the fall spotlight card reads its own list and is unaffected.",
    ],
  },
  {
    version: "2.201.13",
    date: "2026-08-06",
    changes: [
      "CUP-ONLY enrollments (Kerry ruling, John Wade's $150 Venmo bundle): a NET Points Race buy-in made AFTER the chapter's City NET race is declared final is a Fellowship Cup entry only — 'He shouldn't be shown as paid for that one. It's over and he didn't buy into it.' New season_contests.cup_only flag: the city board's IN pill and $40×N pot exclude these rows; THE FELLOWSHIP CUP counts them fully (enrolled + pot head). The contest sync stamps the flag automatically from the gg_points_race_final dial, so future post-final Cup buy-ins behave the same; boot heal marks John Wade's existing row.",
    ],
  },
  {
    version: "2.201.12",
    date: "2026-08-06",
    changes: [
      "Chase email header now carries the REGISTERED TGF logo — the roundel with 'THE GOLF FELLOWSHIP' wrapped around the G plus the (R) mark — instead of the plain G icon (Kerry: 'why can't we seem to get our actual logo in there... our registered trademark'). Sourced from the TGF Design System's tgf-logo-white.svg via DesignSync (the OneDrive image path can't serve binaries); rendered to static/email/tgf-logo-r-white-216.png at 3x for retina, SVG master alongside. The old plain-G roundel PNG stays on disk so previously sent emails keep their image.",
    ],
  },
  {
    version: "2.201.11",
    date: "2026-08-06",
    changes: [
      "Chase email chain cards sized up (Kerry: 'I'd still like to see the block text in the 3 blocks get bigger'): the city-finish and points-reset numerals go 30px → 34px, the navy card's gap numerals 22px → 26px, the small-caps captions 9.5px → 12px (navy 9px → 11.5px), and every CLICK FOR STANDINGS strip 8px → 10px (including the Players Cup card's) so the tap targets grow with the text.",
    ],
  },
  {
    version: "2.201.10",
    date: "2026-08-06",
    changes: [
      "New bridge command scoring-chase-send:<cid> — builds and sends ONE full chase-email render (the player's live data, no forced test states) to Kerry's recap inbox, for single-render review passes ('Just send an email with the full render') without firing the 11-case matrix. Like the matrix bridge, it accepts no destination address — the only recipient is the recap inbox; member sends remain gated elsewhere.",
    ],
  },
  {
    version: "2.201.9",
    date: "2026-08-06",
    changes: [
      "Chase email State B head now names what the player is signed up for (Kerry: \"'You're signed up' for WHAT?\") — 'You're signed up for the TGF Championship. One step left:'. This was the one head line flagged as not-yet-ratified (#299 item 3); Kerry's rework closes that gate item.",
    ],
  },
  {
    version: "2.201.8",
    date: "2026-08-06",
    changes: [
      "Chase email: THE PLAYERS CUP gross-path card text bumped 12.5px → 15px to match the narrative body paragraphs (Kerry: 'the players cup text is too small. It should match the size of body text above'); the small-caps kicker head goes 12px → 13px so the label still reads as a label. Second deviation-batch from the #296 frozen design, folded into mailbox note to design-claude.",
    ],
  },
  {
    version: "2.201.7",
    date: "2026-08-06",
    changes: [
      "Chase email State A: step 1's head line no longer duplicates the button (Kerry: 'Redundant CTA on step 1') — the head now reads 'Get in the field.' and the orange SIGN UP FOR THE TGF CHAMPIONSHIP button carries the action, matching step 2's 'Then buy into your Cup(s).' rhythm. Copy deviation from the #296 frozen block; flagged to design-claude.",
    ],
  },
  {
    version: "2.201.6",
    date: "2026-08-06",
    changes: [
      "Spotlight NOT IN pills are now amber-urgent instead of neutral gray (Kerry: 'Don't you think the NOT INs need a more urgent color?'): the enrollment pill on the WHERE X STANDS race cards uses the app's due-badge warning family (amber fill, dark-amber text, thin amber ring) so an un-entered race reads as a call to action rather than a disabled state. The IN pill is unchanged; pill size is identical (inset ring, no border).",
    ],
  },
  {
    version: "2.201.5",
    date: "2026-08-06",
    changes: [
      "Handicaps rounds list shows 'Star Ranch' instead of 'The Golf Club Star Ranch' (Kerry): the course row had imported with short_name set to its full name, which the fill-only-if-empty seed skips — 'Star Ranch' is now in the ratified short-name pin list (applied via the scoring-course-short-pins bridge, which corrects mismatches; keyed so Texas Star Golf Course never matches).",
    ],
  },
  {
    version: "2.201.4",
    date: "2026-08-06",
    changes: [
      "Spotlight city Net cards count MVPs instead of GG 'wins' (Kerry: 'change wins to count MVPs... Only count MVPs per event, not per 9'): the count reads our engine's per-event MVP determinations (event_mvp_computed, kind 'mvp', distinct events, chapter-scoped) — the per-nine drill-down rows display the same award twice but it counts once. John Wade's AUSTIN NET card reads '113 pts · 18 ev · 1 MVP · reset 97'. Non-net cards keep their previous behavior.",
    ],
  },
  {
    version: "2.201.3",
    date: "2026-08-06",
    changes: [
      "Chase email mobile fix (Kerry, first test-render review: 'the mobile state renders way too small'): the 620px fixed shell was being scale-to-fit shrunk by iPhone Mail (~63%) — the chain stacked but inside a shrunken canvas. The stacking media query now also makes the shell fluid (width:100%) and tightens side padding to 18px, so phones render at true size like the design mock.",
      "Chase email name fix (the 'DOGGETT,, your city finish' double comma): the builder took names from the target list, which carries GG-style 'DOGGETT, Bryce' — display name now comes from the canonical customer record via the spotlight ('Bryce Doggett' in the header, 'Bryce' in the passage), with a GG-style transform fallback.",
    ],
  },
  {
    version: "2.201.2",
    date: "2026-08-06",
    changes: [
      "Spotlight: THE FELLOWSHIP CUP card now shows the distance to the lead (Kerry: '3 from 1st') right after the points — 'leads' when the player is first. John Wade reads 'T12 of 121 · 97 pts · 3 from 1st'.",
    ],
  },
  {
    version: "2.201.1",
    date: "2026-08-06",
    changes: [
      "EMERGENCY (Kerry, both chapters): championship points were double-counted on the points races — GG's close-out folded the championship into its own season totals days AFTER the board went final, and the overlay's absorption baseline was date-scoped, so every morning it re-baselined against already-absorbed totals and never stood down. Immediate fix was data-side (championship boards dial disabled, backup in gg_champ_points_boards_backup_20260806); this release makes the absorption check durable: the baseline is captured ONCE (not per-day) and absorption LATCHES permanently once a majority of championship scorers' snapshot totals move.",
      "Drill-down presentation per Kerry's rule ('only the standalone, not one of the 10'): after close-out GG lists the championship as a plain white row inside the counted list — the renderer now harvests that row out of the list and carries its points and date on the orange CITY CHAMPIONSHIP line itself.",
    ],
  },
  {
    version: "2.201.0",
    date: "2026-08-05",
    changes: [
      "R6 Championship Chase email built from the design handoff package (mailbox #294-#299): email_parser/chase_email.py carries design-claude's production template verbatim with the sanctioned module tokens — 7-state seat-gap phrase ladder (exact arithmetic), CTA states A/B/C keyed off championship signup + cup enrollment, suppressible Players Cup card (threshold dial chase_pc_suppress_gap AWAITING KERRY; auto-suppress when no gross standing), inside-the-line payoff ('IN'), no-flight caption swap, #299 preheader, ladder-driven subject candidate, and the previously-missing CAN-SPAM compliance footer (unsubscribe + business address dial email_business_address). Assets hosted at /static/email/ (white roundel, star, two trophies — PNGs @2x from SVG masters). Deep links per #300. Store URLs are dials (chase_link_signup / chase_link_buyin) with a flagged placeholder until Kerry posts the GoDaddy product pages.",
      "Bridges: scoring-chase-preview:<cid>[|overrides] renders without sending; scoring-chase-test:<cid>[|send] runs the #299 test matrix (State A baseline, ladder states 1-7, State B, gross-suppressed, no-flight) to Kerry's recap inbox ONLY — no member-send path exists in the bridge by design.",
    ],
  },
  {
    version: "2.200.4",
    date: "2026-08-05",
    changes: [
      "FINANCIAL tab is now admin-only (Kerry): hidden from managers on both the desktop tab row and the mobile toggle, and the financial-summary API is raised to admin so the hide is enforced server-side too. For admins the tab renders in persistent TGF orange — always filled, going a shade darker with a white inset ring when it's the active view.",
    ],
  },
  {
    version: "2.200.3",
    date: "2026-08-05",
    changes: [
      "GAMES tab shows bucket purses on bucket-account events (Kerry: 'I just don't want my manager coming in there and thinking these are the games'): events with per-bucket payout accounts (the championship pattern) replace the regular 9/18 matrix panel with the derived SATURDAY/SUNDAY/COMBINED purse cards plus a field-based explainer — the matrix doesn't apply to a 36-hole event and no championship matrix exists yet. Regular-season events unchanged; works on desktop and the mobile GAMES toggle (same renderer).",
    ],
  },
  {
    version: "2.200.2",
    date: "2026-08-05",
    changes: [
      "Package due-badge now nets settled +PAY children and respects the paid_at stamp (mailbox #286, Kerry screenshot: Callaway's $86 credit + $334 settled Venmo child still showed '$334.00 DUE' next to his package chip). Due = package price − (parent + active +PAY children), suppressed entirely once the row carries the balance-paid stamp the green $ badge reads. Mazanec (genuinely unpaid) keeps his DUE badge until his Venmo lands. Same netting applied to the no-packages ≥-base fallback badge.",
    ],
  },
  {
    version: "2.200.1",
    date: "2026-08-05",
    changes: [
      "scoring-expense-patch can now set matched_item_id, linking an inbound receipt to the roster registration it paid for (mailbox #284: Jenkins' $420 Venmo receipt → his Add Player row, with review_status 'ignored' guarding the double-count since the paid-separately add already booked the income).",
    ],
  },
  {
    version: "2.200.0",
    date: "2026-08-05",
    changes: [
      "Package-aware Apply Credit (mailbox #281, Kerry-ratified, championship-critical): on events with package configurations the modal's Event Selections block becomes a Package dropdown filtered by the player's status ('- Member'/'- Guest' label suffix; 1st Timer prices as member; flipping status refilters, keeping the same base package). New Event Price = the selected package's price — Callaway picking 'Both Days + Side Games - Member' shows $420 − $86 = $334 due, exact — games auto-derive from the label, the created registration is pinned to the package, and the balance-due email/Venmo-request pipeline receives the package-derived balance. Events without configs behave exactly as before; the server re-reads the price from stored configs, never trusting the client.",
      "WHICH DAYS extraction (mailbox #282): the order-email parser now always carries the multi-day 'WHICH DAYS?' answer into notes, and the championship bundle classifier self-assigns single-day buyers from it (the champ_single_day_assignments dial remains the override). Larson's day was ruled SATURDAY from his order email — SATURDAY purse $480.",
    ],
  },
  {
    version: "2.199.3",
    date: "2026-08-05",
    changes: [
      "Championship per-bucket payout accounts (mailbox #276 A, approved #279): bridge scoring-champ-buckets upserts '2026 TGF CHAMPIONSHIP — SATURDAY / SUNDAY / COMBINED' tgf_events accounts with purses DERIVED from the live bundle-carrier roster (SAT/SUN = carriers × $30, COMBINED = full bundles × $40). Single-day buyers count toward their day via the champ_single_day_assignments dial ('Name=SAT'); unassigned players are surfaced, never silently counted.",
      "Championship allocation reclass (mailbox #276 B, approved #279): bridge scoring-champ-alloc-reclass moves each bundle's dollars ($100 full / $30 single-day) to prize_pool with $0 tax — delta out of tgf_operating, course_payable untouched, pure-bundle rows (Robert's +PAY) zero their other buckets, and missing allocations are created status 'pending' with ratified fields only.",
      "HIO pot sizes 36-hole championships at $4/player via the new hio_36h_event_patterns dial (default '2026 TGF CHAMPIONSHIP') — two 18-hole competition days per the $1/nine/player law; Friday practice contributes $0; field = all registered players.",
    ],
  },
  {
    version: "2.199.2",
    date: "2026-08-05",
    changes: [
      "MCP get_event_registrations now resolves event_aliases in both directions (mailbox #276 item G): querying '2026 TGF CHAMPIONSHIP' also returns rows stored under the 'TGF CHAMPIONSHIP' alias (James Jones item 2392) and vice versa, matching what the UI roster shows.",
      "Boot heal: items with a null chapter now derive it from the customer's record (mailbox #276 item H, Kerry ruling: customer record, never shipping address) — fills chapter and chapter_id in one pass. Covers the Aug 5 championship orders (items 2505/2507/2509) whose event_id also links on this boot via the existing alias-aware backfill.",
    ],
  },
  {
    version: "2.199.1",
    date: "2026-08-04",
    changes: [
      "Add Player unknown-name guard (Kerry, the 'Marq' case: return was hit before the typeahead filled 'Mike Marques', saving an unlinked partial name onto the TGF Championship roster): saving an RSVP or paid-separately player whose typed name matches no known player now asks for confirmation first, listing the closest matching names ('Did you mean: Mike Marques?') so the manager can cancel and pick from the dropdown instead of creating an orphan row.",
    ],
  },
  {
    version: "2.199.0",
    date: "2026-08-04",
    changes: [
      "Two-tier desktop width (Kerry: 'widen admin/manager data pages to 1280 universally'): manager and admin sessions now get a 1280px work column on every page via an html.tgf-wide class auth.js stamps when the role resolves (pre-applied from sessionStorage so returning sessions don't flash narrow-then-wide). Member, view-only, and anonymous visitors keep the ratified 1080px. The /me page (720px) and print sheets are unaffected.",
      "PACKAGES is now a first-class tab in BOTH the Add Event and Edit Event modals (Kerry: 'I'd rather do an Event Creator that allows me to build that event and associated packages' - the v2.198.0 editor buried inside PRICING was unclear). The tab explains the concept in plain language (what the event sells, name + total checkout price, auto-match by exact paid amount, credit rows assigned from the roster), and packages entered while CREATING an event save automatically the moment the event is created - no second trip into Edit.",
      "Data fix: the 'Marq' RSVP-only row on the 2026 TGF CHAMPIONSHIP (typed into Add Player without picking from the typeahead) is now linked to Mike Marques (customer_id 14, email/phone/chapter restored), so the Remind flow can reach him.",
    ],
  },
  {
    version: "2.198.0",
    date: "2026-08-04",
    changes: [
      "Event Package Configurations (Kerry: the 2026 TGF CHAMPIONSHIP is a 36-hole Sat/Sun event plus a Friday practice round, sold as day combinations - 'I need to be able to create these configurations now in order to send accurate balance requests to those with credit'): Edit Event > PRICING gains a Package Configurations editor (admin) where each package is a label + price (Kerry entering prices IS the rule-3b ratification). Stored per-event in the event_package_configs app setting - no schema change.",
      "Package-aware roster pricing: registrations auto-match a package by exact paid price (credit rows never auto-match - the credited amount is what was transferred, not a package price); unmatched '(credit)' rows get an amber assign-package dropdown, and assigned rows keep an editable dropdown so a pin can be changed or cleared. A matched row whose payment covers less than its package price shows an EXACT '$X.XX due' badge (no >= hedge); events without packages keep the v2.197.2 >=-base heuristic.",
      "New API: GET /api/events/packages (manager), POST /api/events/<id>/packages (admin, replaces the list), POST /api/events/<id>/packages/assign (manager, pins/clears one registration).",
    ],
  },
  {
    version: "2.197.2",
    date: "2026-08-03",
    changes: [
      "Under-covering credit flag on event rosters (Kerry, the Callaway case: an $86 duplicate-payment credit transferred onto a ~$335+ championship entry showed no difference due): any active '(credit)' registration whose credit covers less than the event's BASE price (course + markup + fee, before optional side-game buy-ins) now shows an amber '>= $X due' badge next to the price. Applies to every transfer pathway, all chapters.",
      "ACTIONS column pins to the right edge of the roster (Kerry: 'My window is unable to scroll left right without scrolling all the way to bottom, so I can't see the ability to reverse it') - the last column is position:sticky with a separating shadow, so Edit/reverse controls stay reachable while the wide table scrolls under it.",
    ],
  },
  {
    version: "2.197.1",
    date: "2026-08-03",
    changes: [
      "Points-record rows cut to near text-height (Kerry: 'Vertical Padding still more than I want on the rows') - 0.1rem vertical padding on the drill-down detail tables; standings rows unchanged.",
    ],
  },
  {
    version: "2.197.0",
    date: "2026-08-03",
    changes: [
      "snapshot_command_center MCP tool (Kerry: give CA 'full access with everything that you created and that can be created with it'): one tool for the whole outreach engine - overview (live counts, criteria, championship signup coverage, dials), queue/targets (tunable windows), preview (the exact email), mark (approve/defer/skip), send_test (to Kerry's inbox), and send (real member send, still hard-gated on Kerry's approved mark - no bulk send exists). Connects via the claude.ai/Desktop MCP endpoint.",
      "docs/claude/snapshot-command-center.md is the spec of record for CA's optimization session: Kerry's intent (regular spotlight email + TGF Championship, cup races, and Lone Star Cup qualification promotion), the verified story facts, targeting criteria, email anatomy, send governance, and the levers to optimize (segment copy variants, cadence, windows, measurement).",
      "CHAMPIONSHIP TOTAL label and its total cell are vertically centered (Kerry - baseline mismatch from the smaller label font).",
    ],
  },
  {
    version: "2.196.6",
    date: "2026-08-03",
    changes: [
      "Snapshot email: immediate CTA button right after the WHERE YOU STAND summary (Kerry) - BUY IN NOW when the player is outside a cup, SIGN UP FOR THE TGF CHAMPIONSHIP when they are in but not registered; nothing when both are handled. The detailed WAYS IN and weekend blocks stay below for the readers who want the why.",
    ],
  },
  {
    version: "2.196.5",
    date: "2026-08-03",
    changes: [
      "Snapshot email reset differentiation (Kerry): the city Net Points Reset carried ONLY into THE FELLOWSHIP CUP - the lead-in now names it specifically, THE PLAYERS CUP row carries an '(own reset · <flight>)' tag, and a footnote spells out that the Players Cup ran its own reset and flights.",
    ],
  },
  {
    version: "2.196.4",
    date: "2026-08-03",
    changes: [
      "Championship card HCP row restored (Kerry): the merged championship tee had no stroke-index data in the course DB, but GG's own tee block carries YARDS + HCP rows — parse_tee_block already read them and the card now consumes them (course-DB tee stays as fill-in). Applies live, no import needed.",
      "Championship card gets the per-nine handicap notes (Kerry: 'you added the handicap diffs for each 18 hole regular season event, but not the City championships'): Adj. gross + Differential against each nine's own rating/slope render under the IN and OUT blocks, from the POSTED two-nine handicap rows.",
      "CHAMPIONSHIP TOTAL label sits left of the bold orange 18-hole total cell (Kerry).",
      "POINTS NOT COUNTED collapses by default on player expansion (Kerry) - the gray banner is the toggle; opening/closing it also folds any scorecards expanded inside.",
      "Tighter drill-down rhythm (Kerry): less padding between the Full Spotlight pill and the DATE/EVENT header, and slimmer vertical padding on every points-record row (.pr-detail).",
      "Fellowship Cup standalone $50 split confirmed by Kerry (40 pool / 10 markup) - pricing records updated.",
    ],
  },
  {
    version: "2.196.3",
    date: "2026-08-03",
    changes: [
      "CITY CHAMPIONSHIP drill-down row matches its neighbors exactly (Kerry): the date cell uses the same default indent as every event row, the expand chevron sits LEFT of the name like the other expandable lines, the label reads '[CHAPTER] CITY CHAMPIONSHIP' (no more 'Total'), and the championship course renders on a second line beneath it. The course comes off the championship-day event per chapter (payload champ_courses) - cross-chapter cup boards pick each player's own chapter's championship.",
    ],
  },
  {
    version: "2.196.2",
    date: "2026-08-03",
    changes: [
      "Snapshot Center joined the admin subnav on every admin page (Kerry: 'Can't see Command Center access' - the page existed but only by URL).",
    ],
  },
  {
    version: "2.196.1",
    date: "2026-08-03",
    changes: [
      "Snapshot email v3 (Kerry's full pass): the TGF logo mark sits left in the dark header with the PLAYER'S NAME as the big line ('Your TGF Snapshot' becomes the eyebrow); the completed city Net race renders as a FINAL block — finish, points total, and what the Points Reset converted to — leading into THE FELLOWSHIP CUP standings then THE PLAYERS CUP; every standings mention deep-links to that live board on the member Leaderboard with the same centered + pulsing landing as the Spotlight links.",
      "WAYS IN section with the direct buy-in link (thegolffellowship.com season contests): The Fellowship Cup by itself for $50 now that City Net is over (Kerry-stated price), The Players Cup $50, and the Fall City Points Race $50 (Best 6 + Fall Championship — its own race, does not feed the TGF Championship or Lone Star Cup). The weekend section now carries the direct SIGN UP FOR THE TGF CHAMPIONSHIP link.",
    ],
  },
  {
    version: "2.196.0",
    date: "2026-08-03",
    changes: [
      "SNAPSHOT COMMAND CENTER at /admin/snapshot-center (Kerry: 'an interactive Command Center for me to approve, preview, mark accordingly'): the live targeting queue as PUSH ENTRY / DEFEND / NORMAL tabs with each player's points back, seat-line gap, cup buy-in, and TGF Championship signup status; per-player Preview (the exact email HTML), Approve / Defer (with a note — 'in Hawaii until Sept') / Skip / Clear marks, Send Test (to your inbox), and a real Send that goes to the player's primary email ONLY after your Approve — nothing ever bulk-sends. Marks persist in the snapshot_center_marks app setting.",
      "TGF Championship signup is the queue's second layer (Kerry): every entry carries whether the player is signed up or RSVP'd for an upcoming championship event; when they're not, the snapshot email adds 'Be there for the weekend itself' — the TGF Championship and Lone Star Cup as TGF's top two experiences, family welcome, place-in-the-money honest. No fall championship event posted yet reads as unknown, never guessed.",
      "Seat-line window widened to 15 points (Kerry: 'within 15 points of an LSC seat line would be relevant too') — the push window is now within-15-of-the-lead OR within-15-of-a-seat.",
      "City Championship card final polish (Kerry): the name/points headline is gone (the row above already names the player) and the 18-hole total hangs as a bold orange cell right under the last nine's CHAMP PTS sum; CHAMP PTS rows wear the faded-orange band matching the CITY CHAMPIONSHIP Total row; YARDS and HCP rows render from the player's imported round's tee.",
      "18-hole scorecards show what was actually banked: per-nine Adj. gross + Differential (each against its own GG-course-setup rating/slope) under each nine block, replacing the 18-hole adj/diff line — on the Contests drill-downs, the member Handicaps page, and /me.",
      "GROSS PTS row hidden under CITY NET race scorecards (the gross score itself stays as the basis); BUY-IN column centers like every other stat column (Kerry asked about its 'extra padding' — it was a 110px column with left-aligned content).",
    ],
  },
  {
    version: "2.195.1",
    date: "2026-08-03",
    changes: [
      "Snapshot targeting queue only scores chapters that field Lone Star Cup teams - a lone player from an inactive chapter (live find: a single Houston player on the gross board) was otherwise 'leading' a pool of one and landing in the push list.",
    ],
  },
  {
    version: "2.195.0",
    date: "2026-08-03",
    changes: [
      "UNIVERSAL card standard (Kerry: 'if we make a change to the look of it, it will change universally'): the hole-by-hole card style moved to static/js/tgf-standards.js (window.TGF_CARD_STYLE) and EVERY scorecard renderer consumes it — Contests drill-down event cards, the live City Championship card, and the member-portal cards on Handicaps + /me (scorecard-render.js had quietly drifted: darker header shade, 3px section borders, grey facts rows — now pixel-identical, and it picked up the back-nine-first play-order rule it was missing).",
      "UNIVERSAL stat-column standard (window.TGF_STAT_COL, same file): 110px desktop / 50px compact, centered, 6px horizontal padding. 'The wider of the two dictates' — POINTS joined POINTS RESET at 110px on the standings tables and the drill-down; TODAY/THRU take the standard width on desktop and keep their phone-tuned tight widths.",
      "Snapshot email seat-line gaps translate to golf (Kerry: 'you're 1 point from... is equal to one net bogey in the TGF Championship!'): gaps ≤1 read 'That's one net bogey at the TGF Championship', small gaps read as a hole count.",
      "Snapshot targeting queue (scoring-snapshot-targets): walks both cup boards and segments every player — push_entry (in the window, not bought in: within 15 of the lead or within 3 of an LSC seat line), defend (in the window, bought in), normal. A review queue for Kerry — availability is a human call; nothing auto-sends.",
    ],
  },
  {
    version: "2.194.3",
    date: "2026-08-03",
    changes: [
      "Season-standings payout lines read friendly on the Spotlight (spotted on live Callaway/Niester payloads): 'City Net — SAN ANTONIO Net 2026 final standings — 2 place' now renders 'City Points Race — 2nd Place | Season Standings'.",
    ],
  },
  {
    version: "2.194.2",
    date: "2026-08-03",
    changes: [
      "ONE hole-by-hole card standard (Kerry: 'adopt the same style setting for the City Championship scorecard display on everything, including the column widths'): prCardStyle() now feeds BOTH the championship card and the imported-event scorecards — cell metrics, column widths, label column, section borders, points band, and the vs-par marks come from a single place so the grids can never drift.",
      "Column padding equalized to the POINTS RESET standard (Kerry: 'It's 6 right?'): every stat column on the standings tables — RANK, POINTS/SEASON, POINTS RESET, ROUNDS, BUY-IN, and the live MOVE/TODAY/THRU set — plus the drill-down POINTS/Date/POS headers, body cells, and the CITY CHAMPIONSHIP row all carry 6px horizontal padding.",
      "Snapshot email measures from the Lone Star Cup seat line (Kerry: 'making your city's Lone Star Cup team is an even lower bar'): the navy LSC block now shows BOTH cup paths with the last seat's points and the player's gap to it — inside-the-line players see their cushion, chasers see exactly how few points a seat costs. The spotlight LSC payload carries seat_cut_points / my_points / gap_to_seat per path.",
      "Snapshot email fixes from the live Youngs payload: a non-enrolled player who out-points every enrolled player no longer reads as negative points back (the player joins their own comparison field), non-entered boards now show in WHERE YOU STAND with a '(not entered)' tag, and winnings labels polish — 'City MVP', 'TGF MVP — combined same-day pot', 'Closest to Pin — Hole 3'.",
    ],
  },
  {
    version: "2.194.1",
    date: "2026-08-03",
    changes: [
      "YOUR TGF SNAPSHOT email builder (MOCK phase — Kerry: 'clean and totally about them', no bait): a personalized member email telling the Points Reset story — where the player stands in every race they're in, points back from the lead on the reset seeds, how many players sit within 15 of the lead ('this is our Tour Championship'), the ~72-points-for-shooting-your-handicap weekend math, and the verified Mark Freund 2024 proof of concept (30th on the seeded board when championship weekend started, 14.5 back, won the Fellowship Cup by 2.5). Bridge: scoring-snapshot-email:<cid>[|<to>][|send] — dry-run preview by default; sends ONLY to the named/admin address until Kerry ratifies member sends.",
      "Spotlight race entries carry reset-field context: leader_points, points_back, and n_within_15 (players within 15 points of the lead, on reset seeds when official).",
    ],
  },
  {
    version: "2.194.0",
    date: "2026-08-03",
    changes: [
      "CITY CHAMPIONSHIP drill-down row aligns to its real columns (Kerry): the championship date sits in the Date column on the left, the points total sits inside the bordered POINTS column (same centered 2px-rule treatment as every other row), and POSITION populates with the player's live championship rank (T-ties included). The date comes from the gg_points_race_final dial; the rank is computed among scorers on every board read.",
      "The live championship hole-by-hole card now follows the SAME formatting as the imported scorecards (Kerry: 'It should follow the formatting of the other scorecards from previous events'): dark HOLE header band, blue PAR facts row, thick-bordered GROSS SCORE section with the red-circle/blue-square vs-par marks, NET SCORE with corner handicap dots on net races, and points on the tinted band. Each nine carries its own OUT/IN total column; 18-hole Gross + points totals ride the note line beneath, with the under/over-par legend. Unplayed holes keep the Tour-style dash — this card is live.",
      "Player Spotlight hero index tile now links to the player's full handicap detail on the Handicaps page — pinned to top, expanded, pulsing (the same deep link the recap emails use).",
      "Lone Star Cup SEAT differentiates projected vs secured (Kerry: 'I'm showing a SEAT... but that's a projection for me, whereas Callaway and Straiton... are locked'): a locked champion seat reads SEAT · locked 🔒 · Secured, while a live projection reads PROJ · seat · Projected.",
      "scoring-hcp-r1-impact now reports the unchanged players by name (Kerry: 'which 10 player handicaps did not rise?').",
    ],
  },
  {
    version: "2.193.3",
    date: "2026-08-03",
    changes: [
      "Play-order fix rebuilt on a dial: scoring_rounds has no first_hole column (the field in round lists is computed at read time), so which nine an event teed off on lives in the event_first_nine app-settings dial instead of a schema change. The scorecard payload and the championship drill-down card read the dial; the scoring-hcp-nine-order command writes it and still reorders the two-nine differential pairs.",
    ],
  },
  {
    version: "2.193.2",
    date: "2026-08-03",
    changes: [
      "Spotlight winnings games read like English (Kerry: 'individual_net · Ind Net LOW Flight 1st is really gobbledy guck'): each game renders as 'Individual Net — 1st Place | Low Flight', 'Skins — Holes 3, 7 & 12 | Low Flight', 'Team Net — T1st Place w/ Callaway & Wade', 'Individual Gross — T1st Place | Flight 1'. Team partners resolve live from the event's saved team pairings; skins payouts now record WHICH holes in their description going forward (older rows show the skin count). Closest to Pin shows its hole.",
    ],
  },
  {
    version: "2.193.1",
    date: "2026-08-03",
    changes: [
      "Handicaps HOW IT WORKS matches the Season Contests pill (Kerry) and its content rebuilds on the thegolffellowship.com handicaps page language: best 8 of last 20 nine-hole differentials, WHS standards on 9-hole scores, why counting each nine on its own beats GHIN's combine-9s (your best golf is your potential, and the index updates every event), the net-double-bogey cap, the small-record ladder, the 75%-of-existing-handicap onboarding until 27 TGF holes, and event-day playing handicaps.",
      "Every lingering ×0.96 surface is scrubbed (Kerry: 'I thought we sunset that' — it sunset today, v2.192.3): the per-player calc modal hides the multiplier sentence at 1.0, and the admin settings modal reads WHS = 1.0 with a note that the pre-2020 factor retired.",
      "Nines display in PLAY order (Kerry: the SA championship teed off on the back): new scoring-hcp-nine-order:<event>|<front|back>|apply stamps first_hole on the event's rounds and reorders each player's two-nine differential pair so the newest-first list shows the second-played nine on top; expanded scorecards (imported rounds and the championship drill-down card) render IN above OUT when the round started on 10.",
      "Spotlight LSC line uses the chapter's REAL Fellowship seat count (a co-captain year shaves 6 to 5 — Kerry-confirmed).",
    ],
  },
  {
    version: "2.193.0",
    date: "2026-08-03",
    changes: [
      "LONE STAR CUP row on every Player Spotlight (Kerry): a Texas-navy row in WHERE PLAYER STANDS linking to the LSC projections page. Seat holders see their seat, alternates their number, enrolled cup players their live path place — and players who haven't bought in see where they WOULD land today via the better of the Fellowship Cup or Players Cup path ('buy in to make it count'). Until the selection deadline (Aug 14, dial lsc_selection_deadline) everyone sees the row; after that it narrows to players bought into either cup. The old hero-card LSC line retires into this row.",
    ],
  },
  {
    version: "2.192.3",
    date: "2026-08-03",
    changes: [
      "R1 APPLIED — the ×0.96 multiplier is out of the handicap index (ratified 7/16, sequenced behind an impact sweep that ran today: 158 of 168 indexes rise, mean +0.31, max +0.8). The live dial and the code default are both 1.0 so a settings reset can't resurrect it; the HOW IT WORKS copy, the calc modal default, and the handicap docs all drop the factor. Record layer updates retroactively by design; no paid result is touched.",
    ],
  },
  {
    version: "2.192.2",
    date: "2026-08-03",
    changes: [
      "Player Spotlight WHERE PLAYER STANDS reads the LIVE standings path (Kerry: 'not all updated') — the section was built on the base season snapshots, which lag championship points and the official reset re-projection; it now uses the same championship-inclusive live read the Contests page serves, so ranks, totals, and reset values match the leaderboard.",
      "Spotlight Recent Winnings groups by EVENT (Kerry): one row per event with the total won, tap to expand the games and amounts inside it (native expander, latest six events). Older payloads fall back to the flat list.",
    ],
  },
  {
    version: "2.192.1",
    date: "2026-08-03",
    changes: [
      "Two handicap analyses land as MCP bridge commands (Kerry): scoring-hcp-ghin-compare builds each player's comparable-GHIN 18-hole index from TGF event scores only — consecutive nines combined into 18s the old GHIN way, WHS best-8-of-20, no 0.96, no time window — and reports the TGF-to-GHIN ratio distribution (testing the '75-90% of GHIN' rule of thumb) plus a validation of the 75% onboarding rule against players with stamped starting handicaps. scoring-hcp-r1-impact runs the R1 sweep the 7/16 ratification sequenced (recompute every index without the ×0.96 and report movement); :apply flips the multiplier dial to 1.0.",
    ],
  },
  {
    version: "2.192.0",
    date: "2026-08-03",
    changes: [
      "Handicaps page gets a HOW IT WORKS explainer (Kerry): a page-level modal walking through the TGF system in member language — the 9-hole N index and its 18-hole twin, championship rounds posting as two nines against each nine's own rating/slope, the net-double-bogey cap, the differential formula, best-8-of-20 over 12 months (with the small-record ladder for newer players), and how the index becomes event-day playing handicap dots. Opens from a HOW IT WORKS pill in the filter row.",
      "Full Spotlight pill on the expanded handicap view (Kerry: 'same that you added on expanded player view in the season contests') — expanding any linked player's rounds now offers the same black Full Spotlight → link the Contests drill-down carries, on desktop and mobile cards, member and admin views.",
    ],
  },
  {
    version: "2.191.7",
    date: "2026-08-03",
    changes: [
      "Handicap recap email reads as one block per player (Kerry: 'listed the name only once and the final Index and change only once... added a Side column'): the two nine rows sit under a single name with a Front/Back SIDE column, the 9-hole index and change span the block, inner dividers lighten so each player reads as one unit, the movers list dedupes to one entry per player, and the WHS-cap dagger rides the capped side. Single-round postings keep their old shape — the SIDE column only appears when a posting has sides.",
      "Player names in the recap link to the member handicap page with that player pinned to the top and their rounds expanded (Kerry) — /member/handicaps?player=<name> now scrolls the row to the top, expands their differentials, and pulses it, on the desktop table and the mobile cards alike.",
    ],
  },
  {
    version: "2.191.6",
    date: "2026-08-03",
    changes: [
      "Handicap recap emails label their indexes as what they are (Kerry): every index value carries the N suffix (TGF indexes are 9-hole indexes) and the column header reads 9-Hole Index. Differentials stay bare — the suffix marks indexes only.",
    ],
  },
  {
    version: "2.191.5",
    date: "2026-08-03",
    changes: [
      "Championship handicaps POSTED, both chapters: SA 32 players / 64 nine-hole differentials (The Quarry) and Austin 16 players / 32 (Falconhead) — every 18-hole round split into front + back nines, each against that nine's own GG-course-setup rating and slope (Kerry-read; the validation rule is that front + back ratings sum exactly to the 18-hole rating, while GG stores the 18-hole slope independently). The chapter recap email now works for two-nine postings: the 9-hole preview path deliberately skips 18-hole rounds, so the recap rebuilds its rows from the posted handicap rounds instead.",
    ],
  },
  {
    version: "2.191.4",
    date: "2026-08-03",
    changes: [
      "Championship handicap posting prep (Kerry: '2 x 9 hole diffs posted based on 9 front and back ratings/slope'): the two-nines derive gains a generic MCP bridge command (scoring-hcp-2nines:<event>|<per-nine JSON>|apply — the Vaaler command's reusable successor) and an intra-run dedup guard: the ALL Net → ALL Gross scorecard backfill banks two scoring rounds per player per championship, and without the guard a single apply would have posted every nine twice.",
    ],
  },
  {
    version: "2.191.3",
    date: "2026-08-03",
    changes: [
      "One bordered stat-column standard (Kerry: 'I'd like a standard unless I ask for a specific change'): 50px on phones / 110px on desktop, centered titles, 6px horizontal padding, full-height 2px dividers, stacked two-line titles. Applied to the Fellowship Cup's CITY RANK and RESET columns and the city boards' reset column — the RESET header now stacks POINTS over RESET everywhere it appears, matching CITY over RANK.",
    ],
  },
  {
    version: "2.191.2",
    date: "2026-08-03",
    changes: [
      "Fellowship Cup CITY RANK column gets its full-height left divider line, a centered title, and enough width that RANK no longer overflows into the RESET border on phones (the 34px column couldn't hold the 9px-caps title). Header-title padding audit across table views: compact table headers get 6px horizontal everywhere — the main standings container already had it; the base compact rule and the points-render.js injected drill-down tables (Customers page Points tab) now match, so no bordered column title touches its divider.",
    ],
  },
  {
    version: "2.191.1",
    date: "2026-08-03",
    changes: [
      "The cross-links now run both directions (Kerry): a POINTS RESET value on the San Antonio or Austin city board links back to that player's row on THE FELLOWSHIP CUP — same center-and-pulse landing as the CITY RANK links going the other way. Only the two cup-feeding NET races link; gross and monthly resets seed other contests. Also guards the jump against pouncing on the same player's row in the outgoing table before the new board renders.",
    ],
  },
  {
    version: "2.191.0",
    date: "2026-08-03",
    changes: [
      "Fellowship Cup CITY RANK links (Kerry): the column header stacks as CITY / RANK (it was colliding with RESET on phones as 'CITY # RESET'), and each player's rank is now a link that jumps to their chapter's city race board, centers their row on screen, and pulses it — the same treatment as the Spotlight deep links — so anyone can see who's above and below them in one tap.",
    ],
  },
  {
    version: "2.190.2",
    date: "2026-08-03",
    changes: [
      "Players Cup scorecard scores GROSS points correctly (Kerry: 'it needs to show the Gross points, not the net points'): v2.190.1's card used the championship NET scale on the gross race, showing Pat 43 while the board said 50. The championship gross boards actually used the SEASON gross doubling table (birdie 4, eagle 8, par 2, bogey 1, double 0, triple -1; ace 9) — verified exactly against six players' GG board totals spanning +50 to -4, including the negative finishes. The card now computes through get_championship_formulas + compute_hole_derivations (the same formula layer that already encoded this rule), so Pat's card sums to his official 50.",
    ],
  },
  {
    version: "2.190.1",
    date: "2026-08-03",
    changes: [
      "City Championship scorecard shows on THE PLAYERS CUP drill-down (Kerry: 'No scorecard showing for city champ'): the cross-chapter gross race had no scorecard-board config, so the hole-by-hole card came back 'No holes posted yet.' The race now reads BOTH cities' championship scorecard boards (list entry, same shape as the points boards), and gross races score the card correctly: points off the raw gross vs par, no handicap dots, no NET row, no plus-handicap deduction. A guard in the plus-adjustment path keeps the new scorecard config from ever re-scoring the gross race totals — the plus rule is a NET-points rule and the GG gross boards were recorded as posted.",
      "Fellowship Cup column relabel (Kerry: 'Net # is more accurately CITY'): the per-chapter rank column now reads CITY # / CITY Rank.",
      "The expanded row's 'Proj. points reset' line stands down once the reset is official (Kerry: 'projected points reset is redundant and projected is obsolete') — the table's RESET column already carries the figure.",
      "New MCP bridge command scoring-setting-get:<key> — read an app_settings dial (companion to scoring-setting-set).",
    ],
  },
  {
    version: "2.190.0",
    date: "2026-08-03",
    changes: [
      "Mobile wave 1 (Kerry: 'Do wave 1 of the mobile fixes'): the page-slide class of bugs is retired app-wide. A global body overflow-x guard in dashboard.css now stops ANY wide table from dragging the whole page sideways (clip, not hidden, so sticky headers keep working), and every known wide table gained its own horizontal scroll container: Events' Comp Players and Actual Expenses financial tables, Contests' Enrollments and Removals tables, Cashflow's 7-column weekly table, the TGF screenshot-import preview, both Test Center leaderboard/field tables, both GG History tables, and all points-render.js injected drill-downs (rounds list, champ scorecard, points-detail tables).",
      "TGF Payouts action column is tappable on phones: Pay/Venmo, + Add Payment, and Mark Paid buttons get a 40px tap-target floor on mobile (they were ~22px pills), the Mark Paid button's inline styles moved to a proper class so the mobile override can reach it, the action cell wraps and stacks its controls instead of truncating ('Mark Pa…'), and the handle input is 16px on mobile so iOS stops zooming the page on focus.",
      "COO dashboard section headers and filter pills wrap on narrow screens instead of overflowing the section card.",
    ],
  },
  {
    version: "2.189.9",
    date: "2026-08-02",
    changes: [
      "Chapter badges replace the Chapter column (Kerry: 'Rather than a chapter column can we do a chapter badge with the chapter color. Simple SA or A'): on every cross-chapter board — The Fellowship Cup, The Players Cup, and Monthly — the chapter now rides as a small colored pill beside the player's name (SA on the steel chapter blue, A on the Austin burnt orange, future chapters as initials on national gray) and the whole column disappears, giving the Player column the width back on phones.",
    ],
  },
  {
    version: "2.189.8",
    date: "2026-08-02",
    changes: [
      "THE PLAYERS CUP settles into Points Reset status (Kerry): the championship gross overlay's final boards report scorers forever, so the Cup was stuck wearing the LIVE badge and the championship-day TDY/THRU columns. Once the reset is official the live layout stands down — championship-inclusive totals stay, presented as the season view with POINTS RESET leading and the season totals dimmed under a SEASON header, no LIVE badge. The TGF Championship's own live day this fall gets its own board config.",
    ],
  },
  {
    version: "2.189.7",
    date: "2026-08-02",
    changes: [
      "Receipt memos keep their payee prefix deterministically: the AI email reader is instructed to copy the memo verbatim but still dropped the 'Chuck Fehlis - ' prefix on 8 of 15 championship receipts — starving the payout matcher of its best identity signal. After extraction the code now finds the returned memo in the raw email and, when a 'Name - ' run precedes it on the same line, takes the full line. The email text outranks the model's rendering.",
    ],
  },
  {
    version: "2.189.6",
    date: "2026-08-02",
    changes: [
      "Hotfix on v2.189.4's paid-row preservation: the consumed-twin matching resolved assembled names with the generic customer lookup, which can't read GG's 'VASQUEZ, Gus' format — so the first live force re-record preserved all 33 paid SA rows correctly but re-inserted 26 of them as pending duplicates. Consumption now uses the same _resolve_customer_for_payout resolver the insert path uses; a follow-up force re-record deletes the pending duplicates and inserts nothing back.",
    ],
  },
  {
    version: "2.189.5",
    date: "2026-08-02",
    changes: [
      "Participation is usable on a phone (Kerry: 'participation on mobile slides everything'): the 11-column table now scrolls inside its own wrapper instead of dragging the whole page sideways (header, stat cards, and filters stay put; body overflow-x clipped as a belt), and mobile gets compact table typography and tighter filter controls.",
    ],
  },
  {
    version: "2.189.4",
    date: "2026-08-02",
    changes: [
      "A force re-record never un-pays money that moved (Kerry: 'I have paid this and initially tracker has cleared it. Why has it come back?'): the hourly auto-sync force-replaces recent events' payout rows, and the old path deleted PAID rows too, re-inserted everything pending, and trusted the receipts to re-match — which silently fails when two players owe the same amount (Chuck Fehlis' $42.50 kept reverting because Don Sharitz' $42.50 made the amount-fallback ambiguous mid-cycle). Rows backed by a real (non-pending) ledger transaction are now PRESERVED through the re-record, their assembled twins consumed one-for-one on (customer, category, exact amount) instead of re-inserted. A paid row whose assembled amount later changes stays alongside the new pending difference for admin reconciliation.",
    ],
  },
  {
    version: "2.189.3",
    date: "2026-08-02",
    changes: [
      "Lone Star Cup: the City Match Play champion's seat renders in the standard standings style ('YOUNGS, Luke') — the bracket stores plain display names, so a formatter normalizes it to match every other seat.",
      "How It Works: THE MONEY section reads below the points chart and example scorecard on every contest that has them (the chart-less Match Play modal keeps its written order) — race first, points and the worked card, then the money.",
    ],
  },
  {
    version: "2.189.2",
    date: "2026-08-02",
    changes: [
      "Championship GROSS points reach THE PLAYERS CUP (Kerry: 'We didn't wire up gross points from the championships to be added to the players cup!'): the championship-points overlay now accepts a LIST of boards per race — the Cup is one cross-chapter race fed by BOTH cities' championship gross boards (sChampionship POINTS Gross + aChamp POINTS Gross) — so season totals, ranks, and the straight-restack reset ladder all include the championships. Any board failing fails the whole read (no half-cup overlays); the double-count guard stands the overlay down when GG absorbs the points. The Lone Star Cup projection's Players Cup seats read the live combined order, and a fully-posted champ board persists once the reset is official even for races that continue to the TGF Championship and never flip race_final.",
    ],
  },
  {
    version: "2.189.1",
    date: "2026-08-02",
    changes: [
      "The Fellowship Cup's HOW IT WORKS leads with championship scoring (Kerry): the Net Stableford chart's CHAMP column takes the bold orange treatment on a deeper tinted band while REG steps back muted, and the example scorecard now works the Championship BONUS scale — a new orange CHAMP PTS line (every hole +1: eagle +4, birdie +3, par +2, bogey +1, double bogey or worse 0, totaling 17 on the sample card) above the regular REG PTS line kept for comparison. The city NET / Monthly / Fall modals keep the regular-emphasis chart and card.",
    ],
  },
  {
    version: "2.189.0",
    date: "2026-08-02",
    changes: [
      "Post-reset Contests page (Kerry, after GG performed the season points resets): THE FELLOWSHIP CUP is now the landing race, and the two cups lead the race switcher — chips and mobile dropdown both order The Fellowship Cup, The Players Cup, then the city NET races, Monthly, and the fall previews. Race deep links (#race=) still override the landing.",
      "The reset is official, so the reset columns stop reading '(Projected)' on The Fellowship Cup and The Players Cup (and everywhere the column renders) — driven by a new gg_points_reset_official dial the payloads carry as reset_official, so next season's pre-reset phase can read Projected again by clearing one setting.",
      "THE PLAYERS CUP leads with the reset: the POINTS RESET column takes the bold headline treatment and season points step back to a muted SEASON column (Kerry: 'deemphasize season points in the players cup and emphasize the reset').",
    ],
  },
  {
    version: "2.188.17",
    date: "2026-08-02",
    changes: [
      "'+ Add Payment' on the Payouts page works (Kerry: 'Add Payment button doesn't work'): the page's script is a strict-mode IIFE and its inline onclick handlers (tgfRevealAddPay / tgfSaveAddPay / tgfPayHint / onPayTap) were never exported to window, so tapping the chooser — and the method-edit ✎ badge — threw a silent ReferenceError and did nothing. The four functions are now window-exported. Side effect fixed for free: onPayTap now actually runs on Pay taps, so the 'Sent · verifying…' pill engages instead of the button silently relying on the receipt sweep alone.",
    ],
  },
  {
    version: "2.188.16",
    date: "2026-08-02",
    changes: [
      "Aliases are editable on mobile (Kerry: 'I can't see, edit, or add aliases on Mobile'): the mobile customer card's Info tab now carries the same Aliases section as the desktop panel — list with delete, plus name/email add controls — wired to the existing /api/customers/aliases endpoints and loaded by the shared detail-handler pass. A Venmo display name that doesn't match the member (Chuck's 'Charles Fehlis') can now be captured as an alias from the phone, right where the payout mismatch is noticed.",
    ],
  },
  {
    version: "2.188.15",
    date: "2026-08-02",
    changes: [
      "Venmo payout matcher learns codeless event names: the memo-event fallback only understood '[sa]N.N' codes, so Chuck Fehlis' $42.50 championship payment — whose Venmo displays 'Charles Fehlis' (no alias) and whose receipt extraction dropped the memo's payee prefix — resolved to nobody and sat pending while every other payment auto-flipped PAID. The fallback now also matches the memo's full event name ('Winnings for TGF SAN ANTONIO CHAMPIONSHIP', season-contest codes) verbatim against tgf_events, then applies the same unique-exact-amount rule.",
    ],
  },
  {
    version: "2.188.14",
    date: "2026-08-02",
    changes: [
      "GG-posted purses are now the money of record for the GG-recorded games (Kerry: 'we need to allow me to adjust GAMES money'): the payouts assembly takes a Team Net position's pool from the purse posted on the GG board (captured on every re-walk) instead of the matrix split, and a CTP/Longest Putt purse likewise overrides the matrix amount — so rounding a place to a cleaner number on GG (SA championship team places $170/$86 → $42.50/$21.50 member shares) flows into the tracker automatically, including through the hourly auto re-record. The matrix remains the fallback when no purse is posted.",
    ],
  },
  {
    version: "2.188.13",
    date: "2026-08-02",
    changes: [
      "Per-event gross-flight pot mode override (the first small piece of Kerry's FLIGHTS mechanism): the hourly auto-sync force-re-records recent events' payouts, so recording the championships under a temporarily-flipped GLOBAL gross_flight_pot_mode dial got clobbered on the next sync (Austin's Larson/McDonnell reverted to the buy-ins split, $134/$48 vs the $118/$64 GG actually paid). A new gross_flight_pot_mode_overrides JSON dial ({event name: mode}) lets one event pay 'even' while the default stays 'buyins' — set for both 2026-08-01 championships, so every future auto re-record assembles them the way GG paid them.",
    ],
  },
  {
    version: "2.188.12",
    date: "2026-08-02",
    changes: [
      "Docs: Kerry ratified that GUESTS are paid their equal team/cart Net share (included with event fees) — captured verbatim in side-games.md next to the blind-draw rule it mirrors, with the 2026-08-01 Austin Championship as the verified example (guest Matt Larson's $32 team share rides on his own payout row; the 'SHARP, Matt Guest' team-string decoration is the member's own slot, not the guest's).",
    ],
  },
  {
    version: "2.188.11",
    date: "2026-08-02",
    changes: [
      "Docs: recorded both City Championship side-game payouts (SA $1,484 / 33 rows incl. the $156 TGF MVP; Austin $834 / 20 rows), replacing the stale partial team+CTP recordings. Captured Kerry's flight-consolidation precedent (folded the single-player 4th gross flight into 3, pot split evenly — recorded via a temporary gross_flight_pot_mode=even flip, dial restored to buyins) and the pending FLIGHTS-tab mechanism decision in side-games.md.",
    ],
  },
  {
    version: "2.188.10",
    date: "2026-08-02",
    changes: [
      "The payouts assembly learned the ratified 18-hole day type (Kerry 2026-07-31) the Games tab already displays: on a day with a linked same-format 18-hole event there is no $100 MVP cap — the full $8/buyer splits $4 City + $4 TGF, the combined TGF MVP pot records once under the winner's event (exactly like the 9s), and Individual Net gives the capped-away residual back with places scaled proportionally. Single-event 18-hole days are unchanged (capped fold, excess already in Individual Net). Without this, both 2026-08-01 championships would have recorded $100 City MVPs, no TGF MVP money, and an Individual Net pot double-counting the residual.",
    ],
  },
  {
    version: "2.188.9",
    date: "2026-08-02",
    changes: [
      "Individual Net no longer reports 'awaiting results' on a fully-scored 18-hole event: each buyer has TWO scoring_rounds rows (one per imported GG board — the ALL Gross row carries net/playing-handicap as NULL), and last-row-wins picked whichever board imported last. The game-results engine now merges a buyer's rows, letting later rows fill only missing fields, never overwrite a value with NULL (test_game_results_board_merge.py).",
      "Flight labels reach the championship: the per-game flights importer stamped event_id only from the [sa]N.N code convention, so a championship round's Ind Net/Gross/Skins flight cuts would have been captured unlinked and invisible to the payouts assembly. It now falls back to the scorecard import's own round→event linkage (scoring_rounds.gg_league_round_id), and a ?round=<id> scoped reset re-walks one round without forcing the auto sync to re-walk the whole portal.",
    ],
  },
  {
    version: "2.188.8",
    date: "2026-08-02",
    changes: [
      "Ops: a read-only scoring-rounds-orphans diagnostic (unlinked rounds on a date, with every identity field they carry) and a gg_event= selector on the round-link repair — the date+course match also missed because the imported championship rounds carry neither a course link nor a round id, another face of the same string-keyed identity gap Kerry flagged tonight.",
    ],
  },
  {
    version: "2.188.7",
    date: "2026-08-02",
    changes: [
      "Follow-up to v2.188.6: the round-scan importer never stamped gg_league_round_id on the rows it imported, so the round-id repair had nothing to match. The importer now passes the round id through, and the scoring-link-rounds repair identifies the unlinked championship rounds by DATE + COURSE instead (only NULL-event rows are ever touched).",
    ],
  },
  {
    version: "2.188.6",
    date: "2026-08-02",
    changes: [
      "Championship scorecards link to their event: import_gg_scorecards resolved events only by the [sa]N.N code-prefix convention, so the 48 championship rounds (imported clean, all verified) landed with NO event link — invisible to MVP determination and the payouts assembly. Event resolution now tries an exact full-name match first (prefix convention unchanged for coded events), and a scoring-link-rounds repair stamps the already-imported rounds by their GG round id.",
    ],
  },
  {
    version: "2.188.5",
    date: "2026-08-02",
    changes: [
      "The four season-contest payout accounts now file under the SEASON tab on the Payouts page, not EVENTS (Kerry: 'The top four should be under SEASON, not EVENTS') — the tab classifier learned the chapter-prefixed season codes ('SAN ANTONIO Net 2026', 'AUSTIN MATCH PLAY 2026', future gross/Players Cup variants).",
      "Championship game-results import unblocked: the GG round→event mapping keys on the [sa]N.N code embedded in an event's name, and 'TGF SAN ANTONIO CHAMPIONSHIP' carries none — so the championship round's CTP/Team Net winners could never attach to the event and the Payouts assembly reported them missing. scoring-games-import gained an event=<name> override that attaches an UNMAPPED round's winners to the named event (self-mapping rounds are never overridden), clearing the way to record both City Championships' side-game payouts.",
    ],
  },
  {
    version: "2.188.4",
    date: "2026-08-02",
    changes: [
      "Two memo/naming corrections per Kerry: (1) 'FINAL' is dropped from the season payout event names — new recordings create e.g. 'AUSTIN MATCH PLAY 2026', and a new rename bridge (scoring-tgf-event-rename, refuses to merge onto an existing code) renames the four already-created events in place, payout rows and Venmo matching untouched (they key on the event id). (2) The descriptive memo detail is SEASON CONTESTS ONLY — 'I don't want event side game to list out everything. Just the standard is fine' — so the v2.188.3 per-game listing on ordinary event payouts is reverted on both Pay surfaces; season rows keep 'Pool A winner bonus' / '2nd place'. Season recordings are now category-scoped throughout, so the SA Match Play podium can join the event already holding its pool bonuses when that bracket completes.",
    ],
  },
  {
    version: "2.188.3",
    date: "2026-08-02",
    changes: [
      "EVERY PAYOUT MEMO NOW SAYS WHAT WAS WON (Kerry: 'Needs to be descriptive for both TGF and for recipient' — superseding the short-memo convention for ordinary event payouts). Both Pay surfaces (the TGF Payouts page and the per-event PAYOUTS panel) append the winnings detail after the event: 'Jay Horton - Winnings for s9.19 The Quarry — Individual Net LOW 2nd + Skins ×3 + Closest to Pin Hole 5'. Season-contest rows keep their v2.188.2 wording (Pool A winner bonus / 3rd place). The '[Name] - Winnings for [event]' skeleton the auto-confirm matchers key on is unchanged, partial payments describe only the rows they cover, and very long multi-game memos truncate gracefully ('+ more') under Venmo's note limit.",
    ],
  },
  {
    version: "2.188.2",
    date: "2026-08-02",
    changes: [
      "SEASON-CONTEST VENMO MEMOS SAY WHAT THE MONEY IS FOR (Kerry, paying Doug Hamilton's pool bonus: 'Not the right memo for a Match Play Pool Winner' — the prefill read 'Winnings for SAN ANTONIO MATCH PLAY 2026 FINAL', which sounds like podium money). The Pay link now appends the specifics off the exact payout rows being paid: 'Doug Hamilton - Winnings for SAN ANTONIO MATCH PLAY 2026 FINAL — Pool A winner bonus', and a combined payment reads e.g. '3rd place + Pool B winner bonus'. A partial payment describes only the unpaid remainder it covers. The '[Name] - Winnings for [event]' skeleton is unchanged — the Venmo/PayPal/Cash App/Zelle auto-confirm matchers key on the name prefix and that phrase — and ordinary event payouts keep Kerry's ratified short memo (the detail only fires when every row is a season-contest category).",
    ],
  },
  {
    version: "2.188.1",
    date: "2026-08-02",
    changes: [
      "THE LONE STAR CUP MATCH PLAY SEAT NOW POPULATES WHEN THE FINAL IS RECORDED (Kerry, after closing out the Austin matches: the payout sheet filled in but the LSC seat stayed 'to be decided'). Root cause: the Cup seat identifies the champion by customer_id, but bracket saves only ever wrote the winner's NAME — the id column stayed empty until a deploy-time backfill happened to run. Bracket saves now resolve player/opponent/winner ids at write time (principle 6: unresolvable names store NULL, never a guess; clearing a result clears the id so no stale champion lingers), and the Cup projection resolves the name at read time as a fallback so rows saved before this fix populate immediately. The CITY MATCH PLAY seat also now reads 🏆 SECURED like the captaincy — a recorded final is a fact, not a projection — so Luke Youngs holds Austin's seat as '2026 City Match Play Champion'.",
    ],
  },
  {
    version: "2.188.0",
    date: "2026-08-01",
    changes: [
      "CITY CHAMPIONS WEAR GOLD (Kerry, championship night). Once a race is declared final, its champion gets three linked honors: a gold pill on their leaderboard row (🏆 CHAMPION · LSC CAPTAIN on desktop, a 🏆 on phones so names keep their width), a champion strip above the standings (🏆 2026 San Antonio City Champion: Rob Callaway — Lone Star Cup Captain) that persists even after the fall reset folds the FINAL columns away, and the same line in their expanded drill-down. Champions are computed, never typed: the best-ranked BOUGHT-IN finisher (a non-enrolled table-topper can't hold the title — same eligibility as the money).",
      "The Lone Star Cup tab now shows the captaincy as SECURED: the champion's CAPTAIN seat carries a gold 🏆 SECURED chip and gold edge instead of 'projected', the card header counts secured seats, and the captain stream reads the LIVE final standings instead of the pre-championship snapshot.",
      "CO-CHAMPION RULE (Kerry-ratified 2026-08-01): a T1 City NET finish makes co-champions who share the captaincy as CO-CAPTAINS, occupying two of the chapter's seven NET-path Lone Star Cup seats — the Fellowship Cup allocation drops to 5 so the roster stays 12. The leaderboard, strip, and LSC tab all render the co- forms automatically.",
    ],
  },
  {
    version: "2.187.3",
    date: "2026-08-01",
    changes: [
      "WON badges ride the collapsed rows on phones once a race is FINAL (Kerry: 'Can we show the winnings on the top collapsed level like we were showing the projected amounts before?'). The morning declutter moved money into the expanded view because EVERY enrolled row wore a PROJECTED badge and crushed the name column; final money is different — only the placewinners carry a badge and WON is a shorter label. The all-dashes THRU column also stands down on a final race, giving the badges its width back; TDY (championship points) stays until GG absorbs them.",
    ],
  },
  {
    version: "2.187.2",
    date: "2026-08-01",
    changes: [
      "Match Play POOL-WINNER bonuses record into TGF Payouts (Kerry: 'I think pool stage money still needs to be paid'). New scoring-season-payouts mode mp-pools|<chapter>[|record]: one bonus per pool ($20 each per the pinned config) to each pool's rank-1 finisher under the season's ranking rule (D-MP-09 where configured; withdrawn players never win a pool). The rows join the chapter's MATCH PLAY 2026 FINAL payout event alongside the podium — the double-record guard gained an append_category scope so a later wave can join an event that already has rows, but never a second copy of its own category.",
    ],
  },
  {
    version: "2.187.1",
    date: "2026-08-01",
    changes: [
      "The 🔴 LIVE badge stands down once a race is DECLARED final (Kerry: 'It also shouldn't show LIVE anymore') — the green 🏁 FINAL pot chip is the state marker now. The championship TODAY/THRU columns stay until GG absorbs the points into its season totals. The Fellowship Cup follows: when every feeding NET race is final its badge drops too, and its movement-chip history thaws so the final order rotates in once and chips show the day's movement — the same between-events behavior as after any other event.",
    ],
  },
  {
    version: "2.187.0",
    date: "2026-08-01",
    changes: [
      "SEASON-CONTEST FINAL PAYOUTS RECORD INTO TGF PAYOUTS (Kerry, championship evening: 'need payouts for the Points Net for both Chapters and payouts for Austin match play 1st thru 3rd'). New server assembly + MCP bridge (scoring-season-payouts, preview by default, |record to write): City NET reads the LIVE final standings, pays enrolled players only with money flowing past non-enrolled rows, splits ties across combined places (rule 2), and takes pot + ladder from the ratified season_payouts rules on the same entrant count the page projects from; Match Play takes explicit podium placements and prices them off the season's PINNED config + live enrollment count (N=9 Austin: $360 pot − 2×$20 pool bonuses = $320 → $160/$96/$64), pool-winner bonuses deliberately excluded as pool-stage money. Recording finds-or-creates a tgf_events row by code ('<RACE LABEL> FINAL'), refuses to double-record onto a code that already has rows, and delegates inserts to import_tgf_payouts so customer resolution, prize_payout ledger entries, and Venmo reconciliation ride the proven path.",
    ],
  },
  {
    version: "2.186.1",
    date: "2026-08-01",
    changes: [
      "THE CHAMPIONSHIP CAN NO LONGER 'UN-HAPPEN' (Kerry, after closing out GG: 'I refreshed. This is what it came back with. Like the event never happened. That shouldn't occur in any situation'). Two holes closed. FIRST: the admin 'Refresh from Golf Genius' button bypassed the live overlay entirely and painted GG's season portal raw — and GG's portal still shows pre-championship totals even after event close-out, so one tap of the refresh button erased the championship from the screen (the next 60s poll healed it, but it should never paint at all). Every load — forced or not — now goes through the live endpoint, with force=1 riding through so the season snapshot still re-walks GG server-side.",
      "SECOND, the durability guarantee: the moment a race is DECLARED final (the v2.186.0 dial) and every player on the champ board has posted, the finished board — adjusted points, resolved customer ids — is persisted server-side. If GG ever archives, empties, or repoints that board before its season portal absorbs the points, the overlay serves OUR persisted result instead of letting the event vanish. The fallback window is bounded by the FINAL dial, so next season's reset (which clears the dial) can never resurrect an old championship onto a fresh board; and a non-final race keeps the empty read, so clearing test scores still clears the overlay. The double-count guard is unchanged — once GG's totals actually absorb the championship, the overlay stands down as before.",
    ],
  },
  {
    version: "2.186.0",
    date: "2026-08-01",
    changes: [
      "WINNINGS SHOW AS WON, NOT PROJECTED, ONCE A RACE IS FINAL (Kerry, championship evening: 'Can you now show winnings for the finishers. City Net is final'). FINAL is an admin dial (app_settings gg_points_race_final, JSON keyed by race) — a business declaration, not something derived from the board's display state. When set for a race: the payout strip leads with a green 🏁 FINAL chip on the pot, the desktop money badges read WON instead of PROJECTED, the expanded-row stat line reads Won, and the hover explanation says 'Final result' instead of 'if the season ended today'. Tie-splitting and enrolled-only eligibility are unchanged — the same ladder that projected all season is simply declared settled. The Fellowship Cup deliberately keeps PROJECTED (it is decided at the TGF Championship, not today), as does any race not named in the dial. The scoring-champ-live diagnostic reports the flag.",
    ],
  },
  {
    version: "2.185.2",
    date: "2026-08-01",
    changes: [
      "Post-round follow-up caught during production verification: once the round completes, GG clears the champ board's Thru cells to BLANK — never 'F' — so the guard's board-is-final test (which only recognized F/18) would never have consulted the absorption check, and close-out could never have stood the overlay down (double-counted totals once GG folded the championship in). Blank-thru-with-points now reads as final; a scoring player mid-round always carries a hole count, and even a false positive is harmless because the absorption check still requires the snapshot totals to have actually moved before anything stands down.",
    ],
  },
  {
    version: "2.185.1",
    date: "2026-08-01",
    changes: [
      "THE CHAMPIONSHIP NO LONGER VANISHES WHEN THE ROUND ENDS (Kerry, from the course: 'SA is not persisting now the round is over. Make sure both chapters are showing'). The double-count guard stood the live overlay down when the board read final AND the season snapshot was 'fetched today' — but the morning's PRE-ROUND snapshot is also fetched today, so the moment the last group holed out the standings snapped back to season-only, dropping every championship point hours before anyone closed out Golf Genius. The guard is now CONTENT-based: when a board first reads final, each champ scorer's snapshot total is captured as a baseline (per race, dated, in app_settings); the overlay only stands down once a MAJORITY of those totals actually move — which is exactly what GG close-out does and nothing else does on championship day. Pre-close-out refreshes change nothing and keep the final board showing; both chapters run the same guard; a check failure keeps the overlay up rather than eating the points; and a prior day's baseline re-captures fresh so next championship can't inherit it.",
    ],
  },
  {
    version: "2.185.0",
    date: "2026-08-01",
    changes: [
      "POINTS-RESET PROJECTIONS NOW FOLLOW THE LIVE BOARD (Kerry, mid-round: 'I'm currently 3rd for SA City Net, but I'm projecting at 97.5 and I should be 99 with 3rd'). The reset ladder was projected once off the SEASON order and carried through the live merge unchanged, so every mover kept their pre-round reset all day. The live view now re-runs the same ladder — identical methodology, identical coefficient (rebuilt exact from the eligible counts, not the display-rounded copy), identical eligible set — over the live-ranked order, so a player sitting live-3rd projects the 3rd-place reset. Quiet days are untouched: the re-projection only fires when the championship board is actually scoring.",
      "THE FELLOWSHIP CUP UPDATES LIVE during the City Championships (Kerry, same message). The Cup is a pure function of each NET race's reset projection, so it now builds from the LIVE race views instead of the season snapshots — the combined ordering, NET-rank column, reset values, and projected payouts all move with the round. The Cup tab gets the same 🔴 LIVE badge and 60-second tick as the races (payload carries champ_scoring/champ_field summed across both cities). On a non-championship day the live view passes the season standings through unchanged, so the Cup costs one cached champ-board read per race and renders exactly as before.",
      "Cup movement chips FREEZE during a live round: rank-history snapshots stop rotating (a live board reshuffles every minute and would burn the 12-deep history on intra-round noise) and every chip reads against the last pre-round order instead — 'versus where the day started' — resuming normal between-events rotation after the round.",
      "The scoring-champ-live diagnostic now reports each top row's live points_reset so the re-projection is verifiable in production at a glance.",
    ],
  },
  {
    version: "2.184.0",
    date: "2026-08-01",
    changes: [
      "PLUS HANDICAPS COME OFF CHAMPIONSHIP POINTS (Kerry, mid-round): Golf Genius's points game never takes a plus player's give-back strokes, so their board total runs high by exactly their playing handicap — live today that inflated YOUNGS (+4), HORTON (+4) and GRIFFIN (+3) on the SA board. The live overlay now deducts each plus player's playing handicap from their championship points before adding them to the season total. Nobody's name is in code: the plus values are read off the championship SCORECARD board's PlayingHandicap™ column (the same page the hole-by-hole card already walks, cached 120s), so Austin inherits the rule the moment a plus player appears there, and a scorecard-board hiccup falls back to the last good read rather than silently un-adjusting the standings.",
      "The deduction is visible, never silent: the expanded hole-by-hole card states 'Playing handicap +4: 4 pts deducted from today's total', the per-hole PTS row stays the raw Stableford (the cells must add up) while the headline and parity check use the adjusted figure, the drill-down stat line notes the deduction, and the raw board figure rides along in the payload (points_raw) so the scoring-champ-live diagnostic can always show both. Not-started plus players stay None — the deduction lands with their first posted hole.",
    ],
  },
  {
    version: "2.183.3",
    date: "2026-08-01",
    changes: [
      "THE ROOT OF EVERY STALE-LEADERBOARD REPORT TODAY, FOUND AND FIXED. prLoadStandings takes FORCE as its only parameter and reads the active tab from the page — but the 60-second live poll (since v2.174.0, championship-eve) and this morning's return-to-app refresh both called it as (tab, false), passing the tab name where force goes. A truthy force deliberately skips the live endpoint and force-reloads the SEASON standings from Golf Genius. Net effect all morning: the first paint showed live, the first poll tick silently replaced it with a forced season view, and every return to the app did the same — while ALSO re-walking GG's season portal once a minute per open phone for nothing. Both call sites now pass no argument. Confirmed against the new in-process diagnostic (v2.183.2), which showed production computing the live board perfectly the whole time — 32 of 32 scoring — while the page kept asking for the wrong thing.",
    ],
  },
  {
    version: "2.183.2",
    date: "2026-08-01",
    changes: [
      "Ops visibility: new read-only MCP diagnostic (scoring-champ-live:<race>) that reports exactly what the live-overlay computation returns inside the production process — scoring/field counts, errors, absorbed state, top rows, or the precise exception. Added mid-championship when member landings kept falling back to the season view and nothing outside the process could say why.",
    ],
  },
  {
    version: "2.183.1",
    date: "2026-08-01",
    changes: [
      "THE POINTS-RACE POLL IS NOW UNCONDITIONAL (Kerry, third staleness report of the morning — landed on the season view mid-round again). Every conditional version of the poll found a way to strand someone: this time a single failed or slow live fetch at landing fell back to the season payload, which carries no field, so the field-gate never started the poll. The tab now simply ticks every 60 seconds while it's open and visible, retrying the live endpoint each time — one bad fetch heals within a minute instead of freezing the page. The server's 45-second Golf Genius cache keeps upstream traffic flat; the tick still skips hidden tabs and open drill-downs.",
    ],
  },
  {
    version: "2.183.0",
    date: "2026-08-01",
    changes: [
      "NO MORE PULL-TO-REFRESH TO SEE LIVE SCORES (Kerry, mid-round). Two staleness bugs, one root: the live poll STOPPED the moment the board read zero scoring — so a page opened during a quiet moment (test scores just cleared, pre-tee) dropped back to the season view and never woke up when real play started. The poll now keeps ticking as long as the championship board has a FIELD, scoring or not, and the live columns (TDY/THRU with tee times) stay up through quiet moments instead of flickering back to season view. After close-out the absorbed board carries no field and the poll stands down as before.",
      "Returning to the page refetches immediately: iOS resurrects the PWA/Safari tab on a frozen snapshot, so the app now re-pulls the active race the moment it becomes visible again (app-switch return or back-forward restore) — members land on the latest board, not the one from when they left.",
      "This also covers the removed-scores case: cleared test scores now disappear from every open phone within a poll cycle instead of freezing in place.",
    ],
  },
  {
    version: "2.182.3",
    date: "2026-08-01",
    changes: [
      "MATCH PLAY LANDS ON KNOCKOUT while the bracket is seeded (Kerry: 'that's where we're at') — and reverts to Pools by itself next season when the bracket empties, so nothing needs undoing. A manual sub-tab tap or an explicit #mp= deep link always wins over the auto-landing.",
      "The phone PTS column widens a touch — a 3-digit total ('102') was crowding its borders now that season+today totals cross 100.",
    ],
  },
  {
    version: "2.182.2",
    date: "2026-08-01",
    changes: [
      "THE 3RD-PLACE MATCH GOES LIVE (Kerry: 'Jenkins and Barna are live but nothing is populating their match'). Championship day carries TWO match-play games in the Golf Genius round — 'AUSTIN MATCH PLAY CHAMPIONSHIP' for the Final and 'AUSTIN MATCH PLAY 3RD PLACE PLAYOFF' for the consolation (verified on the live widget) — and the live-match walker only ever looked inside the FIRST game matching 'match play'. Hogue/Youngs live there, so the Final populated; Barna/Jenkins live in the second game, so their card sat silent. The walker now checks every match-play game in the round before moving to older rounds. Same fix serves San Antonio's bracket automatically.",
    ],
  },
  {
    version: "2.182.1",
    date: "2026-08-01",
    changes: [
      "THE LIVE FINAL'S OPEN CARD SHOWS ALL 18 HOLES AGAIN (Kerry: 'Matches not showing all holes like it's supposed to and others already do'). The full-card rendering keys off the match length, which is parsed from the TGF event code (a18.x) in the Golf Genius round label — and championship rounds carry no such code, so the live Final's length resolved to nothing and the card collapsed to just the holes played. Two fixes: a round labelled CHAMPIONSHIP reads as 18 holes (City/TGF Championships are 18-hole days), and as a last resort a live card trusts Golf Genius's own column count — GG renders the full card even mid-round. Regular 9-hole matches always carry a parseable code, so nothing changes for them.",
    ],
  },
  {
    version: "2.182.0",
    date: "2026-08-01",
    changes: [
      "THE 3RD-PLACE MATCH IS NOW VISIBLE TO MEMBERS (Kerry, championship morning: 'Not seeing the Austin 3rd place match'). It was hidden behind a manager-only gate from his own 2026-07-19 ruling, made when the consolation might not run this season — it is running, today, so members see the card: both semifinal losers, live scoring through the same 60-second poll as the Final, and the scheduling/split explainer. The record and clear CONTROLS remain manager-only, and the 'hidden from members' tag is gone because it no longer is.",
    ],
  },
  {
    version: "2.181.1",
    date: "2026-08-01",
    changes: [
      "The ENTER EVENTS & CONTESTS banner stands down for championship day only (Kerry) — nobody is buying in mid-championship and the live leaderboard sits a full banner higher on the phone. Gated to 2026-08-01 on the viewer's own clock, so it returns by itself at midnight with no deploy; covers both member pages (Leaderboard and Spotlight).",
    ],
  },
  {
    version: "2.181.0",
    date: "2026-08-01",
    changes: [
      "THE PTS ROW ON THE LIVE CARD IS NOW THE HEADLINE ROW (Kerry): every points value renders bold burnt-orange on a light-orange band — the whole row, sums and TOT included — instead of only the 3-plus holes lighting up. The zebra contrast also got real: PAR and NET wear a visibly darker gray (the earlier tint was too subtle to read as striping), GROSS stays white for the circles and squares.",
      "PROJECTED WINNINGS MOVED OFF THE PHONE ROWS AND INTO THE EXPANDED VIEW (Kerry — saves a full line on every green row). Expanding a player now shows 'Projected $294.40 · Proj. points reset 100' under their name — bringing back the points-reset figure the live table's TODAY/THRU columns displaced. Desktop rows keep the inline PROJECTED badge.",
    ],
  },
  {
    version: "2.180.9",
    date: "2026-08-01",
    changes: [
      "THE 'POINTS AREN'T ADDING' REPORT WAS A LAG READING AS AN ERROR — the math was right. Two different Golf Genius surfaces feed the live card: the per-hole scorecard (which had Callaway's holes 1-2, correctly worth 1+2=3) and the points board (which was still showing 1 pt thru 1 — it hadn't posted hole 2 yet). The card's footnote treated every difference as a discrepancy. It now tells the two apart: when the scorecard is simply AHEAD of the board it says so quietly ('totals sync on its next refresh'), and the amber the-board-is-official warning is reserved for a genuine same-holes disagreement.",
      "THRU heading back to the same size as its neighbours — the column's data font-size override was leaking into the header cell.",
    ],
  },
  {
    version: "2.180.8",
    date: "2026-08-01",
    changes: [
      "Phone header for the day column abbreviates to TDY (Kerry) — the full TODAY label was wider than its tightened column and overlapped THRU. Desktop keeps TODAY.",
      "Austin note, verified live: the whole championship-day treatment (LIVE pill, TDY/THRU columns, movement arrows, tie labels, player cards) is race-generic and Austin's boards carry the identical structure — including the per-player scorecard links the hole-by-hole card walks (probed 2026-08-01, all 16 players). The Austin tab switches to the live view on its own the moment the first Austin score posts to the aChamp POINTS board; until then it correctly shows the season table.",
    ],
  },
  {
    version: "2.180.7",
    date: "2026-08-01",
    changes: [
      "Live-view width tuning (Kerry): every HOLE column on the card is now the same fixed width — a circled score was stretching its own column and the grid read ragged. On the standings, TODAY and THRU tightened (TODAY holds 1-2 digits, THRU at most '10:00a') and the reclaimed width goes back to the Player column, which a long name + handicap was overlapping on at least one row.",
    ],
  },
  {
    version: "2.180.6",
    date: "2026-08-01",
    changes: [
      "MOVEMENT NOW COMPARES RANKS, NOT ROW POSITIONS (Kerry: 'Shouldn't Mary show movement if she's now in tie for 2nd?'). She should. Mary climbed from 4th into a T2 but her ROW stayed fourth from the top — ties order by season points — so the positional arrow read no-move. The day arrow now compares start-of-day rank against the live COMPETITION rank (T2 counts as 2nd): Mary reads ▲2, the man who was already 2nd and got caught reads no move, and two players tied at the same rank all day stop flickering spurious arrows. Pinned by tests on exactly her case.",
    ],
  },
  {
    version: "2.180.5",
    date: "2026-08-01",
    changes: [
      "Live card polish (Kerry): rows alternate white / soft gray (PAR and NET tinted, GROSS and PTS on white) so the five rows read apart at a glance, and the SCORE label now says GROSS — it sits above NET, that is what it is.",
    ],
  },
  {
    version: "2.180.4",
    date: "2026-08-01",
    changes: [
      "Circles and squares on the live card (Kerry): the SCORE row wears the classic marks — red circle for a gross birdie, doubled ring for eagle or better, blue square for bogey, doubled square for double-plus — the same visual language the imported scorecards already use, computed from gross vs par.",
    ],
  },
  {
    version: "2.180.3",
    date: "2026-08-01",
    changes: [
      "NET row is back on the live hole-by-hole card (Kerry: 'that's what the points net is calculated from') — the card now reads HOLE / PAR / SCORE / NET / PTS, so the chain from gross through handicap dots to net to championship points is visible per hole. The handicap dots on the score shrink to half size so they read as marks, not digits.",
    ],
  },
  {
    version: "2.180.2",
    date: "2026-08-01",
    changes: [
      "Phone tee times in the THRU column tighten to '10:00a' / '9:50a' (Kerry) — the full '10:00 AM' was kissing the right screen edge. Hole counts, 'F', and the desktop column are untouched.",
    ],
  },
  {
    version: "2.180.1",
    date: "2026-08-01",
    changes: [
      "TWO LIVE-BOARD FIXES FROM THE COURSE. Ties now label as ties: three players on 94 read T2/T2/T2 with the next man 5th — the live re-rank was a plain 1-2-3 count that mislabeled every tie (the movement arrows stay positional, like the Tour app; only the label groups). Pinned by a test using the exact 94/94/94 case off the live board.",
      "The player expansion works again — v2.179.0's live card renderer was defined inside points-render.js but never exported, so tapping a player on the course threw 'Can't find variable: prRenderChampCard' instead of the card. The internal championship-line path used it from inside the same closure, which is exactly why testing that path never caught this one.",
      "The pinned name is actually visible now: the expansion scroll used a fixed offset and buried the player's name under the sticky navigation stack on phones — the offset is now computed from the real header heights.",
    ],
  },
  {
    version: "2.180.0",
    date: "2026-08-01",
    changes: [
      "SEASON HISTORY RIDES UNDER THE LIVE EXPANSION, COLLAPSED (Kerry, minutes after v2.179.0 landed). Expanding a player during the championship shows today's 18-hole card with a 'SEASON HISTORY ▸' chip beneath it — one tap opens the familiar counted/not-counted event list right there, lazy-loaded so the live card never waits on it, with the in-place scorecard expansions still working inside. The championship line inside the history deliberately does NOT expand to a second copy of the card that is already sitting directly above it.",
    ],
  },
  {
    version: "2.179.0",
    date: "2026-08-01",
    changes: [
      "THE LIVE VIEW NOW READS LIKE THE PGA TOUR APP, TOP TO BOTTOM (Kerry's punch list, sent from the course with the Tour app side-by-side). The three-line LIVE banner on phones is now a slim '🔴 LIVE · 4/32' pill sitting to the right of the collapsed info chip — the leaderboard starts one line lower than the race name. Desktop keeps the full sentence.",
      "Table changes: DAY MOVEMENT gets its own column (green ▲ / red ▼ / a quiet dash), PGA-style, between the rank and the player instead of cramped inside the rank cell. The '+' is gone from TODAY — the column is orange, it reads as today's points without decoration. THRU is wide enough to show a full tee time ('10:00 AM') instead of truncating at '10:0'.",
      "EXPANDING A PLAYER DURING THE CHAMPIONSHIP NOW SHOWS TODAY'S ROUND, NOT THE SEASON HISTORY. The row scrolls to the top of the screen, the player's name pins above the card, and the card is the Tour layout: HOLE / PAR / SCORE / PTS across BOTH nines, all 18 holes always visible with a dash on every hole not yet played — exactly how the Tour app shows a 1:50 PM starter at 7 AM. Handicap dots ride the score as superscripts; the IN block carries the TOT column. Season detail stays one tap away (Full Spotlight), the NET row moved to the Spotlight tier, and the season expansion returns on its own once the board goes quiet.",
      "Players not entered in today's championship keep the season expansion unchanged, live or not.",
    ],
  },
  {
    version: "2.178.0",
    date: "2026-08-01",
    changes: [
      "ON PHONES THE LEADERBOARD NOW SITS ONE THUMB AWAY (Kerry, championship morning). Everything between the points-race name and the table — the bought-in line, the POT and payout chips, the structure note, and the HOW IT WORKS pill — folds behind one slim chip that still carries the headline numbers ('Pot $920 · 23/85 in · details ▸'), so collapsing it loses nothing a member actually checks at a glance. Tap to expand; the HOW IT WORKS button rides inside the folded block and keeps working. Desktop is unchanged, and the orange LIVE banner never folds.",
      "The phone table also drops the Rounds and Buy-in columns (Kerry's call). Who's bought in was already told twice — the green row says it — and the reclaimed width goes to the columns that matter during a championship: PLAYER, PTS, TODAY, THRU. Desktop keeps all columns.",
    ],
  },
  {
    version: "2.177.0",
    date: "2026-08-01",
    changes: [
      "THE LIVE LEADERBOARD NOW READS LIKE A PGA TOUR BOARD (Kerry, championship morning, from his phone mid-test). While a championship is scoring, the standings table swaps its season columns for the day's: the rank carries a green/red DAY-MOVEMENT arrow (start-of-day position vs live position, not last-event movement), TODAY shows the championship points earned so far in burnt orange (+3), and THRU shows the holes completed — or the player's TEE TIME if they haven't started, exactly like the Tour app. RESET and Rounds step aside only for the live day; the column count doesn't change, so nothing shifts, and the season view returns on the next quiet load.",
      "Tee times reach the table because the live merge now carries EVERY board player, not just the ones already scoring — a not-started player keeps points at None (never zero) but brings his tee time along. A player not entered in the championship shows neither, so the three states — playing, waiting to start, not entered — are distinguishable at a glance.",
      "Wording fix on the drill-down and the hole-by-hole card: a player who hasn't started reads 'tees off 9:00 AM' instead of the nonsense 'thru 9:00 AM'.",
      "Ships together with v2.176.0 (the drill-down live figure + hole-by-hole card), merged to main on Kerry's go-ahead after v2.175.1's live verification — his pre-round test scores on the real board proved the fetch/parse/match/re-rank chain end to end before first tee.",
    ],
  },
  {
    version: "2.176.0",
    date: "2026-08-01",
    changes: [
      "THE PLAYER DRILL-DOWN NOW CARRIES THE LIVE CHAMPIONSHIP FIGURE, AND THE CITY CHAMPIONSHIP LINE EXPANDS TO A LIVE HOLE-BY-HOLE CARD (Kerry's ask, built championship morning before first tee). Expanding a player on the LEADERBOARD during the championship shows today's points and 'thru' on the CITY CHAMPIONSHIP line — the same figures the standings row was already showing, passed straight through instead of re-fetched — and clicking that line opens a per-hole card: PAR, GROSS with the handicap dots, NET, and championship-scale points per hole (0/0/1/2/3/4/5 by category, a gross ace pays 9), OUT and IN blocks, live off Golf Genius.",
      "The per-hole card is READ, the points are OURS. Gross strokes and handicap dots come off the player's own scorecard partial on the ALL Net 18 board; pars come off the tee block; NET and the championship Stableford are computed here from those facts rather than trusted. The champ board's own total rides beside ours, and when the two disagree the card says so plainly — the board stays official. Board addresses are a stored setting (gg_champ_scorecard_boards) like the points boards, so next season is a settings change, not a deploy.",
      "One board fetch plus one partial per player, cached 45 seconds per player server-side — the page never walks the whole roster, and a foursome all opening the same card collapses to one Golf Genius fetch. If Golf Genius stops answering mid-round the last good card comes back marked as such instead of a blank panel; a genuine failure paints an error, never silence.",
      "A GUEST IN PLAIN 'FIRST LAST' FORM NO LONGER FALLS OFF THE LIVE BOARD. The champ-board parser required a 'SURNAME, First' comma and the live Austin board (probed overnight) lists 'Matt Larson Guest' without one — he parsed to nothing and was silently dropped. Multi-word comma-less names now pass; section labels and totals rows still don't.",
      "THE 60-SECOND LIVE REFRESH NO LONGER SLAMS AN OPEN DRILL-DOWN SHUT. While a championship is scoring the standings re-render every minute, which destroyed whatever panel a member had expanded — mid-read, every minute, on the busiest day of the season. The refresh now waits while a drill-down is open and resumes on the first quiet tick.",
    ],
  },
  {
    version: "2.175.1",
    date: "2026-08-01",
    changes: [
      "CHAMPIONSHIP-MORNING HOTFIX, SHIPPED BEFORE FIRST TEE: the live overlay was reading every SCORING player as 'not started'. Kerry's pre-round test scores revealed it — Golf Genius renders a scoring player's points cell as '3 (3/0)', total with a front/back split, and the parser ran float() on the whole cell, which fails, so points read as None, the scoring count stayed at zero, the orange LIVE banner never appeared, and no championship points were added. The overlay would have sat silently inert through both City Championships while looking exactly like 'nobody has teed off yet'.",
      "The fix parses the LEADING number of the points cell ('3 (3/0)' → 3, '22 (13/9)' → 22). A bare '-' still has no leading number and still reads None, so the ratified not-started-is-not-zero rule is untouched. Pinned by tests using the exact rows observed on the live SA board.",
      "Shipped as a single surgical change under the championship-day change freeze, explicitly authorized ('Push to main'). Everything else — including the v2.176.0 drill-down/hole-by-hole work — remains on its branch, unmerged, per the freeze.",
    ],
  },
  {
    version: "2.175.0",
    date: "2026-07-31",
    changes: [
      "CITY CHAMPIONSHIP MOVED TO THE TOP OF THE COUNTED LIST, IN ITS OWN COLOUR (Kerry 2026-07-31). It sat at the bottom of the best-10 list where it read like a footnote. It is a REQUIRED, never-droppable addition to the season total, so it now leads the list in burnt orange with rules above and below, distinct from the plain counted rows beneath it. The row can carry a live points figure and a 'thru' marker as the round is played.",
      "DOUBLE-COUNT GUARD ON THE LIVE OVERLAY (Kerry: Golf Genius 'doesn't actually award season points without us closing it out and adding them after the round is done'). That is exactly why the live overlay is needed — and exactly what would break it later. While the round is in progress the stored season snapshot holds no championship points, so adding the live board is correct. Once the event is closed out and the snapshot refreshes, Golf Genius's own total already includes the championship, and adding the board again would show every player inflated by their championship score. The overlay now stands down when the board has gone final AND the snapshot was refreshed the same day, and serves Golf Genius's figure unchanged.",
    ],
  },
  {
    version: "2.174.0",
    date: "2026-07-31",
    changes: [
      "CITY POINTS STANDINGS NOW UPDATE LIVE FROM GOLF GENIUS DURING THE CHAMPIONSHIP (Kerry 2026-07-31). The championship is IN ADDITION to the regular season total, so a player's live figure is their stored best-10 season total PLUS whatever they have earned on today's championship board. The member LEADERBOARD reads both, adds them, and re-ranks — so a player can be seen climbing the table as the round goes on, which is the whole point of showing it live.",
      "The points come straight off the Golf Genius games the admin named: \"sChampionship POINTS Net\" in the San Antonio portal and \"aChamp POINTS\" in Austin. Those board addresses are a stored setting rather than code, so next season's tournament ids are a settings change instead of a deploy.",
      "It refreshes every minute while a championship is scoring, and stops polling on its own once the board goes quiet, so it does not run all season for nothing. The Golf Genius walk is cached server-side for 45 seconds, so a hundred members watching collapse into one fetch rather than a hundred.",
      "A player who has not teed off shows NO championship points rather than a zero, and their season total is left exactly as it stands. That distinction matters on a leaderboard: a genuine nought and a not-yet-started must not look the same.",
      "Matching between the board and the standings is by customer_id first, with the name only as a fallback. Golf Genius spells people its own way — Robert for Roberto Moreno, Mike for Michael Murphy — and that is precisely how points went missing earlier today, so those two are pinned as test cases.",
      "If Golf Genius stops answering mid-round the last good standings stay on screen, marked as such, instead of the leaderboard emptying out in front of everyone.",
    ],
  },
  {
    version: "2.173.0",
    date: "2026-07-31",
    changes: [
      "THE $3,101 HOLE-IN-ONE POT NO LONGER VANISHES — IT WAS BEING WRITTEN INTO A HIDDEN COPY OF THE PAGE (Kerry 2026-07-31: '$3101 would show for a bit, but would just disappear'). The events page renders every event panel TWICE — once into the desktop table and once into the mobile card list — and CSS hides whichever one does not apply. The running-pot line was addressed by a plain HTML id, so two elements in the document shared that id, and the lookup used to fill it returns only the FIRST match: the desktop copy, which is the hidden one on a phone. On whichever render the mobile copy happened to be the only one present the value appeared; the next full re-render recreated both, the fetch filled the hidden desktop line, and the visible one went blank and never recovered. The lines are now addressed by a data attribute and EVERY copy is painted, so which view you are on stops mattering.",
      "The value also survives a re-render now. The last known pot is cached and painted synchronously as the panel is built, so a repaint shows the figure immediately instead of flashing empty while a new request is in flight — and a failed refresh no longer wipes a good number off the screen, it just leaves the last one standing.",
      "CORRECTION to v2.172.0: that release said the pot 'could not persist because nothing could write the carry-in'. That was wrong as a diagnosis of THIS bug — the $3,101 was stored correctly the whole time and was purely a display failure. It is still true that no code path could write the carry-in setting, so the endpoint added in v2.172.0 stays as a genuine gap that was worth closing, but it was not the cause of the disappearing figure.",
    ],
  },
  {
    version: "2.172.0",
    date: "2026-07-31",
    changes: [
      "THE HOLE-IN-ONE CARRY-IN CAN FINALLY BE SET (Kerry 2026-07-31: 'Hole In One Pot is not persisting'). It could not persist, because nothing could write it. The running-pot calculation has read a `hio_pot_carry_in` setting since 2026-07-20 — the balance carried forward from before the Tracker started accruing, ratified at $1,822 — but there was no route, no screen and no tool anywhere in the app that ever SAVED that value. It was read-only by omission. An admin can now click straight through from the GAMES tab banner and enter it; it is stored in app_settings, so it survives redeploys on the Railway volume. Dollar signs and thousands separators in what you type are tolerated; a negative pot is refused.",
      "The running-pot line no longer fails silently. It swallowed every error — a non-OK response became null and the catch block did nothing — so a broken pot, a permission problem and a still-loading pot all looked identical: a banner with a blank second line and no explanation. It now says what went wrong, and the request skips the browser cache so a freshly saved carry-in shows immediately.",
      "When a carry-in IS set the banner says so, e.g. \"Running pot thru TGF: $2,145.00 (incl. $1,822.00 carried in)\", so the accrued figure and the brought-forward figure are never confused with each other. An admin who has not set one sees a 'no carry-in set' prompt instead of silence.",
    ],
  },
  {
    version: "2.171.0",
    date: "2026-07-31",
    changes: [
      "THE 3RD-PLACE MATCH NOW GOES LIVE ALONGSIDE THE FINAL (Kerry 2026-07-31: 'Both the 1st place and 3rd place match will be going at the same time'). It would not have. The live poller only ever looks at bracket cards carrying data-live-* attributes, and the 3rd-place block was built as two static name pills — so tomorrow the Final would have shown running hole dots and a LIVE · thru N status while the 3rd-place match sat dead beside it with nothing but a manual dropdown. It is now rendered through the same card builder as every other match, which gives it those attributes and enrols it in the same 60-second poll automatically.",
      "The GG lookup needs no event of its own — a live match is found by chapter plus the two player names — so the 3rd-place match resolves the same way the Final does. The event name, date and course shown in its header are inherited from the Final, since the consolation is played at the same event and its own bracket row stores no event.",
      "The manual Record / Update / Clear control is untouched and remains the authority. GG's auto-fill of a detected winner deliberately does NOT reach the 3rd-place card: that path requires a standard bracket save button, which this block does not use, so a manager still records the 3rd-place result deliberately rather than having it filled in from a match GG may have mis-paired.",
    ],
  },
  {
    version: "2.170.0",
    date: "2026-07-31",
    changes: [
      "THE 3RD-PLACE MATCH CAN BE CHANGED OR UNDONE (Kerry 2026-07-31, for Robert on the Austin bracket: he 'populated the third place match, but can\'t figure out how to undo it'). He could not, and it was not his fault — the control disappeared the instant a winner was recorded, so a mis-tap was unfixable from the screen even though the API has always treated an empty winner as a clear. The 3rd-place block now keeps its control after a result exists, with the recorded winner pre-selected, an Update button, and a Clear button that reverts the money to the even split between both semifinal losers. Clearing keeps the pairing on the bracket, so the match is still there to play — only the result goes away.",
      "Winner-takes-all was already how it worked and still is: recording a winner gives that player the whole 3rd-place amount, and the even split is only the fallback for when the match cannot be scheduled. On the three-place ladder (8-10 entrants) the 3rd-place winner takes the full 3rd amount and the loser takes nothing; on the four-place ladder (11+) the match decides 3rd versus 4th and both are still paid. The ladder total is identical either way — the match moves money, it never creates any.",
    ],
  },
  {
    version: "2.169.0",
    date: "2026-07-31",
    changes: [
      "TGF MVP NOW RUNS ON 18-HOLE DAYS, NOT JUST 9-HOLE DAYS (Kerry-ratified 2026-07-31, closing an open question from 2026-07-05). Two 18-hole events on the same day now share a combined TGF MVP exactly the way two 9-hole events do — it is the same contest at double the rate. Each city splits its NET-bundle MVP money in half, $4/buyer to its own City MVP and $4/buyer to TGF MVP, and every city's TGF half combines into one pot. Until now the code returned early on any 18-hole event and skipped 18-hole events when scanning the day, so a shared 18-hole TGF MVP was not merely unconfigured — it was unreachable.",
      "NO CAP ON A MULTI-EVENT 18-HOLE DAY, AND NO RESIDUAL. A single 18-hole event still caps City MVP at $100 with the excess flowing to Individual Net, which is what the matrix rows encode. On a day with a second 18-hole event the cap does not apply, so Individual Net has to give that capped-away money back — otherwise the GAMES tab would show the same dollars in two places. At 22 net buyers: a single-event day is $472 Individual Net + $100 MVP; a two-event day is $396 + $88 City + $88 TGF. Both total the $572 NET pot. The Individual Net row is marked \"(multi-event day)\" when this applies and its place ladder scales by the same factor.",
      "NO MIXED-FORMAT TGF MVPs. A 9-hole and an 18-hole event on the same date are two separate contests, each pooling only with its own format. This also fixes the determination engine, which pooled the day by DATE ALONE — a 9-hole and an 18-hole event sharing a date would have been combined into one TGF MVP.",
      "Cross-course comparability is unchanged and deliberate: City MVP is the highest net Stableford points, with no adjustment for course difficulty, so two championship venues are compared on raw points.",
      "The split is derived from the buyer count rather than added as a new matrix column. The live prize matrix is served from app_settings and overrides the seed file wholesale, so a new seed column would have been missing in production — the matrix's own values still take precedence wherever they exist, which keeps the long-standing 9-hole numbers authoritative.",
    ],
  },
  {
    version: "2.168.0",
    date: "2026-07-31",
    changes: [
      "HANDICAP EDITS NOW FLOW BOTH WAYS BECAUSE THE LOOKUP IS KEYED BY customer_id (Kerry 2026-07-31: 'I added in ROSTER and it showed in PAIRINGS, but when I edited in PAIRINGS, it disappeared in ROSTER'). Both screens read one shared handicap index map, and that map was keyed by NAME only — so the whole arrangement rested on a player being spelled identically on their order row and on their profile. When those differ, an edit made on one screen resolves to a key the other screen never looks up, and the value reads as gone. The map now carries a customer_id key alongside every name key, and both the roster cell and the pairing card resolve the id FIRST. This is the same fix the standings points map needed, for the same reason: guiding principle 6.",
      "Every player in the handicap list now carries their customer_id, not just the placeholder-only ones. It was being resolved solely to merge starting handicaps in, so a player with real rounds reached the page with no id at all and nothing downstream could key on one.",
      "Setting a handicap writes the id key into the shared map immediately, so both views repaint off the same entry before the server confirms — the two screens can no longer hold different answers even for a moment.",
    ],
  },
  {
    version: "2.167.0",
    date: "2026-07-31",
    changes: [
      "A STARTING HANDICAP SET ON PAIRINGS NOW LANDS ON THE ROSTER IMMEDIATELY, AND VICE VERSA (Kerry 2026-07-31: 'When I added Mark Villa\'s handicap on PAIRINGS, it did not add it to him in ROSTER. Those need to be immediately synced.'). The value was never lost — Villa's 12.5 saved correctly to his profile. The two screens disagreed because the PAIRINGS card patched its own copy in memory while the ROSTER reads only the shared handicap index map, so the roster kept showing a dash until a reload. The save now writes the new value straight into that shared map — under every name we can tie to that customer_id, because the map is name-keyed and one person can be spelled differently on an order row than on a pairing card — and repaints both views before any network round-trip. The server refresh then confirms it.",
      "The index-map refetch is no longer served from the browser cache. It is fetched immediately after a handicap is saved, and a heuristically cached copy handed back the very map the save was trying to refresh.",
      "A PRELIMINARY HANDICAP IS EDITABLE ON THE ROSTER TOO (Kerry: 'They also both need to be editable'). The roster only ever offered the dash — once a placeholder existed it became plain text, so a typo could not be corrected from the screen where it was most likely made. A P value on the roster is now the same clickable control as on the PAIRINGS card, prefilled with the current number. A handicap computed from real rounds stays uneditable in both places, which is the point of the distinction.",
      "TYPING 12.5 NO LONGER DISPLAYS AS 12.4. A starting handicap is entered as an 18-hole number and halved to get the 9-hole figure; the index map was then re-deriving the 18-hole number from that rounded half, losing a tenth on every odd input. It now reports the number that was actually entered. This affected the roster, the pairing cards, and anything else reading the index map — the stored value was always correct.",
    ],
  },
  {
    version: "2.166.0",
    date: "2026-07-31",
    changes: [
      "PULL AN EVENT'S PAIRINGS STRAIGHT OFF GOLF GENIUS (Kerry 2026-07-31: 'TGF AUSTIN CHAMPIONSHIP already has pairings on GG, because Robert didn't use our generator'). A GG SHEET button now sits beside GENERATE on the PAIRINGS tab. It finds this event's round on its chapter's Golf Genius tee sheet, reads the groups in GG's own seat order, and writes them into the tab — so an event someone else paired lands here intact instead of being retyped or regenerated into something different. Seats 1 and 2 ride together and 3 and 4 ride together, the same cart rule our own saves follow, so the rode-with history stays true.",
      "It works on events that have NOT been played yet, which is the whole point of a per-event button. The nightly history grab walks played rounds only, off the results widget; this reads the tee-sheet widget's own round selector, and that selector is the one place upcoming rounds are listed. The AUSTIN CHAMPIONSHIP sheet was sitting there today.",
      "The round is matched, not guessed. An event code on both sides settles it outright, and a code that disagrees is a hard no rather than a near miss. Where our name carries no code — 'TGF AUSTIN CHAMPIONSHIP' against Golf Genius's 'a18.4 AUSTIN CHAMPIONSHIP | Falconhead' — the name and course words decide, with the date breaking ties when GG has not truncated it off the end of the label. If no round wins clearly, you are asked to pick from the list; you are never handed the wrong sheet quietly.",
      "The import then says what did NOT line up: GG names with no matching customer profile, and players registered here who are missing from the GG sheet. That reconciliation is most of the value of importing someone else's pairings, and it is the part you cannot see by looking at the finished grid.",
      "The tee-sheet parser now reads Golf Genius's markup structurally rather than splitting the flattened text on surnames. A player GG prints as a plain name instead of 'SURNAME, First' — which is common for guests and 1st timers — used to be dropped, and dropping one name shifts every seat behind it and silently corrupts the cart pairs. Fivesomes are read in full, shotgun sheets label by hole instead of by the one repeated time, and Golf Genius's duplicate mobile rows are ignored.",
      "Importing one leg of a 9/18 combo event no longer wipes the other leg.",
      "PRELIMINARY HANDICAPS SHOW AND EDIT ON THE PAIRINGS CARDS (Kerry: 'Jacob Williams not filling HCP on pairings... Also add P to preliminary handicaps on PAIRINGS as well, AND allow us to edit them'). A starting handicap set on the ROSTER left the pairing card showing a dash, because the card only ever saw indexes computed from rounds. The card now falls back to the live handicap map and renders a starting handicap the way the roster does — the number with a P beside it, in the placeholder styling — so it never reads as an established TGF Handicap. Clicking it opens an edit with the current value filled in; a computed index stays uneditable, as it must.",
    ],
  },
  {
    version: "2.165.0",
    date: "2026-07-31",
    changes: [
      "THE MISSING POINTS WERE A customer_id MISTAKE, AND IT WAS MINE (Kerry 2026-07-31: 'Actually our list is showing their names with points!?!?!'). Moreno and Murphy resolved to their profiles perfectly — the Contests board was showing 51 and 29 points with their handicaps beside them the whole time, which is only possible once customer_id has resolved. The pairing card sent the points map over the wire keyed by NAME ONLY; I filtered the customer_id keys out and left a comment saying the UI matches on display name. Golf Genius spells them 'MORENO, Robert' and 'MURPHY, Mike' where our roster says Roberto Moreno and Michael Murphy, so the name key could never match and the card showed a dash. Both maps now carry customer_id keys alongside the names, and the card reads the id first — guiding principle 6, which is exactly what this session has been about.",
      "GOLF GENIUS NAMES NOW RESOLVE THROUGH THE NICKNAME RULE, AND THE MATCH IS CAPTURED AS AN ALIAS (Kerry: 'Aliases should be used to capture anyone in GG that can't be matched'). The standings ingest tried the exact-name and alias lookups and gave up; it now also tries the surname + first-initial person key that match play and partner requests already use, so Robert/Roberto and Mike/Michael collapse. A match on that rung WRITES a customer_aliases row, human-cased, so it is permanent, visible on the profile, and reusable by every other GG path — the second pass resolves on the fast path instead of re-deriving. Ambiguity still refuses: Daniel and Danny South share a person key, so 'SOUTH, Dan' resolves to nobody rather than guessing.",
      "AN AUDIT FOR THE REST OF THE FIELD (Kerry: 'Check rest of points to see if we're missing anyone else'). GET or POST /api/admin/gg-points-identity-audit re-runs the resolver over every stored standings row, links whatever the nickname rung can now match, captures those aliases, and returns per-race counts plus the names still unmatched. An unresolved row still shows on the Contests board — it has a name and a points total — but is invisible to anything that joins on identity: pairings order, the points column, flighting, payouts. This lists exactly who is in that state.",
    ],
  },
  {
    version: "2.164.1",
    date: "2026-07-31",
    changes: [
      "A MISSING POINTS FIGURE NOW SAYS WHY (Kerry 2026-07-31: 'all points are not showing up now, like for Murphy & Moreno'). A dash in the points column has two completely different causes and the same appearance: the player is absent from the race standings altogether, or they ARE on the board and our snapshot holds no points total for them. The first is an enrolment question, the second is a data question — hovering the dash now states which one it is instead of leaving both looking like the same failure. Murphy and Moreno are the second kind: they are ranked (which is why they are seated mid-order rather than teeing off first with the unranked), but their points cell came through the Golf Genius widget non-numeric, so nothing was stored to show. A genuine zero still renders as 0, not a dash.",
      "The click-the-dash starting-handicap control on the pairing cards no longer depends on one payload field. It reads customer_id from EITHER the pairings roster or the event's registrations, whichever has it — relying only on the newer /pairings field meant a cached response left the dash inert with no hint as to why. To be clear about which column it is: the control is on the HANDICAP dash, never on the points dash, and never on a player who already has an index — a real index is computed from rounds and must not be typed over.",
    ],
  },
  {
    version: "2.164.0",
    date: "2026-07-31",
    changes: [
      "UNDO / REDO ON THE PAIRINGS SHEET (Kerry 2026-07-31: 'I dragged and dropped Jay, and 9:00a adjusted, so I can\'t simply drag him back to his one spot. I\'d have to rearrange with the swapping tools.'). Seat compaction is what made a move genuinely irreversible by hand — dragging a player out reshuffles the group behind them, so dragging them back does not restore the original seats. The honest fix is a real undo rather than a cleverer drag. Undo and Redo buttons sit at the head of the action row, greyed when there is nothing to step to, and Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z do the same.",
      "Every group edit is a step: drag-and-drop, click-to-Move, player / cart-pair / group swaps, a hole-label change, and Generate itself — so you can undo your way back out of a regenerate you didn't want. Forty steps are kept. Making a fresh change after undoing drops the redo branch, the way any editor behaves.",
      "Snapshots cover the GROUPS only — who is in which group, in which seat, under which slot label. Undo deliberately does not rewind the pairing mode, the race selection, or the requests panel; none of those are things a manager would expect Undo to touch.",
      "Undo also tracks WHICH position is the saved one, so stepping back to the sheet you last saved reports Saved again instead of a phantom unsaved change. Clear starts the stack over, since it wipes the server copy and there is nothing left to undo back to.",
    ],
  },
  {
    version: "2.163.0",
    date: "2026-07-31",
    changes: [
      "SET A STARTING HANDICAP FROM THE PAIRING CARDS (Kerry 2026-07-31). The dash in a player's handicap column is now clickable on the PAIRINGS tab exactly as it already was on the ROSTER — tap it, type an 18-hole starting number, and it lands on that player's customer record as a placeholder until enough rounds establish their real TGF Handicap. Same endpoint, same rules: offered ONLY where there is no handicap on record (a real index is computed from rounds and must never be typed over), and only where the registration is linked to a customer_id, since the placeholder lives on the customer record and an unlinked row has nowhere to put it.",
      "The card updates immediately instead of sitting on the dash until a reload. Pairing groups carry their own copy of each player's index — it rides on the generated or saved groups — so refreshing the items and events lists alone would have left the old dash on screen; the save now patches every group and roster entry naming that player with the value the server returned.",
    ],
  },
  {
    version: "2.162.0",
    date: "2026-07-31",
    changes: [
      "SEATS CLOSE UP AFTER A MOVE, WITHOUT BREAKING A CART (Kerry 2026-07-31). Pull a player out of seat 1 or 2 while seats 3 and 4 are both filled and that bottom pair now promotes to the top cart together, with the leftover single dropping to seat 3 — so the open spot always ends up at the BOTTOM of the card instead of leaving a hole at the top. It runs the moment a drag is committed, and on click-to-Move too.",
      "The rule is deliberately not a naive shift-everyone-up. Carts ARE seats 1&2 and 3&4, so sliding each player up one would split the surviving pair and marry two people who were never cart partners — and rode-with history is derived from exactly those seat numbers, so that would be wrong in the saved data, not just on screen. Instead INTACT carts claim the cart slots in order and the leftovers fill what remains, top down. Verified across every shape: pull from 1, from 2, from either bottom seat, fivesomes, already-compact groups (untouched), and the case where both carts are already broken.",
      "ALUMNI grey lightened to #aab0bb — same slate family, just softer (Kerry: 'Lighter grey for the alumni. I like the type of gray though'). It is the lightest step in that family that still clears 70 RGB separation from every other band; anything lighter starts closing on the in-the-race green.",
    ],
  },
  {
    version: "2.161.1",
    date: "2026-07-31",
    changes: [
      "FIXED: A PLAYER DRAGGED INTO A 5TH SEAT VANISHED (Kerry 2026-07-31 — 'when I released Jay Horton from 9:00a to 9:10am group he disappeared'). He was never lost: the move worked, the data was right, and the group card simply refused to draw him. The seat renderer looped a hard 1..4, so anyone landing in seat 5 was rendered nowhere while their old seat correctly showed as open. The card now draws as many seats as it needs — five whenever the event allows fivesomes OR a fifth seat is actually occupied — with a cart divider before the odd rider, since carts hold two.",
      "THE PAIRING-METHOD SAVE NO LONGER FAILS IN SILENCE. A 500 from the server does not reject a fetch, so a rejected save looked exactly like 'it just didn't persist' — which is how this went four rounds without a diagnosis. The save now inspects the response and, if the event could not be updated, says so once with the server's reason and notes that the choice is still held in this browser. The panel's own reopen path also falls back to the browser copy when the server value is missing, so a save that never reached the database is no longer lost on the very reopen it was meant to survive.",
      "GUEST AND 1ST TIMER NOW USE ONE PALETTE ACROSS THE APP (Kerry 2026-07-31). The EVENTS roster, the PAIRINGS cards and the CUSTOMERS list all shade those two statuses identically — GUEST in a half-strength 1st-timer orange, 1ST TIMER in the full orange. The roster was still on the old pink, and the customers list had a third vocabulary entirely (yellow for 1st timers, plain white for guests), so the same person changed colour depending on which screen you were looking at.",
    ],
  },
  {
    version: "2.161.0",
    date: "2026-07-31",
    changes: [
      "THE PAIRING METHOD FINALLY STICKS — ROOT CAUSE FOUND. Two real defects, not one. First, the race-pulldown handler referenced a variable that does not exist (pairingsState instead of pairingsData), so it threw a ReferenceError every time the race changed and the choice was never recorded — that bug predates this week. Second, the mode was being seeded from the EVENTS LIST payload, which can be a cached copy from before the column existed; if that first render arrived without it, the panel locked itself to Random for the session. The saved method now rides on the PAIRINGS fetch itself — GET /pairings returns pairing_mode and pairing_race_key in its event block — which is requested at the moment the panel opens and therefore cannot be stale. The server row remains the source of truth, with the localStorage mirror still behind it.",
      "GENERATE, CLEAR AND SAVE MOVED TO THEIR OWN ROW, LEFT-ALIGNED (Kerry 2026-07-31), instead of being pushed to the right of a crowded first line where they got squeezed out.",
      "COLOUR BANDS SETTLED. GUEST is now a half-strength version of the 1st-timer orange rather than pink ('I have never liked GUEST Pink'), and ALUMNI is grey rather than the cream or the violet, both of which were too faint to pick out. Measured rather than eyeballed: every pair of the five bands clears 76 RGB separation, and every band holds at least 6.8:1 text contrast against the row text, so names, points and badges stay readable on all of them.",
      "POINTS, HANDICAP AND TEE ARE NOW CENTRED, and the points column is ruled on both sides so it reads as its own column down the card — the same treatment the Player Rankings table gives its points.",
      "DRAG A PLAYER ONTO ANOTHER GROUP TO MOVE THEM — including as a 5th (Kerry 2026-07-31). Pick up any player and every other group grows a rail telling you what releasing will do: '+ DROP HERE (3 of 4)', or '+ ADD AS 5TH — MAKES A FIVESOME' when the group is already full, or a red 'GROUP FULL (5)' where it cannot take another. Dropping onto the fivesome rail does not ask for confirmation, because dragging onto a rail that says FIVESOME already is the manager asking; click-to-Move still confirms. Six is refused, and a player can only be dragged within their own 9-hole or 18-hole sheet.",
    ],
  },
  {
    version: "2.160.2",
    date: "2026-07-31",
    changes: [
      "ALUMNI IS NOW INDIGO (Kerry 2026-07-31: 'that one is hard to see'). The Player-Rankings REJOIN cream reads as nearly white against a pairing card, which is fine for a small pill but not for a whole row. Checked the candidates against the four fixed bands rather than eyeballing it: a pale violet turned out to sit closer to the guest pink than the cream did to white, so it went too. Indigo-300 (#a5b4fc) won — it carries the same visual weight as the 1st-timer orange, clears 83 RGB separation from its nearest neighbour where the cream cleared 38, and still holds 8.6:1 text contrast. Every pair of bands is now clearly distinguishable except white-vs-guest-pink, which is the ratified roster colour and stays as it is.",
    ],
  },
  {
    version: "2.160.1",
    date: "2026-07-31",
    changes: [
      "HARDENED THE PAIRING-METHOD PERSISTENCE (Kerry 2026-07-31: 'the STANDINGS button should still be highlighted when I reopen the event'). The server-side save shipped in v2.160.0 and is authoritative — the setting follows the manager to any device — but it could fail quietly in two ways, and both are now covered. A localStorage mirror is written alongside every mode change, so the choice survives even if the PATCH is refused or the events payload hasn't picked up the new column yet. And the seed no longer locks itself in against a stale event object: it waits until the payload actually carries pairing_mode before deciding it has read the saved value, instead of pinning the panel to Random for the rest of the session on the first render that arrived without it.",
    ],
  },
  {
    version: "2.160.0",
    date: "2026-07-31",
    changes: [
      "ALUMNI GET THEIR OWN COLOUR (Kerry 2026-07-31: 'Why is Wade Amen shown Pink? Former members (ALUMNI) need their own color'). The pairing card was deciding member-or-not from a boolean, so a FORMER member fell through to the guest pink. It now reads the player's tier from derive_member_financial_status_bulk — the same D1 financial truth Player Rankings chips with — which returns member / alumni / guest properly. Alumni render in the REJOIN cream (#fdf3e7) that Player Rankings already uses for a lapsed membership, so the two screens agree about who someone is. Five bands now: IN the race (green), MEMBER NOT IN (white), ALUMNI (cream), GUEST (pink), 1ST TIMER (orange) — the last two straight off the ROSTER's palette.",
      "STATUS VOCABULARY FOLLOWS HOUSE CASING. The legend and row tooltips now use the app's own uppercase status tokens — MEMBER, ALUMNI, GUEST, 1ST TIMER — instead of sentence case, matching how the roster and Player Rankings already write them.",
      "The pace badge moved to the FAR RIGHT of each player row. It is staging information, not something you read a player by, and sitting beside the name it pushed the whole line out of alignment.",
      "Tee names are abbreviated so every column lines up: Forward renders FWD (Middle MID, Back BACK, Championship CHMP, Senior SR), which was the one value wide enough to stagger the rows against the age bands beside it. All four right-hand cells — points, handicap, tee, pace — now have fixed widths, so they form true columns down a card and across cards instead of drifting with content.",
    ],
  },
  {
    version: "2.159.1",
    date: "2026-07-31",
    changes: [
      "PAIRING-CARD COLOURS SETTLED (Kerry 2026-07-31). Members IN the game keep the Player-Rankings green. Members NOT in the game are now plain WHITE — 'no color like in our standings', where a member who hasn't bought in is the ordinary case rather than something to flag; the amber shipped an hour earlier is gone. Non-members reuse the ROSTER's own colours so the two screens read the same: GUEST pink (#fbcfe8), 1ST TIMER orange (#fdba74). Which of those two a non-member gets comes from the order label, but whether they are a non-member at all still comes from the ROSTER — the label can only pick the shade, never the tier.",
      "The legend follows, with an outlined white swatch for the not-in-the-game tier so the fourth state still reads at a glance.",
    ],
  },
  {
    version: "2.159.0",
    date: "2026-07-31",
    changes: [
      "THE PAIRING METHOD NOW STICKS TO THE EVENT (Kerry 2026-07-31: 'Whatever method (Random | ABCD | STANDINGS) was selected should persist when the event is reopened'). The choice lived only in the open page's memory, so every reopen — or reload, or a different manager on a different device — reset it to Random. It is now a property of the EVENT (events.pairing_mode), saved the moment a mode button is tapped, alongside the season contest a STANDINGS event pairs off (events.pairing_race_key). Reopening the event comes back exactly as it was left. Saving is fire-and-forget so a slow network never blocks the click, and the in-memory event object is updated in step so the buttons don't snap back on the next re-render.",
      "An event reopened in STANDINGS mode now loads its race list without waiting for a click — previously the pulldown would have sat on 'Loading races…' forever, since the fetch was wired only to the mode button.",
      "This also fixes the points column and the in/out colour bands disappearing on reopen for good: they were following the mode, and the mode was resetting.",
    ],
  },
  {
    version: "2.158.0",
    date: "2026-07-31",
    changes: [
      "IN / NOT-IN / NON-MEMBER COLOUR BANDS ON THE PAIRING CARDS (Kerry 2026-07-31). Each player row is now shaded by where they stand with the race being paired off, using the same convention Player Rankings uses for who's bought in: GREEN for a member who is IN the City Net race, AMBER for a member who is NOT bought in, GREY for a non-member. A legend sits above the groups and every row carries a tooltip naming the race. Membership comes from the ROSTER via _ls_is_member, never from the order label — the field is full of '1ST TIMER' rows that are members and '1ST TIMER' rows that aren't — and unknown membership is treated as member, so nobody is badged a non-member on missing data.",
      "FIXED: the points column vanished on a saved sheet. It was gated on the pairings mode being STANDINGS, but the mode resets to Random whenever the panel reopens, so reloading a standings sheet lost the column. Points and colour bands now show whenever the standings data is present, in any mode — knowing who is in the race is useful on a Random sheet too.",
      "FIXED: three columns, not two. The card minimum was set to 330px, which fit only two columns at the 1080px content width; it is now 300px and the non-name cells are tightened, so a standard desktop lays out THREE groups across with full names intact. The grid still uses auto-fit, so it reflows to two and then one as the window narrows rather than squeezing.",
    ],
  },
  {
    version: "2.157.0",
    date: "2026-07-31",
    changes: [
      "STANDINGS PAIRINGS SHOW THE POINTS (Kerry 2026-07-31). In STANDINGS mode each player now carries their season-points total from the selected race, so the number that built the order is visible on the sheet instead of implied. Keyed off the same map as the rank — customer_id first, name forms as a fallback — so a player who is ranked always shows a figure and one who is not shows a dash with a tooltip naming the race. Points ride on the SAVED sheet too, not just a freshly generated one: GET /pairings returns them read-only (a large max-age, so opening the panel never triggers a Golf Genius fetch — the point-of-use refresh stays with Generate).",
      "FULL NAMES ON THE PAIRING CARDS. The group grid packed four 220px columns across, which truncated almost every name to 'Kerry Nie…'. Cards are now a 330px minimum and the grid uses auto-fit, so it lays out only as many columns as genuinely fit — three across on a standard desktop, dropping to two and then one as the window narrows — and names render in full instead of being clipped. A single very long name wraps rather than being cut.",
      "Two smaller corrections in the same pass: the Move drop-target highlight now respects an event's fivesome setting instead of assuming four, and a seeded group being topped up from the free pool fills to the event's group size rather than always to four.",
    ],
  },
  {
    version: "2.156.0",
    date: "2026-07-31",
    changes: [
      "PACE STAGING NO LONGER OVERRIDES THE STANDINGS ORDER — RULED (Kerry 2026-07-31: 'the pace rule kind of becomes obsolete when we do pairings by standings'). The SA Championship sheet said all the right things — 'leaders go off LAST', '28 of 32 players are in the standings' — and then came out in perfect DESCENDING PACE order (2.5, 2.5, 2, 2, 2, 2, 1.75, 1.25), with the four unranked players stranded in the middle instead of teeing off first. Pace staging runs after the groups are settled and re-sorts them, which silently threw the entire standings order away. In STANDINGS mode it is now skipped — for tee times and for shotgun slot ordering alike — and the pairings notes say so instead of leaving the manager to spot it. Group pace is still COMPUTED and shown per group as a read-out; it just doesn't move anybody. Random and ABCD stage by pace exactly as before.",
      "THE GENERATOR NOW HONORS REQUESTS IN SIGNUP ORDER, LIKE THE PANEL DOES (Kerry 2026-07-31: 'Nor is it honoring requests'). Richard Palacios was split from Larry Anthis even though the requests panel showed that pairing active. The generator built PRIVILEGED units first — guest requests and manager-approved ones — so the later approved 'Larry Anthis → Michael Murphy' claimed Larry before the earlier 'Palacios → Anthis' was ever considered, and Palacios lost a request first-come said he had won. Both sides now walk the same list in the same signup order through one shared builder (_build_bound_units), so Palacios claims Anthis and the approval JOINS that unit as a threesome — which is what approving was defined to mean. A panel badge that Generate won't honor is the failure mode this closes for good.",
      "Verified end to end on the SA field: the host foursome (Daniel South + Williams + Villa + Kypuros) holds, the reciprocal Gus Vasquez / Chuck Fehlis pair holds, Palacios + Anthis + Murphy become one threesome, nobody lands in two units, and a fifth player still cannot join a full group no matter how privileged the request.",
    ],
  },
  {
    version: "2.155.0",
    date: "2026-07-31",
    changes: [
      "FIXED: GENERATE CRASHED ON A TIE. Clicking Generate in STANDINGS mode died with 'invalid literal for int() with base 10: T8' — Golf Genius marks a tie with a leading T ('T8' = tied for 8th), and yesterday's rank-map change fed that straight to int(). Introduced in v2.154.1 and fixed here; ranks now parse the digits out of any GG spelling and a tie KEEPS its shared position rather than being silently renumbered.",
      "TIES BREAK ON HANDICAP, THEN LAST NAME (Kerry 2026-07-31). Tied players used to fall back to whatever order the portal listed them in. The lower handicap is now treated as the better position — so within a tie the better player goes off later, as the leader does — and an exact handicap tie is settled alphabetically by last name. A player with no handicap on file sorts last inside a tie rather than jumping ahead of a known-good one.",
      "FIVESOMES (Kerry 2026-07-31). Two ways in, both requiring a manager to ask for it. (1) MANUAL: drag or Move any player into a full group and confirm the prompt — 'That group is already a foursome. Add a 5th anyway?' Six is refused outright. (2) EVENT SETUP: a new 'Allow fivesomes' checkbox on the add/edit event modals builds the WHOLE sheet from fivesomes, with FOURSOMES as the short groups — the same relational rule threesomes follow on a 4-based sheet (20 players → four fivesomes; 32 → four fivesomes and three foursomes; 19 → three fivesomes and a foursome). A field too small to tile as fivesomes falls back to the ordinary 4-based sheet rather than inventing a shape. Off by default, so nothing changes for any existing event.",
      "THE FOURSOME CEILING IS NOW THE EVENT'S CEILING. Host-and-guests groups, guest latitude, and manager approvals all stopped at four; on a fivesome event they stop at five, and the 'honoring this would make five' message counts correctly either way. The manual add-a-5th path bypasses the ceiling entirely, because that IS the manager asking.",
      "The event_pairings table capped cart_pos at 4 with a CHECK constraint, so a hand-added 5th player could not have been SAVED even once placed. The table is rebuilt in place on first use to allow seat 5 — existing rows are carried over untouched, and the migration is idempotent. Carts remain seats 1&2 and 3&4; the fifth rider is an extra and is recorded as playing with the group but riding with nobody.",
      "GENERATE STAYS REACHABLE WITH THE REQUESTS PANEL OPEN (Kerry 2026-07-31). The pairings controls bar now sticks below the nav while you scroll a long requests or locks list, and the action buttons live in one group pinned right instead of being pushed around by a flexible spacer that could shove Generate out of view on a crowded row.",
    ],
  },
  {
    version: "2.154.1",
    date: "2026-07-31",
    changes: [
      "STANDINGS PAIRINGS WERE NOT IN STANDINGS ORDER AT ALL. The SA Championship sheet said '0 of 32 players are in the standings' and was therefore random order wearing a STANDINGS label (Kerry 2026-07-31). The rank map keyed on a plain lowercased player name, but the Golf Genius portal stores names as 'LAST, First' — so not one of the 32 matched and every player was treated as unranked. The map is now keyed by customer_id FIRST, which both the standings snapshot rows and the event roster already carry, with name keys kept only as a fallback for a standings row that never resolved to a profile. Name keys now include the portal's raw spelling AND the 'First Last' forms _gg_name_candidates derives from it, so even an unlinked row matches. This is the third place this session where name-string matching was silently doing nothing that customer_id matching does correctly — guiding principle 6, again.",
      "A TOTAL MISS IS NOW LOUD. When none of the field matches, the notes say 'NONE of the field matched the standings, so this is not a standings order at all' rather than a quiet '0 of 32'. On a partial miss the unmatched players are NAMED (up to six, then a count), so the next mismatch is diagnosable instead of a shrug.",
      "THE TEE SHEET PACKS CLEANLY AGAIN. Two players 'matched no slot' and were dumped into the smallest group on a 32-player field that divides evenly into 8 foursomes. The fill cursor only ever moved FORWARD, so a partner pair arriving at a group of three skipped that group permanently and left a hole nothing could reuse; the units at the tail then had nowhere to go. Groups now fill from the LAST group BACKWARDS with the leader's unit placed first, which also makes 'leaders go off last' exact rather than merely likely — every hole now lands at the FRONT of the sheet, among the unranked players, where the slop costs nothing. Verified across 4,000 randomized fields (5–44 players, random partner pairs): nobody lost or duplicated, no group over a foursome, no split pairs, and the points leader in the final group every time.",
    ],
  },
  {
    version: "2.154.0",
    date: "2026-07-31",
    changes: [
      "GUESTS MAY JOIN A GROUP THAT IS ALREADY CLAIMED; MEMBERS BRANCH OUT (Kerry 2026-07-31). Villa and Kypuros bought their OWN 1st-Timer spots on separate orders and both requested Dan South, so no host link existed to save them and first-come outranked them both. Kerry's rule: 'It's a system to give all guests the ability to feel the group out and play with who they want, but require the members to branch out, beyond a single player request.' A guest's request is now honored even when their partner was claimed earlier — the guest JOINS that group rather than losing to it (GUEST OK badge) — while a member's request onto a claimed player stays OUTRANKED, with a reason that says so. Membership is decided by the ROSTER via _ls_is_member, never by the order label: the SA field is full of '1ST TIMER' rows that are members and '1ST TIMER' rows that are guests, and the label alone can only rule someone OUT.",
      "MANAGERS CAN APPROVE AN OUTRANKED REQUEST. The red OUTRANKED badge is now the override control — tap it to approve, tap the green APPROVED badge to put first-come back. An approved request JOINS the group that claimed its partner instead of displacing whoever got there first, so honoring the override costs nobody their pairing. Stored per requester per event in the new pairing_request_approvals table, so it survives a re-generate and a reload, and it is reversible. POST /api/events/<id>/pairings/requests/approve {requester, approved}, manager tier.",
      "A FOURSOME IS THE CEILING IN EVERY CASE. Guest latitude, host groups, and manager approval all resolve by joining a group, and all three stop at four — a fifth player stays outranked with 'honoring this would make five. Suppress a request in that group to make room.' Approving cannot override arithmetic.",
      "The request simulation moved from PAIRS to UNITS internally, which is what made 'join the group that already exists' expressible at all — a pair-only model could only ever say win or lose. The generator was moved to the same model: guest requests and approved requests are folded into the bound units by the identical join-up-to-a-foursome rule the panel simulates, so a request Generate can't honor is exactly the one the panel still shows as outranked.",
    ],
  },
  {
    version: "2.153.1",
    date: "2026-07-31",
    changes: [
      "GUESTS ARE NO LONGER OUTRANKED BY THE MAN WHO PAID FOR THEM. The host-group rule shipped in v2.153.0 but did not fire in the field: on the SA Championship roster Jacob Williams was grouped with Daniel South while Mark Villa and Orlando Kypuros — both requesting the same Daniel South, all three on Daniel's order — were still badged OUTRANKED. The cause was that the rule looked ONLY at the 'Purchased by <buyer>' note, which the guests' rows did not carry. Who paid is now derived structurally from the shared order_id: a multi-spot order has exactly one payer, and everyone else on it had their spot bought. The buyer is identified by the same rule the Transactions order-group header uses — the row that kept customer_email and carries no Purchased-by note. The note is still read first where it exists, since it is an explicit statement and it is the only signal when a host buys a guest's spot on a separate order.",
      "THE GENERATOR NOW BUILDS THE FOURSOME THE PANEL PROMISES. Badging the guests CONFIRMED while the generator still paired them off two-at-a-time would have been worse than no badge — the panel would have been lying. Host-and-guests units are now built inside Generate as well, placed below Match Play ('Match Play is king' still wins any shared player) and above ordinary partner pairs, in Random and STANDINGS modes alike, and locked against the swap improver so a later optimization pass can't split them. Panel and generator compute the group from the same function, so they cannot drift apart.",
      "THE FIRST CLAIM ON A HOST NO LONGER SHOWS A CONFIRMED BADGE (Kerry 2026-07-31: 'Not sure why Jacob Williams has the CONFIRMED badge'). The earliest guest to claim the host is an ordinary first-come win, identical to any other opening request, so it now renders plain like Gus Vasquez's does. CONFIRMED is reserved for a request that would otherwise have READ as a loser — a reciprocal request, or a guest joining a host already claimed.",
      "Guest-of-a-guest chains collapse to the ultimate host, and a cycle in the paid-for data is dropped rather than looped over — two people cannot have bought each other's spot, so a cycle means the data is wrong, not that there are two hosts.",
    ],
  },
  {
    version: "2.153.0",
    date: "2026-07-31",
    changes: [
      "PARTNER-REQUEST ALIASES NOW RESOLVE THROUGH customer_id PROFILES. Kerry: 'For the pairings request alias thing, why not just reference actual aliases in customer_id profiles?' Yesterday's fix read customer_aliases as a name→name lookup table, which is exactly the name-string comparison guiding principle 6 exists to forbid. The alias rung now resolves BOTH sides — the request text and each rostered player — to a customer_id, off the canonical profile name plus every customer_aliases row carrying that id, and matches id to id. 'Dan South' finds 'Daniel South' because they are the same PERSON, not because the strings resemble each other. Two aliases on the same profile now match each other too, which a name→name map could never do without a second hop.",
      "The roster's own customer_id wins where the caller has it. get_event_partner_requests reads customer_id straight off the roster rows and passes it in, so a request resolves against the id actually registered for this event rather than against whatever the name index thinks. A profile alias pointing at a DIFFERENT customer_id than the rostered player now blocks the match instead of making it — same-name-different-person is caught rather than paired.",
      "Names two real people answer to are dropped from the index rather than pointed at an arbitrary winner — the same refuse-to-guess stance _lookup_customer_id takes on duplicate names. Banned accounts are excluded. Roster names still fall back to the nickname person key and substring rungs when a player has no profile alias on file yet, so nothing that matched before stops matching.",
      "MANAGERS CAN NOW ADD A PARTNER REQUEST (Kerry 2026-07-30: 'I also need the ability to add a Playing Partner Request in the requests drop down'). Requests arrive by text and at the first tee, not only in the signup form. The requests panel gains an 'Add a request' row offering the players who don't already have one; it writes through the existing manual-match path, so the added request enters at that player's SIGNUP position and takes its honest place in the priority order rather than jumping the queue for being entered late. Adding one for a player who isn't on the roster is refused — it would create a request the generator could never act on.",
      "TWO MORE REQUEST RULES FROM THE SA CHAMPIONSHIP FIELD (Kerry 2026-07-30). Paying for someone implies the pairing: Assign Guest already stamps the item 'Purchased by <buyer>', so a bought-for player now gets an implied request pointed at their host even when they wrote none — entered at the guest's own signup position, so priority order is unchanged. And a host plus up to three guests is ONE approved foursome, not three competing requests where the last two lose: 'a member can bring as many guests as they want and play with up to 3', so same-host-group requests are confirmed until the group reaches four, at which point the fourth guest is outranked with 'a foursome is full' rather than silently dropped.",
      "A NON-CHAMPIONSHIP TGF EVENT NO LONGER DEFAULTS TO THE FELLOWSHIP CUP (Kerry 2026-07-30 correction). Yesterday's race pulldown defaulted every TGF-chapter event to the Cup; Kerry: 'A TGF-Chapter event should default to that chapter's City Net contest, not The Fellowship Cup. Only the TGF Championship should default to The Fellowship Cup.' The default now keys on the event NAME containing 'champ' alongside the TGF chapter, and a TGF event that isn't the championship offers the full list with no default rather than a wrong one. The city championships (TGF SAN ANTONIO CHAMPIONSHIP) carry a chapter, so the chapter rule catches them first and they stay on their own City NET race.",
      "CONFIRMED and OUTRANKED now read differently in the panel. A reciprocal request (Chuck Fehlis → Gus Vasquez after Gus Vasquez → Chuck Fehlis) and a host playing with guests they paid for are badged green CONFIRMED, not red OUTRANKED — they are the same pairing restated, and badging them as losers read as though the request had been denied. Requests the manager added are badged ADDED; requests implied by someone else paying for the spot are badged PAID FOR, so the panel never presents a derived request as something the player typed.",
    ],
  },
  {
    version: "2.152.6",
    date: "2026-07-30",
    changes: [
      "PARTNER REQUESTS NOW USE REAL IDENTITY MATCHING. Kerry: 'Dan South should be recognized here as Daniel South. Are aliases at work for the partner requests?' They were not — the matcher did naive substring comparison, and 'dan south' is not a substring of 'daniel south' (nor the reverse), so both Mark Villa's and Orlando Kypuros's requests fell through to 'no roster match'. _find_partner_name is now a ladder: exact full name, then customer_aliases (cached per process), then the nickname-robust person key (surname + first initial) that already serves match play, then substring. All six call sites — including the requests panel — share it, so the panel and the generator can never disagree.",
      "AMBIGUITY NEVER RESOLVES SILENTLY. Every rung requires a unique match: a bare 'Dan' against two Dans, or two players sharing a surname and initial, now yields 'no roster match — fix' and a dropdown rather than the generator quietly pairing the wrong people. Previously the first name in roster order won. Initial-CHANGING nicknames (Dick/Richard, Bill/William) deliberately do NOT auto-resolve — matching those would mean matching on surname alone, which is how you pair the wrong brother; customer_aliases is the mechanism for that class.",
      "Multi-name requests keep working and got better: 'Dan Other or Ed Fifth' still returns the first named player with candidates flagged for the manager, but now honors the order the REQUESTER wrote rather than roster order — 'Ed Fifth or Dan Other' means Ed. A pace-staging fixture that relied on 'Danny Other' NOT matching 'Dan Other' was changed to a genuinely unresolvable name, since Danny/Dan is exactly the class this fix is for; the matcher was not weakened to keep an old test green.",
      "STANDINGS PAIRINGS GAIN A RACE PULLDOWN (Kerry 2026-07-30). Selecting STANDINGS now offers every season contest to order by — both City NET races, THE PLAYERS CUP, and THE FELLOWSHIP CUP — defaulting to the event chapter's own City NET race. A TGF-wide event defaults to THE FELLOWSHIP CUP, since that is what the TGF Championship is paired off. GET /api/events/<id>/pairings/race-options serves the list with the default flagged; the Fellowship Cup routes to get_fellowship_cup_projection rather than a City race.",
    ],
  },
  {
    version: "2.152.5",
    date: "2026-07-30",
    changes: [
      "Pinned by test that STANDINGS pairings resolve the chapter's NET points race specifically, not merely a race tagged with that chapter. This matters because players_cup_gross carries chapter='San Antonio' (it is cross-chapter, enroll_chapter=None, but keeps an SA tag), so a chapter-only match would have paired every San Antonio field off the GROSS Players Cup instead of the City NET race. The selector requires BOTH chapter and a NET contest_type; verified San Antonio resolves to san_antonio_net and never to a GROSS race, Austin resolves to austin_net and never borrows San Antonio's, chapter matching is case- and whitespace-insensitive, an explicit race_key still overrides the default so the Players Cup can be chosen deliberately, and a chapter with no configured race (Houston, DFW, blank) yields nothing rather than the nearest match.",
    ],
  },
  {
    version: "2.152.4",
    date: "2026-07-30",
    changes: [
      "STANDINGS PAIRINGS NOW REFRESH AT THE POINT OF USE (Kerry 2026-07-30). Generating in STANDINGS mode re-pulls the points race from Golf Genius when the saved snapshot is older than 15 minutes, instead of relying on the 12-hour background window. Chosen over a session-start or event-driven refresh on Kerry's own reasoning: pairings lock when an event tees off, so the only moment the numbers must be current is the moment Generate is pressed — including day 2 of a two-day event, where the second day's order comes off day 1's results. That case IS a generate action, so point-of-use covers it and an event-driven refresh adds nothing. A session-start refresh was rejected outright because the standings endpoints sit on the PUBLIC pinless member tier, so it would have let every anonymous visitor to the leaderboard trigger a GG fetch, and would have put a flaky external call on the login path.",
      "The window is short enough that yesterday's snapshot never survives, long enough that hitting Generate repeatedly to reshuffle reuses one fetch rather than hammering GG.",
      "STALE STANDINGS ARE NEVER SILENT. When GG cannot be reached the underlying call falls back to the last snapshot; the generator now surfaces that as a WARNING naming the error and the snapshot's timestamp, because pairing a field off yesterday's order while believing it is current is exactly the failure this refresh exists to prevent. On a good pull it states 'Standings as of <time>' instead. The pairings note strip now distinguishes real warnings from routine status rather than badging every line with a warning triangle — if everything is a warning, the one that matters disappears.",
    ],
  },
  {
    version: "2.152.3",
    date: "2026-07-30",
    changes: [
      "PAIRINGS BY POINTS-RACE STANDINGS, LEADERS OFF LAST (Kerry 2026-07-30): 'I want the leaders paired last just like in the PGA. However, I still want to honor Player Requests for this one. Order should just pick up after their requests are accounted for.' New STANDINGS mode alongside Random and ABCD, resolving the chapter's NET points race automatically (San Antonio / Austin) with an optional race_key override.",
      "Partner requests are resolved into UNITS FIRST, then units are ordered by their BEST-ranked member. That detail is load-bearing: a leader who requests an unranked partner would otherwise be dragged to an early tee time by their partner's position. Unranked players (guests, first timers, anyone not enrolled) tee off EARLIEST, since leaders-last makes the front of the field the place for everyone outside the race. Short groups are placed earliest too, so the leaders land in a full foursome at the back as they would on tour.",
      "The Partner Requests toggle now shows in STANDINGS mode as well as Random (ABCD has no use for it — its whole point is one player per handicap tier per group). When the standings are missing or empty the generator says so in its notes and falls back to ABCD rather than silently producing an order that looks intentional.",
      "Covered by test_pairings_standings.py: leaders always last, unranked earliest, requested pairs kept together, the leader-with-unranked-partner case, and every field size from 2 to 24 placing all players with no group over four.",
    ],
  },
  {
    version: "2.152.2",
    date: "2026-07-30",
    changes: [
      "CLICK THE HCP DASH TO SET A STARTING HANDICAP (Kerry 2026-07-30). On the event roster a player with no handicap on record now shows the '—' as an orange dashed button; clicking it stamps a starting (placeholder) handicap on the 18-hole scale. Offered ONLY where there is no handicap — a computed index is never editable there, because it is derived from rounds and must not be typed over. A registration with no customer_id shows a plain dash with a tooltip explaining there is nowhere to store it.",
      "PLACEHOLDERS ARE NOW VISUALLY DISTINCT. /api/handicaps/index-map carries handicap_source and round count, and the roster renders a placeholder in orange with a 'P' marker and a tooltip reading 'STARTING handicap — placeholder, no rounds on record yet'. Golf Genius silently places unhandicapped players into a flight regardless; showing a stand-in identically to an established index would be the same mistake in our own UI.",
      "MANAGERS CAN NOW PUT MONEY BACK AT EVENTS (Kerry 2026-07-30). Robert could not credit Carlos Zapata when he dropped out of side games he had already bought into: /api/items/<id>/credit was already manager-level, but the SAME credit modal's Refund and Partial Refund buttons were admin-only, so the flow 403'd halfway through. refund / partial-refund / payout-credit / refund-watch are now manager, matching credit and wd. View-only and member remain blocked. NOT chapter-scoped — any manager can act on any event; chapter managers already carry session['chapter'] so scoping is a flagged follow-up rather than a silent assumption.",
      "acquisition_source is no longer touched when recording a referral (Kerry: godaddy and referral are not alternatives — they answer different questions and a transaction can be both). Who referred a player lives in referred_by_customer_id and nowhere else.",
    ],
  },
  {
    version: "2.152.1",
    date: "2026-07-30",
    changes: [
      "ASSIGN GUEST now creates a REAL customer record and records WHO BROUGHT THEM. The buyer is already known at that moment, so the referral is derived rather than asked for (Principle 1): new customers.referred_by_customer_id / referred_at, set from the purchasing member, with acquisition_source stamped only when it was blank so a known source is never overwritten. The response returns the created customer_id and the referrer's name, and — critically — says so when NO customer record could be created, because a NULL customer_id leaves the registration invisible to every cid-keyed feature and must never pass silently as success. Optional EMAIL and PHONE fields were added to the same modal and flow through to both the customer record and the registration.",
      "RECORDING A REFERRAL NEVER MINTS A LIABILITY. referral_fees rows arise only from a redeemed coupon (comped) or a payout receipt (paid) per the ratified rules, so set_referred_by writes the relationship and nothing else; verified end to end that no fee row is created. Self-referral and unknown referrers are rejected.",
      "MEMBERSHIP IS DECIDED BY THE ROSTER, NOT THE LABEL (Kerry 2026-07-30): 'a 1st timer could be either a guest or a member — if you match it against the current roster, you'll see that they aren't members yet.' New _ls_is_member resolves customers.current_player_status against the ratified member statuses and falls back to the item's user_status snapshot only when there is no linked customer, and then only to rule someone OUT. This gates hole-in-one eligibility (guests pay in but cannot win), so letting the ambiguous label decide would have been a money error — Kypuros and Villa are both guests despite reading '1st TIMER'.",
      "Assign Member already had the type-and-autofill member picker; no change needed there. Test fixtures gained current_player_status so the roster path is exercised rather than the label fallback.",
    ],
  },
  {
    version: "2.152.0",
    date: "2026-07-30",
    changes: [
      "STARTING (placeholder) HANDICAP (Kerry 2026-07-30). A guest or first timer has no TGF rounds, so no index, so they read '—' on every roster AND cannot be flighted at all. Assign Guest now takes an optional starting handicap alongside the name, stamped onto the player's record as a placeholder until real rounds establish their own TGF Handicap. New customers columns starting_handicap_18 / _set_at / _set_by / _note, POST /api/customers/<id>/starting-handicap to set or clear it for anyone (first timers have the same gap even as members), and get_all_handicap_players now surfaces placeholder-only players with handicap_source='starting' so nothing downstream can mistake a stand-in for a real index. It is NEVER a handicap round: no differential, never feeds compute_handicap_index, and a computed index always supersedes it while the placeholder stays on the record as history.",
      "The scale is in the COLUMN NAME on purpose — starting_handicap_18 — and the input is labelled 18-hole, matching the number TGF quotes and the roster column already displays. After a full exchange spent resolving a 9-vs-18 ambiguity in flighting, naming the scale is the cheapest possible guard against repeating it.",
      "Assign Guest's three prompt() call sites are replaced by one shared modal taking name + starting handicap, with Enter/Escape handling and an explanation of what the placeholder does.",
      "BUG FIXED, found by this work: four queries did SELECT customer_name FROM customers, but the real customers table has first_name/last_name and NO customer_name column — the two Test Center sites (ls_add_player, _ls_seed_from_registrations) would have thrown in production. They passed tests only because the test fixture invented a customer_name column. Both fixtures now mirror the real schema so this class of error cannot hide behind green tests again.",
    ],
  },
  {
    version: "2.151.6",
    date: "2026-07-30",
    changes: [
      "FLIGHT AUDIT — ls_flight_audit grades BOTH flighting modes against Golf Genius's own captured flights across ALL past multi-flight events, which is CA method option C step 2 (mailbox #253): derive the flighting rule from what was actually done rather than specifying it from recollection. Results report per event AND aggregated by chapter and by year, deliberately never collapsed to a single score — a split result most likely means the rule changed over time or differed by chapter, and collapsing would hide exactly that. Where neither mode reproduces GG on most events the output says so and explicitly warns against tuning parameters to close the gap, since the disagreement may be in flight COUNT rather than the cut lines. An empty history reports 'nothing to grade' rather than a vacuous clean score.",
      "New MCP bridges so the analysis is runnable without a browser session: scoring-flight-lab:<event>|<game>[|min=N][|scale=9|18][|tie=...] for one event, and scoring-flight-audit[:min=N|scale=..|limit=N] for the whole history. Both read-only.",
    ],
  },
  {
    version: "2.151.5",
    date: "2026-07-30",
    changes: [
      "FLIGHTING INDEX SCALE RULED (Kerry via mailbox #253, 2026-07-30): handicap bands for flighting are on the 18-HOLE TGF handicap, defined as exactly 2x the 9-hole index. index_scale now defaults to 18. platform-claude flagged a risk that a rating-derived 18-hole index might not equal 2x the 9-hole one — verified across the codebase and it does not exist: every 18-hole index is literally round(index_9 * 2, 1) at all three producing sites. The concern rested on a conflation worth recording — the 'merged 1-18 index' from #251 is the per-hole STROKE INDEX (hole difficulty ranking used to allocate handicap dots), not a handicap index. No handicap index is derived from course ratings anywhere.",
      "BANDS NOW SHARE THE ALREADY-RATIFIED REPRESENTATION. Found a live ratified 4-flight ladder in _GG_POINTS_RACES (Players Cup): (min_inclusive, max_exclusive) = <6.0 / 6.0-12.0 / 12.0-18.0 / 18.0+, whose own comment independently confirms the 18-hole scale. So Kerry's ruling was already encoded in one place and simply had not reached the new engine. Switched SEED_FLIGHT_CONFIG bands and the Individual Net low-flight ceiling from an inclusive-11.9 form to that exclusive-12.0 form: the two agree at one decimal place but diverge the moment an index carries more precision, and '12.0 goes UP' is exactly the boundary that was ratified. New tests assert our 4-flight bands equal the live ratified ladder and that every boundary value lands in the same flight under both — so the two can never silently drift apart.",
    ],
  },
  {
    version: "2.151.4",
    date: "2026-07-30",
    changes: [
      "DOCS: full live-scoring + flighting handoff for CA (docs/claude/live-scoring-spec-for-ca.md, 14 sections) covering the engine, the flighting rule taught by Kerry on 2026-07-29, the pot-split analysis, the flights-freeze/money-floats scenario matrix, the data model and Platform portability, and the test coverage. Deliberately keeps RATIFIED, DERIVED (engine decisions that merely look like rules) and UNKNOWN in separate buckets, because documenting a derived decision as ratified silently skips the ratification step. Posted to the platform mailbox as #251; digest #250 had explicitly not covered this wave.",
      "The central reframe recorded for the Platform: the scoring was ALREADY untethered from Golf Genius — net/gross Stableford, adjusted gross, the ace rule, WHS allocation, MVP, match play and season payouts all compute from our own tables — but the FLIGHTING was not, since determine_event_game_results takes GG's labels and returns flights_unknown rather than guessing. Flighting is the rule that decides who gets paid, and it is now specified. Blocking unknown flagged throughout: whether the raw TGF handicap index is the 9-hole or 18-hole number, which mis-flights the entire field by a factor of two if wrong while looking perfectly plausible.",
      "Two generalisable corrections banked: at a nines-playing club, any per-tee lookup assuming one course_tees row per tee is wrong (GG rates each nine separately, so one physical tee is several rows each holding only its own nine), and any per-round flight label is wrong (flights differ per game, so gg_game_flights is the source and scoring_rounds.flight is a legacy fallback). Both are SHAPE errors rather than data errors and both fail silently. state-of-the-tracker.md refreshed per workflow rule 4.",
    ],
  },
  {
    version: "2.151.3",
    date: "2026-07-29",
    changes: [
      "SHADOW AN UPCOMING EVENT — the pre-flight is now actually possible. Seeding a Test Center session required imported scorecards, so the only events you could shadow were ones already PLAYED: the SA Championship was correctly absent from the picker, and the pre-flight written into its own runbook could not be performed. An event with no cards yet now seeds from its REGISTRATIONS instead (_ls_seed_from_registrations) — the field from active items with credited/refunded/transferred/rsvp_only rows excluded, buyer flags from what each player actually bought, guests flagged not-a-member so they cannot win the HIO, teams from saved pairings, hole count derived from the registrations, and the course tee taken from what the field usually plays there (merged across per-nine ratings). No scores and no playing handicaps — those arrive on the day via Pull from GG, which the session is immediately ready for. Course coverage, buyer counts and flighting can now all be checked days ahead.",
      "CLICKABLE EVENT PICKER replacing the prompt() that asked for a row number — a filterable modal listing every event with registrations or cards, each row showing its date, course, and whether it has scorecards or is registrations-only. Escape or a click outside cancels. The event list behind it no longer restricts to events with scorecards.",
    ],
  },
  {
    version: "2.151.2",
    date: "2026-07-30",
    changes: [
      "RSVPs from multi-round GG events now match the tracker event (Kerry: 2026 TGF CHAMPIONSHIP round 1 RSVPs weren't populating). GG names each round separately — 'round 1', 'round 2', 'Practice Round' — while the tracker carries one event, and the matcher's direct-substring strategy required the event name to CONTAIN the full GG identifier, so the round suffix broke every match. match_rsvp_to_event now strips a trailing round qualifier (round N / practice round, optional dash or colon) and retries the direct name and alias matches with the base name; ordinary event names ('HILL COUNTRY ROUND ROBIN' included) are untouched. rematch_rsvps runs at boot, so the round-1 RSVPs already received self-heal on this deploy.",
    ],
  },
  {
    version: "2.151.1",
    date: "2026-07-29",
    changes: [
      "Mobile customer transaction cards condensed to tight two-line rows (Kerry: 'could be much more condensed and succinct'). All badge pills are gone from the collapsed card — line 1 is the event name (single line, ellipsized) with the amount right-aligned; line 2 is one small plain-text meta line: date · payment rail · games · tee · status word (Credit amber / Transferred purple / Refunded-WD red / 'Via credit' blue). Padding and fonts tightened so roughly twice as many transactions fit per screen; tap-to-expand for actions is unchanged.",
    ],
  },
  {
    version: "2.151.0",
    date: "2026-07-29",
    changes: [
      "FLIGHTING LAB (Test Center tab) + the flight rule as DATA. Flighting was the last tethered piece of event scoring: determine_event_game_results deliberately refuses to guess it (GG labels only, else status 'flights_unknown'), so everything else reproduced GG while flights still came FROM GG. New flight_plan() in live_scoring.py encodes Kerry's ruleset (2026-07-29) as SEED_FLIGHT_CONFIG — flight on the RAW TGF handicap index, not the playing handicap; two legitimate modes (equal-size groups and fixed bands); breaks are floors for the upper flight so 12.0 goes UP and 11.9 tops the flight below with no shared value; Individual Net splits near the middle but its low flight never runs past 11.9; gross bands harder and runs a minimum of three flights; equal indexes NEVER split across flights (the cut slides to the edge that leaves counts evener, dead heat goes up). Flights under a minimum size merge into their neighbour, which is also where 'skewed down from 3 flights to 2 because the handicaps were concentrated' comes from — no separate concentration test needed. Every decision is returned as a note so the reasoning is visible rather than implied.",
      "The Lab runs one event's REAL field through BOTH modes side by side (GET /api/test-center/flight-lab), with min-flight-size, index scale and tie direction as live controls, so the unratified parameters can be dialled and reacted to instead of specified in the abstract. Where GG's own per-game flights were captured it GRADES both modes against them by partition (not by label, since GG may name flights differently while cutting in the same places) — deriving the rule from what was actually done across past events rather than from recollection.",
      "CORRECTION to v2.150.1's claim that the importer does not capture flights: it does. gg_game_flights + import_gg_game_flights walk each flighted game's own GG leaderboard (Ind Net / Ind Gross via detail fragments, Skins via Expand-All) and store per-game flight membership. The earlier check looked at scoring_rounds.flight, which is NULL everywhere because it is the LEGACY single-label fallback — flights differ per game, so the per-game table is the real source. Also flagged: whether the index is the 9-hole or 18-hole number is NOT confirmed, and getting it wrong is a silent factor-of-two mis-flight, so index_scale is an explicit setting rather than an assumption. Minimum flight size and the 3- and 4-flight band ladders remain UNRATIFIED defaults.",
    ],
  },
  {
    version: "2.150.4",
    date: "2026-07-29",
    changes: [
      "Mobile roster games badge now merges game add-ons (Kerry: Mazanec's NET add-on via credit 'didn't update his games badge to BOTH'). The mobile player cards classified the parent row's side_games alone while the desktop table already used getEffectiveGameType (parent + child +PAY game rows combined) — mobile now uses the same effective type, so a GROSS registration with a NET add-on reads BOTH everywhere.",
      "Mobile customer transaction history shows the money without expanding (Kerry: 'more descriptive with actual money amounts… functional and visible'). Each card now carries the dollar amount on its right edge (red for negative refund rows, amber for held credits), a second line with the order date and payment rail (GoDaddy / Venmo / Credit transfer / etc., derived from the merchant label), and add-on child rows surface their note line (e.g. 'NET Games — paid via player credit'). No styling flourish — plain functional text per Kerry's ask.",
    ],
  },
  {
    version: "2.150.3",
    date: "2026-07-29",
    changes: [
      "Add Payment modal now prices itself and can pay from held credit (Kerry, the Mazanec TGF Championship case). Picking a player fetches a pricing quote from the event's own setup: NET/GROSS auto-fill at the event's per-game addon ($16 nine/combo, $30 standalone 18 by the player's holes, 27-hole per-event override), BOTH at 2x, Event Upgrade at the 9-to-18 subtotal difference for the player's status — the amount stays editable and a manual entry is never overwritten. When the player holds credit, Payment Source gains 'Apply Credit — $X available' with a banner listing where each credit came from; submitting consumes credits oldest-first using the same bookkeeping as the Apply Credit entry flow (source items flip to transferred, partial use leaves a credit-excess remainder row, ledger gets transfer_out/transfer_in instead of a new-cash addon entry). The server refuses amounts above the available credit before writing anything.",
    ],
  },
  {
    version: "2.150.2",
    date: "2026-07-29",
    changes: [
      "PER-NINE TEE RATINGS NOW MERGE INTO ONE 18-HOLE COURSE (_ls_tee_holes), correcting a wrong conclusion in v2.150.1. TGF plays nines and Golf Genius rates each nine separately, so one physical tee becomes SEVERAL course_tees rows each holding only its own nine's holes: The Quarry's '1 - Gold Tee' is the front nine (slope 117 / rating 34.2, holes 1-9, the ODD stroke indexes 1-17) AND the back nine (128 / 35.6, holes 10-18, the EVENS 2-18). Reading a single tee_id returns half a golf course — which is why the previous release reported The Quarry's front nine as missing when it was sitting on tee 109 all along (from s9.15, 2026-06-23). Test Center sessions now collect holes from every tee row sharing the same course AND tee name, preferring the requested tee then the newest rating, so seeding off either nine's row yields all 18 holes with a valid 1-18 stroke index. Regression-tested in both directions, including that a different tee name cannot leak in and that a 9 handicap's strokes straddle both nines. The course_coverage banner stays as the backstop for courses where a nine genuinely has not been imported.",
      "Documented TGF's handicap scoping (Kerry): course/playing handicaps come off the 18-HOLE rating and slope and apply across all 18 holes — which the merged 1-18 index above is exactly what's needed for — while handicap DIFFERENTIALS are computed from the 9-HOLE ratings, a separate posting path the Test Center does not touch. Also recorded that GG FLIGHTS ARE LIVE DATA readable off the GG Leaderboard once an event is live, so they should be read rather than inferred; scoring_rounds.flight is currently NULL on every imported round (verified across 100 Quarry rounds and the s18.8 field), so leaderboard flight capture at import time is the next build and typing flights on the Field tab is the Saturday workaround.",
      "SA CHAMPIONSHIP runbook refreshed against live registration: 26 entries (up from 19 the same morning), 18 NET buyers and 16 GROSS. That crossed a threshold — Individual Gross moves from 3 flights to 4 at 16+ buyers on an 18 — so the runbook now warns to read buyer counts off the page on the day rather than trusting written numbers, and notes gross activation sits near its 12-buyer floor where withdrawals can switch the game off. Field spans four tees (<50, 50-64, 65+, Forward), so the modal-tee limitation is called out for CTP yardage and any tee whose stroke index differs.",
    ],
  },
  {
    version: "2.150.1",
    date: "2026-07-29",
    changes: [
      "TEST CENTER GOES LIVE-CAPABLE, for shadowing the SA CHAMPIONSHIP at The Quarry on 2026-08-01. Seeding a session was a one-time snapshot; new Pull from GG (ls_refresh_session_from_gg → POST /api/test-center/sessions/<id>/refresh) re-imports from Golf Genius and re-syncs the session IN PLACE so the board moves during a round. Refresh semantics protect manager work: hole scores, handicap dots and playing handicaps come from GG every pull, while teams, flight overrides, buyer flags, member status, the championship toggle and recorded CTP/Longest Putt/HIO winners are all preserved. Cards that appear mid-round are added; a player who DISAPPEARS from GG is kept rather than dropped (GG re-keys aggregate ids mid-round, and silently removing a player mid-event is worse than a stale row). A GG fetch failure leaves the last good board standing. The tournament URL is remembered per session.",
      "COURSE COVERAGE GUARD — a hole with no par derives nothing, so it scores ZERO in every game while looking completely normal, making a half-scored leaderboard indistinguishable from a low-scoring one. The leaderboard payload now carries course_coverage, and the page shows a red 'the board is WRONG' banner for holes that already have scores but no par, an amber warning for par not yet known, and a separate warning that a missing stroke index makes every NET game wrong rather than merely incomplete. This is not hypothetical: TGF has only ever played The Quarry's BACK nine, so holes 1-9 have no par or stroke index on any Quarry tee and Saturday's 18-hole championship there would otherwise have silently scored nine holes. Refresh also re-accretes course holes from a newly-published 18-hole tee block, filling gaps only (COALESCE) so hand-typed par is never overwritten.",
      "Championship events auto-select the +1-per-net-category points schedule from the event name when seeded (Principle 1 — derive, don't ask); the Field & Course tab still overrides. New docs/claude/runbook-sa-championship-2026-08-01.md carries the event's pre-flight, the Quarry front-nine fix, the buyer counts that decide which games activate (15 NET → 2 flights, 13 GROSS → Individual Gross ACTIVE at 3 flights, Skins 2 flights), and the disagreements worth recording on the day. Test coverage for this wave: 33 new integration assertions including the exact Quarry half-scored-board failure and proof that every class of manager edit survives a refresh.",
    ],
  },
  {
    version: "2.150.0",
    date: "2026-07-29",
    changes: [
      "LIVE SCORING TEST CENTER (admin, /admin/test-center) — the Stage-1 build from docs/claude/game-engine.md: 'rely on GG for ONLY the raw gross hole scores; compute EVERYTHING ourselves.' New pure engine email_parser/live_scoring.py computes Individual Net, Individual Gross, Team Net, Skins, MVP, CTP/Longest Putt and Hole-in-One from nothing but gross hole scores plus our own course/tee facts and playing handicaps. Every threshold is rules-as-data in SEED_LIVE_SCORING_CONFIG transcribed from the ratified side-games spec v1.0 (net flights 1 to 11 buyers then 2 at 12+ splitting at HCP 12.0; Individual Gross activating at 16 buyers on a nine / 12 on an eighteen; skins flights at 8+; CTP max 2 per nine choosing the SHORTEST par-3s with the leftover becoming a Longest Putt on the last hole). The engine reuses the existing formula layer (compute_hole_derivations) and WHS allocation (handicap_calc.allocate_strokes) rather than reimplementing either — duplicating that math would defeat the parity harness it exists to feed.",
      "SHADOW A REAL EVENT + PARITY GATE — seeding a test session from an event with imported scorecards clones the FACTS (gross strokes, GG's own handicap dots, playing handicaps) into sandbox tables, pulls buyer flags from real purchases and teams from saved pairings, and remembers each player's source scoring_round_id. The Parity tab then diffs our engine against GG player by player across gross, net, playing handicap, both Stableford totals, and (where we derived the dots ourselves) the per-hole stroke allocation. Reads PARITY only when every checked value matches; a GG row of all-nulls checks nothing and explicitly does NOT claim parity. This is the confidence gate — GG stays official until it reads clean across real events.",
      "LIVE SCORE ENTRY + SIMULATION — a scorecard grid where a gross score typed into any cell recomputes the entire board (the Stage-2 write path in miniature), with handicap dots shown per hole, par-3 columns shaded, and a 10-second live-refresh toggle. Autoplay fills the field through a chosen hole from an optional seed and never overwrites a hand-entered score, so repeatedly advancing the through-hole reproduces a round unfolding in real time. Field & Course tab edits handicaps, teams, flights, buyer flags, member status, par, yardage and stroke index, plus a championship toggle that swaps in the +1-per-net-category schedule.",
      "SANDBOX ISOLATION — all writes land in new lazily-created ls_test_* tables (sessions, players, holes, course holes, contests); seeding READS production scoring rows and never writes them, and deleting a session touches nothing outside the sandbox. Every table referencing a person carries customer_id as an FK per Guiding Principle 6, and a player linked to a customer takes the canonical name. All routes are admin-only. Covered by test_live_scoring.py (63 engine assertions) and test_live_scoring_center.py (57 integration assertions including the parity gate and a deliberately corrupted score proving the gate can actually fail).",
    ],
  },
  {
    version: "2.149.27",
    date: "2026-07-29",
    changes: [
      "Handicap postings now auto-email a chapter-manager recap (Kerry: 'auto send manager handicap reports for each chapter after each posting to give a recap just like you did here'). Every scoring-hcp-import |apply that writes rounds sends an HTML report — event/course/date header, biggest index movers first (green down / amber up), then the full per-player table with gross, NDB-adjusted score, differential, and index before → after (capped-hole dagger, 'new' for first-ever rounds). Recipients are rules-as-data via app_settings (hcp_recap_email_austin / hcp_recap_email_san_antonio / hcp_recap_email_default) falling back to the owner's inbox until manager addresses are configured; a mail failure never blocks the posting. New scoring-hcp-recap:<event> bridge (re)sends the recap for an already-posted event — the preview's differential pool excludes each card's own bridged round, so before/after numbers stay correct post-hoc.",
    ],
  },
  {
    version: "2.149.26",
    date: "2026-07-28",
    changes: [
      "Golfer winnings detail gains a second meta line under the paying-events average: total events PLAYED overall (counted from live registrations — active/rsvp_only items on real, non-cancelled golf events whose date has passed) with winnings averaged across all of them (Kerry: 'add total events played with average winnings per overall events in a row below the 13 - event average $'). The /api/tgf winnings payload now carries events_entered per golfer, floored at the paying-events count so pre-tracker payout history can never read as played < paid.",
    ],
  },
  {
    version: "2.149.25",
    date: "2026-07-28",
    changes: [
      "Golfer winnings detail: removed the chapter text chip (SAN ANTONIO / AUSTIN / TGF) from the event bands — Kerry: 'No need to put SAN ANTONIO badge on payout detail. City color is fine.' The band's chapter background color carries the signal alone, and event rows no longer wrap to two lines on mobile.",
    ],
  },
  {
    version: "2.149.24",
    date: "2026-07-28",
    changes: [
      "Coupon-sourced referrals no longer sit as owed $25 fees (Kerry: a redeemed tgf-referral-* coupon 'denotes that they already used a coupon that I issued them. So I don't need to be notified to issue another referral fee'). The coupon scan now records the referral as COMPED — the coupon WAS the compensation — with a coupon method stamp and the order date; the pre-rule Jesse Saldana → Craig Bourquin row migrates the same way on the next console load. Comped referrals show in the settled referral table with a purple COUPON badge (no dollar amount) so the referral history stays visible; the cash-fee path (receipt scan + scoring-referral-paid) remains for word-of-mouth referrals with no coupon.",
    ],
  },
  {
    version: "2.149.23",
    date: "2026-07-28",
    changes: [
      "The Refunds console's Venmo pill now registers the refund watch when tapped (Kerry: 'I did initiate each of those directly from the payouts page' — but the pill was a bare deep link, so In Flight stayed empty and nothing was watching for the receipts). Tapping now fires a keepalive POST to the existing refund-watch endpoint (which also schedules the ~75s/~180s quick receipt sweeps) before the Venmo app opens; season-contest removal refunds keep the bare link by design (they complete via the receipt scan). Together with v2.149.22's always-on watchless pass, refunds clear whether or not the tap registers.",
    ],
  },
  {
    version: "2.149.22",
    date: "2026-07-28",
    changes: [
      "Refunds now clear when Kerry pays straight from the Venmo app (Kerry's catch after the s9.20 night: four credit-refund receipts parsed but the credits sat OUTSTANDING). The auto-matcher bailed out early whenever no in-app refund watch was open — which is always, in Kerry's pay-from-Venmo workflow — so the watchless completion pass (built for the Jeff Rideout case) was unreachable. The early return is gone, a latent NameError in the pass's error handler is fixed, the watch-loop match log actually records matches now, and a scoring-refund-sweep bridge command runs the matcher on demand for receipts that landed while the sweep was dead.",
    ],
  },
  {
    version: "2.149.21",
    date: "2026-07-28",
    changes: [
      "Quick-results-text format refined per Kerry: write like a top-end news reporter — lead with what's sensational, editorial judgment over checklist completeness (skins were the first cut for space), next-event teaser as its own punchy line, FULL RESULTS link last. Kerry's final Canyon Springs text recorded in events.md as the reference example.",
    ],
  },
  {
    version: "2.149.20",
    date: "2026-07-28",
    changes: [
      "Docs: Kerry's approved quick-results-text format recorded in events.md — ≤300 characters including the GG results link, news-ticker style with the first five words in all caps then standard case, no emojis, storyline first (name the deciding tiebreaker), then flights/skins/CTPs compressed, ending with the Full results link.",
    ],
  },
  {
    version: "2.149.19",
    date: "2026-07-28",
    changes: [
      "City MVP incomplete-card guard (Kerry's s9.20 Canyon Springs catch): the scorecard import ran mid-live-scoring and stored Larry Anthis with 8 of 9 holes, so his Stableford summed one hole short (13 vs his real 14) and Steve Kulawik was crowned City MVP without the tiebreak ever firing — with full cards they tie at 14 points and tie on net 31, and Anthis wins the gross tiebreaker (40 vs 44). The live data is fixed (cards re-imported, Anthis stamped City MVP + TGF MVP), and determine_tgf_mvp now refuses to determine a winner while any entrant's card is short of a full 9/18 and within catching distance of the leader (9 pts per missing hole) — status 'incomplete_cards' lists the affected players, nothing is stamped, and the TGF MVP roll-up waits with it.",
    ],
  },
  {
    version: "2.149.18",
    date: "2026-07-28",
    changes: [
      "patch_acct_row merge validation accepts 'reconciled' survivors: the bank matcher stamps statement-fed ledger rows reconciled once their Frost CSV debit matches, and the cash-truth winnings resolution (Kerry-ratified option A) merges payouts-console rows into exactly those rows — the active-only check bounced 28 of the first 99 merges.",
    ],
  },
  {
    version: "2.149.17",
    date: "2026-07-28",
    changes: [
      "Starter Sheet and Cart Signs get a ← Back button (Kerry's live catch: in the installed PWA these print sheets open same-tab with no browser chrome, so on mobile there was no way to exit). The button goes history-back when there is history, else lands on /events; it is hidden in the printed output like the rest of the toolbar.",
    ],
  },
  {
    version: "2.149.16",
    date: "2026-07-28",
    changes: [
      "Venmo statement reconciliation wave (Feb–Apr 2026, data operation — docs updated in expense-workflow.md): 123 Feb/Mar + 106 April statement lines tied to the penny against the books. 87 Frost-funded winnings/refund rows on TGF Checking enriched with payee, customer FK, event FK, and Venmo trace ids; 2025 Austin Fall Match Play refunds recategorized Refunds & Returns; 21 double-booked inbound payments merged (Venmo import + email parser + app recorder each wrote rows — ~$1.6k of income de-doubled); Joe Warring's contractor payments ($2,757.37) and all Two Man Tour pass-through flows tagged entity Two Man Tour; the $930 balance-funded Waterchase skins payout (never touched checking) booked from the statement. The payouts-console vs cash winnings overlap ($2,631.82) is quantified and awaits Kerry's policy ruling before any cross-source merge.",
    ],
  },
  {
    version: "2.149.15",
    date: "2026-07-28",
    changes: [
      "Pairings staging: when two groups tie on pace-of-play average, the group with the LOWER total handicap index now goes first (Kerry's ruling from the live Events staging view — better players play faster than their pace rating implies). Applies within each size class on both tee-time and shotgun staging; players with no stored index count 20.0 so an unknown never jumps a known group. Rules-as-data: pace_tie_break in pairing_staging_rules ('none' disables).",
    ],
  },
  {
    version: "2.149.14",
    date: "2026-07-28",
    changes: [
      "patch_expense_row's review_status validation now accepts 'ignored' — the schema's actual dismissal state — instead of 'rejected', which the table's CHECK constraint would have refused; first use is dismissing the $27,060 Arlington Golf receipt (Joe Warring's money, not TGF's ledger, per Kerry's ruling).",
      "patch_acct_row can resolve duplicate ledger rows: status 'merged' + merged_into_id soft-deletes a row exactly like Duplicate Detective (aggregates already exclude merged rows), status 'active' reverses. Needed because the February/March Venmo statements exposed inbound member payments booked twice — once by the app's external-payment recorder and again by the Venmo import's venmo-<id> row.",
    ],
  },
  {
    version: "2.149.13",
    date: "2026-07-28",
    changes: [
      "review_status joins patch_expense_row's allowed fields (validated to pending/approved/corrected/rejected) so Kerry can approve or dismiss review-queue rows through the reconciliation conversation — first use: approving the La Quinta Fort Worth lodging receipt as a Two Man Tour expense. Approving via patch promotes the row to the ledger through the existing guard (pending rows still never promote).",
    ],
  },
  {
    version: "2.149.12",
    date: "2026-07-28",
    changes: [
      "The boot-time expense dedup migration no longer touches statement-sourced rows: identical twins on one statement are two REAL charges (two $10 Vaaler Creek swipes, two same-day $33.22 Vercel bills) with deterministic ordinal uids, and the migration was silently deleting one twin on every deploy — discovered when a Vaaler Creek row Kerry asked about had vanished. A new idempotent boot heal rebuilds any statement expense row whose promoted ledger row survived as an orphan (the ledger side was never lost, so account totals were unaffected), restoring it under its original id with category/entity/account FKs recovered from the ledger split.",
    ],
  },
  {
    version: "2.149.11",
    date: "2026-07-28",
    changes: [
      "P2P rail consistency (three cross-rail false matches in the June checking tie-out): a statement line naming one P2P rail (Venmo/PayPal/Cash App/Zelle) never consumes a books row sourced from — or describing — a different rail, and P2P-sourced rows never match lines that name no rail at all. Caught live: an inbound Zelle from the website contractor matched a member's same-amount Venmo receipt (and took its category), and two same-day $9.00 Cash App/PayPal debits matched $9.00 Venmo refund rows. Both matching paths guarded; the ledger path reads the rail from the row's source or its description marker.",
    ],
  },
  {
    version: "2.149.10",
    date: "2026-07-28",
    changes: [
      "Bank statements may match P2P payout rows again (the v2.149.5 guard was card-specific but blocked everything): a checking 'VENMO PAYMENT' debit IS the funding leg of a Venmo payout, and batch funding posts days after the payout — so on a non-card feed, a debit line naming the P2P rail (VENMO/PAYPAL/CASHAPP/ZELLE) matches that rail's payout rows amount-only across the full ±7-day window. Card feeds keep the hard exclusion, and bank lines NOT naming a P2P rail still refuse payout rows.",
    ],
  },
  {
    version: "2.149.9",
    date: "2026-07-28",
    changes: [
      "Categories auto-register like entities: ledger promotion, patch_acct_row, and a new idempotent boot backfill all create missing acct_categories rows and stamp category_id onto splits that only carried the category as text — the live table predated several bookkeeping names (Business Meals, Travel — Transportation, …), silently breaking category FKs on statement-fed rows.",
      "patch_expense_row no longer promotes PENDING rows to the ledger: patching the $27,060 Arlington Golf tournament-flyer receipt (an informational document, not a paid expense) briefly created a phantom ledger expense. A one-off boot heal removes that phantom row and unlinks the receipt.",
    ],
  },
  {
    version: "2.149.8",
    date: "2026-07-28",
    changes: [
      "Statement-match account consistency: a purchase/credit line only matches books rows of the SAME account (payments still cross accounts by design — they pair with the other side of the transfer). Caught live: a $31.61 Chipotle on the personal Sapphire consumed the business 7680's $31.61 Chipotle books row from the old card import, leaving the Sapphire charge unbooked.",
      "New patch_acct_row + bridge cmd scoring-acct-patch: connectivity patches (entity, category, event, append_note) for acct_transactions rows with NO backing expense row — the old card-import rows matched by statement feeds get their entity/category/event FKs set on their acct_splits (created if absent). Built for the Two Man Tour re-tag of the March DFW contractor-trip rows.",
    ],
  },
  {
    version: "2.149.7",
    date: "2026-07-28",
    changes: [
      "Statement-match type compatibility (caught by the March 7680 feed): a $51.75 own-store card charge matched the GoDaddy ORDER INCOME row for the very same membership purchase via the ledger fallback — the charge and the revenue are two different sides of the same money and both belong in the books. A statement line now only consumes a books row of the same money direction: purchase→expense, payment→transfer, credit→received/income, enforced on both the expense-match and ledger-fallback paths.",
    ],
  },
  {
    version: "2.149.6",
    date: "2026-07-28",
    changes: [
      "Ledger promotion auto-registers new entities: when an expense carries an entity name with no acct_entities row (e.g. 'Two Man Tour' — Kerry's contractor work, tracked separately from both TGF and Personal), the entity is created on the spot so the acct_transactions row gets a real entity FK instead of silently dropping to null. Entity names only arrive from controlled admin paths (statement feeds, expense patches), so an unknown name is a deliberate new book.",
    ],
  },
  {
    version: "2.149.5",
    date: "2026-07-28",
    changes: [
      "Statement-match guards (two false matches caught by the June Sapphire tie-out): (1) P2P payout rows (Venmo/PayPal/CashApp/Zelle) are never match candidates — a member payout can't be the books entry for a card purchase, yet a FACEBK $75 ad charge matched a $75 Venmo payout to a member and mis-patched his row's category/account; (2) statement-sourced rows must match on the EXACT date (their dates are authoritative), stopping a 5/30 $4.00 from matching a different course's 6/6 $4.00; (3) candidates sharing no name token with the statement line only match within ±2 days. Both the expense-match and ledger-fallback paths carry all three guards (the ledger path joins promoted rows back to their expense row for the payout check), candidates are scanned nearest-date-first, and account_id joined the patchable fields for the live repair of the mis-patched payout row.",
    ],
  },
  {
    version: "2.149.4",
    date: "2026-07-28",
    changes: [
      "Statement rows are exempt from the email re-key guard (the third and final twin fix): the guard treats same merchant+amount+date under a new uid as a re-keyed EMAIL and adopts the existing row — but on statements, identical twins are normal and rows carry no platform transaction_id to veto with, so the ordinal-uid insert kept being adopted onto its sibling (which had also stolen the sibling's uid). Statement saves now use a plain uid-keyed upsert; their deterministic stmt-<last4>-<date>-<cents>[-ordinal] scheme is the identity, no re-key semantics apply. email_uid added to the patchable fields for the one-time live repair.",
    ],
  },
  {
    version: "2.149.3",
    date: "2026-07-28",
    changes: [
      "Statement feed: kind 'credit' now books as INCOME ('received' → entry_type income) instead of falling through to expense, and lines accept an optional entity so personal items on business accounts classify to the Personal entity — surfaced by the January Venmo statements, where the two TGF-checking Venmo debits turned out to be personal payments (wedding gift, groom-honoring food) and a personal $50 receipt landed in the @tgf-payments balance.",
    ],
  },
  {
    version: "2.149.2",
    date: "2026-07-28",
    changes: [
      "Second half of the twin-line fix: the occurrence counter only counted CREATED lines, so when twin #1 matched an existing row, twin #2's uid carried no ordinal suffix and the upsert silently overwrote its sibling instead of inserting. Every line now consumes an occurrence slot for its (date, amount) key — matched twins included — verified against the exact live sequence (one pre-existing row, then a two-twin feed → 1 match + 1 create with the -2 uid, and a full re-feed matches both).",
    ],
  },
  {
    version: "2.149.1",
    date: "2026-07-28",
    changes: [
      "Statement reconcile twin-line fix (caught live by the Feb Frost feed's two identical $54.75 Venmo debits on 2/10, which the created-total vs statement-total tie-out exposed): rows created or matched earlier in the SAME feed run are excluded as match candidates for later lines — on both the expense and ledger fallback paths — and repeated (date, amount) lines get ordinal-suffixed uids, so every twin books its own row while re-feeding the same statement stays fully idempotent.",
    ],
  },
  {
    version: "2.149.0",
    date: "2026-07-28",
    changes: [
      "Recurring payments registry (Kerry: 'keep track of recurring payments too — annual and monthly; Aura is annual'): recurring_payments table keyed by merchant token, cadence monthly|annual, auto-refreshed from expense history (latest paid date/amount/account/category) with computed next-due dates and overdue/due-soon flags plus monthly/annual run-rate totals. Bridge: scoring-recurring (sync + list), scoring-recurring-set:<merchant>|<cadence>|<amount>|<category>|<notes>.",
      "scoring-expense-patch bridge: controlled field patch (category / event_name / transaction_type / customer_id / merchant / append_note) on an expense row with immediate ledger re-promotion so splits and FKs follow — the apply-side of Kerry's statement rulings. First uses: the $1,000 Gus Vasquez Zelle reclassified from the learned-categorizer's 'Prizes' guess to an uncategorized TRANSFER noted as return of investor capital (fall 2025 website/app fundraising — balance-sheet movement, not P&L spend), and the $600 Canyon Springs payment linked to the season's first Canyon Springs event as a deposit-to-hold.",
    ],
  },
  {
    version: "2.148.0",
    date: "2026-07-28",
    changes: [
      "Statement reconcile connects the remaining FKs (Kerry: 'course, event, vendor/customer'): feed lines can carry event and customer — event names resolve through the events registry onto the ledger split's event_id (course payments tie to the event they paid for), customer names resolve through the identity engine onto the transaction's customer_id (Zelle/vendor/member lines). MATCHED lines get the same treatment retroactively: a books row missing category/event/customer/account gets patched from the feed and re-promoted, so every statement pass upgrades old rows' connectivity too.",
      "New kind 'deposit' for bank-statement credit lines: they land in bank_deposits (same dedup as the CSV importers, provenance in raw_data) and run through the GoDaddy subset-sum auto-matcher — batch settlements reconcile against income already booked per order, never create new income (which would double-count). The feed response includes the auto-match result.",
      "Kerry is the reconciliation interface's user, not its operator ('the reconciliation engine we built is overwhelming and I can't use it effectively'): the working model is statements in → matched/created/patched report out → a short list of judgment calls. The match queue UI remains for drill-down, not as required workflow.",
    ],
  },
  {
    version: "2.147.1",
    date: "2026-07-28",
    changes: [
      "Statement-created entries are now fully connected through the database (Kerry: 'everything needs to be categorized and connected via the database with all applicable FKs'): the statement's account resolves to a real acct_accounts row by last_four (created with entity FK, institution, and account_type if it doesn't exist yet — no more defaulting to checking), every created ledger row carries that account_id, and every non-transfer line gets a categorized acct_split — explicit category from the feed, else the admin's own most recent categorization of the same merchant (learned mapping), else Other Business Expense as the floor so nothing lands uncategorized.",
      "Card-payment transfer lines intentionally carry no P&L category (moving checking→card isn't spend — standard bookkeeping); they still FK to the card account. Bridge payload gains account_name / account_type / institution.",
    ],
  },
  {
    version: "2.147.0",
    date: "2026-07-28",
    changes: [
      "Statement-feed reconciliation (Kerry: 'I really want to just feed things to you and you reconcile … create ledger entries where we don't have something. Full coverage of bookkeeping'): new reconcile_statement_lines engine + bridge cmd scoring-statement-reconcile take actual statement lines (any account — card or bank), match each against the books (expense rows first, then ledger rows, ±$0.01 / ±7 days), and CREATE properly-sourced ledger entries for whatever email extraction missed — source_type 'statement', provenance (statement label + raw line) in raw_extract, promoted to the ledger immediately.",
      "Card payments book as TRANSFERS, not expenses (moving money checking→card isn't P&L spend), and the synthetic uid stmt-<last4>-<date>-<cents> makes re-feeding the same statement fully idempotent — the second pass matches its own first-pass entries. The report returns matched / created / skipped with dollar totals, so 'what's outstanding to account for' is the direct output of feeding a statement.",
    ],
  },
  {
    version: "2.146.1",
    date: "2026-07-28",
    changes: [
      "Transferred money no longer vanishes from the Money Flow waterfall: a credit transfer left the source item inactive (never allocated) AND excluded the destination row as 'no new money' — a double-exclusion that dropped every transferred dollar. Destination rows now count, booking each transferred dollar exactly once (the ledger side already counts it once at the source), and stale zero-bucket XFER allocations refresh like EXT ones.",
      "The Ledger check's difference is now itemized instead of mysterious: debug adds ledger_without_allocations — income rows whose order has no allocation at all (items later credited/transferred/deactivated while their income persists, plus uncategorized manual income rows), grouped by category with dollar totals. First YTD run after the reconciliation pass: 85 zero-decomposition rows → 5, season contests $1,680 pools / $325 markup now flowing.",
    ],
  },
  {
    version: "2.146.0",
    date: "2026-07-28",
    changes: [
      "Statement check on Money Flow (Kerry: 'with actual statements vs your own email extractions'): the report now proves the email-derived books against a source they didn't create — bank_deposits rows imported straight from Chase/Venmo statements, tied to ledger rows via the reconciliation match queue. TGF-overall views show what the statements say actually arrived, how much of the books' expected net is statement-matched (dollars and rows, with a % that colors green ≥85 / amber / red <60), and a one-tap link into the match queue for the remainder.",
      "Timing honesty: deposits settle days after order dates and cash / Venmo-balance funds never hit a bank feed, so match coverage is presented as the true signal with the raw totals as context (stated on the page). debug=1 adds deposits_by_source.",
      "Fixed the day-old Ledger check silently shrinking as reconciliation progresses: bank-matched ledger rows get status='reconciled', and the gross query's status='active' filter dropped them (same fix applied to the processor-fee and income-by-category queries).",
    ],
  },
  {
    version: "2.145.0",
    date: "2026-07-28",
    changes: [
      "Full reconciliation pass (Kerry: 'I'm wanting you to be able to reconcile everything'). No more $0 decompositions: events missing from the registry or lacking a configured course cost now REVERSE-derive the course fee from the collected price using the ratified pricing formula (price = course fee + included pots + base markup by player type + side games) — the residual after peeling off every ratified term IS the course fee. Discounted rows absorb the shortfall from TGF's markup, never the pass-through pots. Rows are noted 'residual-derived' so forward-configured events stay distinguishable.",
      "SEASON CONTESTS orders finally decompose (ratified Section 4): $10 TGF markup per contest with per-contest pools (NET Points $80, all others $40; Plus members' markup waived → pure pool), solved from the collected price; unmatched prices book conservatively as all prize pool with a logged warning. New _calc_item_allocation dispatcher routes membership / contest / event items in both the GoDaddy-order and external-payment allocators.",
      "Membership bundle fixes: contest prize pools were booked flat $20/contest (vs the ratified $80/$40 per type), and the 'price ≥ $200 → Plus' heuristic misread a $215 Returning + 2-contest bundle as a $244 Plus membership. Base type now best-fits the collected price against ratified totals, preferring what the order's fields say.",
      "Ledger proof on the Money Flow report: TGF-overall views compare the waterfall total to gross income actually booked in the ledger (net + merchant fees, transfer-ins excluded) and show a '✓ Ledger check' line — green within fee-rounding tolerance, amber with the difference when it drifts. Stale zero-decomposition allocations in the queried period are recomputed automatically under the same time budget as the gap-fill.",
    ],
  },
  {
    version: "2.144.0",
    date: "2026-07-23",
    changes: [
      "Money Flow gains scope + period toggles (Kerry): a TGF · Austin · San Antonio segmented control filters the whole waterfall to one chapter (allocations by their chapter; processor fees follow the order's items — a transaction counts toward a chapter when any of its items belongs to it), and a Month · YTD toggle rolls January through the selected month. A label under the toolbar states exactly what's on screen ('Jan–Jul 2026 · Austin').",
      "First YTD query of a year can owe months of allocation backfill, so the gap-fill is now time-budgeted (~40s per request) like the other importers: the page shows 'still filling older months (N orders left)' and auto-refreshes until coverage completes. Bridge syntax grows to scoring-money-flow:<YYYY-MM>[|austin|sa][|ytd][|debug].",
    ],
  },
  {
    version: "2.143.1",
    date: "2026-07-23",
    changes: [
      "Money Flow expand tables refit for mobile (Kerry: 'getting cut off a bit'): tighter cell padding so the dollar column no longer clips off-screen, a new Date column in simple m/d form, and tappable column headers to sort by Event, Date, Players, or amount — defaulting to event date oldest → newest — on ALL expandable categories (course, prizes, markup).",
      "Events no longer split into duplicate rows on name casing: transfer-created items carry mixed-case names ('s9.14 Hill Country' vs the order rows' 's9.14 HILL COUNTRY'), so grouping is now case-insensitive with the events registry's canonical name (and its event_date) preferred for display.",
    ],
  },
  {
    version: "2.143.0",
    date: "2026-07-23",
    changes: [
      "Monthly Money Flow report (platform-claude directive #242, Kerry approved): new admin page at /accounting/money-flow (linked from the Accounting sub-tabs) answering the recurring 'we collected $30K but TGF's cut is only $5K — how?' question. A month picker drives a 7-line waterfall — Course fees → courses, Prize pools → winners, GoDaddy fee → processor, TGF markup, TGF retained fee, = TGF gross margin, Total collected — with a 'TGF keeps X%' stat pill. Course/prize/markup lines tap-expand to per-event totals.",
      "Engine (get_monthly_money_flow + bridge cmd scoring-money-flow:<YYYY-MM>[|debug]): sums the acct_allocations bucket decomposition on an order-date basis, with the sales-tax engine's exclusions (comps, wd, credit-transfer destinations, negatives) so the numbers tie. Coverage finding flagged per the directive: allocations were created LAZILY, so most GoDaddy orders had no rows — the report now fills a month's gaps through calculate_order_allocation itself (idempotent upserts from the ratified pricing tables) before summing.",
      "Processor fee lines come from godaddy_order_splits at raw grain (transaction_fee = collected from customers; merchant_fee = GoDaddy's actual signed cut): GoDaddy line = actual cut, TGF retained = collected − cut — the split the directive said to derive if not stored. debug mode reports fee sums, split-row counts, and any still-uncovered items.",
    ],
  },
  {
    version: "2.142.0",
    date: "2026-07-23",
    changes: [
      "Payouts admin landing rebuilt for mobile (platform-claude directive #241, Kerry approved): a sticky band now tops the page with three stat tiles — Outstanding to pay, Unpaid events, Paid this month — so the day's work shows before any scroll. Outstanding counts unpaid ROWS (a partially-paid group contributes only its remainder), matching what the Pay buttons actually carry.",
      "The control strip splits into two axes: a segmented Events · Season · Golfers view control plus an All · Unpaid · Refunds filter-chip row beneath it — the old single row mashed both together and Refunds ran off-screen on a phone. Tapping a view segment snaps the filter back to All; Unpaid/Refunds chips show their work queues regardless of view.",
      "Event rows are now actionable without drilling in: an Unpaid (orange) or Paid (muted) status pill plus a '14/19 paid' progress count sit under each event name, and the green number finally has a label ('Pot' — it's the event's payout pool, which Kerry and platform-claude both had to reverse-engineer). The 'Select an event' placeholder hint is gone; rows read as tappable on their own.",
    ],
  },
  {
    version: "2.141.0",
    date: "2026-07-22",
    changes: [
      "Overpayment tracking (Kerry — the a9.19 Teravista CTP mix-up: both CTPs were entered for Jay Hogue and paid out $98.50 before GG re-awarded one to Paul Reed): when a results correction SHRINKS a golfer's group after its receipt was sent, the payout matcher now links the whole group PAID and records the overage in the new tgf_overpayments table instead of dead-ending. The Unpaid queue gets an amber 'Overpaid — Request Back' section with a one-tap Venmo REQUEST button (a charge, not a payment) prefilled with the difference and the memo 'Overpaid winnings for <event> — please return $X'.",
      "The loop closes itself: when the player pays the request, the inbound Venmo receipt carries that memo, and the new recovery scan matches it to the open overpayment (customer + event + exact amount), marks it RECOVERED, and books the returned money as ledger income. Manual closes (cash back / waived) via the scoring-overpay-resolve bridge; scoring-overpayments lists the ledger. The underpaid mirror case (a correction GROWS a group, e.g. Paul's added $17 CTP) already worked via the subset pass — the remainder shows as due with the normal Pay button.",
      "Fixed inbound receipt promotions writing entry_type='expense': _sync_expense_ledger_entry compared the mapped type ('income') against 'received', which can never match, so every promoted inbound P2P payment was classified as an expense in reconciliation/P&L. Inbound promotions now book as income (forward-only; historical rows untouched).",
    ],
  },
  {
    version: "2.140.3",
    date: "2026-07-22",
    changes: [
      "Expense dedup no longer swallows twin payments (found via Kerry's Bob Atkinson receipts screenshot): the Graph re-key guard treats any second email with the same payee + amount + date as a re-key of the first, so Bob's four 7/21 Venmo payments (two $58 credit refunds, two $25 referral fees) collapsed to two rows — $83 silently missing from the ledger. Both dedup paths now compare the payment platform's transaction_id from the receipt (Venmo/PayPal ids are globally unique): different ids = two real payments, never folded. Same id or no id keeps the re-key protection intact.",
      "Boot heal recreates the two folded receipts — the $58 s9.19 THE QUARRY credit and the $25 David Decareaux referral fee — as approved venmo expense rows promoted to the ledger, and the referral receipt scan then files the Decareaux fee PAID from the recovered memo. The healed rows carry no transaction_id, so if the original emails ever re-deliver they adopt these rows instead of duplicating them.",
    ],
  },
  {
    version: "2.140.2",
    date: "2026-07-22",
    changes: [
      "Gross flight-pot rule is now a LEVER, not code (Kerry: 'there's times where we may do it for a number of players in the flight or straight split — we need to finalize the levers'): app_setting gross_flight_pot_mode = 'buyins' (default — each flight's pot is its own players' buy-ins, the GG-parity rule that just corrected s18.8) or 'even' (straight split of the pot across flights). No behavior change until the setting is flipped; editable via the scoring-setting-set bridge or a future Matrix UI control. The final policy (which mode applies when, within-flight ladder proportions, and whether flighted skins gets the same question) is logged as an OPEN FLAG in the side-games spec pending Kerry's ratification.",
    ],
  },
  {
    version: "2.140.1",
    date: "2026-07-22",
    changes: [
      "Individual Gross flight pots now follow each flight's own buy-ins (Kerry, s18.8 Vaaler Creek): gross flights are handicap BANDS with uneven headcounts (4/5/7 on a 16-buyer field), but the engine paid the matrix's flat grossLow1st ($32 = total ÷ flights, an even-split assumption) to every flight — $96 paid out of a $128 pot. The pot now apportions by flight headcount with exact cents (per-player rate × players: $32/$40/$56), matching GG's model to the penny; the matrix ladder's proportions still split places within a flight, and ties still split (Horton/Niester $16 each was coincidentally right and is unchanged).",
      "s18.8 corrections on re-record: Neal Cloer's Ind Gross $32 → $40, Fernando Romero's $32 → $56 (both still unpaid, so their groups simply update to $103 and $205 due). Also: scoring-referral-link bridge to resolve an ambiguous referral coupon token to a specific customer — 'tgf-referral-jesse' is Jesse Saldana per Kerry.",
    ],
  },
  {
    version: "2.140.0",
    date: "2026-07-22",
    changes: [
      "Referral fee tracking (Kerry: 'I would like to add referral fee tracking'). New REFERRAL FEES section in the Refunds console: OWED derives automatically from tgf-referral-<name> signup coupons (the referred member's order names the referrer in the coupon the parser already extracts), and PAID auto-completes from P2P receipts whose memo reads 'Referral fee for <person>' — the same receipt-verifies-payment philosophy as refund watches. Fee amount is rules-as-data: app_setting referral_fee_amount, default $25.",
      "Owed rows carry a one-tap Venmo pay link prefilled with the referrer's handle, the fee, and the exact memo the scanner listens for — pay from the console and the receipt closes the loop on its own. referral_fees table keys both sides by customer_id per the identity rule; bridge commands scoring-referrals (sync + read) and scoring-referral-paid:<id> (manual completion for cash) round it out.",
      "Backfill: the receipt scan retro-records Bob Atkinson's two paid referral fees (Hector Aguilera 07/21, David Decareaux 07/22 — the latter lands as soon as its Venmo receipt arrives). Bob's second $58 credit (s9.19) also stamped COMPLETED against today's payment.",
    ],
  },
  {
    version: "2.139.4",
    date: "2026-07-22",
    changes: [
      "Apply Credit 'Internal server error' fixed (Kerry, the Fieber case): v2.129.25's edit accidentally deleted the _send_credit_entry_confirmation helper while keeping both call sites, so every Apply Credit since the evening of 7/20 hit a NameError AFTER the database work — the credit genuinely applied (Fieber's $54.79 is on the Championship with balance_due:112.21) but the modal showed an error and the balance-due auto-email never sent. The helper is restored verbatim from the pre-merge commit, with a call-site/def consistency check run over all apply-credit helpers.",
      "If you applied any credits since 7/20 evening and saw this error: the application itself succeeded every time — but no balance-due or entry-confirmation emails went out for those applications. Fieber still needs his $112.21 balance-due email (send it from his registration row).",
    ],
  },
  {
    version: "2.139.3",
    date: "2026-07-22",
    changes: [
      "Unpaid queue + Refunds console fit on a phone (Kerry): the event/date info now stacks UNDER the player's name instead of running inline beside it, so the first column stays narrow. Below 640px the action cell wraps (Venmo pill above Mark Paid) and the event line wraps too, instead of pushing the Amount and Pay controls off the right edge of the screen. Same stacked treatment in both queues via the shared .queue-sub style; desktop layout unchanged apart from the actions column no longer reserving a fixed 200px.",
    ],
  },
  {
    version: "2.139.2",
    date: "2026-07-22",
    changes: [
      "Payout matcher causality guard (the Paul Reed case): a payment receipt can never be matched to winnings for an event played AFTER the payment date. Reed's a9.19 rows ($25.50 + $39.00) were stamped paid by an unconsumed April 7 Venmo receipt that happened to total exactly $64.50 — the matcher's amount-only fallback saw exact cents and linked it, dating his July winnings paid 2026-04-07. Candidate groups are now filtered to event_date <= payment date (+1 day slack); date-less pseudo-events (monthly points) stay eligible. Verified: the April receipt no longer claims the July group, and a genuine event-night receipt still matches.",
      "Reed's a9.19 payout rows unlinked back to unpaid ($64.50 due, in the Unpaid queue). The stray April receipt remains in the ledger as a real payment awaiting its true home — surfaced to Kerry for disposition.",
    ],
  },
  {
    version: "2.139.1",
    date: "2026-07-22",
    changes: [
      "New read-only payout-state tracer (Kerry: 'Tracker says Paul Reed is already paid out. I didn't do that. Track why'): inspect_event_payouts / bridge scoring-payouts-inspect:<event>[|<player>] lists every payout row for an event with the FULL linked ledger row inlined (source, source_ref, date, amount, status) and a computed state — PAID / PENDING / UNLINKED / DANGLING. A payout renders paid whenever its acct link is non-pending, so tracing a wrong paid state requires seeing exactly which ledger row claims it; until now that required raw DB access.",
    ],
  },
  {
    version: "2.139.0",
    date: "2026-07-22",
    changes: [
      "GG games import learns to check back for late winners (Kerry: 'CTPs are almost inherently later because they're not live'). A round whose game board exists but has no winners entered is no longer marked done — it goes on a recheck list (gg_game_recheck) and re-walks on every import pass until the winners appear, giving up after 14 days. Previously one walk froze the round forever, which is how s9.19's two CTPs (Kulawik #12, Mary Wade #16, $26 each) sat in GG invisible to the Tracker.",
      "Late winners flow all the way through: the import now reports which events' winner sets actually changed (real set comparison, so routine re-walk upserts don't trigger it), and the auto-sync force-re-records those events' auto payouts even when the event is older than the recent-days window. The sweep's no-event-today skip also yields when rechecks are outstanding, so an off-day CTP entry still lands within the hour.",
      "Tonight's discrepancy sweep (Tracker vs GG): a9.19 Teravista matched exactly ($525 both sides). s9.19 The Quarry reconciled to the penny — $52 missing CTPs (now imported + payouts re-recorded, $539 → $591/21 rows), $4 GG Team Net purse configured at the 27-player matrix value for a 26-player field ($104 is correct), and $0.02 GG rounding up a 4-way tie split our exact-cents rule doesn't overpay.",
    ],
  },
  {
    version: "2.138.1",
    date: "2026-07-22",
    changes: [
      "Match Play close-out fix (Kerry, Youngs v Jenkins): the clinch walk now counts holes remaining IN THE MATCH, not holes GG has posted flags for. The old walk closed the 2&1 semifinal at hole 7 — but 2 up with two to play is dormie, and the match was decided ON hole 8 by a net halve (Youngs' stroke made his gross 6 a net 5 vs Jenkins' 5). Hole 8 now renders as a played, halved hole (gray dot, full-color scores with the stroke dot) instead of being greyed as post-clinch; only hole 9 shows unplayed.",
      "Boot-time heal rewrites any stored gg_match_detail snapshot (cmp_bracket + cmp_matches) whose close-out summary was frozen by the old walk — closed_at_order/thru/margin recompute from the per-hole flags; hole data and the manually recorded winner/margin are untouched. The live GG fetch also re-derives with the true match length from the TGF event code before hardening a snapshot, so a mid-round '2&1-looking' state can no longer persist prematurely.",
      "Same length-aware fix applied to the raw-score reconciler (_cmp_derive_match), which had the identical one-hole-early clinch on truncated rounds. Note on presentation: match cards show GROSS scores with a stroke dot on stroked holes (GG's own convention); the hole winner/halve verdicts are NET — GG's per-hole flags — so the card was already scoring net, it just buried the deciding hole.",
    ],
  },
  {
    version: "2.138.0",
    date: "2026-07-22",
    changes: [
      "Match Play admin SETUP sub-tab (Kerry): the pill row is now POOLS | KNOCKOUT | PAYOUTS | SETUP, with SETUP as an admin-only tab in the telltale admin orange. Every control that can restructure or destroy a live contest — + Add Pool, Auto-Assign Pools, Seed Knockout, Clear Bracket, and the versioned Config editor — moved off the member-facing panels into SETUP, grouped as Pools / Knockout / Config cards with plain-language blast-radius notes. Auto-Assign Pools no longer sits one mis-tap from a contest that's already under way.",
      "The Match Play header card is now purely informational (title + structure line), the Knockout panel opens straight into the bracket, and the chapter/season selector row lost its + Add Pool button. SETUP is deep-linkable like the other sub-tabs (#tab=mp&mp=setup); its content is role-gated so non-admins following the link see an empty panel, and every action remains role-checked server-side.",
      "Access note: these five controls were previously visible to chapter managers; per Kerry's call they are now admin-only. The legacy (pre-v2) Match Play view is unchanged.",
    ],
  },
  {
    version: "2.137.6",
    date: "2026-07-21",
    changes: [
      "Dropped the 'Shown in play order…' caption from real (GG) match scorecards (Kerry): the circle/dot language is self-evident and 'Started on hole N' on the card head already covers play order. The caption remains only on illustrative placeholder cards, where disclosing that the hole detail is generated is load-bearing.",
    ],
  },
  {
    version: "2.137.5",
    date: "2026-07-21",
    changes: [
      "Scorecard Hole row darkened (Kerry): after the size bump it still shared the par row's light placeholder gray, so the header wasn't leading by tone. Now --text-body (#4B5563) — Hole row > Par row in both size and darkness, with the black score digits still on top of the ladder.",
    ],
  },
  {
    version: "2.137.4",
    date: "2026-07-21",
    changes: [
      "Par row, two more sources (Kerry's Barna/Hogue catch): the semifinal WAS linked — to the Falconhead City Champ practice round, an event with zero imported scorecards, and the par lookup only ran through an event's imported rounds. (1) Course-name fallback: an event with no banked cards now resolves pars from the course DB directly ('Falconhead' → 'Falconhead Golf Club' tee pars). (2) Live matches: the live payload now embeds hole_pars resolved from GG's own event code, so a live card (e.g. a semifinal at tonight's event before anyone links it) shows par mid-round — and the hardened snapshot carries the pars forever. Client falls back to the detail's embedded pars when the bracket row has no event.",
    ],
  },
  {
    version: "2.137.3",
    date: "2026-07-21",
    changes: [
      "Scorecard type hierarchy (Kerry): the Hole header row (Bitter) sat visually BELOW the par/data digits — it was set at 0.58rem against the sans rows' 0.66rem, and Bitter's digits already read ~1px smaller than system sans at equal size. Bumped the Hole row to 0.68rem Bitter (optical parity with 0.66rem sans, plus bold/caps/letterspacing to lead) rather than shrinking the par digits, which are data already near the mobile legibility floor. Rule of thumb going forward: Bitter labels next to sans data get ~1px of optical compensation.",
    ],
  },
  {
    version: "2.137.2",
    date: "2026-07-21",
    changes: [
      "Austin knockout par fix (Kerry): the Barna/Hogue semifinals showed no Par row because their bracket matches never had an EVENT linked — no event, no course, no tee pars (SA's semi worked because Vaaler Creek was linked). cmp_get_bracket now self-heals at read time: when a bracket match has no event_id but its hardened GG detail carries the round's event code ('a9.18'), the event resolves by code — feeding the Par row AND the card header's course · date — without touching the stored row. Manually linking the event via the manager dropdown still works instantly and remains the proper data fix.",
    ],
  },
  {
    version: "2.137.1",
    date: "2026-07-21",
    changes: [
      "Completed knockout matches paint their hole dots INSTANTLY (Kerry's Chandler v Moreno catch): bracket matchups had no stored hole detail — unlike pool matches — so every page load re-walked Golf Genius through the 60-second live poller before the dots appeared, even for a long-finished semifinal. cmp_fetch_live_match now hardens a FINISHED match's detail onto the bracket row (cmp_bracket.gg_match_detail; mid-match snapshots are never persisted so a partial card can't freeze), the bracket API serves it, and the first render draws the full scorecard with zero GG traffic. Live matches still poll every 60s as before; the first viewer after a match completes triggers the one fetch that hardens it for everyone after.",
    ],
  },
  {
    version: "2.137.0",
    date: "2026-07-21",
    changes: [
      "Par row on Match Play scorecards (Kerry): the expanded hole-by-hole card — pool matches AND knockout — now shows a Par row above the players' scores, so every score reads against par at a glance. Par comes from the match event's imported tee data (scoring_rounds → course_tee_holes): the pools/bracket APIs attach a per-event hole_pars map, a client-side registry keyed by event name serves it to every render path (including the 60s live re-render), and the row appears whenever par data exists — holes without banked tee pars stay blank rather than misaligning the grid. Illustrative placeholder cards keep their existing Par row unchanged.",
    ],
  },
  {
    version: "2.136.1",
    date: "2026-07-21",
    changes: [
      "Link previews (Kerry): texted/shared links now unfurl with a meaningful card — page-specific Open Graph + Twitter metadata (title, description, TGF icon) via the new templates/_og_meta.html include, added to Contests/Leaderboards, Player Spotlight, Handicaps, and Events (member and admin variants alike). Example: /member/contests previews as 'TGF Leaderboards & Match Play — Season standings, points races, Match Play pools and knockout bracket…'. Note: hash sub-links (#tab=mp&mp=knockout) share their page's card — fragments never reach the server.",
    ],
  },
  {
    version: "2.136.0",
    date: "2026-07-21",
    changes: [
      "Match Play sub-links (Kerry): each Match Play sub-tab — Pools, Knockout, Payouts — is now URL-addressable. Clicking a sub-tab writes #tab=mp&mp=<panel> into the address bar, reloads land back on the same panel, and links can point straight at a panel (e.g. /contests#tab=mp&mp=knockout, or /member/contests#tab=mp&mp=knockout for members). Switching back to the Match Play top tab keeps the active sub-panel in the link.",
    ],
  },
  {
    version: "2.135.3",
    date: "2026-07-21",
    changes: [
      "Holes derived at insert (Kerry): blank or mis-parsed items.holes on a single-format event now gets stamped from the event's format the moment the row is saved — blank holes was undercounting the side-games player buckets, and the boot-time heal only caught it at the next deploy (today's Estes re-import and two live parses sat blank until manually patched). Combo events are untouched (holes is the player's 9/18 choice there), as are non-event rows (memberships, contests). heal_item_holes_from_event stays as the boot backstop and is now alias-aware.",
    ],
  },
  {
    version: "2.135.2",
    date: "2026-07-21",
    changes: [
      "Shotgun staging fix (Kerry's 12A/12B catch): on a shared hole the A group tees off AHEAD of the B group, but foursome staging was filling slots in sheet order — which put the fastest foursome at 12B behind a slower 12A. Foursomes now fill the remaining slots in TRUE play order (hole descending, A before B) fastest first, so higher pace averages go first and the slowest foursome sits at the back of the train (lowest hole's B). Short groups already used play order and are unchanged.",
    ],
  },
  {
    version: "2.135.1",
    date: "2026-07-21",
    changes: [
      "Requests panel: the SUPPRESSED badge is now itself the restore control (Kerry) — tap it to unsuppress. The separate Restore button is gone; Remove stays on active rows.",
    ],
  },
  {
    version: "2.135.0",
    date: "2026-07-21",
    changes: [
      "Multi-name requests (Kerry): signup text naming 2+ rostered players ('Dan Other or Ed Fifth') gets an amber 'N names — link one…' picker on the requests panel — only ONE partner is honored (rule 1), the manager links which; the auto-match's first hit stands until then, and the extras are honored by manual moves after Generate. The panel hint spells out the one-partner rule.",
    ],
  },
  {
    version: "2.134.0",
    date: "2026-07-21",
    changes: [
      "Signup-order request priority (Kerry): partner requests are now honored FIRST-COME instead of alphabetically. The generator processes the roster in signup order (order date → ingest time → row id), so in a 3/4-person cross-request the earliest request wins — once a player is claimed in either direction, later requests touching them (including that player's own later request) are dropped. One request per player, both players locked once paired (rule 1 + 11), manager suppression of the earlier request is the override that promotes the next one in line.",
      "Requests panel upgrades: rows list in signup order with a #priority number and signup date; requests that lose the first-come race show a red OUTRANKED badge whose tooltip names the player already locked and points at the override (suppress the earlier request). The Requests chip count now excludes outranked requests, so it reads as exactly what Generate will enforce.",
      "Manual request matching (Kerry): a 'no roster match' row is now a picker — signup text that doesn't resolve to a rostered player ('Dave Decareaux' vs roster 'David Decareaux') can be bound to the intended player. The generator substitutes the bound roster name, the row shows a purple ✎ manual badge (click to clear), and the binding persists per event in the new pairing_request_matches table (customer ids captured per rule 6). POST /api/events/<id>/pairings/requests/match.",
    ],
  },
  {
    version: "2.133.0",
    date: "2026-07-21",
    changes: [
      "Per-player pace badges on the PAIRINGS tab (Kerry): every seated and unassigned player line shows a ⏱1/2/3 chip next to the name — green 3 (fast), gray 2, amber 1 (slow); unrated players show a dimmed ⏱2 (the implied default). GET /pairings event_players now carries pace_rating to feed it.",
      "Live group-pace chip: the ⏱ average on each group header is now computed in the browser from the group's CURRENT members, so player swaps, cart-pair swaps, group swaps, and moves update it instantly — no regenerate needed. Saved pairings views get the chip too (it was generator-output-only before).",
    ],
  },
  {
    version: "2.132.0",
    date: "2026-07-21",
    changes: [
      "Partner-request console (Kerry): the PAIRINGS controls bar gains a Requests chip (active/total count) that opens a list of every request on the roster — who asked for whom, plus raw text that didn't match a rostered player. Remove suppresses a request BEFORE generating: the generator ignores it on the next run, but the row stays listed with a SUPPRESSED badge and a Restore button. Suppression persists per event in the new pairing_request_suppressions table (requester customer_id captured per rule 6); API: GET /api/events/<id>/pairings/requests + POST .../requests/suppress, and the request list rides along on GET /pairings.",
    ],
  },
  {
    version: "2.131.1",
    date: "2026-07-21",
    changes: [
      "Smalls staging clarified (Kerry): on TEE-TIME events short groups take the EARLIEST times; on shotguns they stage in the exact order furthest-out loaded hole's A slot → its B slot → the A slot one hole back (4A → 4B → 3A), with foursomes filling the remaining slots slowest-first so the fastest foursome sits just behind them. Rule key renamed shotgun_smalls_lead → smalls_lead (it now governs both start types).",
      "Max three 3-somes per 9-hole or 18-hole grouping: documented and test-asserted — _make_group_sizes' splits already guarantee it (worst case is [4, …, 3, 3, 3] when the field is 1 over a multiple of 4).",
    ],
  },
  {
    version: "2.131.0",
    date: "2026-07-21",
    changes: [
      "Shotgun staging: threesomes (and any short group) ALWAYS lead the hole train — they take the last sheet slots (the highest holes, e.g. 4A/4B) regardless of pace; pace still orders the train within each size class (Kerry, The Quarry 2026-07-21). Rules-as-data: the shotgun_smalls_lead key in pairing_staging_rules turns it off.",
      "Cart seating: every settled group now runs the exact seat arranger, so same-tee players share a cart whenever pairing requests don't supersede — priority Match Play opposite carts > partner request same cart > same-tee cart mates. Tee comparison is case/whitespace-insensitive so label drift can't split a tee pair. (Foursome composition is untouched — this only decides who rides together.)",
      "Front/Back 9 side: new events.nine_side setting ('Front' default) in event setup — a back-9 night labels its shotgun train 10A/10B… instead of 1A/1B…. The PAIRINGS tab gains a ⛳ Front 9 / Back 9 toggle that flips the setting and shifts any SAVED shotgun labels with it (1A ↔ 10A), so the sheet and printables follow without a regenerate. Also settable via PATCH /api/events and the update_existing_event MCP tool.",
    ],
  },
  {
    version: "2.130.15",
    date: "2026-07-20",
    changes: [
      "scoring-hio-pot audit bridge: returns the live pot with its full line-item breakdown (carry-in, per-event player counts and contributions, paid out, total) for verification against the GAMES tab display.",
    ],
  },
  {
    version: "2.130.14",
    date: "2026-07-20",
    changes: [
      "HIO pot: future events join only when NEXT IN LINE (Kerry: 'you can't count those until the prior event is completed') — events dated through today always count; among later dates only the earliest upcoming date's sign-ups count, and events behind it wait until the one before them completes.",
    ],
  },
  {
    version: "2.130.13",
    date: "2026-07-20",
    changes: [
      "HIO pot field size derives from scoring data: each event's field is MAX(registrations, distinct players on its banked scorecards) — golfers staged as GG individuals outside pairings (the Hill Country Matches case) get counted the moment the event's cards are imported. The override dial remains as a stopgap for events whose cards aren't banked yet.",
    ],
  },
  {
    version: "2.130.12",
    date: "2026-07-20",
    changes: [
      "HIO pot field-size overrides: the hio_player_count_overrides dial (NAME PATTERN=COUNT) covers days where tracker registrations lag the true field — set to HILL COUNTRY MATCHES=32 (Kerry: 32 played on 5/17, tracker holds 29 registrations), making the Matches contribution 32 × $3 = $96.",
    ],
  },
  {
    version: "2.130.11",
    date: "2026-07-20",
    changes: [
      "HIO pot: 27-hole days contribute $3/player — $1 per 9 holes played (Kerry: 'Hill country matches would be $3 / player because we played 27'). Which events count as 27-hole lives in the hio_27h_event_patterns dial (default 'HILL COUNTRY MATCHES'); this season's Comanche Trace Matches day was being counted at 18-hole rates.",
    ],
  },
  {
    version: "2.130.10",
    date: "2026-07-20",
    changes: [
      "HIO pot includes scheduled (future) events as soon as they have registrations (Kerry: 'The event itself should be included just like the event's pot is included in that event's payouts') — the HIO dollars are collected at registration, and each event's contribution self-corrects as its field grows because the pot recomputes live. Rain-out and cancelled-event guards unchanged.",
    ],
  },
  {
    version: "2.130.9",
    date: "2026-07-20",
    changes: [
      "HOLE-IN-ONE watch (Kerry): scorecard imports now raise a HIGH action item whenever an imported card contains an ace (strokes = 1 on any hole) — the HIO pot pays out, and recording the payout under category 'hio' drains the pot. Dedup-guarded so re-imports don't re-alarm.",
      "scoring-setting-set:<key>|<value> bridge for writing app_settings dials.",
      "HIO pot carry-in ratified and documented: $1,150 remained after the Julius Jenkins half-pot payout at the 2025 TGF Championship, + $672 added through fall 2025 play (GG ALL-Gross-verified) = $1,822 entering 2026.",
    ],
  },
  {
    version: "2.130.8",
    date: "2026-07-20",
    changes: [
      "scoring-hio-gross: GG truncates round-selector labels (~28 chars), cutting off the parenthetical dates — round dates now come from prefix-matching the truncated label against the archive's full event labels, with label-embedded dates as fallback.",
    ],
  },
  {
    version: "2.130.7",
    date: "2026-07-20",
    changes: [
      "scoring-hio-gross walks the widget's round SELECTOR instead of the event export's gg_round_id — those are different id families, and GG answers an unknown &round= with the default page (every event came back 'no ALL Gross board'). Round dates parse from the selector labels.",
    ],
  },
  {
    version: "2.130.6",
    date: "2026-07-20",
    changes: [
      "scoring-hio-gross bridge — EXACT per-event field sizes counted off the LIVE 2025 GG portals' ALL Gross leaderboards (the archive's result rows are winners-only for many fall events, so counting them under- or over-shoots the real field). Walks the proven tournament_results round-selector route, fetch-only, budget-aware.",
      "scoring-south-ledger-repair — removes the double-booked $74 Daniel South ledger entry (mistaken 7/16 repair + today's receipt promotion) and records his real 7/16 payment: $18.59 excess credit from s9.18 Cedar Creek, whose receipt was misparsed.",
    ],
  },
  {
    version: "2.130.5",
    date: "2026-07-20",
    changes: [
      "scoring-hio-archive counts fields from the ALL GROSS leaderboard only (Kerry: distinct names across every game leaderboard ran WAY over the real field — a9.16 Avery Ranch showed 40 vs actual 24); falls back to any gross-labeled game, and reports the count basis per event.",
      "stamp_credit_refunded + scoring-credit-stamp bridge: mark an outstanding credit refunded WITHOUT writing a ledger entry, for payments whose Venmo receipt already reached the ledger via expense promotion (payout_credit would double-book those).",
    ],
  },
  {
    version: "2.130.4",
    date: "2026-07-20",
    changes: [
      "scoring-hio-archive:<subdomains> bridge — per-event field sizes and games-matrix HIO contributions computed from the GG History archive (distinct leaderboard names per event; 9/18 from banked hole rounds where available), for reconstructing the 2025 HIO pot carry-in after the Julius Jenkins payout.",
    ],
  },
  {
    version: "2.130.3",
    date: "2026-07-20",
    changes: [
      "Accounting sub-tab bar audit (Kerry 2026-07-20): Reconcile and Cash Flow rendered in a different font and alignment because they are links while the other tabs are buttons — the shared tab style now pins font, line-height, vertical alignment, and no-wrap for both element kinds, and the bar scrolls sideways instead of wrapping 'Cash Flow' onto two lines in the 1080px column.",
      "The Reconcile and Cash Flow pages' sub-tab bars now include ALL TEN accounting tabs (they listed only six, with a stale 'Transactions' label for Ledger), and /accounting now honors #hash deep links — Dashboard/Ledger/Accounts/Categories/Reports/Liabilities/Contractors/Rules links from those pages land on the named tab instead of always dumping onto Ledger. Switching tabs also stamps the hash in the URL so refresh keeps your tab.",
    ],
  },
  {
    version: "2.130.2",
    date: "2026-07-20",
    changes: [
      "Hotfix: v2.130.1 broke the GG History pending-names queue by selecting customers.customer_name — that column doesn't exist; the suffixed display name ('Victor Arias Jr') lives on customer_aliases.customer_name. Queue + search now derive the display name from the longest name-alias, falling back to first + last + customers.suffix. Verified against a live-shaped schema fixture: both Ariases render with suffixes, blinds stay set aside.",
      "Bonus fix surfaced by the same dig: the customer-search endpoint's alias join was ALSO on the nonexistent customers.customer_name, meaning the 'search name to link' box has been silently erroring since it shipped — the join is now by customer_id, so typed search works for the first time (and the new focus-autofill with it).",
    ],
  },
  {
    version: "2.130.1",
    date: "2026-07-20",
    changes: [
      "Accounting Ledger now fits the 1080px column: long descriptions wrap instead of pushing the table off the right edge (the global nowrap rule was forcing a page-wide horizontal scrollbar), the ledger list contains any residual overflow with its own scroll, and the acct tables adopt the ratified density (4px/5px cell padding).",
      "Courses page fits the 1080px column: the page-local 1200px wrapper and its double padding are gone, the fixed side-column widths were slimmed so the COURSE name + tee list column gets real room (min 220px) instead of wrapping word-by-word.",
      "GG History review: the 'search name to link' box now autofills from the customer database (Kerry 2026-07-20) — focusing the empty box immediately searches the GG surname and shows tappable Link chips, no typing needed; live search while typing is unchanged.",
      "GG History review: candidate and search chips show the customer's full display name with generational suffix (customers.customer_name — 'Victor Arias Jr' vs 'Victor Arias III') instead of the suffix-less first+last, so same-named family members are tellable apart before linking.",
      "GG History review: blind-draw entries (raw names like 'Bl[BOOKER, Raimond]') no longer clutter the pending queue — they are SET ASIDE, not dismissed (Kerry: 'shouldn't show up here, but don't necessarily want to dismiss them either'): rows stay pending in the table with all their data, the queue just skips them and the header counts them as 'blinds set aside N'.",
    ],
  },
  {
    version: "2.130.0",
    date: "2026-07-20",
    changes: [
      "1080px is now the ratified desktop content width for the WHOLE app — Admin, Manager, and Member pages alike (Kerry 2026-07-20: 'let's do 1080px as standard width for desktop on ALL pages... It all just displays too wide'). The global main rule in dashboard.css caps and centers every page's work column (was 1600px); the dark nav header stays full width. The PAYOUTS page's page-local 1080px rule is removed in favor of the global one.",
      "Admin table density is now the app-wide default: the global table rules adopt the Kerry-ratified TGF-console density (header cells 4px, body cells 5px vertical padding, 10px horizontal) and the main content padding tightens to match — 'functional, not all this beautiful white space'. Pages with their own table CSS (Contests leaderboard, points drill-downs) are unaffected.",
    ],
  },
  {
    version: "2.129.27",
    date: "2026-07-20",
    changes: [
      "PAYOUTS page work surface centered in a 1080px max-width column (Kerry 2026-07-20: 'It definitely doesn't need that wide of a window for desktop... it's just all too spread out'), with the admin-density standard applied page-wide: Player Pot Summary and all payout tables at 5px row padding / 0.84rem text, event sidebar rows halved in height and the rail narrowed to 250px, main padding tightened. The whole page — tabs, sidebar, tables — reads as one compact centered console.",
    ],
  },
  {
    version: "2.129.26",
    date: "2026-07-20",
    changes: [
      "apply_credit_to_rsvp joins the single credit-value source (_item_credit_value): its inline formula still counted transaction fees, so the SERVER applied John White's $122 credit as $141.92 (owed $17 became owed $0 — no balance email, phantom excess) and armed Larry Anthis's excess watch at $14.08 when the modal correctly showed $4.00. Every credit read/write path now shares one function.",
      "Apply Credit double-click guard: a second tap while the first apply was in flight consumed the credits and threw 'No valid credited items found' over a SUCCESSFUL apply — the button now locks on first tap.",
      "REFUNDS console: every Outstanding row with a Venmo handle gets a small inline Venmo button (opens in a new window, amount + Kerry-format memo naming the credit's ORIGIN event prefilled) — no more detour through the customer page; 'more…' keeps the profile link. Buttons shrunk to match the utilitarian standard.",
      "PAYOUTS sub-nav: UNPAID/REFUNDS pills left-align right after GOLFERS and the bar caps at 900px (Kerry: 'they don't need to be spread out').",
      "scoring-item-note:<item_id>|<note> repair bridge for stamping balance_due tags on rows applied under the old math.",
    ],
  },
  {
    version: "2.129.25",
    date: "2026-07-20",
    changes: [
      "Apply Credit auto-sends the balance-due email (Kerry 2026-07-20): when the member still owes after credit is applied, the STANDARD balance-due email with the prepared Venmo request link goes out automatically on Apply — a pre-checked 'Auto-send balance-due email' box in the modal's note section opts out per-application. Works on both the item and GG-RSVP apply paths (server-side send, so mobile behaves identically); the confirmation alert reports where the email went, and a failed send tells you to use the manual Send Balance Email instead of failing silently.",
    ],
  },
  {
    version: "2.129.24",
    date: "2026-07-20",
    changes: [
      "Admin work queues go UTILITARIAN (Kerry 2026-07-20: 'Functional, not all this beautiful white space'): the Unpaid Payouts queue and REFUNDS console render dense single-line rows — golfer + event·date on one line, 4px row padding, tables capped at 860px so amounts and buttons sit next to the names instead of across the screen.",
    ],
  },
  {
    version: "2.129.23",
    date: "2026-07-20",
    changes: [
      "ONE credit-value function everywhere (_item_credit_value — no fees, minus partial carve-outs, floored at $0): the REFUNDS console still computed its own amounts and would have shown/paid John White $122 + $15.65 = $137.65 against $122 actually held. get_player_credits, payout_credit (the money actually sent), the REFUNDS console, and the watchless-completion matcher now all read the same helper — display, modal, and payment can no longer disagree. Same lesson as the badge-vs-modal split earlier today: duplicated money math WILL drift.",
    ],
  },
  {
    version: "2.129.22",
    date: "2026-07-20",
    changes: [
      "Watchless refund completion (Kerry 2026-07-20, the Jeff Rideout case): Kerry often pays a credit refund straight from the Venmo app with no in-app Refund tap, so no watch existed and the credited item sat OUTSTANDING forever — even though the receipt arrived (under his alias 'Paul Rideout') with a memo naming Jeff. The refund-watch sweep now has a second pass: an unclaimed payout receipt whose memo reads like a credit refund and matches exactly ONE open credited/WD item by customer_id + exact amount completes that item the same way a verified watch would.",
    ],
  },
  {
    version: "2.129.21",
    date: "2026-07-20",
    changes: [
      "FEES ARE NEVER CREDITED (Kerry-ratified 2026-07-20: 'We don't refund fees' — the rule existed in practice but was written nowhere and the credit code had included transaction fees since it was built): get_player_credits now uses the entry price only. John White's Cedar Creek credit corrects from $126.27 to $122.00 total ($106.35 entry + $15.65 downgrade carve-out); Larry Anthis from $116.08 to $106.00. Rule recorded in docs/claude/events.md.",
      "Daily Briefing deep links (Kerry): membership outreach rows link straight to the player's page, and the money chips link to their queues (payouts/refunds → TGF page, credits → Transactions).",
      "scoring-refund-watch-cancel:<name>[|<amount>][|apply] bridge — cancels an open In-Flight refund watch that was initiated but never actually sent (no cancel path existed).",
      "scoring-credit-payout:<item_id>|<method>|<date>|<note> bridge records an already-sent credit refund via db.payout_credit (the Jeff Rideout $19.15 was Venmo'd under his alias 'Paul Rideout' so the console never saw it complete), and scoring-alias-add:<canonical>|<alias> records the Venmo-account name alias for future matching.",
    ],
  },
  {
    version: "2.129.20",
    date: "2026-07-20",
    changes: [
      "Credit math accounts for partial carve-outs (Kerry 2026-07-20, the John White case): a credited entry's item_price still reflects the ORIGINAL bundle, so when a partial refund/credit child existed (his 18→9 downgrade held $15.65 as separate credit before the rain-out credited the whole entry at full 18-hole price) the same money counted twice — Apply Credit offered $141.92 when the house holds $126.27. get_player_credits now subtracts Partial Credit / Partial Refund / Refund(<method>) children from the parent's credit (floored at $0), so parent + carve-out lines always sum to the money actually held. Applies everywhere credits surface: Apply Credit modal, roster badges, credit-alert emails, balance-due emails.",
    ],
  },
  {
    version: "2.129.19",
    date: "2026-07-20",
    changes: [
      "Daily Briefing money chips (Kerry 2026-07-20): a second overview row shows Outstanding Payouts ($ + golfer count), Outstanding Refunds, and Open Credits at a glance.",
      "Quick Wins now leads with OVERDUE PAYOUTS rendered deterministically — any unpaid payout group past the 24-hour-after-event standard shows as 'Pay <golfer> $X — <event>, Nd past the 24h payout standard' with an Unpaid-queue link; the money SLA is not left to the AI's judgement. SLA is a dial: app_settings payout_sla_hours (default 24).",
    ],
  },
  {
    version: "2.129.18",
    date: "2026-07-20",
    changes: [
      "GG-RSVP Apply Credit endpoint now DELEGATES to get_rsvp_credit_info — the same proven code path behind the roster CREDIT badge and the credit-alert emails — instead of maintaining a hand-rolled duplicate of its resolution/pricing logic (the duplicate drifted twice in one day while the shared function worked throughout; Anthis's badge and alert email were fine while his modal failed). One code path now serves badge, alert, and modal.",
      "New debug bridge scoring-credit-info:<rsvp_id> runs the same analysis server-side and returns the payload or full traceback — player-specific Apply Credit failures are now diagnosable without a phone.",
    ],
  },
  {
    version: "2.129.17",
    date: "2026-07-20",
    changes: [
      "Daily Briefing restructured (Kerry 2026-07-20: 'honestly overwhelming' — 200 action items as full cards): the email now opens with an ADMINISTRATIVE OVERVIEW of the last 24 hours (stat chips + an AI-written prioritized 3-6 bullet summary), then QUICK WINS (sub-5-minute actions), then a MEMBERSHIPS section (expiring-soon and just-lapsed lists for personal outreach, plus renewed/new members this week). Action Required shows full cards ONLY for new-in-24h + high-urgency items (capped); the standing backlog rolls up to one row per category with count, oldest date, and a dashboard link — every item's detail stays one click away.",
      "All briefing thresholds are dials in app_settings: daily_briefing_detail_cap (10), daily_briefing_expiry_window (30 days), daily_briefing_recent_window (7 days). Subject now reads 'N new · M open' instead of the raw item count.",
    ],
  },
  {
    version: "2.129.16",
    date: "2026-07-20",
    changes: [
      "Apply Credit modal X works in every state (Kerry 2026-07-20: the failure popup's X was dead — only tapping outside closed it): the header X is wired once at page setup instead of only after a successful load, and the modal body no longer injects a duplicate 'Apply Credit' header with a second #apply-credit-close id (which also made the popup show its title twice).",
    ],
  },
  {
    version: "2.129.15",
    date: "2026-07-20",
    changes: [
      "Refund memo reason condenses to Kerry's exact shorthand (2026-07-20): a stored removal reason like 'Withdrew — Injury' renders as 'WD (Injury)' — full memo 'Rolando Campos - WD (Injury) Refund for Match Play 2026'. Withdrew/withdrawal/withdrawn heads map to WD; the detail after a dash/colon/parenthesis becomes the parenthetical.",
    ],
  },
  {
    version: "2.129.14",
    date: "2026-07-20",
    changes: [
      "GG-RSVP credit-info endpoint now resolves the player EXACTLY like the roster CREDIT badge does — rsvps.customer_id first (rule 6), canonical customers name, then email fallback. The old email-only lookup left an email-less GG-format name ('Anthis, Larry') unresolvable: the roster badge showed his live $116.08 credit while Apply Credit 404'd (Kerry 2026-07-20 mobile).",
      "HTML pages are no-store too (was /api/* only): the iOS PWA kept serving a cached /events page whose old inline JS failed long after fixes deployed — the modal was even showing pre-fix error text. Pages always fetch fresh now; /static assets keep normal caching.",
    ],
  },
  {
    version: "2.129.13",
    date: "2026-07-20",
    changes: [
      "External links open in a new window APP-WIDE (Kerry-ratified 2026-07-20: 'Any link that sends to an outside website outside of a Tracker URL should be brought up in a separate window'). One capture-phase click handler in auth.js stamps target=_blank + rel=noopener on any off-origin http(s) anchor — covers every dynamically-rendered link on every page without per-call-site target attributes. Protocol handoffs (venmo://, mailto:, tel:) are untouched.",
    ],
  },
  {
    version: "2.129.12",
    date: "2026-07-20",
    changes: [
      "REFUNDS console Venmo memo reformatted (Kerry 2026-07-20): '[Player] - [Reason] Refund for [Contest]' — e.g. 'Rolando Campos - Removal Refund for Match Play 2026'. The 'City' prefix, chapter parenthetical, and trailing 'removal refund' are dropped; a short removals.reason is title-cased into the memo, long free-text reasons fall back to 'Removal'. Memo is built server-side in get_refunds_overview (single source of truth) and carried on the row as 'memo'.",
      "The console's desktop Venmo button opens in a NEW window (target=_blank) instead of navigating the Tracker tab away.",
    ],
  },
  {
    version: "2.129.11",
    date: "2026-07-20",
    changes: [
      "Apply Credit modal: selecting 'Venmo back' for the excess flips the submit button to 'Apply Credit, Register & Refund' (Kerry 2026-07-20) — the label now states all three actions the tap performs; switching back to 'Keep as credit' restores 'Apply Credit & Register'.",
    ],
  },
  {
    version: "2.129.10",
    date: "2026-07-20",
    changes: [
      "GG-RSVP credit-info endpoint passes the RSVP's email into get_player_credits (it already had an email-fallback resolver that was never used here): a GG-format name ('McCRARY, Justin') that matched no items row 404'd 'No credits on file' even when the player held a live rain-out credit — McCrary's $106 s9.18 Cedar Creek credit applying to s9.19 The Quarry is the trigger case.",
    ],
  },
  {
    version: "2.129.9",
    date: "2026-07-20",
    changes: [
      "Apply Credit modal surfaces the server's actual error ('No credits on file for this player') instead of the generic 'Failed to load credit info.' — a no-credit 404 was indistinguishable from a deploy-rollover 502 (Kerry 2026-07-20, McCrary at s9.19). 5xx responses add a 'server may be restarting — try again in a minute' hint.",
    ],
  },
  {
    version: "2.129.8",
    date: "2026-07-20",
    changes: [
      "API responses are never browser-cached: Safari/iOS caches GET XHRs that carry no Cache-Control header, so the Payouts PWA kept re-serving a stale /api/tgf payload long after the DB was corrected (Kerry: 'Taking forever for the BARNA and Cedar Creek thing to resolve' — the server had been right for a while). A global after_request hook stamps Cache-Control: no-store on every /api/* response.",
      "scoring-payouts-restore-explicit bridge — stage-2 of the over-match repair (Kerry: 'Of course rebuild what you screwed up'): re-inserts the 8 deleted rows that had NO surviving ledger mirror, reconstructed from GG's round boards (s18.3 net/skins purse tables reconcile the event to GG's $1,118.00 total to the penny; s18.1's two rows keyed off GG's team roster + CTP winners at the sheet's sibling amounts). Each restores under its original id and is marked paid via the app's own bulk-confirm ledger-mirror mechanism, dated to the event.",
    ],
  },
  {
    version: "2.129.7",
    date: "2026-07-20",
    changes: [
      "Docs: events.md now records that the Payouts sidebar total is tgf_events.total_purse (not the payout-row sum), the full payout repair-bridge set (clear-auto |all with shell-row sweep, restore-from-ledger-mirrors, unlink, rainout-label incl. |clear), and the removed course-name matching fallback with the incident that killed it.",
    ],
  },
  {
    version: "2.129.6",
    date: "2026-07-20",
    changes: [
      "Cedar Creek '$229' mystery SOLVED: the Payouts sidebar shows tgf_events.total_purse (a stored screenshot-import column), not the sum of payout rows — the rain-out's shell row had $229 stored and ZERO payout rows, so every row-only sweep truthfully reported 'removed: 0' while the sidebar kept showing money. clear-auto '<event>|all' now also deletes matched tgf_events rows left with zero payout rows and reports them (empty_event_rows_deleted with the purse figure).",
      "Payouts page mobile (Kerry 2026-07-20 screenshot): with no event selected, the events list now takes the screen and the 'Select an event' placeholder shrinks to a slim bottom bar — 'uncover many more events'. Picking an event restores the compact-list + detail split.",
      "scoring-payouts-restore arg parsing: event codes containing pipes ('s18.3 SAN ANTONIO KICKOFF | Cedar Creek') no longer swallow the |apply flag (rpartition + literal-apply check).",
    ],
  },
  {
    version: "2.129.5",
    date: "2026-07-20",
    changes: [
      "INCIDENT + repair: the v2.129.3 clear-auto course-name-token fallback over-matched — clearing 's9.18 Cedar Creek' also swept s18.1 CEDAR CREEK and s18.3 SAN ANTONIO KICKOFF (same course, DIFFERENT events), deleting 36 legitimately-paid payout rows. The name fallback is REMOVED (event CODE is the only safe key; whitespace-collapse prefix matching stays). New repair bridge scoring-payouts-restore:<tgf code>[|apply] rebuilds deleted rows from their surviving bulk-confirm ledger mirrors (source_ref payout-<id> carries the original id, category, customer, amount, paid link) — idempotent, ids re-inserted exactly; rows that were linked to grouped real Venmo receipts have no per-row mirror and are reported as a remaining gap instead of guessed at.",
      "Hole-in-One banner renders as two stacked rows (Kerry 2026-07-20 mobile screenshot: the single line wrapped mid-sentence) — line 1 this event's contribution, line 2 the running pot thru the event.",
    ],
  },
  {
    version: "2.129.4",
    date: "2026-07-20",
    changes: [
      "scoring-rainout-label:<event>|clear|apply removes a mislabeled RAINED OUT badge (Kerry 2026-07-20: on the 4/21 Tuesday only the Austin event was a rain out — s9.6 The Quarry's cancellation was something else). Status is untouched, so the cancelled-status payout/HIO-pot guards stay in force; only the display badge clears.",
    ],
  },
  {
    version: "2.129.3",
    date: "2026-07-20",
    changes: [
      "clear-auto matching rebuilt on whitespace-collapse normalization: the Cedar Creek $229 sat on a tgf_events code variant the TRIM+LIKE prefix still couldn't reach (memo-style 's9. 18 CEDAR CREEK' spacing). Codes are now compared with ALL whitespace stripped; the bare event code matches as a prefix with a non-digit guard (s9.1 can never swallow s9.18 rows), and a course-name-token fallback (>=8 chars) catches rows that dropped the number entirely. The response still lists every matched code for the audit trail.",
    ],
  },
  {
    version: "2.129.2",
    date: "2026-07-20",
    changes: [
      "Subset receipt-matcher gated to memo-resolved events only: the first live run subset-matched an April $32 expense receipt (no event memo) onto a July s18.8 payout row because $32 happened to equal one unpaid row. The subset pass now runs ONLY when the receipt's memo resolves to a specific event and only against that event's payout group — the Barna partial-payment case (memo'd to a9.18) still matches; memo-less receipts never subset-match.",
      "scoring-payouts-unlink:<acct_transaction_id> repair bridge — clears acct_transaction_id + paid_at from tgf_payouts rows wrongly linked to a receipt (returns them to unpaid), used to undo the false positive above without touching the receipt itself.",
      "scoring-rainout-label now also badge-fills events that are already cancelled but badge-less (the 4/21 ShadowGlen + Quarry and 5/26 Quarry cancellations predate the badge convention): status is kept as-is, only the badge is stamped so the payout/HIO-pot guards and the UI read the shutdown uniformly.",
    ],
  },
  {
    version: "2.129.1",
    date: "2026-07-20",
    changes: [
      "Rain-out labeling sweep (Kerry 2026-07-20: 'We had other rain outs. They need to be labeled as such'): new bridge scoring-rainout-audit lists every past event's shutdown signals (status/badge, credited-registration ratio, recorded payout rows) and flags ACTIVE-status events with >=50% credited registrations as unlabeled-washout candidates for Kerry's review; scoring-rainout-label:<event>[|<badge>][|apply] stamps the confirmed ones with the cancelled status + badge — the authoritative signal the payout and Hole-In-One-pot guards read.",
      "clear-auto row matching hardened: duplicate tgf_events code variants (case/stray whitespace — 's9.18 CEDAR CREEK ') hid the Cedar Creek manual rows from the sweep; matching now TRIMs and adds a code-prefix pattern, and the response lists the matched codes.",
    ],
  },
  {
    version: "2.129.0",
    date: "2026-07-20",
    changes: [
      "Partial-payment awareness end to end (Kerry 2026-07-20, the Barna a9.18 case — $146.83 already Venmo'd, then the $26 TGF MVP row landed): the P2P receipt matcher gains a SUBSET pass — when no payout group's total matches a receipt, it finds the subset of one candidate group's unpaid rows summing exactly to the receipt and marks just those rows paid. Both payout UIs (Events PAYOUTS tab + TGF page) now show a PAID/DUE subline on partially-paid golfers, and the Pay / Mark Paid buttons carry ONLY the unpaid remainder.",
      "Hole-In-One pot on the GAMES tab: the banner now shows this event's contribution AND the running cross-event pot THROUGH that event. get_hio_pot carries per-event running totals and an app_settings carry-in dial (hio_pot_carry_in + note) for the end-of-2025 balance once Kerry confirms it (~$2000 recalled).",
      "scoring-payouts-clear-auto gains '<event>|all' to ALSO remove manual/screenshot-imported payout rows (Kerry-directed only — the s9.18 Cedar Creek rain-out sheet was manual rows the auto-only clear couldn't touch), and the sweep now covers duplicate tgf_events code rows.",
    ],
  },
  {
    version: "2.128.1",
    date: "2026-07-20",
    changes: [
      "Uniform match-play allowance encoded as a config DIAL (Kerry-ratified 2026-07-20: 'Stored as a setting is our standard for everything — ultimate control to turn the dials without getting a developer'). cmp_encode_uniform_allowance authors a match_play config version carrying handicap_allowance = {basis: off_lowest, value: 0.75, adjustable: true} + the historical GG-era per-chapter facts (SA 75 / Austin 100) for the record. 2026 season snapshots are NOT re-pinned (past frozen); future seasons snapshot the new current version. Bridge: scoring-mp-encode-allowance[:<value>][|apply].",
    ],
  },
  {
    version: "2.128.0",
    date: "2026-07-20",
    changes: [
      "TGF MVP single-event-day pot rule (Kerry ruling 2026-07-20, the a9.18 $26 shortfall): when the linked chapter's same-day event produced no City MVP (rained out), there is still no cross-chapter TGF MVP HONOR — but this event's players funded its TGF MVP contribution, and money follows collection: the day's sole determined City MVP takes this event's own tgfMVP pot. GG left the $26 unallocated; we now pay it (Kelly Barna, a9.18).",
      "Running Hole-In-One pot (Kerry 2026-07-20): new get_hio_pot sums every past non-rained-out event's GAMES-matrix holeInOne contribution (by player count and 9/18 matrix) minus recorded HIO payouts. GET /api/hio-pot (manager) + bridge scoring-hio-pot.",
      "Prize Fund Reconciliation itemizes the Hole-In-One accrual as its own line (it accrues to the running pot rather than paying out per event, so it never reads as an unexplained difference), computes the difference net of HIO, and shows the running cross-event pot total inline.",
    ],
  },
  {
    version: "2.127.4",
    date: "2026-07-20",
    changes: [
      "Match Play WD standings rule (Kerry ruling 2026-07-20): a withdrawn player who PLAYED matches sorts to the bottom of the pool standings, keeping the WD tag and played record (Campos, SA Pool A); a withdrawn player with NO played matches is a clean removal + refund and disappears from standings entirely. Applied in both ranking paths (dmp09 + legacy); ranks renumber in display order; points/records/advancement math untouched.",
      "2026 season ruling documented: NO 3rd-place consolation matches — semifinal losers split the combined 3rd/4th money (the D-MP-08 split_combined_places fallback the payout sheet already applies when no consolation match is recorded); the manager-only consolation recording stays hidden. NH notation clarified in the D-MP-11 register: the number is a COUNT of holes actually played (9-hole match won on the 2nd extra hole = 11H; 18-hole match won on the 1st extra hole = 19H) — the future app records each extra hole's scores on the leaderboard and the label reflects the count.",
    ],
  },
  {
    version: "2.127.3",
    date: "2026-07-20",
    changes: [
      "Team/Cart Net tie-with-duplicate correction (Kerry ruling 2026-07-20, superseding the keep-your-real-slot tie-break): when TIED teams share a duplicated player (real slot on one, blind on the other), the tied teams stop being separate pots — the COMBINED pool splits evenly among ALL unique players across the tied teams (two tied foursomes with one shared player → pool / 7, everyone equal; s18.8-style $192 → $27.43 each). A tie with no duplicate keeps the per-team split (matches GG's $96/$96). The higher-share rule remains for a player duplicated across DIFFERENTLY-placed teams (1st and 2nd).",
    ],
  },
  {
    version: "2.127.2",
    date: "2026-07-20",
    changes: [
      "Rain-out guard fix: the registration query referenced items.status, which doesn't exist (that column lives on acct_transactions) — every payout assembly errored with 'no such column'. Guard now counts credited/WD registrations without the phantom filter.",
      "Rain-out guard reads the BADGE first (Kerry: 'It should simply see that the event was rained out. We have a badge on it. That means everything is shut down.'): events.status != 'active' — stamped by the cancel flow with badges like RAINED OUT — is the authoritative shut-down signal for payout assembly. The credited-registrations ratio stays only as a backstop for events cancelled before the status field existed.",
    ],
  },
  {
    version: "2.127.1",
    date: "2026-07-20",
    changes: [
      "Rain-out guard on game payouts (Kerry 2026-07-20, s9.18 Cedar Creek: 'It was a RAIN OUT. There were no winners... all amounts were credited'): the hourly auto-recorder had assembled $229 of 'winners' from the partial game data — it had no idea the event washed out. assemble_event_game_payouts now refuses any event whose registrations are >=75% credited/WD/refunded (threshold high enough that ordinary per-player WDs never trip it) — rules-derived from the ledger, no flag to set. The auto-recorder skips such events with the rain-out reason.",
      "New bridge scoring-payouts-clear-auto:<event>: removes an event's auto-recorded payout rows and their PENDING ledger entries (a matched real Venmo transaction is never touched; manual/screenshot rows untouched) — used to clear Cedar Creek's phantom $229.",
    ],
  },
  {
    version: "2.127.0",
    date: "2026-07-20",
    changes: [
      "Season-contest removal refunds now surface in the REFUNDS console (Kerry 2026-07-20: 'is it in overall PAYOUTS where it should be, so I don't miss it?'). A removal recorded with a refund amount previously lived only on the Enrollment tab's removals list — the Campos $40 sat invisible to every work queue. It now appears OUTSTANDING (with a one-tap Venmo pay link carrying amount + memo when the player has a handle on file) until a matching outbound Venmo receipt lands via the expense inbox — same person, same amount, on/after the removal date — at which point it shows COMPLETED. Rules-based/derived; no new schema. New read bridge scoring-refunds-overview.",
      "Team/Cart Net unique-player rule refined for the equal-shares case (two-team tie for 1st with a player on both teams): shares are equal so 'higher share' can't decide — the player keeps their REAL slot and vacates the BLIND one; the blind team's pot splits among its remaining members. Unequal shares still pay the higher share regardless of which slot is the blind.",
    ],
  },
  {
    version: "2.126.4",
    date: "2026-07-20",
    changes: [
      "Team payout member names: strip the portal decoration a cross-chapter team string leaves on its last member ('SHARITZ, Don TGF Austin,' / '... TGF Austin, Guest') — the importer's end-anchored chapter regex only removes the final tag. Payout rows now resolve to the clean player name.",
    ],
  },
  {
    version: "2.126.3",
    date: "2026-07-20",
    changes: [
      "GG games importer gains REPLACE semantics per tournament: rows a previous walk stored that are NOT in the current winner set are deleted. A walk during a live round captures transient standings (every team 'T1 - $0'); the later re-walk upserted the real winners but left the stale rows behind — the source of the phantom Team Net 'ties' at a9.18 (GG really had ONE clear winner at -5) and s18.8 (a real 2-way tie, not 5). An explicitly requested round (&round=<id> on the widget URL) now always re-walks, so stale captures can be healed on demand.",
      "Team/Cart Net payout rule encoded (Kerry ruling 2026-07-20): the pot splits evenly among UNIQUE players. A player on TWO paid teams (real slot on one, blind on the other) receives only the HIGHER per-player share; the lower team's pot then splits among its remaining members — one other player in Cart Net, three in Team Net. Blind slots remain paid (s9.17 precedent).",
    ],
  },
  {
    version: "2.126.2",
    date: "2026-07-20",
    changes: [
      "Course seeder made ALIAS-AWARE: the boot 'Seed courses' step (the original source of the name-only stubs) re-created every deleted stub under a fresh course_id on the next boot, because it only deduped against exact courses.name. It now skips any items/events course name that already resolves through course_aliases.",
      "Rule-based alias-shadow sweep in the registry migration: a courses row whose name matches an alias of a DIFFERENT course, with zero rounds and zero tees, merges into the alias target automatically — heals the one boot's worth of re-created stubs (ids 44298+) and permanently closes this drift class. Orphan facilities left by merged rows are cleaned up; courses-audit's missing-names check now also consults aliases.",
    ],
  },
  {
    version: "2.126.1",
    date: "2026-07-20",
    changes: [
      "Course registry migration fix: the live run aborted at the Cedar Creek merge because course_tees' UNIQUE(course_id, tee_name, slope, rating) rejects moving an archived tee whose spec never actually changed (GG archived the course anyway). Tees now move one at a time — an identical-spec tee COLLAPSES into the winner's existing row (rounds re-pin to the surviving tee_id, holes fill gaps, duplicate deleted; ratings identical so nothing moves numerically), distinct tees carry over with their version tag. Each merge/stub step is also isolated so one failure can't abort the rest of the migration. First run had completed only the Quarry merge (verified: 335 rounds on the canonical row); this deploy completes the remaining 5 merges, 26 stub deletions, and the facilities backfill.",
    ],
  },
  {
    version: "2.126.0",
    date: "2026-07-20",
    changes: [
      "Course registry v1 (Kerry-ratified): one course_id per real course per city, forever. New facilities layer — every course carries a facility_id (1:1 auto-created for single-course properties; Cypresswood/Comanche Trace/Hyatt/TPC SA/Bear Creek group by prefix) so property info has one home. New course_combos (+ combo tees) for the named 18-hole pairings of nines at 27-hole facilities, carrying the OFFICIAL combo 18-hole ratings. course_tees gain version tags (version_label/valid_from/valid_to): GG's '(OLD) - Archived on <date>' duplicate course rows merged into their canonical course with tees carried over as dated versions — period ratings frozen because every historical round pins its tee_id. 26 duplicate clusters resolved: 6 archived versions merged (Quarry, Cedar Creek x2, La Cantera, GC of Texas, Willow Springs), 26 zero-round stubs/misspellings deleted with names aliased to the survivor (Riverside kept separated by city: ATX row untouched, the five SA zero-rows collapsed to one). Boot migration, idempotent.",
      "Handicap rule ratified (Kerry): PLAY OFF THE 18, POST BY THE 9. An 18-hole event's course handicap comes from the tee's (or combo's) 18-hole rating/slope; post-round differentials always post per nine against each nine's own 9-hole data (TGF is a 9-hole-index league). 27-hole facilities: single-nine day → that nine's data; 18-hole event → the combo's official 18-hole tee data; 27-hole match-play day (Hill Country Matches) → three separate 9-hole matches, each off its nine. Selection derives from event structure — never asked.",
      "customers.gender (Kerry-ratified) + ladies-tee marking: tees named with the (L) marker are flagged is_ladies; gender backfills from tees actually played (any ladies-tee round -> F, rounds only on other tees -> M, no rounds -> blank for manual entry). Only NULL genders are ever filled — manual corrections stick.",
      "Stale-scorecard repair: scoring-import-event gains |refresh=<player>[,...] to force-replace a player's stored card from GG's current board — GG score corrections made after our import couldn't self-heal (the cross-tournament dedup treats the existing row as owned). Deletes the player's round + holes + bridged handicap rows, then re-imports fresh. Found via s18.8 Vaaler: GG edited Wilson's front nine post-import (97 -> 91), which also explains the one-skin HIGH-flight delta vs GG ($18/skin x8 vs our $20.57 x7).",
      "New read bridge scoring-facilities: facility count + any facility with more or fewer than one course, for registry verification.",
    ],
  },
  {
    version: "2.125.4",
    date: "2026-07-20",
    changes: [
      "The Austin 'missing 11' hole-data diagnosis: the reconcilers' no_hole_scores_imported reports were (at least partly) an identity gap, not a data gap — cmp_pool_members rows with a NULL customer_id made both reconcilers report players' imported cards as missing (Barna's a9.17 card exists with full back-nine hole detail, yet every Barna/Marques/Cloer/Hogue match read as uncheckable). Two-part fix: (1) boot backfill _backfill_customer_id_on_cmp_pool_members resolves customer_id on unlinked cmp_pool_members rows AND player1_id/player2_id/winner_id on cmp_matches via the canonical resolver (registered in the standard backfill chain per CLAUDE.md rule 6); (2) _cmp_round_row_for gives both reconcilers a nickname-robust person-key NAME fallback against the event's imported cards when the id path misses.",
      "scoring-mp-pools-audit now also lists cmp_pool_members rows with no customer_id link ('unlinked_members') so this class is visible from the bridge; the boot backfill should keep it empty.",
    ],
  },
  {
    version: "2.125.3",
    date: "2026-07-20",
    changes: [
      "Manual result-lock path for the two played matches GG never published a match card for (Hamilton/Wade s9.17, Straiton/Cloer a18.3 — the auto-locker's no_gg_card class). New cmp_lock_match_manual + bridge scoring-mp-lock-one:<chapter>|<A>|<B>[|apply] stamps result_locked_at with a 'Kerry-confirmed <date>, no GG card' note; dry-run by default, refuses unplayed matches, and reports (never restamps) already-locked rows. Runs only on Kerry's explicit confirmation of each result — 30/30 locked is the finish line.",
      "Targeted GG scorecard backfill for ONE past event: import_event_scorecards_by_code + bridge scoring-import-event:<event_code>[@<round_id>] (url = the portal's tournament_results widget) walks the round selector to the event's round and imports its ALL Net then ALL Gross boards (net first so handicaps land — same recipe as the auto-sync, which only covers the newest rounds). Built to backfill the 11 Austin pool matches whose hole scores were never imported (a9.11, a9.12, a9.13, a9.14, a9.17, a18.3).",
    ],
  },
  {
    version: "2.125.2",
    date: "2026-07-20",
    changes: [
      "scoring-mp-relabel-extrahole gains a general one-match form (<chapter>|<A>|<B>|<to>|<expect_margin>[|apply][|force]) and cmp_relabel_margins accepts per-update force to relabel a result-locked row, refreshing the lock note to document the final label. Built for Kerry's ruling that Ellis d. McCrary s9.14 was won via putt-off — margin relabeled '1Up' -> 'Putt Off' to match the Niester/Wade and Chandler/Peterson convention.",
    ],
  },
  {
    version: "2.125.1",
    date: "2026-07-20",
    changes: [
      "scoring-mp-lock classifier: a halved pool match (stored 'Tied'/no winner, GG card AS/no winner) is agreement, not a conflict — locks as gg-verified. Caught by the SA dry run (Rideout/McCrary s18.7).",
    ],
  },
  {
    version: "2.125.0",
    date: "2026-07-20",
    changes: [
      "Match Play reconcilers now walk holes in PLAY ORDER (Kerry 2026-07-20: a 9-hole match starting on 4 plays 4..9 then wraps to 1..3 — it never goes to 10). Both read-only reconcilers previously walked holes in ascending number order, which made close-out margins (X&Y counts holes remaining IN PLAY ORDER) wrong for every shotgun/staggered start — that was the source of the margin 'mismatches' reported against stored results, which were correct all along. Play order comes from GG's own match card snapshot (explicit per-hole order, else wrap from the start hole).",
      "Result hardening: cmp_matches gains result_locked_at/result_locked_note. New cmp_lock_verified_results (bridge: scoring-mp-lock:<season>|<chapter>[|apply]) stamps a lock on every match whose stored result matches GG's own card exactly, or where GG shows AS and we recorded the extra-holes/putt-off outcome. Locked results refuse winner/margin changes and deletion in cmp_save_match (409 from the API), cmp_relabel_margins (locked_skip), and cmp_clear_match, unless force=True is passed deliberately. GG-card conflicts and matches with no GG card are reported, never auto-locked.",
    ],
  },
  {
    version: "2.124.4",
    date: "2026-07-20",
    changes: [
      "Match Play standings: tapping a player's name now scrolls that name to the top of the window (under the sticky header stack) when their match cards expand, so the cards fill the screen instead of opening below the fold (Kerry 2026-07-20).",
    ],
  },
  {
    version: "2.124.3",
    date: "2026-07-19",
    changes: [
      "Pts rows restored on POOL match cards (Kerry: pool play shows points, knockouts don't — v2.123.0 removed them from the shared renderer, which wrongly killed them on pool cards too). Pool scorecards again show the per-hole points rows with totals; knockout cards stay clean. Post-decision holes already render in gray on pool cards when Golf Genius has the scores — a pool card missing trailing holes (e.g. Hamilton/Campos 6/02) means GG has no strokes recorded for those holes, not that the card is hiding them.",
    ],
  },
  {
    version: "2.124.2",
    date: "2026-07-19",
    changes: [
      "New scoring-unenroll bridge command exposing the existing remove_season_contest_enrollment flow (snapshot removal record, clear the purchase's contest flag, drop the enrollment) so a refund-withdrawal can be recorded without the UI. Used for Campos's injury withdrawal from SA City Match Play — the pot recomputes from remaining entrants (10 → 9 × $40 = $360) automatically, since the Payouts sheet derives N live from enrollments.",
    ],
  },
  {
    version: "2.124.1",
    date: "2026-07-19",
    changes: [
      "Withdrawals can carry a short reason code shown on the chip (Kerry): 'WD · INJ' for an injury withdrawal, stored as cmp_pool_members.withdrawn_reason (uppercased, max 12 chars, cleared when the WD flag is cleared). The manager route and the scoring-mp-wd bridge both accept the reason. Campos is flagged WD · INJ.",
    ],
  },
  {
    version: "2.124.0",
    date: "2026-07-19",
    changes: [
      "Withdrawal is now RECORDED on Match Play pool members (Kerry: WD wasn't showing on Campos). The WD tag previously relied on a played-zero-matches guess, which misses a player who played some matches and THEN withdrew. New cmp_pool_members.withdrawn flag, set by managers (POST /api/cmp/pools/<id>/members/<name>/withdrawn, or the scoring-mp-wd bridge); standings carry it and the UI shows WD + dimmed row while keeping the real result dots for matches actually played. The zero-matches heuristic remains as a fallback.",
      "Pool standings badges ($20 pool-winner, ADV, WD) are larger — 0.74rem with roomier padding (were a squinty 0.6rem).",
    ],
  },
  {
    version: "2.123.11",
    date: "2026-07-19",
    changes: [
      "Pool headers get the same dark #1B1B1B band as the match cards (Kerry): 'POOL B · 5 players · in progress' in Bitter uppercase on dark with the MATCHES chip in TGF orange, replacing the plain underlined row. Hover/tap states darken the band; the expanded state keeps the orange-filled chip.",
    ],
  },
  {
    version: "2.123.10",
    date: "2026-07-19",
    changes: [
      "Pool footer legend rewritten from a five-line run-on paragraph into three short lines: 'Rank: match points → head-to-head → Stableford' / '$20 pool-winner bonus · ADV advances · WD withdrew' / 'Tap a player for their matches.' Dropped the when-it-pays detail (lives on the Payouts tab) and the 'or Matches for the whole pool' hint (the button is self-labelling).",
    ],
  },
  {
    version: "2.123.9",
    date: "2026-07-19",
    changes: [
      "Pool note ('Everyone counts three matches') fixed on mobile: the side-by-side label + paragraph layout squeezed the text into a near one-word-per-line column with a tall dead box. It now stacks — label on top, one full-width line under it — and the copy is cut to a single sentence: 'Standings count each player's first three matches by date — a 4th (scheduling extra) counts only for the opponent.'",
    ],
  },
  {
    version: "2.123.8",
    date: "2026-07-19",
    changes: [
      "City Match Play subtext: 'KO of 4' → 'knockout of 4' (Kerry — still fits on one line with the earlier trims).",
    ],
  },
  {
    version: "2.123.7",
    date: "2026-07-19",
    changes: [
      "Match card headers are now a dark #1B1B1B band (Kerry: the pale strip was too washed out) — 'Semifinal 1 - Falconhead · 07/19' renders in Bitter uppercase on dark, echoing the nav and the active KNOCKOUT pill, with the status (FINAL/TBD) in TGF orange and LIVE in green. Applies to every Match Play card (knockout, pools).",
    ],
  },
  {
    version: "2.123.6",
    date: "2026-07-19",
    changes: [
      "The 3rd-place (consolation) match block on the Match Play knockout is now MANAGER-ONLY (Kerry: may not run this season). Members and view-only no longer see it; managers/admins keep the block — labeled '· hidden from members' — so they can still schedule and record a 3rd-place match if they decide to run one. The payout tie-policy (semifinal losers split 3rd/3rd+4th money if no consolation is played) is unchanged.",
    ],
  },
  {
    version: "2.123.5",
    date: "2026-07-19",
    changes: [
      "Match Play vertical rhythm tightened to Kerry's max-15px rule: every gap between sections is now ≤15px. The biggest offender was the (member-hidden) Seed/Clear button row above the bracket, whose 16px margin stacked on the subtab pills' 16px for a ~32px hole between the pills and SEMIFINALS — its margin now lives on the buttons themselves so hidden buttons add zero gap. Also capped: subtabs (14px), header card (14px), between rounds (14px, was 19), pool cards (14px, was 24), champion card and consolation block (14px).",
    ],
  },
  {
    version: "2.123.4",
    date: "2026-07-19",
    changes: [
      "Removed the stray horizontal bar between bracket match cards (Kerry). The invisible match wrapper kept its base box-shadow, and the empty space under each card (the card's contained bottom margin) painted that shadow as a faint rounded grey rule between Semifinal 1 and 2. The wrapper is now fully unstyled in the V2 view and matches are separated by a plain 12px gap.",
    ],
  },
  {
    version: "2.123.3",
    date: "2026-07-19",
    changes: [
      "More Match Play redundancy trimmed (Kerry review). The green winner footer under a decided bracket match ('Jay Hogue (6&5) City Champ Practice Round - Falconhead') is gone in the V2 view — the arrow strip already shows winner + margin and the header shows the course; the legacy pill view keeps it. The expanded scorecard caption no longer restates 'Started on hole 10' (the card head carries it) — it now reads 'Shown in play order. Circles mark…'. 'Connecting to live scoring…' only appears when the match has an event dated today or earlier — an unscheduled/future match (Semifinal 2) has nothing to connect to. Also fixed the 'Falcomhead' typo in the Practice Round event's course field.",
    ],
  },
  {
    version: "2.123.2",
    date: "2026-07-19",
    changes: [
      "Match Play header/card polish (Kerry). HOW IT WORKS button is left-aligned. The City Match Play subtext is shortened to fit one line ('$40 × 10 · $400 pot · 2 pools → KO of 4'). The seed/wildcard legend is hidden in the current (arrow-strip) bracket view since those cards don't show seed/WC chips. Removed the redundant 'Holes 10–18' / 'Holes 1–9' block labels — the hole numbers are already in each block's Hole row. Course now shows in the match header for MEMBERS too: cmp_get_bracket joins the linked event so the bracket carries a member-safe course + event name + date (the /api/events list is view-only+ and members can't fetch it). The numbered round label ('Semifinal 1 - Falconhead') and the course now survive the live/cache re-render paths via data-live-matchno/matchcount/course.",
    ],
  },
  {
    version: "2.123.1",
    date: "2026-07-19",
    changes: [
      "Match Play bracket de-cluttered (Kerry). Dropped the redundant final-result pill on the scorecard (e.g. 'Hogue 6&5') — the head arrow already shows the winner and margin; the live running margin still shows. The seed/wildcard legend now appears only when the bracket actually carries seeds or wildcards. Removed the 'Bracket · Knockout of N' title. The round-group header (SEMIFINALS) is now black and a bit larger. Each match header is numbered with its course — 'Semifinal 1 - Falconhead', 'Semifinal 2 - <course>' — instead of the shared 'Semifinals · <event> · <date>'. Scorecard captions drop 'Hole-by-hole from Golf Genius' and keep 'Started on hole N'.",
    ],
  },
  {
    version: "2.123.0",
    date: "2026-07-19",
    changes: [
      "Match Play knockout scorecard cleaned up (Kerry). Removed the per-hole 'Pts' rows — match play has no per-hole Stableford, so the running state is just the hole-winner circles and the margin. Handicap strokes ('pops') are now a clear player-colored dot pinned to the top-right corner of each hole cell, instead of the near-invisible 3px grey tick. Added a 'Strokes off low' header on each card showing each player's total match pops (e.g. Barna 0 · Hogue 1), so the match handicap is visible at a glance.",
    ],
  },
  {
    version: "2.122.9",
    date: "2026-07-19",
    changes: [
      "ensure_courses_from_history now skips Golf Genius artifacts rather than minting them as real courses: 'Copy of …' event copies, '… - 2' second-instance re-runs, and bare nine fragments (e.g. 'Lakes'). Those are reported under skipped_as_junk for review.",
    ],
  },
  {
    version: "2.122.8",
    date: "2026-07-19",
    changes: [
      "Course-database cleanup tooling (Kerry). New audit_courses() reports duplicate course rows (grouped by a normalized key, with per-row scoring-round counts) and every handicap-round course name that has no courses row yet. New ensure_courses_from_history() gives each such course its own courses row + course_id, dup-aware so a venue already present under a different label isn't duplicated (those are withheld for the dedupe review); new rows carry name + short_name and get chapter/city/rating details enriched later as GG history fills in. Bridges: scoring-courses-audit, scoring-courses-ensure.",
    ],
  },
  {
    version: "2.122.7",
    date: "2026-07-19",
    changes: [
      "Short-name pins for two Houston multi-course facilities: 'Cypresswood Golf Club | Tradition' → 'Cypresswood | Tradition' and 'Bentwater Yacht & Country Club | Weiskopf Course' → 'Bentwater | Weiskopf', matching the Facility | Course convention. Applied via the scoring-course-short-pins bridge.",
    ],
  },
  {
    version: "2.122.6",
    date: "2026-07-19",
    changes: [
      "Rounds tables now show a colored year breaker row whenever the list crosses into another calendar year. Because dates render as M/D, a year boundary (e.g. from 2026 rounds into 2025) was invisible; a dark full-width band with the year now marks each transition. Added on both the Handicaps expanded-rounds table and the Customers → Scores table. On Handicaps the breaker hides/shows with the 'older rounds' toggle like the other separators.",
    ],
  },
  {
    version: "2.122.5",
    date: "2026-07-19",
    changes: [
      "Fix: the ±1-day played-side fallback needs the scorecard's course name, but scoring_rounds stores course_id, not a name — the backfill query now joins the courses table to get it. (Supersedes the .4 attempt that selected a non-existent column.)",
    ],
  },
  {
    version: "2.122.3",
    date: "2026-07-19",
    changes: [
      "Played-side backfill now tolerates the one-day date offset between a handicap posting and its scorecard. Some events (e.g. s9.1 The Quarry) have the handicap posting stamped 03-18 while the scorecard is 03-17, so the exact-date match found no card and left the side blank even though the card clearly existed. When there's no exact-date card, the backfill now accepts a same-course card within ±1 day (course name normalized so 'The Quarry Golf Club' and 'The Quarry Golf Course (OLD) …' match). This fills the last blank sides where a scorecard exists.",
    ],
  },
  {
    version: "2.122.2",
    date: "2026-07-19",
    changes: [
      "Played-side backfill name fallback now normalizes 'LAST, First' (scorecards) and 'First Last' (handicap postings) to one key, so a posting with no customer link still matches its scorecard by name. This catches rounds the customer_id match can't reach because the posting was never linked to a customer.",
    ],
  },
  {
    version: "2.122.1",
    date: "2026-07-19",
    changes: [
      "Played-side backfill now matches unbridged handicap postings to their scorecard by customer_id (via handicap_player_links), not by name. Handicap rounds store names as 'First Last' while scorecards store 'LAST, First', so the earlier name-based fallback silently missed every posting that wasn't already bridged to a card — including rounds whose scorecard clearly exists (e.g. a Quarry front nine). Matching on the customer identity key catches those, so more rounds get their front/back recorded.",
    ],
  },
  {
    version: "2.122.0",
    date: "2026-07-19",
    changes: [
      "Played side is now RECORDED, not derived live (Kerry-ratified). Each 9-hole handicap posting stores the nine it represents — front (holes 1–9) or back (10–18) — in a new handicap_rounds.nine column, populated from the round's scorecard at import time. Previously the Scores/Handicaps card figured the side out live from each round's linked scorecard on every page load, so a posting whose scorecard link was missing or ambiguous showed a BLANK side even when a scorecard proving the nine existed (e.g. Kerry's 3/18 The Quarry front nine). Now the side is stamped once and read everywhere. A one-time backfill stamps front/back onto every existing round we can resolve from a scorecard; named-nine courses (Comanche, Hyatt) stay blank by design since their nine is in the course name. Scores/differentials are never touched, so frozen results are unaffected.",
    ],
  },
  {
    version: "2.121.13",
    date: "2026-07-19",
    changes: [
      "Squaw Valley (Glen Rose) short names corrected. Its two 18-hole courses are Apache Links and Comanche Lakes (confirmed on the course's site) — not 'Lakes/Creeks'. Added short-name pins so they read 'Squaw Valley | Links' and 'Squaw Valley | Lakes', matching the Facility | Course convention used for TPC and Comanche. The stored course that was showing 'Squaw Valley GC | LAKES' is the Comanche Lakes course and now shows 'Squaw Valley | Lakes - <side>'. Pins are keyed on 'squaw' so they never collide with The Club at Comanche Trace.",
    ],
  },
  {
    version: "2.121.12",
    date: "2026-07-19",
    changes: [
      "Squaw Valley Golf Course joins TPC San Antonio as a multi-18-course facility: it has two 18-hole courses (Lakes and Creeks), so 'Lakes'/'Creeks' name the COURSE, not a nine, and a played side reads Front/Back. Added 'squaw' to the multi-18-course facility list, so 'Squaw Valley GC | LAKES' now shows the side played instead of being treated as a named nine. Genuine tri-nine facilities (Comanche Trace, Hyatt Hill Country) are unaffected.",
    ],
  },
  {
    version: "2.121.11",
    date: "2026-07-19",
    changes: [
      "Customers → Scores table is tighter on mobile: every column is left-aligned (Score/Diff/Used were right/center-aligned, which spread them out on the narrow horizontal scroll), horizontal cell padding is reduced, and dates show as M/D (e.g. 7/18) instead of the full YYYY-MM-DD. The six columns now pack close together on the left so the sideways scroll is short. Desktop keeps its roomier layout with right-aligned numerics and full dates.",
    ],
  },
  {
    version: "2.121.10",
    date: "2026-07-19",
    changes: [
      "Handicaps/Scores: TPC San Antonio's Oaks and Canyons now read '— Front / — Back' for the side played, instead of being treated as named nines. TPC San Antonio is one facility with TWO 18-hole courses (the Oaks Course and the Canyons Course), so 'Oaks'/'Canyons' name the COURSE, not a nine — a played side of either is a Front or Back like any other 18-hole course. The named-nine rule previously matched on the trailing word alone, which couldn't tell 'TPC | Oaks' (a course) from 'Hill Country | Oaks' (a genuine Hyatt nine); it now excludes multi-18-course facilities (TPC) by name, so the real tri-nine facilities — Comanche Trace (Creeks/Hills/Valley) and Hyatt Hill Country (Lakes/Oaks/Creeks) — keep their nine names and everything else reads Front/Back.",
    ],
  },
  {
    version: "2.121.9",
    date: "2026-07-19",
    changes: [
      "Customers → Scores tab now scrolls sideways on mobile. The scores table has six columns (Date, Course, Tee, Score, Diff, Used) but its wrapper had no horizontal-scroll setting, so on a phone the Tee/Score/Diff/Used columns were simply clipped off the right edge with no way to reach them. The wrapper now has overflow-x:auto (max-width 100%, touch momentum), so the table scrolls within its card while the rest of the page stays put — same fix on all three render paths (mobile expand + both desktop detail cards).",
    ],
  },
  {
    version: "2.121.8",
    date: "2026-07-18",
    changes: [
      "Handicaps: generic 18-hole courses played as a single nine (Silverhorn, The Quarry, Canyon Springs, etc.) now correctly show '— Front / — Back'. The prior guard keyed on whether the tee had 18 holes imported, which failed for a course only ever played as one nine; it now keys on whether the course NAMES its nines. A course that names its nines (Comanche Creeks/Hills/Valley, TPC Oaks/Canyons, Hyatt Oaks/Lakes) keeps its nine's name and is never labeled Front/Back; every other 9-hole round is a front (holes 1–9) or back (10–18) of an 18-hole course.",
    ],
  },
  {
    version: "2.121.7",
    date: "2026-07-18",
    changes: [
      "Played-nine label now shows consistently on the Customers → Scores tab too, via a new shared static/js/course-label.js (window.courseNineLabel / window.teeLabel). A round reads its course with the nine PLAYED — generic 18-hole courses as 'Course - Front/Back' (holes 1–9 = Front, 10–18 = Back), named-nine courses (Comanche Creeks/Hills/Valley, Hyatt Oaks/Lakes) as their name — and the Tee column drops 'Tee' and the nine suffix. Same rule the Handicaps card uses, now shared so both stay in sync.",
    ],
  },
  {
    version: "2.121.6",
    date: "2026-07-18",
    changes: [
      "Handicaps nine-label clarification (Kerry): a course that NAMES its nines (Comanche Creeks/Hills/Valley, Hyatt Oaks/Lakes/Creeks, etc.) keeps that nine's NAME on the Course column and never gets a generic 'Front/Back' — those are stored as single-nine entries with the name already in the course name. Only courses with generic front/back nines (Kissing Tree, Vaaler, Silverhorn, Quarry) get '— Front / — Back'. No behavior change from 2.121.5; corrects the wording (there are no true 9-hole courses on the schedule).",
    ],
  },
  {
    version: "2.121.5",
    date: "2026-07-18",
    changes: [
      "Handicaps card now shows the nine PLAYED (— Front / — Back) on the Course column for every generic 18-hole course, not just when the back nine deviated. Derived from the holes actually played (1–9 = Front, 10–18 = Back). Courses that name their nines keep their nine name instead (see 2.121.6). Supersedes the earlier back-only rule.",
    ],
  },
  {
    version: "2.121.4",
    date: "2026-07-18",
    changes: [
      "Handicaps card Tee column: drop the Front/Back nine off the tee entirely (the nine already shows on the Course column), so \"1 - Blue Tee — Back 9\" now reads just \"1 - Blue\". Still drops the redundant word \"Tee\" (\"1 - Gold Tee\" → \"1 - Gold\"). Display-only; stored tee names unchanged.",
    ],
  },
  {
    version: "2.121.2",
    date: "2026-07-18",
    changes: [
      "Handicaps (backend): added the two-nine posting path for 18-hole events — derive_18hole_rounds_as_two_nines() writes each player's round as a front-9 and a back-9 handicap record, each with that nine's own course rating + slope (TGF is a 9-hole-index league). Same WHS net-double-bogey math and identity/dedup as the 9-hole path; a tee with no per-nine rating supplied is skipped, never guessed. Wired the s18.8 Vaaler Creek event (per-nine ratings from GG course setup) behind a dry-run/apply bridge. No member-facing UI change.",
    ],
  },
  {
    version: "2.121.1",
    date: "2026-07-18",
    changes: [
      "Match Play scorecards no longer show a fabricated (illustrative) hole map — ever. A card renders ONLY Golf Genius's real hole-by-hole (scores + handicap pops); with no GG detail it shows just the result strip. Fixes recorded bracket matches falling back to invented scores/pops that didn't match the GG card (result was right, the hole detail wasn't).",
      "Recorded bracket matches now pull GG's real card behind the frozen result: the poller/cache hydrates a recorded card once with GG's actual scores and pops (aligning display to GG per the frozen-results rule — the recorded winner/margin never change), instead of leaving it on a placeholder. In-progress cards still refresh every 60s; recorded cards are hydrated once, not re-polled.",
    ],
  },
  {
    version: "2.121.0",
    date: "2026-07-18",
    changes: [
      "Match Play one-tap record from Golf Genius (Kerry-ratified): when GG shows a DECISIVE final for an in-progress bracket match, the manager card surfaces a highlighted 'Record from GG: <winner> <margin>' button and pre-fills the winner + margin controls. Tapping it runs the exact same Save path (records the result and auto-advances the winner) — and it stays fully editable afterward, so a scoring correction or an extra-holes result can be changed. Deliberately does NOT fire on a mid-round lead or an all-square-through-18 (extra holes) — those still need a human decision. Manager view only.",
      "Match Play live scoring now persists across reloads: the last live score is cached in the browser and painted instantly on load, so an in-progress card no longer sits blank for ~30s waiting on Golf Genius — it shows the last-known state immediately, then refreshes live.",
    ],
  },
  {
    version: "2.120.4",
    date: "2026-07-18",
    changes: [
      "Match Play live scoring now shows a status line on an in-progress card until it goes live (\"Connecting to live scoring…\", or the specific reason it can't yet — network/HTTP error, no match found, or waiting for the first hole). Surfaces why a card is still on the scheduled strip instead of leaving it silent, and confirms when the live feed is connected but no holes are posted.",
    ],
  },
  {
    version: "2.120.3",
    date: "2026-07-18",
    changes: [
      "Match Play live poll made reliable on load: an in-progress bracket card now kicks quick retries (every 5s, up to 5x) until it goes live, instead of showing the plain scheduled strip for up to a full minute while Golf Genius's first server-side walk lagged or briefly missed. Each card's fetch/render is also guarded so one hiccup can't stall the others. Once live, it settles into the steady 60s refresh.",
    ],
  },
  {
    version: "2.120.2",
    date: "2026-07-18",
    changes: [
      "Match Play scorecard now shows the FULL match — every hole they'll play (all 18, or 9 for a 9-hole match), not just the holes posted so far. Played holes fill in with scores/dots/points; the rest render blank/pending. Match length comes from the Golf Genius event code (s18.8 → 18, a9.16 → 9); when the code isn't available (older stored details) it falls back to showing the posted holes. Applies to the collapsed hole-dots row and the expanded scorecard alike, so a live match mid-round reads as a full card filling in hole by hole.",
    ],
  },
  {
    version: "2.120.1",
    date: "2026-07-18",
    changes: [
      "Match Play live scoring: a live (in-progress) match no longer greys out holes mid-round. The GG parser's closed_at (clinch hole) is only meaningful for a completed match; mid-round it can flag a running lead as a false clinch, which would have greyed real live holes. Live cards now ignore closed_at entirely — every played hole shows in full color as the round progresses.",
    ],
  },
  {
    version: "2.120.0",
    date: "2026-07-18",
    changes: [
      "Match Play is LIVE (Kerry go, 2026-07-18): the new Match Play tab — CD scoreboard, pool cards, hole-dots, expandable scorecards, seeded bracket, and Golf Genius live scoring — now shows for all members and managers. Kill switch preserved: set MATCHPLAY_V2=0 on Railway to instantly revert everyone to the legacy tab.",
      "Match Play scorecard: per-hole match points now show on EVERY expanded card — restored on the 18-hole cards and ADDED to the 9-hole Golf Genius cards (previously blank). Points come from the per-hole winner flag (hole winner 2, loser 1, halve 2/2); dead holes after the clinch and unplayed holes carry no points. Corrects the prior release that removed them from the 18s instead of adding them to the 9s.",
    ],
  },
  {
    version: "2.119.9",
    date: "2026-07-18",
    changes: [
      "Match Play live scoring (frontend): in-progress bracket matches now live-poll Golf Genius once a minute and re-render just that card with the current match state — running net hole-dots from the correct starting hole, a 'LIVE · thru N' status chip, the leader's running margin on the strip bar (e.g. Moreno 2 UP), and a LIVE result line on the expanded scorecard. Wired for today's 18-hole semifinal (Moreno vs Chandler). Polling targets only cards tagged in progress (both players present, no recorded winner) via /api/cmp/live-match; a card drops out of the poll once GG shows a winner, and the frozen recorded result takes over on the next load. Cards with no holes posted yet stay as scheduled. MATCHPLAY_V2-gated; flag-off behavior unchanged.",
    ],
  },
  {
    version: "2.119.8",
    date: "2026-07-17",
    changes: [
      "Match Play live scoring (backend): cmp_fetch_live_match() fetches Golf Genius current match-play detail for one in-progress match on demand (walks the chapter tournament_results widget, finds the newest round MATCH PLAY game containing the pair, returns the live per-hole detail with thru/margin). Server-side cached ~25s so many viewers polling every 60s collapse to one GG walk. Exposed at GET /api/cmp/live-match?chapter=&a=&b= (member read). Frontend polling wires next.",
    ],
  },
  {
    version: "2.119.7",
    date: "2026-07-17",
    changes: [
      "Match Play GG importer: unwrap a GG name marker like Bl[HAMILTON, Doug] to the real HAMILTON, Doug so Doug Hamilton match-play matches resolve and store instead of falling to the 18-hole placeholder. Applied in the parser and in the name-match helpers. Added a reset option to the importer/bridge (scoring-mp-import-gg:reset) to force a full re-walk so previously-unmatched matches get stored.",
    ],
  },
  {
    version: "2.119.6",
    date: "2026-07-17",
    changes: [
      "Match Play scorecard: removed the per-hole Pts (Stableford) rows everywhere. Match play is decided hole-by-hole, not by Stableford points, so points no longer show on the placeholder 18-hole cards (they were never on the GG-sourced 9-hole cards) — the two now match.",
    ],
  },
  {
    version: "2.119.5",
    date: "2026-07-17",
    changes: [
      "Match Play scorecard/dots: once a match is decided, the holes played out AFTER the clinch (dead holes) no longer show a winner color circle. Their gross scores still show but greyed out; in the collapsed dots row those holes render as empty (hollow) circles. Driven by GG closed_at_order in play order, so a 4&3 greys the last holes correctly.",
      "Read-only diagnostic scoring-mp-detail:<chapter>|<A>|<B> dumps a stored gg_match_detail (incl. a per-hole p1/p2 stroke summary) to check whether GG per-hole pops were captured.",
    ],
  },
  {
    version: "2.119.4",
    date: "2026-07-17",
    changes: [
      "Match Play scorecard: hole columns are now uniform width. The grid uses table-layout:fixed with fixed label/total columns so the nine (or eighteen) hole columns share the remaining width equally — a winner-circle cell no longer pushes its column wider than the plain-number columns.",
      "Match Play: clear cached cross-chapter standings/bracket at the start of each pool load so switching Chapter never renders the previous chapter's standings against the new chapter's pools (defensive fix while chasing an SA-shows-empty report; SA pools/matches are confirmed present in the data).",
    ],
  },
  {
    version: "2.119.3",
    date: "2026-07-17",
    changes: [
      "Match Play render: 9-hole matches now show a 9-hole card and 9 dots (was 18). GG cards carry all 18 hole columns even for a 9-hole match (holes 10-18 blank), so the converter now drops the unplayed holes before rendering: a 9-hole match yields 9 dots and a single 9-hole scorecard starting on its actual starting hole and ending on the last hole played with the total, instead of a padded 18-hole grid with an empty back-nine block.",
    ],
  },
  {
    version: "2.119.2",
    date: "2026-07-17",
    changes: [
      "Handicaps: suppress the trend arrow for players idle 30+ days (Kerry). A trend mark computed off stale rounds is misleading, so get_all_handicap_players now nulls handicap_trend when the player has not posted a round in more than 30 days (measured to today, Central). The row then shows the neutral — in place of the up/down arrow, the same no-trend state new players already display. Index and round counts are unaffected.",
    ],
  },
  {
    version: "2.119.1",
    date: "2026-07-17",
    changes: [
      "Match Play sandbox render now uses REAL Golf Genius hole detail when available (cmp_matches.gg_match_detail), replacing the placeholder engine per match. mpHolesFromGG() converts GG detail to the same render shape: actual hole COUNT (9 or 18 — both exist; a 9-hole match no longer renders as 18), real starting-hole PLAY ORDER, real per-hole NET winner (dots + winner circles), real gross scores, and real handicap-stroke ticks. GG players are mapped to the strip A/B sides by surname+first-initial so the dots align with the recorded winner. GG-sourced scorecards show gross in play order with real hole numbers and omit the Par/Pts rows (match play has no per-hole Stableford); the caption reads from Golf Genius rather than illustrative. Matches without GG detail fall back to the labeled placeholder. Frozen winner/margin still come from the stored record.",
    ],
  },
  {
    version: "2.119.0",
    date: "2026-07-17",
    changes: [
      "Match Play sandbox render updated to the full CD member-scoreboard spec (gated behind MATCHPLAY_V2, off in prod): each match strip carries a center hole-dots row (per-hole winner colors) and a click-to-expand hole-by-hole scorecard grid (FRONT/BACK 9, winner circles, stroke ticks, margin pill); pool standings show chronological W-L-T dots; player rows are full-width accordion toggles (opening one collapses the previous). Placeholder hole engine is deterministic and never contradicts the recorded result (labeled illustrative) until real GG match detail is wired in.",
      "Match Play pools: the WHOLE pool header is now the expand target (full width), not just the Matches chevron — click or keyboard-activate anywhere on the pool name row to show/hide that pool completed matches. The chip is now a visual affordance that fills accent when open; role=button + aria-expanded + focus ring for accessibility.",
    ],
  },
  {
    version: "2.118.14",
    date: "2026-07-17",
    changes: [
      "Docs: Match Play PARTICIPATION & COMMUNICATION layer for CA. Match Play demands more participation, so idle players break the pool/bracket. Captured: per-match/round completion deadlines (complete-by X) with automated reminders/escalation; DQ boundaries for non-participation (missed matches / past-deadline / weeks idle) and walkover/forfeit + standings handling; matches played OUTSIDE TGF events (self-scheduled makeups, event-independent, pair-keyed); automated participant comms driven by match state. Plus format-history context (earlier double-elimination playback format produced more matches than the current pools->knockout). In the CA handoff and game-engine.md D-MP-11.",
    ],
  },
  {
    version: "2.118.13",
    date: "2026-07-17",
    changes: [
      "Match Play: relabel the two a9.17 extra-hole margins from 1 UP to 10H (Kerry-directed). Youngs def. Marques and Barna def. Cloer were all square through regulation and decided on an extra hole; the recorded 1 UP hid the sudden-death fact. cmp_relabel_margins() updates ONLY the margin (winner, W-L-T records, knockout qualifiers, and seeding untouched), guarded so it only writes when the current margin/winner match the expected values. Bridge scoring-mp-relabel-extrahole (dry-run by default; :apply writes).",
    ],
  },
  {
    version: "2.118.12",
    date: "2026-07-17",
    changes: [
      "Docs: extra-hole notation corrected to Ryder Cup shorthand (Kerry) — holes PLAYED + H (a 9-hole match decided on the first extra hole = 10H; holes played, not the physical hole number, so a shotgun match started on 5 also reads 10H). Added the extra-holes feature requirement: score entry for the extra hole(s) that ALSO configures the handicap pops (continue the off-lowest allocation onto extra holes by stroke index so net decides the hole), recorded as NH. Captured in the CA handoff and game-engine.md D-MP-11.",
    ],
  },
  {
    version: "2.118.11",
    date: "2026-07-17",
    changes: [
      "Docs: Match Play tie-resolution decision flow + scaling north star for CA. Added the ultimate-app requirement that at end of regulation on an All Square match the app presents STAGE-AWARE options (rules-derived): a pool round offers End-in-a-tie/Halved (half point each); a knockout prompts How do you want to determine the match? Putt-Off or Extra Holes, surfacing practical constraints (has to be completed tonight - daylight/pace/availability). Added the overarching design north star: simplicity for MANY chapters + scaling (one rule over per-chapter special cases, derive-dont-ask, near-zero bespoke per-chapter setup; the future uniform allowance is the model). Captured in the CA handoff and game-engine.md D-MP-11.",
    ],
  },
  {
    version: "2.118.10",
    date: "2026-07-17",
    changes: [
      "Docs: Match Play registration/eligibility for CA. Added the front-of-lifecycle stage — signup timing + prerequisites, notably an established-handicap GATE (a player without an established handicap is held out until X qualifying rounds; X, what qualifies, hard-block vs flag, and refund/hold/defer interaction TBD), plus membership/chapter/good-standing prerequisites. Captured in the CA handoff (section 0) and game-engine.md D-MP-11.",
    ],
  },
  {
    version: "2.118.9",
    date: "2026-07-17",
    changes: [
      "Docs: extra-hole win notation. An extra-hole (sudden-death) win is recorded as the hole it ended on — e.g. 10H (won on the 10th; H = hole), 18-hole analog the 19th hole — rather than 1 UP, which reads like a regulation win and hides the sudden-death fact. Captured in game-engine.md D-MP-11 and the CA handoff. Correcting the two historical a9.17 margins (Youngs/Marques, Barna/Cloer) from 1 UP to 10H is pending Kerry (winner/record/seed unaffected).",
    ],
  },
  {
    version: "2.118.8",
    date: "2026-07-17",
    changes: [
      "Docs: captured the Match Play mechanics the GG-source audit uncovered. game-engine.md D-MP-11 records the setup/recordation/winner-determination items — starting hole (shotgun, play-order close-out), NET stroke dots, EXTRA HOLES / sudden death (a Tracker GAP: AS-after-regulation matches decided on an extra hole, e.g. Youngs/Marques and Barna/Cloer on hole 10), putt-offs (GAP), the all-square resolution ladder, matches spanning events, and GG-as-audit-source with frozen results. New handoffs/match-play-uncovered-for-CA.md is the lifecycle-organized (purchase→conclusion) handoff for CA's overall Match Play documentation, listing built-vs-gap status. No behavior change.",
    ],
  },
  {
    version: "2.118.7",
    date: "2026-07-17",
    changes: [
      "Match Play GG importer: align by player PAIR across the whole chapter, not by event. TGF match-play matches are played/made-up across different events (e.g. Hogue def. Kirksey 4&3 is recorded on a9.12 in our data but GG scored it under a9.17), so matching within the GG event missed them. Now the importer indexes every cmp_matches row in the chapter (derived from the portal host) by customer_id pair (rule-6) with a surname+first-initial fallback, and records both the GG event and our stored event on each snapshot/mismatch. Added a done-rounds tracker (cmp_mp_import_rounds) so store-mode sweeps converge instead of re-walking every call.",
    ],
  },
  {
    version: "2.118.6",
    date: "2026-07-17",
    changes: [
      "Match Play GG importer verify: compare GG-vs-stored winner on the nickname-robust person key (surname + first initial) instead of raw name tokens, so a spelling variant like GG 'JENKINS, Matt' vs our 'Matthew Jenkins' is recognised as the same winner (aligned) rather than a false mismatch. Margin comparison unchanged.",
    ],
  },
  {
    version: "2.118.5",
    date: "2026-07-17",
    changes: [
      "Match Play GG importer alignment hardening: match GG's match-play players to our stored cmp_matches by customer_id pair (resolved via _resolve_scoring_player, the same LAST,First + alias spine the scorecard importer uses), with a nickname-robust (surname, first-initial) fallback so GG 'JENKINS, Matt' aligns to our 'Matthew Jenkins'. Also dedup the two GG aggregates per match (GG exposes one detail card per player) so each match is snapshotted once. Parser now also captures the GG profile id when the fragment distinguishes both players.",
    ],
  },
  {
    version: "2.118.4",
    date: "2026-07-17",
    changes: [
      "Match Play GG source importer (Kerry-ratified, schema): reads GG's OWN computed match-play detail as the audit source instead of re-deriving it. New email_parser/gg_match_play.py parses each match's /tournaments2/details/<agg> fragment for the STARTING HOLE (GG's starting_hole_mark — shotgun matches start on different holes, e.g. Niester/Wade on 5), the per-hole NET winner flag (GG's own match row), each player's per-hole gross, and the handicap-stroke dots (NET matches). Reading GG's winner flags in PLAY ORDER from the start hole reproduces the recorded winner + margin exactly (validated: a9.16 REYES/JENKINS → start hole 2, JENKINS 5&4, REYES stroked on 8 of 9). cmp_import_gg_match_play() walks the tournament_results widget on a portal, finds each round's MATCH PLAY game, and snapshots the detail onto the new cmp_matches.gg_match_detail column, keyed to the stored match by event + player-name tokens. DISPLAY-ONLY: it never overwrites the frozen winner/margin/records/seeding — any GG-vs-stored disagreement is reported, not applied. Bridge extract='scoring-mp-import-gg[:<round>|verify]'.",
    ],
  },
  {
    version: "2.118.3",
    date: "2026-07-17",
    changes: [
      "Match Play reconciliation CORRECTED for TGF's real handicapping (READ-ONLY, Kerry): the prior cmp_reconcile_hole_results() used the stroke-play strokes_received baked into the GG import — 100% allowance, full-field allocation — which is the WRONG pops for match play and gave bad margins/all-square calls (Chandler/Rideout s9.15 computed AS while GG shows Chandler 1 up). New cmp_reconcile_match_play_75() re-derives each match from the per-hole GROSS using TGF's OFF-LOWEST rule (lower handicapper plays scratch; higher receives the difference on the hardest holes by stroke index) with PER-CHAPTER allowance — San Antonio 75%, Austin 100% — taken from _CMP_ALLOWANCE_BY_CHAPTER. Concessions/gimmes/putt-offs still aren't in the scorecard, so a residual set will still need GG's own match state. Bridge extract='scoring-mp-reconcile75[:<season>|<chapter>|<allow>]'. No data or member-facing change.",
    ],
  },
  {
    version: "2.118.2",
    date: "2026-07-17",
    changes: [
      "Match Play per-hole reconciliation (READ-ONLY, Kerry): cmp_reconcile_hole_results() derives each match's result from the imported GG per-hole scores (net = gross \u2212 strokes_received/pops, lower net wins the hole; standard X&Y close-out) and diffs it against our stored winner/margin. Buckets: aligned, winner_mismatch, margin_mismatch, putt_off (holes all-square but a winner stored \u2014 extra-holes decision hole data can\u0027t show), no_event, no_hole_scores_imported. Feeds the real Slate & Clay hole-dots + expandable scorecard grid (replacing the placeholder engine where GG holes exist). Bridge extract=\u0027scoring-mp-reconcile[:<season>|<chapter>]\u0027.",
    ],
  },
  {
    version: "2.118.1",
    date: "2026-07-17",
    changes: [
      "Match Play visual rollout REBUILT to the approved CD member scoreboard (the first pass had layered D-MP labels on the manager table instead — corrected). New member-facing design: POOLS · KNOCKOUT · PAYOUTS pill sub-tabs that swap; pool standings as rows with rank, $20/ADV/WD chips, W-L-T as colored dots, big Stableford, per-player expand; Slate (#2F5D74) & Clay (#C1673F) arrow match strips with monograms, margins, TIE/PUTT/provenance states; knockout rail with seed/WC chips + legend + consolation + Next-In; dark POT waterfall + bonus/ladder cards. member_mode = read-only scoreboard; admin/manager = same scoreboard plus a collapsible MANAGER editor per pool (result entry, Add/Delete, Seed/Clear, consolation control). Still gated behind MATCHPLAY_V2 (flag off = current tab unchanged).",
      "Sandbox controls: /admin/matchplay-preview gains an Admin | Member view toggle bar (?view=) via SANDBOX_PREVIEW, and the live tab shows an admin-only 'Preview new Match Play design' button so admins reach the sandbox without typing the URL. Known canvas gaps (no per-hole data in /api/cmp): hole-by-hole scorecard grid and live 'thru 13' omitted rather than fabricated.",
    ],
  },
  {
    version: "2.118.0",
    date: "2026-07-17",
    changes: [
      "Match Play visual rollout (#228, platform-claude-approved canvas) — the new Slate (#2F5D74) & Clay (#C1673F) scoreboards, bracket views with seed numbers + wildcard chips + legend (P4), the D-MP-08 consolation block (gated hasConsolation = fieldN>=6, field-aware fallback copy, nothing at N=4-5), the D-MP-09 'Everyone counts three matches' pool note (shown only where a 4-match player exists), D-MP-07 PUTT/TIE/walkover states, and the private-match provenance chip. Plus the five carry-forwards: D-MP-02 chapter/season selectors, D-MP-06 wildcard 'Next In' cut-line, D-MP-03 mode-dynamic pool-assignment copy, N=12 bye render check, and go-green #0d7556 buttons (money stays #047857). POT never PURSE; Stableford labeled; no member-facing 'match points'.",
      "GATED behind the MATCHPLAY_V2 kill switch (SHELL_V2-style): default OFF so members/managers keep the current tab byte-for-byte. Admins preview the new tab on LIVE data at /admin/matchplay-preview; flip env MATCHPLAY_V2=1 to promote it live everywhere after sign-off. The consolation manager control POSTs /api/cmp/consolation and reads the payout `consolation` block (both live from 2.117.6).",
    ],
  },
  {
    version: "2.117.6",
    date: "2026-07-17",
    changes: [
      "D-MP-08 consolation match RECORDING (backend, config v2): cmp_record_consolation(season, chapter, loser_a, loser_b, winner_name) stores the 3rd-place playoff between the two semifinal losers as one cmp_bracket row (round 'consolation'); POST /api/cmp/consolation records or clears it (winner blank = clear). cmp_get_payout_sheet now awards 3rd — and 4th on 4-place ladders — to the consolation winner when recorded, and falls back to the combined-place split (3-place 10/10 · 4-place 12.5/12.5) when it can't be coordinated. Nothing at N=4–5 (only 2 ladder places). Sum-to-pot preserved either way; default behavior unchanged (no consolation row → existing split). The payout return carries a `consolation` block (applies / sf_losers / winner / recorded / places) to drive the manager UI.",
    ],
  },
  {
    version: "2.117.5",
    date: "2026-07-17",
    changes: [
      "I-2 sweep (READ-ONLY, gates R1): sweep_i2_multiplier_removal() computes every handicap player's index with the current ×0.96 'Bonus for Excellence' factor vs without it (×1.00 = modern WHS), the delta, and whether the change crosses a whole-number 9-hole Playing Handicap line at reference slopes 113 (floor) and 125 (typical Texas). Removing 0.96 raises every index, more for higher handicaps. Decision package only — changes nothing. Bridge extract='scoring-sweep-i2'.",
    ],
  },
  {
    version: "2.117.4",
    date: "2026-07-17",
    changes: [
      "D-MP-09 goes LIVE for standings (config-gated): cmp_get_standings now honors pool_rank_rule='dmp09' on a season's PINNED config — first-3-by-date counting, match points-of-3 with ½-ties, aggregate H2H, pool Stableford. Seasons pinned to an older version keep the legacy wins→W−L→Stableford sort (past events frozen). Verified clean by the #217 diff: no advancer/winner changes, only 3 non-advancing reorderings harden.",
      "Re-pin (#223, Kerry-approved): cmp_repin_2026_to_dmp_register() authors a new match_play config version carrying the D-MP-01→09 register as rules-as-data (pool_rank_rule=dmp09, pool_assignment_mode=random, seed_placement=p1_p4, consolation min-N-6 + fallback split, unchanged cross-pool 4-player exception) and pins both 2026 season snapshots (SA + Austin) to it. Bridge extract='scoring-mp-repin'.",
      "get_tracker_source list mode (#220): passing a whitelisted directory (e.g. 'handoffs/') returns its filenames instead of file text, so special-character handoff names no longer have to be guessed. New handoffs/README.md documents the CD review-bundle delivery + deploy-included rule (#222) and naming convention.",
    ],
  },
  {
    version: "2.117.3",
    date: "2026-07-17",
    changes: [
      "D-MP register: game-engine.md updated to the closed D-MP-01→09 register (D-MP-03 random default, D-MP-04 P1–P4 asymmetric placement incl. the index-snapshot → enrollment-date tiebreak, D-MP-08 consolation + fallback split, D-MP-09 unified 3-match counting + points-of-3 rank chain), and the two stale #181 lines folded (flat $20 bonus; N=4 ladder $97/$38 → $100.10/$39.90).",
      "D-MP-09 pool-standings engine: match_play.dmp09_pool_standings() — pure function ranking a pool under the ratified rule (first-3-by-date counting so a forced 4th match counts only for its opponent; match points of 3 with ½-ties → aggregate head-to-head → pool Stableford). Unit-checked against pool-of-4/5/3 and draw/H2H cases.",
      "READ-ONLY standings diff (#217 step 1): database.cmp_standings_diff_dmp09() recomputes both chapters' 2026 pool standings under D-MP-09 and diffs against the live standings that seeded the knockouts, flagging any advancer or winner/runner-up change (verdict clean vs review). Reachable via the probe_golf_genius bridge extract='scoring-mp-standings-diff'. Changes no data — the live brackets and played results stand.",
    ],
  },
  {
    version: "2.117.2",
    date: "2026-07-17",
    changes: [
      "get_tracker_source read-only whitelist now includes handoffs/ (#212, Kerry) — opens the design-claude Match Play canvas handoffs to MCP read so platform-claude's visual-pass review can pull them. Head of the critical path for the member-facing Match Play visual rollout; ships ahead of the D-MP encode work.",
    ],
  },
  {
    version: "2.117.1",
    date: "2026-07-16",
    changes: [
      "Three date-sensitive READ-ONLY reports delivered (financial-audit session, Kerry's priority order): docs/claude/june-2026-tax-slice.md — June ledger income $33,845.15 carries $549 of confirmed exp-promoted income double-counts (+$16 Lee Vasquez a9.13 triple-book) and $2,141 of floating income (Joe Warring $1,809, three $100 contest entries, Lee x2 $16) that any event-derived taxable base misses; corrected ledger figure $33,280.15; venmo-bd regression confirmed NOT in June; cross-month heads-up that Lee's a9.12 $16 was re-booked 07-16 so JULY carries that dup. docs/claude/k3-payout-variance-characterization.md — the -$3/-$2 exact-delta lumps are an ENGINE/MATRIX POT-TIER delta, not pay-time netting (where GG published money exists, paid == GG and our computed is the outlier: s9.10 CTP 23/20/20, s9.7 CTP 39/37/37); other classes are the known a9.13 Team-Net blind-draw shares and pay-time rounding (mostly round-UPs); proposed explanation codes ENGINE_POT_TIER / TEAMNET_SHARE / ROUNDING_PAY. S2 prize exposure run live: 9 REPORTABLE >=$600 (Straiton $1,974.26 leads), 2 W-9-REQUIRED >=$500, 5 WATCH >=$400 before championship payouts. A2 answered: zero fee-double-booked transfer chains across all 107.",
    ],
  },
  {
    version: "2.117.0",
    date: "2026-07-16",
    changes: [
      "IRS-lane read-only reports (fin_audit bridge, financial-audit Deliverable 2 phase): scoring-fin-audit gains four sections. taxslice=YYYY-MM — month-scoped income integrity for the sales-tax webfile: the month's income ledger by category/source, floating income rows (no customer/item/event), cross-writer twin pairs widened to a ±1-day window (catches the date-off-by-one class), and the app's own acct_allocations-sourced tax_reserve shown for context (that table is near-dead, so it is context, not truth). prizes=YYYY — S2 1099-MISC prize exposure: per-customer calendar-YTD totals from tgf_payouts (event-date basis, settled + unsettled so credit-applied winnings count) flagged WATCH >=$400 / W-9-REQUIRED >=$500 / REPORTABLE >=$600, plus the $300-400 next-in-line band. k3 — every computed-vs-actual variance lump with its payout rows, customer, event code/date, and GG's published money for the same player+event (gg_game_results.purse + gg_history_results.money_cents) so Kerry can rule netting-vs-engine-delta on evidence. xferchain — A2 evidence: per-transfer-chain balance (out leg vs in leg via items.transferred_to_id) and whether the fee difference is double-booked by a venmo-bd income row on the target item. All pure SELECT/PRAGMA.",
      "Governance library seed #1 (mailbox #201, Kerry-directed): docs/governance/TGF_Handicap_Standard_v1_0.md committed VERBATIM per the README intake rule. The draft Audit Readiness Standard is NOT mirrored (explicitly held until Kerry ratifies).",
    ],
  },
  {
    version: "2.116.4",
    date: "2026-07-16",
    changes: [
      "Read-only bridge scoring-print-pack:<event_id> returns the assembled Starter Sheet / Cart Signs data (get_event_print_pack) for GATE-1 dry-run fitness checks against real saved pairings.",
    ],
  },
  {
    version: "2.116.3",
    date: "2026-07-16",
    changes: [
      "Deliverable 1 SHIPPED: docs/claude/financial-audit-gap-report.md — the whole-Tracker customer_id + financial + FK gap audit (read-only, quantified, risk-ranked P0-P7). Headlines: exp-promoted ledger rows 367/850 unattributed ($162,176.84) and no re-resolution on alias-add (P0); no event_id on acct_transactions with 1,406 live rows carrying unresolvable event_name strings, four coexisting ledger designs, money stored as dollar-text on items (P1); 8 dangling-FK classes rooted in hard deletes, zero orphaned customer_ids anywhere (P2); 158 live duplicate candidates incl. a $1,879 bank-deposit/exp-promoted twin, Duplicate Detective never run (P5); bank imports stalled since Apr 28-30 with 440 unmatched deposits (P6). tgf_payouts computed-vs-actual variance is only $52.14 total across 25 lumps (max $3) — far healthier than feared; the gap is the missing variance report, not missing money. Every number reproducible via scoring-fin-audit.",
    ],
  },
  {
    version: "2.116.2",
    date: "2026-07-16",
    changes: [
      "fin_audit refinement pass after the first live run: (1) status semantics corrected — 'reconciled' is a LIVE ledger status (bank-matched), so dead-link checks now count only reversed/merged targets; (2) FK map fixes proven by live data — bank_deposits.account_id actually references acct_accounts (ids 3/7), not the vestigial bank_accounts table, and message_log.template_id references message_templates; (3) tgf_payouts variance now judged per lump payment (sum of payout rows sharing an acct_transaction_id vs the actual paid amount) instead of per row, since one Venmo payment covers several category payouts; (4) items.item_price is dollar-formatted TEXT on the live DB — audit strips/CASTs it and reports the typeof() distribution as its own finding; (5) transfer legs (xfer -in/-out source_refs) excluded from the cross-writer duplicate scan — they are double-entry pairs by design.",
    ],
  },
  {
    version: "2.116.1",
    date: "2026-07-16",
    changes: [
      "Financial-audit charter Deliverable 1 instrumentation (READ-ONLY): new email_parser/fin_audit.py runs a whole-DB integrity audit — per-table customer_id coverage/null/orphan/name-only counts (lens A), dangling-FK sweep across every declared REFERENCES clause plus a conventional *_id map with live-schema introspection (lens C), and a financial lens (acct_transactions by status/entry_type/category/source_ref family, floating money, tgf_payouts computed-vs-actual variance, expense promotion integrity, GoDaddy split-sum checks, items outside the ledger, cross-writer double-count candidates). Pure SELECT/PRAGMA — writes nothing. Reachable in-session via the probe_golf_genius bridge: extract='scoring-fin-audit:<tables|customer|fks|ledger|money|dupes|summary>'.",
    ],
  },
  {
    version: "2.116.0",
    date: "2026-07-16",
    changes: [
      "Starter Sheet + Cart Signs printables (B5, Kerry — ready for s9.19). Two print-optimized pages render from the saved pairings: GET /events/<id>/starter-sheet (a one-table sheet of tee time / group / player / tee / index / cart) and GET /events/<id>/cart-signs (one large foldable card per cart, page-break each). Cart split follows the ratified ruling — seats 1&2 = Cart A, 3&4 = Cart B. Print buttons appear in the pairings toolbar once pairings are Saved (the pages read the saved data). Both are standalone print templates with their own @media print / @page CSS. The handicap column is labeled 'Idx' (the 9-hole index the pairings carry) — the full D1 playing-handicap column is a fast follow-up (needs each player's selected-tee slope/rating/par). New helper get_event_print_pack(event_id).",
    ],
  },
  {
    version: "2.115.5",
    date: "2026-07-16",
    changes: [
      "H-2 (results hardening): made the playing-handicap FREEZE explicit. scoring_rounds.playing_handicap is the event-time value written at GG import and never recomputed by our engine (our projection is read-only shadow); re-imports only re-carry GG's value under the handicap/completeness upgrade guards. Added an explicit invariant comment at the import write site and a note in handicap-projection.md: when the untether path begins writing our self-computed playing handicap, it must write ONLY where playing_handicap IS NULL, so an index/cap change can never retroactively alter a frozen round (past-events-frozen + the retroactivity boundary).",
    ],
  },
  {
    version: "2.115.4",
    date: "2026-07-16",
    changes: [
      "Added docs/claude/financial-audit-charter.md — the charter for a dedicated, comprehensive audit of the entire Tracker's financial system and customer_id / FK integrity (Kerry, 2026-07-16). End-state: one FINANCIAL/LEDGER as single source of truth, every financial row tied to a customer_id and an FK home, CPA/IRS-audit-defensible. Documents the known gaps (Venmo receipts captured but customer_id null; one-shot resolution with no re-resolve on alias-add; computed-vs-actual payout variance unreconciled), the read-only-first method, and the phased deliverables. Kicks off in a fresh session; CA architecture guidance solicited via mailbox #199.",
    ],
  },
  {
    version: "2.115.3",
    date: "2026-07-16",
    changes: [
      "H-1 results-hardening audit (read-only): audit_pre_boundary_mvp compares OUR self-computed City MVP (net-points winner) against GG's recorded MVP for every event before the 2026-07-14 boundary and returns the full mismatch list. This is the first place a WHS-cap-driven net-points change surfaces. Bridge scoring-audit-mvp. Changes nothing — it's the pre-July-14 'do our results still match GG' proof.",
    ],
  },
  {
    version: "2.115.2",
    date: "2026-07-16",
    changes: [
      "Pre-boundary MVP badge now shows Co-MVP when GG split the pot (Kerry): if GG recorded more than one MVP winner for an event it paid the money in shares rather than applying a tiebreaker (s18.6 Flying L: Young/Sanford/Fehlis $33.33 each), so all of them now read 'Co-MVP' instead of sole 'MVP' (winner count read from event_mvps; same for a multi-winner GG TGF MVP -> Co-TGF MVP). This split is an outlier to our Net->Gross tiebreaker; going forward (a9.18+) our engine tiebreaks to a sole MVP by default and only a future admin override should force a split.",
    ],
  },
  {
    version: "2.115.1",
    date: "2026-07-16",
    changes: [
      "Retroactivity boundary sharpened to Kerry's clarification: a9.18 Forest Creek is the FIRST event the WHS cap affects results (and is unpaid), so it is authoritatively on our side — the MVP badge boundary is now inclusive (event_date >= 2026-07-14 = ours; before = GG bible). Functionally unchanged for current data (GG had no a9.18 record) but the code now matches the ruling precisely. Docs record the results-authority hierarchy: actual Venmo payouts (IMMUTABLE — nothing paid ever changes) > GG results (bible before a9.18) > our computation (from a9.18 forward), and the records-vs-results distinction (handicap RECORDS update retroactively with the cap; RESULTS do not change pre-a9.18).",
    ],
  },
  {
    version: "2.115.0",
    date: "2026-07-16",
    changes: [
      "MVP badge now respects the ratified retroactivity boundary (Kerry standing rule): our self-computed determination is authoritative only for events AFTER a9.18/s9.18 (2026-07-14). For events on/before that boundary, Golf Genius stays bible — where GG recorded an MVP we defer to it, and our computation only fills events GG never recorded (import lag, e.g. a9.18 Kelly Barna, s9.17 Jeff Young). This fixes a regression where our post-cap handicaps re-crowned a pre-boundary City MVP (s18.6 Flying L: our net points made Sanford the winner, but GG's tiebreaker-resolved MVP is Jeff Young) — GG's frozen result now stands, as ratified.",
      "Read-only MCP access for platform review (Kerry-approved #194/#198): get_tracker_source (whitelisted templates/static/docs + pure engine modules; secrets/DB/app.py/database.py hard-denied), get_app_settings (redacts secret-ish keys), get_gg_snapshots (the GG display cache), and project_playing_handicaps promoted from bridge to a first-class tool. Governance library surfaced through get_tracker_docs (docs/governance/, OneDrive-authoritative mirror). New MCP tools go live for the platform session-side; they are not callable within the session that adds them (frozen inventory).",
    ],
  },
  {
    version: "2.114.2",
    date: "2026-07-16",
    changes: [
      "TGF MVP is now gated to multi-chapter days (Kerry ruling B): on a day where only one chapter fielded the game (the other chapter's event had no players / rained out), the lone City MVP is NOT elevated to TGF MVP — matching GG, which never ran the TGF MVP game on a single-chapter day. Co-TGF-MVP still applies only to genuine multi-chapter ties.",
      "Docs: handicap-projection.md flipped to RATIFIED and handicaps.md updated with the go-live rulings of record (Kerry mailbox #196/#197, 2026-07-16): D1 tee-based playing handicap, D4 nine-hole cap ordering note, R1 remove ×0.96 (sweep-gated, not yet applied), R2 12-month lookback deviation, R3 plus handling held, the layering principle, the standing retroactivity boundary (no handicap change alters results before a9.18/s9.18), and H-5 Star Ranch tee values stand.",
    ],
  },
  {
    version: "2.114.1",
    date: "2026-07-16",
    changes: [
      "MVP badge correctness: our self-computed determination is now the sole authority for any event we've scored (tracked in mvp_computed_events). The GG 'MVP $' import is used only as a fallback for events we've never computed — so a computed event can never show a stale GG badge for a player our engine didn't crown. Recompute also now handles two 18-hole events sharing a date (each is its own day-group).",
    ],
  },
  {
    version: "2.114.0",
    date: "2026-07-16",
    changes: [
      "MVP / TGF MVP badges are now SELF-COMPUTED from our own scorecards — no longer waiting on Golf Genius's 'MVP $' import (Kerry). The badge was missing on recent events (e.g. Kelly Barna a9.18 Forest Creek, Jeff Young s9.17 Silverhorn) because the GG import lagged; now the badge reads our determination directly. Rule (Kerry-ratified): City MVP = most points in the event's MVP side game (net Stableford); ties break Net score, then Gross score; still tied = split. TGF MVP = the City MVP with the most points across the day's linked events.",
      "New Co-MVP and Co-TGF MVP badges for ties: when the tiebreakers can't separate the leaders they split the honor and each shows 'Co-MVP' / 'Co-TGF MVP' (amber / teal) instead of the sole title.",
      "Determination is materialized into event_mvp_computed and refreshed automatically the moment an event's scores are imported (so the badge appears within the same import), with a one-time backfill for all past events. The GG 'MVP $' table is still kept for the money/purse record and as a cross-check.",
    ],
  },
  {
    version: "2.113.3",
    date: "2026-07-16",
    changes: [
      "Entry-confirmation email now always shows the Side games line, including 'None' (Kerry). Previously a NONE side-game row was omitted; showing 'Side games: None' makes the registration detail unambiguous for the player. Applies to auto + manual/retroactive sends.",
    ],
  },
  {
    version: "2.113.2",
    date: "2026-07-16",
    changes: [
      "Automated member-facing sends now CC admin@thegolffellowship.com for the record (Kerry). The entry-confirmation email (auto + manual/retroactive) copies admin@ on every send via a new _auto_email_cc() helper; disable or repoint with the AUTO_EMAIL_CC env var (set AUTO_EMAIL_CC=\"\" to suppress). send_entry_confirmation_email gained an optional cc param (defaults to the admin CC; pass \"\" to suppress on a one-off copy).",
      "Manual entry-confirmation resend can now be redirected and CC-controlled: the scoring-entry-confirm bridge accepts '<item_id>[|<override_to>[|<cc>]]' so a copy of exactly what a player received can be sent to another address (e.g. kerry@) without CC'ing admin. Used to send Kerry copies of the Dan South / Jeff Rideout s9.19 confirmations.",
    ],
  },
  {
    version: "2.113.1",
    date: "2026-07-16",
    changes: [
      "Entry-confirmation email can now be sent manually / retroactively (Kerry: send one to players whose credits were applied before the auto-email went live). Refactored the build+send into shared database.py helpers (build_entry_confirmation_email / send_entry_confirmation_email); the apply-credit auto-path now delegates to them. New manager endpoint POST /api/items/<id>/entry-confirmation/send and MCP tool send_entry_confirmation(item_id) both force-send for a given registered item (skip the balance guard) — the resend path for credit-covered registrations. 'Credit applied' falls back to the item's price when there's no live apply result.",
    ],
  },
  {
    version: "2.113.0",
    date: "2026-07-16",
    changes: [
      "Auto entry-confirmation email when a credit covers the whole fee (Kerry). When Apply Credit & Register leaves nothing owed (amount_owed <= 0 — the credit fully covers, or overcovers, the entry), the player now automatically gets a confirmation email: 'You're all set — you're entered into [event]' with the details (date, course, holes, tee, side games, credit applied), plus an excess note if their credit overcovered. Sends on both the RSVP and GG-RSVP apply-credit paths via _send_credit_entry_confirmation, through the same Microsoft Graph sender + message log as the balance-due email; when a balance IS still due it does NOT fire (that's the balance-due email's job). Kill switch AUTO_CREDIT_ENTRY_EMAIL=0; test routing CREDIT_ENTRY_EMAIL_OVERRIDE=<addr>. Never blocks the apply response on a mail failure.",
    ],
  },
  {
    version: "2.112.1",
    date: "2026-07-16",
    changes: [
      "Excess Venmo-back memo now always names the ORIGINAL event the credit came from (Kerry). A normal rain-out/WD credit already carried its source event, but a chained credit (an 'Excess credit — [applied event]' row from a prior application) named the event it was applied to, not the origin. get_player_credits now attaches origin_event to every credit via a new _credit_origin_event() that traces the transfer chain (excess email_uid credit-excess-<rid> -> that registration's transferred_from_id -> the source credit -> recurse) back to the true origin; all credit-info responses expose it and the Apply Credit modal's Venmo memo uses origin_event. So applying a Cedar-Creek-origin credit that had already been bounced through another event still reads 'Excess credit from s9.18 Cedar Creek'.",
    ],
  },
  {
    version: "2.112.0",
    date: "2026-07-16",
    changes: [
      "Apply Credit & Register now Venmos the excess in one tap (Kerry): pick 'Venmo back', tap Apply Credit & Register, and Venmo opens automatically with the right person, amount, and memo -- no separate 'open Venmo link' click -- and the refund self-records when you come back. How it works: the apply request is dispatched first (the server arms a refund watch on the new excess-credit item via _arm_excess_venmo_watch, so the receipt matches even though it arrives after), then Venmo opens synchronously inside the click gesture (iOS blocks app-scheme links fired after an await, so ordering matters). The provider receipt then auto-records the refund through the same watch/verify path as the red Refund buttons (amount + customer/handle, ~75s/180s quick sweeps + the 2-min cycle), flipping the excess item credited -> refunded with no manual step. apply_credit_to_rsvp now returns excess_credit_id; the memo follows the ratified 'Excess credit from [origin event]' grammar. Works on both the RSVP and GG-RSVP apply-credit paths.",
    ],
  },
  {
    version: "2.111.2",
    date: "2026-07-16",
    changes: [
      "Mobile roster now shows the CREDIT badge and drops the noise NONE badge (Kerry). RSVP players with an outstanding credit now get the same green 'Credit: $X' chip mobile as desktop -- tappable to apply the credit (document-delegated handler, same as desktop). The 'NONE' side-games pill (shown for players with no side games, meaningless on an RSVP-only row) no longer renders on mobile cards; NET/GROSS/BOTH still show.",
    ],
  },
  {
    version: "2.111.1",
    date: "2026-07-16",
    changes: [
      "Add Player name autofill now works on mobile (Kerry: typing a name when RSVPing someone showed no roster suggestions on the phone). The field used a native <input list=datalist>, and iOS Safari renders no dropdown for <datalist> -- so desktop suggested existing players but mobile showed nothing (only the OS keyboard's own guess). Replaced it with a custom typeahead dropdown (prefix-then-contains match over the known customer names, tap to fill) that works on both desktop and mobile; selecting a known player still auto-fills status and hides the new-contact email/phone fields as before. mousedown-based selection so the tap registers before the input blur on iOS.",
    ],
  },
  {
    version: "2.111.0",
    date: "2026-07-16",
    changes: [
      "Mobile now has the SAME per-player actions as desktop (Kerry: needed to revert Daniel South from his phone). The mobile roster card was a thinner, separate implementation -- for an active player it only offered Credit/WD/Delete and had NO credit-transfer branch, so a credit-transfer registration like Daniel South's showed Credit/WD instead of the Undo (revert-credit-application) desktop shows. Both views now render from ONE shared builder (playerActionItems), so mobile and desktop can't drift apart again: Apply Credit, Send Venmo Email/Remind, Undo, Credit, WD, Assign Guest, Assign Member, Reverse, and Delete all appear per the player's exact state, in either view. Handlers are document-delegated, so the mobile buttons drive the same endpoints with the same admin/manager gating.",
    ],
  },
  {
    version: "2.110.1",
    date: "2026-07-16",
    changes: [
      "Task #16 playing-handicap projection validated against actual GG and documented for CA (docs/claude/handicap-projection.md). Parity sweep across 46 real rounds (a9.18 Forest Creek 19, s9.17 Silverhorn 27): the tee-based stroke ALLOCATION reproduced GG's per-hole dots 46/46 = 100% from our data alone (our tee slope + stroke index, no GG input). Playing-handicap VALUE was exact wherever our index matched GG's; every residual traced to a known/separate cause -- 3 a9.18 rounds were new Austin players with no handicap history in our system yet (our_index null), and all 4 s9.17 residuals were GG = our value + 1, the documented WHS net-double-bogey policy gap (GG uses raw gross, we cap -- Kerry ratified WHS 7/14, so our number is the intended one). Conclusion: the 100% tee-based playing-handicap calc is ratification-ready; per-game allowance/caps/par-3 rules layer on top next.",
    ],
  },
  {
    version: "2.110.0",
    date: "2026-07-16",
    changes: [
      "Task #16 (Kerry) -- playing-handicap projection engine, the keystone that untethers NET scoring. New pure module email_parser/handicap_calc.py computes, with NO Golf Genius input: course handicap (index x slope/113 + (rating - par)), playing handicap (whs_round of course handicap x allowance, optional max-handicap cap -- 100%/no-cap is the base milestone), and per-hole stroke allocation by stroke index (hardest first, wraps for a 2nd pop, TGF max 2 pops/hole, plus-handicaps give strokes back on the easiest holes). Read-only parity sweep project_playing_handicaps() + bridge hcp-project:<event> compares our projection to GG's own playing handicap and stored per-hole dots -- separating the tee/allocation math (the 100% target, index-independent) from index differences. Confirmed vector: John Wade's a9.18 (PH 5, White tee) allocates onto stroke-index 1,3,5,7,9 exactly as GG did. Nothing member-facing yet; this is the shadow/validation stage before Kerry + CA ratify the calc. Tests: test_handicap_calc.py (21 checks).",
    ],
  },
  {
    version: "2.109.0",
    date: "2026-07-16",
    changes: [
      "Scorecard imports now self-heal a partial card (Kerry: a9.18 points weren't updating). a9.18 Forest Creek was imported ~11pm on game night while GG score entry was still in progress, so our copy froze with only 4-7 of 9 holes per player. A plain re-import couldn't fix it: GG re-keys the tournament's aggregate ids once the round finalizes, so the COMPLETE card arrives under a NEW aggregate id and the cross-tournament dedupe skipped it as 'other tournament' (all 19 players skipped). The importer's upgrade rule now also fires on COMPLETENESS -- an incoming card with more holes scored than the stored one replaces it in place (previously it only upgraded a raw-gross card to a net card). So re-importing any event that was first grabbed mid-round now pulls the finished scores. This unblocks a9.18's points/handicap inputs. Tests: test_scorecard_refresh.py (8 checks).",
    ],
  },
  {
    version: "2.108.1",
    date: "2026-07-16",
    changes: [
      "REFUNDS console age fix (Kerry: 'Age on those is incorrect'). The OUTSTANDING bucket was keying each credit's age off the player's REGISTRATION date (items.order_date), so credits from the SAME rain-out showed different ages -- every s9.18 Cedar Creek credit read 7d/3d/2d by who registered when, instead of a single age since the event. Age now anchors to the EVENT date for registration-based credits (rain-out/withdrawal rows flipped to credited/wd): all s9.18 Cedar Creek credits (event 2026-07-14) read the same age. Synthetic credit rows (excess/overpayment, email_uid credit-excess-*) are created AT credit time, so those correctly keep their own creation date (an 'Excess credit' made today still shows 0d). Future-event or date-less credits fall back to order_date, and ages clamp at 0. test_refunds_overview.py extended to 16 checks (same-event credits share age; synthetic rows keep creation date).",
    ],
  },
  {
    version: "2.108.0",
    date: "2026-07-15",
    changes: [
      "REFUNDS console (Kerry: 'I don't want to go to 25 places to do all this work ... consolidation so nothing falls thru the cracks'). New admin REFUNDS tab on the TGF Payouts page consolidates every credit refund in one view, mirroring the PAYOUTS layout, with three buckets: OUTSTANDING (held credit balances -- WD credits + standalone credited rows -- that could be paid back, sorted OLDEST FIRST so aging credits surface), IN FLIGHT (open refund watches -- a P2P pay link was tapped, awaiting the provider's receipt, shown 'watching...'), and COMPLETED (payouts recorded in the last 120 days, VERIFIED if a receipt confirmed it, else PAID). Each bucket shows its count + dollar total; outstanding rows carry an age chip (amber >=14d, red >=30d). Backed by GET /api/refunds/overview (admin) and get_refunds_overview() with test_refunds_overview.py (12 checks).",
      "v1 of the console consolidates + routes: each OUTSTANDING row's 'Refund...' button deep-links to that player's profile, where the existing red Refund modal (Venmo/PayPal/Cash App/Zelle pay links + receipt verification) already lives -- rather than duplicating money-action modals. Inline refund actions in the console are the next increment. A per-item 'Held' marker (to distinguish credits you're intentionally holding from those awaiting refund) is a separate schema addition pending Kerry's ruling; today the bucket is age-sorted.",
    ],
  },
  {
    version: "2.107.0",
    date: "2026-07-15",
    changes: [
      "Balance-due payments now auto-recognize even when a spouse pays from THEIR OWN Venmo (Kerry: 'What happens if Richard's wife sends the Venmo from her Venmo?'). Before: the inbound matcher resolved the payer by handle -> name -> alias; an unrecognized payer (a spouse) landed in the manual-match queue. Now, when none of those resolve, a memo fallback kicks in: because the balance-due link we email the player prefills the memo with the PLAYER's name ('Richard Palacios - Balance due for s18.8 Vaaler Creek'), the matcher reads the receipt memo and ties the payment to the UNIQUE open balance whose amount matches AND whose player's full name appears in the memo. Guards keep it safe: full names only (a bare 'Richard' won't match), exact amount (±$1), and if two open balances would both match it stays manual. The verified +PAY child is tagged '[memo-match]' for the audit trail. The refund (outbound) side already used memo as a verifier; this brings the inbound side to parity. Tests: test_inbound_memo_match.py (11 checks).",
    ],
  },
  {
    version: "2.106.2",
    date: "2026-07-15",
    changes: [
      "Balance-due emails no longer produce '+'-riddled Venmo memos (Kerry, from Richard Palacios's payment: 'all those pluses in the memo...I don't like em'). Root cause: the email linked https venmo.com, which renders the note's encoded spaces as literal '+' characters no matter how they're encoded -- the same quirk the in-app pay buttons dodged on 2026-07-08 by using the native venmo:// scheme, which emails can't use directly (Gmail strips app-scheme links). Fix: a new no-auth /pay/venmo bounce page -- the email links there over https, the page auto-fires venmo://paycharge (where %20 decodes to real spaces) and shows the memo with a venmo.com fallback for desktop. Memo wording also aligned to the ratified grammar: '[First] [Last] - Balance due for [Event]' (inbound money is FOR the event; outbound credits read FROM their origin event). Balance-due auto-matching is unaffected -- it matches on customer + amount, never memo text.",
    ],
  },
  {
    version: "2.106.1",
    date: "2026-07-15",
    changes: [
      "Refund memo wording per Kerry's live review of Rob Callaway's excess refund ('Credit for Excess credit -- s9.19' read wrong): memos now say money comes FROM its origin event. Full refunds: '[First] [Last] - Credit from [Event]'. Excess-credit rows -- which are named for the event the credit was APPLIED to -- trace back through the transfer chain (excess item -> the registration it funded -> transferred_from_id -> the original event) and read '[First] [Last] - Excess credit from s9.18 Cedar Creek'; if the chain can't be traced the applied-to event is used without the double-prefix. Overpayment rows read 'Overpayment credit from [Event]'. The apply-credit modals' excess Venmo-back links on both the Customers and Events pages carry the same source-event memo (previously a generic 'Excess credit refund').",
    ],
  },
  {
    version: "2.106.0",
    date: "2026-07-15",
    changes: [
      "Refund buttons now PAY, not just record (Kerry): the Refund Credit modal builds a one-tap payment link for Venmo (venmo:// on phones), PayPal (PayPal.Me), and Cash App ($cashtag) -- prefilled with the player's handle from their customer record, the exact credit amount, and the ratified memo \"[First Name] [Last Name] - Credit for [Event Name]\" (with a Copy button for providers whose links can't carry a memo). Zelle has no deep link: an \"I'm sending via Zelle\" button arms the same verification. Manual Record Refund remains for Check/GoDaddy or any fallback.",
      "Verification is automatic: tapping a pay link registers a refund watch (refund_watches table, one open watch per item -- re-taps replace, not stack) and schedules the same ~75s/~180s quick inbox sweeps the Payouts tab uses. When the provider's receipt email lands, auto_match_refund_watches verifies it (amount exact to the cent AND same customer / same handle / memo present in the receipt note; receipts predating the watch or already backing a winnings payout are excluded; one receipt verifies exactly one watch) and records the payout through the SAME payout_credit path as a manual Record Refund -- identical books, receipt-dated. The modal shows Sent -> watching -> verified & recorded live; the 5-minute inbox cycle is the backstop.",
      "Recordation implications handled: winnings matcher keeps first claim on every receipt (refund matcher runs after it and skips payout-backed receipts); an amount edited inside the payment app simply never matches (stays pending, manual record always available); double-tap can't double-record (payout_credit refuses already-actioned rows, watch verifies once); /api/customers now carries payment_method/payment_handle so non-Venmo handles prefill. Tests: test_refund_watch.py (13 checks).",
    ],
  },
  {
    version: "2.105.0",
    date: "2026-07-15",
    changes: [
      "RSVP match hygiene is now fully automatic (Kerry: 'I don't want to worry that things aren't matching'). The Audit RSVPs pass -- clear email-mismatched first-name matches + rematch -- now runs itself in three places: (1) after EVERY RSVP inbox ingest (rematch_rsvps only filled unmatched rows; it never cleared a bad match, so the Daniel South class of mis-match survived every cycle until someone pressed the button), (2) when a manager/admin opens an event (inline before the RSVP read, throttled to once per event per 15 minutes, so what you see is already healed), and (3) a nightly 3:35 AM Central sweep across upcoming events (AUTO_RSVP_AUDIT=0 to disable). The manual button remains for on-demand use.",
    ],
  },
  {
    version: "2.104.2",
    date: "2026-07-14",
    changes: [
      "RSVP credit badge fix (Kerry's live catch: Daniel South's $74 rain-out credit missing from his Vaaler Creek RSVP row): the first-name RSVP matcher had pinned his RSVP to Daniel LEHAN's active purchase. The roster UI's email-mismatch guard correctly re-displayed him as his own row, but the backend credit map used a stricter query WITHOUT that guard, so mis-matched players were never considered for a badge. get_event_rsvp_credit_map now mirrors the frontend rule exactly (a matched-but-different-email RSVP counts as unmatched) and resolves identity by the RSVP's own customer_id first.",
      "Worse bug fixed in the same trace: get_rsvp_credit_info (the Apply Credit modal + credit-alert email path) resolved the player THROUGH the matched item -- for a mis-matched RSVP that surfaces, and would have applied, the WRONG PERSON'S credits. It now resolves by the RSVP's own customer_id (rule 6), trusts the matched item only when its email agrees, and passes customer_id + email into the credit lookup. The item-based credit-info endpoint also passes customer_id. Regression proof: test_rsvp_credit_map.py (9 checks, cross-Daniel scenario reproduced exactly).",
    ],
  },
  {
    version: "2.104.1",
    date: "2026-07-14",
    changes: [
      "Docs: state-of-the-tracker.md refreshed for the CA handoff (Kerry: scoring go-live planning moves to the claude.ai project) -- July 8-14 build-wave summary (own handicaps ratified, pairing engine complete w/ Match Play constraint + pace staging, season-contest economics, member tier, cancellation suite, GG archive) and the scoring go-live readiness assessment referenced as mailbox #187.",
    ],
  },
  {
    version: "2.104.0",
    date: "2026-07-14",
    changes: [
      "Cancel Event clears the RSVP roster (Kerry, after running the s9.18 rain-out live): unpaid rsvp_only/gg_rsvp entries are withdrawn during execute (default-on 'Clear RSVP roster' checkbox) so a cancelled event's roster reads empty -- the credit pass rightly skips them (they never paid), which previously left them populating the roster after everyone else was credited. They still receive the notification email (the recipient plan captures them before the clear). Unmatched Golf Genius 'PLAYING' RSVPs no longer render as synthetic roster rows (or count in the roster number) on cancelled/postponed events.",
      "Selectable status badge at cancel time: a Badge chip row (CANCELLED / RAINED OUT / COURSE CLOSED / WEATHER / POSTPONED / RESCHEDULED) picks the label shown on the event -- new events.status_badge column, rendered on the desktop list rows, the mobile event cards (which previously showed no cancelled badge at all), and the event detail banner. Auto-defaults to the chosen status until a chip is pinned; Restore Event clears it. status_badge is also editable via the event update path for backfills.",
    ],
  },
  {
    version: "2.103.0",
    date: "2026-07-14",
    changes: [
      "Per-player email preview in the Cancel Event flow (Kerry): a Preview Emails button under the message editor renders every recipient's exact email BEFORE execute -- name, address, an outcome chip with their settled amount (CREDIT $76.00 / REFUND $52.00 / SKIPPED / NO PAYMENT), the rendered subject, and the full personalized body. Tap again to hide; players with no email on file are flagged at the bottom of the list.",
      "WYSIWYG by construction: new POST /api/events/<id>/cancel-preview is a zero-write dry run that predicts each item's outcome from the selected mode (Credit All / Refund All / One-by-One choices) and renders through the SAME recipient builder and template renderer the execute send uses -- the shared helpers (_cancel_recipient_list, _cancel_predicted_outcomes, _cancel_event_vars) were factored out of cancel-execute so preview and send can never drift apart.",
    ],
  },
  {
    version: "2.102.2",
    date: "2026-07-14",
    changes: [
      "Docs: events.md cancellation section now states where Cancel Event lives on each form factor (desktop registrations-header Actions menu; mobile expanded-card Actions menu as of v2.102.1) so the gap Kerry hit is discoverable in the docs of record.",
    ],
  },
  {
    version: "2.102.1",
    date: "2026-07-14",
    changes: [
      "Cancel Event reaches mobile: the expanded event card's ⚙ Actions menu now carries the admin Cancel Event item (Restore Event when already cancelled/postponed), mirroring the desktop menu -- it was desktop-only, which left the new one-tap cancellation flow unreachable from a phone on the night it was needed. Handler wiring was already shared (attachDetailHandlers runs for mobile detail elements), so this is menu markup only.",
    ],
  },
  {
    version: "2.102.0",
    date: "2026-07-14",
    changes: [
      "One-tap event cancellation (Kerry-ratified after the s9.18 Cedar Creek rain-out): the Cancel Event modal is now a single screen of questions -- status + reason, Credit All / Refund All / One-by-One, and an editable notification email -- with one EXECUTE that does everything server-side: sets the event status, settles every paid player, silently removes comps, and emails EVERYONE (paid, skipped, RSVP-only, and unmatched GG 'PLAYING' RSVPs) in one call.",
      "Each email carries the player's EXACT settled amount: new {credit_amount} and {credit_line} template variables are personalized per recipient ('Your $76.00 entry has been converted to a full credit...'), with distinct wording for refunds (includes the auto-detected method), skipped players, and RSVP-only players who owed nothing. Amounts are computed from active entry items plus their add-on children, summed per player across multiple orders (plan_event_cancellation_notice; sends recorded in the Message History log).",
      "Root-cause fix for 'the cancellation email reached nobody': the send path used to skip credited players unconditionally, but after Credit All the credited players ARE the audience. The new endpoint plans recipients+amounts BEFORE crediting (structurally immune), and both the Message Players composer and /api/messages/send now include credited/refunded registrants when the event is cancelled or postponed (transferred players stay excluded; active events unchanged).",
      "New endpoint POST /api/events/<id>/cancel-execute (admin); the old cancel/cancel-bulk/cancel-apply endpoints remain for compatibility. send_bulk_emails supports per-recipient template variables. Tests: test_cancel_notice.py (10 checks: per-player totals w/ add-on cascade, multi-order summing, canonical email resolution, RSVP coverage, plan-before-credit).",
    ],
  },
  {
    version: "2.101.0",
    date: "2026-07-14",
    changes: [
      "Pace rating one-tap editor (task #23): the Customers page gets a PACE column (list view) and an inline control on the mobile cards -- a 1|2|3 segmented tap for managers (Kerry + Robert). Unrated players show a gray 'implied' 2 (NULL reads as 2 by rule); a tap always stores an explicit value with source='manager' so manager edits beat the boot seed forever (clearing to NULL would let the fill-only-if-NULL seed resurrect old values on redeploy, so there is deliberately no clear). New endpoint POST /api/customers/<id>/pace; /api/customers now returns pace_rating + pace_rating_source.",
      "Pace STAGING engine (task #23): Generate Pairings now orders the settled groups by aggregate group pace (average member rating, unrated = 2). Sequential tee-time events stage fast groups FIRST; shotgun hole-trains stage fast groups at the FRONT of the train (higher hole numbers = later sheet slots), with group size breaking pace ties -- which also preserves the old threesomes-to-the-front shotgun behavior when everyone is a 2. HARD RULE upheld: pace never dictates composition, only where a finished group is staged; manager-seeded groups stay where they were placed.",
      "The staging rule ships as editable data (principle 2): PAIRING_STAGING_DEFAULTS overridable via the 'pairing_staging_rules' app_settings JSON (enabled / shotgun / tee_times / aggregate / default_rating); enabled=false restores the legacy shotgun ordering. Pace lookup joins customers via items.customer_id (rule 6, suffix-proof for the Victor Arias case). Each generated group carries group_pace, shown as a stopwatch chip on the PAIRINGS group headers. Tests: test_pace_staging.py (19 checks, both start types, composition invariance, config override).",
    ],
  },
  {
    version: "2.100.0",
    date: "2026-07-14",
    changes: [
      "Match Play dictates pairings (task #25, Kerry-ratified rule 8 amendment: 'Match Play is king'). Generate Pairings now detects potential matches from the Match Play season state -- during pool play, every pool-mate pair on the event roster without a PLAYED match; once a knockout bracket exists, the current round's undecided matchups between rostered players -- and shows the manager a per-match CONFIRM panel before generating. A decline means the match isn't required this event: that constraint drops and normal rules run.",
      "Confirmed matches are the generator's FIRST constraint, above partner requests: opponents land in the same foursome in OPPOSITE carts (seats 1/2 vs 3/4) -- a new lock type distinct from partner locking, which keeps request pairs together. Partner requests are still honored where they fit around a match (the requester or partner joins the match foursome when there's room), never at the match's expense; anything the generator couldn't apply is reported in visible notes, never dropped silently.",
      "PAIRINGS tab visually denotes Match Play participants: an orange 'MP' badge on any player whose pending opponent is seated in the same group (works on saved pairings too via GET /pairings mp_matches), plus a Match Play chip in the controls bar to reopen the confirm panel. New endpoints: GET /api/events/<id>/pairings/matchplay (detection) and mp_pairs on the generate POST; debug bridge scoring-pairings:mp|<event_id>.",
      "Seat-order fix that fell out of the new constraint seater: partner-request pairs now share a CART (seats 1/2 or 3/4), not merely adjacent seat numbers -- plain adjacency could straddle seats 2/3, which is two different carts. Groups without a constraint pair keep the existing tee-adjacency ordering. Functional proof in test_mp_pairings.py (22 checks: detection both phases, opposite-cart placement, request-around-match, decline behavior).",
    ],
  },
  {
    version: "2.99.5",
    date: "2026-07-14",
    changes: [
      "Pace seed fix: the two Victor Ariases store first+last as plain 'Victor Arias' (the III/Jr suffix lives outside first_name/last_name), so the suffixed seed entries missed both. One unsuffixed entry now matches both rows -- intended, since they always ride and stage together, both carry the 1. Live verification via scoring-pairings:pace| showed 21/23 before, 23/23 expected after.",
    ],
  },
  {
    version: "2.99.4",
    date: "2026-07-14",
    changes: [
      "Pairing Standards rule 8 amended (Kerry): Match Play dictates pairings as the FIRST rule -- 'Match Play is king.' When the Match Play season state (pool play or current knockout round) implies a potential match between two rostered players, the generator must put the opponents in the same foursome (ideally separate carts) and visually denote them as Match Play participants, with a per-match manager CONFIRM question before generation (a 'no' drops the constraint and normal rules run). Documentation-of-record update; engine build is task #25.",
    ],
  },
  {
    version: "2.99.3",
    date: "2026-07-14",
    changes: [
      "Match Play 4-player knockouts seed CROSS-POOL (Kerry): each pool winner plays the OTHER pool's runner-up in the semis -- Stableford no longer seeds that bracket (it only breaks record ties within pool finishes, which pool rank already applies). Seed Knockout button, member How-It-Works copy, engine (cross_pool_semi_order + seeding_knockout4 config key, default cross_pool so existing snapshots inherit the rule), and tests all updated. Larger brackets (8/12/16) keep ratified Stableford seeding; a malformed field (not two pools x two advancers) falls back to Stableford with a warning.",
    ],
  },
  {
    version: "2.99.2",
    date: "2026-07-14",
    changes: [
      "Pace-of-play ratings seeded (Kerry-ratified, 1=slowest to 3=fastest): customers.pace_rating + pace_rating_source columns, boot-time fill-only-if-NULL seed of 23 rated players (15 threes incl. the three Austin exceptions Hogue/Cloer/Straiton, 8 ones incl. both Victor Ariases who always ride together). Everyone unrated reads as 2 system-wide until further notice; manager edits always win over the seed. Read back via scoring-pairings:pace| bridge. Pace never affects pairing composition -- staging only (engine comes next).",
    ],
  },
  {
    version: "2.99.1",
    date: "2026-07-14",
    changes: [
      "scoring-pairings:playerstaging| -- per-player staging positions across all 9-hole events, bucketed by start type (SA shotgun trains where later sheet position = front of train, Austin shotguns, Austin sequential tee times) with pre-4PM early-play waves counted separately as preference. Feeds Kerry's initial 1-3 pace ratings derived from where each player has historically been staged.",
    ],
  },
  {
    version: "2.99.0",
    date: "2026-07-14",
    changes: [
      "Generate Pairings seats same-tee players together within each settled group (Kerry's tee-grouping pace rule: adjacent seats share a cart AND a tee box, so groups don't leapfrog between tees; partner-request pairs stay adjacent and sort by their first member's tee).",
      "Nightly auto pairings grab (03:20 US/Central, AUTO_PAIRINGS_GRAB=0 to disable): walks both portals' FINAL tee sheets into pairing history + past-event PAIRINGS tabs. Idempotent replace-per-event; rounds without a published sheet are skipped so team-board fallback data stands. Tonight's events land in history automatically by morning.",
      "scoring-pairings:staging| -- read-only side-quest probe: every 9-hole event's actual groups in staging order with pace proxies (size, avg current handicap index, age-band mix) for detecting the manager's staging patterns.",
    ],
  },
  {
    version: "2.98.0",
    date: "2026-07-14",
    changes: [
      "Past events' PAIRINGS tab shows the ACTUAL played groups (Kerry): every pairings ingest path (final tee sheets, team boards, manual starter sheets) now also mirrors its groups into event_pairings -- tee-time slot labels where the source has them, seat-order cart positions (blind fills keep the cart alignment but are not written). Re-running the season walks backfills the whole 2026 schedule.",
    ],
  },
  {
    version: "2.97.0",
    date: "2026-07-14",
    changes: [
      "Generate Pairings optimizes for NEW PAIRINGS first (Kerry's rule 3, ratified in-session): a once-played pair and a thrice-played pair are equally 'not new', so the optimizer now minimizes the NUMBER of repeat-pairs as the primary term and uses play counts only as the tiebreaker (prefer re-pairing the 1s over the 3s when repeats are forced). Previously it minimized the summed play counts, which could trade an extra repeat-pair for a lower total.",
    ],
  },
  {
    version: "2.96.2",
    date: "2026-07-14",
    changes: [
      "Shotgun tee sheets parse again: the 18-hole layout guard treated shotgun hole labels ('1A'/'1B') as non-hole cells and under-parsed several 9-hole rounds (s9.12 to zero). Hole cells now match 1-2 digits plus optional A/B; tee labels still end the window so the By-Individual table stays excluded.",
    ],
  },
  {
    version: "2.96.1",
    date: "2026-07-14",
    changes: [
      "18-hole tee-sheet layouts guarded: their alphabetical By-Individual table places the 'Other Players' cell (names joined by +) inside the time-cell window, so the first SA walk ingested per-player rows as phantom groups with '+'-suffixed names on the five 18-hole rounds. The names cell must now be +-free and only pure-digit hole cells may sit between the time and the players; contaminated events re-applied clean.",
    ],
  },
  {
    version: "2.96.0",
    date: "2026-07-14",
    changes: [
      "FINAL tee sheets are now the pairings ingest source (Kerry's route: every portal's SCHEDULE calendar lists a public per-round Tee Sheet page, and its next_round widget serves the historical sheet when given round_id= -- the param the first attempt missed). scoring-pairings:round|/all| now walk these: groups parsed in true seat order from the By-Tee-Times layout (two-column rows deduped, the alphabetical By-Individual table skipped structurally), so rode-with pairs come from the actual tee-sheet sequence instead of the team-board order assumption. round| accepts an event override for GG's truncated preseason labels.",
    ],
  },
  {
    version: "2.95.8",
    date: "2026-07-14",
    changes: [
      "gen| probe also returns the event roster's full nonzero pair submatrix, so 'is this arrangement optimal' is checkable offline against the real season history.",
    ],
  },
  {
    version: "2.95.7",
    date: "2026-07-14",
    changes: [
      "Generate Pairings escapes the last-group attractor (Kerry's s9.18 case, root-caused via the gen| probe: history was loaded and scored, but the greedy fills groups in order, so the most-played players get avoided until the end and pool together in the final group -- random restarts alone never escape it). Every restart candidate now runs a pairwise-swap hill-climb between groups (partner-request pairs are never split); on the live Cedar Creek roster this reaches the theoretical floor -- zero avoidable repeats, with the only remaining counts inside explicitly requested pairs.",
    ],
  },
  {
    version: "2.95.6",
    date: "2026-07-14",
    changes: [
      "scoring-pairings:gen|<event_id> -- read-only generator probe: runs Generate Pairings server-side with no seeds and reports each group's repeat-pairs and score, isolating 'generator ignores history' from 'UI passed locked seeds' (Kerry's s9.18 re-run still produced last week's trio).",
    ],
  },
  {
    version: "2.95.5",
    date: "2026-07-14",
    changes: [
      "Twin Crystal Falls events merged (Kerry-ratified: 'a18.2 CRYSTAL FALLS' and 'a18.3 CRYSTAL FALLS' were the SAME May 30 event, renamed mid-registration; GG's coding wins -- a18.2 is AUSTIN KICKOFF | ShadowGlen). Boot repair moves every event_id reference from the stale twin (3267) to the keeper (3263), registers the old product name as an event alias so name-joined items/RSVPs keep resolving, deletes the twin, and drops its stale pairing rows (the keeper already carries the tee-sheet truth). Fixes the double-counted registrations (11 + 12 for one 12-player event).",
      "a9.17 Falconhead and a18.3 Crystal Falls foursomes written from Kerry's tee-sheet screenshots (21 + 18 pairs, source 'tee_sheet') -- every played 2026 event now has full playing-group history feeding Generate Pairings.",
    ],
  },
  {
    version: "2.95.4",
    date: "2026-07-14",
    changes: [
      "Manual pairing groups accept a '!Name' literal escape that skips customer resolution: the fuzzy identity cascade mis-attached a Hill Country Matches GUEST ('Cleary, Paul', not a customer) to a member -- literal seats store the normalized name with NO customer id, so guests can never inherit a member's history.",
    ],
  },
  {
    version: "2.95.3",
    date: "2026-07-14",
    changes: [
      "Generate Pairings actually avoids this season's repeats (Kerry, live s9.18 report: paired with last week's foursome while unplayed roster players sat elsewhere). Two fixes: pair-history lookups are now case/whitespace-insensitive (an exact-string key silently dropped history on any name drift between writers), and the random generator runs best-of-30 restarts keeping the fewest-repeats arrangement (a single greedy pass could trap early picks into repeats even when a zero-repeat arrangement exists).",
      "Manual tee-sheet groups write path (scoring-pairings:manual|<event_id>|<json>[|apply], source 'tee_sheet'): per Kerry, CART Net weeks still played in real 3/4-somes -- the foursomes for those rounds come from the OneDrive Seasons starter sheets, which are the ruled primary source. scoring-pairings:hist|<event id or name> is a read-only debug view of pairing_history rows + 2026 totals by source.",
    ],
  },
  {
    version: "2.95.2",
    date: "2026-07-14",
    changes: [
      "Two Austin-walk fixes: (1) affiliation tails may START with Guest/Former (a lone guest blind's tail has no TGF token at all -- 'Bl[FRANZ, Kyle] Guest' leaked as a fake player on a9.14); (2) duplicate-code events disambiguate by label/name word overlap instead of latest-date-wins -- the Tracker has BOTH 'a18.2 AUSTIN KICKOFF | ShadowGlen' (Mar 14) and 'a18.2 CRYSTAL FALLS' (May 30, looks like a mislabeled twin of a18.3 -- flagged for Kerry), and the kickoff round's pairs landed on the wrong one. scoring-pairings:clear|<event_id> deletes ONLY source='gg_teamnet' rows to undo a mis-matched apply.",
    ],
  },
  {
    version: "2.95.1",
    date: "2026-07-14",
    changes: [
      "Team-board parser handles the real affiliation tails the SA dry-run surfaced: the text after the last member is a comma-separated affiliation PER PLAYER ('TGF San Antonio, Former, TGF Houston, TGF Austin', '..., Guest'), not a single chapter tag -- the old single-tag strip let blind markers leak through as fake player names on mixed-chapter 18-hole rounds. Also added an event override arg (scoring-pairings:team|<portal>|<round>|apply|<event id or name fragment>) for the two preseason rounds whose selector labels GG truncates mid-date.",
    ],
  },
  {
    version: "2.95.0",
    date: "2026-07-14",
    changes: [
      "2026 pairings grab route B (the working one): the public TEE SHEETS page proved to be a next_round widget (tonight's event only) and the tee-sheet archive is login-gated, so the ingest now reads each played round's TEAM Net $ (SA foursomes) / CART Net $ (Austin cart pairs) tournament board off the tournament_results widget -- those rows ARE the actual playing groups in seat order. Blind-draw fills (Bl[Name]) stay as empty seats: excluded from played-with pairs but preserving the 1&2 / 3&4 cart split for the rode flag. New bridge commands scoring-pairings:teamrounds|/team|/teamall|; rows land in pairing_history with source 'gg_teamnet', same replace-per-event semantics as the tee-sheet route.",
    ],
  },
  {
    version: "2.94.0",
    date: "2026-07-14",
    changes: [
      "GG tee-sheet pairings ingest (Kerry overnight directive): scoring-pairings bridge commands walk each portal's TEE SHEETS widget round by round, parse the groups, resolve players through the scoring identity cascade, and write pairing_history per event -- played-with pairs for the whole group plus the rode-with flag per Kerry's cart ruling (tee-sheet sequence 1&2 / 3&4 ride together). Tee sheets are the ruled PRIMARY pairings source; apply REPLACES that event's history rows so re-runs are safe.",
      "pairing_history carries the RATIFIED customer_id amendment additively: customer_a_id/customer_b_id, rode, and source ('app' vs 'gg_teesheet') columns; app-side Save Pairings now writes all four too. Generate Pairings' season-scoped repeat-minimizing counts read this same table, so the ingested 2026 history immediately drives 'maximize new pairings' -- repeats only come back after a cycle, exactly the objective in the pairing standards.",
    ],
  },
  {
    version: "2.93.2",
    date: "2026-07-14",
    changes: [
      "PAIRINGS works on mobile (Kerry): the phone event card's PAIRINGS tab rendered a 'Feature Coming Soon!' stub even though the whole desktop pairings feature (generate/ABCD/locks/swaps/save) was already container-scoped and mobile-aware underneath -- the stub was the only blocker. Phones now get the full panel; the group grid collapses to one column on narrow screens.",
    ],
  },
  {
    version: "2.93.1",
    date: "2026-07-14",
    changes: [
      "9-hole rounds only carry a nine label when it says something (Kerry): '- Back' when the back nine was played; front-nine rounds and true 9-hole courses (Comanche Trace CREEKS/HILLS/VALLEY -- the names ARE the nines) show no suffix. 18-hole splits keep Front/Back since the pair needs distinguishing.",
      "Handicap records honor the admin-curated course short name on every screen size (was phones only), and 'The Golf Club Star Ranch' is seeded as 'Star Ranch' (fill-only-if-empty -- a /courses edit always wins).",
    ],
  },
  {
    version: "2.93.0",
    date: "2026-07-14",
    changes: [
      "Partial Refunds (incl. the 18 -> 9 Event Downgrade) gained a CREDIT method (Kerry): choosing 'Credit (hold for a future event)' creates a CREDITED child row for the amount instead of recording an outbound refund -- it surfaces in the player's open credits (Apply Credit, balance-due emails) via the same machinery as full credits, the parent registration still updates (games/holes), and NO accounting expense is written (internal ledger move; the money leaves only when the credit is later applied or refunded).",
      "Kerry also flagged the Credit modal's option sprawl (Credit/Refund/Partial/Transfer + WD + Apply Credit elsewhere) for consolidation -- logged for a design pass; destinations and money semantics stay as-is until that lands.",
    ],
  },
  {
    version: "2.92.1",
    date: "2026-07-14",
    changes: [
      "The 'FRONT/BACK NINE of an 18-hole round' note no longer appears on 9-hole event rounds (Kerry screenshot: Canyon Springs 6/2) -- 9-hole records got Front/Back labels in v2.91.0 and the expansion note wrongly keyed off the label instead of the backing card's hole count. The note (and single-nine slicing) now require an actual 18-hole card, and the note text renders smaller on phones.",
    ],
  },
  {
    version: "2.92.0",
    date: "2026-07-14",
    changes: [
      "Event Downgrade 18 -> 9 (Kerry, for s9.18 Cedar Creek): the Credit modal's PARTIAL REFUND tab now offers an 'Event Downgrade 18 -> 9 holes' component for players registered for 18 in a 9/18 Combo event -- the amount is the price difference between the formats (course cost + markup + included games, same per-event pricing chains as the WD calculator), and confirming it refunds that difference AND flips the registration's holes to 9. The inverse of Add Payment's Event Upgrade, which existed; the downgrade direction never did.",
    ],
  },
  {
    version: "2.91.0",
    date: "2026-07-14",
    changes: [
      "Full-table handicap bridge AUDIT (Kerry: 'audit all the records'): read-only bridge command scoring-hcp-audit classifies every handicap record -- bridged and reconciled to a scorecard nine, bridged but matching neither nine (review queue), unbridged with a card available that day (review queue), unbridged with no card (expected for pre-scorecard eras), or over-claimed cards. The repairs shipped today were always global (boot repairs sweep every player); this proves it with numbers.",
      "9-hole rounds now carry Front/Back too (Kerry): a 9-hole record's nine comes from the physical holes on its card (a back-nine event carries holes 10-18), so Falconhead-style back-nine events read 'Course - Back' and named nines resolve the same way as 18s ('Hyatt Hill Country | Oaks').",
    ],
  },
  {
    version: "2.90.4",
    date: "2026-07-14",
    changes: [
      "Flying L resolved (Kerry): both nines of that round scored an identical 41, and the nine-resolver demanded a UNIQUE match -- a 41/41 tie matched both nines, resolved neither, left the gross dashed, and (with no nine assigned) the expansion fell back to showing the full 18. Records sharing a card now resolve TOGETHER: each claims a nine in order, front first, so ties assign cleanly. Identical twin nines mean identical gross either way, so the displayed number is exact even in the tie case.",
    ],
  },
  {
    version: "2.90.3",
    date: "2026-07-14",
    changes: [
      "Nine naming (Kerry): the F9/B9 superscript is gone -- a record that is one nine of an 18-hole round now appends '- Front' / '- Back' to the course name, and when the course name carries NAMED nines ('Hyatt Hill Country | Lakes/Oaks') the record shows the nine's own name: 'Hyatt Hill Country | Oaks'.",
      "Dashes resolved, not covered (Kerry): the bridge repair gained a correction pass -- an unmatched record whose stored 'adjusted' equals a nine's RAW gross (while WHS capping says lower) is another uncapped Composer-era import (the workbook repair skipped 18-hole rounds), so it is corrected to the WHS adjusted value, its differential recomputed, and bridged. Suspect days now also include any day with an unbridged record and an existing scorecard, so the Flying L / Comanche HILLS dashes resolve on this deploy. Only records matching NEITHER the WHS nor the raw total stay unbridged, logged for review.",
      "Expanding a record that is one nine of an 18-hole round now shows ONLY that nine (Kerry: TGF handicaps are every-9-holes; the full 18 belongs on player scoring records) -- the other nine's grid and the 18-hole totals line are gone; the note above the card carries the nine's gross/adjusted.",
    ],
  },
  {
    version: "2.90.2",
    date: "2026-07-14",
    changes: [
      "Multi-round-day bridge repair (Kerry's Comanche Trace screenshot): the handicap-to-scorecard bridge matched by player+date alone, so on days with multiple rounds (Hill Country Matches: CREEKS/HILLS/VALLEY all on 5/16) the FIRST card imported claimed every record -- all three rows showed the same card's gross (37) beside their own correct ADJ values (37/39/43), producing 'adjusted' scores HIGHER than gross, which is impossible. A boot repair re-derives every suspect day: each record now bridges to the card+nine whose WHS-adjusted total equals its adjusted score; no reconciling card means unbridged (dash), never a guess. Runs on this deploy and fixes the live data.",
      "The importer's bridge is reconciling from now on: each nine of a new card claims at most one record whose adjusted score matches its WHS total; the old date-only claim survives only in the provably-safe single-card single-record case.",
      "Read-time guard: a record whose adjusted exceeds its bridged card's gross (a cap can only LOWER) shows a dash for gross instead of the wrong card's number -- mis-bridges can never render as phantom adjustments again.",
    ],
  },
  {
    version: "2.90.1",
    date: "2026-07-14",
    changes: [
      "18-hole rounds in the handicap records fixed (Kerry screenshots): an 18-hole round posts as TWO 9-hole handicap records, but the GROSS column was showing the full-18 total beside one nine's ADJ -- Kissing Tree read '80 | 41' and the tooltip claimed a '39-stroke WHS cap'. The server now resolves which nine each record represents (per-nine gross + WHS-adjusted totals matched against the record's adjusted score) and shows THAT nine's gross with an F9/B9 tag; the false orange cap flag and phantom tooltip are gone.",
      "Expanding an 18-hole-backed record now leads with which nine it covers: 'FRONT NINE (OUT) of an 18-hole round -- this handicap record covers only that nine (gross X, adjusted Y)' above the full card, so the record's numbers reconcile against the right half of the scorecard.",
    ],
  },
  {
    version: "2.90.0",
    date: "2026-07-14",
    changes: [
      "Handicap records now show BOTH scores (Kerry): a GROSS column (raw, from the bridged scorecard) sits next to ADJ (the WHS net-double-bogey adjusted score the handicap is computed from) in every expanded player's rounds table -- admin and member views. When a cap bit, the ADJ value renders TGF orange with a tooltip saying how many strokes the cap removed. Legacy rounds with no scorecard bridge show a dash for gross.",
      "Handicap records expand to the actual scorecard (Kerry): rounds bridged to an imported scorecard get an orange chevron on the date -- tap to unfold the full hole-by-hole card inline (same renderer as the member portal), tap again to close.",
      "Scorecard grids grew an ADJ SCORE row (both renderers: scorecard-render.js + points-render.js, kept in sync): appears ONLY when the WHS cap lowered at least one hole, with the capped holes in orange -- you can see exactly where and why the handicap score diverges from the gross.",
    ],
  },
  {
    version: "2.89.1",
    date: "2026-07-14",
    changes: [
      "First export-free handicap update is LIVE (Kerry: 'apply'): s9.17 Silverhorn (27 rounds) + a9.17 Falconhead (15) written to the handicap record straight from our scorecards -- WHS net-double-bogey adjusted gross, verified 42/42 byte-identical to GG's own Adjusted Gross Score sheets in Kerry's season-scores workbooks before writing.",
      "scoring-hcp-repair bridge command (Kerry: 'run it'): repairs 2026 handicap rounds whose adjusted_score was imported as RAW gross (the Spreadsheet Composer export has no adjusted column) using GG's true Adjusted Gross from the season workbooks. Guarded per row: 2026 only, capping-only direction, unique name+date match, and the stored value must equal the file's gross (proof of an uncapped import) -- anything else skips for review. Differential recomputed from the row's own stored slope/rating; the tee-rating question is deliberately untouched.",
    ],
  },
  {
    version: "2.89.0",
    date: "2026-07-14",
    changes: [
      "Self-derived handicap IMPORT (Kerry-ratified): scoring-hcp-import:<event>[|apply] writes handicap rounds straight from our own scorecards -- WHS net-double-bogey adjusted gross, slope/rating from the round's own tee row, differential computed, scoring_round_id bridged at birth. Dry-run by default; apply writes only rounds not already recorded. The GG handicap export/import ritual is now optional per event.",
      "Ruling basis verified on Kerry's actual GG Spreadsheet Composer downloads for a9.17 Falconhead + s9.17 Silverhorn: the export's only score column is the RAW gross (all 42 rows byte-identical to our stored gross; no adjusted column exists), so the historical record never had WHS capping. Kerry ruled: WHS standards for adjusted gross going forward.",
      "Writer reuses each customer's existing handicap player_name variant (freshest record wins, same rule as the export dedup) so self-derived rounds extend the record instead of forking it under a new spelling; brand-new players get their handicap_player_links row created on apply.",
    ],
  },
  {
    version: "2.88.0",
    date: "2026-07-14",
    changes: [
      "Self-derived handicap PREVIEW (Kerry): new read-only bridge command scoring-hcp-preview:<event> computes, from our own imported scorecards, the handicap round each player WOULD get -- adjusted gross, differential, and the index change it produces -- without writing anything. Built so the GG handicap export/import ritual can be retired with evidence instead of nerve.",
      "Differential parity triage: the ~9% mismatch against GG's export is now classified into families. Root cause of the dominant family CONFIRMED on real cards (McKinley a9.1, Barna a9.4): GG's export carries the RAW gross as 'adjusted' while our math applies the WHS net-double-bogey cap -- a policy difference, not a math bug. The preview therefore shows BOTH variants (capped vs raw) side by side; which becomes TGF's standard is a Kerry ruling before any self-derived import ships.",
      "get_differential_parity now reports mismatch_families (gg_adjusted_equals_gross / gg_below_ours / other) and tee_mismatch_detail with each tee row's hole range vs the nine actually played -- distinguishes legitimate front/back-nine rating pairs from genuinely stale tee rows (the Silverhorn 'duplicate Gold tee' question).",
    ],
  },
  {
    version: "2.87.6",
    date: "2026-07-13",
    changes: [
      "Where-{Name}-Stands row order (Kerry): the ACTIVE City Match Play row now sits above the dormant SA/Austin Fall NET placeholder -- live competitions outrank a race that hasn't started.",
    ],
  },
  {
    version: "2.87.5",
    date: "2026-07-13",
    changes: [
      "THE PLAYERS CUP payout strip: the Champion chip now reads 'Champion $x PLUS' (Kerry) -- the Champion bonus stacks on top of flight winnings (win your flight AND the Cup, the money stacks), and the badge now says so.",
    ],
  },
  {
    version: "2.87.4",
    date: "2026-07-13",
    changes: [
      "FIX: anchored tip cards hugged the page's left edge on desktop, pointing at nothing (Kerry screenshot; the #155 residual). Anchored tips now align to the element they point at -- left edge and width follow the anchor (capped at 360px) -- so the search tip sits under the centered search box on desktop and is unchanged on phones.",
    ],
  },
  {
    version: "2.87.3",
    date: "2026-07-13",
    changes: [
      "WHERE-{NAME}-STANDS polish (Kerry): rows get the app's light-orange hover (same shade as the search suggestions), and the Season Contest names in each row are larger and TGF orange -- the rows now clearly read as links to the Leaderboard.",
      "Chooser sheet button relabeled 'THIS WEEK'S EVENTS' -> 'EVENTS' (Kerry: no good way to manage next-week's events yet -- the shop section link shows whatever events are on sale, so the plain label is honest). Destination unchanged.",
    ],
  },
  {
    version: "2.87.2",
    date: "2026-07-13",
    changes: [
      "SPOTLIGHT CONVERSION REVISED (Kerry, supersedes the #156 per-row BUY IN): the BUY IN chips are REMOVED from the Where-{Name}-Stands rows -- a commerce chip on every row competed with the row's leaderboard deep-link and invited mis-taps. Instead: (1) the ENTER EVENTS & CONTESTS bar now sits at the top of the member Spotlight (same banner as the Leaderboard page, opens the two-button chooser); (2) the row chevrons are TGF orange so the rows read as tappable; (3) the section header gains an italic orange '(Click for Standings)' hint. Rows are pure navigation again, with one conversion CTA at the top of the page.",
    ],
  },
  {
    version: "2.87.1",
    date: "2026-07-13",
    changes: [
      "Welcome card repositioned (Kerry look-review): it was a fixed overlay pinned under the nav, covering the search box and hero -- exactly the elements its new copy points to. It now sits IN the page flow below all content (under the 'Live snapshots...' subtext), centered with its 360px cap on desktop. It's the only nudge allowed to reflow; the contextual tips keep their overlay/toast behavior.",
    ],
  },
  {
    version: "2.87.0",
    date: "2026-07-13",
    changes: [
      "SPOTLIGHT CONVERSION PACKAGE (Kerry-ratified, mailbox #155/#156). The standings section is now personal and leads the page: 'WHERE THEY STAND' becomes 'WHERE {FIRST NAME} STANDS' (e.g. WHERE DAVID STANDS) and moves ABOVE Scoring -- the profile's job is Season Contest signups, so standings-vs-money reads first: header -> Where {Name} Stands -> Scoring -> Recent Winnings.",
      "BUY IN -> action chip: a MEMBER not bought into a race sees an orange BUY IN -> chip (links the Season Contests product) in place of the NOT IN badge on their standings rows. Guests/alumni keep plain NOT IN -- their one action is the header JOIN/REJOIN chip (one action chip per page, no competing CTAs). The Leaderboard's Not-in column is unchanged.",
      "Action chips restyled to solid TGF-orange pills with white text, worded JOIN TGF -> (guest) and REJOIN TGF -> (alumni) -- the old grey/amber accents were too weak as CTAs.",
      "Welcome card copy updated for the Spotlight-first landing (Kerry-ratified verbatim): 'Welcome to the Fellowship. Start with your own name -- your season, your stats, your winnings are all in here. Then tap LEADERBOARD for every Season Contest and how it all works...and pays!'",
    ],
  },
  {
    version: "2.86.8",
    date: "2026-07-13",
    changes: [
      "ALUMNI is now the Tracker-wide display term for lapsed members (Kerry): the Customers list badge and detail Status field, the status dropdown, and the events registration-check message all read ALUMNI instead of FORMER, and the statuses reference row is renamed idempotently at boot. Internal keys (former/expired_member/inactive) and the member-facing spotlight treatment (no label, amber REJOIN chip) are unchanged. GG side per Kerry's ruling: newly-lapsed get tagged ALUMNI as memberships expire; legacy FORMER rows in GG remain until then.",
    ],
  },
  {
    version: "2.86.7",
    date: "2026-07-13",
    changes: [
      "GG-drift aligned to Kerry's ruling after he worked the first checklist (all 9 confirmed accurate -- none had renewed): the GG roster tag going forward is ALUMNI, applied as memberships expire; legacy FORMER rows remain until their time. The drift report's suggested action now reads 'set GG roster to ALUMNI', and an Alumni/Former tag is recognized even when GG renders it alongside the chapter name (checked before the TGF-membership match so a lapsed player can never read as a member).",
    ],
  },
  {
    version: "2.86.6",
    date: "2026-07-13",
    changes: [
      "STATUS DERIVATION SOFTENED after the first live drift run flagged clearly-active members (Mary Wade, Jeff Young class) as 'guest': their memberships are legacy/cash joins that predate the Tracker's order history, so purchase records alone can't see them. The curated Tracker status column now VOUCHES a member IN (and expired_member marks alumni) -- it can add member status but can never hide one, so the Decareaux fix stands (financial truth still promotes regardless of a stale column). Both directions of GG-vs-Tracker disagreement still surface on the drift checklist.",
    ],
  },
  {
    version: "2.86.5",
    date: "2026-07-13",
    changes: [
      "GG-drift report now runs with NO URL needed: it compares Tracker financial status against the GG affiliation tag already ingested with every points-race standings snapshot (the roster-derived value GG prints on its boards -- the CH=G column). This covers every ranked player and needs no scraping; the GG member directory turned out to be login-gated, so the page-scrape mode stays only as an option for public pages.",
    ],
  },
  {
    version: "2.86.4",
    date: "2026-07-13",
    changes: [
      "GG-drift widget fetch aligned with the proven gg_history recipe: widget URLs are HTML-entity-unescaped (&amp; -> &) and fetched as a plain GET -- the widgets serve a full HTML page with tables that way, where the XHR variant returns a JS partial the table parser can't read.",
    ],
  },
  {
    version: "2.86.3",
    date: "2026-07-13",
    changes: [
      "GG-drift widget-follow fix: the iframe URL extraction sliced the first CHARACTER of each match instead of the whole URL (re.findall with one capture group returns strings). Verified extraction against a sample iframe; the drift report can now actually read the roster widget.",
    ],
  },
  {
    version: "2.86.2",
    date: "2026-07-13",
    changes: [
      "HOTFIX: Player Spotlight search returned nobody (Kerry caught it within minutes of v2.86.0). The widened R3 search query referenced an archived column that exists on items but NOT on customers, so every search threw and the typeahead silently showed nothing. Reproduced, fixed (the shell-profile guard now uses customers.account_status), and verified against the real schema.",
    ],
  },
  {
    version: "2.86.1",
    date: "2026-07-13",
    changes: [
      "GG-drift report follow-up: Golf Genius pages render their content via widget iframes, so the first live run saw zero tables in the page shell. The report now follows the page's widget URLs (the proven widget-route recipe) and reads the roster rows from there.",
    ],
  },
  {
    version: "2.86.0",
    date: "2026-07-13",
    changes: [
      "MEMBER UX AUDIT S1 PACKAGE (Kerry-ratified, mailbox #149-#151). D1 -- membership status now derives from TRACKER FINANCIAL TRUTH (paid membership terms/purchases) at read time, not the mutable status column that GG-roster syncs left stale (the Decareaux/Beam defect): 'Our side needs to dictate whether he's a member or not.' Adopted terms: member / alumni / guest ('ALUMNI' is our word; GG's roster keeps FORMER for ops). New GG-drift report (bridge scoring-gg-drift:<roster-url>) lists everyone whose GG roster tag disagrees with our financial status so Kerry updates GG from a checklist.",
      "F18 -- the Spotlight EVENTS tile now counts ALL events actually played this season (distinct events across tracked rounds), regardless of member/guest/1st-timer/alumni status. It previously read the points-race standings' tournaments column, so non-enrolled players showed 0-1 (Beam 0 vs 2 rounds; Decareaux 1 vs 5).",
      "R3 -- Spotlight search now indexes EVERYONE tracked (members, guests, alumni, historical): 'if we track it, they have a presence.' The old members-only filter made current members invisible whenever the status column went stale. Empty state reads 'No players found'.",
      "R1 -- status chips from financial truth: TGF MEMBER (green), GUEST (grey + tappable JOIN link), lapsed member = NO label, just an amber tappable REJOIN -> chip to the membership product (no 'former' badge on a fellowship page; doubles as the lapse notice).",
      "R4 -- points-race boards now SHOW non-members ranked (guests/alumni were silently hidden): preserves the LSC alternates math, and 'ranked next to a pot is the best join pitch.' Rows carry a small GUEST/REJOIN pill; the money ladder is UNCHANGED -- visible does not mean eligible, ineligible rows still take no ladder spot and no reset points.",
      "R2 -- nudge amendments: doing the thing a tip teaches now dismisses it (searching kills the search tip, expanding a row kills the standings tip); the standings tip renders as a bottom toast so it never covers table rows; no tips on ?player= deep-link arrival; cards cap at 360px on desktop.",
      "R5 -- the member CTA is now 'ENTER EVENTS & CONTESTS' opening a two-button chooser: This Week's Events (shop section) / Season Contests (product). Interim styling until CD's sheet spec; tap-away cancels.",
    ],
  },
  {
    version: "2.85.2",
    date: "2026-07-14",
    changes: [
      "Player Spotlight subtext now matches the renamed tab: members see 'Live snapshots, same as LEADERBOARD' (was 'CONTESTS'); the admin preview still reads 'CONTESTS'.",
    ],
  },
  {
    version: "2.85.1",
    date: "2026-07-14",
    changes: [
      "Renamed the member 'Spotlight' nav tab to 'PLAYERS' (Kerry) — member nav is now PLAYERS | LEADERBOARD | HANDICAPS. The page URL (/member/spotlight) and its 'Player Spotlight' hero are unchanged, so existing links still work.",
    ],
  },
  {
    version: "2.85.0",
    date: "2026-07-14",
    changes: [
      "MEMBER VIEW IS NOW PLAYER-FIRST (Kerry). Opening the app (/member) now lands on SPOTLIGHT — the individual-player page — instead of the standings, so the member experience leads with the golfer. The member nav is reordered and relabeled to SPOTLIGHT | LEADERBOARD | HANDICAPS (the old 'Season Contests' tab is now 'Leaderboard'). The installed-app start page and the first-visit welcome nudge follow the landing to Spotlight. The paid 'Enter Season Contests' signup button and the admin/manager 'Season Contests' management tab are unchanged.",
    ],
  },
  {
    version: "2.84.2",
    date: "2026-07-14",
    changes: [
      "FIX: 9-hole event registrations wrongly showing an 18H badge (Kerry, a9.18 Forest Creek). The order parser sometimes grabs the SEQUENCE number out of an event code -- 'a9.18' is the 18th 9-hole Austin event, not an 18-hole event -- and stored holes='18' on players in a 9-hole-only event (inconsistently: some parsed as blank). IMPORTANT: this never affected money -- side-game pot sizes are chosen from the event's hole count (a9.x = 9), not the per-player holes field -- only the roster badge, the 9|18 filter counts, and the hole-aware handicap column. New boot heal (heal_item_holes_from_event) forces items.holes to the event's hole count for every single-format event (combo events keep their real per-player 9/18 choice), so the badges are correct and a parser mis-read can't show the wrong hole count. Runs on deploy and on demand.",
    ],
  },
  {
    version: "2.84.1",
    date: "2026-07-14",
    changes: [
      "FIX: prebuilt message templates missing from the Message Players dropdown (Kerry, seen on mobile). The built-in templates (Payment Reminder, Event Announcement, Tee Time Update, etc.) are stored server-side and shared across devices -- not a mobile limitation. The dropdown was built only from a single page-load fetch whose failures were silently ignored and never retried; on the installed app that fetch can fire before the session is ready, come back empty, and leave the list stuck at just 'Custom Message'. The Message Players modal now refreshes the template list from the server every time it opens (and preserves your current selection), so the built-ins reliably appear.",
    ],
  },
  {
    version: "2.84.0",
    date: "2026-07-13",
    changes: [
      "PAYPAL, CASH APP & ZELLE PAYOUTS NOW AUTO-CONFIRM TO PAID (Kerry) -- not just Venmo. All four carry the recipient name AND your note, which is everything the matcher needs, so the payout flips to PAID automatically when the receipt email lands: PayPal (service@paypal.com, \"Your note to <name>: …\"), Cash App (noreply@notifications.cash.app, note shown as \"For <name> - …\"), and Zelle via your bank (Frost's \"Send Money With Zelle Confirmation\" includes \"Message: <name> - Winnings for …\"). One shared peer-to-peer handler now classifies and records each under its correct payment method (PayPal receipts were previously mis-filed internally as \"venmo\" -- they matched, but the label was wrong) and runs the same memo-name + event + amount matching and 2-minute confirmation sweep. The matcher also tolerates Cash App's \"For \" note prefix. Note: Zelle sent from CHASE arrives as a Chase alert with no memo and stays on the old path; Frost Zelle (with the message) is the one that auto-confirms.",
    ],
  },
  {
    version: "2.83.0",
    date: "2026-07-13",
    changes: [
      "EDIT A PLAYER'S PAYMENT METHOD FROM THE PAYOUT ROW (Kerry): once a payment method is set, its pill is now tappable to change it -- previously the '+ Add Payment' chooser only appeared when nothing was on file, so a wrong entry (e.g. a PayPal EMAIL that can't make a one-tap link) was stuck. Now tap the method pill (e.g. 'PayPal ✎') and the chooser re-opens pre-filled with the current method and handle so you can correct it -- swap Don Sharitz's PayPal email for his PayPal.Me name 'dsharitz' and the row instantly becomes a working one-tap PayPal link. Works on both the PAYOUTS tab and the per-event PAYOUTS panel; the pill stays a single narrow control so the column doesn't widen.",
    ],
  },
  {
    version: "2.82.1",
    date: "2026-07-13",
    changes: [
      "FIX: PayPal pay link no longer breaks when the handle is an email (Kerry hit 'Something went wrong' after adding a PayPal email and tapping Pay). PayPal.Me links only resolve a USERNAME (paypal.me/JohnDoe) -- an email 404s to PayPal's error page. Now: a PayPal.Me username builds a one-tap prefilled link; a PayPal EMAIL shows a 'PayPal (manual)' badge instead (pay in the PayPal app, then Mark Paid on the PAYOUTS tab) since there's no way to deep-link a prefilled payment to an email. Same guard added for Cash App (an email/phone can't be a $cashtag). The '+ Add Payment' handle box now shows a per-method hint -- picking PayPal prompts for a 'PayPal.Me name (email = manual)' so the right thing gets entered.",
    ],
  },
  {
    version: "2.82.0",
    date: "2026-07-13",
    changes: [
      "PULL-TO-REFRESH ON THE INSTALLED APP (Kerry): when the app is added to your home screen (iOS), you can now pull down at the top of any page to reload it -- a small orange spinner follows your finger and flips to a spin as it refreshes past the threshold. Mobile web browsers already had this natively; the installed iOS app did not (it just rubber-banded), so this fills that gap. Built into the shared nav shell so it works on every page, member and admin. Gated to the iOS installed app so it never double-fires with a browser's or Android's built-in pull-to-refresh, and it ignores pulls that start inside a drawer, sheet, or dialog.",
    ],
  },
  {
    version: "2.81.1",
    date: "2026-07-13",
    changes: [
      "FASTER PAYOUT CONFIRMATION (Kerry: confirmations 'took way longer than I'd like'). The expense inbox -- which catches the Venmo receipt and flips a payout to PAID -- now sweeps every 2 minutes instead of every 5 (new EXPENSE_CHECK_INTERVAL_MINUTES, default 2). This is cost-neutral: the dedup table bills each email to the AI exactly once no matter how often we poll, so a tighter cadence only adds free Microsoft Graph calls. This mainly helps payments made OUTSIDE the app -- e.g. paying to someone's partner's Venmo with their name in the memo -- where there's no in-app Pay tap to trigger the existing 75s/180s fast sweep. Tapping Pay on the per-event PAYOUTS panel now also triggers that fast sweep (previously only the main PAYOUTS tab did).",
    ],
  },
  {
    version: "2.81.0",
    date: "2026-07-13",
    changes: [
      "PAYOUTS ACTION COLUMN SIMPLIFIED TO ONE PILL (Kerry): each payout row now shows a SINGLE control instead of two side-by-side badges. Before, an unpaid row showed a Pay link AND a PENDING badge; because that double-width cell set the column width, the green PAID pills on everyone else got pushed off the right edge on mobile. Now: paid rows show PAID, unpaid rows show just the Pay link (the link already means 'not paid yet', so the redundant PENDING pill is gone), and rows with no payment info show a single '+ Add Payment' control. The column stays narrow and every row's status is visible without horizontal scrolling. Applies to the per-event PAYOUTS panel and the PAYOUTS tab.",
      "\"+ ADD PAYMENT\" NOW SUPPORTS ANY METHOD (Kerry): the quick add on a payout row is no longer Venmo-only. Tap '+ Add Payment', choose Venmo / PayPal / Cash App / Zelle, enter the handle (or email), Save -- it's written to that person's Customer record (Venmo handle to venmo_username; PayPal/Cash App/Zelle to payment_method + payment_handle) and the row instantly becomes the matching pay link (or a Zelle 'pay manually' badge). No reload. New customer fields payment_method/payment_handle are now editable through /api/customers/update.",
    ],
  },
  {
    version: "2.80.0",
    date: "2026-07-13",
    changes: [
      "QUICK \"+ VENMO\" ON PAYOUTS (Kerry): winners with no Venmo handle on file now show a small dashed \"+ Venmo\" button on their unpaid payout row (both the PAYOUTS tab and the per-event PAYOUTS panel on Events). Tap it, type the handle, Save -- it's written to that person's Customer record (by customer_id, so it sticks for every future event) and the row instantly swaps to a live blue Pay link with the amount and memo pre-filled. No page reload and no trip to the Customers page just to pay someone.",
    ],
  },
  {
    version: "2.79.4",
    date: "2026-07-13",
    changes: [
      "Hardened the Team Net blind-draw repair's player matching: it now resolves each winner through the curated GG-name spine (the same one used to record payouts), so scorecard names that differ from the customer record -- e.g. 'MORENO, Robert' on the card vs 'Roberto Moreno' in the directory -- resolve to the right person instead of failing. No shell customers are created on a miss.",
    ],
  },
  {
    version: "2.79.3",
    date: "2026-07-13",
    changes: [
      "TEAM NET BLIND-DRAW PAYOUT REPAIR -- PARTIAL, UNPAID-ONLY (Kerry: 'only repair those, I've paid others from that event'). The v2.78.4 code fix (blind-draw partners share the team purse) only affects NEW recordings; s9.17 Silverhorn's payouts were recorded before it, so its stored split still over-paid the winning team's real members and gave the blind-draw partner $0. A full re-record would delete and re-create the whole event's rows including ones already paid, so instead a new surgical repair (repair_teamnet_blind_draw_shares) corrects ONLY the unpaid rows of the affected Team Net group and never touches a paid row. It brings each unpaid winner's team_net share to the correct uniform amount (adjusting the pending payout row AND its mirror pending ledger entry in lockstep, or inserting a fresh pending row for the excluded blind-draw member), and skips any teammate already paid. Net change across the group is $0. Exposed as bridge command scoring-teamnet-repair:<event> (dry-run) / <event>|apply.",
    ],
  },
  {
    version: "2.79.2",
    date: "2026-07-13",
    changes: [
      "VENMO PAYOUT MATCHER NOW READS THE MEMO'S PAYEE NAME (Kerry: 'Matt Griffin didn't register as paid... I thought it should look at the memo'). Matt's payout ($38.25, s9.17 Silverhorn) never flipped to PAID because his Venmo account name displays as 'robert griffin', which is who the receipt was addressed to -- but the memo said 'Matt Griffin - Winnings for s9.17 Silverhorn'. The expense parser had been STRIPPING that leading payee name off the memo, so the matcher only ever saw the wrong account name. Three fixes: (1) the parser now preserves the memo verbatim, including the 'Name - ' prefix; (2) on new Venmo payout emails, the payee is resolved from the memo's name prefix FIRST, falling back to the Venmo display name only if that misses -- so the account name no longer mis-attributes the payment; (3) the matcher gained two memo-based fallbacks for records where the recipient name doesn't resolve: it reads the memo's payee name, and if that still misses it matches the memo's event code + the exact payment amount to the one pending payout in that event owing exactly that sum. Matt's stuck payout is resolved by fallback (3).",
    ],
  },
  {
    version: "2.79.1",
    date: "2026-07-13",
    changes: [
      "PAY BUTTON NOW SHOWS A VERIFYING STATE (Kerry): after you tap Pay on a payout, the button turns into an amber 'Sent · verifying…' pill (with a small spinner) so you know the payment is registered and NOT to tap it again while we wait for the Venmo receipt. A background poll flips the row to Paid the moment the server confirms it (within a couple minutes, riding the new 75s/180s inbox sweep). If 5 minutes pass without confirmation, the Pay button pops back up so it can be retried. The verifying state is per-device (localStorage) and survives a reload or the app backgrounding while you're in Venmo -- reopening the Payouts page resumes the wait and the live poll.",
    ],
  },
  {
    version: "2.79.0",
    date: "2026-07-13",
    changes: [
      "FASTER VENMO PAYOUT CONFIRMATION (Kerry): tapping a Pay button on the PAYOUTS page now asks the server to sweep the expense inbox ~75 seconds and ~180 seconds later, so the Venmo receipt is caught and the payout flips to PAID within a couple minutes instead of waiting for the normal 5-minute cycle. New admin endpoint POST /api/tgf/schedule-venmo-check schedules two one-shot APScheduler jobs running check_expense_inbox (which parses the receipt AND runs the payout matcher inline). Repeated Pay taps coalesce onto the same two jobs, so paying a batch triggers one sweep shortly after the last tap. The 5-minute cycle remains the backstop, and cost is unchanged -- the expense dedup bills each email at most once no matter how often the inbox is swept.",
    ],
  },
  {
    version: "2.78.4",
    date: "2026-07-13",
    changes: [
      "TEAM NET BLIND-DRAW FIX (Kerry, verified vs GG Player Purse Summary): blind-draw team partners are now PAID their equal share of the team purse, matching Golf Genius. assemble_event_game_payouts previously excluded the Bl[LAST, First] slot and split the team pot among the real members only -- on s9.17 Silverhorn (2026-07-07) that paid the winning team's South/Moreno/Wade $18 each and gave the blind-draw Hamilton $0, where GG splits the $54 four ways at $13.50 each. Fix unwraps the Bl[...] wrapper to the real name and includes it in the split. Affected past 2026 team-net events with a blind draw will re-record to match GG.",
      "AUDIT LESSON banked: team-game payouts must be reconciled player-by-player, not by event total -- the earlier s9.17 audit matched on totals (686.01 vs 686.04) and every individual game board, which masked $4.50-$13.50 per-player errors that netted to pennies. Documented in docs/claude/side-games.md.",
    ],
  },
  {
    version: "2.78.3",
    date: "2026-07-13",
    changes: [
      "Verified Tuesday's (s9.17 Silverhorn, 2026-07-07) calculated payouts game-by-game against Golf Genius: Individual Net, Team Net, CTP, City/TGF MVP all match to the penny. The only differences are three sub-cent tie-split rounding cases (Moreno $11.33 vs GG $11.34, Sharitz $7.55 vs $7.56, Young skins $19.12 vs $19.13). ROOT CAUSE + RULING (Kerry, no code change): our splits apportion so shares sum EXACTLY to the pot collected (last tied player absorbs the shortfall); GG rounds each share half-up, which pays a penny or two OVER the pot (GG's own Ind Gross shares summed to $68.03 under a $68.01 'Total Purse Allocated' line). Kerry ratified MONEY OUT = MONEY IN -- keep our exact-to-pot behavior; GG over-pays by rounding. Documented in docs/claude/side-games.md so it is never 'fixed' to match GG.",
    ],
  },
  {
    version: "2.78.2",
    date: "2026-07-12",
    changes: [
      "CONTESTS SHOW POINTS EVENTS ONLY (Kerry): the NON-POINTS EVENTS / other-rounds scorecard lists are removed from the expanded player panels (race and monthly views) -- points lines still expand to their hole-by-hole scorecards in place.",
      "2025 LEAK PLUGGED (Kerry: 'we're revealing 2025 scores -- I didn't want to do that yet'): the scorecards list was reading /api/scoring/rounds, which had no season filter, so last night's archive imports surfaced to members. The endpoint now returns ONLY current-season, live-source rounds to pinless/member sessions (logged-in staff still see everything) -- the 2026-only ruling is now enforced at the API layer, not just in the UI, so no future member surface can leak archive data through this route.",
    ],
  },
  {
    version: "2.78.1",
    date: "2026-07-12",
    changes: [
      "PLAYERS CUP PLACES ARE BY FLIGHT (Kerry): the Contests page's flight sections now number players within their flight (competition ranking, ties share a T-rank) instead of showing the overall 119-player rank -- 2ND FLIGHT starts at 1, not 10. The rank-movement arrow still reflects overall movement. Spotlight's Where They Stand matches: a flighted race shows rank-in-flight over flight size ('4 of 32' alongside the 2ND FLIGHT label) instead of '16 of 119'.",
    ],
  },
  {
    version: "2.78.0",
    date: "2026-07-12",
    changes: [
      "FIRST-USE MEMBER NUDGES LIVE (design-claude spec #139/#140, Kerry-ratified look with the #141 welcome-copy edit): three one-time discovery whispers on the member view -- the WELCOME card on first /member visit ('Welcome to the Fellowship. Tap HOW IT WORKS on any contest to see exactly how it pays -- and tap any player to explore their season.'), the standings TIP ('Tap any player to see their rounds -- event by event, hole by hole.') anchored under the first standings rows, and the Spotlight TIP ('Search any member -- including yourself.') under the search box.",
      "The whisper pattern per spec: Bitter eyebrow + one-line system-sans body, orange exactly twice (eyebrow + 3px keyline), 40x40 one-tap dismiss, no scrim, absolute overlay so nothing reflows, bottom-toast degrade when the anchor is off-screen. Once per device via localStorage (tgf_nudge_welcome / tgf_nudge_standings / tgf_nudge_spotlight_search); one at a time -- welcome wins and defers the standings tip to the next visit. SCOPE GUARD (ratified #141): the nudge component is for discovery tips ONLY, never actionable/time-sensitive/financial messaging.",
      "Measurement: the anonymous member beacon logs nudge impressions and dismissals (new whitelisted 'nudge' event, detail '<key>:impression|dismiss') so /traffic shows whether they work. Admin pages never see nudges (MEMBER_MODE only).",
    ],
  },
  {
    version: "2.77.3",
    date: "2026-07-12",
    changes: [
      "MEMBER APP INSTALL FIX (Adam Baker's Android, via Kerry): installing the app from a /member page launched at the manifest's start_url (/events -- the PIN-gated admin landing), stripping the member context. The three member pages now serve a dedicated member manifest (manifest-member.json: name 'The Golf Fellowship -- Members', start_url /member/contests), so a home-screen app added from any member page opens pinless on the member view. Android reads the manifest of the page it was installed from; existing broken icons need a remove + re-add.",
    ],
  },
  {
    version: "2.77.2",
    date: "2026-07-12",
    changes: [
      "HOTFIX -- drama lines PULLED (Kerry: the numbers were wrong). The 'Only N pts from the money' line quoted in_reach.points_to_next, which is the gap to the NEXT PLACE UP, not to the money line -- it badly understated the real distance for anyone more than one place below the ladder. All incentive lines are removed from Where They Stand until the server computes a true money-line gap (points to the last paying position, ties considered). The server templates and in_reach block stay in place for the corrected version.",
    ],
  },
  {
    version: "2.77.1",
    date: "2026-07-12",
    changes: [
      "Spotlight Where They Stand order (Kerry): THE FELLOWSHIP CUP now sits above THE PLAYERS CUP -- display order is SA NET, Austin NET, Fellowship Cup, Players Cup, then fall/match-play rows.",
    ],
  },
  {
    version: "2.77.0",
    date: "2026-07-12",
    changes: [
      "Spotlight -> Contests now lands ON the player (Kerry): the Where They Stand links carry the player through the hash, and after the standings render the page scrolls their row to center with a soft orange pulse. Works for every race view; member and admin alike.",
      "IN-THE-MONEY DRAMA LINES LIVE (#99 items 1/3 under CA GO #120's bind conditions -- canonical templates are SERVER-side, every number from the live payload): each Where They Stand row now carries an incentive line colored by state. Leader: 'Leading the race -- $X projected today' (green). In the money: '$X projected · N pts to the next rung' (green). Chasing: 'Only N pts from the money ($X)' (orange). Not entered: '$X pot and growing -- not entered yet' (gray). Numbers come from the ratified in_reach block (projected payout, next rung, live pot).",
    ],
  },
  {
    version: "2.76.5",
    date: "2026-07-12",
    changes: [
      "Contests -> Spotlight connection (Kerry GO on the expanded-panel design): when a player row is expanded on the Contests page, a 'Full Spotlight ->' pill appears at the top of the event-breakdown panel (both the race and monthly views) linking to that player's Spotlight via the ?player= deep link -- member view targets /member/spotlight, admin /spotlight. The row tap itself is untouched: expand -> event lines -> scorecard detail all behave exactly as before; the pill only exists inside the opened panel, so there are no competing tap targets on mobile. Completes the loop with v2.76.3's Where-They-Stand links back into the contest views.",
    ],
  },
  {
    version: "2.76.4",
    date: "2026-07-12",
    changes: [
      "Spotlight scoring stats now cover ALL of the current season (Kerry): par-3/4/5 averages, gross averages, and the eagles/birdies/pars/bogeys distribution compute over every 2026 tracked round (was a rolling last-20 window); the stat-strip label reads 'N rounds this season'. Trends stay recent-form (last 10 rounds, 5 vs 5) per the earlier ruling. The calendar-year filter also keeps archive-era rounds out of member-visible stats by construction, honoring the 2026-only ruling as history imports grow.",
    ],
  },
  {
    version: "2.76.3",
    date: "2026-07-12",
    changes: [
      "Spotlight WHERE THEY STAND rows now deep-link to their contest views (Kerry): each race row is a tappable link (chevron affordance, race name highlights on hover) into the Contests page's restore-in-place hash -- SA/Austin NET, Players Cup, Fellowship Cup, Fall NET rows land on their race; the Match Play row lands on the Match Play tab. Member-mode rows target /member/contests; admin rows target /contests.",
    ],
  },
  {
    version: "2.76.2",
    date: "2026-07-12",
    changes: [
      "Spotlight scoring trends now read recent FORM off the last 10 rounds (Kerry): latest 5 rounds vs the 5 before, and the arrows earn at 10+ tracked rounds (was last-10-vs-prior-10, earned at 15+). Averages and the scoring distribution keep the 20-round window; negative trend still means improving.",
    ],
  },
  {
    version: "2.76.1",
    date: "2026-07-12",
    changes: [
      "Member nav mobile fit (Kerry): with three tabs, the first tab collapses to CONTESTS on mobile (the 'Season ' prefix returns on desktop) so CONTESTS | HANDICAPS | SPOTLIGHT all fit without truncation. Threshold rule reaffirmed: more sections than three moves the member view to a hamburger with the full SEASON CONTESTS label.",
    ],
  },
  {
    version: "2.76.0",
    date: "2026-07-12",
    changes: [
      "SPOTLIGHT IS MEMBER-VISIBLE (Kerry GO, in-session): the pinless member view gains a third tab -- CONTESTS | HANDICAPS | SPOTLIGHT (inline tabs per the <=3-sections rule, no hamburger). New /member/spotlight route renders the page in member mode (admin subnav and preview chip hidden, window.MEMBER_MODE set so the login modal is skipped and the anonymous traffic beacon counts opens/taps); /api/spotlight/search and /api/spotlight/player flip from admin to the member public-read tier.",
      "Kerry's rulings enforced: WINNINGS SHOWN (career total + recent payouts from Tracker payout records); 2026-ERA DATA ONLY -- satisfied by construction, the payload reads live points-race snapshots, current handicaps, season contests, and Tracker payouts, never gg_history/archive rows; the typeahead's member-status filter already excludes archive-created (gg_roster/expired) profiles. PII sweep re-verified: both payloads carry name/chapter/competitive data only -- no emails, phones, addresses, or DOBs.",
    ],
  },
  {
    version: "2.75.6",
    date: "2026-07-12",
    changes: [
      "Contests page decluttered (Kerry): the on-page season-structure paragraph under the cup standings and the pot-projection caption under the purse chips are removed -- both duplicated what the HOW IT WORKS popup already explains (its The Race / The Money sections carry the best-10 + POINTS RESET + TGF Championship story and the pot-growth mechanics). prRenderStructureNote kept as a no-op that clears the element.",
    ],
  },
  {
    version: "2.75.5",
    date: "2026-07-12",
    changes: [
      "Android app icon: dedicated MASKABLE icons added (mark at the 62% safe-zone proportion) so Android's circle/squircle masks never clip the ring, while iOS and 'any' contexts keep the new full-bleed 84% mark. Manifest purposes split accordingly (big icons purpose=any; maskable pair purpose=maskable). Android users: remove + re-add the home-screen app to refresh the icon, same as iOS.",
    ],
  },
  {
    version: "2.75.4",
    date: "2026-07-12",
    changes: [
      "Home-screen app icon: the TGF mark now fills ~84% of the tile (was 62%) -- Kerry's 'bigger logo on the badge' was about the PWA icon, not the in-app nav (both are now bigger). icon.svg rescaled and all PNG sizes (180/192/512) regenerated from it. iOS caches home-screen icons: remove and re-add the app to see the new one.",
    ],
  },
  {
    version: "2.75.3",
    date: "2026-07-12",
    changes: [
      "Nav badge: TGF logo icon enlarged (32/34px -> 42px) in the dark shell brand, per Kerry.",
      "SPOTLIGHT MEMBER FLIP RULINGS BANKED (Kerry, in-session): SHOW WINNINGS on the public member view; data scope 2026-ONLY (archive years join per-season after audit sign-off, via the v2.74.0 source tags); member nav stays inline tabs at 3 pages (Contests | Handicaps | Spotlight) -- no hamburger, per the existing <=3-sections threshold rule. The flip itself (role change + PII sweep + nav link + traffic beacon) leads the next build session.",
    ],
  },
  {
    version: "2.75.2",
    date: "2026-07-12",
    changes: [
      "REVIEW UI -- Link by NAME (Kerry, in-session: 'I don't have customer #s'): the customer-number box on each pending-name card is now a live name search. Type two or more letters and matching customers appear as tappable Link chips (searches first/last/full name, 'LAST, First' order, and name aliases; typing a number still looks up that exact customer id). Tapping a chip performs the Link immediately -- same-surname candidate chips continue to appear automatically.",
    ],
  },
  {
    version: "2.75.1",
    date: "2026-07-12",
    changes: [
      "HOTFIX -- name_links rebuild stranded-shell recovery: python-sqlite3 runs CREATE TABLE in autocommit but the copy INSERT opens a transaction, so a read-only caller (the overview API) that closed without committing left an empty gg_history_name_links_v2 shell committed while the copy/drop/rename rolled back -- every later gg-history call then failed with 'table already exists' (caught on prod within minutes; no data touched). The rebuild now drops any stranded shell first and commits itself unconditionally. Recovery reproduced and proven against a replica of the broken state.",
      "PER-GAME MONEY WALK (Phase B part 2): scoring-gg-history:games=<subdomain>[@budget] (+ games-bg) walks each round's per-tournament boards -- INDIVIDUAL Net $, SKINS $, TEAM Net $, MVP $, Closest to Pin, everything except the ALL boards/Adjustments -- into gg_history_results with the verbatim board label as game_label, verbatim T1-style positions, parsed purse/points, team rows flagged via team_label. Rows attach to the SAME gg_history_events row the export channel created (matched by round_index), so export and scrape sit side by side per event; scrape rows replace idempotently, export rows are never touched. Fetch-then-write per round so no write transaction spans network I/O (the holes walk may run concurrently).",
      "IDENTITY CASCADE EXTENDED: _resolve_identity now falls back from the scoring resolver to the roster map (printed handle -> exactly one customer, collision-safe) and then to any earlier ruling for that name+portal -- so Kerry's manual links and roster matches propagate to every future walk's rows instead of re-pending.",
      "AUDIT EXTENDED: audit=<prefix> now ALSO runs the gross/net scorecard check for non-2026 seasons once Phase-B holes are banked (reported under 'scoring') -- the export and scrape channels prove each other on archive years, not just live.",
    ],
  },
  {
    version: "2.75.0",
    date: "2026-07-12",
    changes: [
      "GG HISTORY REVIEW UI (admin): new /admin/gg-history page (linked from every admin subnav) with three views -- the PENDING NAMES queue (each unresolved archive name with its portal, data-row counts, roster affiliation, and same-surname candidate chips; actions Link / Guest / Not-a-person, with Undo), per-portal COVERAGE (Phase-A pages, Phase-B rounds, standings/events/results/hole-round counts, pending names), and a STANDINGS BROWSER (verbatim rows with position_raw, linked customer, points, money). Link backfills every banked row for that name+portal (standings, results, hole-by-hole scoring_rounds); Guest never creates a profile (house rule); reopen un-links only what the manual ruling linked.",
      "NAME_LINKS 3-COL UNIQUENESS REBUILD (the deferred #123 amendment-b item, flagged in mailbox #130): gg_history_name_links rebuilt so uniqueness is (raw_name, portal_id, gg_member_id) -- the same printed name CAN be two people when their GG member ids differ (the Kryszak class). gg_member_id is now NOT NULL DEFAULT '' (SQLite UNIQUE treats NULLs as distinct; '' keeps the no-id case deduped). Idempotent boot-path migration preserves row ids; the writer's upsert moved to the 3-col conflict target and stamps the preferred key when the printed handle maps to exactly one master-roster member. Reviewed rulings (Kerry's manual decisions) are never overwritten by automated passes.",
      "COO SURFACING: one aggregate action item ('GG History: names pending identity review') tracks the live pending count -- created/updated by the ingest walkers and every review action, completed automatically when the queue empties. 121 names never become 121 items.",
      "OPS: scoring-gg-history:holes-bg=<subdomain>[@budget] runs the Phase-B walk in a background thread (MCP clients time out ~60s; a portal walk wants minutes), holes-status polls it, overview returns the per-portal coverage payload the admin page uses.",
    ],
  },
  {
    version: "2.74.0",
    date: "2026-07-12",
    changes: [
      "PHASE B HOLE-BY-HOLE INGEST (Kerry's #1 data priority; pilot portal tgf-sa2025): new bridge command scoring-gg-history:holes=<subdomain>[@budget] walks the portal's tournament_results round selector (the full season, server-side) and imports every round's ALL Net then ALL Gross boards through the existing import_gg_scorecards machinery -- courses/tees, scoring_rounds/scoring_holes, raw archive before parse, cid resolution, and per-card verification all reused. Walk state lives in gg_history_pages as 'round:<round_id>' rows, so runs are resumable and a postponed/zero-card round is marked done instead of retrying forever.",
      "import_gg_scorecards gains round_date + source params: archive events have no Tracker events row, and without a date the cross-tournament dedupe cannot scope (round_date NULL never matches in SQL) -- ALL Net + ALL Gross would double-import every player. Round dates join from the export channel's gg_history_events by round_index (verified: export Round N == widget round_index N on sa2025); rounds with no resolvable date are SKIPPED and surfaced rather than double-imported. Archive rows are tagged source='gg_history:<subdomain>' so history imports stay distinguishable from live-sync rows (and a future Two Man Tour lane can be brand-filtered).",
      "POC lessons applied: round_key=<round_id> scopes the dedupe on multi-round days (Hill Country Matches class), and unresolved player names register in gg_history_name_links per portal for the review queue, then backfill from gg_member_map when the printed handle maps to exactly one customer (collision-safe: ambiguous handles stay pending).",
    ],
  },
  {
    version: "2.73.1",
    date: "2026-07-11",
    changes: [
      "MAILBOX #126-#128 COMPLIANCE BATCH. #123-amendment retrofit (the ratification amendments crossed mid-flight with the v2.70.0 build): gg_history_standings gains position_raw (verbatim 'T6' ranks backfilled from raw_row -- nothing was ever lost) and contest_kind + a (season,chapter) index; gg_history_name_links gains gg_member_id as the preferred match key (backfilled from the master map), and any handle mapping to multiple customers is FORCED to pending -- never auto-linked. The 3-column uniqueness rebuild is deferred to the review-UI build and flagged in the mailbox.",
      "#127 GUARDRAILS on the created profiles: historical status verified (expired_member + gg_roster source); marketing-flow exclusion enforced in code (the re-engagement sender now skips gg_roster profiles with an explicit reason -- Brevo/HubSpot don't exist in this stack, so no sync to disable); dup-name review lane live (created profiles colliding with existing names get flagged review_dup_name, never auto-merged -- the fixture immediately caught the roster's own two distinct Joe Kryszaks); cross-chapter principle upheld by construction (chapter was never a match signal).",
      "#128 ENRICH AT BIRTH: gg_roster profiles get phone + date-of-birth (guarded new customers column) synced from the roster contact file (850 contact rows staged; never overwrites existing values, only touches gg_roster profiles). LSC 2025 money-image page: widget HTML archived verbatim with the cloudfront image URL pinned (the image host is outside the SSRF allowlist; the money DATA is already banked via the export).",
    ],
  },
  {
    version: "2.73.0",
    date: "2026-07-11",
    changes: [
      "HISTORICAL MEMBER PROFILES (Kerry: 'Absolutely yes, create them'): roster_create_members creates customer profiles for the master roster's unmatched TGF and Former members -- name from the GG handle (mixed-case particles preserved), chapter from affiliation, status expired_member, acquisition_source gg_roster, GG email as primary. Guests, Facebook Leads, and Interest rows are NEVER created. After creation, all banked history rows (standings, results, name-links) backfill by handle join. Bridge: scoring-gg-history:roster-create-members; idempotent.",
      "PAIRINGS RULING banked (Kerry): scrape GG tee sheets as primary, starter-sheet PDFs as cross-check (and sole pre-GG source), scorecard groupings as game-time tiebreaker; disagreements flagged, never silently resolved. YEAR-AT-A-TIME directive: complete EVERYTHING for one year before moving to the next -- the per-year playbook is standings + exports + hole-by-hole + game money + match play + pairings + identity + audit + sign-off.",
    ],
  },
  {
    version: "2.72.1",
    date: "2026-07-11",
    changes: [
      "2025+2026 PROOF OF CONCEPT COMPLETE: all eight export pairs ingested live (205 events, 3,199 player-rounds; 2026 identity-matched 100%, 2025 ~97%) and the cross-channel audit ran -- 1,305 checks, 95.1% exact, with every mismatch in one of three explained classes: post-import score edits (rescrape flags -- vanishes on frozen archive years), multi-round-day date-join ambiguity (Hill Country Matches' six same-Saturday rounds; audits need round-label joins), and per-round purse vs season-total money scope (exports carry round money; standings carry season-contest payouts on top -- career winnings = standings truth).",
      "Channel-redundancy thesis proven on the first season tried: LSC 2025's portal money page is an uploaded image (unscrapable) and the export is the only structured source. Clean 100% sheets: Austin 2026 (369/369), Austin 2025 (88/88), Road Trip 2025 (9/9).",
    ],
  },
  {
    version: "2.72.0",
    date: "2026-07-11",
    changes: [
      "EXPORT-PAIR INGEST + PARITY AUDIT (Kerry: complete 2025+2026 as the proof of concept before moving back): the eight staged GG export pairs now flow into the database -- league rounds become gg_history_events (with parsed dates), and every player-round becomes a gg_history_results row carrying gross/net/course-handicap structured plus adjusted-gross, at-the-time handicap index, purse, and points verbatim in raw_row. Identity through the roster map + scoring cascade; league rosters enrich gg_member_map with league-scoped ids. Idempotent per league.",
      "Bridge commands: scoring-gg-history:export=<prefix>|ALL and audit=<prefix>|ALL. The audit is the three-channel framework's proof: 2026 leagues check per-round gross/net against independently scraped scorecards (customer+date join); 2025 leagues check per-player season purse totals against the Phase-A money-leaders standings (verbatim-name join).",
      "ROSTER MAP APPLIED (map-only -- no customers created): 1,089 gg_member_map rows live, 365 customer-linked (344 email, 21 handle cascade); 4 standings rows backfilled, 2 pending names resolved. The 219 unmatched TGF/Former member profiles remain Kerry's open decision.",
      "Local verification against the real staged CSVs before deploy: SA 2026 = 43 events + 628 player-rounds; Anthis R3 92/77/CH15 matches the earlier live parity check; deleted Round 13 honored via header labels; re-run idempotent.",
    ],
  },
  {
    version: "2.71.1",
    date: "2026-07-11",
    changes: [
      "GG EXPORT CHANNEL VALIDATED AND STAGED (Kerry supplied the SA + Austin 2026 Season Scores + roster exports): the export data is audit-grade -- spot-checks matched the Tracker's independently-scraped scorecards stroke-for-stroke (gross/net/course-handicap). Exports are now the third channel in the history framework: the ONLY source for at-the-time handicap index series, adjusted gross, DOBs, referral graph, payout handles, and deleted-round visibility; scraping stays the only source for hole-by-hole, per-game money, and standings. The overlap is the audit zone.",
      "Both 2026 export pairs converted and staged under email_parser/data/gg_exports/ (18 CSVs; rosters trimmed -- DOBs/phones deliberately not committed). Key finding: GG numeric member ids are CONTAINER-SCOPED (same golfer, different id per league) -- handle+email are the stable person keys, confirming the gg_member_map design. Export-pair ingest template is the next build.",
      "Also: roster email-map fix (emails live in customer_emails; customers has no email column) shipped earlier this release train.",
    ],
  },
  {
    version: "2.71.0",
    date: "2026-07-11",
    changes: [
      "MASTER ROSTER INGEST (Kerry: 'master roster first' -- the identity spine for the whole history initiative): Kerry's GG admin export (1,089 golfers -- every one with a unique GG member id, 98% with emails, Start Years reaching back to 2007) ships trimmed to matching essentials as email_parser/data/gg_master_roster_v6.csv. Phones and DOBs were deliberately left out of the repo; they stay in Kerry's spreadsheet and can layer in later through the review UI.",
      "New gg_member_map table: GG member id -> customer_id, plus handle/email/affiliation/start_year/member-or-guest. The roster's Handle column is the exact 'LAST, First' string GG prints on every standings table across all ten years -- a direct join key that turns name-guessing into id lookups.",
      "Bridge commands: scoring-gg-history:roster=report (dry-run match report -- exact email match first, then the scoring-resolver handle cascade; never creates customers) and roster=apply (writes the map, then backfills customer_id onto already-ingested standings rows and resolves pending name-links by handle join). Report-first discipline: apply runs only after Kerry reviews the report.",
    ],
  },
  {
    version: "2.70.1",
    date: "2026-07-11",
    changes: [
      "FIRST GG HISTORY DATA IS IN THE DATABASE: the 2025 wave ingested live on the deployed engine -- 46 standings pages across tgf-sa2025, tgf-austin2025, tgf-champ25, tgf-roadtrip25, and tgf-lonestarcup25, banking 1,943 verbatim standings rows with 1,871 (96.3%) identity-linked to customer_ids on the first pass; 38 unique names queued pending review. Every fetched widget response was raw-archived to gg_raw_archive before parsing. Idempotency verified in production (immediate re-run performed zero work).",
      "Known item: lonestarcup25's LEADERBOARD/MONEY page is the images-widget class (uploaded graphic, no server-side table) -- flagged for Phase B or manual entry, same class as the 2016 match-play brackets.",
    ],
  },
  {
    version: "2.70.0",
    date: "2026-07-11",
    changes: [
      "GG HISTORY INGEST ENGINE (Phase A) -- Kerry RATIFIED the gg_history_* schema in-session and directed the start: slowly, backwards chronologically. New email_parser/gg_history.py ships the six ratified tables (portals registry seeded with all 61 entries and Kerry's brand rulings, pages catalog, standings, events, results, name-links review queue) plus the Phase-A walker: per portal it discovers league_id and the full page catalog, then for every standings-kind page archives the raw widget response into gg_raw_archive BEFORE parsing (the GG-prune insurance), banks verbatim standings rows with parsed rank/points/money, and identity-links through the scoring resolver cascade -- never creating customers; unmatched names queue as pending for Kerry's review.",
      "Bridge commands on probe_golf_genius (stale-session-safe, same pattern as the scoring bridges): scoring-gg-history:seed | status | ingest=<subdomain>[@<budget_s>]. Ingest is resumable and time-budgeted with polite 1s pacing and per-page commits.",
      "TWO MAN TOUR LANE (Kerry): the Tour 'needs its own home' -- no functional crossover with TGF currently. Tour portals ingest LAST under the hard brand filter; TGF members who played Tour events still identity-link by customer_id so the future partner build inherits connected history.",
      "Parser + classifier unit-verified against both captured eras: the 2016 season_points shape (Number/Player/Points/Purse with the folded Totals row) and the modern season_points_v2 shape (T-ranks, Points Behind Lead, no purse).",
    ],
  },
  {
    version: "2.69.7",
    date: "2026-07-11",
    changes: [
      "GG HISTORY INVENTORY: 100% COVERAGE. Kerry's final link batch (lonestarcup, tgf-2020hccup, tgf-hc, tgf-hcm, hillcountrymatches, hillcountry2man-1, hillcountry2man) -- all seven alive -- closes the map at 59 LIVE PORTALS: every in-scope archived league now has a walkable entry URL. The naming conventions were wildly inconsistent (tgf-<name><YYYY>, two-digit years, year-first, champ/hcc/hc/hcm abbreviations, bare no-prefix subdomains), so the gg-history.md registry table is the only reliable index.",
      "Brand correction from Kerry (supersedes the earlier ruling): the two Hill Country Two Man Challenge leagues (Jul + Nov 2023) are TWO MAN TOUR, not TGF. Only ingest-time verification left: whether the 2024-25 per-course Two Man Tour events aggregate inside tgf-twomantour.",
    ],
  },
  {
    version: "2.69.6",
    date: "2026-07-11",
    changes: [
      "GG HISTORY INVENTORY CLOSES AT 52 LIVE PORTALS. Kerry's four late-session links (tgf-hcc22, lonestarcup24, redblue, tgf-trinity) revealed two more naming conventions -- 'hcc' abbreviations and NO-PREFIX subdomains -- and the derived sweep added tgf-hcc21 (2021 Hill Country Cup, full league site). Recovered tonight in total: TGF Championships 2020-2025 complete, Lone Star Cups 2021/2022/2024/2025, Hill Country Cups 2021/2022, Red Blue Challenge 2023, Trinity River Cup 2022, Road Trips 2020-2025 complete, Two Man 2020-2022 + Tour.",
      "Only SIX in-scope leagues remain URL-less: Lone Star Cup 2023, Hill Country Cup 2020, TGF Hill Country 2022, Hill Country Matches 2023 + 2024, and the two 2023 Hill Country Two Man Challenges (the 2024-25 per-course Two Man Tour events likely aggregate inside tgf-twomantour -- verified at ingest). Kerry supplies those links from the admin console or flags them no-website.",
    ],
  },
  {
    version: "2.69.5",
    date: "2026-07-11",
    changes: [
      "GG HISTORY: THE CHAMPIONSHIP SERIES IS COMPLETE -- tgf-champ20 through tgf-champ25 all alive, every TGF CHAMPIONSHIP 2020-2025 with Fellowship Cup, points/Players Cup, match play, money, and event-results pages. Plus tgf-trinity (2022 Trinity River Cup, the DFW-v-Houston Ryder Cup event). Registry final for this session: 48 live portals.",
      "Remaining gaps after exhausting every naming pattern: Lone Star Cup 2023 + 2024, the Hill Country family (Cups 2020-2022, TGF Hill Country 2022, Matches 2023/2024), Red Blue Challenge, and Hill Country Two Man x2 -- these need website links from Kerry's GG admin console (or a no-website flag). The 2024-25 per-course Two Man Tour events likely aggregate inside tgf-twomantour, to be verified at ingest.",
    ],
  },
  {
    version: "2.69.4",
    date: "2026-07-11",
    changes: [
      "GG HISTORY: SIX MORE PORTALS RECOVERED via Kerry's tgf-lonestarcup25 link, which revealed the TWO-DIGIT year suffix pattern the earlier guesses missed: 2021/2022/2025 Lone Star Cups, the 2025 TGF CHAMPIONSHIP (tgf-champ25 -- 'champ', not 'championship'), and Road Trips 2024/2025. Registry now 42 live portals. The champ25 portal cross-links a 2024 TGF CHAMPIONSHIP page, so that data exists reachable somewhere; a final derived-pattern sweep (champ20-24, LSC 23/24 variants, Trinity River, Hill Country Cup, Red Blue) is underway.",
    ],
  },
  {
    version: "2.69.3",
    date: "2026-07-11",
    changes: [
      "GG HISTORY BRAND RULINGS (Kerry, in-session): Two Man Challenge Series 2020 is TGF (pre-Two Man Tour era); all Road Trips are TGF, with the 2024 Road Trip a hybrid (TGF league + one Two Man Tour event tagged inside); Hill Country Two Man Challenge and Red Blue Challenge are TGF; Trinity River Cup 2022 is TGF (a DFW-vs-Houston Ryder-Cup-style event); Rough Water Cup is non-TGF and joins the excluded list.",
      "TWO MAN TOUR SEPARATION SEMANTICS: the Tour is a separate brand kept for a future Two Man Tour partner build -- its data gets ingested and identity-linked but is TOTALLY separate from TGF today. The proposed gg_history_* schema gains brand as a first-class column (portals registry NOT NULL + per-event override for hybrids) acting as a hard filter: Two Man Tour rows are excluded from TGF career stats, the trophy case, and member-facing Spotlight surfaces.",
    ],
  },
  {
    version: "2.69.2",
    date: "2026-07-11",
    changes: [
      "GG HISTORY MASTER LIST RECONCILED: Kerry supplied the authoritative league list from the GG admin console (14 screenshots -- 75 archived + 4 current leagues), revealing ~40 leagues the public-portal walk couldn't see: TGF CHAMPIONSHIP 2020-2025, Lone Star Cup 2021-2025, Hill Country Cups, Trinity River Cup, Red Blue Challenge, Rough Water Cup, Road Trips 2020-2025, the Two Man brand's full history, and two Non-TGF Events leagues. All banked in docs/claude/gg-history.md.",
      "Pattern-guess sweeps recovered SEVEN more live portals (tgf-roadtrip2020/2021/2022, tgf-twoman2020/2021/2022, tgf-twomantour) -- the walkable set is now 36 portals. A second 17-candidate sweep came back all dead, so the guessable subdomain universe is exhausted: the remaining missing leagues (championships and Lone Star Cups above all) need their website links pulled from the GG admin console, or have no public website at all.",
      "SCOPE RULING (Kerry, in-session): ingest covers TGF + Two Man Tour; the two Non-TGF Events leagues are excluded.",
    ],
  },
  {
    version: "2.69.1",
    date: "2026-07-11",
    changes: [
      "GG HISTORY INVENTORY COMPLETE (mailbox #100/#102/#105/#106 -- the Kerry-approved plan's phase 1): an automated walker probed every archive portal and the coverage map is banked in docs/claude/gg-history.md. 29 portals total: SA 2016-2025, Austin 2019-2025, DFW 2020-2024 and Houston 2021-2024 (the closed chapters keep per-year subdomains -- all alive -- while their main tgf-dfw/tgf-houston portals are dead corporate redirects), plus the three one-offs (Hill Country, Two Man, Road Trip 2023). Every page id for every season's results, standings, match play, money, and monthly races is catalogued.",
      "THE ACCESS RECIPE IS PROVEN, overturning the walkers' first-pass 'JS-widget, unreachable' verdict: each portal's league_id sits in a hidden input in any page's HTML body, and the widget routes (/leagues/<id>/widgets/season_points[_v2]?page_id=...) plus the /v2tournaments XHR partials serve full tables server-side. Demonstrated end-to-end on the OLDEST data (the complete 66-player 2016 SA points race, with career purse figures) and the NEWEST closed-chapter data (DFW 2024 event results with machine-readable member ids). Name format across eras is 'LASTNAME, First'; guests render mixed-case.",
      "Proposed gg_history_* ingest schema (portals/pages/standings/events/results/name-links, customer_id FKs per rule 6, raw snapshots into the existing gg_raw_archive before any parsing) is documented in gg-history.md and posted to the mailbox for Kerry's rule-3b ratification. NO TABLES SHIP in this release -- ingest starts only after ratification.",
    ],
  },
  {
    version: "2.69.0",
    date: "2026-07-10",
    changes: [
      "SPOTLIGHT REBUILT DENSE per the approved design handoff (design-claude spotlight-mobile-scoring-071026, CA GO mailbox #111 -- Kerry had flagged the first cut as far too bulky): hero collapses to a single band (name + chapter/member chips left, big handicap INDEX right, Lone Star Cup projection as one line under a divider), the three stat cards become one 3-across strip (EVENTS / CONTESTS / WON in green), WHERE THEY STAND collapses to one card of compact rows (rank-of-field block left, race + inline meta, IN/NOT IN micro-pill; Players Cup rank tinted burnt orange), winnings are single-line rows with right-aligned green amounts, and the search intro copy disappears once a player is loaded. Roughly half the scroll on a phone; desktop shows the same dense column pending design-claude's desktop pass.",
      "SCORING card is LIVE with real numbers (bound to the v2.68.0 scoring payload): PAR 3/4/5 stroke-average tiles, the 9-hole average as the PRIMARY line (18-hole demoted to a muted conditional line, hidden when a player has no 18-hole rounds -- the common case), and the EAG/BIRD/PAR/BOG/OTHER distribution strip with zero-count tiles muted. Trend arrows are the EARNED state: they appear only at 15+ tracked rounds (last-10 vs prior-10), green down = improving, red up = worse; under 15 rounds the card renders clean numbers -- designed as the default look, not a stripped one. The scope cue reads 'last N rounds' honestly.",
      "Verified in-browser on a seeded fixture: an improving 20-round player shows all-green arrows and the exact distribution; an 8-round player gets the no-arrow default with an honest 'last 8 rounds' cue; a player with no tracked rounds gets no SCORING card at all; no horizontal overflow at 390px.",
    ],
  },
  {
    version: "2.68.0",
    date: "2026-07-10",
    changes: [
      "SPOTLIGHT SCORING AGGREGATE (mailbox #103/#104 -- design-claude's mobile density pass added a SCORING card on Kerry's request and asked whether the numbers are derivable; they are, and now they're REAL): the spotlight payload carries a scoring block computed from the player's last 20 tracked rounds -- par-3/4/5 stroke averages with trend arrows, an eagle/birdie/par/bogey/other distribution, and separate 9-hole and 18-hole average-gross lines (TGF rounds are mostly 9-hole, so a single '18-hole average' would have been mostly synthetic). Par comes from course_tee_holes via each round's tee.",
      "TREND DEFINITION (correcting the prototype's assumption): last 10 rounds vs the 10 before -- NOT last-20-vs-previous-20, which needs a 40-round history nobody has this season (the most active players hold ~21). Trends suppress entirely until a player has 15+ rounds (5+ in the prior window) so early-season arrows can't mislead; negative = improving. Windows deepen automatically once the GG history ingest lands.",
      "Verified with a synthetic 20-round fixture: par-type averages exact, distribution counts exact, trend arrows appear only when the prior window exists and read +1.0 for a player who went from all-pars to all-bogeys.",
      "GG HISTORY recon extended per mailbox #106: all seven Austin archives (tgf-austin2019 through 2025) probed ALIVE and public, completing the inventory target list -- SA 2016-2025, Austin 2019-2025, DFW, Houston, plus three one-off portals discovered in the 2023 footer (Hill Country, Two Man Challenge, 2023 Road Trip) for the ONE-OFFS category Kerry added to scope.",
    ],
  },
  {
    version: "2.67.1",
    date: "2026-07-10",
    changes: [
      "SPOTLIGHT 'WHAT'S IN REACH' DATA (mailbox #99 item 1, Kerry-RATIFIED -- backend prep; the visual treatment waits for design-claude's pass per the ratified sequencing): every race entry in the spotlight payload now carries in_reach = points to the place above, what the player would cash if the season ended today (server-side mirror of the CONTESTS payout walk -- enrolled-only, tie groups split combined places cent-exact, Players Cup champion bonus + per-flight 1st/2nd stacking), the next payout rung up, and the live pot.",
      "race_pots added to the spotlight payload: label + live pot + buy-in count for EVERY race and The Fellowship Cup, whether or not the player is in it -- the data feed for #99's 'NOT ENTERED doorway' and 'empty states as invitations' items.",
      "Verified on the synthetic fixture: mid-pack player shows the exact gap and last-place-money rung; the race leader shows 1st-place money and no rung above; tied cup leaders split 1st+2nd combined with the outright-1st amount as their next rung.",
    ],
  },
  {
    version: "2.67.0",
    date: "2026-07-10",
    changes: [
      "PLAYER SPOTLIGHT (Kerry-directed, ADMIN PREVIEW v1 -- deliberately NOT member-visible yet): a new /spotlight page where you type any player's name and pull up their story -- name/chapter/member badges, current handicap index (18- and 9-hole), headline stat tiles (events played, contests entered, season winnings), a WHERE THEY STAND card for every points race they appear in (rank of field, points, events, flight, projected reset, BOUGHT IN pill), fall buy-in cards, a City Match Play card (pool + W-L-D record + Stableford), a projected Lone Star Cup seat/alternate chip, and their five most recent winnings. Search is a live typeahead over member names; ?player=<id> deep links restore on refresh.",
      "GATING: the page and both APIs (/api/spotlight/search, /api/spotlight/player) are ADMIN-ONLY while Kerry iterates the design with design-claude and platform-claude. The payloads are PII-FREE BY DESIGN (name, chapter, and competitive data only -- no emails/phones/addresses/DOB), so opening it to the pinless member tier later is a role-string change, not a data audit. The page carries an amber 'ADMIN PREVIEW - not member-visible yet' chip and, temporarily, the admin subnav (comes off when it goes member-facing).",
      "Data is composed entirely from existing engines: the persisted points-race snapshots, The Fellowship Cup projection, cmp match-play standings, handicap_player_links, get_customer_winnings, and the v2.66.0 Lone Star Cup projection. Monthly standing is deliberately deferred (its data path does live GG page walks -- too heavy per player) and is on the iteration list.",
      "Admin subnav across all admin pages gains a SPOTLIGHT link (after Traffic).",
    ],
  },
  {
    version: "2.66.0",
    date: "2026-07-10",
    changes: [
      "THE LONE STAR CUP arrives on the member Season Contests page (Kerry-directed concept, ratified spec: mailbox #85-#88): a third top-level tab -- POINTS RACES | MATCH PLAY | LONE STAR CUP -- explaining the event, the 12-seat qualification structure (1 Captain = City NET Champion, 6 from The Fellowship Cup final standings top-6-per-chapter, 1 City Match Play Champion, 4 from The Players Cup top-4-per-chapter), and LIVE PROJECTED ROSTERS per chapter computed from current standings, in the same spirit as the projected payouts.",
      "Selection rules implemented exactly as ratified: only bought-in players hold seats; double-qualifiers take the seat where they placed HIGHER by absolute place (#86 interim -- Kerry's proportional-valuation tweak stays open until he rules); vacated or unfillable seats fill from the unified per-chapter ALTERNATES POOL ranked by percentile finish (place / field size) with events-played tiebreak (#87); the Match Play seat shows TO BE DECIDED until the knockout bracket crowns a champion (Kerry, no speculative seeding projection). Pool-filled seats wear a small POOL chip; each card lists its NEXT MEN UP alternates with their best finish context.",
      "Engine: get_lone_star_cup_projection() composes the existing City NET / Fellowship Cup / Players Cup standings plus cmp_bracket state -- no new data sources; GET /api/season-contests/lone-star-cup serves the member tier. Verified against a synthetic 22-player fixture: captain precedence over own cup seat, no double-seating, standings-order seats, percentile pool fill, alternates ordering, small-field exhaustion (open seats stay TBD).",
      "This is the PROJECTION HALF only: actual selection-day rosters with Kerry's manual adds/overrides at every level (#87 hard requirement -- guests and past members exist outside contest standings) is a separate admin feature to build before selection day, post-Championships.",
      "The three member top tabs now fit a 390px phone without scrolling (tighter tab padding under 420px).",
      "Nomenclature audit per mailbox #86 (capital-The is part of the Cup names): live member surfaces checked; the one non-compliant string -- the transient 'Building Fellowship Cup projection' loading note -- now reads 'Building The Fellowship Cup projection'. Race chips, structure notes, and the new popups already complied.",
    ],
  },
  {
    version: "2.65.0",
    date: "2026-07-10",
    changes: [
      "HOW IT WORKS popups rebuilt to the ratified design handoff (design-claude hiw-popup-final-071026, Kerry-RATIFIED per view, mailbox #95): every contest now has its own popup -- City NET, The Fellowship Cup, The Players Cup, City Match Play, Monthly Points Race, Fall Points Race -- rendered data-driven from one modal template. Each opens with the game name in TGF orange, an at-a-glance chip row, THE RACE / THE MONEY / THE POINTS scan blocks (Match Play: THE FORMAT / THE MONEY / THE SEEDING), the ratified per-hole points chart (net REG|CHAMP; gross REG-only with the aces-only championship bonus in the footnote per ruling R4), and a muted footnote.",
      "EXAMPLE SCORECARD on every points contest (ruling R3): a worked 9-hole example -- PAR / GROSS SCORE / NET SCORE / NET PTS for the net races (stroke dots included), GROSS-only for The Players Cup -- with red circles under par, gray squares over par, and doubled rings at two-or-more either way. Both examples verified hole-by-hole against the ratified schedules (net example totals 8 points, gross 19). Match Play carries neither chart nor scorecard: matches are head-to-head.",
      "MATCH PLAY gets its own HOW IT WORKS button for the first time (top-right of the Match Play page, both viewports). The shared modal is hoisted to <body> at boot so it renders over the Match Play tab (a fixed element inside the hidden points-race section painted nothing), and reopened popups now start scrolled to the top instead of wherever the last reader left off.",
      "PHONES present the popup as a bottom sheet (handoff view 1g): it rises from the bottom edge with rounded top corners and a full-width GOT IT button; desktop keeps the centered 600px card.",
      "POT, not PURSE -- everywhere (Kerry-RATIFIED mailbox #90; 'rename everywhere' confirmed today): the standings strip pill reads POT, the Monthly standings column header is POT, all popup / pay-note / roster copy says pot, and the admin TGF Payouts + Events financial cards read Total Pot. Internal field names (total_purse etc.) are unchanged -- display text only.",
      "Monthly calendar rule banked as ratified (mailbox #95 item 2): the Monthly Points Race runs March through October with NO race in August (Championship month); the Monthly popup states it and game-engine.md records it.",
    ],
  },
  {
    version: "2.64.0",
    date: "2026-07-10",
    changes: [
      "THE MCP HAS A CLOCK (Kerry via platform-claude, mailbox #81): new get_current_time tool returns Central time (ISO + friendly like 'Friday, July 10, 2026 - 1:45 PM CDT'), UTC equivalent, and day of week; every read_platform_dialogue response now leads with server_time_local and an explicit note that post timestamps are UTC -- so no Claude misreads UTC as local time again.",
      "FALL How It Works popup restructured to Kerry's ratified copy (mailbox #76): singular title, at-a-glance chip row (STARTS SAT, AUG 29 / BEST 6 + FALL CHAMPIONSHIP / $40 TO THE PURSE), THE RACE / THE MONEY / THE POINTS scan blocks in Bitter, chart unchanged, standalone disclaimer demoted to a muted footnote.",
      "ACCURACY correction (Kerry, applies everywhere): points CAN go negative on a hole -- the zero floor applies to the EVENT TOTAL only. All three popups now say it right; no 'never below zero' phrasing remains.",
    ],
  },
  {
    version: "2.63.0",
    date: "2026-07-10",
    changes: [
      "FALL ENROLLMENT IS AUTOMATIC (Kerry: 'It's already being purchased under the umbrella SEASON CONTESTS. You need to account for it... and set up the site to populate immediately upon receipt of new orders just like everything else.'). The parser now extracts the FALL NET option from SEASON CONTESTS order emails (new fall_net_points_race field), and the season-contest sync maps it straight to the fall race ('2026 Fall'), chapter from the buyer's profile -- the fall pages populate within the normal 5-minute inbox cycle, no manual step. The order math checks out against the ratified money model: Adam's $140 = $90 NET bundle + $50 fall; Luke's $190 = $90 + $50 Players Cup + $50 fall.",
      "Audit re-extract force-updates the fall flag, so today's two fall orders backfill by re-extracting them once -- done as part of this release.",
      "Adam Baker is enrolled in SA FALL NET (this morning's order R967407420, canonical profile -- his GoDaddy 'James Baker' alias resolved correctly).",
    ],
  },
  {
    version: "2.62.1",
    date: "2026-07-10",
    changes: [
      "REFRESH IN PLACE (Kerry): the selected race now lives in the page URL (#race=fall_sa etc.), so refreshing SA FALL NET reloads SA FALL NET instead of snapping back to SAN ANTONIO NET. Match Play and Enrollment tabs survive refresh the same way, and race links can now be shared directly.",
      "TRAFFIC self-exclusion (Kerry): open /member/contests#notrack once on each device you test from and that browser stops counting (the flag lives on the device -- no IP addresses are stored, by design; #track re-enables). Instructions are on the TRAFFIC page, and a one-shot scoring-traffic-reset command flushes the launch-day testing counts.",
      "Bridge command args actually parse now: the dispatcher splits 'command:arg' before the handlers see it, so the parameterized fall-enroll (and the new raw-order reader) matched nothing -- running fall-enroll with an argument silently re-ran the two-person seed instead of enrolling the requested customer. This is why Adam Baker hadn't appeared on SA FALL NET; he's enrolled right after this deploys.",
    ],
  },
  {
    version: "2.62.0",
    date: "2026-07-10",
    changes: [
      "MEMBER TRAFFIC tracking (Kerry): the pinless member pages now count page opens and button/link clicks -- anonymously (no names, no identifiers, just the event, the page, and the control's label). New admin-only TRAFFIC page in the admin sub-nav: opens/clicks for the last 24h / 7d / 30d, a 14-day daily series, per-page totals, and the top-25 tapped controls, so you can see what members actually use.",
      "Fall enrollment bridge is parameterized: scoring-fall-enroll:<customer_id>[:<order_item>] enrolls any customer into the fall NET from their canonical profile -- no more code change per signup. Context (Kerry's Adam Baker check): his SEASON CONTESTS order this morning auto-enrolled him in the spring NET as expected, but fall has no shop product yet, so nothing auto-writes fall enrollments -- they stay manual via this command until the fall products + sync mapping exist.",
    ],
  },
  {
    version: "2.61.1",
    date: "2026-07-10",
    changes: [
      "The Monthly How It Works chart drops its CHAMP column (Kerry): championship values only exist at the August championships, and Monthly doesn't run in August -- so they can never apply to a monthly race. The season and fall popups keep REG | CHAMP.",
    ],
  },
  {
    version: "2.61.0",
    date: "2026-07-10",
    changes: [
      "HOW IT WORKS popups are now race-specific (Kerry): the MONTHLY popup says only what Monthly is (auto-entry, all points count, $1/member award, ties split) with just the NET chart; the FALL popup covers only the standalone best-6 + Fall Championship race, buy-in/purse rules, and the NET chart; the season races keep the full best-10 / reset / TGF Championship explanation with both charts (its Monthly paragraph and fall sentence removed). Each popup's title names its race. Roughly half the text per popup.",
    ],
  },
  {
    version: "2.60.5",
    date: "2026-07-10",
    changes: [
      "The ENTER SEASON CONTESTS banner and the POINTS RACES | MATCH PLAY sub-nav are PINNED under the top nav while scrolling (Kerry) -- the whole header stack (dark nav / orange banner / tabs) stays put as the standings scroll beneath it. Offsets computed from live heights so member/staff/desktop bars all stack flush; the race dropdown still anchors right under the pinned tabs.",
    ],
  },
  {
    version: "2.60.4",
    date: "2026-07-10",
    changes: [
      "The fall pages' inline sign-up button reads ENTER POINTS RACE (Kerry) -- the page is already about one specific race, so the generic ENTER SEASON CONTESTS label (which stays on the top banner) was redundant there. Same shop link.",
    ],
  },
  {
    version: "2.60.3",
    date: "2026-07-10",
    changes: [
      "Enrolled-players lists hidden on all IN-PROGRESS race pages (Kerry): the standings already mark buy-in on every row (green + check), so the bottom roster was redundant on the live NETs, the cups, and Monthly (whose explainer lives in How It Works now). The list remains only on the upcoming FALL pages, where it's the whole show until play begins.",
    ],
  },
  {
    version: "2.60.2",
    date: "2026-07-10",
    changes: [
      "Fall races are STANDALONE (Kerry): best 6 + the Fall Championship decides them outright -- no points reset and no connection to the cups or the TGF Championship. The fall page blurbs, the How It Works popup, and the repo docs all say so now (the earlier wording could be read as a shorter version of the four-step structure).",
      "TGF-orange dividers in the race dropdown (Kerry): thin orange rules separate the four groups -- city NETs | the two cups | Monthly | fall races -- in the POINTS RACES tab menu.",
    ],
  },
  {
    version: "2.60.1",
    date: "2026-07-10",
    changes: [
      "Fall races moved BELOW Monthly in the race selector and recolored (Kerry): burnt-orange 'upcoming' chips -- soft tint idle, solid burnt orange selected -- in both the desktop chip row and the mobile tab menu.",
      "Fall format corrected per Kerry: the fall season total is your BEST 6 event totals + the FALL CHAMPIONSHIP (not best 10). The fall pages carry a 'Best 6 + Fall Championship' chip next to the start date, and the How It Works popup notes the fall exception.",
      "Fall pages now list ENROLLED PLAYERS live from the enrollment database (season '2026 Fall', green bought-in pills with a running count). New one-shot scoring-fall-enroll bridge command seeds the first two SA Fall NET enrollments: Luke Mazanec (his SEASON CONTESTS order from this morning, R170271926) and Kerry Niester -- manually_enrolled so nothing auto-cleans them before the fall products exist.",
    ],
  },
  {
    version: "2.60.0",
    date: "2026-07-10",
    changes: [
      "FALL POINTS NET pages (Kerry): SA FALL NET and AUSTIN FALL NET join the race selector (desktop chips + the mobile POINTS RACES tab menu), each with its own page announcing 'STARTS SATURDAY, AUGUST 29' in the status-chip style, a short what-it-is blurb, and a big ENTER SEASON CONTESTS pill right in the page (the top banner is hidden on desktop member view, so the inline button covers every device). Standings, purse, and enrolled players light up here once the fall races begin; the phase chip, payout strip, and refresh button stay hidden until then.",
    ],
  },
  {
    version: "2.59.4",
    date: "2026-07-10",
    changes: [
      "HOW IT WORKS button restyled (Kerry): solid TGF orange pill with white uppercase Bitter lettering, matching the app's primary-pill convention -- was a gray ghost outline.",
    ],
  },
  {
    version: "2.59.3",
    date: "2026-07-10",
    changes: [
      "FIX: the How It Works popup wasn't scrolling on phones (Kerry) -- iOS was handing the swipe to the page BEHIND the popup, so the popup looked frozen. The page body now locks in place while the popup is open (position:fixed at the current scroll spot, restored on close) and the popup contains its own overscroll.",
    ],
  },
  {
    version: "2.59.2",
    date: "2026-07-10",
    changes: [
      "How It Works opener wording (Kerry): 'Earn points ON every hole you play' (was 'for').",
    ],
  },
  {
    version: "2.59.1",
    date: "2026-07-10",
    changes: [
      "CHAMP columns in the How It Works point charts (Kerry): both Stableford tables now show REG and CHAMP values side by side, per the ratified 2026-07-06 championship schedule -- NET gets +1 in every category (Triple 0 / Bogey +1 / Par +2 / Birdie +3 / Eagle +4 / Double Eagle +5 / Ace +9); GROSS adds +1 to the hole-in-one bonus only (8 -> 9, so a championship par-3 ace beats the eagle). The popup copy states these apply to BOTH the City Championship and the TGF Championship rounds.",
      "The app icon is now the official TGF mark (Kerry): white GF-circle on the #1B1B1B brand tile, replacing the generic dark 'T' on home screens and the old blue golf-flag favicon in browser tabs. New 512/192/180 PNGs + rebuilt icon.svg; manifest points at them for Android installs; the three admin pages that were missing the apple-touch-icon link got it. Anyone with the old icon on their phone should remove it and re-add via Share -> Add to Home Screen -- iOS caches the icon at add time.",
      "How It Works opener rewritten to Kerry's line: 'Earn points for every hole you play.'",
    ],
  },
  {
    version: "2.59.0",
    date: "2026-07-10",
    changes: [
      "Projected TIES split the combined money of the tied places (Kerry; ratified universal rule): two bought-in players tied at T2 each show half of 2nd + 3rd money (e.g. $190 + $136.80 -> PROJECTED: $163.40 each), and the ladder resumes at the right place below them. Applies to the city ladders, the Fellowship Cup, and the Players Cup (tied Champions split the 10% bonus; ties atop a flight split the 67/33 money). Cent-exact largest-remainder splits.",
      "HOW IT WORKS popup (Kerry): a '? How it works' pill next to the phase chip opens a popup with the full explanation -- how points are earned (Stableford, net vs gross), best 10 + City Championship, the POINTS RESET -> TGF CHAMPIONSHIP structure, Monthly's rules, and buy-in/projected-payout mechanics -- plus the NET and GROSS Stableford value charts, which MOVED here from the bottom of the page. The page is shorter and the reference is there only for people who need it. Esc / X / tap-outside closes it.",
      "The stale 'Score entry and leaderboards coming soon' note under the enrolled roster is gone -- leaderboards have been live for weeks.",
      "The Monthly IN PROGRESS chip moved BELOW the month tabs (Kerry) so the tab row stays put when switching between open and completed months.",
    ],
  },
  {
    version: "2.58.3",
    date: "2026-07-10",
    changes: [
      "ROUNDS column data truly centered this time (Kerry): the real culprit was the table's auto-layout stretching the numeric columns wide on phones, leaving centered numbers floating oddly between the divider rules. The PLAYER column now absorbs ALL the slack width (width:99% on its header), so PTS / PROJ RESET / R / IN collapse snug around their content and the numbers sit visibly centered between their rules. Same fix on the Fellowship Cup table.",
      "Open monthly races show an 'IN PROGRESS' chip up top (Kerry) -- e.g. 'JULY - IN PROGRESS' in the burnt-orange chip style above the month tabs. Completed months show nothing extra; their trophy rows already mark the winners.",
    ],
  },
  {
    version: "2.58.2",
    date: "2026-07-10",
    changes: [
      "Projected money moved BELOW the player's name as a small green 'PROJECTED: $xxx' line (Kerry) -- the inline pill was overflowing the name column into the chapter/points columns on phones (the Players Cup badge sat on top of 'AUS 188'). Block line under the name can't collide with anything.",
    ],
  },
  {
    version: "2.58.1",
    date: "2026-07-10",
    changes: [
      "THE FELLOWSHIP CUP and THE PLAYERS CUP now explain the full season structure (Kerry): a note under the purse strip states that regular-season standings count best 10 + City Championship, then the POINTS RESET (the PROJ RESET column) condenses the field onto one master ladder after the City Championships -- those totals are the starting point for the TGF CHAMPIONSHIP, whose final round decides the cup. City NET races and Monthly don't carry the note.",
      "The (PROJ) eyebrow over the RESET column is TGF orange (Kerry) -- it had been silently rendered gray since v2.56.0 because the header restyle's gray-span rule outranked its inline amber; the new rule out-specifics it.",
      "ROUNDS column data centered under its header (Kerry) -- th and td now carry a hard-centering class so no table restyle can knock it loose.",
    ],
  },
  {
    version: "2.58.0",
    date: "2026-07-10",
    changes: [
      "PROJECTED PAYOUTS on the points races (Kerry): every race now shows its purse and place money computed live from the current buy-in count, per the ratified TGF Season Contest Payouts v1.0 rules. A PURSE pill + per-place chips sit under the standings heading (SA NET today: $720 paying 5 places $252/$180/$129.60/$86.40/$72), and the players who would cash if the season ended today wear a green dollar badge on their row. Only bought-in players are eligible -- the money visibly flows PAST non-enrolled rows to the next bought-in player, which is the whole sales pitch for the ENTER SEASON CONTESTS banner above it.",
      "New pure payout engine email_parser/season_payouts.py (rules-as-data, Platform-portable) with parity tests against every worked matrix in the ratified spec: City Net places curve 30%@10->20%@60 with the 2-7 place ladder families; THE FELLOWSHIP CUP 45%-flat first place until $1,008 at N=56 then +$8 of every new $40 buy-in (the winner-growth engine), remainder ladders per the proposed defaults; THE PLAYERS CUP 10% Champion off top + 90% split across the 4 fixed flights at 67/33 (the Champion's badge stacks with their flight win).",
      "THE FELLOWSHIP CUP purse counts every NET-bundle buy-in across both chapters ($40 of each $90 bundle; the other $40 funds the buyer's City Net race). Its summary line now leads with the same green bought-in count as the races. Monthly shows no payout strip -- its purse is the $1/member award, already explained on the tab.",
      "Flagged for Kerry per spec section 8: Cup remainder ladders are the spec's proposed defaults; ties currently pay down the ladder sequentially (no split display); City ladder capped at 7 places / Cup at 5 until the ladder families are extended.",
    ],
  },
  {
    version: "2.57.9",
    date: "2026-07-10",
    changes: [
      "Color semantics on the standings header (Kerry): green now means BOUGHT IN, nothing else. The 'BEST 10 + CITY CHAMPIONSHIP' phase chip switched from green to a burnt-orange tint (#FDF0E6 / #BF5700) so it can't be read as a buy-in signal, and the '18 of 73 currently bought in' lead is highlighted in the exact green of the bought-in rows (#bbf7d0) so the number and the rows visibly belong together. Staff diagnostics after the lead stay plain muted text.",
    ],
  },
  {
    version: "2.57.8",
    date: "2026-07-10",
    changes: [
      "Phase chip wording matches the ratified season spec (Kerry): 'REGULAR SEASON - BEST 10 + CITY CHAMPIONSHIP' -- the season total is the best 10 event totals PLUS the City Championship on top (mailbox #71), so the chip no longer undersells it as 'best 10 count'. Still hidden on the Monthly race, which is uncapped.",
      "Standings subtext reduced to '18 of 73 currently bought in' (Kerry) -- the ranked-players sentence, non-members-hidden note, reset coefficient, and Golf Genius timestamp are gone for members and view-only. Manager/admin still see all of those diagnostics after the short lead (they run the refreshes); the summary re-renders when the role check lands so staff never get stuck with the short line. Applies to every race through the shared renderer -- Austin NET included.",
    ],
  },
  {
    version: "2.57.7",
    date: "2026-07-10",
    changes: [
      "Contest headings on the CONTESTS page are now prominent (Kerry): the standings title is just the contest name -- 'AUSTIN NET 2026', 'THE PLAYERS CUP 2026', 'THE FELLOWSHIP CUP' -- in large uppercase Bitter on its own line, with the phase chip and staff refresh button wrapping underneath. The '-- Standings & Buy-in' / '-- Projected Points Reset' suffixes are gone; now that the race dropdown carries the names, the heading doesn't need to explain the table.",
    ],
  },
  {
    version: "2.57.6",
    date: "2026-07-10",
    changes: [
      "FIX: the POINTS RACES tab menu shipped in v2.57.5 opened but was invisible on iPhones (Kerry) -- the menu was parented inside the sideways-scrolling tab strip, whose overflow clips absolutely-positioned children on iOS Safari. Menus now anchor to a new un-clipped wrapper around the strip.",
      "MATCH PLAY gets the same treatment (Kerry): on phones, tapping the tab drops an Austin / San Antonio chapter menu right from the tab; the chapter tab line is gone on mobile (members lose the whole line; staff keep the season input and + Add Pool).",
      "ENTER SEASON CONTESTS is now a full-page-width banner attached directly to the dark nav with no white space above it (Kerry) -- it moved out of the page body, dropping the pill margins and rounded corners. Desktop member view still carries the CTA as the nav pill instead of the banner.",
    ],
  },
  {
    version: "2.57.5",
    date: "2026-07-10",
    changes: [
      "POINTS RACES tab is the race selector on phones (Kerry): tapping the tab drops the race menu right from the tab bar -- the separate selector row below is gone on mobile. Picking a race switches the standings and closes the menu; tapping the tab again toggles it; switching to MATCH PLAY or ENROLLMENT closes it. The active tab wears a small orange down-caret so the drop-down is discoverable. Desktop keeps the race chip row unchanged.",
    ],
  },
  {
    version: "2.57.4",
    date: "2026-07-10",
    changes: [
      "Member mobile top bar upsized (Kerry): 64px tall with a 34px TGF mark and 13px tabs, and the first tab reads the full SEASON CONTESTS instead of SEASON -- two tabs leave plenty of room. Staff mobile bar (hamburger layout) unchanged.",
    ],
  },
  {
    version: "2.57.3",
    date: "2026-07-10",
    changes: [
      "Member round history drops the COUNT column on phones (Kerry) -- the green row treatment already marks counting rounds, so the column was redundant; Date / Course / Gross / Diff / Index all fit on screen now. The legend reads 'green row' on mobile. Desktop keeps the full Counting column with its checkmarks.",
    ],
  },
  {
    version: "2.57.2",
    date: "2026-07-10",
    changes: [
      "Course pin corrections from the first live run's report: 'Silverhorn Golf Club of Texas' had been caught by the Golf Club of Texas pattern (it now correctly reads Silverhorn -- the real GC of Texas keeps its pin), and the two Austin Riverside rows are now 'Riverside | ATX' instead of '| SA'.",
      "Pins now also CREATE course rows for round-history course strings that match a pin but had no database row yet -- the Hyatt Hill Country nines, Olympia Hills, and Black Jack's get exact short names on phones instead of the derivation fallback.",
      "Archived courses no longer appear in the EVENTS course autocomplete -- the /courses editor's archive toggle now actually controls the picker (the datalist and the editor read the same course database).",
    ],
  },
  {
    version: "2.57.1",
    date: "2026-07-10",
    changes: [
      "Kerry's ratified course short names applied to the live database via the scoring-course-short-pins bridge command (one-shot -- /courses UI edits afterwards always stick): TPC | Oaks, TPC | Canyons, Hill Country | Oaks/Creeks/Lakes, Comanche | Creeks/Hills/Valley, Silverhorn, Olympia Hills, Black Jack's, La Cantera | Resort, Riverside | SA, Brackenridge, GC of Texas.",
    ],
  },
  {
    version: "2.57.0",
    date: "2026-07-10",
    changes: [
      "COURSE DATABASE EDITOR (Kerry): new admin page at /courses (COURSES in the admin sub-nav) -- every course in the database in one editable grid: Short Name, Chapter, City, State, and Status (archived courses dim and hide from the default list), plus read-only tee and imported-round counts. Edit a cell and a SAVE pill appears on the row; saves are per-row and instant.",
      "Short names you edit here now flow to the phone displays: the handicaps rounds payload carries the course's DB short_name (exact name match), with the automatic derivation as fallback for course names not yet in the database.",
      "Course NAMES stay read-only in the grid -- imports and backfills join on them, so renames need Claude (alias-aware). Search and a show-archived toggle included.",
    ],
  },
  {
    version: "2.56.5",
    date: "2026-07-10",
    changes: [
      "Member round-history headers compact on phones (Kerry): DIFFERENTIAL -> DIFF, COUNTING -> COUNT, RUNNING INDEX -> INDEX -- the counting checkmarks now fit on screen at 390px without scrolling. Desktop keeps the full labels.",
    ],
  },
  {
    version: "2.56.4",
    date: "2026-07-10",
    changes: [
      "Mobile dates switch to m/d slashes (Kerry) -- matching the points-race convention app-wide.",
      "COURSE SHORT NAMES (Kerry): the course database gains a short_name column, auto-derived at boot for existing rows (only where empty, so manual edits stick) by stripping venue boilerplate -- 'The Quarry Golf Club' -> 'The Quarry', 'The Club at Comanche Trace' -> 'Comanche Trace', 'Hyatt Hill Country' -> 'Hill Country', 'Flying L Ranch Resort' -> 'Flying L'. Phones show short names in the Handicaps round history and the Contests round lists; desktop keeps full names.",
      "Tightened mobile columns in the round history (Kerry: 'date to course space is massive') -- the desktop min-widths and padding no longer apply under 768px, so DATE hugs COURSE and more columns fit before scrolling.",
    ],
  },
  {
    version: "2.56.3",
    date: "2026-07-10",
    changes: [
      "Handicaps dates compact to m-d on phones (Kerry): round-history rows and the mobile card 'Last:' line read 7-1 instead of 2026-07-01 at mobile widths (member and admin alike); desktop keeps the full date.",
    ],
  },
  {
    version: "2.56.2",
    date: "2026-07-10",
    changes: [
      "FIXED: filter pills dead on the member Handicaps page (Kerry's screenshot). The nav-shell release moved the ops buttons out of the member DOM, but the page's init script still bound handlers to them unguarded -- the resulting error silently killed every binding after it, including the chapter and MEMBERS|EVERYONE pills and the sort control. All bindings are now null-safe.",
      "FIXED: a filter that matched nobody left stale player cards on the mobile list (the empty-state path cleared only the desktop table).",
      "Member round history now wears the ratified view-1a treatment (Kerry's other screenshot showed the old 9-column table overflowing the phone): the lean six columns -- Date | Course | Gross | Differential | Counting | Running Index -- with counting rounds green-barred and checked, the red dashed LOOKBACK CUTOFF rule, dimmed excluded rounds, and the explanatory legend. Admin/manager keep the full table; both get Bitter hairline headers.",
    ],
  },
  {
    version: "2.56.1",
    date: "2026-07-10",
    changes: [
      "SEASON CONTESTS phase B: the player drill-down wears the ratified 1g treatment -- POINTS COUNTED band in TGF black with the (Best 10 + City Championship) note, POINTS NOT COUNTED in warm gray, CITY CHAMPIONSHIP row on the warm paper tint, Bitter hairline table headers with soft dividers, and the compact mobile size raised to the 12.5px floor. Scorecards: PAR/YARDS/HCP rows in info blue, points rows on a blue-tinted band, 2px black rules opening each score group. Shared renderer, so the Customers Points tab matches automatically.",
      "HANDICAPS member restyle (view 1a): the pinless member table is the ratified five columns -- Player | Index | TREND | Rounds -- with a new Trend column (index delta vs before the latest round: green falling arrow = improving, red rising = up, computed server-side from the same WHS pools). Admin/manager tables keep all columns and gain the trend chip beside HCP. MEMBERS|EVERYONE active pill goes dark per the design; stat cards and table headers adopt the Bitter treatment.",
      "Deferred with intent: the expanded round-history interior cosmetics (green counting rows / red dashed cutoff restyle) ride with the upcoming admin-density handoff -- the current functional cutoff lines stay.",
    ],
  },
  {
    version: "2.56.0",
    date: "2026-07-09",
    changes: [
      "SEASON CONTESTS member restyle, phase A (design handoff contests-handicaps-071026, Kerry-ratified mailbox #63): the race selector is now a pill-chip row on desktop -- active chip wears its chapter color (Austin burnt orange, San Antonio slate; the TGF-wide cups and Monthly go dark) -- and on phones it becomes the design-system dropdown (44px control, orange focus ring, card menu with the active race checked). One code path: the dropdown delegates to the chips.",
      "Standings get the ratified table treatment: Bitter uppercase hairline headers, sans tabular-nums data at the 12.5px mobile floor, soft row dividers. A green phase chip reads 'Regular Season / best 10 count' on every race except MONTHLY (which counts everything, per the season spec ratified in mailbox #71).",
      "Season spec recorded in game-engine.md (mailbox #71, Kerry-confirmed): Best 10 + City Championship applies to the NET races AND The Players Cup; points = Stableford floored at zero; championship adds at face value; monthly races are uncapped. Four-step championship structure documented; its UI (view 1b) stays HELD per Kerry until cleared.",
      "Phase B next: the expanded-player drill-down (POINTS COUNTED / NOT COUNTED bands, scorecard treatment) and the Handicaps member restyle (trend column, cutoff-line history, mobile cards).",
    ],
  },
  {
    version: "2.55.2",
    date: "2026-07-09",
    changes: [
      "Restored the Admin link (Kerry): the shell's desktop ADMIN pill now actually navigates to the Admin section -- it sat outside auth.js's nav-link selectors so the anchor never un-hid; the visible orange pill was the unclickable role badge. For admins the pill IS the /accounting link on desktop (badge hides as redundant); mobile keeps the badge in the bar with the drawer's Admin row as the way in.",
      "Member views can never show manager/admin controls (Kerry): the monthly points 'Refresh from Golf Genius' button is re-injected on every render AFTER the role pass and leaked into the pinless member view. Injected render now gates on role, and member pages carry a CSS backstop (.manager-only/.admin-only display:none !important) so nothing role-gated can ever appear regardless of render timing.",
    ],
  },
  {
    version: "2.55.1",
    date: "2026-07-09",
    changes: [
      "Season-total rule recorded (Kerry): best 10 event point totals + City Championship total is the TGF standard for THE FELLOWSHIP CUP and THE PLAYERS CUP (computed on the Golf Genius side today; documented in game-engine.md pending platform-claude's parameter pass). The projected points-reset formula as implemented live is documented on the mailbox thread (#64): master ladder 100 - 0.5x(p-1); race rank maps via ROUND(1 + coef x (r-1)); NET races prorate by largest-chapter headcount, The Players Cup restacks straight at coef 1.",
    ],
  },
  {
    version: "2.55.0",
    date: "2026-07-09",
    changes: [
      "NAV SHELL V2 APP-WIDE (design-claude handoff nav-shell-070926, Kerry-ratified mailbox #58): every Tracker page now wears the dark top nav -- TGF circular-G mark + Tracker wordmark + version chip, uppercase Bitter section links with orange active underline, orange Admin pill, quiet outline Log Out. Built once as a shared _shell_nav.html include with shell.css/shell.js.",
      "MOBILE: hamburger drawer (Kerry's call) replaces the wrapped tab nav for manager/admin -- 82%-width dark panel, 52px section rows with orange active treatment, ADMIN pill on gated rows, role pill + Log Out in the footer. Kerry's drawer threshold rule: roles with 3 or fewer sections (member, view-only) get inline tabs in the dark bar instead -- no drawer for two items.",
      "PAGE-OPS TOOLBAR (spec 1e/1f): header operation buttons moved to a white toolbar row below the nav with tiered pills -- filled-dark primary, 2px-outline secondary, gray maintenance, red-outline destructive isolated right (Purge), Settings last. On phones the row keeps the primary + a '... Actions' bottom sheet holding the rest; operations never enter the navigation drawer. Row collapses to nothing when a page/role has no ops.",
      "MEMBER SHELL: pinless pages show The Golf Fellowship wordmark, Season Contests | Handicaps inline tabs, and the ENTER SEASON CONTESTS pill in the nav on desktop (the in-content CTA stays on mobile).",
      "ROLLBACK: single SHELL_V2 env var (default on). Flip to 0 on Railway and every page instantly reverts to its legacy header -- old markup is preserved in {% else %} branches until a cleanup release after Kerry's bake-in sign-off.",
    ],
  },
  {
    version: "2.54.6",
    date: "2026-07-09",
    changes: [
      "Role lanes revised per Kerry's ratification (mailbox #50, supersedes the 'content/data manager' framing): tracker-claude owns and builds the Tracker and is authoritative on what's live in it, scoped to the Tracker specifically; design-claude owns visual/UX design but verifies business vocabulary/IA with tracker-claude; platform-claude owns Platform architecture/scope/roadmap and cross-system continuity; Kerry is final ratification and tie-breaker. Encoded as CLAUDE.md workflow rule 3c.",
    ],
  },
  {
    version: "2.54.5",
    date: "2026-07-09",
    changes: [
      "Governance guardrail encoded (mailbox #47, Kerry via platform-claude): changes touching money, schema, member-facing behavior, or scope require an explicit Kerry-ratifies checkpoint BEFORE shipping -- multi-Claude consensus is not approval. Role lanes recorded: tracker-claude is the content/data manager, design-claude is design only, platform-claude is the project manager. Also corrected the record on THE PLAYERS CUP (mailbox #48): it is the live season-long GROSS points race sub-tab on Season Contests -- canonical vocabulary confirmed for the design handoff.",
    ],
  },
  {
    version: "2.54.4",
    date: "2026-07-09",
    changes: [
      "Design-handoff delivery pivoted to the mailbox itself (Claude Design can read but not write other Claude Design projects): handoffs arrive as design-handoff posts using a FILE/part protocol with a closing manifest (spec in mailbox #45). Prototypes must be self-contained HTML/CSS referencing Design System assets by name; the DS project stays the DesignSync-readable source for assets/tokens. Green light given to design-claude for the full Season Contests + Handicaps compliance build (admin + member views, real IA and states).",
    ],
  },
  {
    version: "2.54.3",
    date: "2026-07-09",
    changes: [
      "Typography rule ratified (Kerry): Bitter serif is reserved for headings, nav/CTA labels, eyebrows, and large stat numerals; dense data (table cells, list rows, numeric columns) stays system sans with tabular numerals. Locked into CLAUDE.md and relayed to Claude Design (mailbox #44) so the SEASON CONTESTS + HANDICAPS prototypes apply it from the start.",
    ],
  },
  {
    version: "2.54.2",
    date: "2026-07-09",
    changes: [
      "Three-party mailbox convention (Kerry): the platform dialogue mailbox now carries tracker-claude, platform-claude, AND design-claude (Claude Design). Every post starts with a TO: line, topics are prefixed design-*/platform-*, and design handoffs are delivered via the Claude Design 'TGF Design System' project under handoffs/<section>-<date>/ (DesignSync-readable). Posted the Payouts-handoff design feedback and the SEASON CONTESTS + HANDICAPS prototype requirements (member-view constraints, real-state coverage, mobile type floors) to design-claude (mailbox #42/#43).",
    ],
  },
  {
    version: "2.54.1",
    date: "2026-07-09",
    changes: [
      "Official TGF circular-G icon marks are in: static/tgf-icon.svg (black) + static/tgf-icon-white.svg, pulled straight from the Claude Design 'TGF Design System' project via the new DesignSync connection. The Payouts dark nav now shows the real mark instead of the placeholder tracker icon. The design system's full token sheet (colors_and_type.css) is checked in under docs/design-system/ as the Phase 2 reference.",
    ],
  },
  {
    version: "2.54.0",
    date: "2026-07-09",
    changes: [
      "TGF DESIGN SYSTEM PHASE 1 (Claude Design handoff, Kerry-approved): the Payouts page is the reference implementation of the new design standards. Dark near-black top nav (TGF icon + 'Tracker' wordmark + version chip left; uppercase Bitter nav links + orange role pill linking to Admin right), white sub-tab bar with UNPAID rendered as a right-aligned solid-orange pill -- the new visual convention for an admin-only tab. Tab names unchanged per Kerry.",
      "GOLFERS tab rebuilt as the Command Ledger: dark left rail with ranked golfer leaderboard (search, rank, event count, winnings in money-green; active golfer gets the orange left-border treatment) and a white detail panel -- Payouts/Info toggle, golfer name in Bitter serif, season-year WINNINGS stat in TGF orange, and per-event collapsible groups with chapter-colored header bands (Austin burnt orange / San Antonio slate / TGF dark) and category-colored payout lines. Events collapse by default; each toggles independently.",
      "Mobile: the ledger becomes a leaderboard list -> golfer detail flow with a back affordance, per the 2b/2c mock screens.",
      "Design tokens (dark surfaces, money greens, payout category colors) added to dashboard.css :root for the Phase 2 site-wide rollout -- which is ON HOLD pending Claude Design's SEASON CONTESTS + HANDICAPS prototypes (Kerry, member-pages priority). TGF icon marks are still placeholders until the design-system SVGs land.",
    ],
  },
  {
    version: "2.53.1",
    date: "2026-07-09",
    changes: [
      "HANDICAPS default filter is CURRENT MEMBERS only (Kerry): a MEMBERS | EVERYONE pill pair next to the chapter tabs, defaulting to MEMBERS (customers.current_player_status of active_member or member_plus). Guests, first-timers, expired/inactive members, and players not yet linked to a customer record show under EVERYONE. Applies to the admin page and the public /member/handicaps view alike; the players API now carries a player_status field (status label only -- no PII).",
    ],
  },
  {
    version: "2.53.0",
    date: "2026-07-09",
    changes: [
      "TGF MEMBER VIEW (Kerry): a pinless, shareable URL -- https://tgf-tracker.up.railway.app/member -- that opens SEASON CONTESTS and HANDICAPS read-only with no login. Full expansion and drill-down works (points races, Fellowship Cup, monthly points, Match Play pools/bracket, handicap cards); every hyperlink into the rest of the Tracker is removed in this view -- player names render as plain text, the nav shows only Season Contests | Handicaps, and the version badge no longer links to the changelog.",
      "Under the hood: a new public 'member' role tier sits below view-only; only PII-free GET endpoints declare it (season contests, points races, monthly points, handicaps, scoring reads, match-play reads). Customers, events (with cost/markup fields), transactions and every write path still require a PIN exactly as before.",
      "ENTER SEASON CONTESTS CTA (Kerry): a prominent TGF-orange button at the top of the Contests page -- both the normal and the member view -- links to the registration page at thegolffellowship.com/shop/ols/products/season-contests.",
    ],
  },
  {
    version: "2.52.3",
    date: "2026-07-09",
    changes: [
      "BULK CONFIRM (Kerry): bulk_mark_payouts_paid(before_date) marks every still-pending payout group from events before a cutoff as PAID -- payments made before mid-May predate the Venmo receipt capture and can never auto-match. Where an unconsumed receipt within \$3 exists it links to it (single ledger entry, receipt consumed); otherwise the pending placeholder becomes the expense of record, annotated '(bulk-confirmed paid)' with paid_at = event date. Bridge command scoring-payouts-bulk-paid:<YYYY-MM-DD>; idempotent. Ran with 2026-07-07 -- only this week's Falconhead/Silverhorn (+ true stragglers) remain on the UNPAID tab.",
    ],
  },
  {
    version: "2.52.2",
    date: "2026-07-09",
    changes: [
      "Matcher memo-typo fallback: when a receipt's memo names an event where that customer has NO pending group (the same-day cross-chapter case -- Austin players paid with the 's9.8 SILVERHORN' memo on a9.8 day), the matcher falls back to an EXACT-cents unique match across all their pending groups, the same evidence tier a memo-less receipt already gets. Non-exact amounts still never match without a correct event.",
    ],
  },
  {
    version: "2.52.1",
    date: "2026-07-09",
    changes: [
      "VENMO MATCHER: MEMO OUTRANKS THE PIPELINE GUESS (Kerry: 'there should be far more matches'). Audit of the 209 unpaid groups showed the expense classifier's event attribution is routinely wrong ('Winnings for s9.16 ...' receipts tagged s9.12), and the matcher trusted it first -- so exact-amount receipts for s9.10 Riverside, s9.16 TPC Oaks, a9.8 Avery Ranch and more never matched. The event code in YOUR memo now resolves first; the pipeline's event_id is only a fallback.",
      "Also: memo codes with a space after the dot parse ('s9. 10' -> s9.10), and the amount tolerance scales with evidence -- memo-named event: +/-$3 (you often paid GG's printed amounts, which differ from our computed cents by a couple dollars); pipeline-guessed event: +/-$1; no event: exact only. Uniqueness still required at every tier.",
    ],
  },
  {
    version: "2.52.0",
    date: "2026-07-09",
    changes: [
      "UNPAID WORK QUEUE (Kerry): the Payouts page grew an UNPAID tab -- every non-paid golfer/account group across events AND season contests in one list, newest first, with the total due up top and Pay / Mark Paid / status inline so it can be worked straight through.",
      "MOBILE COMPACTION: 'Season Contests' reads 'Season' below 768px (main nav tab AND the Payouts page tab); the Payouts page tables got the same treatment as the per-event panel -- # and Games columns hidden on phones, status badge after the Pay link, horizontal-scroll wrapper; category badges shorten Individual Net/Gross to Ind Net / Ind Gross (and Closest to Pin to CTP) on phones.",
      "COMPACT DESCRIPTIONS everywhere payouts render: the category badge already names the game, so descriptions now show just 'LOW | T1st' style (flight | place, ties prefixed T), 'Hole 4' for CTP/Longest Putt, 'LOW | x2' for skins. Display-only -- stored descriptions unchanged.",
      "Diagnosis plumbing for 'why didn't my old Venmo payments match': get_unpaid_payout_groups pairs every unpaid group with that customer's recent Venmo payout receipts (bridge command scoring-payouts-unpaid).",
    ],
  },
  {
    version: "2.51.2",
    date: "2026-07-08",
    changes: [
      "Removed the 'auto: ' prefix from payout descriptions everywhere they display (Payouts page breakdowns, per-event PAYOUTS panel, Customers winnings API). The prefix stays in STORAGE -- it is how re-recording distinguishes auto-recorded rows from manual ones -- it just no longer wastes screen space (Kerry).",
    ],
  },
  {
    version: "2.51.1",
    date: "2026-07-08",
    changes: [
      "PAYOUT NAMES SHOW THE SUFFIX (Kerry): every payout surface -- the Payouts page tables, the per-event PAYOUTS panel, Customers -> Winnings, mark-paid descriptions -- now renders 'Victor Arias Jr' / 'Victor Arias III' instead of two indistinguishable 'Victor Arias' rows. The name builds append customers.suffix when present; the Venmo memo inherits it automatically since it uses the same display name.",
    ],
  },
  {
    version: "2.51.0",
    date: "2026-07-08",
    changes: [
      "MONTHLY POINTS PAYOUTS ARE NOW TRACKED (Kerry): each completed month gets its own payout account (like an event) -- 'MARCH Points 2026' etc. with one row per winner ($1/member purse, ties split, from the monthly snapshot). record_monthly_points_payouts runs after the daily monthly-points refresh, is idempotent, and reuses the proven import path (pending ledger placeholders + Venmo reconciliation).",
      "PAYOUTS page grew a top-level tab: EVENTS | SEASON CONTESTS | GOLFERS. Season Contests lists the month accounts (and future Fellowship Cup / Match Play accounts by naming convention) with the same golfer table, PAID/PENDING badges, Pay links, and Mark Paid as events. Monthly rows also appear in Customers -> Winnings automatically (new 'Monthly Points' category badge).",
      "Venmo auto-confirm now covers monthly payments: 'Winnings for MARCH Points' receipts resolve ONLY to the month's own account (never a golf event) and mark the winner's row PAID. The v2.50.1 repair leaves legitimate month-account links alone.",
    ],
  },
  {
    version: "2.50.1",
    date: "2026-07-08",
    changes: [
      "VENMO MATCHER GUARD: monthly-points winnings payments ('Winnings for MARCH Points' etc.) are excluded from payout matching -- those are paid from the Contests page and have no PAYOUTS-tab rows, but a $70.00 MARCH Points payment slipped through the +/-$1 tolerance and wrongly marked a $70.37 event group PAID within the first hour live. The +/-$1 fallback now also requires the EVENT to have resolved (receipt event or memo code); a bare close-amount is no longer enough evidence.",
      "Boot repair reverts any payout rows falsely matched to monthly-points payments (reinstates their pending placeholder, clears paid_at) -- healed the one live case (Straiton a9.17). Event winnings confirmations are unaffected: Young $232.29 and Ellis $70.56 for s9.17 Silverhorn matched cleanly from their receipt emails during the same test.",
    ],
  },
  {
    version: "2.50.0",
    date: "2026-07-08",
    changes: [
      "VENMO PAYMENTS AUTO-CONFIRM PAYOUTS (Kerry): the expense inbox already ingests your outbound Venmo 'you paid' receipts (recipient, amount, memo). A new matcher (auto_match_venmo_payouts_to_tgf) links each receipt to the pending payout group for that golfer+event -- resolved by customer, then event (receipt's event, or the 'Winnings for s9.16 ...' memo code), then amount (exact first, +/-$1 only when unique) -- reverses the PENDING ledger placeholder, and stamps the payout PAID with the payment date. The PAYOUTS tab flips to PAID and the Pay link disappears with zero manual steps.",
      "Runs everywhere it needs to: automatically as each Venmo receipt email arrives (5-min inbox check), when an expense is approved in review, right after Record Payouts (consumes receipts that arrived before recording), on demand via POST /api/tgf/auto-match-venmo-payouts (admin backfill), and via the scoring-payouts-venmo-match bridge command. Ambiguous matches (two pending groups with the same amount) are left alone for manual Mark Paid rather than guessed.",
    ],
  },
  {
    version: "2.49.6",
    date: "2026-07-08",
    changes: [
      "VENMO MEMO FORMAT (Kerry): pay links now prefill '[First] [Last] - Winnings for [event]' (was 'TGF [event]') on both the per-event PAYOUTS panel and the Payouts page, and the excess-credit refund links read '[Name] - Excess credit refund'.",
      "NO MORE '+' BETWEEN WORDS: Venmo's https universal link re-serializes the query so the app showed a literal + for every space in the memo (e.g. 'TGF+s9.17+Silverhorn'). On phones/tablets the links now use the native venmo:// scheme, which the app parses directly so spaces come through as spaces; desktop keeps the venmo.com web link.",
    ],
  },
  {
    version: "2.49.5",
    date: "2026-07-08",
    changes: [
      "PAYOUTS breakdown simplified on mobile (Kerry): the expanded per-golfer detail now shows just the game name (category badge) on the left and the amount on the right -- the free-text description column (which repeats the category) hides below 768px, and the breakdown indent tightens so rows use the full width.",
      "PENDING/PAID status badge now renders AFTER the Venmo Pay link on each payout row, and the whole payouts table sits in a horizontally scrollable container so anything that still overflows can be swiped into view instead of being cut off.",
    ],
  },
  {
    version: "2.49.4",
    date: "2026-07-08",
    changes: [
      "PAYOUTS TAB CLEANUP (Kerry): removed the obsolete 'Paste Screenshot' drop zone (and its AI-parse handlers) from the per-event PAYOUTS panel -- the auto Golf Genius results sync + Record Payouts pipeline replaced screenshot imports. The empty state now points at the automatic path instead of asking for a screenshot.",
      "PAYOUTS panel on phones: the REGISTERED and GAMES columns are hidden below 768px so # / GOLFER / TOTAL / status fit without horizontal crush. Desktop unchanged; the expandable per-golfer breakdown still shows every game line.",
    ],
  },
  {
    version: "2.49.3",
    date: "2026-07-08",
    changes: [
      "FRESH LAUNCH ALWAYS LANDS ON EVENTS (Kerry): iOS resurrects the PWA's last URL on relaunch -- after tapping a customer link, the app could reopen on /customers?name=... with the search prefilled. The fresh-launch redirect now only stays put for REAL deep links (?txn= / ?item= / ?cid=, the params email links use); every other restored URL goes to Events.",
      "NO MORE SURPRISE ZOOM ON MOBILE: added maximum-scale=1 to the viewport meta on every page, which stops iOS from auto-zooming when a small-font input gets focus (that zoom persisted across launches and made the app open 'slightly zoomed in'). Manual pinch-zoom still works -- iOS ignores maximum-scale for user-initiated zoom.",
    ],
  },
  {
    version: "2.49.2",
    date: "2026-07-08",
    changes: [
      "HYPERLINKS = UNIVERSAL BLUE (Kerry): customer and item/event links in table rows (.cell-link) are the classic hyperlink blue (#2563eb, new --link var) -- everyone associates hyperlinks with blue. Orange stays reserved for CTAs and active states; all other table-row text is black, including the Handicaps index numbers (desktop + mobile card) which had inherited orange from the palette swap.",
    ],
  },
  {
    version: "2.49.1",
    date: "2026-07-08",
    changes: [
      "CUSTOMER TEXT BACK TO BLACK (Kerry): the v2.49.0 palette swap turned customer-name links (.cell-link -- Events roster, Transactions, Customers) orange; they now read as standard black text again, with the hover underline (in orange-hover) keeping the click affordance.",
    ],
  },
  {
    version: "2.49.0",
    date: "2026-07-08",
    changes: [
      "PAIRINGS INTERACTIVITY (Kerry): open seats in a 3some/2some/1some now render as dashed '-- open --' rows and are CLICK TARGETS -- pick a player (Player or Move mode) or a cart pair (Cart Pair mode) and click an open seat to drop them exactly there; moving a pair into an empty cart now works (it previously required an occupied row to swap with). Group hole assignments are editable by clicking the header above the names (prompts for the new label; Save persists it). The '(Hole)' suffix is gone from group headers and the header bar is TGF orange. Also fixed a latent bug where moving a player into a group with non-contiguous seats could double-book a cart position.",
      "STANDARD COLORS ADOPTED (Kerry's brand sheet): the app-wide palette switches to TGF Orange #E87C3E accent + monochrome foundation -- primary buttons/links are now orange (hover #D06B2E), text #1B1B1B on #F8F8F8 surfaces, borders #E5E7EB, and the PWA theme color is orange. Chapter semantic colors are live on the Events/Handicaps chapter pills: AUSTIN burnt orange #BF5700, SAN ANTONIO slate #D3DDE4, ALL stays TGF orange. FG2/FG4 and chapter vars are defined in :root for future use.",
      "EVENT VIEW BADGES (Kerry): PLAYERS renamed ROSTER, and FINANCIAL moved to the END after PAYOUTS (Roster | Pairings | Games | Payouts | Financial) on desktop and mobile.",
      "JULY MONTHLY POINTS (Kerry): the Contests MONTHLY tab no longer waits for the hand-built '<MONTH> Points' page on the GG portals -- when the current month has no page yet, the tracker synthesizes it from each played player's season-points detail (only players with a scoring round that month are fetched), so JULY shows now and every future month appears on day one. Once the GG page exists it takes over automatically.",
      "ARIAS FIX 1 -- participation last-played now joins registrations to events by EVENT ID (name-string match only remains as a legacy fallback). The Ariases' s9.16 TPC Oaks rounds were invisible to Participation because the items say 'TPC OAKS' while the event row says 'TPC San Antonio | Oaks'.",
      "ARIAS FIX 2 -- the payout recorder was minting duplicate shell customers for GG 'LAST, First Suffix' names ('ARIAS, Victor Jr' became a fresh 'Victor Jr Arias' shell on every recording pass; 8 shells found). The resolver now goes through the scoring identity spine first (same resolver that links their scorecards correctly), a boot repair merges the existing shells back into the real customers and repoints their payout rows, and a guard prevents the same shell from ever being minted twice.",
      "MANAGER ACCESS TIGHTENED (Kerry): Send Report (Transactions) is admin-only, and Match Venmo can no longer linger visible after an admin logs out and a manager logs in on the same page -- both are also force-hidden on any role switch.",
      "HEADER LAYOUT: the role badge, Import/Export dropdown, Email Cards, and Log Out now sit on ONE line (the header-actions row is flex on desktop too; the dropdown wrapper was a block element that stacked the handicaps header).",
      "EVENTS TOOLBAR (Kerry): the search bar, Columns, and + Add Event moved onto the SAME line as the UPCOMING | Past | All Events control, right-justified, with the search bar shortened to a compact width.",
      "RED \u2715 CLEAR (Kerry): the wide 'Clear Filters' button is now a small red \u2715 sitting immediately right of the search bar on EVERY page that had one (Events, Transactions, Customers, RSVP Log). Same behavior -- appears only when a filter is active, one click resets.",
    ],
  },
  {
    version: "2.48.0",
    date: "2026-07-08",
    changes: [
      "SEASON CONTESTS (Kerry batch): the nav tab is renamed Season Contests, and view-only sessions can now actually SEE the standings -- the read-only standings APIs (enrollments list, points races, Fellowship Cup, monthly, scoring-round drill-downs) dropped from manager to view-only, fixing the 'requires Manager Access' dead end; the ENROLLMENT top-tab hides for view-only (write APIs all stay manager/admin).",
      "CHAPTER SCOPING EVERYWHERE: HANDICAPS gains ALL | AUSTIN | SAN ANTONIO pills (player chapter now rides on the handicaps API via the customer link); TRANSACTIONS and the RSVP LOG gain a chapter select that scopes by each item's EVENT chapter with shared/TGF events always included (chapterless rows like memberships stay visible). All three pre-select the chapter manager's chapter; admin lands on ALL.",
      "PARTICIPATION: new 'Played' filter (any / this calendar year / has played / never), and the landing sort is now LAST PLAYED most-recent-first with never-played members at the BOTTOM -- they no longer top the MEMBER view. (Known data note: a member with no Last Played usually means their event rows never matched an events-table row; audit ongoing.)",
      "TGF ORANGE ACTIVES: every active filter/toggle state -- segmented controls, chapter pills, PLAYERS/GAMES/FINANCIAL badges, category buttons, customer detail tabs, contests sub-tabs -- switches from royal blue to TGF orange (#E87C3E).",
      "OPS BUTTONS ADMIN-ONLY (Kerry): Sync Events, Check RSVPs, and Check Now disappear for managers and view-only on every page. Customers Export CSV is admin-only (no bulk download access for managers yet). HANDICAPS consolidates Import Rounds + ALL/SA/Austin CSV into one Import/Export dropdown; Email Cards stays standalone.",
      "REFRESH CADENCE (Kerry: 'too much refreshing'): the GG results auto-sync now runs ONLY on event days (event today or yesterday, Central) -- close-the-event-to-results-in-an-hour still holds on those days, and off days skip GG entirely. Points-race snapshots likewise stop auto-refreshing unless an event happened since the snapshot was taken; the manual Refresh button always forces a live pull.",
    ],
  },
  {
    version: "2.47.0",
    date: "2026-07-08",
    changes: [
      "CHAPTER-MANAGER PINS (Kerry): new AUSTIN_MANAGER_PIN and SA_MANAGER_PIN env vars log in as manager with the chapter attached to the session -- Events lands on their chapter tab, Contests opens their chapter's points race, the Customers chapter filter and Participation chapter pre-select, and the role badge reads e.g. 'AUSTIN Manager'. They can still click over to other chapters. The LEGACY shared MANAGER_PIN is demoted to view-only (per Kerry: it becomes the view-only PIN); a dedicated VIEWONLY_PIN env var also works. ADMIN_PIN unchanged. NOTE: manager access requires the two new Railway variables -- until they're set, only admin and view-only logins exist.",
      "VIEW-ONLY REDUCED: view-only sessions see only EVENTS | CONTESTS | HANDICAPS in the nav; /transactions, /customers, /rsvps, and /participation redirect them to Events (server-side, not just hidden links). Badge reads 'View Only'.",
      "NAV REWORK (Kerry): order is now Events | Contests | Handicaps | Transactions | Customers everywhere, with Payouts and an ADMIN tab in TGF orange (#E87C3E) pinned LAST for admins. RSVP Log is consolidated as a sub-tab inside TRANSACTIONS and Participation as a sub-tab inside CUSTOMERS (segmented-control links under the main nav; the pages themselves are unchanged underneath).",
      "PARTICIPATION LANDING (Kerry): first load defaults to MEMBER status + >=30-day dormancy, plus the manager's chapter for chapter-manager sessions.",
      "EVENTS: UPCOMING tab is now ALL CAPS (Past / All Events stay standard case); the All Events view draws a TGF-orange PAST EVENTS breakline where upcoming meets past (desktop and mobile, date-sorted views); and the per-event PAYOUTS view toggle now shows on MOBILE event cards for admins -- it was desktop-only (it is the event-scoped view of the top-level PAYOUTS page, so it stays admin-only per v2.45.0).",
    ],
  },
  {
    version: "2.46.0",
    date: "2026-07-08",
    changes: [
      "EVENTS TIME TABS RESTYLED to the app's standard segmented control (Kerry's reconcile-page reference): Upcoming | Past | All Events -- reordered, standard case, counts inline, active segment as the blue pill. Every CHAPTER click re-opens on Upcoming; ALL remains the landing chapter. Default ordering: Upcoming soonest-first, Past AND All Events most-recent-first.",
      "SHARED EVENTS ACROSS CHAPTERS: the Edit/Add Event chapter dropdown gains 'TGF (All Chapters)' (stored as events.chapter = 'TGF') for shared 18s and the TGF Championship -- those events now appear under EVERY chapter tab, not just one. Event sync never overwrites an edited chapter, so the designation sticks. When more chapters exist, a subset multi-select can layer on the same mechanism.",
    ],
  },
  {
    version: "2.45.0",
    date: "2026-07-08",
    changes: [
      "PAYOUTS ARE ADMIN-ONLY (Kerry rulings): managers keep credit/transfer/WD (internal ledger moves -- no real money leaves), but everything that records an actual outbound payment or shows payout data is now admin-only: the Payouts nav tab and /tgf page, the per-event PAYOUTS view, the Games-tab Record Payouts button, the Customers Winnings tab, and the APIs behind them (payout read/write, mark-paid, screenshot import, record/preview game payouts). Refund, partial-refund, and payout-credit were already admin-only -- confirmed, no change needed there. Verified with headless role-by-role checks: the manager session's nav shows 7 tabs with no payout surface anywhere.",
      "EVENTS CHAPTER TABS (Kerry): the big ALL EVENTS / UPCOMING / PAST stat cards are replaced by two compact tab rows -- a CHAPTER scope on top (ALL | AUSTIN | SAN ANTONIO) with the time tabs (ALL EVENTS | UPCOMING | PAST, with counts) subordinate underneath. Chapter is the outer context: counts, the time buckets, and even search all re-scope to the selected chapter. Clear Filters resets to ALL/UPCOMING; event deep-links widen the chapter scope automatically when the target event is outside it.",
    ],
  },
  {
    version: "2.44.0",
    date: "2026-07-08",
    changes: [
      "EVENTS IS THE LANDING PAGE (Kerry): opening the app -- fresh PWA launch, bare URL, or bookmark to / -- now lands on EVENTS instead of TRANSACTIONS. The Transactions dashboard moved to /transactions (all nav tabs updated); old /?txn= deep links redirect there with the transaction still highlighted, the PWA manifest start_url follows, and non-admins hitting an admin URL now land on Events instead of a mislabeled Transactions render.",
      "ACCESS AUDIT + LOCKDOWN (Kerry: 'tell me what MANAGERS are seeing and have access to'): swept every route's role gate and found 20 API endpoints that answered WITHOUT ANY LOGIN -- left ungated when v2.16.10 sealed the main PII set. Worst were /api/tgf (payout data incl. payment handles) and the RSVP feeds (names/emails); also /api/events, /api/customers/names, /api/matrix, parse warnings, and the check-now trigger. All now require a session: read-only views at view-only, operational/payout data at manager (/api/tgf, orphaned items, parse warnings, message templates, Check Now). Verified before/after with an unauthenticated probe of a live instance: every one of the 20 now returns 401. Final gate counts: 41 view-only / 114 manager / 197 admin routes.",
    ],
  },
  {
    version: "2.43.1",
    date: "2026-07-08",
    changes: [
      "FELLOWSHIP CUP MOVEMENT BACKFILL (Kerry: 'Any way to reverse engineer the change in The Fellowship Cup by reviewing the history of last GG event and yesterday's?'): yes -- the Cup's reset value is a pure function of each player's POSITION in their NET race (master ladder + coefficient), and GG's race snapshots already carry everyone's Previous Rank from before the July 7 events. seed_fellowship_cup_history() rebuilds yesterday's Cup ordering from those previous positions (players whose first imported round IS the latest event date are treated as not-yet-on-the-list newcomers), seeds it as the prior rank-history snapshot, and rotates today's order on top -- so the \\u25b2/\\u25bc chips show the last event's effect IMMEDIATELY instead of waiting for the next event. One-time bridge command scoring-fc-seed; normal snapshot-on-change recording takes over from here.",
    ],
  },
  {
    version: "2.43.0",
    date: "2026-07-08",
    changes: [
      "FELLOWSHIP CUP MOVEMENT CHIPS (Kerry: 'I know you don't have a GG reference for The Fellowship Cup because that's on our side, but could you create the same movement symbols? Are you recording the changes?'): we weren't -- the Cup is recomputed live from both NET races on every view, so nothing stored the previous order. New rank-history layer (rank_history_snapshots/_rows, generic by list_key): each Cup computation snapshots the ordering and ROTATES only when the order actually changes, so every row gains a prev_rank vs the pre-change state and the same green \\u25b2N / red \\u25bcN chips render in the Rank column (compact stacking on phones included). Chips persist until the NEXT standings change, matching GG's between-events arrow semantics; newcomers show no chip. History starts recording with this release, so the first chips appear after the next event shifts the Cup order. Keeps the last 12 snapshots per list; the monthly races can adopt the same mechanism later.",
    ],
  },
  {
    version: "2.42.0",
    date: "2026-07-08",
    changes: [
      "RANK MOVEMENT on the Contests points races (Kerry: 'add some type of movement symbol like is shown on the Golf Genius side... needs to be compact'): the season standings (SAN ANTONIO Net / AUSTIN Net / THE PLAYERS CUP) now show a GG-style chip in the Rank column -- green \\u25b2N for places gained, red \\u25bcN for places lost, computed from GG's own Previous Rank column (which the snapshot already stored but never displayed). A '-' previous rank shows nothing, matching GG; ties compare on the numeric part (T11 from 13 -> \\u25b22). On phones the chip stacks under the rank number so the narrow # column stays narrow. Monthly and Fellowship Cup standings are merged cross-chapter computations with no GG previous rank, so no chip there.",
      "Backfill/completion sweep behind the a9.17 Falconhead gap: re-walked EVERY round on both portals with the v2.41.2 leaderboard-section flight fallback (~1,300 flight rows, zero unresolved names) and force re-recorded all past auto payouts. All the old Austin 'flights_unknown' Individual Net games are now determined and PAID rows exist (a9.13 Star Ranch $416->$669, a9.16 ShadowGlen $339->$474, a9.9 ShadowGlen $350->$512, etc.). Remaining gaps are boards GG itself doesn't flight-section (s18.7/s18.2 Ind Net, a few early-season skins) plus the unratified Skins \\u00bd-Net rule -- listed per event in the Games tab notes.",
    ],
  },
  {
    version: "2.41.2",
    date: "2026-07-08",
    changes: [
      "AUSTIN IND NET FLIGHTS (a9.17 Falconhead showed 'flights_unknown'): Austin's flighted leaderboards render flight sections ('LOW Flight' / 'HIGH Flight') INSIDE the board itself and expose no per-player detail fragments -- the fragment walk (how SA flights import) recorded nothing there. The flights importer now falls back to parsing the section headings off the leaderboard table when fragments yield no labels (same idea as the skins Expand-All membership capture).",
      "TGF MVP SINGLE-OWNER RULE: once determined, the combined same-day pot was assembled by BOTH linked events, so a same-pass force-refresh of both (the auto-sync's 3-day heal window, or Populate All) recorded the $72-ish row TWICE -- once under each event. Exactly one event now owns the pot: the winner's own event (deterministic on both sides; cross-event tie splits settle by name order). The other event's assembly notes where it was recorded instead.",
      "Ran a full force re-record of all past auto-recorded events after deploy so any historical TGF MVP double-records and pre-tie-split Team Net amounts self-heal (manual/screenshot payout events untouched, as always).",
    ],
  },
  {
    version: "2.41.1",
    date: "2026-07-08",
    changes: [
      "Fix (found on a9.17 Falconhead, Kerry: 'closed out but I don't see much automatically coming thru'): the auto-sync's scorecard step matched board links EXACTLY against 'ALL Net'/'ALL Gross' -- the San Antonio portal's naming -- but Austin names its boards 'ALL Net 9'/'ALL Gross 9', so Austin events NEVER got scorecards from the hourly sync (winners/flights walks worked; everything scorecard-derived sat 'awaiting results'). Board matching is now prefix-based and imports every matching board (handles a future 'ALL Net 18' on combo days). Falconhead's 15 scorecards were imported by hand the same morning; note the sync window is 12:10-23:10 Central, so an event closed overnight lands on the 12:10 pass.",
    ],
  },
  {
    version: "2.41.0",
    date: "2026-07-08",
    changes: [
      "TEAM NET TIE SPLIT (found on s9.17 Silverhorn, where two teams tied T1): tied teams now split the combined place money before the per-member split, matching GG's own purse math -- $108 team pot, two T1 teams -> $54/team, then $18 each for the 3 payable members of SOUTH+MORENO+WADE (+blind draw excluded) and $13.50 each for YOUNG+WATSON+SHARITZ+DECAREAUX. Previously the first team took the whole first-place amount by list order and the tied second team got NOTHING (the matrix has one team place at this player count, so the second team fell off the end of the place list). Untied teams pay per place exactly as before; descriptions gain a '(T)' marker on ties.",
      "AUTO SYNC HARDENED (why s9.17's Team Net/CTP were missing after close): the hourly pass previously ran scorecards -> games -> flights inside ONE try/except per portal, so a transient GG fetch failure during the scorecard walk silently skipped the games and flights walks -- and the payout refresh then recorded the event with no Team Net/CTP attached. Each step is now isolated (a failed round fetch logs to that round's entry; games and flights each run regardless of earlier steps' failures), so one hiccup can no longer suppress winners that are sitting finalized in GG.",
      "PAST events under EVENTS now list most-recent-first (Kerry's ask): switching to the PAST filter flips the default date sort to newest-on-top; UPCOMING/ALL keep soonest-first, and an explicit column sort you've clicked survives the filter switch. Deep-links that auto-flip to PAST get the same ordering.",
    ],
  },
  {
    version: "2.40.1",
    date: "2026-07-07",
    changes: [
      "Documented the auto GG results sync pipeline in side-games.md (hourly close-event flow, recent-round re-walk semantics, 3-day payout refresh window, manual-payout protection) after verifying it live: s9.17 Silverhorn's scorecards, flights, and all computable games landed via the pipeline minutes after Kerry closed the event, and its 18 payouts ($452.01) recorded -- Team Net/CTP/TGF MVP will flow in on the next hourly pass once entered in GG / the linked event closes.",
    ],
  },
  {
    version: "2.40.0",
    date: "2026-07-07",
    changes: [
      "AUTO GG RESULTS SYNC (Kerry: 'I expected that once I closed the event on GG that results would show up in Tracker'): a scheduled job now runs the whole pipeline hourly (12:10-23:10 Central; AUTO_GG_SYNC=0 disables; pure HTTP against the public portals, no AI spend). Each pass, for BOTH portals: imports scorecards for the newest rounds' ALL Net then ALL Gross boards (net first so handicaps land; idempotent), re-walks the newest rounds for GG-recorded winners (CTP/Longest Putt/HIO/Team Net) and per-game flights -- live rounds get marked walked before results are entered, so recent rounds ALWAYS re-walk (upserts make it safe) -- then refreshes auto-recorded payouts, force-replacing events from the last 3 days so late GG entries flow through while older events and anything manually recorded stay untouched. Close the event in GG; within the hour the Games tab shows winners and the PAYOUTS tab has the rows with payment links.",
      "On-demand trigger: probe_golf_genius bridge command scoring-auto-sync runs one pass immediately; scoring-games-import accepts a rewalk arg for targeted recent-round re-walks (flights already had reset).",
    ],
  },
  {
    version: "2.39.2",
    date: "2026-07-07",
    changes: [
      "MOBILE CLARITY on the Games tab (Kerry's phone screenshots): (1) winner sub-rows previously wrapped at the horizontally-scrolled TABLE width, running off the right edge -- their content is now pinned sticky-left and capped to the screen width, so every winner line wraps fully on screen and stays visible while the money columns scroll; (2) the Game column now keeps a 150px minimum so labels and the inline CTP/MVP chips stop shredding into one-word-per-line towers (the fixed money columns were squeezing it to nothing) -- inline chips drop to their own line under the bold label; (3) winner text sized to match the table (0.72rem). Verified with headless phone-width screenshots, including pinned behavior mid-scroll.",
    ],
  },
  {
    version: "2.39.1",
    date: "2026-07-07",
    changes: [
      "Fix: skins payout rows now apportion the flight pot by skin counts with largest-remainder cents, so each flight sums to its pot exactly -- per-row rounding was drifting a cent (s9.16 Flight 1: 48.75+24.38+24.38 = 97.51 on a 97.50 pot).",
    ],
  },
  {
    version: "2.39.0",
    date: "2026-07-07",
    changes: [
      "PAYOUT ASSEMBLY MOVED SERVER-SIDE (single source of truth): assemble_event_game_payouts() reads the LIVE prize matrix from app_settings, mirrors the Games tab's player-count rules server-side, and produces the same rows the client showed -- City MVP (18h uses the matrix's capped mvp value; 9h folds TGF money in on single-event days), the combined TGF MVP pot computed across linked same-day events, per-flight Ind Net/Ind Gross ladders with exact-cent tie splits, Skins dollars, GG-recorded Team Net member splits and CTP/Longest Putt. The Games tab's Record Payouts button now previews the server's rows (GET /api/events/game-payouts-preview) and records via the same engine; the v2.38.0 client-side assembly was removed.",
      "POPULATE ALL EVENTS (Kerry): record_all_event_game_payouts() bulk-records every past event, time-budgeted -- bridge command scoring-record-payouts:ALL (repeat until events_left=0; ':ALL!' also re-records auto rows; ':<event>' does one). Guardrails: events with MANUAL/screenshot-imported payouts are always skipped (never mix -- would double-count the purse; also enforced in record_event_game_payouts itself), already-auto-recorded events skip unless forced, and events with nothing determined are reported, not written.",
      "FIXES from Kerry's screenshots: tgf_events.code now stores the FULL event name ('s9.15 The Quarry') matching the long-standing convention every consumer keys on -- the TGF sidebar no longer shows a truncated name and the Events page PAYOUTS tab (which matches code === item_name) now finds recorded payouts. Boot repair renames bare-code rows already created (the prod s9.15 row); recording into a legacy bare-code row upgrades it in place. Venmo note no longer duplicates the event name when code == name.",
    ],
  },
  {
    version: "2.38.1",
    date: "2026-07-07",
    changes: [
      "Fix: payout descriptions assembled by Record Payouts no longer HTML-escape the GG flight names -- 'Flight 1 (HCP <12.0)' was being stored in the ledger as '&lt;12.0'. Descriptions are data, not markup; the display layer escapes at render time.",
    ],
  },
  {
    version: "2.38.0",
    date: "2026-07-07",
    changes: [
      "RECORD PAYOUTS (Kerry directive): the Games tab gains a manager-only '💸 Record Payouts' button that assembles every DETERMINED winner into PAYOUTS-tab rows -- City MVP (+the combined TGF MVP pot exactly once, from whichever event's tab you click, with a warning not to record it again from the linked event), Individual Net per-flight place ladders with exact-cent tie splits, Skins per player (flight pot / skins x count), Ind. Gross per flight, GG-recorded TEAM Net split per member (blind-draw fills excluded), and GG-recorded CTP / Longest Putt. Hole-in-One is never auto-recorded (accruing cross-event pot). A confirmation dialog lists every row + total before anything writes.",
      "Server side record_event_game_payouts() finds-or-creates the tgf_events row by event code and delegates to the proven import_tgf_payouts path, so recorded rows get the full treatment: customer resolution (every payout row carries customer_id -- payouts tie to Customers, per Kerry), automatic matching against existing Venmo prize payments, pending ledger entries for the rest, and event aggregates. Rows are stamped 'auto:'; re-recording asks and then REPLACES the previous auto rows -- their pending ledger entries are deleted but a matched real Venmo transaction is never touched.",
      "PAYMENT LINKS: customers gain payment_method / payment_handle (admin-editable data; default = Venmo via the existing venmo_username). Boot-seeds Kerry's exceptions: Don Sharitz -> PayPal, Brian Thompson -> Cash App, Gus Vasquez + Michelle DelCarmen -> Zelle (only when the field is empty -- an admin edit always wins). The PAYOUTS tab's pay button is now method-aware: Venmo (blue) / PayPal.me (navy) / Cash App (green) deep links with the amount and 'TGF <event>' note prefilled; Zelle has no deep link so a badge shows the handle + amount and Mark Paid closes it out; missing PayPal/Cash App handles show an 'add handle' badge until supplied.",
    ],
  },
  {
    version: "2.37.1",
    date: "2026-07-07",
    changes: [
      "SKINS FLIGHTS SOLVED (Kerry's pointer): the skins leaderboard's Expand All view (/tournaments2/details?adjusting=false&event_id=<tid>) renders one per-player skin grid per flight -- full flight MEMBERSHIP, not just winners. import_gg_game_flights now captures skins flights from that view (one fetch per skins game instead of per-player fragments, which skins pages don't have); a single-section page means unflighted and records nothing. scoring-flights-import accepts a 'reset' arg to re-walk rounds already marked done (upserts make it safe) -- needed once so previously-walked rounds pick up their skins flights.",
    ],
  },
  {
    version: "2.37.0",
    date: "2026-07-07",
    changes: [
      "PER-GAME FLIGHTS (Kerry design ruling): flighting differs per game -- Net, Gross, and Skins cut differently -- so a player's flight is now a property of (game, event), not of their round. New gg_game_flights table ('Joe Smith is in flight X for THIS game') populated by import_gg_game_flights(widget_url) (bridge command scoring-flights-import): walks each flighted game's own GG leaderboard per round and reads the Flight section label from the per-player details fragments (the same parse the scorecard importer uses). The results engine prefers gg_game_flights and never mixes sources within a game; scoring_rounds.flight is only a legacy fallback for games with no per-game rows; responses carry flight_source. This closes the single-flight-column limitation flagged in v2.36.0.",
      "GAMES TAB LAYOUT (Kerry): winners for TEAM Net, Individual Net (per flight), Skins, and Ind. Gross moved to their OWN sub-rows below each game/flight row (hidden until results hydrate) instead of riding inline next to the name -- Individual Net flight placewinners now actually render (the inline flight-cell spans were the miss), Skins shows per-player skin counts WITH dollars (flight pot / skins x count), and Ind. Gross lists each flight on its own line. CTP and City MVP winners stay inline next to the name; the TGF MVP winner moved INLINE next to the heading; each TGF MVP event-breakout line now shows that event's City MVP winner (non-bold). City MVP, TEAM Net, CTP, and Ind. Gross headings are bold to match TGF MVP / Individual Net / Skins Gross.",
      "MOBILE: the bad inline wrapping is gone -- long results live in the full-width winner sub-rows, which wrap freely (dashed separators); the only inline chips left (CTP, City MVP, TGF MVP) are short and wrap naturally inside the label cell. The v2.36.0 chip-block/max-width mobile hacks were removed.",
      "New verification bridge commands on probe_golf_genius: scoring-game-results:<event>|<game>|<flights> (shadow-computed winners) and scoring-gg-results:<event> (GG-recorded winners) for checking production data per event.",
    ],
  },
  {
    version: "2.36.0",
    date: "2026-07-07",
    changes: [
      "Kerry's game-results rulings applied (screenshot answers to mailbox id 25). FLIGHT RULE: flights now come from GG ONLY -- multi-flight games group by the imported scoring_rounds.flight labels (ordered low-to-high by average playing handicap so the matrix-named rows align) and the v2.35.0 handicap-derived fallback is removed; games whose scored entrants lack labels show 'flights pending GG import' (the labels arrive when the game's own GG leaderboard is imported, not just ALL Net/ALL Gross). Known limit flagged: scoring_rounds holds one flight label per round, so games with different cut lines share whichever import ran last -- per-game labels queued as an import extension.",
      "GG-RECORDED WINNERS: CTP / Longest Putt / Hole-in-One / TEAM Net are manually entered into GG post-round, so the portal is the source of record. New import_gg_game_results(widget_url) walks the Event Results rounds exactly like the MVP importer (time-budgeted, per-round dedup, bridge command scoring-games-import on probe_golf_genius) and records winners into the new gg_game_results table (purse>0 rows, else position 1/T1 ties; team rows keep the full 'A + B + C + D' string with is_team=1; CTP feet-and-inches Details captured). Table shapes verified against the LIVE s9.17 round (CTP = Pos./Player/Details, TEAM Net = Pos./Foursome/TotalNet). GET /api/events/gg-game-results serves them; the Games tab hydrates trophy chips on the Team Net and CTP rows and the Hole-in-One banner (Longest Putt winners ride on the CTP rows; team names shorten to surnames).",
      "MOBILE PRESENTATION: on phones the winner chips (MVP + computed + GG-recorded) drop to their own line under the game label and are allowed to wrap -- overriding the global tbody nowrap that would otherwise let long names stretch the Game column and shove the money columns off screen. Game-label cells cap at ~half the viewport, tighter cell padding, and the Hole-in-One banner wraps. All inside the existing 768px games-panel media block so there is one mobile breakpoint, with the panel's horizontal scroll preserved for the money columns.",
    ],
  },
  {
    version: "2.35.1",
    date: "2026-07-07",
    changes: [
      "Banked mailbox ids 22/24 (Platform adversarial review, Kerry-ratified) into game-engine.md for future sessions: the wallet VOID verb (ADD/VOID/SPEND contract -- VOID before Venmo-ing out a wallet credit, pay only the returned voided_remaining, idempotent on the credit's external_ref), the 'money goes back the way it came' refund rule (30-day new-member guarantee refunds via Stripe from the Platform -- the only exception; Tracker-era money always refunds via Venmo from the Tracker), and the held_until guarantee window on new-member membership revenue (no effect on the $1/active-member monthly purse). No Tracker code change -- contracts finalize at Stage 4.",
    ],
  },
  {
    version: "2.35.0",
    date: "2026-07-07",
    changes: [
      "GAME WINNERS ON THE GAMES TAB: following the City/TGF MVP pattern (v2.33.0), the other scorecard-computable side games now shadow-compute their winners from OUR imported scorecards and hydrate 🏆 rows on the Events Games tab: Individual Net (stroke, flighted -- winner names + net scores per flight with golf-style tied positions), Ind. Gross (raw gross per flight), and gross Skins (outright low gross per hole within flight; per-player skin counts shown, ties kill the hole). New engine determine_event_game_results() in database.py + GET /api/events/game-results?event=&game=&flights= (manager). Buyer eligibility reuses the Games-tab rules via the new _event_game_buyers(kind NET|GROSS) generalization of the MVP's buyer helper (credited/refunded/transferred/rsvp_only out; wd out only when that bundle was credited back; child add-on payments upgrade the parent).",
      "Flights are derived by playing handicap over THIS game's buyer set (balanced split, low handicaps first, spares to the earlier flights). The imported scoring_rounds.flight label is NOT used for grouping -- it reflects whatever GG leaderboard the import walked, not this game's cut lines over this game's buyers -- but is returned for cross-checking. The matrix flight count is passed in by the Games tab, which owns the matrix amounts; the server only ranks. Display-only (Stage 1 shadow discipline): GG stays official, no payout-ledger writes.",
      "Deliberately NOT auto-computed, pending Kerry (mailbox topic game-results-wiring): CTP / Longest Putt / Hole-in-One (physical contests -- not in scorecard data; proposal = manual winner entry with CTP carry-over + HIO accrual handling), TEAM Net (off-lowest handicap semantics explicitly deferred by admin + no team-of-record source imported; proposal = use saved Pairings), and Skins ½ Net below 8 gross buyers (half-pop allocation rule unratified -- the row shows 'manual -- ½-net rule pending').",
    ],
  },
  {
    version: "2.34.2",
    date: "2026-07-07",
    changes: [
      "Refreshed docs/claude/state-of-the-tracker.md (the Platform-facing brief served by get_tracker_docs) with the Match Play build wave: versioned season-contest config as the Game Creator engine's first concrete build, the portable pure engine, and the CONTESTS surfaces -- so Platform planning reads a current picture of the V2.0 scoring_config prototype.",
    ],
  },
  {
    version: "2.34.1",
    date: "2026-07-07",
    changes: [
      "Adversarial review pass over the v2.34.0 Match Play build fixed 8 confirmed issues before deploy: (1) a seeded bracket's shape is now frozen -- rendering/auto-advance derive rounds from the SAVED bracket rows, not the live enrollment count, so an enrollment change after seeding no longer hides rounds or advances winners through the wrong template; (2) the payout sheet always splits the combined 3rd/4th money by the expected TWO semifinal losers, so a lone recorded SF loser shows $52.50 (of $105) instead of the full combined amount marked final; (3) two DIFFERENT customers who share a name both count as entrants (dedup is customer_id-first per Principle 6) -- name-dedup only applies to legacy id-less rows; (4) the payout ladder renders any config shape without crashing (no more hard [0]/[1] indexing; places beyond 4th render as TBD rows so the sheet always sums to the pot) and sct_save_version now rejects ladders paying fewer than 2 places; (5) seeding with fewer than 2 qualifiers returns a clear error instead of a 500; (6) the standings 'Advances' badge and header honor the config's advance_per_pool and mention wildcards instead of hardcoding 'Top 2'; (7) a bracket slot's seed/WC chips clear when a different player lands in the slot (stale-chip fix in the upsert); (8) the payout sheet warns when chapterless enrollments are being counted in every chapter's field.",
    ],
  },
  {
    version: "2.34.0",
    date: "2026-07-06",
    changes: [
      "MATCH PLAY lands in CONTESTS as the first Game Creator engine build (Kerry's directive, mailbox ids 18-21). The full 29-column Prizes-Match Play Matrix.xlsx (July 6 final) is now RULES-AS-DATA: pools, knockout size, wildcards, first-round byes, $20/pool-winner bonuses ($25 at N=4), and the payout ladders all live in a versioned admin-editable config -- nothing is hard-coded. New tables season_contest_templates / season_contest_versions (append-only, payout_templates pattern) and season_contest_config_snapshots, which pins a season+chapter to a config version on its first structural action so later template edits never rewrite a season in flight (past-events-frozen). Boot seeds City Match Play v1 from the matrix; test_match_play.py proves the engine reproduces every xlsx column exactly.",
      "New pure engine email_parser/match_play.py (no DB, no Flask -- lifts to the Platform unchanged): structure_for_n (pot $40 x N, bonuses, balanced pool sizes 3-5, ladder bands 71.5/28.5 at N=4 through 50/25/15/10 at N=11+ with whole-dollar overrides where percentages don't divide), largest-remainder cents allocation so payouts always sum to the pot exactly, classic seeded bracket placement (1v8/4v5...) with automatic byes (12-bracket = top 4 seeds skip round 1), and tie splits (semifinal losers split combined 3rd+4th place money).",
      "Match Play tab is now config-driven end to end: a structure banner shows N enrolled -> pools/knockout/wildcards/byes/pot/ladder with the config version badge (pinned state visible); Auto-Assign Pools randomly fills the matrix-prescribed pools from enrollments (refuses to destroy recorded results without confirmation); Seed Knockout moved server-side -- advancers per pool + cross-pool wildcards by Stableford, global seeding (most Stableford points across pool matches, ratified), seed/WC chips on the bracket, Round-of-16 support; new Payouts view computes pool-winner bonuses (leaders provisional until the bracket is seeded) and the knockout ladder with exact-cent tie splits; admins get a Config editor (version history, JSON edit, computed-matrix preview, save-as-new-version, pin-season-to-version).",
      "New API: GET/POST /api/cmp/config(+/versions, /snapshot), GET /api/cmp/structure (?n= or full matrix, ?version_id= preview), POST /api/cmp/pools/auto-assign, POST /api/cmp/bracket/seed, GET /api/cmp/payouts. cmp_bracket gains player_seed / is_wildcard columns (idempotent migration). Design questions posted to mailbox topic match-play-implementation (id 21): N=4/5 ladder per xlsx supersedes the 75/25 note, tie-split default, wildcard rule, bye scope, random-vs-snake pool assignment.",
    ],
  },
  {
    version: "2.33.8",
    date: "2026-07-06",
    changes: [
      "Banked the Platform mailbox exchange (ids 16-20) into the docs. Championship season progression RATIFIED (no multiplier anywhere): best-10 regular season; City Championship 18h Stableford added at face value as a REQUIRED amount (never droppable; winner = Lone Star Cup Captain); Points Reset (v2.22.0 methodology stands); TGF Championship 36h scored with the +1 championship values added to the reset number, placewinners fill LSC rosters. Accumulation model = three phases: best-X, required-add, reset-checkpoint. Closes the last open points-model question.",
      "game-engine.md gains the full Platform reconciliation: the Platform's Game Creator is commerce-only config -- scoring config was never designed, making game-engine.md the V2.0 scoring prototype. Locked entity model recorded (games/bundles/season_contests with scoring_config JSONB hook, hierarchical org_units for scope, no V1.0 versioning -- V2.0 adds ours additively, customer_id maps 1:1 to users.user_id). Season-contest payout economics ratified (NET Bundle $90 = $40 City Net + $40 Fellowship Cup + $10; Cup 1st = 45% flat to $1,008 then threshold taper; Players Cup 4 fixed flights, 10% champion).",
      "NEXT BUILD DIRECTIVE captured from Kerry: wire the ratified Match Play design into CONTESTS -- World Cup pools + wildcards + knockout with seeding/byes, $20 pool-winner bonuses, place ladders on a $40 x N pot, all as admin-editable versioned config; full N=4-32 lookup recorded in game-engine.md; source matrix at OneDrive/01_STANDARDS/Prizes/. Queued as the top item for the next session.",
    ],
  },
  {
    version: "2.33.7",
    date: "2026-07-06",
    changes: [
      "Clarified (per admin's concern about the historically FK-shaky items table) that cross-chapter points routing has ZERO dependency on the items table: the routing key is customers.chapter reached through the customer_id FK that scoring_rounds already carries -- a clean join scoring_rounds.customer_id -> customers.chapter. items.chapter (a per-order event-location snapshot) is never read for identity or routing.",
      "New design-of-record doc game-engine.md: the TGF Game Creator engine (versioned, admin-editable create/edit/version-control for every event game AND season contest) plus the staged untether-from-GG plan (Stage 0 done: parity-verified against GG; Stage 1: parallel shadow leaderboard computing everything ourselves from raw gross hole scores; Stage 2: our own score-entry app, GG out of the loop). Two definition layers (game defs + season-contest defs) with a config-JSON attribute set (scope chapter/TGF-wide/regional, basis net/gross, accumulation best-X/all, months toggle, funding, weighting) mirroring the payout_templates versioning pattern. To be reconciled with the Platform's existing Game Creator planning (TGF Project + OneDrive).",
    ],
  },
  {
    version: "2.33.6",
    date: "2026-07-06",
    changes: [
      "Ratified the points-race scope rules (admin): CITY NET season races route to a player's HOME chapter ONLY (a member is in exactly one city Net race today), so a visitor's net points never count in the host chapter's race. THE PLAYERS CUP (gross) and the MONTHLY races are TGF-WIDE -- everyone's points count regardless of chapter. This resolves the cross-chapter routing open question: the engine routes Net by customers.chapter and pools gross/monthly across all of TGF.",
      "Refined the monthly-race rules (admin): TGF-wide (not per chapter), all members automatically entered (a dues-funded membership benefit, no opt-in), funded $1/month from every membership (purse = $1 x active memberships that month), and it runs only in March-July plus September and October (7 months) -- no August or off-season race. Documented in scoring.md; the canonical active-months list should be encoded as a rule so no phantom August race is invented.",
    ],
  },
  {
    version: "2.33.5",
    date: "2026-07-06",
    changes: [
      "Captured the cross-chapter points-routing requirement (admin): every event can draw members from other chapters, and a visitor earns season points toward THEIR home chapter's race -- in GG this is a manual wire-up each event, which our system must automate. We already hold the data (customers.chapter via customer_id), so the points engine can route each player's Stableford to their home-chapter race automatically. Documented in scoring.md with the open rule to confirm (home-only vs also-host, and monthly handling).",
      "Reframed the points/games documentation: these are TGF standards the admin authored, not GG's. GG is a configurable engine and the current entry surface, not the source of truth; it does not lock a game's definition for subsequent events. The automation goal is for the Tracker/Platform to persist every game as an admin-editable versioned definition that applies to future events by default -- the definitions captured in side-games.md ARE that lock, and the GG cross-checks confirm our encoding matches the admin's standard.",
    ],
  },
  {
    version: "2.33.4",
    date: "2026-07-06",
    changes: [
      "NET points schedule VALIDATED against Golf Genius's own game configuration. The admin supplied the GG setup for the SAN ANTONIO Net points game (category 26-SAn): its Assign Points row reads HIO 8, Triple Eagle-or-Better 4, Double Eagle 4, Eagle 3, Birdie 2, Par 1, Bogey 0, Double Bogey -1, Triple Bogey -1, Others -1 -- an exact match to our net table on every category, including Others = -1 (a direct match to our clamp, unlike the gross game where Others = 0). Both net and gross points schedules are now GG-config-validated.",
      "Confirmed one net game feeds multiple point categories -- the season chapter race (26-SAn) and the monthly race (26-Jun) draw from the SAME per-event net Stableford -- validating the model that monthly (all points) and season (best-10 + City Championship) accumulate identical numbers differently. Flagged one curiosity for the admin: the same net game also lists AUSTIN Net (26-An), unexpected for a San Antonio game. Docs gain the authoritative NET points game definition; no code change required.",
    ],
  },
  {
    version: "2.33.3",
    date: "2026-07-06",
    changes: [
      "GROSS points schedule VALIDATED against Golf Genius's own game configuration. The admin supplied the GG setup for THE PLAYERS CUP gross points game (category TPC26reg, Handicap None/Gross): its Assign Points row reads HIO 8, Triple Eagle-or-Better 16, Double Eagle 16, Eagle 8, Birdie 4, Par 2, Bogey 1, Double Bogey 0, Triple Bogey -1, Others 0 -- an exact match to our corrected table on every reachable category. This is GG's authoritative config, so no eagle round was needed to confirm it. GG lists both a Hole-in-One box (8) and a Triple-Eagle box (16), which with the admin's 'award the higher' rule validates our max(HIO, vs-par) implementation (a par-5 ace scores 16, not 8). 'Others = 0' is a no-score / worse-than-triple catch-all, unreachable for played holes under the Max Triple cap; our engine matches both ways. Docs updated with the authoritative gross game definition; no code change required.",
    ],
  },
  {
    version: "2.33.2",
    date: "2026-07-06",
    changes: [
      "Finalized the hole-in-one and championship points rules per admin. A RAW hole-in-one (actual ace, gross strokes == 1) is also a hole result, so it now awards the HIGHER of the 8-point HIO bonus and its vs-par value -- never both: a par-3 ace scores 8 (its eagle value equals the bonus), a par-4 ace scores 16 gross (double eagle beats the bonus), 8 net. A \"net hole-in-one\" (a net 1 reached via handicap strokes) is not a raw ace and is scored normally. Applies to both net and gross (max of bonus vs table).",
      "Championship schedule RATIFIED (resolves the earlier +1 contradiction; it is asymmetric): the NET table gets +1 on every category including the HIO bonus (par 1->2, birdie 2->3, ... HIO 8->9), while the GROSS table keeps its vs-par values and only the raw-HIO bonus goes +1 (8->9) -- so a championship par-3 ace scores 9 gross. get_championship_formulas() builds this for the live-standings engine; per-event championship selection is future wiring. Verified across 22 regular + championship cases.",
    ],
  },
  {
    version: "2.33.1",
    date: "2026-07-06",
    changes: [
      "Corrected the GROSS Stableford points table to the admin's actual values: birdie 4, eagle 8, double eagle 16 (the code previously had eagle 4 / double eagle 8 -- both wrong). Added a raw hole-in-one override for GROSS: an actual ace (1 stroke) scores the HIO value (8) regardless of par, so an ace on a par 4/5 gets 8 rather than a double/triple eagle -- only HIO points apply. The value is admin-tunable (stableford_gross_hio).",
      "Corrected the NET Stableford table: the -4 bucket was 8 (a mistaken hole-in-one encoding) and is now 4 (triple-eagle-or-better). NET has no hole-in-one bonus -- a net ace is scored as its net achievement (a net eagle or better). Ordinary net totals (par/birdie/bogey) are unchanged, so MVP and net points standings for normal scores are unaffected; only net-triple-eagle holes and all gross totals shift to match GG. Verified across the full table plus the TGF MVP determination suite.",
      "Championship points schedule is documented but NOT yet coded: two admin readings conflict (+1 on all categories vs +1 on the hole-in-one only) and are held pending re-confirmation. See scoring.md.",
    ],
  },
  {
    version: "2.33.0",
    date: "2026-07-06",
    changes: [
      "TGF MVP determination AUTOMATED (admin: 'Build it') -- the manual step GG cannot do. determine_tgf_mvp() computes each linked same-day event's City MVP from our imported scorecards through the formula layer (highest net Stableford POINTS among NET-bundle buyers; tiebreakers Individual Net stroke score, then Gross, then split) and names the TGF MVP (higher day points across the day's events; ties split with no further tiebreaker). Buyer eligibility mirrors the Games-tab rules exactly, including child add-on upgrades and wd/net-credited exclusions.",
      "Surfaced three ways: GET /api/events/tgf-mvp (manager), new MCP tool determine_tgf_mvp (61 tools), and trophy winner rows on the Events Games tab -- the City MVP row and combined TGF MVP block now lazy-hydrate the computed winners, with honest 'awaiting results' and single-event-day states. GG-recorded MVP names are returned alongside for cross-checking. Verified against a synthetic database across five scenarios (determination, single-event day, TGF tie split, City tiebreaker on Individual Net, awaiting-results).",
    ],
  },
  {
    version: "2.32.13",
    date: "2026-07-06",
    changes: [
      "Leaderboard information architecture captured from admin: horizontal tab nav (Team / Gross / Net / Skins / Points / Proxies) replacing GG's vertically stacked game lists, with Match Play as a contextual tab shown only on bracket-match days. Also documented the GG friction the live leaderboard removes: points games need dedicated divisions with season points attached, and points post only after the round.",
    ],
  },
  {
    version: "2.32.12",
    date: "2026-07-05",
    changes: [
      "Championship points weighting captured from admin (resolves the open business rule): City Championship and TGF Championship use the regular Assign Points schedule shifted +1 per category -- net values Triple 0 / Double 0 / Bogey 1 / Par 2 / Birdie 3 / Eagle 4 / Double Eagle 5 / HIO 9 (~+1 point per hole vs regular events). The live-standings points engine must select the schedule per event; documented in scoring.md points model and side-games.md.",
      "MVP definition precision per admin: City MVP is the highest net Stableford POINTS (per the MVP Assign Points schedule), not the best net stroke score, among NET buyers.",
    ],
  },
  {
    version: "2.32.11",
    date: "2026-07-05",
    changes: [
      "Docs: MVP Stableford schedule confirmed as NET Stableford; MVP-vs-POINTS structure recorded (MVP = per-event buyers-only game; POINTS = separate GG game capturing the same net Stableford for the whole field). Admin's Platform consolidation concept captured: one leaderboard computing net AND gross Stableford for everyone -- net points column serves the points race, gross column serves THE PLAYERS CUP, MVP = best net among color-coded entrants (buy-in flag from commerce data) -- collapsing three GG games into one live view.",
      "TGF MVP recording documented as a manual step today (GG cannot configure it); flagged as a prime Tracker automation target since the Events Games tab already computes the pot and same-day link awareness -- only winner determination (compare linked City MVPs' points, tie splits) needs building.",
    ],
  },
  {
    version: "2.32.10",
    date: "2026-07-05",
    changes: [
      "Matrix page now opens to the 9-hole games by default (admin request) — the toggle previously landed on 18 holes.",
      "Team Net variant rules ratified into side-games.md from admin answers: allowance follows ball count per USGA standard recommendations (Best 1 -> 75%, Best 2 -> 85%, Best 3/4 -> 100%); automation should rotate Best 1 / Best 2 every other event with admin override for the other variants; gross Max Triple caps the recorded score in ALL games (net pops apply from the capped gross); off-lowest handicapping scopes to the competition (flight, field, or the two players in a match) with details deferred to a dedicated session.",
      "GG setup definitions v1 added for MVP and Individual Net from admin screenshots. MVP: Stableford (custom schedule: ace 8, eagle 3, birdie 2, par 1, bogey 0, double/triple -1), NET division only, USGA Net 100%, winner-take-all purse -- s9.16's $42 pot cross-checks the multi-event-day $2/NET-buyer City MVP half-share at 21 buyers. Individual Net: Stroke, Player v. Flight, per-flight purse $63/$31.50 -- 2 flights x $94.50 = $189 = $9 x 21 buyers, matching the matrix N=21 row verbatim. Both games carry the Max Triple rule; individual games use plain USGA Net while team games use off-lowest.",
    ],
  },
  {
    version: "2.32.9",
    date: "2026-07-05",
    changes: [
      "Per admin ruling, the 9-hole Individual Gross flight payouts at 16-19 players snap to exact division ($21.33/$22.67/$24/$25.33 = pot / 3 flights, replacing the hand-rounded whole dollars). Boot repair now enforces the gross-flight payout formula matrix-wide: flight pot = Ind Gross pot / flights, winner-take-all per flight, 2/3-1/3 split once a 2nd place is in play (18h 48+, verified already exact). Seed regenerated.",
      "GG game SETUP layer begins in side-games.md from admin's screenshots: TEAM Net definition v1 (Stroke / Foursome v. Field / Best Ball each hole / USGA Net off-lowest at 75% / Retain Ties / winner-take-all purse from matrix -- s9.16's $128 pot cross-checks exactly as $4 x 32 players) plus GLOBAL standards: Maximum Playing Handicap 36 (18h) / 18 (9h) for all genders and games (never more than 2 pops a hole), Disallow Strokes on Par 3 Holes for all team competitions, and the gross Max Triple pickup rule. Standard variation noted: alternate events run Best 2 Balls at 85%.",
    ],
  },
  {
    version: "2.32.8",
    date: "2026-07-05",
    changes: [
      "LIVE prize-matrix audit complete (via get_side_games_matrix, source app_settings). Admin's Matrix UI edits CONFIRMED: Individual Gross now activates at 16 players (9h) / 12 players (18h) with self-consistent pots (Ind Gross $4/$8 per buyer, Skins $9/$18, gross pool intact at $13/$26), plus an 18-hole Team Net 1st/2nd split extended down to 32 players. Earlier repairs verified applied with zero collateral on admin-edited rows.",
      "Two stale companion-cell families the Matrix UI edits did not recompute, now auto-repaired: 18h N=12-15 skins payout arrays still showed FULL-pool values (would overpay skins ~44% at those buyer counts; 36 cells -> flight pot / skin count) and 18h N=32-35 teamMWP still showed the winner-take-all value after the 1st/2nd split (4 cells -> team1st / 4). Boot repair extended to cover both matrices and the ratified MWP formula; repo seed regenerated from the repaired live copy so fresh boots keep the admin's 16/12 thresholds. side-games.md updated to live-verified rules.",
    ],
  },
  {
    version: "2.32.7",
    date: "2026-07-05",
    changes: [
      "Events Games tab now applies the MVP day-type rule the admin ratified: when a 9-hole event has NO linked same-day TGF event (single-event day, or the other nine unlinked/rained out), the TGF MVP money folds into City MVP (shown as 'City MVP (incl. TGF $)' at the full $4/buyer) instead of rendering a phantom standalone TGF MVP game. Admin relink buttons still appear so a mistakenly-unlinked nine can be reattached.",
    ],
  },
  {
    version: "2.32.6",
    date: "2026-07-05",
    changes: [
      "New MCP tool get_side_games_matrix (60 total) serves the LIVE prize matrix from the database — the copy the Matrix UI actually edits. Root cause documented: UI saves rewrite the repo's games-matrix.js only on Railway's ephemeral disk, so the checked-in seed silently drifts from live (the admin's Ind Gross minimum changes to 16/12 players never reached the seed). The seed-based audit will be re-run against the live matrix; the v2.32.5 boot repair was value-guarded so it could not touch legitimate edits.",
    ],
  },
  {
    version: "2.32.5",
    date: "2026-07-05",
    changes: [
      "Prize matrix audit (admin-requested) complete, with two defects found and FIXED: the 9-hole GROSS Total Pot column overstated at $15/buyer for fields of 20+ while its own game pots correctly summed to the ratified $13 (45 cells corrected — this also fed the Events Games-tab gross subtotal), and one bad skins cell at 18 players (24.67 -> 39.00). A boot repair patches the live DB matrix copy; the static seed is corrected in-repo. Not defects: the audit proved the 'lost Excel formulas' survive as encoded rules — CART Net pairs below 16 players (team pot absorbs the CTP money), Individual Gross cancelling into Skins at low buyer counts (real-world confirmed: s9.16 skins purse $195.01 = 13 x 15 buyers), and the 18-hole MVP $100 cap flowing excess into Individual Net.",
      "teamMWP identified by admin as Maximum Winnings Potential (one player's max share of the team game, = team 1st / team size — verified exact) feeding the Events Games-tab MWP column; deletion recommendation retracted. side-games.md updated with the audit, the MVP day-type rule (single 18h-event day: City MVP capped $100 with excess to Individual Net; multi-event day: $4+$4 uncapped pending confirmation), and the CART Net / rollover rules.",
    ],
  },
  {
    version: "2.32.4",
    date: "2026-07-05",
    changes: [
      "side-games.md promoted from draft to RATIFIED SPEC v1.0 after the full mailbox reconciliation with the Platform planning docs (admin ratified all eight open items same-day): buy-in pricing with pool/markup decompositions and the combo-event nuance, CTP flat-entry + Longest Putt fallback + shortest-par-3 selection + carryover rule, hole-in-one accrual with members-only wins, MVP $4/$8 with the single-vs-multi-event-day split and full tiebreaker chain, TGF MVP higher-points rule, and Match Play season payouts (50/25/15/10).",
      "Prize matrix fully decoded and published: every line is a per-buyer multiple with flight-count bands; skins arrays verified as flight-pot / skin-count. teamMWP mystery resolved — a vestigial column from the source spreadsheet that no payout logic reads; recommended for deletion. Three new discrepancies flagged for the admin: the 9-hole GROSS pool pays $15/buyer above 19 buyers vs the pricing doc's $13, the 18-hole MVP pot caps at $100 flat in the matrix, and one skins-array data-entry anomaly at N=18.",
    ],
  },
  {
    version: "2.32.3",
    date: "2026-07-05",
    changes: [
      "New docs/claude/side-games.md: the full side-games catalog reverse-engineered from live GG portal results and reconciled against the prize matrix — fee architecture ($7/player event game money, $13 NET package, $15 GROSS package), TEAM Net best-ball with blind draws, flighted Individual Net/Gross and Skins, city/TGF MVP pots at $2/buyer, CTPs at $1/player, hole-in-one reserve, and season match play brackets. Marked DRAFT pending admin verification; open questions listed (teamMWP meaning, CTP no-winner handling, GROSS $2 residual, first MVP tiebreaker).",
    ],
  },
  {
    version: "2.32.2",
    date: "2026-07-05",
    changes: [
      "State-of-the-Tracker brief completeness pass: added the handicap system (9-hole index, manual GG CSV ritual, Phase 2 parity goal), participation analysis / re-engagement, and automated expense ingestion — pre-existing systems that matter to Platform planning but were missing from the Platform-facing brief.",
    ],
  },
  {
    version: "2.32.1",
    date: "2026-07-05",
    changes: [
      "Points model fully verified across BOTH race types and recorded in scoring.md: race points = the player's Stableford score in that race's POINTS game floored at 0 (net Stableford for the NET races, gross for THE PLAYERS CUP), best 10 + City Championship for both. GROSS confirmed via Pat Youngs (3rd place, gross Stableford 13 -> 13 points; five wins paying 25/23/22/21/19 rule out any position table) and the 0-floor confirmed directly via a -6 gross round showing 0 awarded. First real exchange completed over the new platform dialogue mailbox (entries 2-4).",
    ],
  },
  {
    version: "2.32.0",
    date: "2026-07-05",
    changes: [
      "Platform collaboration bridge (3 new MCP tools, 59 total): get_tracker_docs serves the living documentation (CLAUDE.md + docs/claude/*) to any connected Claude — built for the claude.ai Golf Fellowship Project so Platform planning always sees the current built state; read_platform_dialogue / post_platform_dialogue are a durable two-way mailbox (platform_dialogue table) between the Project and the Tracker's coding sessions — both sides write, no more copy/paste relaying. Boot seeds a welcome post on first deploy.",
      "New docs/claude/state-of-the-tracker.md: the Platform-facing brief covering everything built through v2.32 — modules, verified league mechanics (Stableford points model, monthly purses, MVP semantics), in-flight work (live championship standings, live-updates ladder, own live scoring), and the app roadmap. Standing workflow rule added: read the mailbox at session start, post a digest at session end, refresh the brief after major build waves.",
      "Platform stack note: Supabase (managed Postgres + auth + realtime + row-level security) recorded as the scoped database for the TGF Platform in the roadmap docs.",
    ],
  },
  {
    version: "2.31.3",
    date: "2026-07-05",
    changes: [
      "Platform roadmap folded into docs/claude/member-portal.md as the plan of record: one backend with two faces (admin website + member app), phased as mobile-first portal (live) -> PWA with offline score entry -> Capacitor native wrap with store listings and push -> native extras. Also records the points-model finding (race points = net Stableford floored at 0, verified against GG member details) that unblocks live championship standings.",
    ],
  },
  {
    version: "2.31.2",
    date: "2026-07-05",
    changes: [
      "Customers page auto-refresh now checks whether the data actually changed before rebuilding the page (a fingerprint of the synced payloads). Most 30-second ticks change nothing, so the page sits perfectly still — scroll position, expanded cards, open scorecards, and the active tab are physically untouched. When something did change, the full rebuild runs exactly as before. First rung of the live-updates ladder (next: targeted row updates, then true push for live event standings).",
    ],
  },
  {
    version: "2.31.1",
    date: "2026-07-05",
    changes: [
      "Fixed the mobile customer card snapping back to the Transactions tab moments after opening Points (or Scores/Winnings/Info): the page's 30-second auto-refresh rebuilds every card, and the mobile template hardcoded Transactions as the active tab. Mobile now persists the active tab across re-renders like desktop, and reloads the open tab's content after each refresh so it never sits on a stuck 'Loading…'.",
    ],
  },
  {
    version: "2.31.0",
    date: "2026-07-05",
    changes: [
      "Customer Points tab is live (was 'Feature Coming Soon'). Expanding a customer and opening Points shows every points race the player appears in — rank, total points, rounds, wins — with the same DATE | EVENT | PTS | POS round-by-round breakdown as the Contests drill-downs; points lines with an imported scorecard expand to the hole-by-hole card in place, MVP badges included. A MONTHLY RACE strip lists the player's month totals and rank with wins highlighted gold and the $ share shown. Imported rounds without a points line follow in their own list.",
      "Race membership comes from the persisted Golf Genius standings snapshot via the new /api/customers/<id>/gg-cards endpoint — no live GG wait, freshness rides the standings' existing 12-hour auto-refresh.",
      "The Contests drill-down renderers (points tables, rounds lists, hole-by-hole scorecard, badges, formatting) moved from contests.html into shared static/js/points-render.js so the Contests page and the customer Points tab render from one code path and can never drift apart. No visual change on Contests.",
    ],
  },
  {
    version: "2.30.3",
    date: "2026-07-05",
    changes: [
      "Fixed player-name links from Contests landing on the Customers page with 'can't find': the deep link now carries the customer id (?cid=) instead of the Golf Genius-format name, which never matched the tracker's 'Last, First' cards. The name fallback also matches loosely now (order- and case-insensitive) for any remaining name-only referrers.",
      "MONTHLY standings persist in the database (gg_data_snapshots) instead of re-fetching Golf Genius whenever the old 10-minute cache went cold — opening the tab is now instant. A scheduler job refreshes the snapshot daily at 5:30 AM Central, the Refresh button still pulls live on demand, and desktop shows an 'as of' stamp next to it. First boot after this release queues a background fetch so nobody waits.",
    ],
  },
  {
    version: "2.30.2",
    date: "2026-07-04",
    changes: [
      "MONTHLY player expansion now matches the other drill-downs: the same DATE | EVENT | PTS | POS points table (pulled from the player's chapter season page, filtered to the month) with clickable rows opening the hole-by-hole scorecard — no counted/not-counted split since ALL points count monthly. Imported rounds without a points line follow in an OTHER ROUNDS THIS MONTH list.",
      "Bottom-level expand chevrons sit LEFT of the event name everywhere (points-detail rows and rounds lists) per admin preference.",
      "Rounds-list dates use the same month-day formats as the points tables: 'Jun 30' on desktop, '6/30' on phones (a regression had them back at full ISO).",
      "MONTHLY chapter column on phones now shows initials only — 'A' for Austin, 'SA' for San Antonio — AUS overflowed the narrow column.",
    ],
  },
  {
    version: "2.30.1",
    date: "2026-07-04",
    changes: [
      "MONTHLY tab refinements per admin: player rows now expand to that month's rounds (each opening the same hole-by-hole scorecard as everywhere else); a PURSE column shows the winner's split on final months and the projected total on the current leader for in-progress months; the title and purse-calculation summary lines are gone (the month tabs carry the context); Refresh is now a small inline button right of the month tabs.",
      "Fixed the Chapter column showing San Antonio for every player: the merge stamped the portal's chapter instead of each row's affiliation — and since the monthly tables are TGF-wide, the SA portal's pass won every row. Chapter now comes from the player's own affiliation.",
      "All expand chevrons in the points-race drill-downs are bigger and blue (primary color) so they read as tappable.",
    ],
  },
  {
    version: "2.30.0",
    date: "2026-07-04",
    changes: [
      "MONTHLY points races: a new MONTHLY tab under Points Races with a month nav bar (every month the portals have published, completed or in progress). Standings come live from each portal's '<MONTH> Points' pages (both chapters merged; a cross-chapter player keeps their higher portal total, never a double-counted sum) — ALL points earned in the month count, no best-10 cap. Completed months highlight the winner (gold row + trophy) and show the award: $1 per active TGF member as of the close of that month (from customer_memberships), split on ties. In-progress months show the projected purse. Served by /api/season-contests/monthly-points (10-minute cache, ?force=1 via the Refresh button).",
      "Dash normalization per admin: every en/em dash in drill-down labels renders as a plain hyphen, and the server-side Front/Back suffixes now use '- Front'/'- Back'.",
      "s9.16 renamed to 's9.16 TPC San Antonio | Oaks' (was 'TPC Oaks'), and the nine-suffix logic now falls through to Front/Back when the course's nine name is already part of the event name — so s9.16 and s9.9 read '… | Oaks - Front' / '… | Canyons - Front' from their actual hole ranges. Hill Country Matches league rounds are exempt (true 9-hole nines have no front/back).",
      "Mobile MVP badges drop to their own line under the event name unless the name is long enough to wrap already (then they stay inline at the end).",
    ],
  },
  {
    version: "2.29.2",
    date: "2026-07-04",
    changes: [
      "9-hole events at 18-hole courses now say which nine was played: matched event lines append ' - Front' or ' - Back' from the round's actual hole range (holes 10-18 = Back). Named-nine facilities keep their nine's name (Oaks, Valley, Hills) as before; 18-hole Front/Back splits already carried the suffix from GG.",
      "MVP backfill ran across all three portals after the v2.29.1 walker fix: San Antonio 32 winners over 21 rounds, Austin 26 winners over 18 rounds, Hill Country Matches none (no MVP games in the matches league) — 58 records, every name resolved to a customer profile. Badges are live in the drill-down.",
    ],
  },
  {
    version: "2.29.1",
    date: "2026-07-04",
    changes: [
      "MVP importer hotfix: parse_page_structure requires the page URL for link resolution — the v2.29.0 walker crashed on its first fetch. Both call sites now pass it.",
      "Scorecard legend trimmed per admin: the '(doubled = by 2+) — gross row vs par, net row vs net' tail is gone everywhere; the legend now reads '● = handicap stroke · ○ = plus stroke · ⊖ under par · ⊞ over par'. Desktop drill-down POS values are centered under their header.",
    ],
  },
  {
    version: "2.29.0",
    date: "2026-07-04",
    changes: [
      "MVP badges: a new event_mvps layer imports each event's 'MVP $' and 'TGF MVP $' games from Golf Genius (winner = the purse>0 rows, which is how GG records tiebreaker outcomes — one MVP per city per event, TGF MVP can be shared; a tied MVP with no purse posted is left unresolved rather than guessed). The points drill-down and Non-Points Events list show an amber MVP pill and a teal TGF MVP pill right of the event name. Import via the scoring-mvp-import bridge command (walks a portal's rounds with a time budget; repeated calls converge).",
      "Points drill-down polish batch per admin: section list renamed to NON-POINTS EVENTS; mobile banners shorten to COUNTED (Best 10 + City Championship) / NOT COUNTED; mobile dates go M/D (3/24); desktop date header is just DATE and POSITION is POS; Hill Country Matches lines read HILL COUNTRY MATCHES - R1 Valley (round number + nine, ALL CAPS on desktop, standard case on phones); matched lines append the nine played when the course carries one (s9.14 Hill Country - Oaks) or Front/Back for 18-hole splits.",
      "Points column alignment: on desktop the drill-down's POINTS column now lines up exactly under the standings POINTS column (90px + a spacer mirroring RESET/Rounds/Buy-in; the drill-down row lost its side indent to make the geometry true). On phones the spacer is gone — PTS rides the right edge with breathing room instead of being pinched in the middle.",
      "Scorecard footer slimmed per admin: the Gross/Net/Stableford totals (already visible in the grid) are gone; the note line now carries Adjusted Gross plus the round's Differential computed from the tee's slope/rating — the same formula as the Phase 2 parity engine. Legend shortens to '● = handicap stroke · ○ = plus stroke'. Portal renderer matched.",
    ],
  },
  {
    version: "2.28.15",
    date: "2026-07-04",
    changes: [
      "Points drill-down columns reordered per admin spec: DATE | EVENT | PTS | POSITION (points were on the left, which read backwards under a standings header whose points sit right of the player). Dates render as mmm d (May 16); on phones POSITION hides and the date shows instead, and the PTS column gets the same centered/bold/2px-bordered treatment as the standings PTS column plus a 94px trailing spacer that mirrors the standings' RESET+R+IN block, so the two points columns align exactly. The Other Scorecards list uses the same date format.",
      "Austin Kickoff points lines now match their rounds: Golf Genius labels them just 'Kickoff' with no a18.2 code (admin confirmed they're the same event), so the name substitution gained a first-word override (Kickoff → a18.2 AUSTIN KICKOFF | ShadowGlen) and a series fallback that resolves GG's a18.3 to the tracker's 'a18 CRYSTAL FALLS' event; the drill-down matcher tolerates the same series-only lookup client-side.",
    ],
  },
  {
    version: "2.28.14",
    date: "2026-07-04",
    changes: [
      "Hill Country Matches rounds now match their points lines instead of duplicating into the scorecards list below. Two fixes: (1) GG's HCM tournament codes grew a suffix (hcmR1 → hcmR1nm) that broke the code parser, so the admin label overrides (Valley/Hills/Creeks) silently stopped applying — the parser now handles compound codes and falls back to the stripped base; (2) the drill-down matcher gained a league fallback for code-less lines: base-name prefix plus qualifier-vs-course matching links 'Hill Country Matches - Valley' to the imported Comanche Trace round whose course carries VALLEY.",
      "OTHER SCORECARDS renamed to SCORECARDS WITHOUT A POINTS LINE with an explainer (desktop): investigation of the admin's report showed rounds like s9.12, s9.5, s18.1, and s18.2 sit there because Golf Genius's own member cards have no points rows for those tournaments (verified by fetching a card directly — 0-point rows do appear, so absence means the race never awarded that event). That's a GG-side configuration gap, not an import problem; the section title now says what the section actually holds.",
    ],
  },
  {
    version: "2.28.13",
    date: "2026-07-04",
    changes: [
      "Wrapping is now opt-in per cell instead of table-wide: v2.28.12's blanket white-space:normal let unintended cells fold (content wrapping under the RDS column in the standings). A pr-wrap class now marks exactly the cells that may wrap — event names (drill-down + Other Scorecards), the counted/not-counted section banners, flight header bars, and the scorecard's summary/legend container — while players, numbers, dates, and badges are single-line again.",
      "Mobile standings Rounds header shortened from RDS to R (full word in the tooltip).",
    ],
  },
  {
    version: "2.28.12",
    date: "2026-07-04",
    changes: [
      "THE actual wrap bug, found and killed: dashboard.css sets a GLOBAL tbody td { white-space: nowrap } that every table on every page inherits — which is why event names, the section banners, and even the scorecard legend never wrapped no matter what wrapping properties were added. The contests enrollment tables now restore white-space: normal (cells that need nowrap, like dates, set it inline).",
      "Phone display of Golf Genius event names is de-shouted: ALL-CAPS runs become Title Case (KISSING TREE → Kissing Tree; acronyms TPC/TGF/HCM stay uppercase; single letters like the L in Flying L Ranch survive) and 'San Antonio' abbreviates to 'SA' (SAN ANTONIO KICKOFF → SA Kickoff). Display-only — scorecard matching still uses the raw name; desktop shows names exactly as GG sends them.",
      "Counted banner: the (Best 10 + City Championship) parenthetical is now standard case and unbolded so it fits beside POINTS COUNTED without competing; the POINTS NOT COUNTED banner lightens from 40% to 25% gray per admin spec.",
    ],
  },
  {
    version: "2.28.11",
    date: "2026-07-04",
    changes: [
      "Event-name wrapping finally works on phones: Safari ignores overflow-wrap inside table cells, so compact cells now also carry word-break:break-word (the property Safari does honor in tables), and the space normalizer was rebuilt on \\s so it collapses every Unicode whitespace plus zero-width characters. Long names like the Cedar Creek events wrap to a second line inside their cell.",
      "Points drill-down restyle per admin spec: a black banner with white text reading POINTS COUNTED (BEST 10 + CITY CHAMPIONSHIP) opens the counted section, and a 40% gray banner with black text reading POINTS NOT COUNTED replaces Golf Genius's 'following points are not counted' sentence row. With the banners carrying the contrast, event rows are no longer bold on phones (bold stays on desktop).",
      "Contests tab strip (POINTS RACES / MATCH PLAY / ENROLLMENT) now matches the site nav's sizing (0.82rem, weight 600) with viewport-scaled padding so all three tabs fit on a phone screen without sliding.",
      "POINTS RACES is now the first tab and the landing view when opening Contests — it loads immediately on page open; Match Play still warms in the background so switching to it stays instant.",
    ],
  },
  {
    version: "2.28.10",
    date: "2026-07-04",
    changes: [
      "Long event names now wrap inside their cell instead of running across the POS column (the Cedar Creek case): the drill-down's space normalizer now catches the full family of exotic Unicode spaces Golf Genius emits (narrow no-break, en/em spaces, zero-width, BOM — not just plain &nbsp;), and compact table cells carry overflow-wrap:anywhere as a hard guarantee that text breaks rather than paints over a neighbor.",
      "The scorecard's summary line (Gross/Net/Stableford) and symbol legend were running off screen without wrapping — their &nbsp;-glued separators defeated line breaking. On phones they now use plain separators and a viewport-width cap, so they fold into multiple lines.",
      "Row hover highlighting is now limited to hover-capable devices — on iPhones the desktop :hover background stuck to whatever row you last tapped (the lavender row in the drill-down) until you tapped somewhere else.",
    ],
  },
  {
    version: "2.28.9",
    date: "2026-07-04",
    changes: [
      "Every navigation strip now slides sideways independently of the page when it's wider than the screen: the site nav (ADMIN / TRANSACTIONS / …), the Contests top tabs (MATCH PLAY / POINTS RACES / ENROLLMENT), the race sub-tabs, and the admin sub-nav. Swipe the strip itself to reach the cut-off tabs; the rest of the page stays put. This is base CSS, not a mobile breakpoint — phones in desktop-site mode report a wide viewport and skip media queries, which is why the existing mobile-only nav scrolling never kicked in.",
      "Fixed the overlapping text in the points drill-down (level 2): Golf Genius separates words with non-breaking spaces, so event names couldn't wrap and painted straight over the AWARDED DATE column in the width-locked compact tables. Cell text is now normalized to regular spaces (which also hardens scorecard matching), and on phones the AWARDED DATE column is dropped entirely and POSITION narrows to a 34px POS column — points, event, and position all fit with no overlap.",
      "Scorecard (level 3) narrowed one more notch on phones (0.58rem type, slimmer cells and score rings) so the full nine plus OUT/IN totals fit comfortably on screen. Portal renderer matched.",
    ],
  },
  {
    version: "2.28.8",
    date: "2026-07-04",
    changes: [
      "Points-race drill-down (level 2) is now compact on phones: the round-by-round points tables shrink to the same tight type as the standings, the POINTS column narrows to a 34px PTS column (it was auto-sizing very wide), and the detail row's side indent drops from 1rem to almost nothing so the event names get the width.",
      "OTHER SCORECARDS list on phones: Course/Tee folds into a muted second line under the event name, the date shortens to MM/DD, and Holes/Gross/Net headers abbreviate to H/G/N — the full 7-column desktop layout no longer runs off screen.",
      "Compact tables now use table-layout:fixed, which makes the declared column widths binding — nothing can push the right-edge columns (the IN badge was slightly clipped in v2.28.7) off screen; long names wrap inside the Player cell instead.",
      "Scorecard (level 3) tightened on phones — 0.62rem type, slimmer cells — so a full nine plus the OUT column fits the screen at once; and because the standings/detail tables are width-locked now, an expanded scorecard pans inside its own row instead of stretching the whole drill-down (which is what was spreading level 2 out). Portal renderer updated to match.",
    ],
  },
  {
    version: "2.28.7",
    date: "2026-07-04",
    changes: [
      "Points-race standings now fit entirely on a phone screen — no more POINTS column cut off at the right edge. On phones the standings tables (all four tabs: San Antonio NET, Austin NET, The Fellowship Cup, The Players Cup) switch to a compact variant: narrow fixed columns, tighter cell padding, short headers (# / PTS / RESET / RDS / IN), the buy-in badge collapses to just ✓ / ✗ / ?, and chapter names abbreviate (San Antonio → SA, Austin → AUS) with the full value in the tooltip. Desktop layout is unchanged.",
      "The two points-race cards' side padding shrinks on phones (their inline 2rem padding was eating 64px of table width), and the standings container got an overflow-x guard as a fallback so any residual overflow pans inside the card instead of stretching the page.",
      "The phone-detection logic (viewport media query OR physical screen ≤ 640) now lives in one shared prIsCompact() helper used by both the standings tables and the scorecard renderer.",
    ],
  },
  {
    version: "2.28.6",
    date: "2026-07-04",
    changes: [
      "Fixed the giant text on the tracker's mobile Contests drill-down: iOS Safari 'font boosting' inflates text whenever page content is wider than the screen, and the wide fixed-width standings tables triggered it — expanding a player made all the text grow and the scorecard showed only about one hole. Contests and My TGF pages now pin text-size-adjust to 100% so Safari never rescales.",
      "The inline scorecard's scroll container is now capped at the viewport width (max-width: calc(100vw - 2rem)) on both the Contests drill-down and the member portal, so the card pans horizontally inside its own box instead of stretching the page.",
    ],
  },
  {
    version: "2.28.5",
    date: "2026-07-03",
    changes: [
      "Compact scorecard detection now also checks the PHYSICAL screen (smaller dimension <= 640 CSS points): the media query alone reports a wide viewport when a phone runs in desktop-site mode or inside the tracker's wide admin tables, which is why the compact card showed on the portal but not the Contests drill-down. Phones now get the compact card everywhere; iPads/desktops keep the full layout.",
    ],
  },
  {
    version: "2.28.4",
    date: "2026-07-03",
    changes: [
      "Compact scorecard on phones: on screens up to 640px the card renders with tighter cell padding, smaller type, narrower score rings, and abbreviated row labels (GROSS / G PTS / NET / N PTS / YDS) so a full nine fits with minimal horizontal scrolling. Desktop rendering is unchanged. Applies to both the Contests drill-down and the member portal (shared logic in each renderer).",
    ],
  },
  {
    version: "2.28.3",
    date: "2026-07-03",
    changes: [
      "Handicap-stroke dots moved from the GROSS SCORE row to the NET SCORE row (admin request) — the dots are what turn gross into net, so they now annotate the number they produce. Gross row shows the clean score with its vs-par symbol; net row carries the corner-pinned dots plus its net-vs-par symbol. Both renderers (Contests drill-down + member portal).",
    ],
  },
  {
    version: "2.28.2",
    date: "2026-07-03",
    changes: [
      "Scorecard dot-marker fix: handicap-stroke dots were wrapping under the score number on narrow (mobile) cells, pushing scores out of line — dots are now pinned to the cell's top-right corner (like a printed card) and cells no longer wrap, so the number always stays centered.",
      "Scorecard rows regrouped per admin: GROSS section (GROSS SCORE bold, GROSS PTS directly beneath on a grey band) then NET section (NET SCORE bold, NET PTS beneath on grey), each opened with a thick border — scores read visually stronger than points. Applied to both the Contests drill-down and the member portal renderer.",
    ],
  },
  {
    version: "2.28.1",
    date: "2026-07-03",
    changes: [
      "Scorecard symbols now match their row (admin request): the GROSS SCORE row's circles/squares reflect the GROSS score vs par, and the net-relative symbols moved to the NET SCORE row. Both are computed from tracker facts (vs_par / net_vs_par) — GG's own markings, which are net-relative, stay stored untouched and are used only by the verifier. Applied to both the Contests drill-down and the member portal renderer; legend updated.",
    ],
  },
  {
    version: "2.28.0",
    date: "2026-07-03",
    changes: [
      "MEMBER PORTAL M1: /me — a mobile-first personal page each member opens with their own magic link (HMAC-signed per-customer token; every /api/me endpoint derives the customer FROM the token, so no one can request anyone else's data; bumping customers.portal_token_version revokes a member's links). Shows season snapshot (rounds, best gross/net 9 & 18), points-race ranks with projected reset, handicap-differential trend sparkline, par-3/4/5 and hole-difficulty scoring splits, and every imported scorecard expandable to the full hole-by-hole card (shared renderer static/js/scorecard-render.js). Admins fetch a member's link via GET /api/customers/<id>/portal-link. End-to-end tested incl. bad-token 401s, cross-customer 404s, and link revocation.",
      "Multi-round import support: Hill Country Matches is its own GG league with six rounds all dated the same Saturday — the importer now accepts a round_key (GG league round id, stored as scoring_rounds.gg_league_round_id) so same-day rounds don't collapse into one while ALL Net/ALL Gross of the same round still dedupe.",
      "s9.12 Canyon Springs imported after the admin released results: 39 players, 39/39 verified, 2 no-show tee-sheet cards auto-skipped. Every published 2026 round in both chapter portals is now in the tracker.",
    ],
  },
  {
    version: "2.27.0",
    date: "2026-07-03",
    changes: [
      "Phase 2 step 1 — differential parity engine: get_differential_parity recomputes every bridged handicap round's adjusted gross (WHS net double bogey through the admin formula layer) and differential (113/slope × (adjusted − rating)) from tracker-owned scorecard facts and compares them to the values imported from Golf Genius's handicap export. Exposed as MCP tool get_differential_parity_tool (56 tools) and the scoring-parity bridge command. 9-hole rounds first; 18-hole front/back splitting is the next pass. When parity holds at 100%, the handicap layer derives from scoring_rounds directly and the manual export/import ritual dies.",
      "Member portal + email summaries design doc added (docs/claude/member-portal.md): magic-link tokens per customer (reusing the roster opt-in signing pattern), a mobile-first My TGF page (season snapshot, handicap trend, expandable scorecards, par-3/4/5 and stroke-index stats), post-event recap emails triggered by scorecard imports, and a phased rollout that reuses the existing scorecard renderer and read paths.",
    ],
  },
  {
    version: "2.26.1",
    date: "2026-07-03",
    changes: [
      "Full 2026 season sweep: 31 more rounds imported across both chapters (SA s9.1–s9.13 + five 18-hole Saturdays + La Cantera + Cedar Creek pre-season; Austin a9.1–a9.13 + Crystal Falls + Kickoff + Morris Williams) — 728 player-rounds, zero unresolved names, one verification flag. s9.12 Canyon Springs (6/2) is the only round not yet imported: GG still shows 'results are being reviewed' — one command re-imports it once released.",
      "Zero-hole scorecards are tee-sheet artifacts, not scoring records: the sweep's single flag was Brian Parch's s9.8 card — on the tee sheet with a 10 handicap but never played, so GG published a blank card with sums of 0 and the net math check fired. The importer now skips cards with no strokes on any hole (skipped_empty_cards in the result), and a boot cleanup removes any stored earlier, resets their handicap bridges, and closes their discrepancy alarms.",
    ],
  },
  {
    version: "2.26.0",
    date: "2026-07-03",
    changes: [
      "Scorecard grid restructured per admin: SCORE row renamed GROSS SCORE (bold, most prominent) and a NET SCORE row added beneath it (gross minus strokes received per hole), with thick sectional borders above GROSS and below NET separating course facts on top from the points rows below. Stroke-index row header stays 'HCP'.",
      "PLUS HANDICAPS: the 3-week backfill's parallel-run verification flagged 6 cards, all the same root cause — GG renders plus playing handicaps as '(+1)' which the parser didn't match (Texas Terry: gross 36, NET 37). The parser now reads '+N' (stored negative so net = gross − ph stays uniform, displayed as '+N'), and the importer allocates the give-back stroke on the |ph| easiest holes played (highest stroke index, WHS allocation) since GG renders no dot for them. Give-backs render as hollow ○ marks on the card. Re-importing the affected tournaments cleared all 6 discrepancies.",
      "Scorecard discrepancy action items now close themselves: when a re-import verifies a previously-flagged round clean, its open COO action item is marked completed automatically.",
      "3-week scorecard backfill imported and verified: s9.14 Hill Country (34), s9.15 The Quarry (35), s18.7 Kissing Tree (29, 18 holes — two 9-hole handicap differentials bridged per player), a9.14 Avery Ranch (18), a9.15 Teravista (20), joining s9.16 TPC Oaks (32) — 168 rounds total, zero unresolved names. a9.16 ShadowGlen is pending: its results haven't been released to the Austin portal in GG yet.",
    ],
  },
  {
    version: "2.25.0",
    date: "2026-07-03",
    changes: [
      "Scorecards now expand from the points lines themselves: in the Contests player drill-down, any round line with an imported scorecard gets a chevron and expands the hole-by-hole card right under it (matched by event name, with event-code fallback). The separate list below only remains — retitled OTHER SCORECARDS — for rounds with no points line above (e.g. guests without points detail).",
      "The hole-by-hole grid gains NET PTS and GROSS PTS rows — per-hole stableford points computed through the admin formula settings, with block totals that correctly show 0 and negative sums. The stroke-index row is relabeled 'HCP' per admin (it's the hole handicap ranking, 1 = hardest — it decides where a player's handicap dots land; hover the label for the explanation).",
    ],
  },
  {
    version: "2.24.4",
    date: "2026-07-03",
    changes: [
      "Import recipe corrected per admin: ALL Net and ALL Gross are the gold standard — both carry the FULL field. ALL Net has everyone's playing handicaps + stroke dots (Individual Net is a purchased game and only covers buyers); ALL Gross is the raw-score baseline our own calculations build on to reverse-engineer GG's derivations. New upgrade rule: a net-game card (has playing handicap) now REPLACES a stored raw-gross card for the same physical round (upgraded_with_handicap in the result), never the reverse — so importing ALL Net retrofits handicaps/dots/net onto rounds that arrived via ALL Gross.",
      "Documented the mid-season membership rule: points earned as a non-member WITHIN the season-contest window (Spring/Summer Gross & Net races: Kickoff events through City Championships; Fall has its own window) activate in full on becoming a member. The live pipeline already honors it — snapshots keep every ranked row, and the member filter + eligibility recompute at read time, so a status flip instantly surfaces the player with their full total.",
    ],
  },
  {
    version: "2.24.3",
    date: "2026-07-03",
    changes: [
      "Identity repair, pass 3 (the one that actually fixes Kailey Lopez): her link wasn't nameless — the email auto-matcher had filled BOTH customer_name and customer_id with the BUYER ('Steve Kulawik', whose email her guest spots were bought on), so pass 1 saw a self-consistent link and pass 2 didn't apply. New pass re-points links whose GG player_name is EXACTLY one other customer's canonical name while the linked customer separately holds a link under their own name — proof the row can't be a display-name variant. The wrong customer_name is corrected along with the id; nickname links (GG 'Mike Murphy' → Michael Murphy) are untouched.",
    ],
  },
  {
    version: "2.24.2",
    date: "2026-07-03",
    changes: [
      "Identity repair, pass 2: handicap links created WITHOUT a customer_name (nothing recorded about who the link is for) are now checked against the GG player name itself — when that name is a customer's exact canonical name and the link points at a different profile, the link and its handicap rounds are re-pointed (alias-mediated or ambiguous matches are left alone). Found via the first full-field scorecard import: Kailey Lopez's nameless link pointed at Steve Kulawik, silently feeding her rounds into his handicap record and blocking her scorecard import as his 'duplicate'. Moved rounds get their scorecard bridge reset so the next import re-links them to the right card.",
    ],
  },
  {
    version: "2.24.1",
    date: "2026-07-03",
    changes: [
      "Added scoring-resolve:<gg_name> to the probe bridge — identity debugging that shows a GG name's parse candidates, any handicap_player_links rows they hit, and the final customer resolution. Built to chase why Kailey Lopez's ALL Gross card was skipped as a duplicate when she had no round on file.",
    ],
  },
  {
    version: "2.24.0",
    date: "2026-07-03",
    changes: [
      "Scorecards are now VISIBLE: expanding a player on Contests → Points Races shows a SCORECARDS section under their points breakdown — every imported round (date, event, course/tee with slope/rating, holes, HCP, gross, net), and clicking a round renders the classic hole-by-hole card: black HOLE header, PAR/YARDS/S.I. rows from the course DB, scores with handicap-stroke dots and GG's net-relative circle/square markings, OUT/IN totals, plus a summary line with stableford points and adjusted gross.",
      "Scorecard importer now recognizes that one physical round appears under EVERY Golf Genius game that day (Individual Net, ALL Gross, Skins…) with different aggregate ids: the first tournament to bring a player's card owns the row, later tournaments only FILL players still missing (result field skipped_other_tournament). This is what lets a full-field game like ALL Gross top up the 11 s9.16 players who weren't in the Individual Net game without duplicating the 21 who were.",
    ],
  },
  {
    version: "2.23.4",
    date: "2026-07-03",
    changes: [
      "Scorecard parser now HTML-unescapes text pulled from GG partials (flight labels, player names, tee headers) — the first real import stored 'Flight 1 (HCP &lt;12.0)' with the raw entity. Facts land clean; re-import (idempotent) rewrites existing rows.",
    ],
  },
  {
    version: "2.23.3",
    date: "2026-07-03",
    changes: [
      "Temporary MCP bridge: probe_golf_genius accepts scoring-* extract values (scoring-import:<code>, scoring-rounds:<event>, scoring-verify:<id>, scoring-card:<id>, scoring-courses) that dispatch to the v2.23 scoring layer. Client sessions freeze their tool inventory at session start, so sessions opened before v2.23.0 can't see the five new scoring tools — this reaches them through a tool every session already has. Remove once stale sessions age out.",
    ],
  },
  {
    version: "2.23.2",
    date: "2026-07-03",
    changes: [
      "Retired the Jeff Goretzke profile-details pin: the admin renamed cid 126 to 'Jeff Goretzke', so GG's name resolves directly and the pin's cid+name guard was (correctly) skipping with a boot warning every deploy.",
    ],
  },
  {
    version: "2.23.1",
    date: "2026-07-04",
    changes: [
      "Scorecard imports now auto-verify every card against Golf Genius's own numbers immediately; any discrepancy files a COO action item (category 'scoring', deduped while open) naming the failing checks and the usual fix path — so parallel-run mismatches surface in the existing review queue instead of hiding in logs. Import results report verified_ok and discrepancies counts.",
    ],
  },
  {
    version: "2.23.0",
    date: "2026-07-04",
    changes: [
      "Scoring records Phase 1: tracker-owned hole-by-hole scorecards extracted from Golf Genius. New scoring_rounds/scoring_holes tables store FACTS only (strokes, strokes received per hole via GG's handicap dots, tee, GG's gross/net) with customer_id resolved at import through handicap_player_links then the alias machinery; derived values — WHS net-double-bogey adjusted gross (per-player: par+2+strokes received), net/gross stableford, vs-par — compute at read time through admin-controllable formula settings so TGF can retune or toggle to USGA standards later. Verified against Adam Baker's live TPC card end-to-end, including the discovery that GG's circle/square markings are NET-relative.",
      "Course database enriched, not duplicated: scorecard imports resolve GG course names through the existing courses/course_aliases registry (the same one the Events tab course selector already reads) and accrete course_tees (slope/rating/yardage) + course_tee_holes (par/yardage/stroke index) passively from every import.",
      "Own-the-data insurance: every parsed GG response is archived gzipped in gg_raw_archive so anything can be re-parsed even if GG severs access. handicap_rounds gains a scoring_round_id bridge (a differential is DERIVED from a scoring round) — Phase 2 proves differential parity and retires the handicap export/import ritual.",
      "5 new MCP tools (55 total): import_gg_scorecards, get_scoring_rounds, get_scorecard_detail, verify_scoring_round_tool, get_courses — plus POST /api/scoring/import, GET /api/scoring/rounds, /api/scoring/scorecard/<id>, /api/courses/tees.",
    ],
  },
  {
    version: "2.22.4",
    date: "2026-07-03",
    changes: [
      "THE PLAYERS CUP gains a Chapter column (tracker profile's chapter first, GG affiliation as fallback for unmatched names), and both it and THE FELLOWSHIP CUP's Chapter columns get the same vertical border treatment as POINTS. NET tabs stay single-chapter with no extra column.",
    ],
  },
  {
    version: "2.22.3",
    date: "2026-07-03",
    changes: [
      "POINTS RESET column headers now carry an amber '(Projected)' label above the title on all four sub-tabs — making clear the values are live projections until the actual reset after the City Championships.",
    ],
  },
  {
    version: "2.22.2",
    date: "2026-07-03",
    changes: [
      "Hidden non-members no longer affect rankings (admin rule): standings re-rank over the visible list, so a player whose only tie partner was hidden shows a plain rank (Michelle DelCarmen's phantom T59 becomes 59), positions close up, and real ties among visible players keep their T-marks. GG's original rank is preserved internally as gg_rank. The reset ladder likewise counts ELIGIBLE players only — a visible-but-ineligible row (expired member kept visible by their buy-in, or a member with zero rounds) consumes no ladder position.",
    ],
  },
  {
    version: "2.22.1",
    date: "2026-07-03",
    changes: [
      "Expanded player view: Tournament column renamed EVENT; the counted scores (best 10, above GG's 'not counted' divider) show bold EVENT names and point totals while thrown-out rows are muted; new CITY CHAMPIONSHIP Total line sits at the end of the counted block (blank until played) — each race's final total = best 10 point totals + City Championship total (bonus-points Stableford; net values +1).",
      "Standings tables: light-red highlight removed from not-bought-in rows — green alone carries the contrast; the ✗ Not in badge stays. Amber stays for unmatched names (identity to-do, not a buy-in state).",
    ],
  },
  {
    version: "2.22.0",
    date: "2026-07-03",
    changes: [
      "POINTS RESET projections are live (methodology admin-established from the 2025 workbook): one master ladder (position p = 100 − 0.5×(p−1)); each race rank maps to master position ROUND(1 + coef×(rank−1)). NET races share the ladder with coef = anchor ÷ own eligible count (anchor = largest chapter; e.g. 88/56 → 1.571, verified against the 2025 sheet's own values); THE PLAYERS CUP restacks its combined cross-chapter list straight down the ladder at coef 1, flights dismissed. Eligible = active members who have played ≥1 event this season, any point total; tied ranks share a value and the ladder skips accordingly. Values are PROJECTIONS — the actual reset happens after the City Championships. Summary line shows each race's coefficient and eligible counts.",
      "New THE FELLOWSHIP CUP sub-tab: both City NET competitions merged into one projected reset standings list (the race that plays out at the TGF Championship) — TFC rank, player, chapter, NET rank, and POINTS RESET, with the same buy-in color coding. Mirrors the 2025 workbook's 'TFC Projected' tab. Refresh here re-pulls both NET races from Golf Genius.",
    ],
  },
  {
    version: "2.21.7",
    date: "2026-07-03",
    changes: [
      "Points race table: vertical column borders extended to POINTS RESET and Rounds (right-edge rules, so adjacent columns share a single 2px line with POINTS's existing borders).",
    ],
  },
  {
    version: "2.21.6",
    date: "2026-07-03",
    changes: [
      "Hill Country Matches rounds drop the code prefix in the expanded detail (admin preference): 'Hill Country Matches - Valley / Hills / Creeks' instead of 'hcmR1 …'. Regular events keep their codes ('a9.13 Star Ranch').",
    ],
  },
  {
    version: "2.21.5",
    date: "2026-07-03",
    changes: [
      "Hill Country Matches rounds labeled in the expanded detail (admin-provided): hcmR1 = Valley, hcmR2 = Hills, hcmR3 = Creeks — via a static override registry that only fills codes the events table doesn't cover (a future tracker event with the same code would win).",
    ],
  },
  {
    version: "2.21.4",
    date: "2026-07-03",
    changes: [
      "Expanded player detail shows real event names (admin request): GG tournament labels like 'a9.13 POINTS Gross - THE PLAYERS CUP' are swapped for the tracker's event name ('a9.13 Star Ranch') by matching the shared event-code prefix against events.item_name. 18-hole Front/Back splits keep their qualifier ('s18.7 KISSING TREE — Front'); labels with no matching tracker event (e.g. Hill Country Matches rounds) pass through unchanged.",
    ],
  },
  {
    version: "2.21.3",
    date: "2026-07-03",
    changes: [
      "Expanded player detail reshaped (admin request): Points is now the first column and the redundant Event column ('TGF San Antonio 2026' on nearly every row) is dropped — leaving Points | Tournament | Awarded Date | Position. GG's 'points not counted in standings' divider now spans the full table width instead of rendering as a stray single cell.",
    ],
  },
  {
    version: "2.21.2",
    date: "2026-07-03",
    changes: [
      "Points race table: POINTS and Rounds data now centered (was right-justified); new empty POINTS RESET column between them (placeholder — no data yet, reserved for the upcoming points-reset feature).",
    ],
  },
  {
    version: "2.21.1",
    date: "2026-07-03",
    changes: [
      "Points race table polish: fixed pixel widths on the Rank / POINTS / Rounds / Buy-in columns so all three race tabs lay out identically (columns were auto-sizing to each tab's content, making SA Net's POINTS/Rounds spacing drift from the others). Flight heading rows are now black with white text, with the flight name in ALL CAPS ('1ST FLIGHT') and the range/count in regular weight; the no-handicap bucket matches as 'FLIGHT UNASSIGNED'.",
    ],
  },
  {
    version: "2.21.0",
    date: "2026-07-03",
    changes: [
      "Points races show members only (admin rule): rows hide when the resolved profile isn't an active member (guests, first-timers, expired, inactive), or — for names with no tracker profile — when Golf Genius's own affiliation column doesn't show a current TGF chapter. Anyone with a buy-in is NEVER hidden regardless of status. The summary line notes how many were hidden; hover it to see who.",
      "POINTS column emphasized: bold with vertical rules on both sides. Current handicap moved from its own column into muted parentheses after each player's name.",
      "Jeff Goretzke resolves now: the tracker knows him as Jeffrey (active Austin member through 5/10/2027) while GG's portal names him 'GORETZKE, Jeff' — he was the Austin race's unmatched amber row. A pinned 'Jeff Goretzke' name alias (profile-details registry) links them. Note: he has no Austin NET buy-in on record, so he shows red 'Not in' — flag if that's wrong.",
    ],
  },
  {
    version: "2.20.5",
    date: "2026-07-03",
    changes: [
      "Comp'd season-contest enrollments (owner privilege, admin request): Kerry Niester is enrolled in both San Antonio races — NET Points Race and GROSS Points Race (THE PLAYERS CUP) — via a new boot-seed registry (_COMPED_CONTEST_ENROLLMENTS). These rows carry manually_enrolled=1, the same protection as cash enrollments, so the purchase-reconcile sync will never remove them; cid+name are pinned and the seed is idempotent. His existing City Match Play manual enrollment already followed this pattern.",
    ],
  },
  {
    version: "2.20.4",
    date: "2026-07-03",
    changes: [
      "Points race sub-tab labels per admin: 'San Antonio NET' and 'Austin NET' (were 'SA NET Points Race' / 'AUSTIN NET Points Race').",
    ],
  },
  {
    version: "2.20.3",
    date: "2026-07-03",
    changes: [
      "Points race polish (admin requests): enrolled rows are a brighter green so buy-ins pop; every race now shows a current-handicap (HCP) column, not just the flighted Players Cup — computed live, so it always reflects today's index; BEHIND and WINS columns removed; the GROSS sub-tab is renamed THE PLAYERS CUP (the underlying contest data name is unchanged).",
    ],
  },
  {
    version: "2.20.2",
    date: "2026-07-03",
    changes: [
      "Fix: 'REED, Paul1' on the Austin Net race now resolves to Paul Reed and shows his buy-in — Golf Genius appends a digit to the given name when a duplicate name registers in a league, and the name matcher took it literally. Candidate generation now also tries the digit-stripped form (exact form first), fixing this whole artifact class. Works immediately on the existing snapshot via the read-time enrollment-name fallback — no GG refresh required.",
    ],
  },
  {
    version: "2.20.1",
    date: "2026-07-03",
    changes: [
      "AUSTIN Net 2026 points race added (admin request): third sub-tab on the Points Race tab, pulling standings from the Austin league portal (tgf-austin.golfgenius.com, league 514705, page 6077320) with the same persisted snapshot, buy-in color coding, and expandable round detail. Buy-in check is scoped to Austin NET Points Race enrollments; the SA NET tab is now labeled 'SA NET Points Race' and its enrolled-players roster is scoped to San Antonio (previously the roster mixed both chapters). The GROSS/Players Cup roster stays all-chapters.",
    ],
  },
  {
    version: "2.20.0",
    date: "2026-07-03",
    changes: [
      "Fix: round-by-round detail now loads — GG's expansion partial injects via jQuery .append(), not .html(); the unwrapper only matched .html() so every expansion showed 'no detail available'. Verified against the live individual_info response (Event | Tournament | Awarded Date | Position | Points, including GG's 'not counted in standings' section).",
      "Fix: THE PLAYERS CUP buy-in check is now cross-chapter (admin-confirmed 'The players cup is all chapters') — Robert Straiton and the other Austin GROSS Points Race enrollees showed wrongly red because the enrollment join was scoped to San Antonio. Each race now declares its own enroll_chapter scope; NET races stay chapter-scoped.",
      "Flights for THE PLAYERS CUP (admin request): standings group into 1st Flight (HCP <6.0), 2nd (6-11.9), 3rd (12-17.9), 4th (18+), assigned from each player's CURRENT 18-hole handicap index (TGF 9-hole index x2 - the same value the GG export syncs) computed at render time, so a handicap change moves a player to their new flight automatically. Players with no linked handicap rounds appear under 'No current handicap - flight unassigned'. An HCP column shows the index used. Flight boundaries live in the _GG_POINTS_RACES registry.",
    ],
  },
  {
    version: "2.19.2",
    date: "2026-07-03",
    changes: [
      "Points Race rows are now expandable (admin request): click a player to unfold their round-by-round points detail, fetched live from Golf Genius the same way GG's own row expansion works (season_points_v2/individual_info XHR, discovered by reverse-engineering GG's widget bundle). Each snapshot row now stores the GG member_card_id (column added in place for existing tables); detail responses are cached 10 minutes per player. If GG answers with something other than a player breakdown the row shows a clear error instead of wrong data. Profile links in the name cell still navigate normally — clicking anywhere else on the row toggles the detail.",
    ],
  },
  {
    version: "2.19.1",
    date: "2026-07-02",
    changes: [
      "Points Race standings moved from the Enrollment tab to the Points Race tab itself (admin request): the NET and GROSS sub-tabs now show their GG standings automatically — no Load button — above the enrolled-players roster. Standings persist in a new gg_points_standings table (customer_id FK, registered in the merge re-point registry), so the tab renders instantly from the last snapshot and survives restarts; a refresh from Golf Genius happens only when the snapshot is empty or older than 12 hours, or via the ↻ Refresh button. Buy-in status is never stored — it joins live against season_contests at render time, so recording a buy-in shows green immediately without refetching GG. If GG is unreachable the last snapshot is served with a warning.",
    ],
  },
  {
    version: "2.19.0",
    date: "2026-07-02",
    changes: [
      "Points Race — Buy-in Status panel on the Contests page Enrollment tab (the first live Golf Genius data integration): loads the public season_points_v2 standings widget from the GG portal server-side (SAN ANTONIO Net 2026 and THE PLAYERS CUP 2026, registry: _GG_POINTS_RACES) and color-codes every ranked player by season-contest buy-in — green = bought in, red = has a tracker profile but no buy-in, amber = GG name didn't match any profile. GG's 'LAST, First' names (including suffixes like 'ARIAS, Victor Jr') resolve to customer_id via _lookup_customer_id with aliases, per the identity-key principle. Also lists players who bought in but aren't in the GG standings yet. Endpoint /api/season-contests/points-race, cached 10 minutes.",
    ],
  },
  {
    version: "2.18.1",
    date: "2026-07-02",
    changes: [
      "New MCP tool probe_golf_genius (50 tools): fetches a PUBLIC Golf Genius portal page server-side (Railway has open egress to golfgenius.com; Claude's sandbox does not) and returns parsed structure — title, headings, links, tables, text, or raw HTML. Read-only, no login, hard-restricted to *.golfgenius.com URLs including redirect targets (anything else would make the tool an open proxy into the Railway network). This is the exploration path for importing GG results/standings into the tracker, starting from the admin's public SA portal page.",
    ],
  },
  {
    version: "2.18.0",
    date: "2026-07-02",
    changes: [
      "Vendor auto-suggest in expense review (admin-requested): opening a pending expense with no linked vendor/customer now checks the merchant name against every profile. If an existing vendor (or customer — e.g. a Venmo payout recipient) matches, a one-click 'Link' suggestion appears; if nothing matches, a '＋ Create vendor & link' button offers to create the vendor from a cleaned-up merchant name (processor prefixes like 'SQ *' and trailing store numbers stripped, bank ALL-CAPS title-cased). Creation reuses the existing dedup-safe /api/accounting/vendors endpoint, so a repeat suggestion can never make a duplicate profile.",
      "The nightly 02:00 Golf Genius sync job is no longer scheduled (admin decision): the screen-scraping upload never established a reliable connection, and handicaps flow to GG via the manual CSV export the admin uploads by hand. The on-demand sync endpoint and the CSV export are unchanged.",
    ],
  },
  {
    version: "2.17.15",
    date: "2026-07-02",
    changes: [
      "Golf Genius boot-log diff now respects the admin exclusion registry: the 'Matt LAWYER NEWLY included' line kept printing after v2.17.14 because the log-only email-diff pass queries handicap_player_links directly and never consulted _GG_SYNC_EXCLUDES — only the actual export data (get_handicap_export_data) did. Excluded players are now skipped in the diff too, so the deploy log matches what the export would really contain.",
      "Clarified in docs: the nightly 02:00 'GG sync' job has never uploaded anything — it needs GOLF_GENIUS_EMAIL/PASSWORD env vars (screen-scraping roster upload, no official API) and skips every night without them, which matches the admin's report that a reliable GG connection was never established. The export path still matters for the manual CSV download (/api/handicaps/export-csv) and any future on-demand sync, so the exclusion registry stays.",
    ],
  },
  {
    version: "2.17.14",
    date: "2026-07-02",
    changes: [
      "Golf Genius sync: players the admin intentionally removed from GG are now excluded from the nightly handicap export (registry: Matt Lawyer). Without this, tonight's 02:00 sync would have silently re-added him — the boot log had him queued as 'NEWLY included'. He remains a fully active tracker member; this only stops the re-upload to Golf Genius. Reggie Johnson stays IN the export and joins GG on tonight's sync as intended.",
      "Data (from the GG roster cross-check, admin-approved): Casey Purvis gets purvis.casey@yahoo.com and Matthew Starnes gets matthewrstarnes@yahoo.com — Golf Genius had emails the tracker lacked for both.",
    ],
  },
  {
    version: "2.17.13",
    date: "2026-07-02",
    changes: [
      "Data (admin-provided): Victor Arias Jr. gets the VicYClau-Arias Venmo handle — the roster backfill's ambiguity guard had correctly refused to choose between father and son; admin confirmed it's Dad's. Torey Tonche (phone, tjtonche@gmail.com, membership term 1/31/25–1/31/26) and Nic Skinner (phone, nic.skinner2@gmail.com, Venmo Nicolas-Skinner-1, membership term 4/27/25–4/27/26) get their pre-tracker details.",
      "MCP: new list_customer_contacts tool (37 tools) — one compact row per non-vendor customer with name, chapter, status, primary email, Venmo, and phone, filterable by chapter/status. Built for cross-referencing external rosters (Golf Genius exports, spreadsheets) against tracker data in a single call.",
    ],
  },
  {
    version: "2.17.12",
    date: "2026-07-02",
    changes: [
      "Merge (admin-confirmed): 'Kailey L' into Kailey Lopez — Ashley Padilla's guest twice (TPC Canyons 5/8, TPC Oaks 6/29), surname abbreviated on the second order. One guest profile now, with 'Kailey L' kept as an alias.",
      "Merge (admin-confirmed): the empty 'Lee Vazques' shell (created 5/18, zero data) into the real Lee Vasquez — Austin member, 11 rounds since March, membership through 5/4/2027. The misspelling stays as an alias so anything arriving under it resolves to him. His 'Leonel Vasquez' Venmo payer alias also landed today, so his Venmo payments link to his profile.",
      "The roster contact backfill is now one-shot: the extracted data file is removed from the repo after its single production run (234 profiles matched, 164 Venmo handles + 9 emails filled). The admin maintains the source spreadsheet externally and it isn't a master record, so a stale snapshot must not keep writing old handles onto future profiles. The mechanism remains — drop a fresh extract at data/member_roster_backfill.json and it applies once, blank-only.",
    ],
  },
  {
    version: "2.17.11",
    date: "2026-07-02",
    changes: [
      "MCP connection: access tokens now last 24 hours (was 1 hour — the cause of the constant re-authorization), and the OAuth server issues 30-day refresh tokens with a refresh_token grant so claude.ai can renew the connection silently. One more manual reconnect picks this up; after that it should stay connected for weeks at a time.",
      "Data: contact backfill from the 25TGF_Members Player Database sheet (471 usable rows from 20 years of records). For every roster person who already has a tracker profile, missing Venmo handles and missing emails are filled in — resolved email-first then by exact name including alternate first-name spellings, with the ambiguity guard. Existing values are never overwritten, an email already on another profile is never cross-attached, and no new profiles are created (roster people who never appear in the tracker stay out). Runs at every boot, so future profiles get enriched from the roster automatically the moment they're created.",
    ],
  },
  {
    version: "2.17.10",
    date: "2026-07-02",
    changes: [
      "Fix: the lead-email separation was fighting a resurrection loop visible in the last deploy log — it removed Joe Orel's email from Garza's profile, then the historical-alias capture re-created it from the old order row's email snapshot, and the RSVP backfill re-linked the decline, every boot. The separation is now a full quarantine: a lead's email is removed from every profile, every alias, every RSVP link, AND the items.customer_email snapshots that fed the capture step. One pass, permanent.",
      "Data (admin-provided): Chris Best — Doug Hamilton's guest, played s18.7 KISSING TREE — gets chris.best@ferguson.com and (864) 601-0467 on his profile.",
      "Repair: the 'Casey Best' profile is queued for deletion — not a person, but a name-mash of Doug Hamilton's two guests, Casey Purvis and Chris Best, who each have their own profiles. Same pinned-and-guarded fragment delete as the Brandons: if anything still references it, the deploy log lists exactly what, instead of deleting.",
    ],
  },
  {
    version: "2.17.9",
    date: "2026-07-02",
    changes: [
      "Fix: Venmo handles are stored bare (no leading @) — the Customer Info save path already stripped it and the payout/matching code handles both forms, but a direct write had stored '@Matt-Rose-58' which rendered as '@@Matt-Rose-58'. A boot normalization strips leading @ from any stored handle, so the field stays clean for wiring direct Venmo payout/refund links later.",
      "Correction (HubSpot-verified, admin-confirmed): joe@jjoconstruction.com belongs to Joe OREL — a Facebook ad lead who never played — not Joe Garza (no email was ever received from Garza). The email and its alias are detached from Garza's profile, his Canyon Springs decline RSVP is unlinked, and Joe Orel joins the known-lead registry. Same shape as the Steve Barr correction; both now run through one registry-driven separation repair.",
    ],
  },
  {
    version: "2.17.8",
    date: "2026-07-02",
    changes: [
      "Correction (HubSpot-verified): the 'Steve' who declines Golf Genius invites from planelite1959@gmail.com is Steve BARR — a separate Facebook ad lead with his own HubSpot contact and phone — NOT Steve Novosad. v2.17.7 had attached that address to Novosad's profile and linked 7 decline RSVPs to him; a boot repair detaches the email/alias and unlinks the RSVPs, and Steve Barr joins the known-lead registry so his declines stay unlinked by design. Novosad's real details (snovosad78@gmail.com, phone, Stephen alias, 2025–26 term) are untouched.",
      "HubSpot cross-check confirmed the other lead identities: Linda Sackett (SA), Martin Parker, Christopher Graham, and 'Gbob Runner' (placeholder name) — all PAID_SOCIAL leads who never played. Matt Rose's phone matches his HubSpot record exactly.",
    ],
  },
  {
    version: "2.17.7",
    date: "2026-07-02",
    changes: [
      "Data (admin-provided): Steve Novosad's profile is filled in — phone (210) 557-2621, primary email snovosad78@gmail.com, his Golf Genius sending address planelite1959@gmail.com as a secondary email so his RSVPs link, a 'Stephen Novosad' name alias, and his initial membership term 5/2/2025–5/2/2026. His 7 unlinked decline RSVPs now attach to his profile.",
      "Data (admin-provided): Matt Rose's profile is filled in — phone (210) 287-2502, email matt.rose3@yahoo.com, Venmo @Matt-Rose-58, and his 2025 membership term (Venmo $75 on 3/18/2025). His decline RSVP links. Joe Garza gets joe@jjoconstruction.com and his Canyon Springs RSVP.",
      "Repair: the 'Joe Brandon' profile is deleted — placeholder notes for a guest Brandon who never played, not a person (same pinned-and-guarded fragment delete as Victor Brandon).",
      "Audit: the five confirmed Facebook-ad-lead RSVP senders (Robin Hulsey, Linda, Martin Parker, Christopher Graham, 'Gbob') are registered as known non-customers — their Golf Genius decline RSVPs stay unlinked by design and the identity audit now segregates them into their own count instead of flagging them as problems.",
    ],
  },
  {
    version: "2.17.6",
    date: "2026-07-02",
    changes: [
      "Vendors: vendor-role profiles (Costco, Arcis Golf, HubSpot, etc.) no longer appear on the Customers page or anywhere else people-facing — they're expense payees, not golfers. Their home is now a Vendors panel on the Accounting page (next to Review Queue): the list with ledger-entry counts plus an Add Vendor button. They stay in the customer table under the hood so expense ledger links keep working.",
      "Repair: the Victor Brandon fragment delete was correctly blocked last deploy because 3 order-split rows still pointed at it — those splits are now re-pointed to their own item's owner first, unblocking the delete. The guard that refused to delete while data was attached is exactly the behavior we want and it worked.",
    ],
  },
  {
    version: "2.17.5",
    date: "2026-07-02",
    changes: [
      "Repair (identity audit findings, all admin-confirmed): the 'Will Massey' name alias is removed from Colby Johnson's profile — the last shard of their old bad merge (which began with Colby paying for Will's first event); any name-resolution path reaching that alias could have attributed Massey's activity to Colby.",
      "Repair: 'Reggie Johnson' and 'Reginald Johnson' are one person — the empty Reggie shell (no purchases, no email) is merged into the real Reginald profile, with 'Reggie Johnson' kept as an alias so either spelling resolves correctly.",
      "Repair: the 'Victor Brandon' profile is deleted — not a real person, but a name-mash fragment from a Victor Arias Jr. order where he paid for his son and a guest named Brandon. The repair is pinned to that exact profile id and refuses to run if the profile ever holds real data.",
      "MCP: get_customer_data_audit now returns the actual unlinked RSVP rows (player name, email, event, date) instead of just a count, and the no-email customer list is uncapped and annotated with any email still recoverable from each customer's old order rows plus their assigned roles — groundwork for filling in the pre-tracker member emails.",
    ],
  },
  {
    version: "2.17.4",
    date: "2026-07-02",
    changes: [
      "Data: the two retroactive City Match Play refund records now carry their full Venmo details (admin-provided). Neil Cheshire: $51.75 on 2026-06-23, transaction fees included because Match Play had closed but was accidentally left open for purchase. Joseph Lourigan: $50.00 on 2026-05-26, withdrew due to limited availability, transaction fees not refunded. The Removed date on each record is the actual refund date. Applied idempotently at boot; records already carrying an amount are never touched.",
      "MCP: new get_customer_data_audit tool — the identity checks get_customer_profile runs for one person, swept across ALL customers in a single call: nameless shell profiles, same-name profile groups (potential unmerged splits, with confirmed-distinct pairs annotated), customers missing emails or a primary email, emails shared across profiles, rows pointing at deleted customer ids, unlinked rows per identity table, and name aliases that shadow another customer's canonical name (flagged for review — intentional for spouse payment accounts). Empty sections mean clean.",
    ],
  },
  {
    version: "2.17.3",
    date: "2026-07-02",
    changes: [
      "Cleanup: duplicate alias rows are collapsed at boot — repeated captures had piled up identical entries (Stu Kirksey carried SEVEN copies of the 'Stuart Kirksey' name alias). The earliest row per customer + alias type + value (case-insensitive) is kept; unlinked shadow copies of already-linked aliases are removed too. The deploy log reports how many rows were removed.",
      "Guard: unique indexes on customer_aliases now make every future duplicate capture a silent no-op — all alias write paths (captures, merges, backfills, repairs, renames) were converted to duplicate-tolerant statements so nothing breaks when they hit the guard. Merging two customers who both carry the same alias now correctly keeps the target's single copy instead of stranding the source's.",
      "Intentional aliases are untouched: typo email variants (this is what routes Stu's frequently mistyped order emails to the right profile) and spouse-payment aliases like Kay Kirksey → Stu stay exactly as they are.",
    ],
  },
  {
    version: "2.17.2",
    date: "2026-07-02",
    changes: [
      "MCP: four new tools for Claude's direct database access (31 → 35). get_season_contest_enrollments and get_season_contest_removals expose the Enrollment tab's data (enrollments + the removals/refunds recordation) with contest/chapter/season filters — until now enrollment state couldn't be verified over MCP at all. sync_season_contests triggers the same sync as the Enrollment tab's button and returns the {enrolled, linked} counts.",
      "MCP: get_customer_profile returns a full identity snapshot for one customer — canonical profile row, emails, aliases, status history, membership terms, handicap links, contest enrollments/removals, and a transaction summary — looked up by customer_id or name (ambiguous names return the candidate list instead of guessing). It explicitly flags NAMELESS SHELL profiles (blank first/last names), the exact condition that silently broke Stu Kirksey's enrollment; get_customer_details only returns purchase rows, which is why that shell was invisible over MCP.",
    ],
  },
  {
    version: "2.17.1",
    date: "2026-07-02",
    changes: [
      "Fix: the deploy log showed the sync still reporting '10 new enrollments' every run after v2.16.32 — a second churn loop. When a purchase's customer name is a variant of the profile's canonical name (e.g. 'Stu' vs 'Stuart', or an alias), the sync inserted a variant-named enrollment (counted as 'new'), then its own name-normalization step collided with the already-existing canonical row and deleted it — every single run. Enrollments are now created under the canonical profile name and chapter from the start (resolving the profile alias-aware at insert when the purchase doesn't carry one), so they land on the existing row as a link, not a phantom 'new enrollment'. A warning now fires if the cleanup ever removes duplicates again, so this class of churn can't hide in the counts.",
      "Fix: Stu Kirksey STILL wasn't enrolled — his purchase pointed at a customer profile with BLANK first/last names (a nameless shell), so the sync's canonical-name step blanked his enrollment and the blank-row purge deleted it every boot (the deploy log's 'deleted nameless City Match Play/2026 enrollment' line). The name-normalization now never renames an enrollment to a blank name, and the boot repair names the shell profile (or re-points the purchase at his real profile), then merges any remaining Stu/Stuart split. His City Match Play enrollment (5/25) now sticks.",
    ],
  },
  {
    version: "2.17.0",
    date: "2026-07-02",
    changes: [
      "Feature: clicking ✗ on an enrollment (Enrollment tab, or the City Match Play 'Not Yet in a Pool' list) now opens a removal modal instead of a bare confirm — pick a reason (Refunded / Duplicate entry / Entered by mistake / Other), and for refunds record the amount and method (Venmo, Cash, Check, GoDaddy refund, Other) plus an optional note.",
      "Feature: every removal is permanently recorded in a new removals log, shown as a 'Removals & Refunds' table at the bottom of the Enrollment tab (follows the same contest/chapter/season filters). The enrollment row is deleted as before — and the source purchase's contest flag is still cleared so the sync doesn't re-enroll — but there is now always a record of who was removed, when, why, and what was refunded.",
      "Seeded: Neil Cheshire and Joseph Lourigan's 2026 City Match Play Venmo refunds (removed before this log existed) are recorded retroactively at boot so the list is complete from day one. Refund amounts weren't captured at the time — they show blank until provided.",
    ],
  },
  {
    version: "2.16.32",
    date: "2026-07-02",
    changes: [
      "Fix: the season contest Sync no longer reports the same '9 new enrollments' on every run — the sync was creating enrollments and then its own cleanup was deleting them, endlessly. Root cause: new enrollments were saved without the purchase's customer_id, a name-based backfill then guessed which profile they belonged to, and when it guessed a DIFFERENT profile than the purchase's (split/duplicate profiles), the cleanup saw 'no backing purchase for this customer' and deleted the row — which the next sync re-created. Enrollments now inherit customer_id directly from their source purchase at creation (Guiding Principle #6), and the cleanup never deletes a row whose own source purchase is still active and carries the matching contest selection.",
      "Repair: Stu Kirksey had TWO customer profiles (Stu/Stuart split) — the exact condition that made his City Match Play enrollment vanish on every sync. A boot repair merges them into the profile holding his purchases (the other spelling becomes an alias), after which his 5/25 SEASON CONTESTS purchase enrolls him and STAYS.",
      "With the loop dead, Sync now correctly reports 0 new enrollments when nothing changed — a nonzero count on a re-run means genuinely new purchases.",
    ],
  },
  {
    version: "2.16.31",
    date: "2026-07-02",
    changes: [
      "Repair: order R747210347 (standalone SEASON CONTESTS purchase, City Match Play, 2026-05-25) parsed with a blank buyer — the order email names Stu Kirksey. The item is assigned to his profile, the order's stuart.kirksey@gmail.com captured as his, and he enrolls in City Match Play dated 5/25 automatically at boot.",
      "Fix: the season contest sync now runs at every boot — previously it only ran when new orders arrived or the Sync button was clicked, so repairs and item corrections didn't produce enrollments until one of those happened. Purchases → enrollments is now automatic on every deploy.",
      "Audit: a boot-time contest-enrollment audit (the requested 'any others like that?' check) verifies every active membership-with-contest-flags and SEASON CONTESTS purchase has its matching enrollment(s), and flags any SEASON CONTESTS purchase whose contest selection wasn't parsed at all (those silently enrolled nobody). Runs after the boot sync, so anything it reports is a genuine residual problem, with item/order identifiers for follow-up.",
      "Hardening: '(Unknown)'-named items (an early migration renames blank customers to that placeholder) can no longer create enrollments, and any existing blank or '(Unknown)' enrollment rows are purged with their source purchase logged.",
    ],
  },
  {
    version: "2.16.30",
    date: "2026-07-02",
    changes: [
      "Repair: some handicap player links pointed at the WRONG customer profile — the historical auto-linker matched players by the email on their purchases, which for guest/family purchases is the BUYER's: Will Massey's handicap link pointed at Colby Johnson's profile (why the v2.16.28 deploy still warned his Golf Genius sync would use Colby's address — the contamination wasn't an email on Massey's profile, it was the link itself), and Isabella Luna's pointed at her guardian's profile. A boot repair now re-points any link whose own player/customer name resolves uniquely to a different profile than its customer_id, moving that player's handicap rounds along with it; ambiguous names are logged and left alone, and links whose name is a known alias of the linked customer are correctly recognized as fine. After this, Massey syncs to Golf Genius as wncmassey@outlook.com and Isabella as her pinned isabellamluna7@gmail.com.",
    ],
  },
  {
    version: "2.16.29",
    date: "2026-07-02",
    changes: [
      "Feature: the NET Points Race and GROSS Points Race tabs on the Contests page now show the enrolled-player roster for the current season (player, chapter, enrollment date, sorted by chapter then name, with a count) instead of only a Coming-Soon placeholder. The roster reads the same enrollment data as the Enrollment tab, so removals and syncs reflect immediately. Standings/leaderboards remain a future feature.",
    ],
  },
  {
    version: "2.16.28",
    date: "2026-07-02",
    changes: [
      "Fix: the enrollment-date repair (v2.16.27) now also runs at boot — it only ran inside the contest sync, which fires when new orders arrive or the Sync button is clicked, so a deploy alone didn't re-date existing rows (Paul Reed's date only corrected after a manual Sync).",
      "Fix: removing an enrollment on the Enrollment tab now STICKS — the red ✗ deleted the row but left the contest flag on the backing purchase, so the next sync silently re-enrolled the player. Deleting now also clears that item's contest flag (the purchase row itself is untouched), making it the right way to remove refunded contest entries.",
      "Fix: a nameless enrollment row (blank CUSTOMER cell in the Enrollment log) is purged at boot and by every sync, with its source purchase logged so the rightful player can be identified — fix that purchase's customer and Sync re-enrolls them correctly. The sync also refuses to create enrollments from items with no customer name going forward.",
      "Repair: Colby Johnson's email (colbygjohnson8@gmail.com) was still on Will Massey's profile from their old bad merge — surfaced by the v2.16.26 Golf Genius email diff, which would have synced Massey's handicap under Colby's address, and which let orders from Colby's address resolve to Massey. The email is moved to Colby's own profile and wncmassey@outlook.com set as Massey's primary.",
      "Repair: Isabella Luna's Golf Genius sync address is pinned to isabellamluna7@gmail.com via the designated-GG-email flag — her profile's primary email is rlight@hughes.net (guardian/household), but Golf Genius has always received her own address from previous syncs; the pin preserves that exactly. Changeable any time on her profile.",
    ],
  },
  {
    version: "2.16.27",
    date: "2026-07-02",
    changes: [
      "Fix: the season contest Enrollment log showed WHEN THE DATABASE ROW WAS WRITTEN, not when the member enrolled — enrolled_at defaulted to the insert timestamp, and the sync's cleanup passes can delete and re-create rows (name/chapter corrections, dedup), re-stamping the date each time. That's why Paul Reed's NET Points enrollment (purchased with his 3/2 membership) displayed as July 2 after this session's identity repairs churned his row. Every purchase-backed enrollment now derives enrolled_at from its source purchase's order date, a repair pass re-dates all existing rows on the next sync, and the date stays correct no matter how often a row is recreated. Manual enrollments with no purchase keep their admin-entry timestamp.",
      "Fix: the contest sync and its reconciliation both used transaction_status IN ('active', NULL) — which never matches NULL in SQL — so a member whose membership row has no status value was invisible to BOTH sides: their enrollment was deleted as 'no backing purchase' and never re-created. Now uses the app-standard COALESCE(status,'active') convention, so any such silently-lost enrollments reappear on the next sync, dated by their original purchase. If new names show up in the Enrollment log after this deploy, that's this fix restoring them.",
    ],
  },
  {
    version: "2.16.26",
    date: "2026-07-02",
    changes: [
      "Fix: the Golf Genius handicap sync resolved each player's email from their most recent transaction row (matched by display name) instead of their customer profile — Golf Genius matches league members BY EMAIL, so a player whose latest transaction carried a blank (guest purchase), a buyer's email, or an old typo could be silently dropped from the sync or synced under an address GG doesn't recognize, leaving their GG handicap stale. Resolution is now canonical-first via the link's customer_id: the profile's designated Golf Genius email (the is_golf_genius flag existed in the schema for exactly this but was never read by the export), then the primary email, then any profile email — with the old transaction-snapshot method kept only as a fallback for unlinked legacy rows, so no currently-syncing player can lose their email.",
      "Diagnostics: a boot-time log-only pass lists every player whose Golf Genius sync email CHANGES under the new resolution (and anyone newly included), so the deploy log shows exactly who is affected before the nightly 02:00 sync uploads them — if a listed player's new canonical address isn't what Golf Genius knows them by, fix the profile (or set their GG-specific email flag) before the sync runs.",
    ],
  },
  {
    version: "2.16.25",
    date: "2026-07-02",
    changes: [
      "Repair: three Venmo payer names admin-identified as existing members now resolve via cid-linked name aliases — 'Leonel Vasquez' → Lee Vasquez (Austin), 'Christopher Lieck' → Wade Lieck (San Antonio), 'Dan Lehan' → Daniel Lehan (San Antonio). Their 7 unlinked ledger rows link to the right member profiles on the next boot, and any future payment or import under those name variants resolves automatically. Each alias is only created when the member resolves uniquely by name — a wrong guess is impossible.",
      "The remaining Venmo payers admin-confirmed as NOT TGF customers (the Two Man Tour owner and participants, plus personal payments) are registered as known non-customers: their ledger rows keep the payer's name for readability but are never name-resolved, never counted as 'unresolved', and never nagged about in deploy logs again.",
    ],
  },
  {
    version: "2.16.24",
    date: "2026-07-02",
    changes: [
      "Polish: Venmo ledger rows whose payer has no customer profile (37 rows / 17 payers after the v2.16.23 repair) now display the PAYER's name instead of the payment memo — the ledger reads correctly, and the moment a profile is created for one of these payers the boot backfill links their rows automatically with no further action. The per-row 'unresolved' log noise also stops repeating every boot (each row logs once, when its display is first rewritten; the summary count line remains).",
    ],
  },
  {
    version: "2.16.23",
    date: "2026-07-02",
    changes: [
      "Fix: the Venmo CSV importer stored the payment MEMO as the customer name on incoming payments ('Skins', 'Putting Contest', 'Luke+Youngs+...+Balance+Due') — the importer never used the CSV's From field, so those ledger rows could never link to a customer. Incoming payments now take the payer from the From field; the 'NAME - reason' note pattern still wins so payments made on someone else's behalf keep crediting the named player.",
      "Repair: a boot-time pass re-links the existing memo-named Venmo ledger rows (54 found in the live audit). The real payer was recoverable from the row's own description ('<payer>: <memo>'): each row is linked to the payer's profile and its customer field rewritten to the payer's canonical name, with the memo preserved in the description. Payers with no profile or an ambiguous name are left as-is and logged for review rather than guessed.",
      "Fix: name display columns that stored title-cased roman numerals (Golf Genius import wrote 'Victor Iii Arias') are normalized to proper suffix casing ('Victor III Arias') across handicap links/rounds, RSVPs, season standings, match play pools, aliases, and the ledger. Only unambiguous numeral tokens are touched (II/III/IV/VII/VIII/IX — never 'Vi' or 'V', which collide with real names).",
    ],
  },
  {
    version: "2.16.22",
    date: "2026-07-02",
    changes: [
      "Repair: the ledger customer_id verification (enabled by v2.16.21) revealed a FIFTH Victor Arias profile — customer 426, auto-created months ago when a ledger writer resolved 'Victor Arias III' before the son's real profile was findable by that name. Its name parts were stored malformed (last name 'III'), which is both why every census missed it AND a live risk: future 'Victor Arias III' name lookups match it ahead of the alias step, so new rows could keep landing there instead of on the son's real profile (308). The Arias repair now routes 426's five ledger rows (the son's registration, credit transfers, and Venmo excess-credit payout) to the son by the same name-marker rule, moves unmarked leftovers to the son (everything on that profile arrived via his name), and retires the profile. Verified on a simulated copy incl. repeat-boot stability.",
    ],
  },
  {
    version: "2.16.21",
    date: "2026-07-02",
    changes: [
      "MCP: get_acct_transactions now includes customer_id in its output. The ledger view was identity-blind — you could see a row's customer NAME but not which customer profile it was actually linked to, which made identity verification (e.g. confirming the Victor Arias III ledger rows link to the son's profile, not the father's) impossible through the connector. customer_id is the one true identity key everywhere else in the app; the MCP ledger view now honors that.",
    ],
  },
  {
    version: "2.16.20",
    date: "2026-07-02",
    changes: [
      "Repair: merged the duplicate Kyle Franz profile (316, held only a status row) into his canonical record (315), per admin confirmation.",
      "Repair: merged the three Will/William Massey fragment profiles (407, 408, 409 — between them a role, a status, a ledger row, and a membership term that was invisible on his real card) into canonical 311, and registered 'William Massey' as his name alias, per admin confirmation. Duplicate roles dedupe; distinct membership terms are both preserved.",
      "Repair: untangled the two Victor Arias profiles WITHOUT merging them — admin confirmed they are father (Victor Arias, Jr., customer 17, vicdr.dirt@yahoo.com) and son (Victor Arias, III, customer 308, v3rdgen.dirt@gmail.com), with dad making all payments. Rows on the two stray fragments (414, 434) and any misrouted rows on the real profiles are routed by the name text they carry (III/3rd/v3rdgen → son; Jr/vicdr → dad; unmarked payment-side strays → dad), the fragments are retired, dad's transactions now display 'Victor Arias Jr' (son's already displayed 'Victor Arias III'), and suffix-name aliases were added for both. The bare name 'Victor Arias' is deliberately left ambiguous so the identity lookup keeps refusing to guess between them — the pair is registered as known-distinct so the duplicate-name census stops warning about it.",
      "Improvement: the alias that merge_customers auto-creates for a renamed source profile now carries the target's customer_id, so it resolves by id instead of relying on the name-join fallback.",
    ],
  },
  {
    version: "2.16.19",
    date: "2026-07-02",
    changes: [
      "Repair: alias rows whose customer_id points at a customer deleted by an old merge are now re-pointed at boot to the unique living profile with the alias's exact customer name (the census-identified live case: nickname 'Bill' → 'Bill Barstow', left behind by the merge that deleted customer 362). When no unique name match exists the dead id is cleared instead, so resolution falls back to the name join rather than referencing a deleted profile. Idempotent; each repair is logged.",
    ],
  },
  {
    version: "2.16.18",
    date: "2026-07-02",
    changes: [
      "Repair: merges the duplicate Dan Stich profile into his canonical record (customer_id 298 — all 22 transactions, email, phone) and registers 'Daniel Stich' as a name alias, per admin confirmation that he is one person. The duplicate held no transactions so it was invisible in the UI; it was blocking name-keyed housekeeping rows from linking (the identity lookup refuses to guess between same-named profiles). Runs at boot, moves every linked table via the v2.16.13 merge machinery, and is fully idempotent; the same boot's backfill then links the rows that were waiting.",
    ],
  },
  {
    version: "2.16.17",
    date: "2026-07-02",
    changes: [
      "Diagnostics: new boot-time duplicate-name census logs every pair of customer profiles sharing the same first+last name, with each profile's emails and per-table reference counts (transactions, memberships, handicap links, etc.). Needed because the v2.16.14 ambiguity guard intentionally leaves name-keyed rows unlinked when two same-named profiles exist — the census puts everything needed to pick the canonical profile in the deploy log, where duplicate profiles with zero transactions are otherwise invisible (the Customers page and MCP tools group by transactions). Log-only; changes nothing.",
    ],
  },
  {
    version: "2.16.16",
    date: "2026-07-02",
    changes: [
      "Fix: the member_plus schema migration has been failing on every production boot since it shipped — it rebuilt the customers table from a hardcoded 14-column definition, but the live table has grown to 17 columns via later migrations, so the data copy aborted (leaving a stale customers_new artifact that then blocked every retry with 'already exists'). Net effect: the status CHECK constraint never gained 'member_plus', so saving a MEMBER+ status failed in production. The migration now rebuilds from the live schema (current columns, indexes, and triggers preserved), clears the stale artifact, and was verified against a simulated production schema: data intact, MEMBER+ writable, autoincrement ids preserved, idempotent. Customer data was never at risk — the old failure happened before the original table was touched.",
      "Diagnostics: the orphan-FK census (v2.16.13) now breaks its counts down by deleted customer_id — and for orphaned aliases prints the alias itself — so the deploy log identifies WHICH old merge left the rows instead of just how many. (The v2.16.13 deploy found exactly one: a customer_aliases row pointing at a deleted id; next boot will name it.)",
      "Fix: the Chalfant boot repair logged 're-attributed 1 item(s)' on every boot because its known-order UPDATE matched the already-repaired row unconditionally — a no-op write reported as work. It now skips rows that are already fully correct, so the log only reports genuine repairs.",
    ],
  },
  {
    version: "2.16.15",
    date: "2026-07-02",
    changes: [
      "Security: role levels are now actually enforced as a hierarchy (view-only < manager < admin). Previously only 'admin' was checked — any logged-in view-only session could call every manager endpoint (update customers, apply credits, send balance-due emails, import rosters). A view-only PIN is now read-only in practice, not just in name; manager and admin sessions are unaffected.",
      "Security: the login rate limiter keyed attempts on the FIRST X-Forwarded-For entry, which the client controls — an attacker could bypass PIN brute-force protection by rotating a fake header (or deliberately lock out a victim's IP). It now keys on the last hop, which Railway's edge proxy appends and the client cannot forge.",
      "Security: every HTML-escaping helper across the app (10 copies in 9 files) now escapes quote characters too. The old div.textContent trick escaped < > & but NOT quotes, and these helpers are routinely interpolated into HTML attributes (data-customer-name=\"...\") — a customer name containing a double-quote could break out of the attribute and inject markup (stored XSS via any imported roster/RSVP/order name). All copies now use one quote-safe implementation.",
    ],
  },
  {
    version: "2.16.14",
    date: "2026-07-02",
    changes: [
      "Fix: the Archive/Unarchive button on customer cards did nothing — the route accepted the field but update_customer_info()'s internal whitelist silently dropped it while still reporting success. 'archived' is now allowed through, and the button also sends customer_id so the update is keyed by identity instead of display name.",
      "Fix: editing a transaction's customer name (admin inline edit) changed the display name but kept the OLD person's customer_id on the row, so credits, winnings, memberships, and Venmo balance-due matching still attributed the transaction to the previous customer. The endpoint now re-resolves customer_id whenever the name actually changes (an explicit customer_id in the payload, e.g. from Assign Member, still wins).",
      "Fix: Assign Guest explicitly NULLed the item's customer_id, leaving the guest's registration invisible to every id-keyed feature until a boot backfill guessed at it. It now resolves (or creates) the guest's own customer record at assign time.",
      "Fix: the quantity-expansion backfill (Audit tab) built partner rows as copies of the buyer's row, so each partner row carried the BUYER's customer_id — a named partner's registration was attributed to the buyer's identity. Named partners now get their own resolved customer record; unnamed 'Guest of' placeholders get no id rather than the wrong one.",
      "Fix: customer identity lookup now refuses to guess when two different customers share the exact same first+last name — previously it silently picked one (LIMIT 1), which could attach orders, credits, and payments to the wrong same-named person. An email or alias can still disambiguate; otherwise a fresh profile is created and the boot-time shared-email auto-merge collapses it once an email ties them together.",
      "Fix: alias lookups (both email- and name-aliases) resolved the customer by reconstructing 'first last' from the customers table instead of using the alias row's own customer_id column — misfiring for names with suffixes/middle names and ambiguous when two customers share a name. The alias's customer_id is now used directly, with the legacy name-join kept only as a fallback for unlinked alias rows.",
      "Fix: correcting a customer's name on the Info tab now propagates to the season standings and match-play pool member lists (season_contests/cmp_pool_members display-name copies), which previously kept rendering the old name.",
    ],
  },
  {
    version: "2.16.13",
    date: "2026-07-02",
    changes: [
      "Fix: the boot-time duplicate-customer auto-merge (shared-email detection) crashed mid-merge on every run — it inserted into a customer_aliases column that doesn't exist (alias_name; the real column is alias_value). The crash hit AFTER transactions were re-pointed and the duplicate's emails were stripped but BEFORE the duplicate row was deleted, so every auto-merged duplicate left behind a stripped 'ghost' profile. Column name fixed in both merge branches.",
      "Fix: merging customers (the Merge button, the boot-time auto-merge, and the boot-time attribution repairs) moved only transactions, emails, and TGF payouts before deleting the source profile — membership terms, member status history, roles, RSVPs, accounting ledger rows, expense links, handicap links/rounds, season contest and match play enrollments, and 10 other linked tables kept pointing at the deleted customer_id, silently orphaning that data. All merge paths now route through a shared helper (_repoint_customer_fks) that re-points every customer-linked table (28 columns across 24 tables) before the source row is deleted.",
      "Repair: a boot-time pass re-points rows orphaned by the two known pre-fix merges (Joseph Lourigan 406→83, Tim Watson 94→433) and logs a count-only census of any rows still referencing deleted customer_ids, so the deploy log shows whether any other historical merges left orphans (no guessing — unknowns are reported, not auto-moved).",
      "Fix: the boot-time player-status autocorrect (membership purchase → MEMBER, played-more-than-once → GUEST) updated only the legacy customers.current_player_status column and never wrote the customer_statuses history table — but the Customers page derives badges from the LATEST HISTORY row, so an autocorrected status could keep rendering its stale pre-correction badge indefinitely. A new boot-time reconciler appends a matching history row wherever the newest history row disagrees with the column (the column is authoritative: every writer updates it, only some update history). Verified idempotent across repeated boots.",
    ],
  },
  {
    version: "2.16.12",
    date: "2026-07-02",
    changes: [
      "Fix: the Venmo balance-due auto-matcher resolved the payer by Venmo DISPLAY NAME first and only consulted the @handle when the name found nothing — but the display name is free text the payer controls, while the @handle maps to exactly one customer via customers.venmo_username. A payer whose account displays another customer's registered name (same-surname family members do this routinely) could clear the OTHER customer's balance due whenever the amounts fell within the ±$1 tolerance, marking the wrong person paid. The chain is now handle-first: when the @handle resolves to a known customer it is trusted exclusively (their balance_due items are looked up by customer_id, with a canonical-name fallback for legacy unlinked rows), and display-name/alias matching only runs when the expense has no handle or the handle isn't registered to any customer. A known payer with no open balance now lands in no_candidate for manual review instead of borrowing a same-named customer's balance.",
      "Fix: the +PAY child item created on a Venmo match re-resolved its customer_id from the parent's name/email instead of inheriting the parent's customer_id directly — the payment settles that specific item's balance, so re-resolution could pin the child to a different same-named customer. It now inherits parent.customer_id, falling back to resolution only for legacy parents with no id.",
    ],
  },
  {
    version: "2.16.11",
    date: "2026-07-02",
    changes: [
      "Fix: the 2.16.6 Withdraw Player rewrite read only the combo pricing columns (tgf_markup_9/side_game_fee_9) for any 9-hole event — but standalone \"9 Holes\" events store their pricing in the base columns (tgf_markup/side_game_fee), which the edit modal only populates for the single-format layouts. A custom-priced standalone 9-hole event therefore showed default amounts ($8 markup / $7 games) in the Withdraw Player and Partial Refund component lists instead of its configured pricing, and those amounts feed directly into withdrawal credit money. The lookup now chains _9 column → base column → default, the same fallback the Apply Credit modal has always used. 18-hole and combo events were unaffected.",
      "Fix: for a customer whose canonical name differed from their transaction-history name (the population the 2.16.9 name overlay targets), saving the Info tab twice could silently drop the second save's items-level fields (DOB, shirt size, address). The first save renames every transaction row to the canonical display name server-side, but the card's local grouping key kept the old name — so the second save posted a name that matched zero rows while still reporting \"Saved!\". Two-part fix: update_customer_info() now keys the items update by customer_id when it's resolved (with a name-keyed sweep only for legacy unlinked rows), so a stale display name can never target zero rows; and patchCustomerLocal() now mirrors the backend's display-name sync into the local customer object (cust.name, item.customer, expandedNames) and triggers a re-render when the name changed, so every data-customer-name attribute picks up the new key immediately.",
    ],
  },
  {
    version: "2.16.10",
    date: "2026-07-02",
    changes: [
      "Security: GET /api/items, /api/stats, /api/audit, and /api/data-snapshot had no authentication — any anonymous caller who knew the URL could download the complete customer database (names, emails, phones, addresses, DOBs, full order history). All four now require a logged-in session (@require_role('view-only')), matching the already-protected /api/customers. The five handicaps read endpoints (/players, /rounds, /for-customer, /index-map, /settings) were also unauthenticated — including one that performed a database write on an anonymous GET — and are now gated the same way. Pages that loaded data before login (Transactions, Customers, Events, Handicaps) now start their initial fetch from onAuthReady() instead, so an unauthenticated visitor sees the login modal with no failed requests behind it and data loads immediately after login (RSVPs and Contests already worked this way). The legacy mcp_server_remote.py helper now logs in before reads, not just writes.",
      "Security: the MCP endpoint's auth middleware failed OPEN — if MCP_CLIENT_ID/MCP_CLIENT_SECRET were ever missing from the environment, every request skipped authentication entirely, leaving write tools (update/delete transactions, delete events) publicly callable at /mcp/mcp. It now fails CLOSED with a 503 and a loud log line until both env vars are configured. (Production has them set, so behavior there is unchanged; this closes the misconfigured-deploy hole.)",
    ],
  },
  {
    version: "2.16.9",
    date: "2026-07-02",
    changes: [
      "Fix: mobile customer cards read DOB and shirt size from only the first purchase row (items[0]) instead of scanning every item like the desktop Info tab does — since mobile has no separate edit/view mode (fields are always live), saving any change could silently blank a customer's DOB/shirt-size if it wasn't on their first order. Now matches desktop's scan-all-items lookup.",
      "Fix: the Winnings tab could show one member another member's payout history if they shared a first+last name — get_customer_winnings() resolved the customer via an unqualified name match with no tiebreaker. GET /api/customers/winnings now accepts customer_id (the Customers page already has it resolved on every card) and uses it directly.",
      "Fix: a corrected first/last name on the Info tab could fail to fully propagate and the old name would reappear as an apparent duplicate profile after a refresh — email/phone/chapter were already overlaid with the canonical customers-table value on every page load, but first_name/last_name never were. Added them to the same overlay.",
      "Fix: several admin bulk-action buttons on the Handicaps page (Purge 18-hole Scores, Auto-link Players, Create Customers for Unlinked, Repair Links, and the inline \"add customer for player\" flow) read response fields without checking HTTP status first, so a server error rendered as \"Deleted undefined invalid round(s)\" instead of a real error message. All now check response.ok and surface the actual error.",
      "Fix: creating a vendor only checked for an existing customer by company_name — a vendor whose display name happened to exactly match an existing personal customer's name (e.g. a sole-proprietor course pro billed under their own name) would get a second, disconnected customers row instead of reusing the real one. Now also checks first+last name.",
      "Polish: the Winnings/Scores tabs' \"lookup failed\" and \"genuinely has zero records\" messages were easy to conflate at a glance; reworded the lookup-failure message to make clear it's a linking problem, not an empty-data state, and both tabs (plus Aliases) now check response.ok so a real server error surfaces distinctly instead of rendering as an empty list.",
    ],
  },
  {
    version: "2.16.8",
    date: "2026-07-01",
    changes: [
      "Fix: six more places created a customer profile with no linked customer_id, the same defect fixed for +Add Customer/Roster Upload/RSVP-Import in 2.16.7 — the Handicap \"create customers for unlinked\" bulk tool, applying credit to a Golf Genius RSVP (two copies of the same insert), overpayment and excess-credit rows posted mid-credit-application, a partial-refund child row, and the secondary items row link_rsvp_to_customer() creates when linking an RSVP from a member's second email. All now resolve or copy a real customer_id at insert time instead of leaving it NULL forever. 'Handicap Import' rows were also missing from every placeholder-merchant exclusion list (dashboard.js, customers.html, mcp_server.py, and ~10 reporting queries in database.py), so they were silently counted as real transactions — added alongside the other administrative merchants everywhere that list appears. The RSVP Email Link exclusion is also dropped from the boot-time customer_id backfill: that merchant only ever fires once the target customer is already resolved, so the 'will get picked up under its own name later' assumption behind the original exclusion was actually never true — confirmed via a live-data audit that found exactly this pattern on a real profile.",
      "Fix: merge_customers() could silently produce a split-identity record — if the target name in a Customers-page Merge didn't have an exact first+last match in the customers table (a suffix, a middle name, or simply no row under that spelling), the transactions still got renamed to the target's display name but the customer_id/customer_emails/tgf_payouts reassignment was skipped entirely, with no error surfaced (the UI showed \"Merged!\" either way). The function now accepts the customer_ids the Customers page already has resolved on screen and uses them directly, and raises a real error before any write happens if the target still can't be resolved. Live-data audit (see below) found two real customers already split this way from before this fix existed; boot-time repair functions (_repair_lourigan_attribution(), _repair_watson_attribution()) merge them automatically on next deploy, following the same pattern as the existing Chalfant/Massey repairs.",
      "Ops: ran a live-data audit via the TGF Transaction Tracker MCP connector across all 1,630 items to size these bugs against real data (requested after a manual review of individual profiles). Found 1 item with a NULL customer_id (a second-email RSVP-link row for an existing member), 0 active merge-corrupted (\"split identity\") records, and 2 customers fragmented across two customer_id records each (Joseph Lourigan, Tim Watson) — both now covered by the new repair functions above.",
    ],
  },
  {
    version: "2.16.7",
    date: "2026-07-01",
    changes: [
      "Fix: customers added via the \"+ Add Customer\" modal or Roster Upload (and unmatched RSVPs auto-added as new customers) never got a canonical customers-table row — create_customer()/import_roster()/create_customer_from_rsvp() only wrote the items placeholder row and left customer_id NULL forever, since the boot-time _backfill_customer_ids() repair explicitly excluded those merchant types. Every customer_id-gated feature broke silently for anyone whose only footprint was one of these paths: the Membership Terms card (and its \"+ Add term\" button) didn't render at all, and Member Status / Roles edits on the Info tab appeared to save (\"Saved!\", badge updated locally) but were actually dropped server-side with no error, reverting on the next refresh. All three creation paths now call _resolve_or_create_customer() to create the customers row up front, and the backfill exclusion is removed so existing affected profiles (e.g. a customer added via Roster Import who's never made a real purchase) self-heal on next deploy.",
      "Fix: the Customer Info-tab Save button re-derived customer_id server-side via a fragile items/customers name match instead of using the customer_id the frontend already had resolved on the card — so a status or role change could silently no-op (200 OK, but no customer_statuses row written) whenever that name match missed, with the illusion of success from an optimistic local UI patch until the next refresh reasserted the old value. /api/customers/update and /api/customers/sync-roles now accept an explicit customer_id and use it directly; sync-roles failures (previously an unchecked, silently-dropped fetch) now surface an alert instead of failing invisibly.",
      "Fix: editing a customer's Info tab could silently revert to read-only and discard unsaved changes mid-edit — the 30-second auto-refresh (added to keep multiple managers in sync) rebuilt and re-rendered every customer card unconditionally, and every render path always starts the Info tab back in read-only view. The refresh now skips itself while any Info-tab edit panel is open or an edit field is focused, same as it already did for the Credit and Login modals.",
    ],
  },
  {
    version: "2.16.6",
    date: "2026-07-01",
    changes: [
      "Fix: the Withdraw Player modal's Credit Components (Included Games, Net Games, Gross Games) were computed from the live GAMES prize matrix — a share of the current pot divided by however many net/gross players happen to be registered right now. That matrix tracks payouts to game winners, not what the withdrawing player actually paid at registration, so the numbers drifted from the real charge (e.g. Included Games showed $12 instead of the event's configured $14, Net/Gross Games showed $40 instead of the flat $30 per-game add-on) and kept shifting as other players were added or withdrawn from the same event. Included Games now reads the event's configured Inc. Games amount (holes-aware for 9/18 Combo events), and Net/Gross Games now use the same flat per-game add-on (getPerGameAddon) as the pricing calculator and Apply Credit modal — so all three components match what was actually charged and sum back to the player's price.",
    ],
  },
  {
    version: "2.16.5",
    date: "2026-06-24",
    changes: [
      "Fix: Participation was dropping most registrations for yesterday's s9.15 The Quarry (36 players) and a9.15 Teravista (20 players) — only the handful whose items.item_name matched events.item_name byte-for-byte were showing the new event as Last Played. The JOIN is now TRIM(...) COLLATE NOCASE on both sides so a parsed-from-email name like 's9.15 THE QUARRY' resolves against a manager-entered 's9.15 The Quarry' (and trailing-space variants stop silently dropping rows). The cell also now renders the canonical events.item_name so every row's event label reads consistently regardless of how it was originally parsed.",
      "Fix: clicking a past event from Participation flipped the Events page to Past correctly but the specific event still didn't expand. The auto-expand block was calling renderEvents() recursively and ALSO calling toggleEventDetail after — so the recursive pass expanded the row and the outer pass immediately collapsed it. The outer call is now removed; the recursive pass falls through to the expand on its own.",
    ],
  },
  {
    version: "2.16.4",
    date: "2026-06-24",
    changes: [
      "Participation: Last Played now strictly uses events.event_date (INNER JOIN events on item_name, event_date IS NOT NULL, event_date <= today). The previous COALESCE-to-order_date fallback let purchase dates masquerade as play dates AND let future-dated registrations leak through (their order_date was already in the past). The price of strictness: legacy items with no matching events row don't count — the fix is to backfill those into events, not to silently fake the date.",
      "Participation: new Next Event column shows each customer's soonest upcoming registration — MIN(events.event_date) where event_date > today, with the matching item_name. Same date+name+link cell as Last Played; default sort on the column header is ascending (soonest first); nulls always go to the end. Makes re-engaged players visibly distinct from dormant ones in one glance.",
      "Events: /events?item=<name> deep-links now resolve past events too. Previously the auto-expand searched the currently-filtered view (defaults to Upcoming), so a Last-Played link from Participation hit the Events tab but found nothing to expand. The handler now searches the full allEvents list and flips eventTimeFilter to 'past' or 'upcoming' before calling toggleEventDetail so the row exists in the rendered DOM.",
    ],
  },
  {
    version: "2.16.3",
    date: "2026-06-24",
    changes: [
      "Participation: the Last Played cell now shows the event name on a second line as a link to the Events tab (deep-links via /events?item=<name>, which auto-expands the event detail panel on arrival). The date stays the primary read; the event name is muted and smaller so the column is still scannable. /api/participation/players returns last_event_name alongside last_event_date — picked from the items row that owns MAX(played_date) for that customer, tiebroken by items.id DESC so multi-event days resolve to the most recently inserted registration deterministically.",
    ],
  },
  {
    version: "2.16.2",
    date: "2026-06-24",
    changes: [
      "Participation: Last Played + the 12-month / prior 12-month frequency counts now use the actual event date (when the round was played), not the purchase date (when the registration was bought). Joins items to the events table via items.item_name = events.item_name and uses COALESCE(events.event_date, items.order_date) so legacy items with no matching events row still appear with their order_date as a fallback. Future-dated events are now excluded — a player who pre-registered for next month's event no longer looks like a recent play, so an otherwise-real dormancy signal isn't masked. Previously, a player who bought a May event in February would show February as Last Played; now they show May (and only after May actually happens).",
    ],
  },
  {
    version: "2.16.1",
    date: "2026-06-24",
    changes: [
      "Participation: player names in the table are now links to the Customers page (open the same player's full profile via /customers?name=...). Same pattern Handicaps and Transactions use, so the click target is consistent across pages. Click handling on the rest of the row is unchanged — clicking the name navigates; clicking anywhere else still toggles the selection checkbox.",
    ],
  },
  {
    version: "2.16.0",
    date: "2026-06-24",
    changes: [
      "New: Participation page (top nav, between Handicaps and Payouts) for identifying lapsed players and re-engaging them. Each active customer (MEMBER / MEMBER+ / GUEST / 1st TIMER — excludes FORMER and archived) appears with their last-event date, days since, plays in the last 12 months, plays in the prior 12 months, and a Trend arrow (up / down / flat / new). 'Event' means a non-membership, non-season-contest items row with transaction_status active or rsvp_only and parent_item_id NULL, so membership renewals don't paper over an actual dormancy. Filter by chapter, status, dormancy threshold (30 / 60 / 90 / 180 / 365 days — default 90), and 'has email only' so the audience matches who can actually be emailed. Multi-select rows (or Select-all-visible) → Send Re-engagement Email composer with an editable subject + HTML body (TGF-voice default I drafted) and merge variables {first_name}, {last_name}, {days_since}, {last_event}, {chapter}, {plays_12mo}, {last_event_phrase}. A live preview shows the merged message for each recipient (Prev / Next to scrub through the selection); Send to All pushes through the same Microsoft Graph hook as the handicap cards and returns a per-recipient sent / skipped / failed log. Skipped rows (no primary email) are surfaced before sending so the count you confirm matches what actually goes out.",
    ],
  },
  {
    version: "2.15.30",
    date: "2026-06-24",
    changes: [
      "Fix: multi-item orders bought for several players were attributed to the wrong person in the Transactions list. A 3-spot Kissing Tree order paid by Doug Hamilton with partners Casey Purvis and Chris Best displayed as \"Chris Best — 3 items — $657.00\" because the order-group summary used group[0].customer — i.e. whichever row sorted alphabetically first. The parser's _expand_quantity_rows reliably marks the buyer: only the buyer's row keeps customer_email and the extras get a 'Purchased by <buyer>' note. dashboard.js now uses a pickBuyerRow() helper that prefers the row with customer_email set and without a Purchased-by note, then falls back to the first non-extra row — applied to both desktop and mobile order-group renderers so the order header correctly reads the buyer's name (and order date/time) in every multi-player transaction.",
    ],
  },
  {
    version: "2.15.29",
    date: "2026-06-24",
    changes: [
      "Fix: when a customer paid for a TGF MEMBERSHIP renewal their Renewal date flipped to the new expiration (green) but their status badge stayed FORMER until the next daily scheduler run or app boot. record_renewal_for_item was opening the new term row in customer_memberships but never invoking sync_player_status_with_terms, so current_player_status stayed at expired_member and the most recent customer_statuses row stayed at 'former' — and deriveStatus() in the Customers list reads that history row first. record_renewal_for_item now calls sync_player_status_with_terms immediately after inserting the term, which both flips current_player_status to active_member and writes a fresh 'member' history row so the MEMBER badge appears the moment the order is parsed.",
    ],
  },
  {
    version: "2.15.28",
    date: "2026-06-23",
    changes: [
      "Fix: handicap CSV export (and Golf Genius sync) sometimes shipped a stale handicap index for a player whose UI clearly showed the current one — caused by two handicap_rounds player_name variants linking to the same customer email (e.g. a legacy un-normalized name alongside the current First Last form). The export deduped by email but kept whichever variant happened to be alphabetically first, so a stale record could win. The export now groups candidates by email and picks the one with the most recent round date (tiebreak: most active rounds, then total rounds) so the exported index always matches the freshest data shown in the UI. /api/handicaps/export-preview now returns a duplicate_emails block under _debug listing every collision and which player_name was chosen vs dropped, so the underlying duplicates can be cleaned up at the source.",
    ],
  },
  {
    version: "2.15.27",
    date: "2026-06-01",
    changes: [
      "Customers: added \"Cash App\" as a refund-method option in both the Refund Credit modal and the Apply-Credit custom-refund picker. The backend already accepted Cash App for the /refund and /payout-credit endpoints — the dropdowns just hadn't exposed it, so Cash App refunds had to be recorded under another method. Both pickers now match the backend allowlist.",
    ],
  },
  {
    version: "2.15.26",
    date: "2026-05-28",
    changes: [
      "Fix: Add Player no longer falsely reports \"<name> is already registered for this event\" for someone who isn't on the roster. The duplicate guard was matching against ALL historical registrations (including credited/refunded/withdrawn/transferred rows and child-payment rows), so a player who deleted themselves — or was refunded/withdrawn/credited/transferred out — could not be added back even though they no longer appeared in the player list. The guard now mirrors the active-roster filter: it only blocks when a matching-name registrant is currently active (excludes inactive statuses and child payments).",
    ],
  },
  {
    version: "2.15.25",
    date: "2026-05-26",
    changes: [
      "Fix: resolve_player_email step 3 is now a name-based customer_emails lookup (joins customers by first+last name and via name aliases) — fixes customers whose credit-transfer item has a stale/null customer_id so the customer_emails customer_id lookup fails silently",
      "Fix: removed broken _backfill_customer_emails_from_customers_table (customers table has no email column); removed broken step 3 that queried customers.email",
    ],
  },
  {
    version: "2.15.24",
    date: "2026-05-26",
    changes: [
      "Fix: resolve_player_email now checks customers.email directly (step 3) before falling back to items snapshot — fixes all customers whose email was entered via the UI edit form but not in customer_emails",
      "Boot migration: _backfill_customer_emails_from_customers_table copies every customers.email into customer_emails at startup so future lookups hit the fast path",
    ],
  },
  {
    version: "2.15.23",
    date: "2026-05-26",
    changes: [
      "Fix: crash-loop on boot — customer_emails PK is email_id not id; fixed _promote_lone_customer_emails_to_primary and resolve_player_email to use correct column name",
      "Fix: wrapped boot migration in try/except so a failure is non-fatal",
    ],
  },
  {
    version: "2.15.22",
    date: "2026-05-26",
    changes: [
      "Fix: balance-due (and all send paths) now resolve email for customers whose address was stored with is_primary=0 — previously fell through to the stale items.customer_email snapshot (e.g. typo address) even when a correct email was on file",
      "Boot migration: auto-promote lone non-primary emails to is_primary=1 across the whole customer_emails table so the fix is proactive",
    ],
  },
  {
    version: "2.15.21",
    date: "2026-05-26",
    changes: [
      "Knockout Bracket: winner auto-advances to the correct slot in the next round when a match is saved",
      "Knockout Bracket: removed Stableford Pts inputs — points are for pool play only; bracket tracks winner, margin, and event",
    ],
  },
  {
    version: "2.15.20",
    date: "2026-05-26",
    changes: [
      "Knockout Bracket: added Clear Bracket button (DELETE /api/cmp/bracket) to reset all bracket slots for a season/chapter",
      "Knockout Bracket: added event dropdown to each match footer so the TGF event where the match was played can be recorded alongside the score",
    ],
  },
  {
    version: "2.15.19",
    date: "2026-05-26",
    changes: [
      "Fix: customers table query used customer_name column (doesn't exist); now uses first_name || last_name",
    ],
  },
  {
    version: "2.15.18",
    date: "2026-05-26",
    changes: [
      "Fix: season contest cleanup now backfills customer_id BEFORE reconciliation so orphaned rows (e.g. Eduardo Melchor) are properly removed",
      "Fix: added name-based fallback reconciliation for rows with NULL customer_id that still lack a valid backing purchase",
    ],
  },
  {
    version: "2.15.17",
    date: "2026-05-26",
    title: "Season Contests: reconciliation cleanup + manual delete button",
    changes: [
      "Sync now runs a reconciliation pass: any enrollment where the customer has no valid backing season contest purchase (checked by customer_id) is automatically removed. This is what cleans up Eduardo Melchor and others who were enrolled via Hill Country Matches before the item-type guard existed.",
      "Admin/manager can now manually delete individual enrollments via a × button in both the Enrollment table and the Not-Yet-in-a-Pool panel, for edge cases the auto-cleanup can't handle.",
      "Added manually_enrolled flag to season_contests: when an admin manually enrolls a player (cash payment, admin override) the flag is set to 1, protecting the row from auto-cleanup. Only auto-sync-sourced rows with no valid purchase are removed.",
      "DELETE /api/season-contests/<id> endpoint added.",
      "CLAUDE.md Guiding Principle #6 updated: customer_id is the explicit lookup standard for every query, dedup, cleanup, and cross-table join — never compare customer name strings.",
    ],
  },
  {
    version: "2.15.16",
    date: "2026-05-26",
    title: "Season Contests: customer_id-based dedup and chapter correction",
    changes: [
      "Enrollment cleanup now works by customer_id, not by customer_name string. 'Stuart Kirksey' and 'Stu Kirksey' share a customer_id, so the cleanup correctly identifies them as the same person and collapses to one canonical-name row.",
      "Chapter correction now resolves via customer_id → customers.chapter instead of customer_name string lookup. This fixes cases where the enrollment name is an alias (not the canonical name) and the name-based chapter lookup returned blank.",
      "Sync now calls _backfill_customer_id_on_season_contests before cleanup so alias names get their customer_id resolved (Stuart → Stu Kirksey's customer_id) before the dedup pass runs.",
      "Added explicit dedup pass: after name/chapter correction, any remaining (customer_id, contest_type, season) group with > 1 row is collapsed to the canonical-name row.",
    ],
  },
  {
    version: "2.15.15",
    date: "2026-05-26",
    title: "Season Contests: never enroll from golf event items (Hill Country Matches, etc.)",
    changes: [
      "net_points_race / gross_points_race / city_match_play flags are now enforced as null for all non-membership/contest item types. Hill Country Matches is a golf event, not a season contest — buying it must never create a season contest enrollment even if the event involves match play format.",
      "Added _is_contest_item() guard in parser.py: flags are only carried through to the DB row when item_name is 'TGF MEMBERSHIP' or 'SEASON CONTESTS'. All other item types get null regardless of what the LLM extracted.",
      "Sync query now explicitly restricts to MEMBERSHIP / SEASON CONTESTS item names, so flagged event items can never re-enter through the sync path.",
      "On sync, bad flags are cleared from event items in the DB (UPDATE items SET ...=NULL) and any season_contests rows that were sourced from a non-membership/contest item are deleted.",
    ],
  },
  {
    version: "2.15.14",
    date: "2026-05-26",
    title: "Parser: SEASON CONTESTS chapter always null; address never sets chapter",
    changes: [
      "Shipping address (or any address) must never determine a player's chapter. Added a code-level guard in parser.py: if the item name is 'SEASON CONTESTS', chapter is forced to null regardless of what the LLM extracted. The LLM had no valid chapter source for contest-only items and was grabbing the shipping city.",
      "Strengthened the parser prompt to explicitly state that SEASON CONTESTS items (SKU 26-SC) must always have a blank chapter — there is no golf course, therefore no chapter to infer.",
    ],
  },
  {
    version: "2.15.13",
    date: "2026-05-26",
    title: "Season Contests: always use canonical customer chapter, never items.chapter",
    changes: [
      "Season contest enrollments now always derive chapter from the customer's canonical chapter in the Customers table. Previously, items.chapter (which captures golf event/course location or GoDaddy shipping address city) was used when non-blank — this caused Luke Youngs to show 'San Antonio' even though his profile chapter is 'Austin' because his shipping address is in San Antonio.",
      "The chapter-correction cleanup now handles any chapter value that doesn't match the customer's canonical chapter, not just blank ones. On next sync, wrong-chapter rows are updated to the correct chapter (or deleted if the correct row already exists).",
    ],
  },
  {
    version: "2.15.12",
    date: "2026-05-26",
    title: "Season Contests: fix independent-contest sync logic, add customer_id FKs to CMP tables",
    changes: [
      "Reverted incorrect 'full bundle = all three' assumption in SEASON CONTESTS sync. Each contest (NET Points Race, GROSS Points Race, City Match Play) is now enrolled only when its own explicit keyword appears in the item options — 'NET' for NET race, 'GROSS' for GROSS race, 'MATCH PLAY' for City Match Play. They are completely independent purchases.",
      "Removed the incorrect side-effect where detecting 'NET' also auto-enrolled the player in City Match Play. The '(City & Fellowship Cup)' phrase in 'Points NET Bundle' describes the NET race scope, not a separate contest enrollment.",
      "Added customer_id FK columns to cmp_matches (player1_id, player2_id, winner_id) and cmp_bracket (player_id, opponent_id, winner_id) via idempotent ALTER TABLE migrations. Every customer reference now has a path back to the single customers table FK — name columns remain as display labels only.",
    ],
  },
  {
    version: "2.15.11",
    date: "2026-05-26",
    title: "Season Contests: enrollment auto-load, chapter fix, badges, full-bundle sync",
    changes: [
      "Enrollment tab now auto-loads when selected, pre-filling the current year so you see results immediately without clicking Load.",
      "Sync now falls back to the customer's canonical chapter (from the Customers table) when an item's chapter field is blank — fixes Stuart/Isaac/Dow showing '—' in the enrollment table even though their profiles have a chapter set.",
      "Standalone 'SEASON CONTESTS' items with no NET/GROSS qualifier are now treated as the full bundle (NET Points Race + GROSS Points Race + City Match Play). Previously they enrolled nobody.",
      "After syncing a standalone SEASON CONTESTS item, the item's net_points_race / gross_points_race / city_match_play flags are stamped 'YES', so the customer profile badges (NET Pts, GROSS Pts, Match Play) now appear for players who bought a separate SEASON CONTESTS item rather than having it bundled into their membership.",
      "Customer profile badge logic now checks all items (not just the membership item) so any item carrying contest flags contributes to the displayed badges.",
      "Blank-chapter enrollment rows are cleaned up automatically during sync when a properly-chaptered row exists for the same customer/contest/season.",
    ],
  },
  {
    version: "2.15.10",
    date: "2026-05-26",
    title: "Match Play: fix duplicate player in Not Yet in a Pool panel",
    changes: [
      "When the same person is enrolled under two different names (e.g. 'Stu Kirksey' and 'Stuart Kirksey'), they now appear only once in the unassigned panel. Deduplication is now done by customer_id (not just by name string) after the canonical-name map is built, so both enrollment rows collapse to the same canonical name.",
    ],
  },
  {
    version: "2.15.9",
    date: "2026-05-26",
    title: "Match Play: compact single-line match rows",
    changes: [
      "Fixed the grid column count (was 10, needed 11) that caused the Clear button to wrap onto its own second line for every match. All 11 columns — dot, player 1, vs, player 2, winner, margin, pts P1, pts P2, event, save, clear — now render on a single row.",
      "Tightened sizing throughout: reduced gap, padding, font size, and input widths (winner selector 105px, margin 62px, stab inputs 40px, event selector 130px). Winner options now show first name + 'W' (e.g. 'Kelly W') for brevity; event options show MM/DD + 14-char truncated name with full name on hover.",
    ],
  },
  {
    version: "2.15.8",
    date: "2026-05-26",
    title: "Match Play: event selector on each match row",
    changes: [
      "Each match row now has an Event dropdown populated from the live events list (sorted newest first, showing MM/DD + event name). Selecting an event and saving links the match to that TGF event via a FK on cmp_matches.event_id.",
      "DB: idempotent migration adds event_id column (REFERENCES events(id) ON DELETE SET NULL) to cmp_matches on existing deployments. cmp_get_matches() and cmp_save_match() updated to join/store event data.",
      "The selected event persists when the page reloads — loadMatchScores() restores the event selector and shows a read-only MM/DD + name label for view-only users. Clearing a match also resets the event selector.",
    ],
  },
  {
    version: "2.15.7",
    date: "2026-05-26",
    title: "Match Play: Clear button to reset a match result",
    changes: [
      "Each match row now has a small '✕' Clear button (next to Save) that removes the match result — winner, margin, and Stableford points are all wiped. The match dot reverts to gray (unplayed) and pool standings recalculate immediately. A confirmation prompt prevents accidental clears.",
      "New API: DELETE /api/cmp/matches with pool_id + player names in the JSON body. New DB function: cmp_clear_match() deletes the row using the canonical sorted player name pair.",
    ],
  },
  {
    version: "2.15.6",
    date: "2026-05-26",
    title: "Match Play: fix duplicate in Add Player modal; fix missing handicap in unassigned panel",
    changes: [
      "Add Player modal no longer shows duplicate entries when a player has two customer records (e.g. one FORMER and one MEMBER). Deduplicates by name on load, keeping the record with the better membership status (MEMBER > STAFF > FORMER).",
      "Handicap now shows correctly in the 'Enrolled — Not Yet in a Pool' panel even when the enrollment name differs from the canonical customer name (e.g. 'Stuart Kirksey' enrolled vs 'Stu Kirksey' in the handicap system). Resolved by looking up the canonical name via customer_id when the direct name lookup misses.",
      "Customer data is now fetched in parallel with pools and handicaps on page load instead of lazily on first modal open, so the customer_id resolution map is always ready.",
    ],
  },
  {
    version: "2.15.5",
    date: "2026-05-26",
    title: "Match Play: unassigned panel scoped to active chapter",
    changes: [
      "The 'Enrolled — Not Yet in a Pool' panel now only shows players whose enrollment chapter matches the currently selected chapter tab (Austin or San Antonio). Players whose chapter was not recorded at enrollment time still appear in both chapter views so they can still be assigned.",
    ],
  },
  {
    version: "2.15.4",
    date: "2026-05-26",
    title: "Match Play: unassigned enrollees roster with pool assignment dropdown",
    changes: [
      "Added an 'Enrolled — Not Yet in a Pool' amber panel at the top of each chapter's Match Play view. It lists every player who signed up for City Match Play but hasn't been placed in a pool yet, with their handicap index. Each player row has a pool dropdown (scales to any number of pools) and an Assign button — no modal needed.",
      "The panel disappears automatically once all enrolled players are placed. Shows a 'Create a pool first' hint when no pools exist yet.",
      "Enrollee data now stores customer_id alongside the name so pool assignments carry the FK reference.",
    ],
  },
  {
    version: "2.15.3",
    date: "2026-05-26",
    title: "Auto-sync season contest payments from inbox; ON CONFLICT backfill",
    changes: [
      "Season contest payments are now auto-synced during every inbox check (same loop that auto-syncs events). When a payment for a NET/GROSS Points Race or City Match Play arrives, it is enrolled automatically — no manual Sync button needed.",
      "Manual enrollments created before the payment arrives (e.g. adding a player who hasn't paid yet) now get their source_item_id back-filled automatically when the payment does arrive, thanks to ON CONFLICT DO UPDATE WHERE source_item_id IS NULL logic in the upsert helper.",
      "sync_season_contests_from_items() now returns {enrolled: N, linked: N} so the auto-sync logger can distinguish brand-new enrollments from payment back-fills.",
    ],
  },
  {
    version: "2.15.2",
    date: "2026-05-26",
    title: "Match Play: customer-search modal enforces FK for Add Player",
    changes: [
      "Replaced the free-text 'Add Player' dropdown (which allowed typing any arbitrary name) with a customer-search modal that only shows real customers from the customers table. Typing filters by name; each result shows chapter, status, and handicap index. Selecting a player auto-enrolls them in City Match Play for the season (idempotent) then adds them to the pool — both with the customer_id FK.",
      "New API: POST /api/season-contests manually enrolls a customer by customer_id, looking up their canonical name from the customers table so enrollments always point to a real record.",
    ],
  },
  {
    version: "2.15.1",
    date: "2026-05-26",
    title: "Match Play: chapter tabs auto-load, handicaps, enrollment fix",
    changes: [
      "Replaced the Chapter dropdown + Load button with Austin / San Antonio toggle tabs that auto-load the correct pools as soon as you click them. Season input also triggers an immediate reload on change. Austin auto-loads on page open.",
      "Handicap index (18-hole) now appears next to every player name in pool member lists, match entry rows, and the Add Player dropdown — pulled from the live handicap index map.",
      "Fixed: players who enrolled in City Match Play without a chapter code (e.g. manually added or order chapter field was blank) no longer disappear from the Add Player dropdown. The enrollee fetch now returns all City Match Play enrollees for the season regardless of chapter.",
    ],
  },
  {
    version: "2.15.0",
    date: "2026-05-26",
    title: "Add CONTESTS tab: City Match Play pools, standings & bracket",
    changes: [
      "New CONTESTS nav tab (after Events, before Customers) on every page. The tab hosts three sub-sections: Match Play, Points Race, and Enrollment.",
      "City Match Play (Match Play tab): Admin creates named pools per chapter/season, assigns players to pools of 4, and records two independent results per match: (1) the traditional match play result — winner and margin (e.g. 1 Up, 5&4, Putt Off, Halved) — and (2) each player's Stableford points for the round, which are tracked separately because the match loser can outscore the winner.",
      "Pool standings: W/L/D is determined by the match play winner; Stableford points accumulate independently and serve as the tiebreaker for advancement and as seeding for the knockout bracket. Top 2 from each pool advance and are highlighted.",
      "Knockout bracket: 'Seed from Pool Standings' auto-populates bracket slots using cross-pool seeding ranked by total Stableford points (Pool A #1 vs Pool B #2, Pool B #1 vs Pool A #2). Admin enters Stableford points, selects winner, and enters margin for each bracket match through Semifinals and Final.",
      "Points Race tab: Shows the NET and GROSS Modified Stableford scoring tables for reference. NET race: Triple Bogey=-1, Double Bogey=-1, Bogey=0, Par=+1, Birdie=+2, Eagle=+3, Dbl Eagle=+4, HIO=+8. GROSS race: TB=-1, DB=0, Bogey=+1, Par=+2, Birdie=+4, Eagle=+8, Dbl Eagle=+16, HIO=+8. Full standings and score entry in the next phase.",
      "Enrollment tab: Filterable list of all season contest enrollments (contest type, chapter, season). 'Sync from Purchases' rescans membership items and enrolls new participants.",
      "DB schema: cmp_matches now stores winner_name + margin (match play result) and player1_stableford + player2_stableford (independent points) separately. cmp_bracket stores player_stableford + margin. Idempotent column migrations run at startup for existing deployments.",
    ],
  },
  {
    version: "2.14.16",
    date: "2026-05-19",
    title: "Add Cash App as a refund method option (events.html)",
    changes: [
      "Cash App was missing from the Refund Method and Partial Refund dropdowns on the Events page (events.html). Both selects now include Cash App, matching the Transactions page fix from v2.14.15.",
    ],
  },
  {
    version: "2.14.15",
    date: "2026-05-19",
    title: "Add Cash App as a refund method option",
    changes: [
      "Cash App added to the Refund Method dropdown in the Credit / Transfer / Refund modal, and accepted by all three refund/partial-refund API endpoints.",
    ],
  },
  {
    version: "2.14.14",
    date: "2026-05-19",
    title: "Fix duplicate-round rejection when importing multi-course events on the same day",
    changes: [
      "When a handicap file includes a round_id, the duplicate check previously matched on (player_name, round_date, round_id) alone. For multi-course events at the same facility — e.g. Comanche Trace VALLEY / HILLS / CREEKS all played on the same day — Golf Genius assigns the same round_id to every round in the event. This meant the second and third course files were rejected as duplicates after the first was imported, even though they were distinct 9-hole rounds at different courses.",
      "The round_id dedup check now also includes course_name, so (player_name, round_date, round_id, course_name) must all match before a round is skipped. Two rounds at VALLEY and HILLS on the same day with the same round_id are now treated as distinct and both import correctly.",
    ],
  },
  {
    version: "2.14.13",
    date: "2026-05-18",
    title: "Fix false price_total_mismatch action items on multi-quantity & multi-line orders",
    changes: [
      "The price-mismatch check compared a single row's PER-UNIT item_price against the order's WHOLE-ORDER total_amount. Because total_amount is the full order charge and is copied unchanged onto every line item and every expanded per-player row, the check could only ever balance for single-line, single-quantity orders. It false-fired on every multi-quantity order (Doug Hamilton paying 2 x $205 for guests = $410; Victor Arias 2 x $65 = $130) and every multi-line order (Wade Fieber: $75 membership + $81 event = $156). No price was ever mis-extracted — the validation invariant was simply wrong.",
      "Both code paths now reconcile at the ORDER level: sum(item_price across the order's rows) + transaction_fees - coupon must equal total_amount (within $1). scan_price_games_mismatches() groups items by order_id (fallback email_uid) and emits at most one warning per non-reconciling order; _validate_parsed_items() does the same at parse time. A genuine parser price grab (e.g. an $88 description price on a $148 single-reg order) still fails to reconcile and is still flagged.",
      "New resolve_reconciled_price_warnings() boot step drains the backlog conservatively: it recomputes order-level reconciliation from current items for every OPEN price_total_mismatch warning and resolves only the ones that now balance (the multi-qty / multi-line false positives). Anything that still doesn't reconcile — a real single-line price grab — is left open for human review. Idempotent.",
      "No item prices are rewritten and no rows are created/merged: the orders' data was already correct (N players = N rows at the unit price); only the validation logic and the stale warnings were wrong. The separate guest-naming issue on quantity orders (e.g. Hamilton's two spots are for 'Casey Purvis' / 'Will Drewry') is unaffected and still handled by the existing GUEST_NAME_MISSING path.",
    ],
  },
  {
    version: "2.14.12",
    date: "2026-05-18",
    title: "Auto-clear EMAIL_DRIFT action items when the drifted email is obviously the same person",
    changes: [
      "EMAIL_DRIFT warnings fire when a new order's email differs from the customer's canonical email. The vast majority are a legitimate alternate address (jgoretzke@gmail.com vs jmsg1933@gmail.com) or an obvious typo of the same address (fredwickee vs fredwicker) — both safe — but the warning sat open in the COO action-items banner until a human dismissed it one by one.",
      "New resolve_low_risk_email_drift_warnings() boot step classifies each open EMAIL_DRIFT as low-risk when the drifted email plausibly belongs to the same person: the customer's surname (>=3 chars) appears in the local-part, OR it is within edit-distance 2 of the canonical local-part on the same domain, OR it is the identical handle on a different provider. Low-risk warnings are auto-resolved.",
      "Because the identity-drift guard overwrites the order email with canonical BEFORE the row is inserted, the drifted value never reaches items.customer_email and the existing capture_email_aliases_from_items() never sees it — it lives only in the warning message. So for low-risk warnings this step now also captures the drifted email into customer_aliases (type 'email', keyed to the canonical name so customer resolution can use it), making it visible on the Customer Info page — the same outcome the warning text prescribed for 'capture as alias', just automated.",
      "Genuine cross-person contamination (a different person's email landing on this order — the 'fredwickee class' bug the warning exists to catch) is NOT low-risk, so it stays open in the banner for a human to review before it can pollute customer resolution. The human gate is preserved exactly where the risk actually lives.",
      "Idempotent and conservative: unparseable messages and anything that does not clearly look like the same person are left open, never auto-captured.",
    ],
  },
  {
    version: "2.14.11",
    date: "2026-05-18",
    title: "Stop bogus CHAPTER_DRIFT action items + the silent items.chapter corruption behind them",
    changes: [
      "The identity-drift guard in save_items() compared a new order's chapter against customers.chapter and, on mismatch, raised a CHAPTER_DRIFT parse warning AND overwrote the order's chapter with the member's home chapter. But items.chapter is the event/course location (the AI parser is explicitly told to use the course, not the buyer's address), while customers.chapter is the member's home chapter — so any time an Austin member played a San Antonio event the two legitimately differed. This fired a false-positive action item in the COO banner on every cross-chapter registration, and worse, silently rewrote the correct event-location chapter (e.g. 'San Antonio' for a Hill Country / TPC Canyons order) to the member's home chapter, corrupting the column the dashboard filters/sorts/groups events by.",
      "Fix: chapter is removed from the drift _checks tuple, so save_items() no longer raises CHAPTER_DRIFT and no longer overwrites items.chapter. EMAIL_DRIFT and PHONE_DRIFT are unchanged — a typo'd email or phone on an order is still caught and canonical still wins.",
      "An idempotent boot step resolves any historical open CHAPTER_DRIFT parse warnings so the stale ones (Youngs / Marques / Goretzke and any others) clear out of the COO action-items banner on deploy; it is a no-op on every subsequent boot.",
      "Not addressed here: items.chapter rows that were already overwritten to a member's home chapter by the old behavior are left as-is — restoring them needs each order's true event location and is a separate historical migration (the 'past events are frozen' principle means we don't rewrite stored rows casually).",
    ],
  },
  {
    version: "2.14.10",
    date: "2026-05-18",
    title: "Proactively email the owner when the Anthropic/Claude budget is exhausted",
    changes: [
      "New email_parser/ops_alerts.py: maybe_alert_anthropic_billing(exc) detects the two owner-actionable Claude failures — 'credit balance is too low' (out of API credit) and a revoked/invalid key (AuthenticationError / PermissionDeniedError) — and emails the owner via the existing Microsoft Graph mail path so a billing problem shows up in the inbox instead of as a surprise bank charge or a silent dashboard gap.",
      "Wired into the three recurring automated Claude paths: the expense classifier (expense_parser._call_llm), the order parser batch (parser.parse_emails), and the inbox check (app._check_inbox_background). Generic bad-prompt errors and transient rate limits are intentionally NOT alerted.",
      "Throttled to one email per 6 hours, with the marker persisted in the SQLite DB (on the Railway /data volume) so neither the every-5-minute classifier nor a redeploy crash-loop can turn it into an email storm. The throttle is stamped only after a successful send, so a failed alert retries next cycle instead of going silent.",
      "Recipient resolves ANTHROPIC_ALERT_EMAIL_TO -> COO_EMAIL_TO -> EMAIL_ADDRESS. The alert is best-effort and never raises, so it cannot break the caller's own error handling. The email reassures that queued orders/expenses are not lost (they reprocess once Claude works) and links straight to console.anthropic.com billing.",
    ],
  },
  {
    version: "2.14.9",
    date: "2026-05-18",
    title: "Fix UTC day-boundary bug — dates now roll at midnight US/Central, not ~7 PM",
    changes: [
      "The Railway container runs in UTC, so every 'what day is it' computation done with a naive datetime.now()/utcnow()/date.today() rolled over to the next day at 00:00 UTC — roughly 6–7 PM US/Central. Most visibly: an order or expense email that arrived in the evening and didn't carry its own date was stamped with TOMORROW's date, quietly skewing daily totals and reconciliation; the daily digest / COO email headers showed tomorrow's date; and membership 'expires today' notices fired a day early.",
      "New email_parser/timezone_utils.py with now_central()/today_central()/today_central_str() (pytz America/Chicago, returns naive values to match existing date arithmetic). Applied to ~26 user-facing day-boundary/date-stamp sites across app.py, email_parser/database.py, report.py, coo_email.py and memberships.py: new-record date defaults (order_date, transaction_date, deposit/refund dates), dashboard/COO 'today' and month-prefix windows, get_upcoming_events, recurring-transaction due dates, daily digest + COO email date labels, and membership renewal/'expires today' logic.",
      "Stored history is intentionally untouched — only new-record defaults and live 'today'-relative computations changed, so closed/month-end periods and the 'past events are frozen' principle are preserved. Existing rows keep whatever date they were saved with.",
      "Deliberately NOT changed: report.py get_recent_items() 24h cutoff (it is a rolling window compared against the UTC-stored items.created_at — switching it to Central would introduce a 5-hour skew), audit-only created_at columns (SQLite datetime('now'), read back consistently in UTC), and signed-roster token TTLs in memberships.py (epoch-based, correctly UTC). The ~55 benign datetime.now() uses (logging, elapsed timers, rate limiting) are untouched.",
    ],
  },
  {
    version: "2.14.8",
    date: "2026-05-18",
    title: "Expense classifier: stop re-billing Anthropic for already-seen emails",
    changes: [
      "Root cause of large, variable daily Anthropic API charges ($20–$200+/day): the expense email classifier (check_expense_inbox) only recorded an email as processed if it produced an expense_transaction or action_item. Emails classified as 'unknown' — and order/RSVP emails it deliberately skips — were never recorded, so the scheduler re-sent every one of them to Claude for classification on every cycle (every 5 minutes), for the full lookback window. With a general mailbox of newsletters/replies/etc. that is tens of thousands of wasted classification calls per day. The GoDaddy order parser already solved this via processed_emails; the lesson was never applied to expenses.",
      "Fix: new expense_seen_emails table (email_uid PK) plus get_expense_seen_uids()/mark_expense_email_seen() in email_parser/database.py. check_expense_inbox now marks EVERY email seen the moment it is classified — before the per-type branches that early-continue — and adds that set to the dedup gate. Each email is therefore classified (and billed) at most once, regardless of how often the scheduler runs. The table is intentionally separate from processed_emails so it can never hide a GoDaddy order from the order parser. A rare classify_email() exception is left unmarked so it retries next cycle (matches the GoDaddy parser).",
      "Polling frequency is now fully decoupled from cost, so near-real-time checks are kept (every CHECK_INTERVAL_MINUTES, default 5, 24/7 — unchanged). The expense lookback window dropped from a flat 14 days to a safe 48h steady-state (EXPENSE_LOOKBACK_HOURS), with a one-time wider backfill on a cold start (EXPENSE_BACKFILL_DAYS, default 14) — i.e. a fresh DB or a wiped Railway volume. Admin/manual runs (/api/accounting/check-expense-inbox) can still pass an explicit days_back.",
      "Re-key protection: save_expense_transaction() previously did a content-dedup ONLY when no email_uid was present; with a uid it did a pure ON CONFLICT(email_uid) upsert, so a Graph-re-keyed email (new uid, same economic event — folder rebuild, mass reply, PWA resync) double-inserted. It now probes for an existing row with the same (source_type, merchant, amount, transaction_date) under a different uid and adopts that row instead of inserting a duplicate. NULL amount/date conservatively falls through to the normal path so genuinely distinct transactions still insert.",
      "Operational safety: start_scheduler() now logs a loud warning at boot if DATABASE_PATH is unset, because the dedup memory lives in SQLite — without a Railway persistent volume every redeploy wipes it and re-bills the entire backfill window. Recommend also setting a hard spend cap in console.anthropic.com as a backstop.",
    ],
  },
  {
    version: "2.14.7",
    date: "2026-05-13",
    title: "Gzip-compress all text responses (flask-compress)",
    changes: [
      "Network-tab timing on /api/handicaps/rounds for a high-volume player (Kerry Niester, ~262 rounds) showed 214 ms server time and 4.82 s content download — the response itself was the bottleneck, not the server. flask-compress is added to requirements.txt and initialized once in app.py right after Flask() so every HTML/CSS/JS/JSON response above the default min length is gzipped. The handicap rounds payload drops from ~80 KB to ~10–15 KB on the wire; the Transactions and Customers dashboards also benefit since they ship large JSON dumps. Browsers that don't advertise gzip support continue to receive uncompressed responses unchanged.",
    ],
  },
  {
    version: "2.14.6",
    date: "2026-05-13",
    title: "Handicaps page: server-side running INDEX so player expand is fast",
    changes: [
      "Clicking on a player to view their score history used to feel sluggish because the browser was recomputing the running INDEX column from scratch — for every historical round, re-running the full WHS lookup/sort/average — on every expand. For a player with 70 rounds that's thousands of operations in the main thread before the table renders. Computation moved to the server: get_handicap_rounds now attaches a running_index_9 field to each row when called with a player_name, mirroring the same WHS algorithm and today's lookback cutoff so values are byte-for-byte identical. The browser just reads the field and renders.",
      "templates/handicaps.html: removed the O(N²) running-handicap loop and the same-date canonical override in renderRoundsTable. The DIFF_LOOKUP / ADJ_LOOKUP constants are still needed for the per-card breakdown HTML below so they remain in the file.",
      "email_parser/database.py: added _attach_running_index_9 helper next to compute_handicap_index, wired into get_handicap_rounds(player_name=…). build_handicap_card_data passes include_running_index=False since it ignores the field. New composite index idx_handicap_rounds_player_date on (player_name, round_date DESC, id DESC) so the per-player history query reads pre-sorted.",
      "No behavior change to the index value itself — the running INDEX column on each historical row shows exactly the same number as before, just rendered ~10–100× faster on larger histories. Today's fixed lookback cutoff is still used (per docs/claude/handicaps.md), so older rounds still reflect what the handicap would have been with today's 12-month window applied.",
    ],
  },
  {
    version: "2.14.5",
    date: "2026-05-13",
    title: "Handicap card: show sum-then-divide so the math reconciles with the DIFF column",
    changes: [
      "The calculation line on the handicap card preview now reads 'Sum of lowest N: {sum} ÷ N = {avg} × 0.96 = {after_mult} → {index}'. Earlier wording showed only the average ('Avg of lowest 7: -0.07 × 0.96 = ...'), which was correct but disagreed with the visible DIFF column at a glance — a manager adding the seven starred diffs got -0.5 and couldn't see how that became -0.07 without doing the division mentally. The sum is now printed at 1 decimal (matching the DIFFs), divided by N, then multiplied by 0.96, then floored to the nearest tenth per WHS Rule 5.2.",
      "Build/file: email_parser/database.py → build_handicap_card_html, calc_html. No behavior change to the index value itself.",
    ],
  },
  {
    version: "2.14.4",
    date: "2026-05-13",
    title: "Handicap diffs stored at tenths — card math reconciles with displayed DIFFs",
    changes: [
      "Per-round differentials in handicap_rounds were stored at 2-decimal precision while the handicap card displayed each DIFF rounded to 1 decimal. Result: the printed 'Avg of lowest N' line averaged the hidden hundredths and didn't match the eye-test sum of the visible tenths (e.g. seven visible diffs summing to -0.5 but the card showing avg = -0.07 from underlying -0.67/0.47/etc.). Per WHS Rule 5.2 ('round to the nearest tenth'), every DIFF in the system is now stored at 1-decimal precision.",
      "email_parser/database.py: import_handicap_rounds() rounds incoming and computed differentials to 1 decimal (was 2). The display in build_handicap_card_html keeps the 2-decimal format for the averaged value (it's an average of tenths — typically a hundredth) but the underlying numbers being averaged are now the same tenths a manager sees in the DIFF column.",
      "One-time idempotent boot migration _migrate_round_handicap_diffs_to_tenths runs in init_db: UPDATE handicap_rounds SET differential = ROUND(differential, 1) WHERE differential != ROUND(differential, 1). Existing rows with hidden hundredths are normalised on first boot; subsequent boots find nothing to update.",
    ],
  },
  {
    version: "2.14.3",
    date: "2026-05-13",
    title: "Database admin: schema view for empty tables + sidebar sticky-scroll",
    changes: [
      "/database admin page now shows a collapsible Schema panel above the rows table — column name, type, NOT NULL / PRIMARY KEY constraints, default values. Auto-opens when the table is empty so an admin can still verify a table's structure (matters for newly added tables like the chunk-1 payout_templates trio which start with zero rows). Reads from a new schema field in /api/database/table/<name>, derived from PRAGMA table_info.",
      "Database browser sidebar is now sticky and scrolls independently of the main content. On long-scrolling tables, the table list stays pinned in view; if the list itself overflows the viewport, it scrolls inside the sidebar rather than carrying the page along with it.",
    ],
  },
  {
    version: "2.14.2",
    date: "2026-05-13",
    title: "Payout Templates schema (chunk 1 of 8) — DB tables only, no UI yet",
    changes: [
      "init_db now creates three new tables behind the upcoming Payout Templates system: payout_templates (named templates with one default per holes value, enforced by partial unique index), payout_template_versions (append-only history; every save makes a new row with rates_json, rules_json, computed_matrix_json, max_players), and event_type_template_map (event_type + holes → default template lookup). All three are idempotent CREATE TABLE IF NOT EXISTS — safe to run on every boot.",
      "events table gains payout_template_version_id (INTEGER FK → payout_template_versions(id), nullable). Stamped at event creation from the event_type_template_map; never auto-updated after that. Per-event override on the event detail page rewrites it explicitly. Editing a template later creates a new version row but does not touch already-stamped events — past events keep the rules they ran under.",
      "Schema only — no UI, no API, no behavior change in this chunk. The existing /matrix admin page, the games-matrix.js static file, and the app_settings.games_matrix_9/18 JSON keys all keep functioning unchanged. Subsequent chunks (seed templates from live values, read API, GAMES tab cutover, event-type mapping, admin editor, history/rollback) land incrementally on the same branch.",
      "Implementation note: the new CREATE TABLE block sits below init_db's last explicit conn.commit() (line 4134), and _connect() does not autocommit — so the block ends with its own conn.commit() to ensure tables persist. docs/claude/schema.md updated with the new tables, the new events column, and the commit caveat for any future additions at the bottom of init_db.",
      "Source-of-truth correction: the matrix values to seed from live in app_settings.games_matrix_9/games_matrix_18 (DB override, set when admin edits via /matrix) and fall back to static/js/games-matrix.js. The 25-SideGame-PrizeMatrix.xlsx is stale and is no longer used as a seed source.",
    ],
  },
  {
    version: "2.14.1",
    date: "2026-05-13",
    title: "Guiding Principles + Payout Templates design captured in docs",
    changes: [
      "CLAUDE.md and PROJECT.md gain a new top-level Guiding Principles section: (1) automate toward 0% manual input, (2) rules-based not magic, (3) portable to TGF Platform, (4) past events are frozen (snapshot rules-in-effect), (5) admin-edits / manager-runs / customer-views access layers. These apply to every feature in this product and to the future Platform.",
      "PROJECT.md Backlog / Roadmap gains a High Priority entry for Payout Templates — the DB-backed replacement for the static 25-SideGame-PrizeMatrix.xlsx + games-matrix.js. New tables: payout_templates, payout_template_versions, event_type_template_map. New column: events.payout_template_version_id (snapshot per event so completed events never change retroactively). Admin UI has Rates (per-player $/game) and Rules (flight/place/min-player thresholds, overflow rules) panels with a live-preview matrix. Manager-side GAMES tab stays identical — same auto-compute, no manual input added. xlsx kept as historical reference for the Tracker, not migrated to Platform.",
      "PROJECT.md Future Considerations gains a Side Games section capturing the longer-horizon items raised during design review: customer-facing matrix view (Platform), full games builder/editor with add/remove/reorder, 9/18 combo per-side game enablement (data shape ready, UI later), Owner-configurable Permissions UI for role assignment, generic overflow rule shape (Gross→Skins when Individual Gross can't run), max_players-per-template (64 default 9-hole, 128+ for 18-hole), and the direct port path to TGF Platform backend.",
      "No code or behavior changes in this version — documentation only. Implementation begins after final go-ahead.",
    ],
  },
  {
    version: "2.14.0",
    date: "2026-05-11",
    title: "Duplicate Detective: ledger cleanup admin tool",
    changes: [
      "New admin tool at /admin/duplicate-detective that detects and merges duplicate acct_transactions rows accumulated from multiple writers recording the same financial event (Venmo CSV import, Venmo email parser via exp-promoted-N, in-app refund/credit-payout operations). The Frost Checking variance bloat — caused by Venmo + email parser + in-app ops all double-booking the same refund — is what this is designed to clean up.",
      "Four detection patterns: A) Venmo CSV ↔ exp-promoted, B) in-app refund/credit-payout/wd-credit-payout ↔ exp-promoted, C) in-app ↔ Venmo CSV, D) manual fallback (same customer_id, different source_ref, within 7 days). Confidence scored 0.95 (customer_id match) / 0.85 (name-only match) / 0.65 (Pattern D), with penalties for date gap, amount delta, and FK warnings. Survivor selection prefers Venmo CSV (bank truth) > GoDaddy order detail > in-app op > exp-promoted (least specific).",
      "First-run mode defaults to dry_run_only — UI renders but action buttons are disabled, every card shows the exact UPDATE SQL inline, and CSV + Markdown report exports work for offline review. Switch to review_each for per-card merge/swap/dismiss buttons, or auto_high_confidence for a batch button that merges every pair ≥0.90 confidence with no FK warnings. Mode flag persisted in app_settings.",
      "Soft-delete pattern: merged rows are marked status='merged' with merged_into_id pointing at the survivor. Never hard-deletes. Every merge logs one row to duplicate_merge_audit with confidence, reason, operator, and notes. Reverse a bad merge from /admin/duplicate-detective/audit — flips status back to active. FK re-points (allocations / reconciliation matches / expense_transactions) are NOT auto-restored on reverse; the audit notes flag manual cleanup required.",
      "Read paths that aggregate ledger totals now exclude merged rows: get_acct_account_balances, get_reconciliation_dashboard book_balance, and mcp_server._get_ledger_entries (defaults to filtering when no status arg supplied). Other aggregates (get_acct_transactions, get_monthly_reconciliation, get_cashflow_data, get_event_financial_summary) were already filtering.",
      "HARD ERROR safety net: if survivor and merged row are both matched to DIFFERENT bank_deposits, auto-merge refuses; per-card merge requires explicit allow_fk_hard_error=True override (UI surfaces a stronger confirmation dialog). Override is logged in the audit row's notes for traceability.",
      "Schema additions (idempotent migrations in init_db): acct_transactions.merged_into_id (nullable FK), duplicate_merge_audit table, duplicate_dismissed_pairs table (UNIQUE on pair so dismissed pairs do not resurface).",
      "35 unit tests in test_duplicate_detective.py cover all four patterns, customer-id vs name-only match scoring, idempotency, FK re-pointing including the UNIQUE constraint conflict case, HARD ERROR refusal + override, reverse round-trip, audit ordering, and the book-balance exclusion behaviour.",
      "Full reference doc at docs/claude/duplicate-detective.md; cross-refs added to CLAUDE.md, docs/claude/schema.md, and docs/claude/bank-reconciliation.md.",
    ],
  },
  {
    version: "2.13.0",
    date: "2026-05-08",
    title: "Roles decoupled from status; Venmo matcher fixes; NOT PLAYING dedup",
    changes: [
      "Customer status is now decoupled from roles. New `customer_statuses` history table is the canonical source — `golfer` role no longer forces a MEMBER badge. Joe Brandon (golfer + 1ST TIMER) now reads 1ST TIMER on the badge as expected. Status changes write a new history row via the new `POST /api/customers/<id>/status` endpoint; latest row determines current status. Reference tables `roles` and `statuses` seeded at boot. `customers.current_player_status` kept in sync as a denormalized snapshot for legacy reads.",
      "FORMER status automation: `email_parser/memberships.py` daily scheduler now writes a FORMER row to `customer_statuses` when a term lapses, and a MEMBER row when a renewal is recorded. Most recent row wins, so a renewal cleanly restores membership.",
      "Mismatch flags in events tab: registered as MEMBER + canonical status FORMER → `Former Member renewal needed`. Registered as MEMBER + canonical not-a-member → `Customer profile is not a member`. MEMBER + 1st Timer pricing on first event = no flag (legitimate). Flag only fires on second 1st Timer attempt.",
      "Venmo balance-due matcher: now also accepts `transaction_type='income'` (not just `'received'`) — the LLM expense parser splits inbound payments inconsistently between those two labels, which was silently excluding ~half the inbound stream from auto-matching. Pat Youngs's $53.85 from 'James Youngs Jr' is the case that surfaced this.",
      "Venmo matcher: third fallback added — when name + alias lookups miss, the matcher now compares `expense_transactions.other_party_handle` (Venmo @handle) against `customers.venmo_username`. Lets a payment from a Venmo display name that differs from the registered name match by handle alone. Backed up with a canonical-name fallback when the balance_due item has a NULL `customer_id`.",
      "New diagnostic endpoint `GET /api/admin/venmo-debug?payer=<name>` returns expense_transactions, customer_aliases, customers.venmo_username matches, and balance_due items for a given payer fragment — used to pinpoint why a specific Venmo payment isn't matching.",
      "NOT PLAYING section in event detail now (a) suppresses any GG RSVP whose player has since registered with an active transaction (Daniel Stich-style: he RSVPd not-playing, then registered and paid; his GG badge no longer appears in NOT PLAYING), and (b) deduplicates by email/name so a doubled GG RSVP import doesn't surface twice (HOFFMAN, Rocky × 2 etc).",
      "events.html `statusMismatchReason()`: hoisted `statusName` to function top to fix a `ReferenceError: info is not defined` that was crashing `renderDetailContent` and emptying the entire player table when a row had no canonical profile (e.g. unmatched GG RSVPs like 'Matt'). Now degrades gracefully.",
      "ALTER TABLE migrations added at boot for `customers.suffix` and `customers.middle_name` — fixed a 500 on `/api/customers` after the columns were added to the schema but the live Railway DB was missing them.",
      "CLAUDE.md: added 'Workflow rules (always)' section documenting durable per-session expectations (bump `version.js` and update affected `docs/claude/*.md` after every push).",
    ],
  },
  {
    version: "2.12.1",
    date: "2026-05-04",
    title: "Membership: state-aware T-30/T-7 + status badge fix for lapsed golfers",
    changes: [
      "T-30 and T-7 templates' subject + body opening + renewal-impact phrase adapt to the term's actual state — sending T-30 to a member 28 days lapsed now reads 'Your TGF membership lapsed 28 days ago' / 'Just a heads-up that your membership lapsed 28 days ago' / 'puts your weekly event invitations and member pricing back in place', instead of the canonical 'expires in 30 days / without a gap' wording. Canonical days_left=30 / days_left=7 cases still render the spec wording verbatim.",
      "Edge cases: 'expires tomorrow' / 'expires today' / 'lapsed yesterday' branches handled. T-0 and lapsed templates stay canonical (warmth lines are state-specific — admins should pick T-30/T-7 for off-cycle informational sends).",
      "Status badge fix: deriveStatus() previously short-circuited to MEMBER on any 'elevated' role including 'golfer', which meant lapsed members who carry the golfer role (i.e. most members) still read MEMBER on the customers list even when the Info-tab Member Status correctly read FORMER. Split the role check: PERMANENT roles (owner / admin / manager — TGF leadership) always read MEMBER and override lapsed state; the 'golfer' role only reads MEMBER when the latest term is NOT lapsed. Demonte now reads FORMER on the badge as expected.",
    ],
  },
  {
    version: "2.12.0",
    date: "2026-05-04",
    title: "Membership emails: locked v1.0 copy standards (May 2026)",
    changes: [
      "All four pre-lapse + lapsed templates rewritten to the v1.0 email standards spec. Each opens with a unique warmth line: T-30 'built on people like you', T-7 'wouldn't be what it is without members like you', T-0 'love to keep you in the crew', T+14 lapsed 'better because you were part of it'. Tone is appreciative, not transactional.",
      "Subject lines are now locked to the spec (T-30: 'Your TGF membership expires in 30 days' / T-7: '... 7 days' / T-0: '... today' / lapsed: 'One last note from TGF'). The Send Notice Now modal still allows inline subject editing for non-canonical cases.",
      "Body language reverts to spec-canonical wording (drops the prior 14-day-state-aware variants). Editable subject in the modal is the escape hatch for off-cycle sends.",
      "Golf Genius opt-in/out section locked: 'Still want the weekly invites? We send event invitations through Golf Genius every week...' Closing for opted-in emails is the 'Either way, no hard feelings' line. Closing for opt-out-free emails is 'Thanks for being part of The Golf Fellowship.'",
      "Lapsed final notice now respects the with_roster_buttons toggle (was always-on). Daily scheduler still defaults lapsed to with-buttons; admin Send Notice Now defaults lapsed checked but allows uncheck for the spec's without-buttons variant.",
      "Confirmation (renewal thank-you) email unchanged — not in the v1.0 spec.",
    ],
  },
  {
    version: "2.11.6",
    date: "2026-05-04",
    title: "Roster opt-in/out copy: warmer, less transactional tone",
    changes: [
      "About Golf Genius header reframed from \"unless we hear from you, we'll be removing you\" to \"we don't want to crowd your inbox with our weekly event invitations if they're no longer useful — totally fine either way.\" The opt-out feels like a courtesy, not a threat.",
      "Remove button relabeled from \"❌ Remove me from the rosters\" to \"No need to keep me posted\" and recolored from red (#dc2626) to neutral grey (#6b7280) so the choice doesn't read as a destructive action.",
      "Closing paragraph softened: \"Either button just sends a quick note ... so we know what to do. If we don't hear from you in the next 7 days, we'll quietly take you off the rosters so we're not buggin' you — and you're always welcome back any time.\" Replaces the older \"go ahead and remove you ... no hard feelings\" phrasing.",
      "Plain-text fallback link labels updated to match the new button copy.",
    ],
  },
  {
    version: "2.11.5",
    date: "2026-05-04",
    title: "Membership: lapsed → FORMER (auto), opt-in/out toggle on Send Notice Now",
    changes: [
      "Member Status now flips to FORMER automatically when a customer's latest membership term is lapsed. Frontend deriveStatus() consults c.membershipTerm and returns FORMER over the 'they bought a membership = MEMBER' rule. Backend has a new sync_player_status_with_terms helper that runs at boot and inside the daily scheduler — flips active_member/member_plus → expired_member when latest term has expires_at < today, and back to active_member when a renewal lands. Idempotent.",
      "The Member Status field on the Info tab also overrides to FORMER for lapsed terms, with a small italic '(membership term lapsed YYYY-MM-DD)' note when the stored player_status hasn't caught up yet (e.g. between deploys).",
      "Send Notice Now modal now has an 'Include opt-in/out buttons' checkbox — appends the Golf Genius keep-on-rosters / remove-from-rosters block (with HMAC-signed one-click links + admin notification) to T-30 / T-7 / T-0 emails. Useful for lapsed members who might prefer to gracefully step away rather than renew. The lapsed final notice always includes the buttons by design (toggle disabled). Confirmation email never includes them (toggle disabled).",
      "Roster buttons block extracted into _roster_buttons_block() helper so all five email windows can share one definition.",
    ],
  },
  {
    version: "2.11.4",
    date: "2026-05-04",
    title: "Membership notices: body language now state-aware (active / today / lapsed)",
    changes: [
      "Body copy in T-30 / T-7 / T-0 templates now adapts to the term's actual state, not just the window label. Previously: firing T-30 on a member whose term lapsed 69 days ago produced 'A heads-up that your membership ... expires on Feb 24, 2026' — future-tense framing on a past date. Now produces 'A heads-up that your membership ... lapsed on Feb 24, 2026 (69 days ago) and we haven't seen a renewal yet.'",
      "Three states branch: active (future-tense, 'expires on X (in N days)'), today ('expires today'), lapsed (past-tense, 'lapsed on X (N days ago) and we haven't seen a renewal yet'). The window label still controls tone — heads-up vs. quick reminder vs. day-of phrasing — but no longer forces incorrect facts about state.",
      "T-30 closing paragraph also adapts: 'no action needed' (active) vs. 'last chance' (today) vs. 'a few clicks gets you back to active' (lapsed). T-7 and T-0 closing paragraphs are short enough to share across states.",
      "Lapsed final-notice template (with Golf Genius opt-in/out buttons) is unchanged — it was already lapsed-only.",
    ],
  },
  {
    version: "2.11.3",
    date: "2026-05-04",
    title: "Membership notices: BCC admin on member-facing emails",
    changes: [
      "Member-facing membership emails (T-30/T-7/T-0/lapsed/confirmation, including manual Send Notice Now sends) are now BCC'd to admin@thegolffellowship.com automatically. Member's email client doesn't display the BCC line, so the recipient sees a clean email; the owner gets a paper trail of every notice that goes out.",
      "Configurable via MEMBERSHIP_MEMBER_BCC env var (defaults to admin@thegolffellowship.com, comma-separated for multiple, set to \"\" to disable). De-duplicates against the TO line so a member email can't accidentally end up BCC'ing itself.",
      "Admin-facing emails (roster opt-in/out, no-response digest) keep the existing CC behavior via MEMBERSHIP_ADMIN_CC. The two paths are now mutually exclusive — admin-facing uses CC, member-facing uses BCC.",
      "send_mail_graph extended with optional bcc_address kwarg → real bccRecipients in the Graph payload (Microsoft Graph respects BCC privacy: it's not echoed back in headers).",
    ],
  },
  {
    version: "2.11.2",
    date: "2026-05-04",
    title: "Membership notices: dynamic subject + editable subject + configurable URL",
    changes: [
      "Subject lines are now computed from the actual days remaining between today and expires_at, not hardcoded to the window label. Sending the T-30 notice on a term that expires in 14 days now reads 'Your TGF membership expires in 14 days' (was: 'in 30 days'). Falls through to 'expires today' / 'expires tomorrow' / 'lapsed N days ago' for edge cases.",
      "The Send Notice Now modal now exposes the subject as an editable text input (with a Reset button to revert to the auto-generated subject). Edits are passed through as `subject` in the POST body and round-trip into Microsoft Graph as the actual subject.",
      "Renewal link is now configurable via the MEMBERSHIP_RENEWAL_URL env var (read at render time, no code deploy needed if the storefront URL ever moves). Falls back to https://thegolffellowship.com/shop/ols/products/tgf-membership.",
    ],
  },
  {
    version: "2.11.1",
    date: "2026-05-04",
    title: "Membership: Renewal column on customers list + Send Notice Now + admin CC",
    changes: [
      "New Renewal column on the top-level Customers list shows each customer's current-term expires_at as a colored badge (green=active, amber=≤30d left, red=lapsed). Sortable by date. Backed by GET /api/memberships/current which returns the latest term per customer in one fetch.",
      "New 'Send notice' button on every membership term row (admin only). Opens a preview modal with a notice-window dropdown (T-30, T-7, T-0, T+14 lapsed, Confirmation), live preview iframe of the actual rendered email, recipient line, and Send button. Stamps the matching *_sent_at column on success so the daily scheduler doesn't re-fire.",
      "Admin notifications (roster opt-in/out, no-response digest) now CC admin@thegolffellowship.com by default. Override via MEMBERSHIP_ADMIN_CC env var (set to '' to disable, or comma-separated for multiple). Auto-dedup so a recipient already on the TO line isn't added again.",
      "send_mail_graph extended with optional cc_address kwarg → real ccRecipients in the Graph payload (not a second TO).",
      "New endpoints: GET /api/memberships/<id>/preview-notice?window=… and POST /api/memberships/<id>/send-notice (admin only).",
    ],
  },
  {
    version: "2.11.0",
    date: "2026-05-04",
    title: "Membership renewal reminders + Golf Genius roster opt-in/out",
    changes: [
      "New customer_memberships table tracks one row per term (year). Backfilled at boot from every parsed items row with item_name LIKE '%membership%'. Term length: 365 days from purchase for terms started 2025+; calendar-year for older.",
      "Daily 09:00 US/Central scheduler job sends four notice emails per term: T-30, T-7, day-of, and T+14 lapsed. All include the $75 / 12-month renewal CTA pointed at https://thegolffellowship.com/shop/ols/products/tgf-membership.",
      "When a renewal lands in the parser, the prior term's reminders auto-shut-off (idempotent gate via 'later term exists' check) and a 'Thanks for renewing' confirmation fires from the same daily job.",
      "The lapsed final notice includes two HMAC-signed one-click buttons (Keep on rosters / Remove from rosters) — clicking notifies admin@thegolffellowship.com and stamps the customer's roster_choice. Plain-text fallback links rendered for stricter email clients.",
      "If neither button is clicked within 7 days, the daily job emails admin@thegolffellowship.com a single digest of non-responders so they can be removed from Golf Genius. One-shot per term via roster_admin_notified_at.",
      "New Membership Terms card on every customer's Info tab shows term history with status badges, source, notice/confirmation timestamps, and roster choice. Admins can + Add term (back-date legacy renewals), Edit, or ✕ Delete.",
      "API: GET/POST /api/customers/<id>/memberships, PATCH/DELETE /api/memberships/<id>, POST /api/admin/run-membership-reminders, GET /m/roster/<token>.",
    ],
  },
  {
    version: "2.10.21",
    date: "2026-05-04",
    title: "Parser: route MEMBERSHIP orders to Sonnet, keep Haiku for everything else",
    changes: [
      "The v2.10.19 prompt update with an explicit MEMBERSHIP+EVENT worked example was not sufficient — Haiku still returned single mashed-up rows on Wafford R301078428 even after Re-extract. Five suspect rows surfaced via /api/audit/membership-mashup-scan: two recent Wafford/Fehlis mashups plus older Fehlis/Colby/Buratowski rows.",
      "New routing in email_parser/parser.py:_call_ai(): if the email body matches /TGF\\s+MEMBERSHIP|SKU:\\s*MEM-[A-Z]-[A-Z]/i, the call goes to claude-sonnet-4-5 (override via env var CLAUDE_MODEL_PREMIUM); everything else stays on the existing Haiku default. CLAUDE_MODEL env still wins as a global override. Each parse logs the model and whether membership routing fired.",
      "Cost impact: minimal — membership purchases are rare relative to event registrations, and only those orders pay Sonnet rates.",
    ],
  },
  {
    version: "2.10.20",
    date: "2026-05-04",
    title: "Admin scanner for membership-mashup victims",
    changes: [
      "New read-only GET /api/audit/membership-mashup-scan admin endpoint. Returns every active TGF MEMBERSHIP row in the items table that has non-null event-side fields (holes / side_games != NONE / tee_choice). Those rows are likely victims of the same parser mash-up bug that hit Jeremy Wafford R301078428 (membership name with event's price/games/holes). For each suspect: id, order_id, email_uid, customer, item_price, holes, side_games, tee_choice, order_date, transaction_status, created_at — enough to decide whether to delete + re-import.",
      "Workflow: hit the endpoint, review the list, then for each row delete the bad row and click 'Re-import This Order' on the corresponding Audit Log card to let the v2.10.19 tightened prompt re-extract both items correctly.",
    ],
  },
  {
    version: "2.10.19",
    date: "2026-05-04",
    title: "Parser prompt: handle MEMBERSHIP + EVENT combo orders correctly",
    changes: [
      "Tightened the AI extraction prompt with an explicit MEMBERSHIP + EVENT rule. When an order contains both a TGF MEMBERSHIP and an event in the same email (e.g. Jeremy Wafford R301078428: TGF MEMBERSHIP + s9.8 SILVERHORN), the parser was returning a single mashed-up row — TGF MEMBERSHIP item_name with the event's $96 price, holes=9, side_games=BOTH, tee_choice=<50 — and dropping the second item entirely.",
      "The new prompt rule includes a concrete worked example that anchors each item to its own SKU and price line, and explicitly forbids assigning event-side fields (holes / side_games / tee_choice / user_status) to a membership row, or membership-side fields (has_handicap / returning_or_new / date_of_birth / MEM SKU) to an event row.",
    ],
  },
  {
    version: "2.10.18",
    date: "2026-05-04",
    title: "Audit page: Re-import This Order; remove now-redundant Delete Phantom Duplicates button",
    changes: [
      "New 'Re-import This Order' button on the Audit Log card (admin-only, shown when status != ok and email_uid is non-manual). Calls a new POST /api/audit/reimport-order endpoint that re-fetches the email by uid via Microsoft Graph, runs the AI parser, and INSERTs the resulting rows via save_items(). Use case: an order's items were deleted (e.g. to clean up a parser mis-extraction) — the existing 'Re-extract This Order' button can't help because it only UPDATEs existing rows. The cross-uid dedup gate in save_items() prevents any duplicates if rows already exist.",
      "Removed the 'Delete Phantom Duplicates' button from the Transactions header now that the cleanup is complete and the v2.10.17 dedup gate prevents recurrence. The backend endpoint POST /api/audit/delete-phantom-duplicates remains as a quiet safety net but is no longer surfaced in the UI.",
    ],
  },
  {
    version: "2.10.17",
    date: "2026-05-04",
    title: "Fix phantom-duplicate items: order_id+item_index dedup gate + admin delete backfill",
    changes: [
      "Root cause of the 5/3 incident: Microsoft Graph re-keyed ~65 already-parsed 'New Order' emails under brand-new message ids in a single 3-minute burst (likely a folder rebuild, mass reply/forward, or PWA resync). The existing dedup gate keyed only on email_uid + item_index, so the same logical orders sailed through under their new uids and got inserted as identical sibling rows under the buyer's name — making the Transactions tab show '2 items — $192' for what was actually a single $96 purchase.",
      "Prevention (save_items in email_parser/database.py): added a cross-email-uid dedup check. Before each INSERT, if a row with the same (order_id, item_index) already exists under a different email_uid for a real (non-manual) order, the new row is skipped and logged. The original UNIQUE(email_uid, item_index) constraint is preserved.",
      "Cleanup (POST /api/audit/delete-phantom-duplicates, admin-only): finds groups of items sharing (order_id, customer, item_name, item_price) with COUNT > 1, keeps the lowest-id row (the original), and DELETEs each later duplicate. Skips any row that has downstream references (acct_allocations.item_id, acct_transactions.item_id, items.transferred_from_id / transferred_to_id / parent_item_id) so accounting state is never corrupted. Idempotent. Supports ?dry_run=1 for preview and ?since=YYYY-MM-DD to scope the window (default 2026-04-26).",
      "New 'Delete Phantom Duplicates' admin-only button on the Transactions page next to 'Expand Qty Purchases'.",
    ],
  },
  {
    version: "2.10.16",
    date: "2026-05-03",
    title: "27 Holes event format with custom pricing rules",
    changes: [
      "New 27 Holes event format added to the Edit/Add Event modal alongside 9 Holes, 18 Holes, and 9/18 Combo. Treated as a single-day event using the 18-hole tee-time / shotgun rules (single start time, 5-hour planning duration).",
      "27 Holes pricing has its own rules: Guest = Member + $25 (vs +$10 for 9/Combo and +$15 for standalone 18 Hole), and there is no 1st Timer tier (the pricing grid hides the 1st Timer column).",
      "New per-event 'Per Game Add ($)' field appears in the Pricing tab when 27 Holes is selected. Defaults to $27 and persists to the new events.per_game_addon column. The server-side breakdown calculator honors this override for NET/GROSS/BOTH game add-ons on 27-Hole events.",
    ],
  },
  {
    version: "2.10.15",
    date: "2026-04-27",
    title: "Migrate non-canonical side_games text into notes (one-time, idempotent)",
    changes: [
      "New startup migration _migrate_move_noncanonical_side_games_to_notes() finds items where side_games has free-form text (anything other than NET / GROSS / BOTH / NONE / empty) and moves that text into the notes column, then sets side_games = NULL. If notes already had content, the moved text is appended with ' — ' as a separator; if notes already contains the same string, no change. Naturally idempotent — once side_games is NULL, the row no longer matches the SELECT.",
      "Concrete cleanup: Bartz's two '+PAY Difference between ...' rows and any similar manual entries get the descriptive text moved out of Side Games and into Notes at the data layer (matching what v2.10.14 was already doing in display).",
    ],
  },
  {
    version: "2.10.14",
    date: "2026-04-27",
    title: "Customer Transactions tab: Notes column, Side Games kept canonical",
    changes: [
      "Added a Notes column to the Customer detail Transactions tab. Pulls from item.notes (with internal markers like [venmo-bd-exp:N] and [xfer-consumed:N] stripped for display).",
      "Side Games column is now restricted to the canonical values NET / GROSS / BOTH / NONE. Free-form text that had been stuffed into side_games (e.g. 'Difference between ShadowGlen & Teravista' on Bartz's manual +PAY rows) now surfaces in the Notes column instead, where it belongs. Storage is unchanged — this is display-only.",
      "Long notes truncate to 14rem with overflow ellipsis + title tooltip for the full text on hover.",
    ],
  },
  {
    version: "2.10.13",
    date: "2026-04-27",
    title: "Customer Transactions tab: account, total/fees, coupon badge, T circle",
    changes: [
      "Customer detail Transactions tab now mirrors the badges and richness already on the Transactions and Events pages: coupon C-badge, simplified circular T (registered via credit transfer) replacing the long 'From Transfer' pill, and stripPriceSuffix() applied so '(credit transfer)' no longer trails the price.",
      "Two new columns: Account (derived from merchant — Venmo / GoDaddy / Manual / Credit Transfer / RSVP / Roster) and Total / Fees (shows total_amount and transaction_fees when present). Helps eyeball where money came from per row.",
      "Multi-item order hint: when an order_id appears on more than one row, the Item cell shows a small italic '<N>-item order R<id>' subtitle so it's clear when a registration was part of a bigger transaction. Single-item orders show order_id in lighter grey.",
      "Reverse hidden on credit-excess- and overpayment-credit- rows here too (mirrors the Events page fix in v2.10.12) so accidental clicks can't ghost-flip them.",
    ],
  },
  {
    version: "2.10.12",
    date: "2026-04-27",
    title: "Credit-pool rows: hide Reverse + descriptive item_name",
    changes: [
      "Reverse button is hidden on credit-pool rows (excess credit from a transfer, overpayment credit from a Venmo overpayment) on both desktop and mobile, in the Players action dropdown and the Inactive section. Reverse on these rows used to silently flip transaction_status from 'credited' → 'active' and clear credit_note, leaving a phantom player on the event (the Todd McConahy ghost). To unwind a credit pool row now, reverse the parent credit-transfer instead, which deletes the excess via reverse_credit_application's existing cleanup.",
      "apply_credit_to_rsvp() and _post_overpayment_credit() now write item_name as 'Excess credit — <event>' / 'Overpayment credit — <event>' so the row visibly differentiates from a registration. New _migrate_relabel_credit_pool_items() backfills existing rows on startup; idempotent.",
      "New JS helper isCreditPoolRow(row) (events.html) detects credit-pool rows by email_uid prefix (credit-excess- / overpayment-credit-).",
    ],
  },
  {
    version: "2.10.11",
    date: "2026-04-27",
    title: "Events page: actions dropdown, child-row truncation, hole-aware HCP",
    changes: [
      "Per-row registration actions on the desktop Events table are now collapsed into a single '⚙ ▾' dropdown using the existing .ev-actions-toggle / .ev-actions-menu pattern. Apply Credit, Send Venmo Email / Remind, Undo, Credit, WD, Reverse, and Delete each become an .ev-menu-item, with Delete styled as .ev-menu-item-danger. New .menu-row variant is right-aligned and narrower (140px min-width). Mobile registration actions are unchanged.",
      "Child +PAY rows: the GAMES column for child rows (e.g. 'Difference between ShadowGlen & Teravista' on Bartz's row) now wraps in a max-width 8rem div with overflow ellipsis + title attribute, so long child-row text no longer stretches the parent column. Hover for the full text.",
      "HCP column rule on Events rows: 9-hole-only events and mixed 9/18 events show only the 9-hole net handicap (e.g. '4.1 N'); 18-hole-only events show only the 18-hole index (e.g. '8.2'). Detection counts active registrants by holes — desktop and mobile match.",
    ],
  },
  {
    version: "2.10.10",
    date: "2026-04-27",
    title: "Tighter T+$ badge spacing; T badge re-tinted to deeper navy",
    changes: [
      "The circled 'T' (credit transfer) badge was mint green (#ecfdf5/#065f46) which clashed with the light-blue (#dbeafe) row tint applied to credit-transfer rows. Re-tinted to a deeper navy (#1e40af bg, white text, #1e3a8a border) so it harmonizes with the row color and reads cleanly.",
      "Added .status-tag-circle + .status-tag-circle adjacent-sibling rule to remove the inter-margin between two circular badges (e.g. T+$ on a paid credit-transfer row). They now group visually instead of looking like two unrelated tags.",
    ],
  },
  {
    version: "2.10.9",
    date: "2026-04-27",
    title: "Coupon C-badge on Events rows + circular $-badge replaces 'Paid' pill",
    changes: [
      "Events page registration rows (desktop + mobile) now render the same purple 'C' coupon badge that lives on the Transactions page. Triggered when coupon_code or coupon_amount is set on the item; tooltip shows 'Coupon: <code> -$<amount>'.",
      "The green 'Paid' pill on settled credit-transfer rows is now a circular '$' badge (mirrors the existing circular 'T' transfer badge). Same green colors, less horizontal space. Tooltip still shows 'Balance paid via Venmo on YYYY-MM-DD'. New .status-tag-paid CSS class.",
    ],
  },
  {
    version: "2.10.8",
    date: "2026-04-27",
    title: "Hide '(credit transfer)' suffix on price display",
    changes: [
      "Item prices stored as '$76.59 (credit transfer)' now render as just '$76.59' on the Transactions page (desktop + mobile), Events page (parent and child registration rows), and the credit / WD modal info panels. The circled-T tag and row tint already convey the transfer context. Storage is unchanged; the inline-edit data-original attribute still holds the raw value, so saving an unedited cell preserves the suffix. Math is unaffected — Python _parse_dollar() and JS parseDollar() both ignore the trailing parenthetical.",
      "Other suffixes like '(credit)' and '(comp)' are intentionally preserved.",
    ],
  },
  {
    version: "2.10.7",
    date: "2026-04-27",
    title: "Rename user role 'member' → 'golfer' (avoids collision with player_status MEMBER)",
    changes: [
      "Customer roles: the lowercase 'member' user-role has been renamed to 'golfer' so it no longer collides with the uppercase player_status display value 'MEMBER'. Player_status values (MEMBER, MEMBER+, 1ST TIMER, GUEST, FORMER, active_member, expired_member) are unchanged.",
      "New _migrate_rename_member_role_to_golfer() runs at startup, recreates customer_roles with the updated CHECK constraint (golfer, manager, admin, owner, course_contact, sponsor, vendor) and maps existing role_type='member' rows to 'golfer'. Idempotent.",
      "Updated callers: customer_roles seed in _migrate_seed_customer_roles, valid_roles set in /api/replace-customer-roles, ELEVATED + ALL_ROLES arrays in customers.html, and four hasRole() business-rule guards in events.html.",
    ],
  },
  {
    version: "2.10.6",
    date: "2026-04-27",
    title: "Coupon badge ('C') on transaction rows",
    changes: [
      "Items with a non-empty coupon_code or coupon_amount now render a small purple 'C' circle next to the item-name status tags (desktop table) and the top-tags row (mobile card). Hover tooltip shows 'Coupon: <code> -$<amount>'.",
    ],
  },
  {
    version: "2.10.5",
    date: "2026-04-27",
    title: "Match Venmo button on Events page (admin)",
    changes: [
      "Added a 'Match Venmo' button next to Check Now on the Events page header (admin-only). Triggers POST /api/accounting/auto-match-venmo-balance-due and reports counts. Useful after adding a customer alias (e.g. William Needles → Bill Needles) so a stuck Venmo IN gets re-matched without waiting for the 5-minute scheduler tick.",
    ],
  },
  {
    version: "2.10.4",
    date: "2026-04-27",
    title: "Customer credit badge shows cents",
    changes: [
      "Credit badges on the Customers page (mobile card, desktop table, mobile customer card) now format as $X.XX instead of whole dollars. A $0.19 overpayment credit no longer renders as $0 Credit. totalSpent formatting is unchanged (still whole dollars).",
    ],
  },
  {
    version: "2.10.3",
    date: "2026-04-27",
    title: "Reconcile sweep: also net already-attached +PAY children, case-insensitive merchant",
    changes: [
      "reconcile_orphan_venmo_payments() now runs a two-pass netting: (1) sums existing manual-entry +PAY children already attached to each balance_due parent, then (2) consumes orphan payments for any remainder. Joshua Bartz's $8.00 +PAY was already linked to his credit-transfer parent (parent_item_id=1224) so the orphan-only sweep skipped it; the new pass picks it up.",
      "Merchant filter is now case-insensitive (`merchant LIKE 'Manual Entry%' COLLATE NOCASE`) so it matches both 'Manual Entry (venmo)' (matcher-created) and 'Manual Entry (Venmo)' (human-entered) and any 'Manual Entry (Cash)' variants.",
      "apply_credit_to_rsvp() mirrors the same two-pass logic for forward-going Apply Credit operations, plus exposes the breakdown in its return dict.",
      "New helper _sum_existing_child_payments() factored out for reuse.",
    ],
  },
  {
    version: "2.10.2",
    date: "2026-04-27",
    title: "Apply Credit nets against prior unallocated Venmo +PAY (Joshua-Bartz fix)",
    changes: [
      "apply_credit_to_rsvp() now scans for orphan +PAY items by the same customer (Manual Entry / Manual Entry (venmo), parent_item_id IS NULL, last 14 days) and nets them against amount_owed before writing balance_due. Consumed rows are reparented onto the credit-transfer item with a [xfer-consumed:<id>] marker in notes for audit/undo.",
      "If the prior payment exceeds the difference, the surplus is posted as a transaction_status='credited' Overpayment credit item so it shows up in the customer's available credit pool (e.g. Joshua's $0.19 surplus from his $8.00 Venmo vs $7.81 owed).",
      "New backfill: reconcile_orphan_venmo_payments() + POST /api/admin/reconcile-orphan-venmo. Sweeps existing credit-transfer items with balance_due and applies the same netting retroactively. Idempotent; supports dry_run.",
      "reverse_credit_application() now detaches reparented +PAY rows (clears parent_item_id, strips the marker) and deletes any overpayment-credit-* item created during apply.",
    ],
  },
  {
    version: "2.10.1",
    date: "2026-04-27",
    title: "Coupon-aware price validation + faster default Audit Log window",
    changes: [
      "Parse validation: price_total_mismatch now adds coupon_amount back into the expected_price formula (item_price ≈ total_amount − transaction_fees + coupon_amount). Coupon-discounted orders no longer raise false-positive action items. Applies to both the in-flight parser check and the scan_price_games_mismatches backfill.",
      "Audit Log defaults reduced from 90 days / 100 emails to 7 days / 25 emails so Run Audit completes faster. Backend defaults on /api/audit/emails aligned to match.",
    ],
  },
  {
    version: "2.10.0",
    date: "2026-04-27",
    title: "Customer & Events polish: status logic, chapter cleanup, manager actions, UI tightening",
    changes: [
      // Customers — status derivation
      "deriveStatus now considers customer_roles + current_player_status authoritatively, with items as fallback. Recomputed after the /api/customer-roles fetch resolves so the badge reflects the final view.",
      "Membership-purchase auto-promote: any item whose item_name contains 'membership' lifts the customer to MEMBER, overriding stored player_status. _migrate_autocorrect_player_status mirrors this in the DB on init.",
      "1st TIMER cap: customers flagged first_timer with more than one purchase auto-demote to GUEST (frontend) and active_guest (DB migration).",
      // Customers — chapters
      "Chapter dropdown locked to the canonical chapters dim table (San Antonio, Austin, DFW, Houston, Hill Country) on the Info tab and Add-Customer modal. Legacy non-canonical values surface as a (legacy) option until an admin picks a canonical one.",
      "Hill Country added to chapters via _migrate_canonicalize_chapters (the original seed block early-returns once initialized). Same migration remaps legacy chapter strings: Cedar Park → Austin, Pflugerville → Austin, August → NULL, Yes_For_Both → NULL — applied across items.chapter, events.chapter, customers.chapter.",
      "update_customer_info now writes chapter to the customers master record (was only writing to items). /api/customer-roles surfaces chapter per customer, so the Customers page reads it authoritatively.",
      // Customers — list view
      "Activity-Year filter (default: This Year) — list filters to customers with at least one real purchase in the target calendar year. Roster Import / Customer Entry / RSVP Import / RSVP Email Link items excluded from the year match and from the customer-detail Transactions tab.",
      "Members stat card now shows a per-chapter breakdown beneath the count, sorted by chapter size desc.",
      "Full-row tinting on the Customers list by status: MEMBER mint, MEMBER+ teal, 1ST TIMER amber, FORMER slate, GUEST white. Mobile cards add a 4px left border accent.",
      // Customers — name normalization
      "_migrate_normalize_customer_name_case: converts UPPERCASE customer first/last names to proper case with Mc/Mac/O'/hyphen/Roman-numeral handling. Propagates to items.first_name / items.last_name / items.customer for every matching row, plus a second pass that re-syncs items rows where customers.* is already proper but items.* is still uppercase.",
      // Events — manager access
      "Manager role now has access to Event player ACTIONS: Credit, WD, Transfer, Reverse, Undo (reverse-credit-application), Apply Credit (item / RSVP / GG RSVP). Event-level Edit / Merge / Delete remain admin-only. Client-side undo handler also widened to admin || manager.",
      // Events — UI tightening
      "TRANSFER pill on event registrations replaced with a circular T badge.",
      "RSVP-Remind pill shortened to Remind. Balance-due pill now shows -$X.XX (was $X.XX DUE). Undo Credit button shortened to Undo.",
      "Delete buttons across event registrations and the Transactions table replaced with a compact red × icon (title='Delete'). Sort arrows hidden visually; column headers stay clickable.",
      "Check Now button added to the Events page header (mirrors the Transactions page button) — POSTs /api/check-now, polls /api/check-status, refreshes events on completion.",
      "Inactive and Not Playing player names linkable to /customers?name=... — full names rendered for Not Playing rows via the new rsvps.customer_id FK lookup (resolved_name from get_rsvps_for_event / get_all_rsvps_bulk).",
      // Events — row tinting
      "Row tints expanded: GUEST players render with a pink (#fbcfe8) background, 1ST TIMER players render with a peach (#fdba74) background. Distinct from the existing palette (mint comp/manager, light-blue manual/credit-transfer, amber RSVP-only, light-red WD).",
      "Surname uppercase decoration: displayName(name, status) renders the surname in UPPERCASE when status is MEMBER / MEMBER+ / MANAGER / OWNER (events.html and dashboard.js only — not the Customers page). Render-only; underlying data unchanged.",
      // Inbox cadence
      "Default scheduler interval reduced from 15 to 5 minutes (CHECK_INTERVAL_MINUTES env var still overrides). Inbox lookback for both the transaction inbox and the RSVP inbox reduced from 90 days to 7 days.",
    ],
  },
  {
    version: "2.9.0",
    date: "2026-04-22",
    title: "Event Cancellation, Credit Flows, Vendor System, and Expense Reconciliation",
    changes: [
      // Event Cancellation
      "Event Cancellation: Cancel or Postpone any event via a 4-step modal (choose status + reason → bulk or one-by-one → stage credits/refunds → send cancellation email). Refund method auto-detected from original payment method.",
      "Comp and RSVP-only players silently removed on cancel; add-on payments cascade via existing credit/refund logic. Restore Event available until first player action is taken.",
      "New event columns: status (active/cancelled/postponed), status_reason, rescheduled_to_event_id, status_changed_at. Cancelled/postponed badges on event list and detail view.",
      // RSVP Credit Application
      "RSVP Credit Application: green Credit badge on RSVP-only rows when the player has an outstanding credit. Apply Credit modal shows price breakdown, balance-due or excess, and disposition choice.",
      "After RSVP inbox check, credit alert emails are auto-sent to players with credits who are RSVPing to upcoming events.",
      "Undo Credit Application: reverse_credit_application restores source credits, removes excess item, reverses accounting entries, reverts target back to rsvp_only.",
      "Apply Credit from Customers page: Apply button on credited items opens event picker with price preview; idempotent via manual-credit-{id} uid.",
      // Vendor system
      "Vendor System: vendors stored in customers table with vendor role and company_name field. Vendor typeahead shows all vendors when focused (empty); + New Vendor creates and immediately selects.",
      "Ledger Customer/Vendor column with column visibility toggle (Customer/Vendor, Category, Type, Account) — persisted in localStorage via CSS class toggle on table element.",
      "Smart Fill: POST /api/accounting/smart-fill bulk-assigns accounts and default splits for all unsplit ledger entries. Dry-run preview before apply.",
      // Customer editing
      "Info tab: admins can edit Member Status (1ST TIMER / GUEST / MEMBER / MEMBER+ / FORMER) and Roles (member, manager, admin, vendor, etc.) directly on any customer profile.",
      "New member_plus status (DB migration adds to CHECK constraint); expired_member displays as FORMER for backward compat.",
      // Expense reconciliation
      "Approved expense transactions auto-promoted to acct_transactions with entry_type='expense' and amount set, so they appear in the Inline Match Queue.",
      "Auto-match handles negative bank deposits (debits): matches against entry_type='expense' entries within ±$1 / ±10 days. Confidence 0.85 (desc+amount), 0.65 (desc only), 0.55 (amount only).",
      "get_match_suggestions amount comparison fixed for expense deposits: uses abs(dep_amt) so -$21.37 debit correctly matches $21.34 expense.",
      "GoDaddy auto-match uses net_deposit (gross minus merchant fee) as comparison amount so bank credits match correctly.",
    ],
  },
  {
    version: "2.8.0",
    date: "2026-04-17",
    title: "Inline Match Queue in the Ledger — reconcile without leaving the page",
    changes: [
      "Clicking the 'Unreconciled' status pill in the Ledger now transforms the view into a two-panel split layout: unmatched bank deposits on the left, unreconciled ledger entries on the right",
      "Click a deposit to highlight amount-similar ledger entries (±$1) on the right — the matching column cell turns amber so the candidate jumps out",
      "Click a candidate row to select it, then press 'Match' to call POST /api/reconciliation/match — the deposit disappears from the left pane and the ledger row fades out",
      "'Auto-Match All' button runs POST /api/reconciliation/auto-match inline and reloads both panes; a brief status message shows auto/partial/unmatched counts",
      "When an account pill is active (not 'All Accounts'), the deposits list is client-side filtered to deposits from that bank account",
      "Other status pills (All / Reconciled / Pending Review) still render the normal flat table — the split pane only appears under Unreconciled",
      "The standalone /accounting/reconcile page is unchanged — it remains available for Account Dashboard, Monthly Summary / CSV export, and power-user batch matching",
    ],
  },
  {
    version: "2.7.4",
    date: "2026-04-17",
    title: "Hotfix: guard backfill with try/except",
    changes: [
      "Wrapped account_id backfill in try/except so schema edge cases can't crash startup",
      "ALTER TABLE migrations for account_last4/account_name remain; backfill is now non-fatal",
    ],
  },
  {
    version: "2.7.3",
    date: "2026-04-17",
    title: "Hotfix: add missing account_last4/account_name migrations",
    changes: [
      "Live Railway DB crashed on boot because backfill referenced expense_transactions.account_last4 which didn't exist",
      "Added ALTER TABLE migrations for account_last4 and account_name before backfill runs",
    ],
  },
  {
    version: "2.7.2",
    date: "2026-04-17",
    title: "Add account_id FK to expense_transactions",
    changes: [
      "expense_transactions.account_id INTEGER FK → acct_accounts.id",
      "Backfill: matches by last_four first, then by account_name",
    ],
  },
  {
    version: "2.7.1",
    date: "2026-04-17",
    title: "Fix account pill filtering for expense rows",
    changes: [
      "expense_transactions have no account_id FK — only account_name text and account_last4",
      "When an account pill is selected, now matches expense rows by last_four (preferred) or account name, so Chase/Venmo/etc. rows filter correctly",
    ],
  },
  {
    version: "2.7.0",
    date: "2026-04-17",
    title: "Ledger — account toggle pills + status filter pills",
    changes: [
      "Account pills replace the account dropdown: All Accounts | TGF Checking | Venmo (dynamically loaded from your bank accounts)",
      "Status pills replace the review dropdown: All | Active | Reconciled | Pending Review — one tap to see exactly what needs attention",
      "'Reconciled' pill shows only bank-confirmed ledger entries; 'Pending Review' shows only expense_transactions awaiting approval",
      "Advanced filters (Type, Category, Source, Review Status) now collapse behind a ⚙ Filters button to reduce clutter",
      "Tab renamed from 'Transactions' to 'Ledger' (v2.6.10) to distinguish from the top-level Transactions revenue page",
    ],
  },
  {
    version: "2.6.10",
    date: "2026-04-17",
    title: "Rename Transactions tab to Ledger",
    changes: [
      "The 'Transactions' sub-tab under Accounting is now labeled 'Ledger' to distinguish it from the top-level Transactions page (which tracks revenue registrations)",
      "acct_transactions table is the financial ledger — income, expenses, manual entries; the Transactions page at / is GoDaddy order registrations",
    ],
  },
  {
    version: "2.6.9",
    date: "2026-04-17",
    title: "Batch review — Event and Notes fields per row",
    changes: [
      "Each batch review row now has an Event input and a Notes input alongside Category and Entity",
      "Event is auto-populated from the description for GoDaddy transactions (text after ' — ')",
      "Both fields are included in the batch-approve payload — backend already supported them",
    ],
  },
  {
    version: "2.6.8",
    date: "2026-04-17",
    title: "Event typeahead — keyboard navigation (↑↓ Enter Escape)",
    changes: [
      "Arrow keys move the highlighted option up/down with blue highlight and auto-scroll",
      "Enter selects the highlighted option (or the only match when there's just one)",
      "Escape closes the dropdown; ArrowDown opens it if closed",
    ],
  },
  {
    version: "2.6.7",
    date: "2026-04-17",
    title: "Event typeahead — fix selection (double-quote/blur race condition)",
    changes: [
      "Dropdown items now use data-val + mousedown instead of onclick — JSON.stringify was injecting unescaped double-quotes into onclick attributes, breaking the handler",
      "mousedown + preventDefault() prevents the input from losing focus before the selection registers, eliminating the blur race condition",
    ],
  },
  {
    version: "2.6.6",
    date: "2026-04-17",
    title: "Event typeahead fix — correct field names; entity short name only",
    changes: [
      "Fixed event typeahead: events table uses item_name/event_date columns, not name/date — all events were being filtered out silently",
      "Business Entity dropdown now shows short name only (e.g. 'TGF' not 'TGF — The Golf Fellowship')",
    ],
  },
  {
    version: "2.6.5",
    date: "2026-04-17",
    title: "Create Ledger Entry modal — required category, inline add category/entity, custom event typeahead",
    changes: [
      "Category is now required — submit is blocked with red highlight if no category is selected",
      "Category dropdown has '＋ Add new category…' option — opens inline form to create and immediately select a new acct_categories entry",
      "Business Entity dropdown has '＋ Add new entity…' option — opens inline form to create a new acct_entities row",
      "Event field replaced with custom typeahead dropdown — shows matching events as you type, fully cross-browser reliable",
      "Add-category/add-entity inline forms hide correctly when reopening the modal",
    ],
  },
  {
    version: "2.6.4",
    date: "2026-04-17",
    title: "Ledger Entry modal — real DB connections for all fields",
    changes: [
      "Category dropdown now pulls from acct_categories table (was calling wrong URL /api/acct/categories instead of /api/accounting/categories)",
      "Business Entity field now pulls from acct_entities table; labeled 'Business Entity (TGF / Personal)' for clarity; defaults to first entity (TGF)",
      "Bank Account dropdown populated from bank_accounts table via already-loaded accounts data; pre-selects the account the deposit was imported to",
      "Event field is now a browser datalist autocomplete sourced from the events table — type to search all existing events",
      "Category dropdown groups into Income / Expense optgroups filtered by the selected Type",
      "Fixed get_bank_deposits() SQL join: was incorrectly joining to acct_accounts instead of bank_accounts — deposit account names now resolve correctly",
    ],
  },
  {
    version: "2.6.3",
    date: "2026-04-17",
    title: "Create Ledger Entry modal with full field set",
    changes: [
      "Create New Ledger Entry now opens a full modal overlay instead of replacing the suggestions column",
      "Modal pre-populates date, amount, and description directly from the bank deposit row",
      "Full field set: Type, Category (filtered by type), Entity, Account, Event, Notes",
      "Category dropdown updates when Type changes (shows income or expense categories)",
      "Account auto-detected from deposit description (VENMO→Venmo, PAYPAL→PayPal, etc.)",
      "Amount is editable — override the deposit amount if needed",
      "Escape key or backdrop click closes the modal",
    ],
  },
  {
    version: "2.6.2",
    date: "2026-04-17",
    title: "Batch Internal Transfer Recording",
    changes: [
      "Batch deposit selection — checkboxes on every deposit row in the Match Queue, with a Select All button",
      "Batch transfer bar — appears above the deposit list when deposits are checked; shows From→To account dropdowns and a Record All button",
      "Auto-detects destination account from deposit descriptions when selecting in batch (VENMO→Venmo, PAYPAL→PayPal, etc.)",
      "Processing progress indicator while recording transfers in sequence",
    ],
  },
  {
    version: "2.6.1",
    date: "2026-04-17",
    title: "Expense Inbox Hardening & Reconcile Transfer Accounting",
    changes: [
      "Expense re-parse no longer overwrites ignored/approved/corrected status — previously clearing inbox would re-queue already-dismissed items",
      "Block Merchant — new button on expense review modal; future emails from that merchant are auto-ignored at parse time",
      "'Not a Transaction' now sets ignored status instead of deleting the row, so the item won't reappear on next email sync",
      "Expense parser now uses the email received date as transaction_date unless the email body explicitly contains a different payment date — prevents invoice/event dates from being captured as the charge date",
      "Match Queue sign filter — suggestions for negative bank deposits (expense withdrawals) now show only expense/contra ledger entries, not income entries",
      "Internal transfer accounting — 'Mark as Internal Transfer' now creates a real acct_transactions entry (type=transfer) linked to the bank deposit, recording the debit/credit between accounts for proper reconciliation",
      "Transfer form with From/To account dropdowns — auto-detects destination account from bank deposit description (VENMO→Venmo, PAYPAL→PayPal, etc.)",
      "Removed 'Not Applicable' button from reconcile Match Queue — all bank deposits are real transactions and should be accounted for",
      "Dismissed deposits excluded from unmatched count on Account Dashboard",
    ],
  },
  {
    version: "2.6.0",
    date: "2026-04-17",
    title: "AI Bookkeeper, Liabilities Dashboard & Month Close",
    changes: [
      "Duplicate transaction fix — cross-table fingerprint dedup prevents email-parsed transactions from appearing twice when they already exist in the ledger",
      "Batch categorization preview — review AI suggestions 20 at a time before committing; covers the full YTD backlog across both inbox and uncategorized ledger entries",
      "Batch confidence badges — color-coded (green/yellow/orange/red) with source: exact match, prefix match, keyword rule, or Claude AI",
      "Duplicate warning flags in batch preview — items that look like existing transactions are flagged before approval",
      "Create from Bank — orphaned bank deposits that don't match any transaction can now generate a ledger entry directly from the Reconcile match queue",
      "Liabilities Dashboard — new tab showing all 9 TGF liability buckets: prize pools (per-event), course fees owed, HIO pot, season contests, Lone Star Cup shirt fund, chapter manager payouts, tax reserve YTD, investor debt, and member credits 2025",
      "Manual liability editing — click any manual liability bucket to update its balance; saves instantly to coo_manual_values",
      "Prize pool drill-down — expand the prize pools row to see the per-event breakdown",
      "Month Close checklist — live status for 5 close criteria: transactions categorized, inbox clear, deposits matched, ledger reconciled, events accounted",
      "Financial Position cards on Dashboard — YTD income, expenses, net; cash on hand vs. total liabilities; net position (cash minus obligations)",
      "Checklist action links — each failing item links directly to the relevant tool (batch review, reconcile page, events)",
    ],
  },
  {
    version: "2.5.0",
    date: "2026-04-17",
    title: "Platform Identity FKs, Payout Budget Reconciliation & Legacy Cleanup",
    changes: [
      "Payouts Made vs. Budget section on Event Financial tab — compares actual prize payouts against GAMES matrix budget (HIO, Included, NET, GROSS) with variance indicator",
      "customer_id FK added to acct_transactions — enables direct joins for event financial queries without string-matching on customer names",
      "customer_id FK added to handicap_player_links — Golf Genius player rows now carry direct identity link to customers table",
      "Backfill logic populates customer_id on existing acct_transactions and handicap_player_links rows using 5-step customer resolution cascade",
      "_write_acct_entry() now resolves and writes customer_id automatically on every new ledger entry",
      "Handicap import and relink routines now populate customer_id alongside customer_name",
      "Removed legacy acct_splits writes from transfer_item() — transfers already write flat acct_transactions entries via _write_acct_entry()",
      "Renamed create_acct_transaction() to _create_acct_ledger_entry() — clarifies it is the accounting-ledger path (bank imports, recurring entries), not the event financial model path",
    ],
  },
  {
    version: "2.4.0",
    date: "2026-04-14",
    title: "GoDaddy Order-Level Accounting, Match Queue & Reconciliation Indicators",
    changes: [
      "GoDaddy order-level accounting — entries now created per order instead of per item, with automatic migration from old format",
      "Order splits table — each GoDaddy order broken into registration, transaction fee, merchant fee, and coupon components",
      "GoDaddy merchant fee correction — updated from flat 2.7% to actual 2.9% + $0.30 per-order formula",
      "Batch match API — match multiple order transactions to a single bank deposit (1:many)",
      "Transaction merge — combine multiple GoDaddy orders into a single batch entry for deposit matching",
      "Match Queue: Browse All mode with wider date windows (±14 days) for finding older unmatched deposits",
      "Match Queue: deposit status filter — toggle between Unmatched, Matched, and All views",
      "Match Queue: matched deposit drill-down with Unmatch All to undo batch matches",
      "Match Queue: multi-select checkboxes for batch matching multiple transactions at once",
      "Reconciliation indicators — clickable green dots on reconciled transactions deep-link to Match Queue tab",
      "Reconciliation dots hidden for non-admin users",
      "\"Purchased by\" indicator now shown for all player statuses, not just GUEST items",
      "Venmo handles consolidated to customers table as single source of truth with roster import support",
    ],
  },
  {
    version: "2.3.0",
    date: "2026-04-13",
    title: "Bank Reconciliation, Smart Categorization, Handicap Cards & Mobile Accounting",
    changes: [
      "Bank statement import — upload CSV or PDF bank statements with auto-format detection (Chase, Frost Bank, Venmo)",
      "Smart bank reconciliation — suggestion-based matching engine with auto-match by amount, date, and description",
      "Smart expense categorization — auto-assigns categories using learned rules from past manual categorizations",
      "Cash flow page — 90-day rolling weekly view with expected income, confirmed deposits, expenses, and running balance",
      "Unified transaction review modal — full editing capability with account selector, category, event linking, and Save button",
      "Collapsible Source Data section in review modal for inspecting raw imported data",
      "\"Not a Transaction\" discard button — dismiss non-transaction statement emails from the review queue",
      "Handicap card email tools — preview card, send to individual players, or bulk send for an upcoming event",
      "Handicap card HTML rendering optimized for iOS Mail and mobile email clients",
      "Mobile admin views — optimized accounting card layout with inline editing controls on mobile",
      "Nav reorganization — Admin tab moved to first position, Accounting set as default admin page",
      "Guest swap improvements — 1st TIMER status detection and cross-item guest name matching in multi-item orders",
      "Customer dedup — email-based duplicate detection with auto-merge for matching customer records",
      "Account card enhancements — last-4 digit matching on bank accounts with click-to-edit",
      "RSVP auto-replace — placeholder RSVP entries automatically replaced when GoDaddy payment arrives",
      "Email TNEF/winmail.dat fix — resolved Outlook attachment rendering issues via Graph API",
      "Unified financial model — acct_transactions table as single source of truth for all accounting data",
    ],
  },
  {
    version: "2.2.0",
    date: "2026-04-09",
    title: "COO Dashboard Widgets, Financial Accuracy & AI Chat Enhancements",
    changes: [
      "COO Dashboard widget system — collapsible sections with drag-to-reorder for personalized layout",
      "Financial accuracy improvements — add-on revenue and allocation-based profitability now included in COO context",
      "Copy button on COO AI chat messages — click to copy any AI response to clipboard",
      "COO AI tone update — \"confident but vigilant\" analyst personality for more actionable insights",
      "Fix: Financial tab processing fee double-count removed, prize fund now calculated client-side",
      "Fix: Transactions table column widths constrained to prevent layout expansion",
    ],
  },
  {
    version: "2.1.0",
    date: "2026-04-08",
    title: "Compact Event Pricing — Collapsible Calculators, Player Type Cards & Side-by-Side Combo",
    changes: [
      "Collapsible Course Cost Calculator — collapsed by default (green fees only), click to expand all 5 line items",
      "9/18 Combo pricing displayed side-by-side: 9-Hole Calculator (green) + 18-Hole Calculator (blue)",
      "Event Cost total shown at bottom of each calculator card = ceil(Course Cost) + Markup + Inc. Games",
      "Calculator header shows rounded-up course cost (e.g., $68 not $67.11)",
      "Colored pricing cards: Member (green), Guest (blue), 1st Timer (gold), N/A (gray)",
      "Three tiers: Event Only, With One Game (+$16), With Both Games (+$32)",
      "Guest markup auto-derived: Member + $10 (9h/combo) or +$15 (18h standalone)",
      "1st Timer markup auto-derived: Guest − $25 (can go negative as discount)",
      "Both Games = N/A for Guest and 1st Timer; combo 18-hole = Member only",
      "Course cost rounds up FIRST before adding markup and game fees",
      "Transaction fee defaults to 3.5% (pre-filled value, not just placeholder)",
      "Renamed Side Game Fee → Inc. Games ($) to distinguish from per-game add-ons",
      "Modal widened to 700px for side-by-side combo layout",
    ],
  },
  {
    version: "2.0.0",
    date: "2026-04-06",
    title: "Guest Registration Handling, Action Items Banner, Event & Payment Fixes",
    changes: [
      "GUEST registration handling — parser auto-detects when a member buys for a guest and swaps customer name with 'Purchased by' note",
      "Guest? prompt tag on GUEST items in multi-item orders where guest name is unknown — click to assign the guest's name",
      "Action Items notification banner on Transactions + Events pages — aggregates parse warnings and guest items for admin/manager",
      "Per-order Re-extract button on Audit page — re-parse a single order's email without running bulk re-extract",
      "Re-extract now applies guest-swap (customer change) on GUEST items",
      "Add Payment: Event Upgrade (9→18 holes) now updates parent item's holes to 18",
      "Add Payment: Event Upgrade no longer incorrectly changes parent game type",
      "Add Payment: duplicate players in dropdown fixed (child payment rows excluded)",
      "Clickable game switching — NET ↔ GROSS toggle on event detail (no-cost swap only)",
      "Fix: paid players no longer incorrectly marked red from old GG RSVP 'NOT PLAYING' status",
      "Fix: Add Payment works for events with aliases (course changes)",
      "Fix: deleted/merged events no longer re-appear after deploy (seed + sync now check aliases)",
      "GUEST_NAME_MISSING parse warning — only fires for multi-item orders with no guest info",
      "Parse warning dismiss/resolve now accessible to managers (was admin-only)",
      "Improved AI prompt for extracting guest_name from Special Instructions",
    ],
  },
  {
    version: "1.9.0",
    date: "2026-04-05",
    title: "Multi-Agent Architecture: Chief of Staff, Financial, Operations, Course Correspondent, Member Relations, Compliance",
    changes: [
      "Six specialist COO agents with dedicated system prompts and domain ownership",
      "Agent routing in COO Chat — questions auto-routed to specialist by keyword, response always from Chief of Staff voice",
      "Agent action log — every agent decision logged with timestamp, action type, description, outcome",
      "Compliance Agent automated checks — sales tax reminders (15th-20th), IRS installment flags, pairings submission deadlines",
      "Compliance checks run automatically before daily COO email at 7 AM CT",
      "MCP tool: get_agent_action_log for querying agent activity",
      "Agent registry API: GET /api/coo/agents, GET /api/coo/agent-log",
    ],
  },
  {
    version: "1.8.0",
    date: "2026-04-05",
    title: "Bank Reconciliation: Chart of Accounts, General Ledger, CSV Import, Two-Way Matching, Month-End Close",
    changes: [
      "Chart of accounts with IRS Schedule C categories — income, expense, asset, liability accounts",
      "General ledger table for double-entry bookkeeping journal entries",
      "Bank statement CSV upload with auto-detect (Chase and Frost Bank formats)",
      "Duplicate detection on bank import — skips rows already imported",
      "Two-way auto-reconciliation — matches bank rows against items and expense_transactions by amount and date",
      "Three reconciliation states: Matched, In Bank Only, Missing from Bank",
      "Filter bar for reconciliation results: All / Matched / Unmatched / Missing",
      "Month-end close — locks period, generates income/expense/net/tax summary",
      "Reconciliation tab on Accounting page with chart of accounts display",
      "MCP tools: get_reconciliation_summary, get_ledger_entries",
    ],
  },
  {
    version: "1.7.0",
    date: "2026-04-05",
    title: "Daily Admin Email: Action Items, Financial Snapshot, Upcoming Events, COO Observations",
    changes: [
      "Daily COO briefing email at 7:00 AM CT to kerry@thegolffellowship.com",
      "Email sections: action items, financial snapshot, upcoming events (14 days), AI observations",
      "Manual trigger: POST /api/coo/send-daily-email for testing",
      "Professional HTML styling with TGF navy header, mobile-friendly inline CSS",
      "Deep links from email action items to /coo#action-[id]",
      "AI-generated observations (2-3 short pattern/risk/opportunity insights per morning)",
    ],
  },
  {
    version: "1.6.0",
    date: "2026-04-05",
    title: "COO Dashboard: Action Items, Financial Snapshot, Review Queue, COO Chat",
    changes: [
      "New /coo page — COO Operations Command Center with four vertical sections",
      "Action Items checklist — urgency badges, resolution workflow, AI advice integration",
      "Financial Snapshot — account balances, obligations (prize pools, course fees, tax reserve), debt tracker",
      "Available to Spend calculation — TGF Total minus all outstanding obligations",
      "Editable manual values — click any balance or debt to update inline",
      "Unified Review Queue — pending expense transactions + low-confidence action items in one view",
      "COO Chat — Claude Sonnet-powered strategic advisor with full operational context",
      "COO nav tab added to all pages",
    ],
  },
  {
    version: "1.5.0",
    date: "2026-04-04",
    title: "COO Agent Foundation: Allocation Tracking, Course Cost Infrastructure, list_events MCP Tool",
    changes: [
      "Multi-entity accounting system — track income/expenses across TGF, Personal, and future entities with transaction splitting",
      "AI Bookkeeper — auto-categorizes transactions using learned rules + Claude AI, with event-aware suggestions",
      "CSV bank import with smart auto-detect column mapping (Chase, Amex, Wells Fargo supported)",
      "Transfer auto-detection and cross-account linking during CSV import",
      "Standard accounting categories — IRS Schedule C business, personal finance, and TGF-specific categories",
      "Event linking on transaction splits — associate expenses with specific TGF events",
      "Course surcharge field on events — per-player surcharges (e.g. $1 ACGT printing fee)",
      "Allocation tracking table — breaks down every GoDaddy order into course payable, prize pool, TGF operating, GoDaddy fee, and tax reserve",
      "Allocation calculation engine with membership and season contest support",
      "list_events MCP tool — exposes event pricing data to Claude for COO agent queries",
      "Version sync — all version references now consistent at v1.5.0",
    ],
  },
  {
    version: "1.3.0",
    date: "2026-03-04",
    title: "Messaging, Roster Import & RSVP Linking",
    changes: [
      "Bulk email messaging for events — compose, preview, send to filtered audiences with reusable templates",
      "Message templates — create, edit, delete reusable email templates with variable placeholders",
      "Message log — track all sent messages per event with delivery status",
      "Excel roster upload — bulk import customers from spreadsheets with column detection and email matching",
      "Structured name fields — first/last/full names with AI parsing and validation",
      "Customer aliases — link alternate emails, phones, and names to a single customer record",
      "Add Customer button on Customers page — create customers manually without a transaction",
      "Customer Info panel — read-only default with Transactions/Info tab toggle on customer cards",
      "Customer update API — edit customer details (email, phone, chapter, status) inline",
      "Link to Customer on RSVP Log — connect unmatched RSVPs to existing customers",
      "New Customer from RSVP — create a customer record directly from an unlinked RSVP entry",
      "Auto-resolve RSVP player names from known customer emails",
      "WD (withdrawal) action for event players — mark players as withdrawn with credit tracking",
      "Player card editing on Events page — inline edit player details on mobile cards",
      "Extra email recipients — add CC recipients when sending event reminders",
      "NET/GROSS/NONE connected toggle group — unified button bar replacing separate dropdowns",
      "Audit date range and limit controls — filter audit emails by 7/14/30/90 days",
      "Autofix confirmation + undo — preview changes before applying, one-click rollback",
      "Re-extract fields audit tool — backfill new item fields from original email text",
      "Customer email/phone backfill in Autofix All",
      "RSVP full-name and email backfill in Autofix All",
      "Support feedback system — collect and review user feedback with daily digest emails",
      "Test digest button on Audit > Feedback tab",
      "Fix OAuth flow for Claude.ai MCP connector — PKCE + stateless HMAC tokens",
      "Mobile improvements — merge/edit/delete on cards, game stat badges on collapsed cards",
      "Exclude non-transaction placeholder rows from Transactions and Events views",
      "Pin mcp, uvicorn, and a2wsgi dependency versions"
    ]
  },
  {
    version: "1.2.0",
    date: "2026-03-01",
    title: "Audit Hardening",
    changes: [
      "Log database errors instead of silently swallowing them",
      "AI parser now surfaces API auth and bad-request errors properly",
      "Add managed_connection context manager to prevent DB connection leaks",
      "Wrap auto-refresh intervals in try/catch to prevent silent failures",
      "Fix XSS risk in orphan banner — replaced inline onclick with data-attribute handlers",
      "Email send results now checked and reported to frontend",
      "Warn at startup if SECRET_KEY is not set in environment",
      "Add input validation (type/length) on mutation API endpoints",
      "Fix RSVP popover event listener leak on repeated clicks",
      "Added .get() guards on all API endpoints",
      "NOT NULL constraints on customer/item_name columns",
      "Add database index on transaction_status column",
      "Tighten scheduler race condition with PID-based guard",
      "Case-insensitive customer name matching in merge",
      "DOM null reference guards across all pages",
      "Fix amount inputs to prevent multiple decimal points",
      "Clean up cached RSVP overrides when collapsing events",
      "Accessibility: aria-required, aria-label, role=dialog on modals",
      "CSS cleanup: replaced !important with variables and specificity",
      "Consolidate inline onclick handlers to addEventListener pattern",
      "Move inline imports to module level",
      "Removed dead code and redundant imports"
    ]
  },
  {
    version: "1.1.0",
    date: "2026-02-26",
    title: "Add Player Overhaul + GG Dot States",
    changes: [
      "Redesigned Add Player dialog with 3 modes: Manager Comp, RSVP Only, Paid Separately",
      "GG RSVP dot now has 4 states: blank, auto-green (GG Playing), red (GG Not Playing), manual-green (manager confirmed)",
      "RSVP-only players can be upgraded to full registration via Record Payment action",
      "Skins label now shows '1/2 Net Skins' when <8 gross players, 'Skins Gross' when ≥8",
      "Fixed skins NO_EVENT display bug (was showing — $0 NaN)",
      "Added Side Games Matrix page with 9/18 toggle and inline editing",
      "Populated Net and Gross data for 2-3 players in games matrix",
      "Added version display and changelog page"
    ]
  },
  {
    version: "1.0.0",
    date: "2026-02-20",
    title: "Initial Release",
    changes: [
      "Transaction dashboard with email parsing",
      "Events page with registration tracking and side games",
      "Customer directory",
      "RSVP Log from GolfGenius",
      "Audit Log with data quality checks",
      "Mobile-responsive design"
    ]
  }
];
