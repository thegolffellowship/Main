# The Golf Fellowship

Platform repository for The Golf Fellowship — a golf club operating across San Antonio, Austin, DFW, and Houston.

## Repository Structure

```
Main/
├── index.html                  # Static landing / sign-in page
├── css/styles.css              # Landing page styles
├── js/signin.js                # Landing page form validation
├── .mcp.json                   # MCP server config for Claude Code
│
└── transaction-tracker/        # TGF Transaction Tracker (main app)
    ├── app.py                  # Flask backend (~6200 lines, 200+ routes)
    ├── email_parser/           # AI email parsing, database layer, RSVP
    ├── templates/              # 15 Jinja2 HTML templates
    ├── static/                 # CSS + JS (dashboard, accounting, COO, auth)
    ├── PROJECT.md              # Full project documentation
    ├── PLATFORM_SPEC.md        # Technical spec, architecture, known concessions
    └── README.md               # Setup guide
```

## Transaction Tracker

The primary application — an AI-powered event and financial management platform.

**Live:** https://tgf-tracker.up.railway.app

### Key capabilities

- **Email parsing** — Microsoft Graph API fetches transaction emails; Claude AI extracts every field automatically
- **Event management** — Registrations, RSVPs (Golf Genius sync), cancellation/credit flows, tee time planning
- **Customer identity** — Canonical `customers`/`customer_emails` tables as single source of truth; 5-step lookup cascade
- **Unified financials** — `acct_transactions` flat ledger + bank reconciliation (Chase, Frost, Venmo CSV/PDF import)
- **COO Dashboard** — AI chat with 6 specialist agents (Financial, Operations, Course Correspondent, Member Relations, Compliance, Chief of Staff)
- **Handicaps** — 9-hole WHS index calculator with Golf Genius sync
- **TGF Payouts** — Tournament prize tracking with screenshot import via Claude Vision
- **MCP server** — 31 tools for Claude (Desktop or Code) to directly query/modify the database

See `transaction-tracker/PROJECT.md` for full documentation and `PLATFORM_SPEC.md` for architecture and technical debt notes.
