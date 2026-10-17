from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from codekit.baseline_binding import validate_baseline_binding  # noqa: E402
from codekit.coverage import CoverageDecision  # noqa: E402
from codekit.currentness import evaluate_baseline_currentness  # noqa: E402
from codekit.git_ancestor import AncestorObservation  # noqa: E402
from codekit.git_probe import GitProbeObservation  # noqa: E402
from codekit import protocols  # noqa: E402


BASE = "a" * 40
TREE = "b" * 40
REF = {"kind": "accepted-result", "id": "alpha", "sha256": "c" * 64, "path": "evidence/a.json"}


def binding() -> dict[str, object]:
    return {
        "record_type": "baseline-binding", "schema_version": 1,
        "repo_id": "code-kit", "environment_id": "windows-review", "object_format": "sha1",
        "base_sha": BASE, "tree_sha": TREE, "upstream_results": [copy.deepcopy(REF)],
        "coverage_mode": "exact_tree", "coverage_refs": [copy.deepcopy(REF)],
        "authorization_ref": {"kind": "authorization", "id": "baseline-use", "sha256": "d" * 64, "path": "evidence/auth.json"},
        "observation_ref": {"kind": "observation", "id": "git-observation", "sha256": "e" * 64, "path": "evidence/git.json"},
        "guard_version": 1,
    }


def git(*, verified=True, blocked=(), unknown=()):
    return GitProbeObservation({"base_commit_present": True}, verified, tuple(blocked), tuple(unknown))


class CurrentnessTests(unittest.TestCase):
    def test_all_gates_are_required_in_fixed_order(self):
        decision = evaluate_baseline_currentness(
            binding(), git(verified=False, blocked=("base_tree_mismatch",)),
            AncestorObservation("NOT_ANCESTOR"), CoverageDecision("BLOCK", ("AUTHORIZATION_UNKNOWN",)),
            authorization_current=False, guard_match=False,
        )
        self.assertEqual(decision.decision, "BLOCK")
        self.assertEqual(decision.reasons, (
            "REJECT_REAL_COMMIT", "REJECT_ANCESTRY", "REJECT_COVERAGE",
            "REJECT_BASELINE_AUTHORIZATION", "REJECT_CURRENTNESS",
        ))

    def test_unknown_facts_wait_and_only_all_true_verifies(self):
        waiting = evaluate_baseline_currentness(
            binding(), git(verified=False), AncestorObservation("UNKNOWN"), CoverageDecision("BLOCK", ()),
            authorization_current=None, guard_match=None,
        )
        self.assertEqual(waiting.reasons, (
            "WAIT_REAL_COMMIT", "WAIT_ANCESTRY", "WAIT_COVERAGE",
            "WAIT_BASELINE_AUTHORIZATION", "WAIT_CURRENTNESS",
        ))
        ready = evaluate_baseline_currentness(
            binding(), git(), AncestorObservation("ANCESTOR"), CoverageDecision("COVERAGE_VERIFIED"),
            authorization_current=True, guard_match=True,
        )
        self.assertEqual(ready.decision, "BASELINE_CURRENT_VERIFIED")
        self.assertEqual(ready.reasons, ())

    def test_input_binding_is_not_mutated(self):
        raw = binding()
        before = copy.deepcopy(raw)
        evaluate_baseline_currentness(raw, git(), AncestorObservation("ANCESTOR"), CoverageDecision("COVERAGE_VERIFIED"), authorization_current=True, guard_match=True)
        self.assertEqual(raw, before)

    def test_malformed_gate_inputs_are_structured_errors(self):
        cases = (
            ("/git_observation", [], AncestorObservation("ANCESTOR"), CoverageDecision("COVERAGE_VERIFIED"), True, True),
            ("/ancestor_observation", git(), [], CoverageDecision("COVERAGE_VERIFIED"), True, True),
            ("/coverage_decision", git(), AncestorObservation("ANCESTOR"), [], True, True),
            ("/authorization_current", git(), AncestorObservation("ANCESTOR"), CoverageDecision("COVERAGE_VERIFIED"), [], True),
            ("/guard_match", git(), AncestorObservation("ANCESTOR"), CoverageDecision("COVERAGE_VERIFIED"), True, []),
        )
        for field, git_observation, ancestor_observation, coverage_decision, authorization_current, guard_match in cases:
            with self.subTest(field=field):
                with self.assertRaises(protocols.ProtocolError) as caught:
                    evaluate_baseline_currentness(binding(), git_observation, ancestor_observation,
                                                  coverage_decision,
                                                  authorization_current=authorization_current,
                                                  guard_match=guard_match)
                self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")
                self.assertEqual(caught.exception.field, field)


if __name__ == "__main__":
    unittest.main()
