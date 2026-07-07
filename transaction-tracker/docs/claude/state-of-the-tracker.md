# State of the Tracker — July 2026 (Platform-facing brief)

Audience: the claude.ai "The Golf Fellowship" Project, where TGF Platform
planning has lived for the past six months. Purpose: catch that planning
context up on what the Tracker actually is today — it has grown far
beyond transaction tracking. Maintained by tracker-claude; check the
platform_dialogue mailbox (read_platform_dialogue on this MCP server)
for session-by-session updates after this brief.

## What the Tracker is now

Flask + SQLite on Railway (tgf-tracker.up.railway.app), version 2.34.x,
~200+ routes, 61 MCP tools. Started as a GoDaddy order-email parser;
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
  a Points tab on every customer profile.
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

## In flight (July 2026)

- **Live championship standings** — City and TGF Championships are
  upcoming; GG does live scoring but does NOT compute points standings
  live. Design: poll GG's live POINTS game during play → each player's
  running Stableford IS their provisional race points → merge into
  persisted season standings → live projected Best-10+CC standings with
  movement, shareable to members' phones. Points model solved (above);
  the one open risk is whether public portal pages update mid-round —
  live-fire test planned at the next regular event.
- **Live-updates ladder** — step 1 shipped (skip page rebuilds when
  fetched data is unchanged); step 2 targeted DOM updates; step 3
  SSE/WebSocket push. Serves both website live standings and the
  future app's live feed.
- **Own live scoring** — assessed viable: scoring math, course data,
  groups, and magic-link auth all exist; remaining build is the score
  entry UI, offline queue, and a live write path. Plan: shadow-mode
  pilots at regular events alongside GG; championships stay on GG.

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
- **get_tracker_docs** — list/read all living docs (CLAUDE.md +
  docs/claude/*) for architecture depth on any subsystem.
- **Live data** — the other 56 tools on this server query the
  production database directly (customers, scoring, standings,
  financials, GG probe).
