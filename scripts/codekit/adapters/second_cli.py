"""Heterogeneous second-CLI adapter boundary.

This module contains the provider-neutral five-interface facade required by
11.  The Claude Code implementation only probes the installed executable in
this revision; it never starts a model request implicitly.  A caller must
provide an exact model and an already-authorized runtime before it can build
an invocation.  Stream normalization keeps the original UTF-8 record bytes
and collection refuses to settle on incomplete, ambiguous, or unverified
evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform as _platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .. import protocols
from ..builtin_artifacts import resource_ref
from ..planner_runtime import PlannerRuntimeError, extract_unique_result
from ..runtime import InvocationSpec
from .capability import AdapterCapability, CapabilityError, CapabilityEvidence, bind_profile
from .protocol import Invocation


class SecondCliError(ValueError):
    def __init__(self, code: str, message: str = "second CLI adapter input rejected") -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_KNOWN_TYPES = {"system", "assistant", "user", "result", "tool_use", "tool_result"}


def _text(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and not value):
        raise SecondCliError("E_CLI_SCHEMA", f"{field} must be text")
    if any(ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F or 0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise SecondCliError("E_CLI_SCHEMA", f"{field} contains unsafe text")
    return value


def _strict_json(value: Any, field: str = "/") -> None:
    try:
        protocols.check_json_value(value, max_bytes=protocols.DEFAULT_MAX_BYTES)
    except protocols.ProtocolError as exc:
        raise SecondCliError("E_CLI_JSON", f"{field} is not strict JSON") from exc


def _raw(value: bytes | str) -> bytes:
    if isinstance(value, str):
        try:
            value = value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise SecondCliError("E_CLI_ENCODING", "record is not UTF-8") from exc
    if type(value) is not bytes:
        raise SecondCliError("E_CLI_ENCODING", "raw record must be UTF-8 bytes")
    if len(value) == 0 or len(value) > protocols.DEFAULT_MAX_BYTES:
        raise SecondCliError("E_CLI_LIMIT", "raw record has invalid size")
    try:
        value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SecondCliError("E_CLI_ENCODING", "raw record is not UTF-8") from exc
    return value


def _env_digest(environment: Mapping[str, str]) -> str:
    if type(environment) is not dict:
        raise SecondCliError("E_CLI_ENV", "environment must be a closed mapping")
    clean: dict[str, str] = {}
    for key, value in environment.items():
        _text(key, "/environment/key")
        _text(value, "/environment/value", allow_empty=True)
        if "=" in key:
            raise SecondCliError("E_CLI_ENV", "environment names cannot contain '='")
        clean[key] = value
    encoded = (json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ProbeResult:
    capability: AdapterCapability
    executable: str
    version_output: bytes
    help_output: bytes
    version_exit_code: int
    help_exit_code: int
    status: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "record_type": "second-cli-probe",
            "schema_version": 1,
            "adapter_id": self.capability.adapter_id,
            "executable": self.executable,
            "version_exit_code": self.version_exit_code,
            "help_exit_code": self.help_exit_code,
            "status": self.status,
            "capability": self.capability.to_mapping(),
            "version_sha256": hashlib.sha256(self.version_output).hexdigest(),
            "help_sha256": hashlib.sha256(self.help_output).hexdigest(),
        }


@dataclass(frozen=True)
class SecondCliProfile:
    adapter_id: str
    executable: str
    role: str
    platform: str
    environment_kind: str
    model_id: str
    profile_id: str
    read_only: bool = True
    capabilities: tuple[str, ...] = ("streaming_events", "terminal_event", "model_identity")

    def __post_init__(self) -> None:
        for field in ("adapter_id", "executable", "role", "platform", "environment_kind", "model_id", "profile_id"):
            _text(getattr(self, field), field)
        if any(token in self.model_id.upper() for token in ("EXACT_MODEL", "REPLACE_ME", "<MODEL>", "YOUR_")):
            raise SecondCliError("E_CLI_MODEL", "an exact model identifier is required")
        if type(self.read_only) is not bool or type(self.capabilities) is not tuple or not self.capabilities:
            raise SecondCliError("E_CLI_PROFILE", "invalid read-only or capability declaration")


@dataclass(frozen=True)
class SecondCliInvocation:
    runtime: InvocationSpec
    adapter: Invocation
    stdin: bytes
    resource_allowlist: tuple[str, ...]
    read_only: bool

    def __post_init__(self) -> None:
        if type(self.stdin) is not bytes:
            raise SecondCliError("E_CLI_INVOCATION", "stdin must be bytes")
        if type(self.resource_allowlist) is not tuple or len(set(self.resource_allowlist)) != len(self.resource_allowlist):
            raise SecondCliError("E_CLI_INVOCATION", "resource allowlist must be unique")
        if type(self.read_only) is not bool:
            raise SecondCliError("E_CLI_INVOCATION", "read_only must be boolean")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "request_id": self.adapter.request_id,
            "run_id": self.adapter.run_id,
            "role": self.adapter.role,
            "profile_id": self.adapter.profile_id,
            "argv": list(self.runtime.command),
            "cwd": self.runtime.cwd,
            "environment_sha256": self.runtime.environment_sha256,
            "stdin_sha256": hashlib.sha256(self.stdin).hexdigest(),
            "resource_allowlist": list(self.resource_allowlist),
            "read_only": self.read_only,
            "invocation_sha256": self.runtime.digest(),
        }


@dataclass(frozen=True)
class CliEvent:
    request_id: str
    run_id: str
    seq: int
    role: str
    event_id: str
    event_type: str
    payload: Mapping[str, Any]
    raw_record_ref: Mapping[str, str]
    raw_start: int
    raw_end: int
    adapter_revision: str
    actual_model: str | None = None
    terminal: bool = False
    complete: bool = True
    tool_id: str | None = None

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id"); _text(self.run_id, "run_id"); _text(self.role, "role")
        _text(self.event_id, "event_id"); _text(self.event_type, "event_type"); _text(self.adapter_revision, "adapter_revision")
        if type(self.seq) is not int or self.seq < 1:
            raise SecondCliError("E_CLI_EVENT_SEQ", "seq must be one-based")
        if type(self.payload) is not dict:
            raise SecondCliError("E_CLI_EVENT", "payload must be an object")
        _strict_json(dict(self.payload), "/payload")
        if set(self.raw_record_ref) != {"kind", "id", "path", "sha256"}:
            raise SecondCliError("E_CLI_RAW_REF", "raw_record_ref must be closed")
        try:
            normalized = resource_ref(dict(self.raw_record_ref), "/raw_record_ref")
        except Exception as exc:
            raise SecondCliError("E_CLI_RAW_REF", "raw_record_ref must be a ResourceRef") from exc
        object.__setattr__(self, "raw_record_ref", normalized)
        if type(self.raw_start) is not int or type(self.raw_end) is not int or not 0 <= self.raw_start < self.raw_end:
            raise SecondCliError("E_CLI_RAW_RANGE", "raw range must be half-open")
        if type(self.terminal) is not bool or type(self.complete) is not bool:
            raise SecondCliError("E_CLI_EVENT", "terminal and complete must be boolean")
        if self.actual_model is not None:
            _text(self.actual_model, "actual_model")

    def to_result_event(self) -> dict[str, Any]:
        return {"event_id": self.event_id, "event_type": "result" if self.terminal else self.event_type,
                "payload": dict(self.payload), "complete": self.complete,
                "terminated": self.terminal, "execution_mode": "deterministic_check"}


@dataclass(frozen=True)
class CollectionResult:
    settled: bool
    status: str
    reasons: tuple[str, ...]
    result: Mapping[str, Any] | None
    actual_model: str | None
    usage: Mapping[str, Any]
    invocation_sha256: str

    def to_mapping(self) -> dict[str, Any]:
        return {"settled": self.settled, "status": self.status, "reasons": list(self.reasons),
                "result": None if self.result is None else dict(self.result),
                "actual_model": self.actual_model, "usage": dict(self.usage),
                "invocation_sha256": self.invocation_sha256}


def _probe_command(executable: str, args: Sequence[str], timeout: float) -> tuple[int, bytes, bool]:
    try:
        completed = subprocess.run((executable, *args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, shell=False, timeout=timeout, check=False)
        raw = bytes(completed.stdout or b"")
        return int(completed.returncode), raw, False
    except (OSError, subprocess.TimeoutExpired):
        return 127, b"", True


class ClaudeCodeAdapter:
    """A real executable probe plus deterministic stream adapter for Claude Code."""

    adapter_id = "claude-code"
    protocol_version = "claude-stream-json-v1"

    def probe(self, executable: str = "claude", *, timeout: float = 5.0,
              platform: str | None = None, environment_kind: str = "native") -> ProbeResult:
        executable_path = shutil.which(executable) or executable
        version_exit, version_raw, version_timeout = _probe_command(executable_path, ("--version",), timeout)
        help_exit, help_raw, help_timeout = _probe_command(executable_path, ("--help",), timeout)
        text = (version_raw + b"\n" + help_raw).decode("utf-8", errors="replace")
        version_match = re.search(r"(?:Claude Code|claude)\s+([0-9]+\.[0-9]+\.[0-9]+)", text, re.I)
        version = version_match.group(1) if version_match else "unknown"
        selected_platform = (platform or {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}.get(_platform.system(), "linux"))
        if selected_platform not in ("linux", "macos", "windows"):
            raise SecondCliError("E_CLI_PLATFORM", "platform must be linux, macos, or windows")
        if environment_kind not in ("native", "wsl"):
            raise SecondCliError("E_CLI_PLATFORM", "environment_kind must be native or wsl")
        # These are declared from the help surface, while the command output
        # itself is observed evidence.  A model call is required before a
        # capability can be considered production-verified.
        capabilities = ["terminal_event"]
        if "stream-json" in text:
            capabilities.append("streaming_events")
        if "--model" in text:
            capabilities.append("model_identity")
        if "tool" in text.lower():
            capabilities.append("tool_events")
        ref = {"kind": "cli-probe", "id": self.adapter_id + "-version", "path": "probe/claude-version.txt",
               "sha256": hashlib.sha256(version_raw).hexdigest()}
        evidence = tuple(CapabilityEvidence(name, "observed" if name == "terminal_event" else "declared",
                                             source_ref=ref if name == "terminal_event" else None,
                                             note="version/help probe; model request not run") for name in capabilities)
        capability = AdapterCapability(self.adapter_id, self.protocol_version, version, (selected_platform,),
                                       ("planner", "executor", "observer"), tuple(capabilities), "required", "argv",
                                       evidence, False, (environment_kind,))
        status = "OBSERVED_EXECUTABLE" if version_exit == 0 and help_exit == 0 and not version_timeout and not help_timeout else "BLOCKED"
        return ProbeResult(capability, executable_path, version_raw, help_raw, version_exit, help_exit, status)

    def validate_profile(self, capability: AdapterCapability, *, role: str, platform: str,
                         model_id: str, profile_id: str, executable: str = "claude", environment_kind: str = "native",
                         required_capabilities: Sequence[str] = ("streaming_events", "terminal_event", "model_identity"),
                         require_observed: bool = False) -> SecondCliProfile:
        binding = bind_profile(capability, role=role, platform=platform, environment_kind=environment_kind,
                               required_capabilities=tuple(required_capabilities), model_id=model_id,
                               require_observed=require_observed)
        if not binding.supported:
            raise SecondCliError("E_CLI_PROFILE", ";".join(binding.reasons))
        return SecondCliProfile(capability.adapter_id, executable, role, platform, environment_kind, model_id,
                                profile_id, True, tuple(required_capabilities))

    def build_invocation(self, profile: SecondCliProfile, *, request_id: str, run_id: str,
                         cwd: str, environment: Mapping[str, str], prompt: bytes | str,
                         resource_allowlist: Sequence[str] = ()) -> SecondCliInvocation:
        _text(request_id, "request_id"); _text(run_id, "run_id"); _text(cwd, "cwd")
        prompt_bytes = _raw(prompt)
        command = (profile.executable, "--print", "--output-format", "stream-json", "--verbose",
                   "--no-session-persistence", "--model", profile.model_id)
        if profile.read_only:
            command += ("--tools", "")
        env_digest = _env_digest(dict(environment))
        runtime = InvocationSpec(request_id, run_id, command, cwd, env_digest, 900, False)
        adapter = Invocation(request_id, run_id, profile.role, profile.profile_id, command,
                             profile.capabilities, env_digest, profile.adapter_id)
        return SecondCliInvocation(runtime, adapter, prompt_bytes, tuple(resource_allowlist), profile.read_only)

    def normalize_event(self, raw_record: bytes | str, *, request_id: str, run_id: str, seq: int,
                        role: str, adapter_revision: str = "claude-stream-json-v1",
                        raw_path: str | None = None) -> CliEvent:
        raw = _raw(raw_record)
        if raw.endswith(b"\n"):
            body = raw[:-1]
        else:
            body = raw
        try:
            record = protocols.strict_json_loads(body, max_bytes=protocols.DEFAULT_MAX_BYTES)
        except protocols.ProtocolError:
            record = None
        event_id = hashlib.sha256(raw).hexdigest()[:32]
        ref = {"kind": "raw-segment", "id": event_id, "path": raw_path or ("stdout/" + event_id + ".jsonl"),
               "sha256": hashlib.sha256(raw).hexdigest()}
        if not isinstance(record, dict):
            return CliEvent(request_id, run_id, seq, role, event_id, "protocol_error",
                            {"reason": "MALFORMED_JSON", "raw_sha256": ref["sha256"]}, ref, 0, len(raw),
                            adapter_revision, complete=False)
        kind = record.get("type")
        model = record.get("model")
        if model is None and isinstance(record.get("message"), dict):
            model = record["message"].get("model")
        if kind not in _KNOWN_TYPES:
            return CliEvent(request_id, run_id, seq, role, event_id, "unknown", {"raw": record}, ref, 0, len(raw),
                            adapter_revision, actual_model=model if isinstance(model, str) else None, complete=False)
        event_type = {"system": "run_started", "assistant": "assistant", "user": "tool_finished",
                      "tool_use": "tool_started", "tool_result": "tool_finished", "result": "run_finished"}[kind]
        terminal = kind == "result"
        complete = True
        if terminal:
            complete = record.get("subtype") == "success" and record.get("is_error") is not True
        payload = dict(record)
        tool_id = None
        if kind == "tool_use":
            tool_id = record.get("id") or (record.get("content") or {}).get("id") if isinstance(record.get("content"), dict) else record.get("id")
        elif kind == "tool_result":
            tool_id = record.get("tool_use_id")
        return CliEvent(request_id, run_id, seq, role, event_id, event_type, payload, ref, 0, len(raw), adapter_revision,
                        actual_model=model if isinstance(model, str) else None, terminal=terminal, complete=complete,
                        tool_id=tool_id if isinstance(tool_id, str) else None)

    def normalize_events(self, records: Iterable[bytes | str], *, request_id: str, run_id: str,
                         role: str, adapter_revision: str = "claude-stream-json-v1") -> tuple[CliEvent, ...]:
        result = []
        seen: set[str] = set()
        for seq, record in enumerate(records, 1):
            event = self.normalize_event(record, request_id=request_id, run_id=run_id, seq=seq, role=role,
                                          adapter_revision=adapter_revision)
            if event.event_id in seen:
                raise SecondCliError("E_CLI_EVENT_DUPLICATE", "raw event repeated")
            seen.add(event.event_id)
            result.append(event)
        return tuple(result)

    def collect_result(self, events: Sequence[CliEvent], *, invocation_sha256: str,
                       exit_code: int | None, expected_model: str | None = None,
                       cancelled: bool = False, response_lost: bool = False) -> CollectionResult:
        reasons: list[str] = []
        if not events:
            reasons.append("NO_EVENTS")
        unique_events: list[CliEvent] = []
        by_id: dict[str, CliEvent] = {}
        expected_seq = 1
        if events:
            bound = (events[0].request_id, events[0].run_id, events[0].role)
            for event in events:
                if (event.request_id, event.run_id, event.role) != bound:
                    reasons.append("EVENT_CONTEXT_MISMATCH")
                previous = by_id.get(event.event_id)
                if previous is None:
                    if event.seq != expected_seq:
                        reasons.append("EVENT_SEQUENCE_GAP")
                    expected_seq = max(expected_seq, event.seq + 1)
                    by_id[event.event_id] = event
                    unique_events.append(event)
                elif previous.raw_record_ref != event.raw_record_ref:
                    reasons.append("EVENT_REPLAY_CONFLICT")
        events = tuple(unique_events)
        if exit_code is None:
            reasons.append("EXIT_UNKNOWN")
        elif exit_code != 0:
            reasons.append("NONZERO_EXIT")
        if cancelled:
            reasons.append("CANCELLED")
        if response_lost:
            reasons.append("RESPONSE_LOST")
        models = {event.actual_model for event in events if event.actual_model}
        actual_model = next(iter(models)) if len(models) == 1 else None
        if len(models) > 1:
            reasons.append("MODEL_IDENTITY_CONFLICT")
        if expected_model is not None and actual_model != expected_model:
            reasons.append("MODEL_MISMATCH" if actual_model else "MODEL_UNKNOWN")
        if any(not event.complete or event.event_type in {"unknown", "protocol_error"} for event in events):
            reasons.append("PROTOCOL_INCOMPLETE")
        active_tools: set[str] = set()
        for event in events:
            if event.event_type == "tool_started":
                if not event.tool_id:
                    reasons.append("TOOL_ID_MISSING")
                else:
                    active_tools.add(event.tool_id)
            elif event.event_type == "tool_finished":
                if event.tool_id in active_tools:
                    active_tools.remove(event.tool_id)
        if active_tools:
            reasons.append("TOOL_AUDIT_INCOMPLETE")
        terminals = [event for event in events if event.terminal]
        if len(terminals) != 1:
            reasons.append("TERMINAL_MISSING" if not terminals else "TERMINAL_AMBIGUOUS")
        result: Mapping[str, Any] | None = None
        try:
            if terminals:
                result = extract_unique_result([event.to_result_event() for event in events])
        except PlannerRuntimeError as exc:
            reasons.append(exc.code)
        usage: Mapping[str, Any] = {}
        for event in events:
            if event.event_type == "usage" and isinstance(event.payload.get("usage"), dict):
                usage = dict(event.payload["usage"])
            if event.terminal and isinstance(event.payload.get("usage"), dict):
                usage = dict(event.payload["usage"])
        if not usage:
            reasons.append("USAGE_UNKNOWN")
        status = "SETTLED" if not reasons and result is not None else ("UNKNOWN" if any(code.endswith("UNKNOWN") or code in {"NO_EVENTS", "EXIT_UNKNOWN", "RESPONSE_LOST"} for code in reasons) else "BLOCKED")
        return CollectionResult(status == "SETTLED", status, tuple(dict.fromkeys(reasons)), result, actual_model, usage, invocation_sha256)


__all__ = ["ClaudeCodeAdapter", "CollectionResult", "CliEvent", "ProbeResult", "SecondCliError", "SecondCliInvocation", "SecondCliProfile"]
