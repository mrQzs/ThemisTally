import json
import unittest
from pathlib import Path

from scripts.codekit.project_delivery import evaluate_release_gate, offline_fault_matrix, request_pull_delivery


class ProjectDeliveryTests(unittest.TestCase):
    def test_pull_delivery_is_deterministic_and_not_run_without_host(self):
        view_id = "a" * 64
        first = request_pull_delivery(view_id, observer_ref="observer-1")
        second = request_pull_delivery(view_id, observer_ref="observer-1")
        self.assertEqual(first, second); self.assertEqual(first.status, "NOT_RUN")

    def test_fault_matrix_and_gate_never_promote_blocked_capabilities(self):
        matrix = offline_fault_matrix(); self.assertEqual(len(matrix), 30)
        self.assertTrue(all(item["production"] == "NOT_RUN/BLOCKED" for item in matrix))
        gate = evaluate_release_gate({"S1": "ACCEPTED_WITH_EXCEPTION"}, real_capabilities={"host_delivery": "blocked", "provider": "not_run"})
        self.assertEqual(gate["status"], "BLOCKED"); self.assertFalse(gate["production_release"])
        ready = evaluate_release_gate({"S1": "PASS"}, real_capabilities={"host_delivery": "verified"})
        self.assertEqual(ready["status"], "PASS"); self.assertTrue(ready["production_release"])

    def test_schemas_are_valid_json(self):
        for path in ("schemas/delivery-receipt-v1.schema.json", "schemas/release-gate-v1.schema.json"):
            self.assertTrue(json.loads(Path(path).read_text(encoding="utf-8"))["$id"].startswith("urn:codekit:"))


if __name__ == "__main__":
    unittest.main()
