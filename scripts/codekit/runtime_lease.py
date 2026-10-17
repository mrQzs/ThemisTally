"""Boot-bound lease facts for the S4 runtime boundary.

The module is an adapter contract and deterministic fixture implementation. It
does not query a PID or kill a process; platform adapters must supply the
observed process identity and tri-state liveness fact.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any

from .identity import IdentityModelError, ProcessIdentity, process_identity_decision, KNOWN


_MAX_SAFE_INTEGER = 2**53 - 1


class LeaseError(ValueError):
    def __init__(self, code: str, message: str = "lease rejected") -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class RuntimeLease:
    run_id: str
    generation: int
    owner: ProcessIdentity
    expires_at: float
    token: str

    def __post_init__(self) -> None:
        _validate_lease_fields(self)


@dataclass(frozen=True)
class LeaseDecision:
    decision: str
    reasons: tuple[str, ...] = ()


_TOKEN_RE = re.compile(r"[0-9a-f]{64}\Z")


def _lease_text(value: Any, field: str) -> str:
    if type(value) is not str or not value:
        raise LeaseError("E_LEASE_SCHEMA", f"{field} must be non-empty text")
    if any(ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F or 0xD800 <= ord(char) <= 0xDFFF
           for char in value):
        raise LeaseError("E_LEASE_SCHEMA", f"{field} contains a control or non-scalar character")
    return value


def _lease_generation(value: Any, field: str) -> int:
    if type(value) is not int or value < 1 or value > _MAX_SAFE_INTEGER:
        raise LeaseError("E_LEASE_SCHEMA", f"{field} must be a positive integer")
    return value


def _lease_time(value: Any, field: str) -> float:
    if type(value) not in (int, float) or value < 0:
        raise LeaseError("E_LEASE_SCHEMA", f"{field} must be a finite non-negative number")
    # Converting an oversized integer to float raises OverflowError on some
    # Python versions; map that malformed input to the contract error rather
    # than leaking an implementation exception.
    try:
        converted = float(value)
    except (OverflowError, ValueError):
        raise LeaseError("E_LEASE_SCHEMA", f"{field} must be a finite non-negative number")
    if not math.isfinite(converted) or converted > _MAX_SAFE_INTEGER:
        raise LeaseError("E_LEASE_SCHEMA", f"{field} must be a finite non-negative number")
    return converted


def _owner_key(owner: Any, *, allow_unknown: bool = False) -> str | None:
    if not isinstance(owner, ProcessIdentity):
        raise LeaseError("E_OWNER_UNKNOWN")
    try:
        decision = process_identity_decision(owner)
        owner_key = owner.canonical_key
    except IdentityModelError as exc:
        if allow_unknown:
            return None
        raise LeaseError("E_OWNER_UNKNOWN") from exc
    if decision.status != KNOWN or owner_key is None:
        if allow_unknown:
            return None
        raise LeaseError("E_OWNER_UNKNOWN")
    return owner_key


def _derive_token(run_id: str, generation: int, owner_key: str, expires_at: float) -> str:
    raw = json.dumps({"run_id": run_id, "generation": generation, "owner": owner_key,
                      "expires_at": expires_at}, sort_keys=True, separators=(",", ":"),
                     allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_lease_fields(lease: RuntimeLease) -> None:
    if type(lease) is not RuntimeLease:
        raise LeaseError("E_LEASE_SCHEMA")
    run_id = _lease_text(lease.run_id, "run_id")
    generation = _lease_generation(lease.generation, "generation")
    expires_at = _lease_time(lease.expires_at, "expires_at")
    owner_key = _owner_key(lease.owner)
    if type(lease.token) is not str or _TOKEN_RE.fullmatch(lease.token) is None:
        raise LeaseError("E_LEASE_TOKEN", "token must be lowercase SHA-256")
    if lease.token != _derive_token(run_id, generation, owner_key, expires_at):
        raise LeaseError("E_LEASE_TOKEN", "token does not bind lease fields")


def issue_lease(run_id: str, owner: ProcessIdentity, *, generation: int, expires_at: float) -> RuntimeLease:
    run_id = _lease_text(run_id, "run_id")
    generation = _lease_generation(generation, "generation")
    expires_at = _lease_time(expires_at, "expires_at")
    owner_key = _owner_key(owner)
    return RuntimeLease(run_id, generation, owner, expires_at,
                        _derive_token(run_id, generation, owner_key, expires_at))


def assess_lease(lease: RuntimeLease, *, current_generation: int, observed_owner: ProcessIdentity,
                 process_alive: bool | None, now: float) -> LeaseDecision:
    _validate_lease_fields(lease)
    current_generation = _lease_generation(current_generation, "current_generation")
    now = _lease_time(now, "now")
    if type(process_alive) not in (bool, type(None)):
        raise LeaseError("E_LEASE_SCHEMA")
    if current_generation != lease.generation:
        return LeaseDecision("BLOCK", ("FENCED_GENERATION",))
    observed_key = _owner_key(observed_owner, allow_unknown=True)
    if observed_key is None:
        return LeaseDecision("BLOCK", ("OWNER_IDENTITY_MISMATCH",))
    if observed_key != lease.owner.canonical_key:
        return LeaseDecision("BLOCK", ("OWNER_IDENTITY_MISMATCH",))
    if now <= lease.expires_at:
        return LeaseDecision("ACTIVE")
    if process_alive is True:
        return LeaseDecision("HOLD", ("EXPIRED_BUT_PROCESS_ALIVE",))
    if process_alive is None:
        return LeaseDecision("BLOCK", ("PROCESS_LIVENESS_UNKNOWN",))
    return LeaseDecision("RECLAIM_ALLOWED", ("EXPIRED_AND_PROCESS_DEAD",))


def release_lease(lease: RuntimeLease, *, token: str, owner: ProcessIdentity, generation: int) -> LeaseDecision:
    _validate_lease_fields(lease)
    generation = _lease_generation(generation, "generation")
    if type(token) is not str or token != lease.token:
        return LeaseDecision("BLOCK", ("LEASE_TOKEN_MISMATCH",))
    owner_key = _owner_key(owner, allow_unknown=True)
    if generation != lease.generation or owner_key is None or owner_key != lease.owner.canonical_key:
        return LeaseDecision("BLOCK", ("OWNER_FENCED",))
    return LeaseDecision("RELEASE_ALLOWED")


__all__ = ["LeaseDecision", "LeaseError", "RuntimeLease", "assess_lease", "issue_lease", "release_lease"]
