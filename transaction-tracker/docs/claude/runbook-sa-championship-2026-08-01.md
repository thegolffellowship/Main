# Runbook — shadowing the SA CHAMPIONSHIP live (Sat 2026-08-01, The Quarry)

First live outing for the Test Center. **Golf Genius remains the official
scorer all day.** We shadow, we diff, we learn where our engine disagrees.
Nothing on this page changes a score, a payout, or a member-facing surface.

## The event

| | |
|---|---|
| Event | `TGF SAN ANTONIO CHAMPIONSHIP` (events.id 3289) |
| Date | Saturday 2026-08-01 |
| Course | The Quarry Golf Club (course_id 22361) |
| Holes | **18** (every registration carries `holes = 18`) |
| Field | **26** registered as of Wed 7/29 ~4pm (was 19 that morning) |
| Points | Championship schedule — auto-selected from the event name |

Buyer split at 26 registrations (drives which games activate):

- **NET buyers: 18** (NET or BOTH)
- **GROSS buyers: 16** (GROSS or BOTH)
- No side games: 3 (South, Thompson, Bricco)
- Tee choice: `<50` ×7 · `50-64` ×14 · `65+` ×4 · `Forward` ×1

Which means, on the ratified 18-hole matrix:

- **Individual Net → 2 flights** (18h: 1 flight to 13 buyers, 2 at 14–33)
- **Individual Gross → ACTIVE, 4 flights** (activates at 12 on an 18;
  12–15 → 3 flights, **16+ → 4**)
- **Skins → 2 flights** (18h: 2 flights 8–31)

**These counts move and they cross thresholds.** At 19 registrations that
morning it was 13 GROSS buyers → 3 flights; seven entries later it is 16 → 4.
Gross activation also sits close to its floor: it needs 12 buyers on an 18,
so withdrawals can switch the game off entirely. The board always recomputes
from whoever is actually in `items`, so **read the counts off the page on the
day** rather than trusting any number written here.

## The Quarry course data — RESOLVED (was a false alarm)

We hold **all 18 holes** of The Quarry. An earlier read of this concluded the
front nine was missing; that was wrong, and the reason is worth recording
because it will recur at every course TGF plays as nines.

TGF plays nines and **Golf Genius rates each nine separately**, so one
physical tee becomes several `course_tees` rows, each holding only its own
nine's holes:

| Tee row | Rating | Holes | Stroke indexes |
|---|---|---|---|
| 109 — 1 - Gold Tee | 117 / 34.2 | 1–9 (`s9.15`, 2026-06-23) | 9,3,15,17,1,11,7,13,5 — **odd** |
| 592 — 1 - Gold Tee | 128 / 35.6 | 10–18 (`s9.4`, `s9.19`) | 4,18,14,10,2,16,12,6,8 — **even** |

Together that is a complete 18-hole stroke index 1–18. Same pattern on Blue
(112 front / 594 back), Red (L) (111 / 615) and Red (116 / 627).

Reading a **single** `tee_id` therefore returns half a golf course. The
Test Center now merges `course_tee_holes` across every tee row sharing the
same course and tee name (`_ls_tee_holes`), so seeding off either nine's row
yields all 18 holes with a valid 1–18 index. Regression-tested both
directions, including that a different tee name cannot leak in.

The `course_coverage` banner remains as the backstop — it is still correct
that a par-less hole scores zero in every game, and it will fire at any
course where a nine genuinely has not been imported yet.

## TGF handicap scoping (Kerry, ratified in conversation 2026-07-29)

Two rules that pull in different directions, both true:

1. **Course / playing handicaps come off the 18-HOLE rating and slope, and
   apply across all 18 holes.** So a shotgun 18 at The Quarry allocates
   strokes over the merged 1–18 stroke index — which is exactly what the
   merge above produces.
2. **Handicap DIFFERENTIALS are computed from the 9-HOLE ratings and
   indexes.** That is the posting path (`handicap_rounds`,
   `docs/claude/handicaps.md`) and the Test Center does not touch it — it is
   a scoring and leaderboard surface, so rule 2 is context here, not work.

