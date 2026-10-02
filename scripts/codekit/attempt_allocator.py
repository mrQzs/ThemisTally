"""Deterministic candidate ordering and all-or-nothing resource allocation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


class AllocationError(ValueError):
    pass


@dataclass(frozen=True)
class Candidate:
    task_id: str
    priority: int
    window_seq: int
    resource_keys: tuple[str, ...] = ()
    budget_available: bool | None = True
    wait_reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.task_id) is not str or not self.task_id or type(self.priority) is not int or type(self.window_seq) is not int or self.window_seq < 0:
            raise AllocationError("E_CANDIDATE")
        if len(set(self.resource_keys)) != len(self.resource_keys) or tuple(sorted(self.resource_keys)) != self.resource_keys:
            raise AllocationError("E_RESOURCE_ORDER")
        if type(self.budget_available) not in (bool, type(None)):
            raise AllocationError("E_BUDGET_FACT")


@dataclass(frozen=True)
class AllocationDecision:
    selected: tuple[Candidate, ...]
    waiting: tuple[tuple[str, str], ...]
    diagnostic: str | None


def order_candidates(candidates: Sequence[Candidate]) -> tuple[Candidate, ...]:
    if type(candidates) not in (list, tuple):
        raise AllocationError("E_CANDIDATES")
    return tuple(sorted(candidates, key=lambda item: (-item.priority, item.window_seq, item.task_id)))


def allocate_candidates(candidates: Sequence[Candidate], *, capacity: int, held_resources: Sequence[str] = ()) -> AllocationDecision:
    if type(capacity) is not int or capacity < 0 or len(set(held_resources)) != len(held_resources):
        raise AllocationError("E_ALLOCATION")
    held = set(held_resources)
    selected: list[Candidate] = []
    waiting: list[tuple[str, str]] = []
    for candidate in order_candidates(candidates):
        if len(selected) >= capacity:
            waiting.append((candidate.task_id, "WAIT_CONCURRENCY"))
            continue
        if candidate.wait_reason:
            waiting.append((candidate.task_id, candidate.wait_reason))
            continue
        if candidate.budget_available is not True:
            waiting.append((candidate.task_id, "WAIT_BUDGET" if candidate.budget_available is None else "WAIT_BUDGET_EXHAUSTED"))
            continue
        if held.intersection(candidate.resource_keys):
            waiting.append((candidate.task_id, "WAIT_RESOURCE"))
            continue
        selected.append(candidate)
        held.update(candidate.resource_keys)
    diagnostic = None
    if not selected:
        reasons = [reason for _, reason in waiting]
        diagnostic = "RECOVERY_REQUIRED" if "RECOVERY_REQUIRED" in reasons else (reasons[0] if reasons else "WAIT_UPSTREAM")
    return AllocationDecision(tuple(selected), tuple(waiting), diagnostic)


__all__ = ["AllocationDecision", "AllocationError", "Candidate", "allocate_candidates", "order_candidates"]
