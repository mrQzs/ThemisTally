#!/usr/bin/env python3
"""07-T2D restricted parallel-admission model.

The model operates on caller-supplied, already validated declarations.  It
does not resolve platform paths, inspect symlinks, acquire OS locks, create a
worktree, or start a process.  Its purpose is to make deterministic ordering,
read/write compatibility, all-or-nothing resource admission, and blocking
reasons explicit before those facts are connected to a scheduler.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Optional, Sequence

from . import protocols


MAX_SAFE_INTEGER = 2**53 - 1
CLAIM_KINDS = frozenset(("path", "key"))
CLAIM_MODES = frozenset(("read", "write", "exclusive", "unknown"))
ACTIVE_STATES = frozenset((
    "CLAIMED", "ADMITTED", "HANDOFF_ACCEPTED", "STARTED", "START_UNKNOWN", "REVIEW_PENDING",
))
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_KEY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
_HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
MAX_CLAIMS = 256
MAX_SCOPE_REFS = 256


class ParallelModelError(ValueError):
    """Invalid declaration; no external state has been changed."""

    def __init__(self, code: str, field: str, reason: str) -> None:
        self.code = code
        self.field = field
        self.reason = reason
        super().__init__(f"{code} {field}: {reason}")


@dataclass(frozen=True)
class ResourceClaim:
    """One repo-local resource declaration."""

    repo_id: str
    kind: str
    key: str
    mode: str


@dataclass(frozen=True)
class ResourceHold:
    """An existing operation's resource claims, including its lifecycle state."""

    repo_id: str
    request_id: str
    task_id: str
    operation_id: str
    state: str
    claims: tuple[ResourceClaim, ...]


@dataclass(frozen=True)
class IndependenceProof:
    """A caller-supplied immutable proof binding the admitted scope."""

    scope_refs: tuple[str, ...]
    digest: str
    guard_version: int


@dataclass(frozen=True)
class AdmissionCandidate:
    """A ready-window candidate with all facts needed for local admission."""

    repo_id: str
    request_id: str
    task_id: str
    priority: int
    admission_seq: int
    claims: tuple[ResourceClaim, ...]
    ready: Optional[bool] = True
    budget_available: Optional[bool] = True
    recovery_clear: Optional[bool] = True
    independence_proof: Optional[IndependenceProof] = None
    guard_version: Optional[int] = None


@dataclass(frozen=True)
class Admission:
    repo_id: str
    request_id: str
    task_id: str
    claims: tuple[ResourceClaim, ...]


@dataclass(frozen=True)
class AdmissionResult:
    admitted: tuple[Admission, ...]
    blocked: tuple[tuple[str, str], ...]


def _text(value: object, field: str, *, pattern: re.Pattern[str] = _ID_RE) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ParallelModelError("E_SCHEMA_FIELDS", field, "invalid_text")
    return value


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or isinstance(value, bool) or value < minimum or value > MAX_SAFE_INTEGER:
        raise ParallelModelError("E_SCHEMA_TYPE", field, "integer_required")
    return value


def _optional_bool(value: object, field: str) -> None:
    if value is not None and type(value) is not bool:
        raise ParallelModelError("E_SCHEMA_TYPE", field, "boolean_or_unknown_required")


def _path_key(value: object, field: str) -> str:
    if type(value) is str and (len(value) > 1024 or any(char in value for char in "[]{}")):
        raise ParallelModelError("E_RESOURCE_KEY", field, "nonportable_path")
    try:
        return protocols.validate_business_path(value, field=field)
    except protocols.ProtocolError as error:
        # Keep this module's error family stable while reusing the canonical
        # business-path profile (including control, bidi, reserved-name and
        # Unicode scalar checks).
        raise ParallelModelError("E_RESOURCE_KEY", field, error.reason) from None


def validate_claim(claim: ResourceClaim, *, field: str = "/claim") -> ResourceClaim:
    if not isinstance(claim, ResourceClaim):
        raise ParallelModelError("E_SCHEMA_TYPE", field, "resource_claim_required")
    repo_id = _text(claim.repo_id, f"{field}/repo_id")
    if claim.kind not in CLAIM_KINDS:
        raise ParallelModelError("E_SCHEMA_FIELDS", f"{field}/kind", "unknown_claim_kind")
    key = (_path_key(claim.key, f"{field}/key") if claim.kind == "path"
           else _text(claim.key, f"{field}/key", pattern=_KEY_RE))
    if claim.mode not in CLAIM_MODES:
        raise ParallelModelError("E_SCHEMA_FIELDS", f"{field}/mode", "unknown_claim_mode")
    return ResourceClaim(repo_id, claim.kind, key, claim.mode)


