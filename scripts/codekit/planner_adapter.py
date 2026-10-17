"""Deterministic offline planner adapter and static draft checks for 09.

This adapter is intentionally not a provider integration.  It models the
handoff envelope and emits a recorded result event so protocol, truncation and
replay tests can run without credentials or a second CLI.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .planner_protocol import (validate_context_manifest, validate_planner_request,
                               validate_planning_binding, validate_planning_bundle,
                               validate_resource_ref)
from .planner_runtime import PlannerRuntimeError, extract_unique_result
from . import protocols


class AdapterError(ValueError):
    def __init__(self, code: str, message: str = "offline adapter rejected input") -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MUTABLE_ALIASES = frozenset(("latest", "head", "current", "tip", "default"))


def _identity(value: Any, field: str) -> str:
    if type(value) is not str or not value or len(value) > 128 or any(
            ord(ch) < 0x20 or 0x7f <= ord(ch) <= 0x9f or 0xd800 <= ord(ch) <= 0xdfff
            for ch in value):
        raise AdapterError("E_HANDOFF_ID", f"{field} must be non-empty scalar text")
    return value


def _canonical_record(value: Mapping[str, Any]) -> bytes:
    try:
        protocols.check_json_value(value, max_bytes=protocols.DEFAULT_MAX_BYTES)
        raw = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError, protocols.ProtocolError) as exc:
        raise AdapterError("E_HANDOFF_RESULT", "strict bounded JSON object required") from exc
    if len(raw) > protocols.DEFAULT_MAX_BYTES:
        raise AdapterError("E_HANDOFF_RESULT", "result exceeds byte limit")
    return raw


def _immutable_ref(value: Mapping[str, Any], field: str, *, code: str = "E_HANDOFF_REF") -> dict[str, Any]:
    try:
        normalized = validate_resource_ref(value, field=field)
    except Exception as exc:
        raise AdapterError(code, f"{field} must be a ResourceRef") from exc
    if normalized["id"].lower() in _MUTABLE_ALIASES:
        raise AdapterError(code, f"{field} must use an immutable id")
    return normalized


@dataclass(frozen=True)
class PlanningHandoff:
    """Immutable offline binding from a planner result to the 09 boundary.

    This record intentionally carries only references and a content digest. It
    does not allocate a draft id, revision, candidate id, approval, or
    publication.  The 09 ``PlanningService`` receives the validated bundle in
    a separate call and remains the owner of those identities.
    """

    request_id: str
    run_id: str
    operation_id: str
    planner_profile_id: str
    planner_session_id: str
    planner_request_ref: Mapping[str, Any]
    context_manifest_ref: Mapping[str, Any]
    bundle_ref: Mapping[str, Any]
    bundle_sha256: str
    budget_generation: int
    state: str = "READY"
    execution_mode: str = "offline_stub"

    def __post_init__(self) -> None:
        for value, field in ((self.request_id, "request_id"), (self.run_id, "run_id"),
                             (self.operation_id, "operation_id"),
                             (self.planner_profile_id, "planner_profile_id"),
                             (self.planner_session_id, "planner_session_id")):
            _identity(value, field)
        for value, field in ((self.planner_request_ref, "/planner_request_ref"),
                             (self.context_manifest_ref, "/context_manifest_ref"),
                             (self.bundle_ref, "/bundle_ref")):
            normalized = _immutable_ref(value, field)
            object.__setattr__(self, field[1:], normalized)
        if type(self.bundle_sha256) is not str or _SHA256.fullmatch(self.bundle_sha256) is None:
            raise AdapterError("E_HANDOFF_RESULT", "bundle_sha256 must be lowercase SHA-256")
        if self.bundle_ref["sha256"] != self.bundle_sha256:
            raise AdapterError("E_HANDOFF_RESULT", "bundle ref digest does not match bundle_sha256")
        if type(self.budget_generation) is not int or self.budget_generation < 1:
            raise AdapterError("E_HANDOFF_GENERATION", "positive budget generation required")
        if self.state not in {"READY", "BLOCKED", "RECOVERY_REQUIRED"}:
            raise AdapterError("E_HANDOFF_STATE", "unsupported planning handoff state")
        if self.execution_mode not in {"offline_stub", "deterministic_check"}:
            raise AdapterError("E_HANDOFF_MODE", "unsupported execution mode")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "record_type": "planning-handoff",
            "schema_version": 1,
            "request_id": self.request_id,
            "run_id": self.run_id,
            "operation_id": self.operation_id,
            "planner_profile_id": self.planner_profile_id,
            "planner_session_id": self.planner_session_id,
            "planner_request_ref": dict(self.planner_request_ref),
            "context_manifest_ref": dict(self.context_manifest_ref),
            "bundle_ref": dict(self.bundle_ref),
            "bundle_sha256": self.bundle_sha256,
            "budget_generation": self.budget_generation,
            "state": self.state,
            "execution_mode": self.execution_mode,
        }


@dataclass(frozen=True)
class ExecutorHandoff:
    """Closed offline evidence binding for a 09 candidate execution result.

    ``candidate_ref`` and ``report_ref`` are supplied by the owning layers;
    this record only proves that the exact report bytes, invocation identity,
    event sources and check references were retained together.  It never marks
    a candidate accepted and never starts or retries a process.
    """

    request_id: str
    run_id: str
    operation_id: str
    executor_profile_id: str
    executor_session_id: str
    candidate_ref: Mapping[str, Any]
    report_ref: Mapping[str, Any]
    invocation_sha256: str
    result_sha256: str
    event_refs: tuple[Mapping[str, Any], ...]
    check_refs: tuple[Mapping[str, Any], ...]
    status: str
    settled: bool
    budget_generation: int
    state: str = "READY"
    execution_mode: str = "offline_stub"

    def __post_init__(self) -> None:
        for value, field in ((self.request_id, "request_id"), (self.run_id, "run_id"),
                             (self.operation_id, "operation_id"),
                             (self.executor_profile_id, "executor_profile_id"),
                             (self.executor_session_id, "executor_session_id")):
            _identity(value, field)
        refs: list[dict[str, Any]] = []
        for value, field in ((self.candidate_ref, "/candidate_ref"), (self.report_ref, "/report_ref")):
            refs.append(_immutable_ref(value, field, code="E_EXECUTOR_REF"))
        if refs[0] == refs[1]:
            raise AdapterError("E_EXECUTOR_REF", "candidate and report refs must be distinct")
        object.__setattr__(self, "candidate_ref", refs[0]); object.__setattr__(self, "report_ref", refs[1])
        for value, field in ((self.invocation_sha256, "invocation_sha256"),
                             (self.result_sha256, "result_sha256")):
            if type(value) is not str or _SHA256.fullmatch(value) is None:
                raise AdapterError("E_EXECUTOR_DIGEST", f"{field} must be lowercase SHA-256")
        if type(self.event_refs) is not tuple or not self.event_refs:
            raise AdapterError("E_EXECUTOR_EVIDENCE", "at least one event reference is required")
        if type(self.check_refs) is not tuple:
            raise AdapterError("E_EXECUTOR_EVIDENCE", "check references must be a tuple")
        normalized_events = []
        normalized_checks = []
        for values, field, target in ((self.event_refs, "/event_refs", normalized_events),
                                      (self.check_refs, "/check_refs", normalized_checks)):
            seen: set[tuple[Any, ...]] = set()
            for index, value in enumerate(values):
                try:
                    normalized = _immutable_ref(value, f"{field}/{index}", code="E_EXECUTOR_EVIDENCE")
                except AdapterError:
                    raise
                except Exception as exc:
                    raise AdapterError("E_EXECUTOR_EVIDENCE", f"{field} must contain ResourceRefs") from exc
                key = tuple(normalized[name] for name in ("kind", "id", "path", "sha256"))
                if key in seen:
                    raise AdapterError("E_EXECUTOR_EVIDENCE", f"{field} contains duplicate references")
                seen.add(key); target.append(normalized)
        object.__setattr__(self, "event_refs", tuple(normalized_events))
        object.__setattr__(self, "check_refs", tuple(normalized_checks))
        if self.status not in {"SETTLED", "UNKNOWN", "BLOCKED", "START_UNKNOWN"}:
            raise AdapterError("E_EXECUTOR_STATUS", "unsupported execution status")
        if type(self.settled) is not bool:
            raise AdapterError("E_EXECUTOR_STATUS", "settled must be boolean")
        if self.settled != (self.status == "SETTLED"):
            raise AdapterError("E_EXECUTOR_STATUS", "settled and status disagree")
        if type(self.budget_generation) is not int or self.budget_generation < 1:
            raise AdapterError("E_EXECUTOR_GENERATION", "positive budget generation required")
        if self.state not in {"READY", "BLOCKED", "RECOVERY_REQUIRED"}:
            raise AdapterError("E_EXECUTOR_STATE", "unsupported executor handoff state")
        if self.execution_mode not in {"offline_stub", "deterministic_check"}:
            raise AdapterError("E_EXECUTOR_MODE", "unsupported execution mode")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "record_type": "executor-handoff", "schema_version": 1,
            "request_id": self.request_id, "run_id": self.run_id,
            "operation_id": self.operation_id, "executor_profile_id": self.executor_profile_id,
            "executor_session_id": self.executor_session_id,
            "candidate_ref": dict(self.candidate_ref), "report_ref": dict(self.report_ref),
            "invocation_sha256": self.invocation_sha256, "result_sha256": self.result_sha256,
            "event_refs": [dict(ref) for ref in self.event_refs],
            "check_refs": [dict(ref) for ref in self.check_refs],
            "status": self.status, "settled": self.settled,
            "budget_generation": self.budget_generation, "state": self.state,
            "execution_mode": self.execution_mode,
        }


@dataclass(frozen=True)
class InvocationEnvelope:
    request_id: str
    operation_id: str
    role: str
    resource_allowlist: tuple[Mapping[str, Any], ...]
    context_partition: str = "planner"
    capability_level: str = "read-only"

    def to_mapping(self) -> dict[str, Any]:
        if self.role != "planner" or self.context_partition != "planner":
            raise AdapterError("E_ADAPTER_ROLE", "offline planner envelope requires planner role")
        if self.capability_level not in {"read-only", "static-check"}:
            raise AdapterError("E_ADAPTER_CAPABILITY", "unsupported offline capability")
        if not self.request_id or not self.operation_id:
            raise AdapterError("E_ADAPTER_ID", "request and operation identity required")
        return {"request_id": self.request_id, "operation_id": self.operation_id,
                "role": self.role, "context_partition": self.context_partition,
                "capability_level": self.capability_level,
                "resource_allowlist": [dict(ref) for ref in self.resource_allowlist]}


class OfflinePlannerAdapter:
    """A no-network adapter that returns a single deterministic result event."""

    execution_mode = "offline_stub"

    def invoke(self, request: Mapping[str, Any], result: Mapping[str, Any], *,
               envelope: InvocationEnvelope) -> tuple[dict[str, Any], ...]:
        try:
            normalized = validate_planner_request(request)
        except Exception as exc:
            raise AdapterError("E_ADAPTER_REQUEST", str(exc)) from exc
        envelope.to_mapping()
        try:
            protocols.check_json_value(result, max_bytes=protocols.DEFAULT_MAX_BYTES)
            raw = (json.dumps(result, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        except Exception as exc:
            raise AdapterError("E_ADAPTER_RESULT", "result must be strict JSON") from exc
        event_id = hashlib.sha256((normalized["operation_id"] + "\0" + raw.decode("utf-8")).encode("utf-8")).hexdigest()
        return ({"event_id": event_id, "event_type": "planning.result", "payload": dict(result),
                 "complete": True, "terminated": True, "execution_mode": self.execution_mode},)

    def extract(self, events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        try:
            return extract_unique_result(events)
        except PlannerRuntimeError as exc:
            raise AdapterError(exc.code, str(exc)) from exc

    def bind(self, request: Mapping[str, Any], context: Mapping[str, Any],
             events: Sequence[Mapping[str, Any]], *, envelope: InvocationEnvelope,
             planner_profile_id: str, planner_session_id: str,
             planner_request_ref: Mapping[str, Any], bundle_ref: Mapping[str, Any],
             budget_generation: int = 1) -> tuple[PlanningHandoff, dict[str, Any]]:
        """Validate and bind one settled result to the 09 planning boundary.

        The adapter only validates the request/context/result closure.  Draft,
        revision, candidate and publication identities remain allocated by the
        09 service after this function returns.
        """
        return bind_planning_result(
            request, context, events, envelope=envelope,
            planner_profile_id=planner_profile_id,
            planner_session_id=planner_session_id,
            planner_request_ref=planner_request_ref,
            bundle_ref=bundle_ref,
            budget_generation=budget_generation,
        )


def bind_planning_result(request: Mapping[str, Any], context: Mapping[str, Any],
                        events: Sequence[Mapping[str, Any]], *, envelope: InvocationEnvelope,
                        planner_profile_id: str, planner_session_id: str,
                        planner_request_ref: Mapping[str, Any], bundle_ref: Mapping[str, Any],
                        budget_generation: int = 1
                        ) -> tuple[PlanningHandoff, dict[str, Any]]:
    """Create a deterministic planner→09 handoff from offline adapter events.

    A result is accepted only when the request, context manifest and bundle
    agree on request/mode/baseline/requirements, and the caller's bundle
    ``ResourceRef`` hashes the exact canonical bytes.  The function performs no
    filesystem or process operation and does not grant approval or execution.
    """
    try:
        normalized_request = validate_planner_request(request)
        normalized_context = validate_context_manifest(context)
    except Exception as exc:
        raise AdapterError("E_ADAPTER_REQUEST", "planner request/context is invalid") from exc
    if not isinstance(envelope, InvocationEnvelope):
        raise AdapterError("E_ADAPTER_ENVELOPE", "InvocationEnvelope is required")
    try:
        envelope.to_mapping()
    except AdapterError:
        raise
    if envelope.request_id != normalized_request["request_id"]:
        raise AdapterError("E_HANDOFF_REQUEST", "envelope request identity differs")
    if envelope.operation_id != normalized_request["operation_id"]:
        raise AdapterError("E_HANDOFF_OPERATION", "envelope operation identity differs")
    if normalized_context["request_id"] != normalized_request["request_id"]:
        raise AdapterError("E_HANDOFF_REQUEST", "context request identity differs")
    # The adapter's read set must be exactly the context manifest's set.  This
    # catches both missing context inputs and an accidental extra resource.
    try:
        allowed = {json.dumps(dict(ref), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                   for ref in envelope.resource_allowlist}
        context_refs = {json.dumps(dict(ref), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                        for ref in normalized_context["resources"]}
    except (TypeError, ValueError):
        raise AdapterError("E_HANDOFF_SCOPE", "resource allowlist must contain JSON objects")
    if allowed != context_refs:
        raise AdapterError("E_HANDOFF_SCOPE", "resource allowlist must equal context resources")
    try:
        bundle = extract_unique_result(events)
        normalized_bundle = validate_planning_binding(normalized_request, normalized_context, bundle)["bundle"]
    except Exception as exc:
        # Do not leak provider/parser implementation details through the
        # handoff boundary; the underlying event parser still keeps its stable
        # error in ``__cause__`` for local diagnostics.
        if isinstance(exc, AdapterError):
            raise
        raise AdapterError("E_HANDOFF_BUNDLE", "planning result is not bound to request/context") from exc
    raw = _canonical_record(normalized_bundle)
    actual_sha = hashlib.sha256(raw).hexdigest()
    normalized_bundle_ref = _immutable_ref(bundle_ref, "/bundle_ref")
    if normalized_bundle_ref["sha256"] != actual_sha:
        raise AdapterError("E_HANDOFF_RESULT", "bundle_ref does not hash the exact bundle bytes")
    normalized_request_ref = _immutable_ref(planner_request_ref, "/planner_request_ref")
    # The request/context refs are copied into the handoff as provenance; no
    # generated identity or path is invented by this adapter.
    handoff = PlanningHandoff(
        request_id=normalized_request["request_id"],
        run_id=normalized_request["run_id"],
        operation_id=normalized_request["operation_id"],
        planner_profile_id=_identity(planner_profile_id, "planner_profile_id"),
        planner_session_id=_identity(planner_session_id, "planner_session_id"),
        planner_request_ref=normalized_request_ref,
        context_manifest_ref=normalized_request["context_manifest_ref"],
        bundle_ref=normalized_bundle_ref,
        bundle_sha256=actual_sha,
        budget_generation=budget_generation,
        execution_mode="offline_stub",
    )
    return handoff, normalized_bundle


def bind_execution_result(*, request_id: str, run_id: str, operation_id: str,
                          executor_profile_id: str, executor_session_id: str,
                          candidate_ref: Mapping[str, Any], report_ref: Mapping[str, Any],
                          result: Mapping[str, Any], event_refs: Sequence[Mapping[str, Any]],
                          check_refs: Sequence[Mapping[str, Any]], invocation_sha256: str,
                          status: str, settled: bool, budget_generation: int = 1,
                          state: str = "READY") -> ExecutorHandoff:
    """Bind one already-collected offline execution result to 09 identities.

    The function consumes recorded evidence only.  ``report_ref`` must hash
    the exact canonical result object, and at least one event reference is
    required so a status cannot be detached from its source stream.
    """
    try:
        normalized_result = dict(result)
    except (TypeError, ValueError) as exc:
        raise AdapterError("E_EXECUTOR_RESULT", "result object required") from exc
    raw = _canonical_record(normalized_result)
    result_sha = hashlib.sha256(raw).hexdigest()
    normalized_report = _immutable_ref(report_ref, "/report_ref", code="E_EXECUTOR_REF")
    if normalized_report["sha256"] != result_sha:
        raise AdapterError("E_EXECUTOR_RESULT", "report ref does not hash exact result bytes")
    if status != "SETTLED" and settled is True:
        raise AdapterError("E_EXECUTOR_STATUS", "non-settled status cannot claim settled")
    try:
        events = tuple(event_refs)
        checks = tuple(check_refs)
    except TypeError as exc:
        raise AdapterError("E_EXECUTOR_EVIDENCE", "event/check reference sequences required") from exc
    return ExecutorHandoff(
        request_id=_identity(request_id, "request_id"), run_id=_identity(run_id, "run_id"),
        operation_id=_identity(operation_id, "operation_id"),
        executor_profile_id=_identity(executor_profile_id, "executor_profile_id"),
        executor_session_id=_identity(executor_session_id, "executor_session_id"),
        candidate_ref=candidate_ref, report_ref=normalized_report,
        invocation_sha256=invocation_sha256, result_sha256=result_sha,
        event_refs=events, check_refs=checks, status=status, settled=settled,
        budget_generation=budget_generation, state=state, execution_mode="offline_stub",
    )


def ingest_planning_handoff(service: Any, handoff: PlanningHandoff, bundle: Mapping[str, Any], *,
                            contract_ir: Mapping[str, Any], draft_id: str,
                            expected_head: int | None = None, graph_version: int = 1) -> Any:
    """Pass a validated contract draft from a handoff into 09 without publishing.

    The planner's first-level graph/templates are not themselves a v1
    ``ContractIR``.  A caller must therefore supply the separately refined
    ``contract_ir``; this function checks that its task is represented by the
    handed-off graph before calling ``PlanningService.ingest_planning_result``.
    Callers still need a separate review and publication operation.  The
    digest check prevents a different bundle from being substituted after the
    adapter handoff was recorded.
    """
    if not isinstance(handoff, PlanningHandoff):
        raise AdapterError("E_HANDOFF_SCHEMA", "PlanningHandoff is required")
    if handoff.state != "READY":
        raise AdapterError("E_HANDOFF_STATE", "planning handoff is not ready")
    try:
        normalized_bundle = validate_planning_bundle(bundle)
    except Exception as exc:
        raise AdapterError("E_HANDOFF_BUNDLE", "planning bundle is invalid") from exc
    actual_sha = hashlib.sha256(_canonical_record(normalized_bundle)).hexdigest()
    if actual_sha != handoff.bundle_sha256:
        raise AdapterError("E_HANDOFF_RESULT", "bundle bytes differ from handoff")
    if type(contract_ir) is not dict:
        raise AdapterError("E_HANDOFF_CONTRACT", "refined ContractIR mapping is required")
    task_ids = {task["id"] for task in normalized_bundle["task_graph"]["tasks"]}
    task_id = contract_ir.get("task_id")
    if task_id not in task_ids:
        raise AdapterError("E_HANDOFF_CONTRACT", "refined contract task is absent from the handed-off graph")
    if not any(draft.get("task_id") == task_id for draft in normalized_bundle["contract_drafts"]):
        raise AdapterError("E_HANDOFF_CONTRACT", "refined contract task has no handed-off draft")
    ingest = getattr(service, "ingest_planning_result", None)
    if not callable(ingest):
        raise AdapterError("E_HANDOFF_SERVICE", "09 PlanningService ingest operation is required")
    kwargs: dict[str, Any] = {"graph_version": graph_version}
    if expected_head is not None:
        kwargs["expected_head"] = expected_head
    try:
        return ingest(draft_id, contract_ir, **kwargs)
    except Exception as exc:
        raise AdapterError("E_HANDOFF_SERVICE", "09 planning service rejected the bundle") from exc


def validate_static_draft_commands(commands: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Validate command shape only; never execute a draft setup/check."""
    if not isinstance(commands, Sequence) or isinstance(commands, (str, bytes)):
        raise AdapterError("E_STATIC_COMMANDS", "command sequence required")
    output = []
    for index, command in enumerate(commands):
        if not isinstance(command, Mapping) or set(command) - {"id", "argv", "cwd", "timeout_seconds", "required"}:
            raise AdapterError("E_STATIC_COMMANDS", f"command {index} is not closed")
        argv = command.get("argv")
        if not isinstance(argv, list) or not argv or any(type(item) is not str or not item for item in argv):
            raise AdapterError("E_STATIC_COMMANDS", f"command {index} argv is invalid")
        if any(any(ch in token for ch in "&|;<>\r\n") for token in argv):
            raise AdapterError("E_STATIC_COMMANDS", f"command {index} contains shell composition")
        timeout = command.get("timeout_seconds", 600)
        if type(timeout) is not int or timeout < 1:
            raise AdapterError("E_STATIC_COMMANDS", f"command {index} timeout is invalid")
        output.append({"id": command.get("id", f"C{index + 1:02d}"), "argv": list(argv),
                       "cwd": command.get("cwd", "."), "timeout_seconds": timeout,
                       "required": command.get("required", True), "executed": False})
    return tuple(output)


__all__ = ["AdapterError", "ExecutorHandoff", "InvocationEnvelope", "OfflinePlannerAdapter", "PlanningHandoff",
           "bind_execution_result", "bind_planning_result", "ingest_planning_handoff",
           "validate_static_draft_commands"]
