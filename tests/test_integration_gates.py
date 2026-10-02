"""07-S5.3 offline integration and production-boundary gates."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from codekit.integration_gates import (BLOCKED, OFFLINE_WIRED, PASS, PRODUCTION_BLOCKED, WAIT,
                                       contract_digest, evaluate_commit_permission,
                                       evaluate_integration_gates, evaluate_production_connectors,
                                       verify_09_10_wiring, verify_contract_hash, verify_fixed_candidate)
from codekit.projections import project_readiness, project_state, render_brief


def readiness_facts(**changes: object) -> dict[str, bool]:
    facts = {name: True for name in (
        "inputs_accepted", "baseline_present", "baseline_authorized", "planner_authorized",
        "planner_environment_ok", "planner_budget_ok", "input_locks_ok", "request_open",
        "contract_current", "approval_current", "capabilities_ok", "execution_authorized",
        "budget_ok", "conflicts_clear")}
    facts.update(changes)  # type: ignore[arg-type]
    return facts


def state_and_brief() -> tuple[dict[str, object], dict[str, object]]:
    state = project_state(indexed_cursor=2, applied_cursor=2, source_vector={"ledger": 2},
                          verification_ref="ledger:v3", as_of="2026-10-02T00:00:00Z",
                          source_coverage="complete", issues=[], budget_coverage="complete")
    return state, render_brief(state)


def candidate_ref() -> dict[str, str]:
    return {"kind": "candidate", "id": "candidate-1", "sha256": "a" * 64, "path": "candidate.json"}


class ContractAndCandidateTests(unittest.TestCase):
    def test_contract_hash_is_fixed_and_declared_reference_must_match(self) -> None:
        contract = {"task_id": "07-s5-3", "plan_version": 1, "checks": ["offline"]}
        digest = contract_digest(contract)
        self.assertEqual(verify_contract_hash(contract, digest).decision, PASS)
        serialized = b'{"task_id":"07-s5-3","plan_version":1,"checks":["offline"]}\n'
        self.assertEqual(verify_contract_hash(serialized, contract_digest(serialized)).decision, PASS)
        mismatch = verify_contract_hash(contract, "b" * 64)
        self.assertEqual(mismatch.decision, BLOCKED)
        self.assertIn("CONTRACT_HASH_MISMATCH", mismatch.reasons)
        bad_ref = verify_contract_hash(contract, digest,
                                       declared_ref={"kind": "contract", "id": "fixed-1",
                                                     "sha256": "c" * 64})
        self.assertEqual(bad_ref.decision, BLOCKED)
        self.assertIn("CONTRACT_REF_HASH_MISMATCH", bad_ref.reasons)
        self.assertEqual(verify_contract_hash(contract, None).decision, WAIT)

    def test_fixed_candidate_rejects_alias_drift_roundtrip_and_hash_drift(self) -> None:
        expected = candidate_ref()
        actual = {"candidate_ref": expected, "roundtrip_verified": True}
        self.assertEqual(verify_fixed_candidate(expected, actual).decision, PASS)
        dispatcher_candidate = {"tree": "b" * 40, "patch_sha256": "c" * 64,
                               "roundtrip_verified": True}
        self.assertEqual(verify_fixed_candidate(dispatcher_candidate, dispatcher_candidate).decision, PASS)
        self.assertEqual(verify_fixed_candidate(dispatcher_candidate,
                                                 {**dispatcher_candidate, "tree": "d" * 40}).decision, BLOCKED)
        self.assertEqual(verify_fixed_candidate(expected, {"candidate_ref": {**expected, "id": "latest"},
                                                              "roundtrip_verified": True}).decision, BLOCKED)
        self.assertEqual(verify_fixed_candidate(expected, {"candidate_ref": expected,
                                                            "roundtrip_verified": False}).decision, BLOCKED)
        self.assertEqual(verify_fixed_candidate(expected, {"candidate_ref": expected}).decision, WAIT)

    def test_commit_permission_never_creates_a_commit(self) -> None:
        blocked = evaluate_commit_permission(has_uncommitted_changes=True, integration_actions=())
        self.assertEqual(blocked.decision, BLOCKED)
        self.assertIn("COMMIT_PERMISSION_REQUIRED", blocked.reasons)
        waiting = evaluate_commit_permission(has_uncommitted_changes=True,
                                             integration_actions=("local_commit",))
        self.assertEqual(waiting.decision, WAIT)
        allowed = evaluate_commit_permission(has_uncommitted_changes=True,
                                             integration_actions=("local_commit",), commit_sha="d" * 64)
        self.assertEqual(allowed.decision, PASS)
        self.assertEqual(evaluate_commit_permission(has_uncommitted_changes=False).decision, PASS)
        self.assertEqual(evaluate_commit_permission(has_uncommitted_changes=None).decision, WAIT)
        generic_commit = evaluate_commit_permission(has_uncommitted_changes=True, integration_actions=("commit",),
                                                    commit_sha="e" * 64)
        self.assertEqual(generic_commit.decision, BLOCKED)


class WiringAndProductionTests(unittest.TestCase):
    def test_09_readiness_and_10_brief_are_linked_but_brief_cannot_authorize(self) -> None:
        state, brief = state_and_brief()
        decision = verify_09_10_wiring(readiness=project_readiness(readiness_facts()), state=state, brief=brief)
        self.assertEqual(decision.decision, OFFLINE_WIRED)
        self.assertTrue(decision.evidence["offline_only"])
        self.assertEqual(brief["dispatch_eligibility"], "not_evaluated")
        self.assertEqual(verify_09_10_wiring(readiness=project_readiness(readiness_facts()),
                                             state=state, brief={**brief, "dispatch_eligibility": "eligible"}).decision,
                         BLOCKED)
        self.assertEqual(verify_09_10_wiring(readiness=project_readiness(readiness_facts()),
                                             state=state, brief={**brief, "budget": "[未知] 无可核验预算快照"}).decision,
                         BLOCKED)

    def test_unknown_readiness_and_projection_mismatch_block(self) -> None:
        state, brief = state_and_brief()
        facts = readiness_facts(planner_authorized=None)
        projection = project_readiness(facts)
        self.assertFalse(projection.can_start_planner)
        self.assertEqual(verify_09_10_wiring(readiness={"can_refine": True,
                                                          "can_start_planner": False,
                                                          "can_execute": False,
                                                          "reasons": ("WAIT_PLANNER_AUTH",)},
                                             state=state,
                                             brief={**brief, "source_coverage": "partial"}).decision,
                         BLOCKED)

    def test_missing_and_synthetic_connectors_are_explicitly_production_blocked(self) -> None:
        missing = evaluate_production_connectors(None)
        self.assertEqual(missing.decision, PRODUCTION_BLOCKED)
        self.assertIn("CONNECTOR_03_MISSING", missing.reasons)
        synthetic = {stage: {"status": "offline_fixture", "production": False, "available": True}
                     for stage in ("03", "04", "05", "06", "09", "10")}
        blocked = evaluate_production_connectors(synthetic)
        self.assertEqual(blocked.decision, PRODUCTION_BLOCKED)
        self.assertTrue(all(reason.endswith("_OFFLINE_ONLY") for reason in blocked.reasons))

    def test_composite_gate_keeps_offline_evidence_and_production_block(self) -> None:
        contract = {"task_id": "07-s5-3", "plan_version": 1}
        expected = candidate_ref()
        state, brief = state_and_brief()
        connectors = {stage: {"status": "offline_fixture", "production": False, "available": True}
                     for stage in ("03", "04", "05", "06", "09", "10")}
        decision = evaluate_integration_gates(
            contract=contract, expected_contract_sha256=contract_digest(contract),
            candidate_ref=expected, candidate={"candidate_ref": expected, "roundtrip_verified": True},
            has_uncommitted_changes=False, integration_actions=(),
            readiness=project_readiness(readiness_facts()), state=state, brief=brief,
            connectors=connectors,
        )
        self.assertEqual(decision.decision, PRODUCTION_BLOCKED)
        self.assertEqual(decision.evidence["wiring"]["offline_only"], True)
        self.assertEqual(decision.evidence["production_decision"], PRODUCTION_BLOCKED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
