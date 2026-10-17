#!/usr/bin/env python3
"""07-T2A pure readiness projection tests."""
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
from codekit.readiness import READINESS_FACTS, readiness  # noqa: E402


class ReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.facts = {name: True for name in READINESS_FACTS}

    def test_all_guards_allow_refinement_and_execution(self) -> None:
        self.assertEqual(readiness(self.facts), {
            "can_refine": True,
            "can_execute": True,
            "reasons": [],
        })

    def test_contract_and_approval_can_block_execution_after_refinement(self) -> None:
        facts = copy.deepcopy(self.facts)
        facts["contract_current"] = False
        facts["approval_current"] = False
        self.assertTrue(readiness(facts)["can_refine"])
        self.assertFalse(readiness(facts)["can_execute"])
        self.assertEqual(readiness(facts)["reasons"], ["WAIT_CONTRACT_CURRENT", "WAIT_APPROVAL_CURRENT"])

    def test_baseline_guards_block_refinement(self) -> None:
        for name in ("inputs_accepted", "baseline_present", "baseline_authorized"):
            with self.subTest(guard=name):
                facts = copy.deepcopy(self.facts)
                facts[name] = False
                report = readiness(facts)
                self.assertFalse(report["can_refine"])
                self.assertFalse(report["can_execute"])
                self.assertEqual(report["reasons"], [f"WAIT_{name.upper()}"])

    def test_every_execution_guard_has_a_stable_reason(self) -> None:
        for name in READINESS_FACTS:
            with self.subTest(guard=name):
                facts = copy.deepcopy(self.facts)
                facts[name] = False
                report = readiness(facts)
                self.assertFalse(report["can_execute"])
                self.assertIn(f"WAIT_{name.upper()}", report["reasons"])

    def test_fact_shape_and_types_are_rejected(self) -> None:
        with self.assertRaises(protocols.ProtocolError) as caught:
            readiness({"inputs_accepted": True})
        self.assertEqual(caught.exception.code, "E_SCHEMA_FIELDS")
        self.assertEqual(caught.exception.field, "/facts")

        facts = copy.deepcopy(self.facts)
        facts["budget_ok"] = 1
        with self.assertRaises(protocols.ProtocolError) as caught:
            readiness(facts)
        self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")
        self.assertEqual(caught.exception.field, "/facts/budget_ok")

        with self.assertRaises(protocols.ProtocolError) as caught:
            readiness([])  # type: ignore[arg-type]
        self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")

    def test_projection_does_not_mutate_facts(self) -> None:
        facts = copy.deepcopy(self.facts)
        before = copy.deepcopy(facts)
        readiness(facts)
        self.assertEqual(facts, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
