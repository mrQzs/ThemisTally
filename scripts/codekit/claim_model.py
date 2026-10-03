#!/usr/bin/env python3
"""07-T2C-S pure claim and handoff boundary model.

This module consumes facts already obtained by trusted owners.  It never
opens a database, reads a PID, starts a process, or treats a directory claim
as an atomic handoff.  Its purpose is to make the three-way unknown decisions
and activity/idempotency boundaries executable before a production ledger is
designed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from . import protocols


CLAIMED = "CLAIMED"
ADMITTED = "ADMITTED"
HANDOFF_ACCEPTED = "HANDOFF_ACCEPTED"
STARTED = "STARTED"
START_UNKNOWN = "START_UNKNOWN"
REVIEW_PENDING = "REVIEW_PENDING"
ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"
CANCELLED_NOT_STARTED = "CANCELLED_NOT_STARTED"

ACTIVE_TASK_STATES = frozenset({
    CLAIMED, ADMITTED, HANDOFF_ACCEPTED, STARTED, START_UNKNOWN, REVIEW_PENDING,
})
KNOWN_STATES = frozenset(ACTIVE_TASK_STATES | {
    ACCEPTED, REJECTED, CANCELLED_NOT_STARTED,
})


class ClaimModelError(ValueError):
    """Invalid model input; no external state has been changed."""

    def __init__(self, code: str, field: str, reason: str) -> None:
        self.code = code
        self.field = field
        self.reason = reason
        super().__init__(f"{code} {field}: {reason}")


@dataclass(frozen=True)
class ClaimReceipt:
    """Immutable receipt shape for a single logical operation."""

    repo_id: str
    request_id: str
    task_id: str
    plan_version: int
    operation_id: str
    state: str
    controller_generation: int
    claim_generation: int
    guard_version: int
    stop_epoch: int
    owner: str
    lease_until: float
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True)
class ActiveOperation:
    repo_id: str
    request_id: str
    task_id: str
    plan_version: int
    operation_id: str
    state: str


@dataclass(frozen=True)
class ClaimRequest:
    repo_id: str
    request_id: str
    task_id: str
    plan_version: int
    idempotency_key: str
    request_fingerprint: str
    controller_generation: int
    guard_version: int
    stop_epoch: int


@dataclass(frozen=True)
class ClaimFacts:
    request_open: Optional[bool]
    stop_requested: Optional[bool]
    controller_generation: Optional[int]
    guard_version: Optional[int]
    stop_epoch: Optional[int]
    contract_valid: Optional[bool]
    baseline_valid: Optional[bool]
    upstream_accepted: Optional[bool]
    resources_available: Optional[bool]
    budget_available: Optional[bool]


@dataclass(frozen=True)
class HandoffFacts:
    """Trusted, point-in-time facts supplied to the pure handoff decision."""

    request_open: Optional[bool]
    stop_requested: Optional[bool]
    controller_generation: Optional[int]
    claim_generation: Optional[int]
    guard_version: Optional[int]
    stop_epoch: Optional[int]
    lease_valid: Optional[bool]
    budget_available: Optional[bool]
    resources_available: Optional[bool]


@dataclass(frozen=True)
class Decision:
    decision: str
    reasons: Tuple[str, ...] = ()
    operation_id: Optional[str] = None


def _text(value: object, field: str, *, max_len: int = 256) -> str:
    if type(value) is not str or not value or len(value) > max_len or "\x00" in value:
        raise ClaimModelError("E_SCHEMA_FIELDS", field, "nonempty_text_required")
    if any(ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F
           or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ClaimModelError("E_SCHEMA_FIELDS", field, "unicode_scalar_required")
    return value


def _positive(value: object, field: str) -> int:
    if type(value) is not int:
        raise ClaimModelError("E_SCHEMA_TYPE", field, "exact_integer_required")
    if value < 1 or value > protocols.MAX_SAFE_INTEGER:
        raise ClaimModelError("E_INTEGER_RANGE", field, "positive_integer_required")
    return value


def _nonnegative(value: object, field: str) -> int:
    if type(value) is not int:
        raise ClaimModelError("E_SCHEMA_TYPE", field, "exact_integer_required")
    if value < 0 or value > protocols.MAX_SAFE_INTEGER:
        raise ClaimModelError("E_INTEGER_RANGE", field, "nonnegative_integer_required")
    return value


def _optional_bool(value: object, field: str) -> Optional[bool]:
    if value is not None and type(value) is not bool:
        raise ClaimModelError("E_SCHEMA_TYPE", field, "optional_boolean_required")
    return value


def _optional_int(value: object, field: str, *, minimum: int = 0) -> Optional[int]:
    if value is None:
        return None
    if type(value) is not int:
        raise ClaimModelError("E_SCHEMA_TYPE", field, "optional_integer_required")
    if value < minimum or value > protocols.MAX_SAFE_INTEGER:
        raise ClaimModelError("E_INTEGER_RANGE", field, "integer_out_of_range")
    return value


def _validate_receipt(receipt: ClaimReceipt) -> None:
    if not isinstance(receipt, ClaimReceipt):
        raise ClaimModelError("E_SCHEMA_TYPE", "/receipt", "claim_receipt_required")
    protocols.validate_logical_id(receipt.repo_id, field="/receipt/repo_id")
    protocols.validate_request_id(receipt.request_id, field="/receipt/request_id")
    protocols.validate_task_id(receipt.task_id, field="/receipt/task_id")
    _positive(receipt.plan_version, "/receipt/plan_version")
    protocols.validate_logical_id(receipt.operation_id, field="/receipt/operation_id")
    if receipt.state not in KNOWN_STATES:
        raise ClaimModelError("E_SCHEMA_FIELDS", "/receipt/state", "unknown_state")
    for name in ("controller_generation", "claim_generation", "guard_version"):
        _positive(getattr(receipt, name), f"/receipt/{name}")
    _nonnegative(receipt.stop_epoch, "/receipt/stop_epoch")
    _text(receipt.owner, "/receipt/owner")
    if (type(receipt.lease_until) is not float or not math.isfinite(receipt.lease_until)
            or receipt.lease_until < 0 or receipt.lease_until > protocols.MAX_SAFE_INTEGER):
        raise ClaimModelError("E_SCHEMA_TYPE", "/receipt/lease_until", "finite_nonnegative_float_required")
    _text(receipt.idempotency_key, "/receipt/idempotency_key")
    _text(receipt.request_fingerprint, "/receipt/request_fingerprint")


def validate_claim_receipt(receipt: ClaimReceipt) -> ClaimReceipt:
    """Validate and return the same immutable receipt; never persists it."""
    _validate_receipt(receipt)
    return receipt


def idempotency_decision(existing: Optional[ClaimReceipt], *, key: str,
                         request_fingerprint: str, repo_id: Optional[str] = None,
                         request_id: Optional[str] = None, task_id: Optional[str] = None,
                         plan_version: Optional[int] = None) -> Decision:
    """Resolve replay/conflict without allocating a second operation."""
    _text(key, "/idempotency_key")
    _text(request_fingerprint, "/request_fingerprint")
    if existing is None:
        return Decision("NEW")
    _validate_receipt(existing)
    if repo_id is not None or request_id is not None or task_id is not None or plan_version is not None:
        protocols.validate_logical_id(repo_id, field="/repo_id")
        protocols.validate_request_id(request_id, field="/request_id")
        protocols.validate_task_id(task_id, field="/task_id")
        _positive(plan_version, "/plan_version")
        if ((existing.repo_id, existing.request_id, existing.task_id, existing.plan_version)
                != (repo_id, request_id, task_id, plan_version)):
            return Decision("CONFLICT", ("idempotency_scope_mismatch",), existing.operation_id)
    if existing.idempotency_key != key:
        return Decision("NEW")
    if existing.request_fingerprint != request_fingerprint:
        return Decision("CONFLICT", ("idempotency_fingerprint_mismatch",), existing.operation_id)
    return Decision("REPLAY", (), existing.operation_id)


def active_task_decision(operations: Iterable[ActiveOperation], *, repo_id: str,
                         request_id: str, task_id: str, plan_version: int) -> Decision:
    """Reject an active task even when a caller presents a newer plan version."""
    protocols.validate_logical_id(repo_id, field="/repo_id")
    protocols.validate_request_id(request_id, field="/request_id")
    protocols.validate_task_id(task_id, field="/task_id")
    _positive(plan_version, "/plan_version")
    conflicts = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, ActiveOperation):
            raise ClaimModelError("E_SCHEMA_TYPE", f"/operations/{index}", "active_operation_required")
        protocols.validate_logical_id(operation.repo_id, field=f"/operations/{index}/repo_id")
        protocols.validate_request_id(operation.request_id, field=f"/operations/{index}/request_id")
        protocols.validate_task_id(operation.task_id, field=f"/operations/{index}/task_id")
        _positive(operation.plan_version, f"/operations/{index}/plan_version")
        protocols.validate_logical_id(operation.operation_id, field=f"/operations/{index}/operation_id")
        if operation.state not in KNOWN_STATES:
            raise ClaimModelError("E_SCHEMA_FIELDS", f"/operations/{index}/state", "unknown_state")
        if ((operation.repo_id, operation.request_id, operation.task_id)
                == (repo_id, request_id, task_id)
                and operation.state in ACTIVE_TASK_STATES):
            conflicts.append(operation.operation_id)
    if conflicts:
        return Decision("BLOCK", ("active_task",), conflicts[0])
    return Decision("ALLOW")


def _validate_claim_request(request: ClaimRequest) -> None:
    if not isinstance(request, ClaimRequest):
        raise ClaimModelError("E_SCHEMA_TYPE", "/request", "claim_request_required")
    protocols.validate_logical_id(request.repo_id, field="/request/repo_id")
    protocols.validate_request_id(request.request_id, field="/request/request_id")
    protocols.validate_task_id(request.task_id, field="/request/task_id")
    _positive(request.plan_version, "/request/plan_version")
    _text(request.idempotency_key, "/request/idempotency_key")
    _text(request.request_fingerprint, "/request/request_fingerprint")
    _positive(request.controller_generation, "/request/controller_generation")
    _positive(request.guard_version, "/request/guard_version")
    _nonnegative(request.stop_epoch, "/request/stop_epoch")


def claim_decision(request: ClaimRequest, facts: ClaimFacts,
                   operations: Iterable[ActiveOperation] = (),
                   existing: Optional[ClaimReceipt] = None) -> Decision:
    """Evaluate the pre-transaction claim gate without allocating anything."""
    _validate_claim_request(request)
    if not isinstance(facts, ClaimFacts):
        raise ClaimModelError("E_SCHEMA_TYPE", "/facts", "claim_facts_required")
    _validate_claim_facts(facts)
    idem = idempotency_decision(existing, key=request.idempotency_key,
                                request_fingerprint=request.request_fingerprint,
                                repo_id=request.repo_id, request_id=request.request_id,
                                task_id=request.task_id, plan_version=request.plan_version)
    if idem.decision != "NEW":
        return idem
    active = active_task_decision(operations, repo_id=request.repo_id, request_id=request.request_id,
                                  task_id=request.task_id, plan_version=request.plan_version)
    if active.decision != "ALLOW":
        return active
    reasons = []

    def require_true(value: object, unknown_reason: str, false_reason: str) -> None:
        if value is None:
            reasons.append(unknown_reason)
        elif value is not True:
            reasons.append(false_reason)

    def require_false(value: object, unknown_reason: str, true_reason: str) -> None:
        if value is None:
            reasons.append(unknown_reason)
        elif value is not False:
            reasons.append(true_reason)

    require_true(facts.request_open, "request_open_unknown", "request_closed")
    require_false(facts.stop_requested, "stop_state_unknown", "stop_requested")
    if facts.controller_generation is None:
        reasons.append("controller_generation_unknown")
    elif facts.controller_generation != request.controller_generation:
        reasons.append("controller_generation_mismatch")
    if facts.guard_version is None:
        reasons.append("guard_version_unknown")
    elif facts.guard_version != request.guard_version:
        reasons.append("guard_version_mismatch")
    if facts.stop_epoch is None:
        reasons.append("stop_epoch_unknown")
    elif facts.stop_epoch != request.stop_epoch:
        reasons.append("stop_epoch_mismatch")
    require_true(facts.contract_valid, "contract_unknown", "contract_invalid")
    require_true(facts.baseline_valid, "baseline_unknown", "baseline_invalid")
    require_true(facts.upstream_accepted, "upstream_acceptance_unknown", "upstream_not_accepted")
    require_true(facts.resources_available, "resources_unknown", "resources_unavailable")
    require_true(facts.budget_available, "budget_unknown", "budget_unavailable")
    if reasons:
        return Decision("BLOCK", tuple(reasons))
    return Decision(CLAIMED)


def handoff_decision(receipt: ClaimReceipt, facts: HandoffFacts) -> Decision:
    """Return HANDOFF_ACCEPTED only when every mutable guard is affirmatively true."""
    _validate_receipt(receipt)
    if receipt.state not in (CLAIMED, ADMITTED):
        return Decision("BLOCK", ("handoff_state_invalid",), receipt.operation_id)
    if not isinstance(facts, HandoffFacts):
        raise ClaimModelError("E_SCHEMA_TYPE", "/facts", "handoff_facts_required")
    _validate_handoff_facts(facts)
    reasons = []

    def require_true(value: object, unknown_reason: str, false_reason: str) -> None:
        if value is None:
            reasons.append(unknown_reason)
        elif value is not True:
            reasons.append(false_reason)

    def require_false(value: object, unknown_reason: str, true_reason: str) -> None:
        if value is None:
            reasons.append(unknown_reason)
        elif value is not False:
            reasons.append(true_reason)

    require_true(facts.request_open, "request_open_unknown", "request_closed")
    require_false(facts.stop_requested, "stop_state_unknown", "stop_requested")
    if facts.controller_generation is None:
        reasons.append("controller_generation_unknown")
    elif facts.controller_generation != receipt.controller_generation:
        reasons.append("controller_generation_mismatch")
    if facts.claim_generation is None:
        reasons.append("claim_generation_unknown")
    elif facts.claim_generation != receipt.claim_generation:
        reasons.append("claim_generation_mismatch")
    if facts.guard_version is None:
        reasons.append("guard_version_unknown")
    elif facts.guard_version != receipt.guard_version:
        reasons.append("guard_version_mismatch")
    if facts.stop_epoch is None:
        reasons.append("stop_epoch_unknown")
    elif facts.stop_epoch != receipt.stop_epoch:
        reasons.append("stop_epoch_mismatch")
    require_true(facts.lease_valid, "lease_unknown", "lease_expired")
    require_true(facts.budget_available, "budget_unknown", "budget_unavailable")
    require_true(facts.resources_available, "resources_unknown", "resources_unavailable")
    if reasons:
        return Decision("BLOCK", tuple(reasons), receipt.operation_id)
    return Decision(HANDOFF_ACCEPTED, (), receipt.operation_id)


def _validate_claim_facts(facts: ClaimFacts) -> None:
    for name in ("request_open", "stop_requested", "contract_valid", "baseline_valid",
                 "upstream_accepted", "resources_available", "budget_available"):
        _optional_bool(getattr(facts, name), f"/facts/{name}")
    for name in ("controller_generation", "guard_version"):
        _optional_int(getattr(facts, name), f"/facts/{name}", minimum=1)
    _optional_int(facts.stop_epoch, "/facts/stop_epoch")


def _validate_handoff_facts(facts: HandoffFacts) -> None:
    for name in ("request_open", "stop_requested", "lease_valid", "budget_available", "resources_available"):
        _optional_bool(getattr(facts, name), f"/facts/{name}")
    for name in ("controller_generation", "claim_generation", "guard_version"):
        _optional_int(getattr(facts, name), f"/facts/{name}", minimum=1)
    _optional_int(facts.stop_epoch, "/facts/stop_epoch")


def liveness_decision(*, state: str, handoff_accepted: bool,
                      liveness: Optional[bool], identity_match: Optional[bool],
                      not_started_proven: Optional[bool], fencing_confirmed: bool) -> Decision:
    """Decide whether an operation may be released after an uncertain start.

    ``None`` is never treated as false.  A handoff that already committed can
    only be released with complete NOT_STARTED evidence; otherwise it remains
    START_UNKNOWN for recovery.
    """
    if state not in KNOWN_STATES:
        raise ClaimModelError("E_SCHEMA_FIELDS", "/state", "unknown_state")
    if type(handoff_accepted) is not bool or type(fencing_confirmed) is not bool:
        raise ClaimModelError("E_SCHEMA_TYPE", "/facts", "exact_boolean_required")
    _optional_bool(liveness, "/liveness")
    _optional_bool(identity_match, "/identity_match")
    _optional_bool(not_started_proven, "/not_started_proven")
    if handoff_accepted and state not in (HANDOFF_ACCEPTED, STARTED, START_UNKNOWN):
        return Decision("BLOCK", ("handoff_state_invalid",))
    if handoff_accepted and state == STARTED:
        return Decision("BLOCK", ("started_requires_reconciliation",))
    if not handoff_accepted and state not in (CLAIMED, ADMITTED):
        return Decision("BLOCK", ("pre_handoff_state_invalid",))
    if liveness is True:
        if identity_match is not True:
            return Decision("START_UNKNOWN", ("process_identity_unknown",) if identity_match is None
                            else ("process_identity_mismatch",))
        return Decision("RETAIN_ACTIVE", ("process_alive",))
    if liveness is None:
        return Decision("START_UNKNOWN", ("process_liveness_unknown",))
    if identity_match is not True:
        return Decision("START_UNKNOWN", ("process_identity_unknown",) if identity_match is None
                        else ("process_identity_mismatch",))
    if not fencing_confirmed:
        return Decision("BLOCK", ("owner_not_fenced",))
    if not_started_proven is not True:
        return Decision("START_UNKNOWN", ("not_started_proof_unknown",) if not_started_proven is None
                        else ("not_started_proof_negative",))
    if handoff_accepted:
        return Decision(CANCELLED_NOT_STARTED)
    return Decision(CANCELLED_NOT_STARTED)


def cleanup_decision(*, stray_processes: Optional[bool],
                     scope_empty_verified: Optional[bool]) -> Decision:
    """Release worktree/resource holds only after the supervised scope is clear."""
    _optional_bool(stray_processes, "/stray_processes")
    _optional_bool(scope_empty_verified, "/scope_empty_verified")
    if stray_processes is True:
        return Decision("RECOVERY_REQUIRED", ("stray_processes_present",))
    if stray_processes is None:
        return Decision("RECOVERY_REQUIRED", ("stray_processes_unknown",))
    if scope_empty_verified is None:
        return Decision("RECOVERY_REQUIRED", ("supervision_scope_unknown",))
    if scope_empty_verified is not True:
        return Decision("BLOCK", ("supervision_scope_not_empty",))
    return Decision("RELEASE")


__all__ = [
    "ACCEPTED", "ADMITTED", "ACTIVE_TASK_STATES", "ActiveOperation", "CANCELLED_NOT_STARTED",
    "CLAIMED", "ClaimModelError", "ClaimReceipt", "Decision", "HANDOFF_ACCEPTED", "HandoffFacts",
    "ClaimFacts", "ClaimRequest", "KNOWN_STATES", "REJECTED", "REVIEW_PENDING", "STARTED",
    "START_UNKNOWN", "active_task_decision", "claim_decision", "cleanup_decision", "handoff_decision",
    "idempotency_decision", "liveness_decision",
    "validate_claim_receipt",
]
