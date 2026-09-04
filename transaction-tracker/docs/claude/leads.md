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
| dial | `lead_sms_presets` | JSON preset copy merged per key over the ratified defaults (P1–P4 carry `tue`/`sat`/`both`, others `text`; plus `closer` and `p9`). |
| Railway env | `META_ACCESS_TOKEN` | Marketing API token for the campaign stats META panel (hourly insights); until set, the campaign's manual spend drives CPL / CPP / CPMem. |
| dial | `lead_outreach_tags` | Tags that arm the 48-hour alarm. Default Texted / Sent email / Left VM. |
| dial | `lead_touch_owners` | `{"San Antonio": "Kerry", "Austin": "Robert", "default": "Kerry"}` — the `{owner}` voice per chapter. |

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

## Notes log + first-touch SMS (#361, presets #383 → #388/#389)

`lead_notes` table (lead_id FK, author, note, timestamps) —
`add_lead_note` / `POST /api/leads/<id>/note` / bridge
`scoring-lead-note:<id>|<author>|<text>`. Newest note previews on the
card and in the desktop row. The mobile card is a call
sheet: badge chips (Availability/Importance/Invitations + ad-set tag),
sms:/tel:/mailto: action row, status dot, sticky one-line summary,
primary action + ⋯ overflow.

