#!/usr/bin/env python3
"""07-T2C-L restricted SQLite ledger tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from codekit.claim_model import ClaimFacts, ClaimRequest  # noqa: E402
from codekit.scheduler_store import SchedulerStore, SchedulerStoreError  # noqa: E402


REQUEST_ID = "req-" + "a" * 32


def request(**changes: object) -> ClaimRequest:
    values = {
        "repo_id": "code-kit", "request_id": REQUEST_ID, "task_id": "task-a", "plan_version": 1,
        "idempotency_key": "key-a", "request_fingerprint": "fingerprint-a",
        "controller_generation": 1, "guard_version": 1, "stop_epoch": 0,
    }
    values.update(changes)
    return ClaimRequest(**values)  # type: ignore[arg-type]


def facts(**changes: object) -> ClaimFacts:
    values = {
        "request_open": True, "stop_requested": False, "controller_generation": 1,
        "guard_version": 1, "stop_epoch": 0, "contract_valid": True, "baseline_valid": True,
        "upstream_accepted": True, "resources_available": True, "budget_available": True,
    }
    values.update(changes)
    return ClaimFacts(**values)  # type: ignore[arg-type]


class SchedulerStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "ledger.sqlite3"
        self.store = SchedulerStore(self.path)
        self.store.seed_request(REQUEST_ID, "code-kit", max_concurrency=2)
        self.store.seed_task(REQUEST_ID, "task-a", max_attempts=3)
        self.store.seed_task(REQUEST_ID, "task-b", max_attempts=3)

    def tearDown(self) -> None:
        self.store.close()
        self.temp.cleanup()

    def test_schema_uses_delete_journal_foreign_keys_and_short_transactions(self) -> None:
        self.assertIn(str(self.store.db.execute("PRAGMA journal_mode").fetchone()[0]).lower(), ("delete", "memory"))
        self.assertEqual(self.store.db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(self.store.db.execute("PRAGMA synchronous").fetchone()[0], 2)

    def test_claim_handoff_and_outbox_are_persisted_together(self) -> None:
        result = self.store.claim(request(), facts(), owner="owner-a", lease_until=100,
                                  reservation={"dispatches": 1}, resource_keys=["src/a"])
        self.assertEqual((result.state, result.replayed), ("CLAIMED", False))
        self.assertEqual(self.store.operation(result.operation_id)["state"], "CLAIMED")
        handoff = self.store.handoff(result.operation_id, owner="owner-a", now=10,
                                     budget_available=True, resources_available=True)
        self.assertEqual((handoff.state, handoff.replayed), ("HANDOFF_ACCEPTED", False))
        self.assertEqual([row["event_type"] for row in self.store.outbox()],
                         ["scheduler.claimed", "scheduler.handoff_accepted"])
        payload = json.loads(self.store.outbox()[0]["payload_json"])
        self.assertEqual(payload["resources"], ["src/a"])
        self.assertEqual(payload["reservation"], {"dispatches": 1})
        self.assertEqual(payload["owner"], "owner-a")
        self.assertEqual(payload["lease_until"], 100.0)

    def test_same_key_replays_and_different_fingerprint_conflicts(self) -> None:
        first = self.store.claim(request(), facts(), owner="owner-a", lease_until=100,
                                 reservation={"dispatches": 1}, resource_keys=[])
        replay = self.store.claim(request(), facts(), owner="owner-b", lease_until=200,
                                  reservation={"dispatches": 1}, resource_keys=[])
        self.assertEqual((replay.operation_id, replay.replayed), (first.operation_id, True))
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.claim(request(request_fingerprint="other"), facts(), owner="owner-a", lease_until=100,
                             reservation={"dispatches": 1}, resource_keys=[])
        self.assertEqual(caught.exception.code, "E_IDEMPOTENCY_CONFLICT")
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.claim(request(task_id="task-b"), facts(), owner="owner-a", lease_until=100,
                             reservation={"dispatches": 1}, resource_keys=[])
        self.assertEqual(caught.exception.code, "E_IDEMPOTENCY_CONFLICT")

    def test_same_key_new_generation_or_stop_epoch_is_not_old_replay(self) -> None:
        self.store.claim(request(), facts(), owner="owner-a", lease_until=100,
                         reservation={"dispatches": 1}, resource_keys=[])
        self.assertEqual(self.store.rollover(), 2)
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.claim(request(controller_generation=2, stop_epoch=1),
                             facts(controller_generation=2, stop_epoch=1, request_open=False, stop_requested=True),
                             owner="owner-a", lease_until=100, reservation={"dispatches": 1}, resource_keys=[])
        self.assertEqual(caught.exception.code, "E_IDEMPOTENCY_CONFLICT")

    def test_active_task_and_resource_holds_are_atomic_guards(self) -> None:
        self.store.claim(request(), facts(), owner="owner-a", lease_until=100,
                         reservation={"dispatches": 1}, resource_keys=["shared"])
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.claim(request(plan_version=2, idempotency_key="key-b", request_fingerprint="fp-b"), facts(),
                             owner="owner-b", lease_until=100, reservation={"dispatches": 1}, resource_keys=[])
        self.assertEqual(caught.exception.code, "E_CLAIM_BLOCKED")
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.claim(request(task_id="task-b", idempotency_key="key-b", request_fingerprint="fp-b"), facts(),
                             owner="owner-b", lease_until=100, reservation={"dispatches": 1}, resource_keys=["shared"])
        self.assertEqual(caught.exception.code, "E_RESOURCE_BUSY")

    def test_failed_transaction_leaves_no_partial_claim_or_outbox(self) -> None:
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.claim(request(), facts(), owner="owner-a", lease_until=100,
                             reservation={"dispatches": 1}, resource_keys=["src/a"], fail_before_commit=True)
        self.assertEqual(caught.exception.code, "E_SYNTHETIC_FAILPOINT")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM operations").fetchone()[0], 0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM resource_holds").fetchone()[0], 0)
        self.assertEqual(len(self.store.outbox()), 0)

    def test_rollover_fences_handoff_and_stop_blocks_claim(self) -> None:
        result = self.store.claim(request(), facts(), owner="owner-a", lease_until=100,
                                  reservation={"dispatches": 1}, resource_keys=[])
        self.assertEqual(self.store.rollover(), 2)
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.handoff(result.operation_id, owner="owner-a", now=10)
        self.assertEqual(caught.exception.code, "E_HANDOFF_BLOCKED")
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.cancel_unstarted(result.operation_id, owner="owner-a", generation=2)
        self.assertEqual(caught.exception.code, "E_FENCED")
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.claim(request(task_id="task-b", idempotency_key="key-b", request_fingerprint="fp-b"), facts(),
                             owner="owner-b", lease_until=100, reservation={"dispatches": 1}, resource_keys=[])
        self.assertEqual(caught.exception.code, "E_CLAIM_BLOCKED")
        self.store.close()
        self.store = SchedulerStore(self.path)
        self.store.stop(REQUEST_ID, "TEST_STOP")
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.claim(request(idempotency_key="key-b", request_fingerprint="fp-b", controller_generation=2,
                                     stop_epoch=1), facts(request_open=False, stop_requested=True,
                                                          controller_generation=2, stop_epoch=1), owner="owner-b",
                             lease_until=100, reservation={"dispatches": 1}, resource_keys=[])
        self.assertEqual(caught.exception.code, "E_CLAIM_BLOCKED")

    def test_cancel_before_handoff_releases_hold_and_is_idempotent(self) -> None:
        result = self.store.claim(request(), facts(), owner="owner-a", lease_until=100,
                                  reservation={"dispatches": 1}, resource_keys=["src/a"])
        cancelled = self.store.cancel_unstarted(result.operation_id, owner="owner-a", generation=1)
        self.assertEqual(cancelled.state, "CANCELLED_NOT_STARTED")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM resource_holds").fetchone()[0], 0)
        claim_replay = self.store.claim(request(), facts(), owner="owner-b", lease_until=200,
                                        reservation={"dispatches": 1}, resource_keys=["src/a"])
        self.assertTrue(claim_replay.replayed)
        replay = self.store.cancel_unstarted(result.operation_id, owner="owner-a", generation=1)
        self.assertTrue(replay.replayed)
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.handoff(result.operation_id, owner="owner-a", now=10,
                               budget_available=True, resources_available=True)
        self.assertEqual(caught.exception.code, "E_HANDOFF_STATE")

    def test_cancel_requires_owner_binding(self) -> None:
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.claim(object(), facts(), owner="owner-a", lease_until=100,
                             reservation={"dispatches": 1}, resource_keys=[])
        self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.claim(request(), facts(), owner="owner-a", lease_until=10 ** 10000,
                             reservation={"dispatches": 1}, resource_keys=[])
        self.assertEqual(caught.exception.code, "E_SCHEMA_TYPE")
        result = self.store.claim(request(), facts(), owner="owner-a", lease_until=100,
                                  reservation={"dispatches": 1}, resource_keys=["src/a"])
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.cancel_unstarted(result.operation_id, owner="owner-b", generation=1)
        self.assertEqual(caught.exception.code, "E_FENCED")

    def test_expired_lease_and_unknown_budget_remain_blocked(self) -> None:
        result = self.store.claim(request(), facts(), owner="owner-a", lease_until=10,
                                  reservation={"dispatches": 1}, resource_keys=[])
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.handoff(result.operation_id, owner="owner-a", now=10,
                               budget_available=True, resources_available=True)
        self.assertEqual(caught.exception.code, "E_HANDOFF_BLOCKED")
        result = self.store.claim(request(task_id="task-b", idempotency_key="key-b", request_fingerprint="fp-b"),
                                  facts(), owner="owner-b", lease_until=100, reservation={"dispatches": 1}, resource_keys=[])
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.handoff(result.operation_id, owner="owner-b", now=1, budget_available=None)
        self.assertEqual(caught.exception.code, "E_HANDOFF_BLOCKED")

    def test_accepted_handoff_rechecks_lease_and_fencing_on_replay(self) -> None:
        result = self.store.claim(request(), facts(), owner="owner-a", lease_until=100,
                                  reservation={"dispatches": 1}, resource_keys=[])
        self.store.handoff(result.operation_id, owner="owner-a", now=1,
                           budget_available=True, resources_available=True)
        replay = self.store.handoff(result.operation_id, owner="owner-a", now=2)
        self.assertTrue(replay.replayed)
        self.assertEqual(self.store.rollover(), 2)
        with self.assertRaises(SchedulerStoreError) as caught:
            self.store.handoff(result.operation_id, owner="owner-a", now=2)
        self.assertEqual(caught.exception.code, "E_HANDOFF_BLOCKED")

    def test_stop_is_idempotent_and_preserves_first_reason(self) -> None:
        self.store.stop(REQUEST_ID, "FIRST")
        self.store.stop(REQUEST_ID, "SECOND")
        row = self.store.db.execute(
            "SELECT stopped,stop_epoch,stop_reason FROM requests WHERE request_id=?", (REQUEST_ID,)
        ).fetchone()
        self.assertEqual(tuple(row), (1, 1, "FIRST"))
        events = self.store.outbox()
        self.assertEqual([item["event_type"] for item in events], ["request.stopped", "request.stop_already"])
        self.assertEqual(json.loads(events[-1]["payload_json"])["reason"], "FIRST")

    def test_partial_or_unconstrained_schema_is_rejected(self) -> None:
        view_only = Path(self.temp.name) / "view.sqlite3"
        db = sqlite3.connect(view_only)
        db.execute("CREATE VIEW scheduler_meta AS SELECT 1 AS singleton, 1 AS schema_version")
        db.commit()
        db.close()
        with self.assertRaises(SchedulerStoreError) as caught:
            SchedulerStore(view_only)
        self.assertEqual(caught.exception.code, "E_SCHEMA_MISSING")

        partial = Path(self.temp.name) / "partial.sqlite3"
        db = sqlite3.connect(partial)
        db.execute("CREATE TABLE scheduler_meta(singleton INTEGER, schema_version INTEGER)")
        db.execute("INSERT INTO scheduler_meta VALUES(1,1)")
        db.commit()
        db.close()
        with self.assertRaises(SchedulerStoreError) as caught:
            SchedulerStore(partial)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")

        malformed = Path(self.temp.name) / "malformed.sqlite3"
        db = sqlite3.connect(malformed)
        db.executescript("""
        CREATE TABLE scheduler_meta(singleton INTEGER, schema_version INTEGER);
        INSERT INTO scheduler_meta VALUES(1,1);
        CREATE TABLE controller(singleton INTEGER, generation INTEGER);
        CREATE TABLE requests(request_id TEXT, repo_id TEXT, max_concurrency INTEGER,
                              stopped INTEGER, stop_epoch INTEGER, stop_reason TEXT);
        CREATE TABLE tasks(request_id TEXT, task_id TEXT, guard_version INTEGER, max_attempts INTEGER);
        CREATE TABLE operations(operation_id TEXT, request_id TEXT, task_id TEXT, plan_version INTEGER,
                                controller_generation INTEGER, claim_generation INTEGER, guard_version INTEGER,
                                stop_epoch INTEGER, idempotency_key TEXT, request_fingerprint TEXT, owner TEXT,
                                lease_until REAL, state TEXT, reservation_json TEXT, resource_json TEXT);
        CREATE TABLE resource_holds(repo_id TEXT, resource_key TEXT, operation_id TEXT);
        CREATE TABLE outbox(seq INTEGER, operation_id TEXT, event_type TEXT, payload_json TEXT);
        INSERT INTO controller VALUES(1,1);
        """)
        db.commit()
        db.close()
        with self.assertRaises(SchedulerStoreError) as caught:
            SchedulerStore(malformed)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")

        corrupted = Path(self.temp.name) / "corrupted.sqlite3"
        valid = SchedulerStore(corrupted)
        valid.seed_request(REQUEST_ID, "code-kit")
        valid.close()
        db = sqlite3.connect(corrupted)
        db.execute("UPDATE requests SET max_concurrency='oops' WHERE request_id=?", (REQUEST_ID,))
        db.commit()
        db.close()
        with self.assertRaises(SchedulerStoreError) as caught:
            SchedulerStore(corrupted)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")

    def test_reopen_rejects_resource_hold_drift_and_generation_split(self) -> None:
        valid = Path(self.temp.name) / "drift.sqlite3"
        store = SchedulerStore(valid)
        store.seed_request(REQUEST_ID, "code-kit")
        store.seed_task(REQUEST_ID, "task-a")
        result = store.claim(request(), facts(), owner="owner-a", lease_until=100,
                             reservation={"dispatches": 1}, resource_keys=["src/a"])
        store.close()
        db = sqlite3.connect(valid)
        db.execute("UPDATE operations SET controller_generation=2 WHERE operation_id=?", (result.operation_id,))
        db.commit()
        db.close()
        with self.assertRaises(SchedulerStoreError) as caught:
            SchedulerStore(valid)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")

        valid = Path(self.temp.name) / "hold-drift.sqlite3"
        store = SchedulerStore(valid)
        store.seed_request(REQUEST_ID, "code-kit")
        store.seed_task(REQUEST_ID, "task-a")
        result = store.claim(request(), facts(), owner="owner-a", lease_until=100,
                             reservation={"dispatches": 1}, resource_keys=["src/a"])
        store.close()
        db = sqlite3.connect(valid)
        db.execute("DELETE FROM resource_holds WHERE operation_id=?", (result.operation_id,))
        db.commit()
        db.close()
        with self.assertRaises(SchedulerStoreError) as caught:
            SchedulerStore(valid)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")

    def test_reopen_rejects_hold_for_finished_operation(self) -> None:
        valid = Path(self.temp.name) / "finished-hold.sqlite3"
        store = SchedulerStore(valid)
        store.seed_request(REQUEST_ID, "code-kit")
        store.seed_task(REQUEST_ID, "task-a")
        result = store.claim(request(), facts(), owner="owner-a", lease_until=100,
                             reservation={"dispatches": 1}, resource_keys=[])
        store.close()
        db = sqlite3.connect(valid)
        db.execute("UPDATE operations SET state='ACCEPTED' WHERE operation_id=?", (result.operation_id,))
        db.execute("INSERT INTO resource_holds(repo_id,resource_key,operation_id) VALUES(?,?,?)",
                   ("code-kit", "stray", result.operation_id))
        db.commit()
        db.close()
        with self.assertRaises(SchedulerStoreError) as caught:
            SchedulerStore(valid)
        self.assertEqual(caught.exception.code, "E_SCHEMA_INVALID")

    def test_reopen_rejects_nonstandard_json_constants(self) -> None:
        valid = Path(self.temp.name) / "nan.sqlite3"
        store = SchedulerStore(valid)
        store.seed_request(REQUEST_ID, "code-kit")
        store.close()
        db = sqlite3.connect(valid)
        db.execute("INSERT INTO outbox(operation_id,event_type,payload_json) VALUES(?,?,?)",
                   (None, "tampered", '{"value":NaN}'))
        db.commit(); db.close()
        with self.assertRaises(SchedulerStoreError):
            SchedulerStore(valid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
