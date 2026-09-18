# Handoff — Handicap Surfaces: Identity + Plus Rule, and the Handicap Lock (2026-09-16 → 18)

Lane "Handicap Surfaces: Identity + Plus Rule", branch
`claude/handicap-surfaces-k4m9xr` (merged to `main` as v2.459.0), then
continued on `main` through **v2.465.9**. Spun off from "TGF Tracker
Improvements 2" by the 2026-09-16 contract
(`session-prompt-2026-09-16-handicap-card-identity.md`); Kerry then
routed the parent's carry-forwards (items A–G) and the morning-after
findings here. Mailbox: #534, #536 (digests); CA Queue #2/#3/#5/#6/#8
closed by this lane.

## 1. What shipped, by version

| Version | What | Guard |
|---|---|---|
| 2.458.0 | Points race rows vs total (event-day refresh window; the timezone trap in the old guard) | test_points_race_staleness.py |
| 2.458.7–9 | Tee legend zip-before-sort; blind re-seat by person across regenerations; one blind per person; gg rows left loose | test_tee_legend_pairing.js, test_blind_reseat.py |
| 2.458.10 | **An ingest may not erase what it does not carry** (`_write_event_pairings_from_groups` preserves hole label / tee / index / customer_id); tee read from the ROSTER at read time; "Group N" never printed as "Hole Group N"; `scoring-pairings:relabel` repair; s9.23 sheet repaired live | test_pairings_ingest_preserve.py |
| 2.458.11 | **"Women"** on both legends via `TEE_LEGEND_WOMEN_WORD`; key aligns to the visible board edge (already v2.446 `fitKeys`) | test_tee_legend_pairing.js |
| 2.459.0 | Handicap-card send by customer_id (`get_handicap_export_data` publishes it; `audit_handicap_link_identity` / `scoring-hcp-link-audit`); the plus rule in `compute_hole_derivations(game=)`; half-away-from-zero round deduction; MVP on the game view from `PLUS_RULE_EFFECTIVE_DATE`; GROSS − PH = NET total columns on the expanded card | test_handicap_identity.py, test_plus_handicap_card.py, test_plus_handicap_render.js |
| 2.462.0 | **The handicap lock**: `get_all_handicap_players(as_of=)`, `_event_index_as_of(ev)`, `/api/events` publishes `handicap_as_of`, `/api/handicaps/index-map?as_of=`, page `ensureHcpAsOf` + `hcpEntryFor(name, cid, ev)`; **PAIRINGS = ROSTER** (`_roster_handicap_index_map` is a view of the one computation, not an average); Avery Ranch PH from the event's own rounds; `scoring-pairings:sheet` bridge | test_handicap_index_lock.py |
| 2.462.1 | PH note scoped to tees a seated player uses | — |
| 2.462.2 | A tee row's nine decided by played history (`events.nine_side`, `handicap_rounds.nine`) — Avery Ranch labelled itself, 8/8 | test_tee_nine_from_history.py |
| 2.464.6 | Remembered PAIRINGS tab repaints on a phone after reload (`detailContainerFor`) | test_events_restore_mobile.js |
| 2.464.7–8 | `scoring-chapter-guesses[:confirm\|…]` — chapter guesses with evidence; confirm writes blank profiles only | test_chapter_guesses.py |
| 2.464.9 | House chevron on `/me` + Money Flow; `state-of-the-tracker.md` rewritten in full | test_chevron_standard.js |
| 2.464.10–13 | **A swap moves the whole person** (`_swapSeatPayloads`, `_movePlayer` copies the seat); save resolves a seat's id by name (`_seat_customer_id`); read corrects stale ids; the ROSTER tee wins over the row snapshot; `scoring-pairings:swap` | test_pairings_swap_identity.js, test_pairings_seat_identity.py |
| 2.464.14 | **customer_id is king** (principle 6): `name_parse_failures.customer_id`, the seed picker carries the id; the allow-list of person-naming columns without a sibling id is EMPTY | test_customer_id_everywhere.py, test_seat_carries_identity.js |
| 2.464.15–16 | Team handicaps: the MATRIX decides CART (<16) vs TEAM; allowance on the unrounded CH, rounded once, **off the lowest in the FIELD** (never per cart); IDX on the event's scale (18-hole index on an 18) on sheet + cards | test_team_handicaps.py |
| 2.465.0–7 | **The print pack**: Starter Sheet + Cart Signs + Divisions & Flights + Proximity bound into one PDF, mailed the evening before (5–10 PM Central, once per change); bridge `scoring-print-pack-pdf:<id>[\|send]`; Railway build fixed twice (a literal `\n` in requirements; Nix libs) | test_print_pack.py |
| 2.465.2 | PH beside the index in the foursome boxes; both badges; CART/TEAM label follows the game; centred handicap columns | test_event_reports.py |
| 2.465.6 | **Rule 15h**: a Cart Net blind is drawn from the OTHER cart of the same foursome (field only when nobody there qualifies); Team Net unchanged (field outside the group) | test_blind_draws.py |
| 2.465.8 | Pack rendered by headless Chromium (WeasyPrint fallback) — the WeasyPrint pack "really bad compared to the PDF downloads" | test_print_pack.py |
| 2.465.9 | **NEW = first event AS A MEMBER** (membership started ≤ event, nothing played since); 1T independent; both can show | test_new_badge.py |

