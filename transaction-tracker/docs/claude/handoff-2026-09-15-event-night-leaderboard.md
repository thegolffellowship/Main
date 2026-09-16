# Session record — 2026-09-15 event night, v2.437.0 → v2.456.0

**Lane:** tracker-claude "TGF Tracker Improvements" · branch
`claude/tracker-improvements-h7q2ns` · all 25 commits merged to `main`
and live on Railway.
**Events in play:** s9.23 The Quarry (San Antonio, 5:00 PM shotgun, 21
players) and a9.23 Avery Ranch (Austin, 4:57 PM tee times, 12 players).
Most of this was built WHILE the rounds were being played, from Kerry
watching the live board on his phone at the course.
**Mailbox:** #508–#522 are this session's posts. #522 covers through
v2.442.0 only; the digest for v2.443.0–v2.456.0 is post #523.

---

## 1. The night's arc

Kerry issued short sequential directives, each one shipped and verified
live before the next. They fall into six groups:

1. Auto-removal of credited/WD players from the sheet, and BLINDs.
2. Money and winner holds — nothing pays until every hole is in.
3. Leaderboard display — tee colour, ordering, all holes, live skins,
   team handicap, team cards.
4. Starter sheet — tee circles, NEW/1T badges, legend wording.
5. The plus-handicap MVP rule.
6. Golf Genius data corrections and the payouts they invalidated.

Then, after play: Apple Pay, the one-modal Mark Paid, and the
handicap-card accounting that could not add up.

---

## 2. Rule 15 — a credited player leaves the sheet, and a BLIND fills the seat

**Kerry, 2026-09-15 (verbatim):** *"Found out after play started that
Will Wallace wasn't able to make it… He should automatically be removed
from the pairings when that happens unless you strongly suggest
otherwise… for any open spots like this, BLIND's from the field of
Members with established handicaps only, should be added into those
slots. I've already added for the previously open spots but not for
Will's. Blind's should be auto generated based off of a history of who's
been blinds too, so there's even distribution of who gets the benefit of
being a blind for Team Net over the course of a year."*

### 15a — auto-removal (v2.438.0)

A yes/no popup already existed on exactly two front-end paths (the
credit modal and the WD modal) — which was the whole problem. The same
money action taken from the roster tab, the customer page, the MCP
bridge or a bulk fix left the sheet stale, and the amber "Not on the
roster" banner was the only thing that noticed.

The check moved to the boundary: `_pairings_drop_if_off_roster(item_id,
reason, event_name=None, db_path=None)` in `database.py`, called from
`credit_item`, `refund_item`, `wd_item` and `transfer_item`. It only
fires when the player has **no active row left on that event** — a
partial credit, a package downgrade, or one of two spots refunded leaves
the seat alone.

`remove_player_from_pairings(event_id, player_name, dry_run=False,
reseat=None, db_path=None)` does the removal. `reseat=None` asks
`_event_started(ev, now=None)`: **before the gun the group re-seats;
after the gun the seat stays open** so the sheet still matches the paper
in the carts. `_event_started` uses `now_central()` — a past date counts
as started, today with no time counts as started.

### 15b — the clock

`_event_started` and the client's `tgfToday()` both work in Central.
See §7.

### 15c — what a blind is

A blind is a **Team Net placeholder**: a real member, not playing, whose
posted TGF handicap and a par-plus-handicap score stand in for an empty
seat so the cart still has a Team Net entry. It is a benefit — the seat
gets a free contribution — which is why the distribution has to be even.

### 15d — eligibility and draw order

Eligible = `current_player_status IN ('active_member','member_plus')`
AND an established index (`_established_index_by_customer`). **Not
eligible:** guests, non-members, and members without an established
handicap. **Kerry, live:** *"Christopher Espinosa is NOT an eligible
blind because he doesn't have an established TGF Handicap yet. Guests
aren't eligible either."*

`_blind_pick` picks **at random among the tier with the fewest blinds
this calendar year** — Kerry: *"RANDOM would choose players randomly
who've been blinds the least."* Random inside the tier, not "first
alphabetically in the tier", which is what a naive fewest-first sort
gives you.

