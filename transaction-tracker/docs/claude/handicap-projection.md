# Playing-Handicap Projection (Task #16) — CA review & ratification draft

**Status: SHADOW / read-only. Awaiting Kerry + CA ratification of the
100% tee-based playing-handicap calculation.** Nothing member-facing.
Author: tracker-claude, 2026-07-16.

This is the keystone that untethers **net** scoring from Golf Genius:
gross points need none of it; net needs all of it. It turns a player's
**handicap index** + their **selected tee** into a course handicap, a
playing handicap, and a per-hole stroke allocation — with **no GG input**.

## The calculation (the spec to ratify)

Pure, portable, DB-free: `email_parser/handicap_calc.py` (unit tests:
`test_handicap_calc.py`). Everything is on the 9-hole scope (TGF plays
9-hole rounds; the index is a 9-hole index and slope/rating/par are the
9-hole tee values GG's tee block carries). The same formulas hold for 18
if fed 18-hole inputs.

1. **Course Handicap** = `index × (slope / 113) + (rating − par)` — unrounded.
2. **Playing Handicap** = `whs_round(Course Handicap × allowance)`, optional
   `max_hcp` cap applied before rounding. `whs_round` = nearest whole, 0.5
   **up toward +∞** (NOT Python's banker's rounding). **Base milestone:
   allowance = 100%, no cap** → Playing Handicap = `whs_round(Course Handicap)`.
3. **Allocation** = distribute the playing handicap across the holes played
   by stroke index (1 = hardest first); wraps for a 2nd stroke if the
   handicap exceeds the hole count; **TGF cap: max 2 pops/hole**. Plus
   handicaps give a stroke **back** on the easiest holes (highest SI).

`allowance` and `max_hcp` are the **per-game hooks** — the next layer
(game-engine config: 85% allowances, Max Playing Handicap, Team-Net
no-pops-on-par-3). This milestone ratifies the **100% base**; per-game
rules layer on top of it.

## Validation against actual GG (read-only bridge `scoring-hcp-project:<event>`)

`project_playing_handicaps()` projects each player's playing handicap +
allocation from **our** index + the round's tee, and compares to GG's own
`playing_handicap` and stored per-hole dots. It reports two numbers on
purpose, to separate the tee math from the index:

- **alloc-vs-GG-dots (using GG's own playing handicap)** — index-independent;
  proves the tee / stroke-index / allocation machinery. **This is the 100%
  target.**
- **playing-hcp-exact** — additionally requires our index to equal GG's.

### Results (2026-07-16)

| Event | Rounds | Allocation = GG dots | Playing-hcp exact |
|---|---|---|---|
| a9.18 Forest Creek | 19 | **19 / 19 (100%)** | 16 / 16 *(with an index)* |
| s9.17 Silverhorn | 27 | **27 / 27 (100%)** | 23 / 27 |

**Allocation: 46 / 46 = 100%.** The tee-based stroke allocation reproduces
GG exactly, every player, both chapters — from our data alone.

### Every residual is a known / separate thing — not a tee-math error

- **a9.18 (3 rounds):** Gonzalez, Trejo, Zapata — brand-new Austin players
  with **no handicap history in our system**, so `our_index` is null and the
  full chain can't run. Their allocation still matched GG. → **coverage**,
  not math.
- **s9.17 (4 rounds):** Rideout, South, Watson, White — GG's playing
  handicap is **exactly our value + 1** in every case (our CH 11.51/3.48/
  2.42/3.36 → 12/3/2/3; GG 13/4/3/4). This is the documented policy gap:
  **GG does not apply the WHS net-double-bogey cap** (it treats raw gross as
  adjusted), so GG's differentials — and thus index and playing handicap —
  run ~1 higher on capped players. **Kerry ratified WHS standards 2026-07-14**
  (handicaps.md → Self-derived handicap import), so **our number is the
  intended-correct one; GG's is the legacy uncapped one.**

## What this means for go-live

- **Ratification-ready now:** the tee-based playing-handicap calculation
  (course-handicap formula + allocation). Proven 100% against real GG dots.
- **Net scoring can compute on this** once the index is fully our own — and
  the index difference is already ratified in our favor (WHS cap). Where we
  ever differ from GG on a net line, it will be because we're applying the
  cap Kerry ratified and GG isn't.
- **Gross points** need none of this and are independently ready (raw scores
  + par + the ratified points table).

## Open for CA / next layer (do NOT block the base ratification)

1. **Per-game handicap config** (parked task #16 config): allowance %
   (100 / 85 / …), Max Playing Handicap cap, Team-Net no-pops-on-par-3 —
   as versioned game config, snapshot-frozen per event (principle 4). The
   calc already exposes the `allowance` / `max_hcp` hooks + per-hole
   allocation control.
2. **New-player index coverage:** getting every active player's handicap
   history into our system so `our_index` is never null at event time
   (identity/backfill, not calc).
3. **9-hole slope source confirmation:** the 100% allocation parity confirms
   the tee slope/rating we captured from GG's 9-hole tee block is the right
   one for the course-handicap formula (else allocation would not match).

## Key files
- `email_parser/handicap_calc.py` — pure WHS primitives.
- `email_parser/database.py` — `project_playing_handicaps()` (parity sweep).
- `mcp_server.py` — bridge `scoring-hcp-project:<event>[|<allowance>[|<cap>]]`.
- Tests: `test_handicap_calc.py` (21).
