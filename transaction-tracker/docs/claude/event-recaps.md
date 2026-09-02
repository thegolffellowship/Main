# Event Recaps — House Style (Kerry-taught, 2026-09-02)

News-reporter recaps of TGF events, written for the chapter's GG roster
email blast. First one shipped for s9.21 Canyon Springs; Kerry refined
the rules live. This is the voice and rulebook of record.

## Editorial rules (Kerry, verbatim-derived)

1. **Evaluate every number comparatively against the season before
   printing it.** Highlight what is impressive FOR TGF; stay silent on
   what isn't. Never spotlight a small field ("twenty players teed it
   up" — cut) or small dollar amounts. "I'm a little embarrassed to
   highlight the smaller attendance and smaller $ amounts."
2. **Dollars: MVP money only, plus the percentage angle.** The MVP
   sweep is "always going to be a big number" — print it (e.g.
   "Rideout's $124 night"). Individual game payouts ($16.50 seconds,
   $20 CTPs, $30 skins) never get printed. Instead sell the SPREAD:
   "half the field went home with money — ten different players
   cashed." TGF pays out a high percentage; that's the story.
3. **Score format for NET contests: `Gross / Net (± to par)`** —
   e.g. "49 / 34 net (−2)". Pull gross/net/playing_handicap from
   scoring_rounds (par from the scorecard detail; SA 9-hole courses
   are usually par 36 but VERIFY per course).
4. **Great golf gets celebrated regardless of buy-in.** Luke Mazanec
   didn't buy the games but had the round of the night (eagle run) —
   he's a headline anyway. Verify streak claims hole-by-hole from
   `get_scorecard_detail` before printing them.
5. **The buy-in nudge rides inside the humor, never as a pitch.**
   Kerry, on "a par bought $30.33 — play the games, people" and the
   trailing buy-in lines: "I definitely love your little jab and
   nudge... Little notices like that will go a long way." One or two
   per recap, attached to a real moment, never a standalone ad.
6. **New members and guests get highlighted** — especially conversion
   stories ("Justin Angelone played Tuesday and joined as a member
   before the week was out"). Name the convert; give other first-timers
   a collective welcome unless Kerry wants them named.
7. **Close with the fellowship**, not the golf: where the group ended
   up (Aldaco's after s9.21 — "where the real leaderboard gets
   settled"), then the next-event teaser ("Up next: s9.22 at
   Silverhorn. See you Tuesday.").
8. **Standings paragraph**: the chapter's live race (Fall Points during
   fall), top 3–4 names with points, the format reminder (best 6 +
   Fall Championship, Oct 31 at Kissing Tree), and the it's-still-early
   invitation. Monthly Points gets a one-liner (every member is in,
   no buy-in).

## Data sources (all verified before writing)

- Winners + GG-posted purses: `scoring-gg-results:<event>` /
  `scoring-payouts-inspect:<event>` (bridge).
- Scores: `get_scoring_rounds` filtered by event (gross, net,
  playing_handicap, tee); par + hole results via
  `get_scorecard_detail`.
- Standings: the fall/city points-race API or GG widgets.
- "% cashed": distinct golfers across the event's payout rows ÷ field.
- Never print a claim the cards can't back; anything from Kerry's
  memory (e.g. "his best TGF round") is fine to use but flag it back
  to him once.

## Cautions

- People who were refunded/removed from a race (e.g. non-member fall
  buy-ins) must not appear in race framing.
- Quiet on WDs and medical situations unless Kerry says otherwise.
- The recap goes out under Kerry's name to real members — when unsure
  whether a detail flatters or embarrasses, ask or omit.

9. **Get the season arc right before framing (Kerry 2026-09-02, second
   correction on the s9.21 draft).** Count actual EVENTS, never GG's
   "tournaments" column — an 18-hole event posts as TWO GG point
   rounds, so "tournaments: 3" after the Fall Kickoff + one Tuesday is
   really event #2. Match the narrative energy to where the season
   truly stands: early season = "the race is on / leaders emerge",
   never "the race tightens / chased down"; late season inverts.
   Anchor the timeline in the lede ("three days after the Kickoff,
   the fall's first Tuesday night...").

10. **Every buy-in or event mention carries its store LINK** (Kerry
    2026-09-02): season contests →
    https://thegolffellowship.com/shop/ols/products/season-contests ;
    events use their product URL (pattern:
    /shop/ols/products/<code-with-dashes>, e.g. s9-22-silverhorn,
    a18-5-forest-creek). A nudge without a link is a wasted nudge.
11. **The closer promotes the road ahead, both chapters**: next
    same-chapter event (linked), plus the next 18s — including the
    OTHER chapter's ("join the Austin crew for a little road trip...").
12. **Accuracy guardrails**: never call the Blues "the tips" (a longer
    set exists that's outside the under-50 parameters); a scratch
    player's gross IS their net — describe it that way (37/37 (+1),
    "all gross, no strokes"); "doubled up" style claims must carry the
    combined dollar total (Mary Wade's $46.83 night); introduce guests
    as guests on first mention.
13. **TGF MVP is a head-to-head — name the other city's MVP with their
    points and course** ("held off Austin's John Wade — 10 points at
    Star Ranch — 11 to 10"). Source: determine_tgf_mvp.
14. **Tone**: no "trash talk"; the fellowship close uses celebration /
    good vibes language. Fall race framing: "the baby brother of the
    summer City Net races — best 6 + Fall Championship instead of best
    10; more of a sprint than a marathon."

## Sent template of record (Kerry's final s9.21 send, 2026-09-02)

Kerry's shipped version added structure to keep in every draft:
- **Subject**: `TGF Results | <WINNER-SURNAME CAPS> <verb phrase>` —
  e.g. "TGF Results | RIDEOUT Sweeps the First Tuesday Night at the
  Springs!"
- **Section order**: lede/results grafs → **FULL EVENT RESULTS**
  (button/link to GG results) → Fall Points Race graf with BUY IN HERE
  link → **CURRENT STANDINGS** (button/link) → September/monthly points
  one-liner → **Hole-in-One pot teaser** ("BTW... Our HOLE-IN-ONE Pot
  is reaching monumental heights at $X,XXX!!!" — pull the CURRENT
  accrued pot value fresh each time; it's a cross-event accruing pot)
  → NEW FACES → fellowship close → UP NEXT (linked, both chapters) →
  signature block (Kerry Niester / The Golf Fellowship / 210.838.3948).
- Draft with placeholders for the FULL EVENT RESULTS / CURRENT
  STANDINGS links (Kerry wires the GG URLs in his email tool).
