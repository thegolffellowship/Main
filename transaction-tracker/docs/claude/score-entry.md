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
  On the sign screen (v2.493.6) every number on the player's OWN row is a
  button, underlined: tap it and the screen asks "Hole N shows X. Is that
  wrong?" with Flag hole N / Cancel, it's right. "Something's wrong" does
  the same with the row outlined. Kerry, 2026-09-25, on the old screen:
  "So are you saying I can tap a hole on that summary scorecard to change
  it? Because that's not obvious." A player flags; only the scorekeeper
  changes a score (from Check the card, tap a number).
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

## Preview and admin bridges (v2.493.1)

- `scoring-se-preview:<event_id>|<customer ids>[|apply]` — a labelled
  PREVIEW round (`PREVIEW_LABEL`) with one group, reused on repeat calls,
  never the round `seed_round_from_pairings` builds. Dry run by default.
- `scoring-se-links:<round_id>` — one link per group, for Kerry to hand out.
- `scoring-se-close:<round_id>|apply` — status closed; the links stop
  opening; nothing is deleted.
- While `score_entry_live` is off, a link opens only for an admin session.
- **Proposed, not built (scope → CA):** a "Score entry" panel on the event's
  PAIRINGS view — Seed from pairings, each group's link and QR, round status
  and a Close button — so Kerry never needs a bridge.

## Tee colour bar (v2.493.5)

Kerry, 2026-09-25: "Show a color bar on left side of name blocks for each
hole that are the color of player tees that would match tee sheets." The
group card carries `tees` = `_tee_legend(event)`, a view of
`database.event_tee_legend` (the starter-sheet / print-pack legend, no
second colour map), keyed by band; a player's `se_players.tee` is his band.
Hole, turn and review rows get a left bar; the read-only and sign-off cards
get a dot. Light tees (white, yellow) get a dark outline; the women's tee
(`ring`) is an outline; no tee on file → neutral grey. The PREVIEW round's
players carry no tee (no PAIRINGS behind it), so its bars are grey.

## Check the card, photo, submit (v2.495.0)

Kerry, 2026-09-25, on how a round ends: a printed scorecard is kept beside
the live one, "both scorers compare at the end of the round. The print card
is tossed away then." He picked option A of three mockups
(`docs/claude/mockups/card-check-*.png`): "A is what is most like what the
paper is and order will be exactly the same. plus its how GG works so
there'll be familiarity." With: "Add toggle for FRONT | BACK for 18s ... so
row of replacement scores is right under the 9 being edited", "Reduce text
above the card ... or put a ? in a circle for help", and on totals: "Not
totals first. Hole by hole. Totals should be there too, but the print
scorer will not have totals generally." The photo: "The live scorer with the
phone is prompted to take a pic that is stored on record, and scorer is
prompted to enter that person's name as well." And: "Dry run, scorekeeper
signs for group."

