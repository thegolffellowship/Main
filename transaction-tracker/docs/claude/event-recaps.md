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

15. **Never infer a player's gender from their name** (Kerry 2026-09-02:
    "Kelly Barna is a guy"). Verify from the customers row (`gender`)
    or write around the pronoun. A wrong pronoun in a roster email is
    worse than no pronoun.
16. **Lead with titles when a member headlines the standings** —
    "Austin Manager and now two-time Players Cup Champion Robert
    Straiton has the early lead..." Chapter managers, cup champions,
    city champions / LSC captains all get their billing.
17. **Date sanity**: cross-check every event date against the Tracker
    calendar (list_events) — Kerry noted he'd been typing Oct for
    September; the draft is the backstop.

## Public (Brevo) variant — v2 in Brevo (#14), CA/Kerry-ratified 2026-09-02 (mailbox #381)

Kerry: a version "more towards the public rather than membership...
putting the carrot out there to get people to try it out." Drafted
directly in Brevo as campaign **#13** (DRAFT — Kerry sends), list 3
"TGF CONTACTS" (~1,316; ~1,200 delivered, 45–61% opens historically),
sender id 1 kerry@. CA consulted via mailbox #380 (topic
`platform-public-recap`) on joint-vs-per-city, the money hook, brand
guardrails, and cadence — fold its reply in before v2.

Working rules (v1):
- ONE joint email for both cities, ~40% the length of the member recap,
  two CTAs (SA / Austin next Tuesday, linked) + Saturday 18s + calendar.
- Lead with the human carrot, not the leaderboard: first-timer cashes
  in his first round; guest joins on the spot; a PAR won money in both
  cities; "half the field / nearly two-thirds went home with money".
- No member vocabulary (Fall Points Race, MVP, Best-6) without a
  translating clause — mostly cut. Echo the proven kickoff voice:
  "Connect. Compete. Celebrate." / "Your Golf Crew. Zero Hassle." /
  "New to TGF? Show up, play, and see what everyone's talking about."
- NO dollar prices (tgf-pricing rule: figures only from the master
  document) — say "first-timers get a discounted rate" and link.
