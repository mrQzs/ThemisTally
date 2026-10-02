import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.runtime import InvocationSpec, Lifecycle, ProcessIdentity, RuntimeErrorCode, classify_start, reconcile, validate_argv


def invocation():
    return InvocationSpec("req", "run", ("python", "-c", "pass"), "C:\\repo", "a" * 64, 30)


class RuntimeTests(unittest.TestCase):
    def test_argv_and_shell_are_mutually_exclusive(self):
        self.assertEqual(validate_argv(["cmd", "中文"]), ("cmd", "中文"))
        with self.assertRaisesRegex(RuntimeErrorCode, "E_RUNTIME_SHELL_ARGV"):
            validate_argv(["cmd"], shell=True)
        with self.assertRaisesRegex(RuntimeErrorCode, "E_RUNTIME_ARGV"):
            validate_argv(["cmd\x00bad"])

    def test_invocation_and_process_identity_fields_are_strict_text(self):
        cases = [
            {"request_id": 1},
            {"run_id": b"run"},
            {"cwd": Path("C:/repo")},
            {"cwd": "C:\x00repo"},
            {"environment_sha256": None},
            {"shell": 1},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                values = {
                    "request_id": "req", "run_id": "run", "command": ("python",),
                    "cwd": "C:/repo", "environment_sha256": "a" * 64,
                    "timeout_seconds": 30,
                }
                values.update(changes)
                with self.assertRaises(RuntimeErrorCode):
                    InvocationSpec(**values)
        for changes in ({"boot_id": 1}, {"worktree_id": b"tree"}, {"executable_sha256": None}):
            with self.subTest(changes=changes):
                values = {"pid": 10, "boot_id": "boot", "executable_sha256": "b" * 64,
                          "worktree_id": "tree"}
                values.update(changes)
                with self.assertRaisesRegex(RuntimeErrorCode, "E_RUNTIME_IDENTITY"):
                    ProcessIdentity(**values)

    def test_observation_inputs_are_rejected_before_attribute_errors(self):
        spec = invocation()
        with self.assertRaisesRegex(RuntimeErrorCode, "E_RUNTIME_OBSERVATION"):
            classify_start(handoff_accepted=True, started_observation="started", expected=spec)
        with self.assertRaisesRegex(RuntimeErrorCode, "E_RUNTIME_OBSERVATION"):
            classify_start(handoff_accepted=1, started_observation=None, expected=spec)
        with self.assertRaisesRegex(RuntimeErrorCode, "E_RUNTIME_OBSERVATION"):
            reconcile(spec, "started")

    def test_lifecycle_rejects_invalid_state_generation_and_identity(self):
        for kwargs, code in (
            ({"state": "BROKEN"}, "E_RUNTIME_TRANSITION"),
            ({"generation": True}, "E_RUNTIME_FENCE"),
            ({"identity": "pid-only"}, "E_RUNTIME_IDENTITY"),
            ({"state": "STARTED"}, "E_RUNTIME_IDENTITY"),
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(RuntimeErrorCode, code):
                    Lifecycle(**kwargs)
        with self.assertRaisesRegex(RuntimeErrorCode, "E_RUNTIME_FENCE"):
            Lifecycle().transition("STARTING", expected_generation=True)

    def test_lifecycle_requires_identity_and_fences_transitions(self):
        identity = ProcessIdentity(10, "boot", "b" * 64, "tree")
        state = Lifecycle().transition("STARTING")
        state = state.transition("STARTED", identity=identity)
        state = state.transition("STOPPING")
        self.assertEqual(state.transition("STOPPED").state, "STOPPED")
        with self.assertRaisesRegex(RuntimeErrorCode, "E_RUNTIME_TRANSITION"):
            state.transition("STARTED", identity=identity)

    def test_unknown_handoff_never_becomes_started(self):
        spec = invocation()
        self.assertEqual(classify_start(handoff_accepted=True, started_observation=None, expected=spec), "START_UNKNOWN")
        self.assertEqual(classify_start(handoff_accepted=False, started_observation=None, expected=spec), "NOT_STARTED")
        self.assertEqual(reconcile(spec, {"state": "STARTED", "run_id": "other", "environment_sha256": "a" * 64})["status"], "IDENTITY_MISMATCH")

    def test_matching_observation_is_started_and_replay_policy_is_conservative(self):
        spec = invocation()
        observation = {"state": "STARTED", "run_id": spec.run_id, "environment_sha256": spec.environment_sha256}
        self.assertEqual(classify_start(handoff_accepted=True, started_observation=observation, expected=spec), "STARTED")
        self.assertFalse(reconcile(spec, observation)["replay_allowed"])
        self.assertFalse(reconcile(spec, {"state": "FAILED", "run_id": spec.run_id, "environment_sha256": spec.environment_sha256})["replay_allowed"])
        self.assertTrue(reconcile(spec, {"state": "FAILED", "run_id": spec.run_id, "environment_sha256": spec.environment_sha256, "cleanup_confirmed": True})["replay_allowed"])

    def test_unknown_state_requires_generation_fence(self):
        identity = ProcessIdentity(10, "boot", "b" * 64, "tree")
        state = Lifecycle().transition("STARTING").transition("START_UNKNOWN")
        with self.assertRaisesRegex(RuntimeErrorCode, "E_RUNTIME_FENCE"):
            state.transition("FAILED")
        self.assertEqual(state.transition("FAILED", expected_generation=state.generation).state, "FAILED")


if __name__ == "__main__":
    unittest.main()
