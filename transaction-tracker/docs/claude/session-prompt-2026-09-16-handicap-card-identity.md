# Spin-off contract — handicap surfaces: identity, and the plus rule

Written by tracker-claude 2026-09-15 ~9:15 PM Central as the parent
"TGF Tracker Improvements" session closed out. This file IS the new
session's opening prompt; it is also the record if the session is
started by hand later.

---

SPIN-OFF from "TGF Tracker Improvements" — 2026-09-15. Kerry, on being
told the handicap-card event filter matches players by name string:
**"It's not 1am. It's 9:00pm. What's the bug? We need to fix it"**, then
**"let's spin off a new session."**

**GOAL — two items, in order.**

**(1) Identity.** The handicap-card path resolves every player by
`customer_id` — never by a name string — so no registrant can be
silently dropped from a send, and every registrant lands in exactly one
reported bucket. Done = the Quarry and Avery Ranch sends reconcile with
`unaccounted = 0` for a reason, not by luck, and the same holds for any
event with a name variant in it.

**(2) The plus rule, carried to the surfaces that still get it wrong.**
A plus handicap comes off the ROUND, never off a hole — ratified by
Kerry 2026-09-15 and shipped that night on two call sites out of
eleven. The scorecard on `/handicaps` and the Players Cup card still add
a plus stroke hole by hole. Done = the rule lives in the MECHANISM, not
in each caller.

## READ FIRST, BEFORE ANY REPLY

1. Tracker mailbox: `read_platform_dialogue` since_id=**522**. Posts
   **#522** and **#523** are this lane's parents. Re-read before every
   response to Kerry (CLAUDE.md rule 4).
2. `transaction-tracker/CLAUDE.md` — rules 3b / 3c / 3d / 4 govern you.
   **Guiding principle 6** (`customer_id` is the one true identity key)
   is the whole subject of this lane. Also read the **"Identity drift
   watch"** section and **"Pairings roster: ONE builder (v2.410.0)"**.
3. `docs/claude/handoff-2026-09-15-event-night-leaderboard.md` — §10
   states the bug; §9 states which sends went out wrong.
4. `docs/claude/handicaps.md` and `docs/claude/customers.md`.
5. Confirm your tools: the TGF Tracker MCP (`probe_golf_genius` with
   `scoring-*` bridges, `read_platform_dialogue`). A freshly created
   session can start WITHOUT connectors — if any is missing, say so
   before building anything.

## RULINGS ALREADY MADE (verbatim — do not reopen)

- **Kerry, 2026-09-16:** *"Not sure how we have 21 registered and only
  16 sent and 3 skipped. Seems to be 2 unaccounted for."* → every
  registrant must land in exactly one bucket, and anyone skipped must be
  NAMED. Shipped in v2.456.0; this lane makes the classification
  correct, not just complete.
- **Kerry, 2026-09-15:** *"What's the bug? We need to fix it."*
- **Kerry, 2026-09-15 (the plus rule, ratified):** *"for plus
  handicappers like Pat Youngs there's something that Golf Genius can't
  do. For MVP nobody is allowed to have to add strokes on any given
  hole, so there should be no pluses on any holes. But his +3 PH still
  stands. The way it works on our side is that his total points gets
  deducted that 3 strokes. It's not fair to make a player have to
  perform on any one hole, but it should be applied across a round."*
- **Kerry, 2026-09-15 ~9:15 PM, on Pat Youngs' Quarry Front card:** *"We
  just determined this isn't how we do Net Points with pluses on
  holes."* — the rule above is already ratified; this is carrying it,
  not reopening it.
- **Kerry, 2026-08-01:** *"In general if I say to do something I want
  you to do it across the board, all chapters, unless I specifically say
  one or the other."*
- CLAUDE.md principle 6: *"when checking whether 'Stuart Kirksey' and
  'Stu Kirksey' are the same person, join through `customer_id` — never
  compare name strings."*

## THE BUG, PRECISELY

### Layer 1 — `app.py` `api_handicap_send_bulk_email` (~line 9670)

The `event_name` filter is built from three name-string structures and
one string equality:

