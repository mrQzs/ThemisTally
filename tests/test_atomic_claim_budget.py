"""07-T3A/T2C-L: claim, budget and resource hold atomicity proof."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.atomic_claim_budget import (AtomicClaimBudgetStore, AtomicLedgerError)
from codekit.budget import BudgetPolicy, UsageObservation
from codekit.claim_model import ClaimFacts, ClaimRequest


REQUEST_ID = "req-" + "a" * 32


def policy() -> BudgetPolicy:
    return BudgetPolicy({"tokens": 10, "dispatches": 2}, {"task-a": {"tokens": 8, "dispatches": 2}, "task-b": {"tokens": 8, "dispatches": 2}})


def request(**changes: object) -> ClaimRequest:
    values = {
        "repo_id": "code-kit", "request_id": REQUEST_ID, "task_id": "task-a", "plan_version": 1,
        "idempotency_key": "key-a", "request_fingerprint": "fingerprint-a",
        "controller_generation": 1, "guard_version": 1, "stop_epoch": 0,
    }
    values.update(changes)
    return ClaimRequest(**values)  # type: ignore[arg-type]


def facts(**changes: object) -> ClaimFacts:
    values = {
        "request_open": True, "stop_requested": False, "controller_generation": 1,
        "guard_version": 1, "stop_epoch": 0, "contract_valid": True, "baseline_valid": True,
        "upstream_accepted": True, "resources_available": True, "budget_available": True,
    }
    values.update(changes)
    return ClaimFacts(**values)  # type: ignore[arg-type]


def observation(operation_id: str, **changes: object) -> UsageObservation:
    values = {
        "observation_id": "obs-a", "operation_id": operation_id, "dimension": "tokens",
        "kind": "cumulative", "amount": 3, "revision": 1,
        "economic_call_key": "call-a", "evidence_ref": "e" * 64,
        "request_id": REQUEST_ID, "task_id": "task-a",
    }
    values.update(changes)
    if "kind" in changes:
        values["final"] = changes["kind"] == "final"
    return UsageObservation(**values)  # type: ignore[arg-type]


class AtomicClaimBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "atomic.sqlite3"
        self.store = AtomicClaimBudgetStore(self.path)
        self.store.seed(REQUEST_ID, "code-kit", policy(), max_concurrency=2)
        self.store.add_task(REQUEST_ID, "task-a", max_attempts=3)
        self.store.add_task(REQUEST_ID, "task-b", max_attempts=3)
        self.store.add_task(REQUEST_ID, "task-c", max_attempts=3)

    def tearDown(self) -> None:
        self.store.close()
        self.temp.cleanup()

    def claim(self, **changes: object):
        values = {"reservation": {"tokens": 5, "dispatches": 1}, "resource_keys": ["src/a"], "owner": "owner-a"}
        values.update(changes)
        return self.store.claim(request(**values.pop("request", {})), facts(**values.pop("facts", {})), **values)  # type: ignore[arg-type]

    def test_schema_is_durable_and_strict(self) -> None:
        self.assertEqual(self.store.db.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        self.assertEqual(self.store.db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(self.store.db.execute("PRAGMA synchronous").fetchone()[0], 2)
        self.assertEqual(self.store.db.execute("SELECT max_concurrency FROM requests").fetchone()[0], 2)

        partial = Path(self.temp.name) / "partial.sqlite3"
        db = sqlite3.connect(partial)
        db.execute("CREATE TABLE requests(request_id TEXT PRIMARY KEY)")
        db.commit()
        db.close()
        with self.assertRaises(AtomicLedgerError) as caught:
            AtomicClaimBudgetStore(partial)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")

        wrong_index = Path(self.temp.name) / "wrong-index.sqlite3"
        seeded = AtomicClaimBudgetStore(wrong_index)
        seeded.close()
        db = sqlite3.connect(wrong_index)
        db.execute("DROP INDEX one_active_task_v2")
        db.execute("CREATE INDEX one_active_task_v2 ON operations(request_id)")
        db.commit()
        db.close()
        with self.assertRaises(AtomicLedgerError) as caught:
            AtomicClaimBudgetStore(wrong_index)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")

    def test_seed_and_claim_are_idempotent_and_write_one_outbox_event(self) -> None:
        first = self.claim()
        replay = self.claim(owner="other-owner")
        self.assertEqual((replay.operation_id, replay.replayed), (first.operation_id, True))
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM operations").fetchone()[0], 1)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM resource_holds").fetchone()[0], 1)
        self.assertEqual([row["event_type"] for row in self.store.outbox()], ["atomic.seeded", "atomic.claimed"])
        with self.assertRaises(AtomicLedgerError) as caught:
            self.claim(request={"request_fingerprint": "other"})
        self.assertEqual(caught.exception.code, "E_IDEMPOTENCY_CONFLICT")

    def test_claim_failure_rolls_back_operation_hold_and_outbox(self) -> None:
        with patch.object(self.store, "_emit", side_effect=RuntimeError("failpoint")):
            with self.assertRaises(RuntimeError):
                self.claim()
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM operations").fetchone()[0], 0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM resource_holds").fetchone()[0], 0)
        self.assertEqual([row["event_type"] for row in self.store.outbox()], ["atomic.seeded"])

    def test_budget_failure_is_atomic_and_resource_conflicts_are_scoped(self) -> None:
        self.claim(reservation={"tokens": 8, "dispatches": 2})
        with self.assertRaises(AtomicLedgerError) as caught:
            self.claim(request={"task_id": "task-b", "idempotency_key": "key-b", "request_fingerprint": "fp-b"}, resource_keys=["src/b"], reservation={"tokens": 3, "dispatches": 1})
        self.assertEqual(caught.exception.code, "E_BUDGET_EXCEEDED")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM operations").fetchone()[0], 1)

        other_request = "req-" + "b" * 32
        self.store.seed(other_request, "code-kit", policy())
        self.store.add_task(other_request, "task-a")
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.claim(ClaimRequest("code-kit", other_request, "task-a", 1, "key", "fp", 1, 1, 0), facts(), owner="owner", reservation={"tokens": 1, "dispatches": 1}, resource_keys=["src/a"])
        self.assertEqual(caught.exception.code, "E_RESOURCE_BUSY")

    def test_concurrency_and_active_task_limits_are_enforced(self) -> None:
        self.claim(resource_keys=[])
        self.claim(request={"task_id": "task-b", "idempotency_key": "key-b", "request_fingerprint": "fp-b"}, resource_keys=[])
        with self.assertRaises(AtomicLedgerError) as caught:
            self.claim(request={"task_id": "task-c", "idempotency_key": "key-c", "request_fingerprint": "fp-c"}, resource_keys=[])
        self.assertEqual(caught.exception.code, "E_CONCURRENCY")

        with AtomicClaimBudgetStore(":memory:") as other:
            other.seed(REQUEST_ID, "code-kit", policy(), max_concurrency=2)
            other.add_task(REQUEST_ID, "task-a")
            first = other.claim(request(), facts(), owner="owner", reservation={"tokens": 1, "dispatches": 1}, resource_keys=[])
            with self.assertRaises(AtomicLedgerError) as caught:
                other.claim(request(plan_version=2, idempotency_key="key-d", request_fingerprint="fp-d"), facts(), owner="owner", reservation={"tokens": 1, "dispatches": 1}, resource_keys=[])
            self.assertEqual(caught.exception.code, "E_CLAIM_BLOCKED")

    def test_observation_replay_final_releases_hold_and_stops_on_overrun(self) -> None:
        result = self.claim()
        applied = self.store.observe(observation(result.operation_id, kind="final", amount=4))
        self.store.observe(observation(result.operation_id, observation_id="obs-dispatches", dimension="dispatches", kind="final", amount=1, economic_call_key="call-dispatches"))
        self.assertEqual(applied.state, "APPLIED")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM resource_holds").fetchone()[0], 1)
        self.assertEqual(self.store.snapshot(REQUEST_ID).dimensions["tokens"].held, 0)
        replay = self.store.observe(observation(result.operation_id, kind="final", amount=4))
        self.assertTrue(replay.replayed)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 2)
        finished = self.store.finish_operation(result.operation_id, owner="owner-a", generation=1, cleanup_proven=True)
        self.assertEqual(finished.state, "FINISHED")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM resource_holds").fetchone()[0], 0)

        result2 = self.claim(request={"task_id": "task-b", "idempotency_key": "key-b", "request_fingerprint": "fp-b"}, reservation={"tokens": 1, "dispatches": 1}, resource_keys=[])
        overrun = self.store.observe(observation(result2.operation_id, observation_id="obs-b", kind="final", amount=11, economic_call_key="call-b", task_id="task-b"))
        self.assertIn("BUDGET_EXCEEDED", overrun.reasons)
        self.assertEqual(self.store.db.execute("SELECT stopped FROM requests WHERE request_id=?", (REQUEST_ID,)).fetchone()[0], 1)
        self.store.close()
        self.store = AtomicClaimBudgetStore(self.path)
        self.assertIn("BUDGET_EXCEEDED", self.store.snapshot(REQUEST_ID).stop_reasons)

    def test_unknown_usage_keeps_exposure_and_blocks_new_claim(self) -> None:
        result = self.claim()
        unknown = self.store.observe(observation(result.operation_id, kind="unknown", amount=None, unknown_reason="provider_timeout"))
        self.assertIn("USAGE_UNKNOWN", unknown.reasons)
        snapshot = self.store.snapshot(REQUEST_ID)
        self.assertEqual(snapshot.dimensions["tokens"].unknown_operations, (result.operation_id,))
        self.store.close()
        self.store = AtomicClaimBudgetStore(self.path)
        self.assertIn("USAGE_UNKNOWN", self.store.snapshot(REQUEST_ID).stop_reasons)
        with self.assertRaises(AtomicLedgerError) as caught:
            self.claim(request={"task_id": "task-b", "idempotency_key": "key-b", "request_fingerprint": "fp-b"}, reservation={"tokens": 1, "dispatches": 1}, resource_keys=[])
        self.assertEqual(caught.exception.code, "E_CLAIM_BLOCKED")

    def test_start_unknown_recovery_reason_survives_reopen(self) -> None:
        result = self.claim(lease_until=10)
        self.store.handoff(result.operation_id, owner="owner-a", now=1, budget_available=True, resources_available=True)
        self.store.mark_start_unknown(result.operation_id, owner="owner-a", generation=1)
        self.store.close()
        self.store = AtomicClaimBudgetStore(self.path)
        snapshot = self.store.snapshot(REQUEST_ID)
        self.assertIn("RECOVERY_REQUIRED", snapshot.stop_reasons)
        self.assertEqual(snapshot.coverage, "incomplete")

    def test_rollover_fences_controller_stops_open_requests_and_advances_global_high_water(self) -> None:
        first = self.claim(resource_keys=[])
        before = self.store.snapshot(REQUEST_ID).as_of_seq
        other_request = "req-" + "b" * 32
        self.store.seed(other_request, "code-kit", policy())
        self.store.add_task(other_request, "task-a")
        self.assertEqual(self.store.rollover(), 2)
        after = self.store.snapshot(REQUEST_ID).as_of_seq
        self.assertGreater(after, before)
        self.assertIn("RECOVERY_REQUIRED", self.store.snapshot(REQUEST_ID).stop_reasons)
        self.assertIn("RECOVERY_REQUIRED", self.store.snapshot(other_request).stop_reasons)
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.cancel_unstarted(first.operation_id, owner="owner-a", generation=1, not_started_proven=True)
        self.assertEqual(caught.exception.code, "E_FENCED")

    def test_rollover_start_unknown_can_be_reconciled_by_new_owner_with_proof(self) -> None:
        result = self.claim(lease_until=10)
        self.store.handoff(result.operation_id, owner="owner-a", now=1, budget_available=True, resources_available=True)
        self.store.mark_start_unknown(result.operation_id, owner="owner-a", generation=1)
        self.assertEqual(self.store.rollover(), 2)
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.reconcile_not_started(result.operation_id, owner="owner-b", generation=2, not_started_proven=True)
        self.assertEqual(caught.exception.code, "E_FENCED")
        reconciled = self.store.reconcile_not_started(result.operation_id, owner="owner-b", generation=2,
                                                       not_started_proven=True, takeover_proven=True)
        self.assertEqual((reconciled.state, reconciled.reasons), ("CANCELLED_NOT_STARTED", ("RECOVERY_RECONCILED",)))
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM resource_holds WHERE operation_id=?", (result.operation_id,)).fetchone()[0], 0)
        replay = self.store.reconcile_not_started(result.operation_id, owner="owner-b", generation=2, not_started_proven=True)
        self.assertTrue(replay.replayed)

    def test_cancel_requires_proof_releases_hold_and_late_fact_marks_recovery(self) -> None:
        result = self.claim()
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.cancel_unstarted(result.operation_id, owner="owner-a", generation=1)
        self.assertEqual(caught.exception.code, "E_RELEASE_NOT_PROVEN")
        cancelled = self.store.cancel_unstarted(result.operation_id, owner="owner-a", generation=1, not_started_proven=True)
        self.assertEqual(cancelled.state, "CANCELLED_NOT_STARTED")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM resource_holds").fetchone()[0], 0)
        late = self.store.observe(observation(result.operation_id, kind="final", amount=2))
        self.assertIn("RECOVERY_REQUIRED", late.reasons)
        self.assertEqual(self.store.db.execute("SELECT stopped FROM requests WHERE request_id=?", (REQUEST_ID,)).fetchone()[0], 1)

    def test_stop_and_claim_facts_are_fenced(self) -> None:
        self.store.stop(REQUEST_ID, "OPERATOR_STOP")
        with self.assertRaises(AtomicLedgerError) as caught:
            self.claim(request={"idempotency_key": "key-z", "request_fingerprint": "fp-z"})
        self.assertEqual(caught.exception.code, "E_CLAIM_BLOCKED")
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.claim(request(), facts(contract_valid=False), owner="owner", reservation={"tokens": 1, "dispatches": 1}, resource_keys=[])
        self.assertEqual(caught.exception.code, "E_CLAIM_BLOCKED")

    def test_handoff_rechecks_lease_guards_and_is_idempotent(self) -> None:
        result = self.claim(lease_until=10)
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.handoff(result.operation_id, owner="owner-a", now=1, budget_available=None, resources_available=True)
        self.assertEqual(caught.exception.code, "E_HANDOFF_BLOCKED")
        accepted = self.store.handoff(result.operation_id, owner="owner-a", now=1, budget_available=True, resources_available=True)
        self.assertEqual(accepted.state, "HANDOFF_ACCEPTED")
        replay = self.store.handoff(result.operation_id, owner="owner-a", now=2)
        self.assertTrue(replay.replayed)
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.handoff(result.operation_id, owner="owner-a", now=10)
        self.assertEqual(caught.exception.code, "E_HANDOFF_BLOCKED")

    def test_start_unknown_stops_request_and_retains_resource_risk(self) -> None:
        result = self.claim(lease_until=10)
        self.store.handoff(result.operation_id, owner="owner-a", now=1, budget_available=True, resources_available=True)
        unknown = self.store.mark_start_unknown(result.operation_id, owner="owner-a", generation=1)
        self.assertEqual((unknown.state, unknown.reasons), ("START_UNKNOWN", ("RECOVERY_REQUIRED",)))
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM resource_holds").fetchone()[0], 1)
        snapshot = self.store.snapshot(REQUEST_ID)
        self.assertEqual(snapshot.stop_reasons, ("RECOVERY_REQUIRED",))
        self.assertEqual(snapshot.coverage, "incomplete")
        self.assertEqual(snapshot.dimensions["tokens"].unknown_operations, (result.operation_id,))
        replay = self.store.mark_start_unknown(result.operation_id, owner="owner-a", generation=1)
        self.assertTrue(replay.replayed)
        with self.assertRaises(AtomicLedgerError) as caught:
            self.claim(request={"task_id": "task-b", "idempotency_key": "key-b", "request_fingerprint": "fp-b"}, resource_keys=[])
        self.assertEqual(caught.exception.code, "E_CLAIM_BLOCKED")
        with self.assertRaises(AtomicLedgerError) as caught:
            self.claim(request={"plan_version": 2, "idempotency_key": "key-c", "request_fingerprint": "fp-c"}, resource_keys=[])
        self.assertEqual(caught.exception.code, "E_CLAIM_BLOCKED")

    def test_final_usage_after_handoff_does_not_release_os_risk_hold(self) -> None:
        result = self.claim(lease_until=10)
        self.store.handoff(result.operation_id, owner="owner-a", now=1, budget_available=True, resources_available=True)
        self.store.observe(observation(result.operation_id, kind="final", amount=2))
        self.store.observe(observation(result.operation_id, observation_id="obs-dispatches", dimension="dispatches", kind="final", amount=1, economic_call_key="call-dispatches"))
        self.assertEqual(self.store.db.execute("SELECT state FROM operations WHERE operation_id=?", (result.operation_id,)).fetchone()[0], "HANDOFF_ACCEPTED")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM resource_holds").fetchone()[0], 1)

    def test_handoff_rejects_missing_internal_hold_even_when_external_fact_is_true(self) -> None:
        result = self.claim(lease_until=10)
        self.store.db.execute("DELETE FROM resource_holds WHERE operation_id=?", (result.operation_id,))
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.handoff(result.operation_id, owner="owner-a", now=1, budget_available=True, resources_available=True)
        self.assertEqual(caught.exception.code, "E_HANDOFF_BLOCKED")

    def test_cancel_is_fenced_by_current_controller_generation(self) -> None:
        result = self.claim()
        self.store.db.execute("UPDATE controller SET generation=2 WHERE singleton=1")
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.cancel_unstarted(result.operation_id, owner="owner-a", generation=1, not_started_proven=True)
        self.assertEqual(caught.exception.code, "E_FENCED")
        self.assertEqual(self.store.db.execute("SELECT state FROM operations WHERE operation_id=?", (result.operation_id,)).fetchone()[0], "CLAIMED")

    def test_handoff_rechecks_internal_budget_stop_reason(self) -> None:
        result = self.claim(lease_until=10)
        self.store.db.execute("INSERT INTO stop_reasons(request_id,reason,stop_epoch) VALUES(?,?,?)", (REQUEST_ID, "USAGE_UNKNOWN", 1))
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.handoff(result.operation_id, owner="owner-a", now=1, budget_available=True, resources_available=True)
        self.assertEqual(caught.exception.code, "E_HANDOFF_BLOCKED")

    def test_start_unknown_requires_internal_resource_holds(self) -> None:
        result = self.claim(lease_until=10)
        self.store.handoff(result.operation_id, owner="owner-a", now=1, budget_available=True, resources_available=True)
        self.store.db.execute("DELETE FROM resource_holds WHERE operation_id=?", (result.operation_id,))
        with self.assertRaises(AtomicLedgerError) as caught:
            self.store.mark_start_unknown(result.operation_id, owner="owner-a", generation=1)
        self.assertEqual(caught.exception.code, "E_START_UNKNOWN_BLOCKED")
        self.assertEqual(self.store.db.execute("SELECT state FROM operations WHERE operation_id=?", (result.operation_id,)).fetchone()[0], "HANDOFF_ACCEPTED")

    def test_reopen_rejects_malformed_json_and_hold_mismatch(self) -> None:
        result = self.claim()
        self.store.close()
        db = sqlite3.connect(self.path)
        db.execute("UPDATE operations SET reservation_json='not-json' WHERE operation_id=?", (result.operation_id,))
        db.commit()
        db.close()
        with self.assertRaises(AtomicLedgerError) as caught:
            AtomicClaimBudgetStore(self.path)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")
        db = sqlite3.connect(self.path)
        db.execute("UPDATE operations SET reservation_json=? WHERE operation_id=?", (json.dumps({"tokens": 5, "dispatches": 1}), result.operation_id))
        db.execute("UPDATE outbox SET payload_json='[]' WHERE event_type='atomic.claimed'")
        db.commit()
        db.close()
        with self.assertRaises(AtomicLedgerError) as caught:
            AtomicClaimBudgetStore(self.path)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")


if __name__ == "__main__":
    unittest.main(verbosity=2)
