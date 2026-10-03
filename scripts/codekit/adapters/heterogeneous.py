"""Provider-neutral routing and handoff records for the second CLI boundary.

The registry deliberately knows only the adapter protocol.  It does not
contain provider names, start processes, grant approval, or own a budget.  The
handoff and recovery records are immutable observations that the 03/05/07/09
controllers can consume after applying their own authorization and process
guards.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Protocol, Sequence

from .. import protocols
from ..builtin_artifacts import resource_ref
from ..planner_runtime import PlanningBudgetLedger
from .capability import AdapterCapability, PreflightResult, bind_profile
from .second_cli import (
    CliEvent, CollectionResult, ProbeResult, SecondCliInvocation,
    SecondCliProfile,
)


class AdapterFacadeProtocol(Protocol):
    adapter_id: str

    def probe(self, executable: str = "claude", **kwargs: Any) -> ProbeResult: ...

    def validate_profile(self, capability: AdapterCapability, **kwargs: Any) -> SecondCliProfile: ...

    def build_invocation(self, profile: SecondCliProfile, **kwargs: Any) -> SecondCliInvocation: ...

    def normalize_event(self, raw_record: bytes | str, **kwargs: Any) -> CliEvent: ...

    def collect_result(self, events: Sequence[CliEvent], **kwargs: Any) -> CollectionResult: ...


class AdapterFacadeError(ValueError):
    def __init__(self, code: str, message: str = "adapter facade input rejected") -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class HeterogeneousAdapterFacade:
    """Route all five adapter operations by registered adapter identity."""

    def __init__(self, adapters: Iterable[AdapterFacadeProtocol] = ()) -> None:
        self._adapters: dict[str, AdapterFacadeProtocol] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: AdapterFacadeProtocol) -> None:
        adapter_id = getattr(adapter, "adapter_id", None)
        if type(adapter_id) is not str or not adapter_id:
            raise AdapterFacadeError("E_ADAPTER_IDENTITY", "adapter_id is required")
        if adapter_id in self._adapters:
            raise AdapterFacadeError("E_ADAPTER_DUPLICATE", "adapter id already registered")
        for method in ("probe", "validate_profile", "build_invocation", "normalize_event", "collect_result"):
            if not callable(getattr(adapter, method, None)):
                raise AdapterFacadeError("E_ADAPTER_PROTOCOL", f"missing adapter method: {method}")
        self._adapters[adapter_id] = adapter

    def resolve(self, adapter_id: str) -> AdapterFacadeProtocol:
        adapter = self._adapters.get(adapter_id)
        if adapter is None:
            raise AdapterFacadeError("E_ADAPTER_UNKNOWN", "adapter is not registered")
        return adapter

    def probe(self, adapter_id: str, **kwargs: Any) -> ProbeResult:
        return self.resolve(adapter_id).probe(**kwargs)

    def validate_profile(self, adapter_id: str, capability: AdapterCapability, **kwargs: Any) -> SecondCliProfile:
        return self.resolve(adapter_id).validate_profile(capability, **kwargs)

    def build_invocation(self, adapter_id: str, profile: SecondCliProfile, **kwargs: Any) -> SecondCliInvocation:
        return self.resolve(adapter_id).build_invocation(profile, **kwargs)

    def normalize_event(self, adapter_id: str, raw_record: bytes | str, **kwargs: Any) -> CliEvent:
        return self.resolve(adapter_id).normalize_event(raw_record, **kwargs)

    def collect_result(self, adapter_id: str, events: Sequence[CliEvent], **kwargs: Any) -> CollectionResult:
        return self.resolve(adapter_id).collect_result(events, **kwargs)

    def adapter_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


class ProfileRouter:
    """Bind profile ids to the facade without embedding provider branches."""

    def __init__(self, facade: HeterogeneousAdapterFacade) -> None:
        self.facade = facade
        self._profiles: dict[str, tuple[str, SecondCliProfile]] = {}

    def register(self, profile: SecondCliProfile, *, capability: AdapterCapability | None = None,
                 require_observed: bool = False) -> None:
        if profile.profile_id in self._profiles:
            raise AdapterFacadeError("E_PROFILE_DUPLICATE", "profile id already registered")
        self.facade.resolve(profile.adapter_id)
        if not profile.capability_digest:
            raise AdapterFacadeError("E_PROFILE_UNBOUND", "profile must carry a capability digest")
        if capability is not None:
            if capability.adapter_id != profile.adapter_id:
                raise AdapterFacadeError("E_PROFILE_ADAPTER", "capability adapter does not match profile")
            binding = bind_profile(capability, role=profile.role, platform=profile.platform,
                                   environment_kind=profile.environment_kind,
                                   required_capabilities=profile.capabilities,
                                   model_id=profile.model_id, require_observed=require_observed)
            if not binding.supported:
                raise AdapterFacadeError("E_PROFILE_CAPABILITY", ";".join(binding.reasons))
            if binding.capability_digest != profile.capability_digest:
                raise AdapterFacadeError("E_PROFILE_DRIFT", "capability digest changed")
        self._profiles[profile.profile_id] = (profile.adapter_id, profile)

    def resolve(self, profile_id: str) -> tuple[str, SecondCliProfile]:
        binding = self._profiles.get(profile_id)
        if binding is None:
            raise AdapterFacadeError("E_PROFILE_UNKNOWN", "profile is not registered")
        return binding

    def build_invocation(self, profile_id: str, **kwargs: Any) -> SecondCliInvocation:
        adapter_id, profile = self.resolve(profile_id)
        return self.facade.build_invocation(adapter_id, profile, **kwargs)

    def probe(self, profile_id: str, **kwargs: Any) -> ProbeResult:
        adapter_id, profile = self.resolve(profile_id)
        kwargs.setdefault("executable", profile.executable)
        kwargs.setdefault("platform", profile.platform)
        kwargs.setdefault("environment_kind", profile.environment_kind)
        return self.facade.probe(adapter_id, **kwargs)

    def normalize_event(self, profile_id: str, raw_record: bytes | str, **kwargs: Any) -> CliEvent:
        adapter_id, _ = self.resolve(profile_id)
        return self.facade.normalize_event(adapter_id, raw_record, **kwargs)

    def collect_result(self, profile_id: str, events: Sequence[CliEvent], **kwargs: Any) -> CollectionResult:
        adapter_id, _ = self.resolve(profile_id)
        return self.facade.collect_result(adapter_id, events, **kwargs)

    def start_gate(self, profile_id: str, **kwargs: Any) -> "StartGate":
        """Evaluate an executor start gate for a registered profile.

        The router only supplies the provider-neutral profile binding.  The
        gate itself still rechecks the run context, handoff and shared budget
        at the point where a caller would pass an invocation to the 05
        process runner; it never starts a process or grants approval.
        """
        _, profile = self.resolve(profile_id)
        return evaluate_start_gate(profile=profile, **kwargs)


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value or any(ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F or 0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise AdapterFacadeError("E_HANDOFF_SCHEMA", f"{field} must be safe non-empty text")
    return value


def _ref(value: Any, field: str) -> dict[str, str]:
    try:
        return resource_ref(value, field)
    except Exception as exc:
        raise AdapterFacadeError("E_HANDOFF_REF", f"{field} must be a ResourceRef") from exc


@dataclass(frozen=True)
class ProfileHandoff:
    """A cross-session planner result handoff, without approval or execution."""

    request_id: str
    run_id: str
    planner_profile_id: str
    executor_profile_id: str
    planner_session_id: str
    executor_session_id: str
    contract_ref: Mapping[str, str]
    input_refs: tuple[Mapping[str, str], ...]
    budget_generation: int
    read_only: bool = True
    state: str = "READY"
    executor_context: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for field in ("request_id", "run_id", "planner_profile_id", "executor_profile_id",
                      "planner_session_id", "executor_session_id"):
            _text(getattr(self, field), field)
        if self.planner_session_id == self.executor_session_id:
            raise AdapterFacadeError("E_HANDOFF_SESSION", "planner and executor sessions must be distinct")
        object.__setattr__(self, "contract_ref", _ref(dict(self.contract_ref), "/contract_ref"))
        if type(self.input_refs) is not tuple or not self.input_refs:
            raise AdapterFacadeError("E_HANDOFF_INPUT", "at least one input ResourceRef is required")
        refs = []
        normalized_refs = []
        for index, value in enumerate(self.input_refs):
            normalized = _ref(dict(value), f"/input_refs/{index}")
            key = tuple(normalized[item] for item in ("kind", "id", "path", "sha256"))
            if key in refs:
                raise AdapterFacadeError("E_HANDOFF_INPUT", "input refs must be unique")
            refs.append(key)
            normalized_refs.append(normalized)
        object.__setattr__(self, "input_refs", tuple(normalized_refs))
        if type(self.budget_generation) is not int or self.budget_generation < 1:
            raise AdapterFacadeError("E_HANDOFF_GENERATION", "positive budget generation required")
        if type(self.read_only) is not bool or not self.read_only:
            raise AdapterFacadeError("E_HANDOFF_SCOPE", "handoff must remain read-only")
        if self.state not in {"READY", "REQUIRES_REVIEW", "BLOCKED", "RECOVERY_REQUIRED"}:
            raise AdapterFacadeError("E_HANDOFF_STATE", "unsupported handoff state")
        if self.executor_context is not None:
            try:
                context = dict(self.executor_context)
                protocols.validate_run_context(context, for_executor_dispatch=True)
            except Exception as exc:
                raise AdapterFacadeError("E_HANDOFF_CONTEXT", "executor context is not dispatch-valid") from exc
            if context["request_id"] != self.request_id or context["run_id"] != self.run_id:
                raise AdapterFacadeError("E_HANDOFF_CONTEXT", "executor context identity does not match handoff")
            object.__setattr__(self, "executor_context", context)

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "profile-handoff", "schema_version": 1,
                "request_id": self.request_id, "run_id": self.run_id,
                "planner_profile_id": self.planner_profile_id,
                "executor_profile_id": self.executor_profile_id,
                "planner_session_id": self.planner_session_id,
                "executor_session_id": self.executor_session_id,
                "contract_ref": dict(self.contract_ref),
                "input_refs": [dict(ref) for ref in self.input_refs],
                "budget_generation": self.budget_generation,
                "read_only": self.read_only, "state": self.state,
                **({"executor_context": dict(self.executor_context)} if self.executor_context is not None else {})}


def validate_handoff(handoff: ProfileHandoff, *, request_id: str, budget_generation: int,
                     planner_profile_id: str, executor_profile_id: str) -> None:
    if type(handoff) is not ProfileHandoff:
        raise AdapterFacadeError("E_HANDOFF_SCHEMA", "ProfileHandoff required")
    if handoff.request_id != request_id:
        raise AdapterFacadeError("E_HANDOFF_REQUEST", "request identity changed")
    if handoff.budget_generation != budget_generation:
        raise AdapterFacadeError("E_HANDOFF_GENERATION", "stale budget generation")
    if handoff.planner_profile_id != planner_profile_id or handoff.executor_profile_id != executor_profile_id:
        raise AdapterFacadeError("E_HANDOFF_PROFILE", "profile binding changed")
    if handoff.state != "READY":
        raise AdapterFacadeError("E_HANDOFF_STATE", "handoff is not ready")


@dataclass(frozen=True)
class CancellationObservation:
    request_id: str
    run_id: str
    generation: int
    cancel_requested: bool
    exit_code: int | None
    response_lost: bool = False
    process_observed: bool | None = None
    cancel_after_exit: bool = False
    state: str = "UNKNOWN"

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id"); _text(self.run_id, "run_id")
        if type(self.generation) is not int or self.generation < 1:
            raise AdapterFacadeError("E_RECOVERY_GENERATION", "positive generation required")
        if type(self.cancel_requested) is not bool or type(self.response_lost) is not bool or type(self.cancel_after_exit) is not bool:
            raise AdapterFacadeError("E_RECOVERY_SCHEMA", "boolean recovery facts required")
        if self.exit_code is not None and type(self.exit_code) is not int:
            raise AdapterFacadeError("E_RECOVERY_SCHEMA", "exit_code must be integer or null")
        if self.process_observed is not None and type(self.process_observed) is not bool:
            raise AdapterFacadeError("E_RECOVERY_SCHEMA", "process_observed must be boolean or null")
        if self.state not in {"CANCEL_REQUESTED", "CANCELLED", "CANCEL_AFTER_EXIT", "START_UNKNOWN", "RECOVERY_REQUIRED"}:
            raise AdapterFacadeError("E_RECOVERY_STATE", "unsupported recovery state")

    @classmethod
    def classify(cls, *, request_id: str, run_id: str, generation: int,
                 cancel_requested: bool, exit_code: int | None,
                 response_lost: bool = False, process_observed: bool | None = None,
                 cancel_after_exit: bool = False) -> "CancellationObservation":
        if not cancel_requested:
            state = "RECOVERY_REQUIRED" if response_lost or exit_code is None else "CANCEL_REQUESTED"
        elif cancel_after_exit:
            state = "CANCEL_AFTER_EXIT"
        elif process_observed:
            state = "RECOVERY_REQUIRED"
        elif response_lost or exit_code is None or process_observed is None:
            state = "START_UNKNOWN"
        else:
            state = "CANCELLED"
        return cls(request_id, run_id, generation, cancel_requested, exit_code, response_lost, process_observed, cancel_after_exit, state)

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "second-cli-recovery", "schema_version": 1,
                "request_id": self.request_id, "run_id": self.run_id,
                "generation": self.generation, "cancel_requested": self.cancel_requested,
                "exit_code": self.exit_code, "response_lost": self.response_lost,
                "process_observed": self.process_observed, "cancel_after_exit": self.cancel_after_exit,
                "state": self.state}


@dataclass(frozen=True)
class RoleGate:
    allowed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class IndependentReleaseGate:
    allowed: bool
    reasons: tuple[str, ...]
    evidence_refs: Mapping[str, Mapping[str, str]]

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "second-cli-release-gate", "schema_version": 1,
                "allowed": self.allowed, "reasons": list(self.reasons),
                "evidence_refs": {key: dict(value) for key, value in self.evidence_refs.items()}}


def evaluate_independent_release_gate(*, preflights: Sequence[PreflightResult],
                                     real_model_chain: bool, real_platform_lifecycle: bool,
                                     independent_review: bool, external_connectors: bool,
                                     evidence_refs: Mapping[str, Mapping[str, str]] | None = None) -> IndependentReleaseGate:
    """Machine-checkable final gate; offline fixtures cannot satisfy it."""
    reasons: list[str] = []
    if not isinstance(preflights, (tuple, list)) or not preflights:
        reasons.append("PREFLIGHTS_MISSING")
    elif any(type(item) is not PreflightResult or item.status != "READY" for item in preflights):
        reasons.append("PREFLIGHT_NOT_READY")
    refs: dict[str, Mapping[str, str]] = {}
    if evidence_refs is not None:
        if not isinstance(evidence_refs, Mapping):
            reasons.append("EVIDENCE_REFS_INVALID")
        else:
            for key, value in evidence_refs.items():
                try:
                    refs[key] = _ref(dict(value), "/evidence_refs/" + str(key))
                except (TypeError, AdapterFacadeError):
                    reasons.append("EVIDENCE_REF_INVALID:" + str(key))
    for key, value, reason in (("real_model_chain", real_model_chain, "REAL_MODEL_CHAIN_MISSING"),
                               ("real_platform_lifecycle", real_platform_lifecycle, "REAL_PLATFORM_LIFECYCLE_MISSING"),
                               ("independent_review", independent_review, "INDEPENDENT_REVIEW_MISSING"),
                               ("external_connectors", external_connectors, "EXTERNAL_CONNECTORS_MISSING")):
        if type(value) is not bool:
            reasons.append(reason + "_UNKNOWN")
        elif not value:
            reasons.append(reason)
        elif key not in refs:
            reasons.append("EVIDENCE_REF_MISSING:" + key)
    return IndependentReleaseGate(not reasons, tuple(dict.fromkeys(reasons)), refs)


def check_role_gate(*, profile: SecondCliProfile, expected_role: str,
                    handoff: ProfileHandoff | None = None,
                    ledger: PlanningBudgetLedger | None = None,
                    generation: int | None = None) -> RoleGate:
    reasons: list[str] = []
    if profile.role != expected_role:
        reasons.append("ROLE_MISMATCH")
    if expected_role == "executor" and profile.read_only is not True:
        reasons.append("EXECUTOR_SCOPE_UNKNOWN")
    if handoff is not None:
        try:
            validate_handoff(handoff, request_id=handoff.request_id,
                             budget_generation=generation if generation is not None else handoff.budget_generation,
                             planner_profile_id=handoff.planner_profile_id,
                             executor_profile_id=handoff.executor_profile_id)
        except AdapterFacadeError as exc:
            reasons.append(exc.code)
    if ledger is None:
        reasons.append("BUDGET_UNBOUND")
    else:
        if generation is not None and ledger.generation != generation:
            reasons.append("STALE_GENERATION")
        stopped, stop_reasons = ledger.state.stop_decision()
        if stopped:
            reasons.extend("BUDGET_" + reason for reason in stop_reasons)
        if ledger.request_id != (handoff.request_id if handoff is not None else ledger.request_id):
            reasons.append("REQUEST_MISMATCH")
    return RoleGate(not reasons, tuple(dict.fromkeys(reasons)))


@dataclass(frozen=True)
class StartGate:
    """Point-in-time executor admission decision for an offline runtime.

    ``allowed`` means only that the supplied, already-built invocation may be
    handed to a trusted 05 runner.  It is not evidence that a process started
    and it does not consume budget or approval.
    """

    allowed: bool
    reasons: tuple[str, ...]
    context_report: Mapping[str, Any] | None = None

    def to_mapping(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "reasons": list(self.reasons),
                "context_report": dict(self.context_report) if self.context_report is not None else None}


def evaluate_start_gate(*, run_context: Mapping[str, Any], profile: SecondCliProfile,
                        handoff: ProfileHandoff, ledger: PlanningBudgetLedger,
                        invocation: SecondCliInvocation | None = None,
                        generation: int | None = None) -> StartGate:
    """Recheck all local bindings immediately before executor dispatch.

    This is deliberately provider-neutral: the only provider-specific object
    is the adapter-created ``SecondCliInvocation``.  The gate validates the
    shared RunContext contract and identity, then checks the cross-session
    handoff, profile role, generation and core ``PlanningBudgetLedger``.  A
    missing or mismatched fact is a conservative block, never an implicit
    start or retry.
    """
    reasons: list[str] = []
    report: Mapping[str, Any] | None = None
    context: Mapping[str, Any] | None = run_context if isinstance(run_context, Mapping) else None
    if context is None:
        reasons.append("CONTEXT_SCHEMA")
    else:
        try:
            report = protocols.validate_run_context(dict(context), for_executor_dispatch=True)
        except protocols.ProtocolError as exc:
            reasons.append("CONTEXT_" + exc.code)

    expected_generation = handoff.budget_generation if generation is None else generation
    if type(expected_generation) is not int or expected_generation < 1:
        reasons.append("GENERATION_INVALID")
    try:
        role_gate = check_role_gate(profile=profile, expected_role="executor", handoff=handoff,
                                    ledger=ledger, generation=expected_generation)
        reasons.extend(role_gate.reasons)
    except (AdapterFacadeError, TypeError, AttributeError):
        reasons.append("ROLE_GATE_SCHEMA")

    if context is not None and not any(item.startswith("CONTEXT_") for item in reasons):
        if context.get("request_id") != handoff.request_id:
            reasons.append("REQUEST_MISMATCH")
        if context.get("run_id") != handoff.run_id:
            reasons.append("RUN_MISMATCH")
        if context.get("role") != "executor":
            reasons.append("ROLE_MISMATCH")
        if context.get("platform") != profile.platform:
            reasons.append("PLATFORM_MISMATCH")
        try:
            context_ref = _ref(dict(context["contract_ref"]), "/context/contract_ref")
            if context_ref != handoff.contract_ref:
                reasons.append("CONTRACT_MISMATCH")
        except (KeyError, TypeError, AdapterFacadeError):
            reasons.append("CONTRACT_MISMATCH")
        if handoff.executor_context is not None and dict(context) != dict(handoff.executor_context):
            reasons.append("CONTEXT_DRIFT")

    if isinstance(ledger, PlanningBudgetLedger):
        if context is not None and ledger.request_id != context.get("request_id"):
            reasons.append("REQUEST_MISMATCH")
        if expected_generation != ledger.generation:
            reasons.append("STALE_GENERATION")
    else:
        reasons.append("BUDGET_UNBOUND")

    if invocation is not None:
        if not isinstance(invocation, SecondCliInvocation):
            reasons.append("INVOCATION_SCHEMA")
        else:
            adapter = invocation.adapter
            runtime = invocation.runtime
            if adapter.request_id != handoff.request_id or runtime.request_id != handoff.request_id:
                reasons.append("INVOCATION_REQUEST_MISMATCH")
            if adapter.run_id != handoff.run_id or runtime.run_id != handoff.run_id:
                reasons.append("INVOCATION_RUN_MISMATCH")
            if adapter.role != "executor" or profile.role != "executor":
                reasons.append("INVOCATION_ROLE_MISMATCH")
            if adapter.profile_id != handoff.executor_profile_id or profile.profile_id != handoff.executor_profile_id:
                reasons.append("INVOCATION_PROFILE_MISMATCH")
            if adapter.adapter_id != profile.adapter_id:
                reasons.append("INVOCATION_ADAPTER_MISMATCH")
            if invocation.read_only is not True:
                reasons.append("INVOCATION_SCOPE_UNKNOWN")
            if invocation.session_id != handoff.executor_session_id:
                reasons.append("INVOCATION_SESSION_MISMATCH")

    return StartGate(not reasons, tuple(dict.fromkeys(reasons)), report)


__all__ = ["AdapterFacadeError", "AdapterFacadeProtocol", "CancellationObservation",
           "HeterogeneousAdapterFacade", "IndependentReleaseGate", "ProfileHandoff", "ProfileRouter",
           "RoleGate", "StartGate", "check_role_gate", "evaluate_independent_release_gate",
           "evaluate_start_gate", "validate_handoff"]
