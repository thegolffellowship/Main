# Member Portal & Email Summaries — M1 LIVE (v2.28.0), M2/M3 designed
#   + Platform roadmap: native app + website (plan of record, 2026-07-05)

## Pinless Member View — LIVE (v2.53.0, Kerry)

Distinct from the token-based `/me` portal below: a fully PUBLIC,
anonymous, read-only view at `/member` (→ `/member/contests`,
`/member/handicaps`) — one URL Kerry can blast to the whole membership.
It reuses contests.html/handicaps.html with `member_mode=True`, backed
by the new `member` role tier (rank 0, below view-only) in app.py —
`@require_role("member")` GETs serve anonymous callers. Only PII-free
reads declare the tier; see CLAUDE.md → Auth for the exact rules
(customers/events endpoints stay view-only+). `window.MEMBER_MODE`
short-circuits auth.js (no login modal, currentRole = null so all
manager/admin UI stays hidden), the nav shows only Season Contests |
Handicaps, /customers name links render as plain text, and the version
badge loses its /changelog link. The Contests page carries the orange
ENTER SEASON CONTESTS registration CTA in both normal and member views.

M1 shipped: `/me?t=<token>` (templates/me.html, mobile-first) + token-only
API endpoints in app.py (`/api/me/summary|scorecards|scorecard/<id>`),
`get_member_summary`/`make_portal_token`/`verify_portal_token` in
database.py, `customers.portal_token_version` (guarded ALTER), shared
renderer static/js/scorecard-render.js (mirror of the Contests card —
keep in sync), admin link endpoint GET
/api/customers/<cid>/portal-link (manager) and the scoring-portal-link
bridge command. End-to-end tested: 401 on bad/absent/revoked tokens,
404 on cross-customer card access, revocation via version bump.

Original design (M2 recap emails + M3 digest still to build):

The first true CUSTOMER-VIEWS surface (guiding principle 5). Members see
their own scoring records, handicap trend, and points-race standing —
no staff PIN, no ability to see anyone else's private data.

## Identity & access (the key decision)

Members are customers, not staff — the PIN/role system does not apply.
Reuse the **signed magic-link token** pattern that already exists for
membership roster opt-in (memberships.py): a per-customer HMAC-signed
token embedding customer_id + issued_at, delivered by email, verified
server-side with SECRET_KEY. Rules:

- Every `/api/me/*` endpoint resolves customer_id FROM THE TOKEN ONLY —
  never from a query param. There is no way to ask for someone else's id.
- Tokens are long-lived (a season) but revocable: a per-customer
  `portal_token_version` column is salted into the signature; bumping it
  kills all outstanding links for that member.
- Later, TGF Platform accounts replace magic links; the endpoints keep
  the same shape (token → session → customer_id).

## "My TGF" profile page (M1)

Mobile-first single page at `/me?t=<token>`:

1. Header — name, chapter, member status, current handicap index.
2. Season snapshot — rounds played, best gross/net, stableford average,
   points-race rank(s) with POINTS RESET projection (reuses
   get_points_race_standings filtered to self).
3. Handicap trend — differentials over time (sparkline), from
   handicap_rounds today, scoring-derived after Phase 2 lands.
4. Scorecards — the same expandable hole-by-hole cards already built for
   the Contests drill-down (prRenderScorecard is reusable as-is; the
   /api/me variants force customer_id from the token).
5. Stats — par-3/4/5 scoring averages, performance by stroke-index
   bucket, best/worst holes. All computable NOW from scoring_holes +
   course_tee_holes (full 2026 season imported).

## Email summaries

- **Post-event recap** (M2, highest value): fired when an event's
  scorecard import completes — your hole-by-hole card, gross/net/
  stableford, points earned, race position and movement, handicap
  delta, plus your magic link. Send path: existing Graph mailer
  (report.py); one template rendered per registered player with a
  scorecard on file.
- **Monthly digest** (M3): rounds this month, trend arrow, standings.
- Opt-in/out flags per customer (pattern: memberships roster_choice);
  unsubscribe link in every mail.

## Rollout order

M1 profile page + an admin "Copy portal link / email link" button on the
Customers page → M2 post-event recap automation → M3 stats deep-dive +
monthly digest → Platform accounts later. M1 has zero schema risk (one
token-version column) and reuses existing renderers and read paths.

## Privacy rules

Own data only behind the token; anything cross-player (leaderboards,
race standings) shows exactly what the public GG portal already shows.
No emails/phones/DOBs anywhere on the page.

## Platform roadmap: native app + website (PLAN OF RECORD, 2026-07-05)

Admin-agreed path from the Tracker to the TGF Platform's member-facing
app. Core insight: **"native app + website" is one backend with two
faces**, not two products. The website stays the admin/manager console;
the app is the member experience; both consume the same API against the
same database, so nothing can drift.

```
                    +- Website (admin/manager console — today's Tracker)
One backend + API --+
                    +- Member app (scores, points, RSVPs, live scoring)
```

