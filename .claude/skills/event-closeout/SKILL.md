---
name: event-closeout
description: The post-event routine for a TGF event (Tuesday nine, Saturday 18, championship) — scorecards in, the FINAL Golf Genius pairings ingested, payouts verified and PAID, handicap differentials posted, handicap cards emailed to the players who played, contests synced, financial summary, recap. Phases are dependency-ordered. Invoke when Kerry says "close out", "closeout", or names an event that has been played and asks what is left to do for it.
---

# Event closeout

Every step below already has a tool. What did not exist until 2026-09-09
was the SEQUENCE. The proof it was needed: the final GG pairings for three
August rounds had never been ingested (135 pairs), and nothing anywhere
said a step had been skipped.

This file was first written on 2026-09-08 and LOST — `.claude/` was
gitignored, so it never reached the repo. Rewritten 2026-09-09 from the
first live run (s9.22 Silverhorn, a9.22 ShadowGlen). `.gitignore` now
tracks `.claude/skills/`.

**Rule 3d applies.** An instruction to close out applies to every chapter
that played that day unless Kerry names one. Report per chapter.

**Say what you did NOT do**, and why. Kerry reads the gaps.

## How commands are run

Bridge commands run through the MCP tool `probe_golf_genius` with
`url` = the chapter's live portal and `extract` = the command string:

| Chapter | url | tournament_results widget (for import / mvp / games walks) |
|---|---|---|
| San Antonio | `https://tgf-sa.golfgenius.com` | `https://tgf-sa.golfgenius.com/leagues/514047/widgets/tournament_results?shared=false` |
| Austin | `https://tgf-austin.golfgenius.com` | `https://tgf-austin.golfgenius.com/leagues/514705/widgets/tournament_results?shared=false` |

`<event>` below is the events.item_name (e.g. `s9.22 Silverhorn`), NOT the
events.id. **`scoring-rounds:<event>` and `get_scoring_rounds(event=)`
filter by NAME SUBSTRING** — passing an id like `3306` returns `[]` and
reads as "no scorecards" when there are 24. That is how the 2026-09-08
closeout was mis-read as "nothing has happened" before this first run.

## Phase 0 — what the machine already did

The hourly auto-sync (`_GG_RESULT_PORTALS`, database.py) runs on any day
an event happened today or yesterday: scorecards (ALL Net → ALL Gross) for
the newest rounds, GG-recorded winners + flights, and a payout refresh
that auto-records rows (descriptions start `auto:`). Expect Phase 1.1,
1.3 and the payout RECORDING to be done within an hour of GG finalizing.
Do not assume it — read it — but do not redo it either.

## Phase 1 — data in (gates everything downstream)

1.1 **Scorecards.** `get_scoring_rounds(event=<event>)` → one row per
    player who played. Compare the count against active registrations
    (`get_event_registrations`). Missing? `scoring-import-event:<code>@<gg_round_id>`
    with url = the widget (round ids from `scoring-pairings:teamrounds|<sa|austin>`).
    A card imported mid-round self-heals on re-import.

    **Identity check here, before anything writes:** any row with
    `customer_id: null` is a name GG spells differently from the
    customers row (`scoring-resolve:<GG name>` shows why — e.g.
    "Donovan, Tom" vs customers "Thomas Donovan"). Fix with
    `scoring-alias-add:<canonical name>|<GG-style name>`, then re-pull the
    card: `scoring-import-event:<code>@<round_id>|refresh=<surname>`.
    Never post handicaps or pairings for a null-cid row (CLAUDE.md rule 6).
    **Which spelling is canonical is Kerry's call** (2026-09-09: "Tom
    Donovan" is the member's name, "Thomas Donovan" the alias) — ask
    before renaming a customers row; the rename itself is
    `scoring-customer-set:<cid>|first_name|<value>` (safe for one field
    at a time since v2.348.0).

1.2 **The final GG pairings — the forgotten step.**
    `scoring-pairings:team|<portal>|<round_id>` (dry run) → check
    `applied`, `blind_seats`, `unresolved_names: []`. Then `…|apply`.
    GG is the only source of pairing history; app rows are plans. Blind
    draw seats never count. Both rounds of a multi-day event are applied
    separately on the same event.

1.3 **GG winners + MVP cross-check.** `scoring-gg-results:<event>` — the
    boards GG has posted, with purses. Rows with `purse: 0.0` mean Kerry
    has not entered money on GG yet; the payout layer then falls back to
    the matrix. A game with NO board at all (no CTP row, no Skins row)
    means GG has nothing for it — the tracker may still have
    SHADOW-computed it (payout descriptions without "(GG $)"). Say which
    is which. `scoring-mvp-import` with url = `<widget>&round=<round_id>`
    pulls GG's recorded MVP; `determine_tgf_mvp(<event>)` then shows
    `gg_recorded_mvp` beside our determination. Ours is authoritative
    post-2026-07-14; a mismatch is a finding, not a fix.

## Phase 2 — verify before anything leaves the building

2.1 **Parity.** `verify_scoring_round_tool` on the MVP's card and one
    other: `all_ok: true`. Any discrepancy already filed a COO action item.
2.2 **Payouts recorded AND paid.** `scoring-payouts-inspect:<event>` —
    every row's `state`. `PENDING` = recorded, not paid. Paying is Kerry
    (Venmo); the receipt matcher flips the state when the receipt lands.
    Report the pending total per chapter. Never mark paid from here.
2.3 **Roster truth.** Registrations vs cards: no-shows (registered, no
    card), WDs, `credit_amount`, balance-due rows. A WD still in the saved
    pairings: `scoring-pairings-remove:<event>|<player>`.
