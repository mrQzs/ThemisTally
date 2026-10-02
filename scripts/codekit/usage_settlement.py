"""Offline, auditable usage settlement facts for Code-Kit 07-S3.2.

The existing :mod:`codekit.budget` reducer is the request admission model.
This module is the deliberately small economic facts boundary used by offline
fixtures.  It keeps every observation and derives one current value per
``operation/dimension/economic-call`` series.  It does not call providers,
read credentials, infer exchange rates, or release budget for a refund unless
the policy explicitly opts into that behaviour.

The model is immutable from a caller's point of view: accepted facts and audit
events are append-only, while snapshots are rebuilt from those facts.  This
is useful for deterministic tests and makes the production boundary explicit;
durable SQLite/OS/provider integration belongs to later S3/S4 contracts.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from .protocols import MAX_SAFE_INTEGER


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_DIMENSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_CURRENCY = re.compile(r"[A-Z][A-Z0-9]{2,11}\Z")
_KINDS = frozenset(("cumulative", "final", "unknown", "refund"))
_REFUND_POLICIES = frozenset(("record_only", "release"))
_MAX_CANONICAL_DEPTH = 64


class SettlementError(ValueError):
    """A stable rejection code for an economic fact or settlement action."""

    def __init__(self, code: str, message: str = "settlement fact rejected") -> None:
        self.code = code
        super().__init__(message)


def _text(value: Any, name: str, *, pattern: re.Pattern[str] = _ID) -> str:
    if type(value) is not str or not value or len(value) > 128 or pattern.fullmatch(value) is None:
        raise SettlementError("E_SETTLEMENT_VALUE", name)
    return value


def _amount(value: Any, name: str = "amount") -> int:
    # ``bool`` is an ``int`` subclass; exact type checking is intentional.
    if type(value) is not int or value < 0 or value > MAX_SAFE_INTEGER:
        raise SettlementError("E_SETTLEMENT_AMOUNT", name)
    return value


def _revision(value: Any) -> int:
    if type(value) is not int or value < 1 or value > MAX_SAFE_INTEGER:
        raise SettlementError("E_SETTLEMENT_REVISION", "revision")
    return value


def _boolean(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise SettlementError("E_SETTLEMENT_VALUE", name)
    return value


def _currency(value: Any) -> str:
    if type(value) is not str or _CURRENCY.fullmatch(value) is None:
        raise SettlementError("E_SETTLEMENT_CURRENCY", "currency")
    return value


def _mapping(values: Mapping[str, int], name: str, *, nonempty: bool = False) -> Mapping[str, int]:
    if not isinstance(values, Mapping) or (nonempty and not values) or len(values) > 256:
        raise SettlementError("E_SETTLEMENT_VALUE", name)
    result: dict[str, int] = {}
    for key, value in values.items():
        result[_text(key, name, pattern=_DIMENSION)] = _amount(value, name)
    return MappingProxyType(result)


def _canonical_value(value: Any, path: str = "$", *, _stack: set[int] | None = None,
                     _depth: int = 0) -> Any:
    """Copy strict JSON values before hashing settlement history.

    Audit fingerprints must fail as a typed settlement error for cycles,
    surrogate text, non-string object keys, unsafe integers, non-finite floats,
    and unsupported Python objects.  ``json.dumps`` alone would otherwise leak
    implementation exceptions or silently coerce values such as ``IntEnum``.
    """
    if _depth > _MAX_CANONICAL_DEPTH:
        raise SettlementError("E_SETTLEMENT_CANONICAL", path)
    if value is None or type(value) is bool:
        return value
    if type(value) is str:
        if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
            raise SettlementError("E_SETTLEMENT_CANONICAL", path)
        return value
    if type(value) is int:
        if value < -MAX_SAFE_INTEGER or value > MAX_SAFE_INTEGER:
            raise SettlementError("E_SETTLEMENT_CANONICAL", path)
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise SettlementError("E_SETTLEMENT_CANONICAL", path)
        return value
    if _stack is None:
        _stack = set()
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in _stack:
            raise SettlementError("E_SETTLEMENT_CANONICAL", path)
        _stack.add(identity)
        try:
            result: dict[str, Any] = {}
            for key, item in value.items():
                if (type(key) is not str
                        or any(0xD800 <= ord(ch) <= 0xDFFF for ch in key)):
                    raise SettlementError("E_SETTLEMENT_CANONICAL", path)
                result[key] = _canonical_value(item, path + "." + key,
                                                _stack=_stack, _depth=_depth + 1)
            return result
        finally:
            _stack.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in _stack:
            raise SettlementError("E_SETTLEMENT_CANONICAL", path)
        _stack.add(identity)
        try:
            return [_canonical_value(item, f"{path}[{index}]", _stack=_stack,
                                     _depth=_depth + 1)
                    for index, item in enumerate(value)]
        finally:
            _stack.remove(identity)
    raise SettlementError("E_SETTLEMENT_CANONICAL", path)


def _canonical(value: Any) -> str:
    try:
        normalized = _canonical_value(value)
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False)
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise SettlementError("E_SETTLEMENT_CANONICAL", "canonical JSON required") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SettlementPolicy:
    """Caps and explicit refund/unknown handling for an offline ledger."""

    caps: Mapping[str, int]
    policy_ref: str = "settlement-v1"
    unknown_policy: str = "stop"
    refund_policy: str = "record_only"

    def __post_init__(self) -> None:
        object.__setattr__(self, "caps", _mapping(self.caps, "caps", nonempty=True))
        for dimension in self.caps:
            if dimension.startswith("charge:"):
                _currency(dimension.split(":", 1)[1])
        object.__setattr__(self, "policy_ref", _text(self.policy_ref, "policy_ref"))
        if type(self.unknown_policy) is not str or self.unknown_policy != "stop":
            raise SettlementError("E_SETTLEMENT_POLICY", "only stop unknown_policy is supported")
        if type(self.refund_policy) is not str or self.refund_policy not in _REFUND_POLICIES:
            raise SettlementError("E_SETTLEMENT_POLICY", "unsupported refund_policy")


@dataclass(frozen=True)
class SettlementOperation:
    operation_id: str
    request_id: str
    task_id: str
    reservation: Mapping[str, int]
    state: str = "reserved"
    finished: bool = False

    def __post_init__(self) -> None:
        for name in ("operation_id", "request_id", "task_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "reservation", _mapping(self.reservation, "reservation", nonempty=True))
        if type(self.state) is not str or self.state not in {"reserved", "provisional", "reconciled", "unknown", "cancelled_not_started"}:
            raise SettlementError("E_SETTLEMENT_STATE", "state")
        _boolean(self.finished, "finished")


@dataclass(frozen=True)
class SettlementFact:
    """One provider/economic observation retained in the append-only history."""

    fact_id: str
    operation_id: str
    dimension: str
    call_key: str
    revision: int
    kind: str
    amount: int | None
    currency: str | None = None
    correction: bool = False
    supersedes: str | None = None
    refund_for: str | None = None
    unknown_reason: str | None = None
    evidence_ref: str | None = None

    def __post_init__(self) -> None:
        for name in ("fact_id", "operation_id", "call_key"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "dimension", _text(self.dimension, "dimension", pattern=_DIMENSION))
        _revision(self.revision)
        if type(self.kind) is not str or self.kind not in _KINDS:
            raise SettlementError("E_SETTLEMENT_KIND", "unsupported settlement kind")
        _boolean(self.correction, "correction")
        if self.amount is not None:
            _amount(self.amount)
        if self.kind == "unknown":
            if self.amount is not None or not self.unknown_reason:
                raise SettlementError("E_SETTLEMENT_UNKNOWN", "unknown requires a reason and no amount")
            object.__setattr__(self, "unknown_reason", _text(self.unknown_reason, "unknown_reason"))
        elif self.kind == "refund":
            if self.amount is None:
                raise SettlementError("E_SETTLEMENT_REFUND", "refund requires a non-negative amount")
            if self.correction or self.supersedes is not None or not self.refund_for:
                raise SettlementError("E_SETTLEMENT_REFUND", "refund requires an independent target")
            object.__setattr__(self, "refund_for", _text(self.refund_for, "refund_for"))
        else:
            if self.amount is None or self.unknown_reason is not None:
                raise SettlementError("E_SETTLEMENT_VALUE", "known fact requires amount and no unknown reason")
            if self.kind == "final" and self.revision < 1:
                raise SettlementError("E_SETTLEMENT_REVISION", "final revision required")
        if self.kind == "final" and self.correction is False:
            # A final observation is valid without correction; this branch is
            # kept explicit to make the relationship obvious in audit code.
            pass
        if self.supersedes is not None:
            object.__setattr__(self, "supersedes", _text(self.supersedes, "supersedes"))
        if self.evidence_ref is not None:
            object.__setattr__(self, "evidence_ref", _text(self.evidence_ref, "evidence_ref"))
        if self.dimension.startswith("charge:"):
            expected = self.dimension.split(":", 1)[1]
            # Currency dimensions are an accounting boundary; accepting an
            # arbitrary suffix would make ``charge:USD/evil`` a valid unit
            # while bypassing the currency allowlist.
            _currency(expected)
            if type(self.currency) is not str:
                raise SettlementError("E_SETTLEMENT_CURRENCY", "charge dimension requires currency")
            _currency(self.currency)
            if self.currency != expected:
                raise SettlementError("E_SETTLEMENT_CURRENCY", "charge dimension currency mismatch")
        elif self.currency is not None:
            raise SettlementError("E_SETTLEMENT_CURRENCY", "currency is only valid on charge dimensions")
        if self.kind != "refund" and self.refund_for is not None:
            raise SettlementError("E_SETTLEMENT_REFUND", "refund_for only belongs to refund facts")
        if self.kind == "unknown" and self.correction:
            raise SettlementError("E_SETTLEMENT_UNKNOWN", "unknown cannot be a correction")
        if self.correction and self.supersedes is None:
            raise SettlementError("E_SETTLEMENT_CORRECTION", "correction requires supersedes")
        if self.supersedes is not None and not self.correction:
            raise SettlementError("E_SETTLEMENT_CORRECTION", "supersedes requires correction")

    def semantic_payload(self) -> dict[str, Any]:
        """Payload used to decide whether same-revision evidence is a mirror."""
        return {
            "operation_id": self.operation_id,
            "dimension": self.dimension,
            "call_key": self.call_key,
            "revision": self.revision,
            "kind": self.kind,
            "amount": self.amount,
            "currency": self.currency,
            "correction": self.correction,
            "supersedes": self.supersedes,
            "refund_for": self.refund_for,
            "unknown_reason": self.unknown_reason,
        }

    def as_dict(self) -> dict[str, Any]:
        result = {"fact_id": self.fact_id, **self.semantic_payload()}
        if self.evidence_ref is not None:
            result["evidence_ref"] = self.evidence_ref
        return result

    @property
    def semantic_hash(self) -> str:
        return _hash(self.semantic_payload())

    @property
    def fingerprint(self) -> str:
        return _hash(self.as_dict())


@dataclass(frozen=True)
class SettlementDecision:
    status: str
    replayed: bool = False
    historical: bool = False
    changed_dimensions: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class SettlementDimension:
    dimension: str
    cap: int
    known: int
    held: int
    exposure: int
    gross_known: int
    refunds: int
    net_known: int
    refund_excess: int
    unknown_operations: tuple[str, ...]
    over_limit: bool
    coverage: str
    enforcement: str


@dataclass(frozen=True)
class SettlementSnapshot:
    sequence: int
    policy_ref: str
    dimensions: Mapping[str, SettlementDimension]
    stop_reasons: tuple[str, ...]
    coverage: str


class UsageSettlement:
    """Pure offline settlement reducer with append-only audit facts."""

    def __init__(self, policy: SettlementPolicy | Mapping[str, int]) -> None:
        if isinstance(policy, Mapping):
            policy = SettlementPolicy(policy)
        if type(policy) is not SettlementPolicy:
            raise SettlementError("E_SETTLEMENT_POLICY", "policy required")
        self.policy = policy
        self._operations: dict[str, SettlementOperation] = {}
        self._facts: list[SettlementFact] = []
        self._facts_by_id: dict[str, SettlementFact] = {}
        self._stop_reasons: list[str] = []
        self._sequence = 0
        self._request_id: str | None = None

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def operations(self) -> tuple[SettlementOperation, ...]:
        return tuple(self._operations.values())

    @property
    def facts(self) -> tuple[SettlementFact, ...]:
        return tuple(self._facts)

    @property
    def stop_reasons(self) -> tuple[str, ...]:
        return tuple(self._stop_reasons)

    def _reason(self, reason: str) -> None:
        if reason not in self._stop_reasons:
            self._stop_reasons.append(reason)

    def _event(self, event_type: str, payload: Mapping[str, Any]) -> None:
        self._sequence += 1
        # Events are represented by immutable facts in the audit export.  The
        # sequence is advanced even for mirrors so arrival order is auditable.
        del event_type, payload

    def _current_rows(self, operation_id: str, dimension: str,
                      call_key: str | None = None) -> list[SettlementFact]:
        rows = [fact for fact in self._facts
                if fact.operation_id == operation_id and fact.dimension == dimension
                and fact.kind != "refund"
                and (call_key is None or fact.call_key == call_key)]
        by_revision: dict[int, SettlementFact] = {}
        for fact in rows:
            by_revision.setdefault(fact.revision, fact)
        return [by_revision[key] for key in sorted(by_revision)]

    def _series_for(self, operation_id: str, dimension: str) -> list[SettlementFact]:
        return self._current_rows(operation_id, dimension)

    def _current(self, operation_id: str, dimension: str) -> tuple[SettlementFact | None, int]:
        rows = self._series_for(operation_id, dimension)
        if not rows:
            return None, 0
        current = rows[-1]
        if current.kind != "unknown":
            return current, current.amount or 0
        # A late lower revision must not rewrite the known lower bound that was
        # in force when the unknown fact arrived.
        index = next(i for i, fact in enumerate(self._facts)
                     if fact.fact_id == current.fact_id)
        prior = [fact for fact in self._facts[:index]
                 if fact.operation_id == operation_id and fact.dimension == dimension
                 and fact.kind != "unknown" and fact.kind != "refund"]
        if not prior:
            return current, 0
        by_revision: dict[int, SettlementFact] = {}
        for fact in prior:
            by_revision.setdefault(fact.revision, fact)
        fact = by_revision[max(by_revision)]
        return current, fact.amount or 0

    def _refund_total(self, dimension: str) -> int:
        return sum(fact.amount or 0 for fact in self._facts
                   if fact.kind == "refund" and fact.dimension == dimension)

    def _known_for_budget(self, gross: int, refunds: int) -> int:
        if self.policy.refund_policy == "release":
            return max(gross - refunds, 0)
        return gross

    def _project_dimension(self, dimension: str) -> SettlementDimension:
        cap = self.policy.caps[dimension]
        gross = refunds = 0
        held = 0
        unknown: list[str] = []
        provisional = False
        for operation in self._operations.values():
            current, subtotal = self._current(operation.operation_id, dimension)
            operation_known = subtotal
            if current is not None and current.kind == "unknown":
                unknown.append(operation.operation_id)
            closed = current is not None and current.kind == "final"
            if operation.finished and not closed and operation.operation_id not in unknown:
                unknown.append(operation.operation_id)
            if current is None and not operation.finished:
                provisional = True
            if current is not None and current.kind != "final" and current.kind != "unknown":
                provisional = True
            gross += operation_known
            if not closed and operation.state != "cancelled_not_started":
                held += max(operation.reservation[dimension] - operation_known, 0)
        refunds = self._refund_total(dimension)
        net = gross - refunds
        known = self._known_for_budget(gross, refunds)
        exposure = known + held
        over_limit = exposure > cap
        if unknown:
            coverage = "unknown"
        elif provisional:
            coverage = "partial"
        else:
            coverage = "complete"
        enforcement = "stop" if over_limit or unknown else "allow"
        return SettlementDimension(
            dimension=dimension,
            cap=cap,
            known=known,
            held=held,
            exposure=exposure,
            gross_known=gross,
            refunds=refunds,
            net_known=net,
            refund_excess=max(refunds - gross, 0),
            unknown_operations=tuple(sorted(set(unknown))),
            over_limit=over_limit,
            coverage=coverage,
            enforcement=enforcement,
        )

    def _refresh_operation(self, operation_id: str) -> None:
        """Derive lifecycle state from current facts without deleting history."""
        operation = self._operations[operation_id]
        if operation.state == "cancelled_not_started":
            return
        currents = [self._current(operation_id, dimension)[0] for dimension in self.policy.caps]
        all_closed = all(current is not None and current.kind == "final" for current in currents)
        unknown = any(current is not None and current.kind == "unknown" for current in currents)
        if operation.finished and not all_closed:
            unknown = True
        state = "unknown" if unknown else ("reconciled" if all_closed else "provisional")
        self._operations[operation_id] = SettlementOperation(operation.operation_id, operation.request_id,
                                                              operation.task_id, operation.reservation,
                                                              state=state, finished=operation.finished)

    def snapshot(self) -> SettlementSnapshot:
        dimensions = {dim: self._project_dimension(dim) for dim in sorted(self.policy.caps)}
        coverage = "complete"
        for value in dimensions.values():
            if value.coverage == "unknown":
                coverage = "unknown"
                break
            if value.coverage == "partial":
                coverage = "partial"
        return SettlementSnapshot(self._sequence, self.policy.policy_ref,
                                  MappingProxyType(dimensions), tuple(self._stop_reasons), coverage)

    def _check_admission(self, reservation: Mapping[str, int]) -> None:
        if self._stop_reasons:
            raise SettlementError("E_SETTLEMENT_STOPPED", "settlement is stopped")
        if set(reservation) != set(self.policy.caps):
            raise SettlementError("E_SETTLEMENT_DIMENSION", "reservation must cover every cap dimension")
        snapshot = self.snapshot()
        for dimension, amount in reservation.items():
            if snapshot.dimensions[dimension].unknown_operations:
                raise SettlementError("E_SETTLEMENT_UNKNOWN", dimension)
            if snapshot.dimensions[dimension].exposure + amount > self.policy.caps[dimension]:
                raise SettlementError("E_SETTLEMENT_CAP", dimension)

    def reserve(self, operation_id: str, request_id: str, task_id: str,
                reservation: Mapping[str, int]) -> SettlementDecision:
        operation_id = _text(operation_id, "operation_id")
        request_id = _text(request_id, "request_id")
        task_id = _text(task_id, "task_id")
        clean = _mapping(reservation, "reservation", nonempty=True)
        if set(clean) != set(self.policy.caps):
            raise SettlementError("E_SETTLEMENT_DIMENSION", "reservation must cover every cap dimension")
        old = self._operations.get(operation_id)
        if old is not None:
            if (old.request_id, old.task_id, old.reservation) == (request_id, task_id, clean):
                return SettlementDecision("REPLAY", replayed=True, reasons=self.stop_reasons)
            raise SettlementError("E_SETTLEMENT_CONFLICT", "operation replay conflict")
        if self._request_id is not None and request_id != self._request_id:
            raise SettlementError("E_SETTLEMENT_SCOPE", "request binding")
        self._check_admission(clean)
        self._request_id = request_id
        self._operations[operation_id] = SettlementOperation(operation_id, request_id, task_id, clean)
        self._event("operation.reserved", {"operation_id": operation_id, "reservation": dict(clean)})
        return SettlementDecision("RESERVED", changed_dimensions=tuple(sorted(clean)))

    def _fact_conflict(self, fact: SettlementFact) -> SettlementFact | None:
        existing = self._facts_by_id.get(fact.fact_id)
        if existing is None:
            return None
        if existing.fingerprint != fact.fingerprint:
            raise SettlementError("E_SETTLEMENT_CONFLICT", "fact id payload conflict")
        return existing

    def _check_scope(self, fact: SettlementFact) -> SettlementOperation:
        operation = self._operations.get(fact.operation_id)
        if operation is None:
            raise SettlementError("E_SETTLEMENT_SCOPE", "operation unknown")
        if fact.dimension not in self.policy.caps or fact.dimension not in operation.reservation:
            raise SettlementError("E_SETTLEMENT_SCOPE", "dimension unknown")
        # A stable economic call cannot be charged to two operations.  Mirrors
        # within one operation are handled below by revision and fact identity.
        owners = {item.operation_id for item in self._facts
                  if item.call_key == fact.call_key and item.kind != "refund"}
        if owners and owners != {fact.operation_id}:
            raise SettlementError("E_SETTLEMENT_SCOPE", "economic call belongs to another operation")
        return operation

    def record(self, fact: SettlementFact) -> SettlementDecision:
        if type(fact) is not SettlementFact:
            raise SettlementError("E_SETTLEMENT_VALUE", "SettlementFact required")
        self._check_scope(fact)
        if (existing := self._fact_conflict(fact)) is not None:
            return SettlementDecision("REPLAY", replayed=True, reasons=self.stop_reasons)
        if fact.kind == "refund":
            target_seen = any(item.call_key == fact.refund_for
                              and item.dimension == fact.dimension
                              and item.operation_id == fact.operation_id
                               and item.kind != "unknown"
                               for item in self._facts if item.kind != "refund")
            if not target_seen:
                raise SettlementError("E_SETTLEMENT_REFUND_TARGET", "refund target is unknown")
            self._facts.append(fact)
            self._facts_by_id[fact.fact_id] = fact
            self._event("usage.refund", fact.as_dict())
            return self._post_fact(fact, "APPLIED")

        rows = self._series_for(fact.operation_id, fact.dimension)
        current = rows[-1] if rows else None
        same_revision = next((item for item in rows if item.revision == fact.revision), None)
        if same_revision is not None:
            if same_revision.semantic_hash != fact.semantic_hash:
                raise SettlementError("E_SETTLEMENT_CONFLICT", "revision payload conflict")
            self._facts.append(fact)
            self._facts_by_id[fact.fact_id] = fact
            self._event("usage.mirror", fact.as_dict())
            return SettlementDecision("MIRROR", historical=True, reasons=self.stop_reasons)
        if rows and rows[0].call_key != fact.call_key:
            raise SettlementError("E_SETTLEMENT_KEY", "one cumulative series per operation/dimension")
        if fact.supersedes is not None:
            target = self._facts_by_id.get(fact.supersedes)
            if target is None or target.operation_id != fact.operation_id or target.dimension != fact.dimension \
                    or target.call_key != fact.call_key or target.revision >= fact.revision:
                raise SettlementError("E_SETTLEMENT_CORRECTION", "supersedes must identify a lower revision")
        historical = current is not None and fact.revision < current.revision
        if not historical and current is not None:
            _, previous = self._current(fact.operation_id, fact.dimension)
            decreases = fact.amount is not None and fact.amount < previous
            if (current.kind == "final" or decreases) and (not fact.correction or fact.supersedes != current.fact_id):
                raise SettlementError("E_SETTLEMENT_CORRECTION", "current decrease/final requires correction")
            if fact.correction and fact.supersedes != current.fact_id:
                raise SettlementError("E_SETTLEMENT_CORRECTION", "current correction must supersede current fact")
        self._facts.append(fact)
        self._facts_by_id[fact.fact_id] = fact
        self._event("usage." + fact.kind, fact.as_dict())
        return self._post_fact(fact, "HISTORICAL_ONLY" if historical else "APPLIED", historical=historical)

    def _post_fact(self, fact: SettlementFact, status: str, *, historical: bool = False) -> SettlementDecision:
        self._refresh_operation(fact.operation_id)
        snapshot = self.snapshot()
        for dimension, item in snapshot.dimensions.items():
            if item.over_limit:
                self._reason("BUDGET_EXCEEDED")
            if item.unknown_operations:
                self._reason("USAGE_UNKNOWN")
        # A stop reason is an admission gate, but late facts remain accepted.
        reasons = self.stop_reasons
        return SettlementDecision(status, historical=historical,
                                  changed_dimensions=(() if historical else (fact.dimension,)),
                                  reasons=reasons)

    def settle(self, operation_id: str) -> SettlementDecision:
        operation_id = _text(operation_id, "operation_id")
        operation = self._operations.get(operation_id)
        if operation is None:
            raise SettlementError("E_SETTLEMENT_SCOPE", "operation unknown")
        if operation.finished:
            return SettlementDecision("REPLAY", replayed=True, reasons=self.stop_reasons)
        self._operations[operation_id] = SettlementOperation(operation.operation_id, operation.request_id,
                                                             operation.task_id, operation.reservation,
                                                             state=operation.state, finished=True)
        self._refresh_operation(operation_id)
        self._event("operation.settled", {"operation_id": operation_id})
        snapshot = self.snapshot()
        for item in snapshot.dimensions.values():
            if item.unknown_operations:
                self._reason("USAGE_UNKNOWN")
        return SettlementDecision("SETTLED", reasons=self.stop_reasons)

    def release_proven_unstarted(self, operation_id: str, *, not_started_proven: bool = False) -> SettlementDecision:
        operation_id = _text(operation_id, "operation_id")
        if not_started_proven is not True:
            raise SettlementError("E_SETTLEMENT_RELEASE_NOT_PROVEN", "explicit proof required")
        operation = self._operations.get(operation_id)
        if operation is None:
            raise SettlementError("E_SETTLEMENT_SCOPE", "operation unknown")
        if operation.finished and operation.state == "cancelled_not_started":
            return SettlementDecision("REPLAY", replayed=True, reasons=self.stop_reasons)
        if operation.finished or any(fact.operation_id == operation_id for fact in self._facts):
            raise SettlementError("E_SETTLEMENT_RELEASE_NOT_PROVEN", "operation has evidence")
        self._operations[operation_id] = SettlementOperation(operation.operation_id, operation.request_id,
                                                             operation.task_id, operation.reservation,
                                                             state="cancelled_not_started", finished=True)
        self._event("operation.cancelled_not_started", {"operation_id": operation_id})
        return SettlementDecision("RELEASED", reasons=self.stop_reasons)

    def audit_record(self) -> dict[str, Any]:
        """Return a deterministic export suitable for fixture evidence."""
        return {
            "schema_version": 1,
            "policy": {"caps": dict(self.policy.caps), "policy_ref": self.policy.policy_ref,
                        "unknown_policy": self.policy.unknown_policy,
                        "refund_policy": self.policy.refund_policy},
            "sequence": self._sequence,
            "stop_reasons": list(self._stop_reasons),
            "operations": [{"operation_id": item.operation_id, "request_id": item.request_id,
                            "task_id": item.task_id, "reservation": dict(item.reservation),
                            "state": item.state, "finished": item.finished}
                           for item in self._operations.values()],
            "facts": [fact.as_dict() for fact in self._facts],
            "snapshot": {
                "coverage": self.snapshot().coverage,
                "dimensions": {key: value.__dict__ for key, value in self.snapshot().dimensions.items()},
            },
        }

    def audit_fingerprint(self) -> str:
        return _hash(self.audit_record())


__all__ = [
    "SettlementDecision", "SettlementDimension", "SettlementError", "SettlementFact",
    "SettlementOperation", "SettlementPolicy", "SettlementSnapshot", "UsageSettlement",
]
