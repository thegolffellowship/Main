# Late adds, lock → first tee: the manual fallback for Tue 10/27

Event Ops, Mon 10/26. For **3303 s9.29 Silverhorn** (San Antonio, **shotgun 4:30 PM**) and **3320 a9.29 Teravista** (Austin, **tee times from 4:08 PM**). Times are Central.

Asked by CoS #2308 / Front Desk #2314. Kerry, verbatim (#2308): *"Sign-ups between 5 and 7p. We need something here to automate adding to groups … We've got to get to the point of zero manager reliance. The show must go on."*

Seat-fill (the automatic version) is ruled but NOT built; Tracker Build sized it medium, after Tuesday (#2310). This is the stand-in until then. It needs no new ruling (CoS #2308) and does not wait on Kerry or Robert.

## 1. The one rule (RULED, Kerry 10/20, event-timeline.md)

- **Tee times (Teravista):** fill the **latest** threesome first, then earlier.
- **Shotgun (Silverhorn):** fill the **lowest hole** first; on one hole, **B before A**.
- **Only registered (paid) players are seated.**
  - An RSVP-only player who hasn't paid is not seated after lock (Tracker Build default, #2310).
  - Unpaid RSVPs are released at 4:50 PM by the live deadline job.
- **Pairing requests made after lock are ignored** (Kerry 10/20: "Only a manager can honor that").
- **An open seat holds a BLIND** (pairing rule 15). Seating a late add takes that blind seat; the blinds are redrawn for any seats still open.
- **No open seat left:** the player stays **Unassigned**. Event Ops posts to Kerry and the manager. The waitlist and new-group rules aren't ruled, so nothing is invented.

## 2. Who seats them, and how (the fallback)

**Event Ops seats them, on scheduled check-ins** that wake this session without anyone asking. The check-ins:

| Day | Times |
|---|---|
| Mon | 5:20 PM, 6:45 PM, 8:30 PM, 11:30 PM |
| Tue | 6:40 AM, 10:30 AM, 2:30 PM, 3:00 PM (the last one: nobody is seated after 3:08 PM, one hour before Teravista's first tee, so no course sheet goes during the window Kerry closed, #2329-4) |

At each check-in, for each event:
1. **Compare roster and seats.** Read the roster (`get_event_registrations`) and the saved sheet (`get_event_pairings`). Anyone registered and not seated is a late add.
2. **Pick the seat** by §1.
3. **Dry run** `scoring-pairings-set-sheet:<event_id>|<the full sheet with the late add in that seat>`. It must show everyone already seated, exactly once, each on their own seat, with the audit clean.
4. **Apply** with `|apply`. That saves the sheet and redraws the blinds for any seats still open.
5. **Check** with `scoring-after-lock:<event_id>` (read-only): what the 15-minute job will send.
6. **Post one line** to the mailbox: who was seated where, at what time.

Event Ops never sends an email by hand here. Every email below goes out by itself once the seat is saved.

Kerry or the manager can still place someone by hand on the PAIRINGS page (Move, open seat). The check-in then finds nothing to do.

## 3. What happens to someone who signs up, by window

| Signs up | Seated | Their emails (automatic once seated) | Their group | The course |
|---|---|---|---|---|
| **Before 4:50 PM Mon, unpaid RSVP** | dealt in at 5:00 PM if still on the roster, unless released at 4:50 | 1:00 PM deadline warning; 4:50 PM release email if unpaid | n/a | n/a |
| **5:00–7:00 PM Mon, paid** | Event Ops check-in at **5:20 or 6:45 PM**, into the draft sheet | the **tee-times email** goes on approval or at **7:00 PM**, whichever comes first, with them on it; the **7:00 AM Event Info** on Tuesday | the draft sheet changed, so the manager's review prompt re-sends (at most hourly). Groupmates see the 4th in the tee-times email and Event Info | the **course tee-times email** at approval/7 PM carries the updated sheet |
| **7:00 PM–midnight Mon, paid** | Event Ops check-in at **8:30 or 11:30 PM** | the **tee-times job** runs every 15 minutes from 7 PM to midnight and sends once per person, so they get their own tee-times email within 15 minutes of being seated; then **7:00 AM Event Info** | groupmates already had their tee-times email (old group). Tuesday's **7:00 AM Event Info** shows them the 4th | the course had the 7 PM sheet; the **noon Course Files** carry the new one |
| **Midnight–7:00 AM Tue, paid** | Event Ops check-in at **6:40 AM** | **7:00 AM Event Info** with their group | same: 7:00 AM Event Info shows the 4th | noon Course Files |
| **7:00 AM–first tee Tue, paid** | Event Ops check-in at **10:30 AM, 2:30 PM or 3:00 PM** | the **after-lock job** (every 15 minutes, baseline = the 7 AM Event Info send): the player gets the Event Info, marked "UPDATED GROUP" | everyone in that group gets it with a notice naming who joined; the **manager is CC'd** | if the Course Files have gone, the course gets **only the changed sheets** (that group's scorecard and cart sign), CC the manager and Kerry; before noon, the noon Course Files carry it |
| **After 3:08 PM Tue** (one hour before first tee) | not seated by Event Ops; the manager decides at the course | none | n/a | the manager decides at the course |

A first-timer, guest or new member placed as a late add:
- their group's notice carries Kerry's welcome line;
- their own email opens with the Rules of Play link (v2.575.12).

## 4. Things this does NOT cover (say them, don't guess)

- **More late adds than open seats** (Silverhorn 1, Teravista 2 at lock): no waitlist or new-group rule exists. They stay Unassigned and Event Ops posts to Kerry and the manager.
- **A paid late add asking to play with someone:** ignored after lock (ruled). A manager may still do it by hand.
- **RSVP-only after 4:50 PM:** not seated. Payment reminders stop at the lock (Kerry #2313; the stop-at-lock guard is Tracker Build 5's, for Kerry's Deploy tonight).
- **Tomorrow's no-push window** (new rule #2307-1): Teravista 3:08 PM until one hour after the last score of either event. Seating is a data change, not a deploy, so the 2:30 and 3:00 PM check-ins still run. There is no 3:50 PM check-in: Kerry ruled course sheets stop one hour before first tee (#2329-4), and the 15-minute job has no course-only switch until Tracker Build 5's item 0c ships.
