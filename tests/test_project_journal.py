import tempfile
import threading
import unittest
import hashlib
from pathlib import Path

from scripts.codekit.project_events import ProjectEvent
from scripts.codekit.project_journal import ProjectJournal, ProjectJournalError, WriterLock
from tests.test_project_events import event


class ProjectJournalTests(unittest.TestCase):
    def test_append_is_idempotent_and_rejects_same_source_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            journal = ProjectJournal(path)
            first = journal.append(event())
            replay = journal.append(event())
            self.assertFalse(first.replayed)
            self.assertTrue(replay.replayed)
            self.assertEqual(journal.cursor, 1)
            with self.assertRaisesRegex(ProjectJournalError, "same SourceKey"):
                journal.append(event(payload={"status": "STARTED"}))

    def test_reload_rejects_gap_and_repairs_only_uncommitted_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            journal = ProjectJournal(path)
            journal.append(event())
            path.write_bytes(path.read_bytes() + b'{"kind":"event"}')
            recovered = ProjectJournal(path)
            self.assertEqual(recovered.recovery, "TRUNCATED_TAIL")
            with self.assertRaisesRegex(ProjectJournalError, "repair"):
                recovered.append(event(source_record_id="source-2", immutable_facet_id="prepared-2"))
            recovered.repair_tail(expected_generation=1, expected_cursor=1)
            self.assertEqual(recovered.recovery, "CLEAN")
            self.assertTrue(path.with_name(path.name + ".tail-backup").exists())

    def test_tail_repair_checks_expected_bytes_before_truncating(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"; journal = ProjectJournal(path); journal.append(event())
            path.write_bytes(path.read_bytes() + b'{"tail":')
            recovered = ProjectJournal(path)
            with self.assertRaisesRegex(ProjectJournalError, "bytes changed"):
                recovered.repair_tail(expected_generation=1, expected_cursor=1, expected_sha256="0" * 64)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            original = path.read_bytes()
            backup = Path(tmp) / "preserved-tail.bin"
            recovered.repair_tail(expected_generation=1, expected_cursor=1, expected_sha256=digest, backup_path=backup)
            self.assertEqual(backup.read_bytes(), original)

    def test_middle_corruption_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            journal = ProjectJournal(path)
            journal.append(event())
            journal.append(event(source_record_id="source-2", immutable_facet_id="prepared-2"))
            journal.append(event(source_record_id="source-3", immutable_facet_id="prepared-3"))
            lines = path.read_bytes().splitlines(keepends=True)
            path.write_bytes(lines[0] + b'not-json\n' + lines[2])
            with self.assertRaisesRegex(ProjectJournalError, "strict JSON"):
                ProjectJournal(path)

    def test_writer_lock_has_one_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "writer.lock"
            entered = threading.Event(); release = threading.Event()
            def hold():
                with WriterLock(lock_path):
                    entered.set(); release.wait(2)
            thread = threading.Thread(target=hold)
            thread.start(); self.assertTrue(entered.wait(1))
            with self.assertRaises(ProjectJournalError) as caught:
                with WriterLock(lock_path, timeout=0.05):
                    pass
            self.assertEqual(caught.exception.code, "E_LOCK_BUSY")
            release.set(); thread.join(2)


if __name__ == "__main__":
    unittest.main()
