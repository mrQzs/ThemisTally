"""Offline platform and failure classification adapters."""
from __future__ import annotations
from copy import deepcopy
import re
from typing import Any, Mapping, Sequence
from .builtin_artifacts import ArtifactError

OS_NAMES = {"windows", "wsl", "linux", "macos", "unknown"}
FAILURE_KINDS = {"timeout", "cancelled", "log_missing", "response_missing", "drift", "start_unknown", "environment"}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

def _err(code: str, message: str) -> None:
    raise ArtifactError(code, "/platform", message)

def make_platform_observation(*, os_name: str, adapter_id: str, connected: bool = False,
                              command: Sequence[str] | None = None, environment_digest: str | None = None) -> dict[str, Any]:
    if type(os_name) is not str or os_name not in OS_NAMES or type(adapter_id) is not str or not adapter_id or len(adapter_id) > 128 or any(ord(ch) < 32 for ch in adapter_id):
        _err("E_PLATFORM", "known OS and adapter id required")
    if type(connected) is not bool:
        _err("E_PLATFORM", "connected must be boolean")
    if command is not None and (not isinstance(command, list) or not command or any(type(x) is not str or not x for x in command)):
        _err("E_PLATFORM", "command must be a non-empty string list")
    if environment_digest is not None and (type(environment_digest) is not str or not _HEX64.fullmatch(environment_digest)):
        _err("E_PLATFORM", "environment digest must be lowercase SHA-256")
    return {"os": os_name, "adapter_id": adapter_id, "connected": connected,
            "execution_mode": "dispatcher" if connected else "REFERENCE_ONLY",
            "command": list(command or []), "environment_digest": environment_digest}

def classify_failure(*, kind: str, detail: str | None = None, expected_generation: int | None = None,
                     observed_generation: int | None = None) -> dict[str, Any]:
    if type(kind) is not str or kind not in FAILURE_KINDS:
        _err("E_FAILURE", "unknown failure kind")
    if detail is not None and (type(detail) is not str or not detail or len(detail) > 4096 or any(ord(ch) < 32 for ch in detail)):
        _err("E_FAILURE", "detail must be bounded text")
    if any(value is not None and (type(value) is not int or value < 0) for value in (expected_generation, observed_generation)):
        _err("E_FAILURE", "generation must be a non-negative integer")
    if kind == "drift" and expected_generation == observed_generation:
        _err("E_FAILURE", "drift requires generation mismatch")
    return {"kind": kind, "detail": detail or kind,
            "recoverable": kind in {"timeout", "cancelled", "log_missing", "response_missing", "start_unknown"},
            "expected_generation": expected_generation, "observed_generation": observed_generation}

def reconcile_failure(observation: Mapping[str, Any], failure: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(observation, Mapping) or not isinstance(failure, Mapping) or set(failure) != {"kind", "detail", "recoverable", "expected_generation", "observed_generation"}:
        _err("E_RECONCILE", "observation and failure required")
    classify_failure(kind=failure["kind"], detail=failure["detail"], expected_generation=failure["expected_generation"], observed_generation=failure["observed_generation"])
    if type(failure["recoverable"]) is not bool:
        _err("E_RECONCILE", "failure recoverable flag must be boolean")
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
