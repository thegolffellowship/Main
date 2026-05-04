# Customer Identity System

## Source of Truth
`customers` + `customer_emails` are the **canonical source of truth** for all customer data.
- `update_customer_info()` syncs edits to email/phone/name into `customers`/`customer_emails`,
  not just into `items.*` (transaction copies).
- `get_all_customers()` reads from `customers LEFT JOIN customer_emails WHERE is_primary=1`
  and is served by `GET /api/customers`. The Customers page overlays this data after the
  items-based map is built to always show authoritative contact info.

(For the list of tables that carry a `customer_id` FK, see `docs/claude/schema.md`.)

## Customer Lookup Flow (`_lookup_customer_id` — 5-step cascade)
When a new transaction arrives, the system resolves the customer in this order:
1. **Email via `customer_emails`** — exact email match
2. **Alias email via `customer_aliases`** — alias_type='email' JOIN customers
3. **Exact first+last name** in `customers` table
4. **Alias name via `customer_aliases`** — alias_type='name' JOIN customers
5. **Fallback: `items.customer_email`** — checks existing items for pre-migration customers

`_resolve_lookup_customer_id` (the variant used by some send paths) **also** consults
`customer_aliases` (alias_type='name') when the direct first+last name match misses, so
an `item.customer` of "Stu Kirksey" can resolve to the canonical "Stuart Kirksey" record.

## Customer Resolution (`_resolve_or_create_customer`)
- Calls `_lookup_customer_id` first
- If no match, creates a new `customers` row + `customer_emails` row
- On email IntegrityError (duplicate), returns the existing owner's customer_id instead of creating an orphan

## Canonical Identity Resolvers (`resolve_player_*`)

`items.customer_email` / `customer_phone` / `first_name` / `last_name` / `chapter` /
`user_status` are historical snapshots captured per-order — they can carry typos or stale
values that the manager has corrected on the Customer Info page. Reading `items.*`
directly resurrects bugs (e.g. handicap card preview using a typo'd email from one old
order). Five resolver helpers in `database.py` look up the canonical value via
`items.customer_id` (or by name match) and fall back to `items.*` only when nothing
canonical exists:

- `resolve_player_email(item, conn=None)` — `customer_emails.is_primary`
- `resolve_player_phone(item, conn=None)` — `customers.phone`
- `resolve_player_name(item, conn=None)` — `customers.first_name + last_name`
- `resolve_player_chapter(item, conn=None)` — `customers.chapter`
- `resolve_player_status(item, conn=None)` — `customers.current_player_status` + roles

Every customer-facing send path goes through `_resolve_player_email` (which delegates to
`resolve_player_email`): `_send_rsvp_credit_alerts`, `_build_balance_due_email`, the
`/api/items/<id>/send-payment-reminder` route, and the bulk-send composer's
`resolve_email()`. Drop the `'and i.get("customer_email")'` filters on player-collection
lists and skip rows that resolve to no email at send time, so manually-added RSVPs whose
email lives only in `customer_emails` are no longer excluded from reminders.

**Connection lifetime gotcha** — `_resolve_db` opens its own connection via
`get_connection()` and closes it directly with `conn.close()` in the resolver `finally`
blocks. The earlier implementation used `_connect(db_path).__enter__()` without holding
a reference to the contextmanager, which CPython's reference counting reclaimed
immediately and closed the underlying sqlite generator's connection in its `finally`
block — every `owns=True` resolver call then hit "Cannot operate on a closed database"
on its first `.execute()` and bubbled out of `api_send_messages` as a 500. Always open
the connection directly in resolver helpers.

## Identity Self-Healing at Boot

Three idempotent migrations run in `init_db()` so the `items` snapshot stays consistent
with the canonical `customers` / `customer_emails` records:

