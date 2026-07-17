# Match Play — Items Uncovered for CA (2026-07-17)

**From:** tracker-claude · **For:** CA (overall Match Play documentation, purchase → conclusion)
**Trigger:** live GG-source audit of the 2026 Austin + San Antonio match-play games
(`cmp_import_gg_match_play` reading GG's own computed match state as the source of truth).

These are the mechanics we surfaced that affect **setup, recordation, and determining
winners** and belong in the end-to-end Match Play spec. Several are **Tracker gaps** (not
modeled yet). None of this changes any **frozen** result, record, qualifier, or seed —
reconciliation aligns *display detail* to the recorded winner, never the reverse.

## Design north star (applies to everything below)

**Simplicity for MANY chapters and SCALING.** The spec must scale cleanly to many
chapters (national), so favor **one rule over per-chapter special cases**, and **derive,
don't ask** (rules-based defaults; manager/player screens compute, not collect). Minimize
manual input and per-chapter divergence at every stage. The **future uniform, adjustable
allowance** (one % for all chapters, replacing the historical SA-75/Austin-100 split, A2)
is the model: collapse historical per-chapter divergence into a single configurable rule.
Every decision point (eligibility gate, tie-resolution flow, extra-hole/putt-off
recordation, display) should be as simple and self-serve as possible so a new chapter
needs near-zero bespoke setup.

**Format history (context for CA).** Match Play has been the hardest contest to run —
years of hair-pulling. An earlier **double-elimination** format (playback to the
championship even after one loss, à la NCAA wrestling) was used; it produces **more
matches** than the current World-Cup-style pools→knockout, which compounds the
participation/scheduling load. Format choice trades competitive fairness against match
volume and manageability — weigh against the simplicity/scaling north star and the
participation layer above.

---

## PARTICIPATION & COMMUNICATION (cross-cutting — a whole layer for CA)

Match Play inherently demands **more participation** than stroke events, so a player who
goes quiet for a few weeks is a real problem for the whole pool/bracket. This layer needs
its own guidance and automated comms:

- **Completion deadlines.** Each match / round must be **completed by a date X**; the app
  should communicate the deadline, send reminders, and escalate as X approaches.
- **Disqualification for non-participation.** Define the **boundary** at which a
  non-participating player is DQ'd (missed matches, past-deadline, N weeks idle), what
  happens to their opponent(s) and the standings/bracket (walkover? forfeit recorded
  how?), and whether/how it's appealable.
- **Matches outside TGF events (self-scheduled makeups).** Players must be able to play a
  match **on their own, away from a TGF event**, and record it — how it's scheduled,
  verified, and entered (ties to recordation: event-independent, pair-keyed).
- **Automated participant communication.** Reminders, nudges, deadline warnings, "your
  match vs X must be played by [date]", makeup-scheduling prompts, DQ warnings — driven by
  match state so managers don't chase people manually (scaling north star).

## 0. REGISTRATION / ELIGIBILITY / PREREQUISITES

0a. **Registration timing.** When enrollment opens/closes relative to the season and the
    pool/bracket build — and what happens to late signups. *(We have some of this; CA to
    make it explicit end-to-end.)*
0b. **Eligibility gate — established handicap (NEW rule to specify).** A player **without
    an established handicap** should be **held out of Match Play until they have X
    qualifying rounds**. Needs: the value of **X**, what counts as a qualifying round,
    whether it's a hard block at signup vs. a flag, and how it interacts with the paid
    enrollment (refund/hold/defer). This gates who may be pooled and seeded.
0c. **Other prerequisites to confirm:** membership status, chapter, prior-participation
    or good-standing requirements, and any per-season cap.

## A. SETUP / STRUCTURE

1. **Handicap allowance is OFF LOWEST.** The lower course handicap is subtracted from
   both players → the lower handicapper plays scratch; the higher receives the (rounded)
   difference, allocated on the hardest holes by stroke index. Equal handicaps play
   straight up.
2. **Allowance % — historical vs future:**
   - **Historical (GG-run) events:** per chapter — **San Antonio 75%**, **Austin 100%**.
   - **Future (Tracker-run) events:** **ONE uniform, adjustable** allowance across all
     chapters — default **75%**, settable (e.g. 90%, 100%). Single config value, not
     per-chapter. *(Design intent ratified; durable config key pending ship-approval.)*
3. **NET matches.** net = gross − off-lowest strokes; per-hole handicap **stroke dots**
   must be recorded and displayed.
4. **Starting hole (shotgun).** Matches begin on different holes (e.g. Niester/Wade on
   **5**; a9.17 matches on **10**, the back nine). The starting hole is match data and
   drives both winner determination and display.
5. **Which holes.** 9 holes on either nine, or 18 — course + tees + **stroke index**
   needed to place off-lowest strokes on the correct holes.

## B. RECORDATION

6. **Matches span events / are made up on other dates.** A match may be played at a
   **different event** than its home/pool event (Hogue/Kirksey is recorded on **a9.12**
   in our data but GG scored it under **a9.17**). Recordation must NOT tie a match to a
   single event; a match is a unique **pool pairing** regardless of when/where played.
7. **Extra holes / sudden death — GAP (not modeled).** A match all-square after
   regulation goes to extra hole(s); the winner takes the next hole. Confirmed cases:
   **Youngs v Marques** and **Barna v Cloer** were AS after 9, decided on the first extra
   hole. We have no extra-hole entity and no extra-hole score.
   - **Notation (Ryder Cup, Kerry-confirmed):** an extra-hole result is written as the
     **number of holes PLAYED + "H"** — a 9-hole match decided on the first extra hole =
     10 holes played = **`10H`**. The number is holes *played*, NOT the physical hole
     number (matters for shotgun starts: a match that began on hole 5 and went one extra
     also reads `10H`, played on physical hole 5). These two are currently stored as
     **`1 UP`**, which reads like a *regulation* 1-up and hides the extra-hole fact —
     `10H` carries the real information. (Correcting the two historical margins is Kerry's
     call; winner/record/seed untouched either way.)
   - **Feature needed (recordation):** in an extra-holes situation the app must provide
     **score entry for the extra hole(s) that ALSO configures the handicap pops** —
     continuing the off-lowest stroke allocation onto the extra holes by stroke index so
     **net** decides the hole. Not just a "who won" toggle: enter the strokes, apply the
     correct pops, compute net, determine the winner, and record the result as `NH`.
8. **Putt-offs — GAP.** Another all-square resolution class (Chandler/Peterson s9.12,
   Niester/Wade s9.15). Needs a recordation path + display.
9. **Concessions / gimmes.** GG's match state reflects conceded holes/putts that raw
   gross does not show — so hole-by-hole detail (and margin) must come from the **actual
   match**, not a re-derivation from gross.
10. **Per-hole detail source.** Starting hole, per-hole winner (W/L/H), per-hole gross +
    strokes, and margin are read from **GG (the audit source)** until Tracker-native
    live match scoring exists.

## C. DETERMINING WINNERS

11. **Play-order close-out.** Winner/margin ("X up with Y to play", X&Y) are computed in
    **play order from the starting hole**, not hole-number order.
12. **All-square resolution ladder — for CA.** Canonical order (extra holes → putt-off →
    …?) and exactly how each is recorded and shown is unspecified.
12a. **Tie-resolution DECISION FLOW at end of regulation (ultimate-app requirement).**
     When a match is All Square after the regulation holes, the app must present
     **stage-aware guidance/options** — derived from the match's stage (rules-based, not
     asked blindly):
     - **Pool round (or any stage where a tie is allowed):** offer **"End in a tie /
       Halved"** as a valid outcome (counts as a halve — ½ point each under D-MP-09).
     - **Knockout / any must-produce-a-winner stage:** a tie is NOT allowed → prompt
       **"How do you want to determine the match?"** → **Putt-Off** or **Extra Holes**.
     - **Practical constraints surfaced in the prompt:** e.g. *"It has to be completed
       tonight"* — daylight/time/pace, group availability, course access — nudging toward
       the feasible method (a putt-off is faster than extra holes).
     - The chosen method + its result feed **recordation** (B7 extra holes / B8 putt-off)
       and the **display** (D16/D17), and produce the winner (or the recorded tie).
     - This is the interactive front end to the all-square ladder (item 12) — the app
       guides players/manager through the decision at the moment of the tie.
