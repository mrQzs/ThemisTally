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
        if invocation.adapter_id is not None and invocation.adapter_id != self.adapter_id:
            raise AdapterError("E_ADAPTER_IDENTITY", "invocation adapter does not match offline adapter")
        normalized = normalize_events(events, expected_source=self.adapter_id, preserve_unknown=True)
        if not normalized or normalized[0].event_type != "run_started":
            raise AdapterError("E_ADAPTER_SETTLEMENT", "run_started is required")
        terminal_indexes = [index for index, event in enumerate(normalized)
                            if event.event_type in {"run_finished", "error"}]
        if len(terminal_indexes) > 1 or (terminal_indexes and terminal_indexes[0] != len(normalized) - 1):
            raise AdapterError("E_ADAPTER_SETTLEMENT", "terminal event must be unique and final")
        open_tools = set()
        for event in normalized:
            if event.event_type == "run_started" and event.seq != 0:
                raise AdapterError("E_ADAPTER_SETTLEMENT", "run_started must be the first event", seq=event.seq)
            if event.event_type == "tool_started":
                tool_id = event.payload.get("tool_id")
                if not isinstance(tool_id, str) or not tool_id:
                    raise AdapterError("E_ADAPTER_TOOL", "tool_started requires a tool_id", seq=event.seq)
                if tool_id in open_tools:
                    raise AdapterError("E_ADAPTER_TOOL", "tool_started repeated before tool_finished", seq=event.seq)
                open_tools.add(tool_id)
            elif event.event_type == "tool_finished":
                tool_id = event.payload.get("tool_id")
                if not isinstance(tool_id, str) or not tool_id or tool_id not in open_tools:
                    raise AdapterError("E_ADAPTER_TOOL", "tool_finished must close an open tool", seq=event.seq)
                open_tools.remove(tool_id)
        if terminal_indexes and open_tools:
            raise AdapterError("E_ADAPTER_TOOL", "terminal event arrived with open tools")
        terminal = normalized[-1].event_type
        settled = terminal in {"run_finished", "error"}
        if not settled:
            return AdapterResult(invocation.digest(), normalized, False, "UNKNOWN", {"status": "unknown"}, False)
        usage = {"status": "unknown"}
        for event in normalized:
            if event.event_type == "usage":
                usage = dict(event.payload)
        status = "ERROR" if terminal == "error" else "SUCCEEDED"
        return AdapterResult(invocation.digest(), normalized, True, status, usage, terminal == "run_finished")


__all__ = ["OfflineAdapter"]
