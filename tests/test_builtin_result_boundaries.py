"""Deterministic boundary tests for the offline regression/mutation reducers."""

from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.builtin_artifacts import ArtifactError
from codekit.builtin_mutation import (
    build_mutation_artifact,
    build_mutation_plan,
    reduce_mutation_results,
    validate_mutation_artifact,
)
from codekit.builtin_regression import (
    build_regression_artifact,
    collect_targets,
    summarize_results,
    validate_regression_artifact,
)


def artifact_arguments() -> dict:
    def ref(kind: str) -> dict:
        return {"kind": kind, "id": kind, "path": f"fixtures/{kind}.json", "sha256": "a" * 64}

    return {
        "artifact_id": "result-boundary-fixture",
        "producer": {"kind": "deterministic_check", "id": "offline-fixture", "version": "1"},
        "candidate_ref": ref("candidate"),
        "environment_ref": ref("environment"),
        "source_refs": [ref("source")],
    }


def mutation_plan() -> dict:
    return build_mutation_plan(
        [
            {"id": "m2", "path": "src/b.py", "description": "invert comparison"},
            {"id": "m1", "path": "src/a.py", "description": "remove guard"},
        ],
        baseline_id="known-good",
    )


def regression_plan() -> dict:
    return collect_targets(
        {"targets": ["test_skip", "test_xfail", "test_run"], "skip": ["test_skip"], "xfail": ["test_xfail"]}
    )


def regression_results() -> list:
    return [
        {"target": "test_skip", "status": "SKIP"},
        {"target": "test_xfail", "status": "XFAIL"},
        {"target": "test_run", "status": "PASS"},
    ]


