import hashlib
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from codekit.builtin_docs_change import build_docs_change, validate_docs_change
from codekit.builtin_artifacts import ArtifactError

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

    def test_offline_docs_change_rejects_production_pass(self):
        with self.assertRaisesRegex(ArtifactError, "E_DOCS_PRODUCTION_GATE"):
            build_docs_change({"docs/a.md": b"old"}, {"docs/a.md": b"new"},
                              writable_paths=["docs/a.md"], status="PASS")

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

if __name__ == "__main__": unittest.main()
