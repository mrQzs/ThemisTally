import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.plugins import PluginError, build_lock, check_permission_intersection, digest, resolve_plugins, validate_lock, validate_manifest


def manifest(plugin_id="demo", depends=None):
    return {"record_type": "builtin-task-plugin-manifest", "schema_version": 1, "plugin_id": plugin_id,
            "version": "1.0.0", "api_version": "builtin-check-v1", "roles": [], "capabilities": ["check"],
            "resources": [{"kind": "check", "id": plugin_id, "path": f"fixtures/{plugin_id}.json", "sha256": "a" * 64}],
            "depends_on": depends or [], "conflicts": [], "checks": [{"id": "check", "command": ["python", "-c", "pass"], "deterministic": True}]}


class PluginTests(unittest.TestCase):
    def test_manifest_accepts_deterministic_empty_roles(self):
        self.assertEqual(validate_manifest(manifest())["roles"], [])

    def test_manifest_rejects_dynamic_network_and_path_escape(self):
        bad = manifest(); bad["checks"][0]["command"] = ["python", "-c", "importlib.import_module('x')"]
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_CHECK"):
            validate_manifest(bad)
        bad = manifest(); bad["resources"][0]["path"] = "../secret"
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_PATH"):
            validate_manifest(bad)

    def test_dependencies_are_sorted_and_missing_or_cycles_block(self):
        ordered = resolve_plugins({"a": manifest("a", ["b"]), "b": manifest("b")}, ["a"])
        self.assertEqual([x["plugin_id"] for x in ordered], ["b", "a"])
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_DEPENDENCY"):
            resolve_plugins({"a": manifest("a", ["missing"])}, ["a"])
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_CYCLE"):
            resolve_plugins({"a": manifest("a", ["b"]), "b": manifest("b", ["a"])}, ["a"])

    def test_lock_is_deterministic_and_detects_one_byte_drift(self):
        lock = build_lock([manifest()], compiler_sha256="b" * 64)
        self.assertEqual(validate_lock(lock)["lock_sha256"], lock["lock_sha256"])
        changed = copy.deepcopy(lock); changed["plugins"][0]["version"] = "1.0.1"
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_LOCK_DRIFT"):
            validate_lock(changed)

    def test_conflicting_plugins_are_rejected(self):
        left = manifest("left"); right = manifest("right"); left["conflicts"] = ["right"]
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_CONFLICT"):
            resolve_plugins({"left": left, "right": right}, ["left", "right"])

    def test_identity_and_lock_binding_are_strict(self):
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_IDENTITY"):
            resolve_plugins({"alias": manifest("demo")}, ["alias"])
        bad = manifest(); bad["checks"][0]["deterministic"] = "yes"
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_CHECK"):
            validate_manifest(bad)
        lock = build_lock([manifest()], compiler_sha256="b" * 64)
        changed = copy.deepcopy(manifest()); changed["capabilities"] = ["different"]
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_LOCK_BINDING"):
            validate_lock(lock, {"demo": changed})

    def test_permission_intersection_and_platform_are_conservative(self):
        value = manifest()
        value["permissions"] = ["read-candidate", "write-candidate"]
        value["platforms"] = ["linux"]
        ready = check_permission_intersection(value, allowed_permissions=["read-candidate", "write-candidate"], platform_name="linux")
        self.assertEqual(ready["status"], "READY")
        blocked = check_permission_intersection(value, allowed_permissions=["read-candidate"], platform_name="windows")
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertEqual(blocked["missing_permissions"], ["write-candidate"])
        self.assertTrue(blocked["platform_blocked"])

    def test_canonical_bytes_rejects_non_json_values_and_unsafe_text(self):
        from codekit.plugins import canonical_bytes
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_JSON"):
            canonical_bytes(("tuple",))
        cyclic = []
        cyclic.append(cyclic)
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_JSON"):
            canonical_bytes(cyclic)
        for key in ("bad\nkey", "bad\ud800"):
            with self.subTest(key=repr(key)), self.assertRaisesRegex(PluginError, "E_PLUGIN_JSON"):
                canonical_bytes({key: "value"})
        bad = manifest(); bad["checks"][0]["command"] = ["python", "a\x7fb"]
        with self.assertRaisesRegex(PluginError, "E_PLUGIN_CHECK"):
            validate_manifest(bad)


if __name__ == "__main__":
    unittest.main()
