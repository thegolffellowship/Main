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

## Question 3 and the rulings that came with it (evening) — v2.351.0

Kerry, verbatim: *"All memberships fund shirts but here's how it needs to
be allocated. August 2025 thru July 2026 goes to 2026 Lone Star Cup shirt
fund, while August 2026 to July 2027 goes to 2027 shirt fund. The shirt
fund needs to have it's own column in the lead breakdown."* · *"I'm fine
with moving the margin-model cutover back to 8/27, but ultimately I want
you to tell me where the gaps are in the past event costs ... I don't
care if it doesn't match the Comptroller's stuff. We can always amend
past reporting if necessary. Our bookkeeping needs to be above reproach
and account for every penny and I need to know what needs to be in our
liability buckets too."* · *"I want to be able to see that ACTUALLY LEFT
and OVERSTATED column reduced to one column, MARGIN ... Then perhaps a
column that computes tax liability for sales tax."*

Done: cutover dial → 2026-08-27, window rebooked (87 orders, 57 rows,
margin −$122.71, tax −$6.95, Aug+Sep only). Table: Paid · Fee net ·
Course · Prizes · Shirt fund · Margin · Sales tax · Check; pre-cutover
rows flagged "rate card". New reads `scoring-margin-gaps` and
`scoring-liabilities` (`email_parser/margin_ledger.py`).

### Liabilities snapshot (2026-09-09)
Prize payouts owed $838.01 (34 rows) · credits held $110.70 (2) · LSC
shirt fund 2026: 108 memberships = $1,080; 2027: 9 = $90 (shirt purchases
not yet tagged to the fund) · sales-tax reserve open: Aug $143.48 (due
9/20) + Sep $61.45 = $204.93; Jan–Jul filed ($2,034.64 reserved).
Sidebar from Kerry: long-term liabilities into a high-yield savings
account — routed to CA / Sarah (mailbox #435).

### The gap list (pre-8/27 history, 73 events, 1,257 rows)
Books say $25,408 of margin; today's residual model would book $28,299.
The difference is DATA, not model. What Kerry needs to supply, by class:
1. **Memberships (110 rows, booked $8,661 vs $5,691):** the membership
   price list by period and what each tier included (New/Renewal/Plus,
   contest add-ons, $6 pool), so the tiers of the day can be encoded.
2. **Items with no events row at all:** 2026 HILL COUNTRY MATCHES (27),
   Austin Kickoff SHADOWGLEN (23), San Antonio Kickoff CEDAR CREEK (24),
   s9.9 TPC CANYONS (37), s9.16 TPC OAKS (28), s9.10 BRACKENRIDGE (19),
   San Antonio Kickoff NORTHERN HILLS (1), a18.2 CRYSTAL FALLS (11).
   Need: course cost per player and the prize structure.
3. **Package events:** 2026 TGF CHAMPIONSHIP (29 rows; per-package course
   cost), s18.10 FALL KICKOFF Landa Park (24).
4. **Events rows with course cost blank:** s9.2/s9.7/s9.12/s9.20 Canyon
   Springs, s9.3/s9.8/s9.13/s9.17 Silverhorn, s9.4/s9.15/s9.19 Quarry,
   s9.5 Brackenridge, s9.14 Hill Country, s9.9 TPC SA Canyons, a9.3 Avery
   Ranch, a9.5 Star Ranch, s18.1 Cedar Creek. Need: course cost per player.
5. **No gap, ready to restate on Kerry's word** (course cost present;
   only the 1st-Timer discount shows): s18.7 Kissing Tree, a9.11 Riverside,
   a9.20/a9.8 Avery, a9.12 Roy Kizer, s18.4 Landa, s18.8 Vaaler, a9.19
   Teravista, a9.18 Forest Creek, a9.10 Star Ranch, s9.21 Canyon Springs.

### Walk-in 1st Timers (Hightower, Hammond — a18.5 Forest Creek) — PROPOSAL, not built
Kerry: *"They aren't from our Leads ad ... but we still need to be able
to track them in LEADS. They should be filterable as not part of any
Leads Ad."* Map:
- **Capture:** when a GoDaddy order lands for a customer with no prior
  purchase history and no lead row, auto-create a lead: `source='organic'`,
  sub-source `store_order` (new value in the ratified list), chapter from
  the event, `status='converted'` + tag "Registered event", campaign =
  Unattributed / organic (so CPL/CPP never see them). Also on the
  manual path today.
- **Filter:** a source chip "Store 1st Timers (no ad)" beside the campaign
  select; the ALL funnel counts them, campaign cost math does not.
- **The clock:** their 48-hour clock is a PRE-EVENT touch, not a sales
  touch: a new preset (P11 "you're in for Saturday") that asks for a
  handicap index and offers the ropes-buddy line; the reply logs as a
  note and the manager enters the index as the starting handicap.
  Post-event: the first-timer follow-up template the closeout skill found
  missing (Phase 5.2).
- **Brevo:** GoDaddy→Brevo already puts them on the new-contact series;
  the nightly sync should stamp TGF_FIRST_EVENT (date) so the series can
  branch before/after the first round.
- **Now:** Hightower and Hammond added by hand as the first two rows once
  Kerry says go.

## Kerry's evening round of questions, answered and shipped — v2.352.0

Kerry, on the new table and the liabilities read:

