import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.builtin_artifacts import ArtifactError
from codekit.offline_runner import run_command, run_mutation_commands, run_repeated


class OfflineRunnerTests(unittest.TestCase):
    def _command(self, code):
        return [sys.executable, "-c", code]

    def test_records_identity_hashes_and_pass_fail_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.py"
            target.write_text("print('ok')\n", encoding="utf-8")
            passed = run_command(target="target", command=self._command("print('ok')"), cwd=tmp,
                                 check_plan_id="cp", candidate_digest="candidate", target_path="target.py",
                                 environment={"PYTHONIOENCODING": "utf-8"})
            self.assertEqual(passed["status"], "PASS")
            self.assertEqual(len(passed["check_execution_id"]), 64)
            self.assertEqual(len(passed["target_bytes_sha256"]), 64)
            failed = run_command(target="target", command=self._command("raise SyntaxError('bad')"), cwd=tmp,
                                 check_plan_id="cp", candidate_digest="candidate",
                                 environment={"PYTHONIOENCODING": "utf-8"})
            self.assertEqual(failed["status"], "FAIL")
            self.assertEqual(failed["failure_class"], "SYNTAX")

    def test_timeout_is_blocked_and_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocked = run_command(target="slow", command=self._command("import time; time.sleep(1)"), cwd=tmp,
                                  check_plan_id="cp", candidate_digest="candidate", timeout_seconds=0.01)
            self.assertEqual(blocked["status"], "BLOCKED")
            self.assertEqual(blocked["reason"], "TIMEOUT")
            with self.assertRaisesRegex(ArtifactError, "E_RUNNER_PATH"):
                run_command(target="escape", command=self._command("pass"), cwd=tmp,
                            check_plan_id="cp", candidate_digest="candidate", target_path="../outside.py")
            with self.assertRaisesRegex(ArtifactError, "E_RUNNER_ENV"):
                run_command(target="secret", command=self._command("pass"), cwd=tmp,
                            check_plan_id="cp", candidate_digest="candidate", environment={"API_TOKEN": "blocked"})
            with self.assertRaisesRegex(ArtifactError, "E_RUNNER_ENV"):
                run_command(target="unlisted", command=self._command("pass"), cwd=tmp,
                            check_plan_id="cp", candidate_digest="candidate", environment={"UNLISTED": "blocked"})
            with self.assertRaisesRegex(ArtifactError, "E_RUNNER_ENV"):
                run_command(target="bad-type", command=self._command("pass"), cwd=tmp,
                            check_plan_id="cp", candidate_digest="candidate", environment={"PATH": None})  # type: ignore[arg-type]
            with self.assertRaisesRegex(ArtifactError, "E_RUNNER_TIMEOUT"):
                run_command(target="bad-timeout", command=self._command("pass"), cwd=tmp,
                            check_plan_id="cp", candidate_digest="candidate", timeout_seconds=float("nan"))

    def test_shell_free_argv_preserves_empty_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_command(target="argv", command=[sys.executable, "-c", "import sys; raise SystemExit(0 if sys.argv[1] == '' else 1)", ""], cwd=tmp,
                                 check_plan_id="cp", candidate_digest="candidate")
            self.assertEqual(result["status"], "PASS")
            with self.assertRaisesRegex(ArtifactError, "E_RUNNER_ARGV"):
                run_command(target="argv", command=[sys.executable, "-c", "pass", "a\x00b"], cwd=tmp,
                            check_plan_id="cp", candidate_digest="candidate")
            with self.assertRaisesRegex(ArtifactError, "E_RUNNER_ID"):
                run_command(target="identity", command=self._command("pass"), cwd=tmp,
                            check_plan_id="cp\nunsafe", candidate_digest="candidate")

    def test_mutation_requires_stable_baseline_and_kills_all_mutants(self):
        with tempfile.TemporaryDirectory() as tmp:
            common = {"cwd": tmp, "check_plan_id": "cp", "candidate_digest": "candidate",
                      "environment": {"PYTHONIOENCODING": "utf-8"}}
            result = run_mutation_commands(
                baseline={"target": "base", "command": self._command("pass"), **common},
                mutations=[
                    {"id": "survives", "target": "m1", "command": self._command("pass"), **common},
                    {"id": "killed", "target": "m2", "command": self._command("raise SystemExit(1)"), **common},
                ],
            )
            self.assertEqual(result["outcome"], "FAIL")
            self.assertFalse(result["results"][0]["flaky"])
            all_killed = run_mutation_commands(
                baseline={"target": "base", "command": self._command("pass"), **common},
                mutations=[{"id": "killed", "target": "m2", "command": self._command("raise SystemExit(1)"), **common}],
                repeat=2,
            )
            self.assertEqual(all_killed["outcome"], "PASS")
        with self.assertRaisesRegex(ValueError, "E_MUTATION_RUN"):
            run_mutation_commands(baseline={"command": self._command("pass")}, mutations=[])

    def test_repeat_detects_flaky_status_without_best_of(self):
        with tempfile.TemporaryDirectory() as tmp:
            # The process-local file makes the second run exit differently.
            marker = Path(tmp) / "marker"
            code = f"from pathlib import Path; p=Path({str(marker)!r}); first=not p.exists(); p.write_text('x'); raise SystemExit(1 if first else 0)"
            record = run_repeated(target="flaky", command=self._command(code), cwd=tmp,
                                  check_plan_id="cp", candidate_digest="candidate", repeat=2)
            self.assertTrue(record["flaky"])
            self.assertEqual(record["status"], "BLOCKED")

    def test_repeat_detects_flaky_output_even_when_status_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "counter"
            code = f"from pathlib import Path; p=Path({str(marker)!r}); n=int(p.read_text()) + 1 if p.exists() else 1; p.write_text(str(n)); print(n)"
            record = run_repeated(target="flaky-output", command=self._command(code), cwd=tmp,
                                  check_plan_id="cp", candidate_digest="candidate", repeat=2)
            self.assertTrue(record["flaky"])
            self.assertEqual(record["status"], "BLOCKED")

    def test_candidate_ref_is_closed_and_binds_the_candidate_digest(self):
        candidate = {"kind": "file", "id": "candidate", "path": "candidate.patch", "sha256": "a" * 64}
        with tempfile.TemporaryDirectory() as tmp:
            accepted = run_command(target="candidate", command=self._command("pass"), cwd=tmp,
                                   check_plan_id="cp", candidate_digest="a" * 64, candidate_ref=candidate)
            self.assertEqual(accepted["candidate_ref"], candidate)
            with self.assertRaisesRegex(ArtifactError, "E_RUNNER_CANDIDATE"):
                run_command(target="candidate", command=self._command("pass"), cwd=tmp,
                            check_plan_id="cp", candidate_digest="b" * 64, candidate_ref=candidate)
            unsafe = {**candidate, "path": "../candidate.patch"}
            with self.assertRaisesRegex(ArtifactError, "E_RUNNER_CANDIDATE"):
                run_command(target="candidate", command=self._command("pass"), cwd=tmp,
                            check_plan_id="cp", candidate_digest="a" * 64, candidate_ref=unsafe)


if __name__ == "__main__":
    unittest.main()
