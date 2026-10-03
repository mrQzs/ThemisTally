"""Schema and failure fixtures for the second CLI boundary.

The Windows test image intentionally has no jsonschema dependency.  These
tests therefore verify the generated records against the closed schema shape
and the same field/constant rules enforced by the record constructors.  They
also exercise the negative stream cases which must remain blocked offline.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from scripts.codekit.adapters.capability import AdapterCapability, CapabilityEvidence
from scripts.codekit.adapters.heterogeneous import CancellationObservation, ProfileHandoff
from scripts.codekit.adapters.second_cli import ClaudeCodeAdapter, ProbeResult, RawRecordStore, SecondCliError


ROOT = Path(__file__).resolve().parents[1]


def _ref(name: str, payload: bytes = b"fixture\n") -> dict[str, str]:
    return {
        "kind": "fixture",
        "id": name,
        "path": "fixtures/" + name + ".json",
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _capability() -> AdapterCapability:
    names = ("streaming_events", "terminal_event", "model_identity", "tool_events", "usage")
    return AdapterCapability(
        "claude-code",
        "claude-stream-json-v1",
        "fixture-2.1.288",
        ("linux",),
        ("planner", "executor", "observer"),
        names,
        "required",
        "argv",
        tuple(CapabilityEvidence(name, "synthetic", note="offline fixture") for name in names),
        False,
        ("native",),
    )


def _assert_closed(test: unittest.TestCase, record: dict, schema_name: str) -> None:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    required = set(schema["required"])
    test.assertEqual(set(record), required, schema_name)
    test.assertFalse(schema["additionalProperties"], schema_name)
    if "schema_version" in schema["properties"]:
        test.assertEqual(schema["properties"]["schema_version"]["const"], 1)


class SecondCliSchemaFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = ClaudeCodeAdapter()

    def test_all_public_record_mappings_are_closed_and_versioned(self) -> None:
        capability = _capability()
        probe = ProbeResult(
            capability,
            "claude",
            b"Claude Code 2.1.288\n",
            b"Usage: claude --print --output-format stream-json\n",
            0,
            0,
            "OBSERVED_EXECUTABLE",
        )
        _assert_closed(self, capability.to_mapping(), "adapter-capability-v1.schema.json")
        _assert_closed(self, probe.to_mapping(), "second-cli-probe-v1.schema.json")

        event = self.adapter.normalize_event(
            b'{"type":"system","model":"fixture-model","subtype":"init"}\n',
            request_id="req",
            run_id="run",
            seq=1,
            role="planner",
        )
        event_record = {
            "request_id": event.request_id,
            "run_id": event.run_id,
            "seq": event.seq,
            "role": event.role,
            "event_id": event.event_id,
            "event_type": event.event_type,
            "payload": dict(event.payload),
            "raw_record_ref": dict(event.raw_record_ref),
            "raw_start": event.raw_start,
            "raw_end": event.raw_end,
            "adapter_revision": event.adapter_revision,
            "actual_model": event.actual_model,
            "terminal": event.terminal,
            "complete": event.complete,
            "tool_id": event.tool_id,
            "cli_model": event.cli_model,
            "provider_model": event.provider_model,
        }
        _assert_closed(self, event_record, "second-cli-event-v1.schema.json")

        handoff = ProfileHandoff(
            "req",
            "run",
            "planner-profile",
            "executor-profile",
            "planner-session",
            "executor-session",
            _ref("contract"),
            (_ref("input"),),
            2,
        )
        _assert_closed(self, handoff.to_mapping(), "second-cli-handoff-v1.schema.json")

        recovery = CancellationObservation.classify(
            request_id="req",
            run_id="run",
            generation=2,
            cancel_requested=True,
            exit_code=None,
            response_lost=True,
            process_observed=None,
        )
        _assert_closed(self, recovery.to_mapping(), "second-cli-recovery-v1.schema.json")

    def test_schema_files_have_closed_root_and_resource_ref_shape(self) -> None:
        for name in (
            "adapter-capability-v1.schema.json",
            "second-cli-event-v1.schema.json",
            "second-cli-probe-v1.schema.json",
            "second-cli-handoff-v1.schema.json",
            "second-cli-recovery-v1.schema.json",
            "second-cli-probe-manifest-v1.schema.json",
        ):
            schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertFalse(schema["additionalProperties"], name)
            if name != "second-cli-event-v1.schema.json":
                self.assertIn("record_type", schema["required"])
                self.assertIn("schema_version", schema["required"])
        handoff_schema = json.loads(
            (ROOT / "schemas" / "second-cli-handoff-v1.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            handoff_schema["$defs"]["resource_ref"]["required"],
            ["kind", "id", "path", "sha256"],
        )

    def test_local_probe_manifest_hashes_are_reproducible_and_non_production(self) -> None:
        manifest_path = ROOT / "tests" / "fixtures" / "11" / "claude-probe-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _assert_closed(self, manifest, "second-cli-probe-manifest-v1.schema.json")
        for evidence in (manifest["version_evidence"], manifest["help_evidence"]):
            raw = (ROOT / evidence["path"]).read_bytes()
            self.assertEqual(len(raw), evidence["bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), evidence["sha256"])
            self.assertEqual(evidence["exit_code"], 0)
        self.assertEqual(manifest["model_status"], "NOT_RUN")
        self.assertEqual(manifest["provider_status"], "NOT_RUN")
        self.assertEqual(manifest["authentication_status"], "NOT_INSPECTED")

    def test_unknown_usage_is_blocked_and_does_not_settle(self) -> None:
        records = [
            b'{"type":"system","model":"fixture-model","subtype":"init"}\n',
            b'{"type":"result","subtype":"success","is_error":false,"model":"fixture-model","result":{"ok":true}}\n',
        ]
        events = self.adapter.normalize_events(records, request_id="req", run_id="run", role="planner")
        result = self.adapter.collect_result(
            events,
            invocation_sha256="a" * 64,
            exit_code=0,
            expected_model="fixture-model",
        )
        self.assertFalse(result.settled)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertIn("USAGE_UNKNOWN", result.reasons)
        self.assertEqual(dict(result.usage), {})

    def test_repeated_terminal_results_are_ambiguous(self) -> None:
        records = [
            b'{"type":"system","model":"fixture-model","subtype":"init"}\n',
            b'{"type":"result","subtype":"success","is_error":false,"model":"fixture-model","result":{"answer":"one"},"usage":{"output_tokens":1}}\n',
            b'{"type":"result","subtype":"success","is_error":false,"model":"fixture-model","result":{"answer":"two"},"usage":{"output_tokens":2}}\n',
        ]
        events = self.adapter.normalize_events(records, request_id="req", run_id="run", role="planner")
        result = self.adapter.collect_result(
            events,
            invocation_sha256="b" * 64,
            exit_code=0,
            expected_model="fixture-model",
        )
        self.assertFalse(result.settled)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("TERMINAL_AMBIGUOUS", result.reasons)

    def test_exact_replayed_raw_record_is_rejected_before_collection(self) -> None:
        record = b'{"type":"system","model":"fixture-model","subtype":"init"}\n'
        with self.assertRaisesRegex(SecondCliError, "E_CLI_EVENT_DUPLICATE"):
            self.adapter.normalize_events((record, record), request_id="req", run_id="run", role="planner")

    def test_truncated_unknown_and_response_loss_remain_unsettled(self) -> None:
        malformed = self.adapter.normalize_event(
            b'{"type":"result","subtype":"success"',
            request_id="req",
            run_id="run",
            seq=1,
            role="planner",
        )
        self.assertEqual(malformed.event_type, "protocol_error")
        self.assertFalse(malformed.complete)
        blocked = self.adapter.collect_result(
            (malformed,),
            invocation_sha256="c" * 64,
            exit_code=0,
            expected_model="fixture-model",
        )
        self.assertFalse(blocked.settled)
        self.assertIn("PROTOCOL_INCOMPLETE", blocked.reasons)

        unknown = self.adapter.normalize_event(
            b'{"type":"future-event","model":"fixture-model"}\n',
            request_id="req",
            run_id="run",
            seq=1,
            role="planner",
        )
        self.assertEqual(unknown.event_type, "unknown")
        lost = self.adapter.collect_result(
            (unknown,),
            invocation_sha256="d" * 64,
            exit_code=None,
            expected_model="fixture-model",
            response_lost=True,
        )
        self.assertFalse(lost.settled)
        self.assertEqual(lost.status, "UNKNOWN")
        self.assertIn("RESPONSE_LOST", lost.reasons)

    def test_raw_record_store_verifies_ref_range_and_drift(self) -> None:
        raw = b'{"type":"system","model":"fixture-model"}\n'
        store = RawRecordStore()
        ref = store.add(raw, raw_path="stdout/record.jsonl", record_id="record-1")
        self.assertEqual(store.verify(ref, raw_start=0, raw_end=len(raw)), raw)
        with self.assertRaisesRegex(SecondCliError, "E_CLI_RAW_REPLAY"):
            store.add(raw + b"x", raw_path="stdout/record.jsonl", record_id="record-1")
        with self.assertRaisesRegex(SecondCliError, "E_CLI_RAW_DRIFT"):
            store.verify(ref, raw_start=0, raw_end=len(raw), expected_bytes=raw + b"x")
        with self.assertRaisesRegex(SecondCliError, "E_CLI_RAW_MISSING"):
            store.verify(dict(ref, id="missing"), raw_start=0, raw_end=len(raw))

    def test_terminal_after_event_and_unhashable_type_are_blocked(self) -> None:
        records = [
            b'{"type":"result","subtype":"success","is_error":false,"model":"fixture-model","result":{"ok":true},"usage":{"output_tokens":1}}\n',
            b'{"type":"assistant","model":"fixture-model","message":{"content":[]}}\n',
        ]
        events = self.adapter.normalize_events(records, request_id="req", run_id="run", role="planner")
        result = self.adapter.collect_result(events, invocation_sha256="e" * 64, exit_code=0,
                                             expected_model="fixture-model")
        self.assertFalse(result.settled)
        self.assertIn("TERMINAL_NOT_FINAL", result.reasons)
        unhashable = self.adapter.normalize_event(b'{"type":[]}', request_id="req", run_id="run", seq=1, role="planner")
        self.assertEqual(unhashable.event_type, "unknown")


if __name__ == "__main__":
    unittest.main()
