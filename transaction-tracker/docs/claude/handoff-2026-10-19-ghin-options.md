# GHIN posting after Golf Genius: options and costs (Handicap Management & Research)

**Date:** 2026-10-19 · **Lane:** CGO > Handicap Management & Research · **Status:** research only. Nothing bought, signed, sent, changed or contacted. Prices below are quoted only where a source is linked; "seen" = 2026-10-19. Anything not confirmed is **UNKNOWN**.

**Rulings carried (verbatim, not reopened):** Kerry 10/19: TGF does not offer a GHIN discount, is discontinuing posting to GHIN (it posted while on Golf Genius because GG offered the connection free), and cannot buy the API connection now. Kerry also asked whether becoming an official TGA member club is cheaper.

## Bottom line

1. **Do not pursue the GHIN API.** It is the USGA's Golfer Product Access (GPA) program for technology vendors serving individual golfers, not for an event organizer. No official fee or application steps are published (UNKNOWN).
2. **The TGA club route is the only real one, and its price is unpublished (UNKNOWN).** Joining as a TGA member club means using the GHIN service. Club fee and TGA's per-golfer rate are not on txga.org. Getting the number costs one free inquiry.
3. **Meanwhile members can post their own scores, free**, if they hold a GHIN number through any club. TGF's index and handicap card are unaffected.

**Recommendation: do nothing paid. After Kerry's OK, send one free inquiry to the TGA (below) once the 12/1 all-Stripe cutover and the #731 gate are done, and decide only when a written quote exists.**

## Comparison

