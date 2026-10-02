"""Offline invoice and allocation facts."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.provider_economics import (  # noqa: E402
    AllocationEntry,
    EconomicsError,
    InvoiceLine,
    OfflineBillingAdapter,
)
def observation(*, observation_id="obs-a", run_id="run-a", call_id="call-a", amount=12):
    from codekit.provider_economics import EconomicCallIdentity, ProviderCallObservation
    identity = EconomicCallIdentity(call_id, "offline", "fixture-v1", "acct-a", "fixture",
                                    request_id="request-a", task_id="task-a", run_id=run_id)
    return ProviderCallObservation(observation_id, identity, "complete",
                                   {"input_tokens": 4, "output_tokens": 8}, "USD", amount,
                                   "fixture-evidence")


def setup_adapter():
    adapter = OfflineBillingAdapter()
    adapter.observe(observation())
    adapter.observe(observation(observation_id="obs-b", run_id="run-b", call_id="call-b"))
    adapter.add_invoice_line(InvoiceLine("invoice-a", "line-a", "acct-a", "fixture", "USD", 12))
    return adapter


def entry(*, entry_id="alloc-a", amount=12, call_key=None, call_id="call-a", currency="USD",
          account="acct-a", source="fixture"):
    return AllocationEntry(entry_id, "invoice-a", "line-a", call_key or observation(call_id=call_id).call_key,
                           currency, amount, account, source)


class OfflineProviderTests(unittest.TestCase):
    def test_invoice_line_replay_and_conflict(self):
        adapter = OfflineBillingAdapter()
        line = InvoiceLine("invoice-a", "line-a", "acct-a", "fixture", "USD", 12)
        self.assertEqual(adapter.add_invoice_line(line).status, "APPLIED")
        self.assertTrue(adapter.add_invoice_line(line).replayed)
        with self.assertRaises(EconomicsError) as ctx:
            adapter.add_invoice_line(InvoiceLine("invoice-a", "line-a", "acct-a", "fixture", "USD", 13))
        self.assertEqual(ctx.exception.code, "E_INVOICE_CONFLICT")

    def test_allocation_requires_observed_call_and_invoice(self):
        adapter = OfflineBillingAdapter()
        with self.assertRaises(EconomicsError) as ctx:
            adapter.allocate(entry())
        self.assertEqual(ctx.exception.code, "E_INVOICE_UNKNOWN")
        adapter.add_invoice_line(InvoiceLine("invoice-a", "line-a", "acct-a", "fixture", "USD", 12))
        with self.assertRaises(EconomicsError) as ctx:
            adapter.allocate(entry(call_key="missing-call"))
        self.assertEqual(ctx.exception.code, "E_CALL_UNKNOWN")

    def test_allocation_sum_and_replay(self):
        adapter = setup_adapter()
        self.assertEqual(adapter.allocate(entry(amount=7)).status, "APPLIED")
        self.assertEqual(adapter.allocate(entry(entry_id="alloc-b", amount=5, call_id="call-b")).status, "APPLIED")
        self.assertEqual(adapter.allocated_total("invoice-a", "line-a"), 12)
        self.assertEqual(adapter.unallocated("invoice-a", "line-a"), 0)
        self.assertTrue(adapter.allocation_complete("invoice-a", "line-a"))
        self.assertTrue(adapter.allocate(entry(amount=7)).replayed)

    def test_allocation_cannot_exceed_line(self):
        adapter = setup_adapter()
        adapter.allocate(entry(amount=10))
        with self.assertRaises(EconomicsError) as ctx:
            adapter.allocate(entry(entry_id="alloc-b", amount=3, call_id="call-b"))
        self.assertEqual(ctx.exception.code, "E_ALLOCATION_EXCEEDS_LINE")

    def test_allocation_scope_isolated_by_currency_account_and_source(self):
        adapter = setup_adapter()
        for kwargs in ({"currency": "JPY"}, {"account": "acct-b"}, {"source": "other"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(EconomicsError) as ctx:
                adapter.allocate(entry(entry_id="alloc-" + next(iter(kwargs)), **kwargs))
            self.assertEqual(ctx.exception.code, "E_ALLOCATION_SCOPE")

    def test_same_target_different_amount_conflicts(self):
        adapter = setup_adapter()
        adapter.allocate(entry(amount=7))
        with self.assertRaises(EconomicsError) as ctx:
            adapter.allocate(entry(entry_id="alloc-b", amount=8))
        self.assertEqual(ctx.exception.code, "E_ALLOCATION_CONFLICT")


if __name__ == "__main__":
    unittest.main()
