# Manager Event Report + Monthly Recap — SPEC v0 (docs only)

Owner: Event Ops (CGO). Written Wed 10/21/2026 for Kerry, due Fri 10/23.
Status: **proposal, not ratified**. Everything member-facing, money or schema
here waits on Kerry's word (rule 3b). Coordinating on the mailbox with the CFO
(money lines) and db-claude (pace). Nothing built, sent, paid or deleted.

Kerry, 10/21, verbatim: *"pace tables. Where do I review them? Where do I get a
managers event report showing event details like that and profitability and
overall event statistics. Some of that I know we need to define but stats like
pace need to go into it. Also need a monthly recap report. Brainstorm on what
these reports should show for event data, participation, etc that would be
helpful for a manager and me to see."*

## 0. Pace: where you can review it TODAY

- **Not in the Tracker yet.** The pace tables (migration 0037, `se_group_pace` / `se_player_pace`) passed db-claude's review (#2133) but are not deployed; they wait on your "Deploy" in Tracker Build. Until then there is no pace page.
- **What exists:** every hole's save time is kept (`se_audit`), and a read-only bridge shows them (`scoring-se-hole-times:<round>`). db-claude's 10/13 sample is in mailbox #2092.
- **Tuesday 10/20, computed from those save times** by the ruled method: first hole to second-to-last; a catch-up save under 2 minutes is spread over the two holes; the last hole is not used. Group = its first save per hole.

**s9.28 TPC Canyons (tee times from 3:40, all start hole 1). Sunset 6:59 PM.**

| Tee | Players | Min/hole | Est. 9 holes | Last score |
|---|---|---|---|---|
| 3:40 | Stich, Niester, Skinner (3) | 13.8 | 124 min | 5:41 PM |
| 4:30 | Baker, Mesa, Murphy, Hunt | 16.2 | 146 min | **7:04 PM** |
| 4:10 | M. Wade, Allen, Sharitz, R. Johnson | 16.4 | 148 min | 6:33 PM |
| 4:00 | McCormick, Peterson, Mazanec, P. Youngs | 16.6 | 150 min | 6:38 PM |
| 4:20 | J. Young, Copeland, Rideout, W. Lewis | 16.6 | 150 min | 6:45 PM |
| 3:50 | G. Vasquez, Kulawik, Wilson, Palacios | 16.7 | 150 min | 6:14 PM |

Holes, average minutes (groups): 2 **19.7** (6) · 3 13.6 · 4 12.2 · 5 16.6 · 6 **19.8** · 7 16.1 · 8 14.4. **Slowest: 6, 2, 5** (holes 2 and 6 are the par 5s). Holes 1 and 9: no clean time, since every group started on 1 and finished on 9.

Notes:
- The last group finished 5 minutes after sunset.
- The 4:00 group's first save (4:25) came after the 4:10 group's (4:16). They may have gone off in swapped order.
- The 4:20 group saved hole 9 early by mistake on two cards (fixed later). The method does not use hole 9, so it doesn't matter.

**a9.28 Avery Ranch (4:03 and 4:12, start hole 1). Sunset 6:55 PM.**

| Tee | Players | Min/hole | Est. 9 holes | Last score |
|---|---|---|---|---|
| 4:03 | L. Vasquez, Cannon, Zapata (3) | 13.8 | 124 min | 6:04 PM |
| 4:12 | Melchor, Compton, Sharp, Schneider | 16.2 | 146 min | 6:37 PM |

Holes: 2 13.4 · 3 **18.8** · 4 13.7 · 5 **19.7** · 6 11.2 · 7 **17.0** · 8 11.3. Slowest: 5, 3, 7.

- **Proposal, for Tracker Build to build after 0037 is deployed:** a staff-only page, **Event → REPORTS → Pace**, rendering db-claude's manager pace report (#2092: groups fastest to slowest with names, hole-by-hole averages, slowest marked, method line) for any played event. Read-only. Seed it with 10/13 and 10/20 so you can review the first two nights.
- The emailed version (morning after, to the manager, CC Kerry) is part 1 of the Manager Event Report below.

## 1. MANAGER EVENT REPORT

