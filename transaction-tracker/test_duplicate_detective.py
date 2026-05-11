"""Tests for the Duplicate Detective module.

Run: python test_duplicate_detective.py

These tests use a freshly-initialized temporary SQLite database. They seed
acct_transactions rows that match each of the four detection patterns
(A/B/C/D) plus negative-case rows that must NOT be flagged, and assert
on the candidate list returned by find_duplicate_candidates().

Merge + reverse logic is covered in later commits.
"""

import os
import sqlite3
import tempfile
import unittest

from email_parser.database import (
    DuplicateMergeError,
    _connect,
    dismiss_duplicate_pair,
    find_duplicate_candidates,
    get_duplicate_detective_mode,
    get_duplicate_merge_audit,
    init_db,
    merge_duplicate_pair,
    reverse_duplicate_merge,
    set_duplicate_detective_mode,
)


def _insert_txn(conn, **fields):
    """Insert one acct_transactions row using sensible defaults. Returns the
    inserted id."""
    defaults = {
        "date": "2026-05-01",
        "description": "test row",
        "total_amount": 0.0,
        "type": "expense",
        "entry_type": "expense",
        "amount": 0.0,
        "source": "manual",
        "source_ref": None,
        "customer": None,
        "customer_id": None,
        "event_name": None,
        "status": "active",
    }
    defaults.update(fields)
    cols = ", ".join(defaults.keys())
    placeholders = ", ".join("?" for _ in defaults)
    cur = conn.execute(
        f"INSERT INTO acct_transactions ({cols}) VALUES ({placeholders})",
        tuple(defaults.values()),
    )
    return cur.lastrowid


class DuplicateDetectiveTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        # init_db twice to mirror production: the first call creates tables,
        # the second call runs forward-migration ALTERs that were authored
        # against tables that didn't exist on the first pass (see
        # acct_allocations.acct_transaction_id and other unified-model cols).
        init_db(self.db_path)
        init_db(self.db_path)

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Detection — Pattern A (Venmo CSV vs exp-promoted)
    # ------------------------------------------------------------------
    def test_pattern_A_high_confidence_same_customer_id(self):
        with _connect(self.db_path) as conn:
            id_venmo = _insert_txn(
                conn,
                date="2026-05-01",
                description="Todd McConahy",
                total_amount=93.06,
                amount=93.06,
                source="venmo",
                source_ref="venmo-12345",
                customer="Todd McConahy",
                customer_id=42,
            )
            id_promoted = _insert_txn(
                conn,
                date="2026-05-02",
                description="Todd McConahy",
                total_amount=93.06,
                amount=93.06,
                source="manual",
                source_ref="exp-promoted-825",
                customer="Todd McConahy",
                customer_id=42,
            )
            conn.commit()

        cands = find_duplicate_candidates(self.db_path)
        self.assertEqual(len(cands), 1, f"expected 1 candidate, got {cands}")
        c = cands[0]
        self.assertEqual(c["pattern"], "A")
        self.assertGreaterEqual(c["confidence"], 0.90)
        # Survivor is the Venmo CSV row (bank truth)
        self.assertEqual(c["suggested_survivor_id"], id_venmo)
        self.assertEqual(c["suggested_merged_id"], id_promoted)
        self.assertEqual(c["fk_warnings"], [])

    def test_pattern_A_name_only_match_lower_confidence(self):
        with _connect(self.db_path) as conn:
            _insert_txn(
                conn,
                description="Todd McConahy refund",
                total_amount=93.06,
                amount=93.06,
                source="venmo",
                source_ref="venmo-12345",
                customer="Todd McConahy",
            )
            _insert_txn(
                conn,
                description="Todd McConahy",
                total_amount=93.06,
                amount=93.06,
                source="manual",
                source_ref="exp-promoted-825",
                customer="Todd McConahy",
            )
            conn.commit()
        cands = find_duplicate_candidates(self.db_path)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["pattern"], "A")
        self.assertEqual(cands[0]["match_kind"], "name")
        # 0.85 base (name only)
        self.assertAlmostEqual(cands[0]["confidence"], 0.85, places=4)

    # ------------------------------------------------------------------
    # Detection — Pattern B (in-app refund/credit vs exp-promoted)
    # ------------------------------------------------------------------
    def test_pattern_B_credit_payout_vs_exp_promoted(self):
        with _connect(self.db_path) as conn:
            id_credit = _insert_txn(
                conn,
                description="Credit payout (Venmo)",
                total_amount=93.06,
                amount=93.06,
                source="manual",
                source_ref="credit-payout-1222",
                customer="Todd McConahy",
                customer_id=42,
            )
            id_promoted = _insert_txn(
                conn,
                description="Todd McConahy",
                total_amount=93.06,
                amount=93.06,
                source="manual",
                source_ref="exp-promoted-825",
                customer="Todd McConahy",
                customer_id=42,
            )
            conn.commit()
        cands = find_duplicate_candidates(self.db_path)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["pattern"], "B")
        self.assertAlmostEqual(cands[0]["confidence"], 0.95, places=4)
        # Survivor: in-app operation beats exp-promoted
        self.assertEqual(cands[0]["suggested_survivor_id"], id_credit)
        self.assertEqual(cands[0]["suggested_merged_id"], id_promoted)

    def test_pattern_B_wd_credit_payout_variant(self):
        with _connect(self.db_path) as conn:
            _insert_txn(
                conn,
                description="WD credit payout",
                total_amount=14.0,
                amount=14.0,
                source="manual",
                source_ref="wd-credit-payout-99",
                customer_id=99,
            )
            _insert_txn(
                conn,
                description="Brian Parch",
                total_amount=14.0,
                amount=14.0,
                source="manual",
                source_ref="exp-promoted-300",
                customer_id=99,
            )
            conn.commit()
        cands = find_duplicate_candidates(self.db_path)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["pattern"], "B")

    # ------------------------------------------------------------------
    # Detection — Pattern C (in-app vs Venmo CSV)
    # ------------------------------------------------------------------
    def test_pattern_C_inapp_vs_venmo_csv(self):
        with _connect(self.db_path) as conn:
            id_venmo = _insert_txn(
                conn,
                description="Paul Reed",
                total_amount=46.0,
                amount=46.0,
                source="venmo",
                source_ref="venmo-99999",
                customer="Paul Reed",
                customer_id=7,
            )
            id_inapp = _insert_txn(
                conn,
                description="Refund flat",
                total_amount=46.0,
                amount=46.0,
                source="manual",
                source_ref="refund-flat-555",
                customer="Paul Reed",
                customer_id=7,
            )
            conn.commit()
        cands = find_duplicate_candidates(self.db_path)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["pattern"], "C")
        # Venmo CSV wins over in-app
        self.assertEqual(cands[0]["suggested_survivor_id"], id_venmo)
        self.assertEqual(cands[0]["suggested_merged_id"], id_inapp)

    # ------------------------------------------------------------------
    # Detection — Pattern D (manual fallback, medium confidence)
    # ------------------------------------------------------------------
    def test_pattern_D_same_customer_different_source_ref(self):
        with _connect(self.db_path) as conn:
            _insert_txn(
                conn,
                description="Misc 1",
                total_amount=100.0,
                amount=100.0,
                source="manual",
                source_ref="manual-A",
                customer_id=33,
            )
            _insert_txn(
                conn,
                description="Misc 2",
                total_amount=100.0,
                amount=100.0,
                source="manual",
                source_ref="manual-B",
                customer_id=33,
            )
            conn.commit()
        cands = find_duplicate_candidates(self.db_path)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["pattern"], "D")
        self.assertAlmostEqual(cands[0]["confidence"], 0.65, places=4)

    # ------------------------------------------------------------------
    # Negative cases — must NOT be flagged
    # ------------------------------------------------------------------
    def test_no_match_when_entry_types_differ(self):
        with _connect(self.db_path) as conn:
            _insert_txn(
                conn, amount=50.0, total_amount=50.0, type="income",
                entry_type="income", source="venmo", source_ref="venmo-1",
                customer_id=5,
            )
            _insert_txn(
                conn, amount=50.0, total_amount=50.0, type="expense",
                entry_type="expense", source="manual",
                source_ref="exp-promoted-1", customer_id=5,
            )
            conn.commit()
        cands = find_duplicate_candidates(self.db_path)
        self.assertEqual(cands, [])

    def test_no_match_when_dates_more_than_7_days_apart(self):
        with _connect(self.db_path) as conn:
            _insert_txn(
                conn, date="2026-05-01", amount=50.0, total_amount=50.0,
                source="venmo", source_ref="venmo-1", customer_id=5,
            )
            _insert_txn(
                conn, date="2026-05-15", amount=50.0, total_amount=50.0,
                source="manual", source_ref="exp-promoted-1", customer_id=5,
            )
            conn.commit()
        self.assertEqual(find_duplicate_candidates(self.db_path), [])

    def test_no_match_when_amount_off_by_more_than_one_cent(self):
        with _connect(self.db_path) as conn:
            _insert_txn(
                conn, amount=50.00, total_amount=50.00, source="venmo",
                source_ref="venmo-1", customer_id=5,
            )
            _insert_txn(
                conn, amount=50.05, total_amount=50.05, source="manual",
                source_ref="exp-promoted-1", customer_id=5,
            )
            conn.commit()
        self.assertEqual(find_duplicate_candidates(self.db_path), [])

    def test_merged_status_rows_are_skipped(self):
        with _connect(self.db_path) as conn:
            _insert_txn(
                conn, amount=50.0, total_amount=50.0, source="venmo",
                source_ref="venmo-1", customer_id=5, status="merged",
            )
            _insert_txn(
                conn, amount=50.0, total_amount=50.0, source="manual",
                source_ref="exp-promoted-1", customer_id=5,
            )
            conn.commit()
        self.assertEqual(find_duplicate_candidates(self.db_path), [])

    def test_transfers_are_ignored(self):
        with _connect(self.db_path) as conn:
            _insert_txn(
                conn, type="transfer", entry_type="transfer", amount=50.0,
                total_amount=50.0, source="venmo", source_ref="venmo-1",
                customer_id=5,
            )
            _insert_txn(
                conn, type="transfer", entry_type="transfer", amount=50.0,
                total_amount=50.0, source="manual",
                source_ref="exp-promoted-1", customer_id=5,
            )
            conn.commit()
        self.assertEqual(find_duplicate_candidates(self.db_path), [])

    # ------------------------------------------------------------------
    # Date / amount scoring adjustments
    # ------------------------------------------------------------------
    def test_date_more_than_3_days_apart_reduces_confidence(self):
        with _connect(self.db_path) as conn:
            _insert_txn(
                conn, date="2026-05-01", amount=50.0, total_amount=50.0,
                source="venmo", source_ref="venmo-1", customer_id=5,
            )
            _insert_txn(
                conn, date="2026-05-06", amount=50.0, total_amount=50.0,
                source="manual", source_ref="exp-promoted-1", customer_id=5,
            )
            conn.commit()
        cands = find_duplicate_candidates(self.db_path)
        self.assertEqual(len(cands), 1)
        # 0.95 base - 0.10 (date > 3 days) = 0.85
        self.assertAlmostEqual(cands[0]["confidence"], 0.85, places=4)

    # ------------------------------------------------------------------
    # Idempotency — running twice = identical output
    # ------------------------------------------------------------------
    def test_finder_is_idempotent(self):
        with _connect(self.db_path) as conn:
            _insert_txn(
                conn, amount=50.0, total_amount=50.0, source="venmo",
                source_ref="venmo-1", customer_id=5,
            )
            _insert_txn(
                conn, amount=50.0, total_amount=50.0, source="manual",
                source_ref="exp-promoted-1", customer_id=5,
            )
            conn.commit()
        first = find_duplicate_candidates(self.db_path)
        second = find_duplicate_candidates(self.db_path)
        self.assertEqual(
            [c["candidate_id"] for c in first],
            [c["candidate_id"] for c in second],
        )
        self.assertEqual(
            [c["confidence"] for c in first],
            [c["confidence"] for c in second],
        )

    # ------------------------------------------------------------------
    # FK warning detection — hard error when both rows reconciled to
    # different bank deposits
    # ------------------------------------------------------------------
    def test_fk_warning_when_both_matched_to_different_deposits(self):
        with _connect(self.db_path) as conn:
            id_a = _insert_txn(
                conn, amount=50.0, total_amount=50.0, source="venmo",
                source_ref="venmo-1", customer_id=5,
            )
            id_b = _insert_txn(
                conn, amount=50.0, total_amount=50.0, source="manual",
                source_ref="exp-promoted-1", customer_id=5,
            )
            # Need bank_deposits rows to satisfy the FK
            conn.execute(
                "INSERT INTO bank_accounts (name, account_type) "
                "VALUES ('test-bank', 'checking')"
            )
            ba = conn.execute("SELECT id FROM bank_accounts ORDER BY id DESC LIMIT 1").fetchone()[0]
            conn.execute(
                "INSERT INTO bank_deposits (account_id, deposit_date, amount, "
                "description, status) VALUES (?, '2026-05-01', 50.0, 'd1', 'unmatched')",
                (ba,),
            )
            dep1 = conn.execute("SELECT id FROM bank_deposits ORDER BY id DESC LIMIT 1").fetchone()[0]
            conn.execute(
                "INSERT INTO bank_deposits (account_id, deposit_date, amount, "
                "description, status) VALUES (?, '2026-05-01', 50.0, 'd2', 'unmatched')",
                (ba,),
            )
            dep2 = conn.execute("SELECT id FROM bank_deposits ORDER BY id DESC LIMIT 1").fetchone()[0]
            conn.execute(
                "INSERT INTO reconciliation_matches (bank_deposit_id, "
                "acct_transaction_id, match_type) VALUES (?, ?, 'manual')",
                (dep1, id_a),
            )
            conn.execute(
                "INSERT INTO reconciliation_matches (bank_deposit_id, "
                "acct_transaction_id, match_type) VALUES (?, ?, 'manual')",
                (dep2, id_b),
            )
            conn.commit()
        cands = find_duplicate_candidates(self.db_path)
        self.assertEqual(len(cands), 1)
        self.assertTrue(cands[0]["fk_warnings"])
        self.assertIn("HARD ERROR", cands[0]["fk_warnings"][0])
        # Penalty applied (-0.20)
        self.assertLess(cands[0]["confidence"], 0.80)

    # ------------------------------------------------------------------
    # Dismissed pairs are filtered out
    # ------------------------------------------------------------------
    def test_dismissed_pair_is_skipped(self):
        with _connect(self.db_path) as conn:
            id_a = _insert_txn(
                conn, amount=50.0, total_amount=50.0, source="venmo",
                source_ref="venmo-1", customer_id=5,
            )
            id_b = _insert_txn(
                conn, amount=50.0, total_amount=50.0, source="manual",
                source_ref="exp-promoted-1", customer_id=5,
            )
            conn.commit()
        self.assertEqual(len(find_duplicate_candidates(self.db_path)), 1)
        self.assertTrue(dismiss_duplicate_pair(id_a, id_b, "not a dup", self.db_path))
        # Second dismissal of the same pair is a no-op
        self.assertFalse(dismiss_duplicate_pair(id_a, id_b, "again", self.db_path))
        self.assertEqual(find_duplicate_candidates(self.db_path), [])
        # include_dismissed=True surfaces it again
        self.assertEqual(
            len(find_duplicate_candidates(self.db_path, include_dismissed=True)), 1
        )

    # ------------------------------------------------------------------
    # Mode flag persistence
    # ------------------------------------------------------------------
    def test_mode_flag_default_and_round_trip(self):
        self.assertEqual(get_duplicate_detective_mode(self.db_path), "dry_run_only")
        set_duplicate_detective_mode("auto_high_confidence", self.db_path)
        self.assertEqual(
            get_duplicate_detective_mode(self.db_path), "auto_high_confidence"
        )
        set_duplicate_detective_mode("review_each", self.db_path)
        self.assertEqual(get_duplicate_detective_mode(self.db_path), "review_each")
        with self.assertRaises(ValueError):
            set_duplicate_detective_mode("bogus", self.db_path)

    # ------------------------------------------------------------------
    # Survivor selection: GoDaddy beats exp-promoted, in-app beats
    # exp-promoted, Venmo beats everything
    # ------------------------------------------------------------------
    def test_survivor_godaddy_beats_promoted(self):
        with _connect(self.db_path) as conn:
            id_gd = _insert_txn(
                conn, amount=100.0, total_amount=100.0, source="manual",
                source_ref="godaddy-order-R12345", customer_id=22,
            )
            id_prom = _insert_txn(
                conn, amount=100.0, total_amount=100.0, source="manual",
                source_ref="exp-promoted-999", customer_id=22,
            )
            conn.commit()
        cands = find_duplicate_candidates(self.db_path)
        # Pattern D match (same customer, both different source_refs)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["suggested_survivor_id"], id_gd)
        self.assertEqual(cands[0]["suggested_merged_id"], id_prom)


