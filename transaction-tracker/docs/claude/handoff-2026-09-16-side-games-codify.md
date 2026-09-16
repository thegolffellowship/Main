# Side games, codified — lane handoff (2026-09-16)

Branch `claude/side-games-codify-r7h2wq`, pushed. **NOT merged to `main` —
see §6.** Mailbox: ack #531. CA Queue: #7, #8 opened.

Spun off from "TGF Tracker Improvements 2" on Kerry's *"should we spin off a
TGF Side Games session for a full journey through all possible game scenarios
and controls?"* → *"A. Write the spin off."*

---

## 1. The finding, and the correction to the record

**a9.23 Avery Ranch skins, $52. Golf Genius was right and we were wrong.**

Only **4 players bought the gross bundle** on a nine. The side-games matrix
switches Skins to ½ Net below 8 buyers on a nine, so GG ran **"SKINS 1/2 Net
$"** — a NET game. Our engine computed skins on `"basis": "gross"` and
carried `"half_net_below": {"9": 8}` beside a comment saying it *"does not
yet implement"* that — and then computed gross anyway behind a warning nobody
acted on. **A rule that only warns is not a rule.**

So we compared a net result against a gross computation and reported that GG
contradicted itself on Carlos Zapata's hole 7. It did not. Zapata made
**gross 4 on a par 4**, took a stroke there under the 50% allowance, and
**netted 3 — an outright net birdie**. GG's scorecard par and GG's skins-board
birdie are the gross and the net of the same hole, both correct.

`docs/claude/side-games.md` carried the wrong version as fact ("Golf Genius
disagreeing with ITSELF"). **Corrected in place** with the correction marked,
not silently rewritten.

**No money moves.** a9.23 was always paid correctly: Youngs $39 (holes 2/3/5),
Zapata $13 (hole 7), $52 over 4 skins. Zapata's differential (7.7 off gross
44) is computed off gross and never saw the allowance.

## 2. What is PROVEN

GG's detail strings are relative to par, so they pin the allocation from
outside our system:

| Player | GG detail | purse |
|---|---|---|
| YOUNGS, Luke | "Par on 2, Birdie on 3, Eagle on 5" | $39 |
| ZAPATA, Carlos | "Birdie on 7" | $13 |

- **Youngs received ZERO strokes.** Hole 5 is a par 5 he made in 3; GG calls
  it an **Eagle**, and with a stroke it would be an Albatross. PH 1.0 → 50% =
  0.5 → rounded **DOWN**. Half-up is refuted by GG's own words, not by the
  payout.
- **The engine reproduces GG exactly** — holes, vs-par labels and dollars —
  given the allocation those strings pin. `test_half_net_skins.py`.

## 3. What is OPEN — CA Queue #7, and it is money

