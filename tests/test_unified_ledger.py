from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from dataclasses import replace

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.atomic_claim_budget import AtomicClaimBudgetStore, AtomicLedgerError
from codekit.claim_model import ClaimFacts, ClaimRequest
from codekit.budget import BudgetPolicy
from codekit.unified_ledger import UnifiedLedgerStore, evidence_hash

REQUEST = "req-" + "a" * 32


def request() -> ClaimRequest:
    return ClaimRequest(
        repo_id="code-kit", request_id=REQUEST, task_id="task-a",
        plan_version=1, idempotency_key="key-a",
        request_fingerprint="fingerprint-a", controller_generation=1,
        guard_version=1, stop_epoch=0,
    )


def facts() -> ClaimFacts:
    return ClaimFacts(
        request_open=True, stop_requested=False, controller_generation=1,
        guard_version=1, stop_epoch=0, contract_valid=True,
        baseline_valid=True, upstream_accepted=True, resources_available=True,
        budget_available=True,
    )


class UnifiedLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "ledger.sqlite3"
        self.store = UnifiedLedgerStore(self.path)
        self.store.seed(REQUEST, "code-kit", BudgetPolicy({"tokens": 10}), max_concurrency=1)
        self.store.add_task(REQUEST, "task-a")

    def tearDown(self) -> None:
        self.store.close()
        self.temp.cleanup()

    def claim(self):
        return self.store.claim(
            request(), facts(), owner="owner-a",
            reservation={"tokens": 3}, resource_keys=[], lease_until=100,
        )

    def test_manifest_exposes_v3_tables_without_replacing_v2_schema(self):
        manifest = self.store.manifest()
        self.assertEqual(manifest["schema_version"], 3)
        self.assertIn("attempts", manifest["tables"])
        self.assertEqual(self.store.db.execute("SELECT schema_version FROM atomic_meta").fetchone()[0], 2)

    def test_evidence_hash_rejects_cycles_non_string_keys_and_unsafe_integers(self):
        value = {}
        value["self"] = value
        for payload in (value, {1: "integer-key"}, {"n": 2**53}, [("key", "value")]):
            with self.subTest(payload=payload if payload is not value else "cycle"), self.assertRaises(AtomicLedgerError) as caught:
                evidence_hash(payload)
            self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")

    def test_evidence_hash_accepts_json_boolean_and_finite_float(self):
        self.assertNotEqual(evidence_hash({"value": True}), evidence_hash({"value": 1}))
        self.assertNotEqual(evidence_hash({"value": 1.0}), evidence_hash({"value": 1}))

    def test_evidence_hash_rejects_unsupported_numeric_subclass(self):
        from enum import IntEnum

        class Value(IntEnum):
            ONE = 1

        with self.assertRaises(AtomicLedgerError) as caught:
            evidence_hash({"value": Value.ONE})
        self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")

    def test_attempt_lifecycle_is_fenced_and_idempotent(self):
        operation = self.claim()
        self.assertEqual(self.store.create_attempt(
            "attempt-a", operation.operation_id, "run-a", "stage-a", 1
        ).state, "ADMITTED")
        self.assertTrue(self.store.create_attempt(
            "attempt-a", operation.operation_id, "run-a", "stage-a", 1
        ).replayed)
        self.assertEqual(self.store.transition_attempt(
            "attempt-a", expected_state="ADMITTED", next_state="STARTING", generation=1
        ).state, "STARTING")
        self.assertTrue(self.store.transition_attempt(
            "attempt-a", expected_state="ADMITTED", next_state="STARTING", generation=1
        ).replayed)
        with self.assertRaises(AtomicLedgerError) as conflict:
            self.store.transition_attempt(
                "attempt-a", expected_state="ADMITTED", next_state="STARTING", generation=1,
                evidence_ref=evidence_hash({"different": True})
            )
        self.assertEqual(conflict.exception.code, "E_IDEMPOTENCY_CONFLICT")
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.transition_attempt(
                "attempt-a", expected_state="STARTING", next_state="STARTED", generation=2
            )
        self.assertEqual(caught.exception.code, "E_FENCED")
        self.assertEqual(self.store.transition_attempt(
            "attempt-a", expected_state="STARTING", next_state="START_UNKNOWN",
            generation=1, evidence_ref=evidence_hash({"reason": "timeout"})
        ).state, "START_UNKNOWN")
        self.assertEqual(self.store.transition_attempt(
            "attempt-a", expected_state="START_UNKNOWN", next_state="STARTED",
            generation=1, evidence_ref=evidence_hash({"pid": 7})
        ).state, "STARTED")
        self.assertEqual(self.store.transition_attempt(
            "attempt-a", expected_state="STARTED", next_state="REVIEW_PENDING",
            generation=1
        ).state, "REVIEW_PENDING")
        self.assertEqual(self.store.transition_attempt(
            "attempt-a", expected_state="REVIEW_PENDING", next_state="FINISHED",
            generation=1
        ).state, "FINISHED")

    def test_invalid_transition_and_duplicate_stage_are_rejected(self):
        operation = self.claim()
        self.store.create_attempt("attempt-a", operation.operation_id, "run-a", "stage-a", 1)
        with self.assertRaises(AtomicLedgerError):
            self.store.transition_attempt(
                "attempt-a", expected_state="ADMITTED", next_state="FINISHED", generation=1
            )
        with self.assertRaises(AtomicLedgerError):
            self.store.create_attempt("attempt-b", operation.operation_id, "run-b", "stage-a", 1)

    def test_cursor_advance_is_cas_and_replayable(self):
        operation = self.claim()
        self.store.create_attempt("attempt-cursor", operation.operation_id, "run-cursor", "stage-cursor", 1)
        high_water = self.store.outbox()[-1]["seq"]
        self.assertEqual(self.store.upsert_consumer_cursor(
            "projection-10", expected_seq=0, next_seq=high_water
        ).next_seq, high_water)
        self.assertTrue(self.store.upsert_consumer_cursor(
            "projection-10", expected_seq=0, next_seq=high_water
        ).replayed)
        with self.assertRaises(AtomicLedgerError):
            self.store.upsert_consumer_cursor("projection-10", expected_seq=0, next_seq=high_water + 1)
        self.assertTrue(self.store.upsert_consumer_cursor(
            "projection-10", expected_seq=high_water, next_seq=high_water
        ).replayed)

    def test_attempt_cannot_revive_cancelled_or_stopped_operation(self):
        operation = self.claim()
        self.store.cancel_unstarted(operation.operation_id, owner="owner-a", generation=1,
                                     not_started_proven=True)
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.create_attempt("attempt-cancelled", operation.operation_id, "run-cancelled", "stage-a", 1)
        self.assertEqual(caught.exception.code, "E_ATTEMPT_STATE")
        self.store.add_task(REQUEST, "task-b")
        operation = self.store.claim(
            replace(request(), task_id="task-b", idempotency_key="key-b", request_fingerprint="fingerprint-b"),
            facts(), owner="owner-a", reservation={"tokens": 3}, resource_keys=[], lease_until=100,
        )
        self.store.create_attempt("attempt-stopped", operation.operation_id, "run-stopped", "stage-a", 1)
        self.store.stop(REQUEST, "manual")
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.transition_attempt("attempt-stopped", expected_state="ADMITTED", next_state="STARTING", generation=1)
        self.assertEqual(caught.exception.code, "E_STOPPED")

    def test_stop_allows_started_attempt_to_enter_review_and_finish(self):
        operation = self.claim()
        self.store.create_attempt("attempt-finish", operation.operation_id, "run-finish", "stage-a", 1)
        self.store.transition_attempt("attempt-finish", expected_state="ADMITTED", next_state="STARTING", generation=1)
        self.store.transition_attempt("attempt-finish", expected_state="STARTING", next_state="STARTED", generation=1)
        self.store.stop(REQUEST, "manual")
        self.assertEqual(self.store.transition_attempt("attempt-finish", expected_state="STARTED", next_state="REVIEW_PENDING", generation=1).state, "REVIEW_PENDING")
        self.assertEqual(self.store.transition_attempt("attempt-finish", expected_state="REVIEW_PENDING", next_state="FINISHED", generation=1).state, "FINISHED")

    def test_attempt_generation_is_bound_to_operation_after_rollover(self):
        operation = self.claim()
        self.assertEqual(self.store.rollover(), 2)
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.create_attempt("attempt-fenced", operation.operation_id, "run-fenced", "stage-a", 1, generation=2)
        self.assertEqual(caught.exception.code, "E_FENCED")

    def test_migration_batch_is_immutable_and_conflicts_are_explicit(self):
        row_hash = evidence_hash({"row": 1})
        self.assertFalse(self.store.record_migration_batch(
            "migration-a", source_db="scheduler-v1", source_schema=1,
            row_hash=row_hash
        ))
        self.assertTrue(self.store.record_migration_batch(
            "migration-a", source_db="scheduler-v1", source_schema=1,
            row_hash=row_hash
        ))
        with self.assertRaises(AtomicLedgerError):
            self.store.record_migration_batch(
                "migration-a", source_db="scheduler-v1", source_schema=1,
                row_hash=evidence_hash({"row": 2})
            )

    def test_reopen_rejects_partial_v3_schema_before_activation(self):
        self.store.close()
        base = AtomicClaimBudgetStore(self.path)
        base.close()
        db = sqlite3.connect(self.path)
        try:
            db.execute("DROP TABLE attempts")
            db.execute("CREATE TABLE attempts(attempt_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL)")
            db.commit()
        finally:
            db.close()
        with self.assertRaises(AtomicLedgerError) as caught:
            UnifiedLedgerStore(self.path)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")
        self.assertIn("v3_ddl", caught.exception.reasons)

    def test_reopen_rejects_missing_v3_table_in_existing_ledger(self):
        self.store.close()
        db = sqlite3.connect(self.path)
        try:
            db.execute("DROP TABLE attempts")
            db.commit()
        finally:
            db.close()
        with self.assertRaises(AtomicLedgerError) as caught:
            UnifiedLedgerStore(self.path)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")
        self.assertIn("v3_partial_schema", caught.exception.reasons)

    def test_reopen_rejects_v3_attempt_generation_tampering(self):
        operation = self.claim()
        self.store.create_attempt("attempt-tampered", operation.operation_id, "run-tampered", "stage-tampered", 1)
        self.store.close()
        db = sqlite3.connect(self.path)
        db.execute("UPDATE attempts SET generation=99 WHERE attempt_id=?", ("attempt-tampered",))
        db.commit()
        db.close()
        with self.assertRaises(AtomicLedgerError) as caught:
            UnifiedLedgerStore(self.path)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")
        self.assertTrue(any(reason.startswith("attempt_binding:") for reason in caught.exception.reasons))

    def test_reopen_rejects_cursor_high_water_regression(self):
        operation = self.claim()
        self.store.create_attempt("attempt-cursor-tampered", operation.operation_id, "run-cursor-tampered", "stage-cursor-tampered", 1)
        high_water = self.store.outbox()[-1]["seq"]
        self.store.upsert_consumer_cursor("projection-tampered", expected_seq=0, next_seq=high_water)
        self.store.close()
        db = sqlite3.connect(self.path)
        db.execute("UPDATE consumer_cursors SET high_water=0 WHERE consumer_id=?", ("projection-tampered",))
        db.commit()
        db.close()
        with self.assertRaises(AtomicLedgerError) as caught:
            UnifiedLedgerStore(self.path)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")
        self.assertIn("cursor_high_water", caught.exception.reasons)


if __name__ == "__main__":
    unittest.main()
