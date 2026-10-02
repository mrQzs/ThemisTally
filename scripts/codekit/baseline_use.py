"""Explicit baseline-use authorization and multi-upstream merge gate."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

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
    if not isinstance(binding, BaselineBinding):
        binding = validate_baseline_binding(binding)
    reasons: list[str] = []
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
    for acceptance_id in required:
        item = accepted.get(acceptance_id)
        if item is None:
            reasons.append("WAIT_UPSTREAM_ACCEPTANCE")
        elif acceptance_id in revoked:
            reasons.append("ACCEPTANCE_REVOKED")
        elif item.request_id != expected_request_id or item.guard_version != expected_guard_version:
            reasons.append("UPSTREAM_GUARD_MISMATCH")
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
