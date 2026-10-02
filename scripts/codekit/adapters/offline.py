"""Deterministic adapter used for protocol tests; it never starts a process."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .protocol import AdapterError, AdapterResult, Invocation, normalize_events


class OfflineAdapter:
    adapter_id = "offline"
    protocol_version = "offline-adapter-v1"

    def probe(self) -> Mapping[str, Any]:
        return {"adapter_id": self.adapter_id, "protocol_version": self.protocol_version,
                "offline": True, "process_started": False, "network_used": False}

    def run(self, invocation: Invocation, events: Iterable[Mapping[str, Any]]) -> AdapterResult:
        normalized = normalize_events(events, expected_source=self.adapter_id)
        if not normalized or normalized[0].event_type != "run_started":
            raise AdapterError("E_ADAPTER_SETTLEMENT", "run_started is required")
        terminal = normalized[-1].event_type
        settled = terminal in {"run_finished", "error"}
        if not settled:
            return AdapterResult(invocation.digest(), normalized, False, "UNKNOWN", {"status": "unknown"}, False)
        usage = {"status": "unknown"}
        for event in normalized:
            if event.event_type == "usage":
                usage = dict(event.payload)
        status = "ERROR" if terminal == "error" else "SUCCEEDED"
        return AdapterResult(invocation.digest(), normalized, True, status, usage, True)


__all__ = ["OfflineAdapter"]
