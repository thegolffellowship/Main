# Live Scoring & Flighting — end-to-end spec for CA

**Author:** tracker-claude · **Date:** 2026-07-30 · **Versions:** v2.150.0 → v2.151.3
**Status:** built and live (admin-only); **not** yet proven at a real event.

Companion docs: `live-scoring-test-center.md` (implementation detail),
`game-engine.md` (the untether staging this serves), `side-games.md` (the
ratified game rules), `runbook-sa-championship-2026-08-01.md` (first live use).

This is the source material for CA's end-to-end documentation. It states what
is RATIFIED, what is BUILT, and what is still UNKNOWN — those three are
deliberately kept apart, because most of the risk lives in the third bucket.

---

## 1. Why this exists

`game-engine.md` defines a three-stage untether from Golf Genius:

| Stage | Meaning | Status |
|---|---|---|
| 0 | GG is the official scorer; we import and verify | done, long-standing |
| 1 | **Shadow leaderboard** — GG supplies ONLY raw gross hole scores; we compute every game and diff until we reproduce GG exactly | **harness built, parity not yet proven at a real event** |
| 2 | Own score entry — customers enter scores, GG leaves the loop | not started |

That doc named the missing pieces as *"the leaderboard surface + the diff
harness."* Both now exist as the **Live Scoring Test Center**
(`/admin/test-center`, admin-only).

**GG remains the official scorer.** Nothing on this surface changes a score, a
payout, or a member-facing page.

---

## 2. What was already ours, and what was not

Worth stating plainly, because it reframes how much of the untether was
actually left:

**Already ours before this work.** Net and gross Stableford, the WHS
net-double-bogey adjusted gross, the raw-ace rule, WHS stroke allocation,
MVP determination, match play, season payouts, per-game flight *capture* from
GG. All of it computes from our own tables through
`get_scoring_formulas()` / `compute_hole_derivations()`.

**Not ours: the FLIGHTING RULE.** `determine_event_game_results` computes
every game and then takes GG's flight labels, returning
`status: "flights_unknown"` when they are absent rather than guessing (Kerry,
2026-07-07). That was the single remaining tether on event scoring — and it
is the rule that decides *who gets paid*.

So the honest summary of this wave: **the scoring was already untethered; the
flighting was not, and now has a rule.**

---

## 3. The engine (`email_parser/live_scoring.py`)

Pure — no DB, no Flask — following the `match_play.py` / `season_payouts.py`
pattern, so it unit-tests in isolation and ports to the Platform unchanged.

It deliberately does **not** reimplement two pieces of shared math, because
duplicating them would defeat the parity harness it exists to feed:

- `compute_hole_derivations` — the formula layer (injected as `derive_hole`,
  lazy-imported by default, so the engine imports with no DB module present)
- `handicap_calc.allocate_strokes` — WHS stroke allocation

**Input** is a plain-data round state: holes (`hole`, `par`, `yardage`,
`stroke_index`) and players (`key`, `customer_id`, `name`,
`playing_handicap`, `flight`, `team`, `buys_net`, `buys_gross`, `is_member`,
`scores`, optional `strokes_received`).

**Output** is every game plus an overall board and per-player derived cards.

### Games computed

| Game | Rule (all from the ratified side-games spec v1.0) |
|---|---|
| Individual Net | Flighted net Stableford. Flights 1→11 buyers, 2 at 12+ (9h); 1/2/3/4 at 13/33/49/64 (18h) |
| Individual Gross | Flighted gross Stableford. Activates at **16 buyers (9h) / 12 (18h)** — LIVE matrix values, not the stale Excel seed's 20/16. Minimum 3 flights |
| Team Net | Foursomes, one best NET ball per hole vs par. `no_pops_on_par3` is a config toggle, shipped OFF |
| Skins | Gross, outright low score within flight. Flights at 8+. Below 8 on a nine the matrix runs **Skins ½ Net** — a different game, reported not faked |
| MVP | Highest net Stableford among NET buyers; tiebreak net → gross → split |
| CTP | Max 2 per nine; more par-3s than slots → the **shortest** chosen; fewer → leftover becomes **Longest Putt on the last hole** |
| HIO | Raw ace (gross == 1); members-only eligible to win |

