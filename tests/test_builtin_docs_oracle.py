import hashlib
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from codekit.builtin_docs_oracle import CheckBinding, build_review_bundle, content_oracle, quality_issues, review_readiness

class DocsOracleTests(unittest.TestCase):
    def test_fixed_content_oracle_distinguishes_match_mismatch_and_drift(self):
        self.assertEqual(content_oracle(b"stable sentence", "stable sentence")["status"], "REVIEWED_SATISFIED")
        self.assertEqual(content_oracle(b"wrong", "stable sentence")["status"], "CONTENT_MISMATCH")
        self.assertEqual(content_oracle(b"stable sentence", "stable sentence", document_sha256="0" * 64)["status"], "UNKNOWN")

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
        docs = {"record_type": "docs-check", "schema_version": 1, "artifact_id": "d", "producer": {"kind": "builtin-plugin", "id": "docs-checks", "version": "1.0.0"}, "status": "PASS", "source_refs": [], "candidate_ref": None, "environment_ref": None, "payload": {"findings": []}}
        bundle = build_review_bundle(docs_check=docs, content_review=content_oracle("ok", "ok"), observations=[observation], readiness=readiness)
        self.assertEqual(bundle["status"], "READY")
        self.assertNotEqual(bundle["status"], "PASS")

if __name__ == "__main__": unittest.main()