- Brand tokens from the best-performing sent campaign (#10): logo
  img 69986bc3ae141cb2ac450cf1.png on #1b1b1b, TGF orange #e2773d
  pill buttons (radius 25px, white text), light bg #eff2f7, SA slate
  #d3dde4, Arial, {{ contact.FIRSTNAME }} greeting, {{ unsubscribe }}
  + {{ update_profile }} in the footer.
- Brevo MCP can CREATE draft campaigns (htmlContent inline) but has no
  campaign test-send tool — Kerry previews/tests in the Brevo UI.

**Ratified by Kerry via CA (#381) — supersedes the v1 working rules where they differ:**
- JOINT email (agreed). WEEKLY through Oct 31, biweekly off-season.
  Fatigue defense = brevity: ≤2-min read, one story box, one CTA block;
  watch unsubscribes (<0.5%/send is fine).
- Money is PROOF, not the promise: headline = belonging/fairness ("You
  don't have to be the best golfer out here to get paid"); "% cashed" is
  one proof line inside the story box; never "come get paid/yours".
- Guardrails: never "league" as self-description (golf club/community);
  POT not purse; count seasons; no TGF Plus; no DFW/Houston.
- Names in PUBLIC sends: guests/new members = first name + last
  initial (Kannon B., Justin A.).
- Offer, verbatim, same as ad/text/welcome email: "$25 off your first
  event, plus a drink on us."
- Signature: Founder (not Co-Founder). Buttons: two lines — CHAPTER /
  course · date. Calendar = two links (SA / Austin GG schedule pages).
  Saturday 18s as a bold lead-in + list. Celebrate block: "It's the best
  part, and it's yours if you want it" (never "not optional").
- Close box: jump-in-anytime + à la carte (no mandatory events, games,
  or contests) + "See what our 150+ members are talking about."
- Fixed 5-block template: story headline → 3-beat highlight box →
  EVERGREEN Connect/Compete/Celebrate (static) → Try a Tuesday CTAs
  (auto from next events) → close box.
- SEGMENTATION: send to everyone EXCEPT active members (they get the
  GG recap); alumni ride in the general send (alumni variant = v2
  experiment). BUILD (Kerry-assigned): Brevo attribute TGF_MEMBER_STATUS
  {active_member, former_member, prospect} pushed nightly from
  derive_member_financial_status via Brevo API; "Active members"
  segment excluded from the public campaign. First Tracker→Brevo API
  brick (HubSpot decommission path). Gated on BREVO_API_KEY env.
- PROCESS (ratified): Wednesday AM auto-draft from Tracker data into
  Brevo as DRAFT + ping Kerry; he approves/edits on phone; sends
  Wednesday afternoon. Kerry's weekly effort target: 5 minutes.
- Brevo API has no campaign update/delete — revisions are new drafts;
  superseded drafts are deleted in the UI.

**v3 fixes (Kerry, off the Brevo preview 2026-09-02) — template rules:**
- The Season-20 logo (69986bc3…png) is BLACK INK — header band must be
  WHITE (with a dark rule under it), never #1b1b1b (v2 rendered black
  on black).
- One body size everywhere: 16px / line-height 1.55 / #1b1b1b for every
  paragraph, list, and close-box line (v2 drifted 15→17px around the
  Try-a-Tuesday block). Only the eyebrow (12px) and footer (12px) differ.
- Connect line reads "You sign up, show up, and play with a group
  that's rooting for you."
- HOLE-IN-ONE block belongs in the public template too (Kerry): a dark
  callout after the story box — what it is (every entrant kicks in $1
  per 9 / $2 per 18, accrues until won, a MEMBER who jars one at a TGF
  event takes it all; guests pay in but can't win — say "a member")
  + where it stands (live pot value; $3,295 on 9/2/26).
- Campaign lineage: #13 (v1) → #14 (v2) → #15 (v3). Brevo API has no
  update/delete; Kerry deletes superseded drafts in the UI.

**Tracker→Brevo sync — setup Kerry performs:** Brevo → profile menu →
SMTP & API → "API Keys" tab → Generate a new API key, name it
"TGF Tracker" → copy it once → Railway → tgf-tracker service →
Variables → add BREVO_API_KEY → Deploy. Code ships idle-until-set.

**TEMPLATE OF RECORD (Kerry's final edit of v3, 2026-09-02):**
`docs/claude/templates/public-recap-template.html` — his sent
structure with `{{PLACEHOLDER}}` slots for the Wednesday auto-draft
(EYEBROW, HEADLINE, LEDE, BEAT_1..3 lead/body, HIO_POT, CELEBRATE_PROOF,
SA/AUS next-event URL+label, SATURDAY_18_ITEMS, CLOSE_LEAD). Kerry's
changes over my v3, now standard: no rule under the white-bg logo; the
HOLE-IN-ONE block is a big centered orange "Hole-In-One Pot = $X,XXX"
(36px) over the one-paragraph explainer ("...11 have won over our 20
years. Join and you could be next!"); Saturday 18s each LINKED with
city + date bolded (Cedar Creek confirmed the URL pattern:
/shop/ols/products/s18-11-cedar-creek); no course-condition asides.
Brevo's editor wraps merge fields in `rte-personalized-node` spans —
that's its own representation, not something to paste as raw HTML.

18. **Every event named in the lede links to its GG RESULTS page**
    (Kerry 2026-09-02: "Realized we didn't have any event results
    links!!!") — orange bold "RESULTS" in parentheses after the
    bolded event, e.g. "<b>San Antonio at Canyon Springs</b> (RESULTS)".
    URL shape: SA `tgf-sa.golfgenius.com/pages/5783307?round_id=<id>`,
    Austin `tgf-austin.golfgenius.com/pages/5790752?round_id=<id>`;
    the id is the GG LEAGUE ROUND id (what the tournament_results
    widget's round selector uses and gg_game_results_rounds records),
    not the tournament id on scoring_rounds. Applies to the member GG
    recaps too (the FULL EVENT RESULTS button). "Lede" = the opening
    paragraph under the headline (newsroom spelling).
