# Handoff — FLIGHTING lane: the ratified rules as data + the DIVISIONS/FLIGHTS tab (2026-09-21)

Lane "Flighting & payouts", branch `claude/flighting-payouts-k7p2wd`,
shipped to `main` as **v2.469.0**. Spun off "TGF Tracker Improvements 2"
by Kerry on 2026-09-21 ("Spin off the flighting lane for #582"). Mailbox:
#582 (CA's lane request), #584 (this lane's ack + plan), the digest that
closes it. Rulings applied: #571–#575 as revised by #581/#582 — nothing
reopened.

## 1. What shipped

| Piece | Where | Guard |
|---|---|---|
| The rule set as data: ladders, no minimum / no merge, places by flight size, the Individual Gross pot with the 10% Overall Low Gross bonus, derived labels, tie split to the cent | `email_parser/flighting.py` (`FLIGHT_RULES`, `cut_by_edges`, `places_for`, `gross_amounts`, `net_amounts`, `skins_amounts`, `tie_split`) | `test_flighting.py` |
| Two layers: `build()` = SELECTION + AMOUNTS from one field; `settle()` = frozen SELECTION, late add placed by the frozen edges, credited WD dropped from the headcount, AMOUNTS recomputed, DELTA per flight | same | same (#572 field A, #573 worked examples, Landa Park 6/5/4, Cedar Creek T1×3, ½ Net frozen at 7 stays ½ Net at 8, published-at-10-settles-at-9 pays one place, 300 random fields to the cent) |
| The board from Tracker data: roster buy-ins (`_event_game_buyers`, wd_credits decides), 18-hole index of record locked as-of, PH as the starter sheet computes it (`_event_player_ph_map`), LIVE matrix (source reported), GG's recorded purses beside each game | `database.py` `event_flights_board`, `_event_player_ph_map`, `_event_gg_recorded_purses` | `test_flights_board.py` |
| The printed Divisions & Flights page is a VIEW of the board | `database.py` `event_flights_report` (adapter) | `test_event_reports.py` |
| FLIGHTS tab beside GAMES on every event with a hole count, manager+, desktop + phone, re-read on every open, survives a refresh | `templates/events.html` (`data-toggle-games="5"`, `flightsOpenForEvent`, `loadFlightsBoard`, `renderFlightsPanel`, `fbGgRecorded`) | page JS guards still green |
| `GET /api/events/<id>/flights-board` (manager+); bridge `scoring-flights-board:<event_id>` | `app.py`, `mcp_server.py` | `test_flights_board.py` |
| Seed flip by ruling: `SEED_FLIGHT_CONFIG.min_flight_size` 0; the 3-flight ladder comment reads RATIFIED | `email_parser/live_scoring.py` | `test_live_scoring.py` |
| Docs: events.md "The DIVISIONS / FLIGHTS tab", live-scoring-spec-for-ca.md §4/§5/§6 status banners, side-games.md Individual Gross ruling, state-of-the-tracker.md §2 + §5, CLAUDE.md index + key files, the print page footer | — | — |

**Dry run, by design.** `dry_run: True`, `payer_of_record: "Golf Genius"` on
every board. No payout row is written or read for payment; the recorded
payouts path (`assemble_event_game_payouts`, the `gross_flight_pot_mode`
dial, GG purses) is untouched.

## 2. How the rulings were read (the ASSUMPTIONS on the record, #584)

- The B4-revised pot (10% bonus + 90% by headcount) and the 1/10/20 places
  rule apply to **Individual Gross**. **Skins is unaffected** (#572, verbatim):
  its structure freezes the same way; its pot stays the matrix skins pot ÷
  flights, paid per skin. **Individual Net** keeps the equal-size cut with the
  11.9 ceiling (#571: "net flights are equal-size cuts and unaffected except
  B2") and its AMOUNTS from the live matrix's place columns, read per flight
  in the recorded-payouts convention (netLow, netHigh, netMid, net4th).
  **Awaiting Kerry:** whether 1/10/20 should also govern Individual Net's
  places (one dial if so).
- The Individual Gross rate is the buy-in split in side-games.md ($8 on an
  18 / $4 on a nine), so share = $7.20 / $3.60 exactly as #582 states.
- An EMPTY band is still a numbered flight on the board (no merging means
  the ladder's bands are the flights, whoever is in them); it prints greyed
  with "no players in this band" and pays $0.
- A game NOT running at the freeze does not start at settlement; a game
  that WAS running keeps running if buyers fall.
- Net's frozen "edges" are the equal-size cut's own boundaries (each flight's
  exclusive upper bound = the next flight's lowest index) so a late add after
  the freeze lands by the same line.

## 3. Rule 3b — the freeze schema: RATIFIED and BUILT (v2.471.0)

Kerry 2026-09-21 ~2:20 PM CDT: "Yes, build the freeze tables and the button."
Built as proposed in #584 (`board_json` holds both layers instead of two JSON columns; see schema.md "Flight snapshots"). The freeze is the FREEZE button on the tab; SETTLE and Unfreeze sit beside it; bridges `scoring-flights-freeze|settle|unfreeze:<id>[|apply]`. The proposal, as it was ratified:

- `event_flight_snapshots(id, event_id FK events, state 'frozen'|'settled',
  taken_at, taken_by, trigger 'freeze_button'|'final_pairings_send'|'closeout',
  handicap_as_of, holes_key, matrix_source, structure_json, amounts_json,
  note, voided_at, voided_by)` — one row per transition; voiding keeps the row.
- `event_flight_snapshot_members(snapshot_id FK, game, variant, flight_no,
  flight_label, customer_id FK customers, customer_name, index_18,
  playing_handicap, buyer_kind)` — principle 6.
- State DERIVED from rows (LIVE / FROZEN / SETTLED); no `events` column.
- Actions `POST /api/events/<id>/flights/freeze|unfreeze|settle` (manager+,
  audited) + bridges. Settle writes the recomputed amounts and the delta;
  pays nobody.
- **The first question to Kerry (#584):** is the freeze action the Final
  Pairings send button or a separate FREEZE button? Recommendation: a FREEZE
  button on the FLIGHTS tab; the send OFFERS to freeze when the event is not
  frozen yet, so a re-send never silently re-freezes.

The page already renders FROZEN / SETTLED (badge with timestamp, "since
freeze" panel per flight and per game) from the same payload shape
`flighting.settle()` returns; wiring is the schema + the action.

## 4. Dry-run findings (bridges, read-only)

- **s18.11 Cedar Creek (9/19, 18h):** Ind Net 9 buyers / 1 flight; GG paid
  T1×3 at $54 = $162 = matrix 108 + 54 pooled — the tie rule reproduces it.
  Skins 8 buyers / 2 flights: GG paid $104 + $104 (equal per flight, the
  matrix rule) but cut the field **4/4** (Schneider 9.6 in the upper flight)
  where the 12.0 ladder cuts **5/3** — the P2-6 class on a hardened event;
  reported, nothing changed. Ind Gross did not run (8 < 12).
- **s18.10 Landa Park (8/29, 18h):** Ind Gross 15 buyers, ladder 6/5/4;
  ratified rule pays $43.20 / $36.00 / $28.80 + $12.00 Overall Low Gross =
  $120; GG paid 48 / 36 / 36 (40/30/30, no bonus) — same $120, moved
  differently. Skins 15 → $135 / $135 under the matrix rule (11/4 cut).
- **Tomorrow (as of 9/21 midday):** s9.24 Brackenridge — Ind Net 14 → 2
  flights 4/10 (equal-size, ceiling moved 3 up); Skins 10 → 3/7 at 12.0; Ind
  Gross off (10 < 16). a9.24 Teravista — Ind Net 7 → 1 flight; Skins 5 on a
  nine → Skins ½ Net; Ind Gross off.
- **Live boards (deployed build, `scoring-flights-board`, 2026-09-21 1 PM):**
  Landa Park Ind Net 19 → 10/9 (cut at 11.8); matrix 98.50/59.10/39.40 per
  flight = $394 and **GG paid $394 to the cent** (LOW T1×2 at $78.80, HIGH
  T3×2 at $19.70 — the tie rule reproduces GG). Cedar Creek Ind Net likewise.
  **Skins cut finding:** on BOTH completed 18s GG cut Skins by EQUAL HALVES
  (Cedar Creek 4/4, Landa Park 8/7 — Wade 9.4 / Vasquez 11.2 / Hogue 11.8
  upstairs), not at 12.0 as #572 states; the board cuts at 12.0 (P2-6,
  forward only) and the digest asks Kerry which GG runs tomorrow
  (Brackenridge: 3/7 by the ladder vs 5/5 by GG's habit). Brackenridge
  prints no PH: the course record's tee legend is empty (the starter-sheet
  bridge shows the same) — the parent lane's course-record item.

## 5. How to verify without a login

`scoring-flights-board:<event_id>` → the whole board: `state`, `buyers`,
`handicap_as_of`, `matrix_source`, per game `selection` (variant + reason,
flight_count + source, edges, flights with members: customer_id / name /
index / PH), `amounts` (pot, bonus, share, per-flight pots and places),
`gg_recorded` (rows + total), `delta` (null while LIVE).
`scoring-event-report:<event_id>|flights` → the printed page as data
(the same cut).

## 6. Root causes / lessons

1. **The seed said UNRATIFIED for weeks after the ruling.** `SEED_FLIGHT_CONFIG`
   carried `min_flight_size: 3` (merges) and "UNRATIFIED" on the 3-flight
   ladder; the printed Divisions & Flights page merged thin flights on
   every pack. A ruling has to reach the seed the day it lands.
2. **Two computations of one fact.** The printed page and the tab would have
   cut the field separately; the page is now an adapter over the board.
3. **Version collisions, twice in one hour.** Merge `origin/main` BEFORE
   bumping; on conflict keep both entry sets with yours renumbered above
   origin's top (2.468.5 → 2.468.6 landed during the push; 2.469.0 stayed
   above both).
4. **A fixture index rounds.** The index of record rounds to a tenth on the
   nine-hole scale, so an 18-hole fixture value like 5.9 (→ 2.95 → 3.0 →
   6.0) crosses a cut line. State fixture indexes with even hundredths.

## 6b. Kerry's answers, 2026-09-21 afternoon

1. Freeze action: "Let's go with the button for now." — a FREEZE button on
   the FLIGHTS tab. Waits on the schema (2).
2. The snapshot schema: Kerry asked to see it again ("What is that about?
   Show me again") — explained in plain words in the session reply; not
   yet ratified, nothing built.
3. Places: "Matrix should govern placewinners for [Net]. 1/10/20 for Gross
   yes. Probably just needs to be part of the matrix as well based on
   players in a flight." → `gross_places_by_flight_size` dial (v2.469.4),
   seed = FLIGHT_RULES; Matrix-page editor next.
Also that afternoon: Brackenridge's four tee sets seeded from Kerry's GG
screenshots and designated; nine-hole PH now reads per-nine rating rows.

## 7. Open / carried forward

- Next: the Final Pairings send OFFERS the freeze when the event is not
  frozen; the closeout routine writes the settled snapshot; a Matrix-page
  editor for `gross_places_by_flight_size`.
- P2-6 item 4 (a label/assignment mismatch on a future event raises a
  followups CA Queue item) is NOT built: it is the closeout comparison of
  `gg_game_flights` against the FROZEN selection, so it follows the schema.
- Kerry: which Skins cut GG runs tomorrow (12.0 ladder vs equal halves).
- The Flighting Lab (`ls_flight_lab`) still runs `flight_plan` with the
  seed's dials — fine as a lab; the board is the rule.
- Not this lane: Kissing Tree combo yardages (Event Closeout lane), handicap
  surfaces / print pack / pairings automation (parent lane), paying anyone.
