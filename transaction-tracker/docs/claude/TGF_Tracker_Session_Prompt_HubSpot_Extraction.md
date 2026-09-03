# SESSION PROMPT — HUBSPOT EXTRACTION & DECOMMISSION

You are helping Kerry Niester extract every piece of data out of HubSpot
and then replace it as the lead pipe with a direct Meta connection.
HubSpot costs $42.64/month and has exactly one job left: carrying
Facebook lead-form submissions into the Tracker. Extraction is the gate —
nothing about the pipe changes until the archive is verified.

---

## CONTEXT FILE
`TGF_Tracker_LeadCenter_Context_v1_0.md` — OneDrive
`7_Web & App Development\`
**Read that file before doing anything else.** It holds every confirmed
number, credential and ruling so you never re-derive them.

Also in the repo (`transaction-tracker/docs/claude/`):
- `hubspot-decommission-directive.md` — the full scope and Kerry's rulings
- `railway-api-setup.md` — credentials and scopes
- `database-backup-gap.md` — backup design and the passed restore drill

---

## STATE ON ARRIVAL

Already done, do not redo:
- Campaign stats live on real Meta data, refreshing hourly
- HubSpot service key widened to 9 scopes (value did NOT rotate)
- Nightly off-site backups running, restore drill PASSED
- Duplicate-lead merge built; Shane Winters resolved; 0 duplicates left

---

## WHAT THIS SESSION NEEDS TO ACCOMPLISH

**Step 1 — Raw full export.** Every HubSpot object, every property,
associations, property history, as dated immutable JSON. Raw BEFORE any
interpretation, so a mistake in how we read it is recoverable.

**Step 2 — The engagement records via the Claude connector.** 15 notes,
118 tasks, 24 calls, 22 meetings = 179 records. These scopes do NOT
exist in HubSpot's Service Keys catalog, so the service key cannot reach
them — but the Claude HubSpot connector can, authenticating as Kerry.
Write them to repo files. This is the highest-value material in the
whole archive.

**Step 3 — Reconciliation report.** Sort all 1,453 contacts into three
buckets: confident match (exact email or last-10 phone against
customer_emails), ambiguous, no match. **Publish the counts before
proposing any import.** Nobody knows the third number yet.

**Step 4 — Kerry works the ambiguous queue.** Present each as: the
HubSpot record, the candidate customer(s), what matches and what does
not, and Merge / Not the same person / Skip. **His answer is the
decision. Never break a tie yourself.**

**Step 5 — Import.** Confident matches fold into the EXISTING customer —
never a second record. Notes/calls/tasks/meetings onto the timeline with
original author and timestamp preserved and source-marked so a 2023 note
never reads as typed yesterday. Attribution onto `acquisition_source`.
Unmatched contacts still get a customer record, marked not-active.

**Step 6 — Verification.** Counts per object type, archive vs source.
Oldest and newest spot-checked. Every note readable in its new home.
**A signed-off report is the gate — not "the script finished."**

---

## CRITICAL NOTES FOR THIS SESSION

- **Confident matches merge, uncertain matches go to Kerry, nothing is
  ever guessed.** A wrong merge silently fuses two people's histories
  with no clean way to find it later. An unmatched record costs one row.
- The customer table is TGF's **identity spine back to 2007**. Golf
  Genius history is still arriving. "Archived" is a state on a record,
  never a reason to withhold one.
- **Opted-out is a promise, not a state.** Capture whatever consent data
  HubSpot holds; do NOT design the consent model in passing. Kerry
  parked the "can an active member fully opt out" question deliberately.
- **Historical lead ROWS only exist in HubSpot.** Meta's lead retention
  is short. Campaign STATS come from Meta, lead rows from the export.
- The cutover gate is **field parity**, not a duration — prove every
  field HubSpot carries can be reproduced from Meta, especially the
  three survey answers at their exact raw option values (routing,
  badges, CSV filters and SMS preset selection all key on those strings).
- Do not touch the lead pipe while a campaign is running.

---

## START THIS SESSION BY SAYING:

"I've read the context file. HubSpot extraction is the gate before
anything else moves. Do you want me to start with the raw full export,
or pull the 179 hand-written notes, calls and tasks first — those are
the irreplaceable ones and they're small enough to do right now?"
