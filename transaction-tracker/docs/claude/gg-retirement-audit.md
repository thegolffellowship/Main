# GG retirement audit: readers still tied to Golf Genius sources (#1809-2)

Requested by Front Desk 10/19 (Kerry via Tracker Build #2115). Audit only, no code changed.
Scanned: origin/main at v2.574.2 (2026-10-20), `git grep` over `*.py`, templates and static.
Confidence: items marked READ were opened and checked; items marked GREP were found by search only and still need an owner to confirm.

## A. Pairings history off Golf Genius sources (the new audit line)

| # | Reader | Finding | Status | Owner | Suggested fix |
|---|---|---|---|---|---|
| A1 | `database.py` `_pair_history` / solo streaks (~68290) | Reads every `source <> 'app'`; `rode` kept for `gg_teesheet`, `entry`, `se` (READ) | FIXED in v2.574.0 | Tracker Build | none |
| A2 | `cos_reads.py:133` CoS read tool 8 (cart record, solo carts) | `if "gg_teesheet" not in e["sources"]: continue` drops every event not from the tee sheet, so every round since 10/7 is missing from `cart_record` and `solo_carts`; `COUNTED_RULE` text says "Counts Golf Genius rows only" (READ) | STILL OPEN, same bug class | Tracker Build | accept any source in the cart sources (`gg_teesheet`, `entry`); rewrite `COUNTED_RULE`; extend `test_cos_reads.py` with an `entry` event |
| A3 | `_pair_history` "rule 2: Golf Genius owns the event" (`gg_events = src != 'entry'`) | any non-entry row marks the event GG-owned and drops its entry rows. Post-10/7 events have no GG rows so this is harmless today; a pre-10/7 event re-run through entry would be skipped (READ) | latent | Tracker Build | rename to "legacy-owned"; no behavior change needed |
| A4 | `_CART_SOURCES` = (`gg_teesheet`, `entry`, `se`) | no writer inserts `source='se'` into `pairing_history`. The writers are: `app` (sheet save), `gg_teesheet`, `gg_teamnet`, `entry` (closeout), and `import_manual_pairing_groups` (default `source='tee_sheet'`) (READ) | cosmetic for `se` | Tracker Build | drop `'se'` at the next touch |
| A7 | `import_manual_pairing_groups` writes `source='tee_sheet'` (starter sheets / tee sheets, "Kerry's ruled PRIMARY pairing source") | `'tee_sheet'` is NOT in `_CART_SOURCES`, so those rows get `rode=None` (no cart data) in `_pair_history`, and `src != 'entry'` in rule 2 treats them as Golf Genius-owned and drops that event's entry rows. Also not counted by A2's filter (READ the code; whether production has such rows was NOT checked) | possible silent gap for any event paired from a starter sheet | Tracker Build | add `tee_sheet` to the cart sources and to the non-GG list in rule 2; check `scoring-pairings-audit` for rows by source before and after |
| A5 | `closeout_checks.GG_PAIR_SOURCES` shadow compare | correct by design: diffs entered pairs against GG rows when GG rows exist (READ) | keep | Tracker Build | retire after the last pre-cutover event is closed |
| A6 | writers `import_gg_teesheet_round`, `import_gg_teamnet_round` | refused for events on/after the untether date (F3); teamnet import retired (READ) | keep as history | Tracker Build | none |

Not found: any other reader keyed on `source='gg_teesheet'` or `'gg_teamnet'` outside tests.

## B. Other code still reading or calling Golf Genius (GREP unless noted)

| # | Where | What | Disposition | Owner | Suggested fix |
|---|---|---|---|---|---|
| B1 | `insider.py:56-57` and recap templates (`docs/claude/templates/public-recap-template.html`, recaps) | member-facing email links to `tgf-sa/tgf-austin.golfgenius.com/pages/...` ("FULL EVENT RESULTS", "Full fall calendars") (READ) | breaks when GG is switched off; member-facing | Tracker Build + Front Desk (copy) | point to Tracker results and calendar pages; needs Kerry's OK (member-facing, rule 3b) before the 10/31 switch-off |
| B2 | `insider.py:313` reads `gg_game_results` | results for the Insider write-up | verify it falls back to the engine for untethered events | Tracker Build | add a test with a post-10/7 event |
| B3 | `rsvp_parser.py` (mail from noreply@golfgenius.com) | GG RSVPs: kept on by Kerry 10/8 until `gg_rsvps_off`=1 | must be switched at GG shut-off; needs the Tracker RSVP path live first | Kerry decision | flip the setting only on Kerry's word |
| B4 | `golf_genius_sync.py` (login with `GOLF_GENIUS_EMAIL`, roster upload) and the `app.py:1854` teesheet job | pushes data to and pulls from GG | dead after switch-off | Tracker Build | disable the jobs, remove the GG credentials from the environment after Gate 1 |
| B5 | `points_ledger.py` manual captures | read GG public pages for Kerry's comparison; `gg_points_intake` is OFF | retire after the comparison is accepted | Kerry / Tracker Build | none until Kerry says |
| B6 | `gg_game_results`, `gg_game_flights`, `gg_points_standings`, `gg_data_snapshots` readers: `database.py` (leaderboard, GAMES), `tracker_points.py`, `g2a_parity.py`, `gg_freeze.py`, `fin_audit.py` | the pre-10/7 record and the GG-vs-Tracker parity checks | KEEP the data (it is the history); retire `g2a_parity` after Gate 1 | GG Retirement lane | fold these tables into the events/courses step (gg_history FKs); `fin_audit.py` to be confirmed by the CFO lane |
| B7 | `contests.html:5584-5585`, `points-render.js` notes | text saying results are "the recorded Golf Genius result" | correct for pre-10/7 events | none | none |
| B8 | `gg_history.py`, `gg_archive.py`, bridges `scoring-gg-*` | this lane's own tools | stay until Step 4 | GG Retirement lane | none |

## C. What this audit does not cover
- Not read line by line: B2, B6 (`tracker_points.py`, `g2a_parity.py`, `gg_freeze.py`, `fin_audit.py`). Owners should confirm.
- No runtime or data checks (the production database was not queried for this audit).
- Anything outside `*.py`, templates and static (for example the Brevo templates or the website) was not scanned.
