"""07-A13/A26/F28 immutable acceptance provenance tests."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.acceptance import (BindingDecision, resolve_input_binding, resolve_input_bindings,
                                validate_accepted_result, validate_acceptance_revocation,
                                validate_input_binding_receipt)
from codekit.protocols import ProtocolError


REQUEST = "req-" + "a" * 32
HASHES = {
    "candidate": "a" * 64, "checks": "b" * 64, "output": "c" * 64,
    "schema": "d" * 64, "verdict": "e" * 64,
}


def ref(kind: str, identity: str, digest: str, path: str) -> dict[str, str]:
    return {"kind": kind, "id": identity, "sha256": digest, "path": path}


def accepted(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "record_type": "accepted-result", "schema_version": 1,
        "acceptance_id": "accept-a", "request_id": REQUEST, "task_id": "source-a",
        "plan_version": 3, "guard_version": 7,
        "candidate_ref": ref("candidate", "candidate-3", HASHES["candidate"], "candidate.json"),
        "check_set_ref": ref("check-set", "checks-3", HASHES["checks"], "checks.json"),
        "verdict_ref": ref("verdict", "verdict-3", HASHES["verdict"], "verdict.json"),
        "output_refs": {"result": ref("artifact", "result-3", HASHES["output"], "out/result.json")},
        "target_schema_refs": {"result": ref("schema", "schema-1", HASHES["schema"], "schemas/result.json")},
        "upstream_acceptance_ids": [],
    }
    value.update(changes)
    return value


def receipt(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "record_type": "input-binding-receipt", "schema_version": 1,
        "request_id": REQUEST, "task_id": "consumer-a", "plan_version": 4,
        "source_plan_version": 3, "guard_version": 7, "source_guard_version": 7,
        "source_task_id": "source-a", "source_port": "result",
        "upstream_acceptance_id": "accept-a",
        "candidate_ref": ref("candidate", "candidate-3", HASHES["candidate"], "candidate.json"),
        "output_ref": ref("artifact", "result-3", HASHES["output"], "out/result.json"),
        "target_schema_ref": ref("schema", "schema-1", HASHES["schema"], "schemas/result.json"),
        "check_set_ref": ref("check-set", "checks-3", HASHES["checks"], "checks.json"),
    }
    value.update(changes)
    return value


def revocation(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "record_type": "acceptance-revocation", "schema_version": 1,
        "revocation_id": "revoke-a", "acceptance_id": "accept-a",
        "reason": "candidate_changed", "guard_version": 8, "evidence_ref": "evidence-a",
    }
    value.update(changes)
    return value


class AcceptanceTests(unittest.TestCase):
    def test_valid_fixed_binding_resolves_across_plan_versions(self) -> None:
        result = validate_accepted_result(accepted())
        bound = validate_input_binding_receipt(receipt())
        self.assertEqual(resolve_input_binding(bound, [result], expected_request_id=REQUEST,
                                               expected_task_id="consumer-a", expected_plan_version=4,
                                               expected_guard_version=7),
                         BindingDecision("BOUND", (), "accept-a"))
        self.assertEqual(result.record["plan_version"], 3)
        with self.assertRaises(TypeError):
            result.record["candidate_ref"] = {}  # type: ignore[index]

    def test_latest_alias_and_unknown_fields_are_rejected(self) -> None:
        bad = accepted(candidate_ref=ref("candidate", "latest", HASHES["candidate"], "candidate.json"))
        with self.assertRaises(ProtocolError) as caught:
            validate_accepted_result(bad)
        self.assertEqual(caught.exception.code, "E_SCHEMA_FIELDS")
        unknown = copy.deepcopy(accepted())
        unknown["extra"] = True
        with self.assertRaises(ProtocolError):
            validate_accepted_result(unknown)

    def test_candidate_output_schema_and_check_set_are_each_bound(self) -> None:
        result = validate_accepted_result(accepted())
        for field, changed in (
            ("candidate_ref", ref("candidate", "candidate-4", HASHES["candidate"], "candidate.json")),
            ("output_ref", ref("artifact", "result-4", HASHES["output"], "out/result.json")),
            ("target_schema_ref", ref("schema", "schema-2", HASHES["schema"], "schemas/result.json")),
            ("check_set_ref", ref("check-set", "checks-4", HASHES["checks"], "checks.json")),
        ):
            candidate = receipt(**{field: changed})
            decision = resolve_input_binding(candidate, [result], expected_request_id=REQUEST,
                                             expected_task_id="consumer-a", expected_plan_version=4,
                                             expected_guard_version=7)
            self.assertEqual(decision.decision, "BLOCK", field)

    def test_missing_port_or_acceptance_is_blocked(self) -> None:
        result = validate_accepted_result(accepted())
        missing = resolve_input_binding(receipt(upstream_acceptance_id="accept-missing"), [result],
                                         expected_request_id=REQUEST, expected_task_id="consumer-a",
                                         expected_plan_version=4, expected_guard_version=7)
        self.assertEqual(missing.reasons, ("ACCEPTANCE_UNKNOWN",))
        no_port = resolve_input_binding(receipt(source_port="other"), [result],
                                         expected_request_id=REQUEST, expected_task_id="consumer-a",
                                         expected_plan_version=4, expected_guard_version=7)
        self.assertEqual(no_port.reasons, ("OUTPUT_PORT_UNKNOWN",))

    def test_guard_and_current_target_are_rechecked(self) -> None:
        result = validate_accepted_result(accepted())
        for kwargs, reason in (
            ({"guard_version": 6}, "TARGET_BINDING_MISMATCH"),
            ({"source_guard_version": 6}, "SOURCE_GUARD_MISMATCH"),
        ):
            decision = resolve_input_binding(receipt(**kwargs), [result], expected_request_id=REQUEST,
                                             expected_task_id="consumer-a", expected_plan_version=4,
                                             expected_guard_version=7)
            self.assertEqual(decision.reasons, (reason,))

    def test_revocation_is_append_only_and_blocks_downstream(self) -> None:
        result = validate_accepted_result(accepted())
        revoke = validate_acceptance_revocation(revocation())
        decision = resolve_input_binding(receipt(), [result], [revoke], expected_request_id=REQUEST,
                                         expected_task_id="consumer-a", expected_plan_version=4,
                                         expected_guard_version=7)
        self.assertEqual(decision.reasons, ("ACCEPTANCE_REVOKED",))
        self.assertEqual(result.record["acceptance_id"], "accept-a")
        with self.assertRaises(ProtocolError):
            validate_acceptance_revocation({**revocation(), "record_type": "accepted-result"})

    def test_multi_upstream_closure_blocks_if_any_upstream_is_revoked(self) -> None:
        upstream = accepted(acceptance_id="accept-upstream")
        merged = accepted(acceptance_id="accept-merge", task_id="merge-a",
                          upstream_acceptance_ids=["accept-upstream"])
        bound = receipt(upstream_acceptance_id="accept-merge", source_task_id="merge-a",
                        source_plan_version=3,
                        candidate_ref=merged["candidate_ref"], output_ref=merged["output_refs"]["result"],
                        target_schema_ref=merged["target_schema_refs"]["result"], check_set_ref=merged["check_set_ref"])
        decision = resolve_input_binding(bound, [validate_accepted_result(merged), validate_accepted_result(upstream)],
                                         [validate_acceptance_revocation( revocation(acceptance_id="accept-upstream"))],
                                         expected_request_id=REQUEST, expected_task_id="consumer-a",
                                         expected_plan_version=4, expected_guard_version=7)
        self.assertEqual(decision.reasons, ("ACCEPTANCE_REVOKED",))

    def test_all_inputs_must_be_bound(self) -> None:
        result = validate_accepted_result(accepted())
        decisions = resolve_input_bindings([receipt(), receipt(upstream_acceptance_id="missing")], [result],
                                           expected_request_id=REQUEST, expected_task_id="consumer-a",
                                           expected_plan_version=4, expected_guard_version=7)
        self.assertEqual(tuple(item.decision for item in decisions), ("BOUND", "BLOCK"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
