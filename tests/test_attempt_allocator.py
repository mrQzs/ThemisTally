from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from codekit.attempt_allocator import Candidate, AllocationError, allocate_candidates, order_candidates  # noqa: E402


class AttemptAllocatorTests(unittest.TestCase):
    def test_priority_window_and_task_id_are_stable_tie_breakers(self):
        items = [Candidate("b", 1, 1), Candidate("a", 1, 1), Candidate("c", 2, 8)]
        self.assertEqual(tuple(item.task_id for item in order_candidates(items)), ("c", "a", "b"))

    def test_resources_are_all_or_nothing_and_capacity_is_fair(self):
        result = allocate_candidates([Candidate("a", 2, 1, ("module:a", "port:a")),
                                      Candidate("b", 1, 1, ("module:a",)), Candidate("c", 1, 2, ("module:c",))],
                                     capacity=2)
        self.assertEqual(tuple(item.task_id for item in result.selected), ("a", "c"))
        self.assertIn(("b", "WAIT_RESOURCE"), result.waiting)

    def test_unknown_budget_and_recovery_never_look_like_completion(self):
        result = allocate_candidates([Candidate("a", 1, 1, budget_available=None)], capacity=1)
        self.assertEqual(result.diagnostic, "WAIT_BUDGET")
        result = allocate_candidates([Candidate("a", 1, 1, wait_reason="RECOVERY_REQUIRED")], capacity=1)
        self.assertEqual(result.diagnostic, "RECOVERY_REQUIRED")

    def test_invalid_resource_order_is_rejected(self):
        with self.assertRaises(AllocationError):
            Candidate("a", 1, 1, ("z", "a"))


if __name__ == "__main__":
    unittest.main()
