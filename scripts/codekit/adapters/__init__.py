"""Trusted adapter protocol and deterministic offline adapter."""

from .offline import OfflineAdapter
from .capability import PreflightResult, preflight_profile
from .heterogeneous import (AdapterFacadeError, CancellationObservation, HeterogeneousAdapterFacade,
                            FallbackDecision, IndependentReleaseGate, ProfileHandoff, ProfileRouter,
                            RecoveryLedger, RoleGate, StartGate, check_role_gate,
                            evaluate_independent_release_gate, evaluate_start_gate, select_fallback,
                            validate_handoff)
from .protocol import (AdapterDescriptor, AdapterError, AdapterRegistry, AdapterResult, Invocation,
                       NormalizedEvent, normalize_events)
from .second_cli import RawRecordStore

__all__ = ["AdapterDescriptor", "AdapterError", "AdapterRegistry", "AdapterResult", "Invocation",
           "NormalizedEvent", "OfflineAdapter", "normalize_events", "AdapterFacadeError",
           "CancellationObservation", "HeterogeneousAdapterFacade", "ProfileHandoff", "RoleGate",
           "ProfileRouter", "RawRecordStore", "StartGate", "check_role_gate", "evaluate_start_gate",
           "validate_handoff", "PreflightResult", "preflight_profile", "IndependentReleaseGate",
           "evaluate_independent_release_gate", "FallbackDecision", "RecoveryLedger", "select_fallback"]
