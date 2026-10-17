import hashlib
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from codekit.builtin_docs_change import build_docs_change, validate_docs_change
from codekit.builtin_artifacts import ArtifactError, resource_ref_key

class DocsChangeTests(unittest.TestCase):
    def test_change_mapping_is_deterministic_and_closed(self):
        before = {"docs/a.md": b"old"}; after = {"docs/a.md": b"new", "docs/b.md": b"add"}
        a = build_docs_change(before, after, writable_paths=["docs/a.md", "docs/b.md"])
        b = build_docs_change(before, after, writable_paths=["docs/b.md", "docs/a.md"])
        self.assertEqual(a, b)
        self.assertEqual([x["kind"] for x in a["payload"]["changes"]], ["modify", "add"])
        self.assertEqual(validate_docs_change(a)["record_type"], "docs-change")

    def test_scope_and_protected_paths_reject_changes(self):
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_SCOPE"):
            build_docs_change({}, {"README.md": b"x"}, writable_paths=[])
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_PROTECTED"):
            build_docs_change({}, {"README.md": b"x"}, writable_paths=["README.md"], protected_paths=["README.md"])
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_SCOPE"):
            build_docs_change({}, {"docs/x.txt": b"x"}, writable_paths=["docs/x.txt"])

    def test_delete_has_closed_hash_shape(self):
        result = build_docs_change({"docs/a.md": b"old"}, {}, writable_paths=["docs/a.md"])
        row = result["payload"]["changes"][0]
        self.assertEqual(row["kind"], "delete")
        self.assertIsNone(row["after_sha256"])
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_SCHEMA"):
            bad = dict(result); bad["payload"] = dict(result["payload"]); bad["payload"]["changes"] = [dict(row, after_sha256="a" * 64)]
            validate_docs_change(bad)

    def test_validator_rejects_forged_scope_paths_and_duplicates(self):
        record = build_docs_change({"docs/a.md": b"old"}, {"docs/a.md": b"new"}, writable_paths=["docs/a.md"])
        for writable, error in (([1], "E_DOCS_SCOPE|E_DOCS_PATH"),
                                (["../secret"], "E_DOCS_PATH"),
                                (["docs/\x80.md"], "E_DOCS_PATH"),
                                (["docs/a.md", "docs/a.md"], "E_DOCS_SCOPE"),
                                ("docs/a.md", "E_DOCS_SCOPE")):
            forged = copy.deepcopy(record)
            forged["payload"]["scope"]["writable"] = writable
            with self.subTest(writable=writable), self.assertRaisesRegex(ArtifactError, error):
                validate_docs_change(forged)
        forged = copy.deepcopy(record)
        forged["payload"]["scope"]["protected"] = ["docs/a.md"]
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_PROTECTED"):
            validate_docs_change(forged)

    def test_offline_docs_change_rejects_production_pass(self):
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_PRODUCTION_GATE"):
            build_docs_change({"docs/a.md": b"old"}, {"docs/a.md": b"new"},
                              writable_paths=["docs/a.md"], status="PASS")
        record = build_docs_change({"docs/a.md": b"old"}, {"docs/a.md": b"new"}, writable_paths=["docs/a.md"])
        forged = copy.deepcopy(record)
        forged["status"] = "PASS"
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_PRODUCTION_GATE"):
            validate_docs_change(forged)

    def test_change_anchor_must_be_declared_by_source_refs(self):
        result = build_docs_change({"docs/a.md": b"old"}, {"docs/a.md": b"new"}, writable_paths=["docs/a.md"])
        row = dict(result["payload"]["changes"][0])
        row["source_anchors"] = [{"ref": {"kind": "file", "id": "foreign", "path": "docs/foreign.md", "sha256": "a" * 64}, "start_byte": 0, "end_byte": 1, "excerpt_sha256": "b" * 64}]
        forged = dict(result); forged["payload"] = dict(result["payload"]); forged["payload"]["changes"] = [row]
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_PROVENANCE"):
            validate_docs_change(forged)

    def test_builder_rejects_untyped_snapshot_and_sequences(self):
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_SNAPSHOT"):
            build_docs_change({"docs/a.md": "old"}, {}, writable_paths=["docs/a.md"])
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_SCOPE"):
            build_docs_change({}, {"docs/a.md": b"new"}, writable_paths=None)
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_SCHEMA"):
            build_docs_change({}, {"docs/a.md": b"new"}, writable_paths=["docs/a.md"], status=[])
        record = build_docs_change({"docs/a.md": b"old"}, {"docs/a.md": b"new"}, writable_paths=["docs/a.md"])
        forged = copy.deepcopy(record)
        forged["payload"]["changes"][0]["kind"] = []
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_SCHEMA"):
            validate_docs_change(forged)

    def test_builder_binds_change_anchors_to_frozen_source_bytes(self):
        source = b"abcdef"
        frozen_ref = {"kind": "file", "id": "frozen", "path": "docs/source.md",
                      "sha256": hashlib.sha256(source).hexdigest()}
        anchor = {"ref": frozen_ref, "start_byte": 1, "end_byte": 4,
                  "excerpt_sha256": hashlib.sha256(source[1:4]).hexdigest()}
        result = build_docs_change(
            {"docs/a.md": b"old"}, {"docs/a.md": b"new"},
            writable_paths=["docs/a.md"], source_refs=[frozen_ref],
            source_anchors_by_path={"docs/a.md": [anchor]},
            source_bytes_by_ref={resource_ref_key(frozen_ref): source},
        )
        self.assertEqual(result["payload"]["changes"][0]["source_anchors"][0]["end_byte"], 4)
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_SOURCE"):
            build_docs_change(
                {"docs/a.md": b"old"}, {"docs/a.md": b"new"},
                writable_paths=["docs/a.md"], source_refs=[frozen_ref],
                source_anchors_by_path={"docs/a.md": [anchor]},
                source_bytes_by_ref={resource_ref_key(frozen_ref): b"changed"},
            )
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_SOURCE"):
            build_docs_change(
                {"docs/a.md": b"old"}, {"docs/a.md": b"new"},
                writable_paths=["docs/a.md"], source_refs=[frozen_ref],
                source_anchors_by_path={"docs/a.md": [anchor]},
                source_bytes_by_ref={},
            )
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_SOURCE"):
            build_docs_change(
                {"docs/a.md": b"old"}, {"docs/a.md": b"new"},
                writable_paths=["docs/a.md"], source_refs=[frozen_ref],
                source_anchors_by_path={"docs/a.md": [anchor]},
            )

    def test_snapshot_paths_are_normalized_before_diffing_and_aliases_rejected(self):
        result = build_docs_change({"docs\\a.md": b"old"}, {"docs\\a.md": b"new"},
                                   writable_paths=["docs/a.md"])
        self.assertEqual(result["payload"]["changes"][0]["path"], "docs/a.md")
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_SNAPSHOT"):
            build_docs_change({"docs/a.md": b"old", "docs\\a.md": b"old"}, {},
                              writable_paths=["docs/a.md"])
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_SNAPSHOT"):
            build_docs_change({"docs/a.md": b"old", "DOCS/A.md": b"old"}, {},
                              writable_paths=["docs/a.md"])

    def test_validator_rejects_impossible_duplicate_and_unsorted_rows(self):
        record = build_docs_change({"docs/a.md": b"old"}, {"docs/a.md": b"new"},
                                   writable_paths=["docs/a.md"])
        row = record["payload"]["changes"][0]
        for forged in (
            dict(row, kind="modify", before_sha256=None),
            dict(row, kind="modify", after_sha256=row["before_sha256"]),
            dict(row, kind="add", before_sha256=None, after_sha256=None),
            dict(row, path="secret.txt"),
        ):
            value = copy.deepcopy(record)
            value["payload"]["changes"] = [forged]
            with self.subTest(forged=forged), self.assertRaisesRegex(ArtifactError, "E_DOCS_SCHEMA"):
                validate_docs_change(value)
        forged = copy.deepcopy(record)
        forged["payload"]["changes"][0]["after_sha256"] = b"bytes-not-a-digest"
        with self.assertRaisesRegex(ArtifactError, "E_ARTIFACT_JSON"):
            validate_docs_change(forged)

if __name__ == "__main__": unittest.main()
