# GG History — archive coverage map + ingest plan (INVENTORY phase)

Kerry-directed initiative (mailbox #100, approved #105, closers #106/#107):
capture ALL Golf Genius data since 2016 into the Tracker, tied to customer
IDs. This doc banks the INVENTORY-phase deliverables: the portal coverage
map, the proven data-access recipe, and the proposed ingest schema
(**PROPOSAL ONLY — no gg_history_* tables exist yet; Kerry rule-3b
ratification required before INGEST writes anything**).

Inventory ran 2026-07-11 (automated walker over `probe_golf_genius`,
~160 probes across 7 parallel agents + targeted follow-ups).

## THE KEY FINDING — how the data is actually reachable

Every archive portal serves its data pages as **empty JS-widget shells**:
`n_tables=0` on every EVENT RESULTS / standings / match-play / directory
page across all portals. Static page scraping gets navigation only.
The agents' first-pass "high ingest risk" verdict was WRONG, however —
the data is fully server-fetchable via the widget routes the page JS
calls. Proven recipe:

1. **league_id discovery**: any portal page's raw HTML body (past ~85KB —
   fetch full length, the head scripts are huge) carries hidden inputs:
   `current_league_id`, `website_id`, `current_league_name`. Example:
   tgf-sa2016 → league_id 15478, website_id 15492; tgf-sa2024 → 395571.
2. **Widget discovery shortcut (no guessing)**: the same raw page body
   embeds `<iframe class='page-iframe' src='…/widgets/<type>?…'>` — every
   page NAMES its own widget. Worked on both eras; only login-locked
   pages hide it (they fall back to rendering SCHEDULE's calendar iframe).
3. **Standings widgets**: `https://<portal>.golfgenius.com/leagues/
   <league_id>/widgets/<type>?page_id=<page_id>&shared=false` (plain GET).
   Types confirmed in the wild: `season_points_v2` (modern points races +
   cups — the live 2026 sync's route; columns vary per config: `Handle`
   present on Fellowship Cup, absent on monthlies; `Affiliation` values
   incl. `TGF San Antonio/Austin/DFW/Houston` and `Former`),
   `season_points` (v1: 2016-era standings AND the modern MONEY &
   SCORING LEADERS pages — no rank-movement columns, `Totals:` folded
   into the last row). Proven pulls: the full 66-player 2016 SA points
   race and the 94-row 2024 SA money list (`Rank | Player | Times
   Played | Total Purse | Avg. Gross | Avg. Net | Low Gross | Low Net`,
   totals $27,591.17). Error semantics: unknown widget type → HTTP 404;
   valid type not configured for the page → empty shell (title
   "Golf Genius ::", 0 tables). NOTE: `season_points` appears
   league-scoped on the old portal (returned data even for a page whose
   real widget is `images`) — treat page_id as a hint, not a guarantee
   of provenance.
4. **Event results (two hops, round enumeration SOLVED)**: the EVENT
   RESULTS page embeds `/leagues/<league_id>/widgets/tournament_results
   ?shared=false`, which serves ONE round (defaults to latest) and
   contains a server-side `<select name="round">` listing EVERY round_id
   of the season (32 options on SA 2024). Appending `&round=<round_id>`
   switches rounds — verified. Each round lists per-tournament XHR
   partials: `/v2tournaments/<tid>?player_stats_for_portal=true&
   round_index=<n>` (fetch with `xhr=true`, parse the JS partial —
   `_unwrap_js_string` in golf_genius_sync.py already does this) plus
   `/v2tournaments/total_purse?league_id=..&round_id=..`. Proven on DFW
   2024 (league_id 395610): full results table with header
   `Pos. | Player | Playing Handicap | Total Gross | To Par Net |
   Total Net | Purse`. Same v2tournaments scheme on BOTH eras (2016
   included) — one parser covers all ten seasons.
5. **Machine keys**: v2tournaments rows carry `data-member-ids`,
   `data-aggregate-id`, `data-aggregate-name` attributes — stable GG ids
   we can store for idempotent re-import and identity linking.
6. **`images` widget pages**: some content is uploaded PNGs, not tables —
   2016 MATCH PLAY brackets are two cloudfront images
   (`ddz5qbrxrbzp.cloudfront.net/uploads/page_image/image/…`), and the
   2016 FINAL STANDINGS page's own widget is an image (its data lives in
   the league-scoped season_points widget anyway). **2024 SA Match Play
   renders "No image uploaded."** — that bracket was never published as
   an image and per-round match data must come from tournament_results.
7. Scorecard-level ingest for archive events reuses the existing
   `import_gg_scorecards` path (`/tournaments2/details/<agg>`) unchanged.

## Name formats observed

- **"LASTNAME, First"** (uppercase surname) is the dominant format for
  members across eras: `NIESTER, Kerry` (SA 2016 points race),
  `WETZ, David` (DFW 2024 results). Mixed-case surname particles are
  PRESERVED (`DelCARMEN, Michelle`, `McLIN, Matthew`, `DeBORDE,
  Geremey`) and suffixes append after a second comma (`LEVESQUE,
  Michael, Jr`, `Martinez, Jesse, III`) — the normalizer must handle
  both.
- **Guests/newer players render Title case** with affiliation "Guest"
  (`Hennessey, Matt`, DFW 2024; `Fieber, Scott`, SA 2024) — a useful
  member/guest signal at parse time.
