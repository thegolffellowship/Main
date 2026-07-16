# TGF Tracker — Financial System & Customer-ID Integrity Audit (CHARTER)

**Owner: Kerry. Opened 2026-07-16. Lane: tracker-claude builds; platform-claude
(CA) advises architecture; Kerry ratifies.** This is a dedicated, comprehensive
audit of the **entire** Tracker's financial system and `customer_id` /
foreign-key integrity — database-architecture foundation work to a standard that
survives a CPA / bookkeeper / IRS audit, **before go-live**, so gaps don't
compound as membership grows.

## Mission
Root out **every** `customer_id` gap and **every** financial-tracking gap across
the whole Tracker. **No data floats on its own** — every row has a home via a
proper FK connection (customers, events, courses, orders, payouts, addons,
credits, refunds…). This is the foundation of everything moving forward.

## End-state (Kerry's architecture)
- **ONE FINANCIAL/LEDGER (`acct_transactions`) is the single source of truth.**
- EVENTS, TGF Payouts, Refunds, Orders/RSVPs, Addons, Credits are **windows /
  views** into that ledger — never parallel truth.
- **Every financial row ties to a `customer_id`** (CLAUDE.md rule 6), and every
  row generally has an FK home. No orphans, no name-only references, no floating
  money.
- Reconcilable line-by-line; audit-defensible; easy for any bookkeeper/CPA.

## Authority hierarchy (ratified 2026-07-16, Kerry)
**Actual Venmo receipts (IMMUTABLE — nothing paid ever changes) > GG results
(bible before a9.18/s9.18, 2026-07-14) > our computation (a9.18 forward).**
Records reconcile DOWN to actual paid; never alter a paid amount.

## Read these first
- `CLAUDE.md` — rule 6 (customer_id everywhere), Duplicate Detective, identity
  resolvers/drift.
- `docs/claude/schema.md`, `unified-financial-model.md`, `bank-reconciliation.md`,
  `expense-workflow.md`, `events.md`, `customers.md`.
- **Mailbox** (`read_platform_dialogue` since **#199**) — CA architecture
  guidance on (a) canonical ledger model, (b) identity-resolution pipeline,
  (c) CPA/IRS reconciliation/variance design, (d) migration/backfill plan.

## Known problems (starting evidence from 2026-07-16 — find the rest)
1. Venmo receipts ARE captured (email → `expense_transactions` →
   `exp-promoted-*` `acct_transactions` rows) but **`customer_id` is NULL on
   nearly every `exp-promoted` row** — money attributed to nobody. Rule-6
   violation at scale.
2. Customer resolution is **one-shot at capture**; a later-added alias (e.g.
   "Leonel Vasquez"→Lee Vasquez, created 07-02) **never retro-links** prior
   rows. Lost Lee's Jun-11 −$146 a9.12 payout + Jun-2 +$16 buy-in.
3. `tgf_payouts.amount` is our **COMPUTED** value, never reconciled to ACTUAL
   Venmo paid even when matched (matching stamps `paid_at`/`acct_transaction_id`
   only, ±$3 tolerance). **No three-way variance report exists.**
4. Two ingestion paths (email → `expense_transactions`; CSV
   `import_venmo_statement` → `acct_transactions`) with differing resolution
   quality; the CSV importer's placement confidence is **unverified**.

## Scope — audit EVERY table, three lenses
- **A. `customer_id` FK integrity:** every table referencing a person must carry
  a `customer_id` FK (rule 6). Find every NULL, every name-only reference, every
  orphan, every table missing the column.
- **B. Financial-tracking integrity:** every money-in/out row tied to its proper
  homes (customer, event, course, order, payout, refund, addon, credit). No
  floating money; reconciliation-ready; **no double-counting** across the
  multiple writers (Venmo CSV, email parser `exp-promoted-N`, in-app ops) —
  Duplicate Detective handles the dup class.
- **C. General FK integrity:** every row has a home. No orphans / dangling FKs.

## Method / discipline
- **READ-ONLY audit FIRST.** Map + quantify every gap before mutating anything.
- Live data via MCP tools (`get_acct_transactions`, `get_venmo_transactions`,
  `get_expense_transactions`, `get_customer_data_audit`,
  `get_reconciliation_dashboard`, …) and read-only bridge queries
  (`probe_golf_genius` `scoring-*`; MCP tool inventory freezes at session start,
  so add server-side reads via a bridge to run them within a session).
- `customer_id` everywhere; every row an FK home. Single ledger of record;
  events/payouts/refunds as views.
- **Kerry uploads real Venmo CSVs in-session; store + wire CAREFULLY, asking ONE
  clarifying question at a time. NO blind bulk imports. Nothing committed
  without 100% confidence.**
- Immutable paid money.
- **Rule 3b:** money/schema/member-facing changes need Kerry's explicit
  ratification BEFORE shipping — this audit's mutations all qualify.
- Deploy workflow: bump `static/js/version.js`, update docs, `git merge --no-ff`
  to main (Railway auto-deploys), verify via `get_tracker_docs` byte markers.

## Instrumentation (v2.116.1, extended v2.117.0)
The read-only audit engine lives in `email_parser/fin_audit.py`; run it live via
the `probe_golf_genius` bridge with
`extract="scoring-fin-audit:<section>"`. Core sections (=`summary`):
`tables|customer|fks|ledger|money|dupes`. IRS-lane sections (v2.117.0, run
explicitly): `taxslice=YYYY-MM` (sales-tax month slice: income base, floating
income, ±1-day cross-writer twins), `prizes=YYYY` (S2 1099-MISC exposure w/
$400/$500/$600 flags), `k3` (payout variance lumps vs GG published money),
`xferchain` (A2 transfer-chain balance + fee double-book detector).
Pure SELECT/PRAGMA against the live schema — writes nothing.

## Deliverables (phased)
1. **COMPREHENSIVE GAP AUDIT (read-only):** per table — `customer_id` coverage %,
   count of null/name-only/orphan rows, missing-FK columns, floating financial
   rows, double-count risks. One ranked report. **Do not mutate.**
2. **TARGET MODEL (with CA #199):** ledger-of-record schema; the view layer;
   FK discipline + boot-time `customer_id` backfill registry; identity-resolution
   pipeline (name + `customer_aliases` + `venmo_username`, **re-resolve on
   alias-add**); reconciliation/variance design (computed vs recorded vs
   actual-paid vs GG).
3. **MIGRATION / BACKFILL PLAN** to 100% coverage, zero double-counting,
   Kerry-ratified before execution.
4. **CAREFUL INGESTION** of real CSVs (Venmo statement first) — wire with
   customer linking, one clarifying question at a time.
5. **RECONCILIATION + VARIANCE** reporting + the fixed ongoing
   ingestion/resolution pipeline.

## Start here
Read `CLAUDE.md` + `schema.md` + `unified-financial-model.md` + this charter +
mailbox since #199. Produce **Deliverable 1** — the comprehensive `customer_id`
+ financial + FK gap audit across the ENTIRE Tracker — read-only, quantified,
ranked by risk. Report to Kerry; post a digest to the mailbox for CA. **Mutate
no data until Kerry ratifies the migration plan.**
