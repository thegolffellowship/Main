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

Kerry, 2026-09-03: *"Biggest thing I think is to get all the necessary
APIs setup thru Railway that you need."*

**Full step-by-step checklist: `docs/claude/railway-api-setup.md`** —
what each variable unlocks, which token type, exact permissions and
scopes, and the order to do them in. Summary:

| Variable | Unlocks |
|---|---|
| `HUBSPOT_EXPORT_TOKEN` | the archive. **Highest priority — the only irreplaceable data here.** The current token reads contacts only; notes, calls, tasks and emails are invisible to it. |
| `META_ACCESS_TOKEN` | live campaign stats + the historical backfill (§9A). |
| `META_PAGE_TOKEN` | direct lead rows. |
| `META_APP_SECRET` + `META_WEBHOOK_VERIFY_TOKEN` | real-time lead delivery. |

The three Meta values come from one System User — one sitting in
Business Settings, not three. Cost is settled: ~$45/month.

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

## 9A. Historical advertising history (Kerry, 2026-09-03 — NEW REQUIREMENT)

> "One of the things we need to make sure and capture from HubSpot is
> historical Lead Campaign data and if we can, connect with Facebook for
> those old campaign stats to populate that data to be able to see those
> campaigns isolated and everything altogether for our historical
> advertising efforts."

**Answer: yes, Meta still has all of it.** Verified live 2026-09-03 via
the Meta connector against `act_2353186181735308`: **34 campaigns back
to April 2025, ~$2,897.61 of spend**, every one still returning full
lifetime insights. This is no longer a hypothetical — it promotes #391
item 4 from "deferred" to a funded piece of this project.

**The six lead campaigns, worst CPL to best:**

| Campaign | Ran | Spend | Leads | CPL |
|---|---|---:|---:|---:|
| 6/11/25 | Jun 2025 | $357.17 | 87 | $4.11 |
| 4/24/25 | Apr 2025 | $181.25 | 45 | $4.03 |
| Season 20 Kickoff | Feb–Mar 2026 | $345.00 | 91 | $3.79 |
| 8/18/25 | Aug 2025 | $132.49 | 39 | $3.40 |
| 9/11/25 v3 | Sep 2025 | $246.09 | 85 | $2.90 |
| **Fall 2026 Leads** | **Aug–Sep 2026** | **$128.35** | **85** | **$1.51** |

**$1,390.35 across 432 leads, blended CPL $3.22.** The remaining
~$1,507 is event, landing-page and brand promotion — Kerry said
"historical advertising efforts," so those belong in the picture too,
even though only lead campaigns produce CPL / CPP / CPMem.

**What to build:**
1. **Backfill campaign rows from Meta**, not by hand — name, id, dates
   and spend all come from the insights call. `source='meta'`.
2. **Attach historical leads to them.** HubSpot's `hs_analytics_first_url`
   carries `hsa_cam` (campaign), `hsa_grp` (ad set) and `hsa_ad` — the
   same fields the auto-linker already reads. So every historical lead
   in the HubSpot export self-attributes to its campaign with the
   existing logic. This is why the export must keep `hs_analytics_*`.
3. **Isolated and combined views** — the stats view already does both
   ("All campaigns" versus one). Backfilled rows just appear.
4. **Non-lead campaigns** are spend-and-reach only; their funnel columns
   should read as not-applicable rather than as zeros, or they will drag
   the blended numbers into nonsense.

**Caveat to verify, not assume:** insights for old campaigns are
retrievable today, but Meta's *lead-row* retention is a different and
shorter thing. The historical **stats** come from Meta; the historical
**lead rows** come from the HubSpot export. Both halves are needed and
they come from different places.

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

**NO MATCH → still becomes a customer record, marked not-active.**

*(Kerry corrected an earlier reading of this on 2026-09-03. The first
version of this document said unmatched contacts would be archived
WITHOUT creating a customer. That was wrong.)* His words:

> "No, I think archived DOES have a customer record. Considering that
> we're bringing in more and more historical records from Golf Genius
> and eventually will go back to the beginning in 2007, I want to match
> up everything possible into single customer entities. So 'archived'
> really just means not active, or they opted out or whatever. We may
> also have some like Paul Wuerdeman and Bob North that we have 'banned'
> from participation."