def normalize_claims(claims: Sequence[ResourceClaim], *, field: str = "/claims") -> tuple[ResourceClaim, ...]:
    if type(claims) not in (tuple, list):
        raise ParallelModelError("E_SCHEMA_TYPE", field, "claims_array_required")
    if len(claims) > MAX_CLAIMS:
        raise ParallelModelError("E_JSON_LIMIT", field, "claim_limit_exceeded")
    if not claims:
        return ()
    normalized = tuple(validate_claim(item, field=f"{field}/{index}") for index, item in enumerate(claims))
    keys = {(item.repo_id, item.kind, item.key) for item in normalized}
    if len(keys) != len(normalized):
        raise ParallelModelError("E_SCHEMA_FIELDS", field, "duplicate_claim")
    return tuple(sorted(normalized, key=lambda item: (item.repo_id, item.kind, item.key, item.mode)))


def claims_from_task(repo_id: str, task: Mapping[str, object]) -> tuple[ResourceClaim, ...]:
    """Map the v1 task declaration to conservative runtime claims.

    Existing ``write_scope`` entries are writes and ``resource_keys`` are
    exclusive.  This deliberately does not infer reads or platform aliases.
    """
    _text(repo_id, "/repo_id")
    if not isinstance(task, Mapping):
        raise ParallelModelError("E_SCHEMA_TYPE", "/task", "mapping_required")
    claims: list[ResourceClaim] = []
    scopes = task.get("write_scope", ())
    keys = task.get("resource_keys", ())
    if type(scopes) not in (tuple, list) or type(keys) not in (tuple, list):
        raise ParallelModelError("E_SCHEMA_TYPE", "/task", "claims_arrays_required")
    for index, scope in enumerate(scopes):
        if (not isinstance(scope, Mapping) or set(scope) != {"path", "kind"}
                or scope.get("kind") not in ("file", "tree")):
            raise ParallelModelError("E_SCHEMA_FIELDS", f"/task/write_scope/{index}", "scope_required")
        claims.append(ResourceClaim(repo_id, "path", scope.get("path"), "write"))  # type: ignore[arg-type]
    for index, key in enumerate(keys):
        claims.append(ResourceClaim(repo_id, "key", key, "exclusive"))  # type: ignore[arg-type]
    return normalize_claims(claims, field="/task/claims")


def _validate_hold(hold: ResourceHold, field: str) -> ResourceHold:
    if not isinstance(hold, ResourceHold):
        raise ParallelModelError("E_SCHEMA_TYPE", field, "resource_hold_required")
    repo_id = _text(hold.repo_id, f"{field}/repo_id")
    _text(hold.request_id, f"{field}/request_id")
    _text(hold.task_id, f"{field}/task_id")
    _text(hold.operation_id, f"{field}/operation_id")
    if hold.state not in ACTIVE_STATES:
        raise ParallelModelError("E_SCHEMA_FIELDS", f"{field}/state", "inactive_hold")
    claims = normalize_claims(hold.claims, field=f"{field}/claims")
    if any(item.repo_id != repo_id for item in claims):
        raise ParallelModelError("E_RESOURCE_SCOPE", f"{field}/claims", "repo_mismatch")
    return ResourceHold(repo_id, hold.request_id, hold.task_id, hold.operation_id, hold.state, claims)


