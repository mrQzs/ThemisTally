import sys
import copy
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.builtin_artifacts import ArtifactError
from codekit.builtin_change import assert_change_current, build_change_report


def ref(name="source"):
    return {"kind": "file", "id": name, "path": f"src/{name}.py", "sha256": "a" * 64}


class ChangeTests(unittest.TestCase):
    def report(self, **kwargs):
        args = {"artifact_id": "change-1", "producer": {"kind": "builtin-plugin", "id": "code-change", "version": "1.0.0"},
                "source_refs": [ref()], "candidate_ref": ref("candidate"), "environment_ref": ref("environment"),
                "scope": ["src"], "files": [{"path": "src/a.py", "change_type": "modified", "old_sha256": "a" * 64, "new_sha256": "b" * 64}]}
        args.update(kwargs)
        return build_change_report(**args)

    def test_scope_and_hash_bindings(self):
        report = self.report(link_bindings=[{"path": "src/a.py", "target": "src/b.py", "kind": "relative"}])
        assert_change_current(report, candidate_ref=ref("candidate"), source_refs=[ref()], environment_ref=ref("environment"))
        with self.assertRaisesRegex(ArtifactError, "E_CHANGE_DRIFT"):
            assert_change_current(report, candidate_ref=ref("other"), source_refs=[ref()], environment_ref=ref("environment"))

    def test_out_of_scope_and_external_link_are_rejected(self):
        with self.assertRaisesRegex(ArtifactError, "E_CHANGE_SCOPE"):
            self.report(files=[{"path": "tests/a.py", "change_type": "modified", "old_sha256": "a" * 64, "new_sha256": "b" * 64}])
        with self.assertRaisesRegex(ArtifactError, "E_CHANGE_PATH"):
            self.report(link_bindings=[{"path": "src/a.py", "target": "https://example.invalid", "kind": "relative"}])

    def test_added_deleted_and_submodule_shapes(self):
        added = self.report(files=[{"path": "src/new.py", "change_type": "added", "old_sha256": None, "new_sha256": "b" * 64}])
        self.assertEqual(added["payload"]["files"][0]["change_type"], "added")
        with self.assertRaisesRegex(ArtifactError, "E_CHANGE_HASH"):
            self.report(files=[{"path": "src/new.py", "change_type": "added", "old_sha256": "a" * 64, "new_sha256": "b" * 64}])

    def test_builder_rejects_untyped_status_and_sequences(self):
        with self.assertRaisesRegex(ArtifactError, "E_CHANGE_STATUS"):
            self.report(status=[])
        with self.assertRaisesRegex(ArtifactError, "E_CHANGE_SCOPE"):
            self.report(scope=None)
        with self.assertRaisesRegex(ArtifactError, "E_CHANGE_SCHEMA"):
            self.report(files=None)

    def test_validator_rejects_untyped_payload_enums(self):
        report = self.report()
        forged = copy.deepcopy(report)
        forged["payload"]["mode"] = []
        with self.assertRaisesRegex(ArtifactError, "E_CHANGE_SCHEMA"):
            from codekit.builtin_change import validate_change_report
            validate_change_report(forged)
        forged = copy.deepcopy(report)
        forged["payload"]["evidence_class"] = []
        with self.assertRaisesRegex(ArtifactError, "E_CHANGE_SCHEMA"):
            validate_change_report(forged)

    def test_paths_and_change_facts_are_portable_and_consistent(self):
        for unsafe in ("C:/repo/a.py", "src/a:b.py", "src/CON.txt", "src/a\u202e.py"):
            with self.subTest(unsafe=unsafe), self.assertRaisesRegex(ArtifactError, "E_CHANGE_PATH"):
                self.report(files=[{"path": unsafe, "change_type": "modified",
                                    "old_sha256": "a" * 64, "new_sha256": "b" * 64}])
        with self.assertRaisesRegex(ArtifactError, "E_CHANGE_HASH"):
            self.report(files=[{"path": "src/a.py", "change_type": "modified",
                                "old_sha256": "a" * 64, "new_sha256": "a" * 64}])
        with self.assertRaisesRegex(ArtifactError, "E_CHANGE_SCHEMA"):
            self.report(files=[{"path": "src/a.py", "old_path": "src/a.py", "change_type": "renamed",
                                "old_sha256": "a" * 64, "new_sha256": "a" * 64}])
        with self.assertRaisesRegex(ArtifactError, "E_CHANGE_MODE"):
            self.report(files=[{"path": "src/a.py", "change_type": "mode-only",
                                "old_sha256": "a" * 64, "new_sha256": "a" * 64}])


if __name__ == "__main__":
    unittest.main()
