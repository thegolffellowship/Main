# Events Page — Player Status Architecture

## Transaction statuses
- `active` — normal registration, shown in main table
- `rsvp_only` — RSVP without payment, shown in main table (yellow background)
- `gg_rsvp` — Golf Genius RSVP, shown in main table (yellow background)
- `credited` — payment credited back, shown in **Inactive** section below table
- `refunded` — payment refunded, shown in **Inactive** section below table. Creates `acct_transactions` expense entry.
- `transferred` — transferred to another event, shown in **Inactive** section below table. Creates contra-revenue on source event + revenue on target event in `acct_transactions`, plus allocation at target.
- `wd` — withdrawn, shown in **Inactive** section below table

## Event detail view sections (top to bottom)
1. **Toggle bar** — PLAYERS | PAIRINGS | GAMES + 9|18 holes filter + NET | GROSS | NONE
2. **Registrations table** — only active/rsvp players (compact rows)
3. **Inactive section** — credited/refunded/transferred/WD players in a gray box with Reverse buttons
4. **Not Playing section** — GG RSVP players marked as not playing (red box)
5. **Message History** — collapsible section

## Columns in registrations table
Order: RSVP circle → Customer → HCP → Holes → Games → Tee → Status → Order → Price → Actions

## Status normalization
The `user_status` field is cleaned at display time via `_cleanStatus()`:
- Strips parenthetical notes like "($25 Off + FREE Drink)"
- Normalizes to: "1st TIMER", "MEMBER", "MEMBER+", "GUEST", or "MANAGER"

## Holes field
- Parsed from emails: "9 or 18 HOLES?" field → stored as `holes` TEXT column
- Shown as column in both Transactions and Events tables
- Mobile collapsed view: amber badge showing "9h" or "18h" (first of three badges: Holes, Games, Tees)
- 9|18 toggle filter in Events: filters registrants by hole count
- Can be backfilled via `/api/audit/re-extract-fields`

## Game stats computation (`computeGameStats`)
- Excludes credited/refunded/transferred players from counts
- WD players: complex logic based on which game components were credited
- RSVP-only players: counted in PLAYERS total but as NONE (no games)

## GUEST registration handling
- When a member buys two items (one for themselves, one for a guest), the parser's
  `_promote_guest_customers()` auto-swaps the GUEST item's customer to the actual
  guest name (from `guest_name` field) and adds a "Purchased by <buyer>" note
- **"Guest?" tag** — amber clickable tag on GUEST items in multi-item orders where
  the guest name is unknown. Only appears when: same buyer has a peer item in the
  same order AND no `guest_name` or `partner_request` is set
- **"Paid by" badge** — blue badge on GUEST items where guest-swap has already occurred
- **Assign guest endpoint**: `POST /api/items/:id/assign-guest` (manager+)
- Detection is conservative: standalone GUEST registrations (guest signed up themselves)
  are NOT flagged

## Add Payment
- Creates a child payment row linked to parent registration via `parent_item_id`
- Child rows excluded from player counts, shown as indented "+PAY" sub-rows
- Item types: NET Games, GROSS Games, BOTH Games, Event Upgrade (9→18 holes), Other
- **Event Upgrade** updates the parent item's `holes` to "18" but does NOT affect games
- Child payment `side_games` is empty for Event Upgrade (prevents false game merging)
- Player dropdown filters out child payment rows to avoid duplicates
- Supports event aliases (course changes) for parent lookup
- **Unified financial model:** creates `acct_allocations` row + `acct_transactions` entry
  for each add-on payment (allocation uses synthetic `order_id = MANUAL-PAY-{item_id}`)

## Clickable game switching
- GAMES column is clickable for active registrations with NET or GROSS games
- Click toggles between NET ↔ GROSS (no-cost swap only)
- BOTH and NONE are NOT clickable — those involve money changes
- Uses `PATCH /api/items/:id` (admin only) to update `side_games`

## Action Items banner
- Red notification banner on Transactions and Events pages for admin/manager
- Aggregates: parse warnings + GUEST items needing guest name assignment
- `GET /api/action-items` endpoint returns combined list
- Auto-expands on page load; items can be dismissed or acted on inline
- Parse warning dismiss/resolve accessible to managers (was admin-only)

