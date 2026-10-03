"""Read-only project status/checkpoint commands for 10 consumers."""
from __future__ import annotations

from typing import Any, Sequence

from .project_authority import AuthorityObservation
from .project_events import canonical_bytes
from .project_views import ViewPackageStore


class ProjectCommandError(ValueError):
    def __init__(self, code: str, message: str = "project command rejected") -> None:
        self.code = code
        super().__init__(message)


def project_status(store: ViewPackageStore, authorities: Sequence[AuthorityObservation] = ()) -> dict[str, Any]:
    manifest, state, brief = store.read_current()
    if isinstance(authorities, (str, bytes)):
        raise ProjectCommandError("E_AUTHORITY", "authority observations sequence required")
    observations = [item.to_mapping() for item in authorities]
    observations.sort(key=lambda item: item["authority"])
    return {"record_type": "project-status", "schema_version": 1,
            "view": manifest.to_mapping(), "state": state,
            "brief_sha256": manifest.brief_sha256, "authority_observations": observations,
            "actions": [], "dispatch_eligibility": "not_evaluated"}


def project_checkpoint(store: ViewPackageStore, authorities: Sequence[AuthorityObservation] = ()) -> dict[str, Any]:
    status = project_status(store, authorities)
    body = {"view_id": status["view"]["view_id"], "manifest_sha256": status["view"]["manifest_sha256"],
            "authority_observations": status["authority_observations"]}
    return {"record_type": "project-checkpoint", "schema_version": 1,
            "checkpoint_id": __import__("hashlib").sha256(canonical_bytes(body)).hexdigest(),
            "status": status, "read_only": True}


__all__ = ["ProjectCommandError", "project_checkpoint", "project_status"]
