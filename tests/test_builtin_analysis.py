import copy
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.builtin_analysis import assert_analysis_current, build_analysis_report, validate_analysis_report
from codekit.builtin_artifacts import ArtifactError, resource_ref_key


def ref(name="source"):
    return {"kind": "file", "id": name, "path": f"src/{name}.py", "sha256": "a" * 64}


class AnalysisTests(unittest.TestCase):
    def report(self):
        return build_analysis_report(
            artifact_id="analysis-1", producer={"kind": "builtin-plugin", "id": "repo-analysis", "version": "1.0.0"},
            source_refs=[ref()], candidate_ref=ref("candidate"), environment_ref=ref("environment"),
            facts=[{"id": "fact-1", "statement": "module exists", "confidence": "high"}],
            inferences=[{"id": "infer-1", "statement": "module is reachable", "reason": "fact-1"}],
            assumptions=[{"id": "assume-1", "statement": "working tree is fixed"}],
            questions=[{"id": "question-1", "statement": "is provider available?"}],
        )

    def test_report_is_closed_and_currentness_is_bound(self):
        report = self.report()
        self.assertEqual(validate_analysis_report(report)["payload"]["facts"][0]["id"], "fact-1")
        assert_analysis_current(report, candidate_ref=ref("candidate"), source_refs=[ref()], environment_ref=ref("environment"))
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_DRIFT"):
            assert_analysis_current(report, candidate_ref=ref("other"), source_refs=[ref()], environment_ref=ref("environment"))

    def test_synthetic_evidence_cannot_claim_ready_or_production(self):
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_STATUS"):
            self.report_with(status="READY")
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_EVIDENCE"):
            self.report_with(evidence_class="PRODUCTION")

    def report_with(self, **kwargs):
        args = {"artifact_id": "analysis-1", "producer": {"kind": "builtin-plugin", "id": "repo-analysis", "version": "1.0.0"},
                "source_refs": [ref()], "candidate_ref": ref("candidate"), "environment_ref": ref("environment"),
                "facts": [{"id": "f", "statement": "fact"}]}
        args.update(kwargs)
        return build_analysis_report(**args)

    def test_duplicate_items_and_bad_anchor_rejected(self):
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_DUPLICATE"):
            self.report_with(facts=[{"id": "f", "statement": "one"}, {"id": "f", "statement": "two"}])
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_SOURCE"):
            self.report_with(facts=[{"id": "f", "statement": "bad", "source_anchors": [{"ref": ref(), "start_byte": 2, "end_byte": 2, "excerpt_sha256": "b" * 64}]}])

    def test_anchor_must_be_declared_by_source_refs(self):
        foreign = ref("foreign")
        report = self.report_with(facts=[{"id": "f", "statement": "fact"}])
        report["payload"]["facts"][0]["source_anchors"] = [{"ref": foreign, "start_byte": 0,
                                                               "end_byte": 1, "excerpt_sha256": "b" * 64}]
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_PROVENANCE"):
            validate_analysis_report(report)

    def test_builder_rejects_untyped_status_and_sources(self):
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_STATUS"):
            self.report_with(status=[])
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_SOURCE"):
            self.report_with(source_refs=None)

    def test_validator_rejects_untyped_payload_enums(self):
        report = self.report()
        forged = copy.deepcopy(report)
        forged["payload"]["analysis_mode"] = []
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_MODE"):
            validate_analysis_report(forged)
        forged = copy.deepcopy(report)
        forged["payload"]["evidence_class"] = []
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_EVIDENCE"):
            validate_analysis_report(forged)

    def test_validator_rechecks_ready_evidence_boundary(self):
        # A replayed/edited envelope must not bypass the builder's synthetic
        # evidence guard by calling the validator directly.
        forged = copy.deepcopy(self.report_with())
        forged["status"] = "READY"
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_STATUS"):
            validate_analysis_report(forged)

    def test_builder_binds_anchors_to_frozen_source_bytes(self):
        source = b"abcdef"
        frozen_ref = {"kind": "file", "id": "frozen", "path": "src/frozen.py",
                      "sha256": hashlib.sha256(source).hexdigest()}
        anchor = {"ref": frozen_ref, "start_byte": 1, "end_byte": 4,
                  "excerpt_sha256": hashlib.sha256(source[1:4]).hexdigest()}
        report = self.report_with(
            source_refs=[frozen_ref],
            facts=[{"id": "f", "statement": "fact", "source_anchors": [anchor]}],
            source_bytes_by_ref={resource_ref_key(frozen_ref): source},
        )
        self.assertEqual(report["payload"]["facts"][0]["source_anchors"][0]["end_byte"], 4)
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_SOURCE"):
            self.report_with(
                source_refs=[frozen_ref],
                facts=[{"id": "f", "statement": "fact", "source_anchors": [anchor]}],
                source_bytes_by_ref={resource_ref_key(frozen_ref): b"changed"},
            )
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_SOURCE"):
            self.report_with(
                source_refs=[frozen_ref],
                facts=[{"id": "f", "statement": "fact", "source_anchors": [anchor]}],
                source_bytes_by_ref={},
            )
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_SOURCE"):
            self.report_with(
                source_refs=[frozen_ref],
                facts=[{"id": "f", "statement": "fact", "source_anchors": [anchor]}],
            )


if __name__ == "__main__":
    unittest.main()
