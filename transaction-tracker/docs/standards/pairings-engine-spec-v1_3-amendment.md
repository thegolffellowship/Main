# Pairings Engine Spec v1.3: amendment to v1.2 (DRAFT for the Librarian)

Kerry gave these three rules on 2026-10-12, 5:35 PM CDT (Front Desk, mailbox #1633). They amend `TGF_Pairings_Engine_Spec_v1_2.md` (Project / OneDrive; it is not in this repo). The Librarian files v1.3 with this text.

**Kerry, verbatim:** "New rule for pairings. I don't want any first year players riding on their own in initial pairings unless it can't be avoided. For instance. Michele McCormick is shown on her own. I don't want that. Also, I just removed and re-seated after removing Chris Espinosa triggered that. However, that reduced us to 20 players. So the reseat should trigger a reduction in groups from 6 to 5 groups, reseating according to pairings rules/standards. Another thing I observe is that 2nd time guest, Hector Hinojosa is being placed with Michelle DelCarmen who is not an ambassador. I would like all guests to always be placed with an ambassador, unless they are the guest of one of our members, or requests someone specificially."

## R-H: a first year player never rides alone

- A first year player never takes the solo seat of a short group in the initial pairings, unless no other sheet keeps the requests, matches and locks.
- First year means:
  - **1Y**: joined as a new member in the event's year, and has no handicap round before that year;
  - **or 1st Timer**: their first event.
- **Hard** in the audit.

## R-H2: rule tiers (Kerry 2026-10-12, second message)

Kerry, verbatim: "1st Timers have additional rules to First Year members. You graduate from 1st Timer rules into First Year rules. In other words, some of the rules, like riding/playing with an Ambassador drop. 1st Timer and First Year member rules do need to supercede count rules, only if there's a conflict."

- **1st Timer** = the First Year rules + the Ambassador rule (R-A).
- **First Year** = never alone (R-H).
- Both outrank every count rule when they conflict:
  - repeat counts and repeats in sequence;
  - cart history (R-G);
  - solo streaks (R-C).
- Requests and Match Play are not count rules, so they are unchanged.

## R-I: a reseat that frees a group re-deals

- **When:** a player is removed before the event starts, and the field now fits fewer groups (ceil of players / 4).
- **What happens:**
  - the group count drops;
  - the short groups are dealt again under every rule;
  - a full group keeps its seats unless they break R-H or R-J.
- **What never happens:**
  - nothing changes once the event has started (rule 15b);
  - nothing is re-dealt while the roster and the sheet disagree.

## R-J: every guest rides with an Ambassador

- A guest (not a member) rides in a cart with an Ambassador.
- **Exempt:**
  - the guest of a member who is playing in the event;
  - a guest whose own request names a player who is in the event.
- A request for someone who is not playing does not exempt the guest.
- **Hard** in the audit.

## Ambassador source (for Kerry to confirm)

- The generator reads the Ambassador chip on the customer (`customers.ambassador`).
- The audit reads the per-chapter flag (`customer_ambassadors`).
- They agree for the 10/13 field.
- R-J should read the per-chapter flag, as R-A does in v1.2. Kerry to confirm.

## Built and tested

- Built in v2.551.0 (not live until Kerry says "Deploy").
- Behaviour of record: `docs/claude/pairings.md`, "Rules 16-18".
