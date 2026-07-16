# TGF Governance Library

**OneDrive = authoritative · Tracker copy = enforcement mirror · updates
arrive via the platform mailbox and are committed verbatim.**

This directory holds the ratified TGF standards the Tracker must build
against. It is surfaced through `get_tracker_docs` (namespaced as
`governance/<name>`) so the rulings load in every session's start-up reads.

Governance docs are **mirrors**, not working drafts: the canonical copy lives
in Kerry's OneDrive. When platform-claude posts an update (topic
`platform-governance` / `platform-scoring-golive`) or Kerry uploads a new
version, it is committed here **verbatim** — no editorial changes. Enforcement
notes and cross-references to Tracker code belong in `docs/claude/*.md`, not
in these mirror files.

## Contents (seeded 2026-07-16, Kerry-approved)

Pending intake from platform-claude / Kerry:
- `TGF_Handicap_Standard_v1_0.md` — the ratified handicap standard (D1/D4/
  R1/R2/R3, layering principle, retroactivity boundary). Enforcement mirror
  of the rulings captured in `docs/claude/handicaps.md` +
  `docs/claude/handicap-projection.md`.
- CTA & Color Standard
- Season-contest payout spec
- Decision captures

Each governance doc carries the header rule above at its top.
