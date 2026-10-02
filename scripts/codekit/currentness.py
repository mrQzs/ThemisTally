"""Deterministic composition of fixed Git/currentness evidence.

The individual Git, ancestry, coverage, and authorization layers deliberately
do not grant one another's facts.  This module only combines their already
verified observations; it never runs Git, mutates a repository, or issues
authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .baseline_binding import BaselineBinding, validate_baseline_binding
from .coverage import CoverageDecision
from .git_ancestor import AncestorObservation
from .git_probe import GitProbeObservation


@dataclass(frozen=True)
class BaselineCurrentnessDecision:
    decision: str
    reasons: tuple[str, ...]
    facts: Mapping[str, Any]


def evaluate_baseline_currentness(
    binding: BaselineBinding | Mapping[str, Any],
    git_observation: GitProbeObservation,
    ancestor_observation: AncestorObservation,
    coverage_decision: CoverageDecision,
    *,
    authorization_current: bool | None,
    guard_match: bool | None,
) -> BaselineCurrentnessDecision:
    """Combine all gates in fixed order, preserving unknown versus rejected."""
    if not isinstance(binding, BaselineBinding):
        binding = validate_baseline_binding(binding)
    if not isinstance(git_observation, GitProbeObservation):
        raise TypeError("git_observation must be GitProbeObservation")
    if not isinstance(ancestor_observation, AncestorObservation):
        raise TypeError("ancestor_observation must be AncestorObservation")
    if not isinstance(coverage_decision, CoverageDecision):
        raise TypeError("coverage_decision must be CoverageDecision")
    if authorization_current is not None and type(authorization_current) is not bool:
        raise TypeError("authorization_current must be bool or None")
    if guard_match is not None and type(guard_match) is not bool:
        raise TypeError("guard_match must be bool or None")

    reasons: list[str] = []
    if git_observation.verified is not True:
        reasons.append("REJECT_REAL_COMMIT" if git_observation.blocked_reasons else "WAIT_REAL_COMMIT")
    if ancestor_observation.decision != "ANCESTOR":
        reasons.append("REJECT_ANCESTRY" if ancestor_observation.decision == "NOT_ANCESTOR" else "WAIT_ANCESTRY")
    if coverage_decision.decision != "COVERAGE_VERIFIED":
        reasons.append("REJECT_COVERAGE" if coverage_decision.reasons else "WAIT_COVERAGE")
    if authorization_current is not True:
        reasons.append("REJECT_BASELINE_AUTHORIZATION" if authorization_current is False else "WAIT_BASELINE_AUTHORIZATION")
    if guard_match is not True:
        reasons.append("REJECT_CURRENTNESS" if guard_match is False else "WAIT_CURRENTNESS")

    facts = MappingProxyType({
        "repo_id": binding.repo_id,
        "environment_id": binding.environment_id,
        "base_sha": binding.base_sha,
        "tree_sha": binding.tree_sha,
        "git_verified": git_observation.verified,
        "ancestor": ancestor_observation.decision,
        "coverage": coverage_decision.decision,
        "authorization_current": authorization_current,
        "guard_match": guard_match,
    })
    return BaselineCurrentnessDecision(
        "BASELINE_CURRENT_VERIFIED" if not reasons else "BLOCK",
        tuple(reasons),
        facts,
    )


__all__ = ["BaselineCurrentnessDecision", "evaluate_baseline_currentness"]
