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

from .authorization import ApprovalLedger, ApprovalHead, AuthorizationError, InputLock, canonical_bytes, validate_approval


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
                if index == len(lines) - 1:
                    self.recovery = {"status": "TRUNCATED_TAIL", "ignored_tail": True, "line": index + 1}
                    break
                self._fail("E_AUTH_JOURNAL", f"invalid non-tail event at line {index + 1}")
            if not complete and index == len(lines) - 1:
                self.recovery = {"status": "TRUNCATED_TAIL", "ignored_tail": True, "line": index + 1}
                break
            if not isinstance(event, dict) or set(event) != {"seq", "type", "scope", "operation_id", "expected_generation", "record"} and event.get("type") != "lock":
                # Lock events carry a different closed shape and are handled below.
                if not isinstance(event, dict) or set(event) != {"seq", "type", "scope", "operation_id", "receipt_id", "bindings"}:
                    self._fail("E_AUTH_JOURNAL", f"invalid event shape at line {index + 1}")
            seq = event.get("seq")
            if type(seq) is not int or seq != self.high_water + 1:
                self._fail("E_AUTH_JOURNAL", f"non-contiguous sequence at line {index + 1}")
            self.high_water = seq
            self._operation_events.add((event["type"], event["operation_id"]))
            if event["type"] == "approval":
                self.ledger.put(scope=event["scope"], operation_id=event["operation_id"], expected_generation=event["expected_generation"], record=event["record"])
            elif event["type"] == "lock":
                self.ledger.lock(scope=event["scope"], receipt_id=event["receipt_id"], operation_id=event["operation_id"], bindings=event["bindings"])
            else:
                self._fail("E_AUTH_JOURNAL", f"unknown event type at line {index + 1}")

    def _append(self, event: Mapping[str, Any]) -> None:
        line = canonical_bytes(dict(event))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        self.high_water = int(event["seq"])

    def put(self, *, scope: str, operation_id: str, expected_generation: int, record: Mapping[str, Any]) -> ApprovalHead:
        normalized = validate_approval(record)
        replay = ("approval", operation_id) in self._operation_events
        head = self.ledger.put(scope=scope, operation_id=operation_id, expected_generation=expected_generation, record=normalized)
        if replay:
            return head
        self._append({"seq": self.high_water + 1, "type": "approval", "scope": scope, "operation_id": operation_id,
                      "expected_generation": expected_generation, "record": normalized})
        self._operation_events.add(("approval", operation_id))
        return head

    def lock(self, *, scope: str, receipt_id: str, operation_id: str, bindings: list[Mapping[str, Any]]) -> InputLock:
        replay = ("lock", operation_id) in self._operation_events
        lock = self.ledger.lock(scope=scope, receipt_id=receipt_id, operation_id=operation_id, bindings=bindings)
        if replay:
            return lock
        self._append({"seq": self.high_water + 1, "type": "lock", "scope": scope, "operation_id": operation_id,
                      "receipt_id": receipt_id, "bindings": copy.deepcopy(bindings)})
        self._operation_events.add(("lock", operation_id))
        return lock

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