**The customer table is the single identity spine for TGF, back to
2007.** Not a list of currently-active people. Golf Genius history is
still arriving and will keep arriving; every person who has ever touched
TGF should exist exactly once, and "archived" is a *state on that
record*, not a reason to withhold it.

**The schema already supports this** — no new concept required:
- `customers.account_status` — CHECK constraint on `active` / `inactive`
  / `banned`. Paul Wuerdeman and Bob North are the `banned` case, and it
  is already honored: the Brevo sync and other outbound paths exclude
  banned rows today.
- `customers.acquisition_source` — the existing home for HubSpot's
  original-source attribution. No new column needed.
- `customers.current_player_status` — `active_member` / `expired_member`
  / `active_guest` / `inactive` / `first_timer`.

**RULED (Kerry, 2026-09-03): opted-out is its own thing, not a flavor of
inactive.** His reasoning: *"opted out relates to communication
correspondence that we absolutely need to honor for our TGF Platform
build and future consolidated communications, so I think it needs it's
own thing."*

The distinction that makes it load-bearing: **archived is a state,
opted-out is a promise.** Archived describes where someone stands with
TGF and can be changed by us. Opted-out is something a person told us,
it survives every future migration and platform rewrite, and honoring it
is not optional. Folding it into `inactive` would eventually get it
overwritten by a status change nobody thought twice about.

**Design implication:** consent should not live on `account_status` at
all. A single status column cannot express "active member who does not
want the newsletter." Consent is orthogonal to standing, so it wants its
own field(s) — and the Platform will consolidate communications across
email, SMS and the member portal, so it likely wants consent **per
channel**, with the date and source of the opt-out recorded.

**PARKED — Kerry, explicitly for another day:** *"An active member
should not be able to completely opt out of communications...I
think...that's for another day to decide."*

Real question, correctly deferred. There is a genuine difference between
**transactional** messages a member cannot opt out of and still be a
member (your tee time moved, your payment failed, the event is
cancelled) and **marketing** messages anyone may refuse at any time.
That split is also what keeps a business on the right side of consent
law. **Do not design this in passing** — it needs its own conversation,
and the extraction only has to capture whatever HubSpot already records
about consent so the decision has data behind it when Kerry takes it up.

**Companies and meetings** are archive-only, but attributed to a
customer wherever the match is certain — same no-speculation rule.

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

**Kerry's answer (2026-09-03), and he is right:** *"because Facebook is
the source, I don't see a real need, as long as we're definitely
capturing the full detail that Facebook currently APIs to HubSpot."*

Correct, and it reframes the test. Facebook is upstream of both paths,
so there is no second source of truth that could *disagree* with the
first. Two systems reading one origin cannot diverge on the facts. The
only real risk is **field completeness** — that Meta-direct silently
hands us less than HubSpot was handing us.

**So the gate is a FIELD PARITY PROOF, not a duration.** Before
cutover, take a set of leads that already arrived through HubSpot, pull
the same leads directly from Meta, and diff them field by field. Every
field any downstream rule depends on must be present and identical:
- the three survey answers, at their exact raw option values (the
  routing, badges, CSV filters and SMS preset selection all key on those
  exact strings);
- identity: first name, last name, email, phone, city;
- attribution: campaign id, ad set id, ad id, form name, submission
  timestamp;
- anything else in the payload a rule reads.

**Any field HubSpot carries that Meta-direct cannot reproduce gets named
before we build, not discovered after.** That diff is the deliverable
that ends this workstream.

**Timing is no longer a blocker.** Kerry: *"The plan is to start a new
campaign with new creative when this one ends."* The Fall campaign
closes Sep 6 and a new one begins straight after, so live leads keep
flowing. The new campaign's first days give a free side-by-side overlap
— Kerry sees a week as reasonable but not strictly needed. Run both
pipes through it because it costs nothing, and let the parity proof, not
the calendar, decide when HubSpot's pipe goes off.

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
