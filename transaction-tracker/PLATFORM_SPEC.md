# TGF Transaction Tracker — Platform Specification

## Overview

A Flask + SQLite web application that scans email inboxes (via Microsoft Graph API) for golf event transaction/receipt emails, uses Claude AI to extract structured purchase data, and serves an interactive dashboard for managing transactions, events, and customers.

**Stack:** Python/Flask, SQLite (WAL mode), vanilla JavaScript, APScheduler, Anthropic Claude API, Microsoft Graph API.

---

## File Structure

```
transaction-tracker/
├── app.py                        # Flask app, all routes, scheduler, webhook
├── asgi_app.py                   # ASGI wrapper for Railway deployment
├── mcp_server.py                 # MCP server (21 tools for Claude integration)
├── mcp_auth.py                   # MCP OAuth 2.0 authentication
├── mcp_server_remote.py          # Remote MCP via SSE
├── golf_genius_sync.py           # Golf Genius handicap sync via HTTP
├── migrate_customers.py          # Customer migration script
├── seed_sa_events.py             # Script to seed San Antonio events
├── test_parser.py                # Parser unit tests
├── requirements.txt
├── .env / .env.example
├── transactions.db               # SQLite database
├── email_parser/
│   ├── __init__.py
│   ├── parser.py                 # Claude AI email extraction
│   ├── fetcher.py                # Microsoft Graph email fetching
│   ├── database.py               # SQLite storage & queries (~3500 lines)
│   ├── report.py                 # Daily digest email sender
│   └── rsvp_parser.py            # Golf Genius RSVP email parsing
├── templates/
│   ├── index.html                # Main transactions dashboard
│   ├── events.html               # Events management + Tee Time Advisor
│   ├── customers.html            # Customer directory + roster import
│   ├── audit.html                # Email audit/QA page (admin)
│   ├── rsvps.html                # RSVP management
│   ├── matrix.html               # Side games prize matrix
│   ├── handicaps.html            # Handicap management (manager)
│   ├── database.html             # Admin database browser
│   └── changelog.html            # Version changelog
└── static/
    ├── js/
    │   ├── auth.js               # PIN-based auth + sticky nav offsets
    │   ├── dashboard.js          # Main dashboard interactivity
    │   ├── games-matrix.js       # Prize matrix data (9h & 18h, 2-64 players)
    │   ├── chat-widget.js        # Support/feedback chat widget
    │   └── version.js            # Version number & update detection
    └── css/
        └── dashboard.css         # All styling (single file)
```

---

## Database Schema (SQLite)

### `items` table (main transaction data)

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| email_uid | TEXT NOT NULL | Unique email identifier |
| item_index | INTEGER DEFAULT 0 | Position in multi-item order |
| merchant | TEXT NOT NULL | e.g. "The Golf Fellowship" |
| customer | TEXT | Buyer name (Title Case) |
| first_name | TEXT | Parsed first name (AI-extracted) |
| last_name | TEXT | Parsed last name |
| middle_name | TEXT | Parsed middle name/initial |
| suffix | TEXT | e.g. Jr., III |
| customer_email | TEXT | |
| customer_phone | TEXT | |
| order_id | TEXT | Confirmation number |
| order_date | TEXT NOT NULL | ISO date |
| order_time | TEXT | Time of order (HH:MM) |
| total_amount | TEXT | Full order value |
| transaction_fees | TEXT | Processing fees |
| item_name | TEXT NOT NULL | Event/product name |
| event_date | TEXT | Date of golf event |
| item_price | TEXT | e.g. "$158.00" |
| quantity | INTEGER DEFAULT 1 | |
| city | TEXT | Event city |
| chapter | TEXT | Chapter (San Antonio / Austin) |
| course | TEXT | Golf course (canonical name) |
| handicap | TEXT | |
| has_handicap | TEXT | YES/NO flag |
| side_games | TEXT | NET/GROSS/BOTH/NONE |
| tee_choice | TEXT | <50/50-64/65+/Forward |
| member_status | TEXT | MEMBER/NON-MEMBER |
| post_game | TEXT | Post-game fellowship |
| returning_or_new | TEXT | |
| partner_request | TEXT | Preferred playing partner |
| fellowship_after | TEXT | Post-game fellowship selection |
| notes | TEXT | General notes from registration |
| shirt_size | TEXT | |
| guest_name | TEXT | |
| date_of_birth | TEXT | |
| net_points_race | TEXT | |
| gross_points_race | TEXT | |
| city_match_play | TEXT | |
| subject | TEXT | Original email subject |
| from_addr | TEXT | Original sender |
| transaction_status | TEXT DEFAULT 'active' | active/credited/transferred/wd |
| credit_note | TEXT | Reason for credit/transfer |
| transferred_from_id | INTEGER | FK to originating item |
| transferred_to_id | INTEGER | FK to destination item |
| wd_reason | TEXT | Withdrawal reason |
| wd_note | TEXT | Withdrawal note |
| wd_credits | TEXT | Credit policy applied |
| credit_amount | TEXT | Dollar amount credited on WD |
| created_at | TEXT DEFAULT datetime('now') | |

