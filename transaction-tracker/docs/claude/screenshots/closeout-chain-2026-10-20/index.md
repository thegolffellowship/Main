# Tue 10/20/2026 event chain: s9.28 TPC Canyons (3301) and a9.28 Avery Ranch (3319)

Made 2026-10-21. Nothing was sent to make these. All times are Central (stored UTC minus 5).

How each picture was made:
- **Production build.** The results emails (27, 28) are production's own HTML, from the `scoring-results-email:preview|...|html` dry run with no send.
- **Local build.** Everything else is the Tracker's own builder code at v2.575.17, run locally on production's sheets, games tabs and handicap rows from read-only bridges. Every mail sender was replaced with a capture stub.
  - The template hashes match production: Event Day `10e5848ccdd34829`; Tee Times player / course / manager `fec8c4625569cb4a` / `98a0903c7877fb4f` / `16e7f8c738ecc3b7`.
  - Production's own Event Info text sample (Adam Baker) matches the local render word for word.
  - Buttons in local builds carry local sample links, not live tokens.
- **Public pages.** 16, 22, 29 and 30 are the live public pages, at 390 px and 1280 px. The page's analytics beacon (POST /api/member-metric) was blocked.

Sources for the times: `scoring-message-log`, `get_agent_action_log`, the app settings `pairings_approval`, `payout_ask` and `results_email_schedule`, mailbox #2122, #2137, #2138, #2142 and #2152-#2166, and handoff-2026-10-20-event-day-sends.md.