Every threshold is data in `SEED_LIVE_SCORING_CONFIG`. Nothing is hard-coded
(Guiding Principle 2).

### Behaviours that matter

- **Dots: given vs derived.** Supplied `strokes_received` are used verbatim,
  so a GG-seeded card keeps GG's own dots and a parity diff isolates the
  *scoring* math from the *allocation* math. Absent, they derive from the
  playing handicap — the Stage-2 behaviour. Each card reports which happened
  via `allocation_source`.
- **MVP is decided on POINTS, not low net.** A bogey golfer off a 14 beats an
  even-par 4-handicap 14 to 13, because two pops on five holes turns bogeys
  into net birdies. The engine must not "correct" that; it is pinned by test.
- **MVP incomplete-card guard** mirrors `determine_tgf_mvp` including Kerry's
  s9.20 catch: a short card leaves the result provisional while its player
  could still catch the leader. A mathematically eliminated card does not block.
- **Nothing is silently faked.** Short teams warn the ratified blind draw is
  not generated; sub-8 skins warn the real game is Skins ½ Net; a field with
  no pairings warns rather than inventing teams.

---

## 4. The flighting rule (Kerry, 2026-07-29) — `SEED_FLIGHT_CONFIG`

### RATIFIED

1. **Flight on the raw TGF handicap index**, not the playing handicap.
2. **Two legitimate modes**: equal-size groups (traditional) and fixed bands
   (the recent trend). Ideal is fixed bands that also come out even; real
   fields do not cooperate. Both ship; mode is per game.
3. **Breaks are floors for the upper flight.** 12.0 goes UP; 11.9 tops the
   flight below. No value is claimed by two flights ("no shared break").
4. **Individual Net** splits near the middle, but the low flight **never runs
   past 11.9** — a ceiling on the break, not the break itself.
5. **Gross bands harder** (a high index has little chance in a low flight) and
   runs a **minimum of three flights** whenever active, for entry incentive.
6. **Skins** goes ½ Net at low counts; **Individual Gross** does not run at
   all at low counts.
7. **Players Cup** bands `<6` / `6–11.9` / `12–17.9` / `18+` are fixed for the
   foreseeable future; revisit at 4-stroke brackets from 6 only at much
   higher participation.
8. **Flight count may be skewed DOWN** when indexes are concentrated (3 → 2).

### DERIVED (engine decisions, not Kerry's words — flag for ratification)

- **Equal indexes never split across flights.** Two players on the same index
  in different flights is the one outcome that cannot be defended, so a cut
  landing inside a tie group slides to an edge: whichever leaves counts
  evener, dead heat going UP (consistent with 12.0-goes-up).
- **Thin flights merge into their neighbour** at a minimum flight size.
  This independently reproduces Kerry's rule 8 — a concentrated field leaves a
  band nearly empty, it merges, and the 3-flight event becomes a 2-flight
  event with no judgment call. An *empty* band simply does not appear.
- Every decision returns a note (boundaries, tie slides, ceiling moves,
  merges) so the reasoning is visible rather than implied.

### UNKNOWN — must be ratified before this drives money

| # | Question | Risk if wrong |
|---|---|---|
| 1 | **Is the index the 9-hole or 18-hole number?** We store both (`handicap_index`, `handicap_index_18` = ×2). The 11.9 ceiling and the Players Cup ladder are on the same scale as each other, but which one is unconfirmed | **Factor-of-two mis-flight of the entire field, silently** — the output looks perfectly plausible. Exposed as `index_scale`, never assumed |
| 2 | **Minimum flight size** (default 3) | Degenerate flights; a flight of 1 is a bye with a prize |
| 3 | **Band ladders at 3 and 4 flights.** Only the 2-flight Net line (≤11.9 / 12.0+) is ratified; the 4-flight ladder is borrowed from the Players Cup, the 3-flight one inferred | Wrong cut lines → wrong winners |
| 4 | **Uneven bands + equal pot split.** See §5 | Cross-subsidy between flights |
| 5 | **Late add / WD scenarios.** See §6 | Money and eligibility disputes on the day |

