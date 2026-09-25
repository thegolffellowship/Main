# Player Score Entry (Track A, "CTO › Live Score Entry")

**Status 2026-09-25 (v2.493.0): on main, BEHIND THE FLAG.** Kerry ratified
the se_* schema — #657 + the #661 Foursomes team row + the #666 sign-off,
CTP and HIO rows — on 2026-09-24 ("Yes.", #667), with access by QR/link
(#666 B, cart-sign QR first) and the 9/29 dry run = his group at s9.25
Canyon Springs. CA's four-screen mockup is the approved MVP target (#669).
Members see nothing until the `score_entry_live` app setting is "1" and
Kerry has OK'd the screens on his phone (rule 3b).
Contract: `docs/claude/session-prompt-2026-09-24-live-score-entry.md`.
Mailbox: #654, #655 (directive + standards), #657 (ack + plan), #661 (CA
rulings: rounds plural, Foursomes team row in scope, PH from the lock),
#665.1 (load rehearsal before the 10/2 go/no-go), #666 (Kerry's rulings:
sign-off, access, CTP/HIO), #667 (ratified), #668/#669 (mockup = MVP).

## Rules of record

- **Golf Genius stays the official and money record.** Entered scores feed
  our board and the diff against GG only. No payout, GG, flighting or season
  path reads se_* — `test_score_entry.py` fails if any file but
  `email_parser/score_entry.py` names an se_ table, or if
  `season_payouts.py` / `gg_match_play.py` / `match_play.py` /
  `flighting.py` import the module.
- **customer_id on every row that names a person** (principle 6). A PAIRINGS
  seat with no customer_id is reported (`skipped_no_customer_id`), never
  scored by name.
- **Gross only.** Nothing here computes net or a game. `live_scoring.py`
  and the LSC match engine (`lsc_cup.py`, Track B) read the same rows.
- **Playing handicap is the locked one**, snapshotted at seed time from
  `get_event_print_pack` (the number the starter sheet prints; handicaps.md
  "The handicap lock"). Nobody derives it a second way. On 9-hole Tuesday
  shadows the stroke convention is open (CA Queue #10 / #11): boards show
  gross and net with the note "strokes per GG convention".

## Lock / take-over

One device holds a group (`se_group_locks`). The first device to open the
group with a scorer chosen claims it. A second device sees "<name> is
keeping score" and must press **Take over scoring**; the lock moves and the
audit row keeps both device ids. **There is no timeout** — a dead phone is
replaced by an explicit take-over, never by a clock, so two phones can never
both believe they hold the card. A write from a device that does not hold
the lock is `refused_lock`, and its value is kept in `se_audit.detail` so no
hole is ever lost; the phone tells the scorer so.

## Weak signal

Every hole write is queued on the phone (localStorage `se_queue_<link>`)
with its own `op_id` and sent in order, every 5 s, on `online` and on
return to the tab, until the server acks it. The server is idempotent on
`op_id` (`se_audit.op_id` UNIQUE): a replay returns `dup` and never
re-applies, so an old op can never overwrite a newer value. The header
shows "N holes waiting to send" (amber) until the queue is empty; a
waiting number renders amber, never as saved. Green is not used anywhere
on the page — green means bought in.

## Sign-off, flags, closest to the pin, hole-in-one (Kerry #666)

- **Sign-off.** One scorekeeper; everyone signs his own card at the end
  (`sign_card`, kind `player`), only when the card is complete and no hole
  on it is flagged. The scorekeeper's phone attests the group (kind
  `scorekeeper`). A manager may sign on the player's behalf with a note
  (kind `manager`, admin route). **An edit voids that player's signature
  only** (and the scorekeeper's attestation); re-writing the same value
  voids nothing. Every signature keeps who, device, time and the card
  signed. Beta: unsigned at the 9 PM close-out shows "unsigned" and
  proceeds — GG is the record.
- **Something's wrong.** `flag_hole` records the hole, voids that player's
  signature, and blocks his re-signing until the hole is edited (auto-
  resolves) or a manager resolves it.
- **Closest to the pin.** Par 3s only, answered from the scorekeeper's phone:
  a player (claim) or "No one closer" (never unseats a holder). The latest
  claim is the holder the next group sees; `rule_ctp` is the manager's
  ruling. No distances.
- **Hole-in-one.** A raw 1 opens a claim (`se_hio_claims`); `eligible` is a
  membership term covering the round date (`hio_eligible`), and an
  ineligible player's 1 is a score only. Chain: scorekeeper confirms (lock
  phone) → one OTHER player in the group confirms → manager verifies.
  Changing the 1 withdraws an unverified claim. The staff alert and the
  member-wide blast are NOT built: the alert is a 10/6 item, the blast is a
  Platform requirement, and any member send is rule 3b.
