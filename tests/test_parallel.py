#!/usr/bin/env python3
"""07-T2D restricted parallel-admission tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.parallel import (  # noqa: E402
    AdmissionCandidate, IndependenceProof, ParallelModelError, ResourceClaim, ResourceHold,
    MAX_CLAIMS, admit_candidates, claims_conflict, claims_from_task, no_progress_reason,
    normalize_claims,
)


REPO = "repo-a"
REQUEST = "req-" + "a" * 32


def claim(key: str, mode: str = "exclusive", *, repo: str = REPO, kind: str = "key") -> ResourceClaim:
    return ResourceClaim(repo, kind, key, mode)


def proof(*refs: str) -> IndependenceProof:
    return IndependenceProof(refs or ("scope:all",), "a" * 64, 1)


def candidate(task: str, *, request: str = REQUEST, claims: tuple[ResourceClaim, ...] = (), priority: int = 0,
             sequence: int = 0, ready: bool | None = True, budget: bool | None = True,
             recovery: bool | None = True, independence: IndependenceProof | None = None,
             guard: int | None = 1) -> AdmissionCandidate:
    return AdmissionCandidate(REPO, request, task, priority, sequence, claims, ready, budget, recovery,
                               independence, guard)


class ParallelTests(unittest.TestCase):
    def test_read_read_shares_but_write_and_unknown_conflict(self) -> None:
        self.assertFalse(claims_conflict(claim("module:x", "read"), claim("module:x", "read")))
        self.assertTrue(claims_conflict(claim("module:x", "read"), claim("module:x", "write")))
        self.assertTrue(claims_conflict(claim("module:x", "unknown"), claim("module:x", "read")))

    def test_path_overlap_is_segment_aware_and_cross_repo_isolated(self) -> None:
        self.assertTrue(claims_conflict(claim("src/a", "write", kind="path"),
                                        claim("src/a/child", "read", kind="path")))
        self.assertFalse(claims_conflict(claim("src/a", "write", kind="path"),
                                         claim("src/alpha", "write", kind="path")))
        self.assertFalse(claims_conflict(claim("module:x", repo="repo-b"), claim("module:x")))

    def test_task_mapping_is_conservative_and_allows_no_resource_claim(self) -> None:
        mapped = claims_from_task(REPO, {
            "write_scope": [{"path": "src/a", "kind": "tree"}],
            "resource_keys": ["module:a"],
        })
        self.assertEqual([(item.kind, item.key, item.mode) for item in mapped],
                         [("key", "module:a", "exclusive"), ("path", "src/a", "write")])
        self.assertEqual(claims_from_task(REPO, {"write_scope": [], "resource_keys": []}), ())
        with self.assertRaises(ParallelModelError):
            claims_from_task(REPO, {"write_scope": [{"path": "src/a", "kind": "tree", "extra": True}],
                                    "resource_keys": []})

    def test_stable_order_is_priority_sequence_then_task(self) -> None:
        result = admit_candidates([
            candidate("z", priority=1, sequence=2),
            candidate("a", priority=1, sequence=1),
            candidate("high", priority=2, sequence=99),
        ], (), max_parallel_tasks=3)
        self.assertEqual([item.task_id for item in result.admitted], ["high", "a", "z"])

    def test_resource_admission_is_all_or_nothing_and_cross_request_visible(self) -> None:
        held = ResourceHold(REPO, "req-" + "b" * 32, "held", "op-held", "STARTED",
                            (claim("module:shared"),))
        result = admit_candidates([
            candidate("blocked", claims=(claim("module:shared"), claim("module:other")), priority=2),
            candidate("free", claims=(claim("module:free"),), priority=1, independence=proof("key:module:free")),
        ], (held,), max_parallel_tasks=2)
        self.assertEqual([item.task_id for item in result.admitted], ["free"])
        self.assertEqual(result.blocked, (("blocked", "WAIT_RESOURCE"),))

    def test_existing_active_task_blocks_even_without_overlapping_claims(self) -> None:
        held = ResourceHold(REPO, REQUEST, "same", "op-held", "REVIEW_PENDING", ())
        result = admit_candidates([candidate("same")], (held,), max_parallel_tasks=1)
        self.assertEqual(result.blocked, (("same", "WAIT_TASK_ACTIVE"),))

    def test_capacity_blocks_without_leaving_partial_holds(self) -> None:
        result = admit_candidates([candidate("a"), candidate("b")], (), max_parallel_tasks=1)
        self.assertEqual([item.task_id for item in result.admitted], ["a"])
        self.assertEqual(result.blocked, (("b", "WAIT_CONCURRENCY"),))

    def test_parallel_admission_requires_independence_proof_for_claimed_resources(self) -> None:
        blocked = admit_candidates([candidate("a", claims=(claim("module:a"),))], (), max_parallel_tasks=2)
        self.assertEqual(blocked.blocked, (("a", "WAIT_RESOURCE"),))
        allowed = admit_candidates([candidate("a", claims=(claim("module:a"),), independence=proof("key:module:a"))],
                                   (), max_parallel_tasks=2)
        self.assertEqual([item.task_id for item in allowed.admitted], ["a"])

    def test_unknown_facts_block_before_resource_or_capacity(self) -> None:
        result = admit_candidates([
            candidate("recovery", recovery=None),
            candidate("budget", budget=None),
            candidate("upstream", ready=None),
        ], (), max_parallel_tasks=1)
        self.assertEqual(result.blocked, (("budget", "WAIT_BUDGET"),
                                          ("recovery", "RECOVERY_REQUIRED"),
                                          ("upstream", "WAIT_UPSTREAM")))
        unknown = admit_candidates([candidate("unknown", claims=(claim("dynamic", "unknown"),))], (),
                                   max_parallel_tasks=1)
        self.assertEqual(unknown.blocked, (("unknown", "WAIT_RESOURCE"),))

    def test_no_progress_does_not_claim_completion(self) -> None:
        empty = admit_candidates([], (), max_parallel_tasks=1)
        self.assertEqual(no_progress_reason(empty, required_remaining=True), "WAIT_NO_READY")
        self.assertEqual(no_progress_reason(empty, required_remaining=None), "WAIT_REQUIRED_STATE_UNKNOWN")
        self.assertEqual(no_progress_reason(empty, required_remaining=False), "COMPLETE_PROVEN")

    def test_claims_and_candidates_are_strict(self) -> None:
        with self.assertRaises(ParallelModelError):
            claims_conflict(claim("bad\\path", kind="path"), claim("x"))
        with self.assertRaises(ParallelModelError):
            claims_conflict(claim("src/line\nfeed", kind="path"), claim("x"))
        for path in ("src/[ab]", "src/{a,b}", "/".join(["a" * 200] * 6)):
            with self.subTest(path=path), self.assertRaises(ParallelModelError):
                claims_conflict(claim(path, kind="path"), claim("x"))
        with self.assertRaises(ParallelModelError):
            admit_candidates([candidate("a", ready=1)], (), max_parallel_tasks=1)  # type: ignore[arg-type]
        with self.assertRaises(ParallelModelError):
            admit_candidates([candidate("a", claims=(claim("x"),), independence=IndependenceProof(("x",), "bad", 1))],
                             (), max_parallel_tasks=2)

    def test_unicode_path_scope_can_be_bound_by_independence_proof(self) -> None:
        item = claim("src/模块", kind="path")
        result = admit_candidates(
            [candidate("unicode", claims=(item,), independence=proof("path:src/模块"))],
            (), max_parallel_tasks=2,
        )
        self.assertEqual(tuple(admission.task_id for admission in result.admitted), ("unicode",))

    def test_claim_vector_has_a_bounded_size(self) -> None:
        items = tuple(claim(f"module:{index}") for index in range(MAX_CLAIMS + 1))
        with self.assertRaises(ParallelModelError):
            normalize_claims(items)

    def test_underreported_active_count_fails_closed_from_holds(self) -> None:
        hold = ResourceHold(REPO, "req-" + "b" * 32, "held", "op-held", "STARTED", ())
        result = admit_candidates([candidate("next")], (hold,), max_parallel_tasks=1, active_count=0)
        self.assertEqual(result.blocked, (("next", "WAIT_CONCURRENCY"),))


if __name__ == "__main__":
    unittest.main(verbosity=2)
