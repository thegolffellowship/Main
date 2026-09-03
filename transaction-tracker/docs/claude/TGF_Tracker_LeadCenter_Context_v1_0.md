# TGF TRACKER — LEAD CENTER, CAMPAIGN STATS & DATA SAFETY CONTEXT
**Version:** 1.0
**Created:** September 3, 2026
**Status:** In Progress — infrastructure done, extraction not started
**Tracker versions covered:** v2.292.0 → v2.296.0 (all on `main`)
**Repo:** thegolffellowship/Main → `transaction-tracker/`

---

## SITUATION SUMMARY

A single long working session that did three things: finished the Lead
Center's campaign measurement layer on live Meta data, fixed a class of
duplicate-lead bugs caused by HubSpot, and closed the largest
operational risk in the business — the Tracker's database had no real
backup. Kerry provisioned every API credential live during the session.
The HubSpot decommission is now scoped and gated, but not begun.

---

## CONFIRMED DATA / DECISIONS — DO NOT RE-DERIVE

### Metric definitions (Kerry, ratified 2026-09-03)
- **CPL** = ad spend / leads
- **CPP** (Cost Per Player) = ad spend / unique leads who registered any
  event OR became a member. A lead who did both counts once.
- **CPMem** (Cost Per Member) = ad spend / leads who became members.
  Never abbreviate "CPM" — that means cost-per-mille in the Meta panel.
- Each reported **CURRENT** and **30-DAY TRAILING** (conversions counted
  through `end_date + 30`, because conversions keep arriving after spend
  stops). While that window is open, trailing equals current.

### Live campaign data (verified 2026-09-03 19:40 UTC)
Fall 2026 Leads · Meta campaign `120253511733060195` · 8/27–9/6

| Metric | Value |
|---|---:|
| Spend | $129.05 |
| Impressions | 14,477 |
| Reach | 6,885 |
| Frequency | 2.10 |
| Link clicks | 404 |
| CTR | 6.49% |
| CPM | $8.91 |
| CPL | $1.63 (attributed) / **$1.52 (true)** |
| CPP | $25.81 |
| CPMem | $43.02 |

### Attribution loss — measured, not theoretical
Meta reports **85** form leads. The Tracker holds **79 attributed + 6
"unattributed/organic" = exactly 85**. Those 6 are NOT organic — their
`hsa_*` tracking parameters did not survive the HubSpot hop. **~7% of
leads lose campaign attribution in transit.** This is the concrete
argument for direct-Meta ingest.

### Historical advertising (verified retrievable from Meta today)
**34 campaigns back to April 2025, ~$2,897.61 total spend.** Six are
lead campaigns:

| Campaign | Spend | Leads | CPL |
|---|---:|---:|---:|
| 6/11/25 | $357.17 | 87 | $4.11 |
| 4/24/25 | $181.25 | 45 | $4.03 |
| Season 20 Kickoff | $345.00 | 91 | $3.79 |
| 8/18/25 | $132.49 | 39 | $3.40 |
| 9/11/25 v3 | $246.09 | 85 | $2.90 |
| **Fall 2026** | **$128.35** | **85** | **$1.51** |

$1,390.35 over 432 leads, blended CPL $3.22. **The current campaign is
the best ever run by a wide margin** — roughly double the efficiency of
the previous best. Kerry plans NEW creative for the next campaign, so
what changed here is worth preserving deliberately.

**Split to remember:** historical campaign STATS come from Meta;
historical LEAD ROWS come from the HubSpot export. Meta's lead-row
retention is short. Two halves, two sources.

### HubSpot inventory (portal 23917509, pulled 2026-09-03)
CONTACT **1,453** (oldest Feb 2023) · EMAIL 469 · COMPANY 130 ·
TASK 118 · CALL 24 · MEETING 22 · NOTE **15** · LIST 3 · DEAL 0.
Cost **$42.64/mo** (Starter Customer Platform $20 + extra core seat $20
+ tax). **388 of 1,453** flagged as "marketing contacts" of a 1,000 tier.

**The irreplaceable material is NOT the contact rows** — Brevo holds
1,381 and the Tracker holds customers with purchase history. It is the
hand-written context and attribution: the notes, tasks, calls, emails,
and each contact's original-source record.

### Kerry's rulings
1. **Unknown contacts → ARCHIVE, not reactivation** — but they still get
   a customer record. *"I want to match up everything possible into
   single customer entities. So 'archived' really just means not active,
   or they opted out."* The customer table is TGF's **identity spine
   back to 2007**, not a list of active people.
2. **Standing rule:** confident matches merge, uncertain matches go to
   Kerry, **nothing is ever guessed.** A wrong merge silently fuses two
   people's histories; an unmatched record costs one row.
3. **Opted-out is its own concept**, not a flavor of inactive.
   **Archived is a STATE (ours to change); opted-out is a PROMISE
   (theirs, survives every migration).** Likely wants per-channel
   consent fields with date and source.
4. **PARKED, explicitly:** whether an active member can fully opt out.
   The real line is transactional vs marketing. **Do not design it in
   passing.**
5. **Cutover gate is FIELD PARITY, not duration.** Kerry: *"because
   Facebook is the source, I don't see a real need, as long as we're
   definitely capturing the full detail that Facebook currently APIs to
   HubSpot."* Correct — one origin means the paths cannot disagree on
   facts, only on completeness.
6. Next campaign starts when this one ends (after Sep 6), with new
   creative — so live leads keep flowing and the overlap is free.