- **Strokes.** `_strokes_by_player` allocates the LOCKED PH on GG's full-
  card setting; on a nine the card says "strokes per GG convention" until
  CA Queue #10/#11 are ruled. A PH the card's stroke indexes cannot carry
  (a nine indexed 1–9) is listed in `strokes._unresolved`, never guessed.

## Access: the cart-sign QR (Kerry #666 B)

The first access path is a QR code on the cart sign: scan, tap your name,
keep score or follow along. A sign carries a code only for the groups the
**`score_entry_qr`** app setting names — `{"<event_id>": "all" | [group
numbers]}` — so the 9/29 dry run can list Kerry's group alone.
`attach_cart_sign_qr(pack)` runs on both cart-sign paths (the page and the
print-pack PDF), seeds the group's round from PAIRINGS the first time
(idempotent), and stamps `score_qr {url, svg}` on the group; the SVG is
inline (segno), so printing needs no network. It never raises: no dial or a
bad dial prints the old sign. The scorecard QR (R7) and the personal email
link (R8, a member send — Kerry OKs each batch) come later; the email link
is the strong identity path, "tap your name" from a shared code is weak and
is accepted for the beta because every action is logged by device.

## Data model (`ensure_score_entry_tables`, lazily created)

```
se_rounds          event_id, round_date, label, holes 9|18, pairings_holes,
                   course_id, status open|closed
se_round_holes     round_id, hole_number, par, stroke_index, yardage
se_groups          round_id, group_num, label, start_hole, tee_time,
                   token_version (bump = revoke the group's link)
se_players         round_id, group_id, customer_id FK, display_name
                   (snapshot label), tee, playing_handicap (locked), seat
se_teams           round_id, group_id, customer_id_a FK, customer_id_b FK
                   — Foursomes: one ball per pair
se_hole_scores     round_id, group_id, subject_key ('c:<cid>' | 't:<team>'),
                   customer_id | team_id (+ team_customer_id_a/_b),
                   hole_number, gross 1-20 or NULL (cleared),
                   entered_by_customer_id, device_id, op_id, client_ts,
                   server_ts; UNIQUE(round, subject, hole)
se_group_locks     group_id, device_id, holder_customer_id, claimed_at,
                   heartbeat_at
se_audit           claim / takeover / write rows; op_id UNIQUE; result
                   ok|refused_lock|invalid; detail keeps the value
se_signoffs        round/group, customer_id FK, kind player|scorekeeper|
                   manager, signed_by_customer_id, device_id, card (JSON
                   snapshot signed), note, at, voided_at, void_reason
se_card_flags      round/group, customer_id FK, hole_number, note,
                   raised_by_customer_id, device_id, at, resolved_at,
                   resolved_by_customer_id, resolution
se_ctp_claims      round/group, hole_number, customer_id FK (NULL = no one
                   closer), kind claim|none|manager, claimed_by_customer_id
se_hio_claims      round/group, customer_id FK, hole_number, eligible,
                   status pending|confirmed|witnessed|verified|rejected|
                   withdrawn, scorekeeper/witness customer_ids, verified_by
se_event_versions  event_id, version (bumps on every accepted write,
                   claim, take-over and build change)
```

## API

