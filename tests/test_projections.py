from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from codekit.projections import (OutboxProjection, ProjectionError, ProjectionEvent,
                                 event_identity, project_readiness, project_state, render_brief)


FACTS = {name: True for name in (
    "inputs_accepted", "baseline_present", "baseline_authorized", "planner_authorized",
    "planner_environment_ok", "planner_budget_ok", "input_locks_ok", "request_open",
    "contract_current", "approval_current", "capabilities_ok", "execution_authorized",
    "budget_ok", "conflicts_clear")}


class ProjectionTests(unittest.TestCase):
    def test_readiness_keeps_three_authority_levels_separate(self):
        result = project_readiness({**FACTS, "planner_authorized": None, "execution_authorized": None})
        self.assertTrue(result.can_refine)
        self.assertFalse(result.can_start_planner)
        self.assertFalse(result.can_execute)
        self.assertIn("WAIT_PLANNER_PLANNER_AUTHORIZED", result.reasons)

    def test_unknown_and_missing_facts_do_not_become_false_or_complete(self):
        result = project_readiness({**FACTS, "baseline_authorized": None})
        self.assertFalse(result.can_refine)
        self.assertIn("WAIT_REFINE_BASELINE_AUTHORIZED", result.reasons)
        with self.assertRaises(ProjectionError):
            project_readiness({**FACTS, "extra": True})

    def test_event_identity_and_atomic_consumer(self):
        first = ProjectionEvent(1, "ledger", "usage", {"units": 2})
        event_id, _ = event_identity(first.source_key, first.event_type, first.payload)
        self.assertEqual(OutboxProjection().consume_batch([first], generation=1), "APPLIED")
        consumer = OutboxProjection()
        self.assertEqual(consumer.consume_batch([ProjectionEvent(1, "ledger", "usage", {"units": 2}, event_id)], generation=1), "APPLIED")
        self.assertEqual(consumer.consume_batch([ProjectionEvent(1, "ledger", "usage", {"units": 2}, event_id)], generation=1), "REPLAY")
        with self.assertRaises(ProjectionError) as caught:
            consumer.consume_batch([ProjectionEvent(1, "ledger", "usage", {"units": 3}, event_id)], generation=1)
        self.assertEqual(caught.exception.code, "E_EVENT_ID")
        with self.assertRaises(ProjectionError) as caught:
            event_identity("ledger", "usage", [])
        self.assertEqual(caught.exception.code, "E_EVENT_PAYLOAD")

    def test_consumer_requires_contiguous_sequences_and_generation(self):
        consumer = OutboxProjection(generation=2)
        with self.assertRaises(ProjectionError) as caught:
            consumer.consume_batch(None, generation=2)
        self.assertEqual(caught.exception.code, "E_EVENT")
        with self.assertRaises(ProjectionError) as caught:
            consumer.consume_batch([ProjectionEvent(2, "ledger", "usage", {})], generation=2)
        self.assertEqual(caught.exception.code, "E_EVENT_GAP")
        with self.assertRaises(ProjectionError) as caught:
            consumer.consume_batch([], generation=1)
        self.assertEqual(caught.exception.code, "E_FENCED")

    def test_event_identity_rejects_coercive_or_unsafe_payloads(self):
        with self.assertRaises(ProjectionError) as caught:
            event_identity("ledger", "usage", {1: "coerced-key"})
        self.assertEqual(caught.exception.code, "E_EVENT_PAYLOAD")
        with self.assertRaises(ProjectionError) as caught:
            event_identity("ledger", "usage", {"units": 2 ** 53})
        self.assertEqual(caught.exception.code, "E_EVENT_PAYLOAD")
        with self.assertRaises(ProjectionError) as caught:
            event_identity("ledger\n", "usage", {})
        self.assertEqual(caught.exception.code, "E_EVENT_ID")

    def test_rebuild_rejects_coercive_rows(self):
        consumer = OutboxProjection()
        with self.assertRaises(ProjectionError) as caught:
            consumer.rebuild_from_authority([{1: "coerced-key"}], generation=1)
        self.assertEqual(caught.exception.code, "E_REBUILD")

    def test_rebuild_and_brief_preserve_unknown_budget_and_truncation(self):
        consumer = OutboxProjection()
        consumer.consume_batch([ProjectionEvent(1, "ledger", "fact", {"ok": True})], generation=1)
        consumer.rebuild_from_authority([{"id": "row-a"}], generation=1)
        self.assertEqual(consumer.indexed_cursor, 0)
        state = project_state(indexed_cursor=0, applied_cursor=0, source_vector={}, verification_ref="v1",
                              as_of="2026-10-02T00:00:00Z", source_coverage="partial", issues=["source_gap"],
                              budget_coverage="unknown", truncated=True)
        brief = render_brief(state)
        self.assertEqual(brief["budget"], "[未知] 无可核验预算快照")
        self.assertEqual(brief["dispatch_eligibility"], "not_evaluated")
        self.assertTrue(brief["truncated"])

    def test_state_and_brief_reject_untyped_projection_fields(self):
        common = dict(indexed_cursor=0, applied_cursor=0, source_vector={}, verification_ref="v1",
                      as_of="2026-10-02T00:00:00Z", source_coverage="complete", issues=[], budget_coverage="complete")
        with self.assertRaises(ProjectionError) as caught:
            project_state(**{**common, "indexed_cursor": "0"})
        self.assertEqual(caught.exception.code, "E_CURSOR")
        with self.assertRaises(ProjectionError) as caught:
            project_state(**{**common, "source_vector": {"ledger": "0"}})
        self.assertEqual(caught.exception.code, "E_SOURCE_VECTOR")
        with self.assertRaises(ProjectionError) as caught:
            project_state(**{**common, "issues": "source_gap"})
        self.assertEqual(caught.exception.code, "E_ISSUES")
        with self.assertRaises(ProjectionError) as caught:
            render_brief({"health": 1})
        self.assertEqual(caught.exception.code, "E_STATE")
        with self.assertRaises(ProjectionError) as caught:
            render_brief({"health": "degraded", "issues": None})
        self.assertEqual(caught.exception.code, "E_ISSUES")
        with self.assertRaises(ProjectionError) as caught:
            project_state(**{**common, "source_coverage": []})
        self.assertEqual(caught.exception.code, "E_COVERAGE")
        with self.assertRaises(ProjectionError) as caught:
            render_brief({"health": [], "source_coverage": "complete", "issues": []})
        self.assertEqual(caught.exception.code, "E_STATE")


if __name__ == "__main__":
    unittest.main()
