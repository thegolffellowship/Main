# New Leads — Facebook/HubSpot lead intake (v2.257.0)

Kerry-ratified via mailbox #352/#353 (2026-08-27): the Fall 2026 Meta
lead campaign's 48-hour personal touch is the conversion gate, so the
Tracker pulls new leads on a timer, queues them, and pings the touch
owners (Kerry — San Antonio, Robert Straiton — Austin) the moment one
arrives.

## Inbound path (recommended + verified)

Meta Lead Ads → **HubSpot** native integration → contact with
`hs_analytics_source = PAID_SOCIAL`, object source `FORM`. Verified live
2026-08-28: the campaign's first lead (created 03:21 UTC) is a HubSpot
contact with exactly that shape, while Brevo holds only the mailing
lists. Scheduled pull (not webhooks) is the ratified default.

## Moving parts

- `email_parser/leads.py` — the whole feature: `leads` table
  (`UNIQUE(source, external_id)` dedup; `customer_id` FK per CLAUDE.md
  rule 6, matched via `customer_emails`), the HubSpot poll
  (`check_new_leads`), chapter routing, notification email, and the
  queue read/mark API.
- Scheduler job `lead_poll` in `app.py` — every
  `LEAD_CHECK_INTERVAL_MINUTES` (default 45; 0 disables). Safe no-op
  until `HUBSPOT_TOKEN` is set.
- Routes: `/admin/leads` (page, manager+), `GET /api/leads`,
  `POST /api/leads/<id>/mark`, `POST /api/leads/<id>/edit`
  (v2.262.0 — first/last name fix via `edit_lead_identity`; syncs the
  purchase-less prospect customer, never one with purchase history;
  the UI prefills a surname guess from the email local-part),
  `POST /api/leads/poll` (admin, on-demand).
- Template `templates/leads.html` — stat cards (new / touched /
  converted / past-48h-untouched; clickable = status filter), filter
  toolbar (All | Austin | San Antonio chapter toggle + status chips +
  sort select), desktop work list + mobile call-sheet cards (below).
- Bridge commands (`mcp_server.py`): `scoring-leads[:status]`,
  `scoring-lead-mark:<id>|<status>[|<by>][|<note>]` (agent-audited),
  `scoring-leads-poll`.

## Config

| Where | Key | Meaning |
|---|---|---|
| Railway env | `HUBSPOT_TOKEN` | HubSpot private-app token, scope `crm.objects.contacts.read`. **The one thing Kerry must add** — feature idles without it. |
| Railway env | `LEAD_CHECK_INTERVAL_MINUTES` | Poll cadence, default 45. |
| dial | `leads_hubspot_watermark` | ISO high-water mark (auto-advanced each pass; default 2026-08-27T00:00:00Z = campaign start, so the first real poll backfills anything already arrived). |
| dial | `lead_source_filter` | `{"analytics_sources": [...], "object_source_labels": [...]}` — queue when either matches. Default PAID_SOCIAL/SOCIAL_MEDIA + FORM/IMPORT; store-sync INTEGRATION contacts deliberately excluded. |
| dial | `lead_city_chapters` | lowercase city substring → chapter. Defaults cover Austin + SA metro; unmatched cities route NULL. |
| dial | `lead_notify_recipients` | `{"San Antonio": [emails], "Austin": [emails], "default": [emails]}`. Default falls back to `COO_EMAIL_TO`/`EMAIL_ADDRESS`. An UNROUTED lead notifies every list — better a double ping than a missed 48-hour window. Set Robert's address here via `scoring-setting-set:lead_notify_recipients|{"Austin": ["robert@..."]}`. |

## Form-response capture (#355)

Facebook form answers arrive as HubSpot **custom contact properties**
(e.g. `can_you_play_tuesdays_or_saturdays`, `which_is_most_important_to_you`,
`chapter_interest`, `ad_variation`). For each genuinely NEW lead the poll
does a batch read against the **full portal property list** and stores
every non-empty property as JSON in `leads.payload` — excluding identity
columns and `hs_`-internals except the attribution keep-set
(`hs_analytics_source[_data_1/2]`, `hs_analytics_first_url`,
`hs_object_source_label`; `recent_conversion_event_name` has no prefix
and comes through naturally). Nothing is hardcoded to this campaign's
questions — new form fields in future campaigns are captured
automatically. The queue renders headline chips (Plays / Wants /
Chapter) + an expandable full-answers row, and the notification email
carries the answers table.

