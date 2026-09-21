# The Dashboard — the landing page (v2.471.0, Kerry-ratified 2026-09-21)

Kerry: *"maybe I should be landing on a DASHBOARD page that summarizes
anything current that I can go to with a click. Could be this week's
events that I could click to work...new players that need to be denoted
like Ty Bubela for potential lead development...perhaps checklists,
etc."* Then, ratifying: *"Dashboard replaces COO as landing, absorb the
action items — I don't use the current what needs me today stuff at all
right now, so let's ditch those for the new comprehensive dashboard."*

`/` now redirects to `/dashboard`. EVENTS held that slot from
2026-07-08.

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
| `action_items` | open `action_items` — **absorbed from COO** | `/coo` |
| `ca_queue` | open `ca_queue` rows | `/admin/ca-queue` |

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

## Adding a card

Write a feed, add it to `FEEDS`, give it a row in the table above. It
must return `None` (or a zero count) when there is nothing to show, and
it must link to a surface that already owns the work. If there is no
such surface, build that first — a card with nowhere to go is a card
that teaches Kerry to ignore the page.
