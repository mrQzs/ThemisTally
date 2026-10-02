"""Append-only offline persistence for the approval/input-lock ledger.

The store is deliberately small and file based.  It is useful for crash and
recovery fixtures, but it is not a production authorization service: callers
still need the core dispatcher, durable storage policy, and external audit
controls before allowing side effects.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .authorization import (ApprovalLedger, ApprovalHead, AuthorizationError, InputLock,
                            canonical_bytes, validate_approval, validate_authorization)


class AuthorizationStoreError(AuthorizationError):
    pass


class PersistentApprovalStore:
    """Replay an append-only journal and persist successful ledger mutations."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.ledger = ApprovalLedger()
        self.high_water = 0
        self.recovery: Dict[str, Any] = {"status": "CLEAN", "ignored_tail": False}
        self._operation_events: set[tuple[str, str]] = set()
        self._load()

    def _fail(self, code: str, message: str) -> None:
        raise AuthorizationStoreError(code, "/journal", message)

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = self.path.read_bytes()
        if not raw:
            return
        lines = raw.splitlines(keepends=True)
        for index, line in enumerate(lines):
            complete = line.endswith(b"\n")
            try:
                event = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                if index == len(lines) - 1 and not complete:
                    self.recovery = {"status": "TRUNCATED_TAIL", "ignored_tail": True, "line": index + 1}
                    break
                self._fail("E_AUTH_JOURNAL", f"invalid non-tail event at line {index + 1}")
            if not complete and index == len(lines) - 1:
                self.recovery = {"status": "TRUNCATED_TAIL", "ignored_tail": True, "line": index + 1}
                break
            if not isinstance(event, dict):
                self._fail("E_AUTH_JOURNAL", f"event must be an object at line {index + 1}")
            event_type = event.get("type")
            approval_shape = {"seq", "type", "scope", "operation_id", "expected_generation", "record"}
            lock_shape = {"seq", "type", "scope", "operation_id", "receipt_id", "bindings"}
            consume_shape = {"seq", "type", "scope", "operation_id", "expected_generation", "action", "input_refs"}
            if event_type == "approval" and set(event) != approval_shape:
                self._fail("E_AUTH_JOURNAL", f"invalid approval shape at line {index + 1}")
            if event_type == "lock" and set(event) != lock_shape:
                self._fail("E_AUTH_JOURNAL", f"invalid lock shape at line {index + 1}")
            if event_type == "consume" and set(event) != consume_shape:
                self._fail("E_AUTH_JOURNAL", f"invalid consume shape at line {index + 1}")
            if event_type not in {"approval", "lock", "consume"}:
                self._fail("E_AUTH_JOURNAL", f"unknown event type at line {index + 1}")
            seq = event.get("seq")
            if type(seq) is not int or seq != self.high_water + 1:
                self._fail("E_AUTH_JOURNAL", f"non-contiguous sequence at line {index + 1}")
            self.high_water = seq
            self._operation_events.add((event["type"], event["operation_id"]))
            if event["type"] == "approval":
                self.ledger.put(scope=event["scope"], operation_id=event["operation_id"], expected_generation=event["expected_generation"], record=event["record"])
            elif event["type"] == "lock":
                self.ledger.lock(scope=event["scope"], receipt_id=event["receipt_id"], operation_id=event["operation_id"], bindings=event["bindings"])
            elif event["type"] == "consume":
                if not self.ledger.consume_once(scope=event["scope"], action=event["action"],
                                                input_refs=event["input_refs"], operation_id=event["operation_id"],
                                                expected_generation=event["expected_generation"]):
                    self._fail("E_AUTH_JOURNAL", f"consume event was not applicable at line {index + 1}")

    def _append(self, event: Mapping[str, Any]) -> None:
        line = canonical_bytes(dict(event))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        self.high_water = int(event["seq"])

    def _ensure_writable(self) -> None:
        if self.recovery.get("status") != "CLEAN":
            raise AuthorizationStoreError("E_AUTH_RECOVERY", "/journal", "reconcile or repair recovery tail before writing")

    def put(self, *, scope: str, operation_id: str, expected_generation: int, record: Mapping[str, Any]) -> ApprovalHead:
        self._ensure_writable()
        normalized = validate_approval(record)
        replay = ("approval", operation_id) in self._operation_events
        head = self.ledger.put(scope=scope, operation_id=operation_id, expected_generation=expected_generation, record=normalized)
        if replay:
            return head
        self._append({"seq": self.high_water + 1, "type": "approval", "scope": scope, "operation_id": operation_id,
                      "expected_generation": expected_generation, "record": normalized})
        self._operation_events.add(("approval", operation_id))
        return head

    def put_authorization(self, *, scope: str, operation_id: str, expected_generation: int,
                          record: Mapping[str, Any]) -> ApprovalHead:
        validate_authorization(record)
        return self.put(scope=scope, operation_id=operation_id,
                        expected_generation=expected_generation, record=record)

    def lock(self, *, scope: str, receipt_id: str, operation_id: str, bindings: list[Mapping[str, Any]]) -> InputLock:
        self._ensure_writable()
        replay = ("lock", operation_id) in self._operation_events
        lock = self.ledger.lock(scope=scope, receipt_id=receipt_id, operation_id=operation_id, bindings=bindings)
        if replay:
            return lock
        self._append({"seq": self.high_water + 1, "type": "lock", "scope": scope, "operation_id": operation_id,
                      "receipt_id": receipt_id, "bindings": copy.deepcopy(bindings)})
        self._operation_events.add(("lock", operation_id))
        return lock

    def consume_once(self, *, scope: str, action: str, input_refs: list[Mapping[str, Any]],
                     operation_id: str, expected_generation: int,
                     now: Any = None) -> bool:
        self._ensure_writable()
        replay = ("consume", operation_id) in self._operation_events
        result = self.ledger.consume_once(scope=scope, action=action, input_refs=input_refs,
                                          operation_id=operation_id, expected_generation=expected_generation, now=now)
        if not result or replay:
            return result
        self._append({"seq": self.high_water + 1, "type": "consume", "scope": scope,
                      "operation_id": operation_id, "expected_generation": expected_generation,
                      "action": action, "input_refs": copy.deepcopy(input_refs)})
        self._operation_events.add(("consume", operation_id))
        return True

    def _has_lock_receipt(self, receipt_id: str) -> bool:
        # The in-memory ledger intentionally exposes no mutable receipt map; a
        # replay can be recognized by scanning the journal's immutable events.
        if not self.path.exists():
            return False
        for line in self.path.read_bytes().splitlines():
            try:
                event = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if event.get("type") == "lock" and event.get("receipt_id") == receipt_id:
                return True
        return False

    def reconcile(self) -> Dict[str, Any]:
        return {"high_water": self.high_water, "recovery": copy.deepcopy(self.recovery), "scopes": sorted(self.ledger._heads)}


__all__ = ["AuthorizationStoreError", "PersistentApprovalStore"]
