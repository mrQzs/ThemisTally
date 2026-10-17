#!/usr/bin/env python3
"""07-T2C-S pure claim/handoff boundary tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.claim_model import (  # noqa: E402
    ACCEPTED, ADMITTED, ActiveOperation, CLAIMED, ClaimFacts, ClaimModelError, ClaimReceipt, ClaimRequest,
    HandoffFacts, STARTED, START_UNKNOWN, active_task_decision, claim_decision, cleanup_decision, handoff_decision,
    idempotency_decision, liveness_decision,
    validate_claim_receipt,
)


def receipt(**changes: object) -> ClaimReceipt:
    values = {
        "repo_id": "code-kit", "request_id": "req-" + "a" * 32, "task_id": "task-a",
        "plan_version": 1, "operation_id": "op-a", "state": CLAIMED,
        "controller_generation": 4, "claim_generation": 9, "guard_version": 2,
        "stop_epoch": 0, "owner": "host/boot/owner", "lease_until": 100.0,
        "idempotency_key": "idem-a", "request_fingerprint": "fp-a",
    }
    values.update(changes)
    return ClaimReceipt(**values)  # type: ignore[arg-type]


def facts(**changes: object) -> HandoffFacts:
    values = {
        "request_open": True, "stop_requested": False, "controller_generation": 4,
        "claim_generation": 9, "guard_version": 2, "stop_epoch": 0,
        "lease_valid": True, "budget_available": True, "resources_available": True,
    }
    values.update(changes)
    return HandoffFacts(**values)  # type: ignore[arg-type]


def claim_facts(**changes: object) -> ClaimFacts:
    values = {
        "request_open": True, "stop_requested": False, "controller_generation": 4,
        "guard_version": 2, "stop_epoch": 0, "contract_valid": True,
        "baseline_valid": True, "upstream_accepted": True, "resources_available": True,
        "budget_available": True,
    }
    values.update(changes)
    return ClaimFacts(**values)  # type: ignore[arg-type]


def claim_request(**changes: object) -> ClaimRequest:
    values = {
        "repo_id": "code-kit", "request_id": "req-" + "a" * 32, "task_id": "task-a",
        "plan_version": 1, "idempotency_key": "idem-a", "request_fingerprint": "fp-a",
        "controller_generation": 4, "guard_version": 2, "stop_epoch": 0,
    }
    values.update(changes)
    return ClaimRequest(**values)  # type: ignore[arg-type]


class ClaimModelTests(unittest.TestCase):
    def test_receipt_is_strict_and_immutable(self) -> None:
        value = receipt()
        self.assertIs(validate_claim_receipt(value), value)
        with self.assertRaises((AttributeError, TypeError)):
            value.state = ADMITTED  # type: ignore[misc]
        with self.assertRaises(ClaimModelError):
            validate_claim_receipt(receipt(lease_until=float("nan")))
        with self.assertRaises(ClaimModelError):
            validate_claim_receipt(receipt(owner="\ud800"))
        with self.assertRaises(ClaimModelError):
            validate_claim_receipt(receipt(owner="owner\nlog"))
        with self.assertRaises(ClaimModelError):
            validate_claim_receipt(receipt(lease_until=-1.0))
        with self.assertRaises(ClaimModelError):
            validate_claim_receipt(receipt(lease_until=float(2**53)))

    def test_idempotency_replay_and_conflict(self) -> None:
        self.assertEqual(idempotency_decision(None, key="k", request_fingerprint="f").decision, "NEW")
        self.assertEqual(idempotency_decision(receipt(), key="idem-a", request_fingerprint="fp-a").decision,
                         "REPLAY")
        conflict = idempotency_decision(receipt(), key="idem-a", request_fingerprint="other")
        self.assertEqual((conflict.decision, conflict.reasons), ("CONFLICT", ("idempotency_fingerprint_mismatch",)))
        scoped = idempotency_decision(receipt(), key="idem-a", request_fingerprint="fp-a",
                                      repo_id="other", request_id="req-" + "a" * 32,
                                      task_id="task-a", plan_version=1)
        self.assertEqual((scoped.decision, scoped.reasons), ("CONFLICT", ("idempotency_scope_mismatch",)))

    def test_active_task_is_blocked_across_plan_versions(self) -> None:
        active = [ActiveOperation("code-kit", "req-" + "a" * 32, "task-a", 1, "op-a", CLAIMED)]
        decision = active_task_decision(active, repo_id="code-kit", request_id="req-" + "a" * 32,
                                        task_id="task-a", plan_version=2)
        self.assertEqual((decision.decision, decision.reasons), ("BLOCK", ("active_task",)))
        self.assertEqual(active_task_decision(active, repo_id="code-kit", request_id="req-" + "b" * 32,
                                              task_id="task-a", plan_version=2).decision, "ALLOW")
        self.assertEqual(active_task_decision(active, repo_id="code-kit", request_id="req-" + "a" * 32,
                                              task_id="task-b", plan_version=2).decision, "ALLOW")

    def test_claim_gate_combines_all_preconditions(self) -> None:
        allowed = claim_decision(claim_request(), claim_facts())
        self.assertEqual(allowed.decision, CLAIMED)
        blocked = claim_decision(claim_request(), claim_facts(contract_valid=None, budget_available=None))
        self.assertEqual(blocked.reasons, ("contract_unknown", "budget_unknown"))
        replay = claim_decision(claim_request(), claim_facts(), existing=receipt())
        self.assertEqual(replay.decision, "REPLAY")

    def test_claim_gate_checks_active_task_before_other_facts(self) -> None:
        active = [ActiveOperation("code-kit", "req-" + "a" * 32, "task-a", 1, "op-a", CLAIMED)]
        decision = claim_decision(claim_request(plan_version=2), claim_facts(request_open=None), active)
        self.assertEqual((decision.decision, decision.reasons), ("BLOCK", ("active_task",)))

    def test_handoff_requires_all_current_guards(self) -> None:
        self.assertEqual(handoff_decision(receipt(), facts()).decision, "HANDOFF_ACCEPTED")
        unknown = handoff_decision(receipt(), facts(lease_valid=None, budget_available=None))
        self.assertEqual(unknown.decision, "BLOCK")
        self.assertEqual(unknown.reasons, ("lease_unknown", "budget_unknown"))
        mismatch = handoff_decision(receipt(), facts(controller_generation=5))
        self.assertEqual(mismatch.reasons, ("controller_generation_mismatch",))
        with self.assertRaises(ClaimModelError):
            handoff_decision(receipt(), facts(controller_generation=1.0))  # type: ignore[arg-type]
        with self.assertRaises(ClaimModelError):
            claim_decision(claim_request(), claim_facts(contract_valid=1))  # type: ignore[arg-type]
        self.assertEqual(handoff_decision(receipt(state=ADMITTED), facts()).decision, "HANDOFF_ACCEPTED")

    def test_liveness_unknown_never_releases(self) -> None:
        self.assertEqual(liveness_decision(state=CLAIMED, handoff_accepted=False, liveness=None,
                                           identity_match=None, not_started_proven=None,
                                           fencing_confirmed=True).decision, START_UNKNOWN)
        self.assertEqual(liveness_decision(state=CLAIMED, handoff_accepted=False, liveness=True,
                                           identity_match=True, not_started_proven=None,
                                           fencing_confirmed=True).decision, "RETAIN_ACTIVE")
        self.assertEqual(liveness_decision(state=CLAIMED, handoff_accepted=False, liveness=False,
                                           identity_match=True, not_started_proven=True,
                                           fencing_confirmed=True).decision, "CANCELLED_NOT_STARTED")
        with self.assertRaises(ClaimModelError):
            liveness_decision(state=CLAIMED, handoff_accepted=False, liveness="false",  # type: ignore[arg-type]
                              identity_match=True, not_started_proven=True, fencing_confirmed=True)

    def test_handoff_requires_not_started_proof_before_release(self) -> None:
        uncertain = liveness_decision(state="HANDOFF_ACCEPTED", handoff_accepted=True, liveness=False,
                                      identity_match=True, not_started_proven=None, fencing_confirmed=True)
        self.assertEqual(uncertain.decision, START_UNKNOWN)
        released = liveness_decision(state="HANDOFF_ACCEPTED", handoff_accepted=True, liveness=False,
                                     identity_match=True, not_started_proven=True, fencing_confirmed=True)
        self.assertEqual(released.decision, "CANCELLED_NOT_STARTED")
        self.assertEqual(liveness_decision(state="HANDOFF_ACCEPTED", handoff_accepted=True, liveness=False,
                                           identity_match=True, not_started_proven=True,
                                           fencing_confirmed=False).decision, "BLOCK")
        self.assertEqual(liveness_decision(state=STARTED, handoff_accepted=False, liveness=False,
                                           identity_match=True, not_started_proven=True,
                                           fencing_confirmed=True).decision, "BLOCK")
        self.assertEqual(liveness_decision(state=STARTED, handoff_accepted=True, liveness=False,
                                           identity_match=True, not_started_proven=True,
                                           fencing_confirmed=True).decision, "BLOCK")

    def test_cleanup_keeps_unknown_supervision_scope_for_recovery(self) -> None:
        self.assertEqual(cleanup_decision(stray_processes=None, scope_empty_verified=True).decision,
                         "RECOVERY_REQUIRED")
        self.assertEqual(cleanup_decision(stray_processes=False, scope_empty_verified=None).decision,
                         "RECOVERY_REQUIRED")
        self.assertEqual(cleanup_decision(stray_processes=False, scope_empty_verified=False).decision,
                         "BLOCK")
        self.assertEqual(cleanup_decision(stray_processes=False, scope_empty_verified=True).decision,
                         "RELEASE")
        with self.assertRaises(ClaimModelError):
            cleanup_decision(stray_processes=0, scope_empty_verified=True)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main(verbosity=2)
