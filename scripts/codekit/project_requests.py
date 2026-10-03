"""Exact request-to-event mapping; no similarity or summary matching."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .project_events import ProjectEvent


class RequestMappingError(ValueError):
    def __init__(self, code: str, message: str = "request mapping rejected") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class RequestProjection:
    request_id: str
    matched_event_ids: tuple[str, ...]
    unknown_event_ids: tuple[str, ...]
    foreign_event_ids: tuple[str, ...]
    mapping_method: str = "exact_request_id"

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "request-projection", "schema_version": 1,
                "request_id": self.request_id, "matched_event_ids": list(self.matched_event_ids),
                "unknown_event_ids": list(self.unknown_event_ids), "foreign_event_ids": list(self.foreign_event_ids),
                "mapping_method": self.mapping_method}


def project_request(events: Sequence[ProjectEvent], *, request_id: str) -> RequestProjection:
    if type(request_id) is not str or not request_id:
        raise RequestMappingError("E_REQUEST", "request_id required")
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise RequestMappingError("E_EVENTS", "events sequence required")
    matched: list[str] = []; unknown: list[str] = []; foreign: list[str] = []
    for event in events:
        if type(event) is not ProjectEvent:
            raise RequestMappingError("E_EVENT", "ProjectEvent sequence required")
        event_id = event.event_id or event.derived_event_id
        if event.request_id is None:
            unknown.append(event_id)
        elif event.request_id == request_id:
            matched.append(event_id)
        else:
            foreign.append(event_id)
    return RequestProjection(request_id, tuple(matched), tuple(unknown), tuple(foreign))


__all__ = ["RequestMappingError", "RequestProjection", "project_request"]
