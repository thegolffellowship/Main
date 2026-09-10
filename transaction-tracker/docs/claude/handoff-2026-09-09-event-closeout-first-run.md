# Session record — 2026-09-09 · first run of the event closeout (s9.22 Silverhorn, a9.22 ShadowGlen)

**v2.347.2 (documentation) → v2.348.0 (one data-integrity fix, §3b).**
Branch `claude/mail-from-ca-79xa2a`, pushed to `main` (Railway deploys
from `main`).

Kerry's instruction: *"Close out the two events from 2026-09-08. Use the
`event-closeout` skill … Start at Phase 1. Work both chapters, report per
chapter, and tell me plainly what you did NOT do and why."*

---

## 1. Two premises were wrong before the first command ran

**1.1 The skill did not exist.** The 2026-09-08 commit message says it
adds `.claude/skills/event-closeout/SKILL.md`; the diff does not contain
it. The repo-root `.gitignore` ignored `.claude/` wholesale, so the file
was written into an ignored directory in an ephemeral container and never
reached git. Confirmed: no `SKILL.md` anywhere in history, on any branch.
The routine was rebuilt from mailbox #430 §2–3 (which describes the five
phases and the five OPEN items in detail), the bridge-command inventory in
`mcp_server.py`, and the first live run. `.gitignore` now reads
`.claude/*` + `!.claude/skills/`, so this cannot happen again.

**1.2 "scoring-rounds returns [] for BOTH" was a filter artifact.**
`get_scoring_rounds(event=)` / `scoring-rounds:<x>` match the event NAME
as a substring. Filtering on `3306` returns nothing; filtering on `9.22`
returned 40 rows — 24 Silverhorn, 16 ShadowGlen — imported by the hourly
auto-sync at 18:10–20:12 CDT on game night. Nothing downstream was
"undone" because of missing cards. The skill now says this in its first
section.

## 2. What the auto-sync had already done (Phase 0)

For both events, before this session started: scorecards (ALL Net → ALL
Gross), GG-recorded winners (`gg_game_results`), self-computed MVP badges
(Rideout MVP + TGF MVP; Youngs / Cloer Co-MVP), and payout rows
auto-recorded (`auto: …`, 19 SA + 12 Austin, all PENDING). The course
bills posted as Chase alerts the same evening (SilverHorn $1,169.10,
Shadowglen $692.80 — one each, equal to field × course_cost).

## 3. What this session did, per chapter

### San Antonio — s9.22 Silverhorn (3306)

| Step | Result |
|---|---|
| Cards | 24 of 24 active registrations; all `customer_id` resolved; verify on Rideout 3428 `all_ok` |
| GG boards | CTP #13 + #16 (Baker), Ind Net 2 flights (Rideout / Vasquez $67.50), Skins Gross (Youngs 3, Anthis, Espinosa, Niester, Young), Team Net T1 ×2 — all with GG purses |
| GG MVP cross-check | `scoring-mvp-import` round 1708028 → `gg_recorded_mvp: ["RIDEOUT, Jeff"]`, matches ours |
| Final pairings | `team\|sa\|1708028\|apply` — 6 groups, 0 blind, **36 pairs written**, unresolved `[]` |
| Handicaps | preview clean (24 rows, no flags) → `hcp-import … \|apply` **24 rounds written**, recap emailed to kerry@ + robert.straiton1@ |
| Payouts | 19 rows, **$515.00 PENDING** (Rideout $159.50 across four rows) |
| Financial | net revenue $1,899.43, course $1,169.10, projected profit $672.59, `accounting_verified`, 100% allocation |
| HIO pot line | present, 24 players |
| First-timers | Espinosa (skin), Hinojosa + Lewis (winning Team Net) — all three cashed |
| Recap | `docs/claude/recaps/2026-09-08-s9.22-silverhorn.md` (DRAFT) |

One number worth a glance: the financial summary's `revenue_discrepancy`
gap of −$338 (order totals $2,165 vs item prices $1,827) is other items
riding in the same orders (fall buy-ins, membership), not missing event
revenue. `accounting_verified` is true.

