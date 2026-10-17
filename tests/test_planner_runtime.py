import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.planner_runtime import (  # noqa: E402
    PlannerRuntimeError,
    RepairController,
    RequestBudget,
    PlanningBudgetLedger,
    extract_unique_result,
    readiness_projection,
)


class PlannerRuntimeTests(unittest.TestCase):
    def facts(self):
        return {
            "inputs_accepted": True, "baseline_present": True, "baseline_authorized": True,
            "planner_authorized": True, "planner_environment_ok": True, "planner_budget_ok": True,
            "input_locks_ok": True, "request_open": True,
            "contract_current": True, "approval_current": True, "capabilities_ok": True,
            "execution_authorized": True, "budget_ok": True, "conflicts_clear": True,
        }

    def test_readiness_has_three_independent_gates(self):
        result = readiness_projection(self.facts())
        self.assertTrue(result["can_refine"])
        self.assertTrue(result["can_start_planner"])
        self.assertTrue(result["can_execute"])
        facts = self.facts(); facts["contract_current"] = False
        result = readiness_projection(facts)
        self.assertTrue(result["can_start_planner"])
        self.assertFalse(result["can_execute"])
        facts = self.facts(); facts["planner_budget_ok"] = None
        result = readiness_projection(facts)
        self.assertTrue(result["can_refine"])
        self.assertFalse(result["can_start_planner"])
        self.assertIn("WAIT_PLANNER_PLANNER_BUDGET_OK", result["reasons"])

    def test_unique_result_replay_and_ambiguity(self):
        event = {"event_id": "e1", "event_type": "planning.result", "payload": {"x": 1},
                 "complete": True, "terminated": True}
        self.assertEqual(extract_unique_result([event, dict(event)]), {"x": 1})
        with self.assertRaisesRegex(PlannerRuntimeError, "E_RESULT_AMBIGUOUS"):
            extract_unique_result([event, {**event, "event_id": "e2"}])
        with self.assertRaisesRegex(PlannerRuntimeError, "E_RESULT_REPLAY_CONFLICT"):
            extract_unique_result([event, {**event, "payload": {"x": 2}}])
        with self.assertRaisesRegex(PlannerRuntimeError, "E_RESULT_INCOMPLETE"):
            extract_unique_result([{**event, "complete": False}])
        with self.assertRaisesRegex(PlannerRuntimeError, "E_RESULT_INCOMPLETE"):
            extract_unique_result([{key: value for key, value in event.items() if key != "terminated"}])

    def test_repair_controller_stops_on_loop_and_limit(self):
        controller = RepairController()
        self.assertTrue(controller.allow(error_family="json", field="/x"))
        self.assertFalse(controller.allow(error_family="json", field="/x"))
        self.assertEqual(controller.stopped, "REPAIR_LOOP")

    def test_request_budget_is_single_root_and_generation_fenced(self):
        ledger = RequestBudget("req-1", 3)
        ledger.reserve(2)
        with self.assertRaisesRegex(PlannerRuntimeError, "E_BUDGET_EXHAUSTED"):
            ledger.reserve(2)
        ledger.settle(1)
        ledger.stop("cancelled")
        with self.assertRaisesRegex(PlannerRuntimeError, "E_BUDGET_STOPPED"):
            ledger.reserve(1)
        ledger.restart_controller()
        with self.assertRaisesRegex(PlannerRuntimeError, "E_GENERATION"):
            ledger.settle(1, generation=1)

    def test_planning_budget_delegates_to_core_ledger(self):
        ledger = PlanningBudgetLedger.calls("req-core", "task-core", 3)
        ledger, status = ledger.reserve("op-core", 2)
        self.assertEqual(status, "RESERVED")
        ledger, status = ledger.observe("op-core", 1, observation_id="obs-core")
        self.assertEqual(status, "APPLIED")
        ledger, status = ledger.settle("op-core")
        self.assertEqual(status, "SETTLED")
        self.assertEqual(ledger.snapshot().dimensions["calls"].known, 1)

    def test_planning_budget_operation_binding_is_read_only_and_generation_fenced(self):
        ledger = PlanningBudgetLedger.calls("req-core", "task-core", 2)
        with self.assertRaisesRegex(PlannerRuntimeError, "E_BUDGET_OPERATION"):
            ledger.require_operation("missing")
        ledger, _ = ledger.reserve("op-bound", 1)
        ledger.require_operation("op-bound")
        with self.assertRaisesRegex(PlannerRuntimeError, "E_GENERATION"):
            replace(ledger, generation=2).require_operation("op-bound")
        stopped = ledger.stop("cancelled")
        with self.assertRaisesRegex(PlannerRuntimeError, "E_BUDGET_STOPPED"):
            stopped.require_operation("op-bound")


if __name__ == "__main__":
    unittest.main()
