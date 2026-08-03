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