**How the half stroke ROUNDS is not determined.** Nothing pins Zapata's 2.5
or Melchor's 3.5, and **every naive independent rounding awards Eduardo
Melchor a fifth skin GG did not pay** (half-up 5 skins *and* contradicts the
Eagle; banker's 6; floor 5).

Brute force over all stroke counts leaves 21 allocations consistent with GG's
board. In **every one of them Melchor ends up ≤ Zapata** — which no
independent per-player rounding of 2.5 and 3.5 produces. **The dial cannot be
reverse-engineered from outcomes.** It needs the rounding setting from the GG
tournament setup screen, or Kerry's ruling.

Until then the board **computes but declares itself provisional**
(`handicap_ratified: False` + a warning), and a test asserts that *none* of
the naive roundings reproduce GG, so the gap cannot be quietly closed by
guessing.

**It cannot be closed by analogy either, and this is the sharp bit.** Kerry
ratified a TGF rounding convention the same day (CA Queue #5, mailbox #530):
the plus-handicap ROUND deduction rounds **half away from zero**. Applying
that to the ½-Net allowance is the obvious shortcut — and it **does not
reproduce GG**. It gives Youngs 1 stroke, making his hole 5 an **Albatross**
where GG's own words say Eagle, and pays a fifth skin GG did not pay.

Not a contradiction in Kerry's rulings — a round-level deduction and a
per-player allowance are different mechanisms, and #530 says so. But **TGF's
own rounding convention and GG's observed behaviour disagree here**, which
makes CA Queue #7 the untether question in miniature: **when our rules and
GG's disagree, whose answer pays?** That is Kerry's to settle, and it is
bigger than one $52 pot.

*(Note: "off lowest" was a no-op on a9.23 — Straiton played off 0.0 and was
the low — so this event does not exercise that dial either.)*

**Also opened: CA Queue #9 — the allowance ladder has no row for a FIVESOME.**
Rule 15f (ratified today, #530) made blind-draw team size follow the GROUP
rather than a constant — Kerry: *"Could be more if fivesomes are selected."*
USGA Appendix C stops at four, and a fivesome playing Best 1 would currently
fall through to the four-player 75% row by assumption. Not biting today (live
Team Net money follows GG's team string and the matrix), but it is reachable
by ratified rule now, so it is flagged before it becomes live rather than
after.

## 4. USGA allowances — CA Queue #8

Recorded as data in `live_scoring._USGA_ALLOWANCES` **with verification
state**, because "we are sure" and "we think" must not look alike in money code.

- **CONFIRMED, four-player ladder:** Best 1 of 4 **75%**, Best 2 of 4 **85%**,
  Best 3 of 4 **100%**, Best 4 of 4 **100%** — matches Kerry's ruling exactly.
  Team Net's allowance now follows the **ball count** as data.
- **NOT CONFIRMED, two-player (CART Net):** Best 1 of 2 (85%, agrees with
  USGA's Four-Ball Stroke Play but unverified here) and Best 2 of 2
  (**carries no value at all**).

**Why not just taken:** `usga.org` is blocked by this environment's egress
proxy (403 on CONNECT), as it was for the parent session — and so are
`randa.org`, the mirrored Appendix C PDFs and FORE Magazine. Only search
**snippets** were reachable. A snippet is not the Rules of Handicapping. The
four-player ladder had two independent searches agreeing exactly with what
Kerry had already ratified; the two-ball row did not.

**The unconfirmed rows carry `None`, never a plausible default.** A game that
needs one must report, not assume.

## 5. What shipped (v2.459.0)

All in the **pure engine** + one read-only admin bridge. **No schema, no
money path, no member-facing surface.**

- **The matrix is the governing layer, in data.** `skins` carries `variants`
  (basis + handicap dials + GG's own name each); `select_variant` resolves
  buyer count → which game runs and **REPORTS the decision with its reason**.
- **`pops_per_hole` declared on every game**, and `game_handicaps()` so a game
  derives its OWN allocation (allowance → rounding → off-lowest → stroke
  index) instead of borrowing whatever net game the card was built for.
- **Allowance % and "off the lowest" kept as two separate dials.** USGA's
  allowance is a % of each player's own Course Handicap; off-the-low is a
  TGF/GG convention USGA applies to *match* play.
- **`scoring-skins-audit` asks the game's actual question**, and prints both
  the gross and the pops on every hole plus each buyer's handicap, so the two
  questions can never again be mistaken for each other.

Tests: `test_half_net_skins.py` (43 checks on a9.23's real cards, driving the
audit bridge end-to-end over an in-memory DB). Suite **70 py green**; the 11
failures are identical on `origin/main` and predate this lane.

## 6. WHY THIS IS NOT ON `main`, and what that costs

The lane's conventions say "push to `main` as standard", but this session's
standing git instruction is to develop on `claude/side-games-codify-r7h2wq`
and **never push to another branch without explicit permission**. `main`
auto-deploys to the live app, no human was present to confirm, and I am not
treating a parent session's task note as Kerry's permission. So the work is
complete and pushed to the designated branch, and merging is one command.

**The honest cost: I could not verify live.** The `scoring-*` bridges run
against the deployed Railway app, so the rewritten `skins_audit` is proven by
test but **has not been run against the live database**. First thing after
merge: `scoring-skins-audit:a9.23 Avery Ranch` should report
`game.variant = "half_net"`, `basis = "net"`, `handicap_ratified = false`, and
hole 7 as Zapata's outright hold rather than a tie.

## 7. Scope NOT done, and why

Of the lane's six items, 1, 2, 4 and 5 are done; 3 and 6 are not.

- **(3) The `game_templates` / `game_template_versions` / `event_games`
  tables.** Designed and shaped for, deliberately **not built** — they are
  schema and schema needs rule-3b ratification. The variant structure is
  built to lift into `config_json` unchanged, so it is a move, not a redesign.
  **This matters more than it looks:** without per-event snapshots a past
  event recomputes under TODAY's rules. The a9.23 audit now returns ½ Net
  because the CURRENT config says 4 buyers on a nine means ½ Net — **right by
  luck, not by record**. Guiding principle 4 is not satisfied until the
  snapshot exists.
- **(6) The full journey through every game with Kerry.** Not started — it is
  a conversation, and Kerry was not in this session. CA Queue #7 and #8 are
  the first two questions of it.

**Also open, from the a9.23 GG setup screen and modelled nowhere:** "Skins
with Carry", "To win Skin, score must be", "Validated on next hole by". All
were inert on a9.23 (No / Any score / No validation) but all three are real
dials.

## 8. The lesson, which is the parent lane's lesson again

The `half_net_below` key had been sitting in the config **with a comment
naming the exact gap**, and the engine computed the wrong game anyway and
emitted a warning into a field nobody read. The knowledge was not missing;
the ENFORCEMENT was. #529 put it as "a correct fix applied to the instance
instead of to the mechanism" — this is the same shape one turn further on:
a correct *diagnosis* recorded instead of enforced.

When a rule is known but unimplemented, make the code REFUSE or REPORT at the
surface someone actually reads — not leave a comment and compute something
else.
