# Duplicate Detective

Admin tool for cleaning up duplicate ledger entries in `acct_transactions`.
The same financial event is sometimes recorded by multiple writers (Venmo
CSV import, Venmo email parser via `exp-promoted-N`, in-app
refund/credit-payout operations), which inflates book balance and skews
variance reconciliation. Duplicate Detective surfaces those pairs and
provides a safe, reversible merge workflow.

## Where it lives

- UI: `/admin/duplicate-detective` (main page) and
  `/admin/duplicate-detective/audit` (merge history with reverse buttons)
- Code: `email_parser/database.py` — search for the
  `# Duplicate Detective` section near the bottom; routes in `app.py`
  under the `# Duplicate Detective (admin)` block.
- Templates: `templates/duplicate_detective.html` and
  `templates/duplicate_detective_audit.html`
- Tests: `test_duplicate_detective.py` (35 tests)

## Mode flag

Persisted in `app_settings` under the key `duplicate_detective_mode`.
Three values:

| Mode                    | Behaviour |
|-------------------------|-----------|
| `dry_run_only` (default) | UI renders but every action button is disabled. Each card shows the exact UPDATE SQL inline. Export buttons (CSV + Markdown) work. |
| `review_each`            | Per-card Merge / Swap survivor / Dismiss buttons are active. |
| `auto_high_confidence`   | Adds a banner-level batch button. Triggers `POST /merge-batch`, which merges every pair with confidence ≥ 0.90 AND no FK warnings. Per-card buttons also remain active. |

Switch via the dropdown at the top of the page or directly:
`POST /admin/duplicate-detective/set-mode {mode: ...}`.

## Detection patterns

`find_duplicate_candidates()` scans `acct_transactions` for pairs where:
- both rows are `status='active'`,
- both rows are the same `entry_type` ('income' or 'expense'; transfers
  are ignored),
- amounts are within $0.01,
- dates are within 7 days,
- the pair is not already in `duplicate_dismissed_pairs`,
- AND one of the four fingerprint patterns matches.

| Pattern | Row 1 (writer A)                    | Row 2 (writer B)        | Match key                             |
|---------|-------------------------------------|-------------------------|---------------------------------------|
| **A**   | `source LIKE 'venmo%'` (Venmo CSV)  | `source_ref LIKE 'exp-promoted-%'` (email parser) | same `customer_id` or normalized name overlap |
| **B**   | `source_ref LIKE 'credit-payout-%' \| 'refund-flat-%' \| 'wd-credit-payout-%'` (in-app op) | `source_ref LIKE 'exp-promoted-%'` | same `customer_id` or normalized name overlap |
| **C**   | `source_ref LIKE 'credit-payout-%' \| 'refund-flat-%'` (in-app op) | `source LIKE 'venmo%'` (Venmo CSV) | same `customer_id` or normalized name overlap |
| **D**   | manual fallback                     | manual fallback         | same `customer_id`, different `source_ref` |

## Confidence scoring

Each candidate's `confidence` is computed as a base score with scoring
adjustments:

- Base score:
  - **0.95** — Pattern A/B/C with matching `customer_id`
  - **0.85** — Pattern A/B/C with name-only match
  - **0.65** — Pattern D
- Adjustments (applied additively):
  - **−0.10** if dates are more than 3 days apart
  - **−0.10** if amounts differ by more than $0.001
  - **−0.20** if FK warnings are present (see below)

The result is clamped to [0, 1].

## Survivor selection rule

When a pair is flagged, `_dd_select_survivor()` picks the surviving row
by priority (highest priority kept). The other is the merged row:

1. Venmo CSV (`source LIKE 'venmo%'` AND `source_ref NOT LIKE 'exp-promoted-%'`) — bank truth
2. GoDaddy order detail (`source_ref LIKE 'godaddy-order-%'`)
3. In-app operation (`source_ref LIKE 'credit-payout-%' | refund-flat-% | wd-credit-payout-%'`)
4. Email parser exp-promoted (`source_ref LIKE 'exp-promoted-%'`) — least specific
5. Anything else (lowest)

Ties (equal priority) break to the older `id` for deterministic output.
The UI's "Swap survivor" button lets the operator flip the choice for
that card.

## FK re-pointing

When a merge runs, three FK columns get moved from the merged row to
the survivor:

| Table                     | Column                  | Behaviour |
|---------------------------|-------------------------|-----------|
| `reconciliation_matches`  | `acct_transaction_id`   | Re-point survivor; if UNIQUE(bank_deposit_id, acct_transaction_id) would conflict, DELETE the merged-side row instead and record the bank_deposit_id in `duplicate_merge_audit.notes`. |
| `acct_allocations`        | `acct_transaction_id`   | Re-point survivor. |
| `expense_transactions`    | `acct_transaction_id`   | Re-point survivor. |

