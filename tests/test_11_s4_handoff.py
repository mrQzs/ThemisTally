"""Offline S4 planner handoff and 09 service binding tests."""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from scripts.codekit.planner import PlanningService
from scripts.codekit.planner_adapter import (
    AdapterError,
    ExecutorHandoff,
    InvocationEnvelope,
    OfflinePlannerAdapter,
    PlanningHandoff,
    bind_execution_result,
    bind_planning_result,
    ingest_planning_handoff,
)


def ref(name: str) -> dict[str, str]:
    return {"kind": "fixture", "id": name, "sha256": "a" * 64, "path": f"fixtures/{name}.json"}


def planner_request() -> dict:
    refs = {name: ref(name) for name in (
        "requirements", "context", "baseline", "config", "environment", "catalog",
        "output", "budget", "repair", "stop", "authorization")}
    return {
        "record_type": "planner-request", "schema_version": 1,
        "request_id": "req-1", "run_id": "run-1", "operation_id": "op-1",
        "mode": "graph", "target_task_id": None,
        "requirements_ref": refs["requirements"], "context_manifest_ref": refs["context"],
        "graph_ref": None, "baseline_ref": refs["baseline"],
        "planner_config_ref": refs["config"], "environment_ref": refs["environment"],
        "catalog_ref": refs["catalog"], "rules_refs": [], "decision_refs": [],
        "output_contract_ref": refs["output"], "planning_budget_ref": refs["budget"],
        "authorization_refs": [refs["authorization"]],
        "repair_policy_ref": refs["repair"], "stop_policy_ref": refs["stop"],
    }


def context_manifest(request: dict) -> dict:
    resources = [request[name] for name in (
        "requirements_ref", "baseline_ref", "planner_config_ref", "environment_ref",
        "catalog_ref", "output_contract_ref", "planning_budget_ref", "repair_policy_ref",
        "stop_policy_ref", "authorization_refs")]
    # authorization_refs is an array in the request, while the manifest stores
    # individual ResourceRefs.
    if resources and isinstance(resources[-1], list):
        resources[-1:] = resources[-1]
    return {"record_type": "context-manifest", "schema_version": 1,
            "request_id": request["request_id"], "resources": resources}


def planning_bundle() -> dict:
    source = b"hello planner"
    source_ref = {"kind": "fixture", "id": "source", "sha256": hashlib.sha256(source).hexdigest(),
                  "path": "fixtures/source.txt"}
    return {
        "record_type": "planning-bundle", "schema_version": 1, "request_id": "req-1",
        "planner_request_ref": ref("planner-request"), "mode": "graph", "graph_ref": None,
        "target_task_id": None, "investigation_baseline_ref": ref("baseline"),
        "requirement_refs": [ref("requirements")],
        "facts": [{"id": "fact1", "text": "A source fact", "evidence_class": "source_observation",
                   "evidence": [{"ref": source_ref, "start_byte": 0, "end_byte": 5,
                                  "quote_sha256": hashlib.sha256(source[:5]).hexdigest()}]}],
        "assumptions": [], "questions": [], "risks": [],
        "task_graph": {"tasks": [{"id": "task1", "title": "Plan", "depends_on": [],
                                    "requirement_ids": ["requirements"], "scope_paths": ["scripts/codekit"],
                                    "acceptance_intent": ["validated"],
                                    "stages": [{"id": "investigate", "kind": "investigate", "depends_on": [], "plugin_step_ref": None},
                                                {"id": "freeze", "kind": "freeze", "depends_on": ["investigate"], "plugin_step_ref": None},
                                                {"id": "check", "kind": "check", "depends_on": ["freeze"], "plugin_step_ref": None},
                                                {"id": "verdict", "kind": "verdict", "depends_on": ["check"], "plugin_step_ref": None}],
                                    "estimated_calls": 0}]},
        "contract_drafts": [{"task_id": "task1", "completeness": "template",
                              "baseline": {"state": "unbound", "reason": "awaiting core baseline"},
                              "scope_paths": ["scripts/codekit"], "checks_ref": None,
                              "executor_profile_ref": None, "environment_ref": None, "plugin_lock_ref": None,
                              "narrative": {"goal": "Plan", "non_goals": [], "behavior": ["validate"],
                                             "acceptance": ["accepted"]}}],
        "budget_proposal": {"max_calls": 1, "max_seconds": 10, "max_repair_calls": 0},
        "stop_conditions": ["budget_exhausted"],
    }


