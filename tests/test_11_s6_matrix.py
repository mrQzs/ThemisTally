"""S6 offline evidence for release gates and heterogeneous profile pairs.

These tests exercise only deterministic records.  They do not start a model
request or a process, so a green result remains LOCAL_REFERENCE evidence.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace
from pathlib import Path

from scripts.codekit.adapters.capability import (
    AdapterCapability,
    CapabilityError,
    CapabilityEvidence,
    PreflightResult,
    preflight_profile,
)
from scripts.codekit.adapters.heterogeneous import (
    HeterogeneousAdapterFacade,
    ProfileHandoff,
    ProfileRouter,
    evaluate_independent_release_gate,
    validate_handoff,
)
from scripts.codekit.adapters.second_cli import ClaudeCodeAdapter


ROOT = Path(__file__).resolve().parents[1]


def _ref(name: str) -> dict[str, str]:
    payload = (name + "\n").encode("utf-8")
    return {
        "kind": "s6-fixture",
        "id": name,
        "path": "fixtures/11/" + name + ".json",
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


class AlternateAdapter(ClaudeCodeAdapter):
    adapter_id = "alternate-cli"


def _observed_capability(adapter_id: str) -> AdapterCapability:
    names = ("streaming_events", "terminal_event", "model_identity")
    evidence = tuple(
        CapabilityEvidence(name, "observed", source_ref=_ref(adapter_id + "-" + name), note="offline fixture")
        for name in names
    )
    return AdapterCapability(
        adapter_id,
        "structured-cli-v1",
        "fixture-1.0.0",
        ("linux",),
        ("planner", "executor"),
        names,
        "required",
        "argv",
        evidence,
        False,
        ("native",),
    )


class S6ReleaseAndMatrixTests(unittest.TestCase):
    def test_release_gate_allows_only_complete_observed_evidence(self) -> None:
        capability = _observed_capability("claude-code")
        planner_preflight = preflight_profile(
            capability,
            role="planner",
            platform="linux",
            required_capabilities=("streaming_events", "terminal_event"),
            requested_model="fixture-planner",
            reported_model="fixture-planner",
            authentication_status="READY",
            version_supported=True,
        )
        self.assertEqual(planner_preflight.status, "READY", planner_preflight.reasons)
        refs = {name: _ref("release-" + name) for name in (
            "real_model_chain", "real_platform_lifecycle", "independent_review", "external_connectors"
        )}
        gate = evaluate_independent_release_gate(
            preflights=(planner_preflight,),
            real_model_chain=True,
            real_platform_lifecycle=True,
            independent_review=True,
            external_connectors=True,
            evidence_refs=refs,
        )
        self.assertTrue(gate.allowed, gate.reasons)
        mapping = gate.to_mapping()
        schema = json.loads((ROOT / "schemas" / "second-cli-release-gate-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(mapping), set(schema["required"]))
        self.assertEqual(mapping["record_type"], "second-cli-release-gate")

    def test_forged_ready_preflight_is_rejected_before_release_or_dispatch(self) -> None:
        capability = _observed_capability("claude-code")
        ready = preflight_profile(
            capability,
            role="planner",
            platform="linux",
            required_capabilities=("terminal_event",),
            requested_model="fixture-planner",
            reported_model="fixture-planner",
            authentication_status="READY",
            version_supported=True,
        )
        with self.assertRaisesRegex(CapabilityError, "READY requires a supported profile binding"):
            PreflightResult(
                "READY",
                replace(ready.binding, supported=False),
                ready.requested_model,
                ready.reported_model,
                ready.authentication_status,
                ready.version_supported,
                (),
            )

    def test_release_gate_keeps_missing_real_evidence_blocked(self) -> None:
        gate = evaluate_independent_release_gate(
            preflights=(),
            real_model_chain=False,
            real_platform_lifecycle=False,
            independent_review=False,
            external_connectors=False,
            evidence_refs={},
        )
        self.assertFalse(gate.allowed)
        self.assertIn("PREFLIGHTS_MISSING", gate.reasons)
        self.assertIn("REAL_MODEL_CHAIN_MISSING", gate.reasons)
        self.assertIn("REAL_PLATFORM_LIFECYCLE_MISSING", gate.reasons)
        self.assertIn("INDEPENDENT_REVIEW_MISSING", gate.reasons)
        self.assertIn("EXTERNAL_CONNECTORS_MISSING", gate.reasons)

    def test_release_gate_rejects_non_text_evidence_keys(self) -> None:
        gate = evaluate_independent_release_gate(
            preflights=(),
            real_model_chain=True,
            real_platform_lifecycle=False,
            independent_review=False,
            external_connectors=False,
            evidence_refs={1: _ref("bad-key")},
        )
        self.assertFalse(gate.allowed)
        self.assertIn("EVIDENCE_REF_KEY_INVALID", gate.reasons)

    def test_both_heterogeneous_directions_bind_separate_profiles_and_sessions(self) -> None:
        planner_adapter = ClaudeCodeAdapter()
        executor_adapter = AlternateAdapter()
        planner_capability = _observed_capability(planner_adapter.adapter_id)
        executor_capability = _observed_capability(executor_adapter.adapter_id)
        planner = planner_adapter.validate_profile(
            planner_capability,
            role="planner",
            platform="linux",
            model_id="fixture-planner",
            profile_id="planner-a",
            required_capabilities=("streaming_events", "terminal_event", "model_identity"),
        )
        executor = executor_adapter.validate_profile(
            executor_capability,
            role="executor",
            platform="linux",
            model_id="fixture-executor",
            profile_id="executor-b",
            required_capabilities=("streaming_events", "terminal_event", "model_identity"),
        )
        router = ProfileRouter(HeterogeneousAdapterFacade((planner_adapter, executor_adapter)))
        router.register(planner, capability=planner_capability)
        router.register(executor, capability=executor_capability)
        planner_invocation = router.build_invocation(
            planner.profile_id,
            request_id="request-forward",
            run_id="run-forward",
            cwd=".",
            environment={},
            prompt=b"plan",
        )
        executor_invocation = router.build_invocation(
            executor.profile_id,
            request_id="request-forward",
            run_id="run-forward",
            cwd=".",
            environment={},
            prompt=b"execute",
        )
        self.assertEqual(planner_invocation.adapter.adapter_id, planner.adapter_id)
        self.assertEqual(executor_invocation.adapter.adapter_id, executor.adapter_id)

        contract = _ref("contract")
        inputs = (_ref("input"),)
        forward = ProfileHandoff("request-forward", "run-forward", planner.profile_id, executor.profile_id,
                                 "session-planner-a", "session-executor-b", contract, inputs, 1)
        validate_handoff(forward, request_id="request-forward", budget_generation=1,
                         planner_profile_id=planner.profile_id, executor_profile_id=executor.profile_id)
        reverse = ProfileHandoff("request-reverse", "run-reverse", executor.profile_id, planner.profile_id,
                                 "session-executor-b", "session-planner-a", contract, inputs, 1)
        validate_handoff(reverse, request_id="request-reverse", budget_generation=1,
                         planner_profile_id=executor.profile_id, executor_profile_id=planner.profile_id)
        self.assertNotEqual(forward.planner_session_id, forward.executor_session_id)
        self.assertNotEqual(reverse.planner_session_id, reverse.executor_session_id)
        self.assertNotEqual(planner.adapter_id, executor.adapter_id)


if __name__ == "__main__":
    unittest.main()
