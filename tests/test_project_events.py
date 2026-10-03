import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.codekit.project_events import (
    ProjectEvent, ProjectEventError, SourceKey, event_from_mapping, validate_resource_ref,
)


def ref(name: str) -> dict[str, str]:
    return {"kind": "fixture-source", "id": name, "sha256": hashlib.sha256(name.encode()).hexdigest(),
            "path": "tests/fixtures/project_state/" + name + ".json"}


def event(**changes):
    value = dict(repository_namespace="repo", project_id="project", request_id="request",
                 event_type="attempt.prepared", subject={"task_id": "task"},
                 producer_namespace="core", source_record_id="source-1", immutable_facet_id="prepared",
                 source_ref=ref("source-1"), payload={"status": "PREPARED"}, producer_revision=1)
    value.update(changes)
    return ProjectEvent(**value)


class ProjectEventTests(unittest.TestCase):
    def test_source_key_is_stable_and_event_id_is_content_bound(self):
        key = SourceKey("repo", "core", "source-1", "prepared")
        self.assertEqual(len(key.digest), 64)
        first = event()
        self.assertEqual(first.event_id, None)
        self.assertEqual(first.derived_event_id, event().derived_event_id)
        self.assertNotEqual(first.derived_event_id, event(payload={"status": "STARTED"}).derived_event_id)

    def test_event_rejects_unknown_fields_and_unsafe_json(self):
        with self.assertRaises(ProjectEventError) as caught:
            event(payload={1: "coercion"})
        self.assertEqual(caught.exception.code, "E_JSON")
        with self.assertRaises(ProjectEventError) as caught:
            validate_resource_ref({"kind": "fixture-source", "id": "x", "sha256": "0" * 64, "extra": 1})
        self.assertEqual(caught.exception.code, "E_RESOURCE")

    def test_assigned_event_round_trips_closed_mapping(self):
        assigned = event().assigned(2, 7)
        decoded = event_from_mapping(assigned.to_mapping())
        self.assertEqual(decoded, assigned)
        with self.assertRaises(ProjectEventError):
            event_from_mapping({**assigned.to_mapping(), "extra": True})

    def test_schema_is_valid_json(self):
        value = json.loads(Path("schemas/project-event-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(value["$id"], "urn:codekit:project-event:1")


if __name__ == "__main__":
    unittest.main()
