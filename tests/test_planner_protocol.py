import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.planner_protocol import (
    strict_planner_json_loads,
    validate_bundle,
    validate_context_manifest,
    validate_planner_request,
    validate_planning_binding,
    validate_planning_bundle,
    validate_source_anchor,
)
from codekit.protocols import ProtocolError


def ref(name="r1"):
    return {"kind": "fixture", "id": name, "sha256": "a" * 64, "path": f"docs/{name}.md"}


def bundle():
    req = ref("req1")
    source = b"hello planner"
    source_ref = {"kind": "fixture", "id": "source", "sha256": hashlib.sha256(source).hexdigest(), "path": "docs/source.md"}
    anchor = {"ref": source_ref, "start_byte": 0, "end_byte": 5, "quote_sha256": hashlib.sha256(source[:5]).hexdigest()}
    return {
        "record_type": "planning-bundle", "schema_version": 1, "request_id": "req-1",
        "planner_request_ref": ref("planner-request"), "mode": "graph", "graph_ref": None,
        "target_task_id": None, "investigation_baseline_ref": ref("baseline"), "requirement_refs": [req],
        "facts": [{"id": "fact1", "text": "A source fact", "evidence_class": "source_observation", "evidence": [anchor]}],
        "assumptions": [], "questions": [], "risks": [],
        "task_graph": {"tasks": [{"id": "task1", "title": "Plan", "depends_on": [], "requirement_ids": ["req1"], "scope_paths": ["scripts/codekit"], "acceptance_intent": ["validated"], "stages": [{"id": "investigate", "kind": "investigate", "depends_on": [], "plugin_step_ref": None}, {"id": "freeze", "kind": "freeze", "depends_on": ["investigate"], "plugin_step_ref": None}, {"id": "check", "kind": "check", "depends_on": ["freeze"], "plugin_step_ref": None}, {"id": "verdict", "kind": "verdict", "depends_on": ["check"], "plugin_step_ref": None}], "estimated_calls": 0}]},
        "contract_drafts": [{"task_id": "task1", "completeness": "template", "baseline": {"state": "unbound", "reason": "awaiting core baseline"}, "scope_paths": ["scripts/codekit"], "checks_ref": None, "executor_profile_ref": None, "environment_ref": None, "plugin_lock_ref": None, "narrative": {"goal": "Plan", "non_goals": [], "behavior": ["validate"], "acceptance": ["accepted"]}}],
        "budget_proposal": {"max_calls": 1, "max_seconds": 10, "max_repair_calls": 0},
        "stop_conditions": ["budget_exhausted"],
    }


class PlannerProtocolTests(unittest.TestCase):
    def test_strict_json_rejects_duplicate_nonfinite_and_trailing(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1} {"b":2}', b'{"a":"\xed\xa0\x80"}'):
            with self.subTest(raw=raw):
                with self.assertRaises(ProtocolError):
                    strict_planner_json_loads(raw)

    def test_valid_bundle_and_report(self):
        value = validate_planning_bundle(bundle())
        self.assertEqual(value["record_type"], "planning-bundle")
        self.assertTrue(validate_bundle(value)["valid"])

    def test_bundle_rejects_cycle_and_uncovered_requirement(self):
        bad = bundle(); bad["task_graph"]["tasks"][0]["stages"][0]["depends_on"] = ["verdict"]
        with self.assertRaises(ProtocolError): validate_planning_bundle(bad)
        bad = bundle(); bad["task_graph"]["tasks"][0]["requirement_ids"] = ["missing"]
        with self.assertRaises(ProtocolError): validate_planning_bundle(bad)

    def test_bundle_rejects_schema_duplicate_items(self):
        mutations = []
        bad = bundle(); bad["task_graph"]["tasks"][0]["depends_on"] = ["task1", "task1"]; mutations.append(bad)
        bad = bundle(); bad["task_graph"]["tasks"][0]["requirement_ids"] = ["req1", "req1"]; mutations.append(bad)
        bad = bundle(); bad["task_graph"]["tasks"][0]["scope_paths"] = ["scripts/codekit", "scripts/codekit"]; mutations.append(bad)
        bad = bundle(); bad["contract_drafts"][0]["scope_paths"] = ["scripts/codekit", "scripts/codekit"]; mutations.append(bad)
        bad = bundle(); bad["stop_conditions"] = ["budget_exhausted", "budget_exhausted"]; mutations.append(bad)
        for value in mutations:
            with self.subTest(value=value):
                with self.assertRaises(ProtocolError):
                    validate_planning_bundle(value)

    def test_unbound_future_draft_cannot_contain_sha(self):
        bad = bundle(); bad["contract_drafts"][0]["baseline"]["reason"] = "sha " + "a" * 64
        with self.assertRaises(ProtocolError): validate_planning_bundle(bad)
        bad = bundle(); bad["contract_drafts"][0]["completeness"] = "complete"
        with self.assertRaises(ProtocolError): validate_planning_bundle(bad)

    def test_anchor_checks_half_open_bytes_when_available(self):
        raw = b"abcdef"; r = {"kind": "fixture", "id": "raw", "sha256": hashlib.sha256(raw).hexdigest(), "path": "docs/raw.md"}
        a = {"ref": r, "start_byte": 1, "end_byte": 3, "quote_sha256": hashlib.sha256(raw[1:3]).hexdigest()}
        self.assertEqual(validate_source_anchor(a, source_bytes=raw)["end_byte"], 3)
        bad = copy.deepcopy(a); bad["end_byte"] = 1
        with self.assertRaises(ProtocolError): validate_source_anchor(bad)

    def test_context_and_request_route(self):
        manifest = {"record_type": "context-manifest", "schema_version": 1, "request_id": "req-1", "resources": [ref()]}
        self.assertEqual(validate_context_manifest(manifest)["request_id"], "req-1")
        base = ref("base")
        request = {"record_type": "planner-request", "schema_version": 1, "request_id": "req-1", "run_id": "run-1", "operation_id": "op-1", "mode": "graph", "target_task_id": None, "requirements_ref": ref("requirements"), "context_manifest_ref": ref("context"), "graph_ref": None, "baseline_ref": base, "planner_config_ref": ref("config"), "environment_ref": ref("env"), "catalog_ref": ref("catalog"), "rules_refs": [], "decision_refs": [], "output_contract_ref": ref("output"), "planning_budget_ref": ref("budget"), "authorization_refs": [], "repair_policy_ref": ref("repair"), "stop_policy_ref": ref("stop")}
        self.assertEqual(validate_planner_request(request)["mode"], "graph")
        manifest = {"record_type": "context-manifest", "schema_version": 1, "request_id": "req-1",
                    "resources": [request[name] for name in
                                   ("requirements_ref", "baseline_ref", "planner_config_ref", "environment_ref",
                                    "catalog_ref", "output_contract_ref", "planning_budget_ref",
                                    "repair_policy_ref", "stop_policy_ref")]}
        self.assertEqual(validate_planning_binding(request, manifest)["request"]["request_id"], "req-1")
        bad = dict(manifest); bad["request_id"] = "other-request"
        with self.assertRaises(ProtocolError):
            validate_planning_binding(request, bad)


if __name__ == "__main__":
    unittest.main()