- Identity linking must therefore normalize `LAST, First` → canonical
  `First Last` before the resolver cascade (canonical names →
  `customer_aliases` → `handicap_player_links`); expect maiden-era names,
  guests, and DFW/Houston members with no Tracker profile at all
  (mailbox #100 phase 3: unmatched → review queue for Kerry).

## Portal registry — 59 live portals (+2 dead mains) — COVERAGE COMPLETE

| Portal | Season/Scope | Status | website_id | league_id | Notes |
|---|---|---|---|---|---|
| tgf-sa2016 | SA 2016 | ALIVE | 15492 | 15478 | oldest; "The Golf Fellowship 2016" |
| tgf-sa2017 | SA 2017 | ALIVE | 42332 | — | |
| tgf-sa2018 | SA 2018 | ALIVE | 80023 | — | first FELLOWSHIP CUP + MONEY & SCORING + Two Man GROSS/NET pages |
| tgf-sa2019 | SA 2019 | ALIVE | 133245 | — | dual-city: carries POINTS RACE austin + TEAM RACE |
| tgf-sa2020 | SA 2020 | ALIVE | 192120 | — | |
| tgf-sa2021 | SA 2021 | ALIVE | 234894 | — | first net/gross points split (SA) |
| tgf-sa2022 | SA 2022 | ALIVE | 324207 | — | adds FALL races, TGF HANDICAPS |
| tgf-sa2023 | SA 2023 | ALIVE | 405415 | — | richest era: LEAGUE EAST/WEST/WEEKEND, SKINS NIGHT races, monthly Mar–Oct |
| tgf-sa2024 | SA 2024 | ALIVE | 468184 | 395571 | modern set (= what the Tracker knows from 2026); recipe proven here too |
| tgf-sa2025 | SA 2025 | ALIVE | 525799 | — | adds TGF CREDITS REPORT + Players Cup flight pages |
| tgf-austin2019 | Austin 2019 | ALIVE | 138920 | — | dual-city: carries POINTS RACE san antonio |
| tgf-austin2020 | Austin 2020 | ALIVE | 194603 | — | first Austin MATCH PLAY page |
| tgf-austin2021 | Austin 2021 | ALIVE | 235084 | — | Player Dashboard page |
| tgf-austin2022 | Austin 2022 | ALIVE | 324565 | — | net/gross points split |
| tgf-austin2023 | Austin 2023 | ALIVE | 408164 | — | LEAGUE NORTH/SOUTH/WEEKEND |
| tgf-austin2024 | Austin 2024 | ALIVE | 464543 | — | |
| tgf-austin2025 | Austin 2025 | ALIVE | 527550 | — | TGF CREDITS REPORT; Players Cup flights; Net SPRING/SUMMER vs FALL |
| tgf-dfw2020 | DFW 2020 | ALIVE | 195014 | — | |
| tgf-dfw2021 | DFW 2021 | ALIVE | 237874 | — | |
| tgf-dfw2022 | DFW 2022 | ALIVE | 324803 | — | net/gross split + MATCH PLAY |
| tgf-dfw2023 | DFW 2023 | ALIVE | 409845 | — | full modern set incl. PLAYERS CUP, FALL NET, MC NORTH/SOUTH/WEEKEND |
| tgf-dfw2024 | DFW 2024 | ALIVE | 468223 | 395610 | final DFW season; recipe proven here |
| tgf-houston2021 | Houston 2021 | ALIVE | 237876 | — | leanest portal (no handicaps, no MP) |
| tgf-houston2022 | Houston 2022 | ALIVE | 324804 | — | net/gross split + MATCH PLAY |
| tgf-houston2023 | Houston 2023 | ALIVE | 410486 | — | full modern set, LEAGUE NORTH/NORTHWEST/WEEKEND |
| tgf-houston2024 | Houston 2024 | ALIVE | 468239 | — | final Houston season |
| tgf-hillcountry | ONE-OFF 2023 | ALIVE | 421436 | — | "TGF Hill Country 2023" league (2025 edition lives as a PAGE on tgf-sa2025: 5424367) |
| tgf-twoman | Two Man 2023 | ALIVE | 417329 | — | Two Man Challenge Series 2023; team format; also twomantour.com external |
| tgf-roadtrip2023 | ONE-OFF 2023 | ALIVE | 410532 | — | minimal 2-page shell (Tee Sheets + Results only) |
| tgf-roadtrip2020 | ONE-OFF 2020 | ALIVE | — | — | full league site: ER 2597895, M$ 2597894, POINTS RACE dfw 2597893, FC 2597892, DIR 2597888 |
| tgf-roadtrip2021 | ONE-OFF 2021 | ALIVE | — | — | sparse: Tee Sheets 2818250, Tournament Results 2818251 |
| tgf-roadtrip2022 | ONE-OFF 2022 | ALIVE | — | — | sparse: SCHEDULE 3424508, Tee Sheets 3416819, Tournament Results 3416820 |
| tgf-twoman2020 | Two Man 2020 | ALIVE | — | — | "Two Man Challenge Series League": Players 2532438, Tournament Results 2532442, Player Analytics 2532444 |
| tgf-twoman2021 | Two Man 2021 | ALIVE | — | — | ER 2843357, M$ 3137725, POINTS RACE net 3003170 / gross 3003171, DIR 2843364 |
| tgf-twoman2022 | Two Man 2022 | ALIVE | — | — | richest Two Man site: ER 3507900, M$ 3507901, PR net/gross 3507898/3507899, FC 3594318, DIR 3594319 |
| tgf-twomantour | Two Man Tour | ALIVE | — | — | "Two Man Tour League": Players 4947581, Tournament Results 4947585, Player Event Standings 4947586 — likely aggregates the 2024–25 per-course events |
| tgf-lonestarcup21 | LSC 2021 | ALIVE | — | — | full league site: FC 3220970, PR san antonio 3220971, MP 3220972, M$ 3220973, ER 3220974, DIR 3220967 |
| tgf-lonestarcup22 | LSC 2022 | ALIVE | — | — | LEADERBOARD "2022 LONE STAR CUP" 3827234, DIR 3827227, HCP 3877011/3877012 |
| tgf-lonestarcup25 | LSC 2025 | ALIVE | 575031 | — | Kerry-supplied link (2-digit-year pattern key): LEADERBOARD/MONEY 5710572, DIR 5663174, HCP 5663175; hosted at Squaw Valley GC |
| tgf-champ25 | TGF Championship 2025 | ALIVE | — | — | Kerry-supplied pattern ("champ", not "championship"): FC 5550900, PC Overall+4 flights+RegSeason 5553510/5550902–5550906, M$ 5550907, ER 5550908, DIR 5550896; cross-links a "2024 TGF CHAMPIONSHIP" page (5550914) — 2024 champ data exists somewhere reachable |
| tgf-roadtrip24 | ONE-OFF 2024 | ALIVE | — | — | "2024 Road Trip + Two Man Challenge" (TGF + one Tour event, hybrid): SCHEDULE 4679638, DIR 4673301 — NO results/money pages in nav |
| tgf-roadtrip25 | ONE-OFF 2025 | ALIVE | — | — | RESULTS 5295980, MONEY 5710562, ITINERARY 5295753, DIR 5293940 |
| tgf-champ20 | TGF Championship 2020 | ALIVE | — | — | FC 2568109, PR san antonio 2568110, MP 2568111, M$ 2568112, ER 2568113, DIR 2568105 |
| tgf-champ21 | TGF Championship 2021 | ALIVE | — | — | FC 3063295, PRs 3063296, MP sa 3063297 + austin 3072525, M$ 3063298, ER 3063299, DIR 3063291 |
| tgf-champ22 | TGF Championship 2022 | ALIVE | — | — | FC 3628138, PRs 3628139, MP sa/austin 3628140/3628141, M$ 3628142, ER 3628143, DIR 3628134 |
| tgf-champ23 | TGF Championship 2023 | ALIVE | — | — | FC 4286535, PC 4340774, M$ 4286539, ER 4286540, DIR 4286531 |
| tgf-champ24 | TGF Championship 2024 | ALIVE | — | — | FC 4932416 + RegSeason 4899990, PC flights 4933781/4933784/4934136/4934139 + RegSeason 4899991, M$ 4899992, ER 4899993, DIR 4899986 |
| tgf-trinity | Trinity River Cup 2022 | ALIVE | — | — | DFW-v-Houston Ryder Cup event: FC 3798532, PR san antonio 3798533, MP 3798534, M$ 3798535, ER 3798536, DIR 3798529 |
| tgf-hcc22 | Hill Country Cup 2022 | ALIVE | 384699 | — | Kerry link ("hcc" abbrev): FC 3778690, PR san antonio 3778691, MP 3778692, M$ 3778693, ER 3778694, DIR 3778687 |
| lonestarcup24 | LSC 2024 | ALIVE | 514529 | — | Kerry link (NO tgf- prefix!): DIR 5054894, HCP 5054895/5054896, SCHEDULE 5054897, TEE SHEETS 5054899; hosted at White Bluff Resort — no leaderboard/money page in nav |
| redblue | Red Blue Challenge 2023 | ALIVE | 432025 | — | Kerry link (no prefix): LEADERBOARD 4224162 (nav also labels it "2022 LONE STAR CUP" — mislabeled duplicate entry), DIR 4224157, HCP 4224158/4224159 |
| tgf-hcc21 | Hill Country Cup 2021 | ALIVE | — | — | FC 3188785, PR san antonio 3188786, MP 3188787, M$ 3188788, ER 3188789, DIR 3188781 |
| lonestarcup | LSC 2023 | ALIVE | 456065 | — | Kerry link (no prefix, no year): LEADERBOARD "2023 LONE STAR CUP" 4466344, MATCHES 4467725, DIR 4466339, HCP 4466340/4466341; White Bluff Resort |
| tgf-2020hccup | Hill Country Cup 2020 | ALIVE | 215667 | — | Kerry link (year-FIRST pattern): FC 2667258, PR san antonio 2667259, MP 2667260, M$ 2667261, ER 2667262, DIR 2667254, AN 2667263 |
| tgf-hc | TGF Hill Country 2022 | ALIVE | 341304 | — | Kerry link: FC 3592782, PR hill country 3557452, M$ 3592783, ER 3592784, DIR 3592812, HCP 3592824/3683078, MIP 3592825 |
| tgf-hcm | Hill Country Matches 2023 | ALIVE | 424655 | — | Kerry link: TOURNAMENT RESULTS 4149073, BRACKET 4149530, PLAYERS 4149069, TEE SHEETS 4149072 |
| hillcountrymatches | Hill Country Matches 2024 | ALIVE | 488745 | — | Kerry link (no prefix): TOURNAMENT RESULTS 4799431, BRACKET 4801100, PLAYERS 4799427 |
| hillcountry2man-1 | HC Two Man Jul 2023 | ALIVE | 436950 | — | **Two Man Tour brand (Kerry ruling 2026-07-11, supersedes the earlier TGF call for these two)**; manager Joe Warring: ROSTER 4273433, LEADERBOARD/RESULTS 4273437 |
| hillcountry2man | HC Two Man Nov 2023 | ALIVE | 447709 | — | **Two Man Tour brand (same supersession)**: ROSTER 4381073, LEADERBOARD/RESULTS 4381076, TGF DIRECTORY 4381214 |
| tgf-dfw (main) | — | **DEAD** | — | — | redirects to corporate golfgenius.com; also linked with a typo (`.coms`) from tgf-sa2024 |
| tgf-houston (main) | — | **DEAD** | — | — | redirects to corporate golfgenius.com |

Chapter timeline confirmed by Kerry: SA since 2007 (**GG since 2016 —
2007–2015 is Excel-era, out of GG scope, a future manual import**);
Austin GG 2019–; DFW GG 2020–2024; Houston GG 2021–2024. league_ids for
the remaining portals are discoverable mechanically at ingest time
(recipe step 1) — not enumerated during inventory to save probe budget.

## Coverage map — pages per portal (nav inventory)

Legend: **ER**=Event Results, **M$**=Money & Scoring, **FC**=Fellowship
Cup, **PC**=Players Cup, **PR**=Points Race (season), **MP**=Match Play,
**MON**=monthly points pages, **DIR**=Directory, **HCP**=handicap pages,
**AN**=analytics pages. Page ids in parentheses.

### San Antonio

- **2016**: FINAL STANDINGS (625979), PR (341784), MP (368529), ER
  (341783), CURRENT MEMBERS (341780), AN (341785, 366382), DISCUSSION/
  PHOTOS. No money page, no cup.
- **2017**: ER (879201), PR (879199), MP (879200), DIR (879202), AN
  (879203/879204). No cup/money pages.
- **2018**: FC (1309638), PR (1383157), MP (1309652), ER (1272702),
  M$ (1372235), Two Man GROSS (1535933) / NET (1535934), DIR (1272699),
  HCP SUMMARY (1372320), AN (1272704, 1372296, 1372311, 1372318).
- **2019**: FC (1809436), PR sa (1809437), **PR austin (1932561)**,
  MP (1809438), **TEAM RACE (1923173)**, M$ (1809440), ER (1809439),
  DIR (1809432), HCP (1809433), AN (1809443–1809446).
- **2020**: FC (2436717), PR sa (2436716), MP (2436715), M$ (2417621),
  ER (2417620), DIR (2417616), HCP (2436704), AN (2417622).
- **2021**: FC (2819061), PR net (2819062), PR gross (2856620), MP
  (2819063), M$ (2819064), ER (2819065), DIR (2819057), Player Dashboard
  (3020844), AN (2819066).
- **2022**: FC (3410707), PR net (3410708), PR gross (3410709), FALL net
  (3817082), FALL gross (3817083), MP (3410710), M$ (3410711), ER
  (3410712), DIR (3410703), HCP (3583724, 3683074), AN (3410713,
  3583727, 3594354–3594356, 3594371), LEAGUES directory page (3600038).
- **2023**: ER (3956386), M$ (3956387), FC (4258632), PC (4258633),
  FALL GROSS (4377913), CITY NET (4104065), CITY MP (4112172), FALL CITY
  NET (4377914), LEAGUE EAST/WEST/WEEKEND (4104067/4104068/4104069),
  MON Mar–Oct (4104070, 4129047, 4183886, 4258619, 4299798, 4377928,
  4464262), SKINS NIGHT races (4518987), DIR (3956382), HCP (3956551/
  3956552), AN (4258645, 4258665–4258668).
- **2024**: ER (4582854), M$ (4582855), FC (4932415), FC-RegSeason
  (4582856), PC (4582857), NET (4582859), GROSS (4583569), MP (4583571),
  MON Apr–Jul+Sep (4582866, 4817983, 4856460, 4889251, 4889252), FALL
  NET (5015038), DIR (4582849), HCP (4582850/4582851), AN (4582873–
  4582877).
- **2025**: ER (5168953), M$ (5187607), FC (5547112), PC Overall +
  4 flights + RegSeason (5553526, 5553530–5553533, 5187609), NET
  (5187626), NET-FALL (5591949), MP (5187753), MON Mar–Jul+Sep+Oct
  (5187754–5187757, 5498405, 5607490, 5655885), **2025 HILL COUNTRY
  MATCHES (5424367)**, **TGF CREDITS REPORT (5364532)**, Fall Net ROSTER
  (5582866), DIR (5168949), HCP (5187782/5187783/5187811), AN (5187786,
  5168955, 5187798–5187800), PHOTO STREAM/EVENT TALK.

### Austin

- **2019**: FC (1868577), PR austin (1868578), **PR san antonio
  (1932573)**, ER (1868580), M$ (1868581), DIR (1868573), HCP (1868574),
  AN (1868584–1868587). No MP.
- **2020**: FC (2442653), PR (2442654), **MP (2442655 — first Austin
  MP)**, M$ (2442656), ER (2442657), DIR (2442649), HCP (2442650),
  AN (2442658).
- **2021**: FC (2820488), PR (2820489), MP (2820490), M$ (2820491), ER
  (2820492), DIR (2820484), Player Dashboard (3021511), AN (2820493,
  2855163), LEAGUES directory (2855164).
- **2022**: FC (3413710), PR net (3413711), PR gross (3530279), MP
  (3413712), M$ (3413713), ER (3413714), DIR (3413706), HCP (3594302,
  3683075), AN (3600031–3600034, 3413715/3413716), LEAGUES directory
  (3600039).
- **2023**: ER (3985829), M$ (3985828), FC (4234219), PC (4234220),
  CITY NET (3985825), CITY MP (3985827), LEAGUE NORTH/SOUTH/WEEKEND
  (4112160/4112161/4112162), MON Mar–Jul (4112159, 4129208, 4234227,
  4234221, 4316545), DIR (3985818), HCP (3985819/3985820), AN (3985831–
  3985835).
- **2024**: ER (4543204), M$ (4543205), FC (4543206), PC (4543207), NET
  (4543208), GROSS (4583241), MP (4583243), MON Apr–Jul+Sep (4543214,
  4889253–4889256), DIR (4543199), HCP (4543200/4543201), AN (4543218–
  4543222).
- **2025**: ER (5187519), M$ (5187520), FC (5547113), PC Overall +
  4 flights + RegSeason (5553534–5553538, 5187522), NET SPRING/SUMMER
  (5187523), NET FALL (5593497), MON Mar–Jul+Sep+Oct (5480146, 5480187,
  5466355/5466356, 5498404, 5607491, 5655871), **TGF CREDITS REPORT
  (5364533)**, DIR (5187514), HCP (5187515/5187516), AN (5187531–
  5187535).

### DFW (chapter closed after 2024)

- **2020**: FC (2446944), PR dfw (2446945), M$ (2446947), ER (2446948),
  DIR (2446940), HCP (2446941), AN (2446949).
- **2021**: FC (2843324), PR (2843325), M$ (2843326), ER (2843327), DIR
  (2843320), HCP (2843321), AN (2843328).
- **2022**: FC (3415935), PR net (3415936), PR gross (3530282), MP
  (3579651), M$ (3415937), ER (3415938), DIR (3415931), HCP (3415932,
  3683077), AN (3415939).
- **2023**: ER (4003781), M$ (4003780), FC (4259598), PC (4259600),
  CITY NET (4129061), CITY MP (4129066), FALL NET (4443359), LEAGUE MC
  NORTH/MC SOUTH/WEEKEND (4129063/4129064/4129065), MON Mar–Jul+Sep
  (4129067, 4129068, 4193918, 4259630, 4284921, 4443358), DIR (4003771),
  HCP (4003772/4003773), AN (4003782).
- **2024**: ER (4583372), M$ (4583373), FC (4583374), PC (4583375), NET
  (4583376), GROSS (4583567), MP (4583568), MON Apr–Jul+Sep (4583383,
  4818142, 4889257–4889259), DIR (4583367), HCP (4583368/4583369), AN
  (4583388). league_id 395610.

### Houston (chapter closed after 2024)

- **2021**: FC (2970349), PR (2970351), ER (2843345), M$ (3018741), DIR
  (2843341), AN (2845840). Leanest portal.
- **2022**: FC (3415958), PR net (3415959), PR gross (3530280), MP
  (3589097), ER (3415960), M$ (3415961), DIR (3415962), HCP (3594317,
  3679768).
- **2023**: ER (4011516), M$ (4011517), FC (4259651), PC (4259658),
  CITY NET (4011513), CITY MP (4011515), LEAGUE NORTH/NORTHWEST/WEEKEND
  (4111913/4111914/4111915), MON Mar–Jul (4111906, 4129060, 4191699,
  4259650, 4334569), DIR (4011507), HCP (4011508/4011509).
- **2024**: ER (4583592), M$ (4583593), FC (4583594), PC (4583595), NET
  (4583596), GROSS (4583668), MP (4583670), MON Apr–Jul+Sep (4583602,
  4818478, 4889249, 4889260, 4889261), DIR (4583587), HCP (4583588/
  4583589).

## THE MASTER LEAGUE LIST (Kerry's GG admin console, 2026-07-10 screenshots)

Kerry supplied the authoritative list from the golfgenius.com manager
account: **75 archived + 4 current = 79 LEAGUES** — the portal walk saw
29 public portal WEBSITES; a GG *league* and its public *website* are
separate objects, and ~40 leagues have no portal we discovered. Kerry's
categorization: some leagues are TGF, some are **Two Man Tour** (a
sibling brand, twomantour.com), some are **neither**.

Archived leagues by year (start-date order, verbatim names):
- **2016–2018**: The Golf Fellowship 2016 · 2017 · 2018 (= tgf-sa portals)
- **2019**: TGF San Antonio 2019 · TGF Austin 2019
- **2020**: TGF San Antonio 2020 · TGF Austin 2020 · TGF Dallas-Ft Worth
  2020 · Two Man Challenge Series · 2020 Road Trip · **2020 TGF
  CHAMPIONSHIP** · **2020 Hill Country Cup**
- **2021**: 2021 Road Trip · TGF Austin 2021 · TGF San Antonio 2021 ·
  TGF Dallas-Ft Worth 2021 · **Non-TGF Events** · TGF Houston 2021 ·
  Two Man 2021 · **2021 TGF CHAMPIONSHIP** · **2021 Hill Country Cup** ·
  **2021 Lone Star Cup**
- **2022**: 2022 Road Trip · TGF Houston 2022 · TGF Austin 2022 · TGF
  DFW 2022 · TGF San Antonio 2022 · TGF Hill Country 2022 · **Non-TGF
  Events (2022)** · Two Man 2022 · **2022 TGF CHAMPIONSHIP** · **2022
  Trinity River Cup** · **2022 Hill Country Cup** · **2022 Lone Star Cup**
- **2023**: TGF San Antonio 2023 (league row shows "Not Published" hub
  toggle; the portal website is live regardless) · TGF Austin 2023 ·
  TGF DFW 2023 · TGF Houston 2023 · 2023 Road Trip · TGF Hill Country
  2023 (= tgf-hillcountry portal) · 2023 Hill Country Matches (a SECOND
  hill-country league) · Two Man 2023 (= tgf-twoman portal) · **2023
  Red Blue Challenge** · **Rough Water Cup** · **Hill Country Two Man
  Challenge - July 8-9, 2023** · **2023 TGF CHAMPIONSHIP** · **2023
  Lone Star Cup** · **Hill Country Two Man Challenge (Nov 2023)**
- **2024**: TGF Austin 2024 · TGF San Antonio 2024 ("Not Published" hub
  toggle) · 2024 Road Trip + Two Man Challenge · TGF DFW 2024 · TGF
  Houston 2024 · DFW Two Man WATERCHASE · Two Man QUAIL VALLEY · **2024
  Hill Country Matches** · Two Man MANSFIELD NATIONAL · Two Man LOST
  PINES · **2024 TGF CHAMPIONSHIP** · Two Man TERAVISTA · **2024 LONE
  STAR CUP** · Two Man RED RIVER SHOOTOUT · 2024 TEXAS TWO MAN
  CHAMPIONSHIP
- **2025**: TGF San Antonio 2025 · Two Man SHADOWGLEN · 2025 Road Trip ·
  TGF Austin 2025 · Two Man GOLF CLUB OF HOUSTON · Two Man HAMPTON
  COVE · Two Man TERAVISTA · Two Man VAALER CREEK · **2025 TGF
  CHAMPIONSHIP** · Two Man TPC SAN ANTONIO · **2025 LONE STAR CUP**
- **Undated**: Two Man Tour (badge TGF 2024)

Current (4): TGF San Antonio 2026 · TGF Austin 2026 · 2026 Hill Country
Matches · 2026 TGF CHAMPIONSHIP.

**SCOPE RULING (Kerry, 2026-07-11, in-session): TGF + Two Man Tour.**
The two Non-TGF Events leagues (2021, 2022) are EXCLUDED from ingest.

**BRAND CLASSIFICATION (Kerry, 2026-07-11, in-session — authoritative):**
- **Two Man Challenge Series (2020) = TGF** — pre-Two Man Tour era.
  (Interpretation pending Kerry confirm: Two Man 2021/2022/2023 read as
  the same pre-Tour TGF lineage — their portals carry TGF HANDICAPS and
  Fellowship Cup pages — with the separate Two Man Tour brand starting
  at the 2024 per-course events.)
- **Road Trips = TGF** (all years). **2024 Road Trip = TGF + one Two Man
  Tour event inside** — ingest the league as TGF, tag the Tour event at
  the event level.
- **Hill Country Two Man Challenge (both 2023 leagues) = TGF.**
- **2023 Red Blue Challenge = TGF.**
- **Rough Water Cup = non-TGF → EXCLUDED** (joins the Non-TGF Events
  leagues outside scope).
- **2022 Trinity River Cup = TGF** — a DFW vs Houston Ryder-Cup-style
  event (closed-chapter history; LSC-hierarchy relevant).
- **Two Man Tour = SEPARATE BRAND, kept for a future Two Man Tour
  partner build.** Ingest and identity-link its data, but it is TOTALLY
  SEPARATE from TGF today: excluded from TGF career stats, trophy case,
  and member-facing Spotlight surfaces. `brand` is a hard filter, not a
  display label.

**Reconciliation after the guess sweeps.** Pattern probing recovered 7
more live portals (roadtrip2020–2022, twoman2020–2022, twomantour —
now in the registry above), bringing the walkable set to **36 portals**.
Confirmed-DEAD guesses (redirect to corporate golfgenius.com):
tgf-hillcountry2020/2021/2022/2024/2025, tgf-hillcountrycup,
tgf-hillcountrymatches, tgf-championship[2020/2021/–],
tgf-lonestarcup[/2021], tgf-lonestar[2021], tgf-lsc[2021], twomantour,
tgf-nontgf, tgf-roadtrip[2024/2025/–], tgf-twoman2024/2025,
tgf-redblue[2023], tgf-roughwater[cup], tgf-trinityriver[cup],
tgf-texastwoman. The guessable subdomain universe is exhausted —
everything further needs Kerry's admin links.

**RECOVERED via Kerry's pattern keys (2026-07-11 late session):** Kerry
supplied tgf-lonestarcup25, tgf-champ25, tgf-hcc22, lonestarcup24, and
redblue — revealing THREE conventions the first guesses missed:
two-digit years, abbreviations ("champ", "hcc"), and NO-PREFIX
subdomains. Derived sweeps then completed: **TGF CHAMPIONSHIP 2020–2025
(tgf-champ20…25), Lone Star Cups 2021/2022/2024/2025, Hill Country Cups
2021/2022, Red Blue 2023, Trinity River Cup 2022, Road Trips
2024/2025.** Registry above now 52 live.

**COVERAGE COMPLETE (2026-07-11, Kerry's final link batch):** Kerry
supplied lonestarcup (2023 LSC), tgf-2020hccup (year-FIRST pattern),
tgf-hc, tgf-hcm, hillcountrymatches, hillcountry2man-1, and
hillcountry2man — **all seven alive. Every in-scope archived league now
has a walkable portal entry URL.** Naming conventions catalogued for
the record: tgf-<name><YYYY>, tgf-<name><YY>, tgf-<YYYY><name>,
abbreviations (champ/hcc/hc/hcm), and bare no-prefix subdomains —
there is NO consistent scheme; the registry table above is the only
reliable index.

**Brand correction (Kerry, 2026-07-11, supersedes the earlier ruling):**
the two Hill Country Two Man Challenge leagues (Jul + Nov 2023) are
**Two Man Tour**, not TGF.

Only remaining verification (ingest-time, not blocking): whether the 13
per-course Two Man Tour events (2024–25) + 2024 TEXAS TWO MAN
CHAMPIONSHIP aggregate inside tgf-twomantour's Tournament Results /
Player Event Standings, or need their own URLs from Kerry.

### ONE-OFFS (mailbox #105 scope expansion)

- **tgf-hillcountry** (2023): PR hill country (4117092), M$ (4117093),
  ER (4117094), DIR (4117086), HCP (4117087/4117088), AN (4117095/
  4117096). Single-season 2023; the 2025 edition is a page on tgf-sa2025.
- **tgf-twoman** (2023): ER (4077390), M$ (4129189), HCP ANALYSIS
  (4178094). Team format (2-man); no directory. NOTE: tgf-sa2018 carries
  Two Man GROSS/NET pages — the series predates the dedicated portal.
- **tgf-roadtrip2023**: Results (4012075), Tee Sheets (4012074) only.
- **Awaiting Kerry's gg-links intake** (protocol per #107: post URLs to
  mailbox topic `gg-links`, any format). None posted as of #112.

## Known gaps & risks

1. ~~Round enumeration~~ SOLVED during inventory: the
   tournament_results widget carries the full `<select name="round">`
   server-side; crawl = fetch widget once → scrape option values →
   refetch per `&round=<round_id>`.
2. **Member-gated pages CONFIRMED locked**: DIRECTORY / CURRENT MEMBERS
   pages are members-only (fa-lock in nav) — anonymous fetches silently
   fall back to SCHEDULE (the `:: SCHEDULE` title anomaly the walkers
   saw), and widget-name guesses 404. Rosters are unreachable without
   auth; acceptable — identity comes primarily from results rows.
3. **Monthly race history**: monthly pages exist 2023+ only (before
   that, no monthly races on portals).
3b. **Match Play bracket gaps**: era-dependent. 2016 brackets = uploaded
   PNG images (recoverable, but needs image parsing or manual entry);
   2024 SA bracket = "No image uploaded." (page has NO server-side
   content) — bracket-round results must be reconstructed from
   tournament_results match-play tournaments where they exist.
4. **Vendor courtesy**: all 27 alive portals are unauthenticated public
   subdomains GG could prune anytime — argues for raw-snapshot-first
   ingest (store `gg_raw_archive` rows for every fetched widget/partial
   BEFORE parsing).
5. **Pre-GG SA history (2007–2015)** is Excel — out of walker scope,
   future manual import via the same gg_history_* tables (source column
   distinguishes provenance).
6. **2019 dual-city quirk**: Austin 2019 standings appear on BOTH
   tgf-sa2019 (page 1932561) and tgf-austin2019 (1868578) — dedupe by
   (season, chapter, contest) at ingest, prefer the chapter's own portal.
7. **Widget-type drift by era** (season_points vs season_points_v2 etc.)
   — the ingest walker must try a type list per page kind and record
   which answered (registry column), not hard-code one.

## Ingest schema (**RATIFIED** — Kerry in-session 2026-07-11: "let's start
## per your direction", after reviewing #113/#116 + CA's #120)

Follows the ratified house patterns: customer_id FK at design time
(rule 6), verbatim raw snapshots (past-events-frozen, principle 4),
append-only, Postgres-portable. **No DDL ships until Kerry ratifies.**

```sql
-- Registry: the coverage map as data (seeded from this doc)
CREATE TABLE gg_history_portals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    subdomain     TEXT UNIQUE NOT NULL,      -- 'tgf-sa2016'
    chapter       TEXT,                      -- NULL for one-offs
    season        TEXT,                      -- '2016'; NULL if multi-year
    kind          TEXT NOT NULL,             -- 'season' | 'oneoff'
    brand         TEXT NOT NULL,             -- 'TGF' | 'TwoManTour' (Kerry's
                                             -- 2026-07-11 ruling: hard filter —
                                             -- TwoManTour is banked + linked but
                                             -- excluded from TGF career stats,
                                             -- trophy case, member Spotlight)
    source        TEXT NOT NULL,             -- 'recon' | 'gg-links'
    status        TEXT NOT NULL,             -- 'alive' | 'gone'
    website_id    TEXT, league_id TEXT,      -- discovered per recipe
    last_probed_at TEXT
);

-- One row per data-bearing portal page (from the coverage map)
CREATE TABLE gg_history_pages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    portal_id     INTEGER NOT NULL REFERENCES gg_history_portals(id),
    gg_page_id    TEXT NOT NULL,             -- the /pages/<id> number
    page_title    TEXT,                      -- verbatim nav label
    page_kind     TEXT,                      -- 'event_results','season_standings',
                                             -- 'monthly_points','match_play',
                                             -- 'money_leaders','directory','other'
    widget_type   TEXT,                      -- discovered per era ('season_points',...)
    raw_archive_id INTEGER REFERENCES gg_raw_archive(id),  -- verbatim HTML hedge
    fetch_status  TEXT, fetched_at TEXT,
    UNIQUE(portal_id, gg_page_id)
);

-- One row per player per standings table (points races, cups, money lists)
CREATE TABLE gg_history_standings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id       INTEGER NOT NULL REFERENCES gg_history_pages(id),
    contest_label TEXT NOT NULL,             -- verbatim ('2016 POINTS RACE')
    season        TEXT, chapter TEXT,        -- denormalized for query ease
    position      INTEGER,
    player_name   TEXT NOT NULL,             -- VERBATIM as GG printed it
    customer_id   INTEGER REFERENCES customers(customer_id),  -- resolved link
    points        REAL, money_cents INTEGER,
    gg_member_ids TEXT,                      -- data-member-ids when present
    raw_row       TEXT NOT NULL              -- full row JSON, verbatim
);

-- One row per historical event (from event-results walks)
CREATE TABLE gg_history_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    portal_id     INTEGER NOT NULL REFERENCES gg_history_portals(id),
    season        TEXT, chapter TEXT,
    event_label   TEXT, event_date TEXT, course TEXT,
    brand         TEXT,                      -- NULL = inherit portal brand;
                                             -- set for hybrids (2024 Road Trip's
                                             -- Two Man Tour event inside a TGF league)
    gg_round_id   TEXT, gg_round_index INTEGER,
    tracker_event_id INTEGER REFERENCES events(id),  -- link when one exists
    raw_row       TEXT
);

-- One row per player per event result line (per game/tournament)
CREATE TABLE gg_history_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    gg_event_id   INTEGER NOT NULL REFERENCES gg_history_events(id),
    game_label    TEXT,                      -- 'INDIVIDUAL Net 18 $ - d18.5 Net'
    player_name   TEXT NOT NULL,             -- verbatim
    customer_id   INTEGER REFERENCES customers(customer_id),
    team_label    TEXT,                      -- one-off team formats (Two Man)
    position      TEXT,                      -- 'T1' kept verbatim
    playing_handicap REAL, gross REAL, net REAL,
    points        REAL, money_cents INTEGER,
    gg_aggregate_id TEXT, gg_member_ids TEXT,
    raw_row       TEXT NOT NULL
);

-- Identity review queue (unmatched names -> COO action items for Kerry)
CREATE TABLE gg_history_name_links (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_name      TEXT NOT NULL,             -- 'NIESTER, Kerry' verbatim
    portal_id     INTEGER REFERENCES gg_history_portals(id),
    customer_id   INTEGER REFERENCES customers(customer_id),
    matched_by    TEXT NOT NULL,             -- 'exact','alias','handicap_link',
                                             -- 'manual','pending'
    reviewed      INTEGER DEFAULT 0,
    UNIQUE(raw_name, portal_id)
);
```

Notes:
- Raw payload hedge reuses the existing `gg_raw_archive` (url,
  fetched_at, body_gz) — every widget/partial fetched during ingest is
  archived BEFORE parsing, so a GG prune can never orphan us.
- Scorecard-depth data (hole-by-hole) keeps flowing into the EXISTING
  `scoring_rounds`/`scoring_holes` via `import_gg_scorecards` with
  `source` distinguishing history imports; gg_history_* carries the
  standings/results/money layer those tables don't model.
- Identity resolution cascade at insert: exact canonical name match →
  `customer_aliases` → `handicap_player_links` name map → else
  customer_id NULL + a `gg_history_name_links` 'pending' row. Names
  normalized from "LAST, First" before matching. Rule-6 compliant:
  customer_id column present from day one, backfilled as links resolve.
- Ingest order (approved #105): NEWEST-FIRST (2025 → 2016), season
  portals before one-offs; time-budgeted bridge commands
  (`gg-history-ingest:<subdomain>` pattern) repeated until done.

## INGEST ENGINE (v2.70.0 — Phase A live)

`email_parser/gg_history.py` + MCP bridge commands on `probe_golf_genius`
(pass as `extract`; url param is ignored for seed/status):

- `scoring-gg-history:seed` — creates the six tables + seeds the 61-row
  portal registry (idempotent; brands per Kerry's rulings).
- `scoring-gg-history:ingest=<subdomain>[@<budget_s>]` — Phase-A walk of
  one portal: home fetch → league_id/website_id + full nav page catalog
  (`gg_history_pages`, kind-classified) → for every standings-kind page
  (season_standings / monthly_points / money_leaders): iframe widget
  discovery (fallback season_points_v2 → season_points), **raw archived
  to gg_raw_archive BEFORE parsing**, rows into `gg_history_standings`
  (verbatim name + parsed rank/points/money_cents + raw_row JSON),
  identity via `_resolve_scoring_player` (never creates customers;
  misses → `gg_history_name_links` 'pending'). Resumable + time-budgeted
  (default 240s): repeat until `pages_remaining == 0`. 1s sleep between
  pages (polite pacing). Per-page commit.
- `scoring-gg-history:status` — registry-wide progress + linked/pending
  counts.

Phase B (event_results: round-selector enumeration → /v2tournaments
partials → gg_history_events/gg_history_results; match_play pages;
scorecard-depth via import_gg_scorecards) builds on the same page
catalog. Directory pages are login-walled (skipped); `images`-widget
pages record widget_type='images' with no rows.

### Phase B — hole-by-hole walk (v2.74.0, LIVE)

`scoring-gg-history:holes=<subdomain>[@<budget_s>]` →
`ingest_portal_holes()`: fetches the portal's
`/leagues/<league_id>/widgets/tournament_results?shared=false` (the
server-side `<select name="round">` lists the whole season), walks
rounds chronologically, and per round imports the **ALL Net board
first** (full field WITH playing handicaps), **ALL Gross second**
(fills anyone left) — the live auto-sync's proven ordering, prefix
match on board labels. Cards flow through the EXISTING
`import_gg_scorecards` machinery unchanged (courses/tees,
scoring_rounds/scoring_holes, raw-archive-before-parse, cid
resolution, per-card verification with COO action items).

Design points (the POC lessons, applied):
- **`round_date` is mandatory plumbing**: archive events have no
  Tracker `events` row, so `import_gg_scorecards` gained a
  `round_date` param — without it the cross-tournament dedupe can't
  scope (`round_date = NULL` never matches) and ALL Net + ALL Gross
  would double-import every player. Dates join from the export
  channel's `gg_history_events` by round_index (**verified: export
  "Round N" == widget `round_index` N on sa2025**); fallback parses
  the round label; no date → round SKIPPED and reported
  (`rounds_no_date`), never double-imported.
- **`round_key=<round_id>`** scopes the dedupe on multi-round days
  (Hill Country Matches class).
- **`source='gg_history:<subdomain>'`** tags archive rows in
  scoring_rounds (new `source` param) — distinguishes history imports
  from live sync, and gives the future Two Man Tour lane a brand
  filter via the portal registry join.
- **Walk state** = synthetic `gg_history_pages` rows
  (`gg_page_id='round:<round_id>'`, page_kind='event_round') — no new
  tables, resumable (repeat until `rounds_left == 0`), and zero-card
  rounds (postponed events) mark done instead of retrying forever.
  Rounds with no ALL Net/Gross boards report their board labels in
  `rounds_no_boards` (era-drift watch: match-play days, one-off
  formats).
- **Identity**: unresolved card names register as pending
  `gg_history_name_links` rows per portal, then backfill from
  `gg_member_map` when the printed handle maps to exactly ONE
  customer (ambiguous handles stay pending — collision-safe).

### Phase B — per-game money walk (v2.75.1, LIVE)

`scoring-gg-history:games=<subdomain>[@budget]` (+ `games-bg=`) →
`ingest_portal_games()`: same round-selector walk; per round every
per-tournament board EXCEPT ALL Net/ALL Gross/Adjustments (INDIVIDUAL
Net $, SKINS $, TEAM Net $, MVP $, CTPs, …) is parsed into
`gg_history_results`: verbatim board label as game_label, verbatim
'T1' positions, purse/points parsed, team rows flagged via
team_label. Rows attach to the SAME `gg_history_events` row the
export channel created (round_index join) — export rows
(game_label='export_round') and scrape rows sit side by side per
event; scrape rows replace idempotently, export rows never touched.
Fetch-then-write per round (no write txn across network I/O — walks
may run concurrently). Walk state: `gg_history_pages`
'games:<round_id>' rows. `_resolve_identity` cascade (v2.75.1):
scoring resolver → roster map (single-customer handles) → earlier
ruling for that name+portal, so manual links propagate to all future
walks. NOTE (python-sqlite3 trap, cost one prod hotfix): CREATE TABLE
runs in autocommit but DML opens a transaction — any DDL+copy
migration MUST self-commit, or a read-only caller strands the shell
table.

Ingest order (Kerry: slowly, backwards chronologically): the 2025 wave
(sa2025, austin2025, champ25, lonestarcup25, roadtrip25) → 2024 wave
(incl. DFW/Houston finales) → … → 2016. **Two Man Tour portals ingest
LAST and live in their own brand lane** (Kerry 2026-07-11: the Tour
"needs its own Two Man Tour home… no functional crossover currently" —
TGF members who played Tour events still identity-link via customer_id,
ready for the future partner build, invisible on TGF surfaces).

## THE THREE-CHANNEL FRAMEWORK (Kerry + tracker-claude, 2026-07-11 late)

GG admin EXPORTS joined the design as the third channel. Verified
audit-grade: the SA 2026 Season Scores export matched the Tracker's
independently-scraped scorecards stroke-for-stroke on every spot-check
(Anthis: 5 rounds, gross/net/course-handicap all exact).

- **Channel 1 — Portal scraping (Phases A/B):** ONLY source of
  hole-by-hole scores (Kerry's #1), per-game money breakdowns, game
  results/flights/MVP marks, season-contest standings, brackets,
  course/tee detail.
- **Channel 2 — GG admin exports (Kerry downloads, 2 files/league):**
  ONLY source of at-the-time Handicap Index + Course Handicap series,
  Adjusted Gross, DOBs/gender/tees, "Referred By" (referral graph!),
  payout Venmo handles, registration status, league-scoped member ids,
  deleted-round visibility (SA 2026 Round 13 was removed — exports show
  the true round ledger), and everything behind the members-only wall.
- **Overlap = the audit zone:** per-round gross/net, money totals,
  points, names, event dates — each channel proves the other honest.

Season Scores export shape (9 sheets): Player Summary · Gross / Net /
Adjusted-Gross score matrices (player × round) · Course Handicap +
Handicap Index histories (player × round — at-the-time values!) ·
League Rounds (round# → event name + date) · Purse Summary + Points
Summary (player × round). Roster export: league-scoped id (header
carries the league id — confirmed 514047/514705 for the live leagues),
handle, email, index, tee, DOB, gender, referred-by, payout handles.
**GG numeric ids are CONTAINER-SCOPED** (Aguilera: 41019465 in SA 2026
vs 41580950 in the master) — handle+email are the stable person keys;
per-league rosters decode that league's internal ids.

Staged so far in `email_parser/data/gg_exports/` (converted to CSV;
rosters trimmed to id/handle/email/affiliation/start_year/status/index/
tee — DOBs/phones stay in Kerry's xlsx files, re-uploadable on demand):
**sa2026 + austin2026 full pairs** (9 score sheets + roster each).
Export-pair ingest (template: gg_history_events from league_rounds,
per-round gg_history_results from the matrices, handicap series →
future bridging, parity audit vs scoring_rounds) is the next build.
Kerry pulls further leagues' exports backwards through the seasons as
convenient; attach in chat, any batch size.

## PROOF OF CONCEPT COMPLETE: 2025+2026 (Kerry-directed, 2026-07-11 late)

All eight export pairs ingested to gg_history_events/results (205
events, 3,199 player-rounds; 2026 leagues 100% identity-matched, 2025
~97%) on top of the Phase-A standings. Cross-channel audit: **1,305
checks, 95.1% exact.** Every mismatch falls into three EXPLAINED
classes — the lessons for scaling backwards:

1. **Post-import score edits (sa2026: 9 of 599).** Export reflects
   GG's current values; our scrapes captured import-time values.
   Off-by-1-2 strokes mostly (one WD/adjustment case: 63 vs 119).
   LESSON: the audit is a living reconciler — mismatches = "rescrape
   this event"; neither channel is wrong, they're snapshots at
   different times. Archive years are frozen, so this class vanishes
   going backwards.
2. **Multi-round days break the (customer, date) join (hcm2026: 36
   flagged, most values present in the same day's other rounds).**
   Hill Country Matches plays 6 rounds one Saturday; date-join can't
   pair them. LESSON: audit joins need round labels on multi-round
   days (the scorecard importer's round_key concept, applied to
   audits). Match-play stub rows (gross 4/5/7 = holes-won entries)
   need a format guard.
3. **Per-round purse ≠ season money (sa2025: 9; champ2025: 10).**
   The export Purse Summary is per-ROUND money only; the scraped
   MONEY & SCORING standings include season-contest payouts (repeating
   deltas like +$30.38/+$69.43 = season-end pot shares). LESSON: the
   channels measure different money scopes ON PURPOSE — results-level
   money comes from exports/Phase B, season-total money from
   standings; career winnings = standings-level truth.

Clean sheets: austin2026 369/369 · austin2025 88/88 · roadtrip2025 9/9.
lsc2025: 0 checkable — its portal money page is an image, the export
is the ONLY structured source (the channel-redundancy thesis proven on
the first season tried).

Roster map APPLIED (map-only): 1,089 rows, 365 customer-linked;
league rosters added 753 league-scoped id rows. The 219 unmatched
TGF/Former profiles remain Kerry's open decision (option b).

## Status

- [x] Coverage map complete: 59 live portals, every in-scope league
- [x] Access recipe proven both eras; naming chaos catalogued
- [x] Schema RATIFIED (Kerry 2026-07-11) — tables ship in v2.70.0
- [x] Phase-A ingest engine + bridge commands (v2.70.0)
- [x] **2025 wave INGESTED (2026-07-11, first live run):** sa2025 (19
      pages/921 rows), austin2025 (17/842), champ25 (8/170), roadtrip25
      (1/10), lonestarcup25 (1 page, 0 rows — its LEADERBOARD/MONEY page
      is the images-widget class; Phase-B/manual item). Totals: 46
      standings pages, 1,943 rows, 1,871 identity-linked (96.3%), 38
      unique names pending review. Idempotency verified (re-run = 0
      work). league_ids discovered: sa2025 453183, austin2025 454934,
      champ25 491299, lonestarcup25 502416, roadtrip25 465797.
- [x] **MASTER ROSTER INGEST (v2.71.0, Kerry-directed "master roster
      first"):** Kerry's GG admin export (Golfer Spreadsheet V6, 1,089
      golfers, unique GG member ids, 98% emails, Start Years to 2007)
      trimmed to matching essentials and committed as
      `email_parser/data/gg_master_roster_v6.csv` (phones/DOBs
      deliberately NOT committed — they stay in the xlsx, layer later
      via the review UI). New `gg_member_map` table (GG member id →
      customer_id + handle/email/affiliation/start_year). Bridge:
      `scoring-gg-history:roster=report` (dry-run match report — email
      exact match first, then the handle cascade) | `roster=apply`
      (write map + backfill gg_history_standings.customer_id and
      pending name-links via handle join). The roster `handle` column
      is the EXACT "LAST, First" string standings print — a direct
      join key. Report-first discipline: apply only runs after Kerry
      sees the report.
- [ ] 2024 wave next (incl. DFW/Houston finales) → … → 2016 — 2025
      completes FIRST (Kerry's year-at-a-time directive)
- [x] Hole-by-hole ingest engine (v2.74.0): Phase-B walker
      `holes=<subdomain>` live — see "Phase B — hole-by-hole walk"
      above.
- [x] **sa2025 HOLES PILOT COMPLETE (2026-07-12):** all 47 published
      rounds walked (the export's 65 include unpublished/postponed
      rounds the selector omits), **ZERO per-card verification
      discrepancies** season-wide, ALL Gross deduped 100% against ALL
      Net (full-field Net coverage). Only the two Match Play bracket
      rounds carried no ALL boards (board labels 'HORTON v BOOKER…'/
      'MATCHES — SAN ANTONIO Match Play' — the match-play work item).
      Cross-channel audit (audit=sa2025): scoring **1,203 checks 96.9%
      exact**; money 111 players 91.9% (all 9 misses the known
      season-pot class). The 37 scoring flags classify as (a) net
      off-by-1 with gross exact (plus-handicap rendering), (b) gross
      off-by-1–2 (late GG edits), (c) a few large deltas on
      shared-surname pairs (Nielsen Mike/Travis, Fieber Duncan/Scott)
      — likely resolver cross-attribution, ON THE SPOT-CHECK LIST
      before career stats surface.
- [ ] Row-level handicap_rounds ↔ gg_history_events bridging by
      (customer_id, date) once Phase B yields event dates — extends the
      existing handicap_rounds.scoring_round_id pattern backwards.
      (Holes walk already bridges opportunistically at import.)
- [ ] Phase B remaining: match play brackets + pairings (Kerry's
      ruling: tee-sheet scrape primary / starter-sheet PDFs cross-check
      / score-groups tiebreaker)
- [x] Review UI (v2.75.0): /admin/gg-history — pending-names queue
      (Link/Guest/Not-a-person + Undo, same-surname candidate chips,
      backfill on link), per-portal coverage, standings browser. ONE
      aggregate COO action item tracks the pending count (synced by
      walkers + every review action; auto-completes at zero). The
      deferred #123 name_links 3-col uniqueness rebuild shipped with it:
      UNIQUE(raw_name, portal_id, gg_member_id), gg_member_id NOT NULL
      DEFAULT '', idempotent boot-path migration, writer upsert on the
      3-col target, reviewed rulings never overwritten by automated
      passes. Bridge ops: holes-bg=<sub>[@budget] (daemon-thread walk;
      MCP clients time out ~60s) + holes-status + overview.
- [ ] Two Man Tour lane (last): verify per-course events inside
      tgf-twomantour; ingest under brand='TwoManTour'
