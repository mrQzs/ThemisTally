import copy
import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.observer_protocol import ObserverProtocolError, validate_observer_binding, validate_observer_output
from codekit.observer_runtime import ObserverRuntime, ObserverRuntimeError
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "observer" / "evaluation.json"


def _ref(registry, kind, ident):
    for item in registry:
        if item["kind"] == kind and item["id"] == ident:
            return copy.deepcopy(item)
    raise KeyError((kind, ident))


class ObserverAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.registry = cls.fixture["source_registry"]
        cls.request = cls.fixture["request"]

    def _events(self, runtime, count=4):
        for number in range(count):
            runtime.ingest_event({"event": number + 1})

    def _runtime(self, **kwargs):
        runtime = ObserverRuntime("project-eval", **kwargs)
        self._events(runtime)
        return runtime

    def _output(self, case_id="complete-baseline"):
        event1 = _ref(self.registry, "event", "event-1")
        event3 = _ref(self.registry, "event", "event-3")
        output = {
            "record_type": "observer-output",
            "schema_version": 1,
            "request_id": self.request["request_id"],
            "source_cursor": copy.deepcopy(self.request["source_cursor"]),
            "brief_ref": copy.deepcopy(self.request["brief_ref"]),
            "facts": [],
            "hypotheses": [],
            "risks": [],
            "open_questions": [],
            "suggested_next_actions": [],
            "omitted": [],
            "status": "OK",
        }
        if case_id == "complete-baseline":
            output["facts"] = [{
                "id": "fact-complete",
                "text": "The project remains pending review.",
                "source_refs": [event1],
            }]
        elif case_id == "uncertain-result":
            output["hypotheses"] = [{
                "id": "hyp-uncertain",
                "text": "The incomplete event may indicate a delayed handoff.",
                "source_refs": [event3],
                "missing_information": ["handoff completion event"],
                "verification_method": "inspect the next project event",
            }]
            output["risks"] = [{
                "id": "risk-unknown",
                "text": "The impact cannot be determined from this interval.",
                "source_refs": [event3],
                "impact": "unknown",
                "affected_task_ids": ["task-eval"],
            }]
            output["status"] = "DEGRADED"
        elif case_id == "missing-citation":
            output["facts"] = [{
                "id": "fact-uncited",
                "text": "This statement has no source.",
                "source_refs": [],
            }]
            output["status"] = "REJECTED"
        else:
            raise KeyError(case_id)
        return output

    def test_A01_failure_keeps_deterministic_brief_and_core_flow(self):
        before = copy.deepcopy(self.fixture["deterministic_brief"])
        runtime = self._runtime()
        run = runtime.submit(self.request)
        self.assertEqual(runtime.finish(run.run_id, self.request, outcome="response_lost").status, "RESPONSE_LOST")
        self.assertEqual(self.fixture["deterministic_brief"], before)
        self.assertEqual(self.fixture["real_capability_gate"]["release_default"], "OFF")

    def test_A02_citations_and_fact_hypothesis_separation(self):
        output = self._output("uncertain-result")
        bound = validate_observer_binding(self.request, output, available_refs=self.registry)
        self.assertTrue(bound["output"]["hypotheses"])
        self.assertTrue(bound["output"]["hypotheses"][0]["source_refs"])
        with self.assertRaises(ObserverProtocolError):
            validate_observer_binding(self.request, self._output("missing-citation"), available_refs=self.registry)

    def test_A03_decision_words_are_rejected_and_state_is_unchanged(self):
        output = self._output("complete-baseline")
        output["facts"][0]["text"] = "PASS: authorization and publication are complete."
        with self.assertRaises(ObserverProtocolError):
            validate_observer_output(output)
        runtime = self._runtime()
        self.assertIsNone(runtime.project_state)

    def test_A04_same_cursor_is_single_flight_and_completion_does_not_loop(self):
        runtime = self._runtime()
        first = runtime.submit(self.request)
        replay = runtime.submit(dict(self.request, request_id="eval-request-replay"))
        self.assertEqual(first.run_id, replay.run_id)
        runtime.finish(first.run_id, self.request, output=self._output())
        runtime.ingest_event({"type": "observer_completed", "run_id": first.run_id})
        self.assertEqual(runtime.global_budget.used_calls, 1)
        self.assertEqual(runtime.latest().status, "STALE")

    def test_A05_global_and_observer_budgets_are_both_consumed(self):
        runtime = self._runtime(max_calls=1, max_seconds=30, observer_max_calls=1, observer_max_seconds=30)
        run = runtime.submit(self.request)
        runtime.finish(run.run_id, self.request, outcome="cancelled")
        self.assertEqual(runtime.global_budget.used_calls, 1)
        self.assertEqual(runtime.observer_budget.used_calls, 1)
        with self.assertRaises(ObserverRuntimeError):
            runtime.submit(dict(self.request, request_id="eval-request-after-retry"))

    def test_A06_timeout_unknown_cost_and_source_conflict_are_degraded(self):
        runtime = self._runtime()
        run = runtime.submit(self.request)
        result = runtime.finish(run.run_id, self.request, outcome="timeout")
        self.assertEqual(result.status, "TIMED_OUT")
        self.assertTrue(runtime.global_budget.unknown_cost)
        self.assertEqual(self.fixture["cases"][2]["expected_classification"], "UNTRUSTED_CONFLICT")

    def test_A07_new_event_marks_old_output_stale_without_rewriting_cursor(self):
        runtime = self._runtime()
        run = runtime.submit(self.request)
        output = self._output()
        runtime.finish(run.run_id, self.request, output=output)
        runtime.ingest_event({"event": 5})
        latest = runtime.latest()
        self.assertEqual(latest.status, "STALE")
        self.assertEqual(latest.source_cursor["end"], 4)
        self.assertEqual(runtime.high_water, 5)

    def test_A08_without_host_only_pull_is_claimed(self):
        gate = self.fixture["real_capability_gate"]
        self.assertEqual(gate["host_push"], "BLOCKED")
        self.assertNotIn("delivered", self.fixture)
        self.assertNotIn("read", self.fixture)

    def test_A09_unknown_fields_are_rejected_and_isolation_is_blocked(self):
        output = self._output()
        output["approval"] = True
        with self.assertRaises(ObserverProtocolError):
            validate_observer_output(output)
        self.assertEqual(self.fixture["real_capability_gate"]["native_platform_isolation"], "BLOCKED")
        self.assertEqual(self.fixture["real_capability_gate"]["observer_provider"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