Consequence for the derived path: we do **not** yet hold a true 18-hole
rating/slope row for The Quarry (both existing rows are nine-rated). On a
GG-seeded session that is moot — GG hands us each player's playing handicap
and its own dots, so rule 1 is satisfied by construction. It only matters
for fully untethered Stage-2 scoring, where we would compute the playing
handicap ourselves and need the 18-hole tee row. GG publishes that with the
event, and the import accretes it.

## Pre-flight (once GG publishes the event — Thu/Fri)

1. Import the event from its GG tournament page (Scoring import, or the
   `scoring-import:<event_code>` bridge). Scores need not exist yet.
2. Open `/admin/test-center` → **Shadow a real event** → the championship.
3. Confirm no coverage banner, 18 holes, par 71, championship schedule on.
4. Check the flights match GG's (see below).

## Saturday

1. **Before the shotgun** — seed the session (or reuse the pre-flight one)
   and confirm: 18 holes, no coverage banner, championship schedule on, the
   field looks right, teams came from the pairings.
2. **Paste the GG tournament URL** into the box on the Leaderboard tab. It
   is remembered per session in localStorage, so you paste it once.
3. **During the round** — hit **Pull from GG** whenever you want the board to
   move. Manager edits survive every pull; only scores and handicaps come
   back from GG. The 10-second **Live refresh** toggle re-renders the board
   from local data — it does *not* re-pull GG, so pull explicitly.
4. **Watch the Parity tab.** This is the whole point. Every disagreement
   between our engine and GG is the finding — write down what differs and on
   which game before the cards get finalized.
5. **Record CTP / Longest Putt by hand** as they are adjudicated — they are
   measured on course and can never be derived from scores.

## What will probably differ, and why that's the finding

Expect these, and record rather than "fix" them on the day:

- **Flighting — read it from GG, don't infer it (Kerry, 2026-07-29).** GG's
  flights are LIVE DATA once the event is live: they come off the GG
  Leaderboard by expanding the flight groups. That is the source of truth and
  it retires the guessing entirely.

  Current state: `scoring_rounds.flight` exists but is **NULL on every
  imported round** (checked across 100 Quarry rounds and the s18.8 field), so
  the importer is not capturing it yet — the leaderboard flight groupings are
  a parse target we have not built. Until it is, the engine falls back to
  equal-size handicap bands, which is a guess.

  **Saturday workaround:** expand GG's leaderboard, read the flights, and
  type them into the **Flight** column on the Field & Course tab. Explicit
  flights always win over the fallback, so this pins GG's real flighting and
  isolates the scoring diff from the flighting diff. Capturing flight from
  the leaderboard widget at import time is the follow-up build.
- **Per-player tees.** The field spans **four** tees (`<50`, `50-64`, `65+`,
  `Forward`) and a session carries ONE set of course holes — the field's modal
  tee, which here is `50-64` at 14 of 26. Par is normally identical across
  tees and a seeded session uses GG's own dots, so net scoring should be
  right on Saturday. Two places it can still show: **yardage** (so CTP's
  shortest-par-3 selection uses the modal tee's numbers) and any tee whose
  stroke index differs — Forward often does, and Mary Wade is on it. Real gap
  for untethered Stage-2 scoring, where we allocate dots ourselves.
- **No payouts.** The board ranks; it does not pay. Do not use it for money.
- **Team Net** needs pairings saved for the event, or it warns instead of
  scoring. Short foursomes warn that the ratified blind draw isn't generated.

## Dry run before Saturday (recommended)

`s18.8 VAALER CREEK` (2026-07-18) is a completed **18-hole** event with full
18-hole course data and complete cards already imported. Shadow it and
confirm the Parity tab reads **PARITY** — that proves the whole 18-hole path
end to end on real data, with no Quarry unknowns in the way. If s18.8 shows
deltas, we want to know that on Thursday, not at the turn on Saturday.