Phases — each independently shippable, each building on the last:

1. **Member portal as mobile-first website** (M1 above — LIVE). The
   magic-link portal IS the app's foundation; everything after is
   packaging and plumbing.
2. **PWA** — manifest + service worker + offline cache on the portal:
   installable from the browser ("Add to Home Screen" → TGF icon,
   full-screen, no chrome). This phase also carries the **offline
   score-entry queue** required for own live scoring at courses with
   dead zones. Still one codebase.
3. **Capacitor wrap** — the same web app inside a native iOS/Android
   shell: real App Store / Play Store listings, reliable push
   notifications, camera/GPS access. Thin wrapper, zero rewrite.
   Process costs: Apple dev account ($99/yr), Google ($25 once), app
   review, TestFlight beta with members first. A ground-up
   Swift/Kotlin rewrite is explicitly NOT the plan — doubles the
   codebase for benefits this class of app doesn't need.
4. **Native dividends** — push ("results are in — you finished T2"),
   tee-time reminders, live championship alerts; later GPS/camera
   features.

Architecture requirements underneath:

- **API-first discipline from phase 1**: every member-facing feature is
  a JSON endpoint + UI (the /api/me/* token pattern), never a
  server-rendered page. Admin pages may stay Jinja.
- **Real-time channel**: the live-updates ladder (v2.31.2 fingerprint
  skip → targeted DOM updates → SSE/WebSocket push) serves both the
  website's live standings and the app's live feed. Same work, double
  duty.
- **Database growth path**: SQLite on Railway is fine until live
  scoring means many concurrent writers; then Postgres — scoped as
  **Supabase** for the Platform (managed Postgres + auth + realtime
  subscriptions + row-level security; realtime is the live-scoring
  push channel, RLS is the members-see-own-data rule at the DB layer).

Sequencing against the real calendar: championships live standings
(website, GG-tap) → member portal M2/M3 → PWA + shadow-mode live
scoring pilots at regular events → Capacitor + TestFlight → stores.

### Amendments from the 2026-09-03 session (Kerry-ruled)

Four things settled while building the Lead Center and data-safety work
that constrain the Platform build. They belong here because each one is
cheaper to honor from day one than to retrofit.

**1. Consent is a first-class Platform concern, per channel.** Kerry:
*"opted out relates to communication correspondence that we absolutely
need to honor for our TGF Platform build and future consolidated
communications, so I think it needs it's own thing."*

**Archived is a STATE (ours to change). Opted-out is a PROMISE (theirs,
and it survives every migration.)** Consent must NOT live on
`account_status` — a single status column cannot express "active member
who does not want the newsletter," and folding it in means a routine
status change silently revokes a promise. The Platform consolidates
email, SMS and portal messaging, so model consent **per channel, with
the date and source of each opt-out recorded**.

**PARKED at Kerry's direction, do not decide in passing:** whether an
active member can fully opt out. The real line is **transactional**
(your tee time moved, your payment failed) versus **marketing** — the
former is arguably not opt-out-able while someone is a member, and that
distinction is also what keeps a business on the right side of consent
law. This needs its own conversation.

**2. The customer table is the identity spine, back to 2007.** Not a
list of currently-active people. Golf Genius history keeps arriving and
will eventually reach the beginning. Every person who has ever touched
TGF exists **exactly once**; "archived", "inactive" and "banned" are
states on that record, never reasons to withhold one. The Platform's
member model inherits this — one customer, one record, forever.

Standing rule for any identity matching, anywhere: **confident matches
merge, uncertain matches go to Kerry, nothing is ever guessed.** A wrong
merge silently fuses two people's histories with no clean way to find it
later; an unmatched record costs one row.

**3. The stack is IMPLIED, not decided.** Supabase is scoped above, and
a Supabase project named "TGF Platform" (Postgres 17) exists — but it is
**INACTIVE/paused**, created January 2026 and never built on. Vercel
holds five projects including `v0-golf-event-platform` and
`v0-golf-fellowship-design-system`. The tooling points at
TypeScript/React on Vercel over Supabase, but **no one ever made that
call explicitly.** Marcus should decide it deliberately before the first
line is written, rather than inheriting it by accident.

**4. Vercel is on the HOBBY plan, which prohibits commercial use.**
Nothing enforces it today. The moment the Platform serves real members
it is a terms violation, and the failure mode is the project being
pulled rather than an invoice arriving. Pro is $20/month. **Fix before
launch, not after.**

### Data-safety precedent the Platform inherits

The Tracker's nightly backup (v2.296.0) established three rules worth
carrying forward: take a **consistent** snapshot rather than copying a
live database; **verify integrity before shipping** a backup anywhere;
and treat a backup as unproven **until a restore has actually been
performed**. The Platform's Postgres will get this from Supabase's
managed backups, but the restore-drill discipline is ours to keep.

Related: live points standings during events (GG live scoring tapped
and converted to provisional race points — points = net Stableford
floored at 0, verified 2026-07-05 against member details) and the
own-live-scoring shadow pilot are documented decisions from the same
planning thread; see docs/claude/scoring.md for the points-model
finding.

## Player Spotlight (v2.67.0 — ADMIN PREVIEW, Kerry-directed 2026-07-10)

`/spotlight` — type any player's name, get their story: handicap index
(18/9), stat tiles (events played / contests entered / season
winnings), a WHERE THEY STAND card per points race (rank of field,
points, events, flight, projected reset, BOUGHT IN pill), fall buy-in
cards, City Match Play card (pool, W-L-D, Stableford), projected Lone
Star Cup seat/alternate chip, five most recent winnings.

- Backend: `search_spotlight_players(q)` (typeahead; members only) +
  `get_player_spotlight(customer_id)` in `database.py`, composing the
  persisted points snapshots, cup projection, cmp standings,
  handicap_player_links, get_customer_winnings, and the LSC projection.
- Routes: `/spotlight` page + `/api/spotlight/search` +
  `/api/spotlight/player` — ALL admin-only until Kerry ratifies the
  member rollout after CA/CD iteration.
- **PII-FREE BY DESIGN**: payloads carry name, chapter, and competitive
  data only. Flipping to the pinless member tier is a role-string
  change; never add contact fields to these endpoints.
- Deferred to iteration: Monthly standing (get_monthly_points does live
  GG page walks — too heavy per player; needs a snapshot path first),
  recent-rounds drill-down (member_card is already in the payload for
  the existing points-race/detail endpoint), head-to-head comparisons.
- **Ratified build set (mailbox #99, Kerry 2026-07-10):** four adds —
  (1) "what's in reach" line per standing card, (2) leaderboard names →
  spotlight deep links, (3) NOT ENTERED → ENTER doorway on a member's
  OWN spotlight (needs a self-identity mechanism — member pages are
  pinless), (4) empty states as invitations quoting the live pot.
  design-claude passes on visuals FIRST, then tracker-claude wires.
  Privacy ruling: aggregated Season Winnings OK member-facing; past
  members stay member-hidden in search. **Backend prep shipped
  (v2.67.1):** payload `races[].in_reach` {points_to_next,
  projected_payout_cents (CONTESTS payout walk mirrored server-side:
  `_spotlight_assign_payouts`), next_payout_cents, pot_cents} +
  top-level `race_pots` (every race + cup, entered or not).

**SCORING aggregate (v2.68.0 — #103/#104 SCORING card data):** payload
`scoring` block from `_spotlight_scoring(conn, cid)`: last-20-round
window → `par_avgs` {3,4,5: avg/trend/holes}, `distribution`
(eagle_plus/birdie/par/bogey/other), `avg_gross_9` + `avg_gross_18`
(separate — TGF is mostly 9-hole rounds). Trend = last 10 rounds vs
prior 10 (NOT 20/20 — season volume is ~21 rounds max); suppressed
below 15 rounds. Par joins course_tee_holes via the round's tee;
strokes-null or par-null holes skipped. None when a player has no
tracked rounds. Coverage note: scoring_rounds starts at the 2026
scoring go-live — the GG history ingest (mailbox #100/#105) deepens
this for career-scale windows later.

**Dense layout WIRED (v2.69.0 — handoff spotlight-mobile-scoring-071026,
CA GO #111):** spotlight.html now renders the density pass: single-band
hero (+LSC line), 3-across stat strip, SCORING card (par tiles, 9-hole
avg primary, muted conditional 18-hole, earned trend arrows, EAG→OTHER
distribution with muted zeros), one-card WHERE THEY STAND compact rows
(IN/NOT IN micro-pills, Players Cup rank in burnt orange), single-line
winnings; intro copy hides once a player loads. Desktop shows the same
dense column (max-width 620px) pending CD's desktop pass. NEXT per
sequence: #99 build set (in-reach lines, leaderboard deep links, ENTER
doorway, invitation empty states) + "This is me" (#106) once CD layers
them; member flip stays gated on Kerry's explicit ratification.

**Post-championship Spotlight wave (v2.193.x–v2.194.0, Kerry 2026-08-03):**
WHERE THEY STAND reads the LIVE points boards via `get_points_race_live`
(not stale snapshots); recent winnings group per event in `<details>`
expanders with friendly game lines from `_friendly_game` ("Individual
Net — 1st Place | Low Flight", skins holes, team partners via
`_team_partners`); a navy (#002868) LONE STAR CUP row renders on EVERY
spotlight until the `lsc_selection_deadline` dial (default 2026-08-14)
— modes: seat (payload `status`: `secured` = locked champion seat, SEAT
· locked 🔒; `projected` = PROJ · seat), alternate, in_hunt (enrolled,
outside seats), hypothetical (NOT enrolled: best hypothetical seat off
either cup board if the season ended today) — after the deadline only
enrolled cup players show the row; Fellowship seat count is the real
projection count (co-captain year 6→5). The hero index tile deep-links
to `/(member/)handicaps?player=<handicap_player_name>` (pins + expands
+ pulses, same link the recap emails use).

**YOUR TGF SNAPSHOT email (v2.194.1 — MOCK phase, Kerry 2026-08-03):**
`build_player_snapshot_email(cid, to_address, send)` in database.py /
bridge `scoring-snapshot-email:<cid>[|<to>][|send]`. Personalized
reset-comeback email built entirely from the live spotlight payload
(races[].points_back / leader_points / n_within_15 added same release):
where they stand, points off the lead on the reset seeds, the
within-15 field count (Kerry: the reset is TGF's Tour Championship —
~30 players in range), the ~72-point shoot-your-handicap weekend math,
and the VERIFIED Freund 2024 story (30th/last on the 2024-08-01 seeded
board, 14.5 back, won the Fellowship Cup by 2.5 — tgf-champ24 GG
portal, season_points_v2 widget with effective_date). Navy LSC line
per spotlight mode — for in_hunt/hypothetical it measures from the
SEAT LINE on both cup paths (Kerry: "making your city's Lone Star Cup
team is an even lower bar"): lsc payload carries `paths[]` with
`seat_cut_points` / `my_points` / `gap_to_seat` (v2.194.2). CTA
deep-links `/member/spotlight?player=<cid>`.
**Sends only to the named/admin address — member sends are rule-3b
gated on Kerry's ratification.** Seat-line gaps ≤1 translate to golf
("That's one net bogey at the TGF Championship" — Kerry's framing).
**Targeting queue (v2.195.0, widened v2.196.0):**
`snapshot_target_list()` / bridge `scoring-snapshot-targets[:window|seat]`
segments every cup-board player — `push_entry` (in the window, NOT
bought in: ≤15 back of the lead OR within 15 of an LSC seat line),
`defend` (in window, bought in), `normal`. Each entry carries
`tgf_champ_signed_up` (a registration PURCHASE for an upcoming
`%CHAMPIONSHIP%` event via `_tgf_champ_signups`; None = no fall
championship posted yet) and `tgf_champ_rsvp_only` (matched YES RSVP or
rsvp_only placeholder row with NO purchase — Kerry 2026-08-06, the Mike
Marques split: RSVP'd players must not read as signed up). REVIEW QUEUE ONLY — availability ("he'll
be in Hawaii") is Kerry's call; nothing auto-sends. The email adds a
"Be there for the weekend itself" section (TGF Champ + LSC = top two
experiences, family, getaway) when the player isn't signed up.
**SNAPSHOT COMMAND CENTER (v2.196.0)** — `/admin/snapshot-center`
(admin): queue tabs + per-player Preview (exact HTML in an iframe),
Approve / Defer(note) / Skip / Clear marks (`snapshot_center_marks`
app setting), Send Test → admin inbox, real Send → player's primary
`customer_emails` address, GATED on an approved mark (Kerry's click is
the per-send rule-3b ratification; no bulk send exists).
FUTURE (platform, once player logins exist — Kerry 2026-08-03): member
self-service "out of town" calendar windows that suppress sends or at
least inform managers.

## Member UX Audit S1 package (v2.86.0, Kerry-ratified mailbox #149–#151)

- **D1 — status source of truth:** member-facing surfaces derive status at
  READ time from Tracker financial truth via
  `derive_member_financial_status(_bulk)` (database.py): `member` = current
  customer_memberships term OR active membership purchase ≤366 days;
  `alumni` = had one, lapsed (our term; GG roster keeps FORMER per D2);
  `guest` = never bought. `customers.current_player_status` is no longer
  read by spotlight chip/search or board pills (it remains for admin
  surfaces + ladder eligibility, unchanged). GG-drift report:
  `gg_roster_drift_report(urls)` / bridge `scoring-gg-drift:<roster-url>`.
- **F18:** spotlight `stats.events_played` = distinct events among the
  current season's tracked rounds (all statuses), floored by the old
  race-standings tournaments value.
- **R3:** `search_spotlight_players` indexes everyone tracked (non-empty
  name, not archived). Payload adds `member_status`.
- **R1:** spotlight chips — member green; guest grey + JOIN → link;
  alumni no label + amber REJOIN → link (spotlight.html `statusChips`).
- **R4:** `get_points_race_standings` no longer hides non-enrolled
  non-members; every row carries `member_status`/`is_member`;
  `hidden_nonmembers` is always [] (kept for payload compat). Ladder
  eligibility + reset points UNCHANGED. contests.html rowHtml renders a
  GUEST/REJOIN pill.
- **R2:** member-nudges.js — follow-through dismisses (beacon kind
  `followthrough`), standings tip forced to bottom toast, `player=`
  deep-link arrival suppresses tips, 360px max-width.
- **R5:** member CTA "Enter Events & Contests" opens a two-button chooser
  sheet (`_shell_nav.html` member branch + shell.css/shell.js;
  contests.html mobile banner opens it via `.shell-cta-open`).

**CURRENT / PAST CONTESTS split (v2.284.0, Kerry 2026-09-01):** WHERE
THEY STAND now renders live contests under a dark CURRENT band and
folds every race whose payload says `final` into a collapsed
`<details>` PAST CONTESTS section, grouped by year bands (year parsed
from the race label, current-year fallback) — newest year first, so
2026 folds away automatically when 2027 races appear and historical
backfills get their own bands. Match Play / LSC rows stay in CURRENT
(no final flag yet). Fall races: RACE_HASH/RACE_ORDER carry
`san_antonio_fall_net` / `austin_fall_net` (rows deep-link to the fall
tabs); the "Starts Aug 29" placeholder is retired — it renders (as a
LIVE-badged "play a fall event to get on the board" row) only for a
fall buy-in with no board row yet.

**Spotlight perf + stands completeness (v2.285.0, Kerry 2026-09-01):**
`_spotlight_shared` gives the customer-INDEPENDENT reads (each race's
`get_points_race_live`, the cup and LSC projections) a 120s in-process
TTL cache keyed per db_path — profile clicks re-ran all of them (~9s
measured live; warm loads now ~0.6s). WHERE THEY STAND additions: a
MONTHLY POINTS row for the current month off the `monthly_points`
gg_snapshot (one DB read; `on_board: false` renders a "play an event
this month" nudge — every member is automatically in); Match Play
carries `complete` (season's `cmp_bracket` final has a winner_name) and
folds into PAST CONTESTS under its season year; THE FELLOWSHIP CUP's
`final` now reads the `gg_points_race_final` dial (it was hardcoded
False — the dial already said 2026-08-16). Rows inside PAST CONTESTS
render no status badges (Kerry: the section says COMPLETED already).

## Winnings by Game + SEASON | ALL-TIME scope (v2.372.0, Kerry ratified 2026-09-11)

Kerry (improvements lane, verbatim ask): *"show members how much
they've won in each specific game type. Like Team Net total, or
Individual Net, or Skins, and also per each bundle like NET Games or
GROSS Games."* Ratified as Option A — bundle-first rows that expand to
per-game rows — plus three rulings during build: the scope toggle sits
at the TOP under the name header and flips the whole page (stat strip
AND the new panel), SEASON offers a pill per calendar year the member
has data (only 2026 today; default landing = current season), and
zero-dollar bundles still render, with buy-in counts next to every
bundle ("a zero GROSS row advertises the games you're not in").

- **Bundles are rules-as-data**: app_settings
  `spotlight_winnings_bundles` (JSON, same shape as
  `SEED_WINNINGS_BUNDLES` in database.py) maps bundle → categories +
  label + color + which buy-in counter shows (`net`/`gross` = bundle
  purchases, `events` = entries, `contests` = enrollments). Seed:
  NET Games = individual_net + mvp + tgf_mvp · GROSS Games = skins +
  individual_gross · Included Games = team_net + ctp/closest_to_pin +
  longest_putt + hole_in_one · Season Contests (catch_all) =
  monthly_points + the season display-string categories ("City Net",
  "Match Play", "Fellowship Cup", "Players Cup"...). A category no
  bundle names lands in the catch_all bundle — a future game type can
  never silently vanish. Production spelling note (2026-09-11 audit):
  payout rows use `ctp`, older maps say `closest_to_pin` — both are
  seeded and they merge into ONE "Closest to Pin" game row.
- **Payload** (`get_player_spotlight`): `winnings_by_game =
  {current_year, years[], by_year{year: [bundle...]}, all_time:
  [bundle...]}` where bundle = {key,label,color,buyin_noun,buyins,
  total,games:[{category,label,count,total}]}; plus `stats_scoped =
  {years{year: {events_played,races_entered,total_winnings}},
  all_time{...}}`. Both scopes ship at once — the toggle is a client
  re-render, no second fetch. PII-free (labels, counts, dollars), so
  the member tier serves it unchanged. Helpers: `_winnings_by_game`
  (pure — tested in `test_spotlight_winnings.py`),
  `_spotlight_buyin_counts` (mirrors `_event_game_buyers` eligibility:
  credited/refunded/transferred/rsvp_only out, child add-ons upgrade
  the parent, wd keeps only un-credited bundles),
  `get_winnings_bundles` (dial with seed fallback).
- **UI** (spotlight.html): toggle pills under the hero card
  (SEASON <year> | ALL-TIME; per-year pills appear once 2+ years
  exist); ALL-TIME shows the note "historical records will be added in
  the future"; stat strip reads the scoped values. WINNINGS BY GAME
  panel sits between SCORING and Recent Winnings: a proportional
  color-split bar, then one row per bundle (color dot, buy-in count +
  win count, green total; $0 in gray, no chevron when no wins) using
  the SAME details/summary expand pattern as Recent Winnings; game
  rows carry a chip in the admin payout category colors
  (`--cat-*` tokens, hex fallbacks matching tgf.html's CAT_COLORS).
  Bundle totals sum exactly to the payout total, so the panel
  self-audits against the Won tile in the all-time scope.

**Per-event drill-down (v2.373.0, Kerry 2026-09-11 follow-up):** each
game row inside a bundle is itself expandable to the EVENTS that game
was won in — event name, date, flight/place detail, and the amount won
there. Two payout rows in one event fold to one line with the bits
accumulated ("Hole 13 · Hole 16"). The detail parsing (place with
ties, holes, LOW/MID/HIGH or numeric flights, season-standings place)
lives in `_payout_detail_bits`, extracted from `_friendly_game` so the
Recent Winnings labels and this drill-down can never parse the same
row differently. Payload: each game gains
`events: [{event_name, event_date, total, detail}]`, newest first.

**Detail-parse fix (v2.375.0, Kerry 2026-09-11):** cup rows put the
FLIGHT ordinal first ("Players Cup — 1st Flight 2nd place" = Flight 1,
2nd place); the shared `_payout_detail_bits` read that as 1st place in
Flight 2 (caught on Jeff Young's spotlight line). An ordinal-flight
branch now handles that shape (incl. "Champion & 1st Flight winner"
and the championship-close "4th Flight 2nd" form) before the generic
place/flight regexes.

## EVENTS leaderboard on the LEADERBOARD page (v2.377.0 — ADMIN PILOT, Kerry directed 2026-09-11)

Kerry's ask (improvements lane): an EVENTS tab LEFT of Points Races —
ALL | AUSTIN | SAN ANTONIO chips (lands ALL; year selector arrives
with historical records) — listing played events newest first, each
expanding to its games "like Golf Genius's leaderboard but condensed",
with drill-down to individual players. His merge rules (2026-09-11,
verbatim intent): "Only merge Individual Net with All Net, Individual
Gross with All Gross, and MVP with Points. Maintain flights for the
Net and Gross per the event. Place non-flighted members... in the
flights they would have been in if they'd have played. Highlight those
that did buy in. Team Net has it's own. Skins has it's own, and only
needs to show the players bought in and the flights. Closest to Pins
obviously listed separately."

- **ADMIN-ONLY until Kerry approves** (rule 3b): the tab carries
  `admin-only` (applyRole reveals; member pages CSS-backstop it), both
  routes are `@require_role("admin")` — the member flip is two role
  strings + removing the class. Payloads are PII-free by design.
- **Pilot scope is a dial**: `events_leaderboard_events` (JSON list of
  event-code prefixes; seed s9.22 + a9.22 — this past Tuesday; empty
  list = every event with scorecards).
- **Boards per event** (the ratified leaderboard IA, side-games.md):
  TEAM (gg_game_results rows) · NET (whole field, flight-SECTIONED;
  buyers green + ✓ IN; Ind Net money badged) · GROSS (same shape) ·
  SKINS (bought-in players only, in skins flights, skins won badged) ·
  POINTS (net + gross Stableford from the formula layer, MVP-eligible
  buyers highlighted, City/TGF MVP money badged) · PROXIES (CTP /
  Longest Putt / HIO). Non-buyers are PLACED into the flight their
  handicap would have flighted them (boundaries derived from the
  labeled members' playing handicaps — `_flight_sections`, marked
  `assigned` for a dashed treatment); no-handicap rows land in an
  UNFLIGHTED band.
- **Player drill-down**: tapping a row fetches
  `/api/scoring/scorecard/<id>` (already member-tier) and renders the
  hole-by-hole grid with handicap dots.
- Backend: `get_events_leaderboard` / `get_event_leaderboard`
  (database.py); routes `/api/events-leaderboard[/event]` (app.py).
- **Future (Kerry)**: Player Spotlight winnings drill-down event lines
  deep-link to these event records; year selector.
- Also shipped: the admin dark nav gains a **Member View** link
  (`/member`, admin-nav class) — Kerry 2026-09-11: "give me a top
  level link to go directly to MEMBER VIEW."

**Events leaderboard iteration 2 (v2.378.0, Kerry feedback 2026-09-11,
same day):** (1) TEAM shows ALL teams — sourced from event_pairings
groups (Team Net is Foursome v. Field; the closeout's FINAL GG pairing
ingest makes those the played groups) with best-ball net totals
computed from the hole cards, ranked with ties, GG purses attached by
member-surname overlap; each team expands to a GG-style team card
(members' net per hole, counting ball circled, TEAM row + total).
NOTE: scoring_rounds has NO team column — the spotlight's
_team_partners has been querying one that never existed and failing
into its except (#452 shape); pairings are the team truth. (2) The
chapter chips and game sub-tabs are CONNECTED segments. (3) Player
drill-downs use tgfRenderScorecard (scorecard-render.js — the same
card as the Handicaps/Points expands; renders only the nine(s)
played). (4) Handicapped boards carry Index (9-hole index on 9-hole
events) + Playing Handicap columns; the "(4)" name parenthetical is
gone. (5) A game that didn't run is denoted up front: Individual
Gross's activation threshold read from the LIVE matrix per 9/18, with
the note that its pot rolled into Skins (games_off). (6) SKINS is a
GG-style overall chart: buyers per flight hole-by-hole with winning
skins circled (outright low gross within flight, computed from the
cards), and everyone NOT in skins listed below with their hole
scores. (7) POINTS tab is labeled MVP/Points. (8) Tables compress
LEFT (width:auto) instead of filling the screen. Pilot dial expanded
per Kerry: s9.22, a9.22, s9.21, a9.21, s18.10.

**Events leaderboard iteration 3 (v2.378.2, Kerry 2026-09-11):**
hole columns come only from holes actually PLAYED (GG cards carry
empty rows for the unplayed nine — a front-9 event was rendering
1-18); the team card and skins chart adopt THE card standard's metrics
(2px/6px cells, 2em min-width, #e2e8f0 grid, 110px name column) so
they column-align with the expanded player cards; the ball(s) that
COUNTED for the team best-ball score are highlighted (green fill —
circles stay reserved for the standard's under-par mark and the skins
chart's winning skins); the winning team's row is highlighted in the
team list; the nine's total column reads OUT/IN per the side played.

**Skins placement pass (v2.378.3, Kerry 2026-09-11):** the flat NOT
IN SKINS block is gone — everyone not in skins is PLACED into the
skins flight their handicap would have put them in, at the BOTTOM of
that flight in grey (same boundary derivation as the other boards);
buyers stay on top with the circles and skins counts, and placed rows
never contest a skin. `skins_out` removed from the payload.

**Events leaderboard iteration 4 (v2.379.0, Kerry 2026-09-11):**
- **MVP/Points ties**: points ties STAY ties (T# on the board — the
  races never tiebreak); only Event MVP tiebreaks, per Kerry's
  ratified chain (verbatim): "1. Net Score 2. Gross Score 3. Split
  Pot." The top tied group orders by that chain so the MVP winner
  shows first, and every tied MVP-eligible buyer carries a note
  saying how the chain decided ("MVP tiebreak 2 — low Gross (36)").
- **TEAM board is GG-official**: our best-ball total is a
  reconstruction from each player's OWN card dots (100% individual
  allowance) while the real Team Net game plays 75% OFF-LOWEST — so
  the reconstruction can disagree with the recorded result (s9.21's
  $80 winner showed 2nd; s9.22's GG T1 tie split 30/31 here).
  Recorded GG positions + purses now rank the board; unrecorded teams
  follow by reconstruction total, unranked; the panel says which is
  which. Native engine-scored Team Net (live_scoring.py's
  game_team_net with the ratified allowance) is the proper fix and
  belongs to the untether program.
- **CART Net events**: below 16 players the matrix runs 2-man cart
  teams — team grouping now splits each pairing group into cart pairs
  (cart_pos 1-2 / 3-4) when the matrix row's teamType says CART (or
  N<16 fallback).
- **Joint events** (chapter TGF/national — Landa Park) list under
  BOTH chapter filters.
- **Game activation keys off the Tracker's EVENT/GAMES counts** (Kerry:
  "should be checking against Tracker EVENT / GAMES which should also
  be helping determine which games are being played") —
  `_event_player_counts` (the Games-tab mirror) supplies the player
  count that picks the matrix row (team type) and the GROSS buyer
  count that judges Individual Gross activation, not the scorecard
  field size. The Star Ranch team-game override was a one-off with no
  standing dial; if per-event game overrides become a pattern they
  should land as a dial the leaderboard reads too.

**Events leaderboard iteration 5 (v2.381.0, Kerry 2026-09-11 —
"Both, but do 1 first"): TEAM board shows GG's POSTED TOTALS.**
- The games-results walk (`import_gg_game_results`) now captures the
  ENTIRE Team Net board, not just winners: `_game_winners_from_table`
  grew a `total` field (parsed from GG's "TotalNet" column, "30
  (-/30)") and a `winners_only=False` mode returning every positioned
  row. Winner teams keep their `game='team_net'` row (the posted total
  rides in `detail` as `total:N`); non-winner teams store under
  **`game='team_net_board'`** — a key the payout assembly NEVER reads,
  because storing $0 teams as `team_net` would let the matrix-fallback
  pool invent place money GG didn't record (the v2.126.3 phantom-ties
  class).
- `get_event_leaderboard` reads both keys: every team gets
  `gg_position` + `gg_total`; the board ranks and scores by the
  recorded result end to end (GG even ordered s9.22's non-winners
  differently than our reconstruction — WADE's team 5th at 34 vs our
  3rd at 31). Reconstruction totals appear only for a team GG posted
  no total for (muted, titled), and inside the expanded best-ball card,
  which notes when its own-card sum differs from the recorded total
  and why (75% off-lowest).
- Matching hardened: per-MEMBER hits (full "LAST, First" preferred,
  surname on a WORD BOUNDARY as fallback) — the surname-set approach
  collapsed same-surname teammates (married couple in one cart) below
  the foursome threshold, and bare substring let "buyer" hit inside
  "nonBUYER". Blind-draw append is idempotent (a team can match its
  winner row AND its board row).
- Bridges: `scoring-games-import` takes `rewalk=N` (≤12) for the
  backfill; `scoring-event-board:<event>` is a read-only compact TEAM
  board vet (GG pos/total, reconstruction, purse, official).

**Events leaderboard iteration 6 (v2.382.0, Kerry 2026-09-11):
OVERALL view — the new default subtab.** One whole-field table
(rank-by-net · Player · Idx · PH · hole-by-hole gross · Gross · Net ·
Pts · Won) combining every player's scores. Wins highlight by the
RATIFIED payout category colors (`--cat-*` in dashboard.css): Ind Net
win tints the Net total green, Ind Gross the Gross total amber, Event
MVP the Pts total purple, and winning skins circle their hole cells
pink (`.evlb-circ.sk`); a legend explains each. **Buy-ins are
deliberately NOT identified on this view** (Kerry: "Don't identify
those who bought in") — rows carry no buyer flag or won-chips at all,
only the win highlights and the **Won** column = the player's total
recorded money for the event across ALL games (team shares, proxies,
HIO included), from tgf_payouts. Rows expand to the universal
scorecard (same `tr.evlb-plr[data-rid]` delegation). Backend:
`overall_board` in `get_event_leaderboard`; the
`scoring-event-board:<event>` bridge now also returns the overall
summary (wins coded N/G/S/M + won) for no-login vetting.
v2.382.1: winner STRIPS render above the board — the winning Team Net
team(s) (position, members, recorded total, purse; team-net blue) and
every proxy winner (CTP / Longest Putt / HIO; teal) — so the default
view carries the games that don't live in a player row ("the OVERALL
board shows everything").
v2.384.0: money wins color-code BY FLIGHT (Kerry: "anybody who won
money gets color-coded") — flight 1 red, 2 green, 3 blue (+amber,
violet; `EVLB_FLIGHT_COLORS`/`evlbFlightTint`): tinted Net/Gross
totals and flight-colored skins circles, tooltips name game + flight,
legend shows only the flights that paid; MVP keeps the ratified
purple. Backend: overall rows carry `net_flight` / `gross_flight` /
`skins_flight` ordinals (`_flight_ordinals` over the sectioned
boards — 1 = low flight, placed non-buyers included).
v2.385.0: column order is # | Player | **G** | **N** | Idx | PH |
holes… | Pts | Won — the two totals sit immediately after the name
as one-letter columns (Kerry: "move both of those score columns all
the way left"), so a phone reads name-and-score without scrolling
the hole block; titles still spell them out.
v2.384.1: sort headers carry NO arrow glyphs (they padded every
numeric header and widened the column beneath it) — the ACTIVE
sort column is its header cell filled TGF orange, which costs no
width; on load that mark sits on Net, the real default sort key,
not on the derived # rank.
v2.383.0/.1: every column SORTS (tap to sort, tap again to flip;
Pts/Won open high-first; blanks sink), and the # column RE-RANKS
against the sorted column (Kerry: "re-rank based on which column is
tapped") — T# on tied values, blank rank for players with no value
there. Row expansion became ONE delegated click handler on the event
body (`evlbWireEvent`) so sorted re-renders keep tap-for-scorecard;
the overall row template is module-level (`evlbOvrRowHtml`) shared by
initial paint and re-sorts.

**Team Net scoring — LEARNED FROM GG (parity bridge, 2026-09-11):**
`scoring-teamnet-parity:<event>|<gg v2tournaments url>` computes every
plausible reading of 75%-off-lowest from our cards AND reads GG's
ground truth (the team tournament's per-player detail fragments: each
player's TEAM-game handicap + dots). s9.22 findings, proven from GG's
own dots: team PH = 75% × (UNROUNDED course handicap − lowest
unrounded CH in field), rounded half-up, CAPPED at the TGF max
(18 on nines — DelCarmen's 18 is unreachable any other way);
allocation over ALL holes by stroke index (max 2 pops), then dots on
par 3s are REMOVED, not reallocated (Anthis: TH 8 → 7 dots).
EXACT reproduction from our stored data is impossible: we keep the
ROUNDED net-game PH, and its ±0.5 flips several players by a stroke.
The clean fix is importing the TEAM tournament per-player nets the
way ALL Net imports (GG fragments carry the exact THs/dots) — a
schema addition awaiting Kerry's rule-3b ratification. Until then the
board stays GG-official-ranked. Blind-draw slots now render on teams
(parsed from the GG team string's "Bl[...]", card duplicated from the
drawn player's round — GG's own mechanism).
