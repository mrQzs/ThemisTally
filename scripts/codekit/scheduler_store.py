#!/usr/bin/env python3
"""Restricted single-host SQLite ledger for the 07-T2C prototype.

This store demonstrates short transactional claim/handoff facts only.  It is
not a production scheduler: it does not authenticate callers, inspect Git or
processes, invoke Pi, or make an external launch atomic.  Callers must supply
the trusted facts consumed by :mod:`claim_model`.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator, Mapping, Optional, Sequence
import uuid

from .claim_model import (
    ACTIVE_TASK_STATES, ClaimFacts, ClaimReceipt, ClaimRequest, Decision,
    HandoffFacts, claim_decision, handoff_decision,
)


_DIMENSION_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}")
MAX_RESERVATION_DIMENSIONS = 64
MAX_RESOURCE_KEYS = 256
MAX_RESOURCE_JSON_BYTES = 16_384
_ACTIVE_SQL = tuple(sorted(ACTIVE_TASK_STATES))
_ACTIVE_WHERE_SQL = "'CLAIMED','ADMITTED','HANDOFF_ACCEPTED','STARTED','START_UNKNOWN','REVIEW_PENDING'"
_STATE_SQL = "'CLAIMED','ADMITTED','HANDOFF_ACCEPTED','STARTED','START_UNKNOWN','REVIEW_PENDING','ACCEPTED','REJECTED','CANCELLED_NOT_STARTED'"


DDL = f"""
CREATE TABLE IF NOT EXISTS controller (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    generation INTEGER NOT NULL CHECK(generation>=1)
);
CREATE TABLE IF NOT EXISTS scheduler_meta (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    schema_version INTEGER NOT NULL CHECK(schema_version=1)
);
INSERT OR IGNORE INTO scheduler_meta(singleton,schema_version) VALUES(1,1);
INSERT OR IGNORE INTO controller(singleton,generation) VALUES(1,1);
CREATE TABLE IF NOT EXISTS requests (
    request_id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    max_concurrency INTEGER NOT NULL CHECK(max_concurrency>0),
    stopped INTEGER NOT NULL DEFAULT 0 CHECK(stopped IN(0,1)),
    stop_epoch INTEGER NOT NULL DEFAULT 0 CHECK(stop_epoch>=0),
    stop_reason TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    request_id TEXT NOT NULL REFERENCES requests(request_id),
    task_id TEXT NOT NULL,
    guard_version INTEGER NOT NULL CHECK(guard_version>=1),
    max_attempts INTEGER NOT NULL CHECK(max_attempts>=1),
    PRIMARY KEY(request_id,task_id)
);
CREATE TABLE IF NOT EXISTS operations (
    operation_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    plan_version INTEGER NOT NULL CHECK(plan_version>=1),
    controller_generation INTEGER NOT NULL CHECK(controller_generation>=1),
    claim_generation INTEGER NOT NULL CHECK(claim_generation>=1),
    guard_version INTEGER NOT NULL CHECK(guard_version>=1),
    stop_epoch INTEGER NOT NULL CHECK(stop_epoch>=0),
    idempotency_key TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    owner TEXT NOT NULL,
    lease_until REAL NOT NULL,
    state TEXT NOT NULL CHECK(state IN({_STATE_SQL})),
    reservation_json TEXT NOT NULL,
    resource_json TEXT NOT NULL,
    FOREIGN KEY(request_id,task_id) REFERENCES tasks(request_id,task_id),
    UNIQUE(request_id,idempotency_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_task
ON operations(request_id,task_id)
WHERE state IN ('CLAIMED','ADMITTED','HANDOFF_ACCEPTED','STARTED','START_UNKNOWN','REVIEW_PENDING');
CREATE TABLE IF NOT EXISTS resource_holds (
    repo_id TEXT NOT NULL,
    resource_key TEXT NOT NULL,
    operation_id TEXT NOT NULL REFERENCES operations(operation_id),
    PRIMARY KEY(repo_id,resource_key)
);
CREATE TABLE IF NOT EXISTS outbox (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id TEXT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


class SchedulerStoreError(RuntimeError):
    """Expected prototype ledger rejection."""

    def __init__(self, code: str, reasons: Sequence[str] = ()) -> None:
        self.code = code
        self.reasons = tuple(reasons)
        super().__init__(f"{code}: {', '.join(self.reasons)}")


@dataclass(frozen=True)
class ClaimResult:
    operation_id: str
    state: str
    replayed: bool
    reasons: tuple[str, ...] = ()


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SchedulerStoreError("E_SCHEMA_TYPE", ("json",)) from exc


def _loads(value: Any) -> Any:
    if type(value) is not str:
        raise ValueError("json_text_required")
    return json.loads(value, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))


def _finite(value: object, field: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise SchedulerStoreError("E_SCHEMA_TYPE", (field,))
    try:
        converted = float(value)
    except (OverflowError, ValueError):
        raise SchedulerStoreError("E_SCHEMA_TYPE", (field,)) from None
    if not math.isfinite(converted):
        raise SchedulerStoreError("E_SCHEMA_TYPE", (field,))
    return converted


def _db_text(value: object, field: str, *, nullable: bool = False, limit: int = 512) -> None:
    if nullable and value is None:
        return
    if type(value) is not str or not value or len(value) > limit or "\x00" in value:
        raise SchedulerStoreError("E_SCHEMA_INVALID", (field,))
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise SchedulerStoreError("E_SCHEMA_INVALID", (field,))


def _input_text(value: object, field: str, *, limit: int = 512, code: str = "E_SCHEMA_TYPE") -> str:
    if type(value) is not str or not value or len(value) > limit or "\x00" in value:
        raise SchedulerStoreError(code, (field,))
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise SchedulerStoreError(code, (field,))
    return value


def _input_integer(value: object, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or isinstance(value, bool) or value < minimum or value > 2**53 - 1:
        raise SchedulerStoreError("E_SCHEMA_TYPE", (field,))
    return value


def _db_integer(value: object, field: str, *, minimum: int = 0) -> None:
    if type(value) is not int or isinstance(value, bool) or value < minimum or value > 2**53 - 1:
        raise SchedulerStoreError("E_SCHEMA_INVALID", (field,))


def _reservation(value: Mapping[str, int]) -> dict[str, int]:
    if not isinstance(value, Mapping) or not value:
        raise SchedulerStoreError("E_RESERVATION_SHAPE")
    result: dict[str, int] = {}
    for key, amount in value.items():
        if type(key) is not str or _DIMENSION_RE.fullmatch(key) is None:
            raise SchedulerStoreError("E_RESERVATION_DIMENSION")
        if type(amount) is not int or isinstance(amount, bool) or amount < 0:
            raise SchedulerStoreError("E_RESERVATION_AMOUNT")
        if amount > 2**53 - 1:
            raise SchedulerStoreError("E_RESERVATION_AMOUNT")
        result[key] = amount
    if len(result) > MAX_RESERVATION_DIMENSIONS:
        raise SchedulerStoreError("E_RESERVATION_SHAPE")
    if len(_json(result).encode("utf-8")) > MAX_RESOURCE_JSON_BYTES:
        raise SchedulerStoreError("E_RESERVATION_SHAPE")
    if result.get("dispatches") != 1:
        raise SchedulerStoreError("E_RESERVATION_DISPATCHES")
    return result


def _resources(value: Sequence[str]) -> tuple[str, ...]:
    if type(value) is not list:
        raise SchedulerStoreError("E_RESOURCE_KEYS")
    result = []
    for item in value:
        if (type(item) is not str or not item or len(item) > 200 or "\x00" in item
                or any(0xD800 <= ord(char) <= 0xDFFF for char in item)):
            raise SchedulerStoreError("E_RESOURCE_KEYS")
        result.append(item)
    if len(result) > MAX_RESOURCE_KEYS or len(_json(sorted(result)).encode("utf-8")) > MAX_RESOURCE_JSON_BYTES:
        raise SchedulerStoreError("E_RESOURCE_KEYS")
    if len(set(result)) != len(result):
        raise SchedulerStoreError("E_RESOURCE_KEYS")
    return tuple(sorted(result))


class SchedulerStore:
    """A deliberately narrow, synthetic ledger backed by one SQLite file."""

    def __init__(self, path: str | Path) -> None:
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=5.0)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        mode = str(self.db.execute("PRAGMA journal_mode=DELETE").fetchone()[0]).lower()
        if mode not in ("delete", "memory"):
            self.db.close()
            raise SchedulerStoreError("E_DB_MODE", (mode,))
        self.db.execute("PRAGMA synchronous=FULL")
        existing_objects = {
            row[0]: row[1] for row in self.db.execute(
                "SELECT name,type FROM sqlite_master"
            ) if not str(row[0]).startswith("sqlite_")
        }
        existing_tables = {name for name, kind in existing_objects.items() if kind == "table"}
        if existing_objects and "scheduler_meta" not in existing_tables:
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_MISSING")
        if "scheduler_meta" in existing_tables:
            # A version marker never authorizes bootstrapping a partial database.
            # A migration must be explicit and versioned; this prototype has no
            # migration path, so every required table must already exist.
            required_tables = {"scheduler_meta", "controller", "requests", "tasks",
                               "operations", "resource_holds", "outbox"}
            if not required_tables.issubset(existing_tables):
                self.db.close()
                raise SchedulerStoreError("E_SCHEMA_INVALID", ("missing_table",))
            meta = self.db.execute("SELECT schema_version FROM scheduler_meta WHERE singleton=1").fetchone()
            if meta is None or type(meta[0]) is not int or meta[0] != 1:
                self.db.close()
                raise SchedulerStoreError("E_SCHEMA_VERSION")
        # Only a genuinely empty file may be initialized.  Existing files are
        # validated in place so a rejected legacy/partial file is never
        # silently repaired by CREATE IF NOT EXISTS or INSERT OR IGNORE.
        if not existing_tables:
            self.db.executescript(DDL)
        self._validate_schema()

    def _validate_schema(self) -> None:
        required = {
            "scheduler_meta": {"singleton", "schema_version"},
            "controller": {"singleton", "generation"},
            "requests": {"request_id", "repo_id", "max_concurrency", "stopped", "stop_epoch", "stop_reason"},
            "tasks": {"request_id", "task_id", "guard_version", "max_attempts"},
            "operations": {"operation_id", "request_id", "task_id", "plan_version",
                            "controller_generation", "claim_generation", "guard_version", "stop_epoch",
                            "idempotency_key", "request_fingerprint", "owner", "lease_until", "state",
                            "reservation_json", "resource_json"},
            "resource_holds": {"repo_id", "resource_key", "operation_id"},
            "outbox": {"seq", "operation_id", "event_type", "payload_json"},
        }
        for table, fields in required.items():
            actual = {row[1] for row in self.db.execute(f"PRAGMA table_info({table})").fetchall()}
            if not fields.issubset(actual):
                self.db.close()
                raise SchedulerStoreError("E_SCHEMA_INVALID", (table,))
        # Check the constraints that carry the safety properties.  Column names
        # alone are insufficient: opening a same-column, unconstrained SQLite
        # file would silently remove fencing, referential integrity, and the
        # one-active-task invariant.
        def table_sql(name: str) -> str:
            row = self.db.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
            return str(row[0] or "").lower() if row else ""

        def pk(name: str, expected: Sequence[str]) -> bool:
            actual = [row[1] for row in sorted(self.db.execute(f"PRAGMA table_info({name})"), key=lambda item: item[5])
                      if row[5]]
            return actual == list(expected)

        if not pk("scheduler_meta", ("singleton",)) or not pk("controller", ("singleton",)):
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("primary_key",))
        if not pk("requests", ("request_id",)) or not pk("tasks", ("request_id", "task_id")):
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("scope_keys",))
        if not pk("operations", ("operation_id",)) or not pk("resource_holds", ("repo_id", "resource_key")):
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("operation_keys",))
        if not pk("outbox", ("seq",)):
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("outbox_key",))
        notnull = {
            table: {row[1] for row in self.db.execute(f"PRAGMA table_info({table})") if row[3]}
            for table in ("controller", "requests", "tasks", "operations", "resource_holds", "outbox")
        }
        required_notnull = {
            "controller": {"generation"},
            "requests": {"repo_id", "max_concurrency", "stopped", "stop_epoch"},
            "tasks": {"guard_version", "max_attempts"},
            "operations": {"request_id", "task_id", "plan_version", "controller_generation",
                            "claim_generation", "guard_version", "stop_epoch", "idempotency_key",
                            "request_fingerprint", "owner", "lease_until", "state", "reservation_json",
                            "resource_json"},
            "resource_holds": {"repo_id", "resource_key", "operation_id"},
            "outbox": {"event_type", "payload_json"},
        }
        if any(not required_notnull[table].issubset(notnull[table]) for table in required_notnull):
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("not_null",))
        request_sql = table_sql("requests")
        operation_sql = table_sql("operations")
        meta_sql = table_sql("scheduler_meta")
        controller_sql = table_sql("controller")
        task_sql = table_sql("tasks")
        checks = (
            (meta_sql, ("check(singleton=1)", "check(schema_version=1)")),
            (controller_sql, ("check(singleton=1)", "check(generation>=1)")),
            (request_sql, ("check(max_concurrency>0)", "check(stopped in(0,1))", "check(stop_epoch>=0)")),
            (task_sql, ("check(guard_version>=1)", "check(max_attempts>=1)")),
            (operation_sql, ("check(plan_version>=1)", "check(controller_generation>=1)",
                             "check(claim_generation>=1)", "check(guard_version>=1)", "check(stop_epoch>=0)")),
        )
        if any(needle not in sql for sql, needles in checks for needle in needles):
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("request_checks",))
        expected_state_check = re.sub(r"\s+", "", "check(state in(" + _STATE_SQL + "))").lower()
        compact_operation_sql = re.sub(r"\s+", "", operation_sql)
        if expected_state_check not in compact_operation_sql or "unique(request_id,idempotency_key)" not in compact_operation_sql:
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("operation_checks",))
        foreign_tables = {
            (row[2], row[3], row[4])
            for row in self.db.execute("PRAGMA foreign_key_list(tasks)")
        }
        if ("requests", "request_id", "request_id") not in foreign_tables:
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("task_foreign_key",))
        op_fks = {(row[2], row[3], row[4]) for row in self.db.execute("PRAGMA foreign_key_list(operations)")}
        if not {("tasks", "request_id", "request_id"), ("tasks", "task_id", "task_id")}.issubset(op_fks):
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("operation_foreign_key",))
        hold_fks = {(row[2], row[3], row[4]) for row in self.db.execute("PRAGMA foreign_key_list(resource_holds)")}
        if ("operations", "operation_id", "operation_id") not in hold_fks:
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("hold_foreign_key",))
        index_rows = self.db.execute("PRAGMA index_list(operations)").fetchall()
        if not any(row[1] == "one_active_task" and int(row[2]) == 1 and int(row[4] or 0) == 1
                   for row in index_rows):
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("active_task_index",))
        active_columns = [row[2] for row in self.db.execute("PRAGMA index_info(one_active_task)")]
        if active_columns != ["request_id", "task_id"]:
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("active_task_columns",))
        active_row = self.db.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='one_active_task'"
        ).fetchone()
        expected_active = "create unique index one_active_task on operations(request_id,task_id) where state in (" \
            + _ACTIVE_WHERE_SQL + ")"
        if active_row is None or re.sub(r"\s+", "", expected_active).lower() != re.sub(
                r"\s+", "", str(active_row[0]).lower()):
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("active_task_states",))
        idempotency_columns = []
        for row in index_rows:
            if int(row[2]) == 1:
                columns = [item[2] for item in self.db.execute(f"PRAGMA index_info({row[1]})")]
                if columns == ["request_id", "idempotency_key"]:
                    idempotency_columns = columns
                    break
        if idempotency_columns != ["request_id", "idempotency_key"]:
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("idempotency_index",))
        if self.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or self.db.execute(
                "PRAGMA foreign_key_check").fetchone() is not None:
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("integrity",))
        generation = self.db.execute("SELECT generation FROM controller WHERE singleton=1").fetchone()
        if generation is None or type(generation[0]) is not int or generation[0] < 1:
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("controller.generation",))
        _db_integer(generation[0], "controller.generation", minimum=1)
        try:
            requests = {row["request_id"]: row for row in self.db.execute("SELECT * FROM requests").fetchall()}
            tasks = {(row["request_id"], row["task_id"]): row for row in self.db.execute("SELECT * FROM tasks").fetchall()}
            expected_holds: set[tuple[str, str, str]] = set()
            operations = {}
            for row in self.db.execute("SELECT * FROM requests").fetchall():
                _db_text(row["request_id"], "requests.request_id")
                _db_text(row["repo_id"], "requests.repo_id")
                _db_integer(row["max_concurrency"], "requests.max_concurrency", minimum=1)
                if type(row["stopped"]) is not int or row["stopped"] not in (0, 1):
                    raise SchedulerStoreError("E_SCHEMA_INVALID", ("requests.stopped",))
                _db_integer(row["stop_epoch"], "requests.stop_epoch")
                _db_text(row["stop_reason"], "requests.stop_reason", nullable=True)
                if row["stopped"] == 1 and row["stop_reason"] is None:
                    raise SchedulerStoreError("E_SCHEMA_INVALID", ("requests.stop_reason",))
            for row in self.db.execute("SELECT * FROM tasks").fetchall():
                _db_text(row["request_id"], "tasks.request_id")
                _db_text(row["task_id"], "tasks.task_id")
                _db_integer(row["guard_version"], "tasks.guard_version", minimum=1)
                _db_integer(row["max_attempts"], "tasks.max_attempts", minimum=1)
            for row in self.db.execute("SELECT * FROM operations").fetchall():
                operations[row["operation_id"]] = row
                for column in ("operation_id", "request_id", "task_id", "idempotency_key",
                               "request_fingerprint", "owner"):
                    _db_text(row[column], f"operations.{column}")
                for column in ("plan_version", "controller_generation", "claim_generation", "guard_version"):
                    _db_integer(row[column], f"operations.{column}", minimum=1)
                _db_integer(row["stop_epoch"], "operations.stop_epoch")
                _finite(row["lease_until"], "operations.lease_until")
                if row["state"] not in _STATE_SQL.replace("'", "").split(","):
                    raise SchedulerStoreError("E_SCHEMA_INVALID", ("operations.state",))
                _db_text(row["reservation_json"], "operations.reservation_json")
                _db_text(row["resource_json"], "operations.resource_json")
                if len(row["reservation_json"]) > MAX_RESOURCE_JSON_BYTES or len(row["resource_json"]) > MAX_RESOURCE_JSON_BYTES:
                    raise SchedulerStoreError("E_SCHEMA_INVALID", ("operations.json_size",))
                reservation = _loads(row["reservation_json"])
                _reservation(reservation)
                resources = _loads(row["resource_json"])
                normalized_resources = _resources(resources)
                if row["controller_generation"] != row["claim_generation"]:
                    raise SchedulerStoreError("E_SCHEMA_INVALID", ("operations.generation",))
                if row["state"] in ACTIVE_TASK_STATES:
                    request = requests.get(row["request_id"])
                    task = tasks.get((row["request_id"], row["task_id"]))
                    if request is None or task is None:
                        raise SchedulerStoreError("E_SCHEMA_INVALID", ("operations.scope",))
                    expected_holds.update((request["repo_id"], resource, row["operation_id"])
                                          for resource in normalized_resources)
            for row in self.db.execute("SELECT * FROM resource_holds").fetchall():
                _db_text(row["repo_id"], "resource_holds.repo_id")
                _db_text(row["resource_key"], "resource_holds.resource_key", limit=200)
                _db_text(row["operation_id"], "resource_holds.operation_id")
                operation = operations.get(row["operation_id"])
                if operation is None or operation["state"] not in ACTIVE_TASK_STATES:
                    raise SchedulerStoreError("E_SCHEMA_INVALID", ("resource_holds.operation",))
                request = requests.get(operation["request_id"])
                if request is None or row["repo_id"] != request["repo_id"]:
                    raise SchedulerStoreError("E_SCHEMA_INVALID", ("resource_holds.repo",))
            actual_holds = {(row["repo_id"], row["resource_key"], row["operation_id"])
                            for row in self.db.execute("SELECT repo_id,resource_key,operation_id FROM resource_holds")}
            if actual_holds != expected_holds:
                raise SchedulerStoreError("E_SCHEMA_INVALID", ("resource_holds.mismatch",))
            for row in self.db.execute("SELECT * FROM outbox").fetchall():
                _db_integer(row["seq"], "outbox.seq", minimum=1)
                _db_text(row["operation_id"], "outbox.operation_id", nullable=True)
                _db_text(row["event_type"], "outbox.event_type")
                _db_text(row["payload_json"], "outbox.payload_json")
                if len(row["payload_json"]) > MAX_RESOURCE_JSON_BYTES:
                    raise SchedulerStoreError("E_SCHEMA_INVALID", ("outbox.payload_size",))
                if type(_loads(row["payload_json"])) is not dict:
                    raise SchedulerStoreError("E_SCHEMA_INVALID", ("outbox.payload_json",))
        except SchedulerStoreError:
            self.db.close()
            raise
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.db.close()
            raise SchedulerStoreError("E_SCHEMA_INVALID", ("row_values",)) from exc

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "SchedulerStore":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    @contextmanager
    def tx(self) -> Iterator[None]:
        try:
            self.db.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                raise SchedulerStoreError("E_BUSY") from exc
            raise
        try:
            yield
            try:
                self.db.execute("COMMIT")
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                    raise SchedulerStoreError("E_COMMIT_UNKNOWN") from exc
                raise
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def _emit(self, operation_id: Optional[str], event_type: str, payload: Mapping[str, Any]) -> None:
        self.db.execute("INSERT INTO outbox(operation_id,event_type,payload_json) VALUES(?,?,?)",
                        (operation_id, event_type, _json(dict(payload))))

    def _generation(self) -> int:
        return int(self.db.execute("SELECT generation FROM controller WHERE singleton=1").fetchone()[0])

    def _row(self, operation_id: str) -> sqlite3.Row:
        _input_text(operation_id, "operation_id")
        row = self.db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        if row is None:
            raise SchedulerStoreError("E_OPERATION_UNKNOWN")
        return row

    def _receipt(self, row: sqlite3.Row) -> ClaimReceipt:
        return ClaimReceipt(
            repo_id=str(self.db.execute("SELECT repo_id FROM requests WHERE request_id=?",
                                        (row["request_id"],)).fetchone()[0]),
            request_id=row["request_id"], task_id=row["task_id"], plan_version=row["plan_version"],
            operation_id=row["operation_id"], state=row["state"],
            controller_generation=row["controller_generation"], claim_generation=row["claim_generation"],
            guard_version=row["guard_version"], stop_epoch=row["stop_epoch"], owner=row["owner"],
            lease_until=float(row["lease_until"]), idempotency_key=row["idempotency_key"],
            request_fingerprint=row["request_fingerprint"],
        )

    def seed_request(self, request_id: str, repo_id: str, *, max_concurrency: int = 1) -> None:
        _input_text(request_id, "request_id")
        _input_text(repo_id, "repo_id")
        if type(max_concurrency) is not int or isinstance(max_concurrency, bool) or max_concurrency < 1 \
                or max_concurrency > 2**53 - 1:
            raise SchedulerStoreError("E_CONCURRENCY")
        with self.tx():
            try:
                self.db.execute("INSERT INTO requests(request_id,repo_id,max_concurrency) VALUES(?,?,?)",
                                (request_id, repo_id, max_concurrency))
            except sqlite3.IntegrityError as exc:
                raise SchedulerStoreError("E_REQUEST_EXISTS") from exc

    def seed_task(self, request_id: str, task_id: str, *, guard_version: int = 1,
                  max_attempts: int = 3) -> None:
        _input_text(request_id, "request_id")
        _input_text(task_id, "task_id")
        if (type(guard_version) is not int or isinstance(guard_version, bool) or guard_version < 1
                or guard_version > 2**53 - 1 or type(max_attempts) is not int
                or isinstance(max_attempts, bool) or max_attempts < 1 or max_attempts > 2**53 - 1):
            raise SchedulerStoreError("E_TASK_SHAPE")
        with self.tx():
            if self.db.execute("SELECT 1 FROM requests WHERE request_id=?", (request_id,)).fetchone() is None:
                raise SchedulerStoreError("E_SCOPE_UNKNOWN")
            try:
                self.db.execute("INSERT INTO tasks(request_id,task_id,guard_version,max_attempts) VALUES(?,?,?,?)",
                                (request_id, task_id, guard_version, max_attempts))
            except sqlite3.IntegrityError as exc:
                raise SchedulerStoreError("E_TASK_EXISTS") from exc

    def _active_operations(self, request_id: str, task_id: str) -> list[Any]:
        rows = self.db.execute(
            "SELECT o.*, r.repo_id FROM operations o JOIN requests r USING(request_id) "
            "WHERE o.request_id=? AND o.task_id=? AND o.state IN "
            "('CLAIMED','ADMITTED','HANDOFF_ACCEPTED','STARTED','START_UNKNOWN','REVIEW_PENDING')",
            (request_id, task_id)).fetchall()
        from .claim_model import ActiveOperation
        return [ActiveOperation(row["repo_id"], row["request_id"], row["task_id"], row["plan_version"],
                                row["operation_id"], row["state"]) for row in rows]

    def claim(self, request: ClaimRequest, facts: ClaimFacts, *, owner: str, lease_until: float,
              reservation: Mapping[str, int], resource_keys: list[str], fail_before_commit: bool = False) -> ClaimResult:
        if not isinstance(request, ClaimRequest) or not isinstance(facts, ClaimFacts):
            raise SchedulerStoreError("E_SCHEMA_TYPE", ("claim_facts",))
        for field in ("repo_id", "request_id", "task_id", "idempotency_key", "request_fingerprint"):
            _input_text(getattr(request, field), f"request.{field}")
        _input_integer(request.plan_version, "request.plan_version", minimum=1)
        _input_integer(request.controller_generation, "request.controller_generation", minimum=1)
        _input_integer(request.guard_version, "request.guard_version", minimum=1)
        _input_integer(request.stop_epoch, "request.stop_epoch")
        _input_text(owner, "owner", limit=200, code="E_OWNER")
        lease = _finite(lease_until, "lease_until")
        reserve = _reservation(reservation)
        resources = _resources(resource_keys)
        with self.tx():
            root = self.db.execute("SELECT * FROM requests WHERE request_id=?", (request.request_id,)).fetchone()
            task = self.db.execute("SELECT * FROM tasks WHERE request_id=? AND task_id=?",
                                   (request.request_id, request.task_id)).fetchone()
            if root is None or task is None or root["repo_id"] != request.repo_id:
                raise SchedulerStoreError("E_SCOPE_UNKNOWN")
            existing_row = self.db.execute(
                "SELECT o.*, r.repo_id FROM operations o JOIN requests r USING(request_id) "
                "WHERE o.request_id=? AND o.idempotency_key=?",
                (request.request_id, request.idempotency_key)).fetchone()
            existing = self._receipt(existing_row) if existing_row is not None else None
            current_generation = self._generation()
            effective_facts = ClaimFacts(
                request_open=not bool(root["stopped"]), stop_requested=bool(root["stopped"]),
                controller_generation=current_generation, guard_version=task["guard_version"],
                stop_epoch=root["stop_epoch"], contract_valid=facts.contract_valid,
                baseline_valid=facts.baseline_valid, upstream_accepted=facts.upstream_accepted,
                resources_available=facts.resources_available, budget_available=facts.budget_available,
            )
            if existing_row is not None:
                if (existing_row["task_id"] != request.task_id
                        or existing_row["plan_version"] != request.plan_version
                        or existing_row["guard_version"] != request.guard_version
                        or existing_row["controller_generation"] != request.controller_generation
                        or existing_row["stop_epoch"] != request.stop_epoch
                        or existing_row["reservation_json"] != _json(reserve)
                        or existing_row["resource_json"] != _json(list(resources))):
                    raise SchedulerStoreError("E_IDEMPOTENCY_CONFLICT", ("claim_payload_mismatch",))
            decision = claim_decision(request, effective_facts,
                                      self._active_operations(request.request_id, request.task_id), existing)
            if decision.decision == "REPLAY":
                return ClaimResult(decision.operation_id or "", existing.state if existing else "", True)
            if decision.decision == "CONFLICT":
                raise SchedulerStoreError("E_IDEMPOTENCY_CONFLICT", decision.reasons)
            if decision.decision != "CLAIMED":
                raise SchedulerStoreError("E_CLAIM_BLOCKED", decision.reasons)
            if current_generation != request.controller_generation:
                raise SchedulerStoreError("E_FENCED")
            if root["stopped"]:
                raise SchedulerStoreError("E_STOPPED")
            if task["guard_version"] != request.guard_version:
                raise SchedulerStoreError("E_GUARD_STALE")
            active_count = self.db.execute(
                "SELECT COUNT(*) FROM operations WHERE request_id=? AND state IN "
                "('CLAIMED','ADMITTED','HANDOFF_ACCEPTED','STARTED','START_UNKNOWN','REVIEW_PENDING')",
                (request.request_id,)).fetchone()[0]
            if active_count >= root["max_concurrency"]:
                raise SchedulerStoreError("E_CONCURRENCY")
            attempts = self.db.execute("SELECT COUNT(*) FROM operations WHERE request_id=? AND task_id=?",
                                       (request.request_id, request.task_id)).fetchone()[0]
            if attempts >= task["max_attempts"]:
                raise SchedulerStoreError("E_ATTEMPTS")
            for resource in resources:
                if self.db.execute("SELECT 1 FROM resource_holds WHERE repo_id=? AND resource_key=?",
                                   (request.repo_id, resource)).fetchone() is not None:
                    raise SchedulerStoreError("E_RESOURCE_BUSY", (resource,))
            operation_id = "op-" + uuid.uuid4().hex
            try:
                self.db.execute(
                    "INSERT INTO operations(operation_id,request_id,task_id,plan_version,controller_generation,"
                    "claim_generation,guard_version,stop_epoch,idempotency_key,request_fingerprint,owner,lease_until,"
                    "state,reservation_json,resource_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (operation_id, request.request_id, request.task_id, request.plan_version,
                     request.controller_generation, request.controller_generation, request.guard_version,
                     request.stop_epoch, request.idempotency_key, request.request_fingerprint, owner, lease,
                     "CLAIMED", _json(reserve), _json(list(resources))))
            except sqlite3.IntegrityError as exc:
                raise SchedulerStoreError("E_ACTIVE_TASK") from exc
            for resource in resources:
                self.db.execute("INSERT INTO resource_holds(repo_id,resource_key,operation_id) VALUES(?,?,?)",
                                (request.repo_id, resource, operation_id))
            self._emit(operation_id, "scheduler.claimed", {
                "request_id": request.request_id, "task_id": request.task_id,
                "plan_version": request.plan_version, "resources": list(resources), "reservation": reserve,
                "controller_generation": request.controller_generation, "guard_version": request.guard_version,
                "stop_epoch": request.stop_epoch, "idempotency_key": request.idempotency_key,
                "request_fingerprint": request.request_fingerprint, "owner": owner, "lease_until": lease,
            })
            if fail_before_commit:
                raise SchedulerStoreError("E_SYNTHETIC_FAILPOINT")
            return ClaimResult(operation_id, "CLAIMED", False)

    def handoff(self, operation_id: str, *, owner: str, now: float,
                budget_available: Optional[bool] = None,
                resources_available: Optional[bool] = None) -> ClaimResult:
        _input_text(operation_id, "operation_id")
        _input_text(owner, "owner", limit=200, code="E_OWNER")
        now_value = _finite(now, "now")
        with self.tx():
            row = self._row(operation_id)
            if row["owner"] != owner:
                raise SchedulerStoreError("E_FENCED")
            if row["state"] not in ("CLAIMED", "ADMITTED"):
                if row["state"] == "HANDOFF_ACCEPTED":
                    current_generation = self._generation()
                    root = self.db.execute("SELECT * FROM requests WHERE request_id=?", (row["request_id"],)).fetchone()
                    task = self.db.execute("SELECT * FROM tasks WHERE request_id=? AND task_id=?",
                                           (row["request_id"], row["task_id"])).fetchone()
                    if (root is None or task is None or current_generation != row["controller_generation"]
                            or root["stopped"] or root["stop_epoch"] != row["stop_epoch"]
                            or task["guard_version"] != row["guard_version"]
                            or now_value >= float(row["lease_until"])):
                        raise SchedulerStoreError("E_HANDOFF_BLOCKED", ("handoff_replay_guard_stale",))
                    return ClaimResult(operation_id, row["state"], True)
                raise SchedulerStoreError("E_HANDOFF_STATE")
            root = self.db.execute("SELECT * FROM requests WHERE request_id=?", (row["request_id"],)).fetchone()
            task = self.db.execute("SELECT * FROM tasks WHERE request_id=? AND task_id=?",
                                   (row["request_id"], row["task_id"])).fetchone()
            current_generation = self._generation()
            facts = HandoffFacts(
                request_open=not bool(root["stopped"]), stop_requested=bool(root["stopped"]),
                controller_generation=current_generation, claim_generation=row["claim_generation"],
                guard_version=task["guard_version"], stop_epoch=root["stop_epoch"],
                lease_valid=now_value < float(row["lease_until"]),
                budget_available=budget_available, resources_available=resources_available,
            )
            decision = handoff_decision(self._receipt(row), facts)
            if decision.decision != "HANDOFF_ACCEPTED":
                raise SchedulerStoreError("E_HANDOFF_BLOCKED", decision.reasons)
            self.db.execute("UPDATE operations SET state='HANDOFF_ACCEPTED' WHERE operation_id=?", (operation_id,))
            self._emit(operation_id, "scheduler.handoff_accepted", {"controller_generation": current_generation})
            return ClaimResult(operation_id, "HANDOFF_ACCEPTED", False)

    def cancel_unstarted(self, operation_id: str, *, owner: str, generation: int) -> ClaimResult:
        _input_text(operation_id, "operation_id")
        _input_text(owner, "owner", limit=200, code="E_OWNER")
        with self.tx():
            if type(generation) is not int or generation != self._generation():
                raise SchedulerStoreError("E_FENCED")
            row = self._row(operation_id)
            if row["owner"] != owner:
                raise SchedulerStoreError("E_FENCED")
            if row["controller_generation"] != generation:
                raise SchedulerStoreError("E_FENCED")
            if row["state"] == "CANCELLED_NOT_STARTED":
                return ClaimResult(operation_id, row["state"], True)
            if row["state"] != "CLAIMED":
                raise SchedulerStoreError("E_CANNOT_PROVE_UNSTARTED")
            if self.db.execute("SELECT 1 FROM outbox WHERE operation_id=? AND event_type=?",
                               (operation_id, "scheduler.handoff_accepted")).fetchone() is not None:
                raise SchedulerStoreError("E_CANNOT_PROVE_UNSTARTED")
            self.db.execute("UPDATE operations SET state='CANCELLED_NOT_STARTED' WHERE operation_id=?",
                            (operation_id,))
            self.db.execute("DELETE FROM resource_holds WHERE operation_id=?", (operation_id,))
            self._emit(operation_id, "scheduler.cancelled_before_handoff", {})
            return ClaimResult(operation_id, "CANCELLED_NOT_STARTED", False)

    def rollover(self) -> int:
        with self.tx():
            self.db.execute("UPDATE controller SET generation=generation+1 WHERE singleton=1")
            generation = self._generation()
            self._emit(None, "controller.fenced", {"generation": generation})
            for row in self.db.execute("SELECT request_id FROM requests WHERE stopped=0").fetchall():
                self.db.execute("UPDATE requests SET stopped=1, stop_epoch=stop_epoch+1, "
                                "stop_reason=COALESCE(stop_reason, 'RECOVERY_REQUIRED') WHERE request_id=?",
                                (row["request_id"],))
                self._emit(None, "request.recovery_required", {"request_id": row["request_id"],
                                                                 "generation": generation})
            return generation

    def stop(self, request_id: str, reason: str = "OPERATOR_STOP") -> None:
        _input_text(request_id, "request_id")
        _input_text(reason, "stop_reason", limit=200, code="E_STOP_REASON")
        with self.tx():
            row = self.db.execute("SELECT stopped,stop_epoch,stop_reason FROM requests WHERE request_id=?",
                                  (request_id,)).fetchone()
            if row is None:
                raise SchedulerStoreError("E_SCOPE_UNKNOWN")
            if row["stopped"]:
                self._emit(None, "request.stop_already", {
                    "request_id": request_id, "reason": row["stop_reason"],
                    "requested_reason": reason, "stop_epoch": row["stop_epoch"],
                })
                return
            self.db.execute("UPDATE requests SET stopped=1, stop_epoch=stop_epoch+1, stop_reason=? "
                            "WHERE request_id=? AND stopped=0", (reason, request_id))
            self._emit(None, "request.stopped", {
                "request_id": request_id, "reason": reason, "stop_epoch": row["stop_epoch"] + 1,
            })

    def operation(self, operation_id: str) -> sqlite3.Row:
        return self._row(operation_id)

    def outbox(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM outbox ORDER BY seq").fetchall()


__all__ = ["ClaimResult", "DDL", "SchedulerStore", "SchedulerStoreError"]
