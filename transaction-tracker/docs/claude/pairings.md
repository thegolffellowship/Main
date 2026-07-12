# TGF Pairing Standards — ruleset of record

Kerry, in-session 2026-07-12 (verbatim intent, lightly structured).
**Explicitly NOT exhaustive** — Kerry's first direction: request the
pairing docs platform-claude (CA) holds and merge them here BEFORE the
engine build (mailbox request posted same session). Per house
principle 2, these ship as named, editable rules-as-data, not code.

## Why this matters (Kerry)

"We are The Golf Fellowship and getting to know everyone is part of
who we are." The engine is heavily based on who's played with whom,
maximizing NEW pairings every round. Who RODE together (cart pairs)
matters too, not just the foursome.

## The rules (Kerry, 2026-07-12)

1. **One playing-partner request per person per event.**
2. **TGF reserves the right to fill the remainder of the foursome.**
3. **Random pairing driven by history** — all-time played-with history
   is tracked and reflected, but the operative goal is SEASON-scoped:
   everyone plays with everyone else at least once each season.
4. **Guests pair with their inviter** unless otherwise requested.
5. **Admin and manager can always override** automated pairings.
6. **Every foursome contains at least one member who has played
   before** (experienced anchor).
7. **Ambassadors are spread across groups as captains** — pace of
   play + welcoming new guests/members.
8. **A match (match play) overrides a request** when the two conflict.
9. **Members may fill their foursome with first-time guests.**
10. **Request communication is part of signup** (Platform build):
    when someone signs up, notify whom they've requested.
11. **A request from or for a person LOCKS both players** from further
    requests for that event, unless the other declines.

## Ratified (Kerry, in-session 2026-07-12)

- **customer_id amendment: GO** ("Yes on customer id thing") — rebuild
  pairing_history keyed by customer_id + archive-event support +
  played-with/rode-with distinction. event_pairings joins the same
  amendment (see audit below).
- **Cart-pair ruling:** cart partners derive from the SEQUENCE of the
  pairing on the tee sheet / scorecard — **spots 1 & 2 ride together,
  spots 3 & 4 ride together.** (Scorecard groups preserve player order,
  so rode-with history IS recoverable from the archive walks.)
- **Priority order: NOT final.** Kerry + CA are vetting the full
  directive set; final ordering comes back as direction. The order
  sketched under Engine notes remains a non-ratified draft.

## Rule-6 audit (Kerry-directed, run 2026-07-12)

Swept all 104 CREATE TABLEs + the boot-time customer_id migration
registry. Person-bearing tables WITHOUT customer_id — the complete
list of remaining violators:

1. **pairing_history** (player_a/player_b names) — fix ratified above.
2. **event_pairings** (player_name, cart_pos) — same family, rides the
   same amendment.

Everything else person-bearing is compliant via design or boot
migrations (items, rsvps, season_contests, handicap_rounds,
handicap_player_links, customer_aliases, cmp_matches/cmp_bracket via
player/opponent/winner-id columns, all gg_history_*/gg_member_map).
`name_parse_failures` is exempt by nature — it is the log of names
that COULDN'T resolve to a customer.

## Data feeds

- **Played-with history**: scorecard groups (shared
  `scoring_rounds.gg_aggregate_id` = actually teed off together) —
  already banked by every GG-history holes walk (2025 done, more
  seasons as walks run) — plus `event_pairings` for app-run events,
  plus the future tee-sheet scrape (Kerry's ruling: tee sheets
  primary / starter-sheet PDFs cross-check / score groups tiebreaker).
- **Rode-with history (cart pairs)**: `event_pairings.cart_pos` for
  app-run events. GG scorecard groups do NOT carry cart splits;
  archive cart data only where tee sheets published it.
- **`pairing_history` amendment (RULE 3B — awaiting Kerry's explicit
  ratification):** key pairs by customer_id (currently name-keyed —
  rule-6 violation) + allow archive events (events-FK is NOT NULL
  today) + distinguish played-with vs rode-with.

## Engine notes (design, not yet built)

- Season-coverage objective (rule 3) is the optimizer's primary term;
  all-time history is the tiebreak/novelty signal.
- Constraint order when they conflict: manager override (5) > match
  assignment (8) > request lock (1/11) > guest-inviter binding (4) >
  experienced-anchor (6) + ambassador-spread (7) > coverage
  maximization (3).  ← inferred, NOT ratified — confirm with Kerry.
- Requests: one per person per event; mutual locking per rule 11;
  decline releases the lock.
