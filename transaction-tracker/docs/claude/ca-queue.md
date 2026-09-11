# CA QUEUE — the admin-only open-items checklist

**Kerry directed 2026-09-11** (mailbox #473 spec from platform-claude,
#474 field-shape confirmation from tracker-claude). Kerry verbatim:
"Let's create a checklist in the Tracker that I can interact with and be
able to always keep track of as a standard. You update it whenever is
necessary. Admin view only."

Why it exists: by 2026-09-11 Kerry's open items lived in mailbox digests,
handoff docs, chat, and a markdown file in Project Files — nowhere he
could check one off. The Tracker is now the record; the markdown queue
doc retires once seeded (topic `ca-queue-seed`).

## Surface

- **Page:** `/admin/ca-queue` — admin-only, gated exactly like the
  events-leaderboard pilot: route redirects non-admin to `/events`, the
  API routes are `@require_role("admin")` (401 anonymous), and the shell
  nav link ("CA Queue", desktop + drawer) carries the `admin-nav` class
  so auth.js reveals it only for admin. Never member- or manager-facing
  by Kerry's direction.
- Sections render as bands in enum order; checkbox = done; a row click
  expands to notes / add-note / mark-blocked / move / reorder (the
  three-tier disclosure rule from `ux-directive-work-surfaces.md`).
  All DONE rows collapse under one Done band at the bottom showing the
  section chip + done date + who — **done never deletes**.

## Data model — `ca_queue` (created lazily by `_ensure_ca_queue`)

id (autoincrement) · title · section · owner (free text: kerry | ca |
lane name) · status (`open | blocked | done`) · blocked_on ·
mailbox_ref (comma-separated post ids) · notes_log (append-only JSON
`[{at, author, note}]`, the leads.notes_log shape) · sort_order
(INTEGER per section) · created_at · updated_at · done_at · done_by.

Sections enum (validated in code, maps 1:1 to the master queue doc's
A–H): `kerry_decision | ca_owed | cc_build | finance_cleanup |
followups | parked | settled`.

Semantics:
- **DONE** stamps done_at/done_by and keeps the row (Done band).
- **REOPEN** (status back to open/blocked on a done row) nulls
  done_at/done_by and appends `"reopened (was done <date> by <who>)"`
  to the notes log so history survives.
- **Upsert matching:** by `id` when given, else EXACT title
  (case-insensitive, trimmed), else insert at the bottom of its section
  (`sort_order = max+1`).
- **Move** (`move_ca_queue_item`) re-sections and/or repositions
  (1-based) and densely renumbers the target section.

## Functions (email_parser/database.py)

`list_ca_queue(section, status)` → `{sections, items, n_open, n_done}` ·
`upsert_ca_queue_item(item, author)` · `note_ca_queue_item(id, note,
author)` · `close_ca_queue_item(id, author)` (thin wrapper: upsert
status=done) · `move_ca_queue_item(id, section, position, author)`.

## Access paths

| Who | How |
|---|---|
| Kerry | `/admin/ca-queue` page → `/api/ca-queue` (GET list) + POST `/upsert` `/note` `/move`, author stamped `kerry` |
| platform-claude (claude.ai) | MCP tools `list_ca_queue`, `upsert_ca_queue_item`, `note_ca_queue_item`, `close_ca_queue_item` — writes audited via `_audit` → `log_agent_action` |
| tracker-claude lanes | bridges via `probe_golf_genius` extract=: `scoring-ca-queue[|<section>[|<status>]]`, `scoring-ca-queue-upsert:<json>` (json may carry `author`), `scoring-ca-queue-note:<id>|<author>|<note>`, `scoring-ca-queue-close:<id>|<author>` |

Every write path stamps an author into the notes log and (MCP/bridge)
the agent action log, so "who changed this" is always answerable.

## Seed

platform-claude posts the seed rows as JSON (mailbox topic
`ca-queue-seed`, array of `{title, section, owner, status, blocked_on,
mailbox_ref}`) after deploy confirmation, or calls
`upsert_ca_queue_item` itself once its session picks up the new tools.

## Tests

`test_ca_queue.py` — 32 checks: insert/list grouping, enum validation,
title-match upsert, append-only notes, done-never-deletes, reopen
history note, move/reorder, partial-field updates.

## Not in v1 (deliberately)

Stale-row flag (no update in 7 days) — #473 §6, later. Notifications,
member visibility, Project-Files sync — explicitly out (#473).
