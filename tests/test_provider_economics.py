"""Offline provider identity and call-observation facts."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.provider_economics import (  # noqa: E402
    CallVisibility,
    EconomicCallIdentity,
    EconomicsError,
    OfflineBillingAdapter,
    ProviderCallObservation,
    ProviderIdentity,
    canonical_json,
    canonical_sha256,
)


def identity(*, run_id="run-a", call_id="call-a", request_id="request-a", task_id="task-a"):
    return EconomicCallIdentity(call_id, "offline", "fixture-v1", "acct-a", "fixture",
                                request_id=request_id, task_id=task_id, run_id=run_id)


def observation(*, observation_id="obs-a", run_id="run-a", call_id="call-a", amount=12,
                visibility="complete", request_id="request-a", task_id="task-a"):
    return ProviderCallObservation(observation_id, identity(run_id=run_id, call_id=call_id,
                                                            request_id=request_id,
                                                            task_id=task_id), visibility,
                                   {"input_tokens": 4, "output_tokens": 8},
                                   "USD", amount, "fixture-evidence")


class ProviderEconomicsTests(unittest.TestCase):
    def test_empty_adapter_does_not_claim_complete_visibility(self):
        self.assertEqual(OfflineBillingAdapter().coverage(), CallVisibility.UNKNOWN)

    def test_canonical_json_is_sorted_and_hashed(self):
        self.assertEqual(canonical_json({"b": 2, "a": 1}), '{"a":1,"b":2}')
        self.assertEqual(canonical_sha256({"a": 1}),
                         "015abd7f5cc57a2dd94b7590f04ad808" \
                         "4273905ee33ec5cebeae62276a97f862")

    def test_canonical_rejects_float(self):
        with self.assertRaises(EconomicsError) as ctx:
            canonical_json({"amount": 1.5})
        self.assertEqual(ctx.exception.code, "E_FLOAT")

    def test_canonical_rejects_cycles_and_surrogate_scalars(self):
        value = {}
        value["self"] = value
        with self.assertRaises(EconomicsError) as cycle:
            canonical_json(value)
        self.assertEqual(cycle.exception.code, "E_CANONICAL")
        with self.assertRaises(EconomicsError) as surrogate:
            canonical_json({"value": "\ud800"})
        self.assertEqual(surrogate.exception.code, "E_CANONICAL")
        with self.assertRaises(EconomicsError):
            canonical_sha256({"\ud800": "value"})

    def test_canonical_rejects_unsafe_integer_and_numeric_subclass(self):
        with self.assertRaises(EconomicsError) as unsafe:
            canonical_json({"value": 2**53})
        self.assertEqual(unsafe.exception.code, "E_CANONICAL")
        from enum import IntEnum

        class Value(IntEnum):
            ONE = 1

        with self.assertRaises(EconomicsError) as subclass:
            canonical_json({"value": Value.ONE})
        self.assertEqual(subclass.exception.code, "E_CANONICAL")

    def test_canonical_keeps_boolean_distinct_from_integer(self):
        self.assertEqual(canonical_json({"value": True}), '{"value":true}')

    def test_provider_identity_isolated_by_account_source_and_model(self):
        first = ProviderIdentity("vendor", "model", "acct-a", "offline")
        second = ProviderIdentity("vendor", "model", "acct-b", "offline")
        third = ProviderIdentity("vendor", "model", "acct-a", "recorded")
        self.assertNotEqual(first.fingerprint, second.fingerprint)
        self.assertNotEqual(first.fingerprint, third.fingerprint)

    def test_call_key_excludes_run_for_cross_run_dedupe(self):
        self.assertEqual(identity(run_id="run-a").call_key, identity(run_id="run-b").call_key)
        self.assertNotEqual(identity(call_id="call-a").call_key, identity(call_id="call-b").call_key)

    def test_call_key_excludes_request_and_task_for_cross_scope_dedupe(self):
        first = identity(run_id="run-a", request_id="request-a", task_id="task-a")
        second = identity(run_id="run-b", request_id="request-b", task_id="task-b")
        self.assertEqual(first.call_key, second.call_key)
        self.assertEqual(first.as_call_dict(), second.as_call_dict())

    def test_same_call_same_payload_across_tasks_and_requests_is_mirror(self):
        adapter = OfflineBillingAdapter()
        adapter.observe(observation(observation_id="obs-a", run_id="run-a",
                                    request_id="request-a", task_id="task-a"))
        result = adapter.observe(observation(observation_id="obs-b", run_id="run-b",
                                             request_id="request-b", task_id="task-b"))
        self.assertEqual(result.status, "MIRROR")
        self.assertTrue(result.historical)
        self.assertEqual(len(adapter.observations), 2)

    def test_same_call_different_scope_with_different_facts_is_conflict(self):
        adapter = OfflineBillingAdapter()
        adapter.observe(observation(observation_id="obs-a", request_id="request-a",
                                    task_id="task-a"))
        with self.assertRaises(EconomicsError) as ctx:
            adapter.observe(observation(observation_id="obs-b", request_id="request-b",
                                        task_id="task-b", amount=13))
        self.assertEqual(ctx.exception.code, "E_CALL_CONFLICT")

    def test_observation_visibility_and_units_are_bounded(self):
        item = observation(visibility=CallVisibility.PARTIAL)
        self.assertEqual(item.coverage, "partial")
        self.assertEqual(item.units["output_tokens"], 8)
        with self.assertRaises(EconomicsError):
            ProviderCallObservation("bad", identity(), "not-known", {}, None, None)
        with self.assertRaises(EconomicsError):
            ProviderCallObservation("bad", identity(), units={"tokens": 1.2})

    def test_same_observation_replays(self):
        adapter = OfflineBillingAdapter()
        self.assertEqual(adapter.observe(observation()).status, "APPLIED")
        result = adapter.observe(observation())
        self.assertEqual(result.status, "REPLAY")
        self.assertTrue(result.replayed)

    def test_same_call_same_payload_across_runs_is_mirror(self):
        adapter = OfflineBillingAdapter()
        adapter.observe(observation(observation_id="obs-a", run_id="run-a"))
        result = adapter.observe(observation(observation_id="obs-b", run_id="run-b"))
        self.assertEqual(result.status, "MIRROR")
        self.assertEqual(len(adapter.observations), 2)

    def test_same_call_with_run_local_evidence_is_mirror(self):
        adapter = OfflineBillingAdapter()
        first = observation(observation_id="obs-a", run_id="run-a")
        second = ProviderCallObservation(
            "obs-b", identity(run_id="run-b"), "complete",
            {"input_tokens": 4, "output_tokens": 8}, "USD", 12,
            "run-b-evidence",
        )
        self.assertNotEqual(first.payload_hash, second.payload_hash)
        self.assertEqual(first.call_payload_hash, second.call_payload_hash)
        adapter.observe(first)
        result = adapter.observe(second)
        self.assertEqual(result.status, "MIRROR")
        self.assertTrue(result.historical)

    def test_same_call_different_payload_is_conflict(self):
        adapter = OfflineBillingAdapter()
        adapter.observe(observation())
        with self.assertRaises(EconomicsError) as ctx:
            adapter.observe(observation(observation_id="obs-b", amount=13, run_id="run-b"))
        self.assertEqual(ctx.exception.code, "E_CALL_CONFLICT")

    def test_observation_id_different_payload_is_conflict(self):
        adapter = OfflineBillingAdapter()
        adapter.observe(observation())
        with self.assertRaises(EconomicsError) as ctx:
            adapter.observe(observation(observation_id="obs-a", amount=13))
        self.assertEqual(ctx.exception.code, "E_OBSERVATION_CONFLICT")

    def test_same_observation_fingerprint_includes_evidence_reference(self):
        adapter = OfflineBillingAdapter()
        adapter.observe(observation())
        with self.assertRaises(EconomicsError) as ctx:
            adapter.observe(ProviderCallObservation(
                "obs-a", identity(), "complete", {"input_tokens": 4, "output_tokens": 8},
                "USD", 12, "different-evidence"
            ))
        self.assertEqual(ctx.exception.code, "E_OBSERVATION_CONFLICT")

    def test_coverage_is_unknown_then_partial_then_complete(self):
        adapter = OfflineBillingAdapter()
        adapter.observe(observation(visibility="partial"))
        self.assertEqual(adapter.coverage(), "partial")
        adapter.observe(observation(observation_id="obs-b", run_id="run-b", call_id="call-b",
                                    visibility="unknown"))
        self.assertEqual(adapter.coverage(), "unknown")


if __name__ == "__main__":
    unittest.main()
