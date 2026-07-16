# Financial Audit — Deliverable 2: TARGET MODEL (design of record, pre-ratification)

**tracker-claude, 2026-07-16/17. Inputs: Deliverable 1
(`financial-audit-gap-report.md`), CA's architecture read (mailbox #202,
Marcus lane), the #206 reconciliation, the #207 addendum (A1–A4), and the
Kerry-directed IRS-lane scope additions (#208, S1–S3). Bar: "top CPA / IRS
examiner, above max scrutiny." Status: DESIGN — every mutation herein waits
for Kerry's Deliverable 3 ratification (rule 3b). The Audit Readiness
Standard v1.0 remains DRAFT (not mirrored to docs/governance/ until
ratified).**

## 0. The two-track rule (per #206 item 1)

Work splits by MUTATION RISK, not just sequence:

- **Track R (read-only, no ratification gate):** reports and propose-mode
  resolution. Already shipping: the fin-audit bridge (v2.116.x), the
  IRS-lane sections (v2.117.0: `taxslice`, `prizes`, `k3`, `xferchain`).
  Next in this track: lump-aware variance report as an admin page,
  Duplicate Detective dry-run with ±1-day window, resolver PROPOSE mode,
  S1 tie-out (after A1 normalization defines "ledger gross per rail").
- **Track M (mutations, Kerry-gated):** everything in §§2–8's "repair"
  columns. Order is the ratified sequence; nothing ships early.

## 1. Ledger of record — `acct_transactions` formalized (#202 §a1–a4)

1. **One active row per money movement.** UNIQUE index on live
   `source_ref` (status not in reversed/merged). CHECK-enforced.
2. **Writer registry.** Every `source_ref` prefix maps to exactly one
   owning writer function (godaddy-order-, exp-promoted-, venmo-bd-,
   credit-payout-, partial-refund-, xfer-flat-, comp-, ext-pay-, addon-,
   payout-, manual-payout-, wd-credit-, bank-deposit-, INTXFER-,
   venmo-csv- when the rebuilt importer exists). The registry is data
   (a table seeded at boot), surfaced by the invariant checker (§8);
   an unowned prefix is a boot-visible violation. This is the structural
   fix for the F11/F12 twin classes.
3. **Append-only corrections.** Reverse + repost is the ONLY correction
   path — including every backfill below. Paid/reconciled amounts are
   never UPDATEd (authority hierarchy: actual paid is immutable).
4. **Windows are views.** Events P&L, Payouts, Refunds, Credits, member
   statements = SQL views over the ledger (+ splits). The Financial tab's
   "estimated" fallback path dies for all in-scope periods at the end of
   this audit.

## 2. Counterparty model (K1, shrunk per #206)

Rule 6 refined for money rows: every ledger row carries EXACTLY ONE typed
counterparty home —

| home | column | examples |
|---|---|---|
| person | `customer_id` | registrations, prizes, refunds, balance-due |
| vendor | `customer_id` of a role=vendor profile (cids 393–402 exist) | courses, Costco, HubSpot, Anthropic |
| TGF-internal | `counterparty='tgf_internal'` | bank↔bank transfers, INTXFER, owner draw/contribution (S3) |
| unresolved | `needs_identity=1` (countable queue, never silent NULL) | anything the resolver can't place |

CHECK constraint enforces exactly-one; the `needs_identity` count is a
dashboard number like pending-review. **K1 ruling needed from Kerry:**
just the residual states (TGF-internal + explicit unresolved) — vendor
rows satisfy rule 6 as written via vendor profiles.

**S3 rails-separation lens folds in here:** a TGF-rail row that resolves
to NO home after the vendor-linking pass is flagged `PERSONAL-SUSPECT`
for Kerry review; if confirmed personal it is booked explicitly as owner
draw/contribution (typed ledger categories), never left ambiguous. The
$148k chase_alert NULL class is the hunting ground.

## 3. Identity resolution — one resolver, convergent (#202 §b)

`resolve_counterparty(name, venmo_handle, email, memo)` — called by EVERY
ingestion path (email parser, CSV importer, in-app ops):

- **T1** exact `venmo_username` / `payment_handle` / `other_party_handle`
  match → deterministic link.
- **T2** exact canonical-name or `customer_aliases` match → link.
- **T3** fuzzy → PROPOSE only, never auto-link.
- Below T2 → `needs_identity` queue.

**Re-resolution is an invariant, not an event:** on every alias/handle
add, plus nightly and at boot, sweep all `needs_identity` / NULL rows
back through the resolver (the Lee Vasquez fix). Memos are provenance:
the ratified origin-event memo grammar (#193) is parsed so payouts and
refunds land with BOTH customer_id and event_id. Backfill registry gains
`expense_transactions` and exp-promoted ledger rows.

**PROPOSE mode ships first (Track R):** the resolver runs over all 367
unattributed exp-promoted rows + 390 staging rows and emits a proposals
report (row → proposed counterparty, tier, evidence). Kerry ratifies in
batches per K2: T1 batch-approvable, T2 in groups, T3 one at a time.

## 4. Sign convention normalization — A1, PROMOTED TO P1 (#207)

Evidence: within `entry_type='expense'`, category NULL sums +$175,938
while prize_payout sums −$26,076 — same type, opposite conventions by
writer. Any SUM over expenses today is arithmetic noise.

Normative convention (to ratify): **income positive · expense/outflow
negative · contra as signed offsets to their base category · refunds and
transfers contra-revenue, not expense** — written as a normative table in
`unified-financial-model.md`, every category mapped to a
chart-of-accounts line and a DECLARED SIGN. Repair is a Track-M
reverse+repost normalization pass over every live row whose sign
disagrees with its category's declaration. **S1 (1099-K tie-out) is
sequenced immediately after this pass** — "gross per rail" is
meaningless until signs are coherent.

## 5. Money typing — F7, integer cents (question pinned per #206 item 2)

**Recommendation: INTEGER cents for canonical money columns.** Rationale:
SQLite REAL trades the TEXT trap for float drift; the gg_history_*
tables already use `money_cents` and it has been trouble-free; exact
equality is what reconciliation and invariant checks need. Migration =
new `*_cents` columns populated by strip/CAST (the audit's own parser is
the proven reference), reads flipped behind helpers, TEXT columns kept
as frozen display snapshots until a later drop. `items.parent_item_id`
re-typed INTEGER in the same pass. **Kerry decides: integer cents
(recommended) vs REAL + ROUND(,2)-at-write covenant.**

## 6. Event linkage — F4 (rule 6 extended to events)

`acct_transactions.event_id INTEGER REFERENCES events(id)` + backfill
resolving `event_name` via `events.item_name` then `event_aliases`
(same machinery as the 8 existing event-FK tables). The 1,406
unresolvable live rows land in a propose-mode report first; unmatched
names surface for Kerry mapping or explicit `no_event` typing. EVENTS
window claims wait for this.

## 7. Consolidation + orphans + dupes (F5, P2, F10–F13)

- **F5:** fold the 61 legacy-column rows and the 997-row acct_splits era
  into typed flat entries via reverse+repost; formally retire
  `general_ledger`, `bank_statement_rows`, `bank_accounts`, and the
  unused payout_templates family (drop or archive-rename, Kerry call).
- **P2 orphans:** soft-delete discipline on items/events (status column +
  read-path filters, matching the ledger's merged/reversed pattern);
  the 8 dangling classes repaired by re-point where the target is
  recoverable, else explicit tombstone rows. No hard DELETE of
  money-referenced rows anywhere afterward.
- **Dupes:** Duplicate Detective dry-run (±1-day window) → Kerry report →
  ratified merges of the ≥0.90 class. The venmo-bd leak PATH gets fixed
  (the guard becomes a standing invariant, not a point-in-time backfill).
- **A2 transfer-chain invariant:** per chain, `out = in + residual credit
  ± explicitly-typed fee legs`; the `xferchain` bridge section is the
  read-only detector, and its fee-double-book findings (venmo-bd income
  overlapping the in-leg fee delta) join the dup-merge queue.

## 8. Enforcement — invariant checker (#202 Phase 4)

Boot-time counts, surfaced on the COO dashboard (and failable in tests):
counterparty violations · needs_identity backlog · unowned source_ref
prefixes · unexplained variances · unbalanced transfer chains · dangling
FKs · sign-convention violations · twin candidates. Nonzero = visible.
The backfill registry graduates into this checker.

## 9. Reconciliation + close (#202 §c, S1/S2, K4)

- **Four-way variance report** per payout lump: COMPUTED vs RECORDED vs
  ACTUAL-PAID vs GG. ±$3 stays a MATCHING tolerance only; at CLOSE every
  non-zero variance carries an explanation code (tiebreak-split /
  rounding / netting / comp / engine-delta) or stays open. K3's ruling
  supplies the first codes.
- **Period close artifact** (monthly): deposits 100% matched · Venmo CSV
  ↔ ledger 1:1 · needs_identity = 0 or carried w/ explanation · variance
  report reviewed · **1099/W-9 review (S2 thresholds checked, W-9 gaps
  listed)** · Kerry sign-off recorded. Persisted per period
  (`period_closings` extended). Feeds the sales-tax webfile directly.
- **S1 1099-K tie-out:** per processor rail (Venmo / PayPal / GoDaddy)
  per year with monthly-running view: processor gross vs ledger gross,
  every difference coded (refund timing / misroute / fee). Sequenced
  after §4.
- **S2 prize exposure:** live now as `scoring-fin-audit:prizes=YYYY`;
  Deliverable 3 adds `customers.w9_on_file` flag + date (documents stay
  in OneDrive — PII discipline) and folds the check into period close.
- **K4 acct_allocations:** recommendation pending the derivability check
  (can `tax_reserve` be recomputed from pricing rules for ALL historical
  rows?). CA leans retire-and-derive-as-view; the check runs before
  Kerry rules. Until then the table is quarantined as non-authoritative.
- **Venmo CSV ingestion (Phase 2):** statement-of-record semantics —
  match to existing ledger rows first, create only for unmatched lines,
  every line terminates matched-existing / new-row / flagged; raw file +
  per-line hash stored (7-yr retention floor per the draft Standard).
  Kerry's CSVs wait for this path.

## 10. Ratified sequence (Track M, post-Deliverable-3)

1. Resolver + re-resolution invariant (§3) — then backfill by ratified
   proposal batches.
2. A1 sign normalization (§4) → S1 tie-out unblocked.
3. Money typing to cents (§5) + event_id (§6).
4. Consolidation + soft-delete + dup merges + venmo-bd path fix (§7).
5. Payout ledger unification remnants + four-way variance live (§9).
6. Reconciliation restart: bank imports + Kerry's Venmo CSVs through the
   new pipeline; first monthly close artifact produced.

## 11. Kerry decision register (Deliverable 3 package)

| id | decision | state |
|---|---|---|
| K1 | counterparty residual states (TGF-internal, unresolved) | ready to rule |
| K2 | batch-ratification protocol for backfill proposals (T1 batch / T2 groups / T3 singles) | ready to rule |
| K3 | −$3/−$2 lump pattern → variance explanation codes + tolerance policy | characterization running this session |
| K4 | acct_allocations revive-or-retire | blocked on tax_reserve derivability check |
| K5 | CPA engagement to bless the framework | Kerry, post-Deliverable-2 |
| — | integer-cents vs REAL+covenant (§5) | recommendation: cents |
| — | $30,000 `ignored` transfer | Kerry eyeball (flagged #206) |
| — | Audit Readiness Standard v1.0 ratification → governance mirror | Kerry |
