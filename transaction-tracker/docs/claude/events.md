# Events Page — Player Status Architecture

## Transaction statuses
- `active` — normal registration, shown in main table
- `rsvp_only` — RSVP without payment, shown in main table (yellow background)
- `gg_rsvp` — Golf Genius RSVP, shown in main table (yellow background)
- `credited` — payment credited back, shown in **Inactive** section below table
- `refunded` — payment refunded, shown in **Inactive** section below table. Creates `acct_transactions` expense entry.
- `transferred` — transferred to another event, shown in **Inactive** section below table. Creates contra-revenue on source event + revenue on target event in `acct_transactions`, plus allocation at target.
- `wd` — withdrawn, shown in **Inactive** section below table

## Events list filters (v2.46.0)
CHAPTER scope pills (ALL | AUSTIN | SAN ANTONIO; ALL is the landing)
over the app's standard segmented control for time: Upcoming | Past |
All Events (standard case, counts inline). Chapter is the outer
context — counts, time buckets, and search all scope to it — and
EVERY chapter click re-opens on Upcoming. Shared events carry
events.chapter = 'TGF' (Edit/Add Event modal: "TGF (All Chapters)")
and appear under every chapter tab (shared 18s, TGF Championship).
Clear Filters and ?item= deep-links reset/widen scope as needed.
v2.47.0: time tabs read UPCOMING | Past | All Events; chapter-manager
sessions land pre-scoped to their chapter; the All Events view draws a
TGF-orange (#E87C3E) breakline labeled PAST EVENTS where upcoming meets
past (desktop table + mobile cards, date-sorted views only). Nav order
site-wide: Events | Contests | Handicaps | Transactions | Customers
(+ Payouts and an orange Admin tab pinned last, admin only); RSVP Log
is a sub-tab of Transactions and Participation a sub-tab of Customers
(segmented-control links under the nav). The per-event PAYOUTS view
toggle now renders on MOBILE cards too (admin). v2.49.4 (Kerry): the
per-event PAYOUTS panel's Paste Screenshot drop zone + AI-parse
handlers were REMOVED as obsolete (auto GG results sync + Record
Payouts replaced screenshot imports; the /tgf page importer still
exists), and the REGISTERED + GAMES columns hide below 768px
(`.payout-hide-mobile`). v2.49.5: the expanded breakdown's description
column also hides on mobile (game badge left, amount right), the
status badge renders after the Venmo Pay link, and the payout table is
wrapped in an `overflow-x:auto` container for horizontal swiping.

## Payout visibility is ADMIN-only (v2.45.0, Kerry)
Managers must not make prize payouts or see payout surfaces: the
Payouts nav tab (`/tgf`), the per-event PAYOUTS view toggle, the Games
tab Record Payouts button, and the Customers detail Winnings tab are
all hidden for non-admins; /tgf redirects, and /api/tgf (GET/POST),
mark-paid, parse-screenshot, record-game-payouts, and
game-payouts-preview are @require_role("admin"). Managers keep
credit/transfer/WD (internal ledger moves); anything recording a REAL
outbound payment (refund, partial-refund, payout-credit, payout
recording, mark-paid) is admin-only.

## Events list ordering (v2.46.0)
Default date sort per bucket: Upcoming soonest-first; Past AND All
Events most-recent-first (Kerry). An explicit column-header sort
survives filter switches; deep-links that auto-flip the filter get the
same defaults.

## Event detail view sections (top to bottom)
1. **Toggle bar** — ROSTER | PAIRINGS | GAMES | PAYOUTS (admin) | FINANCIAL + 9|18 holes
   filter + NET | GROSS | NONE. (v2.49.0, Kerry: PLAYERS renamed ROSTER; FINANCIAL moved
   to the end after PAYOUTS.)
2. **Registrations table** — only active/rsvp players (compact rows)
**CREDIT MATH (Kerry-ratified 2026-07-20):** a player's credit is the
ENTRY PRICE only — transaction fees are NEVER refunded or credited ("We
don't refund fees"; the fee covered card processing that already
happened). Partial carve-out children (Partial Credit / Partial Refund /
Refund(<method>) rows from event downgrades or dropped side games)
subtract from the parent's credit so the same dollars never count twice
— parent + carve-out lines always sum to the money actually held.
Implemented in `get_player_credits` (v2.129.20-21); flows to the Apply
Credit modal, roster credit badges, credit-alert emails, and balance-due
math.

3. **Inactive section** — credited/refunded/transferred/WD players in a gray box with Reverse buttons. Names link to `/customers?name=...` (clickable). WD rows with a `credit_amount` and standalone `credited` rows expose an additional **Refund** button (see `Payout Credit / Refund` below).
4. **Not Playing section** — GG RSVP players marked as not playing (red box). Names render as full "Last, First" (resolved via `rsvps.customer_id` FK → `customers` master record), link to `/customers?name=...`, and surnames render UPPERCASE for elevated-role players. No email rendered on the row.
   - **Suppression rule (v2.13.0):** if a player who RSVPd "not playing" later registers and has an active transaction for the event, their GG RSVP is filtered out of this section automatically. Daniel Stich-style: he RSVPd not-playing then paid; he no longer shows up under NOT PLAYING.
   - **Dedup (v2.13.0):** `notPlayingRsvps` is deduplicated by email (primary key) then resolved/first name, so a doubled GG RSVP import (HOFFMAN, Rocky × 2 etc.) only renders once.
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
- **Authoritative source is the EVENT, not the order (v2.84.2).** The AI
  parser sometimes mis-reads the hole count — most often it grabs the
  SEQUENCE number out of the event code ("a9.18 Forest Creek" = the 18th
  Austin 9-hole event, NOT 18 holes) and stores `holes='18'` on a 9-hole
  event. `heal_item_holes_from_event()` (boot heal + bridge
  `scoring-heal-holes`) forces `items.holes` to `_event_holes_type(name,
  format)` for every NON-combo event; combo events keep their real
  per-player 9/18 choice. **Display-only** — side-game pot sizing derives
  its matrix from the event via `_event_holes_type`/`extractHolesType`,
  never from `items.holes`, so a bad value never affected money, only the
  badge, the 9|18 filter, and the hole-aware HCP column.

## Event formats — `events.format`
The Edit/Add Event modal exposes four radios: `9 Holes`, `18 Holes`, `9/18 Combo`, and `27 Holes`.
- **27 Holes** is treated as a single-day event using the same start-time / tee-sheet /
  5-hour-duration rules as 18 Holes. Pairings, default holes, and the side-games matrix all
  map 27 Holes to the 18-hole code path (single block, not combo).
- **Pricing differences for 27 Holes:**
  - Guest = Member + $25 (vs +$10 for 9/Combo, +$15 for 18 standalone)
  - No 1st Timer tier — pricing grid hides the 1st Timer column
  - New per-event **Per Game Add ($)** input (defaults to $27), persisted on
    `events.per_game_addon REAL` and used by the server-side
    `_calc_event_pricing_breakdown` for NET / GROSS / BOTH game add-ons.
- `per_game_addon` is plumbed through `create_event()`, `_validate_update_fields`
  allow-list, and the `POST /api/events` route.

## HCP column — hole-aware rendering
Registration rows (desktop + mobile) apply a hole-aware HCP rule:
- An event with any 9-hole players (9-only or 9/18 mixed) renders only the 9-hole net handicap with the `N` subscript.
- An event with only 18-hole players renders only the 18-hole index.

## Per-row Actions dropdown (desktop)
The Actions cell on each registration row collapses every per-row button into a single
`⚙ ▾` menu (`.ev-actions-toggle` / `.ev-actions-menu`). Each previously-inline button
(Apply Credit, Send Venmo / Remind, Undo, Credit, WD, Reverse, Refund, Delete) becomes
an `.ev-menu-item`; Delete uses `.ev-menu-item-danger`. Class names and `data-*` attrs
are preserved so existing event delegation keeps working unchanged. Mobile registration
cards remain inline buttons.

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

## Pairings printables — Starter Sheet + Cart Signs (B5, v2.116.0)
Two print-optimized pages rendered from the SAVED pairings
(`get_event_pairings`), assembled by `get_event_print_pack(event_id)` in
`database.py` (event row + ordered groups + cart split — seats 1&2 = Cart A,
3&4 = Cart B per Kerry's ruling). Manager routes: `GET /events/<id>/starter-sheet`
→ `templates/starter_sheet.html` (tee time / group / player / tee / Idx / cart,
one table), and `GET /events/<id>/cart-signs` → `templates/cart_signs.html`
(one large card per cart, page-break per card, foldable placard). Both are
standalone templates (no `_shell_nav.html`) with their own `@media print` CSS +
`@page`. Buttons appear in the pairings toolbar **only when pairings are saved**
(they read saved data). The handicap column is labeled **Idx** — the 9-hole
index the pairings carry, NOT the D1 playing handicap (that upgrade needs the
per-player selected-tee slope/rating/par and is a fast follow-up).

## Add Player
- Modes: **comp** (manager comp, `$0.00`), **rsvp** (RSVP-only placeholder),
  **paid_separately** (Venmo/Zelle/Cash). Endpoint: `POST /api/events/add-player` (manager+).
- The server does **not** dedupe — it always inserts a new item. Duplicate prevention is
  **client-side only**, in `handleAddPlayerSubmit` (`events.html`).
- **Duplicate guard mirrors the active roster, not all history.** It blocks a (re-)add only
  when a matching-name registrant is *currently active* on the roster — i.e. it ignores
  inactive statuses (`credited`, `refunded`, `transferred`, `wd`) and child-payment rows
  (`parent_item_id`). A player who deleted themselves, was refunded/withdrawn/credited, or
  was transferred out is **not** treated as "already registered," so the manager can add
  them back. This matches the `activePlayers` filter that renders the player table — if you
  can't see them in the roster, the guard won't claim they're registered.

## Add Payment
- Creates a child payment row linked to parent registration via `parent_item_id`
- Child rows excluded from player counts, shown as indented "+PAY" sub-rows
- Item types: NET Games, GROSS Games, BOTH Games, Event Upgrade (9→18 holes), Other
- **Event Upgrade** updates the parent item's `holes` to "18" but does NOT affect games
- **Partial Refund "Credit" method (v2.93.0, Kerry):** the Partial Refund
  method select includes `Credit (hold for a future event)` — creates a
  child items row with `transaction_status='credited'` and a POSITIVE
  price (get_player_credits surfaces any credited row, parent or child,
  so it feeds Apply Credit + balance emails), parent still updates
  (games/holes), and NO acct entry is written (internal ledger move).
  Kerry flagged the modal's option sprawl for a consolidation design
  pass (task #19) — semantics frozen until then.
- **Event Downgrade (18→9) lives in the CREDIT modal's Partial Refund tab**,
  not here (v2.92.0, Kerry): players registered for 18 in a 9/18 Combo get an
  "Event Downgrade 18 → 9 holes" component (`calcDowngradeAmount` — the
  format price difference via the same per-event pricing chains as
  `calculateWdComponents`); confirming refunds the difference AND sets the
  parent item's `holes` to 9 (`new_holes` on POST
  `/api/items/<id>/partial-refund`; prior value preserved in
  parent_snapshot)
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

## Player ACTIONS column — role boundaries

Player-row action buttons hit role-gated endpoints. As of the current build,
the following are available to **manager** (and admin):

| Action button | Endpoint | Role |
|---|---|---|
| Credit | `POST /api/items/<id>/credit` | manager |
| WD | `POST /api/items/<id>/wd` | manager |
| Transfer | `POST /api/items/<id>/transfer` | manager |
| Reverse | `POST /api/items/<id>/reverse-credit` | manager |
| Undo (revert credit application) | `POST /api/items/<id>/reverse-credit-application` | manager |
| Apply Credit (item) | `POST /api/items/<id>/apply-to-event` | manager |
| Apply Credit (RSVP) | `POST /api/rsvps/<id>/apply-credit` | manager |
| Apply Credit (GG RSVP) | `POST /api/rsvps/gg/<id>/apply-credit` | manager |
| Delete manual player | `DELETE /api/events/delete-manual-player/<id>` | manager |
| Send Venmo / Remind | `GET/POST /api/items/<id>/balance-due-email/{preview,send}` | manager |
| Refund (WD-credit + standalone credited) | `POST /api/items/<id>/payout-credit` (legacy alias `payout-wd-credit`) | admin |
| Match Venmo (header button) | `POST /api/accounting/auto-match-venmo-balance-due` | admin |

### Match Venmo — resolution chain (v2.16.12: handle-first)

`auto_match_venmo_inbound_to_balance_due` in `email_parser/database.py` walks
this chain to find the right `balance_due:` item for each unmatched Venmo IN
expense. The matcher accepts both `transaction_type='received'` and
`transaction_type='income'` — the LLM expense parser splits inbound payments
inconsistently between those two labels, and excluding `'income'` was silently
dropping ~half the inbound stream.

Per-expense lookup, in order:
1. **Venmo handle (authoritative)** — `expense.other_party_handle` (extracted from the Venmo notification email's `venmo.com/u/<handle>` URL by `extract_venmo_other_party_handle`) compared against `customers.venmo_username` after stripping `@` and lowercasing. On hit, looks up balance_due items by `customer_id`; if none match (the item row has a NULL `customer_id`), falls back to a canonical-name lookup for that same customer. **When the handle resolves to a customer, it is trusted exclusively** — the display-name steps below are skipped even if the resolved customer has no open balance due (that lands in `no_candidate` for manual review). A known payer must never borrow a same-named customer's balance.
2. **Exact name** — `items.customer = expense.merchant` (case-insensitive). Only runs when the expense has no handle or the handle isn't on any customer.
3. **Name alias** — `customer_aliases.alias_value = expense.merchant` with `alias_type='name'`, then look up the canonical customer name. Fixes the common case where a Venmo display name differs from the registered name (e.g. "James Youngs Jr" → "Pat Youngs").

Before v2.16.12 the order was name → alias → handle, which let a payment
misattribute: the Venmo display name is free text the payer controls, so a
payer whose account displays a family member's registered name could clear
that other customer's balance due whenever the amounts fell within tolerance.

All paths require a match on the `balance_due:` amount within ±$1.00 to avoid
false positives on similar amounts. Multiple matches → `ambiguous`, no matches
→ `no_candidate`. The `+PAY` child created on a match inherits the parent
item's `customer_id` directly (name/email re-resolution is only a fallback for
NULL-cid parents).

**Memo fallback — spouse-pays-for-player (v2.107.0).** When handle → name →
alias all fail to produce an amount-matching candidate (the classic case: a
player's spouse pays the balance from *their own* Venmo, so the payer handle
and display name aren't the player's), the matcher makes one more pass over
the memo. The balance-due link we email the player prefills the memo with the
**player's** name (`Richard Palacios - Balance due for s18.8 Vaaler Creek`), so
even a spouse's tap carries the player's name. The fallback scans every active
`balance_due:` item within ±$1.00 of the expense amount and keeps those whose
player **full name** (canonical or a `customer_aliases` name alias) appears in
`expense_transactions.notes` (the payer's memo). Exactly one hit → matched
(the `+PAY` child note is tagged `[memo-match]` for the audit trail); two or
more → left for manual. Guards against misfire: **full names only** (`_memo_match_names`
requires a space and ≥5 chars, so a bare "Richard" never matches), exact amount,
and unique-open-balance. This is the inbound mirror of the outbound refund
matcher, which already accepts a memo-in-notes hit as one of its verifiers.
`match_via_memo` is logged (`venmo memo-match: exp … → item …`). Handles/names
still take priority — the memo pass only runs when identity resolution comes up
empty.

Diagnostic: `GET /api/admin/venmo-debug?payer=<name fragment>` returns the full
state (expense_transactions, customer_aliases, customers.venmo_username,
balance_due items) for a payer fragment so you can see exactly where the chain
breaks.

### Balance-due email Venmo link — the `/pay/venmo` bounce page (v2.106.2)

The balance-due email's "Pay on Venmo" button links to `GET /pay/venmo`
(no auth — it lives in members' inboxes), not to venmo.com directly.
Reason (Kerry 2026-07-15, Richard Palacios's payment): `https://venmo.com/...`
universal links render every encoded space in the `note` as a literal `+`
in the prefilled memo — no encoding avoids it — while the native
`venmo://paycharge` scheme decodes `%20` correctly, but Gmail strips
app-scheme hrefs from emails. The bounce page is the bridge: the email
carries an https link to `/pay/venmo?to=&amount=&note=`, the page
auto-fires the `venmo://` link after 400ms, shows the memo as copyable
text, and offers the venmo.com web link as a desktop fallback (with a
warning that the memo may lose its spaces there).

Params are sanitized (`to` stripped to handle-safe chars, `note` capped
at 200 chars, `amount` must parse > 0 → else 400) and HTML-escaped, so
the page reflects nothing raw. The memo itself follows the ratified
grammar: inbound money is FOR the event (`[First] [Last] - Balance due
for [Event]`); outbound credits read FROM their origin event (see
`customers.md` → refund memo grammar). Changing memo wording is safe for
auto-matching: `auto_match_venmo_inbound_to_balance_due` matches on
customer + amount, never memo text.

INFO-level logs are emitted for every unmatched expense (`venmo no-candidate:
exp <id> payer='<name>' handle=<handle>`) and for handle-resolution outcomes
in Railway logs.

**Event-level** Edit / Merge / Delete (entire event) remain admin-only.
The client-side `btn-undo-credit-apply` handler also gates on
`currentRole === 'admin' || 'manager'` so a manager's click isn't
silently swallowed.

See `docs/claude/schema.md → Deferred / Known Concessions` for the
`require_role` decorator caveat (only enforces `"admin"`; everything
else is effectively "any authenticated").

## Player ACTIONS — desktop/mobile parity (v2.111.0)

Both the desktop table (⚙▾ dropdown) and the mobile roster card render
per-player actions from ONE shared builder, `playerActionItems(r, ev, f)`
in `events.html` (formatted by `_playerActionMenuHtml` for desktop /
`_playerActionBtnHtml` for mobile). Before this, mobile was a separate,
thinner implementation with **no credit-transfer branch**, so an active
credit-transfer registration (e.g. Daniel South) showed Credit/WD on
mobile instead of the **Undo** (revert-credit-application) desktop shows —
Kerry couldn't revert a player from his phone. Do NOT re-inline
per-view action logic; add new actions to `playerActionItems` only.
Handlers are all `document`-delegated, so a mobile button with the same
handler class + data-attributes drives the same endpoint and role gating.
The mobile "Inactive" list stays Reverse-only, matching the desktop
action set for credited/wd/transferred/refunded rows.

**Add Player name autofill — custom typeahead, not `<datalist>` (v2.111.1).**
The Add Player modal's name field (`#add-player-name`) uses a custom
suggestion dropdown (`#ap-name-suggest`, `renderApNameSuggest` /
`wireApNameSuggest`), NOT a native `<input list=datalist>` — iOS Safari
renders no dropdown for `<datalist>`, so on mobile the roster autofill
silently did nothing when RSVPing a player. The typeahead matches
prefix-then-contains over `apCustomerNames` (unique `items.customer`
values, set when the modal opens), selection is on `mousedown` (fires
before the iOS input blur) and dispatches an `input` event so the
existing known-player status auto-fill + new-contact-field toggling still
run. Do NOT reintroduce `<datalist>` for a mobile-facing autocomplete.

**Mobile roster badges (v2.111.2, Kerry).** The mobile card `tag` now
renders the green `Credit: $X` chip (`btn-apply-credit-badge`, tappable
to apply) for RSVP/gg-rsvp players with an outstanding credit — parity
with the desktop roster. The `NONE` side-games pill is suppressed on
mobile cards (`sideGameLabel !== "NONE"` guard in `topTags`) — it was
noise, especially on RSVP-only rows; NET/GROSS/BOTH still show.

## Player ACTIONS — Visual conventions

| Element | Rendering |
|---|---|
| Transfer indicator | Compact circular **T** badge (`status-tag-circle status-tag-from-transfer`) on **deep navy** (`#1e40af` bg, `#1e3a8a` border, white text) — harmonizes with the light-blue (`#dbeafe`) credit-transfer row tint |
| Paid-balance indicator | Compact circular **$** badge (`status-tag-circle status-tag-paid`) — replaces the older green "Paid" pill on settled credit-transfer rows; tooltip "Balance paid via Venmo on YYYY-MM-DD" |
| Coupon indicator | Compact circular **C** badge (`.coupon-badge`, purple) on items with `coupon_code` or `coupon_amount` set; tooltip shows full coupon code + discount |
| RSVP reminder pill | "Remind" (was "RSVP - Remind") |
| Balance-due pill on credit-transfer rows | `-$X.XX` (was `$X.XX DUE`) |
| Undo Credit button | "Undo" (was "Undo Credit") |
| Delete button | Compact red **×** icon (`.btn-delete-manual` / `.btn-danger` tightened to icon style); `title="Delete"` for hover hint |
| Sort arrows | Hidden via `.sort-arrow { display: none }`; column headers stay clickable |
| Check Now button | Header on Events page mirrors the Transactions page button — POSTs `/api/check-now`, polls `/api/check-status`, refreshes events on completion |
| Stripped price suffix | `stripPriceSuffix(s)` removes the noise `' (credit transfer)'` from `item_price` at every render site (cells, modals, mobile cards). Other suffixes like `(credit)` and `(comp)` are preserved. Storage is unchanged: `items.item_price` keeps the literal text. |
| Child +PAY truncation | Child +PAY rows truncate the GAMES cell to `max-width: 8rem` with `overflow: ellipsis` + `title=` so long `+PAY Difference between …` labels can't stretch the parent's GAMES column. |
| Adjacent circles | `.status-tag-circle + .status-tag-circle { margin-left: 0 }` so two circular badges in a row (e.g. T+$ on a paid credit-transfer row) group visually instead of being separated by the default `0.35rem` margin. |

## Player ACTIONS — Row tinting palette

Each registration row's background is set inline (per `<td>`) to one of the
following based on status, in this precedence:

| Slot | Color | When |
|---|---|---|
| RSVP-only / GG RSVP | `#fef3c7` (amber, italic) | `transaction_status` is `rsvp_only` / `gg_rsvp` |
| Comp / Manager | `#dcfce7` (mint green) | `email_uid` starts with `manual-comp` |
| GUEST | `#fbcfe8` (pink) | cleaned `user_status === "GUEST"` |
| 1ST TIMER | `#fdba74` (peach) | cleaned `user_status === "1ST TIMER"` |
| Manual / Credit transfer | `#dbeafe` (light blue) | `email_uid` starts with `manual-` **or** `transferred_from_id IS NOT NULL` (catches credit-transfer rows whose RSVP came in via the regular email parser, not a synthesized `manual-gg-rsvp-…` uid). The Delete action and "Manual" badge stay gated on the strict `email_uid` check so a credit-transfer row can't be accidentally deleted (which would orphan the source's `transferred_to_id` pointer). |
| WD | `#fef2f2` (light red) + 0.55 opacity + line-through | `transaction_status === "wd"` |
| Credited / Transferred / Refunded | white + 0.6 opacity (dimmed) | corresponding `transaction_status` |
| Active member (default) | white | otherwise |

Note: GUEST and 1ST TIMER are checked **before** the manual-blue tint so a
guest who happens to be a manually-added player still reads as Guest.

## Surname Uppercase for Elevated Roles

`displayName(name, status)` (events.html and dashboard.js) uppercases the
surname when `status` is `MEMBER` / `MEMBER+` / `MANAGER` / `OWNER`
(case-insensitive). Render-only decoration; underlying data unchanged.
Applies to active player rows, mobile cards, Inactive section, Not
Playing section, and the player picker dropdowns. Customers page does
**not** apply this decoration (proper case throughout).

For Not Playing rows (which lack a per-item `user_status`),
`get_rsvps_for_event` and `get_all_rsvps_bulk` surface a `customer_status`
field on each rsvp dict — derived from `customers.current_player_status`
+ `customer_roles` (any of `manager` / `owner` / `admin` → "MANAGER";
`active_member` → "MEMBER"; `member_plus` → "MEMBER+"). The renderer
passes that to `displayName()` so Not Playing surnames uppercase
consistently with the rest of the page.

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

Events can be cancelled or postponed from the event detail view (admin
only) — desktop: the registrations header's ⚙ Actions menu; **mobile
(v2.102.1): the expanded event card's ⚙ Actions menu** (it was
desktop-only until Kerry hit exactly that gap running the s9.18
rain-out from his phone). Both show Restore Event instead once the
event is cancelled/postponed.
New columns on `events` table: `status` TEXT (`active`/`cancelled`/`postponed`),
`status_reason` TEXT, `rescheduled_to_event_id` INTEGER, `status_changed_at` TEXT.

**Cancel Event modal — ONE-TAP EXECUTE (v2.102.0, Kerry-ratified after
the s9.18 rain-out):** a single screen of questions, then one Execute:
1. Status (`Cancelled`/`Postponed`) + reason (required).
2. Paid players: **Credit All** (default) / **Refund All** (methods
   auto-detected) / **One-by-One** (inline per-row Credit/Refund/Skip;
   paid players load when the modal opens, BEFORE anything runs).
3. Notification email (default ON, editable subject/body). Template
   vars: `{player_name} {event_name} {event_date} {course} {reason}
   {status_label} {credit_amount} {credit_line}` — `{credit_line}` is
   personalized per player server-side: credited → "Your $X.XX entry
   has been converted to a full credit…", refunded → includes the
   method, skipped → "we'll follow up", RSVP-only/comp → nothing owed.
   **Preview Emails** (v2.103.0) renders every recipient's exact email
   before execute — outcome chip w/ amount, subject, full body — via
   `POST /api/events/<id>/cancel-preview` (zero-write dry run that
   predicts outcomes from the selected mode and renders through the
   SAME shared helpers the send uses: `_cancel_recipient_list` /
   `_cancel_predicted_outcomes` / `_cancel_event_vars` in app.py, so
   preview and send cannot drift). Flags players with no email on file.
4. **Execute** → `POST /api/events/<id>/cancel-execute` does everything
   in one call: sets status, silently credits comps, settles paid
   players, then emails **everyone** — paid, skipped, RSVP-only item
   rows, and unmatched PLAYING `rsvps` — with sends recorded in the
   Message History log. Summary reports actions, emails, and any
   players with no email on file.

**v2.104.0 additions (Kerry, after the live s9.18 run):**
- **Clear RSVP roster** (checkbox, default ON; `clear_rsvps` on the
  endpoint): unpaid `rsvp_only`/`gg_rsvp` item rows are flipped to `wd`
  (`clear_event_rsvp_items(event_id, note)`) so the roster reads empty
  — the credit pass rightly skips never-paid rows, which otherwise kept
  the roster populated post-cancel. The notification plan captures them
  BEFORE the clear, so they still get the email. The UI also stops
  rendering unmatched-GG-RSVP synthetic roster rows (and counting them)
  on cancelled/postponed events.
- **Status badge picker** (`badge` on the endpoint → new
  `events.status_badge` column): chips CANCELLED / RAINED OUT / COURSE
  CLOSED / WEATHER / POSTPONED / RESCHEDULED choose the label shown on
  the desktop list rows, mobile event cards, and the detail banner.
  Auto-defaults from the status; Restore clears it; editable later via
  `update_event` (`status_badge` whitelisted) for backfills.

**Why plan-before-credit matters:** the historic flow credited players
FIRST and only then offered the email — but the send path skipped
credited registrants, so the notice reached nobody. `cancel-execute`
computes recipients + exact amounts via
`plan_event_cancellation_notice(event_id)` (active parent items +
active add-on children, summed per player across multiple orders,
canonical email resolver) BEFORE any status/credit write. Additionally,
the Message Players composer and `/api/messages/send` now INCLUDE
credited/refunded registrants when the event is cancelled/postponed
(they are the audience there); transferred players stay excluded and
active-event behavior is unchanged.

**Key behaviors:**
- Refund method auto-detected from original payment (`godaddy` → GoDaddy, `venmo` → Venmo, etc.)
- Add-on payments cascade automatically via existing `credit_item` / `refund_item` logic
- Comp and RSVP-only players are silently removed (no credit/refund needed) but still notified
- **Restore Event** button appears on cancelled/postponed events until the first player
  action is taken (`can_restore_event(conn, event_name)` checks for any credited/refunded items)
- Cancelled/postponed badges shown on the event list rows
- Status banner shown at top of event detail view

**API endpoints (all admin):**
- `POST /api/events/<id>/cancel-execute` — `{status, reason, mode:
  'credit'|'refund'|'custom', actions?, send_email, subject, html_body}`
  → the one-tap flow (status + settle + notify in one call)
- `POST /api/events/<name>/cancel` — `{status, reason}` → sets event status
- `POST /api/events/<name>/restore` — clears status back to active
- `GET  /api/events/<name>/cancellation-players` — list of active players with payment info
- `POST /api/events/<name>/cancel-bulk` — `{action: 'credit'|'refund', method?}` → bulk apply (legacy)
- `POST /api/events/<name>/cancel-apply` — `{actions: [{item_id, action, method?}]}` → one-by-one apply (legacy)

**Key DB functions:**
- `set_event_status(conn, event_name, status, reason)` — writes status + timestamp
- `can_restore_event(conn, event_name)` — returns True if no credited/refunded items yet
- `get_cancellation_players(conn, event_name)` — returns active players with payment method
- `plan_event_cancellation_notice(event_id)` — per-player notification plan
  (totals + canonical emails), MUST run before crediting; tests in
  `test_cancel_notice.py`

# RSVP Credit Application (from Events page)

When an event is cancelled, players who had credits from that event and are now RSVPing
to a future event can have their credit applied directly from the RSVP row.

**Identity rule (v2.104.2, the cross-Daniel bug):** every credit lookup
in this flow resolves the player by the RSVP row's own `customer_id`
FIRST, and trusts `matched_item_id` only when the item's email agrees
with the RSVP's — the first-name matcher can pin an RSVP to the WRONG
player's item (Daniel South's Vaaler RSVP → Daniel Lehan's purchase),
and resolving through such an item surfaces the other person's credits.
`get_event_rsvp_credit_map`'s synthetic-row query must stay in PARITY
with the frontend's `unmatchedPlaying` filter (including the
matched-but-different-email branch) or mis-matched players silently
lose their Credit badge. Regression: `test_rsvp_credit_map.py`.

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
  target item to `rsvp_only` (or deletes if it was a promoted GG RSVP item). Also handles
  every `+PAY` child of the reverted parent (not just rows tagged with
  `[xfer-consumed:<id>]`): each child is detached, children with non-zero `item_price`
  flip to `transaction_status='credited'` (so the player's payment stays on their account
  as a standalone credit), and any `expense_transactions.matched_item_id` pointing at the
  child is cleared so a future Match Venmo run can re-attach.
- Startup helper `repair_orphan_pay_children()` heals pre-existing orphans for parents in
  `transferred` / `rsvp_only` / missing state — re-points `parent_item_id` at an active
  sibling parent for the same customer + event when one exists, otherwise converts the
  child to a standalone `credited` item with a descriptive `credit_note`. Idempotent.
- `POST /api/items/<id>/reverse-credit-application` (admin only)

**Apply Credit nets prior unallocated Venmo +PAY items:**
- `apply_credit_to_rsvp()` scans for orphan manual-payment items by the same customer
  (`parent_item_id IS NULL`, `merchant LIKE 'Manual Entry%' COLLATE NOCASE`, last 14 days),
  reparents them onto the new credit-transfer item with a `[xfer-consumed:<id>]` notes tag,
  and nets their total against `amount_owed`. If fully covered, the parent flips to
  `paid_at:<today>`; any surplus is posted as a `transaction_status='credited'`
  "Overpayment credit" item that surfaces in the customer's available credit pool.
- One-time backfill: `reconcile_orphan_venmo_payments()` + `POST /api/admin/reconcile-orphan-venmo`
  sweeps existing credit-transfer rows with `balance_due:*` and applies the same logic
  retroactively. Idempotent; supports `?dry_run=1`.

## Apply Credit to Event from Customers Page

Credited items in customer detail views have an **Apply** button (alongside Reverse).
Clicking opens a modal to select an upcoming event, shows a price preview (credit vs. event
price, balance-due or excess handling), and applies the credit.

**API endpoints:**
- `GET  /api/items/<id>/apply-credit-info?event_name=<name>` — preview amount owed / excess
- `POST /api/items/<id>/apply-to-event` — `{event_name, disposition}` → apply credit

Uses idempotent uid `manual-credit-{credit_item_id}` to prevent double-apply.
All three rendering paths on the Customers page (inline expand, detail panel, mobile card) updated.

## Apply Credit modal — holes default + multi-credit + Venmo handle inline entry

- **Holes default from event format.** For non-combo events, `apply_credit_to_rsvp` and the
  client-side modal force `holes` to match the event format (e.g. always `18` for an
  18 Holes event), regardless of the credited *source* item's holes. Combo events keep the
  cascade `override > credited > "9"`. Applied in three places: `apply_credit_to_rsvp`
  (database.py), `api_rsvp_credit_info_by_item` + `api_gg_rsvp_credit_info` (app.py), and
  the modal renderer (events.html). Prevents the bug where applying a 9-hole credit to an
  18-hole event yielded `subtotal $109 / owed $32.41` server-side while the modal showed
  `$123 / $46.41`.
- **Multi-credit selection.** The credits table now has a checkbox column (defaults all
  checked). "Total Credit (selected)" recalculates as boxes toggle, and the submit handler
  sends only the checked credit IDs. Last remaining checkbox can't be unticked.
- **Inline Venmo handle entry.** When "Venmo back" is selected and no handle is on file,
  the modal shows a `+ Add @handle` affordance that expands to an inline input + Save
  button. Save persists via `/api/customers/update`, then the modal re-renders the excess
  section with the prefilled Venmo deep link. `excess_action="venmo"` is accepted by
  `apply_credit_to_rsvp`; the excess credit row is created in both `keep` and `venmo`
  modes so the audit trail is preserved either way.
- **One-tap Venmo-back (v2.112.0, Kerry).** Selecting "Venmo back" and tapping **Apply
  Credit & Register** now opens Venmo automatically (right person/amount/memo) and
  self-records the refund — no separate link click, no manual record. Flow: the
  apply request is dispatched FIRST (so `_arm_excess_venmo_watch` in app.py arms a
  refund watch on the new excess-credit item — `apply_credit_to_rsvp` returns
  `excess_credit_id` — before the receipt can arrive), THEN `window.location.href` fires
  the native `venmo://` link **synchronously inside the click gesture** (iOS blocks
  app-scheme navigation after an `await`). The receipt then auto-records via the same
  `refund_watches` / `auto_match_refund_watches` path as the red Refund buttons (amount
  + customer/handle, ~75s/180s quick sweeps + 2-min cycle), flipping the excess item
  `credited → refunded`. The client passes `excess_venmo:{handle,memo}` so the watch memo
  matches what's paid; memo uses the ratified "Excess credit from [origin event]" grammar.
  Both the RSVP and GG-RSVP apply-credit endpoints call the helper.
  **Memo origin (v2.112.1, Kerry):** the memo names the ORIGINAL event the
  credit came from, not the event it was last applied to. `get_player_credits`
  attaches `origin_event` to every credit via `_credit_origin_event()`, which
  traces the transfer chain for excess/overpayment rows (email_uid
  `credit-excess-<rid>` → that registration's `transferred_from_id` → the
  source credit → recurse) back to the origin; normal rain-out/WD credits keep
  their own event. All credit-info responses expose `origin_event`; the modal's
  Venmo memo uses `origin_event` (falls back to `event_name`). Verified: a
  chained "Excess credit — s9.19 The Quarry" credit resolves to origin
  "s9.18 Cedar Creek".
- **Auto entry-confirmation email (v2.113.0, Kerry).** When Apply Credit & Register
  leaves **nothing owed** (`amount_owed <= 0` — the credit fully covers or overcovers
  the entry), the player is auto-emailed a confirmation ("you're entered into [event]")
  with the details (date, course, holes, tee, side games, credit applied) + an excess
  note if overcovered. `_send_credit_entry_confirmation(item_id, result)` runs on BOTH
  apply-credit endpoints (RSVP + GG-RSVP), through the same Graph sender + `log_message`
  as the balance-due email. It does NOT fire when a balance is still due (the balance-due
  email covers that). Kill switch `AUTO_CREDIT_ENTRY_EMAIL=0`; test routing
  `CREDIT_ENTRY_EMAIL_OVERRIDE=<addr>`. Wrapped so a mail failure never breaks the apply.
  **Manual / retroactive send (v2.113.1):** the build+send lives in `database.py`
  (`build_entry_confirmation_email` / `send_entry_confirmation_email`); the auto-path
  delegates to it. `POST /api/items/<id>/entry-confirmation/send` (manager) and MCP tool
  `send_entry_confirmation(item_id)` force-send for a registered item (skip the balance
  guard) — the resend path for registrations made before the auto-email. "Credit applied"
  falls back to the item's price when there's no live apply result.
  **Admin CC + redirectable copies (v2.113.2, Kerry).** Every entry-confirmation send
  (auto + manual) now CCs `admin@thegolffellowship.com` for the record via
  `_auto_email_cc()`; disable/repoint with the `AUTO_EMAIL_CC` env var (`AUTO_EMAIL_CC=""`
  suppresses). `send_entry_confirmation_email` takes an optional `cc` param (default =
  admin CC; `""` suppresses on a one-off). The `scoring-entry-confirm` bridge accepts
  `"<item_id>[|<override_to>[|<cc>]]"` so a copy of exactly what a player received can be
  redirected elsewhere (e.g. `kerry@`) without CC'ing admin (empty third field).

# Payout Credit / Refund (WD + standalone credited rows)

When a player WDs late (only part of their payment is creditable) or carries a standalone
`credited` row (excess credit, overpayment credit, full registration credit), the admin
can record a real-world Venmo / Zelle / Cash App / Check / GoDaddy / PayPal refund and
clear the balance.

**Refund button placement:**
- Event detail (events.html) — Refund button next to Reverse on every WD row that carries
  a `credit_amount`.
- Customers page (customers.html) — Refund button on every `credited` or WD-credit row
  across all three render paths (card view, table view, detail tab).

**Modal fields:** method (Venmo / Zelle / **Cash App** / Check / GoDaddy / PayPal),
back-datable refund date, optional note.

**Backend behavior** — `payout_credit(conn, item_id, method, date, note)` in database.py:
- For `transaction_status='credited'`: amount comes from `item_price`, row flips to
  `refunded`.
- For `transaction_status='wd'`: amount comes from `credit_amount`, the field is cleared,
  status stays `wd`.
- In both cases an `acct_transactions` expense entry is written (`category='refund'`,
  `source=method`). Method `Venmo` routes the entry to the `Venmo` account; `PayPal`
  routes to the `PayPal` account; everything else routes to `TGF Checking`. The
  `credit_note` is stamped `Refunded $X.XX via <method> on YYYY-MM-DD`.
- `payout_wd_credit` retained as a Python alias for back-compat.

**API endpoints (admin only):**
- `POST /api/items/<id>/payout-credit` — canonical route
- `POST /api/items/<id>/payout-wd-credit` — legacy alias (kept so the existing events-page
  WD pill keeps working without changes)

This closes the loop on the apply-credit-with-Venmo-back flow: admin sends the Venmo
manually using the prefilled link, then clicks Refund on the resulting excess-credit
row to record the disbursement and clear the customer's credit balance.

# Transfer cascade — +PAY children follow the parent

`transfer_item` now sums the parent's `item_price` with every active `+PAY` child and
creates ONE new credit-transfer item at the target with the combined amount. Children are
flipped to `transferred` alongside the parent and their `transferred_to_id` points at the
same target. The resulting target `item_price` reads e.g. `$83.37 (credit)` instead of
`$75.00 (credit)` with an orphan `$8.37` child sitting on the source event. `credit_note`
on the new row spells out `$75.00 parent + $8.37 +PAY` so the breakdown is visible.

**Modal gating:** when the Credit/Transfer/Refund dialog is opened on a `+PAY` child
(`parent_item_id IS NOT NULL`), Transfer and Partial Refund are hidden — both options are
nonsensical on a top-up payment (Transfer would strand the parent registration, Partial
Refund would split a single small line). Credit and Refund remain.

# Pairings Generator (events.html PAIRINGS tab)

Full pairings system with seed/lock, cart pairs, and round-robin history.

**Tables:**
- `event_pairings` — saved group assignments per event: `holes`, `group_num`,
  `slot_label` (e.g. `1A`, `1B`, `2A`), `cart_pos` (1–4 within the foursome).
- `pairing_history` — tracks who played with whom per event for round-robin weighting
  (calendar-year window).

Both tables are created lazily on first pairing operation by `_ensure_pairing_tables()`,
called at the top of every pairing function (get, save, delete, history counts, generate).
This eliminates `'no such table'` errors on existing deployments.

**Generator algorithm (Python, `email_parser/database.py`):**
- **Random mode** — history-aware weighted pairing (calendar-year round-robin); honors
  one-way partner requests with same-cart enforcement (positions 1&2 or 3&4).
- **ABCD mode** — splits the field evenly into handicap tiers, one player per tier per group.
- **9 / 18 / 27 hole separation enforced**; players never mix across formats (27 Holes
  shares the 18-hole code path).
- **Threesomes** placed at the furthest holes for shotgun events (1A, 1B, 2A… order).
- **Seed/lock:** pre-assign individual players, cart pairs, or full foursomes to specific
  slots before generating.
- **Tee time slots** computed from `events.start_time` + group count + tee interval.

**Generator robustness — query event players by `item_name`, not `event_id`:**
The `event_id` FK on items is incompletely backfilled on the live DB, so the generator
matches items by `item_name` (+ `event_aliases`) with `event_id` as a fallback — same
pattern used by `get_all_events` throughout the rest of the app. Query joins start from
`events → event_aliases → items` (SQLite requires `ON` clauses only reference tables
already joined).

**API routes (admin):**
- `GET  /api/events/<id>/pairings` — load saved pairings + slot metadata
- `POST /api/events/<id>/pairings/generate` — run generator (not saved)
- `POST /api/events/<id>/pairings/save` — persist + rebuild `pairing_history`
- `DELETE /api/events/<id>/pairings` — clear saved pairings

**UI swap/move modes** (buttons in the pairings control bar):
- **Player** — click one player then another to swap positions.
- **Cart Pair** — click one cart (positions 1&2 or 3&4) then another to swap pairs.
- **Group** — click one foursome then another to swap entire groups.
- **Move** — click a player to pick them up, then click a destination group to place
  them there without swapping. The player is removed from their current position and
  inserted into the destination group's lowest open seat. Works for both assigned players
  and unassigned players (see below).
- **Open seats are click targets (v2.49.0, Kerry):** every group renders all four
  seats; missing seats show as dashed "— open —" rows (`.pairing-empty-slot`). With a
  selection active, clicking an open seat drops the selected player into THAT exact
  seat (Player/Move modes) or moves the selected cart pair into that cart (Cart Pair
  mode — `_moveCartPair`, which handles the empty-cart case `_swapCartPairs` can't
  since it swaps data in place; a half-full target cart routes to `_swapCartPairs`).
  Source groups keep their remaining players' cart positions (no renumbering) so
  seats stay stable. `_movePlayer` accepts an optional destination seat and otherwise
  lands in the lowest free position (the old `length+1` could double-book a cart
  position when seats were sparse).
- **Hole assignment edit (v2.49.0):** the group header (TGF orange, no more
  "(Hole)" suffix) is clickable — prompts for a new `slot_label`, marks dirty, and
  Save persists it (save_event_pairings stores slot_label from the payload).
- All modes block cross-holes moves — you can't move a 9-hole player into an 18-hole
  group. Shows an alert and resets selection.
- Cart dots use solid hex colors (`#3b82f6` blue for Cart A, `#22c55e` green for Cart B)
  instead of CSS vars, so they stay visible on light backgrounds.
- Saved-state indicator + dirty tracking before save.

**Unassigned players panel:**
Displayed below the pairings groups when any registered players are not yet in a group.
Shows an amber "⚠ UNASSIGNED (N) — Click player then a group to place" header. Uses
`getUnassigned(state)` which computes the set difference between all registered players
and those in current groups. In **Move** mode, clicking an unassigned player selects
them; then clicking a group places them. Clicking the same unassigned player again
deselects. The panel disappears automatically once all players are assigned.

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

## Withdraw Player modal — Credit Components (v2.16.6+)

`calculateWdComponents(item, eventName)` in `events.html` breaks a withdrawing player's
price into checkbox line items (Course Fee, Included Games, TGF Markup, Net Games, Gross
Games) so the admin can pick which parts to credit back. It reads the **same frozen
per-event pricing fields** as the calculator above (`course_cost*`, `tgf_markup*`,
`side_game_fee*`, `per_game_addon`, holes-aware for 9/18 Combo) and reuses
`getPerGameAddon(format, override)` for the Net/Gross Games line items — it does **not**
read the Side Games Matrix (`GAMES_MATRIX_9`/`_18`, see below). That matrix tracks prize
*payouts to game winners*, sized by however many net/gross players are registered right
now; it has no relationship to what the withdrawing player was actually *charged* at
registration, and recomputing off it drifts every time another player registers or
withdraws from the same event. If a future change needs the credit total to reconcile
against `item_price`, adjust the pricing fields/`getPerGameAddon`, not the games matrix.

**Column fallback order (v2.16.11+):** the `_9`/`_18` pricing columns are only
populated for 9/18 Combo events — standalone "9 Holes" events store pricing in
the BASE columns (`tgf_markup`/`side_game_fee`), and the combo save path
actively nulls the base columns. So every holes-aware read must chain
`_9/_18 column → base column → PRICING_DEFAULTS`, exactly like the Apply
Credit modal's `_updateCrdCalc()`. The original v2.16.6 version skipped the
base-column step for 9-hole events, so a custom-priced standalone 9-hole
event showed default amounts ($8/$7) in Withdraw Player / Partial Refund.

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
- **Page** at `/tgf` — three top-level tabs: EVENTS | SEASON CONTESTS | GOLFERS
  (v2.51.0). SEASON CONTESTS reuses the events layout filtered to contest
  accounts by code convention (`_CONTEST_ACCOUNT_RE`: '<MONTH> Points…',
  'Fellowship Cup…', 'Match Play…'); each month is its own payout account.
  `record_monthly_points_payouts(force=False)` (database.py) creates
  'MARCH Points 2026'-style tgf_events rows for completed months from the
  monthly snapshot ($1/member, ties split; one tgf_payouts row per winner,
  category 'monthly_points') — runs after the daily monthly-points refresh,
  idempotent, delegates to import_tgf_payouts; bridge command
  `scoring-monthly-payouts[:force]`. The Venmo matcher resolves
  'Winnings for <MONTH> Points' memos ONLY to the month account, and the
  false-match repair skips legitimate month-account links. Monthly rows
  flow into Customers → Winnings automatically via /api/customers/winnings.
- **Data** from `tgf_events` and `tgf_payouts` tables; golfer identity is the `customers` table (tgf_golfers was eliminated)
- **API:** `GET /api/tgf` returns `{customers, events, winnings}` where customers is the list of payout recipients
- **Sidebar totals are `tgf_events.total_purse`** (a stored column set at
  screenshot-import/record time), NOT `SUM(tgf_payouts.amount)`. A
  tgf_events row with zero payout rows still shows its stored purse — the
  2026-07-20 "Cedar Creek $229" was exactly this shell-row class, and
  row-only sweeps truthfully report `removed: 0` against it.
- **Payout repair bridges (v2.129.x, 2026-07-20):**
  - `scoring-payouts-clear-auto:<event>[|all]` — removes an event's
    auto-recorded (`auto:%` description) payout rows + their PENDING
    ledger rows; `|all` (Kerry-directed only) also removes manual/
    screenshot rows AND deletes matched tgf_events rows left with zero
    payout rows (reported as `empty_event_rows_deleted` with the stored
    purse). Event matching is whitespace-collapse-normalized CODE
    matching only (bare code as prefix, non-digit guard). A course-NAME
    fallback was tried and REMOVED same-day: same-course different
    events (s18.1 CEDAR CREEK vs s9.18 Cedar Creek) share the name
    token, and it swept 36 legitimately-paid rows from two other events.
  - `scoring-payouts-restore:<tgf code>[|apply]` — rebuilds deleted
    tgf_payouts rows from surviving bulk-confirm ledger mirrors
    (`source_ref 'payout-<original id>'` carries id/category/customer/
    amount/paid link; ids re-insert exactly — tgf_payouts is
    AUTOINCREMENT so deleted ids are never reused). Rows that were paid
    via grouped REAL Venmo receipts have no per-row mirror and are
    reported as a remaining gap, not guessed at. Arg parsing is
    pipe-safe (codes like "s18.3 SAN ANTONIO KICKOFF | Cedar Creek").
  - `scoring-payouts-unlink:<acct_transaction_id>` — clears the paid
    link from tgf_payouts rows wrongly matched to a receipt (rows revert
    to unpaid; the ledger row is untouched).
  - `scoring-rainout-label:<event>|<badge>|apply` stamps a shut-down
    event's cancelled status + badge; `|clear|apply` removes a
    mislabeled badge (status untouched). The Venmo subset-matcher pass
    (partial payments) only runs for memo-resolved events against that
    event's own payout group.

## Events Tab
- Sidebar lists events by date with total purse amounts
- Main area shows payouts table grouped by golfer (sorted by total descending)
- Expandable rows show category breakdowns (team_net, individual_net, skins, etc.)
- Venmo pay links generated for golfers with venmo_username set.
  Memo format (v2.49.6, Kerry): "[First] [Last] - Winnings for
  [event]"; on phones the links use the native `venmo://paycharge`
  scheme because the https universal link re-serializes the query and
  the app displays a literal '+' for every space in the memo (desktop
  keeps the venmo.com web link). Same treatment on the per-event
  PAYOUTS panel (`venmoPayHref` in events.html) and the excess-credit
  refund links (events.html + customers.html).

## Screenshot Paste / Import (/tgf page ONLY as of v2.49.4)
- The per-event PAYOUTS panel on the Events page no longer has a drop
  zone (removed as obsolete, Kerry 2026-07-08) — this section describes
  the /tgf page importer, which remains for manual/legacy imports.
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
- `_resolve_customer_for_payout(conn, name)` — resolves payout recipient to a `customer_id`: `_resolve_scoring_player` FIRST (v2.49.0 — GG results names are "LAST, First Suffix", exactly what the scoring spine's candidate expansion + curated handicap_player_links map resolve; the old comma-split alone turned 'ARIAS, Victor Jr' into first='Victor Jr'/last='Arias' and minted a fresh shell customer per recording pass), then the `_lookup_customer_id` cascade, then an exact first+last guard; creates a new customer with `acquisition_source='tgf_payout'` only if everything misses. The boot repair `_repair_tgf_payout_shells()` merges any identity-less tgf_payout shells whose name re-resolves to a real customer (repoints tgf_payouts, deletes the shell) — it healed the 8 Arias shells of 2026-07-07.
- Payouts linked to identity via `tgf_payouts.customer_id` (FK to `customers.customer_id`)

## PAYOUTS action column — one pill + "+ Add Payment" chooser (v2.81.0, Kerry)
The payout action cell renders exactly ONE control per row (was two
side-by-side badges, whose double width pushed the PAID pills off-screen
on mobile). Logic (both `/tgf` PAYOUTS `payCellHtml` in tgf.html and the
per-event PAYOUTS panel `renderPayoutsPanel` in events.html):
- **paid** → `PAID ✓` badge (tgf also keeps `PARTIAL` for mixed groups).
- **unpaid + a usable pay link** (venmo via `venmo_username`; paypal /
  cashapp via `payment_method`+`payment_handle`) → the Pay link ONLY. The
  redundant PENDING/UNPAID pill is dropped — a pay link already means "not
  paid yet" (Kerry). tgf keeps its "Sent · verifying…" state after a tap.
- **unpaid + zelle / no-deep-link method** → a single info badge.
- **unpaid + no method on file** → a single **"+ Add Payment"** chooser.

**PayPal/Cash App are USERNAME-only for a one-tap link (v2.82.1):**
PayPal.Me (`paypal.me/<user>` → `www.paypal.com/paypalme/<user>/<amt>`)
and Cash App (`cash.app/$<cashtag>`) resolve a username, not an email —
an email 404s to PayPal's "Something went wrong" page. `payAction`
(tgf) / `payoutPayLink` (events) now strip a pasted URL/`@`, and if the
remaining handle contains `@` return a `(manual)` badge instead of a
broken link (pay in-app, then Mark Paid). The chooser input shows a
per-method placeholder (`PAY_HINT`) so PayPal prompts for a PayPal.Me
name. Zelle is always manual (no deep link).

**Editing an already-set method (v2.83.0):** once a method is on file
the pill is tappable to change it (label `<Method> ✎`, e.g. `PayPal ✎`).
The chooser re-opens PRE-FILLED with the current `payment_method` +
handle (`tgfPayChooserWrap(ev,g,{manual,label,method,handle})` /
`addPaymentChooserHtml(g,code,{...})` carry `data-method`/`data-handle`;
`tgfRevealAddPay`/`evRevealAddPay` read them to prefill the select +
input). This is the fix path for a PayPal EMAIL wrongly entered — swap it
for the PayPal.Me username and the row becomes a working one-tap link.
Manual-method badges use a short `PAY_LABEL` name (not the verbose
`payAction` badge) so the pill stays narrow.

The chooser (not Venmo-only): pick Venmo / PayPal / Cash App / Zelle +
enter handle/email → Save posts to `/api/customers/update` with
`customer_id` + `fields` (`{payment_method, venmo_username}` for Venmo;
`{payment_method, payment_handle}` for the others). `update_customer_info`
persists these to `customers.payment_method` / `payment_handle` /
`venmo_username` (keyed by id, so it holds for every future event; both
columns already existed, seeded by `_seed_customer_payment_methods`). The
cell then swaps in place to the matching pay link (or a Zelle badge), no
reload. Helpers: `tgfRevealAddPay`/`tgfSaveAddPay` +
`payAction` (tgf.html); `payoutPayLink`/`addPaymentChooserHtml`/
`evRevealAddPay`/`evSaveAddPay` (events.html). The `/api/customers/update`
whitelist (app.py route + `update_customer_info`) now includes
`payment_method` and `payment_handle`.

## Payout auto-confirm — Venmo / PayPal / Cash App / Zelle (v2.50.0; multi-provider v2.84.0, Kerry)
`auto_match_venmo_payouts_to_tgf(expense_ids=None)` (database.py) marks
payouts PAID from the outbound receipt emails the expense inbox ingests.
**All four P2P providers ride one path** (v2.84.0): `classify_email`
fast-paths tag Venmo (`venmo.com`), PayPal (`paypal.com` "you sent"),
Cash App (`cash.app` / `notifications.cash.app`), and Zelle (bank
"…Zelle Confirmation", e.g. Frost `frostbank.com`, EXCLUDING Chase which
has no memo and stays a chase_alert). `parse_p2p_payment(provider=…)`
(one generic parser) extracts recipient + amount + the typed note; the
shared app.py handler stores each under its own `source_type`
(`venmo`/`paypal`/`cashapp`/`zelle`) and the matcher's filter is
`source_type IN ('venmo','paypal','cashapp','zelle')`. Every provider's
note carries the true payee + event ("<Name> - Winnings for s9.15 …";
PayPal labels it "Your note to <name>", Cash App prefixes "For ", Zelle
"Message:"). The memo payee-name regex tolerates an optional leading
"For " for Cash App. Records: recipient in `merchant`, memo in `notes`,
customer_id/event_id resolved by the expense pipeline). Per receipt:
resolve customer (customer_id → venmo handle → name/alias cascade →
**memo payee-name prefix → memo event + exact amount**, v2.79.2). The
last two fallbacks exist because the Venmo RECIPIENT display name is the
account's name, which can belong to someone else entirely — Matt
Griffin's Venmo shows "robert griffin", so his $38.25 s9.17 payout never
matched. The memo TGF types is authoritative: "Matt Griffin - Winnings
for s9.17 Silverhorn". Fallback (a) parses the "Name - " prefix and
resolves it via `_lookup_customer_id`; fallback (b) parses the memo's
event code and, if exactly one pending payout in that event owes this
EXACT amount, takes that payee. The expense parser now preserves the
memo verbatim (the "Name - " prefix was previously stripped), and new
payout emails resolve customer_id from the memo prefix at insert time
(app.py) before falling back to the Venmo display name.),
resolve the tgf event — v2.52.1 order: the MEMO's event code FIRST
("Winnings for s9.16 …" → tgf_events.code prefix; a space after the
dot is tolerated, 's9. 10' → s9.10) because the expense pipeline's
event_id guess is routinely wrong and blocking exact matches;
expense.event_id (via `tgf_events.events_id` / code == item_name) is
only the fallback — then match the customer's pending payout-group sum.
Amount tolerance scales with evidence (v2.52.1): memo-resolved event
±$3.00 (Kerry paid GG's printed amounts, which differ from our
computed cents by a few dollars), pipeline-resolved ±$1.00, no event =
exact cents; uniqueness required at every tier (two candidates =
ambiguous, skipped). On match: promote the
expense to the ledger if needed (auto-approving a 'pending' review
row), reverse the source='pending' placeholders, point every
tgf_payouts row in the group at the venmo ledger entry, stamp paid_at
= payment date → get_tgf_data derives payment_status='paid' so the
PAYOUTS tab shows PAID and the Pay link disappears. Idempotent
(already-linked receipts count as already_matched). v2.50.1 guards:
monthly-points memos ("Winnings for MARCH Points") are excluded — the
monthly race is paid from Contests, has no tgf_payouts rows, and a
$70.00 payment ±$1-matched a $70.37 event group in the first live
hour; the ±$1.00 fallback also now requires the event to have
resolved. Boot repair `_repair_false_monthly_venmo_matches` reverts
any such false links (reinstates the 'payout-<id>' pending
placeholder, clears paid_at). Triggers: each
arriving receipt email (expense inbox check), expense review approval
(PATCH expense-transactions), end of `record_event_game_payouts`
(consumes receipts that arrived before recording), admin backfill
`POST /api/tgf/auto-match-venmo-payouts`, bridge command
`scoring-payouts-venmo-match`. NOTE: the boot-time
`_match_pending_payouts_to_new_venmo` never matched these receipts —
it requires `acct_transactions.category='prize_payout'` + a `customer`
name, which the expense-promotion path doesn't set; the new matcher
works from expense_transactions directly.

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


## TGF MVP determination (v2.33.0)

`determine_tgf_mvp(event_name)` (database.py) automates the manual
cross-event comparison GG cannot do. Flow: resolve the event's
same-day linked set (event_date equality minus event_mvp_unlinks,
9-hole/combo nines only — mirrors getMvpLinkedEvents); per event,
collect NET-bundle buyers from items (alias-aware, Games-tab
eligibility rules, child add-ons merged); match buyers to
scoring_rounds by customer_id + event_id; score each round through
the formula layer (get_scorecard → stableford_net); City MVP =
highest points, tiebreakers Individual Net stroke score → Gross →
split; TGF MVP = City MVP with higher day points (summed across the
day's linked events), tie splits. States: single_event_day (all MVP
money to City MVP), awaiting_results (lists which events lack
imported rounds), no_net_buyers. Output includes the top-5 field per
event and GG-recorded event_mvps names for cross-check.

Surfaces: `GET /api/events/tgf-mvp?event=<item_name>` (manager);
MCP tool `determine_tgf_mvp`; Events Games tab 🏆 rows — City MVP
row and TGF MVP block hydrate lazily via hydrateMvpDeterminations()
(per-event fetch cache `_mvpDetCache`, spans marked data-done).

## Payouts page — Command Ledger (v2.54.0, TGF DS Phase 1)

/tgf is the Design System reference page (see CLAUDE.md → TGF Design
System rollout). Chrome: dark top nav + white sub-tab bar; tab names
unchanged (Kerry) but UNPAID renders as the right-aligned orange pill
(admin-only convention). The GOLFERS tab is the Command Ledger:
`.ledger-rail` (dark, 300px, search + ranked winnings leaderboard,
active row = orange left border) + `.ledger-detail` (Payouts/Info
toggle, season-year WINNINGS stat, per-event `.ev-band` collapsible
groups — chapter-colored via the JS `CHAPTER_STYLES` map, payout lines
color-coded via `CAT_COLORS`). Events collapse by default; `openEvents`
Set tracks per-event expansion. Mobile (≤768px): rail-only until a
golfer is selected (`.ledger.has-selection`), then detail w/ "‹ Golfers"
back button. Events/Season Contests/Unpaid tabs keep their previous
layouts and all pay/mark-paid plumbing.

## REFUNDS console (v2.108.0, Kerry — "nothing falls thru the cracks")

Admin **Refunds** top-tab on /tgf (right-aligned orange pill, next to
Unpaid) consolidates every credit refund in one place, so the manager
never has to hunt across 25 rows to see what's owed / paying / paid.
Backend `get_refunds_overview(db_path, completed_days=120)` in
`database.py`; route `GET /api/refunds/overview` (admin). Three buckets:

- **OUTSTANDING** — held credit balances that could be paid back: WD rows
  (credit in `credit_amount`) + standalone `credited` rows (credit in
  `item_price`), positive only, minus any with an OPEN refund watch.
  Sorted **oldest first**; each row shows an age
  chip (amber ≥14d, red ≥30d). **Age anchoring (v2.108.1)** — a credit's
  age is NOT `order_date` (that's the player's *registration* date, so
  same-event rain-out credits would each show a different age by who
  registered when). For registration rows flipped to credited/wd
  (rain-out, withdrawal) the age anchors to the linked **event's date**
  (`_credit_anchor` joins `events` via `items.event_id`), so every credit
  from one event shares an age. Synthetic credit rows (excess/overpayment
  — `email_uid` `credit-excess-*`/`credit-overpay*`, or item_name
  `Excess credit…`/`Overpayment…`) are created *at* credit time, so they
  keep `order_date`. Future-event or date-less credits fall back to
  `order_date`; ages clamp at 0. A per-item **"Held"** marker to separate
  intentionally-held credits from refund-pending ones is a **separate
  schema addition pending Kerry's ruling** — today it's age-sort only.
- **IN FLIGHT** — open `refund_watches` (a P2P pay link was tapped,
  awaiting the provider's receipt); shows method/handle + "watching…".
- **COMPLETED** — payouts recorded in the last `completed_days` days
  (status `refunded`, or WD rows stamped `Refunded …`), newest first,
  parsed from the `credit_note` payout stamp; badge **VERIFIED** when a
  refund watch confirmed it, else **PAID**.

Each bucket carries a count + dollar total (`totals`). v1 is
consolidate-and-route: an OUTSTANDING row's **Refund…** button
deep-links to `/customers?cid=<id>`, where the existing red Refund modal
(pay links + receipt verification) lives — money-action modals are NOT
duplicated into the console. Inline actions are the next increment.
Tests: `test_refunds_overview.py` (12 checks). Read-only; no schema
change.

## Hole-In-One pot (v2.130.x, Kerry-ratified 2026-07-20)

HIO is the one game pot that ACCRUES across events instead of paying per
event. `get_hio_pot()` (database.py): every played, non-rained-out event
contributes its games-matrix holeInOne amount ($1/player 9-hole,
$2/player 18-hole; 27-hole days like HILL COUNTRY MATCHES are $3/player
— $1 per 9 holes — via the `hio_27h_event_patterns` dial, default
'HILL COUNTRY MATCHES'). Scheduled (future) events are INCLUDED as soon as
they have registrations (Kerry 2026-07-20: the HIO dollars are collected
at registration, like the event's own pots in its payouts); the
contribution self-corrects as the field grows since the pot recomputes
live. The pot drains ONLY via `tgf_payouts` rows with `category = 'hio'`.

- **Carry-in dial**: `hio_pot_carry_in` = **1822.00** (app_settings, set
  2026-07-20; provenance in `hio_pot_carry_in_note`). Reconstruction:
  pot was $2,300 at the 2025 TGF Championship → Julius Jenkins was paid
  HALF ($1,150) for his ace (Aug 2025) → $1,150 remained + $672 added
  through fall 2025 play (verified by counting the ALL Gross leaderboards
  on the live tgf-sa2025/tgf-austin2025 GG portals — the
  `scoring-hio-gross:<subdomain>|<start>|<end>[|budget]` bridge; the
  archive's per-game result rows are winners-only and MUST NOT be used
  for field sizes).
- **Ace watch**: `import_gg_scorecards` raises a HIGH `scoring` action
  item ("HOLE-IN-ONE: <player> — hole N") whenever an imported card has
  strokes = 1 on any hole. The fix path is: verify on GG, pay the player,
  record the payout with category 'hio'.
