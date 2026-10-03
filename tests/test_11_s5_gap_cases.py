"""Offline S5 boundary regressions found during the Pi compatibility audit."""

import hashlib
import unittest
from dataclasses import replace

from scripts.codekit.adapters.capability import (
    AdapterCapability,
    CapabilityError,
    PreflightResult,
    ProfileBinding,
)
from scripts.codekit.adapters.heterogeneous import (
    AdapterFacadeError,
    CancellationObservation,
    HeterogeneousAdapterFacade,
    ProfileRouter,
    evaluate_start_gate,
    check_role_gate,
)
from scripts.codekit.adapters.second_cli import ClaudeCodeAdapter
from scripts.codekit.planner_runtime import PlanningBudgetLedger


def _ref(name: str, payload: bytes = b"s5-gap\n") -> dict[str, str]:
    return {
        "kind": "fixture",
        "id": name,
        "path": "fixtures/" + name + ".json",
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


class _ForgedInvocationAdapter(ClaudeCodeAdapter):
    adapter_id = "s5-forged"

    def build_invocation(self, profile, **kwargs):  # type: ignore[no-untyped-def]
        result = super().build_invocation(profile, **kwargs)
        return replace(result, adapter=replace(result.adapter, adapter_id="different-adapter"))


class S5GapTests(unittest.TestCase):
    def test_ready_preflight_cannot_be_forged_with_blocking_facts(self):
        binding = ProfileBinding("fixture", "planner", "linux", "model", "a" * 64, True, ())
        with self.assertRaises(CapabilityError) as caught:
            PreflightResult("READY", binding, "model", "model", "MISSING", False, ())
        self.assertEqual(caught.exception.code, "E_PREFLIGHT_READY")

        with self.assertRaises(CapabilityError) as caught:
            PreflightResult("READY", binding, "model", "other", "READY", True, ())
        self.assertEqual(caught.exception.code, "E_PREFLIGHT_READY")

    def test_cancel_classification_distinguishes_observed_non_cancel(self):
        observation = CancellationObservation.classify(
            request_id="request", run_id="run", generation=1,
            cancel_requested=False, exit_code=0, process_observed=False,
        )
        self.assertEqual(observation.state, "NOT_CANCELLED")
        with self.assertRaisesRegex(AdapterFacadeError, "E_RECOVERY_SCHEMA"):
            CancellationObservation.classify(
                request_id="request", run_id="run", generation=1,
                cancel_requested=False, exit_code=0, process_observed=False,
                cancel_after_exit=True,
            )

    def test_start_gate_reports_malformed_handoff_without_dereference(self):
        adapter = ClaudeCodeAdapter()
        capability = adapter.probe(timeout=1).capability
        profile = adapter.validate_profile(
            capability, role="executor", platform=capability.platforms[0],
            model_id="offline-test-model", profile_id="s5-malformed-handoff",
            required_capabilities=("terminal_event",), require_observed=False,
        )
        gate = evaluate_start_gate(
            run_context={}, profile=profile, handoff=None,  # type: ignore[arg-type]
            ledger=PlanningBudgetLedger.calls("request", "task", 1),
        )
        self.assertFalse(gate.allowed)
        self.assertIn("HANDOFF_SCHEMA", gate.reasons)

    def test_role_gate_classifies_malformed_handoff_and_budget(self):
        adapter = ClaudeCodeAdapter()
        capability = adapter.probe(timeout=1).capability
        profile = adapter.validate_profile(
            capability, role="executor", platform=capability.platforms[0],
            model_id="offline-test-model", profile_id="s5-role-gate",
            required_capabilities=("terminal_event",), require_observed=False,
        )
        gate = check_role_gate(
            profile=profile, expected_role="executor", handoff={},  # type: ignore[arg-type]
            ledger=object(),  # type: ignore[arg-type]
        )
        self.assertFalse(gate.allowed)
        self.assertIn("HANDOFF_SCHEMA", gate.reasons)
        self.assertIn("BUDGET_SCHEMA", gate.reasons)

    def test_router_rejects_invocation_identity_forged_by_adapter(self):
        adapter = _ForgedInvocationAdapter()
        capability = adapter.probe(timeout=1).capability
        profile = adapter.validate_profile(
            capability, role="planner", platform=capability.platforms[0],
            model_id="offline-test-model", profile_id="s5-forged-profile",
            required_capabilities=("terminal_event",), require_observed=False,
        )
        router = ProfileRouter(HeterogeneousAdapterFacade([adapter]))
        router.register(profile, capability=capability)
        with self.assertRaisesRegex(AdapterFacadeError, "E_ADAPTER_IDENTITY"):
            router.build_invocation(
                profile.profile_id, request_id="request", run_id="run", cwd=".",
                environment={}, prompt="offline",
            )


if __name__ == "__main__":
    unittest.main()
