# Handoff — live City Points standings (session of 2026-07-31 → 2026-08-01)

Written at the end of a long session, the night before the two City
Championships. Everything below is either verified or explicitly flagged as
unverified. Read the **Notes to self** section before touching anything.

---

## THE SESSION PROMPT (paste this to start the new session)

> Continuing TGF Tracker work from the overnight session of 2026-07-31
> (v2.166.0 → v2.175.0). Read
> `docs/claude/handoff-2026-08-01-live-standings.md` IN FULL before doing
> anything — especially the **OUTSTANDING** section (18 items) and **NOTES
> TO SELF**. Nothing on that list may be silently dropped: if you don't
> work an item this session, say so and carry it forward.
>
> Context: Saturday 2026-08-01 both City Championships were played — TGF
> SAN ANTONIO CHAMPIONSHIP at The Quarry, TGF AUSTIN CHAMPIONSHIP at
> Falconhead. The live championship-points overlay on the member
> LEADERBOARD shipped the night before and had NEVER been exercised end to
> end from Railway.
>
> Work order:
>
> 1. **Did the live overlay work?** Ask Kerry / check Railway logs for
>    `fetch_champ_points` before assuming anything. The orange LIVE banner
>    appearing = it worked.
> 2. **Ledger duplicates (money, do early):** collapse the two KNOWN
>    double-counted Venmo income pairs (Jeff Young $50: `ext-pay-2195` +
>    `exp-promoted-1540`; Julius Jenkins $219: `ext-pay-2140` +
>    `exp-promoted-1480`) via /admin/duplicate-detective, and check whether
>    Larry Anthis's $30 (`addon-2491`, Venmo handle `Larry-Anthis`,
>    cid 41) has now ALSO duplicated — nothing was watching it.
> 3. **Live championship points into the player drill-down.** The
>    CITY CHAMPIONSHIP row already accepts `opts.champPoints` /
>    `opts.champThru` (static/js/points-render.js); the drill-down endpoint
>    `/api/season-contests/points-race/detail` was NOT touched. Wire it.
> 4. **Hole-by-hole expansion on that row** (Kerry's ask, not started) —
>    see "Where the hole-by-hole data lives" in the handoff.
> 5. **Refresh `docs/claude/state-of-the-tracker.md`** (overdue after ten
>    releases). The session digest is posted to PRODUCTION as mailbox
>    **#258** (2026-08-01 05:33 UTC) — do not re-post. Read production
>    #257 first: it is platform-claude's incident report on the
>    two-database mixup and revises the work order.
> 6. **TWO MCP SERVERS CARRY THE SAME TOOL NAMES — know which you are on
>    before ANY read or write.** The repo-root `.mcp.json` server
>    (`python transaction-tracker/mcp_server.py`) runs INSIDE this
>    container against the LOCAL, EMPTY `transactions.db` (`DATABASE_PATH`
>    unset). The claude.ai connector is the one bound to production.
>    Discriminate with `get_statistics`: production ≈ 1,630+ items; local
>    = 0. `get_tracker_docs` is NOT a discriminator (it reads the
>    filesystem, so both list the same docs). There was NO mailbox reset —
>    that conclusion came from reading the empty local store; production
>    #42–#256 were intact all along. NEVER run money operations (the
>    ledger duplicates above) or repairs against the local server, and
>    never "restore" anything based on what the local store shows.
> 7. Then the rest of the OUTSTANDING list in its written order, and
>    anything Kerry raises from championship day.
>
> Standing rules: bump `static/js/version.js` + changelog every commit,
> update `docs/claude/*.md`, follow CLAUDE.md guiding principle #6
> (`customer_id` everywhere — four separate name-key bugs last session),
> and END the session by posting a mailbox digest (rule 4) — last session
> nearly forgot.

---

## ADDENDUM — championship-morning session (2026-08-01 ~00:15–01:00 CDT)