---

## 5. Pot split across flights — analysis, Kerry's call pending

Kerry asked: with fixed bands and vastly uneven counts, do we prorate the pots?

**The ratified matrix already splits EQUALLY per flight**, not by size —
`side-games.md`: gross flight payout is "flight pot = pot÷flights,
winner-take-all"; Players Cup is "90% ÷ 4 flights". So proration would be a
reversal, not an adoption.

Kerry's concern was that thin bands deter entry. **Proration is what creates
that deterrent**, not equal split. At 20 net buyers, ~$400 to Individual Net,
2 flights split 15/5:

| | Fat flight (15) | Thin flight (5) |
|---|---|---|
| Equal split | $200, 1-in-15 | $200, 1-in-5 |
| Prorated | $300, 1-in-15 | $100, 1-in-5 |

Equal split is the anti-deterrent: the thin band plays for the same money with
fewer opponents. It does cross-subsidise, but **nobody chooses their flight** —
it is set by index — so the imbalance cannot be arbitraged. It becomes EV
variance by band that washes out across a season. A cross-subsidy you cannot
game is a far smaller problem than a payout line reading "$100" that makes
someone skip the next event.

**Recommendation (tracker-claude): keep equal split; fix the imbalance
upstream via the minimum-flight-size merge.** The failure mode is not the
money split, it is letting a band get pathologically small.

**Still needed from Kerry:** the minimum flight size, and the Canyon Springs
numbers (field size, bands used, resulting counts) as the case to encode against.

---

## 6. Flights freeze, money floats — scenario matrix (partly ruled)

Kerry's stated principle: *no re-flighting on late WDs, but money gets
adjusted; late adds add money and potentially flights.* Stated as a rule:
**flighting locks at a moment; the pot is always computed at settlement from
who actually bought in.**

Note the tracker **already has a ratified WD money rule**: `_event_game_buyers`
reads `wd_credits` — a WD whose bundle was credited back stops being a buyer;
a WD not credited stays one. Keep that; do not invent a parallel rule.

| # | Scenario | Proposal | Status |
|---|---|---|---|
| 1 | WD before lock | Gone; re-flight normally | proposed |
| 2 | WD after lock, credited | Out of pot and standings; flights unchanged | proposed |
| 3 | WD after lock, not credited | Money stays in; cannot win | proposed |
| 4 | WD mid-round | As 3 + partial card excluded | proposed |
| 5 | Late add before lock | Normal; may change flight count | proposed |
| 6 | Late add after lock, fits a band | Joins it; money in; no re-flight | proposed |
| 7 | **Late add crossing a flight-count threshold** (15→16 gross = 3→4 flights) | **Kerry's call** — hold at locked count, or re-flight? Direct collision between "flights freeze" and "adds can add flights" | **OPEN** |
| 8 | **Late add landing in a merged-away band** | Un-merge if it now clears the minimum, or stay merged? | **OPEN** |
| 9 | No-show, never withdrew | Money in, no card, no win | proposed |
| 10 | Started but did not complete | Incomplete card blocks MVP as provisional; same for Net/Gross, or just no placing? | **OPEN** |

**Lock moment proposed:** publishing the tee sheet. Not ratified.

---

## 7. The parity gate

`ls_parity(session_id)` diffs our engine against GG per player across `gross`,
`net`, `playing_handicap`, both Stableford totals, and — where we derived the
dots ourselves — the per-hole stroke allocation.

Two properties make it trustworthy:

- **A null on the GG side is SKIPPED, never counted as a match.** A thin GG row
  cannot manufacture a clean report; `parity` is false when nothing was checked.
- **The gate can fail.** The test suite corrupts a stored score and asserts
  parity breaks, that exactly one player is flagged, and that the diff names
  the fields that moved. A parity report that cannot fail is worthless.

