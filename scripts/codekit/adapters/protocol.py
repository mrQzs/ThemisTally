"""Versioned adapter boundary shared by runtime adapters and the dispatcher."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple


EVENT_TYPES = {"run_started", "assistant", "tool_started", "tool_finished", "usage", "run_finished", "error"}


class AdapterError(ValueError):
    def __init__(self, code: str, message: str, *, seq: Optional[int] = None):
        self.code, self.seq = code, seq
        super().__init__(f"{code}: {message}")


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AdapterError("E_ADAPTER_SCHEMA", f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_id: str
    protocol_version: str
    capabilities: Tuple[str, ...]
    roles: Tuple[str, ...]
    offline: bool = False


@dataclass(frozen=True)
class Invocation:
    request_id: str
    run_id: str
    role: str
    profile_id: str
    command: Tuple[str, ...]
    capabilities: Tuple[str, ...]
    environment_sha256: str
    adapter_id: Optional[str] = None

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id"); _text(self.run_id, "run_id"); _text(self.role, "role"); _text(self.profile_id, "profile_id")
        if self.adapter_id is not None:
            _text(self.adapter_id, "adapter_id")
        if not self.command or any(not isinstance(x, str) or not x for x in self.command):
            raise AdapterError("E_ADAPTER_INVOCATION", "command must be a non-empty argv tuple")
        if len(self.environment_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.environment_sha256):
            raise AdapterError("E_ADAPTER_INVOCATION", "environment_sha256 must be lowercase SHA-256")

    def digest(self) -> str:
        payload = {"request_id": self.request_id, "run_id": self.run_id, "role": self.role,
                   "profile_id": self.profile_id, "command": list(self.command),
                   "capabilities": list(self.capabilities), "environment_sha256": self.environment_sha256}
        if self.adapter_id is not None:
            payload["adapter_id"] = self.adapter_id
        return hashlib.sha256((json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()


@dataclass(frozen=True)
class NormalizedEvent:
    seq: int
    event_id: str
    event_type: str
    source: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class AdapterResult:
    invocation_sha256: str
    events: Tuple[NormalizedEvent, ...]
    settled: bool
    status: str
    usage: Mapping[str, Any]
    raw_complete: bool


def normalize_events(events: Iterable[Mapping[str, Any]], *, expected_source: str) -> Tuple[NormalizedEvent, ...]:
    result = []
    seen_ids = set()
    expected_seq = 0
    for raw in events:
        if not isinstance(raw, Mapping):
            raise AdapterError("E_ADAPTER_EVENT", "event must be an object", seq=expected_seq)
        if set(raw) - {"seq", "event_id", "type", "source", "payload"}:
            raise AdapterError("E_ADAPTER_EVENT", "unknown event field", seq=expected_seq)
        seq = raw.get("seq")
        if type(seq) is not int or seq < 0:
            raise AdapterError("E_ADAPTER_EVENT_SEQ", "seq must be a non-negative integer", seq=expected_seq)
        if seq != expected_seq:
            raise AdapterError("E_ADAPTER_EVENT_GAP", f"expected seq {expected_seq}, got {seq}", seq=seq)
        event_id = _text(raw.get("event_id"), "event_id")
        if event_id in seen_ids:
            raise AdapterError("E_ADAPTER_EVENT_DUPLICATE", "event_id repeated", seq=seq)
        seen_ids.add(event_id)
        event_type = _text(raw.get("type"), "type")
        if event_type not in EVENT_TYPES:
            raise AdapterError("E_ADAPTER_EVENT_TYPE", "unknown event type", seq=seq)
        source = _text(raw.get("source"), "source")
        if source != expected_source:
            raise AdapterError("E_ADAPTER_SOURCE", "event source does not match adapter", seq=seq)
        payload = raw.get("payload", {})
        if not isinstance(payload, Mapping):
            raise AdapterError("E_ADAPTER_EVENT", "payload must be an object", seq=seq)
        result.append(NormalizedEvent(seq, event_id, event_type, source, copy.deepcopy(dict(payload))))
        expected_seq += 1
    return tuple(result)


class AdapterRegistry:
    def __init__(self, descriptors: Iterable[AdapterDescriptor] = ()) -> None:
        self._items: Dict[str, AdapterDescriptor] = {}
        for descriptor in descriptors:
            self.register(descriptor)

    def register(self, descriptor: AdapterDescriptor) -> None:
        if descriptor.adapter_id in self._items:
            raise AdapterError("E_ADAPTER_DUPLICATE", "adapter id already registered")
        self._items[descriptor.adapter_id] = descriptor

    def resolve(self, adapter_id: str, *, role: Optional[str] = None) -> AdapterDescriptor:
        descriptor = self._items.get(adapter_id)
        if descriptor is None:
            raise AdapterError("E_ADAPTER_UNKNOWN", "adapter is not registered")
        if role is not None and role not in descriptor.roles:
            raise AdapterError("E_ADAPTER_CAPABILITY", "adapter does not support role")
        return descriptor

    def validate_invocation(self, invocation: Invocation) -> AdapterDescriptor:
        if invocation.adapter_id is None:
            raise AdapterError("E_ADAPTER_IDENTITY", "invocation must bind an adapter descriptor")
        descriptor = self.resolve(invocation.adapter_id, role=invocation.role)
        missing = set(descriptor.capabilities) - set(invocation.capabilities)
        if missing:
            raise AdapterError("E_ADAPTER_CAPABILITY", "invocation is missing descriptor capabilities")
        return descriptor


__all__ = ["AdapterDescriptor", "AdapterError", "AdapterRegistry", "AdapterResult", "Invocation", "NormalizedEvent", "normalize_events"]
