"""Optional observer public facade.

The protocol validators live in :mod:`observer_protocol`; the deterministic
scheduler lives in :mod:`observer_runtime`.  The small value classes below are
kept as an offline compatibility API for tests and fixtures.  None can invoke
a provider or alter project state.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from .observer_protocol import *  # noqa: F401,F403 - public protocol facade
from .planner_protocol import validate_resource_ref
from .observer_runtime import ObserverRuntime, ObserverRuntimeError, RuntimeBudget

ObserverError = ObserverRuntimeError


def _strict(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class ObserverRequest:
    request_id: str
    project_id: str
    source_start: int
    source_end: int
    brief_ref: Mapping[str, Any]
    source_refs: tuple[Mapping[str, Any], ...]
    profile_id: str | None = None
    max_output_chars: int = 8000
    timeout_seconds: int = 30
    retry_limit: int = 0
    observer_max_calls: int = 1
    observer_max_seconds: int = 30

    def __post_init__(self) -> None:
        if type(self.request_id) is not str or not self.request_id:
            raise ObserverError("E_FIELD", "request_id")
        if type(self.project_id) is not str or not self.project_id:
            raise ObserverError("E_FIELD", "project_id")
        if type(self.source_start) is not int or type(self.source_end) is not int or self.source_end < self.source_start:
            raise ObserverError("E_CURSOR_RANGE", "source cursor")
        try:
            validate_resource_ref(dict(self.brief_ref), field="/brief_ref")
            refs = list(self.source_refs)
            for index, ref in enumerate(refs):
                validate_resource_ref(dict(ref), field=f"/source_refs/{index}")
        except Exception as exc:
            raise ObserverError("E_RESOURCE", "invalid observer source reference") from exc

    def to_mapping(self) -> dict[str, Any]:
        return {"request_id": self.request_id, "project_id": self.project_id,
                "source_start": self.source_start, "source_end": self.source_end,
                "brief_ref": dict(self.brief_ref), "source_refs": [dict(v) for v in self.source_refs],
                "profile_id": self.profile_id, "max_output_chars": self.max_output_chars,
                "timeout_seconds": self.timeout_seconds, "retry_limit": self.retry_limit,
                "observer_max_calls": self.observer_max_calls, "observer_max_seconds": self.observer_max_seconds}

    @property
    def dedupe_key(self) -> str:
        value = self.to_mapping(); value.pop("request_id", None)
        return hashlib.sha256(_strict(value)).hexdigest()


@dataclass(frozen=True)
class ObserverResult:
    request_id: str
    source_start: int
    source_end: int
    source_refs: tuple[Mapping[str, Any], ...]
    facts: tuple[Mapping[str, Any], ...] = ()
    hypotheses: tuple[Mapping[str, Any], ...] = ()
    risks: tuple[Mapping[str, Any], ...] = ()
    open_questions: tuple[Mapping[str, Any], ...] = ()
    suggested_next_actions: tuple[Mapping[str, Any], ...] = ()
    omitted: tuple[str, ...] = ()
    status: str = "VALID"

    def __post_init__(self) -> None:
        if type(self.source_start) is not int or type(self.source_end) is not int or self.source_end < self.source_start:
            raise ObserverError("E_CURSOR_RANGE", "source cursor")
        refs = []
        try:
            for index, ref in enumerate(self.source_refs):
                refs.append(validate_resource_ref(dict(ref), field=f"/source_refs/{index}"))
        except Exception as exc:
            raise ObserverError("E_RESOURCE", "invalid observer source reference") from exc
        allowed = {json.dumps(ref, sort_keys=True, separators=(",", ":")) for ref in refs}
        for name in ("facts", "hypotheses", "risks", "open_questions", "suggested_next_actions"):
            for row in getattr(self, name):
                if type(row) is not dict or type(row.get("text")) is not str or not row.get("text"):
                    raise ObserverError("E_OUTPUT", name)
                row_refs = row.get("source_refs", [])
                if name == "facts" and not row_refs:
                    raise ObserverError("E_FACT_SOURCE", name)
                for ref in row_refs:
                    try:
                        normalized = validate_resource_ref(dict(ref), field=f"/{name}/source_refs")
                    except Exception as exc:
                        raise ObserverError("E_RESOURCE", name) from exc
                    if json.dumps(normalized, sort_keys=True, separators=(",", ":")) not in allowed:
                        raise ObserverError("E_SOURCE_SCOPE", name)

    def to_mapping(self) -> dict[str, Any]:
        return {"request_id": self.request_id, "source_start": self.source_start,
                "source_end": self.source_end, "source_refs": [dict(v) for v in self.source_refs],
                "facts": [dict(v) for v in self.facts], "hypotheses": [dict(v) for v in self.hypotheses],
                "risks": [dict(v) for v in self.risks], "open_questions": [dict(v) for v in self.open_questions],
                "suggested_next_actions": [dict(v) for v in self.suggested_next_actions],
                "omitted": list(self.omitted), "status": self.status}


class ObserverScheduler:
    """Compatibility facade around the protocol-shaped offline runtime."""

    def __init__(self, project_id: str, *, max_calls: int = 4, max_seconds: int = 120,
                 observer_max_calls: int = 2, observer_max_seconds: int = 60) -> None:
        self._runtime = ObserverRuntime(project_id, max_calls=max_calls, max_seconds=max_seconds,
                                        observer_max_calls=observer_max_calls,
                                        observer_max_seconds=observer_max_seconds)

    @property
    def high_water(self) -> int:
        return self._runtime.high_water

    @property
    def project_state(self) -> None:
        return self._runtime.project_state

    @property
    def global_budget(self) -> RuntimeBudget:
        return self._runtime.global_budget

    @property
    def observer_budget(self) -> RuntimeBudget:
        return self._runtime.observer_budget

    def ingest_event(self, event: Mapping[str, Any]) -> int:
        return self._runtime.ingest_event(event)

    def reserve(self, request: ObserverRequest):
        # The compatibility shape is converted to the strict protocol shape.
        req = {"record_type": "observer-request", "schema_version": 1,
               "request_id": request.request_id, "project_id": request.project_id,
               "source_cursor": {"start": request.source_start, "end": request.source_end},
               "brief_ref": dict(request.brief_ref), "source_refs": [dict(v) for v in request.source_refs],
               "output_limits": {"max_bytes": request.max_output_chars, "max_items": 256},
               "profile_ref": None, "environment_ref": None,
               "timeout_seconds": request.timeout_seconds, "max_retries": request.retry_limit,
               "budget_reservation_ref": None}
        return self._runtime.submit(req)

    def complete(self, run_id: str, request: ObserverRequest, *, result: ObserverResult | None = None,
                 outcome: str = "success", elapsed_seconds: int | None = None, cost: int | None = None):
        req = {"record_type": "observer-request", "schema_version": 1,
               "request_id": request.request_id, "project_id": request.project_id,
               "source_cursor": {"start": request.source_start, "end": request.source_end},
               "brief_ref": dict(request.brief_ref), "source_refs": [dict(v) for v in request.source_refs],
               "output_limits": {"max_bytes": request.max_output_chars, "max_items": 256},
               "profile_ref": None, "environment_ref": None,
               "timeout_seconds": request.timeout_seconds, "max_retries": request.retry_limit,
               "budget_reservation_ref": None}
        out = None
        if result is not None:
            def entries(values, prefix):
                normalized = []
                for index, value in enumerate(values):
                    row = dict(value)
                    row.setdefault("id", f"{prefix}-{index + 1}")
                    row.setdefault("source_refs", [])
                    if prefix == "hypothesis":
                        row.setdefault("missing_information", ["not provided"])
                        row.setdefault("verification_method", "review source evidence")
                    if prefix == "risk":
                        row.setdefault("impact", "unknown")
                        row.setdefault("affected_task_ids", [])
                    if prefix == "question":
                        row.setdefault("affected_task_ids", [])
                    if prefix == "action":
                        row.setdefault("affected_task_ids", [])
                        row.setdefault("requires_authorization", False)
                    normalized.append(row)
                return normalized
            out = {"record_type": "observer-output", "schema_version": 1,
                   "request_id": result.request_id,
                   "source_cursor": {"start": result.source_start, "end": result.source_end},
                   "brief_ref": dict(request.brief_ref),
                   "facts": entries(result.facts, "fact"),
                   "hypotheses": entries(result.hypotheses, "hypothesis"),
                   "risks": entries(result.risks, "risk"),
                   "open_questions": entries(result.open_questions, "question"),
                   "suggested_next_actions": entries(result.suggested_next_actions, "action"),
                   "omitted": [], "status": "OK" if result.status == "VALID" else "DEGRADED"}
        return self._runtime.finish(run_id, req, output=out, outcome=outcome,
                                   elapsed_seconds=elapsed_seconds, cost=cost)

    def latest(self, *, include_stale: bool = False):
        return self._runtime.latest(include_stale=include_stale)

    def snapshot(self):
        return self._runtime.snapshot()


__all__ = ["ObserverError", "ObserverRequest", "ObserverResult", "ObserverScheduler",
           "ObserverRuntime", "ObserverRuntimeError", "RuntimeBudget"]
