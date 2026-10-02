"""Boundary contracts for the v2 configuration and policy resolver.

These tests deliberately exercise the policy boundary rather than the runtime
or approval implementations.  A policy can narrow a project declaration, but
it cannot manufacture a new role binding, credential, capability, or model
identity.  The fixtures are offline and contain no credential values.
"""

from __future__ import annotations

import json
import sys
import unittest
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.config_profiles import (  # noqa: E402
    AdapterDescriptor,
    AdapterRegistry,
    ConfigError,
    load_strict_json,
    resolve_profile,
    validate_config,
)


def registry(*, descriptor_version: str = "offline-v1", capabilities=("structured-events",)):
    return AdapterRegistry(
        [AdapterDescriptor("offline", descriptor_version, tuple(capabilities), ("demo-model", "other-model"), ("thinking",))]
    )


def config(*, policies=None):
    return {
        "schema_version": 2,
        "_description": "project declaration",
        "runtimes": {
            "demo": {
                "adapter": "offline",
                "command": ["python", "-m", "demo"],
            }
        },
        "profiles": {
            "planning": {
                "runtime": "demo",
                "model": {"id": "demo-model", "provider": "acme"},
                "options": {"thinking": "high"},
                "credential_refs": [{"kind": "env", "name": "TOKEN"}],
                "_description": "planner profile",
            },
            "alternate": {
                "runtime": "demo",
                "model": {"id": "other-model", "provider": "acme"},
                "options": {"thinking": "high"},
            },
        },
        "roles": {"planner": {"profile": "planning"}},
        "policies": {} if policies is None else policies,
        "platforms": {"windows": {"shell_executable": "cmd.exe", "tools": {}}},
    }


def resolve(doc=None, *, trusted_policy=None, profile_id=None, platform=None, local=None, registry_obj=None):
    return resolve_profile(
        config() if doc is None else doc,
        registry() if registry_obj is None else registry_obj,
        role="planner",
        profile_id=profile_id,
        platform=platform,
        local=local,
        trusted_policy=trusted_policy,
    )