def _validate_candidate(candidate: AdmissionCandidate, field: str) -> AdmissionCandidate:
    if not isinstance(candidate, AdmissionCandidate):
        raise ParallelModelError("E_SCHEMA_TYPE", field, "candidate_required")
    repo_id = _text(candidate.repo_id, f"{field}/repo_id")
    request_id = _text(candidate.request_id, f"{field}/request_id")
    task_id = _text(candidate.task_id, f"{field}/task_id")
    priority = _integer(candidate.priority, f"{field}/priority")
    admission_seq = _integer(candidate.admission_seq, f"{field}/admission_seq")
    claims = normalize_claims(candidate.claims, field=f"{field}/claims")
    for name in ("ready", "budget_available", "recovery_clear"):
        _optional_bool(getattr(candidate, name), f"{field}/{name}")
    proof = candidate.independence_proof
    if proof is not None:
        if (not isinstance(proof, IndependenceProof) or type(proof.scope_refs) is not tuple
                or not proof.scope_refs or len(proof.scope_refs) > MAX_SCOPE_REFS):
            raise ParallelModelError("E_SCHEMA_TYPE", f"{field}/independence_proof", "proof_required")
        for index, ref in enumerate(proof.scope_refs):
            _proof_ref(ref, f"{field}/independence_proof/scope_refs/{index}")
        if type(proof.digest) is not str or _HASH_RE.fullmatch(proof.digest) is None:
            raise ParallelModelError("E_SCHEMA_FIELDS", f"{field}/independence_proof/digest", "sha256_required")
        _integer(proof.guard_version, f"{field}/independence_proof/guard_version", minimum=1)
        if len(set(proof.scope_refs)) != len(proof.scope_refs):
            raise ParallelModelError("E_SCHEMA_FIELDS", f"{field}/independence_proof/scope_refs", "duplicate_scope_ref")
        if candidate.guard_version is None or type(candidate.guard_version) is not int:
            raise ParallelModelError("E_SCHEMA_FIELDS", f"{field}/guard_version", "proof_binding_required")
        if candidate.guard_version != proof.guard_version:
            raise ParallelModelError("E_SCHEMA_FIELDS", f"{field}/independence_proof/guard_version", "guard_mismatch")
        expected_refs = {f"{item.kind}:{item.key}" for item in claims}
        if set(proof.scope_refs) != expected_refs:
            raise ParallelModelError("E_SCHEMA_FIELDS", f"{field}/independence_proof/scope_refs", "scope_mismatch")
    elif candidate.guard_version is not None:
        _integer(candidate.guard_version, f"{field}/guard_version", minimum=1)
    if any(item.repo_id != repo_id for item in claims):
        raise ParallelModelError("E_RESOURCE_SCOPE", f"{field}/claims", "repo_mismatch")
    return AdmissionCandidate(repo_id, request_id, task_id, priority, admission_seq, claims,
                               candidate.ready, candidate.budget_available, candidate.recovery_clear, proof,
                               candidate.guard_version)


def _segments(path: str) -> tuple[str, ...]:
    return tuple(path.split("/"))


def _overlap(left: ResourceClaim, right: ResourceClaim) -> bool:
    if left.kind != right.kind or left.repo_id != right.repo_id:
        return False
    if left.kind == "key":
        return left.key == right.key
    a, b = _segments(left.key), _segments(right.key)
    return a == b or a[:len(b)] == b or b[:len(a)] == a


def claims_conflict(left: ResourceClaim, right: ResourceClaim) -> bool:
    """Return whether two validated claims cannot coexist."""
    left = validate_claim(left, field="/left")
    right = validate_claim(right, field="/right")
    if not _overlap(left, right):
        return False
    return "unknown" in (left.mode, right.mode) or not (left.mode == right.mode == "read")


def _candidate_reason(candidate: AdmissionCandidate) -> Optional[str]:
    if candidate.recovery_clear is not True:
        return "RECOVERY_REQUIRED"
    if candidate.budget_available is not True:
        return "WAIT_BUDGET"
    if candidate.ready is not True:
        return "WAIT_UPSTREAM"
    if any(claim.mode == "unknown" for claim in candidate.claims):
        return "WAIT_RESOURCE"
    return None


