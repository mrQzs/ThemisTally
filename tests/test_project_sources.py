import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.codekit.project_sources import SourceVerificationError, verify_source_ref


def make_ref(path: str, raw: bytes, *, kind: str = "fixture-source"):
    return {"kind": kind, "id": "source-1", "sha256": hashlib.sha256(raw).hexdigest(), "path": path}


class ProjectSourceTests(unittest.TestCase):
    def test_verifies_exact_bytes_and_reports_hash_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "a.txt").write_bytes(b"alpha")
            ref = make_ref("a.txt", b"alpha")
            report = verify_source_ref(root, ref)
            self.assertEqual(report.status, "verified")
            self.assertEqual(report.byte_length, 5)
            report = verify_source_ref(root, {**ref, "sha256": "0" * 64})
            self.assertEqual(report.status, "hash_mismatch")
            self.assertEqual(report.observed_sha256, hashlib.sha256(b"alpha").hexdigest())

    def test_missing_escape_and_symlink_are_not_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "a.txt").write_bytes(b"alpha")
            ref = make_ref("missing.txt", b"alpha")
            self.assertEqual(verify_source_ref(root, ref).status, "missing")
            with self.assertRaises(SourceVerificationError):
                verify_source_ref(root, {**ref, "path": "../a.txt"})
            link = root / "link.txt"
            try:
                link.symlink_to(root / "a.txt")
            except (OSError, NotImplementedError):
                self.skipTest("symlink unavailable")
            self.assertEqual(verify_source_ref(root, {**ref, "path": "link.txt"}).status, "conflict")

    def test_path_is_required_and_schema_is_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = b"alpha"
            report = verify_source_ref(root, {"kind": "fixture-source", "id": "source-1", "sha256": hashlib.sha256(raw).hexdigest()})
            self.assertEqual(report.status, "schema_unsupported")
            with self.assertRaises(SourceVerificationError):
                verify_source_ref(root, {"kind": "fixture-source", "id": "source-1", "sha256": "0" * 64, "path": "a", "extra": 1})

    def test_schema_is_valid_json(self):
        value = json.loads(Path("schemas/source-verification-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(value["$id"], "urn:codekit:source-verification:1")


if __name__ == "__main__":
    unittest.main()
