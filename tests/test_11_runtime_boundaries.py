import hashlib
import unittest
from dataclasses import replace

from scripts.codekit.adapters.heterogeneous import (
    AdapterFacadeError,
    CancellationObservation,
    HeterogeneousAdapterFacade,
    ProfileHandoff,
    ProfileRouter,
    check_role_gate,
    evaluate_start_gate,
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
        contract = ref("contract")
        request_id = "req-11111111111141118111111111111111"
        run_id = "run-22222222222242228222222222222222"
        context = {"schema_version": 1, "record_type": "run-context", "request_id": request_id,
                   "task_id": "task-11", "plan_version": 1, "run_id": run_id, "attempt": 1,
                   "role": "executor", "platform": "linux", "contract_ref": contract}
        handoff = ProfileHandoff(request_id, run_id, "planner-p", "executor-p", "planner-session", "executor-session",
                                 contract, (ref("input"),), 3, executor_context=context)
        self.assertEqual(handoff.to_mapping()["executor_context"]["role"], "executor")
        validate_handoff(handoff, request_id=request_id, budget_generation=3,
                         planner_profile_id="planner-p", executor_profile_id="executor-p")
        with self.assertRaisesRegex(AdapterFacadeError, "E_HANDOFF_SESSION"):
            ProfileHandoff("req", "run", "planner-p", "executor-p", "same", "same",
                           ref("contract"), (ref("input"),), 3)
        bad_context = dict(context, request_id="other")
        with self.assertRaisesRegex(AdapterFacadeError, "E_HANDOFF_CONTEXT"):
            ProfileHandoff(request_id, run_id, "planner-p", "executor-p", "planner-session", "executor-session",
                           contract, (ref("input"),), 3, executor_context=bad_context)
        with self.assertRaisesRegex(AdapterFacadeError, "E_HANDOFF_GENERATION"):
            validate_handoff(handoff, request_id=request_id, budget_generation=4,
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

    def test_start_gate_rechecks_run_context_handoff_budget_and_invocation(self):
        adapter = ClaudeCodeAdapter()
        capability = adapter.probe(timeout=1).capability
        platform = capability.platforms[0]
        request_id = "req-11111111111141118111111111111111"
        run_id = "run-22222222222242228222222222222222"
        contract = ref("contract")
        profile = adapter.validate_profile(capability, role="executor", platform=platform,
                                           model_id="offline-test-model", profile_id="executor-gate",
                                           required_capabilities=("terminal_event",), require_observed=False)
        profile = replace(profile, session_id="executor-session")
        context = {"schema_version": 1, "record_type": "run-context", "request_id": request_id,
                   "task_id": "task-11", "plan_version": 1, "run_id": run_id, "attempt": 1,
                   "role": "executor", "platform": platform, "contract_ref": contract}
        handoff = ProfileHandoff(request_id, run_id, "planner-gate", profile.profile_id,
                                 "planner-session", "executor-session", contract, (ref("input"),), 1,
                                 executor_context=context)
        ledger = PlanningBudgetLedger.calls(request_id, "task-11", 1)
        invocation = adapter.build_invocation(profile, request_id=request_id, run_id=run_id, cwd=".",
                                              environment={}, prompt=b"execute",
                                              resource_allowlist=(ref("input"),))
        allowed = evaluate_start_gate(run_context=context, profile=profile, handoff=handoff,
                                      ledger=ledger, invocation=invocation)
        self.assertTrue(allowed.allowed, allowed.reasons)
        self.assertEqual(allowed.context_report["record_type"], "run-context")
        router = ProfileRouter(HeterogeneousAdapterFacade([adapter]))
        router.register(profile)
        self.assertTrue(router.start_gate(profile.profile_id, run_context=context, handoff=handoff,
                                          ledger=ledger, invocation=invocation).allowed)

        blocked = evaluate_start_gate(run_context=dict(context, run_id="run-33333333333343338333333333333333"),
                                      profile=profile, handoff=handoff, ledger=ledger,
                                      invocation=invocation)
        self.assertFalse(blocked.allowed)
        self.assertIn("RUN_MISMATCH", blocked.reasons)
        stopped = evaluate_start_gate(run_context=context, profile=profile, handoff=handoff,
                                      ledger=ledger.stop("USER_STOP"), invocation=invocation)
        self.assertFalse(stopped.allowed)
        self.assertIn("BUDGET_USER_STOP", stopped.reasons)
        wrong_session = replace(invocation, session_id="other-session")
        session_block = evaluate_start_gate(run_context=context, profile=profile, handoff=handoff,
                                             ledger=ledger, invocation=wrong_session)
        self.assertFalse(session_block.allowed)
        self.assertIn("INVOCATION_SESSION_MISMATCH", session_block.reasons)


if __name__ == "__main__":
    unittest.main()
