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

## Customer Resolution (`_resolve_or_create_customer`)
- Calls `_lookup_customer_id` first
- If no match, creates a new `customers` row + `customer_emails` row
- On email IntegrityError (duplicate), returns the existing owner's customer_id instead of creating an orphan

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

**Roles checkboxes:** `member`, `manager`, `admin`, `vendor`, `course_contact`, `sponsor`

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

## Canonical customer data API
- `GET /api/customers` — returns all customers from canonical tables
- `get_all_customers()` — `SELECT FROM customers LEFT JOIN customer_emails WHERE is_primary=1`
  returns `customer_id`, `first_name`, `last_name`, `customer_name` (display), `phone`,
  `primary_email`, `email_label`, and other customer fields
- Customers page `init()` overlays this data after building the items-based map, ensuring
  email and phone always reflect canonical values rather than stale transaction copies