| Route | Who | Purpose |
|---|---|---|
| `GET /member/score?t=<link>` | the group | The entry screen (pinless member tier, Nav Shell v2) |
| `GET /api/score-entry/card?t=&device_id=` | link | The group's card, course, scores, lock |
| `POST /api/score-entry/claim` `{t, device_id, customer_id, takeover}` | link | Claim / take over |
| `POST /api/score-entry/write` `{t, device_id, entered_by, ops[]}` | link | Queued hole writes |
| `POST /api/score-entry/sign` `{t, device_id, customer_id, kind?}` | link | Sign own card / scorekeeper attests |
| `POST /api/score-entry/flag` `{t, device_id, customer_id, hole, note?}` | link | Something's wrong |
| `POST /api/score-entry/ctp` `{t, device_id, hole, customer_id|null}` | link | CTP answer |
| `POST /api/score-entry/hio/confirm` `{t, device_id, hio_id, customer_id}` | link | HIO confirmations |
| `POST /api/score-entry/hio/<id>/verify` `{approve?}` | manager+ | Verify / reject |
| `POST /api/score-entry/flags/<id>/resolve` | manager+ | Resolve a flag by hand |
| `POST /api/score-entry/rounds/<id>/ctp` `{hole, customer_id}` | manager+ | CTP ruling |
| `POST /api/score-entry/groups/<id>/sign-for` `{customer_id, note}` | manager+ | Sign on a player's behalf |
| `GET /api/score-entry/events/<id>/scores[?round_id=][&since_version=]` | manager+ | **THE READ** (below); 304 when unchanged |
| `POST /api/score-entry/events/<id>/seed` `{holes}` | admin | Build a round from PAIRINGS (re-run safe) |
| `POST /api/score-entry/rounds` | admin | Build a round by hand (the cup) |
| `POST /api/score-entry/rounds/<id>/course` | admin | Par / SI / yardage |
| `POST /api/score-entry/rounds/<id>/groups` | admin | Upsert a group and its players |
| `POST /api/score-entry/rounds/<id>/teams` | admin | A Foursomes pair |
| `GET /api/score-entry/rounds/<id>/links` | admin | One link per group, for Kerry to hand out. Nothing is sent |
| `POST /api/score-entry/groups/<id>/revoke` | admin | Kill a group's link |

Link routes are **off** (404) until the app setting `score_entry_live` is
`"1"`; an admin session can always use them for the preview.

## The read (CA #661)

`get_entered_scores(event_id, round_id=None)` / the scores route:

```
{event_id, official: false, source: "tgf-entry", version, as_of,
 rounds: [{round_id, date, label, holes, status,
           course:  [{hole, par, stroke_index, yardage}],
           groups:  [{group_id, group_num, label, tee_time, start_hole,
                      scorer_customer_id, lock_state, last_write_at}],
           players: [{customer_id, name, group_id, tee, playing_handicap,
                      scores: {"1": 4, ...}, thru, last_write_at}],
           teams:   [{team_id, group_id, customer_ids: [a, b], label,
                      scores, thru, last_write_at}],
           signoffs: [{customer_id, kind, at}],        # live ones only
           ctp:     {"<par-3 hole>": {customer_id, name, group_num,
                                      by_manager} | null},
           hio:     [{id, customer_id, hole, eligible, status}]}]}
```

Missing holes are absent, not zero. One version per event; poll every
15 s with `since_version`.

## Tests

`test_score_entry.py` — idempotent replay, lock refusal kept in audit,
take-over audit, team row, the read shape, links (tamper / revoke / closed
round), identity, the money-record guard, seeding from PAIRINGS (shotgun
start hole + clock), and the HTTP layer including the flag.

## Load rehearsal (CA #665.1, 2026-09-25)

Staged data only, on this sandbox: the production stack (gunicorn + one
uvicorn worker, SQLite), 14 groups × 4 players on an 18-hole round, each
group writing a hole every N seconds, 60 viewers polling the event read
with `since_version`. Latencies are measured at the client.

| Rate | Writes p95 / max | Reads p95 / max | Errors / refused |
|---|---|---|---|
| Cup rate (hole every 90 s, poll every 15 s) | 20 ms / 20 ms | 14 ms / 125 ms | 0 / 0 |
| 10× | 60 ms / 238 ms | 59 ms / 1.1 s | 0 / 0 |
| 30× | 5.7 s / 5.8 s | 6.6 s / 7.0 s | 0 / 0 |

- The first run, before the read cache, held at cup rate but reached ~4 s
  at 10×: every poll rebuilt the whole payload. The scores route now builds
  **one payload per event version** and every viewer at that version shares
  it (`_SE_READ_CACHE` in app.py).
- 30× saturates the single worker; that is 120 reads/s, far past the cup.
- Not reproduced here: production's host load (load average 89–113 on 48
  CPUs in the health digest) and the scheduler jobs running beside the
  requests. Track B's member board is a separate read and was not measured.

## Portable-SQL rule (CA #682)

The module follows it and `test_score_entry.py` holds it there: no
`COLLATE NOCASE`, no `INSERT OR ...` (upserts are `ON CONFLICT`), ids come
back via `RETURNING`, no try-ALTER. `RETURNING` needs SQLite 3.35+; the
sandbox has 3.45.1. The tables are still created lazily with `CREATE TABLE
IF NOT EXISTS` (once per database), since the repo has no migration-file
convention yet; that goes to CA with the hardening ruling.