def canonical(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


class S4PlannerHandoffTests(unittest.TestCase):
    def test_result_is_bound_to_request_context_and_exact_bundle_bytes(self):
        request = planner_request()
        context = context_manifest(request)
        bundle = planning_bundle()
        adapter = OfflinePlannerAdapter()
        envelope = InvocationEnvelope("req-1", "op-1", "planner", tuple(context["resources"]))
        events = adapter.invoke(request, bundle, envelope=envelope)
        bundle_sha = hashlib.sha256(canonical(bundle)).hexdigest()
        handoff, normalized = adapter.bind(
            request, context, events, envelope=envelope,
            planner_profile_id="planner-profile", planner_session_id="planner-session",
            planner_request_ref=ref("planner-request-record"),
            bundle_ref={"kind": "planning-bundle", "id": "bundle-1", "path": "bundles/bundle-1.json", "sha256": bundle_sha},
            budget_generation=2,
        )
        self.assertIsInstance(handoff, PlanningHandoff)
        self.assertEqual(handoff.bundle_sha256, bundle_sha)
        self.assertEqual(normalized["request_id"], "req-1")
        self.assertNotIn("approval_id", handoff.to_mapping())
        self.assertNotIn("publication_id", handoff.to_mapping())
        schema = json.loads(Path("schemas/second-cli-planning-handoff-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(handoff.to_mapping()), set(schema["required"]))
        self.assertEqual(set(handoff.to_mapping()), {
            "record_type", "schema_version", "request_id", "run_id", "operation_id",
            "planner_profile_id", "planner_session_id", "planner_request_ref",
            "context_manifest_ref", "bundle_ref", "bundle_sha256", "budget_generation",
            "state", "execution_mode",
        })

    def test_handoff_rejects_allowlist_drift_and_bundle_digest_drift(self):
        request = planner_request(); context = context_manifest(request); bundle = planning_bundle()
        adapter = OfflinePlannerAdapter()
        envelope = InvocationEnvelope("req-1", "op-1", "planner", tuple(context["resources"]))
        events = adapter.invoke(request, bundle, envelope=envelope)
        digest = hashlib.sha256(canonical(bundle)).hexdigest()
        with self.assertRaisesRegex(AdapterError, "E_HANDOFF_SCOPE"):
            bind_planning_result(request, context, events,
                                 envelope=InvocationEnvelope("req-1", "op-1", "planner", (ref("context"),)),
                                 planner_profile_id="p", planner_session_id="s",
                                 planner_request_ref=ref("planner-request-record"),
                                 bundle_ref={"kind": "planning-bundle", "id": "b", "path": "bundles/b.json", "sha256": digest})
        with self.assertRaisesRegex(AdapterError, "E_HANDOFF_RESULT"):
            adapter.bind(request, context, events, envelope=envelope,
                         planner_profile_id="p", planner_session_id="s",
                         planner_request_ref=ref("planner-request-record"),
                         bundle_ref={"kind": "planning-bundle", "id": "b", "path": "bundles/b.json", "sha256": "b" * 64})

    def test_refined_contract_enters_09_service_without_publication(self):
        request = planner_request(); context = context_manifest(request); bundle = planning_bundle()
        adapter = OfflinePlannerAdapter()
        envelope = InvocationEnvelope("req-1", "op-1", "planner", tuple(context["resources"]))
        events = adapter.invoke(request, bundle, envelope=envelope)
        digest = hashlib.sha256(canonical(bundle)).hexdigest()
        handoff, normalized = adapter.bind(
            request, context, events, envelope=envelope, planner_profile_id="p", planner_session_id="s",
            planner_request_ref=ref("planner-request-record"),
            bundle_ref={"kind": "planning-bundle", "id": "b", "path": "bundles/b.json", "sha256": digest})
        contract_ir = {
            "task_id": "task1", "plan_version": 1, "title": "Offline contract", "repository": "Code-Kit",
            "base_sha": "a" * 40, "risk_level": "low",
            "authorization": {"executor": ["local_edit"], "integration": []},
            "executor": {"provider": "offline", "model": "stub", "thinking": "high", "tools": [], "context_files": "project"},
            "scope": {"allowed_modified_files": [], "allowed_new_files": [], "allowed_deleted_files": [], "forbidden_paths": ["AGENTS.md"], "dependency_changes": "forbidden"},
            "setup": [], "checks": [], "definition_of_done": [{"id": "D01", "text": "bound", "evidence": ["handoff"]}],
            "budget": {"max_attempts_total": 1, "max_wall_seconds_per_attempt": 30, "max_wall_seconds_total": 30, "cost_budget": None},
        }
        revision = ingest_planning_handoff(PlanningService(), handoff, normalized,
                                           contract_ir=contract_ir, draft_id="draft-1")
        self.assertEqual(revision.ir["task_id"], "task1")
        self.assertEqual(revision.state, "DRAFT")

    def test_executor_handoff_keeps_report_events_and_checks_together(self):
        result = {"record_type": "analysis-report", "status": "ok", "findings": []}
        report_sha = hashlib.sha256(canonical(result)).hexdigest()
        handoff = bind_execution_result(
            request_id="req-1", run_id="run-1", operation_id="op-1",
            executor_profile_id="executor-profile", executor_session_id="executor-session",
            candidate_ref=ref("candidate"),
            report_ref={"kind": "execution-report", "id": "report-1", "path": "reports/report.json", "sha256": report_sha},
            result=result,
            event_refs=(ref("event-1"),), check_refs=(ref("check-1"),),
            invocation_sha256="b" * 64, status="SETTLED", settled=True, budget_generation=3,
        )
        self.assertIsInstance(handoff, ExecutorHandoff)
        self.assertEqual(handoff.to_mapping()["result_sha256"], report_sha)
        schema = json.loads(Path("schemas/second-cli-executor-handoff-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(handoff.to_mapping()), set(schema["required"]))
        self.assertEqual(set(handoff.to_mapping()), {
            "record_type", "schema_version", "request_id", "run_id", "operation_id",
            "executor_profile_id", "executor_session_id", "candidate_ref", "report_ref",
            "invocation_sha256", "result_sha256", "event_refs", "check_refs", "status",
            "settled", "budget_generation", "state", "execution_mode",
        })
        with self.assertRaisesRegex(AdapterError, "E_EXECUTOR_RESULT"):
            bind_execution_result(
                request_id="req-1", run_id="run-1", operation_id="op-1",
                executor_profile_id="executor-profile", executor_session_id="executor-session",
                candidate_ref=ref("candidate"),
                report_ref={"kind": "execution-report", "id": "report-1", "path": "reports/report.json", "sha256": "c" * 64},
                result=result, event_refs=(ref("event-1"),), check_refs=(),
                invocation_sha256="b" * 64, status="UNKNOWN", settled=False,
            )


if __name__ == "__main__":
    unittest.main()