**SMS presets (Kerry-ratified 2026-09-02 evening, reviewed one by
one — mailbox #388, add-on #389; v2.291.0).** The 💬 Text deep-link is
pre-filled from a preset SET keyed on the survey answers the card
already badges, picked server-side per lead (`select_sms_preset`) and
switchable from the ▾ next to 💬 Text (mobile action row and the
desktop contact column): preview of the exact text, the preset list,
and a ☐ Add offer line toggle.

| Preset | Fires when | Slot |
|---|---|---|
| P1 Competition · P2 Golf · P3 Community · P4 All of it | Importance answer (blank → P4) | Availability: Tue → "Tuesday nights"/`{next_tue}`; Sat → "Saturday 18s"/`{next_sat}`; Both → "Tuesday 9s and a Saturday 18 each month"/`{next_event}`; blank → Tue |
| P6 No days | Availability "Neither, still interested" — regardless of importance | none |
| P7 Second touch · P7b (4+ days) | status touched, no human reply (no hot tag, no note by a person — HS/GG/auto notes don't count) 2+ / 4+ days after `touched_at` | none |
| P8 Re-submitter | HS "Re-submitted the FB survey" note, or a customer with real purchase history | none |
| P9 both-cities add-on | NOT a preset (#389): appended as its own line after the closer question of whichever P1–P4 / P8 fires when Invitations = Both cities | — |
| Offer line | optional append, verbatim: "$25 off your first event, plus a drink on us." | — |

Standing copy rules: no em-dashes anywhere in text-voice copy (period
or "..." instead); `{owner}` = the routed touch owner's first name
(Kerry on San Antonio, Robert on Austin — `lead_touch_owners` dial);
`{next_tue}` = the chapter's next s9./a9. event, `{next_sat}` = its
next s18./a18. (borrowing the other chapter's, tagged, when its own is
more than 3 weeks out), `{next_event}` = the next event of any kind;
TGF-chapter events count for both. Labels read "Tuesday 9/8 at
Silverhorn". Copy lives in the `lead_sms_presets` dial (JSON merged per
key over `DEFAULT_SMS_PRESETS` in `leads.py` — `{"p6": "text"}` or
`{"p1": {"sat": "..."}}`) so edits never need a deploy; a legacy
`lead_sms_template` value, if set, rides along as the "custom" preset.
Bridge: `scoring-lead-sms:<id>[|<preset>][|closer]` renders the picked
(or named) text for one lead with the selection reason. Test:
`python3 test_lead_sms_presets.py`.

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
converted · 5 dismissed; within a tier, Kerry's 12-step
availability × importance ladder (v2.267.0, 2026-08-31) ranks next —
1 Both+All · 2 Tue+All · 3 Both+Community · 4 Both+Golf ·
5 Both+Competition · 6 Tue+Community · 7 Tue+Golf · 8 Tue+Competition
· 9 Sat+All · 10 Sat+Community · 11 Sat+Golf · 12 Sat+Competition;
unlisted combos (no answer / "No days") fall below 12 — then newest
activity (latest note, else touch, else arrival) first. Newest/Oldest/Name/Status sorts
remain in the select. **Category bars, no status badges** (Kerry
2026-08-31, v2.263.0; TOUCHED split v2.265.0): in priority view the
desktop rows group under dark NEW LEADS / RESPONDED / NO RESPONSE /
MEMBERS / CONVERTED / DISMISSED bars with counts — RESPONDED = touched
with a hot tag (Call back / Interested / Coming to event) OR any
logged note (v2.265.1, Kerry: a note most likely means they replied);
NO RESPONSE = the rest of touched (note-less outreach tags or
untagged); MEMBERS (v2.266.0, "the ultimate conversion") = converted +
'Became member' tag, rendered as a TGF-orange bar with orange row edge
and a filled ★ MEMBER badge replacing the tag chip, above plain
CONVERTED (event guests). The Touched and Converted stat cards carry
sub-lines: "N responded · N no response" / "N event guests · N
members". The history flag reads "customer" (was "existing
customer") —
the bar carries the status, so the per-row status pill is gone and
the left column is just age/owner + tag chip (rows max two lines).
The pill returns only in flat sorts (Name/Newest/…) where there are
no sections. **Chapter tabs** (v2.271.0, Kerry, TGF Platform style):
the row's left edge is now a plain 8px CHAPTER color tab — Austin
`--chapter-austin` burnt orange, SA `--chapter-sa-alt` slate,
unrouted gray — replacing the old status edge (sections carry status);
mobile cards get a 6px version. Just the color, no text.

## Follow-up / snooze (mailbox #365, Kerry-ratified 2026-08-31, v2.269.0)

`leads.follow_up_at` (YYYY-MM-DD; boot ALTER migration) —
`set_lead_followup` / `POST /api/leads/<id>/followup` / bridge
`scoring-lead-edit:<id>|follow_up_at|<date>` (blank clears). ⏰ Follow
up in every row's ⋯ menu; the prompt takes a date or days-from-now.
A FUTURE date snoozes the lead into a gray SNOOZED section below
CONVERTED; on/before today (Central) it resurfaces under a red
FOLLOW-UPS DUE section at the VERY TOP, earliest date first. The
freed pill slot shows a ⏰ m/d chip (red when due); mobile card meta
carries the same chip. Dismissed leads never resurface. Round-2 companions
(v2.269.0): Converted demoted behind ⋯ + confirm (auto-detect handles
real conversions), ➕ Note promoted to primary on touched rows, modal
badge chips muted (Tu+Sa / All of it / SA invites / SA ad) so
exceptions read as signal, toolbar search box (name/email/phone).

## Drill-down triage filters (Kerry 2026-09-01, v2.280.0; MULTI-SELECT 2026-09-03, v2.293.0)

Second toolbar row: AVAILABILITY (Both|Tue|Sat|None), IMPORTANCE
(All|Golf|Competition|Community), INVITES (Both|Austin|SA|None).
`triageOf(l)` classifies off the CURRENT form's answers (rawPref
exact-key rule); unanswered questions match only when that group is
unfiltered.

**Multi-select (Kerry 2026-09-03: "allow the toggle filters to include
multiple selections so like with AVAILABILITY I could push both Sat and
BOTH so that I could see all players available for Saturdays").** Each
group is a `Set` — empty = any; picks **inside** one group OR together;
the three groups still **AND** with each other and with
chapter/status/search. Tapping a selected pick removes just that one. A
**Clear** button appears at the end of the row whenever any triage pick
is active (multi-select needs a one-tap way out). The header count
("N of M leads") reflects the combination.

The load-bearing case: Availability **Sat + Both** = everyone who can
play Saturdays, since "Both" also means Saturday-available. Same shape
for Tue + Both. Locked by `test_lead_triage_filters.js`.

## Re-submitter answer separation + real-customer badge (v2.278.1)

HubSpot merges every form submission into one contact (per-property
last-write; old questions keep old values), so a re-submitter's payload
carries BOTH surveys' answers. Rules: (1) chips and the no-loop
dismissal read the CURRENT form's exact keys first
(`LOOP_QUESTION_KEY` etc.), fuzzy match only as fallback; (2)
`_fetch_answer_history` (propertiesWithHistory; versions sorted
explicitly — never trust API element order) stamps
`payload._answer_dates` + `_answers_prev` (the earlier survey's value
for keys the new submission changed) for re-submitters, with a bounded
poll backfill keyed on the `_hist_v: 2` marker; the card renders
COLLAPSIBLE per-survey sections (v2.283.0, Kerry off the Craig Wilder
card): a dark "CURRENT SURVEY · date" band — open by default, showing
the contact's FULL current answers (an answer unchanged between
surveys keeps its old HubSpot timestamp; classifying by timestamp
alone left CURRENT empty on Wilder) — then one collapsed
"SURVEY · date" band per earlier submission date with what that
submission set (changed answers' previous values + old-stamped keys);
bands are click-to-toggle (`renderAnswerTable` + one delegated
listener), attribution rows stay below the bands, always visible, and
a 3rd+ submission automatically becomes the new CURRENT with each
older date keeping its own band; (3) the loop chip shows
"No loop" only for answers starting with "no" — a bare "Yes" from an
old form rendered "No loop" before; (4) the `customer` badge
(`has_history`) requires a non-placeholder active item — identity
shells (Roster Import etc.) don't make someone a customer.

## No-loop auto-dismiss (Kerry 2026-09-01, v2.278.0)

`dismiss_no_loop_leads(conn)` runs every poll: a lead whose
stay-in-the-loop answer starts with "no" (same key/value test the CSV
invite exports use to exclude them) self-dismisses into the bottom
DISMISSED section with an 'auto' note. Converted and already-dismissed
rows are never touched.

## Conversion evidence excludes placeholders (v2.277.1)

The 'Registered event' auto-detect requires an active item whose
merchant is NOT in `PLACEHOLDER_MERCHANTS` (leads.py mirror of
dashboard.js: Roster Import / Customer Entry / RSVP Import / RSVP
Email Link / Handicap Import) — those rows put a PERSON in the system,
not a purchase. The Oscar Gonzalez / Daniel Garza case: one 3/3
'Roster Import' row each read as a conversion though neither ever
played or paid. A poll-time heal reverts auto-tagged 'Registered
event' leads with no real purchase and no membership to status 'new'
(touched fields untouched).

## Deduped re-submitter sweep (Kerry 2026-09-01, v2.277.0)

`_fetch_hubspot_reconversions` in leads.py, run inside every poll: an
EXISTING HubSpot contact who fills the FB survey never crosses the
createdate watermark (HubSpot dedups the submission into the old
contact), so a second sweep keys on `recent_conversion_date` >
`leads_hubspot_reconv_watermark` (default 2026-08-27, the fall
campaign) and keeps only contacts whose
`recent_conversion_event_name` starts "Facebook Lead Ads:" AND whose
createdate ≠ conversion date (genuinely-new contacts ride the normal
poll). These bypass `lead_source_filter` — the conversion event IS the
filter; their years-old original analytics source would wrongly fail
it. They enter the queue with arrived_at = the conversion time, dedup
by external_id as usual, and get an author-'HS' note "Re-submitted the
FB survey — existing HubSpot contact since <date>". Existing customers
among them immediately auto-convert (Registered event / Became member)
per the standing conversion detect, which is the desired display.
First live sweep back-collects the 2026 fall campaign's five: Wilder,
Hinojosa, O. Gonzalez, M. Hernandez, D. Garza.

## Backfill + attribution fixes (platform-claude #405, v2.299.0)

**MIGRATION GAP in v2.294.0.** The 48-hour alarm only arms on a NEW
tagging, so every lead already texted before that release got nothing.
CA found 27 personally-contacted leads sitting **outside the very
conversion gate the release exists to enforce** — the exact failure mode
the feature was built to prevent.

`backfill_outreach_alarms(dry_run)` applies the same rule retroactively:
outreach-tagged + touched + no follow-up pending → `outreach_at =
touched_at`, `follow_up_at = touched_at + 2 days`, plus an auto note
saying it was backfilled. **A hand-set date is never overwritten** (the
`follow_up_at IS NULL` guard is what protects it). Idempotent. Bridge:
`scoring-outreach-backfill[:dry]`.

**THE FORWARD RULE, and it belongs in the release checklist:** any
feature that arms state on an event *going forward* needs a backfill for
the rows that predate it, or it silently under-covers exactly the
population it was built for.

**`touched_by` was NULL on every row.** Not a write bug — the Touched
button prompts for a name, but Kerry works the queue by **tagging**, and
`set_lead_tag` never captured one. It now fills from the session user
automatically (`author=session["user"]` from the tag route), so
attribution costs nobody a prompt. This is the data the chapter-manager
compensation model needs.

## Duplicate leads + merge (Kerry 2026-09-03, v2.295.0)

> "I see we have two Shane Winters. Those need to be merged. I thought
> we already merged them on HubSpot side."

**Why it happens, and why it will recur.** The Tracker dedups on
`(source, external_id)` = the HubSpot contact id. Two rows appear when
the same person submits the survey twice before HubSpot dedups them, or
when Kerry merges two HubSpot contacts **after** the Tracker already
polled both. **A HubSpot-side merge does not propagate back** — nothing
tells the Tracker those two contact ids are now one person.

`find_duplicate_leads()` groups live rows by **email** (case/whitespace
normalized), **phone** (last 10 digits, so `+1` and `(210) 875-4541`
match), and **full name**, and names a suggested keeper: strongest
status, then most notes, then a real customer link, then earliest
arrival. Bridge `scoring-lead-dupes` — compact by design, no payloads.

`merge_leads(keep, drop, dry_run)` folds the loser into the keeper:
notes move across, the **strongest status** and its tag win, the
**earliest** arrival / touch / conversion dates win (the true first
contact), any field blank on the keeper fills from the loser, and
payload keys the keeper lacks are recovered so **an earlier survey's
answers are never lost** (the keeper's own answer still wins a
conflict). An auto note records the merge on the keeper.

**The loser is never deleted.** It is marked `merged_into` + dismissed
and filtered out of every queue read (`get_leads` requires
`merged_into IS NULL`). Deleting it would free its `external_id` and the
next poll would re-create the duplicate. `scoring-lead-merge:<keep>|<drop>[|dry]`,
`scoring-lead-unmerge:<drop>`. Test: `test_lead_merge.py` (28 checks).

**Merged rows and campaign stats (v2.295.1).** A merged loser keeps its
`campaign_id`, so every campaign read must skip it or one person counts
as two leads (inflating leads, deflating CPL). The funnel query, the
campaign list's `lead_count`, and the auto-linker all filter
`merged_into IS NULL`. Every other queue path is already safe because
merged rows are also dismissed. Locked in `test_lead_campaigns.py`.

## 48-hour outreach alarm (Kerry 2026-09-03, v2.294.0)

> "Need a timestamp with alarm set when I click Texted or Emailed for
> someone for the first time. That should auto set a 48 hour alarm that
> resets when I change status or add a note, which probably signifies
> that there's been a response."

Tagging an **outreach** action stamps `leads.outreach_at` (new column,
the precise Central timestamp) and sets `follow_up_at` to **+2 days**,
so the alarm rides the follow-up rails that already exist — the ⏰ chip,
the FOLLOW-UPS DUE section at the top of the queue, and the due-day
email ping (#370). **No second notification system.** An auto note
records it: *"Texted 9/3, 3:45 PM — 48-hour follow-up set for 9/5."*
The chip's hover text distinguishes an auto alarm from a hand-set date.

**Outreach tags** — `lead_outreach_tags` dial over
`DEFAULT_OUTREACH_TAGS` = Texted · Sent email · **Left VM**. Kerry named
Texted and Emailed; Left VM is the same "reached out, now waiting" case
so it ships armed, and the dial drops it in one edit.

**"For the first time"** — the alarm arms only when **no follow-up date
is already pending**, so re-tagging never pushes the date out. A date
Kerry set **by hand** has `outreach_at` NULL and is never armed over,
and never cleared by any of the resets below. `outreach_at NOT NULL` is
precisely what marks a date as the auto alarm.

**Resets (a response happened) — `_clear_outreach_alarm`:**

| Trigger | Clears? | Why |
|---|---|---|
| Any **real status change** (`mark_lead`, old ≠ new) | yes | he acted on it |
| Re-marking the status it already had | **no** | nothing changed |
| A **note by a person** | yes | Kerry's stated signal |
| A **GG** note (RSVP) | yes | a real member action (the RSVP bridge exists for exactly this) |
| An **HS** note (re-submitted the survey) | yes | they re-engaged |
| An **`auto`** note (campaign set, selections edited) | **no** | bookkeeping, not a response |
| A **non-outreach tag** (Interested, Call back, Not now…) | yes | a disposition he only reaches for after hearing something |
| A **hand-set** follow-up date | never | his own intent |

After a reset, tagging Texted again arms a fresh 48 hours. Locked by
`test_lead_outreach_alarm.py` (21 checks, including that an armed lead
is picked up by `check_followup_due_pings` on its due day).

## Due-day ping (mailbox #370, Kerry-ratified 2026-08-31, v2.272.0)

`check_followup_due_pings` in leads.py — runs at the TOP of every
leads poll (before the HubSpot token check, so a missing token or a
failed fetch never swallows it). On a lead's follow-up due morning it
emails the routed chapter owner once — recipients via the same
`lead_notify_recipients` dial as the new-lead ping (default/Kerry +
the chapter's own list; unrouted fans out to everyone). Delivery is
gated to ≥ 7 AM Central so the first post-7AM poll sends, never a
midnight one. Dedup via `leads.follow_up_notified_for` (boot ALTER):
it stores the `follow_up_at` value that was pinged, so each due date
emails exactly once and a re-snooze to a new date re-arms
automatically; an overdue date never pinged still pings once.
Dismissed leads never ping. Email = name, date, tag, contact,
chapter, latest note, Lead Center link. This completes the
anti-March-347 loop: snooze → resurface → ping. Tests in
test_leads_export.py.

## RSVP → lead-note bridge (Kerry 2026-08-31, v2.268.0)

`sync_lead_rsvp_notes` in leads.py — the Alex Porter case: a lead
answering a GG invite (even Not Playing) is a response signal. Each
RSVP matching a lead (customer_id first per rule 6, else
case-insensitive email) becomes one automatic note — author 'GG',
text "RSVP'd Playing/Not Playing — <event>", created_at = the RSVP's
received time — which promotes the lead to RESPONDED under the
notes-count-as-response rule. Idempotent (dedup on exact note text
per lead; a changed answer is new text → its own note). Runs after
every RSVP inbox ingest (app.py check_rsvp_inbox) and as a sweep at
the end of every leads poll (backfill + non-inbox paths).

## Edit selections (Kerry 2026-09-02, v2.287.0)

"I need to be able to edit Lead selections" — Mick Hernandez (lead 63)
lives in SA, plays Austin occasionally, and asked off the Austin
invites; his FB answer still said "Both", so the Austin invite CSV
kept him. ⋯ → **Edit selections** on every card (desktop details panel
/ mobile Details): Availability, Importance, Invitations as selects
over the EXACT Facebook option values (`MANUAL_ANSWER_OPTIONS` in
leads.py — every badge, filter and CSV rule keys on those strings),
plus City (free text) and Chapter (auto / SA / Austin). `POST
/api/leads/<id>/answers` → `set_lead_answers`:
- overrides are stored in `payload["_manual"]` (+ `_manual_meta`
  {by, at, was}) and re-applied by `apply_manual_answers` inside the
  <48h re-sync AND the standing self-heal, so HubSpot's stale answer
  never comes back;
- an Invitations change re-routes the chapter via
  `route_chapter_from_payload` (single-chapter answer → that chapter;
  "Both" leaves the current chapter); an explicit Chapter pick wins;
  "No invitations" is left to the no-loop auto-dismiss on the next poll;
- the card shows "· edited by Kerry 9/2 (was Both)" on the row and an
  `auto` note records every change; agent action log
  `lead-answers-edit`.
Bridge: `scoring-lead-edit:<id>|availability|<raw option>` (also
importance / invitations / city) goes through the same editor.

## Campaign entity + campaign stats view (mailbox #391, Kerry-ratified 2026-09-03, v2.292.0)

`email_parser/campaigns.py`. **Entity:** `lead_campaigns` (name UNIQUE,
source ∈ meta/organic/manual/historical, meta_campaign_id, start_date,
end_date, spend_manual, notes) + `leads.campaign_id` +
`leads.converted_at`; `lead_campaign_insights` caches the Meta pull per
campaign. Seeded once with the current campaign **Fall 2026 Leads**
(Meta 120253511733060195, 8/27–9/6). Leads auto-link from the
payload's `ad_campaign_id` (hsa_cam) on every read; organic /
unattributed leads are assignable from the ⋯ menu (**Campaign…**) or
`scoring-lead-campaign:<lead>|<campaign|none>` (auto note). A manual
assignment is never overwritten by the auto-link.

**Metric definitions (Kerry's, verbatim):** CPL = ad spend / leads ·
CPP = Cost Per Player = ad spend / unique leads who became a PLAYER
(registered any event OR became a member; counts once) · CPMem = Cost
Per Member = ad spend / leads who became members (never "CPM"). Each
reported CURRENT and **30-DAY TRAILING**: conversions counted through
`end_date + 30` (the honest read 30 days after the last dollar); while
that window is open the trailing figure equals current and the panel
says when it closes. `converted_at` stamps on every conversion path
(auto-detect + `mark_lead`), backfilled from `touched_at` for rows
converted before the column existed.

**Funnel vocabulary:** touched = touched + converted; responded = hot
tag / human note / converted (HS/GG/auto notes don't count);
interested = tag Interested or Coming to event; players = converted;
members = converted + Became member; per-chapter split (SA / Austin /
unrouted).

**META panel:** spend, impressions, reach, frequency, link clicks, CTR,
CPM, leads (with Meta's own form-lead count beside the Tracker's),
CPL — from the Marketing API insights edge (`/{campaign}/insights`,
`date_preset=maximum`, act_2353186181735308) once `META_ACCESS_TOKEN`
lands on Railway (hourly job `meta_insights`, cache 60 min, ↻ Refresh
Meta forces). **Fallback until then: the campaign row's manual spend**
(Set spend on the stats view, or `scoring-campaign-set:{"id":1,
"spend_manual":127.64}`) so CPL / CPP / CPMem work from day one.

**UI:** campaign `<select>` on the queue toolbar (All · each campaign ·
Unattributed / organic, with counts) filters alongside chapter/status;
**📊 Stats** toggles the queue into the stats view for the selected
campaign or all-time — META panel, FUNNEL panel with the CPL/CPP/CPMem
current + trailing table, per-chapter table, and (on All) the campaign
list. ＋ Campaign creates a row (name, Meta id, source).

Routes: `GET /api/leads/campaigns[?refresh=1]` (manager; refresh =
admin), `POST /api/leads/campaigns` (admin; create/update),
`POST /api/leads/<id>/campaign` (manager). Bridge:
`scoring-campaigns`, `scoring-campaign-set:<json>`,
`scoring-lead-campaign:<lead>|<campaign|none>`,
`scoring-campaign-refresh`. Test: `python3 test_lead_campaigns.py`.

**Deferred by design (not built):** (4) 2024–2025 backfill — create
rows with `source='historical'` + the Meta ids (Season 20 Kickoff,
9/11/25, 8/18/25, 6/11/25, 4/24/25), spend from Meta once the token
exists, leads matched from HubSpot history and assigned via
`scoring-lead-campaign`; (5) reactivation — a "Historical" campaign
row holds never-converted prior leads so they flow through the same
queue and the P8 / P7b presets. No schema change needed for either.

## Brevo member-status sync (mailbox #381, v2.287.0)

Kerry-ratified via CA: the public "TGF Insider" recap goes to everyone
in Brevo EXCEPT active members. `email_parser/brevo.py` is the first
Tracker→Brevo API brick:
- `tracker_contact_targets` — every `customer_emails` row (non-banned)
  → {email: status, chapter}; status from
  `derive_member_financial_status_bulk` mapped member→`active_member`,
  alumni→`former_member`, guest→`prospect`; a shared email keeps the
  strongest status; chapter "TGF" is treated as blank.
- `sync_member_status(dry_run)` — inventories Brevo (GET /v3/contacts,
  1000/page), ensures the TGF_MEMBER_STATUS attribute, and updates only
  contacts whose stamp differs (POST /v3/contacts/batch, 100/call; a
  batch rejection falls back to per-contact PUT). A blank Tracker
  chapter never wipes a Brevo chapter. Tracker emails missing from
  Brevo are counted; the `brevo_sync_create_missing` dial scopes what
  gets CREATED (v2.288.0/v2.289.0): blank/"0" never, "active" =
  missing active members only, "recent" = active members + anyone who
  played within 365 days (Kerry 2026-09-02, the running setting),
  "1"/"all" = every customer with an email. "Played" reuses the
  Participation definition (`last_played_by_customer`), and every
  synced contact is also stamped TGF_LAST_PLAYED (Brevo date
  attribute) for played-within-N-months segments. New contacts go to list 3 (`brevo_sync_list_id` overrides)
  with FIRSTNAME/LASTNAME/status/chapter; one import address per
  customer (primary email first) so multi-email players never become
  duplicate contacts. Summary persisted to `brevo_last_sync`.
- Chapter fallback chain (v2.289.1/v2.290.0): customers.chapter →
  the lead's routed chapter → the Brevo CITY attribute through the
  Lead Center's `route_chapter` map (`lead_city_chapters` dial over
  `DEFAULT_CITY_CHAPTERS`, then `brevo.LEGACY_CITY_CHAPTERS` for the
  DFW / Houston metros — Brevo-only, never Lead Center routing).
  Brevo-only contacts (never a Tracker customer) get ONLY TGF_CHAPTER
  from CITY, never a status; an existing chapter stamp is never
  overwritten. `city_routed` in the run summary counts them. After the
  2026-09-02 sweeps ~427 contacts remain chapterless with no CITY at
  all (2025 HubSpot imports carrying only a name + SMS).
- Scheduler: `nightly_brevo_sync` cron 09:10 UTC (4:10 AM Central);
  `BREVO_SYNC_DISABLED=1` skips scheduling. No-op until
  `BREVO_API_KEY` is set on Railway (Brevo → profile → SMTP & API →
  API Keys → new key "TGF Tracker").
- Bridge: `scoring-brevo-status`, `scoring-brevo-sync[:dry]`.
- First live run (2026-09-02 4:07 PM, key set by Kerry): 697 Tracker
  emails (141 active / 291 former / 265 prospect), 1,318 Brevo
  contacts, 396 matched and stamped, 301 Tracker emails absent from
  Brevo (untouched — dial off), 0 errors, 10.5 s.
- Brevo side (Kerry, UI): segment "Active members" =
  TGF_MEMBER_STATUS equals active_member; the public campaign sends to
  list 3 minus that segment. Segments are UI-only in Brevo's API.
Next bricks (not built): campaign recipient export (who clicked what)
onto the customer timeline; Wednesday-AM auto-draft of the public
recap (docs/claude/event-recaps.md).

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
