"""Offline currentness and explicit rebuild tests for the observer runtime."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.observer_runtime import ObserverRuntime, ObserverRuntimeError  # noqa: E402


def ref(kind: str, ident: str, letter: str) -> dict[str, str]:
    return {"kind": kind, "id": ident, "sha256": letter * 64, "path": f"agent/project/{ident}.json"}


def request(brief: dict[str, str], source: dict[str, str], *, request_id: str, end: int) -> dict:
    return {
        "record_type": "observer-request", "schema_version": 1,
        "request_id": request_id, "project_id": "project-13",
        "source_cursor": {"start": 1, "end": end, "stream": "project"},
        "brief_ref": brief, "source_refs": [source],
        "output_limits": {"max_bytes": 10000, "max_items": 10},
        "profile_ref": None, "environment_ref": None,
        "timeout_seconds": 10, "max_retries": 1,
        "budget_reservation_ref": None,
    }


def output(req: dict, source: dict[str, str]) -> dict:
    return {
        "record_type": "observer-output", "schema_version": 1,
        "request_id": req["request_id"], "source_cursor": req["source_cursor"],
        "brief_ref": req["brief_ref"],
        "facts": [{"id": "fact-1", "text": "event observed", "source_refs": [source]}],
        "hypotheses": [], "risks": [], "open_questions": [],
        "suggested_next_actions": [], "omitted": [], "status": "OK",
    }


class ObserverRebuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.brief = ref("brief", "brief-1", "a")
        self.source = ref("event", "event-1", "b")

    def test_rebuild_after_new_event_uses_new_run_and_budget(self) -> None:
        runtime = ObserverRuntime("project-13", max_calls=3, max_seconds=40)
        runtime.ingest_event({"type": "first"})
        old_request = request(self.brief, self.source, request_id="req-old", end=1)
        old = runtime.submit(old_request)
        self.assertEqual(runtime.finish(old.run_id, old_request, output=output(old_request, self.source)).status, "COMPLETED")

        runtime.ingest_event({"type": "second"})
        self.assertEqual(runtime.latest().status, "STALE")
        new_request = request(self.brief, self.source, request_id="req-new", end=2)
        rebuilt = runtime.submit(new_request)
        self.assertNotEqual(rebuilt.run_id, old.run_id)
        fresh = runtime.finish(rebuilt.run_id, new_request, output=output(new_request, self.source))
        self.assertEqual(fresh.status, "COMPLETED")
        self.assertEqual(fresh.source_cursor["end"], 2)
        self.assertEqual(runtime.latest().status, "COMPLETED")
        self.assertEqual(runtime.latest().source_cursor["end"], 2)
        self.assertEqual(runtime.global_budget.used_calls, 2)

    def test_old_range_cannot_cover_new_high_water_or_overwrite_rebuild(self) -> None:
        runtime = ObserverRuntime("project-13", max_calls=3, max_seconds=40)
        runtime.ingest_event({"type": "first"})
        old_request = request(self.brief, self.source, request_id="req-old", end=1)
        old = runtime.submit(old_request)
        runtime.finish(old.run_id, old_request, output=output(old_request, self.source))
        runtime.ingest_event({"type": "second"})
        self.assertEqual(runtime.latest().status, "STALE")
        # Replaying the old input is a history lookup, not a new current result.
        replay = runtime.submit(dict(old_request, request_id="req-replay"))
        self.assertEqual(replay.run_id, old.run_id)
        self.assertEqual(runtime.latest().status, "STALE")
        self.assertEqual(runtime.latest(include_stale=True).status, "COMPLETED")

    def test_future_rebuild_cursor_is_rejected_without_consuming_budget(self) -> None:
        runtime = ObserverRuntime("project-13")
        future = request(self.brief, self.source, request_id="req-future", end=1)
        with self.assertRaisesRegex(ObserverRuntimeError, "high-water"):
            runtime.submit(future)
        self.assertEqual(runtime.global_budget.used_calls, 0)
        self.assertEqual(runtime.snapshot()["runs"], [])


if __name__ == "__main__":
    unittest.main()
