> **Repo copy of the session context file.** OneDrive / Project Files name:
> `TGF_Tracker_EventCreator_Context_v1_1.md` (OneDrive → `7_Web & App Development\`).
> Companion: `session-prompt-2026-08-07-event-specific.md`.

# TGF TRACKER — EVENT-SPECIFIC ENTRY & REFUND CONTEXT
**Version:** 1.1
**Created:** 2026-08-07
**Status:** In Progress — display work SHIPPED; entry + refund are the carry-forward
**Repo:** thegolffellowship/Main → `transaction-tracker/`
**Branch:** `claude/tgf-tracker-champ-points-g62t9l` (in sync with `main`)
**Deadline pressure:** 2026 TGF CHAMPIONSHIP plays 2026-08-15/16 (practice round Fri 08-14)

---

## SITUATION SUMMARY

The championship is the first TGF event sold as **day combinations** (14 packages: one day
/ both days / practice round, with and without the $100 side-games bundle, member and
guest). The Tracker was built around single-day events, so three surfaces assume one round
per registration: the roster's Holes column, the Add Player modal, and the Credit/Partial
Refund modal. This session fixed the **display** side. The **entry** and **refund** sides
are still single-day-shaped and are the carry-forward work.

CA cordoned off the Event Creator until after the championship. Kerry (2026-08-07): *"I see
more and more need to get this going… I had also told CA that I may come back to the Event
Creator thing if I had more time before the event."* Treat Event Creator as **re-opened for
scoping**, still pending CA/Kerry agreement on sequence.

---

## CONFIRMED DATA / DECISIONS — DO NOT RE-DERIVE

### Championship event
- **Event id `3291`**, item_name `2026 TGF CHAMPIONSHIP` (older rows carry `TGF CHAMPIONSHIP`
  — alias-resolved), chapter Austin, course Lost Pines, `format` is 18-hole style.
- Roster at time of writing: **24 active players**, hole split **18 (2) | 36 (16) | 54 (6)**.

### The 14 live packages (`event_package_configs` → key `"3291"`), Kerry-entered
| Package | Price | Holes |
|---|---:|---:|
| Both Days – Member | 320 | 36 |
| Both Days – Guest | 340 | 36 |
| Both Days + Side Games – Member | 420 | 36 |
| Both Days + Side Games – Guest | 440 | 36 |
| Both Days + Practice – Member | 425 | 54 |
| Both Days + Practice – Guest | **460** | 54 |
| Full Weekend (Both Days + Practice + Games) – Member | 525 | 54 |
| Full Weekend (Both Days + Practice + Games) – Guest | **560** | 54 |
| One Day – Member | 170 | 18 |
| One Day – Guest | 190 | 18 |
| One Day + Side Games – Member | 200 | 18 |
| One Day + Side Games – Guest | 220 | 18 |
| Practice Round Only – Member | 105 | 18 |
| Practice Round Only – Guest | 120 | 18 |

Guest practice-round pricing was corrected 2026-08-07 (see the resolved question below):
`Both Days + Practice – Guest` 450 → **460**, `Full Weekend – Guest` 550 → **560**. Verified
live in `event_package_configs`.

Pinned assignments in the config: **2488**, **2512**, **2331** → index 2 (*Both Days + Side
Games – Member*) — Rob Callaway, Luke Mazanec (credit-transfer rows) and Robert Straiton
(comp).

### Ratified side-games bundle (mailbox #276 item A/B, approved #279)
`$100 = $30 SAT / $30 SUN / $40 COMBINED`, $0 taxable, pure pot pass-through.
Single-day bundle `$30` (that day's games only). Pots are FIELD-BASED, purses DERIVED at
record time so late adds self-correct.

### Hole counts are DISPLAY-derived, not stored
`items.holes` still says `18` for nearly every championship row (one round is one round).
The roster derives what it shows from the matched package. `items.holes` is only the
fallback. **Do not backfill `items.holes` from packages** — that was considered and
rejected; the boot heal owns that column.

### Boot-heal exemption (already deployed)
`heal_item_holes_from_event()` forces `items.holes` to the event's per-day count on every
non-combo event at startup, and `_event_holes_type()` can only return 9 or 18 — so it would
have reset every 36/54 on the next deploy. `_is_multi_day_holes()` now exempts 36/54, but
**only on 18-style events** (on a 9-hole event a `36` IS the sequence-number misread the
heal exists to fix, e.g. `a9.36 Forest Creek`). Same exemption at insert via
`_canon_holes_for_item(conn, item_name, current)`.

---

## WORK COMPLETED THIS SESSION

Shipped to `main`, deployed, and verified live (v2.208.0 confirmed serving):

| Version | What |
|---|---|
| v2.206.0 | Event-specific hole tabs — the fixed `9\|18` pair replaced by one tab per hole count the roster actually holds, with counts. 36/54 added to Add Player, numeric Holes sort, HCP 18-only rule counts 36/54, boot-heal exemption. Package-save wipe guard. |
| v2.207.0 | Holes column reads the matched PACKAGE, not the order. Per-package Holes selector (Auto/9/18/36/54) in the Event Creator. |
| v2.207.1 | Two bug fixes Kerry caught: Holes sort was a no-op (compared `items.holes` = 18 for all → every pair tied); hole tabs were showing RSVPs (GG RSVP rows appended AFTER the filter, gated only on NET/GROSS/NONE). |
| v2.207.2 | Label rule counts ROUNDS, not phrases — `Both Days + Practice` was resolving 36; a practice round is another 18, so it is 54. |
| v2.208.0 | **MCP write guardrail** (Kerry-ratified) — every write audited, six destructive tools two-step. |
| v2.208.1 | A COMP row can be assigned a package (the picker only rendered for price-matched or credit rows, so a $0 comp got no control at all), and a comp is never shown a balance-due badge. |

### Data fix applied
- **Robert Straiton item 2331** — comp entry, `holes` `18` → **`36`** (he is a both-days
  player; Add Player defaulted him to 18). Recorded in `agent_action_log` id 140 — the
  first entry the log has ever received from an agent write.

### Straiton package badge — DONE
Kerry pinned item **2331** to index 2 (*Both Days + Side Games - Member*) through the roster
dropdown that v2.208.1 added. Verified in `event_package_configs.assignments`. He now reads
36 holes with the package badge and no balance-due badge (comp suppression).

**Still worth building:** there is no `assign_event_package` MCP tool, so an agent cannot pin
a package programmatically. Do NOT reach for the `scoring-setting-set` bridge as a substitute
— it was tried, silently no-op'd (`{"key":"","value":"","saved":true}`), and a malformed write
there would wipe 14 Kerry-entered prices.

### Environment
- Cloud environment **"The Golf Fellowship"**: Network access **Custom**, allowed domain
  `*.up.railway.app`, *"Also include default list of common package managers"* CHECKED.
  Applies to NEW sessions only.

---

## CURRENT STATUS BY COMPONENT

| Component | Status |
|---|---|
| Roster Holes column (18/36/54) | ✅ Live, package-derived |
| Event-specific hole tabs + counts | ✅ Live, desktop + mobile |
| Holes sort / hole-tab RSVP exclusion | ✅ Live |
| Package Holes selector (Event Creator) | ✅ Live (Auto reads the label) |
| Package-config wipe guard | ✅ Live |
| MCP audit + confirm guardrail | ✅ Live |
| Comp rows assignable to a package | ✅ Live (v2.208.1) |
| Guest practice pricing ($120 everywhere) | ✅ Corrected, tracker + website |
| **Add Player — event-specific options** | ❌ Not started (carry-forward #1) |
| **Credit/Partial Refund — event components** | ❌ Not started (carry-forward #2) |
| Event Creator (broader) | ⏸ Re-opened for scoping, CA sequence TBD |

---

## CARRY-FORWARD #1 — Add Player needs event-specific options

**The failure it caused:** Kerry comped Robert Straiton in. The modal's Holes dropdown
defaulted to a flat list, nothing on it said "both days", and he landed as 18 holes on a
36-hole entry. Kerry had to spot it on the roster days later.

**What exists now:** `#add-player-holes` is a static `9 / 18 / 36 (two days) / 54 (three
days)` select (added this session), plus static Side Games / Tee / Status selects. Route
`POST /api/events/add-player` (app.py ~7169) passes `holes` straight through with **no
validation** — 36/54 save fine.

**What it should do:** on an event that has packages, offer a **Package** dropdown as the
primary control. Picking one sets holes, side_games and price together, so a comp both-days
entry cannot land as 18. Falls back to today's manual fields on events with no packages.

**Already tracked as task #34** — "Add Player package dropdown on package-config events
(#284 feedback)". This session's Straiton case is the second real-world instance.

---

## CARRY-FORWARD #2 — Credit/Partial Refund needs event-specific components

**The trigger:** Jeff Young (**item 2507**, `$525.00`, Full Weekend) can no longer play the
Friday practice round. Kerry needs to refund just that day.

**What exists now** (`app.py` ~7025-7040): `refunded_components` is a free dict keyed to
hardcoded standard-event notions (e.g. `{"gross_games": 30}`), plus `new_side_games` and
`new_holes` for the 9/18 Combo "Event Downgrade" case.

**Two concrete blockers found this session:**
1. **`new_holes` is validated to `("9", "18")` only** (app.py:7032). A day-drop needs to
   write 36 or 54 and will be rejected as-is. This validator must widen before any
   per-day refund can land the new hole count.
2. **Side games on this event is a $100 bundle**, not the standard per-game amounts. The
   refund modal's component list has to come from the EVENT, not from a hardcoded set.

**Jeff Young's numbers, already derived — do not re-derive:**
- Full Weekend – Member `$525` − Both Days + Side Games – Member `$420` = **$105 refund**
- `$105` is exactly *Practice Round Only – Member*, so the member ladder is self-consistent
- His package moves Full Weekend → Both Days + Side Games, and his displayed holes **54 → 36**
- The side-games bundle is UNAFFECTED (he keeps Sat/Sun games) — this is a pure day drop

**✅ RESOLVED 2026-08-07 — guest practice round is $120 everywhere.**

The guest ladder had priced practice at `$110` inside bundles but `$120` standalone, while the
member ladder was consistent at `$105`. TGF's rule (Guest = Member + `$15` on an 18-hole
standalone) makes `$120` correct, so the two bundles were raised:

| Package | Was | Now |
|---|---:|---:|
| Both Days + Practice – Guest | 450 | **460** |
| Full Weekend (Both Days + Practice + Games) – Guest | 550 | **560** |

Checks: `340 + 120 = 460` · `440 + 120 = 560` · `460 + 100 (games bundle) = 560`. Updated on
the website AND in the tracker packages; both verified. No guest had purchased at the old
prices, so nothing was stranded.

**⚠ STILL OPEN — the website OPTION LABEL is stale.** The store variants still read
*"ALL 3 DAYS (Fri Practice + Sat/Sun Champ) = **$450**"* while charging $460/$560. A guest
reading the label does `450 + 100` and expects `$550`, then gets billed `$560`. Update the
option text to `= $460`.

---

## CARRY-FORWARD #3 — Event-specific GAME options (NEW, Kerry 2026-08-07)

**Kerry, verbatim:** *"GAMES options for this event should be: YES (for both days), SAT (For
Saturday Only), SUN (For Sunday Only), NO. So GAMES tabs NET | GROSS | NONE should show
YES | SAT | SUN | NO."*

**Why the current model can't express it.** `items.side_games` holds `NET` / `GROSS` /
`BOTH` / `NONE`, and that vocabulary is wired through `classifyGameType()`,
`getEffectiveGameType()`, `computeGameStats()`, the roster's NET/GROSS/NONE tabs, the
click-to-cycle Games cell, and the prize-matrix pot sizing. On the championship a player
does not buy net-or-gross — he buys **days**: the ratified `$100` bundle is
`$30 SAT / $30 SUN / $40 COMBINED`, and a single-day buyer pays `$30` for that day's games.

**This is the same shape as the hole-tab problem, and the hole tabs are the precedent:**
derive the tab set (and the cell's allowed values) from the EVENT rather than from a
global enum. `holesBuckets()` / `holesTabsHtml()` in `events.html` are the working model.

**Mapping Kerry gave:**
| Option | Means | Bundle |
|---|---|---:|
| `YES` | both days | $100 |
| `SAT` | Saturday only | $30 |
| `SUN` | Sunday only | $30 |
| `NO`  | no games | $0 |

**Existing workaround this would retire:** the `champ_single_day_assignments` app-settings
dial (`"Name=SAT,Name=SUN"`) exists *precisely because* per-event game vocabulary doesn't.
`_champ_roster_bundles()` in `database.py` reads it to classify single-day bundle carriers.
Building #3 properly should retire that dial.

**Scope warning:** this is materially bigger than #1 and #2 — it touches the money path
(pot sizing, `_champ_roster_bundles`, payouts), not just display. Treat it as Event Creator
work, scope with CA, and do NOT half-ship it before 08-15. The hole-tab work was safe to
ship mid-week because it was display-only; this is not.

---

## ITEMS STILL NEEDED / OPEN QUESTIONS

- [x] ~~Website option label `= $450`~~ **FIXED by Kerry 2026-08-07** ("Fixed the GoDaddy
      product online for any future purchases").
- [ ] **⚠ The `tgf-pricing` skill file is CORRUPTED** — dollar figures in its tables have been
      replaced by stray words ("round,", "an", "vs", "Guest", "championship", "price").
      e.g. New Member reads `$44 | round, | $50` where the middle cell should be `$6`. This is
      the reference Kerry files Texas sales tax from. Repair against
      `TGF_Pricing___Services_Master_Document_v2_0.md`. **Handed to CA 2026-08-07 (Kerry:
      "Pass the skill thing onto CA so that we can address over there and pass back to you")**
      — mailbox post to CA/platform-claude; awaiting the repaired file back.
- [ ] Confirm whether a day-drop should also adjust the side-games bundle when the dropped
      day carried games (Jeff Young's does not — practice has no games — but One Day + Side
      Games dropping its only day would). The shipped package-downgrade refund (v2.210.0)
      deliberately NEVER touches side games pending this ruling.
- [ ] CA alignment on re-opening Event Creator ahead of the championship vs after.
- [ ] Should Add Player write `items.holes` from the chosen package, or stay display-derived
      like the roster? (v2.209.0 does BOTH: writes `items.holes` AND pins the package.)
- [x] ~~Does per-event GAME vocabulary (#3) replace `side_games` or map onto it?~~
      **RULED by Kerry 2026-08-07: YES/SAT/SUN/NO REPLACES NET|GROSS|NONE, but ONLY for the
      TGF Championship** — a per-event vocabulary, because the championship's games are
      structured differently (Daily: Team $8 / Skins $18 / CTPs ×4 $4 = $30; Combined:
      Ind Net $20 / Ind Gross $20 = $40). Full breakdown recorded in
      `docs/claude/side-games.md`. Build remains carry-forward #3 — scope with CA, after 08-15.

---

## KEY DECISIONS & NOTES

- **Never guess a package price.** Package prices are Kerry-entered through the UI and that
  entry IS the rule-3b ratification (docs/claude/events.md).
- **`pkgHolesFromLabel()` counts ROUNDS**, longest-claim-first: `full weekend`/`all three`/
  `three day` short-circuit to 54 BEFORE the count (they contain "Both Days"); then
  `both days` = 2, `one day` = 1, and `practice` adds one. Any new package label must be
  checked against this, or given an explicit Holes value on its editor row.
- **An RSVP has no hole count.** `rowHoles()` returns `""` for `rsvp_only`/`gg_rsvp`/
  synthetic `gg-rsvp-*` before consulting packages, and the GG RSVP append is gated on
  `!holesFilter`. Both were bugs this session; don't reintroduce either.
- **MCP guardrail shape** — any NEW destructive MCP tool must follow it: `confirm: bool =
  False`, return `_confirm_gate(...)` preview until `confirm=True`, and call `_audit()`.
  The six gated today: `delete_transaction`, `delete_existing_event`, `credit_transaction`,
  `transfer_transaction`, `undo_credit_or_transfer`, `run_autofix`.
- **Push both refs.** Railway deploys `main`; the stop hook checks the feature branch. Push
  `HEAD:main` AND the branch, or one of the two silently lags (happened this session).
- **The MCP server flaps.** It dropped and reconnected several times in one session. The
  `*.up.railway.app` allowlist is the redundant path — use it when MCP is down.

---

## DOCUMENTS / FILES IN HAND

| File | Where |
|---|---|
| `docs/claude/events.md` | Updated this session — hole derivation, package `holes` field, RSVP rule, wipe guard |
| `CLAUDE.md` | Updated this session — MCP write-guardrail section |
| `static/js/version.js` | v2.208.0, full changelog entries for 2.206.0 → 2.208.0 |
| `templates/events.html` | `rowHoles` / `pkgHolesFor` / `pkgHolesFromLabel` / `holesBuckets` / `holesTabsHtml` |
| `mcp_server.py` | `_audit` / `_confirm_gate` / `_item_summary` + the six gated tools |
| `email_parser/database.py` | `_is_multi_day_holes`, `_PACKAGE_HOLES_CHOICES`, package `holes` persistence |

---

## NEXT SESSION GOALS

1. **Clarify the GAMES axis with Kerry** (carry-forward #3) — is YES/SAT/SUN/NO a replacement
   for NET/GROSS/NONE, or a second day-shaped axis alongside it? Design nothing until answered.
2. Build **Add Player package dropdown** on package-config events (task #34) — sets holes,
   side_games and price from one choice.
3. Build **event-specific Credit/Partial Refund components** — per-day refund driven by the
   event's package ladder, starting with Jeff Young dropping Friday ($105, 54 → 36).
4. Widen the `new_holes` validator (app.py:7032) beyond `("9","18")` as part of #3.
5. Scope Event Creator re-opening with CA — what lands before 08-15 vs after. Recommend
   #1 and #2 before the championship (contained), #3 after (money path).

---
*Created 2026-08-07 | v1.1 same day — guest pricing resolved, Straiton pinned*
*Source: Claude Code session on thegolffellowship/Main*