13. **Off-lowest pops feed net → hole winner** (see A1–A3), at the event's allowance.
14. **GG is the audit source.** Our own computation must reconcile to GG; where they
    differ it is a concession/putt-off/extra-hole the gross can't show — surfaced, not
    applied. **Frozen results never change.**

## D. CONCLUSION / DISPLAY / DOWNSTREAM

15. **Frozen forever:** winners, W-L-T records, knockout qualifiers, and seeding never
    change from any reconciliation.
16. **Member scorecard + dots** render in **play order from the starting hole** (wrapping,
    e.g. 5→9→1→4), with **NET stroke dots**, and must never contradict the recorded
    winner.
17. **Playoff-decided display — for CA.** For a match AS in regulation but decided by an
    extra hole / putt-off: show regulation as-is (all square) plus a **"decided in a
    playoff → [winner]"** note? (Kerry's call — captured as an open question.)
18. **Downstream** (standings, knockout seeding, payouts) derive from the recorded
    winners — unchanged.

---

## Lifecycle framing ("purchase → conclusion")

purchase/enrollment → pool assignment → pairing & **setup** (allowance, starting hole,
tees, off-lowest strokes) → play → **recordation** (regulation + extra-hole/putt-off) →
**winner determination** (play-order close-out; all-square ladder) → standings & knockout
seeding → payouts → **member display** (dots + expandable scorecard from the starting
hole).

## Tracker status (so CA knows what's already built vs. gaps)

**Built & validated this session (display-only, frozen results untouched):**
- Off-lowest, per-chapter allowance reconciler (`cmp_reconcile_match_play_75`).
- GG-source importer (`cmp_import_gg_match_play` + `gg_match_play.py`): reads starting
  hole, per-hole NET winner/strokes/gross, margin; aligns by pool pair across the chapter;
  snapshots to `cmp_matches.gg_match_detail`; reports GG-vs-recorded.

**Open gaps needing CA/spec + Kerry ratification:**
- Extra-hole (sudden-death) model + recordation + display.
- Putt-off recordation + display.
- All-square resolution ladder (canonical order).
- Future uniform-allowance config key (default 75%, adjustable).
- Playoff-decided member-display treatment (open question #17).
