# Live Scoring Test Center (v2.150.0)

Admin sandbox at `/admin/test-center` that builds the **Stage 1** surface
from `docs/claude/game-engine.md`:

> **Stage 1 — parallel shadow leaderboard.** Rely on GG for ONLY the raw
> gross hole scores; compute EVERYTHING ourselves (all games, all races)
> from those. Stand a live leaderboard next to GG's at a real event and
> diff, game-by-game and race-by-race, until we reproduce GG exactly. GG
> stays official; we shadow. This is the confidence gate.

That doc also names what was missing: *"the only genuinely new build for
Stage 1 is the leaderboard surface + the diff harness."* This is both, plus
a simulator so the live surface can be exercised without waiting for a
Saturday.

**GG stays official.** Nothing here changes a score, a payout, or a member-
facing page. It exists to earn the right to stop asking GG.

## The three things it does

1. **Shadow a real event.** Clone an event's imported scorecards into a
   sandbox session, recompute every game from the raw gross scores, and
   diff the result against what GG recorded.
2. **Live score entry.** Type a gross score into any cell; the whole board
   recomputes. This is the Stage-2 write path in miniature.
3. **Simulate.** Autoplay a synthetic field through a chosen hole so the
   live leaderboard has something to move.

## Files

| File | Role |
|---|---|
| `email_parser/live_scoring.py` | Pure engine — every game, no DB/Flask |
| `email_parser/database.py` (`ls_*`) | Sandbox tables + state building |
| `app.py` (`/api/test-center/*`) | Admin-only routes |
| `templates/test_center.html` | The four-tab page |
| `test_live_scoring.py` | 63 engine assertions |
| `test_live_scoring_center.py` | 57 integration assertions incl. the parity gate |

## The engine

`live_scoring.py` follows the `match_play.py` / `season_payouts.py` pattern:
pure, no DB or Flask, unit-testable in isolation, Platform-portable.

It does **not** reimplement two pieces of shared math — reimplementing
either would defeat the parity harness it exists to feed:

- **The formula layer** — `compute_hole_derivations` (net/gross Stableford,
  WHS net-double-bogey adjusted gross, the raw-ace rule). Injected as
  `derive_hole`, defaulting to a lazy import, so the engine still imports
  cleanly with no database module present.
- **WHS stroke allocation** — `handicap_calc.allocate_strokes` (hardest
  holes first by stroke index, max 2 pops/hole, plus handicaps give a
  stroke back on the easiest holes).

### Rules are data

Every threshold lives in `SEED_LIVE_SCORING_CONFIG`, transcribed from the
RATIFIED side-games spec v1.0 (`docs/claude/side-games.md`). Nothing is
hard-coded (Guiding Principle 2):

| Game | Encoded rules |
|---|---|
| Individual Net | Flights: 1 to 11 buyers, 2 at 12+ (9h); 1/2/3/4 at 13/33/49/64 (18h). 9h two-flight break at **HCP 12.0** (the observed GG split) |
| Individual Gross | Activates at **16 buyers (9h) / 12 (18h)** — the LIVE matrix values, not the stale Excel seed's 20/16. 3 flights in the low band, 4 above |
| Team Net | Foursomes, one best NET ball per hole vs par. `no_pops_on_par3` is a config toggle, shipped OFF |
| Skins | Gross, outright low score within flight; flights at 8+ (9h). Below 8 the matrix runs **Skins ½ Net** — a different game, reported not faked |
| MVP | Highest net Stableford among NET buyers; tiebreak net → gross → split |
| CTP | Max 2 per nine; more par-3s than slots → the **shortest** are chosen; fewer → the leftover becomes a **Longest Putt on the last hole** |
| HIO | Raw ace (gross == 1); members-only eligible to win |

### Behaviours worth knowing

- **Dots: given vs derived.** Supplied `strokes_received` are used verbatim
  (a GG-seeded card keeps GG's own dots, so a parity diff isolates the
  *scoring* math from the *allocation* math). Absent, they are derived from
  the playing handicap — the untethered Stage-2 behaviour. Every card
  reports which happened via `allocation_source`.
