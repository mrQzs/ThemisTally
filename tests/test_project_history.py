import json
import tempfile
import unittest
from pathlib import Path

from scripts.codekit.project_history import evaluate_currentness, validate_revision_chain
from tests.test_project_events import event


class ProjectHistoryTests(unittest.TestCase):
    def test_revision_chain_reports_missing_predecessor_and_fork(self):
        first = event(source_record_id="r1", immutable_facet_id="facet-1", payload={"task_id": "task-1", "revision": 1}).assigned(1, 1)
        missing = event(source_record_id="r3", immutable_facet_id="facet-3", payload={"task_id": "task-1", "revision": 3}, predecessor_refs=({"event_id": "missing"},)).assigned(1, 2)
        fork = event(source_record_id="r2", immutable_facet_id="facet-2", payload={"task_id": "task-1", "revision": 1}).assigned(1, 3)
        report = validate_revision_chain([first, missing, fork])
        self.assertEqual(report.status, "UNKNOWN"); self.assertIsNone(report.heads["task-1"])
        self.assertTrue(any(item.startswith("predecessor-missing") for item in report.issues))
        self.assertTrue(any(item.startswith("fork") for item in report.issues))

    def test_related_rule_change_stales_only_bound_source(self):
        current = evaluate_currentness(["rule-a", "contract-a"], ["progress-b", "rule-a"])
        self.assertEqual(current.status, "STALE"); self.assertEqual(current.related_changes, ("rule-a",)); self.assertEqual(current.unrelated_changes, ("progress-b",))

    def test_schemas_are_valid_json(self):
        for path in ("schemas/revision-chain-report-v1.schema.json", "schemas/currentness-observation-v1.schema.json"):
            self.assertTrue(json.loads(Path(path).read_text(encoding="utf-8"))["$id"].startswith("urn:codekit:"))


if __name__ == "__main__":
    unittest.main()
