"""Read-only adapters for authority-owned records used by project views."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .project_events import canonical_bytes, validate_resource_ref


class AuthorityObservationError(ValueError):
    def __init__(self, code: str, message: str = "authority observation rejected") -> None:
        self.code = code
        super().__init__(message)


AUTHORITY_NAMES = ("approval", "readiness", "planning", "runtime")
STATUSES = ("observed", "missing", "unknown", "blocked")


@dataclass(frozen=True)
class AuthorityObservation:
    authority: str
    status: str
    source_ref: dict[str, Any] | None
    snapshot: dict[str, Any] | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.authority not in AUTHORITY_NAMES or self.status not in STATUSES:
            raise AuthorityObservationError("E_AUTHORITY", "unsupported authority/status")
        if self.source_ref is not None:
            validate_resource_ref(self.source_ref, field="/source_ref")
        if self.snapshot is not None:
            if type(self.snapshot) is not dict:
                raise AuthorityObservationError("E_SNAPSHOT", "snapshot object required")
            try:
                canonical_bytes(self.snapshot)
            except ValueError as exc:
                raise AuthorityObservationError("E_SNAPSHOT", "snapshot must be strict JSON") from exc

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "authority-observation", "schema_version": 1,
                "authority": self.authority, "status": self.status,
                "source_ref": None if self.source_ref is None else dict(self.source_ref),
                "snapshot": None if self.snapshot is None else dict(self.snapshot),
                "reason": self.reason}


def observe_authority(authority: str, *, status: str = "unknown",
                      source_ref: Mapping[str, Any] | None = None,
                      snapshot: Mapping[str, Any] | None = None,
                      reason: str | None = None) -> AuthorityObservation:
    return AuthorityObservation(authority, status, None if source_ref is None else dict(source_ref),
                                None if snapshot is None else dict(snapshot), reason)


__all__ = ["AUTHORITY_NAMES", "AuthorityObservation", "AuthorityObservationError", "STATUSES", "observe_authority"]
