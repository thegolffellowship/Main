# Facebook Events — description standard (Kerry, revived 2026-09-14)

Kerry posts upcoming Tuesday events as Facebook Events ("any pub is
better than no pub"). Last run May 2026 (s9.10 Brackenridge). The copy
below is the standard; only the facts block changes per event.

## Event name / fields

- Name: `Tuesday Golf | THE QUARRY` (course in caps).
- Location: the course's full name. Start time: the shotgun time, or
  the first tee time.
- Cover: TGF 20-seasons artwork over a course photo.

## Description (template)

```
Looking for a regular game and new friends to play with? You found it.

Every Tuesday night, The Golf Fellowship tees it up at the best courses in {CITY} — and there's always a spot for someone new.

Play your own ball. Compete with a team rooting for you. Stay for drinks after. Twenty seasons of turning foursomes into friendships — and it starts right here.
-----------------------------
{Weekday}, {Month D} | {Course full name}

9 holes | {5:00p Shotgun | Tee times from 4:39p} — Members, Guests & First-Timers welcome
[18 holes | {times} — Members only]        ← only when the store sells an 18-hole option

Members: ${member}
Guests: ${guest}
First-Timers: ${first_timer}
- Includes green fees, cart{, range balls}, team competition, closest to pin, and cash prizes.
- Optional add-ons: NET Games ${net} | GROSS Games ${gross}

Questions? Text Kerry: 210.838.3948

REGISTER: {events.registration_url}
```

## Where each fact comes from

- Times, range balls, first-timer price, link: the Tracker event row —
  what `scoring-lead-sms:<lead>|p1` renders for that chapter's next
  Tuesday (`start_phrase`, `range_balls`, `first_timer_price`, `link`).
- Member / add-on prices: the event's own registrations
  (`get_event_registrations`) — Member with no games, +NET, +BOTH are
  the sold prices. Guest = Member + $10 on a 9 (leads.py
  `first_timer_price` docstring; 1st Timer = Guest − $25). Prefer a
  sold guest row when one exists.
- Brand rules (TGF_Brand_Messaging_Standards v1.6): count SEASONS, never
  attach the count to a chapter; never "golf league"; San Antonio and
  Austin only; the hole-in-one pot is one pot across all of TGF.
- The store page itself is the final check (blocked from the remote
  session's proxy — Kerry eyeballs it).

## 2026-09-15 (first posts back)

s9.23 The Quarry: 5:00p shotgun, range balls; Members $58 / Guests $68 /
First-Timers $43; NET $16, GROSS $16; no 18-hole option sold.
a9.23 Avery Ranch: tee times from 4:39p, no range balls; Members $75 /
Guests $85 / First-Timers $60; NET $16, GROSS $16.

## Not built (candidate)

A bridge `scoring-fb-event:<event>` that renders this block from the
Tracker, so the post is a paste. Every input above is already on the
event row or its registrations.