| Route | What it is | Cost to TGF | Eligibility / catch | Source (seen 10/19) |
|---|---|---|---|---|
| A. GHIN API (GPA) | USGA pathway for vendors to read handicap data and post scores by API | **UNKNOWN.** No official fee page found. Unofficial claims (no fee, or a fee, or a 10-clubs/1,400-golfers threshold) are not usable | Vendor agreement with USGA; built for apps serving individual golfers. TGF would also have to build and maintain it (Tracker code change, out of scope) | [USGA GPA overview](https://www.usga.org/content/usga/home-page/handicapping/world-handicap-system/GPA-Program-Overview.html) (read via search excerpt; direct fetch returned 403) |
| B. TGF becomes a TGA member club | A TGA member club is "a Texas Golf Association member in good standing using the GHIN handicap service"; GHIN posting then runs through the club | **Club fee UNKNOWN. Per-golfer rate UNKNOWN** (TGA says clubs above its per-player rate earn a rebate but does not state the rate). Member course-rating fee is $0 vs $2,000 for non-members (not relevant to TGF) | USGA rules require a licensed club, at least 10 members, bylaws and a Handicap Committee; "Type 2" clubs (members tied by a social or business organization) exist (2016 manual; current text not fetched). Whether the LLC qualifies as a club is **UNKNOWN**, TGA decides. Existing TGA clubs must complete a yearly club assessment (2026 deadline was 7/1) | [TGA Club Services](https://txga.org/member-services/), [TGA Online Join/Renew](https://txga.org/introducing-online-join-renew/), [USGA handicap manual s.1/s.2 (2016)](https://www.usga.org/etc/designs/usga/content/rule-book/handicap-manual/rule-14367.html) |
| B-ref. What another association charges (not Texas) | Iowa Golf Association 2026 schedule | $125 (9-hole) or $250 (18-hole) club fee plus $25 per active golfer, 20-golfer minimum, discounted years 1 and 2 | Shown only to size the question; TGA's schedule may differ a lot | [IGA 2026](https://iowagolf.org/?p=12370) |
| C. Members post their own scores | Any golfer with a GHIN number posts via the GHIN app/site | **$0 to TGF** | Member needs a GHIN number (via any club) and a course with Course and Slope Rating; at least 9 holes can be posted. Manual, per member | [SCGA posting guide](https://news.scga.org/4-things-every-golfer-should-know-about-score-posting) |
| D. Stay on Golf Genius posting | Not available after 10/31 | n/a | GG posts only for "GHIN customers" (needs roster GHIN number + last name, compliant USGA course data, hole-by-hole scores). No fees stated in the GG docs | [GG: posting to GHIN](https://docs.golfgenius.com/en/articles/10777772-posting-round-scores-to-ghin), [automatic posting](https://docs.golfgenius.com/en/articles/10777808-automatic-score-posting-to-ghin) |
| E. Host-course club posts for us | A course's own GHIN club posts scores | UNKNOWN | UNKNOWN whether a host club may post another group's rounds | none |

No other priced vendor holding a GHIN posting connection turned up in my searches.

## What a member pays for a GHIN number on their own (helps answer Justin; TGF pays nothing)

- Through the USGA: **$53 for 12 months** (includes TGA membership). Through a club: price set by that club. Gallery Club: $59. [TGA Join](https://txga.org/join-the-tga/)
- Affinity-club example: LPGA Amateurs Houston sells a TGA-issued GHIN for **$28** a year (their page, year unconfirmed). [LPGA Amateurs Houston](https://chapters.lpgaamateurs.com/education/handicap/TXHO)
- A member keeping a GHIN number on more than one club's roster pays each club's roster fee (TGA says each club charges one). If TGF became a club, members already on another roster would either pay twice or TGF would absorb it. For scale only: 150 members x $28 is about $4,200 a year. That figure is my arithmetic from the affinity price, not a TGA quote.

## What members lose and keep if TGF does not post

- **Keep:** the TGF index and handicap card from the Tracker: World Handicap System basis, 9-hole differentials, best 8 of the last 20 within 12 months, Course/Playing Handicap per tee, 75%-of-GHIN start for new members ([Handicap Standard v1.0](../governance/TGF_Handicap_Standard_v1_0.md), handicaps.md). The handicap-ask page still stores each member's GHIN number and starting index.
- **Lose:** automatic posting of TGF rounds into a member's GHIN record. Their GHIN index will not reflect TGF rounds unless they post them. A GHIN number with no activity can be deactivated (an LPGA Amateurs page says after about 2 years; unconfirmed by TGA).
- **Not a TGF handicap gap:** TGF does not run WHS soft/hard caps, Exceptional Score Reduction or PCC (Standard s.4, "conscious omissions"). That is unchanged by this decision.
- **Website copy:** Standard s.7 item 4 already flags the "posted to GHIN" line; it needs the final wording once Kerry decides.

## Assumptions and unknowns

- Assumed Golf Genius ends 10/31 as stated in the hand-off; I found no public notice either way, so I did not test it.
- **UNKNOWN:** which GHIN customer or club identity Golf Genius used for TGF's posting; whether TGF already has any TGA/GHIN club record; the TGA club fee and per-golfer rate; whether TGF qualifies as a club; the USGA GPA fee and steps.
- usga.org pages (GPA overview, GHIN FAQ, terms, Rules of Handicapping ch. 6) returned 403 to direct fetch. Items from them rest on search excerpts and are marked above. txga.org and docs.golfgenius.com pages were read directly.
- Blog claims of "$50k-$100k API development" are consultancy marketing with no source; not used.

## Revisit when

All of: (1) the 12/1 all-Stripe cutover and the #731 gate are done; (2) Kerry OKs the free TGA inquiry and TGA's written quote exists; (3) the quote fits the money test (Sarah reviews anything over $100; full Board over $1,000). Earlier if members ask repeatedly for GHIN posting, or if entry to TGA/USGA events is being lost to inactive GHIN numbers. Otherwise look again at the owner-draw reserve test (about April 2027, #2041).

## Who Kerry would contact (only if he decides; nothing sent)

- **TGA, Handicapping & Membership:** Mary Harrison, Senior Director, (214) 468-8942 (listed on [Online Join/Renew](https://txga.org/introducing-online-join-renew/)); email mharrison@txga.org appeared in a search result, not on a page I read, so verify. Ask: club fee, per-golfer rate and rebate, whether a social golf group qualifies as a Type 2 club, what a club must do (handicap committee, assessment), and whether TGA already holds a TGF record.
- **Golf Genius support:** ask under which GHIN customer TGF's posting ran and what export of posted history TGF can keep before 10/31.
- **USGA (GPA):** only if route A is ever reconsidered; no contact verified.

## Open question for Kerry

Is there a deadline, or is this for when money allows?
