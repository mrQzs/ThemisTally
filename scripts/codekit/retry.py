"""07-T3B pure finite-retry and stop decision model.

The model consumes facts that a trusted scheduler has already observed.  It
does not allocate an attempt, generate a run id, inspect a process, write a
database, or invoke a provider.  A positive retry decision is only an
authorization to ask a separate allocator for a new operation.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Optional, Tuple

from .protocols import MAX_SAFE_INTEGER


RETRY_ALLOWED = "RETRY_ALLOWED"
WAIT = "WAIT"
STOP = "STOP"
NO_RETRY = "NO_RETRY"
EXHAUSTED = "EXHAUSTED"

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_STATES = frozenset({
    "CLAIMED", "ADMITTED", "HANDOFF_ACCEPTED", "STARTED", "RUNNING",
    "START_UNKNOWN", "REVIEW_PENDING", "ACCEPTED", "REJECTED", "FAILED",
    "CANCELLED", "CANCELLED_NOT_STARTED",
})
_ACTIVE = frozenset({
    "CLAIMED", "ADMITTED", "HANDOFF_ACCEPTED", "STARTED", "RUNNING",
    "START_UNKNOWN", "REVIEW_PENDING",
})
_NEW_PLAN_CODES = frozenset({"CONTRACT_INVALID", "BASELINE_INVALID", "SCOPE_INVALID"})


class RetryError(ValueError):
    """Invalid retry input; no scheduling fact has been changed."""

    def __init__(self, code: str, field: str, reason: str = "invalid_value") -> None:
        self.code = code
        self.field = field
        self.reason = reason
        super().__init__(f"{code} {field}: {reason}")


def _text(value: object, field: str) -> str:
    if type(value) is not str or not value or len(value) > 128 or _ID.fullmatch(value) is None:
        raise RetryError("E_SCHEMA_FIELDS", field, "nonempty_identifier_required")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise RetryError("E_SCHEMA_FIELDS", field, "unicode_scalar_required")
    return value


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int:
        raise RetryError("E_SCHEMA_TYPE", field, "exact_integer_required")
    if value < minimum or value > MAX_SAFE_INTEGER:
        raise RetryError("E_INTEGER_RANGE", field, "integer_out_of_range")
    return value


def _boolean(value: object, field: str, *, optional: bool = True) -> Optional[bool]:
    if value is None and optional:
        return None
    if type(value) is not bool:
        raise RetryError("E_SCHEMA_TYPE", field, "optional_boolean_required" if optional else "boolean_required")
    return value


@dataclass(frozen=True)
class RetryPolicy:
    """Mechanical retry limits registered by the main model.

    ``valid_until_seq`` is a scheduler observation sequence, not wall-clock
    time.  ``retryable_codes`` is an allow-list; a source's ``retryable=true``
    fact alone never grants a retry.
    """

    max_attempts_total: int
    min_backoff_seconds: int
    retryable_codes: Tuple[str, ...]
    valid_until_seq: Optional[int] = None
    max_request_dispatches: Optional[int] = None

    def __post_init__(self) -> None:
        _integer(self.max_attempts_total, "/policy/max_attempts_total", minimum=1)
        _integer(self.min_backoff_seconds, "/policy/min_backoff_seconds")
        if type(self.retryable_codes) not in (tuple, list):
            raise RetryError("E_SCHEMA_TYPE", "/policy/retryable_codes", "string_sequence_required")
        codes = tuple(_text(code, "/policy/retryable_codes") for code in self.retryable_codes)
        if len(set(codes)) != len(codes):
            raise RetryError("E_SCHEMA_FIELDS", "/policy/retryable_codes", "duplicate_code")
        object.__setattr__(self, "retryable_codes", codes)
        if self.valid_until_seq is not None:
            _integer(self.valid_until_seq, "/policy/valid_until_seq", minimum=1)
        if self.max_request_dispatches is not None:
            _integer(self.max_request_dispatches, "/policy/max_request_dispatches", minimum=1)


@dataclass(frozen=True)
class AttemptFact:
    """Immutable fact about one already allocated task attempt."""

    task: str
    request: str
    plan: int
    attempt: int
    operation: str
    state: str
    code: Optional[str]
    retryable: Optional[bool]
    side_effects: Optional[bool]
    guard: Optional[bool]
    sequence: int

    def __post_init__(self) -> None:
        for name in ("task", "request", "operation"):
            _text(getattr(self, name), f"/attempt/{name}")
        _integer(self.plan, "/attempt/plan", minimum=1)
        _integer(self.attempt, "/attempt/attempt", minimum=1)
        _integer(self.sequence, "/attempt/sequence", minimum=1)
        if type(self.state) is not str or self.state not in _STATES:
            raise RetryError("E_SCHEMA_FIELDS", "/attempt/state", "unknown_state")
        if self.code is not None:
            _text(self.code, "/attempt/code")
        _boolean(self.retryable, "/attempt/retryable")
        _boolean(self.side_effects, "/attempt/side_effects")
        _boolean(self.guard, "/attempt/guard")


@dataclass(frozen=True)
class RetryContext:
    """Current mutable facts rechecked immediately before a new claim."""

    request_open: Optional[bool] = None
    stop_requested: Optional[bool] = None
    budget_available: Optional[bool] = None
    resources_available: Optional[bool] = None
    recovery_clear: Optional[bool] = None
    upstream_accepted: Optional[bool] = None
    authorization: Optional[bool] = None
    total_attempts: int = 0
    sequence: Optional[int] = None
    now: Optional[int] = None
    total_dispatches: int = 0
    # ``authorization_valid`` is an explicit spelling accepted by callers
    # that use the claim/handoff vocabulary.  Exactly one value may be set.
    authorization_valid: Optional[bool] = None

    def __post_init__(self) -> None:
        for name in ("request_open", "stop_requested", "budget_available", "resources_available",
                     "recovery_clear", "upstream_accepted", "authorization", "authorization_valid"):
            _boolean(getattr(self, name), f"/context/{name}")
        if self.authorization is not None and self.authorization_valid is not None:
            raise RetryError("E_SCHEMA_FIELDS", "/context/authorization", "duplicate_authorization_fact")
        _integer(self.total_attempts, "/context/total_attempts")
        _integer(self.total_dispatches, "/context/total_dispatches")
        for name in ("sequence", "now"):
            value = getattr(self, name)
            if value is not None:
                _integer(value, f"/context/{name}", minimum=1)
        # Resolve both spellings during construction so an alias disagreement
        # cannot survive until a later decision call.
        self.current_sequence

    @property
    def authorization_fact(self) -> Optional[bool]:
        return self.authorization if self.authorization is not None else self.authorization_valid

    @property
    def current_sequence(self) -> Optional[int]:
        if self.sequence is not None and self.now is not None and self.sequence != self.now:
            raise RetryError("E_SCHEMA_FIELDS", "/context/sequence", "sequence_alias_conflict")
        return self.sequence if self.sequence is not None else self.now


@dataclass(frozen=True)
class RetryDecision:
    status: str
    reasons: Tuple[str, ...] = ()
    next_attempt: Optional[int] = None
    retry_after_seq: Optional[int] = None


def backoff(policy: RetryPolicy, attempt: int) -> int:
    """Return exact integer exponential backoff, capped at MAX_SAFE_INTEGER."""
    if type(policy) is not RetryPolicy:
        raise RetryError("E_SCHEMA_TYPE", "/policy", "retry_policy_required")
    _integer(attempt, "/attempt", minimum=1)
    if policy.min_backoff_seconds == 0:
        return 0
    shift = attempt - 1
    # Avoid constructing an enormous Python integer for hostile attempt values.
    if shift > MAX_SAFE_INTEGER.bit_length() or policy.min_backoff_seconds.bit_length() + shift > MAX_SAFE_INTEGER.bit_length():
        return MAX_SAFE_INTEGER
    value = policy.min_backoff_seconds << shift
    return min(value, MAX_SAFE_INTEGER)


def _safe_next_attempt(total: int) -> int:
    """Keep a diagnostic attempt number inside the public integer range."""
    return MAX_SAFE_INTEGER if total >= MAX_SAFE_INTEGER else total + 1


def _safe_due(sequence: int, delay: int) -> tuple[int, bool]:
    """Return a bounded retry sequence and whether the true value overflowed."""
    if sequence > MAX_SAFE_INTEGER - delay:
        return MAX_SAFE_INTEGER, True
    return sequence + delay, False


def cumulative_attempts(facts: Iterable[AttemptFact], *, request: str, task: str) -> int:
    """Count attempts for one stable request/task identity across all plans."""
    _text(request, "/request")
    _text(task, "/task")
    unique: set[str] = set()
    total = 0
    for index, fact in enumerate(facts):
        if type(fact) is not AttemptFact:
            raise RetryError("E_SCHEMA_TYPE", f"/facts/{index}", "attempt_fact_required")
        if fact.request == request and fact.task == task and fact.operation not in unique:
            unique.add(fact.operation)
            total += 1
    return total


def decide(policy: RetryPolicy, fact: AttemptFact, context: RetryContext,
           history: Iterable[AttemptFact] = ()) -> RetryDecision:
    """Evaluate a retry without allocating or mutating any external state.

    Reasons are emitted in this fixed order: stop/recovery, terminal attempt
    state, side effects/unknowns, policy and count, then current guards and
    backoff.  The status is the strongest class among those reasons, so callers
    cannot turn an unknown gate into a retry by inspecting only one field.
    """
    if type(policy) is not RetryPolicy:
        raise RetryError("E_SCHEMA_TYPE", "/policy", "retry_policy_required")
    if type(fact) is not AttemptFact:
        raise RetryError("E_SCHEMA_TYPE", "/attempt", "attempt_fact_required")
    if type(context) is not RetryContext:
        raise RetryError("E_SCHEMA_TYPE", "/context", "retry_context_required")

    reasons: list[str] = []
    stop_reasons: list[str] = []
    no_retry_reasons: list[str] = []
    wait_reasons: list[str] = []
    exhausted = False

    if context.stop_requested is True or context.request_open is False:
        stop_reasons.append("request_stopped")
    elif context.stop_requested is None:
        wait_reasons.append("stop_state_unknown")
    elif context.request_open is None:
        wait_reasons.append("request_open_unknown")

    if context.recovery_clear is True:
        pass
    elif context.recovery_clear is False:
        stop_reasons.append("recovery_required")
    else:
        stop_reasons.append("recovery_state_unknown")

    if fact.state == "START_UNKNOWN":
        stop_reasons.append("start_unknown")
    elif fact.state == "ACCEPTED":
        no_retry_reasons.append("already_accepted")
    elif fact.state in _ACTIVE:
        no_retry_reasons.append("attempt_active")
    elif fact.state not in ("FAILED", "REJECTED", "CANCELLED", "CANCELLED_NOT_STARTED"):
        no_retry_reasons.append("state_not_retryable")

    if fact.side_effects is True:
        no_retry_reasons.append("side_effects_present")
    elif fact.side_effects is None:
        stop_reasons.append("side_effects_unknown")

    if fact.guard is True:
        pass
    elif fact.guard is False:
        no_retry_reasons.append("guard_invalid")
    else:
        stop_reasons.append("guard_unknown")

    if fact.retryable is True:
        pass
    elif fact.retryable is False:
        no_retry_reasons.append("attempt_nonretryable")
    else:
        wait_reasons.append("retryability_unknown")

    if fact.code is None:
        no_retry_reasons.append("failure_code_missing")
    elif fact.code not in policy.retryable_codes:
        no_retry_reasons.append("code_not_allowed")
    if fact.code in _NEW_PLAN_CODES:
        no_retry_reasons.append("new_plan_required")

    current = context.current_sequence
    if policy.valid_until_seq is not None:
        if current is None:
            wait_reasons.append("policy_sequence_unknown")
        elif current > policy.valid_until_seq:
            no_retry_reasons.append("policy_expired")

    # The triggering fact is itself an allocated attempt.  A stale or omitted
    # context counter must not make the next retry reuse attempt number 1.
    history_items = tuple(history)
    observed = cumulative_attempts(history_items, request=fact.request, task=fact.task)
    if not any(item.request == fact.request and item.task == fact.task
               and item.operation == fact.operation for item in history_items):
        observed += 1
    if observed and observed > context.total_attempts:
        wait_reasons.append("attempt_count_stale")
    total = max(context.total_attempts, observed)
    if total >= policy.max_attempts_total:
        exhausted = True
        reasons.append("attempt_limit")
    if (policy.max_request_dispatches is not None and
            context.total_dispatches >= policy.max_request_dispatches):
        exhausted = True
        reasons.append("request_dispatch_limit")

    for value, unknown, false in (
        (context.budget_available, "budget_unknown", "budget_unavailable"),
        (context.resources_available, "resources_unknown", "resources_unavailable"),
        (context.upstream_accepted, "upstream_unknown", "upstream_not_accepted"),
    ):
        if value is None:
            wait_reasons.append(unknown)
        elif value is not True:
            wait_reasons.append(false)

    authorization = context.authorization_fact
    if authorization is None:
        wait_reasons.append("authorization_unknown")
    elif authorization is not True:
        no_retry_reasons.append("authorization_denied")

    due, due_saturated = _safe_due(fact.sequence, backoff(policy, fact.attempt))
    if current is None:
        wait_reasons.append("sequence_unknown")
    elif due_saturated:
        # There is no representable observation sequence beyond the public
        # bound.  Keep the decision waiting instead of treating a saturated
        # value as already due at MAX_SAFE_INTEGER.
        wait_reasons.append("sequence_limit_reached")
    else:
        if current < due:
            wait_reasons.append("backoff_active")

    reasons.extend(stop_reasons)
    reasons.extend(no_retry_reasons)
    reasons.extend(wait_reasons)
    # Stop and terminal facts take precedence over count, while an exhausted
    # otherwise-valid attempt is reported as EXHAUSTED.  This ordering is fixed.
    if stop_reasons:
        return RetryDecision(STOP, tuple(reasons), _safe_next_attempt(total), None)
    if no_retry_reasons:
        return RetryDecision(NO_RETRY, tuple(reasons), _safe_next_attempt(total), None)
    if exhausted:
        return RetryDecision(EXHAUSTED, tuple(reasons), _safe_next_attempt(total), None)
    if wait_reasons:
        retry_after = None
        if current is not None:
            retry_after = due
        return RetryDecision(WAIT, tuple(reasons), _safe_next_attempt(total), retry_after)
    return RetryDecision(RETRY_ALLOWED, ("retry_authorized",), _safe_next_attempt(total), None)


__all__ = [
    "AttemptFact", "EXHAUSTED", "NO_RETRY", "RETRY_ALLOWED", "RetryContext",
    "RetryDecision", "RetryError", "RetryPolicy", "STOP", "WAIT", "backoff",
    "cumulative_attempts", "decide",
]
