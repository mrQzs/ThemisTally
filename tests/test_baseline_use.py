from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from codekit.baseline_use import resolve_baseline_use  # noqa: E402
from codekit.acceptance import validate_accepted_result, validate_acceptance_revocation  # noqa: E402

REQUEST = "req-" + "a" * 32
HASHES = {"candidate": "a" * 64, "checks": "b" * 64, "output": "c" * 64, "schema": "d" * 64, "verdict": "e" * 64}


def ref(kind, identity, digest, path):
    return {"kind": kind, "id": identity, "sha256": digest, "path": path}


def accepted(identity, task="source-a", candidate="candidate-3", guard=7, upstream=()):
    return {"record_type": "accepted-result", "schema_version": 1, "acceptance_id": identity,
            "request_id": REQUEST, "task_id": task, "plan_version": 3, "guard_version": guard,
            "candidate_ref": ref("candidate", candidate, HASHES["candidate"], "candidate.json"),
            "check_set_ref": ref("check-set", "checks-3", HASHES["checks"], "checks.json"),
            "verdict_ref": ref("verdict", "verdict-3", HASHES["verdict"], "verdict.json"),
            "output_refs": {"result": ref("artifact", "result-3", HASHES["output"], "out/result.json")},
            "target_schema_refs": {"result": ref("schema", "schema-1", HASHES["schema"], "schemas/result.json")},
            "upstream_acceptance_ids": list(upstream)}


def binding():
    return {"record_type": "baseline-binding", "schema_version": 1, "repo_id": "code-kit",
            "environment_id": "windows-review", "object_format": "sha1", "base_sha": "a" * 40,
            "tree_sha": "b" * 40, "upstream_results": [], "coverage_mode": "exact_tree",
            "coverage_refs": [ref("candidate", "c", "c" * 64, "candidate.json")],
            "authorization_ref": ref("authorization", "baseline-use", "d" * 64, "evidence/auth.json"),
            "observation_ref": ref("observation", "git", "e" * 64, "evidence/git.json"), "guard_version": 7}


class BaselineUseTests(unittest.TestCase):
    def test_requires_both_upstreams_and_explicit_merge(self):
        left = validate_accepted_result(accepted("accept-left"))
        right = validate_accepted_result(accepted("accept-right", task="source-b"))
        merge = validate_accepted_result(accepted("accept-merge", task="merge", upstream=("accept-left", "accept-right")))
        candidate = merge.record["candidate_ref"]
        result = resolve_baseline_use(binding(), [left, right, merge], [],
                                      required_acceptance_ids=["accept-left", "accept-right"],
                                      integration_acceptance_id="accept-merge", integration_candidate_ref=candidate,
                                      authorization_current=True, expected_request_id=REQUEST, expected_guard_version=7)
        self.assertEqual(result.decision, "BASELINE_USE_ALLOWED")

    def test_missing_or_revoked_upstream_cannot_fall_back_to_other_branch(self):
        left = validate_accepted_result(accepted("accept-left"))
        merge = validate_accepted_result(accepted("accept-merge", task="merge", upstream=("accept-left", "accept-right")))
        revoke = validate_acceptance_revocation({"record_type": "acceptance-revocation", "schema_version": 1,
            "revocation_id": "revoke", "acceptance_id": "accept-left", "reason": "changed", "guard_version": 8, "evidence_ref": "evidence"})
        result = resolve_baseline_use(binding(), [left, merge], [revoke], required_acceptance_ids=["accept-left", "accept-right"],
                                      integration_acceptance_id="accept-merge", integration_candidate_ref=merge.record["candidate_ref"],
                                      authorization_current=True, expected_request_id=REQUEST, expected_guard_version=7)
        self.assertIn("ACCEPTANCE_REVOKED", result.reasons)
        self.assertIn("WAIT_UPSTREAM_ACCEPTANCE", result.reasons)

    def test_authorization_unknown_and_candidate_drift_block(self):
        merge = validate_accepted_result(accepted("accept-merge", task="merge"))
        result = resolve_baseline_use(binding(), [merge], [], required_acceptance_ids=[], integration_acceptance_id="accept-merge",
                                      integration_candidate_ref={**merge.record["candidate_ref"], "id": "candidate-new"},
                                      authorization_current=None, expected_request_id=REQUEST, expected_guard_version=7)
        self.assertEqual(result.reasons, ("WAIT_BASELINE_AUTHORIZATION", "INTEGRATION_CANDIDATE_MISMATCH"))


if __name__ == "__main__":
    unittest.main()
