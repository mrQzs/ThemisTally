#!/usr/bin/env python3
"""07-T3B pure finite retry and stop gates."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.retry import (  # noqa: E402
    EXHAUSTED, NO_RETRY, RETRY_ALLOWED, STOP, WAIT, AttemptFact,
    RetryContext, RetryError, RetryPolicy, backoff, cumulative_attempts,
    decide,
)


class RetryTests(unittest.TestCase):
    def policy(self, **changes: object) -> RetryPolicy:
        values: dict[str, object] = {
            "max_attempts_total": 3, "min_backoff_seconds": 2,
            "retryable_codes": ("TRANSIENT",), "valid_until_seq": 20,
        }
        values.update(changes)
        return RetryPolicy(**values)  # type: ignore[arg-type]

    def fact(self, **changes: object) -> AttemptFact:
        values: dict[str, object] = {
            "task": "task-a", "request": "req-a", "plan": 1, "attempt": 1,
            "operation": "op-a", "state": "FAILED", "code": "TRANSIENT",
            "retryable": True, "side_effects": False, "guard": True, "sequence": 10,
        }
        values.update(changes)
        return AttemptFact(**values)  # type: ignore[arg-type]

    def context(self, **changes: object) -> RetryContext:
        values: dict[str, object] = {
            "request_open": True, "stop_requested": False, "budget_available": True,
            "resources_available": True, "recovery_clear": True, "upstream_accepted": True,
            "authorization": True, "total_attempts": 1, "sequence": 12,
        }
        values.update(changes)
        return RetryContext(**values)  # type: ignore[arg-type]

    def test_policy_and_fact_types_are_strict(self) -> None:
        for kwargs in (
            {"max_attempts_total": True}, {"min_backoff_seconds": -1},
            {"retryable_codes": ["x", "x"]}, {"valid_until_seq": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(RetryError):
                self.policy(**kwargs)
        for kwargs in ({"attempt": True}, {"side_effects": 1}, {"state": "BOGUS"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(RetryError):
                self.fact(**kwargs)

    def test_backoff_is_exact_integer_and_capped(self) -> None:
        policy = self.policy(min_backoff_seconds=3)
        self.assertEqual((backoff(policy, 1), backoff(policy, 3)), (3, 12))
        self.assertLessEqual(backoff(policy, 2**53 - 1), 2**53 - 1)
        with self.assertRaises(RetryError):
            backoff(policy, True)

    def test_cumulative_attempts_crosses_plan_versions_and_deduplicates_operation(self) -> None:
        facts = [self.fact(plan=1, operation="op-a"), self.fact(plan=2, operation="op-b"),
                 self.fact(plan=2, operation="op-b", attempt=3)]
        self.assertEqual(cumulative_attempts(facts, request="req-a", task="task-a"), 2)
        self.assertEqual(cumulative_attempts(facts, request="req-other", task="task-a"), 0)

    def test_valid_retry_requires_explicit_model_authorization_and_current_gates(self) -> None:
        result = decide(self.policy(), self.fact(), self.context())
        self.assertEqual(result.status, RETRY_ALLOWED)
        self.assertEqual(result.next_attempt, 2)

    def test_retryable_flag_alone_does_not_authorize_unknown_or_unlisted_code(self) -> None:
        for changes in ({"code": "OTHER"}, {"retryable": None}, {"code": None}):
            result = decide(self.policy(), self.fact(**changes), self.context())
            expected = WAIT if "retryable" in changes else NO_RETRY
            self.assertEqual(result.status, expected)

    def test_active_accepted_and_side_effects_states_are_not_retried(self) -> None:
        for changes in ({"state": "REVIEW_PENDING"}, {"state": "ACCEPTED"}, {"side_effects": True}):
            result = decide(self.policy(), self.fact(**changes), self.context())
            self.assertEqual(result.status, NO_RETRY)

    def test_start_unknown_and_recovery_unknown_are_stop(self) -> None:
        for changes in ({"state": "START_UNKNOWN"}, {"state": "FAILED"}):
            ctx = self.context(recovery_clear=None) if changes["state"] != "START_UNKNOWN" else self.context()
            result = decide(self.policy(), self.fact(**changes), ctx)
            self.assertEqual(result.status, STOP)
        result = decide(self.policy(), self.fact(), self.context(budget_available=None))
        self.assertEqual(result.status, WAIT)

    def test_stop_request_has_priority_over_a_valid_retry(self) -> None:
        for changes in ({"stop_requested": True}, {"request_open": False}):
            result = decide(self.policy(), self.fact(), self.context(**changes))
            self.assertEqual(result.status, STOP)
            self.assertIn("request_stopped", result.reasons)

    def test_budget_resource_upstream_and_authorization_are_rechecked(self) -> None:
        for field in ("budget_available", "resources_available", "upstream_accepted"):
            result = decide(self.policy(), self.fact(), self.context(**{field: False}))
            self.assertEqual(result.status, WAIT)
        result = decide(self.policy(), self.fact(), self.context(authorization=False))
        self.assertEqual(result.status, NO_RETRY)

    def test_backoff_waits_until_current_sequence_is_due(self) -> None:
        early = decide(self.policy(), self.fact(sequence=10, attempt=2), self.context(sequence=12))
        self.assertEqual((early.status, early.retry_after_seq), (WAIT, 14))
        due = decide(self.policy(), self.fact(sequence=10, attempt=2), self.context(sequence=14))
        self.assertEqual(due.status, RETRY_ALLOWED)

    def test_attempt_limit_is_cumulative_and_exhausted(self) -> None:
        history = [self.fact(operation="op-a"), self.fact(operation="op-b", plan=2)]
        result = decide(self.policy(max_attempts_total=2), self.fact(operation="op-c", attempt=3),
                        self.context(total_attempts=2, sequence=20), history)
        self.assertEqual(result.status, EXHAUSTED)
        self.assertIn("attempt_limit", result.reasons)

    def test_request_dispatch_cap_is_independent_from_task_attempt_cap(self) -> None:
        result = decide(self.policy(max_request_dispatches=2), self.fact(),
                        self.context(total_attempts=1, total_dispatches=2))
        self.assertEqual(result.status, EXHAUSTED)
        self.assertIn("request_dispatch_limit", result.reasons)
        result = decide(self.policy(max_request_dispatches=3), self.fact(),
                        self.context(total_attempts=1, total_dispatches=2))
        self.assertEqual(result.status, RETRY_ALLOWED)

    def test_stale_attempt_count_waits_instead_of_underestimating(self) -> None:
        history = [self.fact(operation="op-a"), self.fact(operation="op-b", plan=2)]
        result = decide(self.policy(), self.fact(), self.context(total_attempts=1), history)
        self.assertEqual(result.status, WAIT)
        self.assertIn("attempt_count_stale", result.reasons)

    def test_expired_policy_and_guard_or_nonretryable_failure_stop_new_retry(self) -> None:
        result = decide(self.policy(valid_until_seq=5), self.fact(), self.context(sequence=6))
        self.assertEqual(result.status, NO_RETRY)
        result = decide(self.policy(), self.fact(guard=False), self.context())
        self.assertEqual(result.status, NO_RETRY)
        result = decide(self.policy(), self.fact(retryable=False), self.context())
        self.assertEqual(result.status, NO_RETRY)

    def test_contract_or_input_failures_are_new_plan_not_retryable(self) -> None:
        for code in ("CONTRACT_INVALID", "BASELINE_INVALID", "SCOPE_INVALID"):
            result = decide(self.policy(retryable_codes=(code,)), self.fact(code=code), self.context())
            self.assertIn(result.status, (NO_RETRY, STOP))

    def test_model_does_not_change_cli_or_tools(self) -> None:
        result = decide(self.policy(), self.fact(), self.context())
        self.assertFalse(hasattr(result, "model"))
        self.assertFalse(hasattr(result, "cli"))
        self.assertFalse(hasattr(result, "tools"))

    def test_unknown_context_fails_closed_and_reasons_are_deterministic(self) -> None:
        result = decide(self.policy(), self.fact(), RetryContext())
        self.assertEqual(result.status, STOP)
        self.assertEqual(result.reasons, tuple(dict.fromkeys(result.reasons)))
        self.assertEqual(result.reasons[:2], ("recovery_state_unknown", "stop_state_unknown"))

    def test_policy_sequence_alias_conflict_and_bool_inputs_reject(self) -> None:
        with self.assertRaises(RetryError):
            RetryContext(sequence=1, now=2)
        with self.assertRaises(RetryError):
            RetryContext(total_attempts=True)
        with self.assertRaises(RetryError):
            RetryContext(total_dispatches=True)

    def test_retry_outputs_stay_within_safe_integer_range(self) -> None:
        maximum = 2**53 - 1
        exhausted = decide(
            self.policy(max_attempts_total=maximum, min_backoff_seconds=0,
                        valid_until_seq=maximum),
            self.fact(sequence=maximum),
            self.context(total_attempts=maximum, sequence=maximum),
        )
        self.assertEqual(exhausted.status, EXHAUSTED)
        self.assertEqual(exhausted.next_attempt, maximum)

        overflow = decide(
            self.policy(min_backoff_seconds=2, valid_until_seq=maximum),
            self.fact(sequence=maximum),
            self.context(sequence=maximum),
        )
        self.assertEqual(overflow.status, WAIT)
        self.assertIn("sequence_limit_reached", overflow.reasons)
        self.assertEqual(overflow.retry_after_seq, maximum)

    def test_triggering_fact_counts_toward_next_attempt_when_context_is_stale(self) -> None:
        result = decide(self.policy(), self.fact(), self.context(total_attempts=0))
        self.assertEqual((result.status, result.next_attempt), (WAIT, 2))
        self.assertIn("attempt_count_stale", result.reasons)


if __name__ == "__main__":
    unittest.main()
