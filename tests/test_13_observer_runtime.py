import unittest
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.observer_runtime import ObserverRuntime, ObserverRuntimeError
from codekit.observer import ObserverRequest


def ref(kind, ident, byte):
    return {"kind": kind, "id": ident, "sha256": byte * 64, "path": f"agent/project/{ident}.json"}


class ObserverRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.brief = ref("brief", "brief-1", "a")
        self.source = ref("event", "event-1", "b")
        self.request = {
            "record_type": "observer-request", "schema_version": 1,
            "request_id": "req-1", "project_id": "project-1",
            "source_cursor": {"start": 1, "end": 1, "stream": "project"},
            "brief_ref": self.brief, "source_refs": [self.source],
            "output_limits": {"max_bytes": 10000, "max_items": 10},
            "profile_ref": None, "environment_ref": None,
            "timeout_seconds": 10, "max_retries": 1,
            "budget_reservation_ref": None,
        }

    def output(self, request=None, end=1):
        request = request or self.request
        return {
            "record_type": "observer-output", "schema_version": 1,
            "request_id": request["request_id"],
            "source_cursor": {"start": 1, "end": end, "stream": "project"},
            "brief_ref": self.brief,
            "facts": [{"id": "fact-1", "text": "observed change", "source_refs": [self.source]}],
            "hypotheses": [], "risks": [], "open_questions": [],
            "suggested_next_actions": [], "omitted": [], "status": "OK",
        }

    def test_same_input_single_flight_and_replay(self):
        rt = ObserverRuntime("project-1", max_calls=3, max_seconds=30)
        rt.ingest_event({"type": "changed"})
        first = rt.submit(self.request)
        replay = rt.submit(dict(self.request, request_id="req-2"))
        self.assertEqual(first.run_id, replay.run_id)
        self.assertEqual(rt.global_budget.used_calls, 1)
        done = rt.finish(first.run_id, self.request, output=self.output())
        self.assertEqual(done.status, "COMPLETED")
        self.assertEqual(rt.submit(self.request).run_id, first.run_id)

    def test_high_water_stale_summary_does_not_cover_new_event(self):
        rt = ObserverRuntime("project-1")
        rt.ingest_event({"type": "changed"})
        run = rt.submit(self.request)
        rt.finish(run.run_id, self.request, output=self.output())
        rt.ingest_event({"type": "new"})
        self.assertEqual(rt.latest().status, "STALE")
        self.assertEqual(rt.latest().source_cursor["end"], 1)
        self.assertEqual(rt.high_water, 2)

    def test_response_loss_unknown_cost_stops_admission(self):
        rt = ObserverRuntime("project-1")
        rt.ingest_event({"type": "changed"})
        run = rt.submit(self.request)
        self.assertEqual(rt.finish(run.run_id, self.request, outcome="response_lost").status, "RESPONSE_LOST")
        self.assertTrue(rt.global_budget.unknown_cost)
        self.assertTrue(rt.global_budget.stopped)
        with self.assertRaisesRegex(ObserverRuntimeError, "stopped"):
            rt.submit(dict(self.request, request_id="req-3"))

    def test_timeout_cancel_do_not_mutate_project_state(self):
        rt = ObserverRuntime("project-1")
        rt.ingest_event({"type": "changed"})
        before = rt.project_state
        run = rt.submit(self.request)
        self.assertEqual(rt.finish(run.run_id, self.request, outcome="timeout").status, "TIMED_OUT")
        self.assertTrue(rt.global_budget.unknown_cost)
        self.assertTrue(rt.global_budget.stopped)
        self.assertIs(before, rt.project_state)

    def test_future_request_and_output_cursor_rejected(self):
        rt = ObserverRuntime("project-1")
        with self.assertRaises(ObserverRuntimeError):
            rt.submit(self.request)
        rt.ingest_event({"type": "changed"})
        run = rt.submit(self.request)
        with self.assertRaises(ObserverRuntimeError):
            rt.finish(run.run_id, self.request, output=self.output(end=2))

    def test_budget_reservation_is_consumed_even_after_failure(self):
        rt = ObserverRuntime("project-1", max_calls=1, max_seconds=10)
        rt.ingest_event({"type": "changed"})
        run = rt.submit(self.request)
        rt.finish(run.run_id, self.request, outcome="cancelled")
        self.assertEqual(rt.global_budget.used_calls, 1)
        with self.assertRaises(ObserverRuntimeError):
            rt.submit(dict(self.request, request_id="req-2"))

    def test_cancel_without_cost_is_unknown_liability(self):
        rt = ObserverRuntime("project-1")
        rt.ingest_event({"type": "changed"})
        run = rt.submit(self.request)
        self.assertEqual(rt.finish(run.run_id, self.request, outcome="cancelled").status, "CANCELLED")
        self.assertTrue(rt.global_budget.unknown_cost)
        self.assertTrue(rt.global_budget.stopped)

    def test_late_success_is_classified_as_timeout(self):
        rt = ObserverRuntime("project-1")
        rt.ingest_event({"type": "changed"})
        run = rt.submit(self.request)
        ended = rt.finish(run.run_id, self.request, output=self.output(), elapsed_seconds=11)
        self.assertEqual(ended.status, "TIMED_OUT")
        self.assertIsNone(ended.result)

    def test_compatibility_facade_validates_resource_refs(self):
        request = ObserverRequest(
            request_id="req-1", project_id="project-1", source_start=1, source_end=1,
            brief_ref=self.brief, source_refs=(self.source,),
        )
        self.assertEqual(request.dedupe_key, ObserverRequest(
            request_id="req-2", project_id="project-1", source_start=1, source_end=1,
            brief_ref=self.brief, source_refs=(self.source,),
        ).dedupe_key)


if __name__ == "__main__":
    unittest.main()
