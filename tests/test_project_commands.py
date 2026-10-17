import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.codekit.project_authority import observe_authority
from scripts.codekit.project_commands import project_checkpoint, project_status
from scripts.codekit.project_compat import LegacyCompatibilityError, load_registered_legacy_state
from scripts.codekit.project_views import ViewPackageStore, render_project_brief
from tests.test_project_views import STATE


class ProjectCommandTests(unittest.TestCase):
    def test_status_and_checkpoint_are_read_only_and_authority_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ViewPackageStore(tmp); store.publish(STATE, render_project_brief(STATE), generation=1, cursor=2)
            authority = observe_authority("approval", status="unknown", reason="external authority not connected")
            status = project_status(store, [authority]); checkpoint = project_checkpoint(store, [authority])
            self.assertEqual(status["dispatch_eligibility"], "not_evaluated")
            self.assertTrue(checkpoint["read_only"]); self.assertEqual(len(status["authority_observations"]), 1)
            self.assertEqual(checkpoint["checkpoint_id"], project_checkpoint(store, [authority])["checkpoint_id"])

    def test_legacy_requires_registration_and_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"; raw = b'{"legacy":true}\n'; path.write_bytes(raw)
            with self.assertRaises(LegacyCompatibilityError):
                load_registered_legacy_state(path, registration={"source_class": "legacy", "registered": False, "sha256": hashlib.sha256(raw).hexdigest()})
            value = load_registered_legacy_state(path, registration={"source_class": "legacy", "registered": True, "sha256": hashlib.sha256(raw).hexdigest()})
            self.assertEqual(value, {"legacy": True})
            path.write_bytes(b'{"legacy":false}\n')
            with self.assertRaisesRegex(LegacyCompatibilityError, "changed"):
                load_registered_legacy_state(path, registration={"source_class": "legacy", "registered": True, "sha256": hashlib.sha256(raw).hexdigest()})

    def test_schemas_are_valid_json(self):
        for path in ("schemas/authority-observation-v1.schema.json", "schemas/project-checkpoint-v1.schema.json"):
            self.assertTrue(json.loads(Path(path).read_text(encoding="utf-8"))["$id"].startswith("urn:codekit:"))


if __name__ == "__main__":
    unittest.main()