**Constraint:** UNIQUE(email_uid, item_index)
**Indexes:** order_date DESC, item_name, customer, transaction_status

### `events` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| item_name | TEXT NOT NULL UNIQUE | Matches items.item_name |
| event_date | TEXT | |
| course | TEXT | |
| chapter | TEXT | Chapter (San Antonio / Austin) — renamed from `city` |
| format | TEXT | 9 Holes / 18 Holes / 9/18 Combo |
| start_type | TEXT | Tee Times / Shotgun (or 9-hole start type in combo) |
| start_time | TEXT | Start time (HH:MM) or 9-hole start time in combo |
| tee_time_count | INTEGER | Number of tee time slots (or 9-hole count in combo) |
| tee_time_interval | INTEGER | Minutes between tee times |
| start_time_18 | TEXT | 18-hole start time (combo mode only) |
| start_type_18 | TEXT | 18-hole start type (combo mode only) |
| tee_time_count_18 | INTEGER | 18-hole tee time count (combo mode only) |
| tee_direction | TEXT DEFAULT 'First Tee' | Tee time direction: First Tee / Last Tee |
| tee_direction_18 | TEXT DEFAULT 'First Tee' | 18-hole tee direction (combo mode) |
| course_cost | REAL | Course/vendor cost per player (rounds up to nearest dollar) |
| tgf_markup | REAL | TGF markup per player — Member rate (Guest/1st Timer derived) |
| side_game_fee | REAL | Included games admin fee ("Inc. Games") — part of base Event Only price |
| transaction_fee_pct | REAL DEFAULT 3.5 | Transaction processing fee percentage |
| event_type | TEXT DEFAULT 'event' | |
| created_at | TEXT | |

### `rsvps` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| email_uid | TEXT NOT NULL UNIQUE | Golf Genius confirmation email ID |
| player_name | TEXT | Player name from RSVP |
| player_email | TEXT | Player email |
| gg_event_name | TEXT | Golf Genius event name |
| event_identifier | TEXT | Normalized event identifier |
| event_date | TEXT | |
| response | TEXT NOT NULL | YES/NO |
| received_at | TEXT | Email timestamp |
| matched_event | TEXT | Matched TGF event name |
| matched_item_id | INTEGER | FK to items.id if linked |
| created_at | TEXT | |

**Indexes:** matched_event, player_email

### `rsvp_overrides` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| item_id | INTEGER NOT NULL | FK to items.id |
| event_name | TEXT NOT NULL | |
| status | TEXT DEFAULT 'none' | Override status |
| updated_at | TEXT | |

**Constraint:** UNIQUE(item_id, event_name)

### `rsvp_email_overrides` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| player_email | TEXT NOT NULL | For GG RSVP players without item row |
| event_name | TEXT NOT NULL | |
| status | TEXT DEFAULT 'none' | |
| updated_at | TEXT | |

**Constraint:** UNIQUE(player_email, event_name)

### `customer_aliases` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| customer_name | TEXT NOT NULL | Canonical customer name |
| alias_type | TEXT NOT NULL | 'name' or 'email' |
| alias_value | TEXT NOT NULL | Alternative name or email |
| created_at | TEXT | |

