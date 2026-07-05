# Member Portal & Email Summaries — M1 LIVE (v2.28.0), M2/M3 designed
#   + Platform roadmap: native app + website (plan of record, 2026-07-05)

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
  scoring means many concurrent writers; then managed Postgres on
  Railway (already the Platform assumption).

Sequencing against the real calendar: championships live standings
(website, GG-tap) → member portal M2/M3 → PWA + shadow-mode live
scoring pilots at regular events → Capacitor + TestFlight → stores.

Related: live points standings during events (GG live scoring tapped
and converted to provisional race points — points = net Stableford
floored at 0, verified 2026-07-05 against member details) and the
own-live-scoring shadow pilot are documented decisions from the same
planning thread; see docs/claude/scoring.md for the points-model
finding.
