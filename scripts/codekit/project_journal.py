"""A small durable, single-writer project event journal for offline 10 tests."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Any

from . import protocols
from .project_events import ProjectEvent, ProjectEventError, event_from_mapping


class ProjectJournalError(ValueError):
    def __init__(self, code: str, message: str = "project journal rejected") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class AppendReceipt:
    event: ProjectEvent
    replayed: bool


class WriterLock:
    """Cross-platform advisory lock on a stable lock file."""
    def __init__(self, path: str | Path, *, timeout: float = 2.0) -> None:
        self.path = Path(path)
        self.timeout = timeout
        self._handle: Any = None

    def __enter__(self) -> "WriterLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+b")
        if os.fstat(self._handle.fileno()).st_size == 0:
            self._handle.seek(0)
            self._handle.write(b"0")
            self._handle.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self._handle.seek(0)
                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except (OSError, IOError):
                if time.monotonic() >= deadline:
                    self._handle.close()
                    self._handle = None
                    raise ProjectJournalError("E_LOCK_BUSY", "writer lock timeout")
                time.sleep(0.01)

    def __exit__(self, *_: Any) -> None:
        if self._handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None


class ProjectJournal:
    def __init__(self, path: str | Path, *, generation: int = 1, lock_timeout: float = 2.0) -> None:
        if type(generation) is not int or not 1 <= generation <= protocols.MAX_SAFE_INTEGER:
            raise ProjectJournalError("E_GENERATION", "positive generation required")
        self.path = Path(path)
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self.generation = generation
        self.lock_timeout = lock_timeout
        self.cursor = 0
        self.events: dict[str, ProjectEvent] = {}
        self.source_index: dict[str, str] = {}
        self.recovery = "CLEAN"
        self._load()

    def _load(self) -> None:
        self.cursor = 0; self.events = {}; self.source_index = {}; self.recovery = "CLEAN"
        if not self.path.exists():
            return
        raw = self.path.read_bytes()
        if not raw:
            return
        lines = raw.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if not line.endswith(b"\n"):
                if index == len(lines) - 1:
                    self.recovery = "TRUNCATED_TAIL"
                    break
                raise ProjectJournalError("E_JOURNAL_CORRUPT", "middle line is truncated")
            try:
                record = protocols.strict_json_loads(line)
            except protocols.ProtocolError as exc:
                raise ProjectJournalError("E_JOURNAL_CORRUPT", "invalid strict JSON") from exc
            if type(record) is not dict or set(record) != {"kind", "generation", "event"}:
                raise ProjectJournalError("E_JOURNAL_CORRUPT", "closed event journal record required")
            if record["kind"] != "event" or record["generation"] != self.generation:
                raise ProjectJournalError("E_GENERATION", "journal generation mismatch")
            try:
                event = event_from_mapping(record["event"])
            except ProjectEventError as exc:
                raise ProjectJournalError(exc.code, str(exc)) from exc
            if event.seq != self.cursor + 1:
                raise ProjectJournalError("E_CURSOR_GAP", "journal sequence must be contiguous")
            self._index(event)
            self.cursor = event.seq or self.cursor

    def _index(self, event: ProjectEvent) -> None:
        event_id = event.event_id or event.derived_event_id
        key = event.source_key.digest
        previous = self.source_index.get(key)
        if previous is not None and previous != event_id:
            raise ProjectJournalError("E_SOURCE_CONFLICT", "same SourceKey has different event bytes")
        prior = self.events.get(event_id)
        if prior is not None and prior.to_mapping() != event.to_mapping():
            raise ProjectJournalError("E_EVENT_CONFLICT", "event id reused with different bytes")
        self.source_index[key] = event_id
        self.events[event_id] = event

    def append(self, event: ProjectEvent) -> AppendReceipt:
        if type(event) is not ProjectEvent or event.generation is not None or event.seq is not None:
            raise ProjectJournalError("E_EVENT", "unassigned ProjectEvent required")
        with WriterLock(self.lock_path, timeout=self.lock_timeout):
            self._load()
            if self.recovery != "CLEAN":
                raise ProjectJournalError("E_RECOVERY", "repair truncated tail before append")
            event_id = event.derived_event_id
            source_key = event.source_key.digest
            existing_id = self.source_index.get(source_key)
            if existing_id is not None:
                if existing_id == event_id:
                    return AppendReceipt(self.events[existing_id], True)
                raise ProjectJournalError("E_SOURCE_CONFLICT", "same SourceKey has different event bytes")
            assigned = event.assigned(self.generation, self.cursor + 1)
            record = {"kind": "event", "generation": self.generation, "event": assigned.to_mapping()}
            try:
                encoded = json.dumps(record, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
                protocols.check_json_value(record, max_bytes=protocols.DEFAULT_MAX_BYTES)
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("ab") as handle:
                    handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
            except (OSError, TypeError, ValueError, protocols.ProtocolError) as exc:
                raise ProjectJournalError("E_WRITE_UNKNOWN", "journal durability is unknown") from exc
            self._index(assigned); self.cursor = assigned.seq or self.cursor
            return AppendReceipt(assigned, False)

    def repair_tail(self, *, expected_generation: int, expected_cursor: int) -> None:
        if expected_generation != self.generation or expected_cursor != self.cursor:
            raise ProjectJournalError("E_CAS", "journal state changed")
        if self.recovery != "TRUNCATED_TAIL":
            if self.recovery == "CLEAN":
                return
            raise ProjectJournalError("E_RECOVERY", "only truncated tail is repairable")
        with WriterLock(self.lock_path, timeout=self.lock_timeout):
            raw = self.path.read_bytes() if self.path.exists() else b""
            if raw.endswith(b"\n"):
                self.recovery = "CLEAN"; self._load(); return
            boundary = raw.rfind(b"\n") + 1
            with self.path.open("r+b") as handle:
                handle.truncate(boundary); handle.flush(); os.fsync(handle.fileno())
            self._load()

    def handoff(self, *, new_generation: int, expected_generation: int) -> None:
        if expected_generation != self.generation or type(new_generation) is not int or new_generation <= self.generation:
            raise ProjectJournalError("E_GENERATION", "generation must advance from current head")
        self.generation = new_generation; self.cursor = 0; self.events = {}; self.source_index = {}


__all__ = ["AppendReceipt", "ProjectJournal", "ProjectJournalError", "WriterLock"]
