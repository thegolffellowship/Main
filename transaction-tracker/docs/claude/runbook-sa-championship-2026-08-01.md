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
| Field | 19 registered as of Wed 7/29 |
| Points | Championship schedule — auto-selected from the event name |

Buyer split as registered (drives which games activate):

- **NET buyers: 15** (NET or BOTH) — Wolin, Sharitz, Hamilton, Vasquez,
  Horton, Rideout, McCrary, Niester, Rohrmann, Wade, Youngs, Palacios,
  Callaway, Marroquin, Fieber
- **GROSS buyers: 13** (GROSS or BOTH) — Fehlis, Sharitz, Hamilton, Horton,
  McCrary, Niester, Rohrmann, Mazanec, Wade, Griffin, Youngs, Palacios,
  Marroquin
- No side games: South

Which means, on the ratified 18-hole matrix:

- **Individual Net → 2 flights** (18h: 1 flight to 13 buyers, 2 at 14–33)
- **Individual Gross → ACTIVE, 3 flights** (activates at 12 on an 18; the
  12–15 band is 3 flights)
- **Skins → 2 flights** (18h: 2 flights from 8 buyers)

Counts move with late entries and withdrawals — the board recomputes from
whoever is actually in `items` at refresh time, so re-check the buyer counts
on the day rather than trusting this list.

## ⚠ The one real blocker: The Quarry's front nine

**TGF has only ever played the BACK nine at The Quarry.** Every Quarry tee
in our course DB carries par / yardage / stroke index for holes **10–18
only**; holes 1–9 are NULL. Verified on round 3119 (McCrary, s9.19, tee 592
"1 - Gold Tee") — holes 1–9 come back with `par: null`.

A hole with no par derives nothing. Scores post, the card looks normal, and
those holes contribute **zero** to every game. An 18-hole round at The
Quarry would silently score nine holes.

This normally self-heals: GG's tee block for an 18-hole event carries all 18
holes, and `import_gg_scorecards` accretes `course_tee_holes` automatically.
But it only heals **on import**, so it must be proven before Saturday, not
discovered at the turn.

### Pre-flight (do this once GG publishes the event — Thu/Fri)

1. Import the event from its GG tournament page (Scoring import, or the
   `scoring-import:<event_code>` bridge). Scores need not exist yet — the
   tee block is what matters.
2. Open `/admin/test-center` → **Shadow a real event** → the championship.
3. Look at the top of the Leaderboard tab. **A red "Course data incomplete —
   the board is WRONG" banner means the front nine is still missing.**
4. If it is still missing, fill par + stroke index for holes 1–9 on the
   **Field & Course** tab from the Quarry scorecard. It is 18 numbers and it
   takes two minutes. Stroke index matters as much as par: without it,
   handicap dots cannot be allocated and every NET game is wrong.
5. Banner clear = ready.

Note The Quarry's back nine holds all the EVEN stroke indexes (10→4, 11→18,
12→14, 13→10, 14→2, 15→16, 16→12, 17→6, 18→8), so the front nine should
carry the ODD ones, 1–17.

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

- **Flighting.** The only GG split we have directly observed is the 9-hole
  two-flight break at HCP 12.0. An 18-hole 2-flight Net and a 3-flight Gross
  are **both unobserved** — our engine falls back to equal-size bands. This
  is the single most likely source of disagreement, and pinning GG's real
  18-hole rule is the most valuable thing to come out of Saturday. If GG's
  flights are visible, type them into the Flight column and the scoring diff
  isolates cleanly from the flighting diff.
- **Per-player tees.** Players choose `<50` / `50-64` / `65+` / `Forward`,
  and a session carries ONE set of course holes (the field's modal tee).
  Par is usually identical across tees, and a seeded session uses GG's own
  dots, so this should not bite on Saturday — but it is a real gap for the
  untethered Stage-2 path, where we allocate dots ourselves.
- **No payouts.** The board ranks; it does not pay. Do not use it for money.
- **Team Net** needs pairings saved for the event, or it warns instead of
  scoring. Short foursomes warn that the ratified blind draw isn't generated.

## Dry run before Saturday (recommended)

`s18.8 VAALER CREEK` (2026-07-18) is a completed **18-hole** event with full
18-hole course data and complete cards already imported. Shadow it and
confirm the Parity tab reads **PARITY** — that proves the whole 18-hole path
end to end on real data, with no Quarry unknowns in the way. If s18.8 shows
deltas, we want to know that on Thursday, not at the turn on Saturday.
