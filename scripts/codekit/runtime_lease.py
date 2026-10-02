"""Boot-bound lease facts for the S4 runtime boundary.

The module is an adapter contract and deterministic fixture implementation. It
does not query a PID or kill a process; platform adapters must supply the
observed process identity and tri-state liveness fact.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .identity import ProcessIdentity, process_identity_decision, KNOWN


class LeaseError(ValueError):
    def __init__(self, code: str, message: str = "lease rejected") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class RuntimeLease:
    run_id: str
    generation: int
    owner: ProcessIdentity
    expires_at: float
    token: str


@dataclass(frozen=True)
class LeaseDecision:
    decision: str
    reasons: tuple[str, ...] = ()


def issue_lease(run_id: str, owner: ProcessIdentity, *, generation: int, expires_at: float) -> RuntimeLease:
    if type(run_id) is not str or not run_id or type(generation) is not int or generation < 1:
        raise LeaseError("E_LEASE_SCHEMA")
    if type(expires_at) not in (int, float) or expires_at < 0:
        raise LeaseError("E_LEASE_SCHEMA")
    if process_identity_decision(owner).status != KNOWN:
        raise LeaseError("E_OWNER_UNKNOWN")
    raw = json.dumps({"run_id": run_id, "generation": generation, "owner": owner.canonical_key,
                      "expires_at": expires_at}, sort_keys=True, separators=(",", ":"))
    token = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return RuntimeLease(run_id, generation, owner, float(expires_at), token)


def assess_lease(lease: RuntimeLease, *, current_generation: int, observed_owner: ProcessIdentity,
                 process_alive: bool | None, now: float) -> LeaseDecision:
    if type(lease) is not RuntimeLease or type(current_generation) is not int or current_generation < 1:
        raise LeaseError("E_LEASE_SCHEMA")
    if type(now) not in (int, float) or now < 0 or type(process_alive) not in (bool, type(None)):
        raise LeaseError("E_LEASE_SCHEMA")
    if current_generation != lease.generation:
        return LeaseDecision("BLOCK", ("FENCED_GENERATION",))
    if observed_owner.canonical_key != lease.owner.canonical_key:
        return LeaseDecision("BLOCK", ("OWNER_IDENTITY_MISMATCH",))
    if now <= lease.expires_at:
        return LeaseDecision("ACTIVE")
    if process_alive is True:
        return LeaseDecision("HOLD", ("EXPIRED_BUT_PROCESS_ALIVE",))
    if process_alive is None:
        return LeaseDecision("BLOCK", ("PROCESS_LIVENESS_UNKNOWN",))
    return LeaseDecision("RECLAIM_ALLOWED", ("EXPIRED_AND_PROCESS_DEAD",))


def release_lease(lease: RuntimeLease, *, token: str, owner: ProcessIdentity, generation: int) -> LeaseDecision:
    if type(token) is not str or token != lease.token:
        return LeaseDecision("BLOCK", ("LEASE_TOKEN_MISMATCH",))
    if generation != lease.generation or owner.canonical_key != lease.owner.canonical_key:
        return LeaseDecision("BLOCK", ("OWNER_FENCED",))
    return LeaseDecision("RELEASE_ALLOWED")


__all__ = ["LeaseDecision", "LeaseError", "RuntimeLease", "assess_lease", "issue_lease", "release_lease"]
