"""Offline projection checks for the optional read-only observer.

These tests deliberately use only the deterministic project-view and observer
runtime boundaries.  They prove that a brief remains readable while an
observer result is pulled, and that stale or unavailable observer data cannot
change the project projection.
"""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.observer_runtime import ObserverRuntime  # noqa: E402
from codekit.project_delivery import request_pull_delivery  # noqa: E402
from codekit.project_views import ViewPackageStore, render_project_brief  # noqa: E402


STATE = {
    "indexed_cursor": 1,
    "applied_cursor": 1,
    "source_coverage": "complete",
    "budget_coverage": "complete",
    "verification_ref": "verify-13",
    "as_of": "2026-10-04T00:00:00Z",
    "tasks": {"task-1": {"status": "COMPLETED"}},
    "decisions": {},
    "budgets": {},
    "issues": [],
    "dispatch_eligibility": "not_evaluated",
}


def _ref(kind: str, ident: str, digest_letter: str) -> dict[str, str]:
    return {
        "kind": kind,
        "id": ident,
        "sha256": digest_letter * 64,
        "path": f"agent/project/{ident}.json",
    }


def _request(brief_ref: dict[str, str], source_ref: dict[str, str], *, request_id: str = "req-1", end: int = 1) -> dict:
    return {
        "record_type": "observer-request",
        "schema_version": 1,
        "request_id": request_id,
        "project_id": "project-13",
        "source_cursor": {"start": 1, "end": end, "stream": "project"},
        "brief_ref": brief_ref,
        "source_refs": [source_ref],
        "output_limits": {"max_bytes": 10000, "max_items": 10},
        "profile_ref": None,
        "environment_ref": None,
        "timeout_seconds": 10,
        "max_retries": 1,
        "budget_reservation_ref": None,
    }


def _output(request: dict, source_ref: dict[str, str]) -> dict:
    return {
        "record_type": "observer-output",
        "schema_version": 1,
        "request_id": request["request_id"],
        "source_cursor": request["source_cursor"],
        "brief_ref": request["brief_ref"],
        "facts": [{"id": "fact-1", "text": "observed event", "source_refs": [source_ref]}],
        "hypotheses": [],
        "risks": [],
        "open_questions": [],
        "suggested_next_actions": [],
        "omitted": [],
        "status": "OK",
    }


class ObserverProjectionTests(unittest.TestCase):
    def test_brief_remains_readable_when_current_observer_result_is_pulled(self) -> None:
        brief_ref = _ref("brief", "brief-1", "a")
        source_ref = _ref("event", "event-1", "b")
        runtime = ObserverRuntime("project-13")
        runtime.ingest_event({"type": "changed"})
        request = _request(brief_ref, source_ref)
        run = runtime.submit(request)
        result = runtime.finish(run.run_id, request, output=_output(request, source_ref))

        with tempfile.TemporaryDirectory() as tmp:
            store = ViewPackageStore(tmp)
            brief = render_project_brief(STATE)
            manifest = store.publish(STATE, brief, generation=1, cursor=1)
            before = (Path(tmp) / "current.json").read_bytes()
            loaded_manifest, loaded_state, loaded_brief = store.read_current()
            self.assertEqual(loaded_manifest, manifest)
            self.assertEqual(loaded_state, STATE)
            self.assertEqual(loaded_brief, brief)
            self.assertEqual(result.status, "COMPLETED")
            self.assertEqual(runtime.latest().source_cursor["end"], manifest.cursor)
            # Pulling observer data has no write capability over the project view.
            self.assertIsNone(runtime.project_state)
            self.assertEqual((Path(tmp) / "current.json").read_bytes(), before)

    def test_new_events_make_old_observer_projection_untrusted_and_pull_stays_available(self) -> None:
        brief_ref = _ref("brief", "brief-1", "a")
        source_ref = _ref("event", "event-1", "b")
        runtime = ObserverRuntime("project-13")
        runtime.ingest_event({"type": "changed"})
        request = _request(brief_ref, source_ref)
        run = runtime.submit(request)
        runtime.finish(run.run_id, request, output=_output(request, source_ref))
        runtime.ingest_event({"type": "new"})

        stale = runtime.latest()
        self.assertIsNotNone(stale)
        self.assertEqual(stale.status, "STALE")
        self.assertEqual(stale.failure_code, "NEW_EVENTS_AFTER_RESULT")
        self.assertEqual(stale.source_cursor["end"], 1)
        delivery = request_pull_delivery("a" * 64, observer_ref="observer-13")
        self.assertEqual(delivery.mode, "pull")
        self.assertEqual(delivery.status, "NOT_RUN")

    def test_pull_rejects_non_pull_mode_without_changing_runtime(self) -> None:
        runtime = ObserverRuntime("project-13")
        before = runtime.snapshot()
        with self.assertRaisesRegex(ValueError, "10 only supports pull"):
            request_pull_delivery("a" * 64, observer_ref="observer-13", mode="push")
        self.assertEqual(runtime.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
