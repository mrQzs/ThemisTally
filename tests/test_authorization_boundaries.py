"""Boundary regressions for the in-memory approval/input-lock ledger.

These tests deliberately exercise the identity and copy boundaries around the
small offline ledger.  They do not imply that the in-memory implementation is
a production persistence layer.
"""

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.authorization import ApprovalLedger, AuthorizationError, canonical_bytes, sha256, validate_approval


def ref(name: str = "task", *, path: Optional[str] = None) -> dict:
    return {
        "kind": "contract",
        "id": name,
        "path": f"fixtures/{name}.json" if path is None else path,
        "sha256": "a" * 64,
    }


def approval(*, decision: str = "APPROVED", **fields: object) -> dict:
    record = {
        "record_type": "approval-record",
        "schema_version": 1,
        "approval_id": "a1",
        "request_id": "r1",
        "subject_ref": ref(),
        "input_refs": [ref("input")],
        "reviewed_actions": ["prepare", "run"],
        "decision": decision,
        "recorded_at": "2026-01-01T00:00:00Z",
        "reviewer": {"mode": "current_session"},
    }
    record.update(fields)
    return record


class ApprovalLedgerBoundaryTests(unittest.TestCase):
    def test_put_operation_binds_scope_and_expected_generation(self) -> None:
        ledger = ApprovalLedger()
        record = approval()
        first = ledger.put(scope="scope-a", operation_id="op", expected_generation=0, record=record)

        # Retrying the exact operation is a replay, but changing either part of
        # its CAS identity must not be allowed to alias the old operation.
        self.assertEqual(ledger.put(scope="scope-a", operation_id="op", expected_generation=0, record=record), first)
        with self.assertRaisesRegex(AuthorizationError, "E_IDEMPOTENCY_CONFLICT"):
            ledger.put(scope="scope-b", operation_id="op", expected_generation=0, record=record)
        with self.assertRaisesRegex(AuthorizationError, "E_IDEMPOTENCY_CONFLICT"):
            ledger.put(scope="scope-a", operation_id="op", expected_generation=1, record=record)

    def test_put_head_and_history_are_deeply_immutable_to_callers(self) -> None:
        ledger = ApprovalLedger()
        first = ledger.put(scope="scope", operation_id="op1", expected_generation=0, record=approval())

        first.record["reviewer"]["mode"] = "caller-mutated"
        first.record["input_refs"][0]["path"] = "caller-mutated"
        current = ledger.head("scope")
        self.assertIsNotNone(current)
        self.assertEqual(current.record["reviewer"]["mode"], "current_session")
        self.assertEqual(current.record["input_refs"][0]["path"], "fixtures/input.json")

        history = ledger.history("scope")
        self.assertEqual(len(history), 1)
        history[0].record["reviewer"]["mode"] = "history-mutated"
        self.assertEqual(ledger.head("scope").record["reviewer"]["mode"], "current_session")

        # A replay must also be a fresh snapshot, rather than returning a
        # mutable reference held by the ledger.
        replay = ledger.put(scope="scope", operation_id="op1", expected_generation=0, record=approval())
        replay.record["reviewer"]["mode"] = "replay-mutated"
        self.assertEqual(ledger.head("scope").record["reviewer"]["mode"], "current_session")

    def test_consume_honors_aware_not_before_and_half_open_expiry(self) -> None:
        ledger = ApprovalLedger()
        ledger.put(
            scope="scope",
            operation_id="op",
            expected_generation=0,
            record=approval(not_before="2026-01-02T00:00:00Z", expires_at="2026-01-03T00:00:00Z"),
        )
        self.assertFalse(
            ledger.consume(
                scope="scope",
                action="run",
                input_refs=[ref("input")],
                now=datetime(2026, 1, 1, 23, 59, tzinfo=timezone.utc),
            )
        )
        self.assertTrue(
            ledger.consume(
                scope="scope",
                action="run",
                input_refs=[ref("input")],
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
        )
        self.assertFalse(
            ledger.consume(
                scope="scope",
                action="run",
                input_refs=[ref("input")],
                now=datetime(2026, 1, 3, tzinfo=timezone.utc),
            )
        )

    def test_consume_rejects_naive_current_time(self) -> None:
        ledger = ApprovalLedger()
        ledger.put(scope="scope", operation_id="op", expected_generation=0, record=approval())
        with self.assertRaisesRegex(AuthorizationError, "E_APPROVAL_TIME"):
            ledger.consume(
                scope="scope",
                action="run",
                input_refs=[ref("input")],
                now=datetime(2026, 1, 1),
            )

    def test_resource_ref_rejects_unsafe_paths(self) -> None:
        paths = (
            "/absolute/path.json",
            "C:/absolute/path.json",
            "C:\\absolute\\path.json",
            "../escape.json",
            "fixtures/../escape.json",
            "fixtures/./input.json",
            "fixtures//input.json",
            ".",
            "fixtures/input\x00.json",
            "fixtures/input\x1f.json",
        )
        for path in paths:
            with self.subTest(path=path), self.assertRaisesRegex(AuthorizationError, "E_RESOURCE_PATH"):
                validate_approval({**approval(), "subject_ref": ref(path=path)})

    def test_lock_is_idempotent_and_binds_exact_approved_inputs(self) -> None:
        ledger = ApprovalLedger()
        ledger.put(scope="scope", operation_id="op", expected_generation=0, record=approval())
        bindings = [ref("input")]
        first = ledger.lock(scope="scope", receipt_id="receipt-1", operation_id="lock-op", bindings=bindings)
        replay = ledger.lock(scope="scope", receipt_id="receipt-1", operation_id="lock-op", bindings=bindings)
        self.assertEqual(replay, first)

        with self.assertRaisesRegex(AuthorizationError, "E_IDEMPOTENCY_CONFLICT"):
            ledger.lock(scope="scope", receipt_id="receipt-2", operation_id="lock-op", bindings=bindings)
        with self.assertRaisesRegex(AuthorizationError, "E_IDEMPOTENCY_CONFLICT"):
            ledger.lock(scope="scope", receipt_id="receipt-1", operation_id="lock-op", bindings=[ref("other")])

        with self.assertRaisesRegex(AuthorizationError, "E_RECEIPT_CONFLICT"):
            ledger.lock(scope="scope", receipt_id="receipt-1", operation_id="other-lock-op", bindings=bindings)
        with self.assertRaisesRegex(AuthorizationError, "E_LOCK_BINDINGS"):
            ledger.lock(scope="scope", receipt_id="receipt-3", operation_id="third-lock-op", bindings=[])
        with self.assertRaisesRegex(AuthorizationError, "E_LOCK_BINDINGS"):
            ledger.lock(scope="scope", receipt_id="receipt-4", operation_id="fourth-lock-op", bindings=[ref("other")])
        with self.assertRaisesRegex(AuthorizationError, "E_LOCK_BINDINGS"):
            ledger.lock(
                scope="scope",
                receipt_id="receipt-5",
                operation_id="fifth-lock-op",
                bindings=[ref("input"), ref("other")],
            )

    def test_revoke_replay_is_idempotent_and_reason_is_bound(self) -> None:
        ledger = ApprovalLedger()
        ledger.put(scope="scope", operation_id="put-op", expected_generation=0, record=approval())
        revoked = ledger.revoke(scope="scope", operation_id="revoke-op", expected_generation=1, reason="policy")
        replay = ledger.revoke(scope="scope", operation_id="revoke-op", expected_generation=1, reason="policy")
        self.assertEqual(replay, revoked)
        with self.assertRaisesRegex(AuthorizationError, "E_IDEMPOTENCY_CONFLICT"):
            ledger.revoke(scope="scope", operation_id="revoke-op", expected_generation=1, reason="different policy")

    def test_malformed_identities_and_cas_generations_are_classified(self) -> None:
        ledger = ApprovalLedger()
        for bad in ([], {}, 1, True, "", "bad\x00id", "bad\ud800id"):
            with self.subTest(kind="scope", value=repr(bad)), self.assertRaises(AuthorizationError):
                ledger.put(scope=bad, operation_id="put-op", expected_generation=0, record=approval())
            with self.subTest(kind="operation", value=repr(bad)), self.assertRaises(AuthorizationError):
                ledger.put(scope="scope", operation_id=bad, expected_generation=0, record=approval())
            with self.subTest(kind="revoke", value=repr(bad)), self.assertRaises(AuthorizationError):
                ledger.revoke(scope="scope", operation_id=bad, expected_generation=1, reason="revoked")
            with self.subTest(kind="read", value=repr(bad)), self.assertRaises(AuthorizationError):
                ledger.head(bad)
        for generation in (True, False, -1, 0.0, "0", 2**53 - 1, 2**53):
            with self.subTest(generation=generation), self.assertRaisesRegex(AuthorizationError, "E_APPROVAL_SCHEMA"):
                ledger.put(scope="scope", operation_id="put-op", expected_generation=generation, record=approval())
        self.assertIsNone(ledger.head("scope"))
        self.assertEqual(ledger.put(scope="scope", operation_id="put-op", expected_generation=0, record=approval()).generation, 1)

    def test_duplicate_normalized_refs_and_lock_bindings_are_rejected(self) -> None:
        slash = ref("input")
        backslash = {**slash, "path": "fixtures\\input.json"}
        for field in ("input_refs", "authorization_refs"):
            with self.subTest(field=field), self.assertRaisesRegex(AuthorizationError, "E_APPROVAL_SCHEMA"):
                validate_approval(approval(**{field: [slash, backslash]}))
        ledger = ApprovalLedger()
        head = ledger.put(scope="scope", operation_id="put-op", expected_generation=0,
                          record=approval(input_refs=[backslash]))
        self.assertEqual(head.record["input_refs"], [slash])
        self.assertTrue(ledger.consume(scope="scope", action="run", input_refs=[slash]))
        with self.assertRaisesRegex(AuthorizationError, "E_LOCK_BINDINGS"):
            ledger.lock(scope="scope", receipt_id="receipt", operation_id="lock", bindings=[slash, backslash])
        self.assertEqual(len(ledger.lock(scope="scope", receipt_id="receipt", operation_id="lock", bindings=[slash]).bindings), 1)

    def test_malformed_approval_fields_and_clock_do_not_escape_protocol_errors(self) -> None:
        for fields in ({"schema_version": True}, {"decision": []}, {"decision": {}},
                       {"input_refs": [object()]}, {"reviewed_actions": ["run", "run"]},
                       {"reviewer": {"mode": ""}}):
            with self.subTest(fields=fields), self.assertRaises(AuthorizationError):
                validate_approval(approval(**fields))
        ledger = ApprovalLedger()
        ledger.put(scope="scope", operation_id="put", expected_generation=0, record=approval())
        for now in (False, 0, "today", []):
            with self.subTest(now=now), self.assertRaisesRegex(AuthorizationError, "E_APPROVAL_TIME"):
                ledger.consume(scope="scope", action="run", input_refs=[ref("input")], now=now)
        with self.assertRaisesRegex(AuthorizationError, "E_CONSUME_BINDING"):
            ledger.consume_once(scope="scope", action="run", input_refs=None, operation_id="consume", expected_generation=1)
        with self.assertRaisesRegex(AuthorizationError, "E_LOCK_BINDINGS"):
            ledger.lock(scope="scope", receipt_id="receipt", operation_id="lock", bindings=None)

    def test_authorization_fingerprints_reject_non_strict_json_and_byte_subclasses(self) -> None:
        # json.dumps would otherwise coerce both tuple values and integer keys,
        # allowing a non-JSON Python value to obtain a valid authorization hash.
        for value in (("tuple",), {1: "integer-key"}, {"x": object()}):
            with self.subTest(value=repr(value)), self.assertRaises(AuthorizationError):
                canonical_bytes(value)
        class BytesSubclass(bytes):
            pass
        with self.assertRaisesRegex(AuthorizationError, "E_RESOURCE_BYTES"):
            sha256(BytesSubclass(b"payload"))
        self.assertEqual(sha256(b"payload"), sha256(b"payload"))

    def test_resource_refs_use_immutable_identity_and_portable_path_profile(self) -> None:
        for field, value in (("id", "latest"), ("id", "UPPER"), ("kind", "Not-a-kind"),
                             ("kind", "k" * 65), ("path", "fixtures/file\x7f.json"),
                             ("path", "fixtures/CON/file.json"), ("path", "fixtures/file\ud800.json")):
            bad = approval()
            bad["subject_ref"] = {**ref(), field: value}
            with self.subTest(field=field, value=repr(value)), self.assertRaises(AuthorizationError):
                validate_approval(bad)

    def test_approval_input_refs_have_bounded_nonempty_shape(self) -> None:
        with self.assertRaisesRegex(AuthorizationError, "E_APPROVAL_SCHEMA"):
            validate_approval({**approval(), "input_refs": []})
        with self.assertRaisesRegex(AuthorizationError, "E_APPROVAL_SCHEMA"):
            validate_approval({**approval(), "input_refs": [ref(str(index)) for index in range(1025)]})


if __name__ == "__main__":
    unittest.main()
