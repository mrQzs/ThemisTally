import copy
import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.observer_protocol import ObserverProtocolError, validate_observer_binding
from codekit.observer_runtime import ObserverRuntime, ObserverRuntimeError


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "observer" / "evaluation.json"


def _ref(registry, kind, ident):
    for item in registry:
        if item["kind"] == kind and item["id"] == ident:
            return copy.deepcopy(item)
    raise KeyError((kind, ident))


class ObserverEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.registry = cls.fixture["source_registry"]
        cls.request = cls.fixture["request"]
        cls.brief = _ref(cls.registry, "brief", "brief-eval")

    def _event(self, ident):
        return _ref(self.registry, "event", ident)

    def _output(self, case_id):
        event1 = self._event("event-1")
        event2 = self._event("event-2")
        event3 = self._event("event-3")
        base = {
            "record_type": "observer-output",
            "schema_version": 1,
            "request_id": self.request["request_id"],
            "source_cursor": copy.deepcopy(self.request["source_cursor"]),
            "brief_ref": copy.deepcopy(self.brief),
            "facts": [],
            "hypotheses": [],
            "risks": [],
            "open_questions": [],
            "suggested_next_actions": [],
            "omitted": [],
            "status": "OK",
        }
        if case_id == "complete-baseline":
            base["facts"] = [{
                "id": "fact-complete",
                "text": "The project remains pending review.",
                "source_refs": [event1],
            }]
        elif case_id == "omitted-item":
            base["facts"] = [{
                "id": "fact-omitted",
                "text": "The first two events were reviewed.",
                "source_refs": [event1, event2],
            }]
            base["omitted"] = [{
                "id": "omitted-event-3",
                "reason": "output limit",
                "source_refs": [event3],
                "item_ids": ["event-3"],
            }]
            base["status"] = "PARTIAL"
        elif case_id == "conflicting-fact":
            base["facts"] = [{
                "id": "fact-conflict",
                "text": "The project is complete and needs no review.",
                "source_refs": [event1],
            }]
            base["status"] = "DEGRADED"
        elif case_id == "uncertain-result":
            base["hypotheses"] = [{
                "id": "hyp-uncertain",
                "text": "The incomplete event may indicate a delayed handoff.",
                "source_refs": [event3],
                "missing_information": ["handoff completion event"],
                "verification_method": "inspect the next project event",
            }]
            base["risks"] = [{
                "id": "risk-unknown",
                "text": "The impact cannot be determined from this interval.",
                "source_refs": [event3],
                "impact": "unknown",
                "affected_task_ids": ["task-eval"],
            }]
            base["status"] = "DEGRADED"
        elif case_id == "missing-citation":
            base["facts"] = [{
                "id": "fact-uncited",
                "text": "This statement has no source.",
                "source_refs": [],
            }]
            base["status"] = "REJECTED"
        elif case_id == "out-of-scope-source":
            base["facts"] = [{
                "id": "fact-outside",
                "text": "This source is outside the request.",
                "source_refs": [{
                    "kind": "event",
                    "id": "event-outside",
                    "sha256": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                    "path": "agent/project/event-outside.json",
                }],
            }]
            base["status"] = "REJECTED"
        else:
            raise KeyError(case_id)
        return base

    @staticmethod
    def _classify(output, brief):
        if output["omitted"]:
            return "OMITTED_WITH_REASON"
        texts = " ".join(item["text"].lower() for item in output["facts"])
        if brief["state"] == "pending" and "complete" in texts:
            return "UNTRUSTED_CONFLICT"
        if output["hypotheses"] or any(item.get("impact") == "unknown" for item in output["risks"]):
            return "UNCERTAIN"
        return "CORRECT"

    def test_fixture_is_closed_and_has_required_value_categories(self):
        self.assertEqual(self.fixture["schema_version"], 1)
        self.assertEqual(self.fixture["measurement_status"], "NOT_RUN")
        categories = {case["category"] for case in self.fixture["cases"]}
        self.assertTrue({"omission", "conflict", "duplicate", "uncertain"}.issubset(categories))
        self.assertEqual(len({case["case_id"] for case in self.fixture["cases"]}), len(self.fixture["cases"]))

    def test_fixed_outputs_are_cited_and_classified_without_claiming_savings(self):
        expected = {
            "complete-baseline": "CORRECT",
            "omitted-item": "OMITTED_WITH_REASON",
            "conflicting-fact": "UNTRUSTED_CONFLICT",
            "uncertain-result": "UNCERTAIN",
        }
        for case_id, classification in expected.items():
            output = self._output(case_id)
            result = validate_observer_binding(self.request, output, available_refs=self.registry)
            self.assertEqual(self._classify(result["output"], self.fixture["deterministic_brief"]), classification)
        self.assertEqual(self.fixture["measurement_status"], "NOT_RUN")
        self.assertNotIn("token_savings", self.fixture)
        self.assertNotIn("production_pass", self.fixture)

    def test_missing_or_out_of_scope_citations_are_rejected(self):
        with self.assertRaises(ObserverProtocolError):
            validate_observer_binding(self.request, self._output("missing-citation"), available_refs=self.registry)
        with self.assertRaises(ObserverProtocolError):
            validate_observer_binding(self.request, self._output("out-of-scope-source"), available_refs=self.registry)

    def test_duplicate_input_consumes_one_reserved_run(self):
        runtime = ObserverRuntime("project-eval", max_calls=3, max_seconds=60)
        for number in range(4):
            runtime.ingest_event({"event": number + 1})
        first = runtime.submit(self.request)
        replay = runtime.submit(dict(self.request, request_id="eval-request-replay"))
        self.assertEqual(first.run_id, replay.run_id)
        self.assertEqual(runtime.global_budget.used_calls, 1)
        self.assertEqual(runtime.observer_budget.used_calls, 1)

    def test_unknown_cost_is_degraded_and_stops_new_admission(self):
        runtime = ObserverRuntime("project-eval")
        for number in range(4):
            runtime.ingest_event({"event": number + 1})
        run = runtime.submit(self.request)
        result = runtime.finish(run.run_id, self.request, outcome="response_lost")
        self.assertEqual(result.status, "RESPONSE_LOST")
        self.assertTrue(runtime.global_budget.unknown_cost)
        self.assertTrue(runtime.global_budget.stopped)
        with self.assertRaises(ObserverRuntimeError):
            runtime.submit(dict(self.request, request_id="eval-request-after-loss"))


if __name__ == "__main__":
    unittest.main()
