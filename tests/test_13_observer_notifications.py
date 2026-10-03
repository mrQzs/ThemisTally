"""Offline tests for the optional host notification boundary."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.project_delivery import (  # noqa: E402
    DeliveryError,
    evaluate_release_gate,
    request_pull_delivery,
)
from codekit.project_views import ViewPackageStore, make_read_receipt, render_project_brief  # noqa: E402
from codekit.read_receipts import ReadReceiptStore  # noqa: E402


STATE = {
    "indexed_cursor": 1,
    "applied_cursor": 1,
    "source_coverage": "complete",
    "budget_coverage": "complete",
    "verification_ref": "verify-13",
    "as_of": "2026-10-04T00:00:00Z",
    "tasks": {},
    "decisions": {},
    "budgets": {},
    "issues": [],
    "dispatch_eligibility": "not_evaluated",
}


class ObserverNotificationTests(unittest.TestCase):
    def test_no_host_is_pull_only_and_never_claims_delivery_or_read(self) -> None:
        receipt = request_pull_delivery("a" * 64, observer_ref="observer-13")
        self.assertEqual(receipt.status, "NOT_RUN")
        self.assertIn("host delivery adapter", receipt.reason)
        mapping = receipt.to_mapping()
        self.assertNotIn("read_receipt", mapping)
        self.assertNotIn("delivered_at", mapping)
        with self.assertRaisesRegex(DeliveryError, "pull delivery"):
            request_pull_delivery("a" * 64, observer_ref="observer-13", mode="push")

    def test_delivery_and_read_receipt_are_independent_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            view_store = ViewPackageStore(root / "views")
            manifest = view_store.publish(STATE, render_project_brief(STATE), generation=1, cursor=1)
            read = make_read_receipt(manifest, observer_ref="observer-13", read_cursor=1)
            read_store = ReadReceiptStore(root / "read-receipts.jsonl")
            self.assertFalse(read_store.append(read).replayed)

            delivery = request_pull_delivery(manifest.view_id, observer_ref="observer-13")
            self.assertNotEqual(delivery.delivery_id, read.receipt_id)
            self.assertEqual(delivery.view_id, read.view_id)
            self.assertEqual(delivery.status, "NOT_RUN")
            self.assertTrue((root / "views" / "views" / manifest.view_id / "brief.md").exists())
            self.assertEqual(json.loads((root / "read-receipts.jsonl").read_text(encoding="utf-8"))["receipt_id"], read.receipt_id)

    def test_blocked_host_does_not_promote_offline_release_gate(self) -> None:
        gate = evaluate_release_gate(
            {"S5": "ACCEPTED_WITH_EXCEPTION"},
            real_capabilities={"host_delivery": "blocked", "provider": "not_run"},
        )
        self.assertEqual(gate["status"], "BLOCKED")
        self.assertFalse(gate["production_release"])
        self.assertTrue(any(reason.startswith("capability:") for reason in gate["reasons"]))

    def test_pull_receipt_is_deterministic_for_retries(self) -> None:
        first = request_pull_delivery("b" * 64, observer_ref="observer-13")
        retry = request_pull_delivery("b" * 64, observer_ref="observer-13")
        self.assertEqual(first, retry)


if __name__ == "__main__":
    unittest.main()
