#!/usr/bin/env python3
"""07-T1A static workflow-definition contract tests."""
from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit import protocols  # noqa: E402
from codekit import workflow  # noqa: E402


FIXTURE = ROOT / "tests" / "fixtures" / "workflow" / "valid.json"
SCHEMA = ROOT / "schemas" / "workflow-definition-v1.schema.json"


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def assertCode(self, code: str, value, *, field: str | None = None) -> None:
        with self.assertRaises(protocols.ProtocolError) as caught:
            workflow.validate_workflow(value)
        self.assertEqual(caught.exception.code, code)
        if field is not None:
            self.assertEqual(caught.exception.field, field)

    def test_valid_fixture_is_accepted_and_order_comes_from_edges(self) -> None:
        result = workflow.validate_workflow(self.doc)
        self.assertEqual(result.workflow_id, "demo-workflow")
        self.assertEqual(result.task_order, ("alpha", "beta"))
        self.assertEqual(workflow.topological_order(result), ("alpha", "beta"))

    def test_task_array_order_does_not_define_topology(self) -> None:
        reversed_doc = copy.deepcopy(self.doc)
        reversed_doc["nodes"] = list(reversed(reversed_doc["nodes"]))
        result = workflow.validate_workflow(reversed_doc)
        self.assertEqual(result.task_order, ("alpha", "beta"))

    def test_result_is_detached_and_immutable(self) -> None:
        result = workflow.validate_workflow(self.doc)
        self.doc["workflow_id"] = "changed"
        self.doc["nodes"][0]["inputs"]["source"]["required"] = False
        self.assertEqual(result.workflow_id, "demo-workflow")
        self.assertTrue(result.tasks[0]["inputs"]["source"]["required"])
        self.assertIsInstance(result.tasks, tuple)
        with self.assertRaises(TypeError):
            result.record["workflow_id"] = "changed"  # type: ignore[index]
        with self.assertRaises(TypeError):
            result.tasks[0]["inputs"]["source"]["required"] = False  # type: ignore[index]

    def test_unknown_root_field_is_rejected(self) -> None:
        value = copy.deepcopy(self.doc)
        value["unexpected"] = True
        self.assertCode("E_SCHEMA_FIELDS", value, field="/unexpected")

    def test_unknown_schema_version_is_rejected(self) -> None:
        value = copy.deepcopy(self.doc)
        value["schema_version"] = 2
        self.assertCode("E_SCHEMA_VERSION_UNSUPPORTED", value, field="/schema_version")

    def test_duplicate_json_key_is_rejected_by_strict_entrypoint(self) -> None:
        raw = b'{"record_type":"workflow-definition","record_type":"workflow-definition"}'
        with self.assertRaises(protocols.ProtocolError) as caught:
            workflow.parse_workflow(raw)
        self.assertEqual(caught.exception.code, "E_JSON_DUPLICATE_KEY")

    def test_duplicate_task_id_is_rejected(self) -> None:
        value = copy.deepcopy(self.doc)
        value["nodes"].append(copy.deepcopy(value["nodes"][0]))
        self.assertCode("E_SCHEMA_FIELDS", value, field="/nodes/2/id")

    def test_missing_dependency_is_rejected(self) -> None:
        value = copy.deepcopy(self.doc)
        value["nodes"][1]["depends_on"] = ["missing"]
        self.assertCode("E_SCHEMA_FIELDS", value, field="/nodes/1/depends_on/0")

    def test_task_cycle_is_rejected(self) -> None:
        value = copy.deepcopy(self.doc)
        value["nodes"][0]["depends_on"] = ["beta"]
        self.assertCode("E_SCHEMA_FIELDS", value, field="/nodes")

    def test_duplicate_stage_and_stage_cycle_are_rejected(self) -> None:
        duplicate = copy.deepcopy(self.doc)
        duplicate["nodes"][0]["stages"].append(copy.deepcopy(duplicate["nodes"][0]["stages"][0]))
        with self.assertRaises(protocols.ProtocolError) as caught:
            workflow.validate_workflow(duplicate)
        self.assertEqual(caught.exception.reason, "duplicate_stage_id")

        cycle = copy.deepcopy(self.doc)
        stages = cycle["nodes"][0]["stages"]
        stages[0]["depends_on"] = ["verdict"]
        with self.assertRaises(protocols.ProtocolError) as caught:
            workflow.validate_workflow(cycle)
        self.assertEqual(caught.exception.reason, "dependency_cycle")

    def test_check_must_follow_freeze_and_verdict_all_checks(self) -> None:
        value = copy.deepcopy(self.doc)
        stages = value["nodes"][0]["stages"]
        stages[2]["depends_on"] = []
        self.assertCode("E_SCHEMA_FIELDS", value, field="/nodes/0/stages/2/depends_on")

        value = copy.deepcopy(self.doc)
        stages = value["nodes"][0]["stages"]
        stages[3]["depends_on"] = ["freeze"]
        self.assertCode("E_SCHEMA_FIELDS", value, field="/nodes/0/stages/2/depends_on")

    def test_stage_profile_requires_all_four_roles_and_kinds(self) -> None:
        value = copy.deepcopy(self.doc)
        value["nodes"][0]["stages"] = value["nodes"][0]["stages"][:3]
        self.assertCode("E_SCHEMA_FIELDS", value, field="/nodes/0/stages")

        value = copy.deepcopy(self.doc)
        value["nodes"][0]["stages"][0]["role"] = "planner"
        self.assertCode("E_SCHEMA_FIELDS", value, field="/nodes/0/stages/0/role")

    def test_empty_scope_and_resource_key_sets_are_valid(self) -> None:
        value = copy.deepcopy(self.doc)
        for node in value["nodes"]:
            node["write_scope"] = []
            node["resource_keys"] = []
        result = workflow.validate_workflow(value)
        self.assertEqual(result.task_order, ("alpha", "beta"))

    def test_required_input_and_output_stage_are_checked(self) -> None:
        value = copy.deepcopy(self.doc)
        del value["nodes"][0]["input_bindings"]["source"]
        self.assertCode("E_SCHEMA_FIELDS", value, field="/nodes/0/input_bindings/source")

        value = copy.deepcopy(self.doc)
        value["nodes"][0]["outputs"]["result"]["stage_id"] = "missing"
        self.assertCode("E_SCHEMA_FIELDS", value, field="/nodes/0/outputs/result/stage_id")

        value = copy.deepcopy(self.doc)
        value["nodes"][0]["inputs"]["bad/key"] = value["nodes"][0]["inputs"].pop("source")
        self.assertCode("E_SCHEMA_FIELDS", value, field="/nodes/0/inputs/bad~1key")

    def test_binding_source_and_schema_must_match(self) -> None:
        value = copy.deepcopy(self.doc)
        value["nodes"][1]["depends_on"] = []
        self.assertCode("E_SCHEMA_FIELDS", value, field="/nodes/1/input_bindings/source/task_id")

        value = copy.deepcopy(self.doc)
        value["nodes"][1]["inputs"]["source"]["schema_ref"]["id"] = "other-port"
        self.assertCode("E_SCHEMA_FIELDS", value, field="/nodes/1/input_bindings/source/port")

    def test_schema_identity_ignores_locator_but_not_identity_fields(self) -> None:
        left = copy.deepcopy(self.doc["nodes"][0]["inputs"]["source"]["schema_ref"])
        right = copy.deepcopy(left)
        right["path"] = "schemas/another-location.json"
        self.assertEqual(workflow.schema_ref_identity(left), workflow.schema_ref_identity(right))
        self.assertTrue(workflow.schema_refs_compatible(left, right))
        frozen = workflow.validate_workflow(self.doc).tasks[0]["inputs"]["source"]["schema_ref"]
        self.assertEqual(workflow.schema_ref_identity(frozen), workflow.schema_ref_identity(left))
        for key, replacement in (("kind", "other-schema"), ("id", "other-port"), ("sha256", "2" * 64)):
            changed = copy.deepcopy(right)
            changed[key] = replacement
            self.assertFalse(workflow.schema_refs_compatible(left, changed), key)

    def test_resource_conflicts_are_segment_aware_deterministic_and_pure(self) -> None:
        value = copy.deepcopy(self.doc)
        value["nodes"][1]["write_scope"] = [{"path": "src/alpha/child", "kind": "file"}]
        value["nodes"][1]["resource_keys"] = ["module:alpha"]
        before = copy.deepcopy(value)
        conflicts = workflow.resource_conflicts(value)
        self.assertEqual(conflicts, (
            ("alpha", "beta", "resource_key", "module:alpha"),
            ("alpha", "beta", "write_scope", "src/alpha|src/alpha/child"),
        ))
        reversed_conflicts = workflow.resource_conflicts({**value, "nodes": list(reversed(value["nodes"]))})
        self.assertEqual(reversed_conflicts, conflicts)
        self.assertEqual(value, before)

        sibling = copy.deepcopy(self.doc)
        sibling["nodes"][1]["write_scope"] = [{"path": "src/other", "kind": "file"}]
        sibling["nodes"][1]["resource_keys"] = ["module:other"]
        self.assertEqual(workflow.resource_conflicts(sibling), ())

    def test_amount_to_units_is_exact_and_bounded(self) -> None:
        self.assertEqual(workflow.amount_to_units("0", 0), 0)
        self.assertEqual(workflow.amount_to_units("1.2", 3), 1200)
        self.assertEqual(workflow.amount_to_units("1.200", 3), 1200)
        for amount, scale in (("1.234", 2), ("01", 2), ("1e2", 2), ("1.", 2), ("1", -1), ("1", 10)):
            with self.subTest(amount=amount, scale=scale):
                with self.assertRaises(protocols.ProtocolError):
                    workflow.amount_to_units(amount, scale)
        with self.assertRaises(protocols.ProtocolError):
            workflow.amount_to_units(True, 2)  # type: ignore[arg-type]
        with self.assertRaises(protocols.ProtocolError):
            workflow.amount_to_units("9" * 64, 9)

    def test_ref_path_and_digest_are_strict(self) -> None:
        value = copy.deepcopy(self.doc)
        value["plugin_lock_ref"]["sha256"] = "A" * 64
        self.assertCode("E_ID_SYNTAX", value, field="/plugin_lock_ref/sha256")

        value = copy.deepcopy(self.doc)
        value["plugin_lock_ref"]["path"] = "../outside"
        self.assertCode("E_PATH_SYNTAX", value, field="/plugin_lock_ref/path")

        value = copy.deepcopy(self.doc)
        del value["plugin_lock_ref"]["path"]
        self.assertCode("E_SCHEMA_FIELDS", value, field="/plugin_lock_ref/path")

    def test_budget_and_retry_reject_bool_float_and_invalid_money(self) -> None:
        for mutate in (
            lambda value: value["nodes"][0]["budget"].update(max_dispatches=True),
            lambda value: value["nodes"][0]["retry_policy"].update(min_backoff_seconds=1.0),
            lambda value: value["nodes"][0]["budget"]["currency_caps"].update(USD="1e2"),
        ):
            value = copy.deepcopy(self.doc)
            mutate(value)
            with self.assertRaises(protocols.ProtocolError):
                workflow.validate_workflow(value)

    def test_budget_currency_caps_are_bounded(self) -> None:
        value = copy.deepcopy(self.doc)
        value["nodes"][0]["budget"]["currency_caps"] = {
            f"{chr(65 + index // 26)}{chr(65 + index % 26)}A": "1"
            for index in range(workflow.MAX_MAPPING_ENTRIES + 1)
        }
        with self.assertRaises(protocols.ProtocolError) as caught:
            workflow.validate_workflow(value)
        self.assertEqual(caught.exception.code, "E_JSON_LIMIT")

    def test_parse_workflow_accepts_bytes_only(self) -> None:
        result = workflow.parse_workflow(FIXTURE.read_bytes())
        self.assertEqual(result.task_order, ("alpha", "beta"))
        with self.assertRaises(protocols.ProtocolError) as caught:
            workflow.parse_workflow(FIXTURE.read_text(encoding="utf-8"))  # type: ignore[arg-type]
        self.assertEqual(caught.exception.code, "E_JSON_INPUT_TYPE")

    def test_schema_is_closed_and_matches_record_family(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "urn:codekit:workflow-definition:1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["record_type"]["const"], "workflow-definition")
        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
        self.assertEqual(schema["$defs"]["resourceRef"]["required"], ["kind", "id", "sha256", "path"])
        self.assertEqual(schema["$defs"]["stage"]["properties"]["role"]["enum"],
                         ["executor", "core", "independent-review", "supervisor"])
        self.assertEqual(schema["$defs"]["task"]["properties"]["stages"]["minItems"], 4)
        for name in ("inputs", "input_bindings", "outputs"):
            self.assertEqual(schema["$defs"]["task"]["properties"][name]["propertyNames"],
                             {"$ref": "#/$defs/logicalId"})
        trailing_newline_cases = (
            ("logicalId", "demo\n"),
            ("taskId", "demo-task\n"),
            ("requestId", "req-" + "0" * 32 + "\n"),
            ("sha256", "0" * 64 + "\n"),
        )
        for definition, value in trailing_newline_cases:
            with self.subTest(definition=definition):
                self.assertIsNone(re.search(schema["$defs"][definition]["pattern"], value))
        self.assertIsNone(re.search(schema["$defs"]["resourceRef"]["properties"]["kind"]["pattern"], "schema\n"))
        self.assertIsNone(re.search(schema["$defs"]["budget"]["properties"]["currency_caps"]["propertyNames"]["pattern"],
                                    "USD\n"))
        self.assertIsNone(re.search(schema["$defs"]["budget"]["properties"]["currency_caps"]["additionalProperties"]["pattern"],
                                    "1.00\n"))
        self.assertFalse(schema["$defs"]["task"]["additionalProperties"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