| Migration | What it does |
|---|---|
| `capture_email_aliases_from_items` | Promotes every `items.customer_email` value differing from the linked customer's primary email into `customer_aliases` (alias_type='email'). Idempotent — case-only variants and already-aliased typos are skipped. The Customer Info card's Aliases section then shows each captured variant under the 📧 icon. |
| `_heal_items_identity_fields` (Phase 1B) | Flattens `items.customer_email` / `customer_phone` / `chapter` / `first_name` / `last_name` to match the linked `customers` / `customer_emails` record. For email differences, captures the existing `items.customer_email` value as a `customer_alias` (alias_type='email') before overwriting. Other fields overwrite silently — there's no alias slot for phone/name/chapter, and the canonical record is by definition correct. Belt-and-suspenders behind the resolver helpers. |
| `_migrate_relabel_credit_pool_items` | Backfills descriptive `item_name` on credit-pool rows: "Excess credit — `<event>`" or "Overpayment credit — `<event>`". Idempotent (skips rows whose `item_name` already starts with the new prefix). |

## Drift detection on new orders (Phase 3)

When a new GoDaddy order arrives, `save_items()` compares the order's
`customer_email` / `customer_phone` / `chapter` against the canonical record on the linked
customer (`customer_emails.is_primary`, `customers.phone`, `customers.chapter`). For each
field that differs:

- **Canonical wins.** The items row is persisted with the manager-maintained value, never
  the order's drift.
- **A `parse_warning` is raised** (`EMAIL_DRIFT` / `PHONE_DRIFT` / `CHAPTER_DRIFT`) so the
  manager sees the discrepancy in the COO action-items banner and can decide whether to
  update the customer record, capture the variant as an alias, or dismiss it as a typo.
- `parse_warnings.customer_id` (Phase 2 FK) is populated so the warning links straight
  back to the affected customer.

## Customer Merge (`merge_customers`)
- Reassigns `items.customer` string (all transactions)
- Reassigns `items.customer_id` from source to target
- Moves `customer_emails` from source to target
- Creates name alias for old name
- Deletes orphaned source `customers` row

## Vendor Customers

Vendors (suppliers, payment processors, etc.) are stored in the `customers` table with
a `vendor` role in `customer_roles`.

**Key columns:**
- `company_name` VARCHAR(200) — single-name field for vendors/companies (migration-added).
  Display logic: `COALESCE(NULLIF(company_name,''), NULLIF(TRIM(first_name||' '||last_name),''))`.
  Backend stores vendor name in `company_name` + `last_name`; `first_name=''`.

**API endpoints:**
- `GET  /api/accounting/customers` — all customers, returns `display_name` (prefers company_name)
- `GET  /api/accounting/vendors` — customers with `vendor` role, returns `display_name`
- `POST /api/accounting/vendors` — create vendor; body: `{name}`. Creates customer row +
  assigns vendor role. Idempotent (adds role if customer already exists by name).

**Vendor typeahead in accounting modals:**
- All vendors shown at top of dropdown when field is focused (empty) — discoverable without typing
- Type to filter from all customers/vendors
- "＋ New Vendor" option always visible at bottom of dropdown; opens New Vendor modal
- After save, new vendor is immediately selected in the form
- Vendors appear with amber chip color (vs. green for non-vendor customers)
- Applies to: income/ledger modal (`#customer-id`), expense modal (`#exp-customer-id`)

## Customer Status and Role Editing (Info Tab)

Admins can edit a customer's **Member Status** and **Roles** from the Info tab
on any customer profile (all three rendering paths: inline expand, detail panel, mobile card).

**Member Status dropdown options:**
`1ST TIMER` / `GUEST` / `MEMBER` / `MEMBER+` / `FORMER`
- `member_plus` — new status (migration-adds to CHECK constraint); displayed as "MEMBER+"
- `expired_member` kept in DB for backward compat; displayed as "FORMER"

**Roles checkboxes:** `golfer`, `manager`, `admin`, `vendor`, `course_contact`, `sponsor`

> **Renamed:** the old `member` role string was renamed to `golfer` (lowercase, in
> `customer_roles.role_type`) because it collided conceptually with the `MEMBER`
> player_status display label, making code and conversation ambiguous. Migration
> `_migrate_rename_member_role_to_golfer` recreates the `customer_roles` table with the
> new CHECK and maps existing `member` rows to `golfer`. Idempotent (detects whether the
> migration already ran by inspecting the stored CREATE TABLE SQL). All `player_status`
> values (`MEMBER`, `MEMBER+`, `1ST TIMER`, `GUEST`, `FORMER`, `active_member`,
> `expired_member`, `MANAGER`) and `membership` item names are unchanged.
> Frontend constants updated: `ELEVATED` and `ALL_ROLES` arrays in customers.html, the
> four `hasRole(...)` guards in events.html's user_status validator, and the
> `valid_roles` set in `/api/replace-customer-roles`.

