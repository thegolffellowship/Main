# Course-staff timeline, 6:00 AM Event Info, 4:00 PM missing-handicap reminder: SPEC v0

Event Ops (CGO), Mon 10/26, for Kerry to ratify. Source: CoS #2307 items 2, 3 and 5 (Kerry's rulings, paraphrased by the CoS). Nothing here ships until Kerry ratifies the build (rule 3b), and nothing is built inside an event window.

Day names (Kerry #2326): "Sunday noon" = two days before a Tuesday event, "Monday" = the day before, "event day" = the day of play. Times are 12-hour Central.

Status words used below:
- **BUILT:** live today.
- **PART:** some of it is live.
- **NEW:** not built.
- **RULED:** Kerry has ruled it, whether or not it's built.

The example is a Tuesday nine.

Kerry's standing goal (#2308): *"We've got to get to the point of zero manager reliance. The show must go on."* So **every row is a Tracker job on a clock or an event, never a person or an agent routine.**

## A. The course-staff timeline

| When | What | To | Status today | What to build |
|---|---|---|---|---|
| **Sunday noon** (two days before) | **Course update:** the registered list as of now; a live link they can follow (the public member tee sheet, `/member/teesheet/<id>`, shows the roster until pairings exist); and a notice: *"We lock foursome counts at 5:00 PM Monday; please allow us room to grow."* | course contact (To primary, CC other TGF contacts), manager CC | **NEW** | job `course_update_e2` at noon two days before. Wording is a system template with Kerry's stamp. Once per event. Refuse on a blank. Dial `course_update_auto` (off until stamped). |
| **Monday 5:00 PM** (lock) | Nothing to the course. **RULED Monday 10/26 (#2329-2):** *"I don't think the course needs to receive anything until the pairings are approved."* | n/a | superseded | none |
| **Monday on approval or 7:00 PM**, whichever is first | **Tee-times email**, course version, now also carrying the **tee-time count and the released times** | course contact (CC other TGF contacts) and the manager | **BUILT** for the sheet; **NEW** for the count and released times | **RULED (#2331-A, corrected #2332):** weeknight nines keep the LATEST times and release the EARLIEST; weekend events keep the EARLIEST and release the LATEST by default, a per-event setting the manager can flip. The email names each released time. Shotguns unchanged. |
| **Event day noon** | **Print Pack / Course Files** (Starter Sheet, Cart Signs, Scorecards with QR, Proximity if CTP, Rules of Play) | course contact To, TGF contacts + **manager** CC (RULED #2329-3) | **PART.** The send exists (`send_course_files`, gap and QR checks). The schedule is a one-time agent routine per event. **That's the gap.** | job `course_files_noon` at noon on event day. Same checks: a gap holds the send and emails the manager one tap to "send as is / wait". This replaces the routine. A no-handicap player prints blank and never holds it (Kerry 10/20). |
| **Event day noon → 1 hour before first tee** | **Only the changed sheets**: a late add sends that group's scorecard and cart sign only; a move sends the affected sheets | course To, CC other contacts + manager + Kerry | **PART.** Built, but today it runs right up to first tee | **RULED (#2329-4):** *"Changed sheets for the course shouldn't be going to them during play. That should be in the window between Noon and 1 hour prior."* Stop course sheets at first tee − 1 hour (Tracker Build 5 item 0c, tonight). |
| **About 3 holes into play** | **No-show notice**: one message naming any no-shows | course contact, manager CC | **NEW. RULED (#2329-4):** *"any no shows should just be communicated to the course after about 3 holes."* | Needs the scorer's Player-missing mark to know who is absent (`no-show-scorer-sequence-v0.md`). |
| **Event day 6:05–9:05 AM** | **Morning print pack** | manager only | **BUILT, and the code matches the ruling:** it skips any event whose course has a TGF contact (`print_pack.send_due_print_packs`, Kerry 10/20). It's the fallback for courses with no contact. | none |
| **Event day, not before 1 hour before the first tee or shotgun** (earlier only if the course requires it) | **CCA payment form** (the course's card authorization) | course contact | **NEW.** CD has a form drafted. | **Money path and card data: Marcus review, then Kerry's OK, before any build.** Proposal only: the job sends a link to the course's own form, or our filled form, at T−60 min. The Tracker never stores card numbers. A course that needs it earlier gets a per-course setting in course_staff. |

## B. Event Info email moves from 7:00 AM to 6:00 AM (CoS #2307 item 3)

- **Today:** `pairings_approval.EVENT_INFO_HOUR = 7` (sends at 7:00 AM on event day). The tee-times player and manager emails say *"comes at 7:00 AM tomorrow"* (`teetimes_email.EVENT_INFO_LINE`).
- **Build:**
  1. Make the hour a dial: `event_info_hour`, default 6.
  2. Change the tee-times line to read the dial.
  3. The after-lock baseline is set by that send, so it moves with it. Nothing else changes.
- **Note:** the tee-times wording carries Kerry's stamp. Changing "7:00 AM" voids the stamp unless the line is outside the stamped text. **Kerry re-stamps once.**
- **Update emails** (UPDATED GROUP / TEES / GAMES) still go whenever a player's or group's details change (after-lock job, BUILT).
- **Status:** RULED, NEW (Tracker Build 5 listed it, #2315 §6-7).

## C. Missing-handicap reminder, Monday 4:00 PM (CoS #2307 item 5)

**Today:**
- The handicap ask (`handicap_ask`, BUILT, dial on) emails a registered player with no handicap at order time.
- It sends one reminder 2 days before, between 7 AM and 8 PM.
- The missing-handicap banner shows the case to the manager.

**Build:**
1. **Monday 4:00 PM reminder:** a second reminder at 4:00 PM the day before to anyone registered with no handicap and no answer. It reuses the ask's signed link (GHIN number + index → 75% starting handicap; other service → manager check; none → usual 18-hole range).
2. **Event Info line:** a line in the Event Info email for a player still without one: *"We don't have a handicap for you yet. Add it here"* + the link. The Event Info already has the ADD HANDICAP card (v2.575.13). Confirm the wording.
3. **Manager touch: none** (Kerry: "The manager should not have to contact the player"). A player with none at print time prints blank and plays as ruled.
4. Wording needs Kerry's stamp. The reminder is once per player per event.

**Status:** RULED, NEW.

## D. Questions for Kerry (one at a time)

1. ~~Monday 5:00 PM count: own email or folded in?~~ **Answered Monday 10/26 (#2329-2, #2331-A):** nothing until approval; the count and the released times ride in the tee-times course email.
2. **Sunday noon course update:** wording. Draft: *"Here's who's registered for Tuesday so far ({n} players). You can follow along live at {link}. We lock foursome counts at 5:00 PM Monday; please allow us room to grow."*
3. **CCA payment form:** send at first tee − 60 min by default? Which courses need it earlier? (Marcus reviews the money path first.)
4. **6:00 AM Event Info:** re-stamp the tee-times wording with "6:00 AM".
5. **4:00 PM handicap reminder:** wording stamp.

## E. Build order (proposal, all after Tuesday's closeout and outside every window)

1. The noon Course Files job, replacing the per-event routine. This is the biggest gap.
2. 6:00 AM Event Info.
3. 4:00 PM handicap reminder.
4. Sunday noon course update.
5. The count and released times in the tee-times course email (#2331-A).
6. CCA form, after Marcus and Kerry.
