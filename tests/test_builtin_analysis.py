import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.builtin_analysis import assert_analysis_current, build_analysis_report, validate_analysis_report
from codekit.builtin_artifacts import ArtifactError


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
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_PROVENANCE"):
            self.report_with(facts=[{"id": "f", "statement": "fact", "source_anchors": [{"ref": foreign, "start_byte": 0, "end_byte": 1, "excerpt_sha256": "b" * 64}]}])

    def test_builder_rejects_untyped_status_and_sources(self):
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_STATUS"):
            self.report_with(status=[])
        with self.assertRaisesRegex(ArtifactError, "E_ANALYSIS_SOURCE"):
            self.report_with(source_refs=None)


if __name__ == "__main__":
    unittest.main()
