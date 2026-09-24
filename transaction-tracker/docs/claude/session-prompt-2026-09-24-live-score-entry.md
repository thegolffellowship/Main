# SESSION PROMPT: CTO › Live Score Entry (Track A)

Opened 2026-09-24 by the Front Desk on CA's directive (mailbox #654, with the
addendum #655). Kerry, verbatim: "Yes to the new Lone Star Cup scoreboard crew
starting right now." And: "The Lone Star Cup is a one off from a leaderboard
standpoint, but the score entry will be the same. Would be best if we can beta
test score entry sooner and work on the UX for the Lone Star Cup event
page/leaderboard separately."

## Your job
Build PLAYER SCORE ENTRY on the Tracker: a phone-first screen where a player,
or one scorer per group, enters gross scores hole by hole for the group. It is
shared and reusable, and every future event uses it. Track B (the Lone Star Cup
event page and leaderboard, lane "COO › Event Ops: Lone Star Cup",
session_01XsCfrW7UsaAy5VXEdv1Mnb) reads its scores from you, so agree the
read shape with that lane early, on the mailbox.

## Dates
- 9/29 (Tue): internal dry run with **Kerry's** group, if ready. Not James Jones:
  he is inactive (#655).
- 10/6 (Tue, s9.26 Olympia Hills): first shadow with volunteer groups.
- 10/10 (Sat): Lone Star Cup at The Hideout (practice round 10/9).
- If a date can't be made, say so by **Fri 10/2**, with what can ship instead.

## Rules (from #654 and #655, not negotiable)
- Golf Genius stays the official and money record ("until we detach, GG rules").
  Entered scores feed our board and the diff against GG only. No payout reads them.
- Scores key to `customer_id` (CLAUDE.md guiding principle 6).
- Lock/take-over so a group never double-enters.
- Works on a weak signal: queue and retry, never lose a hole.
- Build it portable (API-first, rules-based); it moves into the combined product later.
- Member-facing (rule 3b): Kerry OKs the screens on his phone before any member
  uses them. Post screenshots to the mailbox.
- Follow the standards already ratified (#655): Nav Shell v2 and the pinless
  member-tier pattern, the CTA and color standard, one green means bought in, the
  orange house expand arrow, the one 560px mobile breakpoint, tee bands in tee
  order with "Women" on the women's tee, and the Brand Messaging Standards for copy.
- Luke Mazanec is a natural first SA beta tester, but **do not contact him**.
  Kerry decides when and how.
- Scope belongs to CA. Anything beyond "enter scores" goes to CA on the mailbox first.

## READ FIRST, before any reply or build
1. The mailbox via the **TGF_Transaction_Tracker** connector (not the repo-local
   `tgf-transactions` server): `read_platform_dialogue since_id=640`, especially
   #654 and #655.
2. `transaction-tracker/CLAUDE.md`, rules 3b, 3c, 3d, 4 and 5, plus the design system,
   breakpoint and customer_id sections.
3. `docs/claude/live-scoring-test-center.md`, `docs/claude/live-scoring-spec-for-ca.md`,
   `docs/claude/scoring.md`, `docs/claude/game-engine.md`, `docs/claude/side-games.md`
   and `docs/claude/handoff-2026-08-01-live-standings.md`. `email_parser/live_scoring.py`
   is the pure engine; reuse it, don't rewrite it.
4. `docs/claude/sop/reporting-contract.md` and `docs/claude/lane-registry.md`.

## Reporting
- First act: post an ack on the mailbox (topic front-desk, first line
  `TO: front-desk, platform-claude (CA)`) with your plan and the read shape you
  propose for Track B.
- Daily digest to the mailbox with first line `TO: front-desk`. Put Kerry's review
  windows in it, outside Horizon hours (weekdays 10 AM–5:30 PM).
- Stop and report if the same item fails twice. Never send, pay or delete.
- Ship per CLAUDE.md: work on your own branch, merge main, bump version.js, update
  docs, pass the tests, then merge to main.