## Per-order re-extract
- Audit page email cards have "Re-extract This Order" button
- Calls `POST /api/audit/reextract-order` with `{order_id: "R..."}`
- Re-fetches original email from Graph API, re-runs AI extraction
- Backfills missing fields AND applies guest-swap if parser detects GUEST items
- Also available via browser console for immediate use

## Event deletion / merge persistence
- **Merge** creates an alias (source → target) so sync skips the old name
- **Delete** now preserves the deleted name as an alias (→ `_DELETED_`) when
  items still reference it, preventing `sync_events_from_items()` from recreating
- `seed_events()` also checks aliases before inserting

# Event Cancellation / Postponement

Events can be cancelled or postponed from the event detail view (admin only).
New columns on `events` table: `status` TEXT (`active`/`cancelled`/`postponed`),
`status_reason` TEXT, `rescheduled_to_event_id` INTEGER, `status_changed_at` TEXT.

**Cancel Event modal — 4 steps:**
1. Choose `Cancelled` or `Postponed` + enter reason text (required).
2. Choose refund/credit mode: **Bulk** (Credit All / Refund All in one click) or **One-by-One**.
3. (One-by-One) Staging list with per-row Credit / Refund / Skip buttons → Apply All.
4. Completion summary + optional "Send Cancellation Email" prompt.

**Key behaviors:**
- Refund method auto-detected from original payment (`godaddy` → GoDaddy, `venmo` → Venmo, etc.)
- Add-on payments cascade automatically via existing `credit_item` / `refund_item` logic
- Comp and RSVP-only players are silently removed (no credit/refund needed)
- **Restore Event** button appears on cancelled/postponed events until the first player
  action is taken (`can_restore_event(conn, event_name)` checks for any credited/refunded items)
- Cancelled/postponed badges shown on the event list rows
- Status banner shown at top of event detail view

**API endpoints (all admin):**
- `POST /api/events/<name>/cancel` — `{status, reason}` → sets event status
- `POST /api/events/<name>/restore` — clears status back to active
- `GET  /api/events/<name>/cancellation-players` — list of active players with payment info
- `POST /api/events/<name>/cancel-bulk` — `{action: 'credit'|'refund', method?}` → bulk apply
- `POST /api/events/<name>/cancel-apply` — `{actions: [{item_id, action, method?}]}` → one-by-one apply

**Key DB functions:**
- `set_event_status(conn, event_name, status, reason)` — writes status + timestamp
- `can_restore_event(conn, event_name)` — returns True if no credited/refunded items yet
- `get_cancellation_players(conn, event_name)` — returns active players with payment method

# RSVP Credit Application (from Events page)

When an event is cancelled, players who had credits from that event and are now RSVPing
to a future event can have their credit applied directly from the RSVP row.

**How it works:**
- After RSVP inbox check, `_send_rsvp_credit_alerts()` auto-sends email alerts to players
  with outstanding credits who have RSVPed to an upcoming event.
- Green **Credit** badge appears on RSVP-only rows in the event detail view when the player
  has an outstanding credit (checked via `get_rsvp_credit_info`).
- **Apply Credit** button opens a modal showing: previous selections, event price table for
  their player type, amount owed (if price > credit) or excess credit (if credit > price),
  and disposition choice for excess (keep vs. Venmo note).
- On confirm, calls `apply_credit_to_rsvp(conn, rsvp_id, item_id, disposition)` which:
  - Creates the transferred registration item linking credit source → new event
  - Marks the credit item as used
  - Calculates and records any balance-due or excess
- `rsvps` table new column: `credit_notified_at` TEXT — tracks when the alert email was sent.

**Key DB functions:**
- `get_player_credits(conn, customer_id)` — player's outstanding credit items
- `get_rsvp_credit_info(conn, rsvp_id)` — credit info for a single RSVP row
- `get_event_rsvp_credit_map(conn, event_name)` — map of rsvp_id → credit info for all RSVPs in an event
- `apply_credit_to_rsvp(conn, rsvp_id, item_id, disposition)` — executes the credit transfer
- `mark_rsvp_credit_notified(conn, rsvp_id)` — records credit_notified_at timestamp

