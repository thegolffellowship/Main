# State of the Tracker — mid-July 2026 (Platform-facing brief)

Audience: the claude.ai "The Golf Fellowship" Project, where TGF Platform
planning has lived for the past six months. Purpose: catch that planning
context up on what the Tracker actually is today — it has grown far
beyond transaction tracking. Maintained by tracker-claude; check the
platform_dialogue mailbox (read_platform_dialogue on this MCP server)
for session-by-session updates after this brief.

## What the Tracker is now

Flask + SQLite on Railway (tgf-tracker.up.railway.app), version 2.104.x,
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
