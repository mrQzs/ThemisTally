"""07 recovery/resume gate tests."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit import protocols  # noqa: E402
from codekit.recovery import RESUME_FACTS, resume_decision  # noqa: E402


class RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.facts = {name: True for name in RESUME_FACTS}

    def test_resume_requires_all_recovery_facts(self) -> None:
        self.assertEqual(resume_decision(self.facts), {"decision": "RESUME_ALLOWED", "reasons": []})
        for name in RESUME_FACTS:
            facts = copy.deepcopy(self.facts)
            facts[name] = False
            result = resume_decision(facts)
            self.assertEqual(result["decision"], "BLOCK")
            self.assertEqual(result["reasons"], [f"WAIT_{name.upper()}"])

    def test_multiple_gaps_preserve_fixed_reason_order(self) -> None:
        facts = copy.deepcopy(self.facts)
        facts["budget_reconciled"] = False
        facts["unknown_start_resolved"] = False
        facts["resume_authorized"] = False
        result = resume_decision(facts)
        self.assertEqual(result["reasons"], [
            "WAIT_UNKNOWN_START_RESOLVED", "WAIT_BUDGET_RECONCILED", "WAIT_RESUME_AUTHORIZED",
        ])

    def test_stopped_flag_is_not_cleared_by_projection(self) -> None:
        facts = copy.deepcopy(self.facts)
        before = copy.deepcopy(facts)
        resume_decision(facts)
        self.assertEqual(facts, before)

    def test_fact_shape_is_closed_and_exact_boolean(self) -> None:
        with self.assertRaises(protocols.ProtocolError) as caught:
            resume_decision({"request_stopped": True})
        self.assertEqual(caught.exception.code, "E_SCHEMA_FIELDS")
        facts = copy.deepcopy(self.facts)
        facts["budget_reconciled"] = 1
        with self.assertRaises(protocols.ProtocolError) as caught:
            resume_decision(facts)
        self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