| # | Fire time (Central) | What it is | Who receives it | Trigger | File | Notes |
|---|---|---|---|---|---|---|
| 1 | Mon 10/19 7:02-7:04 AM | Invitation "Last call: sign up by 5:00 PM tonight" | 118 SA + 93 Austin members not yet registered | Tracker job on a clock (7-9 AM at :02/:17/:32/:47) | 01-invitation-last-call.png | SA version shown, sample person Larry Anthis |
| 2 | Mon 7:04 AM | Handicap ask reminder | Chris Best (SA), CC Kerry | Tracker job every 15 minutes | 02-handicap-ask-reminder.png | Austin's reminder (Logan Billeaud) went Sun 10/18 7:03 AM |
| - | Mon 5:10 PM | Pairings generated + blinds drawn (no email) | nobody | Agent routine (Kerry asked for a 10-minute delay; normally a job at 5:00 PM) | not rendered | Screen only; Live Scoring switched on for both events at 5:10 PM |
| 3 | Mon 5:10 PM; again 5:59 PM, 6:06 PM, 7:50 PM | "Pairings ready to approve: s9.28 TPC Canyons" | Kerry | 5:10 PM: agent routine (normally a job every 15 min at :05). 5:59 and 6:06 PM: agent resend. 7:50 PM: job, after the sheet changed at 7:47 PM | 03-pairings-ready-prompt-sa.png | Groups shown are the final Tuesday sheet (23 players); Monday's sheet had 21 (no Adam Wilson or Pat Youngs) |
| 4 | Mon 5:10 PM; again 6:06 PM | "Pairings ready to approve: a9.28 Avery Ranch" | Robert | 5:10 PM: agent routine. 6:06 PM: agent resend | 04-pairings-ready-prompt-austin.png | Monday sheet with Paul Reed in the 4:03 group. The YOUR CARD strip is omitted in this sample (not rebuilt for Austin) |
| 5 | Mon 5:18 PM | Approve Pairings page (screen) | Robert approved 3319 | A button a person presses | 05-approve-pairings-page-austin.png | Manager login page, rendered locally before the tap |
| 6 | Mon 5:18 PM | Tee-times email, player version (Austin) | 8 Austin rows | A button a person presses (Robert's approval) | 06-teetimes-player-austin.png | Registered-player version (Eduardo Melchor) |
| 7 | Mon 5:18 PM | Tee-times email, course version (Austin) | Skyler Morrow | A button a person presses (Robert's approval) | 07-teetimes-course-austin.png | |
| 8 | Mon 5:18 PM | Tee-times email, manager version (Austin) | Robert | A button a person presses (Robert's approval) | 08-teetimes-manager-austin.png | |
| 9 | Mon 7:00 PM | Tee-times email, course version (SA) | Justin Ortiz | Tracker job on a clock (7 PM; runs every 15 min) | 09-teetimes-course-sa.png | Sent before Kerry approved SA |
| 10 | Mon 7:00 PM | Tee-times email, manager version (SA) | Kerry | Tracker job on a clock (7 PM) | 10-teetimes-manager-sa.png | |
| 11 | Mon 7:57 PM | Approve Pairings page (screen) | Kerry approved 3301 | A button a person presses | 11-approve-pairings-page-sa.png | The approve call took 97 s |
| 12 | Mon 7:57-7:59 PM | Tee-times email, player version (SA) | 133 SA rows: 21 registered + 112 invitees | A button a person presses (Kerry's approval) | 12-teetimes-player-sa.png | Registered-player version (Richard Palacios); tee sheet is the final Tuesday sheet |
| 13 | Mon 7:57-7:59 PM | Tee-times email, spots-open version (SA) | Invited members not registered | A button a person presses (Kerry's approval) | 13-teetimes-player-spots-open-sa.png | "3 spots" is illustrative |
| 14 | Mon 8:59, 9:12, 9:25 PM | "Print files" staff copy (one PDF per sheet) | Kerry | Agent routine | 14-print-files-staff-copy.png | PDF attachments not rendered (manager-login route) |
| - | Mon 9:30 PM | Course Files (evening) | nobody | Agent routine | none | Held on Kerry's word, nothing sent (#2122) |
| - | Tue 6:05-9:05 AM | Morning print pack to staff | unknown | Tracker job on a clock | not rendered | Fire time unknown: `print_pack_sent:3301` and `:3319` hold hashes only, and the job skips courses with a contact |
| 15 | Tue 10/20 7:00 AM | Event Info ("Tuesday at TPC Canyons: 4:30 PM tee time") | 21 SA + 8 Austin players | Tracker job on a clock (7 AM; runs every 15 min) | 15-event-info-7am.png | Sample Adam Baker. The Keep score link is a placeholder. Games figures are from Wednesday's read |
| 16 | Tue (linked from 15) | Member tee sheet /member/teesheet/3301 (screen) | public | Page | 16-member-teesheet-3301-phone.png, -desktop.png | Live page as of Wed |
| - | Tue 11:15 AM, 11:34 AM | Event Info test copies | Kerry | Agent routine | not rendered | Same email as 18 / 19 |
| 17 | Tue 10:19 AM | Handicap ask "One quick thing before Tuesday, Adam" | Adam Wilson, CC Kerry | Tracker job every 15 minutes | 17-handicap-ask-adam-wilson.png | Rendered from current code; the live version was v2.575.13 |
| 18 | Tue 11:33 AM | Late-add Event Info | Adam Wilson; Pat Youngs got the same at 11:33 AM | Agent routine (bridge, Kerry OK #2135) | 18-late-add-event-info-adam-wilson.png | Shows Adam's state then: no handicap (ADD HANDICAP box), first-timer (Rules of Play box) |
| 19 | Tue 11:33-11:34 AM | "UPDATED GROUP:" Event Info | 6 groupmates (3:50 and 4:00 groups) | Agent routine (same call) | 19-updated-group-groupmates.png | Sample Richard Palacios |
| 20 | Tue 12:04 PM | Course Files email (Austin) | Skyler Morrow, CC Kerry + Robert | Agent routine (one-time Routine) | 20-course-files-austin.png | An extra copy went to Kerry + Robert at 12:03 PM. PDFs not rendered |
| 21 | Tue 12:24 PM | Course Files email (SA) | Justin Ortiz, CC Patti Rutherford + Kerry | Agent routine | 21-course-files-sa.png | Action log shows 12:24 PM; the handoff says 12:10. Its Scorecards.pdf was the "can't print yet" page; Kerry sent corrected scorecards himself (#2142). PDFs not rendered |
| 22 | Tue (round) | Live Scoring how-to /member/live-scoring (screen) | public | Page | 22-member-live-scoring-guide-phone.png, -desktop.png | |
| - | Tue 3:40 PM onward | Score-entry page /member/score?t=... | each group's scorer | Signed link | not rendered | Needs a group token; opening it could take the scorer lock |
| - | Tue 6:53 PM / 7:53 PM | Auto payouts recorded (3319 $160 / 3301 $462) (no email) | nobody | Tracker job every minute | none | |
| 23 | Tue ~7:15 PM (Austin), 7:24-8:00 PM (SA) | Handicap Update recap | Kerry and Robert | Agent routine (closeout posting sends it) | 23-handicap-recap-managers.png | Austin version shown. Exact times unknown: this email is not in message_log |
| 24 | Tue 8:02 PM | Payout ask "You won $99.50 at s9.28 TPC Canyons" | Adam Wilson, CC Kerry | Tracker job every 15 minutes | 24-payout-ask-adam-wilson.png | Line labels are illustrative |
| 25 | Tue 8:33 PM | Recap draft, SAN ANTONIO (+ .docx) | Kerry | Agent routine | 25-recap-draft-sa.png | Rebuilt locally from the recap .md |
| 26 | Tue 8:33 PM | Recap draft, AUSTIN (+ .docx) | Robert, CC Kerry | Agent routine | 26-recap-draft-austin.png | Rebuilt locally from the recap .md |
| - | Tue 8:56 PM (Chris Best), 10:29 PM (Lou Schneider) | Put back on invitations (no email) | nobody | Agent routine (Kerry's word, #2165) | none | Raised the results audience to 204 |
| 27 | Wed 10/21 6:00-6:03 AM | Results email, player version "your results" | 30 players (23 SA, 7 Austin) | Tracker job on a clock (06:00, scheduled by the closeout) | 27-results-email-player.png | Production HTML, Adam Wilson |
| 28 | Wed 6:00-6:03 AM | Results email, everyone-else version "the results" | 174 members and recent players | Tracker job on a clock (06:00) | 28-results-email-nonplayer.png | Production HTML, Paul Reed. 204 sent in all (SA 121, Austin 83) |
| 29 | Wed (linked from 27/28) | /member/results/3301 (screen) | public | Page | 29-member-results-3301-phone.png, -desktop.png | |
| 30 | Wed (linked from 27/28) | /member/results/3319 (screen) | public | Page | 30-member-results-3319-phone.png, -desktop.png | |

Not sent in the window: handicap cards for 10/20. The last `handicap-card` rows in message_log are from 10/14.
