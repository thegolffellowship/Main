# TGF Transaction Tracker — Project Documentation

> **The Golf Fellowship** — AI-powered transaction and event management platform
> **Current Version:** v1.2.0 (March 1, 2026)
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
- **Delete manual player** — Remove manually-added entries
- **Sync Events** — Auto-detect and create events from transaction item names
- **Check RSVPs** — Trigger manual RSVP inbox check
- **Search** — Filter events by name, course, city
- **Column visibility toggle**
- **Sortable columns** — Event name, date, course, city, registration count
- **Add Event** — Manually create a new event

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
- **Mobile cards** — Automatic card layout on small screens
- **Clickable emails** — `mailto:` links

### 4. RSVP Log (`/rsvps`)

Shows all Golf Genius RSVP responses with matching status.

**Features:**
- **Stats cards** — Total RSVPs, Playing (green), Not Playing (red), Matched, Unmatched
- **Category filters** — All, Playing, Not Playing, Matched, Unmatched
- **Table columns** — Player name, Email, GG Event name, Response (badge), Event Date, Received date, Matched Event
- **Check RSVPs** — Manual inbox check
- **Rematch** — Re-run matching logic on unmatched RSVPs
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
  - Fix All — Normalizes customer names, course names, side games, item names
  - Fix Tee Choices — Standardizes tee choice values (<50, 50-64, 65+, Forward)
- **Search** — Filter by subject, sender, status

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
| transaction_status | TEXT | active / credited / transferred |
| credit_note | TEXT | Reason for credit/transfer |
| transferred_from_id | INTEGER | FK to originating item |
| transferred_to_id | INTEGER | FK to destination item |
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
| city | TEXT | |
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

### Credit / Transfer

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/items/<id>/credit` | POST | Mark as credited (body: `{note}`) |
| `/api/items/<id>/transfer` | POST | Transfer to another event (body: `{target_event, note}`) |
| `/api/items/<id>/reverse-credit` | POST | Undo credit/transfer, restore to active |

### Events

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/events` | GET | — | All events with registration counts |
| `/api/events` | POST | — | Create event (body: `{item_name, event_date, course, city}`) |
| `/api/events/<id>` | PATCH | — | Update event fields |
| `/api/events/<id>` | DELETE | Admin | Delete event |
| `/api/events/sync` | POST | — | Auto-create events from item_name patterns |
| `/api/events/add-player` | POST | — | Add player (body: `{event_name, customer, mode, ...}`) |
| `/api/events/upgrade-rsvp` | POST | — | Convert RSVP placeholder to paid (body: `{item_id, ...}`) |
| `/api/events/send-reminder` | POST | — | Email payment reminder (body: `{to_email, player_name, event_name}`) |
| `/api/events/delete-manual-player/<id>` | DELETE | — | Remove manually-added player |
| `/api/events/seed` | POST | Admin | Batch-create events from JSON array |

### RSVPs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rsvps` | GET | All RSVPs (accepts `?event=` and `?response=` filters) |
| `/api/rsvps/event/<name>` | GET | Latest RSVP per player for a specific event |
| `/api/rsvps/stats` | GET | RSVP summary statistics |
| `/api/rsvps/check-now` | POST | Manual RSVP inbox check |
| `/api/rsvps/rematch` | POST | Re-run matching on unmatched RSVPs |
| `/api/rsvps/overrides/<event>` | GET | Manual RSVP overrides for an event |
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
| `/api/audit/autofix-all` | POST | Normalize names, courses, side games, tees |
| `/api/audit/autofix-tee-choices` | POST | Standardize tee choices |

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
MCP_CLIENT_SECRET=<generate a secure random string>
```

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
MCP_CLIENT_SECRET=...               # OAuth client secret (generate a secure random string)
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

### v1.2.0 — March 1, 2026 — "Audit Hardening"
- **Critical:** Log database IntegrityErrors instead of silently swallowing them
- **Critical:** Add `managed_connection` context manager to prevent DB connection leaks
- **Critical:** Wrap auto-refresh intervals in try/catch to prevent silent failures
- **Critical:** Fix XSS risk in orphan banner by replacing inline onclick with data-attribute handlers
- **Critical:** Warn at startup if SECRET_KEY is not set in environment
- **High:** Add input validation (type/length) on mutation API endpoints
- **High:** Fix RSVP popover event listener leak on repeated clicks
- **Medium:** Add database index on `transaction_status` column for query performance
- **Medium:** Tighten scheduler race condition with PID-based guard
- **Medium:** Fix amount inputs to prevent multiple decimal points
- **Medium:** Clean up cached RSVP overrides when collapsing events to prevent memory growth
- **Medium:** Case-insensitive customer name matching in merge operation
- **Low:** Consolidate inline `onclick` handlers to `addEventListener` pattern on event action buttons
- **Low:** Move inline `import re` / `import time` to module-level imports
- **Low:** Add `aria-required` attributes to key form inputs
- **Low:** Null-safe DOM element checks in auto-refresh callbacks

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
- **SUPPORT button** — "I have a question" button for players to contact TGF directly from the app
- **Player-facing event page** — Public page where players can see their upcoming events, RSVP status, and payment status without needing a PIN
- ~~**Bulk email reminders**~~ — **DONE** (v1.2.0). "Remind All" button on event detail sends to all RSVP-only players at once.

### Medium Priority
- **Event flyer / details section** — Attach course info, directions, tee times, and event notes to each event
- **Waitlist management** — Track when events hit capacity and manage a waitlist
- **Historical reporting** — Season-over-season comparison, player retention metrics, revenue trends
- **Recurring events** — Template system for weekly/monthly recurring events
- **Team assignment** — Assign players to teams/pairings for team events
- **Scoring integration** — Pull scores from Golf Genius post-round

### Lower Priority
- **Multi-city dashboard** — City-specific views (San Antonio, Dallas, Austin, Houston, Galveston) with separate stats
- **Email template editor** — Customize reminder emails and daily reports from the UI
- **Webhook notifications** — Push notifications (Slack, Discord, etc.) when new registrations arrive
- **Player profile photos** — Upload or link profile pictures for the customer directory
- **Dark mode** — System-preference or manual toggle
- **Full-text search API** — Dedicated search endpoint with fuzzy matching
- ~~**Database backup/export**~~ — **DONE** (v1.2.0). Admin endpoint at `/admin/backup` streams the SQLite database file.

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