2.4 **HIO pot.** `scoring-hio-pot` — the event's line is present, players
    = field size. Known quirk: the tool also counts registrations for
    FUTURE events (a18.5 Forest Creek showed on 2026-09-09 with 9), so
    "pot as of tonight" = the running total at the last PLAYED event.

## Phase 3 — handicaps (preview, post, then email — in that order)

3.1 `scoring-hcp-preview:<event>` — read-only. Every row
    `already_imported: false`, `flags: []`, and no absurd index move (a
    wrong tee or course import shows here as a multi-point jump). New
    players show `index_now: null`.
3.2 `scoring-hcp-import:<event>|apply` — writes one handicap round per
    9-hole card (WHS NDB adjusted gross, Kerry-ratified 2026-07-14) and
    auto-emails the chapter recap to `hcp_recap_email_<chapter>` →
    `hcp_recap_email_default` (Kerry + Robert Straiton as of 2026-09-09).
    The preview's footnote saying the standard "needs Kerry's ruling" is
    stale; the ruling is D1 / NDB in `docs/claude/handicaps.md`.
3.3 **Email the players who played their updated card.** Handicaps page →
    Email Handicap Cards → **By Event** (route
    `/api/handicaps/send-bulk-email`, manager login). There is NO bridge
    command for it as of 2026-09-09, so it cannot be run from an MCP
    session — see OPEN 6. Reversing 3.2 and 3.3 mails yesterday's index.

## Phase 4 — money and standings

4.1 `get_event_financial_summary(<event>)` — `accounting_verified: true`,
    `allocation_coverage_pct: 100`, course_fees = field × course_cost.
    Margin questions go through the `tgf-margin` skill.
4.2 **Course bill booked ONCE.** `get_expense_transactions` for the event
    date: one chase_alert per course, amount = course_fees. Two = the
    #428 duplicate-expense class; say so. (Course bills carry no
    event_name today — that is the existing pattern for every course
    charge on record, not a defect to patch mid-closeout.)
4.3 `sync_season_contests()` — idempotent; `enrolled: 0` when nothing new
    was bought.

## Phase 5 — the story

5.1 **Recap draft** in the house style (`docs/claude/event-recaps.md`,
    read it first). Sources: `scoring-gg-results` (winners + GG purses),
    `get_scoring_rounds` (Gross / Net (± to par); par from
    `get_scorecard_detail`), `determine_tgf_mvp`, the fall race at
    `/api/season-contests/points-race?race=<san_antonio|austin>_fall_net`
    (public GET; use ENROLLED rows only for race framing), the monthly
    race at `/api/season-contests/monthly-points` (a daily cache — check
    `rounds` includes last night before printing), `scoring-hio-pot`,
    `list_events` for the next dates. "% cashed" = distinct payout
    recipients ÷ field, from GG-backed rows only. Results link:
    `<portal>/pages/<results page>?round_id=<gg league round id>`.
    Store links for the "up next" events come from
    `events.registration_url` (derived + verified nightly since
    v2.357.0; `scoring-event-links` shows the state) — do not hand-build
    a slug when the row already carries a verified URL.
    Save the draft under `transaction-tracker/docs/claude/recaps/`.
    Kerry sends — OPEN 2.
    **Draft-time inputs the s9.22 send taught (event-recaps.md 20–29):**
    the headliner's PREVIOUS event (card + payout) for a trend; the Team
    Net team score; `customers.acquisition_source` for every first-timer;
    a first-timer is anyone on their first TGF round, membership or not
    (surname CAPS + "New Member!" when they also joined); both chapters'
    next three events, chronological, with tee time / shotgun, nine side
    and registration deadline; links for every proper noun that has a
    page; and no line a named member could read as a dig.
5.2 **First-timer follow-up** while the round is fresh — list them
    (`user_status` = `1st TIMER`) with what they did. There is no
    first-timer system template on the shelf as of 2026-09-09; the send
    is Kerry's or the chapter manager's.
5.3 **Fellowship attendance** — the recap reports who CAME, which only
    Kerry knows (13 said yes at Silverhorn, 9 came). Ask him for the
    number; OPEN 4 is where it should live.

## Report shape

Per chapter: field, cards, pairs written, handicap rounds posted (and the
recap email recipients), GG boards present / missing, payouts pending $,
financial summary line, first-timers, then **NOT DONE** with the reason.
Then the OPEN items, verbatim, for Kerry to rule on.

## OPEN — Kerry has not ruled on these. Raise them; do not guess.

1. **Timing.** Handicaps want same-night so the next event's strokes are
   right; a recap may read better with a day's distance. Deadline on each?
2. **Who sends the recap** — Kerry, the chapter manager, or automated to
   the GG roster once the style is proven?
3. **Photos.** No image path in the recap today.
4. **Fellowship attendance** — worth recording, and where? We ask members
   for a headcount; not using it trains them to ignore the ask.
5. **The version that cannot be skipped.** Every state above is
   computable (cards in, pairings ingested, handicaps posted, payouts
   paid, contests synced) and could render as a per-event checklist that
   fills itself in. Tracker or Platform? Rule 3b: Kerry's call.

Raised 2026-09-09, on the first run:

6. **A bridge for 3.3** (`/api/handicaps/send-bulk-email`, By Event) so
   the whole routine can run from an MCP session. It is a member-facing
   send path that would sit outside the manager login — Kerry's call.
7. **Shadow-computed payouts with no GG board.** Austin a9.22 had no GG
   Skins or CTP board; the tracker recorded Skins from the cards anyway
   ($117.00 across four players, all PENDING). Record shadow games before
   GG posts, or hold them?
8. **HIO pot pre-counting future events** (2.4). Cosmetic today; wrong the
   day a registration is refunded before the event.
