"""Deterministic offline planner adapter and static draft checks for 09.

This adapter is intentionally not a provider integration.  It models the
handoff envelope and emits a recorded result event so protocol, truncation and
replay tests can run without credentials or a second CLI.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from .planner_protocol import validate_planner_request
from .planner_runtime import PlannerRuntimeError, extract_unique_result
from . import protocols


class AdapterError(ValueError):
    def __init__(self, code: str, message: str = "offline adapter rejected input") -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


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


__all__ = ["AdapterError", "InvocationEnvelope", "OfflinePlannerAdapter", "validate_static_draft_commands"]
