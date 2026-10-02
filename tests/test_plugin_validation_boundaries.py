"""Strict input-boundary regressions for built-in plugin records.

These tests stay at the validation boundary: malformed records must produce
the module's stable error type rather than leaking a Python ``KeyError`` or
``TypeError``.  The checked-in plugin fixtures are also exercised as a small
compatibility sample.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.builtin_artifacts import ArtifactError, validate_catalog  # noqa: E402
from codekit.plugins import (  # noqa: E402
    PluginError,
    build_lock,
    digest,
    resolve_plugins,
    validate_lock,
    validate_manifest,
)


def manifest(plugin_id: str = "demo", depends=None):
    return {
        "record_type": "builtin-task-plugin-manifest",
        "schema_version": 1,
        "plugin_id": plugin_id,
        "version": "1.0.0",
        "api_version": "builtin-check-v1",
        "roles": [],
        "capabilities": ["check"],
        "entrypoints": [],
        "resources": [
            {
                "kind": "check",
                "id": plugin_id,
                "path": f"fixtures/{plugin_id}.json",
                "sha256": "a" * 64,
            }
        ],
        "depends_on": [] if depends is None else depends,
        "conflicts": [],
        "checks": [{"id": "check", "command": ["python", "-c", "pass"], "deterministic": True}],
        "platforms": [],
        "permissions": [],
    }


def checked_in_manifests():
    root = Path(__file__).resolve().parents[1] / "plugins"
    return {
        path.parent.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(root.glob("*/manifest.json"))
    }


class PluginValidationBoundaryTests(unittest.TestCase):
    def assert_plugin_error(self, action):
        """Ensure malformed input is rejected by PluginError, never a leak."""
        with self.assertRaises(PluginError):
            action()

    def assert_artifact_error(self, action):
        with self.assertRaises(ArtifactError):
            action()

    def test_checked_in_manifests_and_locks_remain_valid(self):
        manifests = checked_in_manifests()
        self.assertGreaterEqual(len(manifests), 1)
        for value in manifests.values():
            validate_manifest(value)
        for plugin_id, value in manifests.items():
            lock = json.loads((Path(__file__).resolve().parents[1] / "plugins" / plugin_id / "lock.json").read_text(encoding="utf-8"))
            validate_lock(lock, {plugin_id: value})

    def test_all_nine_manifest_fields_are_required(self):
        required = ("record_type", "schema_version", "plugin_id", "version", "api_version", "roles", "capabilities", "resources", "checks")
        for field in required:
            bad = manifest()
            del bad[field]
            with self.subTest(field=field):
                self.assert_plugin_error(lambda bad=bad: validate_manifest(bad))

    def test_plugin_id_and_version_are_strict(self):
        for value in ("Demo", "1demo", "demo_plugin", "demo.", "demo/child", "", "latest", "head", "current", "stable", "a" * 65):
            bad = manifest(value)
            with self.subTest(plugin_id=value):
                self.assert_plugin_error(lambda bad=bad: validate_manifest(bad))
        for value in ("1", "1.0", "v1.0.0", "01.0.0", "1.0.0-beta", "1.0.0+build", "latest"):
            bad = manifest()
            bad["version"] = value
            with self.subTest(version=value):
                self.assert_plugin_error(lambda bad=bad: validate_manifest(bad))

        for value in ("latest", "head", "current", "stable", "main"):
            bad = manifest()
            bad["api_version"] = value
            with self.subTest(api_version=value):
                self.assert_plugin_error(lambda bad=bad: validate_manifest(bad))

        for value in ("latest", "head", "current"):
            bad = manifest()
            bad["checks"][0]["command"] = ["python", value]
            with self.subTest(check_alias=value):
                self.assert_plugin_error(lambda bad=bad: validate_manifest(bad))

    def test_declared_arrays_are_arrays_of_unique_nonempty_strings(self):
        fields = ("roles", "capabilities", "entrypoints", "depends_on", "conflicts", "platforms", "permissions")
        for field in fields:
            bad = manifest()
            bad[field] = ["same", "same"]
            with self.subTest(field=field + " duplicate"):
                self.assert_plugin_error(lambda bad=bad: validate_manifest(bad))
            bad = manifest()
            bad[field] = [""]
            with self.subTest(field=field + " empty"):
                self.assert_plugin_error(lambda bad=bad: validate_manifest(bad))
            bad = manifest()
            bad[field] = "not-an-array"
            with self.subTest(field=field + " type"):
                self.assert_plugin_error(lambda bad=bad: validate_manifest(bad))

    def test_check_id_and_argv_are_nonempty_closed_values(self):
        for check in (
            {"id": "", "command": ["python"], "deterministic": True},
            {"id": "check", "command": [], "deterministic": True},
            {"id": "check", "command": [""], "deterministic": True},
            {"id": "check", "command": ["python"], "deterministic": True, "extra": 1},
        ):
            bad = manifest()
            bad["checks"] = [check]
            self.assert_plugin_error(lambda bad=bad: validate_manifest(bad))

    def test_duplicate_enabled_plugins_and_registry_key_mismatch_are_rejected(self):
        self.assert_plugin_error(lambda: resolve_plugins({"demo": manifest()}, ["demo", "demo"]))
        self.assert_plugin_error(lambda: resolve_plugins({"alias": manifest("demo")}, ["alias"]))

    def test_lock_header_and_rows_are_closed_and_typed(self):
        lock = build_lock([manifest()], compiler_sha256="b" * 64)

        def refresh(value):
            value["lock_sha256"] = digest({key: item for key, item in value.items() if key != "lock_sha256"})
            return value

        for field in ("record_type", "schema_version", "generation", "compiler_sha256", "plugins", "lock_sha256"):
            bad = copy.deepcopy(lock)
            del bad[field]
            self.assert_plugin_error(lambda bad=bad: validate_lock(bad))

        for value in ("B" * 64, "short", "g" * 64):
            bad = copy.deepcopy(lock)
            bad["compiler_sha256"] = value
            # Keep the record internally self-consistent so the compiler hash
            # validator is the first boundary reached.
            refresh(bad)
            self.assert_plugin_error(lambda bad=bad: validate_lock(bad))

        rows = (
            {},
            {"plugin_id": "demo"},
            {"plugin_id": "demo", "version": "1.0.0", "manifest_sha256": "a" * 64, "resources": [], "extra": True},
            {"plugin_id": ["demo"], "version": "1.0.0", "manifest_sha256": "a" * 64, "resources": []},
        )
        for row in rows:
            bad = copy.deepcopy(lock)
            bad["plugins"] = [row]
            refresh(bad)
            self.assert_plugin_error(lambda bad=bad: validate_lock(bad))

    def test_lock_and_permission_inputs_are_canonical(self):
        first = manifest("a")
        second = manifest("b")
        lock = build_lock([first, second], compiler_sha256="b" * 64)
        unsorted = copy.deepcopy(lock)
        unsorted["plugins"] = list(reversed(unsorted["plugins"]))
        unsorted["lock_sha256"] = digest({key: item for key, item in unsorted.items() if key != "lock_sha256"})
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_LOCK"):
            validate_lock(unsorted)
        bad_manifest = manifest()
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_POLICY"):
            from codekit.plugins import check_permission_intersection
            check_permission_intersection(bad_manifest, allowed_permissions=["read", "read"])
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_POLICY"):
            check_permission_intersection(bad_manifest, allowed_permissions=[], platform_name=1)

    def test_lock_builder_rejects_non_sequences_and_duplicate_manifests(self):
        for value in (None, "not-a-sequence", b"bytes", (item for item in [manifest()])):
            with self.subTest(value=type(value).__name__):
                self.assert_plugin_error(lambda value=value: build_lock(value, compiler_sha256="b" * 64))
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_LOCK"):
            build_lock([manifest(), manifest()], compiler_sha256="b" * 64)

    def test_catalog_rows_require_string_id_exact_version_and_closed_refs(self):
        ref = {"kind": "file", "id": "manifest", "path": "plugins/demo/manifest.json", "sha256": "a" * 64}
        good = {"record_type": "builtin-task-plugin-catalog", "schema_version": 1,
                "plugins": [{"plugin_id": "demo", "version": "1.0.0", "manifest_ref": ref, "lock_ref": {**ref, "id": "lock"}}]}
        validate_catalog(good)
        for value in ("Demo", "", "latest", "head", 1, [], {"id": "demo"}):
            bad = copy.deepcopy(good)
            bad["plugins"][0]["plugin_id"] = value
            self.assert_artifact_error(lambda bad=bad: validate_catalog(bad))
        for value in ("", "1", "v1.0.0", 1, [], "1.0.0-beta"):
            bad = copy.deepcopy(good)
            bad["plugins"][0]["version"] = value
            self.assert_artifact_error(lambda bad=bad: validate_catalog(bad))
        bad = copy.deepcopy(good)
        bad["plugins"][0]["manifest_ref"] = None
        self.assert_artifact_error(lambda: validate_catalog(bad))


if __name__ == "__main__":
    unittest.main()
