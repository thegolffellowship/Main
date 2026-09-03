# State of the Tracker — early September 2026 (Platform-facing brief)

Audience: the claude.ai "The Golf Fellowship" Project, where TGF Platform
planning has lived for the past six months. Purpose: catch that planning
context up on what the Tracker actually is today — it has grown far
beyond transaction tracking. Maintained by tracker-claude; check the
platform_dialogue mailbox (read_platform_dialogue on this MCP server)
for session-by-session updates after this brief.

## What the Tracker is now

Flask + SQLite on Railway (tgf-tracker.up.railway.app), version 2.296.x,
~200+ routes, 61+ MCP tools. Started as a GoDaddy order-email parser;
now runs most of TGF's operations:

- **Transactions/orders** — AI email parsing (Claude), order grouping,
  credits/transfers, deep-linking.
- **Customer identity** — canonical customer_id everywhere (the "one
  true identity key" rule), aliases, merge tooling with boot-time
  self-repair, membership terms + automated renewal reminders.
- **Events** — RSVPs (parsed from GG emails), registrations, pairings
  generator (seed/lock/cart pairs/round-robin history), payouts with
  screenshot import (Claude Vision), side-games prize matrix.
- **Accounting** — multi-entity ledger, bank reconciliation with match
  queue, cash-flow view, duplicate detective, month-end close;
  automated expense ingestion (CC/bank alert emails classified and
  categorized by vendor).
- **Handicaps** — TGF 9-hole index system computed from
  handicap_rounds (lookback + best-N differentials), curated GG-name
  links; today's GG sync is a manual CSV export the admin uploads in
  the GG UI — Phase 2 (differential parity, step 1 live) aims to
  derive differentials from our own imported scorecards and kill that
  ritual entirely.
- **Participation** — last-played/frequency/trend analysis per member
  with a re-engagement email composer.
- **COO layer** — dashboard with action items + AI chat (6 specialist
  agents), daily digest email with DB health metrics.
- **SCORING (the big 2026 build)** — hole-by-hole scorecards imported
  from Golf Genius for the entire 2026 season; course DB with tees,
  slope/rating, per-hole pars and stroke indexes; a facts-vs-derivations
  formula layer (net, Stableford gross/net, WHS adjusted gross, net
  double bogey, plus-handicap allocation) that has been parity-verified
  against GG's own numbers. Every parsed GG response is archived
  (gg_raw_archive) so the data outlives GG access.
- **Points races** — live GG-synced standings for SAN ANTONIO Net,
  AUSTIN Net, and THE PLAYERS CUP (persisted snapshots, 12h
  auto-refresh); three-level drill-downs (standings → per-event points
  with dates/positions → hole-by-hole scorecards); event MVP + TGF MVP
  tracking with badges; MONTHLY races (all points count, $1/member
  purse at month close, ties split); Fellowship Cup reset projections;
  a Points tab on every customer profile. **LIVE championship overlay
  (v2.174–176, championship day 2026-08-01)**: during a City
  Championship the member LEADERBOARD adds each player's running
  championship Stableford (read off GG's live POINTS board, 45s server
  cache, 60s member poll) on top of the stored best-10 total and
  re-ranks — with a double-count guard for after GG's close-out folds
  the championship into the season snapshot, customer_id-first board
  matching, and a per-player live hole-by-hole card (gross + dots read
  from GG, NET + champ-scale points computed by us, mismatch vs the
  board stated rather than absorbed).
- **Member portal M1 (LIVE)** — magic-link tokens (HMAC, revocable via
  per-customer version), token-only /api/me/* endpoints, mobile-first
  profile page. M2 (post-event recap emails) and M3 (monthly digest)
  are designed, not yet built.
- **MATCH PLAY (v2.34, July 2026) — the Game Creator engine's first
  concrete build.** The ratified 29-column Match Play matrix (pools,
  knockout sizes, wildcards, first-round byes, pool-winner bonuses,
  payout ladders on a $40×N pot) lives as VERSIONED admin-editable
  config: season_contest_templates / season_contest_versions
  (append-only, payout_templates pattern) + per-season/chapter config
  snapshots (seasons freeze at first structural action). A pure engine
  (email_parser/match_play.py — no DB/Flask, Platform-portable)
  computes structure, seeded brackets with byes, and exact-cents
  payouts (largest-remainder allocation; ties split combined places).
  CONTESTS UI: structure banner, auto-assign pools, server-side
  knockout seeding (Stableford metric, ratified), payouts view, admin
  config editor with matrix preview + pin-season-to-version. This is
  the working prototype of the V2.0 scoring_config JSONB hook.

## Verified league mechanics (July 2026 findings)

These were reverse-engineered from live GG data and cross-verified —
they are load-bearing for Platform scoring design:

- **Race points = each player's Stableford score in the event's
  POINTS game, floored at 0** — net Stableford for NET races, gross
  Stableford for THE PLAYERS CUP. No position→points table exists.
  Season standing = best 10 events + City Championship (both race
  types). (Verified across both models against live GG member details
  and complete event tables, including direct floor-at-0 confirmation
  on a -6 gross round.)
- **Monthly races**: ALL points earned in the month count (no best-10);
  purse = $1 × active TGF members at month close; ties split.
- **member_card_id == GG profile id**, global across GG leagues.
- MVP semantics: winner = purse>0 rows in the event's MVP game (GG
  records tiebreaker outcomes via payment); one MVP per city per event;
  TGF MVP shareable.

## The July 8–14 build wave (v2.5x → v2.104)

The week that closed most of the distance to GG independence:

- **Own handicaps RATIFIED + live** — handicap rounds self-derived from
  our scorecards (WHS net-double-bogey adjusted gross); the manual GG
  CSV export ritual is dead. (handicaps.md)
- **Pairing engine complete** (pairings.md): Kerry's 11-rule standard;
  full 2026 played-with/rode-with history banked from GG final tee
  sheets (nightly 3:20 auto-grab, replace-semantics); NEW-PAIRINGS-FIRST
  optimizer verified optimal vs a 4,000-restart offline search and
  head-to-head better than GG's own scheduler; **Match Play dictates
  pairings** (rule 8 amendment — season-state detection, manager
  confirm gate, opponents same-foursome/opposite-carts, MP badges);
  **pace staging** (1–3 ratings, one-tap editor, groups staged by
  aggregate pace — shotgun fast-to-front, tee-times fast-first;
  composition never affected).
- **Season-contest economics live**: exact-cents payout engines for
  City Net / Fellowship Cup / Players Cup with live projected purses on
  the standings; Best-10+CC season totals; Monthly + Fall races;
  Lone Star Cup 12-seat projection engine; How-It-Works member popups
  (all Kerry-ratified copy).
- **Member tier**: pinless public pages (Spotlight, Leaderboard,
  Handicaps) + Nav Shell v2 app-wide; anonymous member-traffic
  analytics.
- **Event cancellation suite** (born from the s9.18 rain-out, built
  live with Kerry): one-tap execute — status + badge picker (RAINED
  OUT etc.), credit/refund all, RSVP-roster clearing, per-player emails
  carrying exact credit amounts, WYSIWYG preview from the same renderer
  that sends. Pattern note for Platform: plan notification amounts
  BEFORE mutating payment state.
- **GG archive**: 29 portals of history walked (2016–2025), 2026
  pairings from final tee sheets, all raw responses archived — the data
  outlives GG access.

## In flight (July 2026)

**SCORING GO-LIVE is now the plan-of-record work item** — Kerry directed
(2026-07-14) that CA own the full plan + documentation, from
tracker-claude's readiness assessment in mailbox **#187** (topic
platform-scoring-golive). Summary: engine parity, course DB, handicaps,
games/payouts all green; gaps are flighting ASSIGNMENT rules (Kerry
ruling needed), per-game playing-handicap config, the entry-path
decision (shadow-first recommended), the leaderboard surface, and a
print-CSS document creator (Starter Sheet / Cart Signs / Scorecards /
Proximity Marker Sheets — the last needs a per-event game-holes
config, the one datum still trapped in GG).

- **Live championship standings — SHIPPED (v2.174–176), first live fire
  championship day 2026-08-01.** The design above became code: the
  overlay polls GG's live POINTS boards (a settings dial per race),
  adds each player's running championship Stableford to the persisted
  best-10 total, re-ranks live, and stands down after close-out (GG
  only awards season points at manual close-out — Kerry's ruling — so
  absorption is a guard, not a race). Both boards verified parsing
  logged-out from Railway before first tee. Drill-down carries the live
  figure and a per-player hole-by-hole card computed from GG's raw
  facts (v2.176.0, pending merge to main at time of writing).
- **Live-updates ladder** — step 1 shipped (skip page rebuilds when
  fetched data is unchanged); step 2 targeted DOM updates; step 3
  SSE/WebSocket push. Serves both website live standings and the
  future app's live feed.
- **Own live scoring** — **BUILT as of v2.150–v2.151; Stage-1 gate NOT yet
  passed.** The shadow leaderboard + diff harness named in `game-engine.md`
  now exist as the **Live Scoring Test Center** (`/admin/test-center`,
  admin-only): every event game recomputed from raw gross hole scores, live
  in-place GG re-pull, a parity gate that diffs us against GG per player and
  is asserted to be capable of failing, and a Flighting Lab. Full spec for
  CA: `docs/claude/live-scoring-spec-for-ca.md`.

  The reframe worth carrying to the Platform: **the scoring was already
  untethered — the FLIGHTING was not.** `determine_event_game_results`
  computed every game and then took GG's flight labels, returning
  `flights_unknown` rather than guessing. Flighting is the rule that decides
  who gets paid, and it now has one (Kerry, 2026-07-29): flight on raw TGF
  handicap index; two legitimate modes (equal-size and fixed bands); breaks
  are floors for the upper flight; Individual Net's low flight never past
  11.9; gross bands harder with a 3-flight minimum; equal indexes never split
  across flights; thin flights merge — which reproduces "3 flights down to 2
  on a concentrated field" with no separate rule.

  **Blocking unknown:** whether the index is the 9-hole or 18-hole number —
  a silent factor-of-two mis-flight if wrong, so it is an explicit setting,
  never assumed. Also open: minimum flight size, the 3-/4-flight ladders,
  pot-split confirmation, and the late-add/WD scenario matrix.

  First live shadow: SA Championship, 2026-08-01 at The Quarry. Until parity
  reads clean across a meaningful sample of real events, GG stays official
  and none of this drives money. Championships remain on GG regardless.

## The August finals wave (v2.24x → v2.255.28)

The championships month, run live on the Tracker (mailbox digests #~320+
and #333 carry the day-by-day; changelog v2.245–v2.255 is the full record):

- **Live Match Play knockout cards** (contests page): 60s-poll GG match
  detail, nine-scoped finals-day cards driven by the `cmp_match_scope`
  dial (nine / start hole / date / course / pars / tee time per round —
  the dial's start hole OVERRIDES GG's unreliable start-hole mark),
  mis-slotted-entry guard (a score beyond the first unplayed hole in
  play order is blanked), display-FINAL on mathematically decided,
  winner auto-flow into the Final card, post-clinch holes greyed.
  Champion recorded via `scoring-mp-bracket-slot` (now takes winner +
  margin); podium money via `scoring-season-payouts:mp` (now supports
  "A+B" split places for no-consolation chapters).
- **Lone Star Cup rules moved from prose into code**, all Kerry-ratified:
  champion-declined MATCH PLAY seat cascades winner → runner-up → pool
  (rule #88 — exercised for real: both SA finalists declined); a
  cascade-inherited seat secures only on acceptance; alternates
  min-events rule as dial `lsc_alternates_min_events` (default 8,
  accepted players exempt); **events-played = DISTINCT EVENTS from
  registrations** (Kerry-RATIFIED: an Event may have many rounds/nines
  but counts ONCE — GG's Tournaments column counts rounds and was
  demoted to fallback); alternates lists are staff-only (member API
  strips them) and 12 deep.
- **Parser hallucination guard**: a NET/GROSS/Match Play/Fall contest
  flag survives extraction only when the contest is NAMED in the email
  text — Haiku invented a Match Play YES on an order that never
  mentioned it, which auto-enrolled a player. Platform lesson: every
  AI-extraction field needs presence-validation against source text.
- **Money surfaces**: Refunds console is payment-method-aware
  (customers.payment_method → Zelle/PayPal/CashApp badges vs Venmo
  one-tap); TGF Payouts summary shows PAID THIS YEAR;
  `scoring-payouts-coverage` diagnostic proved the payout ledger 100%
  covered and dated (the "light" year figure was seasonal pacing);
  Fall Points Race duplicate-purchase wave (an event-order add-on
  option) resolved with partial credits and the store option removed.
- **Member-facing**: per-URL link-preview cards (1200×400 header-bar
  family) for Leaderboard / LSC / Match Play chapters / Handicaps /
  Spotlight; chapter Match Play deep-link routes; MEMBERS bulk
  handicap-card send mode; sticky Customers page head.

## The September 1-3 wave (v2.257 → v2.296) — Lead Center + data safety

**The Lead Center became a measured acquisition funnel, and the Tracker
got its first real backup.**

- **Campaign entity + live Meta stats** (v2.292.0). `lead_campaigns`
  table, leads auto-linked from their Meta attribution, and a 📊 Stats
  view with a META panel (spend/impressions/reach/CTR/CPM straight from
  the Marketing API, hourly) and a FUNNEL panel carrying Kerry's
  ratified metrics: **CPL** = spend/leads, **CPP** = spend/players
  (registered any event OR became a member, counted once), **CPMem** =
  spend/members — each **current and 30-day trailing**, because
  conversions keep arriving after spend stops.
- **Measured finding: ~7% of leads lose campaign attribution in the
  HubSpot hop.** Meta reports 85 form leads for Fall 2026; the Tracker
  holds 79 attributed + 6 "organic" = exactly 85. The `hsa_*` params do
  not survive the trip. True CPL is $1.52, not $1.63.
- **Duplicate-lead merge** (v2.295.x). The Tracker dedups on HubSpot's
  contact id, so a HubSpot-side merge never propagates back — Kerry's
  two Shane Winters. Detection by email / last-10 phone / name, merge
  that folds notes and recovers payload keys, and a loser that is
  **marked merged, never deleted** (freeing its external_id would let
  the next poll re-create it).
- **48-hour outreach alarm** (v2.294.0) riding the existing follow-up
  rails, and **multi-select triage filters** (v2.293.0).
- **Nightly off-site backups** (v2.296.0). Before this, the entire
  business was one SQLite file on one Railway volume whose only "backup"
  wrote a copy **to the same volume** using a plain file copy of a live
  database. Now: `VACUUM INTO` snapshot → integrity check → gzip →
  OneDrive via the Graph creds already held for mail. **Restore drill
  passed 2026-09-03**: pulled back, decompressed, row counts matched
  live on every table.

**Directives issued this wave** (all in `docs/claude/`, all posted to
the mailbox): `hubspot-decommission-directive.md` (extraction as a hard
gate, field-parity cutover), `ux-directive-work-surfaces.md` (Lead
Center UX to CA + CD — mobile is the PRIMARY surface because `sms:`
only works on Kerry's iPhone), `railway-api-setup.md`,
`database-backup-gap.md`.

**Live credentials now set:** `META_ACCESS_TOKEN` (non-expiring System
User, read-only), HubSpot service key widened to 9 scopes, and
`Files.ReadWrite.All` consented on the Azure app.

## Plan of record: native app + website

See member-portal.md → "Platform roadmap". One backend, two faces
(admin website + member app): mobile-first portal (live) → PWA with
offline score entry → Capacitor native wrap (App Store/Play Store,
push) → native extras (GPS/camera). API-first /api/me pattern from
day one; Supabase (managed Postgres + auth + realtime + RLS) is the
scoped Platform stack when live scoring demands concurrent writes.

## Gateways discipline

Per admin decision: no TGF Platform coding until gateways pass. The
Tracker is the sandbox/bridge; everything here is built portable (see
CLAUDE.md Guiding Principles — rules-based, customer_id identity,
past-events-frozen, admin/manager/customer layers).

## How to talk to tracker-claude

- **read_platform_dialogue / post_platform_dialogue** (this MCP
  server) — the mailbox. Post questions, decisions, and directives;
  tracker-claude reads at session start and posts digests at session
  end. Sign author='platform-claude'.
  **⚠ Two servers carry these same tool names** (incident, mailbox
  #257–#259): the claude.ai connector is bound to PRODUCTION; the
  repo-root `.mcp.json` stdio server runs against a LOCAL, EMPTY
  SQLite inside a Claude Code container. Discriminate with
  `get_statistics` (production ≈ 1,600+ items; local = 0) before
  trusting any read — and never run money operations locally.
- **get_tracker_docs** — list/read all living docs (CLAUDE.md +
  docs/claude/*) for architecture depth on any subsystem.
- **Live data** — the other 56 tools on this server query the
  production database directly (customers, scoring, standings,
  financials, GG probe).