- `event_customers` — a set of `items.customer` lowercased. `items.
  customer` is a **per-order historical snapshot** (CLAUDE.md "Identity
  drift watch"), not identity.
- `player_to_customer` — `SELECT player_name, customer_name FROM
  handicap_player_links WHERE customer_name IS NOT NULL`, mapping one
  name string to another. **The `IS NOT NULL` filter silently drops any
  link that has a `customer_id` but no `customer_name`.**
- The match: `player_to_customer.get(r["player_name"], "").strip()
  .lower() in event_customers`.

Consequences: "Mike Murphy" on the order vs "Michael Murphy" on the
handicap link ⇒ the player is classified **"no TGF handicap on record"**
and gets no card, even though his index is current. A name
proper-cased, married, or corrected after the order does the same.

The same route also re-derives its own roster from `get_all_items()` +
`get_all_event_aliases()` instead of calling **`_event_roster_rows(conn,
event_id)`**, the ONE builder mandated in v2.410.0 — so a Golf Genius
RSVP with no order row is invisible to it and is not even counted in
`registered`.

The `members_only` branch has the same defect: it builds `member_names`
with `c.first_name || ' ' || c.last_name = l.customer_name` and then
matches `r["player_name"]` against that name set.

### Layer 2 — `database.py` `get_handicap_export_data` (~line 36793)

This is the bigger half, and it feeds the **Golf Genius CSV export** as
well as the card send. Its links query is
`FROM handicap_player_links l WHERE l.customer_name IS NOT NULL`, and it
reaches chapter / first_name / last_name / suffix through
`LOWER(i.customer) = LOWER(l.customer_name)` subqueries against `items`.
The rows it returns carry `email`, `player_name`, `handicap_index_9`,
`handicap_index`, `chapter` — **no `customer_id` at all**, which is why
every caller downstream is forced back onto names.

**Protect the CLASS, not the instance.** Fixing only the one route
leaves the export, and any future caller, on the same footing.

### Layer 3 — the plus rule was fixed at the call sites, not the mechanism

`compute_hole_derivations(par, strokes, strokes_received, formulas)` —
`database.py:15533`. A NEGATIVE `strokes_received` (a plus handicap)
makes `net = strokes - (strokes_received)` **add** a stroke on that
hole, and `stableford_net` then falls out of the table at the inflated
net. Eleven call sites go through this function. v2.450.0 patched two of
them locally rather than the function itself.

**The split the fix must respect** — the same negative value is CORRECT
in one half:

- **KEEP plus strokes (WHS / index math):** `get_differential_parity`
  (18358), `get_scoring_handicap_preview` (18514), `_two_nine_recap_rows`
  (20776), `derive_18hole_rounds_as_two_nines` (20977),
  `_nine_totals_for_card` (36471). USGA net double bogey is
  `par + 2 + strokes_received`; for a plus that legitimately lowers the
  cap, and changing it would corrupt every differential and index.
- **Already fixed locally (game):** `get_event_leaderboard` (14015),
  `live_scoring.build_cards`.
- **STILL WRONG:** **`get_scorecard` (22345)** — the card on
  `/handicaps` Kerry screenshotted — and **`fetch_champ_player_card`
  (10152)**, the Players Cup card.
- Renderers drawing the `○ = plus stroke` mark:
  `static/js/scorecard-render.js:137`, `static/js/points-render.js:643`.

**Fix shape:** move the rule INTO `compute_hole_derivations` behind an
explicit game-vs-WHS flag — `adjusted_strokes` keeps the true
`strokes_received`, while `net` / `net_vs_par` / `stableford_net` use
`max(0, strokes_received)` — and have the game callers apply the
round-level deduction (`live_scoring.build_cards` already shows the
shape with `d_pts` / `pts_adjust`). Then delete the two local patches so
there is one implementation. A future caller must not be able to miss
it.

**Worked example to test against** — Pat Youngs, 2026-09-15, The Quarry
Front, 2-Blue, index −0.5N. Gross 4,4,3,3,5,4,4,2,4 = 33. Today the card
shows NET SCORE 4,4,4,4,5,4,4,3,4 = 36 with `○` marks and NET PTS
1,1,0,1,1,1,1,1,1 = 8. Under the rule, no hole takes a plus stroke, so
the net row equals the gross row and net points equal gross points
(22) less the round-level deduction. **Confirm the rounding of the
deduction with Kerry before shipping** — a −0.5 nine-hole playing
handicap is the live case and `int(round(abs(ph)))` makes it 0, which
may or may not be what he wants.

## SCOPE

**In scope — item (1), identity**
1. Publish `customer_id` on every row `get_handicap_export_data`
   returns, and resolve its link/chapter/name joins through
   `handicap_player_links.customer_id` with the name join kept only as
   an explicit last-resort fallback that is *reported*, not silent.
2. Rebuild the event filter in `api_handicap_send_bulk_email` on
   `_event_roster_rows(conn, event_id)` and `customer_id` set
   membership. Keep the v2.456.0 bucket accounting and the named-skip
   list; make its classification correct.
3. Rebuild `members_only` on `customer_id`.
4. Enumerate the rest of the class: grep for any other place that joins
   `handicap_player_links` or `handicap_rounds` to a person by name
   (`LOWER(i.customer) = LOWER(l.customer_name)` is the signature).
   Either fix it or write down in `docs/claude/handicaps.md` which
   members of the class you deliberately left alone and why.
5. A backfill/audit read that lists every `handicap_player_links` row
   with a null or non-resolving `customer_id`, so Kerry can see how big
   the unlinked population actually is before anything is hidden by a
   fallback. Surface it through a bridge (`scoring-hcp-link-audit`) —
   read-only, no writes without Kerry's word.
6. Tests: a registrant whose `items.customer` differs from the handicap
   link's `customer_name` but shares a `customer_id` must be classified
   as SENT, not as "no TGF handicap on record"; a GG-RSVP-only
   registrant must appear in `registered`; a link with a null
   `customer_name` must not vanish.

**In scope — item (2), the plus rule**
7. Move the rule into `compute_hole_derivations` behind an explicit
   flag; remove the two local patches so there is ONE implementation.
8. Carry it to `get_scorecard` and `fetch_champ_player_card`, and to the
   `○ = plus stroke` mark in both renderers.
9. Leave every WHS/index call site alone, and say so in the changelog —
   a reader must be able to see that the differential math was
   deliberately untouched.
10. Ask Kerry how the round-level deduction rounds before shipping
    (the −0.5 case above). Rule 3b: this is member-facing scoring.
11. Test with Pat Youngs' 2026-09-15 Quarry Front card as the fixture,
    and add a WHS regression asserting his differential (0.5) and index
    (−0.5) are unchanged by the fix.

**Not in scope** (stays with the parent lane or another)
- The blind-draw rule-3b ratifications (parent, §10 of the handoff).
- Anything on the live leaderboard, starter sheet, or pairings display
  beyond removing the v2.450.0 local patch once the mechanism carries
  the rule.
- Re-deriving any posted index or differential. WHS math is untouched.
- Payout / money recording for s9.23 and a9.23 — done and verified.
- Re-sending the handicap cards themselves. **Kerry sends those**;
  offer, never send.

## STATE OF THE CODE

- Live version **v2.456.0** on `https://tgf-tracker.up.railway.app`;
  branch `claude/tracker-improvements-h7q2ns` is merged to `main` and
  `main` is deployed.
- v2.456.0 already counts and NAMES every skipped player and publishes
  the arithmetic (red when it does not reconcile) — the reporting is
  right, the *classification underneath it* is what this lane fixes.
- **Handicap rounds for both 2026-09-15 events are POSTED and COMPLETE**:
  s9.23 The Quarry 21 / 21, a9.23 Avery Ranch **12 / 12**.
  **CORRECTION (2026-09-15 late):** Lee Vasquez's tee-less card (3518)
  and Guillermo Arevalo's null-`customer_id` card were BOTH resolved by
  the concurrent event-closeout lane — dropped and keyed-re-imported as
  3529 (Blue tee, index 7.3) and 3528 (`customer_id` 821, index 7.8).
  **Neither is in your scope any more.** They are worth reading as
  evidence: Arevalo's card AND its posted handicap round both carried
  `customer_id` NULL, which is this lane's bug appearing in live data on
  the very night it was written up.
- Kerry's handicap cards for both events went out BEFORE those rounds
  posted, so they carried stale indexes. Once this lane's fix is live,
  tell him the cards are worth re-sending — do not send them yourself.

## STEPS

1. Read everything under READ FIRST. Post a mailbox ack:
   `post_platform_dialogue`, author `tracker-claude`, topic
   `session-digest` — "lane open — read #522–#523, docs
   handoff-2026-09-15…, handicaps.md, starting with the link audit".
2. Run the read-only link audit FIRST and show Kerry the number. If a
   large share of links have no `customer_id`, the fix order changes
   (backfill before switching the join).
3. Fix `get_handicap_export_data`, then the route, then `members_only`.
4. Sweep the class; document what you left.
4b. Then item (2): the plus rule into the mechanism, the two surfaces,
    the two renderers, the WHS regression test.
5. Tests, version bump, changelog, docs, push, verify live.
6. Report to Kerry with the s9.23 / a9.23 numbers recomputed under the
   new classification — specifically whether the 3 SA skips and the 2
   Austin skips were genuinely index-less or were name-match casualties.

## CONVENTIONS

Push to `main` as standard; bump `static/js/version.js` + changelog +
docs per CLAUDE.md rules 1–2; merge `main` into your branch BEFORE
bumping `version.js`; mailbox ack on open and digest on close; **never
send, pay, or delete without Kerry's explicit approval**; rule 3b
ratification before anything touching money, schema, or member-facing
behaviour.

START BY SAYING: *"Lane open — handicap surfaces. Read #522–#523 and the
09-15 handoff. Two things, both cases of a fix landing on the instance
instead of the class. (1) The card send matches registrants to handicap
links by NAME STRING, so a name variant reads as 'no handicap on record'
and the player quietly gets no card — and `get_handicap_export_data`
never returns a `customer_id` at all, which is why every caller is
forced onto names. (2) The plus rule you ratified last night was applied
at two call sites out of eleven, so the `/handicaps` scorecard and the
Players Cup card still add a plus stroke hole by hole. First move is a
read-only audit of how many `handicap_player_links` rows have no
`customer_id` — want that number before I change the join?"*
