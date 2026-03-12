# TGF Transaction Tracker

Scans your email inbox for Golf Fellowship order emails, uses **Claude AI** to parse every field (items, side games, handicap, tee choice, etc.), and displays everything in a live web dashboard your managers can share.

## What It Does

- **AI-powered parsing** — sends each email to Claude, which extracts every field automatically. No brittle regex. If the store changes their email format, the AI adapts.
- **Multi-item orders** — one email with 3 items becomes 3 separate rows, each with its own data.
- **Dedicated columns** — Item Name, City, Course, Handicap, Side Games, Tee Choice, Member Status, Golf or Compete, etc. All filterable and sortable.
- **Webhook connector** — external systems can push order data in via API.
- **Daily email report** — automated summary of new transactions sent to you every morning.
- **CSV export** — download everything as a spreadsheet at any time.

---

## Setup (Start to Finish)

### Prerequisites

- **Python 3.10+** — check with `python3 --version`
- **An Azure AD app registration** with Microsoft Graph API permissions (Mail.Read, optionally Mail.Send)
- **An Anthropic API key** — get one at https://console.anthropic.com/settings/keys

---

### Step 1: Clone and Install

```bash
# Clone the repo (or download it)
git clone https://github.com/thegolffellowship/Main.git
cd Main/transaction-tracker

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt
```

This installs Flask, the Anthropic SDK, MSAL (Microsoft Graph), APScheduler, and gunicorn.

---

### Step 2: Create Your .env File

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in every section:

#### Azure AD / Microsoft Graph (required)

```
AZURE_TENANT_ID=your-directory-tenant-id
AZURE_CLIENT_ID=your-application-client-id
AZURE_CLIENT_SECRET=your-client-secret-value
EMAIL_ADDRESS=yourname@thegolffellowship.com
```

**Setup steps:**
1. Go to https://portal.azure.com → **App registrations** → **New registration**
2. Under **API permissions**, add **Microsoft Graph** → **Application permissions**:
   - `Mail.Read` (required — reads transaction emails)
   - `Mail.Send` (optional — for daily digest and messaging)
3. Click **Grant admin consent**
4. Under **Certificates & secrets**, create a new client secret
5. Copy the Tenant ID, Application (client) ID, and secret value into `.env`

#### Anthropic API Key (required)

```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

Get one at https://console.anthropic.com/settings/keys. This is used to parse each email with Claude AI. Cost is roughly $0.01-0.03 per email.

#### Connector / Webhook (optional)

```
CONNECTOR_API_KEY=your-random-secret-key
```

Generate a secure key:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

This enables the `POST /api/connector/ingest` webhook endpoint. External systems must send this key in the `X-API-Key` header.

#### Daily Email Report (optional)

```
DAILY_REPORT_TO=yourname@thegolffellowship.com
DAILY_REPORT_HOUR=7
```

This sends a styled HTML digest of the last 24 hours of transactions at the specified hour. Uses Microsoft Graph API (Mail.Send permission) to send. Set timezone with `DAILY_REPORT_TZ=US/Central`.

#### App Settings

```
CHECK_INTERVAL_MINUTES=15
SECRET_KEY=change-me-to-a-random-string
```

Generate a secret key:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

### Step 3: Start the App

#### For testing / development:

```bash
python3 app.py
```

Open http://localhost:5000 in your browser. Click **Check Now** to scan your inbox immediately.

#### For production (recommended):

```bash
gunicorn app:app --bind 0.0.0.0:5000 --workers 2 --timeout 120
```

---

## Automation: Run 24/7 Without Thinking About It

The app already auto-checks your inbox every 15 minutes (configurable) and sends the daily report on schedule. But you need the app itself to stay running. Here's how to make it start on boot and stay alive.

### Option A: systemd (Linux servers — recommended for production)

Create a service file:

```bash
sudo nano /etc/systemd/system/tgf-tracker.service
```

Paste this (adjust paths to match your setup):

```ini
[Unit]
Description=TGF Transaction Tracker
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/Main/transaction-tracker
Environment=PATH=/home/your-username/Main/transaction-tracker/venv/bin:/usr/bin
ExecStart=/home/your-username/Main/transaction-tracker/venv/bin/gunicorn app:app --bind 0.0.0.0:5000 --workers 2 --timeout 120
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tgf-tracker     # start on boot
sudo systemctl start tgf-tracker      # start now
sudo systemctl status tgf-tracker     # check it's running
```

Useful commands:
```bash
sudo systemctl restart tgf-tracker    # restart after config changes
sudo journalctl -u tgf-tracker -f     # view live logs
```

### Option B: launchd (Mac — runs on boot)

Create a plist file:

```bash
nano ~/Library/LaunchAgents/com.tgf.tracker.plist
```

Paste this (adjust paths):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tgf.tracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/your-username/Desktop/Main/transaction-tracker/venv/bin/gunicorn</string>
        <string>app:app</string>
        <string>--bind</string>
        <string>0.0.0.0:5000</string>
        <string>--workers</string>
        <string>2</string>
        <string>--timeout</string>
        <string>120</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/your-username/Desktop/Main/transaction-tracker</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/tgf-tracker.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/tgf-tracker-error.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.tgf.tracker.plist
```