### `event_aliases` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| alias_name | TEXT NOT NULL UNIQUE | Old/variant event name |
| canonical_event_name | TEXT NOT NULL | Current canonical name |
| created_at | TEXT | |

**Index:** canonical_event_name

### `message_templates` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| name | TEXT NOT NULL | Template name |
| channel | TEXT DEFAULT 'email' | email/sms/both |
| subject | TEXT | Email subject line |
| html_body | TEXT | HTML email body |
| sms_body | TEXT | SMS message text |
| is_system | INTEGER DEFAULT 0 | 1 = built-in template |
| created_at | TEXT | |
| updated_at | TEXT | |

### `message_log` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| event_name | TEXT | Event context |
| template_id | INTEGER | FK to message_templates.id |
| channel | TEXT NOT NULL | email/sms |
| recipient_name | TEXT | |
| recipient_address | TEXT NOT NULL | Email or phone |
| subject | TEXT | |
| body_preview | TEXT | Truncated body |
| status | TEXT DEFAULT 'sent' | sent/failed |
| error_message | TEXT | Error details if failed |
| sent_by | TEXT | admin/manager role |
| sent_at | TEXT | |

**Indexes:** event_name, sent_at DESC

### `feedback` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| type | TEXT NOT NULL | 'bug' or 'feature' |
| message | TEXT NOT NULL | |
| page | TEXT | Page submitted from |
| role | TEXT | admin/manager |
| status | TEXT DEFAULT 'open' | open/resolved/dismissed |
| created_at | TEXT | |

### `handicap_rounds` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| player_name | TEXT NOT NULL | Normalised `First Last` title case |
| round_date | TEXT NOT NULL | YYYY-MM-DD |
| round_id | TEXT | Golf Genius / Handicap Server round identifier |
| course_name | TEXT | |
| tee_name | TEXT | e.g. `1 - White`, `2 - Gold` |
| adjusted_score | INTEGER NOT NULL | |
| rating | REAL NOT NULL | Course rating |
| slope | INTEGER NOT NULL | Slope rating |
| differential | REAL | Computed on import if not provided |
| created_at | TEXT | |

### `handicap_player_links` table

| Column | Type | Notes |
|--------|------|-------|
| player_name | TEXT PK | Normalised player name |
| customer_name | TEXT | Matched customer (nullable) |
| linked_at | TEXT | |

### `handicap_settings` table

| Column | Type | Notes |
|--------|------|-------|
| key | TEXT PK | `min_rounds` or `multiplier` |
| value | TEXT NOT NULL | |
| updated_at | TEXT | |

### `customers` table

| Column | Type | Notes |
|--------|------|-------|
| customer_id | TEXT PK | UUID-style identifier |
| platform_user_id | TEXT | External platform ID |
| first_name | TEXT | |
| last_name | TEXT | |
| phone | TEXT | |
| chapter | TEXT | |
| ghin_number | TEXT | |
| current_player_status | TEXT | active_member/expired_member/active_guest/inactive/first_timer |
| first_timer_ever | INTEGER | |
| acquisition_source | TEXT | |
| account_status | TEXT | active/inactive/banned |
| created_at | TEXT | |
| updated_at | TEXT | |

### `customer_emails` table

| Column | Type | Notes |
|--------|------|-------|
| email_id | TEXT PK | |
| customer_id | TEXT NOT NULL | FK to customers (CASCADE) |
| email | TEXT NOT NULL | |
| is_primary | INTEGER DEFAULT 0 | |
| is_golf_genius | INTEGER DEFAULT 0 | |
| label | TEXT | |
| created_at | TEXT | |

### `app_settings` table

| Column | Type | Notes |
|--------|------|-------|
| key | TEXT PK | e.g. `matrix_9h`, `matrix_18h` |
| value | TEXT NOT NULL | JSON or string |
| updated_at | TEXT | |

### `season_contests` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| customer_name | TEXT NOT NULL | |
| contest_type | TEXT NOT NULL | net_points_race/gross_points_race/city_match_play |
| chapter | TEXT | |
| season | TEXT | |
| source_item_id | INTEGER | FK to items.id |
| enrolled_at | TEXT | |

