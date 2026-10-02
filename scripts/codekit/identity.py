#!/usr/bin/env python3
"""Pure platform, process, and resource identity models for 07-S1.3.

This module deliberately does not inspect the host, resolve paths, query a
PID, open a lock, or start a process.  Platform adapters must provide facts
as already-bound opaque values.  Unknown facts remain unknown; in particular
a PID by itself never proves process ownership.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Optional, Tuple


KNOWN = "KNOWN"
UNKNOWN = "UNKNOWN"
BLOCKED = "BLOCKED"
ACCEPTED = "ACCEPTED"

PLATFORMS = frozenset(("linux", "macos", "windows"))
ENVIRONMENT_KINDS = frozenset(("native", "wsl1", "wsl2", "container", "vm"))
CLAIM_MODES = frozenset(("read", "write", "exclusive", "unknown"))
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_OPAQUE_RE = re.compile(r"opaque:v1:[A-Za-z0-9._:-]{1,64}:[0-9a-f]{64}\Z")


class IdentityModelError(ValueError):
    """Invalid identity declaration; no external state has been changed."""

    def __init__(self, code: str, field: str, reason: str) -> None:
        self.code = code
        self.field = field
        self.reason = reason
        super().__init__(f"{code} {field}: {reason}")


def _text(value: object, field: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and not value) or "\x00" in value:
        raise IdentityModelError("E_IDENTITY_FIELD", field, "text_required")
    if "\r" in value or "\n" in value:
        raise IdentityModelError("E_IDENTITY_FIELD", field, "line_break_forbidden")
    return value


def _optional_text(value: object, field: str) -> Optional[str]:
    if value is None:
        return None
    return _text(value, field)


def _canonical_value(value: Any, field: str = "/value") -> Any:
    """Return a JSON-safe value without normalizing strings or paths."""
    if value is None or type(value) in (str, bool, int):
        if type(value) is str:
            _text(value, field, allow_empty=True)
        if type(value) is int and (value < -(2**53 - 1) or value > 2**53 - 1):
            raise IdentityModelError("E_IDENTITY_FIELD", field, "integer_out_of_range")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise IdentityModelError("E_IDENTITY_FIELD", field, "finite_number_required")
        return value
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise IdentityModelError("E_IDENTITY_FIELD", field, "string_keys_required")
        result = {}
        for key in sorted(value):
            result[key] = _canonical_value(value[key], f"{field}/{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item, f"{field}/{index}") for index, item in enumerate(value)]
    raise IdentityModelError("E_IDENTITY_FIELD", field, "json_value_required")


def canonical_opaque_key(namespace: str, value: Any) -> str:
    """Hash caller-supplied facts into a deterministic opaque identity key.

    Strings are preserved byte-for-byte before hashing.  No path case folding,
    slash replacement, ``normpath``, symlink lookup, or alias resolution is
    performed.  Consequently two spellings are different identities until a
    trusted platform adapter explicitly supplies the same fact/key.
    """
    namespace = _text(namespace, "/namespace")
    if _NAME_RE.fullmatch(namespace) is None:
        raise IdentityModelError("E_IDENTITY_FIELD", "/namespace", "identifier_syntax")
    payload = _canonical_value({"namespace": namespace, "value": value})
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")
    return "opaque:v1:%s:%s" % (namespace, hashlib.sha256(raw).hexdigest())


def is_canonical_opaque_key(value: object) -> bool:
    return type(value) is str and _OPAQUE_RE.fullmatch(value) is not None


def _opaque(value: object, field: str) -> str:
    value = _text(value, field)
    if not is_canonical_opaque_key(value):
        raise IdentityModelError("E_IDENTITY_KEY", field, "canonical_opaque_key_required")
    return value


def _maybe_opaque(value: object, field: str) -> Optional[str]:
    if value is None:
        return None
    return _opaque(value, field)


def _platform(value: object, field: str) -> str:
    value = _text(value, field)
    if value not in PLATFORMS:
        raise IdentityModelError("E_IDENTITY_FIELD", field, "unsupported_platform")
    return value


def _key_for(kind: str, value: Mapping[str, Any]) -> str:
    return canonical_opaque_key(kind, value)


@dataclass(frozen=True)
class HostIdentity:
    """Stable host facts supplied by a trusted adapter."""

    host_id: Optional[str] = None
    platform: Optional[str] = None
    host_os: Optional[str] = None
    host_arch: Optional[str] = None

    @property
    def status(self) -> str:
        return KNOWN if self.canonical_key is not None else UNKNOWN

    @property
    def canonical_key(self) -> Optional[str]:
        if any(type(item) is not str or not item for item in (self.host_id, self.platform, self.host_os, self.host_arch)):
            return None
        if self.platform not in PLATFORMS:
            return None
        return _key_for("host", {"host_id": self.host_id, "platform": self.platform,
                                  "host_os": self.host_os, "host_arch": self.host_arch})

    @classmethod
    def from_facts(cls, host_id: str, platform: str, host_os: str, host_arch: str) -> "HostIdentity":
        return cls(_text(host_id, "/host_id"), _platform(platform, "/platform"),
                   _text(host_os, "/host_os"), _text(host_arch, "/host_arch"))


@dataclass(frozen=True)
class BootIdentity:
    """A boot epoch bound to a host; boot IDs are never inferred from PID."""

    host_key: Optional[str] = None
    boot_id: Optional[str] = None

    @property
    def status(self) -> str:
        return KNOWN if self.canonical_key is not None else UNKNOWN

    @property
    def canonical_key(self) -> Optional[str]:
        if (self.host_key is None or type(self.boot_id) is not str or not self.boot_id
                or not is_canonical_opaque_key(self.host_key)):
            return None
        return _key_for("boot", {"host_key": self.host_key, "boot_id": self.boot_id})

    @classmethod
    def from_facts(cls, host: HostIdentity, boot_id: str) -> "BootIdentity":
        if not isinstance(host, HostIdentity) or host.canonical_key is None:
            raise IdentityModelError("E_IDENTITY_UNKNOWN", "/host", "known_host_required")
        return cls(host.canonical_key, _text(boot_id, "/boot_id"))


@dataclass(frozen=True)
class EnvironmentIdentity:
    """Execution environment, separate from host and boot identity."""

    environment_id: Optional[str] = None
    environment_kind: Optional[str] = None
    platform: Optional[str] = None
    host_key: Optional[str] = None
    boot_key: Optional[str] = None
    process_arch: Optional[str] = None
    kernel_release: Optional[str] = None
    filesystem_profile: Optional[str] = None

    @property
    def status(self) -> str:
        return KNOWN if self.canonical_key is not None else UNKNOWN

    @property
    def canonical_key(self) -> Optional[str]:
        required = (self.environment_id, self.environment_kind, self.platform, self.host_key,
                    self.boot_key, self.process_arch, self.kernel_release, self.filesystem_profile)
        if any(type(item) is not str or not item for item in required) or self.environment_kind not in ENVIRONMENT_KINDS:
            return None
        if self.platform not in PLATFORMS:
            return None
        if not is_canonical_opaque_key(self.host_key) or not is_canonical_opaque_key(self.boot_key):
            return None
        return _key_for("environment", {
            "environment_id": self.environment_id, "environment_kind": self.environment_kind,
            "platform": self.platform, "host_key": self.host_key, "boot_key": self.boot_key,
            "process_arch": self.process_arch, "kernel_release": self.kernel_release,
            "filesystem_profile": self.filesystem_profile,
        })

    @classmethod
    def from_facts(cls, environment_id: str, environment_kind: str, host: HostIdentity,
                   boot: BootIdentity, process_arch: str, kernel_release: str,
                   filesystem_profile: str) -> "EnvironmentIdentity":
        if environment_kind not in ENVIRONMENT_KINDS:
            raise IdentityModelError("E_IDENTITY_FIELD", "/environment_kind", "unsupported_kind")
        if host.canonical_key is None or boot.canonical_key is None:
            raise IdentityModelError("E_IDENTITY_UNKNOWN", "/host_or_boot", "known_identity_required")
        return cls(_text(environment_id, "/environment_id"), environment_kind,
                   _platform(host.platform, "/platform"), host.canonical_key, boot.canonical_key,
                   _text(process_arch, "/process_arch"), _text(kernel_release, "/kernel_release"),
                   _text(filesystem_profile, "/filesystem_profile"))


# Short name used by the design documents.
Environment = EnvironmentIdentity


@dataclass(frozen=True)
class WorktreeIdentity:
    """Worktree facts; ``worktree_key`` is supplied by Git/platform code."""

    repo_id: Optional[str] = None
    worktree_key: Optional[str] = None
    common_dir_key: Optional[str] = None
    object_format: Optional[str] = None

    @property
    def status(self) -> str:
        return KNOWN if self.canonical_key is not None else UNKNOWN

    @property
    def canonical_key(self) -> Optional[str]:
        if any(type(item) is not str or not item for item in (self.repo_id, self.worktree_key, self.common_dir_key)):
            return None
        if not is_canonical_opaque_key(self.worktree_key) or not is_canonical_opaque_key(self.common_dir_key):
            return None
        if self.object_format is not None and self.object_format not in ("sha1", "sha256"):
            return None
        return _key_for("worktree", {"repo_id": self.repo_id, "worktree_key": self.worktree_key,
                                      "common_dir_key": self.common_dir_key,
                                      "object_format": self.object_format})

    @classmethod
    def from_facts(cls, repo_id: str, worktree_key: str, common_dir_key: str,
                   object_format: Optional[str] = None) -> "WorktreeIdentity":
        if object_format is not None and object_format not in ("sha1", "sha256"):
            raise IdentityModelError("E_IDENTITY_FIELD", "/object_format", "unsupported_object_format")
        return cls(_text(repo_id, "/repo_id"), _opaque(worktree_key, "/worktree_key"),
                   _opaque(common_dir_key, "/common_dir_key"), object_format)


@dataclass(frozen=True)
class ProcessIdentity:
    """A process owner identity bound to host, boot, environment, and run."""

    host_key: Optional[str] = None
    boot_key: Optional[str] = None
    environment_key: Optional[str] = None
    worktree_key: Optional[str] = None
    run_id: Optional[str] = None
    pid: Optional[int] = None
    creation_marker: Optional[str] = None
    entry_key: Optional[str] = None
    process_group_key: Optional[str] = None
    job_key: Optional[str] = None

    @property
    def status(self) -> str:
        return KNOWN if self.is_complete else UNKNOWN

    @property
    def is_pid_only(self) -> bool:
        return self.pid is not None and all(value is None for value in (
            self.host_key, self.boot_key, self.environment_key, self.worktree_key,
            self.run_id, self.creation_marker, self.entry_key, self.process_group_key, self.job_key))

    @property
    def is_complete(self) -> bool:
        required = (self.host_key, self.boot_key, self.environment_key, self.worktree_key,
                    self.run_id, self.pid, self.creation_marker, self.entry_key)
        if not all(value is not None for value in required):
            return False
        if self.pid is None or type(self.pid) is not int or self.pid <= 0:
            return False
        if not all(is_canonical_opaque_key(value) for value in (
                self.host_key, self.boot_key, self.environment_key, self.worktree_key,
                self.run_id, self.creation_marker, self.entry_key)):
            return False
        if self.process_group_key is not None and not is_canonical_opaque_key(self.process_group_key):
            return False
        if self.job_key is not None and not is_canonical_opaque_key(self.job_key):
            return False
        return bool(self.process_group_key or self.job_key)

    @property
    def canonical_key(self) -> Optional[str]:
        if not self.is_complete:
            return None
        return _key_for("process", {
            "host_key": self.host_key, "boot_key": self.boot_key,
            "environment_key": self.environment_key, "worktree_key": self.worktree_key,
            "run_id": self.run_id, "pid": self.pid, "creation_marker": self.creation_marker,
            "entry_key": self.entry_key, "process_group_key": self.process_group_key,
            "job_key": self.job_key,
        })


@dataclass(frozen=True)
class IdentityDecision:
    status: str
    blocked: bool
    reasons: Tuple[str, ...] = ()


def process_identity_decision(identity: ProcessIdentity) -> IdentityDecision:
    if not isinstance(identity, ProcessIdentity):
        raise IdentityModelError("E_IDENTITY_TYPE", "/process", "process_identity_required")
    if identity.is_complete:
        return IdentityDecision(KNOWN, False)
    reasons = []
    if identity.is_pid_only:
        reasons.append("pid_only_identity")
    if identity.host_key is None:
        reasons.append("host_identity_unknown")
    if identity.boot_key is None:
        reasons.append("boot_identity_unknown")
    if identity.environment_key is None:
        reasons.append("environment_identity_unknown")
    if identity.worktree_key is None:
        reasons.append("worktree_identity_unknown")
    if identity.run_id is None:
        reasons.append("run_identity_unknown")
    if identity.pid is None:
        reasons.append("pid_unknown")
    if identity.creation_marker is None:
        reasons.append("creation_marker_unknown")
    if identity.entry_key is None:
        reasons.append("entry_identity_unknown")
    if identity.process_group_key is None and identity.job_key is None:
        reasons.append("process_scope_unknown")
    return IdentityDecision(UNKNOWN, True, tuple(reasons))


@dataclass(frozen=True)
class ResourceIdentity:
    """A resource identity represented only by a canonical opaque key."""

    namespace: str
    kind: str
    opaque_key: Optional[str] = None

    @property
    def status(self) -> str:
        return KNOWN if self.canonical_key is not None else UNKNOWN

    @property
    def canonical_key(self) -> Optional[str]:
        if (type(self.namespace) is not str or _NAME_RE.fullmatch(self.namespace) is None
                or type(self.kind) is not str or _NAME_RE.fullmatch(self.kind) is None):
            return None
        return self.opaque_key if self.opaque_key is not None and is_canonical_opaque_key(self.opaque_key) else None

    @classmethod
    def from_facts(cls, namespace: str, kind: str, facts: Any) -> "ResourceIdentity":
        namespace = _text(namespace, "/namespace")
        kind = _text(kind, "/kind")
        return cls(namespace, kind, canonical_opaque_key(namespace + "." + kind, facts))


@dataclass(frozen=True)
class ResourceClaim:
    resource: ResourceIdentity
    mode: str

    @property
    def status(self) -> str:
        return KNOWN if self.resource.status == KNOWN and self.mode in CLAIM_MODES - {"unknown"} else UNKNOWN


def resource_claim_decision(claim: ResourceClaim) -> IdentityDecision:
    if not isinstance(claim, ResourceClaim):
        raise IdentityModelError("E_IDENTITY_TYPE", "/claim", "resource_claim_required")
    if claim.status == KNOWN:
        return IdentityDecision(KNOWN, False)
    reasons = []
    if claim.resource.status != KNOWN:
        reasons.append("resource_identity_unknown")
    if claim.mode == "unknown":
        reasons.append("claim_mode_unknown")
    elif claim.mode not in CLAIM_MODES:
        reasons.append("claim_mode_invalid")
    return IdentityDecision(UNKNOWN, True, tuple(reasons))


def claims_conflict(left: ResourceClaim, right: ResourceClaim) -> bool:
    """Conservative conflict check; unknown claims block rather than pass."""
    if resource_claim_decision(left).blocked or resource_claim_decision(right).blocked:
        return True
    if left.resource.canonical_key != right.resource.canonical_key:
        return False
    return left.mode != "read" or right.mode != "read"


def validate_identity(value: Any) -> str:
    """Return KNOWN/UNKNOWN for any supported identity or claim value."""
    if isinstance(value, (HostIdentity, BootIdentity, EnvironmentIdentity, WorktreeIdentity,
                          ProcessIdentity, ResourceIdentity)):
        return value.status
    if isinstance(value, ResourceClaim):
        return value.status
    raise IdentityModelError("E_IDENTITY_TYPE", "/identity", "supported_identity_required")


__all__ = [
    "ACCEPTED", "BLOCKED", "BootIdentity", "CLAIM_MODES", "Environment",
    "EnvironmentIdentity", "HostIdentity", "IdentityDecision", "IdentityModelError", "KNOWN",
    "PLATFORMS", "ProcessIdentity", "ResourceClaim", "ResourceIdentity", "UNKNOWN",
    "WorktreeIdentity", "canonical_opaque_key", "claims_conflict", "is_canonical_opaque_key",
    "process_identity_decision", "resource_claim_decision", "validate_identity",
]
