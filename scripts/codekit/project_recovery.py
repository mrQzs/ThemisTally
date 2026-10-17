"""Recovery reports and generation rebuilds for the 10 offline journal."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .project_events import ProjectEvent
from .project_journal import ProjectJournal, ProjectJournalError


class RecoveryError(ValueError):
    def __init__(self, code: str, message: str = "recovery rejected") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class RecoveryReport:
    old_generation: int
    new_generation: int
    old_cursor: int
    new_cursor: int
    reset_required: bool
    source_event_count: int
    status: str

    def to_mapping(self) -> dict[str, Any]:
        return {"old_generation": self.old_generation, "new_generation": self.new_generation,
                "old_cursor": self.old_cursor, "new_cursor": self.new_cursor,
                "reset_required": self.reset_required, "source_event_count": self.source_event_count,
                "status": self.status}


def rebuild_generation(source_path: str | Path, target_path: str | Path, *, new_generation: int) -> RecoveryReport:
    """Replay a clean source journal into a new generation and target file.

    The source is never replaced.  Consumers must treat the changed generation
    as a RESET even when all business events are byte-identical.
    """
    source = ProjectJournal(source_path)
    if source.recovery != "CLEAN":
        raise RecoveryError("E_RECOVERY", "repair source tail before rebuild")
    if type(new_generation) is not int or new_generation <= source.generation:
        raise RecoveryError("E_GENERATION", "new generation must advance")
    target = Path(target_path)
    if target.resolve() == Path(source_path).resolve():
        raise RecoveryError("E_TARGET", "rebuild target must be separate from source")
    if target.exists() and target.stat().st_size:
        raise RecoveryError("E_TARGET", "rebuild target must be empty")
    rebuilt = ProjectJournal(target, generation=new_generation)
    events = [source.events[event_id] for event_id in sorted(source.events, key=lambda key: source.events[key].seq or 0)]
    for assigned in events:
        unassigned = replace(assigned, event_id=None, generation=None, seq=None)
        rebuilt.append(unassigned)
    return RecoveryReport(source.generation, new_generation, source.cursor, rebuilt.cursor,
                          True, len(events), "REBUILT")


__all__ = ["RecoveryError", "RecoveryReport", "rebuild_generation"]