New table `blind_draws` (`_ensure_pairing_tables`): `event_id,
event_date, chapter, holes, group_num, slot_label, cart_pos,
customer_id, player_name, slot_key, source, note, created_at`, with
`UNIQUE(event_id, slot_key)`. `customer_id` is the identity key per
guiding principle 6.

Functions: `get_event_blinds`, `blind_draw_history`,
`backfill_blind_draws_from_gg` (reads `Bl[...]` marks already typed into
GG — `_BLIND_MARK_RE`), `event_blind_pool`, `draw_event_blinds`,
`set_event_blind`, `draw_one_blind`, `clear_event_blinds`.

`_established_index_by_customer` was rewritten as ONE counting query
against `handicap_rounds`/`handicap_player_links` (it called
`get_all_handicap_players` first, which took seconds and made the picker
feel broken):

```python
cfg = get_handicap_settings(db_path)
min_rounds = int(cfg.get("min_rounds", 3))
months = int(cfg.get("lookback_months", 12))
cutoff = (datetime.now() - timedelta(days=months * 30.44)).strftime("%Y-%m-%d")
# SELECT l.customer_id, COUNT(*), AVG(r.differential) … GROUP BY l.customer_id
# kept when n >= min_rounds
```

### 15e — surfaces

- `POST /api/events/<id>/pairings/blinds` — modes `pool`, `clear`,
  `choose`, `random`, plus a whole-sheet draw.
- `blind_pool` ships with the `/pairings` GET so the picker is instant.
- Blinds render **in their seat** (`.pairing-blind-slot`), not in a list
  below — Kerry: *"They should also show in the OPEN spaces themselves,
  not below."* `openPairingPicker(anchor, players, holes, onPick,
  blindCtx, seated)` lets a bullpen player be dropped directly onto a
  blind, and a blind be replaced from the bullpen.
- Starter sheet prints BLIND rows; `get_event_print_pack` carries
  `blinds` per group.
- Bridges: `scoring-blinds`, `scoring-blinds-history`.

**Documented in `docs/claude/pairings.md` as rule 15**, with the
open-for-ratification list (see §10).

### Live actions taken

Will Wallace removed from pairings (seat left open, mid-round); 18
historical blinds backfilled from GG; Gus Vasquez drawn for Will's seat
after Espinosa was ruled ineligible.

---

## 3. Money and winner holds (v2.439.0, v2.452.0, v2.453.0)

**Kerry:** *"Winnings should not be showing. Not all scores are in.
Every hole must be accounted for every player"* — then, seeing a win
tint on a non-winner: *"Why is Rob Burlingame showing as a Net Flight
winner?"*

`_event_field_complete(conn, event_id, holes_n)` is the gate: **every
player must have a stroke on every hole of the event**. It returns
`complete / field / pending / holes_posted / holes_needed`.
`get_event_leaderboard` publishes `money_visible`, `money_reason`,
`field_complete`, `scores_pending`.

Client side, `evlbBlankMoney` clears dollars **and win flags** while
`field_complete === false` — the first cut zeroed the dollars but left
the tints, which is how Rob Burlingame read as a Net Flight winner.
`evlbMoneyNotice` names the players still owing holes, so the hold is
explainable instead of mysterious.

`evlbBlankMoney` was also taught the paid-places cap — Kerry: *"2nd Team
net doesn't need to show if there's only one place paid."*

---

## 4. Leaderboard display

| Directive (Kerry, verbatim) | What shipped |
|---|---|
| "Show a simple colored circle right justified in name cells that corresponds to player's tees." | `evlbTeeFill` / `evlbTeeDot`; `tee_by_player` on the payload, played tee first, starter-sheet band as fallback |
| "Order Net and Gross by associated +/- column during event" | ± ordering while `field_complete` is false |
| "Pin to top goes a little high on the LEADERBOARD" | `evlbStickyTop` measures the whole sticky stack |
| "Also need to show ALL holes that will be played for that event, whether or not that have been played!!!!!!!!!!" | hole columns come from the EVENT (`nine_side`), not from whichever holes happen to be posted |
| "Circle skins, even though the event is still going and even if they're temporary. Of course, remove circle if someone else covers them." | live skins circles that un-circle when covered |
| "For team/cart net, PH should show their team/cart net handicap… The Team chevron should not do what it's doing. It should expand each player in the group to see their cards." | `team_allowance` / `team_basis` on the payload; members carry `hcp` and `team_hcp`; the chevron opens each player's card |
| "SKINS not fitting in cell header. Maybe should just be '#'." | header collapses to `#`; `.evlb-togrow` / `.evlb-teekey` + `fitKeys()` |
| "Need to show legend up top for TEE colors. Right of the check boxes on the same row on desktop. move to row below if narrow or on mobile." | `evlbTeeLegend` |
| "Right align tee legend with right most column." | `evlbAlignCard` measures from the card's own edge |
| "Not good. Fix" (team cards squashed) | forced alignment was collapsing the label column on stacked cards — removed there, plus a zero-width-ruler guard |
| "Pops are too small like you warned. Make them 50% larger" | pops at 0.42em |

