# TGF Transaction Tracker — Project Documentation

> **The Golf Fellowship** — AI-powered transaction and event management platform
> **Current Version:** v1.3.0 (March 4, 2026)
> **Live URL:** https://tgf-tracker.up.railway.app

---

## Table of Contents

1. [What This App Does](#what-this-app-does)
2. [Tech Stack](#tech-stack)
3. [File Structure](#file-structure)
4. [Pages & Features](#pages--features)
5. [Database Schema](#database-schema)
6. [API Endpoints](#api-endpoints)
7. [Email Parsing Pipeline](#email-parsing-pipeline)
8. [RSVP Integration (Golf Genius)](#rsvp-integration-golf-genius)
9. [Side Games Matrix](#side-games-matrix)
10. [Authentication & Roles](#authentication--roles)
11. [MCP Server (Claude Integration)](#mcp-server-claude-integration)
12. [Scheduled Jobs](#scheduled-jobs)
13. [Environment Variables](#environment-variables)
14. [Deployment](#deployment)
15. [PWA / Mobile](#pwa--mobile)
16. [Version History](#version-history)
17. [Backlog / Roadmap](#backlog--roadmap)
18. [Tax Accounting](#tax-accounting)
19. [Order Grouping](#order-grouping)

---

## What This App Does

The TGF Transaction Tracker is a web application built for The Golf Fellowship that:

1. **Scans email inboxes** via Microsoft Graph API for transaction/receipt emails (from MySimpleStore, PayPal, Stripe, etc.)
2. **Parses emails with AI** (Claude Sonnet) to extract structured purchase data — customer names, event registrations, side game selections, tee choices, handicaps, membership info, etc.
3. **Displays everything in an interactive dashboard** with search, sort, filter, inline editing, CSV export, and category views
4. **Manages events** — auto-detects events from transaction data, tracks registration counts, supports manual player additions (comps, RSVP-only, paid separately)
5. **Tracks RSVPs** from Golf Genius — reads confirmation/cancellation emails and matches them to registered players
6. **Manages customers** — derives member status, chapter affiliation, purchase history, and contact info from transaction data
7. **Calculates side game prizes** — a full prize matrix for NET/GROSS/Skins games by player count (9-hole and 18-hole)
8. **Sends daily email reports** with transaction summaries
9. **Provides a webhook/connector** for external systems to push order data
10. **Offers an MCP server** so Claude (Desktop or Code) can directly query and modify the database

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, Flask |
| Database | SQLite (WAL mode) |
| Frontend | Vanilla JavaScript (no frameworks) |
| CSS | Single `dashboard.css` file, CSS custom properties |
| AI Parsing | Anthropic Claude API (`claude-sonnet-4-5-20250929`) |
| Email | Microsoft Graph API (Azure AD OAuth client credentials) |
| Scheduler | APScheduler (background) |
| ASGI | a2wsgi + Uvicorn (for MCP SSE support) |
| MCP | FastMCP (Model Context Protocol) |
| Hosting | Railway (Nixpacks build, Gunicorn + Uvicorn worker) |
| PWA | Web App Manifest, Apple standalone meta tags |

---

## File Structure

```
Main/
├── index.html                          # Landing/sign-in page (static, separate from tracker)
├── css/styles.css                      # Landing page styles
├── js/signin.js                        # Landing page JS
├── .mcp.json                           # MCP server config for Claude Code
│
└── transaction-tracker/                # Main application
    ├── app.py                          # Flask app — all routes, scheduler, webhook
    ├── asgi_app.py                     # ASGI wrapper (Flask + MCP on one port)
    ├── mcp_server.py                   # MCP server (21 tools for Claude)
    ├── mcp_auth.py                     # OAuth 2.0 for MCP (client credentials + PKCE)
    ├── mcp_server_remote.py            # Remote MCP via SSE
    ├── seed_sa_events.py               # Script to seed San Antonio events
    ├── test_parser.py                  # Parser unit tests
    ├── requirements.txt                # Python dependencies
    ├── railway.toml                    # Railway deployment config
    ├── Procfile                        # Heroku/Render deployment config
    ├── .env.example                    # Template for environment variables
    ├── transactions.db                 # SQLite database (local dev)
    │
    ├── email_parser/                   # Email processing modules
    │   ├── __init__.py
    │   ├── parser.py                   # Claude AI email extraction + normalization
    │   ├── fetcher.py                  # Microsoft Graph API email fetching + sending
    │   ├── database.py                 # SQLite schema, CRUD, audit queries, RSVP logic
    │   ├── report.py                   # Daily email report builder + sender
    │   └── rsvp_parser.py             # Golf Genius RSVP email parser (regex, no AI)
    │
    ├── templates/                      # Jinja2/HTML templates
    │   ├── index.html                  # Transactions dashboard (main page)
    │   ├── events.html                 # Events management page
    │   ├── customers.html              # Customer directory page
    │   ├── rsvps.html                  # RSVP log page
    │   ├── matrix.html                 # Side Games prize matrix (admin)
    │   ├── audit.html                  # Email audit / QA page (admin)
    │   └── changelog.html              # Version history page (admin)
    │
    └── static/
        ├── css/dashboard.css           # All app styling (single file)
        ├── js/
        │   ├── auth.js                 # Shared PIN auth, login modal, role management
        │   ├── dashboard.js            # Transactions page logic (largest JS file)
        │   ├── games-matrix.js         # Prize matrix data (9-hole & 18-hole, 2-64 players)
        │   └── version.js              # Version number + changelog data
        ├── manifest.json               # PWA manifest
        ├── icon.svg                    # App icon (SVG)
        └── icon-180.png                # App icon (180x180 PNG for Apple)
```

---

## Pages & Features

### 1. Transactions Dashboard (`/`)

The main page. Shows all parsed transaction data in a sortable, searchable table.

**Features:**
- **Stats cards** — Items count, Orders count, Total Spent, Earliest/Latest dates
- **Category filters** — All, Upcoming Events, Past Events, Memberships (with counts)
- **Search** — Full-text search across all columns or specific column filter
- **Sort** — Click column headers or use dropdown (order date, event date, price, customer, city, side games)
- **Column visibility toggle** — Show/hide any of 24+ columns, saved to localStorage
- **Inline editing** — Click any row to open Edit modal (customer, item name, price, event date, city, course, handicap, side games, tee choice, status, chapter, has_handicap, returning/new, DOB, points races, match play)
- **Credit/Transfer system** — Mark items as "credited" (money held) or "transferred" to another event, with reversibility
- **Delete** — Admin-only row deletion
- **CSV export** — 24-column export of filtered data
- **Check Now** — Manual inbox check with real-time progress polling (emails fetched, parsed, items saved)
- **Send Report** — Manually trigger daily email report (admin)
- **Connector panel** — Collapsible webhook documentation and examples
- **Auto-refresh** — Every 30 seconds (paused when modals are open)
- **Column drag-to-reorder** — Drag columns to rearrange

**Modals:**
- Login modal (PIN entry)
- Edit Item modal (18 editable fields)
- Credit/Transfer modal (credit vs transfer toggle, event picker, notes)

### 2. Events Page (`/events`)

Shows all events with registration details. Events are auto-created from transaction data.

**Features:**
- **Event summary cards** — All Events, Upcoming, Past (clickable filters)
- **Expandable rows** — Click an event to see all registrants with their details
- **Registrant table** — Customer, Price, Side Games, Tee, Handicap, Status, Golf/Compete, RSVP dot indicator, Actions
- **Side Games stats badges** — Per-event counts: X Playing, Y NET, Z GROSS, W BOTH (clickable to filter registrants)
- **RSVP status dots** — 4 states per player:
  - Blank (no RSVP data)
  - Green circle (auto — GG confirmed "Playing")
  - Red circle (auto — GG "Not Playing")
  - Manual green (manager override)
- **Add Player** — 3 modes:
  - **Manager Comp** — Adds a free/comped player ($0)
  - **RSVP Only** — Adds a placeholder for someone who RSVP'd but hasn't paid
  - **Paid Separately** — Adds a player who paid via cash/Venmo/etc.
- **Upgrade RSVP** — Convert RSVP-only placeholder to full paid registration (Record Payment action)
- **Send Reminder** — Email a payment reminder to RSVP-only players
- **Send Reminder All** — Bulk-send payment reminders to all RSVP-only players in an event
- **Withdraw (WD)** — Mark a player as withdrawn; tracks credit amount and shows WD badge
- **Bulk Email Messaging** — Compose and send emails to event registrants with audience filtering, template variables, and preview
- **Message Templates** — Create, edit, and delete reusable email templates with variable placeholders (`{player_name}`, `{event_name}`, etc.)
- **Message Log** — View all sent messages per event with timestamps and recipients
- **Extra Email Recipients** — Add CC recipients when sending event communications
- **Player card editing** — Inline edit player details (handicap, tee, side games) from mobile cards
- **Transactions/Info tabs** — Toggle between transaction details and player info on mobile cards
- **NET/GROSS/NONE toggle** — Connected button bar for side games filter (replaces separate dropdowns)
- **Delete manual player** — Remove manually-added entries
- **Sync Events** — Auto-detect and create events from transaction item names
- **Check RSVPs** — Trigger manual RSVP inbox check
- **Search** — Filter events by name, course, chapter
- **Column visibility toggle**
- **Sortable columns** — Event name, date, course, chapter, registration count
- **Add Event** — Manually create a new event with format, start type, and tee time planning
- **Tee Time Advisor** — Auto-populates when date + chapter are set; fetches sunset data, shows last recommended tee times with traffic light indicators (green/yellow/red), generates tee time sheets with per-slot finish estimates
- **Format support** — 9 Holes, 18 Holes, 9/18 Combo with independent start types (Tee Times/Shotgun) and start times per group in combo mode
- **Tee time planning** — Configurable tee time count, interval; combo mode has separate counts for 9-hole and 18-hole groups with side-by-side tee sheets

### 3. Customers Page (`/customers`)

Customer directory derived from transaction history.

**Features:**
- **Stats cards** — Customer count, Members count, Total Purchases, Total Spent
- **Two view modes:**
  - **List view** (default) — Table with expandable inline detail rows
  - **Cards view** — Card grid with bottom detail panel
- **Customer detail** — Expandable per-customer showing all their transactions (event date, item, price, city, course, side games, order date, actions)
- **Status derivation** — MEMBER (has a TGF MEMBERSHIP item), GUEST (non-member), 1st TIMER (single purchase, no membership)
- **Chapter derivation** — Most frequent city from their transactions, or chapter from membership
- **Filters** — Status (Member/Guest/1st Timer), Chapter dropdown
- **Sort** — Name, purchases count, total spent, last activity
- **Search** — By name, email, chapter
- **Column visibility toggle**
- **CSV export**
- **Credit/Transfer** — Available from customer detail rows
- **Add Customer** — Create a new customer record manually (without a transaction)
- **Transactions/Info tabs** — Toggle between transaction history and editable customer info panel
- **Customer update** — Edit customer email, phone, chapter, status inline from the Info tab
- **Roster upload** — Import customers in bulk from Excel (.xlsx) files with column auto-detection, email matching, and skip-no-email option
- **Customer aliases** — Link alternate names, emails, and phone numbers to a single customer
- **AI name parsing** — Structured first/last/full name fields with AI-powered parsing and validation
- **Mobile cards** — Automatic card layout on small screens with merge/edit/delete buttons
- **WD badge** — Show withdrawal status and credit amounts on customer cards
- **Clickable emails** — `mailto:` links

### 4. RSVP Log (`/rsvps`)

Shows all Golf Genius RSVP responses with matching status.

**Features:**
- **Stats cards** — Total RSVPs, Playing (green), Not Playing (red), Matched, Unmatched
- **Category filters** — All, Playing, Not Playing, Matched, Unmatched
- **Table columns** — Player name, Email, GG Event name, Response (badge), Event Date, Received date, Matched Event
- **Check RSVPs** — Manual inbox check
- **Rematch** — Re-run matching logic on unmatched RSVPs
- **Link to Customer** — Connect an unmatched RSVP to an existing customer record
- **New Customer from RSVP** — Create a new customer directly from an unlinked RSVP entry
- **Auto-resolve names** — Automatically match RSVP player names from known customer emails
- **Search** — By player name, event, email
- **Event filter dropdown**
- **Sortable columns**
- **Mobile card view** — Automatic on small screens

### 5. Side Games Matrix (`/matrix`) — Admin Only

Interactive prize structure calculator based on player count.

**Features:**
- **9/18 hole toggle** — Switch between 9-hole and 18-hole prize structures
- **Player range selector** — Set min/max player count (2-64)
- **Matrix table** — Columns = player counts, rows organized by section:
  - **Event Fees** — Total pot per player count
  - **Team Games** — Team total, 1st, 2nd, MWP, team type
  - **CTP (Closest to Pin)** — Total, CTP 1, CTP 2, Hole-in-One
  - **NET Games** — Total pot, Individual NET, Low placements (1st/2nd/3rd), High placements, flights, City MVP, TGF MVP
  - **GROSS Games** — Total pot, Skins total, individual skins values (per 1-9 skins), flights, Low placements
- **Inline editing** — Click any cell to edit values directly
- **Save bar** — Shows unsaved change count, Save/Discard buttons
- **Auto-calculated** — Skins values computed from skins total / number of skins
- **NO_EVENT / NO_GAME markers** — Visual indicators for unavailable games at certain player counts
- **Skins label logic** — Shows "1/2 Net Skins" when <8 gross players, "Skins Gross" when >=8

### 6. Email Audit (`/audit`) — Admin Only

Data quality assurance page comparing raw emails to parsed data.

**Features:**
- **Summary cards** — Total emails, OK count, Incomplete count, Missing count
- **Status filters** — All, OK, Incomplete, Missing
- **Email cards** — Expandable cards showing:
  - Left panel: Raw email body (truncated preview)
  - Right panel: Parsed items with all extracted fields
- **Status badges:**
  - **OK** — All items parsed successfully with all critical fields
  - **Incomplete** — Items parsed but some critical fields missing
  - **Missing** — Email fetched but no items parsed/saved
- **Autofix buttons:**
  - Fix Side Games — Moves misplaced side_games data from golf_or_compete
  - Fix All — Normalizes customer names, course names, side games, item names; backfills customer emails/phones and RSVP full-names/emails
  - Fix Tee Choices — Standardizes tee choice values (<50, 50-64, 65+, Forward)
  - Re-extract Fields — Backfill new item data fields from original email text using AI
- **Autofix confirmation + undo** — Preview changes before applying; one-click rollback of last autofix
- **Date range and limit controls** — Filter audit emails by 7/14/30/90 days with adjustable result limits
- **Search** — Filter by subject, sender, status
- **Feedback tab** — View user-submitted support feedback with Send Test Digest button

### 7. Changelog (`/changelog`) — Admin Only

Version history and release notes page. Data comes from `version.js`.

---

## Database Schema

### `items` table (main transaction data)

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| email_uid | TEXT NOT NULL | Unique email identifier (from Graph API message ID or external) |
| item_index | INTEGER | Position within multi-item order (0-based) |
| merchant | TEXT NOT NULL | e.g. "The Golf Fellowship" |
| customer | TEXT | Buyer name (Title Case) |
| customer_email | TEXT | |
| customer_phone | TEXT | |
| order_id | TEXT | Confirmation/order number |
| order_date | TEXT NOT NULL | ISO date (YYYY-MM-DD) |
| total_amount | TEXT | Full order value incl. fees (e.g. "$222.53") |
| transaction_fees | TEXT | Processing fee (e.g. "$7.53") |
| item_name | TEXT NOT NULL | Event/product name (memberships normalized to "TGF MEMBERSHIP") |
| event_date | TEXT | Date of the golf event (not the order date) |
| item_price | TEXT | Line item price (e.g. "$158.00") |
| quantity | INTEGER | Default 1 |
| city | TEXT | Event city (null for memberships) |
| chapter | TEXT | TGF chapter: Austin, San Antonio, Dallas, Houston, Galveston (memberships only) |
| course | TEXT | Canonical golf course name |
| handicap | TEXT | Numeric handicap value (events) |
| has_handicap | TEXT | YES/NO (memberships only) |
| side_games | TEXT | NET / GROSS / BOTH / NONE |
| tee_choice | TEXT | <50 / 50-64 / 65+ / Forward |
| member_status | TEXT | MEMBER / NON-MEMBER |
| golf_or_compete | TEXT | GOLF / COMPETE |
| post_game | TEXT | Post-game fellowship selection |
| returning_or_new | TEXT | New / Returning (memberships) |
| shirt_size | TEXT | |
| guest_name | TEXT | |
| date_of_birth | TEXT | YYYY-MM-DD |
| net_points_race | TEXT | YES / NO (memberships) |
| gross_points_race | TEXT | YES / NO (memberships) |
| city_match_play | TEXT | YES / NO (memberships) |
| subject | TEXT | Original email subject line |
| from_addr | TEXT | Original email sender |
| transaction_status | TEXT | active / credited / transferred / wd |
| credit_note | TEXT | Reason for credit/transfer |
| partner_request | TEXT | Partner/pairing request from email |
| fellowship_after | TEXT | Post-event fellowship selection |
| notes | TEXT | General notes field |
| first_name | TEXT | Parsed first name |
| last_name | TEXT | Parsed last name |
| middle_name | TEXT | Parsed middle name |
| suffix | TEXT | Name suffix (Jr., Sr., III, etc.) |
| transferred_from_id | INTEGER | FK to originating item |
| transferred_to_id | INTEGER | FK to destination item |
| wd_reason | TEXT | Reason for withdrawal |
| wd_note | TEXT | Additional withdrawal notes |
| wd_credits | TEXT | JSON object of partial credit components |
| credit_amount | TEXT | Dollar amount credited on WD |
| created_at | TEXT | Auto-set to datetime('now') |

**Constraint:** `UNIQUE(email_uid, item_index)` — prevents duplicate parsing
**Indexes:** `order_date DESC`, `item_name`, `customer`

### `events` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| item_name | TEXT UNIQUE | Matches items.item_name exactly |
| event_date | TEXT | |
| course | TEXT | |
| chapter | TEXT | Chapter (San Antonio / Austin) — renamed from `city` |
| format | TEXT | 9 Holes / 18 Holes / 9/18 Combo |
| start_type | TEXT | Tee Times / Shotgun (or 9-hole start type in combo) |
| start_time | TEXT | Start time HH:MM (or 9-hole start time in combo) |
| tee_time_count | INTEGER | Number of tee time slots (or 9-hole count in combo) |
| tee_time_interval | INTEGER | Minutes between tee times |
| start_time_18 | TEXT | 18-hole start time (combo mode only) |
| start_type_18 | TEXT | 18-hole start type (combo mode only) |
| tee_time_count_18 | INTEGER | 18-hole tee time count (combo mode only) |
| event_type | TEXT | Default 'event' |
| created_at | TEXT | |

### `rsvps` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| email_uid | TEXT UNIQUE | Golf Genius email message ID |
| player_name | TEXT | First name from email greeting |
| player_email | TEXT | From email To: header |
| gg_event_name | TEXT | Full GG event string (e.g. "TGF San Antonio 2026 - s9.1 The Quarry") |
| event_identifier | TEXT | Short name extracted after " - " (e.g. "s9.1 The Quarry") |
| event_date | TEXT | Parsed from email (YYYY-MM-DD) |
| response | TEXT | PLAYING / NOT PLAYING |
| received_at | TEXT | When the RSVP email was received |
| matched_event | TEXT | Matched items.item_name (or null if unmatched) |
| matched_item_id | INTEGER | FK to items.id of the matched registrant |
| created_at | TEXT | |

### `rsvp_overrides` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| item_id | INTEGER NOT NULL | FK to items.id |
| event_name | TEXT NOT NULL | Event item_name |
| status | TEXT NOT NULL | none / playing / not_playing / manual_green |

**Constraint:** `UNIQUE(item_id, event_name)`

### `rsvp_email_overrides` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| player_email | TEXT NOT NULL | GG player email |
| event_name | TEXT NOT NULL | Event item_name |
| status | TEXT NOT NULL | none / playing / not_playing / manual_green |
| updated_at | TEXT | |

### `customer_aliases` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| customer_name | TEXT NOT NULL | Primary customer name (FK to items.customer) |
| alias_type | TEXT NOT NULL | `name` or `email` |
| alias_value | TEXT NOT NULL | The alternate name or email |
| created_at | TEXT | |

### `event_aliases` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| alias_name | TEXT NOT NULL | Variant/old event name |
| canonical_event_name | TEXT NOT NULL | Canonical event name (FK to events.item_name) |
| created_at | TEXT | |

### `message_templates` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| name | TEXT NOT NULL | Template display name |
| channel | TEXT | `email` or `sms` |
| subject | TEXT | Email subject line (supports variables) |
| html_body | TEXT | Email body HTML (supports variables like `{player_name}`, `{event_name}`) |
| sms_body | TEXT | SMS text (for future Twilio integration) |
| is_system | INTEGER DEFAULT 0 | 1 for built-in templates |
| created_at | TEXT | |
| updated_at | TEXT | |

### `message_log` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| event_name | TEXT | Event context for the message |
| template_id | INTEGER | FK to message_templates.id |
| channel | TEXT | `email` or `sms` |
| recipient_name | TEXT | |
| recipient_address | TEXT | Email address or phone number |
| subject | TEXT | Rendered subject |
| body_preview | TEXT | First ~200 chars of rendered body |
| status | TEXT | `sent` / `failed` |
| error_message | TEXT | Error detail if failed |
| sent_by | TEXT | Role of sender (admin/manager) |
| sent_at | TEXT | |
| created_at | TEXT | |

### `feedback` table

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| type | TEXT | `bug` or `feature` |
| message | TEXT NOT NULL | User-submitted feedback text |
| page | TEXT | Page the feedback was submitted from |
| role | TEXT | User's role at time of submission |
| status | TEXT DEFAULT 'open' | `open` / `resolved` / `dismissed` |
| created_at | TEXT | |

---

## API Endpoints

### Pages

| Route | Access | Description |
|-------|--------|-------------|
| `/` | All | Transactions dashboard |
| `/events` | All | Events management |
| `/customers` | All | Customer directory |
| `/rsvps` | All | RSVP log |
| `/matrix` | Admin | Side Games prize matrix |
| `/audit` | Admin | Email audit/QA |
| `/changelog` | Admin | Version history |

### Items / Transactions

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/items` | GET | — | All items as JSON |
| `/api/items/<id>` | PATCH | — | Update fields on an item |
| `/api/items/<id>` | DELETE | Admin | Delete an item |
| `/api/stats` | GET | — | Summary statistics (counts, totals, date range) |
| `/api/audit` | GET | — | Data quality report (fill rates, problems, distributions) |
| `/api/data-snapshot` | GET | — | Recent items + stats (accepts `?limit=N`) |

### Credit / Transfer / Withdrawal

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/items/<id>/credit` | POST | Mark as credited (body: `{note}`) |
| `/api/items/<id>/transfer` | POST | Transfer to another event (body: `{target_event, note}`) |
| `/api/items/<id>/reverse-credit` | POST | Undo credit/transfer, restore to active |
| `/api/items/<id>/wd` | POST | Mark as withdrawn (body: `{reason, note, credits, credit_amount}`) |

### Events

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/events` | GET | — | All events with registration counts |
| `/api/events` | POST | — | Create event (body: `{item_name, event_date, course, chapter, format, start_type, start_time, ...}`) |
| `/api/events/<id>` | PATCH | — | Update event fields |
| `/api/events/<id>` | DELETE | Admin | Delete event |
| `/api/events/sync` | POST | — | Auto-create events from item_name patterns |
| `/api/events/add-player` | POST | — | Add player (body: `{event_name, customer, mode, ...}`) |
| `/api/events/upgrade-rsvp` | POST | — | Convert RSVP placeholder to paid (body: `{item_id, ...}`) |
| `/api/events/send-reminder` | POST | — | Email payment reminder (body: `{to_email, player_name, event_name}`) |
| `/api/events/send-reminder-all` | POST | — | Bulk-send reminders to all RSVP-only players in an event |
| `/api/events/merge` | POST | — | Merge two events (body: `{source_event, target_event}`) |
| `/api/events/orphaned-items` | GET | — | Items not linked to any event |
| `/api/events/resolve-orphan` | POST | — | Link an orphaned item to an event |
| `/api/events/aliases` | GET | — | All event name aliases |
| `/api/events/delete-manual-player/<id>` | DELETE | — | Remove manually-added player |
| `/api/events/seed` | POST | Admin | Batch-create events from JSON array |
| `/api/sunset` | GET | — | Sunset data for tee time advisor (params: `date`, `chapter`). Returns sunset, civil twilight, 24h times. DST-aware. |

### RSVPs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rsvps` | GET | All RSVPs (accepts `?event=` and `?response=` filters) |
| `/api/rsvps/event/<name>` | GET | Latest RSVP per player for a specific event |
| `/api/rsvps/stats` | GET | RSVP summary statistics |
| `/api/rsvps/check-now` | POST | Manual RSVP inbox check |
| `/api/rsvps/rematch` | POST | Re-run matching on unmatched RSVPs |
| `/api/rsvps/overrides/<event>` | GET | Manual RSVP overrides for an event |
| `/api/rsvps/bulk` | GET | Bulk fetch RSVPs for multiple events |
| `/api/rsvps/<id>/match` | POST | Manually match an RSVP to an event |
| `/api/rsvps/<id>/unmatch` | POST | Unmatch an RSVP from its event |
| `/api/rsvps/overrides` | POST | Set RSVP override (body: `{item_id, event_name, status}`) |
| `/api/rsvps/config-status` | GET | Check RSVP credentials configured |

### Inbox & Parsing

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/check-now` | POST | Start background inbox scan + AI parse |
| `/api/check-status` | GET | Poll background check progress |
| `/api/config-status` | GET | Which integrations are configured |

### Connector / Webhook

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/connector/ingest` | POST | X-API-Key | Push pre-structured items or raw email for AI parsing |
| `/api/connector/info` | GET | — | Connector configuration info |

### Audit (Admin)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/audit/emails` | GET | Compare raw emails vs parsed data |
| `/api/audit/autofix-side-games` | POST | Fix side_games misplacement |
| `/api/audit/autofix-all` | POST | Normalize names, courses, side games, tees; backfill emails/phones |
| `/api/audit/undo-autofix` | POST | Undo the last autofix operation |
| `/api/audit/autofix-tee-choices` | POST | Standardize tee choices |
| `/api/audit/re-extract-fields` | POST | Re-extract item fields from original email using AI |

### Customers

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/customers/create` | POST | — | Create a new customer (body: `{first_name, last_name, email, phone, chapter}`) |
| `/api/customers/update` | POST | — | Update customer fields (body: `{customer_name, field, value}`) |
| `/api/customers/merge` | POST | — | Merge one customer into another |
| `/api/customers/aliases` | GET | — | All customer aliases |
| `/api/customers/aliases` | POST | — | Add alias (body: `{customer_name, alias_type, alias_value}`) |
| `/api/customers/aliases/<id>` | DELETE | — | Delete an alias |
| `/api/customers/from-rsvp` | POST | — | Create customer from RSVP data |
| `/api/customers/link-rsvp` | POST | — | Link RSVP to existing customer |
| `/api/customers/parse-roster` | POST | — | Parse uploaded Excel file for column mapping |
| `/api/customers/preview-roster` | POST | — | Preview roster import before confirming |
| `/api/customers/import-roster` | POST | — | Import parsed roster data into database |

### Messaging

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/messages/templates` | GET | — | All message templates |
| `/api/messages/templates` | POST | — | Create template (body: `{name, subject, html_body}`) |
| `/api/messages/templates/<id>` | PATCH | — | Update template fields |
| `/api/messages/templates/<id>` | DELETE | — | Delete template |
| `/api/messages/send` | POST | — | Send bulk messages (body: `{event_name, template_id, audience, ...}`) |
| `/api/messages/preview` | POST | — | Preview rendered message with template variables |
| `/api/messages/log` | GET | — | All sent messages |
| `/api/messages/log/<event_name>` | GET | — | Messages for a specific event |

### Support / Feedback

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/support/chat` | POST | AI-assisted support chat |
| `/api/support/feedback` | POST | Submit bug report or feature request |
| `/api/support/feedback` | GET | List all feedback (admin) |
| `/api/support/feedback/<id>` | PATCH | Update feedback status |
| `/api/support/test-digest` | POST | Send test daily digest email |

### Matrix (Admin)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/matrix` | PUT | Save edits to games-matrix.js |

### Reports

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/report/send-now` | POST | Send daily report immediately |

### Auth

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Authenticate with PIN (body: `{pin}`) |
| `/api/auth/role` | GET | Current session role |
| `/api/auth/logout` | POST | Clear session |

### Admin / System

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/admin/backup` | GET | Admin | Download SQLite database file |
| `/api/health` | GET | — | App health check (scheduler status, DB connectivity) |

---

## Email Parsing Pipeline

### How transaction emails are processed:

1. **Fetch** — Microsoft Graph API reads the configured mailbox, filtered by sender domain and subject keywords. Looks back 90 days. Paginates through all results.

2. **Filter** — Heuristic matching against 60+ known sender domains (mysimplestore.com, thegolffellowship.com, paypal.com, golfgenius.com, etc.) and 30+ subject keywords (new order, receipt, confirmation, registration, membership, etc.)

3. **Dedup** — Emails already in the database (by `email_uid`) are skipped to avoid burning AI credits.

4. **Parse** — Each new email body is sent to Claude Sonnet with a detailed extraction prompt. Returns structured JSON with all item fields. Emails are parsed one at a time so items appear on the dashboard incrementally.

5. **Normalize** — Post-AI cleanup:
   - **Customer names** — Title Case with Mc/Mac/O' prefix handling
   - **Item names** — Memberships normalized to "TGF MEMBERSHIP"
   - **Course names** — Mapped to canonical spellings (LaCANTERA → La Cantera, etc.)
   - **Chapter** — Abbreviations expanded (AUS → Austin, SA → San Antonio, etc.)
   - **Side games** — Split from golf_or_compete field, normalized to NET/GROSS/BOTH/NONE
   - **Tee choices** — Standardized to <50 / 50-64 / 65+ / Forward

6. **Store** — Upsert into SQLite with `UNIQUE(email_uid, item_index)` constraint.

### AI Extraction Fields

The Claude prompt extracts these fields per order:
- merchant, customer, customer_email, customer_phone, order_id, order_date, total_amount, transaction_fees

And per item:
- item_name, event_date, item_price, quantity, city, chapter, course, handicap, has_handicap, side_games, tee_choice, member_status, golf_or_compete, post_game, returning_or_new, shirt_size, guest_name, date_of_birth, net_points_race, gross_points_race, city_match_play

---

## RSVP Integration (Golf Genius)

Golf Genius (GG) sends "Round Signup Confirmation" emails when players confirm or cancel for events.

### How it works:

1. **Fetch** — Reads the RSVP mailbox (e.g. kerry@thegolffellowship.com) via Graph API, filtering for `from: noreply@golfgenius.com` and subject containing "Round Signup Confirmation"

2. **Parse** — Pure regex extraction (no AI needed):
   - Action: "confirmed" → PLAYING, "cancelled" → NOT PLAYING
   - Player first name from email greeting ("Hi Joe,")
   - Player email from To: header
   - Event name from body ("TGF San Antonio 2026 - s9.1 The Quarry")
   - Event date parsed from parenthetical ("Tue, March 17")

3. **Match** — RSVPs are matched to registered players (items) by:
   - Comparing event identifiers to item_name patterns
   - Matching player names/emails across RSVP and registration data

4. **Display** — On the Events page, each registrant shows a colored dot:
   - No dot = no RSVP data
   - Green = GG confirmed Playing
   - Red = GG Not Playing
   - Manual green = manager override (set via click)

---

## Side Games Matrix

The prize matrix (`games-matrix.js`) contains pre-calculated payout structures for side games based on player count. It covers:

- **9-hole** and **18-hole** variants
- **2 to 64 players**
- **Categories:** Event Fees, Team Games, CTP, NET Games (Low/High/Flights/MVP), GROSS Games (Skins/Low/Flights)
- **Special states:** NO_EVENT (team games don't run below certain thresholds), NO_GAME (gross games unavailable)
- **Dynamic skins:** Skins values are divided equally per number of skins won

The matrix was originally sourced from `25-SideGame-PrizeMatrix.xlsx` and can be edited inline from the Matrix page.

---

## Authentication & Roles

PIN-based, optional two-tier authentication:

| Role | Access |
|------|--------|
| **Admin** | Full access: view, edit, delete items, access audit/matrix/changelog, send reports, run autofixes |
| **Manager** | View and edit only — no deletes, no audit/matrix/changelog access |
| **Unauthenticated** | Dashboard is viewable, but login modal appears on page load |

- PINs are stored in environment variables (`ADMIN_PIN`, `MANAGER_PIN`)
- Compared with `secrets.compare_digest()` for timing-safe comparison
- Role stored in Flask session cookie
- `@require_role("admin")` decorator protects admin-only endpoints
- Nav tabs for Matrix, Audit, and Changelog are hidden for non-admin users
- `.env` is re-read on every login so PIN changes take effect without restart

---

## MCP Server (Claude Integration)

An MCP (Model Context Protocol) server gives Claude direct database access with 21 tools:

**Read tools:**
- `get_transactions`, `get_transaction_by_id`, `get_statistics`
- `get_data_quality_report`, `get_recent_snapshot`
- `list_events`, `get_event_registrations`
- `list_customers`, `get_customer_details`
- `search_transactions`

**Write tools:**
- `update_transaction`, `credit_transaction`, `transfer_transaction`, `undo_credit_or_transfer`
- `create_new_event`, `update_existing_event`, `delete_existing_event`
- `add_player`, `delete_transaction`
- `sync_events`, `run_autofix`

**Setup:**
- **Claude Code:** Auto-configured via `.mcp.json` at repo root
- **Claude Desktop:** Connect to `https://tgf-tracker.up.railway.app/mcp/mcp` (streamable-http transport)

### OAuth 2.0 Authentication (Claude.ai Custom Connector)

The MCP endpoint is protected by OAuth 2.0 client credentials when `MCP_CLIENT_ID` and `MCP_CLIENT_SECRET` environment variables are set. This is required for Claude.ai's custom connector setup.

**OAuth endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/oauth-authorization-server` | GET | RFC 8414 metadata discovery |
| `/oauth/authorize` | GET | Authorization endpoint (auto-approves for valid client) |
| `/oauth/token` | POST | Token endpoint (client_credentials + authorization_code with PKCE) |

**Environment variables to set in Railway:**

```bash
MCP_CLIENT_ID=tgf-mcp-client
MCP_CLIENT_SECRET=TGFmcpSecret2026Railway
```

> **Important:** The client secret must be **alphanumeric only** — underscores are fine, but avoid dashes (especially `--`), quotes, backslashes, or other special characters. Railway's variable parser may strip or mishandle values containing double dashes or special symbols, causing the secret to never reach the process environment.

**Claude.ai Custom Connector setup:**

1. Go to Claude.ai Settings → Integrations → Add Custom MCP Server
2. Enter:
   - **Server URL:** `https://tgf-tracker.up.railway.app/mcp/mcp`
   - **OAuth Client ID:** value of `MCP_CLIENT_ID` (e.g. `tgf-mcp-client`)
   - **OAuth Client Secret:** value of `MCP_CLIENT_SECRET`
3. Claude.ai will discover the OAuth metadata, obtain a Bearer token, and connect to the MCP server

**How it works:**
- Token endpoint accepts `grant_type=client_credentials` with `client_id` and `client_secret`
- Returns a signed Bearer token (HMAC-SHA256, 1-hour expiry)
- MCP requests require `Authorization: Bearer <token>` header
- Authorization code flow with PKCE is also supported for browser-based OAuth redirects
- If `MCP_CLIENT_ID` / `MCP_CLIENT_SECRET` are not set, MCP runs without auth (local dev)

---

## Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Transaction inbox check | Every 15 min (configurable) | Fetch + parse new transaction emails |
| RSVP inbox check | Every 15 min | Fetch + parse Golf Genius RSVP emails |
| Daily report | Daily at 7:00 AM (configurable) | Email summary of last 24 hours |

All scheduled via APScheduler. Only one Gunicorn worker runs the scheduler (env-based guard).

---

## Environment Variables

```bash
# Azure AD / Microsoft Graph
AZURE_TENANT_ID=...              # Azure directory tenant ID
AZURE_CLIENT_ID=...              # App registration client ID
AZURE_CLIENT_SECRET=...          # App registration client secret
EMAIL_ADDRESS=...                # Mailbox to read transaction emails from

# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...     # Required for AI email parsing

# Connector/Webhook
CONNECTOR_API_KEY=...            # API key for /api/connector/ingest

# Daily Report
DAILY_REPORT_TO=...              # Recipient email address
DAILY_REPORT_HOUR=7              # Hour to send (0-23)

# RSVP / Golf Genius
RSVP_EMAIL_ADDRESS=...           # Mailbox for GG RSVP emails
# RSVP_AZURE_TENANT_ID=...      # Optional: separate Azure creds for RSVP
# RSVP_AZURE_CLIENT_ID=...
# RSVP_AZURE_CLIENT_SECRET=...

# App Settings
CHECK_INTERVAL_MINUTES=15        # Inbox check frequency
SECRET_KEY=...                   # Flask session secret

# Authentication PINs
ADMIN_PIN=1234                   # Full admin access
MANAGER_PIN=0000                 # View + edit only

# Database (for Railway persistent volume)
DATABASE_PATH=/data/transactions.db

# MCP OAuth (for Claude.ai custom connector)
MCP_CLIENT_ID=tgf-mcp-client       # OAuth client ID
MCP_CLIENT_SECRET=...               # OAuth client secret (alphanumeric only, no dashes/special chars)
```

---

## Deployment

### Railway (Production)

- **Build:** Nixpacks (auto-detects Python)
- **Start command:** `gunicorn asgi_app:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
- **Persistent volume:** Mount at `/data`, set `DATABASE_PATH=/data/transactions.db`
- **Important:** Without a persistent volume, SQLite data is lost on every redeploy

### Local Development

```bash
cd transaction-tracker
cp .env.example .env  # Fill in credentials
pip install -r requirements.txt
python app.py         # Runs on http://localhost:5000
```

### Also supports:
- Heroku/Render (via Procfile)
- Any platform that runs Gunicorn

---

## PWA / Mobile

The app is installable as a Progressive Web App:

- **Web App Manifest** (`manifest.json`) — standalone display mode
- **Apple meta tags** — `apple-mobile-web-app-capable`, status bar style
- **Session-start redirect** — Always starts at Transactions page when PWA is launched fresh
- **Mobile-responsive** — All pages have responsive designs:
  - Tables switch to card layouts on mobile
  - Touch-friendly controls
  - Compact stat cards
  - Shortened labels for category filters
  - Hidden column toggles where not useful on mobile

---

## Version History

### v1.3.0 — March 4, 2026 — "Messaging, Roster Import & RSVP Linking"

**Bulk Messaging:**
- Compose and send emails to event registrants with audience filtering (all, playing, RSVP-only, NET, GROSS, not playing, custom)
- Reusable message templates with variable placeholders (`{player_name}`, `{event_name}`, `{course}`, etc.)
- Message preview before sending
- Message log — track all sent messages per event with delivery status
- Extra email recipients (CC) on event communications
- "Remind All" bulk reminder for RSVP-only players

**Customer Management:**
- Add Customer button — create customers manually without a transaction
- Customer update API — edit email, phone, chapter, status, handicap inline from Info tab
- Transactions/Info tabs on customer cards (desktop and mobile)
- Excel roster upload — bulk import from spreadsheets with column auto-detection, email matching, and skip-no-email
- Structured name fields — first/last/middle/suffix with AI-powered name parsing and validation
- Customer aliases — link alternate names, emails, and phones to a single customer record
- WD badge and credit amounts shown on customer cards

**RSVP Linking:**
- "Link to Customer" button on RSVP Log — connect unmatched RSVPs to existing customers
- "New Customer" button on RSVP Log — create a customer directly from an unlinked RSVP
- Auto-resolve RSVP player names from known customer emails

**Event Management:**
- WD (withdrawal) action — mark players as withdrawn with optional partial credit tracking
- Player card editing — inline edit player details from mobile cards
- NET/GROSS/NONE connected toggle group replacing separate dropdowns

**Audit Improvements:**
- Date range and limit controls — filter by 7/14/30/90 days
- Autofix confirmation + undo — preview before applying, one-click rollback
- Re-extract Fields tool — backfill new item fields from original email with AI
- Customer email/phone and RSVP full-name/email backfill in Autofix All

**Support & Feedback:**
- Support feedback system — collect user bug reports and feature requests
- Daily digest email with feedback summary
- Test Digest button on Audit > Feedback tab

**Infrastructure:**
- Fix OAuth flow for Claude.ai MCP connector (PKCE + stateless HMAC tokens)
- MCP_CLIENT_SECRET alphanumeric-only guidance
- Startup diagnostic log for MCP OAuth env var visibility
- Pin mcp, uvicorn, and a2wsgi dependency versions
- Exclude non-transaction placeholder rows from Transactions and Events views

**Mobile:**
- Merge/edit/delete buttons on mobile cards
- Game stat badges on collapsed mobile event cards
- Transactions/Info tab toggles on mobile player cards

### v1.2.0 — March 1, 2026 — "Audit Hardening"
- **Critical:** Log database IntegrityErrors instead of silently swallowing them
- **Critical:** Add `managed_connection` context manager to prevent DB connection leaks
- **Critical:** Wrap auto-refresh intervals in try/catch to prevent silent failures
- **Critical:** Fix XSS risk in orphan banner by replacing inline onclick with data-attribute handlers
- **Critical:** Warn at startup if SECRET_KEY is not set in environment
- **Critical:** AI parser exception surfacing for better error visibility
- **High:** Add input validation (type/length) on mutation API endpoints
- **High:** Fix RSVP popover event listener leak on repeated clicks
- **High:** Email send result checking
- **Medium:** Add database index on `transaction_status` column for query performance
- **Medium:** Tighten scheduler race condition with PID-based guard
- **Medium:** Fix amount inputs to prevent multiple decimal points
- **Medium:** Clean up cached RSVP overrides when collapsing events to prevent memory growth
- **Medium:** Case-insensitive customer name matching in merge operation
- **Database improvements:** NOT NULL constraints on customer/item_name via triggers, case-insensitive duplicate checks for events, `.get()` guards on all API endpoints
- **Frontend improvements:** Null-safe DOM element checks in auto-refresh callbacks
- **Accessibility:** Added `aria-required` and `aria-label` to form inputs, `role="dialog"` and `aria-modal` to modals, improved confirm dialog messages
- **CSS cleanup:** Replaced 12 `!important` declarations with CSS variables and increased specificity, extracted inline styles to CSS classes
- **Code quality:** Consolidated inline `onclick` handlers to `addEventListener` pattern / event delegation, moved all function-level imports to module level, removed redundant `import re` statements, fixed `__import__("datetime")` anti-pattern
- **Scheduler:** Tightened multi-worker env var guard for Gunicorn deployments

### v1.1.0 — February 26, 2026 — "Add Player Overhaul + GG Dot States"
- Redesigned Add Player dialog with 3 modes: Manager Comp, RSVP Only, Paid Separately
- GG RSVP dot with 4 states: blank, auto-green, red, manual-green
- RSVP-only players can be upgraded to full registration via Record Payment
- Skins label shows "1/2 Net Skins" when <8 gross players, "Skins Gross" when >=8
- Fixed skins NO_EVENT display bug
- Side Games Matrix page with 9/18 toggle and inline editing
- Populated Net and Gross data for 2-3 players in games matrix
- Version display and changelog page

### v1.0.0 — February 20, 2026 — "Initial Release"
- Transaction dashboard with email parsing
- Events page with registration tracking and side games
- Customer directory
- RSVP Log from GolfGenius
- Audit Log with data quality checks
- Mobile-responsive design

---

## Backlog / Roadmap

Features discussed or planned but not yet implemented:

### High Priority
- ~~**Bulk Event Communications (Email + SMS)**~~ — **DONE** (v1.3.0). Email messaging implemented with audience filtering, reusable templates, preview, and message log. SMS (Twilio) still pending.
- ~~**SUPPORT button**~~ — **DONE** (v1.3.0). Support feedback system with bug/feature submission, admin review, and daily digest.
- **Player-facing event page** — Public page where players can see their upcoming events, RSVP status, and payment status without needing a PIN
- ~~**Bulk email reminders**~~ — **DONE** (v1.2.0). "Remind All" button on event detail sends to all RSVP-only players at once.

### Medium Priority
- **Event flyer / details section** — Attach course info, directions, tee times, and event notes to each event
- **Waitlist management** — Track when events hit capacity and manage a waitlist
- **Historical reporting** — Season-over-season comparison, player retention metrics, revenue trends
- **Recurring events** — Template system for weekly/monthly recurring events
- **Team assignment** — Assign players to teams/pairings for team events
- **Live Scoring & Leaderboard** — Player-facing scorecard entry on the course + real-time leaderboard for NET, GROSS, Skins, CTP, and team games. Full spec in [Future Considerations → Live Scoring & Leaderboard](#live-scoring--leaderboard)

### Lower Priority
- **Multi-city dashboard** — City-specific views (San Antonio, Dallas, Austin, Houston, Galveston) with separate stats
- ~~**Email template editor**~~ — **DONE** (v1.3.0). Covered by message templates in Bulk Event Communications.
- **Webhook notifications** — Push notifications (Slack, Discord, etc.) when new registrations arrive
- **Player profile photos** — Upload or link profile pictures for the customer directory
- **Dark mode** — System-preference or manual toggle
- **Full-text search API** — Dedicated search endpoint with fuzzy matching
- ~~**Database backup/export**~~ — **DONE** (v1.2.0). Admin endpoint at `/admin/backup` streams the SQLite database file.

---

## Tax Accounting

TGF has two taxable situations that the transaction tracker must support:

### Sales Tax

Sales tax applies to all sales, but the **taxable amount varies by category**:

| Category | Taxable Portion | Notes |
|----------|----------------|-------|
| **Memberships** | 100% of sale price | Entire membership fee is taxable |
| **Event Sales** | TGF markup only | The markup portion TGF adds on top of course/vendor cost is taxable, not the pass-through amount |
| **Season Contests** | Markup only | Same as events — only TGF's markup is taxable |
| **Merchandise** | Markup only | Only the margin above cost-of-goods is taxable |

**Important:** Even though only the markup is taxable for events, contests, and merchandise, **all sales must be accounted for** in full (total amount collected) for reporting purposes.

### Income Tax

All transactions flowing in and out of TGF need to be accounted for — every dollar received and every dollar spent, regardless of category or tax treatment.

---

## Order Grouping

Items from the same purchase already share an `order_id` field in the database. Order Grouping adds a visual hierarchy to the Transactions view so multi-item orders are displayed as a single collapsible unit.

### Display Rules

| Scenario | Behavior |
|----------|----------|
| **Single-item order** | Displayed as a regular flat row — no collapsible wrapper |
| **Multi-item order** (2+ items with same `order_id`) | Displayed as a collapsible group with a summary row + indented item rows |
| **Default state** | Expanded (all items visible on page load) |

### Summary Row (Collapsed View)

When a multi-item order is collapsed, one summary row represents the entire order:

| Field | Source |
|-------|--------|
| **Order date** | Shared `order_date` from the order |
| **Customer name** | Shared `customer` from the order |
| **Item count** | Number of items in the order (e.g., "3 items") |
| **Total amount** | Sum of all item amounts in the order |
| **Item names** | Abbreviated list of item names (e.g., "SA Kickoff, Net Side Game, Skins") |

### Expanded View (Item Rows)

Each line item within an expanded order shows the **full transaction columns** — the same fields as a standalone single-item row (item name, amount, payment status, event linkage, etc.). This keeps the view consistent regardless of whether an item is part of a group or standalone.

### Visual Style

- **Summary row:** Bold text with a slightly darker/colored background to distinguish it from item rows
- **Item rows:** Indented slightly to the right to show hierarchy beneath the summary row
- **Collapse/expand toggle:** Chevron or arrow icon on the summary row to toggle visibility of item rows

### Interaction

- Clicking the summary row (or its chevron) toggles between collapsed and expanded states
- Search and filter still operate on individual items — if a filter matches one item in a group, the entire group is shown with the matching item highlighted
- Sort order applies to the summary row's values (e.g., sorting by amount uses the order total)

---

## Future Considerations

### Auth Scalability: Per-User PINs

The current two-PIN system (`ADMIN_PIN`, `MANAGER_PIN`) works for San Antonio and Austin today, where one admin and one chapter manager each have a PIN. But TGF is expanding to DFW (Q2 2026) and Houston (Q3 2026), which means:

- 4 chapter managers needing separate access
- Shared PINs make it impossible to audit who did what
- No way to revoke access for a single person without changing everyone's PIN

**Recommended upgrade path (lightweight, no external auth service):**

1. **Add a `users` table:**
   ```sql
   CREATE TABLE users (
       id       INTEGER PRIMARY KEY AUTOINCREMENT,
       name     TEXT NOT NULL,
       pin      TEXT NOT NULL,          -- hashed PIN (bcrypt or similar)
       role     TEXT NOT NULL,          -- 'admin', 'manager'
       chapter  TEXT,                   -- 'San Antonio', 'Austin', 'DFW', 'Houston'
       active   INTEGER DEFAULT 1,     -- soft-disable without deleting
       created_at TEXT DEFAULT (datetime('now'))
   );
   ```

2. **Login flow change:** Login modal accepts a PIN, checks it against the `users` table instead of env vars. Session stores user ID, role, and chapter. Env-based PINs become the initial admin bootstrap mechanism only.

3. **Chapter-scoped views:** Once users have a chapter, add optional chapter filtering to the Events and Customers pages. A DFW manager only sees DFW events by default but can switch to "All Chapters" view.

4. **User management page (admin):** Simple CRUD for managing PINs, roles, and chapters. Admin-only. Could be as simple as a table with inline editing.

5. **Audit logging (optional):** Add a `user_id` column to actions like credits, transfers, merges, and manual player additions for accountability.

**Effort estimate:** 1-2 sessions. The user table and login change are straightforward. Chapter-scoped views are the most work but can be rolled out incrementally.

**When to build:** When the third chapter (DFW) goes live and a third PIN is needed.

---

## Platform Relationship

### Context

The TGF Transaction Tracker was built as an operations tool for managing golf event registrations, payments, and RSVPs. A separate "TGF Platform" MVP is targeting May 2026 as a member-facing application with self-service registration, profiles, and payment.

### Does this tool get deprecated?

**No.** The Transaction Tracker and the TGF Platform serve different audiences and solve different problems:

| Concern | Transaction Tracker | TGF Platform (MVP) |
|---------|-------------------|-------------------|
| **Users** | TGF admins and chapter managers | TGF members and prospective players |
| **Purpose** | Operations: parse emails, reconcile payments, manage rosters | Self-service: register, pay, view schedule, manage profile |
| **Data source** | Email inbox (MySimpleStore, PayPal, GG) | Direct user input + payment gateway |
| **Strength** | Works with existing email-based workflow today | Replaces that workflow long-term |

### Recommended Transition Strategy

**Phase 1 — Parallel operation (now through Platform MVP launch)**
- Transaction Tracker continues as the primary operations tool
- Platform MVP is built and tested independently
- No changes needed on either side

**Phase 2 — Platform launch (May 2026)**
- Platform handles member-facing registration and payment
- Transaction Tracker becomes the **admin/operations layer**:
  - Continues parsing emails for any registrations that still come through the old flow (stragglers, manual payments, comps)
  - Provides the roster management, credit/transfer, and RSVP integration that the Platform MVP won't have on day one
  - Serves as the data reconciliation tool (cross-referencing Platform registrations with email confirmations)

**Phase 3 — Full integration (post-MVP)**
- Platform gets its own admin dashboard → Transaction Tracker's dashboard role shrinks
- **Keep permanently:**
  - **Email parsing pipeline** — Always valuable as a backup data source and for catching edge cases (PayPal direct payments, forwarded receipts, etc.)
  - **MCP server** — Claude integration for operational queries remains useful regardless of what frontend exists
  - **Side Games matrix** — Reusable prize calculation engine, can be exposed as an API to the Platform
  - **RSVP integration** — Golf Genius email parsing stays relevant until GG offers a proper API
- **Deprecate when Platform covers them:**
  - Manual player additions (Platform handles registration directly)
  - Customer directory (Platform has member profiles)
  - Daily email reports (Platform has its own notifications)

### The Bottom Line

The Transaction Tracker evolves from "the whole system" to "the operations and data integrity layer." The email parsing pipeline, MCP server, and GG integration are permanent infrastructure. The dashboard and manual management features gradually hand off to the Platform as it matures.

---

### Live Scoring & Leaderboard

A player-facing live scoring interface for use during events, paired with real-time leaderboards for all game types. Players enter scores hole-by-hole on their phones; spectators and other players see standings update live.

#### What Already Exists (Foundation)

| Component | Status | Details |
|-----------|--------|---------|
| Player registry | Ready | `items` table has `customer`, `handicap`, `side_games` (NET/GROSS/BOTH/NONE), `tee_choice` per registrant |
| Event registry | Ready | `events` table with course, city, date |
| Prize matrix | Ready | Full payout structure for 2-64 players, 9 and 18 holes, all game categories in `games-matrix.js` |
| Flight computation | Ready | Already classifying NET vs GROSS player counts and computing flight sizes per event |
| RSVP / attendance | Ready | Know who's confirmed playing before the round starts |
| Auth system | Ready | Admin/manager roles with PIN-based auth |
| PWA | Ready | App is already installable on phones, standalone mode |
| WAL mode | Ready | SQLite write-ahead logging supports concurrent reads during writes |

#### New Database Tables

**`scorecards` table** — One row per player per event

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| event_id | INTEGER NOT NULL | FK to events.id |
| item_id | INTEGER | FK to items.id (links to registration) |
| player_name | TEXT NOT NULL | Denormalized from items.customer |
| handicap | REAL | Numeric handicap at time of play |
| tee_choice | TEXT | Tee played from |
| side_games | TEXT | NET / GROSS / BOTH / NONE |
| holes | INTEGER NOT NULL | 9 or 18 |
| hole_scores | TEXT | JSON array of strokes per hole, e.g. `[5,4,3,6,4,5,3,4,5]` |
| gross_total | INTEGER | Sum of hole_scores (computed on save) |
| net_total | REAL | gross_total - handicap adjustment (computed on save) |
| thru | INTEGER DEFAULT 0 | How many holes completed (for "thru X" display) |
| status | TEXT DEFAULT 'in_progress' | `in_progress` / `finalized` |
| started_at | TEXT | When first hole was entered |
| updated_at | TEXT | Last hole entry timestamp |
| created_at | TEXT DEFAULT (datetime('now')) | |

**`ctp_entries` table** — Closest-to-pin results per hole

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| event_id | INTEGER NOT NULL | FK to events.id |
| hole_number | INTEGER NOT NULL | Which par-3 |
| player_name | TEXT NOT NULL | |
| distance | REAL | Distance in feet (e.g. 12.5) |
| is_winner | INTEGER DEFAULT 0 | Set to 1 when finalized |
| created_at | TEXT DEFAULT (datetime('now')) | |

**`skin_results` table** — Computed after scores are posted

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| event_id | INTEGER NOT NULL | FK to events.id |
| hole_number | INTEGER NOT NULL | |
| winner_name | TEXT | NULL if hole was tied (carryover) |
| is_carryover | INTEGER DEFAULT 0 | 1 if no outright winner |
| payout | REAL | Amount won (from matrix skins array) |
| flight | TEXT DEFAULT 'all' | `all` / `low` / `high` (for flighted skins) |
| created_at | TEXT DEFAULT (datetime('now')) | |

#### New Pages

**1. Scorecard Entry — `/scorecard/<event_id>`** (Player-facing, mobile-first)

- **No login required** — Player selects their name from the event roster (confirmed players only)
- **Hole-by-hole entry** — Swipeable card per hole with large tap targets for stroke count (+/-)
- **Running totals** — Gross and net scores update live as holes are entered
- **CTP entry** — On designated par-3s, prompt for distance (feet/inches)
- **Save per hole** — Each hole saves immediately via API (survives phone sleep/crash/signal loss)
- **Offline resilience** — Service worker queues entries if signal drops, syncs when reconnected
- **Simple UI** — Big numbers, minimal chrome, one-handed operation, think 18Birdies-style
- **Course info header** — Event name, course, date, player's handicap and tee

**2. Leaderboard — `/leaderboard/<event_id>`** (Spectator/player view, responsive)

| Section | What It Shows |
|---------|---------------|
| **NET Leaderboard** | Ranked by net score, grouped by flight (Low/High/Mid/4th per matrix), "thru X" indicator |
| **GROSS Leaderboard** | Ranked by gross score, shows total skins won |
| **Skins Board** | Hole-by-hole: lowest score, ties = carryover marker, running payout per skin |
| **CTP Board** | Par-3 holes with closest distance and current leader |
| **Team Game** | Team standings if team format is active (cart-net, 2-ball, etc.) |
| **Prize Projection** | "If standings hold" → projected payouts from matrix lookup |

- **Auto-refresh** — Poll every 20 seconds (lightweight — only fetch changed data)
- **Shareable link** — QR code generated per event for posting at the clubhouse / first tee
- **Color coding** — Green highlight for in-the-money positions, bold for leader changes
- **Responsive** — Works on phones (portrait), tablets, and TV/monitors for clubhouse display
- **No login required** — Anyone with the link can view

#### New API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/scorecard/<event_id>` | GET | — | All scorecards for event (leaderboard data) |
| `/api/scorecard/<event_id>/<player>` | GET | — | Single player's scorecard |
| `/api/scorecard/<event_id>/enter` | POST | — | Submit hole score(s): `{player_name, hole_number, strokes}` |
| `/api/scorecard/<event_id>/ctp` | POST | — | Submit CTP distance: `{hole_number, player_name, distance}` |
| `/api/leaderboard/<event_id>` | GET | — | Computed leaderboard JSON (NET/GROSS/Skins/CTP rankings) |
| `/api/scorecard/<event_id>/finalize` | POST | Admin | Lock all scores, compute final standings + payouts |
| `/api/scorecard/<event_id>/export` | GET | Admin | CSV or PDF of final results |
| `/api/events/<event_id>/start-scoring` | POST | Manager | Initialize scorecards for all confirmed players |

#### Scoring Engine — New Module `email_parser/scoring.py`

Core calculation logic, separate from Flask routes:

- **Net score calculation** — `gross - (handicap × holes/18)` for course handicap derivation
- **Flight assignment** — Sort NET players by handicap, divide into N flights based on matrix's `netFlights` value for the player count
- **Skins computation** — Lowest unique score per hole wins; ties carry over to next hole; payout from matrix `skins[]` array divided by number of skins won
- **CTP ranking** — Shortest distance per designated par-3 hole
- **Team game scoring** — Depends on `teamType` from matrix (CART Net best-ball, 2-Ball, etc.)
- **Prize lookup** — Player count → matrix → payout per position per flight
- **Leaderboard assembly** — Combine all game results into a single ranked JSON response

#### Admin Controls (Events Page Additions)

Add to the existing event detail panel in `events.html`:

- **"Start Scoring" button** — Creates scorecard rows for all confirmed-playing players, generates shareable QR code link
- **"View Leaderboard" button** — Opens `/leaderboard/<event_id>` in new tab
- **"Finalize Event" button** — Locks all scores, runs final prize calculation, marks event as scored
- **Scorecard override** — Admin can edit any player's hole score after the fact
- **Results summary** — Post-event view showing all winners and payouts per game category

#### Architecture Decision: Real-Time Mechanism

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **Polling (20s)** | Works with current Flask setup, no new infra, dead simple | Slight delay, more DB reads | **Start here** |
| **SSE** | True one-way push, moderate effort | Needs endpoint, connection management | Upgrade path if needed |
| **WebSockets** | Bi-directional, fastest | New dependency (flask-socketio), Railway config | Overkill for this use case |

**Recommendation:** Start with **20-second polling**. A golf round takes 4+ hours — 20s latency is invisible. The leaderboard endpoint should be lightweight (return only data changed since last poll via `?since=` timestamp). Upgrade to SSE only if polling creates noticeable load.

#### Offline / Connectivity Strategy

Golf courses often have spotty cell coverage. The scorecard page needs to handle this:

1. **Service worker** — Cache the scorecard page shell and JS so it loads even offline
2. **Local queue** — When a hole score is entered but the POST fails, store it in `localStorage` and retry when connectivity returns
3. **Sync indicator** — Show a small badge ("2 holes pending sync") so the player knows their data will catch up
4. **Conflict resolution** — If the same hole is submitted twice (retry + delayed original), server uses latest timestamp

#### Implementation Order (Recommended Build Sequence)

| Session | Deliverable | What's Built |
|---------|------------|--------------|
| **1** | Data model + scoring engine | New tables in `database.py`, new `scoring.py` module with net/gross/skins/CTP/flight calculations, unit tests |
| **2** | Scorecard entry UI | `/scorecard/<event_id>` page, hole-by-hole entry, API endpoints for score submission, mobile-first CSS |
| **3** | Leaderboard + admin controls | `/leaderboard/<event_id>` page, auto-refresh polling, "Start Scoring" / "Finalize" buttons on events page, QR code generation |
| **4** | Polish + offline | Service worker for offline resilience, localStorage queue, CTP entry flow, export/PDF, testing with real event data |

#### Estimated Scope

| Component | Files | Lines (approx) |
|-----------|-------|-----------------|
| Database schema + migrations | Edit `database.py` | ~100 |
| Scoring engine | New `scoring.py` | ~250 |
| API endpoints | Edit `app.py` | ~300 |
| Scorecard page (mobile) | New `scorecard.html` | ~400 |
| Leaderboard page | New `leaderboard.html` | ~500 |
| Admin controls | Edit `events.html` | ~150 |
| CSS additions | Edit `dashboard.css` | ~150 |
| **Total** | **2 new files + 4 edited** | **~1,850 lines** |

#### Open Questions for Implementation Time

1. **Course data** — Do we need a `courses` table with par per hole, or will par be entered at event setup time? (Needed for over/under par display on leaderboard)
2. **Team format details** — How are teams formed? Cart partners? Random draw? Need to know for team game scoring
3. **CTP hole designation** — Are CTP holes always the same per course, or chosen per event? Should admin mark which holes are CTP when starting scoring?
4. **Skins format** — Are skins always gross? Or net skins for some events? The matrix has both scenarios
5. **Post-event flow** — After finalization, should payouts auto-generate transaction records in the items table (as credits/debits)?

---

### Bulk Event Communications (Email + SMS)

A compose-and-send interface for reaching event registrants via email and SMS. Builds on the existing "Remind All" payment reminder (v1.2.0) and `send_mail_graph()` infrastructure, expanding it into a general-purpose communication tool with audience filtering, reusable templates, and SMS support.

#### What Already Exists (Foundation)

| Component | Status | Details |
|-----------|--------|---------|
| Email sending | Ready | `send_mail_graph()` in `fetcher.py` — Microsoft Graph API, HTML body, works today |
| Payment reminder template | Ready | Simple HTML template with player name + event name personalization |
| Daily digest template | Ready | Rich HTML with inline CSS, stat cards, tables, responsive layout |
| Bulk send endpoint | Ready | `/api/events/send-reminder-all` sends sequentially to all RSVP-only players |
| Bulk send UI | Ready | "Remind All (N)" button with confirmation dialog on events page |
| Customer email field | Ready | `customer_email` in items table, auto-backfilled across transactions per customer |
| Customer phone field | Exists but unused | `customer_phone` in items table, populated by parser but never accessed |
| Azure AD / Graph API creds | Ready | `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `EMAIL_ADDRESS` all configured |
| SMS provider | Not integrated | No Twilio or other SMS library in `requirements.txt` |

#### New Database Tables

**`message_templates` table** — Reusable message templates

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| name | TEXT NOT NULL | Template name (e.g. "Event Announcement", "Tee Time Update") |
| channel | TEXT NOT NULL | `email` / `sms` / `both` |
| subject | TEXT | Email subject line (supports `{event_name}` variables) |
| html_body | TEXT | Email HTML body (supports `{player_name}`, `{event_name}`, `{event_date}`, `{course}`, `{city}` variables) |
| sms_body | TEXT | SMS plain text (160-char target, same variables) |
| is_system | INTEGER DEFAULT 0 | 1 for built-in templates (payment reminder, etc.) that can't be deleted |
| created_at | TEXT DEFAULT (datetime('now')) | |
| updated_at | TEXT | |

**`message_log` table** — Send history and delivery tracking

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| event_name | TEXT | Event this message was for (nullable for non-event messages) |
| template_id | INTEGER | FK to message_templates.id (nullable for custom one-off messages) |
| channel | TEXT NOT NULL | `email` / `sms` |
| recipient_name | TEXT | Player name |
| recipient_address | TEXT NOT NULL | Email address or phone number |
| subject | TEXT | Rendered subject (email only) |
| body_preview | TEXT | First 200 chars of rendered body |
| status | TEXT DEFAULT 'sent' | `sent` / `failed` / `bounced` |
| error_message | TEXT | Error details if failed |
| sent_by | TEXT | Admin/manager who triggered it |
| sent_at | TEXT DEFAULT (datetime('now')) | |

#### Compose & Send UI (Events Page Enhancement)

Add a **"Message Players"** button to each event's detail panel, opening a compose modal:

**Compose Modal — Step 1: Audience**
- **Recipient filter chips** (multi-select):
  - All Registered — everyone with `transaction_status` in (`active`, `rsvp_only`, `gg_rsvp`, `paid_separately`)
  - Playing (RSVP confirmed) — green dot players only
  - RSVP Only (unpaid) — existing remind-all audience
  - NET Players / GROSS Players / BOTH — filter by `side_games`
  - Not Playing — red dot players (useful for "we have a spot" messages)
- **Preview count** — "This will reach **14 players** (12 email, 8 SMS)"
- **Recipient list expandable** — Show names + contact info, let admin deselect individuals

**Compose Modal — Step 2: Message**
- **Channel toggle** — Email only / SMS only / Both
- **Template picker** — Dropdown of saved templates + "Custom message" option
- **Subject line** (email) — Editable, supports `{event_name}` variable auto-fill
- **Body editor** — Rich text area for email, plain text area for SMS
  - Variable buttons: click to insert `{player_name}`, `{event_name}`, `{event_date}`, `{course}`, `{city}`
  - Character counter for SMS (160 chars / segment)
  - **Preview toggle** — Show rendered message for a sample player
- **Save as template** checkbox — Save this message for reuse

**Compose Modal — Step 3: Confirm & Send**
- Summary: "Send **email** to **14 players** for **Fall Classic 2026**"
- Send button with confirmation
- Progress bar during send (X of Y sent)
- Results: "12 sent, 2 failed (no email on file)" with failed player list

#### Built-In Templates (Seeded on First Run)

| Template | Channel | Use Case |
|----------|---------|----------|
| **Payment Reminder** | Email | Existing reminder for RSVP-only players (migrated from hard-coded HTML) |
| **Event Announcement** | Both | "You're registered for {event_name} at {course} on {event_date}!" |
| **Tee Time Update** | Both | "Tee times are set for {event_name}. Check-in at..." (custom body) |
| **Weather Alert** | Both | "Weather update for {event_name}..." (custom body) |
| **Event Cancellation** | Both | "{event_name} has been cancelled/postponed..." |
| **Day-Of Reminder** | Both | "See you today at {course}! First tee at..." |
| **Post-Event Results** | Email | "Results are in for {event_name}! View the leaderboard..." |

#### SMS Integration (Twilio)

**New dependency:** `twilio` package in `requirements.txt`

**New function in `fetcher.py`:**
```python
def send_sms_twilio(to_number: str, body: str) -> bool
```

**Environment variables:**
```bash
TWILIO_ACCOUNT_SID=AC...        # Twilio account SID
TWILIO_AUTH_TOKEN=...           # Twilio auth token
TWILIO_FROM_NUMBER=+1...       # Twilio phone number (or messaging service SID)
```

**SMS considerations:**
- 160 characters per segment — template editor shows char count and segment count
- US numbers only (TGF is Texas-based) — validate E.164 format (+1XXXXXXXXXX)
- Opt-out compliance — Twilio handles STOP/HELP automatically on long codes
- Cost: ~$0.0079/segment outbound — for 30 players that's ~$0.24 per blast
- Phone number normalization — strip formatting, add +1 country code

#### New API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/messages/send` | POST | Manager | Send message to filtered audience: `{event_name, channel, audience_filter, subject, body, template_id}` |
| `/api/messages/preview` | POST | Manager | Render template for a sample player, return HTML/text preview |
| `/api/messages/templates` | GET | Manager | List all message templates |
| `/api/messages/templates` | POST | Manager | Create new template |
| `/api/messages/templates/<id>` | PATCH | Manager | Update template |
| `/api/messages/templates/<id>` | DELETE | Admin | Delete non-system template |
| `/api/messages/log` | GET | Manager | Send history (filterable by event, channel, status, date range) |
| `/api/messages/log/<event_name>` | GET | Manager | Send history for specific event |

#### Rate Limiting & Throttling

| Provider | Limit | Strategy |
|----------|-------|----------|
| Microsoft Graph API | ~10,000 emails/day per tenant, 4 requests/sec | 250ms delay between sends, batch of 20 with 1s pause |
| Twilio SMS | Varies by number type (1 msg/sec for long code) | Sequential send with 1s spacing, or use Messaging Service for higher throughput |

**Implementation:** Add a `send_with_throttle()` wrapper that:
1. Accepts a list of `(recipient, rendered_message)` tuples
2. Sends sequentially with configurable delay (default 300ms for email, 1100ms for SMS)
3. Logs each send to `message_log`
4. Returns aggregate `{sent: N, failed: N, errors: [...]}`
5. Runs in a background thread (APScheduler one-off job) so the UI isn't blocked

#### Message History Panel (Events Page)

Add a **"Messages"** tab to the event detail panel showing:
- Chronological log of all messages sent for this event
- Each entry: timestamp, channel icon (email/SMS), template name, recipient count, sent-by
- Expandable: full recipient list with delivery status per player
- **Resend** button on failed recipients

#### Implementation Order (Recommended Build Sequence)

| Session | Deliverable | What's Built |
|---------|------------|--------------|
| **1** | Email compose + send | New tables, compose modal on events page, audience filtering, send with throttle, message log |
| **2** | Templates + history | Template CRUD, built-in template seeding, template picker in compose modal, message history panel |
| **3** | SMS integration | Twilio setup, `send_sms_twilio()`, dual-channel compose, phone number validation, SMS char counter |

#### Estimated Scope

| Component | Files | Lines (approx) |
|-----------|-------|-----------------|
| Database tables + migrations | Edit `database.py` | ~60 |
| Send logic + throttling | Edit `fetcher.py` | ~120 |
| API endpoints | Edit `app.py` | ~200 |
| Compose modal + message history | Edit `events.html` | ~400 |
| SMS integration (Twilio) | Edit `fetcher.py` + `requirements.txt` | ~80 |
| Built-in template seeding | Edit `database.py` | ~60 |
| **Total** | **4 edited files** | **~920 lines** |

#### Open Questions for Implementation Time

1. **SMS opt-in** — Do players explicitly consent to SMS during registration? The current registration flow doesn't capture this. May need a consent field or assume opt-in for registered players.
2. **From identity** — Should event emails come from the chapter's address (e.g. sanantonio@thegolffellowship.com) or a central address? Different Azure AD permissions may be needed per sender.
3. **Non-event messages** — Should this support sending to all members across events (e.g. season announcements, membership renewals)? Or strictly per-event?
4. **Rich email editor** — Is a basic textarea with variable insertion enough, or do you want a full rich-text editor (bold, images, links)? Rich editors add complexity.
5. **Scheduled sends** — Should messages support scheduling (e.g. "send day-of reminder at 6 AM on event date")? This would integrate with APScheduler.

---

### Push Notifications (Customer-Side App)

Web Push Notifications for the future player-facing app. Not needed until a customer-side app exists, but the infrastructure is straightforward to add when the time comes.

**Prerequisite:** A player-facing PWA / customer app (separate from the admin transaction tracker). Push notifications are sent from the server and appear on the player's phone even when the app is closed.

#### How It Works

1. **Service worker** registers on the player's device when they install the PWA
2. Player **subscribes** to push via the Web Push API — browser generates a unique push subscription (endpoint + keys)
3. Subscription is saved to a `push_subscriptions` table on the server
4. Server sends pushes using **VAPID** (Voluntary Application Server Identification) — no third-party push service needed
5. Player's device receives the push and shows a native notification (even when app is closed)

#### Platform Support

| Platform | Support | Notes |
|----------|---------|-------|
| Android (Chrome) | Full | Works since 2015 |
| iOS Safari | Full | Added in iOS 16.4 (March 2023), requires PWA installed to home screen |
| Desktop browsers | Full | Chrome, Firefox, Edge all support |

#### What It Takes to Build

**New dependency:** `pywebpush` Python package

**One-time setup:**
- Generate VAPID keys: `vapid --gen` → produces `vapid_private.pem` and `vapid_public.pem`
- Store as env vars: `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_CONTACT_EMAIL`

**New database table:**

```
push_subscriptions
├── id (PK)
├── player_email (TEXT NOT NULL)
├── endpoint (TEXT NOT NULL) — browser push endpoint URL
├── p256dh (TEXT NOT NULL) — encryption key
├── auth (TEXT NOT NULL) — auth secret
├── created_at (TEXT)
└── UNIQUE(player_email, endpoint)
```

**Server-side function (~50 lines):**
```python
def send_push(subscription, title, body, url=None) -> bool
```

**Service worker (~40 lines):**
- `push` event listener — shows notification with title, body, and click-to-open URL
- `notificationclick` event listener — opens the app to the specified URL

**Subscription flow (~60 lines client JS):**
- Request notification permission
- Subscribe via `registration.pushManager.subscribe()`
- POST subscription to `/api/push/subscribe`

#### Integration with Messaging

When the messaging compose modal gains a "Push" channel option:
- Compose modal adds a third channel: **Email / SMS / Push**
- Push messages use `title` (from subject) and `body` (plain text, max ~200 chars)
- Server iterates subscriptions for the filtered audience and calls `send_push()` per device
- No per-message cost (unlike SMS)

#### Use Cases

| Notification | When | Content |
|-------------|------|---------|
| Day-of reminder | Morning of event | "See you today at {course}!" |
| Tee time posted | When admin sets times | "Tee times are set for {event_name}" |
| Weather alert | As needed | "Weather update for {event_name}" |
| Leaderboard update | During event | "New leader: John Doe at -3 thru 14" |
| Results posted | Post-event | "Results are in! View leaderboard" |

#### Estimated Scope

| Component | Lines (approx) |
|-----------|-----------------|
| Service worker (`sw.js`) | ~40 |
| Client subscription JS | ~60 |
| `push_subscriptions` table | ~20 |
| `send_push()` function | ~50 |
| Push subscribe/unsubscribe API | ~40 |
| Integration with compose modal | ~30 |
| **Total** | **~240 lines** |

#### When to Build

Build when the customer-side app is ready. The push subscription flow must live in the player-facing app (not the admin tracker), because players are the ones granting notification permission on their devices.
