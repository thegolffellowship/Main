# Event timeline: Saturday 18 vs Tuesday 9 (read from the code, 2026-10-28)

Two real events side by side, every automatic step, Central time.
- Fall Championship (3305): Saturday 10/31, 8:00 AM shotgun, Kissing Tree. Locks Wednesday 10/28, 5:00 PM.
- Silverhorn s9.29: Tuesday 10/27, 4:30 PM shotgun. Locked Monday 10/26, 5:00 PM.

The one test behind most differences: an event whose first tee is before 1:00 PM is a "morning" event (`pairings_approval.is_morning_event`). Morning events get Event Info at noon the day before; evening events at 6:00 AM event day.

## Side by side

| # | Step | Who | Saturday 18 | Tuesday 9 |
|---|---|---|---|---|
| 1 | Invitation | Invited members | Fri 10/16, 7 AM | Wed 10/21, 7 AM |
| 2 | Reminder 1 | Not answered | Fri 10/23, 7 AM | Fri 10/23, 7 AM |
| 3 | Payment reminders | Unpaid RSVPs | Odd days of the month, 6 AM, until the lock | same |
| 4 | Reminder 2 | Not answered | Tue 10/27, 7 AM | Sun 10/25, 7 AM |
| 5 | Handicap ask "2 days out" reminder | New players, no handicap | **Thu 10/29 (after the lock)** | Sun 10/25 |
| 6 | Course update ("who's coming, we lock at 5") | Course contact, manager CC | Tue 10/27, noon | Sun 10/25, noon |
| 7 | Last call | Not answered | Wed 10/28, 7 AM | Mon 10/26, 7 AM |
| 8 | Pay by 5 PM or lose your spot | Unpaid RSVPs, Kerry CC | Wed 1:00 PM | Mon 1:00 PM |
| 9 | Handicap lock-day reminder | No-handicap players | Wed 4:00 PM | Mon 4:00 PM |
| 10 | Unpaid spots released | Warned RSVPs | Wed 4:50 PM | Mon 4:50 PM |
| 11 | **LOCK: pairings generated** | internal | **Wed 5:00 PM** | **Mon 5:00 PM** |
| 12 | Late adds seated / withdrawal repair | sheet | From Wed 5 PM, every 15 min | From Mon 5 PM |
| 13 | "Pairings ready" approval prompt | Manager | Wed ~5:05 PM | Mon ~5:05 PM |
| 14 | Auto-approve if nobody does | internal | None at 7 PM. Friday noon Event Info approves it | Mon 7:00 PM |
| 15 | **Event Info** (personal: group, cart, games, Keep score link) | Players | **Fri 10/30, noon** | **Tue 10/27, 6:00 AM** |
| 16 | **Course Files** (starter sheet, cart signs, scorecards, proximity, rules) | Course contact, manager + Kerry CC | **Fri noon** (retries only to 2:45 PM Fri) | **Tue noon** (to 2:45 PM) |
| 17 | After-lock change emails (UPDATED GROUP / tee / games) | Player, both groups, manager; changed sheets to course | Fri noon to Sat 8 AM, any hour; course stops Sat 7 AM | Tue 6 AM to 4:30 PM; course stops 3:30 PM |
| 18 | **Tee-times email** (player / open spots / course / manager) | as named | **Fri 5:00 PM** (after Event Info) | **Mon at approval, else 7:00 PM** (before Event Info) |
| 19 | Print pack (only when the course has NO contact) | Kerry / chapter | Sat 6:05 AM | Tue 6:05 AM |
| 20 | Withdrawal "dissolve a group" | sheet | **Never** (7 AM start = 7 AM cutoff) | Tue 7 AM to 3:30 PM |
| 21 | Scoring opens | Players | Sat 7:00 AM | Tue 3:30 PM |
| 22 | Shotgun | | Sat 8:00 AM | Tue 4:30 PM |
| 23 | No-show notice after 3 holes | Course, manager | in play | in play |
| 24 | Cards final, prize money recorded | internal | 15 min after each group's last score | same |
| 25 | CLOSEOUT START | Event Ops | last score + 15 min (early afternoon) | last score + 15 min |
| 26 | Admin payout report | Kerry | **not before 5 PM** | from 5 PM |
| 27 | Closeout backstop | Event Ops | ~9 PM | ~9 PM |
| 28 | Results email | Members | Sun 6:00 AM (same day not built) | Wed 6:00 AM |
| 29 | Pace report | Manager, Kerry | OFF | OFF |

## What doesn't line up

1. **The tee-times email runs backwards on a Saturday.** Tuesday: tee times Monday evening, then the full Event Info the next morning. Saturday: the full Event Info Friday noon, then the thinner tee-times email five hours later at 5 PM. Fix: for a morning event, send tee times on the lock evening (Wednesday), or keep only the open-spots version Friday.
2. **Saturday players hear nothing for about 43 hours** after the lock (Wed 5 PM to Fri noon), including late adds. Fixed by item 1.
3. **The Wednesday approval prompt quotes Tuesday times** ("7:00 PM the evening before", "Event Info 6:00 AM event day"). For the Fall Championship both are wrong; the approve page's "goes at 7:00 PM Friday" line is wrong too (it's noon Friday).
4. **No-contact print pack comes at 6:05 AM event day**, under two hours before an 8 AM shotgun, while the manager's email says "noon". Fix: send it at noon with the Course Files.
5. **Held Course Files stop retrying at 2:45 PM Friday**, though the notice says "until one hour before first tee".
6. **Group dissolve never runs for an 8 AM start**, and on Tuesday it runs after the 6 AM Event Info (so it triggers UPDATED GROUP emails). Fix: tie it to the Event Info time.
7. **Saturday change emails can go overnight** (e.g. 2 AM to the course). Fix: quiet hours 9 PM to 6 AM.
8. **Handicap "2 days out" reminder lands after the Saturday lock.** Fix: count it from the lock.
9. **"Pay by 5 PM" warning says "{event} tomorrow"** on Wednesday for a Saturday event. Fix: use the day name.
10. **Payment reminders run on odd calendar days**, so a lock-morning reminder is luck. Fix: count back from the lock.
11. **Friday and Sunday events get their last-call invite after the lock** (not these two events). Fix: set last call from the lock day.
12. **Admin payout report waits until 5 PM** even when a Saturday closes at 1 PM.
13. **Same-day results for weekend events** are not built (Event Ops #2457 Build 3).
14. Stale docs: the "evening-before 5-10 PM print pack routine" no longer exists (no double-send with Course Files); events.md still says Event Info is 6 AM for every event.

## Questions for Kerry (one word each is enough)

1. Saturday tee-times email: at the lock Wednesday evening, or drop it?
2. Quiet hours 9 PM-6 AM for after-lock emails?
3. No-contact print pack at noon the day before?
4. Group dissolve for a morning event: evening before, or first tee minus 2 hours?
5. Handicap reminder counted from the lock?
6. Weekend results: how long after the last score?
7. Payment reminders: every other day counted back from the lock?
8. Admin payout report as soon as play closes?
