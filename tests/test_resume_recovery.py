from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from codekit.resume_recovery import resume_recovery_decision, RecoveryError  # noqa: E402


def facts(**changes):
    result = {"recorded_generation": 3, "history_preserved": True, "budget_not_increased": True,
              "resource_holds_reconciled": True, "external_scope_empty": True, "resume_authorized": True,
              "backup_high_water": 10, "journal_high_water": 10, "resource_high_water": 10, "auth_high_water": 10}
    result.update(changes)
    return result


class ResumeRecoveryTests(unittest.TestCase):
    def test_all_high_water_and_cas_gates_are_required(self):
        self.assertEqual(resume_recovery_decision(facts(), expected_generation=3).decision, "RESUME_ALLOWED")
        blocked = resume_recovery_decision(facts(recorded_generation=2), expected_generation=3)
        self.assertEqual(blocked.reasons, ("WAIT_GENERATION_RECHECK",))

    def test_history_budget_and_external_unknowns_never_become_success(self):
        blocked = resume_recovery_decision(facts(history_preserved=False, budget_not_increased=False,
                                                external_scope_empty=False), expected_generation=3)
        self.assertIn("WAIT_HISTORY_PRESERVED", blocked.reasons)
        self.assertIn("WAIT_BUDGET_NOT_INCREASED", blocked.reasons)
        self.assertIn("WAIT_EXTERNAL_SCOPE_EMPTY", blocked.reasons)

    def test_schema_is_closed_and_high_water_cannot_regress(self):
        with self.assertRaises(RecoveryError):
            resume_recovery_decision({**facts(), "extra": True}, expected_generation=3)
        blocked = resume_recovery_decision(facts(backup_high_water=1), expected_generation=3)
        self.assertIn("WAIT_BACKUP_HIGH_WATER", blocked.reasons)


if __name__ == "__main__":
    unittest.main()
