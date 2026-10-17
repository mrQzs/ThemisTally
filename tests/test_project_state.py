import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.codekit.project_state import ProjectStateError, reduce_project_events
from tests.test_project_events import event, ref


class ProjectStateTests(unittest.TestCase):
    def test_duplicate_completion_is_idempotent_and_late_revision_does_not_regress(self):
        events = [
            event(event_type="task.accepted", source_record_id="a", immutable_facet_id="accepted", payload={"task_id": "task-1", "revision": 1}),
            event(event_type="task.completed", source_record_id="b", immutable_facet_id="completed", payload={"task_id": "task-1", "revision": 2}),
            event(event_type="task.completed", source_record_id="c", immutable_facet_id="completed-2", payload={"task_id": "task-1", "revision": 1}),
        ]
        assigned = [item.assigned(1, index) for index, item in enumerate(events, 1)]
        state = reduce_project_events(assigned + [assigned[1]], verification_ref="verify-1", as_of="2026-10-04T00:00:00Z",
                                      verification={item.source_key.digest: "verified" for item in assigned})
        self.assertEqual(state.tasks["task-1"]["status"], "COMPLETED")
        self.assertEqual(state.tasks["task-1"]["revision"], 2)
        self.assertEqual(state.applied_cursor, 3)

    def test_budget_snapshot_replaces_instead_of_accumulating(self):
        first = event(event_type="budget.snapshot.observed", source_record_id="budget-1", immutable_facet_id="snapshot-1",
                      payload={"ledger_id": "ledger", "ledger_revision": 1, "known_amount": "1.00"}).assigned(1, 1)
        second = event(event_type="budget.snapshot.observed", source_record_id="budget-2", immutable_facet_id="snapshot-2",
                       payload={"ledger_id": "ledger", "ledger_revision": 2, "known_amount": "2.00"}).assigned(1, 2)
        state = reduce_project_events([first, second], verification_ref="verify-1", as_of="now",
                                      verification={first.source_key.digest: "verified", second.source_key.digest: "verified"})
        self.assertEqual(state.budgets["ledger"]["snapshot"]["known_amount"], "2.00")
        self.assertEqual(state.budget_coverage, "complete")

    def test_acceptance_and_integration_are_separate_dimensions(self):
        accepted = event(event_type="task.accepted", source_record_id="accept", immutable_facet_id="accepted",
                         payload={"task_id": "task-1", "revision": 1}).assigned(1, 1)
        integrated = event(event_type="task.integrated", source_record_id="integrate", immutable_facet_id="integrated",
                           payload={"task_id": "task-1", "revision": 2}).assigned(1, 2)
        state = reduce_project_events([accepted, integrated], verification_ref="v", as_of="now",
                                      verification={accepted.source_key.digest: "verified", integrated.source_key.digest: "verified"})
        task = state.tasks["task-1"]
        self.assertEqual(task["acceptance_status"], "ACCEPTED")
        self.assertEqual(task["integration_status"], "INTEGRATED")

    def test_latest_unverified_budget_does_not_fallback_to_old_snapshot(self):
        first = event(event_type="budget.snapshot.observed", source_record_id="budget-old", immutable_facet_id="snapshot-old",
                      payload={"ledger_id": "ledger", "ledger_revision": 1, "known_amount": "1.00"}).assigned(1, 1)
        latest = event(event_type="budget.snapshot.observed", source_record_id="budget-new", immutable_facet_id="snapshot-new",
                       payload={"ledger_id": "ledger", "ledger_revision": 2, "known_amount": "2.00"}).assigned(1, 2)
        state = reduce_project_events([first, latest], verification_ref="v", as_of="now",
                                      verification={first.source_key.digest: "verified", latest.source_key.digest: "missing"})
        self.assertEqual(state.budget_coverage, "unknown")
        self.assertEqual(state.budgets["ledger"]["currentness"], "unknown")

    def test_missing_source_verification_is_not_complete(self):
        assigned = event().assigned(1, 1)
        state = reduce_project_events([assigned], verification_ref="v", as_of="now", verification={})
        self.assertEqual(state.source_coverage, "unknown")

    def test_gap_and_unassigned_event_are_rejected(self):
        assigned = event().assigned(1, 2)
        with self.assertRaisesRegex(ProjectStateError, "contiguous"):
            reduce_project_events([assigned], verification_ref="v", as_of="now")
        with self.assertRaisesRegex(ProjectStateError, "assigned"):
            reduce_project_events([event()], verification_ref="v", as_of="now")

    def test_state_schema_is_valid_json(self):
        value = json.loads(Path("schemas/project-state-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(value["$id"], "urn:codekit:project-state:1")


if __name__ == "__main__":
    unittest.main()
