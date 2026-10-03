import hashlib
import json
import unittest
from pathlib import Path

from scripts.codekit.adapters.capability import AdapterCapability, CapabilityEvidence
from scripts.codekit.adapters.second_cli import ClaudeCodeAdapter, SecondCliError, SecondCliProfile


def synthetic_capability():
    names = ("streaming_events", "terminal_event", "model_identity", "tool_events", "usage")
    return AdapterCapability(
        "claude-code", "claude-stream-json-v1", "fixture-2.1.288", ("linux",),
        ("planner", "executor"), names, "required", "argv",
        tuple(CapabilityEvidence(name, "synthetic", note="offline fixture") for name in names), True,
    )


class SecondCliProtocolTests(unittest.TestCase):
    def setUp(self):
        self.adapter = ClaudeCodeAdapter()

    def test_probe_uses_installed_cli_without_model_request(self):
        result = self.adapter.probe(timeout=2)
        self.assertIn(result.status, {"OBSERVED_EXECUTABLE", "BLOCKED"})
        self.assertEqual(result.capability.adapter_id, "claude-code")
        self.assertNotIn("api", result.to_mapping())

    def test_profile_requires_exact_model_and_invocation_is_argv_only(self):
        profile = self.adapter.validate_profile(synthetic_capability(), role="planner", platform="linux",
                                                model_id="claude-test-model", profile_id="planner-offline",
                                                executable="claude")
        invocation = self.adapter.build_invocation(profile, request_id="req-11", run_id="run-11", cwd=".",
                                                   environment={"LANG": "C.UTF-8"}, prompt="plan")
        self.assertFalse(invocation.runtime.shell)
        self.assertIn("--output-format", invocation.runtime.command)
        self.assertEqual(invocation.adapter.adapter_id, "claude-code")
        snapshot = invocation.to_mapping()
        schema = json.loads(Path("schemas/second-cli-invocation-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(snapshot), set(schema["required"]))
        self.assertEqual(snapshot["environment_names"], ["LANG"])
        self.assertEqual(snapshot["platform"], "linux")
        with self.assertRaises(SecondCliError):
            self.adapter.validate_profile(synthetic_capability(), role="planner", platform="linux",
                                          model_id="EXACT_MODEL", profile_id="bad")
        unbound = SecondCliProfile("claude-code", "claude", "planner", "linux", "native",
                                   "claude-test-model", "unbound")
        with self.assertRaisesRegex(SecondCliError, "E_CLI_PROFILE"):
            self.adapter.build_invocation(unbound, request_id="req-11", run_id="run-11", cwd=".",
                                          environment={}, prompt="plan")

    def test_normalization_retains_raw_ref_and_model_identity(self):
        raw = b'{"type":"system","model":"claude-test-model","subtype":"init"}\n'
        event = self.adapter.normalize_event(raw, request_id="req", run_id="run", seq=1, role="planner")
        self.assertEqual(event.event_type, "run_started")
        self.assertEqual(event.actual_model, "claude-test-model")
        self.assertEqual(event.raw_record_ref["sha256"], hashlib.sha256(raw).hexdigest())
        malformed = self.adapter.normalize_event(b'{"type":', request_id="req", run_id="run", seq=2, role="planner")
        self.assertEqual(malformed.event_type, "protocol_error")

    def test_collect_requires_terminal_model_usage_and_tool_closure(self):
        records = [
            b'{"type":"system","model":"claude-test-model","subtype":"init"}\n',
            b'{"type":"assistant","model":"claude-test-model","message":{"content":[]}}\n',
            b'{"type":"result","subtype":"success","is_error":false,"model":"claude-test-model","result":{"answer":"ok"},"usage":{"input_tokens":1,"output_tokens":2}}\n',
        ]
        events = self.adapter.normalize_events(records, request_id="req", run_id="run", role="planner")
        result = self.adapter.collect_result(events, invocation_sha256="a" * 64, exit_code=0,
                                              expected_model="claude-test-model")
        self.assertTrue(result.settled)
        self.assertEqual(result.status, "SETTLED")
        self.assertEqual(result.usage["output_tokens"], 2)

        malformed = self.adapter.normalize_event(b'{"type":"future"}\n', request_id="req", run_id="run", seq=1, role="planner")
        blocked = self.adapter.collect_result((malformed,), invocation_sha256="b" * 64, exit_code=0,
                                               expected_model="claude-test-model")
        self.assertFalse(blocked.settled)
        self.assertIn("PROTOCOL_INCOMPLETE", blocked.reasons)

    def test_cli_and_provider_models_remain_separate_evidence(self):
        records = [
            b'{"type":"system","model":"cli-model","cli_model":"cli-model","provider_model":"provider-model","subtype":"init"}\n',
            b'{"type":"result","subtype":"success","is_error":false,"model":"cli-model","cli_model":"cli-model","provider_model":"provider-model","result":{"ok":true},"usage":{"output_tokens":1}}\n',
        ]
        events = self.adapter.normalize_events(records, request_id="req", run_id="run", role="planner")
        result = self.adapter.collect_result(events, invocation_sha256="a" * 64, exit_code=0,
                                              expected_model="cli-model")
        self.assertTrue(result.settled)
        self.assertEqual(result.actual_model, "cli-model")
        self.assertEqual(result.provider_model, "provider-model")

    def test_nonzero_exit_and_model_mismatch_cannot_settle(self):
        records = [b'{"type":"result","subtype":"success","is_error":false,"model":"other","result":{"ok":true},"usage":{"output_tokens":1}}\n']
        events = self.adapter.normalize_events(records, request_id="req", run_id="run", role="executor")
        result = self.adapter.collect_result(events, invocation_sha256="c" * 64, exit_code=1,
                                              expected_model="claude-test-model")
        self.assertFalse(result.settled)
        self.assertIn("NONZERO_EXIT", result.reasons)
        self.assertIn("MODEL_MISMATCH", result.reasons)


if __name__ == "__main__":
    unittest.main()
