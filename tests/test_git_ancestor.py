"""07-T2B-G ancestry probe tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit import protocols  # noqa: E402
from codekit.git_ancestor import (  # noqa: E402
    AncestorObservation, build_ancestor_plan, interpret_ancestor,
)
from codekit.git_probe import RawResult, TrustedRepositoryIdentity  # noqa: E402


IDENTITY = TrustedRepositoryIdentity(
    repo_id="code-kit", environment_id="windows-review", worktree_root="D:/repo",
    git_dir="D:/repo/.git", common_dir="D:/repo/.git", object_format="sha1",
)


class GitAncestorTests(unittest.TestCase):
    def test_plan_is_fixed_full_oid_and_read_only(self) -> None:
        plan = build_ancestor_plan(IDENTITY, "a" * 40, "b" * 40)
        self.assertEqual(plan.argv, ("git", "-C", "D:/repo", "merge-base", "--is-ancestor", "a" * 40, "b" * 40))
        self.assertNotIn("fetch", plan.argv)
        self.assertNotIn("commit", plan.argv)
        self.assertIn(("GIT_NO_LAZY_FETCH", "1"), plan.environment_set)

    def test_plan_rejects_short_or_wrong_format_ids(self) -> None:
        with self.assertRaises(protocols.ProtocolError) as caught:
            build_ancestor_plan(IDENTITY, "a" * 39, "b" * 40)
        self.assertEqual(caught.exception.code, "E_GIT_OID_SYNTAX")
        identity = TrustedRepositoryIdentity("code-kit", "windows-review", "D:/repo", "D:/repo/.git", "D:/repo/.git", "sha256")
        with self.assertRaises(protocols.ProtocolError):
            build_ancestor_plan(identity, "a" * 40, "b" * 40)

    def test_exit_zero_and_one_are_distinct_answers(self) -> None:
        self.assertEqual(interpret_ancestor(RawResult(0, b"")), AncestorObservation("ANCESTOR"))
        self.assertEqual(interpret_ancestor(RawResult(1, b"")), AncestorObservation("NOT_ANCESTOR"))

    def test_git_error_timeout_truncation_and_output_are_unknown(self) -> None:
        for result in (RawResult(2, b""), RawResult(None, b"", timed_out=True),
                       RawResult(0, b"", truncated=True), RawResult(0, b"unexpected")):
            with self.subTest(result=result):
                self.assertEqual(interpret_ancestor(result).decision, "UNKNOWN")

    def test_mapping_result_is_bounded_and_invalid_mapping_is_unknown(self) -> None:
        self.assertEqual(interpret_ancestor({"returncode": 0, "stdout": b""}).decision, "ANCESTOR")
        self.assertEqual(interpret_ancestor({"returncode": 0, "stdout": ""}).decision, "UNKNOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
