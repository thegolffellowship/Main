# Handoff — Handicap Surfaces lane, part 2 ("TGF Tracker Improvements 2")

**Session:** https://claude.ai/code/session_01CD1p3A96wXobio1yz2y7JS
**Span:** 2026-09-18 evening → 2026-09-23 afternoon · **v2.465.10 → v2.487.4**, all on `main`
**Successor:** "TGF Tracker Improvements 3" — `docs/claude/session-prompt-2026-09-23-tracker-improvements-3.md`
**Before this:** `handoff-2026-09-18-handicap-surfaces-lock.md` (v2.458.0 → v2.465.9)

The lane began as Handicap Surfaces (identity + plus rule) and became Kerry's
general Tracker-improvements lane: print pack, pairings automation, blinds,
the roster→money flows, course identity, and the daily morning brief. This
record is what a successor must not re-derive.

---

## 1. Rulings Kerry made (verbatim where quoted; do not reopen)

| Date | Ruling |
|---|---|
| 9/21 | Pairings auto-generate the day before, 5:00 PM; print packs go out the morning of; **Send Pack** button. |
| 9/22 | Austin print pack also goes to Robert Straiton (`print_pack_chapter_recipients`, default `{"Austin": "robert@thegolffellowship.com"}`). |
| 9/22 | Brackenridge twin course records merged — and all six twin merges applied (Lost Pines, Silverhorn, Star Ranch, Twin Creeks …). Riverside exists in SA, Austin and DFW: never merge by short name without the city (`_LOOSE_PIN_NEEDS_CITY`). |
| 9/22 | BLINDS button and open-spot RANDOM are the **same rule** (one `_blind_seat_candidates`), BLINDS does all at once; the 5:00 PM auto-pairings also draw blinds. |
| 9/22 | "If I click BLINDS when there is already at least one BLIND in an open spot, it should ask me if I want to replace all or only the open spots." BLINDS writes exactly what it previewed (`picks`). |
| 9/22 | Flights: Individual Net defaults to an EVEN split, HCP 12.0 break as the option; Skins / Gross default to the bands, EVEN as the option. Then: shared toggle **EVEN \| HCP \| CUSTOM**, drag names between flights, auto-save on FLIGHTS and PAIRINGS — **handed to the flighting lane** (v2.478.x). |
| 9/22 | "It should all be automated if I remove a player from the ROSTER" → pairings drop / reseat with no popup. |
| 9/22 | Transfers get the Apply-Credit price check: difference shown; excess → keep as credit or Venmo back; short → balance-due email with a prepared Venmo link; existing account credit can be applied (checkbox); transferred rows wear the same remaining-balance badges and Venmo/PayPal matching. |
| 9/22 | A +PAY child (balance-due payment) is never a duplicate registration (Pat Youngs DUP). |
| 9/22 | Spin-off: **Tracker Health & Performance** lane = the CTO agent; digest at **5:00 AM Central**; this lane picks up at **5:15 AM** and leaves Kerry a morning brief (decisions first, then updated/improved with versions, then still slow/broken and owner). |
| 9/23 | "Yes, move the GG archive to its own file." (relayed to gg-history / CTO lanes, mailbox #627). |
| 9/23 | RSVP Only → check for credit; if any, run the Apply Credit process with the player's typical choices; short → approve + email the Venmo link; excess → keep as credit or Venmo now with memo. |
| 9/23 | LEADERBOARD → EVENTS: every event, picks up new ones by itself, BETA, **admin + manager**; members still not. |
| 9/23 | Arrow ↓ ↑ + Enter with a visible highlight in every typeahead. |
| 9/23 | Merges: 689→392 (payout shell into Roberto Moreno), Tommy→Thomas Dettmer (504→500), Merchant→Javed (830→831), Michal→Mical Rochford (460→820); Orlando Saenz "Jr" into the suffix field. |

## 2. What shipped (by area)

**Print pack / starter sheet (v2.465.10–2.468.4):** Chromium renders the pack on Railway (libstdc++/zlib on the Nix path — the build lesson is in events.md); engine reported by the bridge; logo host fix; BLIND tag follows the game; mail body carries the sheet's essentials at phone width; printed-at stamp; allowance / off-the-lowest printed in red; off-the-lowest floors at zero.

**Events / roster:** Add Player offers what the event has (games from Event Setup, GAMES OFFERED tables v2.475.0), history prefills tee and typical games; auto-pairings the day before with a lead-days dial; pace on RSVP-only rows; golfers rail average per event; roster→pairings sync is automatic (`_pairings_drop_if_off_roster` inside credit / refund / WD / transfer; the API returns `pairings {removed, reseated, groups}`).

**Money flows:** transfer price check (`transfer_preview`, `transfer_item(excess_action, apply_credit_ids)`, `reverse_credit` restores applied credits and removes the unapplied excess row); credit-transfer predicate shared by JS `isCreditTransferRow` and three SQL sites; RSVP-Only credit offer (v2.487.1): `/api/customers/credit-check`, `_player_usual_selections()` feeds Apply Credit's `previous_selections` (most common holes / games / tee / status over the last 8 real registrations).

**Course identity / proximity:** `_course_hole_table_any` reads a twin's hole card; `merge_course_records`; `_find_course_loose` guards new twins at seed and tee upsert; CTP count sized by entries against the games matrix.

**Blinds:** one seat rule (Cart Net: other cart of the foursome first, rule 15h); dry-run preview + `picks`; keep-or-replace confirm; in-place redraw; routine blinds.

**Performance / health:** whole-field handicap cache (`_HCP_PLAYERS_CACHE`, signature-keyed); pairings GET section stopwatch → handed to the CTO lane, which built `perf.py` / `health.py`; **volume watch** (v2.486.4) after the 9/22 outage (below).

**Leaderboard:** EVENTS tab shows every event with a scorecard (`events_leaderboard_only` is a test-only narrowing dial; the old `events_leaderboard_events` pilot key is ignored), manager-only class + BETA pill, never in `member_mode`.

**UI:** `static/js/typeahead-keys.js` — one capture-phase keydown listener from the shell; finds the open list after the focused input; Enter picks the highlighted row (mousedown → mouseup → click if still open) and pre-empts page "Enter picks first" handlers.

**Customers:** `update_customer_info` now writes `suffix` / `middle_name` to the customers row (v2.487.4).

## 3. The 9/22 outage (8:46–9:12 PM CDT) — read this before touching storage

The 500 MB Railway volume hit 99% (431 MB DB, 368 MB of it `gg_raw_archive`, plus WAL). SQLite could not grow the WAL/shm, every data read raised `disk I/O error`, `/events` returned `{"error":"Internal server error"}`, jobs failed for 3.5 h, `/health` stayed green. Railway had mailed "95% full" on 9/19 twice; the COO filed both at confidence 45. Kerry live-resized the volume to 250 GB (billing is bytes stored). Nothing lost, nothing restored. Guard: `perf.disk_usage()`, VOLUME line + `volume_full` finding (80/90%), `/api/health.volume`.

**The trap that cost 20 minutes:** the repo's `.mcp.json` `tgf-transactions` server is a LOCAL sandbox process with an empty DB. Production is the claude.ai connector (`TGF_Transaction_Tracker` tools). CLAUDE.md now says so.

## 4. Open — carried to the successor

1. **GG archive to its own file** — ruled 9/23, owned by gg-history / CTO lanes (#627). Check the mailbox that one of them claimed it.
2. **Spotlight cold open** — first open builds whole-field standings + handicaps (cached 120 s). Handed to the CTO lane with four asks (#630): instrument, remove the cold cost, answer Kerry's scaling question (2k / 5k players) in plain words, list untimed pages. Kerry is waiting on that answer.
3. **COO classifier**: hosting-provider alerts (Railway capacity) at confidence ≥90, named in the brief until closed (#621; CTO v2.486.5 already raises open ones as HIGH).
4. **Events page polling cadence** (30 s) — Kerry's call, raised by the CTO lane (#623).
5. **scoring-customer-set report** omits suffix in before/after (cosmetic "changed: false").
6. **Same-phone pairs** (Luke Youngs / Isabella Luna; Isaac Escobar / Ismael Garcia) — different people, one phone each is probably wrong; ask Kerry before editing.
7. **Pre-existing red on main** (not this lane): test_rsvp_credit_map.py, test_starting_handicap.py, test_champ_points_live.py, test_flights_custom_ui.js, test_print_pack.py (no PDF engine in sandbox), test_spotlight_winnings.py (fixture lacks `nine_side`).
8. The **5:15 AM Central pick-up routine** must fire into the successor session (see the session prompt, step 1).

## 5. Where things are

- Mailbox posts from this lane this stretch: #607–#611 (health lane birth, 5 AM ruling), #619 (outage), #621 (volume guard + COO ask), #627 (archive ruling), #628 (RSVP credit), #629 (leaderboard), #630 (Spotlight), #631–#632 (identity audit + merges).
- Docs touched: pairings.md, events.md (Games / merges / print pack / FLIGHTS / Credit-Transfer / RSVP credit), member-portal.md (EVENTS leaderboard), schema.md, CLAUDE.md (local-MCP trap, typeahead-keys.js), handoff-2026-09-22-tracker-health.md §7.
- Tests added: test_course_twins.py, test_transfer_price.py, test_blinds_ui.js, test_roster_pairings_sync.js, test_rsvp_add_credit.py, test_rsvp_add_credit_ui.js, test_events_leaderboard_all.py, test_typeahead_keys.js; extended test_health_digest.py, test_customer_rename_cascade.py, test_event_reports.py, test_blind_draws.py, test_pairings_automation.py, test_print_pack.py, test_flights_board.py.