## Chapter routing (Kerry-ruled 2026-08-31, supersedes 2026-08-28)

1. **Event Invites answer** (stay-in-the-loop: `yes_for_san_antonio`)
   when it names a SINGLE chapter — it OVERRIDES the ad set (Kerry
   2026-08-31, the Renick case: SA ad set + Austin invites → Austin).
   `chapter_interest` is form boilerplate and never decides;
   'yes_for_both' carries no override.
2. **Ad set clicked** (`lead_ad_set_chapters` dial).
3. City map — last resort.
"Yes for both" + no ad set = unrouted → pings every touch owner. Routed
leads ping default + their own chapter's list only. The poll's standing
self-heal also RE-routes an already-routed lead whose single-chapter
invites answer disagrees with its stored chapter, so existing leads
flip within one poll cycle of a rule/dial change.

## Real customer_ids (Kerry 2026-08-28: "I believe we need to")

Every poll links every lead to a customers row: email match first,
otherwise created through `_resolve_or_create_customer` — the SAME
resolver save_items uses — so a later purchase lands on the same
identity. Creation requires a first AND last name (no shell profiles
from half-named FB leads; fix the name via
`scoring-lead-edit:<id>|last_name|<value>` and the next poll links it).

## Lifecycle (with undo — v2.257.12)

`new` → `touched` (stamps `touched_at`/`touched_by`) → `converted`; or
`dismissed`. Undo paths: converted → touched (stamp kept), touched →
new (stamps cleared), dismissed → new (Restore). `mark_lead('edit')`
corrects `touched_by`/`notes` without a status change. `notified_at`
records the ping. `days_since_arrival` computes off `arrived_at`
(HubSpot `createdate`, clamped ≥0); the queue paints `new` rows ≥2 days
old red.

## Queue display vocabulary (Kerry-ruled 2026-08-28)

Columns: Lead / Email / Phone (tappable mailto:/tel:) / Chapter /
**Availability** (Both · Saturdays · Tuesdays · None) / **Importance**
(Golf · Competition · All of it!) / **Invitations** (Both · San Antonio
· Austin) / Ad Set / Received (Central) / Age / Status. All headers
click-sort (default Received, newest first). Mobile (≤768px) renders
stacked cards with tap-to-call/email; its answers fold hides
Campaign/Form rows. `chapter_interest` and `ad_variation` are hidden
everywhere — form-baked constants (`austin_sa` / `city_newcomer` on
every submission). The "existing customer" badge shows ONLY when the
linked customer has active purchase history — never for the prospect
row the lead itself created. Lead-created prospects carry
`acquisition_source = 'facebook_lead'`.

## Young-lead re-sync (#360)

Two pipelines write leads into HubSpot: Privyr's bare-form push and
Meta's native lead-ads sync. When Privyr wins the creation race, the
first snapshot carries no ad attribution (native sync backfills ~15
min later). Every poll therefore re-fetches leads first seen < 48h and
updates payload-if-changed; EMPTY identity fields fill from HubSpot
(a manual scoring-lead-edit fix is never clobbered), then the standing
self-heals re-route chapter and re-derive stats.

## Disposition tags (Kerry 2026-08-28)

One current `leads.tag` per lead, orthogonal to the status pipeline.
Options are the `lead_tag_options` dial (JSON list; defaults Left VM ·
Texted · Sent email · No answer · Call back · Interested · Coming to event · Too
expensive · Not now · Bad contact · Registered event · Became member).
Tagging a NEW lead auto-marks it touched. **Deactivating tags**
(`DEACTIVATING_TAGS`: Too expensive · Bad contact, Kerry 2026-08-31):
selecting one flips the lead to dismissed — deactivated, never
deleted; the row + notes stay, it leaves the invite CSV, Restore
brings it back. A converted lead keeps its status (tag still records
the disposition). CSV export also excludes the Too expensive tag.
`ensure_leads_table` self-heals on every read/write (v2.261.1): an
active lead carrying a deactivating tag (tagged pre-feature or during
a deploy gap) is swept to dismissed. The CSV also hard-skips any
invitations answer starting with 'no' — an opt-out never rides the
routed-chapter fallback. Regression suite: `test_leads_export.py`. Surfaces:
tag picker in desktop actions + mobile action row, orange pill display,
`POST /api/leads/<id>/tag`, bridge `scoring-lead-tag:<id>|<tag>`
(empty clears; audited), `set_lead_tag`/`get_tag_options` in leads.py.