**Tee colours for every course.** Kerry supplied full cards for Avery
Ranch, Cedar Creek and Forest Creek; they live in the NEW file
`email_parser/course_cards.py` (`COURSE_CARDS`, keyed by GG course id —
22363 / 35670 / 29522) with r18/s18/front/back/par/SI/yards, imported by
`import_course_card(key, dry_run=True, db_path=None)` which writes three
rows per tee (full / front / back, and `both` when the nines rate
identically). Bridge: `scoring-course-card`.

**The band rule Kerry restated:** *"1 - <50 / 2 - 50-64 / 3 - 65+ / 3 (L)
- Forward (Ladies), OR 4 (L) - Forward (Ladies)"* — so `event_tee_legend`
maps bands by the **club's tee ORDER number**, not by yardage. This
supersedes the older "under-50 tee = back tee 6300–6800 yds" heuristic.

Legend wording, per Kerry: `Men <50`, `Men 50-64`, `Men 65+`, `Women`
(just "Women", no colour word); "Tee should say Tees";
`_tee_name_plural()` turns `3 - Red (L) Tee` into `Red Tees`; ladies
tees always sort LAST and render as a red outline. White tees are a
black outline with a white centre (`_TEE_COLOR_WORDS["white"] =
"#FFFFFF"`).

---

## 5. Starter sheet (v2.448.0)

Squares became circles (`tee_dot(band)` macro) to match the leaderboard;
all tee TEXT in columns became circles; `Forward` shows as `Fwd` in
foursomes and Alpha; NEW and 1T badges (`.abadge.ft` / `.nw`) on the
alphabetical list with a legend below.

**NEW means joined since the last event** (`_prev_date`) and **can
coexist with 1T** — Kerry: *"a player could be both a 1T and a NEW like
Morris Allen."*

`get_event_print_pack` carries `tee_swatches`, `tee_ladies`, `tee_colors`
(ink; white → black).

---

## 6. The plus-handicap MVP rule (v2.450.0)

**Kerry, verbatim:** *"for plus handicappers like Pat Youngs there's
something that Golf Genius can't do. For MVP nobody is allowed to have to
add strokes on any given hole, so there should be no pluses on any holes.
But his +3 PH still stands. The way it works on our side is that his
total points gets deducted that 3 strokes. It's not fair to make a player
have to perform on any one hole, but it should be applied across a
round."*

**The rule: a plus handicap comes off the ROUND, never off a hole.**

`database.py` `get_event_leaderboard`, in the points loop:

```python
_plus = {id: int(round(abs(ph))) for rounds with playing_handicap < 0}
_recv = max(0, _recv) if rid in _plus
# after the loop:
pts[rid]["net"] -= give
pts[rid]["plus_adjust"] = -give
```

`live_scoring.py` `build_cards` does the same:
`d_pts = derive_hole(par, strokes, max(0, sr), formulas) if sr < 0 else d`,
the row's `stableford_net` uses `d_pts`, `pts_adjust` is subtracted from
the total, and `points_plus_adjust` is published. The PTS row on the
leaderboard shows `pts_plus_adjust`.

Written into `docs/claude/side-games.md`. Tests:
`test_plus_handicap_points.py`.

