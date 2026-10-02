import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.authorization import AuthorizationError
from codekit.authorization_store import PersistentApprovalStore


def ref(name="task"):
    return {"kind": "contract", "id": name, "path": f"fixtures/{name}.json", "sha256": "a" * 64}


def approval():
    return {"record_type": "approval-record", "schema_version": 1, "approval_id": "a1", "request_id": "r1",
            "subject_ref": ref(), "input_refs": [ref("input")], "reviewed_actions": ["run"], "decision": "APPROVED",
            "recorded_at": "2026-01-01T00:00:00Z", "reviewer": {"mode": "current_session"}}


class PersistentAuthorizationTests(unittest.TestCase):
    def test_approval_and_lock_survive_reload(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area) / "auth.jsonl"
            store = PersistentApprovalStore(path)
            store.put(scope="scope", operation_id="put-1", expected_generation=0, record=approval())
            store.lock(scope="scope", receipt_id="lock-1", operation_id="lock-1", bindings=[ref("input")])
            restored = PersistentApprovalStore(path)
            self.assertEqual(restored.ledger.head("scope").generation, 1)
            self.assertEqual(restored.high_water, 2)
            self.assertEqual(restored.reconcile()["recovery"]["status"], "CLEAN")

    def test_replay_is_idempotent_without_duplicate_events(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area) / "auth.jsonl"
            store = PersistentApprovalStore(path)
            first = store.put(scope="scope", operation_id="put-1", expected_generation=0, record=approval())
            replay = store.put(scope="scope", operation_id="put-1", expected_generation=0, record=approval())
            self.assertEqual(first, replay)
            self.assertEqual(len(path.read_bytes().splitlines()), 1)

    def test_truncated_tail_is_ignored_and_reported(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area) / "auth.jsonl"
            store = PersistentApprovalStore(path)
            store.put(scope="scope", operation_id="put-1", expected_generation=0, record=approval())
            with path.open("ab") as handle:
                handle.write(b'{"seq":2,"type":"approval"')
            restored = PersistentApprovalStore(path)
            self.assertEqual(restored.ledger.head("scope").generation, 1)
            self.assertEqual(restored.reconcile()["recovery"]["status"], "TRUNCATED_TAIL")

    def test_non_tail_corruption_is_not_silently_reconciled(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area) / "auth.jsonl"
            path.write_bytes(b"not-json\n" + json.dumps({"seq": 2}).encode() + b"\n")
            with self.assertRaisesRegex(AuthorizationError, "E_AUTH_JOURNAL"):
                PersistentApprovalStore(path)

    def test_newline_terminated_bad_tail_and_malformed_lock_are_rejected(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area) / "auth.jsonl"
            path.write_bytes(b"not-json\n")
            with self.assertRaisesRegex(AuthorizationError, "E_AUTH_JOURNAL"):
                PersistentApprovalStore(path)
            path.write_text(json.dumps({"seq": 1, "type": "lock"}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(AuthorizationError, "E_AUTH_JOURNAL"):
                PersistentApprovalStore(path)


if __name__ == "__main__":
    unittest.main()
