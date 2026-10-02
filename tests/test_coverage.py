"""07-T2B-G content coverage and authorization fact tests."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit import protocols  # noqa: E402
from codekit.baseline_binding import validate_baseline_binding  # noqa: E402
from codekit.coverage import evaluate_coverage, validate_tree_entries  # noqa: E402


BASE_SHA = "a" * 40
TREE_SHA = "b" * 40
REF = {"kind": "accepted-result", "id": "alpha-result", "sha256": "c" * 64, "path": "evidence/alpha.json"}


def binding(mode: str = "exact_tree") -> dict[str, object]:
    return {
        "record_type": "baseline-binding", "schema_version": 1,
        "repo_id": "code-kit", "environment_id": "windows-review", "object_format": "sha1",
        "base_sha": BASE_SHA, "tree_sha": TREE_SHA, "upstream_results": [copy.deepcopy(REF)],
        "coverage_mode": mode, "coverage_refs": [copy.deepcopy(REF)],
        "authorization_ref": {"kind": "authorization", "id": "baseline-use", "sha256": "d" * 64, "path": "evidence/authorization.json"},
        "observation_ref": {"kind": "observation", "id": "git-observation", "sha256": "e" * 64, "path": "evidence/git.json"},
        "guard_version": 1,
    }


def entry(path: str = "src/a.py", *, oid: str = "f" * 40, sha256: str = "1" * 64, mode: str = "100644") -> dict[str, str]:
    return {"path": path, "oid": oid, "sha256": sha256, "mode": mode}


class CoverageTests(unittest.TestCase):
    def test_exact_tree_requires_fixed_tree_ancestor_and_authorization(self) -> None:
        result = evaluate_coverage(validate_baseline_binding(binding()), candidate_tree_oid=TREE_SHA,
                                   ancestor=True, authorization_verified=True)
        self.assertEqual((result.decision, result.reasons), ("COVERAGE_VERIFIED", ()))
        blocked = evaluate_coverage(binding(), candidate_tree_oid=BASE_SHA, ancestor=True, authorization_verified=True)
        self.assertIn("EXACT_TREE_MISMATCH", blocked.reasons)
        blocked = evaluate_coverage(binding(), candidate_tree_oid=TREE_SHA, ancestor=None, authorization_verified=None)
        self.assertEqual(blocked.decision, "BLOCK")
        self.assertIn("ANCESTOR_UNKNOWN", blocked.reasons)
        self.assertIn("AUTHORIZATION_UNKNOWN", blocked.reasons)

    def test_pinned_set_requires_exact_path_git_oid_blob_and_mode_inventory(self) -> None:
        items = [entry(), entry("src/b.py", oid="e" * 40, sha256="2" * 64, mode="100755")]
        result = evaluate_coverage(binding("pinned_artifact_set"), candidate_tree_oid=TREE_SHA,
                                   ancestor=True, authorization_verified=True,
                                   candidate_entries=items, pinned_artifacts=copy.deepcopy(items))
        self.assertEqual(result.decision, "COVERAGE_VERIFIED")
        changed = copy.deepcopy(items)
        changed[1]["sha256"] = "3" * 64
        blocked = evaluate_coverage(binding("pinned_artifact_set"), candidate_tree_oid=TREE_SHA,
                                    ancestor=True, authorization_verified=True,
                                    candidate_entries=items, pinned_artifacts=changed)
        self.assertEqual(blocked.reasons, ("PINNED_ARTIFACT_SET_MISMATCH",))

    def test_pinned_set_rejects_duplicate_or_unsafe_entries(self) -> None:
        items = [entry(), entry()]
        with self.assertRaises(protocols.ProtocolError) as caught:
            evaluate_coverage(binding("pinned_artifact_set"), candidate_tree_oid=TREE_SHA,
                              ancestor=True, authorization_verified=True,
                              candidate_entries=items, pinned_artifacts=[entry()])
        self.assertEqual(caught.exception.code, "E_SCHEMA_FIELDS")
        bad = entry("../secret")
        with self.assertRaises(protocols.ProtocolError) as caught:
            validate_tree_entries([bad], object_format="sha1")
        self.assertEqual(caught.exception.code, "E_PATH_SYNTAX")

    def test_revalidated_integration_requires_fresh_acceptance_and_checks(self) -> None:
        result = evaluate_coverage(binding("revalidated_integration"), candidate_tree_oid=BASE_SHA,
                                   ancestor=True, authorization_verified=True,
                                   integration_accepted=True, checks_current=True)
        self.assertEqual(result.decision, "COVERAGE_VERIFIED")
        blocked = evaluate_coverage(binding("revalidated_integration"), candidate_tree_oid=BASE_SHA,
                                    ancestor=True, authorization_verified=True,
                                    integration_accepted=False, checks_current=None)
        self.assertIn("INTEGRATION_ACCEPTANCE_REJECTED", blocked.reasons)
        self.assertIn("INTEGRATION_CHECKS_UNKNOWN", blocked.reasons)

    def test_unknown_and_false_facts_are_distinct_and_never_granted(self) -> None:
        for value, reason in ((False, "AUTHORIZATION_REJECTED"), (None, "AUTHORIZATION_UNKNOWN")):
            result = evaluate_coverage(binding(), candidate_tree_oid=TREE_SHA, ancestor=True,
                                       authorization_verified=value)
            self.assertEqual(result.decision, "BLOCK")
            self.assertIn(reason, result.reasons)

    def test_input_types_and_git_object_format_are_strict(self) -> None:
        with self.assertRaises(protocols.ProtocolError) as caught:
            evaluate_coverage(binding(), candidate_tree_oid=TREE_SHA, ancestor=1, authorization_verified=True)
        self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")
        with self.assertRaises(protocols.ProtocolError) as caught:
            evaluate_coverage(binding(), candidate_tree_oid="a" * 39, ancestor=True, authorization_verified=True)
        self.assertEqual(caught.exception.code, "E_GIT_OID_SYNTAX")

    def test_binding_is_detached_before_evaluation(self) -> None:
        value = binding()
        validated = validate_baseline_binding(value)
        value["tree_sha"] = "c" * 40
        result = evaluate_coverage(validated, candidate_tree_oid=TREE_SHA, ancestor=True, authorization_verified=True)
        self.assertEqual(result.decision, "COVERAGE_VERIFIED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
