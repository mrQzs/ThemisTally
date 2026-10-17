import json
import tempfile
import unittest
from pathlib import Path

from scripts.codekit.project_journal import ProjectJournal
from scripts.codekit.project_reconcile import ReconcileError, reconcile_events
from tests.test_project_events import event


class ProjectReconcileTests(unittest.TestCase):
    def test_verified_source_appends_once_and_unverified_stays_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = ProjectJournal(Path(tmp) / "events.jsonl")
            first = event(source_record_id="source-1", immutable_facet_id="prepared-1")
            pending = event(source_record_id="source-2", immutable_facet_id="prepared-2")
            statuses = {first.source_key.digest: "verified", pending.source_key.digest: "missing"}
            report = reconcile_events(journal, [first, pending], expected_generation=1, expected_cursor=0, source_status=statuses)
            self.assertEqual(report.status, "PARTIAL"); self.assertEqual(report.appended, 1); self.assertEqual(report.end_cursor, 1)
            replay = reconcile_events(journal, [first], expected_generation=1, expected_cursor=1,
                                      source_status={first.source_key.digest: "verified"})
            self.assertEqual(replay.replayed, 1); self.assertEqual(journal.cursor, 1)

    def test_concurrent_head_change_is_cas_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = ProjectJournal(Path(tmp) / "events.jsonl")
            journal.append(event())
            with self.assertRaisesRegex(ReconcileError, "head changed"):
                reconcile_events(journal, [event(source_record_id="source-2", immutable_facet_id="prepared-2")],
                                 expected_generation=1, expected_cursor=0,
                                 source_status={event(source_record_id="source-2", immutable_facet_id="prepared-2").source_key.digest: "verified"})

    def test_schema_is_valid_json(self):
        value = json.loads(Path("schemas/reconcile-report-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(value["$id"], "urn:codekit:reconcile-report:1")


if __name__ == "__main__":
    unittest.main()