Ran the work order above from a FRESH container (claude.ai connector =
production; the local `.mcp.json` trap in item 6 was avoided — see #257–
#259). Item-by-item:

1. **Pre-flight DONE (rounds had not started — it was 12:15 AM).** Both
   champ boards fetch logged-out from Railway and parse (SA field 30,
   Austin 16, tee times 9:00–10:10 / 9:00–9:27); Railway confirmed
   running the overnight commits. Finding fixed forward: comma-less
   guests ("Matt Larson Guest", Austin) were silently dropped by the
   board parser — fixed in v2.176.0.
2. **Ledger duplicates VERIFIED, not merged (no admin UI from here).**
   The watch FIRED: Larry Anthis addon-2491 duplicated overnight as
   exp-promoted-2230 ($30), and Chuck Fehlis addon-2492 +
   exp-promoted-2231 ($30) is a brand-new same-shape pair. Plus June
   suspects: Daniel South $88, Sam McCormick $88, Ryan Estes $88, Lee
   Vasquez $16 possible TRIPLE (addon-1955 + addon-1956 + exp-promoted-
   1361). Full hit-list with ids: mailbox **#260**. Root cause is the
   addon/ext-pay × exp-promoted writer pair — a promotion-time twin
   check is proposed, needs Kerry (rule 3b).
3. **DONE (v2.176.0, on branch `claude/tgf-tracker-champ-points-g62t9l`
   — NEEDS MERGE TO MAIN TO DEPLOY).** Drill-down CC line carries the
   live figure via the standings row's data-champ-* attrs.
4. **DONE (same commit).** CC line expands to a live hole-by-hole card:
   gross+dots off the player's details partial on the ALL Net 18 board
   (player-name links carry each player's details URL — verified live),
   pars off the nets partial, NET + champ-scale points computed by us,
   board total beside ours with mismatch stated. New dial
   `gg_champ_scorecard_boards`; endpoint /api/season-contests/points-
   race/champ-card; tests test_champ_card_live.py. Also: the 60s live
   poll no longer wipes an open drill-down.
5. **state-of-the-tracker.md refreshed** (this commit).
6. **Resolved by #257/#258 (parallel session) — confirmed here.** My
   #259 digest re-post partially duplicates #258 (posted 14 min apart
   by two concurrent sessions; #258 came first). New in #259: recommend
   removing/renaming the repo `.mcp.json` stdio server.
7. **OUTSTANDING list carry-forward:** items 3 (HIO figure), 4 (matrix
   multi-event rows), 5 (identity audit), 6, 7 (hio write paths), 8–13
   (offers/gaps), 15–18 (customer_id audit, no-handicap correspondence,
   flighting queue, Aug-29 untether) — NOT worked this session, all
   still open. Mailbox #252 (winnings backfill, Kerry Option B ruling)
   is now the TOP of the next working session's queue; #254/#255
   (winnings-by-handicap, fairness study) remain open requests.

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

**I got THREE diagnoses wrong tonight. Every time the pattern was the
same: a real observation, promoted to a cause without checking whether it
explained the whole picture.**

0. **"The production mailbox was reset."** It was not. This session had the
   same MCP tools under TWO servers — the claude.ai connector (production)
   and the repo `.mcp.json` stdio server (local, empty, `DATABASE_PATH`
   unset). I read the mailbox through the local one, saw only the boot
   welcome post, and concluded production history was gone — then wrote an
   investigation item on top of the error. platform-claude caught it from
   the decisive pair: my DOCS reached production (git deploy) while my
   mailbox POST did not — impossible on one database. The tell I missed
   hours earlier: `get_event_registrations` returning `[]` on that server
   for an event with a full field. **An empty answer from a tool is data
   about the TOOL as much as about the world. Cross-check which store
   answered before concluding anything about production — and had I
   "repaired" the phantom loss, I would have written reconstructed rows
   over a healthy production DB.**

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

---

## OUTSTANDING — raised in this session, never actioned

Ordered by how much they cost if ignored. Items 1–4 are money/data
integrity; the rest are asks, offers Kerry never answered, or hygiene.

### Money / data integrity

1. **Two known double-counted Venmo income rows are sitting in the ledger
   right now.** Precedent pairs found while checking Larry Anthis's buy-in:
   Jeff Young `ext-pay-2195` (6/30, $50) + `exp-promoted-1540` (6/29, $50);
   Julius Jenkins `ext-pay-2140` + `exp-promoted-1480`, both 6/24, $219.
   Same money recorded twice — the manual "Add Payment" entry AND the parsed
   Venmo receipt. Collapse them in `/admin/duplicate-detective`.
2. **Larry Anthis's $30 NET Games buy-in is the same shape and unwatched.**
   Kerry's manual entry is item 2491 (`addon-2491`, 2026-07-31). When his
   Venmo receipt lands it will promote as an `exp-promoted-N` income row for
   $30 and duplicate. Kerry asked me to watch for it; **I could not arm the
   Routine** — `create_trigger` and `send_later` both returned "requires
   approval" and this session is non-interactive. Nothing is watching.
   Larry's Venmo handle is `Larry-Anthis`, customer_id 41.
3. **`get_hio_pot` reports two different pots.** `events[].running` =
   carry-in + contributions (does NOT subtract payouts); `pot` = the same
   minus `paid_out`. The GAMES banner shows `running`, the FINANCIAL panel
   shows `pot`. They diverge by exactly the total HIO paid the moment an ace
   is recorded, and the GAMES banner reads HIGH. Worse, the banner falls back
   to `d.pot` when the event is not in the contribution list, so two events
   can show different bases on the same screen. Kerry was told; he has not
   said which figure he wants. **Do not "fix" this without his call.**
4. **The 18h games matrix has no multi-event rows.** On a two-championship
   day the Individual Net *total* is computed exactly, but its per-place
   ladder is scaled proportionally at render time and marked
   "(multi-event day)". Authoritative fix is adding real rows to the matrix
   generator.

### Asked of Kerry, still open

5. **Run `GET /api/admin/gg-points-identity-audit`** (built in v2.165.0) and
   report the "still unmatched" list. An unresolved standings row shows on
   the Contests board — it has a name and a total — but is invisible to
   anything that joins on identity: pairings order, the points column,
   flighting, payouts. Never run.
6. **Which HIO figure belongs on the GAMES tab** (see #3).
7. **`hio_27h_event_patterns` and `hio_player_count_overrides`** are read by
   `get_hio_pot` but have no write path — the same gap the carry-in had
   until v2.172.0. If either is wrong the running pot is wrong and there is
   no way to correct it from the app.

### Offers made, never answered — leave as-is unless he asks

8. **Single-18h-day MVP row label changed** from `MVP` to
   `City MVP (incl. TGF $, capped)` for consistency with the 9-hole
   convention. Money identical (verified across all 63 matrix rows). Offered
   to revert; no answer.
9. **3rd-place GG auto-fill is deliberately NOT wired.** Normal bracket
   matches pre-fill a detected winner from GG; the consolation does not,
   because GG must have the two semifinal losers correctly paired as a match
   for that to be trustworthy. Offered to enable; no answer.
10. **`determine_tgf_mvp` has never been dry-run against real 18-hole
    scorecards.** I verified the format-pooling logic and the money math in
    tests only. Offered a dry-run against a past 18-hole day; not taken up.
11. **CUSTOMERS list colours**: `MEMBER #d1fae5` and `FORMER #e2e8f0` are
    only 27 RGB apart. Offered to bring FORMER in line with the ALUMNI grey.

### Known gaps in what shipped

12. **The consolation match has no event selector of its own.**
    `cmp_record_consolation` writes no `event_id`; the card inherits the
    FINAL's event for its header date. If a 3rd-place match is ever played at
    a different event the header date is wrong (the live GG lookup still
    works, since it matches on chapter + the two player names).
13. **Five MCP servers need OAuth** and surfaced as unauthorized all session.
    A non-interactive session cannot run the flow — Kerry must authorize via
    claude.ai connector settings or `/mcp` in an interactive session.

### Process debt

14. ~~Mailbox digest~~ **DONE — in PRODUCTION as post #258** (2026-08-01
    05:33 UTC), re-posted after the first attempt landed in the
    container-local DB as its post "#2". The "mailbox was reset" finding
    that briefly lived here was WRONG: production #42–#256 were intact the
    whole time; the empty view was the local `.mcp.json` server's own
    file. Full incident chain: production posts #257 (platform-claude's
    diagnosis) and #258 (binding report + digest). Still owed: the
    `docs/claude/state-of-the-tracker.md` refresh. Secondary check done:
    `get_side_games_matrix` reads `app_settings` (persistent volume, seed
    file only as fresh-DB fallback) — redeploy-safe as read, not yet
    proven across an actual redeploy.

### Longer-standing, carried in from before this session

15. `customer_id` audit + safeguards (four more name-key bugs surfaced here —
    the case for this is now much stronger).
16. The no-handicap "send correspondence" path.
17. Flighting queue: minimum flight size, the 3-flight ladder, pot-split
    ratification, scenarios 7/8/10, and the flights-lock moment.
18. The **Aug-29 untether go/no-go for CA**.

---

**Working style that paid off:** reproducing a bug before fixing it. The HIO
duplicate-`id` fix was written against a jsdom harness that replays Kerry's
exact "shows then disappears" sequence — old code fails all three steps, new
code passes. Do that again where the symptom is behavioural.

**Environment gotchas:** local `transactions.db` is EMPTY (live data is on
Railway); the `tgf-transactions` MCP is the only way to see production. This
container cannot reach golfgenius.com directly — use `probe_golf_genius`.
`create_trigger` / `send_later` need approval that a non-interactive session
cannot grant, so scheduled follow-ups can't be armed from here.
