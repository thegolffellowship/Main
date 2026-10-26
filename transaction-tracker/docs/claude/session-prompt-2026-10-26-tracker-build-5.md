SPIN-OFF from "Tracker Build 4" (session_0132zH9u1xQ5LHyvqmyE89o6), Mon 2026-10-26 ~1:10 PM CDT.
Kerry asked for a fresh Tracker Build session (Improvements 5) because the
reconnected TGF Tracker connector does not reach Build 4 after his
MCP_CLIENT_SECRET rotation.

GOAL: carry on as the Tracker Build lane with the production connector:
first post the RSVP and communications brief to the Chief of Staff, then
work the open list below.

READ FIRST, BEFORE ANY REPLY:
1. Tracker mailbox: read_platform_dialogue since_id=2300. These posts matter:
   - #2305, #2306: Screens and the UI/UX Review charter;
   - #2307: the CoS rulings (no-push window, course timeline, unpaid RSVPs, missing handicap, live scoring, texting);
   - #2308: seat-fill;
   - #2309, #2310: my answers.
   Re-read before every response (CLAUDE.md rule 4).
2. transaction-tracker/CLAUDE.md (rules 3b/3c/3d/4, the no-push window, "Finish on main").
3. docs/claude/rsvp-and-communications-brief.md: post it, in full or as a summary with the path, to platform-claude (CoS), cc front-desk and kerry, topic front-desk. Kerry, 10/26: "Communicate with Chief of Staff. We need to ratify all of the event timeline and communications items. It needs to know specifically our details for RSVPs."
4. docs/claude/event-timeline.md, docs/claude/screens.md, docs/claude/ui-ux-review-charter.md, and docs/claude/events.md ("Payment reminder" and "RSVP payment deadline").
5. Confirm your tools: the production TGF Tracker connector (probe_golf_genius with extract="scoring-msg-templates:Payment Reminder" must answer from production). The local `tgf-transactions` server is NOT production (CLAUDE.md "It is LOCAL"). If the production connector is missing, say so first.

LIVE AS OF THIS HAND-OFF (on main, Kerry's "Deploy" each time):
- v2.581.0: one payment reminder email everywhere (email_parser/payment_reminder.py).
- v2.582.x: Admin › Screens (/admin/screens): device toggle, Try it, HTML/CSS view, collapsible sections; the reason chips' hover on the Can't make it page.
- v2.583.0: RSVP payment deadline (email_parser/rsvp_deadline.py, job rsvp_deadline). On the lock day: the 1:00 PM warning, then the 4:50 PM release (the not-playing mark plus an email) of unpaid, warned RSVP-only players. Live since 1:01 PM 10/26. Today's targets are the Tue 10/27 events. Silverhorn's one open RSVP is Christopher Espinosa (customer 802).
- v2.584.0 (pushed 1:06 PM 10/26): Screens update themselves. email_parser/screens_capture.py captures after every deploy and nightly at 3:37 AM. tools/screens_refresh.py, plus test_screens.py's watch_hash check, enforce "retake in the same commit". Bitter must load or no picture is saved; the viewer shows pictures at actual size. CONFIRM it went live, and check `screens_capture` in agent_action_log about 10 minutes after boot.

RULINGS ALREADY MADE (verbatim, do not reopen):
- 10/26 Kerry: "When we make an update to anything, the screenshots are set to update too ... that's an absolute requirement."
- 10/26 Kerry: "All screenshots need to have accurate font types and everything same as live tracker."
- 10/26 Kerry: "Those should be automated emails sent thru the tracker based on our RSVP rules." (the lock-day warning and release)
- 10/26 Kerry: "No messages go out live yet, and no event recap email detail to members about pace."

OPEN, IN ORDER:
1. Post the brief (READ FIRST #3), and put the eight rulings in its §6 to Kerry through the CoS, one at a time.
2. Verify Christopher Espinosa's warning went out (message_log, event 3303, after 1:00 PM 10/26) and, at 4:50 PM, the release, unless he paid. Report both to the Front Desk.
3. Seat-fill for paid late adds (#2310 sizing): build after Tuesday's window closes.
4. Capture recipes for the sets still taken by hand (leaderboard, score entry, Lone Star Cup), so every Screens set updates itself. Back-end pages need test-DB captures, because they carry PII.
5. The UI/UX Review lane: start it once the CoS places it (#2306).

NO-PUSH WINDOW: one hour before the first tee until one hour after the last score (#2307 item 1). Tue 10/27: Teravista's first tee is 4:08 PM and Silverhorn's shotgun is 4:30 PM, so no push to main from 3:08 PM Tuesday until the Front Desk posts WINDOW CLOSED.

SCOPE: the Tracker Build lane. NOT IN SCOPE: pace (Kerry: collect only), the Horizon repo.
