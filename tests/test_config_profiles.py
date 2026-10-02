import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.config_profiles import (AdapterDescriptor, AdapterRegistry, ConfigError,
                                     apply_local_overrides, canonical_json_bytes,
                                     load_strict_json, resolve_profile, validate_config)


def registry():
    return AdapterRegistry([AdapterDescriptor("offline", "offline-v1", ("structured-events",), ("demo-model",), ("thinking",))])


def config():
    return {
        "schema_version": 2,
        "runtimes": {"demo": {"adapter": "offline", "command": ["python", "-m", "demo"]}},
        "profiles": {"planning": {"runtime": "demo", "model": {"id": "demo-model"}, "options": {"thinking": "high"}}},
        "roles": {"planner": {"profile": "planning"}},
        "platforms": {"windows": {"shell_executable": "cmd.exe", "tools": {"check": "check.exe"}}},
    }


class ConfigProfilesTests(unittest.TestCase):
    def test_registry_constructor_rejects_duplicate_descriptors(self):
        descriptor = AdapterDescriptor("offline", "offline-v1")
        with self.assertRaisesRegex(ConfigError, "E_CFG_ADAPTER"):
            AdapterRegistry([descriptor, descriptor])

    def test_strict_json_rejects_duplicate_and_nan(self):
        with self.assertRaisesRegex(ConfigError, "E_JSON_DUPLICATE"):
            load_strict_json('{"schema_version":2,"schema_version":2}')
        with self.assertRaisesRegex(ConfigError, "E_JSON_NUMBER"):
            load_strict_json('{"schema_version":2,"x":NaN}')

    def test_valid_config_and_semantic_snapshot_are_deterministic(self):
        doc = validate_config(config(), registry())
        one = resolve_profile(doc, registry(), role="planner")
        two = resolve_profile(config(), registry(), role="planner")
        self.assertEqual(one.semantic_snapshot, two.semantic_snapshot)
        self.assertEqual(one.semantic_sha256, hashlib.sha256(one.semantic_snapshot).hexdigest())

    def test_unknown_root_and_adapter_are_rejected(self):
        bad = config(); bad["unexpected"] = True
        with self.assertRaisesRegex(ConfigError, "E_CFG_UNKNOWN_FIELD"):
            validate_config(bad, registry())
        bad = config(); bad["runtimes"]["demo"]["adapter"] = "missing"
        with self.assertRaisesRegex(ConfigError, "E_CFG_ADAPTER"):
            validate_config(bad, registry())

    def test_role_and_profile_references_are_explicit(self):
        bad = config(); bad["roles"]["planner"] = {"profile": "missing"}
        with self.assertRaisesRegex(ConfigError, "E_CFG_REFERENCE"):
            validate_config(bad, registry())
        with self.assertRaisesRegex(ConfigError, "E_CFG_CAPABILITY"):
            disabled = config(); disabled["roles"]["planner"] = {"mode": "disabled"}; resolve_profile(disabled, registry(), role="planner")

    def test_local_override_only_changes_selected_executable(self):
        changed = apply_local_overrides(config(), {"runtimes": {"demo": {"executable_by_platform": {"windows": "C:\\tool.exe"}}}}, platform="windows")
        self.assertEqual(changed["runtimes"]["demo"]["command_by_platform"]["windows"][0], "C:\\tool.exe")
        with self.assertRaisesRegex(ConfigError, "E_CFG_PATH"):
            apply_local_overrides(config(), {"profiles": {}}, platform="windows")
        with self.assertRaisesRegex(ConfigError, "E_CFG_PATH"):
            apply_local_overrides(config(), {"runtimes": {"demo": {"command": ["evil"]}}}, platform="windows")

    def test_local_path_must_be_normalized_absolute(self):
        with self.assertRaisesRegex(ConfigError, "E_CFG_PATH"):
            apply_local_overrides(config(), {"runtimes": {"demo": {"executable_by_platform": {"windows": "tool.exe"}}}}, platform="windows")

    def test_credential_values_never_enter_snapshot(self):
        doc = config(); doc["profiles"]["planning"]["credential_refs"] = [{"kind": "env", "name": "TOKEN"}]
        resolved = resolve_profile(doc, registry(), role="planner")
        self.assertNotIn("TOKEN_VALUE", resolved.semantic_snapshot.decode())
        self.assertIn("TOKEN", resolved.semantic_snapshot.decode())

    def test_canonical_bytes_reject_non_finite(self):
        with self.assertRaises(ConfigError):
            canonical_json_bytes({"value": float("nan")})


if __name__ == "__main__":
    unittest.main()
