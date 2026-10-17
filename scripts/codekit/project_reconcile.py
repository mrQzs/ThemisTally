"""Controlled, idempotent source-to-index reconciliation for 10."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .project_events import ProjectEvent
from .project_journal import AppendReceipt, ProjectJournal, ProjectJournalError


class ReconcileError(ValueError):
    def __init__(self, code: str, message: str = "reconcile rejected") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ReconcileReport:
    generation: int
    start_cursor: int
    end_cursor: int
    appended: int
    replayed: int
    pending: tuple[str, ...]
    conflicts: tuple[str, ...]
    status: str

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "reconcile-report", "schema_version": 1,
                "generation": self.generation, "start_cursor": self.start_cursor,
                "end_cursor": self.end_cursor, "appended": self.appended,
                "replayed": self.replayed, "pending": list(self.pending),
                "conflicts": list(self.conflicts), "status": self.status}


def reconcile_events(journal: ProjectJournal, events: Sequence[ProjectEvent], *,
                     expected_generation: int, expected_cursor: int,
                     source_status: Mapping[str, str]) -> ReconcileReport:
    if type(expected_generation) is not int or type(expected_cursor) is not int:
        raise ReconcileError("E_CAS", "expected generation/cursor required")
    if journal.generation != expected_generation or journal.cursor != expected_cursor:
        raise ReconcileError("E_CAS", "journal head changed before reconciliation")
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise ReconcileError("E_EVENTS", "events sequence required")
    if not isinstance(source_status, Mapping):
        raise ReconcileError("E_SOURCE", "source status mapping required")
    pending: list[str] = []; conflicts: list[str] = []
    appended = replayed = 0; cursor = expected_cursor
    for event in events:
        if type(event) is not ProjectEvent or event.generation is not None or event.seq is not None:
            raise ReconcileError("E_EVENT", "unassigned ProjectEvent required")
        key = event.source_key.digest
        if source_status.get(key) != "verified":
            pending.append(key)
            continue
        try:
            receipt = journal.append(event, expected_generation=expected_generation,
                                     expected_cursor=cursor)
        except ProjectJournalError as exc:
            if exc.code in {"E_SOURCE_CONFLICT", "E_EVENT_CONFLICT"}:
                conflicts.append(key); continue
            raise ReconcileError(exc.code, str(exc)) from exc
        if receipt.replayed:
            replayed += 1
        else:
            appended += 1
        cursor = journal.cursor
    status = "APPLIED" if not pending and not conflicts else ("PARTIAL" if appended or replayed else "BLOCKED")
    return ReconcileReport(expected_generation, expected_cursor, journal.cursor, appended,
                           replayed, tuple(dict.fromkeys(pending)), tuple(dict.fromkeys(conflicts)), status)


__all__ = ["ReconcileError", "ReconcileReport", "reconcile_events"]
