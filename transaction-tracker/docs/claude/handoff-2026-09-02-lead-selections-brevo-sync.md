# TGF TRACKER — LEAD SELECTIONS + TRACKER→BREVO SYNC CONTEXT
**Version:** 1.0
**Created:** 2026-09-10 (session ran 2026-09-02 → 2026-09-03; closed 2026-09-10)
**Status:** Complete — one ratified build NOT started (Wednesday auto-draft), handed off below
**Session:** Claude Code remote, branch `claude/desktop-usability-issues-z7aa8w` (fully merged into main; safe to delete)
**Versions shipped:** v2.287.0 → v2.290.2 (+ v2.296.1 docs merge). Live is well past that (v2.367.x) — other lanes kept shipping.

---

## SITUATION SUMMARY
Kerry's 2026-09-02 afternoon session did three things: (1) made Facebook
survey answers EDITABLE on every Lead Center card with overrides that
survive the HubSpot re-sync (the Mick Hernandez case); (2) built and
switched on the first Tracker→Brevo API brick — a nightly sync that
stamps member status, chapter and last-played date onto Brevo contacts
and creates the missing ones, which is the segmentation key for the
public "TGF Insider" recap and the eventual GG→Brevo email transition;
(3) read the first TGF Insider send's 24-hour numbers. The SMS presets
drafted here (#383) were ratified and shipped by later sessions
(#388/#389, waves 1–2) — nothing pending on them from this lane.

---

## CONFIRMED DATA / DECISIONS — DO NOT RE-DERIVE

### Kerry rulings (this session)
- **Brevo create scope = "recent"**: import missing ACTIVE MEMBERS plus
  anyone who PLAYED WITHIN THE LAST 12 MONTHS. "Only include current
  members, but also add anyone who has played within the last 12
  months. We'll need this for our transition to all Brevo emails once
  GG is behind us." Dial `brevo_sync_create_missing` = `recent`.
- **Chapter fallback stops at CITY.** "I wouldn't trust area codes.
  City is where we should stop it." Area-code routing is DEAD, not
  deferred (mailbox #387).
- **Ad-lead segments exclude active members** (Kerry edited #8–#11 in
  the Brevo UI to add TGF_MEMBER_STATUS ≠ active_member).
- **Mick Hernandez (lead 63)**: lives in SA, plays Austin occasionally,
  asked off Austin invites; Kerry removed him from the Austin GG roster
  9/2. Tracker: invites = San Antonio only, city + chapter San Antonio.

### Brevo facts of record
- API key `BREVO_API_KEY` on Railway since 2026-09-02 ~4:05 PM CDT;
  account kerry@thegolffellowship.com / The Golf Fellowship LLC.
- List 3 "TGF CONTACTS" is the only list. Sender id 1 = kerry@.
- Attributes the Tracker owns: `TGF_MEMBER_STATUS`
  {active_member | former_member | prospect}, `TGF_CHAPTER`,
  `TGF_LAST_PLAYED` (Brevo DATE, YYYY-MM-DD). Legacy `TGF_LIFECYCLE`
  (HubSpot era) still exists — do not build segments on it.
- Segments (Kerry-built, UI only — Brevo's API cannot create segments):
  #1 SA Ideal Customer, #2 **Active members** (the exclusion segment),
  #3 Austin Ideal Customer, #4/#5 Austin/SA Saturdays, #12/#13
  Austin/SA Tuesdays, #8–#11 Ad Leads Competitors/Community/Golf/All Of
  It (member-excluded), #6 DFW, #7 Houston, #14 Austin, #15 San
  Antonio, #16 Austin & San Antonio.
- **Campaign exclusion via API is PROVEN**: `recipients:
  {"listIds":[3], "exclusionSegmentIds":[2]}` → Brevo stores
  `excludedSegments:[2]`. Probe draft #16 was deleted by Kerry.
- Brevo API quirks: a pre-existing attribute returns 400 "Attribute
  name must be unique" (treated as exists); segment counts in the UI
  lag creation (Austin Ideal showed 56, real 31); campaign link stats
  lag global stats; Apple MPP inflates opens — judge on
  `trackableViews`.

### Nightly sync state (checked 2026-09-10 4:10 AM run)
1,436 Brevo contacts · 746 Tracker emails (144 active / 295 former /
307 prospect) · 509 matched · 14 updated · 231 Tracker emails still not
in Brevo (out of scope by the "recent" rule) · 0 errors · 4.2 s.

### TGF Insider #15 ("A par won money this week. In both cities.")
Sent Wed 2026-09-02 2:18 PM CDT to the whole list (exclusion didn't
exist yet). +24h: 1,245 delivered, 29.6% opens (10.4% trackable), 76
unique clicks, 3 unsubs (0.24%), MEMBERSHIP the top link (10), ShadowGlen
0. +8 days (2026-09-10): 32.1% opens (11.8% trackable), 80 unique
clicks, 4 unsubs, 1 complaint. Prior sends for comparison: 45.3% /
47.3% / 61.5% opens-rate basis; Season 20 Kickoff 209 unique clicks.
**No TGF Insider #2 has been sent — the ratified weekly cadence lapsed
on Wed 2026-09-09.**

---

## WORK COMPLETED THIS SESSION
- v2.287.0 — Lead Center **Edit selections** (Availability / Importance
  / Invitations / City / Chapter) with `payload._manual` overrides
  re-applied across the <48h HubSpot re-sync and the self-heal;
  invitations change re-routes chapter; auto note + "edited by" marker;
  bridge `scoring-lead-edit` accepts city/availability/importance/
  invitations. Applied to Mick Hernandez.
- v2.287.0–v2.290.1 — `email_parser/brevo.py`: nightly 09:10 UTC sync,
  `scoring-brevo-status`, `scoring-brevo-sync[:dry]`; status + chapter
  + last-played stamps; create scope dial (none/active/recent/all); one
  import address per customer; chapter fallback chain customers.chapter
  → lead's routed chapter → Brevo CITY via the Lead Center map (widened
  with SA/Austin suburbs) → Brevo-only DFW/Houston metro map. Offline
  test `test_brevo_sync.py` (8 checks).
- Live runs 2026-09-02: 396 stamped → 42 active members created →
  168 last-played dates + 20 recent players created → 133 contacts
  routed from CITY. Brevo active-member segment 93 → 135.
- v2.290.2 / v2.296.1 — #15 24h results recorded in
  `docs/claude/event-recaps.md`; CA note #397.
- Mailbox: #383 (SMS preset drafts), #384 (behavior note), #386 (session
  digest), #387 (area-code ruling), #397 (Insider #15 data point).

---

## CURRENT STATUS BY COMPONENT
| Component | Status |
|---|---|
| Edit selections (Lead Center) | LIVE, in use |
| Brevo nightly sync | LIVE, healthy (0 errors nightly) |
| Brevo create scope | `recent`, Kerry-ratified |
| Brevo segments | 16 built by Kerry; exclusion #2 ready |
| TGF Insider weekly recap | #15 sent 9/2; **#2 NOT sent** (9/9 missed) |
| Wednesday AM auto-draft (ratified #381) | **NOT BUILT** |
| Campaign click export → customer timeline | NOT BUILT (idea only) |
| SMS presets | shipped by other lanes (v2.291.0 → v2.326.0) |
| Area-code chapter routing | DEAD by ruling |

---

## ITEMS STILL NEEDED / OPEN QUESTIONS
- [ ] **Build the Wednesday-AM public recap auto-draft** (Kerry-ratified
      via CA #381; buildable now). Template of record:
      `docs/claude/templates/public-recap-template.html`. Create as a
      Brevo DRAFT via `POST /v3/emailCampaigns` with sender id 1,
      `recipients {"listIds":[3],"exclusionSegmentIds":[2]}`, tag
      `public-recap`, subject `TGF Insider | <hook>`; ping Kerry (email)
      with the draft link. Cadence: weekly through Oct 31, biweekly
      after. Use the recap rules in `docs/claude/event-recaps.md` (they
      grew ten rules on 9/10 — read the current file, not memory).
- [ ] Decide whether a hand-built Insider #2 goes out this week to
      restart the cadence while the auto-draft is built.
- [ ] Optional: campaign recipient export (who clicked what) onto the
      customer timeline — Brevo `POST /v3/emailCampaigns/{id}/
      exportRecipients` is async (needs a notify URL or polling).
- [ ] Optional: map legacy Tracker chapter values (DFW/Houston) to blank
      in Brevo if Kerry ever wants those contacts chapterless instead.
- [ ] Delete branch `claude/desktop-usability-issues-z7aa8w` (fully
      merged).

---

## DOCUMENTS / FILES IN HAND
- Repo: `email_parser/brevo.py`, `test_brevo_sync.py`,
  `email_parser/leads.py` (set_lead_answers, apply_manual_answers,
  MANUAL_ANSWER_OPTIONS, widened DEFAULT_CITY_CHAPTERS),
  `templates/leads.html` (editSelections), `docs/claude/leads.md`
  (Edit selections + Brevo sections), `docs/claude/event-recaps.md`
  (public variant + #15 results), `docs/claude/templates/
  public-recap-template.html`.
- OneDrive: `7_Web & App Development\TGF Transaction Tracker\Tracker
  Docs\` — this file as `TGF_Tracker_Context_Brevo_Sync_v1_0.md` and
  the companion `TGF_Tracker_Session_Prompt_Brevo_Next.md`.

---

## KEY DECISIONS & NOTES
- The Brevo-only legacy metro map (`LEGACY_CITY_CHAPTERS`) must NEVER
  feed Lead Center routing — an ad lead from Plano stays unrouted for a
  human. SA/Austin keys are checked first so "JBSA Ft. Sam Houston" is
  San Antonio, not Houston.
- CITY-only routing sets chapter alone, never a member status; an
  existing Brevo chapter is never overwritten; updates never touch
  names Brevo already holds.
- Judge Insider opens on trackable views. Baseline send window is
  mid-afternoon Wednesday; a Thursday-morning A/B is the open question.
- Two-lane merge lesson (also recorded by other lanes): merge main into
  the working branch before bumping `version.js`; the changelog is the
  conflict magnet.
- Standing instruction from Kerry (2026-09-10): read the tracker
  mailbox before responding to ANY prompt.

---

## NEXT SESSION GOALS
1. Read the mailbox (since #449) and `docs/claude/event-recaps.md` as
   they stand now.
2. Build the Wednesday-AM auto-draft (spec above), dry-run it against
   last Tuesday's events, create the DRAFT, and confirm the recipients
   block reads list 3 minus segment 2.
3. Ask Kerry whether to send an Insider #2 this week by hand.
4. Verify the nightly Brevo sync is still 0-error via
   `scoring-brevo-status`.

---
*Created 2026-09-10 | Source: Claude Code remote session on the Tracker repo (tracker-claude)*
