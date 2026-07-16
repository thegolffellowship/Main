# Financial Audit — Deliverable 1: Whole-Tracker Gap Report (READ-ONLY)

**tracker-claude, 2026-07-16. Charter: `financial-audit-charter.md`. Data:
live Railway DB via the `scoring-fin-audit` bridge (v2.116.2); every figure
from pure SELECT/PRAGMA — nothing was mutated.** 103 live tables audited
across lens A (`customer_id`), lens B (financial homes), lens C (FK
integrity). Kerry ratifies before any fix ships (rule 3b).

## How to reproduce every number

`probe_golf_genius` with
`extract="scoring-fin-audit:<tables|customer|fks|ledger|money|dupes>"`.
"Live" rows = status NOT IN (reversed, merged) — `reconciled` is live
(bank-matched). Lens-A coverage tables count ALL statuses. Dollar figures
are absolute sums on the gap rows.

Ledger scale: 4,889 `acct_transactions` rows — 2,816 active, 602
reconciled, 1,470 reversed, 1 merged.

---

## RISK-RANKED FINDINGS

### 🔴 P0 — money attributed to nobody (rule-6 violations at scale)

**F1. `exp-promoted` ledger rows: 367 of 850 live rows have NULL
`customer_id` — $162,176.84 unattributed.** The charter's known gap #1,
confirmed and quantified. The email→expense→promotion pipeline resolves
the customer once at capture and gives up silently. In the
`expense_transactions` staging table itself, 390 of 920 rows (42%) are
NULL ($272k gross). Breakdown by kind:
- `payout` (Venmo prizes TO golfers): 52 of 480 NULL — real people we
  paid, unlinked (the Lee Vasquez −$146 class).
- `received` (Venmo income FROM golfers): 18 of 110 NULL — real people
  who paid us, unlinked.
- `expense`/`transfer`: 313 NULL — mostly vendor spend (courses, Costco)
  and bank moves. Vendor customer profiles exist (cids 393-402,
  role=vendor) but the pipeline never links them, so rule 6 is unmet
  even where the answer already exists in `customers`.

**F2. One-shot identity resolution, never re-resolved.** Confirmed
structurally: nothing re-scans NULL-customer rows when
`customer_aliases` gains a row. The boot-time backfill registry covers
10 tables but NOT `expense_transactions`, and the `acct_transactions`
backfill cascade doesn't consult `other_party_handle` (the Venmo
@handle we already capture) or alias names on exp-promoted rows.

**F3. `acct_transactions` overall: 487 of 4,889 rows NULL `customer_id`
($174,125.68 all-status); 32 live name-only rows (`customer` text set,
id NULL — $10,798.74).** Live rows by source: `chase_alert` 280 of 293
NULL (vendor class, $148k of source total), `venmo` 95 of 1,322,
`csv_import` 33 of 33 (F8), `receipt` 24 of 25, `manual` 27 of 180,
plus 9 `refund` / 9 `add_payment` / 7 `external_payment` legacy rows
with NULL amounts AND NULL customer (zero-information placeholders).
**Floating money (no customer, no item, no event, live):
359 expense rows $146,851.90 + 37 income rows $12,109.74 + 25 transfer
rows $15,100.04 + 60 legacy rows.**

### 🔴 P1 — the ledger is not yet the single source of truth

**F4. No `event_id` column on `acct_transactions`; 1,406 live rows carry
an `event_name` string that matches nothing in `events.item_name`.**
Event linkage from the ledger is by display string only — the same
name-only anti-pattern rule 6 bans for people. EVENTS-as-a-window into
the ledger is impossible until ledger rows carry `event_id` (resolved
via `event_aliases` like the other 8 backfilled tables).

**F5. Four ledger designs coexist in one database.** (a) The flat
unified entries (`entry_type`/`amount`) — the intended source of truth;
(b) 61 live LEGACY rows (`total_amount`/`type`, `entry_type` NULL, 60
of them customer-less — invisible to every flat-entry consumer);
(c) the `acct_splits` era (997 rows) + `acct_entities`/`acct_categories`;
(d) abandoned skeletons `general_ledger` (0 rows) and
`bank_statement_rows` (0 rows). Only one can be the ledger of record.

**F6. `tgf_payouts` computed-vs-actual — structurally BETTER than
feared, but unpoliced.** All 780 payout rows have `customer_id`, all
780 link to a ledger row, 745 are paid, 0 link to dead rows. Judged per
lump payment (one Venmo covers several category payouts), variance
exists on **25 lumps totaling only $52.14 absolute, max single variance
$3.00** — everything inside the ±$3 match tolerance. The gap is that no
variance REPORT exists and the tolerance is silent: a recurring exact
−$3.00 pattern (at least 6 lumps) suggests a systematic $3 delta worth
a ruling, and reconcile-down-to-actual (authority hierarchy) is not yet
recorded anywhere.

