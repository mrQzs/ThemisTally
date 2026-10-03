"""Read-only readiness and outbox projection primitives for 07-S5.

These functions consume trusted facts and append-only event fixtures.  They do
not create acceptance, authorization, billing, or dispatch decisions.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from . import protocols


class ProjectionError(ValueError):
    def __init__(self, code: str, message: str = "projection rejected") -> None:
        self.code = code
        super().__init__(message)


REFINE_FACTS = ("inputs_accepted", "baseline_present", "baseline_authorized")
PLANNER_FACTS = ("planner_authorized", "planner_environment_ok", "planner_budget_ok", "input_locks_ok", "request_open")
EXECUTE_FACTS = ("contract_current", "approval_current", "capabilities_ok", "execution_authorized", "budget_ok", "conflicts_clear")


def _fact(value: Any, name: str) -> bool | None:
    if value is not None and type(value) is not bool:
        raise ProjectionError("E_FACT_TYPE", name)
    return value


@dataclass(frozen=True)
class ReadinessProjection:
    can_refine: bool
    can_start_planner: bool
    can_execute: bool
    reasons: tuple[str, ...]


def project_readiness(facts: Mapping[str, Any]) -> ReadinessProjection:
    """Project three distinct readiness levels while retaining unknown facts."""
    if type(facts) is not dict:
        raise ProjectionError("E_FACTS", "facts object required")
    names = REFINE_FACTS + PLANNER_FACTS + EXECUTE_FACTS
    if set(facts) != set(names):
        raise ProjectionError("E_FACTS", "closed fact set required")
    values = {name: _fact(facts[name], name) for name in names}
    reasons: list[str] = []

    def gate(label: str, items: Sequence[str]) -> bool:
        allowed = True
        for name in items:
            value = values[name]
            if value is not True:
                allowed = False
                reasons.append(("WAIT_" if value is None else "BLOCK_") + label + "_" + name.upper())
        return allowed

    can_refine = gate("REFINE", REFINE_FACTS)
    planner_facts = gate("PLANNER", PLANNER_FACTS) if can_refine else False
    can_start_planner = can_refine and planner_facts
    execute_facts = gate("EXECUTE", EXECUTE_FACTS) if can_start_planner else False
    can_execute = can_start_planner and execute_facts
    return ReadinessProjection(can_refine, can_start_planner, can_execute, tuple(reasons))


def _text(value: Any, field: str, *, code: str = "E_EVENT_ID") -> str:
    """Validate scalar text before it participates in a digest or snapshot.

    Projection identity fields use the same closed text set as the 08
    projections: C0 controls, DEL, the remaining C1 controls, and isolated
    UTF-16 surrogates are never accepted.  ``type`` is intentionally exact so
    subclasses cannot bypass the boundary with coercive JSON behaviour.
    """
    if type(value) is not str or not value or any(
            ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F
            or 0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise ProjectionError(code, field)
    return value


def _safe_int(value: Any, field: str, *, minimum: int = 0,
              code: str = "E_CURSOR") -> int:
    """Require an exact, JSON-safe integer in the supplied range."""
    if type(value) is not int or value < minimum or value > protocols.MAX_SAFE_INTEGER:
        raise ProjectionError(code, field)
    return value


def _canonical(value: Any) -> str:
    try:
        # json.dumps coerces integer mapping keys and tuples.  Projection IDs
        # must describe the exact value that is persisted, so validate the
        # native JSON subset before serializing it.
        protocols.check_json_value(value, max_bytes=protocols.DEFAULT_MAX_BYTES)
    except protocols.ProtocolError as exc:
        raise ProjectionError("E_EVENT_PAYLOAD", "strict bounded JSON required") from exc
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise ProjectionError("E_EVENT_PAYLOAD", "canonical JSON required") from exc


def event_identity(source_key: str, event_type: str, payload: Mapping[str, Any]) -> tuple[str, str]:
    _text(source_key, "source_key")
    _text(event_type, "event_type")
    if not isinstance(payload, Mapping):
        raise ProjectionError("E_EVENT_PAYLOAD", "event payload mapping required")
    try:
        payload_value = dict(payload)
    except (TypeError, ValueError) as exc:
        raise ProjectionError("E_EVENT_PAYLOAD", "event payload mapping required") from exc
    payload_hash = hashlib.sha256(_canonical(payload_value).encode("utf-8")).hexdigest()
    raw = _canonical({"source_key": source_key, "event_type": event_type, "payload_hash": payload_hash}).encode("utf-8")
    return hashlib.sha256(raw).hexdigest(), payload_hash


@dataclass(frozen=True)
class ProjectionEvent:
    seq: int
    source_key: str
    event_type: str
    payload: Mapping[str, Any]
    event_id: str | None = None


class OutboxProjection:
    """Small atomic in-memory consumer suitable for deterministic fixtures."""

    def __init__(self, *, generation: int = 1) -> None:
        self.generation = _safe_int(generation, "positive generation required",
                                    minimum=1, code="E_GENERATION")
        self.indexed_cursor = 0
        self.applied_cursor = 0
        self.source_vector: dict[str, int] = {}
        # Keep the original sequence together with the payload digest.  An
        # event id is content based, so accepting the same id at a different
        # outbox sequence would silently turn a replay into a fabricated
        # delivery and could hide a cursor gap.
        self._events: dict[str, tuple[int, str]] = {}
        self.projection: dict[str, Any] = {"events": {}}

    def consume_batch(self, events: Sequence[ProjectionEvent], *, generation: int) -> str:
        if (type(generation) is not int or not 1 <= generation <= protocols.MAX_SAFE_INTEGER
                or generation != self.generation):
            raise ProjectionError("E_FENCED", "consumer generation is stale")
        if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
            raise ProjectionError("E_EVENT", "event sequence required")
        _safe_int(self.indexed_cursor, "indexed cursor", code="E_CURSOR")
        _safe_int(self.applied_cursor, "applied cursor", code="E_CURSOR")
        if self.applied_cursor > self.indexed_cursor:
            raise ProjectionError("E_CURSOR", "applied cursor exceeds indexed cursor")
        trial_events = dict(self._events)
        trial_projection = deepcopy(self.projection)
        trial_source = dict(self.source_vector)
        expected = self.indexed_cursor + 1
        replayed = True
        for event in events:
            if (type(event) is not ProjectionEvent or type(event.seq) is not int
                    or not 1 <= event.seq <= protocols.MAX_SAFE_INTEGER):
                raise ProjectionError("E_EVENT", "valid projection event required")
            if event.event_id is not None:
                _text(event.event_id, "event_id")
            calculated, payload_hash = event_identity(event.source_key, event.event_type, event.payload)
            event_id = event.event_id or calculated
            if event_id != calculated:
                raise ProjectionError("E_EVENT_ID", "event id mismatch")
            previous = trial_events.get(event_id)
            if previous is not None:
                previous_seq, previous_hash = previous
                if previous_hash != payload_hash or previous_seq != event.seq:
                    raise ProjectionError("E_EVENT_CONFLICT", "event id payload conflict")
                # The duplicate may be in this batch (before the cursor has
                # advanced) or a replay of an already committed event.  In
                # both cases matching the stored sequence is sufficient to
                # distinguish idempotent delivery from a fabricated event.
                continue
            if event.seq != expected:
                raise ProjectionError("E_EVENT_GAP", "outbox sequence must be contiguous")
            trial_events[event_id] = (event.seq, payload_hash)
            trial_projection["events"][event_id] = {"type": event.event_type, "payload": deepcopy(dict(event.payload))}
            trial_source[event.source_key] = event.seq
            expected += 1
            replayed = False
        if events and not replayed:
            new_cursor = expected - 1
            self._events = trial_events
            self.projection = trial_projection
            self.source_vector = trial_source
            self.indexed_cursor = new_cursor
            self.applied_cursor = new_cursor
            return "APPLIED"
        return "REPLAY"

    def rebuild_from_authority(self, rows: Sequence[Mapping[str, Any]], *, generation: int) -> None:
        if (type(generation) is not int or not 1 <= generation <= protocols.MAX_SAFE_INTEGER
                or generation != self.generation):
            raise ProjectionError("E_FENCED", "consumer generation is stale")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise ProjectionError("E_REBUILD", "authority rows sequence required")
        if any(not isinstance(row, Mapping) for row in rows):
            raise ProjectionError("E_REBUILD", "authority rows must be mappings")
        try:
            authority_rows = [dict(row) for row in rows]
            for row in authority_rows:
                if "event_id" in row:
                    _text(row["event_id"], "event_id", code="E_REBUILD")
            protocols.check_json_value(authority_rows, max_bytes=protocols.DEFAULT_MAX_BYTES)
        except (TypeError, ValueError) as exc:
            raise ProjectionError("E_REBUILD", "authority rows must be JSON mappings") from exc
        except protocols.ProtocolError as exc:
            raise ProjectionError("E_REBUILD", "authority rows must be strict JSON") from exc
        self.projection = {"authority_rows": deepcopy(authority_rows), "events": {}}
        self._events.clear()
        self.source_vector.clear()
        self.indexed_cursor = 0
        self.applied_cursor = 0


def project_state(*, indexed_cursor: int, applied_cursor: int, source_vector: Mapping[str, int],
                  verification_ref: str, as_of: str, source_coverage: str, issues: Sequence[str],
                  budget_coverage: str, start_unknown: bool = False, revoked: bool = False,
                  truncated: bool = False) -> dict[str, Any]:
    """Build a read model whose dispatch field is deliberately non-authoritative."""
    _safe_int(indexed_cursor, "indexed cursor", code="E_CURSOR")
    _safe_int(applied_cursor, "applied cursor", code="E_CURSOR")
    if applied_cursor > indexed_cursor:
        raise ProjectionError("E_CURSOR", "cursors must be non-negative and applied must not exceed indexed")
    if not isinstance(source_vector, Mapping):
        raise ProjectionError("E_SOURCE_VECTOR", "source vector must map names to non-negative cursors")
    for key, value in source_vector.items():
        try:
            _text(key, "source_vector key", code="E_SOURCE_VECTOR")
            _safe_int(value, "source vector cursor", code="E_SOURCE_VECTOR")
            if value > indexed_cursor:
                raise ProjectionError("E_SOURCE_VECTOR", "source vector cursor exceeds indexed cursor")
        except ProjectionError as exc:
            if exc.code == "E_SOURCE_VECTOR":
                raise
            raise ProjectionError("E_SOURCE_VECTOR", "source vector must map names to non-negative cursors") from exc
    try:
        _text(verification_ref, "verification_ref", code="E_STATE")
        _text(as_of, "as_of", code="E_STATE")
    except ProjectionError as exc:
        raise ProjectionError("E_STATE", "verification reference and timestamp are required") from exc
    if (type(source_coverage) is not str or source_coverage not in {"complete", "partial", "unknown"}
            or type(budget_coverage) is not str or budget_coverage not in {"complete", "partial", "unknown"}):
        raise ProjectionError("E_COVERAGE", "unsupported coverage")
    if isinstance(issues, (str, bytes)) or not isinstance(issues, Sequence):
        raise ProjectionError("E_ISSUES", "issues must be a sequence of non-empty strings")
    for issue in issues:
        try:
            _text(issue, "issue", code="E_ISSUES")
        except ProjectionError as exc:
            raise ProjectionError("E_ISSUES", "issues must be a sequence of non-empty strings") from exc
    if type(start_unknown) is not bool or type(revoked) is not bool or type(truncated) is not bool:
        raise ProjectionError("E_STATE", "boolean state flags required")
    degraded = source_coverage != "complete" or budget_coverage != "complete" or start_unknown or revoked or bool(issues)
    return {
        "indexed_cursor": indexed_cursor, "applied_cursor": applied_cursor,
        "source_vector": dict(source_vector), "verification_ref": verification_ref,
        "as_of": as_of, "source_coverage": source_coverage,
        "budget_coverage": budget_coverage, "issues": list(issues),
        "health": "degraded" if degraded else "healthy",
        "dispatch_eligibility": "not_evaluated", "truncated": bool(truncated),
    }


def render_brief(state: Mapping[str, Any]) -> dict[str, Any]:
    """Render a pull-only brief; it cannot grant an execution decision."""
    if type(state) is not dict:
        raise ProjectionError("E_STATE", "state object required")
    health = state.get("health", "degraded")
    source_coverage = state.get("source_coverage", "unknown")
    issues = state.get("issues", [])
    truncated = state.get("truncated", False)
    if (type(health) is not str or health not in {"healthy", "degraded"}
            or type(source_coverage) is not str or source_coverage not in {"complete", "partial", "unknown"}):
        raise ProjectionError("E_STATE", "invalid health or source coverage")
    if (isinstance(issues, (str, bytes)) or not isinstance(issues, Sequence)
            or any(type(item) is not str or not item
                   or any(ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F
                          or 0xD800 <= ord(ch) <= 0xDFFF for ch in item)
                   for item in issues)):
        raise ProjectionError("E_ISSUES", "issues must be a sequence of non-empty strings")
    if type(truncated) is not bool:
        raise ProjectionError("E_STATE", "truncated must be boolean")
    budget = "[未知] 无可核验预算快照" if state.get("budget_coverage") != "complete" else "预算快照已核验"
    return {"health": health, "dispatch_eligibility": "not_evaluated",
            "source_coverage": source_coverage, "budget": budget,
            "issues": list(issues), "truncated": truncated}


__all__ = ["OutboxProjection", "ProjectionError", "ProjectionEvent", "ReadinessProjection",
           "event_identity", "project_readiness", "project_state", "render_brief"]
