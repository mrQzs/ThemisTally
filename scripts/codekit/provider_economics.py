"""Deterministic, offline provider and billing facts.

This module deliberately stops at a fact model.  It does not discover
providers, read credentials, call a network service, or infer billing from a
partial observation.  The in-memory adapter is useful for fixtures and for
testing the idempotency and accounting rules before a durable ledger exists.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from .protocols import MAX_SAFE_INTEGER


class EconomicsError(ValueError):
    """A rejected economic fact with a stable machine-readable code."""

    def __init__(self, code: str, message: str = "economic fact rejected") -> None:
        self.code = code
        super().__init__(message)


_IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_CURRENCY = re.compile(r"[A-Z][A-Z0-9]{2,11}\Z")
_VISIBILITY = frozenset(("complete", "partial", "unknown"))
_MAX_ITEMS = 512
_MAX_CANONICAL_DEPTH = 64


def _text(value: Any, name: str, *, pattern: re.Pattern[str] = _IDENT) -> str:
    if type(value) is not str or not value or len(value) > 128 or pattern.fullmatch(value) is None:
        raise EconomicsError("E_ECONOMIC_VALUE", name)
    return value


def _currency(value: Any, name: str = "currency") -> str:
    if type(value) is not str or _CURRENCY.fullmatch(value) is None:
        raise EconomicsError("E_CURRENCY", name)
    return value


def _units(value: Any, name: str, *, minimum: int = 0) -> int:
    # bool is an int subclass, hence the exact type check.
    if type(value) is not int or value < minimum or value > MAX_SAFE_INTEGER:
        raise EconomicsError("E_UNITS", name)
    return value


def _canonical_value(value: Any, path: str = "$", *, _stack: set[int] | None = None,
                     _depth: int = 0) -> Any:
    """Copy JSON-shaped values while fencing cycles and invalid Unicode.

    The provider adapter fingerprints caller-supplied fixture values.  A
    recursive container or an isolated surrogate must become a stable
    ``EconomicsError`` rather than leaking ``RecursionError`` or
    ``UnicodeEncodeError`` from the serializer.
    """
    if _depth > _MAX_CANONICAL_DEPTH:
        raise EconomicsError("E_CANONICAL", path)
    if isinstance(value, float):
        raise EconomicsError("E_FLOAT", path)
    if isinstance(value, str) and any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise EconomicsError("E_CANONICAL", path)
    if _stack is None:
        _stack = set()
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in _stack:
            raise EconomicsError("E_CANONICAL", path)
        _stack.add(identity)
        result = {}
        try:
            for key, item in value.items():
                if type(key) is not str:
                    raise EconomicsError("E_CANONICAL", path)
                result[key] = _canonical_value(item, path + "." + key,
                                                _stack=_stack, _depth=_depth + 1)
            return result
        finally:
            _stack.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in _stack:
            raise EconomicsError("E_CANONICAL", path)
        _stack.add(identity)
        try:
            return [_canonical_value(item, "%s[%d]" % (path, index),
                                     _stack=_stack, _depth=_depth + 1)
                    for index, item in enumerate(value)]
        finally:
            _stack.remove(identity)
    return value


def canonical_json(value: Any) -> str:
    """Return the single JSON representation used for economic fingerprints."""
    value = _canonical_value(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False)
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise EconomicsError("E_CANONICAL", "payload is not canonical JSON") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _freeze_mapping(values: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    if not isinstance(values, Mapping) or len(values) > _MAX_ITEMS:
        raise EconomicsError("E_ECONOMIC_VALUE", name)
    copy = _canonical_value(values, name)
    # Fingerprinting must not depend on mutation of a caller-owned dict.
    return MappingProxyType(copy)


class CallVisibility:
    """Coverage values for provider call facts.

    Strings are used intentionally so serialized records remain stable across
    Python versions and callers can compare a value directly with ``"partial"``.
    """

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    # Readable aliases used by callers that describe the evidence rather than
    # the wire coverage field.
    KNOWN = COMPLETE
    INCOMPLETE = PARTIAL
    UNAVAILABLE = UNKNOWN
    VALUES = _VISIBILITY


@dataclass(frozen=True)
class ProviderIdentity:
    """Stable provider/account/source identity; no secret or endpoint token."""

    provider: str
    model: str
    account: str
    source: str = "offline"
    region: str | None = None

    def __post_init__(self) -> None:
        for name in ("provider", "model", "account", "source"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if self.region is not None:
            object.__setattr__(self, "region", _text(self.region, "region"))

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"provider": self.provider, "model": self.model,
                                  "account": self.account, "source": self.source}
        if self.region is not None:
            result["region"] = self.region
        return result

    @property
    def fingerprint(self) -> str:
        return canonical_sha256(self.as_dict())

    @property
    def identity_key(self) -> tuple[str, str, str, str, str | None]:
        return (self.provider, self.model, self.account, self.source, self.region)


@dataclass(frozen=True)
class EconomicCallIdentity:
    """The provider call key shared by retries and multiple runs.

    ``run_id`` is provenance and is intentionally excluded from ``call_key``;
    the same provider call observed by two runs therefore becomes MIRROR.
    """

    call_id: str
    provider: str
    model: str
    account: str
    source: str
    request_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    region: str | None = None

    def __post_init__(self) -> None:
        for name in ("call_id", "provider", "model", "account", "source"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("request_id", "task_id", "run_id", "region"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _text(value, name))

    def as_dict(self, *, include_run: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {"call_id": self.call_id, "provider": self.provider,
                                  "model": self.model, "account": self.account,
                                  "source": self.source}
        for name in ("request_id", "task_id", "region"):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        if include_run and self.run_id is not None:
            result["run_id"] = self.run_id
        return result

    @property
    def call_key(self) -> str:
        return canonical_sha256(self.as_dict(include_run=False))

    @property
    def fingerprint(self) -> str:
        return self.call_key

    @property
    def provider_identity(self) -> ProviderIdentity:
        """Return the provider/account portion as a reusable identity value."""
        return ProviderIdentity(self.provider, self.model, self.account, self.source, self.region)


@dataclass(frozen=True)
class ProviderCallObservation:
    """A bounded provider report, including explicit coverage."""

    observation_id: str
    identity: EconomicCallIdentity
    visibility: str = CallVisibility.COMPLETE
    units: Mapping[str, int] = field(default_factory=dict)
    currency: str | None = None
    amount_units: int | None = None
    evidence_ref: str | None = None
    revision: int = 1
    # Optional redundant view accepted by offline adapters that receive a
    # provider identity beside the call identity.  It is checked for
    # consistency and never becomes a second source of truth.
    provider_identity: ProviderIdentity | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_id", _text(self.observation_id, "observation_id"))
        if type(self.identity) is not EconomicCallIdentity:
            raise EconomicsError("E_ECONOMIC_VALUE", "identity")
        if self.provider_identity is not None:
            if type(self.provider_identity) is not ProviderIdentity or self.provider_identity.identity_key != self.identity.provider_identity.identity_key:
                raise EconomicsError("E_ECONOMIC_CONFLICT", "provider_identity does not match identity")
        if type(self.visibility) is not str or self.visibility not in _VISIBILITY:
            raise EconomicsError("E_COVERAGE", "visibility")
        if not isinstance(self.units, Mapping) or len(self.units) > _MAX_ITEMS:
            raise EconomicsError("E_UNITS", "units")
        clean_units = { _text(key, "unit"): _units(value, "unit") for key, value in self.units.items() }
        object.__setattr__(self, "units", MappingProxyType(clean_units))
        if self.currency is not None:
            object.__setattr__(self, "currency", _currency(self.currency))
        if self.amount_units is not None:
            object.__setattr__(self, "amount_units", _units(self.amount_units, "amount_units"))
        if self.evidence_ref is not None:
            object.__setattr__(self, "evidence_ref", _text(self.evidence_ref, "evidence_ref"))
        object.__setattr__(self, "revision", _units(self.revision, "revision", minimum=1))
        if self.amount_units is not None and self.currency is None:
            raise EconomicsError("E_CURRENCY", "currency is required for amount_units")

    def semantic_payload(self) -> dict[str, Any]:
        result: dict[str, Any] = {"identity": self.identity.as_dict(include_run=False),
                                  "visibility": self.visibility,
                                  "units": dict(self.units),
                                  "revision": self.revision}
        if self.evidence_ref is not None:
            result["evidence_ref"] = self.evidence_ref
        if self.currency is not None:
            result["currency"] = self.currency
        if self.amount_units is not None:
            result["amount_units"] = self.amount_units
        return result

    @property
    def payload_hash(self) -> str:
        return canonical_sha256(self.semantic_payload())

    @property
    def call_payload_hash(self) -> str:
        """Fingerprint the economic facts independently of evidence location.

        Evidence references identify where one observer saw a fact.  They are
        part of the observation idempotency payload, but they are not part of
        the provider call's economic value.  Two runs can therefore report the
        same call with different local evidence anchors and still be recorded
        as a mirror.  Revision, visibility, units, amount, and provider
        identity remain bound to this fingerprint.
        """
        payload = self.semantic_payload()
        payload.pop("evidence_ref", None)
        return canonical_sha256(payload)

    @property
    def call_key(self) -> str:
        return self.identity.call_key

    @property
    def call_identity(self) -> EconomicCallIdentity:
        return self.identity

    @property
    def coverage(self) -> str:
        return self.visibility


@dataclass(frozen=True)
class InvoiceLine:
    invoice_id: str
    line_id: str
    account: str
    source: str
    currency: str
    amount_units: int

    def __post_init__(self) -> None:
        for name in ("invoice_id", "line_id", "account", "source"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "currency", _currency(self.currency))
        object.__setattr__(self, "amount_units", _units(self.amount_units, "amount_units"))

    @property
    def line_key(self) -> tuple[str, str]:
        return self.invoice_id, self.line_id

    @property
    def total_units(self) -> int:
        return self.amount_units


@dataclass(frozen=True)
class AllocationEntry:
    entry_id: str
    invoice_id: str
    line_id: str
    call_key: str
    currency: str
    amount_units: int
    account: str
    source: str

    def __post_init__(self) -> None:
        for name in ("entry_id", "invoice_id", "line_id", "call_key", "account", "source"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "currency", _currency(self.currency))
        object.__setattr__(self, "amount_units", _units(self.amount_units, "amount_units"))

    @property
    def line_key(self) -> tuple[str, str]:
        return self.invoice_id, self.line_id

    @property
    def units(self) -> int:
        return self.amount_units

    @property
    def payload_hash(self) -> str:
        return canonical_sha256({"invoice_id": self.invoice_id, "line_id": self.line_id,
                                 "call_key": self.call_key, "currency": self.currency,
                                 "amount_units": self.amount_units, "account": self.account,
                                 "source": self.source})


@dataclass(frozen=True)
class BillingDecision:
    status: str
    replayed: bool = False
    historical: bool = False
    coverage: str = CallVisibility.COMPLETE


class OfflineBillingAdapter:
    """An isolated fixture ledger for observations, invoices, and allocations."""

    def __init__(self) -> None:
        self._observations: dict[str, ProviderCallObservation] = {}
        self._calls: dict[str, ProviderCallObservation] = {}
        self._invoices: dict[tuple[str, str], InvoiceLine] = {}
        self._allocations: dict[str, AllocationEntry] = {}

    @property
    def observations(self) -> tuple[ProviderCallObservation, ...]:
        return tuple(self._observations.values())

    @property
    def invoices(self) -> tuple[InvoiceLine, ...]:
        return tuple(self._invoices.values())

    @property
    def allocations(self) -> tuple[AllocationEntry, ...]:
        return tuple(self._allocations.values())

    def record_observation(self, observation: ProviderCallObservation) -> BillingDecision:
        if type(observation) is not ProviderCallObservation:
            raise EconomicsError("E_ECONOMIC_VALUE", "observation")
        existing = self._observations.get(observation.observation_id)
        if existing is not None:
            if existing.payload_hash == observation.payload_hash:
                return BillingDecision("REPLAY", replayed=True, coverage=existing.coverage)
            raise EconomicsError("E_OBSERVATION_CONFLICT", "observation id payload conflict")
        prior = self._calls.get(observation.call_key)
        if prior is not None:
            # Evidence references are observer-local anchors.  Keep them in
            # ``payload_hash`` so replaying one observation id with a changed
            # anchor is a conflict, while cross-run observations of the same
            # economic call compare only the call facts.
            if prior.call_payload_hash != observation.call_payload_hash:
                raise EconomicsError("E_CALL_CONFLICT", "economic call payload conflict")
            self._observations[observation.observation_id] = observation
            return BillingDecision("MIRROR", historical=True, coverage=observation.coverage)
        self._observations[observation.observation_id] = observation
        self._calls[observation.call_key] = observation
        return BillingDecision("APPLIED", coverage=observation.coverage)

    observe = record_observation
    record_call = record_observation
    observe_call = record_observation

    def coverage(self) -> str:
        values = [item.coverage for item in self._observations.values()]
        if not values:
            return CallVisibility.UNKNOWN
        if any(value == CallVisibility.UNKNOWN for value in values):
            return CallVisibility.UNKNOWN
        if any(value == CallVisibility.PARTIAL for value in values):
            return CallVisibility.PARTIAL
        return CallVisibility.COMPLETE

    def add_invoice_line(self, line: InvoiceLine) -> BillingDecision:
        if type(line) is not InvoiceLine:
            raise EconomicsError("E_ECONOMIC_VALUE", "invoice line")
        existing = self._invoices.get(line.line_key)
        if existing is not None:
            if existing == line:
                return BillingDecision("REPLAY", replayed=True)
            raise EconomicsError("E_INVOICE_CONFLICT", "invoice line conflict")
        self._invoices[line.line_key] = line
        return BillingDecision("APPLIED")

    add_invoice = add_invoice_line
    record_invoice = add_invoice_line

    def allocate(self, entry: AllocationEntry) -> BillingDecision:
        if type(entry) is not AllocationEntry:
            raise EconomicsError("E_ECONOMIC_VALUE", "allocation")
        line = self._invoices.get(entry.line_key)
        if line is None:
            raise EconomicsError("E_INVOICE_UNKNOWN", "invoice line is not registered")
        if (line.currency, line.account, line.source) != (entry.currency, entry.account, entry.source):
            raise EconomicsError("E_ALLOCATION_SCOPE", "currency/account/source mismatch")
        if entry.call_key not in self._calls:
            raise EconomicsError("E_CALL_UNKNOWN", "call must be observed before allocation")
        existing = self._allocations.get(entry.entry_id)
        if existing is not None:
            if existing.payload_hash == entry.payload_hash:
                return BillingDecision("REPLAY", replayed=True)
            raise EconomicsError("E_ALLOCATION_CONFLICT", "allocation id payload conflict")
        same_target = [item for item in self._allocations.values()
                       if item.line_key == entry.line_key and item.call_key == entry.call_key]
        if same_target:
            if same_target[0].payload_hash == entry.payload_hash:
                return BillingDecision("MIRROR", historical=True)
            raise EconomicsError("E_ALLOCATION_CONFLICT", "call allocation conflict")
        if self.allocated_total(entry.invoice_id, entry.line_id) + entry.amount_units > line.amount_units:
            raise EconomicsError("E_ALLOCATION_EXCEEDS_LINE", "allocation exceeds invoice line")
        self._allocations[entry.entry_id] = entry
        return BillingDecision("APPLIED")

    def allocated_total(self, invoice_id: str, line_id: str) -> int:
        _text(invoice_id, "invoice_id"); _text(line_id, "line_id")
        return sum(item.amount_units for item in self._allocations.values()
                   if item.invoice_id == invoice_id and item.line_id == line_id)

    def unallocated(self, invoice_id: str, line_id: str) -> int:
        line = self._invoices.get((_text(invoice_id, "invoice_id"), _text(line_id, "line_id")))
        if line is None:
            raise EconomicsError("E_INVOICE_UNKNOWN", "invoice line is not registered")
        return line.amount_units - self.allocated_total(invoice_id, line_id)

    def allocation_complete(self, invoice_id: str, line_id: str) -> bool:
        return self.unallocated(invoice_id, line_id) == 0

    allocate_invoice = allocate

    def invoice_total(self, invoice_id: str, line_id: str) -> int:
        return self.allocated_total(invoice_id, line_id)

    def snapshot(self) -> Mapping[str, Any]:
        """Return a deterministic, read-only summary for fixture assertions."""
        return MappingProxyType({
            "coverage": self.coverage(),
            "observation_count": len(self._observations),
            "invoice_count": len(self._invoices),
            "allocation_count": len(self._allocations),
        })
