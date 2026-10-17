"""Offline, byte-oriented verification for project ResourceRefs.

The verifier deliberately treats the referenced bytes as the authority.  It
does not use mtimes, Git status, or a path string as a substitute for the
declared digest, and it never follows a symlink while establishing identity.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Mapping

from . import protocols
from .project_events import ProjectEventError, validate_resource_ref


class SourceVerificationError(ValueError):
    def __init__(self, code: str, message: str = "source verification rejected") -> None:
        self.code = code
        super().__init__(message)


STATUSES = ("verified", "missing", "incomplete", "hash_mismatch",
            "access_denied", "schema_unsupported", "conflict")


@dataclass(frozen=True)
class SourceVerification:
    status: str
    ref: dict[str, Any]
    observed_sha256: str | None = None
    byte_length: int | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise SourceVerificationError("E_STATUS", "unsupported verification status")
        validate_resource_ref(self.ref, field="/ref")
        if self.observed_sha256 is not None and (
                type(self.observed_sha256) is not str or len(self.observed_sha256) != 64
                or any(ch not in "0123456789abcdef" for ch in self.observed_sha256)):
            raise SourceVerificationError("E_DIGEST", "observed digest must be lowercase sha256")
        if self.byte_length is not None and (
                type(self.byte_length) is not int or self.byte_length < 0):
            raise SourceVerificationError("E_LENGTH", "byte length must be non-negative integer")

    def to_mapping(self) -> dict[str, Any]:
        return {"status": self.status, "ref": dict(self.ref),
                "observed_sha256": self.observed_sha256,
                "byte_length": self.byte_length, "reason": self.reason}


def _result(status: str, ref: dict[str, Any], *, observed: str | None = None,
            length: int | None = None, reason: str | None = None) -> SourceVerification:
    return SourceVerification(status, dict(ref), observed, length, reason)


def verify_source_ref(root: str | Path, ref: Mapping[str, Any]) -> SourceVerification:
    """Verify a file ResourceRef below *root* and return a classified result.

    This function is intentionally report-oriented: missing or unavailable
    evidence is returned as a status so callers can persist the boundary
    without turning an environment fact into a successful projection.
    """
    try:
        normalized = validate_resource_ref(dict(ref), field="/ref")
    except (ProjectEventError, TypeError, ValueError) as exc:
        raise SourceVerificationError("E_RESOURCE", str(exc)) from exc
    if "path" not in normalized:
        return _result("schema_unsupported", normalized, reason="path_required")
    root_path = Path(root)
    try:
        root_resolved = root_path.resolve(strict=True)
    except (OSError, RuntimeError):
        return _result("access_denied", normalized, reason="root_unavailable")
    if not root_resolved.is_dir():
        return _result("access_denied", normalized, reason="root_not_directory")
    candidate = root_path.joinpath(*normalized["path"].split("/"))
    try:
        # Resolve without opening first so an escaping path is classified as a
        # conflict.  Every existing component is checked for symlinks.
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            return _result("conflict", normalized, reason="path_escapes_root")
        cursor = root_resolved
        for part in candidate.relative_to(root_path).parts:
            cursor = cursor / part
            if cursor.is_symlink():
                return _result("conflict", normalized, reason="symlink_component")
        if not candidate.exists():
            return _result("missing", normalized, reason="path_not_found")
        if not candidate.is_file():
            return _result("conflict", normalized, reason="not_regular_file")
        raw = candidate.read_bytes()
    except PermissionError:
        return _result("access_denied", normalized, reason="read_denied")
    except (OSError, RuntimeError):
        return _result("incomplete", normalized, reason="read_incomplete")
    observed = hashlib.sha256(raw).hexdigest()
    if observed != normalized["sha256"]:
        return _result("hash_mismatch", normalized, observed=observed,
                       length=len(raw), reason="sha256_mismatch")
    return _result("verified", normalized, observed=observed,
                   length=len(raw), reason="exact_bytes")


__all__ = ["STATUSES", "SourceVerification", "SourceVerificationError", "verify_source_ref"]
