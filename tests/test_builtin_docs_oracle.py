import hashlib
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from codekit.builtin_artifacts import ArtifactError
from codekit.builtin_docs_oracle import CheckBinding, build_review_bundle, content_oracle, quality_issues, review_readiness

class DocsOracleTests(unittest.TestCase):
    def test_fixed_content_oracle_distinguishes_match_mismatch_and_drift(self):
        self.assertEqual(content_oracle(b"stable sentence", "stable sentence")["status"], "REVIEWED_SATISFIED")
        self.assertEqual(content_oracle(b"wrong", "stable sentence")["status"], "CONTENT_MISMATCH")
        self.assertEqual(content_oracle(b"stable sentence", "stable sentence", document_sha256="0" * 64)["status"], "UNKNOWN")
        with self.assertRaisesRegex(ArtifactError, "E_CONTENT_ENCODING"):
            content_oracle(b"stable", "stable", encoding=[])
        with self.assertRaisesRegex(ArtifactError, "E_CONTENT_ORACLE"):
            content_oracle(b"stable", "stable", document_sha256="bad")
        with self.assertRaisesRegex(ArtifactError, "E_CHECK_SET"):
            quality_issues({"check_id": "docs", "binding": {"candidate_sha256": "a" * 64, "check_set_sha256": "b" * 64, "environment_sha256": "c" * 64}, "source_kind": "core", "transport_complete": True, "exit_code": 0, "tests": {}}, {"docs\x80"})

    def test_readiness_requires_core_observations_and_content(self):
        binding = CheckBinding("a" * 64, "b" * 64, "c" * 64)
        observation = {"check_id": "docs", "binding": {"candidate_sha256": "a" * 64, "check_set_sha256": "b" * 64, "environment_sha256": "c" * 64}, "source_kind": "core_observation", "transport_complete": True, "exit_code": 0, "tests": {"docs": {"status": "PASSED"}}}
        ready = review_readiness(binding, [observation], {"docs"}, {"docs"}, "REVIEWED_SATISFIED", "SATISFIED")
        self.assertEqual(ready["status"], "READY_FOR_SUPERVISOR_DECISION")
        blocked = review_readiness(binding, [observation], {"docs"}, {"docs"}, "CONTENT_MISMATCH", "SATISFIED")
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertIn("E_CONTENT_REVIEW_REQUIRED", blocked["issues"])

    def test_bundle_never_promotes_to_pass(self):
        binding = CheckBinding("a" * 64, "b" * 64, "c" * 64)
        observation = {"check_id": "docs", "binding": {"candidate_sha256": "a" * 64, "check_set_sha256": "b" * 64, "environment_sha256": "c" * 64}, "source_kind": "core_observation", "transport_complete": True, "exit_code": 0, "tests": {"docs": {"status": "PASSED"}}}
        readiness = review_readiness(binding, [observation], {"docs"}, {"docs"}, "REVIEWED_SATISFIED", "SATISFIED")
        docs = {"record_type": "docs-check", "schema_version": 1, "artifact_id": "d", "producer": {"kind": "builtin-plugin", "id": "docs-checks", "version": "1.0.0"}, "status": "REFERENCE_ONLY", "source_refs": [], "candidate_ref": None, "environment_ref": None, "payload": {"profile": "commonmark-explicit-anchors-v1", "findings": [], "local_status": "SATISFIED", "unchecked": 0, "semantic_review": "NOT_PERFORMED", "parser": "fallback-commonmark-subset"}}
        bundle = build_review_bundle(docs_check=docs, content_review=content_oracle("ok", "ok"), observations=[observation], readiness=readiness)
        self.assertEqual(bundle["status"], "READY")
        self.assertNotEqual(bundle["status"], "PASS")

    def test_bundle_rejects_explicit_production_pass(self):
        binding = CheckBinding("a" * 64, "b" * 64, "c" * 64)
        observation = {"check_id": "docs", "binding": {"candidate_sha256": "a" * 64, "check_set_sha256": "b" * 64, "environment_sha256": "c" * 64}, "source_kind": "core_observation", "transport_complete": True, "exit_code": 0, "tests": {"docs": {"status": "PASSED"}}}
        readiness = review_readiness(binding, [observation], {"docs"}, {"docs"}, "REVIEWED_SATISFIED", "SATISFIED")
        docs = {"record_type": "docs-check", "schema_version": 1, "artifact_id": "d", "producer": {"kind": "builtin-plugin", "id": "docs-checks", "version": "1.0.0"}, "status": "REFERENCE_ONLY", "source_refs": [], "candidate_ref": None, "environment_ref": None, "payload": {"profile": "commonmark-explicit-anchors-v1", "findings": [], "local_status": "SATISFIED", "unchecked": 0, "semantic_review": "NOT_PERFORMED", "parser": "fallback-commonmark-subset"}}
        with self.assertRaisesRegex(ArtifactError, "E_REVIEW_PRODUCTION_GATE"):
            build_review_bundle(docs_check=docs, content_review=content_oracle("ok", "ok"), observations=[observation], readiness=readiness, status="PASS")

    def test_bundle_rejects_untyped_inputs(self):
        docs = {"record_type": "docs-check", "schema_version": 1, "artifact_id": "d", "producer": {"kind": "builtin-plugin", "id": "docs-checks", "version": "1.0.0"}, "status": "REFERENCE_ONLY", "source_refs": [], "candidate_ref": None, "environment_ref": None, "payload": {"profile": "commonmark-explicit-anchors-v1", "findings": [], "local_status": "SATISFIED", "unchecked": 0, "semantic_review": "NOT_PERFORMED", "parser": "fallback-commonmark-subset"}}
        readiness = {"status": "BLOCKED", "issues": []}
        for kwargs, error in (({"observations": None}, "E_REVIEW_INPUT"), ({"readiness": None}, "E_REVIEW_INPUT"), ({"status": []}, "E_REVIEW_INPUT")):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ArtifactError, error):
                build_review_bundle(docs_check=docs, content_review=content_oracle("ok", "ok"), observations=kwargs.get("observations", []), readiness=kwargs.get("readiness", readiness), **({"status": kwargs["status"]} if "status" in kwargs else {}))
        with self.assertRaisesRegex(ArtifactError, "E_REVIEW_INPUT"):
            build_review_bundle(docs_check=docs, content_review=content_oracle("ok", "ok"), observations=[], readiness={"status": [], "issues": []})

    def test_bundle_rejects_forged_ready_result(self):
        docs = {"record_type": "docs-check", "schema_version": 1, "artifact_id": "d", "producer": {"kind": "builtin-plugin", "id": "docs-checks", "version": "1.0.0"}, "status": "REFERENCE_ONLY", "source_refs": [], "candidate_ref": None, "environment_ref": None, "payload": {"profile": "commonmark-explicit-anchors-v1", "findings": [], "local_status": "SATISFIED", "unchecked": 0, "semantic_review": "NOT_PERFORMED", "parser": "fallback-commonmark-subset"}}
        forged = {"status": "READY_FOR_SUPERVISOR_DECISION", "issues": []}
        with self.assertRaisesRegex(ArtifactError, "E_REVIEW_BINDING"):
            build_review_bundle(docs_check=docs, content_review=content_oracle("wrong", "ok"), observations=[], readiness=forged)

    def test_quality_issues_rejects_malformed_observation_and_test_collections(self):
        valid = {"check_id": "docs", "binding": {"candidate_sha256": "a" * 64, "check_set_sha256": "b" * 64, "environment_sha256": "c" * 64}, "source_kind": "core_observation", "transport_complete": True, "exit_code": 0, "tests": {"docs": {"status": "PASSED"}}}
        for malformed in (None, [], {**valid, "check_id": []}, {**valid, "tests": {1: {"status": "PASSED"}}}, {**valid, "tests": {"docs": {"status": []}}}):
            with self.subTest(malformed=malformed), self.assertRaisesRegex(ArtifactError, "E_CHECK_"):
                quality_issues(malformed, {"docs"})
        with self.assertRaisesRegex(ArtifactError, "E_CHECK_SET"):
            quality_issues(valid, ["docs"])
        with self.assertRaisesRegex(ArtifactError, "E_CHECK_SET"):
            quality_issues(valid, {f"check-{index}" for index in range(1001)})

    def test_review_readiness_rejects_malformed_observation_and_collections(self):
        binding = CheckBinding("a" * 64, "b" * 64, "c" * 64)
        valid = {"check_id": "docs", "binding": {"candidate_sha256": "a" * 64, "check_set_sha256": "b" * 64, "environment_sha256": "c" * 64}, "source_kind": "core_observation", "transport_complete": True, "exit_code": 0, "tests": {"docs": {"status": "PASSED"}}}
        for observations in (None, "docs", [None], [{**valid, "binding": {}}]):
            with self.subTest(observations=observations), self.assertRaisesRegex(ArtifactError, "E_CHECK_"):
                review_readiness(binding, observations, {"docs"}, {"docs"}, "REVIEWED_SATISFIED", "SATISFIED")
        with self.assertRaisesRegex(ArtifactError, "E_CHECK_BINDING"):
            review_readiness(None, [valid], {"docs"}, {"docs"}, "REVIEWED_SATISFIED", "SATISFIED")
        with self.assertRaisesRegex(ArtifactError, "E_CHECK_SET"):
            review_readiness(binding, [valid], ["docs"], {"docs"}, "REVIEWED_SATISFIED", "SATISFIED")
        with self.assertRaisesRegex(ArtifactError, "E_CHECK_SET"):
            review_readiness(binding, [valid], {"docs"}, ["docs"], "REVIEWED_SATISFIED", "SATISFIED")
        with self.assertRaisesRegex(ArtifactError, "E_CHECK_OBSERVATION"):
            review_readiness(binding, [valid] * 1001, {"docs"}, {"docs"}, "REVIEWED_SATISFIED", "SATISFIED")

if __name__ == "__main__": unittest.main()
