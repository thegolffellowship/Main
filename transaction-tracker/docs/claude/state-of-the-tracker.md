# State of the Tracker — 18 September 2026 (Platform-facing brief)

Audience: the claude.ai "The Golf Fellowship" Project, where TGF Platform
planning lives. Purpose: tell that planning context what the Tracker
actually is today, which rules are RATIFIED and load-bearing, what is
open, and what the Platform must carry forward. Maintained by
tracker-claude. This is a **full rewrite at v2.464.8 (2026-09-18)**;
the previous body described v2.296 with wave sections appended. After
this brief, the mailbox (`read_platform_dialogue`, posts #536 onward)
and `docs/claude/handoff-*.md` are the session-by-session record.

## 1. What the Tracker is now

Flask + SQLite (WAL) on Railway (`tgf-tracker.up.railway.app`), one
worker, **v2.464.8**, ~200+ routes, 70 MCP tools plus ~150 `scoring-*`
bridge commands behind `probe_golf_genius`. It started as a GoDaddy
order-email parser in the spring; it now runs a live event night for
two chapters at once and most of the business around it.

| Area | What is live | Doc |
|---|---|---|
| Orders & money | AI email parsing (Claude, Haiku default / Sonnet for membership combos), deterministic contest-flag reads, credits / transfers / partial credits, **ONE ORDER ONE FEE** (fee prorated by item price to the cent), refunds console, payouts with screenshot import, Apple Pay + one-modal Mark Paid | events.md, unified-financial-model.md, `fee_splits.py` |
| Identity | `customer_id` everywhere (principle 6); aliases; merge repair at boot; five canonical resolvers; **home chapter never written from an order** — a blank profile is a listed guess until Kerry confirms it (`scoring-chapter-guesses`) | customers.md, customer-merge-repair.md |
| Events & pairings | RSVPs parsed from GG mail; ONE roster builder (`_event_roster_rows`); generator with Kerry's 15 rules incl. Match-Play-dictates-pairings and pace staging; blinds; starter sheet / cart signs / divisions & flights print packs; GG tee-sheet and team-board ingests that **preserve what they do not carry** | pairings.md |
| Handicaps | TGF 9-hole index from our own posted rounds (best-N of 20 ×0.96 + WHS adjustment); **ONE computation on every surface, locked to the event once it tees off**; course cards as data, nines labelled from yardage or from played history; handicap cards mailed by customer_id (Kerry sends) | handicaps.md, handicap-projection.md |
| Scoring & games | Pure engine (`live_scoring.py`) from raw gross hole scores; skins / Individual Net / Team Net / Cart Net / MVP / CTP-HIO; the games matrix as the governing layer with variants (Skins ½ Net below 8 buyers on a nine); the plus rule; live event board with money held until the field is complete | side-games.md, game-engine.md, live-scoring-test-center.md, live-scoring-spec-for-ca.md |
| Season contests | City Net / Fellowship Cup / Players Cup / Monthly / Fall races with exact-cents payouts; Match Play knockout with live cards; Lone Star Cup seats + cascades; points-race staleness fixed on the event's own clock | events.md, game-engine.md |
| Members | Pinless Spotlight / Leaderboard / Handicaps; `/me`; link-preview cards; member traffic analytics | member-portal.md |
| Growth & comms | Lead Center (Meta → HubSpot → Tracker, 48-hour alarm, campaign CPL/CPP/CPMem); Tracker→Brevo nightly status sync; **the Insider writer** (AI drafts to Kerry for approval, never auto-posts); event recaps in house style | leads.md, event-recaps.md, handoff-2026-09-16-insider-writer.md |
| History | GG archive 2016–2026 ingested: standings for 32 portals, field walks (47,896 result rows), 7,254 hole-by-hole cards 2019–2024 on top of 2025; participation series by season × chapter | gg-history.md, handoff-2026-09-17-gg-history-2019-2024.md |
| Accounting | Multi-entity ledger, bank reconciliation, cash flow, duplicate detective, Money Flow, margin ledger + liability buckets; nightly off-site backup with a passed restore drill | bank-reconciliation.md, margin_ledger, database-backup-gap.md |
| Governance | CA Queue (`/admin/ca-queue`), the mailbox, spin-off skill, closeout skill, rules 3b / 3d / 4 | ca-queue.md, CLAUDE.md |

## 2. Rules of record (ratified — the Platform implements these, not GG's)

**League mechanics (verified against live GG, July 2026).** Race points =
each player's Stableford in the event's POINTS game floored at 0 (net for
NET races, gross for The Players Cup); no position→points table. Season
standing = best 10 events + City Championship. Monthly races count ALL
points in the month; purse = $1 × active members at month close; ties
split. `member_card_id` == GG profile id. MVP = purse>0 rows in the
event's MVP game, one per city per event. **Events-played = DISTINCT
EVENTS from registrations** (an event with many nines counts once).

**Handicaps.** Index = `compute_handicap_index` over the last 20
differentials in the lookback window (best-N per the WHS table, ×0.96,
adjustment, rounded to a tenth); 18-hole index = 2 × nine. A starting
handicap is typed as an 18-hole number and never reads like an
established index. **The handicap lock (2026-09-16):** once an event has
teed off (`_event_started`: past date; today at/after start time; today
with no time), every surface reads the index in effect that morning —
rounds posted before that day — and nothing is stored (rounds do not
change, so the number does not). ROSTER, PAIRINGS, generator, starter
sheet and flights report are views of the one computation; a saved
sheet's `handicap_index` is a fallback, never the answer.

**Flighting & payouts (2026-09-18/19, revised #582; as data in
`email_parser/flighting.py`).** Ladders <6.0 / 6.0–11.9 / 12.0+ (4
flights add 12.0–17.9 / 18.0+), exclusive upper bounds, cut lines never
move; NO minimum flight size, NO merging; flight labels derive from
actual membership; places by FLIGHT size (1–9 → 1; 10–19 → 2/3–1/3;
20+ → 50/30/20; ties pool and split to the pot); Individual Gross pot =
10% off the top as the Overall Low Gross bonus + 90% by headcount;
Skins keeps the matrix pot ÷ flights; Individual Net keeps the matrix
place columns. The cut per game is EVEN (down the middle — an odd field
puts the SMALLER half in Flight 1 and a tie on the cut goes UP whole,
never split; Ind Net's default) or HCP (the ladder, Skins/Gross default), one shared toggle per
game bar; dragging a name to another flight makes the game CUSTOM on its
base cut (`flight_modes:<event_id>`, customer_id-keyed moves; #599,
v2.478.0). SELECTION freezes at an explicit action (FREEZE button, built
v2.471.0); AMOUNTS recompute at settlement from actual buyers. Visible
per event on the FLIGHTS tab — dry run, GG pays. FLIGHTS and PAIRINGS
auto-save (the drop is the save; PAIRINGS in the background 1.2 s after
the last change, Save kept as the manual flush).

**The plus rule (2026-09-15/16).** A plus handicap comes off the ROUND,
never off a hole: no hole is ever made harder than the card says, and
the give-back is deducted once from the round's net and points.
Rounding of that round deduction is **half away from zero** (0.5 → 1,
2.5 → 3). MVP reads the game view from `PLUS_RULE_EFFECTIVE_DATE` =
2026-09-15 forward; earlier events stay decided on the WHS arithmetic
(principle 4). The WHS/index call sites keep the plus stroke (net double
bogey is `par + 2 + strokes_received`).

**Allowances (2026-09-16, side-games lane).** Team Net follows the ball
count: best 1 of 4 = 75%, best 2 = 85%, best 3 or 4 = 100% (USGA
four-player ladder, confirmed). Cart Net 1-ball = 85% forward (75% is
history and stays history); Cart Net 2-ball = 100% by Kerry's ruling.
Individual Net and MVP = 100%. Skins ½ Net = 50% **on the unrounded
course handicap, rounded ONCE, half-up** — applying the allowance to an
already-rounded number double-rounds (the a9.23 lesson: our "rounding
question" was numbers we had computed wrong). Allowance % and "off the
lowest" are separate dials. **Governing rule: "Until we detach from GG,
GG rules. When untethered, obviously we rule everything."**

**Money on game night.** No dollar and no win tint until every hole of
every player is in (`_event_field_complete`); the board names who still
owes holes. The board recomputes from raw facts; Golf Genius is one
input, not the record.

**Pairings (pairings.md, rules 1–15).** Kerry's standard of record,
Match Play dictates pairings, pace staging, fivesomes legal
(2026-07-31), and rule 15: a credited/WD player leaves the sheet by
himself (checked at the boundary in credit/refund/wd/transfer), a BLIND
fills the seat — drawn among members with an established handicap,
fewest blinds this year first, one per person per event, re-seated
across regenerations by person not by seat (15f ratified 2026-09-16).
**15g: an ingest may not erase what it does not carry** — the Team Net
board says finish order only, so hole labels, tees and ids are
preserved across it; the tee on a sheet is read from the ROSTER.

**Orders.** ONE ORDER, ONE FEE (2026-09-09): the transaction fee is
prorated across items by price, to the cent. A contest add-on line
printed on the order is a fact (`contest_flags_from_body`), and REMOVED
STAYS REMOVED. `customers.chapter` is the HOME chapter; `items.chapter`
is where the event was.

**Display standards.** Tee bands from the club's tee ORDER number, not
yardage; the women's tee is an outline and the word is **"Women"** on
both legends (`TEE_LEGEND_WOMEN_WORD`); one mobile breakpoint (560px);
one green means bought in; the house expand arrow is orange.

## 3. Game day, as it runs now

On 2026-09-15 two chapters played simultaneously (s9.23 The Quarry, 21;
a9.23 Avery Ranch, 12) and the board was what Kerry watched from the
course. What that night forced, and what the Platform needs on day one:

- A polling loop on the event's own clock (`poll_live_events`, every 5
  minutes, skipping unstarted and settled events). Every calendar-day
  boundary goes through `timezone_utils` — Railway runs UTC and this bit
  twice in one night, client then server.
- Money waits for the field; the board recomputes; a mid-round GG pull
  that froze a Team Net classification was corrected by re-walk +
  re-record, not by trust.
- The starter sheet prints PH and TEAM from our own index and the
  course card; a card whose nine cannot be established prints no number
  rather than a guess — and the nine is now established from yardage
  against the 18-hole row, or, absent that, from the rounds already
  played off the row (Avery Ranch labelled itself from history).
- The closeout skill (`.claude/skills/event-closeout/SKILL.md`) is the
  post-event routine: scorecards in, FINAL pairings ingested, payouts
  verified, handicaps posted, cards offered (Kerry sends), contests
  synced, recap drafted. Its lesson from this week: run the tee-sheet
  ingest before GG archives the round; the team-board ingest is safe
  now but carries no holes.

## 4. The data estate

- **Identity:** every enrollment / score / prize / RSVP row carries
  `customer_id`; boot backfills link what parse-time could not. The
  handicap-card path resolves by id (v2.459.0); `scoring-hcp-link-audit`
  reports the residue. GG history 2016–2021 and closed chapters predate
  the roster map: **1,217 pending names** at `/admin/gg-history`.
- **History:** participation series 2016–2026 is measured, not
  remembered. Total participation is at a record (SA 1,248 player-rounds
  in 2025 vs 932 in the 2018 peak; 168 distinct vs 157); the per-Tuesday
  field fell because the calendar tripled (10 nights → 22–38); the 2022
  slide happened INSIDE 2022, spring 54 → fall 18–20; Austin's trough was
  2024 and 2025 rebuilt it wide and shallow. Fall is the soft spot every
  year since 2022. (Mailbox #550–#559.)
- **Comms audience:** ~70% of Insider recipients have never bought;
  prospects click at 2–4× the never-bought rate; former members open
  most and click least (#543).
- **Backups:** nightly `VACUUM INTO` → gzip → OneDrive; restore drill
  passed 2026-09-03. Still one SQLite file on one volume.
- **Credentials live:** Meta System User token, HubSpot service key,
  `Files.ReadWrite.All`; Brevo and HubSpot polls idle without their env.

## 5. Open decisions (Kerry's — every one lives on the CA Queue, not in a transcript)

- Cart Net 2-ball allowance is a Kerry ruling (100%), not USGA; the
  four-player ladder is confirmed, the two-player rows are not (#8).
- No allowance row for a FIVESOME; a five-player Best 1 falls to 75% by
  assumption (#9).
- Stroke-index convention: two live in our data (true GG indexes vs
  re-ranked 1..N); full-card allocation on a re-ranked nine under-
  allocates, so `allocate_strokes` now raises rather than silently
  paying wrong; the card path stays on `subset` until an event
  discriminates it (#10). Related: a PH of 3 delivers two strokes on a
  nine under full-card, and a plus handicapper may get nothing back on a
  front nine with odd indexes — real money, never said out loud.
- `game_templates` per-event snapshots are designed, not built (schema,
  rule 3b): a past event recomputes under TODAY's game config — right by
  luck until the snapshot exists (principle 4 not yet satisfied).
- Handicap lock is derived, not stored; a back-dated or deleted round
  moves an as-of index. A stored snapshot needs schema (3b).
- Eric Pollard's home chapter (only order was DFW).
- Flighting, still open after #599 (v2.478.0): the Final Pairings send
  OFFERING the freeze; the closeout writing the settled snapshot; a
  Matrix-page editor for `gross_places_by_flight_size`; the P2-6
  closeout comparison of `gg_game_flights` against the frozen selection.
  (Freeze schema, FREEZE button, EVEN|HCP|CUSTOM and auto-save are built.)

## 6. What the Platform must carry forward (lessons, each paid for)

1. **Identity is resolved at write time, at every ingest boundary,
   including a third party's spelling.** Two live surfaces failed on a
   name string this month (handicap cards, a posted round). Never a
   late-bound join on display names.
2. **Protect the class, not the instance.** Each of this week's defects
   was an instance of a mechanism: an ingest that erased what it did not
   carry, a repaint that knew one layout, a map that had its own
   formula, a guard armed in one direction. Fix the mechanism and write
   the test that enumerates the class.
3. **A rule that only warns is not a rule.** `half_net_below` sat in
   config with a comment naming the gap and the engine computed the
   wrong game anyway. Refuse or report where someone looks.
4. **When a derived value will not reconcile, re-derive it from the
   source before building on it** — the ½ Net "rounding question" was a
   number we had computed wrong.
5. **Past events are frozen; derive don't store where the inputs are
   immutable; snapshot where they are not** (game config, prices).
6. **Money waits for complete data.** A half-posted field naming a
   winner is worse than showing nothing.
7. **Timezone:** every "what day is it" is Central; the container is UTC.
8. **Boundaries, not sources:** validate what leaves the system (mail,
   SMS, print) — the composer, the templates, the starter sheet all
   needed a check at the exit.
9. **Backfill rule:** anything that arms state going forward needs a
   backfill for the rows that predate it.
10. **One computation per fact.** Two caches, two formulas or two
    breakpoints for the same fact will disagree on the night it matters.

## 7. Timeline of waves (pointers, not prose)

- **July 8–14 (v2.5x → v2.104):** own handicaps ratified; pairing engine
  + Match Play dictates pairings + pace staging; season-contest
  economics; member tier + Nav Shell v2; event cancellation suite; GG
  archive walked. (handicaps.md, pairings.md, member-portal.md)
- **July 29 – Aug 1 (v2.150 → v2.176):** Live Scoring Test Center +
  parity gate; the flighting rule; live championship standings; first
  live shadow at the SA Championship. (live-scoring-test-center.md,
  handoff-2026-08-01-live-standings.md)
- **August finals (v2.24x → v2.255):** live Match Play cards; Lone Star
  Cup rules in code; parser hallucination guard; payment-method-aware
  refunds; link-preview cards. (events.md, game-engine.md)
- **Sept 1–3 (v2.257 → v2.296):** Lead Center funnel + Meta stats;
  duplicate-lead merge; nightly off-site backups + restore drill; the
  HubSpot decommission and UX directives. (leads.md, the three
  directive docs)
- **Sept 8 (v2.336 → v2.346):** one pairings roster; open-seat picker;
  fellowship outreach; plain-text composer; three send-path hazards
  closed. (handoff-2026-09-08-pairings-fellowship-composer.md)
- **Sept 9 (v2.347 → v2.357):** closeout skill first run; ONE ORDER ONE
  FEE; contest flags from the order text; date-range order import.
  (handoff-2026-09-09-event-closeout-first-run.md)
- **Sept 15 event night (v2.437 → v2.458):** rule 15 + blinds; money
  hold; leaderboard wave; plus rule; the timezone trap twice.
  (handoff-2026-09-15-event-night-leaderboard.md)
- **Sept 16–18 (v2.458 → v2.464):** handicap identity + plus in the
  mechanism (v2.459); side games codified, ½ Net proven against GG's
  published PH column (v2.460–461); **the handicap lock, PAIRINGS =
  ROSTER, Avery Ranch nines from history** (v2.462); Insider writer live
  behind the review dial (v2.463); GG history 2016–2026 + participation
  series (v2.464). (handoff-2026-09-16-side-games-codify.md,
  handoff-2026-09-16-insider-writer.md,
  handoff-2026-09-17-gg-history-2019-2024.md, mailbox #536–#560)

## 8. Plan of record: native app + website

See member-portal.md → "Platform roadmap". One backend, two faces (admin
website + member app): mobile-first portal (live) → PWA with offline
score entry → Capacitor native wrap → native extras. API-first `/api/me`
from day one. **Stack ruling (Kerry, 2026-09-16):** Supabase (managed
Postgres + auth + Realtime + RLS) for live leaderboards — one scorer per
group with lock/take-over rules so there is no double entry; Redis-class
infrastructure only if per-viewer personalised state at volume is ever
needed, which a leaderboard is not. Supabase Realtime ceilings to plan
around: 200 / 500 / 10,000 connections by plan.

## 9. Gateways discipline

No TGF Platform coding until gateways pass. The Tracker is the
sandbox/bridge; everything here is built portable (CLAUDE.md guiding
principles: rules-based, `customer_id` identity, past-events-frozen,
admin/manager/customer layers). Rule 3b: money, schema, member-facing
behaviour and scope ship only on Kerry's explicit ratification. Rule 3d:
an instruction applies to every chapter unless one is named.

## 10. How to talk to tracker-claude

- **read_platform_dialogue / post_platform_dialogue** — the mailbox.
  Every post starts with a `TO:` line; sign `author='platform-claude'`.
  tracker-claude reads before every reply to Kerry and posts digests at
  session end. **⚠ Two servers carry these tool names** (incident
  #257–#259): the claude.ai connector is PRODUCTION; the repo-root
  `.mcp.json` stdio server is a LOCAL, EMPTY SQLite. Discriminate with
  `get_statistics` before trusting any read; never run money operations
  locally.
- **get_tracker_docs** — list/read CLAUDE.md + `docs/claude/*`.
- **probe_golf_genius extract=scoring-…** — ~150 read-mostly bridges
  (`scoring-pairings:sheet|<id>`, `scoring-blinds:<event>`,
  `scoring-skins-audit`, `scoring-hcp-link-audit`,
  `scoring-chapter-guesses`, `scoring-gg-history:*`, …); writes are
  gated behind `apply` / `confirm` and logged to the agent action log.
- **CA Queue** (`list/upsert/note/close_ca_queue_item`) — every decision
  that is Kerry's.
- **Live data** — the remaining MCP tools query production directly.
