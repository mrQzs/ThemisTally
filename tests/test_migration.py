from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.codekit.migration import (
    MigrationError,
    MigrationLedger,
    MigrationOperation,
    MigrationPlan,
    MigrationPreflight,
    PreflightCheck,
    backup_ref,
    compare_history_inventory,
    create_backup_snapshot,
    preflight_ref,
)


def ref(kind: str, ident: str, payload: bytes = b"payload") -> dict[str, str]:
    return {"kind": kind, "id": ident, "sha256": hashlib.sha256(payload).hexdigest()}


class MigrationReferenceTests(unittest.TestCase):
    def _plan(self) -> tuple[MigrationPlan, MigrationOperation, dict, dict]:
        preflight = MigrationPreflight(
            "migration-a", "repo-a", "request-a",
            (PreflightCheck("identity", "READY", source_ref=ref("evidence", "identity")),
             PreflightCheck("history", "READY", source_ref=ref("evidence", "history"))),
            state="PREFLIGHTED",
        )
        snapshot = create_backup_snapshot("backup-a", {"state.json": b"before"}, source_generation=1)
        before = ref("config", "v1", b"before")
        after = ref("config", "v2", b"after")
        operation = MigrationOperation("switch-a", "switch_selection", after, before, before)
        plan = MigrationPlan(
            "migration-a", "repo-a", "request-a", preflight_ref(preflight), backup_ref(snapshot),
            ref("maintenance", "auth-a"), 1, before, after, (operation,), state="PLAN_REVIEWED",
        )
        return plan, operation, before, after

    def test_preflight_rejects_unknown_as_not_ready_and_is_immutable(self) -> None:
        preflight = MigrationPreflight(
            "migration-a", "repo-a", "request-a",
            (PreflightCheck("model", "UNKNOWN", remediation="obtain current profile"),),
        )
        self.assertEqual(preflight.status, "UNKNOWN")
        self.assertEqual(preflight.blocking_checks, ("model",))
        self.assertEqual(preflight.to_mapping()["offline_only"], True)
        with self.assertRaisesRegex(MigrationError, "E_STATUS"):
            PreflightCheck("bad", "PASS")  # not a migration preflight status

    def test_backup_and_history_preserve_bytes_and_classify_all_differences(self) -> None:
        snapshot = create_backup_snapshot("backup-a", {"b.txt": b"b", "a.txt": b"a"}, source_generation=1)
        self.assertEqual([entry[0] for entry in snapshot.entries], ["a.txt", "b.txt"])
        self.assertEqual(backup_ref(snapshot)["sha256"], snapshot.digest)
        report = compare_history_inventory(
            {"keep": hashlib.sha256(b"same").hexdigest(), "gone": hashlib.sha256(b"gone").hexdigest(),
             "changed": hashlib.sha256(b"old").hexdigest()},
            {"keep": hashlib.sha256(b"same").hexdigest(), "changed": hashlib.sha256(b"new").hexdigest(),
             "new": hashlib.sha256(b"new").hexdigest()},
            allowed_new=("allowed",), unreadable=("locked",),
        )
        self.assertEqual(report.status, "BLOCKED")
        self.assertEqual(report.unchanged, ("keep",))
        self.assertEqual(report.missing, ("gone",))
        self.assertEqual(report.changed, ("changed",))
        self.assertEqual(report.unplanned_added, ("new",))
        self.assertEqual(report.unreadable, ("locked",))

    def test_apply_replay_response_loss_and_idempotency_conflict(self) -> None:
        plan, operation, before, after = self._plan()
        ledger = MigrationLedger(target_ref=before)
        guards = {name: True for name in ("authorized", "quiescent", "backup_verified", "rules_current", "inputs_current")}
        first = ledger.apply(migration_id="migration-a", plan=plan, operation=operation,
                             idempotency_key="operation-a", expected_generation=1,
                             before_ref=before, after_ref=after, guards=guards)
        self.assertEqual((first.status, first.replayed, first.to_generation), ("APPLIED", False, 2))
        replay = ledger.apply(migration_id="migration-a", plan=plan, operation=operation,
                              idempotency_key="operation-a", expected_generation=1,
                              before_ref=before, after_ref=after, guards=guards)
        self.assertEqual((replay.status, replay.replayed), ("REPLAYED", True))
        with self.assertRaisesRegex(MigrationError, "E_IDEMPOTENCY_CONFLICT"):
            ledger.apply(migration_id="migration-a", plan=plan, operation=operation,
                         idempotency_key="operation-a", expected_generation=2,
                         before_ref=before, after_ref=after, guards=guards)

    def test_response_loss_commits_once_and_same_key_recovers_receipt(self) -> None:
        plan, operation, before, after = self._plan()
        ledger = MigrationLedger(target_ref=before)
        guards = {name: True for name in ("authorized", "quiescent", "backup_verified", "rules_current", "inputs_current")}
        with self.assertRaisesRegex(MigrationError, "E_RESPONSE_LOST"):
            ledger.apply(migration_id="migration-a", plan=plan, operation=operation,
                         idempotency_key="operation-a", expected_generation=1,
                         before_ref=before, after_ref=after, guards=guards, lose_response=True)
        self.assertEqual(ledger.current()[0], 2)
        recovered = ledger.apply(migration_id="migration-a", plan=plan, operation=operation,
                                 idempotency_key="operation-a", expected_generation=1,
                                 before_ref=before, after_ref=after, guards=guards)
        self.assertEqual((recovered.status, recovered.replayed, recovered.current_generation), ("REPLAYED", True, 2))

    def test_cas_and_precommit_failure_do_not_mutate_selection(self) -> None:
        plan, operation, before, after = self._plan()
        ledger = MigrationLedger(target_ref=before)
        guards = {name: True for name in ("authorized", "quiescent", "backup_verified", "rules_current", "inputs_current")}
        with self.assertRaisesRegex(MigrationError, "E_PRECOMMIT_FAILURE"):
            ledger.apply(migration_id="migration-a", plan=plan, operation=operation,
                         idempotency_key="operation-a", expected_generation=1,
                         before_ref=before, after_ref=after, guards=guards, crash_before_commit=True)
        self.assertEqual(ledger.current(), (1, before))
        with self.assertRaisesRegex(MigrationError, "E_CAS_CONFLICT"):
            ledger.apply(migration_id="migration-a", plan=plan, operation=operation,
                         idempotency_key="operation-b", expected_generation=2,
                         before_ref=before, after_ref=after, guards=guards)
        self.assertEqual(ledger.current(), (1, before))

    def test_rollback_is_new_generation_and_user_edit_blocks_inverse(self) -> None:
        plan, operation, before, after = self._plan()
        ledger = MigrationLedger(target_ref=before)
        guards = {name: True for name in ("authorized", "quiescent", "backup_verified", "rules_current", "inputs_current")}
        ledger.apply(migration_id="migration-a", plan=plan, operation=operation,
                     idempotency_key="operation-a", expected_generation=1,
                     before_ref=before, after_ref=after, guards=guards)
        rolled = ledger.rollback(migration_id="migration-a", plan=plan, operation=operation,
                                 idempotency_key="rollback-a", expected_generation=2,
                                 current_ref=after, guards=guards)
        self.assertEqual((rolled.status, rolled.from_generation, rolled.to_generation), ("ROLLED_BACK", 2, 3))
        self.assertEqual(ledger.current(), (3, before))
        # A stale operation cannot resurrect its old postimage after a newer
        # selection has been applied; the current bytes are the user boundary.
        operation_b = MigrationOperation("switch-b", "switch_selection", after, before, before)
        plan_b = MigrationPlan(
            "migration-a", "repo-a", "request-a", plan.preflight_ref, plan.backup_ref,
            plan.maintenance_authorization_ref, 3, before, after, (operation_b,), state="PLAN_REVIEWED",
        )
        ledger.apply(migration_id="migration-a", plan=plan_b, operation=operation_b,
                     idempotency_key="operation-b", expected_generation=3,
                     before_ref=before, after_ref=after, guards=guards)
        user_edit = ref("config", "user-edit", b"user-edit")
        operation_c = MigrationOperation("switch-c", "switch_selection", user_edit, after, after)
        plan_c = MigrationPlan(
            "migration-a", "repo-a", "request-a", plan.preflight_ref, plan.backup_ref,
            plan.maintenance_authorization_ref, 4, after, user_edit, (operation_c,), state="PLAN_REVIEWED",
        )
        ledger.apply(migration_id="migration-a", plan=plan_c, operation=operation_c,
                     idempotency_key="operation-c", expected_generation=4,
                     before_ref=after, after_ref=user_edit, guards=guards)
        with self.assertRaisesRegex(MigrationError, "E_ROLLBACK_USER_EDIT"):
            ledger.rollback(migration_id="migration-a", plan=plan, operation=operation,
                            idempotency_key="rollback-old", expected_generation=5,
                            current_ref=user_edit, guards=guards)

    def test_plan_forbids_online_calls_and_switch_requires_compensation(self) -> None:
        plan, operation, _before, _after = self._plan()
        self.assertFalse(plan.online_calls_allowed)
        self.assertEqual(operation.kind, "switch_selection")
        with self.assertRaisesRegex(MigrationError, "E_COMPENSATION"):
            MigrationOperation("switch-no-comp", "switch_selection", operation.target_ref, operation.precondition_ref)

    def test_combined_schema_is_closed_and_covers_all_record_families(self) -> None:
        schema_path = Path(__file__).parents[1] / "schemas" / "migration-records-v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(
            {item["$ref"] for item in schema["oneOf"]},
            {"#/$defs/migration_preflight", "#/$defs/migration_plan", "#/$defs/migration_operation",
             "#/$defs/migration_receipt", "#/$defs/history_integrity_report", "#/$defs/backup_snapshot"},
        )
        self.assertEqual(len(schema["$defs"]), 12)
        for name in ("migration_preflight", "migration_plan", "migration_operation", "migration_receipt",
                     "history_integrity_report", "backup_snapshot"):
            self.assertFalse(schema["$defs"][name].get("additionalProperties", True))
        # jsonschema is an optional WSL verification dependency; the shape
        # checks above still run in the Windows 3.9 environment.
        try:
            import jsonschema
        except ImportError:
            return
        plan, operation, _before, _after = self._plan()
        snapshot = create_backup_snapshot("backup-schema", {"x": b"x"}, source_generation=1)
        values = [
            plan.to_mapping(), operation.to_mapping(), snapshot.to_mapping(),
            compare_history_inventory({"x": hashlib.sha256(b"x").hexdigest()},
                                      {"x": hashlib.sha256(b"x").hexdigest()}).to_mapping(),
        ]
        ledger = MigrationLedger(target_ref=plan.before_selection_ref)
        guards = {name: True for name in ("authorized", "quiescent", "backup_verified", "rules_current", "inputs_current")}
        receipt = ledger.apply(migration_id=plan.migration_id, plan=plan, operation=operation,
                               idempotency_key="schema-apply", expected_generation=1,
                               before_ref=plan.before_selection_ref, after_ref=plan.after_selection_ref,
                               guards=guards)
        values.extend([receipt.to_mapping(), MigrationPreflight(
            "migration-schema", "repo-schema", "request-schema",
            (PreflightCheck("identity", "READY"),), state="PREFLIGHTED").to_mapping()])
        for value in values:
            jsonschema.Draft202012Validator(schema).validate(value)


if __name__ == "__main__":
    unittest.main()