class ConfigPolicyBoundaryTests(unittest.TestCase):
    def test_trusted_and_project_policies_only_tighten_and_empty_lists_deny(self):
        trusted = {
            "role_profiles": {"planner": ["planning"]},
            "allowed_models": [{"adapter": "offline", "id": "demo-model", "provider": "acme"}],
            "required_capabilities": {"planner": ["structured-events"]},
            "environment_allow_names": ["TOKEN"],
        }
        self.assertEqual(resolve(trusted_policy=trusted).profile_id, "planning")

        # An explicit empty allowlist is a deny-all policy, not an omitted rule.
        with self.assertRaises(ConfigError):
            resolve(trusted_policy={"allowed_models": []})
        with self.assertRaises(ConfigError):
            resolve(doc=config(policies={"allowed_models": []}))

        # A project policy cannot expand the role's original binding when no
        # trusted policy is supplied.
        with self.assertRaises(ConfigError):
            resolve(doc=config(policies={"role_profiles": {"planner": ["alternate"]}}), profile_id="alternate")

        # A trusted allowlist also cannot expand the original role binding.
        with self.assertRaises(ConfigError):
            resolve(trusted_policy={"role_profiles": {"planner": ["alternate"]}}, profile_id="alternate")

    def test_model_policy_compares_full_identity_when_provider_is_present(self):
        allowed = {"allowed_models": [{"adapter": "offline", "id": "demo-model", "provider": "acme"}]}
        self.assertEqual(resolve(trusted_policy=allowed).profile_id, "planning")
        with self.assertRaises(ConfigError):
            resolve(trusted_policy={"allowed_models": [{"adapter": "offline", "id": "demo-model", "provider": "other"}]})

        # provider is optional in a policy entry, while adapter and model id
        # remain part of the identity comparison.
        self.assertEqual(resolve(trusted_policy={"allowed_models": [{"adapter": "offline", "id": "demo-model"}]}).profile_id, "planning")

    def test_required_capabilities_and_environment_names_use_intersection(self):
        policy = {
            "required_capabilities": {"planner": ["structured-events"]},
            "environment_allow_names": ["TOKEN"],
        }
        self.assertEqual(resolve(trusted_policy=policy).profile_id, "planning")
        with self.assertRaises(ConfigError):
            resolve(trusted_policy={"required_capabilities": {"planner": ["missing-capability"]}})

        doc = config()
        doc["profiles"]["planning"]["credential_refs"].append({"kind": "env", "name": "OTHER"})
        with self.assertRaises(ConfigError):
            resolve(doc=doc, trusted_policy={"environment_allow_names": ["TOKEN"]})

        # Both allowlists participate in the effective intersection.
        doc = config(policies={"environment_allow_names": ["TOKEN", "OTHER"]})
        self.assertEqual(resolve(doc=doc, trusted_policy={"environment_allow_names": ["TOKEN"]}).profile_id, "planning")

    def test_strict_json_rejects_bom_nonfinite_oversize_and_deep_documents(self):
        with self.assertRaises(ConfigError):
            load_strict_json(b"\xef\xbb\xbf{" + b'"schema_version":2}')
        with self.assertRaises(ConfigError):
            load_strict_json(b'{"schema_version":2,"value":1e999}')
        with self.assertRaises(ConfigError):
            load_strict_json(b'{"schema_version":2,"value":"' + (b"x" * (1024 * 1024)) + b'"}')
        nested = b'{"schema_version":2,"value":' + (b"[" * 65) + b"0" + (b"]" * 65) + b"}"
        with self.assertRaises(ConfigError):
            load_strict_json(nested)
        with self.assertRaises(ConfigError):
            validate_config(load_strict_json(b'{"schema_version":true}'), registry())

    def test_root_notes_are_limited_and_source_report_is_flat_tuple_of_mappings(self):
        result = resolve()
        self.assertIsInstance(result.source_report, tuple)
        self.assertTrue(result.source_report)
        self.assertTrue(all(isinstance(item, Mapping) for item in result.source_report))
        self.assertFalse(any(isinstance(item, tuple) for item in result.source_report))

        bad = config()
        bad["_internal"] = "must be rejected"
        with self.assertRaises(ConfigError):
            resolve(doc=bad)

    def test_semantic_hash_tracks_descriptor_and_policy_but_not_descriptions(self):
        base = resolve()

        described = config()
        described["_description"] = "a different description"
        described["profiles"]["planning"]["_description"] = "another description"
        self.assertEqual(base.semantic_sha256, resolve(doc=described).semantic_sha256)

        changed_descriptor = resolve(registry_obj=registry(descriptor_version="offline-v2"))
        self.assertNotEqual(base.semantic_sha256, changed_descriptor.semantic_sha256)
        changed_capability = resolve(registry_obj=registry(capabilities=("structured-events", "streaming")))
        self.assertNotEqual(base.semantic_sha256, changed_capability.semantic_sha256)

        trusted = {"allowed_models": [{"adapter": "offline", "id": "demo-model", "provider": "acme"}]}
        self.assertNotEqual(base.semantic_sha256, resolve(trusted_policy=trusted).semantic_sha256)
        project = config(policies=trusted)
        self.assertNotEqual(base.semantic_sha256, resolve(doc=project).semantic_sha256)

    def test_local_override_requires_platform_and_rejects_cross_platform_branches(self):
        local = {"runtimes": {"demo": {"executable_by_platform": {"windows": r"C:\tool.exe"}}}}
        with self.assertRaises(ConfigError):
            resolve(local=local)
        with self.assertRaises(ConfigError):
            resolve(platform="windows", local={"runtimes": {"demo": {"executable_by_platform": {"linux": "/usr/bin/tool"}}}})

    def test_protected_paths_are_relative_and_approval_is_a_boolean_policy(self):
        self.assertEqual(resolve(trusted_policy={"protected_paths": ["docs/private"], "approval_required": True}).profile_id, "planning")
        with self.assertRaises(ConfigError):
            resolve(trusted_policy={"protected_paths": ["../outside"]})
        with self.assertRaises(ConfigError):
            resolve(trusted_policy={"protected_paths": ["/absolute/path"]})
        with self.assertRaises(ConfigError):
            resolve(trusted_policy={"approval_required": "yes"})

    def test_windows_override_uses_windows_path_rules(self):
        local = {"runtimes": {"demo": {"executable_by_platform": {"windows": r"C:\tool.exe"}}}}
        result = resolve(platform="windows", local=local)
        self.assertEqual(result.platform, "windows")
        self.assertEqual(json.loads(result.semantic_snapshot)["command"][0], r"C:\tool.exe")


if __name__ == "__main__":
    unittest.main()
