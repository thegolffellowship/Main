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

## Lessons from the s9.22 send (Kerry's edit of the draft, 2026-09-10: "Learn from it")

Kerry kept the two-week Rideout trend, the head-to-head, the Baker and
South comparisons and the skins paragraph. What he changed is the rulebook:

20. **Humor is never at a member's expense.** Cut: "Enjoy it while it
    lasts, Jeff" (a jab at a falling handicap) → "Enjoy your success,
    Jeff! Well done!" Cut: "Daniel, the games are right there at
    checkout. We are begging you" → "He would be taking all our money if
    he bought into games, so thank you, Dan!" The nudge rides as
    gratitude or a wink, never as pressure on a named person.
21. **Member businesses get a plug when the hook is natural.** Kerry
    added "could it be his new membership at Jeff Young's MAVN Golf???"
    (linked). That is knowledge only he has; the draft should leave room
    for it, and when a member-owned business is on record it can be
    offered as an option.
22. **Every proper noun that has a page gets its link**: the OTHER
    chapter's course in the head-to-head → its GG results page;
    "HANDICAPS" → the member portal handicaps page; CURRENT STANDINGS →
    the Tracker member contests page (`/member/contests#race=fall_sa`,
    `#race=monthly`), not GG. Buttons became inline links.
23. **Explain the mechanic in one line wherever a race is named.** Fall:
    "Your points are being tallied, just activate them by BUYING IN.
    Green highlighted in the standings means you're already in."
    Monthly: "Winner takes all. $1 / TGF Member count at end of each
    month." Team Net: give the team score "at 30 (−6)".
24. **First-timer = first TGF round ever, regardless of what they
    bought.** Michele McCormick (member purchase + first round) is a
    first-timer AND a new member. The sent list: four first-timers, "3 of
    them went home with money", as bullets with surnames in CAPS for the
    two who joined ("Michele McCORMICK - New Member!"), plain for the
    others (events.md § Surname Uppercase for Elevated Roles). A member
    on their second Tuesday (Will Wallace) is not "new faces".
