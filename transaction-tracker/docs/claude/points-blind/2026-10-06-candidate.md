# Points blind test: Tue 10/6/2026, Tracker CANDIDATE (not live)

Kerry 10/13 (CoS #1693-1): "Can we generate points on our side first for last
Tuesday? Then I'll run Golf Genius for you to check it against." Track B owns
this. These numbers are a CANDIDATE: they are not merged into the live
standings. Parity is confirmed by the CoS and ruled by Kerry (#1693 e).
GG points intake has been OFF since v2.559.2 (app setting gg_points_intake).

## Method
- Cards come from `get_scoring_rounds` and `get_scorecard_detail`: 21 for Olympia Hills (3308) and 14 for Avery Ranch (3316).
- NET points = `game_stableford_net_after_plus`. A plus handicap comes off the round once.
- GROSS points = `stableford_gross`.
- Both are floored at 0. A raw negative value is shown in brackets.
- Rules: Side Games #1703 (b), the rules of record.
- **Avery Ranch 3316:** the only scores are GG-imported cards (back nine). It tests the points maths, not score entry.
- **Baker (3308):** the rows carry GG's PH 4. The Tracker's locked PH is 5 (his score-entry card), so his points are re-derived at PH 5.

## Per player: tee · PH · gross · NET pts · GROSS pts

### San Antonio, Olympia Hills (3308)
| Player | cid | Tee | PH | Gross | NET | GROSS |
|---|---|---|---|---|---|---|
| Saldana | 101 | White | 15 | 47 | 13 | 8 |
| Rideout | 6 | Gold | 13 | 48 | 10 | 6 |
| Stich | 298 | Gold | 7 | 42 | 10 | 12 |
| Marroquin | 142 | Gold | 4 | 40 | 9 | 15 |
| Miller | 125 | White | 11 | 47 | 9 | 7 |
| Mazanec | 82 | White | 4 | 40 | 9 | 15 |
| Johnson | 313 | Gold | 15 | 51 | 9 | 3 |
| Palacios | 21 | Gold | 7 | 44 | 8 | 10 |
| Baker | 87 | White | 5 (GG 4) | 42 | 8 (7 at GG PH) | 12 |
| Niester | 18 | White | 1 | 38 | 8 | 18 |
| Pat Youngs | 136 | Gold | +3 | 34 | 8 (11 − 3) | 22 |
| Murphy | 131 | Gold | 15 | 53 | 7 | 2 |
| Thompson | 19 | White | 16 | 56 | 5 | 0 (−2) |
| South | 24 | Gold | 3 | 45 | 5 | 9 |
| Angelone | 709 | White | 15 | 55 | 5 | 0 (−1) |
| Wicker | 33 | Gold | 6 | 47 | 5 | 8 |
| Bourquin | 103 | Gold | 10 | 51 | 4 | 3 |
| Skinner | 93 | White | 3 | 45 | 3 | 9 |
| Lewis | 817 | White | 12 | 55 | 2 | 0 (−1) |
| McCormick | 765 | Red | 17 | 60 | 2 | 0 (−6) |
| Sharitz | 38 | Gold | 7 | 53 | 0 | 1 |

### Austin, Avery Ranch (3316), GG cards only
| Player | cid | Tee | PH | Gross | NET | GROSS |
|---|---|---|---|---|---|---|
| Zapata | 439 | White | 4 | 40 | 9 | 14 |
| Bartz | 22 | White | 6 | 43 | 8 | 12 |
| Arevalo | 821 | Blue | 7 | 45 | 7 | 9 |
| Straiton | 31 | Blue | 1 | 40 | 7 | 16 |
| Vasquez | 99 | Blue | 7 | 45 | 7 | 9 |
| Melchor | 61 | Blue | 5 | 43 | 7 | 11 |
| Gwin | 187 | Blue | 5 | 46 | 6 | 9 |
| Luke Youngs | 13 | Blue | +1 | 39 | 5 (6 − 1) | 17 |
| Post | 49 | Blue | 2 | 43 | 5 | 12 |
| Compton | 166 | White | 7 | 48 | 4 | 7 |
| Williams | 10 | Green | 15 | 57 | 4 | 0 (−2) |
| Parker | 833 | Blue | 2 | 45 | 3 | 10 |
| Cannon | 438 | Blue | 3 | 47 | 2 | 7 |
| Schneider | 85 | Blue | 4 | 48 | 1 | 6 |

## Races (Fall = best 6 plus the Fall Championship, which is not played yet)
The "before" totals are GG's lines through 9/29, read once through the read-only bridge `scoring-race-detail`. GG has not awarded 10/6.

### SA Fall NET
| Player | Before | +10/6 | New total | What changed |
|---|---|---|---|---|
| Rideout | 56 | 10 | 60 | drops a 6 (s9.24) |
| Mazanec | 51 | 9 | 55 | drops a 5 |
| Baker | 49 | 8 | 54 | drops a 3 (53 if GG's 7 is used) |
| Niester | 48 | 8 | 50 | drops a 6 |
| South | 41 | 5 | 45 | drops a 1 |
| Marroquin | 36 (5 lines) | 9 | 45 | nothing dropped |
| Sharitz | 18 (4 lines) | 0 | 18 | |
| Lewis | 5 (3 lines) | 2 | 7 | |
| Miller | none on GG's board | 9 | 9 | FLAG: enrolled (item 2203), but has no GG Fall row |

### Austin Fall NET
| Player | Before | +10/6 | New total | What changed |
|---|---|---|---|---|
| Luke Youngs | 62 | 5 | 62 | 10/6 doesn't make his best 6 |
| Cannon | 28 | 2 | 29 | drops a 1 |
| Schneider | 36 | 1 | 37 | drops a 0 |

### City NET races and The Players Cup
- These races get 0 points for 10/6. Their seasons ended with the City Championships (7/31, 8/1).
- The 10/6 POINTS game feeds the Fall NET races only.

### The Fellowship Cup
- It is a projection from the City NET positions, not points-based, so it gets nothing.

### October Monthly
- 10/6 is the first October event, so each player's October total equals their NET points above.

## Against Side Games' independent cross-check (#1703 c), 3308
- 20 of 21 players match exactly, net and gross.
- Baker is 8 against 7. The gross strokes are the same. The difference is the PH:
  - the rows carry GG's PH 4;
  - the Tracker's locked PH is 5, which pops hole 5 (SI 9), a net birdie.
- This is the known index gap (#1315 / #1333).
- **Finding:** for GG-era events, the derivation layer computes from GG's PH, not the locked PH.

## Schneider "x2 cards sum=36"
| GG record | Events | Points |
|---|---|---|
| 12347458 | a9.21 9/1 = 5, a9.23 9/15 = 9, a9.24 9/22 = 4, a9.25 9/29 = 12 | 30 |
| 13085037 | s18.11 Cedar Creek 9/19: back nine 6, front nine 0 | 6 |

- No event is on both records, so the 36 is NOT overstated. It equals the best 6 over the union of his lines.
- Rules: one card per player per event; events played = DISTINCT events (state-of-the-tracker §2); one person = one customer_id (CLAUDE.md principle 6).
- In the Tracker, all five of his events sit under customer 85.
- The class gap stays open: the GG-side fold sums without an overlap check.

## Open
- Miller's missing Fall row: either he never earned a Fall line, or his GG identity is unlinked.
- The GO 6 ledger baseline is 9/27, not 9/29. That is why the before totals come from the read-only detail read.
- Ranks are not recomputed.
