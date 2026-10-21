# Handoff 2026-10-20 — event day s9.28 TPC Canyons / a9.28 Avery Ranch, and the send map

Session: https://claude.ai/code/session_014svvTq1chymJug3Sc3Tg4T (tracker-claude, front-desk relay posts).
Mailbox ids for today: #2135 to #2140 (Kerry's rulings, verbatim).

## 1. State at handoff (Tue 10/20 ~1:20 PM CDT)

- **Railway builds are PAUSED platform-wide** (Railway banner: "New builds are temporarily paused"). Live is v2.575.13.
- **main is at v2.575.15, not deployed:**
  - v2.575.14: no handicap prints blank; Course Files refuse a scorecards gap page; a handicap-only change never resends.
  - v2.575.15: handicap ask resend bridge.
- **Risk:** when Railway resumes, main will deploy. If that lands inside tonight's window (3:35 PM to closeout), the app restarts mid-round. Watch Railway; skip or hold that deploy until WINDOW CLOSED if it starts in the window.
- **3301 TPC Canyons Course Files:** sent 12:10 PM to Justin Ortiz, CC Patti + Kerry. Scorecards.pdf was the "These cards can't print yet" page (Adam Wilson had no handicap). Kerry: "This is NOT good!!!".
  - Needs: corrected Scorecards.pdf to Justin, CC Patti + Kerry, "replaces the earlier file".
  - With Adam's 9.4 starting handicap set (Kerry #2140), the live v2.575.13 builds clean cards. Run `scoring-print-pack-pdf:3301|files` and check that `scorecards.gaps` is empty BEFORE any send.
  - Only the Scorecards file should go (Kerry: only affected sheets). There is no single-file course bridge yet. Either build one, or Kerry forwards.
- **3319 Avery Ranch Course Files:** sent 12:04 PM to Skyler Morrow, CC Kerry + Robert. Clean.
- **Adam Wilson (846):**
  - First handicap/Venmo ask sent 10:19 AM (CC Kerry). He says he didn't get it.
  - His `handicap_ask` state was cleared at ~1:05 PM so the 15-min job re-sends the same ask.
  - Kerry then gave his GHIN-derived handicap: "he's a 12.5 which converted to a 9.4" (#2140). Set it with `scoring-starting-handicap:846|9.4|2140|apply` once the ask has gone; setting it first removes him from the ask list. That also drops his N/H blind (Jeff Young at 3:50).
  - Gender set M (#2136).
  - Late-add Event Info sent ~11:40 AM (#2135, v2.575.11).
- **Pat Youngs (136):** late add, Event Info sent with Adam's.
- **Blinds 3301:** Reggie Johnson at 3:40 (Kerry asked). Jeff Young at 3:50 for Adam's N/H; comes off with his handicap.
- **Dials changed today:**
  - `gender_infer` = on;
  - `handicap_ask` state edited for 846 only.

## 2. Shipped today (live unless noted)

| Version | What |
|---|---|
| 2.575.10 | TEAM board in tee-time order, left-aligned, blinds marked |
| 2.575.11 | Late-add emails: Event Info to the new player, UPDATED GROUP to their group (bridge `scoring-event-day-email:<id>\|lateadd\|<cids>\|<post>[\|confirm]`) |
| 2.575.12 | Newcomer welcome line + Rules of Play link; YOUR CARD TOT column and colours (NET black, TEAM orange); N/H blind drops when a starting handicap is set; `scoring-blinds:<event>\|set\|…` |
| 2.575.13 | Tee sheet shows TGF index / No handicap and blinds with the reason; ADD HANDICAP box in Event Info; gender M from men's bands |
| 2.575.14 | NOT LIVE (see §1) |
| 2.575.15 | NOT LIVE (see §1) |

## 3. Kerry's rulings today (verbatim in the mailbox)

- Requests are not honored after the 5 PM lock; only a manager can (#2135).
- Late-add seat fill: tee times fill the latest threesome first; shotgun fills the lowest hole, B before A. NOT BUILT.
- Gender from tees: 65+ / 50-64 / <50 men, Forward women (#2136; built, dial on).
- Adam may play NET games tonight at his 75% handicap (#2136). Future shop will not allow a member rate for a non-member.
- No handicap at print time prints blank. A later handicap is a Tracker update + blind removal, never a resend (v2.575.14).
- **After-lock changes (#2139), NOT BUILT:**
  - moved player → email the affected players + send ONLY the affected sheets to the course, CC manager + Kerry;
  - tee change → Tracker + notice to that player, CC manager; no print resend;
  - games change → Tracker + notice to affected players, CC manager; no print resend.

## 4. The send map, Mon 5 PM lock → Tue first tee (from code, 10/20)

Times are Central. See the full report in this session; summary:

**Monday**
- **5:00 PM:** auto-generate sheet + blind draw (no email). Live scoring turns on every 15 min from 5 PM.
- **5:05 PM + every 15 min:** manager "Pairings ready to approve" prompt.
  - Re-prompts on a sheet change, at most hourly.
  - Stops after any Event Info is sent.
- **On Approve:** tee-times email immediately (3 versions). No date/hour guard.
- **7:00 PM:** auto-approve. Tee-times email every 15 min to midnight, once per person (`teetimes_email_sent:<id>`).
- **Any time:** handicap ask (once per person ever, CC Kerry); reminder 7 AM–8 PM within 2 days.

**Tuesday**
- **6:00 AM, odd days:** payment reminders to RSVP-only rows, no dedup.
- **6:05–9:05 AM hourly:** morning print pack to staff. Skips courses with a contact; resends on non-handicap changes.
- **7:00 AM–noon every 15 min:** Event Info to seated players (`event_day_email_sends`). After the first send the job ignores the event.
- **7:00–9:00 AM:** invitations for OTHER events. Payout ask 7 AM–9 PM.
- **Noon:** Course Files. NO JOB — today ran from a one-time routine. The tee-times email promises it.

**Duplicate / wrong-send risks to fix (proposed order):**
1. Tee-times email sent on approval at any hour, including event morning ("comes at 7:00 AM tomorrow"). Guard to Mon 5 PM–midnight.
2. Late-add / reissue sends don't write `event_day_email_sends`: a pre-7 AM late add gets two emails. Write the row.
3. Course Files have no once-only key. Add one per sheet state; build the noon job; the only-affected-sheets rule.
4. Handicap reminder + Event Info ADD HANDICAP box on the same morning, same link. Drop one.
5. Payment reminders: no record, can land on event morning. Add a key; skip event day.
6. Kerry's inbox stacking (prompt, tee-times manager copy, pack, Course Files CC, FAILED alert every retry).
7. Invitations manual slot keyed on UTC `date.today()` (invitations.py:1037).
8. Course Files and SEND PACK ignore each other's records.

## 5. Open for the next session

- Get v2.575.14/15 live outside the event window and verify.
- Corrected TPC Scorecards to Justin, if not done today.
- Build the §3 after-lock rules and the §4 fixes, one small change each, Kerry's OK on each.
- Late-add automation (seat fill rule + emails).
- Closeout of 3301 / 3319 tonight (event-closeout skill).
- Older open items: pace branch claude/pace-0037 (db-claude PASS), SKINS live ranking, SUMMARY colour, manual hold vs IN REVIEW, solo vs 3rd-meeting priority (Reviewer), badges on line 2.
