import json
import unittest
from pathlib import Path

from scripts.codekit.adapters.capability import AdapterCapability, CapabilityError, CapabilityEvidence, bind_profile


def capability():
    return AdapterCapability("second-cli-offline", "second-cli-v1", "offline-fixture-1", ("linux",),
                             ("planner", "executor"), ("streaming_events", "terminal_event", "model_identity", "tool_events", "usage"),
                             "required", "posix", tuple(CapabilityEvidence(name, "synthetic", note="offline fixture") for name in
                             ("streaming_events", "terminal_event", "model_identity", "tool_events", "usage")), True)


class AdapterCapabilityTests(unittest.TestCase):
    def test_binding_requires_role_platform_model_and_capabilities(self):
        value = capability()
        self.assertTrue(bind_profile(value, role="planner", platform="linux", required_capabilities=("terminal_event",), model_id="model-fixture").supported)
        blocked = bind_profile(value, role="observer", platform="windows", required_capabilities=("read_only_mode",), model_id=None)
        self.assertFalse(blocked.supported); self.assertIn("ROLE_UNSUPPORTED", blocked.reasons); self.assertIn("MODEL_REQUIRED", blocked.reasons)

    def test_observed_evidence_is_distinct_from_synthetic(self):
        value = capability()
        binding = bind_profile(value, role="planner", platform="linux", required_capabilities=("usage",), model_id="m", require_observed=True)
        self.assertFalse(binding.supported); self.assertTrue(any(item.startswith("EVIDENCE_NOT_OBSERVED") for item in binding.reasons))

    def test_observed_evidence_requires_closed_resource_ref(self):
        with self.assertRaises(CapabilityError):
            CapabilityEvidence("usage", "observed")
        with self.assertRaises(CapabilityError):
            CapabilityEvidence("usage", "observed", {"kind": "x"})

    def test_every_declared_capability_has_an_evidence_state(self):
        with self.assertRaises(CapabilityError):
            AdapterCapability("x", "v", "v", ("linux",), ("planner",), ("usage", "terminal_event"),
                              "optional", "posix", (CapabilityEvidence("usage", "synthetic"),), True)

    def test_wsl_is_environment_kind_under_linux(self):
        value = AdapterCapability("x", "v", "v", ("linux",), ("planner",), ("usage",),
                                  "optional", "posix", (CapabilityEvidence("usage", "synthetic"),),
                                  True, ("wsl",))
        binding = bind_profile(value, role="planner", platform="linux", environment_kind="wsl",
                               required_capabilities=("usage",))
        self.assertTrue(binding.supported)

    def test_closed_schema_and_json_are_valid(self):
        with self.assertRaises(CapabilityError):
            AdapterCapability("x", "v", "v", ("linux",), ("planner",), ("unknown",), "unknown", "posix", (), True)
        schema = json.loads(Path("schemas/adapter-capability-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "urn:codekit:adapter-capability:1")


if __name__ == "__main__":
    unittest.main()