The app will now start automatically whenever you log in to your Mac and restart if it crashes.

Useful commands:
```bash
launchctl stop com.tgf.tracker        # stop
launchctl start com.tgf.tracker       # start
launchctl unload ~/Library/LaunchAgents/com.tgf.tracker.plist  # disable
cat /tmp/tgf-tracker.log              # view logs
```

### Option C: Cloud Deployment (shareable link for managers)

For a public URL your managers can bookmark:

**Railway (recommended — free tier):**
1. Go to https://railway.app and sign up with GitHub
2. Click **New Project** > **Deploy from GitHub Repo**
3. Select this repo, set the root directory to `transaction-tracker`
4. Add your environment variables (from .env) in the Railway dashboard
5. Railway will give you a public URL like `https://tgf-tracker.up.railway.app`

**Render:**
1. Go to https://render.com and sign up
2. Click **New Web Service** > Connect your repo
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
5. Add your environment variables in the Render dashboard

**DigitalOcean / VPS:**
1. Spin up a $6/mo droplet (Ubuntu)
2. Clone the repo, install Python, create venv, install deps
3. Set up the systemd service (Option A above)
4. Point a domain to the server IP
5. (Optional) Put nginx in front for HTTPS

---

## Using the Dashboard

### Search and Filter

- Type in the **search box** to search across all columns
- Use the **column filter dropdown** to search within a specific field only (e.g., just Side Games)
- Use the **sort dropdown** or **click column headers** to sort by any field

### Export

Click **Export CSV** to download all transactions as a spreadsheet. The CSV includes every column: date, customer, item, price, city, course, handicap, side games, tee choice, member status, golf or compete, post game, shirt size, guest name, order ID, and more.

### Manual Actions

- **Check Now** — scan inbox immediately instead of waiting for the next scheduled check
- **Send Report** — send the daily transaction email report right now (shows when DAILY_REPORT_TO is configured)

---

## Webhook Connector

When `CONNECTOR_API_KEY` is set, external systems can push data in via `POST /api/connector/ingest`.

### Push structured items directly

```bash
curl -X POST https://your-domain.com/api/connector/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-connector-api-key" \
  -d '{
    "items": [{
      "email_uid": "ext-001",
      "item_index": 0,
      "merchant": "The Golf Fellowship",
      "customer": "John Doe",
      "order_id": "R123456",
      "order_date": "2026-02-11",
      "item_name": "Feb 22 - LaCANTERA",
      "item_price": "$158.00",
      "city": "San Antonio",
      "course": "LaCANTERA",
      "side_games": "NET Points Race",
      "handicap": "12",
      "tee_choice": "<50 | 6300-6800y",
      "member_status": "MEMBER = $158",
      "golf_or_compete": "COMPETE"
    }]
  }'
```

### Send raw email text for AI parsing

