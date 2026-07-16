# K3 — Payout Variance Characterization (READ-ONLY, for Kerry's ruling)

**tracker-claude, 2026-07-16 evening. Source: `scoring-fin-audit:k3`
(v2.117.0) — all 44 computed-vs-actual variance lumps with event/game/
date + GG's published money (`gg_game_results.purse`) where captured.
Per #207 A3: hypothesis (a) pay-time netting vs (b) engine delta. Answer:
mostly (b), plus two smaller known classes. No ruling proposed until
Kerry reads this — no data touched.**

## Headline

Where GG's published per-player money exists for a variance lump, **the
PAID amount equals GG's published number and OUR computed value is the
outlier**:

| lump | event | game | our computed | GG published | actually paid |
|---|---|---|---|---|---|
| #4139 Allen Wolin | s9.10 Riverside (05-19) | CTP | $23.00 | **$20.00** | **$20.00** |
| #4144 Jeff Young | s9.10 Riverside | CTP (in lump) | $23.00 | **$20.00** | lump −$3.00 |
| #3239 Roberto Moreno | s9.7 Canyon Springs (04-28) | CTP | $39.00 | **$37.00** | **$37.00** |
| #3082 Paul Reed | a9.2 Teravista (03-24) | CTP | $18.00 | $18.00 | $18.63 (+0.63) |
| #4654 Bryce Doggett | a9.13 Star Ranch (06-09) | CTP (in lump) | $25.00 | $25.00 | lump +$2.67 |

The −$3.00 / −$2.00 exact deltas are therefore an **ENGINE/MATRIX
DELTA** (our recorded pot exceeded GG's actual pot), not Kerry netting
side-game debts at pay time. Authority hierarchy already covers the
money: actual-paid (= GG) stands; our COMPUTED values are the ones to
reconcile down in the ratified pass. This makes K3 partly an **H-1
problem** (results layer), exactly as #207 suspected in hypothesis (b).

## The classes

**1. Engine/matrix delta (the −$3 / −$2 / −$1.50 exact class).**
Concentrated by EVENT, across different games — which points at a
per-event pot-tier (player count) mismatch rather than a per-game rule:
- **s9.7 Canyon Springs (04-28)**: skins $27→$24 ×3 (Wolin, Stich,
  McCrary — the 3217/3218/3219 triplet), team_net $39→$37 ×2 (Bourquin,
  Saldana), CTP $39→$37 (Moreno, GG-confirmed), individual_gross
  $12→$10.50. Seven lumps, every game high by one tier.
- **s9.10 Riverside (05-19)**: CTP $23→$20 (GG-confirmed) ×2 lumps.
- **s18.2 La Cantera**: CTP $18→$15. **s18.1 Cedar Creek**: CTP $19→$18.
Working hypothesis for the Deliverable-2 check: our side-games matrix
was evaluated at a higher player-count row than GG's actual entrant
count for those events. Verifiable event-by-event (matrix row vs GG
entrants) in the ratified pass.

**2. Team-Net blind-draw share delta (a9.13 Star Ranch).** computed
$11.11 (pot/9) vs paid $8.33 (pot/3-style share): the KNOWN v2.79.3
Team Net blind-draw over-distribution class — the repair only touched
unpaid rows, so paid rows retain the over-computed value. Lumps: Estes
−$2.78, Cannon −$2.78, plus the −$0.44/−$0.01 fringes on the same event.

**3. Pay-time rounding by Kerry (small ±, and whole-dollar round-ups).**
Pennies (±$0.01–$0.10, e.g. Landa Park's −$0.04/−$0.03 team-net cents),
and generous round-ups: Doggett $267.33→$270.00 (+$2.67), Marques
$24→$27 (+$3.00), Wicker $18→$20.80, Hogue $19→$21.67, Reed
$18→$18.63. These are the only lumps that look like true pay-time
behavior — all in the payer's-choice direction, mostly UP.

## Proposed explanation codes (for the four-way variance report, §9 of
the target model — Kerry ratifies)

`ENGINE_POT_TIER` (class 1) · `TEAMNET_SHARE` (class 2) ·
`ROUNDING_PAY` (class 3) · `UNEXPLAINED` (anything else — currently
none). Total absolute variance across all 44 lumps stays ~$55 — the
money is small; the CODES are what make the close auditable.

## Coverage caveat

GG published money is captured today only for CTP/LP/HIO/TEAM-class
games (`gg_game_results.purse`); skins/ind-net/gross money isn't in that
table, and `gg_history_results.money_cents` covers archive portals, not
2026\. Where GG money is missing above, the class assignment rests on the
exact-delta pattern + event clustering. A per-game GG money import for
2026 events would close the loop — Deliverable-2 candidate, read-only.

## Bonus: A2 (transfer chains) answered

`scoring-fin-audit:xferchain` over all 107 transfer chains: **zero
fee-double-booked chains** — no case where the 3.5% fee delta inside a
transfer-in leg is ALSO booked as a venmo-bd income row. A2's specific
double-count fear is negative on live data. The 72 "unbalanced" chains
(−$997.54 net) are dominated by missing/differently-keyed IN legs from
the pre-`xfer-flat` era plus residual-credit chains — the per-chain
zero-sum invariant (target model §7) still belongs in Deliverable 2, with
typed fee legs and backfilled in-legs.