25. **Acquisition is a story.** "All 4 found out about us through our
    recent Ad Campaign on Facebook & Instagram!" `customers.
    acquisition_source` (facebook_lead) is on record for every one of
    them — pull it for the NEW FACES block next time.
26. **Fellowship reports who CAME, not who said yes** — "9 of us landed
    at Max & Louie's" (13 said yes). The headcount is Kerry's to give
    until it is recorded somewhere (skill OPEN 4); the draft carries the
    YES count as a placeholder, flagged.
27. **UP NEXT is a chronological list across BOTH chapters**, each line
    `Day | tee times or shotgun time | COURSE (nine side) | REGISTER
    link`, with sub-bullets for the pitch ("Feeling a road trip? This
    Round Rock course is sweet!"), the points reassurance ("Yes, you'll
    gain points by playing") and the **registration deadline** ("Deadline
    is 8pm tonight"). Store URLs come from `events.registration_url`, not
    from a hand-built slug — the Quarry's is `s9-23-quarry`, not
    `s9-23-the-quarry`.
28. **Greeting + merge tag**: "Good Morning, %first_name%!" (GG's merge
    syntax). Section heads in CAPS with a period, no bold: "FALL POINTS
    RACE.", "NEW FACES.", "FELLOWSHIP.", "UP NEXT." Sign-off "See you
    soon!" when the next event is not a Tuesday.
29. **Trim the framing when the facts already carry it.** Cut: "more of a
    sprint than a marathon", "where the real leaderboard gets settled",
    the second new-member paragraph. Kept: "It is early. It is very
    early." Draft leaner; let Kerry add.

## Lessons from the s9.23 send (Kerry's edit of the Word draft, 2026-09-16)

Kerry kept the lede, the ten-shot trend, the head-to-head, the skins
paragraph's facts, the Team Net line, the fall-race top four, the New
Faces bullets and every link. What he changed:

30. **Members' surnames in CAPS and bold on first mention, in the body
    too** — not only in the New Faces block: Adam BAKER, Luke YOUNGS,
    Mary WADE, Pat YOUNGS, Jeff YOUNG, Larry ANTHIS, Rob BURLINGAME, Jesse
    SALDANA, Daniel SOUTH, Luke MAZANEC, Jeff RIDEOUT. Non-members stay
    plain (Justin Guerrero, Joe Mejia). Key phrases bold: "A $156 night",
    "TGF MVP head-to-head over…", "Justin's first TGF round, and he left
    with money", "HOLE-IN-ONE Pot stands at $3,384". (Richard Palacios,
    a member, was left plain — flagged back to Kerry as a likely miss.)
31. **Cut the handicap mechanics from the prose.** Gone: "playing plus-3
    (so his net was 36 — all gross, giving strokes back)" and "with no
    strokes at all". The score line is enough; the reader does not need
    the arithmetic.
32. **Genderless collectives.** "two men at 33" → "two at 33" (rule 15
    extended: do not assume gender of a group either).
33. **The skins nudge is an invitation, not a jab.** Cut: "In our skins
    game every hole is its own contest. Play the games, people." →
    "Every hole is an opportunity to win in Skins, and with
    pre-handicapped flights of <12.0 and 12.0+, everyone has a chance!"
    — explain the flight mechanic, never scold.
34. **Never name who has NOT bought in.** Cut from the fall-race graf:
    "Dan Stich sits fifth at 32 and Jeff Young is tied sixth at 25 — both
    without a buy-in, so those points are waiting on them." Only enrolled
    leaders are named; the BUY IN link carries the nudge (rule 20, hard).
35. **Fellowship without a headcount is fine**: "A number of the players
    stuck around in the clubhouse for food & drinks and good banter."
    Draft that shape when the count is unknown; do not leave a blank.
36. **UP NEXT line shape**: `This Sat, Sep 19 | 8:10-9:00a Tee Times |
    CEDAR CREEK (18) | REGISTER — yes, you gain fall points by playing.
    Deadline tomorrow at NOON.` (deadline in red); Tuesdays as
    `Tue, Sep 22 | 5:00p Shot | BRACKENRIDGE PARK | REGISTER`. "Shot" is
    the shotgun shorthand; the nine side is NOT printed. SAN ANTONIO
    Tuesday nines are 5:00 PM shotguns as a rule — draft that, not a
    blank. AUSTIN varies (Teravista 9/22 = 4:40 PM tee times, ShadowGlen
    9/29 = 5:00 PM): read the event, never assume.
37. **Draft error, caught by Kerry on his final pass — ours to catch
    next time.** The lede said "Two weeks ago at Silverhorn"; s9.22
    Silverhorn was 2026-09-08, ONE week before. Every relative date in a
    draft gets checked against `round_date` (rule 17, now including
    "weeks ago"). Same pass: PALACIOS went to caps (rule 30 holds for
    every member), and the monthly one-liner gained the current leader
    ("Luke YOUNGS from Austin is the current leader.") — name the
    monthly leader when the cache includes last night's rounds.

38. **Name the team game's FORMAT with a one-line explainer** (Kerry's
    last edit, s9.23): "Team Net was Best 2 Balls (cumulative of best two
    net scores per hole) went to … at 61". The format is in
    `scoring-gg-results` (the TEAM Net board's setup) and the allowance
    ladder in side-games.md (1 ball 75%, 2 ball 85%, 3–4 ball 100%);
    print the format, not the percentage. Extends rule 23.

## Austin — what Robert sent for a9.23 (2026-09-16, from the closeout draft)

Kerry: "Most of my edits would be how I'd want to dictate future recaps,
but certainly want to capture anything useful or insightful from him."
Robert Straiton sent the Austin draft under HIS name and phone
(361-389-9395), "See you Tuesday!", with the GG results PDF attached
(26-a9-23-RESULTS.pdf). What he changed and what it teaches:

39. **The chapter manager sends the chapter's recap under his own name**
    (skill OPEN 2, answered in practice for Austin). Draft Austin's with
    Robert's signature block, not Kerry's.
40. **Fellowship line, Austin shape:** "5 of us had drinks and dinner at
    Mama Betty's Mexican Cantina." — headcount + spot, the rule-26 shape.
    The spot is now on the event (fellowship_spot) so the Insider's
    Celebrate line can use it.
41. **Austin UP NEXT carries the real tee time and the real deadline:**
    "Tue Sep 22 | 4:40 PM | TERAVISTA (9) | REGISTER — Deadline Mon Sep
    21 @ 3 PM." (he also prints "(9)" / "(18)" after the course). Those
    are facts only the manager had; the draft's blanks were right to be
    blanks. Capture them on the event when they arrive.
42. **Attach the GG results PDF** — Austin's practice; SA links FULL
    EVENT RESULTS instead. Either is fine; note the chapter's habit.
43. **He kept two things Kerry's rules cut, and one number moved.** (a)
    Surnames stayed plain (rule 30 is Kerry's dictation, not yet
    Robert's); (b) the fall-race graf still names Straiton and Cloer as
    "without a buy-in" (rule 34 says never name who has NOT bought in —
    he named himself, which softens it, but the rule stands for the
    draft); (c) "Luke Youngs shot 70" at Forest Creek — ROBERT WAS RIGHT.
    GG fixed a scoring error after our Saturday import (back nine 33 →
    32); the Tracker card said 71 until 2026-09-16 2:30 PM, when it was
    dropped, re-imported (70 / 67 net) and its two nines re-posted
    (index 0.9 → 0.1). The manager on the ground knows about a
    correction before the Tracker does; when a manager's number differs
    from ours, re-pull the card BEFORE calling it wrong.

**s9.24 Brackenridge, Kerry's send 2026-09-23 (draft vs sent; the SENT
text is the SA section of `recaps/2026-09-22-s9.24-brackenridge-a9.24-teravista.md`):**

44. **The greeting follows the SEND time**: "Good Afternoon, %first_name%!"
    when it goes out after noon. Draft "Good Morning" and flag it; do not
    assume a morning send.
45. **Every member named in a sentence gets the CAPS surname on first
    mention, including partners in a list** ("with Jeff YOUNG, Shahyan
    Javed and 'blind' partner Richard PALACIOS") — and **Kerry's own
    name is treated like everyone else's** (the draft left NIESTER
    un-bolded; he bolded it). The first-timer is the exception in the
    lede: plain there, CAPS in NEW FACES where he is the subject.
46. **A blind draw is written "blind" in quotes** — it is TGF's term of
    art, not a description of the player.
47. **Comparisons across chapters name the thing compared**: "three clear
    of Austin's best", not "three clear of Austin".
48. **Standings links go to the TRACKER board, deep-linked to the race**,
    not the GG portal page: SA fall `https://tgf-tracker.up.railway.app/contests#race=fall_sa`,
    Austin fall `…/contests#race=fall_austin`, the month `…/contests#race=monthly`.
    The link rides at the END of the race graf, inline.