### `parse_warnings` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| email_uid | TEXT | |
| order_id | TEXT | |
| customer | TEXT | |
| item_name | TEXT | |
| warning_code | TEXT | |
| message | TEXT | |
| status | TEXT | open/dismissed/resolved |
| created_at | TEXT | |

---

## API Endpoints

### Page Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Transactions dashboard |
| `/events` | GET | Events management + Tee Time Advisor |
| `/customers` | GET | Customer directory + history |
| `/audit` | GET | Email audit/QA page (admin) |
| `/rsvps` | GET | RSVP management page |
| `/matrix` | GET | Side games prize matrix |
| `/handicaps` | GET | 9-hole WHS handicap calculator (manager) |
| `/database` | GET | Admin database browser |
| `/changelog` | GET | Version changelog |

### Items / Transactions

| Endpoint | Method | Auth | Body / Params | Response |
|----------|--------|------|---------------|----------|
| `/api/items` | GET | — | — | `[{id, customer, item_name, ...}]` |
| `/api/items/<id>` | PATCH | — | `{field: value}` | `{status: "ok"}` |
| `/api/items/<id>` | DELETE | admin | — | `{status: "ok"}` |
| `/api/stats` | GET | — | — | `{total_items, total_orders, total_spent, ...}` |
| `/api/audit` | GET | — | — | `{fill_rates, problems, distributions}` |

### Credit / Transfer / Withdrawal

| Endpoint | Method | Body | Effect |
|----------|--------|------|--------|
| `/api/items/<id>/credit` | POST | `{note}` | Sets transaction_status='credited' |
| `/api/items/<id>/transfer` | POST | `{target_event, note}` | Marks original as 'transferred', creates new $0 item on target event |
| `/api/items/<id>/reverse-credit` | POST | — | Reverts credit/transfer back to 'active' |
| `/api/items/<id>/wd` | POST | `{reason, note, credits, credit_amount}` | Marks as withdrawn with optional partial credit |

### Events

| Endpoint | Method | Auth | Body | Response |
|----------|--------|------|------|----------|
| `/api/events` | GET | — | — | `[{id, item_name, event_date, course, chapter, format, start_type, start_time, ..., registrations}]` |
| `/api/events` | POST | — | `{item_name, event_date, course, chapter, format, start_type, start_time, ...}` | `{event}` |
| `/api/events/<id>` | PATCH | — | `{field: value}` | `{status: "ok"}` |
| `/api/events/<id>` | DELETE | admin | — | `{status: "ok"}` |
| `/api/events/sync` | POST | — | — | Auto-creates events from item_name patterns |
| `/api/events/add-player` | POST | — | `{event_name, customer, ...}` | Creates manual registration item |
| `/api/events/delete-manual-player/<id>` | DELETE | admin | — | Remove manually-added player |
| `/api/events/merge` | POST | — | `{source_id, target_id}` | Merge two events (creates alias) |
| `/api/events/orphaned-items` | GET | — | — | Items not linked to any event |
| `/api/events/resolve-orphan` | POST | — | `{item_id, event_name}` | Link orphaned item to event |
| `/api/events/upgrade-rsvp` | POST | — | `{item_id, event_name}` | Convert RSVP placeholder to paid |
| `/api/events/send-reminder` | POST | — | `{player_name, player_email, event_name}` | Email payment reminder |
| `/api/events/send-reminder-all` | POST | — | `{event_name}` | Bulk-send reminders to all RSVP-only |
| `/api/events/seed` | POST | — | `[{item_name, event_date, ...}]` | Batch-create events from JSON |

### Customers

