import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.builtin_artifacts import ArtifactError, digest, source_anchor, validate_artifact, validate_catalog


def ref(name="source"):
    return {"kind": "file", "id": name, "path": f"docs/{name}.md", "sha256": "a" * 64}


def artifact():
    return {"record_type": "analysis-report", "schema_version": 1, "artifact_id": "a1",
            "producer": {"kind": "builtin-plugin", "id": "repo-analysis", "version": "1.0.0"}, "status": "DRAFT_VALIDATED",
            "source_refs": [ref()], "candidate_ref": None, "environment_ref": None, "payload": {"facts": []}}


class BuiltinArtifactsTests(unittest.TestCase):
    def test_valid_artifact_and_digest_are_stable(self):
        value = validate_artifact(artifact())
        self.assertEqual(digest(value), digest(value))

    def test_artifact_rejects_unknown_fields_and_unsafe_refs(self):
        bad = artifact(); bad["unexpected"] = True
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_SCHEMA"):
            validate_artifact(bad)
        bad = artifact(); bad["record_type"] = []
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_VERSION"):
            validate_artifact(bad)
        bad = artifact(); bad["status"] = []
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_STATUS"):
            validate_artifact(bad)
        bad = artifact(); bad["source_refs"] = [{**ref(), "path": "../secret"}]
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_PATH"):
            validate_artifact(bad)

    def test_candidate_and_environment_are_optional_but_closed(self):
        value = artifact(); value["candidate_ref"] = ref("candidate"); value["environment_ref"] = ref("env")
        self.assertEqual(validate_artifact(value)["candidate_ref"]["id"], "candidate")
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_REF"):
            bad = artifact(); bad["candidate_ref"] = {"id": "missing"}; validate_artifact(bad)

    def test_source_anchor_requires_exact_byte_range(self):
        anchor = source_anchor({"ref": ref(), "start_byte": 0, "end_byte": 3, "excerpt_sha256": "b" * 64})
        self.assertEqual(anchor["end_byte"], 3)
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_SOURCE"):
            source_anchor({"ref": ref(), "start_byte": 3, "end_byte": 3, "excerpt_sha256": "b" * 64})

    def test_catalog_rejects_duplicate_plugin_ids(self):
        item = {"plugin_id": "demo", "version": "1.0.0", "manifest_ref": ref("manifest"), "lock_ref": ref("lock")}
        with self.assertRaisesRegex(ArtifactError, "E_CATALOG_SCHEMA"):
            validate_catalog({"record_type": "builtin-task-plugin-catalog", "schema_version": 1, "plugins": [item, item]})

    def test_artifact_rejects_nonfinite_oversize_and_drive_refs(self):
        bad = artifact(); bad["payload"] = {"value": float("nan")}
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_JSON"):
            validate_artifact(bad)
        bad = artifact(); bad["source_refs"] = [{**ref(), "path": "C:/outside.md"}]
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_PATH"):
            validate_artifact(bad)

    def test_artifact_rejects_refs_that_collide_after_path_normalization(self):
        value = artifact()
        value["source_refs"] = [ref(), {**ref(), "path": "docs\\source.md"}]
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_REF"):
            validate_artifact(value)


if __name__ == "__main__":
    unittest.main()
