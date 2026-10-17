"""Explicit baseline-use authorization and multi-upstream merge gate."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from . import protocols
from .acceptance import AcceptedResult, AcceptanceRevocation, validate_accepted_result, validate_acceptance_revocation
from .baseline_binding import BaselineBinding, validate_baseline_binding


@dataclass(frozen=True)
class BaselineUseDecision:
    decision: str
    reasons: tuple[str, ...] = ()
    integration_acceptance_id: str | None = None


def resolve_baseline_use(
    binding: BaselineBinding | Mapping[str, Any],
    accepted_results: Sequence[AcceptedResult | Mapping[str, Any]],
    revocations: Sequence[AcceptanceRevocation | Mapping[str, Any]],
    *,
    required_acceptance_ids: Sequence[str],
    integration_acceptance_id: str | None,
    integration_candidate_ref: Mapping[str, Any] | None,
    authorization_current: bool | None,
    expected_request_id: str,
    expected_guard_version: int,
) -> BaselineUseDecision:
    """Require explicit current authorization and an accepted merge candidate."""
    if type(accepted_results) not in (list, tuple) or len(accepted_results) > 1024:
        raise protocols.ProtocolError("E_SCHEMA_TYPE", field="/accepted_results", phase="baseline_use",
                                      reason="bounded_array_required")
    if type(revocations) not in (list, tuple) or len(revocations) > 1024:
        raise protocols.ProtocolError("E_SCHEMA_TYPE", field="/revocations", phase="baseline_use",
                                      reason="bounded_array_required")
    if type(required_acceptance_ids) not in (list, tuple) or any(type(value) is not str or not value for value in required_acceptance_ids):
        raise protocols.ProtocolError("E_SCHEMA_TYPE", field="/required_acceptance_ids", phase="baseline_use",
                                      reason="nonempty_string_array_required")
    if integration_acceptance_id is not None and (type(integration_acceptance_id) is not str or not integration_acceptance_id):
        raise protocols.ProtocolError("E_SCHEMA_TYPE", field="/integration_acceptance_id", phase="baseline_use",
                                      reason="string_or_null_required")
    if integration_candidate_ref is not None and not isinstance(integration_candidate_ref, Mapping):
        raise protocols.ProtocolError("E_SCHEMA_TYPE", field="/integration_candidate_ref", phase="baseline_use",
                                      reason="object_or_null_required")
    if authorization_current is not None and type(authorization_current) is not bool:
        raise protocols.ProtocolError("E_SCHEMA_TYPE", field="/authorization_current", phase="baseline_use",
                                      reason="boolean_or_null_required")
    protocols.validate_request_id(expected_request_id, field="/expected_request_id")
    protocols.require_int(expected_guard_version, field="/expected_guard_version", minimum=1)
    if not isinstance(binding, BaselineBinding):
        binding = validate_baseline_binding(binding)
    reasons: list[str] = []
    if binding.guard_version != expected_guard_version:
        reasons.append("BASELINE_GUARD_MISMATCH")
    if authorization_current is not True:
        reasons.append("REJECT_BASELINE_AUTHORIZATION" if authorization_current is False else "WAIT_BASELINE_AUTHORIZATION")
    accepted = {}
    for value in accepted_results:
        item = value if isinstance(value, AcceptedResult) else validate_accepted_result(value)
        if item.acceptance_id in accepted and accepted[item.acceptance_id].record != item.record:
            reasons.append("ACCEPTANCE_CONFLICT")
        accepted[item.acceptance_id] = item
    revoked = set()
    for value in revocations:
        item = value if isinstance(value, AcceptanceRevocation) else validate_acceptance_revocation(value)
        revoked.add(item.acceptance_id)
    required = tuple(required_acceptance_ids)
    if len(set(required)) != len(required):
        reasons.append("ACCEPTANCE_CONFLICT")
    checked: set[str] = set()

    def check_closure(acceptance_id: str, active: set[str]) -> None:
        if acceptance_id in active:
            reasons.append("ACCEPTANCE_CONFLICT")
            return
        if acceptance_id in checked:
            return
        checked.add(acceptance_id)
        item = accepted.get(acceptance_id)
        if item is None:
            reasons.append("WAIT_UPSTREAM_ACCEPTANCE")
            return
        if acceptance_id in revoked:
            reasons.append("ACCEPTANCE_REVOKED")
        if item.request_id != expected_request_id or item.guard_version != expected_guard_version:
            reasons.append("UPSTREAM_GUARD_MISMATCH")
        active.add(acceptance_id)
        for upstream_id in item.record["upstream_acceptance_ids"]:
            check_closure(upstream_id, active)
        active.remove(acceptance_id)

    for acceptance_id in required:
        item = accepted.get(acceptance_id)
        if item is None:
            reasons.append("WAIT_UPSTREAM_ACCEPTANCE")
        elif acceptance_id in revoked:
            reasons.append("ACCEPTANCE_REVOKED")
        elif item.request_id != expected_request_id or item.guard_version != expected_guard_version:
            reasons.append("UPSTREAM_GUARD_MISMATCH")
        check_closure(acceptance_id, set())
    merge = accepted.get(integration_acceptance_id) if integration_acceptance_id else None
    if merge is None:
        reasons.append("WAIT_INTEGRATION_ACCEPTANCE")
    elif integration_acceptance_id in revoked:
        reasons.append("ACCEPTANCE_REVOKED")
    else:
        if merge.request_id != expected_request_id or merge.guard_version != expected_guard_version:
            reasons.append("INTEGRATION_GUARD_MISMATCH")
        if set(merge.record["upstream_acceptance_ids"]) != set(required):
            reasons.append("INTEGRATION_UPSTREAM_MISMATCH")
        if integration_candidate_ref is None or dict(merge.record["candidate_ref"]) != dict(integration_candidate_ref):
            reasons.append("INTEGRATION_CANDIDATE_MISMATCH")
    return BaselineUseDecision(
        "BASELINE_USE_ALLOWED" if not reasons else "BLOCK",
        tuple(dict.fromkeys(reasons)),
        integration_acceptance_id,
    )


__all__ = ["BaselineUseDecision", "resolve_baseline_use"]