## 2. Kerry's rulings this lane (verbatim, dated)

- 2026-09-16 "Open circles should be for ladies tees, not men." / "S1. Women's." / "sync up the two legends".
- 2026-09-16 "Individual Net is not a pops per hole game… Gross Score − PH = Net Score" / "I accept your recommendation."
- 2026-09-16 "D. Standard rounding where .5 goes away from 0." (CA Queue #5)
- 2026-09-16 "MVP − Proceed." (game view forward only)
- 2026-09-16 "C. 1. Could be more if fivesomes are selected 2–5. Correct." (rule 15f)
- 2026-09-16 "Re-seat the pairings as necessary to match and fix blinds. If the tees are in ROSTER, they should automatically show up in PAIRINGS."
- 2026-09-16 "ROSTER handicaps need to lock after an event begins. Past events should not update to current handicap indexes." / "PAIRINGS handicap indexes are not matching those in ROSTER."
- 2026-09-16 "Team Net is 75% for one ball, 85% for two ball, and 100% for 3 or 4. Cart Net… 85% for one ball and 100% for 2 ball" (codified by the side-games lane, CA #8).
- 2026-09-18 "Confirm all" (nine chapter guesses written; Pollard left).
- 2026-09-18 "Why would you ever swap a player without all of their related stuff?" (a swap moves the whole person; and "Justin with Ty. You with Jeff" was a DESCRIPTION of the sheet, not an instruction — I swapped Kerry↔Straiton on it and had to revert. Ask before acting on an ambiguous sheet change.)
- 2026-09-18 "EVERY person gets a customer_id, no matter what their role is… customer_id is king… everything remotely related to a customer needs to be tied to that customer." (CLAUDE.md principle 6, verbatim)
- 2026-09-18 "For an 18 hole event, the TGF Handicap to be shown should be the 18 hole handicap. Also should show the 18 hole PH and Team… Cart Net going tomorrow which is 85%."
- 2026-09-18 "OFF Lowest is not per cart. OFF Lowest is lowest in the whole field. For 1/2 Net Skins it is field too. Team Net is field too."
- 2026-09-18 "On Cart Net, when there are OPEN slots in need of a Blind, the blind is from the other cart in the foursome… In Team Net, it is randomly from the field outside of their group" / "Only if the players in the other cart do NOT meet the prerequisites to be a blind, is a blind randomly selected from the field for Cart Net." (rule 15h; Mary Wade's blind = Louis Schneider)
- 2026-09-18 NEW badge: "Correct on your NEW badge understanding. Ship it." — first event as a member; 1T = first TGF event ever; a first-timer who is already a member wears both.
- Platform stack (2026-09-16): Supabase for live leaderboards; one scorer per group with lock/take-over rules; Redis-class only for per-viewer state at volume.

## 3. Root causes worth remembering

1. **The average.** `_roster_handicap_index_map` was written on 2026-09-15 (v2.416.0) as a fresh query — AVG of the last 20 differentials — instead of calling the index the ROSTER computes. Always 2–4 above the real index; gave a two-round first-timer a number. One day old when Kerry caught it. Lesson: one computation per fact; a "map" is a view.
2. **The ingest that erased.** The Team Net board ingest wrote `slot=None` → "Group N", no tee, no id, over a sheet Kerry had built. Lesson: an ingest may not erase what it does not carry.
3. **The desktop-only repaint.** Three sites looked up `detail-content-<id>`; the phone's container is `ev-mobile-detail-<id>`. Data arrived, nothing repainted. Lesson: resolve the container through one helper that knows both layouts.
4. **The test gate that did not stop.** `python3 test … | grep -v PASS && push` pushed a red test (v2.464.7). Use `|| exit 1` on the test itself.
5. **The badge that was defined three times.** NEW went "joined since last event" → "first-year member" → "first event as a member" in one day. Each was a plausible reading of one sentence; only the third matched what Kerry meant, and he had to name three counter-examples to get there. Lesson: when a rule is about PEOPLE, state the rule back with named members who would and would not qualify BEFORE building it.
6. **The renderer that could not do the layout.** WeasyPrint has no flex/grid; the sheets the browser prints correctly came out stacked. A PDF of a browser template must come from a browser (Chromium). And a current Chrome has removed Playwright's default `--headless=old`; pass `--headless=new`.
7. **Version collisions.** Three lanes on `main` within hours; merge `origin/main` BEFORE bumping, and resolve `version.js` by keeping both entry sets with yours renumbered above origin's top.

## 4. Open / carried forward

- CA Queue #1 (TEAM per-player nets schema), #4 (chapter badge rule), #9 (fivesome allowance), #10 (card-path allocation), #11 (9s vs 18s stroke application) — Kerry's.
- Eric Pollard's home chapter (only order DFW) — new row.
- Handicap lock is DERIVED (as-of), not stored: a back-dated or deleted round moves an as-of index. Kerry read the trade-off and continued; a stored snapshot would need schema (3b) — new row.
- design-claude reviews #517 / #520 still await a reply: `read_platform_dialogue` returns only the newest 20 posts after `since_id`, so those two could not be re-read from this lane. Next lane: fetch them another way (or ask design-claude to re-post) before answering.
- `test_starting_handicap.py` is red on `main` (fixture lacks `items`) — pre-existing, untouched.
- 1,217 pending GG-history identity names at `/admin/gg-history` (gg-history lane).

## 4b. Cedar Creek (event 3310, 2026-09-19, Cart Net, 15 players) — where it was left

Sheet verified live: field-lowest off-lowest, 18-hole IDX, PH + CART columns, Louis Schneider as the blind for Mary Wade's 8:10 cart-B seat, groups as Kerry built them (8:20 Straiton/Rideout/Angelone/Bubela; 8:30 Kerry/Clarkson/Mazanec/Pearson). One pack was emailed through WeasyPrint (bad); the NEW-rule change alters the content hash, so the evening routine re-sends the Chromium pack itself between 5 and 10 PM Central, or `scoring-print-pack-pdf:3310|send` does it on demand.

## 5. How to verify a sheet without a login

`scoring-pairings:sheet|<event_id>` → `handicap_as_of`, every seat's
locked index / roster tee / hole label, the print pack's PH basis +
note, and per-player IDX / PH / TEAM as the starter sheet prints them.
`scoring-tee-nines:<course_id>` → which nine each tee row is and why.
`scoring-blinds:<event>` → the blind rows (`drawn_from` says other-cart vs field). `scoring-print-pack-pdf:<event>` → parts, pages, engine, hash without sending. `scoring-chapter-guesses` →
whose chapter is still a guess.
