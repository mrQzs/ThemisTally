#!/usr/bin/env python3
"""07-T2B-G pure probe-plan and result-interpretation tests."""
from __future__ import annotations

import copy
from dataclasses import replace
import os
import shutil
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit import protocols  # noqa: E402
from codekit.git_probe import (  # noqa: E402
    BASE_BODY, BASE_TYPE, GIT_ENV_SET, GIT_REDIRECT_VARS, GRAFTS, META, PROMISOR, PARTIAL_CLONE,
    ALTERNATES, PROBE_COMMANDS, REPLACEMENTS, TREE_ENTRIES, TREE_TYPE, RawResult, TrustedRepositoryIdentity,
    build_git_env, build_probe_plan, inspect_lfs_evidence, interpret_probe, run_probe,
)
from tests.test_baseline_binding import sample  # noqa: E402


IDENTITY = TrustedRepositoryIdentity(
    repo_id="code-kit", environment_id="windows-review", worktree_root="D:/repo",
    git_dir="D:/repo/.git", common_dir="D:/repo/.git", object_format="sha1",
)


def valid_results() -> dict[str, RawResult]:
    binding = sample()
    tree = binding["tree_sha"]
    base = binding["base_sha"]
    return {
        META: RawResult(0, b"D:/repo\nD:/repo/.git\nD:/repo/.git\nsha1\ntrue\nfalse\n"),
        BASE_TYPE: RawResult(0, b"commit\n"),
        BASE_BODY: RawResult(0, f"tree {tree}\nauthor synthetic\n".encode()),
        TREE_TYPE: RawResult(0, b"tree\n"),
        REPLACEMENTS: RawResult(0, b""),
        GRAFTS: RawResult(0, b"D:/repo/.git/info/grafts\n", path_exists=False),
        PARTIAL_CLONE: RawResult(1, b""),
        PROMISOR: RawResult(1, b""),
        ALTERNATES: RawResult(0, b"D:/repo/.git/objects/info/alternates\n", path_exists=False),
        TREE_ENTRIES: RawResult(0, f"100644 blob {'f' * 40}".encode() + bytes([9]) + b"README.md" + bytes([0])),
    }


class GitProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = build_probe_plan(sample(), IDENTITY)

    def test_plan_uses_trusted_identity_and_fixed_read_only_commands(self) -> None:
        self.assertEqual(self.plan.commands[0][:3], ("git", "-C", "D:/repo"))
        self.assertTrue(any("cat-file" in command for command in self.plan.commands))
        self.assertEqual(self.plan.environment_remove, GIT_REDIRECT_VARS)
        self.assertEqual(self.plan.environment_set, GIT_ENV_SET)
        for command in self.plan.commands:
            self.assertEqual(command[0], "git")
            self.assertNotIn("fetch", command)
            self.assertNotIn("commit", command)

    def test_environment_policy_removes_redirects_without_mutating_input(self) -> None:
        source = {"keep": "yes", "GIT_DIR": "redirect", "OTHER_FLAG": "case-sensitive"}
        before = copy.deepcopy(source)
        result = build_git_env(source)
        self.assertEqual(source, before)
        self.assertNotIn("GIT_DIR", result)
        self.assertIn("OTHER_FLAG", result)
        for key, value in GIT_ENV_SET:
            self.assertEqual(result[key], value)

    def test_environment_policy_rejects_non_text_and_all_git_overrides(self) -> None:
        result = build_git_env({
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.filemode",
            "GIT_CONFIG_VALUE_0": "false", "GIT_OBJECT_DIRECTORY": "redirect",
            "GCM_INTERACTIVE": "yes", "KEEP": "yes",
        })
        self.assertNotIn("GIT_CONFIG_COUNT", result)
        self.assertNotIn("GIT_CONFIG_KEY_0", result)
        self.assertNotIn("GIT_CONFIG_VALUE_0", result)
        self.assertNotIn("GIT_OBJECT_DIRECTORY", result)
        self.assertEqual(result["GCM_INTERACTIVE"], "never")
        self.assertEqual(result["KEEP"], "yes")
        with self.assertRaises(protocols.ProtocolError) as caught:
            build_git_env({"KEEP": 1})  # type: ignore[dict-item]
        self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")

    def test_injected_runner_receives_only_fixed_commands_and_sanitized_env(self) -> None:
        captured = []
        expected = valid_results()

        def runner(argv, cwd, env, timeout, max_output):
            captured.append((tuple(argv), cwd, dict(env), timeout, max_output))
            joined = " ".join(argv)
            if "--show-toplevel" in argv:
                return expected[META]
            if "cat-file" in argv and "-t" in argv:
                return expected[BASE_TYPE] if argv[-1] == self.plan.base_sha else expected[TREE_TYPE]
            if "rev-parse" in argv and "--verify" in argv:
                return expected[BASE_BODY]
            if "replace" in argv:
                return expected[REPLACEMENTS]
            if "info/grafts" in joined:
                return expected[GRAFTS]
            if "extensions.partialClone" in argv:
                return expected[PARTIAL_CLONE]
            if "promisor" in joined:
                return expected[PROMISOR]
            if "objects/info/alternates" in joined:
                return expected[ALTERNATES]
            if "ls-tree" in argv:
                return expected[TREE_ENTRIES]
            raise AssertionError(argv)

        observation = run_probe(
            self.plan,
            runner=runner,
            source_env={"GIT_DIR": "redirect", "KEEP": "yes"},
        )
        self.assertFalse(observation.verified)  # LFS remains unknown by policy.
        self.assertEqual(len(captured), len(PROBE_COMMANDS))
        self.assertTrue(all(item[0][0:2] == ("git", "-C") for item in captured))
        self.assertTrue(all("GIT_DIR" not in item[2] for item in captured))
        self.assertTrue(all(item[2]["GIT_NO_LAZY_FETCH"] == "1" for item in captured))
        self.assertTrue(all("fetch" not in item[0] and "commit" not in item[0] for item in captured))

    @unittest.skipUnless(shutil.which("git"), "git executable required")
    def test_default_adapter_reads_temp_repo_without_git_metadata_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            def git(*args: str) -> str:
                return subprocess.check_output(
                    ["git", *args], cwd=str(repo), stderr=subprocess.STDOUT, text=True
                ).strip()

            git("init", "-q")
            git("config", "user.name", "probe-test")
            git("config", "user.email", "probe-test@example.invalid")
            (repo / "README.md").write_text("probe\n", encoding="utf-8")
            git("add", "README.md")
            git("commit", "-q", "-m", "seed")
            base = git("rev-parse", "HEAD")
            tree = subprocess.check_output(
                ["git", "cat-file", "-p", base], cwd=str(repo), stderr=subprocess.STDOUT
            ).splitlines()[0].split()[1].decode("ascii")
            root = git("rev-parse", "--show-toplevel")
            git_dir = git("rev-parse", "--path-format=absolute", "--git-dir")
            common_dir = git("rev-parse", "--path-format=absolute", "--git-common-dir")
            identity = TrustedRepositoryIdentity(
                "code-kit", "temp-git", root, git_dir, common_dir, "sha1"
            )
            binding = copy.deepcopy(sample())
            binding.update({
                "environment_id": "temp-git",
                "base_sha": base,
                "tree_sha": tree,
            })
            plan = build_probe_plan(binding, identity)
            before = git("rev-parse", "HEAD")
            env = dict(os.environ)
            env["GIT_DIR"] = str(repo / "redirected.git")
            observation = run_probe(plan, source_env=env)
            after = git("rev-parse", "HEAD")
            self.assertEqual(before, after)
            self.assertEqual(git("status", "--porcelain"), "")
            self.assertTrue(observation.facts["repository_identity_match"])
            self.assertTrue(observation.facts["base_commit_present"])
            self.assertTrue(observation.facts["base_tree_matches_binding"])
            self.assertFalse(observation.verified)
            self.assertIn("lfs_status_unknown", observation.unknown_reasons)

    def test_lfs_evidence_blocks_filter_and_pointer_markers(self) -> None:
        status, reasons = inspect_lfs_evidence(
            {".gitattributes": b"*.bin filter=lfs diff=lfs merge=lfs -text\n"},
            {},
            complete=True,
        )
        self.assertTrue(status)
        self.assertEqual(reasons, ("lfs_filter_present",))
        pointer = (
            b"version https://git-lfs.github.com/spec/v1\n"
            b"oid sha256:" + b"a" * 64 + b"\nsize 12\n"
        )
        status, reasons = inspect_lfs_evidence({}, {"large.bin": pointer}, complete=True)
        self.assertTrue(status)
        self.assertEqual(reasons, ("lfs_pointer_present",))

    def test_lfs_evidence_is_clean_only_after_complete_scan(self) -> None:
        self.assertEqual(inspect_lfs_evidence({}, {"README.md": b"plain\n"}, complete=True), (False, ()))
        self.assertEqual(inspect_lfs_evidence({}, {"README.md": b"plain\n"}, complete=False),
                         (None, ("lfs_scan_incomplete",)))

    def test_lfs_evidence_keeps_malformed_or_oversize_inputs_unknown(self) -> None:
        status, reasons = inspect_lfs_evidence(
            {".gitattributes": b"aaaaaaaaa"}, {},
            complete=True,
            max_bytes=8,
        )
        self.assertIsNone(status)
        self.assertIn("lfs_attributes_oversize", reasons)

        status, reasons = inspect_lfs_evidence(
            {}, {"large.bin": b"version https://git-lfs.github.com/spec/v1\nwrong\n"},
            complete=True,
            max_bytes=128,
        )
        self.assertIsNone(status)
        self.assertIn("lfs_pointer_malformed", reasons)

        status, reasons = inspect_lfs_evidence(
            {}, {"ordinary.bin": b"x" * 9}, complete=True, max_bytes=8
        )
        self.assertIsNone(status)
        self.assertEqual(reasons, ("lfs_blob_oversize",))

    def test_identity_is_separate_from_binding_and_mismatch_rejected(self) -> None:
        identity = TrustedRepositoryIdentity(
            repo_id="other", environment_id="windows-review", worktree_root="D:/repo",
            git_dir="D:/repo/.git", common_dir="D:/repo/.git", object_format="sha1",
        )
        with self.assertRaises(protocols.ProtocolError) as caught:
            build_probe_plan(sample(), identity)
        self.assertEqual(caught.exception.code, "E_CONTEXT_BINDING")

    def test_valid_results_are_verified_only_for_local_git_facts(self) -> None:
        observation = interpret_probe(self.plan, valid_results(), lfs_status=False)
        self.assertTrue(observation.verified)
        self.assertEqual(observation.blocked_reasons, ())
        self.assertEqual(observation.unknown_reasons, ())
        self.assertFalse(observation.authorization_verified)
        self.assertFalse(observation.coverage_verified)

    def test_plan_and_lfs_inputs_cannot_bypass_fixed_boundaries(self) -> None:
        tampered = replace(self.plan, commands=self.plan.commands + (("git", "status"),))
        with self.assertRaises(protocols.ProtocolError) as caught:
            interpret_probe(tampered, valid_results(), lfs_status=False)
        self.assertEqual(caught.exception.code, "E_SCHEMA_FIELDS")
        with self.assertRaises(protocols.ProtocolError) as caught:
            run_probe(tampered, runner=lambda *_args: RawResult(1, b""))
        self.assertEqual(caught.exception.code, "E_SCHEMA_FIELDS")
        with self.assertRaises(protocols.ProtocolError) as caught:
            run_probe(self.plan, runner=lambda *_args: RawResult(0, "text"))  # type: ignore[arg-type]
        self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")
        with self.assertRaises(protocols.ProtocolError) as caught:
            interpret_probe(self.plan, [])  # type: ignore[arg-type]
        self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")
        with self.assertRaises(protocols.ProtocolError) as caught:
            interpret_probe(self.plan, {"unexpected": RawResult(0, b"")})
        self.assertEqual(caught.exception.code, "E_SCHEMA_FIELDS")
        with self.assertRaises(protocols.ProtocolError) as caught:
            inspect_lfs_evidence([], {}, complete=True)  # type: ignore[arg-type]
        self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")
        with self.assertRaises(protocols.ProtocolError) as caught:
            inspect_lfs_evidence({}, {}, complete=None)  # type: ignore[arg-type]
        self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")

    def test_malformed_lfs_status_or_path_fact_stays_unknown(self) -> None:
        with self.assertRaises(protocols.ProtocolError) as caught:
            interpret_probe(self.plan, valid_results(), lfs_status="false")  # type: ignore[arg-type]
        self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")
        results = valid_results()
        results[GRAFTS] = RawResult(0, b"D:/repo/.git/info/grafts\n", path_exists="false")  # type: ignore[arg-type]
        observation = interpret_probe(self.plan, results, lfs_status=False)
        self.assertIn("grafts_probe_unknown", observation.unknown_reasons)
        self.assertFalse(observation.verified)

    def test_metadata_identity_and_object_format_mismatch_block(self) -> None:
        results = valid_results()
        results[META] = RawResult(0, b"D:/other\nD:/repo/.git\nD:/repo/.git\nsha256\ntrue\nfalse\n")
        observation = interpret_probe(self.plan, results, lfs_status=False)
        self.assertFalse(observation.verified)
        self.assertIn("repository_identity_mismatch", observation.blocked_reasons)
        self.assertIn("object_format_mismatch", observation.blocked_reasons)

    def test_missing_or_malformed_outputs_are_unknown(self) -> None:
        results = valid_results()
        results.pop(BASE_BODY)
        results.pop(REPLACEMENTS)
        results[META] = RawResult(0, b"\xff")
        observation = interpret_probe(self.plan, results, lfs_status=None)
        self.assertFalse(observation.verified)
        self.assertIn("repository_metadata_malformed", observation.unknown_reasons)
        self.assertIn("base_body_missing", observation.unknown_reasons)
        self.assertIn("replacement_refs_missing", observation.unknown_reasons)
        self.assertIn("lfs_status_unknown", observation.unknown_reasons)
        self.assertFalse(observation.facts["hazards_clear"])

    def test_commit_tree_and_type_mismatches_block(self) -> None:
        results = valid_results()
        results[BASE_TYPE] = RawResult(0, b"tree\n")
        results[BASE_BODY] = RawResult(0, b"tree " + b"1" * 40 + b"\n")
        results[TREE_TYPE] = RawResult(0, b"blob\n")
        observation = interpret_probe(self.plan, results, lfs_status=False)
        self.assertIn("base_object_not_commit", observation.blocked_reasons)
        self.assertIn("base_tree_mismatch", observation.blocked_reasons)
        self.assertIn("base_object_not_tree", observation.blocked_reasons)

    def test_shallow_replacement_promisor_and_alternates_block(self) -> None:
        results = valid_results()
        results[META] = RawResult(0, b"D:/repo\nD:/repo/.git\nD:/repo/.git\nsha1\ntrue\ntrue\n")
        results[REPLACEMENTS] = RawResult(0, b"a" * 40 + b"\n")
        results[PARTIAL_CLONE] = RawResult(0, b"origin\n")
        results[PROMISOR] = RawResult(0, b"remote.origin.promisor true\n")
        results[ALTERNATES] = RawResult(0, b"D:/objects\n", path_exists=True)
        results[GRAFTS] = RawResult(0, b"D:/grafts\n", path_exists=True)
        observation = interpret_probe(self.plan, results, lfs_status=False)
        for reason in ("shallow_repository", "replacement_refs_present", "partial_clone_present",
                       "promisor_config_present", "alternates_present", "grafts_present"):
            self.assertIn(reason, observation.blocked_reasons)
        self.assertFalse(observation.verified)

    def test_submodule_gitmodules_and_lfs_are_never_silently_accepted(self) -> None:
        results = valid_results()
        results[TREE_ENTRIES] = RawResult(
            0, (f"160000 commit {'a' * 40}".encode() + bytes([9]) + b"deps/tool" + bytes([0])
                + b"100644 blob " + b"b" * 40 + bytes([9]) + b".gitmodules" + bytes([0])))
        observation = interpret_probe(self.plan, results, lfs_status=True)
        self.assertIn("submodule_gitlink_present", observation.blocked_reasons)
        self.assertIn("gitmodules_present", observation.blocked_reasons)
        self.assertIn("lfs_entries_present", observation.blocked_reasons)

    def test_timeout_truncation_and_non_utf8_do_not_become_pass(self) -> None:
        results = valid_results()
        results[META] = RawResult(None, b"", timed_out=True)
        results[TREE_ENTRIES] = RawResult(0, b"\xff", truncated=True)
        observation = interpret_probe(self.plan, results, lfs_status=False)
        self.assertFalse(observation.verified)
        self.assertIn("repository_metadata_unavailable", observation.unknown_reasons)
        self.assertIn("tree_entries_probe_unknown", observation.unknown_reasons)

    def test_binding_object_is_detached_before_plan_creation(self) -> None:
        value = sample()
        plan = build_probe_plan(value, IDENTITY)
        value["base_sha"] = "f" * 40
        self.assertEqual(plan.base_sha, "a" * 40)


if __name__ == "__main__":
    unittest.main(verbosity=2)