**F7. Money stored as TEXT.** `items.item_price` / `total_amount` /
`transaction_fees` / `coupon_amount` are dollar-formatted strings
('$182.00'): live typing = 1,480 text + 271 NULL. Naive SUM() returns
$0.00 silently (stripped/CAST the real total is $143,691.67, matching
`get_statistics`). `items.parent_item_id` is likewise TEXT ("1853").
A CPA-facing credibility problem and a proven bug-factory.

**F8. `csv_import` rows: 33 rows, ALL with NULL `customer_id` and NULL
`amount` (written in the legacy column family).** The unverified CSV
importer (charter gap #4) has produced only placeholder-quality rows.
Treat it as UNTRUSTED; do not bulk-run it on Kerry's real Venmo CSVs
without the rebuild.

### 🟠 P2 — orphaned / dangling references (lens C)

141 FK relationships checked (declared + conventional, live-schema
introspected). Real dangling classes:

| Table.column → ref | dangling | note |
|---|---|---|
| `godaddy_order_splits.item_id` → items | 205 | money detail rows outliving deleted items |
| `acct_transactions.item_id` → items | 67 | ledger rows pointing at deleted items |
| `items.event_id` → events | 13 | items pointing at deleted events |
| `rsvps.matched_item_id` → items | 12 | stale matches |
| `rsvp_overrides.item_id` → items | 10 | |
| `extraction_corrections.expense_transaction_id` | 5 | |
| `acct_allocations.item_id` → items | 2 | |
| `items.parent_item_id` → items | 1 | value "1220" (TEXT column) |

Root cause: hard DELETE of items/events with no cascade/soft-delete, so
satellite money rows orphan silently. **Zero orphaned `customer_id`s
anywhere** (customers are never hard-deleted — good). Links to
reversed/merged ledger rows: 0 across tgf_payouts, expense promotions,
splits, and reconciliation matches (initially suspected, disproven once
`reconciled` was classified as live).

### 🟠 P3 — missing `customer_id` columns (lens A, schema)

| Table | rows | person columns | note |
|---|---|---|---|
| `event_pairings` | 1,065 | player_name | no customer_id column |
| `cmp_matches` | 29 | winner_name | match-play winners by name only |
| `cmp_bracket` | 8 | player_name, winner_name | bracket slots by name only |
| `name_parse_failures` | 0 | customer_name | empty; add column before first write |
| `acct_allocations` | 21 | — | per-player MONEY rows with no customer_id column (item_id only) |

(`pairing_history` is fine — `customer_a_id`/`customer_b_id` exist; just
undocumented.)

### 🟡 P4 — coverage gaps in tables that HAVE the column (all-status)

| Table | rows | NULL cid | coverage | name-only |
|---|---|---|---|---|
| expense_transactions | 920 | 390 | 57.6% | — |
| acct_transactions | 4,889 | 487 | 90.0% | 32 |
| action_items | 1,473 | 1,045 | 29.1% | 1,045 |
| handicap_rounds | 14,992 | 1,717 | 88.5% | 1,717 |
| gg_member_map | 1,842 | 634 | 65.6% | — |
| gg_history_results | 14,342 | 629 | 95.6% | 629 |
| gg_history_name_links | 1,379 | 192 | 86.1% | — |
| scoring_rounds | 3,067 | 63 | 97.9% | 63 |
| gg_history_standings | 1,943 | 60 | 96.9% | 60 |
| gg_game_results | 146 | 57 | 61.0% | 57 |
| rsvps | 1,318 | 16 | 98.8% | 16 (known-lead senders) |
| cmp_pool_members | 20 | 4 | 80.0% | 4 |
| gg_points_standings | 267 | 4 | 98.5% | 4 |
| parse_warnings | 78 | 3 | 96.2% | 3 |
| customer_memberships | 246 | 0 — but 130 rows have NULL price_paid AND NULL source_item_id (backfilled terms with no purchase link) | | |

At 100% (clean): items, godaddy_order_splits, tgf_payouts, message_log,
customers + all customer_* satellites, season_contests(+removals),
event_mvps, event_mvp_computed, handicap_player_links, refund_watches,
rsvp_email_overrides, gg_game_flights.

### 🟡 P5 — double-counting risk (lens B)

**F10. Duplicate Detective has NEVER merged anything** (0 merges, 0
dismissed) while the live detector finds **158 candidate pairs, 65 at
≥0.90 confidence**.

**F11. Cross-writer same-day/amount/customer twins (transfer legs
excluded): 40 groups.** Top: a $1,879.22 `bank-deposit-*` vs
`exp-promoted-*` twin (2026-04-13); recurring patterns `credit-payout-*`
vs `exp-promoted-*` (in-app refund op AND its Venmo receipt both posted)
and `venmo-*` (CSV) vs `exp-promoted-*` (email) — the two ingestion
paths double-posting the same payment, several as 3-row groups. This
undercounts: date-off-by-one twins exist (e.g. Jeff Young $50 —
`ext-pay-2195` on 06-30 attributed, `exp-promoted-1540` on 06-29
customer-NULL — the same real Venmo payment twice AND one leg
unattributed).

**F12. venmo-bd dedup regression: 1 active exp-promoted row again has an
active venmo-bd twin** (the v2.9x backfill guard was point-in-time; the
leak path still exists for new rows).

**F13. GoDaddy split-sum mismatches: 15 orders whose child splits don't
sum to the parent's net_deposit** (off by $1.75–$25; one order's splits
EXCEED the parent by $25).

