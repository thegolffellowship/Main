window.TGF_VERSION = "1.1.0";
window.TGF_CHANGELOG = [
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