**GG RSVP synthetic row support:**
- `get_event_rsvp_credit_map` queries both `items` table rows AND unmatched `rsvps`
  table rows (GG RSVPs without a linked items row). Resolves canonical customer name
  via email lookup so name-keyed map matches frontend JS.
- `create_rsvp_only_item()` — promotes a GG RSVP to a real `items` row (idempotent
  via `email_uid`) before credit application runs.
- `GET  /api/rsvps/gg/<id>/credit-info` — credit-info for a synthetic GG RSVP row
- `POST /api/rsvps/gg/<id>/apply-credit` — apply credit to a synthetic GG RSVP row

**API endpoints:**
- `GET  /api/rsvps/<id>/credit-info` — credit info for a specific RSVP
- `GET  /api/events/<name>/rsvp-credits` — all RSVP credit info for an event
- `POST /api/rsvps/<id>/apply-credit` — `{item_id, disposition}` → apply credit

**Undo Credit Application:**
- `reverse_credit_application(conn, item_id)` — restores transferred source credits
  to `credited`, removes any excess credit item, reverses accounting entries, reverts
  target item to `rsvp_only` (or deletes if it was a promoted GG RSVP item).
- `POST /api/items/<id>/reverse-credit-application` (admin only)

## Apply Credit to Event from Customers Page

Credited items in customer detail views have an **Apply** button (alongside Reverse).
Clicking opens a modal to select an upcoming event, shows a price preview (credit vs. event
price, balance-due or excess handling), and applies the credit.

**API endpoints:**
- `GET  /api/items/<id>/apply-credit-info?event_name=<name>` — preview amount owed / excess
- `POST /api/items/<id>/apply-to-event` — `{event_name, disposition}` → apply credit

Uses idempotent uid `manual-credit-{credit_item_id}` to prevent double-apply.
All three rendering paths on the Customers page (inline expand, detail panel, mobile card) updated.

# Event Pricing Architecture

## Edit/Add Event Modal — Pricing Tab

The Pricing tab has a **compact layout** with collapsible calculators and live-updating pricing cards.

**For 9/18 Combo events:**
- Two side-by-side columns: "9-Hole Calculator" (green) and "18-Hole Calculator" (blue)
- Each column has: collapsible Course Cost Calculator, Markup ($), Inc. Games ($)
- "Event Cost" total at bottom of each card = `ceil(courseCost) + markup + incGames`
- Shared Transaction Fee (%) input below
- Side-by-side pricing summary with colored cards below

**Course Cost Calculator** (collapsible):
- Collapsed (default): header + green fees row only + rounded total in header
- Expanded: all 5 items (Green Fees, Cart Fees, Range Balls, Printing, Other)
- Header shows `Math.ceil(total)` (rounded-up course cost)
- Auto-expands if non-green-fees items have saved data

## Pricing Calculation Flow

```
roundedCC     = Math.ceil(courseCost)
eventCharge   = roundedCC + markup + incGames + gameAddon
actualCharge  = Math.ceil(eventCharge)       // whole dollar rounding
txFee         = round(actualCharge × txPct) / 100
playerTotal   = actualCharge + txFee
```

Key function: `calcPricingLine(cc, mu, sg, tf)` in `events.html`

## Player Type Markup Rules

The Markup ($) input = **Member** markup. Guest and 1st Timer are auto-derived:
- **Guest** = Member + $10 (9 Holes and 9/18 Combo) or + $15 (18 Holes standalone)
- **1st Timer** = Guest − $25 (can go negative as discount)
- Determined by `getPlayerMarkups(memberMarkup, format)` function
- For combo events: Guests/1st Timers can ONLY play 9-hole (18-hole shows N/A)

## Game Add-On Tiers

- **Event Only**: base price (includes Inc. Games fee)
- **With One Game (+$16)**: adds `PER_GAME_ADDON` ($16 constant)
- **With Both Games (+$32)**: adds `PER_GAME_ADDON × 2`
- Both Games = N/A for Guest and 1st Timer

## Pricing Summary Cards

