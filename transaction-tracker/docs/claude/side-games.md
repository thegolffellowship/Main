# Side Games Catalog — reverse-engineered from GG portals (DRAFT, 2026-07-05)

Status: **UNVERIFIED — awaiting admin confirmation.** Inferred from live
portal results (s9.16 SA round 1586691, s18.7 SA round 1591013, a9.16
Austin round 1594052) cross-checked against static/js/games-matrix.js
(the 25-SideGame-PrizeMatrix). Every purse observed reconciled to the
matrix; the matrix is keyed by that game's BUYER count, not event field
size. Confirmed cross-check: s9.16 Purse Summary — Niester $177.63 =
Ind Net $47.25 + skin $24.38 + CTP#7 $32 + MVP $42 + team share $32.

## Fee architecture (inferred from matrix per-player multiples)

- **Event entry includes $7/player of game money**: TEAM Net $4 +
  two CTPs $1 each + Hole-in-One reserve $1 (eventTotalPot = 7×N).
- **NET side-game package = $13/buyer**: Individual Net $9 + city MVP
  $2 + TGF MVP $2 (netTotalPot = 13×N).
- **GROSS side-game package = $15/buyer**: Skins $9 + Individual Gross
  $4 + ~$2 residual (grossTotalPot = 15×N; the last $2/buyer's exact
  destination — grossLow1st line? — needs admin confirmation).
- Orders record the purchase as side_games = NET / GROSS / BOTH / NONE.

## Per-event games (all players)

- **TEAM Net $** — foursomes, one best NET ball per hole vs par
  (front/back subtotals shown on 18s). Short teams filled by blind
  draw ("Bl[NAME]" = that player's card counted again). 9-hole:
  winner-take-all (observed $128 at 32 players, split $32 per
  teammate). 18-hole: pays 1st + 2nd (observed $156/$76; 2nd split
  across T2 ties). Cross-chapter + guests all participate.
- **Closest to Pin** — one game per par-3 (2 on a 9, 4 on an 18),
  $1/player each, winner-take-all ($32 at 32 players). "No Winner"
  outcome exists (observed s18.7 #12) — carryover/absorption rule
  unconfirmed.
- **Hole-in-One** — $1/player reserved per event in the matrix; no
  published GG game. Presumed contingent pool that only pays on an
  ace — accrual/carryover mechanics unconfirmed.
- **MATCH PLAY** — season singles bracket per city (SAN ANTONIO MATCH
  PLAY; 2026 Austin City Match Play). One bracket match played during
  each event round (result like "4 & 3"). No per-round purse.

## NET package games (buyers only)

- **INDIVIDUAL Net $** — two flights split at HCP 12.0 (9-hole).
  Pays 1st (~2/3 of flight pot) + 2nd (~1/3); ties split the combined
  places (observed: T1 pair each $47.25 = (63+31.5)/2 at 21 buyers).
  Flight pot = $4.50 × buyers per flight.
- **MVP $ (city)** — highest NET Stableford among package buyers,
  winner-take-all $2 × buyers. Tiebreakers: chain visible in GG
  ("Won 2nd Tiebreaker - Gross Score") — 1st tiebreaker unconfirmed.
  One city MVP per event (matches event_mvps semantics).
- **TGF MVP $** — cross-city MVP among the day's/week's paired events;
  pot $2 × combined buyers (observed $72 = 36 buyers SA+Austin);
  winner recorded purse-only (Pos "None"); shareable on ties.

## GROSS package games (buyers only)

- **SKINS Gross $** — two flights at HCP 12.0 (9-hole). A skin =
  outright lowest GROSS on a hole within the flight (details like
  "Birdie on 5", "Par on 8"). Each flight's pot (half the skins pot)
  divides equally per skin (observed $97.50/flight: 4 skins → $24.38
  each; 3 skins → $32.50 each).
- **INDIVIDUAL Gross $** (observed on 18s; matrix implies 9s too) —
  raw gross score, three flights on s18.7 (<10 / 10-15.9 / 16+),
  1st per flight (observed $34.67 × 3). Matrix grossFlights=4 at
  larger counts — flight count appears buyer-count-adaptive.

## Matrix lines not yet observed in portals (ASK ADMIN)

- **teamMWP** ($1 × N) — unknown meaning (Most Wins Points?); no
  matching GG game found.
- **netHigh1st/2nd/3rd** — matrix names suggest a "high flight" of
  Individual Net; consistent with observed Flight 2 payouts (values
  mirror netLow). Interpretation: netLow = Flight 1, netHigh =
  Flight 2. Needs confirmation.
- **Hole-in-One** accrual (above), CTP "No Winner" handling, and the
  GROSS package $2/buyer residual.

## Not covered here

Hill Country Matches league games (Matches/Shootout/Non-Matches) and
pre-season events (Kickoff, LA CANTERA, CEDAR CREEK) run their own
formats — catalog separately if needed.