Parity is refused outright on a synthetic session — no GG numbers to diff.

**Flighting is graded separately** by the Flighting Lab, against
`gg_game_flights` (per-game membership captured from each flighted game's own
GG leaderboard), **by partition rather than by label**, since GG may name
flights differently while cutting in the same places. This is how the rule
gets derived from what was actually done across past events rather than from
recollection — the recommended next analysis.

---

## 8. Two corrections worth recording

Both were errors in earlier tracker-claude reporting, caught by Kerry:

1. **"The importer does not capture GG flights."** False. `gg_game_flights` +
   `import_gg_game_flights` (bridge `scoring-flights-import`) walk each
   flighted game's own GG leaderboard — Ind Net / Ind Gross via detail
   fragments, Skins via Expand-All. The earlier check looked at
   `scoring_rounds.flight`, which is NULL everywhere because it is the
   **legacy single-label fallback**: flights differ per game, so one label per
   round cannot be right. **Read the per-game table, never the column.**

2. **"We only have The Quarry's back nine."** False. TGF plays nines and GG
   rates each nine separately, so one physical tee becomes several
   `course_tees` rows each holding only its own nine. Quarry "1 - Gold Tee" is
   tee 109 (117/34.2, holes 1–9, ODD stroke indexes) **and** tee 592
   (128/35.6, holes 10–18, EVENS) — together a complete 1–18. Reading a single
   `tee_id` returns half a golf course. `_ls_tee_holes` now merges across tee
   rows sharing course + tee name.

**Generalisable lesson for CA:** at a nines-playing club, *any* per-tee lookup
that assumes one row per tee is wrong, and *any* per-round flight label is
wrong. Both are shape errors, not data errors, and both fail silently.

---

## 9. TGF handicap scoping (Kerry, 2026-07-29)

Two rules pulling in different directions, both true:

1. **Course / playing handicaps come off the 18-HOLE rating and slope and
   apply across all 18 holes.** The merged 1–18 stroke index above is exactly
   what that needs.
2. **Handicap DIFFERENTIALS are computed from the 9-HOLE ratings and indexes.**
   That is the posting path (`handicap_rounds`, `handicaps.md`); this surface
   does not touch it.

Consequence: we do **not** hold a true 18-hole rating/slope row for The Quarry
(both existing rows are nine-rated). Moot on a GG-seeded session — GG supplies
each playing handicap — but it blocks fully untethered Stage-2 scoring, where
we would compute the playing handicap ourselves. GG publishes the 18-hole tee
block with the event and the import accretes it.

---

## 10. Data model (sandbox only)

Lazily created (`_ensure_live_scoring_tables`, the `_ensure_pairing_tables`
pattern) so live deployments self-migrate and `init_db`'s boot path is untouched.

```
ls_test_sessions      id, name, source_kind ('synthetic'|'seeded'), event_id,
                      event_name, round_date, course_id, tee_id, holes,
                      championship, notes, created_by
ls_test_players       session_id, customer_id FK, player_name,
                      playing_handicap, handicap_index, flight, team_num,
                      buys_net, buys_gross, is_member, source_round_id FK
ls_test_holes         session_id, player_id, hole_number, strokes,
                      strokes_received
ls_test_course_holes  session_id, hole_number, par, yardage, stroke_index
ls_test_contests      session_id, kind ('ctp'|'longest_putt'|'hio'),
                      hole_number, player_id, customer_id FK, note
```

Per Guiding Principle 6 every table referencing a person carries `customer_id`
as an FK, and a player linked to a customer takes the **canonical** name.

**Isolation is the contract.** Seeding READS `scoring_rounds` /
`scoring_holes` / `items` / `event_pairings` and writes only `ls_test_*`.
Deleting a session touches nothing outside the sandbox. Asserted by
production row counts after a full seed-and-delete cycle.

