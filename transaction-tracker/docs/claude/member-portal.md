# Member Portal & Email Summaries — Design (proposed, not yet built)

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
