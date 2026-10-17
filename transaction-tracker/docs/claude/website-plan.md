# The new thegolffellowship.com: plan v0.1 (PROPOSAL, not ratified)

Kerry 2026-10-17: "Keep all these things in mind for our very soon to have new
website build that you need to plan out based on our needs, your comments, our
vision, along with pertinent items from our current website. Really need to
think it thru. Of course, needs to be synonymous with our app that we're
building."

Inputs: the GoDaddy site inventory (10/17, every page fetched), GoDaddy's AI
Visibility report (10/17: 43/100, 2 mentions each on Google AI, ChatGPT and
Claude; positive: pay-as-you-play, community golf club, zero monthly dues, a la
carte pricing, inclusive; to improve: "variable experience by chapter",
"limited independent reviews"), the Dec 1 plan (CoS #1971: all Stripe + our
shop, GoDaddy off public checkout 12/1, account setup campaign in November),
#731 (the Tracker is the product), the July app roadmap (member-portal.md:
"one backend, two faces"), the Library ruling #1436 ("member facing versions
for use on the website"), tgf-history-2022-2025.md, and the Privacy Policy /
SMS terms published 10/17. Rule 3b: scope and member-facing words are Kerry's.

## 1. What the site is for

The site and the app are one thing. A golfer who finds TGF on Google, a member
checking Tuesday's tee sheet and a player entering scores are on the same
system, same look, same sign-in, same data. Nothing on the site is typed twice.

Four people it serves, in order:
1. **The golfer who hasn't played yet** (the growth job). Find us, trust us,
   try a Tuesday. Needs: what it is, where, when, what it costs, who plays,
   one button.
2. **The member.** Register and pay, see my events, results, standings,
   handicap, winnings, credit. (Dec 1: this is the account.)
3. **Search engines and AI assistants.** They recommend us only if the facts
   are on our own pages, consistent, and backed by reviews.
4. **Courses, sponsors, press.** Who we are, how big, who to call.

## 2. The big decision: one system or two

**A. One system (recommended).** thegolffellowship.com is served by the
Tracker itself. Public pages (home, chapters, events, results, FAQ) are built
from the same data the app uses: the schedule, prices, rosters, results and
standings are never re-entered. Sign in, register and pay are the Dec 1 account
and shop. Marketing words live as published Library documents (#1436), edited
without code.
- **Marcus:** "Then a public spike can't be allowed to slow a live scorer. Put
  a cache in front (Cloudflare, which we already use for backups) so the public
  pages are served from the edge, and keep the app's writes off that path."
- **Priya:** "A deploy restarts the app. With the cache in front, the public
  site stays up through a restart. The no-push event window protects the rest.
  Email (Microsoft 365) must keep its DNS records untouched at cutover."
- **Sarah:** about $0 extra a month (the Cloudflare free tier); the GoDaddy
  Websites + Marketing plan can be cancelled once nothing points at it.

**B. Two systems.** A site builder (Webflow, Framer, Squarespace) for the
marketing pages and the app on app.thegolffellowship.com. Faster to make
pretty pages, but every schedule, price and result is copied by hand or
embedded, the two drift, and it costs about $20-40 a month. This is the
GoDaddy-plus-Golf-Genius situation we're leaving.

**Alex:** "A is more work up front but it's the only one that's actually
'synonymous with the app'. B rebuilds the problem."

## 3. Site map (A)

| Page | What's on it | Data from |
|---|---|---|
| Home | One line on what TGF is, next events in both chapters, how it works in 3 steps, reviews, one button: Try a Tuesday | events, reviews |
| San Antonio / Austin (one page per chapter) | Where and when we play, courses, the season schedule, manager with photo, this season's standings, recent results | events, courses, standings |
| Events | Every upcoming event; each event has its own page: course, date, format, price, spots left, Register; after it's played, the results | events, rosters, results |
| How it works / Try a Tuesday | First event walkthrough, 1st Timer offer, what to expect, skill levels, pairings | Library copy |
| Membership & pricing | One clear table: member vs guest vs 1st Timer, what's included, add-on games | pricing data (one source, the shop's) |
| Competitions | Every game in plain words, prize funds, season contests, Lone Star Cup, Hole-in-One pot and past winners | games matrix, HIO ledger |
| Results & Leaderboards | The member pages that exist today (Spotlight, Leaderboard, Events board) | live |
| Handicaps | How the TGF handicap works (the table as text, not an image), look up a player | handicaps |
| Stories | Event recaps (already written every week), Insider archive, member spotlights, photos | recaps, Insider |
| FAQ | 20-30 real questions (cost, what to bring, tees, pace, women, beginners, faith, pairings, refunds) | Library copy |
| Our Story | 2007, Kerry, twenty seasons, the podcast | Library copy |
| Rules of Play, Policies, Privacy, SMS Terms, Contact | carried over, fixed | Library copy |
| Sign in / My TGF | The Dec 1 account: register, pay, credit, receipts, my events, score entry | account |

