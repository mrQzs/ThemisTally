"""Pull-only delivery boundary and offline release gate for 10."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping, Sequence

from .project_events import canonical_bytes


class DeliveryError(ValueError):
    def __init__(self, code: str, message: str = "delivery rejected") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class DeliveryReceipt:
    delivery_id: str
    view_id: str
    mode: str
    status: str
    reason: str

    def to_mapping(self) -> dict[str, Any]:
        return {"record_type": "delivery-receipt", "schema_version": 1,
                "delivery_id": self.delivery_id, "view_id": self.view_id,
                "mode": self.mode, "status": self.status, "reason": self.reason}


def request_pull_delivery(view_id: str, *, observer_ref: str, mode: str = "pull") -> DeliveryReceipt:
    if type(view_id) is not str or len(view_id) != 64 or any(ch not in "0123456789abcdef" for ch in view_id):
        raise DeliveryError("E_VIEW", "view id must be lowercase sha256")
    if type(observer_ref) is not str or not observer_ref:
        raise DeliveryError("E_OBSERVER", "observer reference required")
    if mode != "pull":
        raise DeliveryError("E_MODE", "10 only supports pull delivery")
    body = {"view_id": view_id, "observer_ref": observer_ref, "mode": mode}
    delivery_id = hashlib.sha256(canonical_bytes(body)).hexdigest()
    return DeliveryReceipt(delivery_id, view_id, mode, "NOT_RUN", "host delivery adapter not connected")


FAULT_IDS = tuple(f"F{i:02d}" for i in range(1, 31))


def offline_fault_matrix() -> list[dict[str, str]]:
    """Return a reviewable matrix; synthetic entries never claim production."""
    return [{"id": fault_id, "status": "LOCAL_REFERENCE", "production": "NOT_RUN/BLOCKED"} for fault_id in FAULT_IDS]


def evaluate_release_gate(stage_results: Mapping[str, str], *, real_capabilities: Mapping[str, str]) -> dict[str, Any]:
    if type(stage_results) is not dict or type(real_capabilities) is not dict:
        raise DeliveryError("E_GATE", "gate inputs must be mappings")
    failures = [key for key, value in stage_results.items() if value not in {"PASS", "ACCEPTED_WITH_EXCEPTION"}]
    blocked = [key for key, value in real_capabilities.items() if value not in {"ready", "verified"}]
    status = "BLOCKED" if failures or blocked else "PASS"
    reasons = ["stage:" + key for key in sorted(failures)] + ["capability:" + key for key in sorted(blocked)]
    return {"record_type": "release-gate", "schema_version": 1, "status": status,
            "production_release": False if status != "PASS" else True,
            "reasons": reasons, "fault_matrix": offline_fault_matrix()}


__all__ = ["FAULT_IDS", "DeliveryError", "DeliveryReceipt", "evaluate_release_gate", "offline_fault_matrix", "request_pull_delivery"]
