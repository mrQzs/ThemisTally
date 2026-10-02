"""Conservative resume/CAS decision for recovery evidence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .protocols import MAX_SAFE_INTEGER


class RecoveryError(ValueError):
    def __init__(self, code: str, message: str = "recovery rejected") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class RecoveryDecision:
    decision: str
    reasons: tuple[str, ...] = ()


BOOL_FACTS = ("history_preserved", "budget_not_increased", "resource_holds_reconciled", "external_scope_empty", "resume_authorized")
HIGH_WATERS = ("backup_high_water", "journal_high_water", "resource_high_water", "auth_high_water")


def resume_recovery_decision(facts: Mapping[str, Any], *, expected_generation: int) -> RecoveryDecision:
    """Require matching generation, non-regressing high waters, and all gates."""
    if type(facts) is not dict or type(expected_generation) is not int or expected_generation < 1:
        raise RecoveryError("E_RECOVERY_SCHEMA")
    required = {"recorded_generation", *BOOL_FACTS, *HIGH_WATERS}
    if set(facts) != required:
        raise RecoveryError("E_RECOVERY_FIELDS")
    if (type(facts["recorded_generation"]) is not int
            or facts["recorded_generation"] < 1
            or facts["recorded_generation"] > MAX_SAFE_INTEGER):
        raise RecoveryError("E_RECOVERY_SCHEMA")
    reasons: list[str] = []
    if facts["recorded_generation"] != expected_generation:
        reasons.append("WAIT_GENERATION_RECHECK")
    for name in HIGH_WATERS:
        value = facts[name]
        if type(value) is not int or value < 0 or value > MAX_SAFE_INTEGER:
            raise RecoveryError("E_RECOVERY_SCHEMA")
        if value < facts["recorded_generation"] - 1:
            reasons.append("WAIT_" + name.upper())
    for name in BOOL_FACTS:
        value = facts[name]
        if type(value) is not bool:
            raise RecoveryError("E_RECOVERY_SCHEMA")
        if not value:
            reasons.append("WAIT_" + name.upper())
    return RecoveryDecision("RESUME_ALLOWED" if not reasons else "BLOCK", tuple(dict.fromkeys(reasons)))


__all__ = ["BOOL_FACTS", "HIGH_WATERS", "RecoveryDecision", "RecoveryError", "resume_recovery_decision"]
