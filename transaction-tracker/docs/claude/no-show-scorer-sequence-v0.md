# No-show player: the scorer's sequence (one page, for Kerry)

Event Ops, Monday 10/26. Kerry asked: *"Do we have a no-show player sequence for scorers? We talked about it a couple weeks ago."*

**Yes. You ratified it on Wednesday 9/30** (mailbox #1021, Track A's build contract). It also sits in the Pairings Engine Spec v1.4, section 12.2 (accepted 9/30, CoS #1046). **It is not built yet.** Nothing in the scoring code today has a "Player missing" button or an absent mark.

## What you ratified on 9/30 (your words in quotes)

1. **A red "Player missing" button** at the bottom of every hole screen, from the first hole on. *"Tapping − for x is not intuitive. I think on the first hole there needs to be an obvious red player missing button at the bottom. Then that opens up a prompt of who it is. Then follows up with the three answers."*
2. **The scorer taps it, picks who, and answers "Is [Name] coming?"** with one of three answers:
   - **Running late, keep him on the card.**
   - **No, take him off this card.** He's marked absent; he can be added back with "+ Player".
   - **Don't know yet.** It asks again on each hole. *"It should ask each hole until after 4 holes and then the player is taken off card."*
3. **What an absent player counts for:**
   - **Skins:** *"in for skins (if bought in) on the holes they played."*
   - **Team / Cart Net:** his ball counts on the holes he played. *"A blind needs to be auto drawn by system to fill in the missed holes for the team … visual and documented for players to see on leaderboards."*
   - **Individual Net / Gross, MVP, points, handicap:** out (an incomplete round).
4. **A blank hole is never filled with par.**
5. **Moving a player on the day** (section 12.2):
   - The **manager** has a 3-tap "Move to…" on Live Scoring.
   - The **scorer** can mark someone absent on one card and "+ Player" him onto another, choosing the seat.
   - A scorer may **not** take an active player off another card, change tees, handicaps or games, or move anyone after lock.
   - A "moved by scorer" badge shows. The manager sees it, and the closeout notes it.

## New since then (Monday 10/26, #2329)

*"Any no shows should just be communicated to the course after about 3 holes."* So, once built, the Tracker sends the course **one** no-show notice after about 3 holes, and nothing else during play.

**One thing to settle:** 9/30 says the scorer's "don't know yet" turns into absent **after 4 holes**; today's line says the course is told **after about 3**. **Should both be 3?** (Recommended: yes, one number.)

## What happens TODAY, until it's built

- **The scorer leaves the no-show's holes blank.** That card then **never goes final**, and a non-final card **holds the whole event**: no payouts recorded, no points, no 6:00 AM results email.
- **The fix today is a person.** The manager (or Kerry) takes the player off the pairings on the Events page. Live scoring then drops him from the open card, and his entries are kept in the audit (v2.575.16, the Paul Reed fix on 10/20). The group's card can then go final.
- **The course isn't told automatically.**

**That's the gap: a no-show can stop the whole night's money until someone is reached.** "Zero manager reliance" needs the scorer's button.

## Proposed build order (after Tuesday, for your OK)

1. **The Player-missing button** with the three answers, and the absent mark after the agreed number of holes.
2. **The absent mark releases the card**, so it can go final without anyone stepping in.
3. **The course no-show notice** after about 3 holes (once per event, all no-shows in one message, manager CC'd).
4. **The per-hole blind** for Team / Cart Net, shown on the leaderboard.
5. **Manager "Move to…" and the scorer's move**, per section 12.2. This needs a design pass first, as ruled.

Items 1–3 together end the "no-show holds the night" problem. Items 4–5 are the fuller version you described.
