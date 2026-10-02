"""Pure readiness projection for synthetic, already-trusted observations.

This module does not discover, authenticate, or refresh any fact.  Callers must
obtain the facts from the appropriate protocol and authorization layers before
calling :func:`readiness`.
"""
from __future__ import annotations

from typing import Any, Mapping

from . import protocols

READINESS_FACTS = (
    "inputs_accepted",
    "baseline_present",
    "baseline_authorized",
    "contract_current",
    "approval_current",
    "locks_match",
    "capabilities_ok",
    "authorization_ok",
    "budget_ok",
    "conflicts_clear",
    "request_open",
)


def readiness(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Project trusted boolean facts into refinement/execution readiness.

    Refinement requires accepted inputs, a present baseline, and authorization
    to use that baseline.  Execution additionally requires every remaining
    guard.  Reasons preserve the fixed fact order and are observations, not
    permissions or recovery actions.
    """
    if type(facts) is not dict:
        raise protocols.ProtocolError("E_SCHEMA_TYPE", field="/facts", phase="readiness",
                                      reason="facts_object_required")
    if set(facts) != set(READINESS_FACTS):
        raise protocols.ProtocolError("E_SCHEMA_FIELDS", field="/facts", phase="readiness",
                                      reason="fact_set_mismatch")
    for name in READINESS_FACTS:
        if type(facts[name]) is not bool:
            raise protocols.ProtocolError("E_SCHEMA_TYPE", field=f"/facts/{name}", phase="readiness",
                                          reason="boolean_required")
    return {
        "can_refine": all(facts[name] for name in READINESS_FACTS[:3]),
        "can_execute": all(facts[name] for name in READINESS_FACTS),
        "reasons": [f"WAIT_{name.upper()}" for name in READINESS_FACTS if not facts[name]],
    }


__all__ = ["READINESS_FACTS", "readiness"]
