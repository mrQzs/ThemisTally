import json
import tempfile
import unittest
from pathlib import Path

from scripts.codekit.project_views import ProjectViewError, ViewPackageStore, make_read_receipt, render_project_brief


STATE = {"indexed_cursor": 2, "applied_cursor": 2, "source_coverage": "complete", "budget_coverage": "complete",
         "verification_ref": "verify-1", "as_of": "2026-10-04T00:00:00Z", "tasks": {"task-1": {"status": "COMPLETED"}},
         "decisions": {}, "budgets": {}, "issues": [], "dispatch_eligibility": "not_evaluated"}


class ProjectViewTests(unittest.TestCase):
    def test_publish_reads_one_current_package_and_receipt_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ViewPackageStore(tmp)
            brief = render_project_brief(STATE)
            first = store.publish(STATE, brief, generation=1, cursor=2)
            second = store.publish(STATE, brief, generation=1, cursor=2, expected_view_id=first.view_id)
            self.assertEqual(first, second)
            manifest, state, loaded_brief = store.read_current()
            self.assertEqual(manifest, first); self.assertEqual(state, STATE); self.assertEqual(loaded_brief, brief)
            receipt = make_read_receipt(manifest, observer_ref="observer-1", read_cursor=2)
            self.assertEqual(receipt, make_read_receipt(manifest, observer_ref="observer-1", read_cursor=2))

    def test_current_pointer_cas_and_package_drift_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ViewPackageStore(tmp); brief = render_project_brief(STATE)
            first = store.publish(STATE, brief, generation=1, cursor=2)
            with self.assertRaisesRegex(ProjectViewError, "changed"):
                store.publish({**STATE, "as_of": "later"}, brief, generation=1, cursor=3, expected_view_id="0" * 64)
            (Path(tmp) / "views" / first.view_id / "state.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ProjectViewError, "bytes"):
                store.read_current()

    def test_brief_budget_is_refusal_and_schemas_are_valid_json(self):
        with self.assertRaisesRegex(ProjectViewError, "budget"):
            render_project_brief(STATE, max_bytes=1)
        for path in ("schemas/project-view-manifest-v1.schema.json", "schemas/brief-read-receipt-v1.schema.json"):
            value = json.loads(Path(path).read_text(encoding="utf-8")); self.assertTrue(value["$id"].startswith("urn:codekit:"))


if __name__ == "__main__":
    unittest.main()
