"""Trusted adapter protocol and deterministic offline adapter."""

from .offline import OfflineAdapter
from .heterogeneous import (AdapterFacadeError, CancellationObservation, HeterogeneousAdapterFacade,
                            ProfileHandoff, ProfileRouter, RoleGate, StartGate, check_role_gate,
                            evaluate_start_gate, validate_handoff)
from .protocol import (AdapterDescriptor, AdapterError, AdapterRegistry, AdapterResult, Invocation,
                       NormalizedEvent, normalize_events)
from .second_cli import RawRecordStore

__all__ = ["AdapterDescriptor", "AdapterError", "AdapterRegistry", "AdapterResult", "Invocation",
           "NormalizedEvent", "OfflineAdapter", "normalize_events", "AdapterFacadeError",
           "CancellationObservation", "HeterogeneousAdapterFacade", "ProfileHandoff", "RoleGate",
           "ProfileRouter", "RawRecordStore", "StartGate", "check_role_gate", "evaluate_start_gate",
           "validate_handoff"]