| Endpoint | Method | Auth | Body | Response |
|----------|--------|------|------|----------|
| `/api/customers` | GET | — | — | Derived customer list with status, chapter, history |
| `/api/customers/create` | POST | — | `{name, email, phone, ...}` | Create new customer |
| `/api/customers/update` | POST | — | `{name, fields...}` | Update customer fields |
| `/api/customers/merge` | POST | — | `{source, target}` | Merge two customer records |
| `/api/customers/aliases` | GET/POST | — | `{customer_name, alias_type, alias_value}` | Get/add customer aliases |
| `/api/customers/aliases/<id>` | DELETE | — | — | Delete alias |
| `/api/customers/from-rsvp` | POST | — | `{player_name, player_email, event_name}` | Create customer from RSVP data |
| `/api/customers/link-rsvp` | POST | — | `{rsvp_id, customer_name}` | Link RSVP to existing customer |
| `/api/customers/parse-roster` | POST | — | Excel file upload | Parse Excel roster columns |
| `/api/customers/preview-roster` | POST | — | `{rows, column_map}` | Preview import with AI name parsing |
| `/api/customers/import-roster` | POST | — | `{rows, column_map, options}` | Bulk import roster data |

### Messaging

| Endpoint | Method | Auth | Body | Response |
|----------|--------|------|------|----------|
| `/api/messages/templates` | GET | — | — | All message templates |
| `/api/messages/templates` | POST | — | `{name, channel, subject, html_body, sms_body}` | Create template |
| `/api/messages/templates` | PATCH | — | `{id, fields...}` | Update template |
| `/api/messages/templates` | DELETE | admin | `{id}` | Delete template |
| `/api/messages/send` | POST | — | `{event_name, template_id, recipients, ...}` | Send bulk messages |
| `/api/messages/preview` | POST | — | `{template_id, player_name, event_name}` | Preview rendered message |
| `/api/messages/log` | GET | — | — | All sent messages |
| `/api/messages/log/<event_name>` | GET | — | — | Messages for specific event |

### RSVPs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rsvps` | GET | All RSVPs with filters |
| `/api/rsvps/event/<name>` | GET | RSVPs for specific event |
| `/api/rsvps/bulk` | GET | Bulk fetch RSVPs for multiple events |
| `/api/rsvps/stats` | GET | RSVP summary statistics |
| `/api/rsvps/check-now` | POST | Manual RSVP inbox check |
| `/api/rsvps/rematch` | POST | Re-run matching on unmatched RSVPs |
| `/api/rsvps/<id>/match` | POST | Manually match RSVP to event |
| `/api/rsvps/<id>/unmatch` | POST | Unmatch RSVP |
| `/api/rsvps/overrides` | GET/POST | Get/set RSVP overrides |
| `/api/rsvps/config-status` | GET | Check RSVP credentials |

### Support & Feedback

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/support/chat` | POST | Support chat endpoint |
| `/api/support/feedback` | GET/POST | Get all or submit feedback |
| `/api/support/feedback` | PATCH | Update feedback status |

### Inbox & Parsing

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/check-now` | POST | Starts background inbox scan + AI parse |
| `/api/check-status` | GET | Returns `{status, progress, stats}` for polling |
| `/api/config-status` | GET | Shows which integrations are configured |

### Connector / Webhook

| Endpoint | Method | Auth | Body |
|----------|--------|------|------|
| `/api/connector/ingest` | POST | X-API-Key header | `{items: [...]}` or `{raw_email: {uid, subject, from, text}}` |

### Auth

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/api/auth/login` | POST | `{pin}` | `{role: "admin"/"manager"}` |
| `/api/auth/role` | GET | — | `{role}` |
| `/api/auth/logout` | POST | — | `{status: "ok"}` |

### Audit (admin)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/audit/emails` | GET | Compares parsed data vs raw emails |
| `/api/audit/autofix-side-games` | POST | Fixes misplaced side_games data |
| `/api/audit/autofix-all` | POST | Normalizes names, courses, side_games, item_names |
| `/api/audit/autofix-tee-choices` | POST | Standardizes tee_choice values |
| `/api/audit/re-extract-fields` | POST | Re-extract fields from original email. Backfills: address, city, state, zip, transaction_fees, partner_request, fellowship, notes, holes. Overwrites: item_name |

### Reports

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/report/send-now` | POST | Sends daily summary email immediately |

### Sunset / Tee Time Advisor

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sunset` | GET | Proxy to Sunrise-Sunset.org API. Params: `date` (YYYY-MM-DD), `chapter` (San Antonio/Austin). Returns sunset time, civil twilight end, and 24h equivalents. DST-aware via pytz. |

