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

### 3i. The TGF Insider auto-draft, built (v2.369.0)

`email_parser/insider.py` (routed here by #453). Gather → compose →
render → lint → Brevo DRAFT → email Kerry the link; scheduled Wednesdays
13:00 UTC as `insider_draft` beside `brevo_sync`; bridge
`scoring-brevo-draft[:dry|apply]`. The data map and copy rules are in
event-recaps.md (BUILT block); `test_insider.py` covers a two-chapter
week, the lint gate, dry-run-never-calls-Brevo, empty window, single
chapter. Deliberate choices: the module is its own file rather than
brevo.py (the sync must not share a blast radius with a copywriter);
the lint refuses `apply` on any banned word or stray dollar figure, so
a bad data row cannot ship a rule break; every proper name in the send
is first name + last initial. First real draft: only after Kerry reads
the dry run.

Dry run on production (v2.369.2/.3, 2026-09-10 16:47 UTC): subject
"TGF Insider | First round. First payday."; s9.22 24 cards / 12 cashed,
a9.22 16 cards / 9 cashed; 7 first-timers by registration tag (SA
Espinosa, Hinojosa, Lewis; AUS Compton, Donovan, Johnston, Sekiguchi),
6 of whom cashed — checked against `scoring-gg-results` (Espinosa par on
10 skin, Donovan BOGEY on 4 skin, the other four on T1 team-net cards;
Compton did not cash). Lint clean. Two corrections came out of the first
dry run: the no-earlier-card first-timer guess over-counted (a
MEMBER-tagged registrant whose rounds predate the scorecard imports) →
the 1st TIMER tag decides; `str.capitalize` produced "san antonio" →
first-letter-only. Rendered copy of record:
`docs/claude/recaps/2026-09-10-insider-draft-s9.22-a9.22.html`. The
scheduler's first unattended run is Wednesday 2026-09-16 13:00 UTC in
DRAFT mode (v2.369.5). Kerry's two rulings, 2026-09-10, verbatim: "We
always need to review and discuss the Insider mailings until I'm
confident enough to automate it a little more." and, on seeing the dry
run: "Update the dial to create the Brevo draft directly each wednesday
at 8am. I'll review it there because I can see all the visual with it
too. And then I'll work with you for edits before sending so you can
learn from it." So: the job creates the Brevo DRAFT and emails him the
link; he reviews in Brevo; edits come back through this lane (a
revision is a new draft — Brevo has no campaign update API); nothing
sends itself. His first edit — the skins sentence ("alone
sounds...lonely", skins unexplained) — is folded into `compose()` and
recorded in event-recaps.md. Dial `insider_autodraft` = draft (default)
| review | off.

Second review pass (v2.369.7), all Kerry's edits verbatim in
event-recaps.md: first-timers = tag OR new member (8, not 7); "special
tee" cut; ONE rotating highlight band (skill percentages this week, HIO
pot next, dial `insider_highlight`); "How a TGF Event works"; Kerry's
Compete line; Celebrate per chapter from `fellowship_spot` (3306 set to
Max & Louie's); Handicaps page gained chapter badges beside names
(`templates/handicaps.html`). Third pass (v2.369.9–.10): beat 2 "6 of the 8",
Jump-in header, centered eyebrow/headline; Handicaps page index sizing,
HIGH tag gone, pending-players band, Dallas navy / Houston teal badges,
chapter fallback, store capitalisation. Insider #2 SENT by Kerry from
Brevo draft #18 at 13:36 CDT 2026-09-10 (1,244 recipients). Cadence
ruling: WEEKLY stays; opens/click trends are the metric, not unsubs
(event-recaps.md). Next: read #18 at +24h; first unattended draft Wed
2026-09-16 13:00 UTC (highlight rotation → Hole-In-One pot).

### 3j. Second live run — a18.5 FOREST CREEK (Sat 2026-09-12, Austin, 18 holes)

Kerry 2:29 PM: "Forest Creek is ready for close out." Field 16 = 16
cards (no dupes); parity all_ok on Youngs + Cloer; GG boards: Ind Net,
Skins (8 winners), Team Net (winner $128 + 3 board rows); NO CTP board.
MVP import recorded Youngs; determine_tgf_mvp agrees (22 pts). 15 payout
rows auto-recorded, all PENDING $492.01. Financial summary verified,
coverage 100, course_fees 1,818.60 = 16 × 113.66 — but Chase carries TWO
Forest Creek alerts on 9/12 ($1,818.60 AND $2,270.00): the #428 class,
flagged to Kerry, not patched. Contests sync enrolled 0. HIO pot 3,351
after tonight.

Two fixes shipped mid-run: (1) v2.387.1 — the team-board pairings
parser dropped a whole foursome when a seat was a plain "First Last"
(GG's unlinked/guest print; Zac Hammond) — the WINNING team, 3 of 4
groups; plain names are now seats. Pairings applied after the fix: 4
groups, 16 rows, 24 pairs. (2) v2.387.2 — `scoring-customer-merge`
bridge (dry run + audited apply): the GG spelling "Hightower, Geoffery"
had minted customer 823 alongside the registrant Geoff Hightower (818);
aliased, then 823 folded into 818 (payout, ledger row, standings row,
card all re-pointed) BEFORE pairings were written. Canonical = the
customer's own store spelling, per the Donovan precedent.

Phase 3 posted 3:14 PM after Kerry read the per-nine numbers off the
GG tee editor (screenshots of all five tees): 32 handicap_rounds, 16
players, 0 skipped — Blue 3447 F 35.9/133 B 36.3/131, White 3448 F
35.2/125 B 35.2/125, Red(L) 3462 F 34.1/121 B 34.4/120 (now in
handicaps.md "Per-nine ratings of record" so Forest Creek never asks
again). The Chase $2,270.00 was charged AND reversed the same day
(Kerry's screenshot) — nets to zero, only the $1,818.60 stands; a
separate $200.00 ALAMO CITY GOLF TRAIL alert on 9/11 is not tied to an
event yet. 3.3 (By Event card send) and 3.4 (GG upload) are Kerry's;
`scoring-message-log:handicap-card` showed no 9/12 sends at 3:14 PM.
Recap draft:
`docs/claude/recaps/2026-09-12-a18.5-forest-creek.{txt,html}` — three
Kerry blanks (fellowship, tee times, the Luke-not-bought-in line).

### 3k. Third live run — s9.23 THE QUARRY + a9.23 AVERY RANCH (Tue 2026-09-15), run Wed 6:50–7:20 AM

Kerry: "Yeah do closeout for last nights events. Like you said, much was
done last night." True — the improvements + handicap-surfaces lanes had
already posted every handicap (21 SA, 11 of 12 Austin) and emailed the
cards twice (01:52 and 02:06 UTC, the second after the index fix), and
Kerry had paid every payout (14 SA rows, 12 Austin, all PAID by 9/15).
What the run added:

- **Identity:** GG spelled "AREVALO, Guillermo"; the store row is
  "Guilermo Arevalo" (821). The card AND its posted handicap round carried
  customer_id NULL (rule 6 breach, one row). Alias added; `refresh=` on the
  keyed import dropped nothing (`refreshed_players_dropped: []` — the
  stale-card matcher does not treat a null-cid card as stale), so the fix
  was `scoring-round-drop:3526|unpost|apply` → keyed re-import (card 3528,
  cid 821) → `scoring-hcp-import:a9.23|apply` (1 row, index 7.8, recap
  mail to Kerry + Robert for that one row). Which spelling is canonical is
  Kerry's call (his email is guillermoarevalo25@).
- **Lee Vasquez (card 3518) has NO tee or course** — GG served the card
  without a tee row, so par, dots-vs-par and the handicap post are blocked
  (`no_tee_slope_rating`). Not guessed. Registration says <50, which at
  Avery Ranch was Blue (885) for everyone else in that band — Kerry
  confirms, then the card needs a tee stamped (no bridge; skill OPEN 9)
  and one more `scoring-hcp-import:a9.23|apply`.
- **Pairings:** SA TEAM Net board applied (6 groups, 3 blind seats, 21
  rows, 28 pairs). Austin's only team board is **CART Net** (6 pairs of 2)
  — the foursomes are on no GG board, so NOT applied (skill OPEN 10).
- Cards = field both chapters (21, 12); parity all_ok Baker 3498 +
  Youngs 3519; MVP Baker 12 (TGF MVP over Youngs 10), GG agrees both;
  financials verified 100% both; Avery Ranch bill $714.45 alerted 9/15 =
  course_fees exactly; **The Quarry bill ($886.57 expected) has not alerted
  yet**; contests sync enrolled 0; HIO pot $3,384 after Tuesday (Cedar
  Creek's 8 pre-registrations make the tool say 3,392 — OPEN 8; the Insider
  prints the as-of figure since v2.458.2).
- Jeff King (776, Austin first-timer, facebook_lead) had chapter NULL →
  set Austin.
- Recap drafts: `docs/claude/recaps/2026-09-15-s9.23-quarry-a9.23-avery-ranch.md`
  (one per chapter; blanks = fellowship headcounts, tee times, deadlines).

**7:20 AM follow-up (Kerry's three answers).** (1) Lee Vasquez: GG's
results page DID show his tee (Blue 139/36.0) — the auto-sync's card had
lost it; drop 3518 + keyed re-import came back as 3529 WITH the tee,
handicap posted (diff 7.3, index 7.3 unchanged). (2) Austin pairings from
the TEE SHEET with the event id passed: 3 foursomes at 4:57 / 5:06 /
5:15 PM, applied. (3) "Guillermo is correct" — customer 821 renamed
(3 items rows followed); "Guilermo Arevalo" still resolves to 821.

### 3l. a18.5 correction, 2026-09-16 2:30 PM — Luke Youngs 71 → 70

Robert (Austin manager), via Kerry: "there was a scoring error and Luke
shot 70." GG had corrected the card after our 9/12 import (back nine
33 → 32). Dropped card 3479 (unposting hr 15644/15645), keyed re-import
→ card 3530 (70 / 67 net, MVP flag kept), two nines re-posted (front 38
diff 1.8, back 32 diff −3.7; index 0.9 → 0.1). GG boards and all 17
PAID payout rows unchanged (the skins GG paid were already right).
Skill OPEN 12 raised: a post-import GG edit is invisible to the Tracker.

### 3m. Fourth live run — s18.11 CEDAR CREEK (Sat 2026-09-19, SA, 18 holes), run 1:30–2:30 PM CDT

Single-event day (Austin off). Mailbox read #541–#565 first. Field 15 =
15 cards (auto-sync 12:57–1:32 PM), every cid set, no null-cid or
tee-less card. Parity all_ok on Palacios 10793 and Wade 10799. MVP:
Palacios 15 pts on the gross tiebreak over Stich and Wade (all 75 net).
Tee-sheet ingest applied FIRST (skill 1.2): `scoring-pairings:round|sa|
1708030|apply|3310` → 4 groups (3/4/4/4), 15 rows, 21 pairs; the CART
Net board was NOT applied as groups. Financials verified (15 × 90.65 =
1,359.75, coverage 100). Contests sync enrolled 0. Card emails: none
since 9/16 (`scoring-message-log:handicap-card`). Course bill: no
Cedar Creek chase alert yet ($100 Alamo City deposit booked 9/19 per
the earlier split); a $100 expense row dated 9/17 carries event_name
s18.11 under "Luke Mazanec" — noted, not touched.

**Handicaps — asked for twice, posted 5:40 PM.** The 2 PM run read
`no_per_nine_rating` (skipped all 15) as "ask Kerry" and reported it so.
Kerry: "I thought I'd already given you Cedar Creek's breakdown for
tees ratings and indexes. No?" He had: the Tuesday 9-hole tee rows
(`scoring-tee-nines:35670` decides each row's nine) carry them — White
717 = 4433 F 35.5/126 + 2971 B 35.9/123 (= 71.4/125); Gold 711 = 4436
F 34.8/116 + 2973 B 34.6/119 (= 69.4/118); Red (L) 710 = 2441 F
36.4/124 + 2978 B 36.5/116 (= 72.9/120); front/back yardages match the
cards. `scoring-hcp-2nines:s18.11 CEDAR CREEK|{...}|apply` → 30 rounds,
0 skipped, no flags (Palacios 7.7 → 8.2, Straiton 0.6 → 1.1, Wade 7.5
→ 7.3). Now in the ratings-of-record table and skill 3.1c. Card emails
(3.3) and the GG upload (3.4) remain Kerry's.

**The 2 PM money findings were a snapshot, not defects (skill 1.3).**
At 2 PM the walk saw two boards at purse 0.0, no Skins board, and
matrix-fallback rows (12 rows $490; the three-way Ind Net tie split
two ways, Wade missing). Kerry then entered the money and the boards
went up; by 5:30 PM the hourly refresh had re-recorded 18 rows, $622,
all GG-backed: Ind Net T1 $54 ×3, City MVP $72 (Palacios, gross
tiebreak — the tiebreak decides MVP, the purse still splits), Cart Net
$60/$60 + four $15 (T2 Mazanec+Pearson, Palacios+Anthis), Skins Gross
$208 (Schneider 13 and 15 — the shadow read had also given him 18).
All PENDING. No CTP board — Kerry: none was run. Kerry's other read of
my report ("both got $81 for MVP") was my wording: the $81s were the
Ind Net purse, not MVP. Lesson: say which game a dollar belongs to.

Recap draft: `docs/claude/recaps/2026-09-19-s18.11-cedar-creek.md` +
Word file via tools/recap_docx.js (SA only, Kerry's signature). Fall
race standings fetched 2:04 PM still show Tuesday's numbers (Wade on
20 with a tied-1st net) — GG had not posted Saturday's points; monthly
cache 05:30 pre-round. Both flagged as blanks.

### 3n. The course record rebuilt to the USGA/WHS shape (mailbox #576, 2026-09-19 evening → 2026-09-20 00:10 CDT, v2.466.0 → v2.466.2)

Kerry, #576: "the full standard shape in one pass … Migrate existing
rows with source='import' … then correct from CRDB … the rebuild is the
blocker for the 13 staged tees in #569." Done in that order.

- **v2.466.0** — `course_tees` rebuilt IN PLACE on boot (same table,
  same tee_id): gender M|F, holes 9|18, nine, par, bogey_rating,
  is_combo, gg_tee_id, usga_tee_label, source, version columns; natural
  key `(course_id, tee_name, gender, holes, nine, slope, rating)`; new
  `tee_set_ratings(tee_id, rating_type total|front|back, …)`; `courses`
  gains gg_course_id / usga_course_id. The migration ran on the live DB
  at 04:57 UTC — `scoring-per-nine-audit` immediately reported gender
  and `how` per tee, 29 resolved / 85 unresolved, exactly the pre-rebuild
  count (nothing lost, nothing yet corrected). Shape: schema.md.
- **Seeds applied** (`scoring-crdb-seed:22362|apply`, `…:29522|apply`):
  Kissing Tree — 4 existing sets matched by gender + rating/slope
  (Black=Back, Red (KT)=KT, Gold (Legends)=Legends, Green (L)=Forward F),
  10 inserted (tee_ids 14646–14655; three men's combos, six women's
  sets, men's Forward). Forest Creek — Blue/White/Red (L) matched, 4
  inserted (14656–14659: Green M, Red M, White F, Green F). Every set
  now carries total + front + back rating rows with bogey.
- **The 13 staged tees (#569)** → 10 stored as rating rows with
  `scoring-tee-nines-store:<id>|…|apply` (Falconhead 3956/3959/3961,
  Vaaler 2491/2492/2509, Lost Pines 8730/8729/8742/8741); the other
  three of the 13 were Forest Creek's, covered by the seed.
- **Kerry's course cards applied** (`scoring-course-card:<id>|apply`,
  the 2026-09-15 GG course-setup reads): Avery Ranch — five 18-hole sets
  created (Black/Blue/White/Green M, Green (L) F, 14667–14673) with the
  nines the Tuesday rows already had; Cedar Creek — Blue 18 + its front
  nine created, the rest existing; Forest Creek — Gold M created, the
  back nines created, and **Green M adopted the CRDB-seeded row**.
- **v2.466.1** — the gap that adoption fixes: the seed names a set the
  USGA way ("Green"), GG names it "3 - Green Tee"; the exact-name match
  in both GG writers would have inserted a twin with identical numbers.
  `_adopt_crdb_tee_set` claims a CRDB-named 18-hole row of the same
  gender + slope + rating, takes GG's name, keeps the label and tee_id.
  Found on the Forest Creek card's live dry run, one minute after the
  seed. **v2.466.2** — the adoption no longer writes on a dry run.
- **Audit after:** 34 courses, 67 resolved / 68 unresolved. EVERY course
  with an upcoming event resolves every tee: Canyon Springs, ShadowGlen,
  Olympia Hills, The Quarry (paired Tuesday rows), Avery Ranch, Forest
  Creek, Kissing Tree (rating rows). `scoring-hcp-2nines:s18.11 CEDAR
  CREEK` dry run: 30 skipped "already posted", 0 planned — the dedupe
  held through the rebuild; the per-nine source now reads
  `how: paired nine-hole rows` for all four Cedar Creek tees.
- **Still unresolved (68 tees):** 18 courses with no upcoming event
  and no CRDB pull yet (Landa Park, La Cantera, Delaware Springs,
  Crystal Falls, Flying L, The Bandit, Willow Springs, Morris Williams,
  Squaw Valley, Comanche Trace ×2, plus nine archived "(OLD)" GG
  courses), Vaaler White (L) 2514, Falconhead Red (L) 3958, and Cedar
  Creek's three OLDER-rating rows (2198/2189/2190 at 74.2/71.2/73.4 —
  a previous rating version; rounds may point at them). The recipe for
  each is one CRDB pull → `scoring-crdb-seed:<course_id>|<json>|apply`.
- **Not populated yet:** gg_tee_id, gg_course_id, usga_course_id — the
  GG import does not carry its ids today; a follow-up when it does.

### 3o. Tee designation — master name, GG alias, the four sets TGF plays (Kerry 2026-09-20 morning, v2.467.0)

Kerry, after the #576 rebuild: "Master name is what USGA/course call it.
GG should just be an alias. The GG names were purely for Admin, not
necessary for member facing… there's never more than four sets of tees
that we use on a course. The rest can and should be hidden. If we bring
in a New course then there needs to be understanding to identify which
tees we'll choose based on our standard yardage parameters. And as a
default, we do not want to use any combo tees, except as last resort."
Yardage standards, verbatim: <50 6300-6799 · 50-64 5800-6299 · 65+
5300-5799 · Women — shortest tees not less than 4800. "We also have
some 3- for women based on tee availability."

- `course_tees.tee_name` = master; `gg_alias` = GG's name; `tgf_bands` =
  designation. Boot step aliases every GG-style name once (the typed
  number → bands). Writers match alias-or-master; adoption by numbers
  generalised to any unaliased set.
- Standards as data (`tee_yardage_standards`), proposer, setter, apply;
  three bridges. Legend / tee circles / PH read designation first.
- Also fixed on the way: the R1 ×0.96 line in handicap-projection.md was
  stale (applied 2026-08-03) — #578 records it; P2-4 closed.
- NOT done: the Courses admin page still lists every set (right for
  admin); no member-facing tee PICKER exists yet (orders carry the band,
  not a tee), so nothing member-facing needed a filter today. The CRDB
  seed tuples carry no yardage, so a CRDB-only course cannot be proposed
  until its yardages arrive (a course card or the CRDB pull's yardage
  column — add it to the seed shape when the next course comes in).

### 3p. The yardages we have (Kerry 2026-09-21, v2.468.0 / v2.468.1)

Kerry: "Seems like you need to incorporate the yardages we have. Show
me the updated schema." Yardage is the physical tee's, not the rating's:
`_heal_tee_yardages` (boot + after card / store / seed) fills a set from
its holes, then from its other-gender twin of the same master name, and
gives every rating row its own yardage (`tee_set_ratings.yardage`, total
/ front / back). The CRDB seed shape takes an optional `[y18, yf, yb]`.
Live: every imported / carded set already had yardage; 7 of 13 CRDB-only
sets filled from their twin; the 6 Kissing Tree combos wait for the
CRDB numbers (Kerry's pull). Schema block rewritten in schema.md.
Advisory finding: Forest Creek's women's Green (5542) now satisfies the
4800 floor, so the standard proposes Green F for Forward over Red F
(4780); designation unchanged. Blocked from the sandbox: ncrdb.usga.org
is not reachable (network policy), so a CRDB reader would have to run on
Railway behind a widened SSRF allow-list — Kerry's call.

## 4. NOT done, and why

- **Wednesday-AM TGF Insider auto-draft (mailbox #453).** BUILT in
  v2.369.0 — see §3i. What is NOT done: the first REAL Brevo draft. Per
  the spec the dry run for s9.22/a9.22 goes to Kerry first; `apply` runs
  only when he says. Still open: does an Insider #2 go out by hand this
  week?

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