## 4. Findability (the AI Visibility findings)

- **Reviews (biggest lever, needs no website):** a Google Business Profile per
  chapter, and a review ask in the results email to players who had a good
  night (one tap to the Google review page). Target 25+ reviews per chapter by
  spring.
- **One page per chapter** with consistent name, area and contact. That fixes
  "variable experience by chapter".
- **Every event a page** with Event structured data (date, course, price), so
  Google can show it. Results stay on the same address after the event.
- **FAQ with FAQPage structured data**; Organization / SportsClub data on Home.
- **Stories:** the weekly recaps become public posts (names already go out in
  the recap emails; no money amounts or member counts, per event-recaps.md).
  That's 2-4 fresh, local, true pages a week with zero extra writing.
- **Words people search:** "golf league San Antonio", "Austin golf league",
  "9 hole golf after work", "golf group no membership dues", "meet golfers".
- **Old addresses keep working:** 301 redirects from /home-1, /our-story-1,
  /rules-1, /tgf-handicaps-1, /privacy-policy-1, /faq, /competitions,
  /policies, /contact and the /shop links; sitemap.xml; Google Search Console.

## 5. Carry forward from today's site

Keep: "Your Golf Crew. Zero Hassle." / "Real competition. Zero commitment." /
Sign Up, Show Up, Play / "This is where foursomes become friendships" / the
points-race fairness line / the Scott M. testimonial / the FAQ answers on skill
("25-90% of players win prizes each event"), women welcome, "Is TGF a
Christian group?", pairings / Rules of Play in full / handicap explanation /
game descriptions and Hole-in-One history / conduct, refund and weather
policies / Privacy Policy + SMS Terms / founding story (expanded).

Fix while carrying over (and on the GoDaddy site now if cheap):
- "[contact email]" still twice on the privacy page.
- Broken links: /handicaps, /shop/olsPage=all, /shop/ols/categories/events.
- Austin contact: the contact page says Robert Straiton (gmail), Golf Genius
  says James Jones; the layout puts Robert under San Antonio.
- 18-hole deadline: "10p, 3 days prior" vs "Wednesdays at 8p".
- Hole-in-One: home says every event includes it; Competitions and FAQ say
  members only.
- Individual Net flights "one if under 23, two if 24+" (23 uncovered).
- MVP points: double eagle listed as both 4 and 8.
- "After 20 years" vs Est. 2007; typo on Our Story.
- No prices or schedule on the site itself; schedules link to Golf Genius,
  which retires 10/31 (D-plan). **Those links go stale in two weeks.**

## 6. Look and feel

The TGF Design System the app already uses (Bitter headings, TGF orange,
dark nav, chapter colours), mobile-first with the one 560px breakpoint. Real
photos from our events, not stock. Erika: "Every page answers one question,
and the button says what happens next."

## 7. Phases (dates are proposals)

- **Phase 0, by 10/31 (on GoDaddy, small):** the fixes in section 5; replace
  the Golf Genius schedule links (GG retires 10/31) with the Tracker's public
  schedule; set up Google Business Profiles and start the review ask.
- **Phase 1, by 12/1 (with the shop):** Register buttons everywhere point to
  the new account; GoDaddy checkout off (CoS #1971). The GoDaddy pages can
  stay up as the brochure for a few weeks.
- **Phase 2, December to mid-January:** the new site MVP on the Tracker:
  Home, two chapter pages, Events + event pages, Try a Tuesday, Membership &
  pricing, FAQ, Our Story, Rules, Policies, Privacy/SMS, Contact, Sign in.
  Cut DNS to it before the 2027 season opens, with redirects. Not during the
  12/1 payments month if it can be avoided (Priya: one big change at a time).
- **Phase 3, Q1 2027:** Stories (recaps public), Insider archive, public
  Spotlight, review widgets, Competitions in full.
- **Later:** the same pages inside the app-store app (Capacitor, July plan).

## 8. Open decisions for Kerry (one at a time)

1. One system (A) or two (B).
2. Launch target: Phase 2 by mid-January, or sooner.
3. Austin contact on the site: Robert Straiton or James Jones.
4. Mailing address shown publicly: home address or a PO box / virtual mailbox
   (#1795).
5. Recaps public on the site (names yes, money no)?
6. Domain stays registered at GoDaddy (fine), only the website moves.
