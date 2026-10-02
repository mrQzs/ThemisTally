"""Durable T3A ledger adapter checks (independent of SchedulerStore)."""
from __future__ import annotations

import sqlite3
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.budget import BudgetError, BudgetPolicy, UsageObservation
from codekit.budget_store_v2 import BudgetStore, BudgetStoreError


class BudgetStoreV2Tests(unittest.TestCase):
    def setUp(self):
        self.store = BudgetStore(":memory:")
        self.store.seed_policy("req-a", BudgetPolicy({"tokens": 10, "charge:USD": 20}, {"task-a": {"tokens": 8, "charge:USD": 20}}))

    def tearDown(self):
        self.store.close()

    def reserve(self, operation="op-a", task="task-a", tokens=5, usd=0, generation=1):
        return self.store.reserve(operation, "req-a", task, {"tokens": tokens, "charge:USD": usd}, generation)

    def obs(self, **changes):
        values = dict(observation_id="obs-a", operation_id="op-a", dimension="tokens", kind="cumulative",
                      amount=2, revision=1, economic_call_key="call-a", evidence_ref="evidence-a")
        values.update(changes)
        if "kind" in changes:
            values["final"] = changes["kind"] == "final"
        return UsageObservation(**values)

    def test_schema_pragmas_and_scope(self):
        self.assertEqual(self.store.db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(self.store.db.execute("PRAGMA journal_mode").fetchone()[0], "memory")
        self.assertEqual(self.store.db.execute("PRAGMA synchronous").fetchone()[0], 2)
        self.assertEqual(self.store.db.execute("SELECT schema_version FROM budget_meta").fetchone()[0], 2)
        with self.assertRaises(BudgetStoreError):
            self.store.snapshot("unknown")

    def test_seed_is_immutable_and_replayable(self):
        self.assertTrue(self.store.seed_policy("req-a", BudgetPolicy({"tokens": 10, "charge:USD": 20}, {"task-a": {"tokens": 8, "charge:USD": 20}})).replayed)
        with self.assertRaises(BudgetStoreError) as ctx:
            self.store.seed_policy("req-a", BudgetPolicy({"tokens": 11, "charge:USD": 20}))
        self.assertEqual(ctx.exception.code, "E_POLICY_CONFLICT")

    def test_reserve_snapshot_and_outbox_are_atomic(self):
        result = self.reserve()
        self.assertEqual(result.status, "RESERVED")
        snap = self.store.snapshot("req-a")
        self.assertEqual((snap.dimensions["tokens"].known, snap.dimensions["tokens"].held, snap.dimensions["tokens"].exposure), (0, 5, 5))
        self.assertEqual(len(self.store.outbox()), 2)
        replay = self.reserve()
        self.assertTrue(replay.replayed)
        self.assertEqual(len(self.store.outbox()), 2)
        with self.assertRaises(BudgetStoreError):
            self.reserve(tokens=4)

    def test_observation_replay_mirror_history_and_current_projection(self):
        self.reserve()
        first = self.store.observe(self.obs())
        self.assertEqual(first.status, "APPLIED")
        self.assertEqual(self.store.snapshot("req-a").dimensions["tokens"].exposure, 5)
        replay = self.store.observe(self.obs())
        self.assertTrue(replay.replayed)
        mirror = self.store.observe(self.obs(observation_id="obs-mirror", evidence_ref="other-evidence"))
        self.assertEqual(mirror.status, "MIRROR")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 2)

    def test_final_releases_hold_and_late_usage_after_stop_is_accepted(self):
        self.reserve(task="task-b", tokens=10)
        self.store.observe(self.obs(amount=3))
        self.store.stop("req-a", "OPERATOR_STOP")
        result = self.store.observe(self.obs(observation_id="obs-final", kind="final", amount=6, revision=2))
        self.assertEqual(result.status, "APPLIED")
        dim = self.store.snapshot("req-a").dimensions["tokens"]
        self.assertEqual((dim.known, dim.held, dim.exposure), (6, 0, 6))
        self.assertIn("OPERATOR_STOP", self.store.snapshot("req-a").stop_reasons)
        with self.assertRaises(BudgetStoreError):
            self.reserve(operation="op-b", tokens=1)

    def test_unknown_retains_hold_and_stops_without_zeroing(self):
        self.reserve()
        self.store.observe(self.obs())
        result = self.store.observe(self.obs(observation_id="obs-unknown", kind="unknown", amount=None,
                                             revision=2, unknown_reason="provider-unavailable"))
        self.assertEqual(result.status, "APPLIED")
        dim = self.store.snapshot("req-a").dimensions["tokens"]
        self.assertEqual((dim.known, dim.held), (2, 3))
        self.assertEqual(dim.unknown_operations, ("op-a",))
        self.assertIn("USAGE_UNKNOWN", self.store.snapshot("req-a").stop_reasons)

    def test_overrun_and_correction(self):
        self.reserve()
        self.store.observe(self.obs(amount=12))
        dim = self.store.snapshot("req-a").dimensions["tokens"]
        self.assertEqual((dim.known, dim.raw_remaining), (12, -2))
        self.assertIn("BUDGET_EXCEEDED", self.store.snapshot("req-a").stop_reasons)
        with self.assertRaises(BudgetStoreError):
            self.store.observe(self.obs(observation_id="bad", revision=2, amount=3))
        self.store.observe(self.obs(observation_id="corrected", revision=2, amount=3, correction=True, supersedes="obs-a"))
        self.assertEqual(self.store.snapshot("req-a").dimensions["tokens"].known, 3)

    def test_settle_unknown_and_release_unstarted(self):
        self.reserve()
        settled = self.store.settle("op-a")
        self.assertEqual(settled.status, "SETTLED")
        self.assertIn("USAGE_UNKNOWN", self.store.snapshot("req-a").stop_reasons)
        self.assertTrue(self.store.settle("op-a").replayed)
        with self.assertRaises(BudgetStoreError):
            self.reserve(operation="op-b")

    def test_unstarted_release_requires_explicit_proof_and_preserves_late_fact(self):
        self.reserve()
        with self.assertRaises(BudgetStoreError):
            self.store.release_unstarted("op-a")
        released = self.store.release_unstarted("op-a", True)
        self.assertEqual(released.status, "RELEASED")
        self.assertEqual(self.store.snapshot("req-a").dimensions["tokens"].exposure, 0)
        self.assertTrue(self.store.release_unstarted("op-a", True).replayed)
        self.store.observe(self.obs(kind="final", amount=7))
        dim = self.store.snapshot("req-a").dimensions["tokens"]
        self.assertEqual(dim.known, 7)
        self.assertIn("RECOVERY_REQUIRED", self.store.snapshot("req-a").stop_reasons)

    def test_two_operations_survive_observation_updates(self):
        self.reserve()
        self.reserve(operation="op-b", task="task-b", tokens=4)
        self.store.observe(self.obs(amount=2))
        self.store.observe(self.obs(operation_id="op-b", observation_id="obs-b", economic_call_key="call-b", amount=1))
        snap = self.store.snapshot("req-a").dimensions["tokens"]
        self.assertEqual((snap.known, snap.held, snap.exposure), (3, 6, 9))

    def test_transaction_rollback_keeps_facts_and_outbox(self):
        self.reserve()
        self.store.observe(self.obs())
        before = len(self.store.outbox())
        with self.assertRaises(BudgetStoreError):
            self.store.observe(self.obs(amount=1, observation_id="bad", revision=2))
        self.assertEqual(len(self.store.outbox()), before)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 1)

    def test_existing_partial_or_malformed_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "partial.sqlite"
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE budget_meta(singleton INTEGER PRIMARY KEY, schema_version INTEGER)")
            db.commit(); db.close()
            with self.assertRaises(BudgetStoreError):
                BudgetStore(path)


if __name__ == "__main__":
    unittest.main()