- **MVP incomplete-card guard.** Mirrors `determine_tgf_mvp` exactly,
  including Kerry's s9.20 catch: a card short of a full round leaves the
  result provisional while its player could still catch the leader (max 9
  pts/hole on the adjusted championship scale). A mathematically eliminated
  unfinished card does *not* block the result.
- **The MVP is decided on POINTS, not low net.** A bogey golfer off a 14
  beats an even-par 4-handicap 14 points to 13, because 2 pops on five
  holes makes bogeys into net birdies. The engine must not "correct" that;
  `test_live_scoring_center.py` pins it.
- **Nothing is silently faked.** Short teams warn that the ratified blind
  draw isn't generated; sub-8-buyer skins warn that the game that would
  actually be paid is Skins ½ Net; a field with no pairings warns rather
  than inventing teams.

## The parity gate

`ls_parity(session_id)` diffs our engine against GG per player across
`gross`, `net`, `playing_handicap`, both Stableford totals, and — where we
derived the dots ourselves — the per-hole stroke allocation.

Two properties make the report trustworthy:

- **A null on the GG side is SKIPPED, never counted as a match.** A thin GG
  row cannot manufacture a clean report; `parity` is false when nothing was
  checked.
- **The gate can fail.** `test_live_scoring_center.py` corrupts one stored
  score and asserts parity breaks, that exactly one player is flagged, and
  that the diff names the fields that moved. A parity report that cannot
  fail is worthless.

Parity is refused outright on a synthetic session — there are no GG numbers
to diff against.

## Live use at a real event (v2.150.1)

Seeding is a **snapshot**. `ls_refresh_session_from_gg(session_id,
tournament_url)` is what makes the board move during a round: it re-imports
from GG (reusing `import_gg_scorecards`, whose completeness rule replaces a
partial card with a fuller one when GG re-keys aggregate ids mid-round) and
re-syncs the session **in place**.

Refresh semantics are chosen so a mid-round pull can never destroy manager
work:

| From GG, every pull | Preserved across pulls |
|---|---|
| Hole scores (replaced wholesale) | Team assignments |
| Handicap dots | Flight overrides |
| Playing handicaps | Buyer flags, member status |
| `source_round_id` | Championship toggle |
| New players who appear | Recorded CTP / Longest Putt / HIO |

A player who **disappears** from GG is kept, not dropped — a card pulled
mid-round can vanish when GG re-keys, and silently removing a player
mid-event is worse than a stale row. A GG fetch failure returns an error and
leaves the last good board standing.

Refresh also re-accretes the course: an 18-hole tee block published
mid-event fills holes the session was seeded without, and only fills gaps
(`COALESCE`) so hand-typed par is never overwritten.

### Course coverage — the silently-half-scored board

`course_coverage` on the leaderboard payload is the guard against this
surface's most dangerous failure. **A hole with no par derives nothing** —
no vs-par, no Stableford, no net — so it scores zero in every game while
looking completely normal. A half-scored leaderboard is indistinguishable
from a low-scoring one.

The live example is **The Quarry**: TGF has only ever played its BACK nine,
so holes 1–9 carry no par or stroke index on any Quarry tee. An 18-hole
round there would silently score nine holes.

Coverage reports three things, escalating:

- `missing_par` — holes that will score zero the moment anyone posts there.
- `scored_but_no_par` — holes that **already have scores** and are
  contributing nothing. Renders as a red "the board is WRONG" banner.
- `missing_stroke_index` — dots cannot be allocated, so every NET game is
  *wrong*, not merely incomplete.