### The rule shipped on two surfaces, and there are two more (OPEN)

**Kerry, 2026-09-15 ~9:15 PM, looking at Pat Youngs' Quarry Front card
on `/handicaps`:** *"We just determined this isn't how we do Net Points
with pluses on holes."* The card still shows a plus stroke ADDED on
individual holes — NET SCORE reading 4 where GROSS is 3, the `○` plus-
stroke mark, and NET PTS dropping to 0 on hole 3 — which is precisely
what the rule forbids.

v2.450.0 fixed the rule **at the two call sites in front of us**
(`get_event_leaderboard`, `live_scoring.build_cards`) instead of at the
MECHANISM. The mechanism is `compute_hole_derivations(par, strokes,
strokes_received, formulas)` (`database.py:15533`), where a negative
`strokes_received` makes `net = strokes - (strokes_received)` ADD a
stroke, and `stableford_net` falls out of the table at that inflated
net. Eleven call sites go through it. **This is the third instance of
the class/instance failure in one night** (see also §7).

**The split that the fix has to respect** — the same negative
`strokes_received` is CORRECT in one half and wrong in the other:

| Call site | Purpose | Plus strokes on holes |
|---|---|---|
| `get_differential_parity` (18358) | WHS | **KEEP** — USGA net double bogey is `par + 2 + strokes_received`, and for a plus that legitimately lowers the cap |
| `get_scoring_handicap_preview` (18514) | WHS | **KEEP** |
| `_two_nine_recap_rows` (20776) | WHS | **KEEP** |
| `derive_18hole_rounds_as_two_nines` (20977) | WHS | **KEEP** |
| `_nine_totals_for_card` (36471) | adjusted gross | **KEEP** |
| `get_event_leaderboard` (14015) | game | fixed v2.450.0 (locally) |
| `live_scoring.build_cards` | game | fixed v2.450.0 (locally) |
| **`get_scorecard` (22345)** | **display — the card Kerry is looking at** | **STILL WRONG** |
| **`fetch_champ_player_card` (10152)** | **Players Cup card** | **STILL WRONG** |

Renderers carrying the `○ = plus stroke` mark:
`static/js/scorecard-render.js:137` and `static/js/points-render.js:643`.

**Correct fix shape:** put the rule in `compute_hole_derivations` behind
an explicit game-vs-WHS flag — `adjusted_strokes` keeps the true
`strokes_received`, while `net` / `net_vs_par` / `stableford_net` use
`max(0, strokes_received)` — and have the game callers apply the
round-level deduction. Then no future caller can miss it. Carried to the
spin-off; see `docs/claude/session-prompt-2026-09-16-handicap-card-identity.md`.

---

## 7. The timezone bug — twice in one night

**Kerry: "Tonight's events that are currently active already switched to
PAST events"** → `events.html` was comparing against a UTC date. Fixed
with `tgfToday()` (Central) in v2.449.0.

**Kerry, an hour later: "Leaderboard isn't updating again."** → the
server-side poller `poll_live_events()` used `datetime.now()` for
"today". From 7 PM Central onward the container's UTC clock is already
tomorrow, so the poller asked for **tomorrow's events and found none**.
Fixed with `today_central_str()` plus a yesterday-if-recent window
(v2.452.1).

**This was the same mistake, fixed on the client an hour earlier and not
carried to the server** — a textbook failure of *protect the CLASS, not
the instance*. CLAUDE.md's Timezone section already said this. Any
calendar-day boundary must go through `email_parser/timezone_utils.py`.

Auto-poll now runs as `auto_live_poll_job` every 5 minutes
(`AUTO_LIVE_POLL`, `LIVE_POLL_MINUTES`), skipping events that have not
started and events already complete. Bridge: `scoring-live-poll`.

---

## 8. The GG data corrections — and the money they invalidated

**Kerry:** *"Looks like all sorts of stuff about winnings is off because
we pulled stuff too soon from GG. Need to rerun it."* … *"These don't
match"* … *"Looks like Austin needs to rerun"*.

Three separate defects formed one chain:

