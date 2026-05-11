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
    _connect,
    dismiss_duplicate_pair,
    find_duplicate_candidates,
    get_duplicate_detective_mode,
    init_db,
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


if __name__ == "__main__":
    unittest.main()