- *"Lone Star Cup isn't in July. The Cup is typically in October of
  that July. That's the point. To allow time to order shirts with what
  was collected prior to City & TGF Championships as the funding
  source."* — The mapping (Aug–Jul window → that year's Cup) was right;
  the WORDING "that July's Cup" was wrong. Fixed in `lsc_fund_year`,
  the liabilities rule text, the docs and CLAUDE.md.
- *"Left align BOUGHT and DATE columns and adjust width automatically
  to widest. Change BOUGHT to ITEMS."* — Done (`.ld-margintbl`, first
  three columns left, nowrap, 1% width so they take their content).
- *"Shouldn't minus margins be minus sales tax too? ... Comptroller only
  asks for Total Sales and Total Taxable Sales for the month, not the
  per transaction breakdown. So in my mind, that seems like something
  that should reduce my Total Taxable Sales amount."* — RULING:
  tax_reserve is signed per row; the month nets and floors at zero.
  Supersedes the 9/5 per-row floor (#420). Per-row floor removed at
  both allocation sites; `liability_buckets` carries
  `tax_reserve_signed_sum` beside the floored `tax_reserve`.
  Applied on production with `scoring-margin-rebook:2026-08-27|apply`:
  94 rows, 14 restamped (all 1st-Timer loss-leader rows on s9.21
  Canyon Springs, a9.21 Star Ranch, s9.22 Silverhorn, a9.22 ShadowGlen,
  s9.23 Quarry), margin unchanged, tax reserve −$5.59 (Aug −$2.05 →
  $141.43 due 9/20; Sep −$3.54 → $57.91). Open total $199.34.
- *"are you only able to track memberships from January this year?"* —
  Tracker order history begins 2025-12-29 (`records_from` now on the
  read). The 2026 fund's 108 is a FLOOR; Aug–Dec 2025 memberships need
  a source (GoDaddy order export or the HubSpot archive).
- *"Shirt fund 2027 is including some that are renewals at $75 right?"*
  — Yes: 9 rows since 8/1 = 7 New (incl. Kannon Brown at $100) + 2
  Returning at $75 (Joshua Bartz, Andy Sanford). All memberships fund
  shirts.
- *"What do you mean that the shirt purchases aren't tagged to the fund
  yet? Are you talking about our liability accounts for shirts, Hole In
  One Pot, etc.?"* — Yes. The read shows inflows only; the expense side
  (shirt orders) is not linked, so there is no BALANCE. Each earmark
  needs both sides against one bucket: prize pools → payouts, HIO pot,
  shirt fund by Cup year, credits, LSC deposits, tax reserve. HIO pot
  is not yet in `scoring-liabilities` (it lives in `scoring-hio-pot`)
  — to add.
- *"as opposed to what with Hightower and Hammond?"* — As opposed to
  waiting for the automatic walk-in capture to be built. They are in
  now: leads 133 (Geoff Hightower) and 134 (Zac Hammond), source
  organic, Austin.
- *"We'll need to address the GAPS one at a time"* — agreed; nothing
  pushed until Kerry picks the first group. Recommendation: memberships
  (largest swing; also the shirt-fund input).

Mailbox **#436** carries all of it for CA.

## Round two of the evening (v2.353.0)

Kerry picked memberships. `scoring-membership-gap` (measure): 117
rows, 16 groups, 13 fit today's table; margin $8,949.20 → $5,943.00
(−$3,006.20), pools $1,536 → $3,262, shirt set-aside $100 → $1,170,
tax base −$247.73. Misfits (4 rows): $125 Returning no-contest
(Campos, Cheshire), $125 Returning + NET (Miller), $265 Returning +
NET+GROSS (Lourigan). Apply is Kerry-gated. FALL Net Points Race now
decodes inside a membership (Kannon Brown rebooked: $59.20 → $44.20
margin, $46 pools). Lead attribution window is indefinite (Kerry).
HIO pot ($3,349 through 9/12's field; $3,336 played) is in the
liabilities read; Kerry is moving it and the 2027 shirt fund to a HYSA.
Gap list by_month gives the negative-row tax credit per filed month
(Jan–Jul ≈ −$89, indicative). Mailbox #437.

## Kerry decisions this lane is waiting on

- **Apply the membership rebook** (`scoring-membership-gap:apply`).
- **The three prices the table does not know** ($125 no-contest, $125
  + NET on 7/2, $265 + NET+GROSS on 3/16).
- **2025 import**: date range (Aug 1–Dec 28 2025 for the shirt fund, or
  all of 2025), confirm same mailbox, go on the parse spend. Needs a
  windowed import bridge (not built).
- **HIO pot into the liabilities read** + expense tagging to the
  earmark buckets (the "balance" side) — scope with CA's chart of
  accounts.
- **Automatic walk-in 1st-Timer capture** (#435 §6 design) — build or
  not.

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

Mailbox #353–#436 (highest id 436); `docs/claude/leads.md`,
`TGF_Tracker_LeadCenter_Context_v1_0.md`,
`hubspot-decommission-directive.md`,
`Update_Fragment_2026-09-03_Data_Safety_and_HubSpot_Exit.md`,
`session-prompt-2026-09-10-next.md`,
`handoff-2026-09-09-event-closeout-first-run.md`; Outlook (Meta
receipts, ad approvals, Ads Manager alerts, Brevo/renewal sends);
Meta Marketing API via the Meta MCP; Brevo campaigns API;
`get_lead_center`, `scoring-campaigns`, `get_godaddy_order_splits`.
