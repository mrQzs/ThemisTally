import copy
import hashlib
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

    def test_artifact_hash_boundary_rejects_python_only_values_and_cycles(self):
        bad = artifact(); bad["payload"] = {"tuple": (1, 2)}
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_JSON"):
            validate_artifact(bad)
        bad = artifact(); bad["payload"] = {1: "non-text key"}
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_JSON"):
            validate_artifact(bad)
        bad = artifact(); cycle = {}; cycle["self"] = cycle; bad["payload"] = cycle
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_JSON"):
            validate_artifact(bad)
        for key in ("bad\nkey", "bad\ud800"):
            bad = artifact(); bad["payload"] = {key: "value"}
            with self.subTest(key=repr(key)):
                with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_JSON"):
                    validate_artifact(bad)

    def test_artifact_refs_reject_control_characters(self):
        for field in ("kind", "id", "path"):
            bad = artifact(); bad["source_refs"] = [{**ref(), field: "source\x7f"}]
            with self.subTest(field=field):
                with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_REF|E_ARTIFACT_PATH"):
                    validate_artifact(bad)

    def test_artifact_rejects_controls_and_lone_surrogates_before_hashing(self):
        for payload in ({"text": "line\nfeed"}, {"text": "bad\ud800"}):
            bad = artifact(); bad["payload"] = payload
            with self.subTest(payload=repr(payload)):
                with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_JSON"):
                    validate_artifact(bad)
        for field in ("artifact_id",):
            bad = artifact(); bad[field] = "id\udfff"
            with self.subTest(field=field):
                with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_SCHEMA"):
                    validate_artifact(bad)
        bad = artifact(); bad["producer"] = {"kind": "builtin-plugin", "id": "repo-analysis", "version": "1.0.0\ud800"}
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_PRODUCER"):
            validate_artifact(bad)
        bad = artifact(); bad["payload"] = {"count": 2 ** 53}
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_JSON"):
            validate_artifact(bad)

    def test_source_anchor_rejects_unsafe_byte_offsets(self):
        bad = {"ref": ref(), "start_byte": 2 ** 53, "end_byte": 2 ** 53 + 1,
               "excerpt_sha256": "b" * 64}
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_SOURCE"):
            source_anchor(bad)

    def test_source_anchor_binds_resource_and_excerpt_bytes(self):
        source = "甲乙丙".encode("utf-8")
        anchor = {"ref": {**ref(), "sha256": hashlib.sha256(source).hexdigest()},
                  "start_byte": 3, "end_byte": 6,
                  "excerpt_sha256": hashlib.sha256("乙".encode("utf-8")).hexdigest()}
        self.assertEqual(source_anchor(anchor, source)["start_byte"], 3)

        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_SOURCE"):
            source_anchor(anchor, b"changed")
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_SOURCE"):
            source_anchor({**anchor, "end_byte": len(source) + 1}, source)
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_SOURCE"):
            source_anchor({**anchor, "excerpt_sha256": "b" * 64}, source)

    def test_catalog_returns_canonical_resource_paths(self):
        item = {"plugin_id": "demo", "version": "1.0.0", "manifest_ref": ref("manifest"), "lock_ref": ref("lock")}
        item["manifest_ref"]["path"] = "recipes\\manifest.json"
        item["lock_ref"]["path"] = "recipes\\lock.json"
        normalized = validate_catalog({"record_type": "builtin-task-plugin-catalog", "schema_version": 1, "plugins": [item]})
        self.assertEqual(normalized["plugins"][0]["manifest_ref"]["path"], "recipes/manifest.json")
        self.assertEqual(normalized["plugins"][0]["lock_ref"]["path"], "recipes/lock.json")

    def test_catalog_enforces_canonical_size_limit(self):
        item = {"plugin_id": "demo", "version": "1.0.0",
                "manifest_ref": {**ref("manifest"), "path": "x" * (1024 * 1024)},
                "lock_ref": ref("lock")}
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_SIZE"):
            validate_catalog({"record_type": "builtin-task-plugin-catalog", "schema_version": 1, "plugins": [item]})


if __name__ == "__main__":
    unittest.main()