49. **Fellowship with a real count and a real place**: "10 of the players
    headed over to The Cottage Irish Pub for good food, good drinks, and
    good banter. It's the best part, and it's yours if you want it." The
    count and the spot are Kerry's. The spot belongs in the event's
    `fellowship_spot` (set in Edit Event; the MCP event tool does not
    accept it, so it was NOT written for s9.24). Until the count has a
    home (skill OPEN 4), draft the lesson-35 shape and flag the count.
50. **UP NEXT, as sent**: the chapter's OWN lines carry the date and the
    course in **bold** (`**Tue, Sep 29** | 5:00p Shot | **CANYON SPRINGS** |
    REGISTER — Deadline Monday at 5pm.`); the other chapter's line bolds
    only the course. **THE TUESDAY DEADLINE IS MONDAY AT 5PM, BOTH
    CHAPTERS** (Kerry 2026-09-23: "Monday 5pm is the standing SA &
    Austin Deadline.") — print it on every Tuesday line of the
    chapter's own events; never a blank. Austin's tee window is printed as a range: "4:20-5:10p Tee
    Times". **A line with no live store page carries NO link at all**
    (Olympia Hills) rather than a dead one or a blank, and the Lone Star
    Cup line reads "San Antonio vs Austin. Qualifiers Only" — no
    register link, because members do not register for it.
51. **Sign-off: "See you Next Tuesday!"**

Draft-time checklist derived from the above: two-week trend table for
the headliner (previous event's card + payout), team score on Team Net,
acquisition source per first-timer, links for every proper noun, both
chapters' next three events with deadlines, and NO line a named member
could read as a dig.

## Sent template of record — s9.22 Silverhorn (Kerry's send, 2026-09-10)

`docs/claude/recaps/2026-09-08-s9.22-silverhorn.md` carries the SENT text
verbatim above the draft-vs-sent notes. It supersedes the s9.21 structure
below where they differ (inline links instead of buttons, bulleted NEW
FACES and UP NEXT, mechanic one-liners under each race).

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

**BUILT (v2.369.0, 2026-09-10, `email_parser/insider.py`) — how the
Wednesday auto-draft fills the template:**
- `gather_week()` — per chapter, the most recent event WITH SCORECARDS in
  the last 7 days (`scoring_rounds` joined to `events`); field = cards,
  cashed = distinct `tgf_payouts` recipients via `tgf_events.events_id`;
  first-timers = players whose first-ever scoring round is that date
  (cashed flag from the same payouts); skins story = a `gg_game_results`
  skins row whose detail reads "Bogey on 7" / "Par on 3" (bogey wins);
  fairness fallback = playing-handicap spread of the players who cashed;
  results link = chapter page + `?round_id=<gg_league_round_id>`; HIO
  pot from `get_hio_pot()["pot"]`; next Tuesday per chapter (first
  future `[sa]9.`, `registration_url` else `derive_store_url`, label
  "Course · Tue Sep 15"); Saturday 18s = future `[sa]18.` within 45 days,
  not cancelled, max 4.
- `compose()` — deterministic sentences into the 5-block slots. Headline
  follows the strongest beat — "First round. First payday." (a first-timer
  cashed) → the fraction as a title ("Half the Field Won Money!", Kerry's
  pick 2026-09-16, ranked above the skins story because he chose it over
  "A par won money") → "A bogey/par won money Tuesday" → the ratified
  default — **and never repeats last week's title** (`pick_headline`;
  `last_insider_headline` reads the previous draft ping in `message_log`).
  Kerry, week 3: "We copied the Brevo title from last week" — two Insiders
  in a row led "First round. First payday." because a first-timer cashed
  both weeks. Beat 1 is the fraction ("half the field", "a third of the
  field"), never dollars.
- `render()` strips the template's `<!-- example -->` author notes;
  Brevo merge tags (`{{ contact.FIRSTNAME }}`, `{{ unsubscribe }}`,
  `{{ update_profile }}`) stay.
- `lint()` is the gate: unfilled `{{SLOT}}`, banned words (league, purse,
  TGF Plus, DFW, Houston), any dollar figure other than the verbatim $25
  offer and the "Hole-In-One Pot = $X" line. `apply` refuses on any hit.
- Subject `TGF Insider | <headline>`; campaign name `TGF Insider <date>`;
  sender 1, list 3 minus segment 2, tag `public-recap`. Kerry gets the
  campaign link by email (Graph, COO_EMAIL_TO), logged to message_log as
  `insider-draft`. Skipped when no event has cards in the window.
- **2026-09-16 — dial set to `review`; the writer is its own lane.** Kerry:
  "I'm thinking you don't auto post to Brevo each week, but instead send me
  an email of what you suggest, that I can edit and approve. I want it to be
  creative though. I don't necessarily want the same format each time with
  the '3 things.'" and "yes, I am comfortable, ultimately, allowing an
  AI-written draft with options to choose from." Spun off as "Insider
  Writer: Angle Rotation + AI Draft" (branch claude/insider-writer-0e4788):
  angle rotation as a dial, a Claude-written draft with two alternate
  headlines, lint still gating, review email to Kerry, Brevo draft only from
  his approved text. Until it ships, Wednesday 8:00 emails the deterministic
  draft for review and creates NOTHING in Brevo.
- MODES (dial `insider_autodraft`). **draft** (DEFAULT — Kerry 2026-09-10:
  *"Update the dial to create the Brevo draft directly each wednesday at
  8am. I'll review it there because I can see all the visual with it too.
  And then I'll work with you for edits before sending so you can learn
  from it."*): Brevo DRAFT + link emailed to Kerry; edits go through the
  session lane (a Brevo campaign cannot be updated by API — a revision is
  a new draft, the old one deleted in the UI); nothing sends itself.
  **review** — renders the dry run, emails Kerry the Insider under a REVIEW
  banner, posts the beats to the mailbox (topic `insider-review`), nothing
  in Brevo. **off** — nothing. Env `INSIDER_AUTODRAFT=0` is off;
  `BREVO_SYNC_DISABLED=1` also unschedules it. Bridges
  `scoring-brevo-draft[:dry|review|apply]`.
- Kerry's standing review rule (2026-09-10): *"We always need to review and
  discuss the Insider mailings until I'm confident enough to automate it a
  little more."* Every auto-draft is discussed before he sends; what he
  changes goes into the lessons list below and, where it is a pattern,
  into `compose()`.

**THE WRITER (v2.463.0, 2026-09-16, `email_parser/insider_writer.py` — the
"Insider Writer" lane, branch `claude/insider-writer-0e4788`):**
- Kerry's brief, verbatim: *"I'm thinking you don't auto post to Brevo each
  week, but instead send me an email of what you suggest, that I can edit and
  approve. I want it to be creative though. I don't necessarily want the same
  format each time with the '3 things.' I think we need to be more diverse
  about it. We need to explore more of The Golf Fellowship and what it
  provides. So many avenues for potential."* and *"yes, I am comfortable,
  ultimately, allowing an AI-written draft with options to choose from. I
  would ultimately work back and forth with it to hone the message that can
  be committed to memory."*
- **Angle rotation as data.** `insider_writer.ANGLES` is the catalogue (ten
  angles: `tuesday-story`, `first-timer`, `fellowship`, `handicap-fair`,
  `saturday-18s`, `season-contests`, `hio-pot`, `twenty-seasons`,
  `course-of-week`, `member-words`); dial `insider_angles` (comma list of
  keys) is the ORDER; `insider_angle_force` names one angle for the next run
  (consumed once); `insider_angle_history` (JSON, written by the scheduled
  run only) keeps every angle from repeating until the rest have had a
  turn. An angle whose facts are missing this week is skipped, never faked
  (`first-timer` needs a first-timer, `saturday-18s` a Saturday 18 on the
  calendar, `member-words` a quote on the dial `insider_member_quote`).
  `handicap-fair` pins the skill band, `hio-pot` the pot band; every other
  angle keeps the weekly band rotation. Read-only view:
  `scoring-insider-angles`. **RATIFIED, Kerry 2026-09-17 ("Go with your order. Push to main. I don't
  really want to overthink this."):** `first-timer, fellowship, handicap-fair, tuesday-story,
  saturday-18s, hio-pot, season-contests, course-of-week, twenty-seasons, member-words` — set on the
  dial the same day; v2.463.0 on main. Rationale: ~70% of recipients have never bought (mailbox
  #543), so the angles that get a stranger to a first Tuesday lead, and the proof angles follow.
- **One Claude call a week** (`write_insider`; model dial `insider_model` /
  env `INSIDER_MODEL`, default the parser's Sonnet route; parser.py's client
  pattern; `ops_alerts.maybe_alert_anthropic_billing` on auth/credit
  failures). Fed: the angle brief, the public FACT SHEET from
  `gather_week()` (every name already first + initial; the links it may use;
  the surnames it must not print), `PUBLIC_RULES` (the #381 guardrails + the
  Insider lessons, and they WIN over the member-recap style), THIS file for
  voice and corrections, and `docs/claude/templates/insider-voice-examples.md`
  (Kerry's SENT texts — the voice memory; add to it only with text he sent
  or approved). It returns the headline PLUS two alternates, the lede, the
  story box as 1–4 beats (the shape varies — the "3 things" every week is
  what Kerry asked us to stop), the Celebrate line, the close-box header,
  and a one-line "why this angle this week".
- **The gate holds.** `validate()` whitelists tags, unwraps any link not on
  the allow-list, refuses a full surname from the week's roster, a banned
  word, a dollar figure other than the pot, "alone", and a headline that
  repeats a recent one; `lint()` runs on the rendered HTML. One retry with
  the problems fed back, then `compose()` (the deterministic draft) is the
  fallback and the review email says so — the 8:00 email always goes out.
  `insider_writer=off` turns the writer off; no `ANTHROPIC_API_KEY` = off.
- **Review email** (`send_review_preview`, the 8:00 Wednesday job in
  `review` mode): the orange box now carries the angle, why this angle, the
  three headline/subject options, and who wrote it; the mailbox post
  (topic `insider-review`) carries the same digest. `send_review_samples`
  puts SEVERAL angles in ONE email (`scoring-brevo-draft:samples|a,b,c`) —
  the "options to choose from" Kerry asked for.
- **Approval → Brevo.** Kerry edits in chat; the lane folds each edit into
  the lessons here AND the voice examples; then
  `scoring-insider-approve:<subject>|<html>` runs `lint()` on HIS html
  (merge tags must survive), creates the Brevo DRAFT from it, emails him
  the link, and logs `insider-approved` so the headline rotation sees the
  title. Nothing sends itself. `scoring-brevo-draft:apply` (the
  deterministic Brevo draft) stays as the legacy path.
- Bridges: `scoring-brevo-draft[:dry|review|apply|samples][|<angle>|<a,b,c>][|nowriter]`,
  `scoring-insider-angles`, `scoring-insider-approve`. Tests:
  `test_insider_writer.py` (mocked call; rotation, facts, validation,
  fallback, billing alert, review/samples/approve), `test_insider.py`
  unchanged and green.

**The mandate (Kerry 2026-09-17, verbatim, the lane's standing brief):** *"I need your help to get me as
close to SEND each week as possible. There needs to be evaluation of who's clicking what and any other
things you can think of too. You need to be my research assistant and also prompt me when you need more
information. I need you to help me make this thing grow. So putting content out there is important. I
think even tying in current events in the golf world or perhaps other stuff or encouragement or skies the
limit really. We want to build our committee and grow it. If you need to interview me to come up with a
direction fine, but I need you to take the bull by the horns and push the envelope so to say. I'm fine
with taking risks. I can coach you and teach you, but I also need you to push me and teach me."* Two
Routines carry it: Wednesday ~8:30 AM CDT (read the writer's draft, fix what is weak, bring Kerry to
"say go") and Friday ~1:30 PM CDT (the scorecard by group + one recommendation). Content beyond the
recap (golf-world items, encouragement) is welcome by ruling; it still goes through the writer's rules
and Kerry's approval, and the writer never invents a news item — facts come from a dial or the lane's
research.

**FAITH STAYS IMPLICIT — Kerry's founding stance for the public voice (2026-09-17, verbatim):**
*"I've always looked at The Golf Fellowship as preparing a field for people of any background to
come into connecting with other human beings we don't discriminate in anyway, and I certainly want
to continue that as a standard. The Golf Fellowship is about human connection and I believe that is
something we really need and we need more and more in a world that is becoming more and more
isolated even though we have more and more ways to connect than any other time in history, it's
easy to say I can just do life by myself because functionally we can. But emotionally is another
story altogether I believe that we were built for community… So while obviously I go to Mission
point and I've been a disciple of Christ for years and years, as well as that being the foundation
of my faith and what drives me to be loving and kind and encouraging and interested to, and in the
people that come into The Golf Fellowship, I also don't want that to be a stumbling block of any
kind. I want to take people where they are and [not] put a barrier of religiosity in between them
and myself or CHRIST for that matter."* → In the public Insider: no scripture, no God/Christ/Jesus,
no church, no prayer, no "blessed"; encouragement in plain human words is wanted. `validate()`
refuses religious language; `PUBLIC_RULES` carries the stance; a new catalogue angle
`built-for-this` ("We were built for this") says the conviction in his words without the religion —
NOT on the dial until Kerry adds it.

**WHY MEMBERS STOP SHOWING UP — Kerry's read (2026-09-17, interview Q3), the brief for the
re-engagement note to the 71 members who have not played since July and for the Insider's
"there is a place for you" thread:** "mostly people just getting busy" — summer vacations, a
number of injuries, heat, a few money-related, relationship changes, people moving, people
active in other groups, people traveling. And ONE reason he named twice: the group felt
"overly competitive" to a player who did not feel he could play well enough to be comfortable
— Randy Copper (Austin) and Brian Parch (San Antonio), both "no intentions of coming back".
Rules that follow: (a) the re-engagement note assumes life got busy — never guesses at the
reason, never asks "why did you stop"; (b) Randy Copper and Brian Parch are EXCLUDED from any
re-engagement send and any "we miss you" list — Kerry's call whether he reaches them himself;
(c) the "too competitive to be comfortable" perception is a real retention leak: the Insider
and the note both need a plain, true line that a member can show up, skip every game, and
just play (verify the exact mechanics with Kerry before printing — Q4); (d) injuries and heat
are named collectively, never a person ("a few of you have been nursing something"); (e)
nothing about money in a re-engagement note beyond the ratified join-offer line.

**WHAT ENTRY INCLUDES — Kerry's Q4 answer + the Tracker's pricing model (2026-09-17):** a
member can enter any Tuesday without buying the side-game bundles and is still in the team
game, closest-to-the-pin and the hole-in-one pot — that is the "Inc. Games" fee inside every
entry (events.md pricing grid; side-games.md §Included games). The individual Net and Gross
games are the +per-game add-on. Members get no free drink; the drink is the first-timer offer.
Kerry: "You have access to the tracker to see all event pricing. I shouldn't have to tell you
that stuff" — mechanics and prices come from the Tracker first, Kerry is asked only what the
Tracker cannot know. The plain sentence for the Insider (awaiting his ratification): *"Enter a
Tuesday and you're in the team game, closest-to-the-pin and the hole-in-one pot — that's every
player. The individual games are an add-on you can skip any week."*

**THE JOIN OFFER — ratified 2026-09-17 (Kerry: "Yes" to "are you comfortable letting the writer
print '$50 to join through September 30, then $75' in the Insider?").** Supersedes the #381
"no dollar prices" guardrail for ONE line: dial `insider_join_offer` holds the price line verbatim
(set 2026-09-17: "$50 to join through September 30, then $75. 365 days from purchase. No monthly
dues." — the CA round-two price card, #477); the writer prints it once, verbatim, linked to the
membership page; `validate()` allows only the dial's figures and refuses a paraphrase;
`lint()` and `approve_insider()` allow the same figures. Blank dial = no price. Kerry edits the
dial when the promo ends (Oct 1: "$75 to join. 365 days from purchase. No monthly dues.").

**Lessons from the first machine-written sample (three Sonnet drafts on s9.23/a9.23,
2026-09-17 5:21 PM CDT, mailbox #544 — the lane's own edit, before Kerry's):**
- W1. **A Tuesday is nine holes.** The fellowship draft wrote "the banter starts on the
  18th green". `validate()` now refuses 18th/eighteenth when the week's events are nines.
- W2. **Never expose bookkeeping.** "No fellowship spot was on the books, so some grabbed
  drinks where they could" — a reader must never see our data gaps. Refused by
  `validate()`; the rule says write around it silently.
- W3. **Logistics only from the fact sheet, per chapter.** "Usually a 5:00 PM shotgun start"
  was written for both cities; Austin runs tee times. Each event and each next-Tuesday
  button now carries a `format` line (`event_format()`: SA = shotgun at `start_time`,
  Austin = late-afternoon tee times, Saturdays = 18 with morning tee times) and the writer
  may quote only that. "We send you a tee time and your group a day or two before" is
  unverified — Kerry to confirm the real lead time; until then it is not on the sheet.
- Also seen: the three options must agree with each other on the same fact (option 1 said
  SA "grabbed drinks in the clubhouse", option 3 said no spot was recorded) — the SA spot
  is set on the EVENT row (Edit Event → GENERAL), which is where the writer reads it.

**Lessons from Insider #3 (Kerry's Brevo edits of the 8:00 draft, 2026-09-16):**
- **When no fellowship spot is on record, the Celebrate line is** *"Stick
  around for food, drink, and banter after the round."* — Kerry replaced the
  generic "Most of the field stayed for a drink after." with it. Draft that
  shape (the writer's `fellowship` brief carries it); never a blank, never a
  guessed venue.
- The 8:00 draft had repeated last week's headline; he retitled it "Half the
  Field Won Money!" (already folded: `pick_headline`, v2.462.4–.5; the
  writer refuses a recent headline too).

**Lessons from the auto-draft (Kerry's edits, 2026-09-10 — "so you can learn from it"):**
- Skins need plain language for a public list. Kerry on the first draft:
  *"the skin sentence doesn't really work where it says you don't have to
  be good, you just have to be alone. Doesn't resonate with a lot of people
  who don't know what a skin is, and alone sounds...lonely."* → beat 3 now
  names the player (first + initial), says the score was *the best anyone
  posted on that hole*, explains that *every hole is its own small
  contest, so one good hole pays even when the rest of the round doesn't*,
  and never uses "alone". Rule: any game term (skin, CTP, net, flight)
  gets a one-clause explanation the first time it appears in a public send.
- Second pass (Kerry, 2026-09-10, on the Brevo draft #17 + skill-block preview):
  - *"so did 5 of the other 8 first timers. 2 more members were first
    timers, right? There were 4 first timers in each city's events."* →
    the 1st TIMER tag alone under-counts: a brand-new MEMBER whose first
    TGF purchase is inside 90 days and who has no earlier card is a
    first-timer too (Michele McCormick, s9.22). Two doors in, both
    computed. (8 first-timers; Christopher E. + 5 of the other 7 cashed.)
  - *"What does 'nobody gets a special tee' mean? Seem like we could
    scratch that."* → gone. Beat 2 ends "Everybody gets a fair game."
  - *"I think we rotate our highlight sections each week to not
    overwhelm. Drop Hole-In-One Pot this week or possibly move to bottom.
    We can hit different highlight sections each week and rotate them
    back."* → ONE dark highlight band per issue, rotated weekly from the
    week of 2026-09-07: skill (Am I good enough to play?) → hio → skill…
    Dial `insider_highlight` = skill | hio | none forces one.
  - *"How a TGF Event works, not night"* → heading fixed in the template.
  - Compete line, verbatim: *"Your own ball. A Team best ball game
    included, so your foursome roots for you. Optional Individual Net &
    Gross games. A TGF Handicap and flighting keeps it fair."* Kerry:
    "We could have a rotation of items here too, and all three of the
    How a TGF Event works" — not built yet; noted.
  - Celebrate shape, verbatim: *"Austin grabbed drinks in the clubhouse.
    San Antonio went to Max & Louie's for food and fellowship. It's the
    best part, and it's yours if you want it."* → per-chapter sentence
    from `events.fellowship_spot`: clubhouse / on-site / grill / patio →
    "grabbed drinks in the clubhouse"; anything else → "went to <spot>
    for food and fellowship". "Stick around after." dropped. The SA spot
    must be ON the event row (set 3306 → Max & Louie's).
  - Skill block: percentages, not "1 in N" (*"Wouldn't percentages be
    simpler graphically and be able to show larger?"*); three tiles —
    % single digits · lowest-to-highest handicap · % at 20 or higher — a
    header "Am I good enough to play?" and the footer *"The other half of
    us are in between."* + *"Check out our TGF Handicaps"* linked to
    https://tgf-tracker.up.railway.app/member/handicaps. Computed live
    from `handicap_distribution()` (members with an established index,
    18-hole equivalents). Kerry's brief: *"big number, very limited text
    graphic ... Don't want to just appeal to the high or mid-handicappers
    either. It goes both ways. Low, scratch and plus handicappers need to
    see there's others like them in our group too."*
  - Third pass: *"It does change the draft from 5 of 7 to 6 of 8, right?"*
    → beat 2 counts the whole group: "6 of the 8 first-timers on the sheet
    did." *"Jump in any time should be a header above the text."* → close
    box header line, body below.
  - Kerry's Brevo edit of #18: eyebrow + headline CENTERED ("For future,
    show top headlines centered as shown"); the greeting and lede stay
    left. Template updated.

**Cadence ruling (Kerry, 2026-09-10 evening, after #2's first-day numbers —
27.8% opens, 29 tracked clicks, 7 unsubs in 3h40m):** *"let's keep it at
weekly right now. I think there's more stories to tell and I think opens
and click trends might be a better sign of how it's hitting."* Unsubs are
not the steering metric (*"I'd rather people unsubscribe if they truly
don't want to be involved"*). Biweekly stays the recorded off-season
rhythm and the fallback if open/click trends sag; monthly is off the
table because the format lives on last Tuesday's results and next
Tuesday's button. Read #2 again at +24h and keep the opens/clicks trend
per issue (Brevo campaign ids: #15 = Insider 1 (9/2), #18 = Insider 2
(9/10), #19 = Insider 3 (9/16)). **Audience split (v2.462.6):** `scoring-brevo-campaign-split:<campaign id>` — recipients / openers / clickers / unsubs by TGF status (active, former, prospect, unknown = not in the Tracker), read-only; Kerry 2026-09-17: most of list 3 (~920 of 1,437) has no Tracker record, i.e. signed up over the years and never bought.

**ISSUE TREND (per-list basis, Brevo campaignStats listId 3 — the only basis that is consistent across issues; globalStats double-count mirror/share hits). Friday scorecard Routine appends one row per issue:**

| issue | sent | audience | delivered | trackable views | opens rate | unique clickers | clicks | unsubs | non-member regs after send | read at |
|---|---|---|---|---|---|---|---|---|---|---|
| #1 (#15) | Wed 9/2 2:18 PM | whole list 3 | 1,245 | 119 | 32.3% | 24 | 56 | 4 | — | final |
| #2 (#18) | Wed 9/10 1:36 PM | list 3 − active | 1,222 | 238 | 44.0% | 21 | 46 | 10 | 0 | final |
| #3 (#19) | Wed 9/16 1:17 PM | list 3 − active | 1,207 | 109 | 39.2% | 16 | 50 | 7 | 1 (Ty B., 1st timer, Cedar Creek 18, Fri 1:32 PM — source unattributed) | final (9/25); +48h was 106 / 15 / 43 / 6 |
| #4 | — | — | — | — | — | — | — | — | — | NOT SENT. The writer's first-timer draft went to Kerry Wed 9/23 8:00 AM and the corrected text sat in chat awaiting "go"; no reply by Fri 9/25. First missed week of the weekly cadence. |

#3 by group at +48h (openers incl. Apple auto-opens / unique clickers): unknown 71 / 7 · prospect 19 / 6 · former 15 / 1 · active 1 / 1. Links: Brackenridge button 6, MEMBERSHIP 6, SA RESULTS 6, SA calendar 5, Austin calendar 4, Teravista 3, Cedar Creek 18 3, Austin RESULTS 2, home 1. **Reading (2026-09-18):** three issues, clickers 24 → 21 → 15 on a fixed audience; #3's real reads are under half of #2's. Two money headlines in a row ("First payday" → "Half the Field Won Money!") and the second pulled less; prospects are still the group that clicks (6 of 15 from ~260 people) and the event buttons + MEMBERSHIP are where they go. Next issue: the rotation's first-timer angle, a subject that names a person and a moment (no purse, no exclamation), and the ratified "you're in the team game without buying anything" line above the Try-a-Tuesday button. The list itself is the ceiling — the Insider cannot grow the audience; lead ads and first-timers do.

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

**#15 RESULTS at +24h (sent Wed 2026-09-02 2:18 PM CDT, whole list 3 —
the Active-members exclusion didn't exist yet; read 2026-09-03 2:30 PM,
mailbox #397):** 1,274 sent / 1,245 delivered / 24 soft + 5 hard
bounces / 0 complaints. Opens 368 unique = 29.6% Brevo opens rate, of
which 281 are Apple Mail Privacy Protection auto-opens — trackable
views 95 (10.4%), Brevo-estimated real views 129. Prior sends on the
same opens-rate basis: 45.3% / 47.3% / 61.5%. Clicks 76 unique / 91
total (Season 20 Kickoff: 209 unique); clickers by device Windows 14,
iPhone 10, Android 5, Mac 3, iPad 1. Unsubscribes 3 = 0.24% (threshold
0.5%). Link ranking: MEMBERSHIP 10 (top), Landa Park RESULTS 7, Canyon
Springs RESULTS 4, Star Ranch RESULTS 4, SA calendar 3, Silverhorn
(SA Tue) 3, Austin calendar 1, Forest Creek 18 1, Cedar Creek 18 1,
homepage 1, ShadowGlen (Austin Tue) 0. Read: money-as-proof pulled
readers to RESULTS and then to MEMBERSHIP; Austin's Tuesday button
drew nothing. Going forward: compare TRACKABLE views, not the
MPP-inflated rate; send #2 to list 3 minus segment #2 (Active
members); mid-afternoon Wednesday is the baseline send window, a
Thursday-morning A/B is the open question.

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

18. **Every event named in the lede links to its GG RESULTS page; the header logo links to thegolffellowship.com** (Kerry 2026-09-02)
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

19. **Subject-line series (Kerry 2026-09-02):** public/Brevo sends are
    `TGF Insider | <hook>` (e.g. "TGF Insider | A par won money this
    week. In both cities."); member/GG recaps stay `TGF Results |
    <WINNER-SURNAME CAPS> <verb phrase>`. Keep the hook inside ~45
    characters after the prefix so it survives mobile truncation.
