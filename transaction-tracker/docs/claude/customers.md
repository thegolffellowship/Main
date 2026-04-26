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
  frontend uses `_by_name` as fallback when `items.customer_id` is null (pre-identity items)
- `POST /api/customers/sync-roles` — `{customer_id, roles}` replaces full role set

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
