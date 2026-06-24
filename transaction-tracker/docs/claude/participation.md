# Participation Analysis — `/participation`

Identifies players by **last-event date**, **12-month frequency**, and **trend vs the prior 12 months**. Powers the page used to spot dormant players and send re-engagement emails.

## What counts as "played"

A row in `items` qualifies as an event participation when ALL of these hold:

- `customer_id` is non-null (anonymous rows excluded).
- `COALESCE(transaction_status, 'active') IN ('active', 'rsvp_only')` — both paid registrations and RSVP-only event rows count. Credit/refund/transferred/withdrawn rows are excluded.
- `UPPER(item_name)` does **not** contain `'MEMBERSHIP'` (renewals are not playing).
- `UPPER(item_name)` does **not** contain `'SEASON CONTEST'` (enrollments are not playing).
- `parent_item_id IS NULL` (child payment rows skipped — they're payments against an existing event registration, not new participations).

The single source-of-truth for this filter is `_participation_event_filter_sql(alias)` in `app.py`. Reuse it if you add another participation-style endpoint so the definition can't drift.

## Audience

Every customer where:

- `customers.account_status = 'active'` (excludes archived / banned).
- The canonical status (latest `customer_statuses.status_name`, falling back to `customers.current_player_status`) is NOT one of: `former`, `expired_member`, `inactive`. So MEMBER / MEMBER+ / GUEST / 1st TIMER all appear, including guests who came once and never returned — which is part of the value of the tool (re-engage trial guests too, not just drifting members).

Surface labels are mapped in `_get_participation_rows`'s `label_map`:
`member|active_member → MEMBER`, `member_plus → MEMBER+`, `guest|active_guest → GUEST`, `1st_timer|first_timer → 1st TIMER`.

## Frequency + trend math

- `plays_12mo` = participations with `order_date >= DATE(today_central, '-12 months')`.
- `plays_prior_12mo` = participations in `[today − 24 months, today − 12 months)` (excludes the most recent 12, so this is a true prior-period comparison, not running-total).
- `trend` is `'up' | 'down' | 'flat' | 'new'`. `'new'` is reserved for `plays_prior_12mo == 0 AND plays_12mo > 0` so the UI can highlight first-year players differently from a year-over-year increase.
- `trend_delta` = `plays_12mo - plays_prior_12mo` (signed integer).

`today` is `today_central_str()` so the 12-month boundary doesn't roll over at 00:00 UTC. See `CLAUDE.md → Timezone`.

## Endpoints (all `@require_role("manager")`)

| Route | Purpose |
|---|---|
| `GET /participation` | Render `templates/participation.html`. |
| `GET /api/participation/players` | One row per audience customer (see above). Response: `{as_of, default_subject, default_body_html, rows: [...]}`. |
| `POST /api/participation/preview-email` | `{customer_id, subject, body_html}` → renders merged subject + HTML for that one player. Returns 404 if the id isn't in the current audience. |
| `POST /api/participation/send-email` | `{customer_ids: [...], subject, body_html}` → renders + sends per recipient via `send_mail_graph` (same Microsoft Graph hook the handicap cards use). Returns `{requested, sent, skipped, failed, results: [{customer_id, name, email, status, reason?}]}`. Each successful send is logged via `log_message` with `event_name='participation-reengagement'`. |

The default subject + body live in `PARTICIPATION_DEFAULT_SUBJECT` / `PARTICIPATION_DEFAULT_BODY_HTML` constants at the top of the participation routes block in `app.py`. Edit those to change the shipped default; per-send edits in the composer override them.

## Merge variables

| Variable | Source |
|---|---|
| `{first_name}` | `customers.first_name`, falls back to `"there"` if blank. |
| `{last_name}`  | `customers.last_name`. |
| `{days_since}` | Days between today (Central) and `last_event_date`. `"—"` if never played. |
| `{last_event}` | `last_event_date` (YYYY-MM-DD), or `"—"`. |
| `{last_event_phrase}` | `" (on YYYY-MM-DD)"` when there's a date, else empty — used so the default copy reads naturally either way. |
| `{chapter}` | `customers.chapter`, falls back to `"TGF"`. |
| `{plays_12mo}` | `plays_12mo` integer. |

Bracket-unsupported / typo merge keys are tolerated: a `KeyError`/`IndexError` during `str.format` falls back to the raw template instead of crashing the send.

## UI behaviour notes (`templates/participation.html`)

- Stats: Active Customers / Dormant ≥ threshold / Avg days since / Never played. "Never played" is its own bucket and counts as dormant when a threshold is selected.
- Sortable headers (Player, Chapter, Status, Last Played, Days, 12mo, Prior 12, Trend). Default sort: `days_since DESC` (most dormant on top). Never-played rows sort to the top when sorting Days DESC.
- "Has email only" filter ON by default so the visible audience matches who can actually be re-engaged. Toggle off to see no-email rows too.
- Select-all-visible **skips no-email rows** (selecting them is pointless — the send endpoint would skip them anyway).
- Composer preview is a live `/preview-email` call with a 400ms debounce on subject/body edits; Prev/Next scrubs through selected recipients so you can sanity-check the merge on a few before sending.
- Send is gated behind a `confirm()` dialog with the recipient count; success clears the selection, failure leaves it intact so you can retry without re-selecting.

## Not yet implemented (deferred)

- **Saving custom templates** — every send currently reads the in-page composer. If we want named templates (e.g. "Warm nudge", "Schedule-focused", "Free round offer"), add a `participation_email_templates` table keyed by `(name, body_html, subject)` and a small picker dropdown above the subject field.
- **Outreach history** — there's no per-customer "last contacted on" column yet. The `log_message` event with `event_name='participation-reengagement'` is recorded, so a `MAX(message.created_at) WHERE event_name='participation-reengagement' AND recipient_address=...` can be added to the players query when needed.
- **Scheduled sends** — only ad-hoc bulk sends today. A cron-style "automatically nudge players who hit 120 days dormant once per quarter" is a natural extension but needs a state table to avoid re-sending.