### HARD ERROR

If the survivor and the merged row are both matched to **different**
`bank_deposits`, the candidate gets a `fk_warnings` entry that begins
`"HARD ERROR: ..."`. The auto-merge batch refuses these candidates
silently; per-card merge refuses unless the caller passes
`allow_fk_hard_error=True`. The UI's per-card Merge button surfaces a
stronger confirmation dialog when this is set and the override gets
logged in `duplicate_merge_audit.notes`.

## Schema additions

```sql
ALTER TABLE acct_transactions
  ADD COLUMN merged_into_id INTEGER REFERENCES acct_transactions(id);

CREATE TABLE duplicate_merge_audit (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    surviving_txn_id   INTEGER NOT NULL REFERENCES acct_transactions(id),
    merged_txn_id      INTEGER NOT NULL REFERENCES acct_transactions(id),
    merge_reason       TEXT,
    confidence_score   REAL,
    merged_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    merged_by          TEXT DEFAULT 'kerry',
    notes              TEXT,
    reversible         INTEGER NOT NULL DEFAULT 1,
    reversed_at        TIMESTAMP
);

CREATE TABLE duplicate_dismissed_pairs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_a_id       INTEGER NOT NULL,
    txn_b_id       INTEGER NOT NULL,
    dismissed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dismissed_by   TEXT DEFAULT 'kerry',
    reason         TEXT,
    UNIQUE(txn_a_id, txn_b_id)
);
```

All three are added in `init_db()` and wrapped in try/except so re-runs
are idempotent.

## Reverse operation

`reverse_duplicate_merge(audit_id)`:

1. Validates the audit row exists, is not already reversed, and is
   marked reversible.
2. Inside a single transaction:
   - `UPDATE acct_transactions SET status='active', merged_into_id=NULL`
     on the merged row.
   - `UPDATE duplicate_merge_audit SET reversed_at = CURRENT_TIMESTAMP`
     and appends a note recording the reversed_by + timestamp.
3. **FK re-points are NOT automatically restored.** The merge operation
   moves allocations/recon/expense pointers from the merged row to the
   survivor, and there's no record of which specific rows previously
   pointed at the merged txn — the audit note flags
   `"manual cleanup required"` so the operator can re-point if needed.

After reverse, the original duplicate resurfaces in
`find_duplicate_candidates()` because the merged row is `status='active'`
again.

## Default-read filtering

Several aggregate read paths exclude `status='merged'` so the soft-
deleted rows don't contaminate downstream numbers:

- `get_acct_transactions()` — already filtered `('reversed', 'merged')`
- `get_acct_account_balances()` — added in Commit 8
- `get_reconciliation_dashboard()` — added in Commit 8
- `get_monthly_reconciliation()` — pre-existing filter
- `get_cashflow_data()` — pre-existing filter
- `get_event_financial_summary()` — pre-existing `'active'` filter
- `mcp_server._get_ledger_entries()` — added in Commit 8 (defaults when
  no `status` arg is supplied)
- `mcp_server.get_venmo_transactions` — pre-existing filter

To include merged rows for debugging, the MCP entry point accepts an
explicit `status='merged'` argument; the get_acct_transactions Python
API accepts `acct_status='merged'`.

## How to reverse a bad merge

1. Open `/admin/duplicate-detective/audit`.
2. Find the audit row (rows are listed newest first; reversed rows are
   dimmed).
3. Click **Reverse merge** on the row's right.
4. Confirm the dialog. The page reloads.
5. If you also need to restore FK pointers (allocations, reconciliation
   matches, expense_transactions) that the original merge moved to the
   survivor, do that manually — the reverse operation does not do it.

## Known limitations

- Pattern D is permissive: it pairs rows with the same `customer_id`
  and amount/date within tolerance but different `source_ref`s. May
  surface false positives when a customer legitimately has two
  same-amount transactions in the same week (e.g., paying for two
  separate events). Always check the survivor/merged side-by-side in
  review_each mode before clicking Merge.
- Name-only matching (Pattern A/B/C with no `customer_id`) uses
  normalised token overlap. Two different people with the same first
  name will not match (token must be ≥4 chars to count as a last-name
  match). Misspelled names may not match either — only a 2-token
  overlap or substring match wins.
- Reverse does NOT restore FK pointers. The audit row's notes column
  records this; the operator handles cleanup manually.
- The integration test against a live copy of the Railway production
  DB (originally Commit 9 in the implementation plan) is deferred to
  deployment validation — the first dry-run report against production
  is treated as the real integration test.
