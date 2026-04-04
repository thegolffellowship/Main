window.TGF_VERSION = "1.5.0";
window.TGF_CHANGELOG = [
  {
    version: "1.5.0",
    date: "2026-04-04",
    title: "COO Agent Foundation: Allocation Tracking, Course Cost Infrastructure, list_events MCP Tool",
    changes: [
      "Multi-entity accounting system — track income/expenses across TGF, Personal, and future entities with transaction splitting",
      "AI Bookkeeper — auto-categorizes transactions using learned rules + Claude AI, with event-aware suggestions",
      "CSV bank import with smart auto-detect column mapping (Chase, Amex, Wells Fargo supported)",
      "Transfer auto-detection and cross-account linking during CSV import",
      "Standard accounting categories — IRS Schedule C business, personal finance, and TGF-specific categories",
      "Event linking on transaction splits — associate expenses with specific TGF events",
      "Course surcharge field on events — per-player surcharges (e.g. $1 ACGT printing fee)",
      "Allocation tracking table — breaks down every GoDaddy order into course payable, prize pool, TGF operating, GoDaddy fee, and tax reserve",
      "Allocation calculation engine with membership and season contest support",
      "list_events MCP tool — exposes event pricing data to Claude for COO agent queries",
      "Version sync — all version references now consistent at v1.5.0",
    ],
  },
  {
    version: "1.3.0",
    date: "2026-03-04",
    title: "Messaging, Roster Import & RSVP Linking",
    changes: [
      "Bulk email messaging for events — compose, preview, send to filtered audiences with reusable templates",
      "Message templates — create, edit, delete reusable email templates with variable placeholders",
      "Message log — track all sent messages per event with delivery status",
      "Excel roster upload — bulk import customers from spreadsheets with column detection and email matching",
      "Structured name fields — first/last/full names with AI parsing and validation",
      "Customer aliases — link alternate emails, phones, and names to a single customer record",
      "Add Customer button on Customers page — create customers manually without a transaction",
      "Customer Info panel — read-only default with Transactions/Info tab toggle on customer cards",
      "Customer update API — edit customer details (email, phone, chapter, status) inline",
      "Link to Customer on RSVP Log — connect unmatched RSVPs to existing customers",
      "New Customer from RSVP — create a customer record directly from an unlinked RSVP entry",
      "Auto-resolve RSVP player names from known customer emails",
      "WD (withdrawal) action for event players — mark players as withdrawn with credit tracking",
      "Player card editing on Events page — inline edit player details on mobile cards",
      "Extra email recipients — add CC recipients when sending event reminders",
      "NET/GROSS/NONE connected toggle group — unified button bar replacing separate dropdowns",
      "Audit date range and limit controls — filter audit emails by 7/14/30/90 days",
      "Autofix confirmation + undo — preview changes before applying, one-click rollback",
      "Re-extract fields audit tool — backfill new item fields from original email text",
      "Customer email/phone backfill in Autofix All",
      "RSVP full-name and email backfill in Autofix All",
      "Support feedback system — collect and review user feedback with daily digest emails",
      "Test digest button on Audit > Feedback tab",
      "Fix OAuth flow for Claude.ai MCP connector — PKCE + stateless HMAC tokens",
      "Mobile improvements — merge/edit/delete on cards, game stat badges on collapsed cards",
      "Exclude non-transaction placeholder rows from Transactions and Events views",
      "Pin mcp, uvicorn, and a2wsgi dependency versions"
    ]
  },
  {
    version: "1.2.0",
    date: "2026-03-01",
    title: "Audit Hardening",
    changes: [
      "Log database errors instead of silently swallowing them",
      "AI parser now surfaces API auth and bad-request errors properly",
      "Add managed_connection context manager to prevent DB connection leaks",
      "Wrap auto-refresh intervals in try/catch to prevent silent failures",
      "Fix XSS risk in orphan banner — replaced inline onclick with data-attribute handlers",
      "Email send results now checked and reported to frontend",
      "Warn at startup if SECRET_KEY is not set in environment",
      "Add input validation (type/length) on mutation API endpoints",
      "Fix RSVP popover event listener leak on repeated clicks",
      "Added .get() guards on all API endpoints",
      "NOT NULL constraints on customer/item_name columns",
      "Add database index on transaction_status column",
      "Tighten scheduler race condition with PID-based guard",
      "Case-insensitive customer name matching in merge",
      "DOM null reference guards across all pages",
      "Fix amount inputs to prevent multiple decimal points",
      "Clean up cached RSVP overrides when collapsing events",
      "Accessibility: aria-required, aria-label, role=dialog on modals",
      "CSS cleanup: replaced !important with variables and specificity",
      "Consolidate inline onclick handlers to addEventListener pattern",
      "Move inline imports to module level",
      "Removed dead code and redundant imports"
    ]
  },
  {
    version: "1.1.0",
    date: "2026-02-26",
    title: "Add Player Overhaul + GG Dot States",
    changes: [
      "Redesigned Add Player dialog with 3 modes: Manager Comp, RSVP Only, Paid Separately",
      "GG RSVP dot now has 4 states: blank, auto-green (GG Playing), red (GG Not Playing), manual-green (manager confirmed)",
      "RSVP-only players can be upgraded to full registration via Record Payment action",
      "Skins label now shows '1/2 Net Skins' when <8 gross players, 'Skins Gross' when ≥8",
      "Fixed skins NO_EVENT display bug (was showing — $0 NaN)",
      "Added Side Games Matrix page with 9/18 toggle and inline editing",
      "Populated Net and Gross data for 2-3 players in games matrix",
      "Added version display and changelog page"
    ]
  },
  {
    version: "1.0.0",
    date: "2026-02-20",
    title: "Initial Release",
    changes: [
      "Transaction dashboard with email parsing",
      "Events page with registration tracking and side games",
      "Customer directory",
      "RSVP Log from GolfGenius",
      "Audit Log with data quality checks",
      "Mobile-responsive design"
    ]
  }
];
