"""Read-only state, brief and outbox/cursor projections for 08."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence
from .builtin_artifacts import ArtifactError


def _err(code: str, message: str) -> None:
    raise ArtifactError(code, "/projection", message)

def _event_id(source: str, event_type: str, payload: Mapping[str, Any]) -> str:
    if type(source) is not str or not source or type(event_type) is not str or not event_type:
        _err("E_EVENT", "source and event_type required")
    raw = json.dumps({"source": source, "type": event_type, "payload": payload}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return sha256(raw).hexdigest()

@dataclass(frozen=True)
class ProjectionEvent:
    seq: int
    source: str
    event_type: str
    payload: Mapping[str, Any]
    event_id: str | None = None

class CursorProjection:
    """Contiguous cursor consumer with idempotent event IDs and rebuild support."""
    def __init__(self, *, generation: int = 1) -> None:
        if type(generation) is not int or generation < 1:
            _err("E_CURSOR", "positive generation required")
        self.generation = generation
        self.cursor = 0
        self.source_vector: dict[str, int] = {}
        self.events: dict[str, dict[str, Any]] = {}

    def consume(self, events: Sequence[ProjectionEvent], *, generation: int) -> str:
        if generation != self.generation:
            _err("E_FENCED", "stale consumer generation")
        expected = self.cursor + 1
        trial = dict(self.events); trial_sources = dict(self.source_vector)
        applied = False
        for event in events:
            if not isinstance(event, ProjectionEvent) or type(event.seq) is not int or event.seq < 1:
                _err("E_EVENT", "valid projection event required")
            calculated = _event_id(event.source, event.event_type, event.payload)
            eid = event.event_id or calculated
            if eid != calculated:
                _err("E_EVENT_ID", "event id mismatch")
            if eid in trial:
                if trial[eid]["payload"] != dict(event.payload):
                    _err("E_EVENT_CONFLICT", "event ID reused with different payload")
                continue
            if event.seq != expected:
                _err("E_EVENT_GAP", "outbox sequence must be contiguous")
            trial[eid] = {"seq": event.seq, "source": event.source, "type": event.event_type,
                          "payload": deepcopy(dict(event.payload))}
            trial_sources[event.source] = event.seq
            expected += 1; applied = True
        if applied:
            self.events, self.source_vector, self.cursor = trial, trial_sources, expected - 1
            return "APPLIED"
        return "REPLAY"

    def rebuild(self, authority_rows: Sequence[Mapping[str, Any]], *, generation: int) -> None:
        if generation != self.generation:
            _err("E_FENCED", "stale consumer generation")
        self.events = {"authority": {"seq": 0, "source": "authority", "type": "rebuild",
                                      "payload": {"rows": deepcopy([dict(x) for x in authority_rows])}}}
        self.source_vector = {}; self.cursor = 0

def project_state(*, cursor: int, source_vector: Mapping[str, int], status: str,
                  issues: Sequence[str] = (), coverage: str = "complete") -> dict[str, Any]:
    if type(cursor) is not int or cursor < 0 or coverage not in {"complete", "partial", "unknown"}:
        _err("E_STATE", "invalid cursor or coverage")
    if status not in {"READY", "PASS", "FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN"}:
        _err("E_STATE", "invalid status")
    issues = list(issues)
    healthy = status in {"READY", "PASS"} and coverage == "complete" and not issues
    return {"cursor": cursor, "source_vector": dict(source_vector), "status": status,
            "coverage": coverage, "issues": issues, "health": "healthy" if healthy else "degraded",
            "dispatch_eligibility": "not_evaluated"}

def render_brief(state: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(state, Mapping):
        _err("E_BRIEF", "state mapping required")
    return {"status": state.get("status", "UNKNOWN"), "health": state.get("health", "degraded"),
            "cursor": state.get("cursor", 0), "coverage": state.get("coverage", "unknown"),
            "issues": list(state.get("issues", [])), "dispatch_eligibility": "not_evaluated"}

__all__ = ["CursorProjection", "ProjectionEvent", "project_state", "render_brief"]