### Austin — a9.22 ShadowGlen (3313)

| Step | Result |
|---|---|
| Cards | 16 of 16; **one `customer_id: null` — Tom Donovan** (below); verify on Youngs 3452 `all_ok` |
| GG boards | Ind Net T1 (Cloer / Youngs) and Team Net (Straiton / Johnston / Youngs / Sekiguchi) — **both with `purse: 0.0`**; **no Skins board, no CTP board** on GG |
| GG MVP cross-check | `scoring-mvp-import` round 1702842 → 0 winners (GG leaves an unresolved T1 empty); ours splits Co-MVP — consistent |
| Identity fix | `scoring-resolve:Donovan, Tom` → null; customers row is **"Thomas Donovan"** (cid 796). `scoring-alias-add:Thomas Donovan\|Tom Donovan`, then `scoring-import-event:a9.22@1702842\|refresh=Donovan` (16 replaced, 16 verified). Round 3449 now carries cid 796 |
| Final pairings | `team\|austin\|1702842\|apply` — 3 groups, 0 blind, **18 pairs written**, unresolved `[]` (was `["Donovan, Tom"]` before the alias) |
| Handicaps | preview clean (16 rows) → **16 rounds written**, recap emailed to kerry@ + robert.straiton1@ |
| Payouts | 12 rows, **$291.00 PENDING**, of which **$117.00 is Skins the tracker shadow-computed** with no GG board behind it |
| Financial | net revenue $1,135.45, course $692.80, projected profit $401.52, `accounting_verified`, 100% allocation |
| First-timers | Sekiguchi + Johnston (winning Team Net), Compton, Donovan — 4 of 16 |
| Recap | `docs/claude/recaps/2026-09-08-a9.22-shadowglen.md` (DRAFT; skins and CTP deliberately absent) |

Both chapters: `sync_season_contests()` → `enrolled: 0, linked: 92`.

### 3b. Kerry's correction, and the hazard it uncovered (v2.348.0)

