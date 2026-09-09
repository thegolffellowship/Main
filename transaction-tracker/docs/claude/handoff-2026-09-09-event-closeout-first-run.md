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

## 4. NOT done, and why

1. **Handicap cards were not emailed to the players who played (Phase
   3.3).** The only path is `/api/handicaps/send-bulk-email` behind the
   manager login — the Handicaps page, Email Handicap Cards, **By
   Event**. No bridge command exists and building one is a member-facing
   send path outside the login (rule 3b) — OPEN 6. Handicaps ARE posted,
   so the cards Kerry sends will carry Tuesday's index.
2. **No payout was marked paid.** 31 rows PENDING across both events
   ($806.00). Paying is Kerry's Venmo; the receipt matcher closes them.
3. **No recap was sent.** Two drafts exist. Who sends is OPEN 2; Austin's
   draft also has two blanks (venue, September points).
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

## 6. Kerry still owes (asked again here, not for the first time)

- The **San Antonio `lead_notify_recipients`** address. The dial holds
  only Austin (`robert@thegolffellowship.com`); SA is 67% of lead volume.
- **Austin's fellowship meeting spot.** The template blank guard will
  refuse the send until it is filled; the Austin recap draft carries the
  same blank.

## 7. OPEN for Kerry — from the skill, verbatim

1. Timing — deadline on handicaps vs recap?
2. Who sends the recap?
3. Photos in the recap?
4. Fellowship attendance — record it, and where?
5. The self-filling per-event checklist — Tracker or Platform?
6. A bridge for the By-Event handicap-card send (new this run).
7. Shadow-computed payouts with no GG board — record or hold (new).
8. HIO pot pre-counting future registrations (new).