Staff only, never members. One page per event (both chapters' events on a night = two pages in one email).
- **When:** the morning after, about 7:30 AM, after the results email has gone and the night's numbers are settled.
- **To:** the chapter manager, CC Kerry.
- **Also on screen:** Event → REPORTS.

Legend for "Today": **HAVE** = in the Tracker now and readable; **PART** = some of it; **NEW** = not stored or not computed yet. **v1** = proposed for the first build.

### 1a. Event facts
| Line | Today | Where it lives / what is missing | v1 |
|---|---|---|---|
| Course, format, holes, tees used, start type and times | HAVE | events row, print pack (`get_event_print_pack`) | v1 |
| Field vs capacity | PART | field = roster; capacity = `events.tee_time_count` × 4. That column exists but is usually left 0 (the pairings use the roster's count instead), so it needs filling at event setup. No schema change. | v1 (field only where the count is blank) |
| Signup curve by day (orders per day from invite to lock) | HAVE | `items.order_date` + invitation send dates (`event_invite_sent`) | v1 |
| Late adds after lock, withdrawals, credits, no-shows | PART | credits/transfers on items; late adds in agent log / after-lock baseline (v2.577.0); **no-show (registered, no card) is computed at closeout but not stored** | v1 |
| Blinds drawn and why | HAVE | `blind_draws`, pairings | v1 |
| Weather | NEW | not captured; optional free-text by the manager | later |

### 1b. Participation
| Line | Today | Where / missing | v1 |
|---|---|---|---|
| Members / guests / first-timers | HAVE | `customers.current_player_status`, `first_timer_ever` | v1 |
| Returning vs lapsed back (first round in 60+ days) | HAVE | scoring rounds history (participation.md) | v1 |
| "Usually comes, didn't" (played 3 of the last 4 at this chapter, not here) | HAVE (computable) | participation analysis | v1 |
| Invitation → registration conversion; RSVP "can't make it" reasons | HAVE | `event_invite_sent`, `rsvps` tracker rows, `event_decline_reasons` | v1 |
| First-year players (joined this season) and their round count | HAVE | memberships + rounds | v1 |
| Acquisition source of first-timers | PART | `acquisition_source` / `found_us_via`, often empty | v1 (show "not recorded") |

### 1c. Pace (db-claude, #2092)
| Line | Today | Where / missing | v1 |
|---|---|---|---|
| Groups fastest → slowest with names, min/hole, estimated round, status | NEW (0037 undeployed) | se_group_pace; computable now from se_audit (above) | v1 |
| Hole-by-hole average, slowest holes | NEW | same | v1 |
| Last group finish vs sunset | NEW | last save time; sunset computed from the course location. **Course lat/long is not stored**: NEW columns or a lookup | v1 (if lat/long is added) |
| Pace trend at this course (vs prior visits) | NEW | needs 0037 history | later |

### 1d. Scoring
| Line | Today | Where / missing | v1 |
|---|---|---|---|
| Field average gross / net, low gross, low net | HAVE | scoring_rounds | v1 |
| Handicap movement (biggest up / down), new indexes | HAVE | `scoring-hcp-preview` / handicap rounds | v1 |
| Games activated and why one did not (buyer counts; ½ Net Skins below 8 gross) | HAVE | GAMES tab (`get_event_games`), side-games matrix | v1 |
| Skins count, CTP results, takeovers and who confirmed | HAVE | payouts, CTP claims (score entry) | v1 |
| Payouts by game, ties split | HAVE | payout rows, flights board | v1 |
| Card corrections and holds (parity, Unlocks, flags) | PART | se_audit, COO items; no single list | v1 |

### 1e. Money (CFO to confirm every line; tgf-margin skill)
| Line | Today | Where / missing | v1 |
|---|---|---|---|
| Revenue (entry + games + add-ons), refunds/credits | HAVE | `get_event_financial_summary`, allocations | v1 |
| Course cost (expected = field × rate; actual card charge) | HAVE | events.course_cost, expense rows | v1 |
| TGF markup / fee, processing fees, sales tax reserve | HAVE | allocations, fee splits, tax rules (tgf-pricing) | v1 |
| Prize fund in, prizes paid / pending; HIO contribution | HAVE | GAMES tab, payouts ledger, HIO pot | v1 |
| **TGF operating profit and margin per player** | PART | the CFO defines `tgf_operating` (what costs count: shirts, meals, software share?) | v1 once the CFO rules |
| Vs prior events at the same course | HAVE (computable) | same summary for earlier events | v1 |
| Collections owed (on roster, no paid entry) | HAVE | roster vs items (CA #885-2) | v1 |

### 1f. Operations
| Line | Today | Where / missing | v1 |
|---|---|---|---|
| Pairings approval time (prompt sent → approved), auto-send used? | HAVE | `pairings_approval` setting state | v1 |
| What was sent and when (invites, tee times, Event Info, course files, asks, results) | HAVE | message_log, send stamps; the 10/20 sequence (`screenshots/closeout-chain-2026-10-20/index.md`) is the template | v1 |
| After-lock changes and who was told | HAVE (from v2.577.0) | after-lock baseline | v1 |
| Closeout minutes: last score → final → recorded → verified → results scheduled | PART | times exist in card locks, payout rows, mailbox; **not stored as one record**. NEW `event_closeout_log` (rule 3b) | v1 |
| Holds and why (CTP, parity, manual rows) | PART | COO items, auto_payouts notes | v1 |
| Results email delivery (sent / failed / held) | HAVE | `results_email_schedule` last_run | v1 |

### 1g. Member experience
| Line | Today | Where / missing | v1 |
|---|---|---|---|
| Handicap coverage (players with a TGF index, asks open) | HAVE | missing-handicap warnings, handicap ask state | v1 |
| Venmo / payout handle coverage; payout asks open | HAVE | customers.venmo_username, payout ask state | v1 |
| Undeliverable emails, opt-outs touched by this event | HAVE | customer_emails.undeliverable, event_invite_optout | v1 |
| Results email opens / clicks | NEW | the Tracker's mail has no open tracking (Brevo does, for Brevo sends only) | later |

## 2. MONTHLY RECAP

For staff and Kerry. First business day of the month for the month before. Per chapter plus TGF total.
| Line | Today | Where / missing | v1 |
|---|---|---|---|
| Events held, unique players, rounds, average field, capacity use | PART | events + rounds; capacity from `tee_time_count` where filled | v1 |
| New / first-timer / returning / lapsed / lost (played last month, not this) | HAVE | participation | v1 |
| Retention cohorts (first-timers 30/60/90 days later) | HAVE (computable) | rounds + first_timer flags | v1 |
| Memberships added / renewed / ended / lapsed | HAVE | customer_memberships | v1 |
| Revenue and TGF operating profit by chapter, course, format (9 / 18 / championship) | PART | the CFO's tgf_operating | v1 once ruled |
| Games mix (buy-in rates per game, average pot) | HAVE | GAMES per event | v1 |
| Points: monthly winner, fall race movement | HAVE | tracker_points | v1 |
| Pace trend by course | NEW | 0037 history | later |
| Payouts total, paid vs pending, payout asks | HAVE | payouts ledger | v1 |
| Expenses by category | HAVE | expense_transactions | v1 |
| Sales tax collected vs reserved vs filed (ties to the 20th) | HAVE | tgf-sales-tax skill / allocations | v1 |
| HIO pot balance (start, in, end) | HAVE | HIO ledger | v1 |
| Owner draw and contributions | PART | ledger categories; the CFO confirms | v1 |
| Outstanding owed (collections, credits held) | HAVE | liability buckets (`scoring-liabilities`) | v1 |
| Email: invitation → registration rate; results email reach; Insider opens | PART | Tracker sends logged; open rates only from Brevo | v1 (no opens for Tracker mail) |
| Best / worst courses (profit per player, pace, turnout, member feedback) | PART | combination of the above; feedback NEW | v1 without feedback |
| Leads: new, contacted within 48 h, converted | HAVE | Lead Center | v1 |

## 3. Open questions for Kerry (one at a time)

1. **Who gets the event report?** Chapter manager + Kerry, morning after, about 7:30 AM?
2. **Capacity:** should the manager fill the number of booked tee times (`tee_time_count`, which already exists) on every event, so "field vs capacity" and "capacity use" can be shown? No schema change.
3. **Closeout log:** store each night's closeout times (last score, final, recorded, verified, results sent) as one record? That's a schema change.
4. **Course location:** add lat/long to courses so the report can show "last group vs sunset"?
5. **TGF operating profit:** the CFO proposes the definition. Which costs count against an event?
6. **Monthly recap:** send it on the 1st, or the first Monday?

## 4. Build order (proposal)

1. Deploy 0037 + the Pace page on REPORTS (Tracker Build; Kerry's "Deploy").
2. Manager Event Report v1: one page from HAVE lines only, by email and on REPORTS.
3. The CFO's money block once tgf_operating is ruled.
4. Monthly Recap v1.
5. The NEW fields (closeout log, course lat/long) as Kerry rules each; tee_time_count filled at event setup.
