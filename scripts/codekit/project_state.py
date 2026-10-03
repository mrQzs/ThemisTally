"""Deterministic, read-only project state reduction for 10.

The reducer consumes already indexed ProjectEvents.  It never creates an
approval, budget reservation, dispatch decision, or external side effect.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import json
from typing import Any, Mapping, Sequence

from .project_events import ProjectEvent, ProjectEventError, canonical_bytes


class ProjectStateError(ValueError):
    def __init__(self, code: str, message: str = "project state rejected") -> None:
        self.code = code
        super().__init__(message)


TASK_STATUSES = ("UNKNOWN", "PENDING", "ACCEPTED", "COMPLETED", "INTEGRATED", "SUPERSEDED")
DECISION_STATUSES = ("PROPOSED", "ACCEPTED", "REVOKED", "EXPIRED", "UNKNOWN")


@dataclass(frozen=True)
class ProjectState:
    indexed_cursor: int
    applied_cursor: int
    source_vector: dict[str, int]
    source_coverage: str
    budget_coverage: str
    verification_ref: str
    as_of: str
    tasks: dict[str, dict[str, Any]]
    decisions: dict[str, dict[str, Any]]
    budgets: dict[str, dict[str, Any]]
    issues: tuple[str, ...]
    dispatch_eligibility: str = "not_evaluated"

    def to_mapping(self) -> dict[str, Any]:
        return {
            "indexed_cursor": self.indexed_cursor,
            "applied_cursor": self.applied_cursor,
            "source_vector": dict(sorted(self.source_vector.items())),
            "source_coverage": self.source_coverage,
            "budget_coverage": self.budget_coverage,
            "verification_ref": self.verification_ref,
            "as_of": self.as_of,
            "tasks": copy.deepcopy(dict(sorted(self.tasks.items()))),
            "decisions": copy.deepcopy(dict(sorted(self.decisions.items()))),
            "budgets": copy.deepcopy(dict(sorted(self.budgets.items()))),
            "issues": list(self.issues),
            "dispatch_eligibility": self.dispatch_eligibility,
        }

    @property
    def health(self) -> str:
        return "healthy" if self.source_coverage == "complete" and self.budget_coverage == "complete" and not self.issues else "degraded"


def _error(code: str, message: str) -> None:
    raise ProjectStateError(code, message)


def _safe_key(value: Any) -> str | None:
    if type(value) is not str or not value or any(ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F or 0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        return None
    return value


def _revision(payload: Mapping[str, Any], event: ProjectEvent) -> int:
    value = payload.get("revision", event.producer_revision or event.seq or 0)
    if type(value) is not int or value < 0:
        return event.producer_revision or event.seq or 0
    return value


def reduce_project_events(events: Sequence[ProjectEvent], *, verification_ref: str,
                          as_of: str, verification: Mapping[str, str] | None = None) -> ProjectState:
    """Reduce one contiguous indexed event sequence into a deterministic state."""
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        _error("E_EVENTS", "events sequence required")
    if type(verification_ref) is not str or not verification_ref:
        _error("E_STATE", "verification_ref required")
    if type(as_of) is not str or not as_of:
        _error("E_STATE", "as_of required")
    seen: dict[str, ProjectEvent] = {}
    source_ids: dict[str, str] = {}
    tasks: dict[str, dict[str, Any]] = {}
    decisions: dict[str, dict[str, Any]] = {}
    budgets: dict[str, dict[str, Any]] = {}
    source_vector: dict[str, int] = {}
    issues: list[str] = []
    expected = 1
    for event in events:
        if type(event) is not ProjectEvent or event.generation is None or event.seq is None:
            _error("E_EVENT", "assigned ProjectEvent required")
        event_id = event.event_id or event.derived_event_id
        previous = seen.get(event_id)
        if previous is not None:
            if previous.to_mapping() != event.to_mapping():
                _error("E_EVENT_CONFLICT", "event id reused with different bytes")
            # API retries may repeat an already indexed row; it cannot advance
            # the cursor or any completion/budget count.
            continue
        if event.seq != expected:
            _error("E_CURSOR_GAP", "events must be sorted and contiguous")
        expected += 1
        source_key = event.source_key.digest
        prior_source = source_ids.get(source_key)
        if prior_source is not None and prior_source != event_id:
            issues.append("source-conflict:" + source_key)
            continue
        source_ids[source_key] = event_id
        seen[event_id] = event
        source_vector[event.producer_namespace] = max(source_vector.get(event.producer_namespace, 0), event.producer_revision or event.seq)
        subject = dict(event.subject)
        payload = dict(event.payload)
        task_id = _safe_key(payload.get("task_id") or subject.get("task_id"))
        revision = _revision(payload, event)
        if event.event_type.startswith("task.") and task_id is not None:
            status = {"task.started": "PENDING", "task.accepted": "ACCEPTED", "task.completed": "COMPLETED",
                      "task.integrated": "INTEGRATED", "task.superseded": "SUPERSEDED"}.get(event.event_type)
            if status is None:
                issues.append("unknown-task-event:" + event.event_type)
            else:
                current = tasks.get(task_id)
                if current is None or revision > current["revision"]:
                    tasks[task_id] = {"status": status, "revision": revision, "event_id": event_id,
                                      "source_key": source_key}
                elif revision == current["revision"] and status != current["status"]:
                    issues.append("task-revision-conflict:" + task_id)
            continue
        if event.event_type == "decision.observed":
            decision_id = _safe_key(payload.get("decision_id") or subject.get("decision_id"))
            if decision_id is None:
                issues.append("decision-id-missing")
                continue
            status = payload.get("status", "UNKNOWN")
            if status not in DECISION_STATUSES:
                status = "UNKNOWN"; issues.append("decision-status-unknown:" + decision_id)
            current = decisions.get(decision_id)
            if current is None or revision > current["revision"]:
                decisions[decision_id] = {"status": status, "revision": revision, "event_id": event_id,
                                           "source_key": source_key, "payload": copy.deepcopy(payload)}
            elif revision == current["revision"] and canonical_bytes(payload) != canonical_bytes(current.get("payload", {})):
                issues.append("decision-revision-conflict:" + decision_id)
            continue
        if event.event_type == "budget.snapshot.observed":
            ledger_id = _safe_key(payload.get("ledger_id") or subject.get("ledger_id"))
            if ledger_id is None:
                issues.append("budget-ledger-id-missing"); continue
            ledger_revision = payload.get("ledger_revision", revision)
            if type(ledger_revision) is not int or ledger_revision < 0:
                issues.append("budget-revision-invalid:" + ledger_id); continue
            current = budgets.get(ledger_id)
            if current is None or ledger_revision > current["ledger_revision"]:
                budgets[ledger_id] = {"ledger_revision": ledger_revision, "event_id": event_id,
                                      "source_key": source_key, "snapshot": copy.deepcopy(payload)}
            elif ledger_revision == current["ledger_revision"] and canonical_bytes(payload) != canonical_bytes(current["snapshot"]):
                issues.append("budget-revision-conflict:" + ledger_id)
            continue
    verification = {} if verification is None else dict(verification)
    verification_values = set(verification.values())
    if not verification:
        source_coverage = "unknown" if seen else "complete"
    elif all(value == "verified" for value in verification_values):
        source_coverage = "complete"
    else:
        source_coverage = "partial"
        issues.extend("source-" + key + ":" + value for key, value in sorted(verification.items()) if value != "verified")
    budget_coverage = "complete" if budgets and not any(issue.startswith("budget-") for issue in issues) else ("unknown" if not budgets else "partial")
    return ProjectState(expected - 1, expected - 1, source_vector, source_coverage, budget_coverage,
                        verification_ref, as_of, tasks, decisions, budgets,
                        tuple(dict.fromkeys(issues)))


__all__ = ["DECISION_STATUSES", "ProjectState", "ProjectStateError", "TASK_STATUSES", "reduce_project_events"]
