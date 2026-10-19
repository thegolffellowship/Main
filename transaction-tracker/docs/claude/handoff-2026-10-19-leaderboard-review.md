# Leaderboard Review, 2026-10-19 (CGO > Leaderboard Review lane)

Research and proposals only. Nothing in this file is built, ruled or deployed. Kerry's rulings are quoted verbatim and are not reopened. Anything marked **[CONFIRM]** is a rule or wording I could not verify and Tracker Build or Event Ops should check before it ships.

Mailbox read through #2081. Live version when reviewed: v2.571.24 (v2.571.23 live Individual Net, v2.571.24 men's tee labels, flight headings, Skins view). Screenshots: `docs/claude/screenshots/leaderboard-review-2026-10-19/` (390 px wide phone viewport, 2x).

---

## 0. What I reviewed, and what I did not

**Walked on a phone-sized screen against the live site** (finished events only: no event is in play until Tue 10/20):

- Event results board for s9.27 The Quarry (10/13, entry-scored, no Golf Genius): every tab (OVERALL, TEAM, NET, GROSS, SKINS, MVP/POINTS, PROXIES), the HOW TO READ THIS panel, and the event list (about 70 events in one 14,000 px page).
- Season Contests board, TGF Monthly (October).
- Lone Star Cup board: top strip, matches, and the SKINS tab.
- Spotlight landing page (name search only).

**Read in code, not seen live** (they only exist while a round is being played): the live ranking and sort rules in `templates/contests.html` (`evlbOverallSort`, the `boards` table, `evlbRankBand`), the live row builder `entry_publish.live_board_rows`, and the leaderboard payload in `database.get_event_leaderboard`. Every "mid-round" finding below is therefore **from code**; I propose a read-only walk of Tuesday's live board to confirm them (no push, no write).

**Not walked in depth** (say so plainly): the Fellowship Cup / Players Cup championship boards and player cards, the Fall Net/Gross points-race drill-downs, a Spotlight player card, the Handicaps page, and the staff (manager/admin) Events leaderboard. They share the same renderers as the pages I did walk, but I have not seen them on a phone. They are listed in section 6 as the next pass.

---

## 1. The five-second test

For each view: can a player see, in five seconds, (1) who is winning each game, (2) where the real leaders stand now, (3) what each game pays and how many places, (4) what is final and what is still moving?

| View | Who is winning | Real leaders now | What it pays | Final vs moving |
|---|---|---|---|---|
| Event board, OVERALL | Yes after the money lands (rank = money won); no during play | **No** (see F1) | **No** (one POT figure on the event row, nothing per game) | Amber banners, wording differs between states and the HOW TO READ panel disagrees (F8) |
| Event board, TEAM | Yes, T1/T3 bands with a TEAM NET row | Probably not mid-round (F2, from code) | **No** | Same banners |
| Event board, NET | Yes, per flight, tinted | Yes during play (ranks on the ± column) | **No** | Same |
| Event board, GROSS | Yes, when the game runs | Yes during play | **No**; when the game does not run, the explanation is a note, not a state (F9) | Same |
| Event board, SKINS | Yes after the 10/19 Skins view; # shows skins held | n/a (holes, not totals) | **No** pool, buyers or per-skin value | Same |
| Event board, MVP/POINTS | Yes | Cumulative points favour whoever has played more holes; no "thru" (F3) | **No** | Same |
| Event board, PROXIES | Yes (contest, winner, hole, $) | n/a | Amount shown only for the winner | Not marked |
| Season Contests (TGF Monthly) | Yes, rank + points | Yes | `$` only on rank 1, in grey; pot only inside HOW IT WORKS | "OCT •" dot marks the open month |
| Lone Star Cup board | Yes (score strip, match cards) | Yes (live match state) | Only inside tabs | FINAL on each card |
| Spotlight | Per player | n/a | n/a | n/a |

The single biggest gap in the table is the "What it pays" column: it is empty on every event tab. Kerry's 10/19 ruling covers it.

---

## 2. Findings, worst first

### F1. Mid-round, OVERALL has no rank and is ordered by a raw total (from code, high confidence)

`evlbOverallSort(d)` returns `"won"` whenever the event has a pot. Money is blank until the field is complete (and not final for 15 more minutes), so during play every row has no value to rank on: the `#` column is empty, and the rows fall back to the tie-break, which is the player's raw `net` total (`evlbRankBand` / the sort at `contests.html` ~4559-4572). A player three holes in sits above a player who has finished nine, which is exactly the "three holes in, 13 strokes leads a board" bug Kerry fixed for NET and GROSS on 9/15 (those two tabs sort on the ± column, `"tpn"` / `"tpg"`, while the field is incomplete). OVERALL, TEAM, MVP/POINTS and SKINS do not get that fix.

Related, now fixed: the live Individual Net figure itself. `live_board_rows` subtracted the full playing handicap; since v2.571.23 a part-played card subtracts only the pops on the holes played. That fixes the number. It does not fix the order on boards that sort on the total.

### F2. TEAM mid-round likely ranks on a raw team total (from code, medium confidence)

