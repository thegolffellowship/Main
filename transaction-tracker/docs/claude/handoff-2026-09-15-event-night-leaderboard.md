# Session record — 2026-09-15 event night, v2.437.0 → v2.457.0

**Lane:** tracker-claude "TGF Tracker Improvements" · branch
`claude/tracker-improvements-h7q2ns` · all 27 commits merged to `main`
and live on Railway.
**Events in play:** s9.23 The Quarry (San Antonio, 5:00 PM shotgun, 21
players) and a9.23 Avery Ranch (Austin, 4:57 PM tee times, 12 players).
Most of this was built WHILE the rounds were being played, from Kerry
watching the live board on his phone at the course.
**Mailbox:** #508–#524 are this session's posts. #522 covers through
v2.442.0; #523 is the close-out digest for v2.443.0–v2.457.0; #524 is
the addendum (§13 below + the CA Queue rows).

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
  slope/rating on the round"** (round 3518). **RESOLVED the same night by
  the event-closeout lane** (see below). Index moves: Kyle Compton
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


---

## 13. After the close-out — v2.457.0 and the three questions left with Kerry

The handoff above was written and pushed at v2.456.1. Kerry kept
working, so this section covers what came after it.

### 13a — Proxy winners read like every other board (v2.457.0)

**Kerry:** *"Use same text for Proxy winners as the others."*

The Proxies tab was printing the raw Golf Genius string —
`escapeHtml(p.player)` — with no board name cell and no card behind it.
So the one tab whose entire job is to NAME a winner was the one tab
whose winner did not look like a player anywhere else on the page, and
did not open when tapped, although the footer note promises "Tap a
player for their scorecard".

`proxWinner(nm)` resolves the GG name back to the board row through
`evlbRowByName` (built from `d.overall_board`, keyed by both the plain
name and `evlbFlipName`'s "LAST, First" flip — the same flip the tee
dots already use), renders OUR `player_name` in a standard `td.nm` with
its tee dot right-justified, and wraps the row in `evlb-plr` +
`data-rid` so it styles, dots and opens exactly like the others. The
proxies table is the only board that is not `.evlb-holes`, so
`.evlb-prox td.nm` repeats the name-cell rule.

### 13b — NEW BRIDGE: `scoring-skins-audit:<event>` (v2.457.0)

**Kerry:** *"Carlos's skin isn't circled. Audit."*

`skins_audit(event_query, db_path=None)` in `database.py` (just above
`_flight_skins`), bridged in `mcp_server.py`. Read-only. It rebuilds
exactly what `get_event_leaderboard` does for `skin_cells` — outright
low GROSS on a hole among the BUYERS in that flight — and prints the
working: every buyer's stroke on every hole, the low, who held it, and
why the hole did or did not pay, set against what is actually recorded
as skins money. A player with money but no circled hole now produces a
line you can read instead of a missing circle you have to guess at.

### 13c — What the audit found: Golf Genius contradicts itself

a9.23 Avery Ranch. Skins buyers are the GROSS bundle — Luke Youngs,
Carlos Zapata, Eduardo Melchor, Robert Straiton (4 buyers, so ONE
flight; the Individual Gross pot rolled into skins at 4 buy-ins).

Computed: exactly **three** skins, all Luke's — holes 2, 3 and 5. That
matches GG's own detail line for him, *"Par on 2, Birdie on 3, Eagle on
5"*, hole for hole. Carlos was low on three holes and **tied every
one**: hole 1 (4, with Luke), hole 7 (4, with Luke), hole 8 (3, with
Straiton).

But GG's skins board pays Carlos $13 for **"Birdie on 7"**. Avery Ranch
front hole 7 is par 4, so GG's board believes he made **3** there —
while GG's **own scorecard**, which is what we imported, has him at
**4** and totals him at gross 44 (4-5-7-5-7-4-4-3-5).

So our board is faithful to the scorecard; the disagreement is inside
GG. If Carlos made 3, there are four skins at $13 and GG's payout is
right. If he made 4, there are three skins and the whole $52 pot is
Luke's. **$52 and Carlos's posted handicap round both hang on it** —
left with Kerry rather than guessed at. CA Queue #2.

Worth noting for the next person: the same 4-buyer field, the same
`_flight_skins` rule, and GG's own prose agreed on Luke's three skins
exactly. A single hole disagreed. That is what made it diagnosable —
the audit's value is that it prints the agreement as well as the gap.

### 13d — Chapter badges: the rule Kerry has not given yet

**Kerry, on the Points Races standings:** *"Some of these aren't the
right chapters. Weigh against their event signup locations."* (Flagged
in the screenshot: Barna, Moore, Sharp, Franz, Williams.)

The A/SA badge is `prChapterBadge(chapter)` in `templates/contests.html`
(~line 7770); its input is the standings payload's `chapter`, which is
**`customers.chapter` — the DECLARED home chapter**.

Two sensible replacement rules give DIFFERENT answers for exactly the
cross-chapter players flagged:

- (a) the chapter where the player registered for the **most events in
  that race's season**;
- (b) the chapter of their **most recent event**.

tracker-claude recommends (a), with `customers.chapter` as the fallback
for anyone with no event rows: it is stable week to week, where (b)
flips every time someone visits the other city. **Not built** — awaiting
the ruling. CA Queue #4.

**Constraint that must survive whichever rule wins:** change only what
the BADGE DISPLAYS. CLAUDE.md's identity-drift section is explicit that
`customers.chapter` must not be overwritten from `items.chapter`,
because `items.chapter` is the event/course LOCATION and cross-chapter
play would corrupt the member's home chapter. This is a display
derivation, not a data repair.

### 13e — Everything now on Kerry's desk, in the CA Queue

Written to `ca_queue` so they live on his own checklist rather than in a
transcript:

