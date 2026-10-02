from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from codekit.identity import BootIdentity, EnvironmentIdentity, HostIdentity, ProcessIdentity, canonical_opaque_key
from codekit.runtime_lease import LeaseError, assess_lease, issue_lease, release_lease


def owner():
    host = HostIdentity.from_facts("host", "windows", "Windows", "x64")
    boot = BootIdentity.from_facts(host, "boot")
    env = EnvironmentIdentity.from_facts("env", "native", host, boot, "x64", "10", "ntfs")
    return ProcessIdentity(host.canonical_key, boot.canonical_key, env.canonical_key,
                           canonical_opaque_key("worktree", "w"), canonical_opaque_key("run", "run"),
                           123, canonical_opaque_key("creation", "c"), canonical_opaque_key("entry", "e"),
                           process_group_key=canonical_opaque_key("pg", "123"))


class RuntimeLeaseTests(unittest.TestCase):
    def test_pid_only_cannot_issue_lease(self):
        with self.assertRaises(LeaseError) as caught:
            issue_lease("run", ProcessIdentity(pid=123), generation=1, expires_at=10)
        self.assertEqual(caught.exception.code, "E_OWNER_UNKNOWN")

    def test_expired_live_owner_is_held_and_unknown_is_blocked(self):
        lease = issue_lease("run", owner(), generation=1, expires_at=10)
        self.assertEqual(assess_lease(lease, current_generation=1, observed_owner=owner(), process_alive=True, now=11).decision, "HOLD")
        self.assertEqual(assess_lease(lease, current_generation=1, observed_owner=owner(), process_alive=None, now=11).decision, "BLOCK")
        self.assertEqual(assess_lease(lease, current_generation=1, observed_owner=owner(), process_alive=False, now=11).decision, "RECLAIM_ALLOWED")

    def test_generation_identity_and_release_token_fence_owner(self):
        first = owner()
        lease = issue_lease("run", first, generation=2, expires_at=10)
        self.assertEqual(assess_lease(lease, current_generation=3, observed_owner=first, process_alive=False, now=11).reasons, ("FENCED_GENERATION",))
        other = ProcessIdentity(pid=999)
        self.assertEqual(assess_lease(lease, current_generation=2, observed_owner=other, process_alive=False, now=11).reasons, ("OWNER_IDENTITY_MISMATCH",))
        self.assertEqual(release_lease(lease, token="bad", owner=first, generation=2).decision, "BLOCK")
        self.assertEqual(release_lease(lease, token=lease.token, owner=first, generation=2).decision, "RELEASE_ALLOWED")


if __name__ == "__main__":
    unittest.main()
