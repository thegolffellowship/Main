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
| Team Net pot | $6×N CART Net (N=4–15, incl. CTP money); $4×N TEAM Net at 16+ (2nd place appears ~N≥40) | $12×N / $8×N (same shape) |
| CTP total | $2×N split evenly over active CTPs | $4×N; CTP count grows 2→3→4 at N=16/24/32, pot splits evenly |
| Hole-in-One | $1×N | $2×N |
| NET pool | $13×N | $26×N |
| Individual Net | $9×N | $26×N − MVP pot |
| City MVP + TGF MVP | $2×N + $2×N | single-event day: min($8×N, $100), excess → Ind Net; multi-event day: $4×N + $4×N |
| GROSS pool | $13×N always (totals column fixed 2026-07-05) | $26×N |
| Skins | $9×N (all of pool below 20) | $18×N equivalent share |
| Individual Gross | $4×N + $1×N gross-low (active N≥20) | $8×N |
| Net flights | 1 (≤11), 2 (12+) | 1 (≤13), 2 (14-33), 3 (34-49), 4 (50-64) |
| Skins flights | 1 (<8), 2 (8+) | 2 (8-31), 3 (32-47), 4 (48+) |
| Gross flights | off (<20), 4 (20+) | off (<16), 4 (16+) |

Skins payout arrays = flight pot ÷ skins count (verified exact), with
ONE data anomaly: 9h N=18, 3-skin value reads 24.67 vs computed 39.00.

## teamMWP — RESOLVED (admin, 2026-07-05)

**MWP = Maximum Winnings Potential.** Not a game: it is the largest
amount one person can win from the team game = team1st ÷ team size
(verified exact across the matrix once team type is known). Consumed
by the Events page GAMES tab, which shows an MWP column per game and
sums an event-level Max Winnings Potential. KEEP — earlier deletion
recommendation retracted. (The Platform docs' "Team MVP" label remains
a separate naming slip for Team Net.)

## Matrix audit (admin-requested, run 2026-07-05)

Programmatic audit of every cell in both matrices against the ratified
pool model ($13-of-$16 / $26-of-$30 to pots, rollover rules). Results:

**Real defects (both FIXED — boot repair `_repair_matrix_gross_totals`
patches the DB copy; static seed corrected in-repo):**
1. 9h `grossTotalPot` column read $15×N for every N≥20 while its own
   game pots correctly sum to $13×N (Skins 9 + Ind Gross 4). Display
   column only — but it fed the Events Games-tab gross subtotal, which
   overstated. 45 cells corrected to 13×N. (This was the source of the
   earlier "$15/buyer" confusion; the 18h totals were always correct.)
2. 9h N=18 skins array, 3-skin cell: 24.67 → 39.00 (= flight pot 117
   ÷ 3, the ratified formula). 1 cell corrected.
3. Cosmetic, unfixed: N=2–3 rows show eventTotalPot $7×N while every
   event game is NO_EVENT.

**Not defects — the "removed Excel formulas" survive as encoded rules:**
- **CART Net below 16 players**: teamType switches to CART Net
  (2-person cart teams) for N=4–15 with team pot $6×N — the $2×N CTP
  money rides in the team pot because no CTPs run below 16; TEAM Net
  foursomes at $4×N + CTPs $2×N from N=16. Event money is $7×N either
  way. (18h mirror: $12×N cart pot below 16, $8×N + $4×N CTPs at 16+.)
- **Ind Gross → Skins rollover**: below ~20 gross buyers (9h) / 16
  (18h) Individual Gross cancels and its $4×N/$8×N rolls into Skins
  (skins pot = full $13×N/$26×N). Real-world confirmed: s9.16 ran
  Skins-only with total purse $195.01 = 13 × 15 gross buyers.
- **18h MVP cap**: mvp = min($8×N, $100), and Individual Net = $26×N −
  mvp — the excess above the cap flows to Individual Net automatically.
  Matches admin intent for SINGLE-event days (below).

## 18h MVP day-type rule (admin, 2026-07-05 — understanding to confirm)

- **Single 18h event that day**: all MVP money to City MVP, capped at
  $100; MVP-designated money above the cap reroutes to Individual Net
  payouts. (The matrix encodes exactly this.)
- **Multiple TGF events that day**: follow the 9-hole model — split
  evenly, $4/buyer City MVP + $4/buyer TGF MVP, no cap (pending admin
  confirmation on the no-cap reading). The matrix currently encodes
  only the single-event variant; day-type awareness is a runtime
  concern for payout tooling.

## Remaining open item

GG game SETUP layer (handicap %, scoring basis, par-3 strokes, etc.):
admin will supply Golf Genius setup screenshots per tournament rather
than have it reverse-engineered. Fold into this doc as they arrive,
modeled as versioned game definitions per the ratified requirement.

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
