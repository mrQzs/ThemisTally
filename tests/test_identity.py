#!/usr/bin/env python3
"""07-S1.3 deterministic identity model tests.

These tests exercise only the pure model.  Windows/macOS adapters and real
OS/process observations are deliberately marked NOT_RUN by this test module.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.identity import (  # noqa: E402
    KNOWN, UNKNOWN, BootIdentity, EnvironmentIdentity, HostIdentity, IdentityModelError,
    ProcessIdentity, ResourceClaim, ResourceIdentity, WorktreeIdentity, canonical_opaque_key,
    claims_conflict, process_identity_decision, resource_claim_decision,
)


class IdentityTests(unittest.TestCase):
    def host(self) -> HostIdentity:
        return HostIdentity.from_facts("host-a", "windows", "Windows-11", "x86_64")

    def environment(self) -> EnvironmentIdentity:
        host = self.host()
        boot = BootIdentity.from_facts(host, "boot-a")
        return EnvironmentIdentity.from_facts("env-a", "native", host, boot,
                                              "x86_64", "10.0", "windows-case-insensitive")

    def test_canonical_key_is_deterministic_and_opaque(self) -> None:
        left = canonical_opaque_key("path", {"path": "src/a"})
        right = canonical_opaque_key("path", {"path": "src/a"})
        alias = canonical_opaque_key("path", {"path": "./src/a"})
        self.assertEqual(left, right)
        self.assertNotEqual(left, alias)
        self.assertNotIn("src", left)
        self.assertRegex(left, r"^opaque:v1:path:[0-9a-f]{64}$")

    def test_identity_hash_rejects_cycles_and_non_scalar_unicode(self) -> None:
        with self.assertRaises(IdentityModelError):
            canonical_opaque_key("path", "bad\ud800")
        cyclic = []
        cyclic.append(cyclic)
        with self.assertRaises(IdentityModelError):
            canonical_opaque_key("path", cyclic)

    def test_host_boot_environment_worktree_are_known_only_with_complete_facts(self) -> None:
        host = self.host()
        self.assertEqual(host.status, KNOWN)
        boot = BootIdentity.from_facts(host, "boot-a")
        self.assertEqual(boot.status, KNOWN)
        env = self.environment()
        self.assertEqual(env.status, KNOWN)
        wt = WorktreeIdentity.from_facts("repo-a", canonical_opaque_key("worktree", "w"),
                                         canonical_opaque_key("git-common", "g"), "sha1")
        self.assertEqual(wt.status, KNOWN)
        self.assertEqual(HostIdentity().status, UNKNOWN)

    def test_environment_rejects_unregistered_kind_and_unknown_host(self) -> None:
        with self.assertRaises(IdentityModelError):
            EnvironmentIdentity.from_facts("env", "darwin", self.host(), BootIdentity(), "arm64", "x", "p")
        with self.assertRaises(IdentityModelError):
            EnvironmentIdentity.from_facts("env", "native", HostIdentity(), BootIdentity(), "x", "x", "p")

    def test_process_pid_only_is_unknown_and_blocked(self) -> None:
        identity = ProcessIdentity(pid=1234)
        decision = process_identity_decision(identity)
        self.assertEqual(identity.status, UNKNOWN)
        self.assertEqual(decision.status, UNKNOWN)
        self.assertTrue(decision.blocked)
        self.assertIn("pid_only_identity", decision.reasons)

    def test_process_requires_host_boot_environment_worktree_and_scope(self) -> None:
        env = self.environment()
        host = self.host()
        boot = BootIdentity.from_facts(host, "boot-a")
        process = ProcessIdentity(host.canonical_key, boot.canonical_key, env.canonical_key,
                                  canonical_opaque_key("worktree", "w"),
                                  canonical_opaque_key("run", "run-a"), 1234,
                                  canonical_opaque_key("creation", "create-a"),
                                  canonical_opaque_key("entry", "python"),
                                  process_group_key=canonical_opaque_key("pgid", "1234"))
        self.assertEqual(process.status, KNOWN)
        self.assertFalse(process_identity_decision(process).blocked)
        self.assertIsNotNone(process.canonical_key)
        self.assertNotEqual(process.canonical_key, ProcessIdentity(pid=1234).canonical_key)

    def test_resource_identity_does_not_resolve_path_aliases(self) -> None:
        left = ResourceIdentity.from_facts("repo-a", "path", {"path": "src/a"})
        alias = ResourceIdentity.from_facts("repo-a", "path", {"path": "./src/a"})
        self.assertEqual(left.status, KNOWN)
        self.assertNotEqual(left.canonical_key, alias.canonical_key)

    def test_unknown_resource_and_mode_block(self) -> None:
        unknown = ResourceClaim(ResourceIdentity("repo-a", "path"), "write")
        unknown_mode = ResourceClaim(ResourceIdentity.from_facts("repo-a", "key", "x"), "unknown")
        self.assertTrue(resource_claim_decision(unknown).blocked)
        self.assertTrue(resource_claim_decision(unknown_mode).blocked)
        self.assertTrue(claims_conflict(unknown, unknown_mode))

    def test_known_read_claims_share_and_write_claims_conflict(self) -> None:
        resource = ResourceIdentity.from_facts("repo-a", "module", "module:a")
        read = ResourceClaim(resource, "read")
        write = ResourceClaim(resource, "write")
        self.assertFalse(claims_conflict(read, read))
        self.assertTrue(claims_conflict(read, write))

    def test_worktree_does_not_normalize_or_guess_aliases(self) -> None:
        key_a = canonical_opaque_key("worktree", "C:/repo/a")
        key_b = canonical_opaque_key("worktree", "c:\\repo\\a")
        self.assertNotEqual(key_a, key_b)
        wt = WorktreeIdentity("repo-a", key_a, canonical_opaque_key("common", "x"))
        self.assertEqual(wt.status, KNOWN)

    def test_direct_partial_constructors_do_not_promote_empty_facts(self) -> None:
        self.assertEqual(HostIdentity("", "windows", "Windows", "x64").status, UNKNOWN)
        self.assertEqual(BootIdentity(canonical_opaque_key("host", "h"), "").status, UNKNOWN)
        self.assertEqual(ResourceIdentity("", "path", canonical_opaque_key("path", "x")).status, UNKNOWN)

    @unittest.skip("NOT_RUN: Windows/macOS real adapter and OS lock integration are outside pure S1.3")
    def test_windows_and_macos_real_adapters(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
