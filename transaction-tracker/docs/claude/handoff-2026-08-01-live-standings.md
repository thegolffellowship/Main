# Handoff — live City Points standings (session of 2026-07-31 → 2026-08-01)

Written at the end of a long session, the night before the two City
Championships. Everything below is either verified or explicitly flagged as
unverified. Read the **Notes to self** section before touching anything.

---

## THE SESSION PROMPT (paste this to start the new session)

> Continuing TGF Tracker work from the night of 2026-07-31. Read
> `docs/claude/handoff-2026-08-01-live-standings.md` first — it has the full
> state, the verified facts, and the traps.
>
> Context: yesterday (Sat 2026-08-01) both City Championships were played —
> TGF SAN ANTONIO CHAMPIONSHIP at The Quarry and TGF AUSTIN CHAMPIONSHIP at
> Falconhead. I shipped a live championship-points overlay on the member
> LEADERBOARD (v2.174.0/v2.175.0) so players could watch their season total
> update during the round. **First question: did it actually work?** Check
> with me before assuming — the GG fetch from Railway had never been
> exercised end to end.
>
> Then the remaining work, in priority order:
>
> 1. **Live championship points in the player drill-down.** The
>    CITY CHAMPIONSHIP row already accepts `opts.champPoints` /
>    `opts.champThru` (static/js/points-render.js) — nothing feeds them yet.
>    The drill-down is served by `/api/season-contests/points-race/detail`,
>    which I did NOT touch. Wire the live figure through.
> 2. **Hole-by-hole expansion on that row.** Kerry: "those City Championship
>    lines in the player expanded detail should show the live hole by hole
>    results if a player wants to expand them. All that info should be
>    retrievable in the GG live results page." Not started. See
>    **Where the hole-by-hole data lives** below.
> 3. Anything Kerry raises from the day itself.
>
> Standing rules: bump `static/js/version.js` + changelog every commit,
> update `docs/claude/*.md`, and follow the guiding principles in CLAUDE.md —
> especially #6 (`customer_id` is the identity key; this session produced
> four separate bugs from name-keyed lookups).

---

## What shipped (v2.166.0 → v2.175.0, all pushed to main)

| Ver | What |
|---|---|
| 2.166.0 | GG SHEET button — pull an event's pairings off the GG tee sheet |
| 2.167.0 | STARTING handicaps sync ROSTER ↔ PAIRINGS, both editable |
| 2.168.0 | Handicap index map keyed by `customer_id` |
| 2.169.0 | 18-hole TGF MVP day-type rule (Kerry-ratified) |
| 2.170.0 | 3rd-place consolation: change / clear |
| 2.171.0 | 3rd-place match goes LIVE beside the Final |
| 2.172.0 | HIO carry-in write path (**not** the actual bug — see below) |
| 2.173.0 | HIO pot duplicate-`id` fix (the actual bug) |
| 2.174.0 | Live championship points overlay on City Points standings |
| 2.175.0 | City Championship row to top + contrasting; double-count guard |

New tests, all green: `test_gg_pairings_import.py`,
`test_starting_handicap_sync.py`, `test_mvp_18_day_type.py`,
`test_cmp_consolation_undo.py`, `test_hio_carry_in.py`,
`test_champ_points_live.py`.

---

## VERIFIED FACTS (do not re-derive these)

**The member deep links are HASH-based, and they already existed.**
Kerry was right; I said otherwise and was wrong.
- San Antonio → `https://tgf-tracker.up.railway.app/member/contests#race=net`
- Austin → `https://tgf-tracker.up.railway.app/member/contests#race=austin`

Tab keys are `net` / `austin` / `gross` / `tfc` / `monthly` / `fall_sa`
(`data-pr=` in contests.html). The hash restore lives at contests.html ~6063.
`PR_RACE_BY_TAB` (~5365) maps tab → race key: `net→san_antonio_net`,
`austin→austin_net`, `gross→players_cup_gross`.

**The GG championship POINTS boards** (probed live, tables parse cleanly):

| Race | GG game | Tournament URL |
|---|---|---|
| `san_antonio_net` | sChampionship POINTS Net | `tgf-sa…/v2tournaments/4779202?player_stats_for_portal=true&round_index=35` |
| `austin_net` | aChamp POINTS | `tgf-austin…/v2tournaments/4779168?player_stats_for_portal=true&round_index=31` |

Board shape: `Pos. | Player | Stableford Points | Thru`. Blank single-cell
spacer rows between players. Name cell carries the affiliation
(`FIEBER, Wade TGF San Antonio`, `Villa, Mark Guest`). Points read `-`
until a player starts. Stored as a dial:
`app_settings.gg_champ_points_boards`.

**Kerry's ratified rule on how GG behaves** (this is the load-bearing fact):
> "GG does two things. The games I gave you will be live, but it doesn't
> actually award season points without us closing it out and adding them
> after the round is done."

So during the round the season snapshot has NO championship → adding the
live board is correct. After close-out + snapshot refresh, GG's total
already contains it → adding again would double-count. That is exactly what
the v2.175.0 guard handles.

**Other Kerry rulings from this session** (all recorded in the docs):
- 18h multi-event day: no cap, no residual; City $4/buyer + TGF $4/buyer per
  city, TGF halves combine. Single 18h day unchanged (cap $100, excess to
  Individual Net). No mixed-format TGF MVPs. No course-difficulty adjustment.
- Winner-takes-all 3rd place was already the behaviour; the even split is
  only the fallback for an unplayable match.

---

## UNVERIFIED — check these first

