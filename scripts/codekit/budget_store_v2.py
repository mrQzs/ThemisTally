"""Durable, restricted T3A budget ledger.

This module is an intentionally small adapter around :mod:`codekit.budget`.
It persists the immutable facts and the derived current projection in one
SQLite transaction.  It does not call providers, inspect processes or
worktrees, and it is not wired into ``SchedulerStore``.  Callers must supply
the already validated ``BudgetPolicy`` and ``UsageObservation`` value objects.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator, Mapping, Optional

from .budget import (
    BudgetError, BudgetOperation, BudgetPolicy, BudgetSnapshot, BudgetState,
    UsageObservation, _current, stable_observation_fingerprint,
)
from .protocols import MAX_SAFE_INTEGER


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_MAX_JSON = 1 << 20


class BudgetStoreError(RuntimeError):
    """Expected rejection from the durable prototype ledger."""

    def __init__(self, code: str, reasons: tuple[str, ...] = ()) -> None:
        self.code = code
        self.reasons = tuple(reasons)
        super().__init__(f"{code}: {', '.join(self.reasons)}")


@dataclass(frozen=True)
class BudgetResult:
    operation_id: str | None
    status: str
    replayed: bool = False
    historical: bool = False
    reasons: tuple[str, ...] = ()


def _text(value: Any, field: str, *, nullable: bool = False, limit: int = 512) -> Optional[str]:
    if nullable and value is None:
        return None
    if type(value) is not str or not value or len(value) > limit or "\x00" in value:
        raise BudgetStoreError("E_SCHEMA_TYPE", (field,))
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise BudgetStoreError("E_SCHEMA_TYPE", (field,))
    if limit <= 128 and _ID.fullmatch(value) is None:
        raise BudgetStoreError("E_SCHEMA_TYPE", (field,))
    return value


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or isinstance(value, bool) or value < minimum or value > MAX_SAFE_INTEGER:
        raise BudgetStoreError("E_SCHEMA_TYPE", (field,))
    return value


def _json(value: Any) -> str:
    try:
        result = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise BudgetStoreError("E_SCHEMA_TYPE", ("json",)) from exc
    if len(result.encode("utf-8")) > _MAX_JSON:
        raise BudgetStoreError("E_SCHEMA_SIZE", ("json",))
    return result


def _decode_json(value: Any, field: str) -> Any:
    _text(value, field, limit=_MAX_JSON)
    try:
        return json.loads(value)
    except (TypeError, ValueError) as exc:
        raise BudgetStoreError("E_SCHEMA_INVALID", (field,)) from exc


def _policy_payload(policy: BudgetPolicy) -> dict[str, Any]:
    if type(policy) is not BudgetPolicy:
        raise BudgetStoreError("E_SCHEMA_TYPE", ("policy",))
    return {
        "limits": dict(policy.limits),
        "task_limits": {task: dict(limits) for task, limits in policy.task_limits.items()},
        "policy_ref": policy.policy_ref,
        "unknown_policy": policy.unknown_policy,
    }


def _policy_from_payload(value: Any) -> BudgetPolicy:
    if type(value) is not dict or set(value) != {"limits", "task_limits", "policy_ref", "unknown_policy"}:
        raise BudgetStoreError("E_SCHEMA_INVALID", ("policy_json",))
    try:
        return BudgetPolicy(
            value["limits"], value["task_limits"],
            policy_ref=value["policy_ref"], unknown_policy=value["unknown_policy"],
        )
    except (BudgetError, TypeError, ValueError) as exc:
        raise BudgetStoreError("E_SCHEMA_INVALID", ("policy_json",)) from exc


def _observation_payload(observation: UsageObservation) -> dict[str, Any]:
    if type(observation) is not UsageObservation:
        raise BudgetStoreError("E_SCHEMA_TYPE", ("observation",))
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
        raise BudgetStoreError("E_SCHEMA_INVALID", ("observation_json",))
    try:
        return UsageObservation(**value)
    except (BudgetError, TypeError, ValueError) as exc:
        raise BudgetStoreError("E_SCHEMA_INVALID", ("observation_json",)) from exc


DDL = """
CREATE TABLE IF NOT EXISTS budget_meta (
    singleton INTEGER NOT NULL PRIMARY KEY CHECK(singleton=1),
    schema_version INTEGER NOT NULL CHECK(schema_version=2)
);
CREATE TABLE IF NOT EXISTS policies (
    request_id TEXT NOT NULL PRIMARY KEY,
    policy_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS operations (
    operation_id TEXT NOT NULL PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES policies(request_id),
    task_id TEXT NOT NULL,
    generation INTEGER NOT NULL CHECK(generation>=1),
    reservation_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('reserved','provisional','reconciled','unknown_liability','cancelled_not_started')),
    finished INTEGER NOT NULL CHECK(finished IN (0,1)),
    cancellation_conflict INTEGER NOT NULL CHECK(cancellation_conflict IN (0,1)),
    UNIQUE(request_id, operation_id)
);
CREATE TABLE IF NOT EXISTS observations (
    observation_id TEXT NOT NULL PRIMARY KEY,
    operation_id TEXT NOT NULL REFERENCES operations(operation_id),
    request_id TEXT NOT NULL REFERENCES policies(request_id),
    task_id TEXT NOT NULL,
    dimension TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('cumulative','final','unknown')),
    amount INTEGER,
    revision INTEGER NOT NULL CHECK(revision>=1),
    economic_call_key TEXT NOT NULL,
    provider TEXT,
    billing_event_id TEXT,
    currency TEXT,
    final INTEGER NOT NULL CHECK(final IN (0,1)),
    correction INTEGER NOT NULL CHECK(correction IN (0,1)),
    supersedes TEXT,
    unknown_reason TEXT,
    evidence_ref TEXT NOT NULL,
    request_observation_id TEXT,
    task_observation_id TEXT,
    payload_json TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK(sequence>=1),
    FOREIGN KEY(request_id) REFERENCES policies(request_id),
    FOREIGN KEY(supersedes) REFERENCES observations(observation_id)
);
CREATE TABLE IF NOT EXISTS current_projection (
    operation_id TEXT NOT NULL REFERENCES operations(operation_id),
    dimension TEXT NOT NULL,
    observation_id TEXT,
    revision INTEGER,
    kind TEXT,
    known INTEGER NOT NULL CHECK(known>=0),
    held INTEGER NOT NULL CHECK(held>=0),
    exposure INTEGER NOT NULL CHECK(exposure>=0),
    coverage TEXT NOT NULL CHECK(coverage IN ('complete','provisional','incomplete')),
    unknown INTEGER NOT NULL CHECK(unknown IN (0,1)),
    sequence INTEGER NOT NULL CHECK(sequence>=0),
    PRIMARY KEY(operation_id,dimension),
    FOREIGN KEY(observation_id) REFERENCES observations(observation_id)
);
CREATE TABLE IF NOT EXISTS stop_reasons (
    request_id TEXT NOT NULL REFERENCES policies(request_id),
    reason TEXT NOT NULL,
    stop_epoch INTEGER NOT NULL CHECK(stop_epoch>=1),
    sequence INTEGER NOT NULL CHECK(sequence>=1),
    PRIMARY KEY(request_id,reason)
);
CREATE TABLE IF NOT EXISTS outbox (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT REFERENCES policies(request_id),
    operation_id TEXT REFERENCES operations(operation_id),
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS observations_immutable_update
BEFORE UPDATE ON observations BEGIN SELECT RAISE(ABORT, 'immutable observation'); END;
CREATE TRIGGER IF NOT EXISTS observations_immutable_delete
BEFORE DELETE ON observations BEGIN SELECT RAISE(ABORT, 'immutable observation'); END;
INSERT OR IGNORE INTO budget_meta(singleton,schema_version) VALUES(1,2);
"""

_TABLES = {"budget_meta", "policies", "operations", "observations", "current_projection", "stop_reasons", "outbox"}


class BudgetStore:
    """SQLite adapter for one or more independently scoped budget requests."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=5.0)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        try:
            mode = str(self.db.execute("PRAGMA journal_mode=DELETE").fetchone()[0]).lower()
            if mode not in {"delete", "memory"}:
                raise BudgetStoreError("E_DB_MODE", (mode,))
            self.db.execute("PRAGMA synchronous=FULL")
            self._open_or_validate()
        except Exception:
            self.db.close()
            raise

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "BudgetStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    @contextmanager
    def _tx(self) -> Iterator[None]:
        started = False
        try:
            self.db.execute("BEGIN IMMEDIATE")
            started = True
            yield
        except Exception:
            if started:
                self.db.execute("ROLLBACK")
            raise
        else:
            if started:
                self.db.execute("COMMIT")

    def _open_or_validate(self) -> None:
        objects = {
            row[0]: row[1] for row in self.db.execute(
                "SELECT name,type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            )
        }
        tables = {name for name, kind in objects.items() if kind == "table"}
        if not objects:
            self.db.executescript(DDL)
        else:
            if "budget_meta" not in tables or not _TABLES.issubset(tables):
                raise BudgetStoreError("E_SCHEMA_INVALID", ("missing_table",))
            row = self.db.execute("SELECT schema_version FROM budget_meta WHERE singleton=1").fetchone()
            if row is None or type(row[0]) is not int or row[0] != 2:
                raise BudgetStoreError("E_SCHEMA_VERSION")
        self._validate_schema()

    def _validate_schema(self) -> None:
        required = {
            # SQLite reports INTEGER PRIMARY KEY as nullable in PRAGMA
            # table_info even though the key itself is enforced; validate the
            # key separately above and require NOT NULL only on the marker.
            "budget_meta": {"schema_version"},
            "policies": {"request_id", "policy_json"},
            "operations": {"operation_id", "request_id", "task_id", "generation", "reservation_json", "state", "finished", "cancellation_conflict"},
            "observations": {"observation_id", "operation_id", "request_id", "task_id", "dimension", "kind", "amount", "revision", "economic_call_key", "final", "correction", "payload_json", "fingerprint", "sequence"},
            "current_projection": {"operation_id", "dimension", "observation_id", "revision", "kind", "known", "held", "exposure", "coverage", "unknown", "sequence"},
            "stop_reasons": {"request_id", "reason", "stop_epoch", "sequence"},
            "outbox": {"seq", "request_id", "operation_id", "event_type", "payload_json"},
        }
        for table, fields in required.items():
            actual = {row[1] for row in self.db.execute(f"PRAGMA table_info({table})")}
            if not fields.issubset(actual):
                raise BudgetStoreError("E_SCHEMA_INVALID", (table,))
        for table, expected in {
            "budget_meta": ("singleton",), "policies": ("request_id",),
            "operations": ("operation_id",), "observations": ("observation_id",),
            "current_projection": ("operation_id", "dimension"),
            "stop_reasons": ("request_id", "reason"), "outbox": ("seq",),
        }.items():
            pks = [row[1] for row in sorted(self.db.execute(f"PRAGMA table_info({table})"), key=lambda r: r[5]) if row[5]]
            if pks != list(expected):
                raise BudgetStoreError("E_SCHEMA_INVALID", (table, "primary_key"))
        def table_sql(name: str) -> str:
            row = self.db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
            return re.sub(r"\s+", "", str(row[0] or "")).lower() if row else ""

        checks = {
            "budget_meta": ("check(singleton=1)", "check(schema_version=2)"),
            "operations": ("check(generation>=1)", "check(finishedin(0,1))", "check(cancellation_conflictin(0,1))"),
            "observations": ("check(kindin('cumulative','final','unknown'))", "check(revision>=1)", "check(finalin(0,1))", "check(correctionin(0,1))"),
            "current_projection": ("check(known>=0)", "check(held>=0)", "check(exposure>=0)", "check(coveragein('complete','provisional','incomplete'))", "check(unknownin(0,1))"),
            "stop_reasons": ("check(stop_epoch>=1)", "check(sequence>=1)"),
        }
        for table, needles in checks.items():
            sql = table_sql(table)
            if any(needle not in sql for needle in needles):
                raise BudgetStoreError("E_SCHEMA_INVALID", (table, "checks"))
        notnull = {
            table: {row[1] for row in self.db.execute(f"PRAGMA table_info({table})") if row[3]}
            for table in _TABLES
        }
        required_notnull = {
            "budget_meta": {"singleton", "schema_version"},
            "policies": {"request_id", "policy_json"},
            "operations": {"operation_id", "request_id", "task_id", "generation", "reservation_json", "state", "finished", "cancellation_conflict"},
            "observations": {"observation_id", "operation_id", "request_id", "task_id", "dimension", "kind", "revision", "economic_call_key", "final", "correction", "evidence_ref", "payload_json", "fingerprint", "sequence"},
            "current_projection": {"operation_id", "dimension", "known", "held", "exposure", "coverage", "unknown", "sequence"},
            "stop_reasons": {"request_id", "reason", "stop_epoch", "sequence"},
            "outbox": {"event_type", "payload_json"},
        }
        if any(not required_notnull[table].issubset(notnull[table]) for table in required_notnull):
            raise BudgetStoreError("E_SCHEMA_INVALID", ("not_null",))
        fk_expectations = {
            "operations": {("policies", "request_id", "request_id")},
            "observations": {("operations", "operation_id", "operation_id"), ("policies", "request_id", "request_id"), ("observations", "supersedes", "observation_id")},
            "current_projection": {("operations", "operation_id", "operation_id"), ("observations", "observation_id", "observation_id")},
            "stop_reasons": {("policies", "request_id", "request_id")},
            "outbox": {("policies", "request_id", "request_id"), ("operations", "operation_id", "operation_id")},
        }
        for table, expected in fk_expectations.items():
            actual = {(row[2], row[3], row[4]) for row in self.db.execute(f"PRAGMA foreign_key_list({table})")}
            # PRAGMA rows are (id,seq,table,from,to,...).
            if not expected.issubset(actual):
                raise BudgetStoreError("E_SCHEMA_INVALID", (table, "foreign_keys"))
        # A valid schema must retain FK enforcement and immutable-observation triggers.
        if self.db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise BudgetStoreError("E_SCHEMA_INVALID", ("foreign_keys",))
        trigger_names = {row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        if not {"observations_immutable_update", "observations_immutable_delete"}.issubset(trigger_names):
            raise BudgetStoreError("E_SCHEMA_INVALID", ("immutable_observations",))
        trigger_sql = {
            row[0]: re.sub(r"\s+", "", str(row[1] or "")).lower()
            for row in self.db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'")
        }
        if "raise(abort" not in trigger_sql["observations_immutable_update"] or "beforeupdateonobservations" not in trigger_sql["observations_immutable_update"]:
            raise BudgetStoreError("E_SCHEMA_INVALID", ("immutable_observations",))
        if "raise(abort" not in trigger_sql["observations_immutable_delete"] or "beforedeleteonobservations" not in trigger_sql["observations_immutable_delete"]:
            raise BudgetStoreError("E_SCHEMA_INVALID", ("immutable_observations",))
        if self.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or self.db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise BudgetStoreError("E_SCHEMA_INVALID", ("integrity",))
        # Validate every stored value through the same value model before use.
        try:
            for row in self.db.execute("SELECT request_id,policy_json FROM policies"):
                _text(row[0], "policies.request_id", limit=128)
                _policy_from_payload(_decode_json(row[1], "policies.policy_json"))
            for row in self.db.execute("SELECT * FROM operations"):
                _text(row["operation_id"], "operations.operation_id", limit=128)
                _text(row["request_id"], "operations.request_id", limit=128)
                _text(row["task_id"], "operations.task_id", limit=128)
                _integer(row["generation"], "operations.generation", minimum=1)
                _integer(row["finished"], "operations.finished", minimum=0)
                _integer(row["cancellation_conflict"], "operations.cancellation_conflict", minimum=0)
                if row["finished"] not in (0, 1) or row["cancellation_conflict"] not in (0, 1):
                    raise BudgetStoreError("E_SCHEMA_INVALID", ("operations.flags",))
                reservation = _decode_json(row["reservation_json"], "operations.reservation_json")
                if not isinstance(reservation, dict):
                    raise BudgetStoreError("E_SCHEMA_INVALID", ("operations.reservation_json",))
                BudgetOperation(row["operation_id"], row["request_id"], row["task_id"], reservation,
                                state=row["state"], generation=row["generation"], finished=bool(row["finished"]),
                                cancellation_conflict=bool(row["cancellation_conflict"]))
            for row in self.db.execute("SELECT * FROM observations"):
                observed = _observation_from_payload(_decode_json(row["payload_json"], "observations.payload_json"))
                if (row["observation_id"], row["operation_id"], row["dimension"], row["revision"],
                        row["economic_call_key"], row["kind"], row["amount"], bool(row["final"]),
                        bool(row["correction"])) != (observed.observation_id, observed.operation_id,
                        observed.dimension, observed.revision, observed.economic_call_key, observed.kind,
                        observed.amount, observed.final, observed.correction):
                    raise BudgetStoreError("E_SCHEMA_INVALID", ("observations.row_payload",))
                if row["fingerprint"] != stable_observation_fingerprint(observed):
                    raise BudgetStoreError("E_SCHEMA_INVALID", ("observations.fingerprint",))
                _integer(row["sequence"], "observations.sequence", minimum=1)
            for row in self.db.execute("SELECT * FROM current_projection"):
                _text(row["operation_id"], "current_projection.operation_id", limit=128)
                _text(row["dimension"], "current_projection.dimension", limit=128)
                for column in ("known", "held", "exposure", "sequence"):
                    _integer(row[column], f"current_projection.{column}")
                if row["unknown"] not in (0, 1):
                    raise BudgetStoreError("E_SCHEMA_INVALID", ("current_projection.unknown",))
                if row["coverage"] not in ("complete", "provisional", "incomplete"):
                    raise BudgetStoreError("E_SCHEMA_INVALID", ("current_projection.coverage",))
            for row in self.db.execute("SELECT * FROM stop_reasons"):
                _text(row["request_id"], "stop_reasons.request_id", limit=128)
                _text(row["reason"], "stop_reasons.reason", limit=128)
                _integer(row["stop_epoch"], "stop_reasons.stop_epoch", minimum=1)
                _integer(row["sequence"], "stop_reasons.sequence", minimum=1)
            for row in self.db.execute("SELECT * FROM outbox"):
                _integer(row["seq"], "outbox.seq", minimum=1)
                _text(row["request_id"], "outbox.request_id", nullable=True, limit=128)
                _text(row["operation_id"], "outbox.operation_id", nullable=True, limit=128)
                _text(row["event_type"], "outbox.event_type", limit=128)
                _decode_json(row["payload_json"], "outbox.payload_json")
        except (BudgetError, BudgetStoreError, TypeError, ValueError) as exc:
            if isinstance(exc, BudgetStoreError):
                raise
            raise BudgetStoreError("E_SCHEMA_INVALID", ("row",)) from exc

    def _error(self, exc: BudgetError) -> BudgetStoreError:
        return BudgetStoreError(exc.code, (str(exc),))

    def _policy(self, request_id: str) -> BudgetPolicy:
        row = self.db.execute("SELECT policy_json FROM policies WHERE request_id=?", (request_id,)).fetchone()
        if row is None:
            raise BudgetStoreError("E_SCOPE_UNKNOWN", (request_id,))
        return _policy_from_payload(_decode_json(row[0], "policy_json"))

    def _state(self, request_id: str) -> BudgetState:
        policy = self._policy(request_id)
        ops: list[BudgetOperation] = []
        for row in self.db.execute("SELECT * FROM operations WHERE request_id=? ORDER BY rowid", (request_id,)):
            ops.append(BudgetOperation(row["operation_id"], row["request_id"], row["task_id"],
                                       _decode_json(row["reservation_json"], "reservation_json"),
                                       state=row["state"], generation=row["generation"],
                                       finished=bool(row["finished"]),
                                       cancellation_conflict=bool(row["cancellation_conflict"])))
        obs = []
        for row in self.db.execute("SELECT payload_json FROM observations WHERE request_id=? ORDER BY sequence, rowid", (request_id,)):
            obs.append(_observation_from_payload(_decode_json(row[0], "payload_json")))
        reasons = tuple(row[0] for row in self.db.execute("SELECT reason FROM stop_reasons WHERE request_id=? ORDER BY sequence", (request_id,)))
        seq_row = self.db.execute("SELECT COALESCE(MAX(seq),0) FROM outbox WHERE request_id=?", (request_id,)).fetchone()
        state = BudgetState(policy)._evolve(operations=tuple(ops), observations=tuple(obs), stop_reasons=reasons,
                                           stop_epoch=1 if reasons else 0, sequence=int(seq_row[0] or 0), request_id=request_id)
        return state

    def _emit(self, request_id: str | None, operation_id: str | None, event_type: str, payload: Mapping[str, Any]) -> int:
        data = _json(dict(payload))
        cur = self.db.execute("INSERT INTO outbox(request_id,operation_id,event_type,payload_json) VALUES(?,?,?,?)",
                              (request_id, operation_id, event_type, data))
        return int(cur.lastrowid)

    def _persist_reasons(self, request_id: str, before: tuple[str, ...], after: tuple[str, ...]) -> None:
        if before == after:
            return
        for reason in after:
            if reason in before:
                continue
            seq = self._emit(request_id, None, "budget.stop_reason", {"request_id": request_id, "reason": reason})
            self.db.execute("INSERT INTO stop_reasons(request_id,reason,stop_epoch,sequence) VALUES(?,?,?,?)",
                            (request_id, reason, 1, seq))

    def _repair_operation(self, old: BudgetState, new: BudgetState, operation_id: str) -> BudgetState:
        """Compensate for the pure prototype's historical replace helper bug."""
        changed = next((op for op in new.operations if op.operation_id == operation_id), None)
        if changed is None:
            return new
        if not any(op.operation_id == operation_id for op in old.operations):
            return new
        ops = tuple(changed if op.operation_id == operation_id else op for op in old.operations)
        return new._evolve(operations=ops)

    def _persist_operation(self, operation: BudgetOperation) -> None:
        self.db.execute("UPDATE operations SET state=?,finished=?,cancellation_conflict=? WHERE operation_id=?",
                        (operation.state, int(operation.finished), int(operation.cancellation_conflict), operation.operation_id))

    def _refresh_projection(self, state: BudgetState, request_id: str, operation_id: str, seq: int) -> None:
        op = next(op for op in state.operations if op.operation_id == operation_id)
        for dimension in state.policy.limits:
            current, known = _current(state.observations, operation_id, dimension)
            cancelled_without_fact = op.state == "cancelled_not_started" and current is None
            closed = current is not None and current.final
            held = 0 if cancelled_without_fact or closed else max(op.reservation[dimension] - known, 0)
            unknown = bool(op.cancellation_conflict or
                           (current is not None and current.kind == "unknown") or
                           (op.finished and not closed))
            coverage = "incomplete" if unknown else ("complete" if closed or cancelled_without_fact else "provisional")
            self.db.execute(
                "INSERT INTO current_projection(operation_id,dimension,observation_id,revision,kind,known,held,exposure,coverage,unknown,sequence) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(operation_id,dimension) DO UPDATE SET observation_id=excluded.observation_id,revision=excluded.revision,kind=excluded.kind,known=excluded.known,held=excluded.held,exposure=excluded.exposure,coverage=excluded.coverage,unknown=excluded.unknown,sequence=excluded.sequence",
                (operation_id, dimension, current.observation_id if current else None,
                 current.revision if current else None, current.kind if current else None,
                 known, held, known + held, coverage, int(unknown), seq))

    def seed_policy(self, request_id: str, policy: BudgetPolicy) -> BudgetResult:
        request_id = _text(request_id, "request_id", limit=128) or ""
        payload = _policy_payload(policy)
        encoded = _json(payload)
        with self._tx():
            row = self.db.execute("SELECT policy_json FROM policies WHERE request_id=?", (request_id,)).fetchone()
            if row is not None:
                if row[0] == encoded:
                    return BudgetResult(None, "REPLAY", replayed=True)
                raise BudgetStoreError("E_POLICY_CONFLICT", (request_id,))
            self.db.execute("INSERT INTO policies(request_id,policy_json) VALUES(?,?)", (request_id, encoded))
            self._emit(request_id, None, "budget.policy_seeded", {"request_id": request_id, "policy": payload})
        return BudgetResult(None, "SEEDED")

    def reserve(self, operation_id: str, request_id: str, task_id: str,
                reservation: Mapping[str, int], generation: int = 1) -> BudgetResult:
        operation_id = _text(operation_id, "operation_id", limit=128) or ""
        request_id = _text(request_id, "request_id", limit=128) or ""
        task_id = _text(task_id, "task_id", limit=128) or ""
        generation = _integer(generation, "generation", minimum=1)
        with self._tx():
            existing_global = self.db.execute(
                "SELECT request_id FROM operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            if existing_global is not None and existing_global[0] != request_id:
                raise BudgetStoreError("E_OPERATION_CONFLICT", (operation_id,))
            state = self._state(request_id)
            old = state
            try:
                state, decision = state.reserve_for_operation(operation_id, request_id, task_id, reservation, generation=generation)
            except BudgetError as exc:
                raise self._error(exc) from None
            state = self._repair_operation(old, state, operation_id)
            if decision.replayed:
                return BudgetResult(operation_id, decision.status, replayed=True, reasons=decision.reasons)
            op = next(op for op in state.operations if op.operation_id == operation_id)
            self.db.execute("INSERT INTO operations(operation_id,request_id,task_id,generation,reservation_json,state,finished,cancellation_conflict) VALUES(?,?,?,?,?,?,?,?)",
                            (op.operation_id, op.request_id, op.task_id, op.generation, _json(dict(op.reservation)), op.state, int(op.finished), int(op.cancellation_conflict)))
            seq = self._emit(request_id, operation_id, "budget.operation_reserved", {"operation_id": operation_id, "task_id": task_id, "generation": generation, "reservation": dict(op.reservation)})
            self._refresh_projection(state, request_id, operation_id, seq)
        return BudgetResult(operation_id, decision.status, reasons=decision.reasons)

    def observe(self, observation: UsageObservation) -> BudgetResult:
        if type(observation) is not UsageObservation:
            raise BudgetStoreError("E_SCHEMA_TYPE", ("observation",))
        with self._tx():
            row = self.db.execute("SELECT request_id FROM operations WHERE operation_id=?", (observation.operation_id,)).fetchone()
            if row is None:
                raise BudgetStoreError("E_SCOPE_UNKNOWN", ("operation",))
            request_id = str(row[0])
            state = self._state(request_id)
            old = state
            try:
                state, decision = state.record_usage_observation(observation)
            except BudgetError as exc:
                raise self._error(exc) from None
            state = self._repair_operation(old, state, observation.operation_id)
            if decision.replayed:
                return BudgetResult(observation.operation_id, decision.status, replayed=True, historical=decision.historical, reasons=decision.reasons)
            payload = _observation_payload(observation)
            fingerprint = stable_observation_fingerprint(observation)
            seq = self._emit(request_id, observation.operation_id, "budget.observation_recorded", {"observation": payload, "status": decision.status, "reasons": list(decision.reasons)})
            self.db.execute("INSERT INTO observations(observation_id,operation_id,request_id,task_id,dimension,kind,amount,revision,economic_call_key,provider,billing_event_id,currency,final,correction,supersedes,unknown_reason,evidence_ref,request_observation_id,task_observation_id,payload_json,fingerprint,sequence) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (observation.observation_id, observation.operation_id, request_id, next(op.task_id for op in state.operations if op.operation_id == observation.operation_id), observation.dimension, observation.kind, observation.amount, observation.revision, observation.economic_call_key, observation.provider, observation.billing_event_id, observation.currency, int(observation.final), int(observation.correction), observation.supersedes, observation.unknown_reason, observation.evidence_ref, observation.request_id, observation.task_id, _json(payload), fingerprint, seq))
            op = next(op for op in state.operations if op.operation_id == observation.operation_id)
            self._persist_operation(op)
            self._persist_reasons(request_id, old.stop_reasons, state.stop_reasons)
            self._refresh_projection(state, request_id, observation.operation_id, seq)
        return BudgetResult(observation.operation_id, decision.status, historical=decision.historical, reasons=decision.reasons)

    def settle(self, operation_id: str) -> BudgetResult:
        operation_id = _text(operation_id, "operation_id", limit=128) or ""
        with self._tx():
            row = self.db.execute("SELECT request_id FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            if row is None:
                raise BudgetStoreError("E_SCOPE_UNKNOWN", ("operation",))
            request_id = str(row[0])
            old = self._state(request_id)
            try:
                state, decision = old.settle_operation(operation_id)
            except BudgetError as exc:
                raise self._error(exc) from None
            state = self._repair_operation(old, state, operation_id)
            if decision.replayed:
                return BudgetResult(operation_id, decision.status, replayed=True, reasons=decision.reasons)
            seq = self._emit(request_id, operation_id, "budget.operation_settled", {"operation_id": operation_id, "reasons": list(decision.reasons)})
            self._persist_operation(next(op for op in state.operations if op.operation_id == operation_id))
            self._persist_reasons(request_id, old.stop_reasons, state.stop_reasons)
            self._refresh_projection(state, request_id, operation_id, seq)
        return BudgetResult(operation_id, decision.status, reasons=decision.reasons)

    def release_unstarted(self, operation_id: str, not_started_proven: bool | None = None) -> BudgetResult:
        operation_id = _text(operation_id, "operation_id", limit=128) or ""
        with self._tx():
            row = self.db.execute("SELECT request_id FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            if row is None:
                raise BudgetStoreError("E_SCOPE_UNKNOWN", ("operation",))
            request_id = str(row[0])
            old = self._state(request_id)
            try:
                state, decision = old.release_proven_unstarted(operation_id, not_started_proven=not_started_proven)
            except BudgetError as exc:
                raise self._error(exc) from None
            state = self._repair_operation(old, state, operation_id)
            if decision.replayed:
                return BudgetResult(operation_id, decision.status, replayed=True, reasons=decision.reasons)
            seq = self._emit(request_id, operation_id, "budget.operation_released_unstarted", {"operation_id": operation_id})
            self._persist_operation(next(op for op in state.operations if op.operation_id == operation_id))
            self._refresh_projection(state, request_id, operation_id, seq)
        return BudgetResult(operation_id, decision.status, reasons=decision.reasons)

    def snapshot(self, request_id: str, task_id: str | None = None) -> BudgetSnapshot:
        request_id = _text(request_id, "request_id", limit=128) or ""
        if task_id is not None:
            task_id = _text(task_id, "task_id", limit=128)
        return self._state(request_id).snapshot(task_id=task_id)

    def stop(self, request_id: str, reason: str = "OPERATOR_STOP") -> BudgetResult:
        request_id = _text(request_id, "request_id", limit=128) or ""
        reason = _text(reason, "stop_reason", limit=128) or ""
        with self._tx():
            old = self._state(request_id)
            try:
                state = old.request_stop(reason)
            except BudgetError as exc:
                raise self._error(exc) from None
            if state is old:
                self._emit(request_id, None, "budget.stop_already", {"request_id": request_id, "reason": reason, "existing": list(old.stop_reasons)})
                return BudgetResult(None, "REPLAY", replayed=True, reasons=old.stop_reasons)
            seq = self._emit(request_id, None, "budget.stopped", {"request_id": request_id, "reason": reason})
            self.db.execute("INSERT INTO stop_reasons(request_id,reason,stop_epoch,sequence) VALUES(?,?,?,?)", (request_id, reason, 1, seq))
        return BudgetResult(None, "STOPPED", reasons=state.stop_reasons)

    def outbox(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM outbox ORDER BY seq").fetchall()

    def operation(self, operation_id: str) -> sqlite3.Row:
        operation_id = _text(operation_id, "operation_id", limit=128) or ""
        row = self.db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        if row is None:
            raise BudgetStoreError("E_SCOPE_UNKNOWN", ("operation",))
        return row


LedgerError = BudgetStoreError

__all__ = ["DDL", "BudgetResult", "BudgetStore", "BudgetStoreError", "LedgerError"]
