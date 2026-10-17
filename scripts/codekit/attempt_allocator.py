"""Deterministic candidate ordering and all-or-nothing resource allocation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .protocols import MAX_SAFE_INTEGER


class AllocationError(ValueError):
    pass


def _text(value: object, field: str, *, limit: int = 256) -> str:
    """Validate identifiers used by the pure allocator.

    These values are later copied into evidence and diagnostics.  Rejecting
    control characters here keeps a malformed candidate from changing the
    meaning of a line-oriented record while retaining the deliberately broad
    identifier alphabet used by resources.
    """
    if type(value) is not str or not value or len(value) > limit:
        raise AllocationError("E_" + field.upper())
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F or 0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise AllocationError("E_" + field.upper())
    return value


@dataclass(frozen=True)
class Candidate:
    task_id: str
    priority: int
    window_seq: int
    resource_keys: tuple[str, ...] = ()
    budget_available: bool | None = True
    wait_reason: str | None = None

    def __post_init__(self) -> None:
        _text(self.task_id, "task_id")
        if (type(self.priority) is not int or abs(self.priority) > MAX_SAFE_INTEGER
                or type(self.window_seq) is not int or self.window_seq < 0
                or self.window_seq > MAX_SAFE_INTEGER):
            raise AllocationError("E_CANDIDATE")
        if type(self.resource_keys) is not tuple or len(self.resource_keys) > 256:
            raise AllocationError("E_RESOURCE_ORDER")
        for value in self.resource_keys:
            _text(value, "resource_key")
        if len(set(self.resource_keys)) != len(self.resource_keys) or tuple(sorted(self.resource_keys)) != self.resource_keys:
            raise AllocationError("E_RESOURCE_ORDER")
        if type(self.budget_available) not in (bool, type(None)):
            raise AllocationError("E_BUDGET_FACT")
        if self.wait_reason is not None:
            _text(self.wait_reason, "wait_reason")


@dataclass(frozen=True)
class AllocationDecision:
    selected: tuple[Candidate, ...]
    waiting: tuple[tuple[str, str], ...]
    diagnostic: str | None


def order_candidates(candidates: Sequence[Candidate]) -> tuple[Candidate, ...]:
    if type(candidates) not in (list, tuple):
        raise AllocationError("E_CANDIDATES")
    if any(type(candidate) is not Candidate for candidate in candidates):
        raise AllocationError("E_CANDIDATE")
    task_ids = [candidate.task_id for candidate in candidates]
    if len(set(task_ids)) != len(task_ids):
        raise AllocationError("E_CANDIDATE_DUPLICATE")
    return tuple(sorted(candidates, key=lambda item: (-item.priority, item.window_seq, item.task_id)))


def allocate_candidates(candidates: Sequence[Candidate], *, capacity: int, held_resources: Sequence[str] = ()) -> AllocationDecision:
    if type(capacity) is not int or capacity < 0 or capacity > MAX_SAFE_INTEGER:
        raise AllocationError("E_ALLOCATION")
    if type(held_resources) not in (list, tuple) or len(held_resources) > 256:
        raise AllocationError("E_ALLOCATION")
    for value in held_resources:
        _text(value, "resource_key")
    if len(set(held_resources)) != len(held_resources):
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
