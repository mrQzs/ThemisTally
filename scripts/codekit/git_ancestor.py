"""Bounded, read-only Git ancestry probe for fixed full object IDs.

The plan and interpreter are intentionally separate from the repository
adapter.  A return code of one means a valid non-ancestor result; timeout,
truncation, malformed output, or another Git failure remains unknown.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from . import protocols
from .git_probe import RawResult, TrustedRepositoryIdentity, build_git_env, _validate_identity


@dataclass(frozen=True)
class AncestorPlan:
    identity: TrustedRepositoryIdentity
    upstream_sha: str
    candidate_sha: str
    argv: tuple[str, ...]
    environment_remove: tuple[str, ...]
    environment_set: tuple[tuple[str, str], ...]
    timeout_seconds: int = 30
    max_output_bytes: int = 1_048_576


@dataclass(frozen=True)
class AncestorObservation:
    decision: str
    reasons: tuple[str, ...] = ()


def build_ancestor_plan(identity: TrustedRepositoryIdentity, upstream_sha: str, candidate_sha: str) -> AncestorPlan:
    if not isinstance(identity, TrustedRepositoryIdentity):
        _error("E_SCHEMA_TYPE", "/identity", "trusted_identity_required")
    _validate_identity(identity)
    upstream = protocols.validate_git_oid(upstream_sha, identity.object_format, field="/upstream_sha")
    candidate = protocols.validate_git_oid(candidate_sha, identity.object_format, field="/candidate_sha")
    argv = ("git", "-C", identity.worktree_root, "merge-base", "--is-ancestor", upstream, candidate)
    env = build_git_env({})
    return AncestorPlan(identity, upstream, candidate, argv,
                        tuple(name for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                                                "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX")),
                        tuple(env.items()))


def interpret_ancestor(result: RawResult | Mapping[str, Any]) -> AncestorObservation:
    if isinstance(result, Mapping):
        try:
            result = RawResult(**dict(result))
        except (TypeError, ValueError):
            return AncestorObservation("UNKNOWN", ("invalid_result",))
    if not isinstance(result, RawResult):
        return AncestorObservation("UNKNOWN", ("invalid_result",))
    if (result.timed_out or result.truncated or type(result.timed_out) is not bool
            or type(result.truncated) is not bool
            or (result.returncode is not None and type(result.returncode) is not int)
            or type(result.stdout) is not bytes or type(result.stderr) is not bytes
            or (result.path_exists is not None and type(result.path_exists) is not bool)):
        return AncestorObservation("UNKNOWN", ("probe_incomplete",))
    if result.returncode == 0:
        if result.stdout not in (b"", b"\n", b"\r\n"):
            return AncestorObservation("UNKNOWN", ("unexpected_stdout",))
        return AncestorObservation("ANCESTOR")
    if result.returncode == 1:
        if result.stdout not in (b"", b"\n", b"\r\n"):
            return AncestorObservation("UNKNOWN", ("unexpected_stdout",))
        return AncestorObservation("NOT_ANCESTOR")
    return AncestorObservation("UNKNOWN", ("git_probe_error",))


def _error(code: str, field: str, reason: str) -> None:
    raise protocols.ProtocolError(code, field=field, phase="git", reason=reason)


__all__ = ["AncestorObservation", "AncestorPlan", "build_ancestor_plan", "interpret_ancestor"]