**Save flow:**
1. `PATCH /api/customers/<id>` — updates `current_player_status` via `update_customer_info()`
2. `POST /api/customers/sync-roles` — `{customer_id, roles[]}` replaces all roles atomically

**API:**
- `GET  /api/customer-roles` — returns roles per customer + `_by_name` map (name→customer_id);
  frontend uses `_by_name` as fallback when `items.customer_id` is null (pre-identity items).
  Per-customer dict also includes `current_player_status`, `first_timer_ever`, and `chapter`
  (read from the customers master record). The frontend overlays these onto each customer
  object, so the Customers page reads chapter authoritatively from the customers table
  rather than the items-derived `deriveChapter` fallback.
- `POST /api/customers/sync-roles` — `{customer_id, roles}` replaces full role set

## Status Derivation (`deriveStatus`)

`deriveStatus(items, roles, currentPlayerStatus)` (customers.html) returns one of
`MEMBER` / `MEMBER+` / `1st TIMER` / `FORMER` / `GUEST`. Precedence (most authoritative
first):

1. **Elevated role** — `owner` / `admin` / `manager` / `member` in `roles` → `MEMBER`.
2. **Membership purchase** — any item whose `item_name` contains `membership` (case-insensitive)
   → `MEMBER`. Hoisted above `current_player_status` so a customer who just bought a
   membership reads as `MEMBER` even before the stored status is updated.
3. **`current_player_status`**:
   - `active_member` → `MEMBER`
   - `member_plus` → `MEMBER+`
   - `first_timer` → `1st TIMER` **only if `items.length ≤ 1`**; otherwise demoted to `GUEST`
     (a customer flagged first-timer who has played more than once is no longer a first-timer).
   - `expired_member` / `inactive` → `FORMER`
   - `active_guest` → `GUEST`
4. **Items-based fallbacks** — membership in item name; `user_status === MEMBER`;
   `returning_or_new` containing "new"/"1st"/"first" (also capped at `items.length ≤ 1`);
   `NON-MEMBER` / `GUEST` user_status; default `GUEST`.

`c.status` is recomputed after the `/api/customer-roles` fetch resolves, so the badge
reflects the final (roles + player_status) view rather than the items-only first pass.

**Backend autocorrect** (`_migrate_autocorrect_player_status` in `email_parser/database.py`,
runs at `init_db`): mirrors the frontend rules into the database itself.
- Pass 1 — anyone with a `membership` item still flagged `first_timer` / `active_guest` /
  NULL → upgraded to `active_member`.
- Pass 2 — anyone still flagged `first_timer` with more than one item → demoted to
  `active_guest`.

`customer_roles` is intentionally not modified by the autocorrect; only the soft
`current_player_status` flag is flipped.

## Surname Uppercase for Elevated Roles (Events + Transactions only)

`displayName(name, status)` (in events.html and dashboard.js — **not** customers.html)
renders the surname in UPPERCASE when `status` is one of `MEMBER` / `MEMBER+` /
`MANAGER` / `OWNER` (case-insensitive). Render-only decoration; the underlying data
(`items.customer`, `customers.first_name` / `last_name`) stays in proper case. The
Customers page itself does **not** apply this decoration — surnames render in
proper case there to match the source-of-truth view.

For Not-Playing rows (which have no per-item `user_status`), `get_rsvps_for_event`
and `get_all_rsvps_bulk` surface `customer_status` (derived from
`customers.current_player_status` + `customer_roles`) on each rsvp dict so the
renderer can apply the uppercase decoration consistently.

## Chapter Selection (Info Tab)

