"""Revision-chain and related-currentness diagnostics for project state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .project_events import ProjectEvent


class HistoryError(ValueError):
    def __init__(self, code: str, message: str = "history rejected") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class RevisionChainReport:
    status: str
    heads: dict[str, str | None]
    issues: tuple[str, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "revision-chain-report", "schema_version": 1,
                "status": self.status, "heads": dict(sorted(self.heads.items())), "issues": list(self.issues)}


def validate_revision_chain(events: Sequence[ProjectEvent], *, entity_field: str = "task_id") -> RevisionChainReport:
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise HistoryError("E_EVENTS", "events sequence required")
    by_id: dict[str, ProjectEvent] = {}
    groups: dict[str, list[ProjectEvent]] = {}
    issues: list[str] = []
    for event in events:
        if type(event) is not ProjectEvent:
            raise HistoryError("E_EVENT", "ProjectEvent sequence required")
        event_id = event.event_id or event.derived_event_id
        by_id[event_id] = event
        key = event.payload.get(entity_field) or event.subject.get(entity_field)
        if type(key) is not str or not key:
            issues.append("entity-missing:" + event_id); continue
        groups.setdefault(key, []).append(event)
    parent: dict[str, str] = {}
    heads: dict[str, str | None] = {}
    group_for_id: dict[str, str] = {}
    for key, chain in sorted(groups.items()):
        revisions: dict[int, str] = {}
        chain_ids = {item.event_id or item.derived_event_id for item in chain}
        group_for_id.update({item_id: key for item_id in chain_ids})
        chain_problem = False
        for event in chain:
            event_id = event.event_id or event.derived_event_id
            revision = event.payload.get("revision", event.producer_revision or event.seq or 0)
            if type(revision) is not int or revision < 0:
                issues.append("revision-invalid:" + event_id); chain_problem = True; continue
            if revision in revisions and revisions[revision] != event_id:
                issues.append("fork:" + key + ":" + str(revision)); chain_problem = True
            revisions[revision] = event_id
            refs = list(event.predecessor_refs)
            if len(refs) > 1:
                issues.append("multiple-predecessors:" + event_id); chain_problem = True
            if refs:
                ref_id = refs[0].get("event_id")
                if type(ref_id) is not str or not ref_id:
                    issues.append("predecessor-invalid:" + event_id); chain_problem = True
                elif ref_id not in by_id:
                    issues.append("predecessor-missing:" + event_id); chain_problem = True
                elif ref_id not in chain_ids:
                    issues.append("cross-scope:" + event_id); chain_problem = True
                else:
                    parent[event_id] = ref_id
        # A chain with a missing/forked predecessor cannot claim a current head.
        if chain_problem:
            heads[key] = None
        elif revisions:
            heads[key] = revisions[max(revisions)]
        else:
            heads[key] = None
    # Detect cycles without relying on recursion depth.
    for start in sorted(parent):
        seen: set[str] = set(); cursor: str | None = start
        while cursor in parent:
            if cursor in seen:
                issues.append("cycle:" + start)
                if start in group_for_id:
                    heads[group_for_id[start]] = None
                break
            seen.add(cursor); cursor = parent[cursor]
    status = "VALID" if not issues else "UNKNOWN"
    return RevisionChainReport(status, heads, tuple(dict.fromkeys(sorted(issues))))


@dataclass(frozen=True)
class CurrentnessObservation:
    status: str
    related_changes: tuple[str, ...]
    unrelated_changes: tuple[str, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "currentness-observation", "schema_version": 1,
                "status": self.status, "related_changes": list(self.related_changes),
                "unrelated_changes": list(self.unrelated_changes)}


def evaluate_currentness(bound_source_ids: Sequence[str], changed_source_ids: Sequence[str]) -> CurrentnessObservation:
    if isinstance(bound_source_ids, (str, bytes)) or isinstance(changed_source_ids, (str, bytes)):
        raise HistoryError("E_BINDING", "source id sequences required")
    bound = {value for value in bound_source_ids if type(value) is str}
    changed = {value for value in changed_source_ids if type(value) is str}
    related = tuple(sorted(bound & changed)); unrelated = tuple(sorted(changed - bound))
    return CurrentnessObservation("STALE" if related else "CURRENT", related, unrelated)


__all__ = ["CurrentnessObservation", "HistoryError", "RevisionChainReport", "evaluate_currentness", "validate_revision_chain"]