## Invite-list CSV export (Kerry 2026-08-28)

`GET /api/leads/export-csv?chapter=San Antonio|Austin` (manager+) —
First Name / Last Name / Email, handicap-export style, buttons on the
Lead Center. Membership = the lead's Invitations opt-in (yes_for_<ch> /
yes_for_both; no answer → routed chapter); excludes dismissed, Bad
contact / Not now tags, and email-less rows. `get_lead_export_rows`.

## Notes log + first-touch SMS (#361)

`lead_notes` table (lead_id FK, author, note, timestamps) —
`add_lead_note` / `POST /api/leads/<id>/note` / bridge
`scoring-lead-note:<id>|<author>|<text>`. Newest note previews on the
card and in the desktop row. The mobile card is a call
sheet: badge chips (Availability/Importance/Invitations + ad-set tag),
sms:/tel:/mailto: action row — the SMS body renders the
`lead_sms_template` dial with `{first_name}` and `{next_event}` (next
upcoming event for the lead's chapter; TGF events count for both) —
status dot, sticky one-line summary, primary action + ⋯ overflow.

## Desktop work list (Kerry 2026-08-31)

The original desktop 12-column table overflowed sideways — action
buttons off-screen ("not functional"). Replaced with a grid work list
(no horizontal scroll): STATUS FIRST per Kerry ("first thing we need
to see is status") — status pill + age + touched-by + tag in column 1,
plus a color-coded left edge (amber new / green touched / blue
converted / gray dismissed / red overdue). Then name + chapter +
received, contact links (ellipsized, `min-width:0` guards the grid),
the mobile call-sheet's triage badge chips + newest-note preview
(2-line clamp), and always-visible actions (primary status button,
➕ Note, tag picker, ⋯ overflow — desktop menu ids `ld-dmenu-<id>`,
mobile `ld-menu-<id>`). ▾ next to the name expands a details panel
(notes log + full decoded answers incl. Campaign/Form attribution).
Filter toolbar shared by desktop + mobile: All | Austin | San Antonio
segmented toggle with live counts, status chips (New / Touched /
Converted / Dismissed / Overdue) — stat cards click-filter to the same
state, click again to clear — and a sort select replacing
column-header sorts. Counts on cards and the mobile sticky summary
stay whole-queue regardless of filters; the toolbar shows "N of M
leads" when filtered. **Landing sort is PRIORITY** (Kerry 2026-08-31:
respond immediately to new arrivals and hot conversations): tier 0 new
· 1 hot tags (Call back / Interested / Coming to event) · 2 untagged
touched · 3 quiet outreach (Texted / Left VM / Sent email / No answer) · 4
converted · 5 dismissed; within a tier, newest activity (latest note,
else touch, else arrival) first. Newest/Oldest/Name/Status sorts
remain in the select. **Category bars, no status badges** (Kerry
2026-08-31, v2.263.0): in priority view the desktop rows group under
dark NEW LEADS / TOUCHED / CONVERTED / DISMISSED bars with counts —
the bar carries the status, so the per-row status pill is gone and
the left column is just age/owner + tag chip (rows max two lines).
The pill returns only in flat sorts (Name/Newest/…) where there are
no sections. Mobile call sheet unchanged.

## MCP access for CA (platform-claude)

- **`get_lead_center`** — one read: queue rows (decoded answers + ad
  attribution), per-ad-set stats, status counts, and the live dials +
  poll config. THE tool for "nuts and bolts".
- `get_tracker_docs` doc='leads.md' — this design of record.
- Ops via `probe_golf_genius` extract=: `scoring-leads[:status]`,
  `scoring-lead-mark:<id>|<status>[|<by>][|<note>]`,
  `scoring-lead-edit:<id>|<field>|<value>`, `scoring-leads-poll`.
- Dials via `scoring-setting-get/-set` (see Config table above).

## Deliberate choices

- Email ping only (no SMS): the Tracker has no SMS provider; Graph mail
  reaches Kerry's phone. If Kerry wants true texts, that's a Twilio-class
  add — new scope.
- Polling every new contact would ping on every store purchase (the
  GoDaddy→HubSpot sync creates INTEGRATION contacts) — hence the source
  filter.
- Watermark overlap is safe: dedup on the HubSpot contact id makes
  re-reads of boundary contacts no-ops.
