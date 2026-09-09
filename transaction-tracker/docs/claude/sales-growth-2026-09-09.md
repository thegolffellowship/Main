# Sales & Growth lane — session record, 2026-09-09

A Claude Code session on this repo dedicated to **leads, the sales
funnel and TGF growth**. Pushes go straight to `main`. Reads the
mailbox (`read_platform_dialogue`) and the Tracker docs at the start of
every session so CA (platform-claude) and the other Tracker sessions
are never out of step. Mailbox posts from this lane are signed
`tracker-claude` with topic `sales-growth`.

## Where the Fall 2026 Lead Campaign is (verified live, 10:55 AM CDT)

**The campaign is over and nothing has replaced it.** Meta
`120253511733060195` ("TGF Leads Campaign - Fall 2026 Season") ran
8/27 9:57 PM → Sun 9/6 10:00 PM CDT (`stop_time`). It still reads
ACTIVE in Ads Manager but has spent $0 since 9/6, and no campaign or
ad set has been created on act_2353186181735308 since. The Lead
Center's newest lead arrived Sun 9/6 9:22 PM CDT; the HubSpot
watermark is 9/8 5:17 PM and found nothing. Kerry's stated plan
(mailbox #396) was a new campaign with new creative when this one
ended; CA (#400) said the creative decision sat on the Sep 7 retro
agenda. No outcome is posted anywhere. **Three days of dark, and
counting.**

### Meta, final (Marketing API, `date_preset=maximum`)

| | Campaign | SA ad set | Austin ad set |
|---|---:|---:|---:|
| Spend | $199.62 | $132.71 | $66.91 |
| Impressions | 21,305 | 15,242 | 6,063 |
| Reach | 9,183 | 6,178 | 3,137 |
| Frequency | 2.32 | 2.47 | 1.93 |
| Link clicks | 539 | 385 | 154 |
| CTR | 5.57% | 5.84% | 4.90% |
| CPM | $9.37 | $8.71 | $11.04 |
| Form leads | 129 | 89 | 40 |
| CPL | $1.55 | $1.49 | $1.67 |

Daily budget $20. Day by day:

| Day | Spend | Impr | Link clicks | Leads | CPL |
|---|---:|---:|---:|---:|---:|
| Thu 8/27 (launch 9:57p) | $4.53 | 238 | 8 | 1 | $4.53 |
| Fri 8/28 | $22.64 | 2,165 | 70 | 16 | $1.42 |
| Sat 8/29 | $14.37 | 1,322 | 47 | 7 | $2.05 |
| Sun 8/30 | $21.67 | 2,444 | 73 | 15 | $1.44 |
| Mon 8/31 | $22.57 | 2,837 | 74 | 17 | $1.33 |
| Tue 9/1 | $20.96 | 2,874 | 77 | 16 | $1.31 |
| Wed 9/2 | $16.72 | 2,031 | 44 | 12 | $1.39 |
| Thu 9/3 | $15.93 | 1,590 | 42 | 13 | $1.23 |
| Fri 9/4 | $19.31 | 1,953 | 38 | 14 | $1.38 |
| Sat 9/5 | $22.70 | 2,040 | 27 | 7 | $3.24 |
| Sun 9/6 (ended 10p) | $18.22 | 1,811 | 39 | 11 | $1.66 |

Reads: CPL sat in a $1.23–$1.44 band on weekdays and doubled on both
Saturdays. Click-through decayed from 3.2% of impressions (8/28) to
1.3% (9/5) at frequency 2.3 — creative fatigue was arriving right as
the campaign ended, which supports new creative for round two rather
than a restart of the same ads. Meta receipts in Outlook: $0.01
(8/27, advertising credit), $75.00 threshold bill 8/31 (SA $53.72,
Austin $21.28). Ad approvals 8/28, 8/30 and 9/3 (the 9/3 approval is
a mid-flight ad edit, not a new campaign — nothing new exists on the
account). An Ads Manager notification on 9/9 says "5 alerts including
payment issues and policy updates" — unread, worth opening.

Historical context (#396): previous best CPL $2.90, blended $3.22 over
432 leads. This one is the best by a wide margin.

### Tracker funnel (`scoring-campaigns`, 10:57 AM CDT)

All campaigns: **131 leads** (129 Meta + 2 manual referrals), 102
touched, 56 replied (54.9%), 35 interested, **15 players, 5 members**,
14 registered events, 29 dismissed, **0 new**. CPL $1.52 · CPP $13.31
· CPMem $39.92. Trailing window open to 10/6.

| Chapter | Leads | Touched | Replied | Interested | Players | Members | Dismissed |
|---|---:|---:|---:|---:|---:|---:|---:|
| San Antonio | 88 | 68 | 39 (57%) | 25 | 10 | 4 | 20 |
| Austin | 42 | 34 | 17 (50%) | 10 | 5 | 1 | 8 |

Value: collected $1,303 · booked margin $282.35 · actually left
$227.77 (see the fee note below) · ROAS on margin 1.41× booked / 1.14×
actual. Reconciliation: Meta says 129, Tracker holds 123 attributed +
8 unattributed = 131; the 6 "unattributed" Meta-window leads are the
HubSpot attribution loss (#398), the 2 extra are the referrals.

### First touch is fine. Follow-up is the leak.

From the 100-row Lead Center read (`get_lead_center`, limit 100):
arrival → first touch median **1.7 hours**, max 40.5 h, **zero** past
48 h. Kerry's own notes on 33 leads; auto-notes on all. But
`follow_up_at` is past due on **36 of the 39** leads that carry one
(due 9/6, 9/7, 9/8) and 3 more are due today. 37 touched leads have no
reply yet (Texted 17, Followed up 16, Sent email 4). The morning digest
lists them daily; nothing marks them done.

Tags: Followed up 24 · Interested 23 · Texted 21 · No answer 10 ·
Registered event 9 · Sent email 4 · Became member 3 · Too expensive 2.
Form answers: availability Both 61 / Sat 29 / Tue 7 / Neither 1;
priority All-of-it 48 / Community 17 / Golf 17 / Competition 16;
invitations SA 52 / Austin 27 / Both 18 / No 1. Nine of twelve
converts said "both days".

Data quality: 9 leads have no `customer_id` (7 because no surname on
the Facebook form: Joey 129, Randy 126, Lance 120, Joaquin 108, Cody
95, Brendan 69, Jaden 49); `touched_by` is null on 96/100 (attribution
lives in `notes_log`); two "Randy" leads 10 minutes apart from the SA
ad set (127, 126) may be one person; `lead_notify_recipients` holds
only Austin.

### Email and Brevo

Brevo #15 "TGF Insider" (9/2): 1,274 sent, 1,245 delivered, 398
unique opens (32% incl. Apple MPP), 102 trackable views, 80 unique
clicks, 4 unsubscribes. Kerry ratified weekly through 10/31 (#401);
the second send is due Wed 9/9 and has not been created. Renewal
drip mail went out 9/8–9/9 (Brian Westgard, Eddie Kim, Jake Hynds
"one last note"; Billy Gwin "expires today").

## The fee finding (Kerry, this session) — shipped v2.348.1

Kerry: *"I don't think the FEE NET lines are correct for Will
Wallace's transactions. Transaction fee on the one attached with
multiple line items was $10.92. My calculation for GoDaddy fees is
$9.66. So the diff is +$1.26 which would be prorated across all of
those line items."* Correct. Verified in the stored rows
(`get_godaddy_order_splits`): order R343961029's four items each
carry a `transaction_fee` split of $10.92 (the order's fee), while
`merchant_fee` is pro-rated ($3.56 / $1.87 / $2.03 / $2.20 = $9.66).
The table summed the stamped rows: $43.68 of fee-in, +$33.90 fee-net,
against a true +$1.26. Same on Michele McCormick's two-item order
($3.99 on both rows). `money_in` reads the deposit and was never
affected, so ACTUALLY LEFT was right; only the fee columns lied.

Fixed read-side (fee-in apportioned by registration amount, the same
basis as the deposit), and ACTUALLY LEFT now deducts the $10 LSC
shirt set-aside that BOOKED already deducted (memberships had been
reading as "overstated" by exactly $10). 103 checks pass. Live as
v2.348.1.

### Kerry's second point: "differences of amounts as an accepted standard"

The OVERSTATED column exists because three things disagree, and each
has a different fix:

1. **Fee duplication at the source.** The parser stamps the order's
   3.5% fee on every item row; the splits writer copies it; the
   allocator splits the GoDaddy fee **equally** per item; the campaign
   table splits the deposit **by registration share**. Three
   apportionments of one fee. Money Flow RETAINED carries the same
   duplication ($1,098.32 across 145 multi-item orders, #423 §2),
   still untouched. **Needs Kerry:** ratify rewriting the split rows
   (and the allocator's per-item fee) on ONE basis — by item price
   share — for the 145 multi-item orders. It is a migration of money
   records other reports read, which is why it was held (#418).
2. **Pre-cutover allocations book the rate card.** Rows dated before
   `MARGIN_MODEL_CUTOVER` 2026-09-05 book the event's standard markup
   regardless of what the player paid, so a 1st Timer round shows
   +$8 booked / −$6 actual. Kerry and CA ratified forward-only (#420
   C, "won't restate history"). **Needs Kerry:** restate the
   campaign-window rows (8/27 onward, 10 rows), all of 2026, or leave
   history as booked. Caveat: restating changes the tax reserve on
   months already filed — the open CPA question (#423).
3. **Rounding between equal-split and share-split** (±$0.03–$0.48 per
   row). Disappears with item 1.

Once 1 and 2 are ruled, the table should reconcile to $0 and the
OVERSTATED column becomes a red flag rather than a standing feature.

## Ratified and applied (later the same day): one order, one fee — v2.349.x

Kerry asked for the industry standard rather than an invented one
(options page: `https://claude.ai/code/artifact/c7b5be08-9984-4e43-9ac7-28a0c32641de`)
and chose D: the fee stays once per order in the ledger; item shares
for reporting are pro rata by item price. *"So the running example is
what happens first and then D is how it is backfilled (prorated) for use
in our table? If so, then it seems like you can go ahead, yes."*

Applied to production 2026-09-09 ~17:20 UTC after a verified backup
(`tracker_20260909_170331.db.gz`): 59 of 61 multi-item orders rewritten,
113 allocation rows re-stamped, fee-in across multi-item orders $1,072.94
→ $491.18, merchant totals unchanged, integrity 0 offenders. Will's four
rows now net +$1.26. Mailbox **#433**.

The first dry-run caught a wrong assumption (fee derived from the order
row, which can drift after refunds) and nothing was applied until it was
corrected in v2.349.1. **28 orders are DIVERGED** (order row ≠ item
rows) and were left alone — classes and order ids in #433 §5.

Still showing on the campaign table: $64.58 "overstated", which is
Question 2 (pre-cutover rate-card rows + the fee spread's home).

## Question 2, ratified and applied: the fee spread is margin, and taxed — v2.350.x

Kerry: *"the spread should be inside the TGF Margin and in my mind is
the part that gets taxed as it's basically a markup over and above (or
below) what the actual GoDaddy fees are ... Somewhat similar to the
'rounding up' concept with the course fees."* The allocator books each
item's spread into `tgf_operating` from the 9/5 cutover on (new column
`fee_spread`), the 8.25% reserve follows, pre-cutover rows stay frozen.
Rebooked on production (`scoring-margin-rebook:2026-09-05|apply`): 32
orders, 35 rows, spread +$6.53, 13 never-allocated registrations
created on the way. Mailbox **#434** carries the standard amendment for
CA (spread is in the tax base; the GoDaddy-covering part is not).

Question 3 (open): the pre-9/5 rows that book rate-card markup.

## Kerry decisions this lane is waiting on

- **Round two of the lead campaign** — the biggest lever on the board.
  Creative, budget, dates. Every day dark is ~13 leads at $1.55 not
  arriving. (Meta lead-row retention assumption is 90 days, so the
  Fall rows are safe until late November; the webhook path needs the
  `leads_retrieval` use case on TGF App 1418313969582528.)
- The 36 overdue follow-ups (9/6–9/8) — work them or re-date them.
- SA `lead_notify_recipients` address (asked in #429, #430, #431).
- Fee migration and pre-cutover restatement (above).
- Registration URLs on events — P7/P7b follow-up texts still send
  without the link sentence (#419).
- Brevo send #2 (weekly recap cadence ratified 9/3; due today).

## Open with CA, unchanged

#428 asks 1–7 (three need nobody: Luke Youngs cid 13 → `lsc_accepted`;
reply-rate denominator; name the four unmapped ad sets). #416 referral
questions. Money Flow decision. Pricing & Services Master v2.3. CPA
question. `lead_email_subjects` unratified.

## Sources read this session

Mailbox #353–#431 (highest id 431); `docs/claude/leads.md`,
`TGF_Tracker_LeadCenter_Context_v1_0.md`,
`hubspot-decommission-directive.md`,
`Update_Fragment_2026-09-03_Data_Safety_and_HubSpot_Exit.md`,
`session-prompt-2026-09-10-next.md`,
`handoff-2026-09-09-event-closeout-first-run.md`; Outlook (Meta
receipts, ad approvals, Ads Manager alerts, Brevo/renewal sends);
Meta Marketing API via the Meta MCP; Brevo campaigns API;
`get_lead_center`, `scoring-campaigns`, `get_godaddy_order_splits`.
