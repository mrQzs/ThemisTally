import hashlib
import unittest
from dataclasses import replace

from scripts.codekit.authorization import ApprovalLedger
from scripts.codekit.adapters.heterogeneous import (
    AdapterFacadeError,
    ApprovalBinding,
    CancellationObservation,
    HeterogeneousAdapterFacade,
    evaluate_independent_release_gate,
    RecoveryLedger,
    select_fallback,
    ProfileHandoff,
    ProfileRouter,
    check_role_gate,
    evaluate_start_gate,
    validate_handoff,
)
from scripts.codekit.adapters.second_cli import ClaudeCodeAdapter, SecondCliError
from scripts.codekit.adapters.capability import CapabilityEvidence, preflight_profile
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
        drifted = replace(profile, capability_digest="0" * 64, profile_id="router-drift")
        with self.assertRaisesRegex(AdapterFacadeError, "E_PROFILE_DRIFT"):
            ProfileRouter(HeterogeneousAdapterFacade([adapter])).register(drifted, capability=capability)

    def test_local_probe_does_not_unlock_production_profile(self):
        adapter = ClaudeCodeAdapter()
        capability = adapter.probe(timeout=1).capability
        with self.assertRaisesRegex(SecondCliError, "E_CLI_PROFILE"):
            adapter.validate_profile(capability, role="planner", platform=capability.platforms[0],
                                     model_id="offline-test-model", profile_id="requires-real-evidence",
                                     required_capabilities=("terminal_event",), require_observed=True)

    def test_release_gate_keeps_real_chain_blocked_until_all_evidence_exists(self):
        adapter = ClaudeCodeAdapter()
        capability = adapter.probe(timeout=1).capability
        preflight = preflight_profile(capability, role="planner", platform=capability.platforms[0],
                                      required_capabilities=("terminal_event",), requested_model="m",
                                      authentication_status="NOT_INSPECTED", version_supported=True)
        gate = evaluate_independent_release_gate(preflights=(preflight,), real_model_chain=False,
                                                 real_platform_lifecycle=False, independent_review=True,
                                                 external_connectors=False)
        self.assertFalse(gate.allowed)
        self.assertIn("PREFLIGHT_NOT_READY", gate.reasons)
        self.assertIn("REAL_MODEL_CHAIN_MISSING", gate.reasons)
        self.assertEqual(gate.to_mapping()["record_type"], "second-cli-release-gate")
        missing_evidence = evaluate_independent_release_gate(preflights=(), real_model_chain=True,
                                                             real_platform_lifecycle=True,
                                                             independent_review=True, external_connectors=True)
        self.assertFalse(missing_evidence.allowed)
        self.assertIn("EVIDENCE_REF_MISSING:real_model_chain", missing_evidence.reasons)

    def test_fallback_requires_explicit_authorization_and_review(self):
        adapter = ClaudeCodeAdapter()
        capability = adapter.probe(timeout=1).capability
        capability = replace(
            capability,
            evidence=tuple(
                CapabilityEvidence(item.capability, "observed", source_ref=ref("observed-" + item.capability),
                                   note="offline observed fixture")
                for item in capability.evidence
            ),
        )
        primary = preflight_profile(capability, role="planner", platform=capability.platforms[0],
                                    required_capabilities=("terminal_event",), requested_model="m",
                                    authentication_status="READY", version_supported=False,
                                    reported_model="m")
        fallback = preflight_profile(capability, role="planner", platform=capability.platforms[0],
                                     required_capabilities=("terminal_event",), requested_model="m2",
                                     authentication_status="READY", version_supported=True,
                                     reported_model="m2")
        denied = select_fallback(primary_profile_id="primary", fallback_profile_id="fallback",
                                 primary=primary, fallback=fallback)
        self.assertFalse(denied.allowed)
        self.assertIn("FALLBACK_AUTHORIZATION_REQUIRED", denied.reasons)
        accepted = select_fallback(primary_profile_id="primary", fallback_profile_id="fallback",
                                   primary=primary, fallback=fallback,
                                   authorized=True, re_reviewed=True)
        self.assertTrue(accepted.allowed)
        self.assertEqual(accepted.to_mapping()["requires_review"], True)

    def test_fallback_rejects_malformed_controller_input(self):
        adapter = ClaudeCodeAdapter()
        capability = adapter.probe(timeout=1).capability
        fallback = preflight_profile(capability, role="planner", platform=capability.platforms[0],
                                     required_capabilities=("terminal_event",), requested_model="m",
                                     authentication_status="READY", version_supported=True,
                                     reported_model="m")
        denied = select_fallback(primary_profile_id="primary", fallback_profile_id="fallback",
                                 primary={"status": "VERSION_INCOMPATIBLE"}, fallback=fallback)  # type: ignore[arg-type]
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.reasons, ("FALLBACK_INPUT_INVALID",))
        with self.assertRaisesRegex(AdapterFacadeError, "E_FALLBACK_SCHEMA"):
            select_fallback(primary_profile_id="", fallback_profile_id="fallback",
                            primary=fallback, fallback=fallback)

    def test_recovery_ledger_replays_same_observation_and_rejects_conflict(self):
        ledger = RecoveryLedger()
        with self.assertRaisesRegex(AdapterFacadeError, "E_RECOVERY_SCHEMA"):
            ledger.record({})  # type: ignore[arg-type]
        observation = CancellationObservation.classify(request_id="req", run_id="run", generation=1,
                                                        cancel_requested=True, exit_code=None,
                                                        response_lost=True, process_observed=None)
        self.assertEqual(ledger.record(observation), "APPLIED")
        self.assertEqual(ledger.record(observation), "REPLAY")
        conflict = CancellationObservation.classify(request_id="req", run_id="run", generation=1,
                                                     cancel_requested=True, exit_code=130,
                                                     process_observed=False)
        with self.assertRaisesRegex(AdapterFacadeError, "E_RECOVERY_CONFLICT"):
            ledger.record(conflict)

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
        approval_ledger = ApprovalLedger()
        approval_record = {
            "record_type": "approval-record",
            "schema_version": 1,
            "approval_id": "approval-11",
            "request_id": request_id,
            "subject_ref": ref("subject"),
            "input_refs": [ref("input")],
            "reviewed_actions": ["run"],
            "decision": "APPROVED",
            "recorded_at": "2026-01-01T00:00:00Z",
            "reviewer": {"mode": "current_session"},
        }
        approval_head = approval_ledger.put(scope="run-approval", operation_id="approval-op",
                                            expected_generation=0, record=approval_record)
        input_lock = approval_ledger.lock(scope="run-approval", receipt_id="lock-11",
                                          operation_id="lock-op", bindings=[ref("input")])
        approval_binding = ApprovalBinding(
            approval_ledger,
            "run-approval",
            approval_head.generation,
            approval_head.record_sha256,
            "run",
            (ref("input"),),
            input_lock,
        )
        invocation = adapter.build_invocation(profile, request_id=request_id, run_id=run_id, cwd=".",
                                              environment={}, prompt=b"execute",
                                              resource_allowlist=(ref("input"),))
        allowed = evaluate_start_gate(run_context=context, profile=profile, handoff=handoff,
                                      ledger=ledger, invocation=invocation,
                                      approval_binding=approval_binding)
        self.assertTrue(allowed.allowed, allowed.reasons)
        self.assertEqual(allowed.context_report["record_type"], "run-context")
        router = ProfileRouter(HeterogeneousAdapterFacade([adapter]))
        router.register(profile)
        self.assertTrue(router.start_gate(profile.profile_id, run_context=context, handoff=handoff,
                                          ledger=ledger, invocation=invocation,
                                          approval_binding=approval_binding).allowed)

        blocked = evaluate_start_gate(run_context=dict(context, run_id="run-33333333333343338333333333333333"),
                                      profile=profile, handoff=handoff, ledger=ledger,
                                      invocation=invocation, approval_binding=approval_binding)
        self.assertFalse(blocked.allowed)
        self.assertIn("RUN_MISMATCH", blocked.reasons)
        stopped = evaluate_start_gate(run_context=context, profile=profile, handoff=handoff,
                                      ledger=ledger.stop("USER_STOP"), invocation=invocation,
                                      approval_binding=approval_binding)
        self.assertFalse(stopped.allowed)
        self.assertIn("BUDGET_USER_STOP", stopped.reasons)
        wrong_session = replace(invocation, session_id="other-session")
        session_block = evaluate_start_gate(run_context=context, profile=profile, handoff=handoff,
                                             ledger=ledger, invocation=wrong_session,
                                             approval_binding=approval_binding)
        self.assertFalse(session_block.allowed)
        self.assertIn("INVOCATION_SESSION_MISMATCH", session_block.reasons)

        unbound = evaluate_start_gate(run_context=context, profile=profile, handoff=handoff,
                                      ledger=ledger, invocation=invocation)
        self.assertFalse(unbound.allowed)
        self.assertIn("APPROVAL_UNBOUND", unbound.reasons)

        approval_ledger.revoke(scope="run-approval", operation_id="revoke-op",
                               expected_generation=approval_head.generation, reason="stopped")
        stale = evaluate_start_gate(run_context=context, profile=profile, handoff=handoff,
                                    ledger=ledger, invocation=invocation,
                                    approval_binding=approval_binding)
        self.assertFalse(stale.allowed)
        self.assertIn("E_APPROVAL_CURRENTNESS", stale.reasons)


if __name__ == "__main__":
    unittest.main()
