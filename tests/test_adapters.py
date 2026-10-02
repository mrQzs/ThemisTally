import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.adapters import AdapterDescriptor, AdapterError, AdapterRegistry, Invocation, OfflineAdapter, normalize_events


def invocation():
    return Invocation("req", "run", "executor", "offline-profile", ("python", "-c", "pass"), ("structured-events",), "a" * 64)


def event(seq, typ, payload=None, event_id=None):
    return {"seq": seq, "event_id": event_id or f"e{seq}", "type": typ, "source": "offline", "payload": payload or {}}


class AdapterTests(unittest.TestCase):
    def test_registry_rejects_unknown_and_duplicate(self):
        reg = AdapterRegistry([AdapterDescriptor("offline", "v1", ("structured-events",), ("executor",), True)])
        with self.assertRaisesRegex(AdapterError, "E_ADAPTER_UNKNOWN"):
            reg.resolve("missing")
        with self.assertRaisesRegex(AdapterError, "E_ADAPTER_DUPLICATE"):
            reg.register(AdapterDescriptor("offline", "v1", (), (), True))

    def test_probe_is_explicitly_offline(self):
        self.assertEqual(OfflineAdapter().probe()["process_started"], False)

    def test_invocation_can_bind_adapter_identity(self):
        reg = AdapterRegistry([AdapterDescriptor("offline", "v1", ("structured-events",), ("executor",), True)])
        bound = Invocation("req", "run", "executor", "offline-profile", ("python",), ("structured-events",), "a" * 64, "offline")
        self.assertEqual(reg.validate_invocation(bound).adapter_id, "offline")
        with self.assertRaisesRegex(AdapterError, "E_ADAPTER_IDENTITY"):
            OfflineAdapter().run(Invocation("req", "run", "executor", "offline-profile", ("python",), (), "a" * 64, "other"), [event(0, "run_started")])

    def test_events_normalize_in_order_and_usage_is_preserved(self):
        result = OfflineAdapter().run(invocation(), [event(0, "run_started"), event(1, "usage", {"input": "3"}), event(2, "run_finished")])
        self.assertTrue(result.settled); self.assertEqual(result.status, "SUCCEEDED"); self.assertEqual(result.usage["input"], "3")

    def test_gap_duplicate_unknown_and_wrong_source_are_rejected(self):
        with self.assertRaisesRegex(AdapterError, "E_ADAPTER_EVENT_GAP"):
            normalize_events([event(1, "run_started")], expected_source="offline")
        with self.assertRaisesRegex(AdapterError, "E_ADAPTER_EVENT_DUPLICATE"):
            normalize_events([event(0, "run_started", event_id="x"), event(1, "assistant", event_id="x")], expected_source="offline")
        with self.assertRaisesRegex(AdapterError, "E_ADAPTER_EVENT_TYPE"):
            normalize_events([event(0, "wat")], expected_source="offline")
        with self.assertRaisesRegex(AdapterError, "E_ADAPTER_SOURCE"):
            normalize_events([{**event(0, "run_started"), "source": "pi"}], expected_source="offline")

    def test_missing_terminal_is_unknown_not_success(self):
        result = OfflineAdapter().run(invocation(), [event(0, "run_started"), event(1, "assistant")])
        self.assertFalse(result.settled); self.assertEqual(result.status, "UNKNOWN"); self.assertFalse(result.raw_complete)


if __name__ == "__main__":
    unittest.main()