Cards use `_priceCard()` function with `PLAYER_CARD_STYLES` colors:
- Member: green (#f0fdf4 bg, #16a34a border)
- Guest: blue (#eff6ff bg, #2563eb border)
- 1st Timer: gold (#fefce8 bg, #a16207 border)
- N/A: gray (#f3f4f6 bg, #d1d5db border)

Cards display the **event charge** (whole dollars, before tx fee).

## Field Name Mapping

| UI Label | DB Field | Notes |
|----------|----------|-------|
| Markup ($) | `tgf_markup` / `tgf_markup_9` / `tgf_markup_18` | Member rate |
| Inc. Games ($) | `side_game_fee` / `side_game_fee_9` / `side_game_fee_18` | Included games admin fee |
| Transaction Fee (%) | `transaction_fee_pct` | Default 3.5% |
| Course Cost | `course_cost` / `course_cost_9` / `course_cost_18` | From calculator |
| Course Cost Breakdown | `course_cost_breakdown` / `_9` / `_18` | JSON of 5 line items |

# Side Games Matrix

## Persistence
- Matrix data is stored in `app_settings` table (key: `matrix_9h` / `matrix_18h`)
- Also cached in `static/js/games-matrix.js` as fallback
- `PUT /api/matrix` saves to DB primary, file as cache
- Templates receive matrix data server-side via Jinja: `var db9 = {{ matrix9 | tojson }};`

## Skins labels
- "Skins ½ Net" when gross player count < 8
- "Skins Gross" when gross player count >= 8

## Skins Type row
- Computed row in matrix showing which skins format applies per player count

# TGF Payouts Page

## Architecture
- **Page** at `/tgf` — two top-level tabs: EVENTS and GOLFERS
- **Data** from `tgf_events` and `tgf_payouts` tables; golfer identity is the `customers` table (tgf_golfers was eliminated)
- **API:** `GET /api/tgf` returns `{customers, events, winnings}` where customers is the list of payout recipients

## Events Tab
- Sidebar lists events by date with total purse amounts
- Main area shows payouts table grouped by golfer (sorted by total descending)
- Expandable rows show category breakdowns (team_net, individual_net, skins, etc.)
- Venmo pay links generated for golfers with venmo_username set

## Screenshot Paste / Import
- **Drop zone** appears below the payouts table when an event is selected
- **Three input methods:** Ctrl+V paste, drag & drop, click to upload
- **AI parsing:** `POST /api/tgf/parse-screenshot` sends image to Claude Vision
  (`claude-sonnet-4-20250514`), returns JSON with golfer names, categories, amounts
- **Preview table** shows parsed payouts with Save/Cancel buttons
- **Save** calls `POST /api/tgf` with `action: "import_payouts"` — adds payouts to
  the currently selected event (does NOT create a new event)
- **Backend:** `import_tgf_payouts(event_id, payouts)` inserts payouts, updates event
  aggregates (total_purse, winners_count, payouts_count)
- **Paste only fires** when events tab is active AND an event is selected

## Golfer name resolution
- `_resolve_customer_for_payout(conn, name)` — resolves payout recipient to a `customer_id` via the standard `_lookup_customer_id` cascade; creates a new customer with `acquisition_source='tgf_payout'` if no match found
- Payouts linked to identity via `tgf_payouts.customer_id` (FK to `customers.customer_id`)

## Category types
`team_net`, `individual_net`, `individual_gross`, `skins`, `closest_to_pin`,
`hole_in_one`, `mvp`, `other`

## tgf_events → events bridge

`tgf_events.events_id INTEGER REFERENCES events(id)` bridges the tournament prize universe
to the main event registry. Backfilled at startup by `_backfill_events_id_on_tgf_events()`
via exact name match → partial LIKE → year-narrowed LIKE.

This allows prize payouts (`tgf_payouts`) to be joined to registration and financial data
in `events`/`acct_transactions` for combined P&L views.

## Key TGF endpoints
- `GET /api/tgf` — all data (events + payouts + golfer winnings)
- `POST /api/tgf` — actions: `add_event`, `import_payouts`, `add_golfer`,
  `import_golfers`, `update_event`, `delete_event`
- `POST /api/tgf/parse-screenshot` — AI screenshot parsing (manager+ role)