def admit_candidates(candidates: Sequence[AdmissionCandidate], holds: Sequence[ResourceHold], *,
                     max_parallel_tasks: int, active_count: int = 0) -> AdmissionResult:
    """Admit candidates in stable order, taking every claim atomically."""
    if type(candidates) not in (tuple, list) or type(holds) not in (tuple, list):
        raise ParallelModelError("E_SCHEMA_TYPE", "/admission", "arrays_required")
    max_parallel_tasks = _integer(max_parallel_tasks, "/max_parallel_tasks", minimum=1)
    active_count = _integer(active_count, "/active_count")
    if active_count > max_parallel_tasks:
        raise ParallelModelError("E_SCHEMA_FIELDS", "/active_count", "over_capacity")
    checked = tuple(_validate_candidate(item, f"/candidates/{index}")
                    for index, item in enumerate(candidates))
    seen = set()
    for item in checked:
        identity = (item.repo_id, item.request_id, item.task_id)
        if identity in seen:
            raise ParallelModelError("E_SCHEMA_FIELDS", "/candidates", "duplicate_task")
        seen.add(identity)
    checked_holds = tuple(_validate_hold(item, f"/holds/{index}") for index, item in enumerate(holds))
    # A caller may provide a stale lower count while the hold snapshot already
    # proves active operations.  Fail closed by counting the proven holds;
    # never let an underreported scalar open an extra concurrency slot.
    active_count = max(active_count, len(checked_holds))
    occupied = [claim for hold in checked_holds for claim in hold.claims]
    active_tasks = {(hold.repo_id, hold.request_id, hold.task_id) for hold in checked_holds}
    ordered = sorted(checked, key=lambda item: (-item.priority, item.admission_seq, item.task_id,
                                                 item.request_id, item.repo_id))
    admitted: list[Admission] = []
    blocked: list[tuple[str, str]] = []
    for candidate in ordered:
        reason = _candidate_reason(candidate)
        if reason is not None:
            blocked.append((candidate.task_id, reason))
            continue
        if (candidate.repo_id, candidate.request_id, candidate.task_id) in active_tasks:
            blocked.append((candidate.task_id, "WAIT_TASK_ACTIVE"))
            continue
        if active_count + len(admitted) >= max_parallel_tasks:
            blocked.append((candidate.task_id, "WAIT_CONCURRENCY"))
            continue
        if max_parallel_tasks > 1 and candidate.claims and candidate.independence_proof is None:
            blocked.append((candidate.task_id, "WAIT_RESOURCE"))
            continue
        if any(claims_conflict(left, right) for left in candidate.claims for right in occupied):
            blocked.append((candidate.task_id, "WAIT_RESOURCE"))
            continue
        admission = Admission(candidate.repo_id, candidate.request_id, candidate.task_id, candidate.claims)
        admitted.append(admission)
        occupied.extend(candidate.claims)
    return AdmissionResult(tuple(admitted), tuple(blocked))


def no_progress_reason(result: AdmissionResult, *, required_remaining: Optional[bool]) -> str:
    """Explain why a required workflow did not advance; no candidates is not completion."""
    _optional_bool(required_remaining, "/required_remaining")
    if required_remaining is False:
        return "COMPLETE_PROVEN"
    if required_remaining is None:
        return "WAIT_REQUIRED_STATE_UNKNOWN"
    if result.admitted:
        return "PROGRESS"
    if not result.blocked:
        return "WAIT_NO_READY"
    reasons = {reason for _, reason in result.blocked}
    for reason in ("RECOVERY_REQUIRED", "WAIT_RESOURCE", "WAIT_BUDGET", "WAIT_UPSTREAM", "WAIT_CONCURRENCY"):
        if reason in reasons:
            return reason
    return "WAIT_NO_READY"


def _proof_ref(value: object, field: str) -> str:
    """Validate an independence reference without rejecting Unicode paths."""
    # A canonical ``path:<business-path>`` reference may add the kind prefix
    # to the business-path byte limit; leave room for that prefix and Unicode
    # code-point expansion while retaining a finite bound.
    if type(value) is not str or not value or len(value) > 8192:
        raise ParallelModelError("E_SCHEMA_FIELDS", field, "invalid_scope_ref")
    if any(ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F
           or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ParallelModelError("E_SCHEMA_FIELDS", field, "invalid_scope_ref")
    return value


__all__ = [
    "ACTIVE_STATES", "CLAIM_KINDS", "CLAIM_MODES", "MAX_CLAIMS", "MAX_SCOPE_REFS", "Admission", "AdmissionCandidate", "AdmissionResult",
    "IndependenceProof", "ParallelModelError", "ResourceClaim", "ResourceHold", "admit_candidates", "claims_conflict",
    "claims_from_task", "no_progress_reason", "normalize_claims", "validate_claim",
]
