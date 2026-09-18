# Crews — the participation-rate lever (proposal, 2026-09-17)

**Status: PROPOSED by tracker-claude, not ratified. Nothing built.** Member-
facing + scope → rule 3b. Belongs in a Tracker lane, not the Insider lane.

## Why

The 2027 target (40 SA / 30 Austin per Tuesday) needs members playing one
Tuesday in two instead of one in three. Twenty seasons of data say the
core (7+ nights) holds and the middle fades, hardest in fall (Q4 work,
daylight, football). Only one thing has ever been tried on the rate:
Kerry texting people personally — which works and does not scale (Kerry
is the bottleneck, Oct 2025). Plus membership arrives in 2027 as the
price-side incentive; crews are the people-side incentive and can start
NOW, in the fall field, as a pilot.

## The shape

- A **crew** is ~12 members of one chapter, mixed handicaps, built around
  people who already play together (pairing_history + partner requests +
  the FELLOWSHIP filter know who those are).
- A **crew leader** is a member, not a manager: one job, one text, Monday.
  "Who's in Tuesday at Brackenridge? I'm in." Reply-to-leader, not to TGF.
- **The Tracker does the leader's homework** so the job is 90 seconds:
  Monday morning it sends the leader a prefilled message (event, course,
  tee time window, who in the crew is already registered, who has not
  played in 3+ weeks) through the existing plain-text composer / Message
  Players preset. Leader edits or just forwards.
- **Recognition, not discounts** (Sarah): the crew that fields the most
  members over a month gets named in the Insider (first name + last
  initial), a crew line on the leaderboard page, and nothing that costs
  money. Streak stats are free: "your 6th Tuesday this year" on the
  handicap card and in the Monday text.
- **Leader load rule (Pastor Dave / Jim):** leaders rotate every season;
  a leader who goes quiet two Mondays gets a nudge from the chapter
  manager, never a guilt trip; crews are belonging groups, not sales teams.

## Pilot (October 2026, both chapters — rule 3d)

- Two crews per chapter (24 members each chapter), leaders picked by
  Kerry, members picked with him from the ranked participation list:
  half regulars, half one-in-three players. Control = the rest of the
  active roster.
- Runs s9.26–s9.29 / a9.26–a9.29 (Oct 6 – Oct 27), four Tuesdays.
- Measure: crew members' Tuesday rate vs control, same four weeks, vs
  each member's own spring rate. Success = crews play ≥ 1.3× control.
- Cost: zero dollars; Kerry's time = picking eight people and one
  kickoff text; the Tracker's time = one composer preset + one Monday
  job (small; existing pieces).

## What the Tracker needs (if ratified)

1. `crews` table (crew_id, chapter, name, leader customer_id, season) +
   `crew_members` (crew_id, customer_id, joined_at, left_at) — schema →
   rule 3b.
2. Monday 8 AM Central job: per crew, a prefilled text to the leader via
   the plain-text composer (reuse `handoff-2026-09-08` pieces).
3. A crew column on `/participation` and a crew filter on the pairings
   page (pair crews together when they ask; never force it).
4. Scorecard Routine (Friday) reports crew vs control weekly.

## Open for Kerry

- First two crew leaders per chapter (names).
- Pilot in October with the fall field, or wait for the March kickoff?
  (tracker-claude: October — the fall is exactly the condition crews
  exist to fix, and a small field makes the effect visible.)
- Whether crews are named by the members or by TGF.
