"""Cross-platform runtime command and lifecycle contracts.

The module is intentionally observation-driven: platform runners provide real
PID/boot/executable facts, while these pure functions classify them.  No
process is created, killed, or inspected here.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from typing import Any, Mapping, Optional, Tuple


class RuntimeErrorCode(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def validate_argv(command: Any, *, shell: bool = False) -> Tuple[str, ...]:
    if shell:
        raise RuntimeErrorCode("E_RUNTIME_SHELL_ARGV", "shell execution must use a registered shell command contract")
    if not isinstance(command, (list, tuple)) or not command:
        raise RuntimeErrorCode("E_RUNTIME_ARGV", "argv must be a non-empty array")
    result = []
    for index, item in enumerate(command):
        if not isinstance(item, str) or not item:
            raise RuntimeErrorCode("E_RUNTIME_ARGV", f"argv[{index}] must be non-empty text")
        if "\x00" in item:
            raise RuntimeErrorCode("E_RUNTIME_ARGV", f"argv[{index}] contains NUL")
        result.append(item)
    return tuple(result)


@dataclass(frozen=True)
class InvocationSpec:
    request_id: str
    run_id: str
    command: Tuple[str, ...]
    cwd: str
    environment_sha256: str
    timeout_seconds: int
    shell: bool = False

    def __post_init__(self) -> None:
        if not self.request_id or not self.run_id or not self.cwd:
            raise RuntimeErrorCode("E_RUNTIME_INVOCATION", "request, run and cwd are required")
        validate_argv(self.command, shell=self.shell)
        if len(self.environment_sha256) != 64 or any(x not in "0123456789abcdef" for x in self.environment_sha256):
            raise RuntimeErrorCode("E_RUNTIME_INVOCATION", "environment SHA-256 must be lowercase")
        if type(self.timeout_seconds) is not int or self.timeout_seconds <= 0:
            raise RuntimeErrorCode("E_RUNTIME_TIMEOUT", "timeout must be a positive integer")

    def digest(self) -> str:
        payload = "\0".join((self.request_id, self.run_id, *self.command, self.cwd, self.environment_sha256, str(self.timeout_seconds)))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    boot_id: str
    executable_sha256: str
    worktree_id: str

    def __post_init__(self) -> None:
        if type(self.pid) is not int or self.pid <= 0:
            raise RuntimeErrorCode("E_RUNTIME_PID", "pid must be positive")
        if not self.boot_id or not self.worktree_id or not re.fullmatch(r"[0-9a-f]{64}", self.executable_sha256):
            raise RuntimeErrorCode("E_RUNTIME_IDENTITY", "complete process identity is required")


LIFECYCLE = ("NEW", "STARTING", "STARTED", "STOPPING", "STOPPED", "FAILED", "START_UNKNOWN")
ALLOWED_TRANSITIONS = {
    "NEW": {"STARTING", "FAILED"}, "STARTING": {"STARTED", "START_UNKNOWN", "FAILED"},
    "STARTED": {"STOPPING", "FAILED"}, "STOPPING": {"STOPPED", "FAILED", "START_UNKNOWN"},
    "STOPPED": set(), "FAILED": set(), "START_UNKNOWN": {"STARTED", "STOPPING", "FAILED"},
}


@dataclass(frozen=True)
class Lifecycle:
    state: str = "NEW"
    generation: int = 0
    identity: Optional[ProcessIdentity] = None

    def transition(self, state: str, *, identity: Optional[ProcessIdentity] = None, expected_generation: Optional[int] = None) -> "Lifecycle":
        if expected_generation is not None and expected_generation != self.generation:
            raise RuntimeErrorCode("E_RUNTIME_FENCE", "lifecycle generation changed")
        if self.state == "START_UNKNOWN" and expected_generation is None:
            raise RuntimeErrorCode("E_RUNTIME_FENCE", "START_UNKNOWN requires a generation fence")
        if state not in LIFECYCLE or state not in ALLOWED_TRANSITIONS[self.state]:
            raise RuntimeErrorCode("E_RUNTIME_TRANSITION", f"invalid transition {self.state}->{state}")
        if state == "STARTED" and identity is None:
            raise RuntimeErrorCode("E_RUNTIME_IDENTITY", "STARTED requires process identity")
        return replace(self, state=state, generation=self.generation + 1, identity=identity or self.identity)


def classify_start(*, handoff_accepted: bool, started_observation: Optional[Mapping[str, Any]], expected: InvocationSpec) -> str:
    """Classify an uncertain handoff without guessing that a process started."""

    if started_observation is None:
        return "START_UNKNOWN" if handoff_accepted else "NOT_STARTED"
    if started_observation.get("run_id") != expected.run_id or started_observation.get("environment_sha256") != expected.environment_sha256:
        return "IDENTITY_MISMATCH"
    if started_observation.get("state") == "STARTED":
        return "STARTED"
    if started_observation.get("state") in {"FAILED", "STOPPED"}:
        return str(started_observation["state"])
    return "START_UNKNOWN"


def reconcile(expected: InvocationSpec, observed: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return a conservative reconciliation result for an observation."""

    status = classify_start(handoff_accepted=True, started_observation=observed, expected=expected)
    return {"status": status, "run_id": expected.run_id, "expected_environment_sha256": expected.environment_sha256,
            "observed_environment_sha256": observed.get("environment_sha256"), "replay_allowed": status == "NOT_STARTED" or (status in {"FAILED", "STOPPED"} and observed.get("cleanup_confirmed") is True)}


__all__ = ["ALLOWED_TRANSITIONS", "InvocationSpec", "Lifecycle", "ProcessIdentity", "RuntimeErrorCode", "classify_start", "reconcile", "validate_argv"]
