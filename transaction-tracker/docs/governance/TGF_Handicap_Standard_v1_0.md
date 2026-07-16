**OneDrive = authoritative · Tracker copy = enforcement mirror · updates arrive via the platform mailbox and are committed verbatim.**

# TGF HANDICAP STANDARD v1.0

**Status:** Governing document of record for TGF handicaps
**Ratified by:** Kerry Niester — D1 2026-07-16; R1/R2/R3 + layering principle 2026-07-15; prior rulings as cited
**Maintained by:** platform-claude · **Implemented in:** TGF Tracker (handicap_calc.py + handicaps.md)
**Supersedes:** website "TGF Handicaps" page as the source of truth (website rewrite pending, §7)

---

## 1. BASELINE

TGF handicaps follow the **World Handicap System (2020–present)** in every respect except the
deviations enumerated in §4. Golf Genius is not the standard — WHS is. GG's calculations were
used as validation evidence, not as authority. Any behavior not listed in §4 as a deviation is,
by definition, WHS — and any discovered difference from WHS not in §4 is a defect.

## 2. THE TGF INDEX (9-hole index, "N" suffix)

- **Basis:** the player's best 8 of their most recent 20 **nine-hole differentials**,
  within a **12-month lookback window** (Deviations 1, 2).
- **Differential:** (113 / slope) × (adjusted gross − course rating), rounded to tenths,
  using the slope/rating of the nine actually played, from the round's own tee row.
- **Adjusted gross:** WHS net double bogey (par + 2 + strokes received per hole), computed
  at **100% handicaps on raw gross only** — see the Layering Principle, §5.
- **Small records:** WHS Rule 5.2a ladder, adapted to 9-hole counts (established at 27 holes).
  [PENDING D15/O5: straight-40% ladder proposal under impact sweep.]
- **Multiplier:** none. [R1 ratified: ×0.96 removed as a pre-2020 USGA relic.
  APPLICATION PENDING CC impact sweep I-2 + retroactivity boundary — until applied,
  live indexes still carry 0.96.]

## 3. COURSE & PLAYING HANDICAP (D1 — RATIFIED 2026-07-16)

