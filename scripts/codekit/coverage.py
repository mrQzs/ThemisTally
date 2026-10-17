"""Trusted-fact content coverage checks for a fixed baseline binding.

The validator consumes facts obtained by a separate read-only Git/evidence
probe.  It never runs Git, creates a commit, infers authorization, or treats
an unknown fact as false.  The three coverage modes are deliberately
conservative: exact trees require identity, pinned sets require an exact
path/blob inventory, and revalidated integration requires a fresh accepted
candidate plus current checks.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from . import protocols
from .baseline_binding import BaselineBinding, COVERAGE_MODES, validate_baseline_binding

MAX_ENTRIES = 4096


@dataclass(frozen=True)
class CoverageDecision:
    decision: str
    reasons: tuple[str, ...] = ()
    coverage_mode: str | None = None


def evaluate_coverage(
    binding: BaselineBinding | Mapping[str, Any],
    *,
    candidate_tree_oid: str | None,
    ancestor: bool | None,
    authorization_verified: bool | None,
    candidate_entries: Sequence[Mapping[str, Any]] = (),
    pinned_artifacts: Sequence[Mapping[str, Any]] = (),
    integration_accepted: bool | None = None,
    checks_current: bool | None = None,
) -> CoverageDecision:
    """Evaluate content coverage using only fixed, caller-supplied facts."""
    validated = binding if isinstance(binding, BaselineBinding) else validate_baseline_binding(binding)
    mode = validated.coverage_mode
    _bool_or_none(ancestor, "/ancestor")
    _bool_or_none(authorization_verified, "/authorization_verified")
    _bool_or_none(integration_accepted, "/integration_accepted")
    _bool_or_none(checks_current, "/checks_current")
    candidate_oid = _oid(candidate_tree_oid, validated.object_format, "/candidate_tree_oid", required=mode != "exact_tree")
    reasons: list[str] = []

    if authorization_verified is not True:
        reasons.append("AUTHORIZATION_REJECTED" if authorization_verified is False else "AUTHORIZATION_UNKNOWN")
    if ancestor is not True:
        reasons.append("ANCESTOR_REJECTED" if ancestor is False else "ANCESTOR_UNKNOWN")

    if mode == "exact_tree":
        if candidate_oid is None or candidate_oid != validated.tree_sha:
            reasons.append("EXACT_TREE_MISMATCH")
    elif mode == "pinned_artifact_set":
        entries = _entries(candidate_entries, validated.object_format, "/candidate_entries", required=True)
        pins = _entries(pinned_artifacts, validated.object_format, "/pinned_artifacts", required=True)
        if entries != pins:
            reasons.append("PINNED_ARTIFACT_SET_MISMATCH")
    elif mode == "revalidated_integration":
        if candidate_oid is None:
            reasons.append("INTEGRATION_CANDIDATE_UNKNOWN")
        if integration_accepted is not True:
            reasons.append("INTEGRATION_ACCEPTANCE_REJECTED" if integration_accepted is False else "INTEGRATION_ACCEPTANCE_UNKNOWN")
        if checks_current is not True:
            reasons.append("INTEGRATION_CHECKS_STALE" if checks_current is False else "INTEGRATION_CHECKS_UNKNOWN")
    else:  # defensive: BaselineBinding already validates this
        raise protocols.ProtocolError("E_SCHEMA_FIELDS", field="/coverage_mode", phase="coverage", reason="coverage_mode_unsupported")

    if not reasons:
        return CoverageDecision("COVERAGE_VERIFIED", (), mode)
    # Stable, duplicate-free diagnostics make the result safe for persistence.
    return CoverageDecision("BLOCK", tuple(dict.fromkeys(reasons)), mode)


def validate_tree_entries(entries: Sequence[Mapping[str, Any]], *, object_format: str) -> tuple[Mapping[str, str], ...]:
    """Validate and canonicalize a fixed recursive tree inventory."""
    return _entries(entries, object_format, "/entries", required=True)


def _entries(value: Any, object_format: str, field: str, *, required: bool) -> tuple[Mapping[str, str], ...]:
    if type(value) not in (tuple, list) or (required and not value) or len(value) > MAX_ENTRIES:
        _error("E_SCHEMA_TYPE", field, "bounded_nonempty_array_required")
    result: list[Mapping[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if type(item) is not dict:
            _error("E_SCHEMA_TYPE", f"{field}/{index}", "entry_object_required")
        if set(item) != {"path", "oid", "sha256", "mode"}:
            _error("E_SCHEMA_FIELDS", f"{field}/{index}", "closed_entry_fields")
        path = protocols.validate_business_path(item.get("path"), field=f"{field}/{index}/path")
        oid = protocols.validate_git_oid(item.get("oid"), object_format, field=f"{field}/{index}/oid")
        protocols.validate_sha256(item.get("sha256"), field=f"{field}/{index}/sha256")
        mode = item.get("mode")
        if type(mode) is not str or mode not in {"100644", "100755", "120000", "160000"}:
            _error("E_SCHEMA_FIELDS", f"{field}/{index}/mode", "tree_mode_unsupported")
        if path in seen:
            _error("E_SCHEMA_FIELDS", f"{field}/{index}/path", "duplicate_tree_path")
        seen.add(path)
        result.append({"path": path, "oid": oid, "sha256": item["sha256"], "mode": mode})
    return tuple(sorted((MappingProxyType(copy.deepcopy(dict(item))) for item in result), key=lambda item: item["path"]))


def _oid(value: Any, object_format: str, field: str, *, required: bool) -> str | None:
    if value is None and not required:
        return None
    return protocols.validate_git_oid(value, object_format, field=field)


def _bool_or_none(value: Any, field: str) -> None:
    if value is not None and type(value) is not bool:
        _error("E_SCHEMA_TYPE", field, "boolean_or_null_required")


def _error(code: str, field: str, reason: str) -> None:
    raise protocols.ProtocolError(code, field=field, phase="coverage", reason=reason)


__all__ = ["CoverageDecision", "evaluate_coverage", "validate_tree_entries"]
