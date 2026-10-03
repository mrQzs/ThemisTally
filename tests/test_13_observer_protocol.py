import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.observer_protocol import (
    ObserverProtocolError,
    strict_observer_json_loads,
    validate_observer_binding,
    validate_observer_output,
    validate_observer_request,
    validate_observer_source_ref,
)


def ref(kind, ident, digest):
    return {"kind": kind, "id": ident, "sha256": digest * 64, "path": f"agent/project/{ident}.json"}


class ObserverProtocolTests(unittest.TestCase):
    def setUp(self):
        self.brief = ref("brief", "brief-1", "a")
        self.source = ref("event", "event-1", "b")
        self.request = {
            "record_type": "observer-request", "schema_version": 1,
            "request_id": "req-1", "project_id": "project-1",
            "source_cursor": {"start": 1, "end": 3, "stream": "events"},
            "brief_ref": self.brief, "source_refs": [self.source],
            "output_limits": {"max_bytes": 4096, "max_items": 10, "max_text": 1024},
            "profile_ref": None, "environment_ref": None,
            "timeout_seconds": 10, "max_retries": 1, "budget_reservation_ref": None,
            "trigger": "explicit_request",
        }

    def output(self):
        return {
            "record_type": "observer-output", "schema_version": 1,
            "request_id": "req-1", "source_cursor": {"start": 1, "end": 3, "stream": "events"},
            "brief_ref": self.brief,
            "facts": [{"id": "fact-1", "text": "one fact", "source_refs": [self.source]}],
            "hypotheses": [{"id": "hyp-1", "text": "check this", "source_refs": [self.source],
                            "missing_information": ["confirm event"], "verification_method": "read source event"}],
            "risks": [{"id": "risk-1", "text": "may be delayed", "source_refs": [self.source],
                       "impact": "medium", "affected_task_ids": ["task-1"]}],
            "open_questions": [{"id": "question-1", "text": "what changed?", "source_refs": [self.source],
                                "affected_task_ids": ["task-1"]}],
            "suggested_next_actions": [{"id": "action-1", "text": "review event", "source_refs": [self.source],
                                        "affected_task_ids": ["task-1"], "requires_authorization": True}],
            "omitted": [{"id": "omitted-1", "reason": "output limit", "item_ids": ["event-2"]}],
            "status": "PARTIAL",
        }

    def test_request_and_bound_output_are_closed_and_traceable(self):
        self.assertEqual(validate_observer_request(self.request)["request_id"], "req-1")
        result = validate_observer_binding(self.request, self.output(), available_refs=[self.brief, self.source])
        self.assertEqual(result["output"]["source_cursor"]["end"], 3)

    def test_unknown_or_out_of_scope_source_is_rejected(self):
        output = self.output()
        output["facts"][0]["source_refs"] = [ref("event", "event-2", "c")]
        with self.assertRaises(ObserverProtocolError):
            validate_observer_binding(self.request, output)

    def test_missing_fact_citation_and_unknown_fields_are_rejected(self):
        output = self.output()
        output["facts"][0]["source_refs"] = []
        with self.assertRaises(ObserverProtocolError):
            validate_observer_output(output)
        output = self.output(); output["facts"][0]["approval"] = True
        with self.assertRaises(ObserverProtocolError):
            validate_observer_output(output)

    def test_fake_pass_or_authorization_cannot_enter_suggestion(self):
        output = self.output(); output["suggested_next_actions"][0]["text"] = "PASS and publish this"
        with self.assertRaises(ObserverProtocolError):
            validate_observer_output(output)
        output = self.output(); output["status"] = "PASS"
        with self.assertRaises(ObserverProtocolError):
            validate_observer_output(output)

    def test_cursor_and_brief_are_bound_to_request(self):
        output = self.output(); output["source_cursor"]["end"] = 4
        with self.assertRaises(ObserverProtocolError):
            validate_observer_binding(self.request, output)
        output = self.output(); output["brief_ref"] = ref("brief", "other", "d")
        with self.assertRaises(ObserverProtocolError):
            validate_observer_binding(self.request, output)

    def test_strict_json_rejects_duplicate_keys_and_non_object(self):
        with self.assertRaises(ObserverProtocolError):
            strict_observer_json_loads(b'{"record_type":"observer-output","record_type":"x"}')
        with self.assertRaises(ObserverProtocolError):
            strict_observer_json_loads(b"[]")

    def test_source_registry_can_verify_exact_bytes(self):
        payload = b"observer source\n"
        digest = hashlib.sha256(payload).hexdigest()
        exact = {"kind": "event", "id": "event-1", "sha256": digest, "path": "agent/project/event-1.json"}
        self.assertEqual(validate_observer_source_ref(exact, source_bytes=payload), exact)
        with self.assertRaises(ObserverProtocolError):
            validate_observer_source_ref(exact, source_bytes=b"changed")


if __name__ == "__main__":
    unittest.main()
