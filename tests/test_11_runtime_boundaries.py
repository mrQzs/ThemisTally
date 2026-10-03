import hashlib
import unittest

from scripts.codekit.adapters.heterogeneous import (
    AdapterFacadeError,
    CancellationObservation,
    HeterogeneousAdapterFacade,
    ProfileHandoff,
    ProfileRouter,
    check_role_gate,
    validate_handoff,
)
from scripts.codekit.adapters.second_cli import ClaudeCodeAdapter, SecondCliError
from scripts.codekit.planner_runtime import PlanningBudgetLedger


def ref(name: str, payload: bytes = b"fixture\n"):
    return {"kind": "fixture", "id": name, "path": "fixtures/" + name + ".json", "sha256": hashlib.sha256(payload).hexdigest()}


class AlternateAdapter(ClaudeCodeAdapter):
    adapter_id = "alternate-cli"


class RuntimeBoundaryTests(unittest.TestCase):
    def test_facade_routes_by_identity_without_provider_branch(self):
        facade = HeterogeneousAdapterFacade([ClaudeCodeAdapter(), AlternateAdapter()])
        self.assertEqual(facade.adapter_ids(), ("alternate-cli", "claude-code"))
        self.assertIsInstance(facade.resolve("claude-code"), ClaudeCodeAdapter)
        with self.assertRaisesRegex(AdapterFacadeError, "E_ADAPTER_UNKNOWN"):
            facade.resolve("missing")

    def test_profile_router_binds_profile_to_registered_adapter(self):
        adapter = ClaudeCodeAdapter()
        capability = adapter.probe(timeout=1).capability
        profile = adapter.validate_profile(capability, role="planner", platform=capability.platforms[0],
                                           model_id="offline-test-model", profile_id="router-planner",
                                           required_capabilities=("terminal_event",), require_observed=False)
        router = ProfileRouter(HeterogeneousAdapterFacade([adapter]))
        router.register(profile)
        invocation = router.build_invocation("router-planner", request_id="req", run_id="run", cwd=".",
                                             environment={}, prompt="plan")
        self.assertEqual(invocation.adapter.adapter_id, "claude-code")
        with self.assertRaisesRegex(AdapterFacadeError, "E_PROFILE_UNKNOWN"):
            router.resolve("missing")

    def test_local_probe_does_not_unlock_production_profile(self):
        adapter = ClaudeCodeAdapter()
        capability = adapter.probe(timeout=1).capability
        with self.assertRaisesRegex(SecondCliError, "E_CLI_PROFILE"):
            adapter.validate_profile(capability, role="planner", platform=capability.platforms[0],
                                     model_id="offline-test-model", profile_id="requires-real-evidence",
                                     required_capabilities=("terminal_event",), require_observed=True)

    def test_invocation_digest_binds_stdin_and_resource_allowlist(self):
        adapter = ClaudeCodeAdapter()
        capability = adapter.probe(timeout=1).capability
        # Probe evidence is insufficient for production model access, but the
        # offline shape is still useful for deterministic invocation checks.
        profile = adapter.validate_profile(capability, role="planner", platform=capability.platforms[0],
                                           model_id="offline-test-model", profile_id="planner-test",
                                           required_capabilities=("terminal_event",), require_observed=False)
        one = adapter.build_invocation(profile, request_id="req", run_id="run", cwd=".", environment={},
                                       prompt=b"one", resource_allowlist=(ref("one"),))
        two = adapter.build_invocation(profile, request_id="req", run_id="run", cwd=".", environment={},
                                       prompt=b"two", resource_allowlist=(ref("one"),))
        three = adapter.build_invocation(profile, request_id="req", run_id="run", cwd=".", environment={},
                                         prompt=b"one", resource_allowlist=(ref("two"),))
        self.assertNotEqual(one.invocation_sha256(), two.invocation_sha256())
        self.assertNotEqual(one.invocation_sha256(), three.invocation_sha256())
        self.assertEqual(one.session_id, two.session_id)
        executor_profile = adapter.validate_profile(capability, role="executor", platform=capability.platforms[0],
                                                     model_id="offline-test-model", profile_id="executor-test",
                                                     required_capabilities=("terminal_event",), require_observed=False)
        executor = adapter.build_invocation(executor_profile, request_id="req", run_id="run", cwd=".",
                                             environment={}, prompt=b"one", resource_allowlist=(ref("one"),))
        self.assertNotEqual(one.session_id, executor.session_id)

    def test_handoff_is_cross_session_read_only_and_generation_fenced(self):
        handoff = ProfileHandoff("req", "run", "planner-p", "executor-p", "planner-session", "executor-session",
                                 ref("contract"), (ref("input"),), 3)
        validate_handoff(handoff, request_id="req", budget_generation=3,
                         planner_profile_id="planner-p", executor_profile_id="executor-p")
        with self.assertRaisesRegex(AdapterFacadeError, "E_HANDOFF_SESSION"):
            ProfileHandoff("req", "run", "planner-p", "executor-p", "same", "same",
                           ref("contract"), (ref("input"),), 3)
        with self.assertRaisesRegex(AdapterFacadeError, "E_HANDOFF_GENERATION"):
            validate_handoff(handoff, request_id="req", budget_generation=4,
                             planner_profile_id="planner-p", executor_profile_id="executor-p")

    def test_cancel_and_response_loss_are_unknown_until_reconciled(self):
        unknown = CancellationObservation.classify(request_id="req", run_id="run", generation=1,
                                                    cancel_requested=True, exit_code=None,
                                                    response_lost=True, process_observed=None)
        self.assertEqual(unknown.state, "START_UNKNOWN")
        cancelled = CancellationObservation.classify(request_id="req", run_id="run", generation=1,
                                                      cancel_requested=True, exit_code=130,
                                                      process_observed=False)
        self.assertEqual(cancelled.state, "CANCELLED")
        after_exit = CancellationObservation.classify(request_id="req", run_id="run", generation=1,
                                                       cancel_requested=True, exit_code=0,
                                                       process_observed=False, cancel_after_exit=True)
        self.assertEqual(after_exit.state, "CANCEL_AFTER_EXIT")
        recovery = CancellationObservation.classify(request_id="req", run_id="run", generation=1,
                                                     cancel_requested=True, exit_code=None,
                                                     process_observed=True)
        self.assertEqual(recovery.state, "RECOVERY_REQUIRED")

    def test_role_gate_uses_shared_budget_and_rejects_stopped_or_unbound(self):
        adapter = ClaudeCodeAdapter()
        capability = adapter.probe(timeout=1).capability
        profile = adapter.validate_profile(capability, role="executor", platform=capability.platforms[0],
                                           model_id="offline-test-model", profile_id="executor-test",
                                           required_capabilities=("terminal_event",), require_observed=False)
        ledger = PlanningBudgetLedger.calls("req", "task", 1)
        allowed = check_role_gate(profile=profile, expected_role="executor", ledger=ledger)
        self.assertTrue(allowed.allowed)
        stopped = ledger.stop("USER_STOP")
        blocked = check_role_gate(profile=profile, expected_role="executor", ledger=stopped)
        self.assertFalse(blocked.allowed)
        self.assertIn("BUDGET_USER_STOP", blocked.reasons)
        unbound = check_role_gate(profile=profile, expected_role="executor")
        self.assertFalse(unbound.allowed)
        self.assertIn("BUDGET_UNBOUND", unbound.reasons)


if __name__ == "__main__":
    unittest.main()