1. **Check the card** (`hole = "review"`, replaces v2.493.4's "Every hole is
   in"). Once every hole is saved: players down, holes across, one nine at a
   time (FRONT | BACK on an 18, OUT / IN and TOT), every number a button.
   A tap opens the score row (1..par+3, 2..par+3 on a par 5) directly under
   the card; a pick writes through the normal queue and the cell stays
   marked yellow. Help text lives behind the ? circle. Totals under the
   card. One primary action: **Card matches paper**.
2. **Photo of the paper card.** The camera (file input, `capture=
   environment`); the phone shrinks the picture to 1600 px on the long side,
   JPEG 0.7 (~300 KB) and keeps it in localStorage until the server has it.
   **Who kept the paper card?** A chip per group player (customer_id) or
   "Someone else" with a typed name. "Can't take a photo?" allows a submit
   without one.
3. **Submit card** (`submit_card`): scorekeeper's phone only, every card
   complete. Attests the group (kind `scorekeeper`, note "card matches
   paper"), writes one `se_card_checks` row, and when the event's dial is on
   signs every player's card for him: kind `player`, `signed_by_customer_id`
   = the scorekeeper, note "signed for the group by the scorekeeper". It
   never signs over a player's OWN signature or an open flag. Then the photo
   uploads (`attach_card_photo`, idempotent on `photo_op_id`, retried every
   5 s from the phone), stored as a file at
   `<db dir>/se_photos/<event>/check-<id>.jpg`, never as a blob.
4. **Players.** A player whose card was signed for him sees "Kerry signed
   your card for the group" and can still tap a number on his row to flag
   it; the flag voids the signature made for him, exactly as it voids his
   own. A reload of a submitted card lands on the finished card.

**The dial:** app setting `score_entry_keeper_signs` = `{"<event_id>":
true}`; default off. Set it with `scoring-se-keeper-signs:<event_id>|on|off`
or `POST /api/score-entry/events/<id>/keeper-signs {on}` (manager+). The
photo: `GET /api/score-entry/checks/<id>/photo.jpg` (manager+). Guards:
`test_score_entry.py` (submit / dial / photo) and `test_score_entry_ui.py`.

## Kerry's preview notes, 2026-09-26 (v2.498.0)

- **The turn:** each player's nine under his name, every hole tappable to
  edit (`goto`), plus **Back to hole 9**.
- **One column grid:** every card table is `table-layout: fixed` with one
  `colgroup` (name, 9 holes, OUT/IN, TOT); an 18's front nine keeps a blank
  TOT column so FRONT and BACK line up; Your Card's two blocks align. Check
  the card shows the last name under the first. Your own row on Your Card:
  stronger tint (#FDEBDD) and an orange edge.
- **Match standing:** `get_group_card` carries `match_status` (from
  `_match_status`: `lsc_cup.compute_match_detail` over the round's scores,
  locked PHs and pickup marks; a cup session's `n_holes` is honoured) —
  shown on the hole screen, the turn, Check the card and the finished card.
- **A change after submit:** the scorekeeper's finished card lists open
  flags with **Fix it** (opens Check the card on that number); **Change a
  score** replaces "Back to the holes". Change → Card matches paper →
  Submit again; the edit resolves the flag and the submit re-signs.

## Live Scoring in the Tracker (v2.497.0)

Kerry, 2026-09-26: "How will I access this thru the Tracker so I can see the
preview?" The event's PAIRINGS toolbar has a **Live Scoring** button (admin)
that opens `/events/<id>/live-scoring` (`templates/score_entry_admin.html`,
data from `GET /api/score-entry/events/<id>/admin` → `admin_overview`):
every round (PREVIEW flagged), each group's players (✓ when signed), holes
in, the scorer, the card check (Submitted + photo link), and **Open** /
**Copy link** per group. The switches are shown: open to members
(`score_entry_live`), scorekeeper signs for the group (toggle), the cart-sign
QR groups; and **Build the round from PAIRINGS** (9 | 18, re-run safe).

**Cart-sign QR (v2.497.0):** "It could just be in one of the corners and
perhaps a little smaller." Top-right corner of each sign, 0.9 in, one line
"Scan to keep score" under it.

## Match play: Ball in hole or Picked up (v2.496.0)

Kerry, 2026-09-25 (via the Front Desk), verbatim: "The only possible
differentiation is in match play. If triple is entered for match play, a
prompt needs to be for BALL IN HOLE or PICKED UP. If ball in hole then
handicap pops apply for the the match. If ball picked up or over 7, then
that player cannot win the hole. If both players/teams in a match had to
pick up or are over max, then neither team/player wins the hole and the
hole is simply a push, though it's still entered as a triple. It would
receive some type of highlight or mark in a match. Probably scorecard also
needs to recognize that there IS a match going on for the players that
there is one in, like some type of symbol or note." And on "Something's
wrong" above triple: "It should notify the player that the maximum allowed
is Triple".

- **Who has a match.** `round_matches(round_id)` reads the Lone Star Cup
  dial (`lsc_matches`, Track B): a session bound to this round by
  `se_round`. The card carries `matches` ({cid: match_id, format, side,
  partners, opponents}); each such player wears an **M** and "Match vs …"
  on every screen. No bound session = stroke play, nothing changes.
- **The prompt.** When a match player is saved at par + 3 (hole screen or
  the check card) and has no mark, the phone asks **Ball in hole / Picked
  up** for him before moving on (help behind the ?). The answer rides the
  normal write as `op.mark` (`holed` | `picked_up`), so it queues offline
  and is idempotent on op_id. The card still records the triple.
- **Storage.** `se_hole_marks` (one per round + subject + hole, with
  customer_id or team_id). A mark only goes on the triple (`invalid`
  otherwise); a write without `mark` keeps it; moving the gross off the
  triple clears it. A mark does not void signatures (the card is
  unchanged).
- **The read.** `get_entered_scores` players[] and teams[] carry
  `marks: {"<hole>": "picked_up" | "holed"}`; `get_group_card` carries
  `marks: {subject_key: {hole: mark}}`.
- **The match result** is Track B's engine (`lsc_cup.compute_match_detail`,
  new `marks=` argument, fed by `merge_entry_feed`): a picked-up ball
  cannot win the hole (a four-ball partner still plays); both sides picked
  up = a push (`winner 0`); ball in hole keeps the pops. Hole rows carry
  `p1_picked_up` / `p2_picked_up` for the match card's highlight. Guards:
  `tests/test_lsc_cup.py` (six new cases) and `test_score_entry.py` (end to
  end through `lsc_board_payload`).
- **The notice.** Pressing + past the max, the check picker, and the
  "Something's wrong" box all say "Maximum allowed is triple bogey (N)."
  (for a match player: "enter N, then mark it Picked up").
- Screenshots: `docs/claude/screenshots/score-entry-2026-09-25-match-pickup/`.
- **Round-level matches (v2.496.1).** Besides the cup dial, `round_matches`
  reads app setting `score_entry_matches` ({"<round_id>": [{"id", "format",
  "sides": [[cid], [cid]]}]}; `set_round_matches`). Today it binds the
  preview's demo match (`scoring-se-preview:<event>|<cids>|apply|18|match`);
  it is also the place a non-cup match would bind. Read the state with
  `scoring-se-status:<event>`.
- **Help and the paper card (v2.496.1, Kerry 2026-09-26).** Help is the How
  It Works pill (orange, white Bitter capitals, as `.pr-hiw-link`). "Who kept
  the paper card?" offers **Me**; picking it shows "Next time, please have
  one person keep the paper card and another Live Scoring."
- **Names in Bitter (v2.496.2, Kerry 2026-09-26):** "I'd like to use the
  Bitters text for names on the display." Every player name on every
  score-entry screen; numbers stay sans.

## Max Triple, and no ace on a par 5 (v2.493.3)

Kerry, 2026-09-25: "We do Max Triple, so it can't be more than that. Also,
hole in ones wouldn't be possible on Par 5s." `gross_bounds(par)` is the one
rule: lowest 1 (2 on a par 5), highest par + 3; a hole with no par keeps
1–20. The phone's stepper clamps to it and `write_scores` refuses anything
outside it (`invalid`, "max triple" in the reason). A 1 on a par 3 or par 4
still opens the hole-in-one flow.

**Ruled (Kerry, 2026-09-25): "GG is max triple; pickups enter triple."**
Golf Genius caps the same way, so a capped hole is not a GG difference, and
a picked-up or unfinished hole is entered as triple with no separate mark.
A player can't have a real score above triple, so a flag never needs to
carry one.
- WHS posting uses net double bogey, not Max Triple; nothing here posts
  handicap rounds, so this cap never reaches a differential.

## 18 holes (v2.493.2)

- The card strip shows every hole in play order, nine to a row; a shotgun
  group on 10 runs 10–18 then 1–9.
- **The turn:** after the ninth hole played on an 18, the scorekeeper sees
  each player's first-nine total against par, then "Go to hole N". Not in
  CA's mockup; added because Kerry asked to see the front total and it is
  the natural pause on a paper card.
- **The card:** OUT (1–9) and IN (10–18) + TOTAL blocks, not one 20-column
  table. A nine keeps one block.
- Stroke notes use the 18-hole stroke indexes on GG's full-card setting.

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
se_hole_marks      round/group, subject_key, customer_id FK | team_id,
                   hole_number, mark holed|picked_up (only at the triple),
                   entered_by_customer_id, device_id, op_id, at;
                   UNIQUE(round, subject, hole)
se_card_checks     round/group, scorekeeper_customer_id FK,
                   print_scorer_customer_id FK | print_scorer_name (only
                   when not a group player), signed_for_group, photo_op_id
                   UNIQUE, photo_path (file beside the DB), photo_bytes,
                   photo_at, device_id, at — one row per submit
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
| `POST /api/score-entry/submit` `{t, device_id, keeper, print_scorer_customer_id | print_scorer_name, photo_op_id?}` | link | Card matches paper → submit (attest, and sign for the group when the dial is on) |
| `POST /api/score-entry/photo` `{t, device_id, photo_op_id, image}` | link | The paper card's photo (JPEG data URL), after the submit |
| `GET /api/score-entry/checks/<id>/photo.jpg` | manager+ | The kept photo |
| `POST /api/score-entry/events/<id>/keeper-signs` `{on}` | manager+ | The keeper-signs dial |
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
