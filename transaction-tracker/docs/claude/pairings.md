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

## CA/platform-claude docs merge (mailbox #134, 2026-07-12)

Vetting verdict: NO conflicts with Kerry's 11 rules. Additions:
- **Pairing MODES are first-class per event**: standard | **ABCD
  Night** (one A/B/C/D handicap-band player per foursome) | **Dream
  Team** (full player choice, no random assignment). From the live
  website FAQ — Kerry's list omitted these.
- **Foursome Lock System is the engine's runtime** (Error Handling
  Spec §7, ratified): lock at 5pm day-before (9-hole) / 3-days-before
  (18-hole) / custom; pairings generate at/after lock; post-lock only
  complete foursomes may add (max 3, until start); withdrawal reopen
  scenarios defined there.
- **Constraint inputs beyond foursome composition**: TEE-TIME
  preference ("need latest tee time") and CART needs — engine places
  constrained players into compatible slots; cart-pair assignment
  (1&2 / 3&4) honors them.
- **Guest-host association is already structural** (registration +
  roster "Guest of [Member]") → feeds guest-with-inviter directly.
- **Lane ruling**: Tracker builds the V2-era engine (correct home);
  Platform V1.0 only captures the request at signup; Kerry's rule 10
  (signup request-notification) needs a Platform scope decision
  (CA recommends V1.5).
- **CA's proposed build order** (Kerry to finalize): history banking
  (running) → customer_id migration (ratified) → standard-mode rules
  engine → tee/cart/match constraint layer → ABCD/Dream Team modes →
  manager override UI → Platform signup flow.

## GG tee-sheet ingest (v2.94.0 — Kerry overnight directive 2026-07-14)

Bridge commands (`scoring-pairings:` on probe_golf_genius):
`rounds|<sa|austin|page_url>` lists the portal TEE SHEETS widget's
rounds; `round|<portal>|<round_id>[|apply]` parses/writes one;
`all|<portal>[|apply]` walks everything (time-budgeted, resumable).
Discovery: portal menu → TEE SHEETS page → iframe widget (cached).
Parsing (`_parse_teesheet_groups`) handles fill-down time-cell rows
and one-row-per-group layouts; unknown layouts return debug_tables
over the bridge for diagnosis without a redeploy. Players resolve via
`_resolve_scoring_player`; rows store canonical names + customer ids.
**Apply REPLACES the event's pairing_history rows** (tee sheet =
ruled primary source) — same replace semantics as an app-side save,
so app-save and GG-ingest can't double-count an event.

**Ratified customer_id amendment: implemented ADDITIVELY** —
pairing_history gains customer_a_id / customer_b_id / rode / source
('app'|'gg_teesheet'); `save_event_pairings` writes all four (rode by
cart_pos 1&2 / 3&4). The full name-key retirement still pends the
archive-events (nullable event_id) design.

`get_pairing_history_counts(year)` — the generator's season-scoped
repeat-minimizing signal — reads this table unchanged, so ingested
history immediately drives maximize-new-pairings.

## GG TEAM/CART Net board ingest (v2.95.0 — the route that WORKS)

The tee-sheet route above hit two walls the night it shipped: the
public TEE SHEETS page hosts a `next_round` widget (upcoming event
only, no round selector, unpublished pairings render as an
alphabetized confirmed-players grid), and the PLAYER TIMES TOGETHER
page (5783331) is login-gated. **Working source:** each played
round's `tournament_results` widget lists a **TEAM Net $** board
(SA, foursomes; "TEAM Net 18 $" on 18-hole rounds) or **CART Net $**
board (Austin, cart pairs) whose rows are the ACTUAL playing groups
in seat order — e.g. "SOUTH, Daniel + MORENO, Robert + WADE, Mary +
Bl[HAMILTON, Doug] TGF San Antonio".

Bridge commands: `scoring-pairings:teamrounds|<portal>` (round
selector off the results widget), `team|<portal>|<round_id>[|apply]`,
`teamall|<portal>[|apply]` (budgeted, resumable). Source column:
`'gg_teamnet'`; same replace-per-event semantics.

Caveats of record:
- **Blind-draw fills** (`Bl[Name]`) are on the card but not in the
  group: parsed as EMPTY seats — excluded from played-with pairs,
  but the seat is kept so the 1&2 / 3&4 cart split stays aligned.
- **SA rode flags assume board order = tee-sheet seat order** (team
  boards are built from the tee sheet; verify against a published
  tee sheet when one appears). Austin CART rows are cart pairs by
  definition — rode=1 is exact.
- **Austin has NO foursome board** — only cart pairs land; the
  other-cart half of each Austin foursome is not publicly derivable
  (scorecard aggregates are per-player on the 2026 portals).
- Rounds whose label carries no event code and a truncated date
  (preseason: KICKOFF/LA CANTERA/CEDAR CREEK options are cut off
  mid-date by GG) may not match a Tracker event — they surface in
  the walk report as unmatched, not silently skipped. The `team|`
  subcommand takes an event override (`|apply|<event id or name>`).

### 2026 grab COMPLETE (overnight 2026-07-14, Kerry directive)

All 41 played rounds ingested with source `'gg_teamnet'`:
- **SA (22 rounds)**: s9.1–s9.17 (no s9.6/s9.11 — not in GG's round
  list, both 0-registration Tracker events, presumed rained out),
  s18.1–s18.7, LA CANTERA + the two override applies (KICKOFF → 609,
  Feb CEDAR CREEK → 3). ~865 pairs. s18.5 WILLOW SPRINGS used a
  "CART Net 18 $" board → cart pairs only (7).
- **Austin (19 rounds)**: a9.1–a9.17 (no a9.6, same pattern),
  a18.1–a18.3. ~490 pairs. a9.17 Falconhead + a18.3 CRYSTAL FALLS
  are CART-board rounds (pairs only); the rest have TEAM boards, so
  Austin DOES get foursomes most weeks.
- Zero unresolved player names across both portals.
- **Kerry flags from the walk**: (1) Tracker has BOTH
  `a18.2 AUSTIN KICKOFF | ShadowGlen` (id 2578, Mar 14 — the real
  a18.2, matches GG) and `a18.2 CRYSTAL FALLS` (id 3267, May 30,
  11 regs) alongside `a18.3 CRYSTAL FALLS` (id 3263, May 30, 12
  regs) — 3267 looks like a mislabeled twin of 3263 and its
  registrations may need merging; (2) HILL COUNTRY MATCHES |
  Comanche Trace (May 16) is not on either league portal's round
  list — no pairings ingested for it.
- Tonight's s9.18 / a9.18 post AFTER play: re-run
  `scoring-pairings:teamall|<portal>|apply` any time — replace
  semantics make it idempotent, and new rounds are picked up.

## Engine notes (design, not yet built)

- Season-coverage objective (rule 3) is the optimizer's primary term;
  all-time history is the tiebreak/novelty signal.
- Constraint order when they conflict: manager override (5) > match
  assignment (8) > request lock (1/11) > guest-inviter binding (4) >
  experienced-anchor (6) + ambassador-spread (7) > coverage
  maximization (3).  ← inferred, NOT ratified — confirm with Kerry.
- Requests: one per person per event; mutual locking per rule 11;
  decline releases the lock.
