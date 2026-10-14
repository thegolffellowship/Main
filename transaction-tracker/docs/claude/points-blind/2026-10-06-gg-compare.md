# Points blind test, Tue 10/6/2026: Golf Genius comparison (step d)

Kerry, in the Track B session, 10/13 ~1:25 PM CDT: "pull it".

There was ONE manual, read-only pull: `scoring-race-detail` per player, the
row-expansion read. It wrote nothing, and live standings were not touched.
The GG points intake stays OFF (gg_points_intake). GG had already awarded 10/6
(the s9.26 and a9.26 POINTS Net lines). The Tracker candidate is
`2026-10-06-candidate.md`.

## SA Fall NET (best 6)
| Player | Tracker 10/6 | GG 10/6 | Tracker total | GG total | Result |
|---|---|---|---|---|---|
| Rideout | 10 | 10 | 60 | 60 | match |
| Mazanec | 9 | 9 | 55 | 55 | match |
| Baker | 8 | 7 | 54 | 53 | DIFF, cause below |
| Niester | 8 | 8 | 50 | 50 | match |
| South | 5 | 5 | 45 | 45 | match |
| Marroquin | 9 | 9 | 45 | 45 | match |
| Sharitz | 0 | 0 | 18 | 18 | match |
| Lewis | 2 | 2 | 7 | 7 | match |
| Miller | 9 | 9 | 9 | 9 | match (10/6 is his first Fall line, card 12999814) |

## Austin Fall NET (best 6)
| Player | Tracker 10/6 | GG 10/6 | Tracker total | GG total | Result |
|---|---|---|---|---|---|
| Luke Youngs | 5 | 5 | 62 | 62 | match (10/6 not in his best 6 on either side) |
| Cannon | 2 | 2 | 29 | 29 | match |
| Schneider | 1 | 1 | 37 | 37 | match (12+9+6+5+4+1; the s18.11 front 0 drops) |

## Result
- 11 of 12 match exactly, on both the 10/6 points and the new total.
- Every best-6 drop matched as well.

**Baker, 8 vs 7.** The gross strokes are the same. The cause is the handicap.
- GG used PH 4. The Tracker used its locked PH 5 (the 10/7 handicap lock; known index gap #1315 / #1333).
- At PH 5, hole 5 (SI 9, par 3, he made 3) gets a pop: a net birdie worth 2, not 1.
- This is a handicap-source difference, not a points-math difference.
- **For Kerry to rule:** which PH counts for 10/6? The Tracker's lock was ruled to be the right one (CoS #1333).

## Notes
- **Schneider:** the bridge's own `best_n_total_of_parsed` shows 31 for him. That is because it parses only his first GG record. GG's combined table gives 37.
  - This is a display gap in the bridge, not in the board.
  - No event is on both of his records.
- **Not comparable yet:**
  - October Monthly: GG has no October points page yet.
  - City NET and Players Cup: their seasons are over, and GG awarded no 10/6 lines there.
- **Avery Ranch:** its scores are GG cards, so the Austin rows test the points maths only.
