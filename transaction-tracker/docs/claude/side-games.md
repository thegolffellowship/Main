# Side Games — RATIFIED SPEC v1.0 (2026-07-05)

Status: **RATIFIED by admin** via the platform dialogue reconciliation
(mailbox ids 6-11). Platform-side twin: TGF_Side_Games_Rules_v1_0.md
(OneDrive 7_Web & App Development/ + Project knowledge). Sources: live
GG portal evidence (s9.16, s18.7, a9.16), the Pricing & Services Master
Doc v2.0 (via platform-claude), Kerry's 2026-07-05 rulings, and the
prize matrix (analysis below). Open flags listed at the bottom.

## Buy-in pricing (as sold; pools exclude TGF markup)

- **NET add-on**: $16 sale (9h) = Ind Net $9 + MVP $4 + markup $3;
  standalone 18h $30 = Ind Net $18 + MVP $8 + markup $4.
- **GROSS add-on**: $16 sale (9h) = Skins $9 + Ind Gross $4 + markup
  $3; standalone 18h $30 = Skins $18 + Ind Gross $8 + markup $4.
- **BOTH**: $32 (9h) / $60 (standalone 18h).
- **Combo events (9/18)**: 18-hole players pay 18-hole INCLUDED pots
  but 9-HOLE bundle prices. Standalone 18s (s18.x) use the $30/$60.
- Access: NET & BOTH members only; GROSS & NONE available to all.
- Event entry includes game money: **$7/player (9h)** = Team Net $4 +
  CTP $2 flat + Hole-in-One $1; **$14/player (18h)** = $8 + $4 + $2.

## Included games (every player)

- **TEAM Net** — foursomes, one best NET ball per hole vs par; blind
  draw ("Bl[Name]") fills short teams. 9h winner-take-all; 18h pays
  1st + 2nd; ties split. Guests/cross-chapter included.
- **Closest to Pin** — flat $2 (9h) / $4 (18h) entry, max 2 CTPs per
  nine, winner-take-all each. Fewer par-3s than slots → remaining
  dollar(s) become a **Longest Putt contest on the last hole**. More
  par-3s than slots → automation selects the **shortest** par-3s.
  **"No Winner" pots CARRY OVER to the next event** (carried
  liability, not variance).
- **Hole-in-One** — $1/entrant (9h) / $2 (18h); accrues across events
  until won, pays out, resets to $0. **Members-only eligibility to
  win** (guests/first-timers pay in but cannot win).
- **Match Play** — season singles bracket per city, one match per
  event round, no per-round purse; season payout top 4 at
  50%/25%/15%/10% of pool.

## NET add-on games (buyers only)

- **Individual Net** — flighted (matrix-driven; 9h: 1 flight to 11
  buyers, 2 flights at 12+, split observed at HCP 12.0; 18h: up to 4
  flights by buyer count). Pays 1st/2nd per flight at ~2/3-1/3, adding
  3rd (and 4th on 18s) as buyer counts grow; ties split combined
  place money.
- **MVP** — $4/buyer (9h) / $8 (18h) from the NET bundle. Multiple TGF
  events same day → split evenly: **City MVP $2 + TGF MVP $2** (9h) /
  $4 + $4 (18h). Single-event day → ALL MVP money to City MVP, no TGF
  MVP. City MVP = best net Stableford among buyers; tiebreakers:
  1) Individual Net score, 2) Gross score, 3) split. **TGF MVP** = the
  City MVP with the HIGHER points across the day's events; tie →
  split, no tiebreaker. Recorded purse-only in GG (Pos "None").

## GROSS add-on games (buyers only)

- **Skins** — GROSS skins (outright low gross on a hole within
  flight); flighted (2 flights at 8+ buyers on 9h — below 8 the
  matrix runs Skins ½ Net — up to 4 flights on 18s); each flight's
  pot divides equally per skin won.
- **Individual Gross** — raw gross, flighted (activates ~20 buyers on
  9h / 16 on 18h per matrix; manager may override below — observed
  running with 13 buyers and 3 flights on s18.7), 1st per flight
  (2nd added at large counts on 18s).

## Prize matrix — derived rules (from games-matrix.js seed;
## live copy in app_settings, edited via the Matrix UI)

Per-player-count N, closed forms verified across the whole matrix:

| Line | 9-hole | 18-hole |
|---|---|---|
| Event game money | $7×N | $14×N |
| Team Net pot | $4×N (1st only; 2nd appears ~N≥40) | $8×N (same shape) |
| CTP total | $2×N split evenly over active CTPs | $4×N; CTP count grows 2→3→4 at N=16/24/32, pot splits evenly |
| Hole-in-One | $1×N | $2×N |
| NET pool | $13×N | $26×N |
| Individual Net | $9×N | $26×N − MVP pot |
| City MVP + TGF MVP | $2×N + $2×N | MVP pot = $8×N **capped at $100 flat from N≥16** (FLAG) |
| GROSS pool | $13×N below 20 buyers; **$15×N at 20+** (FLAG) | $26×N |
| Skins | $9×N (all of pool below 20) | $18×N equivalent share |
| Individual Gross | $4×N + $1×N gross-low (active N≥20) | $8×N |
| Net flights | 1 (≤11), 2 (12+) | 1 (≤13), 2 (14-33), 3 (34-49), 4 (50-64) |
| Skins flights | 1 (<8), 2 (8+) | 2 (8-31), 3 (32-47), 4 (48+) |
| Gross flights | off (<20), 4 (20+) | off (<16), 4 (16+) |

Skins payout arrays = flight pot ÷ skins count (verified exact), with
ONE data anomaly: 9h N=18, 3-skin value reads 24.67 vs computed 39.00.

## teamMWP investigation (owed per mailbox id 8) — RESOLVED

The "MWP" line originated in the source spreadsheet
25-SideGame-PrizeMatrix.xlsx and was carried verbatim into the Matrix
UI (matrix.html "MWP" sub-row under Team Game) and games-matrix.js at
~$1×N. **No Tracker payout logic reads it** — display-only. Admin has
ruled the game does not exist; recommend deleting the row from the
matrix UI/data (pending admin go-ahead). Likely the same artifact as
the Platform docs' "Team MVP" naming slip.

## Open flags (for admin)

1. 9h GROSS pool: pricing doc says $13/buyer; the matrix pays $15×N
   once Ind Gross activates (N≥20) — and the matrix's own gross total
   exceeds the sum of its listed lines by $1×N there. Which is right?
2. 18h MVP pot capped at $100 flat (matrix) vs $8×N (pricing doc).
3. The 9h N=18 skins-array anomaly (24.67 vs 39.00) — data entry?
4. Delete teamMWP from the matrix?

## Next phase (ratified direction, mailbox ids 10-11)

Extract the GG game SETUP layer (handicap %, scoring basis, par-3
strokes, etc.) for every side game AND POINTS game into this doc.
Standard confirmed: all game configuration = admin-editable, VERSIONED
definitions (payout_templates pattern: append-only versions, per-event
snapshots, past events frozen) — never hard-coded rules.

## Not covered

HCM league games ($100 prize fund included; Skins Gross add-on $27),
Lone Star Cup (Side Games $75 add-on), TGF Championship special
add-ons (NET $50: R1 $15 + R2 $15 + Overall $20; GROSS $52: Skins
$18×2 + Weekend Individual $16), pre-season events. Per Pricing doc
§7.11 special-event side games are defined per event.
