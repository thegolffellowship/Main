# Player Score Entry (Track A, "CTO › Live Score Entry")

**Status 2026-09-25: built on branch `claude/live-score-entry`, NOT on main.**
Rule 3b: Kerry ratifies the se_* schema (including the team row), the
signed link per group, and the screens on his phone before this ships.
Contract: `docs/claude/session-prompt-2026-09-24-live-score-entry.md`.
Mailbox: #654, #655 (directive + standards), #657 (ack + plan), #661 (CA
rulings: rounds plural, Foursomes team row in scope, PH from the lock).

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
                      scores, thru, last_write_at}]}]}
```

Missing holes are absent, not zero. One version per event; poll every
15 s with `since_version`.

## Tests

`test_score_entry.py` — idempotent replay, lock refusal kept in audit,
take-over audit, team row, the read shape, links (tamper / revoke / closed
round), identity, the money-record guard, seeding from PAIRINGS (shotgun
start hole + clock), and the HTTP layer including the flag.
