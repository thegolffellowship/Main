# The Dashboard — the landing page (v2.471.0, Kerry-ratified 2026-09-21)

Kerry: *"maybe I should be landing on a DASHBOARD page that summarizes
anything current that I can go to with a click. Could be this week's
events that I could click to work...new players that need to be denoted
like Ty Bubela for potential lead development...perhaps checklists,
etc."* Then, ratifying: *"Dashboard replaces COO as landing, absorb the
action items — I don't use the current what needs me today stuff at all
right now, so let's ditch those for the new comprehensive dashboard."*

**ADMIN ONLY** (Kerry, same day). `/` redirects to `/dashboard` for an
admin and to `/events` for everyone else — the landing has to know who is
asking, or a manager is bounced straight back off their own home page.
The page route redirects a non-admin rather than answering `require_role`'s
JSON 403, which is a dead end for anyone following a stale link or a
bookmarked PWA start URL. EVENTS held the landing slot from 2026-07-08.

## The two rules

**1. It is a ROUTER, never a workspace.** Every card is a count and a
link to the surface that owns the work. Nothing is worked here. The
moment a card can be acted on it competes with the page it points at and
the two drift. The per-card peek list is five rows and a "+N more" —
enough to recognise the work, never enough to do it.

**2. A card with nothing in it does not render.** `build()` returns only
cards with a non-zero count, and the page draws exactly what it is
given. A page that always shows every card is wallpaper by the second
week; one that shows three things today and six tomorrow keeps being
read. No cards at all renders *"Nothing needs you right now"* — a
result, not an empty state.

## Why the COO page was retired as the landing and its TABLE was not

`action_items` is written from nine code paths (discrepancy sweeps,
parse warnings, the GG history ingest). It is the mechanism by which the
system reports problems it found. Kerry does not read the page it lives
on. The fix is to surface the COUNT where he will see it and link to the
page that works them — not to stop detecting. `/coo` still exists and
still works; it is no longer the front door.

## The cards (v1)

| key | reads | links to |
|---|---|---|
| `events_week` | events in the next 7 days + registration counts | `/events` |
| `closeout` | events played in the last 21 days with unpaid `tgf_payouts` | `/tgf` |
| `leads_due` | leads with `follow_up_at` today or earlier | `/admin/leads` |
| `leads_new` | leads still `new` | `/admin/leads` |
| `attribute` | 1st TIMER customers (last 60d) with no `referred_by_customer_id` | `/admin/leads` |
| `renewals` | latest membership per customer: lapsed, or expiring in 30d | `/customers` |
| `expenses` | `expense_transactions.review_status = 'pending'` | `/accounting` |
| `action_items` | open `action_items`, **urgency high, last 14 days** — absorbed from COO | `/coo` |
| `ca_queue` | open `ca_queue` rows | `/admin/ca-queue` |

**Why `action_items` is scoped and the others are not.** That table is
the AI email triage — mail that wants a reply. It holds ~3,100 open rows
going back to the feature's first day, because nobody has ever worked it.
An unscoped count renders as `3151`, which is an archive, not a to-do
list, and an archive on a landing page is precisely what trained Kerry to
stop opening the COO dashboard. High urgency inside 14 days is the cut
that makes it today's list. **Any future card over a long-lived table
needs the same question asked of it: is this a queue or a pile?**

`attribute` is the Ty Bubela card. It counts today and will gain its
one-tap confirmation once the referral schema is ratified — see
`docs/claude/referral-attribution.md`. The count is true either way.

## Shape

- `email_parser/dashboard.py` — `FEEDS` is a tuple of `(conn, today) ->
  card | None`. **Each feed is independently wrapped**: one that raises
  is named in `skipped` and costs its own card, never the page, and the
  page SAYS which feed failed rather than quietly dropping a row.
- `GET /api/dashboard` (manager+), `GET /dashboard`, bridge
  `scoring-dashboard` (read-only).
- Guards: `test_dashboard_feeds.py` (the build contract, the two rules,
  the date helpers), `test_dashboard.js` (the render, the peek cap, the
  failed-feed notice, HTML escaping). The page exposes `window.__dbRender`
  so the headless guard calls the REAL renderer instead of restating it.

## The perma-load, and the class it belonged to

The first cut set `window.onAuthReady = () => load()` and never called
`initAuth()`. Nothing fired the callback, so `load()` never ran and the
page sat on *"Loading…"* forever with an ungated nav (Kerry: *"Stuck on
perma load."*). CLAUDE.md already said `initAuth()` must be called on
every page; the page simply did not.

Per the guiding principle, the sweep for the CLASS found one more:
`participation.html` loaded auth.js and never called `initAuth()` either.
Its symptom was quiet rather than loud — the data loaded, but the nav was
never role-gated, so an admin saw no admin links on that page. Fixed the
same day.

The durable fix is `test_auth_init.js`: **every template that loads
auth.js must call `initAuth()`**, directly or through a script it loads.
It also pins the dashboard's own shape — `load()` is called at top level
and is never reachable only through the auth callback, because the fetch
carries the session cookie by itself and the data should never wait on
the nav.

## Adding a card

Write a feed, add it to `FEEDS`, give it a row in the table above. It
must return `None` (or a zero count) when there is nothing to show, and
it must link to a surface that already owns the work. If there is no
such surface, build that first — a card with nowhere to go is a card
that teaches Kerry to ignore the page.
