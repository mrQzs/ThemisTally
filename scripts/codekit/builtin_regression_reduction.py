"""Stable reduction helpers for regression and mutation evidence."""
from __future__ import annotations
from typing import Any, Mapping, Sequence
from .builtin_artifacts import ArtifactError

def reduce_regression_and_mutation(regression: Mapping[str, Any], mutation: Mapping[str, Any]) -> dict[str, Any]:
    """Combine evidence without best-of selection.

    A failed regression or mutation review blocks a bundle; unavailable evidence
    remains visible as ``BLOCKED``.  Only two PASS outcomes produce PASS.
    """
    for name, value in (("regression", regression), ("mutation", mutation)):
        if not isinstance(value, Mapping) or value.get("outcome") not in {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}:
            raise ArtifactError("E_REDUCTION", f"/{name}", "invalid outcome")
    outcomes = (regression["outcome"], mutation["outcome"])
    if "FAIL" in outcomes:
        outcome = "FAIL"
    elif "BLOCKED" in outcomes or "NOT_RUN" in outcomes:
        outcome = "BLOCKED"
    else:
        outcome = "PASS"
    return {"outcome": outcome, "regression": dict(regression), "mutation": dict(mutation), "policy": "all_required_evidence"}

__all__ = ["reduce_regression_and_mutation"]