Championship events auto-select the +1-per-net-category schedule from the
event name (Principle 1: derive, don't ask); the Field tab still overrides.

## Data model (sandbox only)

Lazily created by `_ensure_live_scoring_tables` (the `_ensure_pairing_tables`
pattern) so live deployments self-migrate on first use and `init_db`'s boot
path is untouched.

```
ls_test_sessions      id, name, source_kind ('synthetic'|'seeded'), event_id,
                      event_name, round_date, course_id, tee_id, holes,
                      championship, notes, created_by
ls_test_players       session_id, customer_id FK, player_name,
                      playing_handicap, flight, team_num, buys_net,
                      buys_gross, is_member, source_round_id FK
ls_test_holes         session_id, player_id, hole_number, strokes,
                      strokes_received
ls_test_course_holes  session_id, hole_number, par, yardage, stroke_index
ls_test_contests      session_id, kind ('ctp'|'longest_putt'|'hio'),
                      hole_number, player_id, customer_id FK, note
```

Per Guiding Principle 6 every table referencing a person carries
`customer_id` as an FK to `customers(customer_id)`, and adding a player with
a `customer_id` takes the **canonical** name over whatever was typed.

**Isolation is the contract.** Seeding READS `scoring_rounds` /
`scoring_holes` / `items` / `event_pairings` and writes only `ls_test_*`.
Deleting a session touches nothing outside the sandbox. The integration test
asserts production row counts are unchanged after a full seed-and-delete
cycle.

## API (all admin-only)

| Route | Purpose |
|---|---|
| `GET /admin/test-center` | The page |
| `GET/POST /api/test-center/sessions` | List / create (synthetic or `seed_from_event`) |
| `GET/PATCH/DELETE /api/test-center/sessions/<id>` | Full state / rename+flags / delete |
| `POST /api/test-center/sessions/<id>/players` | Add a player |
| `PATCH/DELETE /api/test-center/players/<pid>` | Edit / remove |
| `POST /api/test-center/sessions/<id>/score` | One hole, one player (1–20 validated) |
| `POST /api/test-center/sessions/<id>/hole` | Edit par / yardage / stroke index |
| `POST /api/test-center/sessions/<id>/autoplay` | Simulate through a hole |
| `POST /api/test-center/sessions/<id>/clear-scores` | Wipe scores |
| `POST /api/test-center/sessions/<id>/refresh` | Re-pull from GG in place (live) |
| `POST /api/test-center/sessions/<id>/contest` | Record CTP / Longest Putt / HIO |
| `GET /api/test-center/sessions/<id>/leaderboard` | Every game |
| `GET /api/test-center/sessions/<id>/parity` | The gate |
| `GET /api/test-center/scorable-events` | Seedable events |

## Not built yet

Deliberate gaps, each surfaced in the UI rather than silently wrong:

- **Payouts.** The board ranks; it does not pay. The prize matrix and
  `season_payouts.py` are the obvious next join.
- **Skins ½ Net** (the sub-8-buyer 9-hole game) — detected and reported,
  not computed.
- **Blind draw** for short teams (`Bl[Name]`) — warned, not generated.
- **Match Play** — already live on its own surface (`MATCHPLAY_V2`,
  `cmp_fetch_live_match`) and deliberately not duplicated here.
- **Flighting parity is itself an open question.** The 9-hole 2-flight break
  at HCP 12.0 is the one directly observed GG split; every other band falls
  back to equal-size splitting. Explicit per-player flights override both,
  which is how a known-good GG flighting gets pinned so the scoring diff
  isolates cleanly. Discovering GG's real rule at other counts is one of the
  things this harness is for.
- **Season-race points** — the leaderboard is per-round; race accumulation
  (best-10 + City Championship) still runs off the existing points-race path.

## Ratification status (rule 3b)

The Test Center is admin-only and touches no money, no member-facing
surface, and no production scoring row — so it ships under normal judgment.
Two items still want Kerry's explicit sign-off before they travel further:

1. **The `ls_test_*` schema addition.** Additive, sandbox-prefixed, lazily
   created, but schema is a rule-3b category.
2. **Any move from shadow to official.** Stage 2 (own score entry, GG out of
   the loop) is a member-facing and money-affecting change and must not be
   taken on a green parity report alone.
