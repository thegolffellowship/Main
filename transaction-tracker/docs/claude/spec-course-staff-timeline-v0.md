# Course-staff timeline, 6:00 AM Event Info, 4:00 PM missing-handicap reminder: SPEC v0

Event Ops (CGO), Mon 10/26, for Kerry to ratify. Source: CoS #2307 items 2, 3 and 5 (Kerry's rulings, paraphrased by the CoS). Nothing here ships until Kerry ratifies the build (rule 3b), and nothing is built inside an event window.

Status words used below:
- **BUILT:** live today.
- **PART:** some of it is live.
- **NEW:** not built.
- **RULED:** Kerry has ruled it, whether or not it's built.

Times are Central. E = event day. The example is a Tuesday nine.

Kerry's standing goal (#2308): *"We've got to get to the point of zero manager reliance. The show must go on."* So **every row is a Tracker job on a clock or an event, never a person or an agent routine.**

## A. The course-staff timeline

| When | What | To | Status today | What to build |
|---|---|---|---|---|
| **E-2 noon** (Sunday for a Tuesday) | **Course update:** the registered list as of now; a live link they can follow (the public member tee sheet, `/member/teesheet/<id>`, shows the roster until pairings exist); and a notice: *"We lock foursome counts at 5:00 PM Monday; please allow us room to grow."* | course contact (To primary, CC other TGF contacts), manager CC | **NEW** | job `course_update_e2` at 12:00 on E-2. Wording is a system template with Kerry's stamp. Once per event. Refuse on a blank. Dial `course_update_auto` (off until stamped). |
| **E-1 5:00 PM** (lock) | **Tee-time count** to the course; release unused times or request more | course contact, manager CC | **PART / RULED** (event-timeline §2, Kerry "Yes on all"). Today the course learns the count only from the tee-times course email at approval or 7 PM. Nothing goes at 5 PM, and release/request isn't built. | Add the count and "release N times / need N more" to a 5:00 PM course message, or fold it into the tee-times course email if Kerry prefers one email. **Question for Kerry: one email or two?** |
| **E-1 on approval or 7:00 PM**, whichever is first | **Tee-times email**, course version | course contact (CC other TGF contacts) and the manager | **BUILT** (`teetimes_email`, dial on since 10/19; sent for 3301/3319 10/19) | none |
| **E noon** | **Print Pack / Course Files** (Starter Sheet, Cart Signs, Scorecards with QR, Proximity if CTP, Rules of Play) | course contact To, TGF contacts + manager CC | **PART.** The send exists (`send_course_files`, gap and QR checks). The schedule is a one-time agent routine per event. **That's the gap.** | job `course_files_noon` at 12:00 on E. Same checks: a gap holds the send and emails the manager one tap to "send as is / wait". This replaces the routine. A no-handicap player prints blank and never holds it (Kerry 10/20). |
| **After the noon send → first tee** | **Only the changed sheets**: a late add sends that group's scorecard and cart sign only; a move sends the affected sheets | course To, CC other contacts + manager + Kerry | **BUILT** (after-lock job v2.577.0; `course_files_sent` is the baseline) | none, once the noon job above writes the same baseline |
| **E 6:05–9:05 AM** | **Morning print pack** | manager only | **BUILT, and the code matches the ruling:** it skips any event whose course has a TGF contact (`print_pack.send_due_print_packs`, Kerry 10/20). It's the fallback for courses with no contact. | none |
| **E, not before first tee/shotgun − 1 h** (or earlier only if the course requires it) | **CCA payment form** (the course's card authorization) | course contact | **NEW.** CD has a form drafted. | **Money path and card data: Marcus review, then Kerry's OK, before any build.** Proposal only: the job sends a link to the course's own form, or our filled form, at T−60 min. The Tracker never stores card numbers. A course that needs it earlier gets a per-course setting in course_staff. |

## B. Event Info email moves from 7:00 AM to 6:00 AM (CoS #2307 item 3)

- **Today:** `pairings_approval.EVENT_INFO_HOUR = 7` (sends at 7:00 AM on E). The tee-times player and manager emails say *"comes at 7:00 AM tomorrow"* (`teetimes_email.EVENT_INFO_LINE`).
- **Build:**
  1. Make the hour a dial: `event_info_hour`, default 6.
  2. Change the tee-times line to read the dial.
  3. The after-lock baseline is set by that send, so it moves with it. Nothing else changes.
- **Note:** the tee-times wording carries Kerry's stamp. Changing "7:00 AM" voids the stamp unless the line is outside the stamped text. **Kerry re-stamps once.**
- **Update emails** (UPDATED GROUP / TEES / GAMES) still go whenever a player's or group's details change (after-lock job, BUILT).
- **Status:** RULED, NEW (Tracker Build 5 listed it, #2315 §6-7).

## C. Missing-handicap reminder, E-1 4:00 PM (CoS #2307 item 5)

**Today:**
- The handicap ask (`handicap_ask`, BUILT, dial on) emails a registered player with no handicap at order time.
- It sends one reminder 2 days before, between 7 AM and 8 PM.
- The missing-handicap banner shows the case to the manager.

**Build:**
1. **E-1 4:00 PM reminder:** a second reminder at 4:00 PM on E-1 to anyone registered with no handicap and no answer. It reuses the ask's signed link (GHIN number + index → 75% starting handicap; other service → manager check; none → usual 18-hole range).
2. **Event Info line:** a line in the Event Info email for a player still without one: *"We don't have a handicap for you yet. Add it here"* + the link. The Event Info already has the ADD HANDICAP card (v2.575.13). Confirm the wording.
3. **Manager touch: none** (Kerry: "The manager should not have to contact the player"). A player with none at print time prints blank and plays as ruled.
4. Wording needs Kerry's stamp. The reminder is once per player per event.

**Status:** RULED, NEW.

## D. Questions for Kerry (one at a time)

1. **E-1 5:00 PM count to the course:** its own email, or folded into the tee-times course email at approval / 7 PM?
2. **E-2 noon course update:** wording. Draft: *"Here's who's registered for Tuesday so far ({n} players). You can follow along live at {link}. We lock foursome counts at 5:00 PM Monday; please allow us room to grow."*
3. **CCA payment form:** send at first tee − 60 min by default? Which courses need it earlier? (Marcus reviews the money path first.)
4. **6:00 AM Event Info:** re-stamp the tee-times wording with "6:00 AM".
5. **4:00 PM handicap reminder:** wording stamp.

## E. Build order (proposal, all after Tuesday's closeout and outside every window)

1. The noon Course Files job, replacing the per-event routine. This is the biggest gap.
2. 6:00 AM Event Info.
3. 4:00 PM handicap reminder.
4. E-2 noon course update.
5. The 5:00 PM count / release.
6. CCA form, after Marcus and Kerry.
