import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.planner_adapter import (  # noqa: E402
    AdapterError,
    InvocationEnvelope,
    OfflinePlannerAdapter,
    validate_static_draft_commands,
)


def ref(name: str):
    return {"kind": "file", "id": name, "path": f"inputs/{name}.json", "sha256": "a" * 64}


def request():
    none = None
    return {"record_type": "planner-request", "schema_version": 1, "request_id": "req-1",
            "run_id": "run-1", "operation_id": "op-1", "mode": "graph", "target_task_id": none,
            "requirements_ref": ref("requirements"), "context_manifest_ref": ref("context"),
            "graph_ref": none, "baseline_ref": ref("baseline"), "planner_config_ref": ref("planner"),
            "environment_ref": ref("environment"), "catalog_ref": ref("catalog"), "rules_refs": [],
            "decision_refs": [], "output_contract_ref": ref("output"), "planning_budget_ref": ref("budget"),
            "authorization_refs": [ref("authorization")], "repair_policy_ref": ref("repair"),
            "stop_policy_ref": ref("stop")}


class PlannerAdapterTests(unittest.TestCase):
    def test_offline_adapter_handoff_is_replay_safe(self):
        envelope = InvocationEnvelope("req-1", "op-1", "planner", (ref("context"),))
        adapter = OfflinePlannerAdapter()
        events = adapter.invoke(request(), {"record_type": "planning-bundle"}, envelope=envelope)
        self.assertEqual(adapter.extract(list(events) + list(events)), {"record_type": "planning-bundle"})
        with self.assertRaisesRegex(AdapterError, "E_RESULT_AMBIGUOUS"):
            adapter.extract([events[0], {**events[0], "event_id": "second"}])

    def test_static_commands_only_describe_execution(self):
        commands = validate_static_draft_commands([{"id": "C01", "argv": ["python", "-m", "unittest"]}])
        self.assertFalse(commands[0]["executed"])
        with self.assertRaisesRegex(AdapterError, "E_STATIC_COMMANDS"):
            validate_static_draft_commands([{"argv": "python"}])
        with self.assertRaisesRegex(AdapterError, "E_STATIC_COMMANDS"):
            validate_static_draft_commands([{"argv": ["python", "-c", "x && y"]}])


if __name__ == "__main__":
    unittest.main()