1. **Course Handicap** = index × (slope / 113) + (rating − par), **unrounded** through
   intermediary steps (full precision, rounding once, as the last step — matches WHS and
   GG's own stated method).
2. **Playing Handicap** = whs_round(Course Handicap) at **100% allowance** — nearest whole,
   .5 rounds up toward +∞. Capped at **18.0 nine-hole Course Handicap** (Deviation 3).
   Ordering: pin ROUND-THEN-CAP in config (GG's observed order; equivalent at integer caps,
   divergent at fractional — must be explicit before any per-game cap ships).
3. **Per-hole allocation** by stroke index, hardest first, wrapping for a second stroke;
   **maximum 2 strokes per hole** (equivalent to the 18.0 cap on nine holes).
4. **Explicitly excluded from this ratification:** plus-handicap treatment (§4 Dev. 7) and
   all per-game adjustments (allowances, team rules) — each requires its own ruling.

Validation of record: formula reproduced GG's printed worked calculations for every player
examined (s9.17 Silverhorn, s9.15 Quarry incl. cap-firing and ladies-tee cases); per-hole
allocation matched GG's dots 46/46 across both chapters.

## 4. DEVIATION REGISTER (exhaustive — if it's not here, it's WHS)

| # | Deviation from WHS | Status | Member-facing line |
|---|---|---|---|
| 1 | **9-hole differentials** as the basis (not 18) | RATIFIED (2022, flagship) | "Your best 8 of your last 20 nine-hole scores — your hot nine counts immediately." |
| 2 | **12-month lookback window** (WHS has none) | RATIFIED R2 (2026) | "Only the last 12 months count — your handicap reflects your game now." |
| 3 | **Max 2 strokes/hole = 18.0 nine-hole CH cap** | RATIFIED D4 | "No player receives more than two strokes on any hole." |
| 4 | **Max-triple score entry** interacting with NDB | RATIFIED (documented, accepted) | (internal — rare, favors the player) |
| 5 | **No ×0.96 multiplier** (WHS-conforming; removes a legacy USGA relic) | RATIFIED R1 — application pending sweep | (none needed — this IS WHS) |
| 6 | **75% of external index** for new members until 27 TGF holes | PUBLISHED, unimplemented — O4 | "Bring your GHIN — you'll play at 75% of it until your TGF record stands on its own." |
| 7 | **Plus-handicap treatment** | OPEN — O1 session. Current practice: fall-where-it-falls; website ÷2 rule NOT practiced | (website paragraph stale — pull at rewrite) |
| 8 | **Straight-40% counting ladder** from round 1 | PROPOSED O5/D15 — sweep pending | (drafted after ruling) |

### Conscious omissions (WHS features TGF does not run — pending deliberate rulings, O3)

| WHS feature | What it does | TGF status |
|---|---|---|
| Soft/hard caps (Rule 5.8) | Limits index RISES vs 12-month low (soft at +3, hard at +5) | Not implemented — decide at O3 (note: caps rises, opposite of the injury problem) |
| Exceptional Score Reduction | Auto-cuts index −1/−2 after a score ≥7.0 below | Not implemented — decide at O3 |
| PCC (playing conditions) | Daily field-wide differential adjustment for weather/setup | Not implemented — decide at O3 |
| Relative tee par difference | CH adjustment when tees carry different pars | GG ignores it; TGF position PENDING I-5 — required before any unequal-par course |

## 5. STANDING RULES (ratified 2026-07-15/16)

- **LAYERING PRINCIPLE:** the handicap-record layer only ever sees raw gross adjusted at
  100% handicaps. Game-layer adjustments (off-lowest, allowances, plus zeroing, flighting)
  live downstream and NEVER feed back into caps or differentials. One-way flow — no game
  rule can contaminate a handicap.
- **RETROACTIVITY BOUNDARY:** no handicap-layer change may alter RESULTS for any event
  before a9.18 Forest Creek / s9.18 Cedar Creek. GG is bible for results through those
  events. Every future methodology change (0.96, ladder, plus rules) applies forward and
  must prove result-neutrality backward before deployment.
- **SNAPSHOT RULE:** the playing handicap used in competition is WRITTEN to the round record
  at event time and never recomputed. Indexes move; results don't. (H-2 makes this explicit
  in code.)

## 6. PROVENANCE NOTES (why history looks the way it does)

- **Handicap Server era:** 9-hole exports carried true adjusted gross; 18-hole events were
  manually split without adjusted gross ("tainted"); HS's exports were **nine-blind** —
  back-nine rounds got front-nine slope/rating (177 rounds, Star Ranch confirmed).
  Tracker's per-round tee capture is the correction of record.
- **Tracker recordation era (2026):** initially uncapped; WHS NDB capping ratified
  2026-07-14 and applied retroactively — differentials only, results untouched (boundary).
- 1,165 eighteen-hole legacy rounds remain quarantined from parity validation — future plan needed.

## 7. WEBSITE COPY DELTAS (thegolffellowship.com/tgf-handicaps-1 — rewrite from this doc)

1. REMOVE "same as WHS except 9-hole differentials" absolutism → point to the register (§4).
2. ADD the 12-month window (Deviation 2).
3. PULL or rewrite the plus-÷2 paragraph after the O1 ruling (currently describes an
   unpracticed rule).
4. UPDATE "posted to GHIN and Handicap Server" — HS is retired; TGF Handicaps live in the
   TGF Tracker (member view: /member/handicaps).
5. The 0.96 removal needs no copy (it makes the site's WHS claim MORE true).
6. Differential table image: regenerate after the O5 ladder ruling.

## 8. VERSION PLAN

- **v1.0 (this):** ratified state as of 2026-07-16.
- **v1.1:** fold I-2 (0.96 applied), I-1 index-parity verdict, I-5 tee-par position.
- **v1.2:** fold O1 (plus), O3 (ESR/PCC/caps), O4 (intake + 75% implementation),
  O5 (ladder) as those sessions rule.
- Every change to this doc = archive prior version per protocol; every methodology change
  rides the Retroactivity Boundary.

*Cross-refs: mailbox #195–#197 · claude_TGF_Handicap_Decisions_2026-07-15.md ·
claude_TGF_Scoring_GoLive_Checklist_v1_0.md · Tracker handicaps.md / handicap-projection.md*
