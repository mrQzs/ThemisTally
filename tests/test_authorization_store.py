import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

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

    def test_consume_once_is_journaled_and_replayed(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area) / "auth.jsonl"
            store = PersistentApprovalStore(path)
            store.put(scope="scope", operation_id="put-1", expected_generation=0, record=approval())
            self.assertTrue(store.consume_once(scope="scope", action="run", input_refs=[ref("input")],
                                               operation_id="consume-1", expected_generation=1))
            restored = PersistentApprovalStore(path)
            self.assertTrue(restored.consume_once(scope="scope", action="run", input_refs=[ref("input")],
                                                  operation_id="consume-1", expected_generation=1))
            with self.assertRaisesRegex(AuthorizationError, "E_ALREADY_CONSUMED"):
                restored.consume_once(scope="scope", action="run", input_refs=[ref("input")],
                                     operation_id="consume-2", expected_generation=1)

    def test_consume_replay_uses_original_time_window(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area) / "auth.jsonl"
            store = PersistentApprovalStore(path)
            record = {**approval(), "expires_at": "2025-12-31T00:00:00Z"}
            store.put(scope="scope", operation_id="put-1", expected_generation=0, record=record)
            store.consume_once(scope="scope", action="run", input_refs=[ref("input")],
                               operation_id="consume-1", expected_generation=1,
                               now=datetime(2025, 1, 2, tzinfo=timezone.utc))
            restored = PersistentApprovalStore(path)
            self.assertTrue(restored.reconcile()["recovery"]["status"] == "CLEAN")

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
            with self.assertRaisesRegex(AuthorizationError, "E_AUTH_RECOVERY"):
                restored.put(scope="scope", operation_id="put-2", expected_generation=1, record=approval())

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

    def test_journal_rejects_malformed_identity_and_duplicate_events(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area) / "auth.jsonl"
            event = {"seq": 1, "type": "approval", "scope": "scope", "operation_id": "put-1",
                     "expected_generation": 0, "record": approval()}
            for field in ("type", "scope", "operation_id"):
                for bad in ([], {}, True, 1):
                    with self.subTest(field=field, bad=bad):
                        path.write_text(json.dumps({**event, field: bad}) + "\n", encoding="utf-8")
                        with self.assertRaisesRegex(AuthorizationError, "E_AUTH_JOURNAL"):
                            PersistentApprovalStore(path)
            for bad in (True, False, "0", -1):
                path.write_text(json.dumps({**event, "expected_generation": bad}) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(AuthorizationError, "E_AUTH_JOURNAL"):
                    PersistentApprovalStore(path)
            path.write_text(json.dumps(event) + "\n" + json.dumps({**event, "seq": 2}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(AuthorizationError, "E_AUTH_JOURNAL"):
                PersistentApprovalStore(path)

    def test_journal_text_boundary_rejects_controls_and_surrogates(self):
        bad_values = ("\x01", "\x1f", "\x7f", "\x80", "\x9f", "\ud800")
        for bad in bad_values:
            with self.subTest(codepoint=ord(bad)):
                with tempfile.TemporaryDirectory() as area:
                    path = Path(area) / "auth.jsonl"
                    store = PersistentApprovalStore(path)
                    with self.assertRaises(AuthorizationError):
                        store.put(scope="scope" + bad, operation_id="put-1",
                                  expected_generation=0, record=approval())
                    self.assertFalse(path.exists())

                    event = {"seq": 1, "type": "approval", "scope": "scope" + bad,
                             "operation_id": "put-1", "expected_generation": 0,
                             "record": approval()}
                    path.write_text(json.dumps(event) + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(AuthorizationError, "E_AUTH_JOURNAL"):
                        PersistentApprovalStore(path)

    def test_append_failure_does_not_publish_head_and_fences_writes(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area) / "auth.jsonl"
            store = PersistentApprovalStore(path)
            with patch.object(store, "_append", side_effect=OSError("write failed")):
                with self.assertRaisesRegex(AuthorizationError, "E_AUTH_WRITE_UNKNOWN"):
                    store.put(scope="scope", operation_id="put-1", expected_generation=0, record=approval())
            self.assertIsNone(store.ledger.head("scope"))
            self.assertEqual(store.high_water, 0)
            self.assertEqual(store.recovery["status"], "WRITE_UNKNOWN")
            with self.assertRaisesRegex(AuthorizationError, "E_AUTH_RECOVERY"):
                store.put(scope="scope", operation_id="put-1", expected_generation=0, record=approval())
            restored = PersistentApprovalStore(path)
            self.assertIsNone(restored.ledger.head("scope"))
            self.assertEqual(restored.put(scope="scope", operation_id="put-1", expected_generation=0,
                                          record=approval()).generation, 1)

    def test_fsync_unknown_reopen_recovers_complete_event_without_double_consumption(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area) / "auth.jsonl"
            store = PersistentApprovalStore(path)
            store.put(scope="scope", operation_id="put-1", expected_generation=0, record=approval())
            with patch("codekit.authorization_store.os.fsync", side_effect=OSError("fsync failed")):
                with self.assertRaisesRegex(AuthorizationError, "E_AUTH_WRITE_UNKNOWN"):
                    store.consume_once(scope="scope", action="run", input_refs=[ref("input")],
                                       operation_id="consume-1", expected_generation=1)
            self.assertEqual(store.high_water, 1)
            self.assertEqual(store.ledger._consumptions, {})
            with self.assertRaisesRegex(AuthorizationError, "E_AUTH_RECOVERY"):
                store.lock(scope="scope", receipt_id="lock", operation_id="lock", bindings=[ref("input")])
            restored = PersistentApprovalStore(path)
            self.assertEqual(restored.high_water, 2)
            self.assertEqual(restored.recovery["status"], "CLEAN")
            self.assertTrue(restored.consume_once(scope="scope", action="run", input_refs=[ref("input")],
                                                  operation_id="consume-1", expected_generation=1))
            with self.assertRaisesRegex(AuthorizationError, "E_ALREADY_CONSUMED"):
                restored.consume_once(scope="scope", action="run", input_refs=[ref("input")],
                                     operation_id="consume-2", expected_generation=1)

    def test_partial_append_unknown_is_not_published_or_reused_after_reopen(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area) / "auth.jsonl"
            store = PersistentApprovalStore(path)
            store.put(scope="scope", operation_id="put-1", expected_generation=0, record=approval())
            def torn_append(event):
                with path.open("ab") as handle:
                    handle.write(b'{"seq":2,"type":"lock"')
                raise OSError("torn append")
            with patch.object(store, "_append", side_effect=torn_append):
                with self.assertRaisesRegex(AuthorizationError, "E_AUTH_WRITE_UNKNOWN"):
                    store.lock(scope="scope", receipt_id="lock", operation_id="lock", bindings=[ref("input")])
            self.assertEqual(store.ledger._receipts, {})
            restored = PersistentApprovalStore(path)
            self.assertEqual(restored.high_water, 1)
            self.assertEqual(restored.recovery["status"], "TRUNCATED_TAIL")
            with self.assertRaisesRegex(AuthorizationError, "E_AUTH_RECOVERY"):
                restored.lock(scope="scope", receipt_id="lock", operation_id="lock", bindings=[ref("input")])


if __name__ == "__main__":
    unittest.main()