class DuplicateMergeTestCase(unittest.TestCase):
    """Coverage for merge_duplicate_pair() — FK re-pointing, soft delete,
    rollback, idempotency, HARD ERROR gating."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        # init_db twice to mirror production: the first call creates tables,
        # the second call runs forward-migration ALTERs that were authored
        # against tables that didn't exist on the first pass (see
        # acct_allocations.acct_transaction_id and other unified-model cols).
        init_db(self.db_path)
        init_db(self.db_path)

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _seed_pair(self, conn, **overrides):
        """Helper: seed a basic Pattern A pair, return (survivor_id, merged_id)."""
        a = _insert_txn(
            conn, date="2026-05-01", amount=93.06, total_amount=93.06,
            source="venmo", source_ref="venmo-1",
            customer="Todd McConahy", customer_id=42, **overrides,
        )
        b = _insert_txn(
            conn, date="2026-05-02", amount=93.06, total_amount=93.06,
            source="manual", source_ref="exp-promoted-825",
            customer="Todd McConahy", customer_id=42, **overrides,
        )
        return a, b  # a is venmo (survivor), b is exp-promoted (merged)

    def test_merge_marks_status_and_sets_merged_into_id(self):
        with _connect(self.db_path) as conn:
            survivor, merged = self._seed_pair(conn)
            conn.commit()

        result = merge_duplicate_pair(
            survivor, merged, confidence=0.95, reason="test", db_path=self.db_path
        )
        self.assertFalse(result["noop"])
        self.assertGreater(result["audit_id"], 0)

        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT status, merged_into_id FROM acct_transactions WHERE id = ?",
                (merged,),
            ).fetchone()
            self.assertEqual(row["status"], "merged")
            self.assertEqual(row["merged_into_id"], survivor)

            row = conn.execute(
                "SELECT status, merged_into_id FROM acct_transactions WHERE id = ?",
                (survivor,),
            ).fetchone()
            # Survivor untouched
            self.assertEqual(row["status"], "active")
            self.assertIsNone(row["merged_into_id"])

            audit = conn.execute(
                "SELECT * FROM duplicate_merge_audit WHERE id = ?",
                (result["audit_id"],),
            ).fetchone()
            self.assertEqual(audit["surviving_txn_id"], survivor)
            self.assertEqual(audit["merged_txn_id"], merged)
            self.assertAlmostEqual(audit["confidence_score"], 0.95, places=4)
            self.assertEqual(audit["merge_reason"], "test")
            self.assertIsNone(audit["reversed_at"])

    def test_merge_repoints_acct_allocations(self):
        with _connect(self.db_path) as conn:
            survivor, merged = self._seed_pair(conn)
            conn.execute(
                "INSERT INTO acct_allocations (order_id, item_id, "
                "allocation_date, total_collected, acct_transaction_id) "
                "VALUES (?, ?, ?, ?, ?)",
                ("R999", None, "2026-05-01", 93.06, merged),
            )
            conn.commit()
        result = merge_duplicate_pair(survivor, merged, db_path=self.db_path)
        self.assertEqual(result["fk_repointed"]["allocations"], 1)
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT acct_transaction_id FROM acct_allocations "
                "WHERE order_id = 'R999'"
            ).fetchone()
            self.assertEqual(row["acct_transaction_id"], survivor)

    def test_merge_repoints_expense_transactions(self):
        with _connect(self.db_path) as conn:
            survivor, merged = self._seed_pair(conn)
            conn.execute(
                "INSERT INTO expense_transactions (email_uid, source_type, "
                "amount, transaction_date, acct_transaction_id) "
                "VALUES (?, ?, ?, ?, ?)",
                ("uid-1", "venmo_alert", 93.06, "2026-05-01", merged),
            )
            conn.commit()
        result = merge_duplicate_pair(survivor, merged, db_path=self.db_path)
        self.assertEqual(result["fk_repointed"]["expense_txns"], 1)
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT acct_transaction_id FROM expense_transactions "
                "WHERE email_uid = 'uid-1'"
            ).fetchone()
            self.assertEqual(row["acct_transaction_id"], survivor)

    def test_merge_repoints_reconciliation_match(self):
        with _connect(self.db_path) as conn:
            survivor, merged = self._seed_pair(conn)
            conn.execute(
                "INSERT INTO bank_accounts (name, account_type) "
                "VALUES ('test-bank', 'checking')"
            )
            ba = conn.execute(
                "SELECT id FROM bank_accounts ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO bank_deposits (account_id, deposit_date, amount, "
                "description, status) VALUES (?, '2026-05-01', 93.06, 'd1', 'unmatched')",
                (ba,),
            )
            dep = conn.execute("SELECT id FROM bank_deposits ORDER BY id DESC LIMIT 1").fetchone()[0]
            # Only the merged row is matched — survivor isn't
            conn.execute(
                "INSERT INTO reconciliation_matches (bank_deposit_id, "
                "acct_transaction_id, match_type) VALUES (?, ?, 'manual')",
                (dep, merged),
            )
            conn.commit()
        result = merge_duplicate_pair(survivor, merged, db_path=self.db_path)
        self.assertEqual(result["fk_repointed"]["recon"], 1)
        self.assertEqual(result["recon_match_deleted"], [])
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT acct_transaction_id FROM reconciliation_matches "
                "WHERE bank_deposit_id = ?", (dep,),
            ).fetchone()
            self.assertEqual(row["acct_transaction_id"], survivor)

    def test_merge_deletes_duplicate_match_when_survivor_already_matched(self):
        """When BOTH rows are matched to the SAME bank_deposit, the
        UNIQUE(bank_deposit_id, acct_transaction_id) constraint would block
        a naive re-point. We DELETE the merged-side row and log it."""
        with _connect(self.db_path) as conn:
            survivor, merged = self._seed_pair(conn)
            conn.execute(
                "INSERT INTO bank_accounts (name, account_type) "
                "VALUES ('test-bank', 'checking')"
            )
            ba = conn.execute(
                "SELECT id FROM bank_accounts ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO bank_deposits (account_id, deposit_date, amount, "
                "description, status) VALUES (?, '2026-05-01', 93.06, 'd1', 'unmatched')",
                (ba,),
            )
            dep = conn.execute("SELECT id FROM bank_deposits ORDER BY id DESC LIMIT 1").fetchone()[0]
            conn.execute(
                "INSERT INTO reconciliation_matches (bank_deposit_id, "
                "acct_transaction_id, match_type) VALUES (?, ?, 'manual')",
                (dep, survivor),
            )
            conn.execute(
                "INSERT INTO reconciliation_matches (bank_deposit_id, "
                "acct_transaction_id, match_type) VALUES (?, ?, 'manual')",
                (dep, merged),
            )
            conn.commit()
        result = merge_duplicate_pair(survivor, merged, db_path=self.db_path)
        self.assertEqual(result["recon_match_deleted"], [dep])
        with _connect(self.db_path) as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM reconciliation_matches "
                "WHERE bank_deposit_id = ?", (dep,),
            ).fetchone()[0]
            self.assertEqual(n, 1)
            audit = conn.execute(
                "SELECT notes FROM duplicate_merge_audit WHERE id = ?",
                (result["audit_id"],),
            ).fetchone()
            self.assertIn("deleted duplicate reconciliation_match", audit["notes"])

    def test_merge_blocks_on_hard_error_unless_override(self):
        """Both rows reconciled to DIFFERENT deposits — must refuse without
        an explicit override flag."""
        with _connect(self.db_path) as conn:
            survivor, merged = self._seed_pair(conn)
            conn.execute(
                "INSERT INTO bank_accounts (name, account_type) "
                "VALUES ('test-bank', 'checking')"
            )
            ba = conn.execute(
                "SELECT id FROM bank_accounts ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO bank_deposits (account_id, deposit_date, amount, "
                "description, status) VALUES (?, '2026-05-01', 93.06, 'd1', 'unmatched')",
                (ba,),
            )
            d1 = conn.execute("SELECT id FROM bank_deposits ORDER BY id DESC LIMIT 1").fetchone()[0]
            conn.execute(
                "INSERT INTO bank_deposits (account_id, deposit_date, amount, "
                "description, status) VALUES (?, '2026-05-01', 93.06, 'd2', 'unmatched')",
                (ba,),
            )
            d2 = conn.execute("SELECT id FROM bank_deposits ORDER BY id DESC LIMIT 1").fetchone()[0]
            conn.execute(
                "INSERT INTO reconciliation_matches (bank_deposit_id, "
                "acct_transaction_id, match_type) VALUES (?, ?, 'manual')",
                (d1, survivor),
            )
            conn.execute(
                "INSERT INTO reconciliation_matches (bank_deposit_id, "
                "acct_transaction_id, match_type) VALUES (?, ?, 'manual')",
                (d2, merged),
            )
            conn.commit()
        with self.assertRaises(DuplicateMergeError) as ctx:
            merge_duplicate_pair(survivor, merged, db_path=self.db_path)
        self.assertIn("FK warning", str(ctx.exception))

        # Verify NOTHING was written
        with _connect(self.db_path) as conn:
            n = conn.execute("SELECT COUNT(*) FROM duplicate_merge_audit").fetchone()[0]
            self.assertEqual(n, 0)
            row = conn.execute(
                "SELECT status FROM acct_transactions WHERE id = ?", (merged,)
            ).fetchone()
            self.assertEqual(row["status"], "active")

        # Override succeeds and logs the override in notes
        result = merge_duplicate_pair(
            survivor, merged, allow_fk_hard_error=True, db_path=self.db_path
        )
        with _connect(self.db_path) as conn:
            audit = conn.execute(
                "SELECT notes FROM duplicate_merge_audit WHERE id = ?",
                (result["audit_id"],),
            ).fetchone()
            self.assertIn("HARD ERROR override", audit["notes"])

    def test_merge_is_idempotent(self):
        """Calling merge twice with the same pair returns a noop on the
        second call. No new audit row, no double-write."""
        with _connect(self.db_path) as conn:
            survivor, merged = self._seed_pair(conn)
            conn.commit()
        r1 = merge_duplicate_pair(survivor, merged, db_path=self.db_path)
        r2 = merge_duplicate_pair(survivor, merged, db_path=self.db_path)
        self.assertFalse(r1["noop"])
        self.assertTrue(r2["noop"])
        self.assertEqual(r2["audit_id"], r1["audit_id"])
        with _connect(self.db_path) as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM duplicate_merge_audit WHERE merged_txn_id = ?",
                (merged,),
            ).fetchone()[0]
            self.assertEqual(n, 1)

    def test_merge_refuses_to_merge_already_merged_into_different_survivor(self):
        with _connect(self.db_path) as conn:
            s1, m1 = self._seed_pair(conn)
            s2 = _insert_txn(
                conn, amount=93.06, total_amount=93.06, source="venmo",
                source_ref="venmo-2", customer_id=42,
            )
            conn.commit()
        merge_duplicate_pair(s1, m1, db_path=self.db_path)
        # m1 is now status=merged into s1. Trying to merge m1 into s2 must fail.
        with self.assertRaises(DuplicateMergeError):
            merge_duplicate_pair(s2, m1, db_path=self.db_path)

    def test_merge_refuses_when_same_id_passed(self):
        with _connect(self.db_path) as conn:
            survivor, _ = self._seed_pair(conn)
            conn.commit()
        with self.assertRaises(DuplicateMergeError):
            merge_duplicate_pair(survivor, survivor, db_path=self.db_path)

    def test_merge_refuses_when_either_id_missing(self):
        with _connect(self.db_path) as conn:
            survivor, _ = self._seed_pair(conn)
            conn.commit()
        with self.assertRaises(DuplicateMergeError):
            merge_duplicate_pair(survivor, 9999999, db_path=self.db_path)
        with self.assertRaises(DuplicateMergeError):
            merge_duplicate_pair(9999999, survivor, db_path=self.db_path)


class DuplicateReverseTestCase(unittest.TestCase):
    """Coverage for reverse_duplicate_merge() and get_duplicate_merge_audit()."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        init_db(self.db_path)
        init_db(self.db_path)

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _merged_pair(self):
        with _connect(self.db_path) as conn:
            survivor = _insert_txn(
                conn, amount=93.06, total_amount=93.06, source="venmo",
                source_ref="venmo-1", customer_id=42,
            )
            merged = _insert_txn(
                conn, amount=93.06, total_amount=93.06, source="manual",
                source_ref="exp-promoted-825", customer_id=42,
            )
            conn.commit()
        r = merge_duplicate_pair(survivor, merged, confidence=0.95,
                                 reason="test merge", db_path=self.db_path)
        return survivor, merged, r["audit_id"]

    def test_reverse_restores_status_and_stamps_audit(self):
        survivor, merged, audit_id = self._merged_pair()
        r = reverse_duplicate_merge(audit_id, db_path=self.db_path)
        self.assertEqual(r["audit_id"], audit_id)
        self.assertEqual(r["merged_txn_id"], merged)
        self.assertEqual(r["surviving_txn_id"], survivor)
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT status, merged_into_id FROM acct_transactions WHERE id = ?",
                (merged,),
            ).fetchone()
            self.assertEqual(row["status"], "active")
            self.assertIsNone(row["merged_into_id"])
            audit = conn.execute(
                "SELECT reversed_at, notes FROM duplicate_merge_audit WHERE id = ?",
                (audit_id,),
            ).fetchone()
            self.assertIsNotNone(audit["reversed_at"])
            self.assertIn("FK re-points", audit["notes"])

    def test_reverse_rejects_already_reversed(self):
        _, _, audit_id = self._merged_pair()
        reverse_duplicate_merge(audit_id, db_path=self.db_path)
        with self.assertRaises(DuplicateMergeError) as ctx:
            reverse_duplicate_merge(audit_id, db_path=self.db_path)
        self.assertIn("already reversed", str(ctx.exception))

    def test_reverse_rejects_unknown_audit_id(self):
        with self.assertRaises(DuplicateMergeError):
            reverse_duplicate_merge(9999, db_path=self.db_path)

    def test_reverse_rejects_non_reversible_row(self):
        survivor, merged, audit_id = self._merged_pair()
        with _connect(self.db_path) as conn:
            conn.execute(
                "UPDATE duplicate_merge_audit SET reversible = 0 WHERE id = ?",
                (audit_id,),
            )
            conn.commit()
        with self.assertRaises(DuplicateMergeError) as ctx:
            reverse_duplicate_merge(audit_id, db_path=self.db_path)
        self.assertIn("non-reversible", str(ctx.exception))

    def test_reverse_lets_pair_resurface_in_finder(self):
        """After reverse, the original duplicate should reappear in
        find_duplicate_candidates() since the merged row is active again."""
        survivor, merged, audit_id = self._merged_pair()
        self.assertEqual(find_duplicate_candidates(self.db_path), [])
        reverse_duplicate_merge(audit_id, db_path=self.db_path)
        cands = find_duplicate_candidates(self.db_path)
        self.assertEqual(len(cands), 1)
        self.assertEqual(
            {cands[0]["suggested_survivor_id"], cands[0]["suggested_merged_id"]},
            {survivor, merged},
        )

    def test_get_audit_returns_joined_rows(self):
        survivor, merged, audit_id = self._merged_pair()
        rows = get_duplicate_merge_audit(db_path=self.db_path)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["id"], audit_id)
        self.assertEqual(r["surviving_txn_id"], survivor)
        self.assertEqual(r["merged_txn_id"], merged)
        self.assertEqual(r["surviving_source_ref"], "venmo-1")
        self.assertEqual(r["merged_source_ref"], "exp-promoted-825")
        self.assertEqual(r["merged_status"], "merged")
        self.assertIsNone(r["reversed_at"])

    def test_audit_rows_ordered_newest_first(self):
        with _connect(self.db_path) as conn:
            ids = []
            for i in range(3):
                a = _insert_txn(
                    conn, amount=10 + i, total_amount=10 + i,
                    source="venmo", source_ref=f"venmo-{i}", customer_id=100 + i,
                )
                b = _insert_txn(
                    conn, amount=10 + i, total_amount=10 + i,
                    source="manual", source_ref=f"exp-promoted-{i}",
                    customer_id=100 + i,
                )
                conn.commit()
                ids.append((a, b))
        audit_ids = []
        for s, m in ids:
            r = merge_duplicate_pair(s, m, db_path=self.db_path)
            audit_ids.append(r["audit_id"])
        rows = get_duplicate_merge_audit(db_path=self.db_path)
        # Newest first
        self.assertEqual([r["id"] for r in rows[:3]], list(reversed(audit_ids)))


if __name__ == "__main__":
    unittest.main()
