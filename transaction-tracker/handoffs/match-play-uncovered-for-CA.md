# Match Play — Items Uncovered for CA (2026-07-17)

**From:** tracker-claude · **For:** CA (overall Match Play documentation, purchase → conclusion)
**Trigger:** live GG-source audit of the 2026 Austin + San Antonio match-play games
(`cmp_import_gg_match_play` reading GG's own computed match state as the source of truth).

These are the mechanics we surfaced that affect **setup, recordation, and determining
winners** and belong in the end-to-end Match Play spec. Several are **Tracker gaps** (not
modeled yet). None of this changes any **frozen** result, record, qualifier, or seed —
reconciliation aligns *display detail* to the recorded winner, never the reverse.

---

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
   **Youngs v Marques** and **Barna v Cloer** were AS after 9, both played **hole 10**,
   decided there. We have no extra-hole entity and no extra-hole score. Needs: record
   winner + hole(s) played + result, distinct from regulation.
   - **Notation (proposed, for CA to ratify):** an extra-hole win is recorded as the
     hole it ended on — e.g. **`10H`** (won on the 10th; H = hole), the 18-hole analog
     being the "19th hole." These two are currently stored as **`1 UP`**, which is
     technically true at the moment of victory but reads like a *regulation* 1-up and
     hides the sudden-death fact — `10H` carries the real information. (Correcting the
     two historical margins is Kerry's call; winner/record/seed are untouched either
     way.)
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