---

## Authentication

- **PIN-based**, optional. Two roles: `admin` (full access + delete + audit) and `manager` (read/edit only).
- Flask session cookie stores role. PINs compared with `secrets.compare_digest()`.
- `@require_role("admin")` decorator on protected endpoints.
- Dashboard is viewable without auth; destructive actions and audit require login.

---

## Email Parsing Pipeline

1. **Fetch** — Microsoft Graph API (Azure AD OAuth client credentials) reads inbox, filters by sender domain and subject keywords for transaction-like emails.
2. **Parse** — Each email body sent to Claude AI (`claude-sonnet-4-5-20250929`, max 2048 tokens) with extraction prompt. Returns structured JSON with all item fields.
3. **Normalize** — Title Case names, canonical course names, side_games/golf_or_compete split, tee choice standardization.
4. **Store** — Upsert into SQLite; dedup by (email_uid, item_index).
5. **Schedule** — APScheduler runs inbox check every 15 min (configurable) and daily report at 7 AM.

### Key Parsing Rules

- Customer names: Title Case, special handling for Mc/Mac/O' prefixes
- Item names: Memberships normalized to "TGF MEMBERSHIP"; event names include full venue (e.g. "Austin Kickoff SHADOWGLEN")
- Side games + golf_or_compete are often combined in emails and must be split (e.g. "COMPETE + BOTH NET & GROSS" -> golf_or_compete="COMPETE", side_games="BOTH")
- Course names mapped to canonical spellings (La Cantera, TPC San Antonio, The Quarry, etc.)
- City inferred from course name

---

## Frontend Architecture

All pages use **vanilla JavaScript** (no frameworks). Each HTML template contains its own `<script>` block. Shared: `auth.js` (login modal + role badge), `dashboard.js` (main transactions page logic), `dashboard.css` (all styling).

### Common Patterns Across Pages

- Client-side search, filter, sort on fetched data
- Auto-refresh every 30 seconds (skipped if modal is open)
- Column visibility toggle with localStorage persistence
- Expandable inline detail rows (Events and Customers list view)
- Credit/Transfer modal with event picker
- CSV export
- `escapeHtml()` helper for XSS prevention
- `displayName()` helper formats "First Last" → "Last, First" with suffix handling for display
- `lastNameSortKey()` sorts by last name, stripping suffixes (Jr, III) so variants group together
- `parsePrice()` strips `$,` for numeric sorting
- Email addresses rendered as clickable `mailto:` links

### Page-Specific Notes

**Transactions** (`index.html` + `dashboard.js`): Most complex page. Column drag-to-reorder, inline cell editing via modal, category filter buttons (All/Upcoming/Past/Memberships), 24-column CSV export, "Check Now" button with real-time progress polling.

**Events** (`events.html`): Expandable rows showing registrants per event. Add Player modal. Sync Events button auto-detects events from transaction item names. Edit Event modal with GENERAL and PRICING tabs. GENERAL: format (9/18/Combo), start type (Tee Times/Shotgun — independent per group in combo mode), start time, tee time planning fields. PRICING: collapsible Course Cost Calculator (collapsed=green fees only, expands to 5 line items), Markup ($), Inc. Games ($), Transaction Fee (%). For combo events, calculators and pricing inputs displayed **side-by-side** (9-Hole Calculator green, 18-Hole Calculator blue). Each calculator card shows "Event Cost" total = ceil(courseCost) + markup + incGames. Live-updating pricing summary with colored cards for Member/Guest/1st Timer × Event Only/With One Game (+$16)/With Both Games (+$32). Guest = Member markup +$10 (9h/combo) or +$15 (18h standalone); 1st Timer = Guest −$25. Both Games N/A for Guest/1st Timer; combo 18-hole = Member only. **Tee Time Advisor** panel auto-populates when date + chapter are set: fetches sunset data via `/api/sunset`, shows last recommended tee times with traffic light indicators (green/yellow/red), and generates tee time sheets with per-slot finish estimates. Combo mode shows side-by-side tee sheets with independent start times, start types, and counts for 9-hole and 18-hole groups.