```bash
curl -X POST https://your-domain.com/api/connector/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-connector-api-key" \
  -d '{
    "raw_email": {
      "uid": "ext-002",
      "subject": "New Order #R999999",
      "from": "noreply@mysimplestore.com",
      "text": "The Golf Fellowship\nNew order from: Jane Smith\n..."
    }
  }'
```

---

## API Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | None | Web dashboard |
| GET | `/api/items` | None | All item rows as JSON |
| GET | `/api/stats` | None | Summary stats (items, orders, total, date range) |
| POST | `/api/check-now` | None | Trigger manual inbox check |
| DELETE | `/api/items/:id` | None | Delete an item row |
| GET | `/api/config-status` | None | Check which services are configured |
| POST | `/api/connector/ingest` | X-API-Key | Push items or raw email via webhook |
| GET | `/api/connector/info` | None | Connector endpoint documentation |
| POST | `/api/report/send-now` | None | Trigger daily report email immediately |

---

## Database

SQLite, stored at `transaction-tracker/transactions.db`. Each row is a single line item:

| Column | Example |
|--------|---------|
| `item_name` | Feb 22 - LaCANTERA |
| `item_price` | $158.00 |
| `customer` | Kenneth Carter |
| `order_id` | R854482675 |
| `order_date` | 2026-02-10 |
| `city` | San Antonio |
| `course` | LaCANTERA |
| `handicap` | 12 |
| `side_games` | NET Points Race, City Match Play |
| `tee_choice` | <50 \| 6300-6800y |
| `member_status` | MEMBER = $158 |
| `golf_or_compete` | COMPETE |
| `post_game` | YES |
| `returning_or_new` | Returning |
| `shirt_size` | XL |
| `total_amount` | $163.53 |
| `merchant` | The Golf Fellowship |

---

## Project Structure

```
transaction-tracker/
├── app.py                    # Flask app, routes, scheduler, webhook
├── requirements.txt          # Python dependencies
├── .env.example              # Configuration template
├── .gitignore
├── test_parser.py            # Parser tests (uses mocked AI responses)
├── email_parser/
│   ├── __init__.py
│   ├── fetcher.py            # Microsoft Graph email fetching
│   ├── parser.py             # Claude AI email parsing
│   ├── database.py           # SQLite storage layer
│   ├── report.py             # Daily digest email (Graph API)
│   └── rsvp_parser.py        # Golf Genius RSVP parsing
├── templates/
│   ├── index.html            # Transactions dashboard
│   ├── events.html           # Events management + Tee Time Advisor
│   ├── customers.html        # Customer directory + roster import
│   ├── audit.html            # Email audit/QA (admin)
│   ├── rsvps.html            # RSVP management
│   ├── matrix.html           # Side games prize matrix
│   └── changelog.html        # Version changelog
└── static/
    ├── css/
    │   └── dashboard.css     # Dashboard styles
    └── js/
        └── dashboard.js      # Dashboard interactivity
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'flask'` | Activate the venv: `source venv/bin/activate` |
| `ANTHROPIC_API_KEY not configured` | Add your key to `.env`. Get one at https://console.anthropic.com/settings/keys |
| `Login failed` / `Authentication failed` | Double-check Azure AD credentials (tenant ID, client ID, secret) in `.env` |
| `Graph API error` | Verify Mail.Read permission is granted and admin-consented in Azure portal |
| App finds no emails | Click **Check Now**. Verify your App Password works. Check that transaction emails exist in the last 90 days. |
| AI returns no items | Check the Anthropic API key is valid and has credits. View logs for error details. |
| Daily report not sending | Verify `DAILY_REPORT_TO` is set in `.env` and Mail.Send permission is granted. Check logs for Graph API errors. |
| `Address already in use` | Another instance is running. Stop it first, or change the port. |
| Connector returns 401 | Verify the `X-API-Key` header matches your `CONNECTOR_API_KEY` in `.env` exactly. |

---

## Costs

- **Anthropic API**: ~$0.01-0.03 per email parsed (Claude Sonnet). At 50 orders/month, that's roughly $0.50-1.50/month.
- **Hosting**: Free on Railway/Render free tier. $5-6/mo for a VPS.
- **Everything else**: Free (SQLite, Flask, email via Microsoft Graph API).
