# Transaction Email Tracker

Automatically scans your email inbox for transaction/receipt emails, extracts purchase data (merchant, amount, date, items, order ID), and displays everything in a searchable, sortable web dashboard.

## Features

- **Automatic inbox scanning** — connects via IMAP and checks for new transaction emails on a configurable interval
- **Smart parsing** — recognizes receipts from 25+ common merchants (Amazon, PayPal, Venmo, Apple, Uber, banks, etc.) and extracts amounts, order IDs, and line items
- **Web dashboard** — view all transactions in a clean, sortable table
- **Search & filter** — search by merchant, amount, subject, or date
- **CSV export** — download your transactions as a spreadsheet
- **SQLite storage** — zero-config database, no external services needed

## Quick Start

### 1. Install dependencies

```bash
cd transaction-tracker
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure email credentials

```bash
cp .env.example .env
```

Edit `.env` with your email settings:

```
EMAIL_HOST=imap.gmail.com
EMAIL_PORT=993
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
CHECK_INTERVAL_MINUTES=15
SECRET_KEY=change-me-to-a-random-secret-key
```

**Gmail users:** You need an App Password, not your regular password:
1. Enable 2-Factor Authentication on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Generate an App Password for "Mail"

### 3. Run the app

```bash
python app.py
```

Open http://localhost:5000 in your browser.

### 4. Production deployment (optional)

```bash
gunicorn app:app --bind 0.0.0.0:5000
```

## How It Works

1. **Fetch** — Connects to your inbox via IMAP and retrieves emails from the last 90 days
2. **Filter** — Identifies transaction emails by sender domain and subject keywords
3. **Parse** — Extracts merchant name, total amount, date, line items, and order IDs using pattern matching
4. **Store** — Saves parsed transactions to SQLite (deduplicates by email UID)
5. **Display** — Serves a web dashboard with search, sort, and CSV export

## Project Structure

```
transaction-tracker/
├── app.py                    # Flask app, routes, scheduler
├── requirements.txt          # Python dependencies
├── .env.example              # Configuration template
├── .gitignore
├── email_parser/
│   ├── __init__.py
│   ├── fetcher.py            # IMAP email fetching
│   ├── parser.py             # Transaction data extraction
│   └── database.py           # SQLite storage layer
├── templates/
│   └── index.html            # Dashboard HTML
└── static/
    ├── css/
    │   └── dashboard.css     # Dashboard styles
    └── js/
        └── dashboard.js      # Dashboard interactivity
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web dashboard |
| GET | `/api/transactions` | All transactions as JSON |
| GET | `/api/stats` | Summary statistics |
| POST | `/api/check-now` | Trigger manual inbox check |
| DELETE | `/api/transactions/:id` | Delete a transaction |
| GET | `/api/config-status` | Check if email is configured |