**Customers** (`customers.html`): List view with expandable inline detail rows (like Events). Card view with bottom detail panel. Derives status (MEMBER/GUEST/1st TIMER) and chapter (most frequent city) from transaction history. Email addresses are clickable mailto: links.

**Audit** (`audit.html`, admin only): Compares raw emails vs parsed data. Shows OK/Incomplete/Missing counts. Autofix buttons for batch corrections.

---

## Environment Variables

```
# Azure AD / Microsoft Graph
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
EMAIL_ADDRESS=your-email@yourdomain.com

# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...

# Connector/Webhook (optional)
CONNECTOR_API_KEY=...

# Daily Report (optional)
DAILY_REPORT_TO=report@yourdomain.com
DAILY_REPORT_HOUR=6
DAILY_REPORT_TZ=US/Central

# Feedback Notifications (optional)
FEEDBACK_NOTIFY_TO=admin@yourdomain.com    # Falls back to DAILY_REPORT_TO

# RSVP / Golf Genius (optional)
RSVP_EMAIL_ADDRESS=rsvp@yourdomain.com     # Mailbox for GG RSVP confirmations
RSVP_AZURE_TENANT_ID=...                   # Optional: separate Azure creds for RSVP mailbox
RSVP_AZURE_CLIENT_ID=...
RSVP_AZURE_CLIENT_SECRET=...

# MCP OAuth (optional, for Claude.ai connector)
MCP_CLIENT_ID=tgf-mcp-client
MCP_CLIENT_SECRET=your-alphanumeric-secret  # Alphanumeric only, no dashes

# App Settings
CHECK_INTERVAL_MINUTES=15
SECRET_KEY=random-string-here

# Authentication PINs (optional)
ADMIN_PIN=1234
MANAGER_PIN=0000

# Database Path (optional, for Railway volumes)
DATABASE_PATH=/data/transactions.db
```

---

## Deployment

- **Gunicorn:** `gunicorn app:app --bind 0.0.0.0:5000 --workers 2 --timeout 120`
- Supports Railway (railway.toml), Render/Heroku (Procfile), systemd, launchd
- SQLite DB needs persistent volume in cloud deployments

---

## Technical Debt & Known Concessions

This section documents architectural gaps and deliberate compromises made while
operating on SQLite. All items should be addressed when migrating to Supabase /
TGF Platform (PostgreSQL).

### SQLite Limitation: No Retroactive FK Constraints

**Problem:** SQLite's `ALTER TABLE ADD COLUMN` can declare a `REFERENCES` clause on the
new column, but it cannot add a foreign key constraint to an *existing* column — and it
cannot enforce any FK constraints without setting `PRAGMA foreign_keys = ON` per connection.

The app does not set this PRAGMA, so all `REFERENCES` clauses are documentation/intent only.
They are not enforced at the database layer.

**Full table rebuild** (create new table → copy → drop old → rename) is the only way to
retroactively add a FK constraint, but that risks data loss on a live production database.
We chose not to do this during the bridge phase.

**Concessions made:**

| Table | Column | Status | Notes |
|-------|--------|--------|-------|
| `items` | `customer_id` | No REFERENCES clause | Added pre-migration; app code maintains integrity |
| `items` | `parent_item_id` | No REFERENCES clause | Self-referential; app code enforces |
| `items` | `transferred_from_id` | No REFERENCES clause | Self-referential; app code enforces |
| `items` | `transferred_to_id` | No REFERENCES clause | Self-referential; app code enforces |
| `acct_transactions` | `customer_id` | No REFERENCES clause | Added pre-migration; backfilled via 5-step cascade |
| `handicap_player_links` | `customer_id` | No REFERENCES clause | Added pre-migration; backfilled at startup |
| `rsvps` | `customer_id` | REFERENCES clause added | New column — FK declared but not runtime-enforced |
| `customer_aliases` | `customer_id` | REFERENCES clause added | New column — FK declared but not runtime-enforced |
| `season_contests` | `customer_id` | REFERENCES clause added | New column — FK declared but not runtime-enforced |
| `handicap_rounds` | `customer_id` | REFERENCES clause added | New column — FK declared but not runtime-enforced |
| `godaddy_order_splits` | `customer_id` | REFERENCES clause added | New column — FK declared but not runtime-enforced |

