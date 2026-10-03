import json
import unittest
from pathlib import Path

from scripts.codekit.project_requests import project_request
from tests.test_project_events import event


class ProjectRequestTests(unittest.TestCase):
    def test_exact_mapping_keeps_missing_request_ids_unknown(self):
        events = [event(request_id="request-1").assigned(1, 1),
                  event(request_id=None, source_record_id="unknown", immutable_facet_id="facet-unknown").assigned(1, 2),
                  event(request_id="request-2", source_record_id="foreign", immutable_facet_id="facet-foreign").assigned(1, 3)]
        result = project_request(events, request_id="request-1")
        self.assertEqual(len(result.matched_event_ids), 1); self.assertEqual(len(result.unknown_event_ids), 1); self.assertEqual(len(result.foreign_event_ids), 1)
        self.assertEqual(result.mapping_method, "exact_request_id")

    def test_schema_is_valid_json(self):
        self.assertEqual(json.loads(Path("schemas/request-projection-v1.schema.json").read_text(encoding="utf-8"))["$id"], "urn:codekit:request-projection:1")


if __name__ == "__main__":
    unittest.main()
