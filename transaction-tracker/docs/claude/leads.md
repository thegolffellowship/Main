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
  `POST /api/leads/<id>/mark`, `POST /api/leads/poll` (admin,
  on-demand).
- Template `templates/leads.html` — stat cards (new / touched /
  converted / past-48h-untouched), queue table with red overdue rows,
  Touched / Dismiss / Converted buttons.
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

## Chapter routing (Kerry-ruled 2026-08-28)

1. **Ad set clicked** (`lead_ad_set_chapters` dial) — primary.
2. **Event Invites answer** (stay-in-the-loop: `yes_for_san_antonio`) —
   `chapter_interest` is form boilerplate and never decides.
3. City map — last resort.
"Yes for both" + no ad set = unrouted → pings every touch owner. Routed
leads ping default + their own chapter's list only.

## Real customer_ids (Kerry 2026-08-28: "I believe we need to")

Every poll links every lead to a customers row: email match first,
otherwise created through `_resolve_or_create_customer` — the SAME
resolver save_items uses — so a later purchase lands on the same
identity. Creation requires a first AND last name (no shell profiles
from half-named FB leads; fix the name via
`scoring-lead-edit:<id>|last_name|<value>` and the next poll links it).

## Lifecycle

`new` → (button/bridge) → `touched` (stamps `touched_at`, `touched_by`)
→ `converted`; or `dismissed`. `notified_at` records the ping.
`days_since_arrival` is computed server-side off `arrived_at`
(HubSpot `createdate`); the queue paints `new` rows ≥2 days old red.

## Deliberate choices

- Email ping only (no SMS): the Tracker has no SMS provider; Graph mail
  reaches Kerry's phone. If Kerry wants true texts, that's a Twilio-class
  add — new scope.
- Polling every new contact would ping on every store purchase (the
  GoDaddy→HubSpot sync creates INTEGRATION contacts) — hence the source
  filter.
- Watermark overlap is safe: dedup on the HubSpot contact id makes
  re-reads of boundary contacts no-ops.