Kerry, after the report: *"Tom Donovan should be the base member's name
and Thomas Donovan the alias."* Two writes: `scoring-customer-set:796|
first_name|Tom` and `scoring-alias-add:Tom Donovan|Thomas Donovan`.

The first one mangled his record. `update_customer_info` built the
display name from the INCOMING fields only, so a one-field rename set
`items.customer = "Tom"` and cascaded that surname-less label into
`customer_aliases.customer_name` and `handicap_player_links.customer_name`.
`get_customer_details("Donovan")` then returned nothing. The UI card never
hit this because it always sends first and last together; the bridge sends
one field. Protect the class: the display name is now built from the
MERGED parts (incoming over on-record), the cascade is keyed on
`customer_id` with a name sweep only for unlinked rows, it runs on every
name change (so a repair pass can re-stamp rows a bad label left behind),
and a name alias equal to the canonical name is deleted. `scoring-alias-add`
now stores `customer_id` at insert and refuses a self-alias. Test:
`test_customer_rename_cascade.py` (14 checks).

Repair on production = re-send the same one field after deploy; the
verification is in §5.

### 3c. Store registration links (v2.357.0 — numbered after merging the Sales & Growth lane's 2.349–2.356 from main)

Kerry, pasting the Avery Ranch product URL: *"Are you able to grab other
current event URLs and add them to the Event pages for email or text
presets? You could just add a box in each of the Event Creator/Edit
modals … After the events they become obsolete and should be removed or
something."*

The box already existed (`registration_url`, #417 D, consumed by the Lead
Center texts) — it was hand-typed or blank. Now derived from the event
name, verified against the store before it is saved (GoDaddy soft-404s
to the shop index, so a 200 alone is not proof), surfaced in Edit Event
with a state badge + Verify + Use-suggested, filled on Add Event right
after create, swept daily at 06:00 Central, and marked EXPIRED (not
deleted — past events are frozen) once the date passes. `{event_url}` in
Message Players, with the same send-refuses-with-a-reason guard as
`{manager_phone}`. Full rule: `docs/claude/events.md` § Store
registration link. Test: `test_event_links.py` (32 checks).

**What could not be verified from this container:** the store is
unreachable through the session proxy, so the checker's soft-404 rule
was tested with an injected fetch and then run for real on production
through `scoring-event-links` after deploy — see the digest for what the
store actually answered.

### 3d. The Silverhorn recap went out (2026-09-10), and what it taught

Kerry asked for the recap "to send out" and to "consider what previous
event results were to catch any trends, like Jeff Rideout." The trend:
Rideout was the s9.21 headline too — two Tuesdays, two 49s, two City
MVPs, two TGF MVPs, $124 + $159.50. Draft v2 carried it with a verified
comparison table; Kerry edited and sent, then said "Learn from it."
`event-recaps.md` 20–29 are the lessons (no humor at a member's expense
is rule 20 for a reason); the sent text is the template of record in
`docs/claude/recaps/2026-09-08-s9.22-silverhorn.md` with a draft-vs-sent
table.

His Quarry link was `s9-23-quarry`, not the derived `s9-23-the-quarry`:
the store drops "the". v2.363.0 makes the derivation try variants
(strict → without dropped words → before a pipe) and save the first the
store answers for. Live sweep after deploy: s9.27 The Quarry filled via
the variant (strict 404, variant 200); 11 of 17 upcoming events
verified; 6 October events have no store page yet (s9.26 Olympia Hills,
a9.26 Star Ranch, a9.27 Avery Ranch, a9.28 Forest Creek, a9.29
Teravista, s18.12 FALL CHAMPIONSHIP).

**Two lanes on `main`, twice today.** The Sales & Growth / lead-campaign
lane pushed between my pushes both times. Merge commits, never rebase;
version.js is the only file that conflicts and is resolved by taking
main's copy and renumbering my entry above theirs. Lesson banked: a
`git merge` on a DIRTY tree aborts and my commit lands beside main, not
on it — commit first, merge second, and read `git ls-remote` after every
push.

### 3e. The card sends are on record, and reading them found 32 cards for 16 players (v2.364.0 → v2.365.0)

Kerry, 2026-09-10 morning: "Just sent handicap cards for both events...is
there a historical record logged when those are sent?" Yes. Every bulk
card send has logged to `message_log` under event_name `handicap-card`
since the feature shipped; nothing could read that table from a session
until `scoring-message-log` (v2.364.0). The read-back:

| day (UTC) | cards sent |
|---|---|
| 2026-09-10 15:06–15:07 | 31 — 19 Silverhorn players + 12 ShadowGlen players, one batch, status `sent`, sent_by `admin` |
| 2026-09-02 | 26 |
| 2026-08-31 | 26 |
| 2026-08-26 | 37 |

Field 24 + 16 = 40, cards 31. The nine without a card (SA: Lewis,
Hinojosa, McCormick, Wallace, Espinosa; Austin: Johnston, Compton,
Sekiguchi, Donovan) are the players with no established index yet —
`/api/handicaps/send-bulk-email` skips anyone whose `handicap_index_9` is
null, by design. Not a defect; worth knowing when a first-timer asks why
they got nothing. (The route still matches event registrants to
handicap links by NAME — rule 6 debt, noted, not touched today.)

Reconciling the recipients against the fields is what surfaced the
second finding: `get_scoring_rounds("a9.22 ShadowGlen")` returned 32
rows. Two full sets — ids 3447–3462 (league round key `1702842`,
aggregates 2433694xxx, imported 9/8 23:12 and 9/9 01:12) and 3463–3478
(key NULL, aggregates 2434241xxx, imported 9/9 18:12:21, the hourly
auto-sync's slot). Chain: the closeout's targeted re-import
(`scoring-import-event:a9.22@1702842`, the Donovan refresh) stamped the
key onto the auto-synced rows via the replace path; Kerry added the
Skins/CTP boards on GG that afternoon, which re-keyed the tournament's
aggregate ids; the keyless auto-sync then found no keyless twin and
inserted a second set. `scoring-hcp-preview` showed it plainly: 16
`already_imported: true`, 16 `false` — 16 differentials waiting to
double-post had anyone run the import again. Silverhorn (24 rows, never
keyed) was clean.

Shipped in v2.365.0: the dedupe treats a missing key on either side as a
wildcard (exact matches sort first, so multi-round days stay apart), a
keyless re-import keeps the stored key, a keyed import stamps its key on
a keyless twin it skips; and `scoring-dedupe-rounds[:<event>|all][|apply]`
repairs rows already doubled (keeper = the bridged card; bridge moved,
loser's holes + row deleted, its open discrepancy item closed).
Applied on production after the deploy — see §5.

### 3f. The first production scan, and three morning questions (v2.366.0)

`scoring-dedupe-rounds:all` on v2.365.0 reported 120 groups across five
events. Reading them before applying anything: a9.22 (16, the class
above) and s18.10 FALL KICKOFF (27, a 2026-08-31 re-import under new GG
aggregate ids; hole-for-hole identical) are real; TGF SAN ANTONIO /
AUSTIN CHAMPIONSHIP (32 + 16, same import minute, unbridged twins) need
the hole comparison to say; and the 2026 TGF CHAMPIONSHIP's 29 were NOT
duplicates — Saturday's and Sunday's cards share an event id, and the
grouping had ignored the date. v2.366.0 scopes by date and classifies
every group from the hole scores; apply touches only `identical` and
`partial`. Result of the apply is in §5.

Three things Kerry hit the same morning, all fallout from the 2026-09-09
membership-only historical import (`scoring-import-orders 2025-01-01..
2025-07-31|membership-only`, then Aug–Dec):

- **"Where'd Straiton and others go?"** — the import created 2025
  membership terms that had already expired; `sync_player_status_with_terms`
  then demoted their holders to `expired_member` (Robert Straiton: one
  term, 2025-01-02 → 2026-01-02, no 2026 renewal on file; status flipped
  23:33:53 UTC), and the Handicaps page's MEMBERS toggle hides
  non-members. `scoring-status-changes:2026-09-09` lists every flip with
  the status before. Who is genuinely lapsed vs comped/paid-off-books is
  Kerry's call — the Brevo nightly sync already pushed the new statuses
  at 09:10, so a reversal needs to reach Brevo too.
- **Luke Mazanec "duplicate" renewal** — item 2721 (2025-09-10, $50,
  imported 9/9) vs item 2807 (2026-09-10, $75). A renewal, not a
  duplicate; rule fixed (customers.md), item closed.
- **Six action items** — four phone drifts on 2025 orders (Duran, Carter,
  Dyal, Tonche) and Dan Tarr's 2025-07-10 Twin Creeks order (GUEST rate
  + membership, no guest name: he was the guest). HubSpot agrees with
  the ORDER for Dyal ((210) 557-1765; canonical (270) is wrong) and with
  the CANONICAL for Tonche ((979) 236-8787). Duran and Carter are not in
  HubSpot by name.

### 3g. Kerry's rulings on the morning's questions (v2.368.0)

Verbatim, 2026-09-10 late morning, and what each became:

- *"Robert Straiton is a Manager. Until that changes he is automatically
  a member, without any dues. He is comped, yes, but as we've discussed
  financially with CA, we need to note what that comp amount is for tax
  purposes."* → the `chapter_managers` dial carries `customer_id`; the
  terms→status sync opens a `Manager comp` term (source manual, price 0,
  value $75 in notes) whenever a manager has no term covering today.
  The finance lane owns how the comp value is booked (customers.md).
- *"When someone renews prior to the 365 date, their new membership
  should continue at the 365 date, not reset to the date of the
  renewal."* → `continued_start` on the live and backfill paths;
  `scoring-membership-terms-repair` for terms recorded the old way.
- Phones: Duran (254) 278-1722 and Carter (210) 378-8073 — canonical is
  right, drift warnings dismissed; Dyal → (210) 557-1765 set on the
  customer (HubSpot agreed). Tonche canonical right. Dan Tarr was the
  guest himself: dismissed.
- *"Rochford and Gwin are both correctly Alumni now."* → no change.
- Landa Park (s18.10): *"Reimports are correct for Aguilera and Ayala as I
  entered the remaining missing scores manually. Atkinson and their 4th
  were partial cards that should not be recorded into handicaps."* →
  Aguilera/Ayala: the 8/29 cards dropped with their differentials
  (`scoring-round-drop … |unpost`), the 8/31 cards re-posted through the
  two-nines path; Atkinson + Decareaux: `hcp_exclude` set, their four
  handicap rounds unposted, Atkinson's 10-hole duplicate dropped.

Mailbox #453 (2026-09-10 16:13 UTC) routed the Wednesday-AM TGF Insider
auto-draft build to this lane per Kerry — queued behind the above; see
§4.

### 3h. The v2.368.0 boot incident, and its cleanup (v2.368.1–2.368.3)

The first boot carrying the continuation rule re-ran the historical
membership backfill and, because its idempotency was keyed on
`(customer_id, started_at)` instead of the source item, re-inserted ~188
past items as new terms at their continued start. Two shapes: (a) the
item already had a term → a duplicate a year later (127 rows); (b) the
item's purchase had been entered BY HAND by Kerry on 2026-07-01 (a manual
term with no item link) → the continuation rule read that manual term as
a prior term and stacked a second year on top (61 rows). The status sync
at 16:17:10 UTC then upgraded 50 lapsed members to active_member. Fixed
in three steps, all applied on production between 16:20 and 16:30 UTC,
before the nightly Brevo sync: per-item idempotency + the dedupe
(2.368.1/2), the manual-term guard + the purge of that boot's rows
(2.368.3). Verify with `scoring-status-changes:2026-09-10 16:00`.

Lessons for the class: an idempotency key must be the SOURCE identity,
never a derived value; and a rule that changes a derived value needs its
own backfill dry-run BEFORE it runs at boot — this one ran at boot first.

HELD for Kerry: the early-renewal repair (`scoring-membership-terms-repair`,
29 candidates). Several are two purchases days apart on one customer
(cid 7: 06-26 and 06-28; cid 87: 07-20 and 07-27; cid 38: three in 2026),
which may be family buys attributed to the buyer or refunded duplicates,
not renewals. Also 12 older duplicate terms from earlier backfills
(order dates re-extracted) listed by `scoring-membership-terms-dedupe`.

## 4. NOT done, and why

- **Wednesday-AM TGF Insider auto-draft (mailbox #453, Kerry-routed to
  this lane 2026-09-10).** Not started this session — the rulings above
  came first. Spec of record: `session-prompt-2026-09-02-brevo-next.md`
  (Brevo DRAFT to list 3 excluding segment 2, sender 1, tag
  `public-recap`, Wednesday 13:00 UTC, bridge `scoring-brevo-draft[:dry]`,
  public-variant rules in event-recaps.md). Kerry's answer needed first:
  does an Insider #2 go out by hand this week?

1. **Handicap cards were not emailed to the players who played (Phase
   3.3).** The only path is `/api/handicaps/send-bulk-email` behind the
   manager login — the Handicaps page, Email Handicap Cards, **By
   Event**. No bridge command exists and building one is a member-facing
   send path outside the login (rule 3b) — OPEN 6. Handicaps ARE posted,
   so the cards Kerry sends will carry Tuesday's index.
2. **No payout was marked paid.** 31 rows PENDING across both events
   ($806.00). Paying is Kerry's Venmo; the receipt matcher closes them.
3. **No recap was sent.** Two drafts exist. Who sends is OPEN 2; Austin's
   draft has one blank left (September points; the venue came later —
   "ShadowGlen was right at the course clubhouse", now on the event).
4. **Austin Skins / CTP left as recorded.** The shadow Skins rows were not
   deleted and no CTP was invented. OPEN 7.
5. **Course-bill expenses not linked to their events.** No course charge
   in the ledger carries an `event_name`; that is the standing pattern,
   not a defect introduced Tuesday. Flagged, not patched.
6. **The stale footnote on `scoring-hcp-preview`** ("needs Kerry's ruling
   before any self-derived import ships") was left in code. The ruling
   exists (D1 / NDB, 2026-07-14); the note misleads. One-line fix, not
   made in a documentation-only deploy.
7. **First-timer follow-up (Phase 5.2)** — no first-timer template exists
   on the shelf (eight system templates, none for first-timers). The seven
   names are in the recap drafts.
8. **CA mailbox #428** — still none of the seven asks executed. Unchanged.

## 5. Verified against production

**2026-09-10, v2.366.0 — the duplicate-card repair, applied.** Per-event
runs (the `all` scan timed out on the hole comparison; per-event is the
working shape):

| Event | groups | identical | partial | conflict (held) | rows dropped |
|---|---|---|---|---|---|
| a9.22 ShadowGlen | 16 | 16 | 0 | 0 | 16 |
| s18.10 FALL KICKOFF | 27 | 23 | 1 | 3 | 24 |
| TGF SAN ANTONIO CHAMPIONSHIP | 32 | 32 | 0 | 0 | 32 |
| TGF AUSTIN CHAMPIONSHIP | 16 | 16 | 0 | 0 | 16 |
| 2026 TGF CHAMPIONSHIP | 0 (8/15 and 8/16 are two rounds) | | | | 0 |

88 duplicate cards removed; every keeper was the card the handicap
records were bridged to, so no bridge moved. The three HELD groups on
s18.10 are real disagreements between the 8/29 import (bridged, kept)
and the 8/31 23:44 re-import: Hector Aguilera 103 vs 97, Elio Ayala 116
vs 105, Bob Atkinson 18 holes vs a 10-hole card. GG's current board is
the truth for those; if the 8/31 numbers are the corrected ones, the
fix is `scoring-import-event:s18.10|refresh=Aguilera,Ayala` (which also
re-posts their differentials) — Kerry's call, not taken.


- `get_scoring_rounds` counts before and after; Donovan's row re-read
  with cid 796 after the refresh.
- Pairing applies report `applied: true` and pairs written; the Austin
  dry-run before the alias listed the unresolved name, the apply after it
  did not.
- Both `hcp-import … |apply` results: `skipped: []`, `recap_email.ok`.
- `determine_tgf_mvp` re-read after the MVP import shows GG's Rideout
  beside ours.
- `version.js` polled on production after the push (see the deploy line
  at the top).

## 6. The two standing asks — both answered 2026-09-09 evening

- **San Antonio `lead_notify_recipients`: CLOSED.** Kerry: *"SA lead
  pings are just me."* SA leads already ping the default list, which is
  Kerry's inbox; no SA entry is needed. Item removed from the queue.
- **Fellowship meeting spot: re-designed, not answered.** Kerry: *"Max &
  Louie's was just for that event. We go to different places for each
  event. Some, like next week, are right in the clubhouse on site."* So
  the venue is per EVENT — v2.358.0 adds `events.fellowship_spot` on the
  GENERAL tab and the preset renders `{fellowship_spot}`. His message
  carried a literal "[venue]" placeholder for Austin, so the a9.22 recap
  draft still has its blank; for a9.23 Avery Ranch he will type the spot
  into Edit Event before sending the preset.

## 7. OPEN for Kerry — from the skill, verbatim

1. Timing — deadline on handicaps vs recap?
2. Who sends the recap?
3. Photos in the recap?
4. Fellowship attendance — record it, and where?
5. The self-filling per-event checklist — Tracker or Platform?
6. A bridge for the By-Event handicap-card send (new this run).
7. Shadow-computed payouts with no GG board — record or hold (new).
8. HIO pot pre-counting future registrations (new).
