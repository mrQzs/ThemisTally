"""Trusted adapter protocol and deterministic offline adapter."""

from .offline import OfflineAdapter
from .heterogeneous import (AdapterFacadeError, CancellationObservation, HeterogeneousAdapterFacade,
                            ProfileHandoff, RoleGate, check_role_gate, validate_handoff)
from .protocol import (AdapterDescriptor, AdapterError, AdapterRegistry, AdapterResult, Invocation,
                       NormalizedEvent, normalize_events)

__all__ = ["AdapterDescriptor", "AdapterError", "AdapterRegistry", "AdapterResult", "Invocation",
           "NormalizedEvent", "OfflineAdapter", "normalize_events", "AdapterFacadeError",
           "CancellationObservation", "HeterogeneousAdapterFacade", "ProfileHandoff", "RoleGate",
           "check_role_gate", "validate_handoff"]