1. **`fetch_champ_points` has never run end to end.** This container's
   network is blocked from golfgenius.com (proxy 403); I could only reach GG
   through the `probe_golf_genius` MCP tool, which runs on Railway. The
   PARSER is verified against the real table structure, but the fetch +
   resolve + merge path has only ever run against fixtures.
2. **The GG boards may render differently to a logged-out fetch** than to
   the probe. If the LIVE banner never appeared, that is suspect #1 — check
   Railway logs for `fetch_champ_points`.
3. **The double-count guard's `fetched_at` key.** I originally wrote the
   guard against `last_synced`/`synced_at`, which do not exist — it was a
   silent no-op. Corrected to `base["fetched_at"]` (database.py ~7658) and
   the truth table was verified, but only in isolation, not against a real
   post-close-out snapshot.

---

## Where the hole-by-hole data lives (for item 2)

Not yet explored in depth. Leads, best first:

- `cmp_fetch_live_match(chapter, a, b)` (database.py ~28871) already walks a
  GG tournament_results widget and returns **per-hole detail** for a match —
  `holes[]` with `p1_gross`/`p2_gross`, `thru`, `n_holes`. That is the
  closest working precedent for pulling live hole data out of GG, and it
  proves the route is reachable.
- `import_gg_scorecards(widget_url, …)` walks full scorecards into
  `scoring_rounds` / `scoring_holes` — but that is an IMPORT (writes), and
  during a live round you want a read-only cached fetch like
  `fetch_champ_points`, not a write path.
- The `ALL Net 18` board on each portal (SA `v2tournaments/4779120`,
  Austin `4779165`) is the likely source for a per-player live card.
- `live_scoring.py` computes Stableford from raw gross hole scores. If we
  can get the holes, we can show points per hole without trusting GG's math.

**Design note:** whatever you build, cache it server-side per player like
`_CHAMP_POINTS_CACHE` does (45s). An expand-per-player that hits GG directly
would hammer the portal if a whole roster opens their card at once.

---

## NOTES TO SELF — read before writing any code

**I got two diagnoses wrong tonight. Both times the pattern was the same:
I found a real defect and declared it the cause without checking whether it
explained the actual symptom.**

1. **HIO pot "not persisting."** I found that `hio_pot_carry_in` had no
   write path anywhere — true, and worth fixing — and shipped v2.172.0
   saying that was why the pot vanished. It wasn't. Kerry: *"That's
   incorrect. We had worked on this. $3101 would show for a bit, but would
   just disappear."* The real cause was a duplicate HTML `id` — the page
   renders each panel twice (desktop table + mobile list) and
   `getElementById` filled the hidden copy. **"Shows then disappears" is a
   render/race symptom, not a persistence symptom.** I should have heard
   that in the first message.

2. **Almost shipped a double-count** on member-facing points because I
   assumed GG awarded season points live. Kerry corrected me. **Ask how the
   upstream system behaves before building on top of it.**

**The `customer_id` lesson, four times in one session.** Name-keyed lookups
caused: the missing Moreno/Murphy points, the handicap that wouldn't sync
between ROSTER and PAIRINGS, the standings order matching nobody, and the
GG champ-board matching. Every single one. Guiding principle 6 exists
because of exactly this. **When any two screens disagree about a person,
suspect the name key first.**

**The events page renders every panel TWICE.** `#events-body` (desktop) and
`#events-mobile-cards` (mobile), CSS hides one. **Never use a bare `id` in a
per-event panel** — use a data attribute and paint every match. I checked
the rest of the panels; the two HIO lines were the only offenders, but new
code can reintroduce it trivially.

**Silent `.catch(() => {})` is how these bugs hide.** Three separate
failures this session were invisible because a rejected fetch rendered
nothing rather than an error: the pairing-mode save, the HIO running line,
and the index-map refresh. A 500 and a still-loading state must never look
identical.

**Don't trust a matrix seed file.** `static/js/games-matrix.js` is a SEED;
the live matrix comes from `app_settings` and overrides it wholesale. A new
column added to the seed is simply absent in production — which is why the
18h MVP split is DERIVED from the buyer count at runtime, with matrix values
winning where present.

**Things I flagged but did not change** (get Kerry's call):
- `get_hio_pot` returns `running` (per-event, does NOT subtract payouts) and
  `pot` (does). The GAMES banner uses `running`, the FINANCIAL panel uses
  `pot`. They diverge by exactly `paid_out` the moment an ace is paid.
- `hio_27h_event_patterns` and `hio_player_count_overrides` are read but have
  no write path — same gap as the carry-in had.
- The generator's server-side `hcp_map` excludes STARTING handicaps, so ABCD
  banding and the pace tie-break can't see them. Works against Kerry's stated
  purpose ("it lets them be flighted").
- The 18h games matrix has no multi-event rows, so the Individual Net place
  ladder is scaled proportionally at render time on a two-championship day.
  Totals are exact; the ladder is derived. Adding real rows to the matrix
  generator is the authoritative fix.

**Working style that paid off:** reproducing a bug before fixing it. The HIO
duplicate-`id` fix was written against a jsdom harness that replays Kerry's
exact "shows then disappears" sequence — old code fails all three steps, new
code passes. Do that again where the symptom is behavioural.

**Environment gotchas:** local `transactions.db` is EMPTY (live data is on
Railway); the `tgf-transactions` MCP is the only way to see production. This
container cannot reach golfgenius.com directly — use `probe_golf_genius`.
`create_trigger` / `send_later` need approval that a non-interactive session
cannot grant, so scheduled follow-ups can't be armed from here.