1. **`imported_at` was never restamped on re-import.** `import_gg_
   scorecards` inserted with `ON CONFLICT` but left `imported_at` at the
   FIRST insert, so the "ten minutes since the last score" settle clock
   ran from the original mid-round pull and never moved. Fixed to
   restamp **only when gross / net / holes_played actually changed**
   (v2.452.2) — an unchanged re-walk must not restart the clock either.
2. **Team Net was mislabeled.** `import_gg_game_results` excluded `game`
   from the winners upsert, so a classification captured during a live
   mid-round walk was frozen even after GG finalised the board. Fixed
   with `game = excluded.game` on **both** upserts (winners and the
   board loop) — v2.453.0.
3. Those two produced wrong payout rows, which had already been
   recorded.

**Remediation performed:** both chapters' game boards re-walked, MVPs
imported (Adam Baker — city SA and TGF; Luke Youngs — city Austin),
payouts re-recorded. **s9.23 = $428, a9.23 = $212**, verified line by
line against Kerry's GG screenshots (e.g. Baker $156 = 63 + 21 + 28 +
44). The a9.23 reconciliation "Difference" of $16 is the TGF MVP share
paid at the winner's event — explained, not a defect.

---

## 9. After the round

**Apple Pay (v2.454.0)** — Kerry: *"Just sent Jesse's money that way."*
Added to `ALLOWED_SOURCES`, `_METHOD_LABEL`, and the refund /
payout-credit lists in `app.py`.

**Mark Paid is one modal (v2.455.0)** — Kerry: *"make it all one modal…
auto enter today's date… and enter the appropriate note."* It had been
three chained browser prompts. Now `tgfMarkPaidDialog({name, amount,
eventName, note})` in `templates/tgf.html`: method as a row of buttons
(Venmo first, Apple Pay beside it), the date opening on **Central**
today, and the note composed from what the player actually won
(`paidNoteFor(items)` → "TEAM Net 1st + Skins Birdie on 8") with
bookkeeping tails stripped. Enter confirms, Escape cancels.

**Handicap-card accounting (v2.456.0)** — Kerry: *"Not sure how we have
21 registered and only 16 sent and 3 skipped. Seems to be 2 unaccounted
for."* Then the same on Austin. Two silent `continue`s in the send loop
(no email on file; no nine-hole index) dropped people with no counter
and no name. Both are counted now, every skipped player is NAMED, and
the result line publishes the arithmetic — `N sent · N skipped … of 21
registered` — turning red if the buckets still do not reconcile. **A
count that does not reconcile is worse than no count: it reads as
authoritative.**

**Handicap rounds posted.** Kerry: *"Actually I think I sent those
without actually running the handicaps. Do that now."*

- **s9.23 The Quarry** — 21 written, 0 skipped, 6 `cap_changes_
  differential`. Index moves: Adam Baker 4.3→3.8, Michelle Delcarmen
  20.0→18.5, Larry Anthis 8.1→8.0, Rob Burlingame 9.2→9.5, Mike Murphy
  16.8→17.1, Richard Palacios 7.6→7.7, Pat Youngs −0.7→−0.5. First or
  second round with no index yet: Morris Allen, Christopher Espinosa,
  Justin Guerrero, Joe Mejia. Wade Lewis had 2 capped holes.
- **a9.23 Avery Ranch** — 11 written, **1 skipped: Lee Vasquez, "no tee
  slope/rating on the round"** (round 3518). Index moves: Kyle Compton
  11.1→8.4, Louis Schneider 5.1→4.8, Luke Youngs 0.5→0.3, Eduardo
  Melchor 5.6→5.8, Robert Straiton 0.4→0.6. No index yet: Guillermo
  Arevalo, Tom Donovan, Jeff King.

Both recap emails sent to kerry@ + robert.straiton1@. Standard: *WHS net
double bogey adjusted gross (Kerry-ratified 2026-07-14)*.

**Kerry's handicap cards went out BEFORE these rounds posted**, so they
carried stale indexes. They should be re-sent for both events.

---

## 10. Open — carried out of this session

### Rule 3b ratification still open (blind draws)

None of these has an explicit Kerry ruling; they are how the code
currently behaves:

