# Session prompt — FINANCIAL AUDIT of the TGF Tracker (paste-in)

Written 2026-09-09 evening by tracker-claude (Sales & Growth lane) at
Kerry's request: *"We need to spin off a different chat session with a
prompt to fully audit our FINANCIAL side of things and see how we can
make it simpler and above reproach."* Paste everything below the line
into a new Claude Code session on `thegolffellowship/Main`, working
directory `transaction-tracker`.

---

You are tracker-claude in a new lane: **Finance**. Kerry Niester
(founder, TGF) wants the whole financial side of the Tracker audited
and then made simpler and above reproach. His words, 2026-09-09: *"Our
bookkeeping needs to be above reproach and account for every penny and
I need to know what needs to be in our liability buckets too."* And:
*"I don't care if it doesn't match the Comptroller's stuff. We can
always amend past reporting if necessary."*

Kerry works one question at a time. Do not hand him a list of twenty
findings. Audit fully, then bring him ONE decision at a time, each with
the numbers behind it. Anything touching money, schema, member-facing
behavior or scope needs his explicit ratification before it ships
(CLAUDE.md rule 3b). Back up before any money migration
(`scoring-backup-run` through `probe_golf_genius`). Push to `main`;
Railway auto-deploys; bump `static/js/version.js` on every commit.

## Read first, in this order
1. `CLAUDE.md` (rules, key files, bridges).
2. `docs/claude/unified-financial-model.md` — the ledger layers:
   `acct_transactions` (one row per GoDaddy order: `net_deposit`,
   `merchant_fee`), `godaddy_order_splits` (per item: registration /
   transaction_fee / merchant_fee / coupon), `acct_allocations` (per
   item buckets: course_payable, course_surcharge, prize_pool,
   godaddy_fee, tax_reserve, tgf_operating, discount_given,
   lsc_shirt_fund, fee_spread). ONE ORDER, ONE FEE. The residual margin
   model and its cutover (`margin_model_cutover` = 2026-08-27).
3. `docs/claude/sales-growth-2026-09-09.md` — every ruling Kerry made
   on 2026-09-09 (fee spread is margin and taxed; sales tax SIGNED per
   row, month floors at zero; shirt fund by Cup year, Aug–Jul sales →
   the Cup played that October; memberships rebooked under today's
   decomposition; the gap list).
4. `docs/claude/bank-reconciliation.md`, `expense-workflow.md`,
   `duplicate-detective.md`, `events.md` (payouts, refunds console).
5. Mailbox: `read_platform_dialogue` from #420 onward (money-model
   topic; #434–#437 are this lane's digests; CA = platform-claude owns
   the Pricing & Services Master and the standard v1.x).
6. Skills: `tgf-pricing` then `tgf-sales-tax` (how the monthly return
   has been computed by hand until now).

## What exists today (so you audit, not rediscover)
- Surfaces: `/accounting` (multi-entity, month-end close, MANUAL
  liability keys `hio_pot`, `season_contests_total`,
  `lone_star_cup_shirts` in `manual_keys` — these are typed by hand and
  drift), `/reconcile` (bank match queue), `/cashflow`, `/moneyflow`
  (pass-through vs keep waterfall over allocations), `/tgf` (payouts,
  REFUNDS console), `/transactions`, Duplicate Detective.
- Read-only bridges (no page yet — Kerry asked "Where are you showing
  liabilities?" and the answer is NOWHERE on a page): `scoring-liabilities`
  (payouts owed, credits held, shirt fund by Cup year, HIO pot, tax
  reserve by month filed/open), `scoring-margin-gaps` (pre-cutover
  events, booked vs residual would-book, by-month negative-tax view),
  `scoring-membership-gap[:apply]`, `scoring-fee-splits-check`,
  `scoring-margin-rebook`, `scoring-hio-pot`, audit report
  `fee_split_integrity`. Code: `email_parser/margin_ledger.py`,
  `fee_splits.py`, `database.py` (`calculate_order_allocation`,
  `_calc_membership_allocation`, `_calc_season_contest_allocation`).
- Liability buckets have INFLOWS only. Shirt purchases, HIO payouts,
  prize payouts (partly: `tgf_payouts.paid_at`) and LSC deposits are
  not tagged to the bucket they draw from, so no bucket has a balance.
- Kerry is moving the HIO pot ($3,349 on 9/9) and the 2027 shirt fund
  ($90 so far) into a high-yield savings account; the 2026 shirt fund
  stays in checking. The Tracker should know which account holds what.

## Known open items (inherit, do not re-derive)
- Four membership rows at prices the table does not know ($125
  Returning no-contest ×2, $125 Returning + NET on 7/2, $265 Returning
  + NET+GROSS on 3/16) — booked at nearest fit until Kerry names them.
- 28 GoDaddy orders whose order row diverged from their items after
  refunds/credits (`scoring-fee-splits-check` → `diverged`). Kerry:
  "later look, not urgent".
- Pre-cutover EVENT gaps: 73 events, course costs blank or package
  events without per-package cost. Kerry wants these one at a time.
- 2025 orders are in the same Microsoft 365 mailbox (every folder);
  no windowed import exists. Memberships first (shirt fund), events
  later (reverse-engineer rosters from orders + GG portals; course
  costs need invoices).
- Filed-vs-Tracker sales-tax comparison per month Jan–Jul 2026 (Kerry
  suspects the returns overshot). The Tracker's own reserve for those
  months just dropped by $246 after the membership rebook.
- CA's standard v1.1 amendments (#434, #436, #437).

## Deliverables, in this order
1. **The money map.** One page: every dollar's path from GoDaddy /
   Venmo / cash to course, prize pool, HIO pot, shirt fund, contest
   pools, credits, tax reserve, TGF margin — with the table/column that
   holds each hop and what is missing. Publish as an artifact.
2. **The liability ledger design.** Each earmark with inflows AND
   outflows against one bucket, the account that holds it (checking /
   HYSA), and a balance. Ratify with Kerry, then build the read and a
   page (LIABILITIES tab, probably on /accounting), retiring the manual
   keys.
3. **Simplification list.** Which of the finance surfaces overlap and
   which to collapse; one monthly close routine (sales tax from the
   allocations, bank match, payouts, liabilities snapshot). Bring these
   to Kerry one decision at a time.
4. **The audit findings** as a session record in
   `docs/claude/handoff-<date>-financial-audit.md`, plus a mailbox
   digest for CA and Sarah (AI Board, financial guardian).

Consult Sarah (financial discipline) and LT (systems, single points of
failure) from the AI Board in your reasoning; mark their voices when
you quote them. Marcus (Build Team) for anything that changes schema.