### 🟡 P6 — reconciliation is stale and unfinished

- Bank imports STOPPED 2026-04-28/30 (every account's `last_import`).
  Everything since May is unreconciled by construction.
- `bank_deposits`: 440 unmatched (−$13,466.37 net), 41 partial, 376
  matched. Book-vs-bank at last import: TGF Checking −$17,869.90 (192
  unmatched), Chase CC −$18,227.42 (135), Venmo −$35.98.
- Backlogs: 130 pending expense rows (incl. $73.5k of pending `expense`
  + $6.4k `transfer` staging, many with `transaction_date: "unknown"`),
  4,659 uncategorized ledger rows, 1,067 open action items; 12 approved
  expenses never promoted ($125.80); one $30,000 transfer sits
  `ignored`.
- `acct_allocations` has only 21 rows — the per-player allocation model
  in `unified-financial-model.md` effectively stopped being written
  (5 of 21 lack a ledger link). Revive it or retire it: as-is it's a
  fifth parallel truth.

### ⚪ P7 — schema hygiene (docs vs live)

- 103 live tables vs ~40 documented in `schema.md`; whole subsystems
  (cmp_*, gg_history_*, scoring_*, extraction_corrections,
  refund_watches, rank_history_*, chart_of_accounts, general_ledger,
  course_tee_holes) are undocumented there.
- Vestigial: `bank_accounts` (2 rows — nothing references it;
  `bank_deposits.account_id` actually points at `acct_accounts` ids
  3/7), `general_ledger`, `bank_statement_rows`,
  `payout_templates`/`payout_template_versions`/`event_type_template_map`
  (0 rows — schema shipped, never used).
- Ambiguous id columns with no resolvable target:
  `bank_deposits.import_batch_id`, `bank_statement_rows.import_id/
  matched_id`, `general_ledger.source_id/reconciliation_id`.
- `items` money/id columns TEXT-typed (F7).

---

## What is HEALTHY (protect it)

- **Zero orphaned customer_ids across all 103 tables.**
- items / godaddy_order_splits / tgf_payouts / message_log at 100%
  customer coverage; every TGF-merchant item reaches the ledger (0
  items-not-in-ledger; item revenue $143,691.67 fully represented).
- All 780 tgf_payouts ledger-linked, 0 dead links anywhere, payout
  computed-vs-actual variance only $52.14 total.
- GoDaddy order entries (1,370 live rows, $157,788.04) fully attributed.
- Identity core (customers/aliases/emails/statuses/roles/memberships)
  structurally sound — 1 known same-name pair, flagged OK.

## Recommended fix order (input to Deliverables 2/3 — NOT executed)

1. **Identity re-resolution pipeline** (F1/F2/F3): resolver = name +
   `customer_aliases` + `other_party_handle`/venmo_username; re-run on
   every alias-add; backfill registry entries for expense_transactions
   and exp-promoted ledger rows; vendor-profile linking for vendor
   spend.
2. **Ledger-of-record schema** (F4/F5/F7): add `event_id` + backfill via
   event_aliases; fold the 61 legacy rows + acct_splits era into typed
   flat entries; type money as REAL/cents at the write paths.
3. **Duplicate sweep** (F10/F11/F12): Duplicate Detective dry-run report
   to Kerry (date-window widened to ±1 day); merge the ≥0.90 class after
   ratification; close the venmo-bd leak path.
4. **Variance reporting** (F6): computed vs recorded vs actual-paid vs
   GG three-way report, lump-aware; ratify a tolerance policy and the
   recurring −$3.00 pattern; never mutate paid amounts.
5. **Orphan repair** (P2): re-point or soft-delete the 8 dangling
   classes; adopt soft-delete discipline for items/events.
6. **Reconciliation restart** (P6): fresh bank/Venmo imports through the
   new identity pipeline (Kerry's CSVs, one clarifying question at a
   time), then work the 440 unmatched deposits and the pending queue.

**Nothing above mutates until Kerry ratifies the migration plan.**