class MutationResultBoundaries(unittest.TestCase):
    def test_valid_plan_and_complete_killed_mutations_produce_reference_artifact(self) -> None:
        plan = mutation_plan()
        before = copy.deepcopy(plan)
        summary = reduce_mutation_results(
            plan, "PASS", [{"id": "m2", "status": "FAIL"}, {"id": "m1", "status": "FAIL"}]
        )
        self.assertEqual(plan, before)
        self.assertEqual(summary, {
            "outcome": "PASS", "baseline_status": "PASS",
            "results": {"m1": "FAIL", "m2": "FAIL"}, "surviving": [], "unavailable": [],
        })
        artifact = build_mutation_artifact(**artifact_arguments(), plan=plan, summary=summary)
        self.assertEqual(artifact["status"], "REFERENCE_ONLY")
        self.assertEqual(artifact["payload"], {"plan": plan, "summary": summary})

    def test_baseline_failure_survivor_and_missing_results_are_not_pass(self) -> None:
        plan = mutation_plan()
        cases = (
            ("FAIL", [{"id": "m1", "status": "FAIL"}, {"id": "m2", "status": "FAIL"}], "FAIL"),
            ("NOT_RUN", [{"id": "m1", "status": "FAIL"}, {"id": "m2", "status": "FAIL"}], "BLOCKED"),
            ("PASS", [{"id": "m1", "status": "PASS"}, {"id": "m2", "status": "FAIL"}], "FAIL"),
            ("PASS", [{"id": "m1", "status": "FAIL"}], "NOT_RUN"),
            ("PASS", [{"id": "m1", "status": "BLOCKED"}, {"id": "m2", "status": "FAIL"}], "BLOCKED"),
        )
        for baseline, results, expected in cases:
            with self.subTest(baseline=baseline, results=results):
                summary = reduce_mutation_results(plan, baseline, results)
                self.assertEqual(summary["outcome"], expected)
                artifact = build_mutation_artifact(**artifact_arguments(), plan=plan, summary=summary)
                self.assertEqual(artifact["status"], expected)

    def test_reducer_revalidates_handwritten_mutation_rows(self) -> None:
        base = mutation_plan()
        invalid = [
            {**base, "mutations": []},
            {**base, "baseline_id": ""},
            {**base, "mutations": [base["mutations"][0], base["mutations"][0]]},
            {**base, "mutations": [None]},
            {**base, "mutations": [{"id": "m1", "path": "src/a.py"}]},
            {**base, "mutations": [{"id": [], "path": "src/a.py", "description": "bad id"}]},
            {**base, "mutations": [{**base["mutations"][0], "extra": True}]},
        ]
        for plan in invalid:
            with self.subTest(plan=plan):
                with self.assertRaises(ArtifactError) as caught:
                    reduce_mutation_results(plan, "PASS", [])
                self.assertEqual(caught.exception.code, "E_MUTATION_PLAN")

    def test_reducer_rejects_unsafe_paths_in_handwritten_plan(self) -> None:
        for path in (
            "/outside.py", "C:/outside.py", "C:relative.py", "\\\\server\\share\\outside.py",
            "../outside.py", "src/../outside.py", "src/./a.py", "src//a.py", "src/a\x00.py",
        ):
            plan = mutation_plan()
            plan["mutations"][0]["path"] = path
            with self.subTest(path=path):
                with self.assertRaises(ArtifactError) as caught:
                    reduce_mutation_results(plan, "PASS", [])
                self.assertEqual(caught.exception.code, "E_MUTATION_PLAN")

    def test_mutation_paths_are_canonicalized_before_hashing(self) -> None:
        plan = build_mutation_plan(
            [{"id": "m1", "path": "src\\a.py", "description": "remove guard"}],
            baseline_id="known-good",
        )
        self.assertEqual(plan["mutations"][0]["path"], "src/a.py")

    def test_duplicate_result_is_rejected_instead_of_best_of(self) -> None:
        with self.assertRaises(ArtifactError) as caught:
            reduce_mutation_results(mutation_plan(), "PASS", [
                {"id": "m1", "status": "PASS"}, {"id": "m1", "status": "FAIL"},
            ])
        self.assertEqual(caught.exception.code, "E_MUTATION_RESULT")

    def test_artifact_rejects_forged_mutation_outcome_or_derived_details(self) -> None:
        plan = mutation_plan()
        summary = reduce_mutation_results(plan, "PASS", [
            {"id": "m1", "status": "PASS"}, {"id": "m2", "status": "NOT_RUN"},
        ])
        mutations = (
            {"outcome": "PASS"}, {"surviving": []}, {"unavailable": []},
            {"results": {"m1": "FAIL", "m2": "FAIL"}}, {"extra": "unreviewed"},
        )
        for changed in mutations:
            forged = {**copy.deepcopy(summary), **changed}
            with self.subTest(changed=changed), self.assertRaises(ArtifactError):
                build_mutation_artifact(**artifact_arguments(), plan=plan, summary=forged)

    def test_artifact_rejects_malformed_mutation_summary(self) -> None:
        for summary in ({}, {"outcome": "PASS"}, {"outcome": "PASS", "results": []}):
            with self.subTest(summary=summary), self.assertRaises(ArtifactError):
                build_mutation_artifact(**artifact_arguments(), plan=mutation_plan(), summary=summary)

    def test_persisted_mutation_artifact_replays_plan_and_status(self) -> None:
        plan = mutation_plan()
        summary = reduce_mutation_results(plan, "PASS", [
            {"id": "m1", "status": "FAIL"}, {"id": "m2", "status": "FAIL"},
        ])
        artifact = build_mutation_artifact(**artifact_arguments(), plan=plan, summary=summary)
        self.assertEqual(validate_mutation_artifact(artifact)["status"], "REFERENCE_ONLY")
        forged = copy.deepcopy(artifact)
        forged["payload"]["summary"]["outcome"] = "FAIL"
        with self.assertRaisesRegex(ArtifactError, "E_MUTATION_RESULT"):
            validate_mutation_artifact(forged)
        forged = copy.deepcopy(artifact)
        forged["status"] = "PASS"
        with self.assertRaisesRegex(ArtifactError, "E_MUTATION_STATUS"):
            validate_mutation_artifact(forged)


