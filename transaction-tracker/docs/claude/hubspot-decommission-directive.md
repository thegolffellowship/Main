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
2. The reconciliation report is published, the ambiguous queue is
   worked, and **Kerry has personally ruled on every uncertain match**
   (§10, §11). No match was ever decided by us.
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

**Revised per Kerry's rulings (§9) — the two workstreams decouple.**

*Extraction track, starts after Sep 6 and does not wait for anything
else:*
1. CA details A1-A4 and gets ratification.
2. Full raw export. **Gate: verification signed off.**
3. Reconciliation: the three buckets in §11.
4. Kerry works the ambiguous queue. His answers are the decisions.
5. Import confident matches; archive the rest. No customers created for
   unmatched contacts.

*Pipe track, gated on the next live campaign:*
6. Build Meta-direct ingest behind a dial, idle until the token lands.
7. Prove the plumbing with Meta's Lead Ads testing tool.
8. **Next campaign:** dual-run and reconcile daily.
9. HubSpot pipe off; portal read-only.
10. Grace period, then Kerry decides on cancellation (~$45/month).

---

## 9. Kerry's rulings (2026-09-03, answering the open questions)

**1. The unknown contacts: ARCHIVE, not reactivation.** And more than
that — *"See if they match up with any customers we already have in your
records. One customer, one record... so merge. Ask for clarification on
ones that seem like they could be a match but are not positive."*

This makes the extraction a **customer identity reconciliation**, not a
data dump, and it is the biggest single piece of Workstream A. See §11.

**2. Dual-run: explained, and it hits a scheduling problem.** See §12 —
the Fall campaign closes Sep 6, and a side-by-side comparison proves
nothing when no leads are flowing.

**3. Cost: about $45/month.** ~$540/year. Real, but small next to the
conversion gate. It buys us the right to be unhurried about the *pipe*
half; it does not slow the *extraction* half, which can start now.

**4. Meetings and companies: archive only — but attribute to customers.**
*"Don't need any speculations though."*

---

## 10. The standing rule this creates

Kerry said it twice, about two different things: **"ask for
clarification on ones that seem like they could be a match but are not
positive"** and **"don't need any speculations."**

So, across every part of this migration:

> **Confident matches merge. Uncertain matches go to Kerry. Nothing is
> ever guessed.**

A wrong merge is worse than no merge: it silently fuses two people's
histories and there is no clean way to find it later. An unmatched
record costs nothing but a row in the archive.

---

## 11. Customer identity reconciliation (Workstream A, expanded)

Every one of the 1,453 HubSpot contacts is sorted into exactly one of
three buckets.

**CONFIDENT MATCH → merge into the existing customer.** The bar is an
exact match on normalized email, or on the last 10 digits of a phone
number, against `customer_emails` / customer contacts. Same rule the
lead de-duplicator already uses (v2.295.0).

"Merge" here means the contact's history folds into the customer that
already exists — **it never creates a second customer record**:
- notes, calls, tasks, meetings, emails → the customer's timeline,
  original author and timestamp preserved, source-marked as imported;
- original-source attribution and lifecycle history → the customer;
- any email or phone the customer does not already carry → added to
  their contact records.

**AMBIGUOUS → a review queue for Kerry, never an automatic decision.**
Everything that smells like a match without proving it:
- the name matches but neither email nor phone does;
- a nickname or spelling variant (Mike / Michael, Bob / Robert);
- one HubSpot contact matching **more than one** Tracker customer —
  which also means the *Tracker* holds duplicate customers, and there is
  existing repair machinery for that (`docs/claude/customer-merge-repair.md`,
  `merge_customers()`);
- same name, different contact details (two real people, or one person
  with a new phone — Kerry knows, we do not).

Present these as a worklist: the HubSpot record, the candidate
customer(s), what matches and what does not, and a one-tap Merge / Not
the same person / Skip. **Kerry's answer is the decision. We never
break a tie ourselves.**

**NO MATCH → archive only.** Per Kerry's ruling: archived, **not**
reactivated, and **no customer record is created**. Roughly speaking, if
several hundred of the 1,453 land here, that is several hundred rows we
deliberately do not import. The archive keeps them; the operating system
stays clean.

**Companies and meetings** follow the same rule: archive them, attribute
them to a customer **only** where the match is certain, and speculate
about nothing.

---

## 12. Dual-run, in plain terms — and the timing problem it exposes

**What a dual-run is.** For a while, both lead pipes run at the same
time. A new Facebook lead arrives through HubSpot *and* through the
direct Meta connection. Every day we compare the two lists. If they
match exactly, the new pipe is proven. If a lead shows up in one and not
the other, we find out why *before* anything is switched off. Only after
a clean stretch does the HubSpot pipe get turned off. Nothing is
switched over on a hope.

**The problem.** A side-by-side comparison needs leads to compare. The
Fall campaign closes **Sep 6**, and once the ads stop, lead flow drops to
near zero. A dual-run over a dead pipe proves nothing at all.

**Therefore, split the sequence** (proposed; Kerry to confirm):

- **Workstream A (extraction + reconciliation) starts now.** It has no
  dependency on lead flow. This is where all the irreplaceable data is
  and all the real risk.
- **Workstream B (Meta-direct ingest) is BUILT now but VALIDATED against
  the next live campaign.** Meta's own Lead Ads testing tool can prove
  the plumbing end to end without real traffic; the real dual-run rides
  the next campaign's first days.
- **HubSpot stays live until then.** At ~$45/month, waiting for a real
  campaign costs about $45–90. Getting the lead pipe wrong costs the
  48-hour window on every lead we miss. That is not a close call.

**Open for Kerry:** when is the next ad campaign expected? That date,
not a calendar guess, is what schedules the cutover.

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
