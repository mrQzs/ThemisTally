import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.codekit.project_journal import ProjectJournal
from scripts.codekit.project_recovery import RecoveryError, rebuild_generation
from scripts.codekit.project_scanner import scan_source_tree
from tests.test_project_events import event


class ProjectRecoveryTests(unittest.TestCase):
    def test_bounded_scan_is_deterministic_and_partial_when_limited(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "b.txt").write_bytes(b"b"); (root / "a.txt").write_bytes(b"a")
            (root / "a.txt").touch(); (root / "b.txt").touch()
            import os
            os.utime(root / "a.txt", ns=(1, 1)); os.utime(root / "b.txt", ns=(1, 1))
            first = scan_source_tree(root, cutoff_ns=2**53 - 1, max_entries=10)
            second = scan_source_tree(root, cutoff_ns=2**53 - 1, max_entries=10)
            self.assertTrue(first.complete)
            self.assertEqual(first.to_mapping(), second.to_mapping())
            limited = scan_source_tree(root, cutoff_ns=2**53 - 1, max_entries=1)
            self.assertFalse(limited.complete)
            self.assertIn("entry_limit", limited.issues)
            resumed = scan_source_tree(root, cutoff_ns=2**53 - 1, max_entries=10, after_path=limited.next_page)
            self.assertTrue(resumed.complete)
            self.assertEqual([item["path"] for item in resumed.items], ["b.txt"])

    def test_rebuild_advances_generation_and_requires_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.jsonl"; target = Path(tmp) / "rebuild.jsonl"
            journal = ProjectJournal(source)
            journal.append(event())
            journal.append(event(source_record_id="source-2", immutable_facet_id="prepared-2"))
            report = rebuild_generation(source, target, new_generation=2)
            self.assertTrue(report.reset_required)
            self.assertEqual(report.new_cursor, 2)
            rebuilt = ProjectJournal(target, generation=2)
            self.assertEqual(rebuilt.cursor, 2)
            self.assertEqual([e.event_id for e in rebuilt.events.values()], [e.event_id for e in journal.events.values()])

    def test_rebuild_does_not_overwrite_source_or_accept_tail_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.jsonl"; target = Path(tmp) / "rebuild.jsonl"
            journal = ProjectJournal(source); journal.append(event())
            source.write_bytes(source.read_bytes() + b'{"tail":')
            with self.assertRaisesRegex(RecoveryError, "repair"):
                rebuild_generation(source, target, new_generation=2)

    def test_schemas_are_valid_json(self):
        for path, schema_id in (("schemas/source-scan-v1.schema.json", "urn:codekit:source-scan:1"),
                                ("schemas/recovery-report-v1.schema.json", "urn:codekit:recovery-report:1")):
            value = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(value["$id"], schema_id)


if __name__ == "__main__":
    unittest.main()
