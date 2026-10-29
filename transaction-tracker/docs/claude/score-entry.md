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
  "The handicap lock"). Nobody derives it a second way. Strokes on a nine
  collapse the nine's stroke indexes to 1–9 (Kerry ruled CA Queue #10/#11,
  CA #771: "9 hole events collapse to 1-9 si. So it gets the full 3.").

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
- **The flag says what it should be; approve or deny (v2.531.0, Kerry
  2026-10-09: "Flagged for fix but doesn't say what it should be fixed to.
  Seems like the notification should come thru just for approval and do I
  approve or deny as the manager").** Tapping a hole asks "Hole N shows X.
  What should it be?" with the numbers allowed on that par; the flag is sent
  only with one picked (`flag_hole(..., proposed=)`, table
  `se_flag_proposals`, migration 0009). The scorekeeper's finished card shows
  "Michael says hole 5 should be 3 (card shows 4)" with **Approve 3** /
  **Deny, keep 4**; Live Scoring shows the same pair to the manager.
  `decide_flag(flag_id, approve, device_id/group_id | as_manager)`: approve
  writes the number as an edit does (that hole's signatures void, the flag
  resolves, the pickup mark clears off a non-triple); deny keeps the card and
  tells the player "Hole N stays X (you asked for Y)" until he signs. Only the
  phone holding the card or a manager may decide; a settled flag can't be
  decided twice; both write an `se_audit` `flag_decide` row and the flag's
  `resolution` ("approved by scorekeeper: 4 -> 3"). A flag with no number (an
  old phone) keeps **Fix it** / Clear the flag. Endpoints:
  `POST /api/score-entry/flag/decide` (group link + device) and
  `POST /api/score-entry/flags/<id>/decide` (manager).
- **Reset a submitted TEST card (v2.531.4):** `scoring-se-clear-group:<gid>|apply|checks` also clears the card checks (kept in the `admin_clear` audit row); without `|checks` a submitted card is refused.
- **Closest to the pin / Longest Putt (CA #829, v2.511.1).** Asked ONLY on
  the holes the games matrix plays. `ctp_contests(conn, round_id)` reads the
  one ratified rule the proximity markers print from
  (`database.event_proximity_report`):
  - the matrix at the event's player count decides how many CTPs are funded
    (none below 16 on a nine);
  - the SHORTEST par 3s take them;
  - a slot with no par 3 left is a LONGEST PUTT on the last hole (the phone
    asks "Did anyone in your group hole a long putt?").

**After a clear (v2.532.13, Kerry 10/9: "Make sure all scorecards are cleared and they all land on the starting holes").**
- The card payload carries `cleared_at`, the newest `se_audit` `admin_clear` row for the group.
- The phone drops any queued op whose `client_ts` is at or before `cleared_at`.
- A card cleared while the page is open goes back to its start hole.
- An EMPTY card (no saved scores, nothing queued) ignores the phone's remembered hole and opens on its starting hole.

  Answers come from the scorekeeper's phone: a player (claim), or "No one
  closer" / "No one longer", which never unseats a holder. The latest claim
  is the holder the next group sees. `rule_ctp` is the manager's ruling. No
  distances.

  The card and the read carry each hole's `kind` (`ctp` | `longest_putt`).
  A claim on any other hole is refused. With no course hole card, every par 3
  of the round is asked (source `par3_no_card`). The report is cached for 60
  seconds per event.
- **Hole-in-one.** A raw 1 opens a claim (`se_hio_claims`); `eligible` is a
  membership term covering the round date (`hio_eligible`), and an
  ineligible player's 1 is a score only. Chain: scorekeeper confirms (lock
  phone) → one OTHER player in the group confirms → manager verifies.
  Changing the 1 withdraws an unverified claim. The staff alert and the
  member-wide blast are NOT built: the alert is a 10/6 item, the blast is a
  Platform requirement, and any member send is rule 3b.
- **Strokes.** `_strokes_by_player` allocates the LOCKED PH over the
  round's own holes, re-ranked (`allocate_strokes(mode="subset")`): a nine
  collapses to 1–9, so a 9-hole PH of 3 gets all 3 dots; an 18 uses the
  full 1–18 card (CA #771, v2.503.3). The Team/Cart Net dots use the same
  allocation, and the match engine is handed the same round holes. The old
  "strokes per GG convention" note is gone. A PH that can't be allocated is
  still listed in `strokes._unresolved`, never guessed.

## Preview and admin bridges (v2.493.1)

- `scoring-se-preview:<event_id>|<customer ids>[|apply]` — a labelled
  PREVIEW round (`PREVIEW_LABEL`) with one group, reused on repeat calls,
  never the round `seed_round_from_pairings` builds. Dry run by default.
- `scoring-se-links:<round_id>` — one link per group, for Kerry to hand out.
- `scoring-se-clear-group:<group_id>[|apply]` (v2.528.14, Kerry 10/8) —
  start ONE group's card over: hole scores and marks removed, signatures
  voided, CTP answers removed, HIO claims withdrawn, open flags resolved,
  scorer lock released (the next phone claims it with no take-over). The
  group, its players and its link stay; one `se_audit` row `admin_clear`
  holds every cleared score and the lock holder. Open rounds only; a card
  checked and submitted with a photo is refused. A re-seed (`upsert_group`)
  now also moves a Foursomes pair's `se_teams` row and `t:` scores when both
  players move. Guard `test_se_clear_group.py`.
- `scoring-se-close:<round_id>|apply` — status closed; the links stop
  opening; nothing is deleted.
- While `score_entry_live` is off, a link opens only for an admin session.
- **Score Entry panel on PAIRINGS (v2.507.1, CA #782, Kerry: "before the
  9/29 dry run").** Admin only, under the PAIRINGS toolbar once the pairings
  are saved. It shows:
  - **Seed N-hole score entry** (`POST /api/score-entry/events/<id>/seed`),
    which becomes **Update N-hole groups from pairings** once seeded.
  - Each round's status (OPEN / CLOSED), groups and holes finished.
  - For each group: Open, Copy link, and a **QR** of its link
    (`GET /api/score-entry/groups/<gid>/qr.svg`, admin).
  - **Close round** (`POST /api/score-entry/rounds/<rid>/close`, admin,
    confirm first): the links stop opening; nothing is deleted. A closed
    round offers no seed button, because re-seeding never reopens a round.
  - The members switch and the cart-sign QR switch as read-only chips.
    They stay where they are.
  No new schema. The bridges stay the fallback. Screenshots:
  docs/claude/screenshots/score-entry-2026-09-28-pairings-panel/.

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

**Ties (v2.498.3, Kerry 2026-09-26):** "For Lone Star Cup matches will end
in HALVED if they're tied. But for regular season Match Play, we have rulings
for this." `match_status[].tie_rule` is `halve` for a cup session, `rulings`
otherwise; the phone reads "Halved" vs "All square after N". The rulings
themselves (pool may halve; knockout → extra holes `NH` with pops continuing,
or a putt-off) live in game-engine.md and are NOT yet entered from the phone.
Tee bars are 16 px (Kerry: "twice as wide"); the turn is compact.

**Tee mark standard (v2.498.4, Kerry 2026-09-26):** "Standard for men's
tees is solid color except for white. If shared with women, women's tees are
outlined, while men's are always solid." The card carries each player's
`gender` (customers.gender); the bar/dot is solid for a man (white: dark
outline), outlined for a woman; no gender on file → the legend's own ladies
mark.

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

**Start the preview over (v2.498.1, Kerry 2026-09-26: "reset that scorecard
so I can start over"):** `restart_preview(round_id)` / `POST
/api/score-entry/rounds/<id>/restart-preview` (admin) and a button on each
open PREVIEW round. Never deletes (standing rule): closes the used preview
and opens a fresh one with the same players, holes and demo matches. PREVIEW
rounds only.

**Cart-sign QR (v2.497.0):** "It could just be in one of the corners and
perhaps a little smaller." Top-right corner of each sign, 0.9 in, one line
"Scan to keep score" under it.

## The link lands on two buttons: SCORE THIS GROUP / FOLLOW (v2.525.19)

Kerry 2026-10-07 (CoS #1357-6): the scoring links go on the scorecards and
cart signs as QR codes, "Each group can determine the scorer", and anyone
else who scans must "simply go to the leaderboard and follow along" without
the take-over prompt. Before this a scanned link opened **Who are you?** and
picking a name CLAIMED the group, so a spectator's scan made him the scorer.

- `gateScreen()` in `templates/score_entry.html` renders first for a fresh
  link (`!who && !store.get(K.gate)`): **SCORE THIS GROUP** (sets `K.gate`,
  then the claim flow as built) and **FOLLOW THE CUP** / **FOLLOW THE
  LEADERBOARD** (`location.href`, no claim). A held lock is named on the
  screen ("Fred is already keeping score for this group."). The choice is
  per link per phone, so a scorer reopening his link lands on his card.
- The follow target: a Cup round (any player in `card.matches` with a
  `session`) → `/member/lonestarcup?match=<dial match id>`; the Cup board
  (`lscBoardRender`, contests.html) stamps `data-lsc-match` on each card,
  opens the wanted card once and scrolls to it, and keeps the cards a reader
  has open across its 20 s refresh. A plain event → the scorer's one-event
  board `/member/score/board?t=`.
- **Cup QR signs:** `score_entry.cup_sign_sheets(event_id)` reads the Cup's
  own rounds (`pairings_holes` `lsc:<session>`), one sign per group with
  session, tee time, players, match id and the scorer QR; staff page
  `/events/<id>/cup-signs` (`templates/cup_signs.html`, two per Letter page,
  `?round_id=` narrows). The pairings-based print pack cannot carry three
  sessions' codes, which is why this reads the rounds directly.
- **To the mockups (v2.525.21, `docs/claude/lsc-mockups/` QRLanding /
  WhoAreYou / Held, CoS #1398-A):** the landing carries a THIS GROUP box
  (`.se-this`/`.se-grp`: San Antonio left, Austin right by `card.matches[cid]
  .side`; one list on a plain event), "Group N · Match M · 18 holes" and the
  date as "Oct 10, 2026". **Who are you?** reads "The first person to start
  keeps score for the group." as its sub-line, the handicap / take-over copy
  under the names, and a **Back** pill (`data-act="gate-back"` clears
  `K.gate`). **Held** says how far the holder's card is ("The group's card is
  through hole 7." / "No holes saved yet."), the no-timeout promise, and a
  SAVED SO FAR strip of read-only `.se-cell` divs (the holder's phone owns
  the card; nothing here navigates).
- **The Cup SPLASH (Kerry 2026-10-08, FD #1440/#1442):** a fresh scan of a
  Lone Star Cup link opens on `#se-splash` (inline markup, only when the
  route's `cup_splash` is true: `score_entry.group_is_cup(gid)`, the round's
  `pairings_holes` is `lsc:` or `lscprev:`): the logo centred on the logo's
  own navy `#021A34`, one shimmer sweep (`@keyframes se-shimmer`), ~2 s,
  then a fade to the two-button gate. Tap skips; reduced motion = no shimmer,
  0.7 s; logo load failure = the words LONE STAR CUP 2026 on the plate.
  Fresh scan only: `!who && !K.gate && !following` and not yet shown in this
  tab (`sessionStorage se_splash_<link>`). Ruled flow: splash → gate → Who
  are you?; spectators keep FOLLOW THE CUP.
- Guards: `test_cup_signs.py` (template contract incl. the three screens and
  the splash; the route sets the splash on a Cup link, never on a plain one);
  `test_score_entry_ui.py` clicks the gate before every name and checks the
  held note and the follow target.
- **Four-ball TEAM BALL line (v2.525.20, Kerry #1351 D2):** under the four
  rows on a four-ball hole, `teamBallLine(hole)` shows each side's best net
  ball on this hole from the gross scores as they go in (draft or saved);
  net = gross less that player's own match strokes on the hole, read from
  `match_status[].strokes` (the engine's `detail["strokes"]`, now on the
  card); an X never counts. The Cup board's cards carry `match_id`, which
  is what `?match=` matches on.

## The rules of the page on the Cup hole screens (v2.525.21, Kerry #1398-C)

- **No redundancy:** player rows carry name + tee + PH only; no "vs Name",
  no format prose ("Team · one ball" is gone from a pair's row).
- **TEAM SCORE box** (`teamScoreBox()`) under the rows: the label and the two
  numbers, this session's points. `_cup_standings` adds `session_id`,
  `session_label`, `session_format`, `session_austin` / `session_sa` (and
  `_projected`) summed from the board's own per-match points for the
  session bound to this round. The `.se-cup` strip keeps the overall.
- **HOW IT WORKS** (`hiwPill()`): the orange `.pr-hiw-link` pill under the
  group card, `/member/lonestarcup/info#<fourball|foursomes|singles>`, Cup
  rounds only. Session titles FOURBALL · FOURSOMES · SINGLES (#1397-1).
- Picked-up holes: no new mechanic; v2.496.0 below governs (the mockup's X
  is that mark rendered; the + stepper stops at triple).

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
- **The reload gap (v2.525.12, Kerry 10/6 #1295).** `flush()` drops an
  accepted op from the queue at once, but the card reload lands later. In
  between, `value()` read the hole blank, so an answer tapped in that gap
  went out with `gross: null`, the server refused it ("a pickup mark goes
  only on a triple") and the mark was lost. `flush()` now writes every
  `ok` op's gross (and mark) into the local card before dropping it.
  Intermittent since the start; v2.525.6's slower card read widened the
  gap until `test_score_entry_ui.py` failed on it. Guard: the
  "slow card reload" case there holds every card read for 3 s.
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
- **When each hole was saved** (v2.536.3, read-only): `hole_save_times(round_id)` /
  `scoring-se-hole-times:<round_id>`, the server time (UTC) of every saved hole per
  player or team. The Cup board has no finish times; this is how the clinching match is
  told (Kerry 10/11).
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
inline (segno), so printing needs no network. It never raises: a bad dial
prints the old sign. **Since v2.570.1 (Kerry 10/16: "QR Codes didn't print on
cart signs this week") an event the dial does not name gets EVERY group's
code** whenever live scoring is on for it (auto live scoring never wrote the
dial, so Tuesday's signs printed bare). To leave codes off one event, set its
entry to `"off"`. The scorecard QR (R7) and the personal email
link (R8, a member send — Kerry OKs each batch) come later; the email link
is the strong identity path, "tap your name" from a shared code is weak and
is accepted for the beta because every action is logged by device.

## Chapman (CA #721): one team row, team pops from the match engine

Kerry ratified the cup's alternate-shot session as CHAPMAN (60% low + 40% high).
`ONE_BALL_FORMATS` (`foursomes`, `chapman`, alternate shot) makes one team row per
pair in `_ensure_cup_teams`, so Track B's rename cannot split a pair into two rows.
The team row's pop dots come from the match engine's own per-hole strokes for that
side (`match_status[].card[].s`), key "Team match stroke"; the allowance itself is
Track B's (`lsc_cup.compute_match_detail`).

## Entry stays open after a match is decided (CA #717, 2026-09-26)

Kerry's Lone Star Cup ruling via CA #717: "score entry must stay open after a match
is decided. Don't lock the card or end entry at the close-out; keep taking holes
through the last hole of the round. The board shows the match result as final, and
later holes feed skins only." Verified: nothing in `write_scores`, the lock, the
card or the phone screens reads a match's close-out; it only greys the dead holes in
the match card (labelled "skins only" in the cup). `_match_status` keeps the result
frozen at `closed_at` (the engine's `closed_at_order`). Guards: test_score_entry.py
"CA #717" (holes 6-9 accepted after 5&4, result unchanged, card still held) and
test_score_entry_ui.py (hole 6 keeps its steppers and Save, and saves).

## Play on, the match-won moment, the winner's shimmer, the Cup clinched (v2.535.1, Kerry 2026-10-09)

Kerry: "Players need to be able to continue playing holes even after a match is
determined if there are holes that remain. They can still play for skins even
though match is determined. Match should highlight shimmer in scoring when complete
but should shimmer with chapter color for who won." / "when match ends scorecard
needs to congratulate winner(s) and ask if you want to continue the round (for
skins) or complete and confirm with scorecard" / "When the cup is clinched a pop up
congratulations message needs to pop up on the scorers site to say which chapter
has clinched/retained the cup."

- **Play on.** Unchanged from CA #717 above, re-verified on a phone: after a 4&3
  close-out holes 16-18 keep steppers and Save, save, post, and the card checks and
  submits after 18. A match halved after its last hole is `final` too.
- **Shimmer in the winner's colour.** `matchCard` adds `won` + `lead-austin` /
  `lead-sa` (and `data-result`), or `halved` for a Cup match halved at the end. CSS:
  `.se-mcard.won.lead-austin` / `.lead-sa` (chapter frame, glow, tinted sweep),
  `.se-mcard.halved` (orange-to-slate frame, white sweep); reduced motion stops it.
  The gold `.won` plate stays for non-Cup matches.
- **The match-won moment** (`wonModal`, `#se-mw`): the first render where one of
  this card's Cup matches (`myCupMatches`) is `final`. Scorekeeper only
  (`keeping()`), not after the card is submitted, never over the splash. Words:
  "<First LAST> & <First LAST> win for <CHAPTER>, <margin>" (one player: "wins");
  halved: "Match halved, ½ point each". Buttons: holes left and every Cup match
  decided → Keep playing for skins / Finish and confirm the card; another match on
  the card still live → Keep scoring; no holes left → Check the card. Key
  `se_mwon_<card token[:24]>_<match_id>` is set when it is SHOWN.
- **Finish early.** Finish sets `se_fin_<card>` and opens Check the card;
  `roundOver()` = `allDone()` or (`matchesDecided()` and the flag or a
  `card_check`) drives the screens in place of `allDone()`. Check the card names the
  blank holes and offers "Keep playing for skins instead" (`unfinish`). The submit
  sends `finish_early`; `submit_card` accepts an incomplete card only with it AND
  `card_matches_decided` (every Cup match with a player on the card is final), notes
  "finished after the match was decided" on the attestation and returns
  `finished_early`; `sign_card` lets a player sign such a submitted card.
- **Skins.** `lsc_cup.merge_entry_feed` lists `finished`: players of a submitted
  card (`card_checks`) with fewer holes than the course; `compute_board` adds them
  to the session's `withdrawn` for skins only, so their blank holes hold nothing
  open and the holes they did post still count. Their own blank holes win nothing.
- **Cup clinched.** `_cup_standings` adds `cup: {status, winner, event_id,
  preview}` from the board's `cup_status`; `clinchCheck` hands it to
  `static/js/lsc-clinch.js` (`window.lscClinchPopup`) on every render (the 15 s
  poll). Shown for won / retained only, once per device (`lsc_clinch_seen_<event>`,
  `_preview` for a demo board), never over the splash or the match-won pop-up.
- Guards: `test_lsc_match_won.py`, `test_score_entry_ui.py` (the pop-ups on the
  CA #717 and Cup cards). Screenshots in the scratchpad of the 10/9 lane
  (`mw-modal-fourball.png`, `mw-shimmer-strip.png`, `mw-finish-check.png`,
  `mw-clinch-scoring.png`, `mw-clinch-leaderboard.png`).

## Admin PIN box on the closed page (v2.500.2)

Kerry 2026-09-26: "Yes, add the PIN box." While `score_entry_live` is off, the card
read returns 404 "score entry is not open yet". The page then shows "Live scoring
isn't open to players yet" and a Tracker admin PIN field that posts to the existing
`/api/auth/login` (same PINs, same rate limiter). Only `role == "admin"` reloads the
card; any other PIN is refused on the page. Nothing opens for players.

## Lone Star Cup: foursomes, X, team-colour banners (v2.500.0)

Kerry 2026-09-26: "For Lone Star cup also going to need Team Entries for FOURBALL
and FOURSOMES ... X would also need to be an option for scoring in Lone Star Cup.
... the match position banner needs to be the team color who's in the lead ...
the shimmering banner needs to be color coordinated as well."

- FOURSOMES: `_ensure_cup_teams(group_id)` runs at the top of `get_group_card`.
  For each foursomes cup session (`lsc_matches`, format `foursomes`) bound to the
  round, a pair whose two players are both in this group gets an `se_teams` row via
  `add_team`. Read-first and idempotent. FOUR-BALL stays a row per player.
- X: a cup subject (`card.matches[cid].session != null`) steps from the triple to
  X. X is written as gross = par + 3 with `mark = picked_up`; stepping back or any
  other number sends `mark: null` to clear it. Cup subjects are excluded from
  `needsMark`, so a cup triple is a ball in the hole with no prompt. Regular-season
  (round-level) matches keep Ball in hole / Picked up.
- `_match_status` adds `cup` and `lead_team` (`austin` | `sa` | null). The banner
  takes `lead-austin` (#BF5700) or `lead-sa` (#4B6274); `won` + `lead-*` is the
  champion plate in that colour with the same shine.
- Foursomes pops: a pair's row draws no dots yet (the cup's foursomes allowance is
  50% of the combined difference, computed by the cup engine, not the PH dots).
- Screenshots: `docs/claude/screenshots/score-entry-2026-09-26-cup/`.

## Pops as dots (v2.499.0)

Kerry 2026-09-26: "some way to simply show PH pops at 100% and Team/cart Net pops
on the hole by hole scoring. Don't want it in text necessarily."

- One dot per stroke. Black = the playing handicap at 100% (`card.strokes`,
  unchanged), orange = the team game (`card.team_strokes`, labelled by
  `card.team_game.label`, Cart Net or Team Net). Both are allocated full-card by
  stroke index. A plus handicap draws no dots (a plus comes off the round).
- `se_game_handicaps` (round, customer_id, game='team_net', handicap, unit, basis)
  is the snapshot. `seed_round_from_pairings` copies the starter sheet's
  `team_handicap`, `team_unit` and `team_basis`; `create_preview_round` computes PH
  and the team number with `_preview_handicaps` from the same helpers, the preview
  group as the field. `set_game_handicaps` upserts with ON CONFLICT.
- **A player's strokes fall on HIS tee's stroke index (v2.525.6, Kerry
  2026-10-06 "go now", Tracker Build #1277).** The round's `se_round_holes`
  column is the <50 tee's; `_si_by_band` reads each designated tee's own
  card through `event_tee_legend` + `_ls_tee_holes`, and `_strokes_by_player`
  / `_team_strokes` rank a player whose band has a complete index over that
  (the printed scorecard's `si_own` rule). A band without a complete index
  keeps the round's column; nothing is guessed. Totals never change, only
  which holes carry the strokes (Olympia Hills: Red (L) differs from White on
  8 of 9 holes). Guard: `test_strokes_own_tee.py`. The Side Games engine
  (`live_scoring.game_handicaps`) still allocates over one course index;
  that is its own lane.

## Won-match shimmer and cup standings (v2.498.5)

Kerry 2026-09-26: "If a match is won, then that heading needs to shimmer kind of
like our champion banner on the Points Races. For Lone Star cup, It should also
show an update to the Team Standings."

- A match line with `final` and a `lead_side` gets class `won`: the champion
  plaque look from contests.html (`.tgf-champ-plaque`), cloned as `.se-mline.won`
  with its own `seChampShine` keyframes. Halved and in-progress lines stay plain.
- `get_group_card` returns `cup_standings` from `_cup_standings(round_id)`, which
  reads `lsc_board_payload()` (the board's own numbers, never recomputed) and is
  `None` unless the round is bound to a cup session in `lsc_matches`. The phone
  renders it as the `.se-cup` strip: Austin #BF5700, San Antonio #4B6274, points
  with the live projection beneath, ½ for halves.

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
se_flag_proposals  flag_id PK -> se_card_flags, proposed_gross (1-20): the score a
                   flag asks for (v2.531.0, migration 0009)
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
start hole + clock), and the HTTP layer including the flag. It also holds
the **se_audit append-only guard** (db-claude #2059): no code, score_entry.py
included, may UPDATE / DELETE / REPLACE / DROP se_audit rows.

`test_pace.py` — the pace measure, flags, rebuild, staff read and manager
report (below).

## Pace of play, measured (migration 0037, Kerry 2026-10-19 #2092)

Kerry: "Pace is measured per group but that group number should be an entry
for each player as well" (#2073) and "Yes to both, go ahead - I also want a
pace report sent to the manager ..." (#2092). Measure db-claude #2084,
entry_split #2103, names not group numbers #2096, suggest only #2100.

**The measure** (`compute_round_pace`, all in score_entry.py):
- t[hole] = the group's FIRST accepted save on that hole, from `se_audit`
  (an edit later never moves it; a refused or cleared write is not a save);
  the phone's `client_ts` when within `pace_clock_seconds` of the server
  time, else the server time and flag `clock`. Several players saving the
  same hole: the median of their first saves.
- Holes in PLAY order from `se_groups.start_hole`, wrapping on a shotgun.
- STRAY SAVES (method v2, Database #2261, Kerry's OK 10/26): before the
  median, each player's saves must run forward in play order; the longest
  run that does is kept and the rest dropped (`strays` on the group). The
  case: 10/20 TPC 4:20 PM, two cards saved hole 9 during hole 2, which
  read as 16.9 over 6 adjusted instead of 16.6 over 7 clean.
- A run of gaps under `pace_batch_seconds` (negative gaps included) is a
  catch-up: its holes share the time evenly. Hole 1 saved with hole 2 moves
  the start anchor to the end of that batch; the second-to-last saved with
  the last moves the end anchor before it. The last hole is never used.
- seconds_per_hole = (t[end] - t[start]) / play-order holes between them; a
  missing hole counts as a hole elapsed.
- Flags (status `flagged`: shown, not counted): `few_holes` (under
  `pace_min_holes_9` / `_18`), `long_gap` (a hole over `pace_stop_minutes`
  after spreading), `clock`, `entry_split` (players' saves more than
  `pace_split_seconds` apart on `pace_split_holes` or more span holes),
  `manager_entry` (every span save from a `manager*` / `admin*` device);
  per player `partial` (too few span saves) and `regrouped` (saves in two
  groups; kept in the one with most). Otherwise `adjusted` if any catch-up
  or anchor moved, else `clean`. Clean and adjusted count.
- THREESOMES (method v3, Kerry 10/26: "threesomes are outliers that skew data so don't get configured into standard results"): a group smaller than `pace_standard_group_size` (4) is timed and shown but never in the field median or a player's counted rounds (`standard` 0, `counts` 0).
- Not timed: preview/test rounds, Lone Star Cup / match-play rounds.
- Dials (one app_settings key each, plain integers): `pace_batch_seconds`
  300, `pace_stop_minutes` 35, `pace_clock_seconds` 120, `pace_min_holes_9`
  6, `pace_min_holes_18` 12, `pace_rounds_to_count` 10, `pace_split_seconds`
  120, `pace_split_holes` 3, `pace_standard_group_size` 4.

**Storage**: `se_group_pace` / `se_player_pace` (schema.md), rebuilt by
`rebuild_pace` (dry run default).

**Bridges**: `scoring-se-audit-times:<round_id>` (read-only first saves +
client_ts per group and player/team, with each group's take-over count),
`scoring-pace-rebuild[:<round_id>][|apply]`, `scoring-pace-players[:<cid>]`
(counting rounds, average min/hole and vs field, and the digest line "Pace:
top player N/10 timed rounds" for db-claude's 7:05 digest, #2096; the
Tracker's own daily email has no hook for it), `scoring-pace-report:<event_id>
[|preview|send]`.

**Suggest only** (#2100): `/api/pace/players` (manager+) feeds a small line
under the 1-2-3 pace buttons on the Customers page: "N/10 timed, not used
yet" below the threshold, minutes per hole and "+m:ss vs field" at it. No
suggested 1/2/3; nothing writes `customers.pace_rating`.

**The manager pace report** (`email_parser/pace_report.py`, one per event
round, STAFF ONLY): (a) groups fastest to slowest, each led by the players'
NAMES and the start hole or tee time (the group id never appears), average
min/hole with vs field, total minutes over the measured holes with the hole
count, estimated round time (average x holes), status with the reason; (b)
hole by hole across the counting groups, the three slowest marked, n per
hole, and a reason where a hole has no data; (c) the method line. To the
chapter manager (`pairings_approval.manager_for`), Kerry copied, staff
addresses only (`recap_mail.staff_only`), once per round (message_log
`sent_by='pace_report'`). Job `pace_morning` 6:41 AM Central rebuilds the
tables, then sends yesterday's rounds ONLY when app setting
`pace_report_send` = on (default OFF; Kerry turns it on). The bridge's
`|send` obeys the same dial.

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

## Manager panel on Live Scoring (CA #843, v2.513.5)

The Live Scoring page (`/events/<id>/live-scoring`) and its read
(`admin_overview`) are open to MANAGERS as well as admin. Each round has
a **Manager actions** block with exactly four actions, through the
existing manager routes:
- **settle a CTP / Longest Putt holder** (`rule_ctp`);
- **verify or reject a hole-in-one** (`verify_hio`);
- **sign for a player** (`sign_card` kind `manager`; a note is required,
  and a flagged card is refused and not offered);
- **clear a flag** (`resolve_flag`, with the resolution text).

Every action writes an `se_audit` row in the same transaction: kind
`manager_ctp` | `manager_hio_verify` | `manager_hio_reject` |
`manager_sign` | `manager_flag`, with the actor in `device_id` (`_se_actor`:
role plus chapter, e.g. `manager:San Antonio`). `manager_log(round_id)`
reads the log back, and the panel shows the latest actions.

Seeding and preview restarts stay admin-only; the page hides them from a
manager. Screenshots: `docs/claude/screenshots/score-entry-2026-09-28-manager-panel/`.

## Manager runbook

One page for chapter managers: seed, links and QR, take-over, when a phone
dies, finishing and closing, the paper fallback, and what still needs
Kerry. See `docs/claude/sop/score-entry-manager-runbook.md` (CA #829).

## Entry replay + load harness (CA #800/#801, 2026-09-28)

`tools/se_replay.py --db <SCRATCH.db> --events <ids> --workers 8 --i-am-scratch`
replays each event's GG hole scores through the phone's own HTTP routes on a
SCRATCH copy, 8 groups at once. Per group:
- claim;
- write hole by hole: a lost-ack resend must come back `dup`, and a batch
  dropped mid-send is resent;
- take over on a second phone after hole 6; the stale phone must then be
  `refused_lock`;
- the scorekeeper attests and every player signs.

Then it closes the round and checks every entered hole against the card.
- PASS needs 0 lost and 0 wrong, everyone signed, every group attested, and
  the round closed.
- A GG hole above triple bogey is entered at triple and reported as the named
  class `above_max_triple` (Kerry: "GG is max triple").
- It refuses to run inside Railway, on a production-looking path, or without
  `--i-am-scratch`, and it strips outbound credentials from its environment.

Validated on a synthetic 26-player nine: 234/234 holes checked, 0 lost; p95 118 ms.

## Portable-SQL rule (CA #682)

The module follows it and `test_score_entry.py` holds it there: no
`COLLATE NOCASE`, no `INSERT OR ...` (upserts are `ON CONFLICT`), ids come
back via `RETURNING`, no try-ALTER. `RETURNING` needs SQLite 3.35+; the
sandbox has 3.45.1. The tables are still created lazily with `CREATE TABLE
IF NOT EXISTS` (once per database), since the repo has no migration-file
convention yet; that goes to CA with the hardening ruling.

## Prize money runs itself; a card is final 15 minutes after its last score (v2.562.6, Kerry 2026-10-13)

What Kerry said, verbatim:
- "Payouts need to auto calculate and populate based on GAMES tabs
  immediately after scores are all in"
- "15 minutes after last score entered by each scorer because scorer may
  not finalize how they should"
- "When last hole score is entered by last player in field, won Columns
  should unhide and amounts should show but non-final until 15 minutes
  have passed"

**Final card.**
- `score_entry.card_final_at(last_score_at, complete, unlocked_at,
  minutes)`. Once every hole of every player in the group has a gross,
  the card is final at the later of the group's last `se_hole_scores.server_ts`
  and a manager unlock, plus app setting `se_card_lock_minutes` (default 15).
- Unlocks are stored in app setting `se_card_unlocks` (`{group_id: when}`);
  there is no new table.
- `_group_card_state` gives the state for one group. `get_group_card`
  returns `final` / `final_at` / `lock_minutes`, and `get_entered_scores`
  stamps each group with `final` / `final_at`.
- `write_scores` refuses phone writes to a final card. The result is
  `refused_final`, kept in `se_audit`, and the version is not bumped.
- `POST /api/score-entry/groups/<id>/unlock` (manager) calls `unlock_card`.

**Publish.** `entry_publish.publish_eligibility` publishes a complete card
in any of three cases:
- it is final (no submit or signature needed);
- the old way: submitted or the round closed, and the player signed;
- `rnd["_provisional"]` is set (`publish_event(provisional=True)`). The
  auto-payouts job uses this once the whole field is in.

A complete card that is not final is held with the reason "card final at …".

**Auto payouts** (`email_parser/auto_payouts.py`, job `auto_payouts` every
minute, dial `auto_payouts`). It covers score-entry events of the last 3
days that are untethered from Golf Genius. On each event:
1. A dry run of the publish runs first, so nothing is written while a
   hole is out ("waiting").
2. Once the field is in, it publishes provisionally and assembles the
   payouts with `assemble_event_game_payouts`. The rows, with
   customer_id, become the board PREVIEW (app setting `auto_payouts_preview`):
   `{rows, final, final_at, total, fp}`.
3. `get_event_leaderboard` reads the preview when no payouts are recorded.
   It sets `money_visible` (no 10-minute hold), `money_final` and
   `money_final_at`. contests.html's `evlbFinalNotice` prints the
   "not final yet" note.
4. Once every group is final, it records with
   `record_event_game_payouts(force=True)`, but only while app setting
   `auto_payouts_record` reads `on` AND the event is dated on or after
   app setting `auto_payouts_record_from` (default `2026-10-20`). 10/13
   was display only (CoS #1760/#1761); the dry run matched the recorded
   rows to the cent (#1781), so it goes on for the 10/20 events (CoS
   #1797). With recording off for an event, the state is
   `final_display_only` and the board shows the money as final. That
   state is not sticky: once recording is allowed, the next run records.
   The recording is paid-safe: a re-record never un-pays a paid row.

**One writer; Closeout verifies (CoS #1797, v2.566.0).** From 10/20 this
job is the ONLY thing that records payouts; Closeout no longer presses
Record. It never pays. It does not record while any hold the verifier
relies on is open:
- **card parity** (engine vs saved card, `card_parity`) and **manually
  recorded rows**. Both are refused inside `record_event_game_payouts`,
  the one writer, so every path is held the same way;
- **a closest-to-the-pin takeover the manager has not confirmed**
  (`score_entry.event_ctp_holders` → `needs_confirm`). Before this, the
  hole was dropped from the rows and the rest recorded as if final;
- **a hold placed by the verifier or Kerry**: app setting
  `auto_payouts_hold` `{event_id: {reason, by, at}}`, through
  `auto_payouts.hold` / `release` and the bridge
  `scoring-auto-payouts:hold|<event_id>|<reason>`,
  `scoring-auto-payouts:release|<event_id>`, `scoring-auto-payouts:holds`.
  Rows already recorded stay as they are (pending); release re-checks at
  once.

Every hold reaches Kerry as ONE COO action item `PAYOUTS HELD: <event>`
(deduped by subject); card parity raises its own `SCORING HOLD`. A held or
refused event is re-checked when its cards change (a CTP confirm bumps the
version) and every 15 minutes (`retry_at`), so a fix that does not touch
the cards (a code fix, a manual row removed) still lands. The dry run
reports the same `held` state.

Per-event state lives in app setting `auto_payouts_fp`:
`{fp, v (score-entry version), final, final_at, mins, recorded,
refused | held, retry_at, display_only}`.
An event is not re-run until its version moves, its final time passes,
the lock dial changes, or its retry time comes.

Bridge `scoring-auto-payouts[:apply][|<event_id>]`. Guard
`test_auto_payouts.py`.

## The scoring window and the closeout start (Kerry 2026-10-26)

Kerry (CoS #2307 item 6): live scoring turns on one hour before the first tee
or shotgun and off 15 minutes after the last score is in, per event. Kerry
(CoS #2329 item 5): "I thought I changed it to 15 minutes after last score."
Closeout starts 15 minutes after the last score.

`email_parser/scoring_window.py`. The window gates a player's SAVES only
(`/api/score-entry/write`, non-admin sessions); it does NOT move
`score_entry_events`. That switch (`live_scoring_default.py`, from 5:00 PM the
day before) also puts the Keep score link in the 6:00 AM Event Info email,
the QR codes on the noon cart signs and scorecards, the entered cards on the
boards and the publish of closed cards, all of which must exist outside the
window. So:
- **Opens** at first tee minus `live_scoring_on_minutes` (default 60; the
  first tee from `database._evlb_first_tee`). Before it a save answers 409
  "Scoring opens at 3:08 PM"; the phone keeps the batch in its queue (it
  only drops ops on a 200) and sends it once the window opens.
- **Closes** once every card of the event is final (each card already locks
  15 minutes after its own last score, `se_card_lock_minutes`) and the last
  score is `live_scoring_off_minutes` old (default 15). After that a save
  answers 409 "Scoring has closed for this event". A card still open (a blank
  hole, a no-show) keeps the event open. A manager Unlock reopens the card
  and therefore the event.
- **Fails open**: no first tee, no rounds, any error, or dial
  `scoring_window_auto` = off. Admin sessions are never gated.
- **Closeout start**: closeout is the Event Ops agent routine (the 9:00 PM run
  stays the backstop); the Tracker cannot start an agent session. Job
  `scoring_window` (every 5 minutes, 7:00 AM to 11:55 PM) records
  `closeout_start:<event_id>`, logs agent_action_log `closeout_start`, and
  posts ONE mailbox line (topic `closeout`, TO front-desk and Event Ops)
  "CLOSEOUT START: <event>" once every card is final and the last score is
  `closeout_start_minutes` old (default 15). The routine reads that post. It
  also records `se_event_closed:<event_id>` and logs `live_scoring_closed`.
  Only groups holding a player or a team count (`score_entry.scored_groups`,
  v2.616.0): an EMPTY group never holds scoring-closed or CLOSEOUT START
  (s9.29's "Hole 3B", #2457). Guard `test_empty_group_closeout.py`.
- Read-only bridge `scoring-scoring-window:<event_id>`. Guard
  `test_live_scoring_timing.py`.
- **The closeout chain** (v2.622.0, Kerry 10/29 "Build both now for
  Saturday", #2457 BUILD 1): once CLOSEOUT START is set, every tick runs
  `email_parser/closeout_chain.py` for the event: publish -> final check ->
  payouts recorded -> flights freeze/settle -> pairing history -> handicap
  post (a nine as one round, an 18 as two nines; NO HANDICAPS events
  skipped) -> points rebuild -> pace rebuild -> the night's recap. Each step
  is guarded; a failed step waits for the first 30 minutes (cards and money
  finish on their own minute jobs), then HOLDS that step and every later one
  with one COO item `CLOSEOUT HELD: <event>` and one mailbox post to Event
  Ops; the next tick retries from the held step, done steps never re-run.
  The recap step waits until every Live Scoring event of that date reaches
  it, then `recap_writer.write_and_store` writes the night's recap once
  (`closeout_recap_night:<date>`), staff drafts go out per section
  (`recap_mail.send_recap_draft`), and the 6:00 AM results email is
  scheduled with the stored recap (dial `recap_auto_schedule`, on). A
  writer failure holds the recap step; Event Ops writes it by hand as
  before. State `closeout_chain:<event_id>`; dial `closeout_chain_auto`
  (on); bridge `scoring-closeout-chain:status|run|reset`; guard
  `test_closeout_chain.py`.

## Publishing entered scores (G-0 keystone, CA #786 GO 1)

Kerry's ruling: when a group's card is CLOSED AND SIGNED, its gross scores
are copied into `scoring_rounds` / `scoring_holes` with `source='entry'`; a
GG import may never double it; where both sources exist for one event, keep
both and diff them (the G2a/G2b parity check on 9/29 and 10/6). No new
table. Module: `email_parser/entry_publish.py`. It reads entered scores
only through `score_entry.get_entered_scores` (which now also returns each
round's `course_id`).

**Why two modes.** About a hundred readers of `scoring_rounds` do not filter
on `source`, so an entry row must never sit beside a GG row for the same
event and player.

- **Authoritative**: the event has no non-entry `scoring_rounds` rows AND
  its date is on/after the app setting `entry_record_from` (default
  `2026-10-10`). Eligible players are upserted with
  `gg_aggregate_id = 'entry:<score-entry round id>'`, `source='entry'`,
  customer_id, the customers-table name, event_id, round date, course_id
  (round, else event), tee_id, holes_played, the locked playing handicap,
  gross, net (gross - PH), and one `scoring_holes` row per hole (strokes =
  gross, strokes_received 0; the formula layer derives pops). Re-publishing
  updates the same row; `imported_at` moves only when the card changed.
- **Shadow**: the event has GG rows, or is before the cutover. Nothing is
  written; the result carries `entry_parity`: per player (by customer_id),
  per hole, entered vs GG, players on one side only, totals.

**Eligibility** (`publish_eligibility`, the one place the rule lives): the
round is closed OR the player's group card was submitted (a card check);
AND he holds a live `player` signature (his own or the scorekeeper's for
him); AND every hole of the round has a gross on his own card. Anyone else
is listed as `held` with the reason. A player already published and now
held (an edit voided his signature) is reported as `stale` and left as is
until he signs again. PREVIEW rounds are never published. A player with an
unlinked GG card (event_id NULL) on the same date is held.

**Tee**: a band (`<50`, `50-64`, `65+`, `Forward`) resolves through
`database.event_tee_legend` (the starter sheet's band-to-tee mapping); a
tee name matches the course record by master name (`_gg_tee_parts`). The
concrete row follows `_event_tee_rows`: 18 holes take the legend's row, a
nine takes the row labelled for the side played. An unresolved tee is
published with `tee_id` NULL and reported (handicap posting then skips it
for missing slope/rating, as it does for GG cards).
A tee NAME with no gender mark ("Red") prefers the men's rows, but when
they have no row of the right length it takes the other gender's row of
that name (v2.513.14, 3309: the women's Red nine rows 557 / 2894 beside a
men's 18-hole Red). "Red (L)" pins the women's rows. Guard in
`test_entry_publish.py`.

**Pops (strokes_received)**: each published hole carries the DERIVED
dots: the playing handicap allocated by stroke index under the ruled mode
(`handicap_calc.ruled_allocation_mode`, Kerry CA #771: a nine collapses to
SI 1-9, an 18 uses the full card), the same call the game engine makes.
Stroke index comes from the resolved tee's holes, else the round's own card;
a card with no stroke index for every hole played keeps 0 and is listed in
`dots_unresolved`. Before this every entered hole stored 0, so the handicap
cap, get_scorecard / MVP Stableford and the leaderboard read net = gross
(CA #865/#866/#868). A re-publish with changed dots re-runs the MVP recompute.

**The GG gate**: `import_gg_scorecards` returns `skipped_entry_record` with
a reason, writing no rows, when the resolved event already has entry rows;
per player it skips a card whose owner has an entry row on that date/event
(`skipped_entry_record_players`). The raw GG pages are still archived. The
`scoring-link-rounds` repair refuses to link GG cards into such an event.

**Bridges**: `scoring-entry-publish:<event_id>[|<round_id>][|apply]` (dry
run by default; apply is audited) and `scoring-entry-parity:<event_id>`
(read-only).

**Guard test**: `test_entry_publish.py` (dry run, held players, apply,
idempotency, edit + re-sign, shadow diff, cutover, the GG gate, tee by
band / name / unresolved, and that the module names no score-entry table).

## Seeding by bridge (v2.516.1)

`scoring-se-seed:<event_id>[|9|18][|apply]` is the Seed button without the tap.
With no `apply` it returns `seed_plan`: the groups, each player's tee band and
locked PH, whether a round for that event+holes already exists, and `gaps` naming
any seat with no customer_id, no tee or no PH. It writes nothing. With `apply` it
runs `seed_round_from_pairings` and returns the round id and one link per group.
The member switches (`score_entry_live`, `score_entry_qr`) are never touched.

## Lone Star Cup seeding (v2.517.1, Track B #875/#876)

`scoring-se-cup-seed:<event_id>[|apply]` reads the `lsc_matches` dial and
`lsc_tees`. It makes one round per session (key `pairings_holes = 'lsc:<session id>'`)
and one group per match. A player in two matches in one session (the odd
player's threesome) is one group holding both matches. `se_players.tee` = the
player's `lsc_tees` band; PH = WHS off that tee (`_preview_handicaps`, 18 holes,
locked index). Dry run by default; `gaps` names no tee / no PH / not a customer,
and apply refuses while any player isn't a customer. Track B binds each session's
`se_round` to the returned round id. Seed after Kerry's real pairings are in the
dial; the staged demo should not be applied.

**Singles: one card per tee time** (v2.532.7, Kerry 10/9: "Singles match live
scoring needs to have all four players from the group still in one interface so
one person can score the group even though there's two matches"). In a `singles`
session, matches sharing a `tee_time` share one group (up to 4 players), labelled
"SUN-1 + SUN-2". Players are seated match by match. On the phone, a card that holds
two singles matches boxes each match's pair under "MATCH #" (`teamGroups` in
score_entry.html). Re-seeding a round that was seeded one match per card is
settled by `_settle_regrouped`:
- A group number that now holds different players gets a new link
  (`token_version` + 1; the old QR and link stop working) and its scorer's seat is
  freed.
- A group number past the new count that the moves left with no players, scores,
  marks, teams, sign-offs, flags, claims or checks is dropped.
- A leftover that still holds anything is kept and reported (`leftover_groups_kept`).
- Players' scores move with them (`upsert_group`).

The apply result names `relinked_groups` / `dropped_empty_groups`. After a relink,
reprint that session's QR signs and scorecards. Guard: `test_cup_singles_card.py`.

The G-0 publish dry run (`scoring-entry-publish`) resolves EVERY player's tee,
held or not, and returns `tees: {tee value: {tee_id, players[, why]}}` per round.
Use it to prove tees after seeding, before anyone plays.

## Per-event opt-in (Kerry 2026-09-28)

Score entry is OFF for every event unless its id is in the app setting
`score_entry_events` (JSON list or comma list). Set it with
`scoring-setting-set:score_entry_events|[3304]`. Below admin, every door checks
it: the scorer link routes (`_se_group_from_request`), the Live Scoring page and
read, the scores feed and the four manager actions (`_se_event_gate` in app.py).
The cart-sign QR (`attach_cart_sign_qr`) and the EVENTS page's SCORE ENTRY panel
and Live Scoring button (`SE_EVENTS`, server-rendered) follow it too. Admin
preview is unaffected. `score_entry_live` stays the member switch; both must be
on for a member to score.
Proof on production: `scoring-se-gate-check:<event_id>[|<chapter>]` (read-only)
returns the status codes a chapter manager and a player link get on that event.

## Closest to the pin on the hole screen (v2.605.1, Kerry 10/27)

On a hole with a closest-to-the-pin contest (`card.ctp[hole].kind == "ctp"`, from `ctp_contests`), `ctpBox(hole)` in score_entry.html shows a box under the hole line: "CLOSEST TO THE PIN" and the current holder's name (green), or "No one on the green yet" (grey). Kerry's spec, in order: "Don't put LIVE or Group #", "remove the taken over note", "I don't think it needs the held since either". No distance is measured, so none is shown. The card's 15-second poll keeps it current. Guard `test_follow_sheet.py` (D).

## Links are slot numbers; the round follows the saved pairings (Kerry 2026-09-29)

**The round follows the sheet until first tee (v2.605.0, Kerry 10/27, CoS #2429-2).** Silverhorn 10/27: Kerry's Monday-night consolidation (25 -> 24) took the sheet to groups 1-5 and 7, and the empty "Hole 3B" (group 6) stayed on Live Scoring because a re-seed only dropped groups numbered past the count. Kerry: "That should happen automatically if I've approved it. There was no way to manually delete it." Now:
- `seed_round_from_pairings` drops EVERY group whose number is not on the saved sheet and that holds nothing (`_drop_off_sheet_groups`; a group holding a player, score, mark or claim is kept and reported). A dropped group's printed QR opens "This group isn't on tonight's pairings any more."
- `live_scoring_default.follow_sheet(event_id)` re-derives an existing round from the sheet; app.py's `_follow_sheet_after_save` runs it in a thread after every successful POST/PATCH/PUT/DELETE under `/api/events/<id>/pairings…`, `/api/events/<id>/tee`, and `/api/items/<id>` (+ wd, credit, assign-guest/member). The `live_scoring_auto` job (now every 5 minutes) covers changes made by background jobs (seat-fill, withdrawal fold).
- Nothing re-derives an existing round once first tee has passed (`ensure_live_scoring(..., now)` reports `held`): a group never relinks mid-round. Changes on the course go through the card (+ Player, Player missing).
- se_* reads for this live in score_entry (`round_id_for`, `event_has_round`). Guard `test_follow_sheet.py`.


A group link is the `se_groups` row, and the row is the pairings' GROUP NUMBER, its
place in the list ("slot one and slot two through how many ever slots there are").
It is never matched by the hole or tee-time label: relabelling 2A to 3 keeps the link,
which opens on the new start hole. A new group number gets a new link; a group number
that left the sheet keeps its row and its card answers 410 "This group isn't on
tonight's pairings any more". `upsert_group` moves a moved player's `se_hole_scores` /
`se_hole_marks` rows to his new group; nothing is deleted. `sync_from_pairings(round_id)`
re-seeds an OPEN round seeded from PAIRINGS whenever the saved pairings' fingerprint
(`score_entry_pairings_fp` app setting) differs; it runs when a link's card opens
(`get_group_card`) and when the Live Scoring page / panel reads (`admin_overview`).
(v2.522.0–.2 matched by label first; on 9/29 Kerry's relabel reused "4A" for another
group and slot 7's link opened the wrong group before any score. v2.522.5 fixed it.)


### No member nav on the score-entry page (v2.522.22, Kerry 2026-09-29)

"If players click PLAYERS, LEADERBOARD or HANDICAPS, how will they get back to
the LIVE SCORING? I'd say hide that for now." `score_entry.html` sets
`SHELL_SLIM`, and `_shell_nav.html` then renders the member header with the TGF
mark only, centered and not tappable ("centered TGF Logo on black header for all
screens but don't allow it to link anywhere"): no tabs, no CTA button or sheet.
It shows on every screen, the hole screen included (it used to hide there). The safe-area block in shell.css is untouched.
Other /member pages keep their nav.

The mark is 50 px (v2.522.26, Kerry: "Make the logger bigger. Like 2.5 times"); under 700 px of screen height the hole page shrinks it to 24 px so the card still fits.

### Scorer navigation: SCORING | LEADERBOARD (v2.523.0, Kerry 2026-10-02)

Approved from a real-code mockup rendered at 390×844 (branch
`claude/scorer-nav-mockup`, mailbox #1155 → #1157 → #1158; Kerry: "All looks
good except…", then "go ahead and push this build"). His rulings, verbatim:
"No reason to show BACK TO SCORING if you're already on scoring." / "The
leaderboard that they would go to would be JUST for that event." / "We
originally had a toggle up at the top to go between scoring and leaderboard.
I would prefer that." / "not all toggles for the leaderboard views: OVERALL |
TEAM | NET etc fit on the mobile screen." / "It should just have the event
showing on a top bar and then go straight into the leaderboard toggles,
checkboxes for viewing and leaderboards themselves." / "hide the WON column on
any view until all scores are in. I'd like the names column with the tee color
dots all fit on one row without wrapping."

- **The toggle** (`_shell_nav.html`, `shell.css .se-toggle`): under the mark
  on any page opened with a group link (`?t=`): SCORING | LEADERBOARD, the
  house dark segmented control. Scoring active on `/member/score`; on the
  board page Leaderboard is active and the Scoring segment reads "Hole N"
  from `localStorage.se_live` (written by `render()`, cleared on submit),
  amber with "· N to sync" while holes are saved on the phone but not sent.
  No other member page renders it. The CoS's pinned "Back to scoring" bar
  (#1148) was mocked, shown, and replaced by this on Kerry's word.
  **Pinned (v2.523.1)**: Kerry, "pin to the top as a bar under the header
  and allow scrolling underneath it. I want it to always be visible." The
  nav is `position: sticky`, opaque, with `top` set by the shell script to
  the sticky header's measured height (ResizeObserver, so the tight-card
  shrink is followed).
- **The hole screen's bottom bar**: previous / Save & Go / next sit in
  `.se-bottom`, fixed above the home indicator (#1152: "I do like the bottom
  aligned buttons"). Placement only. The one-screen rule still holds with
  the toggle (`test_scorer_nav.py` measures it).
- **The scorer's board**, `GET /member/score/board?t=<group link>`
  (`score_entry_board_page`): `contests.html` rendered with `SOLO_EVENT` (the
  event's name) and `SOLO_T`; `SHELL_SLIM`; the CTA row, the top tabs and the
  chapter chips carry `hidden`; `#tab=events` is synthesized; `evlbLoad`
  drops every other event, opens his, and fills the event bar
  (`.evlb-solo-bar`: name + IN PLAY / date · final). A bad or closed link
  renders the score page, which explains itself.
- **Reading the board with the link**: `/api/events-leaderboard` and
  `/event` keep the manager tier for sessions and additionally accept a live
  group link (`_board_read_ok`): the list is narrowed to that event and
  another event's board is 403. `get_event_leaderboard` now publishes
  `event.id`. When Tracker Build's member flip (#1149) lands, the role path
  simply widens; the link path stays for scorers who never signed in.
- **Shared-board fixes that ride along** (member Events tab too): the seven
  game tabs wrap to two rows under 560px; `td.nm` is `nowrap` with the tee
  dot absolutely pinned to the cell's right edge (one row per name); while
  `money_visible` is false `evlbBlankMoney` sets `_moneyHeld` and every
  `table.evlb-holes` and the proxies table get `no-won`, which hides the Won
  / $ column until every score is in.
- Guard: `test_scorer_nav.py` (API tier + the screen sequence at 390×844).

### Hole yardage comes from the Men <50 tee (v2.522.27, Kerry 2026-09-29)

"For the yardage under each hole number, use the <50 back tee yardages. 314
seems short." `_event_course_holes` reads par / SI / yardage from the tee the
event's legend (`database.event_tee_legend`) assigns to the `<50` band, via
`_yardage_tee_id`; before, it took the course's newest `course_tees` row, which
could be any tee. No legend → the old fallback. `refresh_round_yardage(round_id,
apply)` / bridge `scoring-se-yardage:<round_id>[|apply]` re-read a seeded
round's yardage column only (par, SI, groups, scores, links untouched).

### The stroke legend (v2.522.27, Kerry 2026-09-29)

`popKey(hole)` in score_entry.html: on the hole screen it keys only the dots
on that hole ("100% Handicap Stroke", "X% Team|Cart Stroke" from
`team_game.pct`, "No Team Strokes on Par 3s") and renders nothing when the
hole has none; it sits below Save & Go. The check card calls `popKey()` with
no hole and keys the whole round. `_basis_pct` reads the allowance out of the
se_game_handicaps basis text.


## Short QR links and own-tee strokes in the engine (v2.525.7, Kerry 2026-10-06)

- **Short QR link.** Kerry: "Are there by chance less dense QR codes that
  could be created as a standard?" Every printed code (scorecards, cart
  signs, the PAIRINGS QR button) carries `short_score_url(url)`:
  `HTTPS://<HOST>/Q/<group>.<version>.<first 12 hex of the signature>`, upper
  case so the QR uses alphanumeric mode (version 3, 29x29, instead of version
  6, 41x41). `GET /Q/<code>` (and `/q/`) -> `resolve_short_code` rebuilds the
  group's CURRENT signed token, compares the 12 hex and the version, runs
  `verify_group_token`, and redirects to `/member/score?t=<token>`; a revoked,
  closed or altered code gets a 404 line. Copy-link URLs stay long.
- **Engine.** `live_scoring.build_cards` honours a player's
  `stroke_index_by_hole` (complete for the round's holes) and writes it on
  his hole rows; `game_handicaps` ranks each card over its own holes
  (`_card_si`), so skins and every per-game allowance follow the player's
  tee. `database.event_engine_state` fills it from each scorecard's `tee_id`
  when it differs from the field's. The phone card's own-tee pops are Track
  A's v2.525.6 (`_si_by_band`).

## One source for strokes, and the engine-vs-card check (v2.564.0, Kerry 2026-10-14)

Kerry 10/14: "Yes, build both before next Tuesday." After s9.27 (10/13) the
saved cards were right and the payout engine was wrong for Dan Stich (net
41 vs 38): the engine worked out his strokes a second time, on the wrong
tee's 18-hole indexes (fixed the same night in v2.563.4, `test_own_tee_nine.py`).

- **One source.** `database.event_engine_state` hands the engine the strokes
  SAVED on every card (`scoring_holes.strokes_received`), entered cards
  included, so payouts and points read the same strokes as the card, the
  handicap post and the MVP. The one exception: an entered card from before
  CA #865 with placeholder zeros (playing handicap 1+ and no stroke on any
  hole) is still derived, and the check below flags it.
- **The check.** `email_parser/card_parity.py` `engine_card_parity(event)`,
  every ENTERED card (GG-era cards carry GG's own dots and are skipped):
  (1) the saved strokes against the rule worked out independently (his own
  tee, the nine he played, `handicap_calc.ruled_dots`); (2) the engine's
  card (`event_engine_state` + `build_cards`) against the saved card, hole
  by hole, gross and net. A card with no holes saved is skipped; a tee with
  no stroke index for a played hole is itself a mismatch.
- **What a difference holds.** `record_event_game_payouts` refuses (the one
  writer: auto payouts, `scoring-record-payouts`, the closeout);
  `closeout_final_check` lists it as blocking (`card_parity` in its output);
  `tracker_points.event_lines` leaves the event out with a `HELD ` warning and
  `rebuild` / `rebuild_monthly` refuse to apply (`refused`), so standings stay
  as they were rather than lose the event's points. Every publish
  (`entry_publish._publish`, applied + changed) runs it and raises one HIGH
  COO item, `SCORING HOLD: engine vs scorecard — <event>`, deduped while open.
- Auto payouts records a refusal and waits for the next card change; after a
  fix that is not a card change (tee data), run `scoring-record-payouts:<event>`.
- Read-only bridge `scoring-card-parity:<event name or id>`. Guard
  `test_card_parity.py`.

## Finding 0: entry mode, the board reads entered scores only (CoS #1333, 2026-10-07)

Kerry (#1313): "audit actual tracker entered scores ... without any importing
from GG. That should have been off." Side Games' true audit (#1315) found the
Events board on Olympia Hills (event 3308) had read Golf Genius imports.

- **Entry mode** (`entry_publish.entry_mode`): score entry is on for the
  event (`score_entry_events`) AND it has a non-PREVIEW score-entry round
  dated TODAY (Central). The live day only: the next day the board reads the
  record again (GG until it retires, published entries after the cutover), so
  a closed event's board never changes after the fact.
- **The board** (`get_event_leaderboard`, so the Events tab, the member
  results and the scorer's LEADERBOARD toggle): in entry mode
  `_entry_mode_overlay` creates TEMP tables `scoring_rounds` /
  `scoring_holes` on the board's connection holding only the live entered
  cards (`entry_publish.live_board_rows`: every entered player, part-played
  cards included, tee resolved and pops allocated by the publisher's own
  rules, over the round's full hole list then cut to the holes played).
  SQLite resolves the unqualified names to TEMP first, so every read in the
  board sees entries and none of the GG import. Nothing is written; the GG
  rows stay stored for parity. Synthetic ids are negative; the team-pops
  helper's second connection reads their tee by tee_id.
- `event.score_source` on the board payload: `entry` or `record`.
- **v2.529.1 (Kerry 10/8, testing Friday's practice round Thursday night:
  "Why isn't the leaderboard showing anything when I've entered scores"):**
  a round dated AFTER today is entry mode too (only a PAST day is frozen to
  the record; nothing official exists for a day not yet played). And the
  events LIST (`get_events_leaderboard`, which the scorer's board reads
  first) now carries a score-entry event in entry mode even with no
  `scoring_rounds` rows (`live_entry: true`; field, last score and
  "in play" measured on the overlay, temp tables dropped after each event).
  Before this an event Golf Genius never scored (the practice round) never
  reached the scorer's board at all.
- **Still to tee off (v2.529.x→2.530.1, Kerry 10/8, "kind of like they do for PGA
  Tour"):** `entry_publish.live_waiting` lists the live day's players with no
  score yet (earliest non-preview round date on/after today; a Foursomes team
  score counts for both), with their group's tee time; `get_event_leaderboard`
  returns it as `waiting` and every board but Team appends them with the tee
  time across the hole columns.
- **CTP can't be skipped (v2.530.5, Kerry 10/9):** `render()` asks any CTP /
  Longest Putt hole that is `holeDone` for the group and not `answered`,
  whatever route left the hole (Save, arrows, card tap, reload). `ctpAsked`
  holds this phone's answers until the next fresh card (an offline answer
  re-asks once the card reloads). 10/6 Olympia Hills: every group answered;
  Tracker CTP winners don't reach payouts/leaderboard yet (GG-only reader).
- **No games, no team pops (v2.529.8, Kerry 10/8):** `_team_strokes`
  returns nothing when the round's event is `database.event_games_off`
  (included-games price $0), and the pairings seed and preview skip
  `set_game_handicaps` for such an event. Only 100% PH pops show. Guard
  `test_se_no_games_pops.py`.
- Not affected: the Lone Star Cup board (`lsc_cup`) already reads entries
  (`get_entered_scores` → `merge_entry_feed`).
- Guard: `test_board_entry_mode.py`.


## Live Scoring ON BY DEFAULT (v2.554.0, Kerry 2026-10-13)

Kerry: "Turn live scoring on for an event should be default after 5:00p
Monday pairings are turned on and definitely prior to these emails being
sent out." This replaces the 9/28 "staff turn an event on; nothing turns one
on by itself" rule for regular events. `email_parser/live_scoring_default.py`:
- `ensure_live_scoring(event_id)` adds the event to `score_entry_events` and
  seeds one round per saved hole set (`seed_round_from_pairings`). It is
  idempotent and never switches anything off. It skips: status not active, no
  saved pairings, Golf Genius era (before `gg_untether_from`), and the Lone Star
  Cup (`lsc_report_context`).
- Job `live_scoring_auto` (app.py, every 15 min, US/Central) runs it for events
  dated today, and for events dated tomorrow from 17:00 Central. Dial
  `live_scoring_auto` (0/off stops the job).
- The event-day email calls it before every preview and send
  (`event_day_email._ensure_scoring`), so every message carries its Keep
  score button.
- Early seeding is safe: rounds re-sync to later pairing saves (the pairings
  fingerprint) and re-seeding never touches a score.
- Guard: `test_live_scoring_default.py`.


## SCORING tab for managers (v2.559.3, Kerry 2026-10-13)

"Can you make the SCORING tab available to Managers under each event?"
- The Events page's SCORING tab (`data-toggle-games="7"`) shows for admin AND manager on any event in `score_entry_events`.
- Managers get the read (`/api/score-entry/events/<id>/admin`, already manager), the copy-link buttons and each group's QR. `/api/score-entry/groups/<id>/qr.svg` is now manager, behind `_se_event_gate("group", ...)`.
- Seed / Update-from-pairings (`/seed`) and Close round stay ADMIN (CA #843); the panel hides those buttons for non-admins.
- Guard: `test_score_entry.py`.

- **v2.559.7, EVENTS list before the first score (Kerry 2026-10-13: "They should show starting when tee times are generated").** `get_events_leaderboard` lists a score-entry event in entry mode (live today or later) as soon as its groups have seated players, even with no score posted (`_entry_mode_overlay` returned `{}`). Field = distinct seated customer_ids across non-preview rounds; money and ranks stay hidden until the field is complete. Guard `test_events_list_pre_score.py`.

## The players' how-to page (v2.561.3, Kerry 2026-10-13)

`/member/live-scoring` is the public, vetted how-to for players: ten steps,
one per slide (Next / back, swipe, `#step-N` deep links) or all on one page.
Kerry: "a slideshow or directions directly on the Tracker that has its own
link that we can send out. So it's fully vetted, locked and can be updated
at any point", "with literal screenshots from a phone that shows correct
fonts". Every word and picture lives in the `steps` list at the top of
`templates/live_scoring_guide.html`; the screenshots are files in
`static/img/live-scoring/` (iPhone size, 390 x 844 at 3x, real Bitter, taken
on a test copy with sample names). When a scoring screen changes, re-shoot
that step and replace its file under the same name. Guard
`test_live_scoring_guide.py`. Known friction it documents: a non-scorekeeper
signs via SCORE THIS GROUP, their name, then Follow along, next to Take over
(Closeout #1739).

Every phone screenshot is one full screen, 780 x 1688, so every phone frame
is the same size (v2.562.1, the test checks it). Step 1 (v2.562.2) shows the
three ways in, each circled in red: the cart sign's QR (`00-cart-sign.jpg`),
the paper scorecard's QR (`00-scorecard.jpg`), and the pairing email's Keep
score on your phone button (`00-email.jpg`). They were rendered from
`cart_signs.html`, `scorecards.html` and `event_day_email.spot_card` /
`scoring_button` with sample names. Re-render them when any of those three
layouts changes.

- **CTP VERIFICATION (v2.562.5, Kerry 2026-10-13, "Yes, build all three after close-out").** At The Quarry, hole 16 went to Dan Stich (group 3) when Pat Youngs (group 6) was closer.
  1. **A stale screen never overwrites a claim.** The phone sends `seen_holder` (the holder it showed) with every CTP answer. If another group has claimed since, `claim_ctp` writes nothing and returns `{stale, holder}` (HTTP 409). The phone shows "X (Group N) claimed this hole while you were playing it" and asks again. A request without `seen_holder` (an old phone) is taken as before.
  2. **The question names the marker:** "Is anyone in your group closer than X's marker?" / "No one closer than X". The copy says not to pick the closest in your own group.
  3. **RETIRED v2.616.0 (Kerry 10/28, #2462-C / #2467-C): no manager confirm, no takeover hold.** The holder is the latest claim by HOLE-SAVE time: `_ctp_current` counts a phone claim at its group's first save of that hole (`_hole_save_at`, se_audit 'write'), so a claim entered or edited later keeps the time the group played the hole; a manager ruling counts at its own time; ties go to the later entry. `ctp_takeover` returns None, so `needs_confirm` is always empty and nothing holds the money. Guard `test_ctp_hole_save_time.py`. The text below is the retired design.
  3a. (retired) **The manager confirms takeovers.** `ctp_takeover(conn, round, hole)` is set when the current holder came from a phone claim that took the hole from a player in another group. A change within the same group, or a manager ruling, is not a takeover. The Live Scoring manager panel shows a "Confirm <name>" button (a manager ruling on the same player) and the hole's claim history (`ctp_history`). `event_ctp_holders` carries `needs_confirm`. Record Payouts (`_tracker_team_and_ctp_rows`) skips an unconfirmed hole with a note, and the EVENTS board shows it as "to be confirmed" with no dollar.
  4. No schema: everything is read from `se_ctp_claims`.
  5. Guards: test_score_entry.py, test_untethered_payouts.py, test_board_phone_ctp.py.

## No-show: the scorer's "Player missing" (Kerry 2026-09-30 #1021, built 10/26 on branches tb5-no-show and tb5-no-show-2)

Kerry 9/30 (ratified, Pairings Spec v1.4 §12.2): "on the first hole there needs to be an obvious red player missing button at the bottom. Then that opens up a prompt of who it is. Then follows up with the three answers" ... "It should ask each hole until after 4 holes and then the player is taken off card." Kerry 10/26 set N for this and for the course notice: "Both should be at 3p", so both default to 3 holes. Event Ops' NO-SHOW SCORER SEQUENCE items 1 to 4 are built; the scorer's side of item 5 is "+ Player" (below), the manager's "Move to..." is not.

- **The button and the questions** (`templates/score_entry.html`): a red "Player missing" button sits above Save & Go in the bottom bar of every hole screen (while anyone else on the card could be missing). It opens "Who's missing?" (this card's players, not the scorer, not a Foursomes pair), then "Is <Name> coming?" with "Running late, keep him on the card" / "No, take him off this card" / "Don't know yet", and, for a player who has already scored a hole, a fourth answer **"Left the course (WD) from this hole"** (Kerry 10/26: "someone could WD due to whatever reason too, having to leave after any number of holes"). "Don't know yet" asks again on each new hole. An absent player gets a red "Off this card (no-show)" box under the rows with **+ Player** to put him back and the line "Blind for Team Net: <name>, holes 1–9". A late / not-here-yet row has a **Here now** button.
- **Who may answer:** `POST /api/score-entry/missing` (`t`, `device_id`, `customer_id`, `answer` late | unknown | absent | present | wd | makeup_yes | makeup_no | makeup_unfinished, `hole`) -> `score_entry.mark_player_missing`. Only the phone holding the group's lock, only for a player on that card, never on a FINAL card (the manager unlocks it first), so a scorer can never take an active player off another card. Every answer is an se_audit row of kind `no_show`.
- **Storage:** `se_no_shows` (migration 0040): one row per round and `customer_id`, `status`, first/last asked hole, `holes_asked`, `marked_by`, `device_id`. **`se_partial_rounds` (migration 0041, a RULE 3b SCHEMA CHANGE that waits on Kerry's OK):** one row per round, `customer_id` and kind: `joined` (put back after his group started; plays from `hole`), `added` (a "+ Player" newcomer or switch, `from_group_id`), `left` (WD; `hole` is the first hole he does not play); `makeup` yes | no | unfinished | NULL. Both tables are also in the score_entry DDL; only score_entry.py touches them (the `test_score_entry.py` guard list includes both).
- **Effective absent** (`_no_show_state`): status `absent`; or `unknown` asked on N different holes; or `unknown` with no score of his own once his group has scored N holes. N = app setting `no_show_absent_after_holes` (default 3, Kerry 10/26).
- **An absent player never holds the night.** `_group_card_state` leaves him out of the card's subjects, so his blank holes don't stop `card_final_at`, auto payouts, closeout checks or card parity. `get_entered_scores` leaves him out of `players` and lists him under each round's `absent`. His holes are never filled with par.
- **BLINDS, by themselves** (Kerry 10/26: "Also need to account for providing a blind, or potentially more blinds for any missing players, based on our blind rules" / "Blinds would happen automatically if a player is removed, correct?"): every answer, every score on a card with a missing or partial player, and the 5-minute `no_show_notice` job call `database.sync_no_show_blinds`. It draws ONE Rule 15 blind per missing seat with the existing per-seat rule (pairings.md 15j) and undoes it when he comes back for those holes or makes them up. An absent player's blind covers every hole; a late arrival's, WD's or newcomer's covers his NOT PLAYED holes (`blind_draw_holes`). No manager tap.
- **LATE ARRIVAL** (Kerry 10/26: "what happens when player shows up on hole 4???"): "+ Player" on the absent box, or **Here now** on a late / not-here-yet row, on hole H after his group has started records `joined` at H (`partial_rounds`). The holes before H in the group's play order are **NOT PLAYED**: never par, never holding the card, shown on the phone as a plain "Not played" line under "Joined on hole 4 · Blind Sam plays 1–3". Before the group has scored a hole, + Player is "back for the whole round" and the blind is undone.
- **MAKE-UP HOLES** (Kerry 10/26: "Player late arrival needs to ask if that player will make up missed holes at end of regular scoring, which is always allowed if there's light", then "The late arrival should only ask that about missed holes after the original 9 are finished for other players, not right when he arrives"): `ask_makeup` is raised only once every other non-absent player on the card has a gross on every hole (`_regular_done`); until then the missed holes just show as missed. Once raised, the card holds until the scorer answers "Will Ned make up holes 1–3?". **Yes** (`makeup_yes`) opens them for entry after the last regular hole and the card waits for them (the blind keeps covering each until he enters it; a made-up round is complete and counts for everything). **No** (`makeup_no`) makes them final as not played. During make-up, "<Name> couldn't finish the make-up holes" (`makeup_unfinished`) makes the rest not played. A WD is never asked (he left).
- **WD** ("Left the course (WD) from this hole" on hole H): his holes played stand; H and after (those with no gross) are NOT PLAYED and never hold the card; a blind covers them; the course notice counts him as having left. "+ Player" on him later deletes the WD (he plays on).
- **"+ PLAYER" FOR SOMEONE ELSE** (Kerry 10/26: "Could also be there for a threesome as a standard, for someone we add last second or switches from another group last second"): on a card with fewer than 4 players or with a no-show (`card.can_add`), "+ Player: add or move someone onto this card" opens `GET /api/score-entry/add-choices` (`score_entry.add_choices`: roster players on no card of the round; players on another card of the round, Foursomes pairs excluded) and `POST /api/score-entry/add-player` (`add_player_to_card`: the lock holder only; never onto or from a final card).
  - A **switch** moves his `se_players` row and carries his `se_hole_scores` / `se_hole_marks` / HIO / no-show rows with him. Scores are unique per round and player, so the two cards can never both hold a score for him on one hole. His signatures are voided.
  - The **pairings follow** with ONE targeted write (`database.move_pairing_seat`, never a full save mid-round): the first free seat of the card's group. An add inserts an `event_pairings` row. The seat a switch leaves is an open seat and gets its Rule 15 blind at once (`draw_one_blind`). An open-seat blind on the seat he takes goes when he plays from the first hole. If the card's group is not on the saved PAIRINGS the response says so and the sheet is left alone (flagged, not guessed).
  - After his new group has started he is `added` at the current hole (late-arrival rules and the make-up question). A newcomer on a card with an absent player FILLS that seat: the absent player's blind keeps only the holes before the newcomer joined.
- **What an INCOMPLETE round plays** (a card with NOT PLAYED holes). Kerry 10/26: "For a lack of holes played, a player cannot compete in Individual Net or Individual Gross, but could still compete in Skins, MVP, and CTPs. Team Net is probably the biggest question." / "His ball on holes played, blind on the rest" / "A short round should still count toward points races, but not towards a handicap." One setting per game, `score_entry.INCOMPLETE_ROUND_GAMES`:
  - individual_net OUT, individual_gross OUT (ruled);
  - skins IN on the holes he played (ruled); a hole he did not play never holds a skin open;
  - mvp IN (ruled): net Stableford over the holes he played. His strokes fall where the card's allocation put them over the full round, so a pop on a missed hole is lost; the plus comes off the round; his NOT PLAYED holes are final at zero and never leave the MVP waiting;
  - ctp IN (ruled);
  - points IN (ruled): the engine's net Stableford on the holes he played, floored at 0 (`tracker_points.event_lines`);
  - handicap_round OUT (ruled).
  - Team / Cart Net: `TEAM_NET_INCOMPLETE_ROUND` = `own_ball_and_blind` (RULED: his ball on the holes he played, the blind's on the rest) or `blind_whole_round`.
  - Because the handicap round is out, an incomplete round is **never published** into scoring_rounds: `entry_publish` lists it under `incomplete_round`, never `held`, so it does not stop the money. Skins, MVP, points and Team Net read his entered card instead (`event_engine_state` adds it, flagged `incomplete_round`; `_partial_round_mvp_entrants` feeds the recorded City MVP; the board and the field check skip his NOT PLAYED holes). The closeout names him as a warning, not a blocker.
- **Only what he paid into** (Kerry 10/26, CoS #2375: "Late arrivals of course is only eligible for what he's paid into or what's already included with his entry, in addition to the restrictions for not being eligible in the invidual net or gross due to incomplete scorecard"): a short round plays a game only when the game's buyer list says he bought it, exactly as for anyone (`_event_game_buyers`: Skins and Individual Gross = gross buyers, MVP and Individual Net = net buyers; Team / Cart Net and CTP come with the entry). `INCOMPLETE_ROUND_GAMES` only takes games away on top of that (Individual Net / Gross). Guarded in `test_no_show.py`.
- **Paying a winning team's shared slot** (Kerry 10/26: "But the question is how you pay it out if the team wins?", then RULED: "Split by holes is good - So that player's share is prorated between two players."): `score_entry.TEAM_SLOT_PAYOUT` = `pro_rata` (the ruled default): the slot's equal share is split between the player and his blind by holes covered, to the cent (`database.team_slot_weights` + `split_weighted_cents`; the parts add up exactly). `player` / `blind` give the whole slot to one. A no-show who covered no hole gives his blind the whole slot in every mode. One slot is never paid twice. Example: a $92 team purse is 4 slots of $23.00; Lou joined on hole 4 (6 holes) and the blind played 1–3: Lou $15.33, the blind $7.67.
- **The phone:** an absent player has no row; a late or not-here-yet player keeps his row (meta "Running late" / "Not here yet" with Here now), and his blank hole doesn't stop the scorer moving on. The server still holds the card until a late player's holes are in, or he is taken off or put back.
- **Not built:** the manager's "Move to..." on the Live Scoring page. Holes an absent player DID play before being taken off leave the feed with him (WD is the answer for a player who leaves). The day-after board reads the record, where a short round is not published, so a past board's Team Net shows his slot from the blind's holes only (the money was recorded on the day from the entered cards).
- **The course notice:** see events.md "Course no-show notice".
- Screens: sequence `no-show` (11 steps, rendered from the real page and card on a throwaway round, `screens_capture._ns_seed` / `_r_no_show`). Guard `test_no_show.py`.


### More than one player missing (Kerry 10/26, v2.603.1)

Kerry: "What if multiple people are missing? Can I tap all that are missing?" Who's missing? is a multi-pick: the scorer taps every player who isn't here, then Next (N missing) asks Is <Name> coming? for each, in turn; the answers post one after another (`/api/score-entry/missing` per player), then one reload. Each absent player gets his own Rule 15 blind (`sync_no_show_blinds`).
