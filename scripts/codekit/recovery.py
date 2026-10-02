"""Pure resume gate for a stopped request.

The gate only projects already trusted recovery facts.  It never clears a
database stop flag, increases a budget, kills a process, or revives an old
attempt.  A caller must preserve history and perform the state-changing CAS in
the authoritative scheduler store after this decision.
"""
from __future__ import annotations

from typing import Any, Mapping

from . import protocols

RESUME_FACTS = (
    "request_stopped",
    "current_generation_matches",
    "permissions_current",
    "unknown_start_resolved",
    "budget_reconciled",
    "locks_match",
    "baseline_current",
    "acceptance_current",
    "resource_holds_reconciled",
    "external_scope_empty",
    "resume_authorized",
)


def resume_decision(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Return a conservative, deterministic resume decision."""
    if type(facts) is not dict:
        raise protocols.ProtocolError("E_SCHEMA_TYPE", field="/facts", phase="recovery",
                                      reason="facts_object_required")
    if set(facts) != set(RESUME_FACTS):
        raise protocols.ProtocolError("E_SCHEMA_FIELDS", field="/facts", phase="recovery",
                                      reason="fact_set_mismatch")
    for name in RESUME_FACTS:
        if type(facts[name]) is not bool:
            raise protocols.ProtocolError("E_SCHEMA_TYPE", field=f"/facts/{name}", phase="recovery",
                                          reason="boolean_required")
    reasons = [f"WAIT_{name.upper()}" for name in RESUME_FACTS if not facts[name]]
    if reasons:
        return {"decision": "BLOCK", "reasons": reasons}
    return {"decision": "RESUME_ALLOWED", "reasons": []}


__all__ = ["RESUME_FACTS", "resume_decision"]
