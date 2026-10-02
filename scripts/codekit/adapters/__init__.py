"""Trusted adapter protocol and deterministic offline adapter."""

from .offline import OfflineAdapter
from .protocol import (AdapterDescriptor, AdapterError, AdapterRegistry, AdapterResult, Invocation,
                       NormalizedEvent, normalize_events)

__all__ = ["AdapterDescriptor", "AdapterError", "AdapterRegistry", "AdapterResult", "Invocation",
           "NormalizedEvent", "OfflineAdapter", "normalize_events"]