**Fix at migration:** When creating the PostgreSQL schema, define all FK constraints
properly at table creation time and set `DEFERRABLE INITIALLY DEFERRED` where needed
for self-referential tables.

---

### Two Separate Event Universes: `tgf_events` vs `events`

**Problem:** The system has two completely separate event tables with no link between them:

- `events` — the main event registry (registrations, RSVPs, pricing, pairings, player data)
- `tgf_events` — tournament payout tracking (prize purses, TGF payout categories)

Both tables represent the same real-world events but have no shared key. Financial
reconciliation across both is impossible — you cannot join event revenue (from `events` +
`acct_transactions`) with prize payouts (from `tgf_events` + `tgf_payouts`) without
a string match on event names, which is fragile under renames.

**Status:** Bridge column `events_id INTEGER REFERENCES events(id)` to be added to
`tgf_events` with a backfill pass. Implementation pending (sequential commits).

---

### Event References via String Name (No Numeric FK)

**Problem:** Most tables reference events by copying the event name string at write time
rather than storing a numeric `event_id` FK. This means:
- Event renames break historical joins silently (the old string doesn't update)
- No referential integrity — a misspelled event name creates a dangling reference
- Aggregation queries must use `COLLATE NOCASE` and still miss variants

**Affected tables (event_id FK missing):**
`items` (`item_name`), `acct_allocations` (`event_name`), `godaddy_order_splits`
(`event_name`), `contractor_payouts` (`event_name`), `rsvps` (`matched_event`),
`expense_transactions` (`event_name`), `message_log` (`event_name`)

**Mitigation in place:** `event_aliases` table + `sync_events_from_items()` + deleted-name
alias preservation. Renames propagate via alias lookup in most read paths.

**Status:** Migration to add `event_id` FK columns + backfill pending (sequential commits).

---

### `items` Self-Referential FK Columns — Unenforced

`items.parent_item_id`, `transferred_from_id`, and `transferred_to_id` reference
other rows in the same `items` table. These columns exist and are populated correctly
by application code, but have no `REFERENCES items(id)` declaration (they predate the
migration strategy). Application code enforces the relationships, but the DB will not
catch a bad write.

**Fix at migration:** Declare these as `REFERENCES items(id)` with `ON DELETE SET NULL`
in PostgreSQL.

---

### No `PRAGMA foreign_keys = ON`

The app does not set `PRAGMA foreign_keys = ON` in its connection setup. Even columns
that have a `REFERENCES` clause will not trigger FK violations — invalid `customer_id`
values can be inserted without error.

**Fix at migration:** PostgreSQL enforces FK constraints by default. No PRAGMA needed.

---

### Migration Checklist for TGF Platform / Supabase

When migrating to PostgreSQL, address these items at schema creation time:

1. **All customer_id columns** — declare as `REFERENCES customers(customer_id) ON DELETE SET NULL`
2. **items self-referential columns** — `parent_item_id`, `transferred_from_id`,
   `transferred_to_id` → `REFERENCES items(id) ON DELETE SET NULL`
3. **event_id FK on all tables** — replace string event_name copies with a proper
   `event_id INTEGER REFERENCES events(id)` column; keep event_name as a denormalized
   display cache only
4. **tgf_events → events bridge** — add `events_id REFERENCES events(id)` and enforce
   that every tournament event maps to a main event record
5. **Enable FK enforcement** — PostgreSQL enforces by default; no special setting needed
6. **Add missing indexes** — `customer_id`, `event_id`, `order_id` columns on high-traffic
   tables currently lack indexes in SQLite (check with `EXPLAIN QUERY PLAN`)
7. **Replace COLLATE NOCASE** — PostgreSQL uses `ILIKE` and `citext` extension for
   case-insensitive string operations; audit all queries that use COLLATE NOCASE
8. **Row-level security** — Supabase supports RLS; design per-chapter data isolation
   at the DB layer rather than application layer
