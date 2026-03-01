window.TGF_VERSION = "1.2.0";
window.TGF_CHANGELOG = [
  {
    version: "1.2.0",
    date: "2026-03-01",
    title: "Security & Code Quality Audit",
    changes: [
      "Fixed silent DB failures — errors now logged instead of swallowed",
      "AI parser now surfaces API auth and bad-request errors properly",
      "XSS protection: sanitized orphan banner DOM insertion",
      "Auto-refresh wrapped in try/catch to prevent silent failures",
      "DB connection leaks fixed with context managers",
      "Email send results now checked and reported to frontend",
      "SECRET_KEY validation at startup — app refuses to run without it",
      "Input validation on user JSON for all DB operations",
      "RSVP popover event listener leak fixed",
      "Added .get() guards on all API endpoints",
      "NOT NULL constraints on customer/item_name columns",
      "Case-insensitive duplicate checks for events",
      "DOM null reference guards across all pages",
      "Amount input prevents multiple decimal points",
      "Override objects cleaned up on event collapse (memory fix)",
      "Accessibility: aria-required, aria-label, role=dialog on modals",
      "CSS cleanup: replaced !important with variables and specificity",
      "Consolidated onclick handlers to event delegation pattern",
      "Moved function-level imports to module level",
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
