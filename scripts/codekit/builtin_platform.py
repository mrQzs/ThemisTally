"""Offline platform and failure classification adapters."""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Mapping, Sequence
from .builtin_artifacts import ArtifactError

OS_NAMES = {"windows", "wsl", "linux", "macos", "unknown"}
FAILURE_KINDS = {"timeout", "cancelled", "log_missing", "response_missing", "drift", "start_unknown", "environment"}

def _err(code: str, message: str) -> None:
    raise ArtifactError(code, "/platform", message)

def make_platform_observation(*, os_name: str, adapter_id: str, connected: bool = False,
                              command: Sequence[str] | None = None, environment_digest: str | None = None) -> dict[str, Any]:
    if os_name not in OS_NAMES or type(adapter_id) is not str or not adapter_id:
        _err("E_PLATFORM", "known OS and adapter id required")
    if command is not None and (not isinstance(command, list) or any(type(x) is not str or not x for x in command)):
        _err("E_PLATFORM", "command must be a non-empty string list")
    return {"os": os_name, "adapter_id": adapter_id, "connected": bool(connected),
            "execution_mode": "dispatcher" if connected else "REFERENCE_ONLY",
            "command": list(command or []), "environment_digest": environment_digest}

def classify_failure(*, kind: str, detail: str | None = None, expected_generation: int | None = None,
                     observed_generation: int | None = None) -> dict[str, Any]:
    if kind not in FAILURE_KINDS:
        _err("E_FAILURE", "unknown failure kind")
    if kind == "drift" and expected_generation == observed_generation:
        _err("E_FAILURE", "drift requires generation mismatch")
    return {"kind": kind, "detail": detail or kind,
            "recoverable": kind in {"timeout", "cancelled", "log_missing", "response_missing", "start_unknown"},
            "expected_generation": expected_generation, "observed_generation": observed_generation}

def reconcile_failure(observation: Mapping[str, Any], failure: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(observation, Mapping) or not isinstance(failure, Mapping) or failure.get("kind") not in FAILURE_KINDS:
        _err("E_RECONCILE", "observation and failure required")
    kind = failure["kind"]
    if kind in {"drift", "start_unknown"}:
        state, action = "UNKNOWN", "freeze_and_reinspect"
    elif kind in {"timeout", "cancelled"}:
        state, action = "STOPPED", "record_stop_and_cleanup"
    elif kind in {"log_missing", "response_missing"}:
        state, action = "UNKNOWN", "retain_evidence_and_reconcile"
    else:
        state, action = "BLOCKED", "record_environment_block"
    return {"state": state, "action": action, "failure": deepcopy(dict(failure)),
            "production_ready": False}

__all__ = ["FAILURE_KINDS", "OS_NAMES", "classify_failure", "make_platform_observation", "reconcile_failure"]
