"""Versioned capability and profile binding records for heterogeneous CLIs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .. import protocols
from ..builtin_artifacts import resource_ref


class CapabilityError(ValueError):
    def __init__(self, code: str, message: str = "adapter capability rejected") -> None:
        self.code = code
        super().__init__(message)


CAPABILITY_NAMES = ("streaming_events", "terminal_event", "model_identity", "tool_events",
                    "usage", "read_only_mode")
ROLE_NAMES = ("planner", "executor", "observer")
PLATFORMS = ("linux", "macos", "windows")
ENVIRONMENT_KINDS = ("native", "wsl")
EVIDENCE_LEVELS = ("observed", "sample", "declared", "synthetic", "unknown")


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value or any(ord(ch) < 0x20 or 0x7f <= ord(ch) <= 0x9f or 0xd800 <= ord(ch) <= 0xdfff for ch in value):
        raise CapabilityError("E_CAPABILITY_SCHEMA", field + " must be safe non-empty text")
    return value


def _unique(values: Any, allowed: Sequence[str], field: str, *, required: bool = False) -> tuple[str, ...]:
    if type(values) is not tuple or (required and not values):
        raise CapabilityError("E_CAPABILITY_SCHEMA", field + " must be a tuple")
    result = []
    for value in values:
        _text(value, field)
        if value not in allowed or value in result:
            raise CapabilityError("E_CAPABILITY_SCHEMA", field + " contains unsupported/duplicate value")
        result.append(value)
    return tuple(result)


@dataclass(frozen=True)
class CapabilityEvidence:
    capability: str
    level: str
    source_ref: Mapping[str, Any] | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        _unique((self.capability,), CAPABILITY_NAMES, "/capability")
        if self.level not in EVIDENCE_LEVELS:
            raise CapabilityError("E_CAPABILITY_SCHEMA", "unsupported evidence level")
        if self.source_ref is not None:
            if type(self.source_ref) is not dict:
                raise CapabilityError("E_CAPABILITY_SCHEMA", "source_ref must be object")
            try:
                normalized = resource_ref(self.source_ref, "/source_ref")
            except Exception as exc:
                raise CapabilityError("E_CAPABILITY_EVIDENCE", "source_ref must be a closed ResourceRef") from exc
            object.__setattr__(self, "source_ref", normalized)
        if self.level == "observed" and self.source_ref is None:
            raise CapabilityError("E_CAPABILITY_EVIDENCE", "observed evidence requires a ResourceRef")
        if self.note is not None:
            _text(self.note, "/note")

    def to_mapping(self) -> dict[str, Any]:
        return {"capability": self.capability, "level": self.level,
                "source_ref": None if self.source_ref is None else dict(self.source_ref), "note": self.note}


@dataclass(frozen=True)
class AdapterCapability:
    adapter_id: str
    protocol_version: str
    version: str
    platforms: tuple[str, ...]
    roles: tuple[str, ...]
    capabilities: tuple[str, ...]
    model_selection: str
    shell: str
    evidence: tuple[CapabilityEvidence, ...]
    offline: bool = False
    environment_kinds: tuple[str, ...] = ("native",)

    def __post_init__(self) -> None:
        _text(self.adapter_id, "/adapter_id"); _text(self.protocol_version, "/protocol_version"); _text(self.version, "/version")
        _unique(self.platforms, PLATFORMS, "/platforms", required=True)
        _unique(self.roles, ROLE_NAMES, "/roles", required=True)
        _unique(self.capabilities, CAPABILITY_NAMES, "/capabilities", required=True)
        if self.model_selection not in {"required", "optional", "unknown"}:
            raise CapabilityError("E_CAPABILITY_SCHEMA", "model_selection must be explicit")
        _text(self.shell, "/shell")
        if type(self.evidence) is not tuple or any(type(item) is not CapabilityEvidence for item in self.evidence):
            raise CapabilityError("E_CAPABILITY_SCHEMA", "evidence tuple required")
        if len({item.capability for item in self.evidence}) != len(self.evidence):
            raise CapabilityError("E_CAPABILITY_EVIDENCE", "evidence must contain one entry per capability")
        if any(item.capability not in self.capabilities for item in self.evidence):
            raise CapabilityError("E_CAPABILITY_EVIDENCE", "evidence cannot describe an undeclared capability")
        if {item.capability for item in self.evidence} != set(self.capabilities):
            raise CapabilityError("E_CAPABILITY_EVIDENCE", "every declared capability needs an evidence state")
        _unique(self.environment_kinds, ENVIRONMENT_KINDS, "/environment_kinds", required=True)
        if type(self.offline) is not bool:
            raise CapabilityError("E_CAPABILITY_SCHEMA", "offline must be boolean")

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "adapter-capability", "schema_version": 1,
                "adapter_id": self.adapter_id, "protocol_version": self.protocol_version,
                "version": self.version, "platforms": list(self.platforms), "roles": list(self.roles),
                "capabilities": list(self.capabilities), "model_selection": self.model_selection,
                "shell": self.shell, "evidence": [item.to_mapping() for item in self.evidence],
                "offline": self.offline, "environment_kinds": list(self.environment_kinds)}


@dataclass(frozen=True)
class ProfileBinding:
    adapter_id: str
    role: str
    platform: str
    model_id: str | None
    capability_digest: str
    supported: bool
    reasons: tuple[str, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {"adapter_id": self.adapter_id, "role": self.role, "platform": self.platform,
                "model_id": self.model_id, "capability_digest": self.capability_digest,
                "supported": self.supported, "reasons": list(self.reasons)}


def bind_profile(capability: AdapterCapability, *, role: str, platform: str,
                 required_capabilities: Sequence[str], model_id: str | None = None,
                 require_observed: bool = False, environment_kind: str = "native") -> ProfileBinding:
    if role not in ROLE_NAMES or platform not in PLATFORMS:
        raise CapabilityError("E_PROFILE_SCHEMA", "unsupported role/platform")
    if environment_kind not in ENVIRONMENT_KINDS:
        raise CapabilityError("E_PROFILE_SCHEMA", "unsupported environment kind")
    required = set(_unique(tuple(required_capabilities), CAPABILITY_NAMES, "/required_capabilities"))
    reasons: list[str] = []
    if role not in capability.roles:
        reasons.append("ROLE_UNSUPPORTED")
    if platform not in capability.platforms:
        reasons.append("PLATFORM_UNSUPPORTED")
    if environment_kind not in capability.environment_kinds:
        reasons.append("ENVIRONMENT_UNSUPPORTED")
    missing = sorted(required - set(capability.capabilities))
    reasons.extend("CAPABILITY_MISSING:" + item for item in missing)
    if capability.model_selection == "required" and not model_id:
        reasons.append("MODEL_REQUIRED")
    if require_observed:
        if capability.offline:
            reasons.append("REAL_CAPABILITY_REQUIRED")
        observed = {item.capability for item in capability.evidence if item.level == "observed"}
        reasons.extend("EVIDENCE_NOT_OBSERVED:" + item for item in sorted(required - observed))
    import hashlib
    digest = hashlib.sha256(protocols.stable_snapshot_bytes(capability.to_mapping())).hexdigest()
    return ProfileBinding(capability.adapter_id, role, platform, model_id, digest, not reasons, tuple(reasons))


__all__ = ["AdapterCapability", "CapabilityEvidence", "CapabilityError", "EVIDENCE_LEVELS", "ProfileBinding", "bind_profile"]
