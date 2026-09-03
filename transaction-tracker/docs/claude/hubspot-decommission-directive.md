# HubSpot Decommission + Meta-Direct Lead Ingest — Scoping Directive

**To:** platform-claude (CA)
**From:** Kerry, via tracker-claude
**Date:** 2026-09-03
**Status:** SCOPING. Nothing is built until Kerry ratifies the plan.

> "Yes scope it. We need to decommission HubSpot as soon as it is safely
> viable. Of course we need to extract every bit of data we've stored on
> HubSpot before we do that." — Kerry, 2026-09-03

---

## 1. Why now

HubSpot has exactly one live job left: it is the pipe that carries Meta
lead-form submissions into the Tracker. Marketing email moved to Brevo
(#381, live). The forms are Meta-native, not HubSpot forms. The Tracker
holds the operational truth for customers, money, events, and now leads.

That single remaining job is also the source of a whole class of bugs we
have paid for repeatedly:

- **Duplicate leads** (v2.295.0, Kerry's two Shane Winters) — the Tracker
  dedups on HubSpot's contact id, so a HubSpot-side merge never
  propagates back.
- **Merged-survey answers** (v2.278.1, the Garza card) — HubSpot merges
  every submission into one contact, so a re-submitter's payload carries
  two surveys at once and the card mixed them.
- **The re-submitter sweep** (v2.277.0) — an existing contact's new
  submission never moves `createdate`, so it needed a whole second
  watermark and a `recent_conversion_date` sweep to be seen at all.
- **Latency** — a 15-minute poll standing between a lead and the
  48-hour clock that is our conversion gate.

Every one of those is a HubSpot dedup artifact, not a Facebook one.
Going direct to Meta does not merely remove a hop; it deletes the
category.

---

## 2. What Meta-direct buys, and what it does not

**Buys:**
- Lead rows in **seconds** (webhook) instead of up to 15 minutes.
- **One row per submission**, with Meta's own `leadgen_id`. The Tracker
  becomes the dedup authority, on identity (email / phone), using the
  merge built in v2.295.0.
- Both surveys of a re-submitter arrive as **two clean rows**, correctly
  dated, instead of one contact carrying two sets of answers.
- One less vendor, one less token, one less failure mode.

**Does not buy, and this is the load-bearing caveat:**
- **Meta is not an archive.** Lead retrieval from the Lead Ads API has a
  limited retention window — CA must confirm the current documented
  window before we depend on it. Anything older than that window exists
  **only** in HubSpot. This is precisely why extraction is a gate and
  not a follow-up.
- It does not carry the hand-written history in §3. Meta never had it.

---

## 3. What is actually in HubSpot (live inventory, portal 23917509, 2026-09-03)

| Object | Count | Assessment |
|---|---:|---|
| **CONTACT** | **1,453** | Oldest is Feb 2023 — about 3.5 years. The Lead Center holds 86. |
| **EMAIL** (logged) | 469 | Email activity against contacts. |
| **COMPANY** | 130 | Mostly auto-created from email domains; low value, verify. |
| **TASK** | 118 | Real follow-ups, e.g. "Follow up with Leon McLin". |
| **CALL** | 24 | Back to 2023. |
| **MEETING_EVENT** | 22 | Includes read.ai calendar noise; triage. |
| **NOTE** | 15 | **Highest value per row.** Hand-typed context, e.g. *"8/28 - going out of country. Said he'll sign up when he gets back and it gets cooler."* |
| **OBJECT_LIST** | 3 | Small; confirm none is load-bearing. |
| **DEAL** | **0** | Never used. Nothing to migrate. |

**The real risk is not the contact rows.** Those largely exist elsewhere
already — Brevo holds 1,381 contacts, the Tracker holds customers with
purchase history. The irreplaceable material is the **hand-written
context and the attribution history**: the 15 notes, 118 tasks, 24
calls, 469 email records, each contact's original-source attribution
(`hs_analytics_source`, first URL, first/recent conversion events), the
lifecycle-stage history, and the per-property change history the Tracker
currently reads only for survey-answer keys.

**None of that is anywhere else.** Lose it and we lose why a member
first found us and what somebody promised them on a phone call in 2023.

---

## 4. Workstream A — EXTRACTION (this is the gate)

**Principle: extract, verify, and prove the archive is complete and
readable BEFORE a single byte of ingest changes.** Kerry's words: "of
course we need to extract every bit of data we've stored on HubSpot
before we do that."

**A1. Full raw export first, before any interpretation.** Every object
type in §3, every property (not a curated subset), every association,
plus per-property history where HubSpot exposes it. Land it as dated
JSON in the repo or OneDrive as the immutable archive. Raw first means a
mistake in our interpretation is recoverable; a lossy export is not.

**A2. A reconciliation report, before anything is deleted.** For all
1,453 contacts: how many the Tracker already knows by email, how many
Brevo knows, how many are unknown to both. That third number is the
migration's actual scope and nobody knows it today. Publish it before
proposing what to import.

**A3. Import what belongs in the operating system.** Proposal for CA to
refine and Kerry to ratify:
- **Notes, calls, tasks, meetings** → the `lead_notes` timeline on the
  matching lead, or a new customer-level timeline where there is no
  lead. Preserve the original author and timestamp; mark the source so
  an imported 2023 note never reads as something typed yesterday.
- **Original-source attribution** → onto the customer record. This is
  the "where did this member come from" history that answers questions
  we cannot answer today.
- **Contacts unknown to both systems** → a decision for Kerry, not for
  us. They may be stale 2023 records, or a dormant audience worth
  reactivating through the "Historical" campaign already designed for in
  the campaign entity (#391 item 5).
- **Companies, lists, meetings** → triage, likely archive-only.

**A4. Verification, and it must be adversarial.** Row counts per object
type, archive versus source. Spot-check the oldest and newest of each.
Confirm every note, task, and call is readable in its new home. **A
signed-off verification report is the gate.** Not "the script finished."

---

## 5. Workstream B — INGEST (only after A is verified)

**B1. Webhook first, poll as the backstop.** Meta's leadgen webhook
fires on submission; a reconciliation poll every N minutes catches
anything the webhook dropped. Webhooks fail silently, and a missed lead
is a missed 48-hour window. Never webhook-only.

**B2. Dedup moves in-house.** Meta gives one row per submission with a
`leadgen_id`. The Tracker dedups on that, then applies identity matching
(email / phone) through the v2.295.0 merge to catch the same person
twice. This is strictly better than HubSpot's contact-id semantics
because *we* control the rule.

**B3. Dual-run, never a hard swap.** Run Meta-direct alongside the
HubSpot poll for a defined period. Every lead should arrive by both
paths; reconcile daily; investigate any divergence. Only when the two
agree for the full window does HubSpot's pipe get switched off. Priya's
rule: no big-bang cutovers on the thing that makes the money.

**B4. Preserve the shape.** Chapter routing, the source filter, survey
decoding, the 48-hour alarm, the SMS presets, campaign linking — all of
it keys off the payload the poll produces today. Meta-direct must
produce the **same normalized payload shape**, so every downstream rule
keeps working untouched. If a field cannot be reproduced from Meta,
name it before we build, not after.

---

## 6. Definition of "safely viable"

HubSpot goes read-only when **all** of these are true. Any one missing
means not yet:

1. The full raw archive exists, is verified per §A4, and is stored
   somewhere that is backed up.
2. The reconciliation report is published and Kerry has ruled on the
   contacts unknown to both systems.
3. Notes, calls, tasks, and attribution are imported and visible in the
   Tracker.
4. Meta-direct ingest has dual-run with zero unexplained divergence for
   the agreed window.
5. Nothing else in the business still reads HubSpot. Audit for it
   rather than assuming.

**Then read-only, not deleted.** Keep the portal (free tier if a paid
plan can be dropped) for a grace period after cutover. Cancelling the
subscription and deleting the data are two different decisions taken at
two different times.

---

## 7. What Kerry provisions

- **Meta Page access token with lead-retrieval permission**, and the
  webhook subscription on the lead-form page. Same shape as the insights
  token in #391 — worth doing both at once.
- **HubSpot private-app token scoped for the export**: read on contacts,
  companies, notes, calls, tasks, meetings, emails, lists, plus
  associations and property history. The current token is contacts-read
  only and will not cover the archive.
- **A decision on the HubSpot plan and its cost.** Sarah's question: what
  are we paying today, and does dropping to free during the grace period
  save it without losing the archive?

---

## 8. Sequence

1. **After Sep 6** (campaign close — do not touch the pipe while it is
   carrying live leads).
2. CA scopes A1-A4 in detail and gets Kerry's ratification.
3. Export + reconciliation report. **Gate: verification signed off.**
4. Import notes / calls / tasks / attribution.
5. Build Meta-direct ingest behind a dial, idle until the token lands.
6. Dual-run and reconcile.
7. HubSpot pipe off; portal read-only.
8. Grace period, then Kerry decides on cancellation.

---

## 9. Open questions for Kerry

1. **The unknown contacts.** If several hundred of the 1,453 are in
   neither the Tracker nor Brevo, is that an archive or a reactivation
   list? (Ties to #391 item 5.)
2. **How long a dual-run** before we trust Meta-direct? One week of
   leads, or two?
3. **Plan and cost** — what is HubSpot billing today?
4. **Meetings and companies** — archive-only, or is anything in there
   worth operating on?

---

## 10. What could go wrong, stated plainly

- **Meta's retention window bites.** If it is shorter than we assume and
  the archive is incomplete, we lose lead history permanently. Mitigated
  entirely by doing extraction first, which is why it is the gate.
- **A dropped webhook silently loses a lead.** Mitigated by the
  reconciliation poll in B1.
- **A payload-shape mismatch** quietly breaks routing or the survey
  decode. Mitigated by B4 and the dual-run.
- **Scope creep into "while we're in there."** This project is: get the
  data out, change the pipe. It is not a CRM redesign.