The Chapter field on the Info tab and the Add-Customer modal is a constrained
`<select>` populated from `/api/chapters` (the canonical chapters dim table — five
entries: San Antonio, Austin, DFW, Houston, Hill Country). Legacy values that
don't match a canonical chapter are preserved as a "(legacy)" option until an
admin picks a canonical one.

**Save flow:** the Save handler reads the selected chapter from `.cust-edit-input`
(class works for both `<input>` and `<select>`). `update_customer_info` writes
the chapter string to:
- `items.chapter` for every items row matching the customer (denormalized cache).
- `customers.chapter` (master record).

The customers table is the authoritative source. `/api/customer-roles` returns
`chapter` per customer, and the Customers page overlays it onto each customer
object after the fetch resolves.

**Note:** `customers.chapter` is still a `VARCHAR(50)` text column. `items.chapter_id`
and `events.chapter_id` are FKs to `chapters.chapter_id`, but `customers` does not
yet have a `chapter_id` column. Adding the FK to `customers` is deferred — see
`docs/claude/schema.md → Deferred / Known Concessions`.

## Customers Page List — Activity Year Filter

The Customers list has an **Activity** dropdown (`This Year` default, `Last Year`,
`All Years`) next to the Active/Archived filter. With `This Year` selected, the
list filters to customers who have at least one **real purchase** in the target
year — defined as an item whose `order_date` starts with the year, whose
`transaction_status` is not `rsvp_only` / `gg_rsvp`, and whose `merchant` is
not in `PLACEHOLDER_MERCHANTS`:

```
Roster Import / Customer Entry / RSVP Import / RSVP Email Link
```

Roster Import items also do not appear in the customer-detail Transactions tab.

## Customers Page List — Credit-Balance Filter

A second dropdown (**All Credits / With Credit / No Credit**) sits next to the existing
filters so admins can quickly isolate players carrying a credit balance — the same
balance surfaced by the orange "$X.XX CREDIT" badge next to the customer name. Cents are
shown via `toLocaleString({min: 2, max: 2})` so a $0.19 overpayment credit reads as
"$0.19 Credit" instead of "$0 Credit". `totalSpent` formatting stays whole-dollar.

## Customers Page — Row Tinting by Status

Each customer row (desktop table + mobile card) gets a status-based class:
- `cust-row-member` — mint green (`#d1fae5`)
- `cust-row-member-plus` — teal (`#99f6e4`)
- `cust-row-first-timer` — amber (`#fde68a`)
- `cust-row-former` — slate gray (`#e2e8f0`, muted text)
- `cust-row-guest` — white (default)

`statusRowClass(status)` maps `c.status` to the class. Hover deepens the tint
one shade. Mobile cards add a 4px left border in a deeper shade for accent.

## Members Stat Card

The "Members" stat card always reflects all-time member counts (does not respect
the Activity-Year filter). Counts `c.status === "MEMBER" || c.status === "MEMBER+"`.
A per-chapter breakdown renders beneath the count, sorted by chapter size desc
then alphabetically.

# Customers Page — Key Behaviors

## Name display format
- All customer/player names display as **"Last, First"** across all pages
- `displayName()` helper converts "First Last" → "Last, First" with suffix handling
- Suffixes (Jr, Sr, II, III, IV, V) are preserved after the first name
- Example: "Victor Arias III" → "Arias, Victor III"
- The underlying data (`items.customer`) remains "First Last" — only display changes

## Name sorting
- `lastNameSortKey()` sorts by last name, stripping suffixes before comparison
- Used on all pages: Transactions, Events, Customers, Handicaps, RSVP Log
- "Victor Arias III" and "Victor Arias JR" sort together under "Arias"

## Merge customer modal
- Uses typeahead autocomplete input (not a dropdown)
- Type to search, click to select from suggestions
- Candidates sorted by last name with purchase counts

## "Purchased by" badge
- When `item.notes` contains "Purchased by X", a blue badge shows on the transaction row
- Indicates someone else paid for this player's registration

## Click-to-navigate
- Transaction rows in customer detail have `data-txn-id` and are clickable
- Clicking navigates to `/?txn=<id>` which deep-links to the Transactions tab

# Customers Page — Tab System

