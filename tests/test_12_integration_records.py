"""Offline module 12 integration record and coverage boundaries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from codekit.integration_records import (  # noqa: E402
    CheckCatalog,
    CheckObservation,
    EvidenceManifest,
    IntegrationRecordError,
    IntegrationTarget,
    evaluate_coverage,
    make_delivery_decision,
    verify_manifest,
)


def ref(kind: str, ident: str, path: str, payload: bytes = b"fixture") -> dict[str, str]:
    return {"kind": kind, "id": ident, "path": path, "sha256": hashlib.sha256(payload).hexdigest()}


class RecordsFixture:
    def __init__(self) -> None:
        self.base = ref("git-tree", "base-1", "git/base", b"base")
        self.candidate = ref("candidate", "candidate-1", "candidate/tree", b"candidate")
        self.contract = ref("contract", "contract-1", "plans/one.json", b"contract")
        self.environment = ref("environment", "linux-1", "env/linux.json", b"linux")
        self.command = ref("command", "command-1", "checks/run.json", b"command")
        self.catalog = ref("check-catalog", "catalog-1", "integration/catalog.json", b"catalog")
        self.scope = ref("scope", "scope-1", "integration/scope.json", b"scope")
        self.stdout = ref("stdout", "stdout-1", "evidence/stdout.txt", b"stdout")
        self.target = IntegrationTarget(
            "integration-1", "repo-1", "request-1", self.base, self.candidate,
            (self.contract,), None, None, (), self.catalog, (), (self.environment,), (), (),
            {"core": "v1"}, self.scope,
        )
        self.case = {"case_id": "case-1", "requirement_id": "12-A01", "description": "offline check",
                     "target_ref": self.candidate, "environment_refs": [self.environment], "command_ref": self.command,
                     "expected": {"exit_code": 0}, "evidence_kinds": ["synthetic"], "required": True,
                     "reviewers": ["primary"], "timeout_seconds": 30}
        self.catalog_obj = CheckCatalog("catalog-1", self.candidate, (self.case,))
        self.manifest = EvidenceManifest("manifest-1", self.candidate,
                                         ({"ref": self.stdout, "size": len(b"stdout"), "purpose": "check output", "case_ids": ["case-1"]},))

    def observation(self, *, outcome: str = "PASS", observation_id: str = "obs-1", target=None,
                    expected_match=True, source_kind="synthetic", evidence=None) -> CheckObservation:
        return CheckObservation(observation_id, "attempt-1", "case-1", target or self.candidate, self.command,
                                0, None, self.stdout, None, "VALID", "COMPLETE", self.environment,
                                expected_match, outcome, None if outcome == "PASS" else "expected failure",
                                source_kind, (self.stdout,) if evidence is None else evidence)


class IntegrationTargetTests(unittest.TestCase):
    def test_round_trip_and_target_digest_are_stable(self) -> None:
        fx = RecordsFixture()
        value = fx.target.to_mapping()
        self.assertEqual(IntegrationTarget.from_mapping(value).target_sha256, fx.target.target_sha256)
        self.assertNotIn("target_sha256", value)  # no self-referential digest field

    def test_cross_candidate_target_composition_is_rejected(self) -> None:
        fx = RecordsFixture()
        other = dict(fx.target.to_mapping())
        other["candidate_ref"] = ref("candidate", "candidate-2", "candidate/tree-2", b"different")
        with self.assertRaisesRegex(IntegrationRecordError, "E_TARGET_CANDIDATE_MISMATCH"):
            from codekit.integration_records import ensure_same_candidate
            ensure_same_candidate([fx.target, IntegrationTarget.from_mapping(other)])


class ManifestAndCoverageTests(unittest.TestCase):
    def test_manifest_requires_exact_expected_members_and_bytes(self) -> None:
        fx = RecordsFixture()
        self.assertEqual(len(verify_manifest(fx.manifest, [fx.stdout], {fx.stdout["path"]: b"stdout"})), 1)
        with self.assertRaisesRegex(IntegrationRecordError, "E_EXPECTED"):
            verify_manifest(fx.manifest, [], {fx.stdout["path"]: b"stdout"})
        with self.assertRaisesRegex(IntegrationRecordError, "E_RESOURCE_HASH"):
            verify_manifest(fx.manifest, [fx.stdout], {fx.stdout["path"]: b"changed"})

    def test_coverage_uses_trusted_denominator_and_missing_case_is_not_run(self) -> None:
        fx = RecordsFixture()
        report = evaluate_coverage(fx.target, fx.catalog_obj, [], manifest=fx.manifest)
        self.assertEqual(report.required_total, 1)
        self.assertEqual(report.required_passed, 0)
        self.assertEqual(report.evidence_readiness, "NONE")
        self.assertEqual(report.cases[0]["status"], "NOT_RUN")

    def test_later_pass_does_not_hide_unresolved_failure(self) -> None:
        fx = RecordsFixture()
        failed = fx.observation(outcome="FAIL", observation_id="obs-fail")
        passed = fx.observation(outcome="PASS", observation_id="obs-pass")
        report = evaluate_coverage(fx.target, fx.catalog_obj, [failed, passed], manifest=fx.manifest,
                                   selected_attempts={"case-1": "obs-pass"})
        self.assertEqual(report.cases[0]["status"], "UNRESOLVED_FAILURE")
        self.assertEqual(report.evidence_readiness, "NONE")
        resolved = evaluate_coverage(fx.target, fx.catalog_obj, [failed, passed], manifest=fx.manifest,
                                     selected_attempts={"case-1": "obs-pass"}, resolved_failures={"obs-fail"})
        self.assertEqual(resolved.evidence_readiness, "COMPLETE")

    def test_same_observation_id_with_different_bytes_is_blocked(self) -> None:
        fx = RecordsFixture()
        first = fx.observation()
        second = fx.observation(observation_id="obs-1", outcome="FAIL")
        with self.assertRaisesRegex(IntegrationRecordError, "E_OBSERVATION_CONFLICT"):
            evaluate_coverage(fx.target, fx.catalog_obj, [first, second], manifest=fx.manifest)

    def test_stale_target_and_nonaccepted_source_do_not_pass(self) -> None:
        fx = RecordsFixture()
        stale = fx.observation(target=ref("candidate", "candidate-other", "candidate/other", b"other"))
        report = evaluate_coverage(fx.target, fx.catalog_obj, [stale], manifest=fx.manifest)
        self.assertEqual(report.cases[0]["status"], "STALE")
        unsupported = fx.observation(source_kind="captured")
        report = evaluate_coverage(fx.target, fx.catalog_obj, [unsupported], manifest=fx.manifest)
        self.assertEqual(report.cases[0]["status"], "INSUFFICIENT_EVIDENCE")

    def test_waived_case_is_recorded_as_exception_and_never_pass(self) -> None:
        fx = RecordsFixture()
        waived = fx.observation(outcome="WAIVED")
        report = evaluate_coverage(fx.target, fx.catalog_obj, [waived], manifest=fx.manifest)
        self.assertEqual(report.cases[0]["status"], "NOT_RUN")
        self.assertEqual(report.exceptions[0]["case_id"], "case-1")
        self.assertEqual(report.evidence_readiness, "NONE")

    def test_selected_attempt_must_match_case_and_environment(self) -> None:
        fx = RecordsFixture()
        other_case = dict(fx.case, case_id="case-2")
        catalog = CheckCatalog("catalog-1", fx.candidate, (fx.case, other_case))
        obs = fx.observation()
        report = evaluate_coverage(fx.target, catalog, [obs], manifest=fx.manifest,
                                   selected_attempts={"case-2": "obs-1"})
        self.assertEqual(report.cases[1]["status"], "INCOMPLETE")
        other_environment = ref("environment", "windows-1", "env/windows.json", b"windows")
        stale = fx.observation()
        stale = CheckObservation(stale.observation_id, stale.attempt_id, stale.case_id, stale.target_ref,
                                 stale.command_ref, stale.exit_code, stale.signal, stale.stdout_ref,
                                 stale.stderr_ref, stale.protocol_status, stale.collection_status,
                                 other_environment, stale.expected_match, stale.outcome, stale.failure_reason,
                                 stale.source_kind, stale.evidence_refs)
        report = evaluate_coverage(fx.target, fx.catalog_obj, [stale], manifest=fx.manifest)
        self.assertEqual(report.cases[0]["status"], "STALE_ENVIRONMENT")


class DeliveryDecisionTests(unittest.TestCase):
    def test_delivery_is_separate_from_execution_and_integration_authority(self) -> None:
        fx = RecordsFixture()
        report = evaluate_coverage(fx.target, fx.catalog_obj, [fx.observation()], manifest=fx.manifest)
        decision = make_delivery_decision(report, coverage_ref=fx.manifest.target_ref, scope={"offline": True}, accepted=True)
        self.assertEqual(decision.decision, "FULL")
        self.assertFalse(decision.dispatch_authorized)
        self.assertFalse(decision.integration_authorized)
        self.assertEqual(decision.to_mapping()["dispatch_authorized"], False)

    def test_incomplete_evidence_cannot_be_called_full(self) -> None:
        fx = RecordsFixture()
        report = evaluate_coverage(fx.target, fx.catalog_obj, [], manifest=fx.manifest)
        decision = make_delivery_decision(report, coverage_ref=fx.manifest.target_ref, scope={"offline": True}, accepted=True)
        self.assertEqual(decision.decision, "BLOCKED")


class SchemaFixtureTests(unittest.TestCase):
    def test_generated_records_are_json_serializable_and_schema_has_expected_families(self) -> None:
        fx = RecordsFixture()
        report = evaluate_coverage(fx.target, fx.catalog_obj, [fx.observation()], manifest=fx.manifest)
        decision = make_delivery_decision(report, coverage_ref=fx.manifest.target_ref, scope={"offline": True}, accepted=True)
        values = [fx.target.to_mapping(), fx.catalog_obj.to_mapping(), fx.observation().to_mapping(),
                  fx.manifest.to_mapping(), report.to_mapping(), decision.to_mapping()]
        for value in values:
            json.dumps(value, ensure_ascii=False, sort_keys=True)
        schema = json.loads((ROOT / "schemas" / "integration-records-v1.schema.json").read_text(encoding="utf-8"))
        refs = {item["$ref"] for item in schema["oneOf"]}
        self.assertEqual(len(refs), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