class RegressionResultBoundaries(unittest.TestCase):
    def test_valid_selection_and_outcomes_produce_reference_artifact(self) -> None:
        plan = regression_plan()
        self.assertEqual(plan["selected"], ["test_run"])
        summary = summarize_results(plan, regression_results())
        self.assertEqual(summary["outcome"], "PASS")
        self.assertEqual(summary["missing_results"], [])
        self.assertEqual(summary["bad_xfail"], [])
        artifact = build_regression_artifact(**artifact_arguments(), plan=plan, summary=summary)
        self.assertEqual(artifact["status"], "REFERENCE_ONLY")
        self.assertEqual(artifact["payload"], {"plan": plan, "summary": summary})

    def test_duplicate_targets_skip_xfail_and_overlap_are_rejected(self) -> None:
        for spec in (
            {"targets": ["a", "a"]},
            {"targets": ["a"], "skip": ["a", "a"]},
            {"targets": ["a"], "xfail": ["a", "a"]},
            {"targets": ["a"], "skip": ["a"], "xfail": ["a"]},
        ):
            with self.subTest(spec=spec):
                with self.assertRaises(ArtifactError) as caught:
                    collect_targets(spec)
                self.assertEqual(caught.exception.code, "E_REGRESSION_SPEC")

    def test_zero_tests_and_unavailable_inventory_remain_not_run(self) -> None:
        empty = collect_targets({"targets": []})
        self.assertEqual(summarize_results(empty, [])["outcome"], "NOT_RUN")
        plan = collect_targets({"targets": ["available", "missing"]}, available=["available"])
        self.assertEqual(plan["missing"], ["missing"])
        summary = summarize_results(plan, [
            {"target": "available", "status": "PASS"}, {"target": "missing", "status": "NOT_RUN"},
        ])
        self.assertEqual(summary["outcome"], "NOT_RUN")

    def test_reducer_rejects_tampered_handwritten_plan(self) -> None:
        replacements = (
            {"selected": []}, {"selected": ["test_run", "test_skip"]},
            {"selected": ["test_run", "test_run"]}, {"selected": ["unknown"]},
            {"zero_tests": True}, {"zero_tests": 0},
            {"targets": ["test_run", "test_run", "test_skip", "test_xfail"]},
            {"skipped": ["test_skip", "test_xfail"]},
            {"expected_failures": ["unknown"]},
            {"skipped": ["test_skip", "test_skip"]},
            {"expected_failures": ["test_xfail", "test_xfail"]},
            {"missing": ["test_run", "test_run"]},
            {"missing": [[]]},
            {"missing": ["unknown"]}, {"missing": ["test_skip"]},
            {"missing": ["test_run", "test_run"]}, {"missing": "test_run"},
        )
        for changed in replacements:
            plan = {**regression_plan(), **changed}
            with self.subTest(changed=changed):
                with self.assertRaises(ArtifactError) as caught:
                    summarize_results(plan, regression_results())
                self.assertEqual(caught.exception.code, "E_REGRESSION_PLAN")

    def test_skip_target_cannot_report_pass_or_xfail(self) -> None:
        for status in ("PASS", "XFAIL"):
            results = regression_results()
            results[0]["status"] = status
            with self.subTest(status=status):
                self.assertEqual(summarize_results(regression_plan(), results)["outcome"], "FAIL")

    def test_xfail_target_cannot_report_skip_or_pass(self) -> None:
        for status in ("SKIP", "PASS"):
            results = regression_results()
            results[1]["status"] = status
            with self.subTest(status=status):
                summary = summarize_results(regression_plan(), results)
                self.assertEqual(summary["outcome"], "FAIL")
                self.assertIn("test_xfail", summary["bad_xfail"])

    def test_duplicate_result_cannot_replace_failure_with_pass(self) -> None:
        plan = collect_targets({"targets": ["test_run"]})
        with self.assertRaises(ArtifactError) as caught:
            summarize_results(plan, [
                {"target": "test_run", "status": "FAIL"}, {"target": "test_run", "status": "PASS"},
            ])
        self.assertEqual(caught.exception.code, "E_REGRESSION_RESULT")

    def test_artifact_rejects_forged_regression_outcome_or_derived_details(self) -> None:
        plan = regression_plan()
        results = regression_results()
        results[2]["status"] = "FAIL"
        summary = summarize_results(plan, results)
        for changed in (
            {"outcome": "PASS"}, {"failures": []}, {"missing_results": ["test_run"]},
            {"blocked": ["test_run"]}, {"unexpected_pass": ["test_xfail"]},
            {"results": {"test_run": "PASS", "test_skip": "SKIP", "test_xfail": "XFAIL"}},
            {"extra": "unreviewed"},
        ):
            forged = {**copy.deepcopy(summary), **changed}
            with self.subTest(changed=changed), self.assertRaises(ArtifactError):
                build_regression_artifact(**artifact_arguments(), plan=plan, summary=forged)

    def test_artifact_rejects_malformed_regression_summary(self) -> None:
        for summary in ({}, {"outcome": "PASS"}, {"outcome": "PASS", "results": []}):
            with self.subTest(summary=summary), self.assertRaises(ArtifactError):
                build_regression_artifact(**artifact_arguments(), plan=regression_plan(), summary=summary)

    def test_persisted_regression_artifact_replays_plan_and_status(self) -> None:
        plan = regression_plan()
        summary = summarize_results(plan, regression_results())
        artifact = build_regression_artifact(**artifact_arguments(), plan=plan, summary=summary)
        self.assertEqual(validate_regression_artifact(artifact)["status"], "REFERENCE_ONLY")
        forged = copy.deepcopy(artifact)
        forged["payload"]["summary"]["outcome"] = "FAIL"
        with self.assertRaisesRegex(ArtifactError, "E_REGRESSION_RESULT"):
            validate_regression_artifact(forged)
        forged = copy.deepcopy(artifact)
        forged["status"] = "PASS"
        with self.assertRaisesRegex(ArtifactError, "E_REGRESSION_STATUS"):
            validate_regression_artifact(forged)


if __name__ == "__main__":
    unittest.main()
