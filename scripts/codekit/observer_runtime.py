"""Offline scheduling runtime for optional observer (module 13).

The runtime is intentionally provider-free.  It reserves a bounded observer
request, serializes the same project/range input, and records only immutable
run outcomes.  Event ingestion increments a high-water cursor but never
reduces or mutates the project state projection.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import json
from typing import Any, Mapping

from .observer_protocol import validate_observer_request, validate_observer_output
from .protocols import ProtocolError, check_json_value


class ObserverRuntimeError(ValueError):
    def __init__(self, code: str, message: str = "observer runtime rejected request") -> None:
        self.code = code
        super().__init__(message)


def _canonical(value: Any) -> bytes:
    try:
        check_json_value(value)
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise ObserverRuntimeError("E_JSON", "strict bounded JSON required") from exc


@dataclass(frozen=True)
class RuntimeBudget:
    max_calls: int
    max_seconds: int
    used_calls: int = 0
    used_seconds: int = 0
    unknown_cost: bool = False
    stopped: bool = False


@dataclass(frozen=True)
class ObserverRun:
    run_id: str
    dedupe_key: str
    request_id: str
    status: str
    source_cursor: Mapping[str, Any]
    reserved_calls: int
    reserved_seconds: int
    result: Mapping[str, Any] | None = None
    failure_code: str | None = None
    elapsed_seconds: int | None = None
    cost: int | None = None


class ObserverRuntime:
    """Deterministic single-flight/dedupe model; no project-state authority."""

    def __init__(self, project_id: str, *, max_calls: int = 4, max_seconds: int = 120,
                 observer_max_calls: int = 2, observer_max_seconds: int = 60) -> None:
        if type(project_id) is not str or not project_id:
            raise ObserverRuntimeError("E_PROJECT", "project_id required")
        self.project_id = project_id
        self.global_budget = RuntimeBudget(max_calls, max_seconds)
        self.observer_budget = RuntimeBudget(observer_max_calls, observer_max_seconds)
        self.high_water = 0
        self._events: list[dict[str, Any]] = []
        self._runs: dict[str, ObserverRun] = {}
        self._active: dict[str, str] = {}
        self._dedupe: dict[str, str] = {}
        self._next_id = 1

    @property
    def project_state(self) -> None:
        """Observer has no project-state write capability by construction."""
        return None

    def ingest_event(self, event: Mapping[str, Any]) -> int:
        if type(event) is not dict:
            raise ObserverRuntimeError("E_EVENT", "event object required")
        try:
            check_json_value(event)
        except Exception as exc:
            raise ObserverRuntimeError("E_EVENT", "event must be strict JSON") from exc
        self.high_water += 1
        stored = copy.deepcopy(dict(event))
        stored["cursor"] = self.high_water
        self._events.append(stored)
        return self.high_water

    @staticmethod
    def dedupe_key(request: Mapping[str, Any]) -> str:
        try:
            normalized = validate_observer_request(dict(request))
        except ProtocolError as exc:
            raise ObserverRuntimeError("E_REQUEST", str(exc)) from exc
        normalized.pop("request_id", None)
        return hashlib.sha256(_canonical(normalized)).hexdigest()

    def submit(self, request: Mapping[str, Any]) -> ObserverRun:
        try:
            normalized = validate_observer_request(dict(request))
        except ProtocolError as exc:
            raise ObserverRuntimeError("E_REQUEST", str(exc)) from exc
        if normalized.get("project_id", self.project_id) != self.project_id:
            raise ObserverRuntimeError("E_PROJECT_SCOPE", "project_id mismatch")
        cursor = normalized["source_cursor"]
        if cursor["end"] > self.high_water:
            raise ObserverRuntimeError("E_CURSOR_FUTURE", "request end exceeds high-water")
        key = self.dedupe_key(normalized)
        prior = self._dedupe.get(key)
        if prior is not None:
            return self._runs[prior]
        if self.global_budget.stopped or self.observer_budget.stopped:
            raise ObserverRuntimeError("E_BUDGET_STOPPED", "observer budget stopped")
        timeout = normalized["timeout_seconds"]
        if self.global_budget.used_calls + 1 > self.global_budget.max_calls or self.observer_budget.used_calls + 1 > self.observer_budget.max_calls:
            self._stop("CALL_BUDGET_EXCEEDED")
            raise ObserverRuntimeError("E_BUDGET_EXCEEDED", "observer call budget exceeded")
        if self.global_budget.used_seconds + timeout > self.global_budget.max_seconds or self.observer_budget.used_seconds + timeout > self.observer_budget.max_seconds:
            self._stop("TIME_BUDGET_EXCEEDED")
            raise ObserverRuntimeError("E_BUDGET_EXCEEDED", "observer time budget exceeded")
        run = ObserverRun(
            run_id=f"observer-run-{self._next_id}", dedupe_key=key,
            request_id=normalized["request_id"], status="RESERVED",
            source_cursor=copy.deepcopy(cursor), reserved_calls=1,
            reserved_seconds=timeout,
        )
        self._next_id += 1
        self._runs[run.run_id] = run
        self._active[key] = run.run_id
        self._dedupe[key] = run.run_id
        self.global_budget = RuntimeBudget(self.global_budget.max_calls, self.global_budget.max_seconds,
                                           self.global_budget.used_calls + 1,
                                           self.global_budget.used_seconds + timeout,
                                           self.global_budget.unknown_cost,
                                           self.global_budget.stopped)
        self.observer_budget = RuntimeBudget(self.observer_budget.max_calls, self.observer_budget.max_seconds,
                                             self.observer_budget.used_calls + 1,
                                             self.observer_budget.used_seconds + timeout,
                                             self.observer_budget.unknown_cost,
                                             self.observer_budget.stopped)
        return run

    def finish(self, run_id: str, request: Mapping[str, Any], *, output: Mapping[str, Any] | None = None,
               outcome: str = "success", elapsed_seconds: int | None = None,
               cost: int | None = None) -> ObserverRun:
        run = self._runs.get(run_id)
        if run is None:
            raise ObserverRuntimeError("E_RUN", "unknown run")
        if run.status != "RESERVED":
            return run
        try:
            normalized = validate_observer_request(dict(request))
        except ProtocolError as exc:
            raise ObserverRuntimeError("E_REQUEST", str(exc)) from exc
        if normalized["request_id"] != run.request_id:
            raise ObserverRuntimeError("E_BINDING", "request id mismatch")
        if outcome not in {"success", "timeout", "cancelled", "response_lost", "protocol_error", "failed"}:
            raise ObserverRuntimeError("E_OUTCOME", "unknown outcome")
        if elapsed_seconds is not None and (type(elapsed_seconds) is not int or elapsed_seconds < 0):
            raise ObserverRuntimeError("E_ELAPSED", "elapsed_seconds must be non-negative")
        if outcome == "success" and elapsed_seconds is not None and elapsed_seconds > normalized["timeout_seconds"]:
            # A late provider reply cannot turn a timeout into a successful
            # observer result; keep the response as an untrusted late fact.
            outcome = "timeout"
        status = "COMPLETED"
        failure = None
        normalized_output = None
        if outcome == "success":
            if output is None:
                raise ObserverRuntimeError("E_OUTPUT", "success requires output")
            try:
                normalized_output = validate_observer_output(dict(output), request=normalized)
            except ProtocolError as exc:
                raise ObserverRuntimeError("E_OUTPUT", str(exc)) from exc
            end = normalized_output["source_cursor"]["end"]
            if end > self.high_water:
                raise ObserverRuntimeError("E_CURSOR_FUTURE", "output cursor exceeds high-water")
            if end != normalized["source_cursor"]["end"]:
                raise ObserverRuntimeError("E_CURSOR_BINDING", "output cursor differs from request")
        else:
            status = {"timeout": "TIMED_OUT", "cancelled": "CANCELLED",
                      "response_lost": "RESPONSE_LOST"}.get(outcome, "FAILED")
            failure = "OBSERVER_" + outcome.upper()
            # A timeout, cancellation, or lost response does not prove that
            # the provider stopped before consuming resources.  Keep the
            # liability unknown and mechanically stop further admissions until
            # a reconciler supplies an explicit settlement.
            if outcome in {"timeout", "cancelled", "response_lost"} and cost is None:
                self._unknown_cost_stop()
        if cost is not None and (type(cost) is not int or cost < 0):
            raise ObserverRuntimeError("E_COST", "cost must be non-negative")
        result = ObserverRun(run.run_id, run.dedupe_key, run.request_id, status,
                             copy.deepcopy(run.source_cursor), run.reserved_calls,
                             run.reserved_seconds, normalized_output, failure,
                             elapsed_seconds, cost)
        self._runs[run_id] = result
        self._active.pop(run.dedupe_key, None)
        # A failed run may be explicitly retried, but budget is consumed and
        # the original result remains in history.
        if status != "COMPLETED":
            self._dedupe.pop(run.dedupe_key, None)
        return result

    def latest(self, *, include_stale: bool = False) -> ObserverRun | None:
        rows = [run for run in self._runs.values() if run.status == "COMPLETED" and run.result is not None]
        if not rows:
            return None
        rows.sort(key=lambda row: int(row.run_id.rsplit("-", 1)[1]))
        row = rows[-1]
        if include_stale or row.source_cursor["end"] == self.high_water:
            return row
        return ObserverRun(row.run_id, row.dedupe_key, row.request_id, "STALE",
                           row.source_cursor, row.reserved_calls, row.reserved_seconds,
                           row.result, "NEW_EVENTS_AFTER_RESULT", row.elapsed_seconds,
                           row.cost)

    def snapshot(self) -> dict[str, Any]:
        return {"project_id": self.project_id, "high_water": self.high_water,
                "global_budget": self.global_budget.__dict__.copy(),
                "observer_budget": self.observer_budget.__dict__.copy(),
                "runs": [copy.deepcopy(run.__dict__) for run in self._runs.values()]}

    def _stop(self, reason: str) -> None:
        self.global_budget = RuntimeBudget(self.global_budget.max_calls, self.global_budget.max_seconds,
                                           self.global_budget.used_calls, self.global_budget.used_seconds,
                                           self.global_budget.unknown_cost, True)
        self.observer_budget = RuntimeBudget(self.observer_budget.max_calls, self.observer_budget.max_seconds,
                                             self.observer_budget.used_calls, self.observer_budget.used_seconds,
                                             self.observer_budget.unknown_cost, True)

    def _unknown_cost_stop(self) -> None:
        self.global_budget = RuntimeBudget(self.global_budget.max_calls, self.global_budget.max_seconds,
                                           self.global_budget.used_calls, self.global_budget.used_seconds, True, True)
        self.observer_budget = RuntimeBudget(self.observer_budget.max_calls, self.observer_budget.max_seconds,
                                             self.observer_budget.used_calls, self.observer_budget.used_seconds, True, True)


__all__ = ["ObserverRuntimeError", "RuntimeBudget", "ObserverRun", "ObserverRuntime"]