## Three rendering paths (IMPORTANT)
The Customers page has 3 separate rendering paths that must be kept in sync:
1. **Inline expanded card** (desktop list view, click to expand) — ~line 1150 in customers.html
2. **Detail panel** (`selectCustomer()`, used in Cards view) — ~line 1674
3. **Mobile card view** (responsive layout) — ~line 663

## Five tabs on all views
Each rendering path has 5 tabs: **Transactions**, **Scores**, **Winnings**, **Points**, **Info**

- **Transactions** — customer's purchase history with click-to-navigate to `/` page
- **Scores** — handicap data loaded via `/api/handicaps/players`, shows index + round history
- **Winnings** — TGF payout history loaded via `/api/customers/winnings`
- **Points** — placeholder for future points system
- **Info** — customer metadata (email, phone, chapter, GHIN, status)

## Customer winnings API
- `GET /api/customers/winnings?customer_name=<name>` — returns payout history
- `get_customer_winnings()` uses multi-step name matching:
  exact → case-insensitive → alias → name reversal
- Returns `{golfer_name, total_winnings, payouts: [{event_name, date, category, amount}]}`

## Customer detail Transactions tab — display columns

The Customer detail Transactions tab renders the same `displaySideGames` / `displayItemNotes`
helpers as the Transactions page:

- `displaySideGames(item)` only renders `NET / GROSS / BOTH / NONE`. Anything else
  collapses to an em-dash so free-form text doesn't pollute the Side Games column.
- `displayItemNotes(item)` joins `item.notes` (with internal markers like
  `[venmo-bd-exp:N]` and `[xfer-consumed:N]` stripped) with any non-canonical
  `side_games` text, separated by ` — `. Notes truncate to `14rem` with overflow
  ellipsis + `title=` tooltip for the full text.

Other columns in this tab:
- **Account** — derived from merchant: `The Golf Fellowship` → GoDaddy,
  `Manual Entry (Venmo)` → Venmo, `Manual Entry` → Manual,
  `Paid Separately ...` → Credit Transfer, RSVP/Roster/Customer Entry variants → labeled.
- **Total / Fees** — `total_amount` with `transaction_fees` in muted grey.
- **Multi-item order hint** — when an `order_id` is shared across rows, the Item cell
  shows a small italic `<N>-item order <id>` subtitle. Single-item orders show
  `order_id` in light grey.
- **From-transfer indicator** — same circular navy `T` badge used on Events
  (replaces the older "From Transfer" pill).
- **Coupon C-badge** — purple `.coupon-badge` on items with `coupon_code` or
  `coupon_amount` set.

**Reverse hidden on credit-pool rows.** New JS helper `isCreditPoolRow(row)` detects
credit-pool rows by `email_uid` prefix (`credit-excess-` / `overpayment-credit-`) and
hides Reverse on them across every render site (desktop INACTIVE chip, mobile chip,
desktop Players-tab actions dropdown, mobile player-row, customer detail Transactions
tab). Reverse on these rows previously flipped `transaction_status` from `credited` to
`active` and cleared `credit_note`, leaving a phantom active registration on the event.
To unwind a credit-pool row, reverse the parent credit-transfer instead —
`reverse_credit_application` already deletes excess + overpayment children.

## Storage migration: non-canonical side_games → notes

Pairs with the display helper above. `_migrate_move_noncanonical_side_games_to_notes`
runs at startup once: any `items` row where `side_games` is non-empty and not in
`{NET, GROSS, BOTH, NONE}` has the text appended to `notes` (with `' — '` separator if
notes already had content, skipping if the exact text is already in notes), then
`side_games` is cleared. Idempotent.

## Canonical customer data API
- `GET /api/customers` — returns all customers from canonical tables
- `get_all_customers()` — `SELECT FROM customers LEFT JOIN customer_emails WHERE is_primary=1`
  returns `customer_id`, `first_name`, `last_name`, `customer_name` (display), `phone`,
  `primary_email`, `email_label`, and other customer fields
- Customers page `init()` overlays this data after building the items-based map, ensuring
  email and phone always reflect canonical values rather than stale transaction copies
