"""Small v2 prototype joining claim, budget reservation and resource holds.

The existing v1 stores intentionally remain unchanged.  This adapter is a
single SQLite ledger with short ``BEGIN IMMEDIATE`` transactions; it never
starts a process, calls a provider, inspects Git, or claims that handoff is
complete.  It is an integration proof, not a production scheduler.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator, Mapping, Sequence
import uuid

from .budget import (BudgetError, BudgetOperation, BudgetPolicy, BudgetSnapshot,
                     BudgetState, UsageObservation, stable_observation_fingerprint)
from .claim_model import ClaimFacts, ClaimModelError, ClaimRequest, claim_decision
from .protocols import MAX_SAFE_INTEGER, ProtocolError


class AtomicLedgerError(RuntimeError):
    def __init__(self, code: str, reasons: Sequence[str] = ()) -> None:
        self.code = code
        self.reasons = tuple(reasons)
        super().__init__(f"{code}: {', '.join(self.reasons)}")


@dataclass(frozen=True)
class AtomicClaimResult:
    operation_id: str
    state: str
    replayed: bool = False
    reasons: tuple[str, ...] = ()


DDL = """
CREATE TABLE IF NOT EXISTS atomic_meta(singleton INTEGER PRIMARY KEY CHECK(singleton=1), schema_version INTEGER NOT NULL CHECK(schema_version=2));
CREATE TABLE IF NOT EXISTS controller(singleton INTEGER PRIMARY KEY CHECK(singleton=1), generation INTEGER NOT NULL CHECK(generation>=1));
CREATE TABLE IF NOT EXISTS requests(request_id TEXT PRIMARY KEY, repo_id TEXT NOT NULL, max_concurrency INTEGER NOT NULL CHECK(max_concurrency>0), stopped INTEGER NOT NULL DEFAULT 0 CHECK(stopped IN(0,1)), stop_epoch INTEGER NOT NULL DEFAULT 0 CHECK(stop_epoch>=0), stop_reason TEXT);
CREATE TABLE IF NOT EXISTS policies(request_id TEXT PRIMARY KEY REFERENCES requests(request_id), policy_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks(request_id TEXT NOT NULL REFERENCES requests(request_id), task_id TEXT NOT NULL, guard_version INTEGER NOT NULL CHECK(guard_version>=1), max_attempts INTEGER NOT NULL CHECK(max_attempts>=1), PRIMARY KEY(request_id,task_id));
CREATE TABLE IF NOT EXISTS operations(operation_id TEXT PRIMARY KEY, request_id TEXT NOT NULL, task_id TEXT NOT NULL, plan_version INTEGER NOT NULL CHECK(plan_version>=1), idempotency_key TEXT NOT NULL, request_fingerprint TEXT NOT NULL, owner TEXT NOT NULL, generation INTEGER NOT NULL CHECK(generation>=1), claim_generation INTEGER NOT NULL CHECK(claim_generation>=1), guard_version INTEGER NOT NULL CHECK(guard_version>=1), stop_epoch INTEGER NOT NULL CHECK(stop_epoch>=0), lease_until REAL, state TEXT NOT NULL CHECK(state IN('CLAIMED','HANDOFF_ACCEPTED','FINISHED','CANCELLED_NOT_STARTED','START_UNKNOWN')), reservation_json TEXT NOT NULL, resource_json TEXT NOT NULL, UNIQUE(request_id,idempotency_key), FOREIGN KEY(request_id,task_id) REFERENCES tasks(request_id,task_id));
CREATE UNIQUE INDEX IF NOT EXISTS one_active_task_v2 ON operations(request_id,task_id) WHERE state IN('CLAIMED','HANDOFF_ACCEPTED','START_UNKNOWN');
CREATE TABLE IF NOT EXISTS resource_holds(repo_id TEXT NOT NULL, resource_key TEXT NOT NULL, operation_id TEXT NOT NULL REFERENCES operations(operation_id), PRIMARY KEY(repo_id,resource_key));
CREATE TABLE IF NOT EXISTS observations(observation_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL REFERENCES operations(operation_id), request_id TEXT NOT NULL REFERENCES requests(request_id), payload_json TEXT NOT NULL, fingerprint TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS atomic_observation_immutable_update BEFORE UPDATE ON observations BEGIN SELECT RAISE(ABORT,'immutable observation'); END;
CREATE TRIGGER IF NOT EXISTS atomic_observation_immutable_delete BEFORE DELETE ON observations BEGIN SELECT RAISE(ABORT,'immutable observation'); END;
CREATE TABLE IF NOT EXISTS stop_reasons(request_id TEXT NOT NULL REFERENCES requests(request_id), reason TEXT NOT NULL, stop_epoch INTEGER NOT NULL CHECK(stop_epoch>=1), PRIMARY KEY(request_id,reason));
CREATE TABLE IF NOT EXISTS outbox(seq INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT, operation_id TEXT, event_type TEXT NOT NULL, payload_json TEXT NOT NULL);
INSERT OR IGNORE INTO atomic_meta(singleton,schema_version) VALUES(1,2);
INSERT OR IGNORE INTO controller(singleton,generation) VALUES(1,1);
"""


def _text(value: Any, field: str, limit: int = 256) -> str:
    if type(value) is not str or not value or len(value) > limit or "\x00" in value or any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise AtomicLedgerError("E_SCHEMA_TYPE", (field,))
    return value


def _int(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or isinstance(value, bool) or value < minimum or value > MAX_SAFE_INTEGER:
        raise AtomicLedgerError("E_SCHEMA_TYPE", (field,))
    return value


def _finite(value: Any, field: str) -> float:
    if type(value) not in (int, float):
        raise AtomicLedgerError("E_SCHEMA_TYPE", (field,))
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise AtomicLedgerError("E_SCHEMA_TYPE", (field,)) from exc
    if not math.isfinite(result) or result < 0:
        raise AtomicLedgerError("E_SCHEMA_TYPE", (field,))
    return result


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise AtomicLedgerError("E_SCHEMA_TYPE", ("json",)) from exc


def _resources(value: Sequence[str]) -> tuple[str, ...]:
    if type(value) is not list or len(value) > 256:
        raise AtomicLedgerError("E_RESOURCE_KEYS")
    if any(type(x) is not str or not x or len(x) > 200 or "\x00" in x or any(0xD800 <= ord(ch) <= 0xDFFF for ch in x) for x in value) or len(set(value)) != len(value):
        raise AtomicLedgerError("E_RESOURCE_KEYS")
    return tuple(sorted(value))


def _policy_payload(policy: BudgetPolicy) -> dict[str, Any]:
    return {"limits": dict(policy.limits), "task_limits": {k: dict(v) for k, v in policy.task_limits.items()}, "policy_ref": policy.policy_ref, "unknown_policy": policy.unknown_policy}


def _policy(value: str) -> BudgetPolicy:
    try:
        raw = json.loads(value)
        return BudgetPolicy(raw["limits"], raw["task_limits"], policy_ref=raw["policy_ref"], unknown_policy=raw["unknown_policy"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, BudgetError) as exc:
        raise AtomicLedgerError("E_SCHEMA_INVALID", ("policy_json",)) from exc


def _observation_payload(observation: UsageObservation) -> dict[str, Any]:
    if type(observation) is not UsageObservation:
        raise AtomicLedgerError("E_SCHEMA_TYPE", ("observation",))
    return {
        "observation_id": observation.observation_id,
        "operation_id": observation.operation_id,
        "dimension": observation.dimension,
        "kind": observation.kind,
        "amount": observation.amount,
        "revision": observation.revision,
        "economic_call_key": observation.economic_call_key,
        "provider": observation.provider,
        "billing_event_id": observation.billing_event_id,
        "currency": observation.currency,
        "final": observation.final,
        "correction": observation.correction,
        "supersedes": observation.supersedes,
        "unknown_reason": observation.unknown_reason,
        "evidence_ref": observation.evidence_ref,
        "request_id": observation.request_id,
        "task_id": observation.task_id,
    }


def _observation_from_payload(value: Any) -> UsageObservation:
    if type(value) is not dict:
        raise AtomicLedgerError("E_SCHEMA_INVALID", ("observation_json",))
    try:
        return UsageObservation(**value)
    except (BudgetError, TypeError, ValueError) as exc:
        raise AtomicLedgerError("E_SCHEMA_INVALID", ("observation_json",)) from exc


class AtomicClaimBudgetStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=5.0)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        mode = str(self.db.execute("PRAGMA journal_mode=DELETE").fetchone()[0]).lower()
        if mode not in ("delete", "memory"):
            self.close(); raise AtomicLedgerError("E_DB_MODE", (mode,))
        self.db.execute("PRAGMA synchronous=FULL")
        # A genuinely empty database may be initialized.  Any existing user
        # schema is treated as a migration boundary and must already be the
        # exact v2 shape; IF NOT EXISTS must never silently repair it.
        objects = self.db.execute(
            "SELECT type,name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        ).fetchall()
        table_names = {row[1] for row in objects if row[0] == "table"}
        required = {"atomic_meta", "controller", "requests", "policies", "tasks", "operations", "resource_holds", "observations", "stop_reasons", "outbox"}
        if objects and not required.issubset(table_names):
            self.close()
            raise AtomicLedgerError("E_SCHEMA_INVALID", ("partial_schema",))
        if not objects:
            self.db.executescript(DDL)
        try:
            self._validate_schema()
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "AtomicClaimBudgetStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    @contextmanager
    def _tx(self) -> Iterator[None]:
        try:
            self.db.execute("BEGIN IMMEDIATE")
            yield
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def _validate_schema(self) -> None:
        required = {"atomic_meta", "controller", "requests", "policies", "tasks", "operations", "resource_holds", "observations", "stop_reasons", "outbox"}
        actual = {row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required.issubset(actual):
            raise AtomicLedgerError("E_SCHEMA_INVALID", ("missing_table",))
        if self.db.execute("PRAGMA foreign_keys").fetchone()[0] != 1 or self.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise AtomicLedgerError("E_SCHEMA_INVALID", ("integrity",))
        expected = {
            "atomic_meta": {"singleton", "schema_version"},
            "controller": {"singleton", "generation"},
            "requests": {"request_id", "repo_id", "max_concurrency", "stopped", "stop_epoch", "stop_reason"},
            "policies": {"request_id", "policy_json"},
            "tasks": {"request_id", "task_id", "guard_version", "max_attempts"},
            "operations": {"operation_id", "request_id", "task_id", "plan_version", "idempotency_key", "request_fingerprint", "owner", "generation", "claim_generation", "guard_version", "stop_epoch", "lease_until", "state", "reservation_json", "resource_json"},
            "resource_holds": {"repo_id", "resource_key", "operation_id"},
            "observations": {"observation_id", "operation_id", "request_id", "payload_json", "fingerprint"},
            "stop_reasons": {"request_id", "reason", "stop_epoch"},
            "outbox": {"seq", "request_id", "operation_id", "event_type", "payload_json"},
        }
        for table, columns in expected.items():
            actual_columns = {row[1] for row in self.db.execute(f"PRAGMA table_info({table})")}
            if not columns.issubset(actual_columns):
                raise AtomicLedgerError("E_SCHEMA_INVALID", (f"columns:{table}",))
        primary_keys = {
            "atomic_meta": ("singleton",), "controller": ("singleton",), "requests": ("request_id",),
            "policies": ("request_id",), "tasks": ("request_id", "task_id"), "operations": ("operation_id",),
            "resource_holds": ("repo_id", "resource_key"), "observations": ("observation_id",), "stop_reasons": ("request_id", "reason"), "outbox": ("seq",),
        }
        for table, expected_pk in primary_keys.items():
            actual_pk = tuple(row[1] for row in sorted(self.db.execute(f"PRAGMA table_info({table})"), key=lambda r: r[5]) if row[5])
            if actual_pk != expected_pk:
                raise AtomicLedgerError("E_SCHEMA_INVALID", (f"primary_key:{table}",))
        required_notnull = {
            "atomic_meta": {"schema_version"}, "controller": {"generation"},
            "requests": {"repo_id", "max_concurrency", "stopped", "stop_epoch"},
            "policies": {"policy_json"}, "tasks": {"guard_version", "max_attempts"},
            "operations": {"request_id", "task_id", "plan_version", "idempotency_key", "request_fingerprint", "owner", "generation", "claim_generation", "guard_version", "stop_epoch", "state", "reservation_json", "resource_json"},
            "resource_holds": {"operation_id"},
            "observations": {"operation_id", "request_id", "payload_json", "fingerprint"},
            "stop_reasons": {"reason", "stop_epoch"},
            "outbox": {"event_type", "payload_json"},
        }
        for table, required_fields in required_notnull.items():
            notnull = {row[1] for row in self.db.execute(f"PRAGMA table_info({table})") if row[3]}
            if not required_fields.issubset(notnull):
                raise AtomicLedgerError("E_SCHEMA_INVALID", (f"not_null:{table}",))
        def table_sql(name: str) -> str:
            row = self.db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
            return re.sub(r"\s+", "", str(row[0] or "")).lower() if row else ""
        checks = {
            "atomic_meta": ("check(singleton=1)", "check(schema_version=2)"),
            "controller": ("check(singleton=1)", "check(generation>=1)"),
            "requests": ("check(max_concurrency>0)", "check(stoppedin(0,1))", "check(stop_epoch>=0)"),
            "tasks": ("check(guard_version>=1)", "check(max_attempts>=1)"),
            "operations": ("check(plan_version>=1)", "check(generation>=1)", "check(claim_generation>=1)", "check(guard_version>=1)", "check(stop_epoch>=0)", "check(statein('claimed','handoff_accepted','finished','cancelled_not_started','start_unknown'))"),
            "stop_reasons": ("check(stop_epoch>=1)",),
        }
        for table, needles in checks.items():
            sql = table_sql(table)
            if any(needle not in sql for needle in needles):
                raise AtomicLedgerError("E_SCHEMA_INVALID", (f"checks:{table}",))
        fk_expectations = {
            "policies": {("requests", "request_id", "request_id")},
            "tasks": {("requests", "request_id", "request_id")},
            "operations": {("tasks", "request_id", "request_id"), ("tasks", "task_id", "task_id")},
            "resource_holds": {("operations", "operation_id", "operation_id")},
            "observations": {("operations", "operation_id", "operation_id"), ("requests", "request_id", "request_id")},
            "stop_reasons": {("requests", "request_id", "request_id")},
        }
        for table, expected_fk in fk_expectations.items():
            actual_fk = {(row[2], row[3], row[4]) for row in self.db.execute(f"PRAGMA foreign_key_list({table})")}
            if not expected_fk.issubset(actual_fk):
                raise AtomicLedgerError("E_SCHEMA_INVALID", (f"foreign_keys:{table}",))
        trigger_names = {row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        if not {"atomic_observation_immutable_update", "atomic_observation_immutable_delete"}.issubset(trigger_names):
            raise AtomicLedgerError("E_SCHEMA_INVALID", ("immutable_observations",))
        trigger_sql = {
            row[0]: re.sub(r"\s+", "", str(row[1] or "")).lower()
            for row in self.db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'")
        }
        if ("beforeupdateonobservations" not in trigger_sql["atomic_observation_immutable_update"]
                or "raise(abort" not in trigger_sql["atomic_observation_immutable_update"]
                or "beforedeleteonobservations" not in trigger_sql["atomic_observation_immutable_delete"]
                or "raise(abort" not in trigger_sql["atomic_observation_immutable_delete"]):
            raise AtomicLedgerError("E_SCHEMA_INVALID", ("immutable_observations",))
        if self.db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise AtomicLedgerError("E_SCHEMA_INVALID", ("foreign_key_integrity",))
        meta = self.db.execute("SELECT schema_version FROM atomic_meta WHERE singleton=1").fetchone()
        if meta is None or type(meta[0]) is not int or meta[0] != 2:
            raise AtomicLedgerError("E_SCHEMA_VERSION")
        controller = self.db.execute("SELECT generation FROM controller WHERE singleton=1").fetchone()
        if controller is None or type(controller[0]) is not int or controller[0] < 1:
            raise AtomicLedgerError("E_SCHEMA_INVALID", ("controller",))
        active_index = next((row for row in self.db.execute("PRAGMA index_list(operations)") if row[1] == "one_active_task_v2"), None)
        if active_index is None or active_index[2] != 1 or active_index[4] != 1:
            raise AtomicLedgerError("E_SCHEMA_INVALID", ("active_task_index",))
        active_columns = tuple(row[2] for row in self.db.execute("PRAGMA index_info(one_active_task_v2)"))
        active_sql_row = self.db.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='one_active_task_v2'").fetchone()
        active_sql = re.sub(r"\s+", "", str(active_sql_row[0] or "")).lower() if active_sql_row else ""
        if active_columns != ("request_id", "task_id") or active_sql.split("where", 1)[-1] != "statein('claimed','handoff_accepted','start_unknown')":
            raise AtomicLedgerError("E_SCHEMA_INVALID", ("active_task_index",))
        idem_index_ok = False
        for row in self.db.execute("PRAGMA index_list(operations)"):
            if row[2] == 1 and row[4] == 0 and tuple(item[2] for item in self.db.execute("SELECT * FROM pragma_index_info(?)", (row[1],))) == ("request_id", "idempotency_key"):
                idem_index_ok = True
                break
        if not idem_index_ok:
            raise AtomicLedgerError("E_SCHEMA_INVALID", ("idempotency_index",))
        self._validate_persisted_rows()

    def _validate_persisted_rows(self) -> None:
        """Reject tampered or partially written rows before serving the ledger.

        SQLite checks protect the shape of future writes, but an operator can
        still reopen a file whose JSON or cross-table facts were edited.  Such
        a file must enter the recovery boundary at open rather than failing
        later with a raw decoder or budget exception.
        """
        try:
            requests = {row["request_id"]: row for row in self.db.execute("SELECT * FROM requests")}
            policies = {row["request_id"]: row for row in self.db.execute("SELECT * FROM policies")}
            tasks = {(row["request_id"], row["task_id"]): row for row in self.db.execute("SELECT * FROM tasks")}
            if set(requests) != set(policies):
                raise ValueError("request_policy_mismatch")
            for request_id, row in requests.items():
                _text(request_id, "request_id")
                _text(row["repo_id"], "repo_id")
                _int(row["max_concurrency"], "max_concurrency", 1)
                _int(row["stopped"], "stopped", 0)
                if row["stopped"] not in (0, 1):
                    raise ValueError("stopped")
                _int(row["stop_epoch"], "stop_epoch", 0)
                if row["stop_reason"] is not None:
                    _text(row["stop_reason"], "stop_reason")
                _policy(policies[request_id]["policy_json"])
            for key, row in tasks.items():
                _text(key[0], "task.request_id")
                _text(key[1], "task_id")
                _int(row["guard_version"], "guard_version", 1)
                _int(row["max_attempts"], "max_attempts", 1)
            operations = {row["operation_id"]: row for row in self.db.execute("SELECT * FROM operations")}
            expected_holds: set[tuple[str, str, str]] = set()
            for operation_id, row in operations.items():
                if (row["request_id"], row["task_id"]) not in tasks:
                    raise ValueError("operation_task_mismatch")
                _text(operation_id, "operation_id")
                _text(row["request_id"], "operation.request_id")
                _text(row["task_id"], "operation.task_id")
                _int(row["plan_version"], "plan_version", 1)
                _text(row["idempotency_key"], "idempotency_key")
                _text(row["request_fingerprint"], "request_fingerprint")
                _text(row["owner"], "owner")
                _int(row["generation"], "generation", 1)
                _int(row["claim_generation"], "claim_generation", 1)
                _int(row["guard_version"], "guard_version", 1)
                _int(row["stop_epoch"], "stop_epoch", 0)
                if row["lease_until"] is not None:
                    _finite(row["lease_until"], "lease_until")
                if row["state"] not in {"CLAIMED", "HANDOFF_ACCEPTED", "FINISHED", "CANCELLED_NOT_STARTED", "START_UNKNOWN"}:
                    raise ValueError("operation_state")
                reservation = json.loads(row["reservation_json"])
                resource_keys = _resources(json.loads(row["resource_json"]))
                BudgetOperation(operation_id, row["request_id"], row["task_id"], reservation,
                                state=("cancelled_not_started" if row["state"] == "CANCELLED_NOT_STARTED" else ("unknown_liability" if row["state"] == "START_UNKNOWN" else "reserved")),
                                generation=row["claim_generation"], finished=row["state"] in ("CANCELLED_NOT_STARTED", "FINISHED", "START_UNKNOWN"))
                repo_id = requests[row["request_id"]]["repo_id"]
                if row["state"] in {"CLAIMED", "HANDOFF_ACCEPTED", "START_UNKNOWN"}:
                    expected_holds.update((repo_id, key, operation_id) for key in resource_keys)
            actual_holds = {(row["repo_id"], row["resource_key"], row["operation_id"])
                            for row in self.db.execute("SELECT repo_id,resource_key,operation_id FROM resource_holds")}
            if actual_holds != expected_holds:
                raise ValueError("resource_hold_mismatch")
            for row in self.db.execute("SELECT * FROM observations"):
                operation = operations.get(row["operation_id"])
                if operation is None or operation["request_id"] != row["request_id"]:
                    raise ValueError("observation_scope_mismatch")
                observation = _observation_from_payload(json.loads(row["payload_json"]))
                if observation.observation_id != row["observation_id"] or observation.operation_id != row["operation_id"]:
                    raise ValueError("observation_identity_mismatch")
                if stable_observation_fingerprint(observation) != row["fingerprint"]:
                    raise ValueError("observation_fingerprint_mismatch")
            for row in self.db.execute("SELECT request_id,reason,stop_epoch FROM stop_reasons"):
                request = requests.get(row["request_id"])
                if request is None or not request["stopped"] or row["stop_epoch"] > request["stop_epoch"]:
                    raise ValueError("stop_reason_mismatch")
                _text(row["reason"], "stop_reason")
                _int(row["stop_epoch"], "stop_epoch", 1)
            for row in self.db.execute("SELECT seq,event_type,payload_json FROM outbox"):
                _int(row["seq"], "outbox.seq", 1)
                _text(row["event_type"], "outbox.event_type")
                payload = json.loads(row["payload_json"])
                if type(payload) is not dict:
                    raise ValueError("outbox_payload")
        except AtomicLedgerError as exc:
            raise AtomicLedgerError("E_SCHEMA_INVALID", ("persisted_rows", exc.code)) from exc
        except (BaseException,) as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise AtomicLedgerError("E_SCHEMA_INVALID", ("persisted_rows",)) from exc

    def _emit(self, request_id: str | None, operation_id: str | None, event: str, payload: Mapping[str, Any]) -> None:
        self.db.execute("INSERT INTO outbox(request_id,operation_id,event_type,payload_json) VALUES(?,?,?,?)", (request_id, operation_id, event, _json(dict(payload))))

    def seed(self, request_id: str, repo_id: str, policy: BudgetPolicy, *, max_concurrency: int = 1) -> None:
        _text(request_id, "request_id"); _text(repo_id, "repo_id"); _int(max_concurrency, "max_concurrency", 1)
        if type(policy) is not BudgetPolicy:
            raise AtomicLedgerError("E_SCHEMA_TYPE", ("policy",))
        encoded = _json(_policy_payload(policy))
        with self._tx():
            if self.db.execute("SELECT 1 FROM requests WHERE request_id=?", (request_id,)).fetchone() is not None:
                old = self.db.execute("SELECT policy_json FROM policies WHERE request_id=?", (request_id,)).fetchone()
                old_request = self.db.execute("SELECT repo_id,max_concurrency FROM requests WHERE request_id=?", (request_id,)).fetchone()
                if old is not None and old[0] == encoded and old_request is not None and old_request[0] == repo_id and old_request[1] == max_concurrency:
                    return
                raise AtomicLedgerError("E_SCOPE_CONFLICT")
            self.db.execute("INSERT INTO requests(request_id,repo_id,max_concurrency) VALUES(?,?,?)", (request_id, repo_id, max_concurrency))
            self.db.execute("INSERT INTO policies(request_id,policy_json) VALUES(?,?)", (request_id, encoded))
            self._emit(request_id, None, "atomic.seeded", {"request_id": request_id, "repo_id": repo_id})

    def add_task(self, request_id: str, task_id: str, *, guard_version: int = 1, max_attempts: int = 3) -> None:
        _text(request_id, "request_id"); _text(task_id, "task_id"); _int(guard_version, "guard_version", 1); _int(max_attempts, "max_attempts", 1)
        with self._tx():
            if self.db.execute("SELECT 1 FROM requests WHERE request_id=?", (request_id,)).fetchone() is None:
                raise AtomicLedgerError("E_SCOPE_UNKNOWN")
            try:
                self.db.execute("INSERT INTO tasks(request_id,task_id,guard_version,max_attempts) VALUES(?,?,?,?)", (request_id, task_id, guard_version, max_attempts))
            except sqlite3.IntegrityError as exc:
                raise AtomicLedgerError("E_TASK_EXISTS") from exc

    def _state(self, request_id: str) -> BudgetState:
        policy = _policy(self.db.execute("SELECT policy_json FROM policies WHERE request_id=?", (request_id,)).fetchone()[0])
        ops = []
        for row in self.db.execute("SELECT * FROM operations WHERE request_id=? ORDER BY rowid", (request_id,)):
            row_state = row["state"]
            is_unknown = row_state == "START_UNKNOWN"
            ops.append(BudgetOperation(row["operation_id"], row["request_id"], row["task_id"], json.loads(row["reservation_json"]), state=("cancelled_not_started" if row_state == "CANCELLED_NOT_STARTED" else ("unknown_liability" if is_unknown else "reserved")), generation=row["claim_generation"], finished=row_state in ("CANCELLED_NOT_STARTED", "FINISHED", "START_UNKNOWN"), cancellation_conflict=is_unknown))
        observations = tuple(_observation_from_payload(json.loads(row[0])) for row in self.db.execute("SELECT payload_json FROM observations WHERE request_id=? ORDER BY rowid", (request_id,)))
        request = self.db.execute("SELECT stop_epoch FROM requests WHERE request_id=?", (request_id,)).fetchone()
        reasons = tuple(row[0] for row in self.db.execute("SELECT reason FROM stop_reasons WHERE request_id=? ORDER BY rowid", (request_id,)))
        if not reasons:
            reasons = tuple(row[0] for row in self.db.execute("SELECT stop_reason FROM requests WHERE request_id=? AND stopped=1 AND stop_reason IS NOT NULL", (request_id,)))
        state = BudgetState(policy)._evolve(operations=tuple(ops), request_id=request_id)
        # Replay through the same reducer so cancellation conflicts, corrections
        # and unknown liabilities survive reload; raw rows alone lose flags.
        for observation in observations:
            state, _ = state.record_usage_observation(observation)
        # Sequence is a database-wide outbox high-water mark.  A request-local
        # max would let two consumers observe the same cursor value while
        # events for another request were committed between their reads.
        return state._evolve(stop_reasons=reasons, stop_epoch=request[0], sequence=self.db.execute("SELECT COALESCE(MAX(seq),0) FROM outbox").fetchone()[0])

    def claim(self, request: ClaimRequest, facts: ClaimFacts, *, owner: str, reservation: Mapping[str, int], resource_keys: list[str], lease_until: float | None = None) -> AtomicClaimResult:
        if not isinstance(request, ClaimRequest) or not isinstance(facts, ClaimFacts):
            raise AtomicLedgerError("E_SCHEMA_TYPE", ("claim",))
        _text(owner, "owner"); resources = _resources(resource_keys); _int(request.controller_generation, "generation", 1)
        lease = None if lease_until is None else _finite(lease_until, "lease_until")
        try:
            gate = claim_decision(request, facts)
            reserve = dict(BudgetOperation("validation", request.request_id, request.task_id, reservation).reservation)
        except (ClaimModelError, ProtocolError, BudgetError) as exc:
            raise AtomicLedgerError("E_SCHEMA_TYPE", ("claim_facts",)) from exc
        with self._tx():
            root = self.db.execute("SELECT * FROM requests WHERE request_id=?", (request.request_id,)).fetchone()
            task = self.db.execute("SELECT * FROM tasks WHERE request_id=? AND task_id=?", (request.request_id, request.task_id)).fetchone()
            if root is None or task is None or root["repo_id"] != request.repo_id:
                raise AtomicLedgerError("E_SCOPE_UNKNOWN")
            generation = self.db.execute("SELECT generation FROM controller WHERE singleton=1").fetchone()[0]
            existing = self.db.execute("SELECT * FROM operations WHERE request_id=? AND idempotency_key=?", (request.request_id, request.idempotency_key)).fetchone()
            if existing is not None:
                if (existing["request_fingerprint"] == request.request_fingerprint
                        and existing["task_id"] == request.task_id
                        and existing["plan_version"] == request.plan_version
                        and existing["generation"] == request.controller_generation
                        and existing["claim_generation"] == request.controller_generation
                        and existing["guard_version"] == request.guard_version
                        and existing["stop_epoch"] == request.stop_epoch
                        and json.loads(existing["reservation_json"]) == reserve
                        and json.loads(existing["resource_json"]) == list(resources)):
                    return AtomicClaimResult(existing["operation_id"], existing["state"], True)
                raise AtomicLedgerError("E_IDEMPOTENCY_CONFLICT")
            if gate.decision != "CLAIMED":
                raise AtomicLedgerError("E_CLAIM_BLOCKED", gate.reasons)
            if root["stopped"] or generation != request.controller_generation or root["stop_epoch"] != request.stop_epoch or task["guard_version"] != request.guard_version:
                raise AtomicLedgerError("E_CLAIM_BLOCKED")
            if self.db.execute("SELECT COUNT(*) FROM operations WHERE request_id=? AND state IN('CLAIMED','HANDOFF_ACCEPTED','START_UNKNOWN')", (request.request_id,)).fetchone()[0] >= root["max_concurrency"]:
                raise AtomicLedgerError("E_CONCURRENCY")
            if self.db.execute("SELECT COUNT(*) FROM operations WHERE request_id=? AND task_id=?", (request.request_id, request.task_id)).fetchone()[0] >= task["max_attempts"]:
                raise AtomicLedgerError("E_ATTEMPTS")
            if self.db.execute("SELECT 1 FROM operations WHERE request_id=? AND task_id=? AND state IN('CLAIMED','HANDOFF_ACCEPTED','START_UNKNOWN')", (request.request_id, request.task_id)).fetchone() is not None:
                raise AtomicLedgerError("E_CLAIM_BLOCKED", ("active_task",))
            if any(self.db.execute("SELECT 1 FROM resource_holds WHERE repo_id=? AND resource_key=?", (request.repo_id, key)).fetchone() for key in resources):
                raise AtomicLedgerError("E_RESOURCE_BUSY")
            state = self._state(request.request_id)
            try:
                state, decision = state.reserve_for_operation("op-" + uuid.uuid4().hex, request.request_id, request.task_id, reservation, generation=request.controller_generation)
            except BudgetError as exc:
                raise AtomicLedgerError(exc.code, (str(exc),)) from None
            operation_id = state.operations[-1].operation_id
            try:
                self.db.execute("INSERT INTO operations(operation_id,request_id,task_id,plan_version,idempotency_key,request_fingerprint,owner,generation,claim_generation,guard_version,stop_epoch,lease_until,state,reservation_json,resource_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (operation_id, request.request_id, request.task_id, request.plan_version, request.idempotency_key, request.request_fingerprint, owner, request.controller_generation, request.controller_generation, request.guard_version, request.stop_epoch, lease, "CLAIMED", _json(dict(reservation)), _json(list(resources))))
            except sqlite3.IntegrityError as exc:
                raise AtomicLedgerError("E_CLAIM_BLOCKED", ("active_task",)) from exc
            for key in resources:
                self.db.execute("INSERT INTO resource_holds(repo_id,resource_key,operation_id) VALUES(?,?,?)", (request.repo_id, key, operation_id))
            self._emit(request.request_id, operation_id, "atomic.claimed", {"operation_id": operation_id, "reservation": dict(reservation), "resources": list(resources)})
            return AtomicClaimResult(operation_id, "CLAIMED")

    def handoff(self, operation_id: str, *, owner: str, now: float,
                budget_available: bool | None = None,
                resources_available: bool | None = None) -> AtomicClaimResult:
        """Record a guarded handoff; this never starts or inspects a process."""
        _text(operation_id, "operation_id")
        _text(owner, "owner")
        now_value = _finite(now, "now")
        with self._tx():
            row = self.db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            if row is None:
                raise AtomicLedgerError("E_SCOPE_UNKNOWN")
            if row["owner"] != owner:
                raise AtomicLedgerError("E_FENCED")
            root = self.db.execute("SELECT * FROM requests WHERE request_id=?", (row["request_id"],)).fetchone()
            task = self.db.execute("SELECT * FROM tasks WHERE request_id=? AND task_id=?", (row["request_id"], row["task_id"])).fetchone()
            current_generation = self.db.execute("SELECT generation FROM controller WHERE singleton=1").fetchone()[0]
            if root is None or task is None:
                raise AtomicLedgerError("E_SCOPE_UNKNOWN")
            lease_valid = row["lease_until"] is not None and now_value < float(row["lease_until"])
            guards_valid = (current_generation == row["generation"] == row["claim_generation"]
                            and not root["stopped"] and root["stop_epoch"] == row["stop_epoch"]
                            and task["guard_version"] == row["guard_version"])
            budget_state = self._state(row["request_id"])
            if budget_state.stop_decision()[0]:
                raise AtomicLedgerError("E_HANDOFF_BLOCKED", ("ledger_budget_stopped",))
            expected_resources = set(json.loads(row["resource_json"]))
            held_resources = {(item[0], item[1]) for item in self.db.execute(
                "SELECT repo_id,resource_key FROM resource_holds WHERE operation_id=?", (operation_id,))}
            if held_resources != {(root["repo_id"], key) for key in expected_resources}:
                raise AtomicLedgerError("E_HANDOFF_BLOCKED", ("ledger_resources_mismatch",))
            if row["state"] == "HANDOFF_ACCEPTED":
                if not guards_valid or not lease_valid:
                    raise AtomicLedgerError("E_HANDOFF_BLOCKED", ("handoff_replay_guard_stale",))
                return AtomicClaimResult(operation_id, row["state"], True)
            if row["state"] != "CLAIMED":
                raise AtomicLedgerError("E_HANDOFF_STATE")
            if current_generation != row["generation"] or row["claim_generation"] != current_generation:
                raise AtomicLedgerError("E_FENCED")
            if not guards_valid or not lease_valid:
                raise AtomicLedgerError("E_HANDOFF_BLOCKED", ("guard_or_lease_invalid",))
            if budget_available is not True:
                raise AtomicLedgerError("E_HANDOFF_BLOCKED", ("budget_unknown" if budget_available is None else "budget_unavailable",))
            if resources_available is not True:
                raise AtomicLedgerError("E_HANDOFF_BLOCKED", ("resources_unknown" if resources_available is None else "resources_unavailable",))
            self.db.execute("UPDATE operations SET state='HANDOFF_ACCEPTED' WHERE operation_id=?", (operation_id,))
            self._emit(row["request_id"], operation_id, "atomic.handoff_accepted", {"generation": current_generation})
            return AtomicClaimResult(operation_id, "HANDOFF_ACCEPTED")

    def mark_start_unknown(self, operation_id: str, *, owner: str, generation: int) -> AtomicClaimResult:
        """Retain all risk holds when the external start result is unknown."""
        _text(operation_id, "operation_id")
        _text(owner, "owner")
        _int(generation, "generation", 1)
        with self._tx():
            row = self.db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            if row is None:
                raise AtomicLedgerError("E_SCOPE_UNKNOWN")
            current_generation = self.db.execute("SELECT generation FROM controller WHERE singleton=1").fetchone()[0]
            if generation != current_generation or row["generation"] != generation or row["claim_generation"] != generation or row["owner"] != owner:
                raise AtomicLedgerError("E_FENCED")
            if row["state"] == "START_UNKNOWN":
                return AtomicClaimResult(operation_id, row["state"], True, ("RECOVERY_REQUIRED",))
            if row["state"] != "HANDOFF_ACCEPTED":
                raise AtomicLedgerError("E_START_UNKNOWN_STATE")
            try:
                expected_resources = set(json.loads(row["resource_json"]))
                root = self.db.execute("SELECT repo_id FROM requests WHERE request_id=?", (row["request_id"],)).fetchone()
                held_resources = {(item[0], item[1]) for item in self.db.execute(
                    "SELECT repo_id,resource_key FROM resource_holds WHERE operation_id=?", (operation_id,))}
                if root is None or held_resources != {(root[0], key) for key in expected_resources}:
                    raise AtomicLedgerError("E_START_UNKNOWN_BLOCKED", ("ledger_resources_mismatch",))
            except json.JSONDecodeError as exc:
                raise AtomicLedgerError("E_SCHEMA_INVALID", ("resource_json",)) from exc
            self.db.execute("UPDATE operations SET state='START_UNKNOWN' WHERE operation_id=?", (operation_id,))
            self.db.execute("UPDATE requests SET stopped=1, stop_epoch=MAX(stop_epoch,1), stop_reason=COALESCE(stop_reason,'RECOVERY_REQUIRED') WHERE request_id=?", (row["request_id"],))
            epoch = self.db.execute("SELECT stop_epoch FROM requests WHERE request_id=?", (row["request_id"],)).fetchone()[0]
            self.db.execute("INSERT OR IGNORE INTO stop_reasons(request_id,reason,stop_epoch) VALUES(?,?,?)", (row["request_id"], "RECOVERY_REQUIRED", epoch))
            self._emit(row["request_id"], operation_id, "atomic.start_unknown", {"generation": generation, "reason": "RECOVERY_REQUIRED"})
            return AtomicClaimResult(operation_id, "START_UNKNOWN", False, ("RECOVERY_REQUIRED",))

    def observe(self, observation: UsageObservation) -> AtomicClaimResult:
        if type(observation) is not UsageObservation:
            raise AtomicLedgerError("E_SCHEMA_TYPE", ("observation",))
        with self._tx():
            row = self.db.execute("SELECT request_id,state FROM operations WHERE operation_id=?", (observation.operation_id,)).fetchone()
            if row is None:
                raise AtomicLedgerError("E_SCOPE_UNKNOWN")
            request_id = row[0]; state = self._state(request_id)
            try:
                new_state, decision = state.record_usage_observation(observation)
            except BudgetError as exc:
                raise AtomicLedgerError(exc.code, (str(exc),)) from None
            if decision.replayed:
                return AtomicClaimResult(observation.operation_id, decision.status, True, decision.reasons)
            payload = _observation_payload(observation)
            self.db.execute("INSERT INTO observations(observation_id,operation_id,request_id,payload_json,fingerprint) VALUES(?,?,?,?,?)", (observation.observation_id, observation.operation_id, request_id, _json(payload), stable_observation_fingerprint(observation)))
            new_reasons = tuple(reason for reason in new_state.stop_reasons if reason not in state.stop_reasons)
            if new_reasons:
                already_stopped = self.db.execute("SELECT stopped FROM requests WHERE request_id=?", (request_id,)).fetchone()[0]
                if not already_stopped:
                    self.db.execute("UPDATE requests SET stopped=1,stop_epoch=MAX(stop_epoch,1),stop_reason=? WHERE request_id=?", (new_reasons[0], request_id))
                for reason in new_reasons:
                    self.db.execute("INSERT OR IGNORE INTO stop_reasons(request_id,reason,stop_epoch) VALUES(?,?,MAX((SELECT stop_epoch FROM requests WHERE request_id=?),1))", (request_id, reason, request_id))
                    self._emit(request_id, observation.operation_id, "atomic.stop_reason", {"reason": reason})
            # Financial closure says nothing about process exit, cleanup or
            # acceptance.  It never releases a resource or active-task slot.
            self._emit(request_id, observation.operation_id, "atomic.observed", {"observation_id": observation.observation_id, "status": decision.status, "reasons": list(decision.reasons)})
            return AtomicClaimResult(observation.operation_id, decision.status, False, decision.reasons)

    def cancel_unstarted(self, operation_id: str, *, owner: str, generation: int, not_started_proven: bool = False) -> AtomicClaimResult:
        _text(operation_id, "operation_id"); _text(owner, "owner"); _int(generation, "generation", 1)
        if not_started_proven is not True:
            raise AtomicLedgerError("E_RELEASE_NOT_PROVEN")
        with self._tx():
            row = self.db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            if row is None:
                raise AtomicLedgerError("E_SCOPE_UNKNOWN")
            current_generation = self.db.execute("SELECT generation FROM controller WHERE singleton=1").fetchone()[0]
            if row["owner"] != owner or not (current_generation == generation == row["generation"] == row["claim_generation"]):
                raise AtomicLedgerError("E_FENCED")
            if row["state"] == "CANCELLED_NOT_STARTED":
                return AtomicClaimResult(operation_id, row["state"], True)
            if row["owner"] != owner or row["generation"] != generation or row["state"] != "CLAIMED":
                raise AtomicLedgerError("E_FENCED")
            if self.db.execute("SELECT 1 FROM observations WHERE operation_id=?", (operation_id,)).fetchone() is not None:
                raise AtomicLedgerError("E_CANNOT_PROVE_UNSTARTED")
            self.db.execute("UPDATE operations SET state='CANCELLED_NOT_STARTED' WHERE operation_id=?", (operation_id,))
            self.db.execute("DELETE FROM resource_holds WHERE operation_id=?", (operation_id,))
            self._emit(row["request_id"], operation_id, "atomic.cancelled_unstarted", {})
            return AtomicClaimResult(operation_id, "CANCELLED_NOT_STARTED")

    def reconcile_not_started(self, operation_id: str, *, owner: str, generation: int,
                              not_started_proven: bool = False,
                              takeover_proven: bool = False) -> AtomicClaimResult:
        """Reconcile a fenced ``START_UNKNOWN`` after controller rollover.

        The store cannot inspect a process.  Callers must supply an explicit
        not-started fact; a new controller generation also needs an explicit
        takeover fact before the owner and fencing generation are replaced.
        """
        _text(operation_id, "operation_id")
        _text(owner, "owner")
        _int(generation, "generation", 1)
        if not_started_proven is not True:
            raise AtomicLedgerError("E_RELEASE_NOT_PROVEN")
        with self._tx():
            row = self.db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            if row is None:
                raise AtomicLedgerError("E_SCOPE_UNKNOWN")
            current_generation = self.db.execute("SELECT generation FROM controller WHERE singleton=1").fetchone()[0]
            if generation != current_generation:
                raise AtomicLedgerError("E_FENCED")
            if row["state"] == "CANCELLED_NOT_STARTED":
                if row["owner"] == owner and row["generation"] == generation:
                    return AtomicClaimResult(operation_id, row["state"], True)
                raise AtomicLedgerError("E_FENCED")
            if row["state"] != "START_UNKNOWN":
                raise AtomicLedgerError("E_RECOVERY_STATE")
            stale_owner = row["owner"] != owner or row["generation"] != generation or row["claim_generation"] != generation
            if stale_owner and takeover_proven is not True:
                raise AtomicLedgerError("E_FENCED")
            root = self.db.execute("SELECT stopped FROM requests WHERE request_id=?", (row["request_id"],)).fetchone()
            if root is None or not root[0]:
                raise AtomicLedgerError("E_RECOVERY_BLOCKED", ("request_not_stopped",))
            self.db.execute("UPDATE operations SET owner=?,generation=?,claim_generation=?,state='CANCELLED_NOT_STARTED' WHERE operation_id=?", (owner, generation, generation, operation_id))
            self.db.execute("DELETE FROM resource_holds WHERE operation_id=?", (operation_id,))
            self._emit(row["request_id"], operation_id, "atomic.reconciled_not_started", {"generation": generation, "takeover": stale_owner})
            return AtomicClaimResult(operation_id, "CANCELLED_NOT_STARTED", False, ("RECOVERY_RECONCILED",))

    def stop(self, request_id: str, reason: str = "OPERATOR_STOP") -> None:
        _text(request_id, "request_id"); _text(reason, "reason")
        with self._tx():
            row = self.db.execute("SELECT stopped FROM requests WHERE request_id=?", (request_id,)).fetchone()
            if row is None:
                raise AtomicLedgerError("E_SCOPE_UNKNOWN")
            if not row[0]:
                self.db.execute("UPDATE requests SET stopped=1,stop_epoch=stop_epoch+1,stop_reason=? WHERE request_id=?", (reason, request_id))
            epoch = self.db.execute("SELECT stop_epoch FROM requests WHERE request_id=?", (request_id,)).fetchone()[0]
            added = self.db.execute("INSERT OR IGNORE INTO stop_reasons(request_id,reason,stop_epoch) VALUES(?,?,?)", (request_id, reason, epoch)).rowcount
            if added:
                self._emit(request_id, None, "atomic.stopped", {"reason": reason})
            else:
                self._emit(request_id, None, "atomic.stop_already", {"reason": reason, "stop_epoch": epoch})

    def rollover(self) -> int:
        """Fence the current controller and stop open requests for recovery."""
        with self._tx():
            self.db.execute("UPDATE controller SET generation=generation+1 WHERE singleton=1")
            generation = self.db.execute("SELECT generation FROM controller WHERE singleton=1").fetchone()[0]
            self._emit(None, None, "atomic.controller_fenced", {"generation": generation})
            for row in self.db.execute("SELECT request_id FROM requests WHERE stopped=0").fetchall():
                request_id = row[0]
                self.db.execute("UPDATE requests SET stopped=1, stop_epoch=stop_epoch+1, stop_reason=COALESCE(stop_reason,'RECOVERY_REQUIRED') WHERE request_id=?", (request_id,))
                epoch = self.db.execute("SELECT stop_epoch FROM requests WHERE request_id=?", (request_id,)).fetchone()[0]
                self.db.execute("INSERT OR IGNORE INTO stop_reasons(request_id,reason,stop_epoch) VALUES(?,?,?)", (request_id, "RECOVERY_REQUIRED", epoch))
                self._emit(request_id, None, "atomic.request_recovery_required", {"generation": generation, "stop_epoch": epoch})
            return generation

    def finish_operation(self, operation_id: str, *, owner: str, generation: int,
                         cleanup_proven: bool = False) -> AtomicClaimResult:
        """Release runtime holds only after an explicit external cleanup proof."""
        _text(operation_id, "operation_id")
        _text(owner, "owner")
        _int(generation, "generation", 1)
        if cleanup_proven is not True:
            raise AtomicLedgerError("E_CLEANUP_NOT_PROVEN")
        with self._tx():
            row = self.db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            if row is None:
                raise AtomicLedgerError("E_SCOPE_UNKNOWN")
            current_generation = self.db.execute("SELECT generation FROM controller WHERE singleton=1").fetchone()[0]
            if row["owner"] != owner or not (current_generation == generation == row["generation"] == row["claim_generation"]):
                raise AtomicLedgerError("E_FENCED")
            if row["state"] == "FINISHED":
                return AtomicClaimResult(operation_id, row["state"], True)
            if row["state"] not in ("CLAIMED", "HANDOFF_ACCEPTED"):
                raise AtomicLedgerError("E_CLEANUP_BLOCKED")
            self.db.execute("UPDATE operations SET state='FINISHED' WHERE operation_id=?", (operation_id,))
            self.db.execute("DELETE FROM resource_holds WHERE operation_id=?", (operation_id,))
            self._emit(row["request_id"], operation_id, "atomic.finished", {"cleanup_proven": True})
            return AtomicClaimResult(operation_id, "FINISHED")

    def snapshot(self, request_id: str, task_id: str | None = None) -> BudgetSnapshot:
        _text(request_id, "request_id")
        # A single read transaction prevents a concurrent observation from
        # mixing pre-commit operations with post-commit totals and stop state.
        self.db.execute("BEGIN")
        try:
            if self.db.execute("SELECT 1 FROM requests WHERE request_id=?", (request_id,)).fetchone() is None:
                raise AtomicLedgerError("E_SCOPE_UNKNOWN")
            result = self._state(request_id).snapshot(task_id=task_id)
            self.db.execute("COMMIT")
            return result
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def outbox(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM outbox ORDER BY seq").fetchall()


__all__ = ["DDL", "AtomicClaimBudgetStore", "AtomicClaimResult", "AtomicLedgerError"]