1. Team size **4** (`BLIND_TEAM_SIZE_DEFAULT`).
2. Eligibility is **field-only** — members with an established index, no
   guests, no unestablished members. (Kerry ruled the Espinosa case
   live; the general rule is inferred from it.)
3. **One blind per person per event.**
4. Counting is by **calendar year, across chapters** — a blind in Austin
   counts against an Austin member's turn in San Antonio.
5. Our draw is a **proposal Kerry enters into Golf Genius**; the Tracker
   does not write to GG.

### The bug Kerry asked about — handicap-card event filter matches by NAME

`app.py` `api_handicap_send_bulk_email` (~line 9737). Three layers:

- **(a) name-string identity.** `event_customers` is a set of
  `items.customer` lowercased; `player_to_customer` maps
  `handicap_player_links.player_name → customer_name`; the match is
  string equality of the two. `items.customer` is a per-order historical
  snapshot (see CLAUDE.md "Identity drift watch"), so "Mike Murphy" vs
  "Michael Murphy" — or any name proper-cased or changed after the order
  — reads as **"no TGF handicap on record"** and the player silently
  gets no card. This violates guiding principle 6 outright.
- **(b) `WHERE customer_name IS NOT NULL`** on the links query drops any
  link that has a `customer_id` but a null `customer_name`.
- **(c) it builds its own roster** from `get_all_items()` + aliases
  rather than `_event_roster_rows(conn, event_id)` — the ONE builder
  mandated in v2.410.0. GG-RSVP-only players with no order row are
  invisible to it and are not even counted in `registered`.

The `members_only` branch has the same (a) defect: it joins
`c.first_name || ' ' || c.last_name = l.customer_name` and then matches
`r["player_name"]` against that name set.

**Fix shape:** resolve both sides to `customer_id` (roster via
`_event_roster_rows`, handicap side via `handicap_player_links.
customer_id`), fall back to name only when a link genuinely has no id,
and report each fallback so the gap is visible rather than silent. This
is spun off — see §11.

### Carried from earlier sessions

- design-claude review #517 / #520 awaiting reply.
- Two off-standard chevrons on `/me` and Money Flow.
- The live-scoring build awaits Kerry's "go".
- CA Queue #1.

---

## 11. Files touched

**New:** `email_parser/course_cards.py`; `test_blind_draws.py`,
`test_money_hold.py`, `test_plus_handicap_points.py`,
`test_mark_paid_modal.js`, `test_handicap_card_counts.js`;
`docs/claude/handoff-2026-09-15-event-night-leaderboard.md` (this file).

**Changed:** `email_parser/database.py` (blinds, `_event_started`,
`_pairings_drop_if_off_roster`, `_event_field_complete`,
`poll_live_events`, `import_course_card`, `event_tee_legend`,
`_tee_name_plural`, `get_event_leaderboard`, `import_gg_game_results`,
`import_gg_scorecards`, `get_event_print_pack`),
`email_parser/live_scoring.py`, `app.py`, `mcp_server.py`,
`templates/events.html`, `templates/contests.html`,
`templates/starter_sheet.html`, `templates/tgf.html`,
`templates/handicaps.html`, `static/js/version.js`,
`docs/claude/pairings.md`, `docs/claude/side-games.md`.

**Updated tests:** `test_event_reports.py`, `test_events_board.js`,
`test_pairings_roster.js`, `test_pairing_rounds.py`.

---

## 12. Traps worth remembering

- **`escapeHtml` is not global.** `tgf.html` and `handicaps.html` do not
  load `dashboard.js`; both needed local copies.
- **Clock-dependent tests.** `_event_started` tests inject `now`; the
  blind test event is dated yesterday. Never let a test read the wall
  clock.
- **Renaming a display string broke playing handicaps.** `_event_tee_
  rows` matched on `tee_name`; the legend rename to "Red Tees" broke it.
  `tee_key` now carries the RAW card name for matching and `tee_name` is
  display only. Never match on a label you also style.
- **`event_blind_pool` read the wrong DB in tests** — it now derives
  `db_path` from `PRAGMA database_list` when not given.
- **The events-board test harness slices the file**; tee helpers had to
  move inside the sliced renderer region to be visible to it.
