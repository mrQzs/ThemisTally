"""07-T3A: one trusted cumulative usage sequence per operation/dimension."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.budget import (BudgetError, BudgetPolicy, BudgetState, UsageObservation,
                            project_budget, stable_observation_fingerprint)
from codekit.protocols import MAX_SAFE_INTEGER


class BudgetTests(unittest.TestCase):
    def state(self, limit=10, task_cap=None):
        tasks = {} if task_cap is None else {"task-a": {"tokens": task_cap}}
        return BudgetState(BudgetPolicy({"tokens": limit}, tasks))

    def reserve(self, state=None, op="op-a", amount=5, task="task-a", **kwargs):
        return (state or self.state()).reserve_for_operation(
            op, "req-a", task, {"tokens": amount}, **kwargs)[0]

    def obs(self, **kwargs):
        values = dict(observation_id="obs-a", operation_id="op-a", dimension="tokens",
                      kind="cumulative", amount=2, revision=1,
                      economic_call_key="call-a", evidence_ref="a" * 64)
        values.update(kwargs)
        if "kind" in kwargs:
            values["final"] = kwargs["kind"] == "final"
        if "final" in kwargs:
            values["final"] = kwargs["final"]
        return UsageObservation(**values)

    def view(self, state, dim="tokens"):
        return project_budget(state).dimensions[dim]

    def record(self, state, **kwargs):
        return state.record_usage_observation(self.obs(**kwargs))[0]

    def test_reservations_check_both_request_and_task_caps(self):
        state = self.reserve(self.state(task_cap=6), amount=6)
        with self.assertRaises(BudgetError):
            self.reserve(state, op="op-b", amount=5, task="task-b")
        with self.assertRaises(BudgetError):
            self.reserve(state, op="op-b", amount=1)
        state = self.reserve(state, op="op-b", amount=4, task="task-b")
        self.assertEqual(self.view(state).exposure, 10)

    def test_reservation_failure_is_all_or_nothing(self):
        state = BudgetState(BudgetPolicy({"tokens": 5, "charge:USD": 10}))
        with self.assertRaises(BudgetError):
            state.reserve_for_operation("op-a", "req-a", "task-a", {"tokens": 3, "charge:USD": 11})
        self.assertEqual(state.operations, ())
        self.assertEqual(state.sequence, 0)

    def test_each_monitored_dimension_requires_explicit_reservation(self):
        state = BudgetState(BudgetPolicy({"tokens": 5, "charge:USD": 10}))
        for vector in ({}, {"tokens": 1}, {"tokens": 1, "charge:USD": 1, "other": 1}):
            with self.subTest(vector=vector), self.assertRaises(BudgetError):
                state.reserve_for_operation("op-a", "req-a", "task-a", vector)

    def test_request_root_cannot_change(self):
        state = self.reserve()
        with self.assertRaises(BudgetError):
            state.reserve_for_operation("op-b", "req-b", "task-a", {"tokens": 1})

    def test_reserve_replay_after_usage_and_stop_does_not_reserve_again(self):
        state = self.record(self.reserve()).request_stop("MANUAL")
        replay, decision = state.reserve_for_operation("op-a", "req-a", "task-a", {"tokens": 5})
        self.assertIs(replay, state)
        self.assertTrue(decision.replayed)
        self.assertEqual(len(state.operations), 1)
        with self.assertRaises(BudgetError):
            state.reserve_for_operation("op-a", "req-a", "task-a", {"tokens": 4})

    def test_partial_usage_reduces_hold_without_doubling_exposure(self):
        original = self.reserve(amount=10)
        state = self.record(original, amount=3)
        self.assertEqual((self.view(state).known, self.view(state).held, self.view(state).exposure), (3, 7, 10))
        self.assertEqual((self.view(original).known, self.view(original).held), (0, 10))

    def test_final_replaces_cumulative_and_releases_unused_hold(self):
        state = self.record(self.reserve(amount=10), amount=3)
        state = self.record(state, observation_id="obs-b", kind="final", amount=5, revision=2)
        self.assertEqual((self.view(state).known, self.view(state).held), (5, 0))
        self.assertEqual(len(state.observations), 2)

    def test_final_is_dimension_local(self):
        state = BudgetState(BudgetPolicy({"tokens": 10, "charge:USD": 10}))
        state = state.reserve_for_operation("op-a", "req-a", "task-a", {"tokens": 5, "charge:USD": 7})[0]
        state = self.record(state, kind="final", amount=2)
        self.assertEqual(self.view(state).held, 0)
        self.assertEqual(self.view(state, "charge:USD").held, 7)
        state, _ = state.settle_operation("op-a")
        self.assertEqual(self.view(state).unknown_operations, ())
        self.assertEqual(self.view(state, "charge:USD").unknown_operations, ("op-a",))

    def test_settling_provisional_usage_preserves_unknown_risk(self):
        state = self.record(self.reserve(), amount=2)
        state, _ = state.settle_operation("op-a")
        snap = self.view(state)
        self.assertEqual((snap.known, snap.held, snap.unknown_operations), (2, 3, ("op-a",)))
        self.assertIn("USAGE_UNKNOWN", state.stop_reasons)
        replay, decision = state.settle_operation("op-a")
        self.assertIs(replay, state)
        self.assertTrue(decision.replayed)

    def test_missing_usage_at_end_and_zero_reserve_are_still_unknown(self):
        for amount in (0, 5):
            with self.subTest(amount=amount):
                state, _ = self.reserve(amount=amount).settle_operation("op-a")
                self.assertEqual(self.view(state).held, amount)
                self.assertEqual(self.view(state).unknown_operations, ("op-a",))
                self.assertIn("USAGE_UNKNOWN", state.stop_reasons)

    def test_explicit_unknown_retains_last_known_subtotal_and_hold(self):
        state = self.record(self.reserve(), amount=2)
        state = self.record(state, observation_id="obs-b", kind="unknown", amount=None,
                            revision=2, unknown_reason="provider-unavailable")
        self.assertEqual((self.view(state).known, self.view(state).held), (2, 3))
        self.assertEqual(self.view(state).unknown_operations, ("op-a",))
        self.assertIn("USAGE_UNKNOWN", state.stop_reasons)

    def test_unknown_on_one_sequence_is_not_cleared_by_another_operation(self):
        state = self.reserve(amount=3)
        state = self.reserve(state, op="op-b", amount=3, task="task-b")
        state = self.record(state, kind="unknown", amount=None, unknown_reason="missing")
        state = self.record(state, operation_id="op-b", observation_id="obs-b", economic_call_key="call-b",
                            kind="final", amount=1, revision=9)
        self.assertEqual(self.view(state).unknown_operations, ("op-a",))

    def test_late_final_closes_liability_without_automatically_resuming(self):
        state, _ = self.reserve().settle_operation("op-a")
        state = self.record(state, kind="final", amount=3)
        self.assertEqual((self.view(state).known, self.view(state).held, self.view(state).unknown_operations), (3, 0, ()))
        self.assertIn("USAGE_UNKNOWN", state.stop_reasons)
        with self.assertRaises(BudgetError):
            self.reserve(state, op="op-b", amount=1)

    def test_overrun_is_recorded_and_raw_remaining_can_be_negative(self):
        state = self.record(self.reserve(), amount=12)
        self.assertEqual((self.view(state).known, self.view(state).held, self.view(state).raw_remaining), (12, 0, -2))
        self.assertIn("BUDGET_EXCEEDED", state.stop_reasons)
        state = self.record(state, observation_id="obs-b", kind="final", amount=13, revision=2)
        self.assertEqual(self.view(state).known, 13)

    def test_task_cumulative_spend_survives_final_and_new_generation(self):
        state = self.reserve(self.state(100, task_cap=10), amount=6)
        state = self.record(state, kind="final", amount=6)
        state, _ = state.settle_operation("op-a")
        with self.assertRaises(BudgetError):
            self.reserve(state, op="op-b", amount=5, generation=2)
        state = self.reserve(state, op="op-b", amount=4, generation=2)
        self.assertEqual(state.task_snapshot("task-a").dimensions["tokens"].exposure, 10)

    def test_task_actual_overrun_stops_even_when_request_has_room(self):
        state = self.record(self.reserve(self.state(100, task_cap=5)), amount=6)
        self.assertTrue(state.stop_reasons)
        self.assertLess(state.task_snapshot("task-a").dimensions["tokens"].raw_remaining, 0)
        with self.assertRaises(BudgetError):
            self.reserve(state, op="op-b", amount=1, task="task-b")

    def test_same_observation_replay_or_conflict(self):
        state = self.record(self.reserve())
        replay, decision = state.record_usage_observation(self.obs())
        self.assertIs(replay, state)
        self.assertTrue(decision.replayed)
        with self.assertRaises(BudgetError):
            self.record(state, amount=3)

    def test_same_revision_mirror_is_retained_but_not_charged_twice(self):
        state = self.record(self.reserve())
        state, decision = state.record_usage_observation(self.obs(observation_id="obs-mirror"))
        self.assertEqual(decision.status, "MIRROR")
        self.assertEqual(self.view(state).known, 2)
        self.assertEqual(len(state.observations), 2)
        with self.assertRaises(BudgetError):
            self.record(state, observation_id="obs-conflict", amount=3)

    def test_historical_revision_never_changes_current_projection(self):
        state = self.record(self.reserve(), revision=3, amount=4)
        before = self.view(state)
        state, decision = state.record_usage_observation(self.obs(observation_id="obs-old", revision=1, amount=9))
        self.assertTrue(decision.historical)
        self.assertEqual(self.view(state), before)
        with self.assertRaises(BudgetError):
            self.record(state, observation_id="obs-old-conflict", revision=1, amount=8)

    def test_increasing_revision_does_not_authorize_decrease(self):
        state = self.record(self.reserve(), amount=4)
        with self.assertRaises(BudgetError):
            self.record(state, observation_id="obs-b", revision=2, amount=3)
        state = self.record(state, observation_id="obs-b", revision=2, amount=3,
                            correction=True, supersedes="obs-a")
        self.assertEqual(self.view(state).known, 3)

    def test_final_changes_require_current_supersession(self):
        state = self.record(self.reserve(), kind="final", amount=3)
        with self.assertRaises(BudgetError):
            self.record(state, observation_id="obs-b", kind="final", amount=4, revision=2)
        state = self.record(state, observation_id="obs-b", kind="final", amount=4, revision=2,
                            correction=True, supersedes="obs-a")
        with self.assertRaises(BudgetError):
            self.record(state, observation_id="obs-c", kind="final", amount=5, revision=3,
                        correction=True, supersedes="obs-a")
        self.assertEqual(self.view(state).known, 4)

    def test_invalid_correction_target_revision_and_branch_are_rejected(self):
        state = self.record(self.reserve(), amount=4)
        for target, revision in (("missing", 2), ("obs-a", 1), ("obs-b", 2)):
            with self.subTest(target=target, revision=revision), self.assertRaises(BudgetError):
                self.record(state, observation_id="obs-b", revision=revision, amount=3,
                            correction=True, supersedes=target)

    def test_single_sequence_and_cross_operation_call_ownership(self):
        state = self.reserve(amount=3)
        state = self.reserve(state, op="op-b", amount=3)
        state = self.record(state)
        with self.assertRaises(BudgetError):
            self.record(state, observation_id="other-call", economic_call_key="call-other")
        with self.assertRaises(BudgetError):
            self.record(state, operation_id="op-b", observation_id="other-op")

    def test_unknown_revision_cannot_reopen_with_same_revision(self):
        state = self.record(self.reserve(), kind="unknown", amount=None, unknown_reason="missing")
        with self.assertRaises(BudgetError):
            self.record(state, observation_id="obs-b", kind="final", amount=2)
        state = self.record(state, observation_id="obs-b", kind="final", amount=2, revision=2)
        self.assertEqual(self.view(state).unknown_operations, ())

    def test_release_requires_explicit_unstarted_fact_and_no_observations(self):
        state = self.reserve()
        with self.assertRaises(BudgetError):
            state.release_proven_unstarted("op-a")
        state, _ = state.release_proven_unstarted("op-a", not_started_proven=True)
        self.assertEqual(self.view(state).exposure, 0)
        replay, decision = state.release_proven_unstarted("op-a", not_started_proven=True)
        self.assertIs(replay, state)
        self.assertTrue(decision.replayed)
        with self.assertRaises(BudgetError):
            self.record(self.reserve()).release_proven_unstarted("op-a", not_started_proven=True)

    def test_cancelled_operation_late_bill_is_not_dropped(self):
        state, _ = self.reserve().release_proven_unstarted("op-a", not_started_proven=True)
        state = self.record(state, kind="final", amount=7)
        self.assertEqual(self.view(state).known, 7)
        self.assertIn("RECOVERY_REQUIRED", state.stop_reasons)

    def test_currencies_are_isolated_with_explicit_currency_binding(self):
        state = BudgetState(BudgetPolicy({"charge:USD": 10, "charge:JPY": 1000}))
        state = state.reserve_for_operation("op-a", "req-a", "task-a", {"charge:USD": 5, "charge:JPY": 0})[0]
        state = self.record(state, dimension="charge:USD", currency="USD", kind="final", amount=3)
        self.assertEqual(self.view(state, "charge:USD").known, 3)
        self.assertEqual(self.view(state, "charge:JPY").known, 0)
        for currency in (None, "JPY"):
            with self.subTest(currency=currency), self.assertRaises(BudgetError):
                self.obs(dimension="charge:USD", currency=currency)

    def test_scope_binding_is_checked_before_aggregation(self):
        state = self.reserve()
        for values in ({"request_id": "req-other"}, {"task_id": "task-other"},
                       {"operation_id": "op-other"}, {"dimension": "other"}):
            with self.subTest(values=values), self.assertRaises(BudgetError):
                self.record(state, **values)

    def test_stop_first_reason_and_epoch_persist(self):
        state = self.reserve().request_stop("FIRST").request_stop("SECOND")
        self.assertIs(state.request_stop("FIRST"), state)
        state = self.record(state, amount=12)
        self.assertEqual(state.stop_reasons[:2], ("FIRST", "SECOND"))
        self.assertEqual(state.stop_epoch, 1)
        self.assertIn("BUDGET_EXCEEDED", state.stop_reasons)

    def test_policy_and_reservation_inputs_are_copied_and_state_not_injectable(self):
        limits = {"tokens": 10}
        tasks = {"task-a": {"tokens": 5}}
        vector = {"tokens": 3}
        state = BudgetState(BudgetPolicy(limits, tasks))
        state = state.reserve_for_operation("op-a", "req-a", "task-a", vector)[0]
        limits.clear()
        tasks["task-a"].clear()
        vector.clear()
        self.assertEqual(self.view(state).held, 3)
        with self.assertRaises((TypeError, ValueError)):
            BudgetState(state.policy, operations=list(state.operations))
        with self.assertRaises((TypeError, ValueError)):
            replace(state, observations=())
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            state.operations = ()

    def test_sum_overflow_preserves_exact_facts_and_stops_admission(self):
        state = self.reserve(self.state(MAX_SAFE_INTEGER), amount=0)
        state = self.reserve(state, op="op-b", amount=0)
        state = self.record(state, kind="final", amount=MAX_SAFE_INTEGER)
        state = self.record(state, operation_id="op-b", observation_id="obs-b", economic_call_key="call-b",
                            kind="final", amount=1)
        self.assertEqual(self.view(state).known, MAX_SAFE_INTEGER + 1)
        self.assertIn("INTEGER_OVERFLOW", state.stop_reasons)
        with self.assertRaises(BudgetError):
            self.reserve(state, op="op-c", amount=0)

    def test_unsupported_delta_alias_and_relaxed_unknown_policy_fail_closed(self):
        for values in ({"kind": "delta"}, {"provider": "p", "billing_event_id": "bill"}):
            with self.subTest(values=values), self.assertRaises(BudgetError):
                self.obs(**values)
        with self.assertRaises(BudgetError):
            BudgetPolicy({"tokens": 10}, unknown_policy="bounded")

    def test_policy_caps_and_input_types_are_strict(self):
        for limits, tasks in (({}, {}), ({"tokens": True}, {}),
                              ({"tokens": 5}, {"task-a": {"tokens": 6}}),
                              ({"tokens": 5}, {"task-a": {"other": 1}})):
            with self.subTest(limits=limits, tasks=tasks), self.assertRaises(BudgetError):
                BudgetPolicy(limits, tasks)
        for values in ({"amount": True}, {"amount": 1.5}, {"amount": -1}, {"amount": MAX_SAFE_INTEGER + 1},
                       {"revision": True}, {"revision": 0}, {"final": 1}, {"correction": "yes"},
                       {"economic_call_key": None}, {"evidence_ref": None},
                       {"kind": "unknown", "amount": 2, "unknown_reason": "missing"},
                       {"kind": "unknown", "amount": None}, {"kind": "final", "final": False},
                       {"unknown_reason": "unexpected"}, {"observation_id": "bad\ud800"}):
            with self.subTest(values=values), self.assertRaises(BudgetError):
                self.obs(**values)

    def test_fingerprint_binds_revision_and_evidence(self):
        self.assertEqual(stable_observation_fingerprint(self.obs()), stable_observation_fingerprint(self.obs()))
        self.assertNotEqual(stable_observation_fingerprint(self.obs()), stable_observation_fingerprint(self.obs(revision=2)))
        self.assertNotEqual(stable_observation_fingerprint(self.obs()), stable_observation_fingerprint(self.obs(evidence_ref="b" * 64)))


if __name__ == "__main__":
    unittest.main()