TEAM uses `sort: "keep"` (server order), and the server orders teams by `total_net` (GG position when GG recorded one, else lowest total). A team that has played fewer holes has a smaller total. The TEAM NET row does show a ± against par, but the order does not use it. This matters more now that TEAM is to be the landing tab. **[CONFIRM on Tuesday's live board.]**

### F3. No "thru" anywhere on the event board

City Match Play has "LIVE · thru 7". The event board has no holes-completed number per player, no "players still to tee off" count, and no field-progress line. Without it, ± and net-to-date are not comparable between players, and a player cannot tell whether the leader has one hole left or nine. Net-to-date (v2.571.23) makes this more necessary, not less: the number is now honest, but it needs its denominator beside it.

### F4. The phone default hides the totals

On a phone the OVERALL board opens with "Hole by hole" ticked (see `event-board-overall-phone.png`). The nine hole columns push G / ± / N / ± / PTS off the right edge; the player has to scroll sideways to see the score that decides the game. The first screen is rank, name, tee dot, WON and holes 10 and 11. Recommend hole-by-hole defaults OFF on phone widths, ON on desktop. Small effort; this is a default, not a rule.

### F5. OVERALL's rank means "money rank", and ties and blanks hide the story

After the money lands, rank = dollars won. Five players at $11.50 all read "T10", and players with $0 have a blank rank. A player at $0 who was 3rd in Net but did not buy Net cannot see where they finished. Fine as a payout list; poor as "where do I stand". Moving OVERALL to the end of the tabs (Kerry 10/19) mostly resolves this, as long as TEAM and NET carry the real standings.

### F6. Full handicap subtracted mid-round: where else (the audit Kerry asked for)

| Place | Status |
|---|---|
| Event board net (`live_board_rows`) | Fixed v2.571.23 |
| Net-to-date vs par (± column) | Already par-to-date (`par_by_rid` counts only holes played): correct |
| Team Net, MVP points, Skins | Hole-level pops (`strokes_received` per hole): correct by construction |
| **½ Net Skins live circles** | **Open.** Live circles compute GROSS skins only. On a night the matrix runs ½ Net Skins (under 8 gross buyers on a nine) the circles are gross while the money is net. Build flagged this in #2071; payouts are right, the board is not. |
| Published record, closeout, card parity, payouts | `gross - playing_handicap` on COMPLETE cards only: correct |
| Lone Star Cup net team skins | Uses its own per-hole pops: correct |
| Points race live (`points-race/live`), City Match Play | Hole-level; I found no full-handicap subtraction, but I did not trace the match-play handicap allocation line by line |

So the only remaining full-vs-partial handicap problem I found is the ½ Net Skins circles.

### F7. Ties and skins display

- The skins `#` column is "skins held". Everyone with none is ranked together ("T4" for ten players on the Cup's Flight 2, "T8" for five on Flight 1; see `lsc-skins-phone.png`). Rank 4 here means "no skins", not "fourth". Recommend blank rank for zero-skin rows, or a divider ("No skins yet").
- Skin circles and the `#` column already update live and un-circle when a hole is covered (Build #2071).
- Skins on the event board land hole by hole; the new view (v2.571.24) removed Net columns and gross-skin pops. That is the right direction.
- The per-skin value is unknowable until the last hole is in (Build #2057 correctly will not show it early). The board should say "per-skin value set when the last hole is in" so a blank is not read as an error.

### F8. Labeling: gross vs net vs to-par, and the two clocks

- Columns read `G ± N ±` with no key. The first ± is gross-to-par, the second net-to-par. A first-time player cannot tell. Recommend `GROSS (to par)` / `NET (to par)` in the header, or put the key in HOW IT WORKS and add a one-line `to par` sub-label.
- During play the net column is "net to date" and at the end it is "net". Same header, different meaning. Add "to date" while the round is open (proposed state label in section 5).
- The page contradicts itself on the money clock: the amber banner says winnings are final "15 minutes after the last score", the HOW TO READ panel says "10 minutes after the last score" (`money_hold_minutes` vs the card-lock 15). With Kerry's 20-minute closeout this will be a third number. One source of truth for the minutes, shown from the dial, not typed into the copy.
- Team tab note still says "the recorded Golf Genius order/result" on a Tracker-scored event (s9.27 has `gg_scored=false`). Stale since the untether.
- Names: the event board shows "Adam Baker" (First Last), the Season Contests board shows "BAKER, Adam" (Last, First). Two conventions on one nav.

### F9. A game that is not being played looks like a game

On s9.27, GROSS did not activate (10 buy-ins, needs 16). The tab still opens as a full ranked table (1 to 10, no money) with one pale note above it. A player reads that as "I finished 4th in Gross, where is my money?". Proposal: a visible state on the tab itself, "NOT PLAYED at this event: 10 of 16 buy-ins, its pot went to Skins", and no ranking table below it (or a greyed "scores only" table).

### F10. Stale labels on the event list

The event list shows "IN PLAY / SCORES OUT" on s9.18 Cedar Creek (Jul 14), three months old. The list has no per-event final/official badge, and the 70-event list is one long scroll. Needs a state per event row (section 5), and a limit (current season on top, older collapsed).

### F11. Season Contests board

- Columns `RK PLAYER R PTS $`: "R" is not defined on the screen (rounds). `A` / `SA` chips are not defined (Austin / San Antonio). Dollars show only on rank 1 and in grey. What the month pays is only inside HOW IT WORKS.
- It does the important thing well: `T3`, `T5` ties are real ties, and the open month has a marker.

### F12. Lone Star Cup

The strongest board in the app on a phone: a single score strip, match cards with FINAL, and the HOW IT WORKS button at the top. Its SKINS tab already carries a one-line legend and "frozen index" language. Not a priority; its patterns are the model for the rest (section 5).

---

## 3. Kerry's 10/19 rulings, added to the audit list

> **Superseded in part by section 11 (Kerry's evening rulings, same day):** tab order is now TEAM, MVP, NET, GROSS, SKINS, PROXIES; OVERALL is retired; SUMMARY shows at FINAL; THRU and name format are ruled; TEAM gets a collapsed one-row-per-team view. Read section 11 first.

Verbatim, from the front-desk routine: "HOW IT WORKS is our standard for any explanations" (replaces HOW TO READ THIS; sits on the same line as the games nav bar on desktop); explanatory notes such as "Individual Gross activates at 16 Gross buy-ins on a 9-hole event..." move into it; the 'not in' badge shows only when Show All Players is checked; OVERALL moves to the end of the tabs on every view and event, and the landing tab is TEAM; a possible SUMMARY tab is an idea to evaluate, not a build.

Current state vs the ruling:

| Ruling | Today (live) | Gap |
|---|---|---|
| HOW IT WORKS replaces HOW TO READ THIS | Button is labelled HOW TO READ THIS, orange pill below the tab bar. The Season Contests and Cup boards already say HOW IT WORKS | Rename; move to the games nav line on desktop; same component as the Cup's |
| Notes move into it | See section 4: about 12 notes and banners | Move all that are explanation; keep status |
| 'Not in' badge only with Show All Players | The legend chip "bought in / not in" renders under every buy-in tab (Net, Gross, Skins, Points) whether or not Show All Players is ticked; grey "not in" rows only appear when it is ticked | The chip is the only mismatch: gate it on the checkbox |
| OVERALL to the end; TEAM is the landing tab | Order today: OVERALL, TEAM, NET, GROSS, SKINS, MVP/POINTS, PROXIES; lands on OVERALL | Reorder to TEAM, NET, GROSS, SKINS, MVP/POINTS, PROXIES, OVERALL on every event (member, staff, Cup events); landing = TEAM. For an event with no Team game (no games, Cup practice rounds) the landing tab should fall to the first tab that exists |
| SUMMARY idea | Not built | Section 7 |

**Landing on TEAM raises the stakes of F2.** If TEAM is first, its mid-round order must be right (to-par, with "thru").

---

## 4. Notes and banners that should move into HOW IT WORKS

| # | Where | Today | Move or keep |
|---|---|---|---|
| 1 | GROSS and SKINS tabs | "Individual Gross activates at 16 GROSS buy-ins on a 9-hole event, this event had 10, so its pot rolled into Skins..." (orange note) | Move the rule into HOW IT WORKS. Keep one short state line on the tab: "NOT PLAYED: pot went to Skins" (F9) |
| 2 | TEAM tab | "Bands are the teams, in the recorded Golf Genius order. Hole scores are each player's GROSS with their pops marked..." | Move; delete the Golf Genius phrase |
| 3 | TEAM tab (GG-era events) | Two grey notes that positions and purses are the recorded Golf Genius result and that the total is a "best-ball reconstruction" with the 75% allowance | Move; only for GG-era events, and say it once |
| 4 | Every tab, below the table | "Tap a player for their scorecard." | Move |
| 5 | Every buy-in tab | Legend chips: Flight tints, `Pts MVP`, `bought in / not in` | Keep the flight tints (they are the key). Gate `not in` on Show All Players. Describe colors in HOW IT WORKS |
| 6 | Tee key | Gold / Blue / Men 65+ Red / Women Red dots | Keep (a key, 4 chips); fold to a single line |
| 7 | Amber "Round in play - winnings are not posted yet..." banner | Banner with the why, plus the list of players who are short | **Keep as a status strip, shorten, drive the minutes from the dial.** Move the explanation into HOW IT WORKS |
| 8 | Amber "Winnings are not final yet..." banner | Banner | Same as 7; this is the provisional state |
| 9 | HOW TO READ panel, "Where the scores come from" | Panel text, with "10 minutes" | Keep in HOW IT WORKS, fix the minutes (F8) |
| 10 | Cup skins | "A circled score won a skin; # is skins won. A session where no skin is won carries its pot to the next session. Individual gross, two flights on the frozen TGF index. TGF settles after the round." | Move |
| 11 | Cup skins, staff only | "Staff · pot ... carry ... out" | Keep (staff-only), but it is the pattern for "playing for" |
| 12 | Season Contests | The welcome nudge ("Welcome to the Fellowship...") | Keep; not an explanation of a board |

The test for a note: if it explains a rule, it goes in HOW IT WORKS. If it says what state the board is in right now, it stays on the board, as one line.

---

## 5. One design that holds the pieces together

The Tracker Build specs (#2057 "playing for", the 20-minute closeout, v2.571.24 skins) and Kerry's tab and HOW IT WORKS rulings all touch the same strip of screen. Proposed so they fit:

```
[ s9.27 The Quarry ]            [HOW IT WORKS (i)]
 TEAM | NET | GROSS | SKINS | MVP/POINTS | PROXIES | OVERALL
 ---------------------------------------------------------
 STATUS   LIVE · 14 of 23 players through 9 · 4 not started
 PLAYING FOR   Pays 2 places per flight · Flight 1 (8): $40 / $24
               Flight 2 (6): $40 / $24 · pot $96, 12 bought in
               (based on 12 bought in as of 3:12 PM) · ties split the places
 ---------------------------------------------------------
 #  PLAYER           THRU   NET (to date)   TO PAR   WON
```

**One status strip, five states, same words on every tab and in the event list.**

| State | Strip says | Money column | Event list badge |
|---|---|---|---|
| Not started | "First tee 3:40 PM · 23 players" | blank | UPCOMING |
| LIVE | "LIVE · N of M players through ..." | blank | LIVE |
| FIELD IN | "Every score is in. Money is provisional until HH:MM" | shown, marked provisional (lighter) | PROVISIONAL |
| FINAL | "Final. Waiting for closeout." (the 15-minute card lock passed) | shown, provisional | FINAL (unofficial) |
| OFFICIAL | "Official" | shown, normal weight | OFFICIAL |

Closeout (+20 minutes, #2057) is the transition FINAL to OFFICIAL, so the board should name it OFFICIAL and not invent a fourth word. The minutes in the strip come from the dials (`se_card_lock_minutes`, `closeout_after_final_minutes`), never from typed copy.

**"Playing for" line per tab** (source: the GAMES tab, Build's spec; I propose only where and how it reads):

- Under the tab, above the table, always visible once the event has buyers.
- NET / GROSS: one line per flight with size and places: "Flight 1, 8 players: pays 2, $40 / $24".
- SKINS: "Skins pool $84, 12 in. Each skin is worth the pool divided by skins won, set when the last hole is in."
- MVP/POINTS: "MVP pays $4 x buyers: $48. Highest net Stableford points wins; ties go to net, then gross." **[CONFIRM the tie order with side-games.md lines 55-58]**
- TEAM: "Team Net pays N places: $... / $..."
- PROXIES: "Closest to Pin: $23 per par 3" (the existing PROXIES table already shows the winner, add what is played for before it is won).
- NOT PLAYED: "Individual Gross: not played at this event (10 of 16 buy-ins)".

**Proposed order of columns on a phone** (the list a player scans): rank, player, THRU, to par, net (to date). Hole-by-hole and handicap columns stay behind their checkboxes (default off on phone).

**Ranking rule while the round is open, all tabs:** rank on to-par net (or to-par gross for Gross), then more holes completed, then name. Do not rank on a raw total. Once FIELD IN, rank on the settling number.

---

## 6. Prioritized fix list

Effort: S = under half a day, M = about 1 day, L = several days. Risk: display-only unless stated. Items marked **(Build)** are already in Tracker Build's lane; the rest are proposals for them.

| # | Fix | Effort | Risk | Needs from Kerry |
|---|---|---|---|---|
| 1 | Rank every tab on to-par while the round is open; show a THRU column (F1, F2, F3) | M | Low (display only; money paths untouched) | Yes, it is a member-facing change (rule 3b) |
| 2 | Tab order: TEAM first and landing, OVERALL last, on every event (Kerry 10/19) | S | Low | Ruled |
| 3 | Rename to HOW IT WORKS, move to the nav line on desktop, move notes in (section 4), delete the stale Golf Genius copy (F8) | M | Low | Ruled; the copy is for his review (section 8) |
| 4 | "Playing for" line per tab with the states above **(Build, #2057)** | M | Low if it reads the GAMES numbers | Ruled |
| 5 | One status strip with the five states; one source for the minutes (F8, F10) | M | Low; ties to the closeout trigger **(Build)** | The words (section 5) |
| 6 | Hole-by-hole default OFF on phone (F4) | S | None | No |
| 7 | "Not in" chip only with Show All Players (Kerry 10/19) | S | None | Ruled |
| 8 | NOT PLAYED state for an inactive game instead of a ranked table (F9) | S | Low | No (explains what already happens) |
| 9 | Column header key: `GROSS (to par)` / `NET (to par)`, "to date" while open (F8) | S | None | Style tier |
| 10 | ½ Net Skins live circles use the game's pops (F6) | M | Medium: touches the live skins view; payouts unaffected | Build already flagged; Kerry's word |
| 11 | Skins and Cup: blank rank or a divider for zero-skin rows (F7) | S | None | Style tier |
| 12 | Event list: per-event state badge, stale "IN PLAY" fixed, current season on top (F10) | M | Low | No |
| 13 | Season Contests: define R and the chips; show the month's pot and places; one name order (F8, F11) | S | None | Name order is Kerry's style call |
| 14 | SUMMARY tab (section 7) | M to L | Medium (money on screen before closeout) | Yes: his call |
| 15 | Walk the live board Tuesday read-only; next pass on the Fellowship Cup, Spotlight, Handicaps and the staff view | S | None | No |

Order I would ship: 2, 6, 7 (hours, safe) with 1 and 3, then 4 and 5 as one change, then 8 to 13. 14 after Kerry rules on the idea.

---

## 7. SUMMARY tab (an idea to evaluate, not a build)

> **Update (section 11):** Kerry ruled SUMMARY shows when the board is FINAL. The "provisional" row in the states table below is therefore not shown on SUMMARY; the tab appears at FINAL and is marked not official until closeout.

Kerry: money winners for all games with links to each game, shown once last scores are in, not official until closeout fires.

**What it would show** (one screen on a phone):

- A header with the status strip and the event pot.
- One block per game that paid, in the same order as the tabs: game name, then the winners with their place and dollars ("Individual Net, Flight 1: 1st Adam Baker $63"), then a "See the board" link that opens that game's tab.
- Team Net: winning team, members, purse. Skins: winners with skins held and dollars. MVP: the winner and points. Proxies: each winner, hole, dollars.
- A footer: "Your winnings: $X" when a signed-in or recognised player is viewing (this depends on sign-in, which lands 12/1; until then, none).
- Ties show "T2" and the split amount; an unpaid place is shown as "not paid" only when the field has fewer buyers than places.

**States:**

| State | Rule | What the tab shows |
|---|---|---|
| Hidden | The field is not complete (a player is still short a hole) | The tab does not appear (the tab list stays short and honest) |
| Provisional | Every score is in. Includes the 15-minute card lock window and the wait for closeout | Visible, every dollar marked "provisional", header strip says why, with the time money is expected to be final |
| Official | Closeout fires and the payouts are recorded (no hold) | Same layout, "Official" in the strip, provisional marking removed |
| Held | A hold is on (card parity, unconfirmed CTP, Kerry's hold) | Back to provisional with one line: "Results are being checked"; never shows a reason that is internal |

**Cautions:**

1. It is the first place dollars appear together before they are official, so the "provisional" marking has to be unmistakable. A winner who reads "$63" and later sees "$57" is a worse outcome than a blank.
2. A correction after closeout (Unlock) can change an official page. The tab needs a "Corrected 8:30 PM" line, which the closeout risk list in #2057 already anticipates.
3. It duplicates the OVERALL tab's WON column for the money. Keep one: OVERALL could be retired in favour of SUMMARY once SUMMARY exists, which would also answer the 10/19 player feedback that OVERALL was confusing.
4. Where it sits in the tab order: first or last is Kerry's call. My lean is last, next to or replacing OVERALL.

---

## 8. HOW IT WORKS drafts, per tab (for Kerry's review; plain language)

Standard shape for every tab, four short blocks: **What this shows**, **How it is decided**, **What it pays**, **What is final**. "What it pays" is filled by the same numbers as the Playing for line, so the words never go stale. Rule details marked [CONFIRM] must be checked against `side-games.md` before this ships.

**TEAM**
- *What this shows:* Each band is a team. Under each player is their score with the strokes they received marked as dots. The TEAM NET row is the team's score.
- *How it is decided:* On every hole the team's best net score counts (your score minus the strokes you get on that hole). The green number is the ball that counted. The lowest team total wins. A BLIND is a member whose handicap fills an empty seat so every team has a full card.
- *What it pays:* The Playing for line above the table. Ties split the places they cover.
- *What is final:* Scores update as each hole is posted. Money is provisional until every score is in, then final 15 minutes after the last score, official when results close. [CONFIRM allowance wording for 4-person teams and 2-person carts]

**NET (Individual Net)**
- *What this shows:* Every player's gross, net, and how far over or under par each is. While the round is on, net is to date: your gross so far minus only the strokes you received on the holes you have finished.
- *How it is decided:* Net = gross minus the strokes you get. You compete against the players in your flight, which is set by handicap at first tee. Lowest net in the flight wins.
- *What it pays:* Per flight, places and dollars in the line above. Only players who bought Net can win; tick Show All Players to see everyone.
- *What is final:* Same as above.

**GROSS (Individual Gross)**
- *What this shows:* Every player's actual score, no strokes.
- *How it is decided:* Lowest gross in the flight wins. This game only runs when enough players buy it ([CONFIRM] 16 on a nine, from the live matrix); below that its money goes to Skins, and the tab says "not played".
- *What it pays / final:* As above.

**SKINS**
- *What this shows:* Hole by hole. A circled score won a skin. The # column is the skins you hold right now.
- *How it is decided:* A skin goes to the lowest score on a hole, but only if nobody ties it. A tied hole pays nobody, and the money carries. [CONFIRM: gross skins at 8 or more buyers on a nine, ½ Net skins below that, per side-games.md]
- *What it pays:* The pool and how many are in. Each skin is worth the pool divided by the skins won, so the per-skin amount is set when the last hole is in.
- *What is final:* A skin can disappear while the round is on (a later score ties it). It is settled at the end.

**MVP / POINTS**
- *What this shows:* Net Stableford points on each hole and the total. The Event MVP is marked.
- *How it is decided:* Points per hole come from your net score against par for that hole [CONFIRM point table]. The highest total wins. Ties are broken by net score, then gross [CONFIRM].
- *What it pays:* The MVP pot in the line above.
- *What is final:* Totals grow as holes are posted, so a player further along is ahead until everyone catches up; look at THRU.

**PROXIES**
- *What this shows:* Closest to the Pin winners by hole, and any hole in one.
- *How it is decided:* The closest ball on the par 3, confirmed by a manager at the event.
- *What it pays:* Dollars per hole, shown before the winner is known.
- *What is final:* A winner stays "unconfirmed" until a manager confirms it.

**OVERALL**
- *What this shows:* Everyone in one table: hole scores, totals, and everything each player won across every game.
- *How it is decided:* It is a roll-up. Each game's rules are on its own tab.
- *What it pays:* The WON column is all money won at this event, all games.
- *What is final:* WON stays blank until every score is in and the last player has finished.

**Status block (identical on every tab, last in the panel):**
"LIVE: scores update as each hole is posted. Every score is in: money appears, marked provisional. Final: 15 minutes after the last score. Official: results are closed and payouts are set. A correction after that updates the board and is noted." (Minutes come from the dials.)

---

## 9. What I need from Kerry for a working session

One question first: **which leaderboard do your players actually open first, on the course and after the round?** It decides what to fix first. The ten-minute agenda:

1. The status strip words (LIVE / PROVISIONAL / FINAL / OFFICIAL): do those four words work?
2. Show-me test: put the TEAM and NET mock-up (section 5) on his phone and ask "who is winning, where do I stand, what are we playing for".
3. Rank on to-par plus a THRU column: yes or no (member-facing, rule 3b).
4. SUMMARY: keep OVERALL, replace it with SUMMARY, or neither.
5. One name order everywhere: First Last, or Last, First.
6. HOW IT WORKS wording: read the TEAM and SKINS blocks aloud.

Open items for the Future Items list (topic `future-items`) are in the mailbox digest.

---

## 10. Appendix: evidence

- Screenshots: `docs/claude/screenshots/leaderboard-review-2026-10-19/` (`event-board-overall-phone.png`, `event-board-net-fullpage.png`, `how-to-read-modal-phone.png` (taken on the MVP/POINTS tab), `season-contests-monthly-phone.png`, `lsc-skins-phone.png`).
- Code read: `templates/contests.html` (`evlbOverallSort`, `evlbReadGuide`, `evlbMoneyNotice`, `evlbFinalNotice`, the `boards` table, `evlbRankBand`), `email_parser/entry_publish.py` (`live_board_rows`), `email_parser/database.py` (`_entry_mode_overlay`, `get_event_leaderboard`).
- Mailbox: #2041-#2081 read; #2057 (playing for, closeout), #2065 and #2069 (live net fix), #2071 and #2079 (skins view), #2067 (Kerry's fourth batch) used.
- Method: Playwright 1.56.1, Chromium, 390 x 844, device scale 2, public member pages only (no PIN, no writes, nothing sent).


---

## 11. Kerry's evening rulings, 10/19 (verbatim) and what they mean for the design

Kerry, with a screenshot of the TEAM board fully expanded:

- "TEAM is always first. Then MVP, NET, GROSS, SKINS, PROXIES"
- "Retire the OVERALL tab but keep the idea around in case we want to bring it back"
- "SUMMARY will show when FINAL"
- "State words. Explain each"
- "Show thru columns on leaderboards that don't show all holes on landing. Pre-Event view would show tee time/hole in that column"
- "First Last, but show last names with the capitalization rules we have."
- "TEAM should be simpler. The attached view should be the fully expanded view state. There should not be any additional player expansion. But I want to the collapsed state to show a single row for each team with their net score (follow hole by hole calculations like we just discussed on NET, rather than cumulative score minus total PH). Then players can click to expand a team into it's current state."

These replace my section 3 and 6 where they differ. Research and proposals only; Tracker Build owns the code.

### 11.1 Tabs

Order: TEAM, MVP, NET, GROSS, SKINS, PROXIES. Landing tab TEAM. Where SUMMARY sits is not ruled (my lean: last). The screenshot labels the last game tab CTPS and the sub-nav shows ENROLLMENT; Kerry's text says PROXIES. **One label, please: PROXIES or CTPS?** (The page header, HOW IT WORKS and the Playing for line should use the same word.)

Retire OVERALL, keep the idea: hide the tab behind one setting (`evlb_overall_tab`, default off), leave its renderer and the `won` roll-up in place, and note in the code comment why. No data or schema change. Its two jobs move: the "everything I won" roll-up becomes SUMMARY; the all-holes view is the Hole by hole checkbox on each tab. Fix F1 and F5 (my doc section 2) simply stop mattering for the landing view, but F1's ranking rule still applies to TEAM, MVP and SKINS (section 11.4).

### 11.2 State words, explained (draft for the strip and HOW IT WORKS)

| Word | Where it shows | Plain-language meaning for a player | What the board does | Event list badge |
|---|---|---|---|---|
| UPCOMING | Before the first tee | The pairings are set; nobody has played yet. | THRU column shows each player's tee time and starting hole. No money. | UPCOMING |
| LIVE | From the first score until every score is in | Scores are coming in hole by hole. Standings move as groups post. | Everything is "to date" with a THRU number. WON is blank. | LIVE |
| PROVISIONAL | Every score is in, up to 15 minutes after the last one | The field is done and the money is shown, but a score can still be corrected, so the dollars can change. | WON shows, lighter, marked provisional. SUMMARY not shown yet. | PROVISIONAL |
| FINAL | Every card has locked (15 minutes after its group's last score) and closeout has not run | Scores are locked. Nothing changes unless a manager unlocks a card. Results are not official until they are closed. | WON normal weight. **SUMMARY appears.** | FINAL |
| OFFICIAL | After closeout runs (the 20-minute rule) and the payouts are recorded | Results are closed and prizes are set. A later correction updates the board and says so. | SUMMARY loses its "not official" marking. | OFFICIAL |

Two things Kerry should know about how these line up with his 20-minute rule (#2057, #2067): closeout starts 20 minutes after the last score, a card is final at 15, so **a clean night spends only about five minutes in FINAL before it becomes OFFICIAL.** FINAL is long only when something holds closeout (card parity, an unconfirmed CTP, his hold, a wait on a stuck group); then SUMMARY shows with "not official yet" for as long as the hold lasts. The words come from the dials; the minutes in the copy are never typed in.

HELD is not a sixth word. A hold keeps the board at FINAL and the strip says one plain line, "Results are being checked."

### 11.3 SUMMARY tab

Appears at FINAL. Until then it is not in the tab row (a tab that appears is clearer than a greyed one). Contents, states and cautions as in section 7, with the provisional state removed. At FINAL it carries "Not official until closed". At OFFICIAL that line goes. If a manager unlocks a card after FINAL the tab disappears again until the board is FINAL (and says "corrected" when it returns after OFFICIAL). Because it can only be seen at FINAL, the "winner reads $63 then $57" risk from section 7 is smaller, but not zero: an Unlock after FINAL can still move money.

### 11.4 THRU column

Rule as ruled: show it on any board that is not showing all the holes on landing. In practice:

- **Hole by hole OFF** (the new phone default I proposed, F4; also any board that never has hole columns): THRU is a column beside the score.
- **Hole by hole ON**: the holes are the progress; THRU is hidden.
- **Value:** holes completed while LIVE ("5"), "F" when the card is finished. Pre-event (UPCOMING): the tee time and start hole, "3:40 PM · 10" for a shotgun start or "3:40 PM" for tee times. Not started once play has begun: the same tee time, greyed. A withdrawn or no-show player: "-".
- Ranking while LIVE stays on to-par (section 2, F1), then more holes completed, then name, so the THRU column and the order always agree.

### 11.5 Names

First Last everywhere (the Season Contests board's "BAKER, Adam" changes). Capitalization: show the player's canonical stored name and do not re-case it at display time. The stored forms follow the app's own rule (`_proper_case`: Mc/Mac, apostrophes, hyphens, roman numerals), and a few are set by hand ("DelCarmen" is on the board today; `_proper_case` alone would print "Delcarmen"). So the display layer should read `customers.customer_name` as stored, never call `_proper_case` itself. **[CONFIRM with Tracker Build that no board applies its own casing, and that the Season Contests board's Last, First form is a display transform and not stored.]** Sort order is separate: sort by last name, show First Last.

### 11.6 TEAM: collapsed by default, expanded = today's board

**Expanded view = Kerry's screenshot, unchanged.** Band header with the four names, the four player rows with holes, per-player `N` and `±`, the green best-ball cells, the `TEAM NET` row with its purse. **No further expansion inside it:** remove the tap-a-player-for-a-scorecard behaviour and the team best-ball card chevron from TEAM (the tee dot, BLIND chip and WON per player stay).

**Collapsed view = one row per team:**

```
# | TEAM                                         | THRU | NET  | ±  | WON
T1  Jeff Rideout, Steven Hunt, Luke Mazanec,        9     30    -6   $46.00
    Jesse Saldana                                                  
T1  Jeff Young, Ale Dimas, Pat Youngs,              9     30    -6   $46.00
    Michele McCormick (blind)
T3  Adam Baker, Wade Lewis, Dan Stich,              9     31    -5
    Michele McCormick
...
```

How the number is built (Kerry: hole by hole, not total minus PH):

- Team NET = the sum, over holes the team has finished, of the best net ball on each hole (each player's gross on that hole minus the strokes they receive on that hole, by stroke index on their own tee). This is exactly the `TEAM NET` row in the expanded view, so collapsed and expanded always agree.
- A hole counts for the team once every ball on the card has posted it (blinds are pre-filled and never hold a hole **[CONFIRM]**). That keeps the number from flickering as the four players post at different moments. Team THRU is the count of those holes.
- `±` is Team NET minus par for those same holes. The row ranks on `±`, then THRU (more holes ahead), then name.
- No team handicap and no "total minus PH" anywhere in the row. If the allowance changes who gets strokes on which hole (the 75% team allowance on the cart, **[CONFIRM against side-games.md]**), that is already inside each player's per-hole pops, so the collapsed row needs no special case.
- WON on the row is the team purse once money shows (PROVISIONAL onward); blank before.
- UPCOMING: the collapsed row shows the team's tee time in the THRU slot.
- Tap anywhere on the row to expand; tap again to collapse. Each team opens and closes on its own. An Expand all / Collapse all control is an obvious add; not ruled, I would offer it (S).

Tab-landing effect: with TEAM the landing tab, one screen on a phone shows every team at a glance (about 6 teams of 4 on a 23-player night), which is the "who is winning, where do I stand" answer in one glance. Hole by hole is not needed on this tab.

### 11.7 What this changes in the fix list (section 6)

| # | Change |
|---|---|
| 2 | Becomes: tab order TEAM, MVP, NET, GROSS, SKINS, PROXIES; OVERALL off behind a setting (S) |
| 5 | The state strip uses the five words in 11.2 (M, with the closeout trigger) |
| 14 | SUMMARY: appears at FINAL (M) |
| new 16 | THRU column per 11.4, including the pre-event tee time and hole (M) |
| new 17 | TEAM collapsed row + expanded = current board, remove player expansion (M) |
| new 18 | Name display: First Last, stored casing, on every board including Season Contests (S, check `_proper_case` use) |

Suggested ship order for the next deploy that is safe before Tuesday's 3:35 PM: only the zero-risk display items (tab order, OVERALL off, name format). The ranking, THRU and TEAM collapsed row change member-facing numbers and layout on a live night, so I recommend they wait for the 10/27 deploy after Tuesday's live walk, unless Kerry wants them sooner (his call; rule 3b).

### 11.8 Questions for Kerry (one at a time, in this order)

1. PROXIES or CTPS as the tab word?
2. Where does SUMMARY sit in the tab row (my lean: last)?
3. Team hole counts when all four balls are posted (my rule) or as soon as one is? (I recommend all four; one ball makes the team number jump.)
4. Ship the safe display items before Tuesday, or hold everything for 10/27?


---

## 12. Kerry's second round, 10/19 evening (verbatim), and the build-ready spec

Kerry: "Not sure about having both FINAL and OFFICIAL. Not much difference and probably confusing to players. PROVISIONAL may be better said as IN REVIEW." / "Thru should be considered like in the PGA. When Thru is done, doesn't it show the final score there on the PGA leaderboards? So you'd show Thru and the +/- column, but after the round is complete, it would show the total Gross score. Before event starts it shows time and hole." / "Casing needs to respect the prefix casing. So DelCarmen would be DelCARMEN for member casing view. Like if MacBride was a member then it would be MacBRIDE." / "Make sure to highlight the scores that are counted for the team. If one player got the Team net low, then highlight green. If two players got it then highlight both green. Of course we need to build in TEAM Net 2 and 3 ball options too, where we're adding cumulative of the two best or three best net scores." / "Use CTPs if it's only CTP's that event. Use PROXIES if it includes something besides just CTPs like a LONGEST PUTT... That should be recognized by the GAMES tab based on course details and side chosen. Could also be the case where we want 4 proxies for an 18 hole event but there's only 3 Par 3s." / "SUMMARY would go first once the event is over and it reveals itself." / "Team's hole count...not sure exactly what you're asking, but I'm thinking you're saying it only counts once all players are entered?" / "I want everything built."

This section supersedes section 11 where they differ. Research and proposals only: **I cannot build; this lane writes the spec and Tracker Build builds it.** Nothing deploys without Kerry's "Deploy", and nothing goes out inside Tuesday's window (3:40 PM first tee through closeout).

### 12.1 Four words, not five

| Word | Means to a player | Board |
|---|---|---|
| UPCOMING | Pairings are set; nobody has teed off. | THRU column shows tee time and start hole |
| LIVE | Scores are coming in hole by hole. | Everything "to date"; WON blank |
| IN REVIEW | Every score is in. The money shows, but it is not settled: a score can still be corrected and results have not closed. | WON shows (marked in review). Lasts until closeout runs, about 20 minutes on a clean night |
| FINAL | Results are closed and prizes are set. | **SUMMARY appears, first in the tab row.** WON normal weight |

Behind the scenes nothing changes (the 15-minute card lock, the +5 closeout, `PROVISIONAL / FINAL / OFFICIAL` as internal states in code). Players just see two end words. FINAL = closeout fired and payouts recorded. A hold keeps the board at IN REVIEW with one line ("Results are being checked"). A correction after FINAL keeps it FINAL and adds "Corrected 8:30 PM".

My reading of "SUMMARY would go first once the event is over": it appears at FINAL, as the first tab, and the landing tab becomes SUMMARY from then on (TEAM before). Tell me if you meant it should appear at IN REVIEW, when the money first shows.

### 12.2 THRU, PGA style

Columns on a board that is not showing hole by hole: `± | THRU`, one cell with three states:

| Moment | THRU cell |
|---|---|
| Before the player tees off | tee time and start hole, "3:40 PM · 10" |
| In play | holes completed, "5" (the ± column beside it is to par for those holes) |
| Finished | the player's total for that tab's game: gross total on GROSS ("39"), net total on NET, points on MVP, team net on TEAM |

Suggested: show the finished state as "F 39" so a stroke total is never mistaken for a hole count. Question 1 below asks whether each tab shows its own score or always gross.

### 12.3 Casing (already coded, only the form changes)

`member_caps_name` (`database.py`, Kerry 9/11) already implements Kerry's rule for the "Last, First" form: a known prefix keeps its shape and the rest of the last name goes to capitals, so "McCrary" shows "McCRARY" and "DelCarmen" shows "DelCARMEN". It guards the false match: "Delgado" has no capital after "Del", so it is just "DELGADO". Members only (`is_member`); non-members and guests keep their normal case. Today it has one caller (`database.py` ~10936, Season Contests' member display). Needed: a First Last variant on the same tokenizer, used on every board, so "Michelle DelCarmen" reads "Michelle DelCARMEN", "Adam Baker" reads "Adam BAKER" for a member, and MacBride shows "MacBRIDE". One-line caveat: the boot step `_migrate_normalize_customer_name_case` rewrites all-uppercase names to proper case, so a hand-set "DelCarmen" is safe but an all-caps "DELCARMEN" arriving from an import would lose its prefix shape.

### 12.4 TEAM: counted balls, and 1 / 2 / 3-ball Team Net

- **Highlight every counted ball.** On each hole, every ball that counted for the team is green: one ball for Best 1; two for Best 2; three for Best 3. A tie that touches the cutoff highlights all the tied balls (they have the same net, so the score is the same either way). Today the cell shading is driven by the single low ball.
- **The board does not do N-ball yet.** `evlbTeamMins` (`contests.html` ~4305) takes `Math.min` of the four nets, i.e. Best 1 only, while the server already knows the event's ball count (`event_team_net_dial`, `allowance_pct_by_balls`) and pays by it. So a Best 2 night would pay on one thing and display another. This is the part that has to be built.
- **The number.** TEAM NET per hole = the sum of the N lowest net scores on that hole. The row total is the sum of those; ± is against N × par for the holes counted (so "-6" still means six under for a 2-ball). The collapsed row uses the same sum.
- **Allowances are already ruled** (side-games.md, Kerry 9/16): Best 1 75%, Best 2 85%, Best 3 and Best 4 100%. The standing rotation is Best 1 / Best 2 on alternating events, overridable to Best 3 / Best 4. The two-player cart ladder is still unresolved (CA Queue #8) and is not part of this.
- Heading and HOW IT WORKS read the same dial: "Team Net · best 2 of 4 · 85% allowance".

### 12.5 CTPs or PROXIES: one tab label, derived from the GAMES tab

- Label = **CTPs** when every contest at the event is Closest to the Pin; **PROXIES** when any is something else (a Longest Putt). Derived from the event's proxy slots before anyone wins, so the label is right from UPCOMING.
- The slot rule already exists (live-scoring spec and Test Center): CTP max 2 per nine; more par 3s than slots, the shortest are chosen; fewer par 3s than slots, the leftover becomes a **Longest Putt on the last hole** of the side. The reader already prints "Putt · n" (events.md). Kerry's examples fit: a nine with one par 3 is one CTP plus a Longest Putt on hole 9 of the side played; an 18 with three par 3s and four slots is three CTPs plus a Longest Putt on the last hole.
- To check, not assume: the side chosen. A back nine's last hole is 18; a shotgun start does not change "last hole of the side". Course card with no par-3 data (the Brackenridge seed case, events.md ~2855) must show a blank hole, never a made-up one.
- Open for Event Ops / Kerry: the CTP pot is split over the proxy contests today. Adding a Longest Putt adds a contest; whether the per-contest dollars change is a payout question (not in this lane).

### 12.6 TEAM hole count (Kerry's question, answered)

Yes: a hole counts toward the team's THRU and net only once **every player on that team has a score on it** (blinds are pre-filled and never wait). It keeps the team number steady: if the team counted a hole as soon as the first ball posted, the number would drop every time a better ball arrived. The cost: if a team's players are in different groups, the team's THRU follows the slowest player. Picked-up or no-card holes: a stuck or missing card is the Event Ops stale-card rule (out of scope here); a hole where a player has no score should still count as posted for the team if the card is closed. **[CONFIRM with Event Ops]**

### 12.7 Build list, in the order I would hand it over

| # | Build | Tier | Why this tier |
|---|---|---|---|
| B1 | Tab order TEAM, MVP, NET, GROSS, SKINS, PROXIES/CTPs; OVERALL off behind one setting | 1 | Display only, no numbers change |
| B2 | CTPs / PROXIES label from the slots (12.5) | 1 | Label only |
| B3 | First LAST casing for members on every board (12.3) | 1 | Display only |
| B4 | State strip with UPCOMING / LIVE / IN REVIEW / FINAL; one source for the minutes (12.1) | 1 | Wording and one line; reads existing state |
| B5 | Counted-ball highlight on the existing best-ball view | 1 | Shading only |
| B6 | Rank on to-par then holes done, on TEAM, MVP, SKINS (NET and GROSS already) | 2 | Changes the order members see |
| B7 | THRU column per 12.2 | 2 | New column and a layout change on phones |
| B8 | TEAM collapsed row, expanded = today's board, no player expansion (11.6, 12.6) | 2 | New layout on the landing tab |
| B9 | Team Net 2- and 3-ball on the board (12.4) | 2 | Board must match what the payouts do |
| B10 | SUMMARY first at FINAL (section 7, 12.1) | 2 | First place money appears together |
| B11 | "Playing for" line per tab (Build #2057) | 2 | Reads the GAMES tab |

Tier 1 is small and display-only: it can ride one deploy before Tuesday's 3:35 PM if Build has room and Kerry says "Deploy". Tier 2 changes what members read on a live night; it is safest built and tested against Tuesday's real data (a read-only walk, no push in the window) and deployed Wed 10/21 or by 10/27. Kerry may choose otherwise (rule 3b, member-facing).

### 12.8 Questions for Kerry, one at a time

1. On THRU: when a player finishes, does each tab show its own total (gross on GROSS, net on NET, points on MVP) or always the gross total?
2. FINAL / SUMMARY timing: appears when results close (about 20 minutes after the last score), or when the money first shows (IN REVIEW)?
3. Tier 1 before Tuesday, or all of it after?
