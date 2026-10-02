"""Versioned unified ledger boundary built on the atomic v2 prototype."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import sqlite3
from typing import Any, Mapping

from .atomic_claim_budget import AtomicClaimBudgetStore, AtomicLedgerError

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ATTEMPT_STATES = frozenset(("ADMITTED", "STARTING", "START_UNKNOWN", "STARTED", "REVIEW_PENDING", "FINISHED", "CANCELLED"))
_TRANSITIONS = {
    "ADMITTED": frozenset(("STARTING", "CANCELLED")),
    "STARTING": frozenset(("START_UNKNOWN", "STARTED", "CANCELLED")),
    "START_UNKNOWN": frozenset(("STARTED", "CANCELLED")),
    "STARTED": frozenset(("REVIEW_PENDING", "CANCELLED")),
    "REVIEW_PENDING": frozenset(("FINISHED",)),
    "FINISHED": frozenset(),
    "CANCELLED": frozenset(),
}


def _id(value: Any, field: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise AtomicLedgerError("E_SCHEMA_TYPE", (field,))
    return value


def _positive(value: Any, field: str) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 1:
        raise AtomicLedgerError("E_SCHEMA_TYPE", (field,))
    return value


def _sequence(value: Any, field: str) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise AtomicLedgerError("E_SCHEMA_TYPE", (field,))
    return value


def _ref(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _id(value, field)


def _json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(dict(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise AtomicLedgerError("E_SCHEMA_TYPE", ("payload",)) from exc


def evidence_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AttemptRecord:
    attempt_id: str
    operation_id: str
    run_id: str
    stage_id: str
    plan_version: int
    generation: int
    state: str
    evidence_ref: str | None
    sequence: int


@dataclass(frozen=True)
class AttemptResult:
    attempt_id: str
    state: str
    replayed: bool = False
    sequence: int = 0


@dataclass(frozen=True)
class CursorResult:
    consumer_id: str
    next_seq: int
    replayed: bool = False


DDL_V3 = """
CREATE TABLE IF NOT EXISTS ledger_meta(singleton INTEGER PRIMARY KEY CHECK(singleton=1), schema_version INTEGER NOT NULL CHECK(schema_version=3), activated_generation INTEGER NOT NULL CHECK(activated_generation>=1));
CREATE TABLE IF NOT EXISTS attempts(
    attempt_id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL REFERENCES operations(operation_id),
    run_id TEXT NOT NULL,
    stage_id TEXT NOT NULL,
    plan_version INTEGER NOT NULL CHECK(plan_version>=1),
    generation INTEGER NOT NULL CHECK(generation>=1),
    state TEXT NOT NULL CHECK(state IN('ADMITTED','STARTING','START_UNKNOWN','STARTED','REVIEW_PENDING','FINISHED','CANCELLED')),
    evidence_ref TEXT,
    sequence INTEGER NOT NULL CHECK(sequence>=0),
    UNIQUE(operation_id, stage_id),
    UNIQUE(run_id, stage_id)
);
CREATE INDEX IF NOT EXISTS active_attempts_v3 ON attempts(operation_id, stage_id) WHERE state NOT IN('FINISHED','CANCELLED');
CREATE TABLE IF NOT EXISTS consumer_cursors(
    consumer_id TEXT PRIMARY KEY,
    next_seq INTEGER NOT NULL CHECK(next_seq>=0),
    high_water INTEGER NOT NULL CHECK(high_water>=0),
    updated_seq INTEGER NOT NULL CHECK(updated_seq>=0)
);
CREATE TABLE IF NOT EXISTS migration_batches(
    migration_id TEXT PRIMARY KEY,
    source_db TEXT NOT NULL,
    source_schema INTEGER NOT NULL CHECK(source_schema>=1),
    row_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN('PLANNED','IMPORTED','ACTIVATED','RECOVERY')),
    conflict_count INTEGER NOT NULL CHECK(conflict_count>=0)
);
"""


class UnifiedLedgerStore(AtomicClaimBudgetStore):
    """The v3 authority candidate; all added writes share the atomic store TX."""

    def __init__(self, path: str = ":memory:") -> None:
        super().__init__(path)
        try:
            # sqlite3.executescript performs its own implicit commit.  Run
            # schema DDL outside the inherited transaction context, then
            # persist the activation marker in the normal atomic path.
            self.db.executescript(DDL_V3)
            with self._tx():
                self.db.execute("INSERT OR IGNORE INTO ledger_meta(singleton,schema_version,activated_generation) VALUES(1,3,(SELECT generation FROM controller WHERE singleton=1))")
                row = self.db.execute("SELECT schema_version FROM ledger_meta WHERE singleton=1").fetchone()
                if row is None or row[0] != 3:
                    raise AtomicLedgerError("E_SCHEMA_INVALID", ("ledger_meta",))
        except Exception:
            self.close()
            raise

    def manifest(self) -> dict[str, Any]:
        row = self.db.execute("SELECT schema_version,activated_generation FROM ledger_meta WHERE singleton=1").fetchone()
        if row is None:
            raise AtomicLedgerError("E_SCHEMA_INVALID", ("ledger_meta",))
        return {
            "schema_version": int(row[0]),
            "activated_generation": int(row[1]),
            "tables": tuple(sorted({"requests", "tasks", "operations", "resource_holds", "observations", "outbox", "attempts", "consumer_cursors", "migration_batches"})),
        }

    def _emit_seq(self, request_id, operation_id, event_type, payload) -> int:
        self._emit(request_id, operation_id, event_type, payload)
        return int(self.db.execute("SELECT max(seq) FROM outbox").fetchone()[0])

    def _attempt(self, attempt_id: str) -> AttemptRecord:
        row = self.db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        if row is None:
            raise AtomicLedgerError("E_SCOPE_UNKNOWN", ("attempt",))
        return AttemptRecord(row["attempt_id"], row["operation_id"], row["run_id"], row["stage_id"], row["plan_version"], row["generation"], row["state"], row["evidence_ref"], row["sequence"])

    def create_attempt(self, attempt_id: str, operation_id: str, run_id: str, stage_id: str, plan_version: int, *, generation: int = 1, evidence_ref: str | None = None) -> AttemptResult:
        attempt_id, operation_id, run_id, stage_id = (_id(attempt_id, "attempt_id"), _id(operation_id, "operation_id"), _id(run_id, "run_id"), _id(stage_id, "stage_id"))
        plan_version, generation = _positive(plan_version, "plan_version"), _positive(generation, "generation")
        evidence_ref = _ref(evidence_ref, "evidence_ref")
        with self._tx():
            current = self.db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
            if current is not None:
                same = (current["operation_id"], current["run_id"], current["stage_id"], current["plan_version"], current["generation"], current["evidence_ref"]) == (operation_id, run_id, stage_id, plan_version, generation, evidence_ref)
                if same:
                    return AttemptResult(attempt_id, current["state"], True, current["sequence"])
                raise AtomicLedgerError("E_IDEMPOTENCY_CONFLICT", ("attempt_id",))
            op = self.db.execute("SELECT request_id FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            if op is None:
                raise AtomicLedgerError("E_SCOPE_UNKNOWN", ("operation",))
            operation = self.db.execute("SELECT state,generation,claim_generation FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            if operation["state"] not in ("CLAIMED", "HANDOFF_ACCEPTED", "START_UNKNOWN"):
                raise AtomicLedgerError("E_ATTEMPT_STATE", ("operation_not_active",))
            controller = self.db.execute("SELECT generation FROM controller WHERE singleton=1").fetchone()[0]
            if generation != controller or operation["generation"] != generation or operation["claim_generation"] != generation:
                raise AtomicLedgerError("E_FENCED", ("generation",))
            request = self.db.execute("SELECT stopped FROM requests WHERE request_id=?", (op[0],)).fetchone()
            if request is None:
                raise AtomicLedgerError("E_STOPPED", ("request_stopped",))
            if request[0] and current.state in ("ADMITTED", "STARTING") and next_state in ("STARTING", "STARTED", "REVIEW_PENDING"):
                raise AtomicLedgerError("E_STOPPED", ("request_stopped",))
            seq = self._emit_seq(op[0], operation_id, "ledger.attempt_admitted", {"attempt_id": attempt_id, "run_id": run_id, "stage_id": stage_id, "plan_version": plan_version, "generation": generation})
            try:
                self.db.execute("INSERT INTO attempts(attempt_id,operation_id,run_id,stage_id,plan_version,generation,state,evidence_ref,sequence) VALUES(?,?,?,?,?,?,?,?,?)", (attempt_id, operation_id, run_id, stage_id, plan_version, generation, "ADMITTED", evidence_ref, seq))
            except sqlite3.IntegrityError as exc:
                raise AtomicLedgerError("E_ATTEMPT_CONFLICT", ("operation_or_run_stage",)) from exc
            return AttemptResult(attempt_id, "ADMITTED", False, seq)

    def transition_attempt(self, attempt_id: str, *, expected_state: str, next_state: str, generation: int, evidence_ref: str | None = None) -> AttemptResult:
        attempt_id = _id(attempt_id, "attempt_id")
        generation = _positive(generation, "generation")
        if expected_state not in _ATTEMPT_STATES or next_state not in _ATTEMPT_STATES or next_state not in _TRANSITIONS[expected_state]:
            raise AtomicLedgerError("E_ATTEMPT_STATE", ("invalid_transition",))
        evidence_ref = _ref(evidence_ref, "evidence_ref")
        with self._tx():
            current = self._attempt(attempt_id)
            controller = self.db.execute("SELECT generation FROM controller WHERE singleton=1").fetchone()[0]
            if current.generation != generation or controller != generation:
                raise AtomicLedgerError("E_FENCED", ("generation",))
            request_id = self.db.execute("SELECT request_id FROM operations WHERE operation_id=?", (current.operation_id,)).fetchone()[0]
            request = self.db.execute("SELECT stopped FROM requests WHERE request_id=?", (request_id,)).fetchone()
            if request is None:
                raise AtomicLedgerError("E_STOPPED", ("request_stopped",))
            if request[0] and current.state in ("ADMITTED", "STARTING") and next_state in ("STARTING", "STARTED", "REVIEW_PENDING"):
                raise AtomicLedgerError("E_STOPPED", ("request_stopped",))
            if current.state == next_state and current.generation == generation:
                if evidence_ref == current.evidence_ref:
                    return AttemptResult(attempt_id, next_state, True, current.sequence)
                raise AtomicLedgerError("E_IDEMPOTENCY_CONFLICT", ("evidence_ref",))
            if current.state != expected_state:
                raise AtomicLedgerError("E_ATTEMPT_STATE", ("expected_state_mismatch",))
            seq = self._emit_seq(request_id, current.operation_id, "ledger.attempt_transition", {"attempt_id": attempt_id, "from": expected_state, "to": next_state, "generation": generation, "evidence_ref": evidence_ref})
            cur = self.db.execute("UPDATE attempts SET state=?,evidence_ref=?,sequence=? WHERE attempt_id=? AND state=? AND generation=?", (next_state, evidence_ref, seq, attempt_id, expected_state, generation))
            if cur.rowcount != 1:
                raise AtomicLedgerError("E_ATTEMPT_CONFLICT", ("cas",))
            return AttemptResult(attempt_id, next_state, False, seq)

    def upsert_consumer_cursor(self, consumer_id: str, *, expected_seq: int, next_seq: int) -> CursorResult:
        consumer_id = _id(consumer_id, "consumer_id")
        expected_seq, next_seq = _sequence(expected_seq, "expected_seq"), _sequence(next_seq, "next_seq")
        if next_seq < expected_seq:
            raise AtomicLedgerError("E_CURSOR_REGRESSION", ("next_seq",))
        with self._tx():
            row = self.db.execute("SELECT next_seq,high_water FROM consumer_cursors WHERE consumer_id=?", (consumer_id,)).fetchone()
            if row is None:
                if expected_seq != 0:
                    raise AtomicLedgerError("E_CURSOR_CONFLICT", ("missing_cursor",))
                current, high_water = 0, 0
            else:
                current, high_water = int(row[0]), int(row[1])
                if current != expected_seq:
                    if current == next_seq:
                        return CursorResult(consumer_id, current, True)
                    raise AtomicLedgerError("E_CURSOR_CONFLICT", ("expected_seq",))
            high_water_available = int(self.db.execute("SELECT COALESCE(MAX(seq),0) FROM outbox").fetchone()[0])
            if next_seq > high_water_available:
                raise AtomicLedgerError("E_CURSOR_GAP", ("next_seq_beyond_outbox",))
            if row is not None and next_seq == current:
                return CursorResult(consumer_id, current, True)
            seq = self._emit_seq(None, None, "ledger.cursor_advanced", {"consumer_id": consumer_id, "from": current, "to": next_seq})
            high_water = max(high_water, next_seq)
            self.db.execute("INSERT INTO consumer_cursors(consumer_id,next_seq,high_water,updated_seq) VALUES(?,?,?,?) ON CONFLICT(consumer_id) DO UPDATE SET next_seq=excluded.next_seq,high_water=excluded.high_water,updated_seq=excluded.updated_seq", (consumer_id, next_seq, high_water, seq))
            return CursorResult(consumer_id, next_seq)

    def record_migration_batch(self, migration_id: str, *, source_db: str, source_schema: int, row_hash: str, state: str = "PLANNED", conflict_count: int = 0) -> bool:
        migration_id, source_db = _id(migration_id, "migration_id"), _id(source_db, "source_db")
        source_schema = _positive(source_schema, "source_schema")
        if type(row_hash) is not str or _HASH.fullmatch(row_hash) is None or state not in {"PLANNED", "IMPORTED", "ACTIVATED", "RECOVERY"} or type(conflict_count) is not int or conflict_count < 0:
            raise AtomicLedgerError("E_SCHEMA_TYPE", ("migration",))
        with self._tx():
            existing = self.db.execute("SELECT source_db,source_schema,row_hash,state,conflict_count FROM migration_batches WHERE migration_id=?", (migration_id,)).fetchone()
            payload = (source_db, source_schema, row_hash, state, conflict_count)
            if existing is not None:
                if tuple(existing) == payload:
                    return True
                raise AtomicLedgerError("E_MIGRATION_CONFLICT", ("migration_id",))
            self.db.execute("INSERT INTO migration_batches(migration_id,source_db,source_schema,row_hash,state,conflict_count) VALUES(?,?,?,?,?,?)", (migration_id, source_db, source_schema, row_hash, state, conflict_count))
            self._emit(None, None, "ledger.migration_recorded", {"migration_id": migration_id, "state": state, "source_schema": source_schema})
            return False


__all__ = ["AttemptRecord", "AttemptResult", "CursorResult", "UnifiedLedgerStore", "evidence_hash"]