| # | Section | Item |
|---|---|---|
| 2 | kerry_decision | a9.23 skins — Carlos Zapata hole 7, $52 (13c) |
| 3 | kerry_decision | Ratify the five blind-draw specifics (§10) |
| 4 | kerry_decision | Chapter badge rule (13d) |
| 5 | kerry_decision | How the plus-handicap deduction rounds — Pat Youngs at −0.5 rounds to zero (§6) |
| 6 | followups | Re-send the handicap cards for both events — the first send carried stale indexes (§9) |

(#1 was already open: ratify importing TEAM tournament per-player nets
at event sync, mailbox #472.)

### 13e-2 — Corrected by the event-closeout lane, same night

A second lane ("event closeout", v2.458.0–v2.458.4) was running
concurrently and resolved two things this handoff had recorded as open.
Verified independently against `scoring-hcp-preview:a9.23 Avery Ranch`
rather than taken from its prose:

- **Lee Vasquez is posted.** Golf Genius's results page DID carry his
  tee (Blue, 139 / 36.0); the auto-sync's card had lost it. Card 3518
  dropped and keyed-re-imported as **3529** with the tee, differential
  7.3, index 7.3 (unchanged). **a9.23 is now 12 of 12, 0 skipped.**
- **Guillermo Arevalo** — GG spelled "AREVALO, Guillermo" against a
  store row "Guilermo Arevalo", and the card AND its posted round both
  carried `customer_id` NULL (a rule-6 breach in the wild, on this very
  night). Alias added, card dropped, keyed re-import as **3528** with
  `customer_id` 821, index 7.8. Kerry ruled "Guillermo is correct"; 821
  renamed, three `items` rows followed.
- Austin pairings applied from the TEE SHEET (3 foursomes, 4:57 / 5:06 /
  5:15 PM) — Austin's only GG team board is CART Net, so the foursomes
  live on no board.
- That lane also reports the handicap cards were emailed **twice**
  (01:52 and 02:06 UTC), the second pass after the index fix. Not
  verified here — CA Queue #6 carries it as open until Kerry confirms.

**Carlos Zapata's card is unchanged at gross 44**, so 13c stands exactly
as written and his posted differential (7.7) is computed off 44.

**Note the lane collision:** this session and the closeout lane both
pushed to `main` within minutes, and `version.js` conflicted. Both
changelog stacks were kept; this session's entry was renumbered to sit
on top of theirs. When two lanes run on one night, merge `main` before
bumping — the rule is already in CLAUDE.md's conventions, and it earned
its place again here.

### 13f — Split of what went where

- **Spun off** to "Handicap Surfaces: Identity + Plus Rule"
  (`claude/handicap-surfaces-k4m9xr`, session prompt
  `docs/claude/session-prompt-2026-09-16-handicap-card-identity.md`):
  the handicap-card identity bug (§10) and the plus rule's nine
  unvisited call sites (§6).
- **HANDED OVER 2026-09-16** — Kerry, closing this session: *"Pass any
  open items to TGF Tracker Improvements 2 lane to pick up."* So the
  Carlos skins question (CA #2), the chapter-badge rule (CA #4), the
  blind-draw ratifications (CA #3), the handicap-card re-send (CA #6),
  the older carry-forwards, and the owed rewrite of
  `state-of-the-tracker.md` ALL moved to that lane
  (`session_01CD1p3A96wXobio1yz2y7JS`, which renamed itself "TGF Tracker
  Improvements 2"). **This lane owns nothing further.** Earlier drafts of
  this section said these stayed with the parent; that is superseded.
- **Still carried from earlier sessions, untouched tonight:**
  design-claude reviews #517 and #520 awaiting a reply; the two
  off-standard chevrons on `/me` and Money Flow; the live-scoring build
  awaiting Kerry's "go".


---

## 14. Session closed — 2026-09-16

Kerry: *"I want to close this session, so needs to be thorough"* and
*"Pass any open items to TGF Tracker Improvements 2 lane to pick up."*

**Shipped and live:** v2.437.0 → v2.458.5 on
`https://tgf-tracker.up.railway.app`. Branch
`claude/tracker-improvements-h7q2ns` fully merged to `main`; working
tree clean.

**Documented:** this handoff (§1–§14), `docs/claude/pairings.md` rule
15, `docs/claude/side-games.md` (the plus rule, the open call-site gap,
and the skins audit reachable from the rule),
`docs/claude/session-prompt-2026-09-16-handicap-card-identity.md`, and
`docs/claude/state-of-the-tracker.md` (version stamped, currency warning
added, v2.347→v2.458 wave section appended — a full rewrite is owed and
was handed over).

**Mailed:** #522, #523 (close-out digest), #528 (the gap-closing
addendum). Every finding in this document has a mailbox home.

**On Kerry's CA Queue** rather than in a transcript: #2 the a9.23 skins
question, #3 the blind-draw ratifications, #4 the chapter-badge rule, #5
the plus-deduction rounding, #6 the handicap-card re-send.

**Handed to "TGF Tracker Improvements 2"** by direct session message:
the three contract corrections (§13e-2) plus every item above, with the
note that A and D block on Kerry rather than on the lane, so those cost
him least to clear first.

**The one thing this lane would tell its successor.** Three separate
defects tonight were the same shape: a correct fix applied to the
instance in front of us instead of to the mechanism — the timezone rule
fixed on the client and not the server (§7), the plus rule fixed at two
call sites out of eleven (§6), and the money hold that blanked dollars
but not win tints (§3). CLAUDE.md's first guiding principle already says
this. The failure is not that we do not know the rule; it is that under
time pressure the visible symptom feels like the whole class. When you
fix something, enumerate its siblings before you move on — or write down
which ones you are deliberately leaving.
