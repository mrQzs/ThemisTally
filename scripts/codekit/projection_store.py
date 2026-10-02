"""Recoverable offline persistence for the 08 projection/outbox boundary.

This is deliberately a small JSONL journal.  It records consumer events and
checkpoints, and treats a partial final line as recoverable tail damage while
rejecting corruption in the middle of the journal.  It is an offline evidence
store; it does not grant dispatch or publication authority.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .builtin_artifacts import ArtifactError
from .builtin_projections import CursorProjection, ProjectionEvent


def _fail(code: str, message: str) -> None:
    raise ArtifactError(code, "/projection_store", message)


def _event_dict(event: ProjectionEvent) -> dict[str, Any]:
    return {
        "seq": event.seq,
        "source": event.source,
        "event_type": event.event_type,
        "payload": deepcopy(dict(event.payload)),
        "event_id": event.event_id,
    }


def _event_from(value: Mapping[str, Any]) -> ProjectionEvent:
    if not isinstance(value, Mapping):
        _fail("E_JOURNAL", "event record must contain a mapping")
    return ProjectionEvent(
        seq=value.get("seq"),
        source=value.get("source"),
        event_type=value.get("event_type"),
        payload=value.get("payload", {}),
        event_id=value.get("event_id"),
    )


class PersistentProjectionStore:
    """Append-only projection journal with deterministic recovery semantics."""

    def __init__(self, path: str | Path, *, generation: int = 1) -> None:
        self.path = Path(path)
        self.projection = CursorProjection(generation=generation)
        self.recovery = "CLEAN"
        self._load()

    @property
    def generation(self) -> int:
        return self.projection.generation

    @property
    def cursor(self) -> int:
        return self.projection.cursor

    @property
    def source_vector(self) -> dict[str, int]:
        return dict(self.projection.source_vector)

    @property
    def events(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self.projection.events)

    def _append(self, record: Mapping[str, Any]) -> None:
        try:
            encoded = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            _fail("E_JOURNAL", f"record is not JSON serializable: {exc}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = self.path.read_bytes()
        if not raw:
            return
        lines = raw.splitlines(keepends=True)
        for index, line in enumerate(lines):
            complete = line.endswith(b"\n")
            if not complete and index != len(lines) - 1:
                _fail("E_JOURNAL_CORRUPT", "non-final journal line is truncated")
            try:
                record = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                if index == len(lines) - 1 and not complete:
                    self.recovery = "TRUNCATED_TAIL"
                    break
                _fail("E_JOURNAL_CORRUPT", f"invalid journal record: {exc}")
            if not isinstance(record, Mapping):
                _fail("E_JOURNAL_CORRUPT", "journal record must be an object")
            self._replay(record)

    def _replay(self, record: Mapping[str, Any]) -> None:
        kind = record.get("kind")
        if kind == "event":
            if record.get("generation") != self.generation:
                _fail("E_JOURNAL_FENCE", "event generation does not match projection")
            self.projection.consume([_event_from(record.get("event", {}))], generation=self.generation)
            return
        if kind == "checkpoint":
            generation = record.get("generation")
            cursor = record.get("cursor")
            vector = record.get("source_vector", {})
            events = record.get("events", {})
            if type(generation) is not int or type(cursor) is not int or not isinstance(vector, Mapping) or not isinstance(events, Mapping):
                _fail("E_JOURNAL_CORRUPT", "invalid checkpoint")
            if generation < 1 or cursor < 0:
                _fail("E_JOURNAL_CORRUPT", "invalid checkpoint generation or cursor")
            self.projection.generation = generation
            self.projection.cursor = cursor
            self.projection.source_vector = {str(k): int(v) for k, v in vector.items()}
            self.projection.events = deepcopy(dict(events))
            return
        if kind == "handoff":
            old = record.get("from_generation")
            new = record.get("to_generation")
            if old != self.generation or type(new) is not int or new <= old:
                _fail("E_JOURNAL_FENCE", "invalid handoff generation")
            self.projection.generation = new
            return
        _fail("E_JOURNAL_CORRUPT", "unknown journal record kind")

    def consume(self, events: Sequence[ProjectionEvent], *, generation: int) -> str:
        if self.recovery != "CLEAN":
            _fail("E_RECOVERY", "reconcile or repair recovery tail before writing")
        before = set(self.projection.events)
        result = self.projection.consume(events, generation=generation)
        if result == "APPLIED":
            for event in events:
                event_id = event.event_id
                if event_id is None:
                    # CursorProjection calculates an ID; replaying the same
                    # event will be idempotent, so derive it from the record.
                    from .builtin_projections import _event_id
                    event_id = _event_id(event.source, event.event_type, event.payload)
                if event_id not in before:
                    self._append({"kind": "event", "generation": generation, "event": _event_dict(event)})
        return result

    def rebuild(self, authority_rows: Sequence[Mapping[str, Any]], *, generation: int,
                expected_cursor: int | None = None) -> None:
        if self.recovery != "CLEAN":
            _fail("E_RECOVERY", "reconcile or repair recovery tail before writing")
        if expected_cursor is not None and expected_cursor != self.cursor:
            _fail("E_CAS", "projection cursor changed")
        self.projection.rebuild(authority_rows, generation=generation)
        self._append({
            "kind": "checkpoint",
            "generation": self.generation,
            "cursor": self.cursor,
            "source_vector": self.source_vector,
            "events": self.events,
        })

    def handoff(self, *, new_generation: int, expected_generation: int) -> None:
        if self.recovery != "CLEAN":
            _fail("E_RECOVERY", "reconcile or repair recovery tail before writing")
        if expected_generation != self.generation:
            _fail("E_FENCED", "stale handoff generation")
        if type(new_generation) is not int or new_generation <= self.generation:
            _fail("E_FENCE", "new generation must advance")
        old = self.generation
        self.projection.generation = new_generation
        self._append({"kind": "handoff", "from_generation": old, "to_generation": new_generation})

    def reconcile(self, *, expected_generation: int, expected_cursor: int) -> dict[str, Any]:
        return {
            "ok": expected_generation == self.generation and expected_cursor == self.cursor,
            "generation": self.generation,
            "cursor": self.cursor,
            "recovery": self.recovery,
        }


__all__ = ["PersistentProjectionStore"]
