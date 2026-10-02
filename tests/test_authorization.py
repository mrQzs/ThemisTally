import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.authorization import ApprovalLedger, AuthorizationError, sha256, validate_approval, validate_authorization


def ref(name="task"):
    return {"kind": "contract", "id": name, "path": f"fixtures/{name}.json", "sha256": "a" * 64}


def approval(decision="APPROVED"):
    return {"record_type": "approval-record", "schema_version": 1, "approval_id": "a1", "request_id": "r1",
            "subject_ref": ref(), "input_refs": [ref("input")], "reviewed_actions": ["prepare", "run"],
            "decision": decision, "recorded_at": "2026-01-01T00:00:00Z", "reviewer": {"mode": "current_session"}}


class AuthorizationTests(unittest.TestCase):
    def test_record_is_closed_and_refs_are_lowercase(self):
        with self.assertRaisesRegex(AuthorizationError, "E_APPROVAL_UNKNOWN_FIELD"):
            validate_approval({**approval(), "fake": True})
        with self.assertRaisesRegex(AuthorizationError, "E_RESOURCE_HASH"):
            bad = approval(); bad["subject_ref"] = {**ref(), "sha256": "A" * 64}; validate_approval(bad)

    def test_cas_and_idempotency(self):
        ledger = ApprovalLedger(); head = ledger.put(scope="scope", operation_id="op1", expected_generation=0, record=approval())
        self.assertEqual(head.generation, 1)
        self.assertEqual(ledger.put(scope="scope", operation_id="op1", expected_generation=0, record=approval()), head)
        with self.assertRaisesRegex(AuthorizationError, "E_CAS_CONFLICT"):
            ledger.put(scope="scope", operation_id="op2", expected_generation=0, record=approval())
        with self.assertRaisesRegex(AuthorizationError, "E_IDEMPOTENCY_CONFLICT"):
            ledger.put(scope="scope", operation_id="op1", expected_generation=0, record=approval("REJECTED"))

    def test_revocation_does_not_restore_previous_approval(self):
        ledger = ApprovalLedger(); ledger.put(scope="scope", operation_id="op1", expected_generation=0, record=approval())
        revoked = ledger.revoke(scope="scope", operation_id="op2", expected_generation=1, reason="policy revoked")
        self.assertEqual(revoked.record["decision"], "REVOKED")
        self.assertFalse(ledger.consume(scope="scope", action="run", input_refs=[ref("input")]))
        self.assertEqual(len(ledger.history("scope")), 2)

    def test_input_and_action_binding_are_exact(self):
        ledger = ApprovalLedger(); ledger.put(scope="scope", operation_id="op1", expected_generation=0, record=approval())
        self.assertTrue(ledger.consume(scope="scope", action="run", input_refs=[ref("input")]))
        self.assertFalse(ledger.consume(scope="scope", action="publish", input_refs=[ref("input")]))
        self.assertFalse(ledger.consume(scope="scope", action="run", input_refs=[ref("other")]))

    def test_lock_captures_generation(self):
        ledger = ApprovalLedger(); ledger.put(scope="scope", operation_id="op1", expected_generation=0, record=approval())
        lock = ledger.lock(scope="scope", receipt_id="lock1", operation_id="lock-op", bindings=[ref("input")])
        self.assertEqual(lock.head_generation, 1)
        self.assertEqual(lock.bindings[0][1], 1)

    def test_strict_v2_authorization_requires_explicit_context(self):
        with self.assertRaisesRegex(AuthorizationError, "E_AUTHORIZATION_SCHEMA"):
            validate_authorization(approval())
        value = {**approval(), "purpose": "run approved checks", "authorization_refs": [ref("auth")],
                 "conditions": {"platform": "offline"}, "rationale": "reviewed fixture"}
        self.assertEqual(validate_authorization(value)["purpose"], "run approved checks")
        ledger = ApprovalLedger()
        with self.assertRaisesRegex(AuthorizationError, "E_AUTHORIZATION_SCHEMA"):
            ledger.put_authorization(scope="scope", operation_id="strict-1", expected_generation=0, record=approval())
        self.assertEqual(ledger.put_authorization(scope="scope", operation_id="strict-1", expected_generation=0,
                                                  record=value).generation, 1)

    def test_consume_once_is_idempotent_and_fenced(self):
        ledger = ApprovalLedger()
        ledger.put(scope="scope", operation_id="op1", expected_generation=0, record=approval())
        self.assertTrue(ledger.consume_once(scope="scope", action="run", input_refs=[ref("input")],
                                            operation_id="consume-1", expected_generation=1))
        self.assertTrue(ledger.consume_once(scope="scope", action="run", input_refs=[ref("input")],
                                            operation_id="consume-1", expected_generation=1))
        with self.assertRaisesRegex(AuthorizationError, "E_ALREADY_CONSUMED"):
            ledger.consume_once(scope="scope", action="run", input_refs=[ref("input")],
                                operation_id="consume-2", expected_generation=1)
        with self.assertRaisesRegex(AuthorizationError, "E_CAS_CONFLICT"):
            ledger.consume_once(scope="scope", action="run", input_refs=[ref("input")],
                                operation_id="consume-3", expected_generation=2)

    def test_currentness_binds_generation_hash_and_decision(self):
        ledger = ApprovalLedger()
        head = ledger.put(scope="scope", operation_id="op1", expected_generation=0, record=approval())
        self.assertEqual(ledger.assert_current(scope="scope", generation=1,
                                                record_sha256=head.record_sha256), head)
        with self.assertRaisesRegex(AuthorizationError, "E_CURRENTNESS"):
            ledger.assert_current(scope="scope", generation=1, record_sha256="b" * 64)
        ledger.revoke(scope="scope", operation_id="op2", expected_generation=1, reason="stop")
        with self.assertRaisesRegex(AuthorizationError, "E_CURRENTNESS"):
            ledger.assert_current(scope="scope", generation=2,
                                  record_sha256=ledger.head("scope").record_sha256)

    def test_consume_once_rejects_duplicate_input_refs(self):
        ledger = ApprovalLedger()
        ledger.put(scope="scope", operation_id="op1", expected_generation=0, record=approval())
        with self.assertRaisesRegex(AuthorizationError, "E_CONSUME_BINDING"):
            ledger.consume_once(scope="scope", action="run", input_refs=[ref("input"), ref("input")],
                                operation_id="consume-1", expected_generation=1)


if __name__ == "__main__":
    unittest.main()
