# SESSION PROMPT — BREVO AUTO-DRAFT + INSIDER CADENCE

You are helping Kerry Niester continue the Tracker→Brevo work: the
nightly member-status sync is live and healthy, and the one ratified
build still missing is the Wednesday-morning auto-draft of the public
"TGF Insider" recap. The weekly cadence (ratified through Oct 31)
lapsed on 2026-09-09 because nothing drafts it yet.

---

## CONTEXT FILE
`docs/claude/handoff-2026-09-02-lead-selections-brevo-sync.md` in the
repo (OneDrive copy: `7_Web & App Development\TGF Transaction
Tracker\Tracker Docs\TGF_Tracker_Context_Brevo_Sync_v1_0.md`).
Read that file before doing anything else.

---

## EXISTING OUTPUT
- `email_parser/brevo.py` — sync, dials, bridge commands.
- `docs/claude/templates/public-recap-template.html` — Kerry's sent
  structure with `{{PLACEHOLDER}}` slots.
- `docs/claude/event-recaps.md` — house style (read the CURRENT file;
  it gained rules after this lane closed).

---

## WHAT THIS SESSION NEEDS TO ACCOMPLISH
Step 1 — Read the tracker mailbox (`read_platform_dialogue` since #449)
before responding to anything. Standing Kerry instruction.
Step 2 — Confirm the nightly sync is still 0-error
(`probe_golf_genius extract=scoring-brevo-status`).
Step 3 — Build `build_public_recap_draft()` in `email_parser/brevo.py`:
fill the template from Tracker data for the most recent Tuesday events
(both chapters), create a Brevo DRAFT via `POST /v3/emailCampaigns`
(sender id 1, `recipients {"listIds":[3],"exclusionSegmentIds":[2]}`,
tag `public-recap`, subject `TGF Insider | <hook>`), email Kerry the
draft link. Schedule it Wednesday 8:00 AM Central (13:00 UTC) via
APScheduler next to `brevo_sync`; bridge `scoring-brevo-draft[:dry]`.
Step 4 — Dry-run against s9.22 Silverhorn / a9.22 ShadowGlen, show
Kerry the rendered HTML, then create the real draft only when he says.
Step 5 — Ask whether an Insider #2 goes out by hand this week.

---

## CRITICAL NOTES FOR THIS SESSION
- Never send. Drafts only; Kerry sends from the Brevo UI.
- No dollar figures except the ratified offer line "$25 off your first
  event, plus a drink on us." (tgf-pricing rule).
- Names in PUBLIC sends: first name + last initial for guests / new
  members.
- Never "league"; POT not purse; no TGF Plus; no DFW/Houston mentions.
- Recipients must be list 3 MINUS segment #2 (Active members) — proven
  shape above.
- Area-code chapter routing is dead by Kerry's ruling; don't revive it.
- Merge main into your branch BEFORE bumping version.js.

---

## START THIS SESSION BY SAYING:
"Mailbox read through #___. The Brevo sync ran clean last night. I'm
ready to build the Wednesday auto-draft against last Tuesday's events —
do you want an Insider #2 out by hand this week while I build it?"
