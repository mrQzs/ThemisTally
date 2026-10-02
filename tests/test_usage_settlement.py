"""07-S3.2 offline settlement facts and conservative accounting boundaries."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.protocols import MAX_SAFE_INTEGER
from codekit.usage_settlement import (SettlementError, SettlementFact, SettlementPolicy,
                                       UsageSettlement, _canonical)


class UsageSettlementTests(unittest.TestCase):
    def policy(self, *, refund_policy: str = "record_only") -> SettlementPolicy:
        return SettlementPolicy({"tokens": 10, "charge:USD": 100, "charge:JPY": 1000},
                                refund_policy=refund_policy)

    def ledger(self, *, refund_policy: str = "record_only") -> UsageSettlement:
        return UsageSettlement(self.policy(refund_policy=refund_policy))

    def reserve(self, ledger: UsageSettlement, operation: str = "op-a", amount: int = 5) -> None:
        ledger.reserve(operation, "req-a", "task-a",
                       {"tokens": amount, "charge:USD": amount, "charge:JPY": 0})

    def fact(self, *, fact_id: str = "fact-a", operation_id: str = "op-a",
             dimension: str = "tokens", call_key: str = "call-a", revision: int = 1,
             kind: str = "cumulative", amount: int | None = 2, currency: str | None = None,
             correction: bool = False, supersedes: str | None = None,
             refund_for: str | None = None, unknown_reason: str | None = None,
             evidence_ref: str | None = "evidence-a") -> SettlementFact:
        if dimension.startswith("charge:") and currency is None:
            currency = dimension.split(":", 1)[1]
        return SettlementFact(fact_id, operation_id, dimension, call_key, revision, kind,
                              amount, currency, correction, supersedes, refund_for,
                              unknown_reason, evidence_ref)

    def test_cumulative_mirror_final_and_audit_history(self) -> None:
        ledger = self.ledger()
        self.reserve(ledger, amount=10)
        self.assertEqual(ledger.record(self.fact(amount=3)).status, "APPLIED")
        mirror = ledger.record(self.fact(fact_id="mirror", amount=3, evidence_ref="evidence-b"))
        self.assertEqual((mirror.status, mirror.replayed, mirror.historical), ("MIRROR", False, True))
        self.assertEqual(ledger.record(self.fact(fact_id="final", kind="final", revision=2, amount=5)).status, "APPLIED")
        current = ledger.snapshot().dimensions["tokens"]
        self.assertEqual((current.gross_known, current.known, current.held, current.exposure), (5, 5, 0, 5))
        self.assertEqual(ledger.operations[0].state, "provisional")
        self.assertEqual(len(ledger.facts), 3)
        exported = ledger.audit_record()
        self.assertEqual(exported["facts"][0]["fact_id"], "fact-a")
        self.assertTrue(ledger.audit_fingerprint())

    def test_out_of_order_revision_and_correction_replace_current(self) -> None:
        ledger = self.ledger()
        self.reserve(ledger)
        ledger.record(self.fact(fact_id="r3", revision=3, amount=8))
        historical = ledger.record(self.fact(fact_id="r1", revision=1, amount=2))
        self.assertEqual((historical.status, historical.historical), ("HISTORICAL_ONLY", True))
        self.assertEqual(ledger.snapshot().dimensions["tokens"].known, 8)
        corrected = ledger.record(self.fact(fact_id="r4", revision=4, amount=6,
                                            correction=True, supersedes="r3"))
        self.assertEqual(corrected.status, "APPLIED")
        self.assertEqual(ledger.snapshot().dimensions["tokens"].known, 6)
        self.assertEqual(sum((fact.amount or 0) for fact in ledger.facts if fact.kind != "unknown"), 16)

    def test_decrease_or_post_final_requires_current_correction(self) -> None:
        ledger = self.ledger()
        self.reserve(ledger)
        ledger.record(self.fact(amount=6))
        with self.assertRaisesRegex(SettlementError, "correction"):
            ledger.record(self.fact(fact_id="bad", revision=2, amount=5))
        ledger.record(self.fact(fact_id="r2", revision=2, amount=5, correction=True, supersedes="fact-a"))
        ledger.record(self.fact(fact_id="final", revision=3, kind="final", amount=5))
        with self.assertRaises(SettlementError):
            ledger.record(self.fact(fact_id="bad-final", revision=4, kind="final", amount=7))
        ledger.record(self.fact(fact_id="fixed-final", revision=4, kind="final", amount=7,
                                correction=True, supersedes="final"))
        self.assertEqual(ledger.snapshot().dimensions["tokens"].known, 7)

    def test_unknown_keeps_exposure_and_blocks_new_admission(self) -> None:
        ledger = self.ledger()
        self.reserve(ledger, amount=5)
        ledger.record(self.fact(kind="unknown", amount=None, unknown_reason="provider-timeout"))
        self.assertEqual(ledger.operations[0].state, "unknown")
        current = ledger.snapshot().dimensions["tokens"]
        self.assertEqual((current.known, current.held, current.exposure), (0, 5, 5))
        self.assertEqual((current.coverage, current.unknown_operations, current.enforcement),
                         ("unknown", ("op-a",), "stop"))
        with self.assertRaises(SettlementError):
            ledger.reserve("op-b", "req-a", "task-b", {"tokens": 1, "charge:USD": 1, "charge:JPY": 0})
        # A late final closes the series but does not erase the durable stop reason.
        ledger.record(self.fact(fact_id="final", revision=2, kind="final", amount=3))
        self.assertEqual(ledger.snapshot().dimensions["tokens"].unknown_operations, ())
        self.assertEqual(ledger.operations[0].state, "provisional")
        self.assertIn("USAGE_UNKNOWN", ledger.stop_reasons)

    def test_actual_usage_over_cap_is_accepted_and_stops(self) -> None:
        ledger = self.ledger()
        self.reserve(ledger, amount=5)
        ledger.record(self.fact(kind="final", amount=12))
        current = ledger.snapshot().dimensions["tokens"]
        self.assertEqual((current.known, current.exposure, current.over_limit), (12, 12, True))
        self.assertIn("BUDGET_EXCEEDED", ledger.stop_reasons)
        with self.assertRaises(SettlementError):
            self.reserve(ledger, "op-b", 1)

    def test_refund_is_separate_fact_and_policy_controls_release(self) -> None:
        for refund_policy, expected_known in (("record_only", 8), ("release", 5)):
            with self.subTest(refund_policy=refund_policy):
                ledger = self.ledger(refund_policy=refund_policy)
                self.reserve(ledger, amount=8)
                ledger.record(self.fact(kind="final", amount=8))
                refund = self.fact(fact_id="refund", dimension="charge:USD", call_key="refund-event",
                                   kind="refund", amount=3, refund_for="call-a")
                # The target is a token call, so a refund in a separate charge
                # dimension must name a charge call; this is rejected before mutation.
                with self.assertRaises(SettlementError):
                    ledger.record(refund)
                ledger.record(self.fact(fact_id="charge-final", dimension="charge:USD", call_key="charge-a",
                                        kind="final", amount=8, revision=1))
                refund = self.fact(fact_id="refund", dimension="charge:USD", call_key="refund-event",
                                   kind="refund", amount=3, refund_for="charge-a")
                self.assertEqual(ledger.record(refund).status, "APPLIED")
                replay = ledger.record(refund)
                self.assertTrue(replay.replayed)
                current = ledger.snapshot().dimensions["charge:USD"]
                self.assertEqual((current.gross_known, current.refunds, current.net_known, current.known),
                                 (8, 3, 5, expected_known))
                self.assertEqual(current.refund_excess, 0)

    def test_currency_dimensions_are_isolated_without_exchange(self) -> None:
        ledger = self.ledger()
        self.reserve(ledger, amount=4)
        ledger.record(self.fact(fact_id="usd", dimension="charge:USD", call_key="usd", kind="final", amount=7))
        ledger.record(self.fact(fact_id="jpy", dimension="charge:JPY", call_key="jpy", kind="final", amount=700,
                                currency="JPY"))
        self.assertEqual(ledger.snapshot().dimensions["charge:USD"].known, 7)
        self.assertEqual(ledger.snapshot().dimensions["charge:JPY"].known, 700)
        with self.assertRaises(SettlementError):
            self.fact(dimension="charge:USD", currency="JPY")

    def test_unknown_refund_target_cross_operation_and_integer_rejection(self) -> None:
        ledger = self.ledger()
        self.reserve(ledger)
        with self.assertRaises(SettlementError):
            ledger.record(self.fact(fact_id="refund", kind="refund", amount=1,
                                    call_key="refund", refund_for="missing"))
        ledger.record(self.fact(kind="final", amount=2))
        self.reserve(ledger, operation="op-b", amount=1)
        with self.assertRaises(SettlementError):
            ledger.record(self.fact(fact_id="cross", operation_id="op-b", call_key="call-a",
                                    kind="final", amount=2))
        for amount in (True, -1, 1.5, MAX_SAFE_INTEGER + 1):
            with self.subTest(amount=amount), self.assertRaises(SettlementError):
                self.fact(amount=amount)  # type: ignore[arg-type]

    def test_fact_policy_and_currency_types_fail_as_settlement_errors(self) -> None:
        with self.assertRaises(SettlementError):
            SettlementPolicy({"tokens": 1}, unknown_policy=[] )  # type: ignore[arg-type]
        with self.assertRaises(SettlementError):
            SettlementPolicy({"charge:usd": 1})
        with self.assertRaises(SettlementError):
            self.fact(kind=[])  # type: ignore[arg-type]
        with self.assertRaises(SettlementError):
            self.fact(dimension="charge:usd", currency="usd")
        with self.assertRaises(SettlementError):
            self.fact(dimension="charge:USD", currency=[])  # type: ignore[arg-type]

    def test_refund_cannot_target_an_unknown_call(self) -> None:
        ledger = self.ledger()
        self.reserve(ledger)
        ledger.record(self.fact(kind="unknown", amount=None, unknown_reason="provider-timeout"))
        with self.assertRaisesRegex(SettlementError, "target"):
            ledger.record(self.fact(fact_id="refund", kind="refund", amount=1,
                                    call_key="refund", refund_for="call-a"))

    def test_audit_fingerprint_is_deterministic_for_same_fixture(self) -> None:
        def build() -> UsageSettlement:
            ledger = self.ledger()
            self.reserve(ledger, amount=3)
            ledger.record(self.fact(amount=2))
            ledger.record(self.fact(fact_id="final", kind="final", revision=2, amount=3))
            return ledger
        self.assertEqual(build().audit_fingerprint(), build().audit_fingerprint())
        self.assertEqual(build().audit_record(), build().audit_record())

    def test_canonical_rejects_cycles_unsafe_values_and_unknown_objects(self) -> None:
        value = {}
        value["self"] = value
        for payload in (value, {"value": 2**53}, {"value": float("nan")},
                        {"value": "\ud800"}, {"\ud800": "surrogate-key"},
                        {1: "integer-key"}, {"value": object()}):
            with self.subTest(payload=payload if payload is not value else "cycle"), self.assertRaises(SettlementError):
                _canonical(payload)

    def test_canonical_distinguishes_boolean_and_integer(self) -> None:
        self.assertNotEqual(_canonical({"value": True}), _canonical({"value": 1}))


if __name__ == "__main__":
    unittest.main()