### Schema facts confirmed
- `customers.account_status` — CHECK (active | inactive | banned).
  Banned already honored by the Brevo sync (Paul Wuerdeman, Bob North).
- `customers.acquisition_source` — existing home for HubSpot attribution.
- `customers.current_player_status` — active_member | expired_member |
  active_guest | inactive | first_timer.

---

## WORK COMPLETED THIS SESSION

- **v2.292.0** Campaign entity + 📊 Stats view (META + FUNNEL panels,
  CPL/CPP/CPMem current + trailing, per-chapter split).
- **v2.292.1** Removed the per-ad-set line from the queue header
  (Kerry: *"way too much going on up top"*); moved into Stats.
- **v2.293.0** Multi-select triage filters — Sat + Both = everyone
  Saturday-available.
- **v2.294.0** 48-hour outreach alarm on Texted / Sent email / Left VM.
- **v2.295.0** Duplicate-lead detection + merge.
- **v2.295.1** Fixed a bug in my own v2.292.0: merged rows would have
  double-counted in campaign stats.
- **v2.296.0** Nightly off-site database backups. **Restore drill
  passed.**
- Three directives written and posted to CA (see Documents below).

---

## CURRENT STATUS BY COMPONENT

| Component | Status |
|---|---|
| Campaign stats | ✅ Live on real Meta data, hourly refresh |
| Duplicate merge | ✅ Shane Winters merged, 0 duplicates across 85 leads |
| 48-hour alarm | ✅ Live |
| Multi-select filters | ✅ Live |
| Nightly backups | ✅ Live, drill passed |
| HubSpot export access | ✅ 9 scopes granted; engagements need my connector |
| Meta lead ingest | ⛔ Needs `leads_retrieval` use case on TGF App |
| HubSpot extraction | ⛔ Not started — this is the gate |
| Historical backfill | ⛔ Scoped, data confirmed retrievable |
| Lead Center UX | ⛔ With CD, awaiting canvas |

---

## CREDENTIALS PROVISIONED THIS SESSION

| Where | What | Notes |
|---|---|---|
| Railway | `META_ACCESS_TOKEN` | System User "TGF Tracker" (61593721125795), **non-expiring**, read-only: ads_read, pages_read_engagement, pages_show_list |
| HubSpot | Service key widened to 9 scopes | **Value did NOT rotate** — `HUBSPOT_TOKEN` untouched |
| Azure | `Files.ReadWrite.All` granted + consented | On existing "Transaction Tracker" app (`12a3c30e-e2f5-48b3-98ee-b767c567fd2f`) |

**Meta app:** TGF App `1418313969582528`, business `155477436882192`.
**Ad accounts assigned:** The Golf Fellowship LLC + legacy `46071351`
(holds old campaign history — Kerry confirmed).

### Scopes that are NOT available and why it does not block us
- `communication_preferences.statuses.batch.read` — tier-gated. We have
  the per-contact read: slower, not blocked.
- `marketing.campaigns.read` — tier-gated, irrelevant (stats come from
  Meta, attribution from the contact property).
- **notes / calls / tasks / meetings — do not exist in the Service Keys
  catalog at all.** Service Keys is beta with a narrower catalog than
  the old private apps. **Resolution: Claude pulls those 179 records
  directly through the HubSpot connector.** The archive is a one-time
  job and does not need to run on Railway.

---

## ITEMS STILL NEEDED / OPEN QUESTIONS

- [ ] Add the Lead Ads **use case** to TGF App so `leads_retrieval`
      becomes available (only when Workstream B starts)
- [ ] Azure **client secret expiry date** — created 2/22/2026; when it
      expires, email parsing stops dead and looks like "no new orders"
- [ ] **Vercel is on the Hobby plan**, which prohibits commercial use.
      Pro is $20/mo. Fix before Platform launch — failure mode is the
      project being pulled, not an invoice.
- [ ] **198 MB SQLite file** — understand what dominates it before it
      becomes a performance problem
- [ ] Second backup destination (currently OneDrive only, same M365
      tenant as TGF email)
- [ ] Platform stack decision — implied by tooling, never actually made

---

## DOCUMENTS / FILES IN HAND

In-repo (`transaction-tracker/docs/claude/`):
- `hubspot-decommission-directive.md` — full scope, Kerry's rulings
- `railway-api-setup.md` — every credential, scopes, priority order
- `database-backup-gap.md` — the risk, the fix, the passed drill
- `ux-directive-work-surfaces.md` — Lead Center UX for CA + CD
- `leads.md` — updated with every feature above

Mailbox posts: #393 (UX directive), #394/#395/#396 (HubSpot
decommission + Kerry's rulings), session digest.

---

## KEY DECISIONS & NOTES

- **Extraction is the GATE, not a follow-up.** Nothing about the lead
  pipe changes until the archive is verified.
- **Raw export before interpretation** — a bad reading is recoverable, a
  lossy export is not.
- **A merged duplicate is never deleted.** Its `external_id` must stay
  or the next poll re-creates it.
- **Verification means a signed-off report**, not "the script finished."
- **Read-only before deletion.** Cancelling the HubSpot subscription and
  destroying the data are two decisions at two different times.

---

## NEXT SESSION GOALS

1. HubSpot **raw full export** + the three-bucket reconciliation.
2. Pull the 179 engagement records via the Claude connector.
3. Work the ambiguous-match queue with Kerry.
4. Historical campaign backfill from Meta (34 campaigns).
5. Lead Center UX build once CD delivers the canvas.

---
*Created September 3, 2026 | Source: TGF Tracker session, Claude Code*
