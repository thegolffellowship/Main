# TGF Transaction Tracker — Platform Specification

## Overview

A Flask + SQLite web application that scans email inboxes (via Microsoft Graph API) for golf event transaction/receipt emails, uses Claude AI to extract structured purchase data, and serves an interactive dashboard for managing transactions, events, and customers.

**Stack:** Python/Flask, SQLite (WAL mode), vanilla JavaScript, APScheduler, Anthropic Claude API, Microsoft Graph API.

---

## File Structure

```
transaction-tracker/
├── app.py                        # Flask app, all routes, scheduler, webhook
├── requirements.txt
├── .env / .env.example
├── transactions.db               # SQLite database
├── email_parser/
│   ├── __init__.py
│   ├── parser.py                 # Claude AI email extraction
│   ├── fetcher.py                # Microsoft Graph email fetching
│   ├── database.py               # SQLite storage & queries
│   └── report.py                 # Daily email report sender
├── templates/
│   ├── index.html                # Main transactions dashboard
│   ├── events.html               # Events management + Tee Time Advisor
│   ├── customers.html            # Customer directory + history
│   └── audit.html                # Email audit/QA page (admin)
└── static/
    ├── js/
    │   ├── auth.js               # PIN-based authentication
    │   └── dashboard.js          # Main dashboard interactivity
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
| customer_email | TEXT | |
| customer_phone | TEXT | |
| order_id | TEXT | Confirmation number |
| order_date | TEXT NOT NULL | ISO date |
| total_amount | TEXT | Full order value |
| item_name | TEXT NOT NULL | Event/product name |
| event_date | TEXT | Date of golf event |
| item_price | TEXT | e.g. "$158.00" |
| quantity | INTEGER DEFAULT 1 | |
| city | TEXT | Event city |
| course | TEXT | Golf course (canonical name) |
| handicap | TEXT | |
| side_games | TEXT | NET/GROSS/BOTH/NONE |
| tee_choice | TEXT | <50/50-64/65+/Forward |
| member_status | TEXT | MEMBER/NON-MEMBER |
| golf_or_compete | TEXT | GOLF/COMPETE |
| post_game | TEXT | Post-game fellowship |
| returning_or_new | TEXT | |
| shirt_size | TEXT | |
| guest_name | TEXT | |
| date_of_birth | TEXT | |
| net_points_race | TEXT | |
| gross_points_race | TEXT | |
| city_match_play | TEXT | |
| subject | TEXT | Original email subject |
| from_addr | TEXT | Original sender |
| transaction_status | TEXT DEFAULT 'active' | active/credited/transferred |
| credit_note | TEXT | Reason for credit/transfer |
| transferred_from_id | INTEGER | FK to originating item |
| transferred_to_id | INTEGER | FK to destination item |
| created_at | TEXT DEFAULT datetime('now') | |

**Constraint:** UNIQUE(email_uid, item_index)
**Indexes:** order_date DESC, item_name, customer

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
| event_type | TEXT DEFAULT 'event' | |
| created_at | TEXT | |

---

## API Endpoints

### Page Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Transactions dashboard |
| `/events` | GET | Events page |
| `/customers` | GET | Customers page |
| `/audit` | GET | Email audit page (admin) |

### Items / Transactions

| Endpoint | Method | Auth | Body / Params | Response |
|----------|--------|------|---------------|----------|
| `/api/items` | GET | — | — | `[{id, customer, item_name, ...}]` |
| `/api/items/<id>` | PATCH | — | `{field: value}` | `{status: "ok"}` |
| `/api/items/<id>` | DELETE | admin | — | `{status: "ok"}` |
| `/api/stats` | GET | — | — | `{total_items, total_orders, total_spent, ...}` |
| `/api/audit` | GET | — | — | `{fill_rates, problems, distributions}` |

### Credit / Transfer

| Endpoint | Method | Body | Effect |
|----------|--------|------|--------|
| `/api/items/<id>/credit` | POST | `{note}` | Sets transaction_status='credited' |
| `/api/items/<id>/transfer` | POST | `{target_event, note}` | Marks original as 'transferred', creates new $0 item on target event |
| `/api/items/<id>/reverse-credit` | POST | — | Reverts credit/transfer back to 'active' |

### Events

| Endpoint | Method | Auth | Body | Response |
|----------|--------|------|------|----------|
| `/api/events` | GET | — | — | `[{id, item_name, event_date, course, chapter, format, start_type, start_time, ..., registrations}]` |
| `/api/events` | POST | — | `{item_name, event_date, course, chapter, format, start_type, start_time, ...}` | `{event}` |
| `/api/events/<id>` | PATCH | — | `{field: value}` | `{status: "ok"}` |
| `/api/events/<id>` | DELETE | admin | — | `{status: "ok"}` |
| `/api/events/sync` | POST | — | — | Auto-creates events from item_name patterns |
| `/api/events/add-player` | POST | — | `{event_name, customer, ...}` | Creates manual registration item |

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
- Item names: Memberships normalized to "TGF MEMBERSHIP"
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
- `parsePrice()` strips `$,` for numeric sorting
- Email addresses rendered as clickable `mailto:` links

### Page-Specific Notes

**Transactions** (`index.html` + `dashboard.js`): Most complex page. Column drag-to-reorder, inline cell editing via modal, category filter buttons (All/Upcoming/Past/Memberships), 24-column CSV export, "Check Now" button with real-time progress polling.

**Events** (`events.html`): Expandable rows showing registrants per event. Add Player modal. Sync Events button auto-detects events from transaction item names. Edit Event modal with format (9/18/Combo), start type (Tee Times/Shotgun — independent per group in combo mode), start time, and tee time planning fields. **Tee Time Advisor** panel auto-populates when date + chapter are set: fetches sunset data via `/api/sunset`, shows last recommended tee times with traffic light indicators (green/yellow/red), and generates tee time sheets with per-slot finish estimates. Combo mode shows side-by-side tee sheets with independent start times, start types, and counts for 9-hole and 18-hole groups.

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
DAILY_REPORT_HOUR=7

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