**Platform portability:** the engine is pure and rules-as-data; the flight
config and game config are JSON-shaped and would serialise into
`season_contests.scoring_config` / a `game_template_versions.config_json`
unchanged. All identity by `customer_id`, which maps 1:1 to `users.user_id`
at Stage 4.

---

## 11. Surfaces

All admin-only. `/admin/test-center`, five tabs:

| Tab | Purpose |
|---|---|
| Leaderboard | Every game from raw scores; 10s live re-render; **Pull from GG**; course-coverage banner |
| Score Entry | Type a gross score, whole board recomputes (Stage-2 write path in miniature); autoplay simulation |
| Field & Course | Handicaps, teams, flights, buyer flags, member status, par/yardage/stroke index, championship toggle |
| Flighting Lab | Both modes side by side on the real field; min-flight-size / index-scale / tie-direction as live controls; graded vs GG |
| Parity vs GG | The Stage-1 confidence gate |

Key API: `GET|POST /api/test-center/sessions`, `POST …/<id>/refresh` (live GG
re-pull, in place), `GET …/<id>/leaderboard`, `GET …/<id>/parity`,
`GET /api/test-center/flight-lab`.

**Live refresh semantics** — chosen so a mid-round pull cannot destroy manager
work: scores, dots and playing handicaps come from GG every pull; teams,
flight overrides, buyer flags, member status, championship toggle and recorded
CTP/LP/HIO are preserved. A player who disappears from GG is **kept** (GG
re-keys aggregate ids mid-round; silently dropping a player mid-event is worse
than a stale row). A GG fetch failure leaves the last good board standing.

**Course coverage guard** — a hole with no par derives nothing, so it scores
ZERO in every game while looking normal, making a half-scored board
indistinguishable from a low-scoring one. Reported as `course_coverage`;
holes that already have scores but no par render a red "the board is WRONG"
banner; a missing stroke index warns that NET games are *wrong*, not merely
incomplete.

**Pre-event seeding** — an event with no cards seeds from its active
registrations (buyer flags from purchases, guests flagged not-a-member, teams
from pairings, course tee from what the field usually plays). Scores arrive on
the day via Pull from GG. Without this the pre-flight was impossible: only
already-played events could be shadowed.

---

## 12. Test coverage

- `test_live_scoring.py` — ~95 engine assertions, incl. the flighting rule
  (tie-group invariant, 11.9 ceiling, concentration collapse) and 500 random
  fields proving every player lands in exactly one flight with no overlap.
- `test_live_scoring_center.py` — ~120 integration assertions, incl. the parity
  gate, a deliberately corrupted score proving the gate can fail, the Quarry
  half-scored-board failure, per-nine tee merge in both directions, every class
  of manager edit surviving a GG refresh, and pre-event seeding from
  registrations.

---

## 13. What CA should carry forward

1. **The rule set in §4 is the first flighting specification in TGF's
   documentation.** It should live alongside the side-games spec as a peer,
   not inside it — flighting is cross-game and has its own vocabulary.
2. **The three-bucket discipline** (ratified / derived / unknown) should
   survive into CA's version. The derived items in §4 are engine decisions
   that *look* like rules; if they are documented as ratified, the ratification
   step is silently skipped.
3. **§8's two corrections generalise.** Per-tee and per-round assumptions both
   fail silently at a nines-playing club. Worth a standing note in any
   scoring/course documentation.
4. **The pot-split analysis in §5** is a money decision with a recommendation
   attached and no ruling. It should not be presented as settled.
5. **Open items requiring Kerry**: index scale (blocking), minimum flight size,
   3-/4-flight ladders, pot-split confirmation, scenarios 7/8/10, lock moment,
   Canyon Springs numbers.

---

## 14. Status against the Stage-1 gate

**Not yet passed.** The harness exists and is self-tested; it has never been
run against a live event. First attempt is the SA Championship, Sat 2026-08-01
at The Quarry (18 holes, ~30 registered) — see the runbook for the pre-flight
and the disagreements worth recording.

Until parity reads clean across a meaningful sample of real events, GG stays
official and none of this drives money.
